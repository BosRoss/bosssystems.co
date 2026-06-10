#!/usr/bin/env python3
"""
BOSS Business AI Analyzer
Usage: python3 business_analyzer.py "Tyler HVAC" "Tyler TX"
OR: python3 business_analyzer.py --type "hvac" --city "Tyler TX"

Analyzes any business and generates a complete AI Transformation Plan.
Figures out exactly what to automate, in what order, and what it will cost/save.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# CREDENTIALS
# ──────────────────────────────────────────────────────────────────────────────
GOOGLE_PLACES_KEY = os.environ.get("GOOGLE_PLACES_KEY", "")
ANTHROPIC_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
NTFY_CHANNEL      = "bossai-bostonrossall-alerts"

BOSS_HQ           = Path("/Users/bostonrossall/Desktop/BOSS_HQ")
CLIENTS_DIR       = BOSS_HQ / "clients"

# ──────────────────────────────────────────────────────────────────────────────
# BUSINESS TYPE KNOWLEDGE BASE
# ──────────────────────────────────────────────────────────────────────────────
BUSINESS_TYPE_META = {
    "hvac": {
        "google_category": "hvac contractor",
        "avg_job_value": 480,
        "avg_job_source": "ServiceTitan 2024 HVAC benchmark",
        "keywords": ["hvac", "heating", "cooling", "air conditioning", "ac repair", "furnace"],
        "pain_signals": ["missed calls during peak season", "seasonal overload (May-Aug)", "no-shows", "billing delays"],
        "specific_automations": ["hvac_filter_reminders", "hvac_seasonal_maintenance", "hvac_warranty_tracker"],
    },
    "plumber": {
        "google_category": "plumber",
        "avg_job_value": 380,
        "avg_job_source": "HomeAdvisor 2024 plumbing service average",
        "keywords": ["plumber", "plumbing", "pipe repair", "drain cleaning", "water heater"],
        "pain_signals": ["emergency calls missed after hours", "permit tracking is manual", "quote delays lose jobs"],
        "specific_automations": ["plumber_emergency_routing", "plumber_permit_tracker"],
    },
    "electrician": {
        "google_category": "electrician",
        "avg_job_value": 420,
        "avg_job_source": "HomeAdvisor 2024 electrical service average",
        "keywords": ["electrician", "electrical", "wiring", "panel upgrade"],
        "pain_signals": ["quote turnaround too slow", "permit tracking is manual", "missed after-hours calls"],
        "specific_automations": ["electrician_emergency_routing", "electrician_permit_tracker"],
    },
    "roofer": {
        "google_category": "roofing contractor",
        "avg_job_value": 6500,
        "avg_job_source": "Angi 2024 roof repair/replacement average",
        "keywords": ["roofing", "roof repair", "roof replacement", "gutters"],
        "pain_signals": ["slow storm-chasing speed", "insurance confusion loses deals", "seasonal demand spikes"],
        "specific_automations": ["roofing_storm_lead_gen", "roofing_insurance_automation"],
    },
    "junk_removal": {
        "google_category": "junk removal",
        "avg_job_value": 310,
        "keywords": ["junk removal", "haul away", "debris removal", "cleanout"],
        "pain_signals": ["call volume spikes go unanswered", "pricing inconsistency", "same-day scheduling chaos"],
        "specific_automations": ["dispatch_automation"],
    },
    "cleaning": {
        "google_category": "house cleaning service",
        "avg_job_value": 175,
        "keywords": ["cleaning", "maid service", "house cleaning", "janitorial"],
        "pain_signals": ["repeat booking management is manual", "crew scheduling overhead", "review generation neglected"],
        "specific_automations": ["dispatch_automation"],
    },
    "auto_repair": {
        "google_category": "auto repair shop",
        "avg_job_value": 300,
        "keywords": ["auto repair", "mechanic", "oil change", "brake repair"],
        "pain_signals": ["appointment scheduling is phone-only", "parts availability causes delays", "customer follow-up dropped"],
        "specific_automations": ["auto_repair_service_reminders", "auto_repair_parts_tracker"],
    },
    "law_firm": {
        "google_category": "law firm",
        "avg_job_value": 3000,
        "keywords": ["attorney", "lawyer", "law firm", "legal"],
        "pain_signals": ["intake overwhelm", "document collection is manual and slow", "missed consultation calls"],
        "specific_automations": ["law_firm_intake", "law_firm_document_requests"],
    },
    "pest_control": {
        "google_category": "pest control service",
        "avg_job_value": 200,
        "keywords": ["pest control", "exterminator", "termite", "bug control"],
        "pain_signals": ["recurring appointment management is manual", "seasonal demand spikes", "upsell opportunities missed"],
        "specific_automations": ["pest_control_recurring_reminders", "pest_control_seasonal_campaigns"],
    },
    "lawn_care": {
        "google_category": "lawn care service",
        "avg_job_value": 80,
        "keywords": ["lawn care", "landscaping", "grass cutting", "yard service"],
        "pain_signals": ["route optimization wasted daily", "recurring billing is manual", "weather rescheduling chaos"],
        "specific_automations": ["lawn_care_route_optimizer", "lawn_care_weather_reschedule"],
    },
    "restaurant": {
        "google_category": "restaurant",
        "avg_job_value": 45,
        "keywords": ["restaurant", "dining", "food", "cafe"],
        "pain_signals": ["reservation management is phone-only", "no-shows waste tables", "review response is neglected"],
        "specific_automations": ["restaurant_reservations", "restaurant_review_response"],
    },
    "gym": {
        "google_category": "gym",
        "avg_job_value": 60,
        "keywords": ["gym", "fitness", "crossfit", "personal training"],
        "pain_signals": ["class booking is phone/walk-in only", "membership churn is high", "no-shows fill slots"],
        "specific_automations": ["gym_class_booking", "gym_membership_renewal"],
    },
    "real_estate": {
        "google_category": "real estate agency",
        "avg_job_value": 8000,
        "keywords": ["real estate", "realtor", "homes for sale", "property"],
        "pain_signals": ["follow-up inconsistency loses deals", "showing coordination is chaotic", "lead nurture falls apart"],
        "specific_automations": ["real_estate_listing_updates"],
    },
    "retail": {
        "google_category": "retail store",
        "avg_job_value": 85,
        "keywords": ["retail", "store", "shop", "boutique"],
        "pain_signals": ["inventory tracking is manual", "customer loyalty is informal", "seasonal promotions are inconsistent"],
        "specific_automations": ["retail_inventory_reorder", "retail_loyalty_program"],
    },
    "dental": {
        "google_category": "dentist",
        "avg_job_value": 350,
        "keywords": ["dentist", "dental", "teeth cleaning", "orthodontist", "dental office"],
        "pain_signals": ["15-20% no-show rate burns chair time", "recall patients lost to competitors", "new patient intake is slow and paper-heavy"],
        "specific_automations": ["dental_appointment_reminders", "dental_recall_system", "dental_new_patient_onboarding"],
    },
    "pressure_washing": {
        "google_category": "pressure washing service",
        "avg_job_value": 275,
        "keywords": ["pressure washing", "power washing", "soft wash", "exterior cleaning"],
        "pain_signals": ["seasonal demand swings", "pricing inconsistency loses jobs", "no follow-up on completed jobs"],
        "specific_automations": ["seasonal_campaigns", "re_engagement_campaign"],
    },
}

PACKAGE_TIERS_BASE = {
    "Starter": {
        "price_setup": 1497,
        "price_monthly": 97,
        "automations": ["phone_receptionist", "missed_call_textback", "payment_collection", "review_request"],
        "description": "Core AI stack — answers calls, texts back misses, collects payment, gets reviews.",
    },
    "Growth": {
        "price_setup": 2997,
        "price_monthly": 247,
        "automations": [
            "phone_receptionist", "missed_call_textback", "payment_collection", "review_request",
            "outbound_caller", "social_media_ai", "competitor_monitor", "re_engagement_campaign",
        ],
        "description": "Full acquisition + retention engine. Finds new customers and keeps old ones coming back.",
    },
    "Full Transformation": {
        "price_setup": 5997,
        "price_monthly": 497,
        "automations": [
            "phone_receptionist", "missed_call_textback", "payment_collection", "review_request",
            "outbound_caller", "social_media_ai", "competitor_monitor", "re_engagement_campaign",
            "quote_generator", "dispatch_automation", "invoice_generator", "seasonal_campaigns", "revenue_dashboard",
        ],
        "description": "Complete AI business transformation. Every process automated. Owner focuses on growth.",
    },
}


def get_package_tiers(business_type):
    """Return package tiers with business-specific automations injected into Growth and Full."""
    meta = BUSINESS_TYPE_META.get(business_type, {})
    specific = meta.get("specific_automations", [])
    tiers = {}
    for name, base in PACKAGE_TIERS_BASE.items():
        tier = dict(base)
        tier["automations"] = list(base["automations"])
        if name == "Growth" and specific:
            tier["automations"].extend(s for s in specific[:1] if s not in tier["automations"])
        elif name == "Full Transformation" and specific:
            tier["automations"].extend(s for s in specific if s not in tier["automations"])
        tiers[name] = tier
    return tiers


PACKAGE_TIERS = PACKAGE_TIERS_BASE


# ──────────────────────────────────────────────────────────────────────────────
# HTTP HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def http_get(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


def http_post(url, payload, headers=None, timeout=10):
    data = json.dumps(payload).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


def slug(name, city):
    combined = f"{name}_{city}".lower()
    for ch in [" ", ",", ".", "/", "\\", "'", '"', "&"]:
        combined = combined.replace(ch, "_")
    while "__" in combined:
        combined = combined.replace("__", "_")
    return combined.strip("_")


def city_state(city_str):
    parts = city_str.strip().rsplit(" ", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip().upper()
    return city_str.strip(), ""


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 1: GOOGLE PLACES RESEARCH
# ──────────────────────────────────────────────────────────────────────────────

def search_places(query, max_results=20):
    url = "https://places.googleapis.com/v1/places:searchText"
    payload = {"textQuery": query, "maxResultCount": min(max_results, 20)}
    headers = {
        "X-Goog-Api-Key": GOOGLE_PLACES_KEY,
        "X-Goog-FieldMask": (
            "places.displayName,places.rating,places.userRatingCount,"
            "places.formattedAddress,places.types,places.websiteUri,"
            "places.internationalPhoneNumber,places.id"
        ),
    }
    try:
        result = http_post(url, payload, headers=headers, timeout=10)
        return result.get("places", [])
    except Exception:
        return []


def get_place_reviews(place_id):
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_PLACES_KEY,
        "X-Goog-FieldMask": "reviews,rating,userRatingCount",
    }
    try:
        result = http_get(url, headers=headers, timeout=10)
        return result.get("reviews", [])
    except Exception:
        return []


def research_business(business_name, city_full, business_type):
    city, state = city_state(city_full)
    meta = BUSINESS_TYPE_META.get(business_type, {})
    google_cat = meta.get("google_category", business_type)

    print(f"\n  [1/4] Searching for '{business_name}' in {city_full}...")
    biz_results = search_places(f"{business_name} {city} {state}", max_results=5)
    target_biz = None
    if biz_results:
        biz_name_lower = business_name.lower()
        for p in biz_results:
            place_name = p.get("displayName", {}).get("text", "").lower()
            if any(word in place_name for word in biz_name_lower.split() if len(word) > 3):
                target_biz = p
                break
        if not target_biz:
            target_biz = biz_results[0]

    print(f"  [2/4] Scanning competitor landscape...")
    competitor_results = search_places(f"{google_cat} {city} {state}", max_results=20)
    local_competitors = [
        p for p in competitor_results
        if city.lower() in p.get("formattedAddress", "").lower()
        or state.lower() in p.get("formattedAddress", "").lower()
    ]
    if not local_competitors:
        local_competitors = competitor_results[:10]

    if target_biz:
        target_id = target_biz.get("id", "")
        local_competitors = [p for p in local_competitors if p.get("id") != target_id]

    print(f"  [3/4] Pulling reviews for pain signal analysis...")
    pain_signals = []
    review_texts = []

    target_place_id = target_biz.get("id", "") if target_biz else ""
    if target_place_id:
        reviews = get_place_reviews(target_place_id)
        for rev in reviews[:5]:
            text = rev.get("text", {}).get("text", "")
            rating = rev.get("rating", 5)
            if text:
                review_texts.append({"rating": rating, "text": text, "source": "target_business"})
                if rating <= 3:
                    text_lower = text.lower()
                    if any(w in text_lower for w in ["call", "phone", "answer", "voicemail", "reach"]):
                        pain_signals.append("Customers cannot reach the business by phone")
                    if any(w in text_lower for w in ["slow", "late", "wait", "hours", "response"]):
                        pain_signals.append("Slow response times cost jobs")
                    if any(w in text_lower for w in ["price", "expensive", "quote", "estimate", "cost"]):
                        pain_signals.append("Pricing transparency needs improvement")
                    if any(w in text_lower for w in ["invoice", "bill", "payment", "charge"]):
                        pain_signals.append("Billing process causes customer friction")
                    if any(w in text_lower for w in ["follow up", "callback", "never called"]):
                        pain_signals.append("Follow-up gaps are losing repeat business")

    for comp in local_competitors[:3]:
        comp_id = comp.get("id", "")
        comp_rating = comp.get("rating", 5)
        if comp_id and comp_rating and comp_rating <= 3.8:
            comp_reviews = get_place_reviews(comp_id)
            for rev in comp_reviews[:3]:
                text = rev.get("text", {}).get("text", "")
                rating = rev.get("rating", 5)
                if text and rating <= 3:
                    review_texts.append({"rating": rating, "text": text, "source": "competitor"})

    pain_signals = list(set(pain_signals))
    for ps in meta.get("pain_signals", []):
        if ps not in pain_signals:
            pain_signals.append(ps)

    print(f"  [4/4] Assessing market position...")
    ratings = [p.get("rating", 0) for p in local_competitors if p.get("rating")]
    review_counts = [p.get("userRatingCount", 0) for p in local_competitors if p.get("userRatingCount")]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
    avg_reviews = int(sum(review_counts) / len(review_counts)) if review_counts else 0
    total_reviews = sum(review_counts)
    low_rated_count = len([p for p in local_competitors if p.get("rating", 5) <= 3.5])
    competitor_count = len(local_competitors)

    has_website = bool(target_biz and target_biz.get("websiteUri"))
    website_url = target_biz.get("websiteUri", "") if target_biz else ""
    target_rating = target_biz.get("rating", None) if target_biz else None
    target_reviews = target_biz.get("userRatingCount", None) if target_biz else None
    target_phone = target_biz.get("internationalPhoneNumber", "") if target_biz else ""
    target_address = target_biz.get("formattedAddress", "") if target_biz else ""

    return {
        "business_name": business_name,
        "city": city,
        "state": state,
        "city_full": city_full,
        "business_type": business_type,
        "target_found": bool(target_biz),
        "target_rating": target_rating,
        "target_reviews": target_reviews,
        "target_phone": target_phone,
        "target_address": target_address,
        "has_website": has_website,
        "website_url": website_url,
        "competitor_count": competitor_count,
        "avg_competitor_rating": avg_rating,
        "avg_competitor_reviews": avg_reviews,
        "total_market_reviews": total_reviews,
        "low_rated_competitors": low_rated_count,
        "pain_signals": pain_signals[:8],
        "recent_reviews": review_texts[:5],
        "competitors": [
            {
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "rating": p.get("rating", "N/A"),
                "reviews": p.get("userRatingCount", 0),
                "address": p.get("formattedAddress", ""),
                "website": p.get("websiteUri", ""),
            }
            for p in local_competitors[:8]
        ],
        "avg_job_value": meta.get("avg_job_value", 300),
        "avg_job_source": meta.get("avg_job_source", "industry average"),
        "specific_automations": meta.get("specific_automations", []),
    }


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 2: CLAUDE ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────

def analyze_with_claude(research, automation_catalog):
    if not ANTHROPIC_KEY:
        print("  [!] No ANTHROPIC_API_KEY found — using rule-based analysis")
        return None

    review_sample = ""
    for rev in research.get("recent_reviews", [])[:3]:
        review_sample += f"  - [{rev['rating']} stars] {rev['text'][:200]}\n"

    pain_list = "\n".join(f"  - {p}" for p in research.get("pain_signals", []))

    catalog_lines = "\n".join(
        f"  {k}: {v['name']} | ${v['annual_value']:,}/yr | ${v['monthly_cost']}/mo | difficulty {v['difficulty']}/5"
        for k, v in list(automation_catalog.items())[:25]
    )

    prompt = f"""You are a business AI automation consultant analyzing a local service business.

