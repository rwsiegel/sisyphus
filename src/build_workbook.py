# Score target-role postings and write the ranked workbook.
# Score (out of 125, minus layoff penalty):
#   pay 30, investors 20, role fit 25, hiring proxy 15, recency 25, TF-IDF 10. PTO is not scored (owner's decision, 2026-11-19).
import gzip
import json
import os
import re
from collections import Counter

import docx
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from companies import load_companies
from company_facts import FACTS, NOT_REACHED, TOP10_NOTE
from filters import WRONG_BOARDS, RUN_DATE, role_type, seniority, location_fit, parse_date
from companies import ats_slug_from_url
from profiles import build_profile, load_research, shortlist_by_name, stage_in_a_to_d
from stack import company_stack
from settings import (OUTPUT_DIR, PAY_FLOOR, PRIVATE_NOTES, RESUME_AE, RESUME_DE, RUN_DAY,
                      data_path, run_path)

# Scoring runs locally only. Resumes are read in place; outputs go to a private local folder.
# The JSON output contains resume-derived TF-IDF scores: keep it private.
OUTPUT = os.path.join(OUTPUT_DIR, f"job_search_run_{RUN_DAY.isoformat()}.xlsx")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, f"job_search_run_{RUN_DAY.isoformat()}.json")

PAY_TEXT = f"${PAY_FLOOR // 1000}K"
# A near miss fails exactly one hard criterion by a small margin: posted up to 30 days ago,
# or pay topping out within 10% of the pay floor.
NEAR_MISS_DAYS = 30
NEAR_MISS_PAY_SHARE = 0.9


def linkedin_search(company):
    """Past-week LinkedIn job search for this company's data roles. To click by hand; nothing is fetched automatically."""
    from urllib.parse import quote
    name = re.sub(r"\s*\(.*\)$", "", company)
    keywords = f'"{name}" AND ("analytics engineer" OR "data engineer" OR "data platform")'
    return "https://www.linkedin.com/jobs/search-results/?keywords=" + quote(keywords) + "&f_TPR=r604800"


def read_docx(path):
    return "\n".join(p.text for p in docx.Document(path).paragraphs)


def parse_pay(pay_field, text):
    """Return (low, high) base pay in dollars, or (None, None) if not posted."""
    source = pay_field or ""
    amounts = []
    for m in re.finditer(r"\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,3}(?:\.\d+)?\s?[kK])", source):
        raw = m.group(1).replace(",", "").replace(" ", "")
        value = float(raw[:-1]) * 1000 if raw[-1] in "kK" else float(raw)
        if value >= 30_000:
            amounts.append(value)
    if not amounts:
        # plain numbers like "255000-340000" (Lever, Rippling)
        amounts = [float(n) for n in re.findall(r"\b(\d{5,6})\b", source) if float(n) >= 30_000]
    if not amounts:
        # fall back to "$123,456" style amounts written in the posting text
        for m in re.finditer(r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}\s?[kK])", text or ""):
            raw = m.group(1).replace(",", "").replace(" ", "")
            value = float(raw[:-1]) * 1000 if raw[-1] in "kK" else float(raw)
            if 30_000 <= value <= 1_000_000:
                amounts.append(value)
    if not amounts:
        return None, None
    return min(amounts), max(amounts)


def pay_points(low, high):
    if low is None:
        return 0, "pay unposted"
    if low >= PAY_FLOOR:
        return 30, ""
    if high >= PAY_FLOOR:
        return 20, f"range starts below {PAY_TEXT}"
    return 0, f"top of range below {PAY_TEXT}"


def hiring_points(open_count):
    # Proxy only: current open postings on the company board. No history yet.
    if open_count >= 50:
        return 15
    if open_count >= 20:
        return 10
    if open_count >= 5:
        return 5
    return 0


def role_fit_points(title_type, level, where):
    # Out of 25. Analytics engineer aligns most closely with the owner's background (2026-11-19).
    points = {"analytics engineer": 15, "data engineer": 12, "data platform engineer": 9,
              "software engineer on a data platform": 6}.get(title_type, 0)
    points += {"senior+": 5, "not stated": 4, "junior": 0}[level]
    if where in ("Boston", "Remote US"):
        points += 5
    elif where.startswith("Remote"):
        points += 2
    return points


