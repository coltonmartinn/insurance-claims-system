"""Unit tests for the numeric/date validators -- pure functions, no DB."""
from datetime import date, timedelta

import pytest

from app import validation
from app.validation import ValidationError


# --- validate_int / validate_float -------------------------------------------

def test_validate_int_accepts_valid_value():
    assert validation.validate_int("5", "Field") == 5


def test_validate_int_rejects_non_numeric():
    with pytest.raises(ValidationError, match="whole number"):
        validation.validate_int("abc", "Field")


def test_validate_int_rejects_none():
    with pytest.raises(ValidationError, match="whole number"):
        validation.validate_int(None, "Field")


def test_validate_int_enforces_min():
    with pytest.raises(ValidationError, match="at least 0"):
        validation.validate_int("-1", "Field", min_value=0)


def test_validate_int_enforces_max():
    with pytest.raises(ValidationError, match="at most 10"):
        validation.validate_int("11", "Field", max_value=10)


def test_validate_float_accepts_valid_value():
    assert validation.validate_float("12.5", "Field") == 12.5


def test_validate_float_rejects_non_numeric():
    with pytest.raises(ValidationError, match="must be a number"):
        validation.validate_float("not-a-number", "Field")


def test_validate_float_enforces_min():
    with pytest.raises(ValidationError, match="at least"):
        validation.validate_float("-5", "Field", min_value=0)


# --- validate_date -------------------------------------------------------------

def test_validate_date_accepts_valid_iso_date():
    assert validation.validate_date("2024-06-01", "Field") == date(2024, 6, 1)


def test_validate_date_rejects_bad_format():
    with pytest.raises(ValidationError, match="valid date"):
        validation.validate_date("06/01/2024", "Field")


def test_validate_date_rejects_none():
    with pytest.raises(ValidationError, match="valid date"):
        validation.validate_date(None, "Field")


def test_validate_date_enforces_not_after():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError, match="cannot be after"):
        validation.validate_date(tomorrow, "Field", not_after=date.today())


def test_validate_date_enforces_not_before():
    with pytest.raises(ValidationError, match="cannot be before"):
        validation.validate_date("1899-12-31", "Field", not_before=date(1900, 1, 1))


# --- validate_territory ---------------------------------------------------------

def test_validate_territory_accepts_five_digits():
    assert validation.validate_territory("44107") == "44107"


def test_validate_territory_rejects_wrong_length():
    with pytest.raises(ValidationError, match="5-digit"):
        validation.validate_territory("441")


def test_validate_territory_rejects_non_digits():
    with pytest.raises(ValidationError, match="5-digit"):
        validation.validate_territory("abcde")


# --- field-specific wrappers -----------------------------------------------------

def test_validate_vehicle_year_rejects_absurd_future_year():
    with pytest.raises(ValidationError, match="at most"):
        validation.validate_vehicle_year("2999")


def test_validate_vehicle_year_rejects_too_old():
    with pytest.raises(ValidationError, match="at least"):
        validation.validate_vehicle_year("1899")


def test_validate_coverage_limit_rejects_negative():
    with pytest.raises(ValidationError, match="at least"):
        validation.validate_coverage_limit("-1000")


def test_validate_coverage_limit_rejects_too_low():
    with pytest.raises(ValidationError):
        validation.validate_coverage_limit("100")


def test_validate_prior_claims_count_rejects_negative():
    with pytest.raises(ValidationError, match="at least"):
        validation.validate_prior_claims_count("-1")


def test_validate_prior_claims_count_rejects_unreasonably_high():
    with pytest.raises(ValidationError, match="at most"):
        validation.validate_prior_claims_count("1000")


def test_validate_claimed_amount_rejects_zero():
    with pytest.raises(ValidationError):
        validation.validate_claimed_amount("0")


def test_validate_claimed_amount_rejects_negative():
    with pytest.raises(ValidationError):
        validation.validate_claimed_amount("-500")


def test_validate_claimed_amount_accepts_valid_value():
    assert validation.validate_claimed_amount("1500.50") == 1500.50


def test_validate_incident_date_rejects_future_date():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError, match="cannot be after"):
        validation.validate_incident_date(tomorrow)


def test_validate_incident_date_accepts_today():
    assert validation.validate_incident_date(date.today().isoformat()) == date.today()


def test_validate_date_of_birth_rejects_under_minimum_age():
    too_young = date.today().replace(year=date.today().year - 10).isoformat()
    with pytest.raises(ValidationError, match="at least 16"):
        validation.validate_date_of_birth(too_young)


def test_validate_date_of_birth_rejects_future_date():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError, match="cannot be after"):
        validation.validate_date_of_birth(tomorrow)


def test_validate_date_of_birth_accepts_reasonable_adult():
    dob = date.today().replace(year=date.today().year - 30).isoformat()
    assert validation.validate_date_of_birth(dob) == date.today().replace(year=date.today().year - 30)
