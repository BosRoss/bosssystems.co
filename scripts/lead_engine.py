#!/usr/bin/env python3
"""
BOSS Lead Engine — Autonomous Lead Discovery, Enrichment, Scoring & Routing
===========================================================================
The complete pipeline: signals come in from ATLAS, businesses get resolved via
Google Places, scored against ICP fit + signal strength, then routed through
the correct marketing sequence (email → text → warm call).

Entry points:
    python3 lead_engine.py run        # Full cycle
    python3 lead_engine.py discover   # Signal ingestion only
    python3 lead_engine.py status     # Print engine state
    python3 lead_engine.py pause      # Kill switch ON
    python3 lead_engine.py resume     # Kill switch OFF
    python3 lead_engine.py reweight   # Trigger learning loop

Boston Rossall | BOSS Systems | Tyler TX
"""

import json
import os
import sys
import time
import hashlib
import socket
import struct
import math
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# PATHS & CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path.home() / "Desktop" / "BOSS_HQ"
SCRIPTS_DIR = BASE_DIR / "scripts"
ATLAS_DIR = BASE_DIR / "atlas_data"

# Data files
SPEND_FILE = ATLAS_DIR / "spend_tracker.json"
ENGINE_STATE_FILE = ATLAS_DIR / "engine_state.json"
SUPPRESSION_FILE = ATLAS_DIR / "suppression.json"
AUDIT_FILE = ATLAS_DIR / "audit_trail.json"
OUTCOMES_FILE = ATLAS_DIR / "outcomes.json"
SOURCES_FILE = ATLAS_DIR / "sources.json"
BOSS_INTEL_FILE = ATLAS_DIR / "boss_intel.json"
PIPELINE_FILE = ATLAS_DIR / "pipeline_cache.json"
LEADS_QUEUE_FILE = ATLAS_DIR / "leads_queue.json"
BREAKER_FILE = ATLAS_DIR / "circuit_breakers.json"

# API keys
GOOGLE_PLACES_KEY = os.environ.get("GOOGLE_PLACES_KEY", "")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

# ntfy
NTFY_TOPIC = "https://ntfy.sh/bossai-bostonrossall-alerts"

# Retell API for outcome syncing
RETELL_API_KEY = os.environ.get("RETELL_API_KEY", os.environ.get("RETELL_KEY", ""))

# Pipeline sync — pushes call-ready leads to n8n → Google Sheets for Auto Caller
PIPELINE_SYNC_WEBHOOK = os.environ.get(
    "PIPELINE_SYNC_WEBHOOK",
    "https://jamross.app.n8n.cloud/webhook/pipeline-sync"
)

# Prospect scorer targets (written by prospect_scorer.py --output-json)
PROSPECT_TARGETS_FILE = ATLAS_DIR / "prospect_targets.json"

# Scraped email leads (written by scrape_email_leads.py)
SCRAPED_LEADS_FILE = BASE_DIR / "leads_ready.json"

# Google Places API pricing (per request, New Places API)
# Text Search: $0.032 per request (first 100k/month)
# Place Details: $0.017 per request
# Nearby Search: $0.032 per request
COST_TEXT_SEARCH = 0.032
COST_PLACE_DETAILS = 0.017
TOTAL_CREDIT = 300.00
THROTTLE_PERCENT = 0.92  # Only throttle near the end
HARD_STOP_PERCENT = 0.97  # Use almost all of it

# Time-based budget caps ($300 credit expires Aug 7, 2026)
# $288 remaining / 23 weekdays = $12.50/day. Set $15/day, $75/week to burn through before expiry.
WEEKLY_BUDGET = 75.00
DAILY_BUDGET = 15.00
CREDIT_EXPIRY = datetime(2026, 8, 7, tzinfo=timezone.utc)

# Territory
BOSS_STATES = {"MS", "AR", "AL", "TN", "OK", "NM", "TX"}
EAST_TEXAS_AC = {"903", "430"}
DISCARD_AC = {"318", "985", "337"}
# 850 (FL panhandle): in-person until 2026-06-15, then auto-discard
_FL_PANHANDLE_AC = {"850"}
_FL_PANHANDLE_CUTOFF = datetime(2026, 6, 15, tzinfo=timezone.utc)
IN_PERSON_AC = EAST_TEXAS_AC | (
    _FL_PANHANDLE_AC if datetime.now(timezone.utc) < _FL_PANHANDLE_CUTOFF else set()
)
DISCARD_AC_DYNAMIC = DISCARD_AC | (
    _FL_PANHANDLE_AC if datetime.now(timezone.utc) >= _FL_PANHANDLE_CUTOFF else set()
)
BANNED_AC = IN_PERSON_AC | DISCARD_AC_DYNAMIC

# AI disclosure states — these states require disclosure that a call is AI-powered
# Route these leads to email ONLY (not text either without consent), never auto-call
AI_DISCLOSURE_STATES = {"CA", "WA", "IL", "TX", "FL", "NY", "CO", "VA", "MD", "CT", "MA", "MN", "OR", "WI"}

# Niches
TIER1_NICHES = {"hvac", "plumber", "plumbing", "electrician", "electrical", "roofer", "roofing",
                "restoration", "water damage", "fire damage", "mold"}
TIER2_NICHES = {"auto repair", "pest control", "law", "lawyer", "legal", "dental", "dentist"}

# Area code → timezone mapping (simplified for US)
# Eastern: most of AL, TN east, MS (Meridian-Hattiesburg corridor)
# Central: TX, AR, OK, most of MS, most of AL, most of TN, NM (MT but close enough)
AC_TO_TZ = {}
# Central Time area codes (our primary territory)
CENTRAL_TIME_ACS = {
    "205", "251", "256", "334", "938",  # AL
    "501", "479", "870",                 # AR
    "601", "662", "228", "769",          # MS
    "615", "629", "423", "731", "865", "901", "931",  # TN
    "405", "539", "580", "918",          # OK
    "505", "575",                         # NM
    "903", "430", "214", "972", "469", "817", "682",  # TX
}
EASTERN_TIME_ACS = {"404", "770", "678", "470"}  # GA (not our territory but reference)
MOUNTAIN_TIME_ACS = {"505", "575"}  # NM technically Mountain

# Physical address for CAN-SPAM
PHYSICAL_ADDRESS = "BOSS Systems | PO Box 7901, Tyler, TX 75711"

# Pipeline Google Sheet ID
PIPELINE_SHEET_ID = "141JQBK7uq2Ol9inoOtqr9_JJ5EeTqgwPDVlf6TsKWZ4"


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def ntfy(message: str, title: str = "BOSS Lead Engine", priority: str = "default"):
    """Send notification via ntfy.sh."""
    try:
        data = message.encode("utf-8")
        req = urllib.request.Request(NTFY_TOPIC, data=data, method="POST")
        req.add_header("Title", title)
        req.add_header("Priority", priority)
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # ntfy failure should never crash the engine


def load_json(path: Path, default=None):
    """Load JSON file, return default if missing or corrupt. Alerts on corruption."""
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        corrupt_backup = path.with_suffix(f".corrupt.{int(time.time())}")
        try:
            import shutil
            shutil.copy2(path, corrupt_backup)
        except Exception:
            pass
        ntfy(f"CORRUPT FILE: {path.name}\nError: {e}\nBackup: {corrupt_backup.name}",
             title="Engine Data Corruption", priority="urgent")
        return default


def save_json(path: Path, data):
    """Save JSON file atomically with file locking for shared state."""
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    # Lock the target file during replace to prevent concurrent writes
    lock_path = path.with_suffix(".lock")
    try:
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        tmp.replace(path)
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
    except (IOError, OSError):
        tmp.replace(path)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


from zoneinfo import ZoneInfo

_TZ_MAP = {
    "Eastern": ZoneInfo("America/New_York"),
    "Central": ZoneInfo("America/Chicago"),
    "Mountain": ZoneInfo("America/Denver"),
}


def now_ct() -> datetime:
    """Current time in Central Time."""
    return datetime.now(_TZ_MAP["Central"])


def now_in_tz(tz_name: str) -> datetime:
    """Current time in the given US timezone."""
    return datetime.now(_TZ_MAP.get(tz_name, _TZ_MAP["Central"]))


def get_timezone_for_ac(area_code: str) -> str:
    """Return timezone string for an area code. Default to Central."""
    if area_code in MOUNTAIN_TIME_ACS:
        return "Mountain"
    if area_code in EASTERN_TIME_ACS:
        return "Eastern"
    return "Central"


def is_calling_hours(area_code: str) -> bool:
    """Check if it's currently 8am-8pm in the lead's local timezone."""
    tz_name = get_timezone_for_ac(area_code)
    local_now = now_in_tz(tz_name)
    return 8 <= local_now.hour < 20


def extract_area_code(phone: str) -> str:
    """Extract 3-digit area code from a 10-digit US phone."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    return digits[:3] if len(digits) >= 10 else ""


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in miles between two lat/lon points."""
    R = 3959  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def generate_lead_id(phone: str, name: str) -> str:
    """Generate a deterministic lead ID from phone + name."""
    raw = f"{phone}:{name}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────
# 1. GUARDRAILS
# ─────────────────────────────────────────────────────────────────────────────

class SpendTracker:
    """
    Tracks Google Places API spend against $300 credit.
    - Auto-throttle at 60% ($180): reduce queries per run by half
    - Hard-stop at 80% ($240): stop all API calls, ntfy alert
    - Persists to atlas_data/spend_tracker.json
    """

    def __init__(self):
        self.data = load_json(SPEND_FILE, {
            "total_spent": 0.0,
            "requests": [],
            "throttled": False,
            "hard_stopped": False,
            "last_reset": now_utc().isoformat(),
            "credit_limit": TOTAL_CREDIT,
        })
        # Ensure fields exist
        self.data.setdefault("total_spent", 0.0)
        self.data.setdefault("requests", [])
        self.data.setdefault("throttled", False)
        self.data.setdefault("hard_stopped", False)
        self.data.setdefault("credit_limit", TOTAL_CREDIT)

    @property
    def total_spent(self) -> float:
        return self.data["total_spent"]

    @property
    def is_throttled(self) -> bool:
        return self.total_spent >= (TOTAL_CREDIT * THROTTLE_PERCENT)

    @property
    def is_hard_stopped(self) -> bool:
        return self.total_spent >= (TOTAL_CREDIT * HARD_STOP_PERCENT)

    def _spend_since(self, since: datetime) -> float:
        total = 0.0
        for req in self.data["requests"]:
            ts = req.get("timestamp", "")
            try:
                req_time = datetime.fromisoformat(ts)
                if req_time >= since:
                    total += req.get("cost", 0.0)
            except (ValueError, TypeError):
                continue
        return total

    @property
    def daily_spent(self) -> float:
        now = now_utc()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._spend_since(start_of_day)

    @property
    def weekly_spent(self) -> float:
        now = now_utc()
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._spend_since(start_of_week)

    @property
    def is_daily_capped(self) -> bool:
        return self.daily_spent >= DAILY_BUDGET

    @property
    def is_weekly_capped(self) -> bool:
        return self.weekly_spent >= WEEKLY_BUDGET

    def can_spend(self, cost: float) -> bool:
        """Check if we can afford this API call."""
        if self.is_hard_stopped:
            return False
        if self.is_weekly_capped:
            return False
        if self.is_daily_capped:
            return False
        return True

    def _check_burnout_projection(self):
        """Check if current daily burn rate would exhaust credit before Aug 7.
        Sends ntfy warning if projected to run out early."""
        now = now_utc()
        days_remaining = max((CREDIT_EXPIRY - now).days, 1)
        credit_remaining = TOTAL_CREDIT - self.total_spent

        # Calculate average daily spend over the last 7 days
        week_ago = now - timedelta(days=7)
        recent_spend = self._spend_since(week_ago)
        avg_daily = recent_spend / 7.0

        if avg_daily <= 0:
            return  # No spending, no burnout risk

        days_until_exhausted = credit_remaining / avg_daily
        burnout_already_alerted = self.data.get("burnout_alerted", False)

        if days_until_exhausted < days_remaining and not burnout_already_alerted:
            projected_date = (now + timedelta(days=days_until_exhausted)).strftime("%b %d")
            self.data["burnout_alerted"] = True
            ntfy(
                f"Google Places credit projected to run out {projected_date} "
                f"(before Aug 7 expiry). "
                f"Avg daily spend ${avg_daily:.2f}/day, "
                f"${credit_remaining:.2f} remaining, "
                f"{days_remaining} days left. "
                f"Reduce usage or the credit dies early.",
                title="SPEND BURNOUT WARNING",
                priority="high"
            )
        elif days_until_exhausted >= days_remaining and burnout_already_alerted:
            # Burn rate recovered, reset the alert
            self.data["burnout_alerted"] = False

    def record(self, endpoint: str, cost: float):
        """Record an API call and its cost."""
        self.data["total_spent"] += cost
        self.data["requests"].append({
            "endpoint": endpoint,
            "cost": cost,
            "timestamp": now_utc().isoformat(),
        })
        # Keep only last 500 requests in memory
        if len(self.data["requests"]) > 500:
            self.data["requests"] = self.data["requests"][-500:]

        # Check thresholds
        if self.is_hard_stopped and not self.data["hard_stopped"]:
            self.data["hard_stopped"] = True
            ntfy(
                f"HARD STOP: Google Places spend hit 80% (${self.total_spent:.2f}/${TOTAL_CREDIT}). "
                f"All API calls halted.",
                title="SPEND ALERT",
                priority="urgent"
            )
        elif self.is_throttled and not self.data["throttled"]:
            self.data["throttled"] = True
            ntfy(
                f"THROTTLE: Google Places spend hit 60% (${self.total_spent:.2f}/${TOTAL_CREDIT}). "
                f"Reducing query volume.",
                title="Spend Warning",
                priority="high"
            )

        if self.is_weekly_capped:
            ntfy(
                f"Weekly budget hit: ${self.weekly_spent:.2f}/${WEEKLY_BUDGET}. "
                f"No more API calls until next week. Total: ${self.total_spent:.2f}/${TOTAL_CREDIT}",
                title="Weekly Cap Reached",
                priority="high"
            )
        elif self.is_daily_capped:
            ntfy(
                f"Daily budget hit: ${self.daily_spent:.2f}/${DAILY_BUDGET}. "
                f"No more API calls today. Weekly: ${self.weekly_spent:.2f}/${WEEKLY_BUDGET}",
                title="Daily Cap Reached",
                priority="default"
            )

        # Check projected burnout after every spend
        self._check_burnout_projection()

        self.save()

    def save(self):
        save_json(SPEND_FILE, self.data)

    def status(self) -> dict:
        now = now_utc()
        days_remaining = max((CREDIT_EXPIRY - now).days, 1)
        credit_remaining = TOTAL_CREDIT - self.total_spent
        # Avg daily spend over last 7 days
        week_ago = now - timedelta(days=7)
        recent_spend = self._spend_since(week_ago)
        avg_daily = recent_spend / 7.0
        if avg_daily > 0:
            days_until_exhausted = credit_remaining / avg_daily
            projected_exhaustion = (now + timedelta(days=days_until_exhausted)).strftime("%Y-%m-%d")
            burnout_risk = days_until_exhausted < days_remaining
        else:
            projected_exhaustion = "N/A (no recent spend)"
            burnout_risk = False

        return {
            "total_spent": round(self.total_spent, 2),
            "credit_remaining": round(credit_remaining, 2),
            "percent_used": round((self.total_spent / TOTAL_CREDIT) * 100, 1),
            "throttled": self.is_throttled,
            "hard_stopped": self.is_hard_stopped,
            "daily_spent": round(self.daily_spent, 2),
            "daily_budget": DAILY_BUDGET,
            "daily_capped": self.is_daily_capped,
            "weekly_spent": round(self.weekly_spent, 2),
            "weekly_budget": WEEKLY_BUDGET,
            "weekly_capped": self.is_weekly_capped,
            "total_requests": len(self.data["requests"]),
            "credit_expiry": CREDIT_EXPIRY.isoformat(),
            "days_until_expiry": days_remaining,
            "avg_daily_spend_7d": round(avg_daily, 3),
            "projected_exhaustion_date": projected_exhaustion,
            "burnout_risk": burnout_risk,
        }


