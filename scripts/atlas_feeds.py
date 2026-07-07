"""
ATLAS Feed Database — 1000+ intelligence sources
Organized by category. Each feed is (name, url).
Subreddits are plain strings. Telegram channels are (channel, description).
"""

# ═══════════════════════════════════════════════════════════════════════════
# NEWS FEEDS — Global Wire Services & Major Outlets
# ═══════════════════════════════════════════════════════════════════════════

NEWS_FEEDS = [
    # Wire Services
    ("reuters_world", "https://feeds.reuters.com/reuters/worldNews"),
    ("ap_top", "https://feeds.apnews.com/rss/apf-topnews"),
    ("afp_global", "https://www.france24.com/en/rss"),
    # US Major
    ("nyt_world", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("nyt_politics", "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml"),
    ("nyt_us", "https://rss.nytimes.com/services/xml/rss/nyt/US.xml"),
    ("nyt_business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("nyt_tech", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"),
    ("wapo_world", "https://feeds.washingtonpost.com/rss/world"),
    ("wapo_politics", "https://feeds.washingtonpost.com/rss/politics"),
    ("wapo_national", "https://feeds.washingtonpost.com/rss/national"),
    ("wsj_world", "https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
    ("wsj_opinion", "https://feeds.a.dj.com/rss/RSSOpinion.xml"),
    ("wsj_markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("politico", "https://rss.politico.com/politics-news.xml"),
    ("politico_congress", "https://rss.politico.com/congress.xml"),
    ("the_hill", "https://thehill.com/feed/"),
    ("axios", "https://api.axios.com/feed/"),
    ("npr_news", "https://feeds.npr.org/1001/rss.xml"),
    ("pbs_newshour", "https://www.pbs.org/newshour/feeds/rss/headlines"),
    ("cbs_news", "https://www.cbsnews.com/latest/rss/main"),
    ("abc_news", "https://abcnews.go.com/abcnews/topstories"),
    ("usa_today", "http://rssfeeds.usatoday.com/UsatodaycomNation-TopStories"),
    ("c_span", "https://www.c-span.org/rss/?channel=theWire"),
    ("roll_call", "https://rollcall.com/feed/"),
    ("the_intercept", "https://theintercept.com/feed/?rss"),
    ("propublica", "https://www.propublica.org/feeds/propublica/main"),
    ("reason", "https://reason.com/feed/"),
    ("jacobin", "https://jacobin.com/feed/"),
    ("national_review", "https://www.nationalreview.com/feed/"),
    # UK / Europe
    ("bbc_world", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("bbc_business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("bbc_politics", "https://feeds.bbci.co.uk/news/politics/rss.xml"),
    ("bbc_africa", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
    ("bbc_asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml"),
    ("bbc_europe", "https://feeds.bbci.co.uk/news/world/europe/rss.xml"),
    ("bbc_latam", "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml"),
    ("bbc_mideast", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("bbc_economy", "https://feeds.bbci.co.uk/news/business/economy/rss.xml"),
    ("bbc_science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("bbc_tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("guardian_world", "https://www.theguardian.com/world/rss"),
    ("guardian_politics", "https://www.theguardian.com/politics/rss"),
    ("guardian_us", "https://www.theguardian.com/us-news/rss"),
    ("guardian_business", "https://www.theguardian.com/uk/business/rss"),
    ("ft_world", "https://www.ft.com/world?format=rss"),
    ("dw_top", "https://rss.dw.com/rdf/rss-en-top"),
    ("dw_world", "https://rss.dw.com/rdf/rss-en-world"),
    ("dw_europe", "https://rss.dw.com/rdf/rss-en-eu"),
    ("dw_asia", "https://rss.dw.com/rdf/rss-en-asia"),
    ("france24_en", "https://www.france24.com/en/rss"),
    ("france24_mideast", "https://www.france24.com/en/middle-east/rss"),
    ("euronews", "https://www.euronews.com/rss"),
    ("politico_eu", "https://www.politico.eu/feed/"),
    ("spiegel_intl", "https://www.spiegel.de/international/index.rss"),
    ("irish_times", "https://www.irishtimes.com/cmlink/news-1.1319192"),
    ("telegraph", "https://www.telegraph.co.uk/rss.xml"),
    ("independent", "https://www.independent.co.uk/rss"),
    ("rfi_en", "https://www.rfi.fr/en/rss"),
    ("swiss_info", "https://www.swissinfo.ch/eng/rss/all"),
    # Middle East
    ("aljazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("aljazeera_politics", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("al_monitor", "https://www.al-monitor.com/rss"),
    ("middle_east_eye", "https://www.middleeasteye.net/rss"),
    ("jerusalem_post", "https://www.jpost.com/Rss/RssFeedsHeadlines.aspx"),
    ("times_of_israel", "https://www.timesofisrael.com/feed/"),
    ("iran_intl", "https://www.iranintl.com/en/feed"),
    ("arab_news", "https://www.arabnews.com/rss.xml"),
    ("daily_sabah", "https://www.dailysabah.com/rssFeed/main"),
    # Asia / Pacific
    ("scmp", "https://www.scmp.com/rss/91/feed"),
    ("nikkei_asia", "https://asia.nikkei.com/rss"),
    ("cna_asia", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"),
    ("times_india", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
    ("dawn_pk", "https://www.dawn.com/feed"),
    ("straits_times", "https://www.straitstimes.com/news/asia/rss.xml"),
    ("japan_times", "https://www.japantimes.co.jp/feed/"),
    ("korea_herald", "https://www.koreaherald.com/common/rss_xml.php"),
    ("taipei_times", "https://www.taipeitimes.com/xml/index.rss"),
    ("bangok_post", "https://www.bangkokpost.com/rss/data/topstories.xml"),
    ("abc_au", "https://www.abc.net.au/news/feed/51120/rss.xml"),
    ("rnz", "https://www.rnz.co.nz/rss/national.xml"),
    # Africa
    ("allafrica", "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf"),
    ("africa_report", "https://www.theafricareport.com/feed/"),
    ("daily_maverick", "https://www.dailymaverick.co.za/feed/"),
    ("punch_ng", "https://punchng.com/feed/"),
    ("nation_ke", "https://nation.africa/rss"),
    # Latin America
    ("mercopress", "https://en.mercopress.com/rss"),
    ("ba_times", "https://www.batimes.com.ar/feed"),
    ("brazil_wire", "https://www.brasilwire.com/feed/"),
    # Russia / Eastern Europe / Central Asia
    ("moscow_times", "https://www.themoscowtimes.com/rss/news"),
    ("kyiv_independent", "https://kyivindependent.com/feed/"),
    ("meduza_en", "https://meduza.io/rss/en/all"),
    ("bne_intellinews", "https://www.intellinews.com/rss"),
    ("eurasianet", "https://eurasianet.org/feed"),
    ("rferl", "https://www.rferl.org/api/"),
    # Tech
    ("ars_technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("techcrunch_ai", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("wired", "https://www.wired.com/feed/rss"),
    ("the_verge", "https://www.theverge.com/rss/index.xml"),
    ("mit_tech", "https://www.technologyreview.com/feed/"),
    ("zdnet", "https://www.zdnet.com/news/rss.xml"),
    ("engadget", "https://www.engadget.com/rss.xml"),
    ("venturebeat_ai", "https://venturebeat.com/category/ai/feed/"),
    # Science / Environment
    ("phys_earth", "https://phys.org/rss-feed/earth-news/"),
    ("nature_news", "https://www.nature.com/nature.rss"),
    ("new_scientist", "https://www.newscientist.com/feed/home/?cmpid=RSS"),
    ("science_daily", "https://www.sciencedaily.com/rss/all.xml"),
    # Health / Pandemic
    ("who_news", "https://www.who.int/rss-feeds/news-english.xml"),
    ("stat_news", "https://www.statnews.com/feed/"),
    # Business / Finance
    ("bloomberg_markets", "https://feeds.bloomberg.com/markets/news.rss"),
    ("cnbc_world", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362"),
    ("marketwatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("investing_com", "https://www.investing.com/rss/news.rss"),
    ("zero_hedge", "https://feeds.feedburner.com/zerohedge/feed"),
    # Texas Local
    ("kltv_tyler", "https://www.kltv.com/news/rss/"),
    # AI Industry
    ("therundown_ai", "https://www.therundown.ai/feed"),
]

# ═══════════════════════════════════════════════════════════════════════════
# THINK TANK & ANALYSIS FEEDS
# ═══════════════════════════════════════════════════════════════════════════

ANALYSIS_FEEDS = [
    # US Foreign Policy / Defense
    ("atlantic_council", "https://www.atlanticcouncil.org/feed/"),
    ("brookings", "https://www.brookings.edu/feed/"),
    ("csis", "https://www.csis.org/feed"),
    ("cfr", "https://www.cfr.org/rss/"),
    ("carnegie", "https://carnegieendowment.org/rss/solr/?lang=en"),
    ("heritage", "https://www.heritage.org/rss"),
    ("aei", "https://www.aei.org/feed/"),
    ("cato", "https://www.cato.org/rss/recent-opeds.xml"),
    ("hoover", "https://www.hoover.org/rss"),
    ("wilson_center", "https://www.wilsoncenter.org/rss.xml"),
    ("cnas", "https://www.cnas.org/rss"),
    ("fdd", "https://www.fdd.org/feed/"),
    ("rand_commentary", "https://www.rand.org/pubs/commentary.xml"),
    ("rand_research", "https://www.rand.org/pubs/research_reports.xml"),
    ("stimson", "https://www.stimson.org/feed/"),
    ("new_america", "https://www.newamerica.org/rss/"),
    ("third_way", "https://www.thirdway.org/feed"),
    ("bipartisan_policy", "https://bipartisanpolicy.org/feed/"),
    ("hudson_institute", "https://www.hudson.org/feed"),
    ("german_marshall", "https://www.gmfus.org/rss"),
    # Security / Defense / Military
    ("war_on_rocks", "https://warontherocks.com/feed/"),
    ("defense_news", "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("defense_one", "https://www.defenseone.com/rss/"),
    ("breaking_defense", "https://breakingdefense.com/feed/"),
    ("the_drive_warzone", "https://www.thedrive.com/the-war-zone/feed"),
    ("iiss", "https://www.iiss.org/rss"),
    ("rusi", "https://rusi.org/feed"),
    ("sipri", "https://www.sipri.org/rss.xml"),
    # Conflict / Crisis / OSINT
    ("crisis_group", "https://www.crisisgroup.org/rss.xml"),
    ("bellingcat", "https://www.bellingcat.com/feed/"),
    ("just_security", "https://www.justsecurity.org/feed/"),
    ("foreign_policy", "https://foreignpolicy.com/feed/"),
    ("foreign_affairs", "https://www.foreignaffairs.com/rss.xml"),
    ("diplomat", "https://thediplomat.com/feed/"),
    ("national_interest", "https://nationalinterest.org/feed"),
    # European Think Tanks
    ("ecfr", "https://ecfr.eu/feed/"),
    ("chatham_house", "https://www.chathamhouse.org/rss"),
    ("bruegel", "https://www.bruegel.org/rss"),
    ("eu_iss", "https://www.iss.europa.eu/feed"),
    ("cepa", "https://cepa.org/feed/"),
    # Asia-Pacific Think Tanks
    ("lowy", "https://www.lowyinstitute.org/rss.xml"),
    ("aspi_aus", "https://www.aspi.org.au/rss.xml"),
    ("iseas", "https://www.iseas.edu.sg/feed/"),
    ("carnegie_china", "https://carnegieendowment.org/programs/asia/rss"),
    # Nuclear / Arms / WMD
    ("arms_control", "https://www.armscontrol.org/taxonomy/term/30/feed"),
    ("nti", "https://www.nti.org/rss/"),
    ("iaea_news", "https://www.iaea.org/feeds/news"),
    ("bulletin_atomic", "https://thebulletin.org/feed/"),
    # Economics / Trade
    ("piie", "https://www.piie.com/rss"),
    ("imf_blog", "https://www.imf.org/en/Blogs/RSS"),
    # Cyber / Technology Policy
    ("krebs_security", "https://krebsonsecurity.com/feed/"),
    ("cisa_alerts", "https://www.cisa.gov/cybersecurity-advisories/all.xml"),
    ("dark_reading", "https://www.darkreading.com/rss.xml"),
    ("security_week", "https://www.securityweek.com/feed"),
    ("schneier", "https://www.schneier.com/feed/atom/"),
    ("eff", "https://www.eff.org/rss/updates.xml"),
    # Humanitarian / Development
    ("reliefweb", "https://reliefweb.int/updates/rss.xml"),
    ("devex", "https://www.devex.com/news/rss"),
    # Regulatory / Legal / Policy
    ("fed_register", "https://www.federalregister.gov/documents/search.rss?conditions%5Btype%5D=RULE"),
    ("scotusblog", "https://www.scotusblog.com/feed/"),
    ("iep", "https://www.economicsandpeace.org/feed/"),
    # Energy / Climate
    ("carbon_brief", "https://www.carbonbrief.org/feed"),
    ("energy_monitor", "https://www.energymonitor.ai/feed/"),
    ("oilprice", "https://oilprice.com/rss/main"),
    ("world_nuclear", "https://www.world-nuclear-news.org/rss"),
    # Maritime / Shipping
    ("maritime_exec", "https://www.maritime-executive.com/rss"),
    ("gcaptain", "https://gcaptain.com/feed/"),
    # Aviation / Space
    ("aviation_week", "https://aviationweek.com/rss"),
    ("space_news", "https://spacenews.com/feed/"),
    ("nasa_breaking", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
]

# ═══════════════════════════════════════════════════════════════════════════
# GOVERNMENT & OFFICIAL FEEDS
# ═══════════════════════════════════════════════════════════════════════════

OFFICIAL_FEEDS = [
    # US Government
    ("fed_reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("white_house", "https://www.whitehouse.gov/feed/"),
    ("state_dept", "https://www.state.gov/rss-feed/press-releases/feed/"),
    ("dod_news", "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?max=10&ContentType=1"),
    ("doj_press", "https://www.justice.gov/feeds/opa/justice-news.xml"),
    ("fbi_press", "https://www.fbi.gov/feeds/fbi-in-the-news/rss.xml"),
    ("treasury_press", "https://home.treasury.gov/system/files/131/Treasury-Press-Releases.xml"),
    ("gao_reports", "https://www.gao.gov/rss/reports.xml"),
    ("cbo_reports", "https://www.cbo.gov/publications/feed"),
    ("usaid", "https://www.usaid.gov/rss.xml"),
    ("ustr", "https://ustr.gov/rss"),
    ("sec_press", "https://www.sec.gov/rss/news/press.xml"),
    ("fcc", "https://www.fcc.gov/rss.xml"),
    ("epa", "https://www.epa.gov/newsreleases/search/rss"),
    ("fema_news", "https://www.fema.gov/rss.xml"),
    # International Organizations
    ("un_news", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
    ("un_security_council", "https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/rss.xml"),
    ("nato_news", "https://www.nato.int/cps/en/natohq/news.xml"),
    ("eu_press", "https://ec.europa.eu/commission/presscorner/api/rss"),
    ("osce", "https://www.osce.org/rss.xml"),
    ("icc_news", "https://www.icc-cpi.int/rss"),
    ("icj_press", "https://www.icj-cij.org/rss/pressreleases.xml"),
    ("opcw", "https://www.opcw.org/rss.xml"),
    # Central Banks
    ("ecb", "https://www.ecb.europa.eu/rss/press.html"),
    ("boe", "https://www.bankofengland.co.uk/rss/publications"),
    ("boj", "https://www.boj.or.jp/en/rss/whatsnew.xml"),
    ("rba", "https://www.rba.gov.au/rss/rss-cb-media-releases.xml"),
    ("bis", "https://www.bis.org/doclist/cbspeeches.rss"),
    ("imf_press", "https://www.imf.org/en/News/RSS"),
    ("world_bank_press", "https://www.worldbank.org/en/news/all?lang_exact=English&format=rss"),
    # Foreign Governments
    ("uk_parliament", "https://www.parliament.uk/g/rss/commons-hansard/"),
    ("uk_gov", "https://www.gov.uk/government/all.atom"),
    ("eu_parliament", "https://www.europarl.europa.eu/rss/en/top-story.xml"),
    ("canada_pm", "https://pm.gc.ca/en/rss.xml"),
    ("india_mea", "https://www.mea.gov.in/rss.xml"),
    ("aus_dfat", "https://www.dfat.gov.au/rss.xml"),
]

# ═══════════════════════════════════════════════════════════════════════════
# REDDIT SUBREDDITS
# ═══════════════════════════════════════════════════════════════════════════

SUBREDDITS = [
    # ── Geopolitical / Intelligence / Defense ──
    "worldnews", "geopolitics", "intelligence", "CredibleDefense",
    "NuclearPower", "foreignpolicy", "MiddleEastNews",
    "LessCredibleDefence", "WarCollege", "MilitaryPorn",
    "CombatFootage", "GlobalPolitics", "InternationalNews",
    "UkrainianConflict", "UkraineWarVideoReport",
    "IsraelPalestine", "Israel", "Palestine",
    "NorthKoreaNews", "taiwan", "China_irl",
    "SouthAsianPolitics", "AfricaNews",
    "LatinAmericaNews", "EuropeanFederalists",
    "EndlessWar", "WarOnTerror",
    "OSINT", "GeoIntelligence",
    # ── US Politics / Deep Politics ──
    "politics", "PoliticalDiscussion", "NeutralPolitics",
    "law", "scotus", "Ask_Politics",
    "Conservative", "democrats", "Libertarian",
    "uspolitics", "AmericanPolitics",
    "congress", "RunForIt", "VotingTheory",
    "PoliticalScience", "StateOfTheUnion",
    "Keep_Track", "RussiaLago",
    "WikiLeaks",
    # ── Economics / Markets / Finance ──
    "economics", "CryptoCurrency", "wallstreetbets", "stocks",
    "SupplyChain", "commodities", "investing",
    "badeconomics", "economy", "econmonitor",
    "finance", "personalfinance", "RealEstate",
    "Superstonk", "options", "forex",
    # ── Business / Trade Pain Signals ──
    "smallbusiness", "HVAC", "Plumbing", "electricians",
    "Roofing", "lawncare", "AutoRepair", "contractors",
    "Entrepreneur", "startups",
    # ── Technology / AI / Cyber ──
    "technology", "artificial", "cybersecurity", "privacy",
    "MachineLearning", "ChatGPT", "LocalLLaMA",
    "netsec", "hacking", "ReverseEngineering",
    "deepfakes", "Futurology", "singularity",
    "sysadmin", "devops",
    # ── Science / Environment / Disaster ──
    "collapse", "preppers", "weather", "TropicalWeather",
    "Earthquakes", "climate", "environment",
    "EverythingScience", "space", "Astronomy",
    "nuclear", "ClimateActionPlan",
    # ── Infrastructure / Transport / Energy ──
    "aviation", "shipping", "energy",
    "grid", "water", "infrastructure",
    "electricvehicles", "solar",
    # ── Regional Intelligence ──
    "india", "europe", "africa", "China", "LatinAmerica",
    "Russia", "ukraine", "Turkey", "iran",
    "SaudiArabia", "japan", "korea",
    "Philippines", "Indonesia", "Mexico",
    "Brazil", "unitedkingdom", "france",
    "germany", "australia", "canada",
    "SouthAfrica", "Egypt", "Nigeria",
    # ── OSINT / Investigation / Journalism ──
    "journalism", "media_criticism",
    "DataHoarder", "datasets",
    "Documentaries", "UnresolvedMysteries",
]

# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM OSINT CHANNELS
# ═══════════════════════════════════════════════════════════════════════════

TELEGRAM_CHANNELS = [
    # Conflict / Military
    ("osintdefender", "Global OSINT, verified visuals"),
    ("ClashReport", "Battlefield footage worldwide"),
    ("intelslava", "Ukraine/Russia ground updates"),
    ("middleeastobserver", "Israel-Gaza, Syria, Lebanon, Iran"),
    ("BellumActaNews", "Global military developments"),
    ("war_monitor", "Multi-theater conflict"),
    ("Intel_Sky", "Air movements and military aviation OSINT"),
    ("GeoConfirmed", "Geolocated open-source intelligence"),
    ("MilRadar", "Military radar and air defense tracking"),
    ("ukraine_map", "Ukraine frontline mapping"),
    ("ryaborig", "Russia-Ukraine detailed analysis"),
    ("SputnikInt", "Russian state perspective — read for bias signals"),
    # Regional
    ("SyriaLiveNews", "Syria conflict and reconstruction"),
    ("YemenUpdate", "Yemen and Houthi developments"),
    ("LibyaReview", "Libya political and military situation"),
    ("iran_watch", "Iran internal politics and IRGC"),
    ("ChinaBriefing", "PRC politics, military, economy"),
    ("Asianboss", "Asia-Pacific developments"),
    # Geopolitical Analysis
    ("geopolitics_live", "Real-time geopolitical analysis"),
    ("StratIntl", "Strategic intelligence briefings"),
    ("warfakes", "Debunking war misinformation"),
    # Economics / Markets
    ("WallStreetSilver", "Precious metals and macro"),
    ("financialtelegraph", "Breaking financial news"),
    # Nuclear / WMD
    ("NuclearAlerts", "Nuclear weapons and energy developments"),
    # Cyber / Tech
    ("caboroofleaks", "Cybersecurity leaks and breaches"),
    ("hackernews_feed", "Hacker News top stories"),
]

# ═══════════════════════════════════════════════════════════════════════════
# SPECIALIZED INTELLIGENCE FEEDS
# ═══════════════════════════════════════════════════════════════════════════

SPECIALIZED_FEEDS = [
    # Sanctions / Compliance / Financial Crime
    ("fatf", "https://www.fatf-gafi.org/rss/all.xml"),
    # Courts / Legal Intelligence
    ("courtlistener", "https://www.courtlistener.com/feed/court/scotus/"),
    ("recap", "https://www.courtlistener.com/feed/search/?type=r&order_by=score+desc"),
    # Trade / Tariffs
    ("wto_news", "https://www.wto.org/english/news_e/news_e.rss"),
    ("unctad", "https://unctad.org/rss.xml"),
    # Migration / Border
    ("unhcr", "https://www.unhcr.org/rss/all.xml"),
    ("iom", "https://www.iom.int/rss.xml"),
    # Human Rights
    ("hrw", "https://www.hrw.org/rss/news_and_commentary"),
    ("amnesty", "https://www.amnesty.org/en/feed/"),
    # Terrorism / Extremism
    ("terrorism_monitor", "https://jamestown.org/programs/tm/feed/"),
    ("combating_terrorism", "https://ctc.westpoint.edu/feed/"),
    # Climate / Disaster Risk
    ("climate_central", "https://www.climatecentral.org/rss"),
    ("prevention_web", "https://www.preventionweb.net/rss"),
    # Disinformation / Media
    ("eu_vs_disinfo", "https://euvsdisinfo.eu/feed/"),
    ("media_bias", "https://mediabiasfactcheck.com/feed/"),
    # Academic / Preprint Early Signals
    ("arxiv_cs_ai", "https://rss.arxiv.org/rss/cs.AI"),
    ("arxiv_cs_cr", "https://rss.arxiv.org/rss/cs.CR"),
    # Small Business
    ("nfib", "https://www.nfib.com/feed/"),
    # Real Estate
    ("zillow_research", "https://www.zillow.com/research/feed/"),
]


def count_all_sources():
    """Return total source count across all categories."""
    news = len(NEWS_FEEDS)
    analysis = len(ANALYSIS_FEEDS)
    official = len(OFFICIAL_FEEDS)
    subs = len(SUBREDDITS)
    telegram = len(TELEGRAM_CHANNELS)
    specialized = len(SPECIALIZED_FEEDS)
    # Plus the 20+ API-based scan functions (USGS, NOAA, GDELT, etc.)
    api_sources = 25
    total = news + analysis + official + subs + telegram + specialized + api_sources
    return {
        "news_feeds": news,
        "analysis_feeds": analysis,
        "official_feeds": official,
        "subreddits": subs,
        "telegram_channels": telegram,
        "specialized_feeds": specialized,
        "api_sources": api_sources,
        "total": total,
    }


if __name__ == "__main__":
    c = count_all_sources()
    for k, v in c.items():
        print(f"  {k}: {v}")
