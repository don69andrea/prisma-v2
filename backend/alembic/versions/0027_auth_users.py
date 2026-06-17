"""auth: add users table and user_id FK to personal-data tables

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

_PERSONAL_TABLES = [
    "alerts",
    "backtest_results",
    "decision_audit_log",
    "research_memos",
    "ranking_runs",
    "llm_call_log",
    "memo_batch_jobs",
    "investor_profiles",
]


def upgrade() -> None:
    # Fresh start: wipe all user-owned data before adding NOT NULL constraint
    for table in _PERSONAL_TABLES:
        op.execute(f"TRUNCATE TABLE {table} CASCADE")

    # Create users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(10), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Add user_id FK to each personal table
    for table in _PERSONAL_TABLES:
        op.add_column(
            table,
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_foreign_key(
            f"fk_{table}_user_id",
            table,
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def downgrade() -> None:
    for table in _PERSONAL_TABLES:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_constraint(f"fk_{table}_user_id", table, type_="foreignkey")
        op.drop_column(table, "user_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
