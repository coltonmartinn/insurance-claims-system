from datetime import datetime, date

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.extensions import db
from app.models import Policyholder, Policy
from app.rating import calculate_premium

bp = Blueprint("quotes", __name__, url_prefix="/quote")


def _parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


@bp.route("/", methods=["GET", "POST"])
def new_quote():
    if request.method == "POST":
        form = request.form
        dob = _parse_date(form["date_of_birth"])
        start_date = _parse_date(form["start_date"]) if form.get("start_date") else date.today()
        driver_age = date.today().year - dob.year - ((date.today().month, date.today().day) < (dob.month, dob.day))
        vehicle_year = int(form["vehicle_year"])
        prior_claims_count = int(form["prior_claims_count"])
        territory = form["territory"].strip()
        coverage_limit = float(form["coverage_limit"])

        premium, breakdown = calculate_premium(
            driver_age=driver_age,
            vehicle_year=vehicle_year,
            prior_claims_count=prior_claims_count,
            territory=territory,
            coverage_limit=coverage_limit,
        )

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

    return render_template("quote_form.html", today=date.today().isoformat())


@bp.route("/<int:policy_id>")
def quote_result(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    dob = policy.policyholder.date_of_birth
    driver_age = date.today().year - dob.year - ((date.today().month, date.today().day) < (dob.month, dob.day))
    _, breakdown = calculate_premium(
        driver_age=driver_age,
        vehicle_year=policy.vehicle_year,
        prior_claims_count=policy.prior_claims_count,
        territory=policy.policyholder.territory,
        coverage_limit=policy.coverage_limit,
    )
    return render_template("quote_result.html", policy=policy, breakdown=breakdown)
