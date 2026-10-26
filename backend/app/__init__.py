import os
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import HTTPException

from config import Config

db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, default_limits=["300 per hour"])


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    app.static_folder = str(frontend_dist)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    Config.init_app(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if app.config["STORAGE_BACKEND"] == "local":
        Path(app.config["STORAGE_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    from app import models  # noqa: F401
    from app.api import api

    app.register_blueprint(api, url_prefix="/api/v1")

    @app.before_request
    def enforce_csrf():
        public_auth_endpoint = request.endpoint in {"api.login", "api.register"}
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and session.get("user_id")
            and not public_auth_endpoint
        ):
            expected = session.get("csrf_token")
            supplied = request.headers.get("X-CSRF-Token", "")
            if not expected or not supplied or not __import__("hmac").compare_digest(
                expected, supplied
            ):
                return jsonify(error="Invalid or missing CSRF token."), 403

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled request failure")
        return jsonify(error="An unexpected server error occurred."), 500

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def serve_frontend(path):
        if path == "api" or path.startswith("api/"):
            abort(404)
        static_root = Path(app.static_folder)
        if path and (static_root / path).is_file():
            return send_from_directory(static_root, path)
        index_path = static_root / "index.html"
        if not index_path.is_file():
            abort(404)
        return send_from_directory(static_root, "index.html")

    return app
