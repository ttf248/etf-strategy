"""命令行入口实现。

CLI 层只负责三件事：
- 解析用户参数
- 根据周期选择日线或分钟线工作流
- 把结果转换成适合终端阅读的中文输出
"""

import argparse
import os
from pathlib import Path
from time import perf_counter

from loguru import logger

from etf_strategy.config import (
    DEFAULT_DATA_PATH,
    DEFAULT_MINUTE_OUTPUT_DIR,
    DEFAULT_MINUTE_REPORT_DIR,
    DEFAULT_MINUTE_DATA_PATH,
    DEFAULT_MINUTE_INTERVAL,
    DEFAULT_MINUTE_PERIOD,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_DIR,
    DEFAULT_SYMBOL,
)
from etf_strategy.data.yahoo import (
    build_default_output_path,
    download_price_bars,
    is_intraday_interval,
    save_price_bars,
)
from etf_strategy.logging_utils import configure_logging
from etf_strategy.reporting import build_minute_report_markdown, build_report_markdown
from etf_strategy.workflow import (
    run_full_workflow,
    run_minute_full_workflow,
    run_minute_optimization_workflow,
    run_minute_validation_workflow,
    run_optimization_workflow,
    run_validation_workflow,
)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="基于 Yahoo 数据的策略回测工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 子命令保持扁平结构，避免用户为了跑一次回测需要记忆多层嵌套命令。
    download_parser = subparsers.add_parser("download", help="下载并标准化历史行情")
    download_parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Yahoo Finance 标的代码")
    download_parser.add_argument("--start", help="开始日期，格式 YYYY-MM-DD；日线不传时默认下载可用全历史")
    download_parser.add_argument("--end", help="结束日期，格式 YYYY-MM-DD；和 --start 一起使用")
    download_parser.add_argument("--interval", default="1d", help="K 线周期，例如 1d、5m、15m、60m")
    download_parser.add_argument(
        "--period",
        default=DEFAULT_MINUTE_PERIOD,
        help="分钟 K 线优先使用的区间，例如 5d、30d、60d",
    )
    download_parser.add_argument(
        "--proxy",
        default=os.getenv("ETF_STRATEGY_PROXY"),
        help="访问 Yahoo 所需的代理地址，例如 http://127.0.0.1:7897",
    )
    download_parser.add_argument(
        "--output",
        default=None,
        help="标准化 CSV 输出路径",
    )

    optimize_parser = subparsers.add_parser("optimize", help="执行样本内参数搜索")
    optimize_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")
    optimize_parser.add_argument("--symbol", default=None, help="Yahoo Finance 标的代码；不传时尝试从文件名推断")
    optimize_parser.add_argument("--interval", default="1d", help="数据周期，决定使用日线还是分钟线工作流")
    optimize_parser.add_argument("--output-dir", default=None, help="参数搜索结果输出目录")
    optimize_parser.add_argument("--validation-start", default="2026-01-01", help="样本外起始日期")
    optimize_parser.add_argument("--lookback-days", type=int, default=120, help="样本内回看天数")
    optimize_parser.add_argument("--validation-ratio", type=float, default=0.25, help="分钟线样本外比例")

    backtest_parser = subparsers.add_parser("backtest", help="执行样本外验证")
    backtest_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")
    backtest_parser.add_argument("--symbol", default=None, help="Yahoo Finance 标的代码；不传时尝试从文件名推断")
    backtest_parser.add_argument("--interval", default="1d", help="数据周期，决定使用日线还是分钟线工作流")
    backtest_parser.add_argument(
        "--grid-spacing",
        type=float,
        required=True,
        help="网格间距比例，例如 0.05 表示每跌 5%% 再开下一层网格",
    )
    backtest_parser.add_argument(
        "--grid-count",
        type=int,
        required=True,
        help="网格层数，例如 7 表示最多允许开启 7 层固定股数网格仓位",
    )
    backtest_parser.add_argument(
        "--take-profit",
        type=float,
        required=True,
        help="单层止盈比例，例如 0.03 表示某层买入后反弹 3%% 就卖出该层",
    )
    backtest_parser.add_argument("--output-dir", default=None, help="样本外验证输出目录")
    backtest_parser.add_argument("--validation-start", default="2026-01-01", help="样本外起始日期")
    backtest_parser.add_argument("--lookback-days", type=int, default=120, help="样本内回看天数")
    backtest_parser.add_argument("--validation-ratio", type=float, default=0.25, help="分钟线样本外比例")

    report_parser = subparsers.add_parser("report", help="生成图表与中文报告")
    report_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")
    report_parser.add_argument("--symbol", default=None, help="Yahoo Finance 标的代码；不传时尝试从文件名推断")
    report_parser.add_argument("--interval", default="1d", help="数据周期，决定使用日线还是分钟线工作流")
    report_parser.add_argument("--output-dir", default=None, help="工作流中间文件目录")
    report_parser.add_argument("--report-dir", default=None, help="图表与 Markdown 报告输出目录")
    report_parser.add_argument("--validation-start", default="2026-01-01", help="样本外起始日期")
    report_parser.add_argument("--lookback-days", type=int, default=120, help="样本内回看天数")
    report_parser.add_argument("--validation-ratio", type=float, default=0.25, help="分钟线样本外比例")

    run_parser = subparsers.add_parser("run", help="串联下载、寻参、验证和报告生成")
    run_parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Yahoo Finance 标的代码")
    run_parser.add_argument("--start", help="开始日期，格式 YYYY-MM-DD；日线不传时默认下载可用全历史")
    run_parser.add_argument("--end", help="结束日期，格式 YYYY-MM-DD；和 --start 一起使用")
    run_parser.add_argument("--interval", default="1d", help="K 线周期，例如 1d、5m、15m、60m")
    run_parser.add_argument("--period", default=DEFAULT_MINUTE_PERIOD, help="分钟 K 线优先使用的区间，例如 5d、30d、60d")
    run_parser.add_argument(
        "--proxy",
        default=os.getenv("ETF_STRATEGY_PROXY"),
        help="访问 Yahoo 所需的代理地址，例如 http://127.0.0.1:7897",
    )
    run_parser.add_argument("--output-dir", default=None, help="完整工作流输出目录")
    run_parser.add_argument("--report-dir", default=None, help="图表与 Markdown 报告输出目录")
    run_parser.add_argument("--validation-start", default="2026-01-01", help="样本外起始日期")
    run_parser.add_argument("--lookback-days", type=int, default=120, help="样本内回看天数")
    run_parser.add_argument("--validation-ratio", type=float, default=0.25, help="分钟线样本外比例")

    return parser


