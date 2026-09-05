import pytest

from database import Database
from models import ApplicationStatus, Job


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "jobs.db"))
    yield database
    database.close()


def make_job(job_id, **overrides):
    defaults = dict(job_id=job_id, title=f"Job {job_id}", company="Acme")
    defaults.update(overrides)
    return Job(**defaults)


# ---------------------------------------------------------------- concurrency

def test_database_uses_wal_journal_mode(db):
    """
    WAL lets the web app (many short-lived read connections) and the
    scraper (one long-lived write connection) share output/jobs.db
    without reads blocking on a writer -- see the comment in
    Database.__init__ for the "database is locked" report this fixes.
    """
    db.cursor.execute("PRAGMA journal_mode")
    assert db.cursor.fetchone()[0] == "wal"


def test_database_can_be_used_from_a_different_thread_than_it_was_created_on(db):
    """
    Reproduces, deterministically, the exact failure FastAPI's threadpool
    caused intermittently in the E2E suite: Depends(get_db) resolves this
    generator dependency and then calls the route function as two
    *separate* run_in_threadpool dispatches, not guaranteed to land on the
    same worker thread. sqlite3's default check_same_thread=True would
    raise "SQLite objects created in a thread can only be used in that
    same thread" the moment a route handler on a different thread touched
    the connection -- see the check_same_thread=False comment in
    Database.__init__.
    """
    import threading

    result: dict = {}

    def use_from_other_thread():
        try:
            db.get_all_jobs()
            result["ok"] = True
        except Exception as e:  # pragma: no cover -- only on regression
            result["error"] = e

    thread = threading.Thread(target=use_from_other_thread)
    thread.start()
    thread.join()

    assert result.get("ok") is True, result.get("error")


# ---------------------------------------------------------------- get_job

def test_get_job_returns_none_for_unknown_id(db):
    assert db.get_job("missing") is None


def test_insert_job_persists_the_canonical_job_url(db):
    db.insert_job(make_job("1", job_url="https://www.linkedin.com/jobs/view/1/"))

    row = db.get_job("1")

    assert row["job_url"] == "https://www.linkedin.com/jobs/view/1/"


def test_get_job_returns_the_matching_row(db):
    db.insert_job(make_job("1"))

    row = db.get_job("1")

    assert row["job_id"] == "1"
    assert row["title"] == "Job 1"


# ------------------------------------------------------- update_job_status

def test_update_job_status_updates_only_status(db):
    db.insert_job(make_job("1"))

    updated = db.update_job_status("1", status=ApplicationStatus.APPLIED)

    assert updated is True
    row = db.get_job("1")
    assert row["application_status"] == "applied"
    assert row["notes"] == ""


def test_update_job_status_updates_only_notes(db):
    db.insert_job(make_job("1"))

    db.update_job_status("1", notes="looks promising")

    row = db.get_job("1")
    assert row["application_status"] == "not_applied"
    assert row["notes"] == "looks promising"


def test_update_job_status_stamps_status_updated_at(db):
    db.insert_job(make_job("1"))
    assert db.get_job("1")["status_updated_at"] is None

    db.update_job_status("1", status=ApplicationStatus.APPLIED)

    # Precise value isn't asserted (that's a clock, not behavior) -- just
    # that setting a status stamps *some* timestamp, since that's what the
    # web app's follow-up reminder ("applied N days ago") is computed from.
    assert db.get_job("1")["status_updated_at"] is not None


def test_update_job_status_does_not_stamp_status_updated_at_for_notes_only(db):
    db.insert_job(make_job("1"))

    db.update_job_status("1", notes="looks promising")

    assert db.get_job("1")["status_updated_at"] is None


def test_update_job_status_updates_only_interview_date(db):
    db.insert_job(make_job("1"))

    updated = db.update_job_status("1", interview_date="2026-09-20")

    assert updated is True
    row = db.get_job("1")
    assert row["interview_date"] == "2026-09-20"
    assert row["application_status"] == "not_applied"


def test_update_job_status_interview_date_empty_string_clears_it(db):
    db.insert_job(make_job("1"))
    db.update_job_status("1", interview_date="2026-09-20")

    db.update_job_status("1", interview_date="")

    assert db.get_job("1")["interview_date"] == ""


