# BOSS Systems — Quick Reference
**Last updated: 2026-07-03**

## What BOSS Systems Is

An AI business innovation company built by Boston Rossall, 17, Tyler TX. BOSS builds AI phone systems, booking engines, payment flows, and review request systems for small service businesses. The target: contractors in small towns (15k-80k pop) across MS, AR, AL, TN, OK, NM.

## Current Numbers

- **MRR:** $50
- **Clients:** 1 (Wickham Lawn Care, McKinney TX, $50/mo)
- **Google Places credit:** ~$290 remaining, expires Aug 7 2026
- **Retell agents:** 15 (12 with phone numbers)
- **n8n workflows:** ~34 active
- **Pipeline:** 200+ scored leads

## Three Products

1. **BOSS ANALYZE** (free) — 60-second AI analysis at bosssystems.co/analyze.html
2. **BOSS BUILD** ($1,497-$5,997 + $97-497/mo) — full AI stack built for their business
3. **BOSS AUTOPILOT** (0 setup, 80/20 revenue split) — we build and operate, partner does physical work

The website homepage leads with the simple offer: AI phone receptionist, $250 setup + $50/mo flat.

## How the System Works

```
ATLAS (intelligence) → Lead Engine (scoring) → Auto Caller (outreach) → Retell (calls)
     ↓                      ↓                       ↓                      ↓
boss_state.json ←───── prospect_scorer ←──── outcomes.json ←──── post-call data
     ↓
ops_report.py → ops dashboard (bosssystems.co/ops.html)
cost_tracker.py → daily spend tracking
```

**ATLAS** scans 40+ sources every 2 hours (weather, Reddit, NOAA, Congress, prediction markets, Telegram OSINT, financial futures). Writes intelligence to boss_intel.json and market_intelligence to boss_state.json.

**Lead Engine** takes ATLAS signals, scores prospects on 15+ factors, routes to appropriate channel. Runs on GitHub Actions (BosRoss/boss-automation) at 10am and 2pm CT weekdays.

**Retell** handles all voice calls — inbound receptionist and outbound sales. ElevenLabs eleven_v3 voices across all agents.

**boss_state.json** is the shared context hub. Written by cost_tracker (costs), atlas (market_intelligence), and ops_report (sales_activity). Read by prospect_scorer for demand signal boosts.

## Territory Rules

- **East Texas (903, 430):** Boston in-person only. Never auto-dial.
- **Louisiana (985, 318):** Banned. Wrong market.
- **Remote markets (MS, AR, AL, TN, OK, NM):** Auto-caller territory.
- **Florida (850):** Expired June 15. Auto-discarded.

## Key Files

| Purpose | File |
|---------|------|
| System rules | CLAUDE.md |
| Cost tracking | scripts/cost_tracker.py |
| Intelligence | scripts/atlas.py |
| Lead scoring | scripts/prospect_scorer.py |
| Agent builder | scripts/business_builder.py |
| Daily ops report | scripts/ops_report.py |
| CLI interface | scripts/boss_command.py |
| Shared state | atlas_data/boss_state.json |
| Warm leads | CALL_TODAY.md |
| Brand audit | BRAND_VOICE_AUDIT.md |

## The Three Locks

1. **No first-touch without human touchpoint** — being in the queue doesn't count
2. **$50 spend gate** — anything over $50 or irreversible needs Boston's OK via ntfy
3. **Kill switch** — `python3 scripts/killswitch.py` shuts everything down

## Key Numbers for Pitches

- 62% of contractor calls go unanswered
- 85% of voicemail callers never call back
- 78% buy from whoever answers first
- HVAC loses $88K-177K/year to missed calls
- Ruby Receptionist costs $250-720/mo. BOSS costs $50/mo flat.

## What NOT to Do

- Never call 903/430 area codes
- Never say "free" as a hook — say "no cost for the first week"
- Never add "Wait." to voice prompts
- Never use Gmail nodes in n8n
- Never ship without testing live
- Never edit scripts without syncing to ~/Library/Application Support/BOSS/
- Never read more than 30 rows from Google Sheets
