#!/usr/bin/env python3
"""
Square Payments — Create payment links, manage subscriptions, check status.

Usage:
  python3 square_payments.py link receptionist "Dale's HVAC"
  python3 square_payments.py link build_standard "Mike's Plumbing"
  python3 square_payments.py link custom 500 "Consulting Fee"
  python3 square_payments.py status
  python3 square_payments.py clients
  python3 square_payments.py history
  python3 square_payments.py test    ← verify API credentials work

Requires SQUARE_ACCESS_TOKEN in config.sh or environment.
"""

import sys, os, json, requests
from datetime import datetime, timedelta

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
BOSS_HQ = os.path.dirname(SCRIPTS)
DATA_DIR = os.path.join(BOSS_HQ, "atlas_data")

_config_sh = os.path.join(SCRIPTS, "config.sh")
if os.path.exists(_config_sh):
    with open(_config_sh) as f:
        for line in f:
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                line = line[7:]
                key, _, val = line.partition("=")
                val = val.strip('"').strip("'")
                if key and val and key not in os.environ:
                    os.environ[key] = val

SQUARE_TOKEN = os.environ.get("SQUARE_ACCESS_TOKEN", "")
SQUARE_BASE = "https://connect.squareup.com/v2"
NTFY = "bossai-bostonrossall-alerts"
NTFY_URL = f"https://ntfy.sh/{NTFY}"
PAY_LOG = os.path.join(DATA_DIR, "payment_links.json")

PRODUCTS = {
    "receptionist": {
        "name": "Automated Receptionist",
        "setup": 250,
        "monthly": 50,
        "desc": "Answers every call 24/7. Quotes jobs, books appointments, takes messages.",
    },
    "build_standard": {
        "name": "BOSS Build Standard",
        "setup": 1497,
        "monthly": 97,
        "desc": "Phone system + CRM basics. Custom-built for your business.",
    },
    "build_premium": {
        "name": "BOSS Build Premium",
        "setup": 2997,
        "monthly": 197,
        "desc": "Phone + follow-ups + reviews. The full automated front office.",
    },
    "website": {
        "name": "Professional Website",
        "setup": 299,
        "monthly": 39,
        "desc": "Custom-built business website. Mobile-friendly, SEO-ready, contact forms, click-to-call.",
    },
    "full": {
        "name": "Full Transformation",
        "setup": 5997,
        "monthly": 497,
        "desc": "Complete automated system. Phone, follow-ups, reviews, scheduling, lead capture.",
    },
}

SUBSCRIPTION_LOG = os.path.join(DATA_DIR, "subscriptions.json")
CATALOG_CACHE = os.path.join(DATA_DIR, "square_catalog_plans.json")


def _headers():
    if not SQUARE_TOKEN:
        print("ERROR: SQUARE_ACCESS_TOKEN not set.")
        print("Run the Square setup first — see SQUARE_SETUP.md")
        sys.exit(1)
    return {
        "Square-Version": "2024-01-18",
        "Authorization": f"Bearer {SQUARE_TOKEN}",
        "Content-Type": "application/json",
    }


def _load_log():
    if os.path.exists(PAY_LOG):
        with open(PAY_LOG) as f:
            return json.load(f)
    return []


def _save_log(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PAY_LOG, "w") as f:
        json.dump(data, f, indent=2)


def _ntfy(title, body):
    try:
        requests.post(NTFY_URL,
            headers={"Title": title, "Priority": "default", "Content-Type": "text/plain"},
            data=body.encode(), timeout=5)
    except requests.RequestException:
        pass


def cmd_test(args):
    """Verify Square credentials work."""
    print("Testing Square API connection...")
    try:
        r = requests.get(f"{SQUARE_BASE}/locations", headers=_headers(), timeout=8)
        if r.status_code == 200:
            locations = r.json().get("locations", [])
            print(f"Connected. {len(locations)} location(s) found:")
            for loc in locations:
                print(f"  {loc.get('name', 'Unnamed')} — {loc.get('id')}")
                print(f"    Status: {loc.get('status', 'unknown')}")
                print(f"    Country: {loc.get('country', '?')}")
            return True
        else:
            print(f"FAILED: {r.status_code}")
            print(r.text[:300])
            return False
    except requests.RequestException as e:
        print(f"Connection error: {e}")
        return False