def _validate_daily_date_range(args: argparse.Namespace, command_name: str) -> None:
    """校验日线显式时间区间参数。"""
    if is_intraday_interval(args.interval):
        return
    if bool(args.start) ^ bool(args.end):
        raise ValueError(f"{command_name} 在日线显式指定区间时，必须同时提供 --start 和 --end。")


def _resolve_download_output_path(symbol: str, interval: str, period: str | None, output: str | None) -> Path:
    """统一计算下载落盘路径。

    默认样本仍保留固定文件名，方便 README、文档和报告复用；
    其余标的或周期则按 `symbol + interval` 自动生成路径。
    """
    if output is not None:
        return Path(output)
    if interval == DEFAULT_MINUTE_INTERVAL and period == DEFAULT_MINUTE_PERIOD and symbol.upper() == DEFAULT_SYMBOL:
        return DEFAULT_MINUTE_DATA_PATH
    if interval == "1d" and symbol.upper() == DEFAULT_SYMBOL:
        return DEFAULT_DATA_PATH
    return build_default_output_path(symbol, interval)


def handle_download(args: argparse.Namespace) -> int:
    """执行下载命令。"""
    started_at = perf_counter()
    _validate_daily_date_range(args, "download")
    output = _resolve_download_output_path(args.symbol, args.interval, args.period, args.output)
    logger.info("收到 download 命令: symbol={} interval={} output={}", args.symbol, args.interval, output)

    bars = download_price_bars(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start if args.interval == "1d" else None,
        end_date=args.end if args.interval == "1d" else None,
        period=args.period if is_intraday_interval(args.interval) else None,
        proxy=args.proxy,
    )
    # 下载命令默认做增量合并，分钟线能保留本地历史，日线也不会因为重跑而覆盖旧样本。
    output_path = save_price_bars(bars, output, interval=args.interval, merge_with_existing=True)
    logger.info("download 命令完成: output={} elapsed={:.2f}s", output_path, perf_counter() - started_at)
    print(f"下载完成: {output_path}")
    return 0


