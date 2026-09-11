"""Integration tests for the quote -> policy creation flow."""
from datetime import date


def test_quote_creates_policy_with_computed_premium(client, db_session):
    resp = client.post("/quote/", data={
        "name": "Test User", "email": "test@example.com", "phone": "555-0000",
        "date_of_birth": "1990-01-01", "address": "1 Test St", "territory": "44107",
        "vehicle_year": "2020", "vehicle_make": "Honda", "vehicle_model": "Civic",
        "coverage_limit": "50000", "prior_claims_count": "0",
        "start_date": date.today().isoformat(),
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Policy Created" in resp.data
    assert b"Premium Breakdown" in resp.data


def test_quote_without_required_field_fails_gracefully(client):
    resp = client.post("/quote/", data={
        "name": "Missing Fields",
    })
    # Missing required form fields should not crash the app with a raw 500;
    # Flask/Werkzeug raises a 400 for the missing key.
    assert resp.status_code == 400
