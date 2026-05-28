from __future__ import annotations
"""布林带均值回归策略回测与参数搜索。

这里补上一类市场上非常常见、且与趋势跟随互补的日线策略：

1. 价格跌破布林带下轨、同时动量偏弱时买入。
2. 价格回到中轨附近时止盈/离场，强调“向均值回归”。
3. 统一复用已有执行口径、买入持有对照、冷却与仓位限制。

它适合作为“震荡环境下的均值回归基线”，帮助和双均线趋势形成对照。
"""

import json
from concurrent.futures import ProcessPoolExecutor
from itertools import product

import numpy as np
import pandas as pd

from strategy_studio.settings import (
    DEFAULT_JOBS,
    DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    ExecutionConfig,
    build_execution_config,
)
from strategy_studio.strategy.metrics import compute_rebound_score, summarize_walk_forward_runs
from strategy_studio.strategy.sampling import build_walk_forward_windows, format_timestamp


TOTAL_CAPITAL = 200000.0
_BOLLINGER_OPTIMIZATION_CONTEXT: dict[str, object] | None = None


def _compute_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_gain = up.rolling(window=window, min_periods=window).mean()
    avg_loss = down.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.fillna(50.0)


def _round_down_to_lot(units: int, lot_size: int) -> int:
    if lot_size <= 0:
        raise ValueError(f"lot_size 必须大于 0，当前值为 {lot_size}")
    return units // lot_size * lot_size


def _buy_execution_price(close_price: float, execution: ExecutionConfig) -> float:
    return close_price * (1 + max(execution.slippage_bps, 0.0) / 10000)


def _sell_execution_price(close_price: float, execution: ExecutionConfig) -> float:
    return close_price * (1 - max(execution.slippage_bps, 0.0) / 10000)


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
        "BuyHoldUnits": buy_hold_units,
        "BuyHoldFinalEquity": buy_hold_equity,
        "BuyHoldReturnPct": (buy_hold_equity / total_capital - 1) * 100 if total_capital else 0.0,
    }


def _prepare_features(data: pd.DataFrame, ma_window: int, band_width: float) -> pd.DataFrame:
    frame = data.copy()
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    frame["RSI"] = _compute_rsi(frame["Close"], 6)
    frame["MiddleBand"] = frame["Close"].rolling(window=ma_window, min_periods=ma_window).mean()
    frame["BandStd"] = frame["Close"].rolling(window=ma_window, min_periods=ma_window).std(ddof=0)
    frame["LowerBand"] = frame["MiddleBand"] - frame["BandStd"] * band_width
    frame["UpperBand"] = frame["MiddleBand"] + frame["BandStd"] * band_width
    return frame


