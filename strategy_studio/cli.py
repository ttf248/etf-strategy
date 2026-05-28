"""命令行入口实现。

CLI 只保留数据库主链路：
- `run`：同步单标的行情并执行单次数据库回测
- `batch`：批量同步行情并提交数据库回测
- 平台命令：数据库初始化、API、Worker、Scheduler、手动同步
"""

from __future__ import annotations

import argparse
import os
from time import perf_counter

from loguru import logger

from strategy_studio.config import DEFAULT_MINUTE_INTERVAL, DEFAULT_MINUTE_PERIOD, DEFAULT_SYMBOL
from strategy_studio.data.yahoo import is_intraday_interval
from strategy_studio.logging_utils import configure_logging
from strategy_studio.platform_cli import (
    add_platform_subcommands,
    handle_api,
    handle_init_db,
    handle_scheduler,
    handle_sync_now,
    handle_worker,
)
from strategy_studio.services.backtests import BacktestRequest, execute_next_job, fetch_job, submit_backtest
from strategy_studio.services.sync import sync_market_data
from strategy_studio.settings import DEFAULT_JOBS, DEFAULT_LOOKBACK_DAYS, DEFAULT_VALIDATION_RATIO, DEFAULT_VALIDATION_START
from strategy_studio.symbols import SYMBOL_SETS, SymbolSpec
from strategy_studio.strategy.registry import strategy_choices, strategy_display_name


