"""add thumbnail_key to files

Revision ID: l7m8n9o0p1q2
Revises: k5l6m7n8o9p0
Create Date: 2026-10-28 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "l7m8n9o0p1q2"
down_revision = "k5l6m7n8o9p0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    cols = {col["name"] for col in inspect(conn).get_columns("files")}
    if "thumbnail_key" not in cols:
        op.add_column("files", sa.Column("thumbnail_key", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("files", "thumbnail_key")