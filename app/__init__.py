import os

from flask import Flask, g, render_template

from app.extensions import db
from app.auth import load_logged_in_user

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "uploads")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="dev-secret-key-not-for-production",
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

    @app.context_processor
    def _inject_user():
        return {"current_user": g.get("user", None)}

    @app.route("/")
    def index():
        return render_template("index.html")

    with app.app_context():
        db.create_all()

    return app