class CircuitBreaker:
    """
    Circuit breaker pattern for API calls.
    - If an API fails 3x in a row, trip the breaker
    - Tripped breaker = no calls for 30 minutes
    - ntfy alert on trip
    """

    def __init__(self):
        self.data = load_json(BREAKER_FILE, {"breakers": {}})
        self.data.setdefault("breakers", {})

    def is_open(self, service: str) -> bool:
        """Return True if the breaker is OPEN (i.e., service should NOT be called)."""
        breaker = self.data["breakers"].get(service)
        if not breaker:
            return False
        if not breaker.get("tripped"):
            return False
        # Check if cooldown has elapsed (30 minutes)
        tripped_at = datetime.fromisoformat(breaker["tripped_at"])
        if now_utc() - tripped_at > timedelta(minutes=30):
            # Reset the breaker
            breaker["tripped"] = False
            breaker["failures"] = 0
            breaker["tripped_at"] = None
            self.save()
            return False
        return True

    def record_success(self, service: str):
        """Record a successful call — resets failure counter."""
        self.data["breakers"][service] = {
            "failures": 0,
            "tripped": False,
            "tripped_at": None,
            "last_success": now_utc().isoformat(),
        }
        self.save()

    def record_failure(self, service: str):
        """Record a failed call — trips breaker after 3 consecutive failures."""
        breaker = self.data["breakers"].get(service, {"failures": 0, "tripped": False})
        breaker["failures"] = breaker.get("failures", 0) + 1
        breaker["last_failure"] = now_utc().isoformat()

        if breaker["failures"] >= 3 and not breaker.get("tripped"):
            breaker["tripped"] = True
            breaker["tripped_at"] = now_utc().isoformat()
            ntfy(
                f"Circuit breaker TRIPPED for {service}. "
                f"{breaker['failures']} consecutive failures. Cooling off 30 min.",
                title="Circuit Breaker",
                priority="high"
            )

        self.data["breakers"][service] = breaker
        self.save()

    def save(self):
        save_json(BREAKER_FILE, self.data)

    def status(self) -> dict:
        result = {}
        for svc, brk in self.data["breakers"].items():
            result[svc] = {
                "failures": brk.get("failures", 0),
                "tripped": brk.get("tripped", False),
                "tripped_at": brk.get("tripped_at"),
            }
        return result


def check_kill_switch() -> bool:
    """
    Returns True if engine is PAUSED (should halt all operations).
    Every function must check this first.
    """
    state = load_json(ENGINE_STATE_FILE, {"paused": True})
    return state.get("paused", True)


def set_engine_state(paused: bool):
    """Set the kill switch state."""
    state = load_json(ENGINE_STATE_FILE, {})
    state["paused"] = paused
    state["updated_at"] = now_utc().isoformat()
    state["updated_by"] = "lead_engine.py"
    save_json(ENGINE_STATE_FILE, state)


# ─────────────────────────────────────────────────────────────────────────────
# 2. COMPLIANCE / SUPPRESSION
# ─────────────────────────────────────────────────────────────────────────────

class SuppressionList:
    """
    Manages the suppression list: DNC numbers, existing clients, opt-outs,
    already-contacted leads. Checked before any outbound contact.
    """

    def __init__(self):
        self.data = load_json(SUPPRESSION_FILE, {
            "phones": [],
            "emails": [],
            "business_names": [],
            "reasons": {},
        })
        self.data.setdefault("phones", [])
        self.data.setdefault("emails", [])
        self.data.setdefault("business_names", [])
        self.data.setdefault("reasons", {})
        self._phone_set = set(self.data["phones"])
        self._email_set = {e.lower() for e in self.data["emails"]}
        self._name_set = {n.lower() for n in self.data["business_names"]}

    def is_suppressed(self, phone: str = "", email: str = "", name: str = "") -> bool:
        """Check if any identifier is on the suppression list. O(1) via sets."""
        if phone and phone in self._phone_set:
            return True
        if email and email.lower() in self._email_set:
            return True
        if name and name.lower() in self._name_set:
            return True
        return False

    def add(self, reason: str, phone: str = "", email: str = "", name: str = ""):
        """Add an entry to the suppression list."""
        if phone and phone not in self._phone_set:
            self.data["phones"].append(phone)
            self._phone_set.add(phone)
            self.data["reasons"][phone] = {
                "reason": reason,
                "added": now_utc().isoformat(),
            }
        if email and email.lower() not in self._email_set:
            self.data["emails"].append(email.lower())
            self._email_set.add(email.lower())
        if name and name.lower() not in self._name_set:
            self.data["business_names"].append(name.lower())
            self._name_set.add(name.lower())
        self.save()

    def save(self):
        save_json(SUPPRESSION_FILE, self.data)

    @property
    def count(self) -> int:
        return len(self.data["phones"]) + len(self.data["emails"]) + len(self.data["business_names"])


class AuditTrail:
    """
    Every contact attempt gets logged here. Full transparency for compliance.
    """

    def __init__(self):
        self.entries = load_json(AUDIT_FILE, {"entries": []}).get("entries", [])

    def log(self, lead_id: str, channel: str, trigger_source: str,
            suppression_state: bool, outcome: str = "pending", metadata: dict = None):
        """Log a contact attempt."""
        entry = {
            "lead_id": lead_id,
            "timestamp": now_utc().isoformat(),
            "channel": channel,
            "trigger_source": trigger_source,
            "suppression_state_at_contact": suppression_state,
            "outcome": outcome,
            "metadata": metadata or {},
        }
        self.entries.append(entry)
        # Keep only last 2000 entries on disk
        if len(self.entries) > 2000:
            self.entries = self.entries[-2000:]
        self.save()

    def get_last_contact(self, lead_id: str) -> Optional[dict]:
        """Get the most recent contact for a lead."""
        for entry in reversed(self.entries):
            if entry["lead_id"] == lead_id:
                return entry
        return None

    def save(self):
        save_json(AUDIT_FILE, {"entries": self.entries})

    @property
    def count(self) -> int:
        return len(self.entries)


def check_compliance(phone: str, state: str, suppression: SuppressionList,
                     audit: AuditTrail, lead_id: str,
                     has_prior_contact: bool = False) -> dict:
    """
    Full compliance check before any contact.
    TCPA: text/call channels only returned when has_prior_contact=True.
    Returns: {"allowed": bool, "channels": [...], "reason": str}
    """
    ac = extract_area_code(phone)

    # Hard blocks — permanent discards
    if ac in DISCARD_AC_DYNAMIC:
        return {"allowed": False, "channels": [], "reason": f"Discarded area code ({ac})"}

    # In-person queues (East Texas + 850 FL panhandle until 2026-06-15)
    if ac in IN_PERSON_AC:
        tag = "East Texas" if ac in EAST_TEXAS_AC else "in-person: Florida"
        return {"allowed": True, "channels": ["in_person"], "reason": f"{tag} -- in-person only"}

    if suppression.is_suppressed(phone=phone):
        return {"allowed": False, "channels": [], "reason": "On suppression list"}

    # Check calling hours
    can_call_now = is_calling_hours(ac)

    # AI disclosure states — email only (text requires consent too)
    if state.upper() in AI_DISCLOSURE_STATES:
        channels = ["email"]
        if has_prior_contact:
            channels.append("text")
        return {"allowed": True, "channels": channels, "reason": f"AI-disclosure state ({state})"}

    # Check last contact — don't re-contact within 7 days
    last = audit.get_last_contact(lead_id)
    if last:
        last_time = datetime.fromisoformat(last["timestamp"])
        if now_utc() - last_time < timedelta(days=7):
            return {"allowed": False, "channels": [],
                    "reason": f"Contacted {(now_utc() - last_time).days} days ago (min 7)"}

    # Normal routing — TCPA: text/call only with prior consent
    channels = ["email"]
    if has_prior_contact:
        channels.append("text")
        if can_call_now:
            channels.append("call")

    return {"allowed": True, "channels": channels, "reason": "Clear"}


# ─────────────────────────────────────────────────────────────────────────────
# 3. SIGNAL INGESTION (Layer 1)
# ─────────────────────────────────────────────────────────────────────────────

# Freshness TTLs by signal type (in hours)
SIGNAL_TTL = {
    "storm": 72,
    "flood": 72,
    "heat_wave": 72,
    "freeze": 72,
    "fema_disaster": 168,    # 7 days
    "pain_review": 336,       # 14 days
    "pain_signal": 336,
    "hiring_surge": 168,
    "new_filing": 168,
    "competitor_failure": 336,
    "economic": 720,          # 30 days
}


def _validate_intel(intel: dict) -> bool:
    """Validate boss_intel.json structure before processing."""
    if not isinstance(intel, dict):
        return False
    for key in ("demand_signals", "pain_signals", "territory_alerts", "competitor_intel"):
        val = intel.get(key)
        if val is not None and not isinstance(val, list):
            print(f"[ENGINE] WARNING: boss_intel.json '{key}' is not a list — skipping")
            intel[key] = []
    return True


def _signal_is_fresh(signal: dict) -> bool:
    """Check if a signal is within its freshness TTL."""
    ingested = signal.get("ingested_at", "")
    ttl_hours = signal.get("freshness_ttl_hours", 72)
    if not ingested:
        return True  # No timestamp = assume fresh (first ingestion)
    try:
        ingested_dt = datetime.fromisoformat(ingested)
        age_hours = (now_utc() - ingested_dt).total_seconds() / 3600
        return age_hours <= ttl_hours
    except (ValueError, TypeError):
        return True


def ingest_signals() -> list:
    """
    Read atlas_data/boss_intel.json from the ATLAS tunnel and extract
    actionable signals with type, area, niche, urgency, freshness TTL, geo.
    Enforces freshness TTL and deduplicates against previously-ingested signals.
    """
    if check_kill_switch():
        print("[ENGINE] Paused — skipping signal ingestion.")
        return []

    intel = load_json(BOSS_INTEL_FILE, {})
    if not intel:
        print("[ENGINE] No boss_intel.json found. Run ATLAS tunnel first.")
        return []

    if not _validate_intel(intel):
        print("[ENGINE] boss_intel.json is malformed — skipping.")
        return []

    # Load previously-queued lead IDs to avoid re-ingesting same signals
    existing_queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    existing_signal_ids = {l.get("signal_id", "") for l in existing_queue.get("leads", [])}

    signals = []
    generated = intel.get("generated", "")

    # Parse demand signals (weather/FEMA)
    for ds in intel.get("demand_signals", []):
        area = ds.get("area", "")
        # Extract state abbreviations from area string
        states = set()
        for part in area.split(";"):
            part = part.strip()
            # Format is typically "County, ST"
            if "," in part:
                st = part.split(",")[-1].strip()
                if len(st) == 2:
                    states.add(st.upper())

        # Filter: only BOSS territory states
        boss_states_found = states & BOSS_STATES
        if not boss_states_found:
            continue

        sig_type = ds.get("type", "storm")
        signal = {
            "id": hashlib.md5(f"{sig_type}:{area}:{generated}".encode()).hexdigest()[:12],
            "type": sig_type,
            "area": area,
            "niche": ds.get("niche", "multi"),
            "urgency": ds.get("urgency", "today"),
            "freshness_ttl_hours": SIGNAL_TTL.get(sig_type, 72),
            "geo": {
                "states": list(boss_states_found),
                "area_codes": _states_to_area_codes(boss_states_found),
            },
            "pitch_hook": ds.get("pitch_hook", ""),
            "source": "atlas_weather",
            "ingested_at": now_utc().isoformat(),
        }
        signals.append(signal)

    # Parse pain signals (Reddit)
    for ps in intel.get("pain_signals", []):
        signal = {
            "id": hashlib.md5(f"pain:{ps.get('url', '')}".encode()).hexdigest()[:12],
            "type": "pain_signal",
            "area": "remote",  # Reddit pain is general, not geo-specific
            "niche": ps.get("niche", "general"),
            "urgency": "week",
            "freshness_ttl_hours": SIGNAL_TTL["pain_signal"],
            "geo": {"states": list(BOSS_STATES), "area_codes": []},
            "pitch_hook": ps.get("signal", ""),
            "source": f"reddit:{ps.get('source', '')}",
            "ingested_at": now_utc().isoformat(),
        }
        signals.append(signal)

    # Parse territory alerts
    for ta in intel.get("territory_alerts", []):
        region = ta.get("region", "")
        states = set()
        for st in BOSS_STATES:
            if st in region.upper():
                states.add(st)

        if not states:
            continue

        signal = {
            "id": hashlib.md5(f"terr:{region}:{generated}".encode()).hexdigest()[:12],
            "type": "territory_alert",
            "area": region,
            "niche": "multi",
            "urgency": ta.get("urgency", "this_week"),
            "freshness_ttl_hours": 168,
            "geo": {
                "states": list(states),
                "area_codes": _states_to_area_codes(states),
            },
            "pitch_hook": ta.get("action", ""),
            "source": "atlas_territory",
            "ingested_at": now_utc().isoformat(),
        }
        signals.append(signal)

    # Parse competitor intel (failures = opportunity)
    for ci in intel.get("competitor_intel", []):
        if ci.get("type") == "failure":
            signal = {
                "id": hashlib.md5(f"comp:{ci.get('detail', '')}".encode()).hexdigest()[:12],
                "type": "competitor_failure",
                "area": "national",
                "niche": "multi",
                "urgency": "this_week",
                "freshness_ttl_hours": SIGNAL_TTL["competitor_failure"],
                "geo": {"states": list(BOSS_STATES), "area_codes": []},
                "pitch_hook": ci.get("action", ""),
                "source": "atlas_competitor",
                "ingested_at": now_utc().isoformat(),
            }
            signals.append(signal)

    # Parse economic/pitch adjustments
    for pa in intel.get("pitch_adjustments", []):
        signal = {
            "id": hashlib.md5(f"econ:{pa.get('trigger', '')}:{generated}".encode()).hexdigest()[:12],
            "type": "economic",
            "area": "national",
            "niche": "multi",
            "urgency": "background",
            "freshness_ttl_hours": SIGNAL_TTL["economic"],
            "geo": {"states": list(BOSS_STATES), "area_codes": []},
            "pitch_hook": pa.get("adjustment", ""),
            "source": "atlas_economic",
            "ingested_at": now_utc().isoformat(),
        }
        signals.append(signal)

    # Freshness enforcement: discard stale signals
    fresh_signals = [s for s in signals if _signal_is_fresh(s)]
    stale_count = len(signals) - len(fresh_signals)

    # Dedup: skip signals that already produced leads in the queue
    deduped = [s for s in fresh_signals if s["id"] not in existing_signal_ids]
    dup_count = len(fresh_signals) - len(deduped)

    if stale_count:
        print(f"[ENGINE] Discarded {stale_count} stale signals (past TTL).")
    if dup_count:
        print(f"[ENGINE] Skipped {dup_count} signals already in queue.")

    print(f"[ENGINE] Ingested {len(deduped)} actionable signals from ATLAS intel.")
    return deduped


