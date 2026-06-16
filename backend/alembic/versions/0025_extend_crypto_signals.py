"""0025 — extend crypto_signals with pattern + agent columns.

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crypto_signals", sa.Column("components", JSONB, nullable=True))
    op.add_column("crypto_signals", sa.Column("price_change_24h", sa.Float, nullable=True))
    op.add_column("crypto_signals", sa.Column("macd_signal", sa.String(10), nullable=True))
    op.add_column("crypto_signals", sa.Column("detected_patterns", JSONB, nullable=True))
    op.add_column("crypto_signals", sa.Column("pattern_score", sa.Float, nullable=True))
    op.add_column("crypto_signals", sa.Column("agent_analysis", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("crypto_signals", "agent_analysis")
    op.drop_column("crypto_signals", "pattern_score")
    op.drop_column("crypto_signals", "detected_patterns")
    op.drop_column("crypto_signals", "macd_signal")
    op.drop_column("crypto_signals", "price_change_24h")
    op.drop_column("crypto_signals", "components")
