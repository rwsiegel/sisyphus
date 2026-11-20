# One profile per company, merged from these sources (first one with a value wins):
#   1. company_facts.py      - facts verified in the main session on 2026-11-19 ("this run")
#   2. profiles_batch_*.json - web research by helper agents on 2026-11-19 ("research 2026-11-19")
#   3. Startup Shortlist     - the Claude-app page, checked October 2026 ("shortlist Oct 2026")
# Stack also comes from live postings collected in this run (see stack.py).
import glob
import os
import json
import re
from datetime import date

from companies import read_shortlist
from company_facts import FACTS
from settings import DATA_DIR, RUN_DAY

SHORTLIST = "shortlist Oct 2026"
RESEARCH = "research 2026-11-19"


def load_research():
    research = {}
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "research", "*", "*.json"))):
        try:
            research.update(json.load(open(path, encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass  # a batch file that is mid-write or broken is skipped; its companies show as not researched
    return {k.lower(): v for k, v in research.items()}


def shortlist_by_name():
    data, _ = read_shortlist()
    return {d["name"].lower(): d for d in data}


def as_text(value):
    if isinstance(value, list):
        return " | ".join(str(v) for v in value)
    return str(value or "")


def layoff_penalty_from_text(text):
    """Find YYYY-MM dates in a layoff note. Within 12 months = 20, 12-24 months = 10."""
    worst = 0
    for year, month in re.findall(r"\b(20\d\d)-(\d\d)\b", text or ""):
        months_ago = (RUN_DAY.year - int(year)) * 12 + RUN_DAY.month - int(month)
        if 0 <= months_ago <= 12:
            worst = max(worst, 20)
        elif months_ago <= 24:
            worst = max(worst, 10)
    return worst


def first_rating(text):
    m = re.match(r"\s*(\d\.\d)", text or "")
    return float(m.group(1)) if m else None


def build_profile(name, shortlist, research, live_stack, live_stack_basis):
    s = shortlist.get(name.lower(), {})
    r = research.get(name.lower(), {})
    f = FACTS.get(name, {})

    def pick(fact_value, research_value, shortlist_value):
        """Return (text, source label) from the first source that has a value."""
        if fact_value:
            return as_text(fact_value), "this run"
        if research_value and as_text(research_value).lower() not in ("not found", "unknown"):
            return as_text(research_value), RESEARCH
        if shortlist_value:
            return as_text(shortlist_value), SHORTLIST
        return "", ""

    what, what_src = pick(None, r.get("what_they_build"), s.get("blurb"))
    investors, inv_src = pick(f.get("investors"), r.get("investors"), s.get("investors"))
    customers, cust_src = pick(None, r.get("customers"), s.get("customers"))
    headcount, head_src = pick(None, r.get("headcount"), s.get("headcount"))
    worth, worth_src = pick(None, r.get("worth_knowing"), s.get("facts"))
    watch, watch_src = pick(None, r.get("watch_outs"), s.get("warnings"))

    profile = {
        "what_they_build": what, "what_source": what_src,
        "sector": s.get("sector", ""),
        "headcount": headcount,
        "investors": investors, "investors_source": inv_src,
        "stack_live": live_stack, "stack_live_basis": live_stack_basis,
        "stack_shortlist": ", ".join(s.get("stack", [])),
        "customers": customers, "customers_source": cust_src,
        "location_detail": s.get("loc", "") or as_text(r.get("hq_and_offices")),
        "boston_presence": as_text(r.get("boston_presence")) or s.get("boston", ""),
        "data_team": s.get("team", ""),
        "possible_first_data_hire": s.get("fdh", ""),
        "worth_knowing": worth, "worth_source": worth_src,
        "watch_outs": watch, "watch_source": watch_src,
        "identity_note": as_text(r.get("identity_note")),
        "careers_page": s.get("careers", ""),
        "sources": " ; ".join(x for x in [f.get("sources", ""), as_text(r.get("sources")).replace(" | ", " ; "),
                                          " ; ".join(s.get("sources", []))] if x),
    }

    # Layoffs
    if f.get("layoffs"):
        profile["layoffs"] = f["layoffs"] + " (this run)"
        profile["layoff_penalty"] = f.get("layoff_penalty", 0)
    elif r.get("layoffs"):
        profile["layoffs"] = as_text(r["layoffs"]) + f" ({RESEARCH})"
        profile["layoff_penalty"] = layoff_penalty_from_text(as_text(r["layoffs"]))
    elif s:
        events = s.get("lay_events") or []
        profile["layoffs"] = ("; ".join(str(e) for e in events) or (s.get("layoff") or "none reported")) + f" ({SHORTLIST})"
        profile["layoff_penalty"] = s.get("layoff_pen", 0) or 0
    else:
        profile["layoffs"] = "not researched"
        profile["layoff_penalty"] = 0

    # Glassdoor
    if f.get("glassdoor_note"):
        profile["glassdoor"] = f["glassdoor_note"] + " (this run)"
        profile["glassdoor_rating"] = f.get("glassdoor")
    elif r.get("glassdoor") and first_rating(as_text(r["glassdoor"])) is not None:
        profile["glassdoor"] = as_text(r["glassdoor"]) + f" ({RESEARCH})"
        profile["glassdoor_rating"] = first_rating(as_text(r["glassdoor"]))
    elif s.get("glassdoor"):
        g = s["glassdoor"]
        profile["glassdoor"] = f"{g['rating']} from {g['reviews']} reviews (checked {g.get('checked', 'Oct 2026')}, {SHORTLIST})"
        profile["glassdoor_rating"] = g["rating"]
    else:
        profile["glassdoor"] = "not found" if (s or r) else "not researched"
        profile["glassdoor_rating"] = None

    # Stage
    if f.get("stage"):
        profile["stage"] = f["stage"] + " (this run)"
        profile["stage_in_a_to_d"] = f.get("stage_in_a_to_d")
    elif r.get("stage") and as_text(r["stage"]).lower() not in ("not found", "unknown"):
        parts = [as_text(r.get(k)) for k in ("stage", "last_round", "round_date") if r.get(k) and as_text(r.get(k)) != "not found"]
        lead = as_text(r.get("lead"))
        profile["stage"] = ", ".join(parts) + (f", lead {lead}" if lead and lead != "not found" else "") + f" ({RESEARCH})"
        profile["stage_in_a_to_d"] = stage_in_a_to_d(as_text(r["stage"]))
    elif s:
        profile["stage"] = f"{s['stage']}, {s['last_round']}, {s['date']}, lead {s.get('lead') or 'unknown'} ({SHORTLIST})"
        profile["stage_in_a_to_d"] = stage_in_a_to_d(s["stage"])
    else:
        profile["stage"] = "not researched"
        profile["stage_in_a_to_d"] = None
    return profile


def stage_in_a_to_d(stage_text):
    t = stage_text.lower()
    # Acquired or public first: a note like "Series B; acquired by X" is not a Series A-D startup.
    if re.search(r"acquired|acquisition|\bpublic\b|\bipo\b", t):
        return False
    if re.search(r"series [a-d]\b", t):
        return True
    if re.search(r"series [e-z]\b|seed", t):
        return False
    return None
