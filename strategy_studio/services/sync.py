from __future__ import annotations

"""行情同步与原始导入服务。"""

from collections import defaultdict
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
import re
from time import perf_counter

import pandas as pd
from sqlalchemy import func, select

from strategy_studio.data.qfq import apply_qfq_segment_frame, build_qfq_segment_frame
from strategy_studio.data.tdx import (
    OVERLAP_ROWS,
    build_tdx_file_signature,
    detect_security_type,
    file_kind_for_interval,
    interval_to_period,
    iter_tdx_files,
    manifest_can_append,
    manifest_is_unchanged,
    normalize_day_frame,
    normalize_minute_frame,
    read_day_frame,
    read_day_frame_tail,
    read_minute_frame,
    read_minute_frame_tail,
    security_type_to_asset_type,
    suffixes_for_interval,
)
from strategy_studio.data.tushare import (
    DIVIDEND_FIELDS,
    build_corporate_action_records,
    fetch_stock_basic,
    load_tushare_client_settings,
    symbol_to_ts_code,
    ts_code_to_instrument_symbol,
    ts_code_to_market,
    TushareClient,
)
from strategy_studio.data.yahoo import download_price_bars, is_intraday_interval
from strategy_studio.db.models import CorporateActionEvent, DataIngestionJob, Instrument, InstrumentAlias, MarketDataBar, MarketDataSeries
from strategy_studio.db.session import open_session
from strategy_studio.db.settings import load_platform_settings
from strategy_studio.repositories.market_data import (
    claim_next_queued_ingestion_job,
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
    replace_price_adjustment_segments,
    replace_corporate_action_events_for_symbol,
    upsert_market_data_frame,
    upsert_price_frame,
    upsert_source_file_manifest,
)
from strategy_studio.symbols import SymbolSpec, get_symbol_set, resolve_symbol_spec

TDX_IMPORT_INTERVALS = ("1d", "1m", "5m")
TDX_PIPELINE_INTERVALS = ("1d", "all")
TDX_QFQ_COMMIT_EVERY = 20
API_REQUESTED_VIA = "api"
WORKER_CHILD_REQUESTED_VIA = "worker_child"
_ACTIVE_ENQUEUED_MARKET_DATA_JOB_ID: ContextVar[int | None] = ContextVar(
    "active_enqueued_market_data_job_id",
    default=None,
)

_QUEUE_PROVIDER_DEFINITIONS: dict[str, dict[str, object]] = {
    "yahoo": {
        "provider_name": "Yahoo Finance",
        "provider_type": "market_data",
        "transport": "api",
        "timezone": "UTC",
        "config_json": {"supports_intervals": ["1d", "15m", "1m"]},
    },
    "tdx": {
        "provider_name": "通达信本地行情",
        "provider_type": "market_data",
        "transport": "filesystem",
        "timezone": "Asia/Shanghai",
        "config_json": {"supports_intervals": ["1d", "1m", "5m", "all"]},
    },
    "tushare": {
        "provider_name": "Tushare 公司行动",
        "provider_type": "corporate_action",
        "transport": "api",
        "timezone": "Asia/Shanghai",
        "config_json": {"supports_actions": ["dividend"]},
    },
    "tdx_qfq": {
        "provider_name": "通达信前复权日线",
        "provider_type": "derived_market_data",
        "transport": "database",
        "timezone": "Asia/Shanghai",
        "config_json": {"supports_intervals": ["1d"], "adjustment_kind": "qfq"},
    },
    "tdx_pipeline": {
        "provider_name": "A 股统一补数链路",
        "provider_type": "workflow",
        "transport": "orchestration",
        "timezone": "Asia/Shanghai",
        "config_json": {"supports_intervals": ["1d", "all"], "pipeline_steps": ["tdx", "tushare", "tdx_qfq"]},
    },
}


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
    symbol_set: str | None = None,
    requested_via: str | None = None,
) -> dict[str, object]:
    """按 provider 分发行情同步。

    - `yahoo`：下载 Yahoo 行情，兼容旧 `price_bars` 并同步写入新主干表。
    - `tdx`：导入通达信原始 `1d / 1m / 5m` 文件，写入统一序列表与文件 manifest。
    - `tushare`：抓取 Tushare dividend 实施事件，写入 `corporate_action_events`。
    - `tdx_qfq`：基于通达信原始日线和 Tushare 公司行动重建前复权日线。
    - `tdx_pipeline`：串行执行 A 股原始导入、公司行动抓取和前复权重算。
    """
    normalized_provider = provider.strip().lower()
    if normalized_provider == "yahoo":
        return _sync_yahoo_market_data(
            symbol=symbol,
            interval=interval,
            proxy=proxy,
            period=period,
            limit=limit,
            symbol_set=symbol_set,
            requested_via=requested_via,
        )
    if normalized_provider == "tdx":
        return _sync_tdx_market_data(
            symbol=symbol,
            interval=interval,
            vipdoc_path=vipdoc_path,
            force=force,
            limit=limit,
            requested_via=requested_via,
        )
    if normalized_provider == "tushare":
        return _sync_tushare_corporate_actions(symbol=symbol, limit=limit, force=force, requested_via=requested_via)
    if normalized_provider == "tdx_qfq":
        return _rebuild_tdx_qfq_market_data(
            symbol=symbol,
            interval=interval,
            force=force,
            limit=limit,
            requested_via=requested_via,
        )
    if normalized_provider == "tdx_pipeline":
        return _run_tdx_pipeline_workflow(
            symbol=symbol,
            interval=interval,
            vipdoc_path=vipdoc_path,
            force=force,
            limit=limit,
            requested_via=requested_via,
        )
    raise ValueError(f"不支持的数据渠道：{provider}")


def enqueue_market_data_sync(
    *,
    symbol: str | None,
    symbol_set: str | None,
    interval: str,
    proxy: str | None,
    period: str | None,
    provider: str = "yahoo",
    vipdoc_path: str | None = None,
    force: bool = False,
    limit: int | None = None,
) -> dict[str, object]:
    normalized_provider = provider.strip().lower()
    if normalized_provider not in _QUEUE_PROVIDER_DEFINITIONS:
        raise ValueError(f"不支持的数据渠道：{provider}")

    provider_definition = _QUEUE_PROVIDER_DEFINITIONS[normalized_provider]
    requested_symbol = (symbol or "").strip()
    normalized_interval = (interval or "1d").strip().lower() or "1d"
    target_scope_json = {
        "provider": normalized_provider,
        "symbol": requested_symbol,
        "symbol_set": (symbol_set or "").strip(),
        "interval": normalized_interval,
        "proxy": (proxy or "").strip(),
        "period": (period or "").strip(),
        "vipdoc_path": (vipdoc_path or "").strip(),
    }
    options_json = {
        "force": force,
        "limit": int(limit or 0),
    }

    with open_session() as session:
        provider_row = ensure_data_provider(
            session,
            provider_key=normalized_provider,
            provider_name=str(provider_definition["provider_name"]),
            provider_type=str(provider_definition["provider_type"]),
            transport=str(provider_definition["transport"]),
            timezone=str(provider_definition["timezone"]),
            config_json=dict(provider_definition.get("config_json") or {}),
            status="active",
        )
        ingestion_job = create_data_ingestion_job(
            session,
            provider=provider_row,
            job_type=f"{normalized_provider}_request",
            requested_via=API_REQUESTED_VIA,
            target_scope_json=target_scope_json,
            options_json=options_json,
            initial_status="queued",
        )
        ingestion_job.targets_total = 1
        ingestion_job.summary_json = {
            "queued_request": True,
            "requested_provider": normalized_provider,
            "requested_symbol": requested_symbol,
            "requested_interval": normalized_interval,
            "requested_symbol_set": target_scope_json["symbol_set"],
        }
        session.commit()
        return {
            "provider": normalized_provider,
            "ingestion_job_id": ingestion_job.id,
            "status": "queued",
            "target_symbol": requested_symbol,
            "interval": normalized_interval,
            "requested_via": API_REQUESTED_VIA,
        }


def retry_market_data_ingestion_job(job_id: int) -> dict[str, object]:
    with open_session() as session:
        job = session.get(DataIngestionJob, job_id)
        if job is None or job.requested_via != API_REQUESTED_VIA:
            return {"job_id": job_id, "status": "not_found", "changed": False}
        if job.status not in {"failed", "partially_failed", "cancelled"}:
            return {"job_id": job_id, "status": job.status, "changed": False}

        previous_status = job.status
        retry_count = int(dict(job.summary_json or {}).get("retry_count") or 0) + 1
        job.status = "queued"
        job.started_at = None
        job.completed_at = None
        job.targets_completed = 0
        job.rows_inserted = 0
        job.rows_updated = 0
        job.error_count = 0
        job.error_message = ""
        job.summary_json = {
            **dict(job.summary_json or {}),
            "retry_count": retry_count,
            "last_terminal_status": previous_status,
            "worker_stage": "queued",
        }
        session.commit()
        return {"job_id": job_id, "status": "queued", "changed": True}


def cancel_market_data_ingestion_job(job_id: int) -> dict[str, object]:
    with open_session() as session:
        job = session.get(DataIngestionJob, job_id)
        if job is None or job.requested_via != API_REQUESTED_VIA:
            return {"job_id": job_id, "status": "not_found", "changed": False}
        if job.status == "queued":
            job.status = "cancelled"
            job.completed_at = datetime.now(UTC)
            job.error_message = "任务已取消，未进入执行。"
            job.summary_json = {
                **dict(job.summary_json or {}),
                "worker_stage": "cancelled",
            }
            session.commit()
            return {"job_id": job_id, "status": "cancelled", "changed": True}
        if job.status == "running":
            job.status = "cancel_requested"
            job.error_message = "已经收到取消请求，当前任务会在安全检查点尽快停止。"
            job.summary_json = {
                **dict(job.summary_json or {}),
                "worker_stage": "cancel_requested",
            }
            session.commit()
            return {"job_id": job_id, "status": "cancel_requested", "changed": True}
        return {"job_id": job_id, "status": job.status, "changed": False}


