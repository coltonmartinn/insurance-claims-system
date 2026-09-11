from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort

from app.extensions import db
from app.models import Claim, ClaimStatusEvent
from app.auth import adjuster_required

bp = Blueprint("adjuster", __name__, url_prefix="/adjuster")

PRIORITY_ORDER = {"high": 2, "normal": 1, "low": 0}


@bp.route("/queue")
@adjuster_required
def queue():
    claims = (
        Claim.query.filter_by(status="pending_review")
        .order_by(Claim.risk_score.desc())
        .all()
    )
    return render_template("adjuster_queue.html", claims=claims)


@bp.route("/claims/<int:claim_id>/transition", methods=["POST"])
@adjuster_required
def transition(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    action = request.form.get("action")
    notes = request.form.get("notes", "").strip()

    def log(new_status, reason):
        event = ClaimStatusEvent(
            claim_id=claim.id,
            old_status=claim.status,
            new_status=new_status,
            changed_by=g.user.username,
            reason=reason,
        )
        claim.status = new_status
        db.session.add(event)

    if action == "approve":
        if claim.status != "pending_review":
            abort(400)
        log("approved", notes or "Approved by adjuster after review.")
    elif action == "deny":
        if claim.status != "pending_review":
            abort(400)
        log("denied", notes or "Denied by adjuster after review.")
    elif action == "mark_paid":
        if claim.status != "approved":
            abort(400)
        log("paid", notes or "Payment issued.")
    elif action == "lower_priority":
        if claim.status != "pending_review":
            abort(400)
        old_priority = claim.risk_priority
        claim.risk_priority = "normal" if old_priority == "high" else "low"
        # status doesn't change, but the priority override is still an
        # auditable adjuster action.
        event = ClaimStatusEvent(
            claim_id=claim.id,
            old_status=claim.status,
            new_status=claim.status,
            changed_by=g.user.username,
            reason=notes or f"Priority manually lowered from '{old_priority}' to '{claim.risk_priority}'.",
        )
        db.session.add(event)
    else:
        abort(400)

    db.session.commit()
    flash("Claim updated.", "success")
    return redirect(url_for("claims.claim_detail", claim_id=claim.id))
