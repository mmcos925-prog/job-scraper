# Automated Job Scraper

A GitHub Actions workflow that runs every morning at 8am, searches multiple
job boards for cloud security and IT roles, and emails a digest of new postings.

## Sources
- **Adzuna** — broad US job listings
- **Remotive** — remote tech roles
- **USAJobs** — federal government roles

## Setup

### Step 1: Get your Adzuna API key (free)
1. Go to https://developer.adzuna.com
2. Sign up for a free account
3. Create an app — copy your App ID and App Key

### Step 2: Set up Gmail App Password
1. Go to your Google Account → Security
2. Enable 2-Factor Authentication if not already on
3. Search for "App passwords" → create one for "Mail"
4. Copy the 16-character password generated

### Step 3: Add GitHub Secrets
Go to your repo → Settings → Secrets and variables → Actions → New secret

Add these 5 secrets:
| Secret Name | Value |
|---|---|
| GMAIL_USER | your Gmail address |
| GMAIL_APP_PASSWORD | the 16-char app password from Step 2 |
| NOTIFY_EMAIL | email to send digest to (can be same as GMAIL_USER) |
| ADZUNA_APP_ID | from Step 1 |
| ADZUNA_APP_KEY | from Step 1 |

### Step 4: Push to GitHub
```bash
git add .
git commit -m "Add automated job scraper workflow"
git push
```

The workflow runs automatically every day at 8am Pacific.
You can also trigger it manually from the Actions tab.

## Customization
Edit `scripts/job_scraper.py` to change:
- `JOB_KEYWORDS` — the roles you're searching for
- `LOCATIONS` — your target locations
