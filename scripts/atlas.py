#!/usr/bin/env python3
"""
ATLAS v3.Autonomous Territorial Listening & Analysis System
Multi-source intelligence engine with anomaly detection and claims tracking.

Usage:
    python3 scripts/atlas.py              # Run with current power level
    python3 scripts/atlas.py --power IDLE  # Run at specific power level
    python3 scripts/atlas.py --status      # Show current status
    python3 scripts/atlas.py --deploy      # Push report to GitHub
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import shutil
import signal
import sys
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    from atlas_intel import (
        assess_anomaly, find_nearby_bases, find_nearby_chokepoints,
        find_nearby_conflict_zones, find_nearby_nuclear_sites,
        identify_aircraft, get_country_centroid, haversine,
        COUNTRY_CENTROIDS,
    )
    HAS_INTEL = True
except ImportError:
    HAS_INTEL = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BOSS_HQ = Path.home() / "Desktop" / "BOSS_HQ"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "BOSS"
ATLAS_DIR = APP_SUPPORT / "atlas_data"
CONFIG_PATH = ATLAS_DIR / "config.json"
REPORT_PATH = ATLAS_DIR / "latest.json"
PREV_REPORT_PATH = ATLAS_DIR / "previous.json"
CALIBRATION_PATH = ATLAS_DIR / "calibration.json"
LOG_PATH = ATLAS_DIR / "atlas.log"
SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env"

ATLAS_DIR.mkdir(parents=True, exist_ok=True)

_cal_cache = None

def load_calibrated_weights() -> dict:
    global _cal_cache
    if _cal_cache is not None:
        return _cal_cache
    if CALIBRATION_PATH.exists():
        try:
            cal = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
            _cal_cache = cal.get("tuned_weights", {})
            return _cal_cache
        except (json.JSONDecodeError, OSError):
            pass
    _cal_cache = {}
    return _cal_cache

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------

def load_env():
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if v and k not in os.environ:
                    os.environ[k] = v

load_env()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

from logging.handlers import RotatingFileHandler
import fcntl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ATLAS] %(levelname)s %(message)s",
    handlers=[
        RotatingFileHandler(str(LOG_PATH), maxBytes=5*1024*1024, backupCount=3,
                            encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("atlas")

# ---------------------------------------------------------------------------
# Atomic write + scan lock
# ---------------------------------------------------------------------------

LOCK_PATH = ATLAS_DIR / "atlas.lock"
TRADER_INTEL_PATH = ATLAS_DIR / "trader_intel.json"


def atomic_write_json(path: Path, data: dict):
    """Write JSON atomically: write to temp, then rename."""
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def acquire_scan_lock():
    """Acquire exclusive scan lock. Returns file descriptor or None."""
    fd = open(LOCK_PATH, 'w')
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write(str(os.getpid()))
        fd.flush()
        return fd
    except (BlockingIOError, OSError):
        fd.close()
        return None


def release_scan_lock(fd):
    """Release scan lock."""
    if fd:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()
        except OSError:
            pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POWER_LEVELS = {
    "SLEEP":  {"interval_hours": 6},
    "IDLE":   {"interval_hours": 2},
    "ACTIVE": {"interval_hours": 0.5},
    "SURGE":  {"interval_hours": 0, "description": "Continuous"},
}

POWER_SOURCES = {
    "SLEEP":  ["usgs", "noaa", "nasa", "iss", "polymarket", "currencies", "commodities", "congress"],
    "IDLE":   ["usgs", "noaa", "nasa", "iss", "polymarket", "manifold", "metaculus",
               "gdelt", "reddit", "hackernews", "rss", "fred", "govinfo", "congress",
               "currencies", "commodities", "global_weather",
               "space_weather", "treasury", "cisa",
               "think_tanks", "official_feeds", "world_bank", "gdacs",
               "sec_edgar", "fema", "bls", "eia", "finnhub", "patents", "alpha_vantage",
               "telegram", "futures", "firms"],
    "ACTIVE": ["usgs", "noaa", "nasa", "iss", "polymarket", "manifold", "metaculus",
               "gdelt", "reddit", "hackernews", "rss", "fred", "govinfo", "congress",
               "currencies", "commodities", "global_weather",
               "space_weather", "treasury", "cisa",
               "think_tanks", "official_feeds", "world_bank", "gdacs",
               "sec_edgar", "fema", "bls", "eia", "finnhub", "patents", "alpha_vantage",
               "telegram", "futures", "firms",
               "adsb", "wikipedia", "safecast", "crest",
               "volcanoes", "fires", "aviation_wx", "sanctions"],
    "SURGE":  ["usgs", "noaa", "nasa", "iss", "polymarket", "manifold", "metaculus",
               "gdelt", "reddit", "hackernews", "rss", "fred", "govinfo", "congress",
               "currencies", "commodities", "global_weather",
               "space_weather", "treasury", "cisa",
               "think_tanks", "official_feeds", "world_bank", "gdacs",
               "sec_edgar", "fema", "bls", "eia", "finnhub", "patents", "alpha_vantage",
               "telegram", "futures", "firms",
               "adsb", "wikipedia", "safecast", "crest",
               "volcanoes", "fires", "aviation_wx", "sanctions",
               "aisstream", "acled", "ioda"],
}

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ATLAS/2.0"
HTTP_TIMEOUT = 15
SOURCE_TIMEOUT = 120  # Max seconds any single source scan can run before being killed
GDELT_COOLDOWN = 30

# Source reliability tiering (Admiralty-inspired)
SOURCE_RELIABILITY = {
    "usgs": 0.95,          # Sensor data, peer-reviewed
    "cisa": 0.95,          # Government technical
    "noaa": 0.95,          # Sensor data
    "nasa": 0.90,          # Institutional science
    "think_tanks": 0.85,   # Expert institutional analysis
    "official_feeds": 0.85,# Central bank / government statements
    "treasury": 0.90,      # US government data
    "fred": 0.90,          # Federal Reserve data
    "bls": 0.90,           # Bureau of Labor Statistics
    "eia": 0.85,           # Energy Information Administration
    "fema": 0.85,          # Disaster declarations
    "sec_edgar": 0.85,     # SEC filings (verified)
    "adsb": 0.75,          # Empirical but incomplete (transponder-off)
    "safecast": 0.75,      # Citizen science, calibrated
    "polymarket": 0.70,    # Money-weighted crowd
    "kalshi": 0.70,        # Regulated exchange
    "manifold": 0.50,      # Play money, less reliable
    "metaculus": 0.65,     # Expert forecasting community
    "gdelt": 0.55,         # Aggregated, noisy, no editorial filter
    "sanctions": 0.80,     # Official government lists
    "world_bank": 0.85,    # Institutional data
    "gdacs": 0.80,         # UN disaster coordination
    "rss": 0.60,           # Mixed quality news feeds
    "finnhub": 0.70,       # Financial data provider
    "alpha_vantage": 0.65, # Financial data
    "patents": 0.80,       # Official filings
    "currencies": 0.80,    # Market data
    "commodities": 0.75,   # Yahoo Finance (undocumented API)
    "telegram": 0.45,      # OSINT channels, fast but unverified raw intel
    "futures": 0.80,       # Market data, money-weighted signal
    "firms": 0.90,         # NASA satellite sensor data
    "reddit": 0.25,        # Anonymous, unverified, easily manipulated
    "hackernews": 0.30,    # Community curated but unverified
    "wikipedia": 0.35,     # Can be manipulated
    "crest": 0.60,         # Declassified (historical)
    "govinfo": 0.80,       # US government publications
    "congress": 0.90,      # Congress.gov official bill/vote data
}

NTFY_BASE = "https://ntfy.sh"
NTFY_TOPIC = "bossai-bostonrossall-alerts"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "BosRoss/bosssystems.co")

# Historical calibration for claims tracker
HISTORICAL_CALIBRATION = [
    {"claim": "MKUltra mind control program", "status": "confirmed", "years_denied": 24,
     "evidence": "CIA Director admitted 1977, documents released via FOIA"},
    {"claim": "COINTELPRO domestic surveillance", "status": "confirmed", "years_denied": 15,
     "evidence": "Church Committee 1975, FBI documents released"},
    {"claim": "Gulf of Tonkin incident fabricated", "status": "confirmed", "years_denied": 39,
     "evidence": "NSA documents declassified 2005"},
    {"claim": "NSA mass surveillance (PRISM)", "status": "confirmed", "years_denied": 7,
     "evidence": "Snowden documents 2013"},
    {"claim": "Tuskegee syphilis experiment", "status": "confirmed", "years_denied": 40,
     "evidence": "Exposed by AP 1972, Clinton apology 1997"},
    {"claim": "Operation Mockingbird media infiltration", "status": "partially confirmed",
     "years_denied": 25, "evidence": "Church Committee found CIA paid journalists, full scope debated"},
    {"claim": "Operation Northwoods false flag proposal", "status": "confirmed",
     "years_denied": 35, "evidence": "JFK assassination records released 1997"},
]

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "power_level": "SLEEP",
    "last_run": None,
    "total_runs": 0,
    "total_data_points": 0,
}

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg: dict):
    atomic_write_json(CONFIG_PATH, cfg)

# ---------------------------------------------------------------------------
# Previous scan state (for trend detection)
# ---------------------------------------------------------------------------

_prev_report = None

def load_previous_report() -> dict:
    global _prev_report
    if _prev_report is not None:
        return _prev_report
    if PREV_REPORT_PATH.exists():
        try:
            _prev_report = json.loads(PREV_REPORT_PATH.read_text(encoding="utf-8"))
            return _prev_report
        except (json.JSONDecodeError, OSError):
            pass
    _prev_report = {}
    return _prev_report

def get_previous_value(key_path: str, default=None):
    """Get a value from the previous scan report. key_path like 'commodities' or nested."""
    prev = load_previous_report()
    keys = key_path.split(".")
    val = prev
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    return val if val is not None else default

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT})

def safe_get(url, headers=None, params=None, timeout=None):
    try:
        r = _session.get(url, headers=headers or {}, params=params or {},
                         timeout=timeout or HTTP_TIMEOUT)
        if r.status_code == 429:
            log.warning("Rate limited on %s", url)
            return None
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        log.warning("Request failed: %s.%s", url[:80], e)
        return None

def safe_source(name, func):
    """Run a source function with error isolation and per-source timeout."""
    default_ret = {} if name == "iss" else []
    result_box = [default_ret]
    error_box = [None]

    def _worker():
        try:
            result_box[0] = func()
        except Exception as e:
            error_box[0] = e

    log.info("Scanning: %s", name)
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=SOURCE_TIMEOUT)

    if t.is_alive():
        log.error("Source %s TIMED OUT after %ds.killing", name, SOURCE_TIMEOUT)
        return default_ret

    if error_box[0] is not None:
        log.error("Source %s failed: %s", name, error_box[0])
        return default_ret

    result = result_box[0]
    log.info("  %s: got %s items", name, len(result) if isinstance(result, list) else "1")
    return result

# ---------------------------------------------------------------------------
# Source: GDELT 2.0
# ---------------------------------------------------------------------------

def _gdelt_fetch(query: str, category: str, max_records: int = 50) -> List[Dict]:
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": str(max_records),
        "format": "json",
        "sort": "DateDesc",
    }
    for attempt in range(2):
        try:
            r = _session.get("https://api.gdeltproject.org/api/v2/doc/doc",
                             params=params, timeout=HTTP_TIMEOUT)
            if r.status_code == 429:
                if attempt == 0:
                    log.info("GDELT rate limited, retry in %ds", GDELT_COOLDOWN)
                    time.sleep(GDELT_COOLDOWN)
                    continue
                log.info("GDELT still rate limited, skipping: %s", query[:40])
                return []
            r.raise_for_status()
            data = r.json()
            results = []
            for a in data.get("articles", []):
                tone = a.get("tone", 0)
                try:
                    tone = float(str(tone).split(",")[0])
                except (ValueError, IndexError):
                    tone = 0.0
                results.append({
                    "source": "gdelt",
                    "title": a.get("title", "")[:200],
                    "url": a.get("url", ""),
                    "published": a.get("seendate", ""),
                    "domain": a.get("domain", ""),
                    "language": a.get("language", "English"),
                    "country": a.get("sourcecountry", ""),
                    "category": category,
                    "tone": round(tone, 2),
                    "date": a.get("seendate", ""),
                })
            return results
        except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
            log.warning("GDELT query failed: %s.%s", query[:40], e)
            return []
    log.warning("GDELT failed for: %s", query[:40])
    return []

def scan_gdelt() -> List[Dict]:
    queries = [
        ("(conflict OR military OR attack OR missile OR strike OR war OR invasion OR bombing OR ceasefire) (Iran OR Israel OR Ukraine OR Russia OR Taiwan OR China)", "conflict"),
        ("(disaster OR earthquake OR flood OR wildfire OR hurricane OR tornado)", "disaster"),
        ("(economic OR crisis OR inflation OR recession OR sanctions OR tariff)", "economic"),
    ]
    results = []
    for i, (query, category) in enumerate(queries):
        if i > 0:
            time.sleep(GDELT_COOLDOWN)
        results.extend(_gdelt_fetch(query, category))
    seen = set()
    deduped = []
    for r in results:
        key = r["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped

# ---------------------------------------------------------------------------
# Source: ADS-B (military aircraft via adsb.lol)
# ---------------------------------------------------------------------------

def scan_adsb() -> List[Dict]:
    r = safe_get("https://api.adsb.lol/v2/mil")
    if r is None:
        return []
    results = []
    try:
        data = r.json()
        for ac in data.get("ac", [])[:100]:
            if not ac.get("lat") or not ac.get("lon"):
                continue
            results.append({
                "source": "adsb",
                "hex": ac.get("hex", ""),
                "callsign": (ac.get("flight") or "").strip(),
                "type": ac.get("t", ""),
                "description": ac.get("desc", ""),
                "operator": ac.get("ownOp", ""),
                "lat": ac.get("lat"),
                "lon": ac.get("lon"),
                "altitude_ft": ac.get("alt_baro", 0),
                "speed_kts": ac.get("gs", 0),
                "squawk": ac.get("squawk", ""),
                "country": ac.get("r", ""),
                "category": ac.get("category", ""),
                "emergency": ac.get("squawk") in ("7500", "7600", "7700"),
                "date": datetime.now(timezone.utc).isoformat(),
            })
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: AISStream (ships.requires API key)
# ---------------------------------------------------------------------------

def scan_aisstream() -> List[Dict]:
    key = os.environ.get("AISSTREAM_API_KEY", "")
    if not key:
        log.info("  aisstream: no API key, skipping")
        return []
    # AISStream is WebSocket-based; use their REST search endpoint instead
    # For now, return empty.WebSocket integration would need asyncio
    log.info("  aisstream: WebSocket source.would need async runtime, skipping for now")
    return []

# ---------------------------------------------------------------------------
# Source: Wikipedia EventStreams (edit velocity)
# ---------------------------------------------------------------------------

def scan_wikipedia() -> List[Dict]:
    # Check recent changes for edit velocity on geopolitical articles
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "recentchanges",
        "rcnamespace": "0",
        "rclimit": "50",
        "rctype": "edit",
        "rcprop": "title|timestamp|sizes|comment",
        "format": "json",
    }
    r = safe_get(url, params=params)
    if r is None:
        return []

    results = []
    title_counts = {}
    try:
        changes = r.json().get("query", {}).get("recentchanges", [])
        for c in changes:
            title = c.get("title", "")
            title_counts[title] = title_counts.get(title, 0) + 1
            old = c.get("oldlen", 0)
            new = c.get("newlen", 0)
            delta = abs(new - old)
            if delta > 500:
                results.append({
                    "source": "wikipedia",
                    "title": title,
                    "timestamp": c.get("timestamp", ""),
                    "date": c.get("timestamp", ""),
                    "delta_bytes": new - old,
                    "comment": (c.get("comment") or "")[:100],
                })
        # Flag articles with high edit velocity (edit storms)
        for title, count in title_counts.items():
            if count >= 3:
                results.append({
                    "source": "wikipedia",
                    "title": f"EDIT STORM: {title}",
                    "edit_count": count,
                    "flag": "edit_storm",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: IODA (Internet Outage Detection)
# ---------------------------------------------------------------------------

def scan_ioda() -> List[Dict]:
    # Georgia Tech IODA API
    now = int(time.time())
    start = now - 86400  # last 24h
    url = f"https://api.ioda.inetintel.cc.gatech.edu/v2/signals/raw/country?from={start}&until={now}"
    r = safe_get(url, timeout=20)
    if r is None:
        return []
    results = []
    try:
        data = r.json()
        for entry in data.get("data", [])[:50]:
            entity = entry.get("entity", {})
            country_code = entity.get("code", "")
            country_name = entity.get("name", "")
            # Look for significant drops
            values = entry.get("values", [])
            if values and len(values) >= 2:
                recent = values[-1] if values[-1] is not None else 0
                baseline = values[0] if values[0] is not None else 0
                if baseline and recent and baseline > 0:
                    drop_pct = ((baseline - recent) / baseline) * 100
                    if drop_pct > 20:
                        results.append({
                            "source": "ioda",
                            "country": country_code,
                            "country_name": country_name,
                            "drop_percent": round(drop_pct, 1),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "severity": "critical" if drop_pct > 50 else "warning",
                        })
    except (json.JSONDecodeError, ValueError, KeyError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: FRED (Federal Reserve Economic Data)
# ---------------------------------------------------------------------------

def scan_fred() -> List[Dict]:
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        log.info("  fred: no API key, skipping")
        return []
    indicators = [
        ("UNRATE", "Unemployment Rate"),
        ("CPIAUCSL", "Consumer Price Index"),
        ("GDP", "Gross Domestic Product"),
        ("DFF", "Federal Funds Rate"),
        ("T10Y2Y", "Treasury Yield Spread (10Y-2Y)"),
    ]
    results = []
    for series_id, name in indicators:
        params = {
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": "5",
        }
        r = safe_get("https://api.stlouisfed.org/fred/series/observations", params=params)
        if r is None:
            continue
        try:
            obs = r.json().get("observations", [])
            if len(obs) >= 2:
                current = obs[0]
                previous = obs[1]
                try:
                    val = float(current.get("value", 0))
                    prev_val = float(previous.get("value", 0))
                    change = val - prev_val
                    pct_change = (change / prev_val * 100) if prev_val else 0
                except (ValueError, ZeroDivisionError):
                    val, prev_val, change, pct_change = 0, 0, 0, 0

                results.append({
                    "source": "fred",
                    "indicator": name,
                    "series_id": series_id,
                    "value": val,
                    "previous": prev_val,
                    "change": round(change, 3),
                    "pct_change": round(pct_change, 2),
                    "date": current.get("date", ""),
                    "shock": abs(pct_change) > 10,
                })
        except (json.JSONDecodeError, ValueError):
            pass
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: Polymarket
# ---------------------------------------------------------------------------

def scan_polymarket() -> List[Dict]:
    results = []
    for offset in [0, 25]:
        r = safe_get(f"https://gamma-api.polymarket.com/markets?closed=false&limit=25&offset={offset}&order=volume24hr&ascending=false")
        if r is None:
            break
        try:
            data = r.json()
            markets = data if isinstance(data, list) else []
            for m in markets:
                question = m.get("question", "")
                if not question:
                    continue
                outcomes = m.get("outcomePrices", "[]")
                try:
                    prices = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
                    prob = round(float(prices[0]) * 100, 1) if prices else 0
                except (json.JSONDecodeError, IndexError, ValueError, TypeError):
                    prob = 0
                results.append({
                    "source": "polymarket",
                    "question": question[:200],
                    "probability": prob,
                    "volume": m.get("volume", 0),
                    "url": f"https://polymarket.com/event/{m.get('slug', '')}",
                    "end_date": m.get("endDate", ""),
                    "date": m.get("startDate", m.get("createdAt", datetime.now(timezone.utc).isoformat())),
                    "description": m.get("description", "")[:300],
                })
        except (json.JSONDecodeError, ValueError):
            pass
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: Manifold Markets
# ---------------------------------------------------------------------------

def scan_manifold() -> List[Dict]:
    results = []
    for term in ["geopolitics war", "economy recession", "AI technology", "climate disaster"]:
        r = safe_get(f"https://api.manifold.markets/v0/search-markets?term={quote(term)}&sort=liquidity&limit=15")
        if r is None:
            continue
        try:
            data = r.json()
            markets = data if isinstance(data, list) else []
            for m in markets:
                question = m.get("question", "")
                if not question:
                    continue
                prob = m.get("probability", 0)
                results.append({
                    "source": "manifold",
                    "question": question[:200],
                    "probability": round(float(prob) * 100, 1) if prob else 0,
                    "traders": m.get("uniqueBettorCount", 0),
                    "volume": m.get("volume", 0),
                    "url": f"https://manifold.markets/{m.get('creatorUsername', '')}/{m.get('slug', '')}",
                    "date": datetime.fromtimestamp(m.get("createdTime", 0) / 1000, tz=timezone.utc).isoformat() if m.get("createdTime") else "",
                    "close_date": datetime.fromtimestamp(m.get("closeTime", 0) / 1000, tz=timezone.utc).isoformat() if m.get("closeTime") else "",
                })
        except (json.JSONDecodeError, ValueError):
            pass
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: Metaculus
# ---------------------------------------------------------------------------

def scan_metaculus() -> List[Dict]:
    r = safe_get("https://www.metaculus.com/api/questions/?limit=20&order_by=-activity&status=open&type=forecast&format=json")
    if r is None:
        r = safe_get("https://www.metaculus.com/questions/feed/rss/")
        if r is None:
            return []
        results = []
        try:
            root = ET.fromstring(r.text)
            for item in root.findall(".//item")[:15]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if not title:
                    continue
                pub_el = item.findtext("pubDate") or item.findtext("dc:date") or ""
                results.append({
                    "source": "metaculus",
                    "question": title[:200],
                    "url": link,
                    "date": pub_el.strip() if pub_el else "",
                })
        except ET.ParseError:
            pass
        return results
    results = []
    try:
        data = r.json()
        questions = data.get("results", data) if isinstance(data, dict) else data
        if not isinstance(questions, list):
            questions = []
        for q in questions[:20]:
            title = q.get("title", "")
            qid = q.get("id", "")
            if not title:
                continue
            community_pred = q.get("community_prediction", {})
            prob = None
            if isinstance(community_pred, dict):
                prob = community_pred.get("full", {}).get("q2")
            results.append({
                "source": "metaculus",
                "question": title[:200],
                "url": f"https://www.metaculus.com/questions/{qid}/",
                "probability": round(prob * 100, 1) if prob else None,
                "date": q.get("publish_time", ""),
            })
    except (ValueError, KeyError, TypeError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: USGS Earthquakes
# ---------------------------------------------------------------------------

def _quake_is_significant(mag, lat, lon, depth_km, alert, tsunami, felt) -> bool:
    """Only keep quakes that matter: big ones, or smaller ones near strategic locations."""
    if mag >= 6.0:
        return True
    if tsunami:
        return True
    if alert in ("yellow", "orange", "red"):
        return True
    if felt and felt >= 100:
        return True
    if mag >= 5.0 and HAS_INTEL:
        if find_nearby_nuclear_sites(lat, lon, 300):
            return True
        if find_nearby_bases(lat, lon, 250):
            return True
        if find_nearby_conflict_zones(lat, lon, 600):
            return True
        if find_nearby_chokepoints(lat, lon, 400):
            return True
    if mag >= 5.0 and depth_km is not None and depth_km < 10:
        return True
    return False


def scan_usgs() -> List[Dict]:
    results = []
    r = safe_get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson")
    if r is None:
        return results
    try:
        data = r.json()
        for feat in data.get("features", [])[:50]:
            props = feat.get("properties", {})
            coords = feat.get("geometry", {}).get("coordinates", [])
            mag = props.get("mag", 0)
            if not mag or mag < 4.5:
                continue
            ts = (props.get("time", 0) or 0) / 1000
            lat = coords[1] if len(coords) >= 2 else 0
            lon = coords[0] if len(coords) >= 2 else 0
            depth = round(coords[2], 1) if len(coords) >= 3 else None
            alert = props.get("alert", "")
            tsunami = props.get("tsunami", 0)
            felt = props.get("felt", 0)
            if not _quake_is_significant(mag, lat, lon, depth, alert, tsunami, felt):
                continue
            results.append({
                "source": "usgs",
                "magnitude": mag,
                "place": props.get("place", ""),
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "",
                "time": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "",
                "coordinates": coords[:2] if len(coords) >= 2 else [],
                "alert": alert,
                "tsunami": tsunami,
                "felt": felt,
                "depth_km": depth,
                "url": props.get("url", ""),
            })
    except (json.JSONDecodeError, ValueError):
        pass
    seen = set()
    deduped = []
    for q in results:
        key = (q.get("magnitude"), q.get("place"), q.get("time", "")[:16])
        if key not in seen:
            seen.add(key)
            deduped.append(q)
    return deduped

# ---------------------------------------------------------------------------
# Source: NOAA Weather
# ---------------------------------------------------------------------------

TARGET_STATES = ["TX", "MS", "AR", "AL", "TN", "OK", "NM", "LA", "FL", "CA", "GA", "SC", "NC", "MO", "KS"]

def scan_noaa() -> List[Dict]:
    results = []
    for state in TARGET_STATES:
        r = safe_get(f"https://api.weather.gov/alerts/active?area={state}",
                     headers={"Accept": "application/geo+json"})
        if r is None:
            time.sleep(1)
            continue
        try:
            features = r.json().get("features", [])
            for feat in features[:10]:
                props = feat.get("properties", {})
                event = props.get("event", "")
                severity = props.get("severity", "Unknown")
                results.append({
                    "source": "noaa",
                    "event": event,
                    "state": state,
                    "headline": props.get("headline", "")[:200],
                    "severity": severity,
                    "urgency": props.get("urgency", ""),
                    "area": props.get("areaDesc", "")[:200],
                    "date": props.get("effective", props.get("onset", "")),
                    "expires": props.get("expires", ""),
                    "description": props.get("description", "")[:400],
                })
        except (json.JSONDecodeError, ValueError):
            pass
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: NASA EONET
# ---------------------------------------------------------------------------

def scan_nasa() -> List[Dict]:
    r = safe_get("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=30")
    if r is None:
        return []
    results = []
    try:
        for event in r.json().get("events", []):
            categories = [c.get("id", "") for c in event.get("categories", [])]
            geometries = event.get("geometry", [])
            coords = None
            event_date = None
            if geometries:
                latest = geometries[-1]
                coords = latest.get("coordinates")
                event_date = latest.get("date", "")
            results.append({
                "source": "nasa",
                "title": event.get("title", ""),
                "category": categories[0] if categories else "unknown",
                "date": event_date[:10] if event_date else "",
                "coordinates": coords,
                "url": event.get("link", ""),
            })
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: ISS Position
# ---------------------------------------------------------------------------

def scan_iss() -> dict:
    r = safe_get("http://api.open-notify.org/iss-now.json")
    if r is None:
        return {}
    try:
        data = r.json()
        pos = data.get("iss_position", {})
        return {
            "latitude": float(pos.get("latitude", 0)),
            "longitude": float(pos.get("longitude", 0)),
            "timestamp": datetime.fromtimestamp(
                data.get("timestamp", 0), tz=timezone.utc
            ).isoformat(),
        }
    except (json.JSONDecodeError, ValueError):
        return {}

# ---------------------------------------------------------------------------
# Source: Safecast (radiation)
# ---------------------------------------------------------------------------

def scan_safecast() -> List[Dict]:
    r = safe_get("https://api.safecast.org/measurements.json?order=created_at+desc&per_page=50")
    if r is None:
        return []
    results = []
    try:
        data = r.json()
        for m in data[:30]:
            cpm = m.get("value", 0)
            if cpm and cpm > 100:  # elevated readings only
                results.append({
                    "source": "safecast",
                    "cpm": cpm,
                    "latitude": m.get("latitude"),
                    "longitude": m.get("longitude"),
                    "captured_at": m.get("captured_at", ""),
                    "unit": m.get("unit", "cpm"),
                    "device_id": m.get("device_id", ""),
                    "elevated": cpm > 350,
                    "date": m.get("captured_at", ""),
                })
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: ACLED (Armed Conflict)
# ---------------------------------------------------------------------------

def scan_acled() -> List[Dict]:
    key = os.environ.get("ACLED_API_KEY", "")
    email = os.environ.get("ACLED_EMAIL", "")
    if not key or not email:
        log.info("  acled: no API key/email, skipping")
        return []
    yesterday = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    params = {
        "key": key,
        "email": email,
        "event_date": f"{yesterday}|{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "event_date_where": "BETWEEN",
        "limit": "50",
    }
    r = safe_get("https://api.acleddata.com/acled/read", params=params, timeout=20)
    if r is None:
        return []
    results = []
    try:
        data = r.json().get("data", [])
        for event in data[:30]:
            results.append({
                "source": "acled",
                "event_type": event.get("event_type", ""),
                "sub_event_type": event.get("sub_event_type", ""),
                "country": event.get("country", ""),
                "location": event.get("location", ""),
                "date": event.get("event_date", ""),
                "fatalities": event.get("fatalities", 0),
                "latitude": event.get("latitude"),
                "longitude": event.get("longitude"),
                "notes": (event.get("notes") or "")[:200],
            })
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: Reddit (pain signals + global)
# ---------------------------------------------------------------------------

SUBREDDITS = [
    # Geopolitical / intelligence
    "worldnews", "geopolitics", "intelligence", "CredibleDefense",
    "NuclearPower", "foreignpolicy", "MiddleEastNews",
    # Economic / markets
    "economics", "CryptoCurrency", "wallstreetbets", "stocks",
    "SupplyChain", "commodities",
    # Business pain signals (Boston's market)
    "smallbusiness", "HVAC", "Plumbing", "electricians",
    "Roofing", "lawncare", "AutoRepair", "contractors",
    # Technology / AI / cyber
    "technology", "artificial", "cybersecurity", "privacy",
    "MachineLearning",
    # Environment / disaster / resilience
    "collapse", "preppers", "weather", "TropicalWeather",
    "Earthquakes", "climate",
    # Infrastructure / transport
    "aviation", "shipping", "space", "energy",
    # Regional
    "india", "europe", "africa", "China", "LatinAmerica",
    # US Domestic / Policy
    "politics", "law",
]

def scan_reddit() -> List[Dict]:
    results = []
    for sub in SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/hot.rss?limit=20"
        r = safe_get(url)
        if r is None:
            time.sleep(1)
            continue
        try:
            root = ET.fromstring(r.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:20]:
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                updated_el = entry.find("atom:updated", ns)
                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                link = link_el.get("href", "") if link_el is not None else ""
                updated = updated_el.text.strip() if updated_el is not None and updated_el.text else ""
                if title:
                    results.append({
                        "source": "reddit",
                        "subreddit": f"r/{sub}",
                        "title": title[:200],
                        "url": link,
                        "timestamp": updated,
                        "date": updated,
                    })
        except ET.ParseError:
            pass
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: Hacker News
# ---------------------------------------------------------------------------

def scan_hackernews() -> List[Dict]:
    r = safe_get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if r is None:
        return []
    results = []
    try:
        ids = r.json()[:30]
    except (json.JSONDecodeError, ValueError):
        return []
    for sid in ids:
        r2 = safe_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        if r2 is None:
            continue
        try:
            s = r2.json()
            ts = s.get("time", 0)
            results.append({
                "source": "hackernews",
                "title": s.get("title", "")[:200],
                "url": s.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                "score": s.get("score", 0),
                "comments": s.get("descendants", 0),
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "",
            })
        except (json.JSONDecodeError, ValueError):
            pass
        time.sleep(0.3)
    return results

# ---------------------------------------------------------------------------
# Source: RSS Feeds.TIER 2 (mainstream news, confirmation only)
# ---------------------------------------------------------------------------

NEWS_FEEDS = [
    ("bbc_world", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("bbc_business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("aljazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("nyt_world", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("bbc_africa", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
    ("bbc_asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml"),
    ("bbc_europe", "https://feeds.bbci.co.uk/news/world/europe/rss.xml"),
    ("bbc_latam", "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml"),
    ("bbc_mideast", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("bbc_economy", "https://feeds.bbci.co.uk/news/business/economy/rss.xml"),
    ("bbc_science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("ars_technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("techcrunch_ai", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("wired", "https://www.wired.com/feed/rss"),
    ("the_verge", "https://www.theverge.com/rss/index.xml"),
    ("phys_earth", "https://phys.org/rss-feed/earth-news/"),
    ("who_news", "https://www.who.int/rss-feeds/news-english.xml"),
]

# ---------------------------------------------------------------------------
# Source: Think Tank & Analysis Feeds.TIER 1 (primary intelligence)
# ---------------------------------------------------------------------------

ANALYSIS_FEEDS = [
    # Conflict / geopolitical analysis
    ("atlantic_council", "https://www.atlanticcouncil.org/feed/"),
    ("crisis_group", "https://www.crisisgroup.org/rss.xml"),
    ("war_on_rocks", "https://warontherocks.com/feed/"),
    ("brookings", "https://www.brookings.edu/feed/"),
    ("ecfr", "https://ecfr.eu/feed/"),
    ("fdd", "https://www.fdd.org/feed/"),
    # Arms / nuclear / WMD
    ("arms_control", "https://www.armscontrol.org/taxonomy/term/30/feed"),
    ("rand_commentary", "https://www.rand.org/pubs/commentary.xml"),
    # Security / defense primary
    ("defense_news", "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("foreign_policy", "https://foreignpolicy.com/feed/"),
    ("just_security", "https://www.justsecurity.org/feed/"),
    ("heritage", "https://www.heritage.org/rss"),
    # OSINT / investigations
    ("bellingcat", "https://www.bellingcat.com/feed/"),
    # Cybersecurity
    ("krebs_security", "https://krebsonsecurity.com/feed/"),
    ("cisa_alerts", "https://www.cisa.gov/cybersecurity-advisories/all.xml"),
    # Humanitarian / crisis
    ("reliefweb", "https://reliefweb.int/updates/rss.xml"),
    # Regulatory / policy
    ("fed_register", "https://www.federalregister.gov/documents/search.rss?conditions%5Btype%5D=RULE"),
    # Peace / conflict indices
    ("iep", "https://www.economicsandpeace.org/feed/"),
]

# ---------------------------------------------------------------------------
# Source: Central Bank & Financial Institution Feeds.TIER 1 (official)
# ---------------------------------------------------------------------------

OFFICIAL_FEEDS = [
    ("fed_reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("ecb", "https://www.ecb.europa.eu/rss/press.html"),
    ("boe", "https://www.bankofengland.co.uk/rss/publications"),
    ("bis", "https://www.bis.org/doclist/cbspeeches.rss"),
    ("un_news", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
]

def _parse_rss_feed(url: str, name: str, tier: str, max_items: int = 15) -> List[Dict]:
    r = safe_get(url)
    if r is None:
        return []
    results = []
    try:
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//atom:entry", ns)
        for item in items[:max_items]:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            if pub_el is None:
                pub_el = item.find("updated")
            if pub_el is None:
                ns2 = {"atom": "http://www.w3.org/2005/Atom"}
                pub_el = item.find("atom:updated", ns2)
            if title_el is None:
                ns2 = {"atom": "http://www.w3.org/2005/Atom"}
                title_el = item.find("atom:title", ns2)
            if link_el is None:
                ns2 = {"atom": "http://www.w3.org/2005/Atom"}
                link_el = item.find("atom:link", ns2)
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            link_text = ""
            if link_el is not None:
                link_text = link_el.text.strip() if link_el.text else link_el.get("href", "")
            pub_date = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
            if title:
                results.append({
                    "source": f"rss_{name}",
                    "title": title[:200],
                    "url": link_text,
                    "date": pub_date,
                    "tier": tier,
                })
    except ET.ParseError:
        pass
    return results


def scan_rss() -> List[Dict]:
    results = []
    for name, url in NEWS_FEEDS:
        results.extend(_parse_rss_feed(url, name, "news", max_items=10))
        time.sleep(1)
    return results


def scan_think_tanks() -> List[Dict]:
    results = []
    for name, url in ANALYSIS_FEEDS:
        results.extend(_parse_rss_feed(url, name, "analysis", max_items=10))
        time.sleep(1)
    return results


def scan_official_feeds() -> List[Dict]:
    results = []
    for name, url in OFFICIAL_FEEDS:
        results.extend(_parse_rss_feed(url, name, "official", max_items=10))
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: GovInfo (US Federal Register)
# ---------------------------------------------------------------------------

def scan_govinfo() -> List[Dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
    r = safe_get(f"https://api.govinfo.gov/collections/FR/{since}?offset=0&pageSize=20&api_key=DEMO_KEY")
    if r is None:
        return []
    results = []
    try:
        data = r.json()
        for pkg in data.get("packages", [])[:15]:
            results.append({
                "source": "govinfo",
                "title": pkg.get("title", "")[:200],
                "date": pkg.get("dateIssued", ""),
                "package_id": pkg.get("packageId", ""),
                "url": pkg.get("packageLink", ""),
            })
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: Congress.gov (US bills, votes, legislative activity)
# ---------------------------------------------------------------------------

def scan_congress() -> List[Dict]:
    results = []

    # 1. Recent bills (sorted by update date)
    r = safe_get("https://api.congress.gov/v3/bill?limit=15&sort=updateDate+desc&api_key=DEMO_KEY")
    if r is not None:
        try:
            data = r.json()
            for bill in data.get("bills", [])[:15]:
                latest_action = bill.get("latestAction", {})
                results.append({
                    "source": "congress",
                    "title": bill.get("title", "")[:200],
                    "date": latest_action.get("actionDate", bill.get("updateDate", "")),
                    "bill_number": f'{bill.get("type", "")}{bill.get("number", "")}',
                    "congress": bill.get("congress", ""),
                    "url": bill.get("url", ""),
                    "action": (latest_action.get("text") or "")[:200],
                })
        except (json.JSONDecodeError, ValueError):
            pass

    time.sleep(1)

    # 2. Bill summaries (catches legislative context)
    r2 = safe_get("https://api.congress.gov/v3/summaries?limit=10&sort=updateDate+desc&api_key=DEMO_KEY")
    if r2 is not None:
        try:
            data2 = r2.json()
            for summary in data2.get("summaries", [])[:10]:
                bill_info = summary.get("bill", {})
                # Skip if we already captured this bill in the first call
                bill_num = f'{bill_info.get("type", "")}{bill_info.get("number", "")}'
                if any(r.get("bill_number") == bill_num for r in results):
                    continue
                results.append({
                    "source": "congress",
                    "title": summary.get("text", "")[:200],
                    "date": summary.get("updateDate", ""),
                    "bill_number": bill_num,
                    "congress": bill_info.get("congress", ""),
                    "url": summary.get("url", ""),
                    "action": f"Summary: {summary.get('actionDesc', '')}",
                })
        except (json.JSONDecodeError, ValueError):
            pass

    return results

# ---------------------------------------------------------------------------
# Source: CIA CREST (FOIA search)
# ---------------------------------------------------------------------------

def scan_crest() -> List[Dict]:
    queries = ["surveillance", "biological", "nuclear proliferation"]
    results = []
    for q in queries:
        r = safe_get(f"https://www.cia.gov/readingroom/rest/collection/search?q={quote(q)}&p=0&ps=5")
        if r is None:
            time.sleep(1)
            continue
        try:
            data = r.json()
            for doc in data.get("results", [])[:5]:
                results.append({
                    "source": "crest",
                    "title": doc.get("title", "")[:200],
                    "date": doc.get("date", ""),
                    "doc_number": doc.get("doc_number", ""),
                    "url": doc.get("url", ""),
                })
        except (json.JSONDecodeError, ValueError):
            pass
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: Open Exchange Rates (currencies)
# ---------------------------------------------------------------------------

def scan_currencies() -> List[Dict]:
    r = safe_get("https://open.er-api.com/v6/latest/USD")
    if r is None:
        return []
    results = []
    prev_currencies = get_previous_value("currencies", [])
    prev_rates = {c["currency"]: c["rate_per_usd"] for c in prev_currencies if "currency" in c}
    try:
        data = r.json()
        rates = data.get("rates", {})
        watchlist = {
            "RUB": "Russian Ruble", "CNY": "Chinese Yuan", "EUR": "Euro",
            "GBP": "British Pound", "JPY": "Japanese Yen", "INR": "Indian Rupee",
            "BRL": "Brazilian Real", "MXN": "Mexican Peso", "TRY": "Turkish Lira",
            "ZAR": "South African Rand", "ARS": "Argentine Peso", "NGN": "Nigerian Naira",
            "EGP": "Egyptian Pound", "UAH": "Ukrainian Hryvnia", "TWD": "Taiwan Dollar",
            "KRW": "South Korean Won", "SAR": "Saudi Riyal", "IRR": "Iranian Rial",
        }
        for code, name in watchlist.items():
            if code in rates:
                rate = rates[code]
                prev_rate = prev_rates.get(code)
                change_pct = round(((rate - prev_rate) / prev_rate) * 100, 2) if prev_rate else 0.0
                entry = {
                    "source": "currencies",
                    "currency": code,
                    "name": name,
                    "rate_per_usd": rate,
                    "change_pct": change_pct,
                    "date": data.get("time_last_update_utc", datetime.now(timezone.utc).isoformat()),
                }
                if abs(change_pct) > 2.0:
                    entry["shock"] = True
                results.append(entry)
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: Global weather (Open-Meteo for international severe weather)
# ---------------------------------------------------------------------------

def scan_global_weather() -> List[Dict]:
    cities = [
        {"name": "London", "lat": 51.51, "lon": -0.13, "region": "Europe"},
        {"name": "Tokyo", "lat": 35.68, "lon": 139.69, "region": "Asia"},
        {"name": "Mumbai", "lat": 19.08, "lon": 72.88, "region": "Asia"},
        {"name": "Lagos", "lat": 6.45, "lon": 3.40, "region": "Africa"},
        {"name": "Cairo", "lat": 30.04, "lon": 31.24, "region": "Middle East"},
        {"name": "São Paulo", "lat": -23.55, "lon": -46.64, "region": "South America"},
        {"name": "Mexico City", "lat": 19.43, "lon": -99.13, "region": "North America"},
        {"name": "Beijing", "lat": 39.90, "lon": 116.40, "region": "Asia"},
        {"name": "Moscow", "lat": 55.76, "lon": 37.62, "region": "Europe"},
        {"name": "Sydney", "lat": -33.87, "lon": 151.21, "region": "Oceania"},
        {"name": "Nairobi", "lat": -1.29, "lon": 36.82, "region": "Africa"},
        {"name": "Jakarta", "lat": -6.21, "lon": 106.85, "region": "Asia"},
        {"name": "Dubai", "lat": 25.20, "lon": 55.27, "region": "Middle East"},
        {"name": "Kyiv", "lat": 50.45, "lon": 30.52, "region": "Europe"},
        {"name": "Taipei", "lat": 25.03, "lon": 121.57, "region": "Asia"},
    ]
    results = []
    batch_lats = ",".join(str(c["lat"]) for c in cities)
    batch_lons = ",".join(str(c["lon"]) for c in cities)
    r = safe_get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": batch_lats,
            "longitude": batch_lons,
            "current": "temperature_2m,wind_speed_10m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
            "forecast_days": "3",
            "timezone": "auto",
        },
    )
    if r is None:
        return results
    try:
        data = r.json()
        items = data if isinstance(data, list) else [data]
        for i, item in enumerate(items):
            if i >= len(cities):
                break
            city = cities[i]
            current = item.get("current", {})
            daily = item.get("daily", {})
            temp = current.get("temperature_2m")
            wind = current.get("wind_speed_10m")
            code = current.get("weather_code", 0)
            max_temps = daily.get("temperature_2m_max", [])
            max_wind = daily.get("wind_speed_10m_max", [])
            precip = daily.get("precipitation_sum", [])
            extreme = False
            if temp is not None and (temp > 42 or temp < -20):
                extreme = True
            if wind is not None and wind > 80:
                extreme = True
            if precip and any(p > 50 for p in precip if p is not None):
                extreme = True
            results.append({
                "source": "global_weather",
                "city": city["name"],
                "region": city["region"],
                "lat": city["lat"],
                "lon": city["lon"],
                "temp_c": temp,
                "wind_kmh": wind,
                "weather_code": code,
                "forecast_max_temp": max(max_temps) if max_temps else None,
                "forecast_max_wind": max(max_wind) if max_wind else None,
                "forecast_max_precip": max(precip) if precip else None,
                "extreme": extreme,
                "date": datetime.now(timezone.utc).isoformat(),
            })
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: Commodity prices (via Yahoo Finance RSS)
# ---------------------------------------------------------------------------

def scan_commodities() -> List[Dict]:
    symbols = {
        "CL=F": "Crude Oil WTI",
        "GC=F": "Gold",
        "SI=F": "Silver",
        "NG=F": "Natural Gas",
        "HG=F": "Copper",
        "ZW=F": "Wheat",
        "ZC=F": "Corn",
    }
    results = []
    for sym, name in symbols.items():
        r = safe_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d",
                     headers={"Accept": "application/json"})
        if r is None:
            continue
        try:
            data = r.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            meta = result.get("meta", {})
            price = meta.get("regularMarketPrice")
            prev = meta.get("previousClose") or meta.get("chartPreviousClose")
            if price and prev and prev > 0:
                pct = round((price - prev) / prev * 100, 2)
                results.append({
                    "source": "commodities",
                    "symbol": sym,
                    "name": name,
                    "price": price,
                    "previous_close": prev,
                    "change_pct": pct,
                    "currency": meta.get("currency", "USD"),
                    "date": datetime.now(timezone.utc).isoformat(),
                })
        except (json.JSONDecodeError, ValueError, KeyError, IndexError):
            pass
        time.sleep(0.5)
    return results

# ---------------------------------------------------------------------------
# Source: Space Weather (NOAA SWPC.solar flares + geomagnetic storms)
# ---------------------------------------------------------------------------

def scan_space_weather() -> List[Dict]:
    results = []
    r = safe_get("https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json")
    if r:
        try:
            for flare in r.json()[:30]:
                cls = flare.get("max_class", "")
                if cls and cls[0] in ("M", "X"):
                    results.append({
                        "source": "space_weather",
                        "type": "solar_flare",
                        "class": cls,
                        "begin_time": flare.get("begin_time", ""),
                        "peak_time": flare.get("max_time", ""),
                        "end_time": flare.get("end_time", ""),
                    })
        except (json.JSONDecodeError, ValueError):
            pass
    time.sleep(1)
    r2 = safe_get("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json")
    if r2:
        try:
            rows = r2.json()
            for row in rows[-12:]:
                kp = float(row.get("Kp", 0)) if isinstance(row, dict) else 0
                if kp >= 4:
                    ts = row.get("time_tag", "") if isinstance(row, dict) else ""
                    results.append({
                        "source": "space_weather",
                        "type": "geomagnetic",
                        "kp_index": kp,
                        "timestamp": ts,
                        "storm_level": "extreme" if kp >= 8 else "severe" if kp >= 7 else "strong" if kp >= 6 else "moderate" if kp >= 5 else "minor",
                    })
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
    return results

# ---------------------------------------------------------------------------
# Source: CISA Known Exploited Vulnerabilities
# ---------------------------------------------------------------------------

def scan_cisa() -> List[Dict]:
    r = safe_get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
    if r is None:
        return []
    results = []
    try:
        vulns = r.json().get("vulnerabilities", [])
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
        for v in vulns:
            if v.get("dateAdded", "") >= cutoff:
                results.append({
                    "source": "cisa_kev",
                    "cve_id": v.get("cveID", ""),
                    "vendor": v.get("vendorProject", ""),
                    "product": v.get("product", ""),
                    "vulnerability": v.get("vulnerabilityName", ""),
                    "description": v.get("shortDescription", "")[:300],
                    "date_added": v.get("dateAdded", ""),
                    "due_date": v.get("dueDate", ""),
                    "known_ransomware": v.get("knownRansomwareCampaignUse", "Unknown"),
                })
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: Volcanoes (Smithsonian Global Volcanism Program)
# ---------------------------------------------------------------------------

def scan_volcanoes() -> List[Dict]:
    r = safe_get("https://volcano.si.edu/news/WeeklyVolcanoRSS.xml")
    if r is None:
        return []
    results = []
    try:
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:15]:
            title = item.findtext("title", "")
            desc = item.findtext("description", "")[:300]
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            if title:
                results.append({
                    "source": "volcanoes",
                    "title": title[:200],
                    "description": desc,
                    "url": link,
                    "date": pub_date,
                })
    except ET.ParseError:
        pass
    return results

# ---------------------------------------------------------------------------
# Source: Treasury Yields (US yield curve.recession indicator)
# ---------------------------------------------------------------------------

def scan_treasury() -> List[Dict]:
    year = datetime.now(timezone.utc).year
    r = safe_get(
        f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
        f"&field_tdr_date_value={year}&page&_format=csv"
    )
    if r is None:
        return []
    results = []
    try:
        lines = r.text.strip().split("\n")
        if len(lines) < 2:
            return []
        headers = [h.strip().strip('"') for h in lines[0].split(",")]
        for line in lines[-3:]:
            vals = [v.strip().strip('"') for v in line.split(",")]
            if len(vals) < len(headers):
                continue
            row = dict(zip(headers, vals))

            def _f(key):
                try:
                    return float(row.get(key, 0) or 0)
                except (ValueError, TypeError):
                    return 0.0

            y2 = _f("2 Yr")
            y10 = _f("10 Yr")
            results.append({
                "source": "treasury",
                "date": row.get("Date", ""),
                "1_mo": _f("1 Mo"), "3_mo": _f("3 Mo"), "6_mo": _f("6 Mo"),
                "1_yr": _f("1 Yr"), "2_yr": y2, "5_yr": _f("5 Yr"),
                "10_yr": y10, "30_yr": _f("30 Yr"),
                "inverted": y2 > y10 and y2 > 0 and y10 > 0,
            })
    except (ValueError, IndexError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: Active Fires (InciWeb / NIFC wildfire incidents)
# ---------------------------------------------------------------------------

def scan_fires() -> List[Dict]:
    r = safe_get("https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/"
                 "MODIS_C6_1_USA_contiguous_and_Hawaii_24h.csv")
    if r is None:
        return []
    results = []
    try:
        lines = r.text.strip().split("\n")
        if len(lines) < 2:
            return []
        headers = lines[0].split(",")
        high_confidence = []
        for line in lines[1:]:
            vals = line.split(",")
            if len(vals) < len(headers):
                continue
            row = dict(zip(headers, vals))
            conf = int(row.get("confidence", "0") or "0")
            if conf >= 80:
                high_confidence.append(row)
        for row in high_confidence[:30]:
            lat = float(row.get("latitude", 0))
            lon = float(row.get("longitude", 0))
            results.append({
                "source": "fires",
                "title": f"Fire detection ({row.get('brightness', '?')}K, conf {row.get('confidence', '?')}%)",
                "coordinates": [lon, lat],
                "brightness": float(row.get("brightness", 0)),
                "confidence": int(row.get("confidence", 0)),
                "frp": float(row.get("frp", 0)),
                "date": row.get("acq_date", ""),
                "satellite": row.get("satellite", ""),
                "daynight": row.get("daynight", ""),
            })
    except (ValueError, IndexError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: Aviation Weather (International SIGMETs.severe wx for aviation)
# ---------------------------------------------------------------------------

def scan_aviation_wx() -> List[Dict]:
    r = safe_get("https://aviationweather.gov/api/data/isigmet?format=json")
    if r is None:
        return []
    results = []
    try:
        for sig in r.json()[:25]:
            results.append({
                "source": "aviation_wx",
                "hazard": sig.get("hazard", ""),
                "qualifier": sig.get("qualifier", ""),
                "region": sig.get("firName", ""),
                "raw_text": (sig.get("rawSigmet") or "")[:300],
                "valid_from": sig.get("validTimeFrom", ""),
                "valid_to": sig.get("validTimeTo", ""),
            })
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: GDACS (UN Global Disaster Alerting.earthquakes, floods, cyclones, volcanoes, wildfires)
# ---------------------------------------------------------------------------

def scan_gdacs() -> List[Dict]:
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    r = safe_get(
        "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
        f"?eventlist=EQ,TC,FL,VO,DR,WF&alertlevel=Green;Orange;Red&fromDate={week_ago}"
    )
    if r is None:
        return []
    results = []
    try:
        features = r.json().get("features", [])
        for f in features:
            props = f.get("properties", {})
            geo = f.get("geometry", {})
            coords = geo.get("coordinates", [])
            alert = props.get("alertlevel", "")
            results.append({
                "source": "gdacs",
                "event_type": props.get("eventtype", ""),
                "name": props.get("name", ""),
                "alert_level": alert,
                "severity": props.get("severitydata", {}).get("severity", 0),
                "severity_text": props.get("severitydata", {}).get("severitytext", ""),
                "country": props.get("country", ""),
                "coordinates": coords[:2] if len(coords) >= 2 else [],
                "date": props.get("fromdate", ""),
                "population_affected": props.get("population", {}).get("value", 0),
                "url": props.get("url", {}).get("report", ""),
                "is_current": props.get("iscurrent", ""),
            })
    except (json.JSONDecodeError, ValueError, KeyError):
        pass
    orange_red = [r for r in results if r.get("alert_level") in ("Orange", "Red")]
    if orange_red:
        return orange_red + [r for r in results if r.get("alert_level") == "Green"][:20]
    return results[:40]

# ---------------------------------------------------------------------------
# Source: OFAC Sanctions (US Treasury SDN List)
# ---------------------------------------------------------------------------

def scan_sanctions() -> List[Dict]:
    results = []
    r = safe_get("https://www.treasury.gov/ofac/downloads/sdn.xml", timeout=20)
    if r:
        try:
            root = ET.fromstring(r.content)
            ns = {"sdn": "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_ADVANCED.XML"}
            if not ns:
                ns = {}
            entries = root.findall(".//{*}sdnEntry")
            if not entries:
                entries = root.findall(".//sdnEntry")
            recent = []
            for entry in entries[-50:]:
                uid = entry.findtext("{*}uid", entry.findtext("uid", ""))
                name_parts = []
                fn = entry.findtext("{*}firstName", entry.findtext("firstName", ""))
                ln = entry.findtext("{*}lastName", entry.findtext("lastName", ""))
                if fn:
                    name_parts.append(fn)
                if ln:
                    name_parts.append(ln)
                sdn_type = entry.findtext("{*}sdnType", entry.findtext("sdnType", ""))
                programs = []
                for prog in entry.findall(".//{*}program") + entry.findall(".//program"):
                    if prog.text:
                        programs.append(prog.text)
                if name_parts:
                    recent.append({
                        "source": "ofac_sdn",
                        "uid": uid,
                        "name": " ".join(name_parts),
                        "type": sdn_type,
                        "programs": programs[:3],
                    })
            results = recent[-30:]
        except ET.ParseError:
            pass

    r2 = safe_get("https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/"
                   "content?token=dG9rZW4tMjAxNw", timeout=20)
    if r2:
        try:
            root = ET.fromstring(r2.content)
            entities = root.findall(".//{*}entity") or root.findall(".//entity")
            for ent in entities[-20:]:
                name_el = ent.find(".//{*}wholeName") or ent.find(".//wholeName")
                name = name_el.text if name_el is not None and name_el.text else ""
                reg_date = ent.get("regulation_date", "")
                if name:
                    results.append({
                        "source": "eu_sanctions",
                        "name": name[:200],
                        "regulation_date": reg_date,
                    })
        except ET.ParseError:
            pass
    return results

# ---------------------------------------------------------------------------
# Source: World Bank Economic Indicators
# ---------------------------------------------------------------------------

def scan_world_bank() -> List[Dict]:
    indicators = {
        "FP.CPI.TOTL.ZG": "Inflation (CPI %)",
        "NY.GDP.MKTP.KD.ZG": "GDP Growth (%)",
        "SL.UEM.TOTL.ZS": "Unemployment (%)",
        "BN.CAB.XOKA.GD.ZS": "Current Account (% GDP)",
    }
    key_countries = ["USA", "CHN", "DEU", "JPN", "GBR", "IND", "BRA", "RUS"]
    results = []
    for code, label in indicators.items():
        countries = ";".join(key_countries)
        r = safe_get(
            f"https://api.worldbank.org/v2/country/{countries}/indicator/{code}"
            f"?date=2023:2025&format=json&per_page=50"
        )
        if r is None:
            time.sleep(1)
            continue
        try:
            data = r.json()
            if isinstance(data, list) and len(data) > 1:
                for item in data[1] or []:
                    val = item.get("value")
                    if val is not None:
                        results.append({
                            "source": "world_bank",
                            "indicator": label,
                            "indicator_code": code,
                            "country": item.get("country", {}).get("value", ""),
                            "country_code": item.get("countryiso3code", ""),
                            "year": item.get("date", ""),
                            "value": round(val, 2),
                        })
        except (json.JSONDecodeError, ValueError):
            pass
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: SEC EDGAR (Corporate filings, insider trades, material events)
# ---------------------------------------------------------------------------

def scan_sec_edgar() -> List[Dict]:
    results = []
    # Use EDGAR RSS for recent filings (most reliable)
    r3 = safe_get("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=20&search_text=&output=atom")
    if r3:
        try:
            root = ET.fromstring(r3.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:15]:
                title = entry.findtext("atom:title", "", ns)
                updated = entry.findtext("atom:updated", "", ns)
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                summary = entry.findtext("atom:summary", "", ns)[:300]
                if title:
                    filing_type = "8-K"
                    if "10-K" in title:
                        filing_type = "10-K"
                    elif "10-Q" in title:
                        filing_type = "10-Q"
                    elif "4" in title and "insider" in title.lower():
                        filing_type = "Form 4 (Insider Trade)"
                    results.append({
                        "source": "sec_edgar",
                        "title": title[:200],
                        "filing_type": filing_type,
                        "date": updated,
                        "url": link,
                        "summary": summary,
                    })
        except ET.ParseError:
            pass
    # Insider trading (Form 4) via RSS
    time.sleep(1)
    r4 = safe_get("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=include&count=15&search_text=&output=atom")
    if r4:
        try:
            root = ET.fromstring(r4.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:10]:
                title = entry.findtext("atom:title", "", ns)
                updated = entry.findtext("atom:updated", "", ns)
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                if title:
                    results.append({
                        "source": "sec_edgar",
                        "title": title[:200],
                        "filing_type": "Form 4 (Insider Trade)",
                        "date": updated,
                        "url": link,
                    })
        except ET.ParseError:
            pass
    return results

# ---------------------------------------------------------------------------
# Source: FEMA Disaster Declarations (service business demand signals)
# ---------------------------------------------------------------------------

def scan_fema() -> List[Dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000Z")
    r = safe_get(f"https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?"
                 f"$filter=declarationDate gt '{since}'&$top=25&$orderby=declarationDate desc")
    if r is None:
        return []
    results = []
    try:
        data = r.json()
        for dec in data.get("DisasterDeclarationsSummaries", [])[:20]:
            state = dec.get("state", "")
            results.append({
                "source": "fema",
                "title": dec.get("declarationTitle", ""),
                "type": dec.get("incidentType", ""),
                "state": state,
                "county": dec.get("designatedArea", ""),
                "date": dec.get("declarationDate", ""),
                "fema_id": dec.get("disasterNumber", ""),
                "in_boss_territory": state in ("TX", "MS", "AR", "AL", "TN", "OK", "NM"),
            })
    except (json.JSONDecodeError, ValueError):
        pass
    return results

# ---------------------------------------------------------------------------
# Source: BLS Employment (industry labor market intelligence)
# ---------------------------------------------------------------------------

def scan_bls() -> List[Dict]:
    results = []
    series_ids = [
        ("CES0000000001", "Total Nonfarm Employment"),
        ("LNS14000000", "Unemployment Rate"),
        ("CUUR0000SA0", "CPI All Items"),
    ]
    payload = {
        "seriesid": [s[0] for s in series_ids],
        "startyear": str(datetime.now(timezone.utc).year - 1),
        "endyear": str(datetime.now(timezone.utc).year),
    }
    try:
        r = _session.post("https://api.bls.gov/publicAPI/v2/timeseries/data/",
                          json=payload, timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            label_map = {s[0]: s[1] for s in series_ids}
            for series in data.get("Results", {}).get("series", []):
                sid = series.get("seriesID", "")
                for dp in series.get("data", [])[:3]:
                    results.append({
                        "source": "bls",
                        "series_id": sid,
                        "indicator": label_map.get(sid, sid),
                        "year": dp.get("year", ""),
                        "period": dp.get("periodName", ""),
                        "value": dp.get("value", ""),
                    })
    except requests.RequestException as e:
        log.warning("BLS request failed: %s", e)
    return results

# ---------------------------------------------------------------------------
# Source: EIA Energy Data (oil, gas, electricity.deeper than Yahoo Finance)
# ---------------------------------------------------------------------------

def scan_eia() -> List[Dict]:
    results = []
    eia_key = os.environ.get("EIA_API_KEY", "")
    if not eia_key:
        log.info("  eia: no API key, skipping")
        return []
    series_list = [
        ("PET.RWTC.D", "WTI Crude Oil (daily)"),
        ("NG.RNGWHHD.D", "Natural Gas Henry Hub (daily)"),
        ("PET.WCESTUS1.W", "US Crude Oil Inventories (weekly)"),
        ("ELEC.GEN.ALL-US-99.M", "US Electricity Generation (monthly)"),
    ]
    for series_id, label in series_list:
        url = f"https://api.eia.gov/v2/seriesid/{series_id}?api_key={eia_key}"
        r = safe_get(url)
        if r:
            try:
                data = r.json()
                for dp in data.get("response", {}).get("data", [])[:3]:
                    results.append({
                        "source": "eia",
                        "series": series_id,
                        "label": label,
                        "period": dp.get("period", ""),
                        "value": dp.get("value"),
                    })
            except (json.JSONDecodeError, ValueError):
                pass
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: Finnhub (economic calendar, earnings, IPOs)
# ---------------------------------------------------------------------------

def scan_finnhub() -> List[Dict]:
    key = os.environ.get("FINNHUB_API_KEY", "")
    if not key:
        log.info("  finnhub: no API key, skipping")
        return []
    results = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_out = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    # Economic calendar
    r = safe_get(f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={week_out}&token={key}")
    if r:
        try:
            for ev in r.json().get("economicCalendar", [])[:15]:
                results.append({
                    "source": "finnhub",
                    "type": "economic_calendar",
                    "event": ev.get("event", ""),
                    "country": ev.get("country", ""),
                    "date": ev.get("time", ""),
                    "impact": ev.get("impact", ""),
                    "estimate": ev.get("estimate"),
                    "actual": ev.get("actual"),
                    "previous": ev.get("prev"),
                })
        except (json.JSONDecodeError, ValueError):
            pass
    time.sleep(1)
    # IPO calendar
    r2 = safe_get(f"https://finnhub.io/api/v1/calendar/ipo?from={today}&to={week_out}&token={key}")
    if r2:
        try:
            for ipo in r2.json().get("ipoCalendar", [])[:10]:
                results.append({
                    "source": "finnhub",
                    "type": "ipo",
                    "name": ipo.get("name", ""),
                    "symbol": ipo.get("symbol", ""),
                    "date": ipo.get("date", ""),
                    "price_range": f"${ipo.get('priceRangeLow', '?')}-${ipo.get('priceRangeHigh', '?')}",
                    "shares": ipo.get("numberOfShares"),
                })
        except (json.JSONDecodeError, ValueError):
            pass
    return results

# ---------------------------------------------------------------------------
# Source: US Patent Office (competitive/tech intelligence)
# ---------------------------------------------------------------------------

def scan_patents() -> List[Dict]:
    results = []
    queries = ["artificial+intelligence+voice", "business+automation+AI"]
    for q in queries:
        r = safe_get(f"https://developer.uspto.gov/ibd-api/v1/application/publications?searchText={q}&start=0&rows=10")
        if r:
            try:
                data = r.json()
                for doc in data.get("results", [])[:5]:
                    results.append({
                        "source": "patents",
                        "title": doc.get("inventionTitle", "")[:200],
                        "applicant": doc.get("applicantName", ""),
                        "date": doc.get("datePublished", ""),
                        "patent_number": doc.get("patentApplicationNumber", ""),
                    })
            except (json.JSONDecodeError, ValueError):
                pass
        time.sleep(1)
    return results

# ---------------------------------------------------------------------------
# Source: Alpha Vantage (stocks, forex, crypto.free tier)
# ---------------------------------------------------------------------------

def scan_alpha_vantage() -> List[Dict]:
    key = os.environ.get("ALPHA_VANTAGE_KEY", "")
    if not key:
        log.info("  alpha_vantage: no API key, skipping")
        return []
    results = []
    # Top gainers/losers.market sentiment
    r = safe_get(f"https://www.alphavantage.co/query?function=TOP_GAINERS_LOSERS&apikey={key}")
    if r:
        try:
            data = r.json()
            for item in data.get("top_gainers", [])[:5]:
                results.append({
                    "source": "alpha_vantage",
                    "type": "top_gainer",
                    "ticker": item.get("ticker", ""),
                    "price": item.get("price", ""),
                    "change_pct": item.get("change_percentage", ""),
                    "volume": item.get("volume", ""),
                })
            for item in data.get("top_losers", [])[:5]:
                results.append({
                    "source": "alpha_vantage",
                    "type": "top_loser",
                    "ticker": item.get("ticker", ""),
                    "price": item.get("price", ""),
                    "change_pct": item.get("change_percentage", ""),
                    "volume": item.get("volume", ""),
                })
            for item in data.get("most_actively_traded", [])[:5]:
                results.append({
                    "source": "alpha_vantage",
                    "type": "most_active",
                    "ticker": item.get("ticker", ""),
                    "price": item.get("price", ""),
                    "change_pct": item.get("change_percentage", ""),
                    "volume": item.get("volume", ""),
                })
        except (json.JSONDecodeError, ValueError):
            pass
    time.sleep(1)
    # Market news sentiment
    r2 = safe_get(f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&topics=technology,economy_macro&apikey={key}")
    if r2:
        try:
            data2 = r2.json()
            for item in data2.get("feed", [])[:10]:
                results.append({
                    "source": "alpha_vantage",
                    "type": "news_sentiment",
                    "title": item.get("title", "")[:200],
                    "url": item.get("url", ""),
                    "sentiment": item.get("overall_sentiment_label", ""),
                    "sentiment_score": item.get("overall_sentiment_score"),
                    "date": item.get("time_published", ""),
                })
        except (json.JSONDecodeError, ValueError):
            pass
    return results

# ---------------------------------------------------------------------------
# Source: Telegram OSINT Channels.TIER 0 (fastest breaking news, 5-30min ahead of MSM)
# ---------------------------------------------------------------------------

TELEGRAM_CHANNELS = [
    ("osintdefender", "Global OSINT, verified visuals"),
    ("ClashReport", "Battlefield footage worldwide"),
    ("intelslava", "Ukraine/Russia ground updates"),
    ("middleeastobserver", "Israel-Gaza, Syria, Lebanon, Iran"),
    ("BellumActaNews", "Global military developments"),
    ("war_monitor", "Multi-theater conflict"),
]

def scan_telegram() -> List[Dict]:
    results = []
    for channel, description in TELEGRAM_CHANNELS:
        url = f"https://t.me/s/{channel}"
        try:
            r = _session.get(url, timeout=10, headers={"User-Agent": USER_AGENT})
            if r.status_code != 200:
                continue
            text = r.text
            messages = text.split('tgme_widget_message_wrap')
            for msg_block in messages[-15:]:
                text_start = msg_block.find('tgme_widget_message_text')
                if text_start == -1:
                    continue
                inner_start = msg_block.find('>', text_start) + 1
                inner_end = msg_block.find('</div>', inner_start)
                if inner_start <= 0 or inner_end == -1:
                    continue
                raw = msg_block[inner_start:inner_end]
                import re
                clean = re.sub(r'<[^>]+>', ' ', raw).strip()
                clean = clean[:500]
                if len(clean) < 20:
                    continue
                time_match = re.search(r'datetime="([^"]+)"', msg_block)
                timestamp = time_match.group(1) if time_match else ""
                results.append({
                    "source": "telegram",
                    "channel": channel,
                    "channel_desc": description,
                    "text": clean,
                    "date": timestamp,
                    "title": clean[:150],
                })
        except Exception:
            continue
        time.sleep(0.5)
    return results

# ---------------------------------------------------------------------------
# Source: Financial Futures.TIER 0 (oil/gold/VIX spike = geopolitical event, 15-60min ahead)
# ---------------------------------------------------------------------------

def scan_futures() -> List[Dict]:
    try:
        import yfinance as yf
    except ImportError:
        log.warning("yfinance not installed.pip install yfinance")
        return []
    tickers = {
        "CL=F": ("Crude Oil", "oil"),
        "GC=F": ("Gold", "gold"),
        "^VIX": ("VIX", "volatility"),
        "NG=F": ("Natural Gas", "natgas"),
        "^TNX": ("10Y Treasury", "bonds"),
        "SI=F": ("Silver", "silver"),
    }
    results = []
    for symbol, (name, category) in tickers.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d", interval="1d")
            if len(hist) < 2:
                continue
            current = float(hist["Close"].iloc[-1])
            previous = float(hist["Close"].iloc[-2])
            change_pct = round(((current - previous) / previous) * 100, 2)
            results.append({
                "source": "futures",
                "name": name,
                "symbol": symbol,
                "category": category,
                "price": round(current, 2),
                "change_pct": change_pct,
                "previous": round(previous, 2),
                "spike": abs(change_pct) >= 2.0,
            })
        except Exception:
            continue
    return results

# ---------------------------------------------------------------------------
# Source: NASA FIRMS.fire/explosion detection from satellite (leading indicator for airstrikes)
# ---------------------------------------------------------------------------

FIRMS_MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "")
CONFLICT_ZONES = [
    ("Middle East", 12, 30, 42, 65),
    ("Ukraine", 44, 22, 52, 40),
    ("East Africa", -5, 25, 15, 52),
    ("Taiwan Strait", 20, 115, 28, 126),
]

def scan_firms() -> List[Dict]:
    if not FIRMS_MAP_KEY:
        return []
    results = []
    for region, south, west, north, east in CONFLICT_ZONES:
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/MODIS_NRT/{west},{south},{east},{north}/2"
        try:
            r = _session.get(url, timeout=15)
            if r.status_code != 200:
                continue
            lines = r.text.strip().split("\n")
            if len(lines) <= 1:
                continue
            headers = lines[0].split(",")
            def col_idx(name):
                return headers.index(name) if name in headers else -1
            lat_i = col_idx("latitude")
            lon_i = col_idx("longitude")
            bright_i = col_idx("bright_ti4") if "bright_ti4" in headers else col_idx("brightness")
            conf_i = col_idx("confidence")
            date_i = col_idx("acq_date")
            time_i = col_idx("acq_time")
            high_confidence = []
            for line in lines[1:]:
                cols = line.split(",")
                if lat_i < 0 or lon_i < 0 or len(cols) <= max(lat_i, lon_i):
                    continue
                conf_val = cols[conf_i].strip() if conf_i >= 0 and conf_i < len(cols) else ""
                try:
                    conf_num = int(conf_val)
                    if conf_num < 50:
                        continue
                except ValueError:
                    if conf_val.lower() not in ("high", "h", "nominal", "n"):
                        continue
                brightness = float(cols[bright_i]) if bright_i >= 0 and bright_i < len(cols) else 0
                high_confidence.append({
                    "lat": float(cols[lat_i]),
                    "lon": float(cols[lon_i]),
                    "brightness": brightness,
                    "confidence": conf_val,
                    "date": cols[date_i] if date_i >= 0 else "",
                    "time": cols[time_i] if time_i >= 0 else "",
                })
            if high_confidence:
                results.append({
                    "source": "firms",
                    "region": region,
                    "hotspot_count": len(high_confidence),
                    "max_brightness": max(h["brightness"] for h in high_confidence),
                    "hotspots": high_confidence[:20],
                    "title": f"{len(high_confidence)} fire/heat detections in {region}",
                })
        except Exception:
            continue
        time.sleep(0.5)
    return results

# ---------------------------------------------------------------------------
# Intelligence Synthesis.ATLAS Assessments
# ---------------------------------------------------------------------------

ASSESSMENT_CATEGORIES = ["geopolitical", "economic", "environmental", "technology", "security", "market_opportunity"]


def _build_situation_picture(data: dict, anomalies: list) -> dict:
    """Stage 1: Fuse all sources into a single situation picture before writing any assessment."""
    weather = data.get("noaa", [])
    gdelt = data.get("gdelt", [])
    adsb = data.get("adsb", [])
    quakes = data.get("usgs", [])
    commodities = data.get("commodities", [])
    currencies = data.get("currencies", [])
    fred = data.get("fred", [])
    reddit = data.get("reddit", [])
    rss = data.get("rss", [])
    think_tanks = data.get("think_tanks", [])
    official = data.get("official_feeds", [])
    hn = data.get("hackernews", [])
    poly = data.get("polymarket", [])
    global_wx = data.get("global_weather", [])
    world_bank = data.get("world_bank", [])
    sanctions = data.get("sanctions", [])

    conflict_news = [g for g in gdelt if g.get("category") == "conflict"]
    disaster_news = [g for g in gdelt if g.get("category") == "disaster"]
    econ_news = [g for g in gdelt if g.get("category") == "economy"]

    severe_wx = [w for w in weather if w.get("severity") in ("Extreme", "Severe")]
    heat_alerts = [w for w in weather if "heat" in (w.get("event", "") or "").lower() or "excessive" in (w.get("event", "") or "").lower()]
    storm_alerts = [w for w in weather if any(k in (w.get("event", "") or "").lower() for k in ["tornado", "hurricane", "thunderstorm", "flood"])]
    major_quakes = [q for q in quakes if q.get("magnitude", 0) >= 5.0]

    oil = next((c for c in commodities if c.get("symbol") == "CL=F"), None)
    gas = next((c for c in commodities if c.get("symbol") == "NG=F"), None)
    gold = next((c for c in commodities if c.get("symbol") == "GC=F"), None)
    fred_shocks = [f for f in fred if f.get("shock")]

    # Military aircraft: group by region
    mil_regions = {}
    tankers = []
    recon = []
    for ac in adsb:
        lat, lon = ac.get("lat", 0), ac.get("lon", 0)
        key = (round(lat / 10) * 10, round(lon / 10) * 10)
        mil_regions.setdefault(key, []).append(ac)
        t = (ac.get("type") or "").lower()
        if "kc-" in t or "tanker" in (ac.get("description") or "").lower():
            tankers.append(ac)
        if any(k in t for k in ["rc-135", "e-3", "e-8", "p-8", "ep-3", "rq-4"]):
            recon.append(ac)

    # Conflict countries
    conflict_countries = {}
    for a in conflict_news:
        c = a.get("country", "")
        if c:
            conflict_countries[c] = conflict_countries.get(c, 0) + 1

    # Prediction market signals by topic
    poly_conflict = [p for p in poly if any(k in (p.get("question") or "").lower()
                     for k in ["war", "invasion", "ceasefire", "military", "attack",
                               "iran", "ukraine", "russia", "china", "taiwan", "israel", "gaza"])]
    poly_econ = [p for p in poly if any(k in (p.get("question") or "").lower()
                 for k in ["recession", "inflation", "fed", "rate", "gdp", "tariff", "economy"])]

    # Reddit intelligence
    pain_keywords = ["missed call", "voicemail", "no answer", "can't reach",
                     "never picks up", "lost customer", "lost a customer",
                     "lost the job", "went to competitor", "answering service"]
    pain_subs = {"hvac", "plumbing", "electricians", "roofing", "lawncare",
                 "autorepair", "contractors", "smallbusiness", "sweatystartup",
                 "entrepreneur", "landscaping"}
    pain_posts = []
    for p in reddit:
        title = (p.get("title") or "").lower()
        sub = (p.get("subreddit") or "").replace("r/", "").lower()
        if any(k in title for k in pain_keywords) and (sub in pain_subs or "business" in sub or "contractor" in sub):
            pain_posts.append(p)

    ai_signals = []
    for item in hn + rss + think_tanks:
        title = (item.get("title") or "").lower()
        if any(k in title for k in ["ai ", "artificial intelligence", "chatgpt", "claude", "gpt", "llm", "automation"]):
            ai_signals.append(item)

    # Think tank conflict/security analysis (tier 1 intelligence)
    conflict_keywords = ["war", "conflict", "military", "attack", "missile", "nuclear",
                         "ceasefire", "invasion", "troops", "nato", "weapons", "sanctions"]
    econ_keywords = ["inflation", "recession", "gdp", "trade", "tariff", "debt",
                     "interest rate", "monetary", "fiscal", "economy", "bank"]
    tt_conflict = [t for t in think_tanks if any(k in (t.get("title") or "").lower() for k in conflict_keywords)]
    tt_econ = [t for t in think_tanks if any(k in (t.get("title") or "").lower() for k in econ_keywords)]
    tt_cyber = [t for t in think_tanks if any(k in (t.get("title") or "").lower()
                for k in ["cyber", "hack", "ransomware", "vulnerability", "malware"])]

    # Official source signals
    cb_signals = [o for o in official if any(k in (o.get("title") or "").lower()
                  for k in ["rate", "inflation", "monetary", "financial stability", "statement"])]

    # World Bank indicators
    wb_inflation = [w for w in world_bank if w.get("indicator_code") == "FP.CPI.TOTL.ZG"]
    wb_gdp = [w for w in world_bank if w.get("indicator_code") == "NY.GDP.MKTP.KD.ZG"]

    # Sanctions
    ofac_entries = [s for s in sanctions if s.get("source") == "ofac_sdn"]
    eu_entries = [s for s in sanctions if s.get("source") == "eu_sanctions"]

    # New sources
    sec_edgar = data.get("sec_edgar", [])
    insider_trades = [s for s in sec_edgar if s.get("filing_type") == "Form 4 (Insider Trade)"]
    material_events = [s for s in sec_edgar if s.get("filing_type") == "8-K"]
    fema = data.get("fema", [])
    fema_boss_territory = [f for f in fema if f.get("in_boss_territory")]
    bls = data.get("bls", [])
    eia = data.get("eia", [])
    finnhub = data.get("finnhub", [])
    econ_calendar = [f for f in finnhub if f.get("type") == "economic_calendar"]
    alpha_vantage = data.get("alpha_vantage", [])
    av_sentiment = [a for a in alpha_vantage if a.get("type") == "news_sentiment"]
    av_bearish = [a for a in av_sentiment if a.get("sentiment") == "Bearish"]
    av_bullish = [a for a in av_sentiment if a.get("sentiment") == "Bullish"]
    currency_shocks = [c for c in currencies if c.get("shock")]

    # Trend detection: compare with previous scan
    prev = load_previous_report()
    prev_commodities = {c.get("symbol"): c for c in prev.get("commodities", []) if "symbol" in c}
    trend_signals = []
    for c in commodities:
        sym = c.get("symbol", "")
        prev_c = prev_commodities.get(sym)
        if prev_c and c.get("change_pct") and prev_c.get("change_pct"):
            if abs(c["change_pct"]) > abs(prev_c["change_pct"]) * 1.5 and abs(c["change_pct"]) > 2:
                trend_signals.append({"type": "accelerating", "symbol": sym,
                    "current_change": c["change_pct"], "prev_change": prev_c["change_pct"]})

    # Trader intelligence feedback.read what the paper trader discovered
    # Check both previous report AND outgoing latest.json (trader writes to latest)
    trader_intel = prev.get("trader_intel", {})
    if not trader_intel and REPORT_PATH.exists():
        try:
            outgoing = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            trader_intel = outgoing.get("trader_intel", {})
        except (json.JSONDecodeError, OSError):
            pass
    trader_hotspots = trader_intel.get("geopolitical_hotspots", [])
    trader_info_gaps = trader_intel.get("information_gaps", [])
    trader_sentiment = trader_intel.get("sentiment_map", {})
    trader_consensus = trader_intel.get("market_consensus", [])
    trader_edges = trader_intel.get("topics_with_edge", {})
    trader_countries = trader_intel.get("countries_active", {})
    trader_divergences = trader_intel.get("cross_platform_divergences", [])

    # Missing sources
    missing = [s for s in ["gdelt", "adsb", "metaculus", "acled", "ioda", "fred", "safecast",
                           "think_tanks", "official_feeds", "gdacs",
                           "sec_edgar", "fema", "bls", "eia"]
               if not data.get(s)]

    space_wx = data.get("space_weather", [])
    solar_flares = [s for s in space_wx if s.get("type") == "solar_flare"]
    geo_storms = [s for s in space_wx if s.get("type") == "geomagnetic" and s.get("kp_index", 0) >= 5]
    cisa_kev = data.get("cisa", [])
    ransomware_vulns = [v for v in cisa_kev if v.get("known_ransomware") == "Known"]
    treasury = data.get("treasury", [])
    yield_inverted = any(t.get("inverted") for t in treasury)
    fires = data.get("fires", [])
    volcanoes = data.get("volcanoes", [])
    aviation_wx = data.get("aviation_wx", [])

    gdacs = data.get("gdacs", [])
    gdacs_orange_red = [g for g in gdacs if g.get("alert_level") in ("Orange", "Red")]
    gdacs_quakes = [g for g in gdacs if g.get("event_type") == "EQ"]
    gdacs_cyclones = [g for g in gdacs if g.get("event_type") == "TC"]
    gdacs_floods = [g for g in gdacs if g.get("event_type") == "FL"]
    gdacs_droughts = [g for g in gdacs if g.get("event_type") == "DR"]

    return {
        "conflict_news": conflict_news, "disaster_news": disaster_news, "econ_news": econ_news,
        "conflict_countries": conflict_countries, "adsb": adsb, "mil_regions": mil_regions,
        "tankers": tankers, "recon": recon,
        "severe_wx": severe_wx, "heat_alerts": heat_alerts, "storm_alerts": storm_alerts,
        "major_quakes": major_quakes, "extreme_global": [w for w in global_wx if w.get("extreme")],
        "oil": oil, "gas": gas, "gold": gold, "fred_shocks": fred_shocks,
        "poly_conflict": poly_conflict, "poly_econ": poly_econ, "poly": poly,
        "currencies": currencies, "commodities": commodities,
        "pain_posts": pain_posts, "ai_signals": ai_signals,
        "reddit": reddit, "rss": rss, "hn": hn,
        "anomalies": anomalies, "missing": missing,
        "solar_flares": solar_flares, "geo_storms": geo_storms,
        "cisa_kev": cisa_kev, "ransomware_vulns": ransomware_vulns,
        "treasury": treasury, "yield_inverted": yield_inverted,
        "fires": fires, "volcanoes": volcanoes, "aviation_wx": aviation_wx,
        "think_tanks": think_tanks, "tt_conflict": tt_conflict,
        "tt_econ": tt_econ, "tt_cyber": tt_cyber,
        "official": official, "cb_signals": cb_signals,
        "world_bank": world_bank, "wb_inflation": wb_inflation, "wb_gdp": wb_gdp,
        "sanctions": sanctions, "ofac_entries": ofac_entries, "eu_entries": eu_entries,
        "gdacs": gdacs, "gdacs_orange_red": gdacs_orange_red,
        "gdacs_quakes": gdacs_quakes, "gdacs_cyclones": gdacs_cyclones,
        "gdacs_floods": gdacs_floods, "gdacs_droughts": gdacs_droughts,
        "sec_edgar": sec_edgar, "insider_trades": insider_trades,
        "material_events": material_events,
        "fema": fema, "fema_boss_territory": fema_boss_territory,
        "bls": bls, "eia": eia, "finnhub": finnhub,
        "econ_calendar": econ_calendar,
        "alpha_vantage": alpha_vantage, "av_sentiment": av_sentiment,
        "av_bearish": av_bearish, "av_bullish": av_bullish,
        "currency_shocks": currency_shocks, "trend_signals": trend_signals,
        "trader_intel": trader_intel, "trader_hotspots": trader_hotspots,
        "trader_info_gaps": trader_info_gaps, "trader_sentiment": trader_sentiment,
        "trader_consensus": trader_consensus, "trader_edges": trader_edges,
        "trader_countries": trader_countries, "trader_divergences": trader_divergences,
    }


def generate_assessments(data: dict, anomalies: list, claims: list) -> List[Dict]:
    """Synthesize multi-source intelligence into fused assessments.
    Every assessment must cross-reference at least 2 sources, include competing
    hypotheses, and specify what to watch for to disambiguate."""
    assessments = []
    sp = _build_situation_picture(data, anomalies)
    now_iso = datetime.now(timezone.utc).isoformat()

    # =====================================================================
    # FUSED ASSESSMENT 1: Military posture + conflict signals + markets
    # =====================================================================
    mil_count = len(sp["adsb"])
    conflict_count = len(sp["conflict_news"])
    has_tankers = len(sp["tankers"])
    has_recon = len(sp["recon"])

    if mil_count >= 10 or conflict_count >= 5:
        # Cross-reference: do the markets agree?
        market_consensus = ""
        if sp["poly_conflict"]:
            high_prob = [p for p in sp["poly_conflict"] if p.get("probability", 50) > 70]
            low_prob = [p for p in sp["poly_conflict"] if p.get("probability", 50) < 30]
            if high_prob:
                market_consensus = f"Markets pricing in escalation: {high_prob[0].get('question','')[:60]} at {high_prob[0].get('probability')}%."
            elif low_prob:
                market_consensus = f"Markets discounting escalation: {low_prob[0].get('question','')[:60]} at {low_prob[0].get('probability')}%."

        # Cross-reference: anomaly engine findings
        mil_anomalies = [a for a in sp["anomalies"] if a.get("pattern") == "mil_air_no_news"]

        # Which regions have aircraft but no news?
        silent_regions = []
        for (glat, glon), aircraft in sp["mil_regions"].items():
            if len(aircraft) >= 5:
                region_news = len([g for g in sp["conflict_news"]
                                   if abs(g.get("lat", 999) - glat) < 15 and abs(g.get("lon", 999) - glon) < 15])
                if region_news < 2:
                    silent_regions.append((glat, glon, len(aircraft)))

        # Cross-reference: oil moves (military activity near oil = supply risk)
        oil_signal = ""
        if sp["oil"] and abs(sp["oil"].get("change_pct", 0)) > 2:
            pct = sp["oil"]["change_pct"]
            oil_signal = f"Oil {'surging' if pct > 0 else 'dropping'} {abs(pct):.1f}%."
            if pct < -3 and mil_count > 20:
                oil_signal += "price drop despite elevated military activity suggests market sees exercise/deterrence, not combat."
            elif pct > 3 and conflict_count > 10:
                oil_signal += "price spike corroborates supply disruption risk from conflict zone activity."
            else:
                oil_signal += "no clear correlation with military posture."

        # Cross-reference: weather (bad weather = training probably cancelled)
        wx_conflict = ""
        if sp["severe_wx"]:
            wx_states = set(w.get("state", "") for w in sp["severe_wx"])
            wx_conflict = f"Note: {len(sp['severe_wx'])} severe weather alerts active. If military activity persists through bad wx, less likely to be routine training."

        # Build hypotheses
        hypotheses = []
        if silent_regions:
            hypotheses.append(f"HYPOTHESIS A (covert positioning): {len(silent_regions)} regions show military aircraft with zero corresponding news.unusual unless activity is deliberate and unpublicized")
        if has_tankers:
            hypotheses.append(f"HYPOTHESIS B (extended operations): {has_tankers} aerial refueling tankers airborne indicates forces preparing for sustained operations, not short exercises")
        if has_recon:
            hypotheses.append(f"HYPOTHESIS C (intelligence gathering): {has_recon} ISR/recon platforms active.collecting against specific targets")
        if conflict_count < 3 and mil_count > 30:
            hypotheses.append("HYPOTHESIS D (exercise): High aircraft count with low conflict news = routine military exercise, not crisis")
        elif conflict_count > 10 and mil_count < 10:
            hypotheses.append("HYPOTHESIS D (diplomatic crisis): News reporting conflict but military not visibly mobilized = diplomatic phase, not kinetic")

        watch_for = ["Change in tanker-to-fighter ratio (more tankers = shifting from training to ops)",
                     "ISR platforms shifting to new regions = new collection target",
                     "Prediction markets moving >10 points in 24hrs on conflict questions"]
        if silent_regions:
            watch_for.append(f"News coverage appearing for regions ({', '.join(f'{lat},{lon}' for lat, lon, _ in silent_regions[:3])}).would confirm something newsworthy is happening there")

        analysis_parts = [f"{mil_count} military aircraft tracked across {len(sp['mil_regions'])} regions."]
        if conflict_count:
            top_countries = sorted(sp["conflict_countries"].items(), key=lambda x: x[1], reverse=True)[:3]
            analysis_parts.append(f"GDELT: {conflict_count} conflict articles.hotspots: {', '.join(f'{c}({n})' for c, n in top_countries)}.")
        if sp.get("tt_conflict"):
            tt_titles = [t.get("title", "")[:80] for t in sp["tt_conflict"][:3]]
            analysis_parts.append(f"Think tank analysis ({len(sp['tt_conflict'])} items): {'; '.join(tt_titles)}.")
        if silent_regions:
            analysis_parts.append(f"ANOMALY: {len(silent_regions)} regions with concentrated military air and no corresponding news coverage.the silence is the signal.")
        if market_consensus:
            analysis_parts.append(market_consensus)
        if oil_signal:
            analysis_parts.append(oil_signal)
        if wx_conflict:
            analysis_parts.append(wx_conflict)

        confidence = 50
        if silent_regions:
            confidence += 15
        if has_tankers or has_recon:
            confidence += 10
        if conflict_count > 10:
            confidence += 10
        confidence = min(90, confidence)

        assessments.append({
            "category": "security",
            "title": f"Military posture assessment: {mil_count} aircraft, {conflict_count} conflict reports, {len(silent_regions)} dark zones",
            "analysis": " ".join(analysis_parts),
            "hypotheses": hypotheses,
            "watch_for": watch_for,
            "confidence": confidence,
            "sources_used": ["adsb", "gdelt", "polymarket", "commodities", "noaa", "think_tanks"],
            "time_horizon": "24h",
        })

    # =====================================================================
    # FUSED ASSESSMENT 2: Economic convergence/divergence
    # =====================================================================
    oil = sp["oil"]
    gas = sp["gas"]
    gold = sp["gold"]
    shocks = sp["fred_shocks"]
    econ_news = sp["econ_news"]

    signals = []
    if oil and abs(oil.get("change_pct", 0)) > 2:
        signals.append(("oil", oil["change_pct"], f"Oil {oil['change_pct']:+.1f}% at ${oil['price']:.2f}"))
    if gas and abs(gas.get("change_pct", 0)) > 2:
        signals.append(("gas", gas["change_pct"], f"NatGas {gas['change_pct']:+.1f}% at ${gas['price']:.2f}"))
    if gold and abs(gold.get("change_pct", 0)) > 1:
        signals.append(("gold", gold["change_pct"], f"Gold {gold['change_pct']:+.1f}% at ${gold['price']:.2f}"))
    if shocks:
        for s in shocks:
            signals.append(("fred", s.get("pct_change", 0), f"FRED shock: {s.get('indicator','')} {s.get('pct_change',0)}%"))

    if len(signals) >= 2 or shocks:
        # Determine direction consensus
        bearish = sum(1 for _, chg, _ in signals if chg < -2)
        bullish = sum(1 for _, chg, _ in signals if chg > 2)
        signal_strs = [desc for _, _, desc in signals]

        # Cross-reference with prediction markets
        market_view = ""
        if sp["poly_econ"]:
            top = sp["poly_econ"][0]
            market_view = f"Markets: '{top.get('question','')[:60]}' at {top.get('probability',50)}%."

        # Cross-reference with conflict (war drives oil up, recession concerns)
        conflict_econ = ""
        if sp["conflict_news"] and oil and oil.get("change_pct", 0) > 3:
            conflict_econ = f"Oil surge coincides with {len(sp['conflict_news'])} conflict reports. Supply disruption risk, not just demand."
        elif sp["conflict_news"] and oil and oil.get("change_pct", 0) < -3:
            conflict_econ = f"Oil dropping despite {len(sp['conflict_news'])} conflict reports. Market sees these conflicts as contained, not threatening supply."

        hypotheses = []
        if bearish > bullish:
            hypotheses.append("HYPOTHESIS A (demand destruction): Multiple commodities falling together = recession signal, demand evaporating")
            if gold and gold.get("change_pct", 0) > 1:
                hypotheses.append("HYPOTHESIS B (flight to safety): Gold up while energy drops = investors fleeing to safe havens, expecting turmoil")
        elif bullish > bearish:
            hypotheses.append("HYPOTHESIS A (supply shock): Multiple commodities surging = supply constraint, not demand growth")
            hypotheses.append("HYPOTHESIS B (inflation impulse): Energy + commodity surge = cost-push inflation incoming for service businesses")
        if conflict_econ:
            hypotheses.append(f"CROSS-SIGNAL: {conflict_econ}")

        analysis = f"Commodity convergence: {'; '.join(signal_strs)}. "
        if market_view:
            analysis += market_view + " "
        if shocks:
            analysis += f"FRED flagging {len(shocks)} economic shock indicators. "
        if sp.get("tt_econ"):
            analysis += f"Think tank analysis ({len(sp['tt_econ'])} items): {sp['tt_econ'][0].get('title','')[:80]}. "
        if sp.get("cb_signals"):
            analysis += f"Central bank signals: {len(sp['cb_signals'])} recent statements. "
        if sp.get("wb_inflation"):
            high_infl = [w for w in sp["wb_inflation"] if w.get("value", 0) > 5]
            if high_infl:
                analysis += f"World Bank: {len(high_infl)} countries with inflation >5%. "
        if bearish > bullish:
            analysis += "Bearish convergence.multiple indicators pointing to economic slowdown."
        elif bullish > bearish:
            analysis += "Bullish convergence.cost pressures building across energy complex."
        else:
            analysis += "Mixed signals. No clear directional consensus across indicators."

        # Impact on BOSS target market
        biz_angle = ""
        if oil and oil.get("change_pct", 0) > 3:
            biz_angle = "Rising fuel costs squeeze contractor margins. They'll cut 'nice to have' subscriptions first.position BOSS as revenue-generating, not overhead."
        elif oil and oil.get("change_pct", 0) < -3:
            biz_angle = "Falling fuel costs improve contractor margins. Expansion-minded businesses are more receptive. Good window for growth-focused pitch."

        assessments.append({
            "category": "economic",
            "title": f"Economic signals: {len(signals)} indicators {'bearish' if bearish > bullish else 'bullish' if bullish > bearish else 'mixed'}",
            "analysis": analysis,
            "hypotheses": hypotheses,
            "watch_for": [
                "If oil and gold move in same direction = crisis; opposite = rotation",
                "FRED shock + market divergence = market hasn't priced it in yet",
                "Contractor sentiment shift in Reddit within 48hrs of commodity moves",
            ],
            "confidence": min(85, 55 + len(signals) * 10),
            "sources_used": ["commodities", "fred", "polymarket", "gdelt", "think_tanks", "official_feeds", "world_bank"],
            "time_horizon": "7d",
            "business_angle": biz_angle,
        })

    # =====================================================================
    # FUSED ASSESSMENT 3: Weather + demand + opportunity timing
    # =====================================================================
    if sp["severe_wx"]:
        states_hit = list(set(w.get("state", "") for w in sp["severe_wx"]))
        heat = sp["heat_alerts"]
        storms = sp["storm_alerts"]
        event_types = list(set(w.get("event", "") for w in sp["severe_wx"]))[:5]

        # Cross-reference: are these states in BOSS territory?
        boss_states = {"TX", "MS", "AR", "AL", "TN", "OK", "NM"}
        territory_overlap = [s for s in states_hit if s in boss_states]

        # Cross-reference: Reddit pain from these regions?
        region_pain = [p for p in sp["pain_posts"]
                       if any(s.lower() in (p.get("title") or "").lower() for s in states_hit)]

        # Cross-reference: oil/gas prices affecting contractor costs
        cost_pressure = ""
        if gas and gas.get("change_pct", 0) > 3:
            cost_pressure = f"Compounding factor: natural gas up {gas['change_pct']:.1f}%.HVAC operating costs rising simultaneously."
        if oil and oil.get("change_pct", 0) > 3:
            cost_pressure = f"Compounding factor: fuel up {oil['change_pct']:.1f}%. Service call costs rising during peak demand."

        analysis_parts = [f"{len(sp['severe_wx'])} severe/extreme alerts across {', '.join(states_hit)}."]
        analysis_parts.append(f"Event types: {', '.join(event_types[:4])}.")
        if heat:
            analysis_parts.append(f"{len(heat)} heat alerts.HVAC demand spike. Historical pattern: 40-70% increase in missed calls during heat emergencies. Every unanswered call = $400-2500 lost revenue for the contractor.")
        if storms:
            analysis_parts.append(f"{len(storms)} storm alerts.roofers, restoration, and plumbers will be overwhelmed within 24-48hrs.")
        if territory_overlap:
            analysis_parts.append(f"BOSS TERRITORY HIT: {', '.join(territory_overlap)}.these are your states. Direct targeting opportunity.")
        if region_pain:
            analysis_parts.append(f"CORROBORATION: {len(region_pain)} Reddit posts about missed calls from affected regions.real-time confirmation of the pain.")
        if cost_pressure:
            analysis_parts.append(cost_pressure)

        hypotheses = []
        if heat and storms:
            hypotheses.append("Combined heat + storms = maximum service demand overload. Contractors can't keep up with emergency AND routine calls.")
        if territory_overlap:
            hypotheses.append(f"ACTIONABLE: {', '.join(territory_overlap)} businesses are losing calls RIGHT NOW. 24-48hr window to reach them while pain is acute.")

        assessments.append({
            "category": "market_opportunity",
            "title": f"Service demand surge: {len(sp['severe_wx'])} alerts, {len(territory_overlap)} BOSS states hit",
            "analysis": " ".join(analysis_parts),
            "hypotheses": hypotheses,
            "watch_for": [
                "Storm path progression.get ahead of it, call businesses BEFORE they're overwhelmed",
                "Reddit pain posts spiking in specific subreddits = niche confirmation",
                "If heat wave persists >3 days, missed call rates compound (crews fatigue)",
            ],
            "confidence": min(95, 65 + len(sp["severe_wx"]) * 2 + len(territory_overlap) * 10),
            "sources_used": ["noaa", "reddit", "commodities"],
            "time_horizon": "24-48h",
            "business_angle": f"{'IMMEDIATE: Target ' + ', '.join(territory_overlap) + ' contractors NOW' if territory_overlap else 'Monitor. Not in BOSS territory yet'}",
        })

    # =====================================================================
    # FUSED ASSESSMENT 4: Seismic + nuclear + news silence
    # =====================================================================
    if sp["major_quakes"]:
        biggest = max(sp["major_quakes"], key=lambda q: q.get("magnitude", 0))
        mag = biggest.get("magnitude", 0)
        place = biggest.get("place", "unknown")

        # Cross-reference: news coverage
        quake_anomalies = [a for a in sp["anomalies"] if a.get("pattern") == "seismic_major"]
        has_news_gap = any(a.get("news_count", 99) < 3 for a in quake_anomalies)

        # Cross-reference: nearby nuclear sites (via intel KB)
        nuclear_note = ""
        if HAS_INTEL and biggest.get("coordinates") and len(biggest["coordinates"]) >= 2:
            lat, lon = biggest["coordinates"][1], biggest["coordinates"][0]
            depth = biggest.get("depth_km", 999)
            nearby_nuke = find_nearby_nuclear_sites(lat, lon)
            if nearby_nuke:
                nuclear_note = f"PROXIMITY ALERT: {len(nearby_nuke)} nuclear sites within range: {', '.join(n.get('name','?')[:30] for n in nearby_nuke[:3])}."
            if depth < 10 and mag > 5.5:
                nuclear_note += " Shallow depth (<10km) at this magnitude warrants monitoring for non-natural origin."

        # Cross-reference: radiation data
        elevated_rad = [s for s in data.get("safecast", []) if s.get("elevated")]

        hypotheses = []
        hypotheses.append(f"MOST LIKELY: Natural tectonic event.{'known seismically active zone' if 'ridge' in place.lower() or 'fault' in place.lower() else 'location consistent with plate boundary activity'}")
        if nuclear_note:
            hypotheses.append(f"MONITOR: {nuclear_note}")
        if elevated_rad:
            hypotheses.append(f"ELEVATED RADIATION: {len(elevated_rad)} readings above baseline.correlate with quake location for nuclear facility damage assessment")
        if has_news_gap:
            hypotheses.append("NEWS GAP: Major seismic event with minimal media coverage.either remote location or reporting delay")

        analysis = f"M{mag} at {place}. Total significant quakes (M5.0+): {len(sp['major_quakes'])}. "
        if biggest.get("tsunami"):
            analysis += "TSUNAMI FLAG SET. "
        analysis += f"Depth: {biggest.get('depth_km', '?')}km. Felt reports: {biggest.get('felt', 0)}. "
        if nuclear_note:
            analysis += nuclear_note + " "
        if elevated_rad:
            analysis += f"Safecast: {len(elevated_rad)} elevated readings (>350 CPM). "
        gdacs_eq = sp.get("gdacs_quakes", [])
        gdacs_eq_match = [g for g in gdacs_eq if g.get("alert_level") in ("Orange", "Red")]
        if gdacs_eq_match:
            analysis += f"GDACS confirms {len(gdacs_eq_match)} elevated earthquake alerts (Orange/Red). "
        elif gdacs_eq:
            analysis += f"GDACS tracking {len(gdacs_eq)} earthquake events (all Green. Low humanitarian impact). "

        sources_used = ["usgs", "safecast", "gdelt", "atlas_intel"]
        if gdacs_eq:
            sources_used.append("gdacs")

        assessments.append({
            "category": "environmental",
            "title": f"Seismic event: M{mag} at {place}" + (". Nuclear proximity" if nuclear_note else ""),
            "analysis": analysis,
            "hypotheses": hypotheses,
            "watch_for": [
                "Aftershock sequence (increasing aftershock magnitude = potential larger event coming)",
                "Tsunami warnings issued/cancelled",
                "Radiation readings change near nuclear facilities within 500km",
                "News coverage appearing (or not).prolonged silence on large quakes is itself a signal",
            ],
            "confidence": min(90, 70 + int(mag) * 3),
            "sources_used": sources_used,
            "time_horizon": "24h",
        })

    # =====================================================================
    # FUSED ASSESSMENT 5: Information environment (claims + wiki + divergence)
    # =====================================================================
    wiki_storms = [a for a in sp["anomalies"] if a.get("pattern") == "wiki_storm"]
    if claims or wiki_storms:
        analysis_parts = []
        hypotheses = []

        if claims:
            top_claim = claims[0]
            vel = top_claim.get("velocity", 0)
            sources = top_claim.get("unique_sources", 0)
            countries = top_claim.get("countries_reporting", [])
            tone = top_claim.get("tone_label", "neutral")
            analysis_parts.append(f"Top claim: '{top_claim.get('claim','')[:80]}'.{vel} articles, {sources} sources, {len(countries)} countries, {tone} tone.")

            if top_claim.get("related_predictions"):
                pred = top_claim["related_predictions"][0]
                analysis_parts.append(f"Prediction market tracking this: '{pred.get('question','')[:50]}' at {pred.get('probability',50)}%.")
                if tone == "negative" and pred.get("probability", 50) < 30:
                    hypotheses.append("DIVERGENCE: Negative media tone but markets discount the outcome.either media is overreacting or markets are behind.")
                elif tone == "negative" and pred.get("probability", 50) > 70:
                    hypotheses.append("CONVERGENCE: Both media and markets agree this is significant.high-confidence signal.")
            else:
                hypotheses.append("NO MARKET COVERAGE: This claim has no corresponding prediction market.could be underpriced risk if it proves true.")

            reddit_corr = top_claim.get("reddit_mentions", 0)
            if reddit_corr > 0:
                analysis_parts.append(f"Reddit corroboration: {reddit_corr} matching discussions.")
            else:
                analysis_parts.append("No Reddit corroboration.may be media-only narrative, not organically spreading.")

        if wiki_storms:
            for ws in wiki_storms[:2]:
                article = ws.get("article", "?")
                edits = ws.get("edit_count", 0)
                news_cov = ws.get("news_coverage", 0)
                analysis_parts.append(f"Wikipedia edit storm on '{article}' ({edits} edits, {news_cov} matching news articles).")
                if news_cov == 0:
                    hypotheses.append(f"INFORMATION WARFARE INDICATOR: Wikipedia page '{article}' being heavily edited with no news coverage.possible narrative shaping before event becomes public.")

        assessments.append({
            "category": "geopolitical",
            "title": f"Information environment: {len(claims)} tracked claims, {len(wiki_storms)} wiki storms",
            "analysis": " ".join(analysis_parts),
            "hypotheses": hypotheses,
            "watch_for": [
                "Claim velocity increasing = story gaining traction, decreasing = narrative collapsing",
                "Wikipedia edits from government IP ranges = state-level information operations",
                "Prediction market movement on related topics within 24hrs of claim spread",
            ],
            "confidence": min(80, 40 + (claims[0].get("velocity", 0) * 5 if claims else 0) + len(wiki_storms) * 15),
            "sources_used": ["gdelt", "reddit", "wikipedia", "polymarket"],
            "time_horizon": "48h",
        })

    # =====================================================================
    # FUSED ASSESSMENT 6: AI/tech competitive landscape
    # =====================================================================
    if len(sp["ai_signals"]) >= 3:
        titles = [s.get("title", "")[:60] for s in sp["ai_signals"][:5]]

        # Cross-reference: any competitor mentions?
        competitors = ["smith.ai", "ruby receptionist", "patlive", "avoca", "my ai front desk",
                       "dialpad", "grasshopper", "ai receptionist", "voice ai"]
        competitor_hits = []
        for item in sp["ai_signals"] + sp["rss"]:
            t = (item.get("title") or "").lower()
            for comp in competitors:
                if comp in t:
                    competitor_hits.append((comp, item.get("title", "")[:60]))

        # Cross-reference: Reddit small business AI sentiment
        ai_reddit = [p for p in sp["reddit"] if any(k in (p.get("title") or "").lower()
                     for k in ["ai replac", "automat", "ai for", "chatbot", "ai answer"])]

        analysis = f"{len(sp['ai_signals'])} AI signals across HN/RSS/Reddit. Topics: {'; '.join(titles[:3])}. "
        if competitor_hits:
            analysis += f"COMPETITOR ALERT: {len(competitor_hits)} mentions.{', '.join(set(c for c, _ in competitor_hits[:3]))}. "
        if ai_reddit:
            analysis += f"Reddit AI sentiment: {len(ai_reddit)} posts about AI in small business. "

        hypotheses = []
        if competitor_hits:
            hypotheses.append(f"WATCH: Competitor activity detected ({', '.join(set(c for c, _ in competitor_hits))}). Check for pricing changes, new features, or market moves.")
        hypotheses.append(f"Market signal: {len(sp['ai_signals'])} mentions suggests {'normal activity' if len(sp['ai_signals']) < 10 else 'elevated attention.possible capability release or regulatory news'}")

        assessments.append({
            "category": "technology",
            "title": f"AI/Tech landscape: {len(sp['ai_signals'])} signals" + (f", {len(competitor_hits)} competitor mentions" if competitor_hits else ""),
            "analysis": analysis,
            "hypotheses": hypotheses,
            "watch_for": [
                "Competitor pricing changes (especially if they lower to match BOSS)",
                "New AI voice agent announcements.potential threats or partnership targets",
                "Small business AI adoption stories in Reddit = market validation",
            ],
            "confidence": 60 + (15 if competitor_hits else 0),
            "sources_used": ["hackernews", "rss", "reddit"],
            "time_horizon": "30d",
            "business_angle": "New AI tools = new automation possibilities for BOSS clients" + (f". PRIORITY: Monitor {', '.join(set(c for c, _ in competitor_hits[:2]))} activity." if competitor_hits else ""),
        })

    # =====================================================================
    # FUSED ASSESSMENT 7: Intelligence gaps.what we CAN'T see
    # =====================================================================
    if sp["missing"]:
        # The absence of data is itself intelligence
        analysis_parts = [f"{len(sp['missing'])} sources returned no data: {', '.join(sp['missing'])}."]

        hypotheses = []
        if "gdelt" in sp["missing"]:
            hypotheses.append("GDELT gap: No global news feed = blind to breaking events. Cannot cross-reference military or economic signals with news coverage.")
        if "adsb" in sp["missing"]:
            hypotheses.append("ADS-B gap: No military aircraft data = cannot assess military posture or detect covert activity.")
        if "fred" in sp["missing"]:
            hypotheses.append("FRED gap: No economic indicators = cannot confirm or deny recession/inflation signals from commodity moves.")
        if "ioda" in sp["missing"]:
            analysis_parts.append("IODA (internet outage) data unavailable.cannot detect blackouts that precede political crises.")

        assessments.append({
            "category": "security",
            "title": f"Intelligence gaps: {len(sp['missing'])} blind spots active",
            "analysis": " ".join(analysis_parts) + " These gaps reduce confidence in all other assessments that would cross-reference these sources.",
            "hypotheses": hypotheses,
            "watch_for": [
                "If multiple sources fail simultaneously, check if it's network-wide (your connection) vs source-specific (their API)",
                "Prolonged GDELT outage = check alternative news APIs",
                "ADS-B silence could mean tracking is being deliberately suppressed.itself a signal",
            ],
            "confidence": 95,
            "sources_used": ["system"],
            "time_horizon": "next_scan",
        })

    # =====================================================================
    # FUSED ASSESSMENT 8: Pain signals with timing intelligence
    # =====================================================================
    if sp["pain_posts"]:
        subs = list(set(p.get("subreddit", "") for p in sp["pain_posts"]))

        # Cross-reference: are pain signals correlating with weather events?
        weather_pain_link = ""
        if sp["heat_alerts"] or sp["storm_alerts"]:
            weather_pain_link = f"CORRELATION: Weather alerts active in BOSS territory while pain signals spike. Weather is driving the pain NOW, not hypothetically."

        analysis = f"{len(sp['pain_posts'])} posts about missed calls or lost customers across {', '.join(subs[:5])}. "
        if weather_pain_link:
            analysis += weather_pain_link + " "
        analysis += "Each post represents a business owner who JUST experienced the pain BOSS solves."

        assessments.append({
            "category": "market_opportunity",
            "title": f"Live pain signals: {len(sp['pain_posts'])} businesses reporting missed call losses",
            "analysis": analysis,
            "hypotheses": [
                f"IMMEDIATE: These businesses are actively searching for solutions. Warm targets",
                f"PATTERN: Pain concentrated in {', '.join(subs[:3])} = these niches are underserved right now",
            ],
            "watch_for": [
                "Pain post volume increasing = market timing is right",
                "New subreddits appearing with pain signals = expanding niche opportunity",
            ],
            "confidence": 80,
            "sources_used": ["reddit", "noaa"],
            "time_horizon": "7d",
            "business_angle": "Direct evidence of the problem BOSS solves.these posters are pre-qualified leads",
        })

    # =====================================================================
    # FUSED ASSESSMENT 9: Space weather + infrastructure risk
    # =====================================================================
    flare_count = len(sp.get("solar_flares", []))
    storm_count = len(sp.get("geo_storms", []))
    if flare_count > 0 or storm_count > 0:
        x_flares = [f for f in sp.get("solar_flares", []) if f.get("class", "").startswith("X")]
        max_kp = max((s.get("kp_index", 0) for s in sp.get("geo_storms", [])), default=0)
        parts = []
        if x_flares:
            parts.append(f"{len(x_flares)} X-class solar flare(s) detected.potential GPS/comm/power grid disruption")
        elif flare_count:
            parts.append(f"{flare_count} M/X-class flare(s) in past 7 days")
        if storm_count:
            parts.append(f"Kp index reached {max_kp}.{'severe' if max_kp >= 7 else 'moderate'} geomagnetic storm")
        analysis = ". ".join(parts) + "."
        if sp.get("adsb"):
            analysis += f" Cross-ref: {len(sp['adsb'])} aircraft tracked.GPS-dependent navigation could be affected."
        assessments.append({
            "category": "environmental",
            "title": f"Space weather alert: {flare_count} flare(s), Kp={max_kp}",
            "analysis": analysis,
            "hypotheses": [
                f"HYPOTHESIS A (transient): Solar activity subsides within 48h, no lasting impact",
                f"HYPOTHESIS B (cascade): CME impact causes GPS degradation + power grid stress in high-latitude regions",
            ],
            "watch_for": [
                "NOAA SWPC upgrade to G3+ geomagnetic storm warning",
                "Airline reroutes away from polar corridors",
                "Power grid operator emergency actions in Scandinavia/Canada",
            ],
            "confidence": 70 if x_flares or max_kp >= 6 else 55,
            "sources_used": ["space_weather", "adsb"],
            "time_horizon": "48h",
        })

    # =====================================================================
    # FUSED ASSESSMENT 10: Cyber threat landscape
    # =====================================================================
    kev_count = len(sp.get("cisa_kev", []))
    ransomware_count = len(sp.get("ransomware_vulns", []))
    if kev_count > 0:
        vendors = {}
        for v in sp.get("cisa_kev", []):
            vn = v.get("vendor", "Unknown")
            vendors[vn] = vendors.get(vn, 0) + 1
        top_vendors = sorted(vendors.items(), key=lambda x: x[1], reverse=True)[:3]
        vendor_str = ", ".join(f"{v}({c})" for v, c in top_vendors)
        analysis = f"{kev_count} new known exploited vulnerabilities in past 14 days. Top targets: {vendor_str}."
        if ransomware_count:
            analysis += f" {ransomware_count} with confirmed ransomware use. Active threat."
        cyber_rss = [r for r in sp.get("rss", []) if any(k in (r.get("source") or "").lower() for k in ["krebs", "cisa"])]
        if cyber_rss:
            analysis += f" {len(cyber_rss)} cybersecurity news items corroborate elevated threat environment."
        assessments.append({
            "category": "security",
            "title": f"Cyber threat assessment: {kev_count} KEVs, {ransomware_count} ransomware-linked",
            "analysis": analysis,
            "hypotheses": [
                "HYPOTHESIS A (targeted): Specific vendor/product under coordinated attack campaign",
                "HYPOTHESIS B (broad): General uptick in exploit activity across multiple vectors",
            ],
            "watch_for": [
                "CISA emergency directive naming specific products",
                "Ransomware gang claiming new victims in affected sectors",
                "Vendor emergency patch releases",
            ],
            "confidence": 75 if ransomware_count > 0 else 60,
            "sources_used": ["cisa_kev", "rss"],
            "time_horizon": "7d",
        })

    # =====================================================================
    # FUSED ASSESSMENT 11: Yield curve + economic signals + markets
    # =====================================================================
    if sp.get("treasury") and sp.get("yield_inverted"):
        latest_t = sp["treasury"][-1] if sp["treasury"] else {}
        spread = round(latest_t.get("10_yr", 0) - latest_t.get("2_yr", 0), 3)
        analysis = f"Yield curve inverted: 2Y-10Y spread at {spread}%. Historically precedes recession by 12-18 months."
        if sp.get("fred_shocks"):
            analysis += f" {len(sp['fred_shocks'])} FRED indicators also showing stress."
        if sp.get("poly_econ"):
            econ_probs = [(p.get("question", ""), p.get("probability", 0)) for p in sp["poly_econ"][:3]]
            analysis += " Market pricing: " + "; ".join(f"{q[:60]} ({p}%)" for q, p in econ_probs) + "."
        assessments.append({
            "category": "economic",
            "title": f"Recession signal: yield curve inverted ({spread}% spread)",
            "analysis": analysis,
            "hypotheses": [
                "HYPOTHESIS A (false signal): Inversion driven by Fed policy mechanics, not recession expectations",
                "HYPOTHESIS B (leading indicator): Recession materializes within 12-18 months as historically predicted",
            ],
            "watch_for": [
                "Un-inversion (curve steepening).historically occurs 3-6 months before recession starts",
                "Initial jobless claims rising above 250K sustained",
                "Consumer spending deceleration in FRED data",
            ],
            "confidence": 65,
            "sources_used": ["treasury", "fred", "polymarket"],
            "time_horizon": "30d",
        })

    # =====================================================================
    # FUSED ASSESSMENT 12: Sanctions environment + geopolitical pressure
    # =====================================================================
    ofac_count = len(sp.get("ofac_entries", []))
    eu_count = len(sp.get("eu_entries", []))
    if ofac_count > 0 or eu_count > 0:
        analysis = f"Sanctions landscape: {ofac_count} OFAC (US) + {eu_count} EU sanctioned entities in latest data."
        if sp.get("tt_conflict"):
            analysis += f" Think tanks flagging {len(sp['tt_conflict'])} conflict-related analyses."
        if sp.get("conflict_news"):
            analysis += f" GDELT: {len(sp['conflict_news'])} conflict articles cross-referencing."
        if sp.get("poly_conflict"):
            top_p = sp["poly_conflict"][0]
            analysis += f" Market: '{top_p.get('question','')[:50]}' at {top_p.get('probability',50)}%."
        assessments.append({
            "category": "geopolitical",
            "title": f"Sanctions posture: {ofac_count} US + {eu_count} EU targets tracked",
            "analysis": analysis,
            "hypotheses": [
                "HYPOTHESIS A (escalation): New sanctions rounds signal diplomatic deterioration.follow with trade restrictions",
                "HYPOTHESIS B (status quo): Existing sanctions maintained, no new designations = stable geopolitical environment",
            ],
            "watch_for": [
                "New OFAC SDN additions in energy/defense sectors",
                "EU-US sanctions divergence on any country = policy split",
                "Sanctions evasion reports in GDELT or think tank feeds",
            ],
            "confidence": 60,
            "sources_used": ["ofac_sdn", "eu_sanctions", "think_tanks", "gdelt", "polymarket"],
            "time_horizon": "30d",
        })

    # =====================================================================
    # FUSED ASSESSMENT 13: Think tank consensus / divergence
    # =====================================================================
    tt_all = sp.get("think_tanks", [])
    if len(tt_all) >= 10:
        tt_topics = {}
        for t in tt_all:
            title = (t.get("title") or "").lower()
            for topic in ["ukraine", "russia", "china", "taiwan", "iran", "israel",
                         "nato", "ai", "nuclear", "climate", "trade"]:
                if topic in title:
                    tt_topics.setdefault(topic, []).append(t)
        if tt_topics:
            top_topics = sorted(tt_topics.items(), key=lambda x: len(x[1]), reverse=True)[:5]
            topic_summary = "; ".join(f"{topic}({len(items)})" for topic, items in top_topics)
            analysis = f"Think tank attention index: {len(tt_all)} analyses across {len(tt_topics)} topics. Top focus: {topic_summary}."
            top_topic, top_items = top_topics[0]
            analysis += f" Dominant theme '{top_topic}'.latest: {top_items[0].get('title','')[:80]}."
            if sp.get("cb_signals"):
                analysis += f" Central banks publishing {len(sp['cb_signals'])} statements simultaneously."
            assessments.append({
                "category": "geopolitical",
                "title": f"Analyst consensus: {len(tt_all)} think tank pieces, top focus: {top_topics[0][0]}",
                "analysis": analysis,
                "hypotheses": [
                    f"HYPOTHESIS A (crisis developing): Heavy analyst attention on '{top_topic}' indicates building crisis that mainstream news hasn't caught yet",
                    f"HYPOTHESIS B (reaction): Analysts responding to events already in progress. This is assessment, not prediction",
                ],
                "watch_for": [
                    f"Shift in think tank attention AWAY from {top_topic} to new topic = new crisis emerging",
                    "Multiple think tanks publishing simultaneously on same topic = coordinated concern",
                    "Official feeds (Fed/ECB/UN) echoing think tank themes = institutional confirmation",
                ],
                "confidence": 70,
                "sources_used": ["think_tanks", "official_feeds"],
                "time_horizon": "7d",
            })

    # =====================================================================
    # FUSED ASSESSMENT 14: GDACS multi-hazard global disaster picture
    # =====================================================================
    gdacs_elevated = sp.get("gdacs_orange_red", [])
    if gdacs_elevated:
        by_type = {}
        for g in gdacs_elevated:
            by_type.setdefault(g.get("event_type", "?"), []).append(g)
        type_labels = {"EQ": "earthquake", "TC": "tropical cyclone", "FL": "flood",
                       "VO": "volcano", "DR": "drought", "WF": "wildfire"}
        type_summary = "; ".join(f"{type_labels.get(t, t)}({len(items)})" for t, items in by_type.items())
        analysis = f"GDACS elevated alerts: {len(gdacs_elevated)} Orange/Red events.{type_summary}. "
        countries = set()
        for g in gdacs_elevated:
            c = g.get("country", "")
            if c:
                countries.add(c.split(",")[0].strip())
        if countries:
            analysis += f"Affected regions: {', '.join(sorted(countries)[:8])}. "
        usgs_quakes = sp.get("major_quakes", [])
        if usgs_quakes and sp.get("gdacs_quakes"):
            analysis += f"Cross-ref: USGS reports {len(usgs_quakes)} M5.0+ quakes; GDACS tracking {len(sp['gdacs_quakes'])} earthquake events. "
        if sp.get("gdacs_cyclones"):
            analysis += f"Active tropical cyclones: {len(sp['gdacs_cyclones'])}. "
        if sp.get("fires"):
            analysis += f"NASA FIRMS: {len(sp['fires'])} high-confidence fire detections. "
        if sp.get("disaster_news"):
            analysis += f"GDELT: {len(sp['disaster_news'])} disaster-related articles corroborate. "

        hypotheses = []
        if sp.get("gdacs_droughts"):
            hypotheses.append(f"HUMANITARIAN: {len(sp['gdacs_droughts'])} drought alerts.food security and displacement risk in affected regions")
        if sp.get("gdacs_cyclones"):
            hypotheses.append(f"INFRASTRUCTURE: Active cyclones threaten shipping lanes and port operations.monitor commodity supply chains")
        if sp.get("gdacs_floods"):
            hypotheses.append(f"CASCADING RISK: {len(sp['gdacs_floods'])} flood events.watch for infrastructure damage, disease outbreaks, displacement")
        if not hypotheses:
            hypotheses.append("MONITORING: Elevated disaster activity.watch for humanitarian escalation or cascading infrastructure failures")

        assessments.append({
            "category": "environmental",
            "title": f"Global disaster alert: {len(gdacs_elevated)} elevated events across {len(by_type)} hazard types",
            "analysis": analysis,
            "hypotheses": hypotheses,
            "watch_for": [
                "Alert level escalation from Orange to Red on any event",
                "Multiple disaster types converging on same region (compound disaster)",
                "Commodity price spikes correlated with disaster-affected supply chains",
                "Humanitarian agency surge (ReliefWeb) confirming escalation",
            ],
            "confidence": 80,
            "sources_used": ["gdacs", "usgs", "nasa_firms", "gdelt"],
            "time_horizon": "7d",
        })

    # =====================================================================
    # FUSED ASSESSMENT 15: Corporate signals + insider activity
    # =====================================================================
    insider_count = len(sp.get("insider_trades", []))
    material_count = len(sp.get("material_events", []))
    if insider_count >= 3 or material_count >= 3:
        insider_sells = [t for t in sp.get("insider_trades", []) if "sale" in (t.get("title", "")).lower()]
        analysis = f"SEC EDGAR shows {insider_count} insider trades and {material_count} material event filings."
        if insider_sells:
            analysis += f" {len(insider_sells)} are insider SELLS. Potential bearish signal."
        if sp.get("av_bearish"):
            analysis += f" Alpha Vantage shows {len(sp['av_bearish'])} bearish news articles, confirming negative sentiment."
        if sp.get("yield_inverted"):
            analysis += " Combined with inverted yield curve, multiple indicators point to economic caution."
        assessments.append({
            "title": f"Corporate Activity Cluster: {insider_count} insider trades, {material_count} material events",
            "category": "economic",
            "analysis": analysis,
            "hypotheses": [
                "Insider selling precedes earnings miss or guidance cut.common pattern before corrections",
                "8-K cluster indicates M&A wave.consolidation creates displaced customers needing new vendors",
                "Routine quarterly filing activity with no directional signal.noise, not signal",
            ],
            "watch_for": [
                "Insider sells in AI/SaaS companies.direct BOSS competitor intelligence",
                "8-K 'going concern' filings.business failures create orphaned customers",
                "Earnings misses following insider sells.confirms the pattern",
            ],
            "confidence": 55 + (10 if len(insider_sells) >= 5 else 0) + (10 if sp.get("av_bearish") else 0),
            "sources_used": ["sec_edgar", "alpha_vantage", "treasury"],
            "time_horizon": "7-30d",
            "business_angle": "Track AI/tech company 8-K filings for competitor shutdowns or pivots. Their displaced customers become BOSS prospects.",
        })

    # =====================================================================
    # FUSED ASSESSMENT 16: FEMA + weather + demand convergence
    # =====================================================================
    fema_territory = sp.get("fema_boss_territory", [])
    if fema_territory:
        affected_states = list(set(f.get("state", "") for f in fema_territory))
        inc_types = list(set(f.get("type", "") for f in fema_territory))
        analysis = f"FEMA declared disasters in BOSS territory: {', '.join(affected_states)}. Types: {', '.join(inc_types)}."
        if sp["severe_wx"]:
            analysis += f" NOAA confirms {len(sp['severe_wx'])} active severe weather warnings in overlapping areas."
        if sp["pain_posts"]:
            analysis += f" Reddit shows {len(sp['pain_posts'])} pain signal posts from service businesses."
        assessments.append({
            "title": f"BOSS Territory Disaster: FEMA declarations active in {', '.join(affected_states)}",
            "category": "market_opportunity",
            "analysis": analysis,
            "hypotheses": [
                "Service contractors in disaster zones are overwhelmed.missing calls = losing revenue = perfect BOSS pitch timing",
                "Disaster response creates temporary demand spike.contractors too busy to answer phones for 2-6 weeks",
                "Insurance claims drive roofer/restoration volume.these businesses need call handling most when they can least afford to miss calls",
            ],
            "watch_for": [
                "New FEMA declarations in TX, MS, AR, AL, TN, OK, NM",
                "Reddit posts from contractors in affected areas complaining about call volume",
                "Local news reporting contractor shortages.confirms market pressure",
            ],
            "confidence": 88,
            "sources_used": ["fema", "noaa", "reddit"],
            "time_horizon": "1-4 weeks",
            "business_angle": f"Target HVAC/roofer/restoration businesses in {', '.join(affected_states)} RIGHT NOW. Say: 'You're drowning in calls. We'll catch every one for $50/mo.'",
        })

    # =====================================================================
    # FUSED ASSESSMENT 17: Market sentiment convergence
    # =====================================================================
    av_bearish = sp.get("av_bearish", [])
    av_bullish = sp.get("av_bullish", [])
    trend_signals = sp.get("trend_signals", [])
    econ_cal = sp.get("econ_calendar", [])
    if len(av_bearish) + len(av_bullish) >= 3 or trend_signals:
        sentiment = "bearish" if len(av_bearish) > len(av_bullish) else "bullish" if len(av_bullish) > len(av_bearish) else "mixed"
        analysis = f"Market sentiment is {sentiment}: {len(av_bearish)} bearish vs {len(av_bullish)} bullish signals from Alpha Vantage."
        if trend_signals:
            for ts in trend_signals[:3]:
                analysis += f" {ts['symbol']} move ACCELERATING: {ts['prev_change']:+.1f}% → {ts['current_change']:+.1f}%."
        if econ_cal:
            upcoming = [e for e in econ_cal if e.get("impact") == "high"]
            if upcoming:
                analysis += f" {len(upcoming)} high-impact economic events upcoming."
        if sp.get("poly_econ"):
            analysis += f" Polymarket tracking {len(sp['poly_econ'])} economic questions."
        assessments.append({
            "title": f"Market Sentiment Convergence: {sentiment.upper()} with {len(trend_signals)} accelerating trends",
            "category": "economic",
            "analysis": analysis,
            "hypotheses": [
                f"{'Bearish sentiment precedes correction. Businesses will tighten spending' if sentiment == 'bearish' else 'Bullish sentiment supports expansion. Businesses more willing to invest in AI tools'}",
                "Sentiment is noise without earnings confirmation.wait for next earnings cycle",
                "Commodity acceleration signals supply chain disruption, not broad market move",
            ],
            "watch_for": [
                "VIX movement confirming sentiment direction",
                "FRED unemployment data.rising = recession, falling = expansion",
                "Commodity price reversals that invalidate trend acceleration",
            ],
            "confidence": 60 + (10 if trend_signals else 0) + (5 if len(av_bearish) >= 5 else 0),
            "sources_used": ["alpha_vantage", "commodities", "finnhub", "polymarket", "fred"],
            "time_horizon": "7-14d",
            "business_angle": f"{'Bearish market: pitch cost savings. Every missed call is money they cant afford to lose.' if sentiment == 'bearish' else 'Bullish market: pitch growth. AI receptionist lets them scale without hiring.'}",
        })

    # =====================================================================
    # FUSED ASSESSMENT 18: Currency + trade + supply chain
    # =====================================================================
    currency_shocks = sp.get("currency_shocks", [])
    if currency_shocks:
        shock_names = [f"{c['name']} ({c['change_pct']:+.1f}%)" for c in currency_shocks[:3]]
        analysis = f"Currency shocks detected: {', '.join(shock_names)}."
        if sp["oil"]:
            analysis += f" Oil at ${sp['oil'].get('price', '?')}, {sp['oil'].get('change_pct', 0):+.1f}%."
        if sp.get("ofac_entries"):
            analysis += f" {len(sp['ofac_entries'])} OFAC sanctions entries may be driving currency moves."
        assessments.append({
            "title": f"Currency Shock: {len(currency_shocks)} currencies moving >2% vs USD",
            "category": "economic",
            "analysis": analysis,
            "hypotheses": [
                "Currency shock driven by geopolitical event.check GDELT conflict news for correlation",
                "Monetary policy divergence.central banks moving at different speeds",
                "Sanctions-driven capital flight.currency weakening in targeted countries",
            ],
            "watch_for": [
                "Follow-on moves in same currencies next 48hrs",
                "Central bank intervention statements",
                "Import price changes affecting US contractor supply costs",
            ],
            "confidence": 65,
            "sources_used": ["currencies", "commodities", "sanctions", "gdelt"],
            "time_horizon": "3-7d",
        })

    # =====================================================================
    # FUSED ASSESSMENT 19: Trader Intelligence Feedback.market edge analysis
    # =====================================================================
    trader_intel = sp.get("trader_intel", {})
    trader_consensus = sp.get("trader_consensus", [])
    trader_hotspots = sp.get("trader_hotspots", [])
    trader_info_gaps = sp.get("trader_info_gaps", [])
    trader_sentiment = sp.get("trader_sentiment", {})
    trader_edges = sp.get("trader_edges", {})
    trader_divergences = sp.get("trader_divergences", [])

    if trader_consensus and len(trader_consensus) >= 3:
        top_edges = trader_consensus[:5]
        edge_countries = set()
        edge_topics = set()
        for e in top_edges:
            edge_countries.update(e.get("countries", []))
            edge_topics.update(e.get("topics", []))

        analysis_parts = [f"Paper trader analyzed {trader_intel.get('markets_analyzed', 0)} markets, found {trader_intel.get('edges_found', 0)} edges."]

        if top_edges:
            top_q = top_edges[0]
            analysis_parts.append(f"Largest edge: '{top_q.get('question', '')[:60]}'.market {top_q.get('market_prob')}% vs ATLAS {top_q.get('atlas_prob')}% ({top_q.get('edge', 0):.1f}pp edge).")

        if trader_hotspots:
            hotspot_names = [h["country"] for h in trader_hotspots[:5]]
            analysis_parts.append(f"Geopolitical hotspots by market attention: {', '.join(hotspot_names)}.")

        neg_topics = [t for t, s in trader_sentiment.items() if s < -0.15]
        pos_topics = [t for t, s in trader_sentiment.items() if s > 0.15]
        if neg_topics:
            analysis_parts.append(f"Negative Reddit sentiment on: {', '.join(neg_topics)}.public mood contra-bullish.")
        if pos_topics:
            analysis_parts.append(f"Positive Reddit sentiment on: {', '.join(pos_topics)}.crowd is bullish.")

        if trader_divergences:
            div = trader_divergences[0]
            analysis_parts.append(f"Cross-platform divergence: '{div.get('topic', '')[:50]}' spread {div.get('spread', 0)}pp.information asymmetry signal.")

        # Cross-reference with ATLAS's own data
        for country in list(edge_countries)[:3]:
            country_names = []
            for k, v in {
                "US": "United States", "RU": "Russia", "CN": "China", "IR": "Iran",
                "UA": "Ukraine", "IL": "Israel", "KP": "North Korea", "TW": "Taiwan",
                "SA": "Saudi Arabia", "TR": "Turkey",
            }.items():
                if k == country:
                    country_names.append(v)
            if country_names:
                conflict_mentions = sum(1 for g in sp["conflict_news"]
                                       if country_names[0].lower() in (g.get("title", "") or "").lower())
                if conflict_mentions:
                    analysis_parts.append(f"{country_names[0]}: {conflict_mentions} conflict articles corroborate trader focus.")

        if trader_info_gaps:
            gap_topics = [g.get("question", "")[:40] for g in trader_info_gaps[:3]]
            analysis_parts.append(f"Information gaps identified: {'; '.join(gap_topics)}.ATLAS should prioritize these regions next scan.")

        hypotheses = []
        if trader_edges.get("peace", {}).get("avg_edge", 0) > 4:
            hypotheses.append("HYPOTHESIS A: Markets consistently overpricing peace/diplomacy outcomes.adversarial base rates suggest NO bets have structural edge")
        if trader_edges.get("conflict", {}).get("avg_edge", 0) > 4:
            hypotheses.append("HYPOTHESIS B: Markets underpricing conflict escalation.ATLAS sensors (GDELT, ADS-B, think tanks) see more activity than markets reflect")
        if trader_divergences:
            hypotheses.append("HYPOTHESIS C: Cross-platform price divergences indicate slow information propagation.exploitable window before convergence")
        if trader_info_gaps:
            hypotheses.append(f"HYPOTHESIS D: {len(trader_info_gaps)} markets have zero relevant news.these are either non-events or black holes where information isn't reaching open sources")
        if not hypotheses:
            hypotheses.append("Trader edges concentrated in well-covered geopolitical events.advantage comes from multi-source fusion, not information asymmetry")

        watch_for = [
            "Edge convergence: if market moves toward ATLAS position, confirms our analysis",
            "New prediction market listings on hotspot countries.fresh liquidity = fresh edge",
        ]
        if trader_info_gaps:
            gap_countries = set()
            for g in trader_info_gaps:
                gap_countries.update(g.get("countries", []))
            if gap_countries:
                watch_for.append(f"Breaking news from {', '.join(list(gap_countries)[:4])}.fills information gaps and may move markets sharply")

        assessments.append({
            "title": f"Market Intelligence: {trader_intel.get('edges_found', 0)} edges across {len(edge_countries)} countries, top edge {top_edges[0].get('edge', 0):.1f}pp",
            "category": "market_intelligence",
            "analysis": " ".join(analysis_parts),
            "hypotheses": hypotheses,
            "watch_for": watch_for,
            "confidence": min(85, 50 + trader_intel.get("edges_found", 0) * 2 + len(trader_hotspots) * 3),
            "sources_used": ["paper_trader", "polymarket", "manifold", "metaculus", "gdelt", "reddit"],
            "time_horizon": "1-7d",
            "business_angle": "Market intelligence reveals global stress patterns. Countries with high market attention = news-cycle-driven anxiety = businesses more receptive to 'protect your revenue' pitch.",
            "trader_data": {
                "top_edges": top_edges,
                "hotspots": trader_hotspots[:5],
                "sentiment": trader_sentiment,
                "info_gaps": len(trader_info_gaps),
                "divergences": len(trader_divergences),
            },
        })

    biz_angle_defaults = {
        "security": "Military/security events create uncertainty.businesses freeze hiring and expand automation. Position BOSS as the stable, cost-cutting option.",
        "economic": "Economic shifts change contractor behavior. Track which direction and adjust pitch: cost savings (downturn) or growth enablement (upturn).",
        "environmental": "Natural events drive emergency service demand spikes. Contractors get overwhelmed with calls.exactly when they need BOSS most.",
        "geopolitical": "Geopolitical shifts affect trade, supply chains, and business confidence. Monitor for ripple effects reaching US small business sector.",
        "market_intelligence": "Prediction market edges reveal where the world is most uncertain. Use hotspot intel to time outreach campaigns.",
    }
    missing_set = set(sp.get("missing", []))
    for a in assessments:
        a["date"] = now_iso
        if "hypotheses" not in a:
            a["hypotheses"] = []
        if "watch_for" not in a:
            a["watch_for"] = []
        if not a.get("business_angle"):
            a["business_angle"] = biz_angle_defaults.get(a.get("category", ""), "Monitor for downstream business impact on BOSS target markets.")

        # Degrade confidence when listed sources didn't return data
        sources_used = a.get("sources_used", [])
        phantom_sources = [s for s in sources_used if s in missing_set]
        if phantom_sources:
            penalty = len(phantom_sources) * 12
            a["confidence"] = max(10, a.get("confidence", 50) - penalty)
            a["sources_used"] = [s for s in sources_used if s not in missing_set]
            a["sources_degraded"] = phantom_sources

    assessments.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return assessments


# ---------------------------------------------------------------------------
# Business Opportunity Detection
# ---------------------------------------------------------------------------

def detect_opportunities(data: dict, assessments: list) -> List[Dict]:
    """Identify actionable business opportunities from intelligence."""
    opportunities = []

    weather = data.get("noaa", [])
    reddit = data.get("reddit", [])
    global_wx = data.get("global_weather", [])
    commodities = data.get("commodities", [])
    rss = data.get("rss", [])
    hn = data.get("hackernews", [])

    # Weather-driven immediate opportunities
    for alert in weather:
        event = (alert.get("event") or "").lower()
        area = alert.get("area", "Unknown")
        if "heat" in event or "excessive" in event:
            opportunities.append({
                "opportunity": f"HVAC contractors overwhelmed in {area}. Heat emergency",
                "category": "weather_demand",
                "region": area,
                "urgency": "immediate",
                "potential_revenue": "$250-500 setup fees",
                "action": f"Target HVAC businesses in {area} with missed-call pitch. They're too busy to answer right now.",
                "evidence": [f"NOAA: {alert.get('event', '')} warning active"],
                "confidence": 90,
            })
        elif any(k in event for k in ["tornado", "hurricane", "hail"]):
            opportunities.append({
                "opportunity": f"Storm damage creating roofer/restoration demand in {area}",
                "category": "disaster_response",
                "region": area,
                "urgency": "immediate",
                "potential_revenue": "$250-1000 per restoration company",
                "action": f"Contact roofers and restoration companies in {area} within 24 hours of storm.",
                "evidence": [f"NOAA: {alert.get('event', '')} warning"],
                "confidence": 85,
            })

    # Reddit pain signals → direct prospects
    pain_keywords = ["missed call", "voicemail", "no answer", "receptionist", "answering service",
                     "phone system", "can't reach", "lost customer"]
    service_subs = {"HVAC", "Plumbing", "electricians", "Roofing", "lawncare",
                    "AutoRepair", "contractors", "smallbusiness"}
    for post in reddit:
        title = (post.get("title") or "").lower()
        sub = (post.get("subreddit") or "").replace("r/", "")
        if sub in service_subs and any(k in title for k in pain_keywords):
            opportunities.append({
                "opportunity": f"Active pain signal in r/{sub}: '{post.get('title', '')[:60]}'",
                "category": "market_gap",
                "region": f"r/{sub} community",
                "urgency": "this_week",
                "potential_revenue": "$50/mo per converted reader",
                "action": "This post's commenters are potential customers. Note the pain and use in cold caller script.",
                "evidence": [f"Reddit: {post.get('url', '')}"],
                "confidence": 75,
            })

    # AI trend opportunities
    ai_trend_signals = []
    for item in hn + rss:
        title = (item.get("title") or "").lower()
        if any(k in title for k in ["small business ai", "ai for business", "ai answering", "ai receptionist",
                                     "ai phone", "voice ai", "ai customer service"]):
            ai_trend_signals.append(item)
    if ai_trend_signals:
        opportunities.append({
            "opportunity": f"AI adoption trend: {len(ai_trend_signals)} articles about AI for business",
            "category": "trend",
            "region": "National",
            "urgency": "this_month",
            "potential_revenue": "Market expansion.more businesses searching for AI solutions",
            "action": "Monitor these articles for competitor positioning. Use trending topics in content marketing.",
            "evidence": [f"{s.get('title', '')[:60]}" for s in ai_trend_signals[:3]],
            "confidence": 70,
        })

    # Competitor failure opportunities
    for item in rss + hn:
        title = (item.get("title") or "").lower()
        if any(k in title for k in ["shutdown", "layoff", "bankrupt", "closing down", "discontinu"]):
            if any(k in title for k in ["ai", "saas", "startup", "tech"]):
                opportunities.append({
                    "opportunity": f"Competitor/adjacent company failure: {item.get('title', '')[:60]}",
                    "category": "competitor_failure",
                    "region": "National",
                    "urgency": "this_week",
                    "potential_revenue": "Displaced customers available",
                    "action": "Check if this company served small businesses. Their customers need alternatives.",
                    "evidence": [item.get("url", "")],
                    "confidence": 60,
                })

    # Commodity price impacts on service businesses
    for commodity in commodities:
        if commodity.get("symbol") == "NG=F" and commodity.get("change_pct", 0) > 5:
            opportunities.append({
                "opportunity": f"Natural gas spike ({commodity['change_pct']:+.1f}%).HVAC costs rising",
                "category": "supply_chain",
                "region": "National",
                "urgency": "this_month",
                "potential_revenue": "HVAC businesses feeling margin pressure = more receptive to efficiency tools",
                "action": "Adjust HVAC pitch: 'Your costs are going up. Every missed call costs you more than ever.'",
                "evidence": [f"Natural gas at ${commodity['price']:.2f}, up {commodity['change_pct']:.1f}%"],
                "confidence": 65,
            })

    # Global extreme weather → international opportunity
    for wx in global_wx:
        if wx.get("extreme"):
            opportunities.append({
                "opportunity": f"Extreme weather in {wx['city']} ({wx['region']}). Service demand spike",
                "category": "weather_demand",
                "region": f"{wx['city']}, {wx['region']}",
                "urgency": "emerging",
                "potential_revenue": "International market signal.future expansion indicator",
                "action": f"Track {wx['city']} service sector response. International BOSS expansion target if pattern holds.",
                "evidence": [f"Open-Meteo: temp={wx.get('temp_c')}°C, wind={wx.get('wind_kmh')}km/h"],
                "confidence": 40,
            })

    # FEMA disaster declarations → immediate service demand
    fema = data.get("fema", [])
    for dec in fema:
        if dec.get("in_boss_territory"):
            inc_type = dec.get("type", "")
            state = dec.get("state", "")
            county = dec.get("county", "Statewide")
            urgency = "immediate"
            if any(t in inc_type.lower() for t in ["hurricane", "tornado", "severe storm", "flood"]):
                opportunities.append({
                    "opportunity": f"FEMA Disaster: {inc_type} in {county}, {state}. Contractors overwhelmed",
                    "category": "fema_disaster",
                    "region": f"{county}, {state}",
                    "urgency": urgency,
                    "potential_revenue": "$500-2000/week per contractor signed during disaster recovery",
                    "action": f"Target roofers, restoration, HVAC, plumbers in {state} immediately. They're drowning in calls.",
                    "evidence": [f"FEMA Declaration #{dec.get('fema_id', '?')}: {inc_type}"],
                    "confidence": 92,
                })
            elif "fire" in inc_type.lower():
                opportunities.append({
                    "opportunity": f"FEMA Wildfire: {county}, {state}. Restoration demand incoming",
                    "category": "fema_disaster",
                    "region": f"{county}, {state}",
                    "urgency": "this_week",
                    "potential_revenue": "$500-1500 per restoration company",
                    "action": f"Post-fire restoration contractors in {state} will be slammed. Pitch now before they're underwater.",
                    "evidence": [f"FEMA Declaration #{dec.get('fema_id', '?')}: {inc_type}"],
                    "confidence": 80,
                })

    # SEC insider trades → market movement signals
    sec = data.get("sec_edgar", [])
    insider_sells = [s for s in sec if s.get("filing_type") == "Form 4 (Insider Trade)" and "sale" in (s.get("title", "")).lower()]
    if len(insider_sells) >= 5:
        opportunities.append({
            "opportunity": f"Insider selling cluster: {len(insider_sells)} Form 4 sales filings detected",
            "category": "insider_signals",
            "region": "National",
            "urgency": "this_week",
            "potential_revenue": "Market correction signal.defensive positioning opportunity",
            "action": "High insider selling = potential market turbulence. Small businesses tighten budgets → harder sales but more pain-driven buyers.",
            "evidence": [f"SEC EDGAR: {s.get('title', '')[:60]}" for s in insider_sells[:3]],
            "confidence": 55,
        })

    # Currency shock → trade/import implications
    currencies = data.get("currencies", [])
    for curr in currencies:
        if curr.get("shock"):
            direction = "strengthened" if curr["change_pct"] < 0 else "weakened"
            opportunities.append({
                "opportunity": f"{curr['name']} ({curr['currency']}) {direction} {abs(curr['change_pct']):.1f}% vs USD",
                "category": "currency_shock",
                "region": "International",
                "urgency": "this_week",
                "potential_revenue": "Supply chain cost shift.impacts contractor material pricing",
                "action": f"Monitor import costs for building materials. {curr['name']} move may shift contractor margins.",
                "evidence": [f"Rate: {curr['rate_per_usd']:.2f}/{curr['currency']}, change: {curr['change_pct']:+.1f}%"],
                "confidence": 50,
            })

    # Treasury yield inversion → recession signal for business strategy
    treasury = data.get("treasury", [])
    yields_by_maturity = {t.get("maturity"): t.get("yield_pct", 0) for t in treasury}
    y2 = yields_by_maturity.get("2year", 0)
    y10 = yields_by_maturity.get("10year", 0)
    if y2 and y10 and y2 > y10:
        spread = round(y10 - y2, 2)
        opportunities.append({
            "opportunity": f"Yield curve inverted ({spread}%). Recession indicator active",
            "category": "recession_signal",
            "region": "National",
            "urgency": "this_month",
            "potential_revenue": "Recession = businesses cut staff before cutting AI tools. Pitch cost savings harder.",
            "action": "Shift sales pitch to cost-cutting angle: 'Replace a $3,000/mo receptionist with $50/mo AI.'",
            "evidence": [f"2Y yield: {y2}%, 10Y yield: {y10}%, spread: {spread}%"],
            "confidence": 70,
        })

    # Assessment-driven opportunities.use the intelligence we already synthesized
    for assess in assessments:
        biz_angle = assess.get("business_angle", "")
        if not biz_angle or len(biz_angle) < 20:
            continue
        cat = assess.get("category", "")
        conf = assess.get("confidence", 0)
        if conf < 60:
            continue
        if cat == "market_opportunity" and not any(o.get("category") == "weather_demand" for o in opportunities):
            opportunities.append({
                "opportunity": assess.get("title", "Assessment-derived opportunity"),
                "category": "assessment_derived",
                "region": "BOSS Territory",
                "urgency": "this_week" if conf >= 80 else "this_month",
                "potential_revenue": "Derived from cross-source intelligence fusion",
                "action": biz_angle,
                "evidence": assess.get("sources_used", []),
                "confidence": min(conf, 85),
            })

    # Alpha Vantage market sentiment → business climate
    av = data.get("alpha_vantage", [])
    bearish_news = [a for a in av if a.get("type") == "news_sentiment" and a.get("sentiment") == "Bearish"]
    if len(bearish_news) >= 4:
        opportunities.append({
            "opportunity": f"Market sentiment turning bearish.{len(bearish_news)} negative news signals",
            "category": "market_sentiment",
            "region": "National",
            "urgency": "this_month",
            "potential_revenue": "Bearish markets → businesses seek cost reduction → AI receptionist pitch stronger",
            "action": "Lead with ROI and cost-cutting in all pitches. Businesses are scared of spending.",
            "evidence": [f"{n.get('title', '')[:50]}" for n in bearish_news[:3]],
            "confidence": 60,
        })

    now_iso = datetime.now(timezone.utc).isoformat()
    for o in opportunities:
        o["date"] = now_iso

    # Sort by confidence then urgency
    urgency_order = {"immediate": 0, "this_week": 1, "this_month": 2, "emerging": 3}
    opportunities.sort(key=lambda x: (-x.get("confidence", 0), urgency_order.get(x.get("urgency", "emerging"), 3)))
    return opportunities[:25]


# ---------------------------------------------------------------------------
# ATLAS Headlines.Original Synthesized Intelligence
# ---------------------------------------------------------------------------

def _headline_hash(text):
    return hashlib.md5(text.strip().lower()[:100].encode()).hexdigest()[:12]

def generate_headlines(data: dict, anomalies: list, claims: list, assessments: list) -> List[Dict]:
    """Generate headlines from fused assessments. Preserves original dates
    for items that appeared in previous scans to prevent dashboard repeats."""
    headlines = []
    now_iso = datetime.now(timezone.utc).isoformat()

    # Load previous headlines to preserve original dates for repeat content
    prev_dates = {}
    if PREV_REPORT_PATH.exists():
        try:
            prev = json.loads(PREV_REPORT_PATH.read_text(encoding="utf-8"))
            for h in prev.get("headlines", []):
                key = _headline_hash(h.get("headline", ""))
                if h.get("date"):
                    prev_dates[key] = h["date"]
        except (json.JSONDecodeError, OSError):
            pass

    for assess in assessments:
        title = assess.get("title", "")
        category = assess.get("category", "other")
        hypotheses = assess.get("hypotheses", [])
        confidence = assess.get("confidence", 0)
        if confidence < 50:
            continue

        top_hypothesis = hypotheses[0] if hypotheses else ""
        headline_text = title
        if top_hypothesis and "HYPOTHESIS" not in top_hypothesis:
            headline_text = f"{title}. {top_hypothesis[:80]}"

        analysis = assess.get("analysis", "")[:400]
        if hypotheses:
            analysis += " Competing views. " + " vs ".join(h[:100] for h in hypotheses[:2])

        hkey = _headline_hash(headline_text)
        item_date = prev_dates.get(hkey, now_iso)

        headlines.append({
            "headline": headline_text[:150],
            "category": category,
            "analysis": analysis,
            "sources": assess.get("sources_used", []),
            "confidence": confidence,
            "watch_for": assess.get("watch_for", []),
            "business_angle": assess.get("business_angle", ""),
            "date": item_date,
        })

    assessment_text = " ".join(a.get("analysis", "") for a in assessments).lower()
    seen_anomaly_patterns = set()
    for anomaly in anomalies[:5]:
        score = anomaly.get("score", 0)
        if score < 60:
            continue
        desc = anomaly.get("description", "")
        pattern = anomaly.get("pattern", "")
        dedup_key = f"{pattern}:{desc[:30]}"
        if dedup_key in seen_anomaly_patterns:
            continue
        seen_anomaly_patterns.add(dedup_key)
        if desc[:30].lower() in assessment_text:
            continue
        assessment_data = anomaly.get("assessment", "")
        if isinstance(assessment_data, dict):
            assessment_data = assessment_data.get("summary", str(assessment_data)[:120])

        headline_text = f"ANOMALY [{score}]. {desc[:120]}"
        hkey = _headline_hash(headline_text)
        item_date = prev_dates.get(hkey, now_iso)

        headlines.append({
            "headline": headline_text,
            "category": "security",
            "analysis": f"Pattern: {anomaly.get('pattern', '?')}. {str(assessment_data)[:200]}",
            "sources": ["anomaly_engine"],
            "confidence": score,
            "business_angle": "Anomalous events create uncertainty. Track for downstream impacts on BOSS target markets and supply chains.",
            "date": item_date,
        })

    cat_priority = {"security": 0, "geopolitical": 1, "market_opportunity": 2, "economic": 3, "environmental": 4, "technology": 5}
    headlines.sort(key=lambda x: (-x.get("confidence", 0), cat_priority.get(x.get("category", ""), 6)))

    return headlines[:12]


# ---------------------------------------------------------------------------
# ATLAS Predictions.Original Probability Estimates
# ---------------------------------------------------------------------------

def generate_atlas_predictions(data: dict, anomalies: list, assessments: list) -> List[Dict]:
    """Generate ATLAS's own predictions with reasoning, using calibrated weights."""
    predictions = []
    now_iso = datetime.now(timezone.utc).isoformat()
    w = load_calibrated_weights()

    poly = data.get("polymarket", [])
    manifold = data.get("manifold", [])
    gdelt = data.get("gdelt", [])
    weather = data.get("noaa", [])
    quakes = data.get("usgs", [])
    adsb = data.get("adsb", [])
    commodities = data.get("commodities", [])
    fred = data.get("fred", [])

    conflict_count = len([g for g in gdelt if g.get("category") == "conflict"])
    mil_aircraft = len(adsb)
    fred_shocks = [f for f in fred if f.get("shock")]
    oil = [c for c in commodities if c.get("symbol") == "CL=F"]
    oil_pct = oil[0].get("change_pct", 0) if oil else 0

    # Load trader intel for cross-reference
    trader_intel = load_previous_report().get("trader_intel", {})
    if not trader_intel and REPORT_PATH.exists():
        try:
            trader_intel = json.loads(REPORT_PATH.read_text(encoding="utf-8")).get("trader_intel", {})
        except (json.JSONDecodeError, OSError):
            pass
    trader_consensus = {m.get("question", "")[:50].lower(): m for m in trader_intel.get("market_consensus", [])}
    trader_sentiment = trader_intel.get("sentiment_map", {})
    trader_momentum = trader_intel.get("momentum", {})

    SPORTS_SKIP = ["fifa", "world cup", "premier league", "champions league",
                    "nba", "nfl", "mlb", "nhl", "serie a", "la liga", "bundesliga",
                    "super bowl", "olympics", "tennis", "boxing", "ufc", "mma",
                    "cricket", "f1", "formula 1", "grand prix", "team to advance",
                    "copa america", "euros 2026", "win the"]

    for market in poly[:20]:
        question = market.get("question", "")
        market_prob = market.get("probability", 50)
        q_lower = question.lower()

        if any(s in q_lower for s in SPORTS_SKIP):
            continue

        atlas_prob = market_prob
        reasoning_parts = []
        sources_used = ["polymarket"]
        confidence = "medium"

        # Check if the deep trader already researched this question
        trader_match = trader_consensus.get(q_lower[:50])
        if trader_match and trader_match.get("confidence") in ("high", "medium"):
            trader_prob = trader_match.get("atlas_prob", market_prob)
            trader_edge = trader_match.get("edge", 0)
            if trader_edge >= 3:
                atlas_prob = trader_prob
                reasoning_parts.append(f"Deep research: {trader_edge:.1f}pp edge (confidence: {trader_match.get('confidence')})")
                sources_used.append("paper_trader")
                confidence = trader_match.get("confidence", "medium")

        # Apply sentiment momentum from trader if applicable
        for topic_key, sent_score in trader_sentiment.items():
            if topic_key in q_lower and abs(sent_score) > 0.2:
                sent_adj = sent_score * 2
                atlas_prob = max(1, min(99, atlas_prob + sent_adj))
                reasoning_parts.append(f"Trader sentiment on '{topic_key}': {sent_score:+.2f}")
                sources_used.append("reddit")

        if any(k in q_lower for k in ["war", "invasion", "attack", "military", "conflict", "ceasefire", "peace"]):
            if conflict_count > w.get("gdelt_conflict_high_threshold", 15):
                atlas_prob = min(99, market_prob + w.get("gdelt_conflict_high_adjust", 12))
                reasoning_parts.append(f"GDELT tracking {conflict_count} conflict articles (elevated)")
                sources_used.append("gdelt")
            elif conflict_count < 3:
                atlas_prob = max(1, market_prob + w.get("gdelt_conflict_low_adjust", 0))
                reasoning_parts.append(f"GDELT conflict reporting low ({conflict_count} articles)")
                sources_used.append("gdelt")
            if mil_aircraft > w.get("adsb_high_threshold", 40):
                atlas_prob = min(99, atlas_prob + w.get("adsb_high_adjust", 12))
                reasoning_parts.append(f"{mil_aircraft} military aircraft on ADS-B (high activity)")
                sources_used.append("adsb")
            elif mil_aircraft > w.get("adsb_moderate_threshold", 20):
                atlas_prob = min(99, atlas_prob + w.get("adsb_moderate_adjust", 3))
                reasoning_parts.append(f"{mil_aircraft} military aircraft on ADS-B")
                sources_used.append("adsb")
            confidence = "medium" if abs(atlas_prob - market_prob) < 10 else "high"

        elif any(k in q_lower for k in ["recession", "inflation", "gdp", "fed", "interest rate", "unemployment", "economy"]):
            if fred_shocks:
                atlas_prob = min(99, market_prob + len(fred_shocks) * w.get("fred_shock_adjust_per", 4))
                reasoning_parts.append(f"{len(fred_shocks)} FRED economic shock indicators")
                sources_used.append("fred")
            if oil and abs(oil_pct) > w.get("oil_significant_threshold", 3):
                dir_word = "rising" if oil_pct > 0 else "falling"
                if oil_pct > 0 and "inflation" in q_lower:
                    atlas_prob = min(99, atlas_prob + w.get("oil_inflation_adjust", 3))
                reasoning_parts.append(f"Oil {dir_word} {abs(oil_pct):.1f}%")
                sources_used.append("commodities")
            confidence = "medium"

        elif any(k in q_lower for k in ["earthquake", "hurricane", "flood", "wildfire", "disaster", "tsunami"]):
            severe = [wx for wx in weather if wx.get("severity") in ("Extreme", "Severe")]
            big_quakes = [q for q in quakes if q.get("magnitude", 0) >= 5.0]
            if len(severe) > w.get("wx_major_threshold", 10):
                atlas_prob = min(99, market_prob + w.get("wx_major_adjust", 5))
                reasoning_parts.append(f"{len(severe)} severe/extreme weather alerts (major)")
                sources_used.append("noaa")
            elif severe:
                atlas_prob = min(99, market_prob + len(severe) * w.get("wx_moderate_adjust_per", 1))
                reasoning_parts.append(f"{len(severe)} severe/extreme weather alerts active")
                sources_used.append("noaa")
            if big_quakes:
                atlas_prob = min(99, atlas_prob + len(big_quakes) * w.get("quake_adjust_per", 3))
                reasoning_parts.append(f"{len(big_quakes)} significant quakes (M5.0+)")
                sources_used.append("usgs")
            confidence = "medium"

        elif any(k in q_lower for k in ["ai ", "artificial intelligence", "openai", "google", "gpt", "agi"]):
            reasoning_parts.append("ATLAS tracking AI developments across HN, RSS, Reddit")
            sources_used.extend(["hackernews", "rss"])
            confidence = "low"

        elif any(k in q_lower for k in ["election", "president", "trump", "biden", "vote", "poll"]):
            reasoning_parts.append("Political prediction.ATLAS defers to market consensus (limited direct data)")
            confidence = "low"

        if not reasoning_parts:
            mr_90 = w.get("mean_revert_90_plus", 2)
            mr_80 = w.get("mean_revert_80_plus", 1)
            mr_10 = w.get("mean_revert_10_minus", 2)
            mr_20 = w.get("mean_revert_20_minus", 1)
            if market_prob > 90:
                atlas_prob = market_prob - mr_90
                reasoning_parts.append("Extreme high.calibrated reversion applied")
            elif market_prob > 80:
                atlas_prob = market_prob - mr_80
                reasoning_parts.append("High confidence.calibrated reversion applied")
            elif market_prob < 10:
                atlas_prob = market_prob + mr_10
                reasoning_parts.append("Extreme low.calibrated reversion applied")
            elif market_prob < 20:
                atlas_prob = market_prob + mr_20
                reasoning_parts.append("Low confidence.calibrated reversion applied")
            else:
                reasoning_parts.append("No direct source data contradicts market consensus")
            confidence = "low"

        atlas_prob = max(1, min(99, round(atlas_prob)))
        divergence = atlas_prob - market_prob

        predictions.append({
            "question": question[:200],
            "atlas_probability": atlas_prob,
            "market_probability": market_prob,
            "divergence": round(divergence, 1),
            "atlas_reasoning": ". ".join(reasoning_parts) + ".",
            "confidence": confidence,
            "sources_used": list(set(sources_used)),
            "market_source": "polymarket",
            "category": _categorize_question(q_lower),
            "url": market.get("url", ""),
            "date": now_iso,
        })

    # Also generate from Manifold for coverage
    seen_questions = set(p["question"].lower()[:50] for p in predictions)
    for market in manifold[:10]:
        question = market.get("question", "")
        if question.lower()[:50] in seen_questions:
            continue
        market_prob = market.get("probability", 50)
        predictions.append({
            "question": question[:200],
            "atlas_probability": market_prob,
            "market_probability": market_prob,
            "divergence": 0,
            "atlas_reasoning": "Manifold market.ATLAS tracking, no divergence signal from source data.",
            "confidence": "low",
            "sources_used": ["manifold"],
            "market_source": "manifold",
            "category": _categorize_question(question.lower()),
            "url": market.get("url", ""),
            "date": now_iso,
        })

    # Sort: highest divergence (edges) first
    predictions.sort(key=lambda x: abs(x.get("divergence", 0)), reverse=True)
    return predictions[:30]


