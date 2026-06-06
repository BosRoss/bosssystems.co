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
            "books the appointment, and sends a confirmation. Never goes to voicemail. "
            "Built on Retell AI + Claude. Books jobs while the owner is on a job."
        ),
        "annual_value": 52000,         # ~4 recovered jobs/week x $250 avg x 52 weeks
        "monthly_cost": 60,
        "build_time_hours": 2,
        "difficulty": 1,
        "tools": ["retell_ai", "n8n", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "auto_repair", "law_firm", "pest_control",
                        "lawn_care", "gym", "retail", "restaurant", "real_estate", "all"],
    },

    "missed_call_textback": {
        "name": "Missed Call Text-Back",
        "category": "Customer Acquisition",
        "description": (
            "When any call is missed, the caller gets an automated text within 60 seconds: "
            "'Hey, this is [business]! We just missed your call — what can we help you with?' "
            "85% of callers never call back. A text catches them before they call a competitor."
        ),
        "annual_value": 9600,          # ~$800/month recovered from missed calls
        "monthly_cost": 15,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
    },

    "outbound_caller": {
        "name": "AI Outbound Cold Caller",
        "category": "Customer Acquisition",
        "description": (
            "AI calls a list of prospects every day, introduces the business, "
            "identifies pain points, and books demos or appointments. "
            "Works from a Google Places scraped prospect list. "
            "Runs 10am and 2pm, caps at 50 calls/day, skips duplicates."
        ),
        "annual_value": 36000,         # 3 clients/month x $1,000 avg job x 12 months
        "monthly_cost": 80,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["retell_ai", "n8n", "google_places"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair", "law_firm"],
    },

    "review_mining": {
        "name": "Competitor Review Mining",
        "category": "Customer Acquisition",
        "description": (
            "Scrapes 1-2 star Google reviews from competitors every week. "
            "Identifies unhappy customers who are actively looking for alternatives. "
            "Adds them to an outreach list. These are the hottest prospects you can find — "
            "they already want someone new."
        ),
        "annual_value": 18000,         # 1.5 clients/month from review mining x avg job value
        "monthly_cost": 20,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_places"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair"],
    },

    "google_lsa_optimizer": {
        "name": "Google LSA Auto-Optimizer",
        "category": "Customer Acquisition",
        "description": (
            "Monitors Google Local Services Ads performance weekly. "
            "Alerts when cost-per-lead spikes, ad pauses, or ranking drops. "
            "Provides weekly recommendations: which job types to promote, "
            "what budget to set, which days have best ROI."
        ),
        "annual_value": 12000,         # Prevents ~$1,000/month in wasted ad spend
        "monthly_cost": 10,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_places"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair", "law_firm"],
    },

    "social_media_ai": {
        "name": "Social Media AI (Daily Posts)",
        "category": "Customer Acquisition",
        "description": (
            "Generates and schedules one social post per day across Facebook and Google Business. "
            "Posts include: before/after jobs, seasonal tips, local shoutouts, promotions. "
            "Written by Claude in the business owner's voice. "
            "Owner reviews via ntfy before posting (optional approval mode)."
        ),
        "annual_value": 8400,          # $700/month equivalent of social media mgmt services
        "monthly_cost": 25,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["n8n", "anthropic_claude"],
        "applies_to": ["all"],
    },

    # ── SALES & QUOTING ───────────────────────────────────────────────────────

    "quote_generator": {
        "name": "AI Quote Generator",
        "category": "Sales & Quoting",
        "description": (
            "Customer texts or emails a description (or photo) of their job. "
            "AI analyzes it and sends back a professional quote within 2 minutes. "
            "Saves 30-45 minutes per estimate. Owner can approve/adjust before it sends. "
            "Closes more jobs because prospects get instant answers instead of waiting 2 days."
        ),
        "annual_value": 19200,         # 4 extra jobs/month closed due to instant response x $400 avg
        "monthly_cost": 35,
        "build_time_hours": 4,
        "difficulty": 3,
        "tools": ["n8n", "anthropic_claude", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair"],
    },

    "follow_up_sequence": {
        "name": "Lead Follow-Up Sequence",
        "category": "Sales & Quoting",
        "description": (
            "When a prospect contacts but does not book, they automatically get a 5-touch "
            "sequence over 7 days: text day 1, text day 3, email day 5, text day 7, "
            "final 'closing the file' text day 10. Closes 15-25% of prospects who went cold."
        ),
        "annual_value": 14400,         # 10% more closes x 3 leads/day x $400 avg job
        "monthly_cost": 20,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
    },

    "lead_scoring": {
        "name": "AI Lead Scoring",
        "category": "Sales & Quoting",
        "description": (
            "Scores every inbound lead 1-10 based on: job type, timing urgency, "
            "location in service area, how they found the business, what they said. "
            "High-score leads get immediate call-back alert to owner. "
            "Owner spends time on $2,000 jobs, not $75 jobs."
        ),
        "annual_value": 7200,          # Owner prioritizes better, closes more high-value jobs
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "anthropic_claude"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "law_firm", "real_estate"],
    },

    "proposal_generator": {
        "name": "AI Proposal Generator",
        "category": "Sales & Quoting",
        "description": (
            "For larger jobs ($1,000+), AI generates a professional PDF proposal: "
            "scope of work, pricing breakdown, timeline, warranty, payment terms. "
            "Sends automatically after the estimate call. "
            "Looks 10x more professional than handwritten quotes."
        ),
        "annual_value": 9600,          # Higher close rate on big jobs due to professionalism
        "monthly_cost": 20,
        "build_time_hours": 3,
        "difficulty": 3,
        "tools": ["n8n", "anthropic_claude"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "law_firm"],
    },

    # ── OPERATIONS ────────────────────────────────────────────────────────────

    "appointment_booking": {
        "name": "Appointment Booking Automation",
        "category": "Operations",
        "description": (
            "Integrates with Google Calendar (or any calendar). "
            "AI books appointments directly into the calendar, sends "
            "customer confirmation text with date/time/address, "
            "sends reminder text 24 hours before, another 2 hours before. "
            "Reduces no-shows by 40%."
        ),
        "annual_value": 6000,          # 2 fewer no-shows/month x $250 avg
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_calendar", "twilio"],
        "applies_to": ["all"],
    },

    "dispatch_automation": {
        "name": "Dispatch Automation",
        "category": "Operations",
        "description": (
            "When a job is booked, automatically assigns it to the right crew "
            "based on location, skill type, and current schedule. "
            "Sends crew their daily job list at 7am via text. "
            "Optimizes route order. Owner stops being a dispatcher."
        ),
        "annual_value": 14400,         # Owner saves 2 hrs/day x $40/hr equivalent
        "monthly_cost": 30,
        "build_time_hours": 4,
        "difficulty": 3,
        "tools": ["n8n", "google_maps", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care"],
    },

    "job_status_updates": {
        "name": "Automated Job Status Texts",
        "category": "Operations",
        "description": (
            "Customers automatically receive texts at each job milestone: "
            "'Your tech is on the way — 20 min out,' 'Job is starting now,' 'All done!' "
            "Reduces 'where are you' calls by 80%. "
            "Customers feel informed = 5-star reviews."
        ),
        "annual_value": 4800,          # Reduces owner phone time + drives review volume
        "monthly_cost": 12,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair"],
    },

    "invoice_generator": {
        "name": "Auto Invoice Generator",
        "category": "Operations",
        "description": (
            "When a job is marked complete, AI instantly creates a professional invoice "
            "and texts/emails it to the customer. "
            "Pre-filled with their info, job details, line items, and payment link. "
            "Owner stops writing invoices by hand or forgetting to send them."
        ),
        "annual_value": 7200,          # Faster payment + fewer forgotten invoices
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "stripe", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "junk_removal",
                        "cleaning", "pest_control", "lawn_care", "auto_repair", "law_firm"],
    },

    "payment_collection": {
        "name": "Payment Collection Automation",
        "category": "Operations",
        "description": (
            "When job completes, customer automatically gets a text with a payment link. "
            "If not paid in 24 hours, gets a reminder. If not paid in 72 hours, owner gets alerted. "
            "Reduces unpaid invoices by 60%. "
            "Average time-to-payment drops from 14 days to 2 days."
        ),
        "annual_value": 8400,          # Faster collections + fewer write-offs
        "monthly_cost": 15,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "stripe", "twilio"],
        "applies_to": ["all"],
    },

    # ── CUSTOMER RETENTION ────────────────────────────────────────────────────

    "review_request": {
        "name": "Review Request Automation",
        "category": "Customer Retention",
        "description": (
            "2 hours after payment confirmed, customer automatically gets a text: "
            "'Hi [name]! It was great working with you. Would you mind leaving us "
            "a quick Google review? It means everything to a local business. [link]' "
            "Converts 25-35% of customers into reviewers. "
            "Reviews are the #1 driver of inbound calls for service businesses."
        ),
        "annual_value": 18000,         # Reviews compound — $1,500/month more revenue at scale
        "monthly_cost": 10,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
    },

    "re_engagement_campaign": {
        "name": "Re-Engagement Campaigns",
        "category": "Customer Retention",
        "description": (
            "Every customer who has not hired the business in 90 days gets "
            "a personalized text: 'Hey [name], it has been a few months — "
            "how is [thing we fixed] holding up? We are running a [seasonal] special.' "
            "Reactivates 10-15% of dormant customers. "
            "Cheapest customer to get is one you already have."
        ),
        "annual_value": 12000,         # 1 job/month recovered x $1,000 avg job value
        "monthly_cost": 20,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio", "anthropic_claude"],
        "applies_to": ["all"],
    },

    "seasonal_campaigns": {
        "name": "Seasonal Campaign Calendar (12/year)",
        "category": "Customer Retention",
        "description": (
            "12 pre-written campaigns run automatically throughout the year: "
            "Spring AC tune-up, summer emergency response, fall furnace check, "
            "winter pipe protection, etc. Each campaign texts all past customers "
            "with a timely, relevant offer. Runs itself — owner does nothing."
        ),
        "annual_value": 24000,         # 2 jobs/month from campaigns x avg job x 12 months
        "monthly_cost": 25,
        "build_time_hours": 3,
        "difficulty": 2,
        "tools": ["n8n", "twilio", "anthropic_claude"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "cleaning",
                        "pest_control", "lawn_care", "auto_repair"],
    },

    "referral_program": {
        "name": "Automated Referral Program",
        "category": "Customer Retention",
        "description": (
            "After every completed job, customer gets a text: "
            "'Know anyone who needs [service]? Send them our way and we will take "
            "$25 off their next visit — and yours.' "
            "Tracks referrals, sends referrer their discount automatically. "
            "Word of mouth is the best lead source. This systematizes it."
        ),
        "annual_value": 9600,          # 0.8 referrals/month x avg job value
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
    },

    "birthday_outreach": {
        "name": "Birthday / Anniversary Outreach",
        "category": "Customer Retention",
        "description": (
            "Sends a personal text on each customer's birthday or job anniversary: "
            "'Happy birthday from [business]! Use code BDAY for $20 off your next service.' "
            "Makes customers feel remembered. "
            "Open rate for birthday texts is 98%. Response rate 8x higher than normal campaigns."
        ),
        "annual_value": 3600,          # Low cost, high conversion on warmest customers
        "monthly_cost": 8,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["all"],
    },

    # ── INTELLIGENCE ──────────────────────────────────────────────────────────

    "revenue_dashboard": {
        "name": "Real-Time Revenue Dashboard",
        "category": "Intelligence",
        "description": (
            "Live dashboard showing: today's revenue, jobs booked vs. completed, "
            "monthly trend, top job types, customer acquisition sources, "
            "review count trend, and crew performance. "
            "Owner knows the score at a glance instead of doing mental math."
        ),
        "annual_value": 6000,          # Better decisions + time saved on bookkeeping
        "monthly_cost": 20,
        "build_time_hours": 4,
        "difficulty": 3,
        "tools": ["n8n", "google_sheets"],
        "applies_to": ["all"],
    },

    "competitor_monitor": {
        "name": "Competitor Intelligence Monitor",
        "category": "Intelligence",
        "description": (
            "Weekly report on every major competitor: new reviews, rating changes, "
            "price changes, new service offerings, Google ranking shifts. "
            "Alerts owner if a competitor drops below 4.0 stars "
            "(opportunity to poach their customers). Delivered every Monday."
        ),
        "annual_value": 4800,          # Catch competitive threats and opportunities early
        "monthly_cost": 15,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "google_places"],
        "applies_to": ["all"],
    },

    "employee_tracking": {
        "name": "Employee Performance Tracker",
        "category": "Intelligence",
        "description": (
            "Tracks: jobs completed per crew member, average job rating, "
            "on-time arrival rate, callbacks/complaints per tech. "
            "Weekly report to owner. Best techs get called out. "
            "Problem techs get addressed before they cost money."
        ),
        "annual_value": 7200,          # Retaining good techs + pruning bad ones saves money
        "monthly_cost": 15,
        "build_time_hours": 3,
        "difficulty": 3,
        "tools": ["n8n", "google_sheets"],
        "applies_to": ["hvac", "plumber", "electrician", "roofer", "cleaning",
                        "pest_control", "lawn_care"],
    },

    "inventory_alerts": {
        "name": "Inventory and Supply Alerts",
        "category": "Intelligence",
        "description": (
            "Owner texts a simple command ('filters low — 10 left') "
            "and the system logs it. When stock hits reorder threshold, "
            "owner gets an alert with a direct order link. "
            "Never run out of filters, freon, or parts mid-job again."
        ),
        "annual_value": 3600,          # Prevents emergency supply runs and job delays
        "monthly_cost": 8,
        "build_time_hours": 1,
        "difficulty": 1,
        "tools": ["n8n", "twilio"],
        "applies_to": ["hvac", "plumber", "electrician", "pest_control"],
    },

    "review_response_ai": {
        "name": "AI Review Response System",
        "category": "Intelligence",
        "description": (
            "When a new Google review comes in, AI drafts a personalized response "
            "and sends it to owner for 1-tap approval. "
            "For 5-star reviews: thank them and highlight the work done. "
            "For 1-3 star reviews: de-escalate, offer resolution, draft professionally. "
            "Businesses that respond to reviews get 35% more clicks."
        ),
        "annual_value": 4800,          # Review velocity and click-through improvement
        "monthly_cost": 12,
        "build_time_hours": 2,
        "difficulty": 2,
        "tools": ["n8n", "anthropic_claude", "google_places"],
        "applies_to": ["all"],
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
}

def normalize_business_type(raw_type: str) -> str:
    """Normalize a business type string to a catalog key."""
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
    Catalog values assume a ~$300 baseline. This adjusts proportionally.
    Values are estimates — labeled accordingly.
    """
    BASELINE_JOB = 300
    if not job_value or job_value <= 0:
        return recommendations

    scale = job_value / BASELINE_JOB
    for rec in recommendations:
        original = rec.get("annual_value", 0)
        scaled = int(round(original * scale / 100) * 100)
        rec["annual_value"] = scaled
        rec["value_note"] = f"Scaled from ${original:,} baseline to ${scaled:,} using ${job_value:.0f} avg job value (industry estimate)"
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
