"""
Searches three employers' own career sites directly, so their postings show up the day they go live:
Amazon (amazon.jobs), TEKsystems (careers.teksystems.com) and Kaiser Permanente (kaiserpermanentejobs.org).
Each fetcher returns jobs in the same shape as the other sources in job_scraper.py.
"""
import json
import re
import urllib.parse
import urllib.request
from html import unescape

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"
HOME_LAT, HOME_LON = 37.93187, -121.69579  # Brentwood, CA


def _get(url, headers=None, data=None, timeout=20):
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _text(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html or ""))).strip()


def find_pay(text):
    """Pull a pay range like '$27.64/hr - $37.74/hr' or '$55,000 - $70,000' out of free text."""
    m = re.search(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:/\s*h(?:ou)?r)?\s*(?:-|to|–)\s*\$\s?"
                  r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(/\s*h(?:ou)?r|per hour|/\s*year|per year|annually)?",
                  text or "", re.I)
    if not m:
        return "Not listed", 0
    lo, hi = (float(x.replace(",", "")) for x in m.groups()[:2])
    hourly = lo < 200
    fmt = (lambda v: f"${v:,.2f}/hr") if hourly else (lambda v: f"${v:,.0f}")
    return f"{fmt(lo)} - {fmt(hi)}", lo


# ---------------------------------------------------------------------------
# Amazon
# ---------------------------------------------------------------------------
AMAZON_QUERIES = ["IT Support", "IT Support Associate", "Data Center Technician", "Help Desk", "Network Technician",
                  # warehouse and operations roles near Brentwood (Tracy, Stockton, Livermore, etc.)
                  "Process Assistant", "Warehouse Associate", "Fulfillment Center", "Delivery Station",
                  "Transportation Associate", "Sortation", "Learning Ambassador"]


def fetch_amazon():
    jobs = []
    for q in AMAZON_QUERIES:
        try:
            params = urllib.parse.urlencode({
                "base_query": q, "latitude": HOME_LAT, "longitude": HOME_LON,
                "radius": "120km", "result_limit": 50, "sort": "recent",
            })
            data = json.loads(_get(f"https://www.amazon.jobs/en/search.json?{params}"))
            for j in data.get("jobs", []):
                desc = _text(" ".join([j.get("description_short", ""), j.get("basic_qualifications", ""),
                                        j.get("preferred_qualifications", ""), j.get("description", "")]))
                salary, sal_min = find_pay(desc)
                jobs.append({
                    "title":       j.get("title", "").strip(),
                    "company":     "Amazon",
                    "location":    j.get("normalized_location") or j.get("location") or "N/A",
                    "url":         "https://www.amazon.jobs" + j.get("job_path", ""),
                    "salary":      salary,
                    "salary_min":  sal_min,
                    "description": desc[:3000].lower(),
                    "source":      "Amazon Jobs",
                })
        except Exception as e:
            print(f"  Amazon error ({q}): {e}")
    return jobs


# ---------------------------------------------------------------------------
# Phenom career sites: TEKsystems and Sutter Health share the same search API
# ---------------------------------------------------------------------------
TEK_QUERIES = ["help desk", "service desk", "desktop support", "IT support", "technical support",
               "NOC", "SOC", "Active Directory", "Entra", "access management"]

# Entry-level, non-IT titles searched at the local employers (Kaiser, Sutter, John Muir, BART)
ENTRY_QUERIES = ["environmental services", "housekeeping", "custodian", "janitor", "receptionist",
                 "cashier", "patient access", "front desk", "clerk", "transporter", "food service",
                 "warehouse", "materials handler", "security officer", "electrician"]


def fetch_phenom(base, company, source, queries, size=100):
    jobs = []
    for q in queries:
        try:
            body = json.dumps({
                "lang": "en_us", "deviceType": "desktop", "country": "us", "pageName": "search-results",
                "ddoKey": "refineSearch", "sortBy": "Most recent", "subsearch": "", "from": 0, "jobs": True,
                "counts": True, "all_fields": ["category", "country", "state", "city", "type"], "size": size,
                "clearAll": False, "jdsource": "facets", "isSliderEnable": False, "pageId": "page20",
                "siteType": "external", "keywords": q, "global": True,
                "selected_fields": {"state": ["California"]}, "locationData": {},
            }).encode()
            data = json.loads(_get(f"{base}/widgets", data=body, headers={"Content-Type": "application/json"}))
            for j in data.get("refineSearch", {}).get("data", {}).get("jobs", []):
                teaser = j.get("descriptionTeaser", "") or ""
                salary, sal_min = find_pay(teaser)
                extras = " ".join(str(j.get(k, "") or "") for k in ("category", "type", "Shift", "department"))
                jobs.append({
                    "title":       j.get("title", "").strip(),
                    "company":     company,
                    "location":    f"{j.get('city', '')}, CA".strip(", "),
                    "url":         f"{base}/us/en/job/{j.get('jobId', '')}",
                    "salary":      salary,
                    "salary_min":  sal_min,
                    "description": f"{teaser} {extras}".lower(),
                    "source":      source,
                })
        except Exception as e:
            print(f"  {company} error ({q}): {e}")
    return jobs


def fetch_teksystems():
    return fetch_phenom("https://careers.teksystems.com", "TEKsystems", "TEKsystems", TEK_QUERIES)


def fetch_sutter():
    return fetch_phenom("https://jobs.sutterhealth.org", "Sutter Health", "Sutter Health Careers",
                        ENTRY_QUERIES + ["IT", "help desk", "service desk", "technician"])


