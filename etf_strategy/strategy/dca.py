from __future__ import annotations
"""定投策略回测与参数搜索。

定投策略不依赖择时信号，只在固定周期的第一个可交易日投入固定金额。
这里仍然完整复用项目的交易假设：最小交易单位、手续费、滑点、仓位上限
和买入持有基准，保证它可以和网格、反弹策略放在同一张报告里比较。
"""

import hashlib
import json
import pickle
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from etf_strategy.settings import (
    DEFAULT_JOBS,
    DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    ExecutionConfig,
    build_execution_config,
)
from etf_strategy.strategy.metrics import compute_robust_score
from etf_strategy.strategy.sampling import build_walk_forward_windows, format_timestamp


TOTAL_CAPITAL = 200000.0
_DCA_OPTIMIZATION_CONTEXT: dict[str, object] | None = None


def _round_down_to_lot(units: int, lot_size: int) -> int:
    if lot_size <= 0:
        raise ValueError(f"lot_size 必须大于 0，当前值为 {lot_size}")
    return units // lot_size * lot_size


def _buy_execution_price(close_price: float, execution: ExecutionConfig) -> float:
    return close_price * (1 + max(execution.slippage_bps, 0.0) / 10000)


def _transaction_cost(execution_price: float, units: int, execution: ExecutionConfig) -> float:
    return execution_price * units * max(execution.commission_bps, 0.0) / 10000


def _annualization_factor(index: pd.Index) -> float:
    if len(index) < 2 or not isinstance(index, pd.DatetimeIndex):
        return 252.0
    median_delta = index.to_series().diff().dropna().median()
    if pd.isna(median_delta) or median_delta >= pd.Timedelta(days=1):
        return 252.0
    return 252.0 / max(float(median_delta / pd.Timedelta(days=1)), 1e-9)


def _buy_cash_required_per_unit(close_price: float, execution: ExecutionConfig) -> float:
    execution_price = _buy_execution_price(close_price, execution)
    return execution_price * (1 + max(execution.commission_bps, 0.0) / 10000)


def _affordable_units(cash_budget: float, close_price: float, lot_size: int, execution: ExecutionConfig) -> int:
    unit_cash = _buy_cash_required_per_unit(close_price, execution)
    raw_units = int(cash_budget / unit_cash) if unit_cash > 0 else 0
    return _round_down_to_lot(raw_units, lot_size)


def _build_benchmark_metrics(
    data: pd.DataFrame,
    total_capital: float,
    lot_size: int,
    execution: ExecutionConfig,
) -> dict[str, float | int]:
    entry_price = float(data.iloc[0]["Close"])
    final_price = float(data.iloc[-1]["Close"])
    buy_hold_units = _affordable_units(total_capital, entry_price, lot_size, execution)
    buy_hold_cash_used = buy_hold_units * _buy_cash_required_per_unit(entry_price, execution)
    buy_hold_equity = total_capital - buy_hold_cash_used + buy_hold_units * final_price
    return {
        "CashIdleUnits": 0,
        "CashIdleFinalEquity": total_capital,
        "CashIdleReturnPct": 0.0,
        "BaseOnlyUnits": 0,
        "BaseOnlyFinalEquity": total_capital,
        "BaseOnlyReturnPct": 0.0,
        "BuyHoldUnits": buy_hold_units,
        "BuyHoldFinalEquity": buy_hold_equity,
        "BuyHoldReturnPct": (buy_hold_equity / total_capital - 1) * 100 if total_capital else 0.0,
    }


def _period_key(timestamp: pd.Timestamp, frequency: str) -> tuple[int, int]:
    if frequency == "weekly":
        calendar = timestamp.isocalendar()
        return int(calendar.year), int(calendar.week)
    if frequency == "monthly":
        return timestamp.year, timestamp.month
    raise ValueError(f"dca frequency 仅支持 weekly/monthly，当前值为 {frequency}")


