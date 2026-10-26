import io
from pathlib import Path

from app.models import Artwork, AuditLog, VerificationRecord
from app.security import decrypt_bytes, encrypt_bytes
from app import db
from conftest import png_file, register, upload


def test_frontend_routes_serve_built_app_and_keep_api_not_found(client, app, tmp_path):
    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    (frontend_dist / "index.html").write_text("<main>ArtLock</main>", encoding="utf-8")
    app.static_folder = str(frontend_dist)

    assert client.get("/").status_code == 200
    assert client.get("/vault").data == b"<main>ArtLock</main>"
    assert client.get("/api/v1/not-a-route").status_code == 404


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
    with app.app_context():
        assert AuditLog.query.filter_by(action="user.login_failed").count() == 1


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
    import pytest

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
