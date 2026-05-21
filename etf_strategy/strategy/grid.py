from __future__ import annotations
"""网格策略核心实现。

这里聚焦两类职责：

1. 定义 backtesting.py 直接调用的策略类。
2. 对外暴露单次回测和参数搜索能力。

样本切分和产物落盘已经拆到相邻模块，避免策略撮合文件继续膨胀。
"""

import hashlib
import json
import pickle
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd
from backtesting import Backtest, Strategy

from etf_strategy.settings import (
    DEFAULT_JOBS,
    DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    ExecutionConfig,
    build_execution_config,
)
from etf_strategy.strategy.artifacts import load_price_frame, save_decline_window, save_run_artifacts
from etf_strategy.strategy.metrics import compute_score, summarize_walk_forward_runs
from etf_strategy.strategy.sampling import (
    DeclineWindow,
    build_intraday_sample_window,
    build_sample_window,
    build_walk_forward_windows,
    format_timestamp,
    split_in_sample_and_validation,
    split_intraday_in_sample_and_validation,
)


TOTAL_CAPITAL = 200000.0
INITIAL_CASH_RATIO = 0.5

class FixedUnitGridStrategy(Strategy):
    """纯现金网格策略。

    策略不在样本起点建立底仓，只把第一根 K 线收盘价作为网格锚点。
    后续只有当价格跌到对应层级时才买入，反弹到单层止盈价时卖出。
    """

    total_capital = TOTAL_CAPITAL
    initial_cash_ratio = INITIAL_CASH_RATIO
    grid_spacing_pct = 0.05
    grid_count = 5
    take_profit_pct = 0.05
    lot_size = 1
    execution_profile = "research"
    commission_bps = 0.0
    slippage_bps = 0.0
    max_position_ratio = 1.0
    stop_loss_pct = 0.0
    cooldown_bars = 0
    benchmark = "buy_hold"
    grid_mode = "cash"
    left_side_policy = "hold"
    force_exit_loss_pct = 0.05

    def init(self) -> None:
        """在样本第一根 K 线上初始化现金网格。

        backtesting.py 会在 `init()` 之后立刻开始逐 bar 调 `next()`，
        因此网格层级和首笔快照都必须在这里准备好。
        """
        if self.grid_mode != "cash":
            raise ValueError(f"当前仅支持纯现金网格模式: grid_mode={self.grid_mode}")
        if self.left_side_policy not in {"hold", "force_exit"}:
            raise ValueError(f"left_side_policy 必须是 hold 或 force_exit，当前值为 {self.left_side_policy}")

        first_close = float(self.data.Close[0])
        first_date = pd.Timestamp(self.data.index[0])

        self.anchor_date = first_date
        self.anchor_price = first_close
        self.high_water_mark = first_close
        self.peak_date = first_date

        # 兼容旧报告字段：纯现金网格没有底仓，相关数量固定为 0。
        self.base_cash_budget = 0.0
        self.reserve_cash_budget = self.total_capital

        self.base_entered = False
        self.base_entry_date: pd.Timestamp | None = None
        self.base_entry_price = first_close
        self.base_transaction_cost = 0.0
        self.base_units = 0
        self.grid_units_per_level = 0
        self.grid_levels: list[dict[str, float | int | bool]] = []
        self.realized_grid_profit = 0.0
        self.latest_unrealized_pnl = 0.0
        self.grid_cycles_completed = 0
        self.transaction_cost_total = 0.0
        self.slippage_cost_total = 0.0
        self.stop_loss_events = 0
        self.risk_skip_events = 0
        self.force_exit_events = 0
        self.force_exit_loss_ratio = 0.0
        self.force_exit_triggered = False
        self.force_exit_date: pd.Timestamp | None = None
        self.trading_stopped = False
        self.cooldown_remaining = 0
        self.stop_loss_active = False
        self.max_position_ratio_used = 0.0
        self.event_log: list[dict[str, object]] = []
        self.history: list[dict[str, object]] = []
        self.grid_units_per_level = self._build_grid_units_per_level(first_close)
        self.grid_levels = self._build_grid_levels(first_close)
        self._record_snapshot(first_date, first_close)

    def next(self) -> None:
        """按收盘价驱动网格开平仓，并记录账户状态快照。"""
        current_date = pd.Timestamp(self.data.index[-1])
        close_price = float(self.data.Close[-1])

        if close_price > self.high_water_mark:
            self.high_water_mark = close_price
            self.peak_date = current_date

        if not self.trading_stopped:
            # 先处理止盈，再判断左侧风险，最后才允许新的网格买入。
            self._handle_grid_exits(current_date, close_price)
            if self._force_exit_required(close_price):
                self._force_exit_all(current_date, close_price)
            if not self.trading_stopped and self._grid_entries_allowed(current_date, close_price):
                self._handle_grid_entries(current_date, close_price)

        self._record_snapshot(current_date, close_price)
        self._decrement_cooldown()

    def _build_grid_units_per_level(self, base_price: float) -> int:
        """把单层预算折算成统一的固定股数。

        这里故意用样本起点价格而不是逐层触发价来估算，
        目的是让所有网格层保持相同仓位大小，避免回测重新退化成“每层不同金额”。
        """
        per_level_budget = self.reserve_cash_budget / self.grid_count
        cash_per_unit = self._buy_cash_required_per_unit(base_price)
        raw_units = int(per_level_budget / cash_per_unit)
        units = self._round_down_to_lot(raw_units)
        if units <= 0:
            raise ValueError(
                f"单层网格预算不足以买入 1 手，无法执行固定股数网格: lot_size={self.lot_size}, price={base_price:.2f}"
            )
        return units

    def _build_grid_levels(self, base_price: float) -> list[dict[str, float | int | bool]]:
        """根据锚定价格预生成所有网格层。

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
                    "entry_transaction_cost": 0.0,
                }
            )
        return levels

    def _handle_grid_entries(self, current_date: pd.Timestamp, close_price: float) -> None:
        """当价格跌破阈值时，为尚未激活的网格层补仓。"""
        if self.trading_stopped:
            return
        for level in self.grid_levels:
            if level["active"]:
                continue
            if close_price > float(level["entry_threshold"]):
                continue

            units = int(level["units"])
            if not self._position_limit_allows_entry(current_date, close_price, units, int(level["level"])):
                break

            tag = self._grid_tag(int(level["level"]))
            self.buy(size=units, tag=tag)
            # 只记录真实成交价，不使用预设阈值作为成本，否则止盈和成本口径都会失真。
            execution_price = self._buy_execution_price(close_price)
            transaction_cost = self._transaction_cost(execution_price, units)
            slippage_cost = self._slippage_cost(close_price, execution_price, units)
            self.transaction_cost_total += transaction_cost
            self.slippage_cost_total += slippage_cost
            level["active"] = True
            level["entry_price"] = execution_price
            level["entry_transaction_cost"] = transaction_cost

            self.event_log.append(
                {
                    "Date": format_timestamp(current_date),
                    "EventType": "grid_buy",
                    "Level": int(level["level"]),
                    "Price": close_price,
                    "ExecutionPrice": execution_price,
                    "Units": units,
                    "CashFlow": units * execution_price + transaction_cost,
                    "TransactionCost": transaction_cost,
                    "SlippageCost": slippage_cost,
                    "Note": "触发下行网格买入",
                }
            )

    def _handle_grid_exits(self, current_date: pd.Timestamp, close_price: float) -> None:
        """当价格满足止盈条件时，仅平掉对应网格层。"""
        for level in self.grid_levels:
            if not level["active"]:
                continue

            entry_price = float(level["entry_price"])
            entry_transaction_cost = float(level.get("entry_transaction_cost", 0.0))
            take_profit_price = entry_price * (1 + self.take_profit_pct)
            if close_price < take_profit_price:
                continue

            self._close_grid_level(
                level=level,
                current_date=current_date,
                close_price=close_price,
                event_type="grid_sell",
                note="达到网格止盈价后卖出本层仓位",
                count_as_cycle=True,
            )

    def _force_exit_required(self, close_price: float) -> bool:
        """判断左侧行情下是否需要强制清掉所有未平网格。"""
        if self.left_side_policy != "force_exit" or self.force_exit_triggered:
            return False
        open_units = self._open_grid_units()
        if open_units <= 0:
            self.latest_unrealized_pnl = 0.0
            return False

        unrealized_pnl = self._open_grid_unrealized_pnl(close_price)
        self.latest_unrealized_pnl = unrealized_pnl
        if unrealized_pnl >= 0:
            self.force_exit_loss_ratio = 0.0
            return False

        self.force_exit_loss_ratio = abs(unrealized_pnl) / self.total_capital if self.total_capital else 0.0
        threshold = max(float(self.force_exit_loss_pct), 0.0)
        return self.force_exit_loss_ratio >= threshold

    def _force_exit_all(self, current_date: pd.Timestamp, close_price: float) -> None:
        """左侧亏损达到阈值后强制卖出所有未平网格，并停止后续交易。"""
        closed_count = 0
        threshold_pct = max(float(self.force_exit_loss_pct), 0.0) * 100
        for level in list(self.grid_levels):
            if not level["active"]:
                continue
            closed = self._close_grid_level(
                level=level,
                current_date=current_date,
                close_price=close_price,
                event_type="force_exit_sell",
                note=f"未平网格浮亏达到总资金 {threshold_pct:.2f}% 阈值，强制卖出本层仓位",
                count_as_cycle=False,
            )
            if closed:
                closed_count += 1

        if closed_count <= 0:
            return
        self.force_exit_events += closed_count
        self.force_exit_triggered = True
        self.force_exit_date = current_date
        self.trading_stopped = True
        self.cooldown_remaining = 0

    def _close_grid_level(
        self,
        level: dict[str, float | int | bool],
        current_date: pd.Timestamp,
        close_price: float,
        event_type: str,
        note: str,
        count_as_cycle: bool,
    ) -> bool:
        """按当前收盘价估算卖出成交，并同步策略内的收益拆解口径。"""
        active_trade = next(
            (trade for trade in self.trades if trade.tag == self._grid_tag(int(level["level"]))),
            None,
        )
        if active_trade is None:
            return False

        units = int(level["units"])
        entry_price = float(level["entry_price"])
        entry_transaction_cost = float(level.get("entry_transaction_cost", 0.0))
        active_trade.close()
        execution_price = self._sell_execution_price(close_price)
        transaction_cost = self._transaction_cost(execution_price, units)
        slippage_cost = self._slippage_cost(close_price, execution_price, units)
        self.transaction_cost_total += transaction_cost
        self.slippage_cost_total += slippage_cost
        level["active"] = False
        level["entry_price"] = 0.0
        level["entry_transaction_cost"] = 0.0
        self.realized_grid_profit += (execution_price - entry_price) * units - entry_transaction_cost - transaction_cost
        if count_as_cycle:
            self.grid_cycles_completed += 1

        self.event_log.append(
            {
                "Date": format_timestamp(current_date),
                "EventType": event_type,
                "Level": int(level["level"]),
                "Price": close_price,
                "ExecutionPrice": execution_price,
                "Units": units,
                "CashFlow": units * execution_price - transaction_cost,
                "TransactionCost": transaction_cost,
                "SlippageCost": slippage_cost,
                "Note": note,
            }
        )
        return True

    def _record_snapshot(self, current_date: pd.Timestamp, close_price: float) -> None:
        """记录当前 bar 的持仓、成本和收益快照。

        报告里的持仓成本、价格图和账户状态表都直接依赖这里的历史记录，
        因此必须把未平网格、已实现收益和浮动盈亏拆开计算。
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
            open_grid_cost += units * float(level["entry_price"]) + float(level.get("entry_transaction_cost", 0.0))

        total_units = open_grid_units
        gross_cost = open_grid_cost
        # 已落袋的网格利润会抵减剩余网格仓位的等效成本，但不会改变市场价值。
        effective_cost_basis = gross_cost - self.realized_grid_profit
        effective_cost = effective_cost_basis / total_units if total_units else 0.0
        market_value = total_units * close_price
        position_ratio = market_value / self.total_capital if self.total_capital else 0.0
        self.max_position_ratio_used = max(self.max_position_ratio_used, position_ratio)
        unrealized_pnl = self._open_grid_unrealized_pnl(close_price) if total_units else 0.0
        self.latest_unrealized_pnl = unrealized_pnl

        self.history.append(
            {
                "Date": format_timestamp(current_date),
                "Close": close_price,
                "PeakClose": self.high_water_mark,
                "PositionUnits": total_units,
                "OpenGridLevels": open_grid_levels,
                "GrossCost": gross_cost,
                "RealizedGridProfit": self.realized_grid_profit,
                "ClosedGridNetProfit": self.realized_grid_profit,
                "UnrealizedPnl": unrealized_pnl,
                "EffectiveCost": effective_cost,
                "CostReductionPct": 0.0,
                "MarketValue": market_value,
                "OpenGridMarketValue": market_value,
                "PositionRatioPct": position_ratio * 100,
                "MaxCapitalUsedPct": self.max_position_ratio_used * 100,
                "TransactionCostCumulative": self.transaction_cost_total,
                "SlippageCostCumulative": self.slippage_cost_total,
                "MaxPositionRatioUsedPct": self.max_position_ratio_used * 100,
            }
        )

    def _grid_entries_allowed(self, current_date: pd.Timestamp, close_price: float) -> bool:
        """检查止损停手和冷却期是否允许继续开新网格。"""
        if self.trading_stopped:
            return False
        if self.cooldown_remaining > 0:
            self._record_risk_event(
                current_date=current_date,
                event_type="risk_cooldown",
                close_price=close_price,
                level=0,
                note=f"停手机制冷却中，剩余 {self.cooldown_remaining} 根 K 线",
            )
            return False

        if self.stop_loss_pct <= 0:
            return True

        stop_loss_price = self.anchor_price * (1 - self.stop_loss_pct)
        if close_price > stop_loss_price:
            self.stop_loss_active = False
            return True

        if not self.stop_loss_active:
            self.stop_loss_events += 1
            self.stop_loss_active = True
            self.cooldown_remaining = max(int(self.cooldown_bars), 1)
            self._record_risk_event(
                current_date=current_date,
                event_type="risk_stop_loss",
                close_price=close_price,
                level=0,
                note=f"价格跌破锚定停手线 {stop_loss_price:.2f}，暂停新增网格",
            )
        return False

    def _position_limit_allows_entry(
        self,
        current_date: pd.Timestamp,
        close_price: float,
        units: int,
        level: int,
    ) -> bool:
        """检查新增一层网格后是否超过最大仓位占用。"""
        if self.max_position_ratio <= 0:
            raise ValueError(f"max_position_ratio 必须大于 0，当前值为 {self.max_position_ratio}")

        current_units = self._open_grid_units()
        projected_market_value = (current_units + units) * close_price
        projected_ratio = projected_market_value / self.total_capital if self.total_capital else 0.0
        if projected_ratio <= self.max_position_ratio:
            return True

        self._record_risk_event(
            current_date=current_date,
            event_type="risk_position_limit",
            close_price=close_price,
            level=level,
            note=(
                f"新增网格后仓位占用 {projected_ratio * 100:.2f}% "
                f"将超过上限 {self.max_position_ratio * 100:.2f}%"
            ),
        )
        return False

    def _record_risk_event(
        self,
        current_date: pd.Timestamp,
        event_type: str,
        close_price: float,
        level: int,
        note: str,
    ) -> None:
        """记录风控事件，避免风控触发时在报告里只看到交易消失。"""
        self.risk_skip_events += 1
        self.event_log.append(
            {
                "Date": format_timestamp(current_date),
                "EventType": event_type,
                "Level": level,
                "Price": close_price,
                "ExecutionPrice": close_price,
                "Units": 0,
                "CashFlow": 0.0,
                "TransactionCost": 0.0,
                "SlippageCost": 0.0,
                "Note": note,
            }
        )

    def _decrement_cooldown(self) -> None:
        """每根 K 线结束后推进停手冷却计数。"""
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1

    def _open_grid_units(self) -> int:
        """统计当前仍打开的网格股数。"""
        return sum(int(level["units"]) for level in self.grid_levels if level["active"])

    def _open_grid_unrealized_pnl(self, close_price: float) -> float:
        """按当前可卖出成交价估算未平网格浮动盈亏。"""
        unrealized_pnl = 0.0
        execution_price = self._sell_execution_price(close_price)
        for level in self.grid_levels:
            if not level["active"]:
                continue
            units = int(level["units"])
            entry_price = float(level["entry_price"])
            entry_transaction_cost = float(level.get("entry_transaction_cost", 0.0))
            exit_transaction_cost = self._transaction_cost(execution_price, units)
            unrealized_pnl += (execution_price - entry_price) * units - entry_transaction_cost - exit_transaction_cost
        return unrealized_pnl

    def _commission_rate(self) -> float:
        return max(float(self.commission_bps), 0.0) / 10000

    def _slippage_rate(self) -> float:
        return max(float(self.slippage_bps), 0.0) / 10000

    def _buy_execution_price(self, close_price: float) -> float:
        """按滑点估算买入成交价。"""
        return close_price * (1 + self._slippage_rate())

    def _sell_execution_price(self, close_price: float) -> float:
        """按滑点估算卖出成交价。"""
        return close_price * (1 - self._slippage_rate())

    def _transaction_cost(self, execution_price: float, units: int) -> float:
        """按成交金额估算手续费。"""
        return execution_price * units * self._commission_rate()

    def _slippage_cost(self, close_price: float, execution_price: float, units: int) -> float:
        """记录相对收盘价的滑点成本，便于报告拆解。"""
        return abs(execution_price - close_price) * units

    def _buy_cash_required_per_unit(self, close_price: float) -> float:
        """估算买入每股需要占用的现金。"""
        execution_price = self._buy_execution_price(close_price)
        return execution_price * (1 + self._commission_rate())

    @staticmethod
    def _grid_tag(level: int) -> str:
        return f"grid_{level}"

    def _round_down_to_lot(self, units: int) -> int:
        if self.lot_size <= 0:
            raise ValueError(f"lot_size 必须大于 0，当前值为 {self.lot_size}")
        return units // self.lot_size * self.lot_size