def build_parser() -> argparse.ArgumentParser:
    """构建仅面向数据库链路的命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="基于数据库的 Strategy Studio 回测工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="同步数据库行情并执行单标的回测")
    run_parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Yahoo Finance 标的代码")
    run_parser.add_argument("--interval", default=DEFAULT_MINUTE_INTERVAL, help="K 线周期，例如 1d、15m、1m")
    run_parser.add_argument("--period", default=DEFAULT_MINUTE_PERIOD, help="分钟 K 线同步窗口，例如 60d")
    run_parser.add_argument(
        "--proxy",
        default=os.getenv("STRATEGY_STUDIO_PROXY"),
        help="访问 Yahoo 必须配置的代理地址，例如 http://127.0.0.1:7897",
    )
    run_parser.add_argument("--validation-start", default=DEFAULT_VALIDATION_START, help="日线样本外起始日期")
    run_parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="日线样本内回看天数")
    run_parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO, help="分钟线样本外比例")
    run_parser.add_argument("--jobs", default=str(DEFAULT_JOBS), help="寻参并行进程数；可传整数或 auto")
    _add_strategy_arguments(run_parser)
    _add_execution_arguments(run_parser)

    batch_parser = subparsers.add_parser("batch", help="批量同步数据库行情并执行回测")
    batch_parser.add_argument("--symbols", default=None, help="逗号分隔的 Yahoo Finance 标的代码，例如 1810.HK,SPY")
    batch_parser.add_argument("--symbol-set", choices=sorted(SYMBOL_SETS), default=None, help="内置批量标的池")
    batch_parser.add_argument("--interval", default=DEFAULT_MINUTE_INTERVAL, help="K 线周期，例如 1d、15m")
    batch_parser.add_argument("--period", default=DEFAULT_MINUTE_PERIOD, help="分钟 K 线同步窗口，例如 60d")
    batch_parser.add_argument("--download", action="store_true", help="批量运行前先同步数据库行情")
    batch_parser.add_argument(
        "--proxy",
        default=os.getenv("STRATEGY_STUDIO_PROXY"),
        help="访问 Yahoo 必须配置的代理地址，例如 http://127.0.0.1:7897",
    )
    batch_parser.add_argument("--validation-start", default=DEFAULT_VALIDATION_START, help="日线样本外起始日期")
    batch_parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="日线样本内回看天数")
    batch_parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO, help="分钟线样本外比例")
    batch_parser.add_argument("--jobs", default=str(DEFAULT_JOBS), help="单标的寻参并行进程数；可传整数或 auto")
    _add_strategy_arguments(batch_parser)
    _add_execution_arguments(batch_parser)

    add_platform_subcommands(subparsers)
    return parser


def _add_strategy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--strategy",
        choices=strategy_choices(),
        default="grid",
        help="策略类型，例如 grid、dca、ma_cross、daily_rebound、minute_rebound",
    )


def _add_execution_arguments(parser: argparse.ArgumentParser) -> None:
    """补充统一的执行口径参数。"""
    parser.add_argument(
        "--execution-profile",
        choices=["research", "realistic"],
        default="realistic",
        help="执行口径：research 保持简化撮合，realistic 加入费用、滑点和基础风控",
    )
    parser.add_argument("--commission-bps", type=float, default=None, help="单边手续费，单位 bps；不传则使用执行口径默认值")
    parser.add_argument("--slippage-bps", type=float, default=None, help="单边滑点，单位 bps；不传则使用执行口径默认值")
    parser.add_argument("--max-position-ratio", type=float, default=None, help="最大仓位占总资金比例，例如 0.95")
    parser.add_argument("--stop-loss-pct", type=float, default=None, help="触发停止新增网格的跌幅，例如 0.2")
    parser.add_argument("--cooldown-bars", type=int, default=None, help="触发停手后冷却的 K 线数量")
    parser.add_argument("--benchmark", choices=["cash_idle", "buy_hold"], default=None, help="报告重点对照基准；默认随执行口径")
    parser.add_argument("--grid-mode", choices=["cash"], default=None, help="网格资金模式；cash 表示不建底仓")
    parser.add_argument(
        "--left-side-policy",
        choices=["hold", "force_exit", "both"],
        default=None,
        help="左侧行情处理：hold 持有未平网格，force_exit 达到亏损阈值强平，both 同时计算两套口径",
    )
    parser.add_argument(
        "--force-exit-loss-pct",
        type=float,
        default=None,
        help="force_exit 模式下未平网格浮亏占总资金的强平阈值，例如 0.05",
    )


def _resolve_jobs(value: str | int) -> int:
    """解析单标的寻参的并行进程数。"""
    if isinstance(value, int):
        return max(1, value)
    if value == "auto":
        return max(1, (os.cpu_count() or 2) - 1)
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("--jobs 必须是正整数或 auto。")
    return parsed


def _build_database_backtest_request(args: argparse.Namespace, symbol: str | None = None) -> BacktestRequest:
    """把 CLI 参数转换为数据库回测任务。"""
    return BacktestRequest(
        symbol=(symbol or args.symbol).upper(),
        interval=args.interval,
        strategy_kind=args.strategy,
        validation_start=getattr(args, "validation_start", None),
        lookback_days=getattr(args, "lookback_days", None),
        validation_ratio=getattr(args, "validation_ratio", None),
        execution_profile=args.execution_profile,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        max_position_ratio=args.max_position_ratio,
        stop_loss_pct=args.stop_loss_pct,
        cooldown_bars=args.cooldown_bars,
        benchmark=args.benchmark,
        left_side_policy=args.left_side_policy,
        force_exit_loss_pct=args.force_exit_loss_pct,
        jobs=_resolve_jobs(args.jobs),
    )


def _submit_and_execute_database_backtest(request: BacktestRequest) -> dict[str, object]:
    """同步执行单个数据库回测任务，便于 CLI 立即返回结果。"""
    submit_result = submit_backtest(request)
    job_id = int(submit_result["job_id"])
    execute_next_job(preferred_job_id=job_id)
    payload = fetch_job(job_id)
    if payload is None:
        raise RuntimeError(f"数据库回测任务提交后无法读取详情: job_id={job_id}")
    return payload


def _resolve_batch_symbols(args: argparse.Namespace) -> tuple[list[str], dict[str, SymbolSpec]]:
    """解析批量标的，支持内置标的池和显式 symbols 叠加。"""
    specs_by_symbol: dict[str, SymbolSpec] = {}
    symbols: list[str] = []

    if args.symbol_set:
        for spec in SYMBOL_SETS[args.symbol_set]:
            normalized = spec.symbol.upper()
            specs_by_symbol[normalized] = spec
            symbols.append(normalized)

    if args.symbols:
        for item in args.symbols.split(","):
            normalized = item.strip().upper()
            if not normalized:
                continue
            if normalized not in specs_by_symbol:
                specs_by_symbol[normalized] = SymbolSpec(
                    symbol=normalized,
                    name=normalized,
                    category="自定义标的",
                    source="命令行 --symbols",
                )
                symbols.append(normalized)

    deduplicated = list(dict.fromkeys(symbols))
    if not deduplicated:
        raise ValueError("batch 需要提供 --symbols 或 --symbol-set。")
    return deduplicated, specs_by_symbol


def handle_run(args: argparse.Namespace) -> int:
    """执行“数据库同步 -> 提交回测 -> 同步执行”的完整链路。"""
    started_at = perf_counter()
    intraday_mode = is_intraday_interval(args.interval)
    logger.info("收到 run 命令: symbol={} interval={} strategy={}", args.symbol, args.interval, args.strategy)

    logger.info("[1/3] 开始同步数据库行情")
    sync_result = sync_market_data(
        symbol=args.symbol.upper(),
        interval=args.interval,
        proxy=args.proxy,
        period=args.period if intraday_mode else None,
    )
    logger.info("[1/3] 数据库行情同步完成: run_id={}", sync_result["run_id"])

    logger.info("[2/3] 开始提交数据库回测任务")
    request = _build_database_backtest_request(args)
    job_payload = _submit_and_execute_database_backtest(request)
    logger.info("[2/3] 数据库回测任务执行结束: job_id={} status={}", job_payload["id"], job_payload["status"])

    report_ids = [int(item["id"]) for item in job_payload.get("reports", [])]
    print(
        "数据库行情同步完成: "
        f"run_id={sync_result['run_id']} inserted={sync_result['bars_inserted']} updated={sync_result['bars_updated']}"
    )
    if job_payload["status"] != "succeeded":
        print(f"数据库回测失败: job_id={job_payload['id']} error={job_payload.get('error_message') or '未返回错误信息'}")
        return 1
    print(
        "数据库回测完成: "
        f"job_id={job_payload['id']} report_ids={','.join(str(item) for item in report_ids) if report_ids else 'none'}"
    )
    print("结果已写入数据库；请通过前端结果库或 API 查看详细回测输出。")
    logger.info("run 命令完成: job_id={} elapsed={:.2f}s", job_payload["id"], perf_counter() - started_at)
    return 0


def handle_batch(args: argparse.Namespace) -> int:
    """批量执行多个标的的数据库回测流程。"""
    started_at = perf_counter()
    symbols, specs_by_symbol = _resolve_batch_symbols(args)
    intraday_mode = is_intraday_interval(args.interval)
    rows: list[dict[str, object]] = []
    logger.info("收到 batch 命令: symbols={} interval={} download={}", symbols, args.interval, args.download)

    for symbol in symbols:
        symbol_started_at = perf_counter()
        spec = specs_by_symbol[symbol]
        try:
            if args.download:
                logger.info("[batch] 开始同步数据库行情: symbol={} interval={}", symbol, args.interval)
                sync_result = sync_market_data(
                    symbol=symbol,
                    interval=args.interval,
                    proxy=args.proxy,
                    period=args.period if intraday_mode else None,
                )
            else:
                sync_result = None
            request = _build_database_backtest_request(args, symbol=symbol)
            job_payload = _submit_and_execute_database_backtest(request)
            rows.append(
                {
                    "Symbol": symbol,
                    "Name": spec.name,
                    "Category": spec.category,
                    "Status": job_payload["status"],
                    "Interval": args.interval,
                    "Strategy": strategy_display_name(args.strategy),
                    "JobId": int(job_payload["id"]),
                    "ReportIds": ",".join(str(item["id"]) for item in job_payload.get("reports", [])),
                    "SyncRunId": int(sync_result["run_id"]) if sync_result is not None else "",
                    "Error": job_payload.get("error_message", ""),
                    "ElapsedSeconds": perf_counter() - symbol_started_at,
                }
            )
            logger.info("[batch] 标的完成: symbol={} job_id={} status={}", symbol, job_payload["id"], job_payload["status"])
        except Exception as exc:
            rows.append(
                {
                    "Symbol": symbol,
                    "Name": spec.name,
                    "Category": spec.category,
                    "Status": "failed",
                    "Interval": args.interval,
                    "Strategy": strategy_display_name(args.strategy),
                    "JobId": "",
                    "ReportIds": "",
                    "SyncRunId": "",
                    "Error": str(exc),
                    "ElapsedSeconds": perf_counter() - symbol_started_at,
                }
            )
            logger.exception("[batch] 标的失败: symbol={}", symbol)

    ok_count = sum(1 for row in rows if row["Status"] == "succeeded")
    print(f"批量数据库回测完成: 成功 {ok_count}/{len(rows)}，详情如下：")
    for row in rows:
        print(
            f"- {row['Symbol']} strategy={row['Strategy']} status={row['Status']} "
            f"job_id={row['JobId'] or '-'} report_ids={row['ReportIds'] or '-'} error={row['Error'] or '-'}"
        )
    print("所有成功结果均已写入数据库；请通过前端结果库或 API 查看详细回测输出。")
    logger.info("batch 命令完成: success={}/{} elapsed={:.2f}s", ok_count, len(rows), perf_counter() - started_at)
    return 0 if ok_count == len(rows) else 1


def main(argv: list[str] | None = None) -> int:
    """命令行主入口。"""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "run": handle_run,
        "batch": handle_batch,
        "init-db": handle_init_db,
        "sync-now": handle_sync_now,
        "api": handle_api,
        "worker": handle_worker,
        "scheduler": handle_scheduler,
    }
    try:
        return handlers[args.command](args)
    except Exception as exc:
        logger.error("命令执行失败: {}", exc)
        print(f"错误: {exc}")
        return 1
