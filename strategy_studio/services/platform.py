from __future__ import annotations

"""平台控制面服务。"""

import os
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from strategy_studio.db.session import open_session
from strategy_studio.db.settings import load_platform_settings
from strategy_studio.repositories.backtests import count_backtest_jobs_by_status
from strategy_studio.repositories.platform import list_platform_heartbeats, upsert_platform_heartbeat


SERVICE_LOG_KEYWORDS = {
    "api": ("api", "uvicorn", "fastapi"),
    "worker": ("worker", "backtest"),
    "scheduler": ("scheduler", "sync"),
}


def _is_missing_heartbeat_table(exc: Exception) -> bool:
    """识别未执行平台迁移导致的心跳表缺失。"""
    message = str(exc).lower()
    return "platform_heartbeats" in message and (
        "undefinedtable" in message or "does not exist" in message or "不存在" in message
    )


def record_platform_heartbeat(service_name: str, details: dict[str, object] | None = None) -> bool:
    """常驻进程定期写心跳，供前端判断服务是否真实存活。

    开发机第一次启动平台时，数据库可能还没执行最新迁移。心跳只是控制面信息，
    表缺失不应阻断 Worker/Scheduler 主流程，因此这里返回 False 让调用方给出
    一次性初始化提示；其他数据库异常继续抛出，避免掩盖真实故障。
    """
    try:
        with open_session() as session:
            upsert_platform_heartbeat(
                session,
                service_name,
                status="running",
                pid=os.getpid(),
                details=details,
            )
            session.commit()
    except Exception as exc:
        if _is_missing_heartbeat_table(exc):
            return False
        raise
    return True


def _safe_database_url() -> str:
    url = make_url(load_platform_settings().database.url)
    return url.render_as_string(hide_password=True)


def _expected_alembic_head() -> str | None:
    """读取当前代码声明的 Alembic 目标版本，便于诊断数据库是否滞后。"""
    try:
        config = Config(str(Path("alembic.ini").resolve()))
        return ScriptDirectory.from_config(config).get_current_head()
    except Exception:
        return None


def fetch_database_diagnostics() -> dict[str, object]:
    """返回数据库连通性、建库状态与迁移状态。

    这里把“服务能否访问 PostgreSQL”和“业务库是否存在/是否完成迁移”拆开输出，
    避免只给一个 failed，让运维无法判断是实例未启动、数据库名配置错误，还是迁移未跟上。
    """
    settings = load_platform_settings()
    target_url = make_url(settings.database.url)
    database_name = target_url.database or ""
    result: dict[str, object] = {
        "status": "failed",
        "url": target_url.render_as_string(hide_password=True),
        "configured_database": database_name,
        "admin_database": settings.database.admin_database,
        "database_exists": None,
        "alembic_head": _expected_alembic_head(),
    }
    try:
        with open_session() as session:
            current_database = session.execute(text("SELECT current_database()")).scalar()
            table_count = session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM information_schema.tables
                    WHERE table_schema='public'
                    """
                )
            ).scalar()
            table_preview = session.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema='public'
                    ORDER BY table_name
                    LIMIT 20
                    """
                )
            ).scalars().all()
            try:
                alembic_revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except Exception:
                alembic_revision = None

        expected_head = result.get("alembic_head")
        if alembic_revision is None:
            migration_state = "uninitialized"
        elif expected_head and alembic_revision != expected_head:
            migration_state = "outdated"
        else:
            migration_state = "head"
        result.update(
            {
                "status": "ok",
                "database_exists": True,
                "current_database": current_database,
                "table_count": int(table_count or 0),
                "table_preview": table_preview,
                "alembic_revision": alembic_revision,
                "migration_state": migration_state,
            }
        )
        return result
    except Exception as exc:
        result["error"] = str(exc)
        result["failure_stage"] = "connect_target"

    admin_url = target_url.set(database=settings.database.admin_database)
    try:
        engine = create_engine(admin_url.render_as_string(hide_password=False), future=True, pool_pre_ping=True)
        with engine.connect() as conn:
            databases = conn.execute(
                text(
                    """
                    SELECT datname
                    FROM pg_database
                    ORDER BY datname
                    """
                )
            ).scalars().all()
        result["admin_connectivity"] = "ok"
        result["database_exists"] = database_name in databases
        result["peer_databases"] = databases
        if not result["database_exists"]:
            result["failure_stage"] = "database_missing"
    except Exception as admin_exc:
        result["admin_connectivity"] = "failed"
        result["admin_error"] = str(admin_exc)
        result["failure_stage"] = "connect_admin"
    return result


