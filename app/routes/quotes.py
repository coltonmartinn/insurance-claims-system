from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.extensions import db
from app.models import Policyholder, Policy
from app.rating import calculate_premium
from app.underwriting import assess_underwriting_risk
from app.validation import (
    ValidationError, validate_date, validate_date_of_birth, validate_vehicle_year,
    validate_prior_claims_count, validate_coverage_limit, validate_territory,
    MIN_VEHICLE_YEAR, MAX_VEHICLE_YEAR, MIN_COVERAGE_LIMIT, MAX_PRIOR_CLAIMS,
)

bp = Blueprint("quotes", __name__, url_prefix="/quote")

FORM_BOUNDS = dict(
    min_vehicle_year=MIN_VEHICLE_YEAR, max_vehicle_year=MAX_VEHICLE_YEAR,
    min_coverage_limit=MIN_COVERAGE_LIMIT, max_prior_claims=MAX_PRIOR_CLAIMS,
)


@bp.route("/", methods=["GET", "POST"])
def new_quote():
    if request.method == "POST":
        form = request.form
        try:
            dob = validate_date_of_birth(form.get("date_of_birth"))
            start_date = (
                validate_date(form.get("start_date"), "Policy start date", field="start_date")
                if form.get("start_date") else date.today()
            )
            vehicle_year = validate_vehicle_year(form.get("vehicle_year"))
            prior_claims_count = validate_prior_claims_count(form.get("prior_claims_count"))
            territory = validate_territory(form.get("territory"))
            coverage_limit = validate_coverage_limit(form.get("coverage_limit"))
        except ValidationError as e:
            return render_template(
                "quote_form.html", today=date.today().isoformat(), form=form,
                field_errors={e.field: str(e)}, **FORM_BOUNDS,
            ), 400

        policyholder = Policyholder(
            name=form["name"].strip(),
            email=form["email"].strip(),
            phone=form.get("phone", "").strip(),
            date_of_birth=dob,
            address=form.get("address", "").strip(),
            territory=territory,
        )
        db.session.add(policyholder)
        db.session.flush()  # get policyholder.id before creating the policy

        premium, _ = calculate_premium(
            driver_age=policyholder.age,
            vehicle_year=vehicle_year,
            prior_claims_count=prior_claims_count,
            territory=territory,
            coverage_limit=coverage_limit,
        )

        policy = Policy(
            policyholder_id=policyholder.id,
            vehicle_year=vehicle_year,
            vehicle_make=form["vehicle_make"].strip(),
            vehicle_model=form["vehicle_model"].strip(),
            coverage_limit=coverage_limit,
            prior_claims_count=prior_claims_count,
            start_date=start_date,
            premium=premium,
        )
        db.session.add(policy)
        db.session.commit()

        flash("Quote generated and policy created.", "success")
        return redirect(url_for("quotes.quote_result", policy_id=policy.id))

    return render_template("quote_form.html", today=date.today().isoformat(), **FORM_BOUNDS)


@bp.route("/<int:policy_id>")
def quote_result(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    driver_age = policy.policyholder.age
    territory = policy.policyholder.territory

    _, breakdown = calculate_premium(
        driver_age=driver_age,
        vehicle_year=policy.vehicle_year,
        prior_claims_count=policy.prior_claims_count,
        territory=territory,
        coverage_limit=policy.coverage_limit,
    )
    underwriting = assess_underwriting_risk(
        driver_age=driver_age,
        vehicle_year=policy.vehicle_year,
        prior_claims_count=policy.prior_claims_count,
        territory=territory,
        coverage_limit=policy.coverage_limit,
    )
    return render_template("quote_result.html", policy=policy, breakdown=breakdown, underwriting=underwriting)
