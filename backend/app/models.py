from datetime import datetime, timezone

from app import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    memberships = db.relationship("WorkspaceMembership", back_populates="user")


class Workspace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class WorkspaceMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="owner")
    __table_args__ = (
        db.UniqueConstraint("user_id", "workspace_id", name="uq_membership_user_workspace"),
    )
    user = db.relationship("User", back_populates="memberships")
    workspace = db.relationship("Workspace")


class Artwork(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    original_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False, index=True)
    ciphertext_sha256 = db.Column(db.String(64), nullable=False)
    storage_key = db.Column(db.String(500), nullable=False, unique=True)
    nonce = db.Column(db.String(64), nullable=False)
    version_number = db.Column(db.Integer, nullable=False, default=1)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    favorite = db.Column(db.Boolean, nullable=False, default=False)
    category = db.Column(db.String(80), nullable=False, default="Uncategorized")
    tags = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    owner = db.relationship("User")
    versions = db.relationship(
        "ArtworkVersion",
        back_populates="artwork",
        cascade="all, delete-orphan",
        order_by="ArtworkVersion.version_number.desc()",
    )


class ArtworkVersion(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    artwork_id = db.Column(db.String(36), db.ForeignKey("artwork.id"), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    ciphertext_sha256 = db.Column(db.String(64), nullable=False)
    storage_key = db.Column(db.String(500), nullable=False, unique=True)
    nonce = db.Column(db.String(64), nullable=False)
    notes = db.Column(db.String(500), nullable=False, default="")
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    artwork = db.relationship("Artwork", back_populates="versions")
    uploader = db.relationship("User")
    __table_args__ = (
        db.UniqueConstraint("artwork_id", "version_number", name="uq_artwork_version"),
    )


class VerificationRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    artwork_id = db.Column(db.String(36), db.ForeignKey("artwork.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    expected_sha256 = db.Column(db.String(64), nullable=False)
    calculated_sha256 = db.Column(db.String(64), nullable=False)
    result = db.Column(db.String(12), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class ForensicComparison(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    artwork_id = db.Column(db.String(36), db.ForeignKey("artwork.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    artwork_title = db.Column(db.String(200), nullable=False)
    artwork_filename = db.Column(db.String(255), nullable=False)
    artwork_content_type = db.Column(db.String(100), nullable=False)
    artwork_sha256 = db.Column(db.String(64), nullable=False)
    artwork_ciphertext_sha256 = db.Column(db.String(64), nullable=False)
    artwork_storage_key = db.Column(db.String(500), nullable=False)
    artwork_nonce = db.Column(db.String(64), nullable=False)
    candidate_filename = db.Column(db.String(255), nullable=False)
    candidate_content_type = db.Column(db.String(100), nullable=False)
    candidate_file_size = db.Column(db.Integer, nullable=False)
    candidate_sha256 = db.Column(db.String(64), nullable=False)
    candidate_ciphertext_sha256 = db.Column(db.String(64), nullable=False)
    candidate_storage_key = db.Column(db.String(500), nullable=False, unique=True)
    candidate_nonce = db.Column(db.String(64), nullable=False)
    artwork_width = db.Column(db.Integer, nullable=True)
    artwork_height = db.Column(db.Integer, nullable=True)
    candidate_width = db.Column(db.Integer, nullable=True)
    candidate_height = db.Column(db.Integer, nullable=True)
    artwork_dhash = db.Column(db.String(16), nullable=True)
    candidate_dhash = db.Column(db.String(16), nullable=True)
    exact_match = db.Column(db.Boolean, nullable=False)
    similarity_percent = db.Column(db.Integer, nullable=True)
    similarity_method = db.Column(db.String(40), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    target_id = db.Column(db.String(100), nullable=True)
    outcome = db.Column(db.String(20), nullable=False, default="success")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    actor = db.relationship("User")
