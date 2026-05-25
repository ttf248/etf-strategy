from __future__ import annotations

"""行情仓储。"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

import pandas as pd
from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from etf_strategy.db.models import DataSyncRun, DataSyncRunItem, Instrument, PriceBar


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
