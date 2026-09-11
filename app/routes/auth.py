from flask import Blueprint, render_template, request, redirect, url_for, session

from app.extensions import db
from app.models import User
from app.auth import login_required

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("user_id", type=int)
        user = db.session.get(User, user_id) if user_id else None
        if user:
            session["user_id"] = user.id
            if user.role == "adjuster":
                return redirect(url_for("adjuster.queue"))
            return redirect(url_for("claims.list_claims"))

    users = User.query.order_by(User.role.desc(), User.display_name).all()
    return render_template("login.html", users=users)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@bp.route("/toggle-reviewer-mode", methods=["POST"])
@login_required
def toggle_reviewer_mode():
    # A preview switch only, not a security control -- the adjuster-only
    # routes still enforce the real role check regardless of this flag, so
    # a customer flipping it just sees the reviewer-mode nav and gets a 403
    # if they actually click into a page they don't have access to.
    session["reviewer_mode"] = not session.get("reviewer_mode", False)
    return redirect(request.referrer or url_for("index"))
