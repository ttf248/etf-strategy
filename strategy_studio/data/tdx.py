from __future__ import annotations

"""通达信日线解析与增量签名。

这里先迁入当前子任务必须的最小集合：

- `.day` 二进制解析
- 证券类型识别与价格/成交量缩放
- 标准化为统一列
- 文件签名、尾部 hash 与安全增量判断

分钟线和更完整的批量导入编排会在后续子任务继续扩展。
"""

from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


DAY_RECORD_SIZE = 32
OVERLAP_ROWS = 5
TDX_DAY_COLUMNS = [
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


@dataclass(frozen=True)
class SecurityTypeInfo:
    market: str
    symbol: str
    prefix: str
    security_type: str
    price_scale: float
    volume_scale: float


def iter_tdx_day_files(vipdoc: Path, symbol: str | None = None, limit: int | None = None) -> list[Path]:
    """枚举通达信 `.day` 文件。"""
    files = sorted(path for path in vipdoc.rglob("*.day") if path.is_file())
    if symbol:
        normalized = symbol.strip().lower()
        files = [path for path in files if path.stem.lower() == normalized]
    if limit is not None:
        files = files[:limit]
    return files


def detect_security_type(source_file: Path, vipdoc: Path | None = None) -> SecurityTypeInfo:
    """按通达信市场和代码前缀识别证券类型。"""
    market = infer_market_from_path(source_file, vipdoc)
    symbol = source_file.stem.lower()
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
    return ""


def read_day_frame(source_file: Path, vipdoc: Path | None = None) -> pd.DataFrame:
    raw = source_file.read_bytes()
    if len(raw) % DAY_RECORD_SIZE != 0:
        raise ValueError(f".day 文件大小不是 {DAY_RECORD_SIZE} 字节整数倍，可能仍在写入：{source_file}")
    return parse_day_records(raw, detect_security_type(source_file, vipdoc))


def read_day_frame_tail(source_file: Path, start_offset: int, vipdoc: Path | None = None) -> pd.DataFrame:
    """按 32 字节边界读取 `.day` 尾部，用于安全增量追加。"""
    if start_offset < 0 or start_offset % DAY_RECORD_SIZE != 0:
        raise ValueError(f".day 增量读取偏移必须按 {DAY_RECORD_SIZE} 字节对齐：{start_offset}")
    with source_file.open("rb") as file:
        file.seek(start_offset)
        raw = file.read()
    if len(raw) % DAY_RECORD_SIZE != 0:
        raise ValueError(f".day 尾部大小不是 {DAY_RECORD_SIZE} 字节整数倍，可能仍在写入：{source_file}")
    return parse_day_records(raw, detect_security_type(source_file, vipdoc))


def parse_day_records(raw: bytes, security: SecurityTypeInfo) -> pd.DataFrame:
    """使用 NumPy 结构化视图批量解析 `.day`。"""
    if not raw:
        return pd.DataFrame(columns=["open", "high", "low", "close", "amount", "volume"])
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


def normalize_day_frame(frame: pd.DataFrame, source_file: Path, vipdoc: Path) -> pd.DataFrame:
    """收敛为统一列顺序，便于直接落入当前仓库的统一序列表。"""
    data = frame.reset_index()
    data = data.rename(columns={data.columns[0]: "datetime"})
    data["datetime"] = data["datetime"].astype(str).str[:10]
    data["market"] = infer_market_from_path(source_file, vipdoc)
    data["symbol"] = source_file.stem.lower()
    data["period"] = "day"
    data["source_file"] = source_file.relative_to(vipdoc).as_posix()
    data["source_mtime"] = source_file.stat().st_mtime
    return data[TDX_DAY_COLUMNS]


def build_day_file_signature(source_file: Path) -> dict[str, object]:
    stat = source_file.stat()
    record_count = stat.st_size // DAY_RECORD_SIZE
    return {
        "source_size": stat.st_size,
        "source_mtime": stat.st_mtime,
        "record_size": DAY_RECORD_SIZE,
        "record_count": record_count,
        "tail_hash_rows": min(record_count, OVERLAP_ROWS),
        "tail_hash": build_tail_hash(source_file, min(record_count, OVERLAP_ROWS)),
        "size_aligned": stat.st_size % DAY_RECORD_SIZE == 0,
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
    return (
        _manifest_int(previous, "source_size") == int(signature["source_size"])
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
    previous_size = _manifest_int(previous, "source_size")
    current_size = int(signature["source_size"])
    previous_rows = _manifest_int(previous, "record_count")
    current_rows = int(signature["record_count"])
    if previous_size <= 0 or current_size <= previous_size or previous_rows <= 0 or current_rows <= previous_rows:
        return False
    tail_rows = min(previous_rows, OVERLAP_ROWS)
    previous_hash = _manifest_str(previous, "tail_hash")
    if not previous_hash:
        return False
    return build_tail_hash(source_file, tail_rows, size_limit=previous_size) == previous_hash


def security_type_to_asset_type(security: SecurityTypeInfo) -> str:
    if "INDEX" in security.security_type:
        return "index"
    if "FUND" in security.security_type:
        return "fund"
    if "BOND" in security.security_type or "REPO" in security.security_type:
        return "bond"
    return "equity"


def _manifest_status(previous: object) -> str:
    return str(getattr(previous, "status", ""))


def _manifest_int(previous: object, field_name: str) -> int:
    return int(getattr(previous, field_name, 0) or 0)


def _manifest_float(previous: object, field_name: str) -> float:
    return float(getattr(previous, field_name, 0.0) or 0.0)


def _manifest_str(previous: object, field_name: str) -> str:
    return str(getattr(previous, field_name, "") or "")
