"""an application can be saved without a cover letter

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("applications", "letter_json", existing_type=postgresql.JSONB(), nullable=True)
    op.alter_column("applications", "letter_pdf", existing_type=sa.LargeBinary(), nullable=True)


def downgrade() -> None:
    # Only possible while every saved application still has its letter.
    op.alter_column("applications", "letter_pdf", existing_type=sa.LargeBinary(), nullable=False)
    op.alter_column("applications", "letter_json", existing_type=postgresql.JSONB(), nullable=False)
