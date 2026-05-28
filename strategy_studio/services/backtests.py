from __future__ import annotations

"""异步回测服务。"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
import pandas as pd

from strategy_studio.db.session import open_session
from strategy_studio.repositories.backtests import (
    claim_next_queued_job,
    count_queued_jobs_ahead,
    create_backtest_job,
    create_backtest_report,
    get_backtest_job,
    get_report,
    mark_job_cancel_requested,
    mark_job_cancelled,
    list_backtest_jobs,
    list_reports,
    mark_job_completed,
    mark_job_failed,
    mark_job_progress,
    replace_report_details,
)
from strategy_studio.repositories.market_data import get_instrument_by_symbol, load_price_frame_from_database
from strategy_studio.settings import build_execution_config
from strategy_studio.services.templates import resolve_backtest_request_payload
from strategy_studio.workflow import run_full_workflow, run_minute_full_workflow


@dataclass(frozen=True)
class BacktestRequest:
    symbol: str
    interval: str | None = None
    strategy_kind: str | None = None
    validation_start: str | None = None
    lookback_days: int | None = None
    validation_ratio: float | None = None
    execution_profile: str | None = None
    commission_bps: float | None = None
    slippage_bps: float | None = None
    max_position_ratio: float | None = None
    stop_loss_pct: float | None = None
    cooldown_bars: int | None = None
    benchmark: str | None = None
    left_side_policy: str | None = None
    force_exit_loss_pct: float | None = None
    jobs: int | None = None
    template_id: int | None = None
    template_snapshot: dict[str, object] | None = None
    parameter_space: dict[str, object] | None = None


def _is_intraday(interval: str) -> bool:
    return interval != "1d"


def _job_payload(request: BacktestRequest) -> dict[str, object]:
    with open_session() as session:
        return resolve_backtest_request_payload(request, session=session)


def submit_backtest(request: BacktestRequest) -> dict[str, object]:
    with open_session() as session:
        job = create_backtest_job(session, _job_payload(request))
        _set_job_runtime(
            session,
            job,
            stage_key="queued",
            message="任务已提交，等待进入执行队列。",
            progress_pct=0.0,
            requested_parallelism=int(job.request_payload_json.get("jobs") or 1),
        )
        session.commit()
        return {"job_id": job.id, "status": job.status}


def _database_source_label(symbol: str, interval: str) -> str:
    return f"database://price_bars/{symbol.upper()}/{interval}"


_RUNTIME_STAGE_ORDER = (
    ("queued", "等待执行", 0.0, 0),
    ("claimed", "已领取任务", 5.0, 1),
    ("loading_market_data", "读取行情数据", 20.0, 2),
    ("running_research", "执行策略回测", 45.0, 3),
    ("writing_report", "写入报告结果", 75.0, 4),
    ("finalizing", "整理结果并收尾", 92.0, 5),
    ("succeeded", "结果已生成", 100.0, 6),
    ("failed", "执行失败", 100.0, 6),
    ("cancel_requested", "等待取消", 100.0, 6),
    ("cancelled", "已取消", 100.0, 6),
)
_RUNTIME_STAGE_MAP = {key: {"label": label, "progress": progress, "step": step} for key, label, progress, step in _RUNTIME_STAGE_ORDER}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _seconds_between(started_at: datetime | None, finished_at: datetime | None = None) -> int | None:
    if started_at is None:
        return None
    end_time = finished_at or _utc_now()
    return max(0, int((end_time - started_at).total_seconds()))


def _estimate_eta_seconds(progress_pct: float, elapsed_seconds: int | None) -> int | None:
    if elapsed_seconds is None or progress_pct <= 0 or progress_pct >= 100:
        return 0 if progress_pct >= 100 else None
    estimated_total = elapsed_seconds / max(progress_pct / 100.0, 0.01)
    return max(0, int(round(estimated_total - elapsed_seconds)))


def _resolve_effective_parallelism(
    requested_jobs: int | None,
    max_optimization_workers: int | None = None,
    worker_concurrency: int = 1,
) -> int:
    requested = max(1, int(requested_jobs or 1))
    cpu_count = max(1, os.cpu_count() or 1)
    per_job_budget = max(1, cpu_count // max(1, worker_concurrency))
    if max_optimization_workers is None:
        return min(requested, per_job_budget)
    return min(requested, max(1, int(max_optimization_workers)), per_job_budget)


def _build_runtime_details(
    job,
    *,
    stage_key: str,
    message: str,
    worker_name: str | None = None,
    requested_parallelism: int | None = None,
    effective_parallelism: int | None = None,
    worker_concurrency: int | None = None,
    max_optimization_workers: int | None = None,
) -> dict[str, object]:
    stage = _RUNTIME_STAGE_MAP[stage_key]
    previous = dict(job.runtime_details_json or {})
    elapsed_seconds = _seconds_between(job.started_at, job.completed_at if stage_key in {"succeeded", "failed", "cancelled"} else None)
    eta_seconds = _estimate_eta_seconds(float(job.progress_pct), elapsed_seconds)
    details: dict[str, object] = {
        **previous,
        "stage_key": stage_key,
        "stage_label": stage["label"],
        "stage_message": message,
        "current_step": int(stage["step"]),
        "total_steps": 6,
        "elapsed_seconds": elapsed_seconds,
        "eta_seconds": eta_seconds,
        "updated_at": _utc_now().isoformat(sep=" "),
    }
    if worker_name is not None:
        details["worker_name"] = worker_name
    if requested_parallelism is not None:
        details["requested_parallelism"] = int(requested_parallelism)
    if effective_parallelism is not None:
        details["effective_parallelism"] = int(effective_parallelism)
    if worker_concurrency is not None:
        details["worker_concurrency"] = int(worker_concurrency)
    if max_optimization_workers is not None:
        details["max_optimization_workers"] = int(max_optimization_workers)
    if effective_parallelism is not None:
        details["resource_summary"] = (
            f"当前任务申请 {requested_parallelism or effective_parallelism} 组并行寻参，"
            f"实际限制为 {effective_parallelism} 组；平台同时执行上限 {worker_concurrency or 1} 个任务。"
        )
    return details


def _set_job_runtime(
    session,
    job,
    *,
    stage_key: str,
    message: str,
    progress_pct: float | None = None,
    worker_name: str | None = None,
    requested_parallelism: int | None = None,
    effective_parallelism: int | None = None,
    worker_concurrency: int | None = None,
    max_optimization_workers: int | None = None,
) -> None:
    if progress_pct is not None:
        mark_job_progress(session, job, progress_pct)
    job.runtime_details_json = _build_runtime_details(
        job,
        stage_key=stage_key,
        message=message,
        worker_name=worker_name,
        requested_parallelism=requested_parallelism,
        effective_parallelism=effective_parallelism,
        worker_concurrency=worker_concurrency,
        max_optimization_workers=max_optimization_workers,
    )


def _serialize_runtime(job, session) -> dict[str, object]:
    details = dict(job.runtime_details_json or {})
    if job.status == "queued":
        details.setdefault("stage_key", "queued")
        details.setdefault("stage_label", "等待执行")
        details.setdefault("stage_message", "任务已入队，等待 worker 领取。")
        details["queue_position"] = count_queued_jobs_ahead(session, job) + 1
    details.setdefault("elapsed_seconds", _seconds_between(job.started_at, job.completed_at))
    details.setdefault("eta_seconds", _estimate_eta_seconds(job.progress_pct, details.get("elapsed_seconds")))
    return details


def _normalize_artifacts(
    workflow_result: dict[str, object],
    template_snapshot: dict[str, object] | None = None,
) -> dict[str, object]:
    def _stringify(value: object) -> object:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, pd.Timestamp):
            return value.isoformat(sep=" ")
        if isinstance(value, datetime):
            return value.isoformat(sep=" ")
        if hasattr(value, "item"):
            return value.item()
        if isinstance(value, dict):
            return {key: _stringify(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_stringify(item) for item in value]
        return value

    payload = {
        "storage_mode": "database_only",
        "data_source": "database",
        "artifact_transport": "embedded_database_rows",
        "in_sample_window": asdict(workflow_result["optimization"]["decline_window"]),
        "template_snapshot": template_snapshot,
    }
    return _stringify(payload)


def _to_jsonable(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat(sep=" ")
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if hasattr(value, "item"):
        return value.item()
    return value


def _build_equity_rows(run_result: dict[str, object]) -> list[dict[str, object]]:
    curve = run_result["equity_curve"].copy().reset_index()
    if curve.empty:
        return []
    date_column = curve.columns[0]
    curve.rename(columns={date_column: "curve_time"}, inplace=True)
    curve["curve_time"] = pd.to_datetime(curve["curve_time"])
    capital = float(run_result["summary"].get("TotalCapital", 200000.0))
    curve["return_pct"] = (curve["Equity"] / capital - 1) * 100
    curve["drawdown_pct"] = curve["DrawdownPct"] * 100
    return [
        {
            "curve_time": row["curve_time"].to_pydatetime(),
            "equity": float(row["Equity"]),
            "drawdown_pct": float(row["drawdown_pct"]),
            "return_pct": float(row["return_pct"]),
        }
        for row in curve.to_dict(orient="records")
    ]


def _build_trade_rows(run_result: dict[str, object]) -> list[dict[str, object]]:
    trades = run_result["trades"].copy()
    if trades.empty:
        return []
    trade_time_column = "ExitTime" if "ExitTime" in trades.columns else trades.columns[0]
    rows: list[dict[str, object]] = []
    for row in trades.to_dict(orient="records"):
        trade_time = pd.to_datetime(row.get(trade_time_column))
        size = int(row.get("Size", row.get("Quantity", 0)) or 0)
        exit_price = float(row.get("ExitPrice", row.get("Price", row.get("Close", 0.0))) or 0.0)
        amount = abs(size) * exit_price
        rows.append(
            {
                "trade_time": trade_time.to_pydatetime(),
                "side": "sell" if size >= 0 else "buy",
                "price": exit_price,
                "quantity": abs(size),
                "amount": amount,
                "fee": float(row.get("Commission", 0.0) or 0.0),
                "slippage_cost": float(row.get("SlippageCost", 0.0) or 0.0),
                "trade_type": str(row.get("Tag", row.get("TradeType", "closed_trade"))),
                "note": str(row.get("PnL", "")),
            }
        )
    return rows


def _build_event_rows(run_result: dict[str, object]) -> list[dict[str, object]]:
    events = run_result["events"].copy()
    if events.empty:
        return []
    rows: list[dict[str, object]] = []
    for item in events.to_dict(orient="records"):
        event_time = pd.to_datetime(item.get("Date"))
        rows.append(
            {
                "event_time": event_time.to_pydatetime(),
                "event_type": str(item.get("EventType", "event")),
                "price": float(item.get("Price", 0.0) or 0.0),
                "payload_json": _to_jsonable(item),
            }
        )
    return rows


def _requeue_failed_job(job_id: int) -> int | None:
    with open_session() as session:
        job = get_backtest_job(session, job_id)
        if job is None:
            return None
        if job.status not in {"queued", "failed"}:
            return job.id
        if job.status == "failed":
            job.status = "queued"
            job.progress_pct = 0.0
            job.started_at = None
            job.completed_at = None
            job.error_message = ""
            _set_job_runtime(
                session,
                job,
                stage_key="queued",
                message="任务已重新入队，等待 worker 再次执行。",
                progress_pct=0.0,
                requested_parallelism=int(job.request_payload_json.get("jobs") or 1),
            )
            session.commit()
    return job_id


def _build_database_report_name(job_id: int, symbol: str, interval: str, strategy_kind: str | None) -> str:
    symbol_slug = symbol.lower().replace(".", "_")
    strategy_slug = (strategy_kind or "strategy").lower().replace(".", "_")
    return f"job_{job_id}_{symbol_slug}_{interval}_{strategy_slug}"


def _cancel_if_requested(session, job) -> bool:
    session.refresh(job)
    if job.status != "cancel_requested":
        return False
    mark_job_cancelled(session, job)
    _set_job_runtime(
        session,
        job,
        stage_key="cancelled",
        message="任务已按取消请求停止，不会继续执行。",
        progress_pct=100.0,
    )
    session.commit()
    return True


def execute_next_job(
    preferred_job_id: int | None = None,
    worker_name: str | None = None,
    max_optimization_workers: int | None = None,
    worker_concurrency: int = 1,
) -> int | None:
    with open_session() as session:
        if preferred_job_id is not None:
            job = get_backtest_job(session, preferred_job_id)
            if job is None or job.status != "queued":
                return None
            job.status = "running"
            job.progress_pct = 5.0
            job.started_at = _utc_now()
            _set_job_runtime(
                session,
                job,
                stage_key="claimed",
                message="任务已被 worker 领取，准备读取数据库行情。",
                progress_pct=5.0,
                worker_name=worker_name,
                requested_parallelism=int(job.request_payload_json.get("jobs") or 1),
                worker_concurrency=worker_concurrency,
                max_optimization_workers=max_optimization_workers,
            )
            target_job_id = job.id
            session.commit()
        else:
            job = claim_next_queued_job(session)
            if job is None:
                session.commit()
                return None
            _set_job_runtime(
                session,
                job,
                stage_key="claimed",
                message="任务已被 worker 领取，准备读取数据库行情。",
                progress_pct=5.0,
                worker_name=worker_name,
                requested_parallelism=int(job.request_payload_json.get("jobs") or 1),
                worker_concurrency=worker_concurrency,
                max_optimization_workers=max_optimization_workers,
            )
            target_job_id = job.id
            session.commit()

    with open_session() as session:
        job = get_backtest_job(session, target_job_id)
        if job is None:
            return None
        payload = BacktestRequest(**job.request_payload_json)
        try:
            if _cancel_if_requested(session, job):
                return job.id
            effective_parallelism = _resolve_effective_parallelism(
                payload.jobs,
                max_optimization_workers=max_optimization_workers,
                worker_concurrency=worker_concurrency,
            )
            _set_job_runtime(
                session,
                job,
                stage_key="loading_market_data",
                message="开始读取数据库中的历史行情与标的元数据。",
                progress_pct=20.0,
                worker_name=worker_name,
                requested_parallelism=payload.jobs or 1,
                effective_parallelism=effective_parallelism,
                worker_concurrency=worker_concurrency,
                max_optimization_workers=max_optimization_workers,
            )
            session.commit()

            price_frame = load_price_frame_from_database(session, payload.symbol, payload.interval)
            instrument = get_instrument_by_symbol(session, payload.symbol)
            if instrument is None:
                raise ValueError(f"数据库中不存在标的: {payload.symbol}")
            execution_config = build_execution_config(
                profile=payload.execution_profile,
                commission_bps=payload.commission_bps,
                slippage_bps=payload.slippage_bps,
                max_position_ratio=payload.max_position_ratio,
                stop_loss_pct=payload.stop_loss_pct,
                cooldown_bars=payload.cooldown_bars,
                benchmark=payload.benchmark,
                left_side_policy=payload.left_side_policy,
                force_exit_loss_pct=payload.force_exit_loss_pct,
            )
            database_source = _database_source_label(payload.symbol, payload.interval)

            if _cancel_if_requested(session, job):
                return job.id
            _set_job_runtime(
                session,
                job,
                stage_key="running_research",
                message="正在跑寻参与验证流程，耗时通常主要集中在这一阶段。",
                progress_pct=45.0,
                worker_name=worker_name,
                requested_parallelism=payload.jobs or 1,
                effective_parallelism=effective_parallelism,
                worker_concurrency=worker_concurrency,
                max_optimization_workers=max_optimization_workers,
            )
            session.commit()
            workflow_result = (
                run_minute_full_workflow(
                    data_path=database_source,
                    symbol=payload.symbol,
                    interval=payload.interval,
                    validation_ratio=payload.validation_ratio,
                    strategy_kind=payload.strategy_kind,
                    execution_config=execution_config,
                    jobs=effective_parallelism,
                    parameter_space=payload.parameter_space,
                    data=price_frame,
                )
                if _is_intraday(payload.interval)
                else run_full_workflow(
                    data_path=database_source,
                    symbol=payload.symbol,
                    validation_start=payload.validation_start,
                    lookback_days=payload.lookback_days,
                    strategy_kind=payload.strategy_kind,
                    execution_config=execution_config,
                    jobs=effective_parallelism,
                    parameter_space=payload.parameter_space,
                    data=price_frame,
                )
            )
            if _cancel_if_requested(session, job):
                return job.id
            _set_job_runtime(
                session,
                job,
                stage_key="writing_report",
                message="寻参与验证已经完成，正在把摘要、曲线和明细写回数据库。",
                progress_pct=75.0,
                worker_name=worker_name,
                requested_parallelism=payload.jobs or 1,
                effective_parallelism=effective_parallelism,
                worker_concurrency=worker_concurrency,
                max_optimization_workers=max_optimization_workers,
            )
            session.commit()

            best_summary = workflow_result["optimization"]["best_run"]["summary"]
            validation_summary = workflow_result["validation"]["run"]["summary"]
            report = create_backtest_report(
                session=session,
                job=job,
                instrument=instrument,
                interval=payload.interval,
                strategy_kind=payload.strategy_kind,
                report_name=_build_database_report_name(job.id, payload.symbol, payload.interval, payload.strategy_kind),
                dataset_start=pd.Timestamp(best_summary["StartDate"]).to_pydatetime(),
                dataset_end=pd.Timestamp(validation_summary["EndDate"]).to_pydatetime(),
                validation_start=payload.validation_start if not _is_intraday(payload.interval) else str(payload.validation_ratio),
                summary_metrics={
                    "optimization": _to_jsonable(best_summary),
                    "validation": _to_jsonable(validation_summary),
                },
                parameters={key: _to_jsonable(value) for key, value in best_summary.items() if isinstance(key, str)},
                artifacts=_normalize_artifacts(
                    workflow_result,
                    template_snapshot=payload.template_snapshot,
                ),
            )
            replace_report_details(
                session,
                report=report,
                equity_rows=_build_equity_rows(workflow_result["validation"]["run"]),
                trade_rows=_build_trade_rows(workflow_result["validation"]["run"]),
                event_rows=_build_event_rows(workflow_result["validation"]["run"]),
            )
            _set_job_runtime(
                session,
                job,
                stage_key="finalizing",
                message="结果已入库，正在整理任务状态与报告入口。",
                progress_pct=92.0,
                worker_name=worker_name,
                requested_parallelism=payload.jobs or 1,
                effective_parallelism=effective_parallelism,
                worker_concurrency=worker_concurrency,
                max_optimization_workers=max_optimization_workers,
            )
            mark_job_completed(session, job)
            _set_job_runtime(
                session,
                job,
                stage_key="succeeded",
                message="回测已完成，可直接打开报告查看收益、回撤和交易节奏。",
                progress_pct=100.0,
                worker_name=worker_name,
                requested_parallelism=payload.jobs or 1,
                effective_parallelism=effective_parallelism,
                worker_concurrency=worker_concurrency,
                max_optimization_workers=max_optimization_workers,
            )
            session.commit()
            return job.id
        except Exception as exc:
            session.rollback()
            job = get_backtest_job(session, job.id)
            if job is not None:
                mark_job_failed(session, job, str(exc))
                _set_job_runtime(
                    session,
                    job,
                    stage_key="failed",
                    message="回测执行失败，请先查看错误信息，再决定是否按原配置重跑。",
                    progress_pct=100.0,
                    worker_name=worker_name,
                    requested_parallelism=payload.jobs or 1,
                    worker_concurrency=worker_concurrency,
                    max_optimization_workers=max_optimization_workers,
                )
                session.commit()
            return None


def retry_backtest(job_id: int) -> dict[str, object]:
    queued_job_id = _requeue_failed_job(job_id)
    return {"job_id": job_id, "queued_job_id": queued_job_id}


def cancel_backtest(job_id: int) -> dict[str, object]:
    with open_session() as session:
        job = get_backtest_job(session, job_id)
        if job is None:
            return {"job_id": job_id, "status": "not_found", "changed": False}
        if job.status == "queued":
            mark_job_cancelled(session, job)
            _set_job_runtime(
                session,
                job,
                stage_key="cancelled",
                message="任务已从队列中移除，不会再继续执行。",
                progress_pct=100.0,
            )
            session.commit()
            return {"job_id": job_id, "status": "cancelled", "changed": True}
        if job.status == "running":
            mark_job_cancel_requested(session, job)
            _set_job_runtime(
                session,
                job,
                stage_key="cancel_requested",
                message="已经收到取消请求，当前任务会在安全检查点尽快停下。",
                progress_pct=job.progress_pct,
            )
            session.commit()
            return {"job_id": job_id, "status": "cancel_requested", "changed": True}
        return {"job_id": job_id, "status": job.status, "changed": False}


def bulk_retry_backtests(job_ids: list[int]) -> dict[str, object]:
    results = [retry_backtest(job_id) for job_id in job_ids]
    return {"results": results}


def bulk_cancel_backtests(job_ids: list[int]) -> dict[str, object]:
    results = [cancel_backtest(job_id) for job_id in job_ids]
    return {"results": results}


def fetch_jobs(limit: int = 100) -> list[dict[str, object]]:
    with open_session() as session:
        jobs = list_backtest_jobs(session, limit=limit)
        return [
            {
                "id": job.id,
                "status": job.status,
                "job_type": job.job_type,
                "request_payload": job.request_payload_json,
                "progress_pct": job.progress_pct,
                "runtime_details": _serialize_runtime(job, session),
                "submitted_at": job.submitted_at.isoformat(sep=" "),
                "started_at": job.started_at.isoformat(sep=" ") if job.started_at else "",
                "completed_at": job.completed_at.isoformat(sep=" ") if job.completed_at else "",
                "error_message": job.error_message,
                "reports": [
                    {
                        "id": report.id,
                        "report_name": report.report_name,
                        "strategy_kind": report.strategy_kind,
                        "interval": report.interval,
                    }
                    for report in job.reports
                ],
            }
            for job in jobs
        ]


def fetch_job(job_id: int) -> dict[str, object] | None:
    with open_session() as session:
        job = get_backtest_job(session, job_id)
        if job is None:
            return None
        return {
            "id": job.id,
            "status": job.status,
            "job_type": job.job_type,
            "request_payload": job.request_payload_json,
            "progress_pct": job.progress_pct,
            "runtime_details": _serialize_runtime(job, session),
            "submitted_at": job.submitted_at.isoformat(sep=" "),
            "started_at": job.started_at.isoformat(sep=" ") if job.started_at else "",
            "completed_at": job.completed_at.isoformat(sep=" ") if job.completed_at else "",
            "error_message": job.error_message,
            "reports": [
                {
                    "id": report.id,
                    "report_name": report.report_name,
                    "strategy_kind": report.strategy_kind,
                    "interval": report.interval,
                }
                for report in job.reports
            ],
        }


def fetch_reports(limit: int = 100) -> list[dict[str, object]]:
    with open_session() as session:
        reports = list_reports(session, limit=limit)
        return [
            {
                "id": report.id,
                "job_id": report.job_id,
                "symbol": report.instrument.symbol,
                "name": report.instrument.name,
                "interval": report.interval,
                "strategy_kind": report.strategy_kind,
                "report_name": report.report_name,
                "dataset_start": report.dataset_start.isoformat(sep=" "),
                "dataset_end": report.dataset_end.isoformat(sep=" "),
                "created_at": report.created_at.isoformat(sep=" "),
                "summary_metrics": report.summary_metrics_json,
            }
            for report in reports
        ]


def fetch_report_detail(report_id: int) -> dict[str, object] | None:
    with open_session() as session:
        report = get_report(session, report_id)
        if report is None:
            return None
        return {
            "id": report.id,
            "job_id": report.job_id,
            "symbol": report.instrument.symbol,
            "name": report.instrument.name,
            "interval": report.interval,
            "strategy_kind": report.strategy_kind,
            "report_name": report.report_name,
            "dataset_start": report.dataset_start.isoformat(sep=" "),
            "dataset_end": report.dataset_end.isoformat(sep=" "),
            "created_at": report.created_at.isoformat(sep=" "),
            "summary_metrics": report.summary_metrics_json,
            "parameters": report.parameters_json,
            "artifacts": report.artifacts_json,
            "equity_curve": [
                {
                    "curve_time": row.curve_time.isoformat(sep=" "),
                    "equity": row.equity,
                    "drawdown_pct": row.drawdown_pct,
                    "return_pct": row.return_pct,
                }
                for row in sorted(report.equity_curves, key=lambda item: item.curve_time)
            ],
            "trades": [
                {
                    "trade_time": row.trade_time.isoformat(sep=" "),
                    "side": row.side,
                    "price": row.price,
                    "quantity": row.quantity,
                    "amount": row.amount,
                    "fee": row.fee,
                    "slippage_cost": row.slippage_cost,
                    "trade_type": row.trade_type,
                    "note": row.note,
                }
                for row in sorted(report.trades, key=lambda item: item.trade_time)
            ],
            "events": [
                {
                    "event_time": row.event_time.isoformat(sep=" "),
                    "event_type": row.event_type,
                    "price": row.price,
                    "payload": row.payload_json,
                }
                for row in sorted(report.events, key=lambda item: item.event_time)
            ],
        }
