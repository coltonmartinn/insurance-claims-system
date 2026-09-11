from flask import Blueprint, render_template, request, redirect, url_for, session

from app.extensions import db
from app.models import User

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
