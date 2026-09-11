"""
Seeds the database with a realistic-looking portfolio: a couple dozen
policyholders/policies and a spread of claims that exercise every risk rule
and every status in the claim lifecycle, so the app isn't empty on first
run.

Run with: python seed.py
"""
import random
from datetime import date, datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import User, Policyholder, Policy, Claim, ClaimStatusEvent
from app.rating import calculate_premium
from app.triage import assess_claim

random.seed(7)

FIRST_NAMES = [
    "James", "Maria", "Robert", "Linda", "Michael", "Patricia", "David", "Jennifer",
    "William", "Elizabeth", "Carlos", "Aisha", "Wei", "Fatima", "Daniel", "Sofia",
    "Kevin", "Nicole", "Brian", "Grace", "Andre", "Priya", "Sam", "Rachel",
    "Tom", "Diane", "Hassan", "Olivia", "Marcus", "Nadia",
]
LAST_NAMES = [
    "Turner", "Nguyen", "Garcia", "Smith", "Johnson", "Brown", "Davis", "Miller",
    "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris",
    "Martin", "Clark", "Lewis", "Walker", "Young", "King", "Wright", "Scott",
    "Green", "Baker", "Adams", "Nelson", "Carter", "Mitchell",
]
MAKES_MODELS = [
    ("Honda", "Civic"), ("Toyota", "Camry"), ("Ford", "F-150"), ("Chevrolet", "Malibu"),
    ("Subaru", "Outback"), ("Nissan", "Altima"), ("Jeep", "Grand Cherokee"), ("Hyundai", "Elantra"),
    ("Kia", "Soul"), ("Mazda", "CX-5"), ("Tesla", "Model 3"), ("BMW", "3 Series"),
]
TERRITORIES = ["44107", "10001", "90210", "30301", "60601", "77002", "98101", "02108", "85001", "48201"]


def make_policyholder(idx):
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    dob_year = random.randint(1955, 2005)
    return Policyholder(
        name=f"{first} {last}",
        email=f"{first.lower()}.{last.lower()}{idx}@example.com",
        phone=f"555-01{idx:02d}",
        date_of_birth=date(dob_year, random.randint(1, 12), random.randint(1, 28)),
        address=f"{100 + idx} Maple Ave",
        territory=random.choice(TERRITORIES),
    )


def make_policy(policyholder, start_date, prior_claims_count, coverage_limit=None):
    make, model = random.choice(MAKES_MODELS)
    vehicle_year = random.randint(2005, 2025)
    coverage_limit = coverage_limit or random.choice([25000, 50000, 75000, 100000])
    driver_age = date.today().year - policyholder.date_of_birth.year
    premium, _ = calculate_premium(
        driver_age=driver_age,
        vehicle_year=vehicle_year,
        prior_claims_count=prior_claims_count,
        territory=policyholder.territory,
        coverage_limit=coverage_limit,
    )
    return Policy(
        policyholder=policyholder,
        vehicle_year=vehicle_year,
        vehicle_make=make,
        vehicle_model=model,
        coverage_limit=coverage_limit,
        prior_claims_count=prior_claims_count,
        start_date=start_date,
        premium=premium,
    )


def file_claim(policy, incident_type, incident_date, claimed_amount, description,
                report_delay_days=3, resolution=None, adjuster_username=None, resolve_delay_days=2):
    """Mirrors the real intake + triage flow, then optionally fast-forwards
    a pending_review claim to a resolved state to populate history."""
    claim_date = datetime.combine(incident_date, datetime.min.time()) + timedelta(days=report_delay_days, hours=random.randint(8, 20))
    claim = Claim(
        policy=policy,
        incident_type=incident_type,
        incident_date=incident_date,
        claim_date=claim_date,
        claimed_amount=claimed_amount,
        description=description,
        status="submitted",
    )
    db.session.add(claim)
    db.session.flush()

    db.session.add(ClaimStatusEvent(
        claim_id=claim.id, old_status=None, new_status="submitted",
        changed_by=policy.policyholder.email.split("@")[0], timestamp=claim_date,
        reason="Claim filed by policyholder.",
    ))

    result = assess_claim(claim, policy)
    claim.risk_score = result.score
    claim.risk_priority = result.priority
    claim.risk_explanation = result.explanation_json()
    claim.ml_score = result.ml_score

    routed_status = "auto_cleared" if result.recommendation == "auto_clear" else "pending_review"
    routed_at = claim_date + timedelta(minutes=1)
    db.session.add(ClaimStatusEvent(
        claim_id=claim.id, old_status="submitted", new_status=routed_status,
        changed_by="system", timestamp=routed_at,
        reason=f"Risk score {result.score}, priority '{result.priority}'."
               + (" Auto-cleared: low risk and low value." if routed_status == "auto_cleared" else " Routed to adjuster review."),
    ))
    claim.status = routed_status

    if routed_status == "pending_review" and resolution:
        resolved_at = routed_at + timedelta(days=resolve_delay_days, hours=random.randint(1, 6))
        db.session.add(ClaimStatusEvent(
            claim_id=claim.id, old_status="pending_review", new_status=resolution,
            changed_by=adjuster_username or "adjuster1", timestamp=resolved_at,
            reason="Reviewed and approved by adjuster." if resolution == "approved" else "Reviewed and denied by adjuster.",
        ))
        claim.status = resolution

        if resolution == "approved" and random.random() < 0.6:
            paid_at = resolved_at + timedelta(days=random.randint(1, 5))
            db.session.add(ClaimStatusEvent(
                claim_id=claim.id, old_status="approved", new_status="paid",
                changed_by=adjuster_username or "adjuster1", timestamp=paid_at,
                reason="Payment issued.",
            ))
            claim.status = "paid"

    return claim


