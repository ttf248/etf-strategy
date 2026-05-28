from __future__ import annotations
"""策略注册表。

新增策略时优先在这里声明元数据、参数空间和运行入口。workflow、模板服务、
CLI 和前端可以围绕这些元数据收敛，避免继续在多个模块里维护同一组
`strategy_kind` 分支。
"""

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from strategy_studio.settings import (
    DAILY_GRID_COUNTS,
    DAILY_REBOUND_DEVIATIONS,
    DAILY_REBOUND_MA_WINDOWS,
    DAILY_REBOUND_MAX_HOLD_BARS,
    DAILY_REBOUND_RSI_ENTRIES,
    DAILY_REBOUND_RSI_WINDOWS,
    DAILY_REBOUND_STOP_LOSS_ATRS,
    DAILY_REBOUND_TAKE_PROFITS,
    DAILY_SPACINGS,
    DAILY_TAKE_PROFITS,
    DCA_DAY_RULES,
    DCA_FREQUENCIES,
    DCA_INVESTMENT_AMOUNTS,
    DCA_MAX_POSITION_RATIOS,
    INTRADAY_GRID_COUNTS,
    INTRADAY_SPACINGS,
    INTRADAY_TAKE_PROFITS,
    MINUTE_REBOUND_DROP_ENTRIES,
    MINUTE_REBOUND_FADE_BLOCK_BARS,
    MINUTE_REBOUND_FADE_UPPER_SHADOWS,
    MINUTE_REBOUND_LOOKBACK_BARS,
    MINUTE_REBOUND_MAX_HOLD_BARS,
    MINUTE_REBOUND_RSI_ENTRIES,
    MINUTE_REBOUND_STOP_LOSSES,
    MINUTE_REBOUND_TAKE_PROFITS,
    ExecutionConfig,
)
from strategy_studio.strategy.dca import optimize_dca_parameters, run_dca_backtest
from strategy_studio.strategy.grid import optimize_grid_parameters, run_grid_backtest
from strategy_studio.strategy.index_grid import run_index_grid_backtest
from strategy_studio.strategy.rebound import optimize_rebound_parameters, run_rebound_backtest


ParameterKind = str


@dataclass(frozen=True)
class ParameterFieldSpec:
    key: str
    label: str
    kind: ParameterKind


@dataclass(frozen=True)
class StrategySpec:
    kind: str
    display_name: str
    signal_family: str
    supported_intervals: tuple[str, ...] | None
    parameter_fields: tuple[ParameterFieldSpec, ...]
    default_parameter_space: Callable[[str], dict[str, object]]
    optimize: Callable[..., tuple[pd.DataFrame, dict[str, object]]]
    run_once: Callable[..., dict[str, object]]
    extract_params: Callable[[dict[str, object]], dict[str, object]]

    def supports_interval(self, interval: str) -> bool:
        if self.supported_intervals is None:
            return True
        if "__intraday__" in self.supported_intervals:
            return interval != "1d"
        return interval in self.supported_intervals


def _normalize_values(values: object, field: ParameterFieldSpec) -> list[object]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{field.key} 必须是非空数组。")
    if field.kind == "int":
        return [int(item) for item in values]
    if field.kind == "float":
        return [float(item) for item in values]
    if field.kind == "string":
        return [str(item).strip() for item in values if str(item).strip()]
    raise ValueError(f"未知参数类型: {field.kind}")


def normalize_parameter_space_for_strategy(
    strategy_kind: str,
    parameter_space: dict[str, object] | None,
    interval: str,
) -> dict[str, object] | None:
    if parameter_space is None:
        return None
    if not isinstance(parameter_space, dict):
        raise ValueError("parameter_space 必须是对象。")
    spec = get_strategy_spec(strategy_kind)
    validate_strategy_interval(strategy_kind, interval)
    normalized: dict[str, object] = {}
    for field in spec.parameter_fields:
        normalized[field.key] = _normalize_values(parameter_space.get(field.key), field)
    return normalized


def default_parameter_space_for_strategy(strategy_kind: str, interval: str) -> dict[str, object]:
    spec = get_strategy_spec(strategy_kind)
    validate_strategy_interval(strategy_kind, interval)
    return spec.default_parameter_space(interval)


