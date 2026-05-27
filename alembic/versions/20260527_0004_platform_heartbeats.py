"""add platform heartbeats

Revision ID: 20260527_0004
Revises: 20260525_0003
Create Date: 2026-05-27 16:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260527_0004"
down_revision = "20260525_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_heartbeats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("service_name", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_platform_heartbeats_service_name", "platform_heartbeats", ["service_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_platform_heartbeats_service_name", table_name="platform_heartbeats")
    op.drop_table("platform_heartbeats")
