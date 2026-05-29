from __future__ import annotations

"""数据库与平台运行配置。"""

import os
from dataclasses import dataclass


DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:tian@localhost:5432/etf_strategy"
DEFAULT_ADMIN_DATABASE = "postgres"
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_FRONTEND_HOST = "127.0.0.1"
DEFAULT_FRONTEND_PORT = 3000
DEFAULT_SYNC_INTERVALS = ("1d", "15m", "1m")
DEFAULT_TDX_CONFIG_PATH = r"F:\trade\tdx\config.local.yaml"
DEFAULT_TDX_VIPDOC = ""
DEFAULT_TUSHARE_CONFIG_PATH = r"F:\trade\tdx\config.local.yaml"
DEFAULT_TUSHARE_TOKEN = ""
DEFAULT_TUSHARE_RATE_LIMIT_PER_MINUTE = 90
DEFAULT_TUSHARE_TIMEOUT_SECONDS = 15.0
DEFAULT_TUSHARE_RETRIES = 3
DEFAULT_WORKER_MAX_CONCURRENT_JOBS = 2
DEFAULT_WORKER_MAX_OPTIMIZATION_WORKERS = 4


@dataclass(frozen=True)
class DatabaseSettings:
    """数据库连接配置。"""

    url: str = DEFAULT_DATABASE_URL
    admin_database: str = DEFAULT_ADMIN_DATABASE


@dataclass(frozen=True)
class PlatformSettings:
    """平台默认运行配置。"""

    database: DatabaseSettings
    api_host: str = DEFAULT_API_HOST
    api_port: int = DEFAULT_API_PORT
    frontend_host: str = DEFAULT_FRONTEND_HOST
    frontend_port: int = DEFAULT_FRONTEND_PORT
    sync_intervals: tuple[str, ...] = DEFAULT_SYNC_INTERVALS
    tdx_config_path: str = DEFAULT_TDX_CONFIG_PATH
    tdx_vipdoc: str = DEFAULT_TDX_VIPDOC
    tushare_config_path: str = DEFAULT_TUSHARE_CONFIG_PATH
    tushare_token: str = DEFAULT_TUSHARE_TOKEN
    tushare_rate_limit_per_minute: int = DEFAULT_TUSHARE_RATE_LIMIT_PER_MINUTE
    tushare_timeout_seconds: float = DEFAULT_TUSHARE_TIMEOUT_SECONDS
    tushare_retries: int = DEFAULT_TUSHARE_RETRIES
    worker_max_concurrent_jobs: int = DEFAULT_WORKER_MAX_CONCURRENT_JOBS
    worker_max_optimization_workers: int = DEFAULT_WORKER_MAX_OPTIMIZATION_WORKERS


def load_platform_settings() -> PlatformSettings:
    """从环境变量加载平台配置。"""
    return PlatformSettings(
        database=DatabaseSettings(
            url=os.getenv("STRATEGY_STUDIO_DATABASE_URL", DEFAULT_DATABASE_URL),
            admin_database=os.getenv("STRATEGY_STUDIO_ADMIN_DATABASE", DEFAULT_ADMIN_DATABASE),
        ),
        api_host=os.getenv("STRATEGY_STUDIO_API_HOST", DEFAULT_API_HOST),
        api_port=int(os.getenv("STRATEGY_STUDIO_API_PORT", str(DEFAULT_API_PORT))),
        frontend_host=os.getenv("STRATEGY_STUDIO_FRONTEND_HOST", DEFAULT_FRONTEND_HOST),
        frontend_port=int(os.getenv("STRATEGY_STUDIO_FRONTEND_PORT", str(DEFAULT_FRONTEND_PORT))),
        tdx_config_path=os.getenv("STRATEGY_STUDIO_TDX_CONFIG_PATH", DEFAULT_TDX_CONFIG_PATH),
        tdx_vipdoc=os.getenv("STRATEGY_STUDIO_TDX_VIPDOC", DEFAULT_TDX_VIPDOC),
        tushare_config_path=os.getenv("STRATEGY_STUDIO_TUSHARE_CONFIG_PATH", DEFAULT_TUSHARE_CONFIG_PATH),
        tushare_token=os.getenv("STRATEGY_STUDIO_TUSHARE_TOKEN", DEFAULT_TUSHARE_TOKEN),
        tushare_rate_limit_per_minute=max(
            1,
            int(os.getenv("STRATEGY_STUDIO_TUSHARE_RATE_LIMIT_PER_MINUTE", str(DEFAULT_TUSHARE_RATE_LIMIT_PER_MINUTE))),
        ),
        tushare_timeout_seconds=max(
            1.0,
            float(os.getenv("STRATEGY_STUDIO_TUSHARE_TIMEOUT_SECONDS", str(DEFAULT_TUSHARE_TIMEOUT_SECONDS))),
        ),
        tushare_retries=max(
            1,
            int(os.getenv("STRATEGY_STUDIO_TUSHARE_RETRIES", str(DEFAULT_TUSHARE_RETRIES))),
        ),
        worker_max_concurrent_jobs=max(
            1,
            int(os.getenv("STRATEGY_STUDIO_WORKER_MAX_CONCURRENT_JOBS", str(DEFAULT_WORKER_MAX_CONCURRENT_JOBS))),
        ),
        worker_max_optimization_workers=max(
            1,
            int(os.getenv("STRATEGY_STUDIO_WORKER_MAX_OPTIMIZATION_WORKERS", str(DEFAULT_WORKER_MAX_OPTIMIZATION_WORKERS))),
        ),
    )

