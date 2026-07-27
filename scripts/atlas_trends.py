#!/usr/bin/env python3
"""
ATLAS Trend Detection Engine
=============================
Detects temporal patterns across scans: sustained increases, acceleration,
breakpoints, and emerging narratives. Stores 90 days of metric history.

Called from atlas.py during each scan to produce trend alerts.
"""

import json
import logging
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("ATLAS.trends")

ATLAS_DIR = Path.home() / "Library" / "Application Support" / "BOSS" / "atlas_data"
TREND_PATH = ATLAS_DIR / "trend_history.json"
MAX_HISTORY_DAYS = 90


def _load_history() -> dict:
    if TREND_PATH.exists():
        try:
            return json.loads(TREND_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"metrics": {}, "alerts": []}


def _save_history(history: dict):
    TREND_PATH.parent.mkdir(parents=True, exist_ok=True)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_HISTORY_DAYS)).isoformat()
    for metric_name in list(history.get("metrics", {}).keys()):
        points = history["metrics"][metric_name]
        history["metrics"][metric_name] = [p for p in points if p.get("t", "") >= cutoff]
        if not history["metrics"][metric_name]:
            del history["metrics"][metric_name]
    TREND_PATH.write_text(json.dumps(history, indent=2, default=str) + "\n", encoding="utf-8")


def _extract_metrics(all_data: dict) -> Dict[str, float]:
    """Extract trackable metrics from a scan's all_data."""
    metrics = {}

    def _count(key):
        v = all_data.get(key, [])
        return len(v) if isinstance(v, list) else 0

    metrics["gdelt_total"] = _count("gdelt")
    metrics["gdelt_conflict"] = len([g for g in all_data.get("gdelt", []) if isinstance(g, dict) and g.get("category") == "conflict"])
    metrics["gdelt_disaster"] = len([g for g in all_data.get("gdelt", []) if isinstance(g, dict) and g.get("category") == "disaster"])
    metrics["reddit_total"] = _count("reddit")
    metrics["adsb_military"] = _count("adsb")
    metrics["weather_alerts"] = _count("noaa")
    metrics["earthquakes"] = _count("usgs")
    metrics["nasa_events"] = _count("nasa")
    metrics["rss_articles"] = _count("rss")
    metrics["think_tanks"] = _count("think_tanks")
    metrics["cisa_vulns"] = _count("cisa")
    metrics["ransomware"] = _count("ransomlook")
    metrics["fires"] = _count("fires")
    metrics["safecast_elevated"] = len([s for s in all_data.get("safecast", []) if isinstance(s, dict) and s.get("cpm", 0) > 100])
    metrics["congress_bills"] = _count("congress")
    metrics["sanctions"] = _count("sanctions")
    metrics["opensanctions"] = _count("opensanctions")
    metrics["urlhaus"] = _count("urlhaus")
    metrics["ucdp_events"] = _count("ucdp")

    futures = all_data.get("futures", [])
    if isinstance(futures, list):
        for f in futures:
            if isinstance(f, dict) and f.get("symbol"):
                sym = f["symbol"].replace("=F", "").lower()
                metrics[f"futures_{sym}"] = f.get("price", 0)
                if f.get("change_pct"):
                    metrics[f"futures_{sym}_chg"] = f["change_pct"]

    # Country-level GDELT conflict counts
    for item in all_data.get("gdelt", []):
        if isinstance(item, dict) and item.get("category") == "conflict":
            country = item.get("country", "")
            if country and len(country) == 2:
                key = f"conflict_{country.upper()}"
                metrics[key] = metrics.get(key, 0) + 1

    return metrics


