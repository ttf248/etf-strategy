import argparse


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="基于 Yahoo 数据的策略回测工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_parser = subparsers.add_parser("download", help="下载并标准化历史行情")
    download_parser.add_argument("--symbol", default="1810.HK", help="Yahoo Finance 标的代码")
    download_parser.add_argument("--start", required=True, help="开始日期，格式 YYYY-MM-DD")
    download_parser.add_argument("--end", required=True, help="结束日期，格式 YYYY-MM-DD")
    download_parser.add_argument(
        "--output",
        default="data/processed/xiaomi_1810_hk_daily.csv",
        help="标准化 CSV 输出路径",
    )

    optimize_parser = subparsers.add_parser("optimize", help="执行样本内参数搜索")
    optimize_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")

    backtest_parser = subparsers.add_parser("backtest", help="执行样本外验证")
    backtest_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")

    report_parser = subparsers.add_parser("report", help="生成图表与中文报告")
    report_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")

    run_parser = subparsers.add_parser("run", help="串联下载、寻参、验证和报告生成")
    run_parser.add_argument("--symbol", default="1810.HK", help="Yahoo Finance 标的代码")
    run_parser.add_argument("--start", required=True, help="开始日期，格式 YYYY-MM-DD")
    run_parser.add_argument("--end", required=True, help="结束日期，格式 YYYY-MM-DD")

    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行主入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    print(f"命令 {args.command} 已解析，后续步骤将由对应模块接管。")
    return 0
