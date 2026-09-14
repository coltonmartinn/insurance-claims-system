"""
Translates the technical ClaimStatusEvent audit trail into plain language
for the customer-facing claim page. Adjusters still see the raw audit trail
(old_status, new_status, reason, changed_by, timestamp) in claim_detail.html
because that precise record is their job; this module exists so a claimant
checking on their claim gets a human answer instead of a status enum.
"""

STATUS_TRANSITION_COPY = {
    "submitted": "We received your claim.",
    "auto_cleared": "Good news, your claim was reviewed automatically and cleared. No adjuster needed to step in.",
    "pending_review": "An adjuster is taking a closer look at your claim.",
    "approved": "Your claim has been approved.",
    "denied": "Your claim was not approved.",
    "paid": "Payment has been issued.",
}

HEADLINE_BY_STATUS = {
    "submitted": "We've got your claim",
    "auto_cleared": "Your claim is cleared",
    "pending_review": "We're reviewing your claim",
    "approved": "Your claim was approved",
    "denied": "Your claim wasn't approved",
    "paid": "Your payment is on its way",
}

SUBHEAD_BY_STATUS = {
    "submitted": "We're looking it over now.",
    "auto_cleared": "It met our criteria for an automatic clearance, no waiting on a person required.",
    "pending_review": "An adjuster is reviewing the details. We'll update this page the moment there's a decision.",
    "approved": "We'll be in touch shortly about payment.",
    "denied": "See the note below for the reason, and reach out if you have questions.",
    "paid": "The payment for this claim has been issued.",
}

NEXT_STEPS_BY_STATUS = {
    "submitted": "Nothing needed from you right now. We'll update this page as soon as we know more.",
    "auto_cleared": "Nothing further needed from you. Keep an eye out for payment.",
    "pending_review": "Nothing needed from you right now. An adjuster is reviewing your claim and will reach out if anything else is required.",
    "approved": "Nothing further needed. Payment is being processed.",
    "denied": "If you have new information or questions about this decision, please contact your adjuster.",
    "paid": "This claim is complete. No further action needed.",
}

MOOD_BY_STATUS = {
    "submitted": "neutral",
    "auto_cleared": "good",
    "pending_review": "progress",
    "approved": "good",
    "denied": "attention",
    "paid": "good",
}

# Statuses that only an adjuster's manual decision produces. A note attached
# to one of these is worth quoting back to the customer; a note on
# "submitted" is just the intake confirmation text, not an explanation.
ADJUSTER_DECISION_STATUSES = {"approved", "denied", "paid"}


def humanize_event(event):
    """Returns (text, detail) for one ClaimStatusEvent, written for the
    policyholder. `detail` is only populated for an adjuster's own note on
    an actual decision (approved/denied/paid), since automated routing
    reasons (risk scores, rule names) are internal methodology the customer
    shouldn't see, and the policyholder's own intake confirmation text
    ("Claim filed.") adds nothing they don't already know."""
    text = STATUS_TRANSITION_COPY.get(event.new_status, f"Status updated to {event.new_status.replace('_', ' ')}.")
    is_adjuster_decision = event.changed_by != "system" and event.new_status in ADJUSTER_DECISION_STATUSES
    detail = event.reason if (is_adjuster_decision and event.reason) else None
    return text, detail


def current_mood(status):
    """Maps a claim's current status to a mood used for the status hero's
    color treatment: good, progress, attention, or neutral."""
    return MOOD_BY_STATUS.get(status, "neutral")


def headline_for_status(status):
    return HEADLINE_BY_STATUS.get(status, "Claim update")


def subhead_for_status(status):
    return SUBHEAD_BY_STATUS.get(status, "")


def next_steps_for_status(status):
    return NEXT_STEPS_BY_STATUS.get(status, "We'll update this page as your claim progresses.")


def progress_for_status(status):
    """Four-step progress (Filed / In Review / Decision / Payment) for the
    portal's progress row. Each step carries a fraction (0/55/100) used to
    draw its bar and a plain-language caption."""
    steps = [{"label": "Filed", "value": "Complete", "fraction": 100, "caption": "We received your claim."}]

    if status == "submitted":
        steps += [
            {"label": "In Review", "value": "In Progress", "fraction": 55, "caption": "We're looking it over."},
            {"label": "Decision", "value": "Not Yet", "fraction": 0, "caption": "Waiting on review."},
            {"label": "Payment", "value": "Not Yet", "fraction": 0, "caption": "Depends on the decision."},
        ]
    elif status == "pending_review":
        steps += [
            {"label": "In Review", "value": "Complete", "fraction": 100, "caption": "Reviewed by an adjuster."},
            {"label": "Decision", "value": "In Progress", "fraction": 55, "caption": "An adjuster is deciding."},
            {"label": "Payment", "value": "Not Yet", "fraction": 0, "caption": "Depends on the decision."},
        ]
    elif status == "auto_cleared":
        steps += [
            {"label": "In Review", "value": "Complete", "fraction": 100, "caption": "Cleared automatically."},
            {"label": "Decision", "value": "Cleared", "fraction": 100, "caption": "No adjuster needed."},
            {"label": "Payment", "value": "N/A", "fraction": 0, "caption": "Not applicable to this claim."},
        ]
    elif status == "approved":
        steps += [
            {"label": "In Review", "value": "Complete", "fraction": 100, "caption": "Reviewed by an adjuster."},
            {"label": "Decision", "value": "Approved", "fraction": 100, "caption": "Your claim was approved."},
            {"label": "Payment", "value": "In Progress", "fraction": 55, "caption": "Payment is being processed."},
        ]
    elif status == "paid":
        steps += [
            {"label": "In Review", "value": "Complete", "fraction": 100, "caption": "Reviewed by an adjuster."},
            {"label": "Decision", "value": "Approved", "fraction": 100, "caption": "Your claim was approved."},
            {"label": "Payment", "value": "Issued", "fraction": 100, "caption": "Payment has been sent."},
        ]
    elif status == "denied":
        steps += [
            {"label": "In Review", "value": "Complete", "fraction": 100, "caption": "Reviewed by an adjuster."},
            {"label": "Decision", "value": "Denied", "fraction": 100, "caption": "Your claim was not approved."},
            {"label": "Payment", "value": "N/A", "fraction": 0, "caption": "Not applicable to this claim."},
        ]
    else:
        steps += [
            {"label": "In Review", "value": "-", "fraction": 0, "caption": ""},
            {"label": "Decision", "value": "-", "fraction": 0, "caption": ""},
            {"label": "Payment", "value": "-", "fraction": 0, "caption": ""},
        ]

    for i, step in enumerate(steps):
        step["is_future"] = step["fraction"] == 0 and i > 0

    return steps
