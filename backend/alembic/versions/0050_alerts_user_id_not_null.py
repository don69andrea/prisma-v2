"""Enforce alerts.user_id NOT NULL (Mandanten-Isolation / IDOR-Fix C-05).

Migration 0029 fügte ``alerts.user_id`` als *nullable* FK hinzu. Nach dem
IDOR-Fix setzt jede Alert-Erstellung einen Owner, daher wird die Spalte hier auf
NOT NULL gezogen. Bereits vorhandene *besitzerlose* Alerts (``user_id IS NULL``)
stammen aus der Zeit vor der Autorisierung, können keinem Mandanten zugeordnet
werden und werden — eng begrenzt auf genau diese Zeilen — entfernt.

Revision ID: 0050
Revises: 0049
Create Date: 2026-07-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Besitzerlose Alerts entfernen — nur exakt user_id IS NULL, kein Blanket-Delete.
    op.execute("DELETE FROM alerts WHERE user_id IS NULL")
    op.alter_column("alerts", "user_id", nullable=False)


def downgrade() -> None:
    op.alter_column("alerts", "user_id", nullable=True)
