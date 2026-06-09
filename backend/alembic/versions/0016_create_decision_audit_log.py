"""create decision_audit_log table

Revision ID: 0016
Revises: 0013
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0016"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("signal", sa.String(10), nullable=False),
        sa.Column("weighted_score", sa.Float, nullable=False),
        sa.Column("quant_score", sa.Float, nullable=False),
        sa.Column("ml_score", sa.Float, nullable=False),
        sa.Column("macro_score", sa.Float, nullable=False),
        sa.Column("is_3a_eligible", sa.Boolean, nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("explanation_de", sa.Text, nullable=False),
    )
    op.create_index("ix_decision_audit_log_ticker", "decision_audit_log", ["ticker"])
    op.create_index("ix_decision_audit_log_computed_at", "decision_audit_log", ["computed_at"])


def downgrade() -> None:
    op.drop_index("ix_decision_audit_log_computed_at", table_name="decision_audit_log")
    op.drop_index("ix_decision_audit_log_ticker", table_name="decision_audit_log")
    op.drop_table("decision_audit_log")
