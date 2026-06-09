#!/usr/bin/env python3
"""
BOSS BUSINESS BUILDER
Usage: python3 business_builder.py "junk removal" "Dothan AL"
       python3 business_builder.py "lawn care" "Clarksville TN" --budget 500 --business-name "BOSS Lawn Clarksville"

Builds a complete autonomous business:
  1. Market analysis via Google Places
  2. Business configuration from template
  3. Retell AI agent creation
  4. n8n workflow creation (3 workflows)
  5. Launch plan output package
  6. ntfy alert to Boston
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
RETELL_KEY          = os.environ.get("RETELL_KEY", "")
N8N_API_KEY         = os.environ.get("N8N_API_KEY", "")
N8N_BASE            = "https://jamross.app.n8n.cloud/api/v1"
N8N_WEBHOOK_BASE    = "https://jamross.app.n8n.cloud/webhook"
GOOGLE_PLACES_KEY   = os.environ.get("GOOGLE_PLACES_KEY", "")
NTFY_CHANNEL        = "bossai-bostonrossall-alerts"
ANTHROPIC_KEY       = os.environ.get("ANTHROPIC_API_KEY", "")

BOSS_HQ             = Path(__file__).resolve().parent.parent
BUSINESSES_DIR      = BOSS_HQ / "businesses"
CLIENTS_DIR         = BOSS_HQ / "clients"

# ──────────────────────────────────────────────────────────────────────────────
# BUSINESS TYPE TEMPLATES
# ──────────────────────────────────────────────────────────────────────────────
BUSINESS_TEMPLATES = {
    "junk removal": {
        "category": "Junk Removal",
        "margin": 0.55,
        "avg_job": 310,
        "revenue_low": 5500,
        "revenue_high": 18000,
        "pricing_text": (
            "PRICING (give exact quotes):\n"
            "- Single item (couch, mattress, appliance): $75-100\n"
            "- Quarter truck load (pickup-truck sized): $125-175\n"
            "- Half truck load: $225-300\n"
            "- Full truck load: $400-550\n"
            "- Yard waste / heavy material: add $50 to any tier\n"
            "- Same-day service: add $30\n\n"
            "WHAT WE TAKE: Furniture, appliances, mattresses, TVs, electronics, "
            "yard waste, construction debris. Hot tubs and pianos: quote on-site.\n"
            "WHAT WE DON'T TAKE: Hazardous waste, paint, chemicals, medical waste, propane tanks."
        ),
        "google_category": "junk removal",
        "keywords": ["junk removal", "haul away", "junk hauling", "debris removal"],
    },
    "pressure washing": {
        "category": "Pressure Washing",
        "margin": 0.65,
        "avg_job": 225,
        "revenue_low": 4000,
        "revenue_high": 14000,
        "pricing_text": (
            "PRICING:\n"
            "- House exterior wash (up to 2,000 sqft): $150-250\n"
            "- House exterior wash (2,000-3,500 sqft): $250-350\n"
            "- Driveway / concrete (up to 500 sqft): $75-125\n"
            "- Driveway / concrete (500-1,200 sqft): $125-175\n"
            "- Deck or patio: $100-200 depending on size\n"
            "- Full property package (house + driveway + deck): $350-550\n"
            "- Commercial storefronts: $150-400"
        ),
        "google_category": "pressure washing",
        "keywords": ["pressure washing", "power washing", "house washing"],
    },
    "lawn care": {
        "category": "Lawn Care",
        "margin": 0.60,
        "avg_job": 80,
        "revenue_low": 3500,
        "revenue_high": 12000,
        "pricing_text": (
            "PRICING:\n"
            "- Small yard (up to 5,000 sqft): $45-65/visit\n"
            "- Medium yard (5,000-10,000 sqft): $65-95/visit\n"
            "- Large yard (10,000-20,000 sqft): $95-150/visit\n"
            "- Oversized / acreage: call for quote\n"
            "- Weekly service discount: 10% off\n"
            "- One-time mow: standard rate + $15\n"
            "- Edging, trimming, blowing included in all prices.\n"
            "- Leaf cleanup / seasonal: add $50-100"
        ),
        "google_category": "lawn care service",
        "keywords": ["lawn care", "lawn mowing", "grass cutting", "yard service"],
    },
    "cleaning": {
        "category": "Cleaning Service",
        "margin": 0.55,
        "avg_job": 175,
        "revenue_low": 4500,
        "revenue_high": 15000,
        "pricing_text": (
            "PRICING:\n"
            "RESIDENTIAL:\n"
            "- 1-2 bedroom home (standard): $100-150\n"
            "- 3-4 bedroom home (standard): $150-225\n"
            "- Deep clean (add-on): +$75-100\n"
            "- Move-in / move-out: $200-350\n"
            "COMMERCIAL:\n"
            "- Small office (up to 1,500 sqft): $200-300\n"
            "- Medium office (1,500-4,000 sqft): $300-500\n"
            "- Recurring weekly/biweekly contracts: 15% off standard rate"
        ),
        "google_category": "house cleaning service",
        "keywords": ["house cleaning", "cleaning service", "maid service", "office cleaning"],
    },
    "pest control": {
        "category": "Pest Control",
        "margin": 0.65,
        "avg_job": 200,
        "revenue_low": 5000,
        "revenue_high": 16000,
        "pricing_text": (
            "PRICING:\n"
            "- Initial inspection + treatment (interior + exterior): $150-250\n"
            "- Monthly maintenance plan: $50-100/month\n"
            "- Quarterly plan: $75-125/quarter\n"
            "- One-time treatment (specific pest): $75-175\n"
            "- Termite inspection: $100-150 (treatment quoted on-site)\n"
            "- Rodent treatment + exclusion: $200-400\n"
            "- Bed bug treatment: $300-600\n"
            "First month free with annual contract."
        ),
        "google_category": "pest control service",
        "keywords": ["pest control", "exterminator", "bug control", "termite"],
    },
    "hvac": {
        "category": "HVAC",
        "margin": 0.50,
        "avg_job": 650,
        "revenue_low": 8000,
        "revenue_high": 25000,
        "pricing_text": (
            "PRICING:\n"
            "- Diagnostic / service call: $89-129\n"
            "- AC tune-up: $79-99\n"
            "- Furnace tune-up: $79-99\n"
            "- Refrigerant recharge (per lb): $50-80\n"
            "- Capacitor / contactor replacement: $150-300\n"
            "- Blower motor replacement: $400-700\n"
            "- Compressor replacement: $1,200-2,500\n"
            "- Full AC system install (2-5 ton): $4,500-8,500\n"
            "- Full furnace install: $2,500-5,500\n"
            "- Ductwork repair: $200-600\n"
            "- Same-day emergency service: add $50-100"
        ),
        "google_category": "hvac contractor",
        "keywords": ["hvac", "air conditioning", "ac repair", "heating", "furnace", "cooling"],
    },
    "plumbing": {
        "category": "Plumbing",
        "margin": 0.55,
        "avg_job": 425,
        "revenue_low": 7000,
        "revenue_high": 22000,
        "pricing_text": (
            "PRICING:\n"
            "- Service call / diagnostic: $75-125\n"
            "- Drain cleaning (single drain): $100-175\n"
            "- Main sewer line clearing: $200-400\n"
            "- Faucet repair or replacement: $125-275\n"
            "- Toilet repair: $100-200\n"
            "- Toilet replacement (installed): $300-600\n"
            "- Water heater repair: $150-400\n"
            "- Water heater replacement (40-50 gal): $900-1,800\n"
            "- Tankless water heater install: $2,000-3,500\n"
            "- Pipe leak repair: $150-500\n"
            "- Slab leak detection: $200-400\n"
            "- Garbage disposal install: $175-350\n"
            "- Emergency / after-hours: add $100-150"
        ),
        "google_category": "plumber",
        "keywords": ["plumber", "plumbing", "drain cleaning", "water heater", "pipe repair"],
    },
    "electrical": {
        "category": "Electrical",
        "margin": 0.55,
        "avg_job": 380,
        "revenue_low": 6000,
        "revenue_high": 20000,
        "pricing_text": (
            "PRICING:\n"
            "- Service call / diagnostic: $75-125\n"
            "- Outlet install or replacement: $100-200\n"
            "- Light fixture install: $100-250\n"
            "- Ceiling fan install: $150-300\n"
            "- Circuit breaker replacement: $150-300\n"
            "- Panel upgrade (100-200 amp): $1,500-3,000\n"
            "- Whole-house rewiring: $4,000-10,000+ (quoted on-site)\n"
            "- EV charger install (Level 2): $500-1,200\n"
            "- Generator hookup / transfer switch: $800-2,000\n"
            "- Smoke detector install (per unit): $50-100\n"
            "- Emergency / after-hours: add $100-150"
        ),
        "google_category": "electrician",
        "keywords": ["electrician", "electrical", "wiring", "panel upgrade", "outlet repair"],
    },
    "roofing": {
        "category": "Roofing",
        "margin": 0.35,
        "avg_job": 8500,
        "revenue_low": 15000,
        "revenue_high": 50000,
        "pricing_text": (
            "PRICING:\n"
            "- Free roof inspection: $0\n"
            "- Roof leak repair (small): $200-500\n"
            "- Roof leak repair (moderate): $500-1,200\n"
            "- Missing shingles / wind damage: $200-800\n"
            "- Full shingle roof (2,000 sqft): $6,000-10,000\n"
            "- Full shingle roof (3,000 sqft): $9,000-15,000\n"
            "- Metal roof install: $12,000-25,000+\n"
            "- Gutter install (per linear foot): $6-12\n"
            "- Gutter cleaning: $100-250\n"
            "- Insurance claim assistance: free with roof replacement\n"
            "- Emergency tarping: $200-500"
        ),
        "google_category": "roofing contractor",
        "keywords": ["roofing", "roof repair", "roof replacement", "shingles", "gutters"],
    },
    "legal": {
        "category": "Law Firm",
        "margin": 0.70,
        "avg_job": 3500,
        "revenue_low": 12000,
        "revenue_high": 40000,
        "pricing_text": (
            "CONSULTATION AND INTAKE:\n"
            "- Initial consultation: $150-300 (or free for personal injury)\n"
            "- Personal injury cases: contingency fee — no upfront cost\n"
            "- Family law retainer: $2,500-5,000\n"
            "- Criminal defense retainer: $3,000-10,000\n"
            "- Estate planning (basic will): $300-800\n"
            "- Estate planning (trust): $1,500-3,500\n"
            "- Business formation (LLC): $500-1,500\n"
            "- Real estate closing: $500-1,200\n\n"
            "INTAKE PROCESS:\n"
            "- Get: caller's name, brief description of their legal matter\n"
            "- Do NOT give legal advice or case assessments\n"
            "- Book a consultation appointment\n"
            "- For personal injury: get incident date, type of injury, insurance info"
        ),
        "google_category": "law firm",
        "keywords": ["lawyer", "attorney", "law firm", "legal help", "personal injury"],
    },
    "auto repair": {
        "category": "Auto Repair",
        "margin": 0.50,
        "avg_job": 450,
        "revenue_low": 7000,
        "revenue_high": 22000,
        "pricing_text": (
            "PRICING:\n"
            "- Diagnostic fee: $75-125 (applied to repair)\n"
            "- Oil change (conventional): $35-55\n"
            "- Oil change (synthetic): $65-95\n"
            "- Brake pads (per axle): $150-300\n"
            "- Brake pads + rotors (per axle): $300-550\n"
            "- Battery replacement: $150-250\n"
            "- Alternator replacement: $350-600\n"
            "- Starter replacement: $300-550\n"
            "- AC recharge: $150-250\n"
            "- Timing belt replacement: $500-900\n"
            "- Transmission service: $150-300\n"
            "- Check engine light diagnostic: $75-125"
        ),
        "google_category": "auto repair shop",
        "keywords": ["auto repair", "mechanic", "oil change", "brake repair", "car repair"],
    },
    "dental": {
        "category": "Dental Office",
        "margin": 0.45,
        "avg_job": 350,
        "revenue_low": 10000,
        "revenue_high": 30000,
        "pricing_text": (
            "APPOINTMENTS AND SERVICES:\n"
            "- New patient exam + cleaning + X-rays: $150-250\n"
            "- Regular cleaning (prophylaxis): $100-150\n"
            "- Deep cleaning (per quadrant): $200-350\n"
            "- Filling (composite): $150-300\n"
            "- Crown: $800-1,500\n"
            "- Root canal (front tooth): $700-1,000\n"
            "- Root canal (molar): $1,000-1,500\n"
            "- Extraction (simple): $150-300\n"
            "- Whitening (in-office): $300-600\n"
            "- Emergency exam: $75-150\n\n"
            "SCHEDULING:\n"
            "- Get: patient name, reason for visit, insurance provider if any\n"
            "- New patients: offer next available new patient slot\n"
            "- Emergencies (pain, swelling, broken tooth): same-day if possible"
        ),
        "google_category": "dentist",
        "keywords": ["dentist", "dental", "teeth cleaning", "dental office", "tooth pain"],
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

BUSINESS_TYPE_ALIASES = {
    "junk removal": ["junk removal", "junk_removal", "junk hauling", "haul away"],
    "pressure washing": ["pressure washing", "pressure_washing", "power washing"],
    "lawn care": ["lawn care", "lawn_care", "landscaping", "yard service", "grass cutting"],
    "cleaning": ["cleaning", "house cleaning", "maid service", "janitorial"],
    "pest control": ["pest control", "pest_control", "exterminator"],
    "hvac": ["hvac", "heating", "cooling", "air conditioning", "ac repair"],
    "plumbing": ["plumbing", "plumber", "pipe repair", "drain cleaning"],
    "electrical": ["electrical", "electrician", "wiring"],
    "roofing": ["roofing", "roofer", "roof repair"],
    "legal": ["legal", "law firm", "law_firm", "attorney", "lawyer"],
    "auto repair": ["auto repair", "auto_repair", "mechanic", "car repair"],
    "dental": ["dental", "dentist", "dental office"],
}


def normalize_business_type(raw):
    raw = raw.lower().strip()
    if not raw:
        return raw
    if raw in BUSINESS_TEMPLATES:
        return raw
    for canonical, aliases in BUSINESS_TYPE_ALIASES.items():
        if raw in aliases:
            return canonical
    for canonical, aliases in BUSINESS_TYPE_ALIASES.items():
        for alias in aliases:
            if len(raw) >= 3 and (alias in raw or raw in alias):
                return canonical
    return raw


def http_get(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def http_post(url, payload, headers=None, timeout=10):
    data = json.dumps(payload).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def http_patch(url, payload, headers=None, timeout=10):
    data = json.dumps(payload).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="PATCH")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def slug(business_type, city):
    """junk_removal_tupelo_ms"""
    return (
        business_type.lower().replace(" ", "_")
        + "_"
        + city.lower().replace(" ", "_").replace(",", "")
    )


def city_state(city_str):
    """'Tupelo MS' → ('Tupelo', 'MS')"""
    parts = city_str.strip().rsplit(" ", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip().upper()
    return city_str.strip(), ""


def title_case(s):
    return " ".join(w.capitalize() for w in s.split())


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 1 — MARKET ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────

def search_places(query, location_bias=None):
    """Text search via Places API v1 (New)."""
    url = "https://places.googleapis.com/v1/places:searchText"
    payload = {
        "textQuery": query,
        "maxResultCount": 20,
    }
    if location_bias:
        payload["locationBias"] = location_bias
    headers = {
        "X-Goog-Api-Key": GOOGLE_PLACES_KEY,
        "X-Goog-FieldMask": (
            "places.displayName,places.rating,places.userRatingCount,"
            "places.formattedAddress,places.types"
        ),
    }
    try:
        result = http_post(url, payload, headers=headers, timeout=10)
        return result.get("places", [])
    except Exception as e:
        return []


def analyze_market(business_type, city_full):
    """Return dict with market analysis results."""
    city, state = city_state(city_full)
    template = BUSINESS_TEMPLATES.get(business_type, BUSINESS_TEMPLATES["junk removal"])
    google_cat = template["google_category"]

    print(f"  Searching Google Places for '{google_cat}' in {city_full}...")
    results = search_places(f"{google_cat} {city} {state}")

    # Filter to local results (address contains city or state)
    local = [
        p for p in results
        if city.lower() in p.get("formattedAddress", "").lower()
        or state.lower() in p.get("formattedAddress", "").lower()
    ]
    if not local:
        local = results[:10]  # fall back to all results

    competitors = len(local)
    ratings = [p.get("rating", 0) for p in local if p.get("rating")]
    review_counts = [p.get("userRatingCount", 0) for p in local if p.get("userRatingCount")]

    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0
    avg_reviews = int(sum(review_counts) / len(review_counts)) if review_counts else 0
    total_reviews = sum(review_counts)
    low_rated = [p for p in local if p.get("rating", 5) <= 3.5]

    # Population proxy: search for city government/hall
    print(f"  Estimating market size for {city}...")
    pop_results = search_places(f"{city} {state} city hall government")
    # Simple heuristic: can't get real pop from Places, use competitor density
    # Small market: <3 competitors, Medium: 3-6, Large: 7+
    if competitors <= 2:
        pop_estimate = "15,000 - 45,000"
        market_size = "small"
    elif competitors <= 5:
        pop_estimate = "45,000 - 100,000"
        market_size = "medium"
    else:
        pop_estimate = "100,000+"
        market_size = "large"

    # Score calculation (1-10)
    score = 5  # baseline
    if competitors == 0:
        score = 9  # no competition = major opportunity
    elif competitors <= 2:
        score += 2
    elif competitors <= 4:
        score += 1
    elif competitors >= 7:
        score -= 2

    if avg_rating < 3.5 and ratings:
        score += 2  # weak competition quality
    elif avg_rating < 4.0 and ratings:
        score += 1
    elif avg_rating >= 4.5:
        score -= 1

    if avg_reviews < 20:
        score += 1  # low review counts = not established
    if total_reviews < 50:
        score += 1

    score = max(1, min(10, score))

    if competitors == 0:
        competition_level = "None found"
    elif competitors <= 2:
        competition_level = "Light"
    elif competitors <= 5:
        competition_level = "Moderate"
    else:
        competition_level = "Heavy"

    # Revenue estimate
    rev_low = template["revenue_low"]
    rev_high = template["revenue_high"]
    if market_size == "small":
        rev_low = int(rev_low * 0.7)
        rev_high = int(rev_high * 0.7)
    elif market_size == "large":
        rev_low = int(rev_low * 1.3)
        rev_high = int(rev_high * 1.3)

    recommendation = "GO" if score >= 6 else "NO-GO"
    if competitors == 0:
        recommendation = "STRONG GO"

    gaps = []
    if low_rated:
        gaps.append(f"{len(low_rated)} competitor(s) rated 3.5 or below — unhappy customers available")
    if avg_reviews < 20 and competitors > 0:
        gaps.append("Competitors have few reviews — easy to outrank with 20+ reviews")
    if competitors == 0:
        gaps.append("Zero local competition found — wide open market")
    if not gaps:
        gaps.append("Market appears established but serviceable with strong execution")

    return {
        "city": city,
        "state": state,
        "city_full": city_full,
        "competitors": competitors,
        "avg_rating": avg_rating,
        "avg_reviews": avg_reviews,
        "total_reviews": total_reviews,
        "competition_level": competition_level,
        "low_rated_competitors": len(low_rated),
        "market_score": score,
        "market_size": market_size,
        "pop_estimate": pop_estimate,
        "revenue_low": rev_low,
        "revenue_high": rev_high,
        "recommendation": recommendation,
        "gaps": gaps,
        "competitor_list": [
            {
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "rating": p.get("rating", "N/A"),
                "reviews": p.get("userRatingCount", 0),
                "address": p.get("formattedAddress", ""),
            }
            for p in local[:8]
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 3 — RETELL AGENT CREATION
# ──────────────────────────────────────────────────────────────────────────────

BUSINESS_TONES = {
    "junk removal": "Matter-of-fact, get-it-done energy. These callers want stuff gone fast.",
    "pressure washing": "Project-focused, professional. Many callers are prepping to sell — ask about timeline.",
    "lawn care": "Casual, neighborly. Many become recurring — always mention the weekly option.",
    "cleaning": "Warm, detail-oriented. Ask about pets and allergies. Callers want to feel their home is safe.",
    "pest control": "Calm, reassuring. Callers are often panicked. Normalize: 'Very common this time of year.'",
    "hvac": "Urgent-ready, knowledgeable. Peak season callers need same-day. Off-peak wants maintenance deals.",
    "plumbing": "Fast, direct. Plumbing callers often have water running — don't waste their time.",
    "electrical": "Safety-aware, confident. Electrical scares people — reassure them it's fixable.",
    "roofing": "Professional, project-scoped. Many callers are post-storm or pre-sale. Ask what prompted the call.",
    "legal": "Professional, composed, empathetic. These callers are stressed about a situation. Listen first.",
    "auto repair": "Straightforward, no-nonsense. Callers want to know: what's wrong, what it costs, when it's done.",
    "dental": "Warm, patient, calming. Many callers are nervous about dental work. Normalize it: 'You're in good hands.'",
}

BUSINESS_VOICES = {
    "junk removal": "11labs-Adrian",
    "pressure washing": "11labs-Adrian",
    "lawn care": "11labs-Adrian",
    "cleaning": "11labs-Myra",
    "pest control": "11labs-Myra",
    "hvac": "11labs-Adrian",
    "plumbing": "11labs-Adrian",
    "electrical": "11labs-Adrian",
    "roofing": "11labs-Adrian",
    "legal": "11labs-Myra",
    "auto repair": "11labs-Adrian",
    "dental": "11labs-Myra",
}

BUSINESS_OBJECTIONS = {
    "pest control": '- "Is it safe for my kids/pets?" → "Absolutely — everything we use is pet and kid safe once it dries, usually about 30 minutes."',
    "pressure washing": '- "Will it damage my siding?" → "Nope — we soft wash when needed. We adjust the pressure based on the surface. Your siding\'s safe."\n- "How long does it take?" → "Most houses take 2-3 hours. Driveways are usually under an hour."',
    "cleaning": '- "Do I need to be home?" → "Nope, most of our clients give us a code or leave a key. Totally up to you."',
    "junk removal": '- "Can you come TODAY?" → "Let me check — we usually can fit same-day in. What time works?"',
    "lawn care": '- "Is it just weekly or can I do one-time?" → "We do both. Most people start with a one-time and then decide. Want me to book you one?"',
    "hvac": '- "Can you come today? It\'s an emergency." → "Got it — we have emergency service. Let me get your address and I\'ll get someone headed your way."\n- "How much to replace my whole system?" → "Depends on the size of your home and what we\'re working with. We can send someone out for a free estimate — usually takes about 30 minutes."',
    "plumbing": '- "Is there a trip charge?" → "The diagnostic is $89-125 and that goes toward the repair if you move forward."\n- "My basement is flooding!" → "I hear you — let me get your address. We\'ll have someone out to you as fast as possible."',
    "roofing": '- "Will insurance cover this?" → "Depends on your policy, but we work with insurance companies all the time. We can do a free inspection and help you file if it qualifies."\n- "Can you just patch it?" → "Yeah, if a patch makes sense we\'ll do that. We\'ll be upfront — we don\'t push full replacements unless it\'s really needed."',
    "legal": '- "How much is a consultation?" → "The initial consultation is $150-300. That gives you a full sit-down with the attorney to go over everything."\n- "Do you handle [case type]?" → "Let me get a few details about your situation and I\'ll make sure we connect you with the right attorney."',
    "electrical": '- "Is this a fire hazard?" → "Could be — that\'s exactly why you want someone to look at it. Let me get you on the schedule."\n- "Can you come today?" → "For electrical issues, we treat it as priority. Let me get your address."',
    "auto repair": '- "Can I wait while you work on it?" → "Depends on the job — if it\'s quick we\'ll knock it out. If not, we can get you a ride or have you drop it off."\n- "How long will it take?" → "I can give you a better timeline once we do the diagnostic. Usually same-day for smaller jobs."',
    "dental": '- "Do you take my insurance?" → "We work with most major insurance plans. What provider do you have? I\'ll check for you."\n- "I\'m scared of the dentist." → "Totally understand — we hear that a lot. We go at your pace and make sure you\'re comfortable the whole time."',
}

EMERGENCY_PROTOCOLS = {
    "hvac": 'If caller says "no AC", "no heat", "it\'s 95 degrees", "furnace out":\n1. "I\'m getting someone dispatched right now. What\'s your address?"\n2. Get: name, address, system type if they know.\n3. "We can usually get someone there within 2 hours. Is there a gate code or anything we need to know?"',
    "plumbing": 'If caller says "water everywhere", "pipe burst", "flooding", "sewage":\n1. "First — if you can, turn off your main water shutoff valve. It\'s usually near the water meter."\n2. "Now let me get someone to you right away. What\'s your address?"\n3. Get: name, address, brief description. "Someone will be there as fast as possible."',
    "electrical": 'If caller says "sparks", "burning smell", "outlet smoking", "power out":\n1. "If you see sparks or smell burning, go to your breaker panel and flip the main breaker off. Safety first."\n2. "Now let me get an electrician out there. What\'s your address?"\n3. Get: name, address. "We treat electrical emergencies as top priority."',
    "roofing": 'If caller says "leak", "storm damage", "tree fell on roof", "water coming in":\n1. "Let me get someone out there to tarp it and stop the damage. What\'s your address?"\n2. Get: name, address, description of damage.\n3. "We\'ll get it covered today and then schedule the full repair."',
    "dental": 'If caller says "tooth pain", "knocked out tooth", "swelling", "abscess":\n1. "We can get you in for an emergency exam today. Are you in pain right now?"\n2. Get: name, phone, brief description.\n3. "We\'ll work you in as soon as possible. If the pain gets worse before your visit, take ibuprofen and use a cold compress."',
    "legal": 'If caller says "arrested", "served papers", "court date tomorrow", "emergency":\n1. "Let me get your information to the attorney right away. What\'s your name and the best number to reach you?"\n2. Get: name, phone, brief description of situation.\n3. "The attorney will call you back within the hour. Don\'t discuss your case with anyone else until then."',
    "auto repair": 'If caller says "broke down", "won\'t start", "smoke from engine", "accident":\n1. "Are you somewhere safe? If you\'re on the road, stay in the vehicle with hazards on."\n2. "We can send a tow or you can bring it in. What\'s your location?"\n3. Get: name, phone, vehicle make/model, location.',
}

CLIENT_CONFIG_DEFAULTS = {
    "owner_name": None,
    "owner_phone": None,
    "owner_email": None,
    "business_hours": "Monday through Saturday, 7am to 7pm",
    "after_hours_behavior": "schedule_next",
    "service_radius": "25-mile radius",
    "services_offered": None,
    "excluded_services": None,
    "custom_pricing": None,
    "voice": None,
    "tone_override": None,
    "emergency_protocol": None,
    "custom_objections": None,
    "payment_method": "venmo",
    "review_request_delay_hours": 2,
    "daily_briefing_time": "08:00",
    "daily_briefing_days": "1-6",
    "package": "starter",
    "spp_partner": False,
}


def load_client_config(config_path):
    """Load a client config JSON and merge with defaults."""
    with open(config_path) as f:
        user_cfg = json.load(f)
    cfg = dict(CLIENT_CONFIG_DEFAULTS)
    cfg.update({k: v for k, v in user_cfg.items() if v is not None})
    return cfg


def build_system_prompt(business_name, business_type, city_full, template, client_cfg=None):
    cfg = client_cfg or {}
    city, state = city_state(city_full)
    bt_title = title_case(business_type)
    pricing = cfg.get("custom_pricing") or template["pricing_text"]
    tone = cfg.get("tone_override") or BUSINESS_TONES.get(business_type, "Friendly, professional, real. Like talking to a neighbor, not a call center.")
    extra_objections = BUSINESS_OBJECTIONS.get(business_type, "")
    custom_obj = cfg.get("custom_objections")
    if custom_obj:
        extra_objections += "\n" + custom_obj

    hours = cfg.get("business_hours", "Monday through Saturday, 7am to 7pm")
    service_area = cfg.get("service_radius", "25-mile radius")
    owner_name = cfg.get("owner_name")
    owner_ref = f" Owner: {owner_name}." if owner_name else ""
    owner_name_or_default = owner_name or "the owner"

    emergency = cfg.get("emergency_protocol") or EMERGENCY_PROTOCOLS.get(business_type, "")
    if not emergency:
        emergency = ('If caller says "today", "right now", "emergency", "ASAP":\n'
                     '1. "Got it — sounds like you need us out there today."\n'
                     '2. Get: name, address, brief description only.\n'
                     '3. "We can get someone out there today. Let me get you on the schedule right now."\n'
                     '4. Do NOT ask preferred date/time for emergencies — tell them when.')

    after_hours_behavior = cfg.get("after_hours_behavior", "schedule_next")
    if after_hours_behavior == "emergency":
        after_hours_msg = f'"Hi, thanks for calling {business_name}! I can get someone dispatched right now for emergencies, or get you on tomorrow\'s schedule. What do you need?"'
    elif after_hours_behavior == "voicemail":
        after_hours_msg = f'"Hi, thanks for calling {business_name}. Leave your name and number and we\'ll call you first thing in the morning."'
    else:
        after_hours_msg = f'"Hi, thanks for calling {business_name}! I can get you on tomorrow\'s schedule right now. What do you need?"'

    services_section = ""
    services_offered = cfg.get("services_offered")
    excluded_services = cfg.get("excluded_services")
    if services_offered:
        services_section = "\nSERVICES WE OFFER:\n" + "\n".join(f"- {s}" for s in services_offered) + "\n"
    if excluded_services:
        services_section += "\nSERVICES WE DO NOT OFFER:\n" + "\n".join(f"- {s}" for s in excluded_services) + "\nIf asked about these, say: \"We don't handle that, but I can help you with what we do offer.\"\n"

    return f"""You answer the phone for {business_name} in {city}, {state}.{owner_ref}

