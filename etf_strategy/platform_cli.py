from __future__ import annotations

"""平台服务相关命令入口。"""

import argparse

import uvicorn

from etf_strategy.db.bootstrap import initialize_database
from etf_strategy.db.settings import load_platform_settings
from etf_strategy.runtime.scheduler import run_scheduler
from etf_strategy.runtime.worker import run_worker_loop
from etf_strategy.services.market_data import import_csv_directory
from etf_strategy.services.sync import sync_market_data
from etf_strategy.web.app import create_app


def add_platform_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    init_db_parser = subparsers.add_parser("init-db", help="创建项目数据库并执行迁移")
    init_db_parser.add_argument("--with-migration", action="store_true", default=True, help="保留兼容参数，占位表示执行迁移")

    import_parser = subparsers.add_parser("import-csv", help="导入本地 CSV 行情到 PostgreSQL")
    import_parser.add_argument("--source-dir", default="data/processed", help="CSV 源目录")

    sync_parser = subparsers.add_parser("sync-now", help="立即同步 Yahoo 行情到数据库")
    sync_parser.add_argument("--symbol", default=None, help="指定单个标的；不传则同步数据库中已知全部标的")
    sync_parser.add_argument("--interval", default="1d", help="行情周期，例如 1d、15m、1m")
    sync_parser.add_argument("--proxy", default=None, help="Yahoo 代理地址")
    sync_parser.add_argument("--period", default=None, help="分钟线下载窗口，例如 7d、60d")

    api_parser = subparsers.add_parser("api", help="启动 FastAPI 服务")
    api_parser.add_argument("--host", default=None, help="监听地址")
    api_parser.add_argument("--port", type=int, default=None, help="监听端口")

    worker_parser = subparsers.add_parser("worker", help="启动回测任务 worker")
    worker_parser.add_argument("--poll-interval", type=int, default=5, help="任务轮询间隔秒数")

    scheduler_parser = subparsers.add_parser("scheduler", help="启动行情同步调度器")
    scheduler_parser.add_argument("--proxy", default=None, help="Yahoo 代理地址")


def handle_init_db(_: argparse.Namespace) -> int:
    database_name = initialize_database()
    print(f"数据库初始化完成：{database_name}")
    return 0


def handle_import_csv(args: argparse.Namespace) -> int:
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
    settings = load_platform_settings()
    uvicorn.run(
        create_app(),
        host=args.host or settings.api_host,
        port=args.port or settings.api_port,
        log_level="info",
    )
    return 0


def handle_worker(args: argparse.Namespace) -> int:
    run_worker_loop(poll_interval_seconds=args.poll_interval)
    return 0


def handle_scheduler(args: argparse.Namespace) -> int:
    run_scheduler(proxy=args.proxy)
    return 0

