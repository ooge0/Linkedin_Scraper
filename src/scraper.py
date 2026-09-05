"""
scraper.py

LinkedIn vacancy scraper with verbose debug logging.
Every selector attempt, count result, and page state is logged
so you can pinpoint broken locators immediately.
"""

import random
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from loguru import logger
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config import (
    SEARCH_URL,
    SEARCH_KEYWORD,
    SEARCH_LOCATION,
    USER_DATA_DIR,
    MAX_PAGES,
    HEADLESS,
    OUTPUT_SCREENSHOTS_DIR,
    REQUESTS_PER_HOUR,
    MAX_CARDS_PER_SESSION,
    TITLE_SKIP_KEYWORDS,
    TITLE_MUST_KEYWORDS,
)
from database import Database
from models import Job, ScraperStats
from rate_limiter import RateLimiter
from utils import (
    random_sleep,
    human_scroll,
    move_mouse_random,
    long_break,
    print_header,
    clean_text,
    clean_description,
    extract_job_id,
    looks_like_blocked,
    ensure_output_dirs,
    parse_location_meta,
    title_skip_reason,
    maybe_distraction_pause,
    build_job_url,
)

# ----------------------------------------------------------------------
# Selectors
# ----------------------------------------------------------------------

CARD_SELECTOR       = "div.job-card-container"
CARD_TITLE_SELECTOR = "a.job-card-list__title--link"
NEXT_PAGE_SELECTOR  = "button[aria-label*='Next'], button:has-text('Next')"
TITLE_SELECTOR      = "h1.job-details-jobs-unified-top-card__job-title"
COMPANY_SELECTOR    = "div.job-details-jobs-unified-top-card__company-name"
COMPANY_URL_SELECTORS = (
    # Standard (non-promoted) job detail panel — old BEM naming
    "div.job-details-jobs-unified-top-card__company-name a",
    # Promoted-job panel — classes are hash-obfuscated, but the company
    # block keeps a stable aria-label and the href always contains /company/
    "div[aria-label^='Company,'] a[href*='/company/']",
    # Last resort: any link to a company page, anywhere on the panel
    "a[href*='/company/']",
)
LOCATION_SELECTOR   = "div.job-details-jobs-unified-top-card__primary-description-container"
SHOW_MORE_SELECTOR  = "button.jobs-description__footer-button"
DESCRIPTION_SELECTORS = (
    "[id^='JobDetails_AboutTheJob_'] p",
    "[class*='jobs-description__content'] p",
    "[class*='jobs-description-content__text'] p",
)


def description_selector(job_id: str) -> str:
    return f"#JobDetails_AboutTheJob_{job_id} > div > div > div > div > p"


# ----------------------------------------------------------------------
# Debug helpers
# ----------------------------------------------------------------------

def _try_text(page, selector: str, label: str) -> str:
    """
    Locate selector, log how many matches were found, return inner_text
    of the first match. Returns "" and logs a WARNING if nothing found.
    """
    loc = page.locator(selector)
    count = loc.count()
    if count == 0:
        logger.warning(f"  SELECTOR MISS  [{label}]  -> 0 matches  |  {selector}")
        return ""
    if count > 1:
        logger.debug(f"  SELECTOR HIT   [{label}]  -> {count} matches (using first)  |  {selector}")
    else:
        logger.debug(f"  SELECTOR HIT   [{label}]  -> 1 match  |  {selector}")
    text = clean_text(loc.first.inner_text())
    logger.debug(f"  VALUE          [{label}]  -> {text[:120]!r}")
    return text


def _session_expired(page) -> bool:
    """
    LinkedIn redirects to /login or /checkpoint (2FA / device verification)
    once the persistent session cookie has expired or been challenged.
    Checking page.url is far cheaper than looks_like_blocked()'s full-page
    text scan, and catches session death before wasting a page's worth of
    card clicks on a login wall.
    """
    return "/login" in page.url or "/checkpoint" in page.url


