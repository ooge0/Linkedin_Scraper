"""
database.py

SQLite helper.
"""

import sqlite3
from typing import List

from models import Job


class Database:

    def __init__(self, db_name: str = "output/jobs.db"):

        self.connection = sqlite3.connect(db_name)

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

            title TEXT,

            company TEXT,

            location TEXT,

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

            scraped_at TEXT

        )
        """)

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

    def insert_job(self, job: Job):
        """
        Save vacancy.
        """

        self.cursor.execute(
            """
            INSERT OR IGNORE INTO jobs
            (

                job_id,

                url,

                title,

                company,

                location,

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

                scraped_at

            )

            VALUES
            (

                ?,?,?,?,?,?,
                ?,?,?,?,?,?,
                ?,?,?,?

            )
            """,
            (

                job.job_id,

                job.url,

                job.title,

                job.company,

                job.location,

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

                str(job.scraped_at)

            )
        )

        self.connection.commit()

    # ------------------------------------------------------------------

    def get_all_jobs(self) -> List[sqlite3.Row]:

        self.cursor.execute("SELECT * FROM jobs")

        return self.cursor.fetchall()

    # ------------------------------------------------------------------

    def count_jobs(self) -> int:

        self.cursor.execute(
            "SELECT COUNT(*) FROM jobs"
        )

        return self.cursor.fetchone()[0]

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