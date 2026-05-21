import unittest
from unittest.mock import Mock, patch

import pandas as pd

from etf_strategy.cli import build_parser
from etf_strategy.data.market_rules import infer_symbol_from_data_path, resolve_lot_size_rule
from etf_strategy.strategy.grid import (
    build_sample_window,
    run_grid_backtest,
    split_intraday_in_sample_and_validation,
    split_in_sample_and_validation,
)


def build_test_frame(close_prices: list[float], start: str = "2025-09-01") -> pd.DataFrame:
    dates = pd.date_range(start=start, periods=len(close_prices), freq="B")
    frame = pd.DataFrame(
        {
            "Open": close_prices,
            "High": [price * 1.01 for price in close_prices],
            "Low": [price * 0.99 for price in close_prices],
            "Close": close_prices,
            "Volume": [1000000] * len(close_prices),
        },
        index=dates,
    )
    frame.index.name = "Date"
    return frame


class GridStrategyTests(unittest.TestCase):
    def test_download_parser_reads_intraday_parameters(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "download",
                "--symbol",
                "1810.HK",
                "--start",
                "2026-04-01",
                "--end",
                "2026-05-21",
                "--interval",
                "15m",
                "--period",
                "60d",
            ]
        )

        self.assertEqual(args.command, "download")
        self.assertEqual(args.symbol, "1810.HK")
        self.assertEqual(args.interval, "15m")
        self.assertEqual(args.period, "60d")
        self.assertEqual(args.period, "60d")
        self.assertIsNone(args.output)

    def test_run_parser_reads_intraday_parameters(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "run",
                "--symbol",
                "1810.HK",
                "--interval",
                "15m",
                "--period",
                "60d",
            ]
        )

        self.assertEqual(args.command, "run")
        self.assertEqual(args.interval, "15m")
        self.assertEqual(args.period, "60d")
        self.assertIsNone(args.start)
        self.assertIsNone(args.end)

    def test_backtest_parser_reads_grid_parameters(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "backtest",
                "--data",
                "data/processed/xiaomi_1810_hk_daily.csv",
                "--symbol",
                "1810.HK",
                "--grid-spacing",
                "0.06",
                "--grid-count",
                "7",
                "--take-profit",
                "0.03",
            ]
        )

        self.assertEqual(args.command, "backtest")
        self.assertEqual(args.data, "data/processed/xiaomi_1810_hk_daily.csv")
        self.assertEqual(args.symbol, "1810.HK")
        self.assertAlmostEqual(args.grid_spacing, 0.06)
        self.assertEqual(args.grid_count, 7)
        self.assertAlmostEqual(args.take_profit, 0.03)
        self.assertEqual(args.validation_start, "2026-01-01")
        self.assertEqual(args.lookback_days, 120)

    def test_infer_symbol_from_data_path(self) -> None:
        self.assertEqual(infer_symbol_from_data_path("data/processed/xiaomi_1810_hk_daily.csv"), "1810.HK")
        self.assertEqual(infer_symbol_from_data_path("data/processed/spy_1d.csv"), "SPY")
        self.assertEqual(infer_symbol_from_data_path("data/processed/brk-b_15m.csv"), "BRK-B")

    def test_resolve_lot_size_rule_for_us_symbol(self) -> None:
        rule = resolve_lot_size_rule("SPY")
        self.assertEqual(rule.market, "US")
        self.assertEqual(rule.lot_size, 1)

    @patch("etf_strategy.data.market_rules.requests.get")
    def test_resolve_lot_size_rule_for_hk_symbol(self, mock_get: Mock) -> None:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = """
        <td class="c3">Lot Size</td>
        <td class="c4">200</td>
        """
        mock_get.return_value = mock_response

        rule = resolve_lot_size_rule("1810.HK")

        self.assertEqual(rule.market, "HK")
        self.assertEqual(rule.lot_size, 200)
        self.assertIn("AASTOCKS", rule.source)

    def test_resolve_lot_size_rule_rejects_unsupported_market(self) -> None:
        with self.assertRaisesRegex(ValueError, "暂不支持"):
            resolve_lot_size_rule("7203.T")

    def test_build_sample_window_uses_sample_start_as_entry(self) -> None:
        prices = [20.0, 21.2, 22.5, 21.8, 20.9, 20.1, 19.5]
        frame = build_test_frame(prices, start="2025-11-03")

        window = build_sample_window(
            frame,
            validation_start="2025-12-01",
            lookback_days=30,
        )

        self.assertEqual(window.peak_date, "2025-11-05")
        self.assertEqual(window.entry_date, "2025-11-03")
        self.assertEqual(window.sample_start, "2025-11-03")
        self.assertEqual(window.validation_start, "2025-12-01")

    def test_split_in_sample_and_validation_no_longer_requires_drawdown_trigger(self) -> None:
        prices = [20.0, 20.5, 21.0, 21.3, 21.6, 21.9, 22.1]
        frame = build_test_frame(prices, start="2025-11-03")

        window, in_sample, validation = split_in_sample_and_validation(
            frame,
            validation_start="2025-11-10",
            lookback_days=30,
        )

        self.assertEqual(window.entry_date, "2025-11-03")
        self.assertFalse(in_sample.empty)
        self.assertFalse(validation.empty)

    def test_run_grid_backtest_enters_on_first_bar(self) -> None:
        prices = [20.0, 19.0, 18.0, 17.0, 18.2, 19.1, 20.0, 18.0, 19.3, 20.2]
        frame = build_test_frame(prices, start="2025-10-01")

        result = run_grid_backtest(
            data=frame,
            scenario_name="unit_test",
            grid_spacing_pct=0.05,
            grid_count=3,
            take_profit_pct=0.05,
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            total_capital=200000,
        )

        summary = result["summary"]
        events = result["events"]

        self.assertTrue(summary["TriggeredEntry"])
        self.assertEqual(summary["EntryDate"], "2025-10-01")
        self.assertAlmostEqual(summary["EntryPrice"], 20.0)
        self.assertEqual(summary["LotSize"], 200)
        self.assertEqual(summary["BaseUnits"], 5000)
        self.assertEqual(summary["GridUnitsPerLevel"], 1600)
        self.assertFalse(events.empty)
        self.assertTrue({"base_buy", "grid_buy"}.issubset(set(events["EventType"])))
        self.assertEqual(events.iloc[0]["Date"], "2025-10-01")
        self.assertEqual(events.iloc[0]["EventType"], "base_buy")
        self.assertTrue((events["Units"] % 200 == 0).all())

    def test_split_intraday_in_sample_and_validation(self) -> None:
        dates = pd.date_range(start="2026-04-01 09:30:00", periods=40, freq="15min")
        prices = [30.0, 31.0, 32.0, 33.0, 34.0, 35.0, 34.0, 33.0, 32.0, 31.0] + [30.0] * 30
        frame = pd.DataFrame(
            {
                "Open": prices,
                "High": [price * 1.01 for price in prices],
                "Low": [price * 0.99 for price in prices],
                "Close": prices,
                "Volume": [1000] * len(prices),
            },
            index=dates,
        )
        frame.index.name = "Date"

        window, in_sample, validation = split_intraday_in_sample_and_validation(frame, validation_ratio=0.25)

        self.assertEqual(window.peak_date, "2026-04-01 10:45:00")
        self.assertEqual(window.entry_date, "2026-04-01 09:30:00")
        self.assertFalse(in_sample.empty)
        self.assertFalse(validation.empty)


if __name__ == "__main__":
    unittest.main()
