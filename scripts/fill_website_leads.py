#!/usr/bin/env python3
"""One-shot script to fill pipeline with 200 NO_WEBSITE leads across all territories.
Only keeps businesses that have no website and no pain/unreachable signals.
Deduplicates against existing pipeline and called numbers."""

import json
import time
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from prospect_scorer import hunt, PAIN_KEYWORDS, _check_budget, _record_spend, COST_PER_SEARCH

ATLAS_DIR = Path.home() / "Library/Application Support/BOSS/atlas_data"
QUEUE_FILE = ATLAS_DIR / "leads_queue.json"
CALLED_FILE = ATLAS_DIR / "called_numbers.json"
TARGETS_FILE = ATLAS_DIR / "prospect_targets.json"

BANNED_AC = ['903', '430', '985', '318', '504', '337', '225', '850',
             '605', '828', '361', '830', '307', '406', '701']

TARGET_COUNT = 200

MARKETS = [
    # MS
    ("HVAC contractor", "Corinth MS"), ("plumber", "Corinth MS"), ("electrician", "Corinth MS"),
    ("HVAC contractor", "Meridian MS"), ("plumber", "Meridian MS"), ("electrician", "Meridian MS"),
    ("roofing contractor", "Meridian MS"), ("HVAC contractor", "Tupelo MS"),
    ("plumber", "Tupelo MS"), ("electrician", "Tupelo MS"), ("roofing contractor", "Tupelo MS"),
    ("HVAC contractor", "Starkville MS"), ("plumber", "Starkville MS"),
    ("HVAC contractor", "Columbus MS"), ("plumber", "Columbus MS"),
    ("HVAC contractor", "Greenville MS"), ("HVAC contractor", "Vicksburg MS"),
    ("plumber", "Vicksburg MS"), ("electrician", "Vicksburg MS"),
    ("HVAC contractor", "Hattiesburg MS"), ("plumber", "Hattiesburg MS"),
    ("roofing contractor", "Hattiesburg MS"), ("auto repair", "Tupelo MS"),
    ("auto repair", "Meridian MS"), ("law firm", "Meridian MS"),
    # AR
    ("HVAC contractor", "Batesville AR"), ("plumber", "Batesville AR"),
    ("electrician", "Batesville AR"), ("HVAC contractor", "Jonesboro AR"),
    ("plumber", "Jonesboro AR"), ("electrician", "Jonesboro AR"),
    ("roofing contractor", "Jonesboro AR"), ("HVAC contractor", "Pine Bluff AR"),
    ("plumber", "Pine Bluff AR"), ("HVAC contractor", "Searcy AR"),
    ("plumber", "Searcy AR"), ("HVAC contractor", "Mountain Home AR"),
    ("plumber", "Mountain Home AR"), ("roofing contractor", "Batesville AR"),
    ("auto repair", "Jonesboro AR"), ("law firm", "Jonesboro AR"),
    # OK
    ("HVAC contractor", "Durant OK"), ("plumber", "Durant OK"), ("electrician", "Durant OK"),
    ("HVAC contractor", "Ada OK"), ("plumber", "Ada OK"), ("electrician", "Ada OK"),
    ("HVAC contractor", "McAlester OK"), ("plumber", "McAlester OK"),
    ("roofing contractor", "McAlester OK"), ("HVAC contractor", "Ardmore OK"),
    ("plumber", "Ardmore OK"), ("roofing contractor", "Durant OK"),
    ("auto repair", "Ada OK"), ("HVAC contractor", "Stillwater OK"),
    ("plumber", "Stillwater OK"),
    # AL
    ("HVAC contractor", "Tuscaloosa AL"), ("plumber", "Tuscaloosa AL"),
    ("electrician", "Tuscaloosa AL"), ("HVAC contractor", "Decatur AL"),
    ("plumber", "Decatur AL"), ("HVAC contractor", "Dothan AL"),
    ("plumber", "Dothan AL"), ("roofing contractor", "Tuscaloosa AL"),
    ("HVAC contractor", "Florence AL"), ("plumber", "Florence AL"),
    ("electrician", "Florence AL"), ("auto repair", "Tuscaloosa AL"),
    # TN
    ("HVAC contractor", "Jackson TN"), ("plumber", "Jackson TN"),
    ("electrician", "Jackson TN"), ("HVAC contractor", "Cookeville TN"),
    ("plumber", "Cookeville TN"), ("roofing contractor", "Jackson TN"),
    ("HVAC contractor", "Dyersburg TN"), ("plumber", "Dyersburg TN"),
    ("HVAC contractor", "Columbia TN"), ("plumber", "Columbia TN"),
    ("auto repair", "Jackson TN"),
    # NM
    ("HVAC contractor", "Hobbs NM"), ("plumber", "Hobbs NM"), ("electrician", "Hobbs NM"),
    ("HVAC contractor", "Carlsbad NM"), ("plumber", "Carlsbad NM"),
    ("HVAC contractor", "Clovis NM"), ("plumber", "Clovis NM"),
    ("roofing contractor", "Hobbs NM"), ("auto repair", "Hobbs NM"),
]

