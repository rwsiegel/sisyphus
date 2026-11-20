# Try to find each company's public job board on Greenhouse, Lever, Ashby, Workable, SmartRecruiters.
# Writes probe_results.json: company -> list of boards that answered with jobs.
import json
import re
import requests
from companies import load_companies, ats_slug_from_url
from settings import data_path

HEADERS = {"User-Agent": "jobhunt-collector/0.1"}


def slug_guesses(company, website, careers_hint=""):
    name = company.lower()
    name = re.sub(r"\(.*?\)", "", name)                          # "datahub (acryl data)" -> "datahub"
    name = re.sub(r",? inc\.?$", "", name).strip()
    guesses = []
    hint = ats_slug_from_url(careers_hint)
    if hint:
        guesses.append(hint[1])                                   # slug from the shortlist's careers link
    if name.endswith(" ai"):
        guesses.append(re.sub(r"[^a-z0-9]", "", name[:-3]))       # "altana ai" -> "altana"
    guesses.append(re.sub(r"[^a-z0-9]", "", name))              # "zero hash" -> "zerohash"
    guesses.append(re.sub(r"[^a-z0-9]+", "-", name).strip("-"))  # "zero hash" -> "zero-hash"
    if website:
        guesses.append(website.split(".")[0].lower())             # "get-carrot.com" -> "get-carrot"
    first_word = re.sub(r"[^a-z0-9]", "", name.split()[0])
    guesses.append(first_word)
    # drop duplicates, keep order
    result = []
    for g in guesses:
        if g and g not in result:
            result.append(g)
    return result


def try_get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def probe(slug):
    found = []
    data = try_get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    if data and data.get("jobs"):
        found.append({"ats": "greenhouse", "slug": slug, "job_count": len(data["jobs"])})
    data = try_get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if isinstance(data, list) and data:
        found.append({"ats": "lever", "slug": slug, "job_count": len(data)})
    data = try_get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if data and data.get("jobs"):
        found.append({"ats": "ashby", "slug": slug, "job_count": len(data["jobs"])})
    data = try_get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    if data and data.get("jobs"):
        found.append({"ats": "workable", "slug": slug, "job_count": len(data["jobs"])})
    data = try_get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings")
    if data and data.get("totalFound"):
        found.append({"ats": "smartrecruiters", "slug": slug, "job_count": data["totalFound"]})
    return found


if __name__ == "__main__":
    # Only probe companies not already in probe_results.json, then merge.
    try:
        results = json.load(open(data_path("boards", "probe_results.json")))
    except FileNotFoundError:
        results = {}
    for c in load_companies():
        if c["company"] in results:
            continue
        boards = []
        hint = ats_slug_from_url(c["careers_hint"])
        if c["list"].startswith("Investor boards"):
            # Name guesses ("One", "Moon", "Radar") hit other companies; use only the job link's own board.
            guesses = [hint[1]] if hint else []
        else:
            guesses = slug_guesses(c["company"], c["website"], c["careers_hint"])
        for slug in guesses:
            boards += probe(slug)
        if hint and hint[0] in ("rippling", "bamboohr") and not boards:
            boards.append({"ats": hint[0], "slug": hint[1], "job_count": None})
        results[c["company"]] = boards
        print(c["company"], "->", [(b["ats"], b["slug"], b["job_count"]) for b in boards], flush=True)
        with open(data_path("boards", "probe_results.json"), "w") as f:  # save after each company so a stop loses nothing
            json.dump(results, f, indent=2)
