"""create cron_run_log table

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cron_run_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),  # "ok" | "error" | "running"
        sa.Column("records_saved", sa.Integer, nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
    )
    op.create_index("ix_cron_run_log_job_started", "cron_run_log", ["job_name", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_cron_run_log_job_started", "cron_run_log")
    op.drop_table("cron_run_log")
