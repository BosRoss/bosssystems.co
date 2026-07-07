#!/usr/bin/env python3
"""
BOSS Automation Library
Complete catalog of every AI automation BOSS Systems can build for a client.
Each entry knows its value, cost, build time, and what business types it applies to.

Usage:
  from automation_library import AUTOMATION_CATALOG, get_recommendations
  recs = get_recommendations("hvac", existing_automations=["phone_receptionist"])
"""

# ──────────────────────────────────────────────────────────────────────────────
# AUTOMATION CATALOG
# ──────────────────────────────────────────────────────────────────────────────

AUTOMATION_CATALOG = {

    # ── CUSTOMER ACQUISITION ──────────────────────────────────────────────────

    "phone_receptionist": {
        "name": "AI Phone Receptionist",
        "category": "Customer Acquisition",
        "description": (
            "AI answers every inbound call 24/7. Qualifies the lead, gives pricing ranges, "
            "books the appointment, and sends a confirmation text to the customer and to you. "
            "Never goes to voicemail. Built on Retell AI + Claude. "
            "Books jobs while you are on a roof, under a sink, or asleep at 2am. "
            "Handles up to 100 simultaneous calls — no busy signals ever."
        ),
        "annual_value": 52000,         # ~4 recovered jobs/week x $250 avg x 52 weeks
        "monthly_cost": 60,
        "build_time_hours": 2,
        "difficulty": 1,
        "tools": ["retell_ai", "n8n", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "auto_repair", "law_firm", "pest_control",
                        "lawn_care", "gym", "retail", "restaurant", "real_estate", "all"],
        "integration": (
            "We forward your existing business number — no new number, no changes to your phone system. "
            "Works with any carrier (AT&T, Verizon, T-Mobile, landline, VoIP). You set up call forwarding "
            "once from your phone settings or call your carrier. When a call comes in, it rings your phone "
            "first — if you do not answer in 3-4 rings, it forwards to the AI. You can also set it to always "
            "forward (nights/weekends). Your customers dial the same number they always have."
        ),
        "owner_effort": (
            "One-time: 15-minute setup call where you tell us your services, pricing ranges, hours, "
            "and any questions customers commonly ask. We build the agent from your answers. "
            "Ongoing: nothing. You get a text every time a job is booked. Review your dashboard anytime."
        ),
        "objections": {
            "What if the AI gives the wrong price?": (
                "The AI only gives ranges you set. If you say 'AC repair is $150-$400 depending on the issue,' "
                "that is exactly what it says. It never invents prices. For anything outside the ranges, "
                "it says 'I will have the owner call you back with an exact quote.' You approve the ranges during setup."
            ),
            "I already have a girl answering phones": (
                "Does she answer at 2am? On Saturdays? When she is on lunch? When 3 calls come in at once? "
                "62% of contractor calls go unanswered — most of those are during business hours when staff is busy. "
                "This is not a replacement for your receptionist. It is her backup for every call she cannot get to."
            ),
            "My customers want a real person": (
                "We tested this with real contractors. Customers care about getting their problem solved fast — "
                "not whether a human or AI answered. The AI books the appointment, gives the price range, "
                "and sends a confirmation text in under 60 seconds. That is faster than any human receptionist. "
                "If someone specifically asks for a person, the AI says 'Let me have the owner call you back' "
                "and you get an immediate text."
            ),
            "How do I know this actually works?": (
                "Call our demo line right now: (903) 522-4459. That is a live AI receptionist handling real calls. "
                "Try to stump it. Ask about pricing, hours, scheduling. If you are not convinced after that call, "
                "we are not a fit. Also — first week is no cost. If it does not book a single job, cancel."
            ),
            "What about my ServiceTitan / Housecall Pro?": (
                "The AI books into Google Calendar, which syncs with ServiceTitan, Housecall Pro, and Jobber "
                "natively. Or we can send booking details as a text/email that your office manager enters. "
                "We do not require you to switch any software. If you use a calendar, we plug into it."
            ),
        },
        "works_with": ["any_phone_system", "google_calendar", "servicetitan", "housecall_pro",
                        "jobber", "outlook_calendar", "apple_calendar"],
    },

    "missed_call_textback": {
        "name": "Missed Call Text-Back",
        "category": "Customer Acquisition",
        "description": (
            "When any call is missed, the caller gets an automated text within 60 seconds: "
            "'Hey, this is [business]! We just missed your call — what can we help you with?' "
            "85% of callers never call back after voicemail. A text catches them before they call a competitor. "
            "Works even when your phone is off, dead, or you are on another call."
        ),
        "annual_value": 9600,          # ~$800/month recovered from missed calls
        "monthly_cost": 15,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
        "integration": (
            "Uses your existing business number via call forwarding. When a call goes unanswered and hits "
            "forwarding, our system detects the miss and fires a text from a local number back to the caller. "
            "The text includes your business name. If paired with the AI Phone Receptionist, the text fires "
            "only if the AI also could not connect (rare). Works with any carrier — AT&T, Verizon, T-Mobile, "
            "landline, VoIP."
        ),
        "owner_effort": (
            "One-time: 5-minute setup. You tell us your business name and what text you want sent. "
            "We set up the forwarding detection. Ongoing: nothing. You just reply to customers who text back."
        ),
        "objections": {
            "I already check my missed calls": (
                "How fast? The data says if you call back within 5 minutes, you are 21x more likely to book the job "
                "than if you wait 30 minutes. This system fires in under 60 seconds. Even if you check missed calls "
                "every hour, you are already too late for most of them."
            ),
            "I do not want to spam people": (
                "It is one text, one time, only when they called you first. They initiated contact. "
                "The text says 'We missed your call, what can we help with?' That is not spam — that is customer service. "
                "Most people reply with their problem and you book the job over text."
            ),
            "What if they just called the wrong number?": (
                "Then they ignore the text. No harm done. But 95% of calls to your business number are real prospects. "
                "The cost of missing a real lead is $250-$2,500. The cost of texting a wrong number is $0.01."
            ),
        },
        "works_with": ["any_phone_system", "any_crm", "servicetitan", "housecall_pro", "jobber"],
    },

    "outbound_caller": {
        "name": "AI Outbound Cold Caller",
        "category": "Customer Acquisition",
        "description": (
            "AI calls a list of prospects every day, introduces the business, "
            "identifies pain points, and books demos or appointments. "
            "Works from a Google Places scraped prospect list or your own list. "
            "Runs at set times (default 10am and 2pm), caps at 50 calls/day, skips duplicates, "
            "skips anyone who said no. Full FTC compliance — AI discloses itself upfront."
        ),
        "annual_value": 36000,         # 3 clients/month x $1,000 avg job x 12 months
        "monthly_cost": 80,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["retell_ai", "n8n", "google_places"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair", "law_firm"],
        "integration": (
            "Standalone system — does not touch your existing phone or CRM. Calls go out from a separate "
            "local number. Prospects who book get added to your calendar (Google Calendar, or we text you). "
            "If you have a CRM (ServiceTitan, Housecall Pro, Jobber), we can push booked leads there via "
            "email notification or webhook. You provide a prospect list or we scrape one from Google for "
            "your service area."
        ),
        "owner_effort": (
            "One-time: 30-minute setup. You approve the call script, define your service area and target "
            "customer type, and provide any existing prospect list (optional — we can build one). "
            "Ongoing: 5 minutes/day reviewing booked appointments. You get a text for every hot lead. "
            "You should personally call back anyone the AI marks as highly interested."
        ),
        "objections": {
            "Is this legal? Cold calling with AI?": (
                "Yes — with proper compliance. The AI discloses it is AI at the start of every call (FTC 2024 rule). "
                "It honors do-not-call requests immediately and adds them to a permanent suppression list. "
                "It only calls during legal hours (9am-6pm local). It never calls the same number twice. "
                "We built three layers of duplicate protection."
            ),
            "I do not want to annoy people": (
                "Neither do we — annoyed prospects do not buy. The AI opens with a question about their business, "
                "not a pitch. If they are not interested, it thanks them and hangs up in under 15 seconds. "
                "Average call time for uninterested prospects is 12 seconds. Interested prospects talk for 2-3 minutes."
            ),
            "I tried cold calling before and it did not work": (
                "Human cold calling fails because humans hate rejection and quit after 10 dials. "
                "The AI does not care about rejection. It makes 50 calls a day, every day, without getting tired or "
                "discouraged. At a 3-5% booking rate, that is 1-2 appointments per day, 20-40 per month. "
                "The math works when volume is consistent."
            ),
            "What if the AI says something stupid to a prospect?": (
                "You approve the exact script before it goes live. The AI sticks to that script — it cannot "
                "improvise outside the boundaries you set. If a prospect asks something unexpected, the AI says "
                "'That is a great question — let me have someone from the team follow up with you on that.' "
                "You get the recording of every call."
            ),
        },
        "works_with": ["google_calendar", "servicetitan", "housecall_pro", "jobber",
                        "any_crm", "google_sheets"],
    },

    "review_mining": {
        "name": "Competitor Review Mining",
        "category": "Customer Acquisition",
        "description": (
            "Scrapes 1-2 star Google reviews from competitors every week. "
            "Identifies unhappy customers who are actively looking for alternatives. "
            "Adds them to an outreach list with what they complained about. "
            "These are the hottest prospects you can find — they already want someone new. "
            "You see the complaint, you know exactly what to say when you reach out."
        ),
        "annual_value": 18000,         # 1.5 clients/month from review mining x avg job value
        "monthly_cost": 20,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_places"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair"],
        "integration": (
            "Fully standalone. Runs weekly on our servers using the Google Places API. "
            "Delivers a report to you via text or email every Monday morning with: "
            "competitor name, reviewer name, what they complained about, and the review date. "
            "No connection to your phone system, CRM, or any of your tools needed. "
            "You can also view results in your BOSS dashboard."
        ),
        "owner_effort": (
            "One-time: 10 minutes. You give us the names of 3-10 local competitors you want to monitor. "
            "Ongoing: 5 minutes/week reading the Monday report and deciding who to reach out to. "
            "The outreach itself is up to you — postcard, call, door knock. We give you the targets."
        ),
        "objections": {
            "That seems shady — going after competitor customers": (
                "Every business owner reads their competitors' Google reviews. This just automates the reading. "
                "You are not contacting the reviewer — you are identifying neighborhoods and job types where "
                "competitors are failing. If someone left a 1-star review for a plumber who flooded their bathroom, "
                "that homeowner needs a real plumber. That is not shady — that is a service."
            ),
            "I already know who my competitors are": (
                "You know their names. Do you know which ones dropped below 4 stars this month? "
                "Do you know which specific jobs they botched last week? This gives you the play-by-play, "
                "not just the roster. One bad review for a competitor is a warm lead for you."
            ),
            "How does this actually get me customers?": (
                "It does not by itself. It gives you intelligence. You send a postcard to the neighborhood "
                "where a competitor just got a 1-star review: 'Had a bad experience with your last plumber? "
                "We have 47 five-star reviews. Here is $25 off.' The competitor's bad review is your best ad."
            ),
        },
        "works_with": ["google_sheets", "any_crm", "any_email"],
    },

    "google_lsa_optimizer": {
        "name": "Google LSA Auto-Optimizer",
        "category": "Customer Acquisition",
        "description": (
            "Monitors Google Local Services Ads performance weekly. "
            "Alerts when cost-per-lead spikes, ad pauses, or ranking drops. "
            "Provides weekly recommendations: which job types to promote, "
            "what budget to set, which days have best ROI. "
            "Most contractors waste 30-50% of their LSA budget on wrong job categories."
        ),
        "annual_value": 12000,         # Prevents ~$1,000/month in wasted ad spend
        "monthly_cost": 10,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_places"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair", "law_firm"],
        "integration": (
            "Reads your Google Business Profile and LSA data via the Google API (read-only — we never "
            "change your ads). You grant read access to your Google Business Profile during setup. "
            "Weekly report delivered via text or email. If you have an ads manager, they can also "
            "receive the report. No software to install, no login to manage."
        ),
        "owner_effort": (
            "One-time: 10 minutes. You connect your Google Business Profile (one-click authorization). "
            "You tell us your max acceptable cost-per-lead. "
            "Ongoing: 5 minutes/week reading the Monday report. You make the actual changes in your "
            "Google LSA dashboard based on our recommendations — or your ads person does."
        ),
        "objections": {
            "My ads guy already handles this": (
                "Does he check it every week? Does he alert you when your cost-per-lead doubles overnight? "
                "Most ads managers check monthly at billing time. By then you have already wasted $500-$1,000. "
                "This catches problems in days, not months. Your ads guy can use the report too."
            ),
            "I do not run LSA ads": (
                "Then this is not for you yet. But when you do start LSA (and most service businesses should), "
                "this is day-one insurance against wasting money. Average contractor wastes $300/month on LSA "
                "before figuring out which job types to bid on."
            ),
            "I can just check Google myself": (
                "You can. Will you? Every Monday at 7am? The value is consistency, not complexity. "
                "This system checks every week without fail and texts you only when something needs attention. "
                "Most owners check their ads once a month when the credit card bill hits."
            ),
        },
        "works_with": ["google_business_profile", "google_lsa", "any_email"],
    },

    "social_media_ai": {
        "name": "Social Media AI (Daily Posts)",
        "category": "Customer Acquisition",
        "description": (
            "Generates and schedules one social post per day across Facebook and Google Business. "
            "Posts include: before/after job photos, seasonal tips, local shoutouts, promotions. "
            "Written by AI in the business owner's voice — not generic 'happy Monday' garbage. "
            "Owner can review and approve before posting, or let it run fully autonomous."
        ),
        "annual_value": 8400,          # $700/month equivalent of social media mgmt services
        "monthly_cost": 25,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["n8n", "anthropic_claude"],
        "applies_to": ["all"],
        "integration": (
            "Connects to your Facebook Page and Google Business Profile via Buffer (scheduling tool). "
            "You grant posting access during setup — one-time authorization. Posts are generated by AI "
            "and queued in Buffer. If approval mode is on, you get a text with the post and tap to approve. "
            "If autonomous mode is on, posts go out automatically at optimal times. "
            "You can send us before/after photos anytime via text and they get worked into posts."
        ),
        "owner_effort": (
            "One-time: 20 minutes. You connect your Facebook Page and Google Business. "
            "You tell us your voice/tone (professional, friendly, funny, etc.) and topics to avoid. "
            "Ongoing (approval mode): 30 seconds/day — read the post preview, tap approve or reject. "
            "Ongoing (autonomous mode): nothing, but sending us job photos via text makes posts better. "
            "Honest note: Social media works best when you occasionally reply to comments. 2 minutes/day."
        ),
        "objections": {
            "Social media does not get me customers": (
                "Direct sales from social? Rarely. But here is what it does: when a prospect Googles you "
                "and sees your Facebook page has not posted in 8 months, they think you are out of business. "
                "A daily post says 'we are active, busy, and real.' It is credibility insurance, not a lead channel. "
                "Also — Google Business posts directly affect your local search ranking."
            ),
            "I do not have time for social media": (
                "That is exactly why this exists. You spend zero time. The AI writes, designs, and posts. "
                "Social media managers charge $500-$1,500/month for the same thing. This is $25/month."
            ),
            "The posts will look fake / AI-generated": (
                "We train the AI on your actual voice and the way you talk about your work. "
                "During setup, you give us 5-10 example phrases you actually use. "
                "The posts sound like you typed them on a break, not like a marketing agency wrote them. "
                "You can reject any post that does not sound right."
            ),
        },
        "works_with": ["facebook_page", "google_business_profile", "instagram_business",
                        "buffer"],
    },

    # ── SALES & QUOTING ───────────────────────────────────────────────────────

    "quote_generator": {
        "name": "AI Quote Generator",
        "category": "Sales & Quoting",
        "description": (
            "Customer texts or emails a description (or photo) of their job. "
            "AI analyzes it and sends back a professional quote within 2 minutes. "
            "Saves 30-45 minutes per estimate. Owner can approve/adjust before it sends. "
            "Closes more jobs because prospects get instant answers instead of waiting 2 days. "
            "78% of customers hire the first business that responds with a number."
        ),
        "annual_value": 19200,         # 4 extra jobs/month closed due to instant response x $400 avg
        "monthly_cost": 35,
        "build_time_hours": 4,
        "difficulty": 3,
        "tools": ["n8n", "anthropic_claude", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair"],
        "integration": (
            "Customer texts your existing business number (or a dedicated quote line). "
            "The system receives the text via Twilio, runs it through AI with your pricing rules, "
            "and drafts a quote. You get a text with the draft — tap approve to send, or reply with "
            "changes. The final quote goes to the customer as a clean, professional text message. "
            "Photos of the job can be analyzed too (AI vision reads damage, scope, etc.). "
            "No app needed — it all works through regular text messages."
        ),
        "owner_effort": (
            "One-time: 45 minutes. This is the most involved setup because your pricing matters. "
            "You walk us through your pricing for every job type: 'drain clean is $150-$250, "
            "water heater install is $800-$2,500 depending on tank vs tankless.' "
            "The more specific you are, the more accurate the quotes. "
            "Ongoing: 30 seconds per quote — review the AI draft, tap approve or adjust the number. "
            "You MUST review every quote before it sends. This is not fully autonomous."
        ),
        "objections": {
            "What if the AI gives the wrong price?": (
                "Every quote goes through you first. The AI drafts it, you approve it. "
                "If the AI says $300 and you think it should be $450, you text back '450' and that is what sends. "
                "The AI never sends a price to a customer without your approval. "
                "Over time, the AI learns your pricing patterns and gets more accurate."
            ),
            "I need to see the job before I can quote it": (
                "For complex jobs, absolutely. The AI tells the customer: 'Based on your description, "
                "this is typically in the $X-$Y range. We will confirm the exact price after an on-site visit. "
                "Want to schedule one?' The AI gives a range, not a binding quote. "
                "The on-site visit still happens — the quote just gets the conversation started fast."
            ),
            "My prices depend on too many variables": (
                "That is why we set ranges, not fixed prices. 'Sewer line repair: $1,500-$8,000 depending on "
                "depth, length, and method.' The AI gives the range and asks the right follow-up questions "
                "to narrow it down. If the variables are too complex, the AI says 'this needs an on-site estimate' "
                "and books the visit."
            ),
            "Customers will hold me to the AI price": (
                "Every quote includes the line: 'This estimate is based on your description. Final price "
                "confirmed after on-site inspection.' This is standard in the industry. Customers understand. "
                "The alternative is taking 2 days to respond — by then they already hired someone else."
            ),
        },
        "works_with": ["any_phone_system", "any_email", "servicetitan", "housecall_pro",
                        "jobber", "quickbooks"],
    },

    "follow_up_sequence": {
        "name": "Lead Follow-Up Sequence",
        "category": "Sales & Quoting",
        "description": (
            "When a prospect contacts but does not book, they automatically get a 5-touch "
            "sequence over 10 days: text day 1, text day 3, email day 5, text day 7, "
            "final 'closing the file' text day 10. The 'closing the file' text alone "
            "recovers 8-12% of dead leads. Total sequence closes 15-25% of prospects who went cold."
        ),
        "annual_value": 14400,         # 10% more closes x 3 leads/day x $400 avg job
        "monthly_cost": 20,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
        "integration": (
            "Triggers automatically when a lead enters your pipeline but does not book within 24 hours. "
            "If you use the AI Phone Receptionist, it connects directly — no extra setup. "
            "If you use your own system, leads enter via a simple webhook (we give you a URL to paste "
            "into your CRM's 'new lead' notification, or you can forward lead notification emails to us). "
            "Texts go out from a local number with your business name."
        ),
        "owner_effort": (
            "One-time: 15 minutes. You approve the 5 follow-up messages. We write them, you tweak to "
            "match your voice. You set the offer for the 'closing the file' text (discount, free estimate, etc.). "
            "Ongoing: nothing unless a prospect replies. If they reply, you get a text and pick up the conversation. "
            "The sequence stops automatically when someone books or replies."
        ),
        "objections": {
            "I do not want to annoy people who said no": (
                "Most of them did not say no. They got busy. They got distracted. They called 3 plumbers "
                "and all 3 gave a price and then nobody followed up. The business that follows up wins. "
                "The sequence is polite and spaced out — 5 messages over 10 days, not 5 messages in a day. "
                "If someone says 'stop,' the sequence stops instantly and adds them to do-not-contact."
            ),
            "I already follow up with my leads": (
                "Every time? Every lead? Most contractors follow up with the big jobs and forget the $200 calls. "
                "This catches every single lead, including the ones you forgot. The math: if you get 3 leads/day "
                "and follow up manually with 1, you are losing 2/day. That is 60 lost leads per month."
            ),
            "What does the 'closing the file' text say?": (
                "Something like: 'Hey [name], we reached out a few times about your [job type] but have not heard "
                "back. No worries — we are closing your file. If you ever need help, just text this number.' "
                "It works because of loss aversion — people respond when they feel something is being taken away. "
                "This single text recovers more leads than the other 4 combined."
            ),
        },
        "works_with": ["any_phone_system", "any_crm", "servicetitan", "housecall_pro",
                        "jobber", "google_calendar"],
    },

    "lead_scoring": {
        "name": "AI Lead Scoring",
        "category": "Sales & Quoting",
        "description": (
            "Scores every inbound lead 1-10 based on: job type, timing urgency, "
            "location in service area, how they found the business, what they said. "
            "High-score leads (8+) get an immediate call-back alert to the owner. "
            "Low-score leads still get followed up — just not by you personally. "
            "Owner spends time on $2,000 jobs, not $75 drain snakes."
        ),
        "annual_value": 7200,          # Owner prioritizes better, closes more high-value jobs
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "anthropic_claude"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "law_firm", "real_estate"],
        "integration": (
            "Plugs into whatever captures your leads. If you use the AI Phone Receptionist, it scores "
            "automatically — zero extra work. If leads come from your website form, ServiceTitan, "
            "Housecall Pro, or email, we connect via webhook or email forwarding. "
            "Scores appear in your BOSS dashboard and you get a text for every 8+ score lead. "
            "Does not change how leads reach you — it just tells you which ones matter most."
        ),
        "owner_effort": (
            "One-time: 20 minutes. You tell us which job types are high-value vs low-value for your business. "
            "You define your ideal service area (zip codes or city radius). "
            "You rank urgency signals ('water flooding' = 10, 'thinking about remodeling' = 3). "
            "Ongoing: nothing. You get a text when a hot lead comes in. Check your dashboard when you want "
            "the full picture."
        ),
        "objections": {
            "I already know which leads are good": (
                "When you talk to them, yes. But can you tell from a missed call at 11pm? "
                "The AI listens to what the caller said, checks their location, checks the job type, "
                "and scores them before you even see the notification. You wake up and know: "
                "'call the 9 first, the 4 can wait.'"
            ),
            "What if it scores a good lead low?": (
                "Every lead still gets followed up — scoring does not drop anyone. "
                "A low score means the AI thinks it is lower priority, but you can always override. "
                "After a few weeks, you review the scores vs actual job values and we retune. "
                "The system learns your business over time."
            ),
            "I treat every customer the same": (
                "That is admirable. But your time is not infinite. If you have 8 leads and 2 hours, "
                "calling the $3,000 AC install first and the $75 filter change last is not bad service — "
                "it is smart business. Both customers get called. One just gets called faster."
            ),
        },
        "works_with": ["any_crm", "servicetitan", "housecall_pro", "jobber",
                        "google_calendar", "any_phone_system"],
    },

    "proposal_generator": {
        "name": "AI Proposal Generator",
        "category": "Sales & Quoting",
        "description": (
            "For larger jobs ($1,000+), AI generates a professional PDF proposal: "
            "scope of work, pricing breakdown, timeline, warranty, payment terms. "
            "Sends automatically after the estimate call or on demand. "
            "Looks 10x more professional than handwritten quotes on the back of an invoice. "
            "Contractors who send professional proposals close 30% more big jobs."
        ),
        "annual_value": 9600,          # Higher close rate on big jobs due to professionalism
        "monthly_cost": 20,
        "build_time_hours": 3,
        "difficulty": 3,
        "tools": ["n8n", "anthropic_claude"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "law_firm"],
        "integration": (
            "You text us the job details after your estimate visit: customer name, address, job scope, "
            "price, and timeline. The AI generates a branded PDF proposal with your company logo, "
            "license number, warranty terms, and payment options. You review and tap approve — "
            "it sends to the customer via text and email. If you use ServiceTitan or Housecall Pro, "
            "we can pull job details directly and auto-generate the proposal."
        ),
        "owner_effort": (
            "One-time: 30 minutes. You provide your company logo, license/insurance info, standard "
            "warranty terms, and payment terms. We build your proposal template. "
            "Ongoing: 2-3 minutes per proposal. After your estimate visit, you text the job details. "
            "Review the PDF, tap approve. Honest note: you still have to do the estimate visit and "
            "determine the price — the AI just makes the paperwork fast and professional."
        ),
        "objections": {
            "I just tell them the price on the spot": (
                "For small jobs, that works. For a $5,000 AC install or a $15,000 rewire, the homeowner "
                "is comparing 3 bids. The contractor who sends a professional PDF with line items, warranty, "
                "and a payment plan wins over the guy who wrote a number on the back of a business card. "
                "The proposal justifies the price."
            ),
            "I do not have time to mess with documents": (
                "You text us 3 sentences: 'John Smith, 123 Main St, full panel upgrade, $4,800, 2-day job.' "
                "You get back a professional PDF in 90 seconds. Total time: under 3 minutes. "
                "Compare that to 30-45 minutes hand-writing a proposal in Word."
            ),
            "My customers do not care about fancy proposals": (
                "The customer might not. Their spouse does. When the homeowner tells their wife 'the electrician "
                "wants $4,800,' and she asks to see the quote, handing her a professional document with scope, "
                "warranty, and payment plan closes the deal. A text message with just a number does not."
            ),
        },
        "works_with": ["servicetitan", "housecall_pro", "jobber", "quickbooks",
                        "any_email", "any_phone_system"],
    },

    # ── OPERATIONS ────────────────────────────────────────────────────────────

    "appointment_booking": {
        "name": "Appointment Booking Automation",
        "category": "Operations",
        "description": (
            "Integrates with Google Calendar (or any calendar). "
            "AI books appointments directly into the calendar, sends "
            "customer a confirmation text with date/time/address, "
            "sends a reminder text 24 hours before, another 2 hours before. "
            "Reduces no-shows by 40%. Customers can reschedule by replying to the text."
        ),
        "annual_value": 6000,          # 2 fewer no-shows/month x $250 avg
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_calendar", "twilio"],
        "applies_to": ["all"],
        "integration": (
            "Connects directly to Google Calendar via API (one-click authorization). "
            "Also works with Outlook/Office 365 calendars and Apple Calendar (via CalDAV). "
            "If you use ServiceTitan or Housecall Pro, we book into their scheduler instead. "
            "The AI reads your calendar to check availability before offering time slots — "
            "no double-booking. Confirmation and reminder texts go from your business number via Twilio."
        ),
        "owner_effort": (
            "One-time: 10 minutes. You connect your calendar and set your available hours "
            "(e.g., 8am-5pm Mon-Fri, no Sundays). You set job duration defaults "
            "(e.g., AC tune-up = 1 hour, full install = 4 hours). "
            "Ongoing: nothing. Appointments appear on your calendar automatically. "
            "If a customer reschedules via text, the calendar updates and you see the change."
        ),
        "objections": {
            "I use ServiceTitan for scheduling": (
                "We can push appointments to ServiceTitan via their API or via email-to-job. "
                "Or we book into Google Calendar and you sync that with ServiceTitan — "
                "ServiceTitan has a native Google Calendar integration. Either way works."
            ),
            "What if the AI double-books me?": (
                "The AI checks your calendar in real-time before offering any slot. "
                "If 2pm Tuesday is taken, it does not offer 2pm Tuesday. "
                "If two customers call at the exact same second, the system locks the slot — "
                "first one gets it, second one gets the next available."
            ),
            "My schedule changes all the time": (
                "Then block time on your calendar when it changes. The AI only offers open slots. "
                "If you finish a job early and open up 3pm, the AI immediately starts offering 3pm. "
                "It reads your calendar live, not a cached copy."
            ),
        },
        "works_with": ["google_calendar", "outlook_calendar", "apple_calendar",
                        "servicetitan", "housecall_pro", "jobber"],
    },

    "dispatch_automation": {
        "name": "Dispatch Automation",
        "category": "Operations",
        "description": (
            "When a job is booked, automatically assigns it to the right crew "
            "based on location, skill type, and current schedule. "
            "Sends each crew member their daily job list at 7am via text with addresses in order. "
            "Optimizes route to minimize drive time. Owner stops being a dispatcher."
        ),
        "annual_value": 14400,         # Owner saves 2 hrs/day x $40/hr equivalent
        "monthly_cost": 30,
        "build_time_hours": 4,
        "difficulty": 3,
        "tools": ["n8n", "google_maps", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care"],
        "integration": (
            "Reads jobs from your calendar (Google Calendar, Outlook, or CRM scheduler). "
            "Uses Google Maps API to calculate drive times and optimize route order. "
            "Each crew member gets a 7am text with their jobs listed in drive-time order, "
            "including addresses and customer phone numbers. If you use ServiceTitan or Housecall Pro, "
            "we read the schedule from there instead. Crew members need a cell phone that receives texts — "
            "no app install needed."
        ),
        "owner_effort": (
            "One-time: 30 minutes. You list your crew members (names + phone numbers), their skills "
            "(e.g., 'Mike does installs, Juan does maintenance'), and your service area. "
            "Ongoing: Honest answer — you still need to book the jobs. Once booked, dispatch is automatic. "
            "If a job gets rescheduled or cancelled, update the calendar and the next day's dispatch adjusts. "
            "This works best for businesses with 2+ crews. Solo operators get less value."
        ),
        "objections": {
            "My guys do not follow a schedule": (
                "That is a management problem, not a software problem. But a 7am text with 'here are your "
                "5 jobs today in order' is a lot harder to ignore than a verbal rundown at the shop. "
                "The text has addresses they can tap to open in Maps. Makes it easier to follow the schedule."
            ),
            "I already dispatch through ServiceTitan": (
                "ServiceTitan dispatch is excellent. This adds route optimization on top — "
                "ordering the jobs by drive time so your crews spend less time in the truck. "
                "It also adds the 7am text summary so crews do not have to open the app to see their day. "
                "If ServiceTitan already does everything you need, you do not need this."
            ),
            "What if a job runs long and the schedule shifts?": (
                "The dispatch updates when the calendar updates. If a job runs 2 hours over and you push "
                "the next appointment, the system recalculates. The customer gets notified of the new time. "
                "But real-time mid-day rescheduling still requires you to make the call — the AI handles "
                "the logistics, not the judgment calls."
            ),
        },
        "works_with": ["google_calendar", "google_maps", "servicetitan", "housecall_pro",
                        "jobber", "outlook_calendar"],
    },

    "job_status_updates": {
        "name": "Automated Job Status Texts",
        "category": "Operations",
        "description": (
            "Customers automatically receive texts at each job milestone: "
            "'Your tech is on the way — about 20 min out,' 'Job is starting now,' 'All done — "
            "here is what we did.' Reduces 'where are you' calls by 80%. "
            "Customers feel informed and in control. Informed customers leave 5-star reviews."
        ),
        "annual_value": 4800,          # Reduces owner phone time + drives review volume
        "monthly_cost": 12,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair"],
        "integration": (
            "Triggered by simple text commands from the tech or crew leader. "
            "Tech texts 'otw 123 main st' and the customer at that address gets 'Your tech is on the way.' "
            "Tech texts 'start' when they arrive, 'done' when finished. Three texts, three triggers. "
            "If you use ServiceTitan or Housecall Pro, we can trigger off their job status changes "
            "instead — no manual texts needed. Customer texts come from your business number."
        ),
        "owner_effort": (
            "One-time: 10 minutes. You approve the status messages and set up your tech's phone numbers. "
            "Ongoing: Your techs send 3 keyword texts per job (otw, start, done). Takes 10 seconds each. "
            "Honest note: this requires your techs to actually send those texts. If they will not do it, "
            "this automation will not work. The CRM-triggered version (ServiceTitan/HCP) removes that requirement."
        ),
        "objections": {
            "My guys will not remember to text": (
                "Valid concern. Two options: 1) Make it part of the job checklist — no 'done' text, "
                "no moving to the next job. 2) Use the CRM-triggered version where status changes in "
                "ServiceTitan or Housecall Pro fire the texts automatically. Option 2 costs the same."
            ),
            "Customers do not need that much hand-holding": (
                "You would be surprised. The #1 complaint on 1-3 star reviews for service businesses is "
                "'they said 8am-12pm and nobody showed up until 2pm with no communication.' "
                "A 20-second text prevents a 1-star review. Uber and Amazon trained customers to expect updates."
            ),
            "What if we are running behind?": (
                "If the tech has not sent 'otw' within the appointment window, the system can auto-send: "
                "'Running a bit behind schedule — we will update you with a new ETA shortly.' "
                "Proactive communication about delays gets better reviews than perfect timeliness with no updates."
            ),
        },
        "works_with": ["any_phone_system", "servicetitan", "housecall_pro", "jobber",
                        "google_calendar"],
    },

    "invoice_generator": {
        "name": "Auto Invoice Generator",
        "category": "Operations",
        "description": (
            "When a job is marked complete, AI instantly creates a professional invoice "
            "and texts/emails it to the customer. "
            "Pre-filled with their info, job details, line items, and payment link. "
            "Owner stops writing invoices by hand or forgetting to send them. "
            "The average contractor has $8,000-$15,000 in unsent invoices at any given time."
        ),
        "annual_value": 7200,          # Faster payment + fewer forgotten invoices
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "venmo", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair", "law_firm"],
        "integration": (
            "Triggers when a job is marked 'done' — either by the tech texting 'done' (if using job status "
            "updates), by status change in your CRM (ServiceTitan, Housecall Pro, Jobber), or by you texting "
            "'invoice [customer] [amount]'. The invoice is generated from a template with your business info, "
            "sent to the customer via text with a payment link (Venmo, Zelle, or card). "
            "If you use QuickBooks, we can push the invoice there too for your bookkeeper."
        ),
        "owner_effort": (
            "One-time: 20 minutes. You provide your business info (name, address, license, tax ID if applicable), "
            "your payment methods (Venmo, Zelle, card link), and standard line items for common jobs. "
            "Ongoing: For simple jobs, nothing — the invoice auto-sends. For complex jobs, you may need to "
            "adjust line items before it sends (30 seconds via text reply). "
            "Honest note: if your pricing is highly custom per job, you will need to text the final amount."
        ),
        "objections": {
            "I use QuickBooks for invoicing": (
                "This does not replace QuickBooks. It gets the invoice to the customer faster. "
                "Most contractors finish a job, drive to the next one, and do not send the invoice "
                "until they sit down at their desk 3 days later. This sends it in 60 seconds. "
                "We can also push the invoice to QuickBooks so your books stay clean."
            ),
            "What if the amount is wrong?": (
                "For standard jobs with known prices, the amount comes from your pricing rules. "
                "For custom jobs, you text the final amount and it populates. "
                "Every invoice goes to the customer — not to you for approval — because speed matters. "
                "But if you want an approval step, we add it. Approval takes 10 seconds via text."
            ),
            "My customers pay on the spot": (
                "Great — then you do not need this for those customers. But what about the ones who say "
                "'can you send me an invoice?' If 20% of your customers pay later, and you forget to send "
                "3 invoices a month at $400 each, that is $1,200/month lost. This catches every one."
            ),
        },
        "works_with": ["quickbooks", "servicetitan", "housecall_pro", "jobber",
                        "venmo", "zelle", "any_payment_processor"],
    },

    "payment_collection": {
        "name": "Payment Collection Automation",
        "category": "Operations",
        "description": (
            "When job completes, customer automatically gets a text with a payment link. "
            "If not paid in 24 hours, a friendly reminder. If not paid in 72 hours, owner gets alerted. "
            "Reduces unpaid invoices by 60%. "
            "Average time-to-payment drops from 14 days to 2 days. "
            "The texts are polite — this is not collections agency stuff."
        ),
        "annual_value": 8400,          # Faster collections + fewer write-offs
        "monthly_cost": 15,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "venmo", "twilio"],
        "applies_to": ["all"],
        "integration": (
            "Triggers after job completion (from job status update, CRM status change, or your text command). "
            "Customer gets a text with a tap-to-pay link — Venmo, Zelle, or card payment page. "
            "No app needed on the customer side. Just a text message with a link. "
            "If the customer pays through your CRM or in cash, you text 'paid [customer]' and the "
            "reminders stop. Integrates with the Invoice Generator if both are active."
        ),
        "owner_effort": (
            "One-time: 10 minutes. You set up your payment link (Venmo, Zelle, Stripe, Square — whatever "
            "you use) and approve the reminder messages. "
            "Ongoing: nothing for most customers. When someone does not pay after 72 hours, you get a text "
            "and you handle it personally. The automation handles the first 3 days; you handle the exceptions."
        ),
        "objections": {
            "I collect payment on the spot": (
                "Most contractors do for residential. But commercial accounts, insurance jobs, and customers "
                "who say 'bill me' need follow-up. If even 10% of your jobs have delayed payment, "
                "this pays for itself in the first month by collecting those faster."
            ),
            "I do not want to harass my customers": (
                "The messages are polite: 'Hi [name], just a reminder about your invoice from [date]. "
                "Here is the payment link: [link]. Let us know if you have any questions.' "
                "That is not harassment — that is how every dentist, doctor, and utility company operates. "
                "One reminder at 24 hours, one at 72 hours. That is it."
            ),
            "What if they dispute the charge?": (
                "The system does not handle disputes — you do. If a customer replies to the text with a question "
                "or complaint, you get forwarded the message and handle it personally. "
                "The automation only handles the routine 'hey, here is your bill' step."
            ),
        },
        "works_with": ["venmo", "zelle", "stripe", "square", "quickbooks",
                        "any_payment_processor", "servicetitan", "housecall_pro", "jobber"],
    },

    # ── CUSTOMER RETENTION ────────────────────────────────────────────────────

    "review_request": {
        "name": "Review Request Automation",
        "category": "Customer Retention",
        "description": (
            "2 hours after payment confirmed, customer automatically gets a text: "
            "'Hi [name]! It was great working with you. Would you mind leaving us "
            "a quick Google review? It means everything to a local business. [direct link]' "
            "Converts 25-35% of customers into reviewers. "
            "Reviews are the #1 driver of inbound calls for service businesses. "
            "Every 10 new reviews increases your call volume measurably."
        ),
        "annual_value": 18000,         # Reviews compound — $1,500/month more revenue at scale
        "monthly_cost": 10,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
        "integration": (
            "Triggers 2 hours after payment is confirmed (from payment collection automation, "
            "CRM payment status, or your text command 'paid [customer]'). "
            "The text includes a direct Google review link — customer taps it, Google review form opens, "
            "they type and post. No searching for your business, no extra steps. "
            "We generate your direct review link during setup from your Google Business Profile."
        ),
        "owner_effort": (
            "One-time: 5 minutes. You give us your Google Business Profile name (we find the direct review "
            "link) and approve the review request message. "
            "Ongoing: literally nothing. The text sends itself after every payment. "
            "If you want to send review requests for cash-pay customers, text 'review [customer phone]' "
            "and it fires manually."
        ),
        "objections": {
            "I already ask for reviews": (
                "In person? Great. How many actually follow through? Most contractors ask at the job site, "
                "the customer says 'sure,' goes home, and forgets. A text 2 hours later with a direct link "
                "catches them while the experience is still fresh. One tap, 30 seconds, done. "
                "The direct link is the key — no searching, no friction."
            ),
            "What if I get a bad review from this?": (
                "Unhappy customers leave reviews without being asked. Happy customers need a nudge. "
                "By asking every customer, you are stacking the deck with happy reviews. "
                "If a customer is unhappy, they were going to leave a bad review anyway — at least now "
                "you have 30 good reviews to drown it out instead of 5."
            ),
            "Google does not like automated review requests": (
                "Google prohibits review gating (only sending requests to happy customers) and "
                "incentivized reviews (offering discounts for reviews). We do neither. "
                "We send every customer the same request with no incentive. "
                "That is 100% compliant with Google's terms of service."
            ),
        },
        "works_with": ["google_business_profile", "any_payment_processor", "any_crm",
                        "servicetitan", "housecall_pro", "jobber"],
    },

    "re_engagement_campaign": {
        "name": "Re-Engagement Campaigns",
        "category": "Customer Retention",
        "description": (
            "Every customer who has not hired the business in 90 days gets "
            "a personalized text: 'Hey [name], it has been a few months — "
            "how is [thing we fixed] holding up? We are running a [seasonal] special.' "
            "Reactivates 10-15% of dormant customers. "
            "The cheapest customer to get is one you already have. "
            "Acquiring a new customer costs 5-7x more than retaining an existing one."
        ),
        "annual_value": 12000,         # 1 job/month recovered x $1,000 avg job value
        "monthly_cost": 20,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio", "anthropic_claude"],
        "applies_to": ["all"],
        "integration": (
            "Reads your customer list from Google Sheets, your CRM (ServiceTitan, Housecall Pro, Jobber), "
            "or the BOSS dashboard. Tracks last service date for every customer. "
            "At the 90-day mark, AI generates a personalized text based on what you did for them last time "
            "(e.g., 'How is that new water heater treating you?'). Text goes from your business number. "
            "If you do not have a digital customer list, we build one from your past job records during setup."
        ),
        "owner_effort": (
            "One-time: 15-30 minutes. You provide your customer list (even a handwritten one works — "
            "we digitize it). You set the re-engagement interval (default 90 days) and approve the "
            "message templates. If you have a seasonal special you want to promote, tell us. "
            "Ongoing: nothing. The system checks daily and sends texts automatically. "
            "If a customer replies, you get the message and handle the conversation."
        ),
        "objections": {
            "I do not have a customer list": (
                "We can build one. If you have old invoices, a QuickBooks export, a ServiceTitan history, "
                "or even a stack of handwritten receipts, we digitize it. Going forward, every new customer "
                "from the AI receptionist or booking system automatically gets added. "
                "Start with what you have, even if it is 20 customers."
            ),
            "I do not want to seem desperate": (
                "The text does not say 'please hire us again.' It says 'how is [thing] holding up?' "
                "That is a genuine check-in. It positions you as a business that cares about quality, "
                "not one that is begging for work. Most customers appreciate the follow-up. "
                "10-15% respond with a new job. The rest just feel remembered."
            ),
            "My customers call me when they need me": (
                "Some do. Most do not — they call whoever shows up first in Google. "
                "A text at the 90-day mark puts your name back in their phone right when "
                "their AC filter needs changing or their lawn needs the seasonal treatment. "
                "The customer who was going to call you anyway still calls you. "
                "The customer who forgot about you now remembers."
            ),
        },
        "works_with": ["google_sheets", "servicetitan", "housecall_pro", "jobber",
                        "quickbooks", "any_crm"],
    },

    "seasonal_campaigns": {
        "name": "Seasonal Campaign Calendar (12/year)",
        "category": "Customer Retention",
        "description": (
            "12 pre-written campaigns run automatically throughout the year, timed to your trade: "
            "HVAC gets spring AC tune-up and fall furnace check. Plumbers get winter pipe protection. "
            "Roofers get post-storm outreach. Each campaign texts all past customers "
            "with a timely, relevant offer. Runs itself — owner does nothing all year."
        ),
        "annual_value": 24000,         # 2 jobs/month from campaigns x avg job x 12 months
        "monthly_cost": 25,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["n8n", "twilio", "anthropic_claude"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "cleaning",
                        "pest_control", "lawn_care", "auto_repair"],
        "integration": (
            "Reads your customer list from Google Sheets, CRM, or the BOSS dashboard. "
            "Campaigns are pre-scheduled for the entire year during setup — you set it and forget it. "
            "Each campaign sends a text from your business number to all past customers. "
            "If you want to change a campaign or add a flash sale, text us and we update it same day. "
            "Pairs naturally with the re-engagement campaign — seasonal campaigns target everyone, "
            "re-engagement targets only dormant customers."
        ),
        "owner_effort": (
            "One-time: 30 minutes. You review and approve all 12 campaigns during setup. "
            "We write them based on your trade and your service area's climate/seasons. "
            "You tell us your seasonal specials (e.g., '$79 spring AC tune-up'). "
            "Ongoing: nothing for the standard 12. If you want to add a flash campaign "
            "(e.g., after a big storm), text us and we push one out same day. "
            "You should update your seasonal pricing each year — takes 10 minutes."
        ),
        "objections": {
            "I do not want to text customers 12 times a year": (
                "It is once a month. Your dentist sends you a reminder every 6 months. "
                "Your oil change place sends one every 3 months. Once a month with a relevant, "
                "seasonal offer is not excessive — it is what good businesses do. "
                "The unsubscribe rate on seasonal service texts is under 2%."
            ),
            "What if my specials change?": (
                "Text us the new pricing and we update the campaign within 24 hours. "
                "The campaigns are not set in stone. We recommend reviewing them once a year "
                "(takes 10 minutes) to update pricing and offers."
            ),
            "I do not run seasonal specials": (
                "You do not have to discount. The campaign can just be a reminder: "
                "'Fall is here — time to check your furnace before the first cold snap. "
                "Want us to get you on the schedule?' No discount needed. "
                "The value is the timely reminder, not the price cut."
            ),
        },
        "works_with": ["google_sheets", "servicetitan", "housecall_pro", "jobber",
                        "any_crm", "any_phone_system"],
    },

    "referral_program": {
        "name": "Automated Referral Program",
        "category": "Customer Retention",
        "description": (
            "After every completed job, customer gets a text: "
            "'Know anyone who needs [service]? Send them our way and we will take "
            "$25 off their next visit — and yours.' "
            "Tracks referrals automatically — when the new customer mentions who sent them, "
            "both get credited. Word of mouth is the #1 lead source for service businesses. "
            "This systematizes it instead of hoping customers remember to mention you."
        ),
        "annual_value": 9600,          # 0.8 referrals/month x avg job value
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
        "integration": (
            "Triggers after job completion (same trigger as review request — they can fire in sequence). "
            "Customer gets a text with a referral message they can forward. When the referred person calls "
            "or texts, the AI receptionist asks 'who referred you?' and logs the referral. "
            "The original customer automatically gets a text: 'Thanks for the referral! $25 off your next service.' "
            "Referral tracking is stored in Google Sheets or your CRM. You decide the referral reward amount."
        ),
        "owner_effort": (
            "One-time: 10 minutes. You set your referral reward amount ($25 off is the default — "
            "you can do more or less) and approve the referral message. "
            "Ongoing: nothing automated. But honest note — you need to actually honor the discounts. "
            "When a referred customer books, apply the $25 off for both parties. "
            "If you forget, the system reminds you via text."
        ),
        "objections": {
            "I already get referrals": (
                "Great — now imagine if you asked for them every single time, automatically, "
                "with an incentive attached. Most contractors get referrals passively. "
                "An active program with a built-in reward generates 3-5x more referrals. "
                "Even one extra referral per month at your average job value pays for a year of this."
            ),
            "I do not want to give discounts": (
                "Then do not. Change the reward to anything: 'free priority scheduling next time,' "
                "'$25 gift card to [local restaurant],' or just a thank-you text. "
                "The ask is more important than the reward. Most customers refer because they like you, "
                "not because of $25. The reward just reminds them to actually do it."
            ),
            "How does the tracking work?": (
                "When the new customer calls, the AI asks 'how did you hear about us?' "
                "If they say a name, it matches against your customer list. If it matches, "
                "both get credited automatically. If the new customer texts your number, "
                "they can include 'referred by [name].' It is not perfect — some referrals will "
                "not be tracked — but it catches most of them without any effort from you."
            ),
        },
        "works_with": ["any_phone_system", "google_sheets", "servicetitan",
                        "housecall_pro", "jobber", "any_crm"],
    },

    "birthday_outreach": {
        "name": "Birthday / Anniversary Outreach",
        "category": "Customer Retention",
        "description": (
            "Sends a personal text on each customer's birthday or job anniversary: "
            "'Happy birthday from [business]! Use code BDAY for $20 off your next service.' "
            "Makes customers feel remembered by a business they already trust. "
            "Birthday texts have a 98% open rate and 8x the response rate of normal campaigns. "
            "Nobody else in your market is doing this."
        ),
        "annual_value": 3600,          # Low cost, high conversion on warmest customers
        "monthly_cost": 8,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
        "integration": (
            "Reads customer birthdays from your customer list (Google Sheets, CRM, or BOSS dashboard). "
            "Checks daily for upcoming birthdays and sends the text on the morning of. "
            "If you do not have birthdays on file, the system can use the job anniversary date instead "
            "(the date you first did work for them). Text goes from your business number."
        ),
        "owner_effort": (
            "One-time: 10 minutes. You approve the birthday message and set the discount code/amount. "
            "Ongoing: nothing. "
            "Honest note: This works best when you actually collect customer birthdays. "
            "If you do not have them, use job anniversary dates (the system already knows those). "
            "Going forward, the AI receptionist can ask 'and when is your birthday?' during booking."
        ),
        "objections": {
            "I do not know my customers' birthdays": (
                "Use their service anniversary instead — the date of their first job with you. "
                "'Hey [name], it has been 1 year since we installed your AC! How is it running? "
                "Here is $20 off your next service.' Same effect, data you already have."
            ),
            "That seems like a lot of texts for a small thing": (
                "It is one text per customer per year. You have 200 customers? That is 200 texts across "
                "365 days — less than one per day. The cost is about $0.01 per text. "
                "If even 5% of those customers book a job from it, that is 10 extra jobs per year."
            ),
            "My customers will think it is weird": (
                "Your barber remembers your birthday. Your dentist sends a card. Your insurance agent calls. "
                "A birthday text from your HVAC company is unexpected — and that is exactly why it works. "
                "It stands out because nobody else in your industry does it."
            ),
        },
        "works_with": ["google_sheets", "servicetitan", "housecall_pro", "jobber",
                        "any_crm"],
    },

    # ── INTELLIGENCE ──────────────────────────────────────────────────────────

    "revenue_dashboard": {
        "name": "Real-Time Revenue Dashboard",
        "category": "Intelligence",
        "description": (
            "Live dashboard showing: today's revenue, jobs booked vs. completed, "
            "monthly trend, top job types, customer acquisition sources, "
            "review count trend, and crew performance. "
            "Owner knows the score at a glance instead of doing mental math. "
            "Accessible from your phone — no app needed, just a browser bookmark."
        ),
        "annual_value": 6000,          # Better decisions + time saved on bookkeeping
        "monthly_cost": 20,
        "build_time_hours": 4,
        "difficulty": 3,
        "tools": ["n8n", "google_sheets"],
        "applies_to": ["all"],
        "integration": (
            "Pulls data from all your BOSS automations into one dashboard. Revenue from invoices/payments, "
            "jobs booked from the calendar, reviews from Google, crew data from job completions. "
            "If you use ServiceTitan or Housecall Pro, we pull data from there too. "
            "Dashboard is a password-protected web page — works on phone, tablet, or desktop. "
            "Data updates every time a job is booked, completed, or paid."
        ),
        "owner_effort": (
            "One-time: 20 minutes. You connect your data sources (we handle the technical part) "
            "and tell us which metrics matter most to you. We build the dashboard to show what you "
            "actually care about — not 50 charts you will never read. "
            "Ongoing: nothing to maintain. Just open the dashboard when you want to check the numbers. "
            "Honest note: the dashboard is only as good as the data feeding it. If your job records "
            "are incomplete, the dashboard will be incomplete. It works best with 3+ other BOSS automations active."
        ),
        "objections": {
            "I already know how my business is doing": (
                "Do you know your average job value this month vs last month? Do you know which job type "
                "makes you the most money? Do you know which lead source produces the best customers? "
                "Most owners know the big picture but miss the trends. The dashboard shows trends, "
                "not just today's numbers."
            ),
            "I use QuickBooks / ServiceTitan for reporting": (
                "Those tools show you financial data. This dashboard shows you operational data: "
                "jobs booked vs completed today, which crew is performing best, review velocity, "
                "lead source effectiveness. It is a different view — the 'how is my business doing right now' "
                "view, not the 'how did last quarter look' view."
            ),
            "I do not want another thing to check": (
                "Then do not check it daily. Open it once a week on Monday morning. "
                "The dashboard also sends you a weekly summary text every Monday at 7am: "
                "'Last week: 23 jobs, $8,400 revenue, 3 new reviews, 2 referrals.' "
                "You do not have to open anything if you do not want to."
            ),
        },
        "works_with": ["google_sheets", "google_calendar", "servicetitan", "housecall_pro",
                        "jobber", "quickbooks", "google_business_profile"],
    },

    "competitor_monitor": {
        "name": "Competitor Intelligence Monitor",
        "category": "Intelligence",
        "description": (
            "Weekly report on every major competitor: new reviews, rating changes, "
            "price changes, new service offerings, Google ranking shifts. "
            "Alerts you immediately if a competitor drops below 4.0 stars "
            "(opportunity to target their unhappy customers). Full report delivered every Monday. "
            "Know what your competition is doing before your customers tell you."
        ),
        "annual_value": 4800,          # Catch competitive threats and opportunities early
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_places"],
        "applies_to": ["all"],
        "integration": (
            "Fully standalone — no connection to your phone, CRM, or systems needed. "
            "Runs weekly on our servers using the Google Places API. Scans your competitors' "
            "Google Business Profiles for changes. Report delivered via text every Monday morning. "
            "You can also view the report in your BOSS dashboard. "
            "Pairs with Review Mining — the monitor tracks competitors, Review Mining identifies "
            "specific unhappy customers to target."
        ),
        "owner_effort": (
            "One-time: 5 minutes. You list 3-10 local competitors by name. "
            "Ongoing: 5 minutes/week reading the Monday report. That is it. "
            "Honest note: the intelligence is only valuable if you act on it. "
            "When a competitor gets a string of bad reviews, that is your window to run ads "
            "in their territory or send postcards to their area."
        ),
        "objections": {
            "I already know my competitors": (
                "You know who they are. Do you know that their star rating dropped from 4.3 to 3.9 "
                "this month? Do you know they stopped responding to reviews? Do you know they added "
                "a new service you do not offer? This gives you the play-by-play, not just the roster."
            ),
            "What am I supposed to do with this information?": (
                "Three things: 1) When a competitor gets bad reviews, run targeted postcards in their area. "
                "2) When a competitor raises prices (visible from review complaints), hold your prices and "
                "mention it in your ads. 3) When a competitor adds a service, decide if you should too. "
                "Intelligence without action is useless — but bad decisions from ignorance are worse."
            ),
            "This sounds like spying": (
                "Every review on Google is public. Every business profile is public. "
                "Your competitors are already looking at your reviews. This just automates the looking "
                "so you do not have to manually search 10 competitors every week. "
                "It is the same information anyone can see — just organized and delivered to you."
            ),
        },
        "works_with": ["google_business_profile", "google_sheets", "any_email"],
    },

    "employee_tracking": {
        "name": "Employee Performance Tracker",
        "category": "Intelligence",
        "description": (
            "Tracks: jobs completed per crew member, average job rating, "
            "on-time arrival rate, callbacks/complaints per tech. "
            "Weekly report to owner every Monday. Top performers get recognized. "
            "Problem techs get addressed before they cost you a customer — or a lawsuit."
        ),
        "annual_value": 7200,          # Retaining good techs + pruning bad ones saves money
        "monthly_cost": 15,
        "build_time_hours": 3,
        "difficulty": 3,
        "tools": ["n8n", "google_sheets"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "cleaning",
                        "pest_control", "lawn_care"],
        "integration": (
            "Pulls data from your job records — Google Sheets, ServiceTitan, Housecall Pro, or Jobber. "
            "If you use the Job Status Updates automation, it automatically logs on-time arrivals per tech. "
            "Customer review scores are pulled from Google and matched to the tech who did the job. "
            "Weekly report delivered via text every Monday with: top performer, most callbacks, "
            "on-time percentage per crew member. Detailed breakdown available in the BOSS dashboard."
        ),
        "owner_effort": (
            "One-time: 20 minutes. You list your crew members and assign them to job records "
            "(or we set up the tracking going forward). You define what 'on-time' means for your business. "
            "Ongoing: nothing if your CRM tracks job assignments automatically. "
            "If you do not use a CRM, your office manager or you need to log which tech did which job. "
            "Honest note: this system is only as accurate as your job assignment records. "
            "If you do not track who did what, we cannot report on it."
        ),
        "objections": {
            "My guys will not like being tracked": (
                "You are not tracking their location or their breaks. You are tracking job completion, "
                "on-time rate, and customer satisfaction — the same things you would check if you "
                "rode along with them every day. Good techs will not mind because they are already doing well. "
                "The ones who mind are usually the ones you need to watch."
            ),
            "I only have 2 employees": (
                "Then the report is simple: who is doing better this week and why. "
                "Even with 2 techs, knowing that one has a 95% on-time rate and the other has 70% "
                "tells you something. But honestly, this system shines with 4+ crew members "
                "where you cannot personally oversee everyone."
            ),
            "I already know who my good and bad techs are": (
                "You know who you like and who frustrates you. Do you know the numbers? "
                "'Mike does 12 jobs/week with 0 callbacks, Juan does 8 jobs/week with 2 callbacks' "
                "is more useful than a gut feeling. Numbers help you justify decisions — "
                "especially when you need to fire someone and want documentation."
            ),
        },
        "works_with": ["google_sheets", "servicetitan", "housecall_pro", "jobber",
                        "google_business_profile"],
    },

    "inventory_alerts": {
        "name": "Inventory and Supply Alerts",
        "category": "Intelligence",
        "description": (
            "Owner texts a simple command ('filters low — 10 left') "
            "and the system logs it. When stock hits reorder threshold, "
            "owner gets an alert with a direct order link to their supplier. "
            "Never run out of filters, freon, capacitors, or fittings mid-job again. "
            "One emergency supply run costs $50-$100 in lost time and markup — this prevents all of them."
        ),
        "annual_value": 3600,          # Prevents emergency supply runs and job delays
        "monthly_cost": 8,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "pest_control"],
        "integration": (
            "Text-based — no app, no barcode scanner, no POS system needed. "
            "Owner or tech texts 'filters 10' or 'freon low' to the system number. "
            "The system logs the item and quantity. When quantity hits the reorder threshold "
            "you set (e.g., 'alert me when filters drop below 5'), you get a text with "
            "a link to your preferred supplier's website. Tracks items in a Google Sheet "
            "you can view anytime."
        ),
        "owner_effort": (
            "One-time: 15 minutes. You list the items you want to track (filters, freon, common parts) "
            "and set reorder thresholds for each. You provide your preferred supplier links. "
            "Ongoing: you or your techs need to text updates when you use supplies. "
            "'Used 2 filters' takes 5 seconds. Honest note: this is a manual-input system. "
            "If nobody texts the updates, the tracking will not be accurate. "
            "It works best for high-value items you buy regularly (filters, freon, capacitors) — "
            "not for every screw and fitting."
        ),
        "objections": {
            "I just order when I run out": (
                "And when you run out mid-job? You drive 30 minutes to the supply house, "
                "pay retail instead of bulk pricing, and the customer waits. "
                "One emergency supply run costs $50-$100 in time and markup. "
                "This prevents that by alerting you before you hit zero."
            ),
            "My supply house delivers next day": (
                "Perfect — then the alert just needs to fire one day before you run out. "
                "Set the threshold to 'alert at 2-day supply remaining' and place the order when alerted. "
                "The system does not order for you — it just makes sure you never forget to order."
            ),
            "This seems too simple to be worth paying for": (
                "It is simple. That is the point. You do not need a $500/month inventory management system "
                "to track 10 items. You need a text reminder before you run out of the thing "
                "that stops a $2,000 job from getting completed. The cost is $8/month. "
                "One prevented emergency run pays for a year."
            ),
        },
        "works_with": ["google_sheets", "any_phone_system"],
    },

    "review_response_ai": {
        "name": "AI Review Response System",
        "category": "Intelligence",
        "description": (
            "When a new Google review comes in, AI drafts a personalized response "
            "and sends it to owner for 1-tap approval. "
            "For 5-star reviews: thanks them by name and highlights the specific work done. "
            "For 1-3 star reviews: de-escalates, offers resolution, drafts professionally. "
            "Businesses that respond to every review get 35% more clicks on their profile. "
            "Most contractors never respond to reviews — this makes you stand out."
        ),
        "annual_value": 4800,          # Review velocity and click-through improvement
        "monthly_cost": 12,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "anthropic_claude", "google_places"],
        "applies_to": ["all"],
        "integration": (
            "Monitors your Google Business Profile for new reviews every 4 hours via the Google API. "
            "When a new review appears, AI reads it, matches it to a recent job if possible, "
            "and drafts a response. You get a text with the draft — tap 'approve' and it posts "
            "directly to Google as your reply. If you want to edit, reply with your changes. "
            "Requires Google Business Profile owner access (one-time authorization during setup)."
        ),
        "owner_effort": (
            "One-time: 10 minutes. You authorize your Google Business Profile and tell us your "
            "preferred response tone (professional, warm, casual). "
            "Ongoing: 15-30 seconds per review. You read the draft and tap approve. "
            "Honest note: for negative reviews, you should read the draft carefully and may want to "
            "personalize it. The AI is good at de-escalation but you know the situation better. "
            "For 5-star reviews, the drafts are usually approve-and-forget."
        ),
        "objections": {
            "I respond to my reviews already": (
                "How fast? Reviews get the most visibility in the first 24-48 hours. "
                "If you respond 2 weeks later, the damage from a bad review is already done. "
                "This drafts a response within 4 hours of the review posting. You approve in 15 seconds. "
                "Even if you already respond, this makes you faster."
            ),
            "What if the AI says something wrong in a bad review response?": (
                "You approve every response before it posts. The AI never posts without your approval. "
                "For negative reviews, the AI draft is conservative: acknowledges the issue, expresses concern, "
                "offers to make it right, invites them to call. It never admits fault, never argues, "
                "never offers specific compensation without your input."
            ),
            "Does responding to reviews actually matter?": (
                "Google's own data shows businesses that respond to reviews get 35% more clicks. "
                "But more importantly — future customers read your responses. When they see you respond "
                "professionally to a 1-star review, it builds trust. When they see you thank 5-star reviewers "
                "by name, it feels personal. The response is marketing to future customers, not just the reviewer."
            ),
        },
        "works_with": ["google_business_profile"],
    },

    # ── BUSINESS-SPECIFIC ─────────────────────────────────────────────────────

    "hvac_filter_reminders": {
        "name": "HVAC Filter Replacement Reminders",
        "category": "Business-Specific (HVAC)",
        "description": (
            "90 days after any service call, HVAC customers get a text: "
            "'Hey [name]! Time to change your AC filter — want us to handle it "
            "while we do your seasonal tune-up? Only $59 added on.' "
            "Generates recurring revenue from existing customers automatically. "
            "Average HVAC customer worth 3x more with maintenance reminders."
        ),
        "annual_value": 14400,         # Filter + tune-up upsells x customer base
        "monthly_cost": 12,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["hvac"],
        "integration": (
            "Pulls customer data from your existing system — ServiceTitan, Housecall Pro, Jobber, "
            "or a plain Google Sheet. We read the 'last service date' field and the customer phone "
            "number. n8n checks every morning for customers hitting the 90-day mark, then Twilio "
            "sends the text from your business number. No software changes on your end."
        ),
        "owner_effort": (
            "One-time: give us access to your customer list (export CSV or share a Google Sheet). "
            "Takes 10 minutes. Ongoing: nothing. Texts go out automatically. You just answer "
            "when customers reply to book."
        ),
        "objections": {
            "My customers don't want to be bothered with texts": (
                "This is not marketing spam — it is a maintenance reminder for equipment they already own. "
                "Filter reminders have a 94% positive response rate because the customer genuinely needs "
                "to change their filter. They appreciate you looking out for their system. "
                "Anyone who replies STOP is automatically removed."
            ),
            "I already remind my customers myself": (
                "How many fall through the cracks? Most HVAC owners say they remind customers, but when "
                "we check their records, 60-70% of past customers never hear from them again after the "
                "first job. This catches every single one, on time, every time."
            ),
            "What if they schedule with someone else after getting the text?": (
                "They are going to need a filter change regardless. The question is whether YOU remind them "
                "or they Google 'HVAC near me' when their system starts struggling. The company that texts "
                "first gets the call 78% of the time."
            ),
        },
        "works_with": ["servicetitan", "housecall_pro", "jobber", "google_sheets",
                        "fieldedge", "successware"],

    },

    "hvac_seasonal_maintenance": {
        "name": "HVAC Seasonal Maintenance Campaign",
        "category": "Business-Specific (HVAC)",
        "description": (
            "Two campaigns per year: Spring AC tune-up (March) and Fall furnace check (September). "
            "Texts every past customer automatically. "
            "Offers $79 inspection (upsells to repairs/parts). "
            "Seasonal campaigns alone can fill a 2-week schedule in advance."
        ),
        "annual_value": 19200,         # 8 tune-up calls/month x $200 avg service
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["hvac"],
        "integration": (
            "Reads your full customer list from ServiceTitan, Housecall Pro, Jobber, or Google Sheets. "
            "Two scheduled triggers in n8n — March 1 and September 1. On those dates, the system pulls "
            "every customer who had service in the last 24 months and sends a text via Twilio from your "
            "existing business number. Replies come back to your phone as normal texts."
        ),
        "owner_effort": (
            "One-time: 15-minute call to confirm your seasonal pricing ($79 inspection or whatever you "
            "charge) and approve the message wording. We write the text, you approve once. "
            "Ongoing: nothing. Campaigns fire automatically every March and September. You handle the "
            "inbound calls when customers reply to book."
        ),
        "objections": {
            "I already do seasonal mailers": (
                "Mailers cost $0.50-$1.00 per piece and have a 1-2% response rate. Texts cost $0.01 each "
                "and have a 45% open rate within 3 minutes. You can keep doing mailers AND run this — "
                "the text catches everyone your mailer missed or who threw it away."
            ),
            "What if I can't handle all the calls at once?": (
                "We stagger the sends — 50 customers per day over a week instead of blasting your entire "
                "list on day one. You tell us your capacity and we throttle to match."
            ),
            "My customers already know to call me in spring/fall": (
                "Some do. Most do not. The average HVAC company loses 40% of one-time customers after the "
                "first job — they just forget you exist. A text 12 months later is the difference between "
                "them calling you or Googling your competitor."
            ),
            "$79 is too cheap, I'll lose money on the inspection": (
                "The $79 inspection is the door opener. Average tune-up upsells to $200-$400 in repairs, "
                "refrigerant, or capacitor replacements. The inspection finds real problems. You set the "
                "price — we just send the text."
            ),
        },
        "works_with": ["servicetitan", "housecall_pro", "jobber", "google_sheets",
                        "fieldedge", "successware"],

    },

    "hvac_warranty_tracker": {
        "name": "Equipment Warranty Tracker",
        "category": "Business-Specific (HVAC)",
        "description": (
            "Tracks warranty expiration dates for every piece of equipment installed. "
            "60 days before expiration: alerts owner and texts customer with "
            "an extended warranty offer or maintenance plan upsell. "
            "Warranty expiry is the #1 reason HVAC customers call a different company."
        ),
        "annual_value": 9600,          # Warranty upsells + customer retention
        "monthly_cost": 10,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_sheets", "twilio"],
        "applies_to": ["hvac"],
        "integration": (
            "Google Sheet (or a tab in your existing one) with columns: customer name, phone, equipment "
            "type, install date, warranty expiration date. If you use ServiceTitan or Housecall Pro, we "
            "pull equipment records directly. n8n checks daily, calculates days until expiration, and "
            "triggers Twilio texts at the 60-day mark. Owner gets a separate alert text."
        ),
        "owner_effort": (
            "One-time: enter your installed equipment data into the tracking sheet. If you have records "
            "in ServiceTitan or invoices, we bulk-import — takes about 30 minutes to clean up. "
            "Ongoing: add new installs to the sheet when you do them. One row per install, 30 seconds. "
            "If you forget, the system still works for everything already tracked."
        ),
        "objections": {
            "I don't track warranty dates right now": (
                "That is exactly the problem. Your customers' warranties are expiring and they don't know. "
                "When the unit breaks 6 months after warranty ends, they call whoever is on Google — not you. "
                "We help you build the list from past invoices. Most owners can reconstruct 2-3 years in an hour."
            ),
            "My customers can track their own warranties": (
                "Less than 5% of homeowners know when their HVAC warranty expires. When you remind them, "
                "you become the trusted advisor — and the first call when they need service or a replacement."
            ),
            "Entering equipment data sounds like a lot of work": (
                "If you have ServiceTitan or Housecall Pro, we pull it automatically — zero data entry. "
                "If you use paper invoices, we set up a simple phone form: scan the model number sticker, "
                "it auto-fills the sheet. Going forward, one row per install takes 30 seconds."
            ),
        },
        "works_with": ["servicetitan", "housecall_pro", "jobber", "google_sheets",
                        "fieldedge", "successware"],

    },

    "plumber_emergency_routing": {
        "name": "Emergency Call Routing (Plumber)",
        "category": "Business-Specific (Plumber)",
        "description": (
            "When AI detects emergency keywords ('flooding,' 'pipe burst,' 'no hot water'), "
            "it immediately pages the on-call tech via text and call, "
            "tells the customer the estimated arrival time, and upgrades their priority. "
            "Emergency jobs pay 2x normal rate — never miss them."
        ),
        "annual_value": 24000,         # 2 emergency jobs/month x $1,000 avg emergency job
        "monthly_cost": 20,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["retell_ai", "n8n", "twilio"],
        "applies_to": ["plumber"],
        "integration": (
            "Works with your existing AI phone receptionist (or we build one). The Retell AI agent "
            "listens for emergency keywords during the call. When triggered, n8n sends an immediate "
            "text AND phone call to your on-call tech's cell phone. The customer gets a text with an "
            "ETA you set. If you rotate on-call, we read the rotation from a simple Google Sheet."
        ),
        "owner_effort": (
            "One-time: tell us your on-call tech's phone number, your emergency response time (30 min, "
            "45 min, 1 hour), and which keywords count as emergencies. 10-minute call. "
            "Ongoing: if you rotate on-call techs, update the Google Sheet weekly — 15 seconds. "
            "If it is always you, there is zero ongoing work."
        ),
        "objections": {
            "What if the AI misidentifies an emergency?": (
                "False positives are better than false negatives. If the AI pages you for a non-emergency, "
                "you spent 10 seconds reading a text. If it misses a real emergency, you lose a $1,000+ job "
                "and a customer for life. We tune the keywords to your business."
            ),
            "I already answer my own emergency calls": (
                "Do you answer at 2am? On Thanksgiving? When you are under a house on another job? "
                "The customer with a flooding kitchen doesn't leave a voicemail — they call the next plumber. "
                "This catches every emergency call you physically cannot answer."
            ),
            "My on-call tech won't like getting paged by a computer": (
                "The page comes as a normal text and phone call — looks identical to you calling him. "
                "The text includes the customer's name, address, and problem description. Your tech gets "
                "more information from this page than from most phone calls."
            ),
            "What about non-emergency after-hours calls?": (
                "Non-emergency calls get booked for the next business day automatically. The AI only pages "
                "for true emergencies. Everything else gets the standard treatment."
            ),
        },
        "works_with": ["servicetitan", "housecall_pro", "jobber", "google_sheets",
                        "google_calendar", "any_phone_system"],

    },

    "plumber_permit_tracker": {
        "name": "Permit Tracking System (Plumber)",
        "category": "Business-Specific (Plumber)",
        "description": (
            "Tracks all open permits: what they are for, status, inspection dates, expiration. "
            "Alerts owner 2 weeks before permit expiration or inspection deadline. "
            "Prevents failed inspections, fines, and angry customers. "
            "Permit violations can shut down a plumbing company."
        ),
        "annual_value": 6000,          # Prevents fines + project delays + customer complaints
        "monthly_cost": 10,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_sheets", "twilio"],
        "applies_to": ["plumber"],
        "integration": (
            "Google Sheet with columns: permit number, job address, permit type, pull date, inspection "
            "date, expiration date, status. You or your office manager adds a row when you pull a permit. "
            "n8n checks every morning and sends you a text 14 days before any inspection or expiration. "
            "No connection to city systems needed — it is your own tracker."
        ),
        "owner_effort": (
            "One-time: we set up the sheet and show you how to add a row (2 minutes to learn). "
            "Ongoing: add one row per permit when you pull it — 60 seconds per permit. "
            "This is real ongoing work, but it replaces sticky notes and the panic of realizing "
            "a permit expired yesterday. If your office manager handles permits, they do the entry."
        ),
        "objections": {
            "I keep track of permits in my head": (
                "Until you don't. One missed inspection date is a $500-$2,000 fine depending on your "
                "jurisdiction, plus a delayed job and an angry customer. If you have 5+ open permits at "
                "any time, something will slip. This is insurance."
            ),
            "My office manager already handles this": (
                "Great — she enters the data into the sheet instead of you. The system texts both of you "
                "the alerts. Now you have a backup for when she is sick, on vacation, or quits."
            ),
            "This seems like extra data entry work for me": (
                "It is. 60 seconds per permit. But compare that to driving back to a job site for a "
                "failed inspection or paying a $1,500 fine because a permit expired. The data entry is "
                "the cheapest insurance you will ever buy."
            ),
        },
        "works_with": ["google_sheets", "servicetitan", "housecall_pro", "jobber"],

    },

    "roofing_storm_lead_gen": {
        "name": "Storm Damage Lead Generator (Roofer)",
        "category": "Business-Specific (Roofer)",
        "description": (
            "Monitors weather data for hail/wind storms in the service area. "
            "Within 24 hours of a storm, auto-generates a prospect list "
            "from neighborhoods in the storm path. "
            "Sends outreach texts/emails immediately. "
            "Storm chasers close 3x more jobs than regular roofers by being first."
        ),
        "annual_value": 60000,         # 1 storm job/month x $5,000 avg roof x 12
        "monthly_cost": 30,
        "build_time_hours": 4,
        "difficulty": 3,
        "tools": ["n8n", "anthropic_claude", "twilio", "google_places"],
        "applies_to": ["roofer"],
        "integration": (
            "NOAA weather API monitors your service area zip codes for hail and high-wind alerts. "
            "When a storm hits, n8n triggers a Google Places scrape of residential neighborhoods in "
            "the storm path. Claude AI generates personalized outreach messages. Twilio sends texts "
            "from a dedicated number. Leads who respond get routed to your phone or AI receptionist. "
            "Standalone lead gen engine — no connection to your existing systems needed."
        ),
        "owner_effort": (
            "One-time: give us your service area zip codes and your storm damage pricing/process. "
            "20-minute setup call. Ongoing: when leads respond, you handle the sales conversation and "
            "schedule the inspection. The system finds leads and makes first contact — you close them. "
            "After a major storm, expect 10-30 responses within 48 hours. Be ready to inspect."
        ),
        "objections": {
            "Storm chasing is shady, I don't want to be that guy": (
                "There is nothing shady about reaching out to homeowners whose roof just got hit by hail "
                "and telling them you do free inspections. The shady companies show up uninvited and "
                "pressure-sell. You are sending a text that says 'We are local, we inspect for free, here "
                "is our Google rating.' The homeowner chooses whether to respond."
            ),
            "What about TCPA compliance with texting strangers?": (
                "For full compliance, we use informational framing: 'Storm damage reported in your area — "
                "free inspections available.' Opt-out is in every message. We can also switch to postcards "
                "with a text-in code that creates consent on response."
            ),
            "I already drive neighborhoods after storms": (
                "Keep doing that. This reaches the neighborhoods you can't drive in the first 24 hours. "
                "A major hailstorm hits 5,000+ homes. You can knock on 50 doors in a day. This texts 500 "
                "homeowners while you are knocking. The two strategies work together."
            ),
            "What if there are no storms this year?": (
                "Then the system costs $30/month to monitor weather and does nothing. It pays for itself "
                "with one storm job ($5,000-$15,000 revenue). Most US markets get 3-8 significant hail "
                "events per year."
            ),
            "Other roofers probably use something like this too": (
                "Less than 2% of local roofing companies have automated storm response. Most are still "
                "driving neighborhoods 2-3 days after the storm. By then, the first-mover already has "
                "30 inspections scheduled. Speed is the entire game in storm work."
            ),
        },
        "works_with": ["google_sheets", "servicetitan", "jobber", "acculynx",
                        "roofr", "any_phone_system"],

    },

    "roofing_insurance_automation": {
        "name": "Insurance Claim Intake (Roofer)",
        "category": "Business-Specific (Roofer)",
        "description": (
            "When a customer calls about storm damage, AI walks them through "
            "the insurance claim process step by step, collects their insurance info, "
            "photos of damage, and adjuster name. "
            "Sends a follow-up email with exactly what they need to do next. "
            "Eliminates the #1 reason roofing jobs fall through: customer confusion about insurance."
        ),
        "annual_value": 36000,         # 3 insurance jobs/month x $1,000 margin increase
        "monthly_cost": 20,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["retell_ai", "n8n", "twilio"],
        "applies_to": ["roofer"],
        "integration": (
            "Plugs into your existing AI phone receptionist. When a caller mentions storm damage, "
            "insurance, hail, or wind damage, the AI switches to insurance intake mode. It collects: "
            "insurance company, policy number, claim status, adjuster name/number, damage description. "
            "All info goes to a Google Sheet and you get a text summary. A follow-up email with next "
            "steps is sent to the homeowner automatically."
        ),
        "owner_effort": (
            "One-time: give us your insurance claim process — what you need from the homeowner, your "
            "inspection process, typical timeline. 20-minute call. Ongoing: nothing from the collection "
            "side. You still do the physical inspection and work with the adjuster. But you walk into "
            "every inspection with the claim info already in hand."
        ),
        "objections": {
            "Insurance work is complicated, an AI can't handle it": (
                "The AI is not handling the claim — it is collecting the information you need upfront. "
                "Insurance company, policy number, adjuster name, what happened, photos. That is data "
                "collection, not claims adjustment. You still do the inspection and adjuster work."
            ),
            "What if the homeowner gives wrong insurance info?": (
                "The AI asks for confirmation and reads it back. If they don't know their policy number, "
                "it tells them where to find it. Wrong info gets caught at the inspection, same as always."
            ),
            "My office manager already does intake on storm calls": (
                "Does she handle 10 calls at once after a major storm? Storm events create call surges. "
                "Your office manager handles 1 call at a time. This handles 100 simultaneously. On the "
                "busiest day of the year, that is when you need this most."
            ),
        },
        "works_with": ["acculynx", "roofr", "google_sheets", "servicetitan",
                        "jobber", "any_phone_system"],

    },

    "law_firm_intake": {
        "name": "Client Intake Automation (Law Firm)",
        "category": "Business-Specific (Law Firm)",
        "description": (
            "AI conducts the initial intake call: type of case, incident date, "
            "parties involved, injuries/damages, prior attorney history. "
            "Scores the case automatically (strong/weak/refer out). "
            "Sends summary to attorney before their callback. "
            "Billable time starts from consultation, not from intake paperwork."
        ),
        "annual_value": 48000,         # 4 additional cases/month x $1,000 avg contingency
        "monthly_cost": 40,
        "build_time_hours": 3,
        "difficulty": 3,
        "tools": ["retell_ai", "n8n", "anthropic_claude"],
        "applies_to": ["law_firm"],
        "integration": (
            "Retell AI handles the intake call using a script customized to your practice areas. "
            "Claude AI scores the case based on criteria you define (statute of limitations, liability "
            "indicators, damages threshold, jurisdiction). Intake summary sent to your email and as a "
            "text. Can push to Clio, MyCase, or PracticePanther via API, or to Google Sheets."
        ),
        "owner_effort": (
            "One-time: 30-minute setup call to define intake questions, case scoring criteria, and which "
            "case types you accept vs. refer out. We need your practice areas and jurisdiction. "
            "Ongoing: review AI-generated case summaries before your callback. Each summary is 1 paragraph. "
            "Strong cases get prioritized, refer-outs get auto-forwarded to your referral partners."
        ),
        "objections": {
            "Legal intake requires a trained paralegal": (
                "Initial intake is data collection: what happened, when, who was involved, what are the "
                "injuries. The AI collects the same data your paralegal's script does, 24/7. Your paralegal's "
                "expertise kicks in during case evaluation — which this does not replace."
            ),
            "What about attorney-client privilege?": (
                "The AI intake system is a tool of the law firm, same as your voicemail or website form. "
                "Data is stored in systems you control (your Google Sheet, your Clio account). We do not "
                "access, review, or share any client data."
            ),
            "My clients expect to talk to a real person": (
                "Your clients expect to not go to voicemail. 68% of potential clients who reach voicemail "
                "at a law firm call the next attorney. The AI answers instantly, collects their information, "
                "and tells them exactly when the attorney will call back."
            ),
            "What if the AI gives legal advice?": (
                "It is explicitly programmed to never give legal advice. It says: 'I am here to collect your "
                "information so the attorney can review your case. I cannot provide legal guidance.' We test "
                "this with adversarial callers before going live."
            ),
            "This is too expensive at $40/month for a law firm": (
                "One missed intake call on a personal injury case can be worth $10,000-$50,000 in contingency "
                "fees. At $40/month, it pays for itself if it catches one case per year that would have gone "
                "to voicemail. Most firms see 3-5 after-hours intake calls per week."
            ),
        },
        "works_with": ["clio", "mycase", "practicepanther", "google_sheets",
                        "google_calendar", "any_phone_system"],

    },

    "law_firm_document_requests": {
        "name": "Automated Document Request System (Law Firm)",
        "category": "Business-Specific (Law Firm)",
        "description": (
            "After intake, AI automatically sends clients a checklist of documents needed "
            "(medical records, police reports, pay stubs, insurance info). "
            "Follows up every 3 days until documents received. "
            "Tracks which clients are missing what. "
            "Case prep time drops by 40% when clients come prepared."
        ),
        "annual_value": 12000,         # Faster case prep + less paralegal time
        "monthly_cost": 20,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["law_firm"],
        "integration": (
            "Triggers after intake automation (or manually by staff). n8n sends the client a text with "
            "their document checklist, customized by case type — PI gets medical records + police report, "
            "employment gets pay stubs + contract, etc. Google Sheet tracks each client and which documents "
            "are received. Every 3 days, clients with missing documents get a follow-up text."
        ),
        "owner_effort": (
            "One-time: give us your document checklists per case type. Most firms already have these. "
            "15-minute call. Ongoing: your paralegal marks documents as 'received' in the Google Sheet "
            "when they come in — one click per document. If they don't mark it, the client gets an extra "
            "reminder. Not harmful, just slightly annoying for the client."
        ),
        "objections": {
            "My paralegal already follows up on documents": (
                "How many times does she chase the same client? Average PI client needs 4-6 follow-ups "
                "before submitting all documents. That is 30+ minutes per client in phone tag. This "
                "automates the nagging so your paralegal focuses on case work."
            ),
            "Clients don't respond to automated texts": (
                "Clients respond to texts faster than phone calls or emails. Average text response time "
                "is 90 seconds. If they don't respond after 3 automated follow-ups (9 days), your "
                "paralegal gets an alert to make a personal call."
            ),
            "What if documents contain sensitive information?": (
                "The system sends a checklist telling the client WHAT to bring — it does not collect or "
                "transmit documents. Clients bring physical documents to your office or upload through "
                "your existing client portal. The automation handles reminders only."
            ),
        },
        "works_with": ["clio", "mycase", "practicepanther", "google_sheets",
                        "any_phone_system"],

    },

    "restaurant_reservations": {
        "name": "AI Reservation Management (Restaurant)",
        "category": "Business-Specific (Restaurant)",
        "description": (
            "AI handles all reservation calls: takes name, party size, date, time, "
            "special requests. Checks availability in real time. "
            "Sends confirmation text and reminder 2 hours before. "
            "Waitlist management when fully booked. "
            "No-show fee collection for parties of 6+."
        ),
        "annual_value": 14400,         # Reduced no-shows + freed staff time
        "monthly_cost": 45,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["retell_ai", "n8n", "twilio"],
        "applies_to": ["restaurant"],
        "integration": (
            "Retell AI answers reservation calls and collects: name, party size, date, time, special "
            "requests. Availability checked against a Google Calendar or Sheet with table capacity per "
            "time slot. Bookings added to calendar automatically. Twilio sends confirmation text and "
            "2-hour reminder. If you use OpenTable or Resy, we sync bookings to a shared calendar."
        ),
        "owner_effort": (
            "One-time: give us your table layout (how many tables, max covers per slot), hours, and "
            "booking rules (minimum party size for private room, deposit for large parties). 30-minute "
            "setup. Ongoing: your host keeps the availability calendar updated — marking tables as "
            "unavailable for private events, adjusting for holidays. Same thing they already do."
        ),
        "objections": {
            "We use OpenTable/Resy, why do we need this?": (
                "OpenTable charges $1-$7.50 per cover. At 200 covers/month, that is $200-$1,500/month. "
                "This handles phone reservations for $45/month flat. Phone callers do not go through "
                "OpenTable — they call you directly. This catches those calls when your host is busy."
            ),
            "Our regulars want to talk to a person when they book": (
                "Your regulars call during dinner rush when nobody can answer. The AI books in 45 seconds "
                "and sends a confirmation text. If someone specifically asks for a person, the AI says "
                "'Let me have the manager call you back.' Regulars care about getting their table."
            ),
            "What about special requests the AI can't handle?": (
                "The AI collects ALL special requests verbatim: 'birthday cake, window table, wheelchair.' "
                "Your staff sees the full request in the calendar event. For complex requests, the AI "
                "says 'I will have the manager coordinate the details' and you get a text."
            ),
        },
        "works_with": ["google_calendar", "google_sheets", "opentable", "resy",
                        "any_phone_system"],

    },

    "restaurant_review_response": {
        "name": "AI Review Response (Restaurant)",
        "category": "Business-Specific (Restaurant)",
        "description": (
            "Monitors Yelp, Google, TripAdvisor for new reviews every 4 hours. "
            "AI drafts a personalized response for every review. "
            "Handles complaints with empathy, thanks positive reviewers by dish/server name. "
            "Restaurants that respond to every review average 0.3 stars higher."
        ),
        "annual_value": 7200,          # Higher star rating = more traffic
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "anthropic_claude"],
        "applies_to": ["restaurant"],
        "integration": (
            "n8n checks your Google Business Profile, Yelp, and TripAdvisor every 4 hours via public "
            "APIs and RSS feeds. Claude AI reads each new review and drafts a response matching your "
            "restaurant's voice. Draft sent to you as a text for approval — tap approve and it posts. "
            "For 5-star reviews, optional auto-post after 12 hours if you don't respond."
        ),
        "owner_effort": (
            "One-time: give us your review page links and 2-3 example responses you've written so "
            "the AI matches your voice. 15-minute call. Ongoing: review and approve AI-drafted "
            "responses — 10-15 seconds per review. For negative reviews, you may want to edit. "
            "Average restaurant gets 5-15 reviews per week."
        ),
        "objections": {
            "AI responses sound generic and fake": (
                "We train the AI on YOUR past responses, your menu items, your server names. It references "
                "specific dishes the reviewer mentioned. 'Thanks for trying the short rib, Sarah!' Not "
                "'Thank you for your valuable feedback.' If a response sounds generic, you reject it and "
                "we retune."
            ),
            "I want to respond personally to negative reviews": (
                "You should — and you still do. The AI drafts negative review responses but flags them as "
                "'needs your review' and does NOT auto-post. You get the draft, edit it, post yourself. "
                "The AI saves you from staring at a blank screen trying to be professional when angry."
            ),
            "We don't get enough reviews to justify this": (
                "If you are not responding to reviews, that is part of why you are not getting more. "
                "Google's algorithm favors businesses that respond. Responding encourages more reviews. "
                "It is a flywheel."
            ),
        },
        "works_with": ["google_business_profile", "yelp", "tripadvisor"],

    },

    "gym_class_booking": {
        "name": "Class Booking Automation (Gym)",
        "category": "Business-Specific (Gym/Fitness)",
        "description": (
            "Members text or call to book classes. AI checks availability, "
            "books the spot, sends confirmation. "
            "Cancellation reminder with 24-hour window. "
            "Waitlist management when full. "
            "No-show tracking — 3 no-shows = warning text from AI."
        ),
        "annual_value": 9600,          # Reduced no-shows + increased class fill rate
        "monthly_cost": 25,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["retell_ai", "n8n", "twilio"],
        "applies_to": ["gym"],
        "integration": (
            "Members text a keyword (e.g., 'BOOK SPIN 6PM TUESDAY') or call and Retell AI handles it "
            "conversationally. Availability checked against a Google Calendar with max attendee counts "
            "per class. Bookings update the calendar and Twilio sends confirmation. If you use MindBody, "
            "Wodify, or PushPress, we sync the calendar with your platform."
        ),
        "owner_effort": (
            "One-time: set up your class schedule in Google Calendar (or give us your existing one to "
            "import). Define max class sizes and cancellation window. 20-minute setup. "
            "Ongoing: update class schedule when it changes (new times, instructor subs, holidays). "
            "Same updates you already make, just in the calendar."
        ),
        "objections": {
            "We already use MindBody/Wodify for booking": (
                "MindBody's app booking rate for small gyms is 40-60%. The rest call or text. This catches "
                "those calls so members who don't use the app can still book without you answering the phone. "
                "We sync with your system — no double-booking."
            ),
            "What about members who want to talk to a trainer?": (
                "The AI handles booking only. If a member asks about programming, nutrition, or personal "
                "training, the AI says 'Let me have Coach [name] get back to you' and texts the trainer."
            ),
            "My classes are small, I know everyone by name": (
                "Great — and you still will. This just means you don't have to stop mid-workout to answer "
                "the phone when someone wants to book the 6am class."
            ),
        },
        "works_with": ["mindbody", "wodify", "pushpress", "google_calendar",
                        "google_sheets", "any_phone_system"],

    },

    "gym_membership_renewal": {
        "name": "Membership Renewal AI (Gym)",
        "category": "Business-Specific (Gym/Fitness)",
        "description": (
            "30 days before membership expires, member gets a renewal text with "
            "a special rate for renewing early. "
            "10 days out: second message. Day of expiry: final offer. "
            "Expired members get a 'we miss you' message at 7 and 14 days. "
            "Increases renewal rate by 20-30%."
        ),
        "annual_value": 14400,         # 20% more renewals x avg membership value
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["gym"],
        "integration": (
            "Reads membership data from Google Sheet, MindBody export, or Wodify export. We need: member "
            "name, phone, membership type, expiration date. n8n checks every morning for members hitting "
            "30-day, 10-day, and same-day renewal windows. Twilio sends texts from your gym's number. "
            "Follow-up texts at day 7 and day 14 after expiry."
        ),
        "owner_effort": (
            "One-time: give us your membership list with expiration dates — if you use MindBody or "
            "Wodify, we export directly. Define your early renewal discount (if any) and approve message "
            "templates. 15-minute setup. Ongoing: keep your membership spreadsheet updated when members "
            "join or cancel. If you use a gym management platform, this is automatic."
        ),
        "objections": {
            "Members know when their membership expires": (
                "In practice, 25-40% of gym members let their membership lapse because they forgot, not "
                "because they wanted to quit. A text at 30 days gives them the nudge to renew before they "
                "lose the habit."
            ),
            "I don't want to seem pushy about renewals": (
                "One text at 30 days and one at 10 days is not pushy — it is helpful. 'Hey, your membership "
                "renews in 10 days. Renew this week and lock in your current rate.' No pressure, no hard sell."
            ),
            "We have automatic billing, renewals are automatic": (
                "For auto-pay members, great. But most small gyms have 15-30% of members on manual renewal, "
                "prepaid plans, or class packs. Those are the ones who drift away. This also works for class "
                "pack renewals — '3 classes left on your 10-pack.'"
            ),
        },
        "works_with": ["mindbody", "wodify", "pushpress", "google_sheets",
                        "any_phone_system"],

    },

    "real_estate_listing_updates": {
        "name": "Listing and Showing Automation (Real Estate)",
        "category": "Business-Specific (Real Estate)",
        "description": (
            "When a new listing goes live, AI texts all matching buyer prospects. "
            "Showing requests are confirmed/rescheduled automatically. "
            "Post-showing: buyer gets a follow-up asking for their thoughts. "
            "Agents close 30% more deals when follow-up is consistent."
        ),
        "annual_value": 24000,         # 2 more closed deals/year x avg commission
        "monthly_cost": 25,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["n8n", "twilio", "anthropic_claude"],
        "applies_to": ["real_estate"],
        "integration": (
            "Buyer prospect sheet (Google Sheets) with columns: name, phone, price range, preferred "
            "areas, bedrooms, must-haves. When you add a new listing to a listings sheet, n8n matches "
            "against all active buyers and texts matches via Twilio. Claude AI personalizes each message. "
            "If you use KVCore, Follow Up Boss, or BoomTown, we pull buyer criteria from there."
        ),
        "owner_effort": (
            "One-time: set up your buyer prospect sheet with current active buyers. If you have this in "
            "your CRM, we import it. 30-minute setup. Ongoing: add new buyers and listings to the sheet. "
            "Approve or customize the AI-generated match texts before they send (optional auto-send). "
            "Review post-showing feedback from buyers."
        ),
        "objections": {
            "I already text my buyers when new listings come up": (
                "Every single one? Within the first hour? The listing that goes live at 2pm gets texted "
                "to matching buyers by 2:05pm — while you are at a closing or showing. Speed matters. "
                "The agent who texts first gets the showing."
            ),
            "My CRM already does listing alerts": (
                "MLS listing alerts are generic emails that go to spam. This is a personal text from YOUR "
                "number with a personalized message referencing what the buyer wants. 'Hey Sarah, this one "
                "has the mother-in-law suite you mentioned.' That is not an alert — it is a recommendation."
            ),
            "What about showing scheduling through ShowingTime?": (
                "This works alongside ShowingTime. ShowingTime handles seller-side scheduling. This handles "
                "buyer-side outreach and follow-up. Different jobs."
            ),
        },
        "works_with": ["kvcore", "follow_up_boss", "boomtown", "google_sheets",
                        "google_calendar", "any_phone_system"],

    },

    "retail_inventory_reorder": {
        "name": "Inventory Reorder Alerts (Retail)",
        "category": "Business-Specific (Retail)",
        "description": (
            "Monitors inventory levels from POS system data. "
            "When any SKU drops below reorder threshold, alerts owner with "
            "supplier name, order quantity, and direct order link. "
            "Prevents stockouts on top-selling items. "
            "Average retail store loses 4.4% of revenue to stockouts."
        ),
        "annual_value": 8400,          # Prevents stockout losses
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["retail"],
        "integration": (
            "Connects to your POS daily sales report — Square, Shopify, Clover, Lightspeed all export "
            "daily sales data via CSV or API. n8n reads sales data, subtracts from inventory counts in "
            "a Google Sheet, and checks reorder thresholds. When a SKU hits threshold, you get a text: "
            "'Low stock: Widget X — 8 left. Supplier: ABC Co. Order link: [url].'"
        ),
        "owner_effort": (
            "One-time: set up your inventory sheet with current counts, reorder thresholds, and supplier "
            "info for your top-selling items. Start with your top 20 SKUs. 45-minute setup. "
            "Ongoing: if your POS tracks inventory (Square, Shopify), zero effort — it reads from the POS. "
            "If manual, update the sheet after each receiving."
        ),
        "objections": {
            "My POS already tells me when I'm low on stock": (
                "Your POS tells you when you look at it. This tells you via text the moment a threshold "
                "is hit, with a direct link to order. Most stockouts happen because the owner saw the POS "
                "warning 3 days ago and forgot to order."
            ),
            "I know my inventory, I walk the shelves every day": (
                "Shelf walks catch empty shelves. This catches items with 3 days of stock left before "
                "they hit zero. Lead times matter — if your supplier ships in 5 days, you need to order "
                "when you have 7 days of stock."
            ),
            "Setting up reorder thresholds for every item is too much work": (
                "Start with your top 20 items — covers 80% of your revenue risk. Takes 15 minutes to set "
                "up. Add more items over time."
            ),
        },
        "works_with": ["square", "shopify", "clover", "lightspeed", "google_sheets"],

    },

    "retail_loyalty_program": {
        "name": "Customer Loyalty Program (Retail)",
        "category": "Business-Specific (Retail)",
        "description": (
            "Text-based loyalty program: customers text to check their points, "
            "get points for purchases (tracked via phone number), "
            "get reward texts when thresholds hit. "
            "No app needed — just a phone number. "
            "Loyalty members spend 67% more than non-members."
        ),
        "annual_value": 12000,         # Increased repeat purchase frequency
        "monthly_cost": 20,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["n8n", "twilio", "google_sheets"],
        "applies_to": ["retail"],
        "integration": (
            "Customers give their phone number at checkout. Cashier enters the number into a simple web "
            "form or POS note field. n8n reads the purchase, credits points in a Google Sheet, and if "
            "a reward threshold hits, Twilio sends: 'You earned a $10 reward! Show this text at checkout.' "
            "Customers text 'POINTS' to your loyalty number anytime to check balance."
        ),
        "owner_effort": (
            "One-time: define your points structure (1 point per dollar? 10 per visit?), reward "
            "thresholds, and rewards. Set up the checkout form. Train cashiers — takes 2 minutes. "
            "30-minute total setup. Ongoing: cashiers enter the phone number at checkout. That is it. "
            "Review the loyalty dashboard monthly to see top customers."
        ),
        "objections": {
            "We tried a punch card system and it didn't work": (
                "Punch cards fail because customers lose them. Phone number loyalty never gets lost — the "
                "customer's number is always with them. No card, no app, no account to create."
            ),
            "My margins are too thin for discounts": (
                "Loyalty members visit 2x more often and spend 67% more per visit. A $10 reward on a $100 "
                "threshold is 10% — but it drives $200+ in additional spending to earn it. You set the "
                "threshold wherever it makes sense for your margins."
            ),
            "My cashiers won't remember to ask for the phone number": (
                "Put a small sign at the register: 'Earn rewards — give us your number!' After a week, "
                "customers start volunteering their number. The form takes 5 seconds."
            ),
            "What about customer privacy concerns?": (
                "You only collect their phone number — no name, email, address. They opt in by giving "
                "you the number. Text STOP anytime to opt out and we delete their data. Less invasive "
                "than any app-based loyalty program."
            ),
        },
        "works_with": ["square", "shopify", "clover", "lightspeed", "google_sheets"],

    },

    # ── ELECTRICIAN-SPECIFIC ─────────────────────────────────────────────────

    "electrician_emergency_routing": {
        "name": "Emergency Call Routing (Electrician)",
        "category": "Business-Specific (Electrician)",
        "description": (
            "When AI detects emergency keywords ('sparks,' 'burning smell,' 'no power,' 'exposed wire'), "
            "it immediately pages the on-call electrician via text and call, "
            "tells the customer the estimated arrival time, and marks it priority. "
            "Electrical emergencies are dangerous — fast response prevents house fires."
        ),
        "annual_value": 21600,         # 1.5 emergency jobs/month x $1,200 avg emergency job
        "monthly_cost": 20,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["retell_ai", "n8n", "twilio"],
        "applies_to": ["electrician"],
        "integration": (
            "Works with your AI phone receptionist (or we build one). Retell AI listens for emergency "
            "keywords during the call. When triggered, n8n sends an immediate text AND phone call to "
            "your on-call electrician's cell. Customer gets a text with your emergency ETA. If you "
            "rotate on-call, we read rotation from a Google Sheet. Same battle-tested architecture "
            "as the plumber emergency routing."
        ),
        "owner_effort": (
            "One-time: tell us your on-call number, emergency response time, and which keywords count "
            "as electrical emergencies. 10-minute call. Ongoing: if you rotate on-call, update the "
            "Google Sheet weekly — 15 seconds. If it is always you, zero ongoing work."
        ),
        "objections": {
            "Electrical emergencies need a licensed electrician on the phone, not an AI": (
                "The AI is not diagnosing or advising — it is dispatching. It detects the emergency, pages "
                "you immediately, and tells the customer help is on the way. You handle everything from there."
            ),
            "What if someone says 'sparks' but it's not really an emergency?": (
                "Better to page you for a false alarm than miss a real one. Electrical fires kill 300+ "
                "people per year in the US. A false page costs you 10 seconds reading a text. A missed "
                "emergency costs you a $1,200+ job and potentially a customer's safety."
            ),
            "I already answer all my emergency calls myself": (
                "At 11pm on a Saturday? When you are at your kid's game? When two emergencies come in at "
                "once? This catches every call you physically cannot answer. If you answer first, the AI "
                "never triggers. It is your safety net."
            ),
        },
        "works_with": ["servicetitan", "housecall_pro", "jobber", "google_sheets",
                        "google_calendar", "any_phone_system"],

    },

    "electrician_permit_tracker": {
        "name": "Permit Tracking System (Electrician)",
        "category": "Business-Specific (Electrician)",
        "description": (
            "Tracks all open electrical permits: job type, status, inspection dates, expiration. "
            "Alerts owner 2 weeks before permit expiration or inspection deadline. "
            "Prevents code violations and failed inspections. "
            "Many jurisdictions require permits for panel upgrades, new circuits, and rewiring."
        ),
        "annual_value": 6000,
        "monthly_cost": 10,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_sheets", "twilio"],
        "applies_to": ["electrician"],
        "integration": (
            "Google Sheet with columns: permit number, job address, permit type (panel upgrade, new "
            "circuit, rewire), pull date, inspection date, expiration date, status. You or your office "
            "manager adds a row when you pull a permit. n8n checks every morning and texts you 14 days "
            "before any deadline. For jurisdictions with online permit status, we can auto-check results."
        ),
        "owner_effort": (
            "One-time: we set up the sheet and show you how to add a row. 5-minute walkthrough. "
            "Ongoing: add one row per permit when you pull it — 60 seconds each. Electrical contractors "
            "average 3-8 permits per month. That is 3-8 minutes per month of data entry to never miss "
            "a deadline."
        ),
        "objections": {
            "I keep track of my permits fine": (
                "How many open permits do you have right now? What are the next 3 inspection dates? If "
                "you hesitate on the second question, this is for you. One missed inspection can delay "
                "a job 2-3 weeks."
            ),
            "My jurisdiction doesn't require that many permits": (
                "Even 2-3 per month is enough. One missed inspection or expired permit is a $500-$2,000 "
                "fine plus rework cost. At $10/month, this pays for itself by preventing one fine per year."
            ),
            "This is just a spreadsheet, I can do this myself": (
                "You can. But you haven't. The value is the automated alerts that text you 14 days before "
                "a deadline. The spreadsheet without automation is a to-do list you forget to check."
            ),
        },
        "works_with": ["google_sheets", "servicetitan", "housecall_pro", "jobber"],

    },

    # ── AUTO REPAIR-SPECIFIC ─────────────────────────────────────────────────

    "auto_repair_service_reminders": {
        "name": "Service Reminder System (Auto Repair)",
        "category": "Business-Specific (Auto Repair)",
        "description": (
            "Tracks mileage-based and time-based service intervals for every customer vehicle. "
            "Sends automated text reminders: 'Your 2019 F-150 is due for an oil change — "
            "want us to get you on the schedule?' "
            "Turns one-time customers into recurring revenue. "
            "Service reminders generate 30-40% of repeat business for top shops."
        ),
        "annual_value": 14400,         # 3 reminder-converted jobs/month x $400 avg
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio", "google_sheets"],
        "applies_to": ["auto_repair"],
        "integration": (
            "Pulls vehicle data from your shop management system — Mitchell 1, ShopWare, Tekmetric, or "
            "a Google Sheet. Tracks: customer name, phone, vehicle year/make/model, last service date, "
            "last known mileage, service type. n8n calculates time-based intervals (oil change every "
            "6 months, brakes every 12 months) and triggers Twilio texts when due."
        ),
        "owner_effort": (
            "One-time: export your customer/vehicle list or give us access to pull it. Set service "
            "intervals for common services. 30-minute setup. Ongoing: your shop system updates "
            "automatically at job completion. If manual, service writer updates the sheet — 30 seconds "
            "per vehicle."
        ),
        "objections": {
            "My shop system already sends reminders": (
                "Most shop systems have a reminder feature that 90% of shops never set up. If yours is "
                "actively sending, check: is it texting or emailing? Email open rates are 15-20%. Text "
                "open rates are 98%. Both can run simultaneously."
            ),
            "Customers think we're just trying to upsell them": (
                "The text includes their specific vehicle: 'Your 2019 F-150 is due for an oil change.' "
                "That is maintenance advice from the shop that knows their truck. Response rate on "
                "vehicle-specific reminders is 25-35%."
            ),
            "I don't have mileage data for most customers": (
                "Then we use time-based intervals. Oil change every 6 months, brakes every 12 months. "
                "When they come in and you read the odometer, we update to mileage-based. Starting "
                "with time-only is perfectly fine."
            ),
        },
        "works_with": ["mitchell1", "shopware", "tekmetric", "shopmonkey",
                        "google_sheets"],

    },

    "auto_repair_parts_tracker": {
        "name": "Parts Availability Tracker (Auto Repair)",
        "category": "Business-Specific (Auto Repair)",
        "description": (
            "When a part needs to be ordered, system tracks the order status "
            "and automatically texts the customer when it arrives: "
            "'Your part is in — ready to schedule your repair?' "
            "Prevents the #1 drop-off in auto repair: customer forgets to come back after parts arrive."
        ),
        "annual_value": 9600,          # 2 recovered jobs/month x $400
        "monthly_cost": 10,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio", "google_sheets"],
        "applies_to": ["auto_repair"],
        "integration": (
            "Google Sheet with columns: customer name, phone, vehicle, part description, supplier, "
            "order date, expected arrival, status (ordered/arrived/installed). When your parts person "
            "updates status to 'arrived,' n8n triggers a Twilio text immediately. If no reply in 3 days, "
            "follow-up goes out. No reply in 7 days, you get a text to call personally."
        ),
        "owner_effort": (
            "One-time: set up the parts tracking sheet. 10-minute setup. Ongoing: your parts manager "
            "adds a row when a part is ordered (30 seconds) and changes status to 'arrived' when it "
            "comes in (5 seconds). This is real ongoing work — but it replaces the sticky note on the "
            "counter that falls off."
        ),
        "objections": {
            "We already call customers when parts come in": (
                "How many call attempts before you reach them? Average customer takes 2-3 attempts by "
                "phone. A text gets read in 3 minutes. If they don't reply to the text, THEN you call. "
                "The text handles 60-70% of customers without phone tag."
            ),
            "Some customers don't want the repair anymore by the time the part arrives": (
                "Those were going to cancel regardless. But 30-40% of 'didn't come back' customers just "
                "forgot or got busy. The text catches them. For the ones who changed their mind, you find "
                "out immediately instead of sitting on a part for 30 days."
            ),
            "Adding parts to a sheet is extra work for my counter guy": (
                "He is already writing down parts orders somewhere — whiteboard, notebook, sticky note. "
                "This is the same information in a sheet that triggers an automatic text. 30 seconds per "
                "part. 5 parts a day = 2.5 minutes to recover $800/month in walked-away jobs."
            ),
        },
        "works_with": ["mitchell1", "shopware", "tekmetric", "shopmonkey",
                        "google_sheets"],

    },

    # ── PEST CONTROL-SPECIFIC ────────────────────────────────────────────────

    "pest_control_recurring_reminders": {
        "name": "Recurring Treatment Reminders (Pest Control)",
        "category": "Business-Specific (Pest Control)",
        "description": (
            "Tracks every customer's treatment schedule (monthly/quarterly/annual). "
            "Sends reminder 5 days before: 'Your quarterly pest treatment is coming up — "
            "same day and time work for you?' "
            "One-tap confirm or reschedule. "
            "Reduces appointment no-shows by 50% and keeps recurring revenue locked in."
        ),
        "annual_value": 12000,         # Prevents 15% churn on recurring accounts
        "monthly_cost": 12,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio", "google_sheets"],
        "applies_to": ["pest_control"],
        "integration": (
            "Reads your customer schedule from PestRoutes, FieldRoutes, Briostack, or Google Sheet. "
            "We need: customer name, phone, service frequency (monthly/quarterly/annual), next scheduled "
            "date. n8n checks every morning for customers 5 days out. Twilio sends the reminder from "
            "your business number. Customer replies 'YES' to confirm or 'CHANGE' to reschedule."
        ),
        "owner_effort": (
            "One-time: give us your recurring customer list with service schedules. If you use PestRoutes "
            "or FieldRoutes, we pull directly. 15-minute setup. Ongoing: nothing for confirmations — "
            "automatic. For reschedule requests, you reply to the customer with a new date."
        ),
        "objections": {
            "I already send reminders through my route software": (
                "PestRoutes and FieldRoutes send email reminders with 15-20% open rates. This sends a text "
                "with 98% open rate. Both can run — the text catches everyone who ignored the email."
            ),
            "My customers are on auto-schedule, they know when we're coming": (
                "15-20% of recurring pest customers are not home when you show up. A text 5 days out gives "
                "them time to adjust or tell you to come a different day. That empty route stop costs you "
                "$30-$50 in lost efficiency."
            ),
            "What if they all reschedule and mess up my routes?": (
                "Less than 5% reschedule from a reminder. The 95% who confirm are locked in. The 5% who "
                "reschedule would have been a no-show anyway — better to know 5 days in advance."
            ),
        },
        "works_with": ["pestroutes", "fieldroutes", "briostack", "google_sheets",
                        "google_calendar"],

    },

    "pest_control_seasonal_campaigns": {
        "name": "Seasonal Pest Campaigns (Pest Control)",
        "category": "Business-Specific (Pest Control)",
        "description": (
            "4 campaigns per year timed to pest seasons: "
            "Spring (ants/termites), Summer (mosquitos/wasps), "
            "Fall (rodents/spiders), Winter (mice/roaches seeking warmth). "
            "Texts all past customers with seasonal offer. "
            "Pest control is 100% seasonal — the company that texts first wins."
        ),
        "annual_value": 16800,         # 3.5 jobs/month from campaigns x $400 avg
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 1,
        "tools": ["n8n", "twilio", "anthropic_claude"],
        "applies_to": ["pest_control"],
        "integration": (
            "Reads your full customer list from PestRoutes, FieldRoutes, Briostack, or Google Sheets. "
            "Four scheduled campaigns: March (ants/termites), June (mosquitos/wasps), September "
            "(rodents/spiders), November (mice/roaches). Claude AI writes seasonal messages using your "
            "business name and pricing. Twilio sends from your number. Dates adjustable to your market."
        ),
        "owner_effort": (
            "One-time: give us your seasonal pricing and any special offers. Approve the 4 campaign "
            "messages (we write them, you approve once). 15-minute call. Ongoing: nothing. Campaigns "
            "fire automatically. Handle inbound calls from customers who respond."
        ),
        "objections": {
            "My customers already know to call us in spring": (
                "Your recurring customers might. But what about the one-time customers from 2 years ago? "
                "Your past customer list is a goldmine most pest control companies never touch. These "
                "campaigns reactivate 10-15% of dormant customers."
            ),
            "I don't want to spam my customers with texts": (
                "Four texts per year — one per season — is not spam. 'Hey [name], ant season is here — "
                "want a perimeter treatment before they get inside? $129 for existing customers.' That is "
                "helpful, not annoying."
            ),
            "We're already booked solid in peak season": (
                "Move spring/summer campaigns earlier by 2-3 weeks to fill before competitors. For fall/"
                "winter — that is your slow season. Rodent and roach work keeps revenue steady when other "
                "companies are laying off technicians."
            ),
        },
        "works_with": ["pestroutes", "fieldroutes", "briostack", "google_sheets"],

    },

    # ── LAWN CARE-SPECIFIC ───────────────────────────────────────────────────

    "lawn_care_route_optimizer": {
        "name": "Daily Route Optimizer (Lawn Care)",
        "category": "Business-Specific (Lawn Care)",
        "description": (
            "Every morning at 6am, AI optimizes the day's job order by location "
            "to minimize drive time. Sends crew their route via text with addresses in order. "
            "Saves 45-90 minutes per day in windshield time. "
            "For a 10-job day, that's 1-2 extra jobs worth of capacity."
        ),
        "annual_value": 9600,          # 1 extra job/day x 2 days/week x $80 avg x 48 weeks
        "monthly_cost": 15,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["n8n", "google_maps"],
        "applies_to": ["lawn_care"],
        "integration": (
            "Reads tomorrow's job list from Jobber, LawnPro, Service Autopilot, or a Google Sheet with "
            "job addresses. At 6am, n8n sends addresses to Google Maps API for distance matrix "
            "optimization. Optimized route sent as a text to each crew lead with addresses in order "
            "and a Google Maps link for turn-by-turn. Re-run on demand if schedule changes."
        ),
        "owner_effort": (
            "One-time: give us access to your job schedule and crew leads' phone numbers. 15-minute "
            "setup. Ongoing: nothing — as long as your schedule is in the system, routes generate "
            "automatically. If you add or cancel a job after 6am, text the crew manually or request "
            "a re-run."
        ),
        "objections": {
            "My guys already know the area, they don't need a route": (
                "They know the area but not the optimal ORDER. A 10-job day with random address order "
                "wastes 45-90 minutes in unnecessary drive time vs. sorted by proximity. Over a week, "
                "that is $400-$800 in capacity you are leaving on the table."
            ),
            "Google Maps already does routing": (
                "Google Maps routes between 2 points. This optimizes the ORDER of 8-15 stops to minimize "
                "total drive time across the entire day. Google Maps doesn't figure out the best order — "
                "it routes in whatever order you enter."
            ),
            "My foreman decides the route, I don't want to override him": (
                "Show him the optimized route and let him decide. If he has a reason to adjust (customer "
                "requested afternoon, morning dew), he does. The AI gives him a starting point better than "
                "guessing. Most foremen adopt it within a week."
            ),
        },
        "works_with": ["jobber", "lawnpro", "service_autopilot", "google_sheets",
                        "google_calendar"],

    },

    "lawn_care_weather_reschedule": {
        "name": "Weather-Based Auto-Reschedule (Lawn Care)",
        "category": "Business-Specific (Lawn Care)",
        "description": (
            "Checks weather forecast every evening. If rain is predicted for tomorrow, "
            "automatically texts affected customers: 'Rain in the forecast tomorrow — "
            "we\'re moving you to [next available day]. Reply KEEP to keep the original time.' "
            "Eliminates the #1 operational headache for lawn care: weather rescheduling."
        ),
        "annual_value": 7200,          # Saves 5+ hrs/week of phone time during rain season
        "monthly_cost": 12,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["lawn_care"],
        "integration": (
            "NOAA weather API checks forecast for your service area every evening at 7pm. If rain "
            "probability exceeds your threshold (you set it — 60%, 70%, 80%), n8n pulls tomorrow's "
            "jobs from Jobber, Service Autopilot, or Google Sheet. Finds next available day per customer "
            "and sends reschedule text via Twilio. 'KEEP' replies stay on original schedule."
        ),
        "owner_effort": (
            "One-time: set your rain threshold, service area zip code, and scheduling system access. "
            "15-minute setup. Ongoing: nothing for the rain check — runs every evening automatically. "
            "Handle customers who want a specific reschedule date."
        ),
        "objections": {
            "I decide whether to work in the rain, not a computer": (
                "You still decide. The system handles customer communication. If the forecast says 80% "
                "rain and you want to skip, you don't make 10-15 phone calls. Set threshold to 95% if "
                "you only want it for guaranteed washouts."
            ),
            "My customers will think I'm unreliable if I reschedule for rain": (
                "'Rain in the forecast — we are moving you to Thursday for a quality cut.' That is "
                "professional, not unreliable. Customers prefer proactive communication over wet-grass "
                "cuts that leave ruts."
            ),
            "Weather forecasts are often wrong": (
                "Set threshold to 80%+ for more certainty. At 80% probability, it actually rains 75-85% "
                "of the time. The 'KEEP' reply covers false alarms — customer says KEEP, you show up. "
                "No harm done."
            ),
        },
        "works_with": ["jobber", "lawnpro", "service_autopilot", "google_sheets",
                        "google_calendar"],

    },

    # ── DENTAL-SPECIFIC ──────────────────────────────────────────────────────

    "dental_appointment_reminders": {
        "name": "Appointment Reminder System (Dental)",
        "category": "Business-Specific (Dental)",
        "description": (
            "Sends 3-touch reminder sequence for every appointment: "
            "7 days before (text), 2 days before (text), 2 hours before (text). "
            "Patients can confirm or reschedule by replying. "
            "Dental no-show rates average 15-20% — this cuts them to 5-8%. "
            "At $200/appointment, recovering 2 no-shows/day = $400/day saved."
        ),
        "annual_value": 24000,         # 2 recovered no-shows/day x $200 x 5 days x 48 weeks
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 1,
        "tools": ["n8n", "twilio", "google_calendar"],
        "applies_to": ["dental"],
        "integration": (
            "Reads appointments from Google Calendar, Dentrix calendar export, Eaglesoft, or Open Dental. "
            "Each appointment needs: patient name, phone, date, time. n8n triggers Twilio texts at 7 "
            "days, 2 days, and 2 hours before. Patient replies 'YES' to confirm or 'CHANGE' to "
            "reschedule. If using Dentrix/Eaglesoft, we sync via nightly CSV export to Google Sheets."
        ),
        "owner_effort": (
            "One-time: give us access to your appointment calendar or set up the nightly export. "
            "20-minute setup with your front desk. Ongoing: nothing. Your front desk handles reschedule "
            "requests the same way they always do — they just get them via text instead of phone call."
        ),
        "objections": {
            "We already use Lighthouse/Weave/Solutionreach for reminders": (
                "Those cost $300-$500/month. This does the same for $15/month. If your current system "
                "is working and reducing no-shows, keep it. But if you are paying $400/month for Weave "
                "and no-shows are still above 10%, the problem is message timing, not software."
            ),
            "Our no-show rate is fine": (
                "What is it? Industry average is 15-20%. If yours is 5-8%, you may not need this. If "
                "10%+, every point you reduce is $200-$400 per day in recovered production."
            ),
            "Patients will get annoyed by 3 texts": (
                "The 7-day text gets 40% confirmation. The 2-day catches the rest. The 2-hour text is "
                "a courtesy patients appreciate. Feedback from 3-touch systems is overwhelmingly positive. "
                "Patients who complain about reminders are not the ones who no-show."
            ),
        },
        "works_with": ["dentrix", "eaglesoft", "open_dental", "google_calendar",
                        "google_sheets"],

    },

    "dental_recall_system": {
        "name": "6-Month Recall System (Dental)",
        "category": "Business-Specific (Dental)",
        "description": (
            "Tracks every patient's last visit. 5 months after their last cleaning, "
            "sends: 'Hi [name], it's about time for your 6-month checkup! "
            "Want us to get you scheduled?' "
            "Follow-up at 6 months, 7 months, and 9 months if no response. "
            "Recall is the #1 revenue driver for dental offices — 60% of revenue comes from existing patients."
        ),
        "annual_value": 36000,         # 15 recalled patients/month x $200 avg cleaning+exam
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 1,
        "tools": ["n8n", "twilio", "google_sheets"],
        "applies_to": ["dental"],
        "integration": (
            "Reads patient data from Google Sheet synced from Dentrix, Eaglesoft, or Open Dental via "
            "nightly CSV export. Tracks: patient name, phone, last visit date, last service type. n8n "
            "checks daily for 5-month, 6-month, 7-month, and 9-month marks. Twilio sends recall texts "
            "from your office number. Patients who book are marked 'scheduled' to stop texts."
        ),
        "owner_effort": (
            "One-time: export your patient list with last-visit dates. We import into the tracking "
            "sheet. 20-minute setup. Ongoing: front desk marks patients as 'scheduled' when they book "
            "from a recall text — one click per patient. New patients added automatically after their "
            "first visit."
        ),
        "objections": {
            "We already do recall postcards": (
                "Postcards cost $0.75-$1.50 each with 1-3% response rate. Texts cost $0.01 each with "
                "45% open rate. Keep doing postcards AND run texts — the text catches everyone who threw "
                "the postcard away. Most practices see 15-25% response on recall texts vs. 1-3% postcards."
            ),
            "Our recall system in Dentrix/Eaglesoft works fine": (
                "Check your numbers. What percentage due for recall actually come back within 30 days? "
                "Industry average is 30-40%. The 4-touch text sequence converts 15-25% of patients who "
                "would have been lost."
            ),
            "9 months is too long to keep following up": (
                "Patients who don't respond for 9 months are ones you have already lost. The 9-month text "
                "is a last effort. About 5% convert. At $200 per cleaning, every converted patient is "
                "worth $400/year in ongoing recall revenue."
            ),
        },
        "works_with": ["dentrix", "eaglesoft", "open_dental", "google_sheets"],

    },

    "dental_new_patient_onboarding": {
        "name": "New Patient Onboarding (Dental)",
        "category": "Business-Specific (Dental)",
        "description": (
            "When a new patient books, they automatically get: "
            "1. Welcome text with office info and what to bring "
            "2. Link to pre-fill intake forms (saves 15 min at front desk) "
            "3. Reminder the day before "
            "4. Post-visit text asking about their experience "
            "5. Prompt to leave a Google review "
            "First impressions drive whether patients come back."
        ),
        "annual_value": 14400,         # Higher retention rate on new patients
        "monthly_cost": 12,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["dental"],
        "integration": (
            "Triggers when a new patient is added to your Google Calendar or scheduling system. n8n "
            "kicks off a 5-step Twilio text sequence: (1) welcome text with address and what to bring; "
            "(2) intake form link; (3) day-before reminder; (4) 2 hours post-visit experience check; "
            "(5) next day Google review prompt with direct link. All texts from your office number."
        ),
        "owner_effort": (
            "One-time: give us office info (address, parking, what to bring), intake form link (or we "
            "create one), and Google review link. Approve 5 message templates. 20-minute setup. "
            "Ongoing: nothing. Sequence triggers automatically for every new patient. Front desk "
            "books the patient in the calendar as normal."
        ),
        "objections": {
            "We already give new patients a welcome packet": (
                "This replaces the 15-minute phone call your front desk makes to every new patient to "
                "explain what to bring and how to find the office. With 10 new patients per month, that "
                "is 2.5 hours of phone time replaced by an automatic text."
            ),
            "Patients won't fill out forms online": (
                "65% prefer to fill out forms at home vs. the waiting room. The ones who don't still come "
                "in and fill out paper. But every patient who does it ahead saves 15 minutes of front "
                "desk time."
            ),
            "The review request feels pushy right after their visit": (
                "Review request goes out the NEXT DAY. The post-visit text (#4) goes 2 hours after: "
                "'How was your visit?' If they reply negative, the review prompt (#5) is suppressed "
                "and you get an alert to follow up personally."
            ),
            "What if the patient had a bad experience and gets the review text?": (
                "The post-visit experience check (#4) catches this. If they reply with anything negative, "
                "review prompt is automatically suppressed. The system protects you from asking unhappy "
                "patients for reviews."
            ),
        },
        "works_with": ["dentrix", "eaglesoft", "open_dental", "google_calendar",
                        "google_sheets"],

    },

}

