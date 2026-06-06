#!/usr/bin/env python3
"""
Client Guide & Course Generator
Generates per-client guide JSON + learning course from their client record.
Stores output in clients/{id}_guide.json — loaded by client-guide.html.

Usage:
  python3 client_guide_generator.py generate <client_id>
  python3 client_guide_generator.py generate-all
  python3 client_guide_generator.py deploy <client_id>
  python3 client_guide_generator.py deploy-all
"""

import json, os, sys, urllib.request, base64, hashlib
from pathlib import Path
from datetime import datetime

BOSS_HQ = Path(__file__).parent.parent
CLIENTS_DIR = BOSS_HQ / "clients"
WEBSITE_DIR = BOSS_HQ / "website"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

BUSINESS_KNOWLEDGE = {
    "hvac": {
        "display": "HVAC",
        "peak_season": "Late April through August (cooling), November through February (heating), spring tune-up rush in March-April, and a fall breakdown window in September-October when summer stress exposes equipment failures",
        "avg_job_value": "$400-14,000 (service calls to full system replacements)",
        "missed_call_cost": "HVAC jobs range from $400 service calls to $10,000+ replacements — every missed call is one of those going to whoever answers first",
        "tips": [
            "Summer is when you're busiest AND when phones ring most — your AI catches the calls you can't",
            "Emergency calls at night are worth 2-3x a normal job — your AI captures the info and alerts you so you can call back within 30 minutes",
            "Maintenance plan customers call to renew in spring — your AI handles renewal scheduling",
            "When your techs are in attics or under houses, they can't answer phones — that's exactly when the AI earns its keep"
        ],
        "growth": [
            "Ask every happy customer for a Google review within 24 hours of finishing the job — 5 stars is the #1 way HVAC companies get new customers",
            "Maintenance plans are recurring revenue — offer $279/year for 2 tune-ups, priority scheduling, and a 10% parts discount. Only promise response times you can actually hit.",
            "Partner with real estate agents — offer free or discounted HVAC inspections on their listings. You get exclusive referrals, they get smoother closings",
            "Post photos of your work on Google Business Profile — the old unit nameplate showing its age, the new system installed, your tech finding the problem in the attic"
        ]
    },
    "plumbing": {
        "display": "Plumbing",
        "peak_season": "Year-round (peaks in winter for frozen pipes, summer for sewer)",
        "avg_job_value": "$300-1,800",
        "missed_call_cost": "Emergency plumbing calls run $300-$800+ and go to whoever answers first — miss it and they call the next number",
        "tips": [
            "Emergency plumbing is where the money is — your AI answers those panic calls 24/7",
            "Callers often don't know what's wrong — your AI asks the right questions to triage before you arrive",
            "Weekend and holiday calls pay premium rates — your AI catches every single one"
        ],
        "growth": [
            "Drain cleaning is a gateway service — offer it to get in the door, then upsell the bigger job",
            "Water heater replacements are high-margin — your AI can quote ballpark prices to pre-qualify",
            "Join your local BNI or chamber group — plumber referrals from other trades are gold"
        ]
    },
    "electrician": {
        "display": "Electrical",
        "peak_season": "Spring through fall (new construction, storm damage)",
        "avg_job_value": "$250-2,000",
        "missed_call_cost": "Electrical jobs range from $250 service calls to $3,000-8,000 panel upgrades — every missed call is revenue walking to whoever answers",
        "tips": [
            "Generator installations spike before and after storms — your AI captures those calls instantly",
            "Most people call 2-3 electricians for quotes — the first one to answer almost always gets the job",
            "Your AI handles the initial quote questions so you can focus on the work, not the phone"
        ],
        "growth": [
            "EV charger installations are growing fast — add it to your service list",
            "Smart home wiring is a premium upsell — offer it with every panel job",
            "Home inspectors need electricians on speed dial — build those relationships"
        ]
    },
    "roofing": {
        "display": "Roofing",
        "peak_season": "Spring and fall (plus storm damage year-round)",
        "avg_job_value": "$5,000-15,000",
        "missed_call_cost": "One missed roof replacement call is $8,000-15,000 walking out the door",
        "tips": [
            "After a hailstorm, phones ring off the hook — your AI handles the surge while you're on a roof",
            "Insurance claim calls are complex — your AI collects the basics so you can follow up prepared",
            "Roof inspections are your lead generator — your AI books those free inspections all day"
        ],
        "growth": [
            "Storm chasing works — when weather hits, your AI is already catching every call",
            "Gutter installation is easy add-on revenue with every roof job",
            "Before-and-after photo galleries on your Google profile build massive trust"
        ]
    },
    "lawn": {
        "display": "Lawn Care",
        "peak_season": "March through October",
        "avg_job_value": "$50-200 per visit",
        "missed_call_cost": "A recurring weekly customer is worth $2,400-4,800 per year — losing them to a missed call is expensive",
        "tips": [
            "Most lawn care calls come while you're mowing — your AI answers so you never miss a new customer",
            "Recurring customers are your bread and butter — your AI books the first visit that leads to weekly service",
            "Spring is when everyone calls — your AI handles the rush so you don't lose leads"
        ],
        "growth": [
            "Upsell seasonal services — aeration, overseeding, leaf removal, fertilization",
            "Offer a referral discount — $10 off for every neighbor who signs up",
            "Monthly billing instead of per-visit makes your income more predictable"
        ]
    },
    "auto_repair": {
        "display": "Auto Repair",
        "peak_season": "Year-round",
        "avg_job_value": "$200-1,500",
        "missed_call_cost": "A check-engine-light call is $300-800 in diagnostics and repair",
        "tips": [
            "People call about car problems when they happen — not during your business hours. Your AI catches those calls.",
            "Your AI can explain common services and approximate pricing without you stopping work",
            "Oil change customers become transmission repair customers — your AI builds that pipeline"
        ],
        "growth": [
            "Text customers when their next service is due — it fills slow weeks",
            "Offer a free inspection with every oil change to find upsell opportunities",
            "Google reviews matter more for auto repair than almost any other business"
        ]
    },
    "general": {
        "display": "Business",
        "peak_season": "Varies by industry",
        "avg_job_value": "Varies",
        "missed_call_cost": "Every missed call is a potential customer going to your competitor",
        "tips": [
            "Your AI answers every call — no voicemail, no hold music, no missed opportunities",
            "After-hours calls are often the most valuable — people calling at night are ready to buy",
            "Your AI handles the routine questions so you can focus on the work that makes money"
        ],
        "growth": [
            "Ask every customer for a Google review — it's the #1 way small businesses get found",
            "Track where your calls come from — your dashboard shows you which marketing actually works",
            "Follow up with every quote that didn't close — a simple text 3 days later closes 15% more"
        ]
    }
}


