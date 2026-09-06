"""
import_csv.py tests. Focused on what only this layer can see -- CSV
parsing and the string<->Python-type round trip (skills, match_score) --
not insert_job()'s own conflict/no-overwrite behavior, which is already
proven directly in tests/backend/test_database_extensions.py.
"""

from pathlib import Path

from database import Database
from import_csv import _row_to_job, import_csv
from models import ApplicationStatus, Job
from runner import export_csv


def make_job(job_id, **overrides):
    defaults = dict(job_id=job_id, title=f"Job {job_id}", company="Acme")
    defaults.update(overrides)
    return Job(**defaults)


def test_row_to_job_splits_skills_back_into_a_list():
    job = _row_to_job({"job_id": "1", "title": "QA", "skills": "python,selenium"})
    assert job.skills == ["python", "selenium"]


def test_row_to_job_treats_empty_skills_as_no_skills():
    job = _row_to_job({"job_id": "1", "title": "QA", "skills": ""})
    assert job.skills == []


def test_row_to_job_converts_empty_match_score_to_none():
    job = _row_to_job({"job_id": "1", "title": "QA", "match_score": ""})
    assert job.match_score is None


def test_row_to_job_converts_numeric_match_score_to_float():
    job = _row_to_job({"job_id": "1", "title": "QA", "match_score": "72.5"})
    assert job.match_score == 72.5


def test_import_csv_round_trips_a_real_export(tmp_path: Path):
    source_db = Database(str(tmp_path / "source.db"))
    source_db.insert_job(make_job(
        "1",
        title="Senior QA Engineer",
        skills=["python", "selenium"],
        application_status=ApplicationStatus.INTERVIEW,
        match_score=42.0,
    ))
    csv_path = tmp_path / "jobs.csv"
    export_csv(source_db, str(csv_path))
    source_db.close()

    target_db = Database(str(tmp_path / "target.db"))
    added, skipped = import_csv(target_db, str(csv_path))

    assert (added, skipped) == (1, 0)
    row = target_db.get_job("1")
    assert row["title"] == "Senior QA Engineer"
    assert row["skills"] == "python,selenium"
    assert row["application_status"] == "interview"
    assert row["match_score"] == 42.0
    target_db.close()


def test_import_csv_skips_jobs_that_already_exist_in_the_target(tmp_path: Path):
    source_db = Database(str(tmp_path / "source.db"))
    source_db.insert_job(make_job("1", title="Original from remote scrape"))
    csv_path = tmp_path / "jobs.csv"
    export_csv(source_db, str(csv_path))
    source_db.close()

    target_db = Database(str(tmp_path / "target.db"))
    target_db.insert_job(make_job("1", title="Already tracked locally"))
    target_db.update_job_status("1", notes="applied last week")

    added, skipped = import_csv(target_db, str(csv_path))

    assert (added, skipped) == (0, 1)
    row = target_db.get_job("1")
    assert row["title"] == "Already tracked locally"
    assert row["notes"] == "applied last week"
    target_db.close()


def test_import_csv_adds_only_the_genuinely_new_jobs_from_a_mixed_batch(tmp_path: Path):
    source_db = Database(str(tmp_path / "source.db"))
    source_db.insert_job(make_job("1", title="Already known"))
    source_db.insert_job(make_job("2", title="Brand new"))
    csv_path = tmp_path / "jobs.csv"
    export_csv(source_db, str(csv_path))
    source_db.close()

    target_db = Database(str(tmp_path / "target.db"))
    target_db.insert_job(make_job("1", title="Already known"))

    added, skipped = import_csv(target_db, str(csv_path))

    assert (added, skipped) == (1, 1)
    assert target_db.get_job("2")["title"] == "Brand new"
    target_db.close()