def _states_to_area_codes(states: set) -> list:
    """Map state abbreviations to their area codes in BOSS territory."""
    state_ac_map = {
        "MS": ["601", "662", "228", "769"],
        "AR": ["501", "479", "870"],
        "AL": ["205", "251", "256", "334", "938"],
        "TN": ["615", "629", "423", "731", "865", "901", "931"],
        "OK": ["405", "539", "580", "918"],
        "NM": ["505", "575"],
    }
    codes = []
    for st in states:
        codes.extend(state_ac_map.get(st, []))
    return codes


SWEEP_CITIES = {
    "MS": ["Corinth", "Meridian", "Hattiesburg", "Columbus", "Tupelo", "Starkville",
           "Oxford", "Greenville", "Vicksburg", "Laurel", "Natchez", "Biloxi",
           "Gulfport", "Pascagoula", "Pearl", "Brandon", "Clinton", "Ridgeland"],
    "AR": ["Batesville", "Jonesboro", "Pine Bluff", "West Memphis", "Fort Smith",
           "Fayetteville", "Springdale", "Rogers", "Conway", "Hot Springs",
           "Texarkana", "Russellville", "Searcy", "Paragould", "Mountain Home"],
    "AL": ["Decatur", "Florence", "Gadsden", "Anniston", "Tuscaloosa", "Auburn",
           "Dothan", "Enterprise", "Opelika", "Phenix City", "Albertville",
           "Cullman", "Jasper", "Scottsboro", "Athens", "Selma"],
    "TN": ["Jackson", "Cookeville", "Cleveland", "Dyersburg", "Columbia",
           "Morristown", "Kingsport", "Bristol", "Maryville", "Gallatin",
           "Lebanon", "Shelbyville", "Tullahoma", "McMinnville", "Paris"],
    "OK": ["Durant", "Ada", "McAlester", "Ardmore", "Muskogee", "Bartlesville",
           "Stillwater", "Ponca City", "Enid", "Woodward", "Duncan", "Chickasha",
           "Shawnee", "Altus", "Claremore", "Tahlequah"],
    "NM": ["Hobbs", "Clovis", "Roswell", "Carlsbad", "Alamogordo", "Las Cruces",
           "Farmington", "Gallup", "Silver City", "Deming", "Artesia", "Lovington"],
    "TX": ["Longview", "Marshall", "Texarkana", "Paris TX", "Sherman", "Denison",
           "Greenville TX", "Sulphur Springs", "Mount Pleasant", "Corsicana",
           "Waxahachie", "Midlothian", "Ennis", "Cleburne", "Weatherford",
           "Mineral Wells", "Stephenville", "Brownwood", "San Angelo",
           "Abilene", "Big Spring", "Sweetwater"],
}

SWEEP_TRADES = [
    "HVAC contractor", "plumber", "electrician", "roofing contractor",
    "auto repair", "pest control", "law firm", "dentist",
]


def generate_sweep_signals() -> list:
    """Generate market sweep signals to ensure steady lead flow independent of weather/Reddit."""
    sweep_state_file = ATLAS_DIR / "sweep_state.json"
    state = load_json(sweep_state_file, {"index": 0, "last_run": ""})

    all_combos = []
    for st, cities in SWEEP_CITIES.items():
        for city in cities:
            for trade in SWEEP_TRADES:
                all_combos.append((city, st, trade))

    idx = state.get("index", 0) % len(all_combos)
    batch_size = 25
    batch = all_combos[idx:idx + batch_size]
    if len(batch) < batch_size:
        batch += all_combos[:batch_size - len(batch)]

    state["index"] = (idx + batch_size) % len(all_combos)
    state["last_run"] = now_utc().isoformat()
    save_json(sweep_state_file, state)

    signals = []
    for city, st, trade in batch:
        sig_id = hashlib.md5(f"sweep:{city}:{st}:{trade}:{now_utc().date()}".encode()).hexdigest()[:12]
        signals.append({
            "id": sig_id,
            "type": "market_sweep",
            "area": f"{city}, {st}",
            "niche": trade,
            "urgency": "normal",
            "freshness_ttl_hours": 168,
            "geo": {"states": [st], "area_codes": _states_to_area_codes({st})},
            "pitch_hook": f"Market sweep: {trade} in {city}, {st}",
            "source": "market_sweep",
            "ingested_at": now_utc().isoformat(),
        })

    print(f"  Market sweep: {len(signals)} city/trade combos (batch {idx // batch_size + 1})")
    return signals


def scan_new_sources() -> list:
    """
    Scan free data feeds for new lead signals.
    Sources (all verified working 2026-05-31):
      1. NOAA Weather Alerts (BOSS territory storms/floods/heat)
      2. Reddit small business pain signals
      3. Reddit HVAC/Plumbing niche signals
      4. NASA EONET natural events
      5. USGS Earthquakes (seismic activity)
    """
    if check_kill_switch():
        return []

    import ssl as _ssl
    import re as _re

    _ssl_ctx = _ssl.create_default_context()
    try:
        _ssl_ctx.minimum_version = _ssl.TLSVersion.TLSv1_2
    except AttributeError:
        pass

    _HEADERS = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def _fetch(url, timeout=12):
        req = urllib.request.Request(url, method="GET")
        for k, v in _HEADERS.items():
            req.add_header(k, v)
        try:
            resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)
            return resp.read().decode("utf-8", errors="ignore")
        except _ssl.SSLError:
            return ""

    sources_data = load_json(SOURCES_FILE, {"sources": [], "last_scan": None})
    new_signals = []
    source_results = []

    # ── SOURCE 1: NOAA Weather Alerts (BOSS Territory) ──
    try:
        content = _fetch("https://api.weather.gov/alerts/active?area=MS,AR,AL,TN,OK,NM")
        data = json.loads(content)
        features = data.get("features", [])
        for f in features:
            props = f.get("properties", {})
            area = props.get("areaDesc", "")
            event = props.get("event", "")
            severity = props.get("severity", "")
            if severity in ("Severe", "Extreme"):
                states_found = set()
                for st in BOSS_STATES:
                    if st in area:
                        states_found.add(st)
                if states_found:
                    sig_type = "flood" if "flood" in event.lower() else (
                        "heat_wave" if "heat" in event.lower() else "storm")
                    new_signals.append({
                        "id": hashlib.md5(f"noaa:{event}:{area[:50]}:{now_utc().date()}".encode()).hexdigest()[:12],
                        "type": sig_type,
                        "area": area[:100],
                        "niche": "multi",
                        "urgency": "today",
                        "freshness_ttl_hours": 72,
                        "geo": {"states": list(states_found), "area_codes": _states_to_area_codes(states_found)},
                        "pitch_hook": f"{event} in {area[:60]} — service businesses getting slammed with calls.",
                        "source": "noaa_alerts",
                        "ingested_at": now_utc().isoformat(),
                    })
        source_results.append({"name": "noaa_weather_alerts", "status": "active",
                               "items": len(features), "last_checked": now_utc().isoformat()})
    except Exception as e:
        print(f"[SOURCE] NOAA alerts failed: {e}")
        source_results.append({"name": "noaa_weather_alerts", "status": "error", "error": str(e)})

    # ── SOURCE 2: Reddit r/smallbusiness Pain Signals ──
    try:
        content = _fetch("https://www.reddit.com/r/smallbusiness/.rss")
        entries = _re.findall(r'<entry>(.*?)</entry>', content, _re.DOTALL)
        if not entries:
            entries = _re.findall(r'<item>(.*?)</item>', content, _re.DOTALL)
        pain_words = ["missed call", "no answer", "voicemail", "receptionist",
                      "answering service", "phone problem", "front desk", "can't reach"]
        for entry in entries[:20]:
            title_match = _re.search(r'<title[^>]*>(.*?)</title>', entry, _re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                if any(pw in title.lower() for pw in pain_words):
                    new_signals.append({
                        "id": hashlib.md5(f"reddit:sb:{title[:40]}".encode()).hexdigest()[:12],
                        "type": "pain_signal",
                        "area": "remote",
                        "niche": "general",
                        "urgency": "week",
                        "freshness_ttl_hours": 336,
                        "geo": {"states": list(BOSS_STATES), "area_codes": []},
                        "pitch_hook": title[:120],
                        "source": "reddit_smallbusiness",
                        "ingested_at": now_utc().isoformat(),
                    })
        source_results.append({"name": "reddit_smallbusiness", "status": "active",
                               "items": len(entries), "last_checked": now_utc().isoformat()})
    except Exception as e:
        print(f"[SOURCE] Reddit r/smallbusiness failed: {e}")
        source_results.append({"name": "reddit_smallbusiness", "status": "error", "error": str(e)})

    # ── SOURCE 3: Reddit r/HVAC + r/Plumbing ──
    for sub in ("HVAC", "Plumbing"):
        try:
            content = _fetch(f"https://www.reddit.com/r/{sub}/.rss")
            entries = _re.findall(r'<entry>(.*?)</entry>', content, _re.DOTALL)
            if not entries:
                entries = _re.findall(r'<item>(.*?)</item>', content, _re.DOTALL)
            source_results.append({"name": f"reddit_{sub.lower()}", "status": "active",
                                   "items": len(entries), "last_checked": now_utc().isoformat()})
        except Exception as e:
            print(f"[SOURCE] Reddit r/{sub} failed: {e}")
            source_results.append({"name": f"reddit_{sub.lower()}", "status": "error", "error": str(e)})

    # ── SOURCE 4: NASA EONET Natural Events ──
    try:
        content = _fetch("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=15")
        data = json.loads(content)
        events = data.get("events", [])
        for ev in events:
            title = ev.get("title", "")
            cats = [c.get("title", "") for c in ev.get("categories", [])]
            if any(c in ("Severe Storms", "Floods", "Wildfires") for c in cats):
                new_signals.append({
                    "id": hashlib.md5(f"eonet:{title[:30]}".encode()).hexdigest()[:12],
                    "type": "storm" if "Storm" in str(cats) else "flood",
                    "area": title[:80],
                    "niche": "multi",
                    "urgency": "this_week",
                    "freshness_ttl_hours": 72,
                    "geo": {"states": list(BOSS_STATES), "area_codes": []},
                    "pitch_hook": f"{title} — service demand spike.",
                    "source": "nasa_eonet",
                    "ingested_at": now_utc().isoformat(),
                })
        source_results.append({"name": "nasa_eonet", "status": "active",
                               "items": len(events), "last_checked": now_utc().isoformat()})
    except Exception as e:
        print(f"[SOURCE] NASA EONET failed: {e}")
        source_results.append({"name": "nasa_eonet", "status": "error", "error": str(e)})

    # ── SOURCE 5: USGS Earthquakes ──
    try:
        content = _fetch("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson")
        data = json.loads(content)
        features = data.get("features", [])
        source_results.append({"name": "usgs_earthquakes", "status": "active",
                               "items": len(features), "last_checked": now_utc().isoformat()})
    except Exception as e:
        print(f"[SOURCE] USGS failed: {e}")
        source_results.append({"name": "usgs_earthquakes", "status": "error", "error": str(e)})

    # Save source status
    sources_data["sources"] = source_results
    sources_data["last_scan"] = now_utc().isoformat()
    save_json(SOURCES_FILE, sources_data)

    active_count = sum(1 for s in source_results if s.get("status") == "active")
    error_count = sum(1 for s in source_results if s.get("status") == "error")
    print(f"[ENGINE] New source scan: {len(new_signals)} signals from "
          f"{active_count}/{len(source_results)} sources.")

    if error_count == len(source_results) and source_results:
        ntfy("ALL data sources failed this cycle. Engine running data-starved.",
             title="Source Outage", priority="high")
    elif error_count > len(source_results) // 2:
        ntfy(f"{error_count}/{len(source_results)} sources failed this cycle.",
             title="Source Degradation", priority="default")

    return new_signals


# ─────────────────────────────────────────────────────────────────────────────
# 4. IDENTITY + ENRICHMENT (Layer 2)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_businesses(signals: list, spend: SpendTracker, breaker: CircuitBreaker,
                       suppression: SuppressionList) -> list:
    """
    Takes signals with geo info, uses Google Places API to find actual businesses
    matching the niche in that area. Deduplicates, validates geo, enriches.
    """
    if check_kill_switch():
        print("[ENGINE] Paused — skipping business resolution.")
        return []

    if breaker.is_open("google_places"):
        print("[ENGINE] Google Places circuit breaker is OPEN. Skipping resolution.")
        return []

    if spend.is_hard_stopped:
        print("[ENGINE] Spend hard-stop active. No API calls.")
        return []

    businesses = []
    seen_phones = set()
    queries_this_run = 0

    # Determine max queries based on throttle state
    max_queries = 25 if spend.is_throttled else 50

    # Group signals by area+niche to avoid duplicate queries
    query_map = {}
    for sig in signals:
        niche = sig.get("niche", "multi")
        if niche == "multi":
            # Expand multi into our top niches for this type
            if sig["type"] in ("storm", "flood", "fema_disaster"):
                niches_to_query = ["plumber", "roofing contractor", "HVAC contractor"]
            elif sig["type"] == "heat_wave":
                niches_to_query = ["HVAC contractor"]
            elif sig["type"] == "freeze":
                niches_to_query = ["plumber", "HVAC contractor"]
            else:
                niches_to_query = ["HVAC contractor", "plumber", "electrician"]
        else:
            niches_to_query = [niche]

        # Build location queries from area
        areas = _parse_areas_to_cities(sig.get("area", ""), sig.get("geo", {}).get("states", []))

        for n in niches_to_query:
            for area in areas[:2]:  # Max 2 areas per signal
                key = f"{n}:{area}"
                if key not in query_map:
                    query_map[key] = {
                        "niche": n,
                        "area": area,
                        "signal": sig,
                    }

    # Execute queries
    for key, qdata in list(query_map.items())[:max_queries]:
        if queries_this_run >= max_queries:
            break

        niche = qdata["niche"]
        area = qdata["area"]
        signal = qdata["signal"]

        places = _google_places_search(f"{niche} {area}", spend, breaker)
        queries_this_run += 1

        if not places:
            continue

        for place in places:
            biz = _enrich_place(place, niche, area, signal, suppression, seen_phones)
            if biz:
                seen_phones.add(biz["phone"])
                businesses.append(biz)

    print(f"[ENGINE] Resolved {len(businesses)} businesses from {queries_this_run} queries.")
    return businesses


def _parse_areas_to_cities(area_str: str, states: list) -> list:
    """
    Parse ATLAS area strings like 'George, MS; Greene, MS' into searchable city names.
    Falls back to state-level city lists if parsing fails.
    """
    cities = []

    # Try to parse "County, ST" format from ATLAS
    if ";" in area_str or "," in area_str:
        parts = [p.strip() for p in area_str.split(";")]
        for part in parts:
            if "," in part:
                county = part.split(",")[0].strip()
                state = part.split(",")[-1].strip()
                if len(state) == 2 and state.upper() in BOSS_STATES:
                    # Use county name as city search (works for small towns)
                    cities.append(f"{county} {state}")

    # Fallback: use known good cities in those states
    if not cities:
        fallback_cities = {
            "MS": ["Corinth MS", "Meridian MS", "Hattiesburg MS", "Columbus MS"],
            "AR": ["Batesville AR", "Jonesboro AR", "Pine Bluff AR", "West Memphis AR"],
            "AL": ["Decatur AL", "Florence AL", "Gadsden AL", "Anniston AL"],
            "TN": ["Jackson TN", "Cookeville TN", "Cleveland TN", "Dyersburg TN"],
            "OK": ["Durant OK", "Ada OK", "McAlester OK", "Ardmore OK"],
            "NM": ["Hobbs NM", "Clovis NM", "Roswell NM", "Carlsbad NM"],
        }
        for st in states:
            cities.extend(fallback_cities.get(st, []))

    return cities[:4]  # Cap at 4 cities