def test_update_job_status_no_args_is_a_no_op(db):
    db.insert_job(make_job("1"))

    assert db.update_job_status("1") is False


def test_update_job_status_returns_false_for_unknown_job(db):
    assert db.update_job_status("missing", status=ApplicationStatus.APPLIED) is False


# ------------------------------------------------------------ get_jobs_filtered

def test_get_jobs_filtered_by_status(db):
    db.insert_job(make_job("1"))
    db.insert_job(make_job("2"))
    db.update_job_status("2", status=ApplicationStatus.APPLIED)

    results = db.get_jobs_filtered(status="applied")

    assert [row["job_id"] for row in results] == ["2"]


def test_get_jobs_filtered_by_search_term(db):
    db.insert_job(make_job("1", title="Python Engineer"))
    db.insert_job(make_job("2", title="Rust Engineer"))

    results = db.get_jobs_filtered(search="Python")

    assert [row["job_id"] for row in results] == ["1"]


def test_get_jobs_filtered_rejects_unknown_sort_column(db):
    with pytest.raises(ValueError):
        db.get_jobs_filtered(sort_by="'; DROP TABLE jobs; --")


def test_get_jobs_filtered_by_column_filter(db):
    db.insert_job(make_job("1", company="Acme Corp"))
    db.insert_job(make_job("2", company="Globex"))

    results = db.get_jobs_filtered(column_filters={"company": "Acme"})

    assert [row["job_id"] for row in results] == ["1"]


def test_get_jobs_filtered_by_salary_employment_type_seniority_applicants(db):
    db.insert_job(make_job(
        "1", salary="$120K/yr", employment_type="Full-time", seniority="Mid-Senior",
        applicants="42 applicants",
    ))
    db.insert_job(make_job(
        "2", salary="$80K/yr", employment_type="Contract", seniority="Entry",
        applicants="5 applicants",
    ))

    assert [r["job_id"] for r in db.get_jobs_filtered(column_filters={"salary": "120K"})] == ["1"]
    assert [r["job_id"] for r in db.get_jobs_filtered(column_filters={"employment_type": "Contract"})] == ["2"]
    assert [r["job_id"] for r in db.get_jobs_filtered(column_filters={"seniority": "Entry"})] == ["2"]
    assert [r["job_id"] for r in db.get_jobs_filtered(column_filters={"applicants": "42"})] == ["1"]


def test_get_jobs_filtered_combines_multiple_column_filters(db):
    db.insert_job(make_job("1", company="Acme Corp", title="Senior QA"))
    db.insert_job(make_job("2", company="Acme Corp", title="Junior QA"))

    results = db.get_jobs_filtered(column_filters={"company": "Acme", "title": "Senior"})

    assert [row["job_id"] for row in results] == ["1"]


def test_get_jobs_filtered_rejects_a_column_not_in_the_filter_whitelist(db):
    with pytest.raises(ValueError):
        db.get_jobs_filtered(column_filters={"description": "anything"})


def test_get_jobs_filtered_excludes_with_a_leading_dash(db):
    db.insert_job(make_job("1", title="Senior QA Engineer"))
    db.insert_job(make_job("2", title="Junior QA Engineer"))

    results = db.get_jobs_filtered(column_filters={"title": "-Senior"})

    assert [row["job_id"] for row in results] == ["2"]


def test_get_jobs_filtered_exclude_filter_does_not_drop_null_column_values(db):
    db.insert_job(make_job("1", title="Senior QA Engineer"))
    db.insert_job(make_job("2", title="Junior QA Engineer", posted=""))

    # Excluding "months" from `posted` shouldn't hide job 2 just because
    # its posted column happens to be empty/NULL -- empty means "doesn't
    # contain it", the same as any other non-matching value would.
    results = db.get_jobs_filtered(column_filters={"posted": "-months"})

    assert {row["job_id"] for row in results} == {"1", "2"}


def test_count_jobs_filtered_matches_get_jobs_filtered(db):
    db.insert_job(make_job("1"))
    db.insert_job(make_job("2"))
    db.update_job_status("2", status=ApplicationStatus.APPLIED)

    assert db.count_jobs_filtered(status="applied") == 1
    assert db.count_jobs_filtered() == 2


