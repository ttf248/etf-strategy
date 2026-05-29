from __future__ import annotations

"""行情同步与原始导入服务。"""

from datetime import UTC, datetime
from pathlib import Path
import re

import pandas as pd

from strategy_studio.data.tdx import (
    DAY_RECORD_SIZE,
    build_day_file_signature,
    detect_security_type,
    iter_tdx_day_files,
    manifest_can_append,
    manifest_is_unchanged,
    normalize_day_frame,
    read_day_frame,
    read_day_frame_tail,
    security_type_to_asset_type,
)
from strategy_studio.data.yahoo import download_price_bars, is_intraday_interval
from strategy_studio.db.session import open_session
from strategy_studio.db.settings import load_platform_settings
from strategy_studio.repositories.market_data import (
    create_data_ingestion_job,
    create_data_ingestion_job_item,
    create_sync_run,
    create_sync_run_item,
    ensure_data_provider,
    get_or_create_instrument,
    get_or_create_instrument_alias,
    get_or_create_market_data_series,
    get_source_file_manifest,
    list_instruments,
    upsert_market_data_frame,
    upsert_price_frame,
    upsert_source_file_manifest,
)
from strategy_studio.symbols import resolve_symbol_spec


def sync_market_data(
    symbol: str | None,
    interval: str,
    proxy: str | None,
    period: str | None = None,
    *,
    provider: str = "yahoo",
    vipdoc_path: str | None = None,
    force: bool = False,
    limit: int | None = None,
) -> dict[str, object]:
    """按 provider 分发行情同步。

    - `yahoo`：下载 Yahoo 行情，兼容旧 `price_bars` 并同步写入新主干表。
    - `tdx`：导入通达信原始 `.day` 日线，写入统一序列表与文件 manifest。
    """
    normalized_provider = provider.strip().lower()
    if normalized_provider == "yahoo":
        return _sync_yahoo_market_data(symbol=symbol, interval=interval, proxy=proxy, period=period)
    if normalized_provider == "tdx":
        return _sync_tdx_market_data(
            symbol=symbol,
            interval=interval,
            vipdoc_path=vipdoc_path,
            force=force,
            limit=limit,
        )
    raise ValueError(f"不支持的数据渠道：{provider}")


def _sync_yahoo_market_data(
    *,
    symbol: str | None,
    interval: str,
    proxy: str | None,
    period: str | None,
) -> dict[str, object]:
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
            "provider": provider.provider_key,
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


