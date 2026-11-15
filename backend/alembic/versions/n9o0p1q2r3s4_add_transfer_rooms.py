"""add transfer rooms and room files

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-11-12 12:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "n9o0p1q2r3s4"
down_revision = "m8n9o0p1q2r3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transfer_rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("max_file_size", sa.BigInteger(), nullable=False),
        sa.Column("max_total_size", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_transfer_rooms_code", "transfer_rooms", ["code"], unique=True)
    op.create_index("ix_transfer_rooms_owner_id", "transfer_rooms", ["owner_id"], unique=False)
    op.create_index("ix_transfer_rooms_expires_at", "transfer_rooms", ["expires_at"], unique=False)
    op.create_index("ix_transfer_rooms_owner_created", "transfer_rooms", ["owner_id", "created_at"], unique=False)

    op.create_table(
        "transfer_room_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploader_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["transfer_rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_transfer_room_files_room_id", "transfer_room_files", ["room_id"], unique=False)
    op.create_index("ix_transfer_room_files_storage_key", "transfer_room_files", ["storage_key"], unique=True)
    op.create_index(
        "ix_transfer_room_files_room_created", "transfer_room_files", ["room_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_transfer_room_files_room_created", table_name="transfer_room_files")
    op.drop_index("ix_transfer_room_files_storage_key", table_name="transfer_room_files")
    op.drop_index("ix_transfer_room_files_room_id", table_name="transfer_room_files")
    op.drop_table("transfer_room_files")
    op.drop_index("ix_transfer_rooms_owner_created", table_name="transfer_rooms")
    op.drop_index("ix_transfer_rooms_expires_at", table_name="transfer_rooms")
    op.drop_index("ix_transfer_rooms_owner_id", table_name="transfer_rooms")
    op.drop_index("ix_transfer_rooms_code", table_name="transfer_rooms")
    op.drop_table("transfer_rooms")
