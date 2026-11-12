"""
Scores each job against Brandon's background, picks which resume version to send,
and flags signs of a recruiting scam. Used by job_scraper.py to rank the daily digest.
Nothing here applies to jobs: it only helps decide which ones are worth applying to.
"""
import re
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Fit score
# ---------------------------------------------------------------------------

# (pattern, points, label). Patterns are regexes matched against lowercase text.
POSITIVE = [
    (r"help ?desk|service desk", 3, "help desk"),
    (r"desktop support|deskside", 3, "desktop support"),
    (r"\bit support\b|technical support|support (specialist|technician|analyst|associate)|\bit technician\b", 3, "IT support"),
    (r"\bfield\b.*technician|deployment|imaging|data center", 2, "field/deployment"),
    (r"\btier (1|i)\b|\blevel (1|i)\b|\bl1\b", 2, "tier 1"),
    (r"entry[- ]level|early[- ]career|junior|\bjr\.?\b", 2, "entry level"),
    (r"\bnoc\b|network operations", 3, "NOC"),
    (r"\bsoc\b|security operations", 3, "SOC"),
    (r"\biam\b|identity|access management|provisioning", 3, "identity/access"),
    (r"\bentra\b|azure ad|active directory", 3, "Entra/AD"),
    (r"\bsso\b|single sign-on|\bmfa\b|multi-?factor|okta", 2, "SSO/MFA"),
    (r"microsoft 365|office 365|\bm365\b|\bo365\b|intune", 2, "Microsoft 365"),
    (r"\baws\b|amazon web services", 2, "AWS"),
    (r"security\+|comptia", 2, "CompTIA"),
    (r"overnight|night shift|graveyard|3rd shift|third shift", 2, "overnight"),
    (r"\bremote\b", 1, "remote"),
]

NEGATIVE = [
    (r"\bsenior\b|\bsr\.?\b", -4, "senior"),
    (r"\blead\b|\bprincipal\b|\barchitect\b|\bmanager\b|\bdirector\b", -4, "leadership"),
    (r"\b([5-9]|1[0-9])\+? years", -4, "5+ years"),
    (r"\b[34]\+? years", -2, "3-4 years"),
    (r"ts/sci|top secret|polygraph|clearance required|active (secret|clearance)", -5, "clearance"),
    (r"\bcissp\b|\bccnp\b", -2, "advanced cert"),
]


def score_job(job):
    """Return (score, reasons): higher is a better fit."""
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    title = job.get("title", "").lower()
    score, reasons = 0, []
    for pattern, points, label in POSITIVE:
        if re.search(pattern, text):
            # Title matches count double: they say what the job really is.
            pts = points * 2 if re.search(pattern, title) else points
            score += pts
            reasons.append(label)
    for pattern, points, label in NEGATIVE:
        if re.search(pattern, text):
            score += points
            reasons.append(f"-{label}")
    return score, reasons


# ---------------------------------------------------------------------------
# Which resume to send
# ---------------------------------------------------------------------------

RESUME_TRACKS = [
    (r"\bnoc\b|network operations|\bsoc\b|security operations|911|monitoring", "NOC Technician"),
    (r"\biam\b|identity|access management|entra|azure ad|okta|provisioning", "IT Support (identity-focused)"),
    (r"help ?desk|service desk|desktop support|\bit support\b|technical support", "IT Support (identity-focused)"),
    (r"\bfield\b|deployment|imaging|refresh|warehouse|fulfillment|data center", "Field IT Technician"),
    (r"cloud|\baws\b|security analyst|cyber", "Cloud Security (v4)"),
]


def pick_resume(job):
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    for pattern, name in RESUME_TRACKS:
        if re.search(pattern, text):
            return name
    return "IT Support (identity-focused)"


# ---------------------------------------------------------------------------
# Scam and fine-print flags
# ---------------------------------------------------------------------------

SCAM_PHRASES = [
    (r"telegram|whatsapp|signal app|google hangouts|chat interview|text interview", "Interview over chat app"),
    (r"purchase (your own )?equipment|buy equipment|equipment (check|reimbursement)", "Asks you to buy equipment"),
    (r"cashier'?s check|deposit (a|the) check|send you a check|wire transfer|gift cards?|bitcoin|crypto(currency)? payment",
     "Mentions checks, wires, gift cards, or crypto"),
    (r"training fee|pay for (your )?training|starter kit|upfront fee", "Asks for money up front"),
    (r"no interview|hired immediately|instant hire", "Promises hiring without an interview"),
]

# Real job boards and applicant tracking systems. A link to anything else whose
# domain looks like "<company>-careers.com" or "<company>jobs.net" gets flagged.
TRUSTED_HOSTS = [
    "myworkdayjobs.com", "workday.com", "greenhouse.io", "lever.co", "icims.com",
    "smartrecruiters.com", "ashbyhq.com", "jobvite.com", "taleo.net", "successfactors.com",
    "adp.com", "paylocity.com", "bamboohr.com", "ultipro.com", "ukg.com",
    "indeed.com", "linkedin.com", "dice.com", "usajobs.gov", "remoteok.com",
    "weworkremotely.com", "remotive.com", "adzuna.com", "ziprecruiter.com", "glassdoor.com",
    "amazon.jobs", "teksystems.com", "careerbuilder.com", "monster.com", "simplyhired.com",
]

# Matched against the site's own name (e.g. "avalara-careers" in avalara-careers.com),
# not subdomains, so jobs.aerotek.com or careers.company.com are fine.
CAREERS_LOOKALIKE = re.compile(r"careers?|jobs?|hiring|recruit")


def scam_flags(job):
    flags = []
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    for pattern, label in SCAM_PHRASES:
        if re.search(pattern, text):
            flags.append(label)

    host = urlparse(job.get("url", "")).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    trusted = any(host == t or host.endswith("." + t) for t in TRUSTED_HOSTS)
    site_name = host.split(".")[-2] if host.count(".") >= 1 else host
    if host and not trusted and CAREERS_LOOKALIKE.search(site_name):
        flags.append(f"Unfamiliar careers-style domain ({host}): check it on the company's main website")

    company = (job.get("company") or "").strip().lower()
    if company in ("", "n/a", "confidential", "unknown", "company confidential"):
        flags.append("Company not named")

    title = job.get("title", "").lower()
    if job.get("salary_min", 0) >= 120000 and re.search(r"entry|junior|tier 1|help ?desk|support", title):
        flags.append("Unusually high pay for an entry-level title")
    return flags


def fine_print(job):
    """Non-scam notes worth knowing before applying."""
    notes = []
    loc = (job.get("location") or "").lower()
    m = re.search(r"remote in [^,]+,\s*([a-z]{2})\b", loc)
    if m and m.group(1) != "ca":
        notes.append(f"'Remote in {m.group(1).upper()}' usually means you must live in that state")
    return notes


def annotate(job):
    """Add score, reasons, resume, flags, and notes to a job dict."""
    job["score"], job["reasons"] = score_job(job)
    job["resume"] = pick_resume(job)
    job["flags"] = scam_flags(job)
    job["notes"] = fine_print(job)
    return job
