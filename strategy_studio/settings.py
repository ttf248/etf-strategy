from __future__ import annotations
"""策略研究运行配置。

这里集中存放会同时影响 CLI、工作流、报告和测试的默认值。
这样后续新增实盘口径、批量研究或多周期配置时，不需要在多个模块里
分别维护同一组魔法数字。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from strategy_studio.config import (
    DEFAULT_MINUTE_INTERVAL,
    DEFAULT_MINUTE_OUTPUT_DIR,
    DEFAULT_MINUTE_PERIOD,
    DEFAULT_MINUTE_REPORT_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_DIR,
)


WorkflowMode = Literal["daily", "intraday"]
ExecutionProfile = Literal["research", "realistic"]
GridMode = Literal["cash"]
LeftSidePolicy = Literal["hold", "force_exit", "both"]
StrategyKind = Literal[
    "grid",
    "dca",
    "daily_rebound",
    "minute_rebound",
    "minute_rebound_with_fade_filter",
    "minute_index_grid_retrace",
]

DEFAULT_VALIDATION_START = "2026-01-01"
DEFAULT_LOOKBACK_DAYS = 120
DEFAULT_VALIDATION_RATIO = 0.25
DEFAULT_WALK_FORWARD_WINDOW_COUNT = 3
DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE = 20
DEFAULT_JOBS = 8

DAILY_SPACINGS = (0.03, 0.04, 0.05, 0.06, 0.07)
DAILY_GRID_COUNTS = (4, 5, 6, 7)
DAILY_TAKE_PROFITS = (0.03, 0.05, 0.07)

INTRADAY_SPACINGS = (0.01, 0.015, 0.02, 0.03, 0.04)
INTRADAY_GRID_COUNTS = (4, 5, 6, 7)
INTRADAY_TAKE_PROFITS = (0.01, 0.015, 0.02, 0.03)

DAILY_REBOUND_RSI_WINDOWS = (6, 8, 10, 14)
DAILY_REBOUND_RSI_ENTRIES = (20.0, 25.0, 30.0, 35.0)
DAILY_REBOUND_MA_WINDOWS = (10, 20)
DAILY_REBOUND_DEVIATIONS = (-8.0, -6.0, -4.0)
DAILY_REBOUND_TAKE_PROFITS = (3.0, 5.0, 8.0)
DAILY_REBOUND_STOP_LOSS_ATRS = (1.5, 2.0, 2.5)
DAILY_REBOUND_MAX_HOLD_BARS = (5, 8, 10)

MINUTE_REBOUND_LOOKBACK_BARS = (8, 12)
MINUTE_REBOUND_DROP_ENTRIES = (-2.0, -1.5)
MINUTE_REBOUND_RSI_ENTRIES = (20.0, 25.0)
MINUTE_REBOUND_TAKE_PROFITS = (0.6, 0.8, 1.0)
MINUTE_REBOUND_STOP_LOSSES = (0.8, 1.0)
MINUTE_REBOUND_MAX_HOLD_BARS = (4, 8)
MINUTE_REBOUND_FADE_UPPER_SHADOWS = (1.0, 1.5)
MINUTE_REBOUND_FADE_BLOCK_BARS = (2,)

DCA_INVESTMENT_AMOUNTS = (5000.0, 10000.0)
DCA_FREQUENCIES = ("weekly", "monthly")
DCA_DAY_RULES = ("first_trading_day",)
DCA_MAX_POSITION_RATIOS = (0.95,)


@dataclass(frozen=True)
class ExecutionConfig:
    """单次回测的执行口径。

    `research` 保持当前简化撮合，适合做历史兼容和快速方向研究。
    `realistic` 会引入费用、滑点和基础风控字段，适合报告里更接近实盘的口径。
    """

    profile: ExecutionProfile = "research"
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    max_position_ratio: float = 1.0
    stop_loss_pct: float = 0.0
    cooldown_bars: int = 0
    benchmark: str = "buy_hold"
    grid_mode: GridMode = "cash"
    left_side_policy: LeftSidePolicy = "both"
    force_exit_loss_pct: float = 0.05


@dataclass(frozen=True)
class WorkflowSpec:
    """工作流规格，供 CLI 和工作流层共享。

    这里不直接执行回测，只描述“用什么数据、什么周期、什么参数空间、什么
    执行口径”运行，避免日线和分钟线在多个函数里重复分支。
    """

    mode: WorkflowMode
    interval: str
    data_path: Path
    symbol: str | None
    output_dir: Path
    report_dir: Path
    validation_start: str = DEFAULT_VALIDATION_START
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    validation_ratio: float = DEFAULT_VALIDATION_RATIO
    spacings: tuple[float, ...] = field(default_factory=tuple)
    grid_counts: tuple[int, ...] = field(default_factory=tuple)
    take_profits: tuple[float, ...] = field(default_factory=tuple)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    wf_window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT
    wf_min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE
    jobs: int = DEFAULT_JOBS
    cache_dir: Path | None = None


def default_execution_config(profile: ExecutionProfile = "research") -> ExecutionConfig:
    """返回默认执行口径。"""
    if profile == "realistic":
        return ExecutionConfig(
            profile="realistic",
            commission_bps=8.0,
            slippage_bps=2.0,
            max_position_ratio=0.95,
            stop_loss_pct=0.20,
            cooldown_bars=5,
            benchmark="buy_hold",
            grid_mode="cash",
            left_side_policy="both",
            force_exit_loss_pct=0.05,
        )
    return ExecutionConfig()


def build_execution_config(
    profile: ExecutionProfile,
    commission_bps: float | None = None,
    slippage_bps: float | None = None,
    max_position_ratio: float | None = None,
    stop_loss_pct: float | None = None,
    cooldown_bars: int | None = None,
    benchmark: str | None = None,
    grid_mode: GridMode | None = None,
    left_side_policy: LeftSidePolicy | None = None,
    force_exit_loss_pct: float | None = None,
) -> ExecutionConfig:
    """基于默认口径叠加命令行显式覆盖值。"""
    base = default_execution_config(profile)
    return ExecutionConfig(
        profile=profile,
        commission_bps=base.commission_bps if commission_bps is None else commission_bps,
        slippage_bps=base.slippage_bps if slippage_bps is None else slippage_bps,
        max_position_ratio=base.max_position_ratio if max_position_ratio is None else max_position_ratio,
        stop_loss_pct=base.stop_loss_pct if stop_loss_pct is None else stop_loss_pct,
        cooldown_bars=base.cooldown_bars if cooldown_bars is None else cooldown_bars,
        benchmark=base.benchmark if benchmark is None else benchmark,
        grid_mode=base.grid_mode if grid_mode is None else grid_mode,
        left_side_policy=base.left_side_policy if left_side_policy is None else left_side_policy,
        force_exit_loss_pct=base.force_exit_loss_pct if force_exit_loss_pct is None else force_exit_loss_pct,
    )


def default_parameter_space(mode: WorkflowMode) -> tuple[tuple[float, ...], tuple[int, ...], tuple[float, ...]]:
    """按周期返回默认寻参空间。"""
    if mode == "intraday":
        return INTRADAY_SPACINGS, INTRADAY_GRID_COUNTS, INTRADAY_TAKE_PROFITS
    return DAILY_SPACINGS, DAILY_GRID_COUNTS, DAILY_TAKE_PROFITS


def default_output_dir(mode: WorkflowMode) -> Path:
    """按周期返回默认中间结果目录。"""
    return DEFAULT_MINUTE_OUTPUT_DIR if mode == "intraday" else DEFAULT_OUTPUT_DIR


def default_report_dir(mode: WorkflowMode) -> Path:
    """按周期返回默认报告目录。"""
    return DEFAULT_MINUTE_REPORT_DIR if mode == "intraday" else DEFAULT_REPORT_DIR


def default_interval_and_period(mode: WorkflowMode) -> tuple[str, str | None]:
    """按工作流模式返回默认周期与下载窗口。"""
    if mode == "intraday":
        return DEFAULT_MINUTE_INTERVAL, DEFAULT_MINUTE_PERIOD
    return "1d", None
