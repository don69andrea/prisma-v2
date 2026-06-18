"""users: add first_name and last_name columns

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(100), nullable=False, server_default=""))
    op.add_column("users", sa.Column("last_name", sa.String(100), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