# ---------------------------------------------------------------------------
# Kaiser Permanente (Radancy career site; it ignores location, so we filter by commute later)
# ---------------------------------------------------------------------------
KAISER_QUERIES = [("IT", 4), ("technician", 3), ("service desk", 1), ("desktop", 1)] + [(q, 2) for q in ENTRY_QUERIES]
# (keyword, pages of 50). Kaiser's search ignores location, so results are filtered by commute later.
KAISER_ROW = re.compile(r'<a href="(/job/[^"]+)"[^>]*>\s*<h2>(.*?)</h2>\s*<span class="job-location">(.*?)</span>', re.S)


def fetch_kaiser():
    jobs = []
    for q, pages in KAISER_QUERIES:
        for page in range(1, pages + 1):
            try:
                params = urllib.parse.urlencode({
                    "ActiveFacetID": 0, "CurrentPage": page, "RecordsPerPage": 50, "Distance": 50,
                    "RadiusUnitType": 0, "Keywords": q, "IsPagination": page > 1, "FacetType": 0,
                    "SearchResultsModuleName": "Search Results", "SearchFiltersModuleName": "Search Filters",
                    "SortCriteria": 0, "SortDirection": 0, "SearchType": 6, "OrganizationIds": 641, "ResultsType": 0,
                })
                data = json.loads(_get(f"https://www.kaiserpermanentejobs.org/search-jobs/results?{params}",
                                       headers={"X-Requested-With": "XMLHttpRequest"}))
                rows = KAISER_ROW.findall(data.get("results", ""))
                for href, title, meta in rows:
                    meta = _text(meta)  # e.g. "Pleasanton, CA, Flexible, Regular, Full-time, Day shift, 40 hours"
                    parts = [p.strip() for p in meta.split(",")]
                    city_state = ", ".join(parts[:2]) if len(parts) >= 2 else meta
                    work_type = parts[2] if len(parts) > 2 else ""
                    location = f"Remote ({city_state})" if work_type.lower() == "remote" else city_state
                    jobs.append({
                        "title":       _text(title),
                        "company":     "Kaiser Permanente",
                        "location":    location,
                        "url":         "https://www.kaiserpermanentejobs.org" + href,
                        "salary":      "Not listed",
                        "salary_min":  0,
                        "description": meta.lower(),
                        "source":      "Kaiser Careers",
                    })
                if len(rows) < 50:
                    break
            except Exception as e:
                print(f"  Kaiser error ({q} p{page}): {e}")
                break
    return jobs


# ---------------------------------------------------------------------------
# John Muir Health (Workday; small enough to read every posting)
# ---------------------------------------------------------------------------
def fetch_johnmuir():
    jobs, base = [], "https://jmh.wd5.myworkdayjobs.com"
    for offset in range(0, 400, 20):
        try:
            body = json.dumps({"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""}).encode()
            data = json.loads(_get(f"{base}/wday/cxs/jmh/JohnMuirHealthCareers/jobs", data=body,
                                   headers={"Content-Type": "application/json"}))
            posts = data.get("jobPostings", [])
            for p in posts:
                title = p.get("title", "")
                # Titles carry schedule details, e.g. "Medical Receptionist - Cardiology - Full Time - 8 Hour - Days"
                jobs.append({
                    "title":       title.split(" - ")[0].strip(),
                    "company":     "John Muir Health",
                    "location":    f"{p.get('locationsText', '')}, CA",
                    "url":         f"{base}/JohnMuirHealthCareers{p.get('externalPath', '')}",
                    "salary":      "Not listed",
                    "salary_min":  0,
                    "description": title.lower(),
                    "source":      "John Muir Health Careers",
                })
            if len(posts) < 20 or offset + 20 >= data.get("total", 0):
                break
        except Exception as e:
            print(f"  John Muir error (offset {offset}): {e}")
            break
    return jobs


# ---------------------------------------------------------------------------
# BART (GovernmentJobs.com / NEOGOV)
# ---------------------------------------------------------------------------
BART_ROW = re.compile(r'<li class="list-item"[^>]*>.*?href="(/careers/bartca/jobs/[^"]+)"[^>]*>(.*?)</a>'
                      r'.*?<ul class="list-meta">(.*?)</ul>.*?<div class="list-entry">(.*?)</div>', re.S)
BART_SITES = [("met", "Oakland, CA"), ("headquarters", "Oakland, CA"), ("hayward", "Hayward, CA"),
              ("concord", "Concord, CA"), ("richmond", "Richmond, CA"), ("daly city", "Daly City, CA"),
              ("pittsburg", "Pittsburg, CA"), ("antioch", "Antioch, CA"), ("oakland", "Oakland, CA")]


def fetch_bart():
    jobs, seen = [], set()
    for page in range(1, 6):
        try:
            html = _get(f"https://www.governmentjobs.com/careers/home/index?agency=bartca&sort=PostingDate"
                        f"&isDescendingSort=true&page={page}", headers={"X-Requested-With": "XMLHttpRequest"})
            rows = BART_ROW.findall(html)
            new = [r for r in rows if r[0] not in seen]
            if not new:
                break
            for href, title, meta, entry in new:
                seen.add(href)
                items = [_text(x) for x in re.findall(r"<li[^>]*>(.*?)</li>", meta, re.S)]
                site = items[0] if items else ""
                pay_line = next((x for x in items if "$" in x), "")
                salary, sal_min = find_pay(pay_line)
                loc = next((city for key, city in BART_SITES if key in site.lower()), "Bay Area (BART)")
                jobs.append({
                    "title":       _text(title),
                    "company":     "BART",
                    "location":    loc,
                    "url":         "https://www.governmentjobs.com" + href,
                    "salary":      salary,
                    "salary_min":  sal_min,
                    "description": f"{' '.join(items)} {_text(entry)[:1500]}".lower(),
                    "source":      "BART Careers",
                })
        except Exception as e:
            print(f"  BART error (page {page}): {e}")
            break
    return jobs
