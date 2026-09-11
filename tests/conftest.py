import os
import tempfile

import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    upload_dir = tempfile.mkdtemp()

    flask_app = create_app(test_config={
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "UPLOAD_FOLDER": upload_dir,
        "TESTING": True,
        "API_KEY": "test-api-key",
    })

    yield flask_app

    with flask_app.app_context():
        _db.session.remove()
        _db.engine.dispose()  # release the sqlite file handle -- Windows locks it otherwise

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    with app.app_context():
        yield _db.session
