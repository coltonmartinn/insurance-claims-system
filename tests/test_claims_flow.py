"""
Integration tests driving the Flask test client through the real HTTP
routes -- these exercise intake, triage routing, and the audit trail
end-to-end, the way a browser actually would.
"""
from datetime import date, timedelta

from app.models import Claim, ClaimStatusEvent
from tests.factories import make_policyholder, make_policy, make_user


def _login(client, user_id):
    return client.post("/login", data={"user_id": user_id})


def test_small_clean_claim_auto_clears(client, db_session):
    ph = make_policyholder()
    policy = make_policy(ph, coverage_limit=50000, start_date=date.today() - timedelta(days=400))
    user = make_user(username="janed", policyholder=ph)
    db_session.commit()

    _login(client, user.id)
    resp = client.post("/claims/new", data={
        "policy_id": str(policy.id),
        "incident_type": "collision",
        "incident_date": (date.today() - timedelta(days=2)).isoformat(),
        "claimed_amount": "800.00",
        "description": "Rear-ended at a stop light, minor bumper damage.",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Auto Cleared" in resp.data

    claim = Claim.query.filter_by(policy_id=policy.id).one()
    assert claim.status == "auto_cleared"
    assert claim.risk_score is not None


def test_high_value_claim_routes_to_pending_review(client, db_session):
    ph = make_policyholder(email="big@example.com")
    policy = make_policy(ph, coverage_limit=10000, start_date=date.today() - timedelta(days=400))
    user = make_user(username="bigclaim", policyholder=ph)
    db_session.commit()

    _login(client, user.id)
    resp = client.post("/claims/new", data={
        "policy_id": str(policy.id),
        "incident_type": "collision",
        "incident_date": (date.today() - timedelta(days=2)).isoformat(),
        "claimed_amount": "9000.00",
        "description": "Rear-ended at a stop light, major damage.",
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"Pending Review" in resp.data

    claim = Claim.query.filter_by(policy_id=policy.id).one()
    assert claim.status == "pending_review"


def test_every_status_change_is_audited(client, db_session):
    ph = make_policyholder(email="audit@example.com")
    policy = make_policy(ph, start_date=date.today() - timedelta(days=400))
    user = make_user(username="audituser", policyholder=ph)
    db_session.commit()

    _login(client, user.id)
    client.post("/claims/new", data={
        "policy_id": str(policy.id),
        "incident_type": "collision",
        "incident_date": (date.today() - timedelta(days=2)).isoformat(),
        "claimed_amount": "500.00",
        "description": "Rear-ended at a stop light.",
    })

    claim = Claim.query.filter_by(policy_id=policy.id).one()
    events = ClaimStatusEvent.query.filter_by(claim_id=claim.id).order_by(ClaimStatusEvent.id).all()

    assert len(events) == 2
    assert events[0].old_status is None
    assert events[0].new_status == "submitted"
    assert events[0].changed_by == "audituser"
    assert events[1].new_status == claim.status
    assert events[1].changed_by == "system"


def test_customer_cannot_view_another_customers_claim(client, db_session):
    ph_a = make_policyholder(email="a@example.com")
    policy_a = make_policy(ph_a, start_date=date.today() - timedelta(days=400))
    user_a = make_user(username="usera", policyholder=ph_a)

    ph_b = make_policyholder(email="b@example.com")
    make_policy(ph_b, start_date=date.today() - timedelta(days=400))
    user_b = make_user(username="userb", policyholder=ph_b)
    db_session.commit()

    _login(client, user_a.id)
    client.post("/claims/new", data={
        "policy_id": str(policy_a.id),
        "incident_type": "collision",
        "incident_date": (date.today() - timedelta(days=2)).isoformat(),
        "claimed_amount": "500.00",
        "description": "Rear-ended at a stop light.",
    })
    claim = Claim.query.filter_by(policy_id=policy_a.id).one()

    client.get("/logout")
    _login(client, user_b.id)
    resp = client.get(f"/claims/{claim.id}")
    assert resp.status_code == 403
