from __future__ import annotations

"""平台服务相关命令入口。"""

import argparse
import importlib
import json
import os
import socket
import subprocess
import time
from urllib import error, request


def _build_missing_dependency_error(command_name: str, exc: ModuleNotFoundError) -> RuntimeError:
    """把缺少平台依赖的导入错误转换成可执行的中文提示。"""
    missing_module = exc.name or "未知模块"
    return RuntimeError(
        f"{command_name} 缺少 Python 依赖 `{missing_module}`。"
        "请先在当前 VS Code 选中的解释器里执行 `python -m pip install -r requirements.txt`；"
        "如果你使用本仓库默认命令，也可以执行 `py -3.13 -m pip install -r requirements.txt`。"
    )


def _import_platform_module(module_name: str, command_name: str):
    """按需导入平台模块，避免未装平台依赖时连其他 CLI 命令都无法启动。"""
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise _build_missing_dependency_error(command_name, exc) from exc


def _normalize_probe_host(host: str) -> str:
    """把监听地址转换成适合本地探测的目标地址。"""
    if host in {"0.0.0.0", "::", ""}:
        return "127.0.0.1"
    if host == "localhost":
        return "127.0.0.1"
    return host


def _is_tcp_port_in_use(host: str, port: int) -> bool:
    """检查本地端口是否已经有监听进程。"""
    probe_host = _normalize_probe_host(host)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((probe_host, port)) == 0


def _probe_existing_platform_api(host: str, port: int) -> bool:
    """判断被占用端口上是否已经是本项目 API。"""
    probe_host = _normalize_probe_host(host)
    health_url = f"http://{probe_host}:{port}/health"
    try:
        with request.urlopen(health_url, timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, error.URLError, error.HTTPError, json.JSONDecodeError):
        return False
    return payload.get("status") == "ok"


def _describe_windows_listener(port: int) -> str | None:
    """尽量补充 Windows 下占用端口的 PID 和进程名。"""
    listener_pid = _get_windows_listener_pid(port)
    if not listener_pid:
        return None
    process_name = _get_windows_process_name(listener_pid) or "未知进程"
    return f"PID={listener_pid} 进程名={process_name}"


def _get_windows_listener_pid(port: int) -> str | None:
    """从 netstat 输出里解析指定端口的监听进程 PID。"""
    if os.name != "nt":
        return None
    try:
        netstat_result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None

    target_suffix = f":{port}"
    for raw_line in netstat_result.stdout.splitlines():
        line = raw_line.strip()
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address = parts[1]
        pid = parts[-1]
        if local_address.endswith(target_suffix):
            return pid
    return None


def _get_windows_process_name(pid: str) -> str | None:
    """查询 Windows 进程名，失败时返回 None。"""
    process_name = "未知进程"
    try:
        tasklist_result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
        first_line = tasklist_result.stdout.strip().splitlines()[0]
        if first_line and not first_line.startswith("INFO:"):
            process_name = next((item.strip('"') for item in first_line.split(",") if item), process_name)
    except (IndexError, FileNotFoundError, subprocess.SubprocessError):
        return None
    return process_name


def _get_windows_process_command_line(pid: str) -> str | None:
    """查询 Windows 进程命令行，用于判断端口占用者是否为本项目 API。"""
    if os.name != "nt":
        return None
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').CommandLine",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    command_line = result.stdout.strip()
    return command_line or None


def _is_project_api_command(command_line: str | None) -> bool:
    """只允许自动替换本仓库自己的 API 进程。"""
    if not command_line:
        return False
    normalized = command_line.lower().replace('"', " ").replace("'", " ")
    return "main.py" in normalized and " api " in f" {normalized} "


