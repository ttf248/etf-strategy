from __future__ import annotations
"""网格策略核心实现。

这里同时承担三类职责：

1. 定义 backtesting.py 直接调用的策略类。
2. 提供日线 / 分钟线样本切分和评分规则。
3. 对外暴露单次回测、参数搜索和产物保存能力。

之所以没有继续拆更细，是因为这些逻辑共享同一套口径：
- 样本起点直接建底仓
- 底仓和网格都按固定股数执行
- 成本摊薄、网格已实现收益和总账户收益需要使用同一批中间状态计算
"""

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy

from etf_strategy.settings import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_VALIDATION_RATIO,
    DEFAULT_VALIDATION_START,
    DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    DEFAULT_WALK_FORWARD_WINDOW_COUNT,
)


TOTAL_CAPITAL = 200000.0
INITIAL_CASH_RATIO = 0.5


@dataclass
class DeclineWindow:
    """样本窗口摘要。"""

    peak_date: str
    peak_price: float
    entry_date: str
    entry_price: float
    sample_start: str
    sample_end: str
    validation_start: str


def format_timestamp(timestamp: pd.Timestamp) -> str:
    """按数据粒度输出日期或日期时间。"""
    normalized = pd.Timestamp(timestamp)
    if normalized.hour or normalized.minute or normalized.second:
        return normalized.strftime("%Y-%m-%d %H:%M:%S")
    return normalized.strftime("%Y-%m-%d")


