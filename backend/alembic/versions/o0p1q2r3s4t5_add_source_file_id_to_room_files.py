"""add source_file_id to transfer_room_files

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-11-15 12:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "o0p1q2r3s4t5"
down_revision = "n9o0p1q2r3s4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transfer_room_files",
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_transfer_room_files_source_file_id",
        "transfer_room_files",
        "files",
        ["source_file_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_transfer_room_files_source_file_id",
        "transfer_room_files",
        ["source_file_id"],
        unique=False,
    )
    op.create_index(
        "ux_transfer_room_files_room_source",
        "transfer_room_files",
        ["room_id", "source_file_id"],
        unique=True,
        postgresql_where=sa.text("source_file_id IS NOT NULL"),
    )
    op.drop_index("ix_transfer_room_files_storage_key", table_name="transfer_room_files")
    op.create_index(
        "ix_transfer_room_files_storage_key",
        "transfer_room_files",
        ["storage_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transfer_room_files_storage_key", table_name="transfer_room_files")
    op.create_index(
        "ix_transfer_room_files_storage_key",
        "transfer_room_files",
        ["storage_key"],
        unique=True,
    )
    op.drop_index("ux_transfer_room_files_room_source", table_name="transfer_room_files")
    op.drop_index("ix_transfer_room_files_source_file_id", table_name="transfer_room_files")
    op.drop_constraint("fk_transfer_room_files_source_file_id", "transfer_room_files", type_="foreignkey")
    op.drop_column("transfer_room_files", "source_file_id")
