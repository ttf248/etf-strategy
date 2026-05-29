from __future__ import annotations

"""前复权公式区间与复权日线计算。"""

from datetime import date, timedelta

import numpy as np
import pandas as pd


PRICE_COLUMNS = ("Open", "High", "Low", "Close")
SEGMENT_COLUMNS = [
    "start_date",
    "end_date",
    "adjust_a",
    "adjust_b",
    "status",
    "payload_json",
]


class UnsupportedCorporateActionError(ValueError):
    """公司行动字段不足以构造可验证前复权公式时中止计算。"""


def build_qfq_segment_frame(
    raw_frame: pd.DataFrame,
    action_frame: pd.DataFrame,
) -> pd.DataFrame:
    """根据原始日线和公司行动构造连续的前复权公式区间。"""
    normalized_raw = _normalize_raw_frame(raw_frame)
    if normalized_raw.empty:
        return pd.DataFrame(columns=SEGMENT_COLUMNS)

    raw_start = normalized_raw["_date"].iloc[0]
    raw_end = normalized_raw["_date"].iloc[-1]
    grouped = _group_actions_by_ex_date(action_frame)
    if grouped.empty:
        return pd.DataFrame(
            [
                {
                    "start_date": raw_start,
                    "end_date": raw_end,
                    "adjust_a": 1.0,
                    "adjust_b": 0.0,
                    "status": "ready",
                    "payload_json": {"source": "none", "reason": "无公司行动", "event_count": 0},
                }
            ],
            columns=SEGMENT_COLUMNS,
        )

    event_dates = grouped["ex_date"].tolist()
    event_a = grouped["event_a"].to_numpy(dtype="float64")
    event_b = grouped["event_b"].to_numpy(dtype="float64")
    suffix_a, suffix_b = _build_suffix_affine_parameters(event_a, event_b)

    rows: list[dict[str, object]] = []
    for index in range(len(event_dates) + 1):
        start_date = raw_start if index == 0 else max(raw_start, event_dates[index - 1])
        end_date = raw_end if index == len(event_dates) else min(raw_end, event_dates[index] - timedelta(days=1))
        if start_date > end_date:
            continue
        rows.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "adjust_a": float(suffix_a[index]),
                "adjust_b": float(suffix_b[index]),
                "status": "ready",
                "payload_json": {
                    "source": "corporate_action_cn_exact",
                    "reason": "国内除权除息参考价仿射递推",
                    "event_count": int(len(event_dates) - index),
                },
            }
        )
    return pd.DataFrame(rows, columns=SEGMENT_COLUMNS)


def apply_qfq_segment_frame(
    raw_frame: pd.DataFrame,
    segment_frame: pd.DataFrame,
) -> pd.DataFrame:
    """把前复权区间映射回原始日线，输出标准 OHLCV DataFrame。

    这里参考 `corp_actions_cpp/src/market/qfq_dayline_builder.cpp` 的双指针思路：

    - 原始日线已按交易日升序；
    - 公式区间已按起止日升序；
    - 因此前复权日 K 不需要为每一行重新二分或扫描全部区间，
      只需线性推进当前区间指针即可完成 O(n + m) 匹配。
    """
    normalized_raw = _normalize_raw_frame(raw_frame)
    normalized_segments = _normalize_segment_frame(segment_frame)
    if normalized_raw.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume", "Amount", "AdjustA", "AdjustB"])
    if normalized_segments.empty:
        raise ValueError("前复权区间为空，无法重算前复权日线。")

    row_dates = normalized_raw["_date_ord"].to_numpy(dtype="int64")
    segment_start_dates = normalized_segments["_start_ord"].to_numpy(dtype="int64")
    segment_end_dates = normalized_segments["_end_ord"].to_numpy(dtype="int64")
    positions = _match_segment_positions_linear(row_dates, segment_start_dates, segment_end_dates)

    adjust_a = normalized_segments["adjust_a"].to_numpy(dtype="float64")[positions]
    adjust_b = normalized_segments["adjust_b"].to_numpy(dtype="float64")[positions]
    adjusted = normalized_raw.copy()
    for column in PRICE_COLUMNS:
        adjusted[column] = pd.to_numeric(adjusted[column], errors="coerce") * adjust_a + adjust_b
    adjusted["AdjustA"] = adjust_a
    adjusted["AdjustB"] = adjust_b
    return adjusted[["Date", "Open", "High", "Low", "Close", "Volume", "Amount", "AdjustA", "AdjustB"]]


def _normalize_raw_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume", "Amount", "_date", "_date_key", "_date_ord"])
    normalized = frame.copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"]).dt.tz_localize(None)
    normalized = normalized.sort_values("Date").reset_index(drop=True)
    normalized["_date"] = normalized["Date"].dt.date
    normalized["_date_key"] = normalized["Date"].dt.strftime("%Y%m%d")
    normalized["_date_ord"] = normalized["Date"].to_numpy(dtype="datetime64[D]").astype("int64")
    if "Amount" not in normalized.columns:
        normalized["Amount"] = None
    return normalized


