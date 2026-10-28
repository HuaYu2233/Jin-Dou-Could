"""add pgtrgm extension and gin index for filename

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-10-28 13:00:00.000000

"""
from alembic import op

revision = "k5l6m7n8o9p0"
down_revision = "j4k5l6m7n8o9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_files_filename_trgm '
        'ON files USING gin (filename gin_trgm_ops)'
    )


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_files_filename_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")