def recency_points(age_days):
    # Out of 25. 1 day or less 25, 3 days 20, 7 days 15, then a straight line down to 3 at 90 days.
    if age_days is None:
        return 0
    if age_days <= 1:
        return 25
    if age_days <= 3:
        return 20
    if age_days <= 7:
        return 15
    if age_days <= 90:
        return round(15 - (age_days - 7) * (12 / 83), 1)
    return 0  # older than 90 days


def years_asked(text):
    """Largest 'N years' experience requirement in the posting, or None."""
    found = [int(n) for n in re.findall(r"(\d{1,2})\+?\s*(?:-\s*\d+\s*)?years?(?:\s+of)?(?:\s+\w+){0,3}\s+experience", text or "", re.I)]
    found += [int(n) for n in re.findall(r"plus\s+(\d{1,2})\s+years?", text or "", re.I)]
    found = [n for n in found if n <= 20]
    return max(found) if found else None


with gzip.open(run_path("postings.json.gz"), "rt", encoding="utf-8") as f:
    postings = json.load(f)
postings = [p for p in postings if (p["company"], p["ats"], p["slug"]) not in WRONG_BOARDS]

# Investor-board companies: keep only the board their job link points to (same slug on another
# system can be a different company), and drop Truebill (same board as Rocket Money).
investor_board_hint = {c["company"]: ats_slug_from_url(c["careers_hint"])
                       for c in load_companies() if c["list"].startswith("Investor boards")}
postings = [p for p in postings
            if p["company"] not in investor_board_hint
            or (investor_board_hint[p["company"]] or (None,))[0] == p["ats"]]
postings = [p for p in postings if p["company"] != "Truebill"]
open_counts = Counter(p["company"] for p in postings)

# Keep target roles in Boston or remote US (any age; the 7-day check is a column).
roles = []
seen_roles = set()  # mirrored boards (e.g. Doppel on Greenhouse and Ashby) list the same job twice
for p in postings:
    title_type = role_type(p["title"])
    if not title_type:
        continue
    if (p["company"], p["title"]) in seen_roles:  # same job posted once per city counts once
        continue
    seen_roles.add((p["company"], p["title"]))
    # Title is checked too, so "... - Europe" is not read as remote US.
    where = location_fit(p["location"] + " | " + p["title"], p["workplace"], p["text"])
    if where.startswith("No:"):
        continue
    posted = parse_date(p["posted"])
    age = max(0, (RUN_DATE - posted).days) if posted else None  # posted today shows 0, not -1
    roles.append({**p, "role_type": title_type, "level": seniority(p["title"]), "where": where, "age_days": age})

# Investor-board roles whose job is not on a board I can read (Workday, company career sites):
# use the investor board's own data (title, date, pay, location). No description, so TF-IDF uses the title only.
getro_roles = json.load(open(run_path("vc_roles.json")))["roles"]
getro_pay = {(g["company"], g["title"]): (g["pay_min"], g["pay_max"]) for g in getro_roles if g.get("pay_max")}
have = {(r["company"], r["title"]) for r in roles}
for g in getro_roles:
    if g["location_fit"] not in ("Boston", "Remote US") or g["company"] == "Truebill":
        continue
    if (g["company"], g["title"]) in have:
        continue
    have.add((g["company"], g["title"]))
    pay = f"{int(g['pay_min'])}-{int(g['pay_max'])} USD" if g.get("pay_max") else ""
    roles.append({
        "company": g["company"], "title": g["title"], "location": g["locations"], "workplace": g["work_mode"] or "",
        "posted": g["created"], "date_field": "createdAt (investor job board)", "url": g["url"] or "",
        "pay_field": pay, "text": "", "ats": "getro", "slug": ",".join(g["firms"]),
        "role_type": g["role_type"], "level": g["level"], "where": g["location_fit"],
        "age_days": max(0, (RUN_DATE - parse_date(g["created"])).days),
    })

# TF-IDF: ae resume for analytics engineer roles, de resume for everything else.
resume_de = read_docx(RESUME_DE)
resume_ae = read_docx(RESUME_AE)
texts = [r["title"] + " " + r["text"] for r in roles]
vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
matrix = vectorizer.fit_transform([resume_de, resume_ae] + texts)
for i, r in enumerate(roles):
    resume_row = 1 if r["role_type"] == "analytics engineer" else 0
    r["resume_used"] = "ae" if resume_row == 1 else "de"
    r["cosine"] = float(cosine_similarity(matrix[resume_row], matrix[2 + i])[0][0])