def run():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        adjuster1 = User(username="adjuster1", display_name="Priya Shah", role="adjuster")
        adjuster2 = User(username="adjuster2", display_name="Marcus Webb", role="adjuster")
        db.session.add_all([adjuster1, adjuster2])

        policies = []
        for i in range(28):
            ph = make_policyholder(i)
            db.session.add(ph)
            db.session.flush()

            months_ago = random.choice([2, 4, 6, 9, 12, 18, 24, 30, 36])
            start_date = date.today() - timedelta(days=30 * months_ago)
            prior_claims = random.choices([0, 0, 0, 1, 1, 2, 3], k=1)[0]

            policy = make_policy(ph, start_date, prior_claims)
            db.session.add(policy)
            db.session.flush()
            policies.append(policy)

            username = f"{ph.name.split()[0].lower()}{ph.id}"
            db.session.add(User(username=username, display_name=ph.name, role="customer", policyholder_id=ph.id))

        db.session.flush()

        # --- Clean claims: small amount, well inside coverage, filed
        # promptly, description matches incident type -> should auto-clear.
        clean_descriptions = {
            "collision": "Rear-ended at a red light, minor bumper damage.",
            "weather": "Hail storm dented the hood and roof overnight.",
            "vandalism": "Someone keyed the driver-side door in a parking lot.",
        }
        for policy in random.sample([p for p in policies if p.prior_claims_count == 0], 10):
            incident_type = random.choice(list(clean_descriptions))
            gap = random.randint(120, 900)
            incident_date = min(date.today() - timedelta(days=random.randint(5, 60)),
                                 policy.start_date + timedelta(days=gap))
            if incident_date <= policy.start_date:
                incident_date = policy.start_date + timedelta(days=gap)
            amount = round(random.uniform(300, 1800), 2)
            file_claim(policy, incident_type, incident_date, amount, clean_descriptions[incident_type],
                       report_delay_days=random.randint(1, 5))

        # --- Flagged claims: a mix of individual risk patterns, routed to
        # review. Some get resolved (approved/denied), some sit in queue.
        flagged_specs = [
            # (incident_type, days_after_policy_start, amount_fraction_of_limit, description, round_amount, resolution)
            ("theft", 10, 0.6, "Car was stolen from my driveway overnight.", False, None),
            ("collision", 400, 0.9, "Collided with another vehicle at an intersection.", False, "approved"),
            ("fire", 200, 0.4, "Engine caught fire while idling in traffic.", True, None),
            ("collision", 500, 0.3, "Vehicle was stolen and later recovered stripped.", False, "denied"),
            ("liability", 600, 0.55, "I was at fault, hit another driver at the intersection.", False, None),
            ("weather", 20, 0.35, "Hail storm damage the week after I got coverage.", False, "approved"),
            ("theft", 700, 0.25, "Stereo and wheels stolen from the vehicle.", True, None),
            ("collision", 800, 0.85, "Crash on the highway, other driver rear-ended me.", False, "denied"),
            ("vandalism", 5, 0.2, "Someone keyed my car the day after I signed up.", False, None),
            ("weather", 300, 0.15, "Flood water damaged the interior.", True, "approved"),
            ("liability", 450, 0.7, "Hit a pedestrian while backing out of a lot.", False, None),
            ("collision", 900, 0.45, "Rear-ended another car, moderate front-end damage.", True, None),
        ]
        eligible_policies = [p for p in policies]
        random.shuffle(eligible_policies)
        for spec, policy in zip(flagged_specs, eligible_policies):
            incident_type, days_after_start, fraction, description, round_amount, resolution = spec
            incident_date = policy.start_date + timedelta(days=days_after_start)
            if incident_date > date.today():
                incident_date = date.today() - timedelta(days=random.randint(3, 30))
            amount = policy.coverage_limit * fraction
            if round_amount:
                amount = round(amount / 500) * 500
            amount = round(amount, 2)
            adjuster = random.choice(["adjuster1", "adjuster2"])
            file_claim(policy, incident_type, incident_date, amount, description,
                       report_delay_days=random.randint(1, 45), resolution=resolution,
                       adjuster_username=adjuster, resolve_delay_days=random.randint(1, 4))

        db.session.commit()

        n_claims = Claim.query.count()
        n_auto = Claim.query.filter_by(status="auto_cleared").count()
        n_pending = Claim.query.filter_by(status="pending_review").count()
        print(f"Seeded {Policyholder.query.count()} policyholders, {Policy.query.count()} policies, {n_claims} claims.")
        print(f"  auto_cleared={n_auto} pending_review={n_pending} "
              f"approved={Claim.query.filter_by(status='approved').count()} "
              f"denied={Claim.query.filter_by(status='denied').count()} "
              f"paid={Claim.query.filter_by(status='paid').count()}")
        print("Log in as 'adjuster1' or 'adjuster2' (role: adjuster) or any seeded customer username.")


if __name__ == "__main__":
    run()
