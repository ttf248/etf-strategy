from __future__ import annotations
"""最小交易单位解析规则。

当前项目的固定股数网格依赖真实交易单位，因此这里负责把标的代码映射成：
- 所属市场
- 最小交易单位
- 数据来源说明
"""

import re
from dataclasses import dataclass

import requests

AASTOCKS_SNAPSHOT_URL = "https://product1.aastocks.com/Snapshot/WHBL/Quote.aspx"
_HK_LOT_SIZE_CACHE: dict[str, int] | None = None


@dataclass(frozen=True)
class LotSizeRule:
    """标的最小交易单位。"""

    symbol: str
    market: str
    lot_size: int
    source: str


def resolve_lot_size_rule(symbol: str) -> LotSizeRule:
    """按市场规则解析最小交易单位。

    当前实现是“通用接口 + 按交易所分层支持”：
    - 港股实时抓公开页面里的每手股数
    - 美股等 1 股市场直接返回 1
    - 其他市场显式报错，避免回测结果看似能跑却不符合交易规则
    """
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("标的代码不能为空。")

    if normalized_symbol.endswith(".HK"):
        lot_size = _resolve_cached_hk_lot_size(normalized_symbol)
        return LotSizeRule(
            symbol=normalized_symbol,
            market="HK",
            lot_size=lot_size,
            source="AASTOCKS 快照页 Lot Size",
        )

    if normalized_symbol.endswith((".SS", ".SZ")):
        return LotSizeRule(
            symbol=normalized_symbol,
            market="CN",
            lot_size=100,
            source="A 股和沪深 ETF 默认 100 股",
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
    """从公开快照页抓取港股每手股数。"""
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

    # 页面结构当前比较稳定，直接按 “Lot Size -> 数值” 的 HTML 结构提取。
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


def _load_hk_lot_size_cache() -> dict[str, int]:
    global _HK_LOT_SIZE_CACHE
    if _HK_LOT_SIZE_CACHE is not None:
        return _HK_LOT_SIZE_CACHE
    _HK_LOT_SIZE_CACHE = {}
    return _HK_LOT_SIZE_CACHE


def _resolve_cached_hk_lot_size(symbol: str) -> int:
    cache = _load_hk_lot_size_cache()
    normalized_symbol = symbol.strip().upper()
    cached = cache.get(normalized_symbol)
    if cached is not None and cached > 0:
        return cached
    lot_size = _fetch_hk_lot_size(normalized_symbol)
    cache[normalized_symbol] = lot_size
    return lot_size