def _build_dca_schedule(index: pd.DatetimeIndex, frequency: str, day_rule: str) -> set[pd.Timestamp]:
    """按真实可交易日生成定投触发点。

    当前只实现每个周期第一个交易日。这样不会假设自然日一定开市，也能兼容
    港股、美股、A 股 ETF 的节假日缺口。
    """
    if day_rule != "first_trading_day":
        raise ValueError(f"dca day_rule 仅支持 first_trading_day，当前值为 {day_rule}")
    selected: list[pd.Timestamp] = []
    seen_periods: set[tuple[int, int]] = set()
    for timestamp in index:
        key = _period_key(pd.Timestamp(timestamp), frequency)
        if key in seen_periods:
            continue
        seen_periods.add(key)
        selected.append(pd.Timestamp(timestamp))
    return set(selected)


def _build_equity_curve(history_rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(history_rows)
    if frame.empty:
        return pd.DataFrame()
    frame["Date"] = pd.to_datetime(frame["Date"])
    curve = frame.set_index("Date")[["Equity"]].copy()
    curve["PeakEquity"] = curve["Equity"].cummax()
    curve["DrawdownPct"] = np.where(curve["PeakEquity"] > 0, curve["Equity"] / curve["PeakEquity"] - 1, 0.0)
    return curve


def _compute_score(return_pct: float, max_drawdown_pct: float, invested_ratio_pct: float) -> float:
    """定投评分更重视收益、回撤和资金是否真正投入。"""
    return return_pct - abs(max_drawdown_pct) * 0.5 + min(invested_ratio_pct, 100.0) * 0.02


def run_dca_backtest(
    data: pd.DataFrame,
    scenario_name: str,
    symbol: str,
    market: str,
    lot_size: int,
    lot_size_source: str,
    params: dict[str, object],
    total_capital: float = TOTAL_CAPITAL,
    execution_config: ExecutionConfig | None = None,
) -> dict[str, object]:
    """运行一次固定周期定投回测。"""
    if data.empty:
        raise ValueError("定投回测需要非空行情数据。")
    execution = execution_config or build_execution_config("research")
    frame = data.copy()
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()

    investment_amount = float(params["investment_amount"])
    frequency = str(params["frequency"])
    day_rule = str(params["day_rule"])
    dca_position_ratio = float(params.get("max_position_ratio", execution.max_position_ratio))
    max_position_ratio = min(max(dca_position_ratio, 0.0), max(execution.max_position_ratio, 0.0))
    schedule_dates = _build_dca_schedule(frame.index, frequency=frequency, day_rule=day_rule)

    cash = total_capital
    position_units = 0
    total_cost_basis = 0.0
    transaction_cost_total = 0.0
    slippage_cost_total = 0.0
    invested_cash = 0.0
    buy_count = 0
    skip_count = 0
    max_position_ratio_used = 0.0
    peak_equity = total_capital
    max_drawdown_pct = 0.0
    event_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    history_rows: list[dict[str, object]] = []

    for timestamp, row in frame.iterrows():
        current_date = pd.Timestamp(timestamp)
        close_price = float(row["Close"])
        market_value_before = position_units * close_price
        position_budget_left = max(total_capital * max_position_ratio - market_value_before, 0.0)
        available_budget = min(investment_amount, cash, position_budget_left)

        if current_date in schedule_dates:
            execution_price = _buy_execution_price(close_price, execution)
            units = _affordable_units(available_budget, close_price, lot_size, execution)
            if units > 0:
                fee = _transaction_cost(execution_price, units, execution)
                cash_required = units * execution_price + fee
                cash -= cash_required
                position_units += units
                total_cost_basis += cash_required
                invested_cash += cash_required
                transaction_cost_total += fee
                slippage_cost = units * max(execution_price - close_price, 0.0)
                slippage_cost_total += slippage_cost
                buy_count += 1
                event_rows.append(
                    {
                        "Date": format_timestamp(current_date),
                        "EventType": "dca_buy",
                        "Level": 0,
                        "Price": close_price,
                        "ExecutionPrice": execution_price,
                        "Units": units,
                        "CashFlow": cash_required,
                        "TransactionCost": fee,
                        "SlippageCost": slippage_cost,
                        "Note": f"{frequency} 定投买入",
                    }
                )
                trade_rows.append(
                    {
                        "EntryTime": format_timestamp(current_date),
                        "ExitTime": format_timestamp(current_date),
                        "Duration": "0 days",
                        "EntryPrice": execution_price,
                        "ExitPrice": execution_price,
                        # 平台详情用 Size 符号判断买卖方向，买入记录保持负数。
                        "Size": -units,
                        "PnL": 0.0,
                        "ReturnPct": 0.0,
                        "Tag": "dca_buy",
                    }
                )
            else:
                skip_count += 1
                event_rows.append(
                    {
                        "Date": format_timestamp(current_date),
                        "EventType": "dca_skip",
                        "Level": 0,
                        "Price": close_price,
                        "ExecutionPrice": close_price,
                        "Units": 0,
                        "CashFlow": 0.0,
                        "TransactionCost": 0.0,
                        "SlippageCost": 0.0,
                        "Note": "可用预算不足一手或已触及仓位上限，跳过本期定投",
                    }
                )

        market_value = position_units * close_price
        equity = cash + market_value
        peak_equity = max(peak_equity, equity)
        drawdown_pct = (equity / peak_equity - 1) * 100 if peak_equity else 0.0
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)
        position_ratio = market_value / total_capital if total_capital else 0.0
        max_position_ratio_used = max(max_position_ratio_used, position_ratio)
        average_cost = total_cost_basis / position_units if position_units else 0.0
        unrealized_pnl = position_units * close_price - total_cost_basis if position_units else 0.0
        history_rows.append(
            {
                "Date": format_timestamp(current_date),
                "Close": close_price,
                "PositionUnits": position_units,
                "OpenGridLevels": 1 if position_units > 0 else 0,
                "GrossCost": total_cost_basis,
                "RealizedGridProfit": 0.0,
                "ClosedGridNetProfit": 0.0,
                "UnrealizedPnl": unrealized_pnl,
                "EffectiveCost": average_cost,
                "CostReductionPct": 0.0,
                "MarketValue": market_value,
                "OpenGridMarketValue": market_value,
                "PositionRatioPct": position_ratio * 100,
                "MaxCapitalUsedPct": max_position_ratio_used * 100,
                "TransactionCostCumulative": transaction_cost_total,
                "SlippageCostCumulative": slippage_cost_total,
                "MaxPositionRatioUsedPct": max_position_ratio_used * 100,
                "Equity": equity,
            }
        )

    history = pd.DataFrame(history_rows)
    events = pd.DataFrame(event_rows)
    trades = pd.DataFrame(trade_rows)
    equity_curve = _build_equity_curve(history_rows)
    final_equity = float(history.iloc[-1]["Equity"]) if not history.empty else total_capital
    return_pct = (final_equity / total_capital - 1) * 100 if total_capital else 0.0
    invested_ratio_pct = invested_cash / total_capital * 100 if total_capital else 0.0
    annual_factor = _annualization_factor(frame.index)
    annual_return_pct = ((final_equity / total_capital) ** (annual_factor / max(len(frame), 1)) - 1) * 100 if total_capital else 0.0
    benchmark_metrics = _build_benchmark_metrics(frame, total_capital, lot_size, execution)
    latest_snapshot = history.iloc[-1].to_dict() if not history.empty else {}
    score = _compute_score(return_pct, abs(max_drawdown_pct), invested_ratio_pct)

    summary = {
        "Symbol": symbol,
        "Market": market,
        "Scenario": scenario_name,
        "StrategyKind": "dca",
        "StrategyName": "定投",
        "SignalFamily": "dca",
        "StartDate": format_timestamp(frame.index.min()),
        "EndDate": format_timestamp(frame.index.max()),
        "PeakDate": format_timestamp(frame["Close"].idxmax()),
        "PeakPrice": float(frame["Close"].max()),
        "EntryDate": str(trades.iloc[0]["EntryTime"]) if not trades.empty else format_timestamp(frame.index.min()),
        "EntryPrice": float(trades.iloc[0]["EntryPrice"]) if not trades.empty else float(frame.iloc[0]["Close"]),
        "AnchorDate": format_timestamp(frame.index.min()),
        "AnchorPrice": float(frame.iloc[0]["Close"]),
        "LotSize": lot_size,
        "LotSizeSource": lot_size_source,
        "BaseUnits": 0,
        "GridUnitsPerLevel": 0,
        "GridSpacingPct": 0.0,
        "GridCount": 0,
        "TakeProfitPct": 0.0,
        "ReturnPct": return_pct,
        "NetReturnPct": return_pct,
        "NetPnl": final_equity - total_capital,
        "AnnualReturnPct": annual_return_pct,
        "MaxDrawdownPct": abs(max_drawdown_pct),
        "ClosedTrades": int(len(trades)),
        "WinRatePct": 0.0,
        "FinalEquity": final_equity,
        "TotalCapital": total_capital,
        "PositionUnits": int(latest_snapshot.get("PositionUnits", 0)),
        "EffectiveCost": float(latest_snapshot.get("EffectiveCost", 0.0)),
        "CostReductionPct": 0.0,
        "RealizedGridProfit": 0.0,
        "ClosedGridNetProfit": 0.0,
        "ClosedGridReturnPct": 0.0,
        "UnrealizedPnl": float(latest_snapshot.get("UnrealizedPnl", 0.0)),
        "OpenGridMarketValue": float(latest_snapshot.get("OpenGridMarketValue", 0.0)),
        "MaxCapitalUsedPct": float(latest_snapshot.get("MaxCapitalUsedPct", 0.0)),
        "GridCyclesCompleted": buy_count,
        "ExecutionProfile": execution.profile,
        "CommissionBps": execution.commission_bps,
        "SlippageBps": execution.slippage_bps,
        "TransactionCost": transaction_cost_total,
        "SlippageCost": slippage_cost_total,
        "MaxPositionRatio": max_position_ratio * 100,
        "MaxPositionRatioUsed": max_position_ratio_used * 100,
        "StopLossPct": 0.0,
        "CooldownBars": 0,
        "StopLossEvents": 0,
        "RiskSkipEvents": skip_count,
        "GridMode": "dca",
        "LeftSidePolicy": "hold",
        "RequestedLeftSidePolicy": "hold",
        "PrimaryLeftSidePolicy": "hold",
        "ForceExitLossPct": 0.0,
        "ForceExitTriggered": False,
        "ForceExitEvents": 0,
        "ForceExitDate": "",
        "ForceExitLossRatioPct": 0.0,
        "Benchmark": execution.benchmark,
        "investment_amount": investment_amount,
        "frequency": frequency,
        "day_rule": day_rule,
        "max_position_ratio": max_position_ratio,
        "DcaInvestmentAmount": investment_amount,
        "DcaFrequency": frequency,
        "DcaDayRule": day_rule,
        "DcaBuyCount": buy_count,
        "DcaSkipCount": skip_count,
        "DcaInvestedCash": invested_cash,
        "DcaInvestedRatioPct": invested_ratio_pct,
        "DcaAverageCost": float(latest_snapshot.get("EffectiveCost", 0.0)),
        **benchmark_metrics,
        "GridVsCashIdle": final_equity - float(benchmark_metrics["CashIdleFinalEquity"]),
        "GridVsBaseOnly": final_equity - float(benchmark_metrics["BaseOnlyFinalEquity"]),
        "GridVsBuyHold": final_equity - float(benchmark_metrics["BuyHoldFinalEquity"]),
        "Score": score,
        "TriggeredEntry": buy_count > 0,
        "TriggeredGridEntry": buy_count > 0,
    }
    return {
        "summary": summary,
        "history": history,
        "events": events,
        "trades": trades,
        "equity_curve": equity_curve,
        "stats": summary,
    }


