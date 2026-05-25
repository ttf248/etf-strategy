from __future__ import annotations

"""行情导入、统计与读取服务。"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from etf_strategy.data.market_rules import DATA_INTERVAL_SUFFIXES, infer_symbol_from_data_path
from etf_strategy.db.session import open_session
from etf_strategy.repositories.market_data import (
    get_market_data_stats,
    get_instrument_by_symbol,
    get_or_create_instrument,
    list_instrument_coverages,
    list_instruments,
    list_price_bars,
    list_sync_runs,
    upsert_price_frame,
)
from etf_strategy.reporting import resolve_symbol_spec


@dataclass(frozen=True)
class CsvImportResult:
    files_scanned: int
    instruments_created: int
    bars_inserted: int
    bars_updated: int
    failed_files: list[str]


def infer_interval_from_data_path(data_path: str | Path) -> str | None:
    stem = Path(data_path).stem
    parts = stem.split("_")
    if not parts:
        return None
    candidate = parts[-1].lower()
    if candidate in DATA_INTERVAL_SUFFIXES:
        return "1d" if candidate == "daily" else candidate
    return None


def load_standard_csv_frame(csv_path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path, encoding="utf-8-sig")
    required_columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"CSV 缺少字段: {missing_columns}")
    frame = frame.loc[:, required_columns].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame


def import_csv_directory(source_dir: str | Path) -> CsvImportResult:
    source_path = Path(source_dir)
    csv_files = [path for path in sorted(source_path.glob("*.csv")) if not path.name.endswith("_test.csv") and "test" not in path.stem.lower()]
    instruments_created = 0
    bars_inserted = 0
    bars_updated = 0
    failed_files: list[str] = []

    with open_session() as session:
        for csv_path in csv_files:
            try:
                symbol = infer_symbol_from_data_path(csv_path)
                interval = infer_interval_from_data_path(csv_path)
                if not symbol or not interval:
                    raise ValueError("无法从文件名解析 symbol 或 interval。")
                frame = load_standard_csv_frame(csv_path)
                spec = resolve_symbol_spec(symbol)
                existing_instrument = get_instrument_by_symbol(session, symbol)
                instrument = get_or_create_instrument(session, symbol=symbol, name=spec.name)
                if existing_instrument is None:
                    instruments_created += 1
                inserted, updated = upsert_price_frame(session, instrument=instrument, interval=interval, frame=frame, source="csv_import")
                bars_inserted += inserted
                bars_updated += updated
                session.commit()
            except Exception as exc:
                session.rollback()
                failed_files.append(f"{csv_path.name}: {exc}")

    return CsvImportResult(
        files_scanned=len(csv_files),
        instruments_created=instruments_created,
        bars_inserted=bars_inserted,
        bars_updated=bars_updated,
        failed_files=failed_files,
    )


def fetch_market_data_stats() -> dict[str, object]:
    with open_session() as session:
        return get_market_data_stats(session)


def fetch_instrument_coverages() -> list[dict[str, object]]:
    with open_session() as session:
        return list_instrument_coverages(session)


def fetch_instruments() -> list[dict[str, object]]:
    with open_session() as session:
        return list_instruments(session)


def fetch_sync_runs(limit: int = 50) -> list[dict[str, object]]:
    with open_session() as session:
        return list_sync_runs(session, limit=limit)


def fetch_price_bars(
    symbol: str,
    interval: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = 2000,
) -> list[dict[str, object]]:
    with open_session() as session:
        return list_price_bars(session, symbol=symbol, interval=interval, start=start, end=end, limit=limit)
