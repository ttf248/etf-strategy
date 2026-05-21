from __future__ import annotations
"""工作流编排层。

这里负责把“数据加载、样本切分、最小交易单位解析、参数搜索、验证、产物落盘”
组织成可直接被 CLI 调用的高层流程。

策略细节不放在这里实现，避免 CLI 和报告层直接依赖回测内部状态。
"""

from pathlib import Path
from time import perf_counter

import pandas as pd
from loguru import logger

from etf_strategy.config import DEFAULT_OUTPUT_DIR
from etf_strategy.data.market_rules import infer_symbol_from_data_path, resolve_lot_size_rule
from etf_strategy.settings import (
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
from etf_strategy.strategy.artifacts import load_price_frame, save_decline_window, save_run_artifacts
from etf_strategy.strategy.grid import optimize_grid_parameters
from etf_strategy.strategy.rebound import optimize_rebound_parameters, run_rebound_backtest
from etf_strategy.strategy.sampling import split_intraday_in_sample_and_validation, split_in_sample_and_validation


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


def run_optimization_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "optimize",
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
    cache_dir: str | Path | None = None,
) -> dict[str, object]:
    """执行样本内参数搜索并保存结果。"""
    started_at = perf_counter()
    execution = execution_config or build_execution_config("research")
    resolved_symbol = _resolve_symbol(symbol, data_path)
    lot_rule = resolve_lot_size_rule(resolved_symbol)
    data = load_price_frame(data_path)
    decline_window, in_sample, _ = split_in_sample_and_validation(
        data=data,
        validation_start=validation_start,
        lookback_days=lookback_days,
    )
    if strategy_kind == "grid":
        spacings = spacings or list(DAILY_SPACINGS)
        grid_counts = grid_counts or list(DAILY_GRID_COUNTS)
        take_profits = take_profits or list(DAILY_TAKE_PROFITS)
        logger.info(
            "[1/2] 开始执行日线样本内寻参: strategy={} symbol={} data={} rows={} combinations={}",
            strategy_kind,
            lot_rule.symbol,
            data_path,
            len(data),
            _count_parameter_combinations(spacings, grid_counts, take_profits),
        )
        results, best_run = optimize_grid_parameters(
            data=in_sample,
            spacings=spacings,
            grid_counts=grid_counts,
            take_profits=take_profits,
            scenario_name="in_sample",
            symbol=lot_rule.symbol,
            market=lot_rule.market,
            lot_size=lot_rule.lot_size,
            lot_size_source=lot_rule.source,
            execution_config=execution,
            wf_window_count=wf_window_count,
            wf_min_window_size=wf_min_window_size,
            jobs=jobs,
            cache_dir=cache_dir,
        )
    else:
        parameter_space = _rebound_parameter_space(strategy_kind)
        logger.info(
            "[1/2] 开始执行日线样本内寻参: strategy={} symbol={} data={} rows={} combinations={}",
            strategy_kind,
            lot_rule.symbol,
            data_path,
            len(data),
            _count_parameter_space_candidates(parameter_space),
        )
        results, best_run = optimize_rebound_parameters(
            data=in_sample,
            strategy_kind=strategy_kind,
            parameter_space=parameter_space,
            scenario_name="in_sample",
            symbol=lot_rule.symbol,
            market=lot_rule.market,
            lot_size=lot_rule.lot_size,
            lot_size_source=lot_rule.source,
            execution_config=execution,
            wf_window_count=wf_window_count,
            wf_min_window_size=wf_min_window_size,
            jobs=jobs,
            cache_dir=cache_dir,
        )

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    prefix = "in_sample_grid" if strategy_kind == "grid" else f"in_sample_{strategy_kind}"
    results_path = target_dir / f"{prefix}_search.csv"
    results.to_csv(results_path, index=False, encoding="utf-8-sig")
    window_path = save_decline_window(target_dir, decline_window)
    best_paths = save_run_artifacts(target_dir, f"{prefix}_best", best_run)
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
        "results_path": results_path,
        "window_path": window_path,
        "best_run": best_run,
        "best_paths": best_paths,
    }


