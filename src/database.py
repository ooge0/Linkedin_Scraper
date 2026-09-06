"""
database.py

SQLite helper.
"""

import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from models import ApplicationStatus, Job
from utils import build_job_url, parse_location_meta

ALL_STATUSES = [status.value for status in ApplicationStatus]

# Columns a caller may sort the filtered job list by -- sort_by comes from
# an external (web app) query param and can't be parameterized in ORDER BY,
# so it must be checked against this whitelist before ever touching SQL text.
SORTABLE_COLUMNS = {"scraped_at", "match_score", "title", "company", "posted"}

# Columns the web app's per-column filter row may substring-match against
# -- same reasoning as SORTABLE_COLUMNS: a column *name* from an external
# query param can't be parameterized, so it's checked against this
# whitelist before ever touching SQL text.
FILTERABLE_TEXT_COLUMNS = {
    "title",
    "company",
    "location_entity",
    "posted",
    "job_id",
    "search_location",
    "notes",
    "salary",
    "employment_type",
    "seniority",
    "applicants",
}


class Database:

    def __init__(self, db_name: str = "output/jobs.db"):

        # timeout=10: how long a write waits on another connection's lock
        # before giving up (default is 5s). WAL mode lets reads proceed
        # without waiting on a writer at all -- the two together are the
        # standard fix for "database is locked" when the scraper (one
        # long-lived writer connection) and the web app (many short-lived
        # connections, mostly reads) touch the same file at once. Without
        # this, a web app request landing mid-write can 500 with
        # "database is locked" -- reproduced directly while diagnosing a
        # real report of this. WAL is stored in the DB file itself once
        # set, so this is a no-op after the first time, on any DB file.
        # check_same_thread=False: FastAPI's Depends(get_db) resolves this
        # generator dependency and then calls the route function as two
        # *separate* run_in_threadpool dispatches -- they aren't guaranteed
        # to land on the same worker thread, so sqlite3's default
        # same-thread check can reject a connection created in one request's
        # dependency-resolution thread when the route handler (a different
        # thread) tries to use it, raising "SQLite objects created in a
        # thread can only be used in that same thread" (hit this for real,
        # intermittently, in the E2E suite). Safe to disable here because
        # each Database is single-request-scoped (one connection, created
        # and closed within get_db() for that request alone) -- it's used
        # by one thread at a time, sequentially, never concurrently by two.
        self.connection = sqlite3.connect(db_name, timeout=10.0, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")

        self.connection.row_factory = sqlite3.Row

        self.cursor = self.connection.cursor()

        self.create_tables()

    # ------------------------------------------------------------------

    def create_tables(self):
        """
        Create tables if they do not exist.
        """

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs
        (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            job_id TEXT UNIQUE,

            url TEXT,

            job_url TEXT,

            search_keyword TEXT,

            search_location TEXT,

            title TEXT,

            company TEXT,

            company_url TEXT,

            location TEXT,

            location_entity TEXT,

            salary TEXT,

            posted TEXT,

            employment_type TEXT,

            seniority TEXT,

            workplace_type TEXT,

            company_size TEXT,

            industry TEXT,

            applicants TEXT,

            description TEXT,

            skills TEXT,

            scraped_at TEXT,

            application_status TEXT DEFAULT 'not_applied',

            notes TEXT DEFAULT '',

            match_score REAL,

            interview_date TEXT,

            status_updated_at TEXT

        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_criteria
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            term TEXT NOT NULL,

            weight REAL NOT NULL DEFAULT 1.0,

            enabled INTEGER NOT NULL DEFAULT 1
        )
        """)

        self.connection.commit()

        self._migrate_schema()

    # ------------------------------------------------------------------

    def _migrate_schema(self):
        """
        Add columns introduced after a DB file was first created, so
        pre-existing jobs.db files keep working without losing data.
        """

        self.cursor.execute("PRAGMA table_info(jobs)")
        existing_columns = {row[1] for row in self.cursor.fetchall()}

        if "company_url" not in existing_columns:
            self.cursor.execute("ALTER TABLE jobs ADD COLUMN company_url TEXT")
            self.connection.commit()

        if "search_keyword" not in existing_columns:
            self.cursor.execute("ALTER TABLE jobs ADD COLUMN search_keyword TEXT")
            self.connection.commit()

        if "search_location" not in existing_columns:
            self.cursor.execute("ALTER TABLE jobs ADD COLUMN search_location TEXT")
            self.connection.commit()

        if "location_entity" not in existing_columns:
            self.cursor.execute("ALTER TABLE jobs ADD COLUMN location_entity TEXT")
            self.connection.commit()

        if "application_status" not in existing_columns:
            self.cursor.execute(
                "ALTER TABLE jobs ADD COLUMN application_status TEXT DEFAULT 'not_applied'"
            )
            self.connection.commit()

        if "notes" not in existing_columns:
            self.cursor.execute("ALTER TABLE jobs ADD COLUMN notes TEXT DEFAULT ''")
            self.connection.commit()

        if "match_score" not in existing_columns:
            self.cursor.execute("ALTER TABLE jobs ADD COLUMN match_score REAL")
            self.connection.commit()

        if "job_url" not in existing_columns:
            self.cursor.execute("ALTER TABLE jobs ADD COLUMN job_url TEXT")
            self.connection.commit()

        if "interview_date" not in existing_columns:
            self.cursor.execute("ALTER TABLE jobs ADD COLUMN interview_date TEXT")
            self.connection.commit()

        if "status_updated_at" not in existing_columns:
            self.cursor.execute("ALTER TABLE jobs ADD COLUMN status_updated_at TEXT")
            self.connection.commit()

        self._backfill_missing_job_urls()
        self._backfill_missing_location_meta()

    # ------------------------------------------------------------------

    def _backfill_missing_location_meta(self):
        """
        location_entity/posted/applicants are parsed out of the raw
        `location` summary line by utils.parse_location_meta() (called in
        scraper.py's parse_job()). Rows saved before that parsing was
        wired in still have the raw `location` text but empty parsed
        fields -- and dedup means job_exists() skips them on every later
        run, so they'd stay that way forever without this repair. No
        LinkedIn access needed: the raw text to re-parse is already here.
        """

        self.cursor.execute(
            "SELECT job_id, location FROM jobs "
            "WHERE location != '' AND (location_entity IS NULL OR location_entity = '')"
        )
        rows = self.cursor.fetchall()
        if not rows:
            return

        updates = [
            (*parse_location_meta(row["location"]), row["job_id"])
            for row in rows
        ]
        self.cursor.executemany(
            "UPDATE jobs SET location_entity = ?, posted = ?, applicants = ? WHERE job_id = ?",
            updates,
        )
        self.connection.commit()

    # ------------------------------------------------------------------

    def _backfill_missing_job_urls(self):
        """
        job_url is a pure function of job_id (utils.build_job_url). Rows
        saved before the job_url column existed -- or before this backfill
        was added -- were left with a NULL/empty job_url, and since dedup
        means job_exists() skips them on every later run, they would stay
        that way forever without this one-time-per-row repair.
        """

        self.cursor.execute(
            "SELECT job_id FROM jobs WHERE job_id != '' AND (job_url IS NULL OR job_url = '')"
        )
        rows = self.cursor.fetchall()
        if not rows:
            return

        self.cursor.executemany(
            "UPDATE jobs SET job_url = ? WHERE job_id = ?",
            [(build_job_url(row["job_id"]), row["job_id"]) for row in rows],
        )
        self.connection.commit()

    # ------------------------------------------------------------------

    def job_exists(self, job_id: str) -> bool:
        """
        Check if job already exists.
        """

        self.cursor.execute(
            "SELECT 1 FROM jobs WHERE job_id=?",
            (job_id,)
        )

        return self.cursor.fetchone() is not None

    # ------------------------------------------------------------------

    def insert_job(self, job: Job) -> bool:
        """
        Save vacancy. Returns True if a new row was inserted, False if
        job_id already existed and the INSERT OR IGNORE was a no-op --
        lets a caller (e.g. import_csv.py, importing jobs scraped
        elsewhere) report how many were actually new without a separate
        job_exists() lookup per row.
        """

        self.cursor.execute(
            """
            INSERT OR IGNORE INTO jobs
            (

                job_id,

                url,

                job_url,

                search_keyword,

                search_location,

                title,

                company,

                company_url,

                location,

                location_entity,

                salary,

                posted,

                employment_type,

                seniority,

                workplace_type,

                company_size,

                industry,

                applicants,

                description,

                skills,

                scraped_at,

                application_status,

                notes,

                match_score

            )

            VALUES
            (

                ?,?,?,?,?,?,
                ?,?,?,?,?,?,
                ?,?,?,?,?,?,
                ?,?,?,?,?,?

            )
            """,
            (

                job.job_id,

                job.url,

                job.job_url,

                job.search_keyword,

                job.search_location,

                job.title,

                job.company,

                job.company_url,

                job.location,

                job.location_entity,

                job.salary,

                job.posted,

                job.employment_type,

                job.seniority,

                job.workplace_type,

                job.company_size,

                job.industry,

                job.applicants,

                job.description,

                ",".join(job.skills),

                str(job.scraped_at),

                job.application_status.value,

                job.notes,

                job.match_score

            )
        )

        self.connection.commit()

        return self.cursor.rowcount > 0

    # ------------------------------------------------------------------

    def get_all_jobs(self) -> List[sqlite3.Row]:

        self.cursor.execute("SELECT * FROM jobs")

        return self.cursor.fetchall()

    # ------------------------------------------------------------------

    def get_jobs_since(self, since) -> List[sqlite3.Row]:
        """
        Jobs scraped at or after `since` (a datetime). scraped_at is stored
        as str(datetime) -- e.g. "2026-09-04 11:40:38.085440" -- which sorts
        lexicographically the same as chronologically, so a plain string
        comparison works without parsing every row back into a datetime.
        """

        self.cursor.execute(
            "SELECT * FROM jobs WHERE scraped_at >= ?",
            (str(since),),
        )

        return self.cursor.fetchall()

    # ------------------------------------------------------------------

    def count_jobs(self) -> int:

        self.cursor.execute(
            "SELECT COUNT(*) FROM jobs"
        )

        return self.cursor.fetchone()[0]

    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> Optional[sqlite3.Row]:
        """
        Fetch a single job by id, or None if it doesn't exist.
        """

        self.cursor.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))

        return self.cursor.fetchone()

    # ------------------------------------------------------------------

    def update_job_status(
        self,
        job_id: str,
        status: Optional[ApplicationStatus] = None,
        notes: Optional[str] = None,
        interview_date: Optional[str] = None,
    ) -> bool:
        """
        Partial update: only the columns whose argument is not None are
        written. Returns True if a row was updated, False if job_id doesn't
        exist (or every argument was None -- a documented no-op).

        interview_date follows the same "None means leave it alone, empty
        string means clear it" convention as notes.

        Setting status also stamps status_updated_at with the current
        time, regardless of what the status is changing to/from -- it's
        "when was this job's status last touched", the basis for a
        follow-up reminder ("applied N days ago, no update since") on the
        web app's job detail page.
        """

        updates = []
        params = []

        if status is not None:
            updates.append("application_status = ?")
            params.append(status.value)
            updates.append("status_updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())

        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if interview_date is not None:
            updates.append("interview_date = ?")
            params.append(interview_date)

        if not updates:
            return False

        params.append(job_id)

        self.cursor.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?",
            params,
        )
        self.connection.commit()

        return self.cursor.rowcount > 0

    # ------------------------------------------------------------------

    def _filtered_where_clause(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        min_score: Optional[float] = None,
        column_filters: Optional[dict] = None,
    ) -> tuple[str, list]:
        """
        Shared WHERE-clause builder for get_jobs_filtered/count_jobs_filtered,
        so the filter logic isn't duplicated between the two.

        column_filters is a {db_column: substring} map for the per-column
        filter row in the web app's Jobs table -- keys are checked against
        FILTERABLE_TEXT_COLUMNS (a fixed, hardcoded set) before ever
        reaching the SQL string, since unlike every value here, a column
        *name* can't be parameterized with a placeholder.
        """

        clauses = []
        params: list = []

        if status is not None:
            clauses.append("application_status = ?")
            params.append(status)

        if search is not None:
            clauses.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
            like_term = f"%{search}%"
            params.extend([like_term, like_term, like_term])

        if min_score is not None:
            clauses.append("match_score >= ?")
            params.append(min_score)

        for column, value in (column_filters or {}).items():
            if column not in FILTERABLE_TEXT_COLUMNS:
                raise ValueError(f"Cannot filter on column {column!r}")
            if not value:
                continue
            # A leading "-" excludes rather than includes (Gmail-style),
            # e.g. "-senior" hides rows whose column contains "senior".
            # NULL is treated as "doesn't contain it" -- a bare
            # `column NOT LIKE ?` would otherwise silently drop NULL rows,
            # since SQL comparisons against NULL are NULL, not true.
            if value.startswith("-") and len(value) > 1:
                clauses.append(f"({column} IS NULL OR {column} NOT LIKE ?)")
                params.append(f"%{value[1:]}%")
            else:
                clauses.append(f"{column} LIKE ?")
                params.append(f"%{value}%")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        return where_sql, params

    # ------------------------------------------------------------------

    def count_jobs_filtered(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        min_score: Optional[float] = None,
        column_filters: Optional[dict] = None,
    ) -> int:

        where_sql, params = self._filtered_where_clause(status, search, min_score, column_filters)

        self.cursor.execute(f"SELECT COUNT(*) FROM jobs {where_sql}", params)

        return self.cursor.fetchone()[0]

    # ------------------------------------------------------------------

    def get_jobs_filtered(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        min_score: Optional[float] = None,
        column_filters: Optional[dict] = None,
        sort_by: str = "scraped_at",
        sort_dir: str = "DESC",
        limit: int = 50,
        offset: int = 0,
    ) -> List[sqlite3.Row]:
        """
        Filtered, sorted, paginated job list -- backs the web app's job
        list endpoint. sort_by must be one of SORTABLE_COLUMNS: it can't be
        parameterized like a value, and (unlike every other method in this
        class) it is reachable from an external, client-controlled query
        param, so it's validated here rather than trusted.
        """

        if sort_by not in SORTABLE_COLUMNS:
            raise ValueError(f"sort_by must be one of {sorted(SORTABLE_COLUMNS)}, got {sort_by!r}")

        sort_dir = "DESC" if sort_dir.upper() != "ASC" else "ASC"

        where_sql, params = self._filtered_where_clause(status, search, min_score, column_filters)
        params = params + [limit, offset]

        self.cursor.execute(
            f"""
            SELECT * FROM jobs {where_sql}
            ORDER BY {sort_by} {sort_dir}
            LIMIT ? OFFSET ?
            """,
            params,
        )

        return self.cursor.fetchall()

    # ------------------------------------------------------------------

    def get_status_counts(self) -> dict:
        """
        Number of jobs per application_status. Always returns all known
        statuses (zero-filled if unused) so callers never have to guard
        against a missing key.
        """

        counts = {status: 0 for status in ALL_STATUSES}

        self.cursor.execute(
            "SELECT application_status, COUNT(*) FROM jobs GROUP BY application_status"
        )

        for status, count in self.cursor.fetchall():
            counts[status] = count

        return counts

    # ------------------------------------------------------------------

    def bulk_update_scores(self, scores: dict) -> int:
        """
        Write many match_score values in a single transaction (recalculate_
        scores.py may touch thousands of rows -- every other write method
        here commits per-call, which would mean thousands of fsyncs).
        scores: job_id -> new match_score.
        """

        self.cursor.executemany(
            "UPDATE jobs SET match_score = ? WHERE job_id = ?",
            [(score, job_id) for job_id, score in scores.items()],
        )
        self.connection.commit()

        return len(scores)

    # ------------------------------------------------------------------
    # Match-scoring criteria
    # ------------------------------------------------------------------

    def add_criterion(self, term: str, weight: float = 1.0, enabled: bool = True) -> int:

        self.cursor.execute(
            "INSERT INTO match_criteria (term, weight, enabled) VALUES (?, ?, ?)",
            (term, weight, int(enabled)),
        )
        self.connection.commit()

        return self.cursor.lastrowid

    def get_criteria(self, enabled_only: bool = False) -> List[sqlite3.Row]:

        if enabled_only:
            self.cursor.execute("SELECT * FROM match_criteria WHERE enabled = 1")
        else:
            self.cursor.execute("SELECT * FROM match_criteria")

        return self.cursor.fetchall()

    def update_criterion(
        self,
        criterion_id: int,
        term: Optional[str] = None,
        weight: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> bool:

        updates = []
        params = []

        if term is not None:
            updates.append("term = ?")
            params.append(term)

        if weight is not None:
            updates.append("weight = ?")
            params.append(weight)

        if enabled is not None:
            updates.append("enabled = ?")
            params.append(int(enabled))

        if not updates:
            return False

        params.append(criterion_id)

        self.cursor.execute(
            f"UPDATE match_criteria SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        self.connection.commit()

        return self.cursor.rowcount > 0

    def delete_criterion(self, criterion_id: int) -> bool:

        self.cursor.execute("DELETE FROM match_criteria WHERE id = ?", (criterion_id,))
        self.connection.commit()

        return self.cursor.rowcount > 0

    # ------------------------------------------------------------------

    def delete_job(self, job_id: str):

        self.cursor.execute(

            "DELETE FROM jobs WHERE job_id=?",

            (job_id,)

        )

        self.connection.commit()

    # ------------------------------------------------------------------

    def clear(self):

        self.cursor.execute("DELETE FROM jobs")

        self.connection.commit()

    # ------------------------------------------------------------------

    def vacuum(self):

        self.cursor.execute("VACUUM")

    # ------------------------------------------------------------------

    def close(self):

        self.connection.close()