def _categorize_question(q: str) -> str:
    if any(k in q for k in ["war", "conflict", "military", "invasion", "ceasefire", "nato"]):
        return "geopolitical"
    if any(k in q for k in ["recession", "inflation", "gdp", "fed", "rate", "economy", "market", "stock"]):
        return "economic"
    if any(k in q for k in ["earthquake", "hurricane", "flood", "disaster", "climate", "weather"]):
        return "environmental"
    if any(k in q for k in ["ai ", "openai", "google", "tech", "gpt", "agi", "robot"]):
        return "technology"
    if any(k in q for k in ["election", "president", "vote", "trump", "biden", "congress", "senate"]):
        return "political"
    return "other"


# ---------------------------------------------------------------------------
# Anomaly Engine
# ---------------------------------------------------------------------------

def detect_anomalies(data: dict) -> List[Dict]:
    """Cross-correlate sources to find observable-but-unreported activity."""
    anomalies = []

    adsb = data.get("adsb", [])
    gdelt = data.get("gdelt", [])
    ioda = data.get("ioda", [])
    wikipedia = data.get("wikipedia", [])
    fred = data.get("fred", [])
    usgs = data.get("usgs", [])
    noaa = data.get("noaa", [])
    acled = data.get("acled", [])
    safecast = data.get("safecast", [])

    # Pattern 1: Military air activity with no corresponding news
    if adsb:
        # Group aircraft by rough region (10-degree grid)
        grid = {}
        for ac in adsb:
            lat, lon = ac.get("lat", 0), ac.get("lon", 0)
            key = (round(lat / 10) * 10, round(lon / 10) * 10)
            grid.setdefault(key, []).append(ac)

        for (glat, glon), aircraft in grid.items():
            if len(aircraft) >= 5:
                # Check if any GDELT news covers this region
                region_news = [g for g in gdelt if _near(g, glat, glon, 15)]
                if len(region_news) < 2:
                    top_types = {}
                    for ac in aircraft:
                        t = ac.get("type", "unknown")
                        top_types[t] = top_types.get(t, 0) + 1
                    anomalies.append({
                        "pattern": "mil_air_no_news",
                        "score": min(95, 40 + len(aircraft) * 5),
                        "description": f"{len(aircraft)} military aircraft near ({glat},{glon}) with minimal news coverage",
                        "aircraft_types": top_types,
                        "lat": glat,
                        "lon": glon,
                        "evidence_count": len(aircraft),
                        "news_count": len(region_news),
                    })

    # Pattern 2: Internet blackout + conflict indicators
    if ioda:
        for outage in ioda:
            country = outage.get("country", "")
            drop = outage.get("drop_percent", 0)
            # Check for conflict in same country
            country_conflict = [a for a in acled if a.get("country", "").lower() == outage.get("country_name", "").lower()]
            country_gdelt = [g for g in gdelt if g.get("country", "").upper() == country.upper()]
            if drop > 30:
                score = min(95, 40 + int(drop))
                if country_conflict:
                    score = min(98, score + 15)
                anomalies.append({
                    "pattern": "blackout_conflict",
                    "score": score,
                    "description": f"{outage.get('country_name', country)}: {drop}% internet drop" +
                                   (f" + {len(country_conflict)} conflict events" if country_conflict else ""),
                    "country": country,
                    "drop_percent": drop,
                    "conflict_events": len(country_conflict),
                    "news_articles": len(country_gdelt),
                })

    # Pattern 3: Wikipedia edit storms (coordinated editing)
    edit_storms = [w for w in wikipedia if w.get("flag") == "edit_storm"]
    for storm in edit_storms:
        title = storm.get("title", "").replace("EDIT STORM: ", "")
        # Check if this topic appears in news
        topic_news = [g for g in gdelt if title.lower() in g.get("title", "").lower()]
        score = min(90, 30 + storm.get("edit_count", 0) * 10)
        if not topic_news:
            score += 15  # More anomalous if no news covers it
        anomalies.append({
            "pattern": "wiki_storm",
            "score": min(95, score),
            "description": f"Wikipedia edit storm on '{title}' ({storm.get('edit_count', 0)} edits)" +
                           (f".{'no' if not topic_news else len(topic_news)} matching news articles" if True else ""),
            "article": title,
            "edit_count": storm.get("edit_count", 0),
            "news_coverage": len(topic_news),
        })

    # Pattern 4: Economic shock indicators
    for indicator in fred:
        if indicator.get("shock"):
            anomalies.append({
                "pattern": "economic_shock",
                "score": min(85, 50 + abs(int(indicator.get("pct_change", 0)))),
                "description": f"{indicator['indicator']}: {indicator['pct_change']}% change ({indicator['value']} from {indicator['previous']})",
                "indicator": indicator.get("series_id", ""),
                "change": indicator.get("pct_change", 0),
            })

    # Pattern 5: Major seismic + no news (only big quakes or strategic locations)
    major_quakes = [q for q in usgs if q.get("magnitude", 0) >= 6.0]
    for quake in major_quakes:
        coords = quake.get("coordinates", [])
        if coords and len(coords) >= 2:
            lat, lon = coords[1], coords[0]
            nearby_news = [g for g in gdelt if _near(g, lat, lon, 10)]
            if len(nearby_news) < 3:
                anomalies.append({
                    "pattern": "seismic_major",
                    "score": min(95, 50 + int(quake["magnitude"] * 8)),
                    "description": f"M{quake['magnitude']} earthquake at {quake.get('place', '?')}.only {len(nearby_news)} news articles",
                    "magnitude": quake["magnitude"],
                    "place": quake.get("place", ""),
                    "lat": lat,
                    "lon": lon,
                    "news_count": len(nearby_news),
                })

    # Pattern 6: Elevated radiation readings
    elevated = [s for s in safecast if s.get("elevated")]
    if elevated:
        anomalies.append({
            "pattern": "radiation_elevated",
            "score": min(90, 50 + len(elevated) * 10),
            "description": f"{len(elevated)} elevated radiation readings detected (>350 CPM)",
            "readings": len(elevated),
            "max_cpm": max(s.get("cpm", 0) for s in elevated),
        })

    now_iso = datetime.now(timezone.utc).isoformat()
    for a in anomalies:
        if "date" not in a:
            a["date"] = a.get("timestamp", now_iso)

    anomalies.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Enrich anomalies with geopolitical assessments
    if HAS_INTEL:
        for anomaly in anomalies:
            try:
                anomaly["assessment"] = assess_anomaly(anomaly, data)
                nearby = []
                if anomaly.get("lat") is not None and anomaly.get("lon") is not None:
                    anomaly["nearby_bases"] = find_nearby_bases(anomaly["lat"], anomaly["lon"])
                    anomaly["nearby_chokepoints"] = find_nearby_chokepoints(anomaly["lat"], anomaly["lon"])
                    anomaly["nearby_conflicts"] = find_nearby_conflict_zones(anomaly["lat"], anomaly["lon"])
                    anomaly["nearby_nuclear"] = find_nearby_nuclear_sites(anomaly["lat"], anomaly["lon"])
            except Exception as e:
                log.warning("Assessment failed for anomaly: %s", e)

    return anomalies


