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

import pandas as pd
from loguru import logger

from etf_strategy.config import (
    DEFAULT_BATCH_REPORT_DIR,
    DEFAULT_DATA_PATH,
    DEFAULT_MINUTE_OUTPUT_DIR,
    DEFAULT_MINUTE_REPORT_DIR,
    DEFAULT_MINUTE_DATA_PATH,
    DEFAULT_MINUTE_INTERVAL,
    DEFAULT_MINUTE_PERIOD,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_DIR,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SYMBOL,
)
from etf_strategy.data.market_rules import infer_symbol_from_data_path
from etf_strategy.data.yahoo import (
    build_default_output_path,
    download_price_bars,
    is_intraday_interval,
    save_price_bars,
)
from etf_strategy.logging_utils import configure_logging
from etf_strategy.reporting import (
    build_minute_report_markdown,
    build_report_index_entry,
    build_report_markdown,
    build_strategy_comparison_report,
    build_unified_report_index,
    bootstrap_report_registry,
    register_report_index_entries,
    resolve_symbol_spec,
)
from etf_strategy.settings import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_VALIDATION_RATIO,
    DEFAULT_VALIDATION_START,
    DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    StrategyKind,
    build_execution_config,
)
from etf_strategy.symbols import SYMBOL_SETS, SymbolSpec
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
    download_parser.add_argument("--interval", default=DEFAULT_MINUTE_INTERVAL, help="K 线周期，例如 1d、5m、15m、60m")
    download_parser.add_argument(
        "--period",
        default=DEFAULT_MINUTE_PERIOD,
        help="分钟 K 线优先使用的区间，例如 5d、30d、60d",
    )
    download_parser.add_argument(
        "--proxy",
        default=os.getenv("ETF_STRATEGY_PROXY"),
        help="访问 Yahoo 必须配置的代理地址，例如 http://127.0.0.1:7897",
    )
    download_parser.add_argument(
        "--output",
        default=None,
        help="标准化 CSV 输出路径",
    )

    optimize_parser = subparsers.add_parser("optimize", help="执行样本内参数搜索")
    optimize_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")
    optimize_parser.add_argument("--symbol", default=None, help="Yahoo Finance 标的代码；不传时尝试从文件名推断")
    optimize_parser.add_argument("--interval", default=DEFAULT_MINUTE_INTERVAL, help="数据周期，决定使用日线还是分钟线工作流")
    optimize_parser.add_argument("--output-dir", default=None, help="参数搜索结果输出目录")
    optimize_parser.add_argument("--validation-start", default=DEFAULT_VALIDATION_START, help="样本外起始日期")
    optimize_parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="样本内回看天数")
    optimize_parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO, help="分钟线样本外比例")
    optimize_parser.add_argument("--wf-window-count", type=int, default=DEFAULT_WALK_FORWARD_WINDOW_COUNT, help="样本内稳健性窗口数")
    optimize_parser.add_argument("--wf-min-window-size", type=int, default=DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE, help="单个稳健性窗口最少 K 线数")
    optimize_parser.add_argument("--jobs", default="1", help="寻参并行线程数；可传整数或 auto")
    optimize_parser.add_argument("--cache-dir", default=None, help="候选参数回测缓存目录")
    _add_strategy_arguments(optimize_parser)
    _add_execution_arguments(optimize_parser)

    backtest_parser = subparsers.add_parser("backtest", help="执行样本外验证")
    backtest_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")
    backtest_parser.add_argument("--symbol", default=None, help="Yahoo Finance 标的代码；不传时尝试从文件名推断")
    backtest_parser.add_argument("--interval", default=DEFAULT_MINUTE_INTERVAL, help="数据周期，决定使用日线还是分钟线工作流")
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
    backtest_parser.add_argument("--validation-start", default=DEFAULT_VALIDATION_START, help="样本外起始日期")
    backtest_parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="样本内回看天数")
    backtest_parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO, help="分钟线样本外比例")
    _add_strategy_arguments(backtest_parser)
    _add_execution_arguments(backtest_parser)

    report_parser = subparsers.add_parser("report", help="生成图表与中文报告")
    report_parser.add_argument("--data", required=True, help="标准化行情 CSV 路径")
    report_parser.add_argument("--symbol", default=None, help="Yahoo Finance 标的代码；不传时尝试从文件名推断")
    report_parser.add_argument("--interval", default=DEFAULT_MINUTE_INTERVAL, help="数据周期，决定使用日线还是分钟线工作流")
    report_parser.add_argument("--output-dir", default=None, help="工作流中间文件目录")
    report_parser.add_argument("--report-dir", default=None, help="图表与 Markdown 报告输出目录")
    report_parser.add_argument("--validation-start", default=DEFAULT_VALIDATION_START, help="样本外起始日期")
    report_parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="样本内回看天数")
    report_parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO, help="分钟线样本外比例")
    report_parser.add_argument("--wf-window-count", type=int, default=DEFAULT_WALK_FORWARD_WINDOW_COUNT, help="样本内稳健性窗口数")
    report_parser.add_argument("--wf-min-window-size", type=int, default=DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE, help="单个稳健性窗口最少 K 线数")
    report_parser.add_argument("--jobs", default="1", help="寻参并行线程数；可传整数或 auto")
    report_parser.add_argument("--cache-dir", default=None, help="候选参数回测缓存目录")
    _add_strategy_arguments(report_parser)
    report_parser.add_argument("--compare-strategies", action="store_true", help="同时输出当前周期下多策略对比报告")
    _add_execution_arguments(report_parser)

    run_parser = subparsers.add_parser("run", help="串联下载、寻参、验证和报告生成")
    run_parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Yahoo Finance 标的代码")
    run_parser.add_argument("--start", help="开始日期，格式 YYYY-MM-DD；日线不传时默认下载可用全历史")
    run_parser.add_argument("--end", help="结束日期，格式 YYYY-MM-DD；和 --start 一起使用")
    run_parser.add_argument("--interval", default=DEFAULT_MINUTE_INTERVAL, help="K 线周期，例如 1d、5m、15m、60m")
    run_parser.add_argument("--period", default=DEFAULT_MINUTE_PERIOD, help="分钟 K 线优先使用的区间，例如 5d、30d、60d")
    run_parser.add_argument(
        "--proxy",
        default=os.getenv("ETF_STRATEGY_PROXY"),
        help="访问 Yahoo 必须配置的代理地址，例如 http://127.0.0.1:7897",
    )
    run_parser.add_argument("--output-dir", default=None, help="完整工作流输出目录")
    run_parser.add_argument("--report-dir", default=None, help="图表与 Markdown 报告输出目录")
    run_parser.add_argument("--validation-start", default=DEFAULT_VALIDATION_START, help="样本外起始日期")
    run_parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="样本内回看天数")
    run_parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO, help="分钟线样本外比例")
    run_parser.add_argument("--wf-window-count", type=int, default=DEFAULT_WALK_FORWARD_WINDOW_COUNT, help="样本内稳健性窗口数")
    run_parser.add_argument("--wf-min-window-size", type=int, default=DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE, help="单个稳健性窗口最少 K 线数")
    run_parser.add_argument("--jobs", default="1", help="寻参并行线程数；可传整数或 auto")
    run_parser.add_argument("--cache-dir", default=None, help="候选参数回测缓存目录")
    _add_strategy_arguments(run_parser)
    run_parser.add_argument("--compare-strategies", action="store_true", help="同时输出当前周期下多策略对比报告")
    _add_execution_arguments(run_parser)

    batch_parser = subparsers.add_parser("batch", help="批量执行多个标的的完整研究流程")
    batch_parser.add_argument("--symbols", default=None, help="逗号分隔的 Yahoo Finance 标的代码，例如 1810.HK,SPY")
    batch_parser.add_argument("--symbol-set", choices=sorted(SYMBOL_SETS), default=None, help="内置批量标的池")
    batch_parser.add_argument("--interval", default=DEFAULT_MINUTE_INTERVAL, help="K 线周期，例如 1d、15m")
    batch_parser.add_argument("--period", default=DEFAULT_MINUTE_PERIOD, help="分钟 K 线下载窗口，例如 60d")
    batch_parser.add_argument("--download", action="store_true", help="批量运行前先下载并合并行情")
    batch_parser.add_argument("--proxy", default=os.getenv("ETF_STRATEGY_PROXY"), help="访问 Yahoo 必须配置的代理地址")
    batch_parser.add_argument("--output-dir", default="outputs/batch", help="批量中间结果与汇总输出目录")
    batch_parser.add_argument("--report-dir", default=str(DEFAULT_BATCH_REPORT_DIR), help="批量报告输出目录")
    batch_parser.add_argument("--validation-start", default=DEFAULT_VALIDATION_START, help="日线样本外起始日期")
    batch_parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="日线样本内回看天数")
    batch_parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO, help="分钟线样本外比例")
    batch_parser.add_argument("--wf-window-count", type=int, default=DEFAULT_WALK_FORWARD_WINDOW_COUNT, help="样本内稳健性窗口数")
    batch_parser.add_argument("--wf-min-window-size", type=int, default=DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE, help="单个稳健性窗口最少 K 线数")
    batch_parser.add_argument("--jobs", default="1", help="单标的寻参并行线程数；可传整数或 auto")
    batch_parser.add_argument("--cache-dir", default=None, help="候选参数回测缓存目录")
    _add_strategy_arguments(batch_parser)
    batch_parser.add_argument("--compare-strategies", action="store_true", help="批量为每个标的生成当前周期的多策略对比报告")
    _add_execution_arguments(batch_parser)

    return parser


