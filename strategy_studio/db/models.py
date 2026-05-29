from __future__ import annotations

"""平台数据库模型。"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import BIGINT, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from strategy_studio.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    exchange: Mapped[str] = mapped_column(String(16))
    asset_type: Mapped[str] = mapped_column(String(32), default="equity")
    name: Mapped[str] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    price_bars: Mapped[list["PriceBar"]] = relationship(back_populates="instrument")
    aliases: Mapped[list["InstrumentAlias"]] = relationship(back_populates="instrument")
    market_data_series: Mapped[list["MarketDataSeries"]] = relationship(back_populates="instrument")
    corporate_actions: Mapped[list["CorporateActionEvent"]] = relationship(back_populates="instrument")


class PriceBar(Base):
    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint("instrument_id", "interval", "bar_time", name="uq_price_bars_instrument_interval_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    interval: Mapped[str] = mapped_column(String(16), index=True)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BIGINT)
    source: Mapped[str] = mapped_column(String(32), default="yahoo")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    instrument: Mapped[Instrument] = relationship(back_populates="price_bars")


class DataSyncRun(Base):
    __tablename__ = "data_sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(32))
    interval: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    symbols_count: Mapped[int] = mapped_column(Integer, default=0)
    bars_inserted: Mapped[int] = mapped_column(Integer, default=0)
    bars_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")

    items: Mapped[list["DataSyncRunItem"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class DataSyncRunItem(Base):
    __tablename__ = "data_sync_run_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("data_sync_runs.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="running")
    bars_inserted: Mapped[int] = mapped_column(Integer, default=0)
    bars_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")

    run: Mapped[DataSyncRun] = relationship(back_populates="items")


class PlatformHeartbeat(Base):
    __tablename__ = "platform_heartbeats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    pid: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    details_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class DataProvider(Base):
    """可管理的数据渠道定义。

    Yahoo、通达信、Tushare 都在这里注册。前端后续只需要读取这个表，就能按渠道展示能力、
    默认配置和任务入口，不必把渠道列表硬编码在页面或服务里。
    """

    __tablename__ = "data_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    provider_name: Mapped[str] = mapped_column(String(64))
    provider_type: Mapped[str] = mapped_column(String(32), default="market_data")
    transport: Mapped[str] = mapped_column(String(32), default="api")
    status: Mapped[str] = mapped_column(String(16), default="active")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    config_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    aliases: Mapped[list["InstrumentAlias"]] = relationship(back_populates="provider")
    market_data_series: Mapped[list["MarketDataSeries"]] = relationship(back_populates="provider")
    corporate_actions: Mapped[list["CorporateActionEvent"]] = relationship(back_populates="provider")
    source_files: Mapped[list["SourceFileManifest"]] = relationship(back_populates="provider")
    ingestion_jobs: Mapped[list["DataIngestionJob"]] = relationship(back_populates="provider")


class InstrumentAlias(Base):
    """保存同一标的在不同数据源中的代码映射。"""

    __tablename__ = "instrument_aliases"
    __table_args__ = (
        UniqueConstraint("provider_id", "source_symbol", name="uq_instrument_aliases_provider_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id", ondelete="CASCADE"), index=True)
    source_symbol: Mapped[str] = mapped_column(String(64))
    source_name: Mapped[str] = mapped_column(String(128), default="")
    market: Mapped[str] = mapped_column(String(32), default="")
    exchange: Mapped[str] = mapped_column(String(32), default="")
    security_type: Mapped[str] = mapped_column(String(32), default="equity")
    currency: Mapped[str] = mapped_column(String(16), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    instrument: Mapped[Instrument] = relationship(back_populates="aliases")
    provider: Mapped[DataProvider] = relationship(back_populates="aliases")
    market_data_series: Mapped[list["MarketDataSeries"]] = relationship(back_populates="alias")


class PriceAdjustmentSegment(Base):
    """把公司行动重算后的仿射公式区间单独持久化。

    这是迁移通达信 C++ 前复权算法的关键基础表。算法先基于公司行动生成连续区间的 A/B，
    再对原始日 K 做双指针线性匹配，可避免每条 K 线重复扫描全部事件。
    """

    __tablename__ = "price_adjustment_segments"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "provider_id",
            "adjustment_kind",
            "start_date",
            "end_date",
            name="uq_price_adjustment_segments_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id", ondelete="CASCADE"), index=True)
    action_provider_id: Mapped[int | None] = mapped_column(ForeignKey("data_providers.id", ondelete="SET NULL"), nullable=True)
    adjustment_kind: Mapped[str] = mapped_column(String(32), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    adjust_a: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    adjust_b: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    status: Mapped[str] = mapped_column(String(16), default="ready")
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class MarketDataSeries(Base):
    """统一描述一组可持久化 K 线序列。"""

    __tablename__ = "market_data_series"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "alias_id",
            "interval",
            "adjustment_kind",
            "session_type",
            "price_type",
            name="uq_market_data_series_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id", ondelete="CASCADE"), index=True)
    alias_id: Mapped[int | None] = mapped_column(ForeignKey("instrument_aliases.id", ondelete="SET NULL"), nullable=True, index=True)
    market: Mapped[str] = mapped_column(String(32), default="")
    exchange: Mapped[str] = mapped_column(String(32), default="")
    interval: Mapped[str] = mapped_column(String(16), index=True)
    bar_type: Mapped[str] = mapped_column(String(32), default="time")
    session_type: Mapped[str] = mapped_column(String(16), default="regular")
    adjustment_kind: Mapped[str] = mapped_column(String(32), default="raw")
    price_type: Mapped[str] = mapped_column(String(32), default="trade")
    currency: Mapped[str] = mapped_column(String(16), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    first_bar_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_bar_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    instrument: Mapped[Instrument] = relationship(back_populates="market_data_series")
    provider: Mapped[DataProvider] = relationship(back_populates="market_data_series")
    alias: Mapped[InstrumentAlias | None] = relationship(back_populates="market_data_series")
    bars: Mapped[list["MarketDataBar"]] = relationship(back_populates="series", cascade="all, delete-orphan")


class MarketDataBar(Base):
    """统一 K 线事实表。

    这里按“序列 + 时间”唯一约束保存不同来源、不同市场、不同复权口径的 K 线，
    与旧版只支持 Yahoo 的 `price_bars` 并行存在，便于平滑迁移。
    """

    __tablename__ = "market_data_bars"
    __table_args__ = (
        UniqueConstraint("series_id", "bar_time", name="uq_market_data_bars_series_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("market_data_series.id", ondelete="CASCADE"), index=True)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[int] = mapped_column(BIGINT, default=0)
    turnover_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_interest: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_status: Mapped[str] = mapped_column(String(16), default="ready")
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    series: Mapped[MarketDataSeries] = relationship(back_populates="bars")


class CorporateActionEvent(Base):
    """公司行动事件事实表。"""

    __tablename__ = "corporate_action_events"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "source_symbol",
            "action_type",
            "ex_date",
            "record_date",
            "announce_date",
            name="uq_corporate_action_events_source_event",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id", ondelete="CASCADE"), index=True)
    source_symbol: Mapped[str] = mapped_column(String(64), index=True)
    action_type: Mapped[str] = mapped_column(String(32), default="dividend")
    announce_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    record_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ex_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pay_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cash_dividend: Mapped[float] = mapped_column(Float, default=0.0)
    stock_bonus_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    stock_conversion_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    rights_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    rights_price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="implemented")
    raw_payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    instrument: Mapped[Instrument] = relationship(back_populates="corporate_actions")
    provider: Mapped[DataProvider] = relationship(back_populates="corporate_actions")


class SourceFileManifest(Base):
    """文件型数据源的增量状态。

    通达信 `.day/.lc1/.lc5` 这类本地文件不会直接暴露 API 游标，因此需要单独记录路径、
    文件大小、mtime、尾部 hash 和最近导入位置，后续增量导入才能稳定运行。
    """

    __tablename__ = "source_file_manifests"
    __table_args__ = (
        UniqueConstraint("provider_id", "source_path", name="uq_source_file_manifests_provider_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("data_providers.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True, index=True)
    series_id: Mapped[int | None] = mapped_column(ForeignKey("market_data_series.id", ondelete="SET NULL"), nullable=True, index=True)
    source_path: Mapped[str] = mapped_column(String(255))
    file_kind: Mapped[str] = mapped_column(String(32), default="tdx_vipdoc")
    market: Mapped[str] = mapped_column(String(32), default="")
    interval: Mapped[str] = mapped_column(String(16), default="1d")
    source_size: Mapped[int] = mapped_column(BIGINT, default=0)
    source_mtime: Mapped[float] = mapped_column(Float, default=0.0)
    record_count: Mapped[int] = mapped_column(BIGINT, default=0)
    tail_hash: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="new")
    last_bar_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    provider: Mapped[DataProvider] = relationship(back_populates="source_files")


class DataIngestionJob(Base):
    """统一的数据导入任务。

    Yahoo 下载、通达信原始导入、Tushare 公司行动抓取和前复权重算都映射为同一种后台任务，
    这样前端可以共用一套列表、状态轮询和错误追踪逻辑。
    """

    __tablename__ = "data_ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("data_providers.id", ondelete="SET NULL"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str] = mapped_column(String(64), default="system")
    requested_via: Mapped[str] = mapped_column(String(16), default="api")
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    target_scope_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    options_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    summary_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    targets_total: Mapped[int] = mapped_column(Integer, default=0)
    targets_completed: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(BIGINT, default=0)
    rows_updated: Mapped[int] = mapped_column(BIGINT, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    provider: Mapped[DataProvider | None] = relationship(back_populates="ingestion_jobs")
    items: Mapped[list["DataIngestionJobItem"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class DataIngestionJobItem(Base):
    """任务拆分到单个标的/单个序列后的执行明细。"""

    __tablename__ = "data_ingestion_job_items"
    __table_args__ = (
        UniqueConstraint("job_id", "item_key", name="uq_data_ingestion_job_items_job_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("data_ingestion_jobs.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("data_providers.id", ondelete="SET NULL"), nullable=True, index=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True, index=True)
    series_id: Mapped[int | None] = mapped_column(ForeignKey("market_data_series.id", ondelete="SET NULL"), nullable=True, index=True)
    item_key: Mapped[str] = mapped_column(String(128))
    source_symbol: Mapped[str] = mapped_column(String(64), default="")
    interval: Mapped[str] = mapped_column(String(16), default="")
    stage: Mapped[str] = mapped_column(String(32), default="prepare")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    rows_inserted: Mapped[int] = mapped_column(BIGINT, default=0)
    rows_updated: Mapped[int] = mapped_column(BIGINT, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    details_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[DataIngestionJob] = relationship(back_populates="items")


class BacktestJob(Base):
    __tablename__ = "backtest_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(32), default="backtest")
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    request_payload_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    runtime_details_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")

    reports: Mapped[list["BacktestReport"]] = relationship(back_populates="job")


class StrategyParameterTemplate(Base):
    __tablename__ = "strategy_parameter_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    template_name: Mapped[str] = mapped_column(String(128))
    strategy_kind: Mapped[str] = mapped_column(String(64), index=True)
    interval: Mapped[str] = mapped_column(String(16), index=True)
    execution_profile: Mapped[str] = mapped_column(String(32), default="realistic")
    validation_start: Mapped[str] = mapped_column(String(32), default="")
    lookback_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    jobs: Mapped[int] = mapped_column(Integer, default=1)
    execution_overrides_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    parameter_space_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class BacktestReport(Base):
    __tablename__ = "backtest_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("backtest_jobs.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    interval: Mapped[str] = mapped_column(String(16), index=True)
    strategy_kind: Mapped[str] = mapped_column(String(64), index=True)
    report_name: Mapped[str] = mapped_column(String(128))
    dataset_start: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    dataset_end: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    validation_start: Mapped[str] = mapped_column(String(32), default="")
    summary_metrics_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    parameters_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    artifacts_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    job: Mapped[BacktestJob] = relationship(back_populates="reports")
    instrument: Mapped[Instrument] = relationship()
    equity_curves: Mapped[list["BacktestEquityCurve"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    trades: Mapped[list["BacktestTrade"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    events: Mapped[list["BacktestEvent"]] = relationship(back_populates="report", cascade="all, delete-orphan")


class BacktestEquityCurve(Base):
    __tablename__ = "backtest_equity_curves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("backtest_reports.id", ondelete="CASCADE"), index=True)
    curve_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    equity: Mapped[float] = mapped_column(Float)
    drawdown_pct: Mapped[float] = mapped_column(Float)
    return_pct: Mapped[float] = mapped_column(Float)

    report: Mapped[BacktestReport] = relationship(back_populates="equity_curves")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("backtest_reports.id", ondelete="CASCADE"), index=True)
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    side: Mapped[str] = mapped_column(String(16))
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_cost: Mapped[float] = mapped_column(Float, default=0.0)
    trade_type: Mapped[str] = mapped_column(String(32), default="")
    note: Mapped[str] = mapped_column(Text, default="")

    report: Mapped[BacktestReport] = relationship(back_populates="trades")


class BacktestEvent(Base):
    __tablename__ = "backtest_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("backtest_reports.id", ondelete="CASCADE"), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    price: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB)

    report: Mapped[BacktestReport] = relationship(back_populates="events")