def _current_enqueued_market_data_job_id() -> int | None:
    return _ACTIVE_ENQUEUED_MARKET_DATA_JOB_ID.get()


def _is_current_enqueued_market_data_job_cancel_requested() -> bool:
    job_id = _current_enqueued_market_data_job_id()
    if job_id is None:
        return False
    with open_session() as session:
        job = session.get(DataIngestionJob, job_id)
        if job is None:
            return False
        return job.status in {"cancel_requested", "cancelled"}


def _current_enqueued_market_data_job_cancel_message() -> str:
    job_id = _current_enqueued_market_data_job_id()
    if job_id is None:
        return "任务已取消。"
    return f"统一导入任务 #{job_id} 已请求取消，剩余目标不再继续执行。"


def execute_next_market_data_job(worker_name: str | None = None) -> int | None:
    with open_session() as session:
        job = claim_next_queued_ingestion_job(session, requested_via=API_REQUESTED_VIA)
        if job is None:
            return None
        job_id = job.id
        target_scope_json = dict(job.target_scope_json or {})
        options_json = dict(job.options_json or {})
        job.summary_json = {
            **dict(job.summary_json or {}),
            "worker_name": worker_name or "",
            "worker_stage": "running",
        }
        session.commit()

    token = _ACTIVE_ENQUEUED_MARKET_DATA_JOB_ID.set(job_id)
    try:
        try:
            result = sync_market_data(
                symbol=str(target_scope_json.get("symbol") or "") or None,
                symbol_set=str(target_scope_json.get("symbol_set") or "") or None,
                interval=str(target_scope_json.get("interval") or "1d"),
                proxy=str(target_scope_json.get("proxy") or "") or None,
                period=str(target_scope_json.get("period") or "") or None,
                provider=str(target_scope_json.get("provider") or "yahoo"),
                vipdoc_path=str(target_scope_json.get("vipdoc_path") or "") or None,
                force=bool(options_json.get("force")),
                limit=int(options_json.get("limit") or 0) or None,
                requested_via=WORKER_CHILD_REQUESTED_VIA,
            )
        except Exception as exc:
            _finalize_enqueued_market_data_job_failure(job_id, str(exc), worker_name=worker_name)
            return job_id

        _finalize_enqueued_market_data_job_success(job_id, result, worker_name=worker_name)
        return job_id
    finally:
        _ACTIVE_ENQUEUED_MARKET_DATA_JOB_ID.reset(token)


