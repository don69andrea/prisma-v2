"""create index_constituents table for PIT universe

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-20

CHALLENGE 04 / Kap. 19 — Survivorship-Bias-Fix.
Speichert das Index-Universum (SMI/SMIM) point-in-time:
Backtests und Feature-Snapshots dürfen nur Titel nutzen,
die zum jeweiligen Datum tatsächlich im Index waren.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "index_constituents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("index_name", sa.String(10), nullable=False),  # 'SMI' | 'SMIM'
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("valid_from", sa.Date, nullable=False),
        sa.Column("valid_to", sa.Date, nullable=True),  # NULL = aktuell im Index
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("index_name", "ticker", "valid_from", name="ux_ic_index_ticker_from"),
    )
    op.create_index("ix_ic_ticker", "index_constituents", ["ticker"])
    op.create_index("ix_ic_index_name", "index_constituents", ["index_name"])


def downgrade() -> None:
    op.drop_index("ix_ic_index_name", "index_constituents")
    op.drop_index("ix_ic_ticker", "index_constituents")
    op.drop_table("index_constituents")