class FixedUnitGridStrategy(Strategy):
    """样本起点建仓 + 双向固定股数网格策略。"""

    total_capital = TOTAL_CAPITAL
    initial_cash_ratio = INITIAL_CASH_RATIO
    grid_spacing_pct = 0.05
    grid_count = 5
    take_profit_pct = 0.05
    lot_size = 1

    def init(self) -> None:
        """在样本第一根 K 线上完成底仓初始化。

        backtesting.py 会在 `init()` 之后立刻开始逐 bar 调 `next()`，
        因此底仓、网格层级和首笔快照都必须在这里准备好。
        """
        first_close = float(self.data.Close[0])
        first_date = pd.Timestamp(self.data.index[0])

        self.high_water_mark = first_close
        self.peak_date = first_date

        # 底仓与网格预留资金在整个样本期内固定，后续只改变实际持仓股数。
        self.base_cash_budget = self.total_capital * self.initial_cash_ratio
        self.reserve_cash_budget = self.total_capital * (1 - self.initial_cash_ratio)

        self.base_entered = False
        self.base_entry_date: pd.Timestamp | None = None
        self.base_entry_price = 0.0
        self.base_units = 0
        self.grid_units_per_level = 0
        self.grid_levels: list[dict[str, float | int | bool]] = []
        self.realized_grid_profit = 0.0
        self.grid_cycles_completed = 0
        self.event_log: list[dict[str, object]] = []
        self.history: list[dict[str, object]] = []
        self._enter_base_position(first_date, first_close)
        self._record_snapshot(first_date, first_close)

    def next(self) -> None:
        """按收盘价驱动网格开平仓，并记录账户状态快照。"""
        current_date = pd.Timestamp(self.data.index[-1])
        close_price = float(self.data.Close[-1])

        if close_price > self.high_water_mark:
            self.high_water_mark = close_price
            self.peak_date = current_date

        # 先处理止盈，再处理新的买入，避免同一根 K 线既卖又立刻回补导致口径混乱。
        self._handle_grid_exits(current_date, close_price)
        self._handle_grid_entries(current_date, close_price)

        self._record_snapshot(current_date, close_price)

    def _enter_base_position(self, current_date: pd.Timestamp, close_price: float) -> None:
        """建立底仓，并据此生成整套网格价位。"""
        units = self._build_base_units(close_price)
        self.buy(size=units, tag="base")

        self.base_entered = True
        self.base_entry_date = current_date
        self.base_entry_price = close_price
        self.base_units = units
        self.grid_units_per_level = self._build_grid_units_per_level(close_price)
        self.grid_levels = self._build_grid_levels(close_price)

        self.event_log.append(
            {
                "Date": format_timestamp(current_date),
                "EventType": "base_buy",
                "Level": 0,
                "Price": close_price,
                "Units": units,
                "CashFlow": units * close_price,
                "Note": "样本开始时初始建仓",
            }
        )

    def _build_base_units(self, close_price: float) -> int:
        """根据底仓预算和最小交易单位，向下取整出可交易股数。"""
        raw_units = int(self.base_cash_budget / close_price)
        units = self._round_down_to_lot(raw_units)
        if units <= 0:
            raise ValueError(
                f"初始资金不足以买入 1 手，无法建底仓: lot_size={self.lot_size}, price={close_price:.2f}"
            )
        return units

    def _build_grid_units_per_level(self, base_price: float) -> int:
        """把单层预算折算成统一的固定股数。

        这里故意用样本起点价格而不是逐层触发价来估算，
        目的是让所有网格层保持相同仓位大小，避免回测重新退化成“每层不同金额”。
        """
        per_level_budget = self.reserve_cash_budget / self.grid_count
        raw_units = int(per_level_budget / base_price)
        units = self._round_down_to_lot(raw_units)
        if units <= 0:
            raise ValueError(
                f"单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size={self.lot_size}, price={base_price:.2f}"
            )
        return units

    def _build_grid_levels(self, base_price: float) -> list[dict[str, float | int | bool]]:
        """根据底仓价格预生成所有网格层。

        这里仅记录未来触发阈值和统一股数，不实际下单；
        是否进场由后续 `next()` 中的价格触发决定。
        """
        levels: list[dict[str, float | int | bool]] = []

        for level_index in range(1, self.grid_count + 1):
            entry_threshold = base_price * (1 - self.grid_spacing_pct * level_index)
            levels.append(
                {
                    "level": level_index,
                    "entry_threshold": entry_threshold,
                    "units": self.grid_units_per_level,
                    "active": False,
                    "entry_price": 0.0,
                }
            )
        return levels

    def _handle_grid_entries(self, current_date: pd.Timestamp, close_price: float) -> None:
        """当价格跌破阈值时，为尚未激活的网格层补仓。"""
        for level in self.grid_levels:
            if level["active"]:
                continue
            if close_price > float(level["entry_threshold"]):
                continue

            units = int(level["units"])
            tag = self._grid_tag(int(level["level"]))
            self.buy(size=units, tag=tag)
            # 只记录真实成交价，不使用预设阈值作为成本，否则止盈和成本口径都会失真。
            level["active"] = True
            level["entry_price"] = close_price

            self.event_log.append(
                {
                    "Date": format_timestamp(current_date),
                    "EventType": "grid_buy",
                    "Level": int(level["level"]),
                    "Price": close_price,
                    "Units": units,
                    "CashFlow": units * close_price,
                    "Note": "触发下行网格买入",
                }
            )

    def _handle_grid_exits(self, current_date: pd.Timestamp, close_price: float) -> None:
        """当价格满足止盈条件时，仅平掉对应网格层。"""
        for level in self.grid_levels:
            if not level["active"]:
                continue

            entry_price = float(level["entry_price"])
            take_profit_price = entry_price * (1 + self.take_profit_pct)
            if close_price < take_profit_price:
                continue

            # 通过 tag 查找当前层的活动交易，避免误平其他层或底仓。
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
                    "Date": format_timestamp(current_date),
                    "EventType": "grid_sell",
                    "Level": int(level["level"]),
                    "Price": close_price,
                    "Units": units,
                    "CashFlow": units * close_price,
                    "Note": "达到网格止盈价后卖出本层仓位",
                }
            )

    def _record_snapshot(self, current_date: pd.Timestamp, close_price: float) -> None:
        """记录当前 bar 的持仓、成本和收益快照。

        报告里的成本摊薄、价格图和账户状态表都直接依赖这里的历史记录，
        因此必须把底仓、未平网格和已实现利润拆开计算。
        """
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
        # 已落袋的网格利润会抵减剩余持仓的等效成本，但不会改变市场价值。
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
                "Date": format_timestamp(current_date),
                "Close": close_price,
                "PeakClose": self.high_water_mark,
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

    def _round_down_to_lot(self, units: int) -> int:
        if self.lot_size <= 0:
            raise ValueError(f"lot_size 必须大于 0，当前值为 {self.lot_size}")
        return units // self.lot_size * self.lot_size


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


