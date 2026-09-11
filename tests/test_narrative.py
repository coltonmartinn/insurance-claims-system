"""
Unit tests for the plain-language claim narrative shown to customers. The
key behavior worth pinning down: automated routing reasons (risk scores,
rule names) must never surface as a customer-facing detail, only a human
adjuster's own note should.
"""
from app import narrative


class _FakeEvent:
    def __init__(self, new_status, changed_by, reason=None):
        self.new_status = new_status
        self.changed_by = changed_by
        self.reason = reason


def test_system_generated_reason_is_never_shown_as_detail():
    event = _FakeEvent(
        "pending_review", "system",
        reason="Risk score 60, priority 'high'. Routed to adjuster review.",
    )
    text, detail = narrative.humanize_event(event)
    assert detail is None
    assert "Risk score" not in text


def test_adjuster_note_is_shown_as_detail():
    event = _FakeEvent("approved", "adjuster1", reason="Verified with body shop estimate.")
    text, detail = narrative.humanize_event(event)
    assert detail == "Verified with body shop estimate."
    assert "approved" in text.lower()


def test_adjuster_transition_without_a_note_has_no_detail():
    event = _FakeEvent("denied", "adjuster1", reason=None)
    text, detail = narrative.humanize_event(event)
    assert detail is None


def test_customers_own_submission_reason_is_not_shown_as_detail():
    # changed_by is the policyholder's own username here, not "system" --
    # but "submitted" isn't a decision, so the intake confirmation text
    # shouldn't be echoed back as if it were an explanation.
    event = _FakeEvent("submitted", "janedoe3", reason="Claim filed by policyholder.")
    text, detail = narrative.humanize_event(event)
    assert detail is None


def test_unknown_status_falls_back_gracefully():
    event = _FakeEvent("some_future_status", "system", reason="internal reason")
    text, detail = narrative.humanize_event(event)
    assert "some future status" in text
    assert detail is None


def test_mood_mapping_covers_every_real_status():
    from app.models import CLAIM_STATUSES
    for status in CLAIM_STATUSES:
        assert narrative.current_mood(status) in {"good", "progress", "attention", "neutral"}


def test_denied_status_has_an_attention_mood_not_good():
    assert narrative.current_mood("denied") == "attention"


def test_approved_and_paid_and_auto_cleared_are_good_mood():
    assert narrative.current_mood("approved") == "good"
    assert narrative.current_mood("paid") == "good"
    assert narrative.current_mood("auto_cleared") == "good"


def test_headline_and_next_steps_exist_for_every_real_status():
    from app.models import CLAIM_STATUSES
    for status in CLAIM_STATUSES:
        assert narrative.headline_for_status(status)
        assert narrative.next_steps_for_status(status)
