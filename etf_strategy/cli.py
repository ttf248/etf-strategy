import argparse
import os
from pathlib import Path

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

    download_parser = subparsers.add_parser("download", help="下载并标准化历史行情")
    download_parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Yahoo Finance 标的代码")
    download_parser.add_argument("--start", help="开始日期，格式 YYYY-MM-DD，日线必填")
    download_parser.add_argument("--end", help="结束日期，格式 YYYY-MM-DD，日线必填")
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
    optimize_parser.add_argument("--interval", default="1d", help="数据周期，决定使用日线还是分钟线工作流")
    optimize_parser.add_argument("--output-dir", default=None, help="参数搜索结果输出目录")
    optimize_parser.add_argument("--validation-start", default="2026-01-01", help="样本外起始日期")
    optimize_parser.add_argument("--lookback-days", type=int, default=120, help="样本内回看天数")
    optimize_parser.add_argument("--validation-ratio", type=float, default=0.25, help="分钟线样本外比例")

    backtest_parser = subparsers.add_parser("backtest", help="执行样本外验证")
    backtest_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")
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
        help="网格层数，例如 7 表示把剩余网格资金拆成 7 层预算",
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
    report_parser.add_argument("--interval", default="1d", help="数据周期，决定使用日线还是分钟线工作流")
    report_parser.add_argument("--output-dir", default=None, help="工作流中间文件目录")
    report_parser.add_argument("--report-dir", default=None, help="图表与 Markdown 报告输出目录")
    report_parser.add_argument("--validation-start", default="2026-01-01", help="样本外起始日期")
    report_parser.add_argument("--lookback-days", type=int, default=120, help="样本内回看天数")
    report_parser.add_argument("--validation-ratio", type=float, default=0.25, help="分钟线样本外比例")

    run_parser = subparsers.add_parser("run", help="串联下载、寻参、验证和报告生成")
    run_parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Yahoo Finance 标的代码")
    run_parser.add_argument("--start", help="开始日期，格式 YYYY-MM-DD，日线必填")
    run_parser.add_argument("--end", help="结束日期，格式 YYYY-MM-DD，日线必填")
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


def handle_download(args: argparse.Namespace) -> int:
    """执行下载命令。"""
    if not is_intraday_interval(args.interval) and (not args.start or not args.end):
        raise ValueError("日线下载必须提供 --start 和 --end。")

    output = args.output
    if output is None:
        if args.interval == DEFAULT_MINUTE_INTERVAL and args.period == DEFAULT_MINUTE_PERIOD:
            output = str(DEFAULT_MINUTE_DATA_PATH)
        elif args.interval == "1d":
            output = str(DEFAULT_DATA_PATH)
        else:
            output = str(build_default_output_path(args.symbol, args.interval))

    bars = download_price_bars(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start if args.interval == "1d" else None,
        end_date=args.end if args.interval == "1d" else None,
        period=args.period if is_intraday_interval(args.interval) else None,
        proxy=args.proxy,
    )
    output_path = save_price_bars(bars, output)
    print(f"下载完成: {output_path}")
    return 0


def handle_placeholder(args: argparse.Namespace) -> int:
    """为尚未接入的子命令提供一致反馈。"""
    logger.warning("命令 {} 尚未完成实现。", args.command)
    print(f"命令 {args.command} 已保留，但将在后续子任务中接入真实逻辑。")
    return 0


def handle_optimize(args: argparse.Namespace) -> int:
    if is_intraday_interval(args.interval):
        output_dir = args.output_dir or str(DEFAULT_MINUTE_OUTPUT_DIR / "optimize")
        result = run_minute_optimization_workflow(
            data_path=args.data,
            output_dir=output_dir,
            validation_ratio=args.validation_ratio,
        )
    else:
        output_dir = args.output_dir or str(DEFAULT_OUTPUT_DIR / "optimize")
        result = run_optimization_workflow(
            data_path=args.data,
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
    return 0


def handle_backtest(args: argparse.Namespace) -> int:
    if is_intraday_interval(args.interval):
        output_dir = args.output_dir or str(DEFAULT_MINUTE_OUTPUT_DIR / "validation")
        result = run_minute_validation_workflow(
            data_path=args.data,
            grid_spacing_pct=args.grid_spacing,
            grid_count=args.grid_count,
            take_profit_pct=args.take_profit,
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
    return 0


def handle_run(args: argparse.Namespace) -> int:
    if not is_intraday_interval(args.interval) and (not args.start or not args.end):
        raise ValueError("日线完整流程必须提供 --start 和 --end。")

    output_dir = Path(args.output_dir or (DEFAULT_MINUTE_OUTPUT_DIR if is_intraday_interval(args.interval) else DEFAULT_OUTPUT_DIR))
    report_dir = args.report_dir or str(DEFAULT_MINUTE_REPORT_DIR if is_intraday_interval(args.interval) else DEFAULT_REPORT_DIR)
    data_path = DEFAULT_MINUTE_DATA_PATH if is_intraday_interval(args.interval) else DEFAULT_DATA_PATH
    bars = download_price_bars(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start if args.interval == "1d" else None,
        end_date=args.end if args.interval == "1d" else None,
        period=args.period if is_intraday_interval(args.interval) else None,
        proxy=args.proxy,
    )
    save_price_bars(bars, data_path)

    if is_intraday_interval(args.interval):
        result = run_minute_full_workflow(
            data_path=data_path,
            output_dir=output_dir,
            validation_ratio=args.validation_ratio,
        )
        report_path = build_minute_report_markdown(result, report_dir=report_dir)
    else:
        result = run_full_workflow(
            data_path=data_path,
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
        "2026 样本外表现: "
        f"return={validation_summary['ReturnPct']:.2f}% "
        f"max_drawdown={validation_summary['MaxDrawdownPct']:.2f}% "
        f"cost_reduction={validation_summary['CostReductionPct']:.2f}%"
    )
    return 0


def handle_report(args: argparse.Namespace) -> int:
    if is_intraday_interval(args.interval):
        output_dir = args.output_dir or str(DEFAULT_MINUTE_OUTPUT_DIR)
        report_dir = args.report_dir or str(DEFAULT_MINUTE_REPORT_DIR)
        result = run_minute_full_workflow(
            data_path=args.data,
            output_dir=output_dir,
            validation_ratio=args.validation_ratio,
        )
        report_path = build_minute_report_markdown(result, report_dir=report_dir)
    else:
        output_dir = args.output_dir or str(DEFAULT_OUTPUT_DIR)
        report_dir = args.report_dir or str(DEFAULT_REPORT_DIR)
        result = run_full_workflow(
            data_path=args.data,
            output_dir=output_dir,
            validation_start=args.validation_start,
            lookback_days=args.lookback_days,
        )
        report_path = build_report_markdown(result, report_dir=report_dir)
    print(f"报告已生成: {report_path}")
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
