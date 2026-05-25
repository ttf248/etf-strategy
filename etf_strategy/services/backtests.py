from __future__ import annotations

"""异步回测服务。"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from etf_strategy.db.session import open_session
from etf_strategy.db.settings import load_platform_settings
from etf_strategy.reporting import build_minute_report_markdown, build_report_markdown
from etf_strategy.repositories.backtests import (
    claim_next_queued_job,
    create_backtest_job,
    create_backtest_report,
    get_backtest_job,
    get_report,
    list_backtest_jobs,
    list_reports,
    mark_job_completed,
    mark_job_failed,
    mark_job_progress,
    replace_report_details,
)
from etf_strategy.repositories.market_data import get_instrument_by_symbol, load_price_frame_from_database
from etf_strategy.settings import build_execution_config
from etf_strategy.workflow import run_full_workflow, run_minute_full_workflow


@dataclass(frozen=True)
class BacktestRequest:
    symbol: str
    interval: str
    strategy_kind: str = "grid"
    validation_start: str = "2026-01-01"
    lookback_days: int = 120
    validation_ratio: float = 0.25
    execution_profile: str = "realistic"
    commission_bps: float | None = None
    slippage_bps: float | None = None
    max_position_ratio: float | None = None
    stop_loss_pct: float | None = None
    cooldown_bars: int | None = None
    benchmark: str | None = None
    left_side_policy: str | None = None
    force_exit_loss_pct: float | None = None
    jobs: int = 1


def _is_intraday(interval: str) -> bool:
    return interval != "1d"


def _job_payload(request: BacktestRequest) -> dict[str, object]:
    return asdict(request)


def submit_backtest(request: BacktestRequest) -> dict[str, object]:
    with open_session() as session:
        job = create_backtest_job(session, _job_payload(request))
        session.commit()
        return {"job_id": job.id, "status": job.status}


def _pseudo_data_path(symbol: str, interval: str) -> Path:
    return Path("db") / f"{symbol.lower().replace('.', '_')}_{interval}.csv"


def _normalize_artifacts(workflow_result: dict[str, object], report_path: Path) -> dict[str, object]:
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
        "combined_summary_path": workflow_result.get("combined_summary_path"),
        "optimization_paths": workflow_result["optimization"].get("best_paths", {}),
        "validation_paths": workflow_result["validation"].get("paths", {}),
        "report_path": report_path,
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
            job.error_message = ""
            session.commit()
    return job_id


def execute_next_job(preferred_job_id: int | None = None) -> int | None:
    settings = load_platform_settings()
    with open_session() as session:
        if preferred_job_id is not None:
            job = get_backtest_job(session, preferred_job_id)
            if job is None or job.status != "queued":
                return None
            job.status = "running"
            job.progress_pct = 5.0
            job.started_at = datetime.now(UTC)
            session.commit()
        else:
            job = claim_next_queued_job(session)
            if job is None:
                session.commit()
                return None
            session.commit()

    with open_session() as session:
        job = get_backtest_job(session, preferred_job_id or int(job.id))
        if job is None:
            return None
        payload = BacktestRequest(**job.request_payload_json)
        try:
            mark_job_progress(session, job, 20.0)
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
            output_dir = settings.output_dir / f"job_{job.id}"
            report_dir = settings.report_dir / payload.symbol.lower().replace(".", "_") / payload.interval
            pseudo_data_path = _pseudo_data_path(payload.symbol, payload.interval)

            mark_job_progress(session, job, 45.0)
            session.commit()
            workflow_result = (
                run_minute_full_workflow(
                    data_path=pseudo_data_path,
                    symbol=payload.symbol,
                    output_dir=output_dir,
                    interval=payload.interval,
                    validation_ratio=payload.validation_ratio,
                    strategy_kind=payload.strategy_kind,
                    execution_config=execution_config,
                    jobs=payload.jobs,
                    data=price_frame,
                )
                if _is_intraday(payload.interval)
                else run_full_workflow(
                    data_path=pseudo_data_path,
                    symbol=payload.symbol,
                    output_dir=output_dir,
                    validation_start=payload.validation_start,
                    lookback_days=payload.lookback_days,
                    strategy_kind=payload.strategy_kind,
                    execution_config=execution_config,
                    jobs=payload.jobs,
                    data=price_frame,
                )
            )
            mark_job_progress(session, job, 75.0)
            session.commit()

            report_path = (
                build_minute_report_markdown(workflow_result, report_dir=report_dir)
                if _is_intraday(payload.interval)
                else build_report_markdown(workflow_result, report_dir=report_dir)
            )
            best_summary = workflow_result["optimization"]["best_run"]["summary"]
            validation_summary = workflow_result["validation"]["run"]["summary"]
            report = create_backtest_report(
                session=session,
                job=job,
                instrument=instrument,
                interval=payload.interval,
                strategy_kind=payload.strategy_kind,
                report_name=report_path.name,
                dataset_start=pd.Timestamp(best_summary["StartDate"]).to_pydatetime(),
                dataset_end=pd.Timestamp(validation_summary["EndDate"]).to_pydatetime(),
                validation_start=payload.validation_start if not _is_intraday(payload.interval) else str(payload.validation_ratio),
                summary_metrics={
                    "optimization": _to_jsonable(best_summary),
                    "validation": _to_jsonable(validation_summary),
                },
                parameters={key: _to_jsonable(value) for key, value in best_summary.items() if isinstance(key, str)},
                artifacts=_normalize_artifacts(workflow_result, report_path=report_path),
            )
            replace_report_details(
                session,
                report=report,
                equity_rows=_build_equity_rows(workflow_result["validation"]["run"]),
                trade_rows=_build_trade_rows(workflow_result["validation"]["run"]),
                event_rows=_build_event_rows(workflow_result["validation"]["run"]),
            )
            mark_job_completed(session, job)
            session.commit()
            return job.id
        except Exception as exc:
            session.rollback()
            job = get_backtest_job(session, job.id)
            if job is not None:
                mark_job_failed(session, job, str(exc))
                session.commit()
            return None


def retry_backtest(job_id: int) -> dict[str, object]:
    queued_job_id = _requeue_failed_job(job_id)
    return {"job_id": job_id, "queued_job_id": queued_job_id}


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
                "submitted_at": job.submitted_at.isoformat(sep=" "),
                "started_at": job.started_at.isoformat(sep=" ") if job.started_at else "",
                "completed_at": job.completed_at.isoformat(sep=" ") if job.completed_at else "",
                "error_message": job.error_message,
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
