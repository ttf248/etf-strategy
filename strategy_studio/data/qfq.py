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
    """把前复权区间映射回原始日线，输出标准 OHLCV DataFrame。"""
    normalized_raw = _normalize_raw_frame(raw_frame)
    normalized_segments = _normalize_segment_frame(segment_frame)
    if normalized_raw.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume", "Amount", "AdjustA", "AdjustB"])
    if normalized_segments.empty:
        raise ValueError("前复权区间为空，无法重算前复权日线。")

    row_dates = normalized_raw["_date_key"].to_numpy(dtype="U8")
    segment_start_dates = normalized_segments["_start_key"].to_numpy(dtype="U8")
    segment_end_dates = normalized_segments["_end_key"].to_numpy(dtype="U8")
    positions = np.searchsorted(segment_end_dates, row_dates, side="left")
    if (positions >= len(normalized_segments)).any():
        raise ValueError("存在超出公式区间覆盖范围的交易日。")

    matched_start = segment_start_dates[positions]
    matched_end = segment_end_dates[positions]
    if ((row_dates < matched_start) | (row_dates > matched_end)).any():
        raise ValueError("交易日没有匹配到连续前复权公式区间。")

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
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume", "Amount", "_date", "_date_key"])
    normalized = frame.copy()
    normalized["Date"] = pd.to_datetime(normalized["Date"]).dt.tz_localize(None)
    normalized = normalized.sort_values("Date").reset_index(drop=True)
    normalized["_date"] = normalized["Date"].dt.date
    normalized["_date_key"] = normalized["Date"].dt.strftime("%Y%m%d")
    if "Amount" not in normalized.columns:
        normalized["Amount"] = None
    return normalized


def _normalize_segment_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=SEGMENT_COLUMNS + ["_start_key", "_end_key"])
    normalized = frame.copy()
    normalized["start_date"] = pd.to_datetime(normalized["start_date"]).dt.date
    normalized["end_date"] = pd.to_datetime(normalized["end_date"]).dt.date
    normalized = normalized.sort_values(["start_date", "end_date"]).reset_index(drop=True)
    normalized["_start_key"] = normalized["start_date"].map(_date_to_key)
    normalized["_end_key"] = normalized["end_date"].map(_date_to_key)
    return normalized


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
