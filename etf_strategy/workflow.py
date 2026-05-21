from __future__ import annotations

from pathlib import Path

import pandas as pd

from etf_strategy.config import DEFAULT_OUTPUT_DIR
from etf_strategy.strategy.grid import (
    load_price_frame,
    optimize_grid_parameters,
    save_decline_window,
    save_run_artifacts,
    split_in_sample_and_validation,
)


def run_optimization_workflow(
    data_path: str | Path,
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
    output_dir: str | Path = DEFAULT_OUTPUT_DIR / "validation",
    validation_start: str = "2026-01-01",
    lookback_days: int = 120,
) -> dict[str, object]:
    """执行 2026 样本外验证。"""
    from etf_strategy.strategy.grid import run_grid_backtest

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
    )
    paths = save_run_artifacts(output_dir, "validation_2026", validation_run)
    return {"run": validation_run, "paths": paths}


def run_full_workflow(
    data_path: str | Path,
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
