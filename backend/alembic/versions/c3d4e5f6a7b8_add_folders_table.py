# /Users/zero/project/JinDou-Cloud/backend/alembic/versions/c3d4e5f6a7b8_add_folders_table.py
"""add folders table and file.folder_id

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-03 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'folders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['id'], ['folders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['folders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_folders_owner_id', 'folders', ['owner_id'])
    op.create_index('ix_folders_parent_id', 'folders', ['parent_id'])

    op.add_column('files', sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_files_folder_id', 'files', ['folder_id'])
    op.create_foreign_key(
        'fk_files_folder_id', 'files', 'folders',
        ['folder_id'], ['id'], ondelete='CASCADE',
    )

def downgrade() -> None:
    op.drop_constraint('fk_files_folder_id', 'files', type_='foreignkey')
    op.drop_index('ix_files_folder_id', table_name='files')
    op.drop_column('files', 'folder_id')

    op.drop_index('ix_folders_parent_id', table_name='folders')
    op.drop_index('ix_folders_owner_id', table_name='folders')
    op.drop_table('folders')