#!/usr/bin/env python3
"""
BOSS Superniche Prospect Scorer
Usage: python3 prospect_scorer.py "HVAC" "Corinth MS"
Finds the most targetable businesses in any market and generates personalized openers.
Always targeting: weak operators with phone problems in small markets.
"""
import sys, requests, json, os, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

GKEY = os.environ.get("GOOGLE_PLACES_KEY", "")

# ─── Spend tracking (shared with lead_engine.py) ───────────────────────────
SPEND_FILE = Path.home() / "Desktop/BOSS_HQ/atlas_data/spend_tracker.json"
TOTAL_CREDIT = 300.00
DAILY_BUDGET = 4.00
WEEKLY_BUDGET = 28.00
HARD_STOP_PERCENT = 0.80
COST_PER_SEARCH = 0.032
NTFY_TOPIC = "https://ntfy.sh/bossai-bostonrossall-alerts"
CREDIT_EXPIRY = datetime(2026, 8, 7, tzinfo=timezone.utc)


def _ntfy(message: str, title: str = "Prospect Scorer", priority: str = "default"):
    """Send notification via ntfy.sh."""
    try:
        data = message.encode("utf-8")
        req = urllib.request.Request(NTFY_TOPIC, data=data, method="POST")
        req.add_header("Title", title)
        req.add_header("Priority", priority)
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def _load_spend():
    """Load spend tracker data from shared JSON file."""
    if not SPEND_FILE.exists():
        return {"total_spent": 0.0, "requests": []}
    try:
        return json.loads(SPEND_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"total_spent": 0.0, "requests": []}


def _save_spend(data):
    """Save spend tracker data back to shared JSON file."""
    SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SPEND_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str) + "\n")
    tmp.replace(SPEND_FILE)


def _spend_since(data, since: datetime) -> float:
    """Calculate spend since a given timestamp."""
    total = 0.0
    for req in data.get("requests", []):
        ts = req.get("timestamp", "")
        try:
            req_time = datetime.fromisoformat(ts)
            if req_time >= since:
                total += req.get("cost", 0.0)
        except (ValueError, TypeError):
            continue
    return total


def _check_budget() -> tuple:
    """Check if we can afford a Google Places API call.
    Returns (can_spend: bool, reason: str).
    Reads the shared spend_tracker.json used by lead_engine.py."""
    data = _load_spend()
    total_spent = data.get("total_spent", 0.0)
    now = datetime.now(timezone.utc)

    # Hard stop at 80% total
    if total_spent >= (TOTAL_CREDIT * HARD_STOP_PERCENT):
        return False, f"HARD STOP: ${total_spent:.2f}/${TOTAL_CREDIT} spent (80% cap reached)"

    # Daily cap
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily_spent = _spend_since(data, start_of_day)
    if daily_spent >= DAILY_BUDGET:
        return False, f"Daily cap hit: ${daily_spent:.2f}/${DAILY_BUDGET} today"

    # Weekly cap
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    weekly_spent = _spend_since(data, start_of_week)
    if weekly_spent >= WEEKLY_BUDGET:
        return False, f"Weekly cap hit: ${weekly_spent:.2f}/${WEEKLY_BUDGET} this week"

    return True, "OK"


