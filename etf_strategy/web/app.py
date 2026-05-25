from __future__ import annotations

"""FastAPI 应用。"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from etf_strategy.services.backtests import (
    BacktestRequest,
    fetch_job,
    fetch_jobs,
    fetch_report_detail,
    fetch_reports,
    retry_backtest,
    submit_backtest,
)
from etf_strategy.services.market_data import (
    fetch_instrument_coverages,
    fetch_instruments,
    fetch_market_data_stats,
    fetch_price_bars,
    fetch_sync_runs,
)
from etf_strategy.services.sync import sync_market_data
from etf_strategy.web.schemas import BacktestRequestModel, SyncRequestModel


def create_app() -> FastAPI:
    app = FastAPI(title="ETF Strategy Platform", version="1.0.0")
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

    @app.get("/api/market-data/instruments")
    def get_instruments() -> list[dict[str, object]]:
        return fetch_instruments()

    @app.get("/api/market-data/coverages")
    def get_coverages() -> list[dict[str, object]]:
        return fetch_instrument_coverages()

    @app.get("/api/market-data/stats")
    def get_market_stats() -> dict[str, object]:
        return fetch_market_data_stats()

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
            interval=request.interval,
            proxy=request.proxy,
            period=request.period,
        )

    @app.post("/api/backtests")
    def post_backtest(request: BacktestRequestModel) -> dict[str, object]:
        return submit_backtest(BacktestRequest(**request.model_dump()))

    @app.get("/api/backtests")
    def get_backtests(limit: int = 100) -> list[dict[str, object]]:
        return fetch_jobs(limit=limit)

    @app.get("/api/backtests/{job_id}")
    def get_backtest(job_id: int) -> dict[str, object]:
        payload = fetch_job(job_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="任务不存在。")
        return payload

    @app.post("/api/backtests/{job_id}/retry")
    def post_backtest_retry(job_id: int) -> dict[str, object]:
        return retry_backtest(job_id)

    @app.get("/api/reports")
    def get_reports(limit: int = 100) -> list[dict[str, object]]:
        return fetch_reports(limit=limit)

    @app.get("/api/reports/{report_id}")
    def get_report(report_id: int) -> dict[str, object]:
        payload = fetch_report_detail(report_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="报告不存在。")
        return payload

    return app
