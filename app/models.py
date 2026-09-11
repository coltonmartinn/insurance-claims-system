"""
Data model for the claims triage system.

Status lifecycle for a Claim (see triage.py for how the transition out of
`submitted` is decided):

    submitted -> auto_cleared                       (system decision, low risk)
    submitted -> pending_review -> approved -> paid  (human decision)
    submitted -> pending_review -> denied            (human decision)

Every transition, automatic or human, writes a ClaimStatusEvent. That table
is the audit trail: nothing changes a claim's status without a row explaining
who changed it, when, and why.
"""
from datetime import datetime, date

from app.extensions import db

INCIDENT_TYPES = ["collision", "theft", "fire", "vandalism", "weather", "liability", "other"]

CLAIM_STATUSES = [
    "submitted",
    "auto_cleared",
    "pending_review",
    "approved",
    "denied",
    "paid",
]


class User(db.Model):
    """A very light stand-in for real auth. Just enough to gate the adjuster
    queue behind a role. No passwords, no sessions beyond a simple cookie."""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")  # 'customer' or 'adjuster'
    policyholder_id = db.Column(db.Integer, db.ForeignKey("policyholder.id"), nullable=True)

    policyholder = db.relationship("Policyholder", back_populates="user")


class Policyholder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    date_of_birth = db.Column(db.Date, nullable=False)
    address = db.Column(db.String(200))
    territory = db.Column(db.String(10), nullable=False)  # zip / rating territory code

    user = db.relationship("User", back_populates="policyholder", uselist=False)
    policies = db.relationship("Policy", back_populates="policyholder", cascade="all, delete-orphan")

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class Policy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    policyholder_id = db.Column(db.Integer, db.ForeignKey("policyholder.id"), nullable=False)

    vehicle_year = db.Column(db.Integer, nullable=False)
    vehicle_make = db.Column(db.String(60), nullable=False)
    vehicle_model = db.Column(db.String(60), nullable=False)

    coverage_limit = db.Column(db.Float, nullable=False)
    prior_claims_count = db.Column(db.Integer, nullable=False, default=0)

    start_date = db.Column(db.Date, nullable=False, default=date.today)
    premium = db.Column(db.Float, nullable=False)

    policyholder = db.relationship("Policyholder", back_populates="policies")
    claims = db.relationship("Claim", back_populates="policy", cascade="all, delete-orphan")


class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey("policy.id"), nullable=False)

    incident_type = db.Column(db.String(30), nullable=False)
    incident_date = db.Column(db.Date, nullable=False)
    claim_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    claimed_amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    photo_filename = db.Column(db.String(200), nullable=True)

    status = db.Column(db.String(20), nullable=False, default="submitted")

    # Triage output. risk_explanation is a JSON-encoded list of the specific
    # rules that fired, so the score is always traceable to concrete inputs.
    risk_score = db.Column(db.Integer, nullable=True)
    risk_priority = db.Column(db.String(20), nullable=True)  # 'low' | 'normal' | 'high'
    risk_explanation = db.Column(db.Text, nullable=True)
    ml_score = db.Column(db.Float, nullable=True)  # optional secondary signal, 0-1

    policy = db.relationship("Policy", back_populates="claims")
    status_events = db.relationship(
        "ClaimStatusEvent", back_populates="claim",
        cascade="all, delete-orphan", order_by="ClaimStatusEvent.timestamp",
    )

    @property
    def resolved_at(self):
        for event in reversed(self.status_events):
            if event.new_status in ("approved", "denied", "auto_cleared"):
                return event.timestamp
        return None

    @property
    def time_to_resolution_hours(self):
        resolved = self.resolved_at
        if not resolved:
            return None
        return (resolved - self.claim_date).total_seconds() / 3600.0


class ClaimStatusEvent(db.Model):
    """Append-only audit trail. One row per status change, no exceptions."""

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claim.id"), nullable=False)

    old_status = db.Column(db.String(20), nullable=True)
    new_status = db.Column(db.String(20), nullable=False)
    changed_by = db.Column(db.String(80), nullable=False)  # 'system' or adjuster username
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    reason = db.Column(db.Text, nullable=True)

    claim = db.relationship("Claim", back_populates="status_events")
