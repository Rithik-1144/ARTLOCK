import base64
import csv
import io
import json
import secrets
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file, session
from flask import Response
from flask_limiter.util import get_remote_address
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from app import db, limiter
from app.models import (
    Artwork,
    ArtworkVersion,
    AuditLog,
    ForensicComparison,
    User,
    VerificationRecord,
    Workspace,
    WorkspaceMembership,
)
from app.forensics import SIMILARITY_METHOD, image_fingerprint, similarity_percent
from app.security import (
    decrypt_bytes,
    digest,
    encrypt_bytes,
    hash_password,
    verify_password,
)
from app.storage import ObjectStorage, StorageError

api = Blueprint("api", __name__)
ALLOWED_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


def error(message, status=400):
    return jsonify(error=message), status


def utc_isoformat(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def active_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


def active_workspace_id():
    user = active_user()
    if not user:
        return None
    membership = WorkspaceMembership.query.filter_by(user_id=user.id).first()
    return membership.workspace_id if membership else None


def log_event(action, target_id=None, outcome="success"):
    workspace_id = active_workspace_id()
    if workspace_id is None:
        return
    db.session.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_id=session.get("user_id"),
            action=action,
            target_id=target_id,
            outcome=outcome,
        )
    )


def serialize_artwork(artwork):
    return {
        "id": artwork.id,
        "title": artwork.title,
        "description": artwork.description,
        "filename": artwork.original_filename,
        "content_type": artwork.content_type,
        "file_size": artwork.file_size,
        "sha256": artwork.sha256,
        "version_number": artwork.version_number,
        "archived": artwork.archived,
        "favorite": artwork.favorite,
        "category": artwork.category,
        "tags": artwork.tags or [],
        "created_at": utc_isoformat(artwork.created_at),
        "creator": artwork.owner.display_name,
    }


def serialize_comparison(comparison):
    return {
        "id": comparison.id,
        "artwork_id": comparison.artwork_id,
        "artwork_title": comparison.artwork_title,
        "artwork_filename": comparison.artwork_filename,
        "artwork_content_type": comparison.artwork_content_type,
        "artwork_sha256": comparison.artwork_sha256,
        "candidate_filename": comparison.candidate_filename,
        "candidate_content_type": comparison.candidate_content_type,
        "candidate_file_size": comparison.candidate_file_size,
        "candidate_sha256": comparison.candidate_sha256,
        "artwork_width": comparison.artwork_width,
        "artwork_height": comparison.artwork_height,
        "candidate_width": comparison.candidate_width,
        "candidate_height": comparison.candidate_height,
        "exact_match": comparison.exact_match,
        "similarity_percent": comparison.similarity_percent,
        "similarity_method": comparison.similarity_method,
        "created_at": utc_isoformat(comparison.created_at),
        "preview_url": f"/api/v1/forensics/comparisons/{comparison.id}/candidate-preview",
        "artwork_preview_url": (
            f"/api/v1/forensics/comparisons/{comparison.id}/artwork-preview"
            if comparison.artwork_content_type.startswith("image/")
            else None
        ),
        "report_url": f"/api/v1/forensics/comparisons/{comparison.id}/report",
    }


def get_artwork(artwork_id):
    workspace_id = active_workspace_id()
    return Artwork.query.filter_by(id=artwork_id, workspace_id=workspace_id).first()


def get_storage():
    if "artlock_storage" not in current_app.extensions:
        current_app.extensions["artlock_storage"] = ObjectStorage(current_app.config)
    return current_app.extensions["artlock_storage"]


def decrypt_stored_object(storage_key, nonce, ciphertext_sha256, plaintext_sha256):
    ciphertext = get_storage().get(storage_key)
    if digest(ciphertext) != ciphertext_sha256:
        raise ValueError("Stored ciphertext checksum does not match its registered value.")
    content = decrypt_bytes(ciphertext, nonce, current_app.config["ENCRYPTION_KEY"])
    if digest(content) != plaintext_sha256:
        raise ValueError("Decrypted content checksum does not match its registered value.")
    return content


