from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from strategy_studio.repositories.market_data import upsert_market_data_frame


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


if __name__ == "__main__":
    unittest.main()
