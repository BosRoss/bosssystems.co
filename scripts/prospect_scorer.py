#!/usr/bin/env python3
"""
BOSS Superniche Prospect Scorer
Usage: python3 prospect_scorer.py "HVAC" "Corinth MS"
Finds the most targetable businesses in any market and generates personalized openers.
Always targeting: weak operators with phone problems in small markets.
"""
import sys, requests, json, os
from datetime import datetime

GKEY = os.environ.get("GOOGLE_PLACES_KEY", "")
BANNED_AC = ['903','430','985','318','504','337','225']

PAIN_KEYWORDS = [
    "no answer", "never answered", "couldn't reach", "couldn't get through",
    "voicemail", "never called back", "didn't return my call", "hard to reach",
    "no response", "never responded", "left a message", "called several times",
    "rang out", "rings and rings", "nobody answered", "no one answered",
    "phone just rings", "straight to voicemail", "impossible to reach",
    "doesn't answer", "doesnt answer", "never returns", "never got a response"
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

def make_opener(pain, has_web, rating, niche, city):
    if pain:
        kw = pain[0]
        if any(w in kw for w in ['answer', 'reach', 'through', 'response', 'responds', 'return']):
            return f"I noticed a customer left a review saying they had trouble reaching y'all by phone. That's jobs walking out the door — that's exactly what we fix for {niche} businesses."
        elif 'voicemail' in kw:
            return f"I saw a review mentioning getting sent to voicemail. Wanted to reach out — every one of those could be a job going to a competitor."
        elif 'message' in kw or 'called several' in kw:
            return f"I noticed a review where someone mentioned leaving messages without hearing back. That usually means jobs are slipping through — and that's exactly what we help fix."
        else:
            return f"I noticed a review mentioning trouble getting through on the phone. Wanted to reach out because that's the exact problem we fix for {niche} businesses."
    elif not has_web:
        return f"I was looking at {niche} businesses in {city} — noticed y'all don't have a website listed, which means your phone is doing all the work. That's actually our specialty."
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
    month = datetime.now().month

    score = 0
    signals = []
    pain = []

    # Pain signals — only from verified negative reviews (<=3 stars)
    for kw in PAIN_KEYWORDS:
        if kw in neg_text:
            pain.append(kw)
            score += 14
            signals.append(f"PAIN:'{kw}'")
            if len(pain) >= 2: break

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
        score -= 5  # established, harder sell

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

    # No website — unsophisticated, open to simple solutions
    if not has_web:
        score += 8
        signals.append('NO_WEBSITE')

    # Peak season timing
    if any(t in n for t in ['hvac', 'air']) and month in [5, 6, 7, 8]:
        score += 8
        signals.append('🔥HVAC_PEAK')
    if 'plumb' in n and month in [12, 1, 2]:
        score += 4
        signals.append('PLUMBER_WINTER')

    tier = ('SUPERNICHE' if score >= 55 else
            'HOT' if score >= 40 else
            'WARM' if score >= 28 else None)
    if not tier:
        return None

    return {
        'name': p.get('displayName', {}).get('text', 'Unknown'),
        'phone': phone,
        'phone_e164': '+1' + phone,
        'rating': rating, 'reviews': rev_count, 'has_web': has_web,
        'score': score, 'tier': tier,
        'signals': signals, 'pain': pain,
        'opener': make_opener(pain, has_web, rating, niche, city),
        'address': p.get('formattedAddress', ''),
        'niche': niche, 'city': city
    }

def hunt(niche, city, verbose=True):
    h = {
        "X-Goog-Api-Key": GKEY,
        "X-Goog-FieldMask": "places.displayName,places.nationalPhoneNumber,places.rating,places.userRatingCount,places.websiteUri,places.reviews,places.formattedAddress",
        "Content-Type": "application/json"
    }
    r = requests.post("https://places.googleapis.com/v1/places:searchText",
        headers=h, json={"textQuery": f"{niche} {city}", "maxResultCount": 20}, timeout=10)

    if r.status_code != 200:
        print(f"API error: {r.status_code}")
        return []

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
