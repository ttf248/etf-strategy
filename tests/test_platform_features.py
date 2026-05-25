from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from etf_strategy.cli import build_parser
from etf_strategy.services.market_data import infer_interval_from_data_path
from etf_strategy.web.app import create_app


class PlatformFeatureTests(unittest.TestCase):
    """覆盖平台化新增命令和 API 基础契约。"""

    def test_cli_registers_platform_commands(self) -> None:
        parser = build_parser()

        init_args = parser.parse_args(["init-db"])
        import_args = parser.parse_args(["import-csv", "--source-dir", "data/processed"])
        api_args = parser.parse_args(["api", "--host", "127.0.0.1", "--port", "8000"])

        self.assertEqual(init_args.command, "init-db")
        self.assertEqual(import_args.command, "import-csv")
        self.assertEqual(import_args.source_dir, "data/processed")
        self.assertEqual(api_args.command, "api")
        self.assertEqual(api_args.host, "127.0.0.1")
        self.assertEqual(api_args.port, 8000)

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


if __name__ == "__main__":
    unittest.main()

