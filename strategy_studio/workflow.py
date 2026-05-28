from __future__ import annotations
"""工作流编排层。

这里负责把“数据读取、样本切分、最小交易单位解析、参数搜索、验证、结果汇总”
组织成可直接被 CLI 调用的高层流程。

策略细节不放在这里实现，避免 CLI 和报告层直接依赖回测内部状态。
"""

from time import perf_counter

import pandas as pd
from loguru import logger

from strategy_studio.data.market_rules import LotSizeRule, resolve_lot_size_rule
from strategy_studio.settings import (
    DAILY_REBOUND_DEVIATIONS,
    DAILY_REBOUND_MA_WINDOWS,
    DAILY_REBOUND_MAX_HOLD_BARS,
    DAILY_REBOUND_RSI_ENTRIES,
    DAILY_REBOUND_RSI_WINDOWS,
    DAILY_REBOUND_STOP_LOSS_ATRS,
    DAILY_REBOUND_TAKE_PROFITS,
    DAILY_GRID_COUNTS,
    DAILY_SPACINGS,
    DAILY_TAKE_PROFITS,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_JOBS,
    DEFAULT_VALIDATION_RATIO,
    DEFAULT_VALIDATION_START,
    DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    INTRADAY_GRID_COUNTS,
    MINUTE_REBOUND_DROP_ENTRIES,
    MINUTE_REBOUND_FADE_BLOCK_BARS,
    MINUTE_REBOUND_FADE_UPPER_SHADOWS,
    MINUTE_REBOUND_LOOKBACK_BARS,
    MINUTE_REBOUND_MAX_HOLD_BARS,
    MINUTE_REBOUND_RSI_ENTRIES,
    MINUTE_REBOUND_STOP_LOSSES,
    MINUTE_REBOUND_TAKE_PROFITS,
    INTRADAY_SPACINGS,
    INTRADAY_TAKE_PROFITS,
    ExecutionConfig,
    StrategyKind,
    build_execution_config,
)
from strategy_studio.strategy.grid import optimize_grid_parameters
from strategy_studio.strategy.index_grid import run_index_grid_backtest
from strategy_studio.strategy.registry import (
    default_parameter_space_for_strategy,
    get_strategy_spec,
    validate_strategy_interval,
)
from strategy_studio.strategy.rebound import optimize_rebound_parameters, run_rebound_backtest
from strategy_studio.strategy.sampling import split_intraday_in_sample_and_validation, split_in_sample_and_validation


def _count_parameter_combinations(spacings: list[float], grid_counts: list[int], take_profits: list[float]) -> int:
    """统计当前穷举参数组合数，便于在控制台提示当前搜索规模。"""
    return len(spacings) * len(grid_counts) * len(take_profits)


def _rebound_parameter_space(strategy_kind: StrategyKind) -> dict[str, list[object]]:
    if strategy_kind == "daily_rebound":
        return {
            "rsi_window": list(DAILY_REBOUND_RSI_WINDOWS),
            "rsi_entry": list(DAILY_REBOUND_RSI_ENTRIES),
            "ma_window": list(DAILY_REBOUND_MA_WINDOWS),
            "deviation_entry_pct": list(DAILY_REBOUND_DEVIATIONS),
            "take_profit_pct": list(DAILY_REBOUND_TAKE_PROFITS),
            "stop_loss_atr": list(DAILY_REBOUND_STOP_LOSS_ATRS),
            "max_hold_bars": list(DAILY_REBOUND_MAX_HOLD_BARS),
        }
    parameter_space: dict[str, list[object]] = {
        "lookback_bars": list(MINUTE_REBOUND_LOOKBACK_BARS),
        "drop_entry_pct": list(MINUTE_REBOUND_DROP_ENTRIES),
        "rsi_entry": list(MINUTE_REBOUND_RSI_ENTRIES),
        "take_profit_pct": list(MINUTE_REBOUND_TAKE_PROFITS),
        "stop_loss_pct": list(MINUTE_REBOUND_STOP_LOSSES),
        "max_hold_bars": list(MINUTE_REBOUND_MAX_HOLD_BARS),
    }
    if strategy_kind == "minute_rebound_with_fade_filter":
        parameter_space["fade_filter_upper_shadow_pct"] = list(MINUTE_REBOUND_FADE_UPPER_SHADOWS)
        parameter_space["fade_filter_block_bars"] = list(MINUTE_REBOUND_FADE_BLOCK_BARS)
    return parameter_space