def _add_execution_arguments(parser: argparse.ArgumentParser) -> None:
    """给会执行回测的命令补充执行口径参数。"""
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
    parser.add_argument(
        "--benchmark",
        choices=["cash_idle", "buy_hold"],
        default=None,
        help="报告重点对照基准；默认随执行口径",
    )
    parser.add_argument(
        "--grid-mode",
        choices=["cash"],
        default=None,
        help="网格资金模式；cash 表示不建底仓，只在触发网格价位时投入现金",
    )
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


def _add_strategy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--strategy",
        choices=["grid", "daily_rebound", "minute_rebound", "minute_rebound_with_fade_filter"],
        default="grid",
        help="策略类型：grid 为现有网格；其余为反转类策略",
    )


def _build_execution_from_args(args: argparse.Namespace):
    """从命令行参数构造执行口径配置。"""
    return build_execution_config(
        profile=args.execution_profile,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        max_position_ratio=args.max_position_ratio,
        stop_loss_pct=args.stop_loss_pct,
        cooldown_bars=args.cooldown_bars,
        benchmark=args.benchmark,
        grid_mode=args.grid_mode,
        left_side_policy=args.left_side_policy,
        force_exit_loss_pct=args.force_exit_loss_pct,
    )


def _resolve_jobs(value: str | int) -> int:
    """解析并行线程数。"""
    if isinstance(value, int):
        return max(1, value)
    if value == "auto":
        return max(1, (os.cpu_count() or 2) - 1)
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("--jobs 必须是正整数或 auto。")
    return parsed


