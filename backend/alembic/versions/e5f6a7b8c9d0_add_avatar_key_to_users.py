"""add avatar_key to users

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-06 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    cols = {col["name"] for col in inspect(conn).get_columns("users")}
    if "avatar_key" not in cols:
        op.add_column("users", sa.Column("avatar_key", sa.String(length=255), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "avatar_key")