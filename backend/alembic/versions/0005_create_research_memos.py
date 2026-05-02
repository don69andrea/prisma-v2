"""create research_memos

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_memos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "stock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ranking_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(2), nullable=False, server_default="de"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("one_liner", sa.String(150), nullable=False),
        sa.Column("ranking_interpretation", sa.String(600), nullable=False),
        sa.Column("sweet_spot", sa.Boolean, nullable=False),
        sa.Column("sweet_spot_explanation", sa.String(300), nullable=True),
        sa.Column(
            "contradictions",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("key_strengths", postgresql.JSONB, nullable=False),
        sa.Column("key_risks", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "stock_id",
            "model_run_id",
            "language",
            name="uq_research_memos_stock_run_lang",
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="confidence",
        ),
    )
    op.create_index(
        "ix_research_memos_model_run_id",
        "research_memos",
        ["model_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_memos_model_run_id", table_name="research_memos")
    op.drop_table("research_memos")
