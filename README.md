# Automated Job Scraper & Digest System

An automated job search pipeline built with Python and GitHub Actions that searches multiple job boards daily, applies intelligent filtering, and delivers a formatted email digest of relevant opportunities.

---

## What It Does

- **Searches multiple job boards** simultaneously — Adzuna, USAJobs (federal), and Remotive
- **Applies intelligent filtering** to remove irrelevant results — senior roles, out-of-state on-site positions, below-salary-threshold postings, and non-IT roles
- **Tracks previously seen jobs** using a persistent JSON cache committed back to the repo, ensuring every email only contains genuinely new postings
- **Delivers a formatted HTML email digest** daily at 8:00 AM Pacific with job title, company, location, salary, and direct apply links grouped by source
- **Runs automatically** via GitHub Actions scheduled workflow — zero manual intervention required

---

## Technologies Used

| Technology | Purpose |
|---|---|
| Python 3 | Core scripting and logic |
| GitHub Actions | Scheduled automation (cron) |
| Adzuna API | Primary US job board source |
| USAJobs API | Federal government IT roles |
| Remotive RSS | Remote tech roles |
| smtplib / MIME | HTML email delivery via Gmail SMTP |
| JSON | Seen jobs persistence cache |
| GitHub Secrets | Secure credential management |

---

## Architecture

```
GitHub Actions (cron: 8AM Pacific daily)
         ↓
job_scraper.py runs on ubuntu-latest runner
         ↓
Fetches jobs from Adzuna + USAJobs + Remotive
         ↓
Deduplicates across all sources
         ↓
Applies filters:
  • Entry-level only (title-based experience check)
  • IT relevance check (keyword matching)
  • Location filter (California/Remote only)
  • Salary floor ($40,000 minimum)
  • Seen jobs cache (no repeats)
         ↓
Builds HTML email digest grouped by source
         ↓
Sends via Gmail SMTP using app password
         ↓
Commits updated seen_jobs.json back to repo
```

---

## Filtering Logic

The scraper applies a multi-layer filtering system:

**Experience Filter** — blocks titles containing senior, principal, director, architect, VP, or explicit year requirements (5+ years, 6+ years, etc.)

**IT Relevance Filter** — requires at least one IT keyword in the title or description (cloud, security, help desk, analyst, engineer, etc.) — eliminates irrelevant USAJobs results like medical or administrative roles

**Location Filter** — allows only:
- Jobs explicitly marked as Remote
- Jobs located in California cities near Brentwood (Bay Area, Sacramento corridor)
- Blocks confirmed out-of-state locations using state abbreviation matching

**Salary Filter** — passes jobs with no salary listed (most don't list it) but filters out confirmed below-threshold postings

**Seen Jobs Cache** — MD5 hash of title + company stored in `seen_jobs.json`, committed back to the repo after each run so no job appears twice

---

## Setup

### Prerequisites
- GitHub account
- Gmail account with 2FA enabled
- Free Adzuna developer account at developer.adzuna.com
- Free USAJobs API key at developer.usajobs.gov

### GitHub Secrets Required

| Secret | Value |
|---|---|
| `GMAIL_APP_PASSWORD` | 16-character Gmail app password |
| `ADZUNA_APP_ID` | Adzuna application ID |
| `ADZUNA_APP_KEY` | Adzuna application key |
| `USAJOBS_API_KEY` | USAJobs registered email |

### Deployment
```bash
git clone https://github.com/mmcos925-prog/job-scraper
cd job-scraper
# Add secrets to GitHub repo settings
# Workflow runs automatically at 8AM Pacific
# Or trigger manually via Actions tab
```

---

## Customization

Edit `scripts/job_scraper.py` to customize:

```python
JOB_KEYWORDS = [...]      # Search terms
MIN_SALARY = 40000        # Salary floor
BLOCKED_EXPERIENCE = [...] # Titles to exclude
BLOCKED_COMPANIES = [...]  # Companies to skip
LOCATIONS = [...]          # Search locations
```

---

## Security Practices

- All credentials stored as GitHub Secrets — never in code
- Gmail App Password used instead of account password
- API keys scoped to read-only job search permissions
- No personal data stored beyond seen job hashes

---

## Author

**Brandon Coston** — Cloud Security Professional  
AWS Certified Cloud Practitioner | Google Cybersecurity Certificate  
[github.com/mmcos925-prog](https://github.com/mmcos925-prog)