BUSINESS PROFILE:
- Name: {research['business_name']}
- Type: {research['business_type']}
- Location: {research['city_full']}
- Google Rating: {research.get('target_rating', 'Not found')} ({research.get('target_reviews', 0)} reviews) [VERIFIED from Google Places]
- Has Website: {research.get('has_website', False)} [VERIFIED from Google Places]
- Avg Job Value: ${research.get('avg_job_value', 300)} [SOURCE: {research.get('avg_job_source', 'industry average')} — NOT verified for this specific business]
- Annual Revenue: UNKNOWN — we do not have this data and should NOT guess it

MARKET CONTEXT:
- Competitors in area: {research.get('competitor_count', 0)}
- Avg competitor rating: {research.get('avg_competitor_rating', 0)} stars
- Low-rated competitors (<=3.5 stars): {research.get('low_rated_competitors', 0)}

PAIN SIGNALS FROM REVIEWS:
{pain_list or '  - No specific signals captured'}

SAMPLE REVIEWS:
{review_sample or '  - No reviews available'}

AUTOMATION CATALOG (key | name | annual_value | monthly_cost | difficulty):
{catalog_lines}

Based on this specific business profile, identify the TOP automations ranked by impact.
Consider: which pain signals map to which automations, highest ROI for this business type, business-specific automations that only apply to this industry.
Return between 8-12 automations — include ALL that are genuinely relevant. Don't pad to 10 if fewer apply. Don't cut at 10 if more are strong fits.

