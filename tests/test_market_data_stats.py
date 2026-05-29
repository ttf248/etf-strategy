from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from strategy_studio.repositories.market_data import get_ingestion_job_detail, get_market_data_stats


class _ScalarListResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)


class _FakeSession:
    def __init__(
        self,
        *,
        scalar_results: list[object],
        execute_results: list[list[object]],
        scalars_results: list[list[object]],
    ) -> None:
        self._scalar_results = list(scalar_results)
        self._execute_results = list(execute_results)
        self._scalars_results = list(scalars_results)

    def scalar(self, _statement: object) -> object:
        return self._scalar_results.pop(0)

    def execute(self, _statement: object) -> list[object]:
        return self._execute_results.pop(0)

    def scalars(self, _statement: object) -> _ScalarListResult:
        return _ScalarListResult(self._scalars_results.pop(0))


class MarketDataStatsTests(unittest.TestCase):
    """覆盖多渠道统计结构的关键返回字段。"""

    def test_get_market_data_stats_includes_provider_summaries_and_ingestion_jobs(self) -> None:
        now = datetime(2026, 5, 29, 12, 30, tzinfo=UTC)
        session = _FakeSession(
            scalar_results=[3, 120],
            execute_results=[
                [
                    SimpleNamespace(interval="1d", bar_count=80),
                    SimpleNamespace(interval="15m", bar_count=40),
                ],
                [
                    SimpleNamespace(
                        provider_key="tdx_qfq",
                        provider_name="通达信前复权",
                        provider_type="derived_market_data",
                        status="active",
                        series_count=1,
                        bars_count=6314,
                        action_count=0,
                        segment_count=26,
                        manifest_count=0,
                        intervals=["1d"],
                        adjustment_kinds=["qfq"],
                        series_last_ingested_at=now,
                        latest_bar_time=datetime(2026, 5, 28, 0, 0),
                        latest_action_at=None,
                        latest_segment_at=now,
                        latest_manifest_at=None,
                        job_id=18,
                        latest_job_status="succeeded",
                        latest_job_requested_at=now,
                        latest_job_completed_at=now,
                    ),
                    SimpleNamespace(
                        provider_key="tushare",
                        provider_name="Tushare 公司行动",
                        provider_type="corporate_action",
                        status="active",
                        series_count=0,
                        bars_count=0,
                        action_count=25,
                        segment_count=0,
                        manifest_count=0,
                        intervals=None,
                        adjustment_kinds=None,
                        series_last_ingested_at=None,
                        latest_bar_time=None,
                        latest_action_at=now,
                        latest_segment_at=None,
                        latest_manifest_at=None,
                        job_id=17,
                        latest_job_status="succeeded",
                        latest_job_requested_at=now,
                        latest_job_completed_at=now,
                    ),
                ],
                [
                    (
                        SimpleNamespace(
                            id=18,
                            provider_id=3,
                            job_type="tdx_qfq_rebuild",
                            status="succeeded",
                            targets_total=1,
                            targets_completed=1,
                            rows_inserted=0,
                            rows_updated=6314,
                            error_count=0,
                            requested_at=now,
                            completed_at=now,
                            error_message="",
                            target_scope_json={"symbol": "sh600000", "interval": "1d"},
                            requested_via="manual",
                        ),
                        "tdx_qfq",
                        "通达信前复权",
                    ),
                ],
            ],
            scalars_results=[
                [
                    SimpleNamespace(
                        id=9,
                        job_type="manual",
                        interval="1d",
                        status="succeeded",
                        started_at=now,
                        completed_at=now,
                        symbols_count=1,
                        bars_inserted=30,
                        bars_updated=0,
                        error_message="",
                    )
                ]
            ],
        )

        with patch(
            "strategy_studio.repositories.market_data.list_instrument_coverages",
            return_value=[
                {
                    "symbol": "1810.HK",
                    "name": "XIAOMI-W",
                    "exchange": "HK",
                    "interval": "1d",
                    "bar_count": 80,
                    "start_time": "2025-01-01 00:00:00",
                    "end_time": "2026-05-28 00:00:00",
                    "last_ingested_at": "2026-05-29 12:30:00+00:00",
                }
            ],
        ):
            stats = get_market_data_stats(session)

        self.assertEqual(stats["instrument_count"], 3)
        self.assertEqual(stats["total_bars"], 120)
        self.assertEqual(len(stats["provider_summaries"]), 2)
        self.assertEqual(stats["provider_summaries"][0]["provider_key"], "tdx_qfq")
        self.assertEqual(stats["provider_summaries"][0]["bars_count"], 6314)
        self.assertEqual(stats["provider_summaries"][0]["adjustment_kinds"], ["qfq"])
        self.assertEqual(stats["provider_summaries"][1]["action_count"], 25)
        self.assertEqual(len(stats["recent_ingestion_jobs"]), 1)
        self.assertEqual(stats["recent_ingestion_jobs"][0]["provider_key"], "tdx_qfq")
        self.assertEqual(stats["recent_ingestion_jobs"][0]["target_symbol"], "sh600000")
        self.assertEqual(stats["recent_ingestion_jobs"][0]["interval"], "1d")
        self.assertEqual(stats["recent_ingestion_jobs"][0]["summary_json"], {})
        self.assertEqual(stats["recent_sync_runs"][0]["status"], "succeeded")

    def test_get_market_data_stats_exposes_pipeline_workflow_summary(self) -> None:
        now = datetime(2026, 5, 29, 13, 0, tzinfo=UTC)
        workflow_summary = {
            "requested_symbol": "SH600000",
            "requested_interval": "all",
            "child_ingestion_job_ids": [19, 20, 21, 22, 23],
            "workflow_results": [
                {
                    "step": "tdx_raw",
                    "step_label": "通达信原始导入",
                    "provider": "tdx",
                    "interval": "all",
                    "symbols_count": 3,
                    "bars_inserted": 600,
                    "bars_updated": 10,
                    "status": "succeeded",
                    "child_ingestion_job_ids": [19, 20, 21],
                },
                {
                    "step": "tushare_actions",
                    "step_label": "Tushare 公司行动抓取",
                    "provider": "tushare",
                    "interval": "corp_actions",
                    "symbols_count": 1,
                    "bars_inserted": 5,
                    "bars_updated": 0,
                    "status": "succeeded",
                    "child_ingestion_job_ids": [22],
                },
            ],
        }
        session = _FakeSession(
            scalar_results=[0, 0],
            execute_results=[
                [],
                [],
                [
                    (
                        SimpleNamespace(
                            id=18,
                            provider_id=5,
                            job_type="tdx_pipeline_workflow",
                            status="succeeded",
                            targets_total=3,
                            targets_completed=3,
                            rows_inserted=605,
                            rows_updated=10,
                            error_count=0,
                            requested_at=now,
                            completed_at=now,
                            error_message="",
                            target_scope_json={},
                            summary_json=workflow_summary,
                            requested_via="manual",
                        ),
                        "tdx_pipeline",
                        "A 股统一补数链路",
                    ),
                ],
            ],
            scalars_results=[[]],
        )

        with patch("strategy_studio.repositories.market_data.list_instrument_coverages", return_value=[]):
            stats = get_market_data_stats(session)

        self.assertEqual(len(stats["recent_ingestion_jobs"]), 1)
        job = stats["recent_ingestion_jobs"][0]
        self.assertEqual(job["provider_key"], "tdx_pipeline")
        self.assertEqual(job["target_symbol"], "SH600000")
        self.assertEqual(job["interval"], "all")
        self.assertEqual(job["summary_json"]["child_ingestion_job_ids"], [19, 20, 21, 22, 23])
        self.assertEqual(job["summary_json"]["workflow_results"][0]["step_label"], "通达信原始导入")

    def test_get_ingestion_job_detail_includes_items(self) -> None:
        now = datetime(2026, 5, 29, 14, 0, tzinfo=UTC)
        session = _FakeSession(
            scalar_results=[],
            execute_results=[
                [
                    (
                        SimpleNamespace(
                            id=24,
                            provider_id=5,
                            job_type="tdx_pipeline_workflow",
                            status="partially_failed",
                            targets_total=3,
                            targets_completed=3,
                            rows_inserted=312,
                            rows_updated=878,
                            error_count=1,
                            requested_at=now,
                            started_at=now,
                            completed_at=now,
                            error_message="有子步骤失败",
                            target_scope_json={"symbol": "", "interval": "all"},
                            options_json={"force": True},
                            summary_json={"workflow_results": [{"step": "tdx_raw", "status": "succeeded"}]},
                            requested_via="manual",
                        ),
                        "tdx_pipeline",
                        "A 股统一补数链路",
                    ),
                ],
                [
                    (
                        SimpleNamespace(
                            id=101,
                            job_id=24,
                            instrument_id=7,
                            series_id=8,
                            item_key="vipdoc/sh/lday/sh600000.day:1d:raw",
                            source_symbol="SH600000",
                            interval="1d",
                            stage="completed",
                            status="succeeded",
                            rows_inserted=12,
                            rows_updated=0,
                            error_message="",
                            details_json={"source_path": "vipdoc/sh/lday/sh600000.day"},
                            started_at=now,
                            completed_at=now,
                        ),
                        "SH600000",
                    ),
                    (
                        SimpleNamespace(
                            id=102,
                            job_id=24,
                            instrument_id=None,
                            series_id=None,
                            item_key="vipdoc/sz/lday/sz000001.day:1d:raw",
                            source_symbol="SZ000001",
                            interval="1d",
                            stage="failed",
                            status="failed",
                            rows_inserted=0,
                            rows_updated=0,
                            error_message="读取失败",
                            details_json={"source_path": "vipdoc/sz/lday/sz000001.day"},
                            started_at=now,
                            completed_at=now,
                        ),
                        "",
                    ),
                ],
            ],
            scalars_results=[],
        )

        payload = get_ingestion_job_detail(session, 24)

        assert payload is not None
        self.assertEqual(payload["provider_key"], "tdx_pipeline")
        self.assertEqual(payload["job_type"], "tdx_pipeline_workflow")
        self.assertEqual(payload["items"][0]["instrument_symbol"], "SH600000")
        self.assertEqual(payload["items"][1]["status"], "failed")
        self.assertEqual(payload["items"][1]["error_message"], "读取失败")


if __name__ == "__main__":
    unittest.main()
