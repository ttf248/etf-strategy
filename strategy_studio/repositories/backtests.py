from __future__ import annotations

"""回测任务与报告仓储。"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from strategy_studio.db.models import (
    BacktestEquityCurve,
    BacktestEvent,
    BacktestJob,
    BacktestReport,
    BacktestTrade,
    Instrument,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def create_backtest_job(session: Session, payload: dict[str, object]) -> BacktestJob:
    job = BacktestJob(request_payload_json=payload, status="queued", progress_pct=0.0, runtime_details_json={})
    session.add(job)
    session.flush()
    return job


def list_backtest_jobs(session: Session, limit: int = 100) -> list[BacktestJob]:
    return session.scalars(select(BacktestJob).order_by(BacktestJob.submitted_at.desc()).limit(limit)).all()


def count_backtest_jobs_by_status(session: Session) -> dict[str, int]:
    rows = session.execute(select(BacktestJob.status, func.count()).group_by(BacktestJob.status)).all()
    return {str(status): int(count) for status, count in rows}


def count_queued_jobs_ahead(session: Session, job: BacktestJob) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(BacktestJob)
            .where(BacktestJob.status == "queued")
            .where(
                (BacktestJob.submitted_at < job.submitted_at)
                | ((BacktestJob.submitted_at == job.submitted_at) & (BacktestJob.id < job.id))
            )
        )
        or 0
    )


def get_backtest_job(session: Session, job_id: int) -> BacktestJob | None:
    return session.get(BacktestJob, job_id)


def claim_next_queued_job(session: Session) -> BacktestJob | None:
    statement = (
        select(BacktestJob)
        .where(BacktestJob.status == "queued")
        .order_by(BacktestJob.submitted_at)
        .with_for_update(skip_locked=True)
    )
    job = session.scalars(statement).first()
    if job is None:
        return None
    job.status = "running"
    job.progress_pct = 5.0
    job.started_at = utc_now()
    job.runtime_details_json = {}
    session.flush()
    return job


def mark_job_failed(session: Session, job: BacktestJob, error_message: str) -> None:
    job.status = "failed"
    job.progress_pct = 100.0
    job.error_message = error_message
    job.completed_at = utc_now()


def mark_job_cancel_requested(session: Session, job: BacktestJob) -> None:
    job.status = "cancel_requested"
    job.error_message = "用户请求取消任务。"
    session.flush()


def mark_job_cancelled(session: Session, job: BacktestJob, message: str = "任务已取消。") -> None:
    job.status = "cancelled"
    job.progress_pct = 100.0
    job.error_message = message
    job.completed_at = utc_now()
    session.flush()


def mark_job_completed(session: Session, job: BacktestJob) -> None:
    job.status = "succeeded"
    job.progress_pct = 100.0
    job.completed_at = utc_now()
    job.error_message = ""


def mark_job_progress(session: Session, job: BacktestJob, progress_pct: float) -> None:
    job.progress_pct = progress_pct


def create_backtest_report(
    session: Session,
    job: BacktestJob,
    instrument: Instrument,
    interval: str,
    strategy_kind: str,
    report_name: str,
    dataset_start: datetime,
    dataset_end: datetime,
    validation_start: str,
    summary_metrics: dict[str, object],
    parameters: dict[str, object],
    artifacts: dict[str, object],
) -> BacktestReport:
    report = BacktestReport(
        job_id=job.id,
        instrument_id=instrument.id,
        interval=interval,
        strategy_kind=strategy_kind,
        report_name=report_name,
        dataset_start=dataset_start,
        dataset_end=dataset_end,
        validation_start=validation_start,
        summary_metrics_json=summary_metrics,
        parameters_json=parameters,
        artifacts_json=artifacts,
    )
    session.add(report)
    session.flush()
    return report


def replace_report_details(
    session: Session,
    report: BacktestReport,
    equity_rows: list[dict[str, object]],
    trade_rows: list[dict[str, object]],
    event_rows: list[dict[str, object]],
) -> None:
    session.query(BacktestEquityCurve).filter(BacktestEquityCurve.report_id == report.id).delete()
    session.query(BacktestTrade).filter(BacktestTrade.report_id == report.id).delete()
    session.query(BacktestEvent).filter(BacktestEvent.report_id == report.id).delete()

    session.add_all(
        [
            BacktestEquityCurve(
                report_id=report.id,
                curve_time=row["curve_time"],
                equity=float(row["equity"]),
                drawdown_pct=float(row["drawdown_pct"]),
                return_pct=float(row["return_pct"]),
            )
            for row in equity_rows
        ]
    )
    session.add_all(
        [
            BacktestTrade(
                report_id=report.id,
                trade_time=row["trade_time"],
                side=str(row["side"]),
                price=float(row["price"]),
                quantity=int(row["quantity"]),
                amount=float(row["amount"]),
                fee=float(row["fee"]),
                slippage_cost=float(row["slippage_cost"]),
                trade_type=str(row["trade_type"]),
                note=str(row["note"]),
            )
            for row in trade_rows
        ]
    )
    session.add_all(
        [
            BacktestEvent(
                report_id=report.id,
                event_time=row["event_time"],
                event_type=str(row["event_type"]),
                price=float(row["price"]),
                payload_json=row["payload_json"],
            )
            for row in event_rows
        ]
    )


def list_reports(session: Session, limit: int = 100) -> list[BacktestReport]:
    return session.scalars(select(BacktestReport).order_by(BacktestReport.created_at.desc()).limit(limit)).all()


def get_report(session: Session, report_id: int) -> BacktestReport | None:
    return session.get(BacktestReport, report_id)
