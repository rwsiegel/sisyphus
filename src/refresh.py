# One command for the weekly refresh:  python src/refresh.py
#
# 1. Pulls the newest collected data (jobhunt-data repo).
# 2. Scores the newest run and writes the workbook and both pages (all local).
# 3. Copies the showcase page into your local website folder, if website_dir is set in config.json.
# 4. Prints what is new since the last refresh.
#
# It never uploads anything. Uploading the website folder stays your step.
import glob
import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta

from settings import CONFIG, DATA_DIR, OUTPUT_DIR, REPO_DIR, WEBSITE_DIR, latest_run_day

SRC = os.path.dirname(os.path.abspath(__file__))


def step(text):
    print("\n== " + text, flush=True)


def run(script, run_day):
    """Run another script in this folder, scoring the given run day."""
    env = dict(os.environ, JOBHUNT_RUN_DATE=run_day, PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, os.path.join(SRC, script)], env=env, cwd=REPO_DIR,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(result.stdout[-1500:])
        print(result.stderr[-1500:])
        sys.exit(f"{script} failed (exit {result.returncode})")
    return result.stdout


def recent_changes(run_day, days=7):
    """Target roles that appeared or closed in the last few days, from the daily change logs."""
    last = date.fromisoformat(run_day)
    new, closed = [], []
    for back in range(days):
        path = os.path.join(DATA_DIR, "changes", f"{last - timedelta(days=back)}.json")
        if os.path.exists(path):
            day_log = json.load(open(path, encoding="utf-8"))
            new.extend(day_log["new"])
            closed.extend(day_log["closed"])
    return new, closed


def previous_run_json(run_day):
    """The newest scored run before this one in the output folder, or None."""
    current = f"job_search_run_{run_day}.json"
    older = [p for p in glob.glob(os.path.join(OUTPUT_DIR, "job_search_run_*.json"))
             if os.path.basename(p) < current]
    return max(older) if older else None


def main():
    step("1. Pull the newest collected data")
    data_repo = os.path.dirname(DATA_DIR)
    pull = subprocess.run(["git", "-C", data_repo, "pull", "--ff-only"], capture_output=True, text=True)
    print((pull.stdout or pull.stderr).strip() or "done")
    if pull.returncode != 0:
        print("(pull failed; continuing with the data already on disk)")

    # A run_date pinned in config.json (or the environment) wins; otherwise the newest run folder.
    run_day = os.environ.get("JOBHUNT_RUN_DATE") or CONFIG.get("run_date") or latest_run_day().isoformat()
    print("Scoring the run from", run_day)

    step("2. Score and build the workbook")
    print(run("build_workbook.py", run_day).splitlines()[0])

    step("3. Build the pages")
    print(run("build_page.py", run_day).strip())

    step("4. Update the local website copy")
    showcase = os.path.join(OUTPUT_DIR, f"job_search_showcase_{run_day}.html")
    if WEBSITE_DIR:
        target = os.path.join(WEBSITE_DIR, "sisyphus", "index.html")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(showcase, target)
        print("copied the showcase page to", target)
    else:
        print("website_dir is not set in config.json, so nothing was copied. Showcase page:", showcase)

    step("5. What this refresh found")
    current = json.load(open(os.path.join(OUTPUT_DIR, f"job_search_run_{run_day}.json"), encoding="utf-8"))
    roles = current["roles"]
    meets = [r for r in roles if r["Meets all hard criteria"] == "Yes"]
    near = [r for r in roles if r["Near miss: missed only on"]]
    print(f"{len(roles)} roles, {len(meets)} meet every criterion, {len(near)} near misses")
    for r in meets:
        pay = f"${r['Pay high'] / 1000:.0f}K" if r["Pay high"] else "pay unposted"
        print(f"  MEETS  {r['Score']:5.1f}  {r['Company']}: {r['Title']} ({r['Age (days)']} days, {pay})")

    old_path = previous_run_json(run_day)
    if old_path:
        old = {(r["Company"], r["Title"]) for r in json.load(open(old_path, encoding="utf-8"))["roles"]}
        new = [r for r in roles if (r["Company"], r["Title"]) not in old]
        print(f"\nNew since the {os.path.basename(old_path)[15:25]} run: {len(new)} roles")
        for r in sorted(new, key=lambda r: -r["Score"])[:8]:
            print(f"  NEW    {r['Score']:5.1f}  {r['Company']}: {r['Title']}")
    else:
        print("\nNo earlier scored run to compare with.")

    new_roles, closed_roles = recent_changes(run_day)
    print(f"\nFrom the daily collection, last 7 days: {len(new_roles)} target roles appeared, {len(closed_roles)} closed")
    for r in closed_roles[:10]:
        print(f"  CLOSED {r['company']}: {r['title']} (first seen {r['first_seen'] or 'earlier'})")

    print("\nNext: upload", WEBSITE_DIR or "the showcase page", "to your site. The workbook and the private page stay on this PC.")


if __name__ == "__main__":
    main()
