#!/usr/bin/env python3
"""
Weekly Client Summary Generator
Pulls Retell call data for each active client, generates a summary,
and sends it to Boston via ntfy (who forwards to the client).

Usage:
    python3 client_weekly_summary.py              # Generate all client summaries
    python3 client_weekly_summary.py --client wickham  # Single client
    python3 client_weekly_summary.py --dry-run     # Preview without sending

Designed to run Monday mornings via LaunchAgent or cron.
"""

import os, sys, json, time
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError

RETELL_KEY = os.environ.get("RETELL_KEY", "")
NTFY_CHANNEL = os.environ.get("NTFY_CHANNEL", "bossai-bostonrossall-alerts")

CLIENTS = {
    "wickham": {
        "name": "Wickham Lawn Care",
        "agent_id": "agent_6d02eab9ce7293fc7ef932b2cb",
        "phone": "(972) 314-5057",
        "avg_ticket": 65,
        "owner": "Wickham",
        "monthly_fee": 50,
        "start_date": "2026-06-08",
    },
}

def client_tenure_days(client):
    sd = client.get("start_date")
    if not sd:
        return 0
    return (datetime.now() - datetime.strptime(sd, "%Y-%m-%d")).days

BOOKING_KEYWORDS = [
    "got you down for", "booked", "on the calendar", "scheduled",
    "appointment", "we can get you", "set up for",
]
AFTER_HOURS_START = 18
AFTER_HOURS_END = 7


def retell_list_calls(agent_id, days=7):
    url = "https://api.retellai.com/v2/list-calls"
    cutoff = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)
    payload = json.dumps({
        "filter_criteria": {"agent_id": [agent_id]},
        "limit": 200,
        "sort_order": "descending",
    }).encode()
    req = Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {RETELL_KEY}")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=15) as resp:
            calls = json.loads(resp.read())
    except (URLError, Exception) as e:
        print(f"  [ERROR] Retell API: {e}")
        return []

    recent = []
    for c in calls:
        ts = c.get("start_timestamp", 0)
        if ts >= cutoff:
            recent.append(c)
    return recent


def analyze_calls(calls, avg_ticket):
    total = len(calls)
    after_hours = 0
    booked = 0
    total_duration_s = 0

    for c in calls:
        dur = c.get("duration_ms", 0) / 1000
        total_duration_s += dur

        ts_ms = c.get("start_timestamp", 0)
        if ts_ms:
            hour = datetime.utcfromtimestamp(ts_ms / 1000).hour - 5  # rough CT
            if hour < 0:
                hour += 24
            if hour >= AFTER_HOURS_START or hour < AFTER_HOURS_END:
                after_hours += 1

        transcript = c.get("transcript", "")
        if isinstance(transcript, list):
            transcript = " ".join(t.get("content", "") for t in transcript)
        transcript_lower = transcript.lower() if transcript else ""
        if any(kw in transcript_lower for kw in BOOKING_KEYWORDS):
            booked += 1

    missed_value = booked * avg_ticket

    best_save = None
    for c in calls:
        ts_ms = c.get("start_timestamp", 0)
        if ts_ms:
            hour = datetime.utcfromtimestamp(ts_ms / 1000).hour - 5
            if hour < 0:
                hour += 24
            if hour >= AFTER_HOURS_START or hour < AFTER_HOURS_END:
                transcript = c.get("transcript", "")
                if isinstance(transcript, list):
                    transcript = " ".join(t.get("content", "") for t in transcript)
                if any(kw in transcript.lower() for kw in BOOKING_KEYWORDS):
                    day_name = datetime.utcfromtimestamp(ts_ms / 1000).strftime("%A")
                    time_str = f"{hour % 12 or 12}:{datetime.utcfromtimestamp(ts_ms / 1000).strftime('%M')} {'PM' if hour >= 12 else 'AM'}"
                    best_save = {"day": day_name, "time": time_str, "value": avg_ticket}
                    break

    return {
        "total_calls": total,
        "after_hours": after_hours,
        "booked": booked,
        "avg_duration_s": total_duration_s / total if total else 0,
        "estimated_revenue": missed_value,
        "best_save": best_save,
    }