def private_image_preview(content):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                image = ImageOps.exif_transpose(source)
                image.thumbnail((900, 700))
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGBA" if "transparency" in image.info else "RGB")
                output = io.BytesIO()
                image.save(output, format="WEBP", quality=84, method=4)
                output.seek(0)
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError("Image preview could not be generated safely.") from exc
    response = send_file(output, mimetype="image/webp", max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    return response


def inspect_upload(file_storage):
    filename = secure_filename(file_storage.filename or "")
    if not filename or "." not in filename:
        raise ValueError("Choose a file with a supported extension.")
    content = file_storage.read()
    file_storage.stream.seek(0)
    if not content:
        raise ValueError("The selected file is empty.")
    max_bytes = current_app.config["MAX_CONTENT_LENGTH"]
    if len(content) > max_bytes:
        raise ValueError(f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit.")

    if content.startswith(b"%PDF-"):
        content_type = "application/pdf"
    else:
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
                content_type = Image.MIME.get(image.format)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError("File content must be a valid PNG, JPEG, WebP, or PDF.") from exc

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("File content must be a valid PNG, JPEG, WebP, or PDF.")
    extension = "." + filename.rsplit(".", 1)[-1].lower()
    if extension != ALLOWED_CONTENT_TYPES[content_type] and not (
        content_type == "image/jpeg" and extension in {".jpeg", ".jpg"}
    ):
        raise ValueError("The filename extension does not match the file content.")
    return filename, content_type, content


def store_version(artwork, user, filename, content_type, content, notes=""):
    encrypted, nonce = encrypt_bytes(content, current_app.config["ENCRYPTION_KEY"])
    object_key = f"{artwork.workspace_id}/{artwork.id}/{uuid.uuid4().hex}.enc"
    get_storage().put(object_key, encrypted)
    version_number = artwork.version_number + 1
    version = ArtworkVersion(
        id=str(uuid.uuid4()),
        artwork_id=artwork.id,
        version_number=version_number,
        filename=filename,
        content_type=content_type,
        file_size=len(content),
        sha256=digest(content),
        ciphertext_sha256=digest(encrypted),
        storage_key=object_key,
        nonce=nonce,
        notes=notes[:500],
        uploaded_by=user.id,
    )
    artwork.version_number = version_number
    artwork.original_filename = filename
    artwork.content_type = content_type
    artwork.file_size = len(content)
    artwork.sha256 = version.sha256
    artwork.ciphertext_sha256 = version.ciphertext_sha256
    artwork.storage_key = object_key
    artwork.nonce = nonce
    db.session.add(version)
    return version


@api.get("/health")
def health():
    try:
        db.session.execute(db.select(User.id).limit(1))
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Health check could not query the application database")
        return jsonify(
            status="error",
            error="Database is unavailable or its migrations have not been applied.",
        ), 503
    return jsonify(status="ok", storage=current_app.config["STORAGE_BACKEND"])


@api.post("/auth/register")
@limiter.limit("5 per hour", key_func=get_remote_address)
def register():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    display_name = str(data.get("display_name", "")).strip()
    workspace_name = str(data.get("workspace_name", "")).strip() or "My Workspace"
    if not email or "@" not in email or len(email) > 255:
        return error("Enter a valid email address.")
    if len(password) < 12:
        return error("Password must contain at least 12 characters.")
    if not display_name or len(display_name) > 120:
        return error("Enter a display name (up to 120 characters).")
    if User.query.filter_by(email=email).first():
        return error("An account with this email already exists.", 409)

    user = User(email=email, password_hash=hash_password(password), display_name=display_name)
    workspace = Workspace(name=workspace_name[:120])
    db.session.add_all([user, workspace])
    db.session.flush()
    db.session.add(WorkspaceMembership(user_id=user.id, workspace_id=workspace.id, role="owner"))
    db.session.flush()
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["csrf_token"] = secrets.token_urlsafe(32)
    log_event("user.registered")
    db.session.commit()
    return jsonify(
        user={"email": user.email, "display_name": user.display_name},
        workspace=workspace.name,
        csrf_token=session["csrf_token"],
    ), 201


@api.post("/auth/login")
@limiter.limit("10 per minute", key_func=get_remote_address)
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(user.password_hash, str(data.get("password", ""))):
        if user:
            membership = WorkspaceMembership.query.filter_by(user_id=user.id).first()
            if membership:
                db.session.add(
                    AuditLog(
                        workspace_id=membership.workspace_id,
                        actor_id=user.id,
                        action="user.login_failed",
                        outcome="failure",
                    )
                )
                db.session.commit()
        return error("Email or password is incorrect.", 401)
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["csrf_token"] = secrets.token_urlsafe(32)
    log_event("user.login")
    db.session.commit()
    membership = WorkspaceMembership.query.filter_by(user_id=user.id).first()
    return jsonify(
        user={"email": user.email, "display_name": user.display_name},
        workspace=membership.workspace.name if membership else "Workspace",
        csrf_token=session["csrf_token"],
    )


@api.post("/auth/logout")
def logout():
    if not active_user():
        return error("Authentication required.", 401)
    log_event("user.logout")
    db.session.commit()
    session.clear()
    return jsonify(status="logged_out")


@api.get("/auth/me")
def me():
    user = active_user()
    if not user:
        return error("Authentication required.", 401)
    membership = WorkspaceMembership.query.filter_by(user_id=user.id).first()
    return jsonify(
        user={"email": user.email, "display_name": user.display_name},
        workspace=membership.workspace.name,
        role=membership.role,
        csrf_token=session["csrf_token"],
    )


@api.get("/artworks")
def list_artworks():
    if not active_user():
        return error("Authentication required.", 401)
    query = Artwork.query.filter_by(workspace_id=active_workspace_id())
    archived = request.args.get("archived", "false").lower() == "true"
    query = query.filter_by(archived=archived)
    search = request.args.get("q", "").strip()
    if search:
        pattern = f"%{search[:100]}%"
        query = query.filter(
            db.or_(
                Artwork.title.ilike(pattern),
                Artwork.description.ilike(pattern),
                Artwork.original_filename.ilike(pattern),
                Artwork.category.ilike(pattern),
                db.cast(Artwork.tags, db.String).ilike(pattern),
            )
        )
    file_type = request.args.get("type", "").strip()[:100]
    if file_type:
        query = query.filter_by(content_type=file_type)
    category = request.args.get("category", "").strip()[:80]
    if category:
        query = query.filter_by(category=category)
    if request.args.get("favorite", "").lower() == "true":
        query = query.filter_by(favorite=True)
    sort = request.args.get("sort", "newest")
    ordering = {
        "newest": Artwork.created_at.desc(),
        "oldest": Artwork.created_at.asc(),
        "name": Artwork.title.asc(),
        "size": Artwork.file_size.desc(),
    }
    query = query.order_by(ordering.get(sort, Artwork.created_at.desc()))
    artworks = query.limit(200).all()
    return jsonify(artworks=[serialize_artwork(item) for item in artworks])


@api.post("/demo/seed")
def seed_demo_workspace():
    user = active_user()
    if not user:
        return error("Authentication required.", 401)
    try:
        from seed_demo import seed_account

        summary = seed_account(
            user.email,
            Path(
                current_app.config.get(
                    "DEMO_ASSETS_DIR",
                    Path(current_app.root_path).parent / "demo_assets",
                )
            ),
        )
    except (RuntimeError, SystemExit):
        current_app.logger.exception("Demo gallery could not be loaded")
        return error("The demonstration gallery could not be loaded. Please try again.", 503)
    return jsonify(**summary)


@api.post("/artworks")
def create_artwork():
    user = active_user()
    if not user:
        return error("Authentication required.", 401)
    file = request.files.get("file")
    title = request.form.get("title", "").strip()
    if not file:
        return error("Select an artwork file.")
    if not title or len(title) > 200:
        return error("Enter an artwork title (up to 200 characters).")
    try:
        filename, content_type, content = inspect_upload(file)
        workspace_id = active_workspace_id()
        file_hash = digest(content)
        duplicate = Artwork.query.filter_by(workspace_id=workspace_id, sha256=file_hash).first()
        if duplicate:
            return error(f"This file is already registered as “{duplicate.title}”.", 409)
        encrypted, nonce = encrypt_bytes(content, current_app.config["ENCRYPTION_KEY"])
        artwork_id = str(uuid.uuid4())
        object_key = f"{workspace_id}/{artwork_id}/{uuid.uuid4().hex}.enc"
        get_storage().put(object_key, encrypted)
        artwork = Artwork(
            id=artwork_id,
            workspace_id=workspace_id,
            owner_id=user.id,
            title=title,
            description=request.form.get("description", "").strip()[:4000],
            original_filename=filename,
            content_type=content_type,
            file_size=len(content),
            sha256=file_hash,
            ciphertext_sha256=digest(encrypted),
            storage_key=object_key,
            nonce=nonce,
            category=request.form.get("category", "").strip()[:80] or "Uncategorized",
            tags=[],
        )
        db.session.add(artwork)
        db.session.flush()
        db.session.add(
            ArtworkVersion(
                id=str(uuid.uuid4()),
                artwork_id=artwork.id,
                version_number=1,
                filename=filename,
                content_type=content_type,
                file_size=len(content),
                sha256=file_hash,
                ciphertext_sha256=artwork.ciphertext_sha256,
                storage_key=object_key,
                nonce=nonce,
                notes="Initial registration",
                uploaded_by=user.id,
            )
        )
        log_event("artwork.registered", artwork.id)
        db.session.commit()
        return jsonify(artwork=serialize_artwork(artwork)), 201
    except ValueError as exc:
        return error(str(exc))
    except StorageError:
        db.session.rollback()
        current_app.logger.exception("Artwork storage failed")
        return error("Artwork could not be stored. Check the configured storage service.", 503)


@api.get("/artworks/<artwork_id>")
def artwork_detail(artwork_id):
    if not active_user():
        return error("Authentication required.", 401)
    artwork = get_artwork(artwork_id)
    if not artwork:
        return error("Artwork not found.", 404)
    result = serialize_artwork(artwork)
    result["versions"] = [
        {
            "id": version.id,
            "version_number": version.version_number,
            "filename": version.filename,
            "file_size": version.file_size,
            "sha256": version.sha256,
            "notes": version.notes,
            "created_at": utc_isoformat(version.created_at),
        }
        for version in artwork.versions
    ]
    return jsonify(artwork=result)


@api.patch("/artworks/<artwork_id>")
def update_artwork(artwork_id):
    if not active_user():
        return error("Authentication required.", 401)
    artwork = get_artwork(artwork_id)
    if not artwork:
        return error("Artwork not found.", 404)
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    description = data.get("description")
    next_title = artwork.title
    next_description = artwork.description
    next_category = artwork.category
    next_tags = artwork.tags or []
    next_archived = artwork.archived
    next_favorite = artwork.favorite
    if title is not None:
        title = str(title).strip()
        if not title or len(title) > 200:
            return error("Artwork title must contain 1–200 characters.")
        next_title = title
    if description is not None:
        next_description = str(description).strip()[:4000]
    if "archived" in data:
        if not isinstance(data["archived"], bool):
            return error("Archived must be a boolean.")
        next_archived = data["archived"]
    if "favorite" in data:
        if not isinstance(data["favorite"], bool):
            return error("Favorite must be a boolean.")
        next_favorite = data["favorite"]
    if "category" in data:
        category = str(data["category"]).strip()
        if not category or len(category) > 80:
            return error("Category must contain 1–80 characters.")
        next_category = category
    if "tags" in data:
        tags = data["tags"]
        if not isinstance(tags, list) or len(tags) > 20:
            return error("Tags must be a list containing at most 20 values.")
        normalized = []
        for tag in tags:
            value = str(tag).strip()
            if not value or len(value) > 32:
                return error("Each tag must contain 1–32 characters.")
            if value.casefold() not in {existing.casefold() for existing in normalized}:
                normalized.append(value)
        next_tags = normalized
    artwork.title = next_title
    artwork.description = next_description
    artwork.archived = next_archived
    artwork.favorite = next_favorite
    artwork.category = next_category
    artwork.tags = next_tags
    log_event("artwork.updated", artwork.id)
    db.session.commit()
    return jsonify(artwork=serialize_artwork(artwork))


@api.post("/artworks/<artwork_id>/verify")
def verify_artwork(artwork_id):
    user = active_user()
    if not user:
        return error("Authentication required.", 401)
    artwork = get_artwork(artwork_id)
    if not artwork:
        return error("Artwork not found.", 404)
    file = request.files.get("file")
    if not file:
        return error("Select a file to compare.")
    try:
        _, _, content = inspect_upload(file)
    except ValueError as exc:
        return error(str(exc))
    calculated = digest(content)
    result = "MATCH" if secrets.compare_digest(artwork.sha256, calculated) else "MISMATCH"
    record = VerificationRecord(
        artwork_id=artwork.id,
        user_id=user.id,
        expected_sha256=artwork.sha256,
        calculated_sha256=calculated,
        result=result,
    )
    db.session.add(record)
    log_event("artwork.verified", artwork.id, result.lower())
    db.session.commit()
    return jsonify(
        result=result,
        registered_sha256=artwork.sha256,
        calculated_sha256=calculated,
        verified_at=utc_isoformat(record.created_at),
    )


@api.post("/forensics/comparisons")
def create_forensic_comparison():
    user = active_user()
    if not user:
        return error("Authentication required.", 401)
    artwork = get_artwork(request.form.get("artwork_id", ""))
    if not artwork:
        return error("Artwork not found.", 404)
    file = request.files.get("file")
    if not file:
        return error("Select a candidate file to compare.")
    try:
        filename, content_type, content = inspect_upload(file)
    except ValueError as exc:
        return error(str(exc))

    try:
        artwork_content = decrypt_stored_object(
            artwork.storage_key,
            artwork.nonce,
            artwork.ciphertext_sha256,
            artwork.sha256,
        )
    except (StorageError, ValueError):
        db.session.rollback()
        current_app.logger.exception("Forensic comparison could not retrieve registered artwork")
        return error("Registered artwork could not be securely retrieved.", 503)
    artwork_width = artwork_height = artwork_dhash = None
    candidate_width = candidate_height = candidate_dhash = None
    try:
        if artwork.content_type.startswith("image/"):
            artwork_width, artwork_height, artwork_dhash = image_fingerprint(artwork_content)
    except ValueError:
        current_app.logger.exception("Registered artwork image could not be analyzed")
        return error("Registered artwork image could not be analyzed safely.", 503)
    try:
        if content_type.startswith("image/"):
            candidate_width, candidate_height, candidate_dhash = image_fingerprint(content)
    except ValueError as exc:
        return error(str(exc))

    exact_match = secrets.compare_digest(artwork.sha256, digest(content))
    visual_similarity = (
        similarity_percent(artwork_dhash, candidate_dhash)
        if artwork_dhash is not None and candidate_dhash is not None
        else None
    )
    comparison_id = str(uuid.uuid4())
    encrypted, nonce = encrypt_bytes(content, current_app.config["ENCRYPTION_KEY"])
    candidate_key = f"{artwork.workspace_id}/forensics/{comparison_id}.enc"
    try:
        get_storage().put(candidate_key, encrypted)
        comparison = ForensicComparison(
            id=comparison_id,
            workspace_id=artwork.workspace_id,
            artwork_id=artwork.id,
            user_id=user.id,
            artwork_title=artwork.title,
            artwork_filename=artwork.original_filename,
            artwork_content_type=artwork.content_type,
            artwork_sha256=artwork.sha256,
            artwork_ciphertext_sha256=artwork.ciphertext_sha256,
            artwork_storage_key=artwork.storage_key,
            artwork_nonce=artwork.nonce,
            candidate_filename=filename,
            candidate_content_type=content_type,
            candidate_file_size=len(content),
            candidate_sha256=digest(content),
            candidate_ciphertext_sha256=digest(encrypted),
            candidate_storage_key=candidate_key,
            candidate_nonce=nonce,
            artwork_width=artwork_width,
            artwork_height=artwork_height,
            candidate_width=candidate_width,
            candidate_height=candidate_height,
            artwork_dhash=artwork_dhash,
            candidate_dhash=candidate_dhash,
            exact_match=exact_match,
            similarity_percent=visual_similarity,
            similarity_method=SIMILARITY_METHOD if visual_similarity is not None else None,
        )
        db.session.add(comparison)
        log_event("forensics.compared", artwork.id, "match" if exact_match else "mismatch")
        db.session.commit()
    except (StorageError, SQLAlchemyError):
        db.session.rollback()
        current_app.logger.exception("Forensic comparison could not be persisted")
        try:
            get_storage().delete(candidate_key)
        except StorageError:
            current_app.logger.exception("Failed to remove an unreferenced forensic candidate")
        return error("Forensic comparison could not be saved securely.", 503)

    return jsonify(comparison=serialize_comparison(comparison)), 201


@api.get("/forensics/comparisons")
def list_forensic_comparisons():
    if not active_user():
        return error("Authentication required.", 401)
    comparisons = (
        ForensicComparison.query.filter_by(workspace_id=active_workspace_id())
        .order_by(ForensicComparison.created_at.desc())
        .limit(100)
        .all()
    )
    return jsonify(comparisons=[serialize_comparison(item) for item in comparisons])


def get_forensic_comparison(comparison_id):
    return ForensicComparison.query.filter_by(
        id=comparison_id,
        workspace_id=active_workspace_id(),
    ).first()


@api.get("/forensics/comparisons/<comparison_id>/candidate-preview")
def preview_forensic_candidate(comparison_id):
    if not active_user():
        return error("Authentication required.", 401)
    comparison = get_forensic_comparison(comparison_id)
    if not comparison:
        return error("Comparison not found.", 404)
    if not comparison.candidate_content_type.startswith("image/"):
        return error("Preview is available for image candidates only.", 415)
    try:
        content = decrypt_stored_object(
            comparison.candidate_storage_key,
            comparison.candidate_nonce,
            comparison.candidate_ciphertext_sha256,
            comparison.candidate_sha256,
        )
        return private_image_preview(content)
    except (StorageError, ValueError, UnidentifiedImageError, OSError):
        current_app.logger.exception("Forensic candidate preview could not be generated")
        return error("Candidate preview could not be securely generated.", 503)


@api.get("/forensics/comparisons/<comparison_id>/artwork-preview")
def preview_forensic_artwork(comparison_id):
    if not active_user():
        return error("Authentication required.", 401)
    comparison = get_forensic_comparison(comparison_id)
    if not comparison:
        return error("Comparison not found.", 404)
    if not comparison.artwork_content_type.startswith("image/"):
        return error("Preview is available for image artwork only.", 415)
    try:
        content = decrypt_stored_object(
            comparison.artwork_storage_key,
            comparison.artwork_nonce,
            comparison.artwork_ciphertext_sha256,
            comparison.artwork_sha256,
        )
        return private_image_preview(content)
    except (StorageError, ValueError, UnidentifiedImageError, OSError):
        current_app.logger.exception("Forensic artwork preview could not be generated")
        return error("Registered artwork preview could not be securely generated.", 503)


@api.get("/forensics/comparisons/<comparison_id>/report")
def download_forensic_report(comparison_id):
    if not active_user():
        return error("Authentication required.", 401)
    comparison = get_forensic_comparison(comparison_id)
    if not comparison:
        return error("Comparison not found.", 404)
    report = {
        "report_type": "ArtLock artwork comparison",
        "comparison": serialize_comparison(comparison),
        "integrity": {
            "exact_sha256_match": comparison.exact_match,
            "registered_sha256": comparison.artwork_sha256,
            "candidate_sha256": comparison.candidate_sha256,
        },
        "visual_similarity": (
            {
                "percent": comparison.similarity_percent,
                "method": comparison.similarity_method,
                "registered_dhash": comparison.artwork_dhash,
                "candidate_dhash": comparison.candidate_dhash,
            }
            if comparison.similarity_percent is not None
            else None
        ),
        "limitations": [
            "SHA-256 equality establishes byte equality only; it does not establish ownership, authorship, originality, or legal rights.",
            "The dHash similarity percentage is a perceptual screening estimate, not proof of copying, authorship, or ownership.",
        ],
    }
    output = io.BytesIO(json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"))
    response = send_file(
        output,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"artlock-comparison-{comparison.id}.json",
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


@api.post("/artworks/<artwork_id>/versions")
def create_version(artwork_id):
    user = active_user()
    if not user:
        return error("Authentication required.", 401)
    artwork = get_artwork(artwork_id)
    file = request.files.get("file")
    if not artwork:
        return error("Artwork not found.", 404)
    if not file:
        return error("Select a version file.")
    try:
        filename, content_type, content = inspect_upload(file)
        version = store_version(
            artwork, user, filename, content_type, content, request.form.get("notes", "")
        )
        log_event("artwork.version_created", artwork.id)
        db.session.commit()
        return jsonify(version_number=version.version_number, sha256=version.sha256), 201
    except ValueError as exc:
        return error(str(exc))
    except StorageError:
        db.session.rollback()
        current_app.logger.exception("Artwork version storage failed")
        return error("Artwork version could not be stored.", 503)


@api.get("/artworks/<artwork_id>/download")
def download_artwork(artwork_id):
    if not active_user():
        return error("Authentication required.", 401)
    artwork = get_artwork(artwork_id)
    if not artwork:
        return error("Artwork not found.", 404)
    try:
        ciphertext = get_storage().get(artwork.storage_key)
        if digest(ciphertext) != artwork.ciphertext_sha256:
            raise ValueError("Stored ciphertext checksum does not match its registered value.")
        content = decrypt_bytes(ciphertext, artwork.nonce, current_app.config["ENCRYPTION_KEY"])
        if digest(content) != artwork.sha256:
            raise ValueError("Decrypted artwork checksum does not match its registered value.")
        log_event("artwork.downloaded", artwork.id)
        db.session.commit()
        return send_file(
            io.BytesIO(content),
            mimetype=artwork.content_type,
            as_attachment=True,
            download_name=artwork.original_filename,
        )
    except (StorageError, ValueError):
        db.session.rollback()
        current_app.logger.exception("Artwork retrieval or decryption failed")
        return error("Artwork could not be securely retrieved.", 503)


@api.get("/artworks/<artwork_id>/preview")
def preview_artwork(artwork_id):
    if not active_user():
        return error("Authentication required.", 401)
    artwork = get_artwork(artwork_id)
    if not artwork:
        return error("Artwork not found.", 404)
    if not artwork.content_type.startswith("image/"):
        return error("Preview is available for image artwork only.", 415)
    try:
        ciphertext = get_storage().get(artwork.storage_key)
        if digest(ciphertext) != artwork.ciphertext_sha256:
            raise ValueError("Stored ciphertext checksum does not match its registered value.")
        content = decrypt_bytes(ciphertext, artwork.nonce, current_app.config["ENCRYPTION_KEY"])
        if digest(content) != artwork.sha256:
            raise ValueError("Decrypted artwork checksum does not match its registered value.")
        with Image.open(io.BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((900, 700))
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            output = io.BytesIO()
            image.save(output, format="WEBP", quality=84, method=4)
            output.seek(0)
        response = send_file(output, mimetype="image/webp", max_age=0)
        response.headers["Cache-Control"] = "private, no-store"
        return response
    except (StorageError, ValueError, UnidentifiedImageError, OSError):
        current_app.logger.exception("Artwork preview could not be generated")
        return error("Artwork preview could not be securely generated.", 503)


@api.post("/artworks/<artwork_id>/archive")
def archive_artwork(artwork_id):
    if not active_user():
        return error("Authentication required.", 401)
    artwork = get_artwork(artwork_id)
    if not artwork:
        return error("Artwork not found.", 404)
    artwork.archived = not artwork.archived
    log_event("artwork.archived" if artwork.archived else "artwork.restored", artwork.id)
    db.session.commit()
    return jsonify(artwork=serialize_artwork(artwork))


@api.get("/analytics/overview")
def analytics_overview():
    if not active_user():
        return error("Authentication required.", 401)
    workspace_id = active_workspace_id()
    artworks = Artwork.query.filter_by(workspace_id=workspace_id, archived=False).all()
    verification_counts = (
        db.session.query(VerificationRecord.result, db.func.count(VerificationRecord.id))
        .join(Artwork, Artwork.id == VerificationRecord.artwork_id)
        .filter(Artwork.workspace_id == workspace_id)
        .group_by(VerificationRecord.result)
        .all()
    )
    recent = Artwork.query.filter_by(workspace_id=workspace_id).order_by(
        Artwork.created_at.desc()
    ).limit(5)
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=13)
    daily_counts = (
        db.session.query(db.func.date(Artwork.created_at), db.func.count(Artwork.id))
        .filter(
            Artwork.workspace_id == workspace_id,
            Artwork.created_at >= datetime.combine(start_date, datetime.min.time(), timezone.utc),
        )
        .group_by(db.func.date(Artwork.created_at))
        .all()
    )
    counts_by_date = {str(day): count for day, count in daily_counts}
    categories = (
        db.session.query(Artwork.category, db.func.count(Artwork.id))
        .filter(Artwork.workspace_id == workspace_id, Artwork.archived.is_(False))
        .group_by(Artwork.category)
        .order_by(db.func.count(Artwork.id).desc(), Artwork.category.asc())
        .limit(6)
        .all()
    )
    versions_count = (
        db.session.query(db.func.count(ArtworkVersion.id))
        .join(Artwork, Artwork.id == ArtworkVersion.artwork_id)
        .filter(Artwork.workspace_id == workspace_id)
        .scalar()
        or 0
    )
    latest_verification = (
        VerificationRecord.query.join(Artwork, Artwork.id == VerificationRecord.artwork_id)
        .filter(Artwork.workspace_id == workspace_id)
        .order_by(VerificationRecord.created_at.desc())
        .first()
    )
    recent_events = (
        AuditLog.query.filter_by(workspace_id=workspace_id)
        .order_by(AuditLog.created_at.desc())
        .limit(7)
        .all()
    )
    storage_trend = []
    for offset in range(13, -1, -1):
        day = start_date + timedelta(days=offset)
        end_of_day = datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc)
        cumulative = (
            db.session.query(db.func.coalesce(db.func.sum(Artwork.file_size), 0))
            .filter(
                Artwork.workspace_id == workspace_id,
                Artwork.archived.is_(False),
                Artwork.created_at < end_of_day,
            )
            .scalar()
            or 0
        )
        storage_trend.append({"date": day.isoformat(), "storage_bytes": cumulative})
    return jsonify(
        total_artworks=len(artworks),
        total_storage_bytes=sum(item.file_size for item in artworks),
        verified=sum(count for result, count in verification_counts if result == "MATCH"),
        mismatches=sum(count for result, count in verification_counts if result == "MISMATCH"),
        total_verifications=sum(count for _, count in verification_counts),
        versions_count=versions_count,
        favorite_count=sum(1 for item in artworks if item.favorite),
        latest_verification=(
            {
                "result": latest_verification.result,
                "created_at": utc_isoformat(latest_verification.created_at),
            }
            if latest_verification
            else None
        ),
        categories=[{"name": category, "count": count} for category, count in categories],
        recent_events=[
            {
                "id": item.id,
                "actor": item.actor.display_name if item.actor else "System",
                "action": item.action,
                "outcome": item.outcome,
                "created_at": utc_isoformat(item.created_at),
            }
            for item in recent_events
        ],
        by_type={
            content_type: sum(1 for item in artworks if item.content_type == content_type)
            for content_type in sorted({item.content_type for item in artworks})
        },
        registration_trend=[
            {
                "date": (start_date + timedelta(days=offset)).isoformat(),
                "registrations": counts_by_date.get(
                    (start_date + timedelta(days=offset)).isoformat(), 0
                ),
            }
            for offset in range(14)
        ],
        storage_trend=storage_trend,
        recent=[serialize_artwork(item) for item in recent],
    )


@api.get("/analytics/inventory.csv")
def export_inventory():
    if not active_user():
        return error("Authentication required.", 401)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "artwork_id",
            "title",
            "description",
            "filename",
            "content_type",
            "file_size_bytes",
            "sha256",
            "category",
            "tags",
            "favorite",
            "version_number",
            "registered_at_utc",
        ]
    )
    artworks = (
        Artwork.query.filter_by(workspace_id=active_workspace_id(), archived=False)
        .order_by(Artwork.created_at.desc())
        .all()
    )
    for artwork in artworks:
        writer.writerow(
            [
                artwork.id,
                artwork.title,
                artwork.description,
                artwork.original_filename,
                artwork.content_type,
                artwork.file_size,
                artwork.sha256,
                artwork.category,
                ", ".join(artwork.tags or []),
                artwork.favorite,
                artwork.version_number,
                utc_isoformat(artwork.created_at),
            ]
        )
    log_event("artwork.inventory_exported")
    db.session.commit()
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="artlock-inventory.csv"'},
    )


@api.get("/audit-logs")
def audit_logs():
    if not active_user():
        return error("Authentication required.", 401)
    events = (
        AuditLog.query.filter_by(workspace_id=active_workspace_id())
        .order_by(AuditLog.created_at.desc())
        .limit(100)
        .all()
    )
    return jsonify(
        events=[
            {
                "id": item.id,
                "actor": item.actor.display_name if item.actor else "System",
                "action": item.action,
                "target_id": item.target_id,
                "outcome": item.outcome,
                "created_at": utc_isoformat(item.created_at),
            }
            for item in events
        ]
    )


@api.errorhandler(StorageError)
def handle_storage_error(exc):
    current_app.logger.exception("Storage operation failed")
    return error(str(exc), 503)
