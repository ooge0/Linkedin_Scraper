"""
runner.py

Entry point for the LinkedIn vacancy scraper.

Workflow
--------
1. Check that a logged-in browser profile exists in USER_DATA_DIR.
   (Created by running `python login.py` once and logging in manually.)
   If missing -> stop and tell the user to log in first.
2. Run the Playwright scraper (scraper.py):
     open search URL -> collect job cards -> open each job ->
     parse fields -> save to SQLite -> next page -> repeat until
     MAX_PAGES or no next page.
3. Export everything currently stored in the DB to CSV.
4. Print run statistics (pages visited, jobs saved, errors, duration).

Usage
-----
    python login.py                       # once, to create/refresh the session
    python runner.py                      # every time you want to scrape
    python runner.py --relogin            # refresh an expired session, then scrape
    python runner.py --since 2026-09-01   # export only jobs scraped since this date
    python runner.py --json               # also export output/jobs.json
"""

import csv
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Make sure the project root is on the path regardless of how the
# script is launched (e.g. via venv, IDE, or direct python call).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import USER_DATA_DIR, OUTPUT_CSV, OUTPUT_JSON
from database import Database
from login import main as run_login_flow
from scraper import Scraper
from scoring import recalculate_all_scores
from models import ScraperStats
from utils import ensure_output_dirs, print_header, print_stats

CSV_FIELDS = [
    "job_id", "url", "job_url", "search_keyword", "search_location", "title", "company",
    "company_url", "location", "location_entity", "salary", "posted",
    "employment_type", "seniority", "workplace_type", "company_size",
    "industry", "applicants", "description", "skills", "scraped_at",
    "application_status", "notes", "match_score",
]


# ----------------------------------------------------------------------

def has_session() -> bool:
    """
    Rough check that login.py has already been run: the persistent
    context folder exists and isn't empty.
    """
    user_data_path = Path(USER_DATA_DIR)
    return user_data_path.exists() and any(user_data_path.iterdir())


# ----------------------------------------------------------------------

def _rows_to_export(db: Database, since: Optional[datetime] = None):
    """
    Rows for export_csv()/export_json(). job_id is UNIQUE in the DB, so
    this is already deduplicated -- and since both exports overwrite their
    file from scratch every call, reruns never append or drift out of sync
    with what's actually in the DB.
    """
    return db.get_jobs_since(since) if since else db.get_all_jobs()


def export_csv(db: Database, path: str, since: Optional[datetime] = None) -> int:
    """
    Dump jobs currently in the DB to a CSV file (optionally limited to jobs
    scraped at or after `since`). Returns the number of rows written.
    """
    ensure_output_dirs()

    rows = _rows_to_export(db, since)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in CSV_FIELDS})

    return len(rows)


def export_json(db: Database, path: str, since: Optional[datetime] = None) -> int:
    """
    Dump the same row set as export_csv(), as a JSON array of objects, for
    downstream pipeline consumption. Returns the number of rows written.
    """
    ensure_output_dirs()

    rows = _rows_to_export(db, since)

    with open(path, "w", encoding="utf-8") as f:
        json.dump([dict(row) for row in rows], f, indent=2, ensure_ascii=False)

    return len(rows)


def finalize_stats(scraper: Scraper) -> ScraperStats:
    """Mark the scraper run complete and return its live statistics."""
    scraper.stats.end_time = datetime.utcnow()
    return scraper.stats


# ----------------------------------------------------------------------

def _parse_since(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--since must be an ISO date or datetime "
            f"(e.g. 2026-09-01 or '2026-09-01 14:30:00'), got {value!r}"
        )


def parse_args():
    parser = argparse.ArgumentParser(description="Scrape LinkedIn job result pages.")
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="Number of LinkedIn result pages to scrape (default: config MAX_PAGES).",
    )
    parser.add_argument(
        "--relogin",
        action="store_true",
        help="Run the manual login flow (opens a visible Chrome window) before scraping. "
             "Use this when a previous run reported an expired session.",
    )
    parser.add_argument(
        "--since",
        type=_parse_since,
        default=None,
        help="Only export jobs scraped at or after this ISO date/datetime "
             "(e.g. 2026-09-01). Does not affect what gets scraped, only the export.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=f"Also export the same jobs as JSON, to {OUTPUT_JSON!r}.",
    )
    args = parser.parse_args()
    if args.pages is not None and args.pages < 1:
        parser.error("--pages must be at least 1")
    return args


def main():
    args = parse_args()
    ensure_output_dirs()

    if args.relogin:
        print_header("Refreshing LinkedIn session")
        run_login_flow()

    if not has_session():
        print_header("No saved LinkedIn session found")
        print("Run 'python login.py' first, log in manually in the browser")
        print("window that opens, then re-run 'python runner.py'.")
        sys.exit(1)

    scraper = Scraper(max_pages=args.pages)

    try:
        print_header("Starting LinkedIn vacancy scraper")
        scraper.run()

    except KeyboardInterrupt:
        print("\nInterrupted by user, saving what was collected so far...")

    finally:
        stats = finalize_stats(scraper)

        # So newly-scraped jobs show a real match_score immediately instead
        # of "--" until someone remembers to click "Recalculate scores" in
        # the web app. Safe to run unconditionally: with no criteria
        # defined yet, every score just comes out 0.0 (see calculate_score).
        rescored = recalculate_all_scores(scraper.db)
        print(f"Recalculated match scores for {rescored} job(s)")

        exported = export_csv(scraper.db, OUTPUT_CSV, since=args.since)
        print(f"Exported {exported} jobs -> {OUTPUT_CSV}")

        if args.json:
            exported_json = export_json(scraper.db, OUTPUT_JSON, since=args.since)
            print(f"Exported {exported_json} jobs -> {OUTPUT_JSON}")

        print_stats(stats)

        scraper.db.close()


if __name__ == "__main__":
    main()