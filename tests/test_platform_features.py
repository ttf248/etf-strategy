from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from strategy_studio.cli import build_parser
from strategy_studio.platform_cli import handle_api, handle_check_db, handle_check_runtime, handle_sync_now
from strategy_studio.services.backtests import _estimate_eta_seconds, _normalize_artifacts, _resolve_effective_parallelism
from strategy_studio.services.platform import record_platform_heartbeat
from strategy_studio.services.sync import sync_market_data
from strategy_studio.services.templates import build_seed_templates, normalize_parameter_space, resolve_backtest_request_payload
from strategy_studio.strategy.sampling import DeclineWindow
from strategy_studio.web.app import create_app
import strategy_studio.data.market_rules as market_rules
import strategy_studio.services.platform as platform_service
import strategy_studio.services.sync as sync_service


class PlatformFeatureTests(unittest.TestCase):
    """覆盖平台化新增命令和 API 基础契约。"""

    def test_cli_registers_platform_commands(self) -> None:
        parser = build_parser()

        init_args = parser.parse_args(["init-db"])
        check_db_args = parser.parse_args(["check-db", "--json"])
        check_runtime_args = parser.parse_args(["check-runtime", "--json"])
        sync_args = parser.parse_args(["sync-now", "--provider", "tdx", "--symbol", "sh600000", "--interval", "1d", "--force", "--limit", "3"])
        sync_minute_args = parser.parse_args(["sync-now", "--provider", "tdx", "--symbol", "sh600000", "--interval", "1m", "--limit", "1"])
        sync_all_args = parser.parse_args(["sync-now", "--provider", "tdx", "--interval", "all", "--limit", "2", "--batch-rounds", "3"])
        yahoo_set_args = parser.parse_args(["sync-now", "--provider", "yahoo", "--symbol-set", "yahoo_global_active_100", "--interval", "15m", "--limit", "100"])
        yahoo_pipeline_args = parser.parse_args(["sync-now", "--provider", "yahoo_pipeline", "--symbol-set", "yahoo_global_active_100", "--interval", "all", "--limit", "100"])
        tushare_args = parser.parse_args(["sync-now", "--provider", "tushare", "--symbol", "600000.SH", "--limit", "2"])
        qfq_args = parser.parse_args(["sync-now", "--provider", "tdx_qfq", "--symbol", "sh600000", "--interval", "1d", "--limit", "2"])
        pipeline_args = parser.parse_args(["sync-now", "--provider", "tdx_pipeline", "--symbol", "sh600000", "--interval", "all", "--force", "--limit", "2"])
        api_args = parser.parse_args(["api", "--host", "127.0.0.1", "--port", "8000"])
        replace_args = parser.parse_args(["api", "--replace-existing"])
        worker_args = parser.parse_args(["worker", "--poll-interval", "3", "--max-concurrent-jobs", "2", "--max-optimization-workers", "4"])

        self.assertEqual(init_args.command, "init-db")
        self.assertEqual(check_db_args.command, "check-db")
        self.assertTrue(check_db_args.json)
        self.assertEqual(check_runtime_args.command, "check-runtime")
        self.assertTrue(check_runtime_args.json)
        self.assertEqual(sync_args.command, "sync-now")
        self.assertEqual(sync_args.provider, "tdx")
        self.assertEqual(sync_args.symbol, "sh600000")
        self.assertTrue(sync_args.force)
        self.assertEqual(sync_args.limit, 3)
        self.assertEqual(sync_minute_args.provider, "tdx")
        self.assertEqual(sync_minute_args.interval, "1m")
        self.assertEqual(sync_minute_args.limit, 1)
        self.assertEqual(sync_all_args.provider, "tdx")
        self.assertEqual(sync_all_args.interval, "all")
        self.assertEqual(sync_all_args.limit, 2)
        self.assertEqual(sync_all_args.batch_rounds, 3)
        self.assertEqual(yahoo_set_args.provider, "yahoo")
        self.assertEqual(yahoo_set_args.symbol_set, "yahoo_global_active_100")
        self.assertEqual(yahoo_set_args.limit, 100)
        self.assertEqual(yahoo_pipeline_args.provider, "yahoo_pipeline")
        self.assertEqual(yahoo_pipeline_args.symbol_set, "yahoo_global_active_100")
        self.assertEqual(yahoo_pipeline_args.interval, "all")
        self.assertEqual(tushare_args.provider, "tushare")
        self.assertEqual(tushare_args.symbol, "600000.SH")
        self.assertEqual(tushare_args.limit, 2)
        self.assertEqual(qfq_args.provider, "tdx_qfq")
        self.assertEqual(qfq_args.symbol, "sh600000")
        self.assertEqual(qfq_args.limit, 2)
        self.assertEqual(pipeline_args.provider, "tdx_pipeline")
        self.assertEqual(pipeline_args.interval, "all")
        self.assertTrue(pipeline_args.force)
        self.assertEqual(pipeline_args.limit, 2)
        self.assertFalse(hasattr(init_args, "with_migration"))
        self.assertEqual(api_args.command, "api")
        self.assertEqual(api_args.host, "127.0.0.1")
        self.assertEqual(api_args.port, 8000)
        self.assertTrue(replace_args.replace_existing)
        self.assertEqual(parser.parse_args(["scheduler"]).command, "scheduler")
        self.assertEqual(worker_args.poll_interval, 3)
        self.assertEqual(worker_args.max_concurrent_jobs, 2)
        self.assertEqual(worker_args.max_optimization_workers, 4)

    def test_hk_lot_size_cache_only_keeps_process_memory(self) -> None:
        self.assertFalse(hasattr(market_rules, "HK_LOT_SIZE_CACHE_PATH"))

    def test_backtest_artifacts_use_database_only_payload(self) -> None:
        payload = _normalize_artifacts(
            {
                "combined_summary_path": None,
                "optimization": {
                    "decline_window": DeclineWindow(
                        peak_price=32.5,
                        peak_date="2026-01-05",
                        entry_date="2026-01-08",
                        entry_price=31.2,
                        sample_start="2025-09-01",
                        sample_end="2025-12-31",
                        validation_start="2026-01-01",
                    ),
                    "best_paths": {},
                },
                "validation": {"paths": {}},
            },
            template_snapshot={"template_key": "grid_15m_realistic_default"},
        )

        self.assertEqual(payload["storage_mode"], "database_only")
        self.assertEqual(payload["data_source"], "database")
        self.assertEqual(payload["artifact_transport"], "embedded_database_rows")
        self.assertNotIn("report_path", payload)
        self.assertEqual(payload["template_snapshot"]["template_key"], "grid_15m_realistic_default")

    def test_web_api_health_and_stats(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.fetch_market_data_stats",
            return_value={
                "instrument_count": 2,
                "total_bars": 10,
                "by_interval": [],
                "coverages": [],
                "provider_summaries": [{"provider_key": "yahoo", "series_count": 1}],
                "recent_ingestion_jobs": [{"id": 7, "provider_key": "yahoo", "status": "succeeded"}],
                "recent_sync_runs": [],
            },
        ):
            health_response = client.get("/health")
            stats_response = client.get("/api/market-data/stats")

        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["status"], "ok")
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.json()["instrument_count"], 2)
        self.assertEqual(stats_response.json()["provider_summaries"][0]["provider_key"], "yahoo")

    def test_handle_check_runtime_prints_summary_and_returns_zero(self) -> None:
        payload = {
            "api": {"status": "down", "base_url": "http://127.0.0.1:8000"},
            "frontend": {"status": "down", "base_url": "http://127.0.0.1:3000"},
            "database": {
                "status": "ok",
                "configured_database": "etf_strategy",
                "migration_state": "head",
                "url": "postgresql+psycopg://postgres:***@localhost:5432/etf_strategy",
            },
            "heartbeats": [
                {"service_name": "worker", "status": "running", "age_seconds": 2, "pid": 1001, "last_seen_at": "2026-05-30 02:30:00+08:00"},
                {"service_name": "scheduler", "status": "running", "age_seconds": 3, "pid": 1002, "last_seen_at": "2026-05-30 02:29:59+08:00"},
            ],
            "queue": {"queued": 1, "running": 2, "cancel_requested": 0, "cancelled": 0, "succeeded": 5, "failed": 1},
            "market_data_runtime": {
                "yahoo": {
                    "status": "ok",
                    "default_symbol_set": "yahoo_global_active_100",
                    "proxy_configured": False,
                    "proxy_source": "none",
                    "system_proxy_candidate": "http://127.0.0.1:7897",
                    "system_proxy_enabled": False,
                    "system_proxy_source": "windows_internet_settings",
                    "warning_message": "检测到系统代理候选，但当前项目不会自动使用；请通过 --proxy 或 STRATEGY_STUDIO_PROXY 显式传入。",
                },
                "tdx": {
                    "status": "ok",
                    "vipdoc_exists": True,
                    "path_source": "config_file",
                    "vipdoc_path": "G:\\new_tdx64\\vipdoc",
                    "market_inventory": {
                        "total_files": 12,
                        "by_interval": {"1d": 4, "1m": 4, "5m": 4},
                        "by_market": {"sh": {"total_files": 6}, "sz": {"total_files": 6}},
                    },
                },
                "tushare": {"status": "ok", "token_present": True, "rate_limit_per_minute": 450, "config_path": "F:\\trade\\tdx\\config.local.yaml"},
            },
        }
        args = SimpleNamespace(json=False)

        with (
            patch("strategy_studio.platform_cli._import_platform_module", return_value=SimpleNamespace(fetch_platform_status=lambda: payload)),
            patch("builtins.print") as mock_print,
        ):
            exit_code = handle_check_runtime(args)

        self.assertEqual(exit_code, 0)
        rendered = "\n".join(" ".join(str(part) for part in call.args) for call in mock_print.call_args_list)
        self.assertIn("平台运行态检查：", rendered)
        self.assertIn("数据库：ok", rendered)
        self.assertIn("Yahoo 代理候选：http://127.0.0.1:7897", rendered)
        self.assertIn("Yahoo 提示：检测到系统代理候选", rendered)
        self.assertIn("TDX 路径：G:\\new_tdx64\\vipdoc", rendered)
        self.assertIn("Tushare 配置：F:\\trade\\tdx\\config.local.yaml", rendered)

    def test_handle_check_runtime_returns_nonzero_when_worker_missing(self) -> None:
        payload = {
            "api": {"status": "down", "base_url": "http://127.0.0.1:8000"},
            "frontend": {"status": "down", "base_url": "http://127.0.0.1:3000"},
            "database": {"status": "ok", "configured_database": "etf_strategy", "migration_state": "head"},
            "heartbeats": [{"service_name": "scheduler", "status": "running", "age_seconds": 3, "pid": 1002, "last_seen_at": "2026-05-30 02:29:59+08:00"}],
            "queue": {},
            "market_data_runtime": {
                "yahoo": {"status": "ok"},
                "tdx": {"status": "ok"},
                "tushare": {"status": "ok"},
            },
        }
        args = SimpleNamespace(json=True)

        with (
            patch("strategy_studio.platform_cli._import_platform_module", return_value=SimpleNamespace(fetch_platform_status=lambda: payload)),
            patch("builtins.print"),
        ):
            exit_code = handle_check_runtime(args)

        self.assertEqual(exit_code, 1)

    def test_web_api_backtest_route_supports_unified_market_data_fields(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch("strategy_studio.web.app.submit_backtest", return_value={"job_id": 13, "status": "queued"}) as mock_submit:
            response = client.post(
                "/api/backtests",
                json={
                    "symbol": "sh600000",
                    "interval": "1d",
                    "strategy_kind": "dca",
                    "market_data_provider": "tdx_qfq",
                    "market_data_adjustment_kind": "qfq",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], 13)
        request = mock_submit.call_args.args[0]
        self.assertEqual(request.symbol, "sh600000")
        self.assertEqual(request.market_data_provider, "tdx_qfq")
        self.assertEqual(request.market_data_adjustment_kind, "qfq")

    def test_web_api_market_data_ingestion_job_detail_route(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.fetch_ingestion_job_detail",
            return_value={
                "id": 24,
                "provider_key": "tdx_pipeline",
                "provider_name": "A 股统一补数链路",
                "status": "succeeded",
                "items": [{"id": 101, "item_key": "tdx_raw:all", "status": "succeeded"}],
            },
        ) as mock_detail:
            response = client.get("/api/market-data/ingestion-jobs/24")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider_key"], "tdx_pipeline")
        self.assertEqual(response.json()["items"][0]["id"], 101)
        mock_detail.assert_called_once_with(24)

    def test_web_api_market_data_ingestion_job_detail_route_returns_404(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch("strategy_studio.web.app.fetch_ingestion_job_detail", return_value=None) as mock_detail:
            response = client.get("/api/market-data/ingestion-jobs/9999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "导入任务不存在。")
        mock_detail.assert_called_once_with(9999)

    def test_web_api_market_data_provider_series_route(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.fetch_provider_series",
            return_value=[
                {
                    "series_id": 11,
                    "provider_key": "tdx",
                    "provider_name": "通达信本地行情",
                    "instrument_symbol": "SH600000",
                    "interval": "1d",
                    "adjustment_kind": "raw",
                    "bar_count": 6314,
                }
            ],
        ) as mock_series:
            response = client.get("/api/market-data/provider-series?provider=tdx&limit=20")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["provider_key"], "tdx")
        self.assertEqual(response.json()[0]["series_id"], 11)
        mock_series.assert_called_once_with(provider_key="tdx", symbol=None, limit=20)

    def test_web_api_market_data_provider_series_route_supports_symbol_filter(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.fetch_provider_series",
            return_value=[
                {
                    "series_id": 12,
                    "provider_key": "tdx_qfq",
                    "instrument_symbol": "SH600000",
                    "interval": "1d",
                    "adjustment_kind": "qfq",
                    "bar_count": 6314,
                }
            ],
        ) as mock_series:
            response = client.get("/api/market-data/provider-series?provider=tdx_qfq&symbol=sh600000&limit=12")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["instrument_symbol"], "SH600000")
        mock_series.assert_called_once_with(provider_key="tdx_qfq", symbol="sh600000", limit=12)

    def test_web_api_market_data_symbol_diagnostics_route(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.fetch_symbol_diagnostics",
            return_value={
                "symbol": "SH600000",
                "summary": {
                    "series_count": 2,
                    "qfq_series_count": 1,
                    "qfq_normal_skip_ready_count": 1,
                    "qfq_force_cache_ready_count": 1,
                },
                "series_rows": [{"series_id": 11}],
                "corporate_action_rows": [{"event_id": 21}],
                "adjustment_segment_rows": [{"segment_id": 31}],
                "source_file_manifest_rows": [{"manifest_id": 41}],
                "recent_ingestion_jobs": [{"id": 51}],
                "qfq_series_diagnostics": [{"series_id": 61, "normal_skip_ready": True}],
            },
        ) as mock_diagnostics:
            response = client.get("/api/market-data/symbol-diagnostics?symbol=sh600000&limit=12")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["symbol"], "SH600000")
        self.assertEqual(response.json()["summary"]["series_count"], 2)
        self.assertEqual(response.json()["summary"]["qfq_force_cache_ready_count"], 1)
        self.assertEqual(response.json()["source_file_manifest_rows"][0]["manifest_id"], 41)
        self.assertEqual(response.json()["qfq_series_diagnostics"][0]["series_id"], 61)
        mock_diagnostics.assert_called_once_with(symbol="sh600000", limit=12)

    def test_web_api_market_data_corporate_actions_route(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.fetch_corporate_actions",
            return_value=[
                {
                    "event_id": 21,
                    "provider_key": "tushare",
                    "instrument_symbol": "SH600000",
                    "ex_date": "2026-05-29",
                    "cash_dividend": 0.5,
                }
            ],
        ) as mock_actions:
            response = client.get("/api/market-data/corporate-actions?provider=tushare&symbol=sh600000&limit=20")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["event_id"], 21)
        self.assertEqual(response.json()[0]["provider_key"], "tushare")
        mock_actions.assert_called_once_with(provider_key="tushare", symbol="sh600000", limit=20)

    def test_web_api_market_data_adjustment_segments_route(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.fetch_adjustment_segments",
            return_value=[
                {
                    "segment_id": 31,
                    "provider_key": "tdx_qfq",
                    "instrument_symbol": "SH600000",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-29",
                    "adjust_a": 0.91,
                }
            ],
        ) as mock_segments:
            response = client.get("/api/market-data/adjustment-segments?provider=tdx_qfq&symbol=sh600000&limit=20")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["segment_id"], 31)
        self.assertEqual(response.json()[0]["provider_key"], "tdx_qfq")
        mock_segments.assert_called_once_with(provider_key="tdx_qfq", symbol="sh600000", limit=20)

    def test_web_api_market_data_source_file_manifests_route(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.fetch_source_file_manifests",
            return_value=[
                {
                    "manifest_id": 41,
                    "provider_key": "tdx",
                    "source_path": "sh/lday/sh600000.day",
                    "interval": "1d",
                    "status": "success",
                }
            ],
        ) as mock_manifests:
            response = client.get("/api/market-data/source-file-manifests?provider=tdx&symbol=sh600000&interval=1d&limit=20")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["manifest_id"], 41)
        self.assertEqual(response.json()[0]["provider_key"], "tdx")
        mock_manifests.assert_called_once_with(provider_key="tdx", symbol="sh600000", interval="1d", limit=20)

    def test_web_api_market_data_sync_route_passes_provider_specific_fields(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={"provider": "tdx", "ingestion_job_id": 3, "status": "queued"},
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "tdx",
                    "symbol": "sh600000",
                    "interval": "1d",
                    "vipdoc_path": "G:/new_tdx64/vipdoc",
                    "force": True,
                    "limit": 2,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "tdx")
        mock_sync.assert_called_once_with(
            symbol="sh600000",
            symbol_set=None,
            interval="1d",
            proxy=None,
            period=None,
            provider="tdx",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=True,
            limit=2,
            batch_rounds=None,
        )

    def test_web_api_market_data_sync_route_supports_tdx_minute_interval(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={"provider": "tdx", "ingestion_job_id": 5, "status": "queued"},
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "tdx",
                    "symbol": "sh600000",
                    "interval": "5m",
                    "vipdoc_path": "G:/new_tdx64/vipdoc",
                    "limit": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "tdx")
        mock_sync.assert_called_once_with(
            symbol="sh600000",
            symbol_set=None,
            interval="5m",
            proxy=None,
            period=None,
            provider="tdx",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=False,
            limit=1,
            batch_rounds=None,
        )

    def test_web_api_market_data_sync_route_supports_tdx_ds_symbol(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={"provider": "tdx", "ingestion_job_id": 6, "status": "queued"},
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "tdx",
                    "symbol": "10#AUDUSD",
                    "interval": "1d",
                    "vipdoc_path": "G:/new_tdx64/vipdoc",
                    "limit": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "tdx")
        mock_sync.assert_called_once_with(
            symbol="10#AUDUSD",
            symbol_set=None,
            interval="1d",
            proxy=None,
            period=None,
            provider="tdx",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=False,
            limit=1,
            batch_rounds=None,
        )

    def test_web_api_market_data_sync_route_supports_tdx_all_interval(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={"provider": "tdx", "ingestion_job_id": 31, "status": "queued"},
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "tdx",
                    "interval": "all",
                    "vipdoc_path": "G:/new_tdx64/vipdoc",
                    "limit": 2,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "tdx")
        mock_sync.assert_called_once_with(
            symbol=None,
            symbol_set=None,
            interval="all",
            proxy=None,
            period=None,
            provider="tdx",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=False,
            limit=2,
            batch_rounds=None,
        )

    def test_web_api_market_data_sync_route_supports_tushare_provider(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={"provider": "tushare", "ingestion_job_id": 7, "status": "queued"},
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "tushare",
                    "symbol": "sh600000",
                    "interval": "1d",
                    "limit": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "tushare")
        mock_sync.assert_called_once_with(
            symbol="sh600000",
            symbol_set=None,
            interval="1d",
            proxy=None,
            period=None,
            provider="tushare",
            vipdoc_path=None,
            force=False,
            limit=1,
            batch_rounds=None,
        )

    def test_web_api_market_data_sync_route_supports_tdx_qfq_provider(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={"provider": "tdx_qfq", "ingestion_job_id": 12, "status": "queued"},
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "tdx_qfq",
                    "symbol": "sh600000",
                    "interval": "1d",
                    "limit": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "tdx_qfq")
        mock_sync.assert_called_once_with(
            symbol="sh600000",
            symbol_set=None,
            interval="1d",
            proxy=None,
            period=None,
            provider="tdx_qfq",
            vipdoc_path=None,
            force=False,
            limit=1,
            batch_rounds=None,
        )

    def test_web_api_market_data_sync_route_supports_tdx_pipeline_provider(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={
                "provider": "tdx_pipeline",
                "ingestion_job_id": 15,
                "status": "queued",
            },
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "tdx_pipeline",
                    "symbol": "sh600000",
                    "interval": "all",
                    "vipdoc_path": "G:/new_tdx64/vipdoc",
                    "force": True,
                    "limit": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "tdx_pipeline")
        mock_sync.assert_called_once_with(
            symbol="sh600000",
            symbol_set=None,
            interval="all",
            proxy=None,
            period=None,
            provider="tdx_pipeline",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=True,
            limit=1,
            batch_rounds=None,
        )

    def test_web_api_market_data_sync_route_supports_yahoo_pipeline_provider(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={
                "provider": "yahoo_pipeline",
                "ingestion_job_id": 16,
                "status": "queued",
            },
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "yahoo_pipeline",
                    "symbol_set": "yahoo_global_active_100",
                    "interval": "all",
                    "limit": 100,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "yahoo_pipeline")
        mock_sync.assert_called_once_with(
            symbol=None,
            symbol_set="yahoo_global_active_100",
            interval="all",
            proxy=None,
            period=None,
            provider="yahoo_pipeline",
            vipdoc_path=None,
            force=False,
            limit=100,
            batch_rounds=None,
        )

    def test_web_api_market_data_sync_route_supports_tdx_batch_rounds(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={"provider": "tdx", "ingestion_job_id": 26, "status": "queued"},
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "tdx",
                    "interval": "all",
                    "limit": 20,
                    "batch_rounds": 4,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "tdx")
        mock_sync.assert_called_once_with(
            symbol=None,
            symbol_set=None,
            interval="all",
            proxy=None,
            period=None,
            provider="tdx",
            vipdoc_path=None,
            force=False,
            limit=20,
            batch_rounds=4,
        )

    def test_web_api_market_data_retry_and_cancel_routes(self) -> None:
        app = create_app()
        client = TestClient(app)

        with (
            patch(
                "strategy_studio.web.app.retry_market_data_ingestion_job",
                return_value={"job_id": 31, "status": "queued", "changed": True},
            ) as mock_retry,
            patch(
                "strategy_studio.web.app.cancel_market_data_ingestion_job",
                return_value={"job_id": 32, "status": "cancel_requested", "changed": True},
            ) as mock_cancel,
        ):
            retry_response = client.post("/api/market-data/ingestion-jobs/31/retry")
            cancel_response = client.post("/api/market-data/ingestion-jobs/32/cancel")

        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(cancel_response.status_code, 200)
        self.assertEqual(retry_response.json()["status"], "queued")
        self.assertEqual(cancel_response.json()["status"], "cancel_requested")
        mock_retry.assert_called_once_with(31)
        mock_cancel.assert_called_once_with(32)

    def test_web_api_market_data_cancel_route_returns_404(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.cancel_market_data_ingestion_job",
            return_value={"job_id": 99, "status": "not_found", "changed": False},
        ) as mock_cancel:
            response = client.post("/api/market-data/ingestion-jobs/99/cancel")

        self.assertEqual(response.status_code, 404)
        mock_cancel.assert_called_once_with(99)

    def test_execute_next_market_data_job_reuses_sync_pipeline_for_queued_api_job(self) -> None:
        queued_job = SimpleNamespace(
            id=51,
            target_scope_json={
                "provider": "tdx",
                "symbol": "sh600000",
                "symbol_set": "",
                "interval": "1d",
                "proxy": "",
                "period": "",
                "vipdoc_path": "G:/new_tdx64/vipdoc",
            },
            options_json={"force": True, "limit": 2, "batch_rounds": 1},
            summary_json={},
            status="queued",
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            error_message="",
            completed_at=None,
        )
        first_session = SimpleNamespace(commit=lambda: None)
        second_session = SimpleNamespace(commit=lambda: None, get=lambda model, job_id: queued_job if job_id == 51 else None)

        class _SessionContext:
            def __init__(self, session: SimpleNamespace) -> None:
                self._session = session

            def __enter__(self) -> SimpleNamespace:
                return self._session

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        with patch("strategy_studio.services.sync.open_session", side_effect=[_SessionContext(first_session), _SessionContext(second_session)]), patch(
            "strategy_studio.services.sync.claim_next_queued_ingestion_job",
            return_value=queued_job,
        ), patch(
            "strategy_studio.services.sync.sync_market_data",
            return_value={
                "provider": "tdx",
                "ingestion_job_id": 91,
                "ingestion_job_ids": [91],
                "symbols_count": 2,
                "bars_inserted": 200,
                "bars_updated": 10,
                "status": "succeeded",
            },
        ) as mock_sync:
            result = sync_service.execute_next_market_data_job(worker_name="worker-1")

        self.assertEqual(result, 51)
        mock_sync.assert_called_once_with(
            symbol="sh600000",
            symbol_set=None,
            interval="1d",
            proxy=None,
            period=None,
            provider="tdx",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=True,
            limit=2,
            batch_rounds=1,
            requested_via="worker_child",
        )
        self.assertEqual(queued_job.status, "succeeded")
        self.assertEqual(queued_job.rows_inserted, 200)
        self.assertEqual(queued_job.rows_updated, 10)
        self.assertEqual(queued_job.summary_json["child_ingestion_job_ids"], [91])
        self.assertEqual(queued_job.summary_json["worker_name"], "worker-1")

    def test_cancel_market_data_ingestion_job_marks_queued_job_cancelled(self) -> None:
        queued_job = SimpleNamespace(
            id=41,
            requested_via="api",
            status="queued",
            completed_at=None,
            error_message="",
            summary_json={},
        )
        session = SimpleNamespace(get=lambda model, job_id: queued_job if job_id == 41 else None, commit=lambda: None)

        class _SessionContext:
            def __enter__(self) -> SimpleNamespace:
                return session

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        with patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()):
            result = sync_service.cancel_market_data_ingestion_job(41)

        self.assertEqual(result["status"], "cancelled")
        self.assertTrue(result["changed"])
        self.assertEqual(queued_job.status, "cancelled")
        self.assertEqual(queued_job.summary_json["worker_stage"], "cancelled")

    def test_retry_market_data_ingestion_job_requeues_failed_api_job(self) -> None:
        failed_job = SimpleNamespace(
            id=52,
            requested_via="api",
            status="failed",
            started_at=datetime(2026, 5, 29, 10, 0, 0),
            completed_at=datetime(2026, 5, 29, 10, 5, 0),
            targets_completed=1,
            rows_inserted=10,
            rows_updated=2,
            error_count=1,
            error_message="boom",
            summary_json={},
        )
        session = SimpleNamespace(get=lambda model, job_id: failed_job if job_id == 52 else None, commit=lambda: None)

        class _SessionContext:
            def __enter__(self) -> SimpleNamespace:
                return session

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        with patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()):
            result = sync_service.retry_market_data_ingestion_job(52)

        self.assertEqual(result["status"], "queued")
        self.assertTrue(result["changed"])
        self.assertEqual(failed_job.status, "queued")
        self.assertEqual(failed_job.targets_completed, 0)
        self.assertEqual(failed_job.rows_inserted, 0)
        self.assertEqual(failed_job.error_count, 0)
        self.assertEqual(failed_job.summary_json["retry_count"], 1)

    def test_web_api_platform_database_check_route(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.fetch_database_diagnostics",
            return_value={
                "status": "ok",
                "configured_database": "etf_strategy",
                "database_exists": True,
                "alembic_revision": "20260529_0006",
                "alembic_head": "20260529_0006",
                "migration_state": "head",
            },
        ) as mock_probe:
            response = client.get("/api/platform/database-check")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["configured_database"], "etf_strategy")
        self.assertEqual(response.json()["migration_state"], "head")
        mock_probe.assert_called_once()

    def test_web_api_platform_control_routes(self) -> None:
        app = create_app()
        client = TestClient(app)
        status_payload = {
            "api": {"status": "ok", "host": "127.0.0.1", "port": 8000, "base_url": "http://127.0.0.1:8000"},
            "frontend": {"status": "ok", "host": "127.0.0.1", "port": 3000, "base_url": "http://127.0.0.1:3000"},
            "database": {"status": "ok", "url": "postgresql+psycopg://postgres:***@localhost:5432/etf_strategy"},
            "market_data_runtime": {
                "yahoo": {
                    "status": "ok",
                    "proxy_configured": False,
                    "proxy_source": "none",
                    "default_symbol_set": "yahoo_global_active_100",
                    "workflow_intervals": ["1d", "15m", "1m"],
                },
                "tdx": {
                    "status": "ok",
                    "config_path": "F:/trade/tdx/config.local.yaml",
                    "config_exists": True,
                    "vipdoc_path": "G:/new_tdx64/vipdoc",
                    "vipdoc_exists": True,
                    "path_source": "config_file",
                    "market_roots": ["sh", "sz", "bj"],
                    "market_inventory": {
                        "total_files": 9338,
                        "by_interval": {"1d": 3200, "1m": 3069, "5m": 3069},
                        "by_market": {"sh": {"1d": 1600, "1m": 1534, "5m": 1534, "total_files": 4668}},
                    },
                    "supports_intervals": ["1d", "1m", "5m", "all"],
                    "error_message": "",
                },
                "tushare": {
                    "status": "ok",
                    "config_path": "F:/trade/tdx/config.local.yaml",
                    "config_exists": True,
                    "token_present": True,
                    "token_source": "config_file",
                    "rate_limit_per_minute": 450,
                    "timeout_seconds": 15.0,
                    "retries": 3,
                    "error_message": "",
                },
            },
            "heartbeats": [],
            "queue": {"queued": 0, "running": 0, "succeeded": 1, "failed": 0},
            "process_control_enabled": False,
            "sync_schedule": [],
        }

        with (
            patch("strategy_studio.web.app.fetch_platform_status", return_value=status_payload) as mock_status,
            patch("strategy_studio.web.app.fetch_platform_processes", return_value=[{"pid": 1, "service_name": "api"}]) as mock_processes,
            patch("strategy_studio.web.app.fetch_platform_logs", return_value={"service": "api", "lines": ["api started"]}) as mock_logs,
        ):
            status_response = client.get("/api/platform/status")
            processes_response = client.get("/api/platform/processes")
            logs_response = client.get("/api/platform/logs?service=api&limit=10")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(processes_response.status_code, 200)
        self.assertEqual(logs_response.status_code, 200)
        self.assertEqual(status_response.json()["api"]["status"], "ok")
        self.assertEqual(status_response.json()["market_data_runtime"]["tdx"]["vipdoc_path"], "G:/new_tdx64/vipdoc")
        self.assertEqual(processes_response.json()[0]["service_name"], "api")
        self.assertEqual(logs_response.json()["lines"], ["api started"])
        mock_status.assert_called_once()
        mock_processes.assert_called_once()
        mock_logs.assert_called_once_with(service="api", limit=10)

    def test_fetch_platform_status_includes_market_data_runtime(self) -> None:
        fake_settings = SimpleNamespace(api_host="127.0.0.1", api_port=8000, frontend_host="127.0.0.1", frontend_port=3000)
        runtime_payload = {
            "yahoo": {
                "status": "ok",
                "proxy_configured": False,
                "proxy_source": "none",
                "default_symbol_set": "yahoo_global_active_100",
                "workflow_intervals": ["1d", "15m", "1m"],
            },
            "tdx": {
                "status": "ok",
                "config_path": "F:/trade/tdx/config.local.yaml",
                "config_exists": True,
                "vipdoc_path": "G:/new_tdx64/vipdoc",
                "vipdoc_exists": True,
                "path_source": "config_file",
                "market_roots": ["sh", "sz", "bj"],
                "market_inventory": {
                    "total_files": 9338,
                    "by_interval": {"1d": 3200, "1m": 3069, "5m": 3069},
                    "by_market": {"sh": {"1d": 1600, "1m": 1534, "5m": 1534, "total_files": 4668}},
                },
                "supports_intervals": ["1d", "1m", "5m", "all"],
                "error_message": "",
            },
            "tushare": {
                "status": "ok",
                "config_path": "F:/trade/tdx/config.local.yaml",
                "config_exists": True,
                "token_present": True,
                "token_source": "config_file",
                "rate_limit_per_minute": 450,
                "timeout_seconds": 15.0,
                "retries": 3,
                "error_message": "",
            },
        }

        with (
            patch("strategy_studio.services.platform.load_platform_settings", return_value=fake_settings),
            patch("strategy_studio.services.platform._tcp_available", side_effect=[True, False]),
            patch("strategy_studio.services.platform._database_status", return_value={"status": "ok", "url": "postgresql+psycopg://postgres:***@localhost:5432/etf_strategy"}),
            patch("strategy_studio.services.platform._market_data_runtime_status", return_value=runtime_payload),
            patch("strategy_studio.services.platform._heartbeat_payload", return_value=[]),
            patch("strategy_studio.services.platform._queue_stats", return_value={"queued": 0, "running": 0, "failed": 0}),
        ):
            payload = platform_service.fetch_platform_status()

        self.assertEqual(payload["api"]["status"], "ok")
        self.assertEqual(payload["frontend"]["status"], "down")
        self.assertEqual(payload["market_data_runtime"]["tdx"]["vipdoc_path"], "G:/new_tdx64/vipdoc")
        self.assertEqual(payload["market_data_runtime"]["tdx"]["market_inventory"]["total_files"], 9338)
        self.assertTrue(payload["market_data_runtime"]["tushare"]["token_present"])

    def test_build_tdx_runtime_payload_includes_market_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vipdoc = Path(temp_dir) / "vipdoc"
            (vipdoc / "sh" / "lday").mkdir(parents=True)
            (vipdoc / "sh" / "minline").mkdir(parents=True)
            (vipdoc / "sh" / "fzline").mkdir(parents=True)
            (vipdoc / "ds" / "lday").mkdir(parents=True)
            (vipdoc / "ds" / "minline").mkdir(parents=True)
            (vipdoc / "sh" / "lday" / "sh600000.day").write_bytes(b"\x00" * 32)
            (vipdoc / "sh" / "minline" / "sh600000.lc1").write_bytes(b"\x00" * 32)
            (vipdoc / "sh" / "fzline" / "sh600000.lc5").write_bytes(b"\x00" * 32)
            (vipdoc / "ds" / "lday" / "10#AUDUSD.day").write_bytes(b"\x00" * 32)
            (vipdoc / "ds" / "minline" / "10#AUDUSD.lc1").write_bytes(b"\x00" * 32)

            fake_settings = SimpleNamespace(tdx_config_path="F:/trade/tdx/config.local.yaml")
            with (
                patch("strategy_studio.services.platform.load_platform_settings", return_value=fake_settings),
                patch.dict("os.environ", {"STRATEGY_STUDIO_TDX_VIPDOC": str(vipdoc)}, clear=False),
            ):
                payload = platform_service._build_tdx_runtime_payload()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["path_source"], "env")
        self.assertEqual(payload["market_roots"], ["ds", "sh"])
        self.assertEqual(payload["market_inventory"]["total_files"], 5)
        self.assertEqual(payload["market_inventory"]["by_interval"], {"1d": 2, "1m": 2, "5m": 1})
        self.assertEqual(payload["market_inventory"]["by_market"]["sh"]["total_files"], 3)
        self.assertEqual(payload["market_inventory"]["by_market"]["ds"]["1d"], 1)

    def test_build_yahoo_runtime_payload_prefers_env_proxy(self) -> None:
        with (
            patch.dict("os.environ", {"STRATEGY_STUDIO_PROXY": "http://127.0.0.1:7897"}, clear=False),
            patch(
                "strategy_studio.services.platform._detect_windows_system_proxy",
                return_value={"proxy_candidate": "http://127.0.0.1:8888", "proxy_enabled": True, "proxy_source": "windows_internet_settings"},
            ),
        ):
            payload = platform_service._build_yahoo_runtime_payload()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["proxy_configured"])
        self.assertEqual(payload["proxy_source"], "env")
        self.assertEqual(payload["system_proxy_candidate"], "http://127.0.0.1:8888")
        self.assertEqual(payload["warning_message"], "")

    def test_build_yahoo_runtime_payload_reports_system_proxy_candidate(self) -> None:
        with (
            patch.dict("os.environ", {"STRATEGY_STUDIO_PROXY": ""}, clear=False),
            patch(
                "strategy_studio.services.platform._detect_windows_system_proxy",
                return_value={"proxy_candidate": "http://127.0.0.1:7897", "proxy_enabled": False, "proxy_source": "windows_internet_settings"},
            ),
        ):
            payload = platform_service._build_yahoo_runtime_payload()

        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["proxy_configured"])
        self.assertEqual(payload["proxy_source"], "none")
        self.assertEqual(payload["system_proxy_candidate"], "http://127.0.0.1:7897")
        self.assertFalse(payload["system_proxy_enabled"])
        self.assertEqual(payload["system_proxy_source"], "windows_internet_settings")
        self.assertIn("--proxy", payload["warning_message"])

    def test_heartbeat_missing_table_does_not_break_runtime_loop(self) -> None:
        missing_table_error = Exception("psycopg.errors.UndefinedTable: relation platform_heartbeats does not exist")

        with patch("strategy_studio.services.platform.open_session", side_effect=missing_table_error):
            self.assertFalse(record_platform_heartbeat("worker"))

        with patch("strategy_studio.services.platform.open_session", side_effect=RuntimeError("database is offline")):
            with self.assertRaisesRegex(RuntimeError, "database is offline"):
                record_platform_heartbeat("worker")

    def test_web_api_backtest_cancel_and_bulk_routes(self) -> None:
        app = create_app()
        client = TestClient(app)

        with (
            patch("strategy_studio.web.app.cancel_backtest", return_value={"job_id": 7, "status": "cancel_requested", "changed": True}) as mock_cancel,
            patch("strategy_studio.web.app.bulk_cancel_backtests", return_value={"results": []}) as mock_bulk_cancel,
            patch("strategy_studio.web.app.bulk_retry_backtests", return_value={"results": []}) as mock_bulk_retry,
        ):
            cancel_response = client.post("/api/backtests/7/cancel")
            bulk_cancel_response = client.post("/api/backtests/bulk-cancel", json={"job_ids": [1, 2]})
            bulk_retry_response = client.post("/api/backtests/bulk-retry", json={"job_ids": [3]})

        self.assertEqual(cancel_response.status_code, 200)
        self.assertEqual(bulk_cancel_response.status_code, 200)
        self.assertEqual(bulk_retry_response.status_code, 200)
        self.assertEqual(cancel_response.json()["status"], "cancel_requested")
        mock_cancel.assert_called_once_with(7)
        mock_bulk_cancel.assert_called_once_with([1, 2])
        mock_bulk_retry.assert_called_once_with([3])

    def test_web_api_templates_routes(self) -> None:
        app = create_app()
        client = TestClient(app)
        template_payload = {
            "id": 1,
            "template_key": "grid_15m_realistic_default",
            "template_name": "网格-15m 实盘口径默认模板",
            "strategy_kind": "grid",
            "interval": "15m",
            "execution_profile": "realistic",
            "validation_start": "",
            "lookback_days": None,
            "validation_ratio": 0.25,
            "jobs": 1,
            "execution_overrides_json": {},
            "parameter_space_json": {"spacings": [0.01], "grid_counts": [4], "take_profits": [0.01]},
            "description": "",
            "is_active": True,
            "is_default": True,
            "created_at": "2026-05-25 20:00:00",
            "updated_at": "2026-05-25 20:00:00",
        }

        with (
            patch("strategy_studio.web.app.list_strategy_templates", return_value=[template_payload]) as mock_list,
            patch("strategy_studio.web.app.create_strategy_template_entry", return_value=template_payload) as mock_create,
            patch("strategy_studio.web.app.update_strategy_template_entry", return_value={**template_payload, "template_name": "已更新模板"}) as mock_update,
        ):
            list_response = client.get("/api/templates?active_only=true")
            create_response = client.post(
                "/api/templates",
                json={
                    "template_key": "grid_custom",
                    "template_name": "自定义网格模板",
                    "strategy_kind": "grid",
                    "interval": "15m",
                    "parameter_space_json": {"spacings": [0.01], "grid_counts": [4], "take_profits": [0.01]},
                },
            )
            update_response = client.patch("/api/templates/1", json={"template_name": "已更新模板"})

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(list_response.json()[0]["template_key"], "grid_15m_realistic_default")
        self.assertEqual(create_response.json()["id"], 1)
        self.assertEqual(update_response.json()["template_name"], "已更新模板")
        mock_list.assert_called_once()
        mock_create.assert_called_once()
        mock_update.assert_called_once()

    def test_handle_api_reports_missing_uvicorn_with_actionable_message(self) -> None:
        args = SimpleNamespace(host="127.0.0.1", port=8000)

        def fake_import(module_name: str):
            if module_name == "uvicorn":
                raise ModuleNotFoundError("No module named 'uvicorn'", name="uvicorn")
            if module_name == "strategy_studio.db.settings":
                return SimpleNamespace(load_platform_settings=lambda: SimpleNamespace(api_host="127.0.0.1", api_port=8000))
            if module_name == "strategy_studio.web.app":
                return SimpleNamespace(create_app=lambda: object())
            raise AssertionError(f"unexpected import: {module_name}")

        with patch("strategy_studio.platform_cli.importlib.import_module", side_effect=fake_import):
            with self.assertRaisesRegex(RuntimeError, "python -m pip install -r requirements.txt"):
                handle_api(args)

    def test_handle_api_reports_existing_api_port_conflict_cleanly(self) -> None:
        args = SimpleNamespace(host="127.0.0.1", port=8000)

        def fake_import(module_name: str, command_name: str):
            if module_name == "uvicorn":
                return SimpleNamespace(run=lambda *args, **kwargs: self.fail("端口已占用时不应继续启动 uvicorn"))
            if module_name == "strategy_studio.db.settings":
                return SimpleNamespace(load_platform_settings=lambda: SimpleNamespace(api_host="127.0.0.1", api_port=8000))
            if module_name == "strategy_studio.web.app":
                return SimpleNamespace(create_app=lambda: object())
            raise AssertionError(f"unexpected import: {module_name} ({command_name})")

        with (
            patch("strategy_studio.platform_cli._import_platform_module", side_effect=fake_import),
            patch("strategy_studio.platform_cli._is_tcp_port_in_use", return_value=True),
            patch("strategy_studio.platform_cli._probe_existing_platform_api", return_value=True),
            patch("strategy_studio.platform_cli._describe_windows_listener", return_value="PID=29876 进程名=python.exe"),
        ):
            with self.assertRaisesRegex(RuntimeError, "已经有本项目 API 在运行"):
                handle_api(args)

    def test_handle_api_replaces_existing_project_api_when_requested(self) -> None:
        args = SimpleNamespace(host="127.0.0.1", port=8000, replace_existing=True)
        run_calls = []

        def fake_import(module_name: str, command_name: str):
            if module_name == "uvicorn":
                return SimpleNamespace(run=lambda *args, **kwargs: run_calls.append(kwargs))
            if module_name == "strategy_studio.db.settings":
                return SimpleNamespace(load_platform_settings=lambda: SimpleNamespace(api_host="127.0.0.1", api_port=8000))
            if module_name == "strategy_studio.web.app":
                return SimpleNamespace(create_app=lambda: object())
            raise AssertionError(f"unexpected import: {module_name} ({command_name})")

        with (
            patch("strategy_studio.platform_cli._import_platform_module", side_effect=fake_import),
            patch("strategy_studio.platform_cli._is_tcp_port_in_use", return_value=True),
            patch("strategy_studio.platform_cli._replace_existing_platform_api", return_value=True),
            patch("builtins.print"),
        ):
            handle_api(args)

        self.assertEqual(len(run_calls), 1)
        self.assertEqual(run_calls[0]["host"], "127.0.0.1")
        self.assertEqual(run_calls[0]["port"], 8000)

    def test_handle_check_db_returns_failure_when_database_not_ready(self) -> None:
        args = SimpleNamespace(json=False)

        def fake_import(module_name: str, command_name: str):
            self.assertEqual(module_name, "strategy_studio.services.platform")
            self.assertEqual(command_name, "check-db")
            return SimpleNamespace(
                fetch_database_diagnostics=lambda: {
                    "status": "failed",
                    "configured_database": "etf_strategy",
                    "database_exists": False,
                    "admin_database": "postgres",
                    "alembic_head": "20260529_0006",
                    "error": "database missing",
                }
            )

        with (
            patch("strategy_studio.platform_cli._import_platform_module", side_effect=fake_import),
            patch("builtins.print") as mock_print,
        ):
            exit_code = handle_check_db(args)

        self.assertEqual(exit_code, 1)
        rendered = "\n".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        self.assertIn("数据库检查状态", rendered)
        self.assertIn("database missing", rendered)

    def test_handle_sync_now_returns_failure_for_failed_provider_run(self) -> None:
        args = SimpleNamespace(
            symbol=None,
            symbol_set="yahoo_global_active_100",
            interval="1d",
            proxy=None,
            period=None,
            provider="yahoo",
            vipdoc=None,
            force=False,
            limit=1,
        )

        def fake_import(module_name: str, command_name: str):
            self.assertEqual(module_name, "strategy_studio.services.sync")
            self.assertEqual(command_name, "sync-now")
            return SimpleNamespace(
                sync_market_data=lambda **_: {
                    "provider": "yahoo",
                    "symbols_count": 1,
                    "bars_inserted": 0,
                    "bars_updated": 0,
                    "ingestion_job_id": 9,
                    "symbol_set": "yahoo_global_active_100",
                    "status": "failed",
                    "error_message": "需要代理",
                }
            )

        with (
            patch("strategy_studio.platform_cli._import_platform_module", side_effect=fake_import),
            patch("builtins.print") as mock_print,
        ):
            exit_code = handle_sync_now(args)

        self.assertEqual(exit_code, 1)
        rendered = "\n".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        self.assertIn("status=failed", rendered)
        self.assertIn("symbol_set=yahoo_global_active_100", rendered)

    def test_sync_market_data_writes_unified_market_data_tables(self) -> None:
        session = SimpleNamespace()
        session.commit = lambda: None
        session.rollback = lambda: None
        registry: dict[int, object] = {}
        session.get = lambda _model, identity: registry.get(identity)

        class _SessionContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return False

        run = SimpleNamespace(id=11, symbols_count=0, completed_at=None, bars_inserted=0, bars_updated=0, status="running")
        run_item = SimpleNamespace(id=12, status="running", bars_inserted=0, bars_updated=0, error_message="")
        ingestion_job = SimpleNamespace(
            id=21,
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            summary_json={},
            completed_at=None,
            status="running",
            error_message="",
        )
        ingestion_item = SimpleNamespace(
            id=22,
            status="running",
            stage="download",
            instrument_id=None,
            series_id=None,
            rows_inserted=0,
            rows_updated=0,
            details_json={},
            error_message="",
        )
        registry.update({11: run, 12: run_item, 21: ingestion_job, 22: ingestion_item})

        bars = pd.DataFrame(
            {
                "Date": ["2026-05-20", "2026-05-21"],
                "Open": [10.0, 10.2],
                "High": [10.3, 10.4],
                "Low": [9.9, 10.1],
                "Close": [10.1, 10.3],
                "Volume": [100, 120],
            }
        )
        instrument = SimpleNamespace(id=101, exchange="HK", asset_type="equity", timezone="UTC")
        alias = SimpleNamespace(id=102)
        series = SimpleNamespace(id=103, first_bar_time=None, last_bar_time=None, last_ingested_at=None)
        provider = SimpleNamespace(id=104, provider_key="yahoo")

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", return_value=provider) as mock_provider,
            patch("strategy_studio.services.sync.create_sync_run", return_value=run),
            patch("strategy_studio.services.sync.create_sync_run_item", return_value=run_item),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", return_value=ingestion_item),
            patch("strategy_studio.services.sync._resolve_yahoo_targets", return_value=[SimpleNamespace(symbol="1810.HK", name="XIAOMI - W")]),
            patch("strategy_studio.services.sync.download_price_bars", return_value=bars),
            patch("strategy_studio.services.sync.get_or_create_instrument", return_value=instrument),
            patch("strategy_studio.services.sync.get_or_create_instrument_alias", return_value=alias) as mock_alias,
            patch("strategy_studio.services.sync.get_or_create_market_data_series", return_value=series) as mock_series,
            patch("strategy_studio.services.sync.upsert_price_frame", return_value=(2, 0)),
            patch("strategy_studio.services.sync.upsert_market_data_frame", return_value=(2, 0)) as mock_upsert_series,
        ):
            result = sync_market_data(symbol="1810.HK", interval="1d", proxy="http://127.0.0.1:7897")

        self.assertEqual(result["run_id"], 11)
        self.assertEqual(result["ingestion_job_id"], 21)
        self.assertEqual(result["series_bars_inserted"], 2)
        self.assertEqual(result["series_bars_updated"], 0)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(ingestion_job.status, "succeeded")
        self.assertEqual(ingestion_job.rows_inserted, 2)
        self.assertEqual(ingestion_job.targets_completed, 1)
        self.assertEqual(ingestion_item.instrument_id, 101)
        self.assertEqual(ingestion_item.series_id, 103)
        mock_provider.assert_called_once()
        mock_alias.assert_called_once()
        mock_series.assert_called_once()
        mock_upsert_series.assert_called_once()

    def test_sync_market_data_dispatches_yahoo_symbol_set(self) -> None:
        with patch(
            "strategy_studio.services.sync._sync_yahoo_market_data",
            return_value={"provider": "yahoo", "ingestion_job_id": 4, "symbols_count": 100, "bars_inserted": 8000, "bars_updated": 0, "status": "succeeded"},
        ) as mock_yahoo:
            result = sync_market_data(
                symbol=None,
                symbol_set="yahoo_global_active_100",
                interval="15m",
                proxy=None,
                provider="yahoo",
                period="60d",
                limit=100,
            )

        self.assertEqual(result["provider"], "yahoo")
        mock_yahoo.assert_called_once_with(
            symbol=None,
            symbol_set="yahoo_global_active_100",
            interval="15m",
            proxy=None,
            period="60d",
            limit=100,
            requested_via=None,
        )

    def test_sync_market_data_dispatches_tdx_provider(self) -> None:
        with patch(
            "strategy_studio.services.sync._sync_tdx_market_data",
            return_value={"provider": "tdx", "ingestion_job_id": 9, "symbols_count": 2, "bars_inserted": 30, "bars_updated": 0, "status": "succeeded"},
        ) as mock_tdx:
            result = sync_market_data(
                symbol="sh600000",
                interval="1d",
                proxy=None,
                provider="tdx",
                vipdoc_path="G:/new_tdx64/vipdoc",
                force=True,
                limit=5,
            )

        self.assertEqual(result["provider"], "tdx")
        mock_tdx.assert_called_once_with(
            symbol="sh600000",
            interval="1d",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=True,
            limit=5,
            requested_via=None,
        )

    def test_sync_market_data_dispatches_tdx_minute_provider(self) -> None:
        with patch(
            "strategy_studio.services.sync._sync_tdx_market_data",
            return_value={"provider": "tdx", "ingestion_job_id": 10, "symbols_count": 1, "bars_inserted": 480, "bars_updated": 0, "status": "succeeded"},
        ) as mock_tdx:
            result = sync_market_data(
                symbol="sh600000",
                interval="5m",
                proxy=None,
                provider="tdx",
                vipdoc_path="G:/new_tdx64/vipdoc",
                force=False,
                limit=1,
            )

        self.assertEqual(result["provider"], "tdx")
        mock_tdx.assert_called_once_with(
            symbol="sh600000",
            interval="5m",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=False,
            limit=1,
            requested_via=None,
        )

    def test_sync_market_data_dispatches_tdx_ds_symbol_provider(self) -> None:
        with patch(
            "strategy_studio.services.sync._sync_tdx_market_data",
            return_value={"provider": "tdx", "ingestion_job_id": 11, "symbols_count": 1, "bars_inserted": 1253, "bars_updated": 0, "status": "succeeded"},
        ) as mock_tdx:
            result = sync_market_data(
                symbol="10#audusd",
                interval="1d",
                proxy=None,
                provider="tdx",
                vipdoc_path="G:/new_tdx64/vipdoc",
                force=True,
                limit=1,
            )

        self.assertEqual(result["provider"], "tdx")
        mock_tdx.assert_called_once_with(
            symbol="10#audusd",
            interval="1d",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=True,
            limit=1,
            requested_via=None,
        )

    def test_sync_market_data_dispatches_tdx_all_provider(self) -> None:
        with patch(
            "strategy_studio.services.sync._sync_tdx_market_data",
            return_value={"provider": "tdx", "ingestion_job_ids": [41, 42, 43], "symbols_count": 3, "bars_inserted": 960, "bars_updated": 15, "status": "succeeded"},
        ) as mock_tdx:
            result = sync_market_data(
                symbol=None,
                interval="all",
                proxy=None,
                provider="tdx",
                vipdoc_path="G:/new_tdx64/vipdoc",
                force=True,
                limit=2,
            )

        self.assertEqual(result["provider"], "tdx")
        mock_tdx.assert_called_once_with(
            symbol=None,
            interval="all",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=True,
            limit=2,
            requested_via=None,
        )

    def test_sync_market_data_dispatches_tdx_batch_rounds_provider(self) -> None:
        with patch(
            "strategy_studio.services.sync._sync_tdx_market_data_in_rounds",
            return_value={"provider": "tdx", "ingestion_job_ids": [51, 52], "symbols_count": 6, "bars_inserted": 3200, "bars_updated": 0, "status": "succeeded"},
        ) as mock_tdx:
            result = sync_market_data(
                symbol=None,
                interval="all",
                proxy=None,
                provider="tdx",
                vipdoc_path="G:/new_tdx64/vipdoc",
                force=False,
                limit=2,
                batch_rounds=3,
            )

        self.assertEqual(result["provider"], "tdx")
        mock_tdx.assert_called_once_with(
            symbol=None,
            interval="all",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=False,
            limit=2,
            batch_rounds=3,
            requested_via=None,
        )

    def test_sync_tdx_market_data_in_rounds_stops_after_pending_files_exhausted(self) -> None:
        with patch(
            "strategy_studio.services.sync._sync_tdx_market_data",
            side_effect=[
                {
                    "provider": "tdx",
                    "interval": "all",
                    "symbols_count": 6,
                    "bars_inserted": 120,
                    "bars_updated": 0,
                    "series_bars_inserted": 120,
                    "series_bars_updated": 0,
                    "files_imported": 6,
                    "files_skipped": 0,
                    "files_failed": 0,
                    "ingestion_job_ids": [101, 102, 103],
                    "error_message": "",
                    "status": "succeeded",
                    "vipdoc_path": "G:/new_tdx64/vipdoc",
                },
                {
                    "provider": "tdx",
                    "interval": "all",
                    "symbols_count": 0,
                    "bars_inserted": 0,
                    "bars_updated": 0,
                    "series_bars_inserted": 0,
                    "series_bars_updated": 0,
                    "files_imported": 0,
                    "files_skipped": 0,
                    "files_failed": 0,
                    "ingestion_job_ids": [],
                    "error_message": "",
                    "status": "skipped",
                    "skip_reason": "no_pending_files",
                    "vipdoc_path": "G:/new_tdx64/vipdoc",
                },
            ],
        ) as mock_tdx:
            result = sync_service._sync_tdx_market_data_in_rounds(
                symbol=None,
                interval="all",
                vipdoc_path="G:/new_tdx64/vipdoc",
                force=False,
                limit=2,
                batch_rounds=5,
            )

        self.assertEqual(result["provider"], "tdx")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["batch_rounds_requested"], 5)
        self.assertEqual(result["batch_rounds_completed"], 2)
        self.assertEqual(result["bars_inserted"], 120)
        self.assertEqual(result["ingestion_job_ids"], [101, 102, 103])
        self.assertEqual([item["round_index"] for item in result["round_results"]], [1, 2])
        self.assertEqual(mock_tdx.call_count, 2)

    def test_tdx_all_interval_orchestrates_supported_intervals(self) -> None:
        observed_calls: list[tuple[str, bool]] = []

        def fake_single_interval(**kwargs):
            observed_calls.append((kwargs["interval"], kwargs["allow_empty"]))
            return {
                "provider": "tdx",
                "interval": kwargs["interval"],
                "symbols_count": 1,
                "bars_inserted": {"1d": 10, "1m": 20, "5m": 30}[kwargs["interval"]],
                "bars_updated": 0,
                "series_bars_inserted": {"1d": 10, "1m": 20, "5m": 30}[kwargs["interval"]],
                "series_bars_updated": 0,
                "files_imported": 1,
                "files_skipped": 0,
                "files_failed": 0,
                "ingestion_job_id": {"1d": 101, "1m": 102, "5m": 103}[kwargs["interval"]],
                "error_message": "",
                "status": "succeeded",
                "vipdoc_path": "G:/new_tdx64/vipdoc",
            }

        with patch("strategy_studio.services.sync._sync_tdx_single_interval_market_data", side_effect=fake_single_interval):
            result = sync_service._sync_tdx_market_data(
                symbol="sh600000",
                interval="all",
                vipdoc_path="G:/new_tdx64/vipdoc",
                force=True,
                limit=2,
            )

        self.assertEqual(observed_calls, [("1d", True), ("1m", True), ("5m", True)])
        self.assertEqual(result["provider"], "tdx")
        self.assertEqual(result["interval"], "all")
        self.assertEqual(result["bars_inserted"], 60)
        self.assertEqual(result["files_imported"], 3)
        self.assertEqual(result["ingestion_job_ids"], [101, 102, 103])
        self.assertEqual(result["status"], "succeeded")

    def test_select_tdx_source_files_for_batch_skips_unchanged_manifest_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vipdoc = Path(temp_dir) / "vipdoc"
            market_dir = vipdoc / "sh" / "lday"
            market_dir.mkdir(parents=True)
            first_file = market_dir / "sh600000.day"
            second_file = market_dir / "sh600001.day"
            third_file = market_dir / "sh600002.day"
            for source_file in (first_file, second_file, third_file):
                source_file.write_bytes(b"\x00" * 32)

            source_files = [first_file, second_file, third_file]
            manifest_index = {
                "sh/lday/sh600000.day": SimpleNamespace(status="success"),
                "sh/lday/sh600001.day": SimpleNamespace(status="success"),
            }

            with patch(
                "strategy_studio.services.sync.get_source_file_manifest_index",
                return_value=manifest_index,
            ):
                selected = sync_service._select_tdx_source_files_for_batch(
                    source_files,
                    provider=SimpleNamespace(id=1, provider_key="tdx"),
                    vipdoc=vipdoc,
                    interval="1d",
                    symbol=None,
                    force=False,
                    limit=1,
                    session=object(),
                )

        self.assertEqual([item.name for item in selected], ["sh600002.day"])

    def test_select_tdx_source_files_for_batch_keeps_changed_tracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vipdoc = Path(temp_dir) / "vipdoc"
            market_dir = vipdoc / "sh" / "lday"
            market_dir.mkdir(parents=True)
            first_file = market_dir / "sh600000.day"
            second_file = market_dir / "sh600001.day"
            for source_file in (first_file, second_file):
                source_file.write_bytes(b"\x00" * 32)

            source_files = [first_file, second_file]
            manifest_index = {
                "sh/lday/sh600000.day": SimpleNamespace(status="success"),
                "sh/lday/sh600001.day": SimpleNamespace(status="success"),
            }

            with (
                patch(
                    "strategy_studio.services.sync.get_source_file_manifest_index",
                    return_value=manifest_index,
                ),
                patch(
                    "strategy_studio.services.sync.build_tdx_file_signature",
                    side_effect=[
                        {"source_size": 32, "source_mtime": 1.0, "record_count": 1, "tail_hash": "a", "record_size": 32, "size_aligned": True},
                        {"source_size": 64, "source_mtime": 2.0, "record_count": 2, "tail_hash": "b", "record_size": 32, "size_aligned": True},
                    ],
                ),
                patch(
                    "strategy_studio.services.sync.manifest_is_unchanged",
                    side_effect=[True, False],
                ),
            ):
                selected = sync_service._select_tdx_source_files_for_batch(
                    source_files,
                    provider=SimpleNamespace(id=1, provider_key="tdx"),
                    vipdoc=vipdoc,
                    interval="1d",
                    symbol=None,
                    force=False,
                    limit=1,
                    session=object(),
                )

        self.assertEqual([item.name for item in selected], ["sh600001.day"])

    def test_sync_market_data_dispatches_tushare_provider(self) -> None:
        with patch(
            "strategy_studio.services.sync._sync_tushare_corporate_actions",
            return_value={"provider": "tushare", "ingestion_job_id": 14, "symbols_count": 1, "bars_inserted": 3, "bars_updated": 1, "status": "succeeded"},
        ) as mock_tushare:
            result = sync_market_data(
                symbol="sh600000",
                interval="1d",
                proxy=None,
                provider="tushare",
                limit=1,
                force=True,
            )

        self.assertEqual(result["provider"], "tushare")
        mock_tushare.assert_called_once_with(
            symbol="sh600000",
            limit=1,
            force=True,
            requested_via=None,
        )

    def test_sync_market_data_dispatches_tdx_qfq_provider(self) -> None:
        with patch(
            "strategy_studio.services.sync._rebuild_tdx_qfq_market_data",
            return_value={"provider": "tdx_qfq", "ingestion_job_id": 18, "symbols_count": 1, "bars_inserted": 100, "bars_updated": 0, "status": "succeeded"},
        ) as mock_qfq:
            result = sync_market_data(
                symbol="sh600000",
                interval="1d",
                proxy=None,
                provider="tdx_qfq",
                limit=2,
                force=True,
            )

        self.assertEqual(result["provider"], "tdx_qfq")
        mock_qfq.assert_called_once_with(
            symbol="sh600000",
            interval="1d",
            limit=2,
            force=True,
            requested_via=None,
        )

    def test_sync_market_data_dispatches_tdx_pipeline_provider(self) -> None:
        with patch(
            "strategy_studio.services.sync._run_tdx_pipeline_workflow",
            return_value={
                "provider": "tdx_pipeline",
                "ingestion_job_id": 19,
                "child_ingestion_job_ids": [41, 42, 43],
                "symbols_count": 1,
                "bars_inserted": 320,
                "bars_updated": 4,
                "status": "succeeded",
            },
        ) as mock_pipeline:
            result = sync_market_data(
                symbol="sh600000",
                interval="all",
                proxy=None,
                provider="tdx_pipeline",
                vipdoc_path="G:/new_tdx64/vipdoc",
                limit=2,
                force=True,
            )

        self.assertEqual(result["provider"], "tdx_pipeline")
        mock_pipeline.assert_called_once_with(
            symbol="sh600000",
            interval="all",
            vipdoc_path="G:/new_tdx64/vipdoc",
            force=True,
            limit=2,
            requested_via=None,
        )

    def test_sync_market_data_dispatches_yahoo_pipeline_provider(self) -> None:
        with patch(
            "strategy_studio.services.sync._run_yahoo_pipeline_workflow",
            return_value={
                "provider": "yahoo_pipeline",
                "ingestion_job_id": 20,
                "child_ingestion_job_ids": [51, 52, 53],
                "symbols_count": 100,
                "bars_inserted": 9000,
                "bars_updated": 0,
                "status": "succeeded",
            },
        ) as mock_pipeline:
            result = sync_market_data(
                symbol=None,
                interval="all",
                proxy="http://127.0.0.1:7897",
                provider="yahoo_pipeline",
                limit=100,
                symbol_set="yahoo_global_active_100",
            )

        self.assertEqual(result["provider"], "yahoo_pipeline")
        mock_pipeline.assert_called_once_with(
            symbol=None,
            symbol_set="yahoo_global_active_100",
            interval="all",
            proxy="http://127.0.0.1:7897",
            limit=100,
            requested_via=None,
        )

    def test_tdx_pipeline_workflow_aggregates_child_provider_results(self) -> None:
        session = SimpleNamespace()
        session.commit = lambda: None
        session.rollback = lambda: None
        registry: dict[int, object] = {}
        session.get = lambda _model, identity: registry.get(identity)

        class _SessionContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return False

        provider = SimpleNamespace(id=301, provider_key="tdx_pipeline")
        ingestion_job = SimpleNamespace(
            id=401,
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            summary_json={},
            completed_at=None,
            status="running",
            error_message="",
        )
        registry[401] = ingestion_job

        item_ids = [501, 502, 503]

        def fake_create_item(*_args, **_kwargs):
            current_id = item_ids.pop(0)
            item = SimpleNamespace(
                id=current_id,
                status="running",
                stage="download",
                rows_inserted=0,
                rows_updated=0,
                details_json={},
                error_message="",
            )
            registry[current_id] = item
            return item

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", return_value=provider),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", side_effect=fake_create_item),
            patch(
                "strategy_studio.services.sync._sync_tdx_market_data",
                return_value={
                    "provider": "tdx",
                    "interval": "all",
                    "symbols_count": 3,
                    "bars_inserted": 600,
                    "bars_updated": 10,
                    "ingestion_job_ids": [91, 92, 93],
                    "status": "succeeded",
                },
            ),
            patch(
                "strategy_studio.services.sync._sync_tushare_corporate_actions",
                return_value={
                    "provider": "tushare",
                    "interval": "corp_actions",
                    "symbols_count": 1,
                    "bars_inserted": 5,
                    "bars_updated": 0,
                    "ingestion_job_id": 94,
                    "status": "succeeded",
                },
            ),
            patch(
                "strategy_studio.services.sync._rebuild_tdx_qfq_market_data",
                return_value={
                    "provider": "tdx_qfq",
                    "interval": "1d",
                    "symbols_count": 1,
                    "bars_inserted": 200,
                    "bars_updated": 1,
                    "ingestion_job_id": 95,
                    "status": "succeeded",
                },
            ),
        ):
            result = sync_service._run_tdx_pipeline_workflow(
                symbol="sh600000",
                interval="all",
                vipdoc_path="G:/new_tdx64/vipdoc",
                force=True,
                limit=2,
            )

        self.assertEqual(result["provider"], "tdx_pipeline")
        self.assertEqual(result["ingestion_job_id"], 401)
        self.assertEqual(result["child_ingestion_job_ids"], [91, 92, 93, 94, 95])
        self.assertEqual(result["ingestion_job_ids"], [91, 92, 93, 94, 95])
        self.assertEqual(result["bars_inserted"], 805)
        self.assertEqual(result["bars_updated"], 11)
        self.assertEqual(result["symbols_count"], 1)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(ingestion_job.targets_total, 3)
        self.assertEqual(ingestion_job.targets_completed, 3)
        self.assertEqual(ingestion_job.rows_inserted, 805)
        self.assertEqual(ingestion_job.rows_updated, 11)
        self.assertEqual(ingestion_job.error_count, 0)
        self.assertEqual(ingestion_job.status, "succeeded")
        self.assertEqual(len(result["workflow_results"]), 3)

    def test_tdx_pipeline_batch_workflow_uses_tdx_daily_targets_for_tushare_and_qfq(self) -> None:
        session = SimpleNamespace()
        session.commit = lambda: None
        session.rollback = lambda: None
        registry: dict[int, object] = {}
        session.get = lambda _model, identity: registry.get(identity)

        class _SessionContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return False

        provider = SimpleNamespace(id=321, provider_key="tdx_pipeline")
        ingestion_job = SimpleNamespace(
            id=421,
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            summary_json={},
            completed_at=None,
            status="running",
            error_message="",
        )
        registry[421] = ingestion_job

        item_ids = [521, 522, 523]

        def fake_create_item(*_args, **_kwargs):
            current_id = item_ids.pop(0)
            item = SimpleNamespace(
                id=current_id,
                status="running",
                stage="download",
                rows_inserted=0,
                rows_updated=0,
                details_json={},
                error_message="",
            )
            registry[current_id] = item
            return item

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", return_value=provider),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", side_effect=fake_create_item),
            patch(
                "strategy_studio.services.sync._sync_tdx_market_data",
                return_value={
                    "provider": "tdx",
                    "interval": "all",
                    "symbols_count": 2,
                    "bars_inserted": 600,
                    "bars_updated": 10,
                    "ingestion_job_ids": [111, 112, 113],
                    "status": "succeeded",
                },
            ),
            patch(
                "strategy_studio.services.sync._resolve_tdx_pipeline_batch_symbols",
                return_value=["SH600000", "SZ000001"],
            ) as mock_pipeline_targets,
            patch(
                "strategy_studio.services.sync._sync_tushare_corporate_actions",
                return_value={
                    "provider": "tushare",
                    "interval": "corp_actions",
                    "symbols_count": 2,
                    "bars_inserted": 6,
                    "bars_updated": 0,
                    "ingestion_job_id": 114,
                    "status": "succeeded",
                },
            ) as mock_tushare,
            patch(
                "strategy_studio.services.sync._rebuild_tdx_qfq_market_data",
                return_value={
                    "provider": "tdx_qfq",
                    "interval": "1d",
                    "symbols_count": 2,
                    "bars_inserted": 200,
                    "bars_updated": 2,
                    "ingestion_job_id": 115,
                    "status": "succeeded",
                },
            ) as mock_qfq,
        ):
            result = sync_service._run_tdx_pipeline_workflow(
                symbol=None,
                interval="all",
                vipdoc_path="G:/new_tdx64/vipdoc",
                force=True,
                limit=2,
            )

        mock_pipeline_targets.assert_called_once_with(limit=2)
        mock_tushare.assert_called_once_with(
            symbol=None,
            limit=2,
            force=True,
            target_symbols=["SH600000", "SZ000001"],
            requested_via=None,
        )
        mock_qfq.assert_called_once_with(
            symbol=None,
            interval="1d",
            force=True,
            limit=2,
            target_symbols=["SH600000", "SZ000001"],
            requested_via=None,
        )
        self.assertEqual(result["provider"], "tdx_pipeline")
        self.assertEqual(result["symbols_count"], 2)
        self.assertEqual(result["child_ingestion_job_ids"], [111, 112, 113, 114, 115])

    def test_resolve_tdx_qfq_targets_filters_non_tushare_symbols_in_batch_mode(self) -> None:
        class _QueryResult:
            def __init__(self, rows: list[tuple[object, object, object]]) -> None:
                self._rows = rows

            def all(self) -> list[tuple[object, object, object]]:
                return list(self._rows)

        class _BatchSession:
            def execute(self, _statement: object) -> _QueryResult:
                return _QueryResult(
                    [
                        (
                            SimpleNamespace(id=701),
                            SimpleNamespace(id=801, symbol="10#AUDUSD"),
                            SimpleNamespace(source_symbol="10#AUDUSD"),
                        ),
                        (
                            SimpleNamespace(id=702),
                            SimpleNamespace(id=802, symbol="SH600000"),
                            SimpleNamespace(source_symbol="SH600000"),
                        ),
                        (
                            SimpleNamespace(id=703),
                            SimpleNamespace(id=803, symbol="BJ810011"),
                            SimpleNamespace(source_symbol="BJ810011"),
                        ),
                    ]
                )

        targets = sync_service._resolve_tdx_qfq_targets(
            _BatchSession(),
            raw_provider=SimpleNamespace(id=401),
            symbol=None,
            limit=None,
        )

        self.assertEqual([item["instrument"].symbol for item in targets], ["SH600000", "BJ810011"])

    def test_resolve_tdx_qfq_targets_rejects_ds_symbol_for_qfq(self) -> None:
        class _QueryResult:
            def __init__(self, rows: list[tuple[object, object, object]]) -> None:
                self._rows = rows

            def all(self) -> list[tuple[object, object, object]]:
                return list(self._rows)

        class _BatchSession:
            def execute(self, _statement: object) -> _QueryResult:
                return _QueryResult(
                    [
                        (
                            SimpleNamespace(id=701),
                            SimpleNamespace(id=801, symbol="10#AUDUSD"),
                            SimpleNamespace(source_symbol="10#AUDUSD"),
                        )
                    ]
                )

        with self.assertRaisesRegex(ValueError, "只支持可映射 Tushare ts_code 的 sh/sz/bj 原始 1d 标的"):
            sync_service._resolve_tdx_qfq_targets(
                _BatchSession(),
                raw_provider=SimpleNamespace(id=401),
                symbol="10#AUDUSD",
                limit=None,
            )

    def test_resolve_tdx_pipeline_batch_symbols_skips_ds_raw_series(self) -> None:
        class _QueryResult:
            def __init__(self, rows: list[tuple[object, object, object]]) -> None:
                self._rows = rows

            def all(self) -> list[tuple[object, object, object]]:
                return list(self._rows)

        class _SessionDouble:
            def execute(self, _statement: object) -> _QueryResult:
                return _QueryResult(
                    [
                        (
                            SimpleNamespace(id=701),
                            SimpleNamespace(id=801, symbol="10#AUDUSD"),
                            SimpleNamespace(source_symbol="10#AUDUSD"),
                        ),
                        (
                            SimpleNamespace(id=702),
                            SimpleNamespace(id=802, symbol="SH600000"),
                            SimpleNamespace(source_symbol="SH600000"),
                        ),
                    ]
                )

        class _SessionContext:
            def __enter__(self):
                return _SessionDouble()

            def __exit__(self, exc_type, exc, tb):
                return False

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", return_value=SimpleNamespace(id=401)),
        ):
            symbols = sync_service._resolve_tdx_pipeline_batch_symbols(limit=10)

        self.assertEqual(symbols, ["SH600000"])

    def test_yahoo_pipeline_workflow_aggregates_three_intervals(self) -> None:
        session = SimpleNamespace()
        session.commit = lambda: None
        session.rollback = lambda: None
        registry: dict[int, object] = {}
        session.get = lambda _model, identity: registry.get(identity)

        class _SessionContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return False

        provider = SimpleNamespace(id=341, provider_key="yahoo_pipeline")
        ingestion_job = SimpleNamespace(
            id=441,
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            summary_json={},
            completed_at=None,
            status="running",
            error_message="",
        )
        registry[441] = ingestion_job

        item_ids = [541, 542, 543]

        def fake_create_item(*_args, **_kwargs):
            current_id = item_ids.pop(0)
            item = SimpleNamespace(
                id=current_id,
                status="running",
                stage="download",
                rows_inserted=0,
                rows_updated=0,
                details_json={},
                error_message="",
            )
            registry[current_id] = item
            return item

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", return_value=provider),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", side_effect=fake_create_item),
            patch(
                "strategy_studio.services.sync._sync_yahoo_market_data",
                side_effect=[
                    {
                        "provider": "yahoo",
                        "interval": "1d",
                        "symbols_count": 100,
                        "bars_inserted": 1000,
                        "bars_updated": 0,
                        "series_bars_inserted": 1000,
                        "series_bars_updated": 0,
                        "ingestion_job_id": 81,
                        "status": "succeeded",
                    },
                    {
                        "provider": "yahoo",
                        "interval": "15m",
                        "symbols_count": 100,
                        "bars_inserted": 2000,
                        "bars_updated": 5,
                        "series_bars_inserted": 2000,
                        "series_bars_updated": 5,
                        "ingestion_job_id": 82,
                        "status": "succeeded",
                    },
                    {
                        "provider": "yahoo",
                        "interval": "1m",
                        "symbols_count": 100,
                        "bars_inserted": 3000,
                        "bars_updated": 7,
                        "series_bars_inserted": 3000,
                        "series_bars_updated": 7,
                        "ingestion_job_id": 83,
                        "status": "succeeded",
                    },
                ],
            ) as mock_yahoo,
        ):
            result = sync_service._run_yahoo_pipeline_workflow(
                symbol=None,
                symbol_set="yahoo_global_active_100",
                interval="all",
                proxy="http://127.0.0.1:7897",
                limit=100,
            )

        self.assertEqual(mock_yahoo.call_count, 3)
        mock_yahoo.assert_any_call(
            symbol=None,
            interval="1d",
            proxy="http://127.0.0.1:7897",
            period=None,
            limit=100,
            symbol_set="yahoo_global_active_100",
            requested_via=None,
        )
        mock_yahoo.assert_any_call(
            symbol=None,
            interval="15m",
            proxy="http://127.0.0.1:7897",
            period="60d",
            limit=100,
            symbol_set="yahoo_global_active_100",
            requested_via=None,
        )
        mock_yahoo.assert_any_call(
            symbol=None,
            interval="1m",
            proxy="http://127.0.0.1:7897",
            period="7d",
            limit=100,
            symbol_set="yahoo_global_active_100",
            requested_via=None,
        )
        self.assertEqual(result["provider"], "yahoo_pipeline")
        self.assertEqual(result["ingestion_job_id"], 441)
        self.assertEqual(result["child_ingestion_job_ids"], [81, 82, 83])
        self.assertEqual(result["bars_inserted"], 6000)
        self.assertEqual(result["bars_updated"], 12)
        self.assertEqual(result["symbols_count"], 100)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["symbol_set"], "yahoo_global_active_100")
        self.assertEqual(ingestion_job.targets_total, 3)
        self.assertEqual(ingestion_job.targets_completed, 3)
        self.assertEqual(ingestion_job.rows_inserted, 6000)
        self.assertEqual(ingestion_job.rows_updated, 12)
        self.assertEqual(ingestion_job.error_count, 0)
        self.assertEqual(ingestion_job.status, "succeeded")
        self.assertEqual(ingestion_job.summary_json["requested_symbol_set"], "yahoo_global_active_100")
        self.assertEqual(len(result["workflow_results"]), 3)

    def test_preload_tdx_qfq_input_frames_groups_raw_bars_and_actions(self) -> None:
        class _ExecuteResult:
            def __init__(self, rows: list[object]) -> None:
                self._rows = rows

            def all(self) -> list[object]:
                return list(self._rows)

        class _BatchSession:
            def __init__(self) -> None:
                self.calls = 0

            def execute(self, _statement: object) -> _ExecuteResult:
                self.calls += 1
                if self.calls == 1:
                    return _ExecuteResult(
                        [
                            SimpleNamespace(
                                series_id=10,
                                bar_time=datetime(2026, 5, 28, 0, 0),
                                open=10.0,
                                high=11.0,
                                low=9.0,
                                close=10.5,
                                volume=100,
                                turnover_amount=1000.0,
                            ),
                            SimpleNamespace(
                                series_id=11,
                                bar_time=datetime(2026, 5, 29, 0, 0),
                                open=20.0,
                                high=21.0,
                                low=19.0,
                                close=20.5,
                                volume=200,
                                turnover_amount=2000.0,
                            ),
                        ]
                    )
                return _ExecuteResult(
                    [
                        SimpleNamespace(
                            instrument_id=101,
                            ex_date="2026-05-29",
                            cash_dividend=0.5,
                            stock_bonus_ratio=0.1,
                            stock_conversion_ratio=0.0,
                            rights_ratio=0.0,
                            rights_price=0.0,
                            status="implemented",
                            updated_at=datetime(2026, 5, 29, 9, 0),
                        )
                    ]
                )

        targets = [
            {"series": SimpleNamespace(id=10), "instrument": SimpleNamespace(id=101)},
            {"series": SimpleNamespace(id=11), "instrument": SimpleNamespace(id=102)},
        ]

        raw_frames, action_frames, action_updated = sync_service._preload_tdx_qfq_input_frames(
            _BatchSession(),
            targets,
            SimpleNamespace(id=301),
        )

        self.assertEqual(sorted(raw_frames.keys()), [10, 11])
        self.assertEqual(sorted(action_frames.keys()), [101, 102])
        self.assertEqual(len(raw_frames[10]), 1)
        self.assertEqual(float(raw_frames[10].iloc[0]["Close"]), 10.5)
        self.assertEqual(len(raw_frames[11]), 1)
        self.assertEqual(float(raw_frames[11].iloc[0]["Amount"]), 2000.0)
        self.assertEqual(len(action_frames[101]), 1)
        self.assertEqual(float(action_frames[101].iloc[0]["cash_dividend"]), 0.5)
        self.assertTrue(action_frames[102].empty)
        self.assertIsNotNone(action_updated[101])
        self.assertIsNone(action_updated[102])
        self.assertEqual(
            list(action_frames[102].columns),
            [
                "ex_date",
                "cash_dividend",
                "stock_bonus_ratio",
                "stock_conversion_ratio",
                "rights_ratio",
                "rights_price",
                "status",
            ],
        )

    def test_preload_tdx_qfq_output_entities_groups_existing_aliases_and_series(self) -> None:
        class _ScalarResult:
            def __init__(self, rows: list[object]) -> None:
                self._rows = rows

            def all(self) -> list[object]:
                return list(self._rows)

        class _BatchSession:
            def __init__(self) -> None:
                self.calls = 0

            def scalars(self, _statement: object) -> _ScalarResult:
                self.calls += 1
                if self.calls == 1:
                    return _ScalarResult(
                        [
                            SimpleNamespace(
                                id=901,
                                provider_id=401,
                                source_symbol="SH600000",
                                source_name="浦发银行",
                            ),
                            SimpleNamespace(
                                id=902,
                                provider_id=401,
                                source_symbol="SZ000001",
                                source_name="平安银行",
                            ),
                        ]
                    )
                return _ScalarResult(
                    [
                        SimpleNamespace(
                            id=1001,
                            provider_id=401,
                            alias_id=901,
                            interval="1d",
                            adjustment_kind="qfq",
                            session_type="regular",
                            price_type="trade",
                        ),
                        SimpleNamespace(
                            id=1002,
                            provider_id=401,
                            alias_id=902,
                            interval="1d",
                            adjustment_kind="qfq",
                            session_type="regular",
                            price_type="trade",
                        ),
                    ]
                )

        targets = [
            {
                "series": SimpleNamespace(id=701),
                "instrument": SimpleNamespace(id=801, symbol="SH600000"),
                "alias": SimpleNamespace(source_symbol="SH600000"),
            },
            {
                "series": SimpleNamespace(id=702),
                "instrument": SimpleNamespace(id=802, symbol="SZ000001"),
                "alias": SimpleNamespace(source_symbol="SZ000001"),
            },
        ]

        alias_map, series_map = sync_service._preload_tdx_qfq_output_entities(
            _BatchSession(),
            targets,
            SimpleNamespace(id=401, provider_key="tdx_qfq"),
            interval="1d",
        )

        self.assertEqual(sorted(alias_map.keys()), ["SH600000", "SZ000001"])
        self.assertEqual(alias_map["SH600000"].id, 901)
        self.assertEqual(alias_map["SZ000001"].id, 902)
        self.assertEqual(
            sorted(series_map.keys()),
            [
                (901, "1d", "qfq", "regular", "trade"),
                (902, "1d", "qfq", "regular", "trade"),
            ],
        )
        self.assertEqual(series_map[(901, "1d", "qfq", "regular", "trade")].id, 1001)
        self.assertEqual(series_map[(902, "1d", "qfq", "regular", "trade")].id, 1002)

    def test_rebuild_tdx_qfq_market_data_uses_preloaded_frames_for_batch_targets(self) -> None:
        registry: dict[int, object] = {}

        class _NestedContext:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        class _SessionDouble:
            def __init__(self) -> None:
                self.commit_calls = 0

            def commit(self) -> None:
                self.commit_calls += 1

            def rollback(self) -> None:
                return None

            def get(self, _model, identity):
                return registry.get(identity)

            def begin_nested(self):
                return _NestedContext()

        session = _SessionDouble()

        class _SessionContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return False

        raw_provider = SimpleNamespace(id=401, provider_key="tdx")
        action_provider = SimpleNamespace(id=402, provider_key="tushare")
        qfq_provider = SimpleNamespace(id=403, provider_key="tdx_qfq")
        ingestion_job = SimpleNamespace(
            id=501,
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            summary_json={},
            completed_at=None,
            status="running",
            error_message="",
        )
        registry[501] = ingestion_job

        item_ids = [601, 602]

        def fake_create_item(*_args, **_kwargs):
            current_id = item_ids.pop(0)
            item = SimpleNamespace(
                id=current_id,
                status="running",
                stage="download",
                rows_inserted=0,
                rows_updated=0,
                details_json={},
                error_message="",
                instrument_id=None,
                series_id=None,
            )
            registry[current_id] = item
            return item

        targets = [
            {
                "series": SimpleNamespace(id=701),
                "instrument": SimpleNamespace(id=801, symbol="SH600000", name="浦发银行", exchange="SH", timezone="Asia/Shanghai"),
                "alias": SimpleNamespace(source_symbol="SH600000", source_name="浦发银行", market="SH", exchange="SH", security_type="stock", timezone="Asia/Shanghai"),
            },
            {
                "series": SimpleNamespace(id=702),
                "instrument": SimpleNamespace(id=802, symbol="SZ000001", name="平安银行", exchange="SZ", timezone="Asia/Shanghai"),
                "alias": SimpleNamespace(source_symbol="SZ000001", source_name="平安银行", market="SZ", exchange="SZ", security_type="stock", timezone="Asia/Shanghai"),
            },
        ]
        raw_frames = {
            701: pd.DataFrame(
                [
                    {"Date": "2026-05-28", "Open": 10.0, "High": 11.0, "Low": 9.0, "Close": 10.5, "Volume": 100, "Amount": 1000.0},
                    {"Date": "2026-05-29", "Open": 10.6, "High": 11.2, "Low": 10.1, "Close": 11.0, "Volume": 110, "Amount": 1100.0},
                ]
            ),
            702: pd.DataFrame(
                [
                    {"Date": "2026-05-28", "Open": 20.0, "High": 21.0, "Low": 19.5, "Close": 20.2, "Volume": 200, "Amount": 2000.0},
                    {"Date": "2026-05-29", "Open": 20.3, "High": 21.1, "Low": 20.0, "Close": 20.8, "Volume": 210, "Amount": 2100.0},
                ]
            ),
        }
        action_frames = {
            801: pd.DataFrame(
                [
                    {
                        "ex_date": "2026-05-29",
                        "cash_dividend": 0.5,
                        "stock_bonus_ratio": 0.0,
                        "stock_conversion_ratio": 0.0,
                        "rights_ratio": 0.0,
                        "rights_price": 0.0,
                        "status": "implemented",
                    }
                ]
            ),
            802: pd.DataFrame(columns=["ex_date", "cash_dividend", "stock_bonus_ratio", "stock_conversion_ratio", "rights_ratio", "rights_price", "status"]),
        }
        preloaded_qfq_aliases = {
            "SH600000": SimpleNamespace(
                id=901,
                instrument_id=801,
                source_symbol="SH600000",
                source_name="浦发银行",
                market="SH",
                exchange="SH",
                security_type="stock",
                timezone="Asia/Shanghai",
                is_primary=True,
            ),
            "SZ000001": SimpleNamespace(
                id=902,
                instrument_id=802,
                source_symbol="SZ000001",
                source_name="平安银行",
                market="SZ",
                exchange="SZ",
                security_type="stock",
                timezone="Asia/Shanghai",
                is_primary=True,
            ),
        }
        preloaded_qfq_series = {
            (901, "1d", "qfq", "regular", "trade"): SimpleNamespace(
                id=903,
                alias_id=901,
                instrument_id=801,
                market="SH",
                exchange="SH",
                bar_type="time",
                timezone="Asia/Shanghai",
                is_active=True,
                metadata_json={"adjusted_frame_digest": ""},
            ),
            (902, "1d", "qfq", "regular", "trade"): SimpleNamespace(
                id=904,
                alias_id=902,
                instrument_id=802,
                market="SZ",
                exchange="SZ",
                bar_type="time",
                timezone="Asia/Shanghai",
                is_active=True,
                metadata_json={"adjusted_frame_digest": ""},
            ),
        }

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", side_effect=[raw_provider, action_provider, qfq_provider]),
            patch("strategy_studio.services.sync._resolve_tdx_qfq_targets", return_value=targets),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", side_effect=fake_create_item),
            patch(
                "strategy_studio.services.sync._preload_tdx_qfq_action_updated_at",
                return_value={801: datetime(2026, 5, 29, 0, 0), 802: None},
            ) as mock_preload_action_updated,
            patch(
                "strategy_studio.services.sync._preload_tdx_qfq_input_frames",
                return_value=(raw_frames, action_frames, {801: datetime(2026, 5, 29, 0, 0), 802: None}),
            ) as mock_preload,
            patch(
                "strategy_studio.services.sync._preload_tdx_qfq_output_entities",
                return_value=(preloaded_qfq_aliases, preloaded_qfq_series),
            ) as mock_preload_output,
            patch(
                "strategy_studio.services.sync.build_qfq_segment_frame",
                return_value=pd.DataFrame(
                    [
                        {
                            "start_date": "2026-05-28",
                            "end_date": "2026-05-29",
                            "adjust_a": 1.0,
                            "adjust_b": 0.0,
                            "status": "ready",
                            "payload_json": {"source": "test", "source_hash": "segmenthash600000"},
                        }
                    ]
                ),
            ),
            patch(
                "strategy_studio.services.sync.apply_qfq_segment_frame",
                side_effect=lambda raw_frame, _segment_frame: raw_frame.assign(AdjustA=1.0, AdjustB=0.0),
            ),
            patch("strategy_studio.services.sync.replace_price_adjustment_segments", return_value=(1, 0, 0)),
            patch("strategy_studio.services.sync.get_or_create_instrument_alias", side_effect=AssertionError("不应创建新的 qfq alias")),
            patch("strategy_studio.services.sync.get_or_create_market_data_series", side_effect=AssertionError("不应创建新的 qfq series")),
            patch(
                "strategy_studio.services.sync.upsert_market_data_frame",
                side_effect=lambda _session, _series, frame: (len(frame), 0),
            ),
            patch("strategy_studio.services.sync._load_raw_market_data_frame") as mock_load_raw,
            patch("strategy_studio.services.sync._load_instrument_action_frame") as mock_load_actions,
        ):
            result = sync_service._rebuild_tdx_qfq_market_data(
                symbol=None,
                interval="1d",
                force=True,
                limit=2,
            )

        mock_preload_action_updated.assert_called_once_with(session, targets, action_provider)
        mock_preload.assert_called_once_with(session, targets, action_provider)
        mock_preload_output.assert_called_once_with(session, targets, qfq_provider, interval="1d")
        mock_load_raw.assert_not_called()
        mock_load_actions.assert_not_called()
        self.assertEqual(result["provider"], "tdx_qfq")
        self.assertEqual(result["symbols_count"], 2)
        self.assertEqual(result["bars_inserted"], 4)
        self.assertEqual(result["bars_updated"], 0)
        self.assertEqual(result["segment_rows_inserted"], 2)
        self.assertEqual(result["action_rows_used"], 1)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(ingestion_job.targets_total, 2)
        self.assertEqual(ingestion_job.targets_completed, 2)
        self.assertEqual(ingestion_job.rows_inserted, 4)
        self.assertEqual(ingestion_job.error_count, 0)
        self.assertEqual(ingestion_job.status, "succeeded")
        self.assertIn("timing_json", result)
        self.assertIn("timing_json", ingestion_job.summary_json)
        self.assertIn("total_elapsed_ms", ingestion_job.summary_json["timing_json"])
        self.assertIn("bar_upsert_ms", ingestion_job.summary_json["timing_json"])
        self.assertIn("timing_json", registry[601].details_json)
        self.assertIn("timing_json", registry[602].details_json)
        self.assertIn("segment_build_ms", registry[601].details_json["timing_json"])
        self.assertIn("total_elapsed_ms", registry[602].details_json["timing_json"])
        self.assertTrue(registry[601].details_json["raw_frame_digest"])
        self.assertTrue(registry[601].details_json["segment_frame_digest"])
        self.assertTrue(registry[601].details_json["adjusted_frame_digest"])
        self.assertEqual(registry[601].details_json["segment_source_hashes"], ["segmenthash600000"])
        self.assertEqual(session.commit_calls, 3)

    def test_rebuild_tdx_qfq_market_data_commits_failed_item_without_rolling_back_batch_progress(self) -> None:
        registry: dict[int, object] = {}

        class _NestedContext:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        class _SessionDouble:
            def __init__(self) -> None:
                self.commit_calls = 0

            def commit(self) -> None:
                self.commit_calls += 1

            def rollback(self) -> None:
                return None

            def get(self, _model, identity):
                return registry.get(identity)

            def begin_nested(self):
                return _NestedContext()

        session = _SessionDouble()

        class _SessionContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return False

        raw_provider = SimpleNamespace(id=411, provider_key="tdx")
        action_provider = SimpleNamespace(id=412, provider_key="tushare")
        qfq_provider = SimpleNamespace(id=413, provider_key="tdx_qfq")
        ingestion_job = SimpleNamespace(
            id=511,
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            summary_json={},
            completed_at=None,
            status="running",
            error_message="",
        )
        registry[511] = ingestion_job

        item_ids = [611, 612]

        def fake_create_item(*_args, **_kwargs):
            current_id = item_ids.pop(0)
            item = SimpleNamespace(
                id=current_id,
                status="running",
                stage="download",
                rows_inserted=0,
                rows_updated=0,
                details_json={},
                error_message="",
                instrument_id=None,
                series_id=None,
            )
            registry[current_id] = item
            return item

        targets = [
            {
                "series": SimpleNamespace(id=711),
                "instrument": SimpleNamespace(id=811, symbol="SH600000", name="浦发银行", exchange="SH", timezone="Asia/Shanghai"),
                "alias": SimpleNamespace(source_symbol="SH600000", source_name="浦发银行", market="SH", exchange="SH", security_type="stock", timezone="Asia/Shanghai"),
            },
            {
                "series": SimpleNamespace(id=712),
                "instrument": SimpleNamespace(id=812, symbol="SZ000001", name="平安银行", exchange="SZ", timezone="Asia/Shanghai"),
                "alias": SimpleNamespace(source_symbol="SZ000001", source_name="平安银行", market="SZ", exchange="SZ", security_type="stock", timezone="Asia/Shanghai"),
            },
        ]
        raw_frames = {
            711: pd.DataFrame(
                [
                    {"Date": "2026-05-28", "Open": 10.0, "High": 11.0, "Low": 9.0, "Close": 10.5, "Volume": 100, "Amount": 1000.0},
                    {"Date": "2026-05-29", "Open": 10.6, "High": 11.2, "Low": 10.1, "Close": 11.0, "Volume": 110, "Amount": 1100.0},
                ]
            ),
            712: pd.DataFrame(
                [
                    {"Date": "2026-05-28", "Open": 20.0, "High": 21.0, "Low": 19.5, "Close": 20.2, "Volume": 200, "Amount": 2000.0},
                    {"Date": "2026-05-29", "Open": 20.3, "High": 21.1, "Low": 20.0, "Close": 20.8, "Volume": 210, "Amount": 2100.0},
                ]
            ),
        }
        action_frames = {
            811: pd.DataFrame(columns=["ex_date", "cash_dividend", "stock_bonus_ratio", "stock_conversion_ratio", "rights_ratio", "rights_price", "status"]),
            812: pd.DataFrame(columns=["ex_date", "cash_dividend", "stock_bonus_ratio", "stock_conversion_ratio", "rights_ratio", "rights_price", "status"]),
        }

        replace_results = [RuntimeError("segment rebuild failed"), (1, 0, 0)]
        qfq_series_ids = [911, 912]

        def fake_replace_segments(*_args, **_kwargs):
            result = replace_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        def fake_get_or_create_market_data_series(*_args, **_kwargs):
            return SimpleNamespace(id=qfq_series_ids.pop(0), metadata_json={})

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", side_effect=[raw_provider, action_provider, qfq_provider]),
            patch("strategy_studio.services.sync._resolve_tdx_qfq_targets", return_value=targets),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", side_effect=fake_create_item),
            patch(
                "strategy_studio.services.sync._preload_tdx_qfq_action_updated_at",
                return_value={811: None, 812: None},
            ),
            patch(
                "strategy_studio.services.sync._preload_tdx_qfq_input_frames",
                return_value=(raw_frames, action_frames, {811: None, 812: None}),
            ),
            patch(
                "strategy_studio.services.sync._preload_tdx_qfq_output_entities",
                return_value=({}, {}),
            ),
            patch(
                "strategy_studio.services.sync.build_qfq_segment_frame",
                return_value=pd.DataFrame(
                    [
                        {
                            "start_date": "2026-05-28",
                            "end_date": "2026-05-29",
                            "adjust_a": 1.0,
                            "adjust_b": 0.0,
                            "status": "ready",
                            "payload_json": {"source": "test"},
                        }
                    ]
                ),
            ),
            patch(
                "strategy_studio.services.sync.apply_qfq_segment_frame",
                side_effect=lambda raw_frame, _segment_frame: raw_frame.assign(AdjustA=1.0, AdjustB=0.0),
            ),
            patch("strategy_studio.services.sync.replace_price_adjustment_segments", side_effect=fake_replace_segments),
            patch("strategy_studio.services.sync.get_or_create_instrument_alias", side_effect=lambda *_args, **kwargs: kwargs["instrument"]),
            patch("strategy_studio.services.sync.get_or_create_market_data_series", side_effect=fake_get_or_create_market_data_series),
            patch("strategy_studio.services.sync.upsert_market_data_frame", side_effect=lambda _session, _series, frame: (len(frame), 0)),
        ):
            result = sync_service._rebuild_tdx_qfq_market_data(
                symbol=None,
                interval="1d",
                force=True,
                limit=2,
            )

        failed_item = registry[611]
        succeeded_item = registry[612]
        self.assertEqual(result["status"], "partially_failed")
        self.assertEqual(result["bars_inserted"], 2)
        self.assertEqual(result["segment_rows_inserted"], 1)
        self.assertEqual(ingestion_job.targets_total, 2)
        self.assertEqual(ingestion_job.targets_completed, 1)
        self.assertEqual(ingestion_job.error_count, 1)
        self.assertEqual(ingestion_job.status, "partially_failed")
        self.assertIn("segment rebuild failed", ingestion_job.error_message)
        self.assertIn("timing_json", result)
        self.assertIn("timing_json", ingestion_job.summary_json)
        self.assertEqual(failed_item.status, "failed")
        self.assertEqual(failed_item.stage, "failed")
        self.assertIn("timing_json", failed_item.details_json)
        self.assertIn("total_elapsed_ms", failed_item.details_json["timing_json"])
        self.assertEqual(succeeded_item.status, "succeeded")
        self.assertEqual(succeeded_item.stage, "completed")
        self.assertIn("timing_json", succeeded_item.details_json)
        self.assertIn("bar_upsert_ms", succeeded_item.details_json["timing_json"])
        self.assertEqual(session.commit_calls, 4)

    def test_rebuild_tdx_qfq_market_data_skips_up_to_date_series_when_not_forced(self) -> None:
        registry: dict[int, object] = {}

        class _NestedContext:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        class _SessionDouble:
            def __init__(self) -> None:
                self.commit_calls = 0

            def commit(self) -> None:
                self.commit_calls += 1

            def rollback(self) -> None:
                return None

            def get(self, _model, identity):
                return registry.get(identity)

            def begin_nested(self):
                return _NestedContext()

        session = _SessionDouble()

        class _SessionContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return False

        raw_provider = SimpleNamespace(id=421, provider_key="tdx")
        action_provider = SimpleNamespace(id=422, provider_key="tushare")
        qfq_provider = SimpleNamespace(id=423, provider_key="tdx_qfq")
        ingestion_job = SimpleNamespace(
            id=521,
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            summary_json={},
            completed_at=None,
            status="running",
            error_message="",
        )
        registry[521] = ingestion_job

        def fake_create_item(*_args, **_kwargs):
            item = SimpleNamespace(
                id=621,
                status="running",
                stage="download",
                rows_inserted=0,
                rows_updated=0,
                details_json={},
                error_message="",
                instrument_id=None,
                series_id=None,
            )
            registry[621] = item
            return item

        raw_last_ingested_at = datetime(2026, 5, 29, 9, 0)
        qfq_last_ingested_at = datetime(2026, 5, 29, 10, 0)
        targets = [
            {
                "series": SimpleNamespace(id=721, last_ingested_at=raw_last_ingested_at),
                "instrument": SimpleNamespace(id=821, symbol="SH600000", name="浦发银行", exchange="SH", timezone="Asia/Shanghai"),
                "alias": SimpleNamespace(source_symbol="SH600000", source_name="浦发银行", market="SH", exchange="SH", security_type="stock", timezone="Asia/Shanghai"),
            }
        ]
        raw_frames = {
            721: pd.DataFrame(
                [
                    {"Date": "2026-05-28", "Open": 10.0, "High": 11.0, "Low": 9.0, "Close": 10.5, "Volume": 100, "Amount": 1000.0},
                    {"Date": "2026-05-29", "Open": 10.6, "High": 11.2, "Low": 10.1, "Close": 11.0, "Volume": 110, "Amount": 1100.0},
                ]
            ),
        }
        action_frames = {
            821: pd.DataFrame(columns=["ex_date", "cash_dividend", "stock_bonus_ratio", "stock_conversion_ratio", "rights_ratio", "rights_price", "status"]),
        }
        preloaded_qfq_aliases = {
            "SH600000": SimpleNamespace(
                id=931,
                instrument_id=821,
                source_symbol="SH600000",
                source_name="浦发银行",
                market="SH",
                exchange="SH",
                security_type="stock",
                timezone="Asia/Shanghai",
                is_primary=True,
            )
        }
        preloaded_qfq_series = {
            (931, "1d", "qfq", "regular", "trade"): SimpleNamespace(
                id=932,
                alias_id=931,
                instrument_id=821,
                market="SH",
                exchange="SH",
                bar_type="time",
                timezone="Asia/Shanghai",
                is_active=True,
                last_ingested_at=qfq_last_ingested_at,
                metadata_json={
                    "raw_provider_key": "tdx",
                    "raw_series_id": 721,
                    "action_provider_key": "tushare",
                },
            )
        }

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", side_effect=[raw_provider, action_provider, qfq_provider]),
            patch("strategy_studio.services.sync._resolve_tdx_qfq_targets", return_value=targets),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", side_effect=fake_create_item),
            patch(
                "strategy_studio.services.sync._preload_tdx_qfq_action_updated_at",
                return_value={821: qfq_last_ingested_at},
            ),
            patch(
                "strategy_studio.services.sync._preload_tdx_qfq_input_frames",
                return_value=(raw_frames, action_frames, {821: qfq_last_ingested_at}),
            ) as mock_preload_input,
            patch(
                "strategy_studio.services.sync._preload_tdx_qfq_output_entities",
                return_value=(preloaded_qfq_aliases, preloaded_qfq_series),
            ),
            patch("strategy_studio.services.sync.build_qfq_segment_frame", side_effect=AssertionError("最新序列不应重建区间")),
            patch("strategy_studio.services.sync.replace_price_adjustment_segments", side_effect=AssertionError("最新序列不应重写区间")),
            patch("strategy_studio.services.sync.apply_qfq_segment_frame", side_effect=AssertionError("最新序列不应重算前复权")),
            patch("strategy_studio.services.sync.upsert_market_data_frame", side_effect=AssertionError("最新序列不应重写 K 线")),
        ):
            result = sync_service._rebuild_tdx_qfq_market_data(
                symbol=None,
                interval="1d",
                force=False,
                limit=1,
            )

        skipped_item = registry[621]
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["symbols_skipped"], 1)
        self.assertEqual(result["bars_updated"], 0)
        self.assertEqual(ingestion_job.targets_total, 1)
        self.assertEqual(ingestion_job.targets_completed, 1)
        self.assertEqual(ingestion_job.status, "skipped")
        self.assertEqual(ingestion_job.summary_json["symbols_skipped"], 1)
        self.assertEqual(skipped_item.status, "skipped")
        self.assertEqual(skipped_item.stage, "completed")
        self.assertEqual(skipped_item.series_id, 932)
        self.assertEqual(skipped_item.details_json["reason"], "qfq_series_up_to_date")
        self.assertEqual(skipped_item.details_json["normal_skip_reasons"], [])
        self.assertIn("缺少原始摘要", skipped_item.details_json["force_skip_reasons"])
        self.assertIn("timing_json", skipped_item.details_json)
        mock_preload_input.assert_not_called()

    def test_rebuild_tdx_qfq_market_data_skips_bar_upsert_when_digest_matches_existing_output(self) -> None:
        registry: dict[int, object] = {}

        class _NestedContext:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        class _SessionDouble:
            def __init__(self) -> None:
                self.commit_calls = 0

            def commit(self) -> None:
                self.commit_calls += 1

            def rollback(self) -> None:
                return None

            def get(self, _model, identity):
                return registry.get(identity)

            def begin_nested(self):
                return _NestedContext()

        session = _SessionDouble()

        class _SessionContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return False

        raw_provider = SimpleNamespace(id=431, provider_key="tdx")
        action_provider = SimpleNamespace(id=432, provider_key="tushare")
        qfq_provider = SimpleNamespace(id=433, provider_key="tdx_qfq")
        ingestion_job = SimpleNamespace(
            id=531,
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            summary_json={},
            completed_at=None,
            status="running",
            error_message="",
        )
        registry[531] = ingestion_job

        def fake_create_item(*_args, **_kwargs):
            item = SimpleNamespace(
                id=631,
                status="running",
                stage="download",
                rows_inserted=0,
                rows_updated=0,
                details_json={},
                error_message="",
                instrument_id=None,
                series_id=None,
            )
            registry[631] = item
            return item

        targets = [
            {
                "series": SimpleNamespace(id=731, last_ingested_at=datetime(2026, 5, 29, 9, 0)),
                "instrument": SimpleNamespace(id=831, symbol="SH600000", name="浦发银行", exchange="SH", timezone="Asia/Shanghai"),
                "alias": SimpleNamespace(source_symbol="SH600000", source_name="浦发银行", market="SH", exchange="SH", security_type="stock", timezone="Asia/Shanghai"),
            }
        ]
        adjusted_frame = pd.DataFrame(
            [
                {"Date": "2026-05-28", "Open": 10.0, "High": 11.0, "Low": 9.0, "Close": 10.5, "Volume": 100, "Amount": 1000.0, "AdjustA": 1.0, "AdjustB": 0.0},
                {"Date": "2026-05-29", "Open": 10.6, "High": 11.2, "Low": 10.1, "Close": 11.0, "Volume": 110, "Amount": 1100.0, "AdjustA": 1.0, "AdjustB": 0.0},
            ]
        )
        segment_frame = pd.DataFrame(
            [
                {
                    "start_date": "2026-05-28",
                    "end_date": "2026-05-29",
                    "adjust_a": 1.0,
                    "adjust_b": 0.0,
                    "status": "ready",
                    "payload_json": {"source": "test"},
                }
            ]
        )
        digest = sync_service._build_market_data_frame_digest(adjusted_frame)
        raw_digest = sync_service._build_market_data_frame_digest(adjusted_frame.drop(columns=["AdjustA", "AdjustB"]))
        segment_digest = sync_service._build_segment_frame_digest(segment_frame)
        raw_frames = {731: adjusted_frame.drop(columns=["AdjustA", "AdjustB"])}
        action_frames = {
            831: pd.DataFrame(columns=["ex_date", "cash_dividend", "stock_bonus_ratio", "stock_conversion_ratio", "rights_ratio", "rights_price", "status"]),
        }
        preloaded_qfq_aliases = {
            "SH600000": SimpleNamespace(
                id=941,
                instrument_id=831,
                source_symbol="SH600000",
                source_name="浦发银行",
                market="SH",
                exchange="SH",
                security_type="stock",
                timezone="Asia/Shanghai",
                is_primary=True,
            )
        }
        preloaded_qfq_series = {
            (941, "1d", "qfq", "regular", "trade"): SimpleNamespace(
                id=942,
                alias_id=941,
                instrument_id=831,
                market="SH",
                exchange="SH",
                bar_type="time",
                timezone="Asia/Shanghai",
                is_active=True,
                metadata_json={
                    "raw_provider_key": "tdx",
                    "raw_series_id": 731,
                    "action_provider_key": "tushare",
                    "raw_frame_digest": raw_digest,
                    "segment_frame_digest": segment_digest,
                    "adjusted_frame_digest": digest,
                },
            )
        }

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", side_effect=[raw_provider, action_provider, qfq_provider]),
            patch("strategy_studio.services.sync._resolve_tdx_qfq_targets", return_value=targets),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", side_effect=fake_create_item),
            patch("strategy_studio.services.sync._preload_tdx_qfq_action_updated_at", return_value={831: None}),
            patch("strategy_studio.services.sync._preload_tdx_qfq_input_frames", return_value=(raw_frames, action_frames, {831: None})),
            patch("strategy_studio.services.sync._preload_tdx_qfq_output_entities", return_value=(preloaded_qfq_aliases, preloaded_qfq_series)),
            patch("strategy_studio.services.sync.build_qfq_segment_frame", return_value=segment_frame),
            patch("strategy_studio.services.sync.apply_qfq_segment_frame", side_effect=AssertionError("区间摘要一致时不应再应用前复权")),
            patch("strategy_studio.services.sync.replace_price_adjustment_segments", side_effect=AssertionError("区间摘要一致时不应重写区间")),
            patch("strategy_studio.services.sync.upsert_market_data_frame", side_effect=AssertionError("摘要一致时不应重写 K 线")),
        ):
            result = sync_service._rebuild_tdx_qfq_market_data(
                symbol=None,
                interval="1d",
                force=True,
                limit=1,
            )

        succeeded_item = registry[631]
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["bars_inserted"], 0)
        self.assertEqual(result["bars_updated"], 0)
        self.assertEqual(succeeded_item.status, "succeeded")
        self.assertTrue(succeeded_item.details_json["segment_replace_skipped"])
        self.assertTrue(succeeded_item.details_json["bar_upsert_skipped"])
        self.assertEqual(succeeded_item.details_json["timing_json"]["segment_replace_ms"], 0)
        self.assertEqual(succeeded_item.details_json["timing_json"]["segment_apply_ms"], 0)
        self.assertEqual(succeeded_item.details_json["timing_json"]["bar_upsert_ms"], 0)

    def test_rebuild_tdx_qfq_market_data_force_cache_hit_skips_input_preload(self) -> None:
        registry: dict[int, object] = {}

        class _NestedContext:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        class _SessionDouble:
            def __init__(self) -> None:
                self.commit_calls = 0

            def commit(self) -> None:
                self.commit_calls += 1

            def rollback(self) -> None:
                return None

            def get(self, _model, identity):
                return registry.get(identity)

            def begin_nested(self):
                return _NestedContext()

        session = _SessionDouble()

        class _SessionContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return False

        raw_last_ingested_at = datetime(2026, 5, 29, 9, 0, tzinfo=UTC)
        qfq_last_ingested_at = datetime(2026, 5, 29, 9, 30, tzinfo=UTC)
        raw_provider = SimpleNamespace(id=541, provider_key="tdx")
        action_provider = SimpleNamespace(id=542, provider_key="tushare")
        qfq_provider = SimpleNamespace(id=543, provider_key="tdx_qfq")
        ingestion_job = SimpleNamespace(
            id=641,
            targets_total=0,
            targets_completed=0,
            rows_inserted=0,
            rows_updated=0,
            error_count=0,
            summary_json={},
            completed_at=None,
            status="running",
            error_message="",
        )
        registry[641] = ingestion_job

        def fake_create_item(*_args, **_kwargs):
            item = SimpleNamespace(
                id=741,
                status="running",
                stage="download",
                rows_inserted=0,
                rows_updated=0,
                details_json={},
                error_message="",
                instrument_id=None,
                series_id=None,
            )
            registry[741] = item
            return item

        targets = [
            {
                "series": SimpleNamespace(id=841, last_ingested_at=raw_last_ingested_at),
                "instrument": SimpleNamespace(id=941, symbol="SH600000", name="浦发银行", exchange="SH", timezone="Asia/Shanghai"),
                "alias": SimpleNamespace(source_symbol="SH600000", source_name="浦发银行", market="SH", exchange="SH", security_type="stock", timezone="Asia/Shanghai"),
            }
        ]
        preloaded_qfq_aliases = {
            "SH600000": SimpleNamespace(
                id=1041,
                instrument_id=941,
                source_symbol="SH600000",
                source_name="浦发银行",
                market="SH",
                exchange="SH",
                security_type="stock",
                timezone="Asia/Shanghai",
                is_primary=True,
            )
        }
        preloaded_qfq_series = {
            (1041, "1d", "qfq", "regular", "trade"): SimpleNamespace(
                id=1042,
                alias_id=1041,
                instrument_id=941,
                market="SH",
                exchange="SH",
                bar_type="time",
                timezone="Asia/Shanghai",
                is_active=True,
                last_ingested_at=qfq_last_ingested_at,
                metadata_json={
                    "raw_provider_key": "tdx",
                    "raw_series_id": 841,
                    "action_provider_key": "tushare",
                    "raw_frame_digest": "rawdigest",
                    "segment_frame_digest": "segmentdigest",
                    "adjusted_frame_digest": "adjusteddigest",
                },
            )
        }

        with (
            patch("strategy_studio.services.sync.open_session", return_value=_SessionContext()),
            patch("strategy_studio.services.sync.ensure_data_provider", side_effect=[raw_provider, action_provider, qfq_provider]),
            patch("strategy_studio.services.sync._resolve_tdx_qfq_targets", return_value=targets),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", side_effect=fake_create_item),
            patch("strategy_studio.services.sync._preload_tdx_qfq_action_updated_at", return_value={941: raw_last_ingested_at}),
            patch("strategy_studio.services.sync._preload_tdx_qfq_input_frames", side_effect=AssertionError("force 缓存命中时不应预加载原始输入")),
            patch("strategy_studio.services.sync._preload_tdx_qfq_output_entities", return_value=(preloaded_qfq_aliases, preloaded_qfq_series)),
            patch("strategy_studio.services.sync.build_qfq_segment_frame", side_effect=AssertionError("force 缓存命中时不应重建区间")),
            patch("strategy_studio.services.sync.replace_price_adjustment_segments", side_effect=AssertionError("force 缓存命中时不应重写区间")),
            patch("strategy_studio.services.sync.apply_qfq_segment_frame", side_effect=AssertionError("force 缓存命中时不应重算前复权")),
            patch("strategy_studio.services.sync.upsert_market_data_frame", side_effect=AssertionError("force 缓存命中时不应重写 K 线")),
        ):
            result = sync_service._rebuild_tdx_qfq_market_data(
                symbol=None,
                interval="1d",
                force=True,
                limit=1,
            )

        succeeded_item = registry[741]
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["bars_inserted"], 0)
        self.assertEqual(result["bars_updated"], 0)
        self.assertEqual(result["segment_rows_inserted"], 0)
        self.assertEqual(result["segment_rows_updated"], 0)
        self.assertEqual(result["segment_rows_deleted"], 0)
        self.assertEqual(result["action_rows_used"], 0)
        self.assertEqual(ingestion_job.summary_json["timing_json"]["preload_input_ms"], 0)
        self.assertEqual(ingestion_job.summary_json["timing_json"]["segment_build_ms"], 0)
        self.assertEqual(succeeded_item.status, "succeeded")
        self.assertEqual(succeeded_item.series_id, 1042)
        self.assertEqual(succeeded_item.details_json["reason"], "qfq_force_cache_hit")
        self.assertEqual(succeeded_item.details_json["force_skip_reasons"], [])
        self.assertEqual(succeeded_item.details_json["raw_frame_digest"], "rawdigest")
        self.assertEqual(succeeded_item.details_json["segment_frame_digest"], "segmentdigest")
        self.assertEqual(succeeded_item.details_json["adjusted_frame_digest"], "adjusteddigest")
        self.assertTrue(succeeded_item.details_json["segment_replace_skipped"])
        self.assertTrue(succeeded_item.details_json["bar_upsert_skipped"])
        self.assertEqual(succeeded_item.details_json["timing_json"]["segment_build_ms"], 0)
        self.assertEqual(succeeded_item.details_json["timing_json"]["segment_replace_ms"], 0)
        self.assertEqual(succeeded_item.details_json["timing_json"]["segment_apply_ms"], 0)
        self.assertEqual(succeeded_item.details_json["timing_json"]["bar_upsert_ms"], 0)