def _default_compare_strategy_kinds(interval: str) -> list[StrategyKind]:
    if is_intraday_interval(interval):
        return ["grid", "minute_rebound", "minute_rebound_with_fade_filter"]
    return ["grid", "daily_rebound"]


def _strategy_display_name(strategy_kind: str) -> str:
    labels = {
        "grid": "网格",
        "daily_rebound": "日线超跌反弹",
        "minute_rebound": "分钟急跌反抽",
        "minute_rebound_with_fade_filter": "分钟反抽+冲高回落过滤",
        "compare": "多策略对比",
    }
    return labels.get(strategy_kind, strategy_kind)


def _single_report_index_entry(
    report_path: str | Path,
    workflow_result: dict[str, object],
    symbol: str,
    interval: str,
    strategy_kind: str | None = None,
    spec: SymbolSpec | None = None,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
) -> dict[str, object]:
    best_summary = workflow_result["optimization"]["best_run"]["summary"]
    validation_summary = workflow_result["validation"]["run"]["summary"]
    resolved_strategy_kind = str(
        strategy_kind
        or best_summary.get("StrategyKind")
        or validation_summary.get("StrategyKind")
        or workflow_result.get("strategy_kind", "grid")
    )
    resolved_symbol = str(symbol or best_summary.get("Symbol") or validation_summary.get("Symbol") or DEFAULT_SYMBOL)
    note = _format_best_parameter_summary(best_summary)
    return build_report_index_entry(
        report_path=report_path,
        symbol=resolved_symbol,
        interval=interval,
        report_view=resolved_strategy_kind,
        strategy_kind=resolved_strategy_kind,
        strategy_name=_strategy_display_name(resolved_strategy_kind),
        validation_return_pct=float(validation_summary.get("NetReturnPct", validation_summary.get("ReturnPct", 0.0))),
        max_drawdown_pct=float(validation_summary.get("MaxDrawdownPct", 0.0)),
        note=note,
        category=spec.category if spec else None,
        name=spec.name if spec else None,
        source=spec.source if spec else None,
        report_root=report_root,
    )