def _wait_for_cards(page, timeout: int = 10_000) -> bool:
    """
    Wait until at least one job card is present, instead of hoping a fixed
    sleep was long enough. Returns False (without raising) on timeout --
    the caller's own "no cards found" / blocked-page checks give a better
    diagnosis than a bare Playwright stack trace would.
    """
    try:
        page.wait_for_selector(CARD_SELECTOR, timeout=timeout)
        random_sleep(0.5, 1.5)
        return True
    except PlaywrightTimeoutError:
        logger.warning(f"  Timed out waiting for job cards to appear ({CARD_SELECTOR})")
        return False


def _wait_for_detail_panel(page, timeout: int = 10_000) -> bool:
    """
    Wait until the job detail panel has rendered enough to be parsed. Waits
    on bare 'h1' rather than TITLE_SELECTOR's BEM class -- parse_job's own
    _try_text() falls back to the same bare tag when LinkedIn omits the BEM
    class (promoted listings do this often), so pinning the wait to the
    BEM-only selector would time out on exactly the pages that need it most.
    """
    try:
        page.wait_for_selector("h1", timeout=timeout)
        random_sleep(0.5, 1.5)
        return True
    except PlaywrightTimeoutError:
        logger.warning("  Timed out waiting for job detail panel (h1) to render")
        return False


def _dump_page_snapshot(page, label: str):
    """
    Log the current URL and the first 600 chars of page text so you can
    see what LinkedIn actually returned.
    """
    logger.debug(f"--- PAGE SNAPSHOT [{label}] ---")
    logger.debug(f"  URL : {page.url}")
    try:
        body_text = clean_text(page.locator("body").inner_text())[:600]
        logger.debug(f"  BODY: {body_text!r}")
    except Exception as e:
        logger.debug(f"  BODY: (could not read) {e}")


def _scroll_results_panel(page, target_job_id=None) -> bool:
    """Scroll the virtualized results panel and optionally locate a job card."""
    script = """
    (card, targetJobId) => {
        let panel = card;
        while (panel.parentElement) {
            const style = window.getComputedStyle(panel);
            const scrollable = panel.scrollHeight > panel.clientHeight + 2 &&
                (style.overflowY === 'auto' || style.overflowY === 'scroll');
            if (scrollable) {
                if (targetJobId) {
                    const target = panel.querySelector(
                        `[data-job-id="${targetJobId}"]`
                    );
                    if (target) {
                        target.scrollIntoView({block: 'center'});
                        return {found: true, atEnd: false};
                    }
                }
                const distance = Math.max(300, Math.floor(panel.clientHeight * 0.8));
                panel.scrollTop = Math.min(panel.scrollTop + distance, panel.scrollHeight);
                return {found: false, atEnd: panel.scrollTop + panel.clientHeight >= panel.scrollHeight - 2};
            }
            panel = panel.parentElement;
        }
        return {found: false, atEnd: true};
    }
    """
    cards = page.locator(CARD_SELECTOR)
    if not cards.count():
        return False
    result = cards.first.evaluate(script, target_job_id)
    return result["found"] or not result["atEnd"]


def _collect_all_card_ids(page) -> list[str]:
    """Collect IDs from all virtualized result-panel positions on one page."""
    card_ids = set()
    previous_signature = None

    for _ in range(100):
        cards = page.locator(CARD_SELECTOR)
        for index in range(cards.count()):
            job_id = cards.nth(index).get_attribute("data-job-id") or ""
            if job_id:
                card_ids.add(job_id)

        signature = (len(card_ids), cards.count())
        if signature == previous_signature:
            break
        previous_signature = signature

        if _scroll_results_panel(page):
            random_sleep(0.5, 1.0)
        else:
            break

    return list(card_ids)


def _find_card_by_id(page, job_id: str):
    """Scroll the virtualized panel until the requested card is rendered."""
    selector = f'{CARD_SELECTOR}[data-job-id="{job_id}"]'
    for _ in range(100):
        card = page.locator(selector).first
        if card.count():
            return card
        if not _scroll_results_panel(page):
            break
        random_sleep(0.5, 1.0)
    return None