def _near(item: dict, lat: float, lon: float, radius_deg: float) -> bool:
    """Check if a GDELT article's source country centroid is near coordinates."""
    if not HAS_INTEL:
        return False
    country = item.get("country", "")
    if not country or len(country) != 2:
        return False
    centroid = get_country_centroid(country.upper())
    if not centroid:
        return False
    dist = haversine(lat, lon, centroid[0], centroid[1])
    return dist < (radius_deg * 111)

# ---------------------------------------------------------------------------
# Claims Tracker
# ---------------------------------------------------------------------------

def build_claims(data: dict) -> List[Dict]:
    """Track claims across sources.never declare true/false, show all evidence."""
    claims = []
    gdelt = data.get("gdelt", [])
    reddit = data.get("reddit", [])
    predictions = data.get("predictions", {})

    # Group articles by topic similarity (crude: shared keywords)
    topic_groups = {}
    for article in gdelt:
        title = article.get("title", "").lower()
        words = set(title.split())
        matched = False
        for topic_key in list(topic_groups.keys()):
            topic_words = set(topic_key.split())
            overlap = len(words & topic_words)
            if overlap >= 3:
                topic_groups[topic_key].append(article)
                matched = True
                break
        if not matched and len(words) >= 3:
            key = " ".join(sorted(list(words)[:5]))
            topic_groups[key] = [article]

    # Find claims with velocity (multiple sources in short time)
    for topic_key, articles in topic_groups.items():
        if len(articles) < 3:
            continue

        # Count sources
        sources = set()
        countries = set()
        tones = []
        for a in articles:
            sources.add(a.get("domain", ""))
            cc = a.get("country", "")
            if cc:
                countries.add(cc)
            t = a.get("tone", 0)
            if isinstance(t, (int, float)):
                tones.append(t)

        avg_tone = sum(tones) / len(tones) if tones else 0
        title = articles[0].get("title", "")[:150]

        # Check Reddit for corroboration
        reddit_mentions = 0
        title_words = set(title.lower().split())
        for post in reddit:
            post_words = set(post.get("title", "").lower().split())
            if len(title_words & post_words) >= 3:
                reddit_mentions += 1

        # Check prediction markets for related questions
        related_predictions = []
        poly = predictions.get("polymarket", [])
        for p in poly:
            pq_words = set(p.get("question", "").lower().split())
            if len(title_words & pq_words) >= 2:
                related_predictions.append({
                    "question": p.get("question", ""),
                    "probability": p.get("probability", 0),
                    "source": "polymarket",
                })

        claims.append({
            "claim": title,
            "velocity": len(articles),
            "unique_sources": len(sources),
            "countries_reporting": list(countries)[:10],
            "avg_tone": round(avg_tone, 2),
            "tone_label": "negative" if avg_tone < -3 else ("positive" if avg_tone > 3 else "neutral"),
            "reddit_mentions": reddit_mentions,
            "related_predictions": related_predictions,
            "first_seen": articles[-1].get("published", ""),
            "articles": [{"title": a.get("title", ""), "source": a.get("domain", ""), "url": a.get("url", "")} for a in articles[:5]],
        })

    claims.sort(key=lambda x: x.get("velocity", 0), reverse=True)
    return claims[:20]

