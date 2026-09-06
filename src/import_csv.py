"""
import_csv.py

Import a previously-exported jobs CSV (runner.py's export_csv() format --
see CSV_FIELDS there) into a jobs database, through the exact same insert
path a live scrape run uses: Database.insert_job(), which is
INSERT OR IGNORE on the unique job_id. A job already in the target
database -- including any status/notes edited since in the web app -- is
left untouched; only job_ids the target database has never seen are
added.

This is the ingestion half of "scrape somewhere, push the CSV here" (e.g.
a scraper run on a remote machine, its output/jobs.csv copied over by
scp/rsync/whatever afterwards) -- getting the file onto this machine is
outside this script's concern, it only handles what happens once it's
here.

Usage
-----
    python import_csv.py path/to/jobs.csv                # into config.OUTPUT_DB
    python import_csv.py path/to/jobs.csv --db other.db   # into a specific DB
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import OUTPUT_DB
from database import Database
from models import Job
from utils import print_header


def _row_to_job(row: dict) -> Job:
    """
    Undoes export_csv()'s two lossy-for-round-tripping conversions --
    skills joined to a comma string, match_score written as "" for NULL
    -- everything else is already a plain string matching a Job field of
    the same name.
    """
    data = dict(row)
    data["skills"] = [s for s in (data.get("skills") or "").split(",") if s]
    match_score = data.get("match_score")
    data["match_score"] = float(match_score) if match_score else None
    return Job(**data)


def import_csv(db: Database, path: str) -> tuple[int, int]:
    """
    Returns (added, skipped). skipped counts rows whose job_id already
    existed in db and were left untouched, not an error condition.
    """
    added = 0
    skipped = 0

    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            job = _row_to_job(row)
            if db.insert_job(job):
                added += 1
            else:
                skipped += 1

    return added, skipped


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import a previously-exported jobs CSV into a jobs database."
    )
    parser.add_argument(
        "csv_path",
        type=str,
        help="Path to the CSV file to import (export_csv()'s format).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=OUTPUT_DB,
        help=f"Path to the jobs SQLite database (default: {OUTPUT_DB}).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print_header(f"Importing {args.csv_path} -> {args.db}")

    db = Database(args.db)
    try:
        added, skipped = import_csv(db, args.csv_path)
        print(f"Added {added} new job(s), skipped {skipped} already in the database.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
