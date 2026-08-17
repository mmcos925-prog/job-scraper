"""
Job Scraper for Brandon Coston
Searches Adzuna, Remotive, and USAJobs for cloud security and IT roles
Sends a daily email digest with new postings
"""

import os
import json
import urllib.request
import urllib.parse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────

# Target job keywords — edit these to change what you search for
JOB_KEYWORDS = [
    "cloud security analyst",
    "SOC analyst",
    "junior cloud engineer",
    "IT support specialist",
    "AWS security",
    "help desk",
    "information security analyst",
    "technical support specialist",
]

# Locations to search
LOCATIONS = ["California", "Remote"]

# Email config — pulled from GitHub Secrets
GMAIL_USER   = os.environ.get("GMAIL_USER")
GMAIL_PASS   = os.environ.get("GMAIL_APP_PASSWORD")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", GMAIL_USER)

# Adzuna API credentials — pulled from GitHub Secrets
ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY")


# ── Adzuna (US jobs) ──────────────────────────────────────────────────────────

def fetch_adzuna(keyword, location="california"):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return []
    try:
        query = urllib.parse.quote(keyword)
        loc   = urllib.parse.quote(location)
        url   = (
            f"https://api.adzuna.com/v1/api/jobs/us/search/1"
            f"?app_id={ADZUNA_APP_ID}&app_key={ADZUNA_APP_KEY}"
            f"&results_per_page=5&what={query}&where={loc}"
            f"&sort_by=date&max_days_old=1"
        )
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        jobs = []
        for j in data.get("results", []):
            jobs.append({
                "title":   j.get("title", "N/A"),
                "company": j.get("company", {}).get("display_name", "N/A"),
                "location":j.get("location", {}).get("display_name", "N/A"),
                "url":     j.get("redirect_url", "#"),
                "salary":  f"${j['salary_min']:,.0f} – ${j['salary_max']:,.0f}"
                           if j.get("salary_min") else "Not listed",
                "source":  "Adzuna",
            })
        return jobs
    except Exception as e:
        print(f"Adzuna error ({keyword}): {e}")
        return []


# ── Remotive (remote tech jobs) ───────────────────────────────────────────────

def fetch_remotive(keyword):
    try:
        query = urllib.parse.quote(keyword)
        url   = f"https://remotive.com/api/remote-jobs?search={query}&limit=5"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        jobs = []
        for j in data.get("jobs", [])[:5]:
            jobs.append({
                "title":    j.get("title", "N/A"),
                "company":  j.get("company_name", "N/A"),
                "location": "Remote",
                "url":      j.get("url", "#"),
                "salary":   j.get("salary", "Not listed") or "Not listed",
                "source":   "Remotive",
            })
        return jobs
    except Exception as e:
        print(f"Remotive error ({keyword}): {e}")
        return []


# ── USAJobs (federal roles) ───────────────────────────────────────────────────

