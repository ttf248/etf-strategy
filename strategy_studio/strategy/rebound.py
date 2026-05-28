from __future__ import annotations
"""反转类策略回测与参数搜索。

这里统一承接两类场景：

1. 日线左侧超跌后的短周期反弹。
2. 15 分钟线急跌反抽，并可叠加“冲高回落不追高”的过滤条件。

模块保持和网格策略相同的返回结构，方便工作流、报告和测试共用。
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
    StrategyKind,
    build_execution_config,
)
from strategy_studio.strategy.metrics import compute_rebound_score, summarize_walk_forward_runs
from strategy_studio.strategy.sampling import build_walk_forward_windows, format_timestamp


TOTAL_CAPITAL = 200000.0
_REBOUND_OPTIMIZATION_CONTEXT: dict[str, object] | None = None


def _compute_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_gain = up.rolling(window=window, min_periods=window).mean()
    avg_loss = down.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.fillna(50.0)


def _compute_atr(data: pd.DataFrame, window: int) -> pd.Series:
    prev_close = data["Close"].shift(1)
    true_range = pd.concat(
        [
            data["High"] - data["Low"],
            (data["High"] - prev_close).abs(),
            (data["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window=window, min_periods=window).mean()


def _compute_rolling_vwap(data: pd.DataFrame, window: int) -> pd.Series:
    weighted = data["Close"] * data["Volume"]
    return weighted.rolling(window=window, min_periods=window).sum() / data["Volume"].rolling(
        window=window,
        min_periods=window,
    ).sum()


def _annualization_factor(index: pd.Index) -> float:
    if len(index) < 2:
        return 252.0
    if not isinstance(index, pd.DatetimeIndex):
        return 252.0
    median_delta = index.to_series().diff().dropna().median()
    if pd.isna(median_delta):
        return 252.0
    if median_delta >= pd.Timedelta(days=1):
        return 252.0
    day_fraction = max(median_delta / pd.Timedelta(days=1), 1e-9)
    return 252.0 / float(day_fraction)


def _build_benchmark_metrics(
    data: pd.DataFrame,
    total_capital: float,
    lot_size: int,
    execution: ExecutionConfig,
) -> dict[str, float | int]:
    entry_price = float(data.iloc[0]["Close"])
    final_price = float(data.iloc[-1]["Close"])
    commission_rate = max(execution.commission_bps, 0.0) / 10000
    slippage_rate = max(execution.slippage_bps, 0.0) / 10000
    execution_price = entry_price * (1 + slippage_rate)
    unit_cash = execution_price * (1 + commission_rate)
    raw_units = int(total_capital / unit_cash) if unit_cash > 0 else 0
    buy_hold_units = raw_units // lot_size * lot_size if lot_size > 0 else raw_units
    buy_hold_cash_used = buy_hold_units * unit_cash
    buy_hold_equity = total_capital - buy_hold_cash_used + buy_hold_units * final_price
    return {
        "CashIdleUnits": 0,
        "CashIdleFinalEquity": total_capital,
        "CashIdleReturnPct": 0.0,
        "BuyHoldUnits": buy_hold_units,
        "BuyHoldFinalEquity": buy_hold_equity,
        "BuyHoldReturnPct": (buy_hold_equity / total_capital - 1) * 100 if total_capital else 0.0,
    }


def _build_parameter_key(strategy_kind: StrategyKind, params: dict[str, object]) -> str:
    return json.dumps({"strategy_kind": strategy_kind, **params}, ensure_ascii=False, sort_keys=True, default=str)


def _set_rebound_optimization_context(context: dict[str, object] | None) -> None:
    """为串行和多进程反转寻参统一准备只读上下文。"""
    global _REBOUND_OPTIMIZATION_CONTEXT
    _REBOUND_OPTIMIZATION_CONTEXT = context


def _run_rebound_candidate_task(params: dict[str, object]) -> dict[str, object]:
    """执行单个反转参数候选。

    保持模块级函数，避免 Windows 多进程模式下闭包任务不可 pickle。
    """
    context = _REBOUND_OPTIMIZATION_CONTEXT
    if context is None:
        raise RuntimeError("反转寻参上下文尚未初始化。")

    run_result = run_rebound_backtest(
        data=context["data"],
        scenario_name=str(context["scenario_name"]),
        strategy_kind=str(context["strategy_kind"]),
        symbol=str(context["symbol"]),
        market=str(context["market"]),
        lot_size=int(context["lot_size"]),
        lot_size_source=str(context["lot_size_source"]),
        params=params,
        execution_config=context["execution"],
    )
    walk_forward_runs = [
        run_rebound_backtest(
            data=window,
            scenario_name=f"{context['scenario_name']}_wf_{index + 1}",
            strategy_kind=str(context["strategy_kind"]),
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


def _prepare_daily_features(data: pd.DataFrame, params: dict[str, object]) -> pd.DataFrame:
    feature = data.copy()
    rsi_window = int(params["rsi_window"])
    ma_window = int(params["ma_window"])
    feature["RSI"] = _compute_rsi(feature["Close"], rsi_window)
    feature["MA"] = feature["Close"].rolling(window=ma_window, min_periods=ma_window).mean()
    feature["ATR"] = _compute_atr(feature, max(5, rsi_window))
    feature["DeviationPct"] = (feature["Close"] / feature["MA"] - 1) * 100
    return feature


def _prepare_minute_features(data: pd.DataFrame, params: dict[str, object]) -> pd.DataFrame:
    feature = data.copy()
    lookback_bars = int(params["lookback_bars"])
    feature["RSI"] = _compute_rsi(feature["Close"], 6)
    feature["RollingPeak"] = feature["Close"].shift(1).rolling(window=lookback_bars, min_periods=lookback_bars).max()
    feature["DropFromPeakPct"] = (feature["Close"] / feature["RollingPeak"] - 1) * 100
    feature["RollingVWAP"] = _compute_rolling_vwap(feature, lookback_bars)
    feature["UpperShadowPct"] = (feature["High"] / feature[["Open", "Close"]].max(axis=1) - 1) * 100
    feature["IntrabarReboundPct"] = (feature["Close"] / feature["Low"] - 1) * 100
    return feature


def _build_features(data: pd.DataFrame, strategy_kind: StrategyKind, params: dict[str, object]) -> pd.DataFrame:
    if strategy_kind == "daily_rebound":
        return _prepare_daily_features(data, params)
    return _prepare_minute_features(data, params)


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


def _strategy_display_name(strategy_kind: StrategyKind) -> str:
    mapping = {
        "grid": "网格",
        "daily_rebound": "日线超跌反弹",
        "minute_rebound": "分钟急跌反抽",
        "minute_rebound_with_fade_filter": "分钟反抽+冲高回落过滤",
    }
    return mapping[strategy_kind]


def _entry_allowed(strategy_kind: StrategyKind, row: pd.Series, previous_row: pd.Series | None, params: dict[str, object]) -> bool:
    if strategy_kind == "daily_rebound":
        if pd.isna(row["MA"]) or pd.isna(row["ATR"]):
            return False
        if previous_row is None:
            return False
        return (
            float(row["RSI"]) <= float(params["rsi_entry"])
            and float(row["DeviationPct"]) <= float(params["deviation_entry_pct"])
            and float(row["Close"]) < float(previous_row["Close"])
        )

    if pd.isna(row["RollingPeak"]) or pd.isna(row["RollingVWAP"]):
        return False
    return (
        float(row["RSI"]) <= float(params["rsi_entry"])
        and float(row["DropFromPeakPct"]) <= float(params["drop_entry_pct"])
        and float(row["Close"]) <= float(row["RollingVWAP"])
    )


def _fade_filter_active(row: pd.Series, params: dict[str, object]) -> bool:
    return float(row.get("UpperShadowPct", 0.0)) >= float(params.get("fade_filter_upper_shadow_pct", 999.0))


def _build_equity_curve(history: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(history)
    if frame.empty:
        return pd.DataFrame()
    frame["Date"] = pd.to_datetime(frame["Date"])
    curve = frame.set_index("Date")[["Equity"]].copy()
    curve["PeakEquity"] = curve["Equity"].cummax()
    curve["DrawdownPct"] = np.where(curve["PeakEquity"] > 0, curve["Equity"] / curve["PeakEquity"] - 1, 0.0)
    return curve


def run_rebound_backtest(
    data: pd.DataFrame,
    scenario_name: str,
    strategy_kind: StrategyKind,
    symbol: str,
    market: str,
    lot_size: int,
    lot_size_source: str,
    params: dict[str, object],
    total_capital: float = TOTAL_CAPITAL,
    execution_config: ExecutionConfig | None = None,
) -> dict[str, object]:
    """运行一次反转类策略回测。"""
    execution = execution_config or build_execution_config("research")
    features = _build_features(data, strategy_kind, params)

    cash = total_capital
    position_units = 0
    entry_execution_price = 0.0
    entry_raw_price = 0.0
    entry_time: pd.Timestamp | None = None
    entry_cost = 0.0
    hold_bars = 0
    realized_profit = 0.0
    transaction_cost_total = 0.0
    slippage_cost_total = 0.0
    peak_equity = total_capital
    max_drawdown_pct = 0.0
    max_position_ratio_used = 0.0
    trade_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    history_rows: list[dict[str, object]] = []
    blocked_bars_remaining = 0
    filter_blocked_events = 0
    stop_loss_events = 0
    take_profit_events = 0
    max_hold_exit_events = 0

    max_position_capital = total_capital * max(execution.max_position_ratio, 0.0)
    param_signature = _build_parameter_key(strategy_kind, params)
    annual_factor = _annualization_factor(features.index)

    for index, (timestamp, row) in enumerate(features.iterrows()):
        close_price = float(row["Close"])
        previous_row = features.iloc[index - 1] if index > 0 else None

        if strategy_kind == "minute_rebound_with_fade_filter" and _fade_filter_active(row, params):
            blocked_bars_remaining = max(blocked_bars_remaining, int(params["fade_filter_block_bars"]))
            event_rows.append(
                {
                    "Date": format_timestamp(timestamp),
                    "EventType": "filter_block",
                    "Level": 0,
                    "Price": close_price,
                    "ExecutionPrice": close_price,
                    "Units": 0,
                    "CashFlow": 0.0,
                    "TransactionCost": 0.0,
                    "SlippageCost": 0.0,
                    "Note": "检测到冲高回落上影，暂时阻止追高入场",
                }
            )
            filter_blocked_events += 1

        if position_units > 0:
            hold_bars += 1
            open_return_pct = (close_price / entry_raw_price - 1) * 100 if entry_raw_price else 0.0
            stop_loss_hit = False
            if strategy_kind == "daily_rebound":
                atr_value = float(row.get("ATR", 0.0) or 0.0)
                if atr_value > 0 and entry_raw_price > 0:
                    stop_loss_pct = atr_value * float(params["stop_loss_atr"]) / entry_raw_price * 100
                    stop_loss_hit = open_return_pct <= -stop_loss_pct
            else:
                stop_loss_hit = open_return_pct <= -float(params["stop_loss_pct"])

            exit_reason = ""
            if open_return_pct >= float(params["take_profit_pct"]):
                exit_reason = "take_profit_sell"
                take_profit_events += 1
            elif stop_loss_hit:
                exit_reason = "stop_loss_sell"
                stop_loss_events += 1
            elif hold_bars >= int(params["max_hold_bars"]):
                exit_reason = "max_hold_sell"
                max_hold_exit_events += 1
            elif strategy_kind == "minute_rebound_with_fade_filter" and _fade_filter_active(row, params):
                exit_reason = "fade_exit_sell"

            if exit_reason:
                exit_execution_price = _sell_execution_price(close_price, execution)
                exit_cost = _transaction_cost(exit_execution_price, position_units, execution)
                cash += position_units * exit_execution_price - exit_cost
                pnl = (
                    position_units * (exit_execution_price - entry_execution_price)
                    - entry_cost
                    - exit_cost
                )
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
                        "Tag": "rebound",
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
                        "Note": "平仓退出",
                    }
                )
                position_units = 0
                entry_execution_price = 0.0
                entry_raw_price = 0.0
                entry_time = None
                entry_cost = 0.0
                hold_bars = 0

        if position_units == 0 and _entry_allowed(strategy_kind, row, previous_row, params):
            if blocked_bars_remaining > 0 and strategy_kind == "minute_rebound_with_fade_filter":
                filter_blocked_events += 1
                event_rows.append(
                    {
                        "Date": format_timestamp(timestamp),
                        "EventType": "filter_skip_buy",
                        "Level": 0,
                        "Price": close_price,
                        "ExecutionPrice": close_price,
                        "Units": 0,
                        "CashFlow": 0.0,
                        "TransactionCost": 0.0,
                        "SlippageCost": 0.0,
                        "Note": "过滤窗口内，跳过这次反抽入场",
                    }
                )
            else:
                execution_price = _buy_execution_price(close_price, execution)
                unit_cash = execution_price * (1 + max(execution.commission_bps, 0.0) / 10000)
                requested_units = int(max_position_capital / unit_cash) if unit_cash > 0 else 0
                units = _round_down_to_lot(requested_units, lot_size)
                if units <= 0:
                    raise ValueError(
                        f"反转策略预算不足以买入 1 手: symbol={symbol} lot_size={lot_size} price={close_price:.2f}"
                    )
                entry_cost = _transaction_cost(execution_price, units, execution)
                cash_required = units * execution_price + entry_cost
                if cash_required <= cash:
                    cash -= cash_required
                    position_units = units
                    entry_execution_price = execution_price
                    entry_raw_price = close_price
                    entry_time = timestamp
                    hold_bars = 0
                    transaction_cost_total += entry_cost
                    slippage_cost_total += units * max(execution_price - close_price, 0.0)
                    event_rows.append(
                        {
                            "Date": format_timestamp(timestamp),
                            "EventType": "rebound_buy",
                            "Level": 0,
                            "Price": close_price,
                            "ExecutionPrice": execution_price,
                            "Units": units,
                            "CashFlow": cash_required,
                            "TransactionCost": entry_cost,
                            "SlippageCost": units * max(execution_price - close_price, 0.0),
                            "Note": "触发反转入场",
                        }
                    )

        market_value = position_units * close_price
        equity = cash + market_value
        peak_equity = max(peak_equity, equity)
        drawdown_pct = (equity / peak_equity - 1) * 100 if peak_equity else 0.0
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)
        position_ratio = market_value / total_capital if total_capital else 0.0
        max_position_ratio_used = max(max_position_ratio_used, position_ratio)
        effective_cost = entry_execution_price if position_units > 0 else 0.0
        unrealized_pnl = position_units * (close_price - entry_execution_price) if position_units > 0 else 0.0
        history_rows.append(
            {
                "Date": format_timestamp(timestamp),
                "Close": close_price,
                "PositionUnits": position_units,
                "OpenGridLevels": 1 if position_units > 0 else 0,
                "GrossCost": position_units * entry_execution_price + entry_cost if position_units > 0 else 0.0,
                "RealizedGridProfit": realized_profit,
                "ClosedGridNetProfit": realized_profit,
                "UnrealizedPnl": unrealized_pnl,
                "EffectiveCost": effective_cost,
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
        if blocked_bars_remaining > 0:
            blocked_bars_remaining -= 1

    history = pd.DataFrame(history_rows)
    events = pd.DataFrame(event_rows)
    trades = pd.DataFrame(trade_rows)
    equity_curve = _build_equity_curve(history_rows)
    final_equity = float(history.iloc[-1]["Equity"]) if not history.empty else total_capital
    return_pct = (final_equity / total_capital - 1) * 100 if total_capital else 0.0
    benchmark_metrics = _build_benchmark_metrics(data, total_capital, lot_size, execution)
    win_rate_pct = float((trades["PnL"] > 0).mean() * 100) if not trades.empty else 0.0
    score = compute_rebound_score(return_pct, abs(max_drawdown_pct), win_rate_pct, len(trades))
    annual_return_pct = ((final_equity / total_capital) ** (annual_factor / max(len(data), 1)) - 1) * 100 if total_capital else 0.0
    latest_snapshot = history.iloc[-1].to_dict() if not history.empty else {}

    summary = {
        "Symbol": symbol,
        "Market": market,
        "Scenario": scenario_name,
        "StrategyKind": strategy_kind,
        "StrategyName": _strategy_display_name(strategy_kind),
        "SignalFamily": "rebound",
        "StartDate": format_timestamp(data.index.min()),
        "EndDate": format_timestamp(data.index.max()),
        "PeakDate": format_timestamp(data["Close"].idxmax()),
        "PeakPrice": float(data["Close"].max()),
        "EntryDate": str(trades.iloc[0]["EntryTime"]) if not trades.empty else format_timestamp(data.index.min()),
        "EntryPrice": float(trades.iloc[0]["EntryPrice"]) if not trades.empty else float(data.iloc[0]["Close"]),
        "AnchorDate": format_timestamp(data.index.min()),
        "AnchorPrice": float(data.iloc[0]["Close"]),
        "LotSize": lot_size,
        "LotSizeSource": lot_size_source,
        "BaseUnits": 0,
        "GridUnitsPerLevel": 0,
        "GridSpacingPct": 0.0,
        "GridCount": 0,
        "TakeProfitPct": float(params["take_profit_pct"]),
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
        "StopLossPct": float(params.get("stop_loss_pct", 0.0)),
        "CooldownBars": 0,
        "StopLossEvents": stop_loss_events,
        "RiskSkipEvents": filter_blocked_events,
        "GridMode": "swing",
        "LeftSidePolicy": "hold",
        "RequestedLeftSidePolicy": "hold",
        "PrimaryLeftSidePolicy": "hold",
        "ForceExitLossPct": 0.0,
        "ForceExitTriggered": False,
        "ForceExitEvents": 0,
        "ForceExitDate": "",
        "ForceExitLossRatioPct": 0.0,
        "Benchmark": execution.benchmark,
        "EntryCount": int(len(events[events["EventType"] == "rebound_buy"])) if not events.empty else 0,
        "AvgHoldBars": float(np.mean([int(params["max_hold_bars"])] if trades.empty else [max(1, 1) for _ in range(len(trades))])),
        "TakeProfitEvents": take_profit_events,
        "FilterBlockedEvents": filter_blocked_events,
        "MaxHoldExitEvents": max_hold_exit_events,
        "ParamSignature": param_signature,
        **{key: value for key, value in params.items()},
        **benchmark_metrics,
        "GridVsCashIdle": final_equity - float(benchmark_metrics["CashIdleFinalEquity"]),
        "GridVsBuyHold": final_equity - float(benchmark_metrics["BuyHoldFinalEquity"]),
        "Score": score,
        "TriggeredEntry": bool(not trades.empty),
        "TriggeredGridEntry": bool(not trades.empty),
    }
    if not trades.empty:
        hold_lengths = []
        for trade in trades.itertuples(index=False):
            entry_time = pd.Timestamp(trade.EntryTime)
            exit_time = pd.Timestamp(trade.ExitTime)
            hold_lengths.append(len(data.loc[entry_time:exit_time]))
        summary["AvgHoldBars"] = float(np.mean(hold_lengths))
    return {
        "summary": summary,
        "history": history,
        "events": events,
        "trades": trades,
        "equity_curve": equity_curve,
        "stats": summary,
    }


def optimize_rebound_parameters(
    data: pd.DataFrame,
    strategy_kind: StrategyKind,
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
    """穷举反转类策略参数。

    `jobs>1` 时会切到多进程并发单个参数候选，避免线程模式在 CPU 密集型回测上受限。
    """
    execution = execution_config or build_execution_config("research")
    walk_forward_windows = build_walk_forward_windows(
        data,
        window_count=wf_window_count,
        min_window_size=wf_min_window_size,
    )
    keys = list(parameter_space)
    candidate_params = [dict(zip(keys, values)) for values in product(*(parameter_space[key] for key in keys))]
    effective_jobs = max(1, int(jobs))
    context = {
        "data": data,
        "walk_forward_windows": walk_forward_windows,
        "scenario_name": scenario_name,
        "strategy_kind": strategy_kind,
        "symbol": symbol,
        "market": market,
        "lot_size": lot_size,
        "lot_size_source": lot_size_source,
        "execution": execution,
        "wf_window_count": wf_window_count,
        "wf_min_window_size": wf_min_window_size,
    }

    if effective_jobs == 1 or len(candidate_params) <= 1:
        _set_rebound_optimization_context(context)
        try:
            candidate_runs = [_run_rebound_candidate_task(params) for params in candidate_params]
        finally:
            _set_rebound_optimization_context(None)
    else:
        with ProcessPoolExecutor(
            max_workers=effective_jobs,
            initializer=_set_rebound_optimization_context,
            initargs=(context,),
        ) as executor:
            candidate_runs = list(executor.map(_run_rebound_candidate_task, candidate_params))

    rows: list[dict[str, object]] = []
    run_records: dict[str, dict[str, object]] = {}
    for run_result in candidate_runs:
        summary = run_result["summary"]
        signature = str(summary["ParamSignature"])
        rows.append(summary)
        run_records[signature] = run_result

    results = pd.DataFrame(rows).sort_values(
        ["RobustScore", "WalkForwardScoreMin", "WalkForwardPositiveWindowRatio", "Score", "ReturnPct"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    if results.empty:
        raise ValueError("参数搜索未产生任何结果。")
    best_row = results.iloc[0]
    best_run = run_records.get(str(best_row["ParamSignature"]))
    if best_run is None:
        raise ValueError("无法回取最优参数对应的回测结果。")
    return results, best_run
