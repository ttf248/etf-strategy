from __future__ import annotations

"""数据库与平台运行配置。"""

import os
from dataclasses import dataclass


DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:tian@localhost:5432/strategy_studio"
DEFAULT_ADMIN_DATABASE = "postgres"
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_FRONTEND_HOST = "127.0.0.1"
DEFAULT_FRONTEND_PORT = 3000
DEFAULT_SYNC_INTERVALS = ("1d", "15m", "1m")


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
    )

