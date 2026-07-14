#!/usr/bin/env python3
"""
BOSS Operations Report — Unified System Aggregator
Reads all data sources and produces ops_report.json for the ops dashboard.
Pushes to GitHub Pages for live display.

Usage:
    python3 ops_report.py          # Generate + push
    python3 ops_report.py local    # Generate only (no push)
"""
import json, os, sys, urllib.request, base64
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path.home() / "Desktop" / "BOSS_HQ"
ATLAS_DIR = BASE_DIR / "atlas_data"
SCRIPTS_DIR = BASE_DIR / "scripts"

N8N_API_KEY = os.environ.get("N8N_API_KEY", "")
N8N_BASE = os.environ.get("N8N_BASE", "https://jamross.app.n8n.cloud/api/v1")
RETELL_KEY = os.environ.get("RETELL_KEY", os.environ.get("RETELL_API_KEY", ""))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "BosRoss/bosssystems.co")


def load_json(path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def n8n_get(path):
    try:
        req = urllib.request.Request(
            f"{N8N_BASE}{path}",
            headers={"X-N8N-API-KEY": N8N_API_KEY}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def retell_get(path):
    if not RETELL_KEY:
        return {}
    try:
        req = urllib.request.Request(
            f"https://api.retellai.com/v2{path}",
            headers={"Authorization": f"Bearer {RETELL_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def build_report():
    now = datetime.now(timezone.utc)
    report = {"generated": now.isoformat(), "sections": {}}

    # ── 1. ATLAS Intelligence ──
    atlas_config = load_json(ATLAS_DIR / "config.json")
    boss_intel = load_json(ATLAS_DIR / "boss_intel.json")
    latest = load_json(ATLAS_DIR / "latest.json")

    report["sections"]["atlas"] = {
        "power_level": atlas_config.get("power_level", "UNKNOWN"),
        "last_scan": atlas_config.get("last_run", latest.get("generated", "")),
        "scan_count": atlas_config.get("total_runs", 0),
        "heat_score": boss_intel.get("boss_heat_score", 0),
        "recommendation": boss_intel.get("recommendation", ""),
        "demand_signals": len(boss_intel.get("demand_signals", [])),
        "pain_signals": len(boss_intel.get("pain_signals", [])),
        "pitch_adjustments": len(boss_intel.get("pitch_adjustments", [])),
        "competitor_intel": len(boss_intel.get("competitor_intel", [])),
        "territory_alerts": len(boss_intel.get("territory_alerts", [])),
        "top_demands": [
            {"type": d.get("type"), "area": d.get("area", "")[:60], "niche": d.get("niche")}
            for d in boss_intel.get("demand_signals", [])[:5]
        ],
        "sources_online": len([s for s in latest.get("source_status", [])
                               if s.get("status") == "ok"]) if latest.get("source_status") else 0,
    }

    # ── 2. Lead Engine ──
    engine_state = load_json(ATLAS_DIR / "engine_state.json")
    leads_queue = load_json(ATLAS_DIR / "leads_queue.json", {"leads": []})
    spend_data = load_json(ATLAS_DIR / "spend_tracker.json")
    outcomes_data = load_json(ATLAS_DIR / "outcomes.json", {"outcomes": []})
    suppression = load_json(ATLAS_DIR / "suppression.json")

    leads = leads_queue.get("leads", [])
    outcomes = outcomes_data.get("outcomes", [])

    by_tier = {}
    by_route = {}
    by_status = {}
    synced = 0
    for l in leads:
        by_tier[l.get("tier", "?")] = by_tier.get(l.get("tier", "?"), 0) + 1
        by_route[l.get("route", "?")] = by_route.get(l.get("route", "?"), 0) + 1
        by_status[l.get("status", "?")] = by_status.get(l.get("status", "?"), 0) + 1
        if l.get("synced_to_pipeline"):
            synced += 1

    by_outcome = {}
    for o in outcomes:
        oc = o.get("outcome", "?")
        by_outcome[oc] = by_outcome.get(oc, 0) + 1

    total_spent = spend_data.get("total_spent", 0)
    if isinstance(total_spent, str):
        try:
            total_spent = float(total_spent)
        except ValueError:
            total_spent = 0

    report["sections"]["lead_engine"] = {
        "state": "PAUSED" if engine_state.get("paused") else "ACTIVE",
        "total_leads": len(leads),
        "by_tier": by_tier,
        "by_route": by_route,
        "by_status": by_status,
        "synced_to_pipeline": synced,
        "api_spend": round(total_spent, 2),
        "api_budget": 300.00,
        "api_percent": round(total_spent / 300 * 100, 1) if total_spent else 0,
        "outcomes_recorded": len(outcomes),
        "by_outcome": by_outcome,
        "learned_weights": bool(outcomes_data.get("learned_weights")),
        "suppression_count": len(suppression.get("phones", [])),
        "top_leads": [
            {
                "name": l.get("business_name", "")[:30],
                "niche": l.get("niche", ""),
                "state": l.get("state", ""),
                "tier": l.get("tier", ""),
                "score": l.get("score", 0),
                "route": l.get("route", ""),
                "status": l.get("status", ""),
                "phone": l.get("phone", ""),
            }
            for l in sorted(leads, key=lambda x: -x.get("score", 0))[:20]
        ],
        "hot_leads": [
            {
                "name": next((ld.get("business_name", "") for ld in leads if ld.get("lead_id") == o.get("lead_id")), ""),
                "phone": next((ld.get("phone", "") for ld in leads if ld.get("lead_id") == o.get("lead_id")), ""),
                "outcome": o.get("outcome", ""),
                "duration": o.get("call_duration_sec", 0),
                "date": o.get("recorded_at", "")[:10],
                "signals": o.get("signals_hit", [])[:3],
            }
            for o in sorted(
                [x for x in outcomes if x.get("outcome") in ("meeting_set", "callback", "closed")],
                key=lambda x: x.get("recorded_at", ""),
                reverse=True,
            )[:10]
        ],
    }

    # ── 3. n8n Workflows ──
    wf_data = n8n_get("/workflows?limit=250")
    wfs = wf_data.get("data", [])
    active_wfs = [w for w in wfs if w.get("active")]
    inactive_wfs = [w for w in wfs if not w.get("active")]

    exec_data = n8n_get("/executions?limit=20&status=error")
    error_execs = exec_data.get("data", [])
    crash_data = n8n_get("/executions?limit=10&status=crashed")
    crashed = crash_data.get("data", [])

    critical_ids = {
        "UQGW8QuaSLb9Euyh": "Auto Caller",
        "wX6OyZ9UY0Xrbui1": "Morning Text",
        "7wFm6CQB3VtoiRb6": "ORACLE",
        "wMWL3U0JsdP6FO7F": "Lead Hunter",
        "Ylf18KkrsZobVvfZ": "Watchdog",
        "TtbV6mhhRnLhQCv3": "Morning Brief",
        "8jvr7e9CDZgggXzM": "Superniche Targeter",
        "kGJ7aDQmp3MgiPWI": "Hot Lead Handler",
    }
    active_ids = {w["id"]: w.get("active", False) for w in wfs}
    critical_status = []
    for wid, wname in critical_ids.items():
        critical_status.append({
            "name": wname,
            "id": wid,
            "active": active_ids.get(wid, False),
        })

    report["sections"]["n8n"] = {
        "active_workflows": len(active_wfs),
        "inactive_workflows": len(inactive_wfs),
        "total_workflows": len(wfs),
        "recent_errors": len(error_execs),
        "recent_crashes": len(crashed),
        "critical_workflows": critical_status,
        "recent_failures": [
            {
                "workflow": e.get("workflowData", {}).get("name", e.get("workflowId", "?")),
                "started": (e.get("startedAt") or "")[:16],
            }
            for e in (error_execs + crashed)[:5]
        ],
    }

    # ── 4. Retell Agents ──
    agents = []
    if RETELL_KEY:
        try:
            req = urllib.request.Request(
                "https://api.retellai.com/list-agents",
                headers={"Authorization": f"Bearer {RETELL_KEY}"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                agents = json.loads(r.read())
        except Exception:
            agents = []
    if not isinstance(agents, list):
        agents = agents.get("agents", []) if isinstance(agents, dict) else []

    agent_summary = []
    for a in agents:
        agent_summary.append({
            "name": a.get("agent_name", ""),
            "id": a.get("agent_id", ""),
            "last_modification": str(a.get("last_modification_timestamp") or "")[:10],
        })

    since_1d = int((now - timedelta(days=1)).timestamp() * 1000)
    calls_today = []
    if RETELL_KEY:
        try:
            payload = json.dumps({
                "filter_criteria": {"after_start_timestamp": since_1d},
                "limit": 50,
                "sort_order": "descending",
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.retellai.com/v2/list-calls",
                data=payload, method="POST",
                headers={"Authorization": f"Bearer {RETELL_KEY}",
                         "Content-Type": "application/json"}
            )
            raw = urllib.request.urlopen(req, timeout=15)
            calls_today = json.loads(raw.read().decode("utf-8"))
            if not isinstance(calls_today, list):
                calls_today = calls_today.get("calls", calls_today.get("data", []))
        except Exception:
            calls_today = []

    outbound = [c for c in calls_today if c.get("direction") == "outbound"]
    inbound = [c for c in calls_today if c.get("direction") != "outbound"]
    ended = [c for c in calls_today if c.get("call_status") == "ended"]
    avg_duration = 0
    if ended:
        durations = [(c.get("end_timestamp", 0) - c.get("start_timestamp", 0)) / 1000
                     for c in ended if c.get("end_timestamp")]
        avg_duration = round(sum(durations) / len(durations), 1) if durations else 0

    report["sections"]["retell"] = {
        "total_agents": len(agent_summary),
        "agents": agent_summary[:10],
        "calls_24h": len(calls_today),
        "outbound_24h": len(outbound),
        "inbound_24h": len(inbound),
        "avg_duration_sec": avg_duration,
    }

    # ── 5. Quant Sandbox ──
    quant_state = load_json(ATLAS_DIR / "quant" / "quant_state.json") if (ATLAS_DIR / "quant").exists() else {}
    paper_trades = load_json(ATLAS_DIR / "paper_trades.json")
    report["sections"]["quant"] = {
        "state": "PAUSED" if quant_state.get("paused") else "ACTIVE",
        "strategies": len(paper_trades.get("strategies", [])) if isinstance(paper_trades, dict) else 0,
        "survivors": 0,
    }

    # ── 6. System Health ──
    breakers = load_json(ATLAS_DIR / "circuit_breakers.json")
    tripped = [svc for svc, b in breakers.get("breakers", {}).items() if b.get("tripped")]

    report["sections"]["health"] = {
        "circuit_breakers_tripped": tripped,
        "engine_paused": engine_state.get("paused", False),
        "atlas_power": atlas_config.get("power_level", "UNKNOWN"),
        "n8n_errors_24h": len(error_execs),
        "retell_calls_24h": len(calls_today),
        "api_spend_pct": round(total_spent / 300 * 100, 1) if total_spent else 0,
    }

    return report


def push_to_github(report):
    if not GITHUB_TOKEN:
        print("[OPS] No GITHUB_TOKEN — saved locally only.")
        return

    content = json.dumps(report, indent=2, default=str)
    encoded = base64.b64encode(content.encode()).decode()
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/ops_report.json"

    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=10)
        sha = json.loads(resp.read().decode()).get("sha")
    except Exception:
        pass

    payload = {
        "message": "Ops report update",
        "content": encoded,
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(api_url, data=data, headers=headers, method="PUT")
        resp = urllib.request.urlopen(req, timeout=10)
        if resp.status in (200, 201):
            print("[OPS] Report pushed to GitHub.")
        else:
            print(f"[OPS] GitHub push failed: {resp.status}")
    except Exception as e:
        print(f"[OPS] GitHub push error: {e}")


def push_file_to_github(local_path, remote_name):
    if not GITHUB_TOKEN:
        return
    try:
        content = local_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    encoded = base64.b64encode(content.encode()).decode()
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{remote_name}"
    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=10)
        sha = json.loads(resp.read().decode()).get("sha")
    except Exception:
        pass
    payload = {"message": f"Update {remote_name}", "content": encoded, "branch": "main"}
    if sha:
        payload["sha"] = sha
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(api_url, data=data, headers=headers, method="PUT")
        urllib.request.urlopen(req, timeout=10)
        print(f"[OPS] {remote_name} pushed to GitHub.")
    except Exception as e:
        print(f"[OPS] {remote_name} push failed: {e}")


def update_boss_state(report):
    """Write sales_activity section to boss_state.json for cross-system reads."""
    boss_state_path = ATLAS_DIR / "boss_state.json"
    boss_state = load_json(boss_state_path)
    s = report["sections"]
    le = s.get("lead_engine", {})
    rt = s.get("retell", {})
    sales = load_json(ATLAS_DIR / "sales_activity.json")
    pitches = sales.get("pitches", [])
    boss_state["sales_activity"] = {
        "last_updated": report["generated"],
        "mrr": 50,
        "active_clients": 1,
        "pipeline_total": le.get("total_leads", 0),
        "pipeline_by_tier": le.get("by_tier", {}),
        "outcomes_recorded": le.get("outcomes_recorded", 0),
        "calls_24h": rt.get("calls_24h", 0),
        "outbound_24h": rt.get("outbound_24h", 0),
        "pitches_7d": len([p for p in pitches if p.get("date", "") >= (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")]),
    }
    boss_state["last_updated"] = report["generated"]
    boss_state_path.write_text(json.dumps(boss_state, indent=2, default=str) + "\n")


def build_sales_data():
    """Build sales_data.json for the sales tools dashboard."""
    queue = load_json(ATLAS_DIR / "leads_queue.json", {"leads": []})
    leads = queue.get("leads", [])
    outcomes_data = load_json(ATLAS_DIR / "outcomes.json", {"outcomes": []})
    outcomes = outcomes_data if isinstance(outcomes_data, list) else outcomes_data.get("outcomes", [])

    callable_statuses = {"queued", "re_engaged", "cold", "callback", "called"}
    callable_leads = sorted(
        [l for l in leads if l.get("status") in callable_statuses],
        key=lambda x: -x.get("score", 0),
    )

    def fmt_phone(p):
        p = str(p).strip()
        if len(p) == 10 and p.isdigit():
            return f"({p[:3]}) {p[3:6]}-{p[6:]}"
        return p

    # Build outcome lookup for last-contact info
    outcome_by_lead = {}
    for o in sorted(outcomes, key=lambda x: x.get("recorded_at", "")):
        lid = o.get("lead_id", "")
        if lid:
            outcome_by_lead[lid] = {
                "last_outcome": o.get("outcome", ""),
                "last_contact": o.get("recorded_at", "")[:10],
            }

    call_list = []
    for l in callable_leads[:200]:
        phone = l.get("phone", "")
        if not phone or len(str(phone).strip()) < 10:
            continue
        lid = l.get("lead_id", "")
        contact_info = outcome_by_lead.get(lid, {})
        call_list.append({
            "name": l.get("business_name", "")[:40],
            "phone": fmt_phone(phone),
            "phone_raw": str(phone).strip(),
            "niche": l.get("niche", ""),
            "city": l.get("area", ""),
            "state": l.get("state", ""),
            "tier": l.get("tier", ""),
            "score": l.get("score", 0),
            "status": l.get("status", ""),
            "signals": l.get("signals_hit", [])[:3],
            "rating": l.get("rating", 0),
            "review_count": l.get("review_count", 0),
            "last_contact": contact_info.get("last_contact", ""),
            "last_outcome": contact_info.get("last_outcome", ""),
        })

    hot_outcomes = []
    seen_phones = set()
    for o in sorted(outcomes, key=lambda x: x.get("recorded_at", ""), reverse=True):
        if o.get("outcome") in ("meeting_set", "callback", "closed"):
            lead_match = next((ld for ld in leads if ld.get("lead_id") == o.get("lead_id")), {})
            phone = lead_match.get("phone", "")
            raw = str(phone).strip()
            name = lead_match.get("business_name", o.get("lead_id", ""))[:40]
            if not raw or len(raw) < 10 or not name or len(name) < 3:
                continue
            if raw in seen_phones:
                continue
            seen_phones.add(raw)
            hot_outcomes.append({
                "name": name,
                "phone": fmt_phone(phone) if phone else "",
                "phone_raw": raw,
                "outcome": o.get("outcome", ""),
                "date": o.get("recorded_at", "")[:10],
                "niche": lead_match.get("niche", ""),
                "city": lead_match.get("area", ""),
            })
            if len(hot_outcomes) >= 15:
                break

    by_status = {}
    for l in leads:
        s = l.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_leads": len(leads),
            "callable": len([l for l in leads if l.get("status") in callable_statuses]),
            "by_status": by_status,
            "meetings_set": len([o for o in outcomes if o.get("outcome") == "meeting_set"]),
            "callbacks": len([o for o in outcomes if o.get("outcome") == "callback"]),
        },
        "call_list": call_list,
        "hot_outcomes": hot_outcomes,
    }


def main():
    print("=" * 60)
    print("  BOSS OPS REPORT — Generating...")
    print("=" * 60)

    report = build_report()

    out_path = ATLAS_DIR / "ops_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\n  Saved: {out_path}")

    update_boss_state(report)
    print("  boss_state.json updated with sales_activity")

    sales_data = build_sales_data()
    sales_path = BASE_DIR / "sales_data.json"
    sales_path.write_text(json.dumps(sales_data, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"  sales_data.json: {len(sales_data['call_list'])} callable leads")

    s = report["sections"]
    print(f"\n  ATLAS: Heat {s['atlas']['heat_score']}/100, "
          f"{s['atlas']['demand_signals']} demands, {s['atlas']['pain_signals']} pains")
    print(f"  Leads: {s['lead_engine']['total_leads']} total, "
          f"{s['lead_engine']['by_tier']}, "
          f"${s['lead_engine']['api_spend']:.2f} spent")
    print(f"  n8n: {s['n8n']['active_workflows']} active, "
          f"{s['n8n']['recent_errors']} errors, "
          f"{s['n8n']['recent_crashes']} crashes")
    print(f"  Retell: {s['retell']['calls_24h']} calls (24h), "
          f"{s['retell']['total_agents']} agents")
    print(f"  Health: {len(s['health']['circuit_breakers_tripped'])} breakers tripped")

    local_only = len(sys.argv) > 1 and sys.argv[1] == "local"
    if not local_only:
        push_to_github(report)
        push_file_to_github(ATLAS_DIR / "boss_intel.json", "boss_intel.json")
        push_file_to_github(sales_path, "sales_data.json")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
