import os

from flask import Flask, g, render_template, request, session

from app.extensions import db
from app.auth import load_logged_in_user

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "uploads")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-not-for-production"),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'claims.db')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=UPLOAD_FOLDER,
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        API_KEY=os.environ.get("CLAIMS_API_KEY", "dev-api-key-change-me"),
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(os.path.dirname(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    from app.routes.auth import bp as auth_bp
    from app.routes.quotes import bp as quotes_bp
    from app.routes.claims import bp as claims_bp
    from app.routes.adjuster import bp as adjuster_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.api import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(quotes_bp)
    app.register_blueprint(claims_bp)
    app.register_blueprint(adjuster_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)

    @app.before_request
    def _load_user():
        load_logged_in_user()

    @app.after_request
    def _no_cache_for_dynamic_pages(response):
        # Every page here reflects who is logged in. Without this, a
        # browser can serve a cached copy of /claims/ (or the static file
        # cache, or the back/forward cache) from a *previous* login after
        # switching accounts in the same browser -- showing one user's data
        # under another user's session without ever hitting the server.
        if not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.context_processor
    def _inject_user():
        from app.models import Claim

        user = g.get("user", None)
        pending_review_count = None
        if user and (user.role == "adjuster" or session.get("reviewer_mode")):
            pending_review_count = Claim.query.filter_by(status="pending_review").count()
        return {"current_user": user, "pending_review_count": pending_review_count}

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/healthz")
    def healthz():
        # Used by the hosting platform's health check to know the process
        # is alive and can talk to its database, not just that it started.
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok"}, 200

    with app.app_context():
        db.create_all()

    return app
