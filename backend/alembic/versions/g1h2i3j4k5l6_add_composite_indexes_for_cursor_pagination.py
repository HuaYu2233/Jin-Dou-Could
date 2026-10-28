"""add composite indexes for cursor pagination

Revision ID: g1h2i3j4k5l6
Revises: f6a7b8c9d0e1
Create Date: 2026-10-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "g1h2i3j4k5l6"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_files_owner_folder_created",
        "files",
        ["owner_id", "folder_id", "created_at"],
    )
    op.create_index(
        "ix_files_owner_deleted_at",
        "files",
        ["owner_id", "deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_files_owner_deleted_at", table_name="files")
    op.drop_index("ix_files_owner_folder_created", table_name="files")