def format_summary(client, stats):
    name = client["name"]
    fee = client["monthly_fee"]
    total = stats["total_calls"]
    booked = stats["booked"]
    after_hours = stats["after_hours"]
    revenue = stats["estimated_revenue"]
    save = stats.get("best_save")

    if total == 0:
        return (
            f"📞 {name} — Weekly Summary\n"
            f"Your AI was on duty 168 hours straight this week — covered nights, weekends, lunch breaks.\n"
            f"No calls came in, but you're protected for the 2 AM Saturday emergency.\n"
            f"You paid ${fee}. A full-time receptionist would've cost $1,050 this week."
        )

    lines = [
        f"📞 {name} — Weekly Summary",
        f"Calls handled: {total}",
    ]
    if booked:
        lines.append(f"Appointments booked: {booked}")
    if after_hours:
        lines.append(f"After-hours calls answered: {after_hours}")
    if revenue:
        lines.append(f"Estimated revenue from bookings: ${revenue:,.0f}")
        lines.append(f"You paid ${fee}. Your AI caught ${revenue:,.0f}.")
    lines.append(f"Average call duration: {stats['avg_duration_s']:.0f}s")

    if save:
        lines.append(f"💡 Best save: {save['day']} at {save['time']} — after-hours booking worth ~${save['value']}. 85% of voicemail callers never call back — this one didn't go to voicemail.")

    if revenue > fee:
        roi = revenue / fee
        lines.append(f"ROI this week: {roi:.0f}x your monthly cost")

    return "\n".join(lines)


def format_client_text(client, stats):
    """The text Boston would forward to the client."""
    name = client["name"]
    total = stats["total_calls"]
    booked = stats["booked"]
    after_hours = stats["after_hours"]
    save = stats.get("best_save")

    if total == 0:
        return (
            f"Hey {client['owner']} — weekly update from your AI.\n"
            f"No calls this past week, but your line was on duty 168 hours straight — nights, weekends, lunch breaks.\n"
            f"When the 9 PM Saturday emergency call comes in, you're covered.\n"
            f"If you want to test it, call {client['phone']} anytime."
        )

    msg = f"Hey {client['owner']} — weekly update: your AI handled {total} call{'s' if total != 1 else ''} this week"
    parts = []
    if booked:
        parts.append(f"booked {booked} appointment{'s' if booked != 1 else ''}")
    if after_hours:
        parts.append(f"answered {after_hours} after-hours call{'s' if after_hours != 1 else ''}")
    if parts:
        msg += ", " + ", ".join(parts)
    msg += "."
    if save:
        msg += f" Best catch: {save['day']} at {save['time']} — that's a ~${save['value']} job your voicemail would've lost. 85% of callers who hit voicemail never call back."
    elif stats["estimated_revenue"]:
        msg += f" Estimated revenue from those bookings: ${stats['estimated_revenue']:,.0f}."
    msg += " Let me know if you need anything tweaked."
    return msg


def format_month1_kitchen_table(client, stats):
    """Month 1 (day 25-31): screenshot-able ROI summary the wife sees at the kitchen table."""
    tenure = client_tenure_days(client)
    if tenure < 25 or tenure > 35:
        return None
    name = client["owner"]
    fee = client["monthly_fee"]
    total = stats["total_calls"]
    after_hours = stats["after_hours"]
    revenue = stats["estimated_revenue"]
    roi = f"{revenue / fee:.0f}x" if revenue > 0 and fee > 0 else "covered"
    return (
        f"Hey {name} — month 1 update:\n"
        f"• Calls answered: {total}\n"
        f"• After-hours calls caught: {after_hours}\n"
        f"• Estimated revenue from bookings: ${revenue:,.0f}\n"
        f"• Your cost: ${fee}/mo\n"
        f"• ROI: {roi}\n"
        f"The ${fee} charge hits tomorrow. That's it — no surprises."
    )


def format_month2_trigger(client, stats):
    """Month 2 (day 50-60): highlight a specific story, fight the invisible-when-working phase."""
    tenure = client_tenure_days(client)
    if tenure < 50 or tenure > 65:
        return None
    name = client["owner"]
    save = stats.get("best_save")
    if save:
        return (
            f"Hey {name} — here's the one that stood out: {save['day']} at {save['time']}, "
            f"someone called about a ~${save['value']} job. "
            f"That was a call your voicemail would've lost. Everything running smooth?"
        )
    return (
        f"Hey {name} — quiet month, but your AI was on duty 168 hours straight every week. "
        f"When the 2 AM Saturday emergency comes in, you're covered. That's what the ${client['monthly_fee']} buys — insurance."
    )


