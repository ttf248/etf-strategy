from __future__ import annotations
"""默认研究标的池。

标的池用于批量研究入口，只保留无需仓库内数据文件的静态名单。
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

YAHOO_US_ACTIVE_SOURCE = "美国高活跃股票与 ETF 样本，参考 2026-05 近期 Most Active 市场榜单整理"
YAHOO_US_ACTIVE: tuple[SymbolSpec, ...] = (
    SymbolSpec("SPY", "SPDR S&P 500 ETF TRUST", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("QQQ", "INVESCO QQQ TRUST", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("IWM", "ISHARES RUSSELL 2000 ETF", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("DIA", "SPDR DOW JONES INDUSTRIAL AVERAGE ETF", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("VOO", "VANGUARD S&P 500 ETF", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("VTI", "VANGUARD TOTAL STOCK MARKET ETF", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("TQQQ", "PROSHARES ULTRAPRO QQQ", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("SQQQ", "PROSHARES ULTRAPRO SHORT QQQ", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("SOXL", "DIREXION DAILY SEMICONDUCTOR BULL 3X SHARES", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("SOXS", "DIREXION DAILY SEMICONDUCTOR BEAR 3X SHARES", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("XLF", "FINANCIAL SELECT SECTOR SPDR FUND", "美股行业 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("XLK", "TECHNOLOGY SELECT SECTOR SPDR FUND", "美股行业 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("XLE", "ENERGY SELECT SECTOR SPDR FUND", "美股行业 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("TLT", "ISHARES 20+ YEAR TREASURY BOND ETF", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("HYG", "ISHARES IBOXX $ HIGH YIELD CORPORATE BOND ETF", "美股高活跃 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("GLD", "SPDR GOLD SHARES", "美股商品 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("SLV", "ISHARES SILVER TRUST", "美股商品 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("BITO", "PROSHARES BITCOIN STRATEGY ETF", "美股数字资产 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("IBIT", "ISHARES BITCOIN TRUST ETF", "美股数字资产 ETF", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("NVDA", "NVIDIA CORPORATION", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("TSLA", "TESLA, INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("AAPL", "APPLE INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("MSFT", "MICROSOFT CORPORATION", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("AMZN", "AMAZON.COM, INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("META", "META PLATFORMS, INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("GOOGL", "ALPHABET INC. CLASS A", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("AMD", "ADVANCED MICRO DEVICES, INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("AVGO", "BROADCOM INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("NFLX", "NETFLIX, INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("PLTR", "PALANTIR TECHNOLOGIES INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("SMCI", "SUPER MICRO COMPUTER, INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("MSTR", "MICROSTRATEGY INCORPORATED", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("COIN", "COINBASE GLOBAL, INC.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("JPM", "JPMORGAN CHASE & CO.", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
    SymbolSpec("BAC", "BANK OF AMERICA CORPORATION", "美股高活跃股票", YAHOO_US_ACTIVE_SOURCE),
)

CN_ETF_513050 = SymbolSpec("513050.SS", "中概互联网ETF", "国内ETF", "用户指定追加标的")
INDEX_GRID_ETF_SOURCE = "用户指定的指数 ETF 网格验证样本"
INDEX_GRID_159941 = SymbolSpec("159941.SZ", "纳指ETF", "指数ETF", INDEX_GRID_ETF_SOURCE)
INDEX_GRID_159605 = SymbolSpec("159605.SZ", "中概互联网ETF", "指数ETF", INDEX_GRID_ETF_SOURCE)
INDEX_GRID_159866 = SymbolSpec("159866.SZ", "日经ETF", "指数ETF", INDEX_GRID_ETF_SOURCE)

YAHOO_CN_ACTIVE_SOURCE = "A 股与跨境 ETF 高活跃样本，结合当前项目研究口径整理"
YAHOO_CN_ACTIVE: tuple[SymbolSpec, ...] = (
    SymbolSpec("513050.SS", "中概互联网ETF", "A股跨境ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("159941.SZ", "纳指ETF", "A股跨境ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("159605.SZ", "中概互联网ETF", "A股跨境ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("159866.SZ", "日经ETF", "A股跨境ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("510300.SS", "沪深300ETF", "A股宽基ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("510500.SS", "中证500ETF", "A股宽基ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("510050.SS", "上证50ETF", "A股宽基ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("159915.SZ", "创业板ETF", "A股宽基ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("588000.SS", "科创50ETF", "A股宽基ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("512480.SS", "半导体ETF", "A股行业ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("512660.SS", "军工ETF", "A股行业ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("512690.SS", "酒ETF", "A股行业ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("159919.SZ", "沪深300ETF", "A股宽基ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("159949.SZ", "创业板50ETF", "A股宽基ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("159995.SZ", "芯片ETF", "A股行业ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("159920.SZ", "恒生ETF", "A股跨境ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("513100.SS", "纳指ETF", "A股跨境ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("513500.SS", "标普500ETF", "A股跨境ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("518880.SS", "黄金ETF", "A股商品ETF", YAHOO_CN_ACTIVE_SOURCE),
    SymbolSpec("511010.SS", "国债ETF", "A股债券ETF", YAHOO_CN_ACTIVE_SOURCE),
)

YAHOO_JP_ACTIVE_SOURCE = "日本高活跃股票样本，参考 2026Q1 JPX 衍生品活跃标的与当前东京市场成交活跃度整理"
YAHOO_JP_ACTIVE: tuple[SymbolSpec, ...] = (
    SymbolSpec("7203.T", "TOYOTA MOTOR CORPORATION", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("6758.T", "SONY GROUP CORPORATION", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("9984.T", "SOFTBANK GROUP CORP.", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("8306.T", "MITSUBISHI UFJ FINANCIAL GROUP, INC.", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("8035.T", "TOKYO ELECTRON LIMITED", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("6861.T", "KEYENCE CORPORATION", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("6501.T", "HITACHI, LTD.", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("9983.T", "FAST RETAILING CO., LTD.", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("4063.T", "SHIN-ETSU CHEMICAL CO., LTD.", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("9432.T", "NIPPON TELEGRAPH AND TELEPHONE CORPORATION", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("6098.T", "RECRUIT HOLDINGS CO., LTD.", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("7974.T", "NINTENDO CO., LTD.", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("8058.T", "MITSUBISHI CORPORATION", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("8316.T", "SUMITOMO MITSUI FINANCIAL GROUP, INC.", "日本高活跃股票", YAHOO_JP_ACTIVE_SOURCE),
    SymbolSpec("1321.T", "NOMURA NF NIKKEI 225 ETF", "日本高活跃ETF", YAHOO_JP_ACTIVE_SOURCE),
)

YAHOO_GLOBAL_ACTIVE_100: tuple[SymbolSpec, ...] = (
    *YAHOO_US_ACTIVE,
    *HSTECH_CONSTITUENTS,
    *YAHOO_CN_ACTIVE,
    *YAHOO_JP_ACTIVE,
)

SYMBOL_SETS: dict[str, tuple[SymbolSpec, ...]] = {
    "hstech_plus_513050": (*HSTECH_CONSTITUENTS, CN_ETF_513050),
    "index_grid_etfs": (INDEX_GRID_159941, INDEX_GRID_159605, INDEX_GRID_159866),
    "yahoo_global_active_100": YAHOO_GLOBAL_ACTIVE_100,
}


def symbol_specs_by_symbol() -> dict[str, SymbolSpec]:
    """按标的代码返回内置元信息映射。"""
    specs: dict[str, SymbolSpec] = {}
    for symbol_set in SYMBOL_SETS.values():
        for spec in symbol_set:
            specs[spec.symbol.upper()] = spec
    return specs


def get_symbol_set(symbol_set: str) -> tuple[SymbolSpec, ...]:
    """读取内置标的池。"""
    normalized = symbol_set.strip()
    if normalized not in SYMBOL_SETS:
        raise ValueError(f"未知标的池：{symbol_set}")
    return SYMBOL_SETS[normalized]


def resolve_symbol_spec(symbol: str, default_symbol: str = "1810.HK") -> SymbolSpec:
    """解析标的展示名、分类和来源说明。"""
    normalized = symbol.strip().upper()
    specs = symbol_specs_by_symbol()
    if normalized in specs:
        return specs[normalized]
    if normalized == default_symbol:
        return SymbolSpec(symbol=normalized, name=normalized, category="默认标的", source="项目默认标的")
    return SymbolSpec(symbol=normalized, name=normalized, category="自定义标的", source="命令行输入")