def _history_to_frame(history: list[dict[str, object]]) -> pd.DataFrame:
    """把策略内部快照列表转成统一 DataFrame。"""
    return pd.DataFrame(history) if history else pd.DataFrame()


def _events_to_frame(events: list[dict[str, object]]) -> pd.DataFrame:
    """把事件流水转成统一 DataFrame。"""
    return pd.DataFrame(events) if events else pd.DataFrame()


def _build_parameter_key(grid_spacing_pct: float, grid_count: int, take_profit_pct: float) -> tuple[float, int, float]:
    """构造稳定的参数键，避免浮点比较误差影响最优结果回取。"""
    return (round(float(grid_spacing_pct), 8), int(grid_count), round(float(take_profit_pct), 8))


def _round_down_to_lot_value(units: int, lot_size: int) -> int:
    """按最小交易单位向下取整。"""
    if lot_size <= 0:
        raise ValueError(f"lot_size 必须大于 0，当前值为 {lot_size}")
    return units // lot_size * lot_size


def _buy_cash_required_per_unit(close_price: float, execution: ExecutionConfig) -> float:
    """估算指定执行口径下买入每股需要的现金。"""
    commission_rate = max(execution.commission_bps, 0.0) / 10000
    slippage_rate = max(execution.slippage_bps, 0.0) / 10000
    execution_price = close_price * (1 + slippage_rate)
    return execution_price * (1 + commission_rate)


