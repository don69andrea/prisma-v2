"""create index_constituents table

Revision ID: 0036
Revises: 0035
Create Date: 2026-06-20

V3 · Kap. 19 / CH-04. Behebt Survivorship-Bias (FIX-18): Feature- und
Backtest-Snapshots werden nur für Titel gebildet, die zum Snapshot-Datum
im Index waren. Idempotent — mehrfach ausführbar.

Beispiel: CSGN (Credit Suisse) delisted 2023-06-12. Snapshots vor dem
Delisting nutzen CSGN; danach nicht mehr. Didaktischer Vorzeige-Case.
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
    )
    op.create_index(
        "ux_index_constituents_pit",
        "index_constituents",
        ["index_name", "ticker", "valid_from"],
        unique=True,
    )
    op.create_index(
        "ix_index_constituents_ticker",
        "index_constituents",
        ["ticker", "valid_from", "valid_to"],
    )


def downgrade() -> None:
    op.drop_index("ix_index_constituents_ticker", "index_constituents")
    op.drop_index("ux_index_constituents_pit", "index_constituents")
    op.drop_table("index_constituents")
