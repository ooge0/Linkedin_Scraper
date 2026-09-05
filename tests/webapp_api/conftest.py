from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import Database
from models import ApplicationStatus, Job

from webapp.backend import deps
from webapp.backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """
    A TestClient wired to a fresh, seeded DB per test -- same tmp_path
    Database pattern the scraper's own tests use, just pointed at the
    FastAPI app instead of the Scraper class.
    """
    db_path = str(tmp_path / "jobs.db")
    monkeypatch.setattr(deps, "DB_PATH", db_path)

    db = Database(db_path)
    db.insert_job(Job(
        job_id="1",
        title="Senior QA Engineer",
        company="Acme",
        skills=["python", "selenium"],
        description="Looking for a QA engineer with Python experience.",
        location="Remote · 3 days ago · 50 applicants",
        location_entity="Remote",
        search_location="Europe",
        salary="$120K/yr",
        employment_type="Full-time",
        seniority="Mid-Senior level",
        applicants="50 applicants",
    ))
    db.insert_job(Job(
        job_id="2",
        title="Junior QA",
        company="Beta",
        application_status=ApplicationStatus.INTERVIEW,
    ))
    db.close()

    from fastapi.testclient import TestClient
    return TestClient(app)
