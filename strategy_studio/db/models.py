from __future__ import annotations

"""平台数据库模型。"""

from datetime import UTC, datetime

from sqlalchemy import BIGINT, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
