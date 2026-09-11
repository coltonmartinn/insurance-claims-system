"""
Minimal stand-in for real authentication. There's no password check -- you
pick a seeded user from a dropdown and the app remembers your user id in the
session. The only thing that matters for this project is the `role` field,
which gates the adjuster queue. See models.User.
"""
from functools import wraps

from flask import session, redirect, url_for, g, abort

from app.extensions import db
from app.models import User


def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def adjuster_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        if g.user.role != "adjuster":
            abort(403)
        return view(*args, **kwargs)
    return wrapped