best_cosine = max(r["cosine"] for r in roles)

# Company profiles: today's facts, helper-agent research, then the October shortlist.
all_companies = load_companies()
shortlist = shortlist_by_name()
research = load_research()
target_titles = {r["title"] for r in roles}
postings_by_company = {}
for p in postings:
    postings_by_company.setdefault(p["company"], []).append(p)
profiles = {}
for c in all_companies:
    live_stack, basis = company_stack(postings_by_company.get(c["company"], []), target_titles)
    profiles[c["company"]] = build_profile(c["company"], shortlist, research, live_stack, basis)
    prof = profiles[c["company"]]
    if c["investor_boards"]:
        # Being listed on a firm's portfolio job board is itself a sourced investor fact.
        board_note = f"{c['investor_boards']} (listed on their portfolio job boards, 2026-11-19)"
        prof["investors"] = (prof["investors"] + " | " if prof["investors"] else "") + board_note
        prof["investors_source"] = prof["investors_source"] or "investor job boards 2026-11-19"
        if prof["stage"] == "not researched":
            getro_stage = c["funding_as_shown"].split(" per ")[0].replace("_", " ")
            prof["stage"] = getro_stage + " (investor job board, 2026-11-19)"
            prof["stage_in_a_to_d"] = stage_in_a_to_d(getro_stage)

rows = []
for r in roles:
    facts = FACTS.get(r["company"], {})
    prof = profiles[r["company"]]
    low, high = parse_pay(r["pay_field"], r["text"])
    pay_source = ""
    board_pay = getro_pay.get((r["company"], r["title"]))
    if low is None and board_pay:
        low, high = board_pay
        pay_source = "pay from investor job board"
    pay_pts, pay_flag = pay_points(low, high)
    fit_pts = role_fit_points(r["role_type"], r["level"], r["where"])
    hire_pts = hiring_points(open_counts[r["company"]])
    tfidf_pts = round(10 * r["cosine"] / best_cosine, 1)
    recency_pts = recency_points(r["age_days"])
    layoff_pen = prof["layoff_penalty"]
    total = pay_pts + 0 + fit_pts + hire_pts + recency_pts + tfidf_pts - layoff_pen

    within_7 = r["age_days"] is not None and r["age_days"] <= 7
    not_junior = r["level"] != "junior"
    pay_ok = high is not None and high >= PAY_FLOOR
    years = years_asked(r["text"])
    fails = []
    if not within_7:
        fails.append(f"posted {r['age_days']} days ago")
    if not not_junior:
        fails.append("junior title")
    if low is None:
        fails.append("pay unposted (allowed, flagged)")
    elif not pay_ok:
        fails.append(f"pay below {PAY_TEXT}")
    if prof["stage_in_a_to_d"] is False:
        fails.append("stage outside A-D (flag)")

    # Hard criteria only (stage and unposted pay are flags). A near miss fails exactly one of these.
    hard_misses = []
    small_miss = True   # true while every miss so far is within the near-miss margin
    if not within_7:
        hard_misses.append("date unknown" if r["age_days"] is None else f"posted {r['age_days']} days ago (limit 7)")
        if r["age_days"] is None or r["age_days"] > NEAR_MISS_DAYS:
            small_miss = False
    if not not_junior:
        hard_misses.append("junior title")
        small_miss = False
    if low is not None and not pay_ok:
        hard_misses.append(f"pay tops out below {PAY_TEXT}")
        if high < PAY_FLOOR * NEAR_MISS_PAY_SHARE:
            small_miss = False
    is_near_miss = len(hard_misses) == 1 and small_miss

    flags = [f for f in [pay_flag, pay_source, facts.get("other_flags", "")] if f]
    if prof["glassdoor_rating"] is not None and prof["glassdoor_rating"] < 3.5:
        flags.append("Glassdoor under 3.5")
    if r["company"] in PRIVATE_NOTES:
        flags.append(PRIVATE_NOTES[r["company"]])
    if years is not None and years <= 3:
        flags.append(f"asks for {years} years experience or less")

    rows.append({
        "Score": round(total, 1),
        "Meets all hard criteria": "Yes" if (within_7 and not_junior and (pay_ok or low is None)) else "No",
        "Why not": "; ".join(fails),
        "Hard criteria missed": len(hard_misses),
        "Near miss: missed only on": hard_misses[0] if is_near_miss else "",
        "Company": r["company"],
        "Title": r["title"],
        "Role type": r["role_type"],
        "Seniority": r["level"],
        "Location": r["location"],
        "Location fit": r["where"],
        "Posted": r["posted"][:10] if r["posted"] else "",
        "Age (days)": r["age_days"],
        "Date field": r["date_field"],
        "Pay low": low, "Pay high": high,
        "Pay as posted": r["pay_field"],
        "Pts: pay (30)": pay_pts,
        "Pts: investors (20)": 0,
        "Pts: role fit (25)": fit_pts,
        "Pts: hiring proxy (15)": hire_pts,
        "Pts: recency (25)": recency_pts,
        "Pts: TF-IDF (10)": tfidf_pts,
        "Years experience asked": years,
        "Layoff penalty": -layoff_pen,
        "TF-IDF cosine": round(r["cosine"], 3),
        "Resume used": r["resume_used"],
        "Open postings on board": open_counts[r["company"]],
        "Stage": prof["stage"],
        "Layoffs": prof["layoffs"],
        "Glassdoor": prof["glassdoor"],
        "Stack (live postings)": prof["stack_live"],
        "Flags": "; ".join(flags),
        "Source page": r["url"],
        "Read from": ("investor job board: " + r["slug"]) if r["ats"] == "getro" else (f"{r['ats']} API (live)" + (" + job page" if r["ats"] == "rippling" else "")),
    })

