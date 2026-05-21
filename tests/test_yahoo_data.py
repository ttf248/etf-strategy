import tempfile
import unittest
from pathlib import Path

import pandas as pd

from etf_strategy.data.yahoo import DEFAULT_DAILY_PERIOD, download_price_bars, merge_price_bars, save_price_bars


class YahooDataTests(unittest.TestCase):
    """覆盖行情合并保存和日线默认下载口径。"""

    def test_merge_price_bars_keeps_latest_duplicate_rows(self) -> None:
        existing = pd.DataFrame(
            {
                "Date": ["2026-05-20 09:30:00", "2026-05-20 09:45:00"],
                "Open": [10.0, 10.1],
                "High": [10.2, 10.3],
                "Low": [9.9, 10.0],
                "Close": [10.1, 10.2],
                "Volume": [100, 200],
            }
        )
        incoming = pd.DataFrame(
            {
                "Date": ["2026-05-20 09:45:00", "2026-05-20 10:00:00"],
                "Open": [10.4, 10.5],
                "High": [10.5, 10.6],
                "Low": [10.3, 10.4],
                "Close": [10.45, 10.55],
                "Volume": [999, 300],
            }
        )

        merged = merge_price_bars(existing, incoming, interval="15m")

        self.assertEqual(
            list(merged["Date"]),
            ["2026-05-20 09:30:00", "2026-05-20 09:45:00", "2026-05-20 10:00:00"],
        )
        duplicate_row = merged.loc[merged["Date"] == "2026-05-20 09:45:00"].iloc[0]
        self.assertEqual(duplicate_row["Volume"], 999)
        self.assertAlmostEqual(float(duplicate_row["Close"]), 10.45)

    def test_save_price_bars_merges_with_existing_file(self) -> None:
        existing = pd.DataFrame(
            {
                "Date": ["2026-05-20", "2026-05-21"],
                "Open": [10.0, 10.5],
                "High": [10.2, 10.7],
                "Low": [9.8, 10.3],
                "Close": [10.1, 10.6],
                "Volume": [100, 200],
            }
        )
        incoming = pd.DataFrame(
            {
                "Date": ["2026-05-21", "2026-05-22"],
                "Open": [11.0, 11.5],
                "High": [11.2, 11.7],
                "Low": [10.8, 11.3],
                "Close": [11.1, 11.6],
                "Volume": [999, 300],
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "daily.csv"
            existing.to_csv(target, index=False, encoding="utf-8-sig")

            save_price_bars(incoming, target, interval="1d", merge_with_existing=True)
            merged = pd.read_csv(target, encoding="utf-8-sig")

        self.assertEqual(list(merged["Date"]), ["2026-05-20", "2026-05-21", "2026-05-22"])
        duplicate_row = merged.loc[merged["Date"] == "2026-05-21"].iloc[0]
        self.assertEqual(int(duplicate_row["Volume"]), 999)
        self.assertAlmostEqual(float(duplicate_row["Close"]), 11.1)

    def test_download_price_bars_uses_max_period_for_daily_without_range(self) -> None:
        captured: dict[str, object] = {}

        def fake_loader(**kwargs: object) -> pd.DataFrame:
            captured.update(kwargs)
            return pd.DataFrame(
                {
                    "Date": ["2026-05-20"],
                    "Open": [10.0],
                    "High": [10.2],
                    "Low": [9.8],
                    "Close": [10.1],
                    "Volume": [100],
                }
            )

        from unittest.mock import patch

        with patch("etf_strategy.data.yahoo._load_from_yfinance", side_effect=fake_loader):
            frame = download_price_bars(symbol="1810.HK", interval="1d")

        self.assertEqual(captured["period"], DEFAULT_DAILY_PERIOD)
        self.assertIsNone(captured["start_date"])
        self.assertIsNone(captured["end_date"])
        self.assertEqual(len(frame), 1)


if __name__ == "__main__":
    unittest.main()