def fetch_usajobs(keyword):
    try:
        query   = urllib.parse.quote(keyword)
        url     = (
            f"https://data.usajobs.gov/api/search?Keyword={query}"
            f"&ResultsPerPage=5&SortField=OpenDate&SortDirection=Desc"
        )
        headers = {
            "Host":              "data.usajobs.gov",
            "User-Agent":        GMAIL_USER or "brandon.coston925@gmail.com",
            "Authorization-Key": "",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        jobs = []
        items = (data.get("SearchResult", {})
                     .get("SearchResultItems", []))
        for item in items[:5]:
            j = item.get("MatchedObjectDescriptor", {})
            locs = j.get("PositionLocation", [{}])
            loc  = locs[0].get("LocationName", "N/A") if locs else "N/A"
            pay  = j.get("PositionRemuneration", [{}])
            sal  = (f"${float(pay[0].get('MinimumRange','0')):,.0f} – "
                    f"${float(pay[0].get('MaximumRange','0')):,.0f}"
                    if pay else "Not listed")
            jobs.append({
                "title":    j.get("PositionTitle", "N/A"),
                "company":  j.get("OrganizationName", "Federal Agency"),
                "location": loc,
                "url":      j.get("PositionURI", "#"),
                "salary":   sal,
                "source":   "USAJobs (Federal)",
            })
        return jobs
    except Exception as e:
        print(f"USAJobs error ({keyword}): {e}")
        return []


# ── Deduplicate ───────────────────────────────────────────────────────────────

def deduplicate(jobs):
    seen  = set()
    clean = []
    for j in jobs:
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in seen:
            seen.add(key)
            clean.append(j)
    return clean


# ── Build email ───────────────────────────────────────────────────────────────

def build_email(jobs):
    today = datetime.now().strftime("%B %d, %Y")
    if not jobs:
        body = f"""
        <h2>☁️ Daily Job Digest — {today}</h2>
        <p>No new postings found today matching your search criteria.
        Check back tomorrow!</p>
        """
        return body

    # Group by source
    by_source = {}
    for j in jobs:
        by_source.setdefault(j["source"], []).append(j)

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;">
    <div style="background:#1a56a0;padding:20px;border-radius:8px 8px 0 0;">
      <h1 style="color:white;margin:0;">☁️ Daily Job Digest</h1>
      <p style="color:#dbeafe;margin:4px 0 0;">{today} — {len(jobs)} new posting(s) found</p>
    </div>
    <div style="padding:20px;background:#f8fafc;border:1px solid #e2e8f0;">
    """

    for source, source_jobs in by_source.items():
        html += f"""
        <h2 style="color:#1a56a0;border-bottom:2px solid #1a56a0;
                   padding-bottom:6px;">{source}</h2>
        """
        for j in source_jobs:
            html += f"""
            <div style="background:white;border:1px solid #e2e8f0;
                        border-radius:6px;padding:16px;margin-bottom:12px;">
              <h3 style="margin:0 0 4px;color:#1e293b;">
                <a href="{j['url']}" style="color:#1a56a0;text-decoration:none;">
                  {j['title']}
                </a>
              </h3>
              <p style="margin:0 0 4px;color:#64748b;font-size:14px;">
                🏢 {j['company']} &nbsp;|&nbsp; 📍 {j['location']}
              </p>
              <p style="margin:0 0 8px;color:#16a34a;font-size:14px;">
                💰 {j['salary']}
              </p>
              <a href="{j['url']}"
                 style="background:#1a56a0;color:white;padding:8px 16px;
                        border-radius:4px;text-decoration:none;font-size:13px;">
                View Job →
              </a>
            </div>
            """

    html += """
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
    <p style="color:#64748b;font-size:12px;text-align:center;">
      Automated job digest for Brandon Coston •
      github.com/mmcos925-prog •
      Powered by GitHub Actions
    </p>
    </div></body></html>
    """
    return html


# ── Send email ────────────────────────────────────────────────────────────────

def send_email(html_body, job_count):
    if not GMAIL_USER or not GMAIL_PASS:
        print("Email credentials not set — printing results instead:")
        print(html_body)
        return

    today = datetime.now().strftime("%B %d, %Y")
    msg   = MIMEMultipart("alternative")
    msg["Subject"] = f"☁️ Job Digest {today} — {job_count} new posting(s)"
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_bytes())
        print(f"✅ Email sent to {NOTIFY_EMAIL} with {job_count} jobs")
    except Exception as e:
        print(f"❌ Email failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"🔍 Starting job search — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    all_jobs = []

    for keyword in JOB_KEYWORDS:
        print(f"  Searching: {keyword}")
        all_jobs += fetch_adzuna(keyword, "california")
        all_jobs += fetch_adzuna(keyword, "remote")
        all_jobs += fetch_remotive(keyword)
        all_jobs += fetch_usajobs(keyword)

    all_jobs = deduplicate(all_jobs)
    print(f"✅ Found {len(all_jobs)} unique postings")

    html  = build_email(all_jobs)
    send_email(html, len(all_jobs))


if __name__ == "__main__":
    main()