def format_month3_churn(client, stats):
    """Month 3 (day 80-95): the churn cliff. Tenure-based retention messaging."""
    tenure = client_tenure_days(client)
    if tenure < 80 or tenure > 100:
        return None
    name = client["owner"]
    total = stats["total_calls"]
    revenue = stats["estimated_revenue"]
    fee = client["monthly_fee"]
    if revenue > fee * 2:
        return (
            f"Hey {name} — 3 months in. Your AI has caught ${revenue:,.0f} in jobs so far. "
            f"Your cost: ${fee * 3}. The guys who stay past month 3 are the ones making real money off this."
        )
    if total > 0:
        return (
            f"Hey {name} — 3-month check-in. Your AI is answering every call, "
            f"24/7. Most contractors who cancel wish they hadn't by the next busy season. "
            f"Everything good on your end?"
        )
    return (
        f"Hey {name} — I know it's been quiet. Your AI's been on duty every night and weekend for 3 months straight. "
        f"When the calls come, you won't miss a single one. If you want to pause instead of cancel, just text me — "
        f"everything stays saved, zero charge."
    )


def format_bookkeeper(client, stats):
    """Line-item format for bookkeeper/accountant review."""
    name = client["name"]
    fee = client["monthly_fee"]
    total = stats["total_calls"]
    revenue = stats["estimated_revenue"]
    tenure = client_tenure_days(client)
    months = max(1, tenure // 30)
    total_cost = fee * months
    return (
        f"{name} — BOSS Systems AI Phone Service\n"
        f"Period: {months} month{'s' if months != 1 else ''}\n"
        f"Monthly charge: ${fee:.2f}\n"
        f"Total paid to date: ${total_cost:.2f}\n"
        f"Calls answered this period: {total}\n"
        f"Estimated revenue from AI-caught bookings: ${revenue:,.2f}\n"
        f"Category: Business telephone answering service (fully deductible)"
    )


def send_ntfy(title, message):
    url = f"https://ntfy.sh/{NTFY_CHANNEL}"
    data = message.encode()
    req = Request(url, data=data, method="POST")
    req.add_header("Title", title)
    req.add_header("Tags", "chart_with_upwards_trend")
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  [ERROR] ntfy: {e}")
        return False


def run(client_filter=None, dry_run=False):
    if not RETELL_KEY:
        print("ERROR: RETELL_KEY not set. Run: source scripts/config.sh")
        sys.exit(1)

    targets = CLIENTS
    if client_filter:
        key = client_filter.lower()
        if key not in CLIENTS:
            print(f"Unknown client: {client_filter}. Available: {', '.join(CLIENTS.keys())}")
            sys.exit(1)
        targets = {key: CLIENTS[key]}

    for key, client in targets.items():
        print(f"\n{'='*50}")
        print(f"Client: {client['name']}")
        print(f"{'='*50}")

        calls = retell_list_calls(client["agent_id"])
        print(f"  Calls in last 7 days: {len(calls)}")

        stats = analyze_calls(calls, client["avg_ticket"])
        summary = format_summary(client, stats)
        client_text = format_client_text(client, stats)

        milestone_msg = (
            format_month1_kitchen_table(client, stats)
            or format_month2_trigger(client, stats)
            or format_month3_churn(client, stats)
        )

        print(f"\n--- BOSS Summary (ntfy) ---")
        print(summary)
        print(f"\n--- Text to Forward to Client ---")
        print(client_text)
        if milestone_msg:
            print(f"\n--- MILESTONE TEXT (send instead of weekly) ---")
            print(milestone_msg)
        print(f"\n--- BOOKKEEPER FORMAT ---")
        print(format_bookkeeper(client, stats))

        if not dry_run:
            full_msg = summary + "\n\n--- SEND TO CLIENT ---\n" + client_text
            if milestone_msg:
                full_msg += "\n\n--- MILESTONE (send THIS instead of weekly) ---\n" + milestone_msg
            full_msg += "\n\n--- BOOKKEEPER FORMAT ---\n" + format_bookkeeper(client, stats)
            ok = send_ntfy(f"Weekly: {client['name']}", full_msg)
            print(f"\n  ntfy sent: {'OK' if ok else 'FAILED'}")
        else:
            print(f"\n  [DRY RUN] Would send via ntfy")

    print(f"\nDone. {len(targets)} client(s) processed.")


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    client_filter = None
    if "--client" in args:
        idx = args.index("--client")
        if idx + 1 < len(args):
            client_filter = args[idx + 1]

    run(client_filter=client_filter, dry_run=dry_run)