def validate_strategy_interval(strategy_kind: str, interval: str) -> None:
    spec = get_strategy_spec(strategy_kind)
    if not spec.supports_interval(interval):
        if spec.supported_intervals == ("__intraday__",):
            raise ValueError(f"{strategy_kind} 模板不能绑定 1d 周期。")
        raise ValueError(f"{strategy_kind} 不支持 {interval} 周期。")


def _grid_parameter_space(interval: str) -> dict[str, object]:
    if interval == "1d":
        return {
            "spacings": [float(item) for item in DAILY_SPACINGS],
            "grid_counts": [int(item) for item in DAILY_GRID_COUNTS],
            "take_profits": [float(item) for item in DAILY_TAKE_PROFITS],
        }
    return {
        "spacings": [float(item) for item in INTRADAY_SPACINGS],
        "grid_counts": [int(item) for item in INTRADAY_GRID_COUNTS],
        "take_profits": [float(item) for item in INTRADAY_TAKE_PROFITS],
    }


def _daily_rebound_parameter_space(interval: str) -> dict[str, object]:
    return {
        "rsi_window": [int(item) for item in DAILY_REBOUND_RSI_WINDOWS],
        "rsi_entry": [float(item) for item in DAILY_REBOUND_RSI_ENTRIES],
        "ma_window": [int(item) for item in DAILY_REBOUND_MA_WINDOWS],
        "deviation_entry_pct": [float(item) for item in DAILY_REBOUND_DEVIATIONS],
        "take_profit_pct": [float(item) for item in DAILY_REBOUND_TAKE_PROFITS],
        "stop_loss_atr": [float(item) for item in DAILY_REBOUND_STOP_LOSS_ATRS],
        "max_hold_bars": [int(item) for item in DAILY_REBOUND_MAX_HOLD_BARS],
    }


def _minute_rebound_parameter_space(interval: str) -> dict[str, object]:
    return {
        "lookback_bars": [int(item) for item in MINUTE_REBOUND_LOOKBACK_BARS],
        "drop_entry_pct": [float(item) for item in MINUTE_REBOUND_DROP_ENTRIES],
        "rsi_entry": [float(item) for item in MINUTE_REBOUND_RSI_ENTRIES],
        "take_profit_pct": [float(item) for item in MINUTE_REBOUND_TAKE_PROFITS],
        "stop_loss_pct": [float(item) for item in MINUTE_REBOUND_STOP_LOSSES],
        "max_hold_bars": [int(item) for item in MINUTE_REBOUND_MAX_HOLD_BARS],
    }


def _minute_rebound_fade_parameter_space(interval: str) -> dict[str, object]:
    space = _minute_rebound_parameter_space(interval)
    space["fade_filter_upper_shadow_pct"] = [float(item) for item in MINUTE_REBOUND_FADE_UPPER_SHADOWS]
    space["fade_filter_block_bars"] = [int(item) for item in MINUTE_REBOUND_FADE_BLOCK_BARS]
    return space


def _dca_parameter_space(interval: str) -> dict[str, object]:
    return {
        "investment_amount": [float(item) for item in DCA_INVESTMENT_AMOUNTS],
        "frequency": [str(item) for item in DCA_FREQUENCIES],
        "day_rule": [str(item) for item in DCA_DAY_RULES],
        "max_position_ratio": [float(item) for item in DCA_MAX_POSITION_RATIOS],
    }


def _empty_parameter_space(interval: str) -> dict[str, object]:
    return {}


def _optimize_grid(**kwargs: object) -> tuple[pd.DataFrame, dict[str, object]]:
    space = kwargs.pop("parameter_space")
    return optimize_grid_parameters(
        spacings=[float(item) for item in space["spacings"]],
        grid_counts=[int(item) for item in space["grid_counts"]],
        take_profits=[float(item) for item in space["take_profits"]],
        **kwargs,
    )


def _run_grid_once(params: dict[str, object], **kwargs: object) -> dict[str, object]:
    return run_grid_backtest(
        grid_spacing_pct=float(params["grid_spacing_pct"]),
        grid_count=int(params["grid_count"]),
        take_profit_pct=float(params["take_profit_pct"]),
        **kwargs,
    )