def _resolve_grid_parameter_space(
    interval: str,
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
    parameter_space: dict[str, object] | None = None,
) -> tuple[list[float], list[int], list[float]]:
    if parameter_space:
        return (
            [float(item) for item in parameter_space.get("spacings", [])],
            [int(item) for item in parameter_space.get("grid_counts", [])],
            [float(item) for item in parameter_space.get("take_profits", [])],
        )
    if interval == "1d":
        return (
            spacings or list(DAILY_SPACINGS),
            grid_counts or list(DAILY_GRID_COUNTS),
            take_profits or list(DAILY_TAKE_PROFITS),
        )
    return (
        spacings or list(INTRADAY_SPACINGS),
        grid_counts or list(INTRADAY_GRID_COUNTS),
        take_profits or list(INTRADAY_TAKE_PROFITS),
    )


def _resolve_rebound_parameter_space(
    strategy_kind: StrategyKind,
    parameter_space: dict[str, object] | None = None,
) -> dict[str, list[object]]:
    if not parameter_space:
        return _rebound_parameter_space(strategy_kind)
    return {key: list(value) for key, value in parameter_space.items()}


def _count_parameter_space_candidates(parameter_space: dict[str, list[object]]) -> int:
    total = 1
    for values in parameter_space.values():
        total *= max(1, len(values))
    return total


def _extract_rebound_params(summary: dict[str, object], strategy_kind: StrategyKind) -> dict[str, object]:
    if strategy_kind == "daily_rebound":
        keys = [
            "rsi_window",
            "rsi_entry",
            "ma_window",
            "deviation_entry_pct",
            "take_profit_pct",
            "stop_loss_atr",
            "max_hold_bars",
        ]
    else:
        keys = [
            "lookback_bars",
            "drop_entry_pct",
            "rsi_entry",
            "take_profit_pct",
            "stop_loss_pct",
            "max_hold_bars",
        ]
        if strategy_kind == "minute_rebound_with_fade_filter":
            keys.extend(["fade_filter_upper_shadow_pct", "fade_filter_block_bars"])
    return {key: summary[key] for key in keys if key in summary}


def _resolve_strategy_parameter_space(
    strategy_kind: str,
    interval: str,
    parameter_space: dict[str, object] | None = None,
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
) -> dict[str, list[object]]:
    """统一解析策略参数空间。

    旧 CLI 仍保留 `spacings/grid_counts/take_profits` 三个显式参数，因此这里
    对网格做一次兼容合并；其他策略统一使用注册表默认值或模板传入值。
    """
    if parameter_space is not None:
        return {key: list(value) for key, value in parameter_space.items()}
    if strategy_kind == "grid" and any(item is not None for item in (spacings, grid_counts, take_profits)):
        default_space = default_parameter_space_for_strategy(strategy_kind, interval)
        return {
            "spacings": list(spacings or default_space["spacings"]),
            "grid_counts": list(grid_counts or default_space["grid_counts"]),
            "take_profits": list(take_profits or default_space["take_profits"]),
        }
    return {key: list(value) for key, value in default_parameter_space_for_strategy(strategy_kind, interval).items()}


