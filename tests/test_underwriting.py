"""Unit tests for the underwriting risk estimate -- pure functions, no DB."""
from datetime import date

from app import underwriting

CURRENT_YEAR = date.today().year


def test_driver_under_21_scores_25():
    points, fired, _ = underwriting.rule_driver_age(driver_age=19)
    assert fired is True
    assert points == 25


def test_driver_21_to_24_scores_15():
    points, fired, _ = underwriting.rule_driver_age(driver_age=22)
    assert fired is True
    assert points == 15


def test_driver_over_70_scores_15():
    points, fired, _ = underwriting.rule_driver_age(driver_age=75)
    assert fired is True
    assert points == 15


def test_driver_in_baseline_band_does_not_fire():
    points, fired, _ = underwriting.rule_driver_age(driver_age=40)
    assert fired is False
    assert points == 0


def test_brand_new_vehicle_scores_10():
    points, fired, _ = underwriting.rule_new_vehicle_exposure(vehicle_year=CURRENT_YEAR)
    assert fired is True
    assert points == 10


def test_old_vehicle_triggers_reliability_rule_not_new_vehicle_rule():
    new_points, new_fired, _ = underwriting.rule_new_vehicle_exposure(vehicle_year=CURRENT_YEAR - 20)
    old_points, old_fired, _ = underwriting.rule_aging_vehicle_reliability(vehicle_year=CURRENT_YEAR - 20)
    assert new_fired is False
    assert old_fired is True
    assert old_points == 10


def test_three_or_more_prior_claims_scores_25():
    points, fired, _ = underwriting.rule_prior_claims(prior_claims_count=3)
    assert fired is True
    assert points == 25


def test_high_risk_territory_scores_15():
    # Territory "9..." carries a 1.20x multiplier in TERRITORY_RISK
    points, fired, _ = underwriting.rule_territory_loss_history(territory="90210")
    assert fired is True
    assert points == 15


def test_low_risk_territory_does_not_fire():
    # Territory "8..." carries a 0.90x multiplier
    points, fired, _ = underwriting.rule_territory_loss_history(territory="85001")
    assert fired is False


def test_coverage_limit_at_100k_scores_15():
    points, fired, _ = underwriting.rule_high_coverage_exposure(coverage_limit=100000)
    assert fired is True
    assert points == 15


def test_baseline_coverage_limit_does_not_fire():
    points, fired, _ = underwriting.rule_high_coverage_exposure(coverage_limit=50000)
    assert fired is False


def test_clean_baseline_policy_is_safe():
    result = underwriting.assess_underwriting_risk(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=0,
        territory="85001", coverage_limit=50000,
    )
    assert result.band == "safe"
    assert result.priority == "low"
    assert result.score <= underwriting.SAFE_MAX_SCORE


def test_stacked_risk_factors_reach_risky_band():
    result = underwriting.assess_underwriting_risk(
        driver_age=19, vehicle_year=CURRENT_YEAR, prior_claims_count=3,
        territory="90210", coverage_limit=100000,
    )
    assert result.score > underwriting.MODERATE_MAX_SCORE
    assert result.band == "risky"
    assert result.priority == "high"
    fired_names = {r["rule"] for r in result.fired_rules}
    assert "rule_driver_age" in fired_names
    assert "rule_prior_claims" in fired_names


def test_moderate_band_is_between_thresholds():
    # One or two moderate factors, nothing stacking to the risky band.
    result = underwriting.assess_underwriting_risk(
        driver_age=40, vehicle_year=CURRENT_YEAR - 5, prior_claims_count=1,
        territory="90210", coverage_limit=50000,
    )
    assert underwriting.SAFE_MAX_SCORE < result.score <= underwriting.MODERATE_MAX_SCORE
    assert result.band == "moderate"
    assert result.priority == "normal"
