from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from strategy_studio.repositories.market_data import load_backtest_price_frame_from_database, upsert_market_data_frame


class _ExecuteResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class _SessionDouble:
    def __init__(self, execute_results: list[list[object]]) -> None:
        self._execute_results = list(execute_results)
        self.execute_calls = 0

    def execute(self, _statement: object) -> _ExecuteResult:
        self.execute_calls += 1
        return _ExecuteResult(self._execute_results.pop(0))

    def scalars(self, _statement: object) -> object:
        raise AssertionError("统一 K 线 upsert 不应再为统计数量预查已存在时间戳。")


class _ScalarRows:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _BacktestSessionDouble:
    def __init__(self, scalars_results: list[list[object]]) -> None:
        self._scalars_results = list(scalars_results)

    def scalars(self, _statement: object) -> _ScalarRows:
        return _ScalarRows(self._scalars_results.pop(0))


class MarketDataRepositoryTests(unittest.TestCase):
    """覆盖统一 K 线仓储里和前复权性能相关的关键行为。"""

    def test_upsert_market_data_frame_uses_returning_counts_without_prequery(self) -> None:
        session = _SessionDouble(
            execute_results=[
                [
                    SimpleNamespace(inserted=True),
                    SimpleNamespace(inserted=False),
                ]
            ]
        )
        series = SimpleNamespace(
            id=17,
            first_bar_time=None,
            last_bar_time=None,
            last_ingested_at=None,
        )
        frame = pd.DataFrame(
            [
                {
                    "Date": "2026-05-28",
                    "Open": 10.0,
                    "High": 10.5,
                    "Low": 9.8,
                    "Close": 10.2,
                    "Volume": 100,
                    "Amount": 1000.0,
                },
                {
                    "Date": "2026-05-29",
                    "Open": 10.3,
                    "High": 10.7,
                    "Low": 10.1,
                    "Close": 10.6,
                    "Volume": 110,
                    "Amount": 1100.0,
                },
            ]
        )

        inserted_count, updated_count = upsert_market_data_frame(session, series, frame)

        self.assertEqual(inserted_count, 1)
        self.assertEqual(updated_count, 1)
        self.assertEqual(session.execute_calls, 1)
        self.assertEqual(series.first_bar_time, datetime(2026, 5, 28, 0, 0))
        self.assertEqual(series.last_bar_time, datetime(2026, 5, 29, 0, 0))
        self.assertIsNotNone(series.last_ingested_at)

    def test_upsert_market_data_frame_accumulates_returning_counts_across_batches(self) -> None:
        session = _SessionDouble(
            execute_results=[
                [SimpleNamespace(inserted=True) for _ in range(1500)],
                [SimpleNamespace(inserted=False)],
            ]
        )
        series = SimpleNamespace(
            id=18,
            first_bar_time=datetime(2026, 5, 1, 0, 0),
            last_bar_time=datetime(2026, 5, 15, 0, 0),
            last_ingested_at=None,
        )
        frame = pd.DataFrame(
            [
                {
                    "Date": f"2026-05-{(index % 28) + 1:02d}",
                    "Open": 20.0 + index,
                    "High": 20.5 + index,
                    "Low": 19.5 + index,
                    "Close": 20.1 + index,
                    "Volume": 1000 + index,
                    "Amount": 5000.0 + index,
                }
                for index in range(1501)
            ]
        )

        inserted_count, updated_count = upsert_market_data_frame(session, series, frame)

        self.assertEqual(inserted_count, 1500)
        self.assertEqual(updated_count, 1)
        self.assertEqual(session.execute_calls, 2)
        self.assertEqual(series.first_bar_time, datetime(2026, 5, 1, 0, 0))
        self.assertEqual(series.last_bar_time, datetime(2026, 5, 28, 0, 0))
        self.assertIsNotNone(series.last_ingested_at)

    def test_upsert_market_data_frame_skips_conflict_update_when_values_unchanged(self) -> None:
        session = _SessionDouble(execute_results=[[]])
        series = SimpleNamespace(
            id=19,
            first_bar_time=datetime(2026, 5, 1, 0, 0),
            last_bar_time=datetime(2026, 5, 10, 0, 0),
            last_ingested_at=None,
        )
        frame = pd.DataFrame(
            [
                {
                    "Date": "2026-05-09",
                    "Open": 8.0,
                    "High": 8.3,
                    "Low": 7.9,
                    "Close": 8.1,
                    "Volume": 80,
                    "Amount": 810.0,
                },
                {
                    "Date": "2026-05-10",
                    "Open": 8.2,
                    "High": 8.4,
                    "Low": 8.0,
                    "Close": 8.3,
                    "Volume": 82,
                    "Amount": 830.0,
                },
            ]
        )

        inserted_count, updated_count = upsert_market_data_frame(session, series, frame)

        self.assertEqual(inserted_count, 0)
        self.assertEqual(updated_count, 0)
        self.assertEqual(session.execute_calls, 1)
        self.assertEqual(series.first_bar_time, datetime(2026, 5, 1, 0, 0))
        self.assertEqual(series.last_bar_time, datetime(2026, 5, 10, 0, 0))
        self.assertIsNotNone(series.last_ingested_at)

    def test_load_backtest_price_frame_prefers_legacy_price_bars(self) -> None:
        session = _BacktestSessionDouble(
            scalars_results=[
                [
                    SimpleNamespace(bar_time=datetime(2026, 5, 28, 0, 0), open=10.0, high=10.5, low=9.9, close=10.2, volume=100),
                    SimpleNamespace(bar_time=datetime(2026, 5, 29, 0, 0), open=10.3, high=10.7, low=10.1, close=10.6, volume=120),
                ]
            ]
        )

        with (
            patch("strategy_studio.repositories.market_data.get_instrument_by_symbol", return_value=SimpleNamespace(id=7, symbol="SPY")),
            patch("strategy_studio.repositories.market_data.list_provider_series", side_effect=AssertionError("旧表命中时不应再查询统一序列")),
        ):
            snapshot = load_backtest_price_frame_from_database(session, "SPY", "1d")

        self.assertEqual(snapshot.source_kind, "legacy_price_bars")
        self.assertEqual(snapshot.source_label, "database://price_bars/SPY/1d")
        self.assertEqual(snapshot.provider_key, "yahoo")
        self.assertEqual(snapshot.adjustment_kind, "raw")
        self.assertListEqual(list(snapshot.frame.columns), ["Open", "High", "Low", "Close", "Volume"])
        self.assertEqual(snapshot.frame.iloc[-1]["Close"], 10.6)

    def test_load_backtest_price_frame_falls_back_to_unique_market_data_series(self) -> None:
        session = _BacktestSessionDouble(
            scalars_results=[
                [],
                [
                    SimpleNamespace(bar_time=datetime(2026, 5, 28, 0, 0), open=12.0, high=12.4, low=11.8, close=12.2, volume=200),
                    SimpleNamespace(bar_time=datetime(2026, 5, 29, 0, 0), open=12.3, high=12.8, low=12.1, close=12.7, volume=220),
                ],
            ]
        )
        series_rows = [
            {
                "series_id": 31,
                "provider_key": "tdx_qfq",
                "instrument_symbol": "SH600000",
                "interval": "1d",
                "adjustment_kind": "qfq",
                "bar_count": 2,
                "is_active": True,
            }
        ]

        with (
            patch("strategy_studio.repositories.market_data.get_instrument_by_symbol", return_value=SimpleNamespace(id=8, symbol="SH600000")),
            patch("strategy_studio.repositories.market_data.list_provider_series", return_value=series_rows),
        ):
            snapshot = load_backtest_price_frame_from_database(session, "SH600000", "1d")

        self.assertEqual(snapshot.source_kind, "market_data_series")
        self.assertEqual(snapshot.series_id, 31)
        self.assertEqual(snapshot.provider_key, "tdx_qfq")
        self.assertEqual(snapshot.adjustment_kind, "qfq")
        self.assertEqual(snapshot.source_label, "database://market_data_series/tdx_qfq/SH600000/1d/qfq")
        self.assertEqual(snapshot.frame.iloc[0]["Open"], 12.0)

    def test_load_backtest_price_frame_rejects_ambiguous_market_data_series(self) -> None:
        session = _BacktestSessionDouble(scalars_results=[[]])
        series_rows = [
            {
                "series_id": 41,
                "provider_key": "tdx",
                "instrument_symbol": "SH600000",
                "interval": "1d",
                "adjustment_kind": "raw",
                "bar_count": 100,
                "is_active": True,
            },
            {
                "series_id": 42,
                "provider_key": "tdx_qfq",
                "instrument_symbol": "SH600000",
                "interval": "1d",
                "adjustment_kind": "qfq",
                "bar_count": 100,
                "is_active": True,
            },
        ]

        with (
            patch("strategy_studio.repositories.market_data.get_instrument_by_symbol", return_value=SimpleNamespace(id=9, symbol="SH600000")),
            patch("strategy_studio.repositories.market_data.list_provider_series", return_value=series_rows),
        ):
            with self.assertRaisesRegex(ValueError, "多条可用于回测的统一行情序列"):
                load_backtest_price_frame_from_database(session, "SH600000", "1d")


if __name__ == "__main__":
    unittest.main()
