"""Integration tests for the JSON API (app/routes/api.py)."""
from datetime import date, timedelta

from tests.factories import make_policyholder, make_policy

API_KEY = "test-api-key"  # matches the app() fixture's test_config


def test_request_without_api_key_is_rejected(client, db_session):
    ph = make_policyholder()
    policy = make_policy(ph)
    db_session.commit()

    resp = client.get(f"/api/policies/{policy.id}")
    assert resp.status_code == 401


def test_request_with_wrong_api_key_is_rejected(client, db_session):
    ph = make_policyholder()
    policy = make_policy(ph)
    db_session.commit()

    resp = client.get(f"/api/policies/{policy.id}", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


def test_get_policy_returns_expected_fields(client, db_session):
    ph = make_policyholder()
    policy = make_policy(ph, coverage_limit=75000.0)
    db_session.commit()

    resp = client.get(f"/api/policies/{policy.id}", headers={"X-API-Key": API_KEY})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == policy.id
    assert data["coverage_limit"] == 75000.0


def test_create_claim_via_api_runs_triage_and_returns_score(client, db_session):
    ph = make_policyholder()
    policy = make_policy(ph, coverage_limit=50000, start_date=date.today() - timedelta(days=400))
    db_session.commit()

    resp = client.post("/api/claims", headers={"X-API-Key": API_KEY}, json={
        "policy_id": policy.id,
        "incident_type": "collision",
        "incident_date": (date.today() - timedelta(days=2)).isoformat(),
        "claimed_amount": 800.0,
        "description": "Rear-ended at a stop light, minor bumper damage.",
        "submitted_by": "integration-test",
    })

    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "auto_cleared"
    assert data["risk_score"] is not None
    assert isinstance(data["fired_rules"], list)


def test_create_claim_via_api_with_missing_fields_returns_400(client, db_session):
    resp = client.post("/api/claims", headers={"X-API-Key": API_KEY}, json={"policy_id": 1})
    assert resp.status_code == 400
    assert "missing fields" in resp.get_json()["error"]


def test_create_claim_via_api_with_unknown_policy_returns_404(client, db_session):
    resp = client.post("/api/claims", headers={"X-API-Key": API_KEY}, json={
        "policy_id": 999999,
        "incident_type": "collision",
        "incident_date": date.today().isoformat(),
        "claimed_amount": 500,
        "description": "test",
    })
    assert resp.status_code == 404


def test_list_claims_filters_by_status(client, db_session):
    ph = make_policyholder()
    policy = make_policy(ph, coverage_limit=50000, start_date=date.today() - timedelta(days=400))
    db_session.commit()

    client.post("/api/claims", headers={"X-API-Key": API_KEY}, json={
        "policy_id": policy.id,
        "incident_type": "collision",
        "incident_date": (date.today() - timedelta(days=2)).isoformat(),
        "claimed_amount": 800.0,
        "description": "Rear-ended at a stop light, minor bumper damage.",
    })

    resp = client.get("/api/claims?status=auto_cleared", headers={"X-API-Key": API_KEY})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["status"] == "auto_cleared"

    resp = client.get("/api/claims?status=denied", headers={"X-API-Key": API_KEY})
    assert resp.get_json() == []