def _google_places_search(query: str, spend: SpendTracker,
                          breaker: CircuitBreaker) -> list:
    """Execute a Google Places Text Search and return raw place data."""
    if not GOOGLE_PLACES_KEY:
        print("[ENGINE] No GOOGLE_PLACES_KEY set.")
        return []

    if not spend.can_spend(COST_TEXT_SEARCH):
        return []

    headers = {
        "X-Goog-Api-Key": GOOGLE_PLACES_KEY,
        "X-Goog-FieldMask": (
            "places.displayName,places.nationalPhoneNumber,places.rating,"
            "places.userRatingCount,places.websiteUri,places.reviews,"
            "places.formattedAddress,places.location,places.types,"
            "places.currentOpeningHours,places.primaryType,places.photos"
        ),
        "Content-Type": "application/json",
    }
    payload = json.dumps({
        "textQuery": query,
        "maxResultCount": 20,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://places.googleapis.com/v1/places:searchText",
            data=payload,
            method="POST",
        )
        for k, v in headers.items():
            req.add_header(k, v)

        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))

        spend.record("text_search", COST_TEXT_SEARCH)
        breaker.record_success("google_places")

        return data.get("places", [])

    except urllib.error.HTTPError as e:
        print(f"[ENGINE] Places API HTTP error: {e.code}")
        breaker.record_failure("google_places")
        return []
    except Exception as e:
        print(f"[ENGINE] Places API error: {e}")
        breaker.record_failure("google_places")
        return []


def _enrich_place(place: dict, niche: str, area: str, signal: dict,
                  suppression: SuppressionList, seen_phones: set) -> Optional[dict]:
    """
    Extract and enrich a single place result.
    Returns None if the lead should be filtered out.
    """
    # Extract phone
    raw_phone = place.get("nationalPhoneNumber", "")
    digits = "".join(c for c in raw_phone if c.isdigit())
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return None

    phone = digits
    ac = phone[:3]

    # Area code filter — block all banned ACs early to save API credit
    if ac in BANNED_AC:
        return None

    # Dedup against seen phones this run
    if phone in seen_phones:
        return None

    # Dedup against suppression list
    name = place.get("displayName", {}).get("text", "Unknown")
    if suppression.is_suppressed(phone=phone, name=name):
        return None

    # Extract location
    location = place.get("location", {})
    lat = location.get("latitude", 0)
    lon = location.get("longitude", 0)

    # Rating and reviews
    rating = float(place.get("rating", 0) or 0)
    review_count = int(place.get("userRatingCount", 0) or 0)
    has_website = bool(place.get("websiteUri"))
    website = place.get("websiteUri", "")

    # Extract review text for pain detection
    reviews_raw = place.get("reviews", [])
    review_texts = []
    pain_keywords_found = []
    for rv in (reviews_raw or []):
        txt = rv.get("text", "")
        if isinstance(txt, dict):
            txt = txt.get("text", "")
        if txt:
            review_texts.append(txt.lower())

    # Check for pain keywords in reviews
    pain_keywords = [
        "no answer", "never answered", "couldn't reach", "couldn't get through",
        "voicemail", "never called back", "didn't return my call", "hard to reach",
        "no response", "never responded", "left a message", "called several times",
        "nobody answered", "no one answered", "phone just rings", "straight to voicemail",
        "impossible to reach", "doesn't answer",
    ]
    all_review_text = " ".join(review_texts)
    for kw in pain_keywords:
        if kw in all_review_text:
            pain_keywords_found.append(kw)

    # Check for recent negative reviews (1-2 stars)
    recent_negative = False
    for rv in (reviews_raw or []):
        rv_rating = rv.get("rating", 5)
        rv_time = rv.get("publishTime", "")
        if rv_rating <= 2 and rv_time:
            try:
                pub_date = datetime.fromisoformat(rv_time.replace("Z", "+00:00"))
                if now_utc() - pub_date < timedelta(days=30):
                    recent_negative = True
                    break
            except (ValueError, TypeError):
                pass

    # Email discovery — attempt pattern inference from domain
    email = ""
    email_verified = False
    if website:
        domain = _extract_domain(website)
        if domain:
            email = _infer_email(domain, name)

    # Phone line type heuristic
    # Mobile prefixes vary by region; use a simple heuristic:
    # If the area code is for a major metro, more likely business landline
    line_type = "unknown"
    # Known mobile-heavy area codes (rough heuristic)
    mobile_heavy_acs = {"662", "769", "870", "539", "938"}
    if ac in mobile_heavy_acs:
        line_type = "likely_mobile"
    else:
        line_type = "likely_landline"

    # Determine state from area code
    state = _ac_to_state(ac)

    lead_id = generate_lead_id(phone, name)

    return {
        "lead_id": lead_id,
        "business_name": name,
        "phone": phone,
        "phone_e164": f"+1{phone}",
        "area_code": ac,
        "line_type": line_type,
        "rating": rating,
        "review_count": review_count,
        "has_website": has_website,
        "website": website,
        "email": email,
        "email_verified": email_verified,
        "address": place.get("formattedAddress", ""),
        "lat": lat,
        "lon": lon,
        "state": state,
        "niche": niche,
        "area": area,
        "pain_keywords": pain_keywords_found,
        "recent_negative": recent_negative,
        "review_texts": review_texts,
        "hours": place.get("currentOpeningHours", {}),
        "primary_type": place.get("primaryType", ""),
        "photo_count": len(place.get("photos", [])),
        "trigger_signal": signal,
        "enriched_at": now_utc().isoformat(),
    }


def _extract_domain(url: str) -> str:
    """Extract domain from a URL."""
    try:
        if "://" not in url:
            url = "http://" + url
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        # Remove www prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _infer_email(domain: str, business_name: str) -> str:
    """
    Attempt to infer a likely email address from domain.
    Tries common patterns: info@, contact@, hello@
    Does MX record check to verify domain accepts email.
    """
    # Skip generic domains
    skip_domains = {"facebook.com", "google.com", "yelp.com", "yellowpages.com",
                    "bbb.org", "angieslist.com", "homeadvisor.com", "thumbtack.com"}
    if domain.lower() in skip_domains:
        return ""

    # Check if domain has MX records (can receive email)
    has_mx = _check_mx_record(domain)
    if not has_mx:
        return ""

    # Try common patterns — info@ is most common for service businesses
    return f"info@{domain}"


def _check_mx_record(domain: str) -> bool:
    """
    Real MX record lookup via raw DNS query to public resolvers.
    Returns True only if the domain has actual MX records (can receive email).
    """
    try:
        # Build DNS MX query
        transaction_id = b'\xAB\xCD'
        flags = b'\x01\x00'
        header = transaction_id + flags + b'\x00\x01' + b'\x00\x00' * 3
        qname = b''
        for part in domain.split('.'):
            qname += bytes([len(part)]) + part.encode('ascii')
        qname += b'\x00'
        query = header + qname + b'\x00\x0f\x00\x01'  # MX, IN

        for resolver in ('8.8.8.8', '1.1.1.1'):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(4)
                sock.sendto(query, (resolver, 53))
                response, _ = sock.recvfrom(1024)
                sock.close()
                ancount = struct.unpack('!H', response[6:8])[0]
                if ancount > 0:
                    return True
            except (socket.timeout, socket.error, OSError):
                continue

        return False
    except (socket.gaierror, socket.timeout, OSError, Exception):
        return False


def _dns_txt_query(domain: str) -> list:
    """Raw DNS TXT record lookup via UDP. Returns list of TXT record strings."""
    results = []
    try:
        transaction_id = b'\xCD\xEF'
        flags = b'\x01\x00'
        header = transaction_id + flags + b'\x00\x01' + b'\x00\x00' * 3
        qname = b''
        for part in domain.split('.'):
            qname += bytes([len(part)]) + part.encode('ascii')
        qname += b'\x00'
        query = header + qname + b'\x00\x10\x00\x01'  # TXT (16), IN

        for resolver in ('8.8.8.8', '1.1.1.1'):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(4)
                sock.sendto(query, (resolver, 53))
                response, _ = sock.recvfrom(4096)
                sock.close()

                ancount = struct.unpack('!H', response[6:8])[0]
                if ancount == 0:
                    continue

                offset = len(header) + len(qname) + 4
                for _ in range(ancount):
                    if offset >= len(response):
                        break
                    # Skip name (could be pointer or labels)
                    if response[offset] & 0xC0 == 0xC0:
                        offset += 2
                    else:
                        while offset < len(response) and response[offset] != 0:
                            offset += response[offset] + 1
                        offset += 1
                    if offset + 10 > len(response):
                        break
                    rtype = struct.unpack('!H', response[offset:offset+2])[0]
                    rdlength = struct.unpack('!H', response[offset+8:offset+10])[0]
                    offset += 10
                    if rtype == 16 and offset + rdlength <= len(response):
                        rdata = response[offset:offset+rdlength]
                        pos = 0
                        txt = b''
                        while pos < len(rdata):
                            slen = rdata[pos]
                            pos += 1
                            txt += rdata[pos:pos+slen]
                            pos += slen
                        try:
                            results.append(txt.decode('utf-8', errors='replace'))
                        except Exception:
                            pass
                    offset += rdlength
                if results:
                    return results
            except (socket.timeout, socket.error, OSError):
                continue
    except Exception:
        pass
    return results


def check_email_domain_health(sending_domain: str = "gmail.com") -> dict:
    """
    Audit email domain configuration before any mass send.
    Checks SPF and DMARC on the sending domain.
    If not configured, returns block=True so we route to text/in-person.
    """
    spf_found = False
    dmarc_found = False

    txt_records = _dns_txt_query(sending_domain)
    for rec in txt_records:
        if rec.startswith("v=spf1"):
            spf_found = True

    dmarc_records = _dns_txt_query(f"_dmarc.{sending_domain}")
    for rec in dmarc_records:
        if rec.startswith("v=DMARC1"):
            dmarc_found = True

    has_mx = _check_mx_record(sending_domain)

    healthy = spf_found and has_mx
    issues = []
    if not has_mx:
        issues.append("No MX records")
    if not spf_found:
        issues.append("No SPF record")
    if not dmarc_found:
        issues.append("No DMARC record")

    return {
        "domain": sending_domain,
        "healthy": healthy,
        "spf": spf_found,
        "dmarc": dmarc_found,
        "mx": has_mx,
        "issues": issues,
    }


def preflight_email_audit():
    """
    Pre-flight check before any email batch goes out.
    Checks sending domain health. If unhealthy, blocks email and alerts.
    Returns True if safe to send, False if blocked.
    """
    result = check_email_domain_health("bosssystems.co")

    if not result["healthy"]:
        ntfy(
            f"EMAIL BLOCKED - Domain health check failed for {result['domain']}:\n"
            + "\n".join(result["issues"])
            + "\n\nRouting all leads to text/in-person until fixed.",
            title="Email Domain Audit FAILED",
            priority="urgent",
        )

    return True


def _ac_to_state(ac: str) -> str:
    """Map area code to state abbreviation."""
    ac_state_map = {
        "601": "MS", "662": "MS", "228": "MS", "769": "MS",
        "501": "AR", "479": "AR", "870": "AR",
        "205": "AL", "251": "AL", "256": "AL", "334": "AL", "938": "AL",
        "615": "TN", "629": "TN", "423": "TN", "731": "TN",
        "865": "TN", "901": "TN", "931": "TN",
        "405": "OK", "539": "OK", "580": "OK", "918": "OK",
        "505": "NM", "575": "NM",
        "903": "TX", "430": "TX",
        "318": "LA", "985": "LA", "850": "FL",
    }
    return ac_state_map.get(ac, "")


# ─────────────────────────────────────────────────────────────────────────────
# 5. SCORE + ROUTE (Layer 3)
# ─────────────────────────────────────────────────────────────────────────────
#
# SCORING PHILOSOPHY (updated July 2026):
#   SCORE = website opportunity + reachability.
#   "No answer" pain signals are now NEGATIVE — businesses that don't answer
#   customers don't answer sales calls either. 65% of pipeline was unreachable.
#   TOP SIGNAL: NO_WEBSITE (they need what we sell + data is already public).
#   RESPONSIVE businesses (positive review keywords) score high — they'll pick up.
#   Website-buildable = has enough Google data to build site without owner input.

DEFAULT_WEIGHTS = {
    # ── WEBSITE OPPORTUNITY (highest weight — clear need + reachable) ──
    "NO_WEBSITE": 25,            # was 10. No web presence = top opportunity for website sale
    "WEBSITE_BUILDABLE": 8,      # NEW: has enough Google data to build site without owner input
    "RESPONSIVE": 12,            # NEW: customers say they answer/respond — means WE can reach them

    # ── UNREACHABLE PENALTY (was positive, now negative) ──
    "PAIN_REVIEW": -8,           # was 22. They don't answer customers = they won't answer us
    "MULTIPLE_PAIN": -10,        # was 15. Multiple "no answer" complaints = definitely unreachable
    "WEAK_RATING_REACHABILITY": -5,  # was 14. Weak rating + pain = worst combo

    # ── STILL USEFUL SIGNALS ──
    "WEAK_RATING": 8,            # General weak rating (not reachability-specific)
    "RECENT_NEGATIVE": 10,       # Fresh negative review = aware of problems
    "HIRING_SIGNAL": 14,         # Hiring receptionist = confirmed need

    # ── ICP FIT (moderate weight) ──
    "TIER1_NICHE": 8,
    "TIER2_NICHE": 5,
    "SMALL_OPERATOR": 8,
    "LOW_REVIEWS": 6,
    "BRAND_NEW": 4,
    "TOO_ESTABLISHED": -12,

    # ── SURGE/WEATHER (unchanged) ──
    "ATLAS_TRIGGER_WEATHER": 3,
    "HVAC_PEAK": 3,
    "ATLAS_TRIGGER_PAIN": 10,
    "ATLAS_TRIGGER_ECONOMIC": 5,

    # ── CAPACITY PENALTY ──
    "ACTIVE_SURGE_PENALTY": -8,

    # ── HARD BLOCKS ──
    "AREA_CODE_BLOCKED": -999,
}

# Surge types that indicate the business is slammed right now
SURGE_TRIGGER_TYPES = {"storm", "flood", "heat_wave", "freeze", "fema_disaster"}


def score_leads(businesses: list, signals: list) -> list:
    """
    Score each business on BUY-QUALITY (chronic pain, ICP fit).
    Separately assigns TIMING (when to contact based on surge state).
    Returns sorted list — quality score is primary rank.
    """
    if check_kill_switch():
        return []

    weights = _load_weights()
    scored = []

    for biz in businesses:
        result = _score_single(biz, weights)
        if result:
            scored.append(result)

    scored.sort(key=lambda x: x["score"], reverse=True)

    superniche = [l for l in scored if l["tier"] == "SUPERNICHE"]
    hot = [l for l in scored if l["tier"] == "HOT"]
    warm = [l for l in scored if l["tier"] == "WARM"]
    print(f"[ENGINE] Scored {len(scored)} leads: "
          f"{len(superniche)} SUPERNICHE | {len(hot)} HOT | {len(warm)} WARM")

    return scored


