from __future__ import annotations

"""Yahoo 同步服务。"""

from datetime import UTC, datetime

import pandas as pd

from strategy_studio.data.yahoo import DEFAULT_DAILY_PERIOD, download_price_bars, is_intraday_interval
from strategy_studio.db.session import open_session
from strategy_studio.symbols import resolve_symbol_spec
from strategy_studio.repositories.market_data import (
    create_sync_run,
    create_sync_run_item,
    get_or_create_instrument,
    list_instruments,
    upsert_price_frame,
)


def sync_market_data(
    symbol: str | None,
    interval: str,
    proxy: str | None,
    period: str | None = None,
) -> dict[str, object]:
    """同步单标的或全部已知标的的指定周期行情。"""
    with open_session() as session:
        if symbol:
            symbols = [symbol.strip().upper()]
        else:
            symbols = [str(item["symbol"]) for item in list_instruments(session)]
        if not symbols:
            raise ValueError("当前数据库中没有可同步的标的，请先在数据库中创建标的或显式传入 --symbol。")

        run = create_sync_run(session, job_type="manual" if symbol else "scheduled", interval=interval)
        run.symbols_count = len(symbols)
        session.commit()

        total_inserted = 0
        total_updated = 0
        for current_symbol in symbols:
            item = create_sync_run_item(session, run, current_symbol)
            session.commit()
            try:
                spec = resolve_symbol_spec(current_symbol)
                effective_period = period
                if is_intraday_interval(interval) and not effective_period:
                    effective_period = "7d" if interval == "1m" else "60d"
                bars = download_price_bars(
                    symbol=current_symbol,
                    interval=interval,
                    period=effective_period if is_intraday_interval(interval) else None,
                    proxy=proxy,
                )
                instrument = get_or_create_instrument(session, symbol=current_symbol, name=spec.name)
                inserted, updated = upsert_price_frame(
                    session,
                    instrument=instrument,
                    interval=interval,
                    frame=bars,
                    source="yahoo",
                )
                item.status = "succeeded"
                item.bars_inserted = inserted
                item.bars_updated = updated
                total_inserted += inserted
                total_updated += updated
                session.commit()
            except Exception as exc:
                session.rollback()
                item = session.get(type(item), item.id)
                if item is not None:
                    item.status = "failed"
                    item.error_message = str(exc)
                    session.commit()

        run = session.get(type(run), run.id)
        if run is None:
            raise RuntimeError("同步任务记录丢失。")
        run.completed_at = datetime.now(UTC)
        run.bars_inserted = total_inserted
        run.bars_updated = total_updated
        run.status = "succeeded" if total_inserted or total_updated else "completed"
        session.commit()

        return {
            "run_id": run.id,
            "interval": interval,
            "symbols_count": len(symbols),
            "bars_inserted": total_inserted,
            "bars_updated": total_updated,
            "status": run.status,
        }
