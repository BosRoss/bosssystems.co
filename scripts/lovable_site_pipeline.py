#!/usr/bin/env python3
"""
Lovable Site Pipeline — Builds websites for WEBSITE_READY leads via Lovable MCP.
Usage:
  python3 lovable_site_pipeline.py --dry-run     # Print prompts, no API calls
  python3 lovable_site_pipeline.py --build 3     # Build top N sites (default 3)
  python3 lovable_site_pipeline.py --status       # Show build log
"""
import sys, json, os, argparse, re, subprocess
from pathlib import Path
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    CT = ZoneInfo("America/Chicago")
except ImportError:
    from datetime import timezone, timedelta
    CT = timezone(timedelta(hours=-5))

BOSS_HQ = Path.home() / "Desktop" / "BOSS_HQ"
BUILDS_LOG = BOSS_HQ / "atlas_data" / "lovable_builds.json"
CLIENTS_DIR = BOSS_HQ / "clients"

NICHE_COLORS = {
    "hvac": "#1E5FBF",
    "air condition": "#1E5FBF",
    "heat": "#1E5FBF",
    "plumb": "#0E7C8A",
    "electr": "#D9A400",
    "roof": "#3D4B5C",
    "law": "#1A2B4C",
    "legal": "#1A2B4C",
    "attorney": "#1A2B4C",
}


def get_niche_color(niche):
    n = niche.lower()
    for key, color in NICHE_COLORS.items():
        if key in n:
            return color
    return "#1E5FBF"


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def build_lovable_prompt(lead):
    """Construct the initial_message for Lovable create_project."""
    color = get_niche_color(lead.get('niche', ''))
    name = lead['name']
    phone = lead['phone']
    formatted_phone = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
    rating = lead.get('rating', 0)
    reviews = lead.get('reviews', 0)
    city = lead.get('city', '')
    niche = lead.get('niche', '')
    snippets = lead.get('review_snippets', [])
    address = lead.get('address', '')

    niche_display = niche.replace('contractor', '').strip().title()
    if 'hvac' in niche.lower() or 'air condition' in niche.lower() or 'heat' in niche.lower():
        niche_display = "HVAC"
        services = ["Air Conditioning Repair", "Heating Installation", "AC Maintenance", "Ductwork", "Emergency HVAC Service"]
    elif 'plumb' in niche.lower():
        niche_display = "Plumbing"
        services = ["Drain Cleaning", "Water Heater Repair", "Leak Detection", "Pipe Repair", "Emergency Plumbing"]
    elif 'electr' in niche.lower():
        niche_display = "Electrical"
        services = ["Electrical Repair", "Panel Upgrades", "Wiring", "Lighting Installation", "Emergency Electrical"]
    elif 'roof' in niche.lower():
        niche_display = "Roofing"
        services = ["Roof Repair", "Roof Replacement", "Storm Damage", "Inspections", "Gutter Installation"]
    elif 'law' in niche.lower() or 'legal' in niche.lower() or 'attorney' in niche.lower():
        niche_display = "Legal Services"
        services = ["Consultations", "Case Review", "Legal Representation", "Document Preparation"]
    else:
        services = ["Service 1", "Service 2", "Service 3"]

    services_section = "\n".join(f"  - {s}" for s in services)

    # Build testimonials or CTA section
    if snippets:
        testimonials_section = "Include a testimonials section with these REAL customer reviews (do NOT fabricate any):\n"
        for i, snip in enumerate(snippets[:3]):
            clean = snip.replace('"', "'")
            testimonials_section += f'  {i+1}. "{clean}"\n'
    else:
        testimonials_section = "Instead of testimonials (none available), add a 'First-Time Customer Offer' CTA section with a bold heading and a call-to-action button linking to the phone number."

    # Service area
    city_name = city.split(',')[0].strip() if ',' in city else city.replace(' TX', '').replace(' MS', '').replace(' AR', '').replace(' OK', '').replace(' NM', '').replace(' AL', '').replace(' TN', '').strip()
    state = city.split()[-1] if city else ''

    prompt = f"""Build a single-page, mobile-first website for a local {niche_display} business using shadcn/ui and Tailwind CSS.

BUSINESS DETAILS:
- Name: {name}
- Phone: {formatted_phone}
- Location: {address or city}
- Niche: {niche_display}
- Rating: {rating} stars ({reviews} reviews on Google)

DESIGN:
- Primary color: {color}
- Premium, trustworthy tone — this is a real local business
- Dark background (#0a0a0a) with the primary color as accent
- Clean, modern, professional
- Mobile-first responsive design

SECTIONS (in order):
1. HERO: Full-width hero with business name, tagline like "Trusted {niche_display} in {city_name}", and a prominent click-to-call CTA button linking to tel:+1{phone}. The CTA should say "Call Now" or "Get a Free Quote".

2. SERVICES: Grid of services offered:
{services_section}

3. TRUST BAR: A horizontal bar showing:
  - {rating} Star Rating
  - {reviews}+ Reviews
  - "Serving {city_name} & Surrounding Areas"

4. TESTIMONIALS / OFFER:
{testimonials_section}

5. SERVICE AREA: List of areas served including {city_name} and surrounding cities in {state}.

6. CONTACT FORM: Simple form with Name, Phone, Message fields. On submit, show a confirmation message ("We'll call you back within 1 hour!"). No backend needed — just the UI with a confirm state.

7. FOOTER: Business name, phone, location. Include a subtle "Built by BOSS Systems" text that links to https://bosssystems.co

RULES:
- Zero placeholder data — every piece of text must be real or contextually accurate
- No stock photos — use solid color backgrounds and icons instead
- All phone links must use tel:+1{phone}
- Must look like a real $2,000+ website
- Fully responsive — must look great on mobile
"""
    return prompt.strip()