def build_sample_window(
    data: pd.DataFrame,
    validation_start: str = DEFAULT_VALIDATION_START,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> DeclineWindow:
    """构建日线样本内/样本外窗口摘要。

    当前项目已经移除“先等 10% 回撤再建仓”的旧规则，
    所以窗口起点就是样本内的首个交易日。
    """
    validation_timestamp = pd.Timestamp(validation_start)
    sample_end_ts = validation_timestamp - pd.Timedelta(days=1)
    sample_start_ts = sample_end_ts - pd.Timedelta(days=lookback_days)
    window = data.loc[sample_start_ts:sample_end_ts]
    if window.empty:
        raise ValueError("样本内区间为空，无法构建样本窗口。")

    first_date = window.index.min()
    first_price = float(window.iloc[0]["Close"])
    peak_date = window["Close"].idxmax()
    peak_price = float(window.loc[peak_date, "Close"])
    return DeclineWindow(
        peak_date=format_timestamp(peak_date),
        peak_price=peak_price,
        entry_date=format_timestamp(first_date),
        entry_price=first_price,
        sample_start=format_timestamp(first_date),
        sample_end=format_timestamp(window.index.max()),
        validation_start=format_timestamp(validation_timestamp),
    )


def _compute_score(return_pct: float, max_drawdown_pct: float, cost_reduction_pct: float) -> float:
    """收益/回撤综合评分。

    这不是通用金融指标，而是当前项目为了平衡三件事的内部评分：
    总收益、回撤可控性、以及摊薄剩余持仓成本的能力。
    """
    return return_pct - abs(max_drawdown_pct) * 0.7 + cost_reduction_pct * 0.5


def _compute_robust_score(
    walk_forward_score_mean: float,
    walk_forward_score_min: float,
    walk_forward_return_std_pct: float,
    window_count: int,
) -> float:
    """基于多窗口结果给参数做稳健性评分。

    当前项目不直接上随机搜索或外部优化器，
    先在可解释性更强的穷举结果上叠加一层“时间顺序多窗口验证”：

    - 平均分高，说明大多数窗口都不差
    - 最差窗口分数不能太差，避免只在单一阶段好看
    - 收益波动越大，说明参数越不稳定，需要扣分
    """
    if window_count <= 1:
        return walk_forward_score_mean
    return walk_forward_score_mean * 0.6 + walk_forward_score_min * 0.4 - walk_forward_return_std_pct * 0.25


def _history_to_frame(history: list[dict[str, object]]) -> pd.DataFrame:
    """把策略内部快照列表转成统一 DataFrame。"""
    return pd.DataFrame(history) if history else pd.DataFrame()


def _events_to_frame(events: list[dict[str, object]]) -> pd.DataFrame:
    """把事件流水转成统一 DataFrame。"""
    return pd.DataFrame(events) if events else pd.DataFrame()


def build_walk_forward_windows(
    data: pd.DataFrame,
    window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
) -> list[pd.DataFrame]:
    """把样本内区间按时间顺序拆成多个连续窗口。

    这里不是机器学习里的训练/验证折，而是给固定参数做稳健性体检：
    同一套参数如果只在一小段窗口表现突出，通常不值得直接拿去样本外验证。
    """
    if data.empty:
        raise ValueError("样本为空，无法拆分稳健性窗口。")
    if window_count < 1:
        raise ValueError("window_count 至少为 1。")
    if min_window_size < 5:
        raise ValueError("min_window_size 过小，至少应保留 5 根 K 线。")
    if len(data) < min_window_size * 2:
        return [data.copy()]

    max_window_count = max(1, len(data) // min_window_size)
    effective_count = min(window_count, max_window_count)
    if effective_count <= 1:
        return [data.copy()]

    split_points = np.linspace(0, len(data), effective_count + 1, dtype=int)
    windows: list[pd.DataFrame] = []
    for start_index, end_index in zip(split_points[:-1], split_points[1:]):
        if end_index - start_index < min_window_size:
            continue
        windows.append(data.iloc[start_index:end_index].copy())

    return windows or [data.copy()]


def _summarize_walk_forward_runs(walk_forward_runs: list[dict[str, object]]) -> dict[str, float | int]:
    """汇总多窗口回测结果。"""
    summaries = [run_result["summary"] for run_result in walk_forward_runs]
    score_values = [float(summary["Score"]) for summary in summaries]
    return_values = [float(summary["ReturnPct"]) for summary in summaries]
    drawdown_values = [float(summary["MaxDrawdownPct"]) for summary in summaries]
    cost_values = [float(summary["CostReductionPct"]) for summary in summaries]
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
        "WalkForwardCostReductionMeanPct": float(np.mean(cost_values)) if cost_values else 0.0,
        "WalkForwardReturnStdPct": walk_forward_return_std_pct,
        "WalkForwardPositiveWindowRatio": positive_window_ratio,
        "RobustScore": _compute_robust_score(
            walk_forward_score_mean=walk_forward_score_mean,
            walk_forward_score_min=walk_forward_score_min,
            walk_forward_return_std_pct=walk_forward_return_std_pct,
            window_count=window_count,
        ),
    }


def _build_parameter_key(grid_spacing_pct: float, grid_count: int, take_profit_pct: float) -> tuple[float, int, float]:
    """构造稳定的参数键，避免浮点比较误差影响最优结果回取。"""
    return (round(float(grid_spacing_pct), 8), int(grid_count), round(float(take_profit_pct), 8))


def build_intraday_sample_window(
    data: pd.DataFrame,
    validation_start: pd.Timestamp,
) -> DeclineWindow:
    """构建分钟线样本内/样本外窗口摘要。

    分钟线窗口来源于最近样本按比例切分，因此这里不再使用固定日历日期回看。
    """
    if data.empty:
        raise ValueError("分钟样本内区间为空，无法构建样本窗口。")

    first_date = data.index.min()
    first_price = float(data.iloc[0]["Close"])
    peak_date = data["Close"].idxmax()
    peak_price = float(data.loc[peak_date, "Close"])
    sample_end = data.index.max()
    return DeclineWindow(
        peak_date=format_timestamp(peak_date),
        peak_price=peak_price,
        entry_date=format_timestamp(first_date),
        entry_price=first_price,
        sample_start=format_timestamp(first_date),
        sample_end=format_timestamp(sample_end),
        validation_start=format_timestamp(validation_start),
    )


def run_grid_backtest(
    data: pd.DataFrame,
    scenario_name: str,
    grid_spacing_pct: float,
    grid_count: int,
    take_profit_pct: float,
    symbol: str,
    market: str,
    lot_size: int,
    lot_size_source: str,
    total_capital: float = TOTAL_CAPITAL,
) -> dict[str, object]:
    """运行单次网格回测。

    返回值既包含给报告使用的汇总数据，也保留明细表和 backtesting 原始统计，
    这样工作流、图表和测试都能共用同一次回测结果。
    """
    backtest = Backtest(
        data,
        FixedUnitGridStrategy,
        cash=total_capital,
        commission=0.0,
        trade_on_close=True,
        exclusive_orders=False,
        finalize_trades=True,
    )
    stats = backtest.run(
        total_capital=total_capital,
        initial_cash_ratio=INITIAL_CASH_RATIO,
        grid_spacing_pct=grid_spacing_pct,
        grid_count=grid_count,
        take_profit_pct=take_profit_pct,
        lot_size=lot_size,
    )
    strategy: FixedUnitGridStrategy = stats["_strategy"]
    history = _history_to_frame(strategy.history)
    events = _events_to_frame(strategy.event_log)

    latest_snapshot = history.iloc[-1].to_dict() if not history.empty else {}
    peak_date = format_timestamp(strategy.peak_date)
    base_entry_date = format_timestamp(strategy.base_entry_date) if strategy.base_entry_date else ""
    max_drawdown_pct = abs(float(stats["Max. Drawdown [%]"]))
    return_pct = float(stats["Return [%]"])
    cost_reduction_pct = float(latest_snapshot.get("CostReductionPct", 0.0))

    # summary 是项目内部统一口径的“最小汇总单元”，CSV、报告和参数搜索都依赖这些字段。
    summary = {
        "Symbol": symbol,
        "Market": market,
        "Scenario": scenario_name,
        "StartDate": format_timestamp(data.index.min()),
        "EndDate": format_timestamp(data.index.max()),
        "PeakDate": peak_date,
        "PeakPrice": strategy.high_water_mark,
        "EntryDate": base_entry_date,
        "EntryPrice": strategy.base_entry_price,
        "LotSize": lot_size,
        "LotSizeSource": lot_size_source,
        "BaseUnits": strategy.base_units,
        "GridUnitsPerLevel": strategy.grid_units_per_level,
        "GridSpacingPct": grid_spacing_pct * 100,
        "GridCount": grid_count,
        "TakeProfitPct": take_profit_pct * 100,
        "ReturnPct": return_pct,
        "AnnualReturnPct": float(stats["Return (Ann.) [%]"]),
        "MaxDrawdownPct": max_drawdown_pct,
        "ClosedTrades": int(stats["# Trades"]),
        "WinRatePct": float(stats["Win Rate [%]"]) if pd.notna(stats["Win Rate [%]"]) else 0.0,
        "FinalEquity": float(stats["Equity Final [$]"]),
        "TotalCapital": total_capital,
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
    symbol: str,
    market: str,
    lot_size: int,
    lot_size_source: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """对网格参数做穷举搜索并返回最优结果。

    当前项目故意保留穷举，优先保证结果可重复和可解释；
    但最终选参不再只看单个样本窗口里的最高分，而是叠加多窗口稳健性筛选。
    """
    rows: list[dict[str, object]] = []
    run_records: dict[tuple[float, int, float], dict[str, object]] = {}
    walk_forward_windows = build_walk_forward_windows(data)

    for spacing in spacings:
        for grid_count in grid_counts:
            for take_profit in take_profits:
                run_result = run_grid_backtest(
                    data=data,
                    scenario_name=scenario_name,
                    grid_spacing_pct=spacing,
                    grid_count=grid_count,
                    take_profit_pct=take_profit,
                    symbol=symbol,
                    market=market,
                    lot_size=lot_size,
                    lot_size_source=lot_size_source,
                )
                walk_forward_runs = [
                    run_grid_backtest(
                        data=window,
                        scenario_name=f"{scenario_name}_wf_{index + 1}",
                        grid_spacing_pct=spacing,
                        grid_count=grid_count,
                        take_profit_pct=take_profit,
                        symbol=symbol,
                        market=market,
                        lot_size=lot_size,
                        lot_size_source=lot_size_source,
                    )
                    for index, window in enumerate(walk_forward_windows)
                ]
                robust_summary = _summarize_walk_forward_runs(walk_forward_runs)
                run_result["summary"].update(robust_summary)
                parameter_key = _build_parameter_key(spacing, grid_count, take_profit)
                run_records[parameter_key] = run_result
                rows.append(run_result["summary"])

    results = pd.DataFrame(rows).sort_values(
        ["RobustScore", "WalkForwardScoreMin", "WalkForwardPositiveWindowRatio", "Score", "ReturnPct"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)
    if results.empty:
        raise ValueError("参数搜索未产生任何结果。")
    best_row = results.iloc[0]
    best_key = _build_parameter_key(
        float(best_row["GridSpacingPct"]) / 100,
        int(best_row["GridCount"]),
        float(best_row["TakeProfitPct"]) / 100,
    )
    best_run = run_records.get(best_key)
    if best_run is None:
        raise ValueError("无法回取最优参数对应的回测结果。")
    return results, best_run


def split_in_sample_and_validation(
    data: pd.DataFrame,
    validation_start: str = DEFAULT_VALIDATION_START,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> tuple[DeclineWindow, pd.DataFrame, pd.DataFrame]:
    """拆分样本内和样本外数据。"""
    decline_window = build_sample_window(
        data,
        validation_start=validation_start,
        lookback_days=lookback_days,
    )
    in_sample = data.loc[decline_window.sample_start:decline_window.sample_end].copy()
    validation = data.loc[decline_window.validation_start:].copy()
    if validation.empty:
        raise ValueError("样本外区间为空，无法验证 2026 表现。")
    return decline_window, in_sample, validation


def split_intraday_in_sample_and_validation(
    data: pd.DataFrame,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
) -> tuple[DeclineWindow, pd.DataFrame, pd.DataFrame]:
    """按最近分钟线样本拆分样本内和样本外数据。

    免费分钟线通常只有最近 60 天，不能照搬日线那套跨年的固定切分方式，
    所以这里按时间顺序做比例切分。
    """
    if not 0 < validation_ratio < 0.5:
        raise ValueError("validation_ratio 必须在 0 和 0.5 之间。")
    if len(data) < 20:
        raise ValueError("分钟线样本过短，至少需要 20 根 K 线。")

    split_index = int(len(data) * (1 - validation_ratio))
    split_index = min(max(split_index, 1), len(data) - 1)
    in_sample = data.iloc[:split_index].copy()
    validation = data.iloc[split_index:].copy()
    validation_start = pd.Timestamp(validation.index.min())
    decline_window = build_intraday_sample_window(in_sample, validation_start=validation_start)
    if validation.empty:
        raise ValueError("分钟样本外区间为空，无法验证表现。")
    return decline_window, in_sample, validation


def save_run_artifacts(output_dir: str | Path, prefix: str, run_result: dict[str, object]) -> dict[str, Path]:
    """保存单次回测产生的明细文件。

    文件拆分得比较细，是为了让参数搜索、人工复盘和报告生成可以独立复用。
    """
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
