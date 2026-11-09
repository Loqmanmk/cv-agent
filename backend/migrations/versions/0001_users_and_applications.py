"""users and applications

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Frozen copy: a migration must never change when the application code changes.
STATUSES = "'saved', 'applied', 'interview', 'offer', 'rejected', 'withdrawn'"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("job_title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("cv_json", postgresql.JSONB(), nullable=False),
        sa.Column("letter_json", postgresql.JSONB(), nullable=False),
        sa.Column("photo", sa.LargeBinary(), nullable=True),
        sa.Column("cv_pdf", sa.LargeBinary(), nullable=False),
        sa.Column("letter_pdf", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_applications_user_id_users",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_applications_status"),
    )
    op.create_index("ix_applications_user_id_id", "applications", ["user_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_applications_user_id_id", table_name="applications")
    op.drop_table("applications")
    op.drop_table("users")