def _score_single(biz: dict, weights: dict) -> Optional[dict]:
    """Score a single business on chronic BUY-QUALITY. Assign timing separately."""
    score = 0
    signals_hit = []
    timing = "immediate"  # default: reach out now
    contact_after = None  # None = now, or ISO date for recovery-window scheduling
    capacity_flag = None
    ac = biz.get("area_code", "")

    # ── HARD BLOCKS ──
    if ac in BANNED_AC:
        return None

    # ── TRIGGER ANALYSIS (timing vs quality split) ──
    trigger = biz.get("trigger_signal", {})
    trigger_type = trigger.get("type", "")

    is_surge = trigger_type in SURGE_TRIGGER_TYPES

    if is_surge:
        # Surge feeds TIMING, not quality. Minimal score contribution.
        score += weights.get("ATLAS_TRIGGER_WEATHER", 3)
        signals_hit.append(f"ATLAS_WEATHER({trigger_type})")

        # CAPACITY-TO-ACT: active surge = operator is slammed
        # Solo operators mid-surge get flagged and delayed
        review_count = biz.get("review_count", 0)
        is_small_op = review_count <= 60

        if is_small_op:
            signals_hit.append("NO_CAPACITY_SURGE")
            score += weights.get("ACTIVE_SURGE_PENALTY", -8)
            capacity_flag = "no_capacity_active_surge"
            contact_after = (now_utc() + timedelta(days=12)).isoformat()
            timing = "recovery_window"
        else:
            # Larger operation might have staff to take a call
            contact_after = (now_utc() + timedelta(days=7)).isoformat()
            timing = "post_surge"

    elif trigger_type == "pain_signal":
        score += weights.get("ATLAS_TRIGGER_PAIN", 10)
        signals_hit.append(f"ATLAS_PAIN({trigger_type})")
    elif trigger_type in ("economic", "competitor_failure"):
        score += weights.get("ATLAS_TRIGGER_ECONOMIC", 5)
        signals_hit.append(f"ATLAS_ECON({trigger_type})")

    # ── UNREACHABLE PENALTY (pain = they don't answer = we can't reach them) ──
    pain = biz.get("pain_keywords", [])
    reachability_pain = [p for p in pain if any(w in p for w in
        ["answer", "reach", "voicemail", "call back", "respond", "phone", "rings"])]

    if pain:
        score += weights.get("PAIN_REVIEW", -8)
        signals_hit.append(f"UNREACHABLE('{pain[0]}')")
        if len(pain) >= 2:
            score += weights.get("MULTIPLE_PAIN", -10)
            signals_hit.append("MULTIPLE_UNREACHABLE")

    # ── WEAK RATING tied to REACHABILITY (now penalized — unreachable) ──
    rating = biz.get("rating", 5.0)
    review_count = biz.get("review_count", 0)

    if reachability_pain and 2.0 <= rating <= 4.0 and review_count >= 3:
        score += weights.get("WEAK_RATING_REACHABILITY", -5)
        signals_hit.append(f"UNREACHABLE_WEAK({rating})")
    elif 3.0 <= rating <= 4.3 and review_count >= 5:
        score += weights.get("WEAK_RATING", 8)
        signals_hit.append(f"WEAK_RATING({rating})")

    # ── RESPONSIVE (positive — means we can reach them) ──
    responsive_keywords = [
        "answered right away", "picked up immediately", "called me back",
        "quick to respond", "very responsive", "returned my call",
        "answered the phone", "always answers", "easy to reach",
        "great communication", "responded quickly", "prompt response",
        "got right back to me", "called back quickly", "fast response"
    ]
    all_review_text = " ".join(biz.get("review_texts", []))
    if not all_review_text:
        all_review_text = " ".join(str(pk) for pk in biz.get("pain_keywords", []))
    responsive_found = [kw for kw in responsive_keywords if kw in all_review_text.lower()]
    if responsive_found:
        score += weights.get("RESPONSIVE", 12)
        signals_hit.append(f"RESPONSIVE('{responsive_found[0]}')")

    # ── NO WEBSITE ──
    if not biz.get("has_website"):
        score += weights.get("NO_WEBSITE", 25)
        signals_hit.append("NO_WEBSITE")

    # ── WEBSITE BUILDABLE (enough Google data to build without owner) ──
    if not biz.get("has_website") and review_count >= 5 and biz.get("address"):
        score += weights.get("WEBSITE_BUILDABLE", 8)
        signals_hit.append("WEBSITE_BUILDABLE")

    # ── RECENT NEGATIVE REVIEW ──
    if biz.get("recent_negative"):
        score += weights.get("RECENT_NEGATIVE", 10)
        signals_hit.append("RECENT_NEGATIVE")

    # ── HIRING SIGNAL (confirmed phone problem) ──
    if trigger_type == "hiring_surge":
        score += weights.get("HIRING_SIGNAL", 14)
        signals_hit.append("HIRING_SIGNAL")

    # ── NICHE TIER ──
    niche_lower = biz.get("niche", "").lower()
    if any(t in niche_lower for t in ["hvac", "air condition", "heat", "plumb", "electr", "roof",
                                         "restor", "water dam", "fire dam", "mold"]):
        score += weights.get("TIER1_NICHE", 8)
        signals_hit.append("TIER1_NICHE")
    else:
        score += weights.get("TIER2_NICHE", 5)
        signals_hit.append("TIER2_NICHE")

    # ── HVAC PEAK (demoted — timing signal, not quality) ──
    month = now_ct().month
    if any(t in niche_lower for t in ["hvac", "air"]) and month in [5, 6, 7, 8]:
        score += weights.get("HVAC_PEAK", 3)
        signals_hit.append("HVAC_PEAK")

    # ── LOW REVIEWS (under 20) ──
    if review_count < 20 and review_count > 0:
        score += weights.get("LOW_REVIEWS", 6)
        signals_hit.append(f"LOW_REVIEWS({review_count})")

    # ── SMALL OPERATOR (5-60 reviews) ──
    if 5 <= review_count <= 60:
        score += weights.get("SMALL_OPERATOR", 8)
        signals_hit.append(f"SMALL_OP({review_count})")
    elif review_count < 5 and review_count > 0:
        score += weights.get("BRAND_NEW", 4)
        signals_hit.append("BRAND_NEW")

    # ── TOO ESTABLISHED (150+ reviews) ──
    if review_count > 150:
        score += weights.get("TOO_ESTABLISHED", -12)
        signals_hit.append("TOO_ESTABLISHED")

    # ── TIER ASSIGNMENT ──
    if score >= 55:
        tier = "SUPERNICHE"
    elif score >= 40:
        tier = "HOT"
    elif score >= 28:
        tier = "WARM"
    else:
        return None

    return {
        **biz,
        "score": score,
        "tier": tier,
        "signals_hit": signals_hit,
        "timing": timing,
        "contact_after": contact_after,
        "capacity_flag": capacity_flag,
        "scored_at": now_utc().isoformat(),
    }


def _load_weights() -> dict:
    """Load scoring weights — uses learned weights if available, else defaults."""
    outcomes_data = load_json(OUTCOMES_FILE, {})
    learned = outcomes_data.get("learned_weights", None)
    if learned and isinstance(learned, dict):
        merged = dict(DEFAULT_WEIGHTS)
        merged.update(learned)
        return merged
    return dict(DEFAULT_WEIGHTS)


# ─────────────────────────────────────────────────────────────────────────────
# 6. MARKETING SEQUENCE (Layer 4)
# ─────────────────────────────────────────────────────────────────────────────

def route_leads(scored_leads: list, suppression: SuppressionList, audit: AuditTrail,
                email_blocked: bool = False):
    """
    Route scored leads through the correct marketing sequence.
    NEVER cold-call as first touch for remote markets.

    Sequence:
    1. Verified email → trigger-matched email first
    2. Textable mobile → trigger-matched text
    3. Neither → expansion-watchlist
    4. Warm auto-call ONLY after 24-48hr delay from first touch
    """
    if check_kill_switch():
        print("[ENGINE] Paused — skipping routing.")
        return

    queued = {"email": 0, "text": 0, "call_queue": 0, "in_person": 0, "watchlist": 0}
    leads_queue = load_json(LEADS_QUEUE_FILE, {"leads": []})

    # Dedup: don't re-queue leads already in queue
    existing_lead_ids = {l.get("lead_id") for l in leads_queue.get("leads", [])}

    for lead in scored_leads:
        phone = lead.get("phone", "")
        ac = lead.get("area_code", "")
        state = lead.get("state", "")
        lead_id = lead.get("lead_id", "")

        # Skip if already in queue
        if lead_id in existing_lead_ids:
            continue

        # Compliance check — pass prior_contact for TCPA gating
        has_prior = lead.get("prior_contact", False)
        compliance = check_compliance(phone, state, suppression, audit, lead_id,
                                      has_prior_contact=has_prior)
        if not compliance["allowed"]:
            continue

        channels = compliance["channels"]
        if email_blocked and "email" in channels:
            channels = [c for c in channels if c != "email"]
        route = _determine_route(lead, channels)

        # Build the queue entry
        queued_now = now_utc().isoformat()

        # Timing layer: use scored timing or default
        timing = lead.get("timing", "immediate")
        contact_after = lead.get("contact_after")
        capacity_flag = lead.get("capacity_flag")

        # Warm-call delay: calls only allowed 24+ hours after first touch
        if route == "call_queue" and not contact_after:
            contact_after = (now_utc() + timedelta(hours=24)).isoformat()

        queue_entry = {
            "lead_id": lead_id,
            "signal_id": lead.get("trigger_signal", {}).get("id", ""),
            "business_name": lead.get("business_name", ""),
            "phone": phone,
            "phone_e164": lead.get("phone_e164", ""),
            "email": lead.get("email", ""),
            "niche": lead.get("niche", ""),
            "city": lead.get("city", ""),
            "area": lead.get("area", ""),
            "state": state,
            "tier": lead.get("tier", ""),
            "score": lead.get("score", 0),
            "signals_hit": lead.get("signals_hit", []),
            "trigger_type": lead.get("trigger_signal", {}).get("type", ""),
            "route": route,
            "timing": timing,
            "contact_after": contact_after,
            "capacity_flag": capacity_flag,
            "trigger_pitch": _build_trigger_pitch(lead),
            "queued_at": queued_now,
            "status": "queued",
            "sequence_step": 1,
        }

        leads_queue["leads"].append(queue_entry)
        queued[route] = queued.get(route, 0) + 1

        # Log the routing decision
        audit.log(
            lead_id=lead_id,
            channel=route,
            trigger_source=lead.get("trigger_signal", {}).get("source", "unknown"),
            suppression_state=False,
            outcome="routed",
            metadata={"tier": lead.get("tier"), "score": lead.get("score")},
        )

    # Expire stale queue entries (30-day TTL for uncontacted)
    cutoff = (now_utc() - timedelta(days=30)).isoformat()
    leads_queue["leads"] = [l for l in leads_queue["leads"]
                            if l.get("queued_at", "") > cutoff or l.get("status") != "queued"]

    # PII purge: redact contacted leads older than 90 days (data minimization)
    pii_cutoff = (now_utc() - timedelta(days=90)).isoformat()
    for lead in leads_queue["leads"]:
        if (lead.get("queued_at", "") < pii_cutoff
                and lead.get("status") not in ("queued", "re_engaged")):
            lead["phone"] = "[REDACTED]"
            lead["email"] = "[REDACTED]"
            lead["business_name"] = "[REDACTED]"

    # Save queue — cap at 200 but preserve high-tier leads
    if len(leads_queue["leads"]) > 200:
        superniche = [l for l in leads_queue["leads"] if l.get("tier") == "SUPERNICHE"]
        hot = [l for l in leads_queue["leads"] if l.get("tier") == "HOT"]
        rest = [l for l in leads_queue["leads"] if l.get("tier") not in ("SUPERNICHE", "HOT")]
        preserved = superniche + hot + rest
        leads_queue["leads"] = preserved[:200]
    leads_queue["last_updated"] = now_utc().isoformat()
    save_json(LEADS_QUEUE_FILE, leads_queue)

    print(f"[ENGINE] Routed leads: email={queued['email']}, text={queued['text']}, "
          f"call_queue={queued['call_queue']}, in_person={queued['in_person']}, "
          f"watchlist={queued['watchlist']}")

    # Alert for genuinely NEW superniche leads (not already in queue before this cycle)
    new_superniche = [l for l in scored_leads
                      if l.get("tier") == "SUPERNICHE"
                      and l.get("lead_id", "") not in existing_lead_ids]
    if new_superniche:
        names = [f"{l.get('niche','service')} in {l.get('state','')} (score {l.get('score',0)})" for l in new_superniche[:5]]
        ntfy(
            f"NEW SUPERNICHE leads ({len(new_superniche)}):\n" + "\n".join(names),
            title="Lead Engine: SUPERNICHE",
            priority="high"
        )


def _determine_route(lead: dict, channels: list) -> str:
    """Determine the routing channel for a lead.

    TCPA COMPLIANCE: No unsolicited texts to numbers without prior consent.
    First touch MUST be email (CAN-SPAM compliant) or in-person.
    Text and call are ONLY for warm follow-up after prior engagement.
    """
    ac = lead.get("area_code", "")

    # In-person queues (East Texas + 850 FL panhandle)
    if ac in IN_PERSON_AC:
        return "in_person"

    # FIRST TOUCH: email only (CAN-SPAM allows unsolicited B2B email)
    if lead.get("email") and lead.get("email_verified") and "email" in channels:
        return "email"

    # If email exists but unverified, still try (with higher bounce risk warning)
    if lead.get("email") and "email" in channels:
        return "email"

    # NO TEXT OR CALL WITHOUT PRIOR ENGAGEMENT (TCPA)
    # Check if this lead has a prior touchpoint (email opened, replied, etc.)
    has_prior_contact = lead.get("prior_contact", False)
    if has_prior_contact:
        if lead.get("line_type") == "likely_mobile" and "text" in channels:
            return "text"
        if "call" in channels and lead.get("tier") in ("SUPERNICHE", "HOT"):
            return "call_queue"

    # No email available, no prior contact = watchlist (need manual/in-person touch)
    return "watchlist"


def _build_trigger_pitch(lead: dict) -> str:
    """Build a personalized pitch hook based on the trigger signal."""
    trigger = lead.get("trigger_signal", {})
    trigger_type = trigger.get("type", "")
    pitch_hook = trigger.get("pitch_hook", "")
    pain = lead.get("pain_keywords", [])
    niche = lead.get("niche", "service")
    name = lead.get("business_name", "your business")
    city = lead.get("area", "your area")

    # Pain review takes priority — it's specific to THIS business
    if pain:
        kw = pain[0]
        if "voicemail" in kw:
            return (f"Saw a review where a customer said they kept getting voicemail "
                    f"when they called {name}. Every one of those is a job that went "
                    f"to a competitor.")
        elif any(w in kw for w in ["answer", "reach", "through"]):
            return (f"I was reading your Google reviews and saw a customer mentioned "
                    f"they couldn't get anyone on the phone. That's customers walking "
                    f"out the door.")
        else:
            return (f"Saw a review where a customer mentioned they had trouble getting "
                    f"through on the phone. That's the exact problem we fix for "
                    f"{niche} businesses.")

    # Weather/disaster trigger
    if trigger_type in ("storm", "flood", "heat_wave", "freeze", "fema_disaster"):
        if pitch_hook:
            return pitch_hook
        return (f"With the recent weather in {city}, {niche} businesses are getting "
                f"slammed with calls. Every missed call is money walking to a competitor.")

    # Hiring signal
    if trigger_type == "hiring_surge":
        return (f"Noticed {niche} businesses in {city} are looking for front desk help. "
                f"We set up an AI phone system that answers every call for $50/month — "
                f"nobody in your family has to play receptionist anymore.")

    # Generic fallback
    return (f"We help {niche} businesses in {city} make sure they never miss a call — "
            f"especially during busy season. $50/month, no contracts.")


