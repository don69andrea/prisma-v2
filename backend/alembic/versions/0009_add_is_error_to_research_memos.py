"""add is_error column to research_memos

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-14

Issue #67: Router-Logik erbte is_error per String-Match aus one_liner. Mit
echtem is_error-Feld auf der Entity (PR-Bundle #66+#67) braucht es die
DB-Spalte. Backfill setzt historische Error-Memos (model_version =
'error-fallback') auf is_error=True.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_memos",
        sa.Column(
            "is_error",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Backfill: bisherige Error-Memos anhand des Sentinels markieren
    op.execute("UPDATE research_memos SET is_error = true WHERE model_version = 'error-fallback'")


def downgrade() -> None:
    op.drop_column("research_memos", "is_error")