def _detect_trend(points: List[dict], metric_name: str) -> Optional[dict]:
    """Detect trend from historical data points for a single metric."""
    if len(points) < 5:
        return None

    values = [p["v"] for p in points[-20:]]
    recent = values[-5:]
    older = values[:-5] if len(values) > 5 else values[:3]

    if not older or all(v == 0 for v in older):
        return None

    recent_avg = statistics.mean(recent)
    older_avg = statistics.mean(older)

    if older_avg == 0:
        if recent_avg > 0:
            change_pct = 100.0
        else:
            return None
    else:
        change_pct = ((recent_avg - older_avg) / abs(older_avg)) * 100

    # Sustained increase: 3+ consecutive scans above previous average
    consecutive_above = 0
    for v in reversed(recent):
        if v > older_avg * 1.1:
            consecutive_above += 1
        else:
            break

    # Acceleration: rate of change increasing
    if len(values) >= 8:
        first_half_slope = values[len(values)//2] - values[0]
        second_half_slope = values[-1] - values[len(values)//2]
        accelerating = second_half_slope > first_half_slope * 1.5 and second_half_slope > 0
    else:
        accelerating = False

    # Breakpoint: sudden jump (latest value > 2 stddev above mean)
    if len(values) >= 5:
        try:
            mu = statistics.mean(values[:-1])
            sd = statistics.stdev(values[:-1])
            if sd > 0:
                z_score = (values[-1] - mu) / sd
                breakpoint = z_score > 2.5
            else:
                breakpoint = values[-1] > mu * 2 if mu > 0 else False
        except statistics.StatisticsError:
            breakpoint = False
            z_score = 0
    else:
        breakpoint = False
        z_score = 0

    if abs(change_pct) < 15 and consecutive_above < 3 and not breakpoint:
        return None

    trend_type = "stable"
    if breakpoint:
        trend_type = "breakpoint"
    elif consecutive_above >= 4 and accelerating:
        trend_type = "accelerating_increase"
    elif consecutive_above >= 3:
        trend_type = "sustained_increase"
    elif change_pct > 30:
        trend_type = "rising"
    elif change_pct < -30:
        trend_type = "declining"

    if trend_type == "stable":
        return None

    return {
        "metric": metric_name,
        "trend": trend_type,
        "change_pct": round(change_pct, 1),
        "recent_avg": round(recent_avg, 1),
        "baseline_avg": round(older_avg, 1),
        "latest_value": values[-1],
        "consecutive_above": consecutive_above,
        "accelerating": accelerating,
        "data_points": len(points),
        "z_score": round(z_score, 2) if breakpoint else None,
    }


def _format_alert(trend: dict) -> str:
    """Generate a human-readable trend alert."""
    metric = trend["metric"].replace("_", " ").title()
    t = trend["trend"]

    if t == "breakpoint":
        return f"BREAKPOINT: {metric} spiked to {trend['latest_value']} (z={trend['z_score']}, baseline {trend['baseline_avg']})"
    elif t == "accelerating_increase":
        return f"ACCELERATING: {metric} up {trend['change_pct']}% and accelerating ({trend['consecutive_above']} consecutive increases)"
    elif t == "sustained_increase":
        return f"SUSTAINED RISE: {metric} up {trend['change_pct']}% over {trend['consecutive_above']} scans (now {trend['recent_avg']} vs baseline {trend['baseline_avg']})"
    elif t == "rising":
        return f"RISING: {metric} up {trend['change_pct']}% (now {trend['recent_avg']} vs baseline {trend['baseline_avg']})"
    elif t == "declining":
        return f"DECLINING: {metric} down {abs(trend['change_pct'])}% (now {trend['recent_avg']} vs baseline {trend['baseline_avg']})"
    return f"TREND: {metric} — {t} ({trend['change_pct']}%)"


PRIORITY_METRICS = {
    "gdelt_conflict", "adsb_military", "weather_alerts", "earthquakes",
    "ransomware", "safecast_elevated", "ucdp_events", "fires",
    "futures_cl_chg", "futures_gc_chg", "futures_vix_chg",
}


def detect_trends(all_data: dict) -> List[dict]:
    """Main entry point — called from atlas.py during each scan.

    Records current metrics, compares against history, returns trend alerts.
    """
    history = _load_history()
    now = datetime.now(timezone.utc).isoformat()

    current_metrics = _extract_metrics(all_data)

    for metric_name, value in current_metrics.items():
        if metric_name not in history["metrics"]:
            history["metrics"][metric_name] = []
        history["metrics"][metric_name].append({"t": now, "v": value})

    trends = []
    for metric_name, points in history["metrics"].items():
        trend = _detect_trend(points, metric_name)
        if trend:
            trend["alert"] = _format_alert(trend)
            trend["priority"] = "high" if metric_name in PRIORITY_METRICS else "normal"
            trends.append(trend)

    trends.sort(key=lambda t: (0 if t["priority"] == "high" else 1, -abs(t.get("change_pct", 0))))

    history["alerts"] = [
        {"time": now, "count": len(trends), "top": trends[0]["alert"] if trends else None}
    ] + history.get("alerts", [])[:100]

    _save_history(history)

    log.info("Trend engine: %d metrics tracked, %d trends detected", len(current_metrics), len(trends))
    return trends


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        h = _load_history()
        print(f"Metrics tracked: {len(h.get('metrics', {}))}")
        print(f"Alert history entries: {len(h.get('alerts', []))}")
        for m, points in sorted(h.get("metrics", {}).items()):
            if points:
                print(f"  {m}: {len(points)} data points, latest={points[-1]['v']}")
    elif len(sys.argv) > 1 and sys.argv[1] == "--alerts":
        h = _load_history()
        for a in h.get("alerts", [])[:10]:
            print(f"  [{a['time'][:16]}] {a.get('count', 0)} trends — {a.get('top', 'none')}")
    else:
        print("Usage: atlas_trends.py --status | --alerts")
