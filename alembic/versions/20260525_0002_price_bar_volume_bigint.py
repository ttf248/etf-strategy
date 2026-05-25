"""alter price bar volume to bigint

Revision ID: 20260525_0002
Revises: 20260525_0001
Create Date: 2026-05-25 16:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260525_0002"
down_revision = "20260525_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("price_bars", "volume", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("price_bars", "volume", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=False)

