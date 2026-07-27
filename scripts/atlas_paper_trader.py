#!/usr/bin/env python3
"""
ATLAS Paper Trader — Simulated prediction market betting
Pulls real markets from Polymarket + Kalshi, compares against ATLAS confidence,
finds edges, places simulated bets, resolves outcomes, tracks P&L.

Usage:
    python3 scripts/atlas_paper_trader.py --scan          # Find edges, place bets
    python3 scripts/atlas_paper_trader.py --check         # Resolve settled bets
    python3 scripts/atlas_paper_trader.py --status        # Show portfolio
    python3 scripts/atlas_paper_trader.py --reset         # Reset to $1000
    python3 scripts/atlas_paper_trader.py --scan --check  # Both: resolve then place new
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

try:
    from atlas_deep_research import deep_research, get_atlas_confidence as deep_get_confidence, generate_trader_intel
    DEEP_RESEARCH_AVAILABLE = True
except ImportError:
    DEEP_RESEARCH_AVAILABLE = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BOSS_HQ = Path.home() / "Desktop" / "BOSS_HQ"
APP_SUPPORT = Path.home() / "Library" / "Application Support" / "BOSS"
ATLAS_DIR = APP_SUPPORT / "atlas_data"
TRADES_PATH = ATLAS_DIR / "paper_trades.json"
REPORT_PATH = ATLAS_DIR / "latest.json"
CALIBRATION_PATH = ATLAS_DIR / "calibration.json"

ATLAS_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ATLAS/3.0"
HTTP_TIMEOUT = 15

STARTING_BALANCE = 1000.0

MIN_EDGE = 10  # Only bet on 10%+ divergences
MAX_BET_PCT = 0.15  # Never more than 15% on one bet
MIN_BET = 5.0  # Minimum $5 bet
MAX_BETS_PER_SCAN = 15
MAX_PER_CATEGORY = 3  # Max 3 bets per topic
MAX_PER_COUNTRY = 2  # Max 2 bets involving the same country
MAX_ACTOR_EXPOSURE = 0.15  # Max 15% of bankroll on bets involving same country
MIN_VOLUME = 5000
MIN_DAYS_TO_EXPIRY = 14
EXPIRY_GRACE_DAYS = 7  # Auto-expire bets 7 days past end_date if unresolved
PREFERRED_HORIZON = (14, 90)  # Prefer bets resolving in 14-90 days
KELLY_FRACTION = 0.25  # Quarter-Kelly for edge uncertainty

# ---------------------------------------------------------------------------
# Country detection for entity-level diversification
# ---------------------------------------------------------------------------

COUNTRY_NAMES = [
    "afghanistan", "albania", "algeria", "argentina", "armenia", "australia",
    "austria", "azerbaijan", "bahrain", "bangladesh", "belarus", "belgium",
    "bolivia", "bosnia", "brazil", "bulgaria", "cambodia", "cameroon", "canada",
    "chad", "chile", "china", "colombia", "congo", "costa rica", "croatia",
    "cuba", "cyprus", "czech", "denmark", "ecuador", "egypt", "el salvador",
    "estonia", "ethiopia", "finland", "france", "georgia", "germany", "ghana",
    "greece", "guatemala", "haiti", "honduras", "hungary", "iceland", "india",
    "indonesia", "iran", "iraq", "ireland", "israel", "italy", "ivory coast",
    "jamaica", "japan", "jordan", "kazakhstan", "kenya", "korea", "kosovo",
    "kuwait", "kyrgyzstan", "laos", "latvia", "lebanon", "libya", "lithuania",
    "malaysia", "mali", "mexico", "moldova", "mongolia", "montenegro", "morocco",
    "mozambique", "myanmar", "nepal", "netherlands", "new zealand", "nicaragua",
    "niger", "nigeria", "north korea", "norway", "oman", "pakistan", "palestine",
    "panama", "paraguay", "peru", "philippines", "poland", "portugal", "qatar",
    "romania", "russia", "rwanda", "saudi arabia", "senegal", "serbia",
    "singapore", "slovakia", "slovenia", "somalia", "south africa", "south korea",
    "spain", "sri lanka", "sudan", "sweden", "switzerland", "syria", "taiwan",
    "tajikistan", "tanzania", "thailand", "tunisia", "turkey", "turkmenistan",
    "uganda", "ukraine", "united arab emirates", "uae", "united kingdom", "uk",
    "united states", "usa", "us ", "uruguay", "uzbekistan", "venezuela",
    "vietnam", "yemen", "zambia", "zimbabwe",
    # Common short forms and regions
    "gaza", "crimea", "donbas", "xinjiang", "tibet", "hong kong", "macau",
]


def detect_countries(text: str) -> List[str]:
    """Extract country/region names from question text."""
    t = text.lower()
    found = []
    for country in COUNTRY_NAMES:
        if country in t:
            # Normalize some short forms
            normalized = country
            if country in ("usa", "us ", "united states"):
                normalized = "united states"
            elif country in ("uk", "united kingdom"):
                normalized = "united kingdom"
            elif country in ("uae", "united arab emirates"):
                normalized = "uae"
            elif country in ("south korea", "korea"):
                # "korea" alone could be either, but usually South Korea in markets
                normalized = "korea"
            if normalized not in found:
                found.append(normalized)
    return found


def kelly_bet_size(atlas_prob: float, market_prob: float, balance: float) -> float:
    """Quarter-Kelly sizing with proper formula."""
    q = atlas_prob / 100.0
    p = market_prob / 100.0
    if q > p:
        f_star = (q - p) / (1 - p)
    else:
        f_star = (p - q) / p
    f_star *= KELLY_FRACTION
    bet = f_star * balance
    return max(MIN_BET, min(bet, balance * MAX_BET_PCT))

# Categories we care about (skip sports/entertainment noise)
SKIP_CATEGORIES = {"sports", "entertainment", "gaming", "celebrity"}

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
            return None
        r.raise_for_status()
        return r
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Calibration — load tuned weights + scope guardrails
# ---------------------------------------------------------------------------

_calibration_cache = None

def load_calibration() -> dict:
    global _calibration_cache
    if _calibration_cache is not None:
        return _calibration_cache
    if CALIBRATION_PATH.exists():
        try:
            cal = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
            _calibration_cache = cal
            return cal
        except (json.JSONDecodeError, OSError):
            pass
    return {}

def get_tuned_weights() -> dict:
    cal = load_calibration()
    return cal.get("tuned_weights", {})

def get_scope_map() -> dict:
    cal = load_calibration()
    return cal.get("scope_map", {})

CALIBRATOR_CATEGORIES = {
    "conflict": ["war", "invasion", "attack", "military", "conflict", "ceasefire",
                  "peace", "missile", "troops", "nato", "ukraine", "russia", "iran",
                  "china", "taiwan", "israel", "gaza", "hamas", "hezbollah", "sanctions"],
    "economic": ["recession", "inflation", "gdp", "federal reserve", "fed ", "interest rate",
                 "unemployment", "economy", "tariff", "trade war", "debt", "default"],
    "disaster": ["earthquake", "hurricane", "flood", "wildfire", "disaster", "tsunami",
                 "tornado", "storm", "heat wave", "drought"],
    "ai_tech": ["ai ", "artificial intelligence", "openai", "google", "gpt", "agi",
                "robot", "autonomous", "chatgpt", "claude", "meta ai", "apple ai"],
    "political": ["election", "president", "trump", "biden", "vote", "poll", "congress",
                  "senate", "governor", "democrat", "republican", "primary"],
    "climate": ["climate", "temperature", "carbon", "emissions", "renewable",
                "fossil fuel", "paris agreement"],
    "energy": ["oil", "crude", "wti", "brent", "gas price", "energy price", "opec"],
    "crypto": ["bitcoin", "ethereum", "crypto", "btc", "eth"],
}

def categorize_question(question: str) -> str:
    q = question.lower()
    for cat, keywords in CALIBRATOR_CATEGORIES.items():
        if any(k in q for k in keywords):
            return cat
    return "other"

def is_out_of_scope(question: str) -> bool:
    scope = get_scope_map()
    if not scope:
        return False
    cat = categorize_question(question)
    status = scope.get(cat, "CALIBRATED")
    if isinstance(status, dict):
        status = status.get("status", "CALIBRATED")
    return status == "OUT_OF_SCOPE"


# ---------------------------------------------------------------------------
# Portfolio management
# ---------------------------------------------------------------------------

def load_portfolio() -> dict:
    if TRADES_PATH.exists():
        try:
            return json.loads(TRADES_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "balance": STARTING_BALANCE,
        "starting_balance": STARTING_BALANCE,
        "total_bets_placed": 0,
        "wins": 0,
        "losses": 0,
        "total_wagered": 0.0,
        "total_pnl": 0.0,
        "pending": [],
        "resolved": [],
        "last_scan": None,
        "last_check": None,
    }


def save_portfolio(portfolio: dict):
    TRADES_PATH.write_text(json.dumps(portfolio, indent=2, default=str) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Fetch Polymarket markets
# ---------------------------------------------------------------------------

def fetch_polymarket() -> List[Dict]:
    results = []
    seen_ids = set()
    for offset in range(0, 1000, 100):
        r = safe_get(
            f"https://gamma-api.polymarket.com/markets?closed=false&limit=100&offset={offset}&order=volume24hr&ascending=false"
        )
        if r is None:
            break
        try:
            data = r.json()
            markets = data if isinstance(data, list) else []
            if not markets:
                break
            for m in markets:
                question = m.get("question", "")
                if not question:
                    continue
                cond_id = m.get("conditionId", "")
                slug = m.get("slug", "")
                mid = cond_id or slug
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)
                outcomes = m.get("outcomePrices", "[]")
                try:
                    prices = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
                    prob = round(float(prices[0]) * 100, 1) if prices else 0
                except (json.JSONDecodeError, IndexError, ValueError, TypeError):
                    prob = 0
                if prob <= 0 or prob >= 100:
                    continue
                vol = 0
                try:
                    vol = float(m.get("volume", 0) or 0)
                except (ValueError, TypeError):
                    vol = 0
                if vol < MIN_VOLUME:
                    continue
                end_date = m.get("endDate", "")
                if end_date:
                    try:
                        end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                        if end_dt < datetime.now(timezone.utc) + timedelta(days=MIN_DAYS_TO_EXPIRY):
                            continue
                    except (ValueError, TypeError):
                        pass
                results.append({
                    "platform": "polymarket",
                    "question": question[:200],
                    "market_prob": prob,
                    "volume": vol,
                    "url": f"https://polymarket.com/event/{slug}",
                    "end_date": end_date,
                    "slug": slug,
                    "condition_id": cond_id,
                    "closed": m.get("closed", False),
                    "resolved": m.get("resolved", False),
                    "description": m.get("description", "")[:300],
                    "market_id": mid,
                })
        except (json.JSONDecodeError, ValueError):
            pass
        time.sleep(0.8)
    return results


# ---------------------------------------------------------------------------
# Fetch Kalshi markets
# ---------------------------------------------------------------------------

def fetch_kalshi() -> List[Dict]:
    base = "https://api.elections.kalshi.com/trade-api/v2"
    results = []

    # Step 1: Get event tickers from interesting categories
    event_tickers = []
    r = safe_get(f"{base}/events?limit=200")
    if r:
        try:
            events = r.json().get("events", [])
            for e in events:
                cat = (e.get("category") or "").lower()
                if any(k in cat for k in ["politic", "election", "climate", "weather",
                                           "econom", "tech", "science", "world",
                                           "financ", "crypto", "energy", "health"]):
                    event_tickers.append(e.get("event_ticker", ""))
        except (json.JSONDecodeError, ValueError):
            pass

    # Step 2: Fetch markets for each interesting event
    for et in event_tickers[:50]:
        if not et:
            continue
        r = safe_get(f"{base}/markets?event_ticker={et}&limit=20&status=open")
        if r is None:
            time.sleep(0.5)
            continue
        try:
            data = r.json()
            for m in data.get("markets", []):
                ticker = m.get("ticker", "")
                title = m.get("title", "")
                if not title:
                    continue
                yes_bid = float(m.get("yes_bid_dollars", 0) or 0)
                yes_ask = float(m.get("yes_ask_dollars", 0) or 0)
                if yes_bid <= 0 and yes_ask <= 0:
                    continue
                mid = (yes_bid + yes_ask) / 2 if yes_bid > 0 and yes_ask > 0 else yes_ask or yes_bid
                prob = round(mid * 100, 1)
                if prob <= 0 or prob >= 100:
                    continue
                results.append({
                    "platform": "kalshi",
                    "question": title[:200],
                    "market_prob": prob,
                    "volume": float(m.get("volume_fp", 0) or 0),
                    "url": f"https://kalshi.com/markets/{ticker}",
                    "end_date": m.get("expiration_time", m.get("close_time", "")),
                    "ticker": ticker,
                    "event_ticker": et,
                    "status": m.get("status", ""),
                    "result": m.get("result", ""),
                    "settled": m.get("status") in ("settled", "finalized"),
                    "market_id": ticker,
                    "category": "",
                    "subtitle": m.get("subtitle", "")[:200],
                    "yes_bid": yes_bid,
                    "yes_ask": yes_ask,
                })
        except (json.JSONDecodeError, ValueError):
            pass
        time.sleep(0.3)

    return results


# ---------------------------------------------------------------------------
# ATLAS confidence engine
# ---------------------------------------------------------------------------

def get_atlas_confidence(question: str, market_prob: float, all_data: dict) -> Tuple[float, str, str]:
    """Return (atlas_probability, reasoning, confidence_level).

    RULE: Only diverge from market when ATLAS has SPECIFIC EVIDENCE.
    No evidence = no trade. Don't guess.
    """
    q = question.lower()

    atlas_prob = market_prob
    reasoning_parts = []
    confidence = "none"
    has_signal = False

    gdelt = all_data.get("gdelt", [])
    adsb = all_data.get("adsb", [])
    weather = all_data.get("weather", [])
    quakes = all_data.get("earthquakes", [])
    commodities = all_data.get("commodities", [])
    fred = all_data.get("fred", [])
    reddit = all_data.get("reddit", [])
    rss = all_data.get("rss", [])

    conflict_count = len([g for g in gdelt if g.get("category") == "conflict"])
    mil_aircraft = len(adsb)
    severe_wx = len([wx for wx in weather if wx.get("severity") in ("Extreme", "Severe")])

    # --- CONFLICT / GEOPOLITICAL ---
    is_conflict_q = any(k in q for k in ["war", "invasion", "attack", "military", "conflict",
                             "ceasefire", "missile", "troops", "nato",
                             "ukraine", "russia", "iran", "china", "taiwan",
                             "israel", "gaza", "hamas", "hezbollah", "strike",
                             "blockade", "airspace", "sanctions"])
    is_peace_q = any(k in q for k in ["peace", "deal", "agreement", "ceasefire", "diplomacy",
                                       "normalize", "lifted"])

    if is_conflict_q:
        if conflict_count > 20:
            # High conflict activity — conflict events MORE likely, peace LESS likely
            if is_peace_q:
                atlas_prob = max(1, market_prob - 15)
                reasoning_parts.append(f"GDELT: {conflict_count} conflict articles — peace less likely during escalation")
            else:
                atlas_prob = min(99, market_prob + 12)
                reasoning_parts.append(f"GDELT: {conflict_count} conflict articles — elevated tension")
            has_signal = True
            confidence = "high"
        elif conflict_count > 8:
            if is_peace_q:
                atlas_prob = max(1, market_prob - 8)
                reasoning_parts.append(f"GDELT: {conflict_count} conflict articles — moderate tension undermines peace prospects")
            else:
                atlas_prob = min(99, market_prob + 6)
                reasoning_parts.append(f"GDELT: {conflict_count} conflict articles — moderate activity")
            has_signal = True
            confidence = "medium"
        elif conflict_count < 3 and is_peace_q:
            # Very quiet = maybe peace actually is progressing (no news is good news for peace)
            atlas_prob = min(99, market_prob + 5)
            reasoning_parts.append(f"GDELT: only {conflict_count} conflict articles — quiet may favor diplomacy")
            has_signal = True
            confidence = "medium"

        if mil_aircraft > 50:
            if is_peace_q:
                atlas_prob = max(1, atlas_prob - 8)
                reasoning_parts.append(f"ADS-B: {mil_aircraft} military aircraft — high posture contradicts peace")
            else:
                atlas_prob = min(99, atlas_prob + 8)
                reasoning_parts.append(f"ADS-B: {mil_aircraft} military aircraft — elevated posture")
            has_signal = True
            if confidence != "high":
                confidence = "medium"

    # --- ECONOMIC ---
    elif any(k in q for k in ["recession", "inflation", "gdp", "federal reserve", "fed ",
                               "interest rate", "unemployment", "economy", "tariff",
                               "trade war", "debt", "default"]):
        shocks = [f for f in fred if f.get("shock")]
        oil = [c for c in commodities if c.get("symbol") == "CL=F"]
        gas = [c for c in commodities if c.get("symbol") == "NG=F"]

        if shocks:
            adjust = min(len(shocks) * 4, 15)
            atlas_prob = min(99, market_prob + adjust)
            reasoning_parts.append(f"FRED: {len(shocks)} economic shock indicators detected")
            has_signal = True
            confidence = "high"

        if oil and abs(oil[0].get("change_pct", 0)) > 4:
            pct = oil[0]["change_pct"]
            price = oil[0].get("price", 0)
            reasoning_parts.append(f"WTI ${price:.0f} ({pct:+.1f}%) — significant move")
            if "inflation" in q and pct > 4:
                atlas_prob = min(99, atlas_prob + 5)
                has_signal = True
            elif "recession" in q and pct > 6:
                atlas_prob = min(99, atlas_prob + 8)
                reasoning_parts.append("Oil spike = cost shock → recession risk")
                has_signal = True
            elif "recession" in q and pct < -6:
                atlas_prob = min(99, atlas_prob + 6)
                reasoning_parts.append("Oil crash = demand destruction signal")
                has_signal = True
            if has_signal and confidence == "none":
                confidence = "medium"

    # --- NATURAL DISASTER ---
    elif any(k in q for k in ["earthquake", "hurricane", "flood", "wildfire",
                               "disaster", "tsunami", "tornado", "storm",
                               "heat wave", "drought"]):
        big_quakes = [eq for eq in quakes if eq.get("magnitude", 0) >= 5.5]
        if "earthquake" in q and big_quakes:
            adjust = min(len(big_quakes) * 3, 15)
            atlas_prob = min(99, market_prob + adjust)
            reasoning_parts.append(f"USGS: {len(big_quakes)} significant quakes (M5.5+) — seismic activity elevated")
            has_signal = True
            confidence = "high" if len(big_quakes) > 5 else "medium"
        if severe_wx > 15:
            atlas_prob = min(99, market_prob + 8)
            reasoning_parts.append(f"NOAA: {severe_wx} severe/extreme alerts — major weather pattern")
            has_signal = True
            confidence = "high"
        elif severe_wx > 8:
            atlas_prob = min(99, market_prob + 4)
            reasoning_parts.append(f"NOAA: {severe_wx} severe/extreme alerts")
            has_signal = True
            if confidence == "none":
                confidence = "medium"

    # --- AI / TECH ---
    elif any(k in q for k in ["ai ", "artificial intelligence", "openai", "google ai",
                               "gpt", "agi", "chatgpt", "claude", "meta ai", "apple ai",
                               "deepseek", "gemini"]):
        ai_rss = len([r for r in rss if any(k in (r.get("title") or "").lower()
                      for k in ["ai ", "artificial intelligence", "openai", "gpt",
                                "gemini", "claude", "deepseek"])])
        ai_reddit = len([p for p in reddit if any(sub in (p.get("subreddit") or "").lower()
                        for sub in ["artificial", "machinelearning", "openai", "localllama"])])
        if ai_rss > 20 or ai_reddit > 15:
            atlas_prob = min(99, market_prob + 5)
            reasoning_parts.append(f"RSS: {ai_rss} AI articles, Reddit: {ai_reddit} posts — high activity")
            has_signal = True
            confidence = "medium"

    # --- ENERGY / COMMODITIES ---
    elif any(k in q for k in ["oil", "crude", "wti", "brent", "gas price",
                               "energy price", "opec"]):
        oil = [c for c in commodities if c.get("symbol") == "CL=F"]
        gas = [c for c in commodities if c.get("symbol") == "NG=F"]
        if oil:
            pct = oil[0].get("change_pct", 0)
            price = oil[0].get("price", 0)
            reasoning_parts.append(f"WTI at ${price:.2f} ({pct:+.1f}%)")
            is_downside_q = "low" in q or "below" in q or "drop" in q or "fall" in q
            is_upside_q = ("above" in q or "high" in q or "reach" in q) and not is_downside_q
            is_hit_q = "hit" in q
            if abs(pct) > 4:
                if is_upside_q and pct > 4:
                    atlas_prob = min(99, market_prob + 10)
                    reasoning_parts.append("Strong upward momentum supports price target")
                elif is_downside_q and pct < -4:
                    atlas_prob = min(99, market_prob + 10)
                    reasoning_parts.append("Downward momentum supports decline target")
                elif is_upside_q and pct < -4:
                    atlas_prob = max(1, market_prob - 10)
                    reasoning_parts.append("Downward momentum contradicts upside target")
                elif is_downside_q and pct > 4:
                    atlas_prob = max(1, market_prob - 10)
                    reasoning_parts.append("Upward momentum contradicts downside target")
                elif is_hit_q and not is_upside_q and not is_downside_q:
                    if pct > 4:
                        atlas_prob = min(99, market_prob + 8)
                        reasoning_parts.append("Strong momentum — price target more likely")
                    elif pct < -4:
                        atlas_prob = max(1, market_prob - 8)
                        reasoning_parts.append("Negative momentum — upside target less likely")
                has_signal = True
                confidence = "high"

    # --- POLITICAL (elections etc) — ATLAS has NO polling data, be honest ---
    elif any(k in q for k in ["election", "president", "vote", "poll",
                               "congress", "senate", "governor", "primary",
                               "democrat", "republican"]):
        reasoning_parts.append("Political/electoral — ATLAS lacks polling data, deferring to market")
        confidence = "none"

    # --- NO SIGNAL: don't guess ---
    if not has_signal:
        if not reasoning_parts:
            reasoning_parts.append("No ATLAS intelligence signal — tracking market consensus")
        confidence = "none"

    atlas_prob = max(1, min(99, round(atlas_prob, 1)))
    reasoning = ". ".join(reasoning_parts) + "."

    return atlas_prob, reasoning, confidence


# ---------------------------------------------------------------------------
# Bet placement logic
# ---------------------------------------------------------------------------

def calculate_bet_size(edge: float, balance: float,
                       atlas_prob: float = 50, market_prob: float = 50) -> float:
    """Quarter-Kelly bet sizing with proper formula."""
    return round(kelly_bet_size(atlas_prob, market_prob, balance), 2)


def make_bet_id(platform: str, market_id: str) -> str:
    return hashlib.md5(f"{platform}:{market_id}".encode()).hexdigest()[:12]


def is_sports_or_noise(question: str) -> bool:
    q = question.lower()
    sports_keywords = [
        "vs.", "vs ", "yankees", "lakers", "celtics", "nba", "nfl", "mlb",
        "nhl", "premier league", "champions league", "world cup", "super bowl",
        "touchdown", "home run", "goal scored", "points scored", "rebounds",
        "assists", "rushing yards", "passing yards", "strikeouts", "innings",
        "batting average", "ERA", "seed", "playoff", "bracket", "march madness",
        "ufc", "boxing", "mma", "fight night", "grand slam", "wimbledon",
        "formula 1", "f1 ", "nascar", "race winner", "lap ",
        "oscars", "grammy", "emmy", "golden globe", "box office",
        "bachelor", "reality tv", "celebrity",
        "diamondbacks", "mariners", "athletics", "mets", "dodgers", "padres",
        "brewers", "cubs", "cardinals", "reds", "pirates", "phillies",
        "braves", "nationals", "marlins", "orioles", "rays", "red sox",
        "blue jays", "twins", "guardians", "tigers", "royals", "white sox",
        "astros", "rangers", "angels", "rockies", "giants",
        "fifa", "win the 202", "la liga", "serie a", "bundesliga", "ligue 1",
        "copa america", "euro 202", "arsenal", "liverpool", "manchester",
        "barcelona", "real madrid", "bayern", "psg", "chelsea", "tottenham",
        "wins by over", "runs scored", "hit a home run",
        "canadiens", "maple leafs", "oilers", "penguins", "bruins",
        "panthers", "hurricanes", "avalanche", "islanders", "flyers",
        "eastern conference", "western conference", "stanley cup",
        "mls ", "defender of the year", "mvp", "rookie of the year",
        "bodø/glimt", "win on 20", "play for ",
        "post ", "tweets from",
    ]
    return any(k in q for k in sports_keywords)


def find_edges(markets: List[Dict], atlas_data: dict, portfolio: dict) -> Tuple[List[Dict], List[Dict]]:
    """Find markets where ATLAS diverges from the market by > MIN_EDGE.
    Returns (edges, all_research) — all_research feeds back to ATLAS."""
    edges = []
    all_research = []
    existing_ids = set(b["bet_id"] for b in portfolio.get("pending", []))
    existing_ids.update(b["bet_id"] for b in portfolio.get("resolved", []))

    # Build lookup from existing ATLAS predictions
    existing_preds = {}
    for p in atlas_data.get("predictions", {}).get("atlas_predictions", []):
        key = p.get("question", "").lower().strip()[:80]
        existing_preds[key] = p

    for market in markets:
        question = market["question"]

        # Skip sports and entertainment
        if is_sports_or_noise(question):
            continue

        # Scope guardrail: skip categories where ATLAS isn't calibrated
        if is_out_of_scope(question):
            continue

        bet_id = make_bet_id(market["platform"], market["market_id"])
        if bet_id in existing_ids:
            continue

        market_prob = market["market_prob"]

        # Near-zero/near-100 markets are priced that way for a reason — skip
        if market_prob < 3 or market_prob > 97:
            continue

        # Deep research: entity extraction + multi-source analysis + calibrated weights
        if DEEP_RESEARCH_AVAILABLE:
            research = deep_research(
                question, market_prob, atlas_data,
                volume=market.get("volume", 0),
                end_date=market.get("end_date", ""),
            )
            all_research.append(research)
            atlas_prob = research["atlas_prob"]
            reasoning = research["reasoning"]
            confidence = research["confidence"]
            evidence = research.get("evidence_summary", {})
            factors = research.get("evidence_factors", [])
            effective_edge = research.get("effective_edge", research.get("edge", 0))
            mkt_quality = research.get("market_quality", {})
        else:
            q_key = question.lower().strip()[:80]
            existing = existing_preds.get(q_key)
            if existing and existing.get("atlas_probability") is not None:
                atlas_prob = existing["atlas_probability"]
                reasoning = existing.get("atlas_reasoning", "From ATLAS prediction engine.")
                confidence = existing.get("confidence", "medium")
            else:
                atlas_prob, reasoning, confidence = get_atlas_confidence(question, market_prob, atlas_data)
            evidence = {}
            factors = []
            effective_edge = abs(atlas_prob - market_prob)
            mkt_quality = {}

        edge = abs(atlas_prob - market_prob)
        if effective_edge < MIN_EDGE:
            continue

        if confidence in ("none", "low"):
            continue

        # Position: if ATLAS thinks probability is HIGHER, buy YES; lower, buy NO
        position = "YES" if atlas_prob > market_prob else "NO"
        entry_price = market_prob / 100 if position == "YES" else (100 - market_prob) / 100

        bet_amount = calculate_bet_size(edge, portfolio["balance"],
                                       atlas_prob=atlas_prob, market_prob=market_prob)
        if bet_amount <= 0 or bet_amount > portfolio["balance"]:
            continue

        shares = bet_amount / entry_price if entry_price > 0 else 0
        potential_payout = round(shares * 1.0, 2)  # Each share pays $1 if correct

        edges.append({
            "bet_id": bet_id,
            "platform": market["platform"],
            "question": question,
            "market_id": market["market_id"],
            "ticker": market.get("ticker", ""),
            "slug": market.get("slug", ""),
            "condition_id": market.get("condition_id", ""),
            "url": market["url"],
            "market_prob": market_prob,
            "atlas_prob": atlas_prob,
            "edge": round(edge, 1),
            "position": position,
            "entry_price": round(entry_price, 4),
            "bet_amount": bet_amount,
            "shares": round(shares, 2),
            "potential_payout": potential_payout,
            "potential_profit": round(potential_payout - bet_amount, 2),
            "reasoning": reasoning,
            "confidence": confidence,
            "effective_edge": effective_edge,
            "market_quality": mkt_quality,
            "evidence_summary": evidence,
            "evidence_factors": factors,
            "end_date": market.get("end_date", ""),
            "placed_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "resolved_at": None,
            "pnl": None,
        })

    # Apply preferred horizon bonus: bets resolving in 14-90 days get a small edge bump
    for e in edges:
        end_date = e.get("end_date", "")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                days_to_expiry = (end_dt - datetime.now(timezone.utc)).days
                if PREFERRED_HORIZON[0] <= days_to_expiry <= PREFERRED_HORIZON[1]:
                    # Mid-range horizon bonus: up to 3% extra effective edge
                    # Peak bonus at the midpoint of the preferred range
                    mid = (PREFERRED_HORIZON[0] + PREFERRED_HORIZON[1]) / 2
                    distance_from_mid = abs(days_to_expiry - mid) / mid
                    horizon_bonus = 3.0 * (1.0 - distance_from_mid)
                    e["effective_edge"] = e.get("effective_edge", e["edge"]) + horizon_bonus
                    e["horizon_bonus"] = round(horizon_bonus, 1)
            except (ValueError, TypeError):
                pass

    edges.sort(key=lambda x: x.get("effective_edge", x["edge"]), reverse=True)

    # Enforce MAX_PER_CATEGORY + MAX_PER_COUNTRY diversification
    category_counts: Dict[str, int] = {}
    country_counts: Dict[str, int] = {}
    diversified = []
    for e in edges:
        cat = categorize_question(e["question"])
        if category_counts.get(cat, 0) >= MAX_PER_CATEGORY:
            continue

        # Entity-level dedup: no more than MAX_PER_COUNTRY bets involving the same country
        countries = detect_countries(e["question"])
        country_blocked = False
        for c in countries:
            if country_counts.get(c, 0) >= MAX_PER_COUNTRY:
                country_blocked = True
                break
        if country_blocked:
            continue

        category_counts[cat] = category_counts.get(cat, 0) + 1
        for c in countries:
            country_counts[c] = country_counts.get(c, 0) + 1
        diversified.append(e)

    return diversified, all_research


# ---------------------------------------------------------------------------
# Resolution — check if bets have settled
# ---------------------------------------------------------------------------

def check_polymarket_resolution(bet: dict) -> Optional[str]:
    """Check if a Polymarket market has resolved. Returns 'YES', 'NO', or None.

    Uses multiple strategies because the gamma slug-based lookup fails silently
    on resolved markets:
      1. CLOB API by condition_id (most reliable for resolved markets)
      2. Gamma events endpoint by slug
      3. Gamma markets endpoint by condition_id
    """
    slug = bet.get("slug", "")
    cond = bet.get("condition_id", "")
    if not slug and not cond:
        return None

    def _parse_outcome_prices(m: dict) -> Optional[str]:
        """Extract YES/NO from a market dict with outcomePrices."""
        outcomes = m.get("outcomePrices", "[]")
        try:
            prices = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
            if prices and float(prices[0]) >= 0.99:
                return "YES"
            elif prices and float(prices[0]) <= 0.01:
                return "NO"
        except (json.JSONDecodeError, IndexError, ValueError, TypeError):
            pass
        return None

    # Strategy 1: CLOB API by condition_id (works best for resolved markets)
    if cond:
        r = safe_get(f"https://clob.polymarket.com/markets/{cond}")
        if r is not None:
            try:
                data = r.json()
                # CLOB returns a single market object
                if data.get("closed") or data.get("resolved"):
                    result = _parse_outcome_prices(data)
                    if result:
                        return result
            except (json.JSONDecodeError, ValueError):
                pass

    # Strategy 2: Gamma events endpoint by slug
    if slug:
        r = safe_get(f"https://gamma-api.polymarket.com/events?slug={slug}")
        if r is not None:
            try:
                data = r.json()
                events = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
                for event in events:
                    # Events contain nested markets
                    markets = event.get("markets", [])
                    for m in markets:
                        if m.get("resolved") or m.get("closed"):
                            result = _parse_outcome_prices(m)
                            if result:
                                return result
            except (json.JSONDecodeError, ValueError):
                pass

    # Strategy 3: Gamma markets by condition_id (direct lookup)
    if cond:
        r = safe_get(f"https://gamma-api.polymarket.com/markets?condition_id={cond}")
        if r is not None:
            try:
                data = r.json()
                markets = data if isinstance(data, list) else []
                for m in markets:
                    if m.get("resolved"):
                        result = _parse_outcome_prices(m)
                        if result:
                            return result
            except (json.JSONDecodeError, ValueError):
                pass

    # Strategy 4: Original slug+closed query as last resort
    if slug:
        r = safe_get(f"https://gamma-api.polymarket.com/markets?slug={slug}&closed=true")
        if r is not None:
            try:
                data = r.json()
                markets = data if isinstance(data, list) else []
                for m in markets:
                    if m.get("resolved"):
                        result = _parse_outcome_prices(m)
                        if result:
                            return result
            except (json.JSONDecodeError, ValueError):
                pass

    return None


def check_kalshi_resolution(bet: dict) -> Optional[str]:
    """Check if a Kalshi market has settled. Returns 'YES', 'NO', or None."""
    ticker = bet.get("ticker", "")
    if not ticker:
        return None
    r = safe_get(f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}")
    if r is None:
        r = safe_get(f"https://trading-api.kalshi.com/trade-api/v2/markets/{ticker}")
    if r is None:
        return None
    try:
        data = r.json()
        market = data.get("market", data)
        status = market.get("status", "")
        result = market.get("result", "")
        if status in ("settled", "finalized"):
            if result == "yes":
                return "YES"
            elif result == "no":
                return "NO"
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def resolve_bets(portfolio: dict) -> int:
    """Check pending bets for resolution. Returns number resolved."""
    resolved_count = 0
    still_pending = []

    for bet in portfolio["pending"]:
        outcome = None
        if bet["platform"] == "polymarket":
            outcome = check_polymarket_resolution(bet)
        elif bet["platform"] == "kalshi":
            outcome = check_kalshi_resolution(bet)

        if outcome is None:
            # Check if bet is way past end date (auto-expire after grace period)
            end = bet.get("end_date", "")
            if end:
                try:
                    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > end_dt + timedelta(days=EXPIRY_GRACE_DAYS):
                        bet["status"] = "expired"
                        bet["resolved_at"] = datetime.now(timezone.utc).isoformat()
                        bet["pnl"] = 0  # Return stake on expired
                        portfolio["balance"] += bet["bet_amount"]
                        portfolio["resolved"].append(bet)
                        resolved_count += 1
                        continue
                except (ValueError, TypeError):
                    pass
            still_pending.append(bet)
            continue

        # Bet resolved
        bet["resolved_at"] = datetime.now(timezone.utc).isoformat()
        if outcome == bet["position"]:
            # Winner
            bet["status"] = "won"
            payout = bet["potential_payout"]
            bet["pnl"] = round(payout - bet["bet_amount"], 2)
            portfolio["balance"] += payout
            portfolio["wins"] += 1
        else:
            # Loser
            bet["status"] = "lost"
            bet["pnl"] = -bet["bet_amount"]
            portfolio["losses"] += 1

        portfolio["total_pnl"] = round(portfolio["total_pnl"] + bet["pnl"], 2)
        portfolio["resolved"].append(bet)
        resolved_count += 1

    portfolio["pending"] = still_pending
    return resolved_count


# ---------------------------------------------------------------------------
# Cross-platform matching
# ---------------------------------------------------------------------------

def find_cross_platform_edges(poly_markets: List[Dict], kalshi_markets: List[Dict]) -> List[Dict]:
    """Find the same question on both platforms with different odds — pure arbitrage."""
    cross_edges = []

    for p in poly_markets:
        p_q = p["question"].lower()
        p_words = set(p_q.split())
        for k in kalshi_markets:
            k_q = k["question"].lower()
            k_words = set(k_q.split())
            overlap = len(p_words & k_words)
            total = min(len(p_words), len(k_words))
            if total > 0 and overlap / total > 0.5:
                diff = abs(p["market_prob"] - k["market_prob"])
                if diff >= 5:
                    cross_edges.append({
                        "polymarket_question": p["question"],
                        "kalshi_question": k["question"],
                        "polymarket_prob": p["market_prob"],
                        "kalshi_prob": k["market_prob"],
                        "spread": round(diff, 1),
                        "polymarket_url": p["url"],
                        "kalshi_url": k["url"],
                    })

    cross_edges.sort(key=lambda x: x["spread"], reverse=True)
    return cross_edges[:20]


# ---------------------------------------------------------------------------
# Load ATLAS intelligence data
# ---------------------------------------------------------------------------

def load_atlas_data() -> dict:
    if REPORT_PATH.exists():
        try:
            return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def show_status(portfolio: dict):
    balance = portfolio["balance"]
    starting = portfolio["starting_balance"]
    total_pnl = portfolio["total_pnl"]
    pnl_pct = (total_pnl / starting * 100) if starting else 0
    wins = portfolio["wins"]
    losses = portfolio["losses"]
    total = wins + losses
    win_rate = (wins / total * 100) if total else 0
    pending = portfolio["pending"]

    print()
    print("=" * 65)
    print("  ATLAS PAPER TRADER — Portfolio Status")
    print("=" * 65)
    print(f"  Balance:      ${balance:,.2f}  (started: ${starting:,.2f})")
    pnl_sign = "+" if total_pnl >= 0 else ""
    print(f"  Total P&L:    {pnl_sign}${total_pnl:,.2f}  ({pnl_sign}{pnl_pct:.1f}%)")
    print(f"  Record:       {wins}W - {losses}L  ({win_rate:.0f}% win rate)")
    print(f"  Total Wagered:${portfolio.get('total_wagered', 0):,.2f}")
    print(f"  Pending Bets: {len(pending)}")
    print(f"  Resolved:     {len(portfolio.get('resolved', []))}")
    print(f"  Last Scan:    {portfolio.get('last_scan', 'never')}")
    print("-" * 65)

    if pending:
        print("  OPEN POSITIONS:")
        for bet in pending[:15]:
            edge_sign = "+" if bet["atlas_prob"] > bet["market_prob"] else "-"
            print(f"    [{bet['platform'][:4].upper()}] {bet['question'][:55]}")
            print(f"      {bet['position']} @ {bet['entry_price']:.0%} | "
                  f"${bet['bet_amount']:.0f} | Edge: {bet['edge']:.0f}% | "
                  f"ATLAS:{bet['atlas_prob']:.0f}% vs Mkt:{bet['market_prob']:.0f}%")
        if len(pending) > 15:
            print(f"    ... and {len(pending) - 15} more")
    else:
        print("  No open positions.")

    resolved = portfolio.get("resolved", [])
    recent = [r for r in resolved if r.get("status") in ("won", "lost")][-10:]
    if recent:
        print()
        print("  RECENT RESULTS:")
        for bet in reversed(recent):
            icon = "W" if bet["status"] == "won" else "L"
            pnl = bet.get("pnl", 0)
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            print(f"    [{icon}] {pnl_str:>10} | {bet['question'][:50]}")

    print("=" * 65)
    print()


# ---------------------------------------------------------------------------
# Main commands
# ---------------------------------------------------------------------------

def cmd_scan(portfolio: dict):
    print("Fetching markets from Polymarket + Kalshi...")

    poly_markets = fetch_polymarket()
    print(f"  Polymarket: {len(poly_markets)} active markets")

    kalshi_markets = fetch_kalshi()
    print(f"  Kalshi:     {len(kalshi_markets)} active markets")

    all_markets = poly_markets + kalshi_markets
    print(f"  Total:      {len(all_markets)} markets")

    # Load ATLAS intelligence
    atlas_data = load_atlas_data()
    if not atlas_data:
        print("  WARNING: No ATLAS report found. Run atlas.py first.")
        print("  Using market data only.")

    # Find edges
    print("\nFinding ATLAS edges (min edge: {0}%)...".format(MIN_EDGE))
    edges, all_research = find_edges(all_markets, atlas_data, portfolio)

    if not edges:
        print("  No edges found above threshold.")
    else:
        print(f"  Found {len(edges)} edges!")

    # Cross-platform matching
    cross = find_cross_platform_edges(poly_markets, kalshi_markets)
    if cross:
        print(f"\n  CROSS-PLATFORM SPREADS ({len(cross)} found):")
        for c in cross[:5]:
            print(f"    {c['spread']:.0f}% spread: {c['polymarket_question'][:50]}")
            print(f"      Poly: {c['polymarket_prob']}% | Kalshi: {c['kalshi_prob']}%")

    # Place bets (limited per scan)
    bets_placed = 0
    for edge in edges:
        if bets_placed >= MAX_BETS_PER_SCAN:
            print(f"\n  Hit max {MAX_BETS_PER_SCAN} bets per scan. Remaining edges saved for next scan.")
            break
        if portfolio["balance"] < MIN_BET:
            print("\n  INSUFFICIENT FUNDS — stopping bet placement.")
            break

        bet_amount = calculate_bet_size(edge["edge"], portfolio["balance"],
                                       atlas_prob=edge.get("atlas_prob", 50),
                                       market_prob=edge.get("market_prob", 50))
        if bet_amount > portfolio["balance"]:
            continue

        edge["bet_amount"] = bet_amount
        edge["shares"] = round(bet_amount / edge["entry_price"], 2) if edge["entry_price"] > 0 else 0
        edge["potential_payout"] = round(edge["shares"], 2)
        edge["potential_profit"] = round(edge["potential_payout"] - bet_amount, 2)

        portfolio["balance"] = round(portfolio["balance"] - bet_amount, 2)
        portfolio["total_wagered"] = round(portfolio.get("total_wagered", 0) + bet_amount, 2)
        portfolio["total_bets_placed"] += 1
        portfolio["pending"].append(edge)
        bets_placed += 1

        print(f"\n  BET PLACED: {edge['position']} on [{edge['platform'][:4].upper()}]")
        print(f"    Q: {edge['question'][:65]}")
        eff = edge.get('effective_edge', edge['edge'])
        mq = edge.get('market_quality', {})
        mq_tag = f" [{mq.get('efficiency', '?')}, {mq.get('time_label', '?')}]" if mq else ""
        print(f"    ATLAS: {edge['atlas_prob']:.0f}% vs Market: {edge['market_prob']:.0f}%  (edge: {edge['edge']:.0f}%, eff: {eff:.0f}%){mq_tag}")
        print(f"    Stake: ${edge['bet_amount']:.2f} → Potential: ${edge['potential_payout']:.2f}")
        ev = edge.get("evidence_summary", {})
        if ev:
            sources = []
            if ev.get("gdelt_relevant"): sources.append(f"GDELT:{ev['gdelt_relevant']}")
            if ev.get("think_tanks_relevant"): sources.append(f"TT:{ev['think_tanks_relevant']}")
            if ev.get("aircraft_near_region"): sources.append(f"ADS-B:{ev['aircraft_near_region']}")
            if ev.get("conflict_zones"): sources.append(f"CZ:{ev['conflict_zones']}")
            if ev.get("nuclear_sites"): sources.append(f"NUK:{ev['nuclear_sites']}")
            if ev.get("reddit_relevant"): sources.append(f"Reddit:{ev['reddit_relevant']}")
            if sources:
                print(f"    Evidence: {' | '.join(sources)}")
        for f in edge.get("evidence_factors", [])[:2]:
            print(f"    → {f['reason'][:75]}")

    portfolio["last_scan"] = datetime.now(timezone.utc).isoformat()
    print(f"\n  Placed {bets_placed} bets. Balance: ${portfolio['balance']:,.2f}")

    # Feed trader intelligence back to ATLAS
    if DEEP_RESEARCH_AVAILABLE and all_research:
        trader_intel = generate_trader_intel(all_research, atlas_data)
        try:
            report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            report["trader_intel"] = trader_intel
            REPORT_PATH.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
            print(f"\n  INTEL FEEDBACK: {trader_intel['markets_analyzed']} markets analyzed → "
                  f"{trader_intel['edges_found']} edges, {len(trader_intel['geopolitical_hotspots'])} hotspots, "
                  f"{len(trader_intel['information_gaps'])} info gaps")
        except (json.JSONDecodeError, OSError):
            pass


def cmd_check(portfolio: dict):
    pending_count = len(portfolio["pending"])
    if not pending_count:
        print("No pending bets to check.")
        return

    print(f"Checking {pending_count} pending bets for resolution...")
    resolved = resolve_bets(portfolio)
    portfolio["last_check"] = datetime.now(timezone.utc).isoformat()

    if resolved:
        print(f"  {resolved} bets resolved!")
        for bet in portfolio["resolved"][-resolved:]:
            icon = "WIN" if bet["status"] == "won" else "LOSS" if bet["status"] == "lost" else "EXP"
            pnl = bet.get("pnl", 0)
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            print(f"    [{icon}] {pnl_str} | {bet['question'][:55]}")
    else:
        print(f"  No bets resolved yet. {pending_count} still pending.")


def cmd_reset():
    portfolio = {
        "balance": STARTING_BALANCE,
        "starting_balance": STARTING_BALANCE,
        "total_bets_placed": 0,
        "wins": 0,
        "losses": 0,
        "total_wagered": 0.0,
        "total_pnl": 0.0,
        "pending": [],
        "resolved": [],
        "last_scan": None,
        "last_check": None,
    }
    save_portfolio(portfolio)
    print(f"Portfolio reset to ${STARTING_BALANCE:,.2f}.")
    return portfolio


# ---------------------------------------------------------------------------
# Report for dashboard
# ---------------------------------------------------------------------------

def export_for_dashboard(portfolio: dict):
    """Write paper trading data into the ATLAS report for dashboard rendering."""
    if not REPORT_PATH.exists():
        return
    try:
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ATLAS Paper Trader")
    parser.add_argument("--scan", action="store_true", help="Find edges and place bets")
    parser.add_argument("--check", action="store_true", help="Resolve settled bets")
    parser.add_argument("--status", action="store_true", help="Show portfolio")
    parser.add_argument("--reset", action="store_true", help="Reset to $1000")
    args = parser.parse_args()

    if not any([args.scan, args.check, args.status, args.reset]):
        args.status = True

    if args.reset:
        portfolio = cmd_reset()
        if not args.scan and not args.check:
            show_status(portfolio)
            return
    else:
        portfolio = load_portfolio()

    if args.check:
        cmd_check(portfolio)
        save_portfolio(portfolio)

    if args.scan:
        cmd_scan(portfolio)
        save_portfolio(portfolio)
        export_for_dashboard(portfolio)

    if args.status or args.scan or args.check:
        show_status(portfolio)
        save_portfolio(portfolio)


if __name__ == "__main__":
    main()
