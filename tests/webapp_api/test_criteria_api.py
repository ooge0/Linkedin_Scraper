def test_add_and_list_criteria(client):
    response = client.post("/api/criteria", json={"term": "python", "weight": 2.0})
    assert response.status_code == 201
    assert response.json()["term"] == "python"

    listed = client.get("/api/criteria").json()
    assert len(listed) == 1
    assert listed[0]["term"] == "python"


def test_update_criterion(client):
    criterion_id = client.post("/api/criteria", json={"term": "python"}).json()["id"]

    response = client.patch(f"/api/criteria/{criterion_id}", json={"weight": 5.0})
    assert response.status_code == 200
    assert response.json()["weight"] == 5.0


def test_update_criterion_requires_at_least_one_field(client):
    criterion_id = client.post("/api/criteria", json={"term": "python"}).json()["id"]

    response = client.patch(f"/api/criteria/{criterion_id}", json={})
    assert response.status_code == 400


def test_update_criterion_404_for_unknown_id(client):
    response = client.patch("/api/criteria/999", json={"weight": 5.0})
    assert response.status_code == 404


def test_delete_criterion(client):
    criterion_id = client.post("/api/criteria", json={"term": "python"}).json()["id"]

    assert client.delete(f"/api/criteria/{criterion_id}").status_code == 204
    assert client.get("/api/criteria").json() == []


def test_recalculate_scores_updates_matching_jobs(client):
    client.post("/api/criteria", json={"term": "python", "weight": 1.0})

    response = client.post("/api/scores/recalculate")
    assert response.status_code == 200
    assert response.json()["updated"] == 2

    # Job 1's description mentions Python -> full score; job 2 has none of it -> zero.
    job_1 = client.get("/api/jobs/1").json()
    job_2 = client.get("/api/jobs/2").json()
    assert job_1["match_score"] == 100.0
    assert job_2["match_score"] == 0.0
