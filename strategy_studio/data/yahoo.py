"""Yahoo 行情下载与标准化。

这里把下载链路统一封装成：
- 只通过 yfinance 访问 Yahoo Finance
- 下载必须显式配置代理
- Yahoo 下载失败时立即抛错停止流程
- 最终都转换成项目内部统一的 OHLCV CSV 结构
"""

from pathlib import Path

import pandas as pd
import yfinance as yf
from loguru import logger

from strategy_studio.config import DEFAULT_RUNTIME_DATA_DIR


STANDARD_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
DEFAULT_DAILY_PERIOD = "max"


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


def _load_from_yfinance(
    symbol: str,
    interval: str,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str | None = None,
    proxy: str | None = None,
) -> pd.DataFrame:
    """通过 yfinance 下载 Yahoo 行情。"""
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


def build_default_output_path(symbol: str, interval: str) -> Path:
    """根据标的和周期生成默认输出路径。"""
    normalized_symbol = symbol.lower().replace(".", "_")
    normalized_interval = interval.lower().replace(" ", "")
    return DEFAULT_RUNTIME_DATA_DIR / f"{normalized_symbol}_{normalized_interval}.csv"


def is_intraday_interval(interval: str) -> bool:
    """判断是否为分钟级周期。"""
    return interval in INTRADAY_INTERVALS


def merge_price_bars(existing_frame: pd.DataFrame, new_frame: pd.DataFrame, interval: str = "1d") -> pd.DataFrame:
    """按时间戳合并两份标准化行情，重复记录以新数据覆盖旧数据。"""
    existing = existing_frame.loc[:, STANDARD_COLUMNS].copy()
    incoming = new_frame.loc[:, STANDARD_COLUMNS].copy()
    existing["Date"] = pd.to_datetime(existing["Date"])
    incoming["Date"] = pd.to_datetime(incoming["Date"])

    merged = (
        pd.concat([existing, incoming], ignore_index=True)
        .drop_duplicates(subset=["Date"], keep="last")
        .sort_values("Date")
        .reset_index(drop=True)
    )
    if interval in INTRADAY_INTERVALS:
        merged["Date"] = merged["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        merged["Date"] = merged["Date"].dt.strftime("%Y-%m-%d")
    merged["Volume"] = merged["Volume"].fillna(0).astype("int64")
    return merged[STANDARD_COLUMNS]


def download_price_bars(
    symbol: str,
    interval: str = "1d",
    start_date: str | None = None,
    end_date: str | None = None,
    period: str | None = None,
    proxy: str | None = None,
) -> pd.DataFrame:
    """下载 Yahoo Finance 行情并返回标准化结果。"""
    if not proxy or not proxy.strip():
        raise ValueError("下载 Yahoo 行情必须配置代理，请通过 --proxy 或 STRATEGY_STUDIO_PROXY 提供代理地址。")
    if is_intraday_interval(interval) and not period:
        raise ValueError("分钟 K 线请通过 period 参数下载，例如 5d 或 60d。")
    if not is_intraday_interval(interval) and not period and not start_date and not end_date:
        period = DEFAULT_DAILY_PERIOD

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
    except Exception as exc:
        raise ValueError(f"Yahoo 行情下载失败，流程已停止: {exc}") from exc

    logger.info("通过 yfinance 下载完成，共 {} 条记录。", len(normalized))
    return normalized


def save_price_bars(
    frame: pd.DataFrame,
    output_path: str | Path,
    interval: str = "1d",
    merge_with_existing: bool = False,
) -> Path:
    """保存标准化数据到 CSV。

    分钟线默认支持和本地历史做增量合并；
    日线也允许在已有全历史样本上继续并入新的重叠或新增日期。
    """
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    output_frame = frame.loc[:, STANDARD_COLUMNS].copy()
    if merge_with_existing and target.exists():
        existing = pd.read_csv(target, encoding="utf-8-sig")
        output_frame = merge_price_bars(existing, output_frame, interval=interval)
    output_frame.to_csv(target, index=False, encoding="utf-8-sig")
    logger.info("标准化数据已写入 {}", target)
    return target


def download_daily_bars(symbol: str, start_date: str, end_date: str, proxy: str | None = None) -> pd.DataFrame:
    """兼容旧接口的日线下载封装。"""
    return download_price_bars(symbol=symbol, interval="1d", start_date=start_date, end_date=end_date, proxy=proxy)


def save_daily_bars(frame: pd.DataFrame, output_path: str | Path) -> Path:
    """兼容旧接口的保存封装。"""
    return save_price_bars(frame, output_path, interval="1d")
