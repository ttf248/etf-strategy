from __future__ import annotations

"""回测任务 Worker。"""

from concurrent.futures import Future, ThreadPoolExecutor
from time import sleep

from loguru import logger

from strategy_studio.db.settings import load_platform_settings
from strategy_studio.services.backtests import execute_next_job
from strategy_studio.services.platform import record_platform_heartbeat

_HEARTBEAT_INIT_WARNING_SHOWN = False


def _safe_heartbeat(
    poll_interval_seconds: int,
    max_concurrent_jobs: int,
    max_optimization_workers: int,
    active_jobs: int,
) -> None:
    global _HEARTBEAT_INIT_WARNING_SHOWN
    try:
        heartbeat_recorded = record_platform_heartbeat(
            "worker",
            {
                "poll_interval_seconds": poll_interval_seconds,
                "max_concurrent_jobs": max_concurrent_jobs,
                "max_optimization_workers": max_optimization_workers,
                "active_jobs": active_jobs,
            },
        )
    except Exception as exc:
        logger.warning("回测 worker 心跳写入失败: {}", exc)
        return
    if not heartbeat_recorded and not _HEARTBEAT_INIT_WARNING_SHOWN:
        _HEARTBEAT_INIT_WARNING_SHOWN = True
        logger.warning("回测 worker 心跳未启用：请执行 `py -3.13 main.py init-db` 完成数据库迁移；任务轮询会继续运行。")


def run_worker_loop(
    poll_interval_seconds: int = 5,
    max_concurrent_jobs: int | None = None,
    max_optimization_workers: int | None = None,
) -> None:
    """持续轮询并执行排队回测任务。"""
    settings = load_platform_settings()
    effective_concurrency = max(1, int(max_concurrent_jobs or settings.worker_max_concurrent_jobs))
    effective_optimization_workers = max(
        1,
        int(max_optimization_workers or settings.worker_max_optimization_workers),
    )
    logger.info(
        "回测 worker 已启动，轮询间隔 {} 秒，同时执行上限 {}，单任务寻参上限 {}。",
        poll_interval_seconds,
        effective_concurrency,
        effective_optimization_workers,
    )
    free_slots = list(range(1, effective_concurrency + 1))
    futures: dict[Future[int | None], int] = {}
    with ThreadPoolExecutor(max_workers=effective_concurrency, thread_name_prefix="backtest-worker") as executor:
        while True:
            completed = [future for future in futures if future.done()]
            for future in completed:
                slot = futures.pop(future)
                free_slots.append(slot)
                try:
                    job_id = future.result()
                except Exception as exc:
                    logger.exception("回测 worker 槽位 {} 执行失败: {}", slot, exc)
                    continue
                if job_id is not None:
                    logger.info("回测任务执行完成: job_id={} slot={}", job_id, slot)

            free_slots.sort()
            _safe_heartbeat(
                poll_interval_seconds,
                effective_concurrency,
                effective_optimization_workers,
                len(futures),
            )

            claimed_any = False
            probe_slots = 1 if not futures else len(free_slots)
            while free_slots and len(futures) < effective_concurrency and probe_slots > 0:
                slot = free_slots.pop(0)
                future = executor.submit(
                    execute_next_job,
                    None,
                    f"worker-{slot}",
                    effective_optimization_workers,
                    effective_concurrency,
                )
                futures[future] = slot
                claimed_any = True
                probe_slots -= 1

            if not claimed_any and not futures:
                sleep(poll_interval_seconds)
                continue
            sleep(0.5 if futures else poll_interval_seconds)
