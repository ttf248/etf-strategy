from __future__ import annotations

"""回测任务 Worker。"""

from time import sleep

from loguru import logger

from etf_strategy.services.backtests import execute_next_job


def run_worker_loop(poll_interval_seconds: int = 5) -> None:
    """持续轮询并执行排队回测任务。"""
    logger.info("回测 worker 已启动，轮询间隔 {} 秒。", poll_interval_seconds)
    while True:
        job_id = execute_next_job()
        if job_id is None:
            sleep(poll_interval_seconds)
            continue
        logger.info("回测任务执行完成: job_id={}", job_id)

