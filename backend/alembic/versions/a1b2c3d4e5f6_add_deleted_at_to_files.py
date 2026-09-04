# /Users/zero/project/JinDou-Cloud/backend/alembic/versions/a1b2c3d4e5f6_add_deleted_at_to_files.py
"""add deleted_at to files

Revision ID: a1b2c3d4e5f6
Revises: 2ebb801da8c6
Create Date: 2026-09-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2ebb801da8c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('files', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    op.drop_column('files', 'deleted_at')