# ---------------------------------------------------------------------------
# ntfy alert with dedup
# ---------------------------------------------------------------------------

ALERT_STATE_PATH = ATLAS_DIR / "alert_state.json"

def _load_alert_state():
    if ALERT_STATE_PATH.exists():
        try:
            return json.loads(ALERT_STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"sent_keys": {}, "last_cleanup": ""}

def _save_alert_state(state):
    try:
        atomic_write_json(ALERT_STATE_PATH, state)
    except Exception:
        pass

def _alert_key(text):
    return hashlib.md5(text.strip().lower()[:120].encode()).hexdigest()[:12]

def send_alert(report: dict):
    SKIP_PATTERNS = {"seismic_major"}

    anomalies = report.get("anomalies", [])
    assessments = report.get("assessments", [])
    headlines = report.get("headlines", [])
    opportunities = report.get("opportunities", [])
    pred_data = report.get("predictions", {})
    if isinstance(pred_data, dict):
        predictions = pred_data.get("atlas_predictions", [])
    elif isinstance(pred_data, list):
        predictions = pred_data
    else:
        predictions = []

    for a in anomalies:
        if a.get("pattern") == "mil_air_no_news":
            lat, lon = a.get("lat", 0), a.get("lon", 0)
            if HAS_INTEL and (find_nearby_conflict_zones(lat, lon, 400)
                              or find_nearby_chokepoints(lat, lon, 300)):
                a["pattern"] = "mil_air_conflict_zone"

    # --- Collect all intelligence worth sending ---

    # Anomalies: score >= 50 (lowered from 70)
    juicy = [a for a in anomalies
             if a.get("score", 0) >= 50
             and a.get("pattern", "") not in SKIP_PATTERNS]

    # Assessments: confidence >= 60, prioritize geopolitical/security/economic over business
    _cat_priority = {"security": 0, "geopolitical": 1, "economic": 2, "technology": 3,
                     "environmental": 4, "market_opportunity": 5, "market_intelligence": 6}
    strong_assessments = sorted(
        [a for a in assessments if a.get("confidence", 0) >= 60],
        key=lambda x: (_cat_priority.get(x.get("category", ""), 9), -x.get("confidence", 0)))

    # Predictions where ATLAS disagrees with markets: divergence >= 8
    divergences = [p for p in predictions
                   if isinstance(p, dict) and abs(p.get("divergence", 0)) >= 8
                   and p.get("confidence") in ("medium", "high")]

    # Breaking news detection
    BREAKING_KEYWORDS = [
        "iran attack", "iran strike", "iran bomb", "iran war",
        "israel strike", "israel attack", "israel bomb",
        "missile launch", "missile strike", "missiles fired",
        "nuclear test", "nuclear detonation",
        "war declared", "declaration of war",
        "invasion of", "invaded by", "troops cross border",
        "massive bombing", "carpet bombing", "air strike on",
        "naval blockade", "blockade of",
        "ceasefire broken", "ceasefire collapses", "ceasefire violated",
        "martial law declared", "state of emergency declared",
        "coup attempt", "coup underway", "military coup", "military takeover",
        "assassination of", "assassinated",
        "embassy attack", "embassy bombed",
        "nuclear facility attack", "nuclear plant",
        "strait of hormuz", "taiwan strait",
        "no-fly zone", "shoots down",
        "chemical weapon", "biological weapon", "gas attack",
    ]
    all_news = report.get("gdelt", []) + report.get("think_tanks", []) + report.get("rss", [])
    telegram_posts = report.get("telegram", [])

    breaking = []
    seen_titles = set()
    for article in all_news:
        title = (article.get("title") or "").lower()
        title_key = title[:60]
        if title_key in seen_titles:
            continue
        if any(kw in title for kw in BREAKING_KEYWORDS):
            seen_titles.add(title_key)
            breaking.append(article)

    telegram_breaking = [p for p in telegram_posts
                         if any(kw in (p.get("text") or "").lower() for kw in BREAKING_KEYWORDS)]

    futures_spikes = [f for f in report.get("futures", []) if abs(f.get("change_pct", 0)) >= 3.0]
    firms_alerts = [f for f in report.get("firms", []) if f.get("hotspot_count", 0) >= 10]

    # Congress/legislation activity
    congress_items = report.get("congress", [])[:3]

    # If there's literally nothing from any source, skip
    has_breaking = breaking or telegram_breaking or futures_spikes or firms_alerts
    has_intel = strong_assessments or divergences or juicy or headlines or congress_items
    if not has_breaking and not has_intel:
        return

    # --- Dedup against previous alerts (48h window) ---
    state = _load_alert_state()
    sent = state.get("sent_keys", {})
    now_iso = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    sent = {k: v for k, v in sent.items() if v > cutoff}

    def is_new(text):
        k = _alert_key(text)
        if k in sent:
            return False
        sent[k] = now_iso
        return True

    telegram_breaking = [t for t in telegram_breaking if is_new(t.get("text", ""))]
    breaking = [b for b in breaking if is_new(b.get("title", ""))]
    futures_spikes = [f for f in futures_spikes if is_new(f.get("name", "") + str(f.get("change_pct", 0)))]
    firms_alerts = [f for f in firms_alerts if is_new(f.get("region", "") + str(f.get("hotspot_count", 0)))]
    juicy = [a for a in juicy if is_new(a.get("description", ""))]
    divergences = [d for d in divergences if is_new(d.get("question", ""))]
    strong_assessments = [a for a in strong_assessments if is_new(a.get("title", ""))]
    headlines = [h for h in headlines if is_new(h.get("headline", ""))]
    congress_items = [c for c in congress_items if is_new(c.get("title", c.get("bill", "")))]

    state["sent_keys"] = sent
    state["last_cleanup"] = now_iso
    _save_alert_state(state)

    # After dedup, check if anything survived
    if not any([telegram_breaking, breaking, futures_spikes, firms_alerts,
                juicy, divergences, strong_assessments, headlines, congress_items]):
        return

    # --- Build intelligence brief ---
    lines = []

    # SECTION 1: Breaking (if any) — urgent stuff first
    if telegram_breaking:
        for t in telegram_breaking[:3]:
            lines.append(f"TELEGRAM ({t.get('channel', '?')}): {t.get('text', '')[:150]}")

    if breaking:
        for b in breaking[:3]:
            lines.append(f"BREAKING: {b.get('title', '')[:120]}")

    if futures_spikes:
        moves = ", ".join(f"{f['name']} {f['change_pct']:+.1f}%" for f in futures_spikes)
        lines.append(f"MARKETS MOVING: {moves}")

    if firms_alerts:
        for f in firms_alerts[:2]:
            lines.append(f"SATELLITE: {f['hotspot_count']} fire hotspots detected in {f['region']}")

    # SECTION 2: ATLAS assessments — the predictive analysis
    if strong_assessments:
        lines.append("")
        lines.append("WHAT ATLAS SEES DEVELOPING:")
        for a in strong_assessments[:4]:
            title = a.get("title", "")[:100]
            analysis = a.get("analysis", "")[:200]
            conf = a.get("confidence", 0)
            cat = a.get("category", "")
            watch = ""
            watch_list = a.get("watch_for", [])
            if watch_list and isinstance(watch_list, list):
                watch = f" Watch for: {watch_list[0][:80]}" if watch_list[0] else ""
            lines.append(f"[{cat.upper()} {conf}%] {title}")
            if analysis:
                lines.append(f"  {analysis}")
            if watch:
                lines.append(f"  {watch}")

    # SECTION 3: ATLAS vs prediction markets
    if divergences:
        lines.append("")
        lines.append("ATLAS DISAGREES WITH MARKETS:")
        for p in divergences[:4]:
            q = p.get("question", "")[:90]
            atlas_pct = p.get("atlas_probability", "?")
            market_pct = p.get("market_probability", "?")
            div = p.get("divergence", 0)
            reasoning = p.get("atlas_reasoning", "")[:120]
            lines.append(f"  {q}")
            lines.append(f"  ATLAS: {atlas_pct}% vs Market: {market_pct}% (gap: {div:+.0f})")
            if reasoning:
                lines.append(f"  Why: {reasoning}")

    # SECTION 4: Congress/legislation
    if congress_items:
        lines.append("")
        lines.append("CONGRESS:")
        for c in congress_items[:3]:
            bill = c.get("bill", c.get("title", ""))[:120]
            lines.append(f"  {bill}")

    # SECTION 5: Anomalies (skip earthquakes — already filtered by SKIP_PATTERNS but also filter text)
    non_seismic = [a for a in juicy if "earthquake" not in a.get("description", "").lower()
                   and "seismic" not in a.get("pattern", "")]
    if non_seismic:
        lines.append("")
        for a in non_seismic[:3]:
            lines.append(f"ANOMALY (score {a['score']}): {a.get('description', '')[:140]}")

    # SECTION 6: Headlines — filtered, no earthquake spam
    non_quake_headlines = [h for h in headlines
                           if "earthquake" not in h.get("headline", "").lower()
                           and "seismic" not in h.get("headline", "").lower()]
    if non_quake_headlines and not strong_assessments:
        lines.append("")
        lines.append("TOP INTEL:")
        for h in non_quake_headlines[:5]:
            lines.append(f"  {h.get('headline', '')[:120]}")

    body = "\n".join(lines).strip()

    is_urgent = bool(breaking or telegram_breaking or futures_spikes
                     or any(a.get("score", 0) >= 90 for a in juicy))
    priority = "urgent" if is_urgent else "high"

    total_items = sum(len(x) for x in [telegram_breaking, breaking, futures_spikes,
                                        firms_alerts, juicy, divergences, strong_assessments])
    if is_urgent:
        title = f"ATLAS URGENT: {total_items} items"
    else:
        title = f"ATLAS Intel Brief: {total_items} items"

    try:
        requests.post(
            f"{NTFY_BASE}/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={"Title": title, "Priority": priority},
            timeout=10,
        )
        log.info("Alert sent: %d items, priority=%s", total_items, priority)
    except requests.RequestException as e:
        log.warning("Alert send failed: %s", e)

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

