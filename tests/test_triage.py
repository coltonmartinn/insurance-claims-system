"""
Unit tests for the risk-scoring rules engine. Each rule is a pure function
of (claim, policy), so these run without a database or app context -- the
fastest and most direct way to pin down the triage logic's behavior.
"""
from datetime import date, datetime

from app import triage
from app.models import Claim, Policy


def make_policy(coverage_limit=50000.0, prior_claims_count=0, start_date=date(2024, 1, 1)):
    return Policy(
        coverage_limit=coverage_limit,
        prior_claims_count=prior_claims_count,
        start_date=start_date,
        vehicle_year=2020, vehicle_make="Honda", vehicle_model="Civic", premium=800.0,
    )


def make_claim(claimed_amount, incident_date, incident_type="collision",
               description="Rear-ended at a stop light, minor bumper damage.",
               claim_date=None):
    return Claim(
        claimed_amount=claimed_amount,
        incident_date=incident_date,
        incident_type=incident_type,
        description=description,
        claim_date=claim_date or datetime.combine(incident_date, datetime.min.time()),
    )


# --- rule_amount_to_limit_ratio ---------------------------------------------

def test_amount_ratio_above_80_percent_scores_30():
    policy = make_policy(coverage_limit=10000)
    claim = make_claim(9000, date(2024, 6, 1))
    points, fired, _ = triage.rule_amount_to_limit_ratio(claim, policy)
    assert fired is True
    assert points == 30


def test_amount_ratio_between_50_and_80_percent_scores_15():
    policy = make_policy(coverage_limit=10000)
    claim = make_claim(6000, date(2024, 6, 1))
    points, fired, _ = triage.rule_amount_to_limit_ratio(claim, policy)
    assert fired is True
    assert points == 15


def test_amount_ratio_below_50_percent_does_not_fire():
    policy = make_policy(coverage_limit=10000)
    claim = make_claim(1000, date(2024, 6, 1))
    points, fired, _ = triage.rule_amount_to_limit_ratio(claim, policy)
    assert fired is False
    assert points == 0


# --- rule_new_policy_incident_gap -------------------------------------------

def test_incident_before_policy_start_scores_40():
    policy = make_policy(start_date=date(2024, 6, 1))
    claim = make_claim(500, date(2024, 5, 1))
    points, fired, _ = triage.rule_new_policy_incident_gap(claim, policy)
    assert fired is True
    assert points == 40


def test_incident_within_14_days_of_start_scores_25():
    policy = make_policy(start_date=date(2024, 1, 1))
    claim = make_claim(500, date(2024, 1, 10))
    points, fired, _ = triage.rule_new_policy_incident_gap(claim, policy)
    assert fired is True
    assert points == 25


def test_incident_within_30_days_of_start_scores_10():
    policy = make_policy(start_date=date(2024, 1, 1))
    claim = make_claim(500, date(2024, 1, 25))
    points, fired, _ = triage.rule_new_policy_incident_gap(claim, policy)
    assert fired is True
    assert points == 10


def test_incident_well_after_start_does_not_fire():
    policy = make_policy(start_date=date(2023, 1, 1))
    claim = make_claim(500, date(2024, 1, 1))
    points, fired, _ = triage.rule_new_policy_incident_gap(claim, policy)
    assert fired is False


# --- rule_prior_claims_history -----------------------------------------------

def test_three_or_more_prior_claims_scores_20():
    policy = make_policy(prior_claims_count=3)
    claim = make_claim(500, date(2024, 6, 1))
    points, fired, _ = triage.rule_prior_claims_history(claim, policy)
    assert fired is True
    assert points == 20


def test_one_or_two_prior_claims_scores_10():
    policy = make_policy(prior_claims_count=1)
    claim = make_claim(500, date(2024, 6, 1))
    points, fired, _ = triage.rule_prior_claims_history(claim, policy)
    assert fired is True
    assert points == 10


def test_no_prior_claims_does_not_fire():
    policy = make_policy(prior_claims_count=0)
    claim = make_claim(500, date(2024, 6, 1))
    points, fired, _ = triage.rule_prior_claims_history(claim, policy)
    assert fired is False


# --- rule_round_number_amount ------------------------------------------------

def test_exact_multiple_of_500_fires():
    policy = make_policy()
    claim = make_claim(1500, date(2024, 6, 1))
    points, fired, _ = triage.rule_round_number_amount(claim, policy)
    assert fired is True
    assert points == 10


def test_non_round_amount_does_not_fire():
    policy = make_policy()
    claim = make_claim(1487.32, date(2024, 6, 1))
    points, fired, _ = triage.rule_round_number_amount(claim, policy)
    assert fired is False


# --- rule_type_description_mismatch ------------------------------------------

