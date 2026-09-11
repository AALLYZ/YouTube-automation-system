"""add topics.source, topics.source_ref

Revision ID: 9a1c4f2e7b3d
Revises: 2bd14a8de2a5
Create Date: 2026-09-11 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '9a1c4f2e7b3d'
down_revision: str | None = '2bd14a8de2a5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('topics', sa.Column('source', sa.String(length=30), nullable=False, server_default='ai'))
    op.add_column('topics', sa.Column('source_ref', postgresql.JSONB(), nullable=True))
    op.alter_column('topics', 'source', server_default=None)


def downgrade() -> None:
    op.drop_column('topics', 'source_ref')
    op.drop_column('topics', 'source')
