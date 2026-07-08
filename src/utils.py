"""
utils.py

Utility functions used across the project.
"""

import random
import re
import time
from pathlib import Path

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
    level="INFO",
)


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

def human_scroll(page):
    """
    Slowly scroll page.
    """

    for _ in range(random.randint(3, 7)):

        pixels = random.randint(250, 700)

        page.mouse.wheel(0, pixels)

        random_sleep(0.4, 1.2)


# ------------------------------------------------------------------------------
# Text helpers
# ------------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Remove duplicate spaces/newlines.
    """

    if not text:
        return ""

    text = text.replace("\xa0", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


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

    return ""


# ------------------------------------------------------------------------------
# File system
# ------------------------------------------------------------------------------

def ensure_output_dirs():
    """
    Create required folders.
    """

    Path("output").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)


# ------------------------------------------------------------------------------
# Browser safety
# ------------------------------------------------------------------------------

def looks_like_blocked(page) -> bool:
    """
    Detect common LinkedIn blocking pages.

    Returns True if scraper should stop.
    """

    html = page.content().lower()

    keywords = [
        "verify",
        "captcha",
        "security verification",
        "too many requests",
        "unusual activity",
    ]

    return any(word in html for word in keywords)


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