def test_description_matching_declared_type_does_not_fire():
    policy = make_policy()
    claim = make_claim(500, date(2024, 6, 1), incident_type="theft",
                        description="My car was stolen from the driveway overnight.")
    points, fired, _ = triage.rule_type_description_mismatch(claim, policy)
    assert fired is False


def test_description_matching_a_different_type_fires():
    policy = make_policy()
    claim = make_claim(500, date(2024, 6, 1), incident_type="collision",
                        description="My car was stolen from the parking garage overnight.")
    points, fired, reason = triage.rule_type_description_mismatch(claim, policy)
    assert fired is True
    assert points == 20
    assert "theft" in reason


def test_description_with_no_keywords_does_not_fire():
    policy = make_policy()
    claim = make_claim(500, date(2024, 6, 1), incident_type="other",
                        description="Something happened to my car.")
    points, fired, _ = triage.rule_type_description_mismatch(claim, policy)
    assert fired is False


# --- rule_late_reporting ------------------------------------------------------

def test_reporting_after_60_days_scores_15():
    incident_date = date(2024, 1, 1)
    claim_date = datetime(2024, 3, 15)  # 74 days later
    policy = make_policy()
    claim = make_claim(500, incident_date, claim_date=claim_date)
    points, fired, _ = triage.rule_late_reporting(claim, policy)
    assert fired is True
    assert points == 15


def test_reporting_after_30_days_scores_5():
    incident_date = date(2024, 1, 1)
    claim_date = datetime(2024, 2, 5)  # 35 days later
    policy = make_policy()
    claim = make_claim(500, incident_date, claim_date=claim_date)
    points, fired, _ = triage.rule_late_reporting(claim, policy)
    assert fired is True
    assert points == 5


def test_prompt_reporting_does_not_fire():
    incident_date = date(2024, 1, 1)
    claim_date = datetime(2024, 1, 3)
    policy = make_policy()
    claim = make_claim(500, incident_date, claim_date=claim_date)
    points, fired, _ = triage.rule_late_reporting(claim, policy)
    assert fired is False


# --- assess_claim: end-to-end scoring and routing ----------------------------

def test_clean_low_value_claim_auto_clears():
    policy = make_policy(coverage_limit=50000, prior_claims_count=0, start_date=date(2023, 1, 1))
    claim = make_claim(
        800, date(2024, 6, 1), incident_type="collision",
        description="Rear-ended at a stop light, minor bumper damage.",
        claim_date=datetime(2024, 6, 3),
    )
    result = triage.assess_claim(claim, policy)
    assert result.recommendation == "auto_clear"
    assert result.priority == "low"
    assert result.score < triage.AUTO_CLEAR_MAX_SCORE


def test_high_value_claim_never_auto_clears_even_with_zero_risk_rules():
    # Large claim, clean on every other axis -- should still be reviewed
    # because the auto-clear dollar gate is independent of the risk score.
    policy = make_policy(coverage_limit=50000, prior_claims_count=0, start_date=date(2020, 1, 1))
    claim = make_claim(
        3000, date(2024, 6, 1), incident_type="collision",
        description="Rear-ended at a stop light, minor bumper damage.",
        claim_date=datetime(2024, 6, 3),
    )
    result = triage.assess_claim(claim, policy)
    assert claim.claimed_amount > triage.AUTO_CLEAR_MAX_AMOUNT
    assert result.recommendation == "review"


def test_multiple_fired_rules_stack_into_high_priority():
    # Stack several risk patterns: high amount ratio, brand-new policy,
    # prior claims, round number.
    policy = make_policy(coverage_limit=10000, prior_claims_count=3, start_date=date(2024, 1, 1))
    claim = make_claim(
        8000, date(2024, 1, 5), incident_type="collision",
        description="Rear-ended at a stop light.",
        claim_date=datetime(2024, 1, 6),
    )
    result = triage.assess_claim(claim, policy)
    assert result.score >= triage.HIGH_PRIORITY_SCORE
    assert result.priority == "high"
    assert result.recommendation == "review"
    fired_rule_names = {r["rule"] for r in result.fired_rules}
    assert "rule_amount_to_limit_ratio" in fired_rule_names
    assert "rule_new_policy_incident_gap" in fired_rule_names
    assert "rule_prior_claims_history" in fired_rule_names


def test_explanation_json_round_trips_fired_rules():
    import json
    policy = make_policy(coverage_limit=10000, prior_claims_count=3, start_date=date(2024, 1, 1))
    claim = make_claim(8000, date(2024, 1, 5), claim_date=datetime(2024, 1, 6))
    result = triage.assess_claim(claim, policy)
    decoded = json.loads(result.explanation_json())
    assert decoded == result.fired_rules
    assert len(decoded) > 0
    assert all({"rule", "points", "reason"} <= set(entry) for entry in decoded)
