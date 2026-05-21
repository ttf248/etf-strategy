import unittest

import pandas as pd

from etf_strategy.strategy.grid import locate_recent_decline_window, run_grid_backtest


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


if __name__ == "__main__":
    unittest.main()
