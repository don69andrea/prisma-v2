# backend/alembic/versions/0019_create_investor_profiles.py
"""create investor_profiles table

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investor_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(255), nullable=False),
        sa.Column("profession", sa.String(255), nullable=True),
        sa.Column("financial_knowledge", sa.String(10), nullable=False, server_default="low"),
        sa.Column("investment_goal", sa.String(20), nullable=False, server_default="beat_savings"),
        sa.Column("time_horizon", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("risk_profile", sa.String(20), nullable=False, server_default="moderate"),
        sa.Column(
            "sector_affinity",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "known_tickers",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("onboarding_complete", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_investor_profiles_session_id",
        "investor_profiles",
        ["session_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_investor_profiles_session_id", table_name="investor_profiles")
    op.drop_table("investor_profiles")
