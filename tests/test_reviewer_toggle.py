"""
Tests for the reviewer-mode preview toggle in the sidebar. This is a UI
convenience only, not a security boundary: any logged-in customer can flip
it to preview the adjuster nav without logging out and back in as an
adjuster account, but the adjuster-only routes still enforce the real role
check regardless of the toggle.
"""
from tests.factories import make_policyholder, make_policy, make_user


def _login(client, user_id):
    return client.post("/login", data={"user_id": user_id})


def test_customer_sees_normal_nav_by_default(client, db_session):
    ph = make_policyholder()
    make_policy(ph)
    customer = make_user(username="normalcust", policyholder=ph)
    db_session.commit()

    _login(client, customer.id)
    resp = client.get("/claims/")
    assert b"My Claims" in resp.data
    assert b"Reviewer Mode" not in resp.data


def test_customer_can_toggle_reviewer_mode_preview_on(client, db_session):
    ph = make_policyholder()
    make_policy(ph)
    customer = make_user(username="toggler", policyholder=ph)
    db_session.commit()

    _login(client, customer.id)
    resp = client.post("/toggle-reviewer-mode")
    assert resp.status_code == 302

    resp = client.get("/claims/")
    assert b"Reviewer Mode" in resp.data
    assert b"Needs Review" in resp.data
    assert b"Auto-Cleared" in resp.data


def test_toggle_does_not_grant_access_to_adjuster_only_pages(client, db_session):
    ph = make_policyholder()
    make_policy(ph)
    customer = make_user(username="notreallyadjuster", policyholder=ph)
    db_session.commit()

    _login(client, customer.id)
    client.post("/toggle-reviewer-mode")

    # The nav shows reviewer-mode links now, but the underlying routes are
    # still gated by the real role check.
    assert client.get("/adjuster/queue").status_code == 403
    assert client.get("/adjuster/auto-cleared").status_code == 403
    assert client.get("/dashboard/").status_code == 403


def test_toggle_flips_back_off(client, db_session):
    ph = make_policyholder()
    make_policy(ph)
    customer = make_user(username="flipper", policyholder=ph)
    db_session.commit()

    _login(client, customer.id)
    client.post("/toggle-reviewer-mode")
    client.post("/toggle-reviewer-mode")

    resp = client.get("/claims/")
    assert b"My Claims" in resp.data
    assert b"Reviewer Mode" not in resp.data


def test_adjuster_always_sees_reviewer_nav_without_a_toggle_button(client, db_session):
    adjuster = make_user(username="realadjuster", role="adjuster")
    db_session.commit()

    _login(client, adjuster.id)
    resp = client.get("/adjuster/queue")
    assert b"Reviewer Mode" in resp.data
    assert b"reviewer-toggle-form" not in resp.data


def test_anonymous_user_cannot_toggle(client):
    resp = client.post("/toggle-reviewer-mode")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