def _require_price_frame(data: pd.DataFrame | None, data_path: str | None = None) -> pd.DataFrame:
    """数据库优先模式下要求调用方直接提供内存行情。"""
    if data is None:
        source_hint = data_path or "未提供 data_path"
        raise ValueError(
            "当前仓库已切换到数据库优先模式，不再支持从本地 CSV 读取正式行情；"
            f"请直接传入数据库中加载好的 DataFrame。source={source_hint}"
        )
    return data


def run_optimization_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    validation_start: str = DEFAULT_VALIDATION_START,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    strategy_kind: StrategyKind = "grid",
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
    execution_config: ExecutionConfig | None = None,
    wf_window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    wf_min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    jobs: int = DEFAULT_JOBS,
    parameter_space: dict[str, object] | None = None,
    data: pd.DataFrame | None = None,
    lot_rule: LotSizeRule | None = None,
) -> dict[str, object]:
    """执行样本内参数搜索并返回结构化结果。"""
    started_at = perf_counter()
    validate_strategy_interval(strategy_kind, "1d")
    spec = get_strategy_spec(strategy_kind)
    execution = execution_config or build_execution_config("research")
    resolved_symbol = _resolve_symbol(symbol, data_path)
    effective_lot_rule = lot_rule or resolve_lot_size_rule(resolved_symbol)
    price_frame = _require_price_frame(data, str(data_path))
    decline_window, in_sample, _ = split_in_sample_and_validation(
        data=price_frame,
        validation_start=validation_start,
        lookback_days=lookback_days,
    )
    resolved_parameter_space = _resolve_strategy_parameter_space(
        strategy_kind=strategy_kind,
        interval="1d",
        parameter_space=parameter_space,
        spacings=spacings,
        grid_counts=grid_counts,
        take_profits=take_profits,
    )
    logger.info(
        "[1/2] 开始执行日线样本内寻参: strategy={} symbol={} data={} rows={} combinations={}",
        strategy_kind,
        effective_lot_rule.symbol,
        data_path,
        len(price_frame),
        _count_parameter_space_candidates(resolved_parameter_space),
    )
    results, best_run = spec.optimize(
        data=in_sample,
        parameter_space=resolved_parameter_space,
        scenario_name="in_sample",
        symbol=effective_lot_rule.symbol,
        market=effective_lot_rule.market,
        lot_size=effective_lot_rule.lot_size,
        lot_size_source=effective_lot_rule.source,
        execution_config=execution,
        wf_window_count=wf_window_count,
        wf_min_window_size=wf_min_window_size,
        jobs=jobs,
    )
    logger.info(
        "[1/2] 日线样本内寻参完成: strategy={} score={:.2f} elapsed={:.2f}s",
        strategy_kind,
        float(best_run["summary"]["Score"]),
        perf_counter() - started_at,
    )

    return {
        "strategy_kind": strategy_kind,
        "decline_window": decline_window,
        "results": results,
        "results_path": None,
        "window_path": None,
        "best_run": best_run,
        "best_paths": {},
    }


