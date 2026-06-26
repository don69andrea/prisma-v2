"""Create model_registry table for champion/challenger tracking (V4-6).

Revision ID: 0046
Revises: 0045
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_registry",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "model_name",
            sa.String(length=128),
            nullable=False,
            comment="e.g. vol_forecast_har",
        ),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column(
            "model_type",
            sa.String(length=32),
            nullable=False,
            comment="har or lgbm",
        ),
        sa.Column("oos_r2", sa.Float(), nullable=False),
        sa.Column(
            "is_champion",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "trained_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_model_registry_name_champion",
        "model_registry",
        ["model_name", "is_champion"],
    )


def downgrade() -> None:
    op.drop_index("ix_model_registry_name_champion", table_name="model_registry")
    op.drop_table("model_registry")