roles_df = pd.DataFrame(rows).sort_values(["Meets all hard criteria", "Score"], ascending=[False, False])
roles_df.insert(0, "Rank", range(1, len(roles_df) + 1))

# Company sheet: every company on the run list plus the speedrun backlog.
probe = json.load(open(data_path("boards", "probe_results.json")))
company_rows = []
for c in all_companies:
    name = c["company"]
    prof = profiles[name]
    boards = [b for b in probe.get(name, []) if (name, b["ats"], b["slug"]) not in WRONG_BOARDS]
    wrong = [f"{b['ats']}/{b['slug']}: {WRONG_BOARDS[(name, b['ats'], b['slug'])]}"
             for b in probe.get(name, []) if (name, b["ats"], b["slug"]) in WRONG_BOARDS]
    company_roles = roles_df[roles_df["Company"] == name]
    facts = FACTS.get(name, {})
    if boards:
        status = "Board read"
    elif name in NOT_REACHED:
        status = "Not reached"
    else:
        status = "Not reached"
    notes = []
    if name in PRIVATE_NOTES:
        notes.append(PRIVATE_NOTES[name])
    if name in NOT_REACHED:
        notes.append(NOT_REACHED[name])
    if wrong:
        notes.append("Rejected board(s): " + " | ".join(wrong))
    company_rows.append({
        "Company": name,
        "List": c["list"],
        "Group": c["group"],
        "Board status": status,
        "Board(s)": ", ".join(f"{b['ats']}/{b['slug']}" for b in boards),
        "Open postings": open_counts.get(name, 0),
        "Target roles (Boston/remote US, any age)": len(company_roles),
        "Target roles within 7 days": int((company_roles["Age (days)"].fillna(999) <= 7).sum()),
        "Best score": company_roles["Score"].max() if len(company_roles) else None,
        "What they build": prof["what_they_build"],
        "Sector": prof["sector"],
        "Headcount": prof["headcount"],
        "Stage": prof["stage"],
        "Stage in A-D": {True: "Yes", False: "No (flag)", None: "Unknown"}[prof["stage_in_a_to_d"]],
        "Funding as shown in source list (unverified)": c["funding_as_shown"],
        "Investors": prof["investors"],
        "Investors source": prof["investors_source"],
        "Top-10 investor firms present": facts.get("top10_firms_present", ""),
        "Stack (live postings)": prof["stack_live"],
        "Stack basis": prof["stack_live_basis"],
        "Stack (shortlist Oct 2026)": prof["stack_shortlist"],
        "Customers": prof["customers"],
        "Location detail": prof["location_detail"],
        "Boston presence": prof["boston_presence"],
        "Data team (shortlist)": prof["data_team"],
        "Possible first data hire (shortlist)": prof["possible_first_data_hire"],
        "Layoffs": prof["layoffs"],
        "Glassdoor": prof["glassdoor"],
        "Worth knowing": prof["worth_knowing"],
        "Watch-outs": prof["watch_outs"],
        "Identity note": prof["identity_note"],
        "Source list flag (info only)": c["run_list_flag"],
        "In target_companies.xlsx (info only)": c["in_target_companies"],
        "Shortlist rank (Oct 2026)": c["shortlist_rank"],
        "Careers page": prof["careers_page"],
        "LinkedIn search (past week)": linkedin_search(name),
        "Check on LinkedIn (board not read)": "Yes" if status == "Not reached" else "",
        "Notes": " ".join(notes),
        "Sources": prof["sources"],
    })