def run_validation_workflow(
    data_path: str | Path,
    grid_spacing_pct: float,
    grid_count: int,
    take_profit_pct: float,
    symbol: str | None = None,
    validation_start: str = DEFAULT_VALIDATION_START,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    strategy_kind: StrategyKind = "grid",
    strategy_params: dict[str, object] | None = None,
    execution_config: ExecutionConfig | None = None,
    data: pd.DataFrame | None = None,
    lot_rule: LotSizeRule | None = None,
) -> dict[str, object]:
    """执行 2026 样本外验证。"""
    validate_strategy_interval(strategy_kind, "1d")
    spec = get_strategy_spec(strategy_kind)
    started_at = perf_counter()
    resolved_symbol = _resolve_symbol(symbol, data_path)
    effective_lot_rule = lot_rule or resolve_lot_size_rule(resolved_symbol)
    execution = execution_config or build_execution_config("research")
    price_frame = _require_price_frame(data, str(data_path))
    logger.info(
        "[2/2] 开始执行日线样本外验证: symbol={} data={} spacing={:.2f}% grid_count={} take_profit={:.2f}%",
        effective_lot_rule.symbol,
        data_path,
        grid_spacing_pct * 100,
        grid_count,
        take_profit_pct * 100,
    )
    _, _, validation = split_in_sample_and_validation(
        data=price_frame,
        validation_start=validation_start,
        lookback_days=lookback_days,
    )
    if strategy_params is None:
        if strategy_kind != "grid":
            raise ValueError(f"{strategy_kind} 策略验证缺少 strategy_params。")
        strategy_params = {
            "grid_spacing_pct": grid_spacing_pct,
            "grid_count": grid_count,
            "take_profit_pct": take_profit_pct,
        }
    validation_run = spec.run_once(
        data=validation,
        scenario_name="validation_2026",
        symbol=effective_lot_rule.symbol,
        market=effective_lot_rule.market,
        lot_size=effective_lot_rule.lot_size,
        lot_size_source=effective_lot_rule.source,
        params=strategy_params,
        execution_config=execution,
    )
    logger.info(
        "[2/2] 日线样本外验证完成: return={:.2f}% max_drawdown={:.2f}% elapsed={:.2f}s",
        float(validation_run["summary"]["ReturnPct"]),
        float(validation_run["summary"]["MaxDrawdownPct"]),
        perf_counter() - started_at,
    )
    return {"strategy_kind": strategy_kind, "run": validation_run, "paths": {}}


def run_full_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    validation_start: str = DEFAULT_VALIDATION_START,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    strategy_kind: StrategyKind = "grid",
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
    execution_config: ExecutionConfig | None = None,
    wf_window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    wf_min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    jobs: int = DEFAULT_JOBS,
    parameter_space: dict[str, object] | None = None,
    data: pd.DataFrame | None = None,
    lot_rule: LotSizeRule | None = None,
) -> dict[str, object]:
    """串联样本内寻参和样本外验证。

    这里复用样本内最优参数直接做样本外，不在验证阶段再次寻参，
    目的是让报告清楚区分“历史上调出来的参数”和“新样本上的延续性”。
    """
    started_at = perf_counter()
    logger.info("开始执行日线完整工作流: data={}", data_path)
    resolved_symbol = _resolve_symbol(symbol, data_path)
    effective_lot_rule = lot_rule or resolve_lot_size_rule(resolved_symbol)
    price_frame = _require_price_frame(data, str(data_path))
    optimization = run_optimization_workflow(
        data_path=data_path,
        symbol=resolved_symbol,
        validation_start=validation_start,
        lookback_days=lookback_days,
        strategy_kind=strategy_kind,
        spacings=spacings,
        grid_counts=grid_counts,
        take_profits=take_profits,
        execution_config=execution_config,
        wf_window_count=wf_window_count,
        wf_min_window_size=wf_min_window_size,
        jobs=jobs,
        parameter_space=parameter_space,
        data=price_frame,
        lot_rule=effective_lot_rule,
    )
    best_summary = optimization["best_run"]["summary"]
    spec = get_strategy_spec(strategy_kind)
    validation = run_validation_workflow(
        data_path=data_path,
        grid_spacing_pct=float(best_summary["GridSpacingPct"]) / 100,
        grid_count=int(best_summary["GridCount"]),
        take_profit_pct=float(best_summary["TakeProfitPct"]) / 100,
        symbol=resolved_symbol,
        validation_start=validation_start,
        lookback_days=lookback_days,
        strategy_kind=strategy_kind,
        strategy_params=spec.extract_params(best_summary),
        execution_config=execution_config,
        data=price_frame,
        lot_rule=effective_lot_rule,
    )

    combined_summary = pd.DataFrame(
        [
            optimization["best_run"]["summary"],
            validation["run"]["summary"],
        ]
    )
    logger.info("日线完整工作流完成: rows={} elapsed={:.2f}s", len(combined_summary), perf_counter() - started_at)

    return {
        "strategy_kind": strategy_kind,
        "optimization": optimization,
        "validation": validation,
        "combined_summary_path": None,
    }


