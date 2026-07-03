#!/usr/bin/env python3
"""
BOSS Systems — Daily Cost Tracker
Reads spend data from all tracked APIs, writes daily summary to boss_state.json.
Run daily via cron or manually: python3 cost_tracker.py
"""
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    CT = ZoneInfo("America/Chicago")
except ImportError:
    from datetime import timezone, timedelta
    CT = timezone(timedelta(hours=-5))

BOSS_HQ = Path.home() / "Desktop" / "BOSS_HQ"
ATLAS_DATA = BOSS_HQ / "atlas_data"
SPEND_TRACKER = ATLAS_DATA / "spend_tracker.json"
COST_LOG = ATLAS_DATA / "cost_log.json"
STATE_FILE = ATLAS_DATA / "boss_state.json"

PLACES_CREDIT_TOTAL = 300.00
PLACES_CREDIT_EXPIRY = "2026-08-07"
COST_PER_PLACES_QUERY = 0.032


def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def get_places_costs():
    tracker = load_json(SPEND_TRACKER, {"total_spent": 0, "requests": []})
    total = tracker.get("total_spent", 0)
    requests = tracker.get("requests", [])
    today = datetime.now(CT).strftime("%Y-%m-%d")
    today_reqs = [r for r in requests if r.get("timestamp", "")[:10] == today]
    today_cost = len(today_reqs) * COST_PER_PLACES_QUERY

    expiry = datetime.strptime(PLACES_CREDIT_EXPIRY, "%Y-%m-%d").replace(tzinfo=CT)
    days_remaining = (expiry - datetime.now(CT)).days

    return {
        "total_spent": round(total, 2),
        "credit_remaining": round(PLACES_CREDIT_TOTAL - total, 2),
        "today_cost": round(today_cost, 2),
        "today_queries": len(today_reqs),
        "total_queries": len(requests),
        "days_until_expiry": max(0, days_remaining),
        "pct_used": round(total / PLACES_CREDIT_TOTAL * 100, 1),
    }


def get_retell_costs():
    retell_key = os.environ.get("RETELL_KEY", "")
    if not retell_key:
        return {"tracked": False, "reason": "no RETELL_KEY in env"}
    try:
        req = urllib.request.Request(
            "https://api.retellai.com/v2/list-calls",
            data=json.dumps({"limit": 1}).encode(),
            headers={
                "Authorization": f"Bearer {retell_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        return {"tracked": True, "note": "call-level cost data not available via API"}
    except Exception as e:
        return {"tracked": False, "reason": str(e)[:100]}


def build_daily_entry():
    now = datetime.now(CT)
    places = get_places_costs()

    return {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        "google_places": places,
        "retell": {"tracked": False, "note": "no per-call cost API available"},
        "anthropic": {"tracked": False, "note": "no spend API available"},
        "n8n": {"tracked": False, "note": "execution count only, no cost data"},
        "total_tracked_spend": places["total_spent"],
        "total_tracked_remaining": places["credit_remaining"],
    }


def update_boss_state(entry):
    state = load_json(STATE_FILE, {})
    state["costs"] = {
        "last_updated": entry["timestamp"],
        "google_places": entry["google_places"],
        "total_tracked_spend": entry["total_tracked_spend"],
        "total_tracked_remaining": entry["total_tracked_remaining"],
    }
    state["last_updated"] = entry["timestamp"]
    save_json(STATE_FILE, state)


def main():
    entry = build_daily_entry()

    log = load_json(COST_LOG, {"entries": []})
    today = entry["date"]
    log["entries"] = [e for e in log["entries"] if e.get("date") != today]
    log["entries"].append(entry)
    log["entries"] = log["entries"][-90:]
    save_json(COST_LOG, log)

    update_boss_state(entry)

    print(f"Cost tracker — {today}")
    print(f"  Google Places: ${entry['google_places']['total_spent']:.2f} spent, ${entry['google_places']['credit_remaining']:.2f} remaining")
    print(f"  Today: {entry['google_places']['today_queries']} queries (${entry['google_places']['today_cost']:.2f})")
    print(f"  Credit expires in {entry['google_places']['days_until_expiry']} days")
    print(f"  Written to: {COST_LOG}")
    print(f"  State updated: {STATE_FILE}")


if __name__ == "__main__":
    main()