def _comparison_report_index_entry(
    report_path: str | Path,
    comparison_results: dict[str, dict[str, object]],
    interval: str,
    symbol: str,
    spec: SymbolSpec | None = None,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
) -> dict[str, object]:
    ranked = sorted(
        comparison_results.values(),
        key=lambda workflow_result: (
            float(workflow_result["validation"]["run"]["summary"].get("NetReturnPct", workflow_result["validation"]["run"]["summary"].get("ReturnPct", 0.0))),
            -float(workflow_result["validation"]["run"]["summary"].get("MaxDrawdownPct", 0.0)),
        ),
        reverse=True,
    )
    recommended = ranked[0]
    best_summary = recommended["optimization"]["best_run"]["summary"]
    validation_summary = recommended["validation"]["run"]["summary"]
    strategy_list = " / ".join(_strategy_display_name(key) for key in comparison_results)
    note = f"推荐 {_strategy_display_name(str(best_summary.get('StrategyKind', 'grid')))}；对比 {strategy_list}"
    return build_report_index_entry(
        report_path=report_path,
        symbol=symbol,
        interval=interval,
        report_view="compare",
        strategy_kind="compare",
        strategy_name="多策略对比",
        validation_return_pct=float(validation_summary.get("NetReturnPct", validation_summary.get("ReturnPct", 0.0))),
        max_drawdown_pct=float(validation_summary.get("MaxDrawdownPct", 0.0)),
        note=note,
        category=spec.category if spec else None,
        name=spec.name if spec else None,
        source=spec.source if spec else None,
        report_root=report_root,
    )


def _failed_report_index_entry(
    report_path: str | Path,
    symbol: str,
    interval: str,
    report_view: str,
    error: Exception,
    spec: SymbolSpec | None = None,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
) -> dict[str, object]:
    return build_report_index_entry(
        report_path=report_path,
        symbol=symbol,
        interval=interval,
        report_view=report_view,
        strategy_kind=report_view,
        strategy_name=_strategy_display_name(report_view),
        validation_return_pct="",
        max_drawdown_pct="",
        note=str(error),
        status="failed",
        error=str(error),
        category=spec.category if spec else None,
        name=spec.name if spec else None,
        source=spec.source if spec else None,
        report_root=report_root,
    )


def _refresh_unified_report_index(entries: list[dict[str, object]], report_root: str | Path) -> Path:
    bootstrap_report_registry(report_root=report_root)
    register_report_index_entries(entries, report_root=report_root)
    return build_unified_report_index(report_root=report_root)


def _resolve_report_root(report_dir: str | Path) -> Path:
    path = Path(report_dir)
    if path.name in {"daily", "minute"} and path.parent != path:
        return path.parent.parent if path.parent.parent != path.parent else path.parent
    return path


def _resolve_report_symbol(explicit_symbol: str | None, data_path: str | Path | None = None) -> str:
    if explicit_symbol:
        return explicit_symbol
    if data_path:
        return infer_symbol_from_data_path(str(data_path))
    return DEFAULT_SYMBOL


def _format_best_parameter_summary(summary: dict[str, object]) -> str:
    strategy_kind = str(summary.get("StrategyKind", "grid"))
    score = float(summary.get("Score", 0.0))
    if strategy_kind == "grid":
        return (
            f"grid_spacing={float(summary['GridSpacingPct']):.2f}% "
            f"grid_count={int(summary['GridCount'])} "
            f"take_profit={float(summary['TakeProfitPct']):.2f}% "
            f"score={score:.2f}"
        )
    parameter_fields = [
        key
        for key in [
            "rsi_window",
            "rsi_entry",
            "ma_window",
            "deviation_entry_pct",
            "lookback_bars",
            "drop_entry_pct",
            "stop_loss_atr",
            "stop_loss_pct",
            "max_hold_bars",
            "fade_filter_upper_shadow_pct",
            "fade_filter_block_bars",
        ]
        if key in summary
    ]
    details = " ".join(f"{field}={summary[field]}" for field in parameter_fields)
    return (
        f"strategy={strategy_kind} "
        f"{details} "
        f"take_profit={float(summary['TakeProfitPct']):.2f}% "
        f"score={score:.2f}"
    ).strip()


def _run_full_workflow_from_args(
    data_path: str | Path,
    args: argparse.Namespace,
    execution_config,
) -> dict[str, object]:
    intraday_mode = is_intraday_interval(args.interval)
    jobs = _resolve_jobs(args.jobs)
    if intraday_mode:
        return run_minute_full_workflow(
            data_path=data_path,
            symbol=args.symbol,
            output_dir=args.output_dir or str(DEFAULT_MINUTE_OUTPUT_DIR),
            validation_ratio=args.validation_ratio,
            strategy_kind=args.strategy,
            execution_config=execution_config,
            wf_window_count=args.wf_window_count,
            wf_min_window_size=args.wf_min_window_size,
            jobs=jobs,
            cache_dir=args.cache_dir,
        )
    return run_full_workflow(
        data_path=data_path,
        symbol=args.symbol,
        output_dir=args.output_dir or str(DEFAULT_OUTPUT_DIR),
        validation_start=args.validation_start,
        lookback_days=args.lookback_days,
        strategy_kind=args.strategy,
        execution_config=execution_config,
        wf_window_count=args.wf_window_count,
        wf_min_window_size=args.wf_min_window_size,
        jobs=jobs,
        cache_dir=args.cache_dir,
    )