def run_minute_optimization_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    interval: str = "15m",
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
    strategy_kind: StrategyKind = "grid",
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
    execution_config: ExecutionConfig | None = None,
    wf_window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    wf_min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    jobs: int = DEFAULT_JOBS,
    parameter_space: dict[str, object] | None = None,
    data: pd.DataFrame | None = None,
    lot_rule: LotSizeRule | None = None,
) -> dict[str, object]:
    """执行分钟线样本内参数搜索并返回结构化结果。"""
    started_at = perf_counter()
    validate_strategy_interval(strategy_kind, interval)
    spec = get_strategy_spec(strategy_kind)
    execution = execution_config or build_execution_config("research")

    resolved_symbol = _resolve_symbol(symbol, data_path)
    effective_lot_rule = lot_rule or resolve_lot_size_rule(resolved_symbol)
    price_frame = _require_price_frame(data, str(data_path))
    decline_window, in_sample, _ = split_intraday_in_sample_and_validation(
        data=price_frame,
        validation_ratio=validation_ratio,
    )
    resolved_parameter_space = _resolve_strategy_parameter_space(
        strategy_kind=strategy_kind,
        interval=interval,
        parameter_space=parameter_space,
        spacings=spacings,
        grid_counts=grid_counts,
        take_profits=take_profits,
    )
    logger.info(
        "[1/2] 开始执行分钟线样本内寻参: strategy={} symbol={} data={} rows={} combinations={}",
        strategy_kind,
        effective_lot_rule.symbol,
        data_path,
        len(price_frame),
        _count_parameter_space_candidates(resolved_parameter_space),
    )
    results, best_run = spec.optimize(
        data=in_sample,
        parameter_space=resolved_parameter_space,
        scenario_name="minute_in_sample",
        symbol=effective_lot_rule.symbol,
        market=effective_lot_rule.market,
        lot_size=effective_lot_rule.lot_size,
        lot_size_source=effective_lot_rule.source,
        execution_config=execution,
        wf_window_count=wf_window_count,
        wf_min_window_size=wf_min_window_size,
        jobs=jobs,
    )
    logger.info(
        "[1/2] 分钟线样本内寻参完成: strategy={} score={:.2f} elapsed={:.2f}s",
        strategy_kind,
        float(best_run["summary"]["Score"]),
        perf_counter() - started_at,
    )

    return {
        "strategy_kind": strategy_kind,
        "decline_window": decline_window,
        "results": results,
        "results_path": None,
        "window_path": None,
        "best_run": best_run,
        "best_paths": {},
    }


def run_minute_validation_workflow(
    data_path: str | Path,
    grid_spacing_pct: float,
    grid_count: int,
    take_profit_pct: float,
    symbol: str | None = None,
    interval: str = "15m",
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
    strategy_kind: StrategyKind = "grid",
    strategy_params: dict[str, object] | None = None,
    execution_config: ExecutionConfig | None = None,
    data: pd.DataFrame | None = None,
    lot_rule: LotSizeRule | None = None,
) -> dict[str, object]:
    """执行分钟线样本外验证。"""
    started_at = perf_counter()
    validate_strategy_interval(strategy_kind, interval)
    spec = get_strategy_spec(strategy_kind)
    resolved_symbol = _resolve_symbol(symbol, data_path)
    effective_lot_rule = lot_rule or resolve_lot_size_rule(resolved_symbol)
    execution = execution_config or build_execution_config("research")
    price_frame = _require_price_frame(data, str(data_path))
    _, _, validation = split_intraday_in_sample_and_validation(
        data=price_frame,
        validation_ratio=validation_ratio,
    )
    if strategy_params is None:
        if strategy_kind != "grid":
            raise ValueError(f"{strategy_kind} 分钟线验证缺少 strategy_params。")
        strategy_params = {
            "grid_spacing_pct": grid_spacing_pct,
            "grid_count": grid_count,
            "take_profit_pct": take_profit_pct,
        }
    validation_run = spec.run_once(
        data=validation,
        scenario_name="minute_validation",
        symbol=effective_lot_rule.symbol,
        market=effective_lot_rule.market,
        lot_size=effective_lot_rule.lot_size,
        lot_size_source=effective_lot_rule.source,
        params=strategy_params,
        execution_config=execution,
    )
    logger.info(
        "[2/2] 分钟线样本外验证完成: return={:.2f}% max_drawdown={:.2f}% elapsed={:.2f}s",
        float(validation_run["summary"]["ReturnPct"]),
        float(validation_run["summary"]["MaxDrawdownPct"]),
        perf_counter() - started_at,
    )
    return {"strategy_kind": strategy_kind, "run": validation_run, "paths": {}}


