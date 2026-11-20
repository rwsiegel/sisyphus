# Build the interactive page from the scored run JSON (written by build_workbook.py).
# Two outputs, both single self-contained HTML files:
#   job_search_run_<date>.html       private: everything, including resume match and tracker notes
#   job_search_showcase_<date>.html  showcase: no resume-derived points, no tracker notes
import json
import os

from settings import OUTPUT_DIR, PAY_FLOOR, PRIVATE_NOTES, RUN_DAY, SITE_HOME_LABEL, SITE_HOME_URL
from vc_boards import FIRMS

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_JSON = os.path.join(OUTPUT_DIR, f"job_search_run_{RUN_DAY.isoformat()}.json")


def clean(value):
    return "" if value is None else str(value)


def is_private(text, showcase):
    """In the showcase, drop any text that mentions a tracker note or an application."""
    if not showcase:
        return False
    low = text.lower()
    return "already applied" in low or any(note.lower() in low for note in PRIVATE_NOTES.values())


PAY_TEXT = f"${PAY_FLOOR // 1000}K"


def hide_pay_floor(text, showcase):
    """The showcase never shows the owner's pay floor; it says "target pay" instead."""
    return text.replace(PAY_TEXT, "target pay") if showcase else text


def split_flags(text, showcase):
    parts = [hide_pay_floor(p.strip(), showcase) for p in clean(text).split(";") if p.strip()]
    return [p for p in parts if not is_private(p, showcase)]


def role_record(r, showcase):
    return {
        "company": r["Company"],
        "title": r["Title"],
        "type": r["Role type"],
        "level": r["Seniority"],
        "location": clean(r["Location"]),
        "where": r["Location fit"],
        "posted": clean(r["Posted"]),
        "age": r["Age (days)"],
        "pay_low": r["Pay low"],
        "pay_high": r["Pay high"],
        "pts": {
            "pay": r["Pts: pay (30)"],
            "fit": r["Pts: role fit (25)"],
            "recency": r["Pts: recency (25)"],
            "hire": r["Pts: hiring proxy (15)"],
            "invest": r["Pts: investors (20)"],
            "tfidf": 0 if showcase else r["Pts: TF-IDF (10)"],
        },
        "layoff_pen": -(r["Layoff penalty"] or 0),
        "loc_pen": -(r["Location penalty"] or 0),
        "years": r["Years experience asked"],
        "flags": split_flags(r["Flags"], showcase),
        "url": clean(r["Source page"]),
        "meets": r["Meets all hard criteria"] == "Yes",
        "near_miss": hide_pay_floor(clean(r["Near miss: missed only on"]), showcase),
        "why_not": hide_pay_floor(clean(r["Why not"]), showcase),
    }


def company_record(c, showcase):
    sources = [s.strip() for s in clean(c["Sources"]).split(" ; ") if s.strip().startswith("http")]
    stage_ok = {"Yes": True, "No (flag)": False}.get(c["Stage in A-D"])
    info_flag = clean(c["Source list flag (info only)"])
    return {
        "name": c["Company"],
        "group": clean(c["Group"]),
        "sector": clean(c["Sector"]),
        "build": clean(c["What they build"]),
        "headcount": clean(c["Headcount"]),
        "stage": clean(c["Stage"]),
        "stage_ok": stage_ok,
        "investors": clean(c["Investors"]),
        "stack": clean(c["Stack (live postings)"]) or clean(c["Stack (shortlist Oct 2026)"]),
        "customers": clean(c["Customers"]),
        "location": clean(c["Location detail"]),
        "boston": clean(c["Boston presence"]),
        "data_team": clean(c["Data team (shortlist)"]),
        "first_hire": clean(c["Possible first data hire (shortlist)"]),
        "layoffs": clean(c["Layoffs"]),
        "glassdoor": clean(c["Glassdoor"]),
        "worth": clean(c["Worth knowing"]),
        "watch": clean(c["Watch-outs"]),
        "identity": clean(c["Identity note"]),
        "info_flag": "" if is_private(info_flag, showcase) else info_flag,
        "careers": clean(c["Careers page"]),
        "linkedin": clean(c["LinkedIn search (past week)"]),
        "check_linkedin": c["Check on LinkedIn (board not read)"] == "Yes",
        "board_status": c["Board status"],
        "open_postings": c["Open postings"],
        "origin": c["List"],
        "sources": sources[:12],
    }


def build(showcase):
    data = json.load(open(SOURCE_JSON, encoding="utf-8"))
    page_data = {
        "run_date": RUN_DAY.isoformat(),
        "showcase": showcase,
        "premium": sorted({f.lower() for f in FIRMS} | {"andreessen", "a16z", "gv", "google ventures"}),
        "roles": [role_record(r, showcase) for r in data["roles"]],
        "companies": [company_record(c, showcase) for c in data["companies"]],
    }
    template = open(os.path.join(HERE, "page_template.html"), encoding="utf-8").read()
    # "</" inside JSON would end the script tag early.
    payload = json.dumps(page_data, ensure_ascii=False).replace("</", "<\\/")
    title = "Sisyphus" + ("" if showcase else " (private)")
    backlink = ""
    if showcase and SITE_HOME_URL:
        backlink = f'<p class="sub"><a href="{SITE_HOME_URL}">&larr; {SITE_HOME_LABEL}</a></p>'
    description = "An interactive tool that scores analytics and data engineering roles from public job boards. Change the weights and the ranking updates."
    html = (template.replace("__TITLE__", title).replace("__DESCRIPTION__", description)
            .replace("__BACKLINK__", backlink)
            .replace("__UPDATED_ISO__", RUN_DAY.isoformat())
            .replace("__UPDATED__", f"{RUN_DAY:%B} {RUN_DAY.day}, {RUN_DAY.year}")
            .replace("__PAY_FLOOR__", "target pay" if showcase else PAY_TEXT)
            .replace("__DATA__", payload))
    name = f"job_search_{'showcase' if showcase else 'run'}_{RUN_DAY.isoformat()}.html"
    path = os.path.join(OUTPUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", path, f"({os.path.getsize(path) // 1024} KB)")


if __name__ == "__main__":
    build(showcase=False)
    build(showcase=True)