def cmd_link(args):
    """Create a Square payment link for a product or custom amount."""
    if len(args) < 1:
        print("Usage:")
        print("  square_payments.py link receptionist 'Client Name'")
        print("  square_payments.py link build_standard 'Client Name'")
        print("  square_payments.py link build_premium 'Client Name'")
        print("  square_payments.py link full 'Client Name'")
        print("  square_payments.py link custom 500 'Description'")
        return

    product_key = args[0]

    if product_key == "custom":
        if len(args) < 2:
            print("Usage: square_payments.py link custom <amount> 'Description'")
            return
        amount = int(args[1])
        desc = " ".join(args[2:]) if len(args) > 2 else "BOSS Systems Service"
        name = desc
    elif product_key in PRODUCTS:
        p = PRODUCTS[product_key]
        amount = p["setup"]
        name = p["name"]
        desc = p["desc"]
        client_name = " ".join(args[1:]) if len(args) > 1 else ""
        if client_name:
            desc = f"{p['name']} for {client_name} — {p['desc']}"
    else:
        print(f"Unknown product: {product_key}")
        print(f"Available: {', '.join(PRODUCTS.keys())}, custom")
        return

    import uuid
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "quick_pay": {
            "name": name,
            "price_money": {
                "amount": amount * 100,
                "currency": "USD",
            },
            "location_id": _get_location_id(),
        },
        "checkout_options": {
            "allow_tipping": False,
            "redirect_url": "https://bosssystems.co",
            "ask_for_shipping_address": False,
        },
    }

    print(f"Creating payment link: {name} — ${amount}...")

    try:
        r = requests.post(
            f"{SQUARE_BASE}/online-checkout/payment-links",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        if r.status_code in (200, 201):
            data = r.json()
            link = data.get("payment_link", {})
            url = link.get("long_url") or link.get("url", "")
            link_id = link.get("id", "")
            order_id = link.get("order_id", "")

            print(f"\nPayment link created:")
            print(f"  URL: {url}")
            print(f"  Amount: ${amount}")
            print(f"  Link ID: {link_id}")

            log = _load_log()
            log.append({
                "id": link_id,
                "product": product_key,
                "name": name,
                "client": client_name if product_key != "custom" else desc,
                "amount": amount,
                "url": url,
                "order_id": order_id,
                "created": datetime.now().isoformat(),
                "status": "active",
            })
            _save_log(log)

            pay_page_url = f"https://bosssystems.co/pay.html?product={product_key}&square={requests.utils.quote(url)}"
            print(f"\n  BOSS pay page: {pay_page_url}")
            print(f"\n  Send this to the client.")

            _ntfy(
                f"Payment link created: ${amount}",
                f"{name}\nClient: {client_name or 'N/A'}\nLink: {url}"
            )
            return url
        else:
            print(f"FAILED: {r.status_code}")
            err = r.json().get("errors", [])
            for e in err:
                print(f"  {e.get('category')}: {e.get('detail', e.get('code'))}")
            return None
    except requests.RequestException as e:
        print(f"Connection error: {e}")
        return None


def _get_location_id():
    """Get the first active location ID."""
    cache_file = os.path.join(DATA_DIR, "square_location.txt")
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            loc_id = f.read().strip()
            if loc_id:
                return loc_id

    try:
        r = requests.get(f"{SQUARE_BASE}/locations", headers=_headers(), timeout=8)
        if r.status_code == 200:
            locations = r.json().get("locations", [])
            for loc in locations:
                if loc.get("status") == "ACTIVE":
                    loc_id = loc["id"]
                    os.makedirs(DATA_DIR, exist_ok=True)
                    with open(cache_file, "w") as f:
                        f.write(loc_id)
                    return loc_id
    except requests.RequestException:
        pass

    print("ERROR: Could not find an active Square location.")
    print("Make sure the Square account is set up — see SQUARE_SETUP.md")
    sys.exit(1)


def cmd_status(args):
    """Show recent payment links and their status."""
    log = _load_log()
    if not log:
        print("No payment links created yet.")
        return

    print(f"\n{'='*60}")
    print(f"  PAYMENT LINKS — {len(log)} total")
    print(f"{'='*60}\n")

    for entry in log[-10:]:
        age = ""
        try:
            created = datetime.fromisoformat(entry["created"])
            days = (datetime.now() - created).days
            age = f"{days}d ago" if days > 0 else "today"
        except (ValueError, KeyError):
            pass

        print(f"  {entry.get('name', '?')}")
        print(f"    Amount: ${entry.get('amount', 0)}  |  {age}  |  {entry.get('status', '?')}")
        print(f"    Client: {entry.get('client', 'N/A')}")
        print(f"    URL: {entry.get('url', 'N/A')}")
        print()


def cmd_clients(args):
    """List all payments received (requires Square API)."""
    print("Checking recent Square payments...")
    try:
        now = datetime.utcnow()
        begin = (now - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")
        r = requests.post(
            f"{SQUARE_BASE}/payments/search",
            headers=_headers(),
            json={
                "query": {
                    "filter": {
                        "date_time_filter": {
                            "created_at": {"start_at": begin}
                        }
                    },
                    "sort": {"sort_field": "CREATED_AT", "sort_order": "DESC"},
                },
                "limit": 50,
            },
            timeout=10,
        )
        if r.status_code == 200:
            payments = r.json().get("payments", [])
            if not payments:
                print("No payments in the last 90 days.")
                return

            total = 0
            print(f"\n{'='*60}")
            print(f"  SQUARE PAYMENTS — Last 90 days")
            print(f"{'='*60}\n")

            for p in payments:
                amt = p.get("amount_money", {}).get("amount", 0) / 100
                status = p.get("status", "?")
                created = p.get("created_at", "")[:10]
                note = p.get("note", "")
                receipt = p.get("receipt_url", "")

                print(f"  ${amt:.0f}  |  {status}  |  {created}")
                if note:
                    print(f"    Note: {note}")
                if receipt:
                    print(f"    Receipt: {receipt}")
                print()

                if status == "COMPLETED":
                    total += amt

            print(f"  Total collected: ${total:,.0f}")
        else:
            print(f"API error: {r.status_code}")
            if r.status_code == 401:
                print("Token may be expired or invalid. Check SQUARE_ACCESS_TOKEN.")
    except requests.RequestException as e:
        print(f"Connection error: {e}")


def cmd_history(args):
    """Show full payment link history from local log."""
    log = _load_log()
    if not log:
        print("No payment links created yet.")
        return

    total = sum(e.get("amount", 0) for e in log)
    print(f"\n{'='*60}")
    print(f"  ALL PAYMENT LINKS — {len(log)} created, ${total:,} total value")
    print(f"{'='*60}\n")

    for entry in log:
        print(f"  [{entry.get('created', '?')[:10]}] {entry.get('name', '?')} — ${entry.get('amount', 0)}")
        print(f"    Client: {entry.get('client', 'N/A')}")
        print(f"    URL: {entry.get('url', 'N/A')}")
        print()


PARTNER_LOG = os.path.join(DATA_DIR, "partner_payments.json")


def _load_partner_log():
    if os.path.exists(PARTNER_LOG):
        with open(PARTNER_LOG) as f:
            return json.load(f)
    return []


def _save_partner_log(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PARTNER_LOG, "w") as f:
        json.dump(data, f, indent=2)


def cmd_partner_link(args):
    """Create a payment link for a partner's customer."""
    if len(args) < 3:
        print("Usage: square_payments.py partner-link <partner_slug> <amount> <service_description>")
        print("Example: square_payments.py partner-link jakes-lawn-care 50 'Weekly Mowing'")
        return

    partner_slug = args[0]
    amount = int(args[1])
    service = " ".join(args[2:])
    partner_display = partner_slug.replace("-", " ").title()

    import uuid
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "quick_pay": {
            "name": f"{partner_display} — {service}",
            "price_money": {"amount": amount * 100, "currency": "USD"},
            "location_id": _get_location_id(),
        },
        "checkout_options": {
            "allow_tipping": False,
            "redirect_url": f"https://bosssystems.co/p/{partner_slug}.html",
            "ask_for_shipping_address": False,
        },
    }

    print(f"Creating partner payment link: {partner_display} — {service} — ${amount}...")

    try:
        r = requests.post(
            f"{SQUARE_BASE}/online-checkout/payment-links",
            headers=_headers(), json=payload, timeout=10,
        )
        if r.status_code in (200, 201):
            data = r.json()
            link = data.get("payment_link", {})
            url = link.get("long_url") or link.get("url", "")
            link_id = link.get("id", "")

            print(f"\nPartner payment link created:")
            print(f"  URL: {url}")
            print(f"  Amount: ${amount}")
            print(f"  Partner: {partner_display} (keeps ${amount * 0.8:.0f}, BOSS keeps ${amount * 0.2:.0f})")

            log = _load_partner_log()
            log.append({
                "id": link_id,
                "partner": partner_slug,
                "partner_name": partner_display,
                "service": service,
                "amount": amount,
                "partner_share": round(amount * 0.8, 2),
                "boss_share": round(amount * 0.2, 2),
                "url": url,
                "created": datetime.now().isoformat(),
                "paid": False,
                "partner_paid_out": False,
            })
            _save_partner_log(log)

            pay_page = f"https://bosssystems.co/pay.html?partner={partner_slug}&name={requests.utils.quote(partner_display)}&amount={amount}&label={requests.utils.quote(service)}&square={requests.utils.quote(url)}"
            print(f"\n  Send to customer: {pay_page}")
            return url
        else:
            print(f"FAILED: {r.status_code}")
            err = r.json().get("errors", [])
            for e in err:
                print(f"  {e.get('detail', e.get('code'))}")
    except requests.RequestException as e:
        print(f"Connection error: {e}")


def cmd_partners(args):
    """Show partner payment summary — who's owed what (80/20 split)."""
    log = _load_partner_log()
    if not log:
        print("No partner payments yet.")
        return

    partners = {}
    for entry in log:
        slug = entry.get("partner", "unknown")
        if slug not in partners:
            partners[slug] = {
                "name": entry.get("partner_name", slug),
                "total_revenue": 0,
                "partner_owed": 0,
                "boss_earned": 0,
                "paid_out": 0,
                "unpaid": 0,
                "jobs": 0,
            }
        p = partners[slug]
        amt = entry.get("amount", 0)
        p["total_revenue"] += amt
        p["partner_owed"] += entry.get("partner_share", amt * 0.8)
        p["boss_earned"] += entry.get("boss_share", amt * 0.2)
        p["jobs"] += 1
        if entry.get("partner_paid_out"):
            p["paid_out"] += entry.get("partner_share", amt * 0.8)
        else:
            p["unpaid"] += entry.get("partner_share", amt * 0.8)

    print(f"\n{'='*60}")
    print(f"  PARTNER PAYMENT SUMMARY — 80/20 Split")
    print(f"{'='*60}\n")

    total_boss = 0
    total_owed = 0

    for slug, p in sorted(partners.items(), key=lambda x: x[1]["total_revenue"], reverse=True):
        print(f"  {p['name']}")
        print(f"    Jobs: {p['jobs']}  |  Revenue: ${p['total_revenue']:,.0f}")
        print(f"    Partner earned (80%): ${p['partner_owed']:,.0f}")
        print(f"    BOSS earned (20%):    ${p['boss_earned']:,.0f}")
        if p["unpaid"] > 0:
            print(f"    >>> OWES PARTNER: ${p['unpaid']:,.0f}")
        else:
            print(f"    All paid out")
        print()
        total_boss += p["boss_earned"]
        total_owed += p["unpaid"]

    print(f"  {'─'*40}")
    print(f"  BOSS total (20%): ${total_boss:,.0f}")
    print(f"  Still owed to partners: ${total_owed:,.0f}")
    print()


def cmd_payout(args):
    """Mark a partner's balance as paid out."""
    if not args:
        print("Usage: square_payments.py payout <partner_slug>")
        print("Marks all unpaid entries for that partner as paid out.")
        return

    partner_slug = args[0]
    log = _load_partner_log()
    count = 0
    total = 0

    for entry in log:
        if entry.get("partner") == partner_slug and not entry.get("partner_paid_out"):
            entry["partner_paid_out"] = True
            entry["payout_date"] = datetime.now().isoformat()
            count += 1
            total += entry.get("partner_share", 0)

    if count > 0:
        _save_partner_log(log)
        name = partner_slug.replace("-", " ").title()
        print(f"Marked {count} payments as paid out for {name}.")
        print(f"Total paid: ${total:,.0f}")
        _ntfy(f"Partner payout: {name}", f"Paid ${total:,.0f} to {name} ({count} jobs)")
    else:
        print(f"No unpaid entries found for {partner_slug}.")


def cmd_scan(args):
    """Scan Square for completed partner payments and sync to local log."""
    import re as _re
    print("Scanning Square for partner payments...")
    now = datetime.utcnow()
    begin = (now - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")
    try:
        r = requests.post(
            f"{SQUARE_BASE}/payments/search",
            headers=_headers(),
            json={
                "query": {
                    "filter": {"date_time_filter": {"created_at": {"start_at": begin}}},
                    "sort": {"sort_field": "CREATED_AT", "sort_order": "ASC"},
                },
                "limit": 100,
            },
            timeout=10,
        )
        if r.status_code != 200:
            print(f"API error: {r.status_code}")
            return

        payments = r.json().get("payments", [])
        log = _load_partner_log()
        existing_ids = {e.get("square_payment_id") for e in log if e.get("square_payment_id")}
        added = 0

        for p in payments:
            pid = p.get("id", "")
            if pid in existing_ids:
                continue
            note = p.get("note", "")
            m = _re.search(r'\[partner:([^\]]+)\]', note)
            if not m:
                continue
            if p.get("status") != "COMPLETED":
                continue

            slug = m.group(1)
            amt = p.get("amount_money", {}).get("amount", 0) / 100
            created = p.get("created_at", "")

            log.append({
                "id": pid,
                "square_payment_id": pid,
                "partner": slug,
                "partner_name": slug.replace("-", " ").title(),
                "service": note.split("]")[-1].strip() if "]" in note else "",
                "amount": amt,
                "partner_share": round(amt * 0.8, 2),
                "boss_share": round(amt * 0.2, 2),
                "url": "",
                "created": created,
                "paid": True,
                "partner_paid_out": False,
            })
            added += 1
            print(f"  + ${amt:.0f} from {slug} ({created[:10]})")

        if added:
            _save_partner_log(log)
            print(f"\nAdded {added} new partner payments to log.")
            _ntfy(f"{added} partner payments synced", f"${sum(e['amount'] for e in log[-added:]):.0f} total from Square scan")
        else:
            print("No new partner payments found.")

    except requests.RequestException as e:
        print(f"Connection error: {e}")


def _load_sub_log():
    if os.path.exists(SUBSCRIPTION_LOG):
        with open(SUBSCRIPTION_LOG) as f:
            return json.load(f)
    return []


def _save_sub_log(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SUBSCRIPTION_LOG, "w") as f:
        json.dump(data, f, indent=2)


def _load_catalog_cache():
    if os.path.exists(CATALOG_CACHE):
        with open(CATALOG_CACHE) as f:
            return json.load(f)
    return {}


def _save_catalog_cache(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CATALOG_CACHE, "w") as f:
        json.dump(data, f, indent=2)


def _ensure_plan(product_key):
    """Create or retrieve a Square catalog subscription plan for a product tier."""
    cache = _load_catalog_cache()
    if product_key in cache:
        return cache[product_key]

    p = PRODUCTS.get(product_key)
    if not p or not p.get("monthly"):
        print(f"Product {product_key} has no monthly price.")
        return None

    import uuid
    plan_id = f"#plan_{product_key}"
    variation_id = f"#var_{product_key}"

    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "object": {
            "type": "SUBSCRIPTION_PLAN",
            "id": plan_id,
            "subscription_plan_data": {
                "name": f"BOSS — {p['name']} Monthly",
                "subscription_plan_variations": [
                    {
                        "type": "SUBSCRIPTION_PLAN_VARIATION",
                        "id": variation_id,
                        "subscription_plan_variation_data": {
                            "name": f"{p['name']} — ${p['monthly']}/mo",
                            "phases": [
                                {
                                    "cadence": "MONTHLY",
                                    "recurring_price_money": {
                                        "amount": p["monthly"] * 100,
                                        "currency": "USD",
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        },
    }

    print(f"  Creating subscription plan for {p['name']} (${p['monthly']}/mo)...")
    try:
        r = requests.post(
            f"{SQUARE_BASE}/catalog/object",
            headers=_headers(), json=payload, timeout=10,
        )
        if r.status_code in (200, 201):
            obj = r.json().get("catalog_object", {})
            real_plan_id = obj.get("id", "")
            variations = (obj.get("subscription_plan_data") or {}).get("subscription_plan_variations", [])
            real_var_id = variations[0]["id"] if variations else ""

            if not real_var_id:
                print(f"  Plan created but no variation ID returned.")
                return None

            result = {"plan_id": real_plan_id, "variation_id": real_var_id}
            cache[product_key] = result
            _save_catalog_cache(cache)
            print(f"  Plan created: {real_plan_id} / variation: {real_var_id}")
            return result
        else:
            print(f"  Catalog error: {r.status_code}")
            errors = r.json().get("errors", [])
            for e in errors:
                print(f"    {e.get('detail', e.get('code'))}")
            return None
    except requests.RequestException as e:
        print(f"  Connection error: {e}")
        return None


def _find_or_create_customer(name, email=None, phone=None):
    """Find existing Square customer by email/phone, or create new one."""
    if email:
        try:
            r = requests.post(
                f"{SQUARE_BASE}/customers/search",
                headers=_headers(), timeout=8,
                json={"query": {"filter": {"email_address": {"exact": email}}}},
            )
            if r.status_code == 200:
                customers = r.json().get("customers", [])
                if customers:
                    cid = customers[0]["id"]
                    print(f"  Found existing customer: {cid}")
                    return cid
        except requests.RequestException:
            pass

    import uuid
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "given_name": name.split()[0] if name else "Client",
        "family_name": " ".join(name.split()[1:]) if name and len(name.split()) > 1 else "",
    }
    if email:
        body["email_address"] = email
    if phone:
        clean = "".join(c for c in phone if c.isdigit())
        if len(clean) == 10:
            clean = "+1" + clean
        elif len(clean) == 11 and clean[0] == "1":
            clean = "+" + clean
        body["phone_number"] = clean

    try:
        r = requests.post(
            f"{SQUARE_BASE}/customers",
            headers=_headers(), json=body, timeout=8,
        )
        if r.status_code in (200, 201):
            cid = r.json().get("customer", {}).get("id", "")
            print(f"  Customer created: {cid}")
            return cid
        else:
            print(f"  Customer creation failed: {r.status_code}")
            errors = r.json().get("errors", [])
            for e in errors:
                print(f"    {e.get('detail', e.get('code'))}")
            return None
    except requests.RequestException as e:
        print(f"  Connection error: {e}")
        return None


def cmd_subscribe(args):
    """Set up automatic monthly billing for a client.

    Creates a Square subscription — client gets a professional invoice
    email each month. They can add a card for autopay or pay manually.

    Usage:
      square_payments.py subscribe website "Smith Plumbing" --email john@smith.com --phone 9035551234
      square_payments.py subscribe receptionist "Dale's HVAC" --email dale@email.com
    """
    if len(args) < 2:
        print("Usage: square_payments.py subscribe <product> <client_name> [--email EMAIL] [--phone PHONE]")
        print(f"\nProducts with monthly billing: {', '.join(k for k,v in PRODUCTS.items() if v.get('monthly'))}")
        print("\nExamples:")
        print('  square_payments.py subscribe website "Smith Plumbing" --email john@smith.com')
        print('  square_payments.py subscribe receptionist "Dale HVAC" --email dale@hvac.com --phone 9035551234')
        return

    product_key = args[0]
    if product_key not in PRODUCTS:
        print(f"Unknown product: {product_key}")
        print(f"Available: {', '.join(PRODUCTS.keys())}")
        return

    p = PRODUCTS[product_key]
    if not p.get("monthly"):
        print(f"{p['name']} has no monthly fee.")
        return

    remaining = args[1:]
    email = None
    phone = None
    name_parts = []

    i = 0
    while i < len(remaining):
        if remaining[i] == "--email" and i + 1 < len(remaining):
            email = remaining[i + 1]
            i += 2
        elif remaining[i] == "--phone" and i + 1 < len(remaining):
            phone = remaining[i + 1]
            i += 2
        else:
            name_parts.append(remaining[i])
            i += 1

    client_name = " ".join(name_parts)
    if not client_name:
        print("Client name is required.")
        return

    if not email:
        print("WARNING: No email provided. Square will create the subscription but")
        print("  the client won't receive invoice emails until you add their email in Square Dashboard.")
        print("  Use --email to include it.\n")

    print(f"\nSetting up ${p['monthly']}/mo subscription for {client_name}...")
    print(f"  Product: {p['name']}")
    print(f"  Monthly: ${p['monthly']}")
    if email:
        print(f"  Email: {email}")
    if phone:
        print(f"  Phone: {phone}")

    plan = _ensure_plan(product_key)
    if not plan:
        print("\nFailed to create subscription plan. Check Square credentials.")
        return

    customer_id = _find_or_create_customer(client_name, email, phone)
    if not customer_id:
        print("\nFailed to create customer. Check Square credentials.")
        return

    import uuid
    location_id = _get_location_id()

    sub_body = {
        "idempotency_key": str(uuid.uuid4()),
        "location_id": location_id,
        "plan_variation_id": plan["variation_id"],
        "customer_id": customer_id,
        "timezone": "America/Chicago",
    }

    print(f"  Creating subscription...")
    try:
        r = requests.post(
            f"{SQUARE_BASE}/subscriptions",
            headers=_headers(), json=sub_body, timeout=10,
        )
        if r.status_code in (200, 201):
            sub = r.json().get("subscription", {})
            sub_id = sub.get("id", "")
            status = sub.get("status", "")
            start_date = sub.get("start_date", "")
            invoice_ids = sub.get("invoice_ids", [])

            print(f"\n  Subscription created!")
            print(f"  ID: {sub_id}")
            print(f"  Status: {status}")
            print(f"  Start date: {start_date}")
            print(f"  Amount: ${p['monthly']}/mo")
            if invoice_ids:
                print(f"  First invoice: {invoice_ids[0]}")
            if email:
                print(f"\n  {client_name} will receive a professional invoice at {email}")
                print(f"  They can pay by card and enable autopay from the invoice email.")
            else:
                print(f"\n  Add their email in Square Dashboard to send invoice emails.")

            log = _load_sub_log()
            log.append({
                "subscription_id": sub_id,
                "customer_id": customer_id,
                "product": product_key,
                "product_name": p["name"],
                "client_name": client_name,
                "email": email or "",
                "phone": phone or "",
                "monthly": p["monthly"],
                "status": status,
                "start_date": start_date,
                "created": datetime.now().isoformat(),
            })
            _save_sub_log(log)

            _ntfy(
                f"Subscription started: {client_name} ${p['monthly']}/mo",
                f"{p['name']}\nClient: {client_name}\n"
                + (f"Email: {email}\n" if email else "")
                + f"Monthly: ${p['monthly']}\nSubscription ID: {sub_id}\n"
                + f"Status: {status}\n"
                + "Client will receive monthly invoices from Square."
            )
            return sub_id
        else:
            print(f"\n  Subscription failed: {r.status_code}")
            errors = r.json().get("errors", [])
            for e in errors:
                print(f"    {e.get('detail', e.get('code'))}")
            return None
    except requests.RequestException as e:
        print(f"  Connection error: {e}")
        return None


def cmd_subscriptions(args):
    """List all active subscriptions."""
    log = _load_sub_log()
    if not log:
        print("No subscriptions created yet.")
        return

    active = [s for s in log if s.get("status") not in ("CANCELED", "DEACTIVATED")]
    total_mrr = sum(s.get("monthly", 0) for s in active)

    print(f"\n{'='*60}")
    print(f"  SUBSCRIPTIONS — {len(active)} active, ${total_mrr}/mo MRR")
    print(f"{'='*60}\n")

    for s in log:
        status_color = "ACTIVE" if s.get("status") not in ("CANCELED", "DEACTIVATED") else s.get("status", "?")
        print(f"  {s.get('client_name', '?')} — {s.get('product_name', '?')}")
        print(f"    ${s.get('monthly', 0)}/mo  |  {status_color}  |  Started {s.get('start_date', '?')}")
        if s.get("email"):
            print(f"    Email: {s['email']}")
        print(f"    Subscription ID: {s.get('subscription_id', '?')}")
        print()


def cmd_cancel_sub(args):
    """Cancel a client's subscription."""
    if not args:
        print("Usage: square_payments.py cancel-sub <subscription_id>")
        print("\nRun 'square_payments.py subscriptions' to see IDs.")
        return

    sub_id = args[0]
    print(f"Canceling subscription {sub_id}...")

    try:
        r = requests.post(
            f"{SQUARE_BASE}/subscriptions/{sub_id}/cancel",
            headers=_headers(), timeout=10,
        )
        if r.status_code in (200, 201):
            sub = r.json().get("subscription", {})
            canceled_date = sub.get("canceled_date", "")
            print(f"  Subscription canceled.")
            print(f"  Effective: {canceled_date}")

            log = _load_sub_log()
            for s in log:
                if s.get("subscription_id") == sub_id:
                    s["status"] = "CANCELED"
                    s["canceled_date"] = canceled_date
            _save_sub_log(log)

            client = next((s.get("client_name", "?") for s in log if s.get("subscription_id") == sub_id), "?")
            _ntfy(f"Subscription canceled: {client}", f"ID: {sub_id}\nEffective: {canceled_date}")
        else:
            print(f"  Failed: {r.status_code}")
            errors = r.json().get("errors", [])
            for e in errors:
                print(f"    {e.get('detail', e.get('code'))}")
    except requests.RequestException as e:
        print(f"  Connection error: {e}")


COMMANDS = {
    "link": (cmd_link, "Create a payment link"),
    "partner-link": (cmd_partner_link, "Create payment link for partner's customer"),
    "status": (cmd_status, "Show recent payment links"),
    "clients": (cmd_clients, "List Square payments received"),
    "partners": (cmd_partners, "Partner payment summary — who's owed what"),
    "payout": (cmd_payout, "Mark partner balance as paid out"),
    "scan": (cmd_scan, "Sync partner payments from Square to local log"),
    "history": (cmd_history, "Full payment link history"),
    "subscribe": (cmd_subscribe, "Set up automatic monthly billing"),
    "subscriptions": (cmd_subscriptions, "List all subscriptions"),
    "cancel-sub": (cmd_cancel_sub, "Cancel a subscription"),
    "test": (cmd_test, "Verify Square API credentials"),
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nSquare Payments — BOSS Systems\n")
        print("Commands:")
        for cmd, (fn, desc) in COMMANDS.items():
            print(f"  square_payments.py {cmd:<12} {desc}")
        print("\nExamples:")
        print("  python3 square_payments.py link receptionist 'Dale HVAC'")
        print("  python3 square_payments.py link custom 500 'Consulting'")
        print("  python3 square_payments.py test")
        print("\nRequires SQUARE_ACCESS_TOKEN — see SQUARE_SETUP.md")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    cmd_args = sys.argv[2:]

    if cmd in COMMANDS:
        COMMANDS[cmd][0](cmd_args)
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(COMMANDS.keys())}")
