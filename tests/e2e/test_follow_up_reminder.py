"""
The job detail page's "consider following up" reminder can't be driven
through the normal status-change UI -- it depends on status_updated_at
being far enough in the past, which only happens with the passage of
real time. These tests seed that timestamp directly via the DB instead
of going through seeded_db's shared two-job fixture (which several other
tests' assertions depend on keeping its exact statuses/counts).
"""

from datetime import datetime, timedelta, timezone

from database import Database
from models import ApplicationStatus, Job
from pages.job_detail_page import JobDetailPage


def _seed_applied_job(db_path: str, job_id: str, days_ago: int):
    db = Database(db_path)
    db.clear()
    db.cursor.execute("DELETE FROM match_criteria")
    db.connection.commit()

    db.insert_job(Job(job_id=job_id, title="Applied Job", company="Acme"))
    stale_timestamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    db.cursor.execute(
        "UPDATE jobs SET application_status = ?, status_updated_at = ? WHERE job_id = ?",
        (ApplicationStatus.APPLIED.value, stale_timestamp, job_id),
    )
    db.connection.commit()
    db.close()


def test_follow_up_reminder_shown_after_14_days_with_no_status_change(page, frontend_url, e2e_db_path, backend_url):
    _seed_applied_job(e2e_db_path, "stale-1", days_ago=20)

    page.goto(f"{frontend_url}/jobs/stale-1")
    page.wait_for_selector("h2")

    JobDetailPage(page, frontend_url).expect_follow_up_reminder()


def test_no_follow_up_reminder_for_a_recently_applied_job(page, frontend_url, e2e_db_path, backend_url):
    _seed_applied_job(e2e_db_path, "fresh-1", days_ago=2)

    page.goto(f"{frontend_url}/jobs/fresh-1")
    page.wait_for_selector("h2")

    JobDetailPage(page, frontend_url).expect_no_follow_up_reminder()