def _run_comparison_workflows(data_path: str | Path, args: argparse.Namespace, execution_config) -> dict[str, dict[str, object]]:
    original_output_dir = args.output_dir
    results: dict[str, dict[str, object]] = {}
    for strategy_kind in _default_compare_strategy_kinds(args.interval):
        args.strategy = strategy_kind
        strategy_slug = strategy_kind.replace("minute_", "").replace("daily_", "")
        base_output_dir = Path(original_output_dir or (DEFAULT_MINUTE_OUTPUT_DIR if is_intraday_interval(args.interval) else DEFAULT_OUTPUT_DIR))
        args.output_dir = str(base_output_dir / strategy_slug)
        results[strategy_kind] = _run_full_workflow_from_args(data_path, args, execution_config)
    args.output_dir = original_output_dir
    return results


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
    logger.info("收到 optimize 命令: data={} interval={} strategy={}", args.data, args.interval, args.strategy)
    execution_config = _build_execution_from_args(args)
    if is_intraday_interval(args.interval):
        output_dir = args.output_dir or str(DEFAULT_MINUTE_OUTPUT_DIR / "optimize")
        result = run_minute_optimization_workflow(
            data_path=args.data,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_ratio=args.validation_ratio,
            strategy_kind=args.strategy,
            execution_config=execution_config,
            wf_window_count=args.wf_window_count,
            wf_min_window_size=args.wf_min_window_size,
            jobs=_resolve_jobs(args.jobs),
            cache_dir=args.cache_dir,
        )
    else:
        output_dir = args.output_dir or str(DEFAULT_OUTPUT_DIR / "optimize")
        result = run_optimization_workflow(
            data_path=args.data,
            symbol=args.symbol,
            output_dir=output_dir,
            validation_start=args.validation_start,
            lookback_days=args.lookback_days,
            strategy_kind=args.strategy,
            execution_config=execution_config,
            wf_window_count=args.wf_window_count,
            wf_min_window_size=args.wf_min_window_size,
            jobs=_resolve_jobs(args.jobs),
            cache_dir=args.cache_dir,
        )
    best_summary = result["best_run"]["summary"]
    print(f"样本内最优参数已生成: {result['results_path']}")
    print(f"最优参数: {_format_best_parameter_summary(best_summary)}")
    logger.info("optimize 命令完成: results={} elapsed={:.2f}s", result["results_path"], perf_counter() - started_at)
    return 0


