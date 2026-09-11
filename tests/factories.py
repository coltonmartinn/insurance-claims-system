"""Test-only helpers for building model instances. Requires an active app context."""
from datetime import date, timedelta

from app.extensions import db
from app.models import User, Policyholder, Policy


def make_policyholder(**overrides):
    defaults = dict(
        name="Jane Doe", email="jane@example.com", phone="555-0100",
        date_of_birth=date(1990, 1, 1), address="1 Main St", territory="44107",
    )
    defaults.update(overrides)
    ph = Policyholder(**defaults)
    db.session.add(ph)
    db.session.flush()
    return ph


def make_policy(policyholder, **overrides):
    defaults = dict(
        vehicle_year=2020, vehicle_make="Honda", vehicle_model="Civic",
        coverage_limit=50000.0, prior_claims_count=0,
        start_date=date.today() - timedelta(days=365), premium=800.0,
    )
    defaults.update(overrides)
    policy = Policy(policyholder_id=policyholder.id, **defaults)
    db.session.add(policy)
    db.session.flush()
    return policy


def make_user(username="user1", display_name="Test User", role="customer", policyholder=None):
    user = User(
        username=username, display_name=display_name, role=role,
        policyholder_id=policyholder.id if policyholder else None,
    )
    db.session.add(user)
    db.session.flush()
    return user