def handle_placeholder(args: argparse.Namespace) -> int:
    """为尚未接入的子命令提供一致反馈。"""
    logger.warning("命令 {} 尚未完成实现。", args.command)
    print(f"命令 {args.command} 已保留，但将在后续子任务中接入真实逻辑。")
    return 0


def handle_optimize(args: argparse.Namespace) -> int:
    """执行样本内参数搜索，并按周期选择对应工作流。"""
    started_at = perf_counter()
    logger.info("收到 optimize 命令: data={} interval={}", args.data, args.interval)
    if is_intraday_interval(args.interval):
        output_dir = args.output_dir or str(DEFAULT_MINUTE_OUTPUT_DIR / "optimize")
        result = run_minute_optimization_workflow(
            data_path=args.data,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_ratio=args.validation_ratio,
        )
    else:
        output_dir = args.output_dir or str(DEFAULT_OUTPUT_DIR / "optimize")
        result = run_optimization_workflow(
            data_path=args.data,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_start=args.validation_start,
            lookback_days=args.lookback_days,
        )
    best_summary = result["best_run"]["summary"]
    print(f"样本内最优参数已生成: {result['results_path']}")
    print(
        "最优参数: "
        f"grid_spacing={best_summary['GridSpacingPct']:.2f}% "
        f"grid_count={best_summary['GridCount']} "
        f"take_profit={best_summary['TakeProfitPct']:.2f}% "
        f"score={best_summary['Score']:.2f}"
    )
    logger.info("optimize 命令完成: results={} elapsed={:.2f}s", result["results_path"], perf_counter() - started_at)
    return 0


def handle_backtest(args: argparse.Namespace) -> int:
    """执行样本外验证。"""
    started_at = perf_counter()
    logger.info(
        "收到 backtest 命令: data={} interval={} spacing={:.2f}% grid_count={} take_profit={:.2f}%",
        args.data,
        args.interval,
        args.grid_spacing * 100,
        args.grid_count,
        args.take_profit * 100,
    )
    if is_intraday_interval(args.interval):
        output_dir = args.output_dir or str(DEFAULT_MINUTE_OUTPUT_DIR / "validation")
        result = run_minute_validation_workflow(
            data_path=args.data,
            grid_spacing_pct=args.grid_spacing,
            grid_count=args.grid_count,
            take_profit_pct=args.take_profit,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_ratio=args.validation_ratio,
        )
    else:
        output_dir = args.output_dir or str(DEFAULT_OUTPUT_DIR / "validation")
        result = run_validation_workflow(
            data_path=args.data,
            grid_spacing_pct=args.grid_spacing,
            grid_count=args.grid_count,
            take_profit_pct=args.take_profit,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_start=args.validation_start,
            lookback_days=args.lookback_days,
        )
    summary = result["run"]["summary"]
    print(
        "样本外验证完成: "
        f"return={summary['ReturnPct']:.2f}% "
        f"max_drawdown={summary['MaxDrawdownPct']:.2f}% "
        f"cost_reduction={summary['CostReductionPct']:.2f}%"
    )
    logger.info("backtest 命令完成: elapsed={:.2f}s", perf_counter() - started_at)
    return 0


