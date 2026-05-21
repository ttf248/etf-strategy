from __future__ import annotations

from pathlib import Path

import pandas as pd

from etf_strategy.config import DEFAULT_OUTPUT_DIR
from etf_strategy.data.market_rules import infer_symbol_from_data_path, resolve_lot_size_rule
from etf_strategy.strategy.grid import (
    load_price_frame,
    optimize_grid_parameters,
    save_decline_window,
    save_run_artifacts,
    split_intraday_in_sample_and_validation,
    split_in_sample_and_validation,
)


def run_optimization_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "optimize",
    validation_start: str = "2026-01-01",
    lookback_days: int = 120,
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
) -> dict[str, object]:
    """执行样本内参数搜索并保存结果。"""
    spacings = spacings or [0.03, 0.04, 0.05, 0.06, 0.07]
    grid_counts = grid_counts or [4, 5, 6, 7]
    take_profits = take_profits or [0.03, 0.05, 0.07]

    resolved_symbol = _resolve_symbol(symbol, data_path)
    lot_rule = resolve_lot_size_rule(resolved_symbol)
    data = load_price_frame(data_path)
    decline_window, in_sample, _ = split_in_sample_and_validation(
        data=data,
        validation_start=validation_start,
        lookback_days=lookback_days,
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
    )

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    results_path = target_dir / "in_sample_grid_search.csv"
    results.to_csv(results_path, index=False, encoding="utf-8-sig")
    window_path = save_decline_window(target_dir, decline_window)
    best_paths = save_run_artifacts(target_dir, "in_sample_best", best_run)

    return {
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
    validation_start: str = "2026-01-01",
    lookback_days: int = 120,
) -> dict[str, object]:
    """执行 2026 样本外验证。"""
    from etf_strategy.strategy.grid import run_grid_backtest

    resolved_symbol = _resolve_symbol(symbol, data_path)
    lot_rule = resolve_lot_size_rule(resolved_symbol)
    data = load_price_frame(data_path)
    _, _, validation = split_in_sample_and_validation(
        data=data,
        validation_start=validation_start,
        lookback_days=lookback_days,
    )
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
    )
    paths = save_run_artifacts(output_dir, "validation_2026", validation_run)
    return {"run": validation_run, "paths": paths}


def run_full_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    validation_start: str = "2026-01-01",
    lookback_days: int = 120,
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
) -> dict[str, object]:
    """串联样本内寻参和样本外验证。"""
    optimization = run_optimization_workflow(
        data_path=data_path,
        symbol=symbol,
        output_dir=Path(output_dir) / "optimize",
        validation_start=validation_start,
        lookback_days=lookback_days,
        spacings=spacings,
        grid_counts=grid_counts,
        take_profits=take_profits,
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

    return {
        "optimization": optimization,
        "validation": validation,
        "combined_summary_path": combined_path,
    }


def run_minute_optimization_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "minute" / "optimize",
    validation_ratio: float = 0.25,
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
) -> dict[str, object]:
    """执行分钟线样本内参数搜索并保存结果。"""
    spacings = spacings or [0.01, 0.015, 0.02, 0.03, 0.04]
    grid_counts = grid_counts or [4, 5, 6, 7]
    take_profits = take_profits or [0.01, 0.015, 0.02, 0.03]

    resolved_symbol = _resolve_symbol(symbol, data_path)
    lot_rule = resolve_lot_size_rule(resolved_symbol)
    data = load_price_frame(data_path)
    decline_window, in_sample, _ = split_intraday_in_sample_and_validation(
        data=data,
        validation_ratio=validation_ratio,
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
    )

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    results_path = target_dir / "minute_in_sample_grid_search.csv"
    results.to_csv(results_path, index=False, encoding="utf-8-sig")
    window_path = save_decline_window(target_dir, decline_window)
    best_paths = save_run_artifacts(target_dir, "minute_in_sample_best", best_run)

    return {
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
    validation_ratio: float = 0.25,
) -> dict[str, object]:
    """执行分钟线样本外验证。"""
    from etf_strategy.strategy.grid import run_grid_backtest

    resolved_symbol = _resolve_symbol(symbol, data_path)
    lot_rule = resolve_lot_size_rule(resolved_symbol)
    data = load_price_frame(data_path)
    _, _, validation = split_intraday_in_sample_and_validation(
        data=data,
        validation_ratio=validation_ratio,
    )
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
    )
    paths = save_run_artifacts(output_dir, "minute_validation", validation_run)
    return {"run": validation_run, "paths": paths}


def run_minute_full_workflow(
    data_path: str | Path,
    symbol: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "minute",
    validation_ratio: float = 0.25,
    spacings: list[float] | None = None,
    grid_counts: list[int] | None = None,
    take_profits: list[float] | None = None,
) -> dict[str, object]:
    """串联分钟线样本内寻参和样本外验证。"""
    optimization = run_minute_optimization_workflow(
        data_path=data_path,
        symbol=symbol,
        output_dir=Path(output_dir) / "optimize",
        validation_ratio=validation_ratio,
        spacings=spacings,
        grid_counts=grid_counts,
        take_profits=take_profits,
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

    return {
        "workflow_type": "minute",
        "interval": "15m",
        "validation_ratio": validation_ratio,
        "optimization": optimization,
        "validation": validation,
        "combined_summary_path": combined_path,
    }


def _resolve_symbol(symbol: str | None, data_path: str | Path) -> str:
    if symbol:
        return symbol.strip().upper()

    inferred_symbol = infer_symbol_from_data_path(data_path)
    if inferred_symbol:
        return inferred_symbol

    raise ValueError("无法从数据文件名推断标的代码，请显式传入 --symbol。")
