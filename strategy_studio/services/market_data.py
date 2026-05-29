from __future__ import annotations

"""行情导入、统计与读取服务。"""

from strategy_studio.db.session import open_session
from strategy_studio.repositories.market_data import (
    get_ingestion_job_detail,
    get_market_data_stats,
    list_provider_series,
    list_instrument_coverages,
    list_instruments,
    list_price_bars,
    list_sync_runs,
)


def fetch_market_data_stats() -> dict[str, object]:
    with open_session() as session:
        return get_market_data_stats(session)


def fetch_provider_series(provider_key: str | None = None, limit: int = 100) -> list[dict[str, object]]:
    with open_session() as session:
        return list_provider_series(session, provider_key=provider_key, limit=limit)


def fetch_ingestion_job_detail(job_id: int) -> dict[str, object] | None:
    with open_session() as session:
        return get_ingestion_job_detail(session, job_id)


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