def _record_spend(endpoint: str = "text_search", cost: float = COST_PER_SEARCH):
    """Record a Google Places API call in the shared spend tracker."""
    data = _load_spend()
    data["total_spent"] = data.get("total_spent", 0.0) + cost
    data.setdefault("requests", []).append({
        "endpoint": endpoint,
        "cost": cost,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep only last 500 requests
    if len(data["requests"]) > 500:
        data["requests"] = data["requests"][-500:]

    # Check 80% hard stop
    if data["total_spent"] >= (TOTAL_CREDIT * HARD_STOP_PERCENT) and not data.get("hard_stopped"):
        data["hard_stopped"] = True
        _ntfy(
            f"HARD STOP: Google Places spend hit 80% (${data['total_spent']:.2f}/${TOTAL_CREDIT}). "
            f"All API calls halted. Triggered by prospect_scorer.py.",
            title="SPEND ALERT", priority="urgent"
        )

    # Check burnout projection
    now = datetime.now(timezone.utc)
    days_remaining = max((CREDIT_EXPIRY - now).days, 1)
    credit_remaining = TOTAL_CREDIT - data["total_spent"]
    week_ago = now - timedelta(days=7)
    recent_spend = _spend_since(data, week_ago)
    avg_daily = recent_spend / 7.0
    if avg_daily > 0:
        days_until_exhausted = credit_remaining / avg_daily
        if days_until_exhausted < days_remaining and not data.get("burnout_alerted"):
            projected_date = (now + timedelta(days=days_until_exhausted)).strftime("%b %d")
            data["burnout_alerted"] = True
            _ntfy(
                f"Google Places credit projected to run out {projected_date} "
                f"(before Aug 7 expiry). "
                f"Avg daily spend ${avg_daily:.2f}/day, "
                f"${credit_remaining:.2f} remaining. "
                f"Triggered by prospect_scorer.py.",
                title="SPEND BURNOUT WARNING", priority="high"
            )

    _save_spend(data)
BANNED_AC = ['903','430','985','318','504','337','225']

PAIN_KEYWORDS = [
    "no answer", "never answered", "couldn't reach", "couldn't get through",
    "voicemail", "never called back", "didn't return my call", "hard to reach",
    "no response", "never responded", "left a message", "called several times",
    "rang out", "rings and rings", "nobody answered", "no one answered",
    "phone just rings", "straight to voicemail", "impossible to reach",
    "doesn't answer", "doesnt answer", "never returns", "never got a response"
]

RESPONSIVE_KEYWORDS = [
    "answered right away", "picked up immediately", "called me back",
    "quick to respond", "very responsive", "returned my call",
    "answered the phone", "always answers", "easy to reach",
    "great communication", "responded quickly", "prompt response",
    "got right back to me", "called back quickly", "fast response",
    "answered my call", "picks up the phone", "reliable communication"
]

def extract_reviews(reviews):
    parts = []
    for rv in (reviews or []):
        txt = rv.get('text', '')
        if isinstance(txt, dict): parts.append(txt.get('text', ''))
        elif isinstance(txt, str): parts.append(txt)
    return ' '.join(parts).lower()

def extract_negative_reviews(reviews):
    """Only return text from reviews rated 3 stars or below."""
    parts = []
    for rv in (reviews or []):
        rating = rv.get('rating', 5)
        if rating > 3:
            continue
        txt = rv.get('text', '')
        if isinstance(txt, dict): parts.append(txt.get('text', ''))
        elif isinstance(txt, str): parts.append(txt)
    return ' '.join(parts).lower()

def make_opener(pain, has_web, rating, niche, city, responsive=False, review_count=0):
    if not has_web and review_count >= 5:
        return f"I was looking at {niche} businesses in {city} and noticed y'all have great reviews but no website. We build websites for {niche} businesses for $299 — and we already have everything we need from your Google profile to get started."
    elif not has_web:
        return f"I was looking at {niche} businesses in {city} — noticed y'all don't have a website. We build professional websites for {niche} businesses for $299, ready in 72 hours."
    elif responsive:
        return f"I noticed your customers say you're great at picking up the phone — that's rare for {niche} businesses. We help businesses like yours turn that into more jobs with AI-powered follow-up and scheduling."
    elif rating < 3.8:
        return f"I was looking at {niche} businesses in {city}. Noticed you're at {rating} stars — we help businesses improve that by making sure every call gets answered and every customer gets followed up with."
    else:
        return f"We work with {niche} businesses in {city} to make sure they never miss a call — especially during busy season. Wanted to see if that's something y'all deal with."

def score_place(p, niche, city):
    digits = ''.join(c for c in (p.get('nationalPhoneNumber') or '') if c.isdigit())
    phone = digits[-10:] if len(digits) >= 10 else ''
    if len(phone) != 10 or any(phone.startswith(ac) for ac in BANNED_AC):
        return None

    rating = float(p.get('rating') or 5)
    rev_count = int(p.get('userRatingCount') or 0)
    has_web = bool(p.get('websiteUri'))
    neg_text = extract_negative_reviews(p.get('reviews', []))
    all_text = extract_reviews(p.get('reviews', []))
    month = datetime.now().month

    score = 0
    signals = []
    pain = []

    # Pain signals — PENALIZE: these businesses won't answer our call either
    for kw in PAIN_KEYWORDS:
        if kw in neg_text:
            pain.append(kw)
            score -= 8
            signals.append(f"UNREACHABLE_PAIN:'{kw}'")
            if len(pain) >= 2: break

    # Responsive signals — check ALL reviews for reachability proof
    responsive_signals = []
    for kw in RESPONSIVE_KEYWORDS:
        if kw in all_text:
            responsive_signals.append(kw)
            score += 12
            signals.append(f"RESPONSIVE:'{kw}'")
            if len(responsive_signals) >= 2: break

    # Niche tier
    n = niche.lower()
    if any(t in n for t in ['hvac','air condition','heat','plumb','electr','roof']):
        score += 8
        signals.append('TIER1')
    else:
        score += 5
        signals.append('TIER2')

    # Rating — weak is good (3.0-4.3 with some reviews)
    if 3.0 <= rating <= 4.3 and rev_count >= 5:
        score += 10
        signals.append(f'WEAK_RATING({rating}⭐)')
    elif rating > 4.7 and rev_count > 100:
        score -= 8  # established, already have everything

    # Size — small operators are the target
    if 5 <= rev_count <= 60:
        score += 8
        signals.append(f'SMALL_OP({rev_count})')
    elif rev_count < 5:
        score += 4
        signals.append('BRAND_NEW')
    elif rev_count > 150:
        score -= 12
        signals.append('TOO_ESTABLISHED')

    # No website — #1 signal, clear need BOSS can fill
    if not has_web:
        score += 25
        signals.append('NO_WEBSITE')

    # Website-buildable: no website + enough public data to build one
    if not has_web and rev_count >= 5 and bool(p.get('formattedAddress')):
        score += 8
        signals.append('WEBSITE_BUILDABLE')

    # Peak season timing
    if any(t in n for t in ['hvac', 'air']) and month in [5, 6, 7, 8]:
        score += 8
        signals.append('🔥HVAC_PEAK')
    if 'plumb' in n and month in [12, 1, 2]:
        score += 4
        signals.append('PLUMBER_WINTER')

    # ATLAS demand signal boost — reads boss_state.json market_intelligence
    try:
        _bs = Path.home() / "Desktop/BOSS_HQ/atlas_data/boss_state.json"
        if _bs.exists():
            _mi = json.loads(_bs.read_text()).get("market_intelligence", {})
            for ds in _mi.get("demand_signals", []):
                ds_niche = (ds.get("niche") or ds.get("type") or "").lower()
                ds_area = (ds.get("area") or "").lower()
                if ds_niche and ds_niche in n and (not ds_area or ds_area in city.lower()):
                    score += 6
                    signals.append("ATLAS_DEMAND")
                    break
    except Exception:
        pass

    tier = ('SUPERNICHE' if score >= 55 else
            'HOT' if score >= 40 else
            'WARM' if score >= 28 else None)
    if not tier:
        return None

    ANNUAL_LOSS = {
        'hvac': 367200, 'air condition': 367200, 'heat': 367200,
        'plumb': 128520, 'electr': 114750, 'roof': 1224000,
        'auto': 91800, 'law': 550800, 'clean': 50000, 'junk': 60000
    }
    est_loss = 126000
    for k, v in ANNUAL_LOSS.items():
        if k in n:
            est_loss = v
            break

    # Best method — lead with phone (website pitch) instead of walk-ins
    if not has_web:
        best_method = "phone (website pitch)"
    elif any('RESPONSIVE' in s for s in signals):
        best_method = "phone"
    else:
        best_method = "phone"

    is_field_trade = any(t in n for t in ['hvac', 'plumb', 'electr', 'roof', 'junk', 'lawn', 'pest', 'pool'])
    if is_field_trade:
        best_time = "4:30-5:30 PM CT (driving home, 71% more effective than AM). Alt: 11:30-12:30 lunch, 6:15-6:45 AM morning drive"
    elif any(t in n for t in ['law', 'legal', 'attorney']):
        best_time = "8-9 AM CT (before court/clients). Alt: 12-1 PM lunch"
    elif any(t in n for t in ['auto', 'mechanic', 'body']):
        best_time = "7:30-8 AM CT (before bays fill). Alt: 5-6 PM after close"
    elif any(t in n for t in ['dental', 'doctor', 'chiro']):
        best_time = "12-1 PM CT (lunch break). Alt: after 5 PM"
    else:
        best_time = "4-5 PM CT"

    return {
        'name': p.get('displayName', {}).get('text', 'Unknown'),
        'phone': phone,
        'phone_e164': '+1' + phone,
        'rating': rating, 'reviews': rev_count, 'has_web': has_web,
        'score': score, 'tier': tier,
        'signals': signals, 'pain': pain,
        'opener': make_opener(pain, has_web, rating, niche, city, responsive=bool(responsive_signals), review_count=rev_count),
        'address': p.get('formattedAddress', ''),
        'niche': niche, 'city': city,
        'est_annual_loss': est_loss,
        'best_contact_time': best_time,
        'best_contact_method': best_method,
        'website_buildable': not has_web and rev_count >= 5 and bool(p.get('formattedAddress')),
        'responsive': bool(responsive_signals),
        'google_data': {
            'name': p.get('displayName', {}).get('text', ''),
            'address': p.get('formattedAddress', ''),
            'rating': rating,
            'review_count': rev_count,
            'reviews': [{'text': rv.get('text', {}).get('text', '') if isinstance(rv.get('text'), dict) else rv.get('text', ''), 'rating': rv.get('rating', 5)} for rv in (p.get('reviews', []))[:5]],
            'phone': phone,
            'niche': niche,
            'city': city,
            'primary_type': p.get('primaryType', ''),
            'opening_hours': p.get('currentOpeningHours', {}),
            'photos': len(p.get('photos', []))
        }
    }

def hunt(niche, city, verbose=True):
    # Check budget before making API call
    can_spend, reason = _check_budget()
    if not can_spend:
        print(f"  BLOCKED: {reason}")
        return []

    h = {
        "X-Goog-Api-Key": GKEY,
        "X-Goog-FieldMask": "places.displayName,places.nationalPhoneNumber,places.rating,places.userRatingCount,places.websiteUri,places.reviews,places.formattedAddress,places.currentOpeningHours,places.primaryType,places.photos",
        "Content-Type": "application/json"
    }
    r = requests.post("https://places.googleapis.com/v1/places:searchText",
        headers=h, json={"textQuery": f"{niche} {city}", "maxResultCount": 20}, timeout=10)

    if r.status_code != 200:
        print(f"API error: {r.status_code}")
        return []

    # Record the spend in shared tracker
    _record_spend("text_search", COST_PER_SEARCH)

    places = r.json().get('places', [])
    scored = [score_place(p, niche, city) for p in places]
    scored = sorted([s for s in scored if s], key=lambda x: x['score'], reverse=True)

    if verbose:
        s = [t for t in scored if t['tier']=='SUPERNICHE']
        h_ = [t for t in scored if t['tier']=='HOT']
        w = [t for t in scored if t['tier']=='WARM']
        print(f"\n{'═'*66}")
        print(f"  🎯 {niche.upper()} — {city.upper()}")
        print(f"  {len(s)} SUPERNICHE | {len(h_)} HOT | {len(w)} WARM | {len(places)-len(scored)} skipped")
        print(f"{'═'*66}")

        for i, t in enumerate(scored[:8]):
            icon = '🔥' if t['tier']=='SUPERNICHE' else '✅' if t['tier']=='HOT' else '🟡'
            print(f"\n  {icon} #{i+1} [{t['tier']}] Score:{t['score']}/100")
            print(f"     {t['name']}")
            print(f"     📞 {t['phone']}  ⭐{t['rating']} ({t['reviews']}rev)  {'🌐' if t['has_web'] else '❌ no site'}")
            print(f"     💰 Est. annual loss to missed calls: ${t.get('est_annual_loss', 126000):,}")
            print(f"     🕐 Best: {t.get('best_contact_method', 'phone')} @ {t.get('best_contact_time', '4-5 PM')}")
            if t['pain']: print(f"     ⚠️  PAIN: '{t['pain'][0]}'")
            print(f"     Tags: {' | '.join(t['signals'][:4])}")
            print(f"     Opener: \"{t['opener'][:85]}...\"")

        if scored:
            best = scored[0]
            print(f"\n{'─'*66}")
            print(f"  🎯 CALL FIRST: {best['name']} — {best['phone']}")
            print(f"     Full opener:")
            print(f"     \"{best['opener']}\"")
        print(f"\n{'═'*66}\n")

    return scored

# Multi-market scan for maximum coverage
BEST_MARKETS = [
    ("HVAC contractor", "Corinth MS"),
    ("HVAC contractor", "Durant OK"),
    ("HVAC contractor", "Hobbs NM"),
    ("electrician", "Corinth MS"),
    ("HVAC contractor", "Ada OK"),
    ("plumber", "Corinth MS"),
    ("HVAC contractor", "Batesville AR"),
    ("roofing contractor", "Meridian MS"),
]

def full_sweep(verbose=True):
    """Scan all best markets, return top targets across everything."""
    all_results = []
    for niche, city in BEST_MARKETS:
        results = hunt(niche, city, verbose=False)
        all_results.extend(results)

    all_results.sort(key=lambda x: x['score'], reverse=True)

    if verbose:
        s = [t for t in all_results if t['tier']=='SUPERNICHE']
        h = [t for t in all_results if t['tier']=='HOT']
        w = [t for t in all_results if t['tier']=='WARM']
        print(f"\n{'═'*66}")
        print(f"  🎯 FULL SWEEP — {datetime.now().strftime('%I:%M %p CT')}")
        print(f"  {len(BEST_MARKETS)} markets | {len(all_results)} scoreable | {len(s)} SUPERNICHE | {len(h)} HOT")
        print(f"{'═'*66}\n")
        for i, t in enumerate(all_results[:10]):
            icon = '🔥' if t['tier']=='SUPERNICHE' else '✅' if t['tier']=='HOT' else '🟡'
            print(f"  {icon} #{i+1} Score:{t['score']} — {t['name']} ({t['city']})")
            print(f"     📞 {t['phone']}  ⭐{t['rating']} ({t['reviews']}rev)  {'🌐' if t['has_web'] else 'NO SITE'}")
            if t['pain']: print(f"     ⚠️  {t['pain'][0]}")
            print(f"     Opener: \"{t['opener'][:80]}...\"")
            print()
        print(f"{'═'*66}\n")

    return all_results

def score_website_ready(place, niche, city):
    """Score a business for website-building readiness.
    Returns (score, tier, signals) or None if not scoreable.
    903/430 are INCLUDED (in-person website sales territory)."""
    WEBSITE_BANNED_AC = ['985', '318', '504', '337', '225']
    digits = ''.join(c for c in (place.get('nationalPhoneNumber') or '') if c.isdigit())
    phone = digits[-10:] if len(digits) >= 10 else ''
    if len(phone) != 10 or any(phone.startswith(ac) for ac in WEBSITE_BANNED_AC):
        return None

    rating = float(place.get('rating') or 0)
    rev_count = int(place.get('userRatingCount') or 0)
    has_web = not bool(place.get('websiteUri'))
    reviews = place.get('reviews', [])

    score = 0
    signals = []

    # NO_WEBSITE_CONFIRMED +15
    if has_web:
        score += 15
        signals.append('NO_WEBSITE(+15)')

    # REVIEW_COUNT 5-49 +8
    if 5 <= rev_count <= 49:
        score += 8
        signals.append(f'REVIEWS_5-49({rev_count})(+8)')

    # STAR_RATING 4.0+ +10
    if rating >= 4.0:
        score += 10
        signals.append(f'RATING_4+({rating})(+10)')

    # TIER1_NICHE +8
    n = niche.lower()
    if any(t in n for t in ['hvac', 'air condition', 'heat', 'plumb', 'electr', 'roof', 'law', 'legal', 'attorney']):
        score += 8
        signals.append('TIER1_NICHE(+8)')

    # IN_PERSON_TERRITORY 903/430 +5
    if phone[:3] in ('903', '430'):
        score += 5
        signals.append('IN_PERSON_903/430(+5)')

    # TOO_NEW <6mo listing -10 (proxy: <3 reviews)
    if rev_count < 3:
        score -= 10
        signals.append('TOO_NEW(<3rev)(-10)')

    # ALREADY_HAS_MARKETING -8 (proxy: has website already)
    if not has_web:
        score -= 8
        signals.append('HAS_WEBSITE(-8)')

    # Extract review snippets for website use
    snippets = []
    for rv in (reviews or [])[:5]:
        r = rv.get('rating', 0)
        txt = rv.get('text', '')
        if isinstance(txt, dict):
            txt = txt.get('text', '')
        if r >= 4 and len(txt) > 30:
            snippets.append(txt[:200])
        if len(snippets) >= 3:
            break

    tier = 'WEBSITE_READY' if score >= 45 else None

    return {
        'name': place.get('displayName', {}).get('text', 'Unknown'),
        'phone': phone,
        'rating': rating,
        'reviews': rev_count,
        'has_website': not has_web,
        'website_ready_score': score,
        'website_ready_tier': tier,
        'signals': signals,
        'address': place.get('formattedAddress', ''),
        'niche': niche,
        'city': city,
        'review_snippets': snippets,
        'services': [],
    }


def website_ready_scan(verbose=True):
    """Scan markets for WEBSITE_READY leads. Cap 30 rows."""
    MARKETS = [
        ("HVAC contractor", "Tyler TX"),
        ("plumber", "Tyler TX"),
        ("electrician", "Longview TX"),
        ("HVAC contractor", "Nacogdoches TX"),
        ("roofing contractor", "Tyler TX"),
        ("HVAC contractor", "Lufkin TX"),
        ("HVAC contractor", "Corinth MS"),
        ("plumber", "Corinth MS"),
    ]

    all_results = []
    h = {
        "X-Goog-Api-Key": GKEY,
        "X-Goog-FieldMask": "places.displayName,places.nationalPhoneNumber,places.rating,places.userRatingCount,places.websiteUri,places.reviews,places.formattedAddress",
        "Content-Type": "application/json"
    }

    for niche, city in MARKETS:
        if len(all_results) >= 30:
            break
        # Check budget before each API call
        can_spend, reason = _check_budget()
        if not can_spend:
            print(f"  BLOCKED: {reason}")
            break
        try:
            r = requests.post("https://places.googleapis.com/v1/places:searchText",
                headers=h, json={"textQuery": f"{niche} {city}", "maxResultCount": 20}, timeout=10)
            if r.status_code != 200:
                continue
            # Record the spend in shared tracker
            _record_spend("text_search", COST_PER_SEARCH)
            places = r.json().get('places', [])
            for p in places:
                scored = score_website_ready(p, niche, city)
                if scored and scored['website_ready_tier'] == 'WEBSITE_READY':
                    # Dedup by phone
                    if not any(x['phone'] == scored['phone'] for x in all_results):
                        all_results.append(scored)
                        if len(all_results) >= 30:
                            break
        except Exception as e:
            print(f"  Error scanning {niche} {city}: {e}")

    all_results.sort(key=lambda x: x['website_ready_score'], reverse=True)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  WEBSITE-READY SCAN — {len(all_results)} leads found")
        print(f"{'='*60}")
        for i, r in enumerate(all_results):
            print(f"\n  #{i+1} Score:{r['website_ready_score']} — {r['name']} ({r['city']})")
            print(f"     Phone: {r['phone']}  Rating: {r['rating']} ({r['reviews']}rev)")
            print(f"     Has website: {r['has_website']}")
            print(f"     Signals: {' | '.join(r['signals'])}")
            if r['review_snippets']:
                print(f"     Snippets: {len(r['review_snippets'])} positive reviews captured")
        print(f"\n{'='*60}\n")

    return all_results


def write_targets_json(results):
    """Write scored targets to prospect_targets.json for lead_engine ingestion."""
    from pathlib import Path
    outpath = Path.home() / "Desktop/BOSS_HQ/atlas_data/prospect_targets.json"
    existing = {}
    if outpath.exists():
        try:
            existing = json.loads(outpath.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing.setdefault("targets", [])
    existing.setdefault("ingested_ids", [])
    existing_phones = {t.get("phone") for t in existing["targets"]}

    added = 0
    for r in results:
        if r["phone"] not in existing_phones:
            existing["targets"].append({
                "id": r["phone"],
                "name": r["name"],
                "phone": r["phone"],
                "phone_e164": r["phone_e164"],
                "rating": r["rating"],
                "reviews": r["reviews"],
                "has_web": r["has_web"],
                "score": r["score"],
                "tier": r["tier"],
                "signals": r["signals"],
                "pain": r["pain"],
                "opener": r["opener"],
                "niche": r["niche"],
                "city": r["city"],
                "address": r.get("address", ""),
            })
            existing_phones.add(r["phone"])
            added += 1

    if existing["targets"]:
        existing["targets"].sort(key=lambda x: x["score"], reverse=True)
        existing["targets"] = existing["targets"][:200]

    existing["last_updated"] = datetime.now().isoformat()
    outpath.write_text(json.dumps(existing, indent=2) + "\n")
    print(f"\n  Wrote {added} new targets to {outpath.name} ({len(existing['targets'])} total)")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        full_sweep()
    elif len(sys.argv) == 2 and sys.argv[1] == '--sweep':
        full_sweep()
    elif len(sys.argv) == 2 and sys.argv[1] == '--output-json':
        results = full_sweep(verbose=True)
        write_targets_json(results)
    elif len(sys.argv) == 2 and sys.argv[1] == '--website-ready':
        results = website_ready_scan(verbose=True)
        print(f"WEBSITE_READY count: {len(results)}")
    elif len(sys.argv) >= 3:
        if '--output-json' in sys.argv:
            args = [a for a in sys.argv[1:] if a != '--output-json']
            if len(args) >= 2:
                results = hunt(args[0], args[1])
                write_targets_json(results)
        else:
            hunt(sys.argv[1], sys.argv[2])
    else:
        print("Usage:")
        print("  python3 prospect_scorer.py                        # Full sweep all markets")
        print("  python3 prospect_scorer.py 'HVAC' 'Corinth MS'    # Single market")
        print("  python3 prospect_scorer.py --output-json           # Sweep + write to prospect_targets.json")
        print("  python3 prospect_scorer.py --website-ready         # Scan for WEBSITE_READY leads")
