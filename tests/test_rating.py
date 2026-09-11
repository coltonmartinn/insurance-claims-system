"""Unit tests for the premium rating function -- pure, no DB needed."""
from datetime import date

import pytest

from app.rating import calculate_premium

CURRENT_YEAR = date.today().year


def test_younger_driver_pays_more_than_baseline_driver():
    young_premium, _ = calculate_premium(
        driver_age=20, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=0,
        territory="30301", coverage_limit=50000,
    )
    baseline_premium, _ = calculate_premium(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=0,
        territory="30301", coverage_limit=50000,
    )
    assert young_premium > baseline_premium


def test_more_prior_claims_increases_premium():
    no_claims, _ = calculate_premium(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=0,
        territory="30301", coverage_limit=50000,
    )
    three_claims, _ = calculate_premium(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=3,
        territory="30301", coverage_limit=50000,
    )
    assert three_claims > no_claims


def test_higher_coverage_limit_increases_premium_proportionally():
    low_limit, _ = calculate_premium(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=0,
        territory="30301", coverage_limit=25000,
    )
    high_limit, _ = calculate_premium(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=0,
        territory="30301", coverage_limit=100000,
    )
    assert high_limit == pytest.approx(low_limit * 4)


def test_prior_claims_factor_caps_at_five_claims():
    five_claims, breakdown_5 = calculate_premium(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=5,
        territory="30301", coverage_limit=50000,
    )
    ten_claims, breakdown_10 = calculate_premium(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=10,
        territory="30301", coverage_limit=50000,
    )
    assert five_claims == ten_claims


def test_breakdown_includes_one_entry_per_factor_plus_base():
    _, breakdown = calculate_premium(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=1,
        territory="30301", coverage_limit=50000,
    )
    factor_names = [step["factor"] for step in breakdown]
    assert factor_names == ["Base rate", "Driver age", "Vehicle age", "Prior claims", "Territory", "Coverage limit"]


def test_premium_is_deterministic_for_same_inputs():
    premium_a, _ = calculate_premium(35, CURRENT_YEAR - 3, 1, "60601", 75000)
    premium_b, _ = calculate_premium(35, CURRENT_YEAR - 3, 1, "60601", 75000)
    assert premium_a == premium_b
