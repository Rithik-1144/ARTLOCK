import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.models import Artwork, AuditLog, ForensicComparison, VerificationRecord
from app.security import decrypt_bytes, encrypt_bytes
from app import db
from conftest import png_file, register, upload


def patterned_png(invert=False):
    image = Image.new("RGB", (64, 64), "white")
    background = "black" if invert else "white"
    foreground = "white" if invert else "black"
    image.paste(background, (0, 0, 64, 64))
    ImageDraw.Draw(image).rectangle((0, 0, 31, 63), fill=foreground)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def test_frontend_routes_serve_built_app_and_keep_api_not_found(client, app, tmp_path):
    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    (frontend_dist / "index.html").write_text("<main>ArtLock</main>", encoding="utf-8")
    app.static_folder = str(frontend_dist)

    assert client.get("/").status_code == 200
    assert client.get("/vault").data == b"<main>ArtLock</main>"
    assert client.get("/api/v1/not-a-route").status_code == 404


def test_health_reports_unavailable_database_schema(app, client):
    with app.app_context():
        db.drop_all()

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json["status"] == "error"


def test_registration_authentication_and_workspace(app, client):
    token = register(client)
    assert client.get("/api/v1/auth/me").json["user"]["email"] == "artist@example.com"
    assert client.get("/api/v1/artworks").json["artworks"] == []
    logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token})
    assert logout.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "artist@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "artist@example.com", "password": "incorrect"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "incorrect"},
    ).status_code == 401
    with app.app_context():
        assert AuditLog.query.filter_by(action="user.login_failed").count() == 1


def test_authenticated_demo_seed_is_workspace_scoped_and_repeatable(app, client, monkeypatch, tmp_path):
    import seed_demo

    assert client.post("/api/v1/demo/seed").status_code == 401
    token = register(client)
    monkeypatch.setattr(seed_demo, "create_app", lambda: app)
    monkeypatch.setattr(
        seed_demo,
        "DEMO_ITEMS",
        [("Test Demo", "Generated sample artwork.", ("#101d31", "#52627d", "#f3c89e", "#354b55"))],
    )
    monkeypatch.setattr(seed_demo, "DEMO_CATEGORIES", ["Illustration"])
    app.config["DEMO_ASSETS_DIR"] = str(tmp_path)

    seeded = client.post("/api/v1/demo/seed", headers={"X-CSRF-Token": token})

    assert seeded.status_code == 200, seeded.json
    assert seeded.json["registered"] == 1
    assert len(client.get("/api/v1/artworks").json["artworks"]) == 1

    again = client.post("/api/v1/demo/seed", headers={"X-CSRF-Token": token})

    assert again.status_code == 200, again.json
    assert again.json["registered"] == 0
    assert again.json["already_present"] == 1
    assert len(client.get("/api/v1/artworks").json["artworks"]) == 1


def test_artwork_upload_encrypts_object_and_download_decrypts(app, client):
    token = register(client)
    source = png_file()
    expected_bytes = source.getvalue()
    response = upload(client, token, image=source)
    assert response.status_code == 201, response.json
    artwork = response.json["artwork"]
    assert len(artwork["sha256"]) == 64

    with app.app_context():
        record = db.session.get(Artwork, artwork["id"])
        stored = (app.config["STORAGE_DIR"] + "/" + record.storage_key).replace("/", "\\")
        from pathlib import Path

        ciphertext = Path(stored).read_bytes()
        assert ciphertext != expected_bytes

    download = client.get(f"/api/v1/artworks/{artwork['id']}/download")
    assert download.status_code == 200
    assert download.data == expected_bytes
    preview = client.get(f"/api/v1/artworks/{artwork['id']}/preview")
    assert preview.status_code == 200
    assert preview.mimetype == "image/webp"
    assert preview.headers["Cache-Control"] == "private, no-store"

    with app.app_context():
        record = db.session.get(Artwork, artwork["id"])
        object_path = Path(app.config["STORAGE_DIR"]) / record.storage_key
        object_path.write_bytes(b"tampered ciphertext")
    assert client.get(f"/api/v1/artworks/{artwork['id']}/download").status_code == 503