def handle_run(args: argparse.Namespace) -> int:
    """执行“下载 -> 寻参 -> 验证 -> 报告”的完整链路。"""
    started_at = perf_counter()
    intraday_mode = is_intraday_interval(args.interval)
    _validate_daily_date_range(args, "run")
    output_dir = Path(args.output_dir or (DEFAULT_MINUTE_OUTPUT_DIR if intraday_mode else DEFAULT_OUTPUT_DIR))
    report_dir = args.report_dir or str(DEFAULT_MINUTE_REPORT_DIR if intraday_mode else DEFAULT_REPORT_DIR)
    data_path = _resolve_download_output_path(args.symbol, args.interval, args.period, output=None)
    logger.info(
        "收到 run 命令: symbol={} interval={} data_path={} output_dir={} report_dir={}",
        args.symbol,
        args.interval,
        data_path,
        output_dir,
        report_dir,
    )
    bars = download_price_bars(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start if args.interval == "1d" else None,
        end_date=args.end if args.interval == "1d" else None,
        period=args.period if intraday_mode else None,
        proxy=args.proxy,
    )
    save_price_bars(bars, data_path, interval=args.interval, merge_with_existing=True)

    # `run` 总是先把最新下载结果和本地样本合并落盘，再交给统一工作流和报告层复用。
    if intraday_mode:
        result = run_minute_full_workflow(
            data_path=data_path,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_ratio=args.validation_ratio,
        )
        report_path = build_minute_report_markdown(result, report_dir=report_dir)
    else:
        result = run_full_workflow(
            data_path=data_path,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_start=args.validation_start,
            lookback_days=args.lookback_days,
        )
        report_path = build_report_markdown(result, report_dir=report_dir)
    best_summary = result["optimization"]["best_run"]["summary"]
    validation_summary = result["validation"]["run"]["summary"]
    print(f"完整工作流已完成，汇总文件: {result['combined_summary_path']}")
    print(f"中文报告: {report_path}")
    print(
        "样本内最优参数: "
        f"grid_spacing={best_summary['GridSpacingPct']:.2f}% "
        f"grid_count={best_summary['GridCount']} "
        f"take_profit={best_summary['TakeProfitPct']:.2f}%"
    )
    print(
        f"{'分钟线样本外表现' if intraday_mode else '2026 样本外表现'}: "
        f"return={validation_summary['ReturnPct']:.2f}% "
        f"max_drawdown={validation_summary['MaxDrawdownPct']:.2f}% "
        f"cost_reduction={validation_summary['CostReductionPct']:.2f}%"
    )
    logger.info("run 命令完成: report={} elapsed={:.2f}s", report_path, perf_counter() - started_at)
    return 0


def handle_report(args: argparse.Namespace) -> int:
    """基于已有 CSV 重跑工作流并生成正式报告。"""
    started_at = perf_counter()
    logger.info("收到 report 命令: data={} interval={}", args.data, args.interval)
    if is_intraday_interval(args.interval):
        output_dir = args.output_dir or str(DEFAULT_MINUTE_OUTPUT_DIR)
        report_dir = args.report_dir or str(DEFAULT_MINUTE_REPORT_DIR)
        result = run_minute_full_workflow(
            data_path=args.data,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_ratio=args.validation_ratio,
        )
        report_path = build_minute_report_markdown(result, report_dir=report_dir)
    else:
        output_dir = args.output_dir or str(DEFAULT_OUTPUT_DIR)
        report_dir = args.report_dir or str(DEFAULT_REPORT_DIR)
        result = run_full_workflow(
            data_path=args.data,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_start=args.validation_start,
            lookback_days=args.lookback_days,
        )
        report_path = build_report_markdown(result, report_dir=report_dir)
    print(f"报告已生成: {report_path}")
    logger.info("report 命令完成: report={} elapsed={:.2f}s", report_path, perf_counter() - started_at)
    return 0


def main(argv: list[str] | None = None) -> int:
    """命令行主入口。"""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "download": handle_download,
        "optimize": handle_optimize,
        "backtest": handle_backtest,
        "report": handle_report,
        "run": handle_run,
    }
    return handlers[args.command](args)
