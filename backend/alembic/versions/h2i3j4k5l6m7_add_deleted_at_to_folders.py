"""add deleted_at to folders

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-10-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "h2i3j4k5l6m7"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "folders",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_folders_owner_deleted_at",
        "folders",
        ["owner_id", "deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_folders_owner_deleted_at", table_name="folders")
    op.drop_column("folders", "deleted_at")