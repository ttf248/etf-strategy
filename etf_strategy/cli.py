import argparse
import os
from pathlib import Path

from loguru import logger

from etf_strategy.config import DEFAULT_DATA_PATH, DEFAULT_OUTPUT_DIR, DEFAULT_SYMBOL
from etf_strategy.data.yahoo import download_daily_bars, save_daily_bars
from etf_strategy.logging_utils import configure_logging
from etf_strategy.workflow import run_full_workflow, run_optimization_workflow, run_validation_workflow


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="基于 Yahoo 数据的策略回测工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_parser = subparsers.add_parser("download", help="下载并标准化历史行情")
    download_parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Yahoo Finance 标的代码")
    download_parser.add_argument("--start", required=True, help="开始日期，格式 YYYY-MM-DD")
    download_parser.add_argument("--end", required=True, help="结束日期，格式 YYYY-MM-DD")
    download_parser.add_argument(
        "--proxy",
        default=os.getenv("ETF_STRATEGY_PROXY"),
        help="访问 Yahoo 所需的代理地址，例如 http://127.0.0.1:7897",
    )
    download_parser.add_argument(
        "--output",
        default=str(DEFAULT_DATA_PATH),
        help="标准化 CSV 输出路径",
    )

    optimize_parser = subparsers.add_parser("optimize", help="执行样本内参数搜索")
    optimize_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")
    optimize_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR / "optimize"), help="参数搜索结果输出目录")
    optimize_parser.add_argument("--validation-start", default="2026-01-01", help="样本外起始日期")
    optimize_parser.add_argument("--lookback-days", type=int, default=120, help="样本内回看天数")

    backtest_parser = subparsers.add_parser("backtest", help="执行样本外验证")
    backtest_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")
    backtest_parser.add_argument("--grid-spacing", type=float, required=True, help="网格间距，例如 0.05")
    backtest_parser.add_argument("--grid-count", type=int, required=True, help="网格层数")
    backtest_parser.add_argument("--take-profit", type=float, required=True, help="网格止盈比例，例如 0.05")
    backtest_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR / "validation"), help="样本外验证输出目录")
    backtest_parser.add_argument("--validation-start", default="2026-01-01", help="样本外起始日期")
    backtest_parser.add_argument("--lookback-days", type=int, default=120, help="样本内回看天数")

    report_parser = subparsers.add_parser("report", help="生成图表与中文报告")
    report_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")

    run_parser = subparsers.add_parser("run", help="串联下载、寻参、验证和报告生成")
    run_parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Yahoo Finance 标的代码")
    run_parser.add_argument("--start", required=True, help="开始日期，格式 YYYY-MM-DD")
    run_parser.add_argument("--end", required=True, help="结束日期，格式 YYYY-MM-DD")
    run_parser.add_argument(
        "--proxy",
        default=os.getenv("ETF_STRATEGY_PROXY"),
        help="访问 Yahoo 所需的代理地址，例如 http://127.0.0.1:7897",
    )
    run_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="完整工作流输出目录")
    run_parser.add_argument("--validation-start", default="2026-01-01", help="样本外起始日期")
    run_parser.add_argument("--lookback-days", type=int, default=120, help="样本内回看天数")

    return parser


def handle_download(args: argparse.Namespace) -> int:
    """执行下载命令。"""
    bars = download_daily_bars(args.symbol, args.start, args.end, proxy=args.proxy)
    output_path = save_daily_bars(bars, args.output)
    print(f"下载完成: {output_path}")
    return 0


def handle_placeholder(args: argparse.Namespace) -> int:
    """为尚未接入的子命令提供一致反馈。"""
    logger.warning("命令 {} 尚未完成实现。", args.command)
    print(f"命令 {args.command} 已保留，但将在后续子任务中接入真实逻辑。")
    return 0


def handle_optimize(args: argparse.Namespace) -> int:
    result = run_optimization_workflow(
        data_path=args.data,
        output_dir=args.output_dir,
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
    result = run_validation_workflow(
        data_path=args.data,
        grid_spacing_pct=args.grid_spacing,
        grid_count=args.grid_count,
        take_profit_pct=args.take_profit,
        output_dir=args.output_dir,
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
    output_dir = Path(args.output_dir)
    data_path = DEFAULT_DATA_PATH
    bars = download_daily_bars(args.symbol, args.start, args.end, proxy=args.proxy)
    save_daily_bars(bars, data_path)

    result = run_full_workflow(
        data_path=data_path,
        output_dir=output_dir,
        validation_start=args.validation_start,
        lookback_days=args.lookback_days,
    )
    best_summary = result["optimization"]["best_run"]["summary"]
    validation_summary = result["validation"]["run"]["summary"]
    print(f"完整工作流已完成，汇总文件: {result['combined_summary_path']}")
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


def main(argv: list[str] | None = None) -> int:
    """命令行主入口。"""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "download": handle_download,
        "optimize": handle_optimize,
        "backtest": handle_backtest,
        "report": handle_placeholder,
        "run": handle_run,
    }
    return handlers[args.command](args)
