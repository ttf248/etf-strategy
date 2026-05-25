"""add strategy parameter templates

Revision ID: 20260525_0003
Revises: 20260525_0002
Create Date: 2026-05-25 19:35:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260525_0003"
down_revision = "20260525_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_parameter_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("template_key", sa.String(length=64), nullable=False),
        sa.Column("template_name", sa.String(length=128), nullable=False),
        sa.Column("strategy_kind", sa.String(length=64), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("execution_profile", sa.String(length=32), nullable=False),
        sa.Column("validation_start", sa.String(length=32), nullable=False),
        sa.Column("lookback_days", sa.Integer(), nullable=True),
        sa.Column("validation_ratio", sa.Float(), nullable=True),
        sa.Column("jobs", sa.Integer(), nullable=False),
        sa.Column("execution_overrides_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("parameter_space_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_strategy_parameter_templates_template_key", "strategy_parameter_templates", ["template_key"], unique=True)
    op.create_index("ix_strategy_parameter_templates_strategy_kind", "strategy_parameter_templates", ["strategy_kind"], unique=False)
    op.create_index("ix_strategy_parameter_templates_interval", "strategy_parameter_templates", ["interval"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_strategy_parameter_templates_interval", table_name="strategy_parameter_templates")
    op.drop_index("ix_strategy_parameter_templates_strategy_kind", table_name="strategy_parameter_templates")
    op.drop_index("ix_strategy_parameter_templates_template_key", table_name="strategy_parameter_templates")
    op.drop_table("strategy_parameter_templates")
