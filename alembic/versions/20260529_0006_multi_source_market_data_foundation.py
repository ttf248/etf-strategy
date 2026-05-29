"""add multi-source market data foundation

Revision ID: 20260529_0006
Revises: 20260528_0005
Create Date: 2026-05-29 18:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260529_0006"
down_revision = "20260528_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_providers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_key", sa.String(length=32), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False, server_default="market_data"),
        sa.Column("transport", sa.String(length=32), nullable=False, server_default="api"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("provider_key", name="uq_data_providers_provider_key"),
    )

    provider_table = sa.table(
        "data_providers",
        sa.column("provider_key", sa.String()),
        sa.column("provider_name", sa.String()),
        sa.column("provider_type", sa.String()),
        sa.column("transport", sa.String()),
        sa.column("status", sa.String()),
        sa.column("timezone", sa.String()),
        sa.column("config_json", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.bulk_insert(
        provider_table,
        [
            {
                "provider_key": "yahoo",
                "provider_name": "Yahoo Finance",
                "provider_type": "market_data",
                "transport": "api",
                "status": "active",
                "timezone": "UTC",
                "config_json": {
                    "supports_intervals": ["1d", "15m", "1m"],
                    "supports_markets": ["US", "HK", "CN"],
                    "notes": "当前项目已实现的在线行情来源。",
                },
            },
            {
                "provider_key": "tdx",
                "provider_name": "通达信本地行情",
                "provider_type": "market_data",
                "transport": "filesystem",
                "status": "planned",
                "timezone": "Asia/Shanghai",
                "config_json": {
                    "supports_intervals": ["1d", "1m", "5m"],
                    "supports_markets": ["SH", "SZ", "BJ"],
                    "notes": "后续通过本地 vipdoc 路径导入原始行情。",
                },
            },
            {
                "provider_key": "tushare",
                "provider_name": "Tushare 公司行动",
                "provider_type": "corporate_action",
                "transport": "api",
                "status": "planned",
                "timezone": "Asia/Shanghai",
                "config_json": {
                    "dataset": "dividend",
                    "notes": "用于通达信前复权重算所需的公司行动事件。",
                },
            },
        ],
    )

    op.create_table(
        "instrument_aliases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_symbol", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("market", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("exchange", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("security_type", sa.String(length=32), nullable=False, server_default="equity"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("provider_id", "source_symbol", name="uq_instrument_aliases_provider_symbol"),
    )
    op.create_index("ix_instrument_aliases_instrument_id", "instrument_aliases", ["instrument_id"], unique=False)
    op.create_index("ix_instrument_aliases_provider_id", "instrument_aliases", ["provider_id"], unique=False)

    op.create_table(
        "price_adjustment_segments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("adjustment_kind", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("adjust_a", sa.Numeric(24, 12), nullable=False),
        sa.Column("adjust_b", sa.Numeric(24, 12), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ready"),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "instrument_id",
            "provider_id",
            "adjustment_kind",
            "start_date",
            "end_date",
            name="uq_price_adjustment_segments_scope",
        ),
    )
    op.create_index("ix_price_adjustment_segments_instrument_id", "price_adjustment_segments", ["instrument_id"], unique=False)
    op.create_index("ix_price_adjustment_segments_provider_id", "price_adjustment_segments", ["provider_id"], unique=False)
    op.create_index("ix_price_adjustment_segments_adjustment_kind", "price_adjustment_segments", ["adjustment_kind"], unique=False)

    op.create_table(
        "market_data_series",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias_id", sa.Integer(), sa.ForeignKey("instrument_aliases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("market", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("exchange", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("bar_type", sa.String(length=32), nullable=False, server_default="time"),
        sa.Column("session_type", sa.String(length=16), nullable=False, server_default="regular"),
        sa.Column("adjustment_kind", sa.String(length=32), nullable=False, server_default="raw"),
        sa.Column("price_type", sa.String(length=32), nullable=False, server_default="trade"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("first_bar_time", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_bar_time", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "provider_id",
            "alias_id",
            "interval",
            "adjustment_kind",
            "session_type",
            "price_type",
            name="uq_market_data_series_scope",
        ),
    )
    op.create_index("ix_market_data_series_instrument_id", "market_data_series", ["instrument_id"], unique=False)
    op.create_index("ix_market_data_series_provider_id", "market_data_series", ["provider_id"], unique=False)
    op.create_index("ix_market_data_series_alias_id", "market_data_series", ["alias_id"], unique=False)
    op.create_index("ix_market_data_series_interval", "market_data_series", ["interval"], unique=False)

    op.create_table(
        "market_data_bars",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("series_id", sa.Integer(), sa.ForeignKey("market_data_series.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=False), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("adj_close", sa.Float(), nullable=True),
        sa.Column("volume", sa.BIGINT(), nullable=False, server_default="0"),
        sa.Column("turnover_amount", sa.Float(), nullable=True),
        sa.Column("open_interest", sa.BIGINT(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("data_status", sa.String(length=16), nullable=False, server_default="ready"),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("series_id", "bar_time", name="uq_market_data_bars_series_time"),
    )
    op.create_index("ix_market_data_bars_series_id", "market_data_bars", ["series_id"], unique=False)
    op.create_index("ix_market_data_bars_bar_time", "market_data_bars", ["bar_time"], unique=False)

    op.create_table(
        "corporate_action_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_symbol", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False, server_default="dividend"),
        sa.Column("announce_date", sa.Date(), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("ex_date", sa.Date(), nullable=True),
        sa.Column("pay_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("cash_dividend", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stock_bonus_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stock_conversion_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rights_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rights_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="implemented"),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "provider_id",
            "source_symbol",
            "action_type",
            "ex_date",
            "record_date",
            "announce_date",
            name="uq_corporate_action_events_source_event",
        ),
    )
    op.create_index("ix_corporate_action_events_instrument_id", "corporate_action_events", ["instrument_id"], unique=False)
    op.create_index("ix_corporate_action_events_provider_id", "corporate_action_events", ["provider_id"], unique=False)
    op.create_index("ix_corporate_action_events_source_symbol", "corporate_action_events", ["source_symbol"], unique=False)

    op.create_table(
        "source_file_manifests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("series_id", sa.Integer(), sa.ForeignKey("market_data_series.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_path", sa.String(length=255), nullable=False),
        sa.Column("file_kind", sa.String(length=32), nullable=False, server_default="tdx_vipdoc"),
        sa.Column("market", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("interval", sa.String(length=16), nullable=False, server_default="1d"),
        sa.Column("source_size", sa.BIGINT(), nullable=False, server_default="0"),
        sa.Column("source_mtime", sa.Float(), nullable=False, server_default="0"),
        sa.Column("record_count", sa.BIGINT(), nullable=False, server_default="0"),
        sa.Column("tail_hash", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("last_bar_time", sa.DateTime(timezone=False), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("provider_id", "source_path", name="uq_source_file_manifests_provider_path"),
    )
    op.create_index("ix_source_file_manifests_provider_id", "source_file_manifests", ["provider_id"], unique=False)
    op.create_index("ix_source_file_manifests_instrument_id", "source_file_manifests", ["instrument_id"], unique=False)
    op.create_index("ix_source_file_manifests_series_id", "source_file_manifests", ["series_id"], unique=False)

    op.create_table(
        "data_ingestion_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("requested_via", sa.String(length=16), nullable=False, server_default="api"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("options_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("targets_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("targets_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_inserted", sa.BIGINT(), nullable=False, server_default="0"),
        sa.Column("rows_updated", sa.BIGINT(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_data_ingestion_jobs_provider_id", "data_ingestion_jobs", ["provider_id"], unique=False)
    op.create_index("ix_data_ingestion_jobs_job_type", "data_ingestion_jobs", ["job_type"], unique=False)
    op.create_index("ix_data_ingestion_jobs_status", "data_ingestion_jobs", ["status"], unique=False)

    op.create_table(
        "data_ingestion_job_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("data_ingestion_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("data_providers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("series_id", sa.Integer(), sa.ForeignKey("market_data_series.id", ondelete="SET NULL"), nullable=True),
        sa.Column("item_key", sa.String(length=128), nullable=False),
        sa.Column("source_symbol", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("interval", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="prepare"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("rows_inserted", sa.BIGINT(), nullable=False, server_default="0"),
        sa.Column("rows_updated", sa.BIGINT(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job_id", "item_key", name="uq_data_ingestion_job_items_job_item"),
    )
    op.create_index("ix_data_ingestion_job_items_job_id", "data_ingestion_job_items", ["job_id"], unique=False)
    op.create_index("ix_data_ingestion_job_items_provider_id", "data_ingestion_job_items", ["provider_id"], unique=False)
    op.create_index("ix_data_ingestion_job_items_instrument_id", "data_ingestion_job_items", ["instrument_id"], unique=False)
    op.create_index("ix_data_ingestion_job_items_series_id", "data_ingestion_job_items", ["series_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_data_ingestion_job_items_series_id", table_name="data_ingestion_job_items")
    op.drop_index("ix_data_ingestion_job_items_instrument_id", table_name="data_ingestion_job_items")
    op.drop_index("ix_data_ingestion_job_items_provider_id", table_name="data_ingestion_job_items")
    op.drop_index("ix_data_ingestion_job_items_job_id", table_name="data_ingestion_job_items")
    op.drop_table("data_ingestion_job_items")

    op.drop_index("ix_data_ingestion_jobs_status", table_name="data_ingestion_jobs")
    op.drop_index("ix_data_ingestion_jobs_job_type", table_name="data_ingestion_jobs")
    op.drop_index("ix_data_ingestion_jobs_provider_id", table_name="data_ingestion_jobs")
    op.drop_table("data_ingestion_jobs")

    op.drop_index("ix_source_file_manifests_series_id", table_name="source_file_manifests")
    op.drop_index("ix_source_file_manifests_instrument_id", table_name="source_file_manifests")
    op.drop_index("ix_source_file_manifests_provider_id", table_name="source_file_manifests")
    op.drop_table("source_file_manifests")

    op.drop_index("ix_corporate_action_events_source_symbol", table_name="corporate_action_events")
    op.drop_index("ix_corporate_action_events_provider_id", table_name="corporate_action_events")
    op.drop_index("ix_corporate_action_events_instrument_id", table_name="corporate_action_events")
    op.drop_table("corporate_action_events")

    op.drop_index("ix_market_data_bars_bar_time", table_name="market_data_bars")
    op.drop_index("ix_market_data_bars_series_id", table_name="market_data_bars")
    op.drop_table("market_data_bars")

    op.drop_index("ix_market_data_series_interval", table_name="market_data_series")
    op.drop_index("ix_market_data_series_alias_id", table_name="market_data_series")
    op.drop_index("ix_market_data_series_provider_id", table_name="market_data_series")
    op.drop_index("ix_market_data_series_instrument_id", table_name="market_data_series")
    op.drop_table("market_data_series")

    op.drop_index("ix_price_adjustment_segments_adjustment_kind", table_name="price_adjustment_segments")
    op.drop_index("ix_price_adjustment_segments_provider_id", table_name="price_adjustment_segments")
    op.drop_index("ix_price_adjustment_segments_instrument_id", table_name="price_adjustment_segments")
    op.drop_table("price_adjustment_segments")

    op.drop_index("ix_instrument_aliases_provider_id", table_name="instrument_aliases")
    op.drop_index("ix_instrument_aliases_instrument_id", table_name="instrument_aliases")
    op.drop_table("instrument_aliases")

    op.drop_table("data_providers")
