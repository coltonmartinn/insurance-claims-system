"""Integration tests for the quote -> policy creation flow."""
from datetime import date

from app.models import Policy

VALID_QUOTE = {
    "name": "Test User", "email": "test@example.com", "phone": "555-0000",
    "date_of_birth": "1990-01-01", "address": "1 Test St", "territory": "44107",
    "vehicle_year": "2020", "vehicle_make": "Honda", "vehicle_model": "Civic",
    "coverage_limit": "50000", "prior_claims_count": "0",
    "start_date": date.today().isoformat(),
}


def test_quote_creates_policy_with_computed_premium(client, db_session):
    resp = client.post("/quote/", data=VALID_QUOTE, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Policy Created" in resp.data
    assert b"Premium Breakdown" in resp.data


def test_quote_without_required_field_fails_gracefully(client):
    resp = client.post("/quote/", data={
        "name": "Missing Fields",
    })
    # Missing required form fields should not crash the app with a raw 500;
    # the date-of-birth validator rejects the missing field with a 400 and
    # a friendly flashed message before any other field is even touched.
    assert resp.status_code == 400
    assert b"Date of birth" in resp.data


def test_quote_with_non_numeric_coverage_limit_shows_error(client, db_session):
    data = {**VALID_QUOTE, "coverage_limit": "not-a-number"}
    resp = client.post("/quote/", data=data)

    assert resp.status_code == 400
    assert b"Coverage limit must be a number" in resp.data
    assert Policy.query.count() == 0


def test_quote_with_negative_prior_claims_shows_error(client, db_session):
    data = {**VALID_QUOTE, "prior_claims_count": "-3"}
    resp = client.post("/quote/", data=data)

    assert resp.status_code == 400
    assert b"Prior claims count must be at least 0" in resp.data
    assert Policy.query.count() == 0


def test_quote_with_absurd_vehicle_year_shows_error(client, db_session):
    data = {**VALID_QUOTE, "vehicle_year": "1899"}
    resp = client.post("/quote/", data=data)

    assert resp.status_code == 400
    assert b"Vehicle year must be at least" in resp.data
    assert Policy.query.count() == 0


def test_quote_with_too_young_driver_shows_error(client, db_session):
    data = {**VALID_QUOTE, "date_of_birth": (date.today().replace(year=date.today().year - 10)).isoformat()}
    resp = client.post("/quote/", data=data)

    assert resp.status_code == 400
    assert b"at least 16 years old" in resp.data
    assert Policy.query.count() == 0


def test_quote_with_invalid_territory_shows_error(client, db_session):
    data = {**VALID_QUOTE, "territory": "abc"}
    resp = client.post("/quote/", data=data)

    assert resp.status_code == 400
    assert b"5-digit" in resp.data
    assert Policy.query.count() == 0


def test_quote_form_repopulates_submitted_values_after_error(client, db_session):
    data = {**VALID_QUOTE, "coverage_limit": "not-a-number", "name": "Repopulate Me"}
    resp = client.post("/quote/", data=data)

    assert resp.status_code == 400
    assert b"Repopulate Me" in resp.data


def test_field_error_renders_immediately_above_its_input_not_as_a_top_banner(client, db_session):
    data = {**VALID_QUOTE, "coverage_limit": "not-a-number"}
    resp = client.post("/quote/", data=data)
    html = resp.data.decode()

    assert resp.status_code == 400
    error_pos = html.index("Coverage limit must be a number")
    input_pos = html.index('name="coverage_limit"')
    # The error markup must sit between the label and the input it's about,
    # not up in the generic flash banner at the top of the page.
    assert error_pos < input_pos
    assert input_pos - error_pos < 400
    assert "flash-error" not in html


def test_field_error_only_appears_on_the_failing_field(client, db_session):
    data = {**VALID_QUOTE, "vehicle_year": "1899"}
    resp = client.post("/quote/", data=data)
    html = resp.data.decode()

    assert "Vehicle year must be at least" in html
    # Only one field failed validation -- no stray error markup elsewhere.
    assert html.count("field-error") == 1
