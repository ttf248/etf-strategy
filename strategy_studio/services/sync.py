from __future__ import annotations

"""Yahoo 同步服务。"""

from datetime import UTC, datetime

import pandas as pd

from strategy_studio.data.yahoo import DEFAULT_DAILY_PERIOD, download_price_bars, is_intraday_interval
from strategy_studio.db.session import open_session
from strategy_studio.symbols import resolve_symbol_spec
from strategy_studio.repositories.market_data import (
    create_data_ingestion_job,
    create_data_ingestion_job_item,
    create_sync_run,
    create_sync_run_item,
    ensure_data_provider,
    get_or_create_instrument,
    get_or_create_instrument_alias,
    get_or_create_market_data_series,
    list_instruments,
    upsert_market_data_frame,
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
        provider = ensure_data_provider(
            session,
            provider_key="yahoo",
            provider_name="Yahoo Finance",
            provider_type="market_data",
            transport="api",
            timezone="UTC",
            config_json={"supports_intervals": ["1d", "15m", "1m"]},
            status="active",
        )
        if symbol:
            symbols = [symbol.strip().upper()]
        else:
            symbols = [str(item["symbol"]) for item in list_instruments(session)]
        if not symbols:
            raise ValueError("当前数据库中没有可同步的标的，请先在数据库中创建标的或显式传入 --symbol。")

        run = create_sync_run(session, job_type="manual" if symbol else "scheduled", interval=interval)
        run.symbols_count = len(symbols)
        ingestion_job = create_data_ingestion_job(
            session,
            provider=provider,
            job_type="yahoo_sync",
            requested_via="manual" if symbol else "scheduler",
            target_scope_json={"symbols": symbols, "interval": interval},
            options_json={"proxy_configured": bool(proxy), "period": period or ""},
        )
        ingestion_job.targets_total = len(symbols)
        session.commit()

        total_inserted = 0
        total_updated = 0
        total_series_inserted = 0
        total_series_updated = 0
        failed_symbols = 0
        for current_symbol in symbols:
            item = create_sync_run_item(session, run, current_symbol)
            ingestion_item = create_data_ingestion_job_item(
                session,
                ingestion_job,
                item_key=f"{current_symbol}:{interval}:raw",
                source_symbol=current_symbol,
                interval=interval,
                provider=provider,
            )
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
                alias = get_or_create_instrument_alias(
                    session,
                    instrument=instrument,
                    provider=provider,
                    source_symbol=current_symbol,
                    source_name=spec.name,
                    market=instrument.exchange,
                    exchange=instrument.exchange,
                    security_type=instrument.asset_type,
                    timezone=instrument.timezone,
                )
                series = get_or_create_market_data_series(
                    session,
                    instrument=instrument,
                    provider=provider,
                    alias=alias,
                    interval=interval,
                    market=instrument.exchange,
                    exchange=instrument.exchange,
                    adjustment_kind="raw",
                    session_type="regular",
                    price_type="trade",
                    bar_type="time",
                    timezone=instrument.timezone,
                )
                inserted, updated = upsert_price_frame(
                    session,
                    instrument=instrument,
                    interval=interval,
                    frame=bars,
                    source="yahoo",
                )
                series_inserted, series_updated = upsert_market_data_frame(session, series=series, frame=bars)
                item.status = "succeeded"
                item.bars_inserted = inserted
                item.bars_updated = updated
                ingestion_item.status = "succeeded"
                ingestion_item.stage = "completed"
                ingestion_item.instrument_id = instrument.id
                ingestion_item.series_id = series.id
                ingestion_item.rows_inserted = series_inserted
                ingestion_item.rows_updated = series_updated
                ingestion_item.details_json = {
                    "provider_key": provider.provider_key,
                    "legacy_price_bar_inserted": inserted,
                    "legacy_price_bar_updated": updated,
                    "series_inserted": series_inserted,
                    "series_updated": series_updated,
                }
                total_inserted += inserted
                total_updated += updated
                total_series_inserted += series_inserted
                total_series_updated += series_updated
                session.commit()
            except Exception as exc:
                session.rollback()
                item = session.get(type(item), item.id)
                ingestion_item = session.get(type(ingestion_item), ingestion_item.id)
                if item is not None:
                    item.status = "failed"
                    item.error_message = str(exc)
                if ingestion_item is not None:
                    ingestion_item.status = "failed"
                    ingestion_item.stage = "failed"
                    ingestion_item.error_message = str(exc)
                failed_symbols += 1
                session.commit()

        run = session.get(type(run), run.id)
        ingestion_job = session.get(type(ingestion_job), ingestion_job.id)
        if run is None:
            raise RuntimeError("同步任务记录丢失。")
        if ingestion_job is None:
            raise RuntimeError("统一导入任务记录丢失。")
        run.completed_at = datetime.now(UTC)
        run.bars_inserted = total_inserted
        run.bars_updated = total_updated
        if failed_symbols == len(symbols):
            run.status = "failed"
        elif failed_symbols:
            run.status = "partially_failed"
        else:
            run.status = "succeeded" if total_inserted or total_updated else "completed"

        ingestion_job.targets_completed = len(symbols) - failed_symbols
        ingestion_job.rows_inserted = total_series_inserted
        ingestion_job.rows_updated = total_series_updated
        ingestion_job.error_count = failed_symbols
        ingestion_job.summary_json = {
            "legacy_price_bars": {"inserted": total_inserted, "updated": total_updated},
            "market_data_bars": {"inserted": total_series_inserted, "updated": total_series_updated},
            "symbols_total": len(symbols),
            "symbols_failed": failed_symbols,
        }
        ingestion_job.completed_at = datetime.now(UTC)
        if failed_symbols == len(symbols):
            ingestion_job.status = "failed"
            ingestion_job.error_message = "本次 Yahoo 同步全部失败。"
        elif failed_symbols:
            ingestion_job.status = "partially_failed"
            ingestion_job.error_message = f"本次 Yahoo 同步有 {failed_symbols} 个标的失败。"
        else:
            ingestion_job.status = "succeeded" if total_series_inserted or total_series_updated else "completed"
        session.commit()

        return {
            "run_id": run.id,
            "ingestion_job_id": ingestion_job.id,
            "interval": interval,
            "symbols_count": len(symbols),
            "bars_inserted": total_inserted,
            "bars_updated": total_updated,
            "series_bars_inserted": total_series_inserted,
            "series_bars_updated": total_series_updated,
            "status": run.status,
        }
