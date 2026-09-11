"""
A small JSON API for system-to-system integration -- the same triage logic
the web UI uses, exposed for a policy admin system, a mobile app, or a
partner integration to call directly. Auth is a single static API key
(X-API-Key header), which is enough to demonstrate the pattern without
building out OAuth/JWT for a portfolio project.
"""
import json
from functools import wraps

from flask import Blueprint, jsonify, request, current_app, abort

from app.extensions import db
from app.models import Claim, Policy
from app.claim_service import file_claim
from app.validation import ValidationError, validate_incident_date, validate_claimed_amount

bp = Blueprint("api", __name__, url_prefix="/api")


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = current_app.config.get("API_KEY")
        provided = request.headers.get("X-API-Key")
        if not expected or provided != expected:
            abort(401)
        return view(*args, **kwargs)
    return wrapped


def _claim_to_dict(claim):
    return {
        "id": claim.id,
        "policy_id": claim.policy_id,
        "incident_type": claim.incident_type,
        "incident_date": claim.incident_date.isoformat(),
        "claim_date": claim.claim_date.isoformat(),
        "claimed_amount": claim.claimed_amount,
        "description": claim.description,
        "status": claim.status,
        "risk_score": claim.risk_score,
        "risk_priority": claim.risk_priority,
        "ml_score": claim.ml_score,
        "fired_rules": json.loads(claim.risk_explanation) if claim.risk_explanation else [],
    }


def _policy_to_dict(policy):
    return {
        "id": policy.id,
        "policyholder_id": policy.policyholder_id,
        "vehicle_year": policy.vehicle_year,
        "vehicle_make": policy.vehicle_make,
        "vehicle_model": policy.vehicle_model,
        "coverage_limit": policy.coverage_limit,
        "prior_claims_count": policy.prior_claims_count,
        "start_date": policy.start_date.isoformat(),
        "premium": policy.premium,
    }


@bp.route("/claims/<int:claim_id>")
@require_api_key
def get_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    return jsonify(_claim_to_dict(claim))


@bp.route("/claims")
@require_api_key
def list_claims():
    query = Claim.query
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    min_score = request.args.get("min_score", type=int)
    if min_score is not None:
        query = query.filter(Claim.risk_score >= min_score)
    claims = query.order_by(Claim.claim_date.desc()).limit(200).all()
    return jsonify([_claim_to_dict(c) for c in claims])


@bp.route("/claims", methods=["POST"])
@require_api_key
def create_claim():
    payload = request.get_json(silent=True) or {}
    required = ["policy_id", "incident_type", "incident_date", "claimed_amount", "description"]
    missing = [field for field in required if field not in payload]
    if missing:
        return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400

    policy = db.session.get(Policy, payload["policy_id"])
    if not policy:
        return jsonify({"error": "policy not found"}), 404

    try:
        incident_date = validate_incident_date(payload.get("incident_date"))
        claimed_amount = validate_claimed_amount(payload.get("claimed_amount"))
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    claim = file_claim(
        policy=policy,
        incident_type=payload["incident_type"],
        incident_date=incident_date,
        claimed_amount=claimed_amount,
        description=payload["description"],
        submitted_by=payload.get("submitted_by", "api"),
    )
    return jsonify(_claim_to_dict(claim)), 201


@bp.route("/policies/<int:policy_id>")
@require_api_key
def get_policy(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    return jsonify(_policy_to_dict(policy))