def _data_fingerprint(data: pd.DataFrame) -> str:
    hash_value = int(pd.util.hash_pandas_object(data.reset_index(), index=False).sum())
    return f"{len(data)}:{format_timestamp(data.index.min())}:{format_timestamp(data.index.max())}:{hash_value}"


def _candidate_cache_path(cache_dir: str | Path | None, payload: dict[str, object]) -> Path | None:
    if cache_dir is None:
        return None
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return Path(cache_dir) / f"{digest}.pkl"


def _load_cached_candidate(cache_path: Path | None) -> dict[str, object] | None:
    if cache_path is None or not cache_path.exists():
        return None
    with cache_path.open("rb") as handle:
        return pickle.load(handle)


def _save_cached_candidate(cache_path: Path | None, run_result: dict[str, object]) -> None:
    if cache_path is None:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        pickle.dump(run_result, handle)


def _set_dca_optimization_context(context: dict[str, object] | None) -> None:
    global _DCA_OPTIMIZATION_CONTEXT
    _DCA_OPTIMIZATION_CONTEXT = context


def _summarize_dca_walk_forward(walk_forward_runs: list[dict[str, object]]) -> dict[str, float | int]:
    summaries = [run_result["summary"] for run_result in walk_forward_runs]
    score_values = [float(summary["Score"]) for summary in summaries]
    return_values = [float(summary["ReturnPct"]) for summary in summaries]
    drawdown_values = [float(summary["MaxDrawdownPct"]) for summary in summaries]
    window_count = len(summaries)
    positive_window_ratio = sum(1 for value in return_values if value > 0) / window_count * 100 if window_count else 0.0
    score_mean = float(np.mean(score_values)) if score_values else 0.0
    score_min = float(np.min(score_values)) if score_values else 0.0
    return_std = float(np.std(return_values, ddof=0)) if return_values else 0.0
    return {
        "WalkForwardWindowCount": window_count,
        "WalkForwardScoreMean": score_mean,
        "WalkForwardScoreMin": score_min,
        "WalkForwardReturnMeanPct": float(np.mean(return_values)) if return_values else 0.0,
        "WalkForwardReturnWorstPct": float(np.min(return_values)) if return_values else 0.0,
        "WalkForwardDrawdownMeanPct": float(np.mean(drawdown_values)) if drawdown_values else 0.0,
        "WalkForwardCostReductionMeanPct": 0.0,
        "WalkForwardClosedGridReturnMeanPct": 0.0,
        "WalkForwardReturnStdPct": return_std,
        "WalkForwardPositiveWindowRatio": positive_window_ratio,
        "RobustScore": compute_robust_score(score_mean, score_min, return_std, window_count),
    }


