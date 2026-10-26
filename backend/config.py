import base64
import hashlib
import os
from pathlib import Path


class Config:
    APP_ENV = os.getenv("ARTLOCK_ENV", "development")
    SECRET_KEY = os.getenv("ARTLOCK_SECRET_KEY", "local-development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path(__file__).resolve().parent / 'instance' / 'artlock.db'}",
    )
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    elif SQLALCHEMY_DATABASE_URI.startswith("postgresql://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    STORAGE_DIR = os.getenv(
        "LOCAL_STORAGE_DIR",
        str(Path(__file__).resolve().parent / "instance" / "objects"),
    )
    S3_BUCKET = os.getenv("S3_BUCKET")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL") or None
    S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
    S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
    ENCRYPTION_KEY = os.getenv("ARTLOCK_ENCRYPTION_KEY")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    @classmethod
    def init_app(cls, app):
        if app.config.get("APP_ENV") == "production":
            secret_key = app.config.get("SECRET_KEY", "")
            if secret_key == "local-development-only-change-me" or len(secret_key) < 32:
                raise RuntimeError(
                    "ARTLOCK_SECRET_KEY must be set to at least 32 characters in production."
                )
            if not app.config.get("ENCRYPTION_KEY"):
                raise RuntimeError("ARTLOCK_ENCRYPTION_KEY must be set in production.")
        elif not app.config.get("ENCRYPTION_KEY"):
            app.config["ENCRYPTION_KEY"] = base64.urlsafe_b64encode(
                hashlib.sha256(app.config["SECRET_KEY"].encode()).digest()
            ).decode()
        try:
            key = base64.urlsafe_b64decode(app.config["ENCRYPTION_KEY"])
        except (ValueError, TypeError) as error:
            raise RuntimeError("ARTLOCK_ENCRYPTION_KEY must be URL-safe base64.") from error
        if len(key) != 32:
            raise RuntimeError("ARTLOCK_ENCRYPTION_KEY must decode to exactly 32 bytes.")
