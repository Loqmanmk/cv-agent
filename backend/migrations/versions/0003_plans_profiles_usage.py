"""plans, profiles and usage

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Frozen copies: a migration must never change when the application code changes.
PLANS = "'free', 'plus', 'pro', 'premium'"
GENDERS = "'m', 'f'"
CV_LANGUAGES = "'fr', 'de', 'en', 'ar'"
USAGE_KINDS = "'application'"


def upgrade() -> None:
    op.add_column("users", sa.Column("plan", sa.Text(), server_default="free", nullable=False))
    op.create_check_constraint("ck_users_plan", "users", f"plan IN ({PLANS})")
    op.create_table(
        "profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("address", sa.Text(), server_default="", nullable=False),
        sa.Column("city", sa.Text(), server_default="", nullable=False),
        sa.Column("gender", sa.Text(), server_default="m", nullable=False),
        sa.Column("cv_language", sa.Text(), server_default="fr", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_profiles_user_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint(f"gender IN ({GENDERS})", name="ck_profiles_gender"),
        sa.CheckConstraint(f"cv_language IN ({CV_LANGUAGES})", name="ck_profiles_cv_language"),
    )
    op.create_table(
        "usage_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_usage_events_user_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint(f"kind IN ({USAGE_KINDS})", name="ck_usage_events_kind"),
    )
    op.create_index(
        "ix_usage_events_user_id_kind_created_at",
        "usage_events",
        ["user_id", "kind", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_events_user_id_kind_created_at", table_name="usage_events")
    op.drop_table("usage_events")
    op.drop_table("profiles")
    op.drop_constraint("ck_users_plan", "users", type_="check")
    op.drop_column("users", "plan")
