import io
import base64
import secrets
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db


@pytest.fixture()
def app(tmp_path):
    encryption_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    app = create_app(
        {
            "TESTING": True,
            "APP_ENV": "testing",
            "SECRET_KEY": "test-secret",
            "ENCRYPTION_KEY": encryption_key,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "STORAGE_BACKEND": "local",
            "STORAGE_DIR": str(tmp_path / "objects"),
            "RATELIMIT_ENABLED": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def png_file(color=(200, 40, 50)):
    image = Image.new("RGB", (12, 12), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def register(client, email="artist@example.com"):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "display_name": "Studio Artist",
            "workspace_name": "Test Studio",
        },
    )
    assert response.status_code == 201, response.json
    return response.json["csrf_token"]


def upload(client, token, title="Sunset Study", image=None):
    return client.post(
        "/api/v1/artworks",
        headers={"X-CSRF-Token": token},
        data={
            "title": title,
            "description": "A test artwork",
            "file": (image or png_file(), "sunset.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
