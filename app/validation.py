"""
Small, explicit validators for user-submitted numeric and date fields.

Consistent with the rest of the app (rules that name exactly why they
fired), each validator raises ValidationError with a plain-English message
naming the exact constraint that failed -- never a generic "invalid input"
and never an unhandled exception that turns into a raw 500 page. Callers
(web routes and the JSON API) catch ValidationError and turn the message
into a flashed error or a 400 JSON response.
"""
from datetime import date, datetime

MIN_VEHICLE_YEAR = 1980
MAX_VEHICLE_YEAR = date.today().year + 1

MIN_COVERAGE_LIMIT = 5_000
MAX_COVERAGE_LIMIT = 1_000_000

MIN_PRIOR_CLAIMS = 0
MAX_PRIOR_CLAIMS = 20

MIN_CLAIMED_AMOUNT = 0.01
MAX_CLAIMED_AMOUNT = 10_000_000

MIN_DRIVER_AGE = 16
MAX_DRIVER_AGE = 100

EARLIEST_REASONABLE_DATE = date(1900, 1, 1)


class ValidationError(ValueError):
    """Raised when a submitted field fails validation. The message is
    written to be shown to the user directly (flashed, or returned as a
    JSON error), not logged for a developer to decode."""


def validate_int(raw_value, field_name, min_value=None, max_value=None):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a whole number.")
    _check_bounds(value, field_name, min_value, max_value)
    return value


def validate_float(raw_value, field_name, min_value=None, max_value=None):
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a number.")
    _check_bounds(value, field_name, min_value, max_value)
    return value


def _check_bounds(value, field_name, min_value, max_value):
    if min_value is not None and value < min_value:
        raise ValidationError(f"{field_name} must be at least {min_value:g}.")
    if max_value is not None and value > max_value:
        raise ValidationError(f"{field_name} must be at most {max_value:g}.")


def validate_date(raw_value, field_name, not_before=None, not_after=None):
    try:
        value = datetime.strptime(raw_value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a valid date (YYYY-MM-DD).")
    if not_before is not None and value < not_before:
        raise ValidationError(f"{field_name} cannot be before {not_before.isoformat()}.")
    if not_after is not None and value > not_after:
        raise ValidationError(f"{field_name} cannot be after {not_after.isoformat()}.")
    return value


def validate_territory(raw_value):
    value = (raw_value or "").strip()
    if not value.isdigit() or len(value) != 5:
        raise ValidationError("Territory must be a 5-digit ZIP code.")
    return value


# --- Field-specific wrappers used by the routes -----------------------------

def validate_vehicle_year(raw_value):
    return validate_int(raw_value, "Vehicle year", min_value=MIN_VEHICLE_YEAR, max_value=MAX_VEHICLE_YEAR)


def validate_coverage_limit(raw_value):
    return validate_float(raw_value, "Coverage limit", min_value=MIN_COVERAGE_LIMIT, max_value=MAX_COVERAGE_LIMIT)


def validate_prior_claims_count(raw_value):
    return validate_int(raw_value, "Prior claims count", min_value=MIN_PRIOR_CLAIMS, max_value=MAX_PRIOR_CLAIMS)


def validate_claimed_amount(raw_value):
    return validate_float(raw_value, "Claimed amount", min_value=MIN_CLAIMED_AMOUNT, max_value=MAX_CLAIMED_AMOUNT)


def validate_incident_date(raw_value):
    return validate_date(raw_value, "Incident date", not_before=EARLIEST_REASONABLE_DATE, not_after=date.today())


def _age_from_dob(dob):
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def validate_date_of_birth(raw_value):
    dob = validate_date(raw_value, "Date of birth", not_before=EARLIEST_REASONABLE_DATE, not_after=date.today())
    age = _age_from_dob(dob)
    if age < MIN_DRIVER_AGE:
        raise ValidationError(f"Driver must be at least {MIN_DRIVER_AGE} years old to be quoted.")
    if age > MAX_DRIVER_AGE:
        raise ValidationError(f"That date of birth implies an age over {MAX_DRIVER_AGE} -- please double-check it.")
    return dob
