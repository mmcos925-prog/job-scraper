"""
Commute and pay helpers for the digest.

Drive times are rough, no-traffic estimates from Brentwood, CA. Rush hour can add a lot,
especially toward Oakland, San Francisco and the South Bay.
"""
import re

MAX_COMMUTE_MIN = 90  # on-site California jobs farther than this are filtered out

COMMUTE_MIN = {
    "brentwood": 0, "oakley": 10, "discovery bay": 15, "byron": 15, "knightsen": 10,
    "antioch": 15, "pittsburg": 20, "bay point": 25, "mountain house": 25, "tracy": 30,
    "clayton": 30, "concord": 30, "rio vista": 35, "livermore": 35, "danville": 35,
    "martinez": 35, "pleasant hill": 35, "walnut creek": 35, "benicia": 40, "dublin": 40,
    "pleasanton": 40, "san ramon": 40, "lafayette": 40, "lathrop": 40, "orinda": 45,
    "moraga": 45, "stockton": 45, "manteca": 45, "fairfield": 50, "suisun city": 50,
    "vallejo": 50, "american canyon": 50, "hercules": 50, "pinole": 50, "richmond": 50,
    "el cerrito": 50, "castro valley": 50, "hayward": 55, "oakland": 55, "berkeley": 55,
    "emeryville": 55, "alameda": 55, "san leandro": 55, "union city": 60, "fremont": 60,
    "vacaville": 60, "modesto": 60, "napa": 60, "lodi": 55, "patterson": 55, "newark": 65,
    "milpitas": 70, "san francisco": 75, "south san francisco": 80, "sacramento": 75,
    "elk grove": 70, "san jose": 80, "santa clara": 80, "san mateo": 85, "sunnyvale": 85,
    "foster city": 85, "redwood city": 90, "mountain view": 90, "palo alto": 90, "menlo park": 90,
    "cupertino": 90, "san rafael": 70, "folsom": 90, "roseville": 90, "rancho cordova": 80,
}

# Longest names first, so "south san francisco" wins over "san francisco".
_CITIES = sorted(COMMUTE_MIN, key=len, reverse=True)


def is_remote(location):
    loc = (location or "").lower()
    return ("remote" in loc or "telework" in loc) and "hybrid" not in loc


def commute_minutes(location):
    """Approximate one-way drive in minutes, or None if remote or not a known city."""
    loc = (location or "").lower()
    if is_remote(loc):
        return None
    for city in _CITIES:
        if re.search(rf"\b{re.escape(city)}\b", loc):
            return COMMUTE_MIN[city]
    return None


def is_california_onsite(location):
    loc = (location or "").lower()
    return not is_remote(loc) and (re.search(r",\s*ca\b", loc) or "california" in loc)


def too_far(location):
    """True for on-site California jobs that aren't within MAX_COMMUTE_MIN of Brentwood."""
    if not is_california_onsite(location):
        return False
    mins = commute_minutes(location)
    return mins is None or mins > MAX_COMMUTE_MIN


def commute_label(location):
    if is_remote(location):
        return "Remote"
    mins = commute_minutes(location)
    if mins is None:
        return ""
    if mins == 0:
        return "In Brentwood"
    return f"~{mins} min drive from Brentwood"


def annual_from(salary_min):
    """Treat small numbers as hourly pay and convert to yearly (40 hrs x 52 weeks)."""
    if not salary_min:
        return 0
    return salary_min * 2080 if salary_min < 200 else salary_min


def pay_label(salary, salary_min):
    """Show pay both ways so hourly and yearly jobs can be compared."""
    if not salary_min:
        return salary or "Not listed"
    if salary_min < 200:
        return f"{salary} (about ${salary_min * 2080:,.0f}/yr full-time)"
    return f"{salary} (about ${salary_min / 2080:,.2f}/hr)"