def _tcp_available(host: str, port: int) -> bool:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::", "localhost", ""} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((probe_host, port)) == 0


def _database_status() -> dict[str, object]:
    return fetch_database_diagnostics()


def _heartbeat_payload() -> list[dict[str, object]]:
    now = datetime.now(UTC)
    try:
        with open_session() as session:
            rows = list_platform_heartbeats(session)
            return [
                {
                    "service_name": row.service_name,
                    "status": row.status,
                    "pid": row.pid,
                    "started_at": row.started_at.isoformat(sep=" "),
                    "last_seen_at": row.last_seen_at.isoformat(sep=" "),
                    "age_seconds": max(0, int((now - row.last_seen_at).total_seconds())),
                    "details": row.details_json,
                }
                for row in rows
            ]
    except Exception:
        return []


def _queue_stats() -> dict[str, int]:
    try:
        with open_session() as session:
            stats = count_backtest_jobs_by_status(session)
    except Exception:
        stats = {}
    for status in ("queued", "running", "cancel_requested", "cancelled", "succeeded", "failed"):
        stats.setdefault(status, 0)
    return stats


def fetch_platform_status() -> dict[str, object]:
    settings = load_platform_settings()
    api_reachable = _tcp_available(settings.api_host, settings.api_port)
    frontend_reachable = _tcp_available(settings.frontend_host, settings.frontend_port)
    return {
        "api": {
            "status": "ok" if api_reachable else "down",
            "host": settings.api_host,
            "port": settings.api_port,
            "base_url": f"http://{settings.api_host}:{settings.api_port}",
        },
        "frontend": {
            "status": "ok" if frontend_reachable else "down",
            "host": settings.frontend_host,
            "port": settings.frontend_port,
            "base_url": f"http://{settings.frontend_host}:{settings.frontend_port}",
        },
        "database": _database_status(),
        "heartbeats": _heartbeat_payload(),
        "queue": _queue_stats(),
        "process_control_enabled": os.getenv("STRATEGY_STUDIO_ENABLE_PROCESS_CONTROL", "").lower() in {"1", "true", "yes"},
        "sync_schedule": [
            {"id": "daily_bars_sync", "interval": "1d", "cron": "18:05 Asia/Shanghai", "period": ""},
            {"id": "minute_15m_sync", "interval": "15m", "cron": "18:15 Asia/Shanghai", "period": "60d"},
            {"id": "minute_1m_sync", "interval": "1m", "cron": "18:25 Asia/Shanghai", "period": "7d"},
        ],
    }


def fetch_platform_processes() -> list[dict[str, object]]:
    if os.name != "nt":
        return []
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*next dev*' } | "
        "Select-Object ProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Depth 3"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    import json

    raw = result.stdout.strip()
    if not raw:
        return []
    payload = json.loads(raw)
    rows = payload if isinstance(payload, list) else [payload]
    processes: list[dict[str, object]] = []
    for row in rows:
        command_line = str(row.get("CommandLine") or "")
        service_name = "frontend" if "next dev" in command_line else "unknown"
        if " api " in f" {command_line.lower()} ":
            service_name = "api"
        elif " worker " in f" {command_line.lower()} ":
            service_name = "worker"
        elif " scheduler " in f" {command_line.lower()} ":
            service_name = "scheduler"
        processes.append(
            {
                "pid": row.get("ProcessId"),
                "name": row.get("Name"),
                "service_name": service_name,
                "created_at": row.get("CreationDate"),
                "command_line": command_line,
            }
        )
    return processes


def fetch_platform_logs(service: str = "api", limit: int = 200) -> dict[str, object]:
    normalized_service = service if service in SERVICE_LOG_KEYWORDS else "api"
    bounded_limit = min(max(limit, 1), 500)
    return {
        "service": normalized_service,
        "lines": [
            "当前平台默认只输出终端日志，不再从本地日志文件目录读取记录。"
        ][:bounded_limit],
    }


def restart_platform_process(service_name: str) -> dict[str, object]:
    if os.getenv("STRATEGY_STUDIO_ENABLE_PROCESS_CONTROL", "").lower() not in {"1", "true", "yes"}:
        raise PermissionError("进程控制默认关闭，请设置 STRATEGY_STUDIO_ENABLE_PROCESS_CONTROL=true 后再使用。")
    raise NotImplementedError(f"{service_name} 重启入口尚未开放自动执行。")
