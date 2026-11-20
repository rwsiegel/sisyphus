# Local settings, read from config.json at the repo root.
# config.json is git-ignored: it holds personal paths and private notes. Start from config.example.json.
import json
import os
from datetime import date, datetime, timezone

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# config.json is needed for scoring only. Collection runs without it.
CONFIG = {}
config_path = os.path.join(REPO_DIR, "config.json")
if os.path.exists(config_path):
    with open(config_path, encoding="utf-8") as f:
        CONFIG = json.load(f)

# The jobhunt-data repo (collected public data only). Default: a sibling folder of this repo.
DATA_DIR = CONFIG.get("data_dir") or os.path.join(os.path.dirname(REPO_DIR), "jobhunt-data", "data")

def latest_run_day():
    """The newest dated folder in data/runs, or today if there is none yet."""
    runs_dir = os.path.join(DATA_DIR, "runs")
    days = []
    if os.path.isdir(runs_dir):
        for name in os.listdir(runs_dir):
            try:
                days.append(date.fromisoformat(name))
            except ValueError:
                pass
    return max(days) if days else date.today()


# Which collected run to score. In order: the JOBHUNT_RUN_DATE environment variable, a pinned
# run_date in config.json (rebuilds a past run), or the newest run folder.
RUN_DAY = date.fromisoformat(os.environ.get("JOBHUNT_RUN_DATE") or CONFIG.get("run_date") or latest_run_day().isoformat())
RUN_DATE = datetime(RUN_DAY.year, RUN_DAY.month, RUN_DAY.day, tzinfo=timezone.utc)

# Collection always files its output under today's date, even when config.json pins an older run_date for scoring.
COLLECT_DAY = date.today()

# Private local inputs. Never copied into either repo.
LIBRARY_DIR = CONFIG.get("library_dir", "")
RUN_LIST = CONFIG.get("run_list", "")
SHORTLIST_HTML = CONFIG.get("shortlist_html", "")
RESUME_DE = CONFIG.get("resume_de", "")
RESUME_AE = CONFIG.get("resume_ae", "")
OUTPUT_DIR = CONFIG.get("output_dir", "")
# Local copy of your website. The refresh puts the showcase page at <website_dir>/sisyphus/index.html.
WEBSITE_DIR = CONFIG.get("website_dir", "")
# Pay floor for the pay score and the hard criteria, in dollars. Set your own in config.json.
PAY_FLOOR = CONFIG.get("pay_floor", 150_000)
# Optional link back to your own site, shown at the top of the showcase page.
SITE_HOME_URL = CONFIG.get("site_home_url", "")
SITE_HOME_LABEL = CONFIG.get("site_home_label", "Home")
PRIVATE_NOTES = CONFIG.get("private_notes", {})  # e.g. {"Company": "already applied ..."}


def data_path(*parts):
    """Path inside the data repo; creates the folder if needed."""
    path = os.path.join(DATA_DIR, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def run_path(name, day=None):
    """Path for one run's file, e.g. data/runs/2026-11-19/postings.json.gz."""
    return data_path("runs", (day or RUN_DAY).isoformat(), name)