def load_builds():
    if BUILDS_LOG.exists():
        try:
            return json.loads(BUILDS_LOG.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"builds": [], "total_credits_spent": 0}


def save_builds(data):
    BUILDS_LOG.parent.mkdir(parents=True, exist_ok=True)
    BUILDS_LOG.write_text(json.dumps(data, indent=2) + "\n")


def save_client_url(lead, url, project_id):
    slug = slugify(lead['name'])
    client_dir = CLIENTS_DIR / slug
    client_dir.mkdir(parents=True, exist_ok=True)
    (client_dir / "website_url.txt").write_text(f"{url}\n")
    (client_dir / "website_meta.json").write_text(json.dumps({
        "business_name": lead['name'],
        "phone": lead['phone'],
        "niche": lead['niche'],
        "city": lead['city'],
        "url": url,
        "project_id": project_id,
        "built": datetime.now(CT).isoformat(),
    }, indent=2) + "\n")


def send_ntfy(message):
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://ntfy.sh/bossai-bostonrossall-alerts",
            data=message.encode(),
            headers={"Title": "Lovable Site Pipeline", "Priority": "default", "Tags": "hammer"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass


def dry_run(leads):
    """Print prompts without making any API calls."""
    print(f"\n{'='*60}")
    print(f"  DRY RUN — {len(leads)} WEBSITE_READY leads")
    print(f"{'='*60}")

    for i, lead in enumerate(leads):
        prompt = build_lovable_prompt(lead)
        print(f"\n{'─'*60}")
        print(f"  LEAD #{i+1}: {lead['name']} ({lead['city']})")
        print(f"  Phone: {lead['phone']} | Rating: {lead['rating']} | Reviews: {lead['reviews']}")
        print(f"  Niche: {lead['niche']} | Color: {get_niche_color(lead['niche'])}")
        print(f"  Snippets: {len(lead.get('review_snippets', []))}")
        print(f"{'─'*60}")
        print(f"\n  === LOVABLE PROMPT ===\n")
        print(prompt)
        print(f"\n  === END PROMPT ===\n")

    print(f"{'='*60}")
    print(f"  {len(leads)} prompts generated. Run without --dry-run to build.")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Lovable Site Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts only, no API calls")
    parser.add_argument("--build", type=int, default=3, help="Number of sites to build (default 3)")
    parser.add_argument("--status", action="store_true", help="Show build log")
    args = parser.parse_args()

    if args.status:
        data = load_builds()
        print(f"\nBuilds: {len(data['builds'])}")
        print(f"Total credits spent: {data['total_credits_spent']}")
        for b in data['builds'][-10:]:
            print(f"  {b['business_name']:30s} | {b.get('url','pending'):50s} | {b['timestamp'][:16]}")
        return

    # Get WEBSITE_READY leads from prospect_scorer
    sys.path.insert(0, str(BOSS_HQ / "scripts"))
    from prospect_scorer import website_ready_scan
    leads = website_ready_scan(verbose=False)

    if not leads:
        print("No WEBSITE_READY leads found.")
        return

    leads = leads[:args.build]

    if args.dry_run:
        dry_run(leads)
        return

    # Live build requires Lovable MCP — check connection
    print("Live build requires Lovable MCP authentication.")
    print("Run: claude mcp add --transport http lovable 'https://mcp.lovable.dev'")
    print("Then authenticate in browser.")
    print("After auth, the pipeline will use create_project, poll get_message, and deploy_project.")
    print("\nFor now, use --dry-run to preview prompts.")

    # Update boss_state.json with build pipeline status
    _update_boss_state_builds(leads, built=False)


def _update_boss_state_builds(leads, built=False):
    """Write lovable_sites section to boss_state.json."""
    bs_path = BOSS_HQ / "atlas_data" / "boss_state.json"
    try:
        bs = json.loads(bs_path.read_text()) if bs_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        bs = {}
    builds_data = load_builds()
    bs["lovable_sites"] = {
        "last_updated": datetime.now(CT).isoformat(),
        "total_built": len(builds_data.get("builds", [])),
        "credits_spent": builds_data.get("total_credits_spent", 0),
        "website_ready_queue": len(leads),
        "mcp_connected": False,
    }
    bs["last_updated"] = datetime.now(CT).isoformat()
    bs_path.write_text(json.dumps(bs, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