def _normalize_summary_value(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _normalize_summary_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_summary_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_summary_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat(sep=" ")
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if hasattr(value, "item"):
        return value.item()
    return value


def _finalize_enqueued_market_data_job_success(
    job_id: int,
    result: dict[str, object],
    *,
    worker_name: str | None = None,
) -> None:
    child_ingestion_job_ids = _collect_child_ingestion_job_ids(result)
    normalized_summary = _normalize_summary_value(result)
    with open_session() as session:
        job = session.get(DataIngestionJob, job_id)
        if job is None:
            return
        normalized_status = str(result.get("status") or "completed")
        job.status = normalized_status
        job.targets_total = 1
        job.targets_completed = 1
        job.rows_inserted = int(result.get("series_bars_inserted") or result.get("bars_inserted") or 0)
        job.rows_updated = int(result.get("series_bars_updated") or result.get("bars_updated") or 0)
        job.error_count = 0 if normalized_status in {"succeeded", "completed", "skipped", "cancelled"} else max(1, int(job.error_count or 0))
        job.error_message = str(result.get("error_message") or "")
        job.completed_at = datetime.now(UTC)
        job.summary_json = {
            **dict(job.summary_json or {}),
            **dict(normalized_summary if isinstance(normalized_summary, dict) else {}),
            "child_ingestion_job_ids": child_ingestion_job_ids,
            "ingestion_job_ids": child_ingestion_job_ids,
            "worker_name": worker_name or "",
            "worker_stage": "completed",
        }
        session.commit()


def _finalize_enqueued_market_data_job_failure(job_id: int, error_message: str, *, worker_name: str | None = None) -> None:
    with open_session() as session:
        job = session.get(DataIngestionJob, job_id)
        if job is None:
            return
        job.status = "failed"
        job.targets_total = 1
        job.targets_completed = 1
        job.error_count = max(1, int(job.error_count or 0))
        job.error_message = error_message
        job.completed_at = datetime.now(UTC)
        job.summary_json = {
            **dict(job.summary_json or {}),
            "worker_name": worker_name or "",
            "worker_stage": "failed",
        }
        session.commit()


def _run_tdx_pipeline_workflow(
    *,
    symbol: str | None,
    interval: str,
    vipdoc_path: str | None,
    force: bool,
    limit: int | None,
    requested_via: str | None = None,
) -> dict[str, object]:
    normalized_interval = interval.strip().lower()
    if normalized_interval not in TDX_PIPELINE_INTERVALS:
        raise ValueError("当前 A 股统一补数链路只支持 1d 或 all。")

    normalized_symbol = (symbol or "").strip().lower()
    requested_target = normalized_symbol.upper() or "ALL"
    steps = [
        {
            "key": "tdx_raw",
            "label": "通达信原始导入",
            "provider": "tdx",
            "interval": normalized_interval,
        },
        {
            "key": "tushare_actions",
            "label": "Tushare 公司行动抓取",
            "provider": "tushare",
            "interval": "corp_actions",
        },
        {
            "key": "tdx_qfq",
            "label": "通达信前复权重算",
            "provider": "tdx_qfq",
            "interval": "1d",
        },
    ]

    with open_session() as session:
        provider = ensure_data_provider(
            session,
            provider_key="tdx_pipeline",
            provider_name="A 股统一补数链路",
            provider_type="workflow",
            transport="orchestration",
            timezone="Asia/Shanghai",
            config_json={
                "depends_on": ["tdx", "tushare", "tdx_qfq"],
                "supports_intervals": list(TDX_PIPELINE_INTERVALS),
                "pipeline_steps": [step["provider"] for step in steps],
            },
            status="active",
        )
        ingestion_job = create_data_ingestion_job(
            session,
            provider=provider,
            job_type="tdx_pipeline_workflow",
            requested_via=requested_via or "manual",
            target_scope_json={
                "symbol": normalized_symbol,
                "interval": normalized_interval,
                "vipdoc_path": (vipdoc_path or "").strip(),
                "limit": limit or 0,
            },
            options_json={"force": force},
        )
        ingestion_job.targets_total = len(steps)

        step_items: dict[str, object] = {}
        for step in steps:
            item = create_data_ingestion_job_item(
                session,
                ingestion_job,
                item_key=f"{step['key']}:{requested_target}:{normalized_interval}",
                source_symbol=requested_target,
                interval=step["interval"],
                provider=provider,
            )
            item.details_json = {
                "provider_key": provider.provider_key,
                "step": step["key"],
                "step_label": step["label"],
                "child_provider": step["provider"],
            }
            step_items[step["key"]] = item
        session.commit()

        bars_inserted_total = 0
        bars_updated_total = 0
        child_ingestion_job_ids: list[int] = []
        workflow_results: list[dict[str, object]] = []
        step_statuses: list[str] = []
        pipeline_target_symbols: list[str] | None = [normalized_symbol.upper()] if normalized_symbol else None
        blocked = False
        blocked_by = ""
        blocked_message = ""
        first_error_message = ""
        cancelled = False

        for step in steps:
            item = step_items[step["key"]]
            if _is_current_enqueued_market_data_job_cancel_requested():
                cancelled = True
                blocked = True
                blocked_by = "cancel_requested"
                blocked_message = _current_enqueued_market_data_job_cancel_message()
            if blocked:
                item.status = "cancelled" if cancelled else "skipped"
                item.stage = "completed"
                item.error_message = ""
                item.details_json = {
                    **dict(item.details_json or {}),
                    "status": "cancelled" if cancelled else "skipped",
                    "reason": "cancel_requested" if cancelled else "upstream_failed",
                    "blocked_by": blocked_by,
                    "blocked_message": blocked_message,
                }
                ingestion_job.targets_completed += 1
                workflow_results.append(
                    {
                        "step": step["key"],
                        "step_label": step["label"],
                        "provider": step["provider"],
                        "interval": step["interval"],
                        "status": "cancelled" if cancelled else "skipped",
                        "error_message": blocked_message,
                        "blocked_by": blocked_by,
                    }
                )
                step_statuses.append("cancelled" if cancelled else "skipped")
                session.commit()
                continue

            try:
                if step["key"] == "tdx_raw":
                    result = _sync_tdx_market_data(
                        symbol=normalized_symbol or None,
                        interval=normalized_interval,
                        vipdoc_path=vipdoc_path,
                        force=force,
                        limit=limit,
                        requested_via=requested_via,
                    )
                    if not normalized_symbol:
                        pipeline_target_symbols = _resolve_tdx_pipeline_batch_symbols(limit=limit)
                elif step["key"] == "tushare_actions":
                    result = _sync_tushare_corporate_actions(
                        symbol=normalized_symbol or None,
                        limit=limit,
                        force=force,
                        target_symbols=pipeline_target_symbols,
                        requested_via=requested_via,
                    )
                else:
                    result = _rebuild_tdx_qfq_market_data(
                        symbol=normalized_symbol or None,
                        interval="1d",
                        force=force,
                        limit=limit,
                        target_symbols=pipeline_target_symbols,
                        requested_via=requested_via,
                    )

                child_ids = _collect_child_ingestion_job_ids(result)
                for child_id in child_ids:
                    if child_id not in child_ingestion_job_ids:
                        child_ingestion_job_ids.append(child_id)

                status = str(result.get("status") or "completed")
                error_message = str(result.get("error_message") or "")
                bars_inserted = int(result.get("bars_inserted") or 0)
                bars_updated = int(result.get("bars_updated") or 0)
                bars_inserted_total += bars_inserted
                bars_updated_total += bars_updated

                item.status = status
                item.stage = "failed" if status == "failed" else "completed"
                item.rows_inserted = bars_inserted
                item.rows_updated = bars_updated
                item.error_message = error_message if status in {"failed", "partially_failed"} else ""
                item.details_json = {
                    **dict(item.details_json or {}),
                    "status": status,
                    "requested_interval": step["interval"],
                    "result_interval": str(result.get("interval") or step["interval"]),
                    "symbols_count": int(result.get("symbols_count") or 0),
                    "child_ingestion_job_ids": child_ids,
                }
                ingestion_job.targets_completed += 1
                workflow_results.append(
                    {
                        "step": step["key"],
                        "step_label": step["label"],
                        "provider": step["provider"],
                        "interval": str(result.get("interval") or step["interval"]),
                        "symbols_count": int(result.get("symbols_count") or 0),
                        "bars_inserted": bars_inserted,
                        "bars_updated": bars_updated,
                        "status": status,
                        "error_message": error_message,
                        "child_ingestion_job_ids": child_ids,
                    }
                )
                step_statuses.append(status)
                if status == "failed":
                    blocked = True
                    blocked_by = step["key"]
                    blocked_message = error_message or f"{step['label']}失败。"
                    if not first_error_message:
                        first_error_message = blocked_message
                elif status == "cancelled":
                    cancelled = True
                    blocked = True
                    blocked_by = step["key"]
                    blocked_message = error_message or _current_enqueued_market_data_job_cancel_message()
                    if not first_error_message:
                        first_error_message = blocked_message
                elif status == "partially_failed" and error_message and not first_error_message:
                    first_error_message = error_message
                session.commit()
            except Exception as exc:
                session.rollback()
                error_message = str(exc)
                item = session.get(type(item), item.id)
                ingestion_job = session.get(type(ingestion_job), ingestion_job.id)
                if item is not None:
                    item.status = "failed"
                    item.stage = "failed"
                    item.error_message = error_message
                    item.details_json = {
                        **dict(item.details_json or {}),
                        "status": "failed",
                        "requested_interval": step["interval"],
                    }
                if ingestion_job is not None:
                    ingestion_job.targets_completed += 1
                workflow_results.append(
                    {
                        "step": step["key"],
                        "step_label": step["label"],
                        "provider": step["provider"],
                        "interval": step["interval"],
                        "status": "failed",
                        "error_message": error_message,
                        "child_ingestion_job_ids": [],
                    }
                )
                step_statuses.append("failed")
                blocked = True
                blocked_by = step["key"]
                blocked_message = error_message
                if not first_error_message:
                    first_error_message = error_message
                session.commit()

        ingestion_job = session.get(type(ingestion_job), ingestion_job.id)
        if ingestion_job is None:
            raise RuntimeError("统一补数 workflow 任务记录丢失。")

        ingestion_job.rows_inserted = bars_inserted_total
        ingestion_job.rows_updated = bars_updated_total
        ingestion_job.completed_at = datetime.now(UTC)
        ingestion_job.error_count = sum(1 for status in step_statuses if status in {"failed", "partially_failed"})
        ingestion_job.summary_json = {
            "provider_key": provider.provider_key,
            "requested_symbol": requested_target if normalized_symbol else "",
            "requested_interval": normalized_interval,
            "child_ingestion_job_ids": child_ingestion_job_ids,
            "workflow_results": workflow_results,
            "bars_inserted": bars_inserted_total,
            "bars_updated": bars_updated_total,
        }
        if any(status == "cancelled" for status in step_statuses):
            ingestion_job.status = "cancelled"
            ingestion_job.error_message = blocked_message or _current_enqueued_market_data_job_cancel_message()
        elif any(status == "failed" for status in step_statuses):
            ingestion_job.status = "failed"
            ingestion_job.error_message = (
                f"A 股统一补数链路执行失败。首个错误：{first_error_message}"
                if first_error_message
                else "A 股统一补数链路执行失败。"
            )
        elif any(status == "partially_failed" for status in step_statuses):
            ingestion_job.status = "partially_failed"
            ingestion_job.error_message = (
                f"A 股统一补数链路部分失败。首个错误：{first_error_message}"
                if first_error_message
                else "A 股统一补数链路部分失败。"
            )
        else:
            ingestion_job.status = "succeeded"
        session.commit()

        return {
            "provider": provider.provider_key,
            "ingestion_job_id": ingestion_job.id,
            "ingestion_job_ids": child_ingestion_job_ids,
            "child_ingestion_job_ids": child_ingestion_job_ids,
            "interval": normalized_interval,
            "symbols_count": _select_tdx_pipeline_symbols_count(workflow_results),
            "bars_inserted": bars_inserted_total,
            "bars_updated": bars_updated_total,
            "series_bars_inserted": bars_inserted_total,
            "series_bars_updated": bars_updated_total,
            "workflow_results": workflow_results,
            "error_message": ingestion_job.error_message,
            "status": ingestion_job.status,
        }


def _collect_child_ingestion_job_ids(result: dict[str, object]) -> list[int]:
    collected: list[int] = []
    direct_job_id = result.get("ingestion_job_id")
    if direct_job_id:
        collected.append(int(direct_job_id))
    for raw_value in result.get("ingestion_job_ids") or []:
        current_id = int(raw_value)
        if current_id not in collected:
            collected.append(current_id)
    return collected


def _select_tdx_pipeline_symbols_count(workflow_results: list[dict[str, object]]) -> int:
    for provider_key in ("tdx_qfq", "tushare", "tdx"):
        for item in workflow_results:
            if str(item.get("provider") or "") != provider_key:
                continue
            if int(item.get("symbols_count") or 0) > 0:
                return int(item.get("symbols_count") or 0)
    return 0


def _sync_yahoo_market_data(
    *,
    symbol: str | None,
    interval: str,
    proxy: str | None,
    period: str | None,
    limit: int | None,
    symbol_set: str | None,
    requested_via: str | None = None,
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
        target_specs = _resolve_yahoo_targets(session, symbol=symbol, symbol_set=symbol_set, limit=limit)
        if not target_specs:
            raise ValueError("当前没有可同步的 Yahoo 标的。请显式传入 --symbol，或使用 --symbol-set 载入内置样本池。")
        symbols = [spec.symbol for spec in target_specs]

        is_manual_request = bool(symbol) or bool(symbol_set)
        run = create_sync_run(session, job_type="manual" if is_manual_request else "scheduled", interval=interval)
        run.symbols_count = len(symbols)
        ingestion_job = create_data_ingestion_job(
            session,
            provider=provider,
            job_type="yahoo_sync",
            requested_via=requested_via or ("manual" if is_manual_request else "scheduler"),
            target_scope_json={"symbols": symbols, "interval": interval, "symbol_set": symbol_set or ""},
            options_json={"proxy_configured": bool(proxy), "period": period or "", "limit": limit or 0},
        )
        ingestion_job.targets_total = len(symbols)
        session.commit()

        total_inserted = 0
        total_updated = 0
        total_series_inserted = 0
        total_series_updated = 0
        failed_symbols = 0
        first_error_message = ""
        cancelled = False
        cancel_message = ""
        for current_spec in target_specs:
            if _is_current_enqueued_market_data_job_cancel_requested():
                cancelled = True
                cancel_message = _current_enqueued_market_data_job_cancel_message()
                break
            current_symbol = current_spec.symbol
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
                effective_period = period
                if is_intraday_interval(interval) and not effective_period:
                    effective_period = "7d" if interval == "1m" else "60d"
                bars = download_price_bars(
                    symbol=current_symbol,
                    interval=interval,
                    period=effective_period if is_intraday_interval(interval) else None,
                    proxy=proxy,
                )
                instrument = get_or_create_instrument(session, symbol=current_symbol, name=current_spec.name)
                alias = get_or_create_instrument_alias(
                    session,
                    instrument=instrument,
                    provider=provider,
                    source_symbol=current_symbol,
                    source_name=current_spec.name,
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
                if not first_error_message:
                    first_error_message = str(exc)
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
        if cancelled:
            run.status = "cancelled"
            run.error_message = cancel_message
        elif failed_symbols == len(symbols):
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
        if cancelled:
            ingestion_job.status = "cancelled"
            ingestion_job.error_message = cancel_message
        elif failed_symbols == len(symbols):
            ingestion_job.status = "failed"
            ingestion_job.error_message = (
                f"本次 Yahoo 同步全部失败。首个错误：{first_error_message}" if first_error_message else "本次 Yahoo 同步全部失败。"
            )
        elif failed_symbols:
            ingestion_job.status = "partially_failed"
            ingestion_job.error_message = (
                f"本次 Yahoo 同步有 {failed_symbols} 个标的失败。首个错误：{first_error_message}"
                if first_error_message
                else f"本次 Yahoo 同步有 {failed_symbols} 个标的失败。"
            )
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
            "symbol_set": symbol_set or "",
            "error_message": ingestion_job.error_message,
            "status": run.status,
        }


def _sync_tdx_market_data(
    *,
    symbol: str | None,
    interval: str,
    vipdoc_path: str | None,
    force: bool,
    limit: int | None,
    requested_via: str | None = None,
) -> dict[str, object]:
    normalized_interval = interval.strip().lower()
    if normalized_interval != "all":
        return _sync_tdx_single_interval_market_data(
            symbol=symbol,
            interval=normalized_interval,
            vipdoc_path=vipdoc_path,
            force=force,
            limit=limit,
            allow_empty=False,
            requested_via=requested_via,
        )

    interval_results: list[dict[str, object]] = []
    skipped_intervals: list[str] = []
    failed_intervals: list[str] = []
    first_error_message = ""
    cancelled = False
    cancel_message = ""
    for current_interval in TDX_IMPORT_INTERVALS:
        if _is_current_enqueued_market_data_job_cancel_requested():
            cancelled = True
            cancel_message = _current_enqueued_market_data_job_cancel_message()
            break
        try:
            result = _sync_tdx_single_interval_market_data(
                symbol=symbol,
                interval=current_interval,
                vipdoc_path=vipdoc_path,
                force=force,
                limit=limit,
                allow_empty=True,
                requested_via=requested_via,
            )
        except Exception as exc:
            if not first_error_message:
                first_error_message = str(exc)
            failed_intervals.append(current_interval)
            continue
        interval_results.append(result)
        if result.get("status") == "skipped" and int(result.get("symbols_count") or 0) == 0:
            skipped_intervals.append(current_interval)
        if result.get("status") == "cancelled":
            cancelled = True
            cancel_message = str(result.get("error_message") or "") or _current_enqueued_market_data_job_cancel_message()
            break

    effective_results = [item for item in interval_results if int(item.get("symbols_count") or 0) > 0]
    if not effective_results:
        raise ValueError(
            f"在通达信 vipdoc 中没有找到可导入的 1d / 1m / 5m 文件："
            f"symbol={symbol or 'ALL'} vipdoc={_resolve_tdx_vipdoc_path(vipdoc_path)}"
        )

    statuses = [str(item.get("status") or "") for item in effective_results]
    child_failed_intervals = [
        str(item.get("interval") or "")
        for item in effective_results
        if str(item.get("status") or "") in {"failed", "partially_failed"}
    ]
    inserted_total = sum(int(item.get("bars_inserted") or 0) for item in effective_results)
    updated_total = sum(int(item.get("bars_updated") or 0) for item in effective_results)
    series_inserted_total = sum(int(item.get("series_bars_inserted") or 0) for item in effective_results)
    series_updated_total = sum(int(item.get("series_bars_updated") or 0) for item in effective_results)
    files_imported_total = sum(int(item.get("files_imported") or 0) for item in effective_results)
    files_skipped_total = sum(int(item.get("files_skipped") or 0) for item in effective_results)
    files_failed_total = sum(int(item.get("files_failed") or 0) for item in effective_results)
    symbols_count_total = sum(int(item.get("symbols_count") or 0) for item in effective_results)

    status = "completed"
    if cancelled:
        status = "cancelled"
    elif (failed_intervals or child_failed_intervals) and all(item == "failed" for item in statuses):
        status = "failed"
    elif failed_intervals or child_failed_intervals or any(item == "partially_failed" for item in statuses):
        status = "partially_failed"
    elif any(item == "succeeded" for item in statuses):
        status = "succeeded"

    error_message = ""
    if cancelled:
        error_message = cancel_message or _current_enqueued_market_data_job_cancel_message()
    elif failed_intervals or child_failed_intervals:
        interval_labels = [*failed_intervals, *[item for item in child_failed_intervals if item not in failed_intervals]]
        first_child_error = next(
            (
                str(item.get("error_message") or "")
                for item in effective_results
                if str(item.get("status") or "") in {"failed", "partially_failed"} and str(item.get("error_message") or "").strip()
            ),
            "",
        )
        error_message = (
            f"通达信 all 周期导入中以下周期失败：{', '.join(interval_labels)}。"
            f"{' 首个错误：' + (first_error_message or first_child_error) if (first_error_message or first_child_error) else ''}"
        )

    return {
        "provider": "tdx",
        "interval": "all",
        "symbols_count": symbols_count_total,
        "bars_inserted": inserted_total,
        "bars_updated": updated_total,
        "series_bars_inserted": series_inserted_total,
        "series_bars_updated": series_updated_total,
        "files_imported": files_imported_total,
        "files_skipped": files_skipped_total,
        "files_failed": files_failed_total,
        "ingestion_job_ids": [int(item["ingestion_job_id"]) for item in effective_results if item.get("ingestion_job_id")],
        "interval_results": [
            {
                "interval": str(item.get("interval") or ""),
                "symbols_count": int(item.get("symbols_count") or 0),
                "bars_inserted": int(item.get("bars_inserted") or 0),
                "bars_updated": int(item.get("bars_updated") or 0),
                "files_imported": int(item.get("files_imported") or 0),
                "files_skipped": int(item.get("files_skipped") or 0),
                "files_failed": int(item.get("files_failed") or 0),
                "status": str(item.get("status") or ""),
            }
            for item in interval_results
        ],
        "skipped_intervals": skipped_intervals,
        "error_message": error_message,
        "status": status,
        "vipdoc_path": str(_resolve_tdx_vipdoc_path(vipdoc_path)),
    }


def _sync_tdx_single_interval_market_data(
    *,
    symbol: str | None,
    interval: str,
    vipdoc_path: str | None,
    force: bool,
    limit: int | None,
    allow_empty: bool,
    requested_via: str | None = None,
) -> dict[str, object]:
    tdx_period = interval_to_period(interval)
    file_kind = file_kind_for_interval(interval)
    vipdoc = _resolve_tdx_vipdoc_path(vipdoc_path)
    if not vipdoc.exists():
        raise FileNotFoundError(f"通达信 vipdoc 目录不存在：{vipdoc}")

    source_files = iter_tdx_files(vipdoc, interval=interval, symbol=symbol, limit=limit)
    if not source_files:
        if allow_empty:
            return {
                "provider": "tdx",
                "interval": interval,
                "symbols_count": 0,
                "bars_inserted": 0,
                "bars_updated": 0,
                "series_bars_inserted": 0,
                "series_bars_updated": 0,
                "files_imported": 0,
                "files_skipped": 0,
                "files_failed": 0,
                "error_message": "",
                "status": "skipped",
                "vipdoc_path": str(vipdoc),
            }
        suffixes = ",".join(sorted(suffixes_for_interval(interval)))
        raise ValueError(
            f"在 vipdoc 中没有找到可导入的通达信 {interval} 文件："
            f"vipdoc={vipdoc} symbol={symbol or 'ALL'} suffixes={suffixes}"
        )

    with open_session() as session:
        provider = ensure_data_provider(
            session,
            provider_key="tdx",
            provider_name="通达信本地行情",
            provider_type="market_data",
            transport="filesystem",
            timezone="Asia/Shanghai",
            config_json={"supports_intervals": ["1d", "1m", "5m"], "vipdoc_path": str(vipdoc)},
            status="active",
        )
        ingestion_job = create_data_ingestion_job(
            session,
            provider=provider,
            job_type="tdx_raw_import",
            requested_via=requested_via or "manual",
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
        first_error_message = ""
        cancelled = False
        cancel_message = ""
        for source_file in source_files:
            if _is_current_enqueued_market_data_job_cancel_requested():
                cancelled = True
                cancel_message = _current_enqueued_market_data_job_cancel_message()
                break
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
                signature = build_tdx_file_signature(source_file, interval=interval)
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
                    overlap_start = max(previous_rows - OVERLAP_ROWS, 0)
                    record_size = int(signature["record_size"])
                    start_offset = overlap_start * record_size
                    raw_frame = _read_tdx_frame_tail(source_file, vipdoc, interval, start_offset)
                    mode = "append"
                else:
                    raw_frame = _read_tdx_frame(source_file, vipdoc, interval)
                    mode = "rebuild"
                normalized = _normalize_tdx_frame(raw_frame, source_file, vipdoc, interval)
                if previous is not None and previous.last_bar_time is not None and mode == "append":
                    cutoff = _format_manifest_bar_time(previous.last_bar_time, interval)
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
                        file_kind=file_kind,
                        market=security.market.upper(),
                        interval=interval,
                        source_size=int(signature["source_size"]),
                        source_mtime=float(signature["source_mtime"]),
                        record_count=int(signature["record_count"]),
                        tail_hash=str(signature["tail_hash"] or ""),
                        status="success",
                        last_bar_time=previous.last_bar_time if previous is not None else None,
                        payload_json={
                            "mode": mode,
                            "period": tdx_period,
                            "security_type": security.security_type,
                            "source_suffix": source_file.suffix.lower(),
                        },
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
                    file_kind=file_kind,
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
                        "period": tdx_period,
                        "security_type": security.security_type,
                        "source_suffix": source_file.suffix.lower(),
                        "price_scale": security.price_scale if interval == "1d" else None,
                        "volume_scale": security.volume_scale if interval == "1d" else None,
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
                    "period": tdx_period,
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
                if not first_error_message:
                    first_error_message = str(exc)
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
        if cancelled:
            ingestion_job.status = "cancelled"
            ingestion_job.error_message = cancel_message
        elif failed_files == len(source_files):
            ingestion_job.status = "failed"
            ingestion_job.error_message = (
                f"本次通达信原始 {interval} 导入全部失败。首个错误：{first_error_message}"
                if first_error_message
                else f"本次通达信原始 {interval} 导入全部失败。"
            )
        elif failed_files:
            ingestion_job.status = "partially_failed"
            ingestion_job.error_message = (
                f"本次通达信原始 {interval} 导入有 {failed_files} 个文件失败。首个错误：{first_error_message}"
                if first_error_message
                else f"本次通达信原始 {interval} 导入有 {failed_files} 个文件失败。"
            )
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
            "error_message": ingestion_job.error_message,
            "status": ingestion_job.status,
            "vipdoc_path": str(vipdoc),
        }


def _read_tdx_frame(source_file: Path, vipdoc: Path, interval: str) -> pd.DataFrame:
    if interval == "1d":
        return read_day_frame(source_file, vipdoc)
    if interval in {"1m", "5m"}:
        return read_minute_frame(source_file)
    raise ValueError(f"当前通达信导入只支持 1d、1m、5m，收到：{interval}")


def _read_tdx_frame_tail(source_file: Path, vipdoc: Path, interval: str, start_offset: int) -> pd.DataFrame:
    if interval == "1d":
        return read_day_frame_tail(source_file, start_offset, vipdoc)
    if interval in {"1m", "5m"}:
        return read_minute_frame_tail(source_file, start_offset)
    raise ValueError(f"当前通达信导入只支持 1d、1m、5m，收到：{interval}")


def _normalize_tdx_frame(frame: pd.DataFrame, source_file: Path, vipdoc: Path, interval: str) -> pd.DataFrame:
    if interval == "1d":
        return normalize_day_frame(frame, source_file, vipdoc)
    if interval in {"1m", "5m"}:
        return normalize_minute_frame(frame, source_file, vipdoc, interval)
    raise ValueError(f"当前通达信导入只支持 1d、1m、5m，收到：{interval}")


def _format_manifest_bar_time(value: object, interval: str) -> str:
    timestamp = pd.Timestamp(value)
    if interval == "1d":
        return timestamp.strftime("%Y-%m-%d")
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def _sync_tushare_corporate_actions(
    *,
    symbol: str | None,
    limit: int | None,
    force: bool,
    target_symbols: list[str] | None = None,
    requested_via: str | None = None,
) -> dict[str, object]:
    client = TushareClient(load_tushare_client_settings())
    targets = _resolve_tushare_targets(client, symbol=symbol, limit=limit, target_symbols=target_symbols)

    with open_session() as session:
        provider = ensure_data_provider(
            session,
            provider_key="tushare",
            provider_name="Tushare 公司行动",
            provider_type="corporate_action",
            transport="api",
            timezone="Asia/Shanghai",
            config_json={
                "supports_actions": ["dividend"],
                "config_path": client.settings.config_path,
                "rate_limit_per_minute": client.settings.rate_limit_per_minute,
            },
            status="active",
        )
        ingestion_job = create_data_ingestion_job(
            session,
            provider=provider,
            job_type="tushare_corporate_actions",
            requested_via=requested_via or "manual",
            target_scope_json={
                "symbol": (symbol or "").strip(),
                "limit": limit or 0,
                "target_symbols": [item.strip().upper() for item in target_symbols or []],
            },
            options_json={
                "force": force,
            },
        )
        ingestion_job.targets_total = len(targets)
        session.commit()

        succeeded_symbols = 0
        skipped_symbols = 0
        failed_symbols = 0
        rows_inserted = 0
        rows_updated = 0
        rows_deleted = 0
        fetched_rows = 0
        implemented_rows = 0
        first_error_message = ""
        cancelled = False
        cancel_message = ""
        for target in targets:
            if _is_current_enqueued_market_data_job_cancel_requested():
                cancelled = True
                cancel_message = _current_enqueued_market_data_job_cancel_message()
                break
            ts_code = str(target["ts_code"]).upper()
            item = create_data_ingestion_job_item(
                session,
                ingestion_job,
                item_key=f"{ts_code}:corp_actions:dividend",
                source_symbol=ts_code,
                interval="corp_actions",
                provider=provider,
            )
            session.commit()
            try:
                raw_frame = client.query("dividend", params={"ts_code": ts_code}, fields=DIVIDEND_FIELDS)
                records = build_corporate_action_records(raw_frame)
                market = ts_code_to_market(ts_code)
                instrument_symbol = ts_code_to_instrument_symbol(ts_code)
                instrument = get_or_create_instrument(
                    session,
                    symbol=instrument_symbol,
                    name=str(target.get("name") or instrument_symbol),
                    asset_type="equity",
                    timezone="Asia/Shanghai",
                )
                instrument.exchange = market
                alias = get_or_create_instrument_alias(
                    session,
                    instrument=instrument,
                    provider=provider,
                    source_symbol=ts_code,
                    source_name=str(target.get("name") or instrument_symbol),
                    market=market,
                    exchange=market,
                    security_type="equity",
                    timezone="Asia/Shanghai",
                )
                inserted, updated, deleted = replace_corporate_action_events_for_symbol(
                    session,
                    instrument,
                    provider,
                    source_symbol=ts_code,
                    rows=records,
                )
                item.status = "succeeded"
                item.stage = "completed"
                item.instrument_id = instrument.id
                item.rows_inserted = inserted
                item.rows_updated = updated
                item.details_json = {
                    "provider_key": provider.provider_key,
                    "source_symbol": ts_code,
                    "alias_id": alias.id,
                    "raw_rows": len(raw_frame),
                    "implemented_rows": len(records),
                    "deleted_rows": deleted,
                }
                ingestion_job.targets_completed += 1
                succeeded_symbols += 1
                fetched_rows += len(raw_frame)
                implemented_rows += len(records)
                rows_inserted += inserted
                rows_updated += updated
                rows_deleted += deleted
                session.commit()
            except Exception as exc:
                session.rollback()
                item = session.get(type(item), item.id)
                ingestion_job = session.get(type(ingestion_job), ingestion_job.id)
                if item is not None:
                    item.status = "failed"
                    item.stage = "failed"
                    item.error_message = str(exc)
                    item.details_json = {
                        "provider_key": provider.provider_key,
                        "source_symbol": ts_code,
                    }
                if ingestion_job is not None:
                    ingestion_job.error_count += 1
                if not first_error_message:
                    first_error_message = str(exc)
                failed_symbols += 1
                session.commit()

        ingestion_job = session.get(type(ingestion_job), ingestion_job.id)
        if ingestion_job is None:
            raise RuntimeError("统一导入任务记录丢失。")
        ingestion_job.rows_inserted = rows_inserted
        ingestion_job.rows_updated = rows_updated
        ingestion_job.completed_at = datetime.now(UTC)
        ingestion_job.summary_json = {
            "provider_key": provider.provider_key,
            "symbols_total": len(targets),
            "symbols_succeeded": succeeded_symbols,
            "symbols_failed": failed_symbols,
            "fetched_rows": fetched_rows,
            "implemented_rows": implemented_rows,
            "deleted_rows": rows_deleted,
        }
        if cancelled:
            ingestion_job.status = "cancelled"
            ingestion_job.error_message = cancel_message
        elif failed_symbols == len(targets):
            ingestion_job.status = "failed"
            ingestion_job.error_message = (
                f"本次 Tushare 公司行动抓取全部失败。首个错误：{first_error_message}"
                if first_error_message
                else "本次 Tushare 公司行动抓取全部失败。"
            )
        elif failed_symbols:
            ingestion_job.status = "partially_failed"
            ingestion_job.error_message = (
                f"本次 Tushare 公司行动抓取有 {failed_symbols} 个标的失败。首个错误：{first_error_message}"
                if first_error_message
                else f"本次 Tushare 公司行动抓取有 {failed_symbols} 个标的失败。"
            )
        else:
            ingestion_job.status = "succeeded"
        session.commit()

        return {
            "provider": provider.provider_key,
            "ingestion_job_id": ingestion_job.id,
            "interval": "corp_actions",
            "symbols_count": len(targets),
            "bars_inserted": rows_inserted,
            "bars_updated": rows_updated,
            "events_deleted": rows_deleted,
            "fetched_rows": fetched_rows,
            "implemented_rows": implemented_rows,
            "error_message": ingestion_job.error_message,
            "status": ingestion_job.status,
        }


def _rebuild_tdx_qfq_market_data(
    *,
    symbol: str | None,
    interval: str,
    force: bool,
    limit: int | None,
    target_symbols: list[str] | None = None,
    requested_via: str | None = None,
) -> dict[str, object]:
    if interval != "1d":
        raise ValueError("当前前复权重算只支持 1d 日线。")

    rebuild_started_at = perf_counter()
    with open_session() as session:
        raw_provider = ensure_data_provider(
            session,
            provider_key="tdx",
            provider_name="通达信本地行情",
            provider_type="market_data",
            transport="filesystem",
            timezone="Asia/Shanghai",
            config_json={"supports_intervals": ["1d"]},
            status="active",
        )
        action_provider = ensure_data_provider(
            session,
            provider_key="tushare",
            provider_name="Tushare 公司行动",
            provider_type="corporate_action",
            transport="api",
            timezone="Asia/Shanghai",
            config_json={"supports_actions": ["dividend"]},
            status="active",
        )
        provider = ensure_data_provider(
            session,
            provider_key="tdx_qfq",
            provider_name="通达信前复权日线",
            provider_type="derived_market_data",
            transport="database",
            timezone="Asia/Shanghai",
            config_json={"depends_on": ["tdx", "tushare"], "supports_intervals": ["1d"], "adjustment_kind": "qfq"},
            status="active",
        )
        targets = _resolve_tdx_qfq_targets(
            session,
            raw_provider=raw_provider,
            symbol=symbol,
            limit=limit,
            target_symbols=target_symbols,
        )
        if not targets:
            raise ValueError("当前数据库中没有可重算前复权的通达信原始 1d 序列。")

        ingestion_job = create_data_ingestion_job(
            session,
            provider=provider,
            job_type="tdx_qfq_rebuild",
            requested_via=requested_via or "manual",
            target_scope_json={
                "symbol": (symbol or "").strip().lower(),
                "interval": interval,
                "limit": limit or 0,
                "target_symbols": [item.strip().upper() for item in target_symbols or []],
            },
            options_json={"force": force},
        )
        ingestion_job.targets_total = len(targets)
        session.commit()

        succeeded_symbols = 0
        skipped_symbols = 0
        failed_symbols = 0
        segment_rows_inserted = 0
        segment_rows_updated = 0
        segment_rows_deleted = 0
        bar_rows_inserted = 0
        bar_rows_updated = 0
        action_rows_used = 0
        first_error_message = ""
        cancelled = False
        cancel_message = ""
        preload_output_started_at = perf_counter()
        qfq_aliases_by_symbol, qfq_series_by_scope = _preload_tdx_qfq_output_entities(
            session,
            targets,
            provider,
            interval=interval,
        )
        preload_output_ms = _elapsed_ms(preload_output_started_at)
        action_updated_at_by_instrument = _preload_tdx_qfq_action_updated_at(
            session,
            targets,
            action_provider,
        )
        pending_targets: list[dict[str, object]] = []
        for target in targets:
            raw_series = target["series"]
            raw_alias = target["alias"]
            instrument = target["instrument"]
            qfq_source_symbol = str(raw_alias.source_symbol or "").strip().upper()
            qfq_alias = qfq_aliases_by_symbol.get(qfq_source_symbol)
            qfq_series = None
            if qfq_alias is not None:
                qfq_series = qfq_series_by_scope.get(_tdx_qfq_series_scope_key(qfq_alias.id, interval=interval))
            target["qfq_source_symbol"] = qfq_source_symbol
            target["qfq_alias"] = qfq_alias
            target["qfq_series"] = qfq_series
            target["skip_ready"] = _can_skip_tdx_qfq_rebuild(
                force=force,
                raw_provider=raw_provider,
                action_provider=action_provider,
                raw_series=raw_series,
                qfq_series=qfq_series,
                action_last_updated_at=action_updated_at_by_instrument.get(instrument.id),
            )
            if not target["skip_ready"]:
                pending_targets.append(target)

        preload_input_ms = 0
        raw_frames_by_series: dict[int, pd.DataFrame] = {}
        action_frames_by_instrument: dict[int, pd.DataFrame] = {}
        if pending_targets:
            preload_input_started_at = perf_counter()
            raw_frames_by_series, action_frames_by_instrument, _ = _preload_tdx_qfq_input_frames(
                session,
                pending_targets,
                action_provider,
            )
            preload_input_ms = _elapsed_ms(preload_input_started_at)
        timing_totals_ms = {
            "segment_build_ms": 0,
            "segment_replace_ms": 0,
            "segment_apply_ms": 0,
            "output_prepare_ms": 0,
            "bar_upsert_ms": 0,
        }
        processed_symbol_timing_ms = 0
        succeeded_symbol_timing_ms = 0
        failed_symbol_timing_ms = 0
        pending_targets_since_commit = 0

        def commit_batch_progress() -> None:
            # 前复权重算是批量写入链路，统一按批次落库，避免每个标的都切一次事务。
            nonlocal pending_targets_since_commit, ingestion_job
            if pending_targets_since_commit <= 0:
                return
            session.commit()
            pending_targets_since_commit = 0
            refreshed_job = session.get(type(ingestion_job), ingestion_job.id)
            if refreshed_job is None:
                raise RuntimeError("统一导入任务记录丢失。")
            ingestion_job = refreshed_job

        for target in targets:
            if _is_current_enqueued_market_data_job_cancel_requested():
                cancelled = True
                cancel_message = _current_enqueued_market_data_job_cancel_message()
                break
            instrument = target["instrument"]
            raw_series = target["series"]
            raw_alias = target["alias"]
            item = create_data_ingestion_job_item(
                session,
                ingestion_job,
                item_key=f"{instrument.symbol}:{interval}:qfq",
                source_symbol=instrument.symbol,
                interval=interval,
                provider=provider,
            )
            item_timing_json: dict[str, int] = {}
            item_started_at = perf_counter()
            try:
                # 单标的失败只回滚当前 savepoint，已处理的批次仍可继续累计并分批提交。
                with session.begin_nested():
                    action_last_updated_at = action_updated_at_by_instrument.get(instrument.id)
                    stage_started_at = perf_counter()
                    qfq_source_symbol = str(target.get("qfq_source_symbol") or str(raw_alias.source_symbol or "").strip().upper())
                    qfq_alias = target.get("qfq_alias")
                    qfq_series = target.get("qfq_series")
                    item_timing_json["output_prepare_ms"] = _elapsed_ms(stage_started_at)
                    if bool(target.get("skip_ready")):
                        item_timing_json["total_elapsed_ms"] = _elapsed_ms(item_started_at)
                        item.status = "skipped"
                        item.stage = "completed"
                        item.instrument_id = instrument.id
                        item.series_id = qfq_series.id if qfq_series is not None else None
                        item.details_json = {
                            "provider_key": provider.provider_key,
                            "raw_series_id": raw_series.id,
                            "reason": "qfq_series_up_to_date",
                            "timing_json": dict(item_timing_json),
                        }
                        skipped_symbols += 1
                        processed_symbol_timing_ms += item_timing_json.get("total_elapsed_ms", 0)
                        ingestion_job.targets_completed = succeeded_symbols + skipped_symbols
                        ingestion_job.error_count = failed_symbols
                        pending_targets_since_commit += 1
                        continue
                    raw_frame = raw_frames_by_series.get(raw_series.id)
                    if raw_frame is None or raw_frame.empty:
                        raise ValueError(f"原始序列没有可用于前复权重算的日线数据：series_id={raw_series.id}")
                    action_frame = action_frames_by_instrument.get(instrument.id, _empty_action_frame())
                    stage_started_at = perf_counter()
                    segment_frame = build_qfq_segment_frame(raw_frame, action_frame)
                    item_timing_json["segment_build_ms"] = _elapsed_ms(stage_started_at)
                    segment_rows = segment_frame.to_dict(orient="records")
                    stage_started_at = perf_counter()
                    seg_inserted, seg_updated, seg_deleted = replace_price_adjustment_segments(
                        session,
                        instrument,
                        provider,
                        action_provider=action_provider,
                        adjustment_kind="qfq",
                        rows=segment_rows,
                    )
                    item_timing_json["segment_replace_ms"] = _elapsed_ms(stage_started_at)
                    stage_started_at = perf_counter()
                    adjusted_frame = apply_qfq_segment_frame(raw_frame, segment_frame)
                    item_timing_json["segment_apply_ms"] = _elapsed_ms(stage_started_at)
                    if qfq_alias is None:
                        qfq_alias = get_or_create_instrument_alias(
                            session,
                            instrument=instrument,
                            provider=provider,
                            source_symbol=raw_alias.source_symbol,
                            source_name=raw_alias.source_name or instrument.name,
                            market=raw_alias.market or instrument.exchange,
                            exchange=raw_alias.exchange or instrument.exchange,
                            security_type=raw_alias.security_type,
                            timezone=raw_alias.timezone,
                        )
                        qfq_aliases_by_symbol[qfq_source_symbol] = qfq_alias
                    else:
                        qfq_alias.instrument_id = instrument.id
                        qfq_alias.source_name = raw_alias.source_name or qfq_alias.source_name or instrument.name
                        qfq_alias.market = raw_alias.market or qfq_alias.market or instrument.exchange
                        qfq_alias.exchange = raw_alias.exchange or qfq_alias.exchange or instrument.exchange
                        qfq_alias.security_type = raw_alias.security_type
                        qfq_alias.timezone = raw_alias.timezone
                        qfq_alias.is_primary = True

                    series_scope = _tdx_qfq_series_scope_key(qfq_alias.id, interval=interval)
                    qfq_series = qfq_series_by_scope.get(series_scope)
                    if qfq_series is None:
                        qfq_series = get_or_create_market_data_series(
                            session,
                            instrument=instrument,
                            provider=provider,
                            alias=qfq_alias,
                            interval=interval,
                            market=raw_alias.market or instrument.exchange,
                            exchange=raw_alias.exchange or instrument.exchange,
                            adjustment_kind="qfq",
                            session_type="regular",
                            price_type="trade",
                            bar_type="time",
                            timezone=raw_alias.timezone or instrument.timezone,
                        )
                        qfq_series_by_scope[series_scope] = qfq_series
                    else:
                        qfq_series.instrument_id = instrument.id
                        qfq_series.market = raw_alias.market or qfq_series.market or instrument.exchange
                        qfq_series.exchange = raw_alias.exchange or qfq_series.exchange or instrument.exchange
                        qfq_series.bar_type = "time"
                        qfq_series.timezone = raw_alias.timezone or instrument.timezone
                        qfq_series.is_active = True
                    stage_started_at = perf_counter()
                    bars_inserted, bars_updated = upsert_market_data_frame(session, qfq_series, adjusted_frame)
                    item_timing_json["bar_upsert_ms"] = _elapsed_ms(stage_started_at)
                    qfq_series.metadata_json = {
                        **qfq_series.metadata_json,
                        "raw_provider_key": raw_provider.provider_key,
                        "raw_series_id": raw_series.id,
                        "action_provider_key": action_provider.provider_key,
                    }
                    item_timing_json["total_elapsed_ms"] = _elapsed_ms(item_started_at)
                    item.status = "succeeded"
                    item.stage = "completed"
                    item.instrument_id = instrument.id
                    item.series_id = qfq_series.id
                    item.rows_inserted = bars_inserted
                    item.rows_updated = bars_updated
                    item.details_json = {
                        "provider_key": provider.provider_key,
                        "raw_series_id": raw_series.id,
                        "segment_rows": len(segment_rows),
                        "segment_rows_inserted": seg_inserted,
                        "segment_rows_updated": seg_updated,
                        "segment_rows_deleted": seg_deleted,
                        "action_rows_used": len(action_frame),
                        "timing_json": dict(item_timing_json),
                    }
                succeeded_symbols += 1
                segment_rows_inserted += seg_inserted
                segment_rows_updated += seg_updated
                segment_rows_deleted += seg_deleted
                bar_rows_inserted += bars_inserted
                bar_rows_updated += bars_updated
                action_rows_used += len(action_frame)
                processed_symbol_timing_ms += item_timing_json.get("total_elapsed_ms", 0)
                succeeded_symbol_timing_ms += item_timing_json.get("total_elapsed_ms", 0)
                for key in timing_totals_ms:
                    timing_totals_ms[key] += item_timing_json.get(key, 0)
                ingestion_job.targets_completed = succeeded_symbols + skipped_symbols
                ingestion_job.error_count = failed_symbols
                pending_targets_since_commit += 1
            except Exception as exc:
                item_timing_json["total_elapsed_ms"] = _elapsed_ms(item_started_at)
                if not first_error_message:
                    first_error_message = str(exc)
                failed_symbols += 1
                processed_symbol_timing_ms += item_timing_json.get("total_elapsed_ms", 0)
                failed_symbol_timing_ms += item_timing_json.get("total_elapsed_ms", 0)
                for key in timing_totals_ms:
                    timing_totals_ms[key] += item_timing_json.get(key, 0)
                item.status = "failed"
                item.stage = "failed"
                item.error_message = str(exc)
                item.details_json = {
                    "provider_key": provider.provider_key,
                    "raw_series_id": raw_series.id,
                    "timing_json": dict(item_timing_json),
                }
                ingestion_job.targets_completed = succeeded_symbols + skipped_symbols
                ingestion_job.error_count = failed_symbols
                pending_targets_since_commit += 1
                commit_batch_progress()
                continue

            if pending_targets_since_commit >= TDX_QFQ_COMMIT_EVERY:
                commit_batch_progress()

        commit_batch_progress()
        ingestion_job.rows_inserted = bar_rows_inserted
        ingestion_job.rows_updated = bar_rows_updated
        ingestion_job.completed_at = datetime.now(UTC)
        processed_symbols = succeeded_symbols + skipped_symbols + failed_symbols
        timing_summary_json = {
            "commit_every": TDX_QFQ_COMMIT_EVERY,
            "processed_symbols": processed_symbols,
            "preload_input_ms": preload_input_ms,
            "preload_output_ms": preload_output_ms,
            "segment_build_ms": timing_totals_ms["segment_build_ms"],
            "segment_replace_ms": timing_totals_ms["segment_replace_ms"],
            "segment_apply_ms": timing_totals_ms["segment_apply_ms"],
            "output_prepare_ms": timing_totals_ms["output_prepare_ms"],
            "bar_upsert_ms": timing_totals_ms["bar_upsert_ms"],
            "symbol_total_ms": processed_symbol_timing_ms,
            "symbol_avg_ms": int(round(processed_symbol_timing_ms / processed_symbols)) if processed_symbols else 0,
            "succeeded_symbol_avg_ms": int(round(succeeded_symbol_timing_ms / succeeded_symbols)) if succeeded_symbols else 0,
            "failed_symbol_avg_ms": int(round(failed_symbol_timing_ms / failed_symbols)) if failed_symbols else 0,
            "total_elapsed_ms": _elapsed_ms(rebuild_started_at),
        }
        ingestion_job.summary_json = {
            "provider_key": provider.provider_key,
            "symbols_total": len(targets),
            "symbols_succeeded": succeeded_symbols,
            "symbols_skipped": skipped_symbols,
            "symbols_failed": failed_symbols,
            "segment_rows_inserted": segment_rows_inserted,
            "segment_rows_updated": segment_rows_updated,
            "segment_rows_deleted": segment_rows_deleted,
            "bar_rows_inserted": bar_rows_inserted,
            "bar_rows_updated": bar_rows_updated,
            "action_rows_used": action_rows_used,
            "timing_json": timing_summary_json,
        }
        if cancelled:
            ingestion_job.status = "cancelled"
            ingestion_job.error_message = cancel_message
        elif failed_symbols == len(targets):
            ingestion_job.status = "failed"
            ingestion_job.error_message = (
                f"本次通达信前复权日线重算全部失败。首个错误：{first_error_message}"
                if first_error_message
                else "本次通达信前复权日线重算全部失败。"
            )
        elif failed_symbols:
            ingestion_job.status = "partially_failed"
            ingestion_job.error_message = (
                f"本次通达信前复权日线重算有 {failed_symbols} 个标的失败。首个错误：{first_error_message}"
                if first_error_message
                else f"本次通达信前复权日线重算有 {failed_symbols} 个标的失败。"
            )
        elif skipped_symbols == len(targets):
            ingestion_job.status = "skipped"
        else:
            ingestion_job.status = "succeeded"
        session.commit()

        return {
            "provider": provider.provider_key,
            "ingestion_job_id": ingestion_job.id,
            "interval": interval,
            "symbols_count": len(targets),
            "symbols_skipped": skipped_symbols,
            "bars_inserted": bar_rows_inserted,
            "bars_updated": bar_rows_updated,
            "segment_rows_inserted": segment_rows_inserted,
            "segment_rows_updated": segment_rows_updated,
            "segment_rows_deleted": segment_rows_deleted,
            "action_rows_used": action_rows_used,
            "timing_json": timing_summary_json,
            "error_message": ingestion_job.error_message,
            "status": ingestion_job.status,
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


def _resolve_yahoo_targets(
    session,
    *,
    symbol: str | None,
    symbol_set: str | None,
    limit: int | None,
) -> list[SymbolSpec]:
    """解析 Yahoo 同步目标。

    优先级：
    1. 单个 `symbol`
    2. 指定内置 `symbol_set`
    3. 数据库中已存在的标的
    """
    if symbol and symbol.strip():
        return [resolve_symbol_spec(symbol)]

    if symbol_set and symbol_set.strip():
        specs = list(get_symbol_set(symbol_set))
        return specs[:limit] if limit is not None else specs

    instrument_rows = list_instruments(session)
    if limit is not None:
        instrument_rows = instrument_rows[:limit]
    targets: list[SymbolSpec] = []
    for row in instrument_rows:
        current_symbol = str(row["symbol"]).strip().upper()
        resolved = resolve_symbol_spec(current_symbol)
        targets.append(
            SymbolSpec(
                symbol=current_symbol,
                name=str(row.get("name") or resolved.name or current_symbol),
                category=resolved.category,
                source=resolved.source,
            )
        )
    return targets


def _resolve_tushare_targets(
    client: TushareClient,
    *,
    symbol: str | None,
    limit: int | None,
    target_symbols: list[str] | None = None,
) -> list[dict[str, str]]:
    if target_symbols:
        targets: list[dict[str, str]] = []
        for raw_symbol in target_symbols:
            normalized_symbol = str(raw_symbol).strip().upper()
            if not normalized_symbol:
                continue
            ts_code = symbol_to_ts_code(normalized_symbol)
            instrument_symbol = ts_code_to_instrument_symbol(ts_code)
            targets.append(
                {
                    "ts_code": ts_code,
                    "symbol": instrument_symbol,
                    "name": instrument_symbol,
                }
            )
        if not targets:
            raise ValueError("统一补数链路没有解析出可抓取的 Tushare 标的。")
        return targets
    if symbol and symbol.strip():
        ts_code = symbol_to_ts_code(symbol)
        instrument_symbol = ts_code_to_instrument_symbol(ts_code)
        return [
            {
                "ts_code": ts_code,
                "symbol": instrument_symbol,
                "name": instrument_symbol,
            }
        ]
    if limit is None:
        raise ValueError("当前 Tushare 公司行动抓取需要显式传入 --symbol，或至少给出 --limit 控制抓取范围。")
    stock_basic = fetch_stock_basic(client)
    if stock_basic.empty:
        raise ValueError("Tushare stock_basic 未返回可抓取的股票清单。")
    targets = []
    for row in stock_basic.head(limit).to_dict(orient="records"):
        ts_code = str(row.get("ts_code") or "").upper()
        if not ts_code:
            continue
        targets.append(
            {
                "ts_code": ts_code,
                "symbol": ts_code_to_instrument_symbol(ts_code),
                "name": str(row.get("name") or ts_code_to_instrument_symbol(ts_code)),
            }
        )
    if not targets:
        raise ValueError("Tushare 股票清单为空，无法构造抓取目标。")
    return targets


def _resolve_tdx_qfq_targets(
    session,
    *,
    raw_provider,
    symbol: str | None,
    limit: int | None,
    target_symbols: list[str] | None = None,
) -> list[dict[str, object]]:
    statement = (
        select(MarketDataSeries, Instrument, InstrumentAlias)
        .join(Instrument, Instrument.id == MarketDataSeries.instrument_id)
        .join(InstrumentAlias, InstrumentAlias.id == MarketDataSeries.alias_id)
        .where(
            MarketDataSeries.provider_id == raw_provider.id,
            MarketDataSeries.interval == "1d",
            MarketDataSeries.adjustment_kind == "raw",
        )
        .order_by(Instrument.symbol)
    )
    if symbol and symbol.strip():
        normalized_symbol = symbol.strip().upper()
        statement = statement.where(
            (Instrument.symbol == normalized_symbol) | (InstrumentAlias.source_symbol == normalized_symbol)
        )
    elif target_symbols:
        normalized_symbols = [item.strip().upper() for item in target_symbols if item.strip()]
        if not normalized_symbols:
            return []
        statement = statement.where(Instrument.symbol.in_(normalized_symbols))
    if limit is not None:
        statement = statement.limit(limit)

    return [
        {"series": row[0], "instrument": row[1], "alias": row[2]}
        for row in session.execute(statement).all()
    ]


def _resolve_tdx_pipeline_batch_symbols(limit: int | None) -> list[str]:
    with open_session() as session:
        raw_provider = ensure_data_provider(
            session,
            provider_key="tdx",
            provider_name="通达信本地行情",
            provider_type="market_data",
            transport="filesystem",
            timezone="Asia/Shanghai",
            config_json={"supports_intervals": ["1d"]},
            status="active",
        )
        targets = _resolve_tdx_qfq_targets(session, raw_provider=raw_provider, symbol=None, limit=limit)
        symbols = [str(item["instrument"].symbol).strip().upper() for item in targets if str(item["instrument"].symbol).strip()]
        if not symbols:
            raise ValueError("统一补数链路未找到可用于公司行动和前复权的通达信原始 1d 标的。")
        return symbols


def _preload_tdx_qfq_input_frames(
    session,
    targets: list[dict[str, object]],
    action_provider,
) -> tuple[dict[int, pd.DataFrame], dict[int, pd.DataFrame], dict[int, datetime | None]]:
    """批量预加载前复权输入，避免每个标的重复走一轮 ORM 查询。"""
    if not targets:
        return {}, {}, {}

    ordered_series_ids: list[int] = []
    ordered_instrument_ids: list[int] = []
    for item in targets:
        raw_series = item["series"]
        instrument = item["instrument"]
        if raw_series.id not in ordered_series_ids:
            ordered_series_ids.append(raw_series.id)
        if instrument.id not in ordered_instrument_ids:
            ordered_instrument_ids.append(instrument.id)

    raw_records_by_series: dict[int, list[dict[str, object]]] = defaultdict(list)
    raw_rows = session.execute(
        select(
            MarketDataBar.series_id,
            MarketDataBar.bar_time,
            MarketDataBar.open,
            MarketDataBar.high,
            MarketDataBar.low,
            MarketDataBar.close,
            MarketDataBar.volume,
            MarketDataBar.turnover_amount,
        )
        .where(MarketDataBar.series_id.in_(ordered_series_ids))
        .order_by(MarketDataBar.series_id, MarketDataBar.bar_time)
    ).all()
    for row in raw_rows:
        raw_records_by_series[int(row.series_id)].append(
            {
                "Date": row.bar_time,
                "Open": row.open,
                "High": row.high,
                "Low": row.low,
                "Close": row.close,
                "Volume": row.volume,
                "Amount": row.turnover_amount,
            }
        )

    action_records_by_instrument: dict[int, list[dict[str, object]]] = defaultdict(list)
    action_updated_at_by_instrument: dict[int, datetime | None] = {instrument_id: None for instrument_id in ordered_instrument_ids}
    action_rows = session.execute(
        select(
            CorporateActionEvent.instrument_id,
            CorporateActionEvent.ex_date,
            CorporateActionEvent.cash_dividend,
            CorporateActionEvent.stock_bonus_ratio,
            CorporateActionEvent.stock_conversion_ratio,
            CorporateActionEvent.rights_ratio,
            CorporateActionEvent.rights_price,
            CorporateActionEvent.status,
            CorporateActionEvent.updated_at,
        )
        .where(
            CorporateActionEvent.provider_id == action_provider.id,
            CorporateActionEvent.instrument_id.in_(ordered_instrument_ids),
        )
        .order_by(CorporateActionEvent.instrument_id, CorporateActionEvent.ex_date, CorporateActionEvent.announce_date)
    ).all()
    for row in action_rows:
        current_updated_at = action_updated_at_by_instrument.get(int(row.instrument_id))
        if current_updated_at is None or (row.updated_at is not None and row.updated_at > current_updated_at):
            action_updated_at_by_instrument[int(row.instrument_id)] = row.updated_at
        action_records_by_instrument[int(row.instrument_id)].append(
            {
                "ex_date": row.ex_date,
                "cash_dividend": row.cash_dividend,
                "stock_bonus_ratio": row.stock_bonus_ratio,
                "stock_conversion_ratio": row.stock_conversion_ratio,
                "rights_ratio": row.rights_ratio,
                "rights_price": row.rights_price,
                "status": row.status,
            }
        )

    raw_frames_by_series = {
        series_id: pd.DataFrame(
            raw_records_by_series.get(series_id, []),
            columns=["Date", "Open", "High", "Low", "Close", "Volume", "Amount"],
        )
        for series_id in ordered_series_ids
    }
    action_frames_by_instrument = {
        instrument_id: pd.DataFrame(
            action_records_by_instrument.get(instrument_id, []),
            columns=[
                "ex_date",
                "cash_dividend",
                "stock_bonus_ratio",
                "stock_conversion_ratio",
                "rights_ratio",
                "rights_price",
                "status",
            ],
        )
        for instrument_id in ordered_instrument_ids
    }
    return raw_frames_by_series, action_frames_by_instrument, action_updated_at_by_instrument


def _tdx_qfq_series_scope_key(
    alias_id: int | None,
    *,
    interval: str,
    adjustment_kind: str = "qfq",
    session_type: str = "regular",
    price_type: str = "trade",
) -> tuple[int | None, str, str, str, str]:
    return (alias_id, interval, adjustment_kind, session_type, price_type)


def _preload_tdx_qfq_output_entities(
    session,
    targets: list[dict[str, object]],
    provider,
    *,
    interval: str,
) -> tuple[dict[str, InstrumentAlias], dict[tuple[int | None, str, str, str, str], MarketDataSeries]]:
    """批量预加载前复权输出端对象，减少重算过程中每个标的重复查 alias/series。"""
    if not targets:
        return {}, {}

    ordered_source_symbols: list[str] = []
    for item in targets:
        raw_alias = item["alias"]
        normalized_symbol = str(raw_alias.source_symbol or "").strip().upper()
        if normalized_symbol and normalized_symbol not in ordered_source_symbols:
            ordered_source_symbols.append(normalized_symbol)

    if not ordered_source_symbols:
        return {}, {}

    alias_rows = session.scalars(
        select(InstrumentAlias).where(
            InstrumentAlias.provider_id == provider.id,
            InstrumentAlias.source_symbol.in_(ordered_source_symbols),
        )
    ).all()
    alias_by_symbol = {
        str(alias.source_symbol).strip().upper(): alias
        for alias in alias_rows
        if str(alias.source_symbol or "").strip()
    }

    alias_ids = [int(alias.id) for alias in alias_rows if getattr(alias, "id", None) is not None]
    if not alias_ids:
        return alias_by_symbol, {}

    series_rows = session.scalars(
        select(MarketDataSeries).where(
            MarketDataSeries.provider_id == provider.id,
            MarketDataSeries.alias_id.in_(alias_ids),
            MarketDataSeries.interval == interval,
            MarketDataSeries.adjustment_kind == "qfq",
            MarketDataSeries.session_type == "regular",
            MarketDataSeries.price_type == "trade",
        )
    ).all()
    series_by_scope = {
        _tdx_qfq_series_scope_key(
            series.alias_id,
            interval=str(series.interval),
            adjustment_kind=str(series.adjustment_kind),
            session_type=str(series.session_type),
            price_type=str(series.price_type),
        ): series
        for series in series_rows
    }
    return alias_by_symbol, series_by_scope


def _preload_tdx_qfq_action_updated_at(
    session,
    targets: list[dict[str, object]],
    action_provider,
) -> dict[int, datetime | None]:
    """只预取公司行动最近更新时间，用于在重算前快速判断是否可以跳过。"""
    if not targets:
        return {}

    ordered_instrument_ids: list[int] = []
    for item in targets:
        instrument = item["instrument"]
        if instrument.id not in ordered_instrument_ids:
            ordered_instrument_ids.append(instrument.id)

    updated_at_by_instrument: dict[int, datetime | None] = {instrument_id: None for instrument_id in ordered_instrument_ids}
    rows = session.execute(
        select(
            CorporateActionEvent.instrument_id,
            func.max(CorporateActionEvent.updated_at).label("updated_at"),
        )
        .where(
            CorporateActionEvent.provider_id == action_provider.id,
            CorporateActionEvent.instrument_id.in_(ordered_instrument_ids),
        )
        .group_by(CorporateActionEvent.instrument_id)
    ).all()
    for row in rows:
        updated_at_by_instrument[int(row.instrument_id)] = row.updated_at
    return updated_at_by_instrument


def _elapsed_ms(started_at: float) -> int:
    return max(0, int(round((perf_counter() - started_at) * 1000)))


def _can_skip_tdx_qfq_rebuild(
    *,
    force: bool,
    raw_provider,
    action_provider,
    raw_series,
    qfq_series,
    action_last_updated_at: datetime | None,
) -> bool:
    if force or qfq_series is None or raw_series is None:
        return False
    qfq_last_ingested_at = getattr(qfq_series, "last_ingested_at", None)
    raw_last_ingested_at = getattr(raw_series, "last_ingested_at", None)
    if qfq_last_ingested_at is None or raw_last_ingested_at is None:
        return False
    metadata_json = dict(getattr(qfq_series, "metadata_json", {}) or {})
    if str(metadata_json.get("raw_provider_key") or "") != str(raw_provider.provider_key):
        return False
    if int(metadata_json.get("raw_series_id") or 0) != int(raw_series.id):
        return False
    if str(metadata_json.get("action_provider_key") or "") != str(action_provider.provider_key):
        return False
    if raw_last_ingested_at > qfq_last_ingested_at:
        return False
    if action_last_updated_at is not None and action_last_updated_at > qfq_last_ingested_at:
        return False
    return True


def _load_raw_market_data_frame(session, series: MarketDataSeries) -> pd.DataFrame:
    rows = session.scalars(
        select(MarketDataBar)
        .where(MarketDataBar.series_id == series.id)
        .order_by(MarketDataBar.bar_time)
    ).all()
    if not rows:
        raise ValueError(f"原始序列没有可用于前复权重算的日线数据：series_id={series.id}")
    return pd.DataFrame(
        [
            {
                "Date": row.bar_time,
                "Open": row.open,
                "High": row.high,
                "Low": row.low,
                "Close": row.close,
                "Volume": row.volume,
                "Amount": row.turnover_amount,
            }
            for row in rows
        ]
    )


def _empty_action_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ex_date",
            "cash_dividend",
            "stock_bonus_ratio",
            "stock_conversion_ratio",
            "rights_ratio",
            "rights_price",
            "status",
        ]
    )


def _load_instrument_action_frame(session, instrument: Instrument, action_provider) -> pd.DataFrame:
    rows = session.scalars(
        select(CorporateActionEvent)
        .where(
            CorporateActionEvent.instrument_id == instrument.id,
            CorporateActionEvent.provider_id == action_provider.id,
        )
        .order_by(CorporateActionEvent.ex_date, CorporateActionEvent.announce_date)
    ).all()
    return pd.DataFrame(
        [
            {
                "ex_date": row.ex_date,
                "cash_dividend": row.cash_dividend,
                "stock_bonus_ratio": row.stock_bonus_ratio,
                "stock_conversion_ratio": row.stock_conversion_ratio,
                "rights_ratio": row.rights_ratio,
                "rights_price": row.rights_price,
                "status": row.status,
            }
            for row in rows
        ]
    )
