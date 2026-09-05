"""
recalculate_scores.py

Recompute match_score for every job already in the database, using the
currently-enabled match_criteria rows -- without re-scraping. Safe to run
any time; independent of the browser/Playwright entirely.

Usage
-----
    python recalculate_scores.py               # uses config.OUTPUT_DB
    python recalculate_scores.py --db path.db  # override the DB path
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import OUTPUT_DB
from database import Database
from scoring import recalculate_all_scores
from utils import print_header


def parse_args():
    parser = argparse.ArgumentParser(
        description="Recalculate match_score for every job in the database."
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
    print_header("Recalculating job match scores")

    db = Database(args.db)
    try:
        updated = recalculate_all_scores(db)
        print(f"Recalculated scores for {updated} job(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