def _run_dca_candidate_task(params: dict[str, object]) -> dict[str, object]:
    context = _DCA_OPTIMIZATION_CONTEXT
    if context is None:
        raise RuntimeError("定投寻参上下文尚未初始化。")
    cache_payload = {
        "data": context["data_fingerprint"],
        "scenario": context["scenario_name"],
        "strategy_kind": "dca",
        "symbol": context["symbol"],
        "market": context["market"],
        "lot_size": context["lot_size"],
        "params": params,
        "execution": asdict(context["execution"]),
        "wf_window_count": context["wf_window_count"],
        "wf_min_window_size": context["wf_min_window_size"],
    }
    cache_path = _candidate_cache_path(context["cache_dir"], cache_payload)
    cached = _load_cached_candidate(cache_path)
    if cached is not None:
        return cached
    run_result = run_dca_backtest(
        data=context["data"],
        scenario_name=str(context["scenario_name"]),
        symbol=str(context["symbol"]),
        market=str(context["market"]),
        lot_size=int(context["lot_size"]),
        lot_size_source=str(context["lot_size_source"]),
        params=params,
        execution_config=context["execution"],
    )
    walk_forward_runs = [
        run_dca_backtest(
            data=window,
            scenario_name=f"{context['scenario_name']}_wf_{index + 1}",
            symbol=str(context["symbol"]),
            market=str(context["market"]),
            lot_size=int(context["lot_size"]),
            lot_size_source=str(context["lot_size_source"]),
            params=params,
            execution_config=context["execution"],
        )
        for index, window in enumerate(context["walk_forward_windows"])
    ]
    run_result["summary"].update(_summarize_dca_walk_forward(walk_forward_runs))
    _save_cached_candidate(cache_path, run_result)
    return run_result


