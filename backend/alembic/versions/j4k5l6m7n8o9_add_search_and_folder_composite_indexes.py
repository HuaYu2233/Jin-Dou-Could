"""add search and folder composite indexes

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-10-28 12:00:00.000000

"""
from alembic import op

revision = "j4k5l6m7n8o9"
down_revision = "i3j4k5l6m7n8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_files_owner_deleted_filename",
        "files",
        ["owner_id", "deleted_at", "filename"],
    )
    op.create_index(
        "ix_folders_owner_parent_name",
        "folders",
        ["owner_id", "parent_id", "name"],
    )
    op.create_index(
        "ix_folders_parent_id",
        "folders",
        ["parent_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_folders_parent_id", table_name="folders")
    op.drop_index("ix_folders_owner_parent_name", table_name="folders")
    op.drop_index("ix_files_owner_deleted_filename", table_name="files")