def load_client(client_id: str) -> dict:
    path = CLIENTS_DIR / f"{client_id}.json"
    if not path.exists():
        print(f"ERROR: Client file not found: {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def generate_guide(client: dict) -> dict:
    biz_type = client.get("business_type", "general")
    knowledge = BUSINESS_KNOWLEDGE.get(biz_type, BUSINESS_KNOWLEDGE["general"])
    stack = client.get("stack", {})
    owner = client.get("owner_name", "there")
    biz_name = client.get("business_name", "your business")

    # Build stack summary
    active_features = []
    stack_sections = []
    for key, comp in stack.items():
        if not comp.get("enabled"):
            continue
        active_features.append(comp.get("description", key))
        section = {
            "id": key,
            "title": _stack_title(key),
            "what_it_does": comp.get("description", ""),
            "features": comp.get("features", []),
        }
        if key == "receptionist":
            section["services"] = comp.get("services_configured", [])
            section["hours"] = comp.get("business_hours", "")
            section["emergency"] = comp.get("emergency_protocol", "")
        if key == "dashboard":
            section["url"] = comp.get("url", "")
            section["login_code"] = comp.get("login_code", "")
        stack_sections.append(section)

    # 10-second summary
    feature_count = len(active_features)
    summary = f"You have {feature_count} tools working for {biz_name} right now. "
    if stack.get("receptionist", {}).get("enabled"):
        summary += f"Your phone is answered 24/7 — every call gets handled, every appointment gets booked, and you see everything on your dashboard. "
    if stack.get("follow_up", {}).get("enabled"):
        summary += "People who call but don't book get a follow-up automatically. "
    summary += "Nothing falls through the cracks."

    # Quick-start checklist
    checklist = []
    if stack.get("receptionist", {}).get("enabled"):
        phone = stack["receptionist"].get("phone_number", "your AI number")
        checklist.append(f"Forward your business line to {phone} — on most carriers, dial *72 then the number. Or give this number out directly.")
        checklist.append("Call your AI number yourself to hear how it sounds")
    if stack.get("dashboard", {}).get("enabled"):
        url = stack["dashboard"].get("url", "bosssystems.co/client-dashboard.html")
        code = stack["dashboard"].get("login_code", "your code")
        checklist.append(f"Log into your dashboard at {url} with code {code}")
        checklist.append("Check your dashboard once a day to see who called")
    checklist.append("Text Boston (903-714-6162) if anything needs changing — same-day updates")
    if stack.get("receptionist", {}).get("enabled"):
        checklist.append("If you have employees or subcontractors who take calls, let them know the AI is handling the main line now")

    # Disabled features → "coming next" upsell hooks
    coming_next = []
    for key, comp in stack.items():
        if not comp.get("enabled") and comp.get("description"):
            coming_next.append({
                "id": key,
                "title": _stack_title(key),
                "description": comp["description"],
                "cta": "Text Boston to add this to your plan"
            })

    # Build results section (add seasonal note)
    results = dict(client.get("results_expected", {}))
    if results:
        results["seasonal_note"] = "These numbers vary by season — expect higher volume in peak months and lighter months in the off-season. Month 1 is usually lighter as the number gets established."

    # Something-not-right troubleshooting
    troubleshooting = [
        {"problem": "AI said something wrong to a customer", "action": "Text Boston with what happened — same-day fix. Your AI's script gets updated immediately."},
        {"problem": "No calls showing on dashboard", "action": "Check that your phone is forwarding to your AI number. Call it yourself to test. If it rings but doesn't show up, text Boston."},
        {"problem": "Number not working", "action": "Call your AI number from your personal phone. If it doesn't answer, text Boston immediately — this gets fixed within the hour."},
        {"problem": "Wrong time or double-booking", "action": "Text Boston the details. The booking logic gets adjusted same-day. In the meantime, call the customer directly to reschedule."},
        {"problem": "After-hours emergency alert came in", "action": "Check your dashboard for the caller's info and what's happening. Call them back within 30 minutes — they're expecting your call. If they mention burning smells or sparks, tell them to shut the breaker off and call 911 if needed."},
    ]

    guide = {
        "client_id": client["client_id"],
        "business_name": biz_name,
        "owner_name": owner,
        "business_type": biz_type,
        "business_type_display": knowledge["display"],
        "plan": client.get("plan", "starter"),
        "generated_at": datetime.now().isoformat(),

        "summary": summary,
        "checklist": checklist,
        "stack_sections": stack_sections,

        "field_tips": knowledge["tips"],
        "growth_tips": knowledge["growth"],
        "peak_season": knowledge["peak_season"],
        "missed_call_cost": knowledge["missed_call_cost"],

        "results_expected": results,
        "coming_next": coming_next,
        "troubleshooting": troubleshooting,

        "contact": {
            "name": "Boston",
            "phone": "903-714-6162",
            "method": "Text is fastest. Changes go live same day."
        }
    }

    return guide


def generate_course(client: dict) -> dict:
    biz_type = client.get("business_type", "general")
    knowledge = BUSINESS_KNOWLEDGE.get(biz_type, BUSINESS_KNOWLEDGE["general"])
    stack = client.get("stack", {})
    biz_name = client.get("business_name", "your business")

    lessons = []

    # Lesson 1: Getting the most out of your AI
    if stack.get("receptionist", {}).get("enabled"):
        lessons.append({
            "title": f"Getting the Most Out of Your AI Phone System",
            "objective": "Know exactly what your AI can and can't do, so you use it to its full potential",
            "content": [
                f"Your AI answers every call to {biz_name} — day, night, weekends, holidays. Here's how to make sure it's working as hard as possible for you.",
                f"**What it handles automatically:** {', '.join(stack['receptionist'].get('features', []))}",
                f"**Services it knows:** {', '.join(stack['receptionist'].get('services_configured', []))}",
                "**How to update it:** Text Boston at 903-714-6162. New services, new hours, vacation days, price changes — anything. Updates go live same day.",
                "**The biggest win:** The calls that come in when you're on a job — in an attic, under a house, driving between sites. Those are the ones worth the most — and your AI catches every single one."
            ],
            "quiz": {
                "question": "A customer calls your AI asking about duct cleaning, but you just added that service last month. The AI doesn't mention it. What happened?",
                "options": [
                    "The AI only knows what it's been told — text Boston to add the new service",
                    "The AI will learn it automatically after a few more calls",
                    "The AI is broken and needs to be replaced",
                    "The customer asked the wrong way — have them call back"
                ],
                "correct": 0,
                "hint": "Your AI doesn't browse your website or guess. If something changes, text Boston and it gets updated same day."
            },
            "first_step": "Call your own AI number right now. Listen to how it sounds. If anything feels off, text Boston."
        })

    # Lesson 2: Reading your dashboard
    if stack.get("dashboard", {}).get("enabled"):
        lessons.append({
            "title": "Reading Your Dashboard Like a Pro",
            "objective": "Spot the patterns in your call data that tell you where money is being made or lost",
            "content": [
                f"Your dashboard at {stack['dashboard'].get('url', 'bosssystems.co/client-dashboard.html')} shows every call your AI handled.",
                "**What to look for daily:** Each call entry shows what the caller needed, whether they booked, and the full conversation transcript.",
                "**After-hours calls:** These are gold. Check how many calls came in outside your normal hours — those would have gone to voicemail without the AI.",
                "**Patterns to notice:** Which days are busiest? What time do most calls come in? What do people ask about most? This tells you where to focus your marketing.",
                "**The number that matters most:** Booked appointments. That's revenue. Track it weekly and you'll see exactly what your AI is worth."
            ],
            "quiz": {
                "question": "You check your dashboard and see 50 calls this week but only 4 booked appointments. What does this tell you?",
                "options": [
                    "Something is off with how calls convert — read the transcripts to find out why",
                    "The AI is working great because it answered 50 calls",
                    "You need to run more ads to get better callers",
                    "The dashboard is probably showing bad data"
                ],
                "correct": 0,
                "hint": "High calls + low bookings means something in the conversation isn't closing. The transcripts show you exactly where."
            },
            "first_step": "Log into your dashboard and check the last 7 days. Count the after-hours calls — those are jobs you would have missed."
        })

    # Lesson 3: Maximizing your AI during peak season
    lessons.append({
        "title": f"Maximizing Your AI During {knowledge['display']} Season",
        "objective": f"Use your AI strategically during your busiest months so you capture every dollar",
        "content": [
            f"**Your peak season:** {knowledge['peak_season']}. This is when your AI earns its keep — phones ring most when you're busiest.",
            f"**What's at stake:** {knowledge['avg_job_value']} per job. {knowledge['missed_call_cost']}",
            "**During peak months, track two numbers on your dashboard:** after-hours calls caught (these are emergency jobs worth 2-3x normal rate) and calls that came in while you were on a job. Add up the job values — that's what your AI saved you.",
            "**Before peak season starts:** Text Boston to make sure your AI knows your current services and pricing. Update your hours if they change for summer. Make sure your emergency protocol is set the way you want it.",
            "**After peak season:** Review your dashboard for the busiest months. How many calls came in? How many booked? Use this to plan staffing and marketing for next year."
        ],
        "quiz": {
            "question": f"It's July, 102 degrees, and you're replacing a compressor in an attic. Your phone rings 4 times. Without the AI, what most likely happens?",
            "options": [
                "All 4 go to voicemail — 3 of them call your competitor before you climb down",
                "They'll all leave messages and patiently wait for you to call back",
                "Your wife or office manager catches every one",
                "It doesn't matter — you're too busy to take new jobs in peak season"
            ],
            "correct": 0,
            "hint": "85% of callers who hit voicemail never call back. They call the next number on Google."
        },
        "first_step": "Check your dashboard right now — how many calls came in while you were on a job this week? That number times your average job value is what your AI saved you."
    })

    # Lesson 4: Money management basics (before growth — know your numbers first)
    lessons.append({
        "title": "Knowing Your Numbers",
        "objective": "Track the 3 numbers that tell you if your business is healthy",
        "content": [
            "You don't need a spreadsheet or an accounting degree. Just track three things:",
            "**1. What came in this week** — total revenue from all jobs",
            f"**2. What went out this week** — fuel, materials, insurance, your AI ({_extract_monthly(client.get('pricing', '$60/mo'))}), everything",
            "**3. What's left** — that's your profit. If it's growing, you're doing it right.",
            "**Set aside 20-30% for taxes.** Texas has no state income tax, but you still owe federal + self-employment tax. If you're making over $1,000/quarter, you likely owe quarterly estimated taxes (April 15, June 15, September 15, January 15). Talk to a tax professional for your specific situation — this is general guidance, not tax advice.",
            "**Your AI shows you part of the picture:** Dashboard call volume tells you demand. If calls are up but revenue is flat, you're not converting. If calls are down but revenue is up, your average job value is growing."
        ],
        "quiz": {
            "question": "You had a great month — $18,000 in revenue, $11,000 in expenses. What should you do with the $7,000 left over?",
            "options": [
                "Set aside 20-30% for quarterly taxes, keep the rest as profit",
                "Spend it all on new equipment while you have it",
                "It's all yours — taxes are only due in April",
                "Put all of it in savings and don't touch it until next year"
            ],
            "correct": 0,
            "hint": "Uncle Sam wants his cut every quarter. Set aside 20-30% before you count it as yours."
        },
        "first_step": "Open your phone's notes app right now. Write down last week's revenue and expenses. Do this every Sunday night — 5 minutes."
    })

    # Lesson 5: Growth strategies (after numbers — grow once you know your margins)
    lessons.append({
        "title": "Getting More Customers Without Spending More",
        "objective": "Concrete free and low-cost ways to fill your schedule starting this week",
        "content": [
            "Your AI handles the phones and you know your numbers. Now let's fill them up with more calls.",
        ] + [f"**Strategy:** {tip}" for tip in knowledge["growth"]] + [
            "**The compound effect:** More reviews = more calls = more bookings = more reviews. Your AI handles the calls in the middle — you just need to start the cycle with great work and asking for reviews."
        ],
        "quiz": {
            "question": "You just finished an AC install and the homeowner says 'y'all did a great job.' What's the most valuable thing to do right now?",
            "options": [
                "Ask them to leave a Google review while they're still happy",
                "Hand them a stack of business cards to pass around",
                "Offer them 10% off their next service call",
                "Just say thanks and get to the next job"
            ],
            "correct": 0,
            "hint": "A 5-star Google review works for you 24/7. Business cards get lost. Discounts cost you money. Reviews make you money."
        },
        "first_step": "Text your last 3 happy customers right now: 'Hey [name], if you were happy with the work, would you mind leaving us a quick Google review? It really helps.'"
    })

    course = {
        "client_id": client["client_id"],
        "business_name": client.get("business_name", ""),
        "business_type": biz_type,
        "mode": "client",
        "generated_at": datetime.now().isoformat(),
        "lessons": lessons
    }

    return course


def _stack_title(key: str) -> str:
    titles = {
        "receptionist": "Your AI Phone System",
        "post_call_handler": "Call Logging",
        "dashboard": "Your Dashboard",
        "follow_up": "Automatic Follow-Ups",
        "review_request": "Review Requests",
        "missed_call_text": "Missed Call Texts",
    }
    return titles.get(key, key.replace("_", " ").title())


def _hash_code(dashboard_code: str) -> str:
    return hashlib.sha256(dashboard_code.upper().encode()).hexdigest()


def _extract_monthly(pricing: str) -> str:
    if not pricing:
        return "$60/mo"
    if "+" not in pricing:
        return pricing
    for part in pricing.split("+"):
        if "/mo" in part.lower():
            return part.strip()
    return pricing.split("+")[-1].strip()


def save_guide(client_id: str, guide: dict, course: dict):
    out = {
        "guide": guide,
        "course": course,
    }
    path = CLIENTS_DIR / f"{client_id}_guide.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved: {path}")

    client = load_client(client_id)
    dash_code = client.get("dashboard_code", "")
    if not dash_code:
        print("WARNING: No dashboard_code in client record — cannot generate web guide")
        return path, None

    hashed = _hash_code(dash_code)
    web_path = WEBSITE_DIR / "client_guides" / f"{hashed}.json"
    web_path.parent.mkdir(exist_ok=True)
    with open(web_path, "w") as f:
        json.dump(out, f)
    print(f"Saved: {web_path}")

    return path, web_path