def _normalize_segment_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=SEGMENT_COLUMNS + ["_start_key", "_end_key", "_start_ord", "_end_ord"])
    normalized = frame.copy()
    normalized["start_date"] = pd.to_datetime(normalized["start_date"]).dt.date
    normalized["end_date"] = pd.to_datetime(normalized["end_date"]).dt.date
    normalized = normalized.sort_values(["start_date", "end_date"]).reset_index(drop=True)
    normalized["_start_key"] = normalized["start_date"].map(_date_to_key)
    normalized["_end_key"] = normalized["end_date"].map(_date_to_key)
    normalized["_start_ord"] = pd.to_datetime(normalized["start_date"]).to_numpy(dtype="datetime64[D]").astype("int64")
    normalized["_end_ord"] = pd.to_datetime(normalized["end_date"]).to_numpy(dtype="datetime64[D]").astype("int64")
    return normalized


def _match_segment_positions_linear(
    row_dates: np.ndarray,
    segment_start_dates: np.ndarray,
    segment_end_dates: np.ndarray,
) -> np.ndarray:
    """按交易日和区间同时升序的前提做线性双指针匹配。"""
    if len(row_dates) == 0:
        return np.empty(0, dtype="int64")
    if len(segment_start_dates) == 0 or len(segment_end_dates) == 0:
        raise ValueError("前复权区间为空，无法匹配交易日。")

    positions = np.empty(len(row_dates), dtype="int64")
    row_index = 0
    segment_index = 0
    while row_index < len(row_dates):
        while segment_index + 1 < len(segment_end_dates) and row_dates[row_index] > segment_end_dates[segment_index]:
            segment_index += 1
        if row_dates[row_index] < segment_start_dates[segment_index] or row_dates[row_index] > segment_end_dates[segment_index]:
            raise ValueError("交易日没有匹配到连续前复权公式区间。")

        next_row_index = row_index + 1
        current_segment_end = segment_end_dates[segment_index]
        while next_row_index < len(row_dates) and row_dates[next_row_index] <= current_segment_end:
            next_row_index += 1
        positions[row_index:next_row_index] = segment_index
        row_index = next_row_index
    return positions


def _group_actions_by_ex_date(action_frame: pd.DataFrame) -> pd.DataFrame:
    if action_frame.empty:
        return pd.DataFrame(columns=["ex_date", "event_a", "event_b"])
    normalized = action_frame.copy()
    normalized["ex_date"] = pd.to_datetime(normalized["ex_date"], errors="coerce").dt.date
    normalized = normalized.dropna(subset=["ex_date"]).reset_index(drop=True)
    if normalized.empty:
        return pd.DataFrame(columns=["ex_date", "event_a", "event_b"])

    for column in (
        "cash_dividend",
        "stock_bonus_ratio",
        "stock_conversion_ratio",
        "rights_ratio",
        "rights_price",
    ):
        normalized[column] = pd.to_numeric(normalized.get(column, 0.0), errors="coerce").fillna(0.0)

    grouped = (
        normalized.groupby("ex_date", as_index=False)
        .agg(
            cash_dividend=("cash_dividend", "sum"),
            stock_bonus_ratio=("stock_bonus_ratio", "sum"),
            stock_conversion_ratio=("stock_conversion_ratio", "sum"),
            rights_ratio=("rights_ratio", "sum"),
            rights_price=("rights_price", "max"),
        )
        .sort_values("ex_date")
        .reset_index(drop=True)
    )

    unsupported: list[str] = []
    event_a_values: list[float] = []
    event_b_values: list[float] = []
    for row in grouped.to_dict(orient="records"):
        rights_ratio = float(row["rights_ratio"])
        rights_price = float(row["rights_price"])
        if rights_ratio > 0 and rights_price <= 0:
            unsupported.append(f"{_date_to_key(row['ex_date'])}:缺少配股价或配股比例")
            continue
        denominator = 1.0 + float(row["stock_bonus_ratio"]) + float(row["stock_conversion_ratio"]) + rights_ratio
        if denominator <= 0:
            unsupported.append(f"{_date_to_key(row['ex_date'])}:股份变动比例异常")
            continue
        event_a_values.append(1.0 / denominator)
        event_b_values.append((-float(row["cash_dividend"]) + rights_price * rights_ratio) / denominator)

    if unsupported:
        raise UnsupportedCorporateActionError(";".join(unsupported))
    grouped["event_a"] = event_a_values
    grouped["event_b"] = event_b_values
    return grouped[["ex_date", "event_a", "event_b"]]


def _build_suffix_affine_parameters(
    event_a: np.ndarray,
    event_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    suffix_a = np.ones(len(event_a) + 1, dtype="float64")
    suffix_b = np.zeros(len(event_a) + 1, dtype="float64")
    for index in range(len(event_a) - 1, -1, -1):
        suffix_a[index] = event_a[index] * suffix_a[index + 1]
        suffix_b[index] = suffix_a[index + 1] * event_b[index] + suffix_b[index + 1]
    return suffix_a, suffix_b


def _date_to_key(value: date) -> str:
    return value.strftime("%Y%m%d")
