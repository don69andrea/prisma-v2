"""market_sentiment table — Fear & Greed Index from alternative.me

Revision ID: 0039
Revises: 0038
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_sentiment",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("fear_greed", sa.Integer(), nullable=False),
        sa.Column("fg_classification", sa.String(), nullable=False),
        sa.Column("source", sa.String(), server_default="alternative_me", nullable=False),
        sa.PrimaryKeyConstraint("date"),
    )


def downgrade() -> None:
    op.drop_table("market_sentiment")