def _extract_grid_params(summary: dict[str, object]) -> dict[str, object]:
    return {
        "grid_spacing_pct": float(summary["GridSpacingPct"]) / 100,
        "grid_count": int(summary["GridCount"]),
        "take_profit_pct": float(summary["TakeProfitPct"]) / 100,
    }


def _optimize_rebound(strategy_kind: str, **kwargs: object) -> tuple[pd.DataFrame, dict[str, object]]:
    return optimize_rebound_parameters(strategy_kind=strategy_kind, **kwargs)


def _run_rebound_once(strategy_kind: str, params: dict[str, object], **kwargs: object) -> dict[str, object]:
    return run_rebound_backtest(strategy_kind=strategy_kind, params=params, **kwargs)


def _extract_rebound_params(summary: dict[str, object]) -> dict[str, object]:
    strategy_kind = str(summary.get("StrategyKind", "daily_rebound"))
    if strategy_kind == "daily_rebound":
        keys = (
            "rsi_window",
            "rsi_entry",
            "ma_window",
            "deviation_entry_pct",
            "take_profit_pct",
            "stop_loss_atr",
            "max_hold_bars",
        )
    else:
        keys = (
            "lookback_bars",
            "drop_entry_pct",
            "rsi_entry",
            "take_profit_pct",
            "stop_loss_pct",
            "max_hold_bars",
            "fade_filter_upper_shadow_pct",
            "fade_filter_block_bars",
        )
    return {key: summary[key] for key in keys if key in summary}


def _optimize_index_grid(**kwargs: object) -> tuple[pd.DataFrame, dict[str, object]]:
    kwargs.pop("parameter_space", None)
    kwargs.pop("wf_window_count", None)
    kwargs.pop("wf_min_window_size", None)
    kwargs.pop("jobs", None)
    kwargs.pop("cache_dir", None)
    run = run_index_grid_backtest(**kwargs)
    return pd.DataFrame([run["summary"]]), run


def _run_index_grid_once(params: dict[str, object], **kwargs: object) -> dict[str, object]:
    return run_index_grid_backtest(**kwargs)


def _extract_empty_params(summary: dict[str, object]) -> dict[str, object]:
    return {}


def _optimize_dca(**kwargs: object) -> tuple[pd.DataFrame, dict[str, object]]:
    return optimize_dca_parameters(**kwargs)


def _run_dca_once(params: dict[str, object], **kwargs: object) -> dict[str, object]:
    return run_dca_backtest(params=params, **kwargs)


def _extract_dca_params(summary: dict[str, object]) -> dict[str, object]:
    return {
        "investment_amount": float(summary["investment_amount"]),
        "frequency": str(summary["frequency"]),
        "day_rule": str(summary["day_rule"]),
        "max_position_ratio": float(summary["max_position_ratio"]),
    }