def run_minute_full_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    interval: str = "15m",
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
    strategy_kind: StrategyKind = "grid",
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
    execution_config: ExecutionConfig | None = None,
    wf_window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    wf_min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    jobs: int = DEFAULT_JOBS,
    parameter_space: dict[str, object] | None = None,
    data: pd.DataFrame | None = None,
    lot_rule: LotSizeRule | None = None,
) -> dict[str, object]:
    """串联分钟线样本内寻参和样本外验证。"""
    started_at = perf_counter()
    logger.info("开始执行分钟线完整工作流: data={}", data_path)
    resolved_symbol = _resolve_symbol(symbol, data_path)
    effective_lot_rule = lot_rule or resolve_lot_size_rule(resolved_symbol)
    price_frame = _require_price_frame(data, str(data_path))
    optimization = run_minute_optimization_workflow(
        data_path=data_path,
        symbol=resolved_symbol,
        interval=interval,
        validation_ratio=validation_ratio,
        strategy_kind=strategy_kind,
        spacings=spacings,
        grid_counts=grid_counts,
        take_profits=take_profits,
        execution_config=execution_config,
        wf_window_count=wf_window_count,
        wf_min_window_size=wf_min_window_size,
        jobs=jobs,
        parameter_space=parameter_space,
        data=price_frame,
        lot_rule=effective_lot_rule,
    )
    best_summary = optimization["best_run"]["summary"]
    spec = get_strategy_spec(strategy_kind)
    validation = run_minute_validation_workflow(
        data_path=data_path,
        grid_spacing_pct=float(best_summary["GridSpacingPct"]) / 100,
        grid_count=int(best_summary["GridCount"]),
        take_profit_pct=float(best_summary["TakeProfitPct"]) / 100,
        symbol=resolved_symbol,
        interval=interval,
        validation_ratio=validation_ratio,
        strategy_kind=strategy_kind,
        strategy_params=spec.extract_params(best_summary),
        execution_config=execution_config,
        data=price_frame,
        lot_rule=effective_lot_rule,
    )

    combined_summary = pd.DataFrame(
        [
            optimization["best_run"]["summary"],
            validation["run"]["summary"],
        ]
    )
    logger.info("分钟线完整工作流完成: rows={} elapsed={:.2f}s", len(combined_summary), perf_counter() - started_at)

    return {
        "workflow_type": "minute",
        "interval": interval,
        "strategy_kind": strategy_kind,
        "validation_ratio": validation_ratio,
        "optimization": optimization,
        "validation": validation,
        "combined_summary_path": None,
    }


def _resolve_symbol(symbol: str | None, data_path: str | Path) -> str:
    """统一处理显式 symbol。"""
    if symbol:
        return symbol.strip().upper()
    raise ValueError(f"当前数据库优先工作流要求显式传入 symbol。source={data_path}")
