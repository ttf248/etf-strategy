from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import requests


INTRADAY_INTERVAL_SUFFIXES = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
DATA_INTERVAL_SUFFIXES = INTRADAY_INTERVAL_SUFFIXES | {"1d", "daily"}
AASTOCKS_SNAPSHOT_URL = "https://product1.aastocks.com/Snapshot/WHBL/Quote.aspx"


@dataclass(frozen=True)
class LotSizeRule:
    """标的最小交易单位。"""

    symbol: str
    market: str
    lot_size: int
    source: str


def infer_symbol_from_data_path(data_path: str | Path) -> str | None:
    """尝试从标准化 CSV 文件名推断 Yahoo 标的代码。"""
    stem = Path(data_path).stem
    normalized_stem = stem.lower()

    hk_match = re.search(r"(?P<code>\d{1,5})_hk(?:_|$)", normalized_stem)
    if hk_match:
        return f"{hk_match.group('code').upper()}.HK"

    parts = stem.split("_")
    if len(parts) >= 2 and parts[-1].lower() in DATA_INTERVAL_SUFFIXES:
        symbol_part = "_".join(parts[:-1]).strip()
        if symbol_part and re.fullmatch(r"[A-Za-z0-9\-\^=.]+", symbol_part):
            return symbol_part.upper()

    return None


def resolve_lot_size_rule(symbol: str) -> LotSizeRule:
    """按市场规则解析最小交易单位。"""
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("标的代码不能为空。")

    if normalized_symbol.endswith(".HK"):
        lot_size = _fetch_hk_lot_size(normalized_symbol)
        return LotSizeRule(
            symbol=normalized_symbol,
            market="HK",
            lot_size=lot_size,
            source="AASTOCKS 快照页 Lot Size",
        )

    if "." not in normalized_symbol and not normalized_symbol.startswith("^"):
        return LotSizeRule(
            symbol=normalized_symbol,
            market="US",
            lot_size=1,
            source="美股市场默认 1 股",
        )

    raise ValueError(f"暂不支持该市场的最小交易单位查询: {normalized_symbol}")


def _fetch_hk_lot_size(symbol: str) -> int:
    code = symbol.removesuffix(".HK")
    if not code.isdigit():
        raise ValueError(f"港股代码格式不正确，无法查询每手股数: {symbol}")

    response = requests.get(
        AASTOCKS_SNAPSHOT_URL,
        params={
            "aaDelay": "1",
            "aaLanguage": "Eng",
            "aaSymbol": str(int(code)),
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()

    match = re.search(
        r"<td[^>]*>\s*Lot Size\s*</td>\s*<td[^>]*>\s*([0-9,]+)\s*</td>",
        response.text,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"未能从 AASTOCKS 页面解析港股每手股数: {symbol}")

    lot_size = int(match.group(1).replace(",", ""))
    if lot_size <= 0:
        raise ValueError(f"港股每手股数无效: {symbol} -> {lot_size}")
    return lot_size
