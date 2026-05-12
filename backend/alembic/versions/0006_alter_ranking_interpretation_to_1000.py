"""alter research_memos.ranking_interpretation VARCHAR(600) -> VARCHAR(1000)

Schema-Constraint wurde in commit cabef60 von 600 auf 1000 hochgezogen, weil
Real-API-Smoke gegen Sonnet 4.6 fuer 5-Modell-Interpretationen 700-1000 Zeichen
liefert. Entity und ORM/DB-Column waren noch auf 600 — Drift fuehrt zu
ValidationError beim ResearchMemo(...)-Aufruf im Service (Schema valides
LLM-Output, aber Entity zu eng).

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "research_memos",
        "ranking_interpretation",
        existing_type=sa.String(600),
        type_=sa.String(1000),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Schlaegt fehl, falls bestehende Rows ranking_interpretation > 600 Zeichen
    # haben. Das ist beabsichtigt — Downgrade in Production muss erst Daten
    # truncaten/migrieren. Lokale Dev-DB ist meistens leer, daher OK.
    op.alter_column(
        "research_memos",
        "ranking_interpretation",
        existing_type=sa.String(1000),
        type_=sa.String(600),
        existing_nullable=False,
    )