def handle_backtest(args: argparse.Namespace) -> int:
    """执行样本外验证。"""
    started_at = perf_counter()
    if args.strategy != "grid":
        raise ValueError("backtest 命令当前仅支持 grid；反转类策略请使用 optimize/report/run 自动选参与验证。")
    logger.info(
        "收到 backtest 命令: data={} interval={} strategy={} spacing={:.2f}% grid_count={} take_profit={:.2f}%",
        args.data,
        args.interval,
        args.strategy,
        args.grid_spacing * 100,
        args.grid_count,
        args.take_profit * 100,
    )
    execution_config = _build_execution_from_args(args)
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
            execution_config=execution_config,
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
            execution_config=execution_config,
        )
    summary = result["run"]["summary"]
    print(
        "样本外验证完成: "
        f"return={summary['ReturnPct']:.2f}% "
        f"max_drawdown={summary['MaxDrawdownPct']:.2f}% "
        f"closed_grid_profit={summary.get('ClosedGridNetProfit', 0.0):.2f}"
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
    report_root = _resolve_report_root(report_dir)
    data_path = _resolve_download_output_path(args.symbol, args.interval, args.period, output=None)
    logger.info(
        "收到 run 命令: symbol={} interval={} strategy={} compare={} data_path={} output_dir={} report_dir={}",
        args.symbol,
        args.interval,
        args.strategy,
        args.compare_strategies,
        data_path,
        output_dir,
        report_dir,
    )
    execution_config = _build_execution_from_args(args)
    logger.info("[1/3] 开始下载并合并最新行情")
    bars = download_price_bars(
        symbol=args.symbol,
        interval=args.interval,
        start_date=args.start if args.interval == "1d" else None,
        end_date=args.end if args.interval == "1d" else None,
        period=args.period if intraday_mode else None,
        proxy=args.proxy,
    )
    merged_data_path = save_price_bars(bars, data_path, interval=args.interval, merge_with_existing=True)
    logger.info("[1/3] 下载与落盘完成: data_path={}", merged_data_path)

    # `run` 总是先把最新下载结果和本地样本合并落盘，再交给统一工作流和报告层复用。
    logger.info("[2/3] 开始执行完整回测工作流")
    args.output_dir = str(output_dir)
    if args.compare_strategies:
        comparison_results = _run_comparison_workflows(data_path, args, execution_config)
        result = comparison_results[args.strategy] if args.strategy in comparison_results else next(iter(comparison_results.values()))
        logger.info("[2/3] 多策略工作流完成: strategies={}", list(comparison_results))
    else:
        result = _run_full_workflow_from_args(data_path, args, execution_config)
        comparison_results = None
        logger.info("[2/3] 完整回测工作流完成: summary={}", result["combined_summary_path"])
    logger.info("[3/3] 开始生成正式报告")
    if comparison_results is not None:
        report_path = build_strategy_comparison_report(
            strategy_results=comparison_results,
            interval=args.interval,
            symbol=args.symbol,
            report_dir=report_dir,
        )
    elif intraday_mode:
        report_path = build_minute_report_markdown(result, report_dir=report_dir)
    else:
        report_path = build_report_markdown(result, report_dir=report_dir)
    report_symbol = _resolve_report_symbol(args.symbol)
    index_entries = [
        _comparison_report_index_entry(report_path, comparison_results, args.interval, args.symbol, report_root=report_root)
        if comparison_results is not None
        else _single_report_index_entry(
            report_path,
            result,
            symbol=report_symbol,
            interval=args.interval,
            strategy_kind=args.strategy,
            report_root=report_root,
        )
    ]
    index_path = _refresh_unified_report_index(index_entries, report_root=report_root)
    logger.info("[3/3] 正式报告生成完成: report={}", report_path)
    best_summary = result["optimization"]["best_run"]["summary"]
    validation_summary = result["validation"]["run"]["summary"]
    print(f"完整工作流已完成，汇总文件: {result['combined_summary_path']}")
    print(f"中文报告: {report_path}")
    print(f"正式汇总报告: {index_path}")
    print(f"样本内最优参数: {_format_best_parameter_summary(best_summary)}")
    print(
        f"{'分钟线样本外表现' if intraday_mode else '2026 样本外表现'}: "
        f"return={validation_summary['ReturnPct']:.2f}% "
        f"max_drawdown={validation_summary['MaxDrawdownPct']:.2f}% "
        f"closed_grid_profit={validation_summary.get('ClosedGridNetProfit', 0.0):.2f}"
    )
    logger.info("run 命令完成: report={} elapsed={:.2f}s", report_path, perf_counter() - started_at)
    return 0


def handle_report(args: argparse.Namespace) -> int:
    """基于已有 CSV 重跑工作流并生成正式报告。"""
    started_at = perf_counter()
    logger.info("收到 report 命令: data={} interval={} strategy={} compare={}", args.data, args.interval, args.strategy, args.compare_strategies)
    logger.info("[1/2] 开始重跑工作流并准备报告数据")
    execution_config = _build_execution_from_args(args)
    output_dir = args.output_dir or str(DEFAULT_MINUTE_OUTPUT_DIR if is_intraday_interval(args.interval) else DEFAULT_OUTPUT_DIR)
    report_dir = args.report_dir or str(DEFAULT_MINUTE_REPORT_DIR if is_intraday_interval(args.interval) else DEFAULT_REPORT_DIR)
    report_root = _resolve_report_root(report_dir)
    args.output_dir = output_dir
    if args.compare_strategies:
        comparison_results = _run_comparison_workflows(args.data, args, execution_config)
        result = comparison_results[args.strategy] if args.strategy in comparison_results else next(iter(comparison_results.values()))
    else:
        comparison_results = None
        result = _run_full_workflow_from_args(args.data, args, execution_config)
    logger.info("[2/2] 工作流数据准备完成，开始写正式报告")
    if comparison_results is not None:
        report_path = build_strategy_comparison_report(
            strategy_results=comparison_results,
            interval=args.interval,
            symbol=args.symbol or DEFAULT_SYMBOL,
            report_dir=report_dir,
        )
    elif is_intraday_interval(args.interval):
        report_path = build_minute_report_markdown(result, report_dir=report_dir)
    else:
        report_path = build_report_markdown(result, report_dir=report_dir)
    report_symbol = _resolve_report_symbol(args.symbol, args.data)
    index_entries = [
        _comparison_report_index_entry(
            report_path,
            comparison_results,
            args.interval,
            report_symbol,
            report_root=report_root,
        )
        if comparison_results is not None
        else _single_report_index_entry(
            report_path,
            result,
            symbol=report_symbol,
            interval=args.interval,
            strategy_kind=args.strategy,
            report_root=report_root,
        )
    ]
    index_path = _refresh_unified_report_index(index_entries, report_root=report_root)
    print(f"报告已生成: {report_path}")
    print(f"正式汇总报告: {index_path}")
    logger.info("report 命令完成: report={} elapsed={:.2f}s", report_path, perf_counter() - started_at)
    return 0


def _batch_symbol_slug(symbol: str) -> str:
    """把标的代码转换为批量输出目录名。"""
    return symbol.strip().lower().replace(".", "_").replace("^", "index_")


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


def _write_failed_batch_report(
    symbol_report_dir: Path,
    symbol: str,
    spec: SymbolSpec,
    interval: str,
    error: Exception,
    report_view: str = "grid",
) -> Path:
    """为失败标的生成可点击的失败报告，保证索引表每一行都有落点。"""
    symbol_report_dir.mkdir(parents=True, exist_ok=True)
    suffix = "strategy_compare_report" if report_view == "compare" else f"{report_view}_report"
    target = symbol_report_dir / f"{_batch_symbol_slug(symbol)}_{interval}_{suffix}.md"
    content = "\n".join(
        [
            f"# {symbol} 批量回测失败记录",
            "",
            f"- 标的：`{symbol}`",
            f"- 名称：{spec.name}",
            f"- 分类：{spec.category}",
            "- 状态：failed",
            f"- 错误：`{str(error)}`",
            "",
            "该文件用于批量报告索引跳转。请先检查数据下载、Yahoo 限流、代理或交易单位解析问题后重跑。",
            "",
        ]
    )
    target.write_text(content, encoding="utf-8")
    return target


def handle_batch(args: argparse.Namespace) -> int:
    """批量执行多个标的的完整研究流程。"""
    started_at = perf_counter()
    symbols, specs_by_symbol = _resolve_batch_symbols(args)

    intraday_mode = is_intraday_interval(args.interval)
    output_root = Path(args.output_dir)
    report_root = Path(args.report_dir)
    execution_config = _build_execution_from_args(args)
    jobs = _resolve_jobs(args.jobs)
    rows: list[dict[str, object]] = []
    index_entries: list[dict[str, object]] = []
    logger.info("收到 batch 命令: symbols={} interval={} download={}", symbols, args.interval, args.download)

    for symbol in symbols:
        symbol_started_at = perf_counter()
        spec = specs_by_symbol[symbol]
        slug = _batch_symbol_slug(symbol)
        data_path = _resolve_download_output_path(symbol, args.interval, args.period, output=None)
        symbol_output_dir = output_root / slug
        symbol_report_dir = report_root / slug / ("minute" if intraday_mode else "daily")
        download_completed = False
        try:
            if args.download:
                logger.info("[batch] 开始下载并合并行情: symbol={} interval={}", symbol, args.interval)
                bars = download_price_bars(
                    symbol=symbol,
                    interval=args.interval,
                    start_date=None if intraday_mode else None,
                    end_date=None if intraday_mode else None,
                    period=args.period if intraday_mode else None,
                    proxy=args.proxy,
                )
                save_price_bars(bars, data_path, interval=args.interval, merge_with_existing=True)
                download_completed = True
            if not data_path.exists():
                raise FileNotFoundError(f"行情文件不存在，请先下载或传 --download: {data_path}")

            cache_dir = Path(args.cache_dir) / slug if args.cache_dir else None
            if args.compare_strategies:
                batch_args = argparse.Namespace(**vars(args))
                batch_args.symbol = symbol
                batch_args.output_dir = str(symbol_output_dir)
                batch_args.cache_dir = str(cache_dir) if cache_dir else None
                comparison_results = _run_comparison_workflows(data_path, batch_args, execution_config)
                result = comparison_results[args.strategy] if args.strategy in comparison_results else next(iter(comparison_results.values()))
                report_path = build_strategy_comparison_report(
                    strategy_results=comparison_results,
                    interval=args.interval,
                    symbol=symbol,
                    report_dir=symbol_report_dir,
                )
                index_entries.append(
                    _comparison_report_index_entry(
                        report_path=report_path,
                        comparison_results=comparison_results,
                        interval=args.interval,
                        symbol=symbol,
                        spec=spec,
                        report_root=report_root,
                    )
                )
            else:
                if intraday_mode:
                    result = run_minute_full_workflow(
                        data_path=data_path,
                        symbol=symbol,
                        output_dir=symbol_output_dir,
                        validation_ratio=args.validation_ratio,
                        strategy_kind=args.strategy,
                        execution_config=execution_config,
                        wf_window_count=args.wf_window_count,
                        wf_min_window_size=args.wf_min_window_size,
                        jobs=jobs,
                        cache_dir=cache_dir,
                    )
                    report_path = build_minute_report_markdown(result, report_dir=symbol_report_dir)
                else:
                    result = run_full_workflow(
                        data_path=data_path,
                        symbol=symbol,
                        output_dir=symbol_output_dir,
                        validation_start=args.validation_start,
                        lookback_days=args.lookback_days,
                        strategy_kind=args.strategy,
                        execution_config=execution_config,
                        wf_window_count=args.wf_window_count,
                        wf_min_window_size=args.wf_min_window_size,
                        jobs=jobs,
                        cache_dir=cache_dir,
                    )
                    report_path = build_report_markdown(result, report_dir=symbol_report_dir)
                index_entries.append(
                    _single_report_index_entry(
                        report_path=report_path,
                        workflow_result=result,
                        symbol=symbol,
                        interval=args.interval,
                        strategy_kind=args.strategy,
                        spec=spec,
                        report_root=report_root,
                    )
                )

            best_summary = result["optimization"]["best_run"]["summary"]
            validation_summary = result["validation"]["run"]["summary"]
            rows.append(
                {
                    "Symbol": symbol,
                    "Name": spec.name,
                    "Category": spec.category,
                    "Status": "ok",
                    "Interval": args.interval,
                    "ReportPath": str(report_path),
                    "GridSpacingPct": best_summary["GridSpacingPct"],
                    "GridCount": best_summary["GridCount"],
                    "TakeProfitPct": best_summary["TakeProfitPct"],
                    "InSampleNetReturnPct": best_summary.get("NetReturnPct", best_summary["ReturnPct"]),
                    "ValidationNetReturnPct": validation_summary.get("NetReturnPct", validation_summary["ReturnPct"]),
                    "ValidationMaxDrawdownPct": validation_summary["MaxDrawdownPct"],
                    "ElapsedSeconds": perf_counter() - symbol_started_at,
                }
            )
            logger.info("[batch] 标的完成: symbol={} report={}", symbol, report_path)
        except Exception as exc:
            if args.download and not download_completed:
                logger.error("[batch] Yahoo 数据下载失败，批量流程停止: symbol={} error={}", symbol, exc)
                raise
            report_view = "compare" if args.compare_strategies else args.strategy
            failed_report_path = _write_failed_batch_report(symbol_report_dir, symbol, spec, args.interval, exc, report_view=report_view)
            rows.append(
                {
                    "Symbol": symbol,
                    "Name": spec.name,
                    "Category": spec.category,
                    "Status": "failed",
                    "Interval": args.interval,
                    "ReportPath": str(failed_report_path),
                    "Error": str(exc),
                    "ElapsedSeconds": perf_counter() - symbol_started_at,
                }
            )
            index_entries.append(
                _failed_report_index_entry(
                    report_path=failed_report_path,
                    symbol=symbol,
                    interval=args.interval,
                    report_view=report_view,
                    error=exc,
                    spec=spec,
                    report_root=report_root,
                )
            )
            logger.exception("[batch] 标的失败: symbol={}", symbol)

    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "batch_summary.csv"
    pd.DataFrame(rows).to_csv(summary_path, index=False, encoding="utf-8-sig")
    index_path = _refresh_unified_report_index(index_entries, report_root=report_root)
    ok_count = sum(1 for row in rows if row["Status"] == "ok")
    print(f"批量流程完成: 成功 {ok_count}/{len(rows)}，汇总文件: {summary_path}，报告索引: {index_path}")
    logger.info("batch 命令完成: summary={} index={} elapsed={:.2f}s", summary_path, index_path, perf_counter() - started_at)
    return 0 if ok_count == len(rows) else 1


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
        "batch": handle_batch,
    }
    try:
        return handlers[args.command](args)
    except Exception as exc:
        logger.error("命令执行失败: {}", exc)
        print(f"错误: {exc}")
        return 1