# ──────────────────────────────────────────────────────────────────────────────
# CALCULATE PRIORITY SCORES
# ──────────────────────────────────────────────────────────────────────────────

for key, auto in AUTOMATION_CATALOG.items():
    monthly_cost = auto.get("monthly_cost", 1)
    annual_value = auto.get("annual_value", 0)
    difficulty = auto.get("difficulty", 3)
    roi_ratio = (annual_value / max(monthly_cost * 12, 1))
    auto["priority_score"] = round(roi_ratio / difficulty, 1)
    auto["roi_ratio"] = round(roi_ratio, 1)


# ──────────────────────────────────────────────────────────────────────────────
# BUSINESS TYPE MAPPINGS
# ──────────────────────────────────────────────────────────────────────────────

BUSINESS_TYPE_ALIASES = {
    "hvac": ["hvac", "heating", "cooling", "air conditioning", "ac repair"],
    "plumber": ["plumber", "plumbing"],
    "electrician": ["electrician", "electrical"],
    "roofer": ["roofer", "roofing", "roof repair"],
    "junk_removal": ["junk removal", "junk_removal", "junk hauling", "haul away", "debris removal"],
    "cleaning": ["cleaning", "house cleaning", "maid service", "janitorial"],
    "auto_repair": ["auto repair", "mechanic", "auto_repair", "car repair"],
    "law_firm": ["law firm", "law_firm", "attorney", "lawyer"],
    "pest_control": ["pest control", "pest_control", "exterminator"],
    "lawn_care": ["lawn care", "lawn_care", "landscaping", "yard service"],
    "gym": ["gym", "fitness", "crossfit", "studio"],
    "retail": ["retail", "store", "shop"],
    "restaurant": ["restaurant", "food", "cafe", "diner"],
    "real_estate": ["real estate", "real_estate", "realtor", "agent"],
    "dental": ["dental", "dentist", "dental office", "orthodontist"],
    "pressure_washing": ["pressure washing", "pressure_washing", "power washing", "soft wash"],
}

