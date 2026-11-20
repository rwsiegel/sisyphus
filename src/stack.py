# Find data/engineering tools named in a company's live postings.
# Uses the target-role postings when there are any, otherwise all engineering postings.
import re
from collections import Counter

# (display name, regex). Word boundaries keep "Go" from matching "Google" etc.
TOOLS = [
    ("Python", r"\bpython\b"), ("SQL", r"\bsql\b"), ("dbt", r"\bdbt\b"),
    ("Snowflake", r"\bsnowflake\b"), ("BigQuery", r"\bbigquery\b"), ("Redshift", r"\bredshift\b"),
    ("Databricks", r"\bdatabricks\b"), ("Spark", r"\bspark\b"), ("Airflow", r"\bairflow\b"),
    ("Dagster", r"\bdagster\b"), ("Prefect", r"\bprefect\b"), ("Kafka", r"\bkafka\b"), ("Flink", r"\bflink\b"),
    ("Fivetran", r"\bfivetran\b"), ("Airbyte", r"\bairbyte\b"), ("Segment", r"\bsegment\.(?:io|com)\b|\bsegment cdp\b"),
    ("Looker", r"\blooker\b"), ("Tableau", r"\btableau\b"), ("Hex", r"\bhex\b"), ("Sigma", r"\bsigma computing\b|\bsigma\b(?= ?(?:bi|computing))"),
    ("Metabase", r"\bmetabase\b"), ("Superset", r"\bsuperset\b"), ("Mode", r"\bmode analytics\b"),
    ("Postgres", r"\bpostgres(?:ql)?\b"), ("ClickHouse", r"\bclickhouse\b"), ("DuckDB", r"\bduckdb\b"),
    ("Iceberg", r"\biceberg\b"), ("Delta Lake", r"\bdelta lake\b"), ("Trino", r"\btrino\b|\bpresto\b"),
    ("AWS", r"\baws\b|amazon web services"), ("GCP", r"\bgcp\b|google cloud"), ("Azure", r"\bazure\b"),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b"), ("Terraform", r"\bterraform\b"),
    ("Hightouch", r"\bhightouch\b"), ("Census", r"\bcensus\b(?= ?(?:reverse|etl))"),
    ("Scala", r"\bscala\b"), ("Java", r"\bjava\b"), ("Go", r"\bgolang\b|\bgo\b(?= ?(?:,|/| and| or)\s*(?:python|rust|java|typescript))"),
    ("Rust", r"\brust\b"), ("TypeScript", r"\btypescript\b"),
]


def tools_in(text):
    t = (text or "").lower()
    return [name for name, pattern in TOOLS if re.search(pattern, t)]


def company_stack(postings, target_titles):
    """postings: one company's postings. target_titles: set of titles that are target roles."""
    chosen = [p for p in postings if p["title"] in target_titles]
    basis = "target-role postings"
    if not chosen:
        chosen = [p for p in postings if re.search(r"engineer|technical staff|developer", p["title"], re.I)]
        basis = "engineering postings"
    if not chosen or not any(p["text"] for p in chosen):
        return "", "no posting text"
    counts = Counter()
    for p in chosen:
        counts.update(set(tools_in(p["text"])))
    stack = ", ".join(name for name, _ in counts.most_common())
    return stack, f"named in {len(chosen)} live {basis}"
