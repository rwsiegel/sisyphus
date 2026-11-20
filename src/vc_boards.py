# Investor-first discovery, step 1: find each firm's public portfolio job board.
# Firm list = Startup Shortlist "premium" firms (51) + Strebulaev-Jackson top-10 firms missing from it (Thrive, Dragoneer, Factorial).
# Domains are starting guesses; a board only counts if the page itself confirms it (Getro network domain or Consider marker).
# Plain GET of public pages with an honest user agent. No private APIs.
import json
import re
import requests

from settings import data_path

HEADERS = {"User-Agent": "jobhunt-collector/0.1"}

FIRMS = {
    "8VC": "8vc.com", "Accel": "accel.com", "Amplify Partners": "amplifypartners.com", "Andreessen Horowitz": "a16z.com",
    "Bain Capital Ventures": "baincapitalventures.com", "Battery Ventures": "battery.com", "Benchmark": "benchmark.com",
    "Bessemer": "bvp.com", "Conviction": "conviction.com", "Costanoa": "costanoa.vc", "Crane": "crane.vc", "CRV": "crv.com",
    "Databricks Ventures": "databricks.com", "DST Global": "dst.global", "Emergence": "emcap.com", "Felicis": "felicis.com",
    "FirstMark": "firstmark.com", "Flybridge": "flybridge.com", "Foundation Capital": "foundationcap.com",
    "Founders Fund": "foundersfund.com", "General Catalyst": "generalcatalyst.com", "GIC": "gic.com.sg", "GV": "gv.com",
    "Greenoaks": "greenoaks.com", "Greylock": "greylock.com", "ICONIQ": "iconiqgrowth.com", "Index Ventures": "indexventures.com",
    "Insight Partners": "insightpartners.com", "IVP": "ivp.com", "Khosla Ventures": "khoslaventures.com",
    "Kleiner Perkins": "kleinerperkins.com", "Lightspeed": "lsvp.com", "Madrona": "madrona.com", "Menlo Ventures": "menlovc.com",
    "NEA": "nea.com", "Norwest": "nvp.com", "NVIDIA (NVentures)": "nvidia.com", "Nyca": "nyca.com", "QED": "qedinvestors.com",
    "Redpoint": "redpoint.com", "Salesforce Ventures": "salesforceventures.com", "Sequoia": "sequoiacap.com",
    "SignalFire": "signalfire.com", "Snowflake Ventures": "snowflake.com", "Spark Capital": "sparkcapital.com",
    "SV Angel": "svangel.com", "TCV": "tcv.com", "Theory Ventures": "theory.ventures", "Two Sigma Ventures": "twosigmaventures.com",
    "Underscore VC": "underscore.vc", "Y Combinator": "ycombinator.com",
    "Thrive Capital": "thrivecap.com", "Dragoneer": "dragoneer.com", "Factorial": "factorialfunds.com",
}


def board_type(url, firm_domain):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    text = r.text
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
    if m and "getro" in text:
        try:
            network = json.loads(m.group(1))["props"]["pageProps"]["network"]
        except (KeyError, json.JSONDecodeError):
            return None
        if firm_domain.split(".")[0] in (network.get("domain") or "") + (network.get("label") or ""):
            return {"platform": "getro", "url": r.url.split("?")[0], "network_id": network.get("id")}
    if "consider.com" in text:
        return {"platform": "consider", "url": r.url.split("?")[0]}
    return None


if __name__ == "__main__":
    results = {}
    for firm, domain in FIRMS.items():
        found = None
        for url in [f"https://jobs.{domain}/jobs", f"https://careers.{domain}/jobs", f"https://talent.{domain}/jobs",
                    f"https://portfoliojobs.{domain}/jobs", f"https://{domain}/jobs"]:
            found = board_type(url, domain)
            if found:
                break
        results[firm] = found
        print(f"{firm:24} {found}", flush=True)
    json.dump(results, open(data_path("boards", "vc_boards.json"), "w"), indent=1)