companies_df = pd.DataFrame(company_rows).sort_values(
    ["Target roles within 7 days", "Best score"], ascending=[False, False], na_position="last")

gaps = [
    ("Result", "No posting met all hard criteria (target role, senior+, Boston or remote US, posted within 7 days). "
               "The only target role posted in the window (AcuityMD Data Engineer) asks for 1-2 years and pays $112,861-$159,000. "
               "Its format (req number, email-only applications) looks like a labor-certification ad; that is an inference from the text."),
    ("Investors", TOP10_NOTE),
    ("Investors", "Ranks 11-50 of the Strebulaev-Jackson list are not available. Investor points are 0 for every role."),
    ("Hiring trend", "Scored as a proxy from current open postings on the company board. Weekly collection will build real history."),
    ("Glassdoor", "No Glassdoor page was read directly. Ratings come from search snippets or aggregators and are marked as such."),
    ("Boards not reached", f"{len(NOT_REACHED)} companies: " + ", ".join(NOT_REACHED) + ". See Companies sheet notes."),
    ("Board identity", "Odyssey (K-12 education savings) and Augustus (banking) boards matched by name; not confirmed to be the a16z speedrun companies. Neither has a target role."),
    ("Posting dates", "Greenhouse first_published, Ashby publishedAt, Lever createdAt, Breezy published_date, Rippling createdOn. Reposted jobs may show a newer date than the original."),
    ("Role filter", "Titles matched: analytics engineer, data engineer, data platform / data infrastructure, and software/backend/platform engineer or MTS with 'data' in the title. "
                    "Titles like 'Engineering Manager, Data Streaming' (Horizon3.ai, 26 days) and 'Research Engineer - Pre-training Data' (Prime Intellect, 33 days) were not counted."),
    ("Company lists", "Run list 62 rows (handoff said 66) + a16z speedrun backlog 22 + Startup Shortlist 81 new (6 overlap) "
                      "+ 18 shortlist industry drops, now flag-only (7AI and Tailscale overlap). Total 183."),
    ("Profiles", "Company profiles merge: facts verified this run, helper-agent web research 2026-11-19, and the Startup Shortlist (Oct 2026). "
                 "Each field says its source. Not researched (search limit hit): Doppel, Rhino Federated Computing, Memcyco, SOC Prime, "
                 "Push Security, TRM Labs. Augustus partly done (identity unclear). Agent research did not search Glassdoor for most companies."),
    ("Identity", "Unconfirmed matches: Odyssey (withodyssey.com, a16z-backed but speedrun link unconfirmed), Augustus, Simile, Unconventional AI, "
                 "VIA (Via Science, fairly confident), Runway (one source says runway.com was sold / company became CFO.ai), Jump (talent-pool board only)."),
]
gaps.append(("Investor boards", "Getro boards (17 firms) were searched for analytics engineer / data engineer / data platform, filtered to remote US and Boston; "
                                 "no search hit the 20-result limit inside 7 days. Consider boards (14 firms, incl. a16z, Sequoia, Lightspeed) load jobs by script "
                                 "and were not read; links are on the Investor boards sheet. 23 firms had no board at the usual addresses."))
gaps.append(("Investor-board companies", "50 companies added from investor boards have no profile research yet (stage comes from the board). "
                                         "HotelTonight's posting is on careers.airbnb.com; its description was not read."))
