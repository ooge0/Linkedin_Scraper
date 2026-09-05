"""
utils.py

Utility functions used across the project.
"""

import random
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from loguru import logger


# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

logger.add(
    LOGS_DIR / "scraper.log",
    rotation="5 MB",
    retention=5,
    level="DEBUG",
)

logger.add(sys.stderr, level="DEBUG")


# ------------------------------------------------------------------------------
# Human-like delays
# ------------------------------------------------------------------------------

def random_sleep(min_sec: float = 2.0, max_sec: float = 4.0):
    """
    Sleep random amount of time.
    """
    time.sleep(random.uniform(min_sec, max_sec))


def long_break():
    """
    Longer pause after several pages.
    """
    seconds = random.randint(25, 60)

    logger.info(f"Long pause ({seconds} sec)")

    time.sleep(seconds)


# ------------------------------------------------------------------------------
# Mouse movement
# ------------------------------------------------------------------------------

def move_mouse_random(page):
    """
    Move mouse to a random screen position.
    """

    x = random.randint(150, 1200)
    y = random.randint(150, 700)

    page.mouse.move(
        x,
        y,
        steps=random.randint(10, 40)
    )


# ------------------------------------------------------------------------------
# Scroll
# ------------------------------------------------------------------------------

def human_scroll(page, min_steps: int = 2, max_steps: int = 9):
    """
    Scroll the page in small increments with random pauses. Occasionally
    skips entirely (user glanced and moved on), occasionally does a fast
    skim (short pauses), occasionally scrolls back up a bit at the end
    (user re-reads something) -- a fixed step range/pace every time is
    exactly the kind of predictable pattern that stands out.
    """

    if random.random() < 0.12:  # 12% chance: don't scroll at all
        logger.debug("human_scroll: skipped (glance behaviour)")
        return

    steps = random.randint(min_steps, max_steps)
    fast_skim = random.random() < 0.20  # 20% chance: quick skim, short pauses

    for _ in range(steps):
        distance = random.randint(120, 380)
        page.mouse.wheel(0, distance)
        if fast_skim:
            random_sleep(0.1, 0.3)
        else:
            random_sleep(0.4, 1.1)

    if random.random() < 0.15:  # 15% chance: scroll back up a bit
        page.mouse.wheel(0, -random.randint(200, 500))
        random_sleep(0.5, 1.2)


def maybe_distraction_pause():
    """
    With small probability, simulate the user tabbing away mid-session.
    Call once per card, after the detail panel has been read.
    """

    if random.random() < 0.07:  # ~7% per card -> roughly once per ~14 cards
        seconds = random.uniform(25, 75)
        logger.info(f"Distraction pause: {seconds:.0f}s (simulating tab-away)")
        time.sleep(seconds)


