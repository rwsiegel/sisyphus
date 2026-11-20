# The list of companies to run: 62 rows from the run list plus the a16z speedrun backlog.
import pandas as pd

from settings import RUN_LIST, SHORTLIST_HTML, run_path

SPEEDRUN = [
    "Slash", "Simile", "Sequen", "Applied Compute", "Prime Intellect", "The Bot Company",
    "River AI", "Goodfire", "Gimlet Labs", "Ricursive", "General Intuition", "Emerald AI",
    "Venice.ai", "Nous Research", "Walden Robotics", "Harmonic", "Odyssey", "Mirendil",
    "Augustus", "NewLimit", "Hubble Network", "Unconventional AI",
]




def read_shortlist():
    """Return (ranked companies, dropped companies) from the Startup Shortlist page's embedded data."""
    import json
    import re
    page = open(SHORTLIST_HTML, encoding="utf-8", errors="replace").read()
    script = re.search(r"<script[^>]*>(.*?)</script>", page, re.S).group(1)
    data = json.loads(re.search(r"const DATA = (\[.*?\]);\s*\n", script, re.S).group(1))
    drops = json.loads(re.search(r"const DROPS = (.*?);\s*\n", script, re.S).group(1))
    return data, drops


def ats_slug_from_url(url):
    """Pull a board slug out of a careers URL, e.g. https://jobs.ashbyhq.com/workos -> ('ashby', 'workos')."""
    import re
    patterns = [
        ("ashby", r"jobs\.ashbyhq\.com/([^/?#\s]+)"),
        ("greenhouse", r"greenhouse\.io/([^/?#\s]+)"),
        ("lever", r"jobs\.lever\.co/([^/?#\s]+)"),
        ("bamboohr", r"([a-z0-9-]+)\.bamboohr\.com"),
        ("rippling", r"ats\.rippling\.com/([^/?#\s]+)"),
        ("workable", r"apply\.workable\.com/([^/?#\s]+)"),
    ]
    for ats, pattern in patterns:
        m = re.search(pattern, url or "")
        if m and m.group(1) not in ("embed", "unusual"):  # jobs.lever.co/unusual is a VC portfolio board
            return ats, m.group(1)
    return None


def load_shortlist_companies(existing_names):
    data, drops = read_shortlist()
    rows = []
    for d in data:
        if d["name"].lower() in existing_names:
            continue
        website = d.get("website") or ""
        domain = re.sub(r"^https?://(www\.)?", "", website.split(" ")[0]).split("/")[0]
        flag = "shortlist: below top-50 cut (info only)" if d["rank"] > 50 else ""
        rows.append({
            "company": d["name"], "website": domain, "list": "Startup Shortlist (Oct 2026)", "group": d["sector"],
            "run_list_flag": flag, "in_target_companies": "",
            "funding_as_shown": f"{d['stage']}, {d['last_round']} ({d['date']}) per shortlist, Oct 2026",
            "excel_row": "", "careers_hint": d.get("careers", ""), "shortlist_rank": d["rank"],
        })
    for name, reason in drops:
        if name.lower() in existing_names or "Excluded" not in reason:
            continue  # below-cut drops are already in DATA
        rows.append({
            "company": name, "website": "", "list": "Startup Shortlist drops (Oct 2026)", "group": "",
            "run_list_flag": "shortlist " + reason.lower() + " (flag only now)", "in_target_companies": "",
            "funding_as_shown": "", "excel_row": "", "careers_hint": "", "shortlist_rank": "",
        })
    return rows


def load_investor_board_companies(existing_names):
    """Companies with a Boston / remote-US data role on a Getro investor portfolio board (2026-11-19)."""
    import json
    try:
        roles = json.load(open(run_path("vc_roles.json")))["roles"]
    except FileNotFoundError:
        return []
    by_company = {}
    for r in roles:
        if r["location_fit"] not in ("Boston", "Remote US"):
            continue
        by_company.setdefault(r["company"], []).append(r)
    rows = []
    for name, company_roles in by_company.items():
        if name.lower() in existing_names:
            continue
        firms = sorted({f for r in company_roles for f in r["firms"]})
        rows.append({
            "company": name, "website": "", "list": "Investor boards (Getro, 2026-11-19)", "group": "",
            "run_list_flag": "", "in_target_companies": "",
            "funding_as_shown": f"{company_roles[0]['stage']} per Getro investor board",
            "excel_row": "", "careers_hint": company_roles[0]["url"] or "", "shortlist_rank": "",
            "investor_boards": ", ".join(firms),
        })
    return rows


import re


def load_companies():
    df = pd.read_excel(RUN_LIST, "Run List")
    rows = []
    for i, r in df.iterrows():
        rows.append({
            "company": str(r["Company"]).strip(),
            "website": r["Website"] if pd.notna(r["Website"]) else "",
            "list": "Run list",
            "group": r["Group (source)"],
            "run_list_flag": r["Screen reason / note"] if pd.notna(r["Screen reason / note"]) else "",
            "in_target_companies": r["Already in target_companies.xlsx"] if pd.notna(r["Already in target_companies.xlsx"]) else "",
            "funding_as_shown": r["Notes"] if pd.notna(r["Notes"]) else "",
            "excel_row": i + 2,
        })
    for name in SPEEDRUN:
        rows.append({
            "company": name, "website": "", "list": "a16z speedrun backlog", "group": "a16z speedrun",
            "run_list_flag": "", "in_target_companies": "", "funding_as_shown": "", "excel_row": "",
        })
    for r in rows:
        r.setdefault("careers_hint", "")
        r.setdefault("shortlist_rank", "")
    existing = {r["company"].lower() for r in rows}
    rows += load_shortlist_companies(existing)
    existing = {r["company"].lower() for r in rows}
    rows += load_investor_board_companies(existing)
    for r in rows:
        r.setdefault("investor_boards", "")
    return rows
