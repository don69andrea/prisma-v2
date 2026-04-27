"""Erstellt universes- und ranking_runs-Tabellen.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "universes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("region", sa.String(10), nullable=False),
        sa.Column("tickers", postgresql.ARRAY(sa.String(20)), nullable=False),
    )
    op.create_index("ix_universes_name", "universes", ["name"], unique=True)

    op.create_table(
        "ranking_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "universe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("universes.id"),
            nullable=False,
        ),
        sa.Column("weight_config", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.create_index("ix_ranking_runs_universe_id", "ranking_runs", ["universe_id"])


def downgrade() -> None:
    op.drop_index("ix_ranking_runs_universe_id", table_name="ranking_runs")
    op.drop_table("ranking_runs")
    op.drop_index("ix_universes_name", table_name="universes")
    op.drop_table("universes")