def deploy_guide(client_id: str):
    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not set")
        return False

    client = load_client(client_id)
    dash_code = client.get("dashboard_code", "")
    if not dash_code:
        print(f"ERROR: No dashboard_code for {client_id}")
        return False

    hashed = _hash_code(dash_code)
    web_path = WEBSITE_DIR / "client_guides" / f"{hashed}.json"
    if not web_path.exists():
        print(f"ERROR: Guide not found at {web_path}. Generate first.")
        return False

    with open(web_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    gh_path = f"client_guides/{hashed}.json"

    # Check if file exists
    req = urllib.request.Request(
        f"https://api.github.com/repos/BosRoss/bosssystems.co/contents/{gh_path}",
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
    )
    sha = None
    try:
        with urllib.request.urlopen(req) as resp:
            sha = json.load(resp).get("sha")
    except urllib.error.HTTPError:
        pass

    body = {
        "message": f"Update client guide: {client_id}",
        "content": content,
    }
    if sha:
        body["sha"] = sha

    put_req = urllib.request.Request(
        f"https://api.github.com/repos/BosRoss/bosssystems.co/contents/{gh_path}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(put_req) as resp:
            result = json.load(resp)
        print(f"Deployed: {gh_path} (sha: {result['content']['sha'][:8]})")
        return True
    except Exception as e:
        print(f"Deploy failed: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "generate":
        if len(sys.argv) < 3:
            print("Usage: python3 client_guide_generator.py generate <client_id>")
            sys.exit(1)
        client_id = sys.argv[2]
        client = load_client(client_id)
        guide = generate_guide(client)
        course = generate_course(client)
        save_guide(client_id, guide, course)
        print(f"\nGuide summary: {guide['summary'][:100]}...")
        print(f"Checklist items: {len(guide['checklist'])}")
        print(f"Stack sections: {len(guide['stack_sections'])}")
        print(f"Course lessons: {len(course['lessons'])}")

    elif cmd == "generate-all":
        for f in CLIENTS_DIR.glob("*.json"):
            if f.name.endswith("_guide.json"):
                continue
            client_id = f.stem
            client = load_client(client_id)
            guide = generate_guide(client)
            course = generate_course(client)
            save_guide(client_id, guide, course)
            print(f"  {client_id}: {len(course['lessons'])} lessons")

    elif cmd == "deploy":
        if len(sys.argv) < 3:
            print("Usage: python3 client_guide_generator.py deploy <client_id>")
            sys.exit(1)
        deploy_guide(sys.argv[2])

    elif cmd == "deploy-all":
        for f in CLIENTS_DIR.glob("*.json"):
            if f.name.endswith("_guide.json"):
                continue
            deploy_guide(f.stem)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