# ------------------------------------------------------------------------------
# Text helpers
# ------------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Remove duplicate spaces/newlines. Collapses real line breaks too --
    fine for single-line fields (title, company, location, ...), but do
    not use this on job descriptions: see clean_description().
    """

    if not text:
        return ""

    text = text.replace("\xa0", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def clean_description(text: str) -> str:
    """
    Like clean_text(), but preserves line breaks instead of flattening
    them to spaces.

    LinkedIn sometimes renders a job description as several separate <p>
    elements (one per paragraph) and sometimes as a single <p> with <br>
    tags for line breaks -- Playwright's inner_text() turns those <br>s
    into real "\\n" characters either way. clean_text()'s blanket
    \\s+ -> " " swallows those along with incidental whitespace, which is
    exactly right for a title/location but turns a single-<p> description
    into one unreadable run-on paragraph. This normalizes horizontal
    whitespace per line and collapses 3+ blank lines down to one, without
    touching intentional line/paragraph breaks.
    """

    if not text:
        return ""

    text = text.replace("\xa0", " ")

    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]

    cleaned_lines = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


APPLICANTS_PATTERN = re.compile(
    r"(over\s+)?\d[\d,]*\+?\s+(applicants?|people clicked apply)|be an early applicant",
    re.IGNORECASE,
)


def parse_location_meta(text: str) -> tuple[str, str, str]:
    """
    Split a top-card summary line ("Kyiv, Ukraine · 2 weeks ago · 16 applicants
    No response insights available yet") into (location_entity, posted, applicants).

    LinkedIn glues extra text onto the applicants segment with no delimiter
    (e.g. "Promoted by hirer", trailing insight blurbs) so that part is
    trimmed via regex rather than a plain split.
    """

    parts = [p.strip() for p in text.split("·") if p.strip()]

    location_entity = parts[0] if len(parts) > 0 else ""
    posted = parts[1] if len(parts) > 1 else ""
    applicants_raw = parts[2] if len(parts) > 2 else ""

    match = APPLICANTS_PATTERN.search(applicants_raw)
    applicants = match.group(0) if match else applicants_raw

    return location_entity, posted, applicants


def title_skip_reason(
    title: str,
    skip_keywords: list,
    must_keywords: list,
) -> Optional[str]:
    """
    Decide whether a card should be skipped based on its title alone,
    before ever opening the detail panel. Returns None if the card should
    be kept, or a short human-readable reason if it should be skipped.
    """

    lowered = (title or "").lower()

    if any(keyword.lower() in lowered for keyword in skip_keywords):
        return "title-skipped"

    if must_keywords and not any(keyword.lower() in lowered for keyword in must_keywords):
        return "no must-keyword match"

    return None


def extract_job_id(url: str) -> str:
    """
    Extract LinkedIn job id from url.

    Example

    https://www.linkedin.com/jobs/view/432123123/

    ->
    432123123
    """

    match = re.search(r"/view/(\d+)", url)

    if match:
        return match.group(1)

    current_job_id = parse_qs(urlparse(url).query).get("currentJobId", [""])[0]
    if current_job_id.isdigit():
        return current_job_id

    return ""


def build_job_url(job_id: str) -> str:
    """
    Canonical, stable LinkedIn job link built from a job id, e.g.

    "432123123" -> "https://www.linkedin.com/jobs/view/432123123/"

    Unlike the raw page URL captured during scraping (which carries
    transient search-context query params such as currentJobId/keywords/
    start), this link stays valid regardless of search context. Returns
    "" if job_id is empty.
    """

    if not job_id:
        return ""

    return f"https://www.linkedin.com/jobs/view/{job_id}/"


# ------------------------------------------------------------------------------
# File system
# ------------------------------------------------------------------------------

def ensure_output_dirs():
    """
    Create required folders.
    """

    Path("output").mkdir(exist_ok=True)
    Path("output/screenshots").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)


# ------------------------------------------------------------------------------
# Browser safety
# ------------------------------------------------------------------------------

def looks_like_blocked(page) -> bool:
    """
    Detect common LinkedIn blocking pages.

    Returns True if scraper should stop.
    """

    try:
        visible_text = clean_text(page.locator("body").inner_text()).lower()
    except Exception as exc:
        logger.warning("Could not inspect visible page text for block detection: {}", exc)
        return False

    keywords = [
        "security verification",
        "too many requests",
        "unusual activity",
        "confirm you are not a robot",
        "account restricted",
    ]

    matched_keyword = next(
        (keyword for keyword in keywords if keyword in visible_text),
        None,
    )
    if matched_keyword:
        logger.warning("Block detector matched visible text: {!r}", matched_keyword)
        return True

    logger.debug("Block detector found no blocking message in visible page text")
    return False


# ------------------------------------------------------------------------------
# Progress
# ------------------------------------------------------------------------------

def print_header(title: str):
    """
    Pretty console header.
    """

    logger.info("=" * 70)
    logger.info(title)
    logger.info("=" * 70)


def print_stats(stats):
    """
    Print scraper statistics.
    """

    logger.info("Finished")

    logger.info(f"Pages visited : {stats.pages_visited}")
    logger.info(f"Cards found   : {stats.cards_found}")
    logger.info(f"Jobs saved    : {stats.jobs_saved}")
    logger.info(f"Skipped       : {stats.jobs_skipped}")
    logger.info(f"Errors        : {stats.parsing_errors}")
    logger.info(f"Requests      : {stats.rate_limited_actions}")
    logger.info(f"Cards processed : {stats.cards_processed}")

    if stats.rate_limit_stopped:
        logger.info(
            "Stopped early: hourly request cap reached -- "
            "resume by re-running the same command."
        )

    if stats.card_limit_stopped:
        logger.info(
            "Stopped early: session card limit reached -- "
            "resume by re-running the same command."
        )

    if stats.session_expired:
        logger.info(
            "Stopped early: LinkedIn session expired -- "
            "run 'python login.py' or 'python runner.py --relogin' before the next scrape."
        )