import os
import json
import urllib.request
import urllib.parse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

JOB_KEYWORDS = [
    "cloud security analyst",
    "SOC analyst",
    "junior cloud engineer",
    "IT support specialist",
    "AWS security",
    "help desk technician",
    "information security analyst",
    "technical support specialist",
]

GMAIL_USER     = os.environ.get("GMAIL_USER")
GMAIL_PASS     = os.environ.get("GMAIL_APP_PASSWORD")
NOTIFY_EMAIL   = os.environ.get("NOTIFY_EMAIL", GMAIL_USER)
ADZUNA_APP_ID  = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY")


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
            f"&sort_by=date&max_days_old=2"
        )
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        jobs = []
        for j in data.get("results", []):
            title    = j.get("title", "N/A").encode("ascii", errors="replace").decode("ascii")
            company  = j.get("company", {}).get("display_name", "N/A").encode("ascii", errors="replace").decode("ascii")
            loc_name = j.get("location", {}).get("display_name", "N/A").encode("ascii", errors="replace").decode("ascii")
            salary   = (f"${j['salary_min']:,.0f} - ${j['salary_max']:,.0f}"
                       if j.get("salary_min") else "Not listed")
            jobs.append({
                "title":    title,
                "company":  company,
                "location": loc_name,
                "url":      j.get("redirect_url", "#"),
                "salary":   salary,
            })
        return jobs
    except Exception as e:
        print(f"Adzuna error ({keyword}/{location}): {e}")
        return []


def deduplicate(jobs):
    seen, clean = set(), []
    for j in jobs:
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in seen:
            seen.add(key)
            clean.append(j)
    return clean


def build_email(jobs):
    today = datetime.now().strftime("%B %d, %Y")
    if not jobs:
        return (
            f"<html><body><h2>Job Digest {today}</h2>"
            f"<p>No new postings found today.</p></body></html>"
        )
    rows = ""
    for j in jobs:
        rows += (
            f"<div style='background:white;border:1px solid #e2e8f0;"
            f"border-radius:6px;padding:16px;margin-bottom:12px;'>"
            f"<h3 style='margin:0 0 4px;'>"
            f"<a href='{j['url']}' style='color:#1a56a0;text-decoration:none;'>{j['title']}</a>"
            f"</h3>"
            f"<p style='margin:0;color:#64748b;font-size:14px;'>"
            f"{j['company']} | {j['location']}</p>"
            f"<p style='margin:4px 0 8px;color:#16a34a;font-size:14px;'>{j['salary']}</p>"
            f"<a href='{j['url']}' style='background:#1a56a0;color:white;"
            f"padding:8px 16px;border-radius:4px;text-decoration:none;"
            f"font-size:13px;'>View Job</a></div>"
        )
    return (
        f"<html><body style='font-family:Arial,sans-serif;max-width:700px;margin:auto;'>"
        f"<div style='background:#1a56a0;padding:20px;border-radius:8px 8px 0 0;'>"
        f"<h1 style='color:white;margin:0;'>Job Digest</h1>"
        f"<p style='color:#dbeafe;margin:4px 0 0;'>{today} - {len(jobs)} posting(s)</p>"
        f"</div><div style='padding:20px;background:#f8fafc;border:1px solid #e2e8f0;'>"
        f"{rows}"
        f"<p style='color:#64748b;font-size:12px;text-align:center;'>"
        f"github.com/mmcos925-prog - Powered by GitHub Actions</p>"
        f"</div></body></html>"
    )


def send_email(html_body, job_count):
    if not GMAIL_USER or not GMAIL_PASS:
        print("Email credentials not configured")
        return
    today = datetime.now().strftime("%B %d, %Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Job Digest {today} - {job_count} posting(s)"
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_bytes())
        print(f"Email sent to {NOTIFY_EMAIL} with {job_count} jobs")
    except Exception as e:
        print(f"Email failed: {e}")


def main():
    print(f"Starting job search - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    all_jobs = []
    for keyword in JOB_KEYWORDS:
        print(f"  Searching: {keyword}")
        all_jobs += fetch_adzuna(keyword, "california")
        all_jobs += fetch_adzuna(keyword, "remote")
    all_jobs = deduplicate(all_jobs)
    print(f"Found {len(all_jobs)} unique postings")
    html = build_email(all_jobs)
    send_email(html, len(all_jobs))


if __name__ == "__main__":
    main()
