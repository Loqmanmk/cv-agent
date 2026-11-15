"""saved cvs

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# Frozen copy: a migration must never change when the application code changes.
MAX_CV_BYTES = 5_000_000


def upgrade() -> None:
    op.create_table(
        "saved_cvs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_saved_cvs_user_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            f"octet_length(content) BETWEEN 1 AND {MAX_CV_BYTES}", name="ck_saved_cvs_content_size"
        ),
    )


def downgrade() -> None:
    op.drop_table("saved_cvs")
