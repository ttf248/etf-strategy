from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
from backtesting import Backtest, Strategy


TOTAL_CAPITAL = 200000.0
INITIAL_CASH_RATIO = 0.5
ENTRY_DRAWDOWN_RATIO = 0.10


@dataclass
class DeclineWindow:
    """样本内下跌窗口定位结果。"""

    peak_date: str
    peak_price: float
    entry_date: str
    entry_price: float
    sample_start: str
    sample_end: str
    validation_start: str


class XiaomiGridStrategy(Strategy):
    """小米港股左侧建仓 + 双向网格策略。"""

    total_capital = TOTAL_CAPITAL
    initial_cash_ratio = INITIAL_CASH_RATIO
    entry_drawdown_pct = ENTRY_DRAWDOWN_RATIO
    grid_spacing_pct = 0.05
    grid_count = 5
    take_profit_pct = 0.05

    def init(self) -> None:
        first_close = float(self.data.Close[0])
        first_date = pd.Timestamp(self.data.index[0])

        self.high_water_mark = first_close
        self.peak_date = first_date
        self.entry_trigger_price = first_close * (1 - self.entry_drawdown_pct)

        self.base_entered = False
        self.base_entry_date: pd.Timestamp | None = None
        self.base_entry_price = 0.0
        self.base_units = 0
        self.base_cash_budget = self.total_capital * self.initial_cash_ratio
        self.reserve_cash_budget = self.total_capital * (1 - self.initial_cash_ratio)

        self.grid_levels: list[dict[str, float | int | bool]] = []
        self.realized_grid_profit = 0.0
        self.grid_cycles_completed = 0
        self.event_log: list[dict[str, object]] = []
        self.history: list[dict[str, object]] = []

    def next(self) -> None:
        current_date = pd.Timestamp(self.data.index[-1])
        close_price = float(self.data.Close[-1])

        if not self.base_entered and close_price > self.high_water_mark:
            self.high_water_mark = close_price
            self.peak_date = current_date

        self.entry_trigger_price = self.high_water_mark * (1 - self.entry_drawdown_pct)

        if not self.base_entered and close_price <= self.entry_trigger_price:
            self._enter_base_position(current_date, close_price)

        if self.base_entered:
            self._handle_grid_exits(current_date, close_price)
            self._handle_grid_entries(current_date, close_price)

        self._record_snapshot(current_date, close_price)

    def _enter_base_position(self, current_date: pd.Timestamp, close_price: float) -> None:
        units = max(int(self.base_cash_budget / close_price), 1)
        self.buy(size=units, tag="base")

        self.base_entered = True
        self.base_entry_date = current_date
        self.base_entry_price = close_price
        self.base_units = units
        self.grid_levels = self._build_grid_levels(close_price)

        self.event_log.append(
            {
                "Date": current_date.strftime("%Y-%m-%d"),
                "EventType": "base_buy",
                "Level": 0,
                "Price": close_price,
                "Units": units,
                "CashFlow": units * close_price,
                "Note": "高点回撤 10% 后初始建仓",
            }
        )

    def _build_grid_levels(self, base_price: float) -> list[dict[str, float | int | bool]]:
        per_level_budget = self.reserve_cash_budget / self.grid_count
        levels: list[dict[str, float | int | bool]] = []

        for level_index in range(1, self.grid_count + 1):
            entry_threshold = base_price * (1 - self.grid_spacing_pct * level_index)
            units = max(int(per_level_budget / entry_threshold), 1)
            levels.append(
                {
                    "level": level_index,
                    "entry_threshold": entry_threshold,
                    "units": units,
                    "active": False,
                    "entry_price": 0.0,
                }
            )
        return levels

    def _handle_grid_entries(self, current_date: pd.Timestamp, close_price: float) -> None:
        for level in self.grid_levels:
            if level["active"]:
                continue
            if close_price > float(level["entry_threshold"]):
                continue

            units = int(level["units"])
            tag = self._grid_tag(int(level["level"]))
            self.buy(size=units, tag=tag)
            level["active"] = True
            level["entry_price"] = close_price

            self.event_log.append(
                {
                    "Date": current_date.strftime("%Y-%m-%d"),
                    "EventType": "grid_buy",
                    "Level": int(level["level"]),
                    "Price": close_price,
                    "Units": units,
                    "CashFlow": units * close_price,
                    "Note": "触发下行网格买入",
                }
            )

    def _handle_grid_exits(self, current_date: pd.Timestamp, close_price: float) -> None:
        for level in self.grid_levels:
            if not level["active"]:
                continue

            entry_price = float(level["entry_price"])
            take_profit_price = entry_price * (1 + self.take_profit_pct)
            if close_price < take_profit_price:
                continue

            active_trade = next(
                (trade for trade in self.trades if trade.tag == self._grid_tag(int(level["level"]))),
                None,
            )
            if active_trade is None:
                continue

            units = int(level["units"])
            active_trade.close()
            level["active"] = False
            level["entry_price"] = 0.0
            self.realized_grid_profit += (close_price - entry_price) * units
            self.grid_cycles_completed += 1

            self.event_log.append(
                {
                    "Date": current_date.strftime("%Y-%m-%d"),
                    "EventType": "grid_sell",
                    "Level": int(level["level"]),
                    "Price": close_price,
                    "Units": units,
                    "CashFlow": units * close_price,
                    "Note": "达到网格止盈价后卖出本层仓位",
                }
            )

    def _record_snapshot(self, current_date: pd.Timestamp, close_price: float) -> None:
        open_grid_cost = 0.0
        open_grid_units = 0
        open_grid_levels = 0

        for level in self.grid_levels:
            if not level["active"]:
                continue
            open_grid_levels += 1
            units = int(level["units"])
            open_grid_units += units
            open_grid_cost += units * float(level["entry_price"])

        total_units = self.base_units + open_grid_units
        gross_cost = self.base_units * self.base_entry_price + open_grid_cost
        effective_cost_basis = gross_cost - self.realized_grid_profit
        effective_cost = effective_cost_basis / total_units if total_units else 0.0
        market_value = total_units * close_price
        cost_reduction_pct = (
            (self.base_entry_price - effective_cost) / self.base_entry_price * 100
            if self.base_entered and total_units
            else 0.0
        )

        self.history.append(
            {
                "Date": current_date.strftime("%Y-%m-%d"),
                "Close": close_price,
                "PeakClose": self.high_water_mark,
                "EntryTriggerPrice": self.entry_trigger_price,
                "PositionUnits": total_units,
                "OpenGridLevels": open_grid_levels,
                "GrossCost": gross_cost,
                "RealizedGridProfit": self.realized_grid_profit,
                "EffectiveCost": effective_cost,
                "CostReductionPct": cost_reduction_pct,
                "MarketValue": market_value,
            }
        )

    @staticmethod
    def _grid_tag(level: int) -> str:
        return f"grid_{level}"


