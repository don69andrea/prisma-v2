"""merge main (0036) and develop (0048) migration heads

Revision ID: 0049
Revises: 0036, 0048
Create Date: 2026-06-26
"""

from collections.abc import Sequence

revision: str = "0049"
down_revision: tuple[str, str] = ("0036", "0048")
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
