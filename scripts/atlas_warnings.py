#!/usr/bin/env python3
"""
ATLAS Indicator-Based Warning System
======================================
Defines indicator bundles for major risk categories (war, coup, financial crisis,
humanitarian crisis, cyber attack, nuclear). When 3+ of 5+ indicators trigger
simultaneously, issues a formal warning with confidence level.

Called from atlas.py after anomaly detection to produce structured warnings.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("ATLAS.warnings")

ATLAS_DIR = Path.home() / "Library" / "Application Support" / "BOSS" / "atlas_data"
WARNING_PATH = ATLAS_DIR / "active_warnings.json"


# ---------------------------------------------------------------------------
# Indicator Bundles
# ---------------------------------------------------------------------------
# Each bundle defines 5-7 observable indicators. When 3+ fire, a formal
# warning is issued. Each indicator is a function that checks the scan data
# and returns (triggered: bool, evidence: str).

def _check_war_risk(all_data: dict, anomalies: list) -> dict:
    """War/interstate conflict risk indicators."""
    indicators = []

    # 1. Military aircraft surge (5+ in a region)
    mil_anomalies = [a for a in anomalies if a.get("pattern") == "mil_air_no_news"]
    triggered = len(mil_anomalies) > 0
    evidence = f"{sum(a.get('evidence_count', 0) for a in mil_anomalies)} military aircraft in {len(mil_anomalies)} regions with minimal news" if triggered else ""
    indicators.append({"name": "military_positioning", "triggered": triggered, "evidence": evidence})

    # 2. GDELT conflict articles above threshold
    gdelt = all_data.get("gdelt", [])
    conflict_articles = [g for g in gdelt if isinstance(g, dict) and g.get("category") == "conflict"]
    triggered = len(conflict_articles) >= 15
    indicators.append({"name": "conflict_reporting_surge", "triggered": triggered,
                       "evidence": f"{len(conflict_articles)} conflict articles in current scan" if triggered else ""})

    # 3. Futures spike (oil >5% or gold >3%)
    futures = all_data.get("futures", [])
    oil_spike = any(f.get("symbol", "").startswith("CL") and abs(f.get("change_pct", 0)) > 5 for f in futures if isinstance(f, dict))
    gold_spike = any(f.get("symbol", "").startswith("GC") and abs(f.get("change_pct", 0)) > 3 for f in futures if isinstance(f, dict))
    triggered = oil_spike or gold_spike
    spikes = []
    for f in futures:
        if isinstance(f, dict) and abs(f.get("change_pct", 0)) > 3:
            spikes.append(f"{f.get('name', f.get('symbol', '?'))} {f.get('change_pct', 0):+.1f}%")
    indicators.append({"name": "commodity_war_premium", "triggered": triggered,
                       "evidence": ", ".join(spikes) if triggered else ""})

    # 4. Internet blackout in conflict zone
    blackout_anomalies = [a for a in anomalies if a.get("pattern") == "blackout_conflict" and a.get("conflict_events", 0) > 0]
    triggered = len(blackout_anomalies) > 0
    indicators.append({"name": "comms_blackout", "triggered": triggered,
                       "evidence": ", ".join(a.get("description", "") for a in blackout_anomalies) if triggered else ""})

    # 5. UCDP conflict events or ACLED violence
    ucdp = all_data.get("ucdp", [])
    acled = all_data.get("acled", [])
    conflict_events = len(ucdp) + len(acled)
    triggered = conflict_events >= 10
    indicators.append({"name": "armed_violence_data", "triggered": triggered,
                       "evidence": f"{len(ucdp)} UCDP + {len(acled)} ACLED events" if triggered else ""})

    # 6. Telegram OSINT channels reporting military action
    telegram = all_data.get("telegram", [])
    mil_posts = [t for t in telegram if isinstance(t, dict) and
                 any(kw in t.get("text", "").lower() for kw in ["strike", "attack", "missile", "troops", "invasion", "offensive", "deploy"])]
    triggered = len(mil_posts) >= 3
    indicators.append({"name": "osint_military_chatter", "triggered": triggered,
                       "evidence": f"{len(mil_posts)} military-related OSINT posts" if triggered else ""})

    return _evaluate_bundle("WAR_RISK", "Interstate War / Major Conflict", indicators)


def _check_coup_risk(all_data: dict, anomalies: list) -> dict:
    """Coup or unconstitutional power seizure indicators."""
    indicators = []

    # 1. Military positioning without news coverage
    mil_anomalies = [a for a in anomalies if a.get("pattern") == "mil_air_no_news"]
    triggered = len(mil_anomalies) > 0
    indicators.append({"name": "military_mobilization", "triggered": triggered,
                       "evidence": f"Unreported military activity in {len(mil_anomalies)} regions" if triggered else ""})

    # 2. Internet/communications disruption
    ioda = all_data.get("ioda", [])
    blackouts = [o for o in ioda if isinstance(o, dict) and o.get("drop_percent", 0) > 50]
    triggered = len(blackouts) > 0
    indicators.append({"name": "internet_shutdown", "triggered": triggered,
                       "evidence": ", ".join(f"{o.get('country_name', '?')} {o.get('drop_percent', 0)}% drop" for o in blackouts) if triggered else ""})

    # 3. GDELT reporting on protests/political crisis
    gdelt = all_data.get("gdelt", [])
    crisis_articles = [g for g in gdelt if isinstance(g, dict) and
                       any(kw in g.get("title", "").lower() for kw in ["coup", "martial law", "state of emergency", "protest", "military takeover", "constitutional crisis"])]
    triggered = len(crisis_articles) >= 3
    indicators.append({"name": "political_crisis_reporting", "triggered": triggered,
                       "evidence": f"{len(crisis_articles)} political crisis articles" if triggered else ""})

    # 4. Wikipedia edit storms on political figures/countries
    wiki_storms = [a for a in anomalies if a.get("pattern") == "wiki_storm"]
    political_storms = [w for w in wiki_storms if any(kw in w.get("description", "").lower() for kw in
                        ["president", "prime minister", "government", "military", "constitution", "parliament"])]
    triggered = len(political_storms) > 0
    indicators.append({"name": "info_warfare_spike", "triggered": triggered,
                       "evidence": ", ".join(w.get("description", "") for w in political_storms) if triggered else ""})

    # 5. Media freedom suppression signals
    rss = all_data.get("rss", [])
    suppression = [r for r in rss if isinstance(r, dict) and
                   any(kw in r.get("title", "").lower() for kw in ["journalist arrested", "media ban", "press freedom", "censorship", "detained reporter"])]
    triggered = len(suppression) >= 2
    indicators.append({"name": "media_suppression", "triggered": triggered,
                       "evidence": f"{len(suppression)} media suppression reports" if triggered else ""})

    return _evaluate_bundle("COUP_RISK", "Coup / Unconstitutional Power Seizure", indicators)


def _check_financial_crisis(all_data: dict, anomalies: list) -> dict:
    """Financial crisis / market contagion indicators."""
    indicators = []

    # 1. VIX spike (>25% change or absolute >30)
    futures = all_data.get("futures", [])
    vix = [f for f in futures if isinstance(f, dict) and "VIX" in f.get("symbol", "").upper()]
    vix_spike = any(abs(f.get("change_pct", 0)) > 15 or f.get("price", 0) > 30 for f in vix)
    indicators.append({"name": "volatility_spike", "triggered": vix_spike,
                       "evidence": f"VIX at {vix[0].get('price', '?')} ({vix[0].get('change_pct', 0):+.1f}%)" if vix_spike and vix else ""})

    # 2. Multiple commodity crashes (3+ down >3%)
    crashes = [f for f in futures if isinstance(f, dict) and f.get("change_pct", 0) < -3]
    triggered = len(crashes) >= 3
    indicators.append({"name": "commodity_crash", "triggered": triggered,
                       "evidence": ", ".join(f"{f.get('name', '?')} {f.get('change_pct', 0):+.1f}%" for f in crashes) if triggered else ""})

    # 3. Currency instability (via ECB rates)
    ecb = all_data.get("ecb_rates", [])
    currency_moves = [r for r in ecb if isinstance(r, dict) and abs(r.get("change_pct", 0)) > 2]
    triggered = len(currency_moves) >= 2
    indicators.append({"name": "currency_instability", "triggered": triggered,
                       "evidence": f"{len(currency_moves)} major currency moves" if triggered else ""})

    # 4. FRED economic indicators showing stress
    fred = all_data.get("fred", [])
    stress = [f for f in fred if isinstance(f, dict) and
              any(kw in f.get("series_id", "").upper() for kw in ["STLFSI", "JHDUSRGDPBR", "UNRATE"])]
    triggered = len(stress) > 0 and any(f.get("value", 0) > f.get("previous", 0) for f in stress if isinstance(f, dict))
    indicators.append({"name": "economic_stress_indicators", "triggered": triggered,
                       "evidence": "FRED stress indicators elevated" if triggered else ""})

    # 5. Sanctions activity surge
    sanctions = all_data.get("sanctions", [])
    opensanctions = all_data.get("opensanctions", [])
    triggered = len(sanctions) + len(opensanctions) >= 5
    indicators.append({"name": "sanctions_wave", "triggered": triggered,
                       "evidence": f"{len(sanctions)} OFAC + {len(opensanctions)} OpenSanctions entries" if triggered else ""})

    # 6. Bank/financial institution news
    rss = all_data.get("rss", [])
    fin_crisis = [r for r in rss if isinstance(r, dict) and
                  any(kw in r.get("title", "").lower() for kw in ["bank run", "liquidity crisis", "bailout", "default", "credit freeze", "contagion"])]
    triggered = len(fin_crisis) >= 2
    indicators.append({"name": "financial_contagion_signals", "triggered": triggered,
                       "evidence": f"{len(fin_crisis)} financial crisis reports" if triggered else ""})

    return _evaluate_bundle("FINANCIAL_CRISIS", "Financial Crisis / Market Contagion", indicators)


def _check_humanitarian_crisis(all_data: dict, anomalies: list) -> dict:
    """Humanitarian crisis / mass displacement indicators."""
    indicators = []

    # 1. UNHCR refugee data
    unhcr = all_data.get("unhcr", [])
    triggered = len(unhcr) >= 3
    indicators.append({"name": "refugee_displacement", "triggered": triggered,
                       "evidence": f"{len(unhcr)} active displacement situations" if triggered else ""})

    # 2. WFP food insecurity
    wfp = all_data.get("wfp_hunger", [])
    critical_hunger = [w for w in wfp if isinstance(w, dict) and w.get("severity", "").lower() in ("critical", "emergency", "famine")]
    triggered = len(critical_hunger) >= 2
    indicators.append({"name": "food_crisis", "triggered": triggered,
                       "evidence": f"{len(critical_hunger)} countries in critical food insecurity" if triggered else ""})

    # 3. Natural disaster cluster
    usgs = all_data.get("usgs", [])
    major_quakes = [q for q in usgs if isinstance(q, dict) and q.get("magnitude", 0) >= 6.0]
    fires = all_data.get("fires", [])
    nasa = all_data.get("nasa", [])
    triggered = len(major_quakes) >= 2 or (len(fires) >= 10 and len(major_quakes) >= 1) or len(nasa) >= 5
    indicators.append({"name": "disaster_cluster", "triggered": triggered,
                       "evidence": f"{len(major_quakes)} major quakes, {len(fires)} fire alerts, {len(nasa)} NASA events" if triggered else ""})

    # 4. Disease outbreak
    who = all_data.get("who_outbreaks", [])
    promed = all_data.get("promed", [])
    triggered = len(who) >= 3 or (len(who) >= 1 and len(promed) >= 2)
    indicators.append({"name": "disease_outbreak", "triggered": triggered,
                       "evidence": f"{len(who)} WHO + {len(promed)} ProMED reports" if triggered else ""})

    # 5. Weather extreme cluster
    noaa = all_data.get("noaa", [])
    extreme = [w for w in noaa if isinstance(w, dict) and w.get("severity") in ("Severe", "Extreme")]
    triggered = len(extreme) >= 5
    indicators.append({"name": "extreme_weather_cluster", "triggered": triggered,
                       "evidence": f"{len(extreme)} severe/extreme weather alerts" if triggered else ""})

    # 6. ReliefWeb/IPC crisis reporting
    relief = all_data.get("reliefweb_crises", [])
    ipc = all_data.get("ipc_food", [])
    triggered = len(relief) >= 3 or len(ipc) >= 3
    indicators.append({"name": "humanitarian_reporting", "triggered": triggered,
                       "evidence": f"{len(relief)} ReliefWeb + {len(ipc)} IPC reports" if triggered else ""})

    return _evaluate_bundle("HUMANITARIAN_CRISIS", "Humanitarian Crisis / Mass Displacement", indicators)


def _check_cyber_threat(all_data: dict, anomalies: list) -> dict:
    """Major cyber attack / infrastructure threat indicators."""
    indicators = []

    # 1. CISA KEV surge (ransomware-linked)
    cisa = all_data.get("cisa", [])
    ransomware_vulns = [v for v in cisa if isinstance(v, dict) and v.get("known_ransomware") == "Known"]
    triggered = len(ransomware_vulns) >= 3 or len(cisa) >= 8
    indicators.append({"name": "cisa_kev_surge", "triggered": triggered,
                       "evidence": f"{len(cisa)} KEV entries ({len(ransomware_vulns)} ransomware-linked)" if triggered else ""})

    # 2. Ransomware group activity
    ransomlook = all_data.get("ransomlook", [])
    triggered = len(ransomlook) >= 10
    indicators.append({"name": "ransomware_surge", "triggered": triggered,
                       "evidence": f"{len(ransomlook)} ransomware victims reported" if triggered else ""})

    # 3. URLhaus / MalwareBazaar activity
    urlhaus = all_data.get("urlhaus", [])
    malware = all_data.get("malwarebazaar", [])
    triggered = len(urlhaus) + len(malware) >= 15
    indicators.append({"name": "malware_surge", "triggered": triggered,
                       "evidence": f"{len(urlhaus)} malicious URLs + {len(malware)} malware samples" if triggered else ""})

    # 4. OTX threat pulses with APT/zero-day tags
    otx = all_data.get("otx", [])
    critical_pulses = [p for p in otx if isinstance(p, dict) and
                       any(t in (p.get("tags") or []) for t in ["apt", "zero-day", "critical", "nation-state"])]
    triggered = len(critical_pulses) >= 3
    indicators.append({"name": "apt_activity", "triggered": triggered,
                       "evidence": f"{len(critical_pulses)} critical threat intelligence pulses" if triggered else ""})

    # 5. Internet outages (non-weather-related)
    ioda = all_data.get("ioda", [])
    outages = [o for o in ioda if isinstance(o, dict) and o.get("drop_percent", 0) > 30]
    triggered = len(outages) >= 2
    indicators.append({"name": "infrastructure_disruption", "triggered": triggered,
                       "evidence": f"{len(outages)} countries with >30% internet drop" if triggered else ""})

    return _evaluate_bundle("CYBER_THREAT", "Major Cyber Attack / Infrastructure Threat", indicators)


def _check_nuclear_risk(all_data: dict, anomalies: list) -> dict:
    """Nuclear escalation / radiological event indicators."""
    indicators = []

    # 1. Safecast radiation elevated
    safecast = all_data.get("safecast", [])
    elevated = [s for s in safecast if isinstance(s, dict) and s.get("cpm", 0) > 100]
    triggered = len(elevated) >= 3
    indicators.append({"name": "radiation_elevated", "triggered": triggered,
                       "evidence": f"{len(elevated)} sensors above 100 CPM" if triggered else ""})

    # 2. Nuclear-related GDELT reporting
    gdelt = all_data.get("gdelt", [])
    nuclear_articles = [g for g in gdelt if isinstance(g, dict) and
                        any(kw in g.get("title", "").lower() for kw in ["nuclear", "warhead", "icbm", "enrichment", "plutonium", "uranium"])]
    triggered = len(nuclear_articles) >= 5
    indicators.append({"name": "nuclear_reporting_surge", "triggered": triggered,
                       "evidence": f"{len(nuclear_articles)} nuclear-related articles" if triggered else ""})

    # 3. Seismic events near known nuclear test sites
    usgs = all_data.get("usgs", [])
    test_sites = [(41.3, 129.1), (37.1, 116.0), (24.2, 71.7), (41.5, 88.7)]  # NK, NV, Pokhran, Lop Nur
    suspicious_quakes = []
    for q in usgs:
        if isinstance(q, dict):
            qlat, qlon = q.get("lat", 0), q.get("lon", 0)
            for slat, slon in test_sites:
                if abs(qlat - slat) < 2 and abs(qlon - slon) < 2 and q.get("magnitude", 0) >= 4.0:
                    suspicious_quakes.append(q)
                    break
    triggered = len(suspicious_quakes) > 0
    indicators.append({"name": "seismic_near_test_site", "triggered": triggered,
                       "evidence": f"{len(suspicious_quakes)} seismic events near nuclear test sites" if triggered else ""})

    # 4. Military flights near nuclear installations
    adsb = all_data.get("adsb", [])
    nuclear_mil = [a for a in adsb if isinstance(a, dict) and
                   any(kw in a.get("type", "").upper() for kw in ["B-52", "B-2", "TU-95", "TU-160", "E-6", "E-4"])]
    triggered = len(nuclear_mil) >= 2
    indicators.append({"name": "nuclear_capable_aircraft", "triggered": triggered,
                       "evidence": f"{len(nuclear_mil)} nuclear-capable aircraft detected" if triggered else ""})

    # 5. Telegram/OSINT nuclear chatter
    telegram = all_data.get("telegram", [])
    nuclear_chatter = [t for t in telegram if isinstance(t, dict) and
                       any(kw in t.get("text", "").lower() for kw in ["nuclear", "warhead", "tactical nuke", "radioactive", "defcon"])]
    triggered = len(nuclear_chatter) >= 3
    indicators.append({"name": "nuclear_osint_chatter", "triggered": triggered,
                       "evidence": f"{len(nuclear_chatter)} nuclear-related OSINT posts" if triggered else ""})

    return _evaluate_bundle("NUCLEAR_RISK", "Nuclear Escalation / Radiological Event", indicators)


def _evaluate_bundle(code: str, label: str, indicators: list) -> dict:
    """Score a bundle: 3+ triggered = formal warning."""
    triggered = [i for i in indicators if i["triggered"]]
    count = len(triggered)
    total = len(indicators)

    if count >= 4:
        level = "CRITICAL"
        confidence = min(95, 60 + count * 8)
    elif count >= 3:
        level = "WARNING"
        confidence = min(85, 45 + count * 10)
    elif count >= 2:
        level = "ELEVATED"
        confidence = min(60, 25 + count * 12)
    else:
        level = "NORMAL"
        confidence = 0

    return {
        "code": code,
        "label": label,
        "level": level,
        "confidence": confidence,
        "triggered_count": count,
        "total_indicators": total,
        "indicators": indicators,
        "evidence": [i["evidence"] for i in triggered if i["evidence"]],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_warnings(all_data: dict, anomalies: list) -> List[dict]:
    """Main entry point — evaluates all warning bundles against current scan data.

    Returns list of warnings sorted by severity, only includes ELEVATED+.
    """
    bundles = [
        _check_war_risk(all_data, anomalies),
        _check_coup_risk(all_data, anomalies),
        _check_financial_crisis(all_data, anomalies),
        _check_humanitarian_crisis(all_data, anomalies),
        _check_cyber_threat(all_data, anomalies),
        _check_nuclear_risk(all_data, anomalies),
    ]

    level_order = {"CRITICAL": 0, "WARNING": 1, "ELEVATED": 2, "NORMAL": 3}
    active = [b for b in bundles if b["level"] != "NORMAL"]
    active.sort(key=lambda b: (level_order.get(b["level"], 3), -b["confidence"]))

    _save_warnings(bundles)

    log.info("Warning system: %d bundles evaluated, %d active (%s)",
             len(bundles), len(active),
             ", ".join(f"{b['code']}={b['level']}" for b in active) if active else "all clear")

    return active


def get_all_bundle_status(all_data: dict, anomalies: list) -> List[dict]:
    """Returns ALL bundles including NORMAL, for dashboard display."""
    bundles = [
        _check_war_risk(all_data, anomalies),
        _check_coup_risk(all_data, anomalies),
        _check_financial_crisis(all_data, anomalies),
        _check_humanitarian_crisis(all_data, anomalies),
        _check_cyber_threat(all_data, anomalies),
        _check_nuclear_risk(all_data, anomalies),
    ]
    return bundles


def _save_warnings(bundles: list):
    """Persist current warning state for cross-scan comparison."""
    WARNING_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bundles": bundles,
    }
    WARNING_PATH.write_text(json.dumps(state, indent=2, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        if WARNING_PATH.exists():
            state = json.loads(WARNING_PATH.read_text(encoding="utf-8"))
            print(f"Last evaluated: {state.get('timestamp', 'unknown')}")
            for b in state.get("bundles", []):
                status = f"  {b['code']}: {b['level']} ({b['triggered_count']}/{b['total_indicators']} indicators)"
                if b["level"] != "NORMAL":
                    status += f" — {b['confidence']}% confidence"
                print(status)
        else:
            print("No warning data yet. Run an ATLAS scan first.")
    else:
        print("Usage: atlas_warnings.py --status")
