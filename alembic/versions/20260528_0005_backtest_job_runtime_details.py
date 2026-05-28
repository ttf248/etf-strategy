"""add backtest job runtime details

Revision ID: 20260528_0005
Revises: 20260527_0004
Create Date: 2026-05-28 20:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260528_0005"
down_revision = "20260527_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "backtest_jobs",
        sa.Column(
            "runtime_details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("backtest_jobs", "runtime_details_json", server_default=None)


def downgrade() -> None:
    op.drop_column("backtest_jobs", "runtime_details_json")
