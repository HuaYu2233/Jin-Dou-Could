"""add composite indexes for file type filter and share pagination

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-10-23 11:00:00.000000

"""
from alembic import op

revision = "i3j4k5l6m7n8"
down_revision = "h2i3j4k5l6m7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    file_idxs = {idx["name"] for idx in inspect(conn).get_indexes("files")}
    share_idxs = {idx["name"] for idx in inspect(conn).get_indexes("shares")}

    if "ix_files_owner_type_created" not in file_idxs:
        op.create_index(
            "ix_files_owner_type_created",
            "files",
            ["owner_id", "file_type", "created_at"],
        )
    if "ix_shares_owner_created" not in share_idxs:
        op.create_index(
            "ix_shares_owner_created",
            "shares",
            ["owner_id", "created_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_shares_owner_created", table_name="shares")
    op.drop_index("ix_files_owner_type_created", table_name="files")