def test_same_bytes_match_and_changed_bytes_mismatch_are_persisted(app, client):
    token = register(client)
    source = png_file()
    source_bytes = source.getvalue()
    created = upload(client, token, image=source)
    artwork_id = created.json["artwork"]["id"]

    match = client.post(
        f"/api/v1/artworks/{artwork_id}/verify",
        headers={"X-CSRF-Token": token},
        data={"file": (io.BytesIO(source_bytes), "candidate.png")},
        content_type="multipart/form-data",
    )
    assert match.status_code == 200
    assert match.json["result"] == "MATCH"
    assert match.json["registered_sha256"] == match.json["calculated_sha256"]

    mismatch = client.post(
        f"/api/v1/artworks/{artwork_id}/verify",
        headers={"X-CSRF-Token": token},
        data={"file": (png_file((10, 90, 200)), "changed.png")},
        content_type="multipart/form-data",
    )
    assert mismatch.status_code == 200
    assert mismatch.json["result"] == "MISMATCH"
    with app.app_context():
        assert [item.result for item in VerificationRecord.query.order_by(VerificationRecord.id)] == [
            "MATCH",
            "MISMATCH",
        ]


def test_forensics_persists_encrypted_comparison_previews_and_report(app, client):
    token = register(client)
    original = patterned_png()
    original_bytes = original.getvalue()
    artwork = upload(client, token, title="Pattern study", image=original).json["artwork"]
    comparison_response = client.post(
        "/api/v1/forensics/comparisons",
        headers={"X-CSRF-Token": token},
        data={
            "artwork_id": artwork["id"],
            "file": (io.BytesIO(original_bytes), "same-pattern.png"),
        },
        content_type="multipart/form-data",
    )
    assert comparison_response.status_code == 201, comparison_response.json
    comparison = comparison_response.json["comparison"]
    assert comparison["exact_match"] is True
    assert comparison["similarity_percent"] == 100
    assert comparison["similarity_method"] == "dhash-8x8-v1"
    assert (comparison["artwork_width"], comparison["artwork_height"]) == (64, 64)
    assert (comparison["candidate_width"], comparison["candidate_height"]) == (64, 64)

    with app.app_context():
        record = db.session.get(ForensicComparison, comparison["id"])
        encrypted_candidate = (Path(app.config["STORAGE_DIR"]) / record.candidate_storage_key).read_bytes()
        assert encrypted_candidate != original_bytes
        assert record.candidate_sha256 == artwork["sha256"]

    history = client.get("/api/v1/forensics/comparisons")
    assert history.status_code == 200
    assert [item["id"] for item in history.json["comparisons"]] == [comparison["id"]]
    candidate_preview = client.get(comparison["preview_url"])
    registered_preview = client.get(comparison["artwork_preview_url"])
    assert candidate_preview.status_code == registered_preview.status_code == 200
    assert candidate_preview.mimetype == registered_preview.mimetype == "image/webp"
    assert candidate_preview.headers["Cache-Control"] == "private, no-store"

    report = client.get(comparison["report_url"])
    assert report.status_code == 200
    assert report.mimetype == "application/json"
    report_data = json.loads(report.data)
    assert report_data["integrity"]["exact_sha256_match"] is True
    assert report_data["visual_similarity"]["method"] == "dhash-8x8-v1"
    assert any("does not establish ownership" in item for item in report_data["limitations"])


