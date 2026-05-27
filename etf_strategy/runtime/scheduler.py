from __future__ import annotations

"""定时同步调度器。"""

from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger

from etf_strategy.db.settings import load_platform_settings
from etf_strategy.services.platform import record_platform_heartbeat
from etf_strategy.services.sync import sync_market_data


def _safe_heartbeat() -> None:
    try:
        record_platform_heartbeat("scheduler", {"timezone": "Asia/Shanghai"})
    except Exception as exc:
        logger.warning("调度器心跳写入失败: {}", exc)


def run_scheduler(proxy: str | None = None) -> None:
    """启动常驻调度器。"""
    settings = load_platform_settings()
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(_safe_heartbeat, "interval", seconds=30, id="scheduler_heartbeat", replace_existing=True)
    scheduler.add_job(
        sync_market_data,
        "cron",
        hour=18,
        minute=5,
        kwargs={"symbol": None, "interval": "1d", "proxy": proxy, "period": None},
        id="daily_bars_sync",
        replace_existing=True,
    )
    scheduler.add_job(
        sync_market_data,
        "cron",
        hour=18,
        minute=15,
        kwargs={"symbol": None, "interval": "15m", "proxy": proxy, "period": "60d"},
        id="minute_15m_sync",
        replace_existing=True,
    )
    scheduler.add_job(
        sync_market_data,
        "cron",
        hour=18,
        minute=25,
        kwargs={"symbol": None, "interval": "1m", "proxy": proxy, "period": "7d"},
        id="minute_1m_sync",
        replace_existing=True,
    )
    logger.info(
        "调度器已启动: db={} api={}:{} intervals={}",
        settings.database.url,
        settings.api_host,
        settings.api_port,
        settings.sync_intervals,
    )
    _safe_heartbeat()
    scheduler.start()
