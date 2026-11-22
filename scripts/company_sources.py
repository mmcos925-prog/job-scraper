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
AMAZON_QUERIES = ["IT Support", "IT Support Associate", "Data Center Technician", "Help Desk", "Network Technician"]


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
# TEKsystems (Phenom career site)
# ---------------------------------------------------------------------------
TEK_QUERIES = ["help desk", "service desk", "desktop support", "IT support", "technical support",
               "NOC", "SOC", "Active Directory", "Entra", "access management"]


def fetch_teksystems():
    jobs = []
    for q in TEK_QUERIES:
        try:
            body = json.dumps({
                "lang": "en_us", "deviceType": "desktop", "country": "us", "pageName": "search-results",
                "ddoKey": "refineSearch", "sortBy": "Most recent", "subsearch": "", "from": 0, "jobs": True,
                "counts": True, "all_fields": ["category", "country", "state", "city", "type"], "size": 100,
                "clearAll": False, "jdsource": "facets", "isSliderEnable": False, "pageId": "page20",
                "siteType": "external", "keywords": q, "global": True,
                "selected_fields": {"state": ["California"]}, "locationData": {},
            }).encode()
            data = json.loads(_get("https://careers.teksystems.com/widgets", data=body,
                                   headers={"Content-Type": "application/json"}))
            for j in data.get("refineSearch", {}).get("data", {}).get("jobs", []):
                teaser = j.get("descriptionTeaser", "") or ""
                salary, sal_min = find_pay(teaser)
                jobs.append({
                    "title":       j.get("title", "").strip(),
                    "company":     "TEKsystems",
                    "location":    f"{j.get('city', '')}, CA".strip(", "),
                    "url":         f"https://careers.teksystems.com/us/en/job/{j.get('jobId', '')}",
                    "salary":      salary,
                    "salary_min":  sal_min,
                    "description": f"{teaser} {j.get('category', '')} {j.get('type', '')}".lower(),
                    "source":      "TEKsystems",
                })
        except Exception as e:
            print(f"  TEKsystems error ({q}): {e}")
    return jobs


# ---------------------------------------------------------------------------
# Kaiser Permanente (Radancy career site; it ignores location, so we filter by commute later)
# ---------------------------------------------------------------------------
KAISER_QUERIES = [("IT", 4), ("technician", 3), ("service desk", 1), ("desktop", 1)]  # (keyword, pages of 50)
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
