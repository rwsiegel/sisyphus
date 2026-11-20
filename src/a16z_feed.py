# Read a16z's public jobs page for data roles near Boston. One run = a few ordinary page requests.
#
# jobs.a16z.com puts the first 25 results of any search into the page as a standard list. Each result is
# only "Title at Company": no link, pay, location or date. So this finds WHICH portfolio companies have
# data roles right now; the details come from each company's own job board (see probe_ats.py).
# The search filters live in the address, e.g. ?locations=metro:greater-boston&postedSince=P30D&q=data
import json
import re
import time
import urllib.parse
import urllib.request

from settings import COLLECT_DAY, run_path

HEADERS = {"User-Agent": "jobhunt-collector/0.1"}
BASE = "https://jobs.a16z.com/"
SEARCHES = [
    {"locations": "metro:greater-boston", "postedSince": "P30D", "q": "data"},
    {"locations": "metro:greater-boston", "postedSince": "P30D", "q": "analytics"},
]
PAGE_LIMIT = 25      # the page shows at most 25 results, so 25 means "there may be more"
PAUSE_SECONDS = 2    # be polite between requests


def read_results(params):
    url = BASE + "?" + urllib.parse.urlencode(params, safe=":")
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as response:
        page = response.read().decode("utf-8", "replace")
    names = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "ItemList":
            names = [item["name"] for item in data.get("itemListElement", [])]
    return url, names


def split_title_company(name):
    """'Staff Data Engineer  at Asimov' -> ('Staff Data Engineer', 'Asimov')."""
    name = " ".join(name.split())
    title, _, company = name.rpartition(" at ")
    return (title or name), company


if __name__ == "__main__":
    roles = {}
    searches = []
    for i, params in enumerate(SEARCHES):
        if i:
            time.sleep(PAUSE_SECONDS)
        url, names = read_results(params)
        searches.append({"url": url, "results": len(names), "may_be_more": len(names) >= PAGE_LIMIT})
        for name in names:
            title, company = split_title_company(name)
            roles[(company, title)] = {"company": company, "title": title, "search": params["q"]}
        print(f"q={params['q']}: {len(names)} results")
    out = {"date": COLLECT_DAY.isoformat(), "searches": searches,
           "roles": sorted(roles.values(), key=lambda r: (r["company"], r["title"]))}
    with open(run_path("a16z_feed.json", COLLECT_DAY), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"{len(roles)} distinct roles saved")
