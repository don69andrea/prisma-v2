"""Create ml_features table (Feature Store für ML-Layer).

Revision ID: 0015
Revises: 0013
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ml_features",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("quant_score", sa.Float(), nullable=False),
        sa.Column("score_rendite", sa.Float(), nullable=False),
        sa.Column("score_sicherheit", sa.Float(), nullable=False),
        sa.Column("score_wachstum", sa.Float(), nullable=False),
        sa.Column("score_substanz", sa.Float(), nullable=False),
        sa.Column("return_12m", sa.Float(), nullable=False),
        sa.Column("vol_30d", sa.Float(), nullable=False),
        sa.Column("rsi_14", sa.Float(), nullable=False),
        sa.Column("snb_rate", sa.Float(), nullable=False),
        sa.Column("chf_eur", sa.Float(), nullable=False),
        sa.Column("forward_return_12m", sa.Float(), nullable=True),
        sa.Column("target_class", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("ticker", "snapshot_date", name="uq_ml_features_ticker_date"),
    )
    op.create_index("ix_ml_features_ticker", "ml_features", ["ticker"])
    op.create_index("ix_ml_features_snapshot_date", "ml_features", ["snapshot_date"])


def downgrade() -> None:
    op.drop_index("ix_ml_features_snapshot_date", table_name="ml_features")
    op.drop_index("ix_ml_features_ticker", table_name="ml_features")
    op.drop_table("ml_features")