HANG UP RULE: If you detect a recording, voicemail greeting, automated menu, or silence lasting 3+ seconds — use end_call immediately.

HOURS: {hours}. Phone answered 24/7 but jobs scheduled during business hours.
SERVICE AREA: {service_area} from {city}, {state}
{services_section}
{pricing}

TONE: {tone}
- Short sentences. Casual but professional. Never corporate.
- Match the caller's energy. Panicked = move fast. Relaxed = conversational.
- One question at a time. Never stack questions.
- Acknowledge before answering: "Yeah for sure." "Got it." Then answer.
- Keep responses under 2 sentences unless explaining pricing.
- Never say "How may I assist you today?" or "Thank you for your patience."
- ACTION OVER SYMPATHY: Never fake emotions. Instead of "I'm so sorry about your pipe burst," say "Let's get someone out there for you right away." Solve, don't sympathize.
- MICRO-PAUSE ON DISTRESS: When the caller mentions an emergency, a child, an elderly person, flooding, no AC in the heat, or any urgent/emotional situation — pause briefly before responding. Don't snap back instantly with a composed sentence. A beat of silence before "Let me get you taken care of right now" sounds human. Instant perfect responses to emotional content sound robotic.
- Never repeat the same filler phrase twice in one call. Vary your transitions — "Sure thing," "Absolutely," "You got it," "Yeah for sure" — rotate, don't repeat.
- Offer value before asking for information. Say what you CAN do before collecting name/address/details.
- Use "sir" and "ma'am" naturally. Use the caller's name once they give it.
- ONE REPEATABLE MOMENT PER CALL: Every call should produce one sentence the caller tells their neighbor. For bookings: "They got me in tomorrow." For after-hours: "They answered at 11 PM on a Saturday." For emergencies: "They had someone on the way in 10 minutes." Design your responses so one line stands out.
- FIRST 2 SECONDS MATTER: The caller decides if you're competent in under a second. Your greeting must complete in under 4 seconds: "Hi, thanks for calling {business_name}, how can I help?" No dead air. No robotic menu. No long intro. The shorter the greeting, the more competent you sound. Sound like someone who's been answering this phone for years.