STRATEGY_SPECS: dict[str, StrategySpec] = {
    "grid": StrategySpec(
        kind="grid",
        display_name="网格",
        signal_family="grid",
        supported_intervals=None,
        parameter_fields=(
            ParameterFieldSpec("spacings", "网格间距", "float"),
            ParameterFieldSpec("grid_counts", "网格层数", "int"),
            ParameterFieldSpec("take_profits", "止盈比例", "float"),
        ),
        default_parameter_space=_grid_parameter_space,
        optimize=_optimize_grid,
        run_once=_run_grid_once,
        extract_params=_extract_grid_params,
    ),
    "dca": StrategySpec(
        kind="dca",
        display_name="定投",
        signal_family="dca",
        supported_intervals=("1d",),
        parameter_fields=(
            ParameterFieldSpec("investment_amount", "每期金额", "float"),
            ParameterFieldSpec("frequency", "定投频率", "string"),
            ParameterFieldSpec("day_rule", "触发日规则", "string"),
            ParameterFieldSpec("max_position_ratio", "最大仓位", "float"),
        ),
        default_parameter_space=_dca_parameter_space,
        optimize=_optimize_dca,
        run_once=_run_dca_once,
        extract_params=_extract_dca_params,
    ),
    "daily_rebound": StrategySpec(
        kind="daily_rebound",
        display_name="日线超跌反弹",
        signal_family="rebound",
        supported_intervals=("1d",),
        parameter_fields=(
            ParameterFieldSpec("rsi_window", "RSI 窗口", "int"),
            ParameterFieldSpec("rsi_entry", "RSI 入场", "float"),
            ParameterFieldSpec("ma_window", "均线窗口", "int"),
            ParameterFieldSpec("deviation_entry_pct", "偏离入场", "float"),
            ParameterFieldSpec("take_profit_pct", "止盈比例", "float"),
            ParameterFieldSpec("stop_loss_atr", "ATR 止损", "float"),
            ParameterFieldSpec("max_hold_bars", "最大持仓 Bar", "int"),
        ),
        default_parameter_space=_daily_rebound_parameter_space,
        optimize=lambda **kwargs: _optimize_rebound("daily_rebound", **kwargs),
        run_once=lambda params, **kwargs: _run_rebound_once("daily_rebound", params, **kwargs),
        extract_params=_extract_rebound_params,
    ),
    "minute_rebound": StrategySpec(
        kind="minute_rebound",
        display_name="分钟急跌反抽",
        signal_family="rebound",
        supported_intervals=("__intraday__",),
        parameter_fields=(
            ParameterFieldSpec("lookback_bars", "回看 Bar", "int"),
            ParameterFieldSpec("drop_entry_pct", "跌幅入场", "float"),
            ParameterFieldSpec("rsi_entry", "RSI 入场", "float"),
            ParameterFieldSpec("take_profit_pct", "止盈比例", "float"),
            ParameterFieldSpec("stop_loss_pct", "止损比例", "float"),
            ParameterFieldSpec("max_hold_bars", "最大持仓 Bar", "int"),
        ),
        default_parameter_space=_minute_rebound_parameter_space,
        optimize=lambda **kwargs: _optimize_rebound("minute_rebound", **kwargs),
        run_once=lambda params, **kwargs: _run_rebound_once("minute_rebound", params, **kwargs),
        extract_params=_extract_rebound_params,
    ),
    "minute_rebound_with_fade_filter": StrategySpec(
        kind="minute_rebound_with_fade_filter",
        display_name="分钟反抽+冲高回落过滤",
        signal_family="rebound",
        supported_intervals=("__intraday__",),
        parameter_fields=(
            ParameterFieldSpec("lookback_bars", "回看 Bar", "int"),
            ParameterFieldSpec("drop_entry_pct", "跌幅入场", "float"),
            ParameterFieldSpec("rsi_entry", "RSI 入场", "float"),
            ParameterFieldSpec("take_profit_pct", "止盈比例", "float"),
            ParameterFieldSpec("stop_loss_pct", "止损比例", "float"),
            ParameterFieldSpec("max_hold_bars", "最大持仓 Bar", "int"),
            ParameterFieldSpec("fade_filter_upper_shadow_pct", "上影线过滤", "float"),
            ParameterFieldSpec("fade_filter_block_bars", "过滤屏蔽 Bar", "int"),
        ),
        default_parameter_space=_minute_rebound_fade_parameter_space,
        optimize=lambda **kwargs: _optimize_rebound("minute_rebound_with_fade_filter", **kwargs),
        run_once=lambda params, **kwargs: _run_rebound_once("minute_rebound_with_fade_filter", params, **kwargs),
        extract_params=_extract_rebound_params,
    ),
    "minute_index_grid_retrace": StrategySpec(
        kind="minute_index_grid_retrace",
        display_name="指数回落反弹网格",
        signal_family="index_grid_retrace",
        supported_intervals=("1m",),
        parameter_fields=(),
        default_parameter_space=_empty_parameter_space,
        optimize=_optimize_index_grid,
        run_once=_run_index_grid_once,
        extract_params=_extract_empty_params,
    ),
}


def get_strategy_spec(strategy_kind: str) -> StrategySpec:
    try:
        return STRATEGY_SPECS[strategy_kind]
    except KeyError as exc:
        raise ValueError(f"未知策略类型: {strategy_kind}") from exc


def strategy_choices() -> list[str]:
    return list(STRATEGY_SPECS)


def strategy_display_name(strategy_kind: str) -> str:
    return get_strategy_spec(strategy_kind).display_name


def compare_strategy_kinds(interval: str) -> list[str]:
    if interval == "1d":
        return ["grid", "dca", "daily_rebound"]
    return ["grid", "minute_rebound", "minute_rebound_with_fade_filter"]