def test_forensics_visual_estimate_and_pdf_hash_only(app, client):
    token = register(client)
    artwork = upload(client, token, image=patterned_png()).json["artwork"]
    visual = client.post(
        "/api/v1/forensics/comparisons",
        headers={"X-CSRF-Token": token},
        data={
            "artwork_id": artwork["id"],
            "file": (patterned_png(invert=True), "inverse.png"),
        },
        content_type="multipart/form-data",
    )
    assert visual.status_code == 201, visual.json
    assert visual.json["comparison"]["exact_match"] is False
    assert visual.json["comparison"]["similarity_percent"] is not None

    pdf = client.post(
        "/api/v1/forensics/comparisons",
        headers={"X-CSRF-Token": token},
        data={
            "artwork_id": artwork["id"],
            "file": (io.BytesIO(b"%PDF-1.4\nminimal test document"), "candidate.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert pdf.status_code == 201, pdf.json
    assert pdf.json["comparison"]["exact_match"] is False
    assert pdf.json["comparison"]["similarity_percent"] is None
    assert pdf.json["comparison"]["similarity_method"] is None
    assert pdf.json["comparison"]["candidate_width"] is None


def test_forensics_storage_failure_reports_error_without_history(client, monkeypatch):
    from app.storage import StorageError

    token = register(client)
    artwork = upload(client, token).json["artwork"]
    deleted_keys = []
    from app.api import get_storage

    with client.application.app_context():
        existing_storage = get_storage()

    class FailedStorage:
        def get(self, key):
            return existing_storage.get(key)

        def put(self, key, content):
            raise StorageError("storage unavailable")

        def delete(self, key):
            deleted_keys.append(key)

    monkeypatch.setattr("app.api.get_storage", lambda: FailedStorage())
    response = client.post(
        "/api/v1/forensics/comparisons",
        headers={"X-CSRF-Token": token},
        data={
            "artwork_id": artwork["id"],
            "file": (png_file(), "candidate.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 503
    assert "could not be saved securely" in response.json["error"]
    assert len(deleted_keys) == 1
    assert client.get("/api/v1/forensics/comparisons").json["comparisons"] == []


def test_forensics_requires_auth_and_csrf_and_is_workspace_scoped(client):
    assert client.get("/api/v1/forensics/comparisons").status_code == 401
    first_token = register(client)
    artwork = upload(client, first_token).json["artwork"]
    missing_csrf = client.post(
        "/api/v1/forensics/comparisons",
        data={
            "artwork_id": artwork["id"],
            "file": (png_file(), "candidate.png"),
        },
        content_type="multipart/form-data",
    )
    assert missing_csrf.status_code == 403
    created = client.post(
        "/api/v1/forensics/comparisons",
        headers={"X-CSRF-Token": first_token},
        data={
            "artwork_id": artwork["id"],
            "file": (png_file(), "candidate.png"),
        },
        content_type="multipart/form-data",
    )
    assert created.status_code == 201
    comparison = created.json["comparison"]

    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": first_token})
    second_token = register(client, "other@example.com")
    assert client.get("/api/v1/forensics/comparisons").json["comparisons"] == []
    for suffix in ("candidate-preview", "artwork-preview", "report"):
        assert client.get(f"/api/v1/forensics/comparisons/{comparison['id']}/{suffix}").status_code == 404
    cross_workspace = client.post(
        "/api/v1/forensics/comparisons",
        headers={"X-CSRF-Token": second_token},
        data={
            "artwork_id": artwork["id"],
            "file": (png_file(), "candidate.png"),
        },
        content_type="multipart/form-data",
    )
    assert cross_workspace.status_code == 404


def test_csrf_duplicate_upload_validation_and_cross_workspace_access(client):
    token = register(client)
    created = upload(client, token)
    artwork_id = created.json["artwork"]["id"]
    assert upload(client, token).status_code == 409
    csrf_failure = client.post(
        "/api/v1/artworks",
        data={"title": "Blocked", "file": (png_file(), "blocked.png")},
        content_type="multipart/form-data",
    )
    assert csrf_failure.status_code == 403
    assert client.post(
        "/api/v1/artworks",
        headers={"X-CSRF-Token": token},
        data={"title": "Bad", "file": (io.BytesIO(b"not an image"), "bad.png")},
        content_type="multipart/form-data",
    ).status_code == 400

    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": token})
    register(client, "other@example.com")
    assert client.get(f"/api/v1/artworks/{artwork_id}").status_code == 404
    assert client.get(f"/api/v1/artworks/{artwork_id}/download").status_code == 404
    assert client.get(f"/api/v1/artworks/{artwork_id}/preview").status_code == 404


def test_versions_keep_historical_record(app, client):
    token = register(client)
    artwork = upload(client, token).json["artwork"]
    response = client.post(
        f"/api/v1/artworks/{artwork['id']}/versions",
        headers={"X-CSRF-Token": token},
        data={
            "notes": "Color correction",
            "file": (png_file((30, 80, 150)), "blue-study.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.json
    details = client.get(f"/api/v1/artworks/{artwork['id']}").json["artwork"]
    assert details["version_number"] == 2
    assert [version["version_number"] for version in details["versions"]] == [2, 1]
    assert details["versions"][1]["sha256"] == artwork["sha256"]


def test_aes_gcm_rejects_modified_ciphertext(app):
    key = app.config["ENCRYPTION_KEY"]
    ciphertext, nonce = encrypt_bytes(b"private artwork bytes", key)
    assert decrypt_bytes(ciphertext, nonce, key) == b"private artwork bytes"
    corrupted = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
    with pytest.raises(Exception):
        decrypt_bytes(corrupted, nonce, key)


def test_storage_failure_is_reported_and_does_not_register_artwork(client, monkeypatch):
    from app.storage import StorageError

    class FailedStorage:
        def put(self, key, content):
            raise StorageError("storage unavailable")

    monkeypatch.setattr("app.api.get_storage", lambda: FailedStorage())
    token = register(client)
    response = upload(client, token)
    assert response.status_code == 503
    assert client.get("/api/v1/artworks").json["artworks"] == []


def test_s3_compatible_storage_uses_endpoint_credentials_and_skips_aws_sse(monkeypatch):
    import boto3

    from app.storage import ObjectStorage, StorageError

    calls = {}

    class FakeClient:
        def put_object(self, **kwargs):
            calls["put"] = kwargs

    def fake_client(service, **kwargs):
        calls["client"] = (service, kwargs)
        return FakeClient()

    monkeypatch.setattr(boto3, "client", fake_client)
    config = {
        "STORAGE_BACKEND": "s3",
        "S3_BUCKET": "artlock-demo",
        "AWS_REGION": "auto",
        "S3_ENDPOINT_URL": "https://account-id.r2.cloudflarestorage.com",
        "S3_ACCESS_KEY_ID": "test-access-key",
        "S3_SECRET_ACCESS_KEY": "test-secret-key",
    }

    storage = ObjectStorage(config)
    storage.put("workspace/artwork/object.enc", b"encrypted-demo-bytes")

    assert calls["client"] == (
        "s3",
        {
            "region_name": "auto",
            "endpoint_url": config["S3_ENDPOINT_URL"],
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
        },
    )
    assert calls["put"] == {
        "Bucket": "artlock-demo",
        "Key": "workspace/artwork/object.enc",
        "Body": b"encrypted-demo-bytes",
    }

    config["S3_ACCESS_KEY_ID"] = ""
    with pytest.raises(StorageError, match="required for a custom S3 endpoint"):
        ObjectStorage(config)


def test_aws_s3_storage_keeps_server_side_encryption(monkeypatch):
    import boto3

    from app.storage import ObjectStorage

    calls = {}

    class FakeClient:
        def put_object(self, **kwargs):
            calls["put"] = kwargs

    monkeypatch.setattr(boto3, "client", lambda service, **kwargs: FakeClient())
    storage = ObjectStorage(
        {
            "STORAGE_BACKEND": "s3",
            "S3_BUCKET": "artlock-demo",
            "AWS_REGION": "ap-southeast-2",
            "S3_ENDPOINT_URL": None,
            "S3_ACCESS_KEY_ID": None,
            "S3_SECRET_ACCESS_KEY": None,
        }
    )

    storage.put("workspace/artwork/object.enc", b"encrypted-demo-bytes")

    assert calls["put"]["ServerSideEncryption"] == "AES256"


def test_favorites_categories_tags_search_sort_and_inventory_export(client):
    token = register(client)
    first = upload(client, token, title="Amber sky").json["artwork"]
    second = upload(client, token, title="Blue horizon", image=png_file((20, 80, 170))).json["artwork"]

    update = client.patch(
        f"/api/v1/artworks/{first['id']}",
        headers={"X-CSRF-Token": token},
        json={
            "favorite": True,
            "category": "Landscape",
            "tags": [" evening ", "sky", "SKY"],
        },
    )
    assert update.status_code == 200
    assert update.json["artwork"]["favorite"] is True
    assert update.json["artwork"]["category"] == "Landscape"
    assert update.json["artwork"]["tags"] == ["evening", "sky"]

    assert client.get("/api/v1/artworks?favorite=true").json["artworks"][0]["id"] == first["id"]
    assert client.get("/api/v1/artworks?category=Landscape").json["artworks"][0]["id"] == first["id"]
    assert client.get("/api/v1/artworks?q=evening").json["artworks"][0]["id"] == first["id"]
    sorted_items = client.get("/api/v1/artworks?sort=name").json["artworks"]
    assert [item["title"] for item in sorted_items] == ["Amber sky", "Blue horizon"]

    stats = client.get("/api/v1/analytics/overview").json
    assert stats["favorite_count"] == 1
    assert {item["name"]: item["count"] for item in stats["categories"]} == {
        "Landscape": 1,
        "Uncategorized": 1,
    }
    assert stats["versions_count"] == 2
    assert len(stats["storage_trend"]) == 14

    export = client.get("/api/v1/analytics/inventory.csv")
    assert export.status_code == 200
    assert export.mimetype == "text/csv"
    assert "Amber sky" in export.text and "Blue horizon" in export.text

    invalid_update = client.patch(
        f"/api/v1/artworks/{first['id']}",
        headers={"X-CSRF-Token": token},
        json={"title": "Should not persist", "tags": "invalid"},
    )
    assert invalid_update.status_code == 400
    assert client.get(f"/api/v1/artworks/{first['id']}").json["artwork"]["title"] == "Amber sky"
