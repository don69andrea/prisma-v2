"""create signal_outcomes table

Revision ID: 0034
Revises: 0033
Create Date: 2026-06-20

V3 · Kap. 2.2 / 5.1 / 17. Continuous-Learning-Backbone. Enthält bewusst
die NETTO-Spalten (cost_adjusted_return, net_excess_return) aus CHALLENGE 03 —
Win-Rate/Alpha werden auf Netto-Basis berechnet, nicht brutto.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("asset_type", sa.String(10), nullable=False),  # stock|crypto
        sa.Column("signal_date", sa.Date, nullable=False),
        sa.Column("signal", sa.String(20), nullable=False),
        sa.Column("price_at_signal", sa.Float, nullable=False),
        sa.Column("horizon_days", sa.Integer, nullable=False),
        sa.Column("evaluation_date", sa.Date, nullable=True),
        sa.Column("price_at_eval", sa.Float, nullable=True),
        sa.Column("actual_return", sa.Float, nullable=True),
        sa.Column("benchmark_ret", sa.Float, nullable=True),
        sa.Column("excess_return", sa.Float, nullable=True),  # brutto-alpha
        sa.Column("cost_adjusted_return", sa.Float, nullable=True),  # CHALLENGE 03
        sa.Column("net_excess_return", sa.Float, nullable=True),  # CHALLENGE 03
        sa.Column("was_correct", sa.Boolean, nullable=True),
        sa.Column("used_for_train", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("source_table", sa.String(30), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_signal_outcomes_ticker_date",
        "signal_outcomes",
        ["ticker", "signal_date"],
    )
    op.create_index(
        "ix_signal_outcomes_eval",
        "signal_outcomes",
        ["evaluation_date", "used_for_train"],
    )
    # Verhindert Doppel-Outcomes für dieselbe Signal/Horizont-Kombination.
    op.create_index(
        "ux_signal_outcomes_unique",
        "signal_outcomes",
        ["ticker", "signal_date", "horizon_days"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_signal_outcomes_unique", "signal_outcomes")
    op.drop_index("ix_signal_outcomes_eval", "signal_outcomes")
    op.drop_index("ix_signal_outcomes_ticker_date", "signal_outcomes")
    op.drop_table("signal_outcomes")
