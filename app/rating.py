"""
Premium rating for the quote flow.

Deliberately simple: a base rate multiplied by a handful of independent
factors, each tied to one risk variable. Nothing here is a black box -- every
dollar of the quoted premium can be traced back to one of the factors below,
which is the same property we want out of the claims risk score.
"""
from datetime import date

BASE_RATE = 600.0

# First digit of the ZIP code stands in for a rating territory. Real insurers
# use much finer-grained, actuarially-derived territories; this is a toy
# version that's still deterministic and explainable.
TERRITORY_RISK = {
    "0": 1.10, "1": 1.15, "2": 1.05, "3": 0.95, "4": 1.00,
    "5": 0.90, "6": 0.95, "7": 1.05, "8": 0.90, "9": 1.20,
}


def _age_factor(driver_age):
    if driver_age < 25:
        return 1.40, "Driver under 25: +40% (inexperience risk)"
    if driver_age <= 65:
        return 1.00, "Driver 25-65: baseline rate"
    return 1.15, "Driver over 65: +15% (age-related risk)"


def _vehicle_factor(vehicle_year):
    vehicle_age = max(date.today().year - vehicle_year, 0)
    if vehicle_age <= 2:
        return 1.20, f"Vehicle is {vehicle_age} yr old: +20% (high repair/replacement cost)"
    if vehicle_age <= 7:
        return 1.05, f"Vehicle is {vehicle_age} yrs old: +5%"
    return 0.90, f"Vehicle is {vehicle_age} yrs old: -10% (lower replacement value)"


def _claims_factor(prior_claims_count):
    capped = min(prior_claims_count, 5)
    factor = 1.0 + 0.15 * capped
    return factor, f"{prior_claims_count} prior claim(s): +{int(15 * capped)}% (capped at 5 claims)"


def _territory_factor(territory):
    digit = (territory or "")[:1]
    factor = TERRITORY_RISK.get(digit, 1.0)
    pct = round((factor - 1) * 100)
    sign = "+" if pct >= 0 else ""
    return factor, f"Territory {territory}: {sign}{pct}% (regional loss history)"


def _coverage_factor(coverage_limit):
    factor = coverage_limit / 50000.0
    return factor, f"Coverage limit ${coverage_limit:,.0f}: scales premium relative to $50,000 baseline"


def calculate_premium(driver_age, vehicle_year, prior_claims_count, territory, coverage_limit):
    """Returns (annual_premium, breakdown) where breakdown is a list of
    {factor, multiplier, explanation} dicts in the order they were applied."""
    steps = [
        ("Driver age", *_age_factor(driver_age)),
        ("Vehicle age", *_vehicle_factor(vehicle_year)),
        ("Prior claims", *_claims_factor(prior_claims_count)),
        ("Territory", *_territory_factor(territory)),
        ("Coverage limit", *_coverage_factor(coverage_limit)),
    ]

    premium = BASE_RATE
    breakdown = [{"factor": "Base rate", "multiplier": None, "explanation": f"${BASE_RATE:,.0f} starting point"}]
    for name, factor, explanation in steps:
        premium *= factor
        breakdown.append({"factor": name, "multiplier": round(factor, 3), "explanation": explanation})

    return round(premium, 2), breakdown
