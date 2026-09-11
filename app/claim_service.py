"""
Shared claim-intake logic used by both the HTML form (routes/claims.py) and
the JSON API (routes/api.py) -- one code path that files a claim, scores it,
and writes the audit trail, regardless of which interface it came through.
"""
from app.extensions import db
from app.models import Claim, ClaimStatusEvent
from app.triage import assess_claim


def file_claim(policy, incident_type, incident_date, claimed_amount, description,
                submitted_by, photo_filename=None):
    """Creates a Claim, writes the 'submitted' audit event, runs triage, and
    writes the resulting routing event. Returns the persisted Claim."""
    claim = Claim(
        policy_id=policy.id,
        incident_type=incident_type,
        incident_date=incident_date,
        claimed_amount=claimed_amount,
        description=description,
        photo_filename=photo_filename,
        status="submitted",
    )
    db.session.add(claim)
    db.session.flush()  # need claim.id for the audit event

    db.session.add(ClaimStatusEvent(
        claim_id=claim.id, old_status=None, new_status="submitted",
        changed_by=submitted_by, reason="Claim filed.",
    ))

    result = assess_claim(claim, policy)
    claim.risk_score = result.score
    claim.risk_priority = result.priority
    claim.risk_explanation = result.explanation_json()
    claim.ml_score = result.ml_score

    routed_status = "auto_cleared" if result.recommendation == "auto_clear" else "pending_review"
    reason = f"Risk score {result.score}, priority '{result.priority}'. "
    reason += "Auto-cleared: low risk and low value." if routed_status == "auto_cleared" else "Routed to adjuster review."
    db.session.add(ClaimStatusEvent(
        claim_id=claim.id, old_status="submitted", new_status=routed_status,
        changed_by="system", reason=reason,
    ))
    claim.status = routed_status

    db.session.commit()
    return claim
