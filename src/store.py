# Where collected postings live.
#
# Daily collection keeps only the CURRENT postings, one file per job board, plus two small records:
#   data/current/postings/<ats>__<slug>.jsonl   one posting per line, sorted by url, so a day's change is a small git diff
#   data/state/first_seen.json                   posting key -> the first day it was seen
#   data/changes/<date>.json                     target roles that appeared or disappeared that day
# Older runs (before 2026-11-21) saved full snapshots at data/runs/<date>/postings.json.gz; those still load.
import glob
import gzip
import json
import os

from settings import DATA_DIR, data_path, run_path


def posting_key(p):
    return f"{p['ats']}|{p['slug']}|{p['url']}"


def board_path(ats, slug):
    safe = f"{ats}__{slug}".replace("/", "_").replace("\\", "_")
    return data_path("current", "postings", safe + ".jsonl")


def read_board(ats, slug):
    path = board_path(ats, slug)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_board(ats, slug, postings):
    """Write one board's postings. Returns True if the file changed, False if it was already identical."""
    lines = [json.dumps(p, sort_keys=True, ensure_ascii=False) for p in sorted(postings, key=lambda p: p["url"])]
    text = "\n".join(lines) + ("\n" if lines else "")
    path = board_path(ats, slug)
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() == text:
                return False
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return True


def load_current_postings():
    postings = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "current", "postings", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            postings.extend(json.loads(line) for line in f if line.strip())
    return postings


def load_postings(run_day):
    """Postings for scoring: a legacy full snapshot if that run has one, otherwise the current postings."""
    legacy = run_path("postings.json.gz", run_day)
    if os.path.exists(legacy):
        with gzip.open(legacy, "rt", encoding="utf-8") as f:
            return json.load(f)
    return load_current_postings()


def first_seen_path():
    return data_path("state", "first_seen.json")


def load_first_seen():
    path = first_seen_path()
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_first_seen(first_seen):
    # indent=0 puts one entry per line, so git shows added postings as added lines.
    with open(first_seen_path(), "w", encoding="utf-8", newline="\n") as f:
        json.dump(first_seen, f, sort_keys=True, indent=0, ensure_ascii=False)


def changes_path(day):
    return data_path("changes", f"{day}.json")


def load_changes(day):
    path = changes_path(day)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"date": str(day), "new": [], "closed": [], "boards_kept": []}