def load_price_frame(data_path: str | Path) -> pd.DataFrame:
    """加载标准化 CSV 并转成 backtesting 需要的结构。"""
    frame = pd.read_csv(data_path, parse_dates=["Date"])
    required_columns = {"Date", "Open", "High", "Low", "Close", "Volume"}
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise ValueError(f"标准化 CSV 缺少字段: {sorted(missing_columns)}")

    frame = frame.sort_values("Date").set_index("Date")
    frame = frame.loc[:, ["Open", "High", "Low", "Close", "Volume"]]
    frame = frame.astype(
        {
            "Open": "float64",
            "High": "float64",
            "Low": "float64",
            "Close": "float64",
            "Volume": "int64",
        }
    )
    return frame


def locate_recent_decline_window(
    data: pd.DataFrame,
    validation_start: str = "2026-01-01",
    lookback_days: int = 120,
    entry_drawdown_pct: float = ENTRY_DRAWDOWN_RATIO,
) -> DeclineWindow:
    """定位最近一轮满足 10% 回撤触发条件的样本内区间。"""
    validation_timestamp = pd.Timestamp(validation_start)
    sample_end_ts = validation_timestamp - pd.Timedelta(days=1)
    lookback_candidates = [lookback_days, 365, 730]

    for days in lookback_candidates:
        window_start_ts = sample_end_ts - pd.Timedelta(days=days)
        window = data.loc[window_start_ts:sample_end_ts]
        if window.empty:
            continue

        peak_date = window["Close"].idxmax()
        peak_price = float(window.loc[peak_date, "Close"])
        after_peak = window.loc[peak_date:]
        entry_threshold = peak_price * (1 - entry_drawdown_pct)
        entry_rows = after_peak[after_peak["Close"] <= entry_threshold]
        if entry_rows.empty:
            continue

        entry_date = entry_rows.index[0]
        entry_price = float(entry_rows.iloc[0]["Close"])
        return DeclineWindow(
            peak_date=peak_date.strftime("%Y-%m-%d"),
            peak_price=peak_price,
            entry_date=entry_date.strftime("%Y-%m-%d"),
            entry_price=entry_price,
            sample_start=peak_date.strftime("%Y-%m-%d"),
            sample_end=sample_end_ts.strftime("%Y-%m-%d"),
            validation_start=validation_timestamp.strftime("%Y-%m-%d"),
        )

    raise ValueError("未能在样本内区间定位到满足 10% 回撤条件的下跌窗口。")