def load_existing_phones():
    phones = set()
    if QUEUE_FILE.exists():
        data = json.loads(QUEUE_FILE.read_text())
        for l in data.get("leads", []):
            p = str(l.get("phone", "")).strip()
            if p:
                phones.add(p)
    if CALLED_FILE.exists():
        data = json.loads(CALLED_FILE.read_text())
        for n in data.get("numbers", []):
            phones.add(str(n).strip())
    return phones

def has_pain_signal(result):
    sigs = " ".join(result.get("signals", [])).lower()
    for kw in ["unreachable", "pain", "voicemail", "no answer", "no response",
               "never answered", "never responded", "left a message",
               "called several", "no one answered", "hard to reach",
               "impossible to reach", "straight to voicemail"]:
        if kw in sigs:
            return True
    pain_list = result.get("pain", [])
    if pain_list:
        return True
    return False

def main():
    existing_phones = load_existing_phones()
    print(f"Existing phones to skip: {len(existing_phones)}")

    queue_data = json.loads(QUEUE_FILE.read_text()) if QUEUE_FILE.exists() else {"leads": []}
    existing_leads = queue_data.get("leads", [])
    print(f"Current pipeline: {len(existing_leads)} leads")

    new_leads = []
    seen_phones = set(existing_phones)
    searches_done = 0

    for niche, city in MARKETS:
        if len(existing_leads) + len(new_leads) >= TARGET_COUNT:
            print(f"\nHit {TARGET_COUNT} target. Stopping.")
            break

        can_spend, reason = _check_budget()
        if not can_spend:
            print(f"BUDGET BLOCKED: {reason}")
            break

        print(f"Scanning: {niche} in {city}...", end=" ")
        try:
            results = hunt(niche, city, verbose=False)
            searches_done += 1
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        added_this = 0
        for r in results:
            phone = str(r.get("phone", "")).strip()
            if not phone or len(phone) < 10:
                continue
            if phone in seen_phones:
                continue
            if phone[:3] in BANNED_AC:
                continue
            if r.get("has_web", True):
                continue
            if has_pain_signal(r):
                continue

            seen_phones.add(phone)
            lead = {
                "lead_id": f"web_{phone}",
                "business_name": r.get("name", "Unknown"),
                "phone": phone,
                "phone_e164": f"+1{phone}",
                "email": "",
                "niche": niche,
                "area": city,
                "state": city.split()[-1] if " " in city else "",
                "tier": r.get("tier", "HOT"),
                "score": r.get("score", 40),
                "signals_hit": r.get("signals", []),
                "route": "call_queue",
                "status": "queued",
                "timing": "immediate",
                "contact_after": None,
                "capacity_flag": None,
                "trigger_pitch": r.get("opener", ""),
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "rating": r.get("rating", 0),
                "review_count": r.get("reviews", 0),
                "has_website": False,
                "address": r.get("address", ""),
                "website_buildable": r.get("website_buildable", False),
                "responsive": r.get("responsive", False),
                "google_data": r.get("google_data", {}),
            }
            new_leads.append(lead)
            added_this += 1

        print(f"{len(results)} results, {added_this} added (total: {len(existing_leads) + len(new_leads)})")
        time.sleep(0.5)

    all_leads = existing_leads + new_leads
    all_leads.sort(key=lambda x: -x.get("score", 0))

    queue_data["leads"] = all_leads
    QUEUE_FILE.write_text(json.dumps(queue_data, indent=2, default=str) + "\n")

    print(f"\n{'='*60}")
    print(f"  PIPELINE FILL COMPLETE")
    print(f"{'='*60}")
    print(f"  Searches: {searches_done} (~${searches_done * 0.032:.2f})")
    print(f"  New leads added: {len(new_leads)}")
    print(f"  Total pipeline: {len(all_leads)}")
    print(f"  All NO_WEBSITE, zero pain signals")

    by_tier = {}
    for l in all_leads:
        t = l.get("tier", "?")
        by_tier[t] = by_tier.get(t, 0) + 1
    print(f"  Tiers: {by_tier}")

    by_state = {}
    for l in all_leads:
        s = l.get("state", "?")
        by_state[s] = by_state.get(s, 0) + 1
    print(f"  States: {by_state}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