def optimize_dca_parameters(
    data: pd.DataFrame,
    parameter_space: dict[str, list[object]],
    scenario_name: str,
    symbol: str,
    market: str,
    lot_size: int,
    lot_size_source: str,
    execution_config: ExecutionConfig | None = None,
    wf_window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    wf_min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    jobs: int = DEFAULT_JOBS,
    cache_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """穷举定投参数，并用多窗口稳健性排序。"""
    execution = execution_config or build_execution_config("research")
    keys = list(parameter_space)
    candidate_params = [dict(zip(keys, values)) for values in product(*(parameter_space[key] for key in keys))]
    if not candidate_params:
        raise ValueError("定投参数空间为空。")
    context = {
        "data": data,
        "walk_forward_windows": build_walk_forward_windows(
            data,
            window_count=wf_window_count,
            min_window_size=wf_min_window_size,
        ),
        "scenario_name": scenario_name,
        "symbol": symbol,
        "market": market,
        "lot_size": lot_size,
        "lot_size_source": lot_size_source,
        "execution": execution,
        "wf_window_count": wf_window_count,
        "wf_min_window_size": wf_min_window_size,
        "cache_dir": cache_dir,
        "data_fingerprint": _data_fingerprint(data),
    }
    effective_jobs = max(1, int(jobs))
    if effective_jobs == 1 or len(candidate_params) <= 1:
        _set_dca_optimization_context(context)
        try:
            candidate_runs = [_run_dca_candidate_task(params) for params in candidate_params]
        finally:
            _set_dca_optimization_context(None)
    else:
        with ProcessPoolExecutor(
            max_workers=effective_jobs,
            initializer=_set_dca_optimization_context,
            initargs=(context,),
        ) as executor:
            candidate_runs = list(executor.map(_run_dca_candidate_task, candidate_params))

    rows = [run_result["summary"] for run_result in candidate_runs]
    run_records = {
        json.dumps(
            {
                "investment_amount": row["investment_amount"],
                "frequency": row["frequency"],
                "day_rule": row["day_rule"],
                "max_position_ratio": row["max_position_ratio"],
            },
            ensure_ascii=False,
            sort_keys=True,
        ): run_result
        for row, run_result in zip(rows, candidate_runs, strict=True)
    }
    results = pd.DataFrame(rows).sort_values(
        ["RobustScore", "WalkForwardScoreMin", "WalkForwardPositiveWindowRatio", "Score", "ReturnPct"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    if results.empty:
        raise ValueError("定投参数搜索未产生任何结果。")
    best_row = results.iloc[0]
    best_key = json.dumps(
        {
            "investment_amount": best_row["investment_amount"],
            "frequency": best_row["frequency"],
            "day_rule": best_row["day_rule"],
            "max_position_ratio": best_row["max_position_ratio"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    best_run = run_records.get(best_key)
    if best_run is None:
        raise ValueError("无法回取最优定投参数对应的回测结果。")
    return results, best_run