gaps_df = pd.DataFrame(gaps, columns=["Area", "Gap"])

# Investor boards sheet: every firm on the 54-firm list and what happened to its board.
from vc_boards import FIRMS
vc_boards = json.load(open(data_path("boards", "vc_boards.json")))
board_rows = []
for firm, domain in FIRMS.items():
    b = vc_boards.get(firm)
    if b and b["platform"] == "getro":
        status = "Read automatically (Getro public page search)"
    elif b:
        status = "Not read: Consider board loads jobs by script. Check by hand."
    else:
        status = "No portfolio job board found at jobs./careers./talent./portfoliojobs. or /jobs"
    board_rows.append({"Firm": firm, "Firm domain (guess)": domain, "Board": (b or {}).get("url", ""),
                       "Platform": (b or {}).get("platform", ""), "Status": status,
                       "Source": "Strebulaev-Jackson top 10" if firm in ("Thrive Capital", "Dragoneer", "Factorial") else "Startup Shortlist premium list"})
boards_df = pd.DataFrame(board_rows)

scoring = pd.DataFrame([
    ("Pay", 30, f"Range bottom >= {PAY_TEXT}: 30. Range spans {PAY_TEXT}: 20. Top below {PAY_TEXT} or unposted: 0 (unposted flagged)."),
    ("Investors", 20, "Strebulaev-Jackson ranks 1-10 = 12 each, capped at 20, only for firms with a Boston office (scoring only; discovery uses all firms). Ranks 11-50 unavailable (fallback approved)."),
    ("Role fit", 25, "Title (analytics engineer 15, data engineer 12, data platform 9, SWE on data platform 6) "
                     "+ seniority (senior+ 5, not stated 4, junior 0) + location (Boston or remote US 5, remote country unclear 2)."),
    ("Recency", 25, "Posted 1 day or less 25, 3 days or less 20, 7 days or less 15, then a straight line down to 3 at 90 days. Older than 90 days 0."),
    ("Hiring proxy", 15, "Open postings on board: 50+ = 15, 20-49 = 10, 5-19 = 5, under 5 = 0."),
    ("TF-IDF", 10, "Cosine similarity to resume (ae for analytics engineer roles, de otherwise), scaled so the best match = 10."),
    ("Layoffs", "-20 / -10", "Layoffs in last 12 months -20, 12-24 months -10."),
    ("Hard criteria", "", f"Target title, Boston or remote US, posted within 7 days, not a junior title, pay top >= {PAY_TEXT} or unposted (flagged). Senior-or-above dropped 2026-11-19."),
    ("Near misses", "", "A role that fails exactly one hard criterion by a small margin: posted 8 to 30 days ago, or pay topping out within 10% of the pay floor. The Near misses sheet and the page list each with the one thing that missed."),
    ("Flags only", "", "Stage outside Series A-D, industry, Glassdoor under 3.5, source-list screen reason, private notes from config.json, asks 3 years experience or less."),
], columns=["Component", "Points", "Rule"])

with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
    roles_df.to_excel(writer, sheet_name="Roles", index=False)
    near_df = roles_df[roles_df["Near miss: missed only on"] != ""].sort_values("Score", ascending=False)
    near_df.to_excel(writer, sheet_name="Near misses", index=False)
    companies_df.to_excel(writer, sheet_name="Companies", index=False)
    boards_df.to_excel(writer, sheet_name="Investor boards", index=False)
    gaps_df.to_excel(writer, sheet_name="Coverage gaps", index=False)
    scoring.to_excel(writer, sheet_name="Scoring", index=False)
    for sheet in writer.sheets.values():
        sheet.freeze_panes = "B2"
        for col in sheet.columns:
            width = max(len(str(cell.value or "")) for cell in col[:50])
            sheet.column_dimensions[col[0].column_letter].width = min(max(width, 8), 60)

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump({"run_date": "2026-11-19",
               "roles": json.loads(roles_df.to_json(orient="records")),
               "companies": json.loads(companies_df.to_json(orient="records"))}, f, indent=1, ensure_ascii=False)

print("wrote", OUTPUT, "and", OUTPUT_JSON)
print(roles_df[["Rank", "Score", "Meets all hard criteria", "Company", "Title", "Age (days)", "Pay high", "Why not"]].to_string(index=False))
