from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from strategy_studio.data.tushare import (
    build_corporate_action_records,
    load_tushare_client_settings,
    symbol_to_ts_code,
    ts_code_to_instrument_symbol,
    ts_code_to_market,
)


class TushareDataTests(unittest.TestCase):
    def test_symbol_conversion_between_tdx_and_tushare_formats(self) -> None:
        self.assertEqual(symbol_to_ts_code("sh600000"), "600000.SH")
        self.assertEqual(symbol_to_ts_code("000001.sz"), "000001.SZ")
        self.assertEqual(ts_code_to_instrument_symbol("600000.SH"), "SH600000")
        self.assertEqual(ts_code_to_market("000001.SZ"), "SZ")

    def test_build_corporate_action_records_only_keeps_rows_with_ex_date(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "ts_code": "600000.SH",
                    "end_date": "20231231",
                    "ann_date": "20240101",
                    "div_proc": "实施",
                    "stk_div": "0",
                    "stk_bo_rate": "0.1",
                    "stk_co_rate": "0.2",
                    "cash_div": "0.8",
                    "cash_div_tax": "1.0",
                    "record_date": "20240104",
                    "ex_date": "20240105",
                    "pay_date": "20240108",
                    "imp_ann_date": "20240103",
                },
                {
                    "ts_code": "600000.SH",
                    "end_date": "20241231",
                    "ann_date": "20250101",
                    "div_proc": "预案",
                    "stk_div": "0",
                    "stk_bo_rate": "0",
                    "stk_co_rate": "0",
                    "cash_div": "2.0",
                    "cash_div_tax": "2.0",
                    "record_date": "",
                    "ex_date": "",
                    "pay_date": "",
                    "imp_ann_date": "",
                },
            ]
        )

        records = build_corporate_action_records(frame)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source_symbol"], "600000.SH")
        self.assertEqual(records[0]["cash_dividend"], 1.0)
        self.assertEqual(records[0]["stock_bonus_ratio"], 0.1)
        self.assertEqual(records[0]["stock_conversion_ratio"], 0.2)
        self.assertEqual(records[0]["status"], "implemented")

    def test_load_tushare_client_settings_reads_nested_yaml_block(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.local.yaml"
            config_path.write_text(
                "tushare:\n"
                "  token: \"demo-token\"\n"
                "  rate_limit_per_minute: 450\n"
                "  timeout_seconds: 12\n"
                "  retries: 5\n",
                encoding="utf-8",
            )
            fake_settings = type(
                "Settings",
                (),
                {
                    "tushare_config_path": str(config_path),
                    "tushare_token": "",
                    "tushare_rate_limit_per_minute": 90,
                    "tushare_timeout_seconds": 15.0,
                    "tushare_retries": 3,
                },
            )()

            with patch("strategy_studio.data.tushare.load_platform_settings", return_value=fake_settings):
                settings = load_tushare_client_settings()

        self.assertEqual(settings.token, "demo-token")
        self.assertEqual(settings.rate_limit_per_minute, 450)
        self.assertEqual(settings.timeout_seconds, 12.0)
        self.assertEqual(settings.retries, 5)


if __name__ == "__main__":
    unittest.main()
