from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from strategy_studio.cli import build_parser
from strategy_studio.platform_cli import handle_api, handle_check_db
from strategy_studio.services.backtests import _estimate_eta_seconds, _normalize_artifacts, _resolve_effective_parallelism
from strategy_studio.services.platform import record_platform_heartbeat
from strategy_studio.services.sync import sync_market_data
from strategy_studio.services.templates import build_seed_templates, normalize_parameter_space, resolve_backtest_request_payload
from strategy_studio.strategy.sampling import DeclineWindow
from strategy_studio.web.app import create_app
import strategy_studio.data.market_rules as market_rules


class PlatformFeatureTests(unittest.TestCase):
    """覆盖平台化新增命令和 API 基础契约。"""

    def test_cli_registers_platform_commands(self) -> None:
        parser = build_parser()

        init_args = parser.parse_args(["init-db"])
        check_db_args = parser.parse_args(["check-db", "--json"])
        api_args = parser.parse_args(["api", "--host", "127.0.0.1", "--port", "8000"])
        replace_args = parser.parse_args(["api", "--replace-existing"])
        worker_args = parser.parse_args(["worker", "--poll-interval", "3", "--max-concurrent-jobs", "2", "--max-optimization-workers", "4"])

        self.assertEqual(init_args.command, "init-db")
        self.assertEqual(check_db_args.command, "check-db")
        self.assertTrue(check_db_args.json)
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

        with patch("strategy_studio.web.app.fetch_market_data_stats", return_value={"instrument_count": 2, "total_bars": 10, "by_interval": [], "coverages": [], "recent_sync_runs": []}):
            health_response = client.get("/health")
            stats_response = client.get("/api/market-data/stats")

        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["status"], "ok")
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.json()["instrument_count"], 2)

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
        self.assertEqual(processes_response.json()[0]["service_name"], "api")
        self.assertEqual(logs_response.json()["lines"], ["api started"])
        mock_status.assert_called_once()
        mock_processes.assert_called_once()
        mock_logs.assert_called_once_with(service="api", limit=10)

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
            patch("strategy_studio.services.sync.list_instruments", return_value=[]),
            patch("strategy_studio.services.sync.create_sync_run", return_value=run),
            patch("strategy_studio.services.sync.create_sync_run_item", return_value=run_item),
            patch("strategy_studio.services.sync.create_data_ingestion_job", return_value=ingestion_job),
            patch("strategy_studio.services.sync.create_data_ingestion_job_item", return_value=ingestion_item),
            patch("strategy_studio.services.sync.resolve_symbol_spec", return_value=SimpleNamespace(name="XIAOMI - W")),
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
