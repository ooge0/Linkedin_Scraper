"""
config.py

Central configuration for the LinkedIn vacancy scraper.
Edit the values below, everything else (SEARCH_URL) is derived automatically.
"""

from urllib.parse import urlencode

# ----------------------------------------------------------------------
# Search parameters
# ----------------------------------------------------------------------

SEARCH_KEYWORD = "general QA"
SEARCH_LOCATION = "Remote"

# Optional LinkedIn search filters
REMOTE_ONLY = False          # f_WT=2  -> remote jobs only
EASY_APPLY = False           # f_AL=true
POSTED_LAST_24H = False      # f_TPR=r86400
POSTED_LAST_WEEK = False     # f_TPR=r604800 (ignored if POSTED_LAST_24H is True)

# ----------------------------------------------------------------------
# Forced search region (LinkedIn geoId)
# ----------------------------------------------------------------------
# LinkedIn's location box doesn't reliably use SEARCH_LOCATION above --
# when the free-text value doesn't resolve to a real place, LinkedIn
# silently falls back to the browser/account's detected location (e.g.
# showing "Ukraine" regardless of what was typed). Passing a matching
# geoId pins the search to one of the regions below no matter what.
# Set FORM_LOCATION to "" to disable and rely on SEARCH_LOCATION alone.
GEO_ID_BY_REGION = {
    "Worldwide": "92000000",
    "European Union": "91000000",
}

FORM_LOCATION = "European Union"     # must be "" or a key in GEO_ID_BY_REGION

# ----------------------------------------------------------------------
# Scraper behaviour
# ----------------------------------------------------------------------

MAX_PAGES = 5
HEADLESS = True

# Hard safety backstop for large runs (e.g. 100 pages) -- not the primary
# pacing mechanism (that's the random_sleep/long_break calls in utils.py).
# A sliding one-hour window of "job detail panel opened" actions; once hit,
# the run stops gracefully and can simply be re-run later (dedup skips
# already-saved jobs, so nothing is lost by stopping early).
REQUESTS_PER_HOUR = 150

# Second, independent safety cap: total cards looked at (clicked OR
# skipped) in a single session, regardless of how much time that took.
# Bounds session length/shape itself, not just the hourly click rate.
MAX_CARDS_PER_SESSION = 40

# Skip a card without clicking it if its title contains any of these
# (case-insensitive). Mimics a human skimming past obviously-irrelevant
# titles, and means fewer detail-panel opens overall.
TITLE_SKIP_KEYWORDS = ["junior", "intern", "internship", "graduate", "trainee"]

# Skip a card if its title contains NONE of these (must match at least
# one to be kept). Leave empty [] to disable this must-match filter.
TITLE_MUST_KEYWORDS = []

# ----------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------

OUTPUT_CSV = "output/jobs.csv"
OUTPUT_JSON = "output/jobs.json"
OUTPUT_DB = "output/jobs.db"
OUTPUT_SCREENSHOTS_DIR = "output/screenshots"
USER_DATA_DIR = "./user_data"


# ----------------------------------------------------------------------
# Build the LinkedIn search URL from the parameters above
# ----------------------------------------------------------------------

def build_search_url() -> str:
    """
    Turns the parameters above into a LinkedIn jobs search URL, e.g.

    https://www.linkedin.com/jobs/search/?keywords=LLM+Evaluation&location=Remote&f_WT=2
    """

    params = {
        "keywords": SEARCH_KEYWORD,
        "location": SEARCH_LOCATION,
    }

    if FORM_LOCATION:
        try:
            params["geoId"] = GEO_ID_BY_REGION[FORM_LOCATION]
        except KeyError:
            raise ValueError(
                f"Unknown FORM_LOCATION {FORM_LOCATION!r}. "
                f"Choose one of: {', '.join(GEO_ID_BY_REGION)!r} or \"\"."
            )

    if REMOTE_ONLY:
        params["f_WT"] = "2"

    if EASY_APPLY:
        params["f_AL"] = "true"

    if POSTED_LAST_24H:
        params["f_TPR"] = "r86400"
    elif POSTED_LAST_WEEK:
        params["f_TPR"] = "r604800"

    return "https://www.linkedin.com/jobs/search/?" + urlencode(params)


SEARCH_URL = build_search_url()