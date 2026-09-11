import json
import os
import uuid
from datetime import datetime, date

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    g, current_app, send_from_directory, abort,
)
from werkzeug.utils import secure_filename

from app.models import Policy, Claim, INCIDENT_TYPES
from app.auth import login_required
from app.claim_service import file_claim

bp = Blueprint("claims", __name__, url_prefix="/claims")

ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf"}


def _save_photo(file_storage):
    if not file_storage or file_storage.filename == "":
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        flash(f"Unsupported file type: .{ext}", "error")
        return None
    filename = f"{uuid.uuid4().hex}_{secure_filename(file_storage.filename)}"
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
    return filename


@bp.route("/")
@login_required
def list_claims():
    if g.user.role == "adjuster":
        claims = Claim.query.order_by(Claim.claim_date.desc()).all()
    else:
        policy_ids = [p.id for p in g.user.policyholder.policies] if g.user.policyholder else []
        claims = (
            Claim.query.filter(Claim.policy_id.in_(policy_ids))
            .order_by(Claim.claim_date.desc())
            .all()
            if policy_ids else []
        )
    return render_template("claim_list.html", claims=claims)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_claim():
    if g.user.role == "adjuster" or not g.user.policyholder:
        policies = Policy.query.all()
    else:
        policies = g.user.policyholder.policies

    if request.method == "POST":
        form = request.form
        policy = Policy.query.get_or_404(int(form["policy_id"]))
        incident_date = datetime.strptime(form["incident_date"], "%Y-%m-%d").date()

        claim = file_claim(
            policy=policy,
            incident_type=form["incident_type"],
            incident_date=incident_date,
            claimed_amount=float(form["claimed_amount"]),
            description=form["description"].strip(),
            submitted_by=g.user.username,
            photo_filename=_save_photo(request.files.get("photo")),
        )

        flash("Claim submitted.", "success")
        return redirect(url_for("claims.claim_detail", claim_id=claim.id))

    return render_template(
        "claim_form.html", policies=policies, incident_types=INCIDENT_TYPES, today=date.today().isoformat(),
    )


@bp.route("/<int:claim_id>")
@login_required
def claim_detail(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    if g.user.role != "adjuster":
        owned_policy_ids = [p.id for p in g.user.policyholder.policies] if g.user.policyholder else []
        if claim.policy_id not in owned_policy_ids:
            abort(403)

    fired_rules = json.loads(claim.risk_explanation) if claim.risk_explanation else []
    return render_template("claim_detail.html", claim=claim, fired_rules=fired_rules)


@bp.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
