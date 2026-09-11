"""
Shared feature extraction used by both the rules engine (triage.py) and the
optional ML signal (ml.py), so the two scores are computed from the same
underlying claim/policy facts and stay directly comparable.
"""

TYPE_KEYWORDS = {
    "collision": ["crash", "collided", "rear-end", "rear ended", "sideswipe", "intersection", "hit another car"],
    "theft": ["stolen", "theft", "broken into", "break-in", "missing", "took my car"],
    "fire": ["fire", "burned", "flames", "smoke damage"],
    "vandalism": ["vandal", "keyed", "spray paint", "broken window", "slashed", "graffiti"],
    "weather": ["hail", "flood", "storm", "tree fell", "ice storm", "high wind", "lightning"],
    "liability": ["hit a pedestrian", "at fault", "other driver", "third party"],
}


def describes_mismatch(incident_type, description):
    """True if the free-text description reads like a different incident
    type than the one the claim was filed under."""
    description = (description or "").lower()
    own_keywords = TYPE_KEYWORDS.get(incident_type, [])
    if any(kw in description for kw in own_keywords):
        return False
    for other_type, keywords in TYPE_KEYWORDS.items():
        if other_type == incident_type and any(kw in description for kw in keywords):
            return False
    for other_type, keywords in TYPE_KEYWORDS.items():
        if other_type != incident_type and any(kw in description for kw in keywords):
            return True
    return False


FEATURE_NAMES = [
    "amount_to_limit_ratio",
    "policy_incident_gap_days",
    "prior_claims_count",
    "is_round_number",
    "type_mismatch",
    "reporting_delay_days",
]


def extract_features(claim, policy):
    """Returns a plain dict of numeric features for one claim. Kept as a
    dict (not a bare list) so training data and live scoring can never get
    the column order out of sync."""
    amount = claim.claimed_amount
    gap_days = (claim.incident_date - policy.start_date).days
    delay_days = (claim.claim_date.date() if hasattr(claim.claim_date, "date") else claim.claim_date) - claim.incident_date
    delay_days = delay_days.days

    return {
        "amount_to_limit_ratio": amount / policy.coverage_limit if policy.coverage_limit else 0.0,
        "policy_incident_gap_days": max(gap_days, 0),
        "prior_claims_count": policy.prior_claims_count,
        "is_round_number": 1.0 if amount > 0 and amount % 500 == 0 else 0.0,
        "type_mismatch": 1.0 if describes_mismatch(claim.incident_type, claim.description) else 0.0,
        "reporting_delay_days": max(delay_days, 0),
    }


def feature_vector(claim, policy):
    feats = extract_features(claim, policy)
    return [feats[name] for name in FEATURE_NAMES]
