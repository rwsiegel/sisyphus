# Sisyphus

A small Python tool that finds and ranks data and analytics engineering roles at startups.

Named for the myth: every Monday the boulder goes back to the bottom and the search starts over, so the tool is built to run every week without help.

It has two parts:

- **Collection** reads public job boards and investor portfolio job boards and saves the postings as plain files. It uses no personal data.
- **Scoring** runs on your own machine. It reads your resume in place, scores each open role, and writes a ranked Excel workbook and an interactive HTML page.

I built it for my own job search. The scripts are meant to be read and adapted, not installed.

## What it reads

All collection uses public endpoints with a plain, honest user agent and no logins:

| Source | How |
|---|---|
| Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Breezy, Rippling, BambooHR | Each company's public job-board JSON feed |
| Investor portfolio job boards (Getro-powered) | The board's public search page, filtered to remote US and Boston |

It does not scrape LinkedIn. The page gives you a LinkedIn search link per company to click yourself.

Check each site's terms before you run this, and keep the request rate polite.

## Setup

1. Run `pip install -r requirements.txt`.
2. Copy `config.example.json` to `config.json` and fill in your paths and your pay floor. `config.json` is git-ignored.
3. Provide your own company list. `src/companies.py` shows the shape: a spreadsheet of companies plus optional extra lists. Replace it with your own sources.

## Run order

| Step | Command |
|---|---|
| Find job boards for new companies | `python src/probe_ats.py` |
| Collect postings from known boards (daily) | `python src/collect.py` |
| Find investor portfolio boards (rarely) | `python src/vc_boards.py` |
| Search investor boards for data roles | `python src/vc_search.py` |
| Score and write the workbook (local only) | `python src/build_workbook.py` |
| Build the interactive pages (local only) | `python src/build_page.py` |
| **Weekly refresh: pull, score, build pages, update your local website copy** | `python src/refresh.py` |

`refresh.py` scores the newest collected run, builds both pages, and copies the showcase page to the folder set as `website_dir` in `config.json`. It never uploads anything. Set `run_date` in `config.json` to rebuild a past run.

`collect.py` and `vc_search.py` are the daily collection job. `scripts/register_daily_task.ps1` schedules them as a Windows task, and `scripts/daily_collect.ps1` is what the task runs.

**Daily collection stores only what changed.** It keeps the current postings of each job board in one file (one posting per line, sorted, so git stores a day's change as a small diff), the first day each posting was seen, and a daily log of target roles that appeared or closed. Scoring measures a role's age from the earlier of its posted date and its first-seen date, so a repost cannot make an old role look new. A board that fails to load, or suddenly answers with nothing, keeps its previous postings: a failed fetch is never treated as every job closing.

## Scoring

Each open role is scored from these parts. The Scoring sheet in the workbook has the exact rules.

| Component | Max points |
|---|---|
| Pay (does the top of the range reach your pay floor) | 30 |
| Role fit (title, seniority, location) | 25 |
| Recency (1 day or less scores highest, easing down to 90 days) | 25 |
| Investors | 20 |
| Hiring (how many roles the company has open) | 15 |
| Resume match (TF-IDF similarity, a tiebreaker) | 10 |
| Layoffs | -20 or -10 |

Stage, industry, and a low Glassdoor rating are flags, never reasons to drop a company.

**Nothing is thrown away.** A role that fails a criterion (wrong location, too old, pay below your floor) is not dropped. It scores low, sinks down the list, and the page's filters let you hide it. Roles outside Boston and remote US take a location penalty of 40 points.

**Near misses.** A role that fails exactly one hard criterion by a small margin (posted 8 to 30 days ago, or pay within 10% of your floor) is listed on its own sheet and filter, with the one thing that missed. Weights are plain numbers in `src/build_workbook.py` and are also live dials in the HTML page.

## The interactive page

`build_page.py` writes two single-file HTML pages:

- A **private** page with everything, including resume-match points.
- A **showcase** page with no resume-derived points, no private notes, and your pay floor shown only as "target pay". It is safe to host on your own site, but it still lists the companies and roles you are watching.

## Privacy by design

- Resumes, application tracking, and personal notes are read from paths in `config.json` and are never copied into the repo.
- `.gitignore` blocks resumes, spreadsheets, and scored output.
- Collected data lives in a separate repo or folder from the code.

## Files in `src/`

| File | Purpose |
|---|---|
| `settings.py` | Reads `config.json` and builds data paths. |
| `companies.py` | Builds the company list. Replace with your own sources. |
| `probe_ats.py` | Finds each company's public job board. |
| `collect.py` | Pulls every posting from each board. |
| `filters.py` | Target titles, seniority, location, and a list of rejected wrong-company boards. |
| `vc_boards.py`, `vc_search.py` | Find and search investor portfolio job boards. |
| `company_facts.py`, `profiles.py`, `stack.py` | Company profiles, and the tools named in live postings. |
| `build_workbook.py` | Scoring and the Excel workbook. |
| `build_page.py`, `page_template.html` | The interactive page. |
