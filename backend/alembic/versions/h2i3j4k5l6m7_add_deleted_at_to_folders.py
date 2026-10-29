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
    from sqlalchemy import inspect
    conn = op.get_bind()
    cols = {col["name"] for col in inspect(conn).get_columns("folders")}
    if "deleted_at" not in cols:
        op.add_column(
            "folders",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
    folder_idxs = {idx["name"] for idx in inspect(conn).get_indexes("folders")}
    if "ix_folders_owner_deleted_at" not in folder_idxs:
        op.create_index(
            "ix_folders_owner_deleted_at",
            "folders",
            ["owner_id", "deleted_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_folders_owner_deleted_at", table_name="folders")
    op.drop_column("folders", "deleted_at")