def run_validation_workflow(
    data_path: str | Path,
    grid_spacing_pct: float,
    grid_count: int,
    take_profit_pct: float,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "validation",
    validation_start: str = DEFAULT_VALIDATION_START,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    strategy_kind: StrategyKind = "grid",
    strategy_params: dict[str, object] | None = None,
    execution_config: ExecutionConfig | None = None,
) -> dict[str, object]:
    """执行 2026 样本外验证。"""
    from etf_strategy.strategy.grid import run_grid_backtest

    started_at = perf_counter()
    resolved_symbol = _resolve_symbol(symbol, data_path)
    lot_rule = resolve_lot_size_rule(resolved_symbol)
    execution = execution_config or build_execution_config("research")
    data = load_price_frame(data_path)
    logger.info(
        "[2/2] 开始执行日线样本外验证: symbol={} data={} spacing={:.2f}% grid_count={} take_profit={:.2f}%",
        lot_rule.symbol,
        data_path,
        grid_spacing_pct * 100,
        grid_count,
        take_profit_pct * 100,
    )
    _, _, validation = split_in_sample_and_validation(
        data=data,
        validation_start=validation_start,
        lookback_days=lookback_days,
    )
    if strategy_kind == "grid":
        validation_run = run_grid_backtest(
            data=validation,
            scenario_name="validation_2026",
            grid_spacing_pct=grid_spacing_pct,
            grid_count=grid_count,
            take_profit_pct=take_profit_pct,
            symbol=lot_rule.symbol,
            market=lot_rule.market,
            lot_size=lot_rule.lot_size,
            lot_size_source=lot_rule.source,
            execution_config=execution,
        )
        prefix = "validation_2026"
    else:
        if strategy_params is None:
            raise ValueError("非网格策略验证缺少 strategy_params。")
        validation_run = run_rebound_backtest(
            data=validation,
            scenario_name="validation_2026",
            strategy_kind=strategy_kind,
            symbol=lot_rule.symbol,
            market=lot_rule.market,
            lot_size=lot_rule.lot_size,
            lot_size_source=lot_rule.source,
            params=strategy_params,
            execution_config=execution,
        )
        prefix = f"validation_{strategy_kind}"
    paths = save_run_artifacts(output_dir, prefix, validation_run)
    logger.info(
        "[2/2] 日线样本外验证完成: return={:.2f}% max_drawdown={:.2f}% elapsed={:.2f}s",
        float(validation_run["summary"]["ReturnPct"]),
        float(validation_run["summary"]["MaxDrawdownPct"]),
        perf_counter() - started_at,
    )
    return {"strategy_kind": strategy_kind, "run": validation_run, "paths": paths}


def run_full_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
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
    cache_dir: str | Path | None = None,
) -> dict[str, object]:
    """串联样本内寻参和样本外验证。

    这里复用样本内最优参数直接做样本外，不在验证阶段再次寻参，
    目的是让报告清楚区分“历史上调出来的参数”和“新样本上的延续性”。
    """
    started_at = perf_counter()
    logger.info("开始执行日线完整工作流: data={} output_dir={}", data_path, output_dir)
    optimization = run_optimization_workflow(
        data_path=data_path,
        symbol=symbol,
        output_dir=Path(output_dir) / "optimize",
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
        cache_dir=cache_dir,
    )
    best_summary = optimization["best_run"]["summary"]
    validation = run_validation_workflow(
        data_path=data_path,
        grid_spacing_pct=float(best_summary["GridSpacingPct"]) / 100,
        grid_count=int(best_summary["GridCount"]),
        take_profit_pct=float(best_summary["TakeProfitPct"]) / 100,
        symbol=symbol,
        output_dir=Path(output_dir) / "validation",
        validation_start=validation_start,
        lookback_days=lookback_days,
        strategy_kind=strategy_kind,
        strategy_params=None if strategy_kind == "grid" else _extract_rebound_params(best_summary, strategy_kind),
        execution_config=execution_config,
    )

    combined_summary = pd.DataFrame(
        [
            optimization["best_run"]["summary"],
            validation["run"]["summary"],
        ]
    )
    combined_path = Path(output_dir) / "combined_summary.csv"
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    combined_summary.to_csv(combined_path, index=False, encoding="utf-8-sig")
    logger.info("日线完整工作流完成: summary={} elapsed={:.2f}s", combined_path, perf_counter() - started_at)

    return {
        "strategy_kind": strategy_kind,
        "optimization": optimization,
        "validation": validation,
        "combined_summary_path": combined_path,
    }


def run_minute_optimization_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "minute" / "optimize",
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
    strategy_kind: StrategyKind = "grid",
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
    execution_config: ExecutionConfig | None = None,
    wf_window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    wf_min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    jobs: int = DEFAULT_JOBS,
    cache_dir: str | Path | None = None,
) -> dict[str, object]:
    """执行分钟线样本内参数搜索并保存结果。"""
    started_at = perf_counter()
    execution = execution_config or build_execution_config("research")

    resolved_symbol = _resolve_symbol(symbol, data_path)
    lot_rule = resolve_lot_size_rule(resolved_symbol)
    data = load_price_frame(data_path)
    decline_window, in_sample, _ = split_intraday_in_sample_and_validation(
        data=data,
        validation_ratio=validation_ratio,
    )
    if strategy_kind == "grid":
        spacings = spacings or list(INTRADAY_SPACINGS)
        grid_counts = grid_counts or list(INTRADAY_GRID_COUNTS)
        take_profits = take_profits or list(INTRADAY_TAKE_PROFITS)
        logger.info(
            "[1/2] 开始执行分钟线样本内寻参: strategy={} symbol={} data={} rows={} combinations={}",
            strategy_kind,
            lot_rule.symbol,
            data_path,
            len(data),
            _count_parameter_combinations(spacings, grid_counts, take_profits),
        )
        results, best_run = optimize_grid_parameters(
            data=in_sample,
            spacings=spacings,
            grid_counts=grid_counts,
            take_profits=take_profits,
            scenario_name="minute_in_sample",
            symbol=lot_rule.symbol,
            market=lot_rule.market,
            lot_size=lot_rule.lot_size,
            lot_size_source=lot_rule.source,
            execution_config=execution,
            wf_window_count=wf_window_count,
            wf_min_window_size=wf_min_window_size,
            jobs=jobs,
            cache_dir=cache_dir,
        )
    else:
        parameter_space = _rebound_parameter_space(strategy_kind)
        logger.info(
            "[1/2] 开始执行分钟线样本内寻参: strategy={} symbol={} data={} rows={} combinations={}",
            strategy_kind,
            lot_rule.symbol,
            data_path,
            len(data),
            _count_parameter_space_candidates(parameter_space),
        )
        results, best_run = optimize_rebound_parameters(
            data=in_sample,
            strategy_kind=strategy_kind,
            parameter_space=parameter_space,
            scenario_name="minute_in_sample",
            symbol=lot_rule.symbol,
            market=lot_rule.market,
            lot_size=lot_rule.lot_size,
            lot_size_source=lot_rule.source,
            execution_config=execution,
            wf_window_count=wf_window_count,
            wf_min_window_size=wf_min_window_size,
            jobs=jobs,
            cache_dir=cache_dir,
        )

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    prefix = "minute_in_sample_grid" if strategy_kind == "grid" else f"minute_in_sample_{strategy_kind}"
    results_path = target_dir / f"{prefix}_search.csv"
    results.to_csv(results_path, index=False, encoding="utf-8-sig")
    window_path = save_decline_window(target_dir, decline_window)
    best_paths = save_run_artifacts(target_dir, f"{prefix}_best", best_run)
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
        "results_path": results_path,
        "window_path": window_path,
        "best_run": best_run,
        "best_paths": best_paths,
    }


def run_minute_validation_workflow(
    data_path: str | Path,
    grid_spacing_pct: float,
    grid_count: int,
    take_profit_pct: float,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "minute" / "validation",
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
    strategy_kind: StrategyKind = "grid",
    strategy_params: dict[str, object] | None = None,
    execution_config: ExecutionConfig | None = None,
) -> dict[str, object]:
    """执行分钟线样本外验证。"""
    from etf_strategy.strategy.grid import run_grid_backtest

    started_at = perf_counter()
    resolved_symbol = _resolve_symbol(symbol, data_path)
    lot_rule = resolve_lot_size_rule(resolved_symbol)
    execution = execution_config or build_execution_config("research")
    data = load_price_frame(data_path)
    logger.info(
        "[2/2] 开始执行分钟线样本外验证: symbol={} data={} spacing={:.2f}% grid_count={} take_profit={:.2f}%",
        lot_rule.symbol,
        data_path,
        grid_spacing_pct * 100,
        grid_count,
        take_profit_pct * 100,
    )
    _, _, validation = split_intraday_in_sample_and_validation(
        data=data,
        validation_ratio=validation_ratio,
    )
    if strategy_kind == "grid":
        validation_run = run_grid_backtest(
            data=validation,
            scenario_name="minute_validation",
            grid_spacing_pct=grid_spacing_pct,
            grid_count=grid_count,
            take_profit_pct=take_profit_pct,
            symbol=lot_rule.symbol,
            market=lot_rule.market,
            lot_size=lot_rule.lot_size,
            lot_size_source=lot_rule.source,
            execution_config=execution,
        )
        prefix = "minute_validation"
    else:
        if strategy_params is None:
            raise ValueError("非网格分钟线验证缺少 strategy_params。")
        validation_run = run_rebound_backtest(
            data=validation,
            scenario_name="minute_validation",
            strategy_kind=strategy_kind,
            symbol=lot_rule.symbol,
            market=lot_rule.market,
            lot_size=lot_rule.lot_size,
            lot_size_source=lot_rule.source,
            params=strategy_params,
            execution_config=execution,
        )
        prefix = f"minute_validation_{strategy_kind}"
    paths = save_run_artifacts(output_dir, prefix, validation_run)
    logger.info(
        "[2/2] 分钟线样本外验证完成: return={:.2f}% max_drawdown={:.2f}% elapsed={:.2f}s",
        float(validation_run["summary"]["ReturnPct"]),
        float(validation_run["summary"]["MaxDrawdownPct"]),
        perf_counter() - started_at,
    )
    return {"strategy_kind": strategy_kind, "run": validation_run, "paths": paths}


def run_minute_full_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "minute",
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
    strategy_kind: StrategyKind = "grid",
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
    execution_config: ExecutionConfig | None = None,
    wf_window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    wf_min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    jobs: int = DEFAULT_JOBS,
    cache_dir: str | Path | None = None,
) -> dict[str, object]:
    """串联分钟线样本内寻参和样本外验证。"""
    started_at = perf_counter()
    logger.info("开始执行分钟线完整工作流: data={} output_dir={}", data_path, output_dir)
    optimization = run_minute_optimization_workflow(
        data_path=data_path,
        symbol=symbol,
        output_dir=Path(output_dir) / "optimize",
        validation_ratio=validation_ratio,
        strategy_kind=strategy_kind,
        spacings=spacings,
        grid_counts=grid_counts,
        take_profits=take_profits,
        execution_config=execution_config,
        wf_window_count=wf_window_count,
        wf_min_window_size=wf_min_window_size,
        jobs=jobs,
        cache_dir=cache_dir,
    )
    best_summary = optimization["best_run"]["summary"]
    validation = run_minute_validation_workflow(
        data_path=data_path,
        grid_spacing_pct=float(best_summary["GridSpacingPct"]) / 100,
        grid_count=int(best_summary["GridCount"]),
        take_profit_pct=float(best_summary["TakeProfitPct"]) / 100,
        symbol=symbol,
        output_dir=Path(output_dir) / "validation",
        validation_ratio=validation_ratio,
        strategy_kind=strategy_kind,
        strategy_params=None if strategy_kind == "grid" else _extract_rebound_params(best_summary, strategy_kind),
        execution_config=execution_config,
    )

    combined_summary = pd.DataFrame(
        [
            optimization["best_run"]["summary"],
            validation["run"]["summary"],
        ]
    )
    combined_path = Path(output_dir) / "combined_summary.csv"
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    combined_summary.to_csv(combined_path, index=False, encoding="utf-8-sig")
    logger.info("分钟线完整工作流完成: summary={} elapsed={:.2f}s", combined_path, perf_counter() - started_at)

    return {
        "workflow_type": "minute",
        "interval": "15m",
        "strategy_kind": strategy_kind,
        "validation_ratio": validation_ratio,
        "optimization": optimization,
        "validation": validation,
        "combined_summary_path": combined_path,
    }


def _resolve_symbol(symbol: str | None, data_path: str | Path) -> str:
    """统一处理显式 symbol 与文件名推断。

    对非标准文件名直接报错，而不是静默猜测，
    是为了避免把错误标的代码带进最小交易单位查询和最终报告。
    """
    if symbol:
        return symbol.strip().upper()

    inferred_symbol = infer_symbol_from_data_path(data_path)
    if inferred_symbol:
        return inferred_symbol

    raise ValueError("无法从数据文件名推断标的代码，请显式传入 --symbol。")
