# Rules for which boards are wrong, which titles count as target roles, and location / date checks.
import re
from datetime import datetime, timezone, timedelta

from settings import RUN_DATE
WINDOW_START = RUN_DATE - timedelta(days=7)

# (company, ats, slug) boards that belong to a different company. Checked by reading posting text.
WRONG_BOARDS = {
    ("Zero Hash", "ashby", "zero"): "construction company, not Zero Hash",
    ("Flex", "greenhouse", "flex"): "getflex.com (rent payments), not flex.one",
    ("1Password", "workable", "1password"): "generic Workable listing",
    ("Engine", "lever", "engine"): "The Engine (nonprofit), not engine.com",
    ("Maven Clinic", "ashby", "maven"): "different company",
    ("Rightway", "greenhouse", "rightway"): "Right Way Garage Doors",
    ("ASI", "greenhouse", "asi"): "ASI Hastings (HVAC/plumbing)",
    ("Antares Therapeutics", "ashby", "antares"): "Antares nuclear energy, not Antares Therapeutics",
    ("Life Biosciences", "lever", "life"): "Life.Church",
    ("Anagram Therapeutics, Inc.", "ashby", "anagram"): "Anagram crypto holding company",
    ("Applied Compute", "ashby", "applied"): "different company (334 jobs, no Applied Compute mention)",
    ("River AI", "ashby", "river"): "different company",
    ("General Intuition", "greenhouse", "general"): "'General Interest' board",
    ("Nous Research", "ashby", "nous"): "different company",
    # Startup Shortlist companies (checked by reading posting text, 2026-11-19)
    ("Aleph", "lever", "aleph"): "Aleph digital-advertising group, not getaleph.com (FP&A)",
    ("Crux", "ashby", "crux"): "Crux AI (AI infrastructure), not Crux climate finance",
    ("Clutch", "greenhouse", "clutch"): "Clutch, Canadian used-car retailer",
    ("Cube", "ashby", "cube"): "CUBE RegTech, not cube.dev",
    ("VIA", "greenhouse", "via"): "Via Transportation, not Via Science",
    ("Socket", "greenhouse", "socket"): "Socket Labs (blockchain), not socket.dev",
    ("Maven AGI", "ashby", "maven"): "different company ('Maven for Business')",
    ("Liquid AI", "ashby", "liquid"): "different company",
    ("Gradient AI", "ashby", "gradient"): "different company",
    ("Basis Theory", "lever", "basis"): "Basis (media planning), not Basis Theory",
    ("Conduit", "ashby", "conduit"): "blockchain infrastructure company; shortlist Conduit is conduit.financial (likely different)",
    ("Altana AI", "ashby", "altana"): "mirror of the Greenhouse board (same 36 jobs); kept Greenhouse",
    ("ScaleOps", "smartrecruiters", "scaleops"): "mirror of the Greenhouse board, no posting text; kept Greenhouse",
}

ROLE_PATTERNS = [
    ("analytics engineer", r"analytics engineer"),
    ("data engineer", r"data engineer|data engineering"),
    ("data platform engineer", r"data platform|data infrastructure|data infra\b|data & training infra|data and training infra"),
    ("software engineer on a data platform", r"(software|backend|platform) engineer.*\bdata\b|\bdata\b.*(software|backend) engineer"),
]

# A title must name an engineering role; this drops e.g. "Product Manager, Data Platform".
ENGINEERING_WORDS = r"engineer|engineering|technical staff|architect|developer"

SENIOR_WORDS = r"\b(senior|sr\.?|staff|principal|lead|head|director|manager|founding|iii|iv)\b"
JUNIOR_WORDS = r"\b(intern|internship|junior|jr\.?|associate|entry|new grad|graduate|apprentice)\b"


def role_type(title):
    t = title.lower()
    if not re.search(ENGINEERING_WORDS, t):
        return ""
    for name, pattern in ROLE_PATTERNS:
        if re.search(pattern, t):
            return name
    return ""


def seniority(title):
    t = title.lower()
    # "Associate Director" and "Associate Vice President" are senior roles, not junior ones.
    if re.search(r"associate (director|vice|vp|principal)", t):
        return "senior+"
    if re.search(JUNIOR_WORDS, t):
        return "junior"
    if re.search(SENIOR_WORDS, t):
        return "senior+"
    return "not stated"


BOSTON_WORDS = r"boston|cambridge, ma|cambridge, massachusetts|somerville|waltham|newton|norwood|burlington, ma|\bma\b|massachusetts"
US_REMOTE_WORDS = r"remote.*(us|u\.s\.|united states|usa|north america|americas)|(us|u\.s\.|united states|usa)[^;]*remote|remote$|^remote\b"


def location_fit(location, workplace, text):
    loc = (location or "").lower()
    wp = (workplace or "").lower()
    if re.search(BOSTON_WORDS, loc):
        return "Boston"
    if re.search(US_REMOTE_WORDS, loc) or ("remote" in wp and not re.search(r"canada|uk|united kingdom|london|india|europe|germany|poland|brazil|mexico|australia|toronto|vancouver|latam|emea|apac|budapest|tel aviv|são paulo|sao paulo", loc)):
        return "Remote US"
    if "remote" in loc:
        return "Remote (country unclear)"
    return "No: " + location


def parse_date(value):
    if not value:
        return None
    value = str(value).replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(value)
    except ValueError:
        d = datetime.strptime(value[:10], "%Y-%m-%d")
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d
