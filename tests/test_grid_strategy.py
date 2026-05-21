import unittest

import pandas as pd

from etf_strategy.cli import build_parser
from etf_strategy.strategy.grid import (
    locate_recent_decline_window,
    run_grid_backtest,
    split_intraday_in_sample_and_validation,
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
        self.assertAlmostEqual(args.grid_spacing, 0.06)
        self.assertEqual(args.grid_count, 7)
        self.assertAlmostEqual(args.take_profit, 0.03)
        self.assertEqual(args.validation_start, "2026-01-01")
        self.assertEqual(args.lookback_days, 120)

    def test_locate_recent_decline_window_finds_peak_and_entry(self) -> None:
        prices = [20.0, 21.2, 22.5, 21.8, 20.9, 20.1, 19.5]
        frame = build_test_frame(prices, start="2025-11-03")

        window = locate_recent_decline_window(
            frame,
            validation_start="2025-12-01",
            lookback_days=30,
            entry_drawdown_pct=0.10,
        )

        self.assertEqual(window.peak_date, "2025-11-05")
        self.assertEqual(window.entry_date, "2025-11-10")
        self.assertEqual(window.sample_start, "2025-11-05")
        self.assertEqual(window.validation_start, "2025-12-01")

    def test_run_grid_backtest_executes_grid_cycle(self) -> None:
        prices = [20.0, 19.0, 18.0, 17.0, 18.2, 19.1, 20.0, 18.0, 19.3, 20.2]
        frame = build_test_frame(prices, start="2025-10-01")

        result = run_grid_backtest(
            data=frame,
            scenario_name="unit_test",
            grid_spacing_pct=0.05,
            grid_count=3,
            take_profit_pct=0.05,
            total_capital=200000,
        )

        summary = result["summary"]
        events = result["events"]

        self.assertTrue(summary["TriggeredEntry"])
        self.assertNotEqual(summary["EntryDate"], "")
        self.assertFalse(events.empty)
        self.assertTrue({"base_buy", "grid_buy"}.issubset(set(events["EventType"])))

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
        self.assertEqual(window.entry_date, "2026-04-01 11:45:00")
        self.assertFalse(in_sample.empty)
        self.assertFalse(validation.empty)


if __name__ == "__main__":
    unittest.main()