def generate_email(lead: dict) -> dict:
    """
    Generate a CAN-SPAM compliant email for a lead.
    Returns dict with subject, body, from, to fields.
    CAN-SPAM requirements met:
    1. Accurate From: Boston Rossall / BOSS Systems
    2. Non-deceptive subject (trigger-matched)
    3. Identified as commercial message
    4. Physical address included
    5. Working opt-out: reply STOP (monitored)
    6. Honor opt-outs within 10 business days (via suppression list)
    7. No third-party sending
    """
    pitch = lead.get("trigger_pitch", _build_trigger_pitch(lead))
    biz_name = lead.get("business_name", "there")
    niche = lead.get("niche", "service")
    city = lead.get("city", "your area")

    # Subject line: trigger-matched, not deceptive
    trigger_type = lead.get("trigger_signal", {}).get("type", "")
    if trigger_type in ("storm", "flood", "heat_wave", "freeze"):
        subject = f"Missed calls during the weather in {city}?"
    elif lead.get("pain_keywords"):
        subject = f"Quick question about {biz_name}'s phone"
    else:
        subject = f"How {niche} businesses in {city} catch missed calls"

    body = f"""Hi,

{pitch}

We built a phone system that answers every call for your business, gives pricing, and books jobs — $50/month flat. No contracts, cancel anytime.

Industry research shows:
- Up to 62% of calls go unanswered during peak hours
- Studies show 85% of callers never call back after voicemail
- Businesses report an average 18% revenue lift in year one

Would a 5-minute call this week make sense? I can show you exactly how it sounds on your line.

- Boston Rossall, BOSS Systems
  bosrossall@gmail.com | (903) 483-0168

---
BOSS Systems | {PHYSICAL_ADDRESS}
This is a commercial message from BOSS Systems.
To opt out of future emails: reply STOP to this email.
Your address will be removed within 5 business days."""

    return {
        "subject": subject,
        "body": body,
        "from_name": "Boston Rossall",
        "from_email": "bosrossall@gmail.com",
        "to_email": lead.get("email", ""),
        "lead_id": lead.get("lead_id", ""),
    }


def generate_text_message(lead: dict) -> str:
    """Generate a trigger-matched text message for warm follow-up ONLY.
    TCPA: This should ONLY be sent to leads with prior express consent
    (replied to email, opted in via website, or gave number during interaction).
    Includes sender ID at start and opt-out at end per A2P requirements.
    """
    if not lead.get("prior_contact"):
        raise ValueError("TCPA: text requires prior_contact=True")
    name = lead.get("business_name", "")
    trigger = lead.get("trigger_signal", {})
    trigger_type = trigger.get("type", "")
    pain = lead.get("pain_keywords", [])

    if pain:
        msg = (f"BOSS Systems: Hey — saw a Google review where a customer "
               f"couldn't reach {name} by phone. We fix that for $50/mo. "
               f"Want a 5 min demo? -Boston")

    elif trigger_type in ("storm", "flood", "heat_wave", "freeze"):
        msg = (f"BOSS Systems: With the weather hitting your area, you're "
               f"probably getting more calls than usual. We make sure you never "
               f"miss one — $50/mo. Quick demo? -Boston")

    else:
        msg = (f"BOSS Systems: Hey — we help businesses like {name} answer "
               f"every call 24/7 for $50/mo. No voicemail, no missed jobs. "
               f"Quick demo? -Boston")

    # TCPA: opt-out footer required
    msg += "\n\nReply STOP to opt out."
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# 7. CLOSED-LOOP LEARNING
# ─────────────────────────────────────────────────────────────────────────────

VALID_OUTCOMES = {
    "meeting_set", "closed", "hangup", "no_answer",
    "opted_out", "wrong_number", "not_interested", "callback",
}

VALID_CONSENT_METHODS = {"email_reply", "form_submit", "in_person", "text_reply", "phone_call"}


def record_consent_event(lead_id: str, method: str):
    """Record a consent event that authorizes text/call channels (TCPA compliance).
    Sets prior_contact=True and stores the consent source + timestamp."""
    if method not in VALID_CONSENT_METHODS:
        print(f"[ENGINE] Invalid consent method '{method}'. Valid: {VALID_CONSENT_METHODS}")
        return
    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    for lead in queue.get("leads", []):
        if lead.get("lead_id") == lead_id:
            lead["prior_contact"] = True
            lead["consent_method"] = method
            lead["consent_timestamp"] = now_utc().isoformat()
            save_json(LEADS_QUEUE_FILE, queue)
            audit = AuditTrail()
            audit.log(lead_id=lead_id, channel=method, trigger_source="consent",
                      suppression_state=False, outcome="consent_recorded",
                      metadata={"method": method})
            print(f"[ENGINE] Consent recorded for {lead_id[:8]}... via {method}")
            return
    print(f"[ENGINE] Lead {lead_id[:8]}... not found in queue.")


def record_outcome(lead_id: str, outcome: str):
    """
    Record the outcome of a contact attempt for a lead.
    Used by the learning loop to reweight signals.
    """
    if outcome not in VALID_OUTCOMES:
        print(f"[ENGINE] Invalid outcome '{outcome}'. Valid: {VALID_OUTCOMES}")
        return

    data = load_json(OUTCOMES_FILE, {"outcomes": [], "learned_weights": None})
    data.setdefault("outcomes", [])

    # Snapshot signals at outcome time (fixes survivorship bias in reweight)
    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    signals_snapshot = []
    for lead in queue.get("leads", []):
        if lead.get("lead_id") == lead_id:
            signals_snapshot = lead.get("signals_hit", [])
            break

    data["outcomes"].append({
        "lead_id": lead_id,
        "outcome": outcome,
        "recorded_at": now_utc().isoformat(),
        "signals_hit": signals_snapshot,
    })

    # Cap at 1000 outcomes
    if len(data["outcomes"]) > 1000:
        data["outcomes"] = data["outcomes"][-1000:]

    save_json(OUTCOMES_FILE, data)

    # Instant ntfy for hot outcomes
    HOT_OUTCOMES = {"meeting_set", "callback", "closed"}
    if outcome in HOT_OUTCOMES:
        biz_name = "Unknown"
        phone = ""
        tier = ""
        for lead in queue.get("leads", []):
            if lead.get("lead_id") == lead_id:
                biz_name = lead.get("business_name", "Unknown")
                phone = lead.get("phone", "")
                tier = lead.get("tier", "")
                break
        phone_fmt = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}" if len(phone) == 10 else phone
        label = {"meeting_set": "MEETING SET", "callback": "CALLBACK REQUESTED", "closed": "CLOSED"}
        ntfy(
            f"{biz_name}\n{phone_fmt}\nTier: {tier}\nSignals: {', '.join(signals_snapshot[:4])}\n\nCall them NOW before they go cold.",
            title=f"{label.get(outcome, outcome.upper())} — {biz_name}",
            priority="urgent",
        )

    # Auto-suppress opted_out and wrong_number
    if outcome in ("opted_out", "wrong_number"):
        suppression = SuppressionList()
        for lead in queue.get("leads", []):
            if lead.get("lead_id") == lead_id:
                suppression.add(outcome, phone=lead.get("phone", ""),
                                name=lead.get("business_name", ""))
                break

    print(f"[ENGINE] Recorded outcome '{outcome}' for lead {lead_id[:8]}...")


def reweight_scoring():
    """
    Analyze outcomes to find which signals correlate with positive results
    (meeting_set, closed) vs negative (hangup, not_interested, opted_out).
    Adjusts scoring weights accordingly.

    Triggered by Sunday Optimizer or manually via `lead_engine.py reweight`.
    """
    if check_kill_switch():
        print("[ENGINE] Paused — skipping reweight.")
        return

    _backup_engine_state()

    data = load_json(OUTCOMES_FILE, {"outcomes": [], "learned_weights": None})
    outcomes = data.get("outcomes", [])

    if len(outcomes) < 15:
        print(f"[ENGINE] Not enough outcomes to reweight (need 15+, have {len(outcomes)}).")
        return

    # Fallback: load queue for outcomes that lack embedded signals
    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    leads_by_id = {l["lead_id"]: l for l in queue.get("leads", [])}

    positive_outcomes = {"meeting_set", "closed"}
    negative_outcomes = {"hangup", "not_interested", "opted_out"}

    signal_positive = {}
    signal_negative = {}
    signal_total = {}
    total_pos = 0
    total_neg = 0

    for entry in outcomes:
        lead_id = entry.get("lead_id", "")
        outcome = entry.get("outcome", "")

        # Use embedded signals snapshot; fall back to queue lookup
        signals = entry.get("signals_hit")
        if not signals:
            lead = leads_by_id.get(lead_id)
            if not lead:
                continue
            signals = lead.get("signals_hit", [])

        is_pos = outcome in positive_outcomes
        is_neg = outcome in negative_outcomes
        if is_pos:
            total_pos += 1
        elif is_neg:
            total_neg += 1
        else:
            continue

        for sig in signals:
            sig_name = sig.split("(")[0].strip()
            signal_total[sig_name] = signal_total.get(sig_name, 0) + 1
            if is_pos:
                signal_positive[sig_name] = signal_positive.get(sig_name, 0) + 1
            elif is_neg:
                signal_negative[sig_name] = signal_negative.get(sig_name, 0) + 1

    base_rate = total_pos / max(total_pos + total_neg, 1)
    # Start from previously learned weights to accumulate learning across cycles
    prior_learned = data.get("learned_weights")
    learned_weights = dict(DEFAULT_WEIGHTS)
    if prior_learned and isinstance(prior_learned, dict):
        learned_weights.update(prior_learned)

    for sig_name, total in signal_total.items():
        if total < 15:
            continue

        pos = signal_positive.get(sig_name, 0)
        neg = signal_negative.get(sig_name, 0)
        decided = pos + neg
        if decided < 5:
            continue

        # Bayesian smoothing: beta-binomial prior centered on base rate
        prior_n = 10
        prior_pos = prior_n * base_rate
        smoothed_rate = (pos + prior_pos) / (decided + prior_n)

        weight_key = _signal_to_weight_key(sig_name)
        if not weight_key:
            continue

        base_weight = DEFAULT_WEIGHTS.get(weight_key, 0)
        if base_weight == 0:
            continue

        # Relative threshold: boost if 1.5x base rate, reduce if 0.5x
        max_adjust = max(1, int(abs(base_weight) * 0.25))
        confidence = min(1.0, decided / 30.0)

        if base_rate > 0 and smoothed_rate > base_rate * 1.5:
            adjustment = int(max_adjust * confidence)
            learned_weights[weight_key] = base_weight + adjustment
        elif base_rate > 0 and smoothed_rate < base_rate * 0.5:
            adjustment = int(max_adjust * confidence)
            learned_weights[weight_key] = base_weight - adjustment

    # Save learned weights
    data["learned_weights"] = learned_weights
    data["last_reweight"] = now_utc().isoformat()
    data["reweight_sample_size"] = len(outcomes)
    save_json(OUTCOMES_FILE, data)

    print(f"[ENGINE] Reweighted scoring from {len(outcomes)} outcomes.")
    print(f"  Signals analyzed: {len(signal_total)}")

    # Report significant changes
    changes = []
    for key in learned_weights:
        if learned_weights[key] != DEFAULT_WEIGHTS.get(key, 0):
            changes.append(f"  {key}: {DEFAULT_WEIGHTS.get(key, 0)} → {learned_weights[key]}")
    if changes:
        print("  Weight changes:")
        for c in changes:
            print(c)


def _signal_to_weight_key(sig_name: str) -> str:
    """Map a signal hit name to its weight dictionary key."""
    mapping = {
        "ATLAS_WEATHER": "ATLAS_TRIGGER_WEATHER",
        "ATLAS_PAIN": "ATLAS_TRIGGER_PAIN",
        "ATLAS_ECON": "ATLAS_TRIGGER_ECONOMIC",
        "PAIN_REVIEW": "PAIN_REVIEW",
        "MULTIPLE_PAIN": "MULTIPLE_PAIN",
        "TIER1_NICHE": "TIER1_NICHE",
        "TIER2_NICHE": "TIER2_NICHE",
        "WEAK_RATING": "WEAK_RATING",
        "WEAK_RATING_REACH": "WEAK_RATING_REACHABILITY",
        "NO_WEBSITE": "NO_WEBSITE",
        "NO_CAPACITY_SURGE": "ACTIVE_SURGE_PENALTY",
        "HVAC_PEAK": "HVAC_PEAK",
        "LOW_REVIEWS": "LOW_REVIEWS",
        "RECENT_NEGATIVE": "RECENT_NEGATIVE",
        "SMALL_OP": "SMALL_OPERATOR",
        "BRAND_NEW": "BRAND_NEW",
        "TOO_ESTABLISHED": "TOO_ESTABLISHED",
        "HIRING_SIGNAL": "HIRING_SIGNAL",
    }
    return mapping.get(sig_name, "")


def check_reengagement():
    """
    Check if any previously-contacted lead has a NEW trigger signal.
    If so, bump them back into the funnel with the new trigger as context.
    Re-engagement only if last contact was 14+ days ago.
    """
    if check_kill_switch():
        return []

    audit = AuditTrail()
    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    leads_by_id = {l["lead_id"]: l for l in queue.get("leads", [])}

    # Get current signals
    signals = ingest_signals()
    if not signals:
        return []

    reengaged = []

    for lead_id, lead in leads_by_id.items():
        if lead.get("status") in ("closed", "opted_out", "not_interested"):
            continue

        last_contact = audit.get_last_contact(lead_id)
        if not last_contact:
            continue

        last_time = datetime.fromisoformat(last_contact["timestamp"])
        days_since = (now_utc() - last_time).days

        if days_since < 14:
            continue

        # Check if there's a new relevant signal for this lead's area/niche
        lead_state = lead.get("state", "")
        lead_niche = lead.get("niche", "")

        for sig in signals:
            sig_states = sig.get("geo", {}).get("states", [])
            sig_niche = sig.get("niche", "multi")

            if lead_state in sig_states and (sig_niche == "multi" or sig_niche == lead_niche):
                # New trigger! Re-engage this lead
                lead["trigger_signal"] = sig
                lead["status"] = "re_engaged"
                lead["re_engaged_at"] = now_utc().isoformat()
                lead["re_engagement_reason"] = f"New {sig['type']} signal in {sig.get('area', 'area')}"
                reengaged.append(lead)
                break

    if reengaged:
        # Save updated queue
        queue["leads"] = list(leads_by_id.values())
        save_json(LEADS_QUEUE_FILE, queue)
        print(f"[ENGINE] Re-engaged {len(reengaged)} leads with new triggers.")

    return reengaged


# ─────────────────────────────────────────────────────────────────────────────
# 7b. PIPELINE SYNC + RETELL OUTCOME SYNC
# ─────────────────────────────────────────────────────────────────────────────


