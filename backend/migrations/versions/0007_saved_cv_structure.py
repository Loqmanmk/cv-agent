"""keep the structured saved cv

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("saved_cvs", sa.Column("structured_cv", postgresql.JSONB(), nullable=True))
    op.add_column("saved_cvs", sa.Column("structure_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("saved_cvs", "structure_version")
    op.drop_column("saved_cvs", "structured_cv")
