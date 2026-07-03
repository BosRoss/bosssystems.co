# CLAUDE.md vs CLAUDE_KNOWLEDGE_TRANSFER.md — Conflict Audit
Generated: 2026-06-25 | Re-verified: 2026-07-03 (Phase 6 Final Integration)

All conflicts resolved by merging into CLAUDE.md (canonical). KT file archived.

## Conflicts Found

### 1. Auto Caller
- **KT:** Lists n8n workflow UQGW8QuaSLb9Euyh as active (10am + 2pm CT)
- **Reality:** n8n Auto Caller dead since June 9 (can't reach Retell API). Replaced by GitHub Actions (BosRoss/boss-automation). Migrated June 25.
- **Resolution:** CLAUDE.md already updated with GitHub Actions as primary.

### 2. Morning Text
- **KT:** Lists n8n wX6OyZ9UY0Xrbui1 at 7am CT
- **Reality:** Crashed n8n worker (OOM). Replaced by GitHub Actions at 8am CT. Migrated June 25.
- **Resolution:** CLAUDE.md already updated.

### 3. Cold Email Outreach
- **KT:** Lists WY9QQU8gSSaKO9kD as active (weekly)
- **Reality:** Permanently deactivated June 4 (Gmail node). Replaced by local contact_sequence.py + LaunchAgent.
- **Resolution:** CLAUDE.md already correct.

### 4. Post-Call Handler
- **KT:** Lists EGyXul1WqnnshU96 as active ("On call end")
- **Reality:** DEACTIVATED. Caused May + June meltdowns (retry storms, burned 222+ executions). Known Mistake #23.
- **Resolution:** Fixed in CLAUDE.md line 145 during this audit (was incorrectly marked Active).

### 5. Voice Settings
- **KT:** "Cartesia-Brian, speed 1.1, volume 1.5, responsiveness 0.95"
- **Reality:** All 15 agents upgraded to ElevenLabs eleven_v3 with Nico (male) / Grace (female) / Hailey (mystery caller). June 9.
- **Resolution:** CLAUDE.md has correct voice settings section.

### 6. AI Disclosure Rule
- **KT Known Mistake #6:** "AI disclosure in opener -> 100% hangup rate"
- **Reality:** FTC 2024 rule requires proactive disclosure. CLAUDE.md Known Mistake #7 says disclose at start of every call. Updated June 1.
- **Resolution:** KT was wrong. CLAUDE.md is correct. Disclosure is legally required.

### 7. ATLAS Sources
- **KT:** Lists only 8 sources (Reddit 19 subs, NOAA 7 states, NASA EONET, ISS, Polymarket, HN, BBC/TechCrunch, USGS)
- **Reality:** 40+ sources including Congress.gov, Telegram OSINT, Financial Futures, NASA FIRMS, Wikipedia Edit Storms, Safecast Radiation, etc.
- **Resolution:** CLAUDE.md has complete source list.

### 8. ATLAS Power Levels
- **KT:** SLEEP (6hr), IDLE (2hr), ACTIVE (30min), SURGE (10min)
- **Reality:** Auto-scheduled. SURGE at 6am/6pm CT, ACTIVE every 2 hours otherwise. No SLEEP/IDLE anymore.
- **Resolution:** CLAUDE.md has correct auto-schedule.

### 9. Pricing Conflict
- **KT:** Mentions "$250 custom build fee + $50/mo" (receptionist) alongside three products
- **CLAUDE.md:** Three products are primary: ANALYZE (free), BUILD ($1,497-$5,997), AUTOPILOT (80/20 split). Also lists "$250 + $50/mo" under WHO BOSTON IS.
- **Resolution:** Both models exist. Receptionist is the entry product. Three products are the mission. No conflict — just different scales.

### 10. Partner/Summer Workflows
- **KT:** Lists 3 partner workflows (Revenue Monitor koi5QT6XJvuoPuvL, Social Content Qikvz1N2lTubgqoS, Intake Xpg4n1zavfeKADcv)
- **Reality:** These IDs don't appear in CLAUDE.md workflow tables. Status unknown.
- **Resolution:** Need to verify if these are still active or were deactivated. Flagged for next audit.

### 11. Current State
- **KT:** "CURRENT STATE (as of May 29, 2026)" — entirely stale. Says n8n quota exhausted, 0 paying clients, summer program waiting.
- **Reality:** Quota reset June 1, Wickham is a paying client ($50/mo), auto-caller on GitHub Actions, systems running.
- **Resolution:** Section deleted. CLAUDE.md has current state inline.

### 12. Superniche Targeter Schedule
- **KT:** Lists Daily Superniche Targeter at "7:30am CT"
- **CLAUDE.md:** Calling hours section says 7:30am calling is a known mistake, Targeter runs at 7am CT and does NOT dial.
- **Resolution:** CLAUDE.md is correct. Targeter finds targets at 7am, auto-caller dials at 10am/2pm.

### 13. Known Mistakes Count
- **KT:** 13 known mistakes
- **CLAUDE.md:** 58 known mistakes (comprehensive)
- **Resolution:** CLAUDE.md is the authoritative list. KT subset is covered.

## Items Unique to KT (Merged if Missing from CLAUDE.md)

### Already in CLAUDE.md:
- All tech stack info
- Territory rules
- Expert frameworks (Van Edwards, Kahneman, Cialdini, Voss, Moore, Ross, Godin)
- Boston Agent system
- BPP details
- Superniche scoring
- Client acquisition findings
- Market intelligence
- File structure
- Claude Code prompting tips (not needed in CLAUDE.md — that's for Claude app users)

### Not needed in CLAUDE.md:
- "How to Prompt Claude Code" section — this is meta-guidance for Claude app, not operational rules
- "What's Next" section — stale priorities from May 29

## Action Taken
- CLAUDE_KNOWLEDGE_TRANSFER.md archived to _audit/CLAUDE_KNOWLEDGE_TRANSFER.md.archived
- CLAUDE.md is the single canonical source of truth
- All conflicts resolved in favor of CLAUDE.md (more current, more complete)
