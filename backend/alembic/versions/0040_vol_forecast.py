# backend/alembic/versions/0040_vol_forecast.py
"""Create vol_forecast table for Layer 3 HAR/LightGBM vol predictions.

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-21

Note: Depends on 0039 (crypto_universe table with coin_id PK).
If 0039 does not yet exist in the target DB, apply 0037-0039 first.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vol_forecast",
        sa.Column("coin_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "horizon",
            sa.Integer(),
            nullable=False,
            comment="Forecast horizon in days (e.g. 1 or 5)",
        ),
        sa.Column(
            "pred_vol",
            sa.Float(),
            nullable=False,
            comment="Predicted daily vol (annualized, HAR or LightGBM)",
        ),
        sa.Column(
            "realized_vol",
            sa.Float(),
            nullable=True,
            comment="Realized vol ex-post (for back-fill)",
        ),
        sa.Column("model_version", sa.String(length=64), nullable=False, server_default="har-v1"),
        sa.ForeignKeyConstraint(
            ["coin_id"],
            ["crypto_universe.coin_id"],
            name="fk_vol_forecast_coin_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("coin_id", "date", "horizon", name="pk_vol_forecast"),
    )
    op.create_index(
        "ix_vol_forecast_date",
        "vol_forecast",
        ["date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vol_forecast_date", table_name="vol_forecast")
    op.drop_table("vol_forecast")