def normalize_business_type(raw_type: str) -> str:
    """Normalize a business type string to a catalog key."""
    if not raw_type:
        return raw_type or ""
    raw = raw_type.lower().strip()
    for canonical, aliases in BUSINESS_TYPE_ALIASES.items():
        if raw in aliases or raw == canonical:
            return canonical
    # fuzzy: check if any alias is a substring
    for canonical, aliases in BUSINESS_TYPE_ALIASES.items():
        for alias in aliases:
            if alias in raw or raw in alias:
                return canonical
    return raw  # return as-is if unknown


def get_recommendations(business_type: str, existing_automations: list = None) -> list:
    """
    Return a prioritized list of automation recommendations for a given business type.

    Args:
        business_type: e.g. "hvac", "plumber", "junk removal"
        existing_automations: list of automation keys already built (to exclude)

    Returns:
        List of automation dicts sorted by priority_score descending.
        Each dict includes the catalog key as "key".
    """
    if existing_automations is None:
        existing_automations = []

    biz_type = normalize_business_type(business_type)
    results = []

    for key, auto in AUTOMATION_CATALOG.items():
        if key in existing_automations:
            continue
        applies = auto.get("applies_to", [])
        if "all" in applies or biz_type in applies:
            entry = dict(auto)
            entry["key"] = key
            results.append(entry)

    # Sort by priority_score descending
    results.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    return results


