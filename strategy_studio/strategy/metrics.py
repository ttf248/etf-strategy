from __future__ import annotations
"""网格策略评分与稳健性指标。"""

import numpy as np


def compute_score(return_pct: float, max_drawdown_pct: float, closed_grid_return_pct: float) -> float:
    """收益/回撤/闭环网格利润综合评分。"""
    return return_pct - abs(max_drawdown_pct) * 0.7 + closed_grid_return_pct * 0.5


def compute_rebound_score(return_pct: float, max_drawdown_pct: float, win_rate_pct: float, trade_count: int) -> float:
    """给反转类策略使用的通用评分。"""
    entry_weight = min(max(trade_count, 0), 10) / 10
    return return_pct - abs(max_drawdown_pct) * 0.7 + win_rate_pct * 0.05 * entry_weight


def compute_robust_score(
    walk_forward_score_mean: float,
    walk_forward_score_min: float,
    walk_forward_return_std_pct: float,
    window_count: int,
) -> float:
    """基于多窗口结果给参数做稳健性评分。"""
    if window_count <= 1:
        return walk_forward_score_mean
    return walk_forward_score_mean * 0.6 + walk_forward_score_min * 0.4 - walk_forward_return_std_pct * 0.25


def summarize_walk_forward_runs(walk_forward_runs: list[dict[str, object]]) -> dict[str, float | int]:
    """汇总多窗口回测结果。"""
    summaries = [run_result["summary"] for run_result in walk_forward_runs]
    score_values = [float(summary["Score"]) for summary in summaries]
    return_values = [float(summary["ReturnPct"]) for summary in summaries]
    drawdown_values = [float(summary["MaxDrawdownPct"]) for summary in summaries]
    closed_grid_values = [
        float(summary.get("ClosedGridReturnPct", summary.get("CostReductionPct", 0.0))) for summary in summaries
    ]
    window_count = len(summaries)
    positive_window_ratio = sum(1 for value in return_values if value > 0) / window_count * 100 if window_count else 0.0
    walk_forward_score_mean = float(np.mean(score_values)) if score_values else 0.0
    walk_forward_score_min = float(np.min(score_values)) if score_values else 0.0
    walk_forward_return_std_pct = float(np.std(return_values, ddof=0)) if return_values else 0.0

    return {
        "WalkForwardWindowCount": window_count,
        "WalkForwardScoreMean": walk_forward_score_mean,
        "WalkForwardScoreMin": walk_forward_score_min,
        "WalkForwardReturnMeanPct": float(np.mean(return_values)) if return_values else 0.0,
        "WalkForwardReturnWorstPct": float(np.min(return_values)) if return_values else 0.0,
        "WalkForwardDrawdownMeanPct": float(np.mean(drawdown_values)) if drawdown_values else 0.0,
        "WalkForwardCostReductionMeanPct": float(np.mean(closed_grid_values)) if closed_grid_values else 0.0,
        "WalkForwardClosedGridReturnMeanPct": float(np.mean(closed_grid_values)) if closed_grid_values else 0.0,
        "WalkForwardReturnStdPct": walk_forward_return_std_pct,
        "WalkForwardPositiveWindowRatio": positive_window_ratio,
        "RobustScore": compute_robust_score(
            walk_forward_score_mean=walk_forward_score_mean,
            walk_forward_score_min=walk_forward_score_min,
            walk_forward_return_std_pct=walk_forward_return_std_pct,
            window_count=window_count,
        ),
    }
