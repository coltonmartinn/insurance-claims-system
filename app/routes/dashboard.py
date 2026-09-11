import json
import os

from flask import Blueprint, render_template

from app.models import Claim, CLAIM_STATUSES
from app.auth import adjuster_required

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

MODEL_METRICS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model_metrics.json")

SCORE_BUCKETS = [
    ("0-14\n(auto-clear range)", 0, 14),
    ("15-29", 15, 29),
    ("30-49", 30, 49),
    ("50+\n(high priority)", 50, 10**9),
]

STATUS_COLOR_VAR = {
    "submitted": "--navy-light",
    "auto_cleared": "--green",
    "pending_review": "--amber",
    "approved": "--green",
    "denied": "--red",
    "paid": "--accent",
}


@bp.route("/")
@adjuster_required
def dashboard():
    claims = Claim.query.all()

    status_counts = {status: 0 for status in CLAIM_STATUSES}
    for claim in claims:
        status_counts[claim.status] = status_counts.get(claim.status, 0) + 1

    resolution_times = [c.time_to_resolution_hours for c in claims if c.time_to_resolution_hours is not None]
    avg_resolution_hours = sum(resolution_times) / len(resolution_times) if resolution_times else None

    scored = [c for c in claims if c.risk_score is not None]
    bucket_counts = []
    for label, low, high in SCORE_BUCKETS:
        count = sum(1 for c in scored if low <= c.risk_score <= high)
        bucket_counts.append((label, count))
    max_bucket = max((count for _, count in bucket_counts), default=0) or 1
    score_distribution = [
        {"label": label, "count": count, "height_pct": round(count / max_bucket * 100) if count else 0}
        for label, count in bucket_counts
    ]

    total = len(claims) or 1
    status_breakdown = [
        {
            "status": status,
            "count": count,
            "pct": round(count / total * 100, 1),
            "color_var": STATUS_COLOR_VAR.get(status, "--muted"),
        }
        for status, count in status_counts.items()
        if count > 0
    ]

    model_metrics = None
    if os.path.exists(MODEL_METRICS_PATH):
        with open(MODEL_METRICS_PATH) as f:
            model_metrics = json.load(f)

    return render_template(
        "dashboard.html",
        status_counts=status_counts,
        status_breakdown=status_breakdown,
        avg_resolution_hours=avg_resolution_hours,
        score_distribution=score_distribution,
        total_claims=len(claims),
        scored_count=len(scored),
        model_metrics=model_metrics,
    )
