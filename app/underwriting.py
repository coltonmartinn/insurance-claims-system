"""
Underwriting risk estimate shown at quote time -- a companion to, but
distinct from, the claims-time triage engine in triage.py.

triage.py asks "does this claim look suspicious." This asks "how much risk
is the company taking on by issuing this policy at all" -- driver
experience, vehicle exposure, prior loss history, territory, and the size
of the payout the coverage limit exposes the insurer to. Same explainable-
rules pattern as claims triage: independent point-contributing checks,
summed into a score, banded into safe / moderate / risky. Like triage, it's
advisory -- it never blocks a quote, it flags a policy for an underwriter's
attention.
"""
from dataclasses import dataclass, field
from datetime import date

from app.rating import TERRITORY_RISK

SAFE_MAX_SCORE = 24
MODERATE_MAX_SCORE = 49


def rule_driver_age(driver_age, **_):
    if driver_age < 21:
        return 25, True, f"Driver is {driver_age}, under 21 (highest inexperience risk band)"
    if driver_age < 25:
        return 15, True, f"Driver is {driver_age}, under 25 (elevated inexperience risk)"
    if driver_age > 70:
        return 15, True, f"Driver is {driver_age}, over 70 (age-related risk factors)"
    return 0, False, ""


def rule_new_vehicle_exposure(vehicle_year, **_):
    vehicle_age = max(date.today().year - vehicle_year, 0)
    if vehicle_age <= 2:
        return 10, True, f"Vehicle is {vehicle_age} yr old -- high replacement cost increases payout exposure"
    return 0, False, ""


def rule_aging_vehicle_reliability(vehicle_year, **_):
    vehicle_age = max(date.today().year - vehicle_year, 0)
    if vehicle_age > 15:
        return 10, True, f"Vehicle is {vehicle_age} yrs old -- elevated mechanical-failure/breakdown risk"
    return 0, False, ""


def rule_prior_claims(prior_claims_count, **_):
    if prior_claims_count >= 3:
        return 25, True, f"{prior_claims_count} prior claims on record (>= 3)"
    if prior_claims_count >= 1:
        return 10, True, f"{prior_claims_count} prior claim(s) on record"
    return 0, False, ""


def rule_territory_loss_history(territory, **_):
    digit = (territory or "")[:1]
    factor = TERRITORY_RISK.get(digit, 1.0)
    if factor >= 1.15:
        return 15, True, f"Territory {territory} carries an elevated loss-history multiplier ({factor}x baseline)"
    if factor >= 1.05:
        return 5, True, f"Territory {territory} carries a slightly elevated loss-history multiplier ({factor}x baseline)"
    return 0, False, ""


def rule_high_coverage_exposure(coverage_limit, **_):
    if coverage_limit >= 100000:
        return 15, True, f"${coverage_limit:,.0f} coverage limit means a larger potential payout on any single claim"
    if coverage_limit >= 75000:
        return 5, True, f"${coverage_limit:,.0f} coverage limit is above the typical baseline"
    return 0, False, ""


RULES = [
    rule_driver_age,
    rule_new_vehicle_exposure,
    rule_aging_vehicle_reliability,
    rule_prior_claims,
    rule_territory_loss_history,
    rule_high_coverage_exposure,
]

BAND_TO_PRIORITY = {"safe": "low", "moderate": "normal", "risky": "high"}


@dataclass
class UnderwritingResult:
    score: int
    band: str  # 'safe' | 'moderate' | 'risky'
    fired_rules: list = field(default_factory=list)

    @property
    def priority(self):
        """Maps the band onto the same low/normal/high vocabulary the risk
        meter/ring UI components use, so both risk displays in the app share
        one set of CSS classes."""
        return BAND_TO_PRIORITY[self.band]


def assess_underwriting_risk(driver_age, vehicle_year, prior_claims_count, territory, coverage_limit):
    inputs = dict(
        driver_age=driver_age, vehicle_year=vehicle_year,
        prior_claims_count=prior_claims_count, territory=territory,
        coverage_limit=coverage_limit,
    )
    fired_rules = []
    score = 0
    for rule_fn in RULES:
        points, fired, reason = rule_fn(**inputs)
        if fired:
            score += points
            fired_rules.append({"rule": rule_fn.__name__, "points": points, "reason": reason})

    if score <= SAFE_MAX_SCORE:
        band = "safe"
    elif score <= MODERATE_MAX_SCORE:
        band = "moderate"
    else:
        band = "risky"

    return UnderwritingResult(score=score, band=band, fired_rules=fired_rules)
