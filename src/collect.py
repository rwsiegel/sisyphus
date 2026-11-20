# Pull every posting from each board found by probe_ats.py, once a day.
# Only the current postings are kept (see store.py), with the first day each was seen and a small
# log of target roles that appeared or disappeared. Each posting keeps its source URL and date field.
import gzip
import html
import json
import re
from datetime import datetime, timezone
import requests

from filters import role_type
from settings import COLLECT_DAY, data_path, run_path
from store import (changes_path, load_changes, load_first_seen, posting_key, read_board,
                   save_first_seen, write_board)

HEADERS = {"User-Agent": "jobhunt-collector/0.1"}


def strip_html(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def greenhouse(slug):
    board = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}")
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    out = []
    for j in data["jobs"]:
        posted = j.get("first_published")
        date_field = "first_published"
        if not posted:
            posted = j.get("updated_at")
            date_field = "updated_at (no first_published)"
        out.append({
            "board_name": board.get("name", ""),
            "title": j["title"],
            "location": (j.get("location") or {}).get("name", ""),
            "workplace": "",
            "posted": posted,
            "date_field": date_field,
            "url": j["absolute_url"],
            "pay_field": "",
            "text": strip_html(j.get("content", "")),
        })
    return out


def lever(slug):
    data = get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    out = []
    for j in data:
        pay = ""
        sr = j.get("salaryRange")
        if sr:
            pay = f"{sr.get('min')}-{sr.get('max')} {sr.get('currency')} {sr.get('interval')}"
        lists_text = " ".join(strip_html(l.get("content", "")) for l in j.get("lists", []))
        out.append({
            "board_name": "",
            "title": j["text"],
            "location": (j.get("categories") or {}).get("location", ""),
            "workplace": j.get("workplaceType", ""),
            "posted": datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc).isoformat(),
            "date_field": "createdAt",
            "url": j["hostedUrl"],
            "pay_field": pay,
            "text": (j.get("descriptionPlain", "") + " " + lists_text + " " + j.get("additionalPlain", "")).strip(),
        })
    return out


def ashby(slug):
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true")
    out = []
    for j in data["jobs"]:
        comp = j.get("compensation") or {}
        location = j.get("location", "")
        secondary = [s.get("location", "") for s in j.get("secondaryLocations", [])]
        if secondary:
            location = location + "; " + "; ".join(secondary)
        out.append({
            "board_name": "",
            "title": j["title"],
            "location": location,
            "workplace": (j.get("workplaceType") or "") + (" isRemote" if j.get("isRemote") else ""),
            "posted": j.get("publishedAt"),
            "date_field": "publishedAt",
            "url": j["jobUrl"],
            "pay_field": comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary") or "",
            "text": j.get("descriptionPlain", ""),
        })
    return out


