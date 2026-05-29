from __future__ import annotations

"""行情仓储。"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

import pandas as pd
from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from strategy_studio.db.models import (
    DataIngestionJob,
    DataIngestionJobItem,
    DataProvider,
    DataSyncRun,
    DataSyncRunItem,
    Instrument,
    InstrumentAlias,
    MarketDataBar,
    MarketDataSeries,
    PriceBar,
)


def _infer_exchange(symbol: str) -> str:
    if symbol.endswith(".HK"):
        return "HK"
    if symbol.endswith(".SS"):
        return "SS"
    if symbol.endswith(".SZ"):
        return "SZ"
    return "US"


def _chunked(values: list[datetime], size: int = 5000) -> Iterable[list[datetime]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def get_instrument_by_symbol(session: Session, symbol: str) -> Instrument | None:
    return session.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))


def get_data_provider_by_key(session: Session, provider_key: str) -> DataProvider | None:
    return session.scalar(select(DataProvider).where(DataProvider.provider_key == provider_key))


def ensure_data_provider(
    session: Session,
    provider_key: str,
    provider_name: str,
    *,
    provider_type: str = "market_data",
    transport: str = "api",
    timezone: str = "UTC",
    config_json: dict[str, object] | None = None,
    status: str = "active",
) -> DataProvider:
    provider = get_data_provider_by_key(session, provider_key)
    if provider is not None:
        provider.provider_name = provider_name
        provider.provider_type = provider_type
        provider.transport = transport
        provider.timezone = timezone
        provider.status = status
        if config_json:
            provider.config_json = {**provider.config_json, **config_json}
        return provider

    provider = DataProvider(
        provider_key=provider_key,
        provider_name=provider_name,
        provider_type=provider_type,
        transport=transport,
        timezone=timezone,
        status=status,
        config_json=config_json or {},
    )
    session.add(provider)
    session.flush()
    return provider


def get_or_create_instrument(
    session: Session,
    symbol: str,
    name: str | None = None,
    asset_type: str = "equity",
    timezone: str = "UTC",
) -> Instrument:
    normalized = symbol.strip().upper()
    instrument = get_instrument_by_symbol(session, normalized)
    if instrument is not None:
        if name and instrument.name != name:
            instrument.name = name
        if instrument.asset_type != asset_type:
            instrument.asset_type = asset_type
        if instrument.timezone != timezone:
            instrument.timezone = timezone
        return instrument

    instrument = Instrument(
        symbol=normalized,
        exchange=_infer_exchange(normalized),
        asset_type=asset_type,
        name=name or normalized,
        timezone=timezone,
        is_active=True,
    )
    session.add(instrument)
    session.flush()
    return instrument


def get_or_create_instrument_alias(
    session: Session,
    instrument: Instrument,
    provider: DataProvider,
    source_symbol: str,
    *,
    source_name: str = "",
    market: str = "",
    exchange: str = "",
    security_type: str = "equity",
    currency: str = "",
    timezone: str = "UTC",
) -> InstrumentAlias:
    normalized = source_symbol.strip().upper()
    alias = session.scalar(
        select(InstrumentAlias).where(
            InstrumentAlias.provider_id == provider.id,
            InstrumentAlias.source_symbol == normalized,
        )
    )
    if alias is not None:
        alias.instrument_id = instrument.id
        alias.source_name = source_name or alias.source_name
        alias.market = market or alias.market
        alias.exchange = exchange or alias.exchange
        alias.security_type = security_type
        alias.currency = currency or alias.currency
        alias.timezone = timezone
        alias.is_primary = True
        return alias

    alias = InstrumentAlias(
        instrument_id=instrument.id,
        provider_id=provider.id,
        source_symbol=normalized,
        source_name=source_name or normalized,
        market=market,
        exchange=exchange,
        security_type=security_type,
        currency=currency,
        timezone=timezone,
        is_primary=True,
    )
    session.add(alias)
    session.flush()
    return alias


def get_or_create_market_data_series(
    session: Session,
    instrument: Instrument,
    provider: DataProvider,
    alias: InstrumentAlias,
    *,
    interval: str,
    market: str = "",
    exchange: str = "",
    adjustment_kind: str = "raw",
    session_type: str = "regular",
    price_type: str = "trade",
    bar_type: str = "time",
    currency: str = "",
    timezone: str = "UTC",
) -> MarketDataSeries:
    series = session.scalar(
        select(MarketDataSeries).where(
            MarketDataSeries.provider_id == provider.id,
            MarketDataSeries.alias_id == alias.id,
            MarketDataSeries.interval == interval,
            MarketDataSeries.adjustment_kind == adjustment_kind,
            MarketDataSeries.session_type == session_type,
            MarketDataSeries.price_type == price_type,
        )
    )
    if series is not None:
        series.instrument_id = instrument.id
        series.market = market or series.market
        series.exchange = exchange or series.exchange
        series.bar_type = bar_type
        series.currency = currency or series.currency
        series.timezone = timezone
        series.is_active = True
        return series

    series = MarketDataSeries(
        instrument_id=instrument.id,
        provider_id=provider.id,
        alias_id=alias.id,
        market=market,
        exchange=exchange,
        interval=interval,
        adjustment_kind=adjustment_kind,
        session_type=session_type,
        price_type=price_type,
        bar_type=bar_type,
        currency=currency,
        timezone=timezone,
        is_active=True,
    )
    session.add(series)
    session.flush()
    return series


def upsert_price_frame(
    session: Session,
    instrument: Instrument,
    interval: str,
    frame: pd.DataFrame,
    source: str = "yahoo",
) -> tuple[int, int]:
    """批量写入 K 线并返回新增/覆盖条数。"""
    if frame.empty:
        return 0, 0

    normalized = frame.copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"]).dt.tz_localize(None)
    timestamps = [item.to_pydatetime() for item in normalized["Date"].tolist()]
    existing: set[datetime] = set()
    for batch in _chunked(timestamps):
        rows = session.scalars(
            select(PriceBar.bar_time).where(
                PriceBar.instrument_id == instrument.id,
                PriceBar.interval == interval,
                PriceBar.bar_time.in_(batch),
            )
        )
        existing.update(rows)

    all_rows = [
        {
            "instrument_id": instrument.id,
            "interval": interval,
            "bar_time": item["Date"].to_pydatetime() if hasattr(item["Date"], "to_pydatetime") else item["Date"],
            "open": float(item["Open"]),
            "high": float(item["High"]),
            "low": float(item["Low"]),
            "close": float(item["Close"]),
            "adj_close": float(item["Close"]),
            "volume": int(item["Volume"]),
            "source": source,
        }
        for item in normalized.to_dict(orient="records")
    ]
    for row_batch in _chunked(all_rows, size=1500):
        statement = insert(PriceBar).values(row_batch)
        update_columns = {
            "open": statement.excluded.open,
            "high": statement.excluded.high,
            "low": statement.excluded.low,
            "close": statement.excluded.close,
            "adj_close": statement.excluded.adj_close,
            "volume": statement.excluded.volume,
            "source": statement.excluded.source,
            "ingested_at": func.now(),
        }
        session.execute(
            statement.on_conflict_do_update(
                constraint="uq_price_bars_instrument_interval_time",
                set_=update_columns,
            )
        )
    updated_count = len(existing)
    inserted_count = len(all_rows) - updated_count
    return inserted_count, updated_count


def upsert_market_data_frame(
    session: Session,
    series: MarketDataSeries,
    frame: pd.DataFrame,
) -> tuple[int, int]:
    """把标准化 OHLCV 写入统一 K 线事实表。"""
    if frame.empty:
        return 0, 0

    normalized = frame.copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"]).dt.tz_localize(None)
    timestamps = [item.to_pydatetime() for item in normalized["Date"].tolist()]
    existing: set[datetime] = set()
    for batch in _chunked(timestamps):
        rows = session.scalars(
            select(MarketDataBar.bar_time).where(
                MarketDataBar.series_id == series.id,
                MarketDataBar.bar_time.in_(batch),
            )
        )
        existing.update(rows)

    all_rows = [
        {
            "series_id": series.id,
            "bar_time": item["Date"].to_pydatetime() if hasattr(item["Date"], "to_pydatetime") else item["Date"],
            "open": float(item["Open"]),
            "high": float(item["High"]),
            "low": float(item["Low"]),
            "close": float(item["Close"]),
            "adj_close": float(item["Close"]),
            "volume": int(item["Volume"]),
            "data_status": "ready",
            "payload_json": {},
        }
        for item in normalized.to_dict(orient="records")
    ]
    for row_batch in _chunked(all_rows, size=1500):
        statement = insert(MarketDataBar).values(row_batch)
        session.execute(
            statement.on_conflict_do_update(
                constraint="uq_market_data_bars_series_time",
                set_={
                    "open": statement.excluded.open,
                    "high": statement.excluded.high,
                    "low": statement.excluded.low,
                    "close": statement.excluded.close,
                    "adj_close": statement.excluded.adj_close,
                    "volume": statement.excluded.volume,
                    "data_status": statement.excluded.data_status,
                    "payload_json": statement.excluded.payload_json,
                    "ingested_at": func.now(),
                },
            )
        )
    series.first_bar_time = min(
        value for value in [series.first_bar_time, min(timestamps)] if value is not None
    )
    series.last_bar_time = max(
        value for value in [series.last_bar_time, max(timestamps)] if value is not None
    )
    series.last_ingested_at = utc_now()
    inserted_count = len(all_rows) - len(existing)
    updated_count = len(existing)
    return inserted_count, updated_count


def create_data_ingestion_job(
    session: Session,
    *,
    provider: DataProvider | None,
    job_type: str,
    requested_via: str,
    target_scope_json: dict[str, object] | None = None,
    options_json: dict[str, object] | None = None,
    requested_by: str = "system",
) -> DataIngestionJob:
    job = DataIngestionJob(
        provider_id=provider.id if provider is not None else None,
        job_type=job_type,
        requested_by=requested_by,
        requested_via=requested_via,
        status="running",
        target_scope_json=target_scope_json or {},
        options_json=options_json or {},
        summary_json={},
    )
    session.add(job)
    session.flush()
    return job


def create_data_ingestion_job_item(
    session: Session,
    job: DataIngestionJob,
    *,
    item_key: str,
    source_symbol: str,
    interval: str,
    provider: DataProvider | None = None,
) -> DataIngestionJobItem:
    item = DataIngestionJobItem(
        job_id=job.id,
        provider_id=provider.id if provider is not None else None,
        item_key=item_key,
        source_symbol=source_symbol,
        interval=interval,
        stage="download",
        status="running",
        details_json={},
    )
    session.add(item)
    session.flush()
    return item


def list_instrument_coverages(session: Session) -> list[dict[str, object]]:
    rows = session.execute(
        select(
            Instrument.symbol,
            Instrument.name,
            Instrument.exchange,
            PriceBar.interval,
            func.count(PriceBar.id).label("bar_count"),
            func.min(PriceBar.bar_time).label("start_time"),
            func.max(PriceBar.bar_time).label("end_time"),
            func.max(PriceBar.ingested_at).label("last_ingested_at"),
        )
        .join(PriceBar, PriceBar.instrument_id == Instrument.id)
        .group_by(Instrument.symbol, Instrument.name, Instrument.exchange, PriceBar.interval)
        .order_by(Instrument.symbol, PriceBar.interval)
    )
    return [
        {
            "symbol": row.symbol,
            "name": row.name,
            "exchange": row.exchange,
            "interval": row.interval,
            "bar_count": int(row.bar_count),
            "start_time": row.start_time.isoformat(sep=" ") if row.start_time else "",
            "end_time": row.end_time.isoformat(sep=" ") if row.end_time else "",
            "last_ingested_at": row.last_ingested_at.isoformat(sep=" ") if row.last_ingested_at else "",
        }
        for row in rows
    ]


def list_instruments(session: Session) -> list[dict[str, object]]:
    coverage_rows = list_instrument_coverages(session)
    grouped: dict[str, dict[str, object]] = {}
    for row in coverage_rows:
        entry = grouped.setdefault(
            str(row["symbol"]),
            {
                "symbol": row["symbol"],
                "name": row["name"],
                "exchange": row["exchange"],
                "intervals": [],
                "last_end_time": "",
            },
        )
        entry["intervals"].append(row["interval"])
        if str(row["end_time"]) > str(entry["last_end_time"]):
            entry["last_end_time"] = row["end_time"]
    return list(grouped.values())


def get_market_data_stats(session: Session) -> dict[str, object]:
    instrument_count = int(session.scalar(select(func.count(Instrument.id))) or 0)
    total_bars = int(session.scalar(select(func.count(PriceBar.id))) or 0)
    interval_rows = session.execute(
        select(PriceBar.interval, func.count(PriceBar.id).label("bar_count"))
        .group_by(PriceBar.interval)
        .order_by(PriceBar.interval)
    )
    by_interval = [{"interval": row.interval, "bar_count": int(row.bar_count)} for row in interval_rows]
    coverages = list_instrument_coverages(session)
    latest_sync = session.scalars(select(DataSyncRun).order_by(DataSyncRun.started_at.desc()).limit(10)).all()
    return {
        "instrument_count": instrument_count,
        "total_bars": total_bars,
        "by_interval": by_interval,
        "coverages": coverages,
        "recent_sync_runs": [
            {
                "id": run.id,
                "job_type": run.job_type,
                "interval": run.interval,
                "status": run.status,
                "started_at": run.started_at.isoformat(sep=" "),
                "completed_at": run.completed_at.isoformat(sep=" ") if run.completed_at else "",
                "symbols_count": run.symbols_count,
                "bars_inserted": run.bars_inserted,
                "bars_updated": run.bars_updated,
                "error_message": run.error_message,
            }
            for run in latest_sync
        ],
    }


def list_price_bars(
    session: Session,
    symbol: str,
    interval: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = 2000,
) -> list[dict[str, object]]:
    instrument = get_instrument_by_symbol(session, symbol)
    if instrument is None:
        return []
    statement = (
        select(PriceBar)
        .where(PriceBar.instrument_id == instrument.id, PriceBar.interval == interval)
        .order_by(PriceBar.bar_time.desc())
        .limit(limit)
    )
    if start:
        statement = statement.where(PriceBar.bar_time >= pd.Timestamp(start).to_pydatetime())
    if end:
        statement = statement.where(PriceBar.bar_time <= pd.Timestamp(end).to_pydatetime())
    rows = list(reversed(session.scalars(statement).all()))
    return [
        {
            "symbol": instrument.symbol,
            "interval": row.interval,
            "bar_time": row.bar_time.isoformat(sep=" "),
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "adj_close": row.adj_close,
            "volume": row.volume,
            "source": row.source,
        }
        for row in rows
    ]


def load_price_frame_from_database(
    session: Session,
    symbol: str,
    interval: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    instrument = get_instrument_by_symbol(session, symbol)
    if instrument is None:
        raise ValueError(f"数据库中不存在该标的: {symbol}")

    statement: Select[tuple[PriceBar]] = (
        select(PriceBar)
        .where(PriceBar.instrument_id == instrument.id, PriceBar.interval == interval)
        .order_by(PriceBar.bar_time)
    )
    if start:
        statement = statement.where(PriceBar.bar_time >= pd.Timestamp(start).to_pydatetime())
    if end:
        statement = statement.where(PriceBar.bar_time <= pd.Timestamp(end).to_pydatetime())

    rows = session.scalars(statement).all()
    if not rows:
        raise ValueError(f"数据库中没有可用于回测的行情: symbol={symbol} interval={interval}")
    frame = pd.DataFrame(
        [
            {
                "Date": row.bar_time,
                "Open": row.open,
                "High": row.high,
                "Low": row.low,
                "Close": row.close,
                "Volume": row.volume,
            }
            for row in rows
        ]
    )
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame.sort_values("Date").set_index("Date")


def create_sync_run(session: Session, job_type: str, interval: str) -> DataSyncRun:
    run = DataSyncRun(job_type=job_type, interval=interval, status="running")
    session.add(run)
    session.flush()
    return run


def create_sync_run_item(session: Session, run: DataSyncRun, symbol: str) -> DataSyncRunItem:
    item = DataSyncRunItem(run_id=run.id, symbol=symbol, status="running")
    session.add(item)
    session.flush()
    return item


def list_sync_runs(session: Session, limit: int = 50) -> list[dict[str, object]]:
    runs = session.scalars(select(DataSyncRun).order_by(DataSyncRun.started_at.desc()).limit(limit)).all()
    return [
        {
            "id": run.id,
            "job_type": run.job_type,
            "interval": run.interval,
            "status": run.status,
            "started_at": run.started_at.isoformat(sep=" "),
            "completed_at": run.completed_at.isoformat(sep=" ") if run.completed_at else "",
            "symbols_count": run.symbols_count,
            "bars_inserted": run.bars_inserted,
            "bars_updated": run.bars_updated,
            "error_message": run.error_message,
        }
        for run in runs
    ]
