from __future__ import annotations
"""默认研究标的池。

标的池用于批量研究入口，保持名单固定可以让报告结果可复现。
"""

from dataclasses import dataclass

from etf_strategy.data.southbound import (
    build_southbound_source_label,
    load_southbound_shanghai_snapshot,
    normalize_southbound_symbol,
)


@dataclass(frozen=True)
class SymbolSpec:
    """批量研究标的信息。"""

    symbol: str
    name: str
    category: str
    source: str


HSTECH_SOURCE = "恒生科技指数官方 factsheet，2026-04，数据截至 2026-04-30"
HSTECH_CONSTITUENTS: tuple[SymbolSpec, ...] = (
    SymbolSpec("3690.HK", "MEITUAN - W", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("0981.HK", "SMIC", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("1211.HK", "BYD COMPANY", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9988.HK", "BABA - W", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9999.HK", "NTES - S", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("1810.HK", "XIAOMI - W", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("0700.HK", "TENCENT", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9618.HK", "JD - SW", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9888.HK", "BIDU - SW", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("1024.HK", "KUAISHOU - W", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9961.HK", "TRIP.COM - S", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9868.HK", "XPENG - W", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("2015.HK", "LI AUTO - W", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("1347.HK", "HUA HONG SEMI", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9660.HK", "HORIZONROBOT - W", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("0992.HK", "LENOVO GROUP", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("0020.HK", "SENSETIME - W", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("0300.HK", "MIDEA GROUP", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("6690.HK", "HAIER SMARTHOME", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9626.HK", "BILIBILI - W", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("6618.HK", "JD HEALTH", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("2382.HK", "SUNNY OPTICAL", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9863.HK", "LEAPMOTOR", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("0241.HK", "ALI HEALTH", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("0268.HK", "KINGDEE INT'L", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("9866.HK", "NIO - SW", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("0780.HK", "TONGCHENGTRAVEL", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("3888.HK", "KINGSOFT", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("0285.HK", "BYD ELECTRONIC", "恒生科技成分股", HSTECH_SOURCE),
    SymbolSpec("1698.HK", "TME - SW", "恒生科技成分股", HSTECH_SOURCE),
)

CN_ETF_513050 = SymbolSpec("513050.SS", "中概互联网ETF", "国内ETF", "用户指定追加标的")
INDEX_GRID_ETF_SOURCE = "用户指定的指数 ETF 网格验证样本"
INDEX_GRID_159941 = SymbolSpec("159941.SZ", "纳指ETF", "指数ETF", INDEX_GRID_ETF_SOURCE)
INDEX_GRID_159605 = SymbolSpec("159605.SZ", "中概互联网ETF", "指数ETF", INDEX_GRID_ETF_SOURCE)
INDEX_GRID_159866 = SymbolSpec("159866.SZ", "日经ETF", "指数ETF", INDEX_GRID_ETF_SOURCE)


def _build_southbound_shanghai_constituents() -> tuple[SymbolSpec, ...]:
    rows = load_southbound_shanghai_snapshot()
    constituents: list[SymbolSpec] = []
    for row in rows:
        security_type = row["SecurityType"] or "股票"
        category = "港股通沪ETF" if security_type.upper() == "ETF" else "港股通沪股票"
        name = row["AbbrCn"] or row["AbbrEn"] or row["SecurityCode"]
        constituents.append(
            SymbolSpec(
                normalize_southbound_symbol(row["SecurityCode"]),
                name,
                category,
                build_southbound_source_label(row["UpdateDate"]),
            )
        )
    return tuple(constituents)


SOUTHBOUND_SHANGHAI_CONSTITUENTS: tuple[SymbolSpec, ...] = _build_southbound_shanghai_constituents()

SYMBOL_SETS: dict[str, tuple[SymbolSpec, ...]] = {
    "hstech_plus_513050": (*HSTECH_CONSTITUENTS, CN_ETF_513050),
    "southbound_shanghai_all": SOUTHBOUND_SHANGHAI_CONSTITUENTS,
    "index_grid_etfs": (INDEX_GRID_159941, INDEX_GRID_159605, INDEX_GRID_159866),
}
