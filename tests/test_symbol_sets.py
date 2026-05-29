from __future__ import annotations

import unittest
from types import SimpleNamespace

from strategy_studio.services.sync import _resolve_yahoo_targets
from strategy_studio.symbols import YAHOO_GLOBAL_ACTIVE_100, get_symbol_set, resolve_symbol_spec


class SymbolSetTests(unittest.TestCase):
    """覆盖 Yahoo 默认样本池和解析逻辑。"""

    def test_yahoo_global_active_100_has_expected_size_and_unique_symbols(self) -> None:
        self.assertEqual(len(YAHOO_GLOBAL_ACTIVE_100), 100)
        symbols = [spec.symbol for spec in YAHOO_GLOBAL_ACTIVE_100]
        self.assertEqual(len(symbols), len(set(symbols)))

    def test_resolve_symbol_spec_reads_yahoo_global_active_symbol(self) -> None:
        spec = resolve_symbol_spec("SPY")
        self.assertEqual(spec.symbol, "SPY")
        self.assertIn("ETF", spec.category)

    def test_get_symbol_set_returns_yahoo_global_active_100(self) -> None:
        symbol_set = get_symbol_set("yahoo_global_active_100")
        self.assertEqual(len(symbol_set), 100)
        self.assertEqual(symbol_set[0].symbol, "SPY")

    def test_resolve_yahoo_targets_prefers_symbol_set_and_limit(self) -> None:
        targets = _resolve_yahoo_targets(
            session=object(),
            symbol=None,
            symbol_set="yahoo_global_active_100",
            limit=3,
        )

        self.assertEqual([item.symbol for item in targets], ["SPY", "QQQ", "IWM"])

    def test_resolve_yahoo_targets_uses_existing_instruments_without_symbol_set(self) -> None:
        session = SimpleNamespace()

        with unittest.mock.patch(
            "strategy_studio.services.sync.list_instruments",
            return_value=[
                {"symbol": "1810.HK", "name": "XIAOMI - W"},
                {"symbol": "SPY", "name": "SPDR S&P 500 ETF TRUST"},
            ],
        ):
            targets = _resolve_yahoo_targets(session, symbol=None, symbol_set=None, limit=1)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].symbol, "1810.HK")
        self.assertEqual(targets[0].name, "XIAOMI - W")


if __name__ == "__main__":
    unittest.main()
