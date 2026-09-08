"""add jobs.artifacts_pruned_at

Revision ID: 2bd14a8de2a5
Revises: 63138ed9c3fe
Create Date: 2026-09-07 22:39:16.755610
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '2bd14a8de2a5'
down_revision: str | None = '63138ed9c3fe'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('artifacts_pruned_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'artifacts_pruned_at')
