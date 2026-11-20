# Investor-first discovery, step 2: search each Getro portfolio board's public page for data roles.
# Reads the search results the page itself renders (newest first). Plain GET, honest user agent.
import base64
import json
import re
import time
from datetime import datetime, timezone

import requests

from filters import role_type, seniority
from settings import COLLECT_DAY, data_path, run_path

COLLECT_MOMENT = datetime(COLLECT_DAY.year, COLLECT_DAY.month, COLLECT_DAY.day, tzinfo=timezone.utc)
HEADERS = {"User-Agent": "jobhunt-collector/0.1"}
QUERIES = ["analytics engineer", "data engineer", "data platform"]
# Getro's shareable-link filters (base64 JSON in ?filter=). Without them each search shows only its first 20 jobs.
FILTERS = {
    "remote US": {"work_mode": ["remote"], "searchable_locations": ["United States"]},
    "Boston": {"searchable_locations": ["Boston, MA, USA"]},
}


def search_board(board_url, query, location_filter=None):
    params = {"q": query}
    if location_filter:
        params["filter"] = base64.b64encode(json.dumps(location_filter).encode()).decode()
    r = requests.get(board_url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    jobs = json.loads(m.group(1))["props"]["pageProps"]["initialState"]["jobs"]
    return jobs.get("total", 0), jobs.get("found", [])


def us_or_boston(job):
    places = " | ".join(job.get("searchableLocations") or []).lower()
    mode = (job.get("workMode") or "").lower()
    if "boston" in places or "massachusetts" in places:
        return "Boston"
    if mode == "remote" and "united states" in places:
        return "Remote US"
    if mode == "remote":
        return "Remote (country unclear)"
    return "No"


if __name__ == "__main__":
    boards = {firm: b for firm, b in json.load(open(data_path("boards", "vc_boards.json"))).items() if b and b["platform"] == "getro"}
    found = {}
    truncated = []
    for firm, b in boards.items():
        url = b["url"].replace("/companies", "/jobs")
        for q in QUERIES:
          for place, location_filter in FILTERS.items():
            try:
                total, jobs = search_board(url, q, location_filter)
            except Exception as e:
                print(firm, q, place, "ERROR", str(e)[:60])
                continue
            if total > len(jobs) and jobs:
                # Results are newest first after a few pinned "featured" jobs. If the oldest shown is
                # still inside 7 days, the week may be incomplete for this search.
                oldest_shown = min(datetime.fromtimestamp(j["createdAt"], timezone.utc) for j in jobs[-10:])
                if (COLLECT_MOMENT - oldest_shown).days <= 7:
                    truncated.append(f"{firm} '{q}' {place}: {len(jobs)} of {total} shown; oldest shown is within 7 days, week may be incomplete")
            for j in jobs:
                title_type = role_type(j["title"])
                if not title_type:
                    continue
                created = datetime.fromtimestamp(j["createdAt"], timezone.utc)
                key = (j["organization"]["name"], j["title"], j.get("url"))
                row = found.setdefault(key, {
                    "company": j["organization"]["name"], "title": j["title"], "role_type": title_type,
                    "level": seniority(j["title"]), "stage": j["organization"].get("stage"),
                    "created": created.date().isoformat(), "age_days": max(0, (COLLECT_MOMENT - created).days),
                    "work_mode": j.get("workMode"), "locations": "; ".join((j.get("searchableLocations") or [])[:6]),
                    "location_fit": us_or_boston(j),
                    "pay_min": (j.get("compensationAmountMinCents") or 0) / 100 or None,
                    "pay_max": (j.get("compensationAmountMaxCents") or 0) / 100 or None,
                    "url": j.get("url"), "firms": [],
                })
                if firm not in row["firms"]:
                    row["firms"].append(firm)
            time.sleep(0.5)  # be polite
        print(f"{firm:22} done", flush=True)
    rows = sorted(found.values(), key=lambda r: r["age_days"])
    json.dump({"roles": rows, "truncated": truncated}, open(run_path("vc_roles.json", COLLECT_DAY), "w"), indent=1)
    print("data roles found:", len(rows), "| truncated searches:", len(truncated))
