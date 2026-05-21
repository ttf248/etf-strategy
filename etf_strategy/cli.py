import argparse
import os

from loguru import logger

from etf_strategy.config import DEFAULT_DATA_PATH, DEFAULT_SYMBOL
from etf_strategy.data.yahoo import download_daily_bars, save_daily_bars
from etf_strategy.logging_utils import configure_logging


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

    backtest_parser = subparsers.add_parser("backtest", help="执行样本外验证")
    backtest_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")

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


def main(argv: list[str] | None = None) -> int:
    """命令行主入口。"""
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "download": handle_download,
        "optimize": handle_placeholder,
        "backtest": handle_placeholder,
        "report": handle_placeholder,
        "run": handle_placeholder,
    }
    return handlers[args.command](args)