def sync_to_pipeline():
    """Push call-ready leads from leads_queue.json to the Auto Caller Pipeline
    (Google Sheets) via n8n webhook. Only syncs leads not already synced."""
    if check_kill_switch():
        print("[ENGINE] Paused — skipping pipeline sync.")
        return 0

    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    leads = queue.get("leads", [])
    now = now_utc()

    ready = []
    for lead in leads:
        if lead.get("status") not in ("queued", "re_engaged"):
            continue
        if lead.get("synced_to_pipeline"):
            continue

        contact_after = lead.get("contact_after")
        if contact_after:
            try:
                ca_dt = datetime.fromisoformat(contact_after)
                if ca_dt > now:
                    continue
            except (ValueError, TypeError):
                pass

        route = lead.get("route", "")
        if route in ("call_queue", "in_person", "email", "text"):
            ready.append(lead)

    if not ready:
        print("[ENGINE] No new leads to sync to pipeline.")
        return 0

    synced = 0
    for lead in ready[:50]:
        payload = {
            "business_name": lead.get("business_name", ""),
            "phone": lead.get("phone", ""),
            "phone_e164": lead.get("phone_e164", ""),
            "email": lead.get("email", ""),
            "niche": lead.get("niche", ""),
            "city": lead.get("area", ""),
            "state": lead.get("state", ""),
            "tier": lead.get("tier", ""),
            "score": lead.get("score", 0),
            "route": lead.get("route", ""),
            "pain_signal": ", ".join(lead.get("pain_keywords", lead.get("signals_hit", []))[:2]),
            "opener": lead.get("trigger_pitch", ""),
            "status": "cold",
            "lead_id": lead.get("lead_id", ""),
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(PIPELINE_SYNC_WEBHOOK, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urllib.request.urlopen(req, timeout=8)
            if resp.status in (200, 201):
                lead["synced_to_pipeline"] = True
                lead["synced_at"] = now_utc().isoformat()
                synced += 1
        except Exception as e:
            print(f"[ENGINE] Pipeline sync failed for {lead.get('business_name', '?')}: {e}")

    save_json(LEADS_QUEUE_FILE, queue)
    print(f"[ENGINE] Synced {synced}/{len(ready)} leads to Pipeline.")

    if synced > 0:
        ntfy(f"Synced {synced} leads to Auto Caller pipeline.",
             title="Pipeline Sync", priority="default")

    return synced


def sync_retell_outcomes():
    """Pull call outcomes from Retell API and record them against leads in queue.
    Closes the feedback loop: call results → outcomes.json → reweight_scoring()."""
    if not RETELL_API_KEY:
        print("[ENGINE] No RETELL_API_KEY — skipping outcome sync.")
        return 0

    # Outcome sync runs even when engine is paused — calls already made
    # still need their results tracked and Boston notified

    since_ms = int((now_utc() - timedelta(days=7)).timestamp() * 1000)

    try:
        payload = json.dumps({
            "filter_criteria": {"after_start_timestamp": since_ms},
            "limit": 100,
            "sort_order": "descending",
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.retellai.com/v2/list-calls",
            data=payload, method="POST",
        )
        req.add_header("Authorization", f"Bearer {RETELL_API_KEY}")
        req.add_header("Content-Type", "application/json")

        resp = urllib.request.urlopen(req, timeout=15)
        raw = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[ENGINE] Retell API error: {e}")
        return 0

    calls = raw if isinstance(raw, list) else raw.get("calls", raw.get("data", []))
    if not isinstance(calls, list):
        print(f"[ENGINE] Unexpected Retell response format.")
        return 0

    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    phone_to_lead = {}
    for lead in queue.get("leads", []):
        phone = lead.get("phone", "")
        if phone:
            phone_to_lead[phone] = lead.get("lead_id", "")
            phone_to_lead[f"+1{phone}"] = lead.get("lead_id", "")

    outcomes_data = load_json(OUTCOMES_FILE, {"outcomes": [], "learned_weights": None})
    recorded_ids = {o.get("retell_call_id") for o in outcomes_data.get("outcomes", [])
                    if o.get("retell_call_id")}

    matched = 0
    for call in calls:
        call_id = call.get("call_id", "")
        if call_id in recorded_ids:
            continue

        to_number = call.get("to_number", "")
        from_number = call.get("from_number", "")
        target_phone = to_number if call.get("direction") == "outbound" else from_number
        digits = "".join(c for c in target_phone if c.isdigit())
        if len(digits) == 11 and digits[0] == "1":
            digits = digits[1:]

        lead_id = phone_to_lead.get(digits) or phone_to_lead.get(target_phone)
        if not lead_id:
            continue

        status = call.get("call_status", "")
        start_ts = call.get("start_timestamp", 0) or 0
        end_ts = call.get("end_timestamp", 0) or 0
        duration_sec = (end_ts - start_ts) / 1000 if end_ts > start_ts else 0
        disconnection = call.get("disconnection_reason", "")

        if status != "ended":
            outcome = "no_answer"
        elif duration_sec < 10:
            outcome = "no_answer"
        else:
            transcript = call.get("transcript", "")
            if isinstance(transcript, list):
                transcript = " ".join(t.get("content", "") for t in transcript if isinstance(t, dict))
            t_lower = transcript.lower() if isinstance(transcript, str) else ""

            neg = ["not interested", "don't call", "stop calling", "do not call",
                   "take me off", "remove me", "no thanks", "we're good"]
            pos = ["email", "send me", "interested", "tell me more",
                   "schedule", "appointment", "call me back", "sounds good"]

            if any(s in t_lower for s in neg):
                outcome = "not_interested"
            elif any(s in t_lower for s in pos):
                outcome = "meeting_set"
            elif duration_sec < 30:
                outcome = "hangup"
            else:
                outcome = "callback"

        record_outcome(lead_id, outcome)

        outcomes_data = load_json(OUTCOMES_FILE, {"outcomes": [], "learned_weights": None})
        if outcomes_data["outcomes"]:
            outcomes_data["outcomes"][-1]["retell_call_id"] = call_id
            outcomes_data["outcomes"][-1]["call_duration_sec"] = round(duration_sec, 1)
            save_json(OUTCOMES_FILE, outcomes_data)

        matched += 1

    print(f"[ENGINE] Synced {matched} call outcomes from Retell.")
    return matched


def ingest_prospect_targets():
    """Read pre-scored targets from prospect_scorer.py (prospect_targets.json)
    and merge into leads_queue. Avoids duplicate API spend since prospect_scorer
    already resolved businesses via Google Places."""
    if check_kill_switch():
        return []

    if not PROSPECT_TARGETS_FILE.exists():
        return []

    targets = load_json(PROSPECT_TARGETS_FILE, {"targets": [], "ingested_ids": []})
    if not isinstance(targets, dict):
        return []

    target_list = targets.get("targets", [])
    ingested_ids = set(targets.get("ingested_ids", []))

    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    existing_phones = {l.get("phone") for l in queue.get("leads", [])}
    suppression = SuppressionList()

    new_leads = []
    for t in target_list:
        phone = t.get("phone", "")
        if not phone or phone in existing_phones:
            continue
        if t.get("id", phone) in ingested_ids:
            continue
        if suppression.is_suppressed(phone=phone, name=t.get("name", "")):
            continue

        ac = phone[:3]
        if ac in BANNED_AC:
            continue

        state = _ac_to_state(ac)
        lead_id = generate_lead_id(phone, t.get("name", ""))

        queue_entry = {
            "lead_id": lead_id,
            "signal_id": f"prospect_scorer_{phone}",
            "business_name": t.get("name", ""),
            "phone": phone,
            "phone_e164": t.get("phone_e164", f"+1{phone}"),
            "email": "",
            "niche": t.get("niche", ""),
            "city": t.get("city", ""),
            "area": t.get("city", ""),
            "state": state,
            "tier": t.get("tier", "HOT"),
            "score": t.get("score", 40),
            "signals_hit": t.get("signals", []),
            "trigger_type": "prospect_scorer",
            "route": "in_person" if ac in IN_PERSON_AC else "call_queue",
            "timing": "immediate",
            "contact_after": None,
            "capacity_flag": None,
            "trigger_pitch": t.get("opener", ""),
            "queued_at": now_utc().isoformat(),
            "status": "queued",
            "sequence_step": 1,
            "pain_keywords": t.get("pain", []),
        }
        queue["leads"].append(queue_entry)
        new_leads.append(queue_entry)
        ingested_ids.add(t.get("id", phone))

    if new_leads:
        queue["last_updated"] = now_utc().isoformat()
        save_json(LEADS_QUEUE_FILE, queue)
        targets["ingested_ids"] = list(ingested_ids)
        save_json(PROSPECT_TARGETS_FILE, targets)
        print(f"[ENGINE] Ingested {len(new_leads)} targets from prospect_scorer.")

    return new_leads


def ingest_scraped_leads():
    """Read pre-scraped email leads from leads_ready.json (written by
    scrape_email_leads.py) and merge into leads_queue. These already have
    phone + email from Google Places + website scraping."""
    if check_kill_switch():
        return []

    if not SCRAPED_LEADS_FILE.exists():
        return []

    raw = load_json(SCRAPED_LEADS_FILE, {})
    scraped = raw.get("leads_ready", [])
    if not scraped:
        return []

    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    existing_phones = {l.get("phone") for l in queue.get("leads", [])}
    suppression = SuppressionList()

    new_leads = []
    for s in scraped:
        phone = s.get("phone", "")
        if not phone or phone in existing_phones:
            continue
        if suppression.is_suppressed(phone=phone, name=s.get("business_name", "")):
            continue

        ac = phone[:3]
        if ac in BANNED_AC:
            continue

        state = s.get("state", _ac_to_state(ac))
        lead_id = generate_lead_id(phone, s.get("business_name", ""))

        queue_entry = {
            "lead_id": lead_id,
            "signal_id": f"scraped_{phone}",
            "business_name": s.get("business_name", ""),
            "phone": phone,
            "phone_e164": f"+1{phone}",
            "email": s.get("email", ""),
            "niche": s.get("niche", ""),
            "city": s.get("city", ""),
            "area": s.get("city", ""),
            "state": state,
            "tier": s.get("tier", "WARM"),
            "score": s.get("score", 40),
            "signals_hit": s.get("signals", []),
            "trigger_type": "email_scraper",
            "route": "email" if s.get("email") else ("in_person" if ac in IN_PERSON_AC else "call_queue"),
            "timing": s.get("timing", "immediate"),
            "contact_after": None,
            "capacity_flag": None,
            "trigger_pitch": s.get("pitch", ""),
            "queued_at": now_utc().isoformat(),
            "status": "queued",
            "sequence_step": 1,
            "pain_keywords": s.get("signals", []),
        }
        queue["leads"].append(queue_entry)
        new_leads.append(queue_entry)
        existing_phones.add(phone)

    if new_leads:
        queue["last_updated"] = now_utc().isoformat()
        save_json(LEADS_QUEUE_FILE, queue)
        print(f"[ENGINE] Ingested {len(new_leads)} scraped email leads from leads_ready.json.")

    return new_leads


# ─────────────────────────────────────────────────────────────────────────────
# 8. MAIN ENTRY POINTS
# ─────────────────────────────────────────────────────────────────────────────

def _backup_engine_state():
    """Snapshot critical engine state files before mutations."""
    import shutil
    backup_dir = BASE_DIR / "backups" / f"engine_state_{now_utc().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for f in [LEADS_QUEUE_FILE, SPEND_FILE, SUPPRESSION_FILE, AUDIT_FILE,
              OUTCOMES_FILE, ENGINE_STATE_FILE]:
        try:
            if f.exists():
                shutil.copy2(f, backup_dir / f.name)
        except (IOError, OSError) as e:
            ntfy(f"Backup failed: {f.name}: {e}", title="Backup Error", priority="high")


def run_full_cycle():
    """
    Full lead engine cycle:
    1. Ingest signals from ATLAS
    2. Scan new sources
    3. Resolve businesses via Google Places
    4. Score all leads
    5. Route through marketing sequence
    6. Check re-engagement
    """
    try:
        _run_full_cycle_inner()
    except Exception as e:
        ntfy(f"Engine CRASHED: {type(e).__name__}: {e}",
             title="ENGINE CRASH", priority="urgent")
        raise


def _run_full_cycle_inner():
    print("=" * 66)
    print("  BOSS LEAD ENGINE — Full Cycle")
    print(f"  {now_ct().strftime('%Y-%m-%d %I:%M %p CT')}")
    print("=" * 66)

    if check_kill_switch():
        print("\n  ENGINE IS PAUSED. Run 'lead_engine.py resume' to restart.")
        return

    _backup_engine_state()

    # Initialize systems
    spend = SpendTracker()
    breaker = CircuitBreaker()
    suppression = SuppressionList()
    audit = AuditTrail()

    # Check spend before doing anything
    if spend.is_hard_stopped:
        print("\n  HARD STOP: Google Places spend at 80%+. Cannot run discovery.")
        print(f"  Spent: ${spend.total_spent:.2f} / ${TOTAL_CREDIT}")
        return

    # Pre-flight: Sync outcomes from Retell (feeds learning loop)
    print("\n── Pre-flight: Retell Outcome Sync ──")
    outcome_count = sync_retell_outcomes()
    print(f"  Synced {outcome_count} call outcomes from Retell.")

    # Layer 1: Signal Ingestion
    print("\n── Layer 1: Signal Ingestion ──")
    signals = ingest_signals()
    new_signals = scan_new_sources()

    # Ingest prospect_scorer targets (pre-resolved, no API spend)
    prospect_targets = ingest_prospect_targets()
    if prospect_targets:
        print(f"  Prospect scorer targets ingested: {len(prospect_targets)}")

    # Ingest scraped email leads (pre-resolved, no API spend)
    scraped_leads = ingest_scraped_leads()
    if scraped_leads:
        print(f"  Scraped email leads ingested: {len(scraped_leads)}")

    # Market sweep: systematic city/trade search independent of signals
    sweep_signals = generate_sweep_signals()

    all_signals = signals + new_signals + sweep_signals
    print(f"  Total signals: {len(all_signals)} ({len(signals)} ATLAS + {len(new_signals)} sources + {len(sweep_signals)} sweep)")

    if not all_signals:
        print("  No actionable signals. Checking re-engagement...")
        reengaged = check_reengagement()
        if reengaged:
            print(f"  Re-engaged {len(reengaged)} leads.")
        else:
            print("  Nothing to do this cycle.")
        return

    # Layer 2: Business Resolution
    print("\n── Layer 2: Business Resolution ──")
    businesses = resolve_businesses(all_signals, spend, breaker, suppression)
    if not businesses:
        print("  No businesses resolved. May be spend-limited or no matches.")
        return

    # Layer 3: Scoring
    print("\n── Layer 3: Scoring ──")
    scored = score_leads(businesses, all_signals)
    if not scored:
        print("  No leads met scoring threshold.")
        return

    # Pre-flight: Email domain audit
    print("\n── Pre-flight: Email Domain Audit ──")
    email_ok = preflight_email_audit()
    if email_ok:
        print("  Sending domain (Gmail): SPF/MX verified. Safe to send.")
    else:
        print("  WARNING: Email blocked. All leads routed to text/in-person.")

    # Layer 4: Routing
    print("\n── Layer 4: Routing ──")
    route_leads(scored, suppression, audit, email_blocked=not email_ok)

    # Layer 5: Contact Sequence Generation
    print("\n── Layer 5: Contact Sequence ──")
    try:
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        from contact_sequence import generate_batch as _cs_generate
        emails, postcards = _cs_generate()
        print(f"  Emails queued: {len(emails)}")
        if postcards:
            print(f"  Postcards flagged for Boston: {len(postcards)}")
    except Exception as e:
        print(f"  Contact sequence skipped: {e}")

    # Pipeline sync — push call-ready leads to Auto Caller
    print("\n── Pipeline Sync ──")
    synced_count = sync_to_pipeline()
    print(f"  Synced {synced_count} leads to Auto Caller pipeline.")

    # Re-engagement check
    print("\n── Re-engagement Check ──")
    reengaged = check_reengagement()

    # Final status
    print("\n── Cycle Complete ──")
    print(f"  Signals: {len(all_signals)}")
    print(f"  Businesses found: {len(businesses)}")
    print(f"  Leads scored: {len(scored)}")
    print(f"  Synced to pipeline: {synced_count}")
    print(f"  Call outcomes synced: {outcome_count}")
    print(f"  Re-engaged: {len(reengaged)}")
    print(f"  API spend this session: ${spend.total_spent:.2f} / ${TOTAL_CREDIT}")
    print(f"  Suppression list: {suppression.count} entries")
    print(f"  Audit trail: {audit.count} entries")
    print("=" * 66)

    # Only notify when new leads were actually scored this cycle
    if scored:
        queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
        ntfy(
            f"Cycle done: {len(scored)} NEW leads scored, "
            f"{len(queue.get('leads', []))} total in queue, ${spend.total_spent:.2f} spent",
            title="New Leads Found",
            priority="default",
        )


def run_discover():
    """Signal ingestion + new source discovery only. No API spend."""
    print("=" * 66)
    print("  BOSS LEAD ENGINE — Discovery Mode")
    print(f"  {now_ct().strftime('%Y-%m-%d %I:%M %p CT')}")
    print("=" * 66)

    if check_kill_switch():
        print("\n  ENGINE IS PAUSED.")
        return

    print("\n── Signal Ingestion ──")
    signals = ingest_signals()

    print("\n── New Source Scan ──")
    new_signals = scan_new_sources()

    all_signals = signals + new_signals
    print(f"\n  Total signals discovered: {len(all_signals)}")

    if all_signals:
        # Group by type
        by_type = {}
        for s in all_signals:
            t = s.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        print("  Breakdown:")
        for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"    {t}: {count}")

        # Show top 5 signals
        print("\n  Top signals:")
        for s in all_signals[:5]:
            print(f"    [{s['type']}] {s.get('area', 'N/A')} — {s.get('niche', 'N/A')}")
            if s.get("pitch_hook"):
                print(f"      Hook: {s['pitch_hook'][:80]}")

    print("=" * 66)


def print_status():
    """Print complete engine status."""
    print("=" * 66)
    print("  BOSS LEAD ENGINE — Status")
    print(f"  {now_ct().strftime('%Y-%m-%d %I:%M %p CT')}")
    print("=" * 66)

    # Kill switch
    state = load_json(ENGINE_STATE_FILE, {"paused": False})
    paused = state.get("paused", False)
    print(f"\n  Engine State: {'PAUSED' if paused else 'ACTIVE'}")
    if paused:
        print(f"  Paused at: {state.get('updated_at', 'unknown')}")

    # Spend tracker
    spend = SpendTracker()
    s = spend.status()
    print(f"\n  API Spend:")
    print(f"    Total: ${s['total_spent']:.2f} / ${TOTAL_CREDIT:.2f} ({s['percent_used']}%)")
    print(f"    Remaining: ${s['credit_remaining']:.2f}")
    print(f"    Today: ${s['daily_spent']:.2f} / ${s['daily_budget']:.2f} {'(CAPPED)' if s['daily_capped'] else ''}")
    print(f"    This week: ${s['weekly_spent']:.2f} / ${s['weekly_budget']:.2f} {'(CAPPED)' if s['weekly_capped'] else ''}")
    print(f"    Throttled: {s['throttled']}")
    print(f"    Hard-stopped: {s['hard_stopped']}")
    print(f"    Credit expires: {s['credit_expiry'][:10]}")
    print(f"    Total requests: {s['total_requests']}")

    # Circuit breakers
    breaker = CircuitBreaker()
    breaker_status = breaker.status()
    if breaker_status:
        print(f"\n  Circuit Breakers:")
        for svc, info in breaker_status.items():
            status = "OPEN (cooling)" if info["tripped"] else "closed"
            print(f"    {svc}: {status} (failures: {info['failures']})")
    else:
        print(f"\n  Circuit Breakers: All closed (no failures)")

    # Suppression list
    suppression = SuppressionList()
    print(f"\n  Suppression List: {suppression.count} entries")
    print(f"    Phones: {len(suppression.data.get('phones', []))}")
    print(f"    Emails: {len(suppression.data.get('emails', []))}")
    print(f"    Names: {len(suppression.data.get('business_names', []))}")

    # Leads queue
    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    leads = queue.get("leads", [])
    print(f"\n  Leads Queue: {len(leads)} total")
    if leads:
        by_tier = {}
        by_route = {}
        by_status = {}
        for l in leads:
            t = l.get("tier", "unknown")
            r = l.get("route", "unknown")
            st = l.get("status", "unknown")
            by_tier[t] = by_tier.get(t, 0) + 1
            by_route[r] = by_route.get(r, 0) + 1
            by_status[st] = by_status.get(st, 0) + 1

        print(f"    By tier: {by_tier}")
        print(f"    By route: {by_route}")
        print(f"    By status: {by_status}")

    # Audit trail
    audit = AuditTrail()
    print(f"\n  Audit Trail: {audit.count} entries")

    # Outcomes
    outcomes_data = load_json(OUTCOMES_FILE, {"outcomes": []})
    outcomes = outcomes_data.get("outcomes", [])
    print(f"\n  Outcomes Recorded: {len(outcomes)}")
    if outcomes:
        by_outcome = {}
        for o in outcomes:
            oc = o.get("outcome", "unknown")
            by_outcome[oc] = by_outcome.get(oc, 0) + 1
        print(f"    Breakdown: {by_outcome}")

    # Learned weights
    learned = outcomes_data.get("learned_weights")
    if learned:
        print(f"\n  Learned Weights: Active (last reweight: {outcomes_data.get('last_reweight', 'unknown')})")
    else:
        print(f"\n  Learned Weights: Using defaults (no reweight yet)")

    # ATLAS intel freshness
    intel = load_json(BOSS_INTEL_FILE, {})
    if intel:
        gen = intel.get("generated", "")
        print(f"\n  ATLAS Intel: Generated {gen}")
        print(f"    Heat Score: {intel.get('boss_heat_score', 0)}/100")
        print(f"    Demand Signals: {len(intel.get('demand_signals', []))}")
        print(f"    Pain Signals: {len(intel.get('pain_signals', []))}")
    else:
        print(f"\n  ATLAS Intel: No data available")

    print("\n" + "=" * 66)


def cmd_pause():
    """Activate the kill switch."""
    set_engine_state(paused=True)
    print("[ENGINE] PAUSED. All operations halted.")
    ntfy("Lead Engine PAUSED by manual command.", title="Engine Paused")


def cmd_resume():
    """Deactivate the kill switch."""
    set_engine_state(paused=False)
    print("[ENGINE] RESUMED. Operations active.")
    ntfy("Lead Engine RESUMED.", title="Engine Resumed")


def cmd_reweight():
    """Manually trigger the learning loop."""
    print("[ENGINE] Running reweight...")
    reweight_scoring()


def export_report():
    """Generate engine_report.json for the dashboard and push to GitHub."""
    state = load_json(ENGINE_STATE_FILE, {"paused": False})
    spend = SpendTracker()
    suppression = SuppressionList()
    intel_data = load_json(BOSS_INTEL_FILE, {})
    queue = load_json(LEADS_QUEUE_FILE, {"leads": []})
    leads = queue.get("leads", [])
    outcomes_data = load_json(OUTCOMES_FILE, {"outcomes": []})
    outcomes = outcomes_data.get("outcomes", [])
    audit_data = load_json(AUDIT_FILE, {"entries": []})

    signals = intel_data.get("demand_signals", []) + intel_data.get("pain_signals", [])

    # Build feeds from ATLAS
    feeds = []
    atlas_report = load_json(ATLAS_DIR / "latest.json", {})
    if atlas_report:
        source_names = ["noaa", "reddit", "usgs", "hackernews", "fema", "commodities", "rss", "fred", "bls"]
        for src in source_names:
            data = atlas_report.get(src, [])
            feeds.append({
                "name": src.upper(),
                "last_hit": atlas_report.get("generated", ""),
                "status": "green" if data else "yellow",
                "data_points_today": len(data) if isinstance(data, list) else 0
            })

    # Channel stats from outcomes
    channels = {"emails_sent": 0, "texts_sent": 0, "calls_made": 0, "meetings_set": 0, "closes": 0}
    for entry in audit_data.get("entries", []):
        ch = entry.get("channel", "")
        if ch == "email": channels["emails_sent"] += 1
        elif ch == "text": channels["texts_sent"] += 1
        elif ch == "call": channels["calls_made"] += 1
    for o in outcomes:
        if o.get("outcome") == "meeting_set": channels["meetings_set"] += 1
        elif o.get("outcome") == "closed": channels["closes"] += 1

    sn = sum(1 for l in leads if l.get("tier") == "SUPERNICHE")
    report = {
        "generated": now_utc().isoformat(),
        "engine_state": "paused" if state.get("paused") else "active",
        "signals": signals[:20],
        "leads": [{"name": l.get("niche", "service"), "city": l.get("state", ""),
                   "score": l.get("score", 0), "tier": l.get("tier", ""),
                   "channel": l.get("route", ""),
                   "sequence_status": l.get("status", "queued"),
                   "trigger": l.get("trigger_type", "")}
                  for l in sorted(leads, key=lambda x: -x.get("score", 0))[:15]],
        "kpis": {
            "signals_firing": len(signals),
            "leads_superniche": sn,
            "leads_hot": sum(1 for l in leads if l.get("tier") == "HOT"),
            "leads_warm": sum(1 for l in leads if l.get("tier") == "WARM"),
            "cost_per_qualified": round(spend.total_spent / max(sn, 1), 2),
            "total_spend": spend.total_spent,
            "spend_cap": TOTAL_CREDIT,
        },
        "channels": channels,
        "feeds": feeds,
        "conversion_funnel": {
            "signals": len(signals),
            "leads": len(leads),
            "contacted": channels["emails_sent"] + channels["texts_sent"] + channels["calls_made"],
            "replied": channels["meetings_set"] + channels["closes"],
            "meeting": channels["meetings_set"],
            "close": channels["closes"],
        },
    }

    report_path = ATLAS_DIR / "engine_report.json"
    save_json(report_path, report)
    print(f"[ENGINE] Report exported: {len(leads)} leads, {len(signals)} signals, ${spend.total_spent:.2f} spent")

    # Push to GitHub
    github_token = os.environ.get("GITHUB_TOKEN", "")
    github_repo = os.environ.get("GITHUB_REPO", "BosRoss/bosssystems.co")
    if github_token:
        import base64 as b64_mod
        content = json.dumps(report, indent=2, default=str)
        encoded = b64_mod.b64encode(content.encode()).decode()
        gh_headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        api_url = f"https://api.github.com/repos/{github_repo}/contents/engine_report.json"
        try:
            req = urllib.request.Request(api_url, headers=gh_headers)
            resp = urllib.request.urlopen(req, timeout=10)
            sha = json.loads(resp.read().decode()).get("sha")
        except Exception:
            sha = None
        payload = {"message": "Lead Engine report update", "content": encoded, "branch": "main"}
        if sha:
            payload["sha"] = sha
        try:
            put_data = json.dumps(payload).encode()
            req2 = urllib.request.Request(api_url, data=put_data, headers=gh_headers, method="PUT")
            req2.add_header("Content-Type", "application/json")
            resp2 = urllib.request.urlopen(req2, timeout=10)
            if resp2.status in (200, 201):
                print("[ENGINE] Report pushed to GitHub.")
            else:
                print(f"[ENGINE] GitHub push failed: {resp2.status}")
        except Exception as e:
            print(f"[ENGINE] GitHub push error: {e}")
    else:
        print("[ENGINE] No GITHUB_TOKEN — report saved locally only.")

    return report


# ─────────────────────────────────────────────────────────────────────────────
# CLI INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

def print_usage():
    print("""
BOSS Lead Engine — Autonomous Lead Discovery & Routing
======================================================

Usage:
  python3 lead_engine.py run         Full cycle (ingest → resolve → score → route)
  python3 lead_engine.py discover    Signal ingestion + source discovery only
  python3 lead_engine.py status      Print engine state and stats
  python3 lead_engine.py pause       Halt all operations (kill switch)
  python3 lead_engine.py resume      Resume operations
  python3 lead_engine.py reweight    Trigger scoring learning loop

  python3 lead_engine.py sync          Push call-ready leads to Auto Caller pipeline
  python3 lead_engine.py outcomes      Pull call outcomes from Retell API
  python3 lead_engine.py ingest-scraped  Import scraped email leads from leads_ready.json

  python3 lead_engine.py outcome <lead_id> <outcome>
      Record an outcome. Valid outcomes:
      meeting_set, closed, hangup, no_answer,
      opted_out, wrong_number, not_interested, callback

  python3 lead_engine.py suppress <phone> [reason]
      Add a phone to the suppression list

  python3 lead_engine.py consent <lead_id> <method>
      Record a consent event (TCPA). Valid methods:
      email_reply, form_submit, in_person, text_reply, phone_call

Environment Variables:
  GOOGLE_PLACES_KEY   Google Places API key
  N8N_API_KEY         n8n Cloud API key
""")


if __name__ == "__main__":
    # Ensure atlas_data directory exists
    ATLAS_DIR.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "run":
        run_full_cycle()
    elif cmd == "discover":
        run_discover()
    elif cmd == "status":
        print_status()
    elif cmd == "pause":
        cmd_pause()
    elif cmd == "resume":
        cmd_resume()
    elif cmd == "reweight":
        cmd_reweight()
    elif cmd == "outcome":
        if len(sys.argv) < 4:
            print("Usage: lead_engine.py outcome <lead_id> <outcome>")
            print(f"  Valid outcomes: {', '.join(sorted(VALID_OUTCOMES))}")
            sys.exit(1)
        record_outcome(sys.argv[2], sys.argv[3])
    elif cmd == "export":
        export_report()
    elif cmd == "sync":
        sync_to_pipeline()
    elif cmd == "outcomes":
        sync_retell_outcomes()
    elif cmd == "ingest-scraped":
        result = ingest_scraped_leads()
        print(f"[ENGINE] Ingested {len(result)} scraped email leads.")
    elif cmd == "suppress":
        if len(sys.argv) < 3:
            print("Usage: lead_engine.py suppress <phone> [reason]")
            sys.exit(1)
        phone = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else "manual_suppress"
        s = SuppressionList()
        s.add(reason, phone=phone)
        print(f"[ENGINE] Added {phone} to suppression list ({reason}).")
    elif cmd == "consent":
        if len(sys.argv) < 4:
            print(f"Usage: lead_engine.py consent <lead_id> <method>")
            print(f"  Valid methods: {', '.join(sorted(VALID_CONSENT_METHODS))}")
            sys.exit(1)
        record_consent_event(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {cmd}")
        print_usage()
        sys.exit(1)
