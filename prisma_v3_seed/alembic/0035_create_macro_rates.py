"""create macro_rates table

Revision ID: 0035
Revises: 0034
Create Date: 2026-06-20

V3 · Kap. 2.2 / 5.3 / FIX-06. Eliminiert die Zwei-System-Inkonsistenz:
MLFeatureService liest künftig SNB/ECB/Fed-Zinsen aus dieser Tabelle statt
aus den hartcodierten Listen (_SNB_RATE_HISTORY etc.). Hardcoded bleibt nur
Notfall-Fallback bei leerer Tabelle.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "macro_rates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rate_type", sa.String(20), nullable=False),  # snb_policy|ecb_deposit|fed_funds
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("rate_pct", sa.Float, nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ux_macro_rates_type_date",
        "macro_rates",
        ["rate_type", "effective_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_macro_rates_type_date", "macro_rates")
    op.drop_table("macro_rates")
