"""Integration tests for the adjuster review queue, role gating, and the
approve/deny/mark-paid state machine."""
from datetime import date, timedelta

from app.models import Claim, ClaimStatusEvent
from tests.factories import make_policyholder, make_policy, make_user


def _login(client, user_id):
    return client.post("/login", data={"user_id": user_id})


def _file_flagged_claim(client, db_session, username="flagged_cust"):
    # High amount-to-limit ratio (+30) stacked with a policy that started
    # just days before the incident (+25) guarantees a high-priority score
    # (>= 50) regardless of threshold tuning elsewhere.
    ph = make_policyholder(email=f"{username}@example.com")
    policy = make_policy(ph, coverage_limit=10000, start_date=date.today() - timedelta(days=10))
    customer = make_user(username=username, policyholder=ph)
    db_session.commit()

    _login(client, customer.id)
    client.post("/claims/new", data={
        "policy_id": str(policy.id),
        "incident_type": "collision",
        "incident_date": (date.today() - timedelta(days=2)).isoformat(),
        "claimed_amount": "9000.00",
        "description": "Rear-ended at a stop light, major damage.",
    })
    client.get("/logout")
    return Claim.query.filter_by(policy_id=policy.id).one()


def test_customer_cannot_access_review_queue(client, db_session):
    ph = make_policyholder()
    make_policy(ph)
    customer = make_user(username="cust", policyholder=ph)
    db_session.commit()

    _login(client, customer.id)
    resp = client.get("/adjuster/queue")
    assert resp.status_code == 403


def test_anonymous_user_redirected_to_login(client):
    resp = client.get("/adjuster/queue")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_flagged_claim_appears_in_queue(client, db_session):
    claim = _file_flagged_claim(client, db_session)
    adjuster = make_user(username="adj1", role="adjuster")
    db_session.commit()

    _login(client, adjuster.id)
    resp = client.get("/adjuster/queue")
    assert resp.status_code == 200
    assert f"#{claim.id}".encode() in resp.data


def test_adjuster_can_approve_pending_claim(client, db_session):
    claim = _file_flagged_claim(client, db_session)
    adjuster = make_user(username="adj2", display_name="Adjuster Two", role="adjuster")
    db_session.commit()

    _login(client, adjuster.id)
    resp = client.post(f"/adjuster/claims/{claim.id}/transition", data={
        "action": "approve", "notes": "Verified with body shop estimate.",
    }, follow_redirects=True)

    assert resp.status_code == 200
    updated = db_session.get(Claim, claim.id)
    assert updated.status == "approved"

    events = ClaimStatusEvent.query.filter_by(claim_id=claim.id).order_by(ClaimStatusEvent.id).all()
    assert events[-1].new_status == "approved"
    assert events[-1].changed_by == "adj2"
    assert events[-1].old_status == "pending_review"


def test_adjuster_can_deny_pending_claim(client, db_session):
    claim = _file_flagged_claim(client, db_session, username="denyme")
    adjuster = make_user(username="adj3", role="adjuster")
    db_session.commit()

    _login(client, adjuster.id)
    client.post(f"/adjuster/claims/{claim.id}/transition", data={"action": "deny"})

    assert db_session.get(Claim, claim.id).status == "denied"


def test_mark_paid_requires_approved_status_first(client, db_session):
    claim = _file_flagged_claim(client, db_session, username="paytest")
    adjuster = make_user(username="adj4", role="adjuster")
    db_session.commit()

    _login(client, adjuster.id)
    # Claim is still pending_review -- marking paid should be rejected.
    resp = client.post(f"/adjuster/claims/{claim.id}/transition", data={"action": "mark_paid"})
    assert resp.status_code == 400
    assert db_session.get(Claim, claim.id).status == "pending_review"

    client.post(f"/adjuster/claims/{claim.id}/transition", data={"action": "approve"})
    resp = client.post(f"/adjuster/claims/{claim.id}/transition", data={"action": "mark_paid"})
    assert resp.status_code == 302
    assert db_session.get(Claim, claim.id).status == "paid"


def test_auto_cleared_page_lists_only_auto_cleared_claims(client, db_session):
    ph = make_policyholder(email="cleancust@example.com")
    policy = make_policy(ph, coverage_limit=50000, start_date=date.today() - timedelta(days=400))
    customer = make_user(username="cleancust", policyholder=ph)
    db_session.commit()

    _login(client, customer.id)
    client.post("/claims/new", data={
        "policy_id": str(policy.id),
        "incident_type": "collision",
        "incident_date": (date.today() - timedelta(days=2)).isoformat(),
        "claimed_amount": "800.00",
        "description": "Rear-ended at a stop light, minor bumper damage.",
    })
    client.get("/logout")
    clean_claim = Claim.query.filter_by(policy_id=policy.id).one()
    assert clean_claim.status == "auto_cleared"

    flagged_claim = _file_flagged_claim(client, db_session, username="dirtycust")

    adjuster = make_user(username="adj_audit", role="adjuster")
    db_session.commit()

    _login(client, adjuster.id)
    resp = client.get("/adjuster/auto-cleared")
    assert resp.status_code == 200
    assert f"#{clean_claim.id}".encode() in resp.data
    assert f"#{flagged_claim.id}".encode() not in resp.data


def test_customer_cannot_access_auto_cleared_page(client, db_session):
    ph = make_policyholder()
    make_policy(ph)
    customer = make_user(username="noaccess", policyholder=ph)
    db_session.commit()

    _login(client, customer.id)
    resp = client.get("/adjuster/auto-cleared")
    assert resp.status_code == 403


def test_lower_priority_does_not_change_status(client, db_session):
    claim = _file_flagged_claim(client, db_session, username="lowerprio")
    adjuster = make_user(username="adj5", role="adjuster")
    db_session.commit()
    assert claim.risk_priority == "high"

    _login(client, adjuster.id)
    client.post(f"/adjuster/claims/{claim.id}/transition", data={"action": "lower_priority"})

    updated = db_session.get(Claim, claim.id)
    assert updated.status == "pending_review"
    assert updated.risk_priority == "normal"
