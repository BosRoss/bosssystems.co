#!/usr/bin/env python3
"""
scrub_pipeline.py — Clean the lead pipeline and prospect targets of unreachable PAIN_REVIEW leads.

Strategy flip: PAIN_REVIEW businesses don't answer their customers AND don't answer BOSS.
Prioritize NO_WEBSITE leads that are actually reachable.

Categories:
  REMOVE  — Has PAIN_REVIEW but NOT NO_WEBSITE (unreachable + has website = worthless)
  DEMOTE  — Has PAIN_REVIEW AND NO_WEBSITE (needs website but won't answer; keep at WARM, -30 score)
  KEEP    — NO_WEBSITE without PAIN_REVIEW (GOLD — reachable + needs us)
  KEEP    — Neither signal (neutral, keep as-is)

Safe to run multiple times (idempotent). Backs up before modifying. Standard library only.
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone


DATA_DIR = os.path.expanduser("~/Library/Application Support/BOSS/atlas_data")
LEADS_FILE = os.path.join(DATA_DIR, "leads_queue.json")
TARGETS_FILE = os.path.join(DATA_DIR, "prospect_targets.json")

TODAY = datetime.now().strftime("%Y%m%d")


def has_pain_signal(signals):
    """Check if any signal indicates PAIN_REVIEW or already-renamed UNREACHABLE."""
    for s in signals:
        if "PAIN_REVIEW(" in s or "UNREACHABLE(" in s:
            return True
    return False


def already_processed(signals):
    """Check if signals have already been renamed to UNREACHABLE (idempotency)."""
    return any("UNREACHABLE(" in s for s in signals) and not any("PAIN_REVIEW(" in s for s in signals)


def has_pain_signal_target(signals):
    """Check pain signals in prospect_targets format (PAIN:'xxx')."""
    for s in signals:
        if s.startswith("PAIN:") or s.startswith("UNREACHABLE:"):
            return True
    return False


def already_processed_target(signals):
    """Check if target signals have already been renamed to UNREACHABLE (idempotency)."""
    return any(s.startswith("UNREACHABLE:") for s in signals) and not any(s.startswith("PAIN:") for s in signals)


def has_no_website_signal(signals):
    """Check if NO_WEBSITE is in the signals list."""
    return any(s == "NO_WEBSITE" for s in signals)


def rename_pain_to_unreachable_lead(signals):
    """Rename PAIN_REVIEW('xxx') to UNREACHABLE('xxx') in leads_queue signals."""
    result = []
    for s in signals:
        if "PAIN_REVIEW(" in s:
            result.append(s.replace("PAIN_REVIEW(", "UNREACHABLE("))
        else:
            result.append(s)
    return result


def rename_pain_to_unreachable_target(signals):
    """Rename PAIN:'xxx' to UNREACHABLE:'xxx' in prospect_targets signals."""
    result = []
    for s in signals:
        if s.startswith("PAIN:'") or s.startswith('PAIN:"'):
            result.append(s.replace("PAIN:", "UNREACHABLE:", 1))
        else:
            result.append(s)
    return result


def backup_file(filepath):
    """Create a dated backup if one doesn't already exist for today."""
    bak_path = f"{filepath}.bak_{TODAY}"
    if os.path.exists(bak_path):
        print(f"  Backup already exists: {os.path.basename(bak_path)} (skipping)")
        return False
    shutil.copy2(filepath, bak_path)
    print(f"  Backed up: {os.path.basename(bak_path)}")
    return True


def process_leads(data):
    """Process leads_queue.json. Returns (modified_data, stats)."""
    leads = data.get("leads", [])

    # Count before
    total_before = len(leads)
    pain_before = sum(1 for l in leads if has_pain_signal(l.get("signals_hit", [])))
    noweb_before = sum(1 for l in leads if has_no_website_signal(l.get("signals_hit", [])))

    removed = []
    demoted = []
    kept = []

    for lead in leads:
        signals = lead.get("signals_hit", [])
        pain = has_pain_signal(signals)
        noweb = has_no_website_signal(signals)

        if pain and not noweb:
            # REMOVE: unreachable + already has website
            removed.append(lead)
        elif pain and noweb:
            # DEMOTE: needs website but won't answer
            lead["tier"] = "WARM"
            if not already_processed(signals):
                # Only reduce score on first run (idempotent)
                lead["score"] = max(0, lead.get("score", 0) - 30)
                lead["signals_hit"] = rename_pain_to_unreachable_lead(signals)
            demoted.append(lead)
        else:
            # KEEP: either gold (noweb, no pain) or neutral
            kept.append(lead)

    # Combine demoted + kept, sort by score descending
    final_leads = kept + demoted
    final_leads.sort(key=lambda l: l.get("score", 0), reverse=True)

    data["leads"] = final_leads
    data["last_purge"] = datetime.now(timezone.utc).isoformat()
    data["purge_stats"] = {
        "date": TODAY,
        "type": "pain_review_scrub",
        "removed": len(removed),
        "demoted": len(demoted),
        "kept": len(kept),
        "before": total_before,
        "after": len(final_leads),
    }

    stats = {
        "total_before": total_before,
        "pain_before": pain_before,
        "noweb_before": noweb_before,
        "removed": len(removed),
        "demoted": len(demoted),
        "kept": len(kept),
        "total_after": len(final_leads),
        "final_leads": final_leads,
    }

    return data, stats


