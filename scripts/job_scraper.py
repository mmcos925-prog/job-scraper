import os
import json
import urllib.request
import urllib.parse
import smtplib
import hashlib
import re
from datetime import datetime
from pathlib import Path

JOB_KEYWORDS = [
    "cloud security analyst",
    "SOC analyst",
    "junior cloud engineer",
    "IT support specialist",
    "AWS security engineer",
    "help desk technician",
    "information security analyst",
    "technical support specialist",
    "junior IT analyst",
    "entry level IT support",
    "entry level cloud engineer",
    "entry level security analyst",
    "junior network administrator",
    "IT help desk",
    "junior systems administrator",
]

LOCATIONS = ["Brentwood CA", "Antioch CA", "Concord CA", "Walnut Creek CA", "Livermore CA", "Pittsburg CA", "remote"]
MIN_SALARY = 40000

BLOCKED_EXPERIENCE = [
    "5+ years", "6+ years", "7+ years", "8+ years", "9+ years", "10+ years",
    "5 years", "6 years", "7 years", "8 years", "9 years", "10 years",
    "5+ yrs", "6+ yrs", "7+ yrs", "8+ yrs",
    "minimum 5", "minimum 6", "minimum 7", "minimum 8",
    "at least 5", "at least 6", "at least 7", "at least 8",
    "senior ", "staff ", "principal ", "director", "manager ",
    "lead ", "architect ", "vp ", "vice president", "head of",
    "4+ years", "4 years experience", "minimum 4 years",
    "at least 4 years", "4+ yrs"
]

BLOCKED_COMPANIES = []

BLOCKED_KEYWORDS = [
    "cissp required", "cism required", "cisa required",
    "10 years", "8 years", "7 years", "6 years", "5 years",
    "4 years experience required", "4+ years required",
    "not entry level", "not a junior", "no entry level",
    "hybrid", "on-site", "onsite", "in-office",
    "san francisco", "san jose", "seattle", "new york",
    "chicago", "boston", "austin", "denver",
    "must be local to", "requires relocation",
    "secret clearance required", "ts/sci required"
]

GMAIL_USER     = "brandon.coston925@gmail.com"
GMAIL_PASS     = os.environ.get("GMAIL_APP_PASSWORD")
NOTIFY_EMAIL   = "brandon.coston925@gmail.com"
ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY")
SEEN_FILE      = "seen_jobs.json"


def load_seen():
    try:
        if Path(SEEN_FILE).exists():
            with open(SEEN_FILE) as f:
                return set(json.load(f))
    except:
        pass
    return set()


def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except:
        pass


def job_id(job):
    key = f"{job['title'].lower()}{job['company'].lower()}"
    return hashlib.md5(key.encode()).hexdigest()


