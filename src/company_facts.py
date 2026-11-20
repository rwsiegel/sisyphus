# Company facts found by web search on 2026-11-19. Each fact keeps its source URL.
# "none found" means a search was run and returned nothing. "not found" means the search did not answer it.
# Companies not listed here were not researched (their target roles, if any, were older than 30 days).

TOP10_NOTE = ("Investor score 0: only ranks 1-10 of the Strebulaev-Jackson list are available (fallback approved), "
              "and no Boston office was found for any top-10 firm (Menlo, Lightspeed, a16z, Thrive, Dragoneer, Sequoia, Benchmark, Factorial).")

FACTS = {
    "AcuityMD": {
        "stage": "Series C ($80M, Apr 2026, led by StepStone)", "stage_in_a_to_d": True,
        "investors": "StepStone, Benchmark, Redpoint, ICONIQ, Atreides",
        "top10_firms_present": "Benchmark (Eric Vishria is rank 9; his personal involvement not confirmed)",
        "layoffs": "none found", "layoff_penalty": 0,
        "glassdoor": 4.1, "glassdoor_note": "4.1 from 39 reviews (glassdoor.ca, via search snippet)",
        "other_flags": "health/medtech",
        "sources": "https://hlth.com/insights/news/acuitymd-raises-80m-series-c-led-by-stepstone-group-nears-1b-valuation ; "
                   "https://trueup.io/co/acuitymd ; https://www.glassdoor.ca/Reviews/AcuityMD-Reviews-E6755063.htm ; "
                   "https://builtin.com/company/acuitymd/faq/work-life-balance-wellbeing",
    },
    "Suno": {
        "stage": "Series D ($400M, Jun 2026, led by Bond)", "stage_in_a_to_d": True,
        "investors": "Bond, Lightspeed, Menlo, Matrix, Schroders Capital",
        "top10_firms_present": "Lightspeed, Menlo (firm level; partner involvement not confirmed)",
        "layoffs": "none found", "layoff_penalty": 0,
        "glassdoor": 4.0, "glassdoor_note": "4.0 from 10 reviews on glassdoor.com snippet; aggregators show 3.9-4.2",
        "other_flags": "music-label copyright litigation reported",
        "sources": "https://builtin.com/articles/suno-raises-400m-series-d-54b-valuation-20260603 ; "
                   "https://siliconangle.com/2026/06/03/generative-ai-music-startup-suno-ai-raises-400m-5-4b-valuation/ ; "
                   "https://www.glassdoor.com/Reviews/-Reviews-E1265394.htm ; https://builtin.com/company/suno-sunocom/benefits",
    },
    "Oddball": {
        "stage": "no venture round found (federal services contractor)", "stage_in_a_to_d": None,
        "investors": "not found", "top10_firms_present": "",
        "layoffs": "none found (search returned general federal 18F cuts, not Oddball)", "layoff_penalty": 0,
        "glassdoor": 4.7, "glassdoor_note": "4.7 shown on joinrise.co aggregator; Glassdoor page not read",
        "other_flags": "federal work (VA, CMS)",
        "sources": "https://app.joinrise.co/company/oddball ; https://simplify.jobs/c/Oddball",
    },
    "Horizon3.ai": {
        "stage": "Series E ($250M, Aug 2026)", "stage_in_a_to_d": False,
        "investors": "NightDragon, NEA, SignalFire, Craft", "top10_firms_present": "",
        "layoffs": "none found", "layoff_penalty": 0,
        "glassdoor": None, "glassdoor_note": "not found",
        "other_flags": "cybersecurity; federal",
        "sources": "https://siliconangle.com/2026/08/03/horizon3-ai-raises-250m-2b-plus-valuation-autonomous-pentesting/ ; "
                   "https://builtin.com/company/horizon3ai/faq/work-life-balance-wellbeing",
    },
    "Vanta": {
        "stage": "Series D ($150M, Jul 2025, led by Wellington)", "stage_in_a_to_d": True,
        "investors": "Wellington, Sequoia, J.P. Morgan, Craft, Y Combinator, CrowdStrike Ventures",
        "top10_firms_present": "Sequoia (firm level; Patrick Grady involvement not confirmed)",
        "layoffs": "not found (search did not answer)", "layoff_penalty": 0,
        "glassdoor": None, "glassdoor_note": "not found",
        "other_flags": "cybersecurity / compliance",
        "sources": "https://www.businesswire.com/news/home/20250723901336/en/Vanta-Raises-150M-Series-D-to-Power-the-Future-of-AI-Driven-Trust/",
    },
    "Walden Robotics": {
        "stage": "unknown (aggregators disagree: Seed vs $300M raised)", "stage_in_a_to_d": None,
        "investors": "not researched", "top10_firms_present": "",
        "layoffs": "not researched", "layoff_penalty": 0,
        "glassdoor": None, "glassdoor_note": "not researched",
        "other_flags": "on-site Cambridge MA",
        "sources": "https://ats.rippling.com/walden-robotics/jobs/c60cb342-dbf6-471b-9c1d-1ded6697680d",
    },
    "ASI": {
        "stage": "Series C ($325M, Oct 2026, led by Spark)", "stage_in_a_to_d": True,
        "investors": "Spark, Craft, Andreessen Horowitz, Citadel Securities affiliates",
        "top10_firms_present": "a16z (firm level)",
        "layoffs": "not researched", "layoff_penalty": 0, "glassdoor": None, "glassdoor_note": "not researched",
        "other_flags": "defense work mentioned",
        "sources": "https://theaiinsider.tech/2026/10/21/asi-secures-325m-series-c-at-3b-valuation-to-scale-ai-for-physical-infrastructure/",
    },
}

# Job boards that could not be read through an API. Leads from search snippets only (not verified live).
NOT_REACHED = {
    "Marqeta": "Greenhouse board 'marqeta' returns 404 now; search snippets are cached.",
    "Second Front": "No public board found; roles seen only on aggregators (Built In, startup.jobs).",
    "Spellbook": "No public board found; aggregator roles mostly remote Canada.",
    "ASI": "No board found (greenhouse 'asi' is a different company).",
    "Ledgebrook": "No board found; Built In lists roles (none data engineering).",
    "OnCorps": "No board found; Built In lists software roles in Boston.",
    "Parabilis Medicines": "Greenhouse slug not found; aggregators list science roles only.",
    "Anagram Therapeutics, Inc.": "No board found; aggregators list CMC/QC roles.",
    "Life Biosciences": "No board; careers page says email careers@lifebiosciences.com.",
    "Mediar Therapeutics": "No board found; Built In lists clinical/CMC roles.",
    "Ratio Therapeutics": "No board found; Built In snippet shows a Junior Data Engineer (junior, from snippet).",
    "Crossbow Therapeutics, Inc": "Lever board 'crossbow-therapeutics' has 0 open postings.",
    "Axoft": "Uses Polymer; no API read. Snippets show a director role mentioning data pipelines.",
    "Elucid": "No board found; Built In lists imaging/clinical roles.",
    "Neurable": "Own careers pages only; snippets show UX, IT, Android roles.",
    "Commonwealth Fusion Systems": "No board found. Snippets: Enterprise Cloud Data Engineer (Devens MA, hybrid, $70-120K, one copy says closed); Senior Data and Operations Software Engineer. Dates unknown.",
    "Applied Compute": "No board found (ashby 'applied' is a different company). In-person San Francisco per snippets.",
    "General Intuition": "No board found. Roles in NYC/London/Paris per snippets.",
    "Ricursive": "No board found. Palo Alto on-site per snippets.",
    "Unconventional AI": "Search returned no results for the company.",
}
