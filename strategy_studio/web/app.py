from __future__ import annotations

"""FastAPI 应用。"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from strategy_studio.services.backtests import (
    BacktestRequest,
    bulk_cancel_backtests,
    bulk_retry_backtests,
    cancel_backtest,
    fetch_job,
    fetch_jobs,
    fetch_report_detail,
    fetch_reports,
    retry_backtest,
    submit_backtest,
)
from strategy_studio.services.market_data import (
    fetch_adjustment_segments,
    fetch_corporate_actions,
    fetch_ingestion_job_detail,
    fetch_instrument_coverages,
    fetch_instruments,
    fetch_market_data_stats,
    fetch_provider_series,
    fetch_price_bars,
    fetch_source_file_manifests,
    fetch_sync_runs,
)
from strategy_studio.services.platform import (
    fetch_database_diagnostics,
    fetch_platform_logs,
    fetch_platform_processes,
    fetch_platform_status,
    restart_platform_process,
)
from strategy_studio.services.sync import sync_market_data
from strategy_studio.services.templates import (
    create_strategy_template_entry,
    get_strategy_template_detail,
    list_strategy_templates,
    update_strategy_template_entry,
)
from strategy_studio.web.schemas import (
    BacktestBulkActionModel,
    BacktestRequestModel,
    StrategyTemplateCreateModel,
    StrategyTemplateUpdateModel,
    SyncRequestModel,
)


def create_app() -> FastAPI:
    app = FastAPI(title="Strategy Studio Platform", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/platform/status")
    def get_platform_status() -> dict[str, object]:
        return fetch_platform_status()

    @app.get("/api/platform/database-check")
    def get_platform_database_check() -> dict[str, object]:
        return fetch_database_diagnostics()

    @app.get("/api/platform/processes")
    def get_platform_processes() -> list[dict[str, object]]:
        return fetch_platform_processes()

    @app.get("/api/platform/logs")
    def get_platform_logs(service: str = "api", limit: int = 200) -> dict[str, object]:
        return fetch_platform_logs(service=service, limit=limit)

    @app.post("/api/platform/processes/{service_name}/restart")
    def post_platform_process_restart(service_name: str) -> dict[str, object]:
        try:
            return restart_platform_process(service_name)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

    @app.get("/api/market-data/instruments")
    def get_instruments() -> list[dict[str, object]]:
        return fetch_instruments()

    @app.get("/api/market-data/coverages")
    def get_coverages() -> list[dict[str, object]]:
        return fetch_instrument_coverages()

    @app.get("/api/market-data/stats")
    def get_market_stats() -> dict[str, object]:
        return fetch_market_data_stats()

    @app.get("/api/market-data/provider-series")
    def get_provider_series(provider: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        return fetch_provider_series(provider_key=provider, limit=limit)

    @app.get("/api/market-data/corporate-actions")
    def get_corporate_actions(provider: str | None = None, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        return fetch_corporate_actions(provider_key=provider, symbol=symbol, limit=limit)

    @app.get("/api/market-data/adjustment-segments")
    def get_adjustment_segments(provider: str | None = None, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        return fetch_adjustment_segments(provider_key=provider, symbol=symbol, limit=limit)

    @app.get("/api/market-data/source-file-manifests")
    def get_source_file_manifests(
        provider: str | None = None,
        symbol: str | None = None,
        interval: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        return fetch_source_file_manifests(provider_key=provider, symbol=symbol, interval=interval, limit=limit)

    @app.get("/api/market-data/ingestion-jobs/{job_id}")
    def get_ingestion_job(job_id: int) -> dict[str, object]:
        payload = fetch_ingestion_job_detail(job_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="导入任务不存在。")
        return payload

    @app.get("/api/market-data/bars")
    def get_bars(symbol: str, interval: str, start: str | None = None, end: str | None = None, limit: int = 2000) -> list[dict[str, object]]:
        return fetch_price_bars(symbol=symbol, interval=interval, start=start, end=end, limit=limit)

    @app.get("/api/market-data/sync-runs")
    def get_sync_runs(limit: int = 50) -> list[dict[str, object]]:
        return fetch_sync_runs(limit=limit)

    @app.post("/api/market-data/sync")
    def post_sync(request: SyncRequestModel) -> dict[str, object]:
        return sync_market_data(
            symbol=request.symbol,
            symbol_set=request.symbol_set,
            interval=request.interval,
            proxy=request.proxy,
            period=request.period,
            provider=request.provider,
            vipdoc_path=request.vipdoc_path,
            force=request.force,
            limit=request.limit,
        )

    @app.post("/api/backtests")
    def post_backtest(request: BacktestRequestModel) -> dict[str, object]:
        try:
            return submit_backtest(BacktestRequest(**request.model_dump()))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/backtests")
    def get_backtests(limit: int = 100) -> list[dict[str, object]]:
        return fetch_jobs(limit=limit)

    @app.post("/api/backtests/bulk-retry")
    def post_backtest_bulk_retry(request: BacktestBulkActionModel) -> dict[str, object]:
        return bulk_retry_backtests(request.job_ids)

    @app.post("/api/backtests/bulk-cancel")
    def post_backtest_bulk_cancel(request: BacktestBulkActionModel) -> dict[str, object]:
        return bulk_cancel_backtests(request.job_ids)

    @app.get("/api/backtests/{job_id}")
    def get_backtest(job_id: int) -> dict[str, object]:
        payload = fetch_job(job_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="任务不存在。")
        return payload

    @app.post("/api/backtests/{job_id}/retry")
    def post_backtest_retry(job_id: int) -> dict[str, object]:
        return retry_backtest(job_id)

    @app.post("/api/backtests/{job_id}/cancel")
    def post_backtest_cancel(job_id: int) -> dict[str, object]:
        result = cancel_backtest(job_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail="任务不存在。")
        return result

    @app.get("/api/reports")
    def get_reports(limit: int = 100) -> list[dict[str, object]]:
        return fetch_reports(limit=limit)

    @app.get("/api/reports/{report_id}")
    def get_report(report_id: int) -> dict[str, object]:
        payload = fetch_report_detail(report_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="报告不存在。")
        return payload

    @app.get("/api/templates")
    def get_templates(
        strategy_kind: str | None = None,
        interval: str | None = None,
        active_only: bool = False,
    ) -> list[dict[str, object]]:
        return list_strategy_templates(strategy_kind=strategy_kind, interval=interval, active_only=active_only)

    @app.get("/api/templates/{template_id}")
    def get_template(template_id: int) -> dict[str, object]:
        payload = get_strategy_template_detail(template_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="模板不存在。")
        return payload

    @app.post("/api/templates")
    def post_template(request: StrategyTemplateCreateModel) -> dict[str, object]:
        try:
            return create_strategy_template_entry(request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/templates/{template_id}")
    def patch_template(template_id: int, request: StrategyTemplateUpdateModel) -> dict[str, object]:
        try:
            return update_strategy_template_entry(template_id, request.model_dump(exclude_unset=True))
        except ValueError as exc:
            status = 404 if str(exc) == "模板不存在。" else 400
            raise HTTPException(status_code=status, detail=str(exc)) from exc

    return app