def workable(slug):
    data = get_json(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    out = []
    for j in data["jobs"]:
        out.append({
            "board_name": data.get("name", ""),
            "title": j["title"],
            "location": f"{j.get('city', '')}, {j.get('state', '')}, {j.get('country', '')}",
            "workplace": "remote" if j.get("telecommuting") else "",
            "posted": j.get("published_on"),
            "date_field": "published_on",
            "url": j["url"],
            "pay_field": "",
            "text": "",
        })
    return out


def smartrecruiters(slug):
    data = get_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings")
    out = []
    for j in data["content"]:
        loc = j.get("location") or {}
        out.append({
            "board_name": (j.get("company") or {}).get("name", ""),
            "title": j["name"],
            "location": f"{loc.get('city', '')}, {loc.get('region', '')}, {loc.get('country', '')}",
            "workplace": "remote" if loc.get("remote") else "",
            "posted": j.get("releasedDate"),
            "date_field": "releasedDate",
            "url": f"https://jobs.smartrecruiters.com/{slug}/{j['id']}",
            "pay_field": "",
            "text": "",
        })
    return out


def breezy(slug):
    data = get_json(f"https://{slug}.breezy.hr/json")
    out = []
    for j in data:
        loc = j.get("location") or {}
        out.append({
            "board_name": (j.get("company") or {}).get("name", ""),
            "title": j["name"],
            "location": loc.get("name", ""),
            "workplace": "remote" if loc.get("is_remote") else "",
            "posted": j.get("published_date"),
            "date_field": "published_date",
            "url": j["url"],
            "pay_field": j.get("salary", ""),
            "text": "",
        })
    return out


def rippling(slug):
    # The list API has no date or pay. Those are read from each job page's embedded data.
    out = []
    page = 0
    while True:
        data = get_json(f"https://ats.rippling.com/api/v2/board/{slug}/jobs?page={page}")
        for j in data["items"]:
            out.append({
                "board_name": "",
                "title": j["name"],
                "location": "; ".join(l["name"] for l in j["locations"]),
                "workplace": "; ".join(l["workplaceType"] for l in j["locations"]),
                "posted": None,
                "date_field": "createdOn (job page)",
                "url": j["url"],
                "pay_field": "",
                "text": "",
            })
        page += 1
        if page >= data["totalPages"]:
            break
    # Same job can be listed once per location; keep one row per URL.
    unique = {}
    for j in out:
        if j["url"] in unique:
            unique[j["url"]]["location"] += "; " + j["location"]
            unique[j["url"]]["workplace"] += "; " + j["workplace"]
        else:
            unique[j["url"]] = j
    for j in unique.values():
        page_html = requests.get(j["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page_html, re.S)
        if not m:
            continue
        api = json.loads(m.group(1))["props"]["pageProps"].get("apiData", {})
        post = api.get("jobPost", {})
        j["posted"] = post.get("createdOn")
        ranges = api.get("payRangeDetails") or []
        j["pay_field"] = "; ".join(f"{r['rangeStart']}-{r['rangeEnd']} {r['currency']} per {r['frequency']} ({r['location']})" for r in ranges)
        j["text"] = strip_html(str(post.get("description", "")))
    return list(unique.values())


def bamboohr(slug):
    # The list has no date or description; each job's detail call has both.
    data = get_json(f"https://{slug}.bamboohr.com/careers/list")
    out = []
    for j in data["result"]:
        detail = get_json(f"https://{slug}.bamboohr.com/careers/{j['id']}/detail")["result"]["jobOpening"]
        loc = j.get("location") or {}
        ats_loc = j.get("atsLocation") or {}
        city = loc.get("city") or ats_loc.get("city") or ""
        state = loc.get("state") or ats_loc.get("state") or ""
        out.append({
            "board_name": "",
            "title": j["jobOpeningName"],
            "location": f"{city}, {state}".strip(", "),
            "workplace": "remote" if detail.get("isRemote") else "",
            "posted": detail.get("datePosted"),
            "date_field": "datePosted",
            "url": f"https://{slug}.bamboohr.com/careers/{j['id']}",
            "pay_field": detail.get("compensation") or "",
            "text": strip_html(detail.get("description", "")),
        })
    return out


FETCHERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby,
            "workable": workable, "smartrecruiters": smartrecruiters,
            "breezy": breezy, "rippling": rippling, "bamboohr": bamboohr}

def brief(p):
    """The few fields the change log keeps about a posting."""
    return {"company": p["company"], "title": p["title"], "location": p["location"], "url": p["url"],
            "posted": p["posted"], "pay": p["pay_field"]}


if __name__ == "__main__":
    probe = json.load(open(data_path("boards", "probe_results.json")))
    today = COLLECT_DAY.isoformat()
    first_seen = load_first_seen()
    changes = load_changes(COLLECT_DAY)   # a second run on the same day adds to the first
    logged_new = {x["url"] for x in changes["new"]}
    logged_closed = {x["url"] for x in changes["closed"]}
    errors = []
    done_boards = set()
    total = 0
    boards_changed = 0
    for company, boards in probe.items():
        for b in boards:
            board = (b["ats"], b["slug"])
            if board in done_boards:
                continue   # the same board can be listed under two company names
            done_boards.add(board)
            try:
                jobs = FETCHERS[b["ats"]](b["slug"])
            except Exception as e:
                errors.append({"company": company, "ats": b["ats"], "slug": b["slug"], "error": str(e)})
                continue   # a failed fetch is not a closed job: the old postings stay as they were
            previous = read_board(*board)
            if not jobs and previous:
                # An empty answer from a board that had jobs is more likely an outage than every job closing.
                errors.append({"company": company, "ats": b["ats"], "slug": b["slug"],
                               "error": "empty answer; kept the previous postings"})
                continue
            for j in jobs:
                j.update({"company": company, "ats": b["ats"], "slug": b["slug"]})
            now_keys = {posting_key(j) for j in jobs}
            for j in jobs:
                key = posting_key(j)
                if key not in first_seen:
                    first_seen[key] = today
                    if role_type(j["title"]) and j["url"] not in logged_new:
                        changes["new"].append(brief(j))
            for old in previous:
                if posting_key(old) not in now_keys and role_type(old["title"]) and old["url"] not in logged_closed:
                    changes["closed"].append({**brief(old), "first_seen": first_seen.get(posting_key(old), "")})
            if write_board(b["ats"], b["slug"], jobs):
                boards_changed += 1
            total += len(jobs)
            print(company, b["ats"], b["slug"], len(jobs), flush=True)
    save_first_seen(first_seen)
    changes["boards_kept"] = sorted({f"{e['ats']}/{e['slug']}" for e in errors})
    with open(changes_path(COLLECT_DAY), "w", encoding="utf-8") as f:
        json.dump(changes, f, indent=1, sort_keys=True, ensure_ascii=False)
    json.dump(errors, open(run_path("collect_errors.json", COLLECT_DAY), "w"), indent=1)
    print(f"total postings {total} | boards changed {boards_changed} | errors {len(errors)}")
    print(f"target roles today: {len(changes['new'])} new, {len(changes['closed'])} closed")
