from __future__ import annotations

"""平台控制面服务。"""

import os
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from etf_strategy.db.session import open_session
from etf_strategy.db.settings import load_platform_settings
from etf_strategy.repositories.backtests import count_backtest_jobs_by_status
from etf_strategy.repositories.platform import list_platform_heartbeats, upsert_platform_heartbeat


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


def _tcp_available(host: str, port: int) -> bool:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::", "localhost", ""} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((probe_host, port)) == 0


def _database_status() -> dict[str, object]:
    try:
        with open_session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok", "url": _safe_database_url()}
    except Exception as exc:
        return {"status": "failed", "url": _safe_database_url(), "error": str(exc)}


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
        "process_control_enabled": os.getenv("ETF_STRATEGY_ENABLE_PROCESS_CONTROL", "").lower() in {"1", "true", "yes"},
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
    log_dir = Path("log").resolve()
    candidates = sorted(log_dir.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True) if log_dir.exists() else []
    lines: list[str] = []
    keywords = SERVICE_LOG_KEYWORDS[normalized_service]
    for path in candidates[:5]:
        if not path.resolve().is_relative_to(log_dir):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        matched = [line for line in content if any(keyword in line.lower() for keyword in keywords)]
        lines.extend(matched[-bounded_limit:])
        if len(lines) >= bounded_limit:
            break
    return {"service": normalized_service, "lines": lines[-bounded_limit:]}


def restart_platform_process(service_name: str) -> dict[str, object]:
    if os.getenv("ETF_STRATEGY_ENABLE_PROCESS_CONTROL", "").lower() not in {"1", "true", "yes"}:
        raise PermissionError("进程控制默认关闭，请设置 ETF_STRATEGY_ENABLE_PROCESS_CONTROL=true 后再使用。")
    raise NotImplementedError(f"{service_name} 重启入口尚未开放自动执行。")
