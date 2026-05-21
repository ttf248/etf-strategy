from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf
from loguru import logger


STANDARD_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
CHART_API_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """将 yfinance 返回的多级列转换为单级列。"""
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    return frame


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """标准化为回测统一使用的 OHLCV 结构。"""
    normalized = _flatten_columns(frame).copy()

    if normalized.empty:
        raise ValueError("Yahoo 返回空数据，无法继续处理。")

    missing_columns = [name for name in ["Open", "High", "Low", "Close", "Volume"] if name not in normalized.columns]
    if missing_columns:
        raise ValueError(f"缺少必要字段: {missing_columns}")

    normalized = normalized[["Open", "High", "Low", "Close", "Volume"]]
    normalized.index = pd.to_datetime(normalized.index).tz_localize(None)
    normalized = normalized.sort_index()
    normalized = normalized.loc[~normalized.index.duplicated(keep="last")]
    normalized = normalized.dropna(subset=["Open", "High", "Low", "Close"])

    normalized["Volume"] = normalized["Volume"].fillna(0).astype("int64")
    normalized.reset_index(inplace=True)
    normalized.rename(columns={"index": "Date"}, inplace=True)
    normalized["Date"] = normalized["Date"].dt.strftime("%Y-%m-%d")
    return normalized[STANDARD_COLUMNS]


def _build_proxies(proxy: str | None) -> dict[str, str] | None:
    """按 requests 约定构造代理配置。"""
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _to_epoch_seconds(date_text: str, inclusive_end: bool = False) -> int:
    """将 YYYY-MM-DD 转成 Unix 时间戳。"""
    date_value = datetime.strptime(date_text, "%Y-%m-%d")
    if inclusive_end:
        date_value = date_value + timedelta(days=1)
    return int(date_value.timestamp())


def _load_from_yfinance(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """优先尝试 yfinance，适合无需代理的环境。"""
    data = yf.download(
        symbol,
        start=start_date,
        end=end_date,
        interval="1d",
        auto_adjust=True,
        progress=False,
        actions=False,
        threads=False,
    )
    return normalize_ohlcv(data)


def _apply_adjustment(frame: pd.DataFrame, adj_close: list[float] | None) -> pd.DataFrame:
    """使用 Adj Close 比例近似复权 OHLC。"""
    if not adj_close:
        return frame

    adjusted = frame.copy()
    adjusted["Adj Close"] = adj_close
    close_values = adjusted["Close"].replace(0, pd.NA)
    factor = adjusted["Adj Close"] / close_values
    factor = factor.fillna(1.0)

    for column in ["Open", "High", "Low", "Close"]:
        adjusted[column] = adjusted[column] * factor
    return adjusted.drop(columns=["Adj Close"])


def _load_from_chart_api(symbol: str, start_date: str, end_date: str, proxy: str | None = None) -> pd.DataFrame:
    """使用 Yahoo Chart API 下载数据，支持显式代理。"""
    params = {
        "period1": _to_epoch_seconds(start_date),
        "period2": _to_epoch_seconds(end_date, inclusive_end=True),
        "interval": "1d",
        "includePrePost": "false",
        "events": "div,splits",
    }
    logger.info("yfinance 不可用，改用 Yahoo Chart API。")
    response = requests.get(
        CHART_API_URL.format(symbol=symbol),
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        proxies=_build_proxies(proxy),
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    result = payload.get("chart", {}).get("result", [])
    if not result:
        error_info = payload.get("chart", {}).get("error")
        raise ValueError(f"Yahoo Chart API 未返回数据: {error_info}")

    item: dict[str, Any] = result[0]
    quote = item["indicators"]["quote"][0]
    timestamps = item.get("timestamp", [])
    timezone_name = item.get("meta", {}).get("exchangeTimezoneName", "Asia/Hong_Kong")

    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(timezone_name).tz_localize(None),
            "Open": quote.get("open", []),
            "High": quote.get("high", []),
            "Low": quote.get("low", []),
            "Close": quote.get("close", []),
            "Volume": quote.get("volume", []),
        }
    )

    adjclose = item.get("indicators", {}).get("adjclose", [])
    if adjclose:
        frame = _apply_adjustment(frame, adjclose[0].get("adjclose"))

    frame = frame.set_index("Date")
    return normalize_ohlcv(frame)


def download_daily_bars(symbol: str, start_date: str, end_date: str, proxy: str | None = None) -> pd.DataFrame:
    """下载 Yahoo Finance 日线数据并返回标准化结果。"""
    logger.info("开始下载 {} 的 Yahoo 日线数据，区间 {} 至 {}", symbol, start_date, end_date)

    try:
        normalized = _load_from_yfinance(symbol, start_date, end_date)
        logger.info("通过 yfinance 下载完成，共 {} 条记录。", len(normalized))
        return normalized
    except Exception as exc:
        logger.warning("yfinance 下载失败: {}", exc)

    normalized = _load_from_chart_api(symbol, start_date, end_date, proxy=proxy)
    logger.info("通过 Yahoo Chart API 下载完成，共 {} 条记录。", len(normalized))
    return normalized


def save_daily_bars(frame: pd.DataFrame, output_path: str | Path) -> Path:
    """保存标准化数据到 CSV。"""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, encoding="utf-8-sig")
    logger.info("标准化数据已写入 {}", target)
    return target