CRITICAL HONESTY RULES:
- Only reference problems you can VERIFY from the Google data (rating, reviews, website, pain signals)
- We do NOT know this business's revenue, call volume, miss rate, or employee count. Do not guess.
- For estimated_annual_value: use CONSERVATIVE numbers based only on the avg job value and reasonable assumptions. Cite what assumption you're making.
- If there's not enough data to estimate a value, say "insufficient data" in why_this_business and set estimated_annual_value to 0
- Do NOT claim phone problems exist unless pain signals from reviews confirm it
- Better to say "we can't estimate this without more data" than to give a fake number
- ALWAYS include business-specific automations from the catalog that match this type — they exist for a reason
- Every why_this_business must state whether the claim is VERIFIED (from Google data) or ESTIMATED (from industry data)

Return a JSON array of objects. Each must have:
- "key": the exact automation key from the catalog
- "name": automation name
- "why_this_business": 1-2 sentence specific reason this matters for THIS business. Only claim verified facts (from Google data). Label estimates as estimates.
- "estimated_annual_value": conservative estimate for this specific business (can differ from catalog — err on low side)
- "priority_score": 1-100 score for this business
- "quick_win": true if buildable and showing ROI within 24 hours

Return ONLY the JSON array, no other text."""

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        result = http_post("https://api.anthropic.com/v1/messages", payload, headers=headers, timeout=30)
        content = result.get("content", [])
        if content and isinstance(content, list):
            text = content[0].get("text", "").strip()
            if text.startswith("["):
                return json.loads(text)
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
    except Exception as e:
        print(f"  [!] Claude analysis failed: {e}")

    return None


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 3: BUILD THE TRANSFORMATION PLAN
# ──────────────────────────────────────────────────────────────────────────────

def build_transformation_plan(research, claude_recs, automation_catalog):
    business_type = research["business_type"]

    sys.path.insert(0, str(BOSS_HQ / "scripts"))
    try:
        from automation_library import get_recommendations, AUTOMATION_CATALOG
        rule_recs = get_recommendations(business_type)
        catalog = AUTOMATION_CATALOG
    except ImportError:
        catalog = automation_catalog
        rule_recs = sorted(
            [{"key": k, **v} for k, v in catalog.items()
             if "all" in v.get("applies_to", []) or business_type in v.get("applies_to", [])],
            key=lambda x: x.get("priority_score", 0),
            reverse=True,
        )

    if claude_recs:
        automations = []
        for rec in claude_recs[:10]:
            key = rec.get("key", "")
            cat_entry = catalog.get(key, {})
            auto = {
                "key": key,
                "name": rec.get("name", cat_entry.get("name", key)),
                "category": cat_entry.get("category", "General"),
                "description": cat_entry.get("description", ""),
                "why_this_business": rec.get("why_this_business", ""),
                "annual_value": rec.get("estimated_annual_value", cat_entry.get("annual_value", 0)),
                "monthly_cost": cat_entry.get("monthly_cost", 20),
                "build_time_hours": cat_entry.get("build_time_hours", 3),
                "build_time_days": round(cat_entry.get("build_time_hours", 3) / 8, 1),
                "difficulty": cat_entry.get("difficulty", 3),
                "tools": cat_entry.get("tools", []),
                "priority_score": rec.get("priority_score", 50),
                "quick_win": rec.get("quick_win", False),
            }
            automations.append(auto)
    else:
        automations = []
        for r in rule_recs[:10]:
            auto = {
                "key": r.get("key", ""),
                "name": r.get("name", ""),
                "category": r.get("category", ""),
                "description": r.get("description", ""),
                "why_this_business": (
                    f"Recommended for {business_type.replace('_',' ')} businesses based on industry data. "
                    f"Value estimate uses industry averages — your actual results depend on call volume, market, and execution."
                ),
                "annual_value": r.get("annual_value", 0),
                "monthly_cost": r.get("monthly_cost", 20),
                "build_time_hours": r.get("build_time_hours", 3),
                "build_time_days": round(r.get("build_time_hours", 3) / 8, 1),
                "difficulty": r.get("difficulty", 3),
                "tools": r.get("tools", []),
                "priority_score": r.get("priority_score", 50),
                "quick_win": r.get("build_time_hours", 10) <= 2,
            }
            automations.append(auto)

    automations.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

    quick_wins  = [a for a in automations if a.get("build_time_hours", 10) <= 2][:3]
    medium_wins = [a for a in automations if 2 < a.get("build_time_hours", 10) <= 8][:4]
    big_wins    = [a for a in automations if a.get("build_time_hours", 10) > 8][:3]
    if not big_wins:
        big_wins = [a for a in automations if a.get("build_time_hours", 0) > 4][:2]

    raw_annual_value = sum(a.get("annual_value", 0) for a in automations)
    total_annual_value = int(raw_annual_value * 0.75 / 100) * 100  # 25% overlap discount
    total_monthly_cost = sum(a.get("monthly_cost", 0) for a in automations)
    roi_ratio = round(total_annual_value / max(total_monthly_cost * 12, 1), 1)

    if total_annual_value > 80000:
        recommended_package = "Full Transformation"
    elif total_annual_value > 40000:
        recommended_package = "Growth"
    else:
        recommended_package = "Starter"

    tiers = get_package_tiers(business_type)
    pkg = tiers[recommended_package]

    return {
        "generated_at": datetime.now().isoformat(),
        "business_name": research["business_name"],
        "city": research["city_full"],
        "business_type": business_type,
        "target_rating": research.get("target_rating"),
        "target_reviews": research.get("target_reviews"),
        "has_website": research.get("has_website", False),
        "website_url": research.get("website_url", ""),
        "competitor_count": research.get("competitor_count", 0),
        "avg_competitor_rating": research.get("avg_competitor_rating", 0),
        "pain_signals": research.get("pain_signals", []),
        "automations": automations,
        "quick_wins": quick_wins,
        "medium_wins": medium_wins,
        "big_wins": big_wins,
        "total_annual_value_unlocked": total_annual_value,
        "total_monthly_cost": total_monthly_cost,
        "roi_ratio": roi_ratio,
        "recommended_package": recommended_package,
        "recommended_package_detail": pkg,
        "analysis_method": "claude+rules" if claude_recs else "rules_only",
    }


# ──────────────────────────────────────────────────────────────────────────────
# TERMINAL REPORT
# ──────────────────────────────────────────────────────────────────────────────

def print_report(plan):
    W = 70
    GOLD  = "\033[33m"
    BOLD  = "\033[1m"
    GREEN = "\033[92m"
    CYAN  = "\033[96m"
    RED   = "\033[91m"
    DIM   = "\033[2m"
    RESET = "\033[0m"

    def hdr(text):
        print(f"\n{GOLD}{BOLD}{'='*W}{RESET}")
        print(f"{GOLD}{BOLD}  {text}{RESET}")
        print(f"{GOLD}{'='*W}{RESET}")

    def sec(text):
        print(f"\n{CYAN}{BOLD}  -- {text} --{RESET}")

    def row(label, value, color=RESET):
        pad = 28 - len(label)
        print(f"  {BOLD}{label}{RESET}{' '*max(pad,1)}{color}{value}{RESET}")

    hdr("BOSS AI TRANSFORMATION PLAN")
    print(f"  {DIM}Generated: {plan['generated_at'][:19]}  |  Method: {plan['analysis_method']}{RESET}")

    sec("BUSINESS PROFILE")
    row("Business:", plan["business_name"])
    row("Type:", plan["business_type"].replace("_", " ").upper())
    row("Location:", plan["city"])
    if plan.get("target_rating"):
        row("Google Rating:", f"{plan['target_rating']} stars ({plan.get('target_reviews', 0)} reviews)")
    else:
        row("Google Rating:", "Not found on Google")
    row("Has Website:", "Yes" if plan.get("has_website") else "No  <-- opportunity to fix")
    row("Competitors:", f"{plan['competitor_count']} in area (avg {plan['avg_competitor_rating']} stars)")

    if plan.get("pain_signals"):
        sec("PAIN SIGNALS DETECTED")
        for ps in plan["pain_signals"][:6]:
            print(f"  {RED}!{RESET}  {ps}")

    sec("TOP 10 AUTOMATION OPPORTUNITIES")
    for i, auto in enumerate(plan["automations"][:10], 1):
        color = GREEN if i <= 3 else (CYAN if i <= 7 else DIM)
        ann_val = auto.get("annual_value", 0)
        mo_cost = auto.get("monthly_cost", 0)
        roi = round(ann_val / max(mo_cost * 12, 1), 1)
        diff = auto.get("difficulty", 3)
        diff_label = "Easy" if diff <= 1 else ("Medium" if diff <= 3 else "Hard")
        print(f"\n  {color}{BOLD}{i}. {auto['name']}{RESET}")
        print(f"     {DIM}{auto['category']}{RESET}")
        print(f"     Value: {GREEN}${ann_val:,}/yr{RESET}  |  Cost: ${mo_cost}/mo  |  ROI: {roi}x  "
              f"|  Build: {auto.get('build_time_hours', '?')}h  |  {diff_label}")
        if auto.get("why_this_business"):
            print(f"     {DIM}{auto['why_this_business']}{RESET}")

    sec("QUICK WINS -- Build Today")
    if plan["quick_wins"]:
        for qw in plan["quick_wins"]:
            print(f"  {GREEN}[TODAY]{RESET}  {qw['name']}")
            print(f"           ${qw['annual_value']:,}/yr  |  {qw['build_time_hours']}h to build")
    else:
        print(f"  {DIM}See medium wins below.{RESET}")

    sec("MEDIUM WINS -- This Week")
    for mw in plan.get("medium_wins", []):
        print(f"  {CYAN}[WEEK]{RESET}   {mw['name']}")
        print(f"           ${mw['annual_value']:,}/yr  |  {mw['build_time_hours']}h to build")

    sec("BIG WINS -- This Month")
    for bw in plan.get("big_wins", []):
        print(f"  {GOLD}[MONTH]{RESET}  {bw['name']}")
        print(f"           ${bw['annual_value']:,}/yr")

    sec("FINANCIAL SUMMARY")
    total_val  = plan["total_annual_value_unlocked"]
    total_cost = plan["total_monthly_cost"]
    net_gain   = total_val - (total_cost * 12)
    row("Est. Annual Opportunity:", f"${total_val:,} (after 25% overlap discount)", GREEN)
    row("Total Monthly Cost:", f"${total_cost}/month")
    row("Annual Cost:", f"${total_cost * 12:,}/year")
    row("Est. Net Annual Gain:", f"${net_gain:,}", GREEN if net_gain > 0 else RED)
    row("Est. ROI Ratio:", f"{plan['roi_ratio']}x", GREEN)
    print(f"\n  {RED}IMPORTANT: These are estimates, not promises.{RESET}")
    print(f"  {DIM}Values use industry averages where business-specific data is unavailable.{RESET}")
    print(f"  {DIM}Your actual results depend on call volume, market, pricing, and execution.{RESET}")
    print(f"  {DIM}We'd rather under-promise and over-deliver.{RESET}")

    sec("RECOMMENDED PACKAGE")
    pkg      = plan["recommended_package"]
    pkg_d    = plan["recommended_package_detail"]
    setup    = pkg_d["price_setup"]
    monthly  = pkg_d["price_monthly"]
    print(f"\n  {GOLD}{BOLD}  {pkg.upper()}  --  ${setup:,} setup + ${monthly}/month{RESET}")
    print(f"  {pkg_d['description']}")
    print(f"\n  Includes:")
    for ak in pkg_d["automations"]:
        print(f"    {GREEN}+{RESET} {ak.replace('_', ' ').title()}")
    print(f"\n  Payment: Venmo @BosRoss")

    print(f"\n{GOLD}{'='*W}{RESET}\n")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="BOSS Business AI Analyzer"
    )
    parser.add_argument("business_name", nargs="?", default=None,
                        help='Business name or type e.g. "Tyler HVAC" or "hvac"')
    parser.add_argument("city", nargs="?", default=None,
                        help='City and state e.g. "Corinth MS"')
    parser.add_argument("--type", dest="biz_type", default=None,
                        help='Business type e.g. "hvac"')
    parser.add_argument("--city", dest="city_flag", default=None,
                        help='City and state e.g. "Corinth MS"')
    parser.add_argument("--name", dest="name_flag", default=None,
                        help='Business name override')
    args = parser.parse_args()

    # Resolve inputs — support both positional and flag modes
    city_full    = args.city_flag or args.city
    raw_type     = args.biz_type or args.business_name or "hvac"
    business_name = args.name_flag or args.business_name

    if not city_full:
        print("Error: city is required. Use --city 'Corinth MS' or pass as second positional arg.")
        sys.exit(1)

    # Normalize business type
    sys.path.insert(0, str(BOSS_HQ / "scripts"))
    try:
        from automation_library import AUTOMATION_CATALOG, normalize_business_type
        catalog = AUTOMATION_CATALOG
        biz_type = normalize_business_type(raw_type or "hvac")
    except ImportError:
        catalog = {}
        biz_type = (raw_type or "hvac").lower().replace(" ", "_")

    # Fallback type detection via keyword match
    if biz_type not in BUSINESS_TYPE_META:
        for t, meta in BUSINESS_TYPE_META.items():
            if any(kw in (raw_type or "").lower() for kw in meta.get("keywords", [])):
                biz_type = t
                break
        else:
            biz_type = "hvac"

    # Build a sensible business name
    city, _ = city_state(city_full)
    if not business_name or business_name == raw_type:
        biz_label = biz_type.replace("_", " ").title()
        business_name = f"{biz_label} Business"

    biz_slug   = slug(biz_type, city_full)
    client_dir = CLIENTS_DIR / biz_slug
    client_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  BOSS BUSINESS AI ANALYZER")
    print(f"  Type:      {biz_type}")
    print(f"  Location:  {city_full}")
    print(f"{'='*60}")

    # Phase 1: Research
    print(f"\nPHASE 1 -- Market Research")
    research = research_business(business_name, city_full, biz_type)
    print(f"\n  Business found on Google: {'Yes' if research['target_found'] else 'No'}")
    print(f"  Rating: {research.get('target_rating', 'N/A')}  |  Reviews: {research.get('target_reviews', 0)}")
    print(f"  Competitors: {research['competitor_count']}  |  Pain signals: {len(research['pain_signals'])}")
    print(f"  Research complete\n")

    # Phase 2: Claude Analysis
    print(f"PHASE 2 -- Claude AI Analysis")
    claude_recs = analyze_with_claude(research, catalog)
    if claude_recs:
        print(f"  Claude identified {len(claude_recs)} prioritized automations")
    else:
        print(f"  Using rule-based analysis ({len(catalog)} automations in catalog)")
    print(f"  Analysis complete\n")

    # Phase 3: Build Plan
    print(f"PHASE 3 -- Building Transformation Plan")
    plan = build_transformation_plan(research, claude_recs, catalog)
    print(f"  Automations identified: {len(plan['automations'])}")
    print(f"  Annual value unlocked:  ${plan['total_annual_value_unlocked']:,}")
    print(f"  ROI ratio:              {plan['roi_ratio']}x")
    print(f"  Recommended package:    {plan['recommended_package']}")
    print(f"  Plan built\n")

    # Save outputs
    plan_path = client_dir / "ai_transformation_plan.json"
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2)
    research_path = client_dir / "research.json"
    with open(research_path, "w") as f:
        json.dump(research, f, indent=2)

    # Print report
    print_report(plan)

    print(f"  Files saved:")
    print(f"    {plan_path}")
    print(f"    {research_path}")
    print()


if __name__ == "__main__":
    main()