def _build_equity_curve(history_rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(history_rows)
    if frame.empty:
        return pd.DataFrame()
    frame["Date"] = pd.to_datetime(frame["Date"])
    curve = frame.set_index("Date")[["Equity"]].copy()
    curve["PeakEquity"] = curve["Equity"].cummax()
    curve["DrawdownPct"] = np.where(curve["PeakEquity"] > 0, curve["Equity"] / curve["PeakEquity"] - 1, 0.0)
    return curve


def run_bollinger_reversion_backtest(
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
    """运行一次布林带均值回归回测。"""
    if data.empty:
        raise ValueError("布林带均值回归回测需要非空行情数据。")

    execution = execution_config or build_execution_config("research")
    ma_window = int(params["ma_window"])
    band_width = float(params["band_width"])
    rsi_entry = float(params["rsi_entry"])
    take_profit_pct = float(params["take_profit_pct"])
    stop_loss_pct = float(params["stop_loss_pct"])
    max_hold_bars = int(params["max_hold_bars"])
    if ma_window <= 1:
        raise ValueError("布林带窗口必须大于 1。")
    if band_width <= 0:
        raise ValueError("布林带宽度必须大于 0。")

    frame = _prepare_features(data, ma_window=ma_window, band_width=band_width)
    cash = total_capital
    position_units = 0
    entry_execution_price = 0.0
    entry_raw_price = 0.0
    entry_time: pd.Timestamp | None = None
    entry_cost = 0.0
    hold_bars = 0
    cooldown_remaining = 0
    realized_profit = 0.0
    transaction_cost_total = 0.0
    slippage_cost_total = 0.0
    peak_equity = total_capital
    max_drawdown_pct = 0.0
    max_position_ratio_used = 0.0
    entry_count = 0
    mean_revert_exit_events = 0
    take_profit_events = 0
    stop_loss_events = 0
    max_hold_exit_events = 0
    cooldown_skip_events = 0

    trade_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    history_rows: list[dict[str, object]] = []
    annual_factor = _annualization_factor(frame.index)
    max_position_capital = total_capital * max(execution.max_position_ratio, 0.0)
    param_signature = json.dumps(params, ensure_ascii=False, sort_keys=True, default=str)

    for timestamp, row in frame.iterrows():
        close_price = float(row["Close"])
        middle_band = row["MiddleBand"]
        lower_band = row["LowerBand"]
        upper_band = row["UpperBand"]
        rsi = float(row["RSI"]) if pd.notna(row["RSI"]) else 50.0

        if position_units > 0:
            hold_bars += 1
            open_return_pct = (close_price / entry_raw_price - 1) * 100 if entry_raw_price else 0.0
            exit_reason = ""
            if stop_loss_pct > 0 and open_return_pct <= -stop_loss_pct:
                exit_reason = "stop_loss_sell"
                stop_loss_events += 1
            elif take_profit_pct > 0 and open_return_pct >= take_profit_pct:
                exit_reason = "take_profit_sell"
                take_profit_events += 1
            elif pd.notna(middle_band) and close_price >= float(middle_band):
                exit_reason = "mean_revert_sell"
                mean_revert_exit_events += 1
            elif max_hold_bars > 0 and hold_bars >= max_hold_bars:
                exit_reason = "max_hold_sell"
                max_hold_exit_events += 1

            if exit_reason:
                exit_execution_price = _sell_execution_price(close_price, execution)
                exit_cost = _transaction_cost(exit_execution_price, position_units, execution)
                cash += position_units * exit_execution_price - exit_cost
                pnl = position_units * (exit_execution_price - entry_execution_price) - entry_cost - exit_cost
                realized_profit += pnl
                transaction_cost_total += exit_cost
                slippage_cost_total += position_units * max(close_price - exit_execution_price, 0.0)
                trade_rows.append(
                    {
                        "EntryTime": format_timestamp(entry_time) if entry_time is not None else "",
                        "ExitTime": format_timestamp(timestamp),
                        "Duration": str(timestamp - entry_time) if entry_time is not None else "0 days",
                        "EntryPrice": entry_execution_price,
                        "ExitPrice": exit_execution_price,
                        "Size": position_units,
                        "PnL": pnl,
                        "ReturnPct": (exit_execution_price / entry_execution_price - 1) if entry_execution_price else 0.0,
                        "Tag": "bollinger_reversion",
                    }
                )
                event_rows.append(
                    {
                        "Date": format_timestamp(timestamp),
                        "EventType": exit_reason,
                        "Level": 0,
                        "Price": close_price,
                        "ExecutionPrice": exit_execution_price,
                        "Units": position_units,
                        "CashFlow": position_units * exit_execution_price - exit_cost,
                        "TransactionCost": exit_cost,
                        "SlippageCost": position_units * max(close_price - exit_execution_price, 0.0),
                        "Note": "布林带均值回归退出",
                    }
                )
                position_units = 0
                entry_execution_price = 0.0
                entry_raw_price = 0.0
                entry_time = None
                entry_cost = 0.0
                hold_bars = 0
                cooldown_remaining = max(cooldown_remaining, int(max(execution.cooldown_bars, 0)))

        entry_allowed = (
            position_units == 0
            and pd.notna(lower_band)
            and close_price <= float(lower_band)
            and rsi <= rsi_entry
        )
        if entry_allowed:
            if cooldown_remaining > 0:
                cooldown_skip_events += 1
                event_rows.append(
                    {
                        "Date": format_timestamp(timestamp),
                        "EventType": "risk_cooldown",
                        "Level": 0,
                        "Price": close_price,
                        "ExecutionPrice": close_price,
                        "Units": 0,
                        "CashFlow": 0.0,
                        "TransactionCost": 0.0,
                        "SlippageCost": 0.0,
                        "Note": "跌破下轨出现，但仍在冷却期内",
                    }
                )
            else:
                execution_price = _buy_execution_price(close_price, execution)
                unit_cash = execution_price * (1 + max(execution.commission_bps, 0.0) / 10000)
                requested_units = int(max_position_capital / unit_cash) if unit_cash > 0 else 0
                units = _round_down_to_lot(requested_units, lot_size)
                if units <= 0:
                    raise ValueError(
                        f"布林带均值回归预算不足以买入 1 手: symbol={symbol} lot_size={lot_size} price={close_price:.2f}"
                    )
                entry_cost = _transaction_cost(execution_price, units, execution)
                cash_required = units * execution_price + entry_cost
                if cash_required <= cash:
                    cash -= cash_required
                    position_units = units
                    entry_execution_price = execution_price
                    entry_raw_price = close_price
                    entry_time = pd.Timestamp(timestamp)
                    hold_bars = 0
                    transaction_cost_total += entry_cost
                    slippage_cost_total += units * max(execution_price - close_price, 0.0)
                    entry_count += 1
                    event_rows.append(
                        {
                            "Date": format_timestamp(timestamp),
                            "EventType": "bollinger_buy",
                            "Level": 0,
                            "Price": close_price,
                            "ExecutionPrice": execution_price,
                            "Units": units,
                            "CashFlow": cash_required,
                            "TransactionCost": entry_cost,
                            "SlippageCost": units * max(execution_price - close_price, 0.0),
                            "Note": "价格跌破布林带下轨，执行均值回归买入",
                        }
                    )

        market_value = position_units * close_price
        equity = cash + market_value
        peak_equity = max(peak_equity, equity)
        drawdown_pct = (equity / peak_equity - 1) * 100 if peak_equity else 0.0
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)
        position_ratio = market_value / total_capital if total_capital else 0.0
        max_position_ratio_used = max(max_position_ratio_used, position_ratio)
        unrealized_pnl = position_units * (close_price - entry_execution_price) if position_units > 0 else 0.0

        history_rows.append(
            {
                "Date": format_timestamp(timestamp),
                "Close": close_price,
                "MiddleBand": float(middle_band) if pd.notna(middle_band) else 0.0,
                "LowerBand": float(lower_band) if pd.notna(lower_band) else 0.0,
                "UpperBand": float(upper_band) if pd.notna(upper_band) else 0.0,
                "RSI": rsi,
                "PositionUnits": position_units,
                "OpenGridLevels": 1 if position_units > 0 else 0,
                "GrossCost": position_units * entry_execution_price + entry_cost if position_units > 0 else 0.0,
                "RealizedGridProfit": realized_profit,
                "ClosedGridNetProfit": realized_profit,
                "UnrealizedPnl": unrealized_pnl,
                "EffectiveCost": entry_execution_price if position_units > 0 else 0.0,
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
        if cooldown_remaining > 0:
            cooldown_remaining -= 1

    history = pd.DataFrame(history_rows)
    events = pd.DataFrame(event_rows)
    trades = pd.DataFrame(trade_rows)
    equity_curve = _build_equity_curve(history_rows)
    final_equity = float(history.iloc[-1]["Equity"]) if not history.empty else total_capital
    return_pct = (final_equity / total_capital - 1) * 100 if total_capital else 0.0
    benchmark_metrics = _build_benchmark_metrics(frame, total_capital, lot_size, execution)
    annual_return_pct = ((final_equity / total_capital) ** (annual_factor / max(len(frame), 1)) - 1) * 100 if total_capital else 0.0
    latest_snapshot = history.iloc[-1].to_dict() if not history.empty else {}
    win_rate_pct = float((trades["PnL"] > 0).mean() * 100) if not trades.empty else 0.0
    score = compute_rebound_score(return_pct, abs(max_drawdown_pct), win_rate_pct, len(trades))

    summary = {
        "Symbol": symbol,
        "Market": market,
        "Scenario": scenario_name,
        "StrategyKind": "bollinger_reversion",
        "StrategyName": "布林带均值回归",
        "SignalFamily": "mean_reversion",
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
        "TakeProfitPct": take_profit_pct,
        "ReturnPct": return_pct,
        "NetReturnPct": return_pct,
        "NetPnl": final_equity - total_capital,
        "AnnualReturnPct": annual_return_pct,
        "MaxDrawdownPct": abs(max_drawdown_pct),
        "ClosedTrades": int(len(trades)),
        "WinRatePct": win_rate_pct,
        "FinalEquity": final_equity,
        "TotalCapital": total_capital,
        "PositionUnits": int(latest_snapshot.get("PositionUnits", 0)),
        "EffectiveCost": float(latest_snapshot.get("EffectiveCost", 0.0)),
        "CostReductionPct": 0.0,
        "RealizedGridProfit": realized_profit,
        "ClosedGridNetProfit": realized_profit,
        "ClosedGridReturnPct": realized_profit / total_capital * 100 if total_capital else 0.0,
        "UnrealizedPnl": float(latest_snapshot.get("UnrealizedPnl", 0.0)),
        "OpenGridMarketValue": float(latest_snapshot.get("OpenGridMarketValue", 0.0)),
        "MaxCapitalUsedPct": float(latest_snapshot.get("MaxCapitalUsedPct", 0.0)),
        "GridCyclesCompleted": int(len(trades)),
        "ExecutionProfile": execution.profile,
        "CommissionBps": execution.commission_bps,
        "SlippageBps": execution.slippage_bps,
        "TransactionCost": transaction_cost_total,
        "SlippageCost": slippage_cost_total,
        "MaxPositionRatio": execution.max_position_ratio * 100,
        "MaxPositionRatioUsed": max_position_ratio_used * 100,
        "StopLossPct": stop_loss_pct,
        "CooldownBars": execution.cooldown_bars,
        "StopLossEvents": stop_loss_events,
        "RiskSkipEvents": cooldown_skip_events,
        "GridMode": "mean_reversion",
        "LeftSidePolicy": "hold",
        "RequestedLeftSidePolicy": "hold",
        "PrimaryLeftSidePolicy": "hold",
        "ForceExitLossPct": 0.0,
        "ForceExitTriggered": False,
        "ForceExitEvents": 0,
        "ForceExitDate": "",
        "ForceExitLossRatioPct": 0.0,
        "Benchmark": execution.benchmark,
        "ma_window": ma_window,
        "band_width": band_width,
        "rsi_entry": rsi_entry,
        "take_profit_pct": take_profit_pct,
        "stop_loss_pct": stop_loss_pct,
        "max_hold_bars": max_hold_bars,
        "MaWindow": ma_window,
        "BandWidth": band_width,
        "RsiEntry": rsi_entry,
        "MaxHoldBars": max_hold_bars,
        "BollingerEntryEvents": entry_count,
        "MeanRevertExitEvents": mean_revert_exit_events,
        "TakeProfitEvents": take_profit_events,
        "MaxHoldExitEvents": max_hold_exit_events,
        "ParamSignature": param_signature,
        **benchmark_metrics,
        "GridVsCashIdle": final_equity - float(benchmark_metrics["CashIdleFinalEquity"]),
        "GridVsBuyHold": final_equity - float(benchmark_metrics["BuyHoldFinalEquity"]),
        "StrategyVsBuyHold": final_equity - float(benchmark_metrics["BuyHoldFinalEquity"]),
        "OutperformBuyHold": final_equity > float(benchmark_metrics["BuyHoldFinalEquity"]),
        "Score": score,
        "TriggeredEntry": entry_count > 0,
        "TriggeredGridEntry": entry_count > 0,
    }

    if not trades.empty:
        hold_lengths: list[int] = []
        for trade in trades.itertuples(index=False):
            entry_slice_time = pd.Timestamp(trade.EntryTime)
            exit_slice_time = pd.Timestamp(trade.ExitTime)
            hold_lengths.append(len(frame.loc[entry_slice_time:exit_slice_time]))
        summary["AvgHoldBars"] = float(np.mean(hold_lengths))
    else:
        summary["AvgHoldBars"] = 0.0

    return {
        "summary": summary,
        "history": history,
        "events": events,
        "trades": trades,
        "equity_curve": equity_curve,
        "stats": summary,
    }


def _set_bollinger_optimization_context(context: dict[str, object] | None) -> None:
    global _BOLLINGER_OPTIMIZATION_CONTEXT
    _BOLLINGER_OPTIMIZATION_CONTEXT = context


def _run_bollinger_candidate_task(params: dict[str, object]) -> dict[str, object]:
    context = _BOLLINGER_OPTIMIZATION_CONTEXT
    if context is None:
        raise RuntimeError("布林带均值回归寻参上下文尚未初始化。")
    run_result = run_bollinger_reversion_backtest(
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
        run_bollinger_reversion_backtest(
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
    run_result["summary"].update(summarize_walk_forward_runs(walk_forward_runs))
    return run_result


def optimize_bollinger_reversion_parameters(
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
) -> tuple[pd.DataFrame, dict[str, object]]:
    """穷举布林带均值回归参数，并按稳健性排序。"""
    execution = execution_config or build_execution_config("research")
    ma_windows = [int(item) for item in parameter_space["ma_window"]]
    band_widths = [float(item) for item in parameter_space["band_width"]]
    rsi_entries = [float(item) for item in parameter_space["rsi_entry"]]
    take_profits = [float(item) for item in parameter_space["take_profit_pct"]]
    stop_losses = [float(item) for item in parameter_space["stop_loss_pct"]]
    max_hold_bars = [int(item) for item in parameter_space["max_hold_bars"]]
    candidate_params = [
        {
            "ma_window": ma_window,
            "band_width": band_width,
            "rsi_entry": rsi_entry,
            "take_profit_pct": take_profit_pct,
            "stop_loss_pct": stop_loss_pct,
            "max_hold_bars": max_hold_bar,
        }
        for ma_window, band_width, rsi_entry, take_profit_pct, stop_loss_pct, max_hold_bar in product(
            ma_windows,
            band_widths,
            rsi_entries,
            take_profits,
            stop_losses,
            max_hold_bars,
        )
    ]
    if not candidate_params:
        raise ValueError("布林带均值回归参数空间为空。")

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
    }
    effective_jobs = max(1, int(jobs))
    if effective_jobs == 1 or len(candidate_params) <= 1:
        _set_bollinger_optimization_context(context)
        try:
            candidate_runs = [_run_bollinger_candidate_task(params) for params in candidate_params]
        finally:
            _set_bollinger_optimization_context(None)
    else:
        with ProcessPoolExecutor(
            max_workers=effective_jobs,
            initializer=_set_bollinger_optimization_context,
            initargs=(context,),
        ) as executor:
            candidate_runs = list(executor.map(_run_bollinger_candidate_task, candidate_params))

    rows = [run_result["summary"] for run_result in candidate_runs]
    run_records = {
        json.dumps(
            {
                "ma_window": row["ma_window"],
                "band_width": row["band_width"],
                "rsi_entry": row["rsi_entry"],
                "take_profit_pct": row["take_profit_pct"],
                "stop_loss_pct": row["stop_loss_pct"],
                "max_hold_bars": row["max_hold_bars"],
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
        raise ValueError("布林带均值回归参数搜索未产生任何结果。")
    best_row = results.iloc[0]
    best_key = json.dumps(
        {
            "ma_window": best_row["ma_window"],
            "band_width": best_row["band_width"],
            "rsi_entry": best_row["rsi_entry"],
            "take_profit_pct": best_row["take_profit_pct"],
            "stop_loss_pct": best_row["stop_loss_pct"],
            "max_hold_bars": best_row["max_hold_bars"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    best_run = run_records.get(best_key)
    if best_run is None:
        raise ValueError("无法回取最优布林带均值回归参数对应的回测结果。")
    return results, best_run
