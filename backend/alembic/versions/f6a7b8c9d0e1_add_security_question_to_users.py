"""add security_question and security_answer to users

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-07 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("security_question", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("security_answer", sa.String(length=255), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "security_answer")
    op.drop_column("users", "security_question")