class StrategyTemplateServiceTests(unittest.TestCase):
    def test_backtest_parallelism_is_capped_by_worker_and_cpu_budget(self) -> None:
        with patch("strategy_studio.services.backtests.os.cpu_count", return_value=8):
            self.assertEqual(_resolve_effective_parallelism(6, max_optimization_workers=4, worker_concurrency=2), 4)
            self.assertEqual(_resolve_effective_parallelism(6, max_optimization_workers=8, worker_concurrency=4), 2)

    def test_eta_estimation_returns_remaining_seconds(self) -> None:
        self.assertEqual(_estimate_eta_seconds(50.0, 120), 120)
        self.assertEqual(_estimate_eta_seconds(100.0, 120), 0)
        self.assertIsNone(_estimate_eta_seconds(0.0, 120))

    def test_normalize_parameter_space_for_grid(self) -> None:
        payload = normalize_parameter_space(
            "grid",
            {"spacings": [0.01, "0.02"], "grid_counts": [4, "5"], "take_profits": [0.01, "0.03"]},
            "15m",
        )

        self.assertEqual(payload, {"spacings": [0.01, 0.02], "grid_counts": [4, 5], "take_profits": [0.01, 0.03]})

    def test_normalize_parameter_space_for_dca_keeps_string_fields(self) -> None:
        payload = normalize_parameter_space(
            "dca",
            {
                "investment_amount": [5000, "10000"],
                "frequency": ["weekly", "monthly"],
                "day_rule": ["first_trading_day"],
                "max_position_ratio": [0.95],
            },
            "1d",
        )

        self.assertEqual(
            payload,
            {
                "investment_amount": [5000.0, 10000.0],
                "frequency": ["weekly", "monthly"],
                "day_rule": ["first_trading_day"],
                "max_position_ratio": [0.95],
            },
        )

    def test_normalize_parameter_space_for_ma_cross(self) -> None:
        payload = normalize_parameter_space(
            "ma_cross",
            {
                "short_window": [5, "10"],
                "long_window": [20, "30"],
                "signal_buffer_pct": [0, "0.005"],
            },
            "1d",
        )

        self.assertEqual(
            payload,
            {
                "short_window": [5, 10],
                "long_window": [20, 30],
                "signal_buffer_pct": [0.0, 0.005],
            },
        )

    def test_normalize_parameter_space_for_macd_trend(self) -> None:
        payload = normalize_parameter_space(
            "macd_trend",
            {
                "fast_window": [8, "12"],
                "slow_window": [21, "26"],
                "signal_window": [5, "9"],
                "histogram_confirm_pct": [0, "0.05"],
                "stop_loss_pct": [4, "6"],
            },
            "1d",
        )

        self.assertEqual(
            payload,
            {
                "fast_window": [8, 12],
                "slow_window": [21, 26],
                "signal_window": [5, 9],
                "histogram_confirm_pct": [0.0, 0.05],
                "stop_loss_pct": [4.0, 6.0],
            },
        )

    def test_normalize_parameter_space_for_donchian_breakout(self) -> None:
        payload = normalize_parameter_space(
            "donchian_breakout",
            {
                "breakout_window": [20, "40"],
                "exit_window": [10, "20"],
                "confirm_buffer_pct": [0, "0.005"],
                "stop_loss_pct": [4, "6"],
            },
            "1d",
        )

        self.assertEqual(
            payload,
            {
                "breakout_window": [20, 40],
                "exit_window": [10, 20],
                "confirm_buffer_pct": [0.0, 0.005],
                "stop_loss_pct": [4.0, 6.0],
            },
        )

    def test_normalize_parameter_space_for_volume_breakout(self) -> None:
        payload = normalize_parameter_space(
            "volume_breakout",
            {
                "breakout_window": [20, "40"],
                "exit_window": [10, "20"],
                "volume_window": [5, "10"],
                "volume_multiplier": [1.2, "1.5"],
                "confirm_buffer_pct": [0, "0.005"],
                "stop_loss_pct": [4, "6"],
            },
            "1d",
        )

        self.assertEqual(
            payload,
            {
                "breakout_window": [20, 40],
                "exit_window": [10, 20],
                "volume_window": [5, 10],
                "volume_multiplier": [1.2, 1.5],
                "confirm_buffer_pct": [0.0, 0.005],
                "stop_loss_pct": [4.0, 6.0],
            },
        )

    def test_normalize_parameter_space_for_bollinger_reversion(self) -> None:
        payload = normalize_parameter_space(
            "bollinger_reversion",
            {
                "ma_window": [10, "20"],
                "band_width": [1.5, "2.0"],
                "rsi_entry": [25, "35"],
                "take_profit_pct": [3, "5"],
                "stop_loss_pct": [4, "6"],
                "max_hold_bars": [5, "8"],
            },
            "1d",
        )

        self.assertEqual(
            payload,
            {
                "ma_window": [10, 20],
                "band_width": [1.5, 2.0],
                "rsi_entry": [25.0, 35.0],
                "take_profit_pct": [3.0, 5.0],
                "stop_loss_pct": [4.0, 6.0],
                "max_hold_bars": [5, 8],
            },
        )

    def test_resolve_backtest_request_payload_merges_template_defaults(self) -> None:
        template = SimpleNamespace(
            id=7,
            template_key="minute_rebound_1m_realistic_default",
            template_name="分钟急跌反抽-1m 默认模板",
            strategy_kind="minute_rebound",
            interval="1m",
            execution_profile="realistic",
            validation_start="",
            lookback_days=None,
            validation_ratio=0.3,
            jobs=2,
            execution_overrides_json={"commission_bps": 8.0, "slippage_bps": 2.0, "max_position_ratio": 0.9, "stop_loss_pct": 0.2, "cooldown_bars": 5, "benchmark": "buy_hold", "left_side_policy": "both", "force_exit_loss_pct": 0.05},
            parameter_space_json={"lookback_bars": [8, 12], "drop_entry_pct": [-2.0, -1.5], "rsi_entry": [20.0], "take_profit_pct": [0.8], "stop_loss_pct": [1.0], "max_hold_bars": [4]},
            is_default=True,
            is_active=True,
        )
        request = SimpleNamespace(
            symbol="1810.hk",
            template_id=7,
            interval=None,
            strategy_kind=None,
            validation_start=None,
            lookback_days=None,
            validation_ratio=None,
            execution_profile=None,
            commission_bps=9.0,
            slippage_bps=None,
            max_position_ratio=None,
            stop_loss_pct=None,
            cooldown_bars=None,
            benchmark=None,
            left_side_policy=None,
            force_exit_loss_pct=None,
            jobs=4,
            parameter_space=None,
        )

        with patch("strategy_studio.services.templates.get_strategy_template", return_value=template):
            payload = resolve_backtest_request_payload(request, session=object())

        self.assertEqual(payload["symbol"], "1810.HK")
        self.assertEqual(payload["interval"], "1m")
        self.assertEqual(payload["strategy_kind"], "minute_rebound")
        self.assertEqual(payload["commission_bps"], 9.0)
        self.assertEqual(payload["validation_ratio"], 0.3)
        self.assertEqual(payload["jobs"], 4)
        self.assertEqual(payload["template_snapshot"]["template_key"], "minute_rebound_1m_realistic_default")

    def test_resolve_backtest_request_payload_normalizes_unified_market_data_fields(self) -> None:
        request = SimpleNamespace(
            symbol="sh600000",
            template_id=None,
            interval="1d",
            strategy_kind="dca",
            market_data_provider="TDX_QFQ",
            market_data_adjustment_kind=None,
            validation_start=None,
            lookback_days=None,
            validation_ratio=None,
            execution_profile=None,
            commission_bps=None,
            slippage_bps=None,
            max_position_ratio=None,
            stop_loss_pct=None,
            cooldown_bars=None,
            benchmark=None,
            left_side_policy=None,
            force_exit_loss_pct=None,
            jobs=2,
            parameter_space=None,
        )

        payload = resolve_backtest_request_payload(request, session=object())

        self.assertEqual(payload["symbol"], "SH600000")
        self.assertEqual(payload["market_data_provider"], "tdx_qfq")
        self.assertEqual(payload["market_data_adjustment_kind"], "qfq")
        self.assertEqual(payload["jobs"], 2)

    def test_seed_templates_keep_unique_keys(self) -> None:
        seeds = build_seed_templates()
        keys = [item.template_key for item in seeds]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("ma_cross_1d_realistic_default", keys)
        self.assertIn("macd_trend_1d_realistic_default", keys)
        self.assertIn("donchian_breakout_1d_realistic_default", keys)
        self.assertIn("volume_breakout_1d_realistic_default", keys)
        self.assertIn("bollinger_reversion_1d_realistic_default", keys)


if __name__ == "__main__":
    unittest.main()
    def test_web_api_market_data_sync_route_supports_yahoo_symbol_set(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch(
            "strategy_studio.web.app.enqueue_market_data_sync",
            return_value={"provider": "yahoo", "ingestion_job_id": 5, "status": "queued"},
        ) as mock_sync:
            response = client.post(
                "/api/market-data/sync",
                json={
                    "provider": "yahoo",
                    "symbol_set": "yahoo_global_active_100",
                    "interval": "15m",
                    "period": "60d",
                    "limit": 100,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "yahoo")
        mock_sync.assert_called_once_with(
            symbol=None,
            symbol_set="yahoo_global_active_100",
            interval="15m",
            proxy=None,
            period="60d",
            provider="yahoo",
            vipdoc_path=None,
            force=False,
            limit=100,
            batch_rounds=None,
        )
