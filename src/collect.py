# Pull every posting from each board found by probe_ats.py and save one flat list to postings.json.
# Each posting keeps its source URL and the date field it came from.
import gzip
import html
import json
import re
from datetime import datetime, timezone
import requests

from settings import COLLECT_DAY, data_path, run_path

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

if __name__ == "__main__":
    probe = json.load(open(data_path("boards", "probe_results.json")))
    postings = []
    errors = []
    for company, boards in probe.items():
        for b in boards:
            try:
                jobs = FETCHERS[b["ats"]](b["slug"])
            except Exception as e:
                errors.append({"company": company, "ats": b["ats"], "slug": b["slug"], "error": str(e)})
                continue
            for j in jobs:
                j.update({"company": company, "ats": b["ats"], "slug": b["slug"]})
                postings.append(j)
            print(company, b["ats"], b["slug"], len(jobs), flush=True)
    with gzip.open(run_path("postings.json.gz", COLLECT_DAY), "wt", encoding="utf-8") as f:
        json.dump(postings, f)
    json.dump(errors, open(run_path("collect_errors.json", COLLECT_DAY), "w"), indent=1)
    print("total postings", len(postings), "errors", len(errors))