def _affordable_units(cash_budget: float, close_price: float, lot_size: int, execution: ExecutionConfig) -> int:
    """根据现金预算、价格和交易单位估算可买股数。"""
    raw_units = int(cash_budget / _buy_cash_required_per_unit(close_price, execution))
    return _round_down_to_lot_value(raw_units, lot_size)


def _build_benchmark_metrics(
    data: pd.DataFrame,
    total_capital: float,
    lot_size: int,
    execution: ExecutionConfig,
) -> dict[str, float | int]:
    """构造现金闲置和买入持有两个对照组。

    对照组使用同一套最小交易单位、手续费和买入滑点口径，避免报告里把
    “策略差异”和“交易假设差异”混在一起。
    """
    entry_price = float(data.iloc[0]["Close"])
    final_price = float(data.iloc[-1]["Close"])

    buy_hold_units = _affordable_units(total_capital, entry_price, lot_size, execution)
    buy_hold_cash_used = buy_hold_units * _buy_cash_required_per_unit(entry_price, execution)
    buy_hold_equity = total_capital - buy_hold_cash_used + buy_hold_units * final_price

    return {
        "CashIdleUnits": 0,
        "CashIdleFinalEquity": total_capital,
        "CashIdleReturnPct": 0.0,
        # 旧字段保留为现金闲置别名，避免历史 CSV 消费方在过渡期直接失效。
        "BaseOnlyUnits": 0,
        "BaseOnlyFinalEquity": total_capital,
        "BaseOnlyReturnPct": 0.0,
        "BuyHoldUnits": buy_hold_units,
        "BuyHoldFinalEquity": buy_hold_equity,
        "BuyHoldReturnPct": (buy_hold_equity / total_capital - 1) * 100 if total_capital else 0.0,
    }