def test_count_jobs_filtered_respects_column_filters(db):
    db.insert_job(make_job("1", company="Acme Corp"))
    db.insert_job(make_job("2", company="Globex"))

    assert db.count_jobs_filtered(column_filters={"company": "Acme"}) == 1


# --------------------------------------------------------------- get_status_counts

def test_get_status_counts_zero_fills_unused_statuses(db):
    db.insert_job(make_job("1"))

    counts = db.get_status_counts()

    assert counts["not_applied"] == 1
    assert counts["applied"] == 0
    assert set(counts) == {s.value for s in ApplicationStatus}


# ------------------------------------------------------------------ criteria CRUD

def test_add_and_get_criteria(db):
    criterion_id = db.add_criterion("python", weight=2.0)

    rows = db.get_criteria()

    assert len(rows) == 1
    assert rows[0]["id"] == criterion_id
    assert rows[0]["term"] == "python"
    assert rows[0]["weight"] == 2.0
    assert rows[0]["enabled"] == 1


def test_get_criteria_enabled_only_excludes_disabled(db):
    db.add_criterion("python", enabled=True)
    db.add_criterion("cobol", enabled=False)

    rows = db.get_criteria(enabled_only=True)

    assert [row["term"] for row in rows] == ["python"]


def test_update_criterion_partial_update(db):
    criterion_id = db.add_criterion("python", weight=1.0)

    db.update_criterion(criterion_id, weight=5.0)

    row = db.get_criteria()[0]
    assert row["term"] == "python"
    assert row["weight"] == 5.0


def test_delete_criterion(db):
    criterion_id = db.add_criterion("python")

    assert db.delete_criterion(criterion_id) is True
    assert db.get_criteria() == []


# ------------------------------------------------------------------ bulk_update_scores

def test_bulk_update_scores_writes_all_rows(db):
    db.insert_job(make_job("1"))
    db.insert_job(make_job("2"))

    updated = db.bulk_update_scores({"1": 80.0, "2": 20.0})

    assert updated == 2
    assert db.get_job("1")["match_score"] == 80.0
    assert db.get_job("2")["match_score"] == 20.0


def test_match_score_defaults_to_null_until_scored(db):
    db.insert_job(make_job("1"))

    assert db.get_job("1")["match_score"] is None


# ------------------------------------------------------------------ backfills
#
# These repair rows saved before a given piece of parsing existed --
# dedup means job_exists() skips them on every later scrape, so without
# a backfill they'd stay incomplete forever. Both run automatically
# whenever a Database is opened (see _migrate_schema()), which these
# tests exercise by reopening a second Database against the same file.

def test_backfill_populates_missing_job_url_from_job_id(db, tmp_path):
    db.insert_job(make_job("1"))  # job_url defaults to "" -- simulates pre-fix data

    reopened = Database(str(tmp_path / "jobs.db"))
    row = reopened.get_job("1")
    reopened.close()

    assert row["job_url"] == "https://www.linkedin.com/jobs/view/1/"


def test_backfill_parses_location_meta_from_raw_location(db, tmp_path):
    # location_entity/posted/applicants default to "" -- simulates a row
    # saved before parse_location_meta() was wired into the scraper.
    db.insert_job(make_job("1", location="Remote · 3 days ago · 50 applicants"))

    reopened = Database(str(tmp_path / "jobs.db"))
    row = reopened.get_job("1")
    reopened.close()

    assert row["location_entity"] == "Remote"
    assert row["posted"] == "3 days ago"
    assert row["applicants"] == "50 applicants"


def test_backfill_does_not_touch_rows_already_parsed(db, tmp_path):
    db.insert_job(make_job(
        "1",
        location="Remote · 3 days ago · 50 applicants",
        location_entity="Remote (edited by hand)",
        posted="3 days ago",
        applicants="50 applicants",
    ))

    reopened = Database(str(tmp_path / "jobs.db"))
    row = reopened.get_job("1")
    reopened.close()

    assert row["location_entity"] == "Remote (edited by hand)"
