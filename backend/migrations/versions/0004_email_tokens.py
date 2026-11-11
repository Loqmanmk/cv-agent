"""email tokens

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# Frozen copy: a migration must never change when the application code changes.
PURPOSES = "'verify_email', 'reset_password'"


def upgrade() -> None:
    op.create_table(
        "email_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_email_tokens_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("token_hash", name="uq_email_tokens_token_hash"),
        sa.CheckConstraint(f"purpose IN ({PURPOSES})", name="ck_email_tokens_purpose"),
        sa.CheckConstraint("expires_at > created_at", name="ck_email_tokens_expiry_after_creation"),
    )
    op.create_index("ix_email_tokens_user_id_purpose", "email_tokens", ["user_id", "purpose"])


def downgrade() -> None:
    op.drop_index("ix_email_tokens_user_id_purpose", table_name="email_tokens")
    op.drop_table("email_tokens")
