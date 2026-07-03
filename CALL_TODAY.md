# CALL TODAY — Warm Leads Awaiting Human Follow-Up
**Generated:** 2026-07-03 | **Source:** Retell call data + outcomes.json

These leads had REAL conversations with the auto-caller. They picked up, they talked, they're warm.
**None have been followed up by a human.** Every one is money left on the table.

---

## Priority 1: Named Leads with Openers

### 1. Tommy Neal Electric Inc
- **Phone:** (580) 332-1928
- **Location:** Oklahoma
- **Outcome:** callback (85s call, June 12)
- **Opener:** "Hey, this is Boston from BOSS Systems. Y'all got a call from us a couple weeks ago about your phone setup. Quick question — when you're out on a job, who's handling your calls?"

### 2. Affordable Plumbing Repairs
- **Phone:** (601) 749-0091
- **Location:** Mississippi
- **Outcome:** callback (38s call, June 15)
- **Opener:** "Hey, this is Boston with BOSS Systems. I called a couple weeks ago and got put on hold. I work with plumbing businesses on their missed calls. How many calls a week do you think go to voicemail when that receptionist is busy?"

### 3. Russell Branan Plumbing
- **Phone:** (918) 683-1775
- **Location:** Oklahoma
- **Outcome:** meeting_set (160s call, June 27)
- **Signals:** Weather surge, no capacity surge, pain review ('no one answered')
- **Opener:** "Hey, this is Boston from BOSS Systems. We talked a couple days ago about setting up a time. Just wanted to lock that in. When's a good 15 minutes this week?"

### 4. CARL RAY'S PLUMBING AND SUPPLIES
- **Phone:** (918) 647-7189
- **Location:** Oklahoma
- **Outcome:** meeting_set (121s call, June 27)
- **Signals:** Weather flood, pain review ('voicemail'), weak rating
- **Opener:** "Hey, this is Boston with BOSS Systems. We spoke earlier this week and you sounded interested. I'd love to show you exactly what we do. Got 15 minutes today or tomorrow?"

### 5. Pinner Plumbing & Heating Inc
- **Phone:** (870) 234-1667
- **Location:** Arkansas
- **Outcome:** meeting_set (67s call, June 27)
- **Signals:** Pain review ('no answer'), multiple pain signals, weak rating (4.3)
- **Opener:** "Hey, this is Boston from BOSS Systems. We had a quick chat the other day. You mentioned some phone issues. I can show you a live demo of how we fix that in about 5 minutes. You free?"

### 6. Anderson Plumbing LLC
- **Phone:** (228) 697-8926
- **Location:** Mississippi
- **Outcome:** callback (73s call, June 27)
- **Signals:** Weather flood, pain review ('voicemail'), multiple pain signals
- **Opener:** "Hey, this is Boston with BOSS Systems. We chatted briefly and I wanted to follow up. I've got a quick demo that takes 2 minutes to show how it works. Can I call the demo line while you listen?"

---

## Priority 2: Unnamed Leads (Need Boston to Call and Identify)

### 7. Unknown — (870) 307-4611
- **Outcome:** callback (43s, June 25)
- **Signals:** No website, Tier 1 niche, low reviews (3), brand new
- **Opener:** "Hey, this is Boston from BOSS Systems. We spoke last week — just following up. Quick question, when a customer calls and you can't pick up, what happens to that call?"

### 8. Unknown — (870) 307-1177
- **Outcome:** meeting_set (15s, June 25)
- **Signals:** No website, Tier 1 niche, low reviews (1), brand new
- **Opener:** Same opener as above

### 9. Unknown — (870) 935-9362
- **Outcome:** callback (47s, June 25)
- **Signals:** Weak rating (4.0), Tier 1 niche, low reviews (5)
- **Note:** May be Tri State Armature (wrong target per hot_followup_list.md)

### 10. Unknown — (918) 225-8097
- **Outcome:** meeting_set (20s, June 25)
- **Signals:** Weather flood, weak rating (4.1), no website, Tier 1 niche
- **Opener:** "Hey, this is Boston from BOSS Systems. We connected last week and I wanted to follow up personally. I've got something that takes 2 minutes to show you."

### 11. Unknown — (601) 701-6068
- **Outcome:** callback (39s, June 27)
- **Signals:** Tier 1, weak rating (4.2), small operation (26 reviews), no website
- **Opener:** Same opener as #7

### 12. Unknown — (903) 601-8008
- **Outcome:** callback (155s, June 27)
- **Signals:** Weather surge, no capacity surge, pain review ('no answer')
- **Note:** 903 area code = East Texas. This is Boston's in-person territory. Walk-in demo opportunity.
- **Opener:** In-person visit preferred. Look up business, drive by, bring tablet.

---

## Call Rules
- Call between 9am-11am CT (golden window for contractors)
- Use personal cell, not AI caller
- If voicemail: leave a 15-second message, text immediately after
- If they answer: use the opener above, pivot to live demo call to (903) 522-4459
- Log every outcome: `python3 boss_command.py pitch "Business Name" warm-call [outcome]`
