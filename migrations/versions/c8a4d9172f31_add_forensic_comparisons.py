"""Add persistent artwork forensic comparisons.

Revision ID: c8a4d9172f31
Revises: b93c156935c6
Create Date: 2026-11-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "c8a4d9172f31"
down_revision = "b93c156935c6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "forensic_comparison",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("artwork_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("artwork_title", sa.String(length=200), nullable=False),
        sa.Column("artwork_filename", sa.String(length=255), nullable=False),
        sa.Column("artwork_content_type", sa.String(length=100), nullable=False),
        sa.Column("artwork_sha256", sa.String(length=64), nullable=False),
        sa.Column("artwork_ciphertext_sha256", sa.String(length=64), nullable=False),
        sa.Column("artwork_storage_key", sa.String(length=500), nullable=False),
        sa.Column("artwork_nonce", sa.String(length=64), nullable=False),
        sa.Column("candidate_filename", sa.String(length=255), nullable=False),
        sa.Column("candidate_content_type", sa.String(length=100), nullable=False),
        sa.Column("candidate_file_size", sa.Integer(), nullable=False),
        sa.Column("candidate_sha256", sa.String(length=64), nullable=False),
        sa.Column("candidate_ciphertext_sha256", sa.String(length=64), nullable=False),
        sa.Column("candidate_storage_key", sa.String(length=500), nullable=False),
        sa.Column("candidate_nonce", sa.String(length=64), nullable=False),
        sa.Column("artwork_width", sa.Integer(), nullable=True),
        sa.Column("artwork_height", sa.Integer(), nullable=True),
        sa.Column("candidate_width", sa.Integer(), nullable=True),
        sa.Column("candidate_height", sa.Integer(), nullable=True),
        sa.Column("artwork_dhash", sa.String(length=16), nullable=True),
        sa.Column("candidate_dhash", sa.String(length=16), nullable=True),
        sa.Column("exact_match", sa.Boolean(), nullable=False),
        sa.Column("similarity_percent", sa.Integer(), nullable=True),
        sa.Column("similarity_method", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artwork_id"], ["artwork.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_storage_key"),
    )
    with op.batch_alter_table("forensic_comparison", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_forensic_comparison_artwork_id"),
            ["artwork_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_forensic_comparison_created_at"),
            ["created_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_forensic_comparison_workspace_id"),
            ["workspace_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("forensic_comparison", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_forensic_comparison_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_forensic_comparison_created_at"))
        batch_op.drop_index(batch_op.f("ix_forensic_comparison_artwork_id"))
    op.drop_table("forensic_comparison")