def _data_fingerprint(data: pd.DataFrame) -> str:
    """为缓存构造行情样本指纹。"""
    hash_value = int(pd.util.hash_pandas_object(data.reset_index(), index=False).sum())
    return f"{len(data)}:{format_timestamp(data.index.min())}:{format_timestamp(data.index.max())}:{hash_value}"


def _candidate_cache_path(
    cache_dir: str | Path | None,
    payload: dict[str, object],
) -> Path | None:
    """根据候选参数和样本口径生成缓存路径。"""
    if cache_dir is None:
        return None
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return Path(cache_dir) / f"{digest}.pkl"


def _load_cached_candidate(cache_path: Path | None) -> dict[str, object] | None:
    """读取单个候选参数缓存。"""
    if cache_path is None or not cache_path.exists():
        return None
    with cache_path.open("rb") as handle:
        return pickle.load(handle)


def _save_cached_candidate(cache_path: Path | None, run_result: dict[str, object]) -> None:
    """写入单个候选参数缓存。"""
    if cache_path is None:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        pickle.dump(run_result, handle)


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
    execution_config: ExecutionConfig | None = None,
) -> dict[str, object]:
    """运行单次网格回测，必要时同时返回左侧风险两套口径。"""
    execution = execution_config or build_execution_config("research")
    if execution.left_side_policy != "both":
        return _run_grid_backtest_single(
            data=data,
            scenario_name=scenario_name,
            grid_spacing_pct=grid_spacing_pct,
            grid_count=grid_count,
            take_profit_pct=take_profit_pct,
            symbol=symbol,
            market=market,
            lot_size=lot_size,
            lot_size_source=lot_size_source,
            total_capital=total_capital,
            execution_config=execution,
        )

    hold_result = _run_grid_backtest_single(
        data=data,
        scenario_name=scenario_name,
        grid_spacing_pct=grid_spacing_pct,
        grid_count=grid_count,
        take_profit_pct=take_profit_pct,
        symbol=symbol,
        market=market,
        lot_size=lot_size,
        lot_size_source=lot_size_source,
        total_capital=total_capital,
        execution_config=replace(execution, left_side_policy="hold"),
    )
    force_exit_result = _run_grid_backtest_single(
        data=data,
        scenario_name=scenario_name,
        grid_spacing_pct=grid_spacing_pct,
        grid_count=grid_count,
        take_profit_pct=take_profit_pct,
        symbol=symbol,
        market=market,
        lot_size=lot_size,
        lot_size_source=lot_size_source,
        total_capital=total_capital,
        execution_config=replace(execution, left_side_policy="force_exit"),
    )

    hold_summary = hold_result["summary"]
    force_summary = force_exit_result["summary"]
    force_exit_policy_result = force_exit_result.copy()
    force_exit_policy_result["summary"] = force_summary.copy()
    force_summary.update(
        {
            "RequestedLeftSidePolicy": "both",
            "PrimaryLeftSidePolicy": "force_exit",
            "HoldFinalEquity": hold_summary["FinalEquity"],
            "HoldNetReturnPct": hold_summary["NetReturnPct"],
            "HoldClosedGridNetProfit": hold_summary["ClosedGridNetProfit"],
            "HoldUnrealizedPnl": hold_summary["UnrealizedPnl"],
            "HoldGridCyclesCompleted": hold_summary["GridCyclesCompleted"],
            "ForceExitFinalEquity": force_summary["FinalEquity"],
            "ForceExitNetReturnPct": force_summary["NetReturnPct"],
            "ForceExitClosedGridNetProfit": force_summary["ClosedGridNetProfit"],
            "ForceExitTriggered": force_summary["ForceExitTriggered"],
        }
    )
    force_exit_result["policy_results"] = {
        "hold": hold_result,
        "force_exit": force_exit_policy_result,
    }
    return force_exit_result