def clean(text):
    if not text:
        return "N/A"
    return (str(text)
            .replace("\xa0", " ").replace("\u00a0", " ")
            .replace("\u2019", "'").replace("\u2018", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .encode("ascii", errors="replace").decode("ascii").strip())


def is_entry_level(job):
    combined = (job.get("title", "") + " " + job.get("description", "")).lower()
    for phrase in BLOCKED_EXPERIENCE:
        if phrase.lower() in combined:
            return False
    company = job.get("company", "").lower()
    for blocked in BLOCKED_COMPANIES:
        if blocked.lower() in company:
            return False
    for phrase in BLOCKED_KEYWORDS:
        if phrase.lower() in combined:
            return False
    return True


def meets_salary(job):
    sal = job.get("salary_min", 0)
    if not sal:
        return True
    return sal >= MIN_SALARY


def fetch_adzuna(keyword, location):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return []
    try:
        query = urllib.parse.quote(keyword)
        loc   = urllib.parse.quote(location)
        url   = (
            f"https://api.adzuna.com/v1/api/jobs/us/search/1"
            f"?app_id={ADZUNA_APP_ID}&app_key={ADZUNA_APP_KEY}"
            f"&results_per_page=10&what={query}&where={loc}"
            f"&sort_by=date&max_days_old=1"
        )
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        jobs = []
        for j in data.get("results", []):
            sal_min = j.get("salary_min", 0)
            sal_max = j.get("salary_max", 0)
            jobs.append({
                "title":       clean(j.get("title", "N/A")),
                "company":     clean(j.get("company", {}).get("display_name", "N/A")),
                "location":    clean(j.get("location", {}).get("display_name", "N/A")),
                "url":         j.get("redirect_url", "#"),
                "salary":      f"${sal_min:,.0f} - ${sal_max:,.0f}" if sal_min else "Not listed",
                "salary_min":  sal_min or 0,
                "description": clean(j.get("description", "")),
                "source":      "Adzuna",
            })
        return jobs
    except Exception as e:
        print(f"  Adzuna error ({keyword}/{location}): {e}")
        return []


def fetch_indeed(keyword, location):
    try:
        query = urllib.parse.quote(keyword)
        loc   = urllib.parse.quote(location)
        url   = f"https://www.indeed.com/rss?q={query}&l={loc}&sort=date&fromage=1"
        req   = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8", errors="replace")
        jobs  = []
        items = re.findall(r"<item>(.*?)</item>", content, re.DOTALL)
        for item in items[:5]:
            title   = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", item)
            link    = re.search(r"<link>(.*?)</link>", item)
            company = re.search(r"<source.*?>(.*?)</source>", item)
            jobs.append({
                "title":       clean(title.group(1)) if title else "N/A",
                "company":     clean(company.group(1)) if company else "N/A",
                "location":    clean(location.title()),
                "url":         link.group(1).strip() if link else "#",
                "salary":      "Not listed",
                "salary_min":  0,
                "description": (title.group(1) if title else "").lower(),
                "source":      "Indeed",
            })
        return jobs
    except Exception as e:
        print(f"  Indeed error ({keyword}/{location}): {e}")
        return []



def fetch_dice(keyword):
    try:
        query   = urllib.parse.quote(keyword)
        api_url = (
            f"https://job-search-api.svc.dhigroupinc.com/v1/dice/jobs/search"
            f"?q={query}&countryCode2=US&radius=30&radiusUnit=mi"
            f"&page=1&pageSize=10&filters.postedDate=ONE&language=en"
        )
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept":     "application/json",
            "x-api-key":  "1YAt0R9wBg4WfsF9VB2778F5CHLAPMVW3WAZcKd8",
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        jobs = []
        for j in data.get("data", [])[:10]:
            company = j.get("company", "N/A")
            if isinstance(company, dict):
                company = company.get("name", "N/A")
            location = clean(j.get("location", "N/A"))
            # Debug - print all keys for first job
            if j == data.get("data", [])[0]:
                print(f"  DICE JOB KEYS: {list(j.keys())}")
                print(f"  DICE LOCATION: {j.get('location')}")
                print(f"  DICE REMOTE: {j.get('remote')} | {j.get('isRemote')} | {j.get('workSetting')} | {j.get('workplaceTypes')}")
            work_setting = j.get("workSetting", j.get("workplaceType", "")).lower()
            # Skip on-site jobs not in California
            if work_setting in ["on_site", "onsite", "on-site", "in_office"]:
                loc_lower = location.lower()
                if "california" not in loc_lower and ", ca" not in loc_lower and "remote" not in loc_lower:
                    continue
            jobs.append({
                "title":       clean(j.get("title", "N/A")),
                "company":     clean(str(company)),
                "location":    location,
                "url":         f"https://www.dice.com/jobs/detail/{j.get('id', '')}",
                "salary":      clean(j.get("salary", "") or "Not listed"),
                "salary_min":  0,
                "description": clean(j.get("title", "")).lower(),
                "source":      "Dice",
            })
        return jobs
    except Exception as e:
        print(f"  Dice error ({keyword}): {e}")
        return []

def fetch_usajobs(keyword):
    try:
        query = urllib.parse.quote(keyword)
        url   = (
            f"https://data.usajobs.gov/api/search?Keyword={query}"
            f"&ResultsPerPage=5&SortField=OpenDate&SortDirection=Desc"
        )
        headers = {
            "Host": "data.usajobs.gov",
            "User-Agent": GMAIL_USER,
            "Authorization-Key": os.environ.get("USAJOBS_API_KEY", ""),
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        jobs  = []
        items = data.get("SearchResult", {}).get("SearchResultItems", [])
        for item in items[:5]:
            j       = item.get("MatchedObjectDescriptor", {})
            locs    = j.get("PositionLocation", [{}])
            loc     = locs[0].get("LocationName", "N/A") if locs else "N/A"
            pay     = j.get("PositionRemuneration", [{}])
            sal_min = float(pay[0].get("MinimumRange", 0)) if pay else 0
            sal_max = float(pay[0].get("MaximumRange", 0)) if pay else 0
            jobs.append({
                "title":       clean(j.get("PositionTitle", "N/A")),
                "company":     clean(j.get("OrganizationName", "Federal Agency")),
                "location":    clean(loc),
                "url":         j.get("PositionURI", "#"),
                "salary":      f"${sal_min:,.0f} - ${sal_max:,.0f}" if sal_min else "Not listed",
                "salary_min":  sal_min,
                "description": j.get("PositionTitle", "").lower(),
                "source":      "USAJobs (Federal)",
            })
        return jobs
    except Exception as e:
        print(f"  USAJobs error ({keyword}): {e}")
        return []


def fetch_remotive(keyword):
    try:
        import re as re_mod
        query = urllib.parse.quote(keyword)
        url   = f"https://remotive.com/remote-jobs/feed?search={query}"
        req   = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            rss = r.read().decode("utf-8", errors="replace")
        items = re_mod.findall(r"<item>(.*?)</item>", rss, re_mod.DOTALL)
        jobs  = []
        for item in items[:5]:
            title   = re_mod.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", item)
            link    = re_mod.search(r"<link>(.*?)</link>", item)
            company = re_mod.search(r"<dc:creator><!\[CDATA\[(.*?)\]\]></dc:creator>", item)
            if not title:
                continue
            jobs.append({
                "title":       clean(title.group(1)),
                "company":     clean(company.group(1)) if company else "N/A",
                "location":    "Remote",
                "url":         link.group(1).strip() if link else "#",
                "salary":      "Not listed",
                "salary_min":  0,
                "description": title.group(1).lower(),
                "source":      "Remotive",
            })
        return jobs
    except Exception as e:
        print(f"  Remotive error ({keyword}): {e}")
        return []


def deduplicate(jobs):
    seen, result = set(), []
    for j in jobs:
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in seen:
            seen.add(key)
            result.append(j)
    return result


# States and cities we never want
BLOCKED_LOCATIONS = [
    "new york", "seattle", "chicago", "boston", "austin",
    "denver", "atlanta", "dallas", "houston", "phoenix",
    "miami", "portland", "minneapolis", "detroit", "las vegas",
    "nashville", "charlotte", "raleigh", "washington dc",
    "washington, dc", "arlington", "virginia", "texas", "florida",
    "georgia", "illinois", "new jersey", "massachusetts",
    "north carolina", "ohio", "michigan", "pennsylvania",
    "colorado", "arizona", "oregon", "washington state",
    "new york, ny", "ny, ny", ", ny", ", tx", ", fl",
    ", ga", ", il", ", nj", ", ma", ", nc", ", oh",
    ", mi", ", pa", ", co", ", az", ", or", ", wa",
    ", va", ", dc", ", md", ", mn", ", mo", ", tn",
    "brooklyn", "manhattan", "bronx", "queens",
]

ALLOWED_LOCATIONS = [
    "remote", "brentwood", "antioch", "concord",
    "walnut creek", "livermore", "pittsburg", "clayton",
    "pleasant hill", "bay point", "oakley", "discovery bay",
    "california", ", ca", "ca,", "bay area", "east bay",
    "united states", "usa", "nationwide", "anywhere", "n/a"
]

def is_allowed_location(job):
    location = job.get("location", "").lower().strip()

    # Block specific out-of-state locations first
    for blocked in BLOCKED_LOCATIONS:
        if blocked in location:
            return False

    # Always allow remote with no state specified
    if location in ["remote", "remote, remote", "anywhere", ""]:
        return True

    # Allow remote if it also mentions California
    if "remote" in location and ("ca" in location or "california" in location):
        return True

    # Allow pure remote with no location info
    if "remote" in location and not any(c.isalpha() and c not in "remote" for c in location.replace("remote", "")):
        return True

    # Allow if no location specified
    if not location or location == "n/a":
        return True

    # Block generic "United States" with no state — too broad
    if location in ["united states", "usa", "us"]:
        return False

    # Check against allowed locations
    for allowed in ALLOWED_LOCATIONS:
        if allowed in location:
            return True

    # If location has "remote" anywhere and passes blocked check, allow it
    if "remote" in location:
        return True

    return False


def build_email(jobs, skipped):
    today = datetime.now().strftime("%B %d, %Y")
    if not jobs:
        return (
            f"<html><body style='font-family:Arial,sans-serif;max-width:700px;margin:auto;'>"
            f"<div style='background:#1a56a0;padding:20px;border-radius:8px 8px 0 0;'>"
            f"<h1 style='color:white;margin:0;'>Job Digest</h1>"
            f"<p style='color:#dbeafe;margin:4px 0 0;'>{today}</p></div>"
            f"<div style='padding:20px;'><p>No new postings today. "
            f"{skipped} jobs were filtered (already seen, overqualified, or below "
            f"${MIN_SALARY:,} salary minimum).</p></div></body></html>"
        )

    by_source = {}
    for j in jobs:
        by_source.setdefault(j["source"], []).append(j)

    html = (
        f"<html><body style='font-family:Arial,sans-serif;max-width:700px;margin:auto;'>"
        f"<div style='background:#1a56a0;padding:20px;border-radius:8px 8px 0 0;'>"
        f"<h1 style='color:white;margin:0;'>Job Digest</h1>"
        f"<p style='color:#dbeafe;margin:4px 0 0;'>{today} - "
        f"{len(jobs)} new | {skipped} filtered out</p>"
        f"</div><div style='padding:20px;background:#f8fafc;border:1px solid #e2e8f0;'>"
    )

    for source, source_jobs in by_source.items():
        html += (
            f"<h2 style='color:#1a56a0;border-bottom:2px solid #1a56a0;"
            f"padding-bottom:6px;'>{source} ({len(source_jobs)})</h2>"
        )
        for j in source_jobs:
            html += (
                f"<div style='background:white;border:1px solid #e2e8f0;"
                f"border-radius:6px;padding:16px;margin-bottom:12px;'>"
                f"<h3 style='margin:0 0 4px;'>"
                f"<a href='{j['url']}' style='color:#1a56a0;text-decoration:none;'>"
                f"{j['title']}</a></h3>"
                f"<p style='margin:0 0 4px;color:#64748b;font-size:14px;'>"
                f"{j['company']} | {j['location']}</p>"
                f"<p style='margin:0 0 8px;color:#16a34a;font-size:14px;'>"
                f"{j['salary']}</p>"
                f"<a href='{j['url']}' style='background:#1a56a0;color:white;"
                f"padding:8px 16px;border-radius:4px;text-decoration:none;"
                f"font-size:13px;'>View and Apply</a>"
                f"</div>"
            )

    html += (
        f"<p style='color:#64748b;font-size:12px;text-align:center;margin-top:20px;'>"
        f"Automated digest for Brandon Coston - github.com/mmcos925-prog</p>"
        f"</div></body></html>"
    )
    return html


def send_email(html_body, job_count, skipped):
    if not GMAIL_PASS:
        print("Gmail app password not configured")
        return
    today   = datetime.now().strftime("%B %d, %Y")
    subject = f"Job Digest {today} - {job_count} new | {skipped} filtered"
    safe    = html_body.encode("ascii", errors="replace").decode("ascii")
    raw     = (
        f"From: {GMAIL_USER}\r\n"
        f"To: {NOTIFY_EMAIL}\r\n"
        f"Subject: {subject}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/html; charset=us-ascii\r\n"
        f"\r\n"
        f"{safe}"
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, NOTIFY_EMAIL,
                          raw.encode("ascii", errors="replace"))
        print(f"Email sent - {job_count} new jobs | {skipped} filtered")
    except Exception as e:
        print(f"Email failed: {e}")


def main():
    print(f"Starting job search - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    seen     = load_seen()
    all_jobs = []

    for keyword in JOB_KEYWORDS:
        print(f"  Searching: {keyword}")
        for loc in LOCATIONS:
            all_jobs += fetch_adzuna(keyword, loc)
            all_jobs += fetch_indeed(keyword, loc)
        all_jobs += fetch_dice(keyword)
        all_jobs += fetch_usajobs(keyword)
        all_jobs += fetch_remotive(keyword)

    all_jobs = deduplicate(all_jobs)
    print(f"Found {len(all_jobs)} unique postings before filtering")

    filtered  = []
    skipped   = 0
    new_seen  = set(seen)

    for job in all_jobs:
        jid = job_id(job)
        if jid in seen:
            skipped += 1
            continue
        if not is_entry_level(job):
            skipped += 1
            continue
        if not meets_salary(job):
            skipped += 1
            continue
        if not is_allowed_location(job):
            skipped += 1
            continue
        filtered.append(job)
        new_seen.add(jid)

    save_seen(new_seen)
    print(f"After filtering: {len(filtered)} new | {skipped} filtered out")

    html = build_email(filtered, skipped)
    send_email(html, len(filtered), skipped)


if __name__ == "__main__":
    main()
