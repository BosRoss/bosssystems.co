#!/usr/bin/env python3
"""
ATLAS Country Deep Model
========================
Deep political intelligence profiles for 67+ countries.
Tracks government structure, power brokers, money flows,
foreign influence, internal stability, and real vs stated politics.

Updated dynamically from ATLAS scan data + annual governance datasets.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("ATLAS.country")

ATLAS_DIR = Path.home() / "Library" / "Application Support" / "BOSS" / "atlas_data"
PROFILES_PATH = ATLAS_DIR / "country_profiles.json"


# ---------------------------------------------------------------------------
# Deep Country Profiles — Seed Data
# ---------------------------------------------------------------------------
# Each profile covers 8 dimensions that news won't tell you:
# 1. Government structure (who officially holds power)
# 2. Power brokers (who ACTUALLY holds power)
# 3. Money flows (where the money goes and who controls it)
# 4. Foreign influence (who pulls strings from outside)
# 5. Internal stability (what could break)
# 6. Historical context (how we got here)
# 7. Real vs stated politics (the gap between narrative and reality)
# 8. ATLAS assessment (trajectory + risks)

SEED_PROFILES: Dict[str, dict] = {
    "US": {
        "name": "United States",
        "government": {
            "system": "Federal presidential constitutional republic",
            "head_of_state": "President",
            "legislature": "Bicameral (Senate + House)",
            "judiciary": "Independent (Supreme Court, lifetime appointments)",
            "real_power_center": "Executive + corporate lobby + regulatory capture",
            "succession": "Election (4-year cycle)",
            "constitutional_strength": "strong",
        },
        "power_brokers": {
            "military": {"influence": 0.35, "mechanism": "Defense budget lobby, revolving door with contractors", "key_entities": ["Pentagon", "Lockheed Martin", "Raytheon", "Northrop Grumman"]},
            "oligarchs": {"influence": 0.7, "sectors": ["tech", "finance", "energy", "pharma"], "mechanism": "Campaign finance, lobbying, media ownership"},
            "intelligence": {"influence": 0.4, "agencies": ["CIA", "NSA", "FBI", "DIA", "NGA"], "oversight": "Congressional (SSCI, HPSCI) — limited effectiveness"},
            "media": {"concentration": "high", "key_owners": ["Comcast/NBC", "Disney/ABC", "Warner/CNN", "Fox Corp", "Sinclair"], "mechanism": "Narrative framing, agenda setting"},
            "religious": {"influence": 0.25, "groups": ["Evangelical Christian right"], "mechanism": "Voting bloc, social policy pressure"},
            "organized_crime": {"influence": 0.1, "type": "Financial crime, corporate fraud"},
        },
        "money_flows": {
            "gdp_usd_b": 28781,
            "budget_pct": {"defense": 3.4, "healthcare": 17.8, "education": 5.0, "social": 12.0},
            "industry_control": {"state_owned_pct": 3, "oligarch_controlled_pct": 25, "foreign_owned_pct": 12},
            "corruption_channels": ["Lobbying (legal bribery)", "Revolving door", "Campaign finance", "Regulatory capture", "Stock trading by officials"],
            "sanctions_role": "Primary imposer (OFAC)",
            "debt_to_gdp": 123,
            "trade_dependencies": {"CN": 0.15, "MX": 0.15, "CA": 0.14, "EU": 0.18},
        },
        "foreign_influence": {
            "leverage_over": {"Global": "Military (750+ bases), USD reserve currency, tech platforms, intelligence sharing"},
            "leverage_by": {"CN": "Trade dependency, debt holdings", "SA": "Oil pricing, petrodollar", "IL": "Lobby (AIPAC)"},
            "alliances": ["NATO", "Five Eyes", "AUKUS", "G7", "G20", "Quad"],
            "hostile": ["IR", "KP", "contested: CN, RU"],
            "bases_abroad": 750,
            "bases_hosted": 0,
        },
        "stability": {
            "score": 7.0,
            "protest_level": "moderate",
            "media_freedom_trend": "declining",
            "judicial_independence": "under_pressure",
            "ethnic_tensions": "elevated",
            "separatism_risk": 0.05,
            "coup_risk": 0.01,
            "key_fault_lines": ["Urban-rural polarization", "Racial inequality", "Wealth concentration", "Institutional trust collapse"],
        },
        "history": {
            "government_origin": "Constitutional founding 1789, continuous democratic system",
            "last_regime_change": "N/A",
            "precedent_events": ["Civil War 1861-65", "Watergate 1974", "Jan 6 2021 Capitol breach"],
            "cyclical_patterns": ["Polarization waves", "Interventionism/isolationism cycles", "Economic inequality → populist movements"],
        },
        "real_vs_stated": {
            "stated_narrative": "Leader of the free world, defender of democracy and human rights",
            "actual_dynamics": "Corporate duopoly. Both parties serve Wall Street and defense contractors. Regulatory capture, gerrymandering, and media tribalism keep structural reform impossible. Public trust in institutions at historic low.",
            "narrative_gap": 0.6,
            "key_contradictions": [
                "Promotes democracy abroad while gerrymandering at home",
                "Anti-corruption messaging while legal lobbying = structural bribery",
                "Free press but media owned by 5 corporations",
            ],
        },
        "democracy_score": 7.0,
    },
    "CN": {
        "name": "China",
        "government": {
            "system": "Unitary one-party socialist republic",
            "head_of_state": "President (General Secretary of CCP)",
            "legislature": "National People's Congress (rubber stamp)",
            "judiciary": "Party-controlled, no independence",
            "real_power_center": "CCP Politburo Standing Committee, Xi Jinping personally",
            "succession": "Party congress (abolished term limits 2018)",
            "constitutional_strength": "weak (party above constitution)",
        },
        "power_brokers": {
            "military": {"influence": 0.6, "mechanism": "PLA reports to party, not state. Xi chairs Central Military Commission", "key_entities": ["PLA", "PLA Navy", "PLA Rocket Force", "Strategic Support Force"]},
            "oligarchs": {"influence": 0.3, "sectors": ["tech", "real_estate", "finance"], "mechanism": "Tolerated as long as they serve party goals — Jack Ma example"},
            "intelligence": {"influence": 0.5, "agencies": ["MSS", "MPS", "PLA Intelligence"], "oversight": "None — reports to party"},
            "media": {"concentration": "total_state", "key_owners": ["CCP Propaganda Dept", "Xinhua", "CCTV", "People's Daily"], "mechanism": "Complete information control, Great Firewall"},
            "religious": {"influence": 0.0, "groups": [], "mechanism": "Suppressed — Uyghur Muslims, Tibetan Buddhists, Falun Gong persecuted"},
            "organized_crime": {"influence": 0.15, "type": "Corruption networks within CCP, triads in semi-autonomous regions"},
        },
        "money_flows": {
            "gdp_usd_b": 17963,
            "budget_pct": {"defense": 1.7, "healthcare": 5.6, "education": 3.6, "social": 8.0},
            "industry_control": {"state_owned_pct": 40, "oligarch_controlled_pct": 20, "foreign_owned_pct": 5},
            "corruption_channels": ["CCP patronage networks", "Land rights manipulation", "SOE embezzlement", "Shadow banking"],
            "sanctions_role": "Target of Western tech sanctions, counter-sanctions on Australia/Lithuania",
            "debt_to_gdp": 83,
            "trade_dependencies": {"US": 0.15, "EU": 0.14, "ASEAN": 0.15, "JP": 0.06, "KR": 0.07},
        },
        "foreign_influence": {
            "leverage_over": {"Developing world": "Belt and Road debt, infrastructure investment", "Supply chains": "Manufacturing dominance", "Rare earths": "80%+ global processing"},
            "leverage_by": {"US": "Tech sanctions, Taiwan policy", "Semiconductor": "TSMC/ASML dependency"},
            "alliances": ["SCO", "BRICS", "BRI partners"],
            "hostile": ["TW", "contested: US, IN, JP, AU, PH, VN"],
            "bases_abroad": 3,
            "bases_hosted": 0,
        },
        "stability": {
            "score": 6.0,
            "protest_level": "suppressed",
            "media_freedom_trend": "none",
            "judicial_independence": "none",
            "ethnic_tensions": "severe_suppressed",
            "separatism_risk": 0.15,
            "coup_risk": 0.02,
            "key_fault_lines": ["Property crisis/Evergrande", "Youth unemployment 20%+", "Uyghur/Tibet/HK suppression", "Demographic collapse", "Local government debt"],
        },
        "history": {
            "government_origin": "CCP revolution 1949, current system post-Deng reform era",
            "last_regime_change": "1949 (revolution), 2018 (Xi term limit abolition = regime change within system)",
            "precedent_events": ["Tiananmen 1989", "Hong Kong crackdown 2020", "Zero-COVID protests 2022"],
            "cyclical_patterns": ["Dynasty cycle (strongman → overreach → collapse)", "Reform-retrench oscillation"],
        },
        "real_vs_stated": {
            "stated_narrative": "Peaceful rise, shared prosperity, Chinese Dream, rejuvenation of the nation",
            "actual_dynamics": "Xi holds more power than any leader since Mao. CCP controls all media, internet, and judiciary. Surveillance state monitors 1.4 billion people. Dissent is criminal — disappearances routine.",
            "narrative_gap": 0.9,
            "key_contradictions": [
                "Anti-corruption campaign used to purge rivals",
                "Peaceful rise while militarizing South China Sea",
                "Common prosperity while billionaires serve party",
            ],
        },
        "democracy_score": 1.0,
    },
    "RU": {
        "name": "Russia",
        "government": {
            "system": "Federal semi-presidential republic (de jure), personalist autocracy (de facto)",
            "head_of_state": "President (Putin since 2000)",
            "legislature": "State Duma (captured, rubber stamp)",
            "judiciary": "Controlled by Kremlin",
            "real_power_center": "Putin personally + siloviki (security services veterans)",
            "succession": "Managed elections (no real opposition since Navalny elimination)",
            "constitutional_strength": "weak (amended to suit Putin)",
        },
        "power_brokers": {
            "military": {"influence": 0.5, "mechanism": "Defense spending 6%+ GDP during war, MoD massive patronage network", "key_entities": ["Russian Armed Forces", "Wagner remnants/Africa Corps", "GRU", "Rosgvardia"]},
            "oligarchs": {"influence": 0.3, "sectors": ["energy", "metals", "banking"], "mechanism": "Tolerated if loyal — Khodorkovsky example of disobedience cost"},
            "intelligence": {"influence": 0.7, "agencies": ["FSB", "SVR", "GRU"], "oversight": "None — FSB is power center, Putin is ex-KGB"},
            "media": {"concentration": "total_state", "key_owners": ["Kremlin-controlled: RT, Tass, RIA Novosti, Channel One"], "mechanism": "Complete domestic information control"},
            "religious": {"influence": 0.2, "groups": ["Russian Orthodox Church (Patriarch Kirill)"], "mechanism": "Ideological legitimization of regime and war"},
            "organized_crime": {"influence": 0.3, "type": "State-criminal nexus, sanctions evasion networks, money laundering"},
        },
        "money_flows": {
            "gdp_usd_b": 2021,
            "budget_pct": {"defense": 6.0, "healthcare": 3.5, "education": 3.7, "social": 10.0},
            "industry_control": {"state_owned_pct": 55, "oligarch_controlled_pct": 25, "foreign_owned_pct": 3},
            "corruption_channels": ["State procurement fraud", "Oligarch kickbacks", "Military budget theft", "Sanctions evasion networks", "Putin's personal wealth network"],
            "sanctions_role": "Heavily sanctioned (Western coalition)",
            "debt_to_gdp": 20,
            "trade_dependencies": {"CN": 0.30, "IN": 0.08, "TR": 0.05, "EU_residual": 0.10},
        },
        "foreign_influence": {
            "leverage_over": {"Energy": "Gas to EU (declining), oil globally", "Nuclear": "Rosatom builds 60% of world's new reactors", "Africa": "Wagner/Africa Corps military presence", "Central Asia": "CSTO security umbrella"},
            "leverage_by": {"CN": "Economic dependency growing, junior partner", "Sanctions": "Western coalition restricting tech/finance"},
            "alliances": ["CSTO", "SCO", "BRICS", "bilateral: CN, IR, KP, SY"],
            "hostile": ["UA (active war)", "NATO members", "contested: GE, MD"],
            "bases_abroad": 15,
            "bases_hosted": 0,
        },
        "stability": {
            "score": 5.0,
            "protest_level": "suppressed",
            "media_freedom_trend": "none",
            "judicial_independence": "none",
            "ethnic_tensions": "managed",
            "separatism_risk": 0.1,
            "coup_risk": 0.05,
            "key_fault_lines": ["Ukraine war casualties/costs", "Sanctions economic pressure", "Elite fractures (Prigozhin precedent)", "Post-Putin succession crisis", "Ethnic republic tensions"],
        },
        "history": {
            "government_origin": "Post-Soviet 1991, Putin consolidated power 2000-2012",
            "last_regime_change": "1991 (Soviet collapse), 2000 (Putin era begins)",
            "precedent_events": ["Soviet collapse 1991", "Chechen wars", "Georgia 2008", "Crimea 2014", "Full Ukraine invasion 2022", "Prigozhin mutiny 2023"],
            "cyclical_patterns": ["Strongman → overextension → collapse (Tsars, USSR, potentially Putin)", "Territorial expansion → resource drain → retreat"],
        },
        "real_vs_stated": {
            "stated_narrative": "Defending against NATO expansion, protecting Russian speakers, multipolar world order",
            "actual_dynamics": "Full authoritarian state. All opposition eliminated — Navalny died in prison. Elections are theater. Media is state propaganda. Criticizing the war is criminal. Regime stable through fear and nationalism.",
            "narrative_gap": 0.95,
            "key_contradictions": [
                "Denazification claim while employing Wagner neo-Nazis",
                "Anti-imperialism narrative while conducting imperial war",
                "Protecting civilians while bombing Ukrainian cities",
            ],
        },
        "democracy_score": 1.5,
    },
    "IN": {
        "name": "India",
        "government": {
            "system": "Federal parliamentary constitutional republic",
            "head_of_state": "President (ceremonial), PM holds executive power",
            "legislature": "Bicameral (Rajya Sabha + Lok Sabha)",
            "judiciary": "Nominally independent, increasingly under pressure",
            "real_power_center": "PM Modi personally + RSS/BJP apparatus + corporate allies",
            "succession": "Election (5-year cycle, first-past-the-post)",
            "constitutional_strength": "strong on paper, weakening in practice",
        },
        "power_brokers": {
            "military": {"influence": 0.2, "mechanism": "Professional military under civilian control, defense procurement leverage", "key_entities": ["Indian Armed Forces", "RAW", "IB"]},
            "oligarchs": {"influence": 0.6, "sectors": ["energy", "telecom", "infrastructure", "tech"], "mechanism": "Adani and Ambani empires deeply intertwined with government contracts"},
            "intelligence": {"influence": 0.3, "agencies": ["RAW", "IB", "NTRO", "DIA"], "oversight": "Limited parliamentary oversight"},
            "media": {"concentration": "high_partisan", "key_owners": ["Adani (NDTV)", "Reliance/Network18", "Zee"], "mechanism": "Largely captured — critical journalists face raids and tax investigations"},
            "religious": {"influence": 0.5, "groups": ["RSS/Hindutva movement", "VHP"], "mechanism": "Hindu nationalist ideology is governing party's core identity"},
            "organized_crime": {"influence": 0.15, "type": "Political-criminal nexus in state politics, land mafia"},
        },
        "money_flows": {
            "gdp_usd_b": 3937,
            "budget_pct": {"defense": 2.4, "healthcare": 2.1, "education": 3.1, "social": 4.5},
            "industry_control": {"state_owned_pct": 15, "oligarch_controlled_pct": 30, "foreign_owned_pct": 10},
            "corruption_channels": ["Government contracts to connected firms", "Electoral bonds (opaque political funding)", "Land acquisition", "Tax raids on opponents"],
            "sanctions_role": "Neutral — buys Russian oil while maintaining Western ties",
            "debt_to_gdp": 83,
            "trade_dependencies": {"US": 0.18, "CN": 0.12, "AE": 0.07, "SA": 0.06, "EU": 0.12},
        },
        "foreign_influence": {
            "leverage_over": {"South Asia": "Regional hegemon", "Global South": "Demographic weight, tech workforce", "Russia": "Oil buyer of last resort"},
            "leverage_by": {"CN": "Border tensions, trade imbalance", "US": "Tech investment, defense partnership"},
            "alliances": ["Quad", "BRICS", "SCO", "G20", "NAM tradition"],
            "hostile": ["PK (Kashmir)", "contested: CN (border)"],
            "bases_abroad": 3,
            "bases_hosted": 0,
        },
        "stability": {
            "score": 5.5,
            "protest_level": "active_suppressed",
            "media_freedom_trend": "declining",
            "judicial_independence": "under_pressure",
            "ethnic_tensions": "elevated",
            "separatism_risk": 0.1,
            "coup_risk": 0.01,
            "key_fault_lines": ["Hindu-Muslim polarization", "Kashmir", "Caste discrimination", "Farmer distress", "Wealth inequality", "Northeast insurgencies"],
        },
        "history": {
            "government_origin": "Independence 1947, constitutional democracy since",
            "last_regime_change": "1947 (independence), 1975-77 (Emergency — only period of suspended democracy)",
            "precedent_events": ["Partition 1947", "Emergency 1975", "Hindu-Muslim riots 2002 Gujarat", "Farm protests 2020-21", "CAA/NRC protests 2019"],
            "cyclical_patterns": ["Congress dominance → coalition era → BJP dominance", "Secularism → Hindu nationalism oscillation"],
        },
        "real_vs_stated": {
            "stated_narrative": "World's largest democracy, inclusive development, ancient civilization revival",
            "actual_dynamics": "BJP has systematically weakened democratic institutions while maintaining democratic form. Media largely captured — critical journalists face raids and charges. Muslim minority increasingly marginalized. Becoming electoral autocracy.",
            "narrative_gap": 0.65,
            "key_contradictions": [
                "Democracy claim while jailing journalists and opposition leaders",
                "Development for all while Adani wealth grows 10x in BJP era",
                "Secularism in constitution while Hindutva as governing ideology",
            ],
        },
        "democracy_score": 5.5,
    },
    "GB": {
        "name": "United Kingdom",
        "government": {
            "system": "Unitary parliamentary constitutional monarchy",
            "head_of_state": "Monarch (ceremonial)",
            "legislature": "Bicameral (House of Lords + House of Commons)",
            "judiciary": "Independent Supreme Court (since 2009)",
            "real_power_center": "PM + City of London financial interests + media barons",
            "succession": "Election (5-year max terms, FPTP)",
            "constitutional_strength": "strong (unwritten but deeply embedded conventions)",
        },
        "power_brokers": {
            "military": {"influence": 0.15, "mechanism": "Professional, apolitical, but defense industry lobby significant", "key_entities": ["BAE Systems", "MI6", "MI5", "GCHQ"]},
            "oligarchs": {"influence": 0.4, "sectors": ["finance", "property", "media"], "mechanism": "London as global money hub, property investment"},
            "intelligence": {"influence": 0.35, "agencies": ["MI6 (SIS)", "MI5", "GCHQ"], "oversight": "ISC parliamentary committee — limited"},
            "media": {"concentration": "very_high", "key_owners": ["Murdoch (Sun, Times)", "Rothermere (Daily Mail)", "BBC (state-funded)"], "mechanism": "Tabloid press shapes elections"},
            "religious": {"influence": 0.05, "groups": ["Church of England (established)"], "mechanism": "Bishops in House of Lords, minimal political influence"},
            "organized_crime": {"influence": 0.15, "type": "London as money laundering capital — 'Londongrad'"},
        },
        "money_flows": {
            "gdp_usd_b": 3495,
            "budget_pct": {"defense": 2.3, "healthcare": 10.2, "education": 4.3, "social": 15.0},
            "industry_control": {"state_owned_pct": 5, "oligarch_controlled_pct": 15, "foreign_owned_pct": 25},
            "corruption_channels": ["London property laundering", "Political donations for peerages", "Revolving door", "Offshore tax structures"],
            "sanctions_role": "Imposer (aligned with US/EU)",
            "debt_to_gdp": 101,
            "trade_dependencies": {"US": 0.15, "EU": 0.42, "CN": 0.07},
        },
        "foreign_influence": {
            "leverage_over": {"Commonwealth": "Historical ties, diplomatic network", "Finance": "London as global financial center"},
            "leverage_by": {"US": "Security dependency", "Gulf states": "Investment leverage", "RU_oligarchs": "London property/finance (declining post-sanctions)"},
            "alliances": ["NATO", "Five Eyes", "AUKUS", "G7", "Commonwealth"],
            "hostile": ["RU", "contested: CN"],
            "bases_abroad": 16,
            "bases_hosted": 6,
        },
        "stability": {
            "score": 7.5,
            "protest_level": "low",
            "media_freedom_trend": "stable",
            "judicial_independence": "strong",
            "ethnic_tensions": "moderate",
            "separatism_risk": 0.15,
            "coup_risk": 0.0,
            "key_fault_lines": ["Scottish independence", "Northern Ireland protocol", "Post-Brexit economic decline", "NHS collapse", "Immigration tensions", "Cost of living"],
        },
        "history": {
            "government_origin": "Continuous parliamentary evolution since Magna Carta 1215",
            "last_regime_change": "N/A (continuous constitutional monarchy)",
            "precedent_events": ["Brexit 2016", "Scottish independence referendum 2014", "Iraq War 2003"],
            "cyclical_patterns": ["Labour-Conservative pendulum", "Imperial decline management"],
        },
        "real_vs_stated": {
            "stated_narrative": "Mother of parliaments, global Britain, special relationship with US",
            "actual_dynamics": "Real power sits with City of London and media barons. Labour won by default against collapsed Conservatives. NHS quietly privatized through underfunding. Among most extensive surveillance states in democracies.",
            "narrative_gap": 0.5,
            "key_contradictions": [
                "Anti-corruption leadership while London launders global dirty money",
                "NHS pride while systematically underfunding it",
                "Global Britain while diminished post-Brexit influence",
            ],
        },
        "democracy_score": 7.5,
    },
    "SA": {
        "name": "Saudi Arabia",
        "government": {
            "system": "Absolute monarchy",
            "head_of_state": "King (Salman), Crown Prince (MBS) holds actual power",
            "legislature": "Shura Council (advisory only, appointed)",
            "judiciary": "Sharia-based, not independent from monarchy",
            "real_power_center": "Crown Prince Mohammed bin Salman personally",
            "succession": "Royal family appointment (MBS consolidated by purging rivals)",
            "constitutional_strength": "none (Quran declared as constitution)",
        },
        "power_brokers": {
            "military": {"influence": 0.4, "mechanism": "Massive defense spending, arms imports, Yemen war", "key_entities": ["Saudi Armed Forces", "National Guard", "General Intelligence Presidency"]},
            "oligarchs": {"influence": 0.2, "sectors": ["construction", "real_estate"], "mechanism": "Serve at royal pleasure — Ritz-Carlton purge showed limits"},
            "intelligence": {"influence": 0.5, "agencies": ["GIP (Presidency of State Security)"], "oversight": "None — directly under crown"},
            "media": {"concentration": "total_state", "key_owners": ["MBC Group", "Saudi Research and Media Group", "Al Arabiya"], "mechanism": "Complete control + influence over pan-Arab media"},
            "religious": {"influence": 0.3, "groups": ["Wahhabi establishment (weakened under MBS)"], "mechanism": "Legitimization of rule, declining but still significant"},
            "organized_crime": {"influence": 0.1, "type": "State-level — Khashoggi murder, Ritz-Carlton shakedown"},
        },
        "money_flows": {
            "gdp_usd_b": 1069,
            "budget_pct": {"defense": 6.0, "healthcare": 5.0, "education": 5.5, "social": 12.0},
            "industry_control": {"state_owned_pct": 60, "oligarch_controlled_pct": 15, "foreign_owned_pct": 5},
            "corruption_channels": ["Royal family as state treasury", "Defense procurement", "Mega-project contracts (NEOM)", "PIF investment decisions"],
            "sanctions_role": "Neither — oil pricing power transcends sanctions",
            "debt_to_gdp": 26,
            "trade_dependencies": {"CN": 0.20, "IN": 0.10, "JP": 0.08, "KR": 0.07, "US": 0.06},
        },
        "foreign_influence": {
            "leverage_over": {"Global": "Oil pricing (OPEC+ leader), sovereign wealth ($700B+ PIF)", "Middle East": "Regional power, holy sites, anti-Iran axis"},
            "leverage_by": {"US": "Security guarantee, arms supply", "CN": "Oil customer leverage growing"},
            "alliances": ["GCC", "OPEC+", "Abraham Accords framework", "US security umbrella"],
            "hostile": ["IR (proxy wars, ideological rivalry)", "Houthis (Yemen)"],
            "bases_abroad": 1,
            "bases_hosted": 3,
        },
        "stability": {
            "score": 6.0,
            "protest_level": "impossible",
            "media_freedom_trend": "none",
            "judicial_independence": "none",
            "ethnic_tensions": "managed",
            "separatism_risk": 0.05,
            "coup_risk": 0.08,
            "key_fault_lines": ["Oil dependency (Vision 2030 transition)", "Youth expectations vs reality", "Royal family internal tensions", "Shia minority in Eastern Province", "Post-oil economic viability"],
        },
        "history": {
            "government_origin": "Kingdom founded 1932 by Ibn Saud, current system since",
            "last_regime_change": "2017 (MBS palace coup against MBN — power consolidation within system)",
            "precedent_events": ["1979 Grand Mosque seizure", "2017 Ritz-Carlton purge", "2018 Khashoggi murder", "2019 Aramco IPO", "2023 Iran rapprochement"],
            "cyclical_patterns": ["Oil boom-bust cycles driving reform-retrench", "External threat (Iran) → internal consolidation"],
        },
        "real_vs_stated": {
            "stated_narrative": "Vision 2030 modernization, entertainment capital, investment hub",
            "actual_dynamics": "Absolute monarchy rebranded as reform. MBS is modernizer AND authoritarian — Khashoggi murder showed both faces. Dissent impossible — activists jailed for tweets. Oil money buys international silence.",
            "narrative_gap": 0.85,
            "key_contradictions": [
                "Women's rights progress while women's rights activists remain jailed",
                "Entertainment freedom while political freedom zero",
                "Anti-extremism campaign while Wahhabi ideology exported for decades",
            ],
        },
        "democracy_score": 1.0,
    },
    "IR": {
        "name": "Iran",
        "government": {
            "system": "Theocratic republic",
            "head_of_state": "Supreme Leader (Khamenei) — true authority",
            "legislature": "Majlis (elected but candidates pre-screened by Guardian Council)",
            "judiciary": "Controlled by Supreme Leader appointees",
            "real_power_center": "Supreme Leader + IRGC (Revolutionary Guards)",
            "succession": "Assembly of Experts selects Supreme Leader (managed process)",
            "constitutional_strength": "weak (velayat-e faqih doctrine — clerical authority overrides all)",
        },
        "power_brokers": {
            "military": {"influence": 0.7, "mechanism": "IRGC controls ~30% of economy, runs proxy network, parallel military", "key_entities": ["IRGC", "IRGC-QF (Quds Force)", "Basij", "Artesh (regular military)"]},
            "oligarchs": {"influence": 0.2, "sectors": ["construction", "import_export"], "mechanism": "IRGC-connected business empires, bonyads (revolutionary foundations)"},
            "intelligence": {"influence": 0.5, "agencies": ["MOIS (VEVAK)", "IRGC Intelligence"], "oversight": "None — Supreme Leader oversight only"},
            "media": {"concentration": "total_state", "key_owners": ["IRIB (state broadcaster)", "Press TV"], "mechanism": "Complete control, internet throttling, VPN blocks"},
            "religious": {"influence": 0.6, "groups": ["Shia clerical establishment"], "mechanism": "Theological justification for system, Guardian Council veto power"},
            "organized_crime": {"influence": 0.2, "type": "Sanctions evasion networks, IRGC smuggling operations"},
        },
        "money_flows": {
            "gdp_usd_b": 401,
            "budget_pct": {"defense": 2.5, "healthcare": 4.5, "education": 4.0, "social": 15.0},
            "industry_control": {"state_owned_pct": 55, "oligarch_controlled_pct": 20, "foreign_owned_pct": 2},
            "corruption_channels": ["IRGC economic empire", "Bonyad foundations (unaudited)", "Sanctions evasion profits", "Oil revenue opacity"],
            "sanctions_role": "Heavily sanctioned (US primary, EU secondary)",
            "debt_to_gdp": 32,
            "trade_dependencies": {"CN": 0.28, "AE": 0.12, "IQ": 0.10, "TR": 0.08},
        },
        "foreign_influence": {
            "leverage_over": {"Axis of Resistance": "Hezbollah, Hamas, Houthis, Iraqi militias", "Strait of Hormuz": "20% of global oil transit"},
            "leverage_by": {"CN": "Oil buyer leverage", "RU": "Military supplier", "Sanctions": "Economic strangulation"},
            "alliances": ["SCO", "BRICS (new member)", "Axis of Resistance", "bilateral: RU, CN"],
            "hostile": ["US", "IL", "SA", "BH"],
            "bases_abroad": 0,
            "bases_hosted": 0,
        },
        "stability": {
            "score": 3.5,
            "protest_level": "cyclical_uprising",
            "media_freedom_trend": "none",
            "judicial_independence": "none",
            "ethnic_tensions": "elevated",
            "separatism_risk": 0.15,
            "coup_risk": 0.05,
            "key_fault_lines": ["Generational gap (youth vs theocracy)", "Woman Life Freedom movement", "Economic collapse under sanctions", "Ethnic peripheries (Kurdish, Baluch, Arab)", "Supreme Leader succession"],
        },
        "history": {
            "government_origin": "1979 Islamic Revolution, current theocratic system since",
            "last_regime_change": "1979 (revolution overthrew Shah)",
            "precedent_events": ["1953 CIA coup against Mossadegh", "1979 Revolution", "Iran-Iraq War 1980-88", "Green Movement 2009", "Mahsa Amini protests 2022"],
            "cyclical_patterns": ["Reformist hope → hardliner crackdown", "External pressure → internal rally-around-flag"],
        },
        "real_vs_stated": {
            "stated_narrative": "Islamic democracy, resistance against Western imperialism, defender of oppressed Muslims",
            "actual_dynamics": "Theocratic dictatorship with managed electoral facade. IRGC runs parallel economy and military. Supreme Leader succession is the central hidden anxiety. Population broadly hostile to system but fragmented.",
            "narrative_gap": 0.85,
            "key_contradictions": [
                "Islamic democracy while Guardian Council vetoes candidates",
                "Anti-imperialism while IRGC operates across 4 countries",
                "Defending Muslims while persecuting Bahais and Sunnis at home",
            ],
        },
        "democracy_score": 2.0,
    },
    "IL": {
        "name": "Israel",
        "government": {
            "system": "Unitary parliamentary republic",
            "head_of_state": "President (ceremonial), PM holds power",
            "legislature": "Unicameral Knesset (120 seats, proportional representation)",
            "judiciary": "Independent Supreme Court (under sustained political assault)",
            "real_power_center": "PM coalition + settler movement + military-security establishment",
            "succession": "Election (no fixed schedule, coalitions collapse frequently)",
            "constitutional_strength": "moderate (no formal constitution, Basic Laws)",
        },
        "power_brokers": {
            "military": {"influence": 0.5, "mechanism": "Universal conscription, IDF as social institution, defense exports", "key_entities": ["IDF", "Mossad", "Shin Bet", "Aman"]},
            "oligarchs": {"influence": 0.3, "sectors": ["tech", "telecom", "banking", "real_estate"], "mechanism": "Tech sector influence, media ownership"},
            "intelligence": {"influence": 0.5, "agencies": ["Mossad", "Shin Bet (Shabak)", "Aman (Military Intel)"], "oversight": "Knesset subcommittee — limited"},
            "media": {"concentration": "moderate", "key_owners": ["Various private owners", "Kan (public)"], "mechanism": "Diverse but security consensus limits coverage"},
            "religious": {"influence": 0.4, "groups": ["Ultra-Orthodox parties (Shas, UTJ)", "Religious Zionism"], "mechanism": "Coalition kingmakers, control personal status law"},
            "organized_crime": {"influence": 0.1, "type": "Financial, some political connections"},
        },
        "money_flows": {
            "gdp_usd_b": 525,
            "budget_pct": {"defense": 5.3, "healthcare": 7.5, "education": 6.0, "social": 10.0},
            "industry_control": {"state_owned_pct": 8, "oligarch_controlled_pct": 25, "foreign_owned_pct": 15},
            "corruption_channels": ["Coalition horse-trading", "Settlement construction contracts", "Defense procurement"],
            "sanctions_role": "Neither — some targeted sanctions on settlers",
            "debt_to_gdp": 62,
            "trade_dependencies": {"US": 0.26, "EU": 0.25, "CN": 0.07},
        },
        "foreign_influence": {
            "leverage_over": {"US": "AIPAC lobby, tech/defense integration", "PA": "Economic and security control"},
            "leverage_by": {"US": "Military aid ($3.8B/yr), diplomatic cover", "Normalization partners": "Abraham Accords leverage"},
            "alliances": ["US bilateral (no formal treaty)", "Abraham Accords (AE, BH, MA)", "NATO partner"],
            "hostile": ["IR", "SY", "LB (Hezbollah)", "Hamas", "Houthis"],
            "bases_abroad": 0,
            "bases_hosted": 2,
        },
        "stability": {
            "score": 5.0,
            "protest_level": "high",
            "media_freedom_trend": "declining",
            "judicial_independence": "under_assault",
            "ethnic_tensions": "severe",
            "separatism_risk": 0.0,
            "coup_risk": 0.01,
            "key_fault_lines": ["Gaza war and international isolation", "Judicial overhaul crisis", "Secular-religious divide", "Palestinian question", "Settler extremism", "Ultra-Orthodox economic burden"],
        },
        "history": {
            "government_origin": "Founded 1948, parliamentary system since",
            "last_regime_change": "1948 (independence/founding)",
            "precedent_events": ["1967 Six-Day War (occupation begins)", "1993 Oslo Accords", "2005 Gaza withdrawal", "2023 judicial overhaul protests", "Oct 7 2023 attack"],
            "cyclical_patterns": ["Security crisis → right-wing consolidation", "Peace process → collapse → more settlements"],
        },
        "real_vs_stated": {
            "stated_narrative": "Only democracy in Middle East, right to self-defense, security necessity",
            "actual_dynamics": "Democracy for Jewish citizens, military occupation for Palestinians. Netanyahu faces corruption charges while governing with ultranationalist coalition. Settler movement operates above the law. Judiciary under assault.",
            "narrative_gap": 0.7,
            "key_contradictions": [
                "Democracy while governing millions without voting rights",
                "Rule of law while judicial independence under attack",
                "Self-defense while expanding settlements in occupied territory",
            ],
        },
        "democracy_score": 6.0,
    },
    "UA": {
        "name": "Ukraine",
        "government": {
            "system": "Unitary semi-presidential republic (wartime centralization)",
            "head_of_state": "President (Zelenskyy, extended term due to martial law)",
            "legislature": "Verkhovna Rada (unicameral, elections suspended during war)",
            "judiciary": "Reforming (EU accession requirements driving cleanup)",
            "real_power_center": "President's Office (wartime executive dominance) + military command",
            "succession": "Election (suspended under martial law)",
            "constitutional_strength": "moderate (tested by war)",
        },
        "power_brokers": {
            "military": {"influence": 0.6, "mechanism": "Wartime necessity, Zaluzhny popularity, military as most trusted institution", "key_entities": ["Armed Forces of Ukraine", "GUR (Military Intelligence)", "SBU"]},
            "oligarchs": {"influence": 0.15, "sectors": ["media", "energy", "agriculture"], "mechanism": "Pre-war oligarch capture largely broken by war (Akhmetov, Kolomoisky neutralized)"},
            "intelligence": {"influence": 0.4, "agencies": ["SBU", "GUR (Budanov)"], "oversight": "Wartime — limited oversight"},
            "media": {"concentration": "moderate_improving", "key_owners": ["United News telethon (wartime)", "Various private"], "mechanism": "Wartime unified broadcast, pre-war oligarch media being dismantled"},
            "religious": {"influence": 0.15, "groups": ["Orthodox Church of Ukraine (split from Moscow)"], "mechanism": "National identity formation, break from Russian church"},
            "organized_crime": {"influence": 0.1, "type": "Wartime corruption in procurement, aid diversion risks"},
        },
        "money_flows": {
            "gdp_usd_b": 179,
            "budget_pct": {"defense": 37.0, "healthcare": 3.0, "education": 4.0, "social": 8.0},
            "industry_control": {"state_owned_pct": 20, "oligarch_controlled_pct": 15, "foreign_owned_pct": 10},
            "corruption_channels": ["Defense procurement (wartime)", "Reconstruction contracts (coming)", "Legacy customs/border corruption"],
            "sanctions_role": "Beneficiary of Russian sanctions, some oligarch sanctions",
            "debt_to_gdp": 84,
            "trade_dependencies": {"EU": 0.45, "CN": 0.08, "PL": 0.07, "TR": 0.05},
        },
        "foreign_influence": {
            "leverage_over": {"EU": "Moral authority, grain exports, front line against Russia", "Global food": "Major grain exporter"},
            "leverage_by": {"US/EU": "Military aid dependency", "RU": "Active invasion", "PL/HU": "Border/minority tensions"},
            "alliances": ["EU candidate", "NATO aspirant", "bilateral: US, GB, PL, DE, FR"],
            "hostile": ["RU (active war)"],
            "bases_abroad": 0,
            "bases_hosted": 0,
        },
        "stability": {
            "score": 4.0,
            "protest_level": "suspended_wartime",
            "media_freedom_trend": "mixed_wartime",
            "judicial_independence": "reforming",
            "ethnic_tensions": "low_wartime_unity",
            "separatism_risk": 0.05,
            "coup_risk": 0.02,
            "key_fault_lines": ["War fatigue", "Mobilization resistance", "Post-war power transition", "Reconstruction corruption risk", "Territorial compromise pressure"],
        },
        "history": {
            "government_origin": "Independence 1991, current constitutional system since",
            "last_regime_change": "2014 Maidan revolution (democratic)",
            "precedent_events": ["Orange Revolution 2004", "Maidan 2014", "Crimea annexation 2014", "Donbas war 2014-22", "Full-scale invasion Feb 2022"],
            "cyclical_patterns": ["Revolution → reform → oligarch capture → new revolution (broken by war)"],
        },
        "real_vs_stated": {
            "stated_narrative": "Defending democracy against Russian imperialism, European integration, freedom",
            "actual_dynamics": "Wartime democracy — Zelenskyy centralized power from necessity but democratic culture survives. Pre-war oligarch capture destroyed by war. EU accession reforms real. Reconstruction will be biggest corruption test.",
            "narrative_gap": 0.25,
            "key_contradictions": [
                "Democratic values while elections suspended",
                "Anti-corruption reforms while wartime procurement opaque",
                "Western integration while some Western fatigue growing",
            ],
        },
        "democracy_score": 5.5,
    },
    "TR": {
        "name": "Turkey",
        "government": {
            "system": "Unitary presidential constitutional republic (since 2017 referendum)",
            "head_of_state": "President (Erdogan, expanded executive powers)",
            "legislature": "Grand National Assembly (unicameral, weakened post-2017)",
            "judiciary": "Captured after 2016 coup attempt purges",
            "real_power_center": "Erdogan personally + AKP apparatus + religious networks",
            "succession": "Election (increasingly unfair playing field)",
            "constitutional_strength": "weak (amended to suit Erdogan)",
        },
        "power_brokers": {
            "military": {"influence": 0.3, "mechanism": "Purged post-2016, now loyal to Erdogan. Defense industry growing (Bayraktar drones)", "key_entities": ["Turkish Armed Forces", "MIT (Intelligence)"]},
            "oligarchs": {"influence": 0.3, "sectors": ["construction", "media", "energy"], "mechanism": "Government contracts, media ownership as political tool"},
            "intelligence": {"influence": 0.4, "agencies": ["MIT (National Intelligence)"], "oversight": "Reports directly to president"},
            "media": {"concentration": "captured", "key_owners": ["AKP-connected businessmen own 90%+ of media"], "mechanism": "Opposition media systematically bought out or shut down"},
            "religious": {"influence": 0.4, "groups": ["Diyanet (state religious authority)", "AKP Islamist base", "Gulen movement (destroyed)"], "mechanism": "Islamic identity as political mobilization tool"},
            "organized_crime": {"influence": 0.15, "type": "Drug trafficking, ultranationalist mafia ties to state"},
        },
        "money_flows": {
            "gdp_usd_b": 1108,
            "budget_pct": {"defense": 1.6, "healthcare": 4.5, "education": 3.0, "social": 8.0},
            "industry_control": {"state_owned_pct": 15, "oligarch_controlled_pct": 25, "foreign_owned_pct": 10},
            "corruption_channels": ["Construction contracts to AKP-connected firms", "Defense procurement", "Central bank policy manipulation", "Municipality budget capture"],
            "sanctions_role": "Neutral broker — sanctions evasion hub for Russia",
            "debt_to_gdp": 29,
            "trade_dependencies": {"EU": 0.35, "RU": 0.10, "CN": 0.10, "US": 0.05},
        },
        "foreign_influence": {
            "leverage_over": {"NATO": "Second largest military, Bosphorus control", "Middle East": "Ottoman legacy, military interventions", "Refugees": "4M+ Syrian refugees as leverage over EU"},
            "leverage_by": {"US": "F-35 exclusion, sanctions threat", "RU": "Energy dependency (gas, nuclear plant)", "EU": "Customs union leverage"},
            "alliances": ["NATO (complicated)", "G20"],
            "hostile": ["SY (Kurdish issue)", "GR (Aegean disputes)", "CY (division)", "contested: EG, AE, SA"],
            "bases_abroad": 5,
            "bases_hosted": 2,
        },
        "stability": {
            "score": 4.5,
            "protest_level": "suppressed",
            "media_freedom_trend": "none",
            "judicial_independence": "captured",
            "ethnic_tensions": "elevated",
            "separatism_risk": 0.15,
            "coup_risk": 0.03,
            "key_fault_lines": ["Kurdish question", "Economic mismanagement (inflation 65%+)", "Secular-Islamist divide", "Erdogan succession", "Syrian refugee tensions", "Earthquake recovery failure"],
        },
        "history": {
            "government_origin": "Republic 1923 (Ataturk), Erdogan transformed system 2017",
            "last_regime_change": "2017 (constitutional referendum converting to presidential system)",
            "precedent_events": ["Military coups (1960, 1971, 1980, 1997 soft coup)", "2013 Gezi protests", "2016 failed coup", "2023 earthquake (50K+ dead)"],
            "cyclical_patterns": ["Military intervention cycle (broken by Erdogan)", "Secular-Islamist pendulum"],
        },
        "real_vs_stated": {
            "stated_narrative": "Bridge between East and West, democratic Muslim nation, regional power",
            "actual_dynamics": "Erdogan transformed parliamentary democracy into presidential autocracy. Media captured, judiciary subservient. Patronage networks and religious identity keep base loyal despite economic mismanagement.",
            "narrative_gap": 0.7,
            "key_contradictions": [
                "NATO ally while buying Russian S-400",
                "Fighting ISIS while enabling jihadist transit",
                "Democracy while jailing journalists and opposition",
            ],
        },
        "democracy_score": 4.0,
    },
    "KP": {
        "name": "North Korea",
        "government": {
            "system": "Totalitarian hereditary dictatorship (Juche ideology)",
            "head_of_state": "Supreme Leader Kim Jong-un",
            "legislature": "Supreme People's Assembly (100% pre-selected, meets days/year)",
            "judiciary": "Political instrument of regime",
            "real_power_center": "Kim Jong-un personally + Organization and Guidance Department",
            "succession": "Hereditary (Kim dynasty: Il-sung → Jong-il → Jong-un)",
            "constitutional_strength": "none (Kim family above all law)",
        },
        "power_brokers": {
            "military": {"influence": 0.6, "mechanism": "Songun (military-first) policy, nuclear arsenal as regime survival guarantee", "key_entities": ["KPA (Korean People's Army)", "Strategic Rocket Force", "RGB (intelligence)"]},
            "oligarchs": {"influence": 0.0, "sectors": [], "mechanism": "No private economy — everything state-controlled"},
            "intelligence": {"influence": 0.5, "agencies": ["RGB (Reconnaissance General Bureau)", "MSS (State Security)"], "oversight": "Kim Jong-un only"},
            "media": {"concentration": "total_state", "key_owners": ["KCNA", "Rodong Sinmun"], "mechanism": "Complete information blackout — no internet for citizens"},
            "religious": {"influence": 0.0, "groups": ["Kim family cult is the religion"], "mechanism": "Juche/Kimilsungism as state religion"},
            "organized_crime": {"influence": 0.3, "type": "State-run: crypto theft ($3B+), counterfeiting, drug manufacturing, weapons sales"},
        },
        "money_flows": {
            "gdp_usd_b": 18,
            "budget_pct": {"defense": 25.0, "healthcare": 1.0, "education": 2.0, "social": 3.0},
            "industry_control": {"state_owned_pct": 100, "oligarch_controlled_pct": 0, "foreign_owned_pct": 0},
            "corruption_channels": ["Kim family personal treasury", "Military corruption", "Sanctions evasion networks", "State-run criminal enterprises"],
            "sanctions_role": "Maximally sanctioned (UNSC + US + EU)",
            "debt_to_gdp": 0,
            "trade_dependencies": {"CN": 0.90, "RU": 0.05},
        },
        "foreign_influence": {
            "leverage_over": {"Global": "Nuclear threat and ICBM capability", "KR/JP": "Artillery/missile threat"},
            "leverage_by": {"CN": "95% of trade, food/fuel dependency", "RU": "Arms-for-troops deal in Ukraine war"},
            "alliances": ["bilateral: CN (treaty), RU (deepening)"],
            "hostile": ["US", "KR", "JP"],
            "bases_abroad": 0,
            "bases_hosted": 0,
        },
        "stability": {
            "score": 4.0,
            "protest_level": "impossible",
            "media_freedom_trend": "none",
            "judicial_independence": "none",
            "ethnic_tensions": "none_reported",
            "separatism_risk": 0.0,
            "coup_risk": 0.03,
            "key_fault_lines": ["Food insecurity (chronic)", "Information leakage via smuggled media", "Elite loyalty (purges suggest anxiety)", "Economic desperation", "Kim succession if health fails"],
        },
        "history": {
            "government_origin": "Soviet-installed 1948, Kim dynasty since founding",
            "last_regime_change": "1948 (founding) — same family since",
            "precedent_events": ["Korean War 1950-53", "Famine 1994-98 (1M+ dead)", "2017 nuclear/ICBM tests", "2018-19 summits (failed)", "2024 Russia alliance deepening"],
            "cyclical_patterns": ["Provocation → negotiation → aid → rearmament", "Famine → partial reform → retrenchment"],
        },
        "real_vs_stated": {
            "stated_narrative": "Self-reliant socialist paradise, defending against US imperialism",
            "actual_dynamics": "Most isolated regime on Earth. Kim dynasty treats country as personal property. Nuclear weapons are sole guarantee of regime survival. Population systematically starved and imprisoned. Information blackout near-total.",
            "narrative_gap": 1.0,
            "key_contradictions": [
                "Self-reliance while 90% dependent on Chinese trade",
                "Workers' paradise while running forced labor camps",
                "Peace while maintaining 1.2M active military",
            ],
        },
        "democracy_score": 0.5,
    },
}


# Additional countries with lighter profiles (expanded from existing HTML data)
SEED_PROFILES.update({
    "JP": {"name": "Japan", "democracy_score": 7.5,
        "government": {"system": "Unitary parliamentary constitutional monarchy", "real_power_center": "PM + bureaucracy + keiretsu networks", "succession": "Election"},
        "power_brokers": {"military": {"influence": 0.15}, "oligarchs": {"influence": 0.4, "sectors": ["auto", "electronics", "finance"]}, "media": {"concentration": "high", "key_owners": ["Kisha clubs control access"]}},
        "money_flows": {"gdp_usd_b": 4213, "debt_to_gdp": 264, "trade_dependencies": {"CN": 0.22, "US": 0.18}},
        "stability": {"score": 8.0, "key_fault_lines": ["Demographic collapse", "China/NK security threat", "Economic stagnation"]},
        "real_vs_stated": {"stated_narrative": "Peaceful economic power, alliance with US", "actual_dynamics": "One-party democracy — LDP ruled almost continuously since 1955. Bureaucracy runs the country regardless of PM. Media self-censors on imperial family and organized crime's political ties.", "narrative_gap": 0.35},
    },
    "DE": {"name": "Germany", "democracy_score": 8.0,
        "government": {"system": "Federal parliamentary republic", "real_power_center": "Chancellor + coalition partners + industrial lobby", "succession": "Election"},
        "power_brokers": {"military": {"influence": 0.1}, "oligarchs": {"influence": 0.4, "sectors": ["auto", "chemicals", "machinery"]}, "media": {"concentration": "moderate"}},
        "money_flows": {"gdp_usd_b": 4460, "debt_to_gdp": 64, "trade_dependencies": {"CN": 0.08, "US": 0.09, "FR": 0.07}},
        "stability": {"score": 7.5, "key_fault_lines": ["AfD rise", "Industrial recession", "Energy transition", "Immigration tensions"]},
        "real_vs_stated": {"stated_narrative": "Engine of Europe, multilateral rules-based order", "actual_dynamics": "Coalition gridlock is standard. AfD rise reflects genuine frustration with immigration and deindustrialization that mainstream parties refused to address.", "narrative_gap": 0.3},
    },
    "FR": {"name": "France", "democracy_score": 7.0,
        "government": {"system": "Unitary semi-presidential republic", "real_power_center": "President + ENA technocratic elite", "succession": "Election (5-year)"},
        "power_brokers": {"military": {"influence": 0.2, "mechanism": "Nuclear deterrent, Africa operations"}, "oligarchs": {"influence": 0.5, "sectors": ["luxury", "defense", "energy"]}, "media": {"concentration": "high", "key_owners": ["Bollore (CNews)", "Dassault", "Bouygues"]}},
        "money_flows": {"gdp_usd_b": 3031, "debt_to_gdp": 112, "trade_dependencies": {"DE": 0.13, "US": 0.08, "CN": 0.05}},
        "stability": {"score": 6.5, "key_fault_lines": ["Yellow vest/pension anger", "Immigration/integration", "Le Pen popularity", "Ungovernable parliament"]},
        "real_vs_stated": {"stated_narrative": "Republic of liberty, equality, fraternity", "actual_dynamics": "Macron governs without mandate — parliament ungovernable. Deep disconnect between Paris elite and the rest of France. Le Pen's RN is the real opposition.", "narrative_gap": 0.5},
    },
    "BR": {"name": "Brazil", "democracy_score": 6.0,
        "government": {"system": "Federal presidential constitutional republic", "real_power_center": "President + Congress horse-trading + agribusiness lobby", "succession": "Election (4-year)"},
        "power_brokers": {"military": {"influence": 0.25, "mechanism": "Bolsonaro brought military back into politics"}, "oligarchs": {"influence": 0.5, "sectors": ["agribusiness", "mining", "banking"]}, "religious": {"influence": 0.3, "groups": ["Evangelical churches"]}},
        "money_flows": {"gdp_usd_b": 2174, "debt_to_gdp": 74, "trade_dependencies": {"CN": 0.31, "US": 0.11, "AR": 0.04}},
        "stability": {"score": 5.5, "key_fault_lines": ["Deep polarization", "Amazon deforestation vs agribusiness", "Military nostalgia", "Inequality"]},
        "real_vs_stated": {"stated_narrative": "Emerging power, environmental leader, social inclusion", "actual_dynamics": "Deeply polarized — Bolsonaro base vs Lula coalition. Congress is a horse-trading bazaar. Agribusiness lobby blocks Amazon enforcement. Military retains outsized influence.", "narrative_gap": 0.55},
    },
    "MX": {"name": "Mexico", "democracy_score": 5.0,
        "government": {"system": "Federal presidential constitutional republic", "real_power_center": "President + cartels (parallel governance)", "succession": "Election (6-year, no re-election)"},
        "power_brokers": {"military": {"influence": 0.3, "mechanism": "AMLO militarized civilian functions"}, "organized_crime": {"influence": 0.6, "type": "Cartels control territory, elections, local government"}},
        "money_flows": {"gdp_usd_b": 1789, "debt_to_gdp": 53, "trade_dependencies": {"US": 0.80}},
        "stability": {"score": 4.0, "key_fault_lines": ["Cartel violence (30K+ murders/yr)", "Journalist murders", "Judicial capture", "US dependency"]},
        "real_vs_stated": {"stated_narrative": "Sovereign democracy, anti-corruption, fourth transformation", "actual_dynamics": "Cartels are the real governing power in large parts of the country. Most dangerous country for journalists. Judiciary restructured to serve ruling party. Corruption endemic.", "narrative_gap": 0.75},
    },
    "PK": {"name": "Pakistan", "democracy_score": 3.0,
        "government": {"system": "Federal parliamentary republic (de jure), military-guided (de facto)", "real_power_center": "Army Chief + GHQ (military headquarters)", "succession": "Election (managed by military)"},
        "power_brokers": {"military": {"influence": 0.8, "mechanism": "ISI controls politics, business, media. Army is permanent government", "key_entities": ["Pakistan Army", "ISI", "GHQ"]}, "religious": {"influence": 0.3, "groups": ["Various Islamist parties", "Madrasa networks"]}},
        "money_flows": {"gdp_usd_b": 374, "debt_to_gdp": 72, "trade_dependencies": {"CN": 0.20, "AE": 0.08, "US": 0.06}},
        "stability": {"score": 3.0, "key_fault_lines": ["Military vs civilian tension", "TTP terrorism", "Balochistan separatism", "Economic collapse", "IMF dependency"]},
        "real_vs_stated": {"stated_narrative": "Islamic democratic republic, nuclear power, anti-terror partner", "actual_dynamics": "Military is the permanent government — civilians serve at generals' pleasure. Imran Khan imprisoned. ISI operates as state within state. Democracy is theater directed by GHQ.", "narrative_gap": 0.8},
    },
    "EG": {"name": "Egypt", "democracy_score": 1.5,
        "government": {"system": "Unitary semi-presidential republic (de jure), military dictatorship (de facto)", "real_power_center": "President Sisi + military establishment", "succession": "Managed election (no real opposition)"},
        "power_brokers": {"military": {"influence": 0.8, "mechanism": "Military owns 25-40% of economy, controls all institutions", "key_entities": ["Egyptian Armed Forces", "GIS (intelligence)"]}, "religious": {"influence": 0.2, "groups": ["Al-Azhar (co-opted)", "Muslim Brotherhood (crushed)"]}},
        "money_flows": {"gdp_usd_b": 398, "debt_to_gdp": 92, "trade_dependencies": {"AE": 0.10, "SA": 0.08, "CN": 0.08}},
        "stability": {"score": 3.5, "key_fault_lines": ["Economic crisis (IMF bailouts)", "60K+ political prisoners", "Suez Canal revenue dependency", "Population growth (2M/yr)", "Sinai insurgency"]},
        "real_vs_stated": {"stated_narrative": "Stable Arab republic, anti-terror partner, economic reform", "actual_dynamics": "Military dictatorship with civilian facade. Sisi eliminated all opposition — 60,000+ political prisoners. Military-owned enterprises crowd out private sector.", "narrative_gap": 0.85},
    },
    "NG": {"name": "Nigeria", "democracy_score": 4.0,
        "government": {"system": "Federal presidential constitutional republic", "real_power_center": "President + state governors (feudal power) + military", "succession": "Election (rotation between North/South)"},
        "power_brokers": {"military": {"influence": 0.3}, "oligarchs": {"influence": 0.5, "sectors": ["oil", "banking", "telecom"]}, "religious": {"influence": 0.3, "groups": ["Northern Muslim establishment", "Southern Christian churches"]}},
        "money_flows": {"gdp_usd_b": 477, "debt_to_gdp": 38, "trade_dependencies": {"EU": 0.25, "IN": 0.12, "US": 0.06}},
        "stability": {"score": 3.5, "key_fault_lines": ["Boko Haram/ISWAP", "Banditry", "Biafra separatism (IPOB)", "Oil theft", "North-South divide", "Youth unemployment"]},
        "real_vs_stated": {"stated_narrative": "Giant of Africa, largest democracy on continent", "actual_dynamics": "Democracy captured by small elite rotating power. Large portions ungovernable. Oil revenue looted for decades. Election fraud standard practice.", "narrative_gap": 0.7},
    },
    "TH": {"name": "Thailand", "democracy_score": 3.5,
        "government": {"system": "Unitary parliamentary constitutional monarchy (de jure), military-guided (de facto)", "real_power_center": "Military + monarchy (untouchable)", "succession": "Election (after coups, military approves)"},
        "power_brokers": {"military": {"influence": 0.7, "mechanism": "Coups are the succession mechanism — 13 successful since 1932"}, "oligarchs": {"influence": 0.4, "sectors": ["conglomerates", "real_estate", "tourism"]}},
        "money_flows": {"gdp_usd_b": 515, "debt_to_gdp": 62, "trade_dependencies": {"CN": 0.14, "US": 0.12, "JP": 0.10}},
        "stability": {"score": 4.5, "key_fault_lines": ["Military vs pro-democracy movement", "Monarchy criticism = prison", "Southern insurgency", "Political polarization"]},
        "real_vs_stated": {"stated_narrative": "Constitutional monarchy, Land of Smiles, democratic governance", "actual_dynamics": "Military is the real power — coups are the succession mechanism. Lese-majeste law makes discussing monarchy impossible. Democracy is performative when generals approve.", "narrative_gap": 0.75},
    },
})


class CountryModelStore:
    """Persistent storage for country intelligence profiles."""

    def __init__(self):
        self.profiles: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if PROFILES_PATH.exists():
            try:
                self.profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.profiles = {}
        if not self.profiles:
            self.profiles = SEED_PROFILES.copy()
            self._save()

    def _save(self):
        PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROFILES_PATH.write_text(json.dumps(self.profiles, indent=2, default=str) + "\n", encoding="utf-8")

    def get(self, iso: str) -> Optional[dict]:
        return self.profiles.get(iso.upper())

    def update(self, iso: str, section: str, data: dict):
        iso = iso.upper()
        if iso not in self.profiles:
            self.profiles[iso] = {"name": iso}
        self.profiles[iso][section] = data
        self.profiles[iso]["last_updated"] = datetime.now(timezone.utc).isoformat()

    def enrich_from_governance(self, governance_data: List[dict]):
        """Ingest World Bank governance indicators."""
        for item in governance_data:
            iso = item.get("country_code", "").upper()
            if iso and iso in self.profiles:
                if "governance_scores" not in self.profiles[iso]:
                    self.profiles[iso]["governance_scores"] = {}
                self.profiles[iso]["governance_scores"][item["indicator"]] = {
                    "value": item.get("value"),
                    "year": item.get("year"),
                }
        self._save()

    def enrich_from_scan(self, all_data: dict):
        """Update country profiles with signal counts from latest ATLAS scan."""
        country_signals: Dict[str, dict] = {}

        for source, items in all_data.items():
            if not isinstance(items, list):
                continue
            for item in items:
                country = item.get("country", "")
                if not country or len(country) != 2:
                    continue
                iso = country.upper()
                if iso not in country_signals:
                    country_signals[iso] = {"total_mentions": 0, "sources": set(), "categories": {}}
                country_signals[iso]["total_mentions"] += 1
                country_signals[iso]["sources"].add(source)
                cat = item.get("category", "other")
                country_signals[iso]["categories"][cat] = country_signals[iso]["categories"].get(cat, 0) + 1

        for iso, signals in country_signals.items():
            if iso in self.profiles:
                self.profiles[iso]["latest_signals"] = {
                    "total_mentions": signals["total_mentions"],
                    "sources": list(signals["sources"]),
                    "categories": signals["categories"],
                    "scan_time": datetime.now(timezone.utc).isoformat(),
                }
        self._save()

    def generate_assessments(self) -> List[dict]:
        """Generate ATLAS country assessments for the report."""
        assessments = []
        for iso, profile in self.profiles.items():
            if not isinstance(profile, dict):
                continue
            score = profile.get("democracy_score", 5.0)
            stability = profile.get("stability", {})
            stability_score = stability.get("score", 5.0) if isinstance(stability, dict) else 5.0

            if score <= 3.0:
                trajectory = "authoritarian_stable" if stability_score > 4.0 else "authoritarian_fragile"
            elif score <= 5.0:
                trajectory = "hybrid_contested"
            elif score <= 7.0:
                trajectory = "flawed_democracy"
            else:
                trajectory = "full_democracy"

            signals = profile.get("latest_signals", {})
            mention_count = signals.get("total_mentions", 0) if isinstance(signals, dict) else 0

            faults = stability.get("key_fault_lines", []) if isinstance(stability, dict) else []
            real = profile.get("real_vs_stated", {})
            gap = real.get("narrative_gap", 0.5) if isinstance(real, dict) else 0.5

            assessments.append({
                "country": iso,
                "name": profile.get("name", iso),
                "democracy_score": score,
                "stability_score": stability_score,
                "trajectory": trajectory,
                "narrative_gap": gap,
                "recent_mentions": mention_count,
                "key_risks": faults[:3] if faults else [],
                "real_politics": real.get("actual_dynamics", "") if isinstance(real, dict) else "",
            })

        assessments.sort(key=lambda x: x["democracy_score"])
        return assessments

    def for_report(self) -> dict:
        """Generate country data for atlas_report.json."""
        return {
            "profiles": {iso: p for iso, p in self.profiles.items() if isinstance(p, dict)},
            "assessments": self.generate_assessments(),
            "count": len(self.profiles),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }


def build_country_intelligence(all_data: dict) -> dict:
    """Main entry point — called from atlas.py during scan."""
    store = CountryModelStore()
    store.enrich_from_scan(all_data)
    return store.for_report()


if __name__ == "__main__":
    import sys
    store = CountryModelStore()
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(f"Country profiles: {len(store.profiles)}")
        for iso in sorted(store.profiles.keys()):
            p = store.profiles[iso]
            name = p.get("name", iso) if isinstance(p, dict) else iso
            score = p.get("democracy_score", "?") if isinstance(p, dict) else "?"
            print(f"  {iso}: {name} (democracy: {score})")
    elif len(sys.argv) > 1 and sys.argv[1] == "--export":
        report = store.for_report()
        print(json.dumps(report, indent=2, default=str))
    else:
        print("Usage: atlas_country_model.py --status | --export")
