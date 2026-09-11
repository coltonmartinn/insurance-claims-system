"""
Rules-based risk scoring for incoming claims -- the centerpiece of this
project.

Every rule below is a small, independent, explainable function: given a
claim and its policy, it decides whether a specific fraud/risk pattern is
present and, if so, how many points it contributes. The rules are summed
into a risk score, and the score (plus an absolute dollar gate) decides the
routing recommendation.

This module never denies a claim. Its only job is to sort claims into:
  - auto_clear:  low value AND low risk -> system can close it without a
                 human ever looking at it.
  - review / high_priority_review: everything else goes to an adjuster.
                 "high_priority" only changes queue ordering, not who
                 makes the call.

Every rule that fires is recorded with its point value and a human-readable
reason, so `risk_explanation` on the Claim is a full audit of *why* a score
came out the way it did -- never just the number.
"""
import json
from dataclasses import dataclass, field

from app.features import TYPE_KEYWORDS, describes_mismatch

# --- Thresholds -------------------------------------------------------------

AUTO_CLEAR_MAX_SCORE = 15       # score must be below this...
AUTO_CLEAR_MAX_AMOUNT = 2000.0  # ...and the claim must be small in dollar terms
HIGH_PRIORITY_SCORE = 50        # score at/above this jumps to the top of the queue


# --- Individual rules --------------------------------------------------------
# Each rule has signature (claim, policy) -> (points, fired, reason)

def rule_amount_to_limit_ratio(claim, policy):
    ratio = claim.claimed_amount / policy.coverage_limit if policy.coverage_limit else 0
    if ratio >= 0.8:
        return 30, True, f"Claimed amount is {ratio:.0%} of the ${policy.coverage_limit:,.0f} coverage limit (>= 80%)"
    if ratio >= 0.5:
        return 15, True, f"Claimed amount is {ratio:.0%} of the ${policy.coverage_limit:,.0f} coverage limit (>= 50%)"
    return 0, False, ""


def rule_new_policy_incident_gap(claim, policy):
    gap_days = (claim.incident_date - policy.start_date).days
    if gap_days < 0:
        return 40, True, "Incident date is before the policy start date"
    if gap_days <= 14:
        return 25, True, f"Incident occurred only {gap_days} day(s) after policy start (classic early-claim pattern)"
    if gap_days <= 30:
        return 10, True, f"Incident occurred {gap_days} days after policy start"
    return 0, False, ""


def rule_prior_claims_history(claim, policy):
    count = policy.prior_claims_count
    if count >= 3:
        return 20, True, f"Policy has {count} prior claims (>= 3)"
    if count >= 1:
        return 10, True, f"Policy has {count} prior claim(s)"
    return 0, False, ""


def rule_round_number_amount(claim, policy):
    amount = claim.claimed_amount
    if amount > 0 and amount % 500 == 0:
        return 10, True, f"Claimed amount ${amount:,.0f} is an exact multiple of $500 (round-number pattern)"
    return 0, False, ""


def rule_type_description_mismatch(claim, policy):
    if not describes_mismatch(claim.incident_type, claim.description):
        return 0, False, ""

    description = (claim.description or "").lower()
    for other_type, keywords in TYPE_KEYWORDS.items():
        if other_type == claim.incident_type:
            continue
        matched = [kw for kw in keywords if kw in description]
        if matched:
            return 20, True, (
                f"Claim filed as '{claim.incident_type}' but description matches "
                f"'{other_type}' language ({matched[0]!r})"
            )
    return 0, False, ""


def rule_late_reporting(claim, policy):
    delay_days = (claim.claim_date.date() - claim.incident_date).days
    if delay_days > 60:
        return 15, True, f"Claim filed {delay_days} days after the incident (> 60 days)"
    if delay_days > 30:
        return 5, True, f"Claim filed {delay_days} days after the incident (> 30 days)"
    return 0, False, ""


RULES = [
    rule_amount_to_limit_ratio,
    rule_new_policy_incident_gap,
    rule_prior_claims_history,
    rule_round_number_amount,
    rule_type_description_mismatch,
    rule_late_reporting,
]


@dataclass
class TriageResult:
    score: int
    fired_rules: list = field(default_factory=list)  # [{rule, points, reason}, ...]
    recommendation: str = "review"  # 'auto_clear' | 'review'
    priority: str = "normal"        # 'low' | 'normal' | 'high'
    ml_score: float = None

    def explanation_json(self):
        return json.dumps(self.fired_rules)


def assess_claim(claim, policy):
    """Run every rule against (claim, policy) and turn the total into a
    routing recommendation. Pure function of the claim/policy data -- no
    side effects, no DB writes; the caller decides what to persist."""
    fired_rules = []
    score = 0
    for rule_fn in RULES:
        points, fired, reason = rule_fn(claim, policy)
        if fired:
            score += points
            fired_rules.append({"rule": rule_fn.__name__, "points": points, "reason": reason})

    if score < AUTO_CLEAR_MAX_SCORE and claim.claimed_amount <= AUTO_CLEAR_MAX_AMOUNT:
        recommendation, priority = "auto_clear", "low"
    elif score >= HIGH_PRIORITY_SCORE:
        recommendation, priority = "review", "high"
    else:
        recommendation, priority = "review", "normal"

    result = TriageResult(score=score, fired_rules=fired_rules, recommendation=recommendation, priority=priority)

    try:
        from app.ml import score_with_model
        result.ml_score = score_with_model(claim, policy)
    except Exception:
        result.ml_score = None

    return result
