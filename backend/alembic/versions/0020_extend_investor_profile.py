# backend/alembic/versions/0020_extend_investor_profile.py
"""extend investor_profiles with sector_hint and new preference dimensions

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "investor_profiles",
        sa.Column("sector_hint", sa.String(30), nullable=True),
    )
    op.add_column(
        "investor_profiles",
        sa.Column(
            "investment_amount",
            sa.String(20),
            nullable=False,
            server_default="10k_100k",
        ),
    )
    op.add_column(
        "investor_profiles",
        sa.Column(
            "esg_preference",
            sa.String(15),
            nullable=False,
            server_default="indifferent",
        ),
    )
    op.add_column(
        "investor_profiles",
        sa.Column(
            "income_preference",
            sa.String(15),
            nullable=False,
            server_default="balanced",
        ),
    )


def downgrade() -> None:
    op.drop_column("investor_profiles", "income_preference")
    op.drop_column("investor_profiles", "esg_preference")
    op.drop_column("investor_profiles", "investment_amount")
    op.drop_column("investor_profiles", "sector_hint")
