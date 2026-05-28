import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from strategy_studio.data.southbound import (
    fetch_southbound_shanghai_eligible_rows,
    normalize_southbound_symbol,
)
from strategy_studio.data.yahoo import DEFAULT_DAILY_PERIOD, download_price_bars, merge_price_bars, save_price_bars


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

    def test_save_price_bars_rejects_local_csv_persistence(self) -> None:
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
            with self.assertRaisesRegex(RuntimeError, "数据库优先模式"):
                save_price_bars(incoming, target, interval="1d", merge_with_existing=True)

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

        with patch("strategy_studio.data.yahoo._load_from_yfinance", side_effect=fake_loader):
            frame = download_price_bars(symbol="1810.HK", interval="1d", proxy="http://127.0.0.1:7897")

        self.assertEqual(captured["proxy"], "http://127.0.0.1:7897")
        self.assertEqual(captured["period"], DEFAULT_DAILY_PERIOD)
        self.assertIsNone(captured["start_date"])
        self.assertIsNone(captured["end_date"])
        self.assertEqual(len(frame), 1)

    def test_download_price_bars_requires_proxy(self) -> None:
        with self.assertRaisesRegex(ValueError, "必须配置代理"):
            download_price_bars(symbol="1810.HK", interval="15m", period="60d")

    def test_download_price_bars_stops_when_yahoo_fails(self) -> None:
        with patch("strategy_studio.data.yahoo._load_from_yfinance", side_effect=RuntimeError("rate limited")):
            with self.assertRaisesRegex(ValueError, "Yahoo 行情下载失败"):
                download_price_bars(
                    symbol="1810.HK",
                    interval="15m",
                    period="60d",
                    proxy="http://127.0.0.1:7897",
                )

    @patch("strategy_studio.data.southbound.requests.get")
    def test_fetch_southbound_shanghai_eligible_rows_parses_official_jsonp(self, mock_get: Mock) -> None:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = (
            'jsonpCallback({"pageHelp":{"data":['
            '{"SECURITY_CODE":"1","ABBR_EN":"CKH HOLDINGS","ABBR_CN":"长和　　　　　　","SECURITY_TYPE":"股票","UPDATE_DATE":"2026-05-21"},'
            '{"SECURITY_CODE":"2800","ABBR_EN":"TRACKER FUND","ABBR_CN":"盈富基金","SECURITY_TYPE":"ETF","UPDATE_DATE":"2026-05-21"}]}})'
        )
        mock_get.return_value = mock_response

        rows = fetch_southbound_shanghai_eligible_rows()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["SecurityCode"], "00001")
        self.assertEqual(rows[0]["AbbrCn"], "长和")
        self.assertEqual(rows[1]["SecurityType"], "ETF")
        self.assertEqual(normalize_southbound_symbol(rows[0]["SecurityCode"]), "0001.HK")
        self.assertEqual(normalize_southbound_symbol(rows[1]["SecurityCode"]), "2800.HK")

if __name__ == "__main__":
    unittest.main()
