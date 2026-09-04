
# /Users/zero/project/JinDou-Cloud/backend/alembic/versions/b2c3d4e5f6a7_add_shares_table.py
"""add shares table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-03 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('shares',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('file_id', sa.UUID(), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('share_token', sa.String(length=32), nullable=False),
        sa.Column('extract_code', sa.String(length=6), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('views', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('share_token')
    )
    op.create_index(op.f('ix_shares_file_id'), 'shares', ['file_id'], unique=False)
    op.create_index(op.f('ix_shares_owner_id'), 'shares', ['owner_id'], unique=False)
    op.create_index(op.f('ix_shares_share_token'), 'shares', ['share_token'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_shares_share_token'), table_name='shares')
    op.drop_index(op.f('ix_shares_owner_id'), table_name='shares')
    op.drop_index(op.f('ix_shares_file_id'), table_name='shares')
    op.drop_table('shares')