def deploy_report():
    if not REPORT_PATH.exists():
        log.error("No report at %s", REPORT_PATH)
        sys.exit(1)
    if not GITHUB_TOKEN:
        log.error("GITHUB_TOKEN not set")
        sys.exit(1)

    # Inject paper trader data into report before deploying
    trades_path = ATLAS_DIR / "paper_trades.json"
    if trades_path.exists():
        try:
            report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            portfolio = json.loads(trades_path.read_text(encoding="utf-8"))
            report["paper_trader"] = {
                "balance": portfolio["balance"],
                "starting_balance": portfolio["starting_balance"],
                "total_pnl": portfolio["total_pnl"],
                "wins": portfolio["wins"],
                "losses": portfolio["losses"],
                "total_wagered": portfolio.get("total_wagered", 0),
                "total_bets_placed": portfolio["total_bets_placed"],
                "pending_count": len(portfolio["pending"]),
                "pending": portfolio["pending"][:20],
                "recent_resolved": [b for b in portfolio.get("resolved", [])
                                   if b.get("status") in ("won", "lost")][-10:],
                "last_scan": portfolio.get("last_scan"),
            }
            REPORT_PATH.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    content = REPORT_PATH.read_text(encoding="utf-8")
    encoded = base64.b64encode(content.encode()).decode()
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/atlas_report.json"

    sha = None
    try:
        r = requests.get(api_url, headers=headers, timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")
    except requests.RequestException:
        pass

    payload = {"message": "ATLAS v3 report update", "content": encoded, "branch": "main"}
    if sha:
        payload["sha"] = sha

    try:
        r = requests.put(api_url, headers=headers, json=payload, timeout=10)
        if r.status_code in (200, 201):
            log.info("Report deployed to GitHub")
        else:
            log.error("Deploy failed: %s", r.status_code)
    except requests.RequestException as e:
        log.error("Deploy failed: %s", e)

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def show_status():
    cfg = load_config()
    print("=" * 50)
    print("  ATLAS v3 Intelligence Engine")
    print("=" * 50)
    print(f"  Power:      {cfg.get('power_level', 'SLEEP')}")
    print(f"  Last Run:   {cfg.get('last_run', 'never')}")
    print(f"  Total Runs: {cfg.get('total_runs', 0)}")
    print(f"  Data Points:{cfg.get('total_data_points', 0)}")

    if REPORT_PATH.exists():
        try:
            rpt = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            print(f"\n  Latest Report:")
            print(f"    Generated:  {rpt.get('generated', '?')}")
            print(f"    Sources:    {rpt.get('sources_scanned', '?')}")
            print(f"    Data Points:{rpt.get('data_points', '?')}")
            anomalies = rpt.get("anomalies", [])
            claims = rpt.get("claims", [])
            print(f"    Anomalies:  {len(anomalies)}")
            print(f"    Claims:     {len(claims)}")
            if anomalies:
                top = anomalies[0]
                print(f"\n  Top Anomaly [{top.get('score', 0)}]: {top.get('description', '?')[:60]}")
        except (json.JSONDecodeError, OSError):
            pass
    print("=" * 50)

# ---------------------------------------------------------------------------
# Main Scan
# ---------------------------------------------------------------------------

def run_scan(power: str):
    lock_fd = acquire_scan_lock()
    if lock_fd is None:
        log.warning("Another scan is already running.skipping")
        return
    try:
        _run_scan_impl(power)
    finally:
        release_scan_lock(lock_fd)


def _apply_power_schedule(power: str) -> str:
    """Override power level based on time-of-day schedule.

    SURGE windows: 5:00-6:59 CT (6am window) and 17:00-18:59 CT (6pm window).
    All other times: ACTIVE.

    Updates both config.json copies so dashboard/status reflect the override.
    """
    try:
        ct_now = datetime.now(ZoneInfo("America/Chicago"))
    except Exception:
        # Fallback: UTC-6 (close enough if zoneinfo unavailable)
        ct_now = datetime.now(timezone(timedelta(hours=-6)))

    hour = ct_now.hour
    if hour in (5, 6) or hour in (17, 18):
        scheduled_power = "SURGE"
        reason = f"CT hour={hour} is within SURGE window (6am/6pm +/-1hr)"
    else:
        scheduled_power = "ACTIVE"
        reason = f"CT hour={hour} is outside SURGE windows.defaulting to ACTIVE"

    if scheduled_power != power:
        log.info("POWER SCHEDULE: overriding %s -> %s (%s)", power, scheduled_power, reason)
    else:
        log.info("POWER SCHEDULE: confirmed %s (%s)", scheduled_power, reason)

    # Update both config locations so dashboard/status commands reflect the override
    for cfg_path in [CONFIG_PATH, BOSS_HQ / "atlas_data" / "config.json"]:
        try:
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            else:
                cfg = dict(DEFAULT_CONFIG)
            cfg["power_level"] = scheduled_power
            atomic_write_json(cfg_path, cfg)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Could not update config at %s: %s", cfg_path, e)

    return scheduled_power


def _run_scan_impl(power: str):
    start = time.time()
    now = datetime.now(timezone.utc)

    # Apply time-based power schedule (SURGE at 6am/6pm CT, ACTIVE otherwise)
    power = _apply_power_schedule(power)

    log.info("ATLAS v3 scan.power: %s", power)

    active_sources = POWER_SOURCES.get(power, POWER_SOURCES["SLEEP"])

    # Skip blocked sources (from config)
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
        blocked = cfg.get("blocked_sources", [])
        if blocked:
            active_sources = [s for s in active_sources if s not in blocked]
    except (json.JSONDecodeError, OSError):
        pass

    # Source dispatch table
    source_funcs = {
        "gdelt": scan_gdelt,
        "adsb": scan_adsb,
        "aisstream": scan_aisstream,
        "wikipedia": scan_wikipedia,
        "ioda": scan_ioda,
        "fred": scan_fred,
        "polymarket": scan_polymarket,
        "manifold": scan_manifold,
        "metaculus": scan_metaculus,
        "usgs": scan_usgs,
        "noaa": scan_noaa,
        "nasa": scan_nasa,
        "iss": scan_iss,
        "safecast": scan_safecast,
        "acled": scan_acled,
        "reddit": scan_reddit,
        "hackernews": scan_hackernews,
        "rss": scan_rss,
        "govinfo": scan_govinfo,
        "congress": scan_congress,
        "crest": scan_crest,
        "currencies": scan_currencies,
        "commodities": scan_commodities,
        "global_weather": scan_global_weather,
        "space_weather": scan_space_weather,
        "treasury": scan_treasury,
        "cisa": scan_cisa,
        "volcanoes": scan_volcanoes,
        "fires": scan_fires,
        "aviation_wx": scan_aviation_wx,
        "think_tanks": scan_think_tanks,
        "official_feeds": scan_official_feeds,
        "world_bank": scan_world_bank,
        "sanctions": scan_sanctions,
        "gdacs": scan_gdacs,
        "sec_edgar": scan_sec_edgar,
        "fema": scan_fema,
        "bls": scan_bls,
        "eia": scan_eia,
        "finnhub": scan_finnhub,
        "patents": scan_patents,
        "alpha_vantage": scan_alpha_vantage,
        "telegram": scan_telegram,
        "futures": scan_futures,
        "firms": scan_firms,
    }

    # Run each active source
    all_data = {}
    sources_scanned = 0
    data_points = 0

    for src_name in active_sources:
        func = source_funcs.get(src_name)
        if not func:
            continue
        result = safe_source(src_name, func)
        all_data[src_name] = result
        sources_scanned += 1
        if isinstance(result, list):
            data_points += len(result)
        elif isinstance(result, dict) and result:
            data_points += 1
        time.sleep(1)

    # Anomaly detection
    log.info("Running anomaly engine...")
    anomalies = detect_anomalies(all_data)

    # Claims tracker
    log.info("Building claims tracker...")
    claims = build_claims({
        "gdelt": all_data.get("gdelt", []),
        "reddit": all_data.get("reddit", []),
        "predictions": {
            "polymarket": all_data.get("polymarket", []),
            "manifold": all_data.get("manifold", []),
            "metaculus": all_data.get("metaculus", []),
        },
    })

    # Intelligence synthesis.ATLAS assessments
    log.info("Generating ATLAS assessments...")
    assessments = generate_assessments(all_data, anomalies, claims)
    log.info("Generated %d assessments", len(assessments))

    # Business opportunity detection
    log.info("Detecting business opportunities...")
    opportunities = detect_opportunities(all_data, assessments)
    log.info("Detected %d opportunities", len(opportunities))

    # Preserve original dates from previous report for repeat assessments
    if PREV_REPORT_PATH.exists():
        try:
            prev = json.loads(PREV_REPORT_PATH.read_text(encoding="utf-8"))
            prev_assess_dates = {}
            for a in prev.get("assessments", []):
                key = _headline_hash(a.get("title", ""))
                if a.get("date"):
                    prev_assess_dates[key] = a["date"]
            for a in assessments:
                key = _headline_hash(a.get("title", ""))
                if key in prev_assess_dates:
                    a["date"] = prev_assess_dates[key]
        except (json.JSONDecodeError, OSError):
            pass

    # ATLAS Headlines.synthesized intelligence
    log.info("Generating ATLAS headlines...")
    headlines = generate_headlines(all_data, anomalies, claims, assessments)
    log.info("Generated %d headlines", len(headlines))

    # ATLAS Predictions.original probability estimates
    log.info("Generating ATLAS predictions...")
    atlas_predictions = generate_atlas_predictions(all_data, anomalies, assessments)
    log.info("Generated %d predictions", len(atlas_predictions))

    elapsed = round(time.time() - start, 1)

    # Build report
    report = {
        "generated": now.isoformat(),
        "version": "3.0",
        "power_level": power,
        "scan_duration_seconds": elapsed,
        "sources_scanned": sources_scanned,
        "data_points": data_points,
        "anomalies": anomalies,
        "claims": claims,
        "assessments": assessments,
        "opportunities": opportunities,
        "headlines": headlines,
        "historical_calibration": HISTORICAL_CALIBRATION,
        "gdelt": all_data.get("gdelt", []),
        "adsb": all_data.get("adsb", []),
        "aisstream": all_data.get("aisstream", []),
        "wikipedia": all_data.get("wikipedia", []),
        "ioda": all_data.get("ioda", []),
        "fred": all_data.get("fred", []),
        "predictions": {
            "polymarket": all_data.get("polymarket", []),
            "manifold": all_data.get("manifold", []),
            "metaculus": all_data.get("metaculus", []),
            "atlas_predictions": atlas_predictions,
        },
        "earthquakes": all_data.get("usgs", []),
        "weather": all_data.get("noaa", []),
        "nasa_events": all_data.get("nasa", []),
        "iss": all_data.get("iss", {}),
        "safecast": all_data.get("safecast", []),
        "acled": all_data.get("acled", []),
        "reddit": all_data.get("reddit", []),
        "hackernews": all_data.get("hackernews", []),
        "rss": all_data.get("rss", []),
        "govinfo": all_data.get("govinfo", []),
        "congress": all_data.get("congress", []),
        "crest": all_data.get("crest", []),
        "currencies": all_data.get("currencies", []),
        "commodities": all_data.get("commodities", []),
        "global_weather": all_data.get("global_weather", []),
        "space_weather": all_data.get("space_weather", []),
        "treasury": all_data.get("treasury", []),
        "cisa_kev": all_data.get("cisa", []),
        "volcanoes": all_data.get("volcanoes", []),
        "fires": all_data.get("fires", []),
        "aviation_wx": all_data.get("aviation_wx", []),
        "think_tanks": all_data.get("think_tanks", []),
        "official_feeds": all_data.get("official_feeds", []),
        "world_bank": all_data.get("world_bank", []),
        "sanctions": all_data.get("sanctions", []),
        "gdacs": all_data.get("gdacs", []),
        "sec_edgar": all_data.get("sec_edgar", []),
        "fema": all_data.get("fema", []),
        "bls": all_data.get("bls", []),
        "eia": all_data.get("eia", []),
        "finnhub": all_data.get("finnhub", []),
        "patents": all_data.get("patents", []),
        "alpha_vantage": all_data.get("alpha_vantage", []),
        "telegram": all_data.get("telegram", []),
        "futures": all_data.get("futures", []),
        "firms": all_data.get("firms", []),
    }

    # Preserve trader_intel so the feedback loop persists across scans
    # The paper trader writes trader_intel to latest.json; when ATLAS scans,
    # it overwrites latest.json. We check both the outgoing latest.json and
    # previous.json so we never lose trader data.
    if REPORT_PATH.exists():
        try:
            outgoing = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            outgoing_ti = outgoing.get("trader_intel")
            if outgoing_ti:
                report["trader_intel"] = outgoing_ti
        except (json.JSONDecodeError, OSError):
            pass
    if "trader_intel" not in report:
        prev_ti = load_previous_report().get("trader_intel")
        if prev_ti:
            report["trader_intel"] = prev_ti

    # Save previous report atomically before overwriting
    if REPORT_PATH.exists():
        try:
            tmp_prev = PREV_REPORT_PATH.with_suffix('.tmp')
            shutil.copy2(str(REPORT_PATH), str(tmp_prev))
            tmp_prev.rename(PREV_REPORT_PATH)
        except OSError:
            pass

    atomic_write_json(REPORT_PATH, report)
    log.info("Report saved: %s", REPORT_PATH)

    # Archive report (dated copy for historical preservation)
    try:
        archive_dir = ATLAS_DIR / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_name = f"atlas_{now.strftime('%Y%m%d_%H%M%S')}.json"
        archive_path = archive_dir / archive_name
        shutil.copy2(str(REPORT_PATH), str(archive_path))
        log.info("Archived report: %s", archive_path)
        # Clean up archives older than 30 days
        cutoff_archive = now - timedelta(days=30)
        for old_file in sorted(archive_dir.glob("atlas_*.json")):
            try:
                # Parse timestamp from filename: atlas_YYYYMMDD_HHMMSS.json
                ts_str = old_file.stem.replace("atlas_", "")
                file_dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
                if file_dt < cutoff_archive:
                    old_file.unlink()
                    log.info("Removed old archive: %s", old_file.name)
            except (ValueError, OSError):
                pass
    except OSError as archive_err:
        log.warning("Archive failed (non-fatal): %s", archive_err)

    # Knowledge base accumulator.rolling 90-day memory for AI assistants
    try:
        kb_path = ATLAS_DIR / "knowledge_base.json"
        kb = {"assessments": [], "opportunities": [], "headlines": [], "anomalies": [], "last_updated": now.isoformat()}
        if kb_path.exists():
            try:
                kb = json.loads(kb_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        # Append new items from this scan
        cutoff_kb = now - timedelta(days=90)
        for key in ("assessments", "opportunities", "headlines", "anomalies"):
            existing = kb.get(key, [])
            new_items = report.get(key, [])
            # Build set of existing titles/patterns for deduplication
            existing_keys = set()
            for item in existing:
                dedup_key = item.get("title") or item.get("headline") or item.get("pattern") or item.get("claim") or ""
                if dedup_key:
                    existing_keys.add(dedup_key)
            # Add new items that don't already exist
            for item in new_items:
                dedup_key = item.get("title") or item.get("headline") or item.get("pattern") or item.get("claim") or ""
                if dedup_key and dedup_key not in existing_keys:
                    # Tag with scan timestamp for age tracking
                    item_copy = dict(item)
                    if "kb_added" not in item_copy:
                        item_copy["kb_added"] = now.isoformat()
                    existing.append(item_copy)
                    existing_keys.add(dedup_key)
            # Prune items older than 90 days
            pruned = []
            for item in existing:
                item_date_str = item.get("kb_added") or item.get("date") or item.get("timestamp") or ""
                if item_date_str:
                    try:
                        item_dt = datetime.fromisoformat(item_date_str.replace("Z", "+00:00"))
                        if item_dt.tzinfo is None:
                            item_dt = item_dt.replace(tzinfo=timezone.utc)
                        if item_dt < cutoff_kb:
                            continue  # skip old items
                    except (ValueError, TypeError):
                        pass
                pruned.append(item)
            kb[key] = pruned
        kb["last_updated"] = now.isoformat()
        atomic_write_json(kb_path, kb)
        total_kb = sum(len(kb.get(k, [])) for k in ("assessments", "opportunities", "headlines", "anomalies"))
        log.info("Knowledge base updated: %d total items across 4 categories", total_kb)
    except Exception as kb_err:
        log.warning("Knowledge base update failed (non-fatal): %s", kb_err)

    # Update config
    cfg = load_config()
    cfg["power_level"] = power
    cfg["last_run"] = now.isoformat()
    cfg["total_runs"] = cfg.get("total_runs", 0) + 1
    cfg["total_data_points"] = cfg.get("total_data_points", 0) + data_points
    save_config(cfg)

    # Write market intelligence to boss_state.json for downstream consumers
    try:
        boss_state_path = DATA_DIR / "boss_state.json"
        boss_state = {}
        if boss_state_path.exists():
            boss_state = json.loads(boss_state_path.read_text())
        boss_state["market_intelligence"] = {
            "last_updated": now.isoformat(),
            "heat_score": report.get("boss_heat_score", 0),
            "demand_signals": [
                {"type": d.get("type", ""), "area": d.get("area", ""), "niche": d.get("niche", "")}
                for d in report.get("demand_signals", report.get("opportunities", []))[:20]
            ],
            "top_opportunities": [
                {"headline": o.get("headline", o.get("title", ""))[:100], "category": o.get("category", "")}
                for o in report.get("opportunities", [])[:10]
            ],
            "anomaly_count": len(anomalies),
            "sources_scanned": sources_scanned,
            "power_level": power,
        }
        boss_state["last_updated"] = now.isoformat()
        boss_state_path.write_text(json.dumps(boss_state, indent=2, default=str) + "\n")
        log.info("boss_state.json updated with market_intelligence")
    except Exception as bs_err:
        log.warning("boss_state.json update failed (non-fatal): %s", bs_err)

    # Alert (include opportunities in alerts)
    send_alert(report)

    # BOSS Intelligence Tunnel.extract actionable intel for BOSS Systems
    try:
        from atlas_boss_tunnel import run_tunnel
        run_tunnel()
    except Exception as tunnel_err:
        log.warning("BOSS tunnel failed (non-fatal): %s", tunnel_err)

    # BOSS Lead Engine.run discovery cycle on fresh intel
    try:
        from lead_engine import run_full_cycle, check_kill_switch, export_report
        if not check_kill_switch():
            run_full_cycle()
            export_report()
    except Exception as engine_err:
        log.warning("Lead Engine cycle failed (non-fatal): %s", engine_err)

    # Summary
    print()
    print("=" * 60)
    print("  ATLAS v3 Intelligence Scan Complete")
    print("=" * 60)
    print(f"  Power:         {power}")
    print(f"  Duration:      {elapsed}s")
    print(f"  Sources:       {sources_scanned}")
    print(f"  Data Points:   {data_points}")
    print(f"  Anomalies:     {len(anomalies)}")
    print(f"  Claims:        {len(claims)}")
    print(f"  Assessments:   {len(assessments)}")
    print(f"  Opportunities: {len(opportunities)}")
    print(f"  Headlines:     {len(headlines)}")
    print(f"  Predictions:   {len(atlas_predictions)}")
    if headlines:
        print(f"\n  Lead Headline: {headlines[0].get('headline', '?')[:70]}")
    if anomalies:
        top = anomalies[0]
        print(f"  Top Anomaly [{top.get('score', 0)}]: {top.get('description', '?')[:70]}")
    if assessments:
        top_a = assessments[0]
        print(f"  Top Assessment: {top_a.get('title', '?')[:70]}")
    if atlas_predictions:
        edge = atlas_predictions[0]
        print(f"  Top Edge: {edge.get('question', '?')[:50]} (ATLAS:{edge.get('atlas_probability')}% vs Market:{edge.get('market_probability')}%)")
    if opportunities:
        top_o = opportunities[0]
        print(f"  Top Opportunity: {top_o.get('opportunity', '?')[:70]}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

NTFY_SCAN_TOPIC = "atlas-scan-trigger"
TRIGGER_PATH = ATLAS_DIR / "scan_trigger"


def listen_for_triggers():
    """Run in a terminal: python3 scripts/atlas.py --listen
    Dashboard SCAN button sends triggers via ntfy. This subscribes and runs scans."""
    log.info("ATLAS listener.waiting for triggers on %s/%s", NTFY_BASE, NTFY_SCAN_TOPIC)
    print(f"Listening for scan triggers on {NTFY_BASE}/{NTFY_SCAN_TOPIC}")
    print("Dashboard SCAN button or `curl -d 'scan' ntfy.sh/atlas-scan-trigger` triggers a scan.")
    print("Include SLEEP/IDLE/ACTIVE/SURGE in message to set power level.")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            r = requests.get(
                f"{NTFY_BASE}/{NTFY_SCAN_TOPIC}/json",
                stream=True, timeout=(10, 60),
                headers={"User-Agent": USER_AGENT},
            )
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("event") != "message":
                    continue

                body = msg.get("message", "")
                log.info("Scan trigger received: %s", body)
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[{ts}] Scan triggered: {body}")

                power = None
                for lvl in ["SURGE", "ACTIVE", "IDLE", "SLEEP"]:
                    if lvl in body.upper():
                        power = lvl
                        break
                if not power:
                    cfg = load_config()
                    power = cfg.get("power_level", "IDLE")

                run_scan(power)
                deploy_report()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Scan complete.deployed to GitHub")

        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.ConnectionError:
            log.warning("Connection lost, retrying in 30s...")
            time.sleep(30)
        except KeyboardInterrupt:
            print("\nListener stopped")
            break
        except Exception as e:
            log.error("Listener error: %s", e)
            time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description="ATLAS v3.Intelligence Engine")
    parser.add_argument("--power", choices=["SLEEP", "IDLE", "ACTIVE", "SURGE"])
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--scan-and-deploy", action="store_true")
    parser.add_argument("--listen", action="store_true", help="Listen for ntfy scan triggers")
    args = parser.parse_args()

    if args.status:
        show_status()
        return
    if args.deploy:
        deploy_report()
        return
    if args.listen:
        listen_for_triggers()
        return

    cfg = load_config()
    power = args.power or cfg.get("power_level", "SLEEP")
    if power not in POWER_LEVELS:
        log.error("Invalid power level: %s", power)
        sys.exit(1)

    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)

    run_scan(power)

    if args.scan_and_deploy:
        deploy_report()


if __name__ == "__main__":
    main()