def scale_to_job_value(recommendations: list, job_value: float) -> list:
    """
    Rescale annual_value estimates based on the actual (or provided) avg job value.
    Catalog values assume a ~$300 baseline. Uses dampened scaling (square root)
    capped at 3x to prevent absurd numbers for high-value businesses like roofing.
    """
    BASELINE_JOB = 300
    MIN_SCALE = 0.3
    MAX_SCALE = 3.0
    if not job_value or job_value <= 0:
        return recommendations

    raw_scale = job_value / BASELINE_JOB
    dampened = raw_scale ** 0.5
    scale = max(MIN_SCALE, min(MAX_SCALE, dampened))
    for rec in recommendations:
        original = rec.get("annual_value", 0)
        scaled = int(round(original * scale / 100) * 100)
        rec["annual_value"] = scaled
        rec["value_note"] = f"Scaled from ${original:,} to ${scaled:,} for ${job_value:.0f} avg job (dampened {scale:.1f}x)"
    return recommendations


def get_catalog_summary() -> dict:
    """Return a summary of the catalog for reporting."""
    categories = {}
    for key, auto in AUTOMATION_CATALOG.items():
        cat = auto.get("category", "Other")
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    total_annual_value = sum(a.get("annual_value", 0) for a in AUTOMATION_CATALOG.values())
    total_monthly_cost = sum(a.get("monthly_cost", 0) for a in AUTOMATION_CATALOG.values())

    return {
        "total_automations": len(AUTOMATION_CATALOG),
        "categories": categories,
        "total_annual_value_if_all_built": total_annual_value,
        "total_monthly_cost_if_all_built": total_monthly_cost,
        "roi_ratio": round(total_annual_value / max(total_monthly_cost * 12, 1), 1),
    }


if __name__ == "__main__":
    import sys
    biz_type = sys.argv[1] if len(sys.argv) > 1 else "hvac"
    print(f"\nTop automations for: {biz_type}")
    print("=" * 60)
    recs = get_recommendations(biz_type)
    for i, r in enumerate(recs[:10], 1):
        print(f"\n{i}. {r['name']}")
        print(f"   Category:      {r['category']}")
        print(f"   Annual Value:  ${r['annual_value']:,}")
        print(f"   Monthly Cost:  ${r['monthly_cost']}/mo")
        print(f"   ROI Ratio:     {r['roi_ratio']}x")
        print(f"   Priority Score:{r['priority_score']}")
        print(f"   Build Time:    {r['build_time_hours']}h")
        print(f"   Difficulty:    {r['difficulty']}/5")

    summary = get_catalog_summary()
    print(f"\n{'='*60}")
    print(f"CATALOG: {summary['total_automations']} automations across {len(summary['categories'])} categories")
    print(f"If ALL built: ${summary['total_annual_value_if_all_built']:,}/year value at ${summary['total_monthly_cost_if_all_built']:,}/month cost")
