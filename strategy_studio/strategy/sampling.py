from __future__ import annotations
"""样本窗口切分与时间格式化。

这些函数不依赖具体策略撮合细节，只负责把标准化行情切成样本内、
样本外和 walk-forward 稳健性窗口。
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy_studio.settings import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_VALIDATION_RATIO,
    DEFAULT_VALIDATION_START,
    DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
    DEFAULT_WALK_FORWARD_WINDOW_COUNT,
)


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


def build_sample_window(
    data: pd.DataFrame,
    validation_start: str = DEFAULT_VALIDATION_START,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> DeclineWindow:
    """构建日线样本内/样本外窗口摘要。"""
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


def build_intraday_sample_window(
    data: pd.DataFrame,
    validation_start: pd.Timestamp,
) -> DeclineWindow:
    """构建分钟线样本内/样本外窗口摘要。"""
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


def build_walk_forward_windows(
    data: pd.DataFrame,
    window_count: int = DEFAULT_WALK_FORWARD_WINDOW_COUNT,
    min_window_size: int = DEFAULT_WALK_FORWARD_MIN_WINDOW_SIZE,
) -> list[pd.DataFrame]:
    """把样本内区间按时间顺序拆成多个连续窗口。"""
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


def split_in_sample_and_validation(
    data: pd.DataFrame,
    validation_start: str = DEFAULT_VALIDATION_START,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> tuple[DeclineWindow, pd.DataFrame, pd.DataFrame]:
    """拆分日线样本内和样本外数据。"""
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
    """按最近分钟线样本拆分样本内和样本外数据。"""
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
