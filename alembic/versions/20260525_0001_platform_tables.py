"""create platform tables

Revision ID: 20260525_0001
Revises:
Create Date: 2026-05-25 17:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260525_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"], unique=True)

    op.create_table(
        "price_bars",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=False), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("adj_close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("instrument_id", "interval", "bar_time", name="uq_price_bars_instrument_interval_time"),
    )
    op.create_index("ix_price_bars_instrument_id", "price_bars", ["instrument_id"], unique=False)
    op.create_index("ix_price_bars_interval", "price_bars", ["interval"], unique=False)
    op.create_index("ix_price_bars_bar_time", "price_bars", ["bar_time"], unique=False)

    op.create_table(
        "data_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("symbols_count", sa.Integer(), nullable=False),
        sa.Column("bars_inserted", sa.Integer(), nullable=False),
        sa.Column("bars_updated", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
    )
    op.create_table(
        "data_sync_run_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("data_sync_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("bars_inserted", sa.Integer(), nullable=False),
        sa.Column("bars_updated", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
    )
    op.create_index("ix_data_sync_run_items_run_id", "data_sync_run_items", ["run_id"], unique=False)

    op.create_table(
        "backtest_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("request_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("progress_pct", sa.Float(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
    )
    op.create_index("ix_backtest_jobs_status", "backtest_jobs", ["status"], unique=False)

    op.create_table(
        "backtest_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("backtest_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("strategy_kind", sa.String(length=64), nullable=False),
        sa.Column("report_name", sa.String(length=128), nullable=False),
        sa.Column("dataset_start", sa.DateTime(timezone=False), nullable=False),
        sa.Column("dataset_end", sa.DateTime(timezone=False), nullable=False),
        sa.Column("validation_start", sa.String(length=32), nullable=False),
        sa.Column("summary_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("parameters_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("artifacts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_backtest_reports_job_id", "backtest_reports", ["job_id"], unique=False)
    op.create_index("ix_backtest_reports_instrument_id", "backtest_reports", ["instrument_id"], unique=False)
    op.create_index("ix_backtest_reports_interval", "backtest_reports", ["interval"], unique=False)
    op.create_index("ix_backtest_reports_strategy_kind", "backtest_reports", ["strategy_kind"], unique=False)

    op.create_table(
        "backtest_equity_curves",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("backtest_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("curve_time", sa.DateTime(timezone=False), nullable=False),
        sa.Column("equity", sa.Float(), nullable=False),
        sa.Column("drawdown_pct", sa.Float(), nullable=False),
        sa.Column("return_pct", sa.Float(), nullable=False),
    )
    op.create_index("ix_backtest_equity_curves_report_id", "backtest_equity_curves", ["report_id"], unique=False)
    op.create_index("ix_backtest_equity_curves_curve_time", "backtest_equity_curves", ["curve_time"], unique=False)

    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("backtest_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trade_time", sa.DateTime(timezone=False), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("slippage_cost", sa.Float(), nullable=False),
        sa.Column("trade_type", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
    )
    op.create_index("ix_backtest_trades_report_id", "backtest_trades", ["report_id"], unique=False)
    op.create_index("ix_backtest_trades_trade_time", "backtest_trades", ["trade_time"], unique=False)

    op.create_table(
        "backtest_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("backtest_reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=False), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_backtest_events_report_id", "backtest_events", ["report_id"], unique=False)
    op.create_index("ix_backtest_events_event_time", "backtest_events", ["event_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_backtest_events_event_time", table_name="backtest_events")
    op.drop_index("ix_backtest_events_report_id", table_name="backtest_events")
    op.drop_table("backtest_events")
    op.drop_index("ix_backtest_trades_trade_time", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_report_id", table_name="backtest_trades")
    op.drop_table("backtest_trades")
    op.drop_index("ix_backtest_equity_curves_curve_time", table_name="backtest_equity_curves")
    op.drop_index("ix_backtest_equity_curves_report_id", table_name="backtest_equity_curves")
    op.drop_table("backtest_equity_curves")
    op.drop_index("ix_backtest_reports_strategy_kind", table_name="backtest_reports")
    op.drop_index("ix_backtest_reports_interval", table_name="backtest_reports")
    op.drop_index("ix_backtest_reports_instrument_id", table_name="backtest_reports")
    op.drop_index("ix_backtest_reports_job_id", table_name="backtest_reports")
    op.drop_table("backtest_reports")
    op.drop_index("ix_backtest_jobs_status", table_name="backtest_jobs")
    op.drop_table("backtest_jobs")
    op.drop_index("ix_data_sync_run_items_run_id", table_name="data_sync_run_items")
    op.drop_table("data_sync_run_items")
    op.drop_table("data_sync_runs")
    op.drop_index("ix_price_bars_bar_time", table_name="price_bars")
    op.drop_index("ix_price_bars_interval", table_name="price_bars")
    op.drop_index("ix_price_bars_instrument_id", table_name="price_bars")
    op.drop_table("price_bars")
    op.drop_index("ix_instruments_symbol", table_name="instruments")
    op.drop_table("instruments")

