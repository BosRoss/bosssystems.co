#!/usr/bin/env python3
"""
ATLAS Structured Daily Brief
==============================
Generates a structured intelligence brief from the latest ATLAS report.
Format follows professional intelligence community standards:

1. KEY DEVELOPMENTS (top 1-2 critical items)
2. REGIONAL UPDATES (Europe, Middle East, Indo-Pacific, Africa, Americas)
3. ECONOMIC PULSE (markets with geopolitical context)
4. CYBER/TECH (significant events with attribution)
5. WATCH LIST (elevated but not breaking)
6. WARNINGS (indicator-based formal warnings)
7. FORECAST UPDATES (prediction changes with reasoning)

Called from atlas.py during scan to produce the brief section of the report.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("ATLAS.brief")

ATLAS_DIR = Path.home() / "Library" / "Application Support" / "BOSS" / "atlas_data"

REGION_COUNTRIES = {
    "EUROPE": {"UA", "RU", "GB", "DE", "FR", "PL", "RO", "IT", "ES", "NL", "BE", "SE", "NO", "FI", "DK",
               "CZ", "AT", "HU", "SK", "BG", "HR", "RS", "BA", "ME", "MK", "AL", "XK", "MD", "BY",
               "GR", "PT", "IE", "CH", "LT", "LV", "EE", "GE", "AM", "AZ"},
    "MIDDLE_EAST": {"IR", "IQ", "SY", "IL", "PS", "LB", "JO", "SA", "AE", "QA", "BH", "KW", "OM", "YE",
                    "TR", "EG", "LY", "TN", "DZ", "MA"},
    "INDO_PACIFIC": {"CN", "JP", "KR", "KP", "TW", "IN", "PK", "BD", "LK", "MM", "TH", "VN", "PH",
                     "ID", "MY", "SG", "AU", "NZ", "FJ", "PG", "MN", "KH", "LA", "NP", "BT", "AF"},
    "AFRICA": {"NG", "ET", "KE", "ZA", "GH", "TZ", "UG", "SN", "ML", "NE", "BF", "TD", "CF", "CD",
               "CG", "AO", "MZ", "ZW", "MW", "RW", "BI", "SO", "SD", "SS", "ER", "DJ", "CM",
               "CI", "GA", "GQ", "ST", "BJ", "TG", "SL", "LR", "GW", "MG", "MR", "NA", "BW", "ZM"},
    "AMERICAS": {"US", "CA", "MX", "BR", "AR", "CO", "VE", "CL", "PE", "EC", "BO", "PY", "UY",
                 "CU", "DO", "HT", "JM", "TT", "GT", "HN", "SV", "NI", "CR", "PA", "GY", "SR"},
}

REGION_LABELS = {
    "EUROPE": "Europe & Eurasia",
    "MIDDLE_EAST": "Middle East & North Africa",
    "INDO_PACIFIC": "Indo-Pacific",
    "AFRICA": "Sub-Saharan Africa",
    "AMERICAS": "Americas",
}


def _classify_region(country_code: str) -> Optional[str]:
    """Map ISO-2 country code to region."""
    if not country_code:
        return None
    cc = country_code.upper()
    for region, codes in REGION_COUNTRIES.items():
        if cc in codes:
            return region
    return None


def _extract_country_codes(item: dict) -> List[str]:
    """Pull country codes from any data item."""
    codes = []
    for field in ("country", "country_code", "countryCode"):
        v = item.get(field, "")
        if isinstance(v, str) and len(v) == 2:
            codes.append(v.upper())
    countries = item.get("countries", [])
    if isinstance(countries, list):
        for c in countries:
            if isinstance(c, str) and len(c) == 2:
                codes.append(c.upper())
    return codes


def generate_brief(report: dict, warnings: list = None) -> dict:
    """Generate a structured intelligence brief from the full report.

    Returns a dict with sections that can be included in the report JSON
    and rendered on the dashboard.
    """
    brief = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "key_developments": _key_developments(report),
        "regional_updates": _regional_updates(report),
        "economic_pulse": _economic_pulse(report),
        "cyber_tech": _cyber_tech(report),
        "watch_list": _watch_list(report),
        "warnings": _format_warnings(warnings or []),
        "forecast_updates": _forecast_updates(report),
    }

    total_items = sum(len(v) if isinstance(v, list) else (1 if v else 0)
                      for v in brief.values() if v and not isinstance(v, str))
    log.info("Brief generated: %d total items across %d sections",
             total_items, sum(1 for v in brief.values() if v))

    return brief


def _key_developments(report: dict) -> List[dict]:
    """Top 1-3 most significant developments from this scan."""
    developments = []

    anomalies = report.get("anomalies", [])
    for a in sorted(anomalies, key=lambda x: x.get("score", 0), reverse=True)[:2]:
        if a.get("score", 0) >= 70:
            developments.append({
                "headline": a.get("description", ""),
                "type": "anomaly",
                "severity": "high" if a.get("score", 0) >= 85 else "medium",
                "score": a.get("score", 0),
                "pattern": a.get("pattern", ""),
            })

    assessments = report.get("assessments", [])
    for a in assessments[:3]:
        if a.get("confidence", 0) >= 75:
            developments.append({
                "headline": a.get("title", ""),
                "type": "assessment",
                "severity": "high" if a.get("confidence", 0) >= 85 else "medium",
                "confidence": a.get("confidence", 0),
                "category": a.get("category", ""),
            })

    headlines = report.get("headlines", [])
    for h in headlines[:5]:
        sent = h.get("sentiment", 0)
        if isinstance(sent, (int, float)) and abs(sent) >= 0.6:
            developments.append({
                "headline": h.get("headline", ""),
                "type": "headline",
                "severity": "high" if abs(sent) >= 0.8 else "medium",
                "sentiment": sent,
            })
            if len(developments) >= 3:
                break

    seen = set()
    deduped = []
    for d in developments:
        key = d["headline"][:50].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(d)

    return sorted(deduped, key=lambda x: {"high": 0, "medium": 1}.get(x.get("severity"), 2))[:3]


def _regional_updates(report: dict) -> Dict[str, List[dict]]:
    """Group events by region with context."""
    regions = {r: [] for r in REGION_LABELS}

    gdelt = report.get("gdelt", [])
    for g in gdelt:
        if not isinstance(g, dict):
            continue
        codes = _extract_country_codes(g)
        for cc in codes:
            region = _classify_region(cc)
            if region and len(regions[region]) < 5:
                regions[region].append({
                    "title": g.get("title", "")[:120],
                    "category": g.get("category", ""),
                    "country": cc,
                    "source": "GDELT",
                })
                break

    rss = report.get("rss", [])
    for r in rss:
        if not isinstance(r, dict):
            continue
        title = r.get("title", "").lower()
        for region, codes in REGION_COUNTRIES.items():
            if len(regions[region]) >= 5:
                continue
            for cc in codes:
                try:
                    import pycountry
                    country = pycountry.countries.get(alpha_2=cc)
                    if country and country.name.lower() in title:
                        regions[region].append({
                            "title": r.get("title", "")[:120],
                            "source": r.get("source", "RSS"),
                            "country": cc,
                        })
                        break
                except ImportError:
                    pass

    acled = report.get("acled", [])
    for a in acled:
        if not isinstance(a, dict):
            continue
        codes = _extract_country_codes(a)
        for cc in codes:
            region = _classify_region(cc)
            if region and len(regions[region]) < 5:
                regions[region].append({
                    "title": a.get("event_type", a.get("title", "Armed conflict event"))[:120],
                    "source": "ACLED",
                    "country": cc,
                })
                break

    result = {}
    for region, items in regions.items():
        if items:
            result[region] = {
                "label": REGION_LABELS[region],
                "items": items[:5],
                "event_count": len(items),
            }

    return result


def _economic_pulse(report: dict) -> dict:
    """Markets summary with geopolitical context."""
    pulse = {"futures": [], "currencies": [], "context": []}

    futures = report.get("futures", [])
    for f in futures:
        if isinstance(f, dict) and f.get("symbol"):
            entry = {
                "symbol": f.get("symbol", ""),
                "name": f.get("name", ""),
                "price": f.get("price", 0),
                "change_pct": f.get("change_pct", 0),
            }
            if abs(f.get("change_pct", 0)) >= 1.5:
                entry["notable"] = True
            pulse["futures"].append(entry)

    ecb = report.get("ecb_rates", [])
    for r in ecb:
        if isinstance(r, dict):
            pulse["currencies"].append({
                "pair": r.get("pair", r.get("currency", "")),
                "rate": r.get("rate", 0),
                "change_pct": r.get("change_pct", 0),
            })

    fred = report.get("fred", [])
    for f in fred:
        if isinstance(f, dict) and f.get("series_id"):
            pulse["context"].append({
                "indicator": f.get("series_id", ""),
                "value": f.get("value", 0),
                "title": f.get("title", ""),
            })

    wb = report.get("wb_governance", report.get("world_bank", []))
    if wb:
        pulse["governance_data"] = len(wb)

    return pulse


def _cyber_tech(report: dict) -> List[dict]:
    """Cyber security and technology events."""
    items = []

    cisa = report.get("cisa_kev", report.get("cisa", []))
    ransomware_linked = [v for v in cisa if isinstance(v, dict) and v.get("known_ransomware") == "Known"]
    if cisa:
        items.append({
            "type": "cisa_kev",
            "headline": f"{len(cisa)} vulnerabilities in CISA KEV ({len(ransomware_linked)} ransomware-linked)",
            "severity": "high" if ransomware_linked else "medium",
            "count": len(cisa),
        })

    ransomlook = report.get("ransomlook", report.get("ransomware", []))
    if ransomlook:
        groups = set()
        for r in ransomlook:
            if isinstance(r, dict) and r.get("group"):
                groups.add(r["group"])
        items.append({
            "type": "ransomware",
            "headline": f"{len(ransomlook)} ransomware victims across {len(groups)} groups",
            "severity": "high" if len(ransomlook) >= 10 else "medium",
            "groups": list(groups)[:10],
        })

    otx = report.get("otx", [])
    if otx:
        apt = [p for p in otx if isinstance(p, dict) and any(t in (p.get("tags") or []) for t in ["apt", "nation-state"])]
        items.append({
            "type": "threat_intel",
            "headline": f"{len(otx)} threat pulses ({len(apt)} APT/nation-state)",
            "severity": "high" if apt else "low",
        })

    urlhaus = report.get("urlhaus", [])
    malware = report.get("malwarebazaar", [])
    if urlhaus or malware:
        items.append({
            "type": "malware",
            "headline": f"{len(urlhaus)} malicious URLs, {len(malware)} malware samples tracked",
            "severity": "medium" if (len(urlhaus) + len(malware)) >= 10 else "low",
        })

    nvd = report.get("nvd_critical", [])
    if nvd:
        items.append({
            "type": "vulnerabilities",
            "headline": f"{len(nvd)} critical vulnerabilities (NVD)",
            "severity": "medium",
        })

    return sorted(items, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity"), 2))


def _watch_list(report: dict) -> List[dict]:
    """Items that are elevated but not yet breaking — things to monitor."""
    watch = []

    trend_alerts = report.get("trend_alerts", [])
    for t in trend_alerts:
        if isinstance(t, dict) and t.get("trend") in ("sustained_increase", "accelerating_increase"):
            watch.append({
                "metric": t.get("metric", ""),
                "trend": t.get("trend", ""),
                "change_pct": t.get("change_pct", 0),
                "alert": t.get("alert", ""),
                "priority": t.get("priority", "normal"),
            })

    narrative = report.get("narrative_trends", [])
    for n in narrative:
        if isinstance(n, dict) and n.get("status") == "ESCALATING":
            watch.append({
                "metric": f"narrative_{n.get('topic', 'unknown')}",
                "trend": "escalating_narrative",
                "alert": f"Escalating narrative: {n.get('topic', '')} — {n.get('count', 0)} mentions across {n.get('sources', 0)} sources",
                "priority": "high",
            })

    country_intel = report.get("countries", {})
    assessments = country_intel.get("assessments", {}) if isinstance(country_intel, dict) else {}
    for cc, assessment in assessments.items():
        if isinstance(assessment, dict) and assessment.get("trajectory") in ("declining", "crisis"):
            watch.append({
                "metric": f"country_{cc}",
                "trend": "country_trajectory",
                "alert": f"{cc}: trajectory {assessment.get('trajectory')} — {', '.join(assessment.get('key_risks', [])[:2])}",
                "priority": "high",
            })

    return sorted(watch, key=lambda x: 0 if x.get("priority") == "high" else 1)[:10]


def _format_warnings(warnings: list) -> List[dict]:
    """Format indicator-based warnings for the brief."""
    formatted = []
    for w in warnings:
        if isinstance(w, dict) and w.get("level") in ("CRITICAL", "WARNING", "ELEVATED"):
            formatted.append({
                "code": w.get("code", ""),
                "label": w.get("label", ""),
                "level": w.get("level", ""),
                "confidence": w.get("confidence", 0),
                "triggered": w.get("triggered_count", 0),
                "total": w.get("total_indicators", 0),
                "evidence": w.get("evidence", []),
            })
    return formatted


def _forecast_updates(report: dict) -> List[dict]:
    """Prediction market positions and ATLAS forecast divergences."""
    updates = []

    pred_data = report.get("predictions", {})
    if not isinstance(pred_data, dict):
        return updates

    atlas_preds = pred_data.get("atlas_predictions", [])
    for p in atlas_preds:
        if not isinstance(p, dict):
            continue
        div = p.get("divergence", 0)
        if abs(div) >= 5:
            updates.append({
                "question": p.get("question", "")[:100],
                "atlas_probability": p.get("atlas_probability", 0),
                "market_probability": p.get("market_probability", 0),
                "divergence": div,
                "direction": "ATLAS higher" if div > 0 else "ATLAS lower",
                "source": p.get("source", ""),
            })

    return sorted(updates, key=lambda x: -abs(x.get("divergence", 0)))[:8]


def format_brief_text(brief: dict) -> str:
    """Render the brief as plain text for ntfy notifications."""
    lines = []

    kd = brief.get("key_developments", [])
    if kd:
        lines.append("KEY DEVELOPMENTS")
        for d in kd:
            marker = "!" if d.get("severity") == "high" else "-"
            lines.append(f"  {marker} {d.get('headline', '')[:100]}")
        lines.append("")

    regions = brief.get("regional_updates", {})
    if regions:
        lines.append("REGIONAL")
        for region_code, data in regions.items():
            if isinstance(data, dict) and data.get("items"):
                label = data.get("label", region_code)
                count = data.get("event_count", len(data["items"]))
                top = data["items"][0].get("title", "")[:80]
                lines.append(f"  {label}: {count} events. {top}")
        lines.append("")

    pulse = brief.get("economic_pulse", {})
    notable_futures = [f for f in pulse.get("futures", []) if f.get("notable")]
    if notable_futures:
        lines.append("MARKETS")
        moves = ", ".join(f"{f.get('name', f.get('symbol', '?'))} {f.get('change_pct', 0):+.1f}%" for f in notable_futures[:5])
        lines.append(f"  {moves}")
        lines.append("")

    cyber = brief.get("cyber_tech", [])
    high_cyber = [c for c in cyber if c.get("severity") == "high"]
    if high_cyber:
        lines.append("CYBER")
        for c in high_cyber[:3]:
            lines.append(f"  {c.get('headline', '')[:100]}")
        lines.append("")

    warnings = brief.get("warnings", [])
    if warnings:
        lines.append("WARNINGS")
        for w in warnings:
            lines.append(f"  [{w.get('level', '')}] {w.get('label', '')} — {w.get('triggered', 0)}/{w.get('total', 0)} indicators ({w.get('confidence', 0)}% conf)")
        lines.append("")

    watch = brief.get("watch_list", [])
    if watch:
        lines.append("WATCH LIST")
        for w in watch[:5]:
            lines.append(f"  {w.get('alert', '')[:100]}")
        lines.append("")

    forecasts = brief.get("forecast_updates", [])
    if forecasts:
        lines.append("FORECASTS")
        for f in forecasts[:4]:
            lines.append(f"  {f.get('question', '')[:70]} (gap {f.get('divergence', 0):+.0f}%)")

    return "\n".join(lines) if lines else "No significant developments."


if __name__ == "__main__":
    import sys
    report_path = ATLAS_DIR / "latest.json"
    if not report_path.exists():
        print("No report found. Run an ATLAS scan first.")
        sys.exit(1)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    brief = generate_brief(report)
    print(format_brief_text(brief))