EMERGENCY HANDLING:
{emergency}
Do NOT ask preferred date/time for emergencies — tell them when.
Emergency 6-step sequence (this exact order, no skipping):
1. VALIDATE urgency (2 sec): "Oh no — let's get someone headed your way."
2. SAFETY action (5 sec): If relevant, tell them what to do NOW ("Turn off the water at the main valve if you can").
3. COMMIT to help (3 sec): "We're going to get someone out there today."
4. GATHER info (15-20 sec): ONLY NOW collect name, address, brief description. Minimum needed to dispatch.
5. SET expectation (5 sec): "Expect a call back within 30 minutes to confirm the window."
6. REASSURE (3 sec): "You're taken care of. We'll get this handled."
Never ask an emergency caller to hold. Never transfer them to voicemail.

BOOKING FLOW (non-emergency):
1. Offer value BEFORE asking for information: "We can definitely help with that."
2. Give a price range with context when asked: "Most [service] visits run [low] to [high], and that gets applied to the repair if you move forward." Never refuse a price question. Never say "it depends."
3. Close with either/or — non-negotiable: "I've got a slot [DAY] afternoon or [DAY] morning — which works better?" This skips WHETHER and goes straight to WHEN. Converts 2-3x vs open questions.
4. Add urgency: "We fill up fast — two slots left this week."
5. Collect: full name, service address, preferred date/time
6. Confirm back slowly and clearly: "Got you down for [DAY] at [TIME] at [ADDRESS] for [SERVICE]."
7. "We'll give you a call about 30 minutes before. Anything else?"
8. Try for email: "What's a good email for your confirmation?"
9. "You're all set. Have a good one!" then end_call

