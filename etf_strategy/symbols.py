from __future__ import annotations
"""默认研究标的池。

标的池用于批量研究入口，保持名单固定可以让报告结果可复现。
"""

from dataclasses import dataclass


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

SYMBOL_SETS: dict[str, tuple[SymbolSpec, ...]] = {
    "hstech_plus_513050": (*HSTECH_CONSTITUENTS, CN_ETF_513050),
}
