from __future__ import annotations

"""回测任务 Worker。"""

from time import sleep

from loguru import logger

from strategy_studio.services.backtests import execute_next_job
from strategy_studio.services.platform import record_platform_heartbeat

_HEARTBEAT_INIT_WARNING_SHOWN = False


def _safe_heartbeat(poll_interval_seconds: int) -> None:
    global _HEARTBEAT_INIT_WARNING_SHOWN
    try:
        heartbeat_recorded = record_platform_heartbeat("worker", {"poll_interval_seconds": poll_interval_seconds})
    except Exception as exc:
        logger.warning("回测 worker 心跳写入失败: {}", exc)
        return
    if not heartbeat_recorded and not _HEARTBEAT_INIT_WARNING_SHOWN:
        _HEARTBEAT_INIT_WARNING_SHOWN = True
        logger.warning("回测 worker 心跳未启用：请执行 `py -3.13 main.py init-db` 完成数据库迁移；任务轮询会继续运行。")


def run_worker_loop(poll_interval_seconds: int = 5) -> None:
    """持续轮询并执行排队回测任务。"""
    logger.info("回测 worker 已启动，轮询间隔 {} 秒。", poll_interval_seconds)
    _safe_heartbeat(poll_interval_seconds)
    while True:
        _safe_heartbeat(poll_interval_seconds)
        try:
            job_id = execute_next_job()
        except Exception as exc:
            logger.exception("回测 worker 执行任务失败: {}", exc)
            sleep(poll_interval_seconds)
            continue
        if job_id is None:
            sleep(poll_interval_seconds)
            continue
        logger.info("回测任务执行完成: job_id={}", job_id)
