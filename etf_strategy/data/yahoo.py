"""Yahoo 行情下载与标准化。

这里把下载链路统一封装成：
- 优先走 yfinance
- 日线失败时回退到 Yahoo Chart API
- 最终都转换成项目内部统一的 OHLCV CSV 结构
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf
from loguru import logger


STANDARD_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
CHART_API_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}


def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """将 yfinance 返回的多级列转换为单级列。"""
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    return frame


def normalize_ohlcv(frame: pd.DataFrame, interval: str = "1d") -> pd.DataFrame:
    """标准化为回测统一使用的 OHLCV 结构。"""
    normalized = _flatten_columns(frame).copy()

    if normalized.empty:
        raise ValueError("Yahoo 返回空数据，无法继续处理。")

    missing_columns = [name for name in ["Open", "High", "Low", "Close", "Volume"] if name not in normalized.columns]
    if missing_columns:
        raise ValueError(f"缺少必要字段: {missing_columns}")

    normalized = normalized[["Open", "High", "Low", "Close", "Volume"]]
    # 回测层统一使用无时区索引，避免不同下载链路带来混合时区数据。
    normalized.index = pd.to_datetime(normalized.index).tz_localize(None)
    normalized = normalized.sort_index()
    normalized = normalized.loc[~normalized.index.duplicated(keep="last")]
    normalized = normalized.dropna(subset=["Open", "High", "Low", "Close"])

    normalized["Volume"] = normalized["Volume"].fillna(0).astype("int64")
    normalized.reset_index(inplace=True)
    normalized.rename(columns={"index": "Date", "Datetime": "Date"}, inplace=True)
    # 分钟线和日线用不同字符串格式，保证后续 parse_dates 时能还原粒度。
    if interval in INTRADAY_INTERVALS:
        normalized["Date"] = normalized["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
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


def _load_from_yfinance(
    symbol: str,
    interval: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str | None = None,
    proxy: str | None = None,
) -> pd.DataFrame:
    """优先尝试 yfinance，适合无需代理的环境。"""
    if proxy:
        yf.set_config(proxy=proxy)

    download_kwargs: dict[str, object] = {
        "interval": interval,
        "auto_adjust": True,
        "progress": False,
        "actions": False,
        "threads": False,
    }
    if period:
        download_kwargs["period"] = period
    else:
        download_kwargs["start"] = start_date
        download_kwargs["end"] = end_date

    data = yf.download(symbol, **download_kwargs)
    return normalize_ohlcv(data, interval=interval)


def _apply_adjustment(frame: pd.DataFrame, adj_close: list[float] | None) -> pd.DataFrame:
    """使用 Adj Close 比例近似复权 OHLC。

    Yahoo Chart API 在不同市场上未必直接给出完整复权 OHLC，
    这里用 Adj Close / Close 的比例做近似，优先统一项目口径。
    """
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
    """使用 Yahoo Chart API 下载数据，支持显式代理。

    当前只作为日线回退链路使用，分钟线仍依赖 yfinance。
    """
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
    return normalize_ohlcv(frame, interval="1d")


def build_default_output_path(symbol: str, interval: str) -> Path:
    """根据标的和周期生成默认输出路径。"""
    normalized_symbol = symbol.lower().replace(".", "_")
    normalized_interval = interval.lower().replace(" ", "")
    return Path("data/processed") / f"{normalized_symbol}_{normalized_interval}.csv"


def is_intraday_interval(interval: str) -> bool:
    """判断是否为分钟级周期。"""
    return interval in INTRADAY_INTERVALS


def download_price_bars(
    symbol: str,
    interval: str = "1d",
    start_date: str | None = None,
    end_date: str | None = None,
    period: str | None = None,
    proxy: str | None = None,
) -> pd.DataFrame:
    """下载 Yahoo Finance 行情并返回标准化结果。"""
    if is_intraday_interval(interval) and not period:
        raise ValueError("分钟 K 线请通过 period 参数下载，例如 5d 或 60d。")

    logger.info(
        "开始下载 {} 的 Yahoo 行情，interval={}，start={}，end={}，period={}",
        symbol,
        interval,
        start_date,
        end_date,
        period,
    )

    try:
        normalized = _load_from_yfinance(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            period=period,
            proxy=proxy,
        )
        logger.info("通过 yfinance 下载完成，共 {} 条记录。", len(normalized))
        return normalized
    except Exception as exc:
        # 这里不直接吞错返回空数据，而是仅在明确存在日线回退链路时继续尝试。
        logger.warning("yfinance 下载失败: {}", exc)

    if is_intraday_interval(interval):
        raise ValueError("分钟 K 线当前仅支持通过 yfinance 下载，请检查代理和 period 参数。")

    if not start_date or not end_date:
        raise ValueError("日线回退到 Yahoo Chart API 时必须提供 start_date 和 end_date。")

    normalized = _load_from_chart_api(symbol, start_date, end_date, proxy=proxy)
    logger.info("通过 Yahoo Chart API 下载完成，共 {} 条记录。", len(normalized))
    return normalized


def save_price_bars(frame: pd.DataFrame, output_path: str | Path) -> Path:
    """保存标准化数据到 CSV。"""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False, encoding="utf-8-sig")
    logger.info("标准化数据已写入 {}", target)
    return target


def download_daily_bars(symbol: str, start_date: str, end_date: str, proxy: str | None = None) -> pd.DataFrame:
    """兼容旧接口的日线下载封装。"""
    return download_price_bars(symbol=symbol, interval="1d", start_date=start_date, end_date=end_date, proxy=proxy)


def save_daily_bars(frame: pd.DataFrame, output_path: str | Path) -> Path:
    """兼容旧接口的保存封装。"""
    return save_price_bars(frame, output_path)
