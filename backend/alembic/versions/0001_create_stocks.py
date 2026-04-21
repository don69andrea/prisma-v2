"""Erstellt die stocks-Tabelle (initiale Migration).

Revision ID: 0001
Revises:
Create Date: 2026-04-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
    )
    # Unique-Index garantiert Eindeutigkeit des Ticker-Symbols auf DB-Ebene.
    op.create_index(
        "ix_stocks_ticker",
        "stocks",
        ["ticker"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_stocks_ticker", table_name="stocks")
    op.drop_table("stocks")
