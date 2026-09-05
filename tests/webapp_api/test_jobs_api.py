"""
API-layer tests: request parsing, status codes, response shape. The
underlying DB behavior (filtering/sorting/pagination logic itself) is
already covered by tests/backend/test_database_extensions.py -- these
tests exist to catch wiring mistakes between the HTTP layer and the DB,
not to re-prove the DB layer.
"""


def test_list_jobs_returns_seeded_jobs(client):
    response = client.get("/api/jobs")
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 2
    assert {job["job_id"] for job in body["items"]} == {"1", "2"}


def test_list_jobs_filters_by_status(client):
    response = client.get("/api/jobs", params={"status": "interview"})
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["job_id"] == "2"


def test_list_jobs_filters_by_column_filter(client):
    response = client.get("/api/jobs", params={"company": "Acme"})
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["job_id"] == "1"


def test_list_jobs_filters_by_location_column_maps_to_location_entity(client):
    response = client.get("/api/jobs", params={"location": "Remote"})
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["job_id"] == "1"


def test_list_jobs_filters_by_salary_employment_type_seniority_applicants(client):
    # Job "1" (see conftest) is the only one with salary/employment_type/
    # seniority/applicants set -- job "2" has all four blank, so a match
    # here proves the new query params actually reach the DB layer rather
    # than being silently ignored.
    for param, value in [
        ("salary", "120K"),
        ("employment_type", "Full-time"),
        ("seniority", "Mid-Senior"),
        ("applicants", "50"),
    ]:
        response = client.get("/api/jobs", params={param: value})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1, f"filtering by {param}={value!r} found {body['total']} jobs"
        assert body["items"][0]["job_id"] == "1"


def test_list_jobs_rejects_unknown_sort_column(client):
    response = client.get("/api/jobs", params={"sort_by": "not_a_real_column"})
    assert response.status_code == 400


def test_get_job_by_id(client):
    response = client.get("/api/jobs/1")
    assert response.status_code == 200

    body = response.json()
    assert body["title"] == "Senior QA Engineer"
    assert body["skills"] == ["python", "selenium"]
    # location_entity is the cleaned location (see utils.parse_location_meta);
    # location is the raw, unparsed summary line -- both are exposed so the
    # UI can prefer the clean one without losing the raw value entirely.
    assert body["location_entity"] == "Remote"
    assert body["location"] == "Remote · 3 days ago · 50 applicants"
    # search_location is the config.SEARCH_LOCATION filter active on the
    # run that found this job -- distinct from location/location_entity,
    # which describe the job listing itself, not the search that found it.
    assert body["search_location"] == "Europe"


def test_get_job_404_for_unknown_id(client):
    response = client.get("/api/jobs/does-not-exist")
    assert response.status_code == 404


def test_update_job_status_and_notes_persists(client):
    response = client.patch("/api/jobs/1", json={"status": "applied", "notes": "Applied via referral"})
    assert response.status_code == 200
    assert response.json()["application_status"] == "applied"
    assert response.json()["notes"] == "Applied via referral"

    # Persisted, not just echoed back
    refetched = client.get("/api/jobs/1")
    assert refetched.json()["application_status"] == "applied"
    assert refetched.json()["notes"] == "Applied via referral"


def test_update_job_interview_date_persists(client):
    response = client.patch("/api/jobs/1", json={"interview_date": "2026-09-20"})
    assert response.status_code == 200
    assert response.json()["interview_date"] == "2026-09-20"

    refetched = client.get("/api/jobs/1")
    assert refetched.json()["interview_date"] == "2026-09-20"


def test_update_job_status_stamps_status_updated_at_in_the_response(client):
    response = client.patch("/api/jobs/1", json={"status": "applied"})
    assert response.status_code == 200
    assert response.json()["status_updated_at"] is not None


def test_update_job_requires_at_least_one_field(client):
    response = client.patch("/api/jobs/1", json={})
    assert response.status_code == 400


def test_update_job_404_for_unknown_id(client):
    response = client.patch("/api/jobs/does-not-exist", json={"status": "applied"})
    assert response.status_code == 404


def test_delete_job_removes_it(client):
    response = client.delete("/api/jobs/1")
    assert response.status_code == 204

    assert client.get("/api/jobs/1").status_code == 404
    assert client.get("/api/jobs").json()["total"] == 1


def test_score_breakdown_reports_matched_and_unmatched_criteria(client):
    # job "1": title "Senior QA Engineer", description mentions Python.
    client.post("/api/criteria", json={"term": "python", "weight": 1})
    client.post("/api/criteria", json={"term": "rust", "weight": 1})

    response = client.get("/api/jobs/1/score-breakdown")
    assert response.status_code == 200

    by_term = {d["term"]: d for d in response.json()}
    assert by_term["python"]["matched"] is True
    assert by_term["python"]["matched_in_title"] is False
    assert by_term["rust"]["matched"] is False


def test_score_breakdown_404_for_unknown_job(client):
    response = client.get("/api/jobs/does-not-exist/score-breakdown")
    assert response.status_code == 404


def test_stats_reflects_seeded_statuses(client):
    response = client.get("/api/stats")
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 2
    assert body["by_status"]["not_applied"] == 1
    assert body["by_status"]["interview"] == 1
