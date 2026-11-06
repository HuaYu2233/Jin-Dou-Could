"""widen shares.extract_code to 8

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-11-06 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "m8n9o0p1q2r3"
down_revision = "l7m8n9o0p1q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    conn = op.get_bind()
    cols = {col["name"]: col for col in inspect(conn).get_columns("shares")}
    current = cols.get("extract_code")
    if current is not None and current["type"].length != 8:
        op.alter_column(
            "shares",
            "extract_code",
            existing_type=sa.String(length=6),
            type_=sa.String(length=8),
            existing_nullable=False,
        )


def downgrade() -> None:
    op.alter_column(
        "shares",
        "extract_code",
        existing_type=sa.String(length=8),
        type_=sa.String(length=6),
        existing_nullable=False,
    )