def _results_url(url: str) -> str:
    """Remove the selected-job parameter while preserving the result batch."""
    parsed = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query)
             if key != "currentJobId"]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                       urlencode(query), parsed.fragment))


# ----------------------------------------------------------------------


class Scraper:

    def __init__(self, max_pages=None):
        self.db = Database()
        self.stats = ScraperStats()
        self.max_pages = max_pages if max_pages is not None else MAX_PAGES
        self.rate_limiter = RateLimiter(REQUESTS_PER_HOUR)

    # ------------------------------------------------------------------

    def _save_debug_screenshot(self, page):
        """
        Overwrite a single screenshot of the first loaded page, purely
        for eyeballing what the scraper actually saw during a run.
        """
        ensure_output_dirs()
        screenshot_path = Path(OUTPUT_SCREENSHOTS_DIR) / "initial_page.png"
        try:
            page.screenshot(path=str(screenshot_path))
            logger.info(f"Saved debug screenshot -> {screenshot_path}")
        except Exception as exc:
            logger.warning(f"Could not capture debug screenshot: {exc}")

    # ------------------------------------------------------------------

    def run(self):
        logger.info(f"Search URL : {SEARCH_URL}")
        logger.info(f"Max pages  : {self.max_pages}")
        logger.info(f"Headless   : {HEADLESS}")
        logger.info(f"User data  : {USER_DATA_DIR}")

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=HEADLESS,
                channel="chrome",
            )
            page = browser.new_page()
            print_header("Starting scraper")

            logger.info(f"Navigating to search URL...")
            page.goto(SEARCH_URL)
            page.wait_for_load_state("domcontentloaded")
            _wait_for_cards(page)
            logger.info(f"Page loaded. Current URL: {page.url}")
            _dump_page_snapshot(page, "after initial load")
            self._save_debug_screenshot(page)
            random_sleep()

            for current_page in range(self.max_pages):
                logger.info(f"========== PAGE {current_page + 1} / {self.max_pages} ==========")
                self.stats.pages_visited += 1

                if _session_expired(page):
                    logger.error(
                        f"Session expired — LinkedIn redirected to {page.url!r}. "
                        f"Re-run 'python login.py' (or 'python runner.py --relogin')."
                    )
                    self.stats.session_expired = True
                    break

                if looks_like_blocked(page):
                    logger.error("Blocked / captcha page detected — stopping.")
                    _dump_page_snapshot(page, "blocked")
                    break

                logger.info(
                    "DOM diagnostics: rendered cards={}, data-job-id elements={}",
                    page.locator(CARD_SELECTOR).count(),
                    page.locator("[data-job-id]").count(),
                )
                if self.collect_cards(page):
                    if self.stats.card_limit_stopped:
                        logger.warning(
                            f"Run stopped early: session card limit reached "
                            f"({MAX_CARDS_PER_SESSION}). Re-run the same command "
                            f"to resume — already-saved jobs are skipped automatically."
                        )
                    else:
                        logger.warning(
                            "Run stopped early: hourly request cap reached. "
                            "Re-run the same command to resume — already-saved "
                            "jobs are skipped automatically."
                        )
                    break

                if current_page + 1 >= self.max_pages:
                    logger.info("Requested page limit reached — scrape complete.")
                    break

                # Randomly leave early after at least a few pages (simulates a
                # human losing interest rather than mechanically finishing
                # every run at exactly the same length).
                if current_page >= 2 and random.random() < 0.15:
                    logger.info("Early exit: simulating user leaving before last page.")
                    break

                if not self.goto_next_page(page):
                    logger.info("No next page found — scrape complete.")
                    break

                if (current_page + 1) % 3 == 0:
                    long_break()

            browser.close()
            logger.info("Browser closed.")

    # ------------------------------------------------------------------

    def collect_cards(self, page) -> bool:
        """
        Opens the detail panel for each not-yet-saved card on this page.

        Returns True if the hourly request cap was hit and the run should
        stop (the caller breaks out of the page loop); False otherwise.
        """
        logger.debug(f"Locating job cards with: {CARD_SELECTOR!r}")
        results_url = _results_url(page.url)
        job_cards = page.locator(CARD_SELECTOR)
        count = job_cards.count()

        if count == 0:
            logger.warning(
                f"No job cards found on this page!\n"
                f"  Selector used : {CARD_SELECTOR}\n"
                f"  Current URL   : {page.url}\n"
                f"  This usually means the selector is wrong or LinkedIn\n"
                f"  returned a redirect / auth wall. Check the snapshot below."
            )
            _dump_page_snapshot(page, "no cards found")
            return False

        card_ids = _collect_all_card_ids(page)
        self.stats.cards_found += len(card_ids)
        logger.info(
            f"Found {len(card_ids)} job cards across the scrollable results panel "
            f"({count} rendered initially)"
        )

        for index, job_id in enumerate(card_ids):
            logger.debug(f"  Card {index + 1}/{len(card_ids)}: data-job-id={job_id!r}")

            if self.stats.cards_processed >= MAX_CARDS_PER_SESSION:
                logger.info(
                    f"Session card limit reached ({MAX_CARDS_PER_SESSION}), stopping."
                )
                self.stats.card_limit_stopped = True
                return True
            self.stats.cards_processed += 1

            if not job_id:
                logger.warning(
                    f"  Card {index + 1}: data-job-id attribute missing, skipping"
                )
                self.stats.parsing_errors += 1
                continue

            if self.db.job_exists(job_id):
                logger.info(f"  Card {index + 1}: already in DB, skipping ({job_id})")
                self.stats.jobs_skipped += 1
                continue

            card = _find_card_by_id(page, job_id)
            if card is None:
                logger.warning(
                    f"  Card {index + 1}: job card disappeared after reload, skipping ({job_id})"
                )
                self.stats.parsing_errors += 1
                continue

            title_el = card.locator(CARD_TITLE_SELECTOR)
            if title_el.count() > 0:
                card_title = title_el.first.inner_text().strip()
                skip_reason = title_skip_reason(
                    card_title, TITLE_SKIP_KEYWORDS, TITLE_MUST_KEYWORDS
                )
                if skip_reason:
                    logger.info(
                        f"  Card {index + 1}: {skip_reason} ({card_title[:60]!r})"
                    )
                    self.stats.jobs_skipped += 1
                    continue

            if not self.rate_limiter.allowed():
                logger.warning(
                    f"Hourly request cap reached ({REQUESTS_PER_HOUR}/hr) — stopping gracefully."
                )
                self.stats.rate_limit_stopped = True
                return True

            move_mouse_random(page)
            random_sleep()

            try:
                card.scroll_into_view_if_needed(timeout=5_000)
                card.click(timeout=10_000)
                self.rate_limiter.record()
                self.stats.rate_limited_actions += 1
            except Exception as e:
                logger.error(f"  Card {index + 1}: click failed — {e}")
                self.stats.parsing_errors += 1
                continue

            page.wait_for_load_state("domcontentloaded")
            _wait_for_detail_panel(page)
            logger.debug(f"  Card {index + 1}: page loaded -> {page.url}")
            human_scroll(page)
            random_sleep()

            job = self.parse_job(page)

            if job.job_id:
                self.db.insert_job(job)
                self.stats.jobs_saved += 1
                logger.info(
                    f"  Card {index + 1}: SAVED  {job.title!r} @ {job.company!r} ({job.job_id})"
                )
            else:
                logger.warning(
                    f"  Card {index + 1}: job_id missing after parse — not saved. URL: {page.url}"
                )
                self.stats.parsing_errors += 1

            maybe_distraction_pause()

            logger.debug(f"  Card {index + 1}: reloading search results...")
            page.goto(results_url)
            page.wait_for_load_state("domcontentloaded")
            _wait_for_cards(page)

        return False

    # ------------------------------------------------------------------

    def parse_job(self, page) -> Job:
        job = Job()
        logger.debug(f"  parse_job: start — {page.url}")

        try:
            job.url     = page.url
            job.job_id  = extract_job_id(page.url)
            job.job_url = build_job_url(job.job_id)
            logger.debug(f"  parse_job: job_id={job.job_id!r}")

            job.search_keyword  = SEARCH_KEYWORD
            job.search_location = SEARCH_LOCATION

            job.title    = _try_text(page, TITLE_SELECTOR,    "title")
            if not job.title:
                job.title = _try_text(page, "h1", "title fallback")
            job.company  = _try_text(page, COMPANY_SELECTOR,  "company")
            job.location = _try_text(page, LOCATION_SELECTOR, "location")
            job.location_entity, job.posted, job.applicants = parse_location_meta(job.location)
            logger.debug(
                f"  parse_job: location_entity={job.location_entity!r}  "
                f"posted={job.posted!r}  applicants={job.applicants!r}"
            )

            for candidate in COMPANY_URL_SELECTORS:
                candidate_loc = page.locator(candidate)
                candidate_count = candidate_loc.count()
                logger.debug(
                    f"  parse_job: company_url candidate count={candidate_count}  |  {candidate}"
                )
                if candidate_count:
                    job.company_url = candidate_loc.first.get_attribute("href") or ""
                    logger.debug(f"  parse_job: company_url={job.company_url!r}")
                    break

            # Expand description if collapsed
            show_more = page.locator(SHOW_MORE_SELECTOR)
            sm_count = show_more.count()
            logger.debug(f"  parse_job: 'show more' button count={sm_count}  |  {SHOW_MORE_SELECTOR}")
            if sm_count > 0:
                show_more.first.click()
                logger.debug("  parse_job: clicked 'show more'")
                random_sleep(0.5, 1.0)

            desc_loc = None
            desc_sel = ""
            p_count = 0
            for candidate in DESCRIPTION_SELECTORS:
                candidate_loc = page.locator(candidate)
                candidate_count = candidate_loc.count()
                logger.debug(
                    f"  parse_job: description candidate count={candidate_count}  |  {candidate}"
                )
                if candidate_count:
                    desc_loc = candidate_loc
                    desc_sel = candidate
                    p_count = candidate_count
                    break

            if p_count == 0:
                logger.warning(
                    f"  parse_job: description selector returned 0 elements!\n"
                    f"    Selectors: {DESCRIPTION_SELECTORS}\n"
                    f"    job_id   : {job.job_id}\n"
                    f"    Hint     : open DevTools on the job page, inspect the\n"
                    f"               description div and verify the id attribute\n"
                    f"               matches '#JobDetails_AboutTheJob_{{job_id}}'."
                )
                _dump_page_snapshot(page, "description miss")
            else:
                paragraphs = [
                    clean_description(desc_loc.nth(i).inner_text())
                    for i in range(p_count)
                ]
                job.description = "\n\n".join(p for p in paragraphs if p)
                logger.debug(f"  parse_job: description length={len(job.description)} chars")

        except Exception as ex:
            logger.exception(f"  parse_job: unexpected error — {ex}")
            self.stats.parsing_errors += 1

        return job

    # ------------------------------------------------------------------

    def goto_next_page(self, page) -> bool:
        logger.debug(f"  next_page: locating button  |  {NEXT_PAGE_SELECTOR}")
        next_button = page.locator(NEXT_PAGE_SELECTOR)
        count = next_button.count()
        logger.debug(f"  next_page: button count={count}")

        if count == 0:
            logger.info("  next_page: button not found — last page reached.")
            return False

        move_mouse_random(page)
        random_sleep()
        next_button.first.scroll_into_view_if_needed(timeout=5_000)
        next_button.click()
        page.wait_for_load_state("domcontentloaded")
        _wait_for_cards(page)
        logger.info(f"  next_page: navigated -> {page.url}")
        return True


# ----------------------------------------------------------------------

if __name__ == "__main__":
    Scraper().run()