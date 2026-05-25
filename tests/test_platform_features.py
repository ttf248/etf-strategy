from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from etf_strategy.cli import build_parser
from etf_strategy.platform_cli import handle_api
from etf_strategy.services.market_data import infer_interval_from_data_path
from etf_strategy.services.templates import build_seed_templates, normalize_parameter_space, resolve_backtest_request_payload
from etf_strategy.web.app import create_app


class PlatformFeatureTests(unittest.TestCase):
    """覆盖平台化新增命令和 API 基础契约。"""

    def test_cli_registers_platform_commands(self) -> None:
        parser = build_parser()

        init_args = parser.parse_args(["init-db"])
        import_args = parser.parse_args(["import-csv", "--source-dir", "data/processed"])
        api_args = parser.parse_args(["api", "--host", "127.0.0.1", "--port", "8000"])
        replace_args = parser.parse_args(["api", "--replace-existing"])

        self.assertEqual(init_args.command, "init-db")
        self.assertEqual(import_args.command, "import-csv")
        self.assertEqual(import_args.source_dir, "data/processed")
        self.assertEqual(api_args.command, "api")
        self.assertEqual(api_args.host, "127.0.0.1")
        self.assertEqual(api_args.port, 8000)
        self.assertTrue(replace_args.replace_existing)
        self.assertEqual(parser.parse_args(["scheduler"]).command, "scheduler")

    def test_infer_interval_from_data_path_supports_daily_alias(self) -> None:
        self.assertEqual(infer_interval_from_data_path("data/processed/1810_hk_daily.csv"), "1d")
        self.assertEqual(infer_interval_from_data_path("data/processed/1810_hk_15m.csv"), "15m")
        self.assertIsNone(infer_interval_from_data_path("data/processed/xiaomi_test.csv"))

    def test_web_api_health_and_stats(self) -> None:
        app = create_app()
        client = TestClient(app)

        with patch("etf_strategy.web.app.fetch_market_data_stats", return_value={"instrument_count": 2, "total_bars": 10, "by_interval": [], "coverages": [], "recent_sync_runs": []}):
            health_response = client.get("/health")
            stats_response = client.get("/api/market-data/stats")

        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["status"], "ok")
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.json()["instrument_count"], 2)

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
            patch("etf_strategy.web.app.list_strategy_templates", return_value=[template_payload]) as mock_list,
            patch("etf_strategy.web.app.create_strategy_template_entry", return_value=template_payload) as mock_create,
            patch("etf_strategy.web.app.update_strategy_template_entry", return_value={**template_payload, "template_name": "已更新模板"}) as mock_update,
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
            if module_name == "etf_strategy.db.settings":
                return SimpleNamespace(load_platform_settings=lambda: SimpleNamespace(api_host="127.0.0.1", api_port=8000))
            if module_name == "etf_strategy.web.app":
                return SimpleNamespace(create_app=lambda: object())
            raise AssertionError(f"unexpected import: {module_name}")

        with patch("etf_strategy.platform_cli.importlib.import_module", side_effect=fake_import):
            with self.assertRaisesRegex(RuntimeError, "python -m pip install -r requirements.txt"):
                handle_api(args)

    def test_handle_api_reports_existing_api_port_conflict_cleanly(self) -> None:
        args = SimpleNamespace(host="127.0.0.1", port=8000)

        def fake_import(module_name: str, command_name: str):
            if module_name == "uvicorn":
                return SimpleNamespace(run=lambda *args, **kwargs: self.fail("端口已占用时不应继续启动 uvicorn"))
            if module_name == "etf_strategy.db.settings":
                return SimpleNamespace(load_platform_settings=lambda: SimpleNamespace(api_host="127.0.0.1", api_port=8000))
            if module_name == "etf_strategy.web.app":
                return SimpleNamespace(create_app=lambda: object())
            raise AssertionError(f"unexpected import: {module_name} ({command_name})")

        with (
            patch("etf_strategy.platform_cli._import_platform_module", side_effect=fake_import),
            patch("etf_strategy.platform_cli._is_tcp_port_in_use", return_value=True),
            patch("etf_strategy.platform_cli._probe_existing_platform_api", return_value=True),
            patch("etf_strategy.platform_cli._describe_windows_listener", return_value="PID=29876 进程名=python.exe"),
        ):
            with self.assertRaisesRegex(RuntimeError, "已经有本项目 API 在运行"):
                handle_api(args)

    def test_handle_api_replaces_existing_project_api_when_requested(self) -> None:
        args = SimpleNamespace(host="127.0.0.1", port=8000, replace_existing=True)
        run_calls = []

        def fake_import(module_name: str, command_name: str):
            if module_name == "uvicorn":
                return SimpleNamespace(run=lambda *args, **kwargs: run_calls.append(kwargs))
            if module_name == "etf_strategy.db.settings":
                return SimpleNamespace(load_platform_settings=lambda: SimpleNamespace(api_host="127.0.0.1", api_port=8000))
            if module_name == "etf_strategy.web.app":
                return SimpleNamespace(create_app=lambda: object())
            raise AssertionError(f"unexpected import: {module_name} ({command_name})")

        with (
            patch("etf_strategy.platform_cli._import_platform_module", side_effect=fake_import),
            patch("etf_strategy.platform_cli._is_tcp_port_in_use", return_value=True),
            patch("etf_strategy.platform_cli._replace_existing_platform_api", return_value=True),
            patch("builtins.print"),
        ):
            handle_api(args)

        self.assertEqual(len(run_calls), 1)
        self.assertEqual(run_calls[0]["host"], "127.0.0.1")
        self.assertEqual(run_calls[0]["port"], 8000)


class StrategyTemplateServiceTests(unittest.TestCase):
    def test_normalize_parameter_space_for_grid(self) -> None:
        payload = normalize_parameter_space(
            "grid",
            {"spacings": [0.01, "0.02"], "grid_counts": [4, "5"], "take_profits": [0.01, "0.03"]},
            "15m",
        )

        self.assertEqual(payload, {"spacings": [0.01, 0.02], "grid_counts": [4, 5], "take_profits": [0.01, 0.03]})

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

        with patch("etf_strategy.services.templates.get_strategy_template", return_value=template):
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


if __name__ == "__main__":
    unittest.main()