def _sync_tdx_market_data(
    *,
    symbol: str | None,
    interval: str,
    vipdoc_path: str | None,
    force: bool,
    limit: int | None,
) -> dict[str, object]:
    if interval != "1d":
        raise ValueError("当前通达信导入只支持 1d 原始日线。")
    vipdoc = _resolve_tdx_vipdoc_path(vipdoc_path)
    if not vipdoc.exists():
        raise FileNotFoundError(f"通达信 vipdoc 目录不存在：{vipdoc}")

    source_files = iter_tdx_day_files(vipdoc, symbol=symbol, limit=limit)
    if not source_files:
        raise ValueError(f"在 vipdoc 中没有找到可导入的 .day 文件：vipdoc={vipdoc} symbol={symbol or 'ALL'}")

    with open_session() as session:
        provider = ensure_data_provider(
            session,
            provider_key="tdx",
            provider_name="通达信本地行情",
            provider_type="market_data",
            transport="filesystem",
            timezone="Asia/Shanghai",
            config_json={"supports_intervals": ["1d"], "vipdoc_path": str(vipdoc)},
            status="active",
        )
        ingestion_job = create_data_ingestion_job(
            session,
            provider=provider,
            job_type="tdx_raw_import",
            requested_via="manual",
            target_scope_json={
                "symbol": (symbol or "").strip().lower(),
                "interval": interval,
                "vipdoc_path": str(vipdoc),
            },
            options_json={"force": force, "limit": limit or 0},
        )
        ingestion_job.targets_total = len(source_files)
        session.commit()

        imported_files = 0
        skipped_files = 0
        failed_files = 0
        rows_inserted = 0
        rows_updated = 0
        for source_file in source_files:
            relative_path = source_file.relative_to(vipdoc).as_posix()
            item = create_data_ingestion_job_item(
                session,
                ingestion_job,
                item_key=f"{relative_path}:{interval}:raw",
                source_symbol=source_file.stem.upper(),
                interval=interval,
                provider=provider,
            )
            session.commit()
            try:
                signature = build_day_file_signature(source_file)
                previous = get_source_file_manifest(session, provider, relative_path)
                if not force and manifest_is_unchanged(previous, signature):
                    item.status = "skipped"
                    item.stage = "completed"
                    item.details_json = {
                        "provider_key": provider.provider_key,
                        "mode": "skip",
                        "reason": "manifest_unchanged",
                    }
                    ingestion_job.targets_completed += 1
                    skipped_files += 1
                    session.commit()
                    continue

                security = detect_security_type(source_file, vipdoc)
                if not force and manifest_can_append(previous, signature, source_file):
                    previous_rows = int(previous.record_count if previous is not None else 0)
                    overlap_start = max(previous_rows - 5, 0)
                    start_offset = overlap_start * DAY_RECORD_SIZE
                    raw_frame = read_day_frame_tail(source_file, start_offset, vipdoc)
                    mode = "append"
                else:
                    raw_frame = read_day_frame(source_file, vipdoc)
                    mode = "rebuild"
                normalized = normalize_day_frame(raw_frame, source_file, vipdoc)
                if previous is not None and previous.last_bar_time is not None and mode == "append":
                    cutoff = str(previous.last_bar_time)[:10]
                    normalized = normalized[normalized["datetime"] >= cutoff]
                    normalized = normalized.drop_duplicates(subset=["datetime"], keep="last").reset_index(drop=True)
                if normalized.empty and mode == "append":
                    item.status = "skipped"
                    item.stage = "completed"
                    item.details_json = {
                        "provider_key": provider.provider_key,
                        "mode": mode,
                        "reason": "append_window_empty",
                    }
                    upsert_source_file_manifest(
                        session,
                        provider,
                        source_path=relative_path,
                        file_kind="tdx_day",
                        market=security.market.upper(),
                        interval=interval,
                        source_size=int(signature["source_size"]),
                        source_mtime=float(signature["source_mtime"]),
                        record_count=int(signature["record_count"]),
                        tail_hash=str(signature["tail_hash"] or ""),
                        status="success",
                        last_bar_time=previous.last_bar_time if previous is not None else None,
                        payload_json={"mode": mode, "security_type": security.security_type},
                    )
                    ingestion_job.targets_completed += 1
                    skipped_files += 1
                    session.commit()
                    continue

                instrument_symbol = source_file.stem.upper()
                instrument = get_or_create_instrument(
                    session,
                    symbol=instrument_symbol,
                    name=instrument_symbol,
                    asset_type=security_type_to_asset_type(security),
                    timezone="Asia/Shanghai",
                )
                instrument.exchange = security.market.upper()
                alias = get_or_create_instrument_alias(
                    session,
                    instrument=instrument,
                    provider=provider,
                    source_symbol=instrument_symbol,
                    source_name=instrument_symbol,
                    market=security.market.upper(),
                    exchange=security.market.upper(),
                    security_type=security.security_type.lower(),
                    timezone="Asia/Shanghai",
                )
                series = get_or_create_market_data_series(
                    session,
                    instrument=instrument,
                    provider=provider,
                    alias=alias,
                    interval=interval,
                    market=security.market.upper(),
                    exchange=security.market.upper(),
                    adjustment_kind="raw",
                    session_type="regular",
                    price_type="trade",
                    bar_type="time",
                    timezone="Asia/Shanghai",
                )
                frame_for_upsert = normalized.rename(
                    columns={
                        "datetime": "Date",
                        "open": "Open",
                        "high": "High",
                        "low": "Low",
                        "close": "Close",
                        "volume": "Volume",
                        "amount": "Amount",
                    }
                )[["Date", "Open", "High", "Low", "Close", "Volume", "Amount"]]
                inserted, updated = upsert_market_data_frame(session, series=series, frame=frame_for_upsert)
                upsert_source_file_manifest(
                    session,
                    provider,
                    source_path=relative_path,
                    file_kind="tdx_day",
                    market=security.market.upper(),
                    interval=interval,
                    source_size=int(signature["source_size"]),
                    source_mtime=float(signature["source_mtime"]),
                    record_count=int(signature["record_count"]),
                    tail_hash=str(signature["tail_hash"] or ""),
                    status="success",
                    last_bar_time=normalized["datetime"].iloc[-1] if not normalized.empty else None,
                    instrument_id=instrument.id,
                    series_id=series.id,
                    payload_json={
                        "mode": mode,
                        "security_type": security.security_type,
                        "price_scale": security.price_scale,
                        "volume_scale": security.volume_scale,
                    },
                )
                item.status = "succeeded"
                item.stage = "completed"
                item.instrument_id = instrument.id
                item.series_id = series.id
                item.rows_inserted = inserted
                item.rows_updated = updated
                item.details_json = {
                    "provider_key": provider.provider_key,
                    "mode": mode,
                    "source_path": relative_path,
                    "record_count": int(signature["record_count"]),
                    "security_type": security.security_type,
                }
                ingestion_job.targets_completed += 1
                imported_files += 1
                rows_inserted += inserted
                rows_updated += updated
                session.commit()
            except Exception as exc:
                session.rollback()
                item = session.get(type(item), item.id)
                ingestion_job = session.get(type(ingestion_job), ingestion_job.id)
                if item is not None:
                    item.status = "failed"
                    item.stage = "failed"
                    item.error_message = str(exc)
                    item.details_json = {"provider_key": provider.provider_key, "source_path": relative_path}
                if ingestion_job is not None:
                    ingestion_job.error_count += 1
                failed_files += 1
                session.commit()

        ingestion_job = session.get(type(ingestion_job), ingestion_job.id)
        if ingestion_job is None:
            raise RuntimeError("统一导入任务记录丢失。")
        ingestion_job.rows_inserted = rows_inserted
        ingestion_job.rows_updated = rows_updated
        ingestion_job.completed_at = datetime.now(UTC)
        ingestion_job.summary_json = {
            "provider_key": provider.provider_key,
            "vipdoc_path": str(vipdoc),
            "files_total": len(source_files),
            "files_imported": imported_files,
            "files_skipped": skipped_files,
            "files_failed": failed_files,
        }
        if failed_files == len(source_files):
            ingestion_job.status = "failed"
            ingestion_job.error_message = "本次通达信原始日线导入全部失败。"
        elif failed_files:
            ingestion_job.status = "partially_failed"
            ingestion_job.error_message = f"本次通达信原始日线导入有 {failed_files} 个文件失败。"
        else:
            ingestion_job.status = "succeeded"
        session.commit()

        return {
            "provider": provider.provider_key,
            "ingestion_job_id": ingestion_job.id,
            "interval": interval,
            "symbols_count": len(source_files),
            "bars_inserted": rows_inserted,
            "bars_updated": rows_updated,
            "series_bars_inserted": rows_inserted,
            "series_bars_updated": rows_updated,
            "files_imported": imported_files,
            "files_skipped": skipped_files,
            "files_failed": failed_files,
            "status": ingestion_job.status,
            "vipdoc_path": str(vipdoc),
        }


def _resolve_tdx_vipdoc_path(override_path: str | None) -> Path:
    settings = load_platform_settings()
    if override_path and override_path.strip():
        return Path(override_path.strip()).expanduser().resolve()
    if settings.tdx_vipdoc.strip():
        return Path(settings.tdx_vipdoc.strip()).expanduser().resolve()
    config_path = Path(settings.tdx_config_path).expanduser()
    if config_path.exists():
        content = config_path.read_text(encoding="utf-8")
        match = re.search(r"(?m)^vipdoc:\s*(.+?)\s*$", content)
        if match:
            value = match.group(1).strip().strip("'\"")
            if value:
                return Path(value).expanduser().resolve()
    raise ValueError(
        "未配置通达信 vipdoc 路径。请通过 --vipdoc、STRATEGY_STUDIO_TDX_VIPDOC，"
        "或在 STRATEGY_STUDIO_TDX_CONFIG_PATH 指向的配置文件中提供 vipdoc。"
    )
