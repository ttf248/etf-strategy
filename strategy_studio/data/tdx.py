from __future__ import annotations

"""通达信日线/分钟线解析与增量签名。

当前仓库需要直接消费本地 `vipdoc` 二进制文件，并把不同周期统一写入
`market_data_series / market_data_bars`。这里提供：

- `.day` 日线解析
- `.lc1/.1` 1 分钟线解析
- `.lc5/.5` 5 分钟线解析
- 统一标准化列
- 基于 record size 的通用 manifest 增量判断
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import struct

import numpy as np
import pandas as pd


DAY_RECORD_SIZE = 32
MINUTE_RECORD_SIZE = 32
OVERLAP_ROWS = 5
TDX_COLUMNS = [
    "market",
    "symbol",
    "period",
    "datetime",
    "open",
    "high",
    "low",
    "close",
    "amount",
    "volume",
    "source_file",
    "source_mtime",
]
TDX_INTERVAL_SUFFIXES = {
    "1d": {".day"},
    "1m": {".lc1", ".1"},
    "5m": {".lc5", ".5"},
}
TDX_INTERVAL_PERIODS = {
    "1d": "day",
    "1m": "min1",
    "5m": "min5",
}
TDX_FILE_KINDS = {
    "1d": "tdx_day",
    "1m": "tdx_min1",
    "5m": "tdx_min5",
}
DAY_DTYPE = np.dtype(
    [
        ("date", "<u4"),
        ("open", "<u4"),
        ("high", "<u4"),
        ("low", "<u4"),
        ("close", "<u4"),
        ("amount", "<f4"),
        ("volume", "<u4"),
        ("reserved", "<u4"),
    ]
)
DS_DAY_DTYPE = np.dtype(
    [
        ("date", "<u4"),
        ("open", "<f4"),
        ("high", "<f4"),
        ("low", "<f4"),
        ("close", "<f4"),
        ("amount", "<f4"),
        ("volume", "<u4"),
        ("reserved", "<u4"),
    ]
)
DS_INDEX_PREFIXES = {"31", "33", "34", "44", "62", "74", "78"}
DS_FUND_PREFIXES = {"102"}
DS_DERIVATIVE_PREFIXES = {"4", "5", "6", "7", "8", "67"}
DS_FOREX_PREFIXES = {"10"}


@dataclass(frozen=True)
class SecurityTypeInfo:
    market: str
    symbol: str
    prefix: str
    security_type: str
    price_scale: float
    volume_scale: float


def interval_to_period(interval: str) -> str:
    normalized_interval = interval.strip().lower()
    if normalized_interval not in TDX_INTERVAL_PERIODS:
        raise ValueError(f"当前通达信导入只支持 1d、1m、5m，收到：{interval}")
    return TDX_INTERVAL_PERIODS[normalized_interval]


def file_kind_for_interval(interval: str) -> str:
    normalized_interval = interval.strip().lower()
    if normalized_interval not in TDX_FILE_KINDS:
        raise ValueError(f"当前通达信导入只支持 1d、1m、5m，收到：{interval}")
    return TDX_FILE_KINDS[normalized_interval]


def suffixes_for_interval(interval: str) -> set[str]:
    normalized_interval = interval.strip().lower()
    if normalized_interval not in TDX_INTERVAL_SUFFIXES:
        raise ValueError(f"当前通达信导入只支持 1d、1m、5m，收到：{interval}")
    return set(TDX_INTERVAL_SUFFIXES[normalized_interval])


def detect_period_from_suffix(suffix: str) -> str | None:
    normalized_suffix = suffix.strip().lower()
    for interval, suffixes in TDX_INTERVAL_SUFFIXES.items():
        if normalized_suffix in suffixes:
            return TDX_INTERVAL_PERIODS[interval]
    return None


def record_size_for_interval(interval: str) -> int:
    return DAY_RECORD_SIZE if interval.strip().lower() == "1d" else MINUTE_RECORD_SIZE


def record_size_for_suffix(suffix: str) -> int:
    period = detect_period_from_suffix(suffix)
    if period == "day":
        return DAY_RECORD_SIZE
    if period in {"min1", "min5"}:
        return MINUTE_RECORD_SIZE
    raise ValueError(f"未支持的通达信文件后缀：{suffix}")


def iter_tdx_files(vipdoc: Path, interval: str, symbol: str | None = None, limit: int | None = None) -> list[Path]:
    """按 interval 枚举通达信源文件。"""
    wanted_suffixes = suffixes_for_interval(interval)
    files = sorted(
        (
            path
            for path in vipdoc.rglob("*")
            if path.is_file() and path.suffix.lower() in wanted_suffixes
        ),
        key=lambda path: path.as_posix().lower(),
    )
    if symbol:
        normalized = symbol.strip().lower()
        files = [path for path in files if path.stem.lower() == normalized]
    if limit is not None:
        files = files[:limit]
    return files


def iter_tdx_day_files(vipdoc: Path, symbol: str | None = None, limit: int | None = None) -> list[Path]:
    """兼容旧调用方：枚举 `.day` 文件。"""
    return iter_tdx_files(vipdoc, interval="1d", symbol=symbol, limit=limit)


def detect_security_type(source_file: Path, vipdoc: Path | None = None) -> SecurityTypeInfo:
    """按通达信市场和代码前缀识别证券类型。"""
    market = infer_market_from_path(source_file, vipdoc)
    symbol = source_file.stem.lower()
    if market == "ds":
        return _detect_ds_security_type(symbol)
    prefix = symbol[2:5] if symbol.startswith("sh204") else symbol[2:4] if len(symbol) >= 4 else ""

    if market == "bj":
        return SecurityTypeInfo(market, symbol, prefix, "BJ_STOCK", 0.01, 1.0)
    if market == "sz":
        if prefix in {"00", "30"}:
            return SecurityTypeInfo(market, symbol, prefix, "SZ_A_STOCK", 0.01, 0.01)
        if prefix == "20":
            return SecurityTypeInfo(market, symbol, prefix, "SZ_B_STOCK", 0.01, 0.01)
        if prefix == "39":
            return SecurityTypeInfo(market, symbol, prefix, "SZ_INDEX", 0.01, 1.0)
        if prefix in {"15", "16", "18"}:
            return SecurityTypeInfo(market, symbol, prefix, "SZ_FUND", 0.001, 0.01)
        if prefix in {"10", "11", "12", "13", "14"}:
            return SecurityTypeInfo(market, symbol, prefix, "SZ_BOND", 0.001, 0.01)
    if market == "sh":
        if prefix in {"60", "68"}:
            return SecurityTypeInfo(market, symbol, prefix, "SH_A_STOCK", 0.01, 0.01)
        if prefix == "90":
            return SecurityTypeInfo(market, symbol, prefix, "SH_B_STOCK", 0.001, 0.01)
        if prefix in {"00", "88", "99"}:
            return SecurityTypeInfo(market, symbol, prefix, "SH_INDEX", 0.01, 1.0)
        if prefix in {"50", "51", "52", "53", "55", "56", "58"}:
            return SecurityTypeInfo(market, symbol, prefix, "SH_FUND", 0.001, 1.0)
        if prefix in {"01", "10", "11", "12", "13", "14", "20"} or symbol.startswith("sh204"):
            security_type = "SH_REPO" if symbol.startswith("sh204") else "SH_BOND"
            return SecurityTypeInfo(market, symbol, prefix, security_type, 0.001, 1.0)
    raise ValueError(f"未支持的证券类型：market={market or '-'} symbol={source_file.stem}")


def infer_market_from_path(source_file: Path, vipdoc: Path | None = None) -> str:
    if vipdoc is not None:
        try:
            return source_file.relative_to(vipdoc).parts[0].lower()
        except (ValueError, IndexError):
            pass
    stem = source_file.stem.lower()
    if stem.startswith(("sh", "sz", "bj")):
        return stem[:2]
    if "#" in stem:
        return "ds"
    return ""


def read_day_frame(source_file: Path, vipdoc: Path | None = None) -> pd.DataFrame:
    raw = source_file.read_bytes()
    if len(raw) % DAY_RECORD_SIZE != 0:
        raise ValueError(f".day 文件大小不是 {DAY_RECORD_SIZE} 字节整数倍，可能仍在写入：{source_file}")
    security = detect_security_type(source_file, vipdoc)
    return parse_day_records(raw, security)


def read_day_frame_tail(source_file: Path, start_offset: int, vipdoc: Path | None = None) -> pd.DataFrame:
    """按 32 字节边界读取 `.day` 尾部，用于安全增量追加。"""
    if start_offset < 0 or start_offset % DAY_RECORD_SIZE != 0:
        raise ValueError(f".day 增量读取偏移必须按 {DAY_RECORD_SIZE} 字节对齐：{start_offset}")
    with source_file.open("rb") as file:
        file.seek(start_offset)
        raw = file.read()
    if len(raw) % DAY_RECORD_SIZE != 0:
        raise ValueError(f".day 尾部大小不是 {DAY_RECORD_SIZE} 字节整数倍，可能仍在写入：{source_file}")
    security = detect_security_type(source_file, vipdoc)
    return parse_day_records(raw, security)


def read_minute_frame(source_file: Path) -> pd.DataFrame:
    raw = source_file.read_bytes()
    if len(raw) % MINUTE_RECORD_SIZE != 0:
        raise ValueError(f"分钟线文件大小不是 {MINUTE_RECORD_SIZE} 字节整数倍，可能仍在写入：{source_file}")
    return parse_minute_records(raw, source_file.suffix.lower())


def read_minute_frame_tail(source_file: Path, start_offset: int) -> pd.DataFrame:
    """按 32 字节边界读取分钟线尾部，用于安全增量追加。"""
    if start_offset < 0 or start_offset % MINUTE_RECORD_SIZE != 0:
        raise ValueError(f"分钟线增量读取偏移必须按 {MINUTE_RECORD_SIZE} 字节对齐：{start_offset}")
    with source_file.open("rb") as file:
        file.seek(start_offset)
        raw = file.read()
    if len(raw) % MINUTE_RECORD_SIZE != 0:
        raise ValueError(f"分钟线尾部大小不是 {MINUTE_RECORD_SIZE} 字节整数倍，可能仍在写入：{source_file}")
    return parse_minute_records(raw, source_file.suffix.lower())


def parse_day_records(raw: bytes, security: SecurityTypeInfo) -> pd.DataFrame:
    """使用 NumPy 结构化视图批量解析 `.day`。"""
    if not raw:
        return pd.DataFrame(columns=["open", "high", "low", "close", "amount", "volume"])
    if security.market == "ds":
        return _parse_ds_day_records(raw)
    return _parse_standard_day_records(raw, security)


def _parse_standard_day_records(raw: bytes, security: SecurityTypeInfo) -> pd.DataFrame:
    records = np.frombuffer(raw, dtype=DAY_DTYPE)
    frame = pd.DataFrame(
        {
            "open": records["open"].astype("float64") * security.price_scale,
            "high": records["high"].astype("float64") * security.price_scale,
            "low": records["low"].astype("float64") * security.price_scale,
            "close": records["close"].astype("float64") * security.price_scale,
            "amount": records["amount"].astype("float64"),
            "volume": records["volume"].astype("uint64") * security.volume_scale,
        }
    )
    frame.index = pd.to_datetime(records["date"].astype(str), format="%Y%m%d", errors="coerce")
    frame.index.name = "date"
    return frame


def _parse_ds_day_records(raw: bytes) -> pd.DataFrame:
    """`vipdoc/ds/*.day` 的价格字段实际是 float32 位模式，不能沿用 A 股整数缩放。"""
    records = np.frombuffer(raw, dtype=DS_DAY_DTYPE)
    frame = pd.DataFrame(
        {
            "open": records["open"].astype("float64"),
            "high": records["high"].astype("float64"),
            "low": records["low"].astype("float64"),
            "close": records["close"].astype("float64"),
            "amount": records["amount"].astype("float64"),
            "volume": records["volume"].astype("uint64"),
        }
    )
    frame.index = pd.to_datetime(records["date"].astype(str), format="%Y%m%d", errors="coerce")
    frame.index.name = "date"
    return frame


def parse_minute_records(raw: bytes, suffix: str) -> pd.DataFrame:
    """解析 `.lc1/.lc5/.1/.5` 分钟线原始记录。"""
    normalized_suffix = suffix.strip().lower()
    if normalized_suffix in {".lc1", ".lc5"}:
        return _parse_lc_minute_records(raw)
    if normalized_suffix in {".1", ".5"}:
        return _parse_legacy_minute_records(raw)
    raise ValueError(f"未支持的分钟线后缀：{suffix}")


def _parse_lc_minute_records(raw: bytes) -> pd.DataFrame:
    datetimes: list[str] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    amounts: list[float] = []
    volumes: list[int] = []
    for offset in range(0, len(raw), MINUTE_RECORD_SIZE):
        date_code, time_code, open_, high, low, close, amount, volume, _reserved = struct.unpack(
            "<HHfffffII",
            raw[offset : offset + MINUTE_RECORD_SIZE],
        )
        datetimes.append(_format_minute_datetime(date_code, time_code))
        opens.append(float(open_))
        highs.append(float(high))
        lows.append(float(low))
        closes.append(float(close))
        amounts.append(float(amount))
        volumes.append(int(volume))
    return _build_minute_frame(datetimes, opens, highs, lows, closes, amounts, volumes)


def _parse_legacy_minute_records(raw: bytes) -> pd.DataFrame:
    datetimes: list[str] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    amounts: list[float] = []
    volumes: list[int] = []
    for offset in range(0, len(raw), MINUTE_RECORD_SIZE):
        date_code, time_code, open_, high, low, close, amount, volume, _reserved = struct.unpack(
            "<HHIIIIfII",
            raw[offset : offset + MINUTE_RECORD_SIZE],
        )
        datetimes.append(_format_minute_datetime(date_code, time_code))
        opens.append(open_ / 100)
        highs.append(high / 100)
        lows.append(low / 100)
        closes.append(close / 100)
        amounts.append(float(amount))
        volumes.append(int(volume))
    return _build_minute_frame(datetimes, opens, highs, lows, closes, amounts, volumes)


def _build_minute_frame(
    datetimes: list[str],
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    amounts: list[float],
    volumes: list[int],
) -> pd.DataFrame:
    if not datetimes:
        return pd.DataFrame(columns=["open", "high", "low", "close", "amount", "volume"])
    frame = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "amount": amounts,
            "volume": volumes,
        }
    )
    frame.index = pd.to_datetime(datetimes, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    frame.index.name = "date"
    return frame


def _format_minute_datetime(date_code: int, time_code: int) -> str:
    year = date_code // 2048 + 2004
    month = (date_code % 2048) // 100
    day = (date_code % 2048) % 100
    hour = time_code // 60
    minute = time_code % 60
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"


def normalize_day_frame(frame: pd.DataFrame, source_file: Path, vipdoc: Path) -> pd.DataFrame:
    """收敛为统一列顺序，便于直接落入当前仓库的统一序列表。"""
    return _normalize_tdx_frame(frame, source_file, vipdoc, period="day", datetime_format="%Y-%m-%d")


def normalize_minute_frame(frame: pd.DataFrame, source_file: Path, vipdoc: Path, interval: str) -> pd.DataFrame:
    """把分钟线规整到与日线相同的统一列。"""
    return _normalize_tdx_frame(
        frame,
        source_file,
        vipdoc,
        period=interval_to_period(interval),
        datetime_format="%Y-%m-%d %H:%M:%S",
    )


def _normalize_tdx_frame(
    frame: pd.DataFrame,
    source_file: Path,
    vipdoc: Path,
    *,
    period: str,
    datetime_format: str,
) -> pd.DataFrame:
    data = frame.reset_index()
    data = data.rename(columns={data.columns[0]: "datetime"})
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce").dt.strftime(datetime_format)
    data["market"] = infer_market_from_path(source_file, vipdoc)
    data["symbol"] = source_file.stem.lower()
    data["period"] = period
    data["source_file"] = source_file.relative_to(vipdoc).as_posix()
    data["source_mtime"] = source_file.stat().st_mtime
    return data[TDX_COLUMNS]


def build_day_file_signature(source_file: Path) -> dict[str, object]:
    return build_tdx_file_signature(source_file, interval="1d")


def build_tdx_file_signature(source_file: Path, interval: str | None = None) -> dict[str, object]:
    stat = source_file.stat()
    record_size = record_size_for_interval(interval) if interval is not None else record_size_for_suffix(source_file.suffix)
    record_count = stat.st_size // record_size
    period = interval_to_period(interval) if interval is not None else detect_period_from_suffix(source_file.suffix)
    return {
        "source_size": stat.st_size,
        "source_mtime": stat.st_mtime,
        "record_size": record_size,
        "record_count": record_count,
        "tail_hash_rows": min(record_count, OVERLAP_ROWS),
        "tail_hash": build_tail_hash(source_file, min(record_count, OVERLAP_ROWS), record_size=record_size),
        "size_aligned": stat.st_size % record_size == 0,
        "period": period or "",
    }


def build_tail_hash(
    source_file: Path,
    rows: int,
    *,
    size_limit: int | None = None,
    record_size: int = DAY_RECORD_SIZE,
) -> str | None:
    if rows <= 0:
        return None
    size = source_file.stat().st_size if size_limit is None else size_limit
    if size <= 0 or size % record_size != 0:
        return None
    byte_count = min(rows * record_size, size)
    with source_file.open("rb") as file:
        file.seek(size - byte_count)
        payload = file.read(byte_count)
    return hashlib.sha256(payload).hexdigest()


def manifest_is_unchanged(previous: object | None, signature: dict[str, object]) -> bool:
    """判断文件是否完全未变化。"""
    if previous is None or _manifest_status(previous) != "success":
        return False
    if signature.get("size_aligned") is not True:
        return False
    previous_record_size = _manifest_int(previous, "record_size")
    current_record_size = int(signature["record_size"])
    return (
        (previous_record_size in {0, current_record_size})
        and _manifest_int(previous, "source_size") == int(signature["source_size"])
        and _manifest_float(previous, "source_mtime") == float(signature["source_mtime"])
        and _manifest_int(previous, "record_count") == int(signature["record_count"])
        and _manifest_str(previous, "tail_hash") == str(signature["tail_hash"] or "")
    )


def manifest_can_append(previous: object | None, signature: dict[str, object], source_file: Path) -> bool:
    """只允许严格尾部增长走安全增量。"""
    if previous is None or _manifest_status(previous) != "success":
        return False
    if signature.get("size_aligned") is not True:
        return False
    record_size = int(signature.get("record_size") or DAY_RECORD_SIZE)
    previous_size = _manifest_int(previous, "source_size")
    current_size = int(signature["source_size"])
    previous_rows = _manifest_int(previous, "record_count")
    current_rows = int(signature["record_count"])
    if previous_size <= 0 or previous_size % record_size != 0:
        return False
    if current_size <= previous_size or previous_rows <= 0 or current_rows <= previous_rows:
        return False
    tail_rows = min(previous_rows, OVERLAP_ROWS)
    previous_hash = _manifest_str(previous, "tail_hash")
    if not previous_hash:
        return False
    return build_tail_hash(source_file, tail_rows, size_limit=previous_size, record_size=record_size) == previous_hash


def security_type_to_asset_type(security: SecurityTypeInfo) -> str:
    if "INDEX" in security.security_type:
        return "index"
    if "FUND" in security.security_type:
        return "fund"
    if "BOND" in security.security_type or "REPO" in security.security_type:
        return "bond"
    if "FOREX" in security.security_type:
        return "forex"
    if "OPTION" in security.security_type or "FUTURE" in security.security_type:
        return "derivative"
    if "OTHER" in security.security_type:
        return "other"
    return "equity"


def _detect_ds_security_type(symbol: str) -> SecurityTypeInfo:
    """`ds` 市场混合了外汇、指数、基金和衍生品，先按已验证样本做保守分类。"""
    prefix, _, raw_contract = symbol.partition("#")
    contract = raw_contract.upper()
    security_type = "DS_OTHER"
    if prefix in DS_FUND_PREFIXES:
        security_type = "DS_FUND"
    elif prefix in DS_FOREX_PREFIXES and _looks_like_ds_forex_contract(contract):
        security_type = "DS_FOREX"
    elif _looks_like_ds_option_contract(contract):
        security_type = "DS_OPTION"
    elif prefix in DS_INDEX_PREFIXES:
        security_type = "DS_INDEX"
    elif prefix in DS_DERIVATIVE_PREFIXES or _looks_like_ds_future_contract(contract):
        security_type = "DS_FUTURE"
    elif contract.isdigit() and len(contract) in {5, 6}:
        security_type = "DS_INDEX"
    return SecurityTypeInfo("ds", symbol, prefix, security_type, 1.0, 1.0)


def _looks_like_ds_forex_contract(contract: str) -> bool:
    return len(contract) == 6 and contract.isalpha()


def _looks_like_ds_option_contract(contract: str) -> bool:
    return "-C-" in contract or "-P-" in contract


def _looks_like_ds_future_contract(contract: str) -> bool:
    return bool(re.match(r"^[A-Z]{1,3}\d{3,4}$", contract))


def _manifest_status(previous: object) -> str:
    return str(getattr(previous, "status", ""))


def _manifest_int(previous: object, field_name: str) -> int:
    return int(getattr(previous, field_name, 0) or 0)


def _manifest_float(previous: object, field_name: str) -> float:
    return float(getattr(previous, field_name, 0.0) or 0.0)


def _manifest_str(previous: object, field_name: str) -> str:
    return str(getattr(previous, field_name, "") or "")