def _terminate_windows_process_tree(pid: str) -> bool:
    """结束指定 Windows 进程树，供替换旧 API 进程使用。"""
    if os.name != "nt":
        return False
    try:
        subprocess.run(["taskkill", "/PID", pid, "/F", "/T"], capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
    return True


def _replace_existing_platform_api(host: str, port: int) -> bool:
    """如果端口占用者确认是本项目旧 API，则终止它并等待端口释放。"""
    listener_pid = _get_windows_listener_pid(port)
    command_line = _get_windows_process_command_line(listener_pid) if listener_pid else None
    if not listener_pid or not _is_project_api_command(command_line):
        return False
    if not _terminate_windows_process_tree(listener_pid):
        return False
    for _ in range(20):
        if not _is_tcp_port_in_use(host, port):
            return True
        time.sleep(0.2)
    return False


def _build_port_in_use_error(host: str, port: int) -> RuntimeError:
    """构造端口占用时的中文提示。"""
    listener_hint = _describe_windows_listener(port)
    base_message = f"API 监听地址 {host}:{port} 已被占用。"
    if _probe_existing_platform_api(host, port):
        detail = "检测到当前端口上已经有本项目 API 在运行，请不要重复启动；需要重启时先停止现有 API 进程。"
    else:
        detail = "请先停止占用该端口的进程，或者改用其他端口重新启动。"
    if listener_hint:
        detail = f"{detail} 当前监听者：{listener_hint}。"
    return RuntimeError(f"{base_message}{detail}")


def add_platform_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    init_db_parser = subparsers.add_parser("init-db", help="创建项目数据库并执行迁移")
    init_db_parser.add_argument("--with-migration", action="store_true", default=True, help="保留兼容参数，占位表示执行迁移")

    import_parser = subparsers.add_parser("import-csv", help="导入本地 CSV 行情到 PostgreSQL")
    import_parser.add_argument("--source-dir", default="data/processed", help="CSV 源目录；默认读取未纳入版本控制的运行目录")

    sync_parser = subparsers.add_parser("sync-now", help="立即同步 Yahoo 行情到数据库")
    sync_parser.add_argument("--symbol", default=None, help="指定单个标的；不传则同步数据库中已知全部标的")
    sync_parser.add_argument("--interval", default="1d", help="行情周期，例如 1d、15m、1m")
    sync_parser.add_argument("--proxy", default=None, help="Yahoo 代理地址")
    sync_parser.add_argument("--period", default=None, help="分钟线下载窗口，例如 7d、60d")

    api_parser = subparsers.add_parser("api", help="启动 FastAPI 服务")
    api_parser.add_argument("--host", default=None, help="监听地址")
    api_parser.add_argument("--port", type=int, default=None, help="监听端口")
    api_parser.add_argument("--replace-existing", action="store_true", help="如果旧 API 进程占用端口，则先结束旧进程再启动")

    worker_parser = subparsers.add_parser("worker", help="启动回测任务 worker")
    worker_parser.add_argument("--poll-interval", type=int, default=5, help="任务轮询间隔秒数")

    scheduler_parser = subparsers.add_parser("scheduler", help="启动行情同步调度器")
    scheduler_parser.add_argument("--proxy", default=None, help="Yahoo 代理地址")


def handle_init_db(_: argparse.Namespace) -> int:
    initialize_database = _import_platform_module("strategy_studio.db.bootstrap", "init-db").initialize_database
    database_name = initialize_database()
    print(f"数据库初始化完成：{database_name}")
    return 0


def handle_import_csv(args: argparse.Namespace) -> int:
    import_csv_directory = _import_platform_module("strategy_studio.services.market_data", "import-csv").import_csv_directory
    result = import_csv_directory(args.source_dir)
    print(f"CSV 导入完成：扫描 {result.files_scanned} 个文件")
    print(f"新增标的：{result.instruments_created}")
    print(f"新增 K 线：{result.bars_inserted}")
    print(f"更新 K 线：{result.bars_updated}")
    print(f"失败文件：{len(result.failed_files)}")
    for item in result.failed_files:
        print(f"- {item}")
    return 0 if not result.failed_files else 1


def handle_sync_now(args: argparse.Namespace) -> int:
    sync_market_data = _import_platform_module("strategy_studio.services.sync", "sync-now").sync_market_data
    result = sync_market_data(symbol=args.symbol, interval=args.interval, proxy=args.proxy, period=args.period)
    print(
        "同步完成："
        f"run_id={result['run_id']} "
        f"symbols={result['symbols_count']} "
        f"inserted={result['bars_inserted']} "
        f"updated={result['bars_updated']}"
    )
    return 0


def handle_api(args: argparse.Namespace) -> int:
    load_platform_settings = _import_platform_module("strategy_studio.db.settings", "api").load_platform_settings
    create_app = _import_platform_module("strategy_studio.web.app", "api").create_app
    uvicorn = _import_platform_module("uvicorn", "api")
    settings = load_platform_settings()
    host = args.host or settings.api_host
    port = args.port or settings.api_port
    if _is_tcp_port_in_use(host, port):
        if getattr(args, "replace_existing", False) and _replace_existing_platform_api(host, port):
            print(f"已停止旧 API 进程，准备重新监听 {host}:{port}")
        else:
            raise _build_port_in_use_error(host, port)
    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level="info",
    )
    return 0


def handle_worker(args: argparse.Namespace) -> int:
    run_worker_loop = _import_platform_module("strategy_studio.runtime.worker", "worker").run_worker_loop
    run_worker_loop(poll_interval_seconds=args.poll_interval)
    return 0


def handle_scheduler(args: argparse.Namespace) -> int:
    run_scheduler = _import_platform_module("strategy_studio.runtime.scheduler", "scheduler").run_scheduler
    run_scheduler(proxy=args.proxy)
    return 0