def _run_grid_backtest_single(
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
    execution_config: ExecutionConfig | None = None,
) -> dict[str, object]:
    """按指定左侧处理策略运行一次网格回测。

    返回值既包含给报告使用的汇总数据，也保留明细表和 backtesting 原始统计，
    这样工作流、图表和测试都能共用同一次回测结果。
    """
    execution = execution_config or build_execution_config("research")
    commission_rate = max(execution.commission_bps, 0.0) / 10000
    slippage_rate = max(execution.slippage_bps, 0.0) / 10000
    backtest = Backtest(
        data,
        FixedUnitGridStrategy,
        cash=total_capital,
        spread=slippage_rate,
        commission=commission_rate,
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
        execution_profile=execution.profile,
        commission_bps=execution.commission_bps,
        slippage_bps=execution.slippage_bps,
        max_position_ratio=execution.max_position_ratio,
        stop_loss_pct=execution.stop_loss_pct,
        cooldown_bars=execution.cooldown_bars,
        benchmark=execution.benchmark,
        grid_mode=execution.grid_mode,
        left_side_policy=execution.left_side_policy,
        force_exit_loss_pct=execution.force_exit_loss_pct,
    )
    strategy: FixedUnitGridStrategy = stats["_strategy"]
    history = _history_to_frame(strategy.history)
    events = _events_to_frame(strategy.event_log)

    latest_snapshot = history.iloc[-1].to_dict() if not history.empty else {}
    peak_date = format_timestamp(strategy.peak_date)
    anchor_date = format_timestamp(strategy.anchor_date)
    max_drawdown_pct = abs(float(stats["Max. Drawdown [%]"]))
    return_pct = float(stats["Return [%]"])
    closed_grid_net_profit = float(strategy.realized_grid_profit)
    closed_grid_return_pct = closed_grid_net_profit / total_capital * 100 if total_capital else 0.0
    unrealized_pnl = float(latest_snapshot.get("UnrealizedPnl", 0.0))
    benchmark_metrics = _build_benchmark_metrics(
        data=data,
        total_capital=total_capital,
        lot_size=lot_size,
        execution=execution,
    )
    final_equity = float(stats["Equity Final [$]"])
    net_pnl = final_equity - total_capital

    # summary 是项目内部统一口径的“最小汇总单元”，CSV、报告和参数搜索都依赖这些字段。
    summary = {
        "Symbol": symbol,
        "Market": market,
        "Scenario": scenario_name,
        "StartDate": format_timestamp(data.index.min()),
        "EndDate": format_timestamp(data.index.max()),
        "PeakDate": peak_date,
        "PeakPrice": strategy.high_water_mark,
        "EntryDate": anchor_date,
        "EntryPrice": strategy.anchor_price,
        "AnchorDate": anchor_date,
        "AnchorPrice": strategy.anchor_price,
        "LotSize": lot_size,
        "LotSizeSource": lot_size_source,
        "BaseUnits": strategy.base_units,
        "GridUnitsPerLevel": strategy.grid_units_per_level,
        "GridSpacingPct": grid_spacing_pct * 100,
        "GridCount": grid_count,
        "TakeProfitPct": take_profit_pct * 100,
        "ReturnPct": return_pct,
        "NetReturnPct": return_pct,
        "NetPnl": net_pnl,
        "AnnualReturnPct": float(stats["Return (Ann.) [%]"]),
        "MaxDrawdownPct": max_drawdown_pct,
        "ClosedTrades": int(stats["# Trades"]),
        "WinRatePct": float(stats["Win Rate [%]"]) if pd.notna(stats["Win Rate [%]"]) else 0.0,
        "FinalEquity": final_equity,
        "TotalCapital": total_capital,
        "PositionUnits": int(latest_snapshot.get("PositionUnits", 0)),
        "EffectiveCost": float(latest_snapshot.get("EffectiveCost", 0.0)),
        "CostReductionPct": 0.0,
        "RealizedGridProfit": strategy.realized_grid_profit,
        "ClosedGridNetProfit": closed_grid_net_profit,
        "ClosedGridReturnPct": closed_grid_return_pct,
        "UnrealizedPnl": unrealized_pnl,
        "OpenGridMarketValue": float(latest_snapshot.get("OpenGridMarketValue", 0.0)),
        "MaxCapitalUsedPct": float(latest_snapshot.get("MaxCapitalUsedPct", 0.0)),
        "GridCyclesCompleted": strategy.grid_cycles_completed,
        "ExecutionProfile": execution.profile,
        "CommissionBps": execution.commission_bps,
        "SlippageBps": execution.slippage_bps,
        "TransactionCost": strategy.transaction_cost_total,
        "SlippageCost": strategy.slippage_cost_total,
        "MaxPositionRatio": execution.max_position_ratio * 100,
        "MaxPositionRatioUsed": strategy.max_position_ratio_used * 100,
        "StopLossPct": execution.stop_loss_pct * 100,
        "CooldownBars": execution.cooldown_bars,
        "StopLossEvents": strategy.stop_loss_events,
        "RiskSkipEvents": strategy.risk_skip_events,
        "GridMode": execution.grid_mode,
        "LeftSidePolicy": execution.left_side_policy,
        "RequestedLeftSidePolicy": execution.left_side_policy,
        "PrimaryLeftSidePolicy": execution.left_side_policy,
        "ForceExitLossPct": execution.force_exit_loss_pct * 100,
        "ForceExitTriggered": strategy.force_exit_triggered,
        "ForceExitEvents": strategy.force_exit_events,
        "ForceExitDate": format_timestamp(strategy.force_exit_date) if strategy.force_exit_date else "",
        "ForceExitLossRatioPct": strategy.force_exit_loss_ratio * 100,
        "Benchmark": execution.benchmark,
        **benchmark_metrics,
        "GridVsCashIdle": final_equity - float(benchmark_metrics["CashIdleFinalEquity"]),
        "GridVsBaseOnly": final_equity - float(benchmark_metrics["BaseOnlyFinalEquity"]),
        "GridVsBuyHold": final_equity - float(benchmark_metrics["BuyHoldFinalEquity"]),
        "Score": compute_score(return_pct, max_drawdown_pct, closed_grid_return_pct),
        "TriggeredEntry": bool(events["EventType"].eq("grid_buy").any()) if not events.empty else False,
        "TriggeredGridEntry": bool(events["EventType"].eq("grid_buy").any()) if not events.empty else False,
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
    execution_config: ExecutionConfig | None = None,
    wf_window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    wf_min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    jobs: int = DEFAULT_JOBS,
    cache_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """对网格参数做穷举搜索并返回最优结果。

    当前项目故意保留穷举，优先保证结果可重复和可解释；
    但最终选参不再只看单个样本窗口里的最高分，而是叠加多窗口稳健性筛选。
    """
    execution = execution_config or build_execution_config("research")
    walk_forward_windows = build_walk_forward_windows(
        data,
        window_count=wf_window_count,
        min_window_size=wf_min_window_size,
    )
    candidate_specs = [
        (spacing, grid_count, take_profit)
        for spacing in spacings
        for grid_count in grid_counts
        for take_profit in take_profits
    ]
    effective_jobs = max(1, int(jobs))
    data_fingerprint = _data_fingerprint(data)

    def run_candidate(spec: tuple[float, int, float]) -> dict[str, object]:
        spacing, grid_count, take_profit = spec
        cache_payload = {
            "data": data_fingerprint,
            "scenario": scenario_name,
            "symbol": symbol,
            "market": market,
            "lot_size": lot_size,
            "spacing": spacing,
            "grid_count": grid_count,
            "take_profit": take_profit,
            "execution": asdict(execution),
            "wf_window_count": wf_window_count,
            "wf_min_window_size": wf_min_window_size,
        }
        cache_path = _candidate_cache_path(cache_dir, cache_payload)
        cached = _load_cached_candidate(cache_path)
        if cached is not None:
            return cached

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
            execution_config=execution,
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
                execution_config=execution,
            )
            for index, window in enumerate(walk_forward_windows)
        ]
        robust_summary = summarize_walk_forward_runs(walk_forward_runs)
        run_result["summary"].update(robust_summary)
        _save_cached_candidate(cache_path, run_result)
        return run_result

    if effective_jobs == 1 or len(candidate_specs) <= 1:
        candidate_runs = [run_candidate(spec) for spec in candidate_specs]
    else:
        with ThreadPoolExecutor(max_workers=effective_jobs) as executor:
            candidate_runs = list(executor.map(run_candidate, candidate_specs))

    rows: list[dict[str, object]] = []
    run_records: dict[tuple[float, int, float], dict[str, object]] = {}
    for run_result in candidate_runs:
        summary = run_result["summary"]
        parameter_key = _build_parameter_key(
            float(summary["GridSpacingPct"]) / 100,
            int(summary["GridCount"]),
            float(summary["TakeProfitPct"]) / 100,
        )
        run_records[parameter_key] = run_result
        rows.append(summary)

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
