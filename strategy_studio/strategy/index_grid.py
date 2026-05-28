from __future__ import annotations
"""指数 ETF 动态回落/反弹网格策略。

这里实现的是更贴近条件单语义的一分钟网格：

1. 首根 K 线先建立长期底仓。
2. 价格先相对参考价达到涨跌阈值。
3. 再等待从局部高低点回落/反弹确认后，才执行一笔固定金额的网格单。

该模块不复用现有纯现金网格内核，因为底仓、动态高低点触发和固定交易单元
都与原有策略假设不同。
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy_studio.settings import ExecutionConfig, build_execution_config
from strategy_studio.strategy.metrics import compute_score
from strategy_studio.strategy.sampling import format_timestamp


TOTAL_CAPITAL = 10000.0
BASE_POSITION_RATIO = 0.5
GRID_TRADE_RATIO = 0.2


@dataclass(frozen=True)
class IndexGridStrategySpec:
    """单只指数 ETF 的固定策略参数。"""

    symbol: str
    name: str
    rise_trigger_pct: float
    sell_pullback_pct: float
    decline_trigger_pct: float
    buy_rebound_pct: float
    total_capital: float = TOTAL_CAPITAL
    base_position_ratio: float = BASE_POSITION_RATIO
    grid_trade_ratio: float = GRID_TRADE_RATIO


INDEX_GRID_SPECS: dict[str, IndexGridStrategySpec] = {
    "159941.SZ": IndexGridStrategySpec(
        symbol="159941.SZ",
        name="纳指ETF",
        rise_trigger_pct=0.02,
        sell_pullback_pct=0.005,
        decline_trigger_pct=0.02,
        buy_rebound_pct=0.005,
    ),
    "159605.SZ": IndexGridStrategySpec(
        symbol="159605.SZ",
        name="中概互联网ETF",
        rise_trigger_pct=0.02,
        sell_pullback_pct=0.005,
        decline_trigger_pct=0.02,
        buy_rebound_pct=0.005,
    ),
    "159866.SZ": IndexGridStrategySpec(
        symbol="159866.SZ",
        name="日经ETF",
        rise_trigger_pct=0.03,
        sell_pullback_pct=0.008,
        decline_trigger_pct=0.03,
        buy_rebound_pct=0.008,
    ),
}


def resolve_index_grid_spec(symbol: str) -> IndexGridStrategySpec:
    """按标的代码返回固定策略参数。"""
    normalized = symbol.strip().upper()
    spec = INDEX_GRID_SPECS.get(normalized)
    if spec is None:
        supported = ", ".join(sorted(INDEX_GRID_SPECS))
        raise ValueError(f"minute_index_grid_retrace 仅支持以下标的: {supported}；当前为 {normalized}")
    return spec


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
    if pd.isna(median_delta):
        return 252.0
    if median_delta >= pd.Timedelta(days=1):
        return 252.0
    day_fraction = max(median_delta / pd.Timedelta(days=1), 1e-9)
    return 252.0 / float(day_fraction)


def _affordable_units(cash_budget: float, close_price: float, lot_size: int, execution: ExecutionConfig) -> int:
    execution_price = _buy_execution_price(close_price, execution)
    unit_cash = execution_price * (1 + max(execution.commission_bps, 0.0) / 10000)
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
    execution_price = _buy_execution_price(entry_price, execution)
    entry_cost = _transaction_cost(execution_price, buy_hold_units, execution)
    buy_hold_cash_used = buy_hold_units * execution_price + entry_cost
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


def _fifo_close_grid_lots(
    grid_lots: list[dict[str, float | int]],
    sell_units: int,
    execution_price: float,
    exit_cost: float,
) -> tuple[float, float]:
    """按 FIFO 结转网格仓已实现利润。"""
    remaining = sell_units
    realized_profit = 0.0
    realized_cost_basis = 0.0
    prorated_exit_cost = exit_cost / sell_units if sell_units > 0 else 0.0

    while remaining > 0 and grid_lots:
        lot = grid_lots[0]
        lot_units = int(lot["units"])
        matched_units = min(remaining, lot_units)
        entry_price = float(lot["entry_price"])
        entry_cost = float(lot["entry_cost"])
        lot_entry_cost_per_unit = entry_cost / lot_units if lot_units > 0 else 0.0
        matched_entry_cost = lot_entry_cost_per_unit * matched_units
        matched_exit_cost = prorated_exit_cost * matched_units
        realized_profit += matched_units * (execution_price - entry_price) - matched_entry_cost - matched_exit_cost
        realized_cost_basis += matched_units * entry_price + matched_entry_cost

        remaining -= matched_units
        lot_units -= matched_units
        if lot_units == 0:
            grid_lots.pop(0)
        else:
            lot["units"] = lot_units
            lot["entry_cost"] = lot_entry_cost_per_unit * lot_units

    return realized_profit, realized_cost_basis


def _grid_cost_basis(grid_lots: list[dict[str, float | int]]) -> float:
    return sum(int(lot["units"]) * float(lot["entry_price"]) + float(lot["entry_cost"]) for lot in grid_lots)


def _build_equity_curve(history_rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(history_rows)
    if frame.empty:
        return pd.DataFrame()
    frame["Date"] = pd.to_datetime(frame["Date"])
    curve = frame.set_index("Date")[["Equity"]].copy()
    curve["PeakEquity"] = curve["Equity"].cummax()
    curve["DrawdownPct"] = np.where(curve["PeakEquity"] > 0, curve["Equity"] / curve["PeakEquity"] - 1, 0.0)
    return curve


def run_index_grid_backtest(
    data: pd.DataFrame,
    scenario_name: str,
    symbol: str,
    market: str,
    lot_size: int,
    lot_size_source: str,
    execution_config: ExecutionConfig | None = None,
) -> dict[str, object]:
    """运行单次指数底仓 + 动态回落/反弹网格回测。"""
    if data.empty:
        raise ValueError("行情数据为空，无法执行指数回落网格回测。")

    execution = execution_config or build_execution_config("research")
    spec = resolve_index_grid_spec(symbol)
    total_capital = float(spec.total_capital)
    first_close = float(data.iloc[0]["Close"])
    base_cash_budget = total_capital * spec.base_position_ratio
    grid_cash_budget = total_capital * spec.grid_trade_ratio

    base_units = _affordable_units(base_cash_budget, first_close, lot_size, execution)
    if base_units <= 0:
        raise ValueError(
            f"底仓预算不足以买入 1 手: symbol={symbol} lot_size={lot_size} price={first_close:.2f}"
        )
    grid_units_per_trade = _affordable_units(grid_cash_budget, first_close, lot_size, execution)
    if grid_units_per_trade <= 0:
        raise ValueError(
            f"单次网格预算不足以买入 1 手: symbol={symbol} lot_size={lot_size} price={first_close:.2f}"
        )

    base_execution_price = _buy_execution_price(first_close, execution)
    base_entry_cost = _transaction_cost(base_execution_price, base_units, execution)
    cash = total_capital - (base_units * base_execution_price + base_entry_cost)
    if cash < 0:
        raise ValueError("初始底仓买入后现金为负，请检查资金或交易单位配置。")

    base_market_value = base_units * first_close
    reference_price = base_execution_price
    armed_side = ""
    extreme_price = reference_price
    peak_equity = cash + base_market_value
    max_drawdown_pct = 0.0
    max_position_ratio_used = base_market_value / total_capital if total_capital else 0.0
    realized_grid_profit = 0.0
    transaction_cost_total = base_entry_cost
    slippage_cost_total = base_units * max(base_execution_price - first_close, 0.0)
    grid_trade_count = 0
    grid_buy_count = 0
    grid_sell_count = 0
    stop_loss_events = 0
    risk_skip_events = 0

    grid_lots: list[dict[str, float | int]] = []
    trade_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = [
        {
            "Date": format_timestamp(data.index[0]),
            "EventType": "base_buy",
            "Level": 0,
            "Price": first_close,
            "ExecutionPrice": base_execution_price,
            "Units": base_units,
            "CashFlow": base_units * base_execution_price + base_entry_cost,
            "TransactionCost": base_entry_cost,
            "SlippageCost": base_units * max(base_execution_price - first_close, 0.0),
            "Note": "首根 K 线建立长期底仓",
        }
    ]
    history_rows: list[dict[str, object]] = []

    for index, (timestamp, row) in enumerate(data.iterrows()):
        close_price = float(row["Close"])
        if index == 0:
            pass
        else:
            if armed_side == "":
                if close_price <= reference_price * (1 - spec.decline_trigger_pct):
                    armed_side = "buy"
                    extreme_price = close_price
                elif close_price >= reference_price * (1 + spec.rise_trigger_pct):
                    armed_side = "sell"
                    extreme_price = close_price
            elif armed_side == "buy":
                extreme_price = min(extreme_price, close_price)
                if close_price >= extreme_price * (1 + spec.buy_rebound_pct):
                    execution_price = _buy_execution_price(close_price, execution)
                    units = _affordable_units(min(grid_cash_budget, cash), close_price, lot_size, execution)
                    if units > 0:
                        entry_cost = _transaction_cost(execution_price, units, execution)
                        cash_required = units * execution_price + entry_cost
                        if cash_required <= cash:
                            cash -= cash_required
                            grid_lots.append(
                                {
                                    "units": units,
                                    "entry_price": execution_price,
                                    "entry_cost": entry_cost,
                                    "entry_time": timestamp,
                                }
                            )
                            transaction_cost_total += entry_cost
                            slippage_cost_total += units * max(execution_price - close_price, 0.0)
                            grid_trade_count += 1
                            grid_buy_count += 1
                            event_rows.append(
                                {
                                    "Date": format_timestamp(timestamp),
                                    "EventType": "retrace_buy",
                                    "Level": 1,
                                    "Price": close_price,
                                    "ExecutionPrice": execution_price,
                                    "Units": units,
                                    "CashFlow": cash_required,
                                    "TransactionCost": entry_cost,
                                    "SlippageCost": units * max(execution_price - close_price, 0.0),
                                    "Note": "下跌触发后从局部低点反弹，执行一笔网格买入",
                                }
                            )
                            reference_price = execution_price
                        else:
                            risk_skip_events += 1
                    else:
                        risk_skip_events += 1
                    armed_side = ""
                    extreme_price = reference_price
            elif armed_side == "sell":
                extreme_price = max(extreme_price, close_price)
                if close_price <= extreme_price * (1 - spec.sell_pullback_pct):
                    open_grid_units = sum(int(lot["units"]) for lot in grid_lots)
                    units = min(grid_units_per_trade, open_grid_units)
                    if units > 0:
                        execution_price = _sell_execution_price(close_price, execution)
                        exit_cost = _transaction_cost(execution_price, units, execution)
                        realized_profit, realized_cost_basis = _fifo_close_grid_lots(
                            grid_lots=grid_lots,
                            sell_units=units,
                            execution_price=execution_price,
                            exit_cost=exit_cost,
                        )
                        cash += units * execution_price - exit_cost
                        realized_grid_profit += realized_profit
                        transaction_cost_total += exit_cost
                        slippage_cost_total += units * max(close_price - execution_price, 0.0)
                        grid_trade_count += 1
                        grid_sell_count += 1
                        trade_rows.append(
                            {
                                "EntryTime": "",
                                "ExitTime": format_timestamp(timestamp),
                                "Duration": "",
                                "EntryPrice": realized_cost_basis / units if units > 0 else 0.0,
                                "ExitPrice": execution_price,
                                "Size": units,
                                "PnL": realized_profit,
                                "ReturnPct": (execution_price / (realized_cost_basis / units) - 1) if realized_cost_basis > 0 else 0.0,
                                "Tag": "retrace_grid",
                            }
                        )
                        event_rows.append(
                            {
                                "Date": format_timestamp(timestamp),
                                "EventType": "retrace_sell",
                                "Level": 1,
                                "Price": close_price,
                                "ExecutionPrice": execution_price,
                                "Units": units,
                                "CashFlow": units * execution_price - exit_cost,
                                "TransactionCost": exit_cost,
                                "SlippageCost": units * max(close_price - execution_price, 0.0),
                                "Note": "上涨触发后从局部高点回落，卖出一笔网格仓",
                            }
                        )
                        reference_price = execution_price
                    else:
                        risk_skip_events += 1
                    armed_side = ""
                    extreme_price = reference_price

        grid_units = sum(int(lot["units"]) for lot in grid_lots)
        total_units = base_units + grid_units
        base_cost_basis = base_units * base_execution_price + base_entry_cost
        grid_cost_basis = _grid_cost_basis(grid_lots)
        base_unrealized_pnl = base_units * (close_price - base_execution_price)
        grid_unrealized_pnl = sum(
            int(lot["units"]) * (close_price - float(lot["entry_price"])) - float(lot["entry_cost"])
            for lot in grid_lots
        )
        market_value = total_units * close_price
        equity = cash + market_value
        peak_equity = max(peak_equity, equity)
        drawdown_pct = (equity / peak_equity - 1) * 100 if peak_equity else 0.0
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)
        position_ratio = market_value / total_capital if total_capital else 0.0
        max_position_ratio_used = max(max_position_ratio_used, position_ratio)
        effective_cost = (base_cost_basis + grid_cost_basis - realized_grid_profit) / total_units if total_units else 0.0

        history_rows.append(
            {
                "Date": format_timestamp(timestamp),
                "Close": close_price,
                "PeakClose": max(reference_price, close_price),
                "PositionUnits": total_units,
                "BasePositionUnits": base_units,
                "GridPositionUnits": grid_units,
                "OpenGridLevels": len(grid_lots),
                "GrossCost": base_cost_basis + grid_cost_basis,
                "BaseCost": base_cost_basis,
                "GridCost": grid_cost_basis,
                "RealizedGridProfit": realized_grid_profit,
                "ClosedGridNetProfit": realized_grid_profit,
                "UnrealizedPnl": base_unrealized_pnl + grid_unrealized_pnl,
                "BaseUnrealizedPnl": base_unrealized_pnl,
                "GridUnrealizedPnl": grid_unrealized_pnl,
                "EffectiveCost": effective_cost,
                "CostReductionPct": 0.0,
                "MarketValue": market_value,
                "OpenGridMarketValue": grid_units * close_price,
                "PositionRatioPct": position_ratio * 100,
                "MaxCapitalUsedPct": max_position_ratio_used * 100,
                "TransactionCostCumulative": transaction_cost_total,
                "SlippageCostCumulative": slippage_cost_total,
                "MaxPositionRatioUsedPct": max_position_ratio_used * 100,
                "Equity": equity,
                "ReferencePrice": reference_price,
                "ArmedSide": armed_side,
                "ExtremePrice": extreme_price,
            }
        )

    history = pd.DataFrame(history_rows)
    events = pd.DataFrame(event_rows)
    trades = pd.DataFrame(trade_rows)
    equity_curve = _build_equity_curve(history_rows)
    final_equity = float(history.iloc[-1]["Equity"]) if not history.empty else total_capital
    return_pct = (final_equity / total_capital - 1) * 100 if total_capital else 0.0
    annual_factor = _annualization_factor(data.index)
    annual_return_pct = ((final_equity / total_capital) ** (annual_factor / max(len(data), 1)) - 1) * 100 if total_capital else 0.0
    benchmark_metrics = _build_benchmark_metrics(data, total_capital, lot_size, execution)
    latest_snapshot = history.iloc[-1].to_dict() if not history.empty else {}
    open_grid_units = int(latest_snapshot.get("GridPositionUnits", 0))
    open_grid_market_value = float(latest_snapshot.get("OpenGridMarketValue", 0.0))
    strategy_vs_buy_hold = final_equity - float(benchmark_metrics["BuyHoldFinalEquity"])

    summary = {
        "Symbol": spec.symbol,
        "Name": spec.name,
        "Market": market,
        "Scenario": scenario_name,
        "StrategyKind": "minute_index_grid_retrace",
        "StrategyName": "指数回落反弹网格",
        "SignalFamily": "index_grid_retrace",
        "StartDate": format_timestamp(data.index.min()),
        "EndDate": format_timestamp(data.index.max()),
        "PeakDate": format_timestamp(data["Close"].idxmax()),
        "PeakPrice": float(data["Close"].max()),
        "EntryDate": format_timestamp(data.index.min()),
        "EntryPrice": first_close,
        "AnchorDate": format_timestamp(data.index.min()),
        "AnchorPrice": first_close,
        "LotSize": lot_size,
        "LotSizeSource": lot_size_source,
        "BaseUnits": base_units,
        "BasePositionUnits": base_units,
        "GridUnitsPerLevel": grid_units_per_trade,
        "GridUnitsPerTrade": grid_units_per_trade,
        "GridSpacingPct": spec.decline_trigger_pct * 100,
        "GridCount": 0,
        "TakeProfitPct": spec.sell_pullback_pct * 100,
        "RiseTriggerPct": spec.rise_trigger_pct * 100,
        "SellPullbackPct": spec.sell_pullback_pct * 100,
        "DeclineTriggerPct": spec.decline_trigger_pct * 100,
        "BuyReboundPct": spec.buy_rebound_pct * 100,
        "BasePositionRatioPct": spec.base_position_ratio * 100,
        "GridTradeRatioPct": spec.grid_trade_ratio * 100,
        "ReturnPct": return_pct,
        "NetReturnPct": return_pct,
        "NetPnl": final_equity - total_capital,
        "AnnualReturnPct": annual_return_pct,
        "MaxDrawdownPct": abs(max_drawdown_pct),
        "ClosedTrades": int(len(trades)),
        "WinRatePct": float((trades["PnL"] > 0).mean() * 100) if not trades.empty else 0.0,
        "FinalEquity": final_equity,
        "TotalCapital": total_capital,
        "PositionUnits": int(latest_snapshot.get("PositionUnits", 0)),
        "GridPositionUnits": open_grid_units,
        "EffectiveCost": float(latest_snapshot.get("EffectiveCost", 0.0)),
        "CostReductionPct": 0.0,
        "RealizedGridProfit": realized_grid_profit,
        "GridRealizedProfit": realized_grid_profit,
        "ClosedGridNetProfit": realized_grid_profit,
        "ClosedGridReturnPct": realized_grid_profit / total_capital * 100 if total_capital else 0.0,
        "UnrealizedPnl": float(latest_snapshot.get("UnrealizedPnl", 0.0)),
        "BaseUnrealizedPnl": float(latest_snapshot.get("BaseUnrealizedPnl", 0.0)),
        "GridUnrealizedPnl": float(latest_snapshot.get("GridUnrealizedPnl", 0.0)),
        "OpenGridMarketValue": open_grid_market_value,
        "MaxCapitalUsedPct": float(latest_snapshot.get("MaxCapitalUsedPct", 0.0)),
        "GridCyclesCompleted": grid_sell_count,
        "GridTradeCount": grid_trade_count,
        "GridBuyCount": grid_buy_count,
        "GridSellCount": grid_sell_count,
        "ExecutionProfile": execution.profile,
        "CommissionBps": execution.commission_bps,
        "SlippageBps": execution.slippage_bps,
        "TransactionCost": transaction_cost_total,
        "SlippageCost": slippage_cost_total,
        "MaxPositionRatio": execution.max_position_ratio * 100,
        "MaxPositionRatioUsed": max_position_ratio_used * 100,
        "StopLossPct": 0.0,
        "CooldownBars": 0,
        "StopLossEvents": stop_loss_events,
        "RiskSkipEvents": risk_skip_events,
        "GridMode": "base_plus_dynamic",
        "LeftSidePolicy": "hold",
        "RequestedLeftSidePolicy": "hold",
        "PrimaryLeftSidePolicy": "hold",
        "ForceExitLossPct": 0.0,
        "ForceExitTriggered": False,
        "ForceExitEvents": 0,
        "ForceExitDate": "",
        "ForceExitLossRatioPct": 0.0,
        "Benchmark": execution.benchmark,
        **benchmark_metrics,
        "GridVsCashIdle": final_equity - float(benchmark_metrics["CashIdleFinalEquity"]),
        "GridVsBaseOnly": final_equity - float(benchmark_metrics["BaseOnlyFinalEquity"]),
        "GridVsBuyHold": strategy_vs_buy_hold,
        "StrategyVsBuyHold": strategy_vs_buy_hold,
        "OutperformBuyHold": strategy_vs_buy_hold > 0,
        "Score": compute_score(return_pct, abs(max_drawdown_pct), realized_grid_profit / total_capital * 100 if total_capital else 0.0),
        "TriggeredEntry": grid_buy_count > 0,
        "TriggeredGridEntry": grid_buy_count > 0,
    }

    return {
        "summary": summary,
        "history": history,
        "events": events,
        "trades": trades,
        "equity_curve": equity_curve,
        "stats": summary,
    }