def process_targets(data):
    """Process prospect_targets.json. Returns (modified_data, stats)."""
    targets = data.get("targets", [])

    total_before = len(targets)
    pain_before = sum(1 for t in targets if has_pain_signal_target(t.get("signals", [])))
    # For targets, NO_WEBSITE can be in signals OR has_web=False
    noweb_before = sum(
        1 for t in targets
        if has_no_website_signal(t.get("signals", [])) or not t.get("has_web", True)
    )

    removed = []
    demoted = []
    kept = []

    for target in targets:
        signals = target.get("signals", [])
        pain_list = target.get("pain", [])

        # Pain from signals or from pain field
        pain = has_pain_signal_target(signals) or bool(pain_list)
        # No website from signals or has_web field
        noweb = has_no_website_signal(signals) or not target.get("has_web", True)

        if pain and not noweb:
            removed.append(target)
        elif pain and noweb:
            target["tier"] = "WARM"
            if not already_processed_target(signals):
                # Only reduce score on first run (idempotent)
                target["score"] = max(0, target.get("score", 0) - 30)
                target["signals"] = rename_pain_to_unreachable_target(signals)
            demoted.append(target)
        else:
            kept.append(target)

    final_targets = kept + demoted
    final_targets.sort(key=lambda t: t.get("score", 0), reverse=True)

    data["targets"] = final_targets
    data["last_updated"] = datetime.now(timezone.utc).isoformat()

    stats = {
        "total_before": total_before,
        "pain_before": pain_before,
        "noweb_before": noweb_before,
        "removed": len(removed),
        "demoted": len(demoted),
        "kept": len(kept),
        "total_after": len(final_targets),
        "final_targets": final_targets,
    }

    return data, stats


def count_tiers(items, tier_key="tier"):
    """Count items by tier."""
    tiers = {}
    for item in items:
        t = item.get(tier_key, "UNKNOWN")
        tiers[t] = tiers.get(t, 0) + 1
    return tiers


def print_report(lead_stats, target_stats):
    """Print the scrub report."""
    print()
    print("PIPELINE SCRUB REPORT")
    print("=====================")
    print()

    # Leads
    print("--- LEADS QUEUE ---")
    print(f"Before: {lead_stats['total_before']} leads "
          f"({lead_stats['pain_before']} with pain, "
          f"{lead_stats['noweb_before']} no website)")
    print(f"Removed: {lead_stats['removed']} (pain + has website -- unreachable)")
    print(f"Demoted: {lead_stats['demoted']} (pain + no website -- kept at WARM)")
    print(f"Kept: {lead_stats['kept']} (no pain -- reachable)")
    print(f"After: {lead_stats['total_after']} leads")
    print()

    tiers = count_tiers(lead_stats["final_leads"])
    print("New composition:")
    for tier_name in ["SUPERNICHE", "HOT", "WARM"]:
        count = tiers.get(tier_name, 0)
        if count > 0:
            print(f"  {tier_name}: {count}")
    for tier_name in sorted(tiers.keys()):
        if tier_name not in ["SUPERNICHE", "HOT", "WARM"] and tiers[tier_name] > 0:
            print(f"  {tier_name}: {tiers[tier_name]}")
    print()

    print("Top 5 leads (highest score):")
    for i, lead in enumerate(lead_stats["final_leads"][:5], 1):
        name = lead.get("business_name", "Unknown")
        score = lead.get("score", 0)
        tier = lead.get("tier", "?")
        signals = lead.get("signals_hit", [])
        print(f"  {i}. {name} | Score: {score} | Tier: {tier} | Signals: {signals}")
    print()

    # Targets
    print("--- PROSPECT TARGETS ---")
    print(f"Before: {target_stats['total_before']} targets "
          f"({target_stats['pain_before']} with pain, "
          f"{target_stats['noweb_before']} no website)")
    print(f"Removed: {target_stats['removed']} (pain + has website -- unreachable)")
    print(f"Demoted: {target_stats['demoted']} (pain + no website -- kept at WARM)")
    print(f"Kept: {target_stats['kept']} (no pain -- reachable)")
    print(f"After: {target_stats['total_after']} targets")
    print()

    tiers = count_tiers(target_stats["final_targets"])
    print("New composition:")
    for tier_name in ["SUPERNICHE", "HOT", "WARM"]:
        count = tiers.get(tier_name, 0)
        if count > 0:
            print(f"  {tier_name}: {count}")
    for tier_name in sorted(tiers.keys()):
        if tier_name not in ["SUPERNICHE", "HOT", "WARM"] and tiers[tier_name] > 0:
            print(f"  {tier_name}: {tiers[tier_name]}")
    print()

    total_removed = lead_stats["removed"] + target_stats["removed"]
    total_demoted = lead_stats["demoted"] + target_stats["demoted"]
    print(f"TOTAL REMOVED: {total_removed} | TOTAL DEMOTED: {total_demoted}")
    print("=====================")
    print()


def main():
    print(f"Pipeline scrub starting ({TODAY})")
    print()

    # Verify files exist
    for f in [LEADS_FILE, TARGETS_FILE]:
        if not os.path.exists(f):
            print(f"ERROR: {f} not found")
            return

    # Create backups
    print("Backups:")
    backup_file(LEADS_FILE)
    backup_file(TARGETS_FILE)
    print()

    # Load data
    with open(LEADS_FILE, "r") as f:
        leads_data = json.load(f)

    with open(TARGETS_FILE, "r") as f:
        targets_data = json.load(f)

    # Process
    leads_data, lead_stats = process_leads(leads_data)
    targets_data, target_stats = process_targets(targets_data)

    # Save
    with open(LEADS_FILE, "w") as f:
        json.dump(leads_data, f, indent=2)
    print(f"Saved: {os.path.basename(LEADS_FILE)} ({lead_stats['total_after']} leads)")

    with open(TARGETS_FILE, "w") as f:
        json.dump(targets_data, f, indent=2)
    print(f"Saved: {os.path.basename(TARGETS_FILE)} ({target_stats['total_after']} targets)")

    # Report
    print_report(lead_stats, target_stats)


if __name__ == "__main__":
    main()