def _compute_score(return_pct: float, max_drawdown_pct: float, cost_reduction_pct: float) -> float:
    """收益/回撤综合评分。"""
    return return_pct - abs(max_drawdown_pct) * 0.7 + cost_reduction_pct * 0.5


def _history_to_frame(history: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(history) if history else pd.DataFrame()


def _events_to_frame(events: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(events) if events else pd.DataFrame()


def run_grid_backtest(
    data: pd.DataFrame,
    scenario_name: str,
    grid_spacing_pct: float,
    grid_count: int,
    take_profit_pct: float,
    total_capital: float = TOTAL_CAPITAL,
) -> dict[str, object]:
    """运行单次网格回测。"""
    backtest = Backtest(
        data,
        XiaomiGridStrategy,
        cash=total_capital,
        commission=0.0,
        trade_on_close=True,
        exclusive_orders=False,
        finalize_trades=True,
    )
    stats = backtest.run(
        total_capital=total_capital,
        initial_cash_ratio=INITIAL_CASH_RATIO,
        entry_drawdown_pct=ENTRY_DRAWDOWN_RATIO,
        grid_spacing_pct=grid_spacing_pct,
        grid_count=grid_count,
        take_profit_pct=take_profit_pct,
    )
    strategy: XiaomiGridStrategy = stats["_strategy"]
    history = _history_to_frame(strategy.history)
    events = _events_to_frame(strategy.event_log)

    latest_snapshot = history.iloc[-1].to_dict() if not history.empty else {}
    peak_date = strategy.peak_date.strftime("%Y-%m-%d")
    base_entry_date = strategy.base_entry_date.strftime("%Y-%m-%d") if strategy.base_entry_date else ""
    max_drawdown_pct = abs(float(stats["Max. Drawdown [%]"]))
    return_pct = float(stats["Return [%]"])
    cost_reduction_pct = float(latest_snapshot.get("CostReductionPct", 0.0))

    summary = {
        "Scenario": scenario_name,
        "StartDate": data.index.min().strftime("%Y-%m-%d"),
        "EndDate": data.index.max().strftime("%Y-%m-%d"),
        "PeakDate": peak_date,
        "PeakPrice": strategy.high_water_mark,
        "EntryDate": base_entry_date,
        "EntryPrice": strategy.base_entry_price,
        "GridSpacingPct": grid_spacing_pct * 100,
        "GridCount": grid_count,
        "TakeProfitPct": take_profit_pct * 100,
        "ReturnPct": return_pct,
        "AnnualReturnPct": float(stats["Return (Ann.) [%]"]),
        "MaxDrawdownPct": max_drawdown_pct,
        "ClosedTrades": int(stats["# Trades"]),
        "WinRatePct": float(stats["Win Rate [%]"]) if pd.notna(stats["Win Rate [%]"]) else 0.0,
        "FinalEquity": float(stats["Equity Final [$]"]),
        "PositionUnits": int(latest_snapshot.get("PositionUnits", 0)),
        "EffectiveCost": float(latest_snapshot.get("EffectiveCost", 0.0)),
        "CostReductionPct": cost_reduction_pct,
        "RealizedGridProfit": strategy.realized_grid_profit,
        "GridCyclesCompleted": strategy.grid_cycles_completed,
        "Score": _compute_score(return_pct, max_drawdown_pct, cost_reduction_pct),
        "TriggeredEntry": bool(strategy.base_entered),
    }

    trades = stats["_trades"].copy()
    equity_curve = stats["_equity_curve"].copy()
    return {
        "summary": summary,
        "history": history,
        "events": events,
        "trades": trades,
        "equity_curve": equity_curve,
        "stats": stats,
    }


def optimize_grid_parameters(
    data: pd.DataFrame,
    spacings: list[float],
    grid_counts: list[int],
    take_profits: list[float],
    scenario_name: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """对网格参数做穷举搜索并返回最优结果。"""
    rows: list[dict[str, object]] = []
    best_run: dict[str, object] | None = None
    best_score = float("-inf")

    for spacing in spacings:
        for grid_count in grid_counts:
            for take_profit in take_profits:
                run_result = run_grid_backtest(
                    data=data,
                    scenario_name=scenario_name,
                    grid_spacing_pct=spacing,
                    grid_count=grid_count,
                    take_profit_pct=take_profit,
                )
                rows.append(run_result["summary"])
                score = float(run_result["summary"]["Score"])
                if score > best_score:
                    best_score = score
                    best_run = run_result

    results = pd.DataFrame(rows).sort_values(["Score", "ReturnPct"], ascending=[False, False]).reset_index(drop=True)
    if best_run is None:
        raise ValueError("参数搜索未产生任何结果。")
    return results, best_run


def split_in_sample_and_validation(
    data: pd.DataFrame,
    validation_start: str = "2026-01-01",
    lookback_days: int = 120,
) -> tuple[DeclineWindow, pd.DataFrame, pd.DataFrame]:
    """拆分样本内和样本外数据。"""
    decline_window = locate_recent_decline_window(
        data,
        validation_start=validation_start,
        lookback_days=lookback_days,
    )
    in_sample = data.loc[decline_window.sample_start:decline_window.sample_end].copy()
    validation = data.loc[decline_window.validation_start:].copy()
    if validation.empty:
        raise ValueError("样本外区间为空，无法验证 2026 表现。")
    return decline_window, in_sample, validation


def save_run_artifacts(output_dir: str | Path, prefix: str, run_result: dict[str, object]) -> dict[str, Path]:
    """保存单次回测产生的明细文件。"""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    summary_path = target_dir / f"{prefix}_summary.csv"
    history_path = target_dir / f"{prefix}_history.csv"
    events_path = target_dir / f"{prefix}_events.csv"
    trades_path = target_dir / f"{prefix}_trades.csv"
    equity_path = target_dir / f"{prefix}_equity_curve.csv"

    pd.DataFrame([run_result["summary"]]).to_csv(summary_path, index=False, encoding="utf-8-sig")
    run_result["history"].to_csv(history_path, index=False, encoding="utf-8-sig")
    run_result["events"].to_csv(events_path, index=False, encoding="utf-8-sig")
    run_result["trades"].to_csv(trades_path, index=False, encoding="utf-8-sig")
    run_result["equity_curve"].to_csv(equity_path, index=True, encoding="utf-8-sig")

    return {
        "summary": summary_path,
        "history": history_path,
        "events": events_path,
        "trades": trades_path,
        "equity_curve": equity_path,
    }


def save_decline_window(output_dir: str | Path, decline_window: DeclineWindow) -> Path:
    """保存样本内区间定位结果。"""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    window_path = target / "in_sample_window.csv"
    pd.DataFrame([asdict(decline_window)]).to_csv(window_path, index=False, encoding="utf-8-sig")
    return window_path