4 CONVERSION KILLERS (never do these):
1. Not asking for the booking — only 35% of agents actually ask. ALWAYS close with either/or.
2. Price fumble — if asked "how much?", give a range with context. Never say "I'd have to check."
3. Too many questions before value — get name/address AFTER offering help, not before.
4. No urgency — "We have availability" loses to "Two slots left this week."

CANCEL / RESCHEDULE:
- "No problem. Can I get your name?"
- "Want to reschedule for another day, or just cancel for now?"
- If reschedule: offer new times. If cancel: "You're all set. Call us whenever you're ready."
- Never guilt them. Never ask why.

"CAN I SPEAK TO A REAL PERSON?" / "IS THERE A MANAGER?":
- NEVER say "I'm sorry, no one is available." That's a wall, not a bridge.
- ALWAYS offer choice: "I can help you with most things, or I can have {owner_name_or_default} call you back within the hour. Which would you prefer?"
- If they insist on a human: "Absolutely. What's the best number? I'll have {owner_name_or_default} call you back within the hour and I'll mark it as priority."
- The word "absolutely" is non-negotiable — it signals compliance, not resistance.
- If the caller is clearly upset or emotional, skip the "I can help" offer — go straight to human handoff.
- CRITICAL: When taking a message for the owner, include WHY they called — not just "someone wants a callback." The owner needs the context to make the callback effective.

BILLING / INVOICE:
- "Let me flag that — billing is handled directly by the owner. Can I get your name and number? They'll call you back today."

ANGRY CALLER / COMPLAINT:
- Let them talk. Do NOT interrupt. Wait until they stop before responding.
- After they finish, summarize what they said to prove you listened: "So the install left a mess and the water still isn't right — and you paid good money for this."
- Say "That is not okay" or "That shouldn't have happened." NEVER say "I understand your frustration."
- "Let me get this to {owner_name_or_default} directly and flag it as urgent. What's your name and the best number?"
- "You'll get a call back today." — always give a specific timeline, not "as soon as possible."
- If they demand to speak to the owner: "Absolutely. {owner_name_or_default} is out on a job but I'm texting them what you told me right now and flagging it urgent. They'll call you back today — what's the best number?"

WRONG NUMBER: "No worries, you've reached {business_name}. Hope you find who you're looking for." → end_call
SPAM/SOLICITOR: "We're good, thanks." → end_call

IF ASKED WHETHER YOU ARE AI:
- "I'm an AI assistant for {business_name}. Let me get you taken care of." Then immediately pivot to solving their problem.
- Brief, confident, no apology, no explanation. The pivot to action is what matters — not the disclosure.

REPEAT CUSTOMER (says "I've called before," "used you before," "last time"):
- NEVER say "I don't have a record of that" — it feels like rejection.
- NEVER pretend to remember specifics you don't have — the lie collapses in one question.
- USE the graceful pivot: validate what they said, show relevant knowledge, move to action.
  Example: "Oh got it, yeah — since you've worked with us before, let me just get you back on the schedule."
- "Do you have a preference for which tech comes out, or is anyone fine?" — feels personal without needing records.

REFERRAL CALLER (says a name "recommended" or "told me about" you):
- IMMEDIATELY acknowledge the referrer by name: "Oh great, glad [name] recommended us!"
- Use the word "recommended" — never "referred." Recommended is personal. Referred is clinical.
- Normalize their problem: "That's usually a quick fix" or "We handle that all the time."
- Close fast — referral callers are pre-sold. Book first, details second.
- If no name given: "Oh great — who sent you our way?" captures the source without feeling like interrogation.

ELDERLY CALLER (slower speech, formal language like "yes, hello," mentions neighbor who referred):
- Slow your speaking pace. Short sentences — max 10 words each.
- One piece of information at a time with a pause between.
- Automatically repeat appointment details: day, date, and time — don't wait to be asked.
- Use "Mrs./Mr. [Last Name]" after they give their name.
- Do NOT offer text confirmation — offer to repeat information verbally.
- If they ask you to repeat something, repeat it word-for-word (don't paraphrase — paraphrasing forces them to process a new sentence).
- End with a warm goodbye: "You're welcome. We'll take good care of it. You have a good day."
- If they go silent for 3-4 seconds, wait 5 before prompting. Don't rush them.

PRICE SHOPPER (says "getting quotes," "how much," "shopping around"):
- Demonstrate expertise early: "That could be a few things" or "We see that a lot."
- Give price RANGES when asked, never refuse: "Most [service] visits run $X to $Y."
- Speed signal: "We can get someone out this week" — not "I'll have someone call you."
- Close with either/or: "Are you more mornings or afternoons?" — skips WHETHER and goes straight to WHEN.
- Mirror their energy: research callers are calm. Match with competent, not urgent.

AFTER HOURS (calls between 7 PM and 7 AM, or weekends):
- NEVER reference "after hours" or "outside normal business hours."
- NEVER say "I can take a message and someone will call you during business hours."
- Answer with the same warmth and energy as daytime — the caller should NOT be able to tell the difference.
- If asked "Are you open?": "Yep! We answer 24/7 so you don't have to wait until morning. What's going on?"
- Treat the call as a live booking opportunity, not a message-taking exercise.
- The after-hours answer IS the competitive advantage — do not dilute it with caveats.

BANNED PHRASES (never say these):
- "I understand your frustration" → say "That is not okay" or "That shouldn't have happened"
- "I'd be happy to help with that" → say "Let's get this handled"
- "I can take a message" → say "Let me get you on the schedule" or "I'll have [owner] call you within the hour"
- "Our normal business hours are..." → say "Yep, we answer 24/7!"
- "I don't have any record of that" → use a graceful pivot to action
- "I'm sorry, I'm just an AI" → say "I'm an AI assistant for {business_name}. Let me get you taken care of."
- "Is there anything else I can help you with?" (monotone) → say "Anything else you need?" (casual)

SILENCE HANDLING: If caller goes silent after two prompts — "Sounds like you might have stepped away. Give us a call back when you're ready — bye now!" then end_call.

OBJECTIONS:
- "I need to think about it" → "What's the main thing holding you back? Price, timing, or something else?"
- "You're too expensive" → "I understand. What's your budget? Let's see if we can work with that."
- "I'll call you back" → "Sure — but we do fill up fast. Can I pencil you in and you can always cancel?"
- "Why should I choose you?" → "We answer the phone every time — no voicemail. We give you a price right now. And we're local, not a franchise."
{extra_objections}

POST-CALL TEXT CONFIRMATION (after every booking):
- Always offer text first: "Want me to text you the appointment details so you have them?"
- If yes, get their number. If you already have it: "Got it, I'll send that over."
- Then try for email: "What's a good email for the confirmation?"
- The post-call text is the only part of the call that persists physically. It's what the caller shows their spouse. It must include: business name, service, date/time, address, and the business phone number to call back.

COMMON QUESTIONS:
- "Are you insured?" → "Yes, fully insured."
- "Do you give free estimates?" → "Yeah, the estimate's no charge. Want me to get you on the schedule for one?"
- "Can someone come look first?" → "Most of the time I can give you a price right here. Tell me what you've got."
- "How soon can you come?" → "Usually within a day or two. When were you thinking?"
- "Do you work weekends?" → "Saturday's our busiest day. The sooner you book the better."
- "How long will it take?" → "Depends on the scope, but I can give you a better idea once I know the details."
- "Are you the owner?" → "I handle the scheduling. What can I get set up for you?"
- "What's your warranty?" → "We stand behind our work. Any issues, just call us and we'll make it right."
- "Can you match a price?" → "Our rates are fair for the area. Want me to get you a quote so you can compare?"
- "Where do I pay?" → "We collect payment after the job's done and you're happy."

HOW YOU HANDLE ANYTHING:
When someone asks you something not on this list, you don't freeze and you don't say "I don't know."

If you can figure it out — answer it confidently.
If it's about pricing for something not listed — estimate based on size, time, or scope. Give a range: "Usually runs [estimate], could be a little more or less once we see it."
If they ask about a service you don't offer — say what you DO do that's close. Find the overlap.
If it's truly off the wall — keep it light and steer back: "Can't help with that one, but if you need {bt_title.lower()} work, that's us."
If they want someone specific — get their info naturally: "They're out on a job. Can I grab your name and number? They'll call you back within the hour."

CLOSING RULES:
- Always use "which" not "whether": "Which day works better?" not "Would you like to schedule?"
- Assume the booking: "I've got Tuesday afternoon or Thursday morning — which one?"
- If they hesitate: "I can pencil you in and you can always cancel. No commitment."
- Create real scarcity when true: "I have two slots left this week" beats "we have availability."

Every call ends one of two ways: BOOKED, or they know how to reach you when they're ready.
"""


def create_retell_agent(business_name, business_type, city_full, template, client_cfg=None):
    cfg = client_cfg or {}
    bt_title = title_case(business_type)
    system_prompt = build_system_prompt(business_name, business_type, city_full, template, cfg)
    voice = cfg.get("voice") or BUSINESS_VOICES.get(business_type, "11labs-Myra")

    # Step 1: Create LLM
    llm_payload = {
        "model": "claude-4.6-sonnet",
        "general_prompt": system_prompt,
        "begin_message": f"Hi, thanks for calling {business_name}, this is Sarah. How can I help you today?",
        "general_tools": [
            {
                "type": "end_call",
                "name": "end_call",
                "description": "End the call when booking is complete, on voicemail/IVR, or caller has no more questions.",
            }
        ],
    }
    headers = {"Authorization": f"Bearer {RETELL_KEY}"}

    try:
        llm_resp = http_post(
            "https://api.retellai.com/create-retell-llm",
            llm_payload,
            headers=headers,
            timeout=15,
        )
        llm_id = llm_resp.get("llm_id")
        if not llm_id:
            raise ValueError(f"No llm_id in response: {llm_resp}")
    except Exception as e:
        return None, None, f"Retell LLM creation failed: {e}"

    # Step 2: Create Agent
    agent_payload = {
        "response_engine": {
            "type": "retell-llm",
            "llm_id": llm_id,
        },
        "agent_name": business_name,
        "voice_id": voice,
        "voice_speed": 1.0,
        "language": "en-US",
        "interruption_sensitivity": 0.6,
        "responsiveness": 0.8,
        "enable_backchannel": True,
        "backchannel_frequency": 0.7,
        "reminder_trigger_ms": 8000,
        "reminder_max_count": 2,
        "post_call_analysis_data": [
            {"name": "call_type", "description": "booking, inquiry, complaint, spam, or wrong_number", "type": "string"},
            {"name": "customer_name", "description": "Caller name if provided", "type": "string"},
            {"name": "booked", "description": "Whether an appointment was booked", "type": "boolean"},
            {"name": "service_requested", "description": "What service the caller needed", "type": "string"},
            {"name": "urgency", "description": "routine, same-day, or emergency", "type": "string"},
        ],
    }

    try:
        agent_resp = http_post(
            "https://api.retellai.com/create-agent",
            agent_payload,
            headers=headers,
            timeout=15,
        )
        agent_id = agent_resp.get("agent_id")
        if not agent_id:
            raise ValueError(f"No agent_id in response: {agent_resp}")
    except Exception as e:
        return llm_id, None, f"Retell Agent creation failed: {e}"

    # Step 3: Verify prompt was actually set
    try:
        verify = http_get(
            f"https://api.retellai.com/get-retell-llm/{llm_id}",
            headers=headers,
            timeout=10,
        )
        prompt_len = len(verify.get("general_prompt", "") or "")
        if prompt_len < 50:
            print(f"  ⚠️  WARNING: LLM prompt is {prompt_len} chars — uploading again")
            http_patch(
                f"https://api.retellai.com/update-retell-llm/{llm_id}",
                {"general_prompt": system_prompt},
                headers=headers,
                timeout=15,
            )
    except Exception:
        pass

    return llm_id, agent_id, None


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 4 — N8N WORKFLOW CREATION
# ──────────────────────────────────────────────────────────────────────────────

def n8n_get(path):
    url = f"{N8N_BASE}{path}"
    headers = {"X-N8N-API-KEY": N8N_API_KEY}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def n8n_post(path, payload):
    url = f"{N8N_BASE}{path}"
    data = json.dumps(payload).encode()
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def n8n_activate(workflow_id):
    url = f"{N8N_BASE}/workflows/{workflow_id}/activate"
    headers = {
        "X-N8N-API-KEY": N8N_API_KEY,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception:
        return {}


def build_post_call_workflow(business_name, business_slug, city_full):
    """Webhook → parse booking → ntfy Boston"""
    webhook_path = f"booking-{business_slug}"
    return {
        "name": f"{business_name} — Post-Call Handler",
        "nodes": [
            {
                "id": "webhook-trigger",
                "name": "Booking Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {
                    "httpMethod": "POST",
                    "path": webhook_path,
                    "responseMode": "onReceived",
                    "responseData": "allEntries",
                },
                "webhookId": webhook_path,
            },
            {
                "id": "parse-booking",
                "name": "Parse Booking Data",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [460, 300],
                "parameters": {
                    "jsCode": (
                        "const body = $input.first().json.body || $input.first().json;\n"
                        "const name = body.customer_name || body.name || 'Unknown';\n"
                        "const address = body.address || body.service_address || 'No address';\n"
                        "const date = body.date || body.scheduled_date || 'TBD';\n"
                        "const time = body.time || body.scheduled_time || 'TBD';\n"
                        "const service = body.service || body.job_type || 'General service';\n"
                        "const phone = body.phone || body.customer_phone || 'No phone';\n"
                        "const email = body.email || body.customer_email || '';\n"
                        "return [{ json: { name, address, date, time, service, phone, email } }];"
                    )
                },
            },
            {
                "id": "ntfy-alert",
                "name": "Notify Boston",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [680, 300],
                "parameters": {
                    "method": "POST",
                    "url": f"https://ntfy.sh/{NTFY_CHANNEL}",
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "Title", "value": f"New Booking — {business_name}"},
                            {"name": "Priority", "value": "high"},
                        ]
                    },
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": []
                    },
                    "specifyBody": "string",
                    "body": (
                        "=New booking!\n"
                        "Name: {{$json.name}}\n"
                        "Service: {{$json.service}}\n"
                        "Address: {{$json.address}}\n"
                        "Date: {{$json.date}} at {{$json.time}}\n"
                        "Phone: {{$json.phone}}"
                    ),
                    "options": {"timeout": 8000},
                },
            },
        ],
        "connections": {
            "Booking Webhook": {
                "main": [[{"node": "Parse Booking Data", "type": "main", "index": 0}]]
            },
            "Parse Booking Data": {
                "main": [[{"node": "Notify Boston", "type": "main", "index": 0}]]
            },
        },
        "settings": {"executionOrder": "v1"},
        "staticData": None,
    }


def build_job_complete_workflow(business_name, business_slug, city_full, client_cfg=None):
    """Webhook → payment link → review request via ntfy"""
    cfg = client_cfg or {}
    payment_method = cfg.get("payment_method", "venmo")
    payment_instructions = {
        "venmo": "Send Venmo payment request to customer.",
        "square": "Send Square invoice link to customer.",
        "stripe": "Send Stripe payment link to customer.",
        "cash": "Collect cash payment at job site.",
        "invoice": "Send invoice to customer email.",
    }.get(payment_method, "Send Venmo payment request to customer.")
    review_delay_hours = cfg.get("review_request_delay_hours", 2)
    webhook_path = f"job-complete-{business_slug}"
    return {
        "name": f"{business_name} — Job Complete Handler",
        "nodes": [
            {
                "id": "job-webhook",
                "name": "Job Complete Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {
                    "httpMethod": "POST",
                    "path": webhook_path,
                    "responseMode": "onReceived",
                    "responseData": "allEntries",
                },
                "webhookId": webhook_path,
            },
            {
                "id": "parse-job",
                "name": "Parse Job Data",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [460, 300],
                "parameters": {
                    "jsCode": (
                        "const body = $input.first().json.body || $input.first().json;\n"
                        "const name = body.customer_name || body.name || 'Customer';\n"
                        "const phone = body.phone || body.customer_phone || '';\n"
                        "const amount = body.amount || body.job_total || '0';\n"
                        "const jobId = body.job_id || Date.now().toString();\n"
                        "return [{ json: { name, phone, amount, jobId } }];"
                    )
                },
            },
            {
                "id": "ntfy-payment",
                "name": "Send Payment Alert",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [680, 200],
                "parameters": {
                    "method": "POST",
                    "url": f"https://ntfy.sh/{NTFY_CHANNEL}",
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "Title", "value": f"Job Complete — {business_name}"},
                            {"name": "Priority", "value": "default"},
                        ]
                    },
                    "sendBody": True,
                    "specifyBody": "string",
                    "body": (
                        "=Job complete!\n"
                        "Customer: {{$json.name}}\n"
                        "Amount: ${{$json.amount}}\n"
                        "Phone: {{$json.phone}}\n"
                        f"{payment_instructions}\n"
                        f"Schedule review request for {review_delay_hours} hours from now."
                    ),
                    "options": {"timeout": 8000},
                },
            },
            {
                "id": "ntfy-review",
                "name": "Queue Review Request",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [680, 400],
                "parameters": {
                    "method": "POST",
                    "url": f"https://ntfy.sh/{NTFY_CHANNEL}",
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "Title", "value": f"Review Request Due — {business_name}"},
                            {"name": "Priority", "value": "low"},
                            {"name": "At", "value": f"+{review_delay_hours}h"},
                        ]
                    },
                    "sendBody": True,
                    "specifyBody": "string",
                    "body": (
                        "=Send review request to {{$json.name}} ({{$json.phone}}).\n"
                        "Text: \"Hi {{$json.name}}, thanks for choosing us! "
                        "Would you mind leaving us a quick Google review? "
                        f"Just search '{business_name}' on Google and click 'Write a review'. "
                        "It means everything to a local business.\""
                    ),
                    "options": {"timeout": 8000},
                },
            },
        ],
        "connections": {
            "Job Complete Webhook": {
                "main": [[{"node": "Parse Job Data", "type": "main", "index": 0}]]
            },
            "Parse Job Data": {
                "main": [
                    [{"node": "Send Payment Alert", "type": "main", "index": 0}],
                    [{"node": "Queue Review Request", "type": "main", "index": 0}],
                ]
            },
        },
        "settings": {"executionOrder": "v1"},
        "staticData": None,
    }


def build_daily_briefing_workflow(business_name, business_slug, city_full, agent_id, client_cfg=None):
    """Daily briefing → ntfy"""
    cfg = client_cfg or {}
    briefing_time = cfg.get("daily_briefing_time", "08:00")
    briefing_days = cfg.get("daily_briefing_days", "1-6")
    hour, minute = briefing_time.split(":") if ":" in briefing_time else ("8", "0")
    cron_expr = f"{minute} {hour} * * {briefing_days}"
    return {
        "name": f"{business_name} — Daily Briefing",
        "nodes": [
            {
                "id": "daily-trigger",
                "name": f"Daily {briefing_time} Trigger",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1,
                "position": [240, 300],
                "parameters": {
                    "rule": {
                        "interval": [
                            {
                                "field": "cronExpression",
                                "expression": cron_expr,
                            }
                        ]
                    }
                },
            },
            {
                "id": "briefing-message",
                "name": "Build Briefing",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [460, 300],
                "parameters": {
                    "jsCode": "\n".join([
                        "const today = new Date().toLocaleDateString('en-US', {weekday:'long', month:'short', day:'numeric'});",
                        "const msg = `" + business_name + " Daily Briefing\\nDate: ${today}\\n\\nAction items:\\n- Check new bookings in Google Sheets\\n- Confirm today's jobs with crews\\n- Review any pending reviews or complaints\\n- Agent ID: " + (agent_id or "Not yet assigned") + "\\n\\nCity: " + city_full + "`;",
                        "return [{ json: { message: msg } }];",
                    ])
                },
            },
            {
                "id": "ntfy-briefing",
                "name": "Send Daily Briefing",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [680, 300],
                "parameters": {
                    "method": "POST",
                    "url": f"https://ntfy.sh/{NTFY_CHANNEL}",
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "Title", "value": f"Daily Briefing — {business_name}"},
                            {"name": "Priority", "value": "default"},
                        ]
                    },
                    "sendBody": True,
                    "specifyBody": "string",
                    "body": "={{$json.message}}",
                    "options": {"timeout": 8000},
                },
            },
        ],
        "connections": {
            f"Daily {briefing_time} Trigger": {
                "main": [[{"node": "Build Briefing", "type": "main", "index": 0}]]
            },
            "Build Briefing": {
                "main": [[{"node": "Send Daily Briefing", "type": "main", "index": 0}]]
            },
        },
        "settings": {"executionOrder": "v1"},
        "staticData": None,
    }


def create_n8n_workflows(business_name, business_type, business_slug, city_full, agent_id, client_cfg=None):
    results = {}
    errors = []
    workflow_defs = [
        ("post_call", build_post_call_workflow(business_name, business_slug, city_full)),
        ("job_complete", build_job_complete_workflow(business_name, business_slug, city_full, client_cfg)),
        ("daily_briefing", build_daily_briefing_workflow(business_name, business_slug, city_full, agent_id, client_cfg)),
    ]
    for key, wf_def in workflow_defs:
        try:
            resp = n8n_post("/workflows", wf_def)
            wf_id = resp.get("id")
            if not wf_id:
                raise ValueError(f"No workflow ID returned: {resp}")
            if key != "daily_briefing":
                n8n_activate(wf_id)
            webhook_path = None
            for node in wf_def.get("nodes", []):
                if node.get("type") == "n8n-nodes-base.webhook":
                    webhook_path = node.get("parameters", {}).get("path")
                    break
            results[key] = {
                "id": wf_id,
                "name": wf_def["name"],
                "webhook_url": (
                    f"{N8N_WEBHOOK_BASE}/{webhook_path}" if webhook_path else None
                ),
            }
        except Exception as e:
            errors.append(f"{key}: {e}")
            results[key] = {"id": None, "name": wf_def["name"], "webhook_url": None, "error": str(e)}
    return results, errors


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 5 — OUTPUT PACKAGE
# ──────────────────────────────────────────────────────────────────────────────

def generate_launch_plan(
    business_name, business_type, city_full, template,
    market, llm_id, agent_id, retell_error,
    workflows, wf_errors, budget, biz_dir
):
    city, state = city_state(city_full)
    bt_title = title_case(business_type)
    voice = BUSINESS_VOICES.get(business_type, "11labs-Myra")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rev_low = market["revenue_low"]
    rev_high = market["revenue_high"]
    margin = template["margin"]
    profit_low = int(rev_low * margin)
    profit_high = int(rev_high * margin)

    retell_section = ""
    if agent_id:
        retell_section = f"""
## Retell AI Agent

| Field | Value |
|-------|-------|
| Agent ID | `{agent_id}` |
| LLM ID | `{llm_id}` |
| Voice | {voice} |
| Interruption Sensitivity | 0.6 |

### To Attach a Phone Number:
1. Go to retellai.com → Dashboard → Phone Numbers
2. Import or purchase a local ({state}) number
3. Assign Agent ID: `{agent_id}`
4. Test by calling the number — agent should answer immediately

### Post-Call Webhook:
Set the post-call webhook in Retell to:
`{workflows.get('post_call', {}).get('webhook_url', 'NOT CREATED — see errors')}`
"""
    else:
        retell_section = f"""
## Retell AI Agent

**CREATION FAILED:** {retell_error}

Manual steps:
1. Go to retellai.com → Create LLM (claude-4.6-sonnet)
2. Use the system prompt saved in `retell_agent.json`
3. Create agent with the LLM
4. Attach a local phone number
"""

    wf_section = "## n8n Workflows\n\n"
    wf_names = {
        "post_call": "Post-Call Handler (Booking → Notify Boston)",
        "job_complete": "Job Complete Handler (Payment → Review Request)",
        "daily_briefing": "Daily Briefing (8am Mon-Sat → ntfy) [INACTIVE — activate when live]",
    }
    for key, info in workflows.items():
        label = wf_names.get(key, key)
        if info.get("id"):
            webhook_line = f"\n  - Webhook: `{info['webhook_url']}`" if info.get("webhook_url") else ""
            wf_section += f"- **{label}**\n  - ID: `{info['id']}`{webhook_line}\n"
        else:
            wf_section += f"- **{label}** — FAILED: {info.get('error', 'unknown error')}\n"

    newline = "\n"
    competitor_lines = ""
    for c in market["competitor_list"]:
        cname = c['name'][:40]
        crating = c['rating']
        creviews = c['reviews']
        caddr = c['address'][:40]
        competitor_lines += f"| {cname} | {crating} | {creviews} | {caddr} |\n"
    no_competitor_row = "| None found | — | — | — |"

    gaps_text = "\n".join(f"- {g}" for g in market["gaps"])

    plan = f"""# {business_name} — Launch Plan
*Generated: {now}*

---

## Market Analysis — {city_full}

| Metric | Value |
|--------|-------|
| Market Score | **{market['market_score']}/10** |
| Competition Level | {market['competition_level']} |
| Competitors Found | {market['competitors']} |
| Avg Competitor Rating | {market['avg_rating']} ⭐ |
| Avg Review Count | {market['avg_reviews']} reviews |
| Total Market Reviews | {market['total_reviews']} |
| Estimated Population | {market['pop_estimate']} |
| Recommendation | **{market['recommendation']}** |

### Revenue Projection
| Scenario | Monthly Revenue | Monthly Profit ({int(margin*100)}% margin) |
|----------|----------------|-------------------------------------------|
| Conservative | ${rev_low:,} | ${profit_low:,} |
| Strong | ${rev_high:,} | ${profit_high:,} |

### Market Gaps Identified
{gaps_text}

### Local Competitors Found
| Name | Rating | Reviews | Address |
|------|--------|---------|---------|
{competitor_lines if competitor_lines else no_competitor_row}

---
{retell_section}

---
{wf_section}

---

## Google Sheets Columns (Manual Setup)

Create a Google Sheet named `{business_name} CRM` with these columns:

| Column | Description |
|--------|-------------|
| A: JobID | Auto-generated or manual |
| B: CustomerName | From booking |
| C: Phone | Customer phone |
| D: Email | Customer email (get every call) |
| E: Address | Service address |
| F: ServiceDate | Scheduled date |
| G: ServiceTime | Scheduled time |
| H: JobType | Service description |
| I: QuotedPrice | Price given on call |
| J: FinalPrice | Actual charged |
| K: Status | Scheduled / Complete / Cancelled |
| L: PaymentStatus | Pending / Paid |
| M: ReviewSent | Yes/No |
| N: ReviewReceived | Yes/No |
| O: LeadSource | LSA / Facebook / Nextdoor / Referral / etc |
| P: Notes | Any notes from call |

---

## Google LSA Setup Checklist

- [ ] Create Google Business Profile at business.google.com
- [ ] Category: "{template['category']}"
- [ ] Service area: 25-mile radius from {city}, {state}
- [ ] Hours: 7am-7pm Mon-Sat (AI answers 24/7)
- [ ] Upload photos (truck/equipment, before/after, team)
- [ ] Write business description (AI handles this in expansion mode)
- [ ] Apply for Local Services Ads at ads.google.com/local-services-ads
- [ ] Complete background check (~$50)
- [ ] Upload proof of insurance
- [ ] Set starting budget: ${budget}/month
- [ ] Target keywords: {', '.join(template['keywords'])}
- [ ] Add business phone number (the Retell number)

---

## First 30 Days Action Plan

### Week 1 — Foundation
- [ ] Attach phone number to Retell agent `{agent_id or "TBD"}`
- [ ] Test the agent: call the number, run through booking flow
- [ ] Create Google Business Profile
- [ ] Post first 3 photos to GBP
- [ ] Submit LSA application
- [ ] Create Google Sheet CRM (columns above)

### Week 2 — Soft Launch
- [ ] Post on Facebook Marketplace: "{bt_title} in {city} — Same-Day Available"
- [ ] Post on Craigslist (free services section)
- [ ] Join {city} {state} Facebook community group — introduce yourself
- [ ] Post on Nextdoor as local business
- [ ] Target first 5 jobs at 10-15% below normal rate — prioritize reviews

### Week 3 — Traction
- [ ] Follow up with every past customer for a Google review
- [ ] LSA should be live by now — monitor lead cost
- [ ] Call 5 local real estate agents — offer $25 referral fee per job
- [ ] Call 3 property management companies — pitch volume discount
- [ ] Confirm post-call webhook is writing bookings to sheet

### Week 4 — Optimize
- [ ] Review lead sources — where are calls coming from?
- [ ] Check average job value vs. projections
- [ ] Adjust LSA daily budget based on lead quality
- [ ] Identify which neighborhoods have the most jobs — plan door hangers
- [ ] Boston reviews ntfy alerts — any patterns in missed bookings?

---

## Revenue Projections — 90 Days

| Month | Expected Jobs | Avg Job | Revenue | Profit |
|-------|--------------|---------|---------|--------|
| Month 1 | 15-25 | ${template['avg_job']} | ${int(20 * template['avg_job']):,} | ${int(20 * template['avg_job'] * margin):,} |
| Month 2 | 30-50 | ${template['avg_job']} | ${int(40 * template['avg_job']):,} | ${int(40 * template['avg_job'] * margin):,} |
| Month 3 | 50-80 | ${template['avg_job']} | ${int(65 * template['avg_job']):,} | ${int(65 * template['avg_job'] * margin):,} |

*Assumes LSA live by end of Week 2. Google reviews compounding from Week 3 on.*

---

## Monthly Cost Estimate

| Item | Monthly Cost |
|------|-------------|
| Retell AI | ~$40-80 |
| n8n Cloud | ~$20-50 |
| Google LSA | ${budget}/month |
| Phone number | ~$5 |
| Misc (gas, dump fees at start) | Varies |
| **Total fixed** | **~${budget + 100}-{budget + 200}/month** |

**Break-even:** {max(2, int((budget + 150) / template['avg_job']))} jobs/month

---

## Emergency Contacts / Next Steps

- Retell dashboard: https://retellai.com
- n8n dashboard: https://jamross.app.n8n.cloud
- Google Business: https://business.google.com
- ntfy channel: https://ntfy.sh/{NTFY_CHANNEL}

**Questions / issues:** Boston reviews ntfy alerts daily.
"""
    return plan


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 6 — NTFY ALERT
# ──────────────────────────────────────────────────────────────────────────────

def send_ntfy_alert(business_name, business_type, city_full, agent_id, market):
    city, state = city_state(city_full)
    rev_low = market["revenue_low"]
    rev_high = market["revenue_high"]
    score = market["market_score"]
    rec = market["recommendation"]

    msg = (
        f"New business built: {business_name}\n"
        f"Type: {title_case(business_type)} | City: {city_full}\n"
        f"Market Score: {score}/10 — {rec}\n"
        f"Agent ID: {agent_id or 'creation failed'}\n"
        f"Revenue potential: ${rev_low:,}-${rev_high:,}/month\n"
        f"Launch plan saved to BOSS_HQ/businesses/"
    )

    # ntfy prefers plain text body, not JSON
    try:
        url = f"https://ntfy.sh/{NTFY_CHANNEL}"
        data = msg.encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Title": f"Business Built: {business_name}",
                "Priority": "high",
                "Content-Type": "text/plain",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return True
    except Exception as e:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="BOSS Business Builder — build a complete autonomous local service business"
    )
    parser.add_argument("business_type", help='Business type, e.g. "junk removal"')
    parser.add_argument("city", help='City and state, e.g. "Tupelo MS"')
    parser.add_argument(
        "--budget",
        type=int,
        default=500,
        help="Monthly ad budget in dollars (default: 500)",
    )
    parser.add_argument(
        "--business-name",
        dest="business_name",
        default=None,
        help='Override business name (default: "BOSS [Type] [City]")',
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        default=None,
        help="Path to client config JSON for per-client customization",
    )
    args = parser.parse_args()

    raw_type = args.business_type.lower().strip()
    business_type = normalize_business_type(raw_type)
    city_full = args.city.strip()
    budget = args.budget

    client_cfg = None
    if args.config_path:
        client_cfg = load_client_config(args.config_path)
        print(f"Loaded client config: {args.config_path}")
        if client_cfg.get("owner_name"):
            print(f"  Client: {client_cfg['owner_name']}")
        if client_cfg.get("package"):
            print(f"  Package: {client_cfg['package']}")

    city, state = city_state(city_full)
    bt_title = title_case(business_type)
    city_title = title_case(city)

    if business_type not in BUSINESS_TEMPLATES:
        supported = ", ".join(f'"{k}"' for k in BUSINESS_TEMPLATES.keys())
        print(f"Unknown business type: '{raw_type}' (normalized: '{business_type}')")
        print(f"Supported types: {supported}")
        sys.exit(1)

    template = BUSINESS_TEMPLATES[business_type]
    business_name = args.business_name or f"BOSS {bt_title} {city_title}"
    biz_slug = slug(business_type, city_full)
    biz_dir = BUSINESSES_DIR / biz_slug

    print(f"\nBOSS BUSINESS BUILDER")
    print(f"{'='*50}")
    print(f"Building: {business_name}")
    print(f"Market:   {city_full}")
    print(f"Budget:   ${budget}/month")
    print(f"{'='*50}\n")

    # ── Phase 1: Market Analysis ──────────────────────────────────────────────
    print("PHASE 1 — Market Analysis")
    market = analyze_market(business_type, city_full)
    print(
        f"  Competitors found: {market['competitors']} "
        f"(avg {market['avg_rating']} stars, avg {market['avg_reviews']} reviews)"
    )
    print(f"  Competition level: {market['competition_level']}")
    print(f"  Market score: {market['market_score']}/10")
    print(f"  Revenue potential: ${market['revenue_low']:,}-${market['revenue_high']:,}/month")
    print(f"  Recommendation: {market['recommendation']}")
    print(f"Market analyzed\n")

    # ── Phase 2: Business Configuration ──────────────────────────────────────
    print("PHASE 2 — Business Configuration")
    print(f"  Template: {template['category']}")
    print(f"  Avg job value: ${template['avg_job']}")
    print(f"  Gross margin: {int(template['margin']*100)}%")
    print(f"Business configured\n")

    # ── Phase 3: Retell Agent ─────────────────────────────────────────────────
    print("PHASE 3 — Creating Retell Agent")
    llm_id, agent_id, retell_error = create_retell_agent(
        business_name, business_type, city_full, template, client_cfg,
    )
    if agent_id:
        print(f"  LLM ID: {llm_id}")
        print(f"Retell agent created: {agent_id}\n")
    else:
        print(f"  LLM ID: {llm_id or 'not created'}")
        print(f"Retell agent FAILED: {retell_error}\n")

    # ── Phase 4: n8n Workflows ────────────────────────────────────────────────
    print("PHASE 4 — Creating n8n Workflows")
    workflows, wf_errors = create_n8n_workflows(
        business_name, business_type, biz_slug, city_full, agent_id, client_cfg,
    )
    for key, info in workflows.items():
        if info.get("id"):
            webhook_display = f" → {info['webhook_url']}" if info.get("webhook_url") else ""
            print(f"  {info['name']}: {info['id']}{webhook_display}")
            print(f"n8n workflow created: {info['name']}")
        else:
            print(f"  {info['name']}: FAILED — {info.get('error', 'unknown')}")
    if wf_errors:
        print(f"  Workflow errors: {wf_errors}")
    print()

    # ── Phase 5: Output Package ───────────────────────────────────────────────
    print("PHASE 5 — Building Output Package")
    biz_dir.mkdir(parents=True, exist_ok=True)

    # Launch plan
    launch_plan = generate_launch_plan(
        business_name, business_type, city_full, template,
        market, llm_id, agent_id, retell_error,
        workflows, wf_errors, budget, biz_dir
    )
    launch_plan_path = biz_dir / "LAUNCH_PLAN.md"
    launch_plan_path.write_text(launch_plan)
    print(f"  Launch plan: {launch_plan_path}")

    # Retell agent config
    cfg = client_cfg or {}
    retell_config = {
        "business_name": business_name,
        "business_type": business_type,
        "city": city_full,
        "llm_id": llm_id,
        "agent_id": agent_id,
        "retell_error": retell_error,
        "system_prompt": build_system_prompt(business_name, business_type, city_full, template, client_cfg),
        "voice": cfg.get("voice") or BUSINESS_VOICES.get(business_type, "11labs-Myra"),
        "interruption_sensitivity": 0.6,
        "created_at": datetime.now().isoformat(),
    }
    retell_path = biz_dir / "retell_agent.json"
    retell_path.write_text(json.dumps(retell_config, indent=2))
    print(f"  Retell config: {retell_path}")

    # Workflow IDs
    workflow_ids = {
        "business": business_name,
        "city": city_full,
        "created_at": datetime.now().isoformat(),
        "workflows": workflows,
    }
    workflow_ids_path = biz_dir / "workflow_ids.json"
    workflow_ids_path.write_text(json.dumps(workflow_ids, indent=2))
    print(f"  Workflow IDs: {workflow_ids_path}")

    # Market analysis
    market_path = biz_dir / "market_analysis.json"
    market_path.write_text(json.dumps(market, indent=2))
    print(f"  Market data: {market_path}")

    # Client record
    import hashlib
    dashboard_code = f"{business_type[:4].upper()}-{biz_slug[-8:].upper()}-{hashlib.md5(business_name.encode()).hexdigest()[:4].upper()}"
    wf_post_call = workflows.get("post_call", {})
    wf_job_complete = workflows.get("job_complete", {})
    client_record = {
        "client_id": biz_slug,
        "business_name": business_name,
        "owner_name": cfg.get("owner_name", ""),
        "owner_phone": cfg.get("owner_phone", ""),
        "owner_email": cfg.get("owner_email", ""),
        "business_type": business_type,
        "city": city_full.split()[0] if " " in city_full else city_full,
        "state": city_full.split()[-1] if " " in city_full else "",
        "dashboard_code": dashboard_code,
        "plan": cfg.get("package", "starter"),
        "start_date": datetime.now().strftime("%Y-%m-%d"),
        "status": "building",
        "spp_partner": cfg.get("spp_partner", False),
        "stack": {
            "receptionist": {
                "enabled": bool(agent_id),
                "agent_id": agent_id or "",
                "phone_number": "",
                "business_hours": cfg.get("business_hours", "Monday through Saturday, 7am to 7pm"),
                "emergency_protocol": cfg.get("emergency_protocol") or EMERGENCY_PROTOCOLS.get(business_type, ""),
            },
            "post_call_handler": {
                "enabled": bool(wf_post_call.get("id")),
                "workflow_id": wf_post_call.get("id", ""),
                "webhook_url": wf_post_call.get("webhook_url", ""),
            },
            "job_complete_handler": {
                "enabled": bool(wf_job_complete.get("id")),
                "workflow_id": wf_job_complete.get("id", ""),
                "webhook_url": wf_job_complete.get("webhook_url", ""),
                "payment_method": cfg.get("payment_method", "venmo"),
            },
            "daily_briefing": {
                "enabled": bool(workflows.get("daily_briefing", {}).get("id")),
                "workflow_id": workflows.get("daily_briefing", {}).get("id", ""),
                "time": cfg.get("daily_briefing_time", "08:00"),
                "days": cfg.get("daily_briefing_days", "1-6"),
            },
            "dashboard": {
                "enabled": True,
                "url": "bosssystems.co/client-dashboard.html",
                "login_code": dashboard_code,
            },
        },
        "market": {
            "score": market["market_score"],
            "recommendation": market["recommendation"],
            "competitors": market["competitors"],
            "revenue_range": f"${market['revenue_low']:,}-${market['revenue_high']:,}/month",
        },
        "config": cfg if cfg else CLIENT_CONFIG_DEFAULTS,
        "created_at": datetime.now().isoformat(),
    }
    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    client_path = CLIENTS_DIR / f"{biz_slug}.json"
    client_path.write_text(json.dumps(client_record, indent=2))
    print(f"  Client record: {client_path}")
    print(f"  Dashboard code: {dashboard_code}")

    print(f"Output package saved\n")

    # ── Phase 6: ntfy Alert ───────────────────────────────────────────────────
    print("PHASE 6 — Sending ntfy Alert")
    alert_sent = send_ntfy_alert(business_name, business_type, city_full, agent_id, market)
    if alert_sent:
        print(f"ntfy alert sent to {NTFY_CHANNEL}\n")
    else:
        print(f"ntfy alert FAILED (non-critical)\n")

    # ── Phase 7: Onboarding Trigger ──────────────────────────────────────────
    print("PHASE 7 — Triggering Onboarding")
    onboarding_payload = {
        "business_name": business_name,
        "business_type": business_type,
        "city": city_full,
        "owner_name": cfg.get("owner_name", ""),
        "owner_phone": cfg.get("owner_phone", ""),
        "dashboard_code": dashboard_code,
        "agent_id": agent_id or "",
        "spp_partner": cfg.get("spp_partner", False),
        "package": cfg.get("package", "starter"),
    }
    try:
        onboarding_data = json.dumps(onboarding_payload).encode()
        onboarding_req = urllib.request.Request(
            f"{N8N_WEBHOOK_BASE}/client-onboarding-start",
            data=onboarding_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(onboarding_req, timeout=8) as r:
            print(f"  Onboarding drip triggered for {cfg.get('owner_name') or business_name}")
    except Exception as e:
        print(f"  Onboarding webhook failed (non-critical): {e}")
    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("=" * 50)
    print(f"BUILD COMPLETE — {business_name}")
    print("=" * 50)
    print(f"  Market score:    {market['market_score']}/10 ({market['recommendation']})")
    print(f"  Competition:     {market['competition_level']} ({market['competitors']} competitors)")
    print(f"  Revenue target:  ${market['revenue_low']:,}-${market['revenue_high']:,}/month")
    print(f"  Retell agent:    {agent_id or 'FAILED — see retell_agent.json'}")
    wf_ids = [info['id'] for info in workflows.values() if info.get('id')]
    print(f"  n8n workflows:   {len(wf_ids)}/3 created {wf_ids}")
    print(f"  Launch plan:     {launch_plan_path}")
    print()

    if market["recommendation"] in ("GO", "STRONG GO"):
        print(f"This market is a {market['recommendation']}. Next step: attach a local phone number")
        print(f"to Retell agent {agent_id or '[create manually]'} and start Google LSA.")
    else:
        print(f"Market scored {market['market_score']}/10. Review the launch plan before committing budget.")

    print()


# ──────────────────────────────────────────────────────────────────────────────
# PART 3 EXTENSION — AUTOMATION BUILDER
# ──────────────────────────────────────────────────────────────────────────────

def build_automation(automation_key, business_config):
    """
    Look up an automation in the library and build it using the right tools.
    Returns: {"key": ..., "status": "built"|"failed", "ids": {...}, "notes": "..."}

    automation_key: e.g. "phone_receptionist", "missed_call_textback"
    business_config: dict with keys: business_name, business_type, city, slug, template
    """
    import sys
    sys.path.insert(0, str(BOSS_HQ / "scripts"))
    try:
        from automation_library import AUTOMATION_CATALOG
    except ImportError:
        return {"key": automation_key, "status": "failed", "ids": {}, "notes": "automation_library not found"}

    if automation_key not in AUTOMATION_CATALOG:
        return {"key": automation_key, "status": "failed", "ids": {}, "notes": f"Unknown automation: {automation_key}"}

    auto = AUTOMATION_CATALOG[automation_key]
    biz_name  = business_config.get("business_name", "BOSS Business")
    biz_type  = business_config.get("business_type", "junk removal")
    city_full = business_config.get("city", "Tyler TX")
    biz_slug  = business_config.get("slug", slug(biz_type, city_full))
    template  = business_config.get("template", BUSINESS_TEMPLATES.get(biz_type, BUSINESS_TEMPLATES["junk removal"]))
    client_cfg = business_config.get("client_cfg")

    ids = {}
    notes = []

    # ── PHONE RECEPTIONIST ──────────────────────────────────────────────────
    if automation_key == "phone_receptionist":
        print(f"    Building Retell AI receptionist for {biz_name}...")
        llm_id, agent_id, err = create_retell_agent(biz_name, biz_type, city_full, template, client_cfg)
        if agent_id:
            ids = {"llm_id": llm_id, "agent_id": agent_id}
            notes.append(f"Attach phone number to agent_id: {agent_id} in Retell dashboard")
            return {"key": automation_key, "status": "built", "ids": ids, "notes": "\n".join(notes)}
        else:
            return {"key": automation_key, "status": "failed", "ids": {}, "notes": str(err)}

    # ── MISSED CALL TEXT-BACK ───────────────────────────────────────────────
    elif automation_key == "missed_call_textback":
        print(f"    Building missed call text-back workflow...")
        webhook_path = f"missed-call-{biz_slug}"
        wf_def = {
            "name": f"{biz_name} — Missed Call Text-Back",
            "nodes": [
                {
                    "id": "mc-webhook",
                    "name": "Missed Call Trigger",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 1,
                    "position": [240, 300],
                    "parameters": {
                        "httpMethod": "POST",
                        "path": webhook_path,
                        "responseMode": "onReceived",
                        "responseData": "allEntries",
                    },
                    "webhookId": webhook_path,
                },
                {
                    "id": "mc-ntfy",
                    "name": "Alert Boston — Missed Call",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4,
                    "position": [460, 300],
                    "parameters": {
                        "method": "POST",
                        "url": f"https://ntfy.sh/{NTFY_CHANNEL}",
                        "sendHeaders": True,
                        "headerParameters": {"parameters": [
                            {"name": "Title", "value": f"Missed Call — {biz_name}"},
                            {"name": "Priority", "value": "high"},
                        ]},
                        "sendBody": True,
                        "specifyBody": "string",
                        "body": "=Missed call from: {{$json.body.from || $json.from || 'Unknown'}}\nText back now: 'Hey! This is {biz_name} — sorry we missed you. How can we help?'",
                        "options": {"timeout": 8000},
                    },
                },
            ],
            "connections": {
                "Missed Call Trigger": {"main": [[{"node": "Alert Boston — Missed Call", "type": "main", "index": 0}]]}
            },
            "settings": {"executionOrder": "v1"},
            "staticData": None,
        }
        try:
            resp = n8n_post("/workflows", wf_def)
            wf_id = resp.get("id")
            if wf_id:
                n8n_activate(wf_id)
                ids = {"workflow_id": wf_id, "webhook_url": f"{N8N_WEBHOOK_BASE}/{webhook_path}"}
                notes.append(f"Webhook URL: {N8N_WEBHOOK_BASE}/{webhook_path}")
                notes.append("Point your phone system's missed-call hook to this URL")
                return {"key": automation_key, "status": "built", "ids": ids, "notes": "\n".join(notes)}
            else:
                return {"key": automation_key, "status": "failed", "ids": {}, "notes": str(resp)}
        except Exception as e:
            return {"key": automation_key, "status": "failed", "ids": {}, "notes": str(e)}

    # ── REVIEW REQUEST ──────────────────────────────────────────────────────
    elif automation_key == "review_request":
        print(f"    Building review request automation...")
        webhook_path = f"review-req-{biz_slug}"
        wf_def = {
            "name": f"{biz_name} — Review Request",
            "nodes": [
                {
                    "id": "rr-webhook",
                    "name": "Job Complete Trigger",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 1,
                    "position": [240, 300],
                    "parameters": {
                        "httpMethod": "POST",
                        "path": webhook_path,
                        "responseMode": "onReceived",
                        "responseData": "allEntries",
                    },
                    "webhookId": webhook_path,
                },
                {
                    "id": "rr-wait",
                    "name": "Wait 2 Hours",
                    "type": "n8n-nodes-base.wait",
                    "typeVersion": 1,
                    "position": [460, 300],
                    "parameters": {"amount": 2, "unit": "hours"},
                },
                {
                    "id": "rr-ntfy",
                    "name": "Send Review Alert",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4,
                    "position": [680, 300],
                    "parameters": {
                        "method": "POST",
                        "url": f"https://ntfy.sh/{NTFY_CHANNEL}",
                        "sendHeaders": True,
                        "headerParameters": {"parameters": [
                            {"name": "Title", "value": f"Review Request Due — {biz_name}"},
                            {"name": "Priority", "value": "default"},
                        ]},
                        "sendBody": True,
                        "specifyBody": "string",
                        "body": "=Send review request to {{$json.body.name || $json.name || 'customer'}} ({{$json.body.phone || $json.phone || 'no phone'}}).\nText: 'Hi! Thanks for choosing {biz_name}. Could you leave us a Google review? Just search our name on Google and click Write a review. It means the world to us!'",
                        "options": {"timeout": 8000},
                    },
                },
            ],
            "connections": {
                "Job Complete Trigger": {"main": [[{"node": "Wait 2 Hours", "type": "main", "index": 0}]]},
                "Wait 2 Hours": {"main": [[{"node": "Send Review Alert", "type": "main", "index": 0}]]},
            },
            "settings": {"executionOrder": "v1"},
            "staticData": None,
        }
        try:
            resp = n8n_post("/workflows", wf_def)
            wf_id = resp.get("id")
            if wf_id:
                n8n_activate(wf_id)
                ids = {"workflow_id": wf_id, "webhook_url": f"{N8N_WEBHOOK_BASE}/{webhook_path}"}
                return {"key": automation_key, "status": "built", "ids": ids, "notes": f"Fire webhook when job done: {N8N_WEBHOOK_BASE}/{webhook_path}"}
            else:
                return {"key": automation_key, "status": "failed", "ids": {}, "notes": str(resp)}
        except Exception as e:
            return {"key": automation_key, "status": "failed", "ids": {}, "notes": str(e)}

    # ── PAYMENT COLLECTION ──────────────────────────────────────────────────
    elif automation_key == "payment_collection":
        # Reuse the job complete workflow from the core builder
        result = build_job_complete_workflow(biz_name, biz_slug, city_full, client_cfg)
        try:
            resp = n8n_post("/workflows", result)
            wf_id = resp.get("id")
            if wf_id:
                n8n_activate(wf_id)
                webhook_path = f"job-complete-{biz_slug}"
                return {
                    "key": automation_key,
                    "status": "built",
                    "ids": {"workflow_id": wf_id, "webhook_url": f"{N8N_WEBHOOK_BASE}/{webhook_path}"},
                    "notes": "Fire webhook at job completion with customer name, phone, amount",
                }
            else:
                return {"key": automation_key, "status": "failed", "ids": {}, "notes": str(resp)}
        except Exception as e:
            return {"key": automation_key, "status": "failed", "ids": {}, "notes": str(e)}

    # ── ALL OTHER AUTOMATIONS — LOGGED AS PLANNED ───────────────────────────
    else:
        tools_needed = ", ".join(auto.get("tools", []))
        build_hours  = auto.get("build_time_hours", 3)
        notes_text   = (
            f"Automation '{auto['name']}' logged. "
            f"Tools needed: {tools_needed}. "
            f"Build time: {build_hours}h. "
            f"This automation requires custom implementation. "
            f"Contact Boston to build: bosrossall@gmail.com"
        )
        return {"key": automation_key, "status": "planned", "ids": {}, "notes": notes_text}


STACK_TIERS = {
    "starter": [
        "phone_receptionist",
        "missed_call_textback",
        "payment_collection",
        "review_request",
    ],
    "growth": [
        "phone_receptionist",
        "missed_call_textback",
        "payment_collection",
        "review_request",
        "outbound_caller",
        "social_media_ai",
        "competitor_monitor",
        "re_engagement_campaign",
    ],
    "full": [
        "phone_receptionist",
        "missed_call_textback",
        "payment_collection",
        "review_request",
        "outbound_caller",
        "social_media_ai",
        "competitor_monitor",
        "re_engagement_campaign",
        "quote_generator",
        "dispatch_automation",
        "invoice_generator",
        "seasonal_campaigns",
        "revenue_dashboard",
    ],
}


def build_full_stack(business_type, city, business_name=None, tier="starter", client_cfg=None):
    """
    Build a complete automation stack for a business.

    tier: "starter" | "growth" | "full"
    Returns: {"business": ..., "tier": ..., "results": [...], "summary": {...}}
    """
    bt = business_type.lower().strip()
    template = BUSINESS_TEMPLATES.get(bt, BUSINESS_TEMPLATES["junk removal"])

    if not business_name:
        city_part, _ = city_state(city)
        business_name = f"BOSS {bt.replace('_',' ').title()} {city_part}"

    biz_slug = slug(bt, city)
    biz_dir  = BUSINESSES_DIR / biz_slug
    biz_dir.mkdir(parents=True, exist_ok=True)

    business_config = {
        "business_name": business_name,
        "business_type": bt,
        "city": city,
        "slug": biz_slug,
        "template": template,
        "client_cfg": client_cfg,
    }

    automations_to_build = STACK_TIERS.get(tier, STACK_TIERS["starter"])

    print(f"\nBUILDING FULL STACK — {tier.upper()} TIER")
    print(f"Business: {business_name} | City: {city} | Automations: {len(automations_to_build)}")
    print("=" * 60)

    results = []
    built = 0
    failed = 0
    planned = 0

    for auto_key in automations_to_build:
        print(f"\n  [{auto_key}]")
        result = build_automation(auto_key, business_config)
        results.append(result)
        status = result.get("status", "unknown")
        if status == "built":
            built += 1
            print(f"    Built — {result.get('notes', '')[:80]}")
        elif status == "planned":
            planned += 1
            print(f"    Planned (requires custom build) — {result.get('notes', '')[:60]}")
        else:
            failed += 1
            print(f"    Failed — {result.get('notes', '')[:80]}")

    summary = {
        "business": business_name,
        "city": city,
        "tier": tier,
        "total": len(automations_to_build),
        "built": built,
        "planned": planned,
        "failed": failed,
        "built_at": datetime.now().isoformat(),
    }

    # Save results
    results_path = biz_dir / f"stack_{tier}.json"
    with open(results_path, "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    print(f"\n{'='*60}")
    print(f"STACK BUILD COMPLETE")
    print(f"  Built:   {built}/{len(automations_to_build)}")
    print(f"  Planned: {planned}")
    print(f"  Failed:  {failed}")
    print(f"  Saved:   {results_path}")
    print()

    return {"summary": summary, "results": results}


if __name__ == "__main__":
    main()
