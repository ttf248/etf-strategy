import unittest
from unittest.mock import ANY, Mock, patch

import pandas as pd

from etf_strategy.cli import build_parser, handle_download, handle_run
from etf_strategy.config import DEFAULT_DATA_PATH, DEFAULT_OUTPUT_DIR
from etf_strategy.data.market_rules import infer_symbol_from_data_path, resolve_lot_size_rule
from etf_strategy.settings import build_execution_config
from etf_strategy.strategy.grid import (
    build_sample_window,
    build_walk_forward_windows,
    optimize_grid_parameters,
    run_grid_backtest,
    split_intraday_in_sample_and_validation,
    split_in_sample_and_validation,
)


def build_test_frame(close_prices: list[float], start: str = "2025-09-01") -> pd.DataFrame:
    """构造最小可回测 OHLCV 测试样本。"""
    dates = pd.date_range(start=start, periods=len(close_prices), freq="B")
    frame = pd.DataFrame(
        {
            "Open": close_prices,
            "High": [price * 1.01 for price in close_prices],
            "Low": [price * 0.99 for price in close_prices],
            "Close": close_prices,
            "Volume": [1000000] * len(close_prices),
        },
        index=dates,
    )
    frame.index.name = "Date"
    return frame


class GridStrategyTests(unittest.TestCase):
    """覆盖 CLI 解析、样本切分和固定股数网格的核心口径。"""

    def test_download_parser_reads_intraday_parameters(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "download",
                "--symbol",
                "1810.HK",
                "--start",
                "2026-04-01",
                "--end",
                "2026-05-21",
                "--interval",
                "15m",
                "--period",
                "60d",
            ]
        )

        self.assertEqual(args.command, "download")
        self.assertEqual(args.symbol, "1810.HK")
        self.assertEqual(args.interval, "15m")
        self.assertEqual(args.period, "60d")
        self.assertEqual(args.period, "60d")
        self.assertIsNone(args.output)

    def test_run_parser_reads_intraday_parameters(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "run",
                "--symbol",
                "1810.HK",
                "--interval",
                "15m",
                "--period",
                "60d",
            ]
        )

        self.assertEqual(args.command, "run")
        self.assertEqual(args.interval, "15m")
        self.assertEqual(args.period, "60d")
        self.assertIsNone(args.start)
        self.assertIsNone(args.end)
        self.assertEqual(args.execution_profile, "realistic")

    def test_handle_download_allows_daily_without_range_and_merges_existing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["download", "--symbol", "1810.HK"])
        bars = pd.DataFrame(
            {
                "Date": ["2026-05-20"],
                "Open": [10.0],
                "High": [10.2],
                "Low": [9.8],
                "Close": [10.1],
                "Volume": [100],
            }
        )

        with (
            patch("etf_strategy.cli.download_price_bars", return_value=bars) as mock_download,
            patch("etf_strategy.cli.save_price_bars", return_value=DEFAULT_DATA_PATH) as mock_save,
            patch("builtins.print"),
        ):
            result = handle_download(args)

        self.assertEqual(result, 0)
        mock_download.assert_called_once_with(
            symbol="1810.HK",
            interval="1d",
            start_date=None,
            end_date=None,
            period=None,
            proxy=None,
        )
        mock_save.assert_called_once_with(bars, DEFAULT_DATA_PATH, interval="1d", merge_with_existing=True)

    def test_handle_run_allows_daily_without_range_and_merges_before_workflow(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--symbol", "1810.HK"])
        bars = pd.DataFrame(
            {
                "Date": ["2026-05-20"],
                "Open": [10.0],
                "High": [10.2],
                "Low": [9.8],
                "Close": [10.1],
                "Volume": [100],
            }
        )
        workflow_result = {
            "combined_summary_path": "outputs/combined_summary.csv",
            "optimization": {
                "best_run": {
                    "summary": {
                        "GridSpacingPct": 7.0,
                        "GridCount": 5,
                        "TakeProfitPct": 3.0,
                    }
                }
            },
            "validation": {
                "run": {
                    "summary": {
                        "ReturnPct": 1.2,
                        "MaxDrawdownPct": 4.5,
                        "CostReductionPct": 2.3,
                    }
                }
            },
        }

        with (
            patch("etf_strategy.cli.download_price_bars", return_value=bars) as mock_download,
            patch("etf_strategy.cli.save_price_bars", return_value=DEFAULT_DATA_PATH) as mock_save,
            patch("etf_strategy.cli.run_full_workflow", return_value=workflow_result) as mock_workflow,
            patch("etf_strategy.cli.build_report_markdown", return_value="reports/1810_hk_grid_report.md"),
            patch("builtins.print"),
        ):
            result = handle_run(args)

        self.assertEqual(result, 0)
        mock_download.assert_called_once_with(
            symbol="1810.HK",
            interval="1d",
            start_date=None,
            end_date=None,
            period=None,
            proxy=None,
        )
        mock_save.assert_called_once_with(bars, DEFAULT_DATA_PATH, interval="1d", merge_with_existing=True)
        mock_workflow.assert_called_once_with(
            data_path=DEFAULT_DATA_PATH,
            symbol="1810.HK",
            output_dir=DEFAULT_OUTPUT_DIR,
            validation_start="2026-01-01",
            lookback_days=120,
            execution_config=ANY,
            wf_window_count=3,
            wf_min_window_size=20,
        )
        execution_config = mock_workflow.call_args.kwargs["execution_config"]
        self.assertEqual(execution_config.profile, "realistic")

    def test_backtest_parser_reads_grid_parameters(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "backtest",
                "--data",
                "data/processed/1810_hk_daily.csv",
                "--symbol",
                "1810.HK",
                "--grid-spacing",
                "0.06",
                "--grid-count",
                "7",
                "--take-profit",
                "0.03",
            ]
        )

        self.assertEqual(args.command, "backtest")
        self.assertEqual(args.data, "data/processed/1810_hk_daily.csv")
        self.assertEqual(args.symbol, "1810.HK")
        self.assertAlmostEqual(args.grid_spacing, 0.06)
        self.assertEqual(args.grid_count, 7)
        self.assertAlmostEqual(args.take_profit, 0.03)
        self.assertEqual(args.validation_start, "2026-01-01")
        self.assertEqual(args.lookback_days, 120)
        self.assertEqual(args.execution_profile, "realistic")
        self.assertIsNone(args.commission_bps)
        self.assertIsNone(args.slippage_bps)

    def test_infer_symbol_from_data_path(self) -> None:
        self.assertEqual(infer_symbol_from_data_path("data/processed/1810_hk_daily.csv"), "1810.HK")
        self.assertEqual(infer_symbol_from_data_path("data/processed/spy_1d.csv"), "SPY")
        self.assertEqual(infer_symbol_from_data_path("data/processed/brk-b_15m.csv"), "BRK-B")

    def test_resolve_lot_size_rule_for_us_symbol(self) -> None:
        rule = resolve_lot_size_rule("SPY")
        self.assertEqual(rule.market, "US")
        self.assertEqual(rule.lot_size, 1)

    @patch("etf_strategy.data.market_rules.requests.get")
    def test_resolve_lot_size_rule_for_hk_symbol(self, mock_get: Mock) -> None:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = """
        <td class="c3">Lot Size</td>
        <td class="c4">200</td>
        """
        mock_get.return_value = mock_response

        rule = resolve_lot_size_rule("1810.HK")

        self.assertEqual(rule.market, "HK")
        self.assertEqual(rule.lot_size, 200)
        self.assertIn("AASTOCKS", rule.source)

    def test_resolve_lot_size_rule_rejects_unsupported_market(self) -> None:
        with self.assertRaisesRegex(ValueError, "暂不支持"):
            resolve_lot_size_rule("7203.T")

    def test_build_sample_window_uses_sample_start_as_entry(self) -> None:
        prices = [20.0, 21.2, 22.5, 21.8, 20.9, 20.1, 19.5]
        frame = build_test_frame(prices, start="2025-11-03")

        window = build_sample_window(
            frame,
            validation_start="2025-12-01",
            lookback_days=30,
        )

        self.assertEqual(window.peak_date, "2025-11-05")
        self.assertEqual(window.entry_date, "2025-11-03")
        self.assertEqual(window.sample_start, "2025-11-03")
        self.assertEqual(window.validation_start, "2025-12-01")

    def test_split_in_sample_and_validation_no_longer_requires_drawdown_trigger(self) -> None:
        prices = [20.0, 20.5, 21.0, 21.3, 21.6, 21.9, 22.1]
        frame = build_test_frame(prices, start="2025-11-03")

        window, in_sample, validation = split_in_sample_and_validation(
            frame,
            validation_start="2025-11-10",
            lookback_days=30,
        )

        self.assertEqual(window.entry_date, "2025-11-03")
        self.assertFalse(in_sample.empty)
        self.assertFalse(validation.empty)

    def test_run_grid_backtest_enters_on_first_bar(self) -> None:
        # 这组价格同时覆盖：样本起点建仓、下跌补仓、反弹止盈三类关键路径。
        prices = [20.0, 19.0, 18.0, 17.0, 18.2, 19.1, 20.0, 18.0, 19.3, 20.2]
        frame = build_test_frame(prices, start="2025-10-01")

        result = run_grid_backtest(
            data=frame,
            scenario_name="unit_test",
            grid_spacing_pct=0.05,
            grid_count=3,
            take_profit_pct=0.05,
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            total_capital=200000,
        )

        summary = result["summary"]
        events = result["events"]

        self.assertTrue(summary["TriggeredEntry"])
        self.assertEqual(summary["EntryDate"], "2025-10-01")
        self.assertAlmostEqual(summary["EntryPrice"], 20.0)
        self.assertEqual(summary["LotSize"], 200)
        self.assertEqual(summary["BaseUnits"], 5000)
        self.assertEqual(summary["GridUnitsPerLevel"], 1600)
        self.assertFalse(events.empty)
        self.assertTrue({"base_buy", "grid_buy"}.issubset(set(events["EventType"])))
        self.assertEqual(events.iloc[0]["Date"], "2025-10-01")
        self.assertEqual(events.iloc[0]["EventType"], "base_buy")
        self.assertTrue((events["Units"] % 200 == 0).all())

    def test_run_grid_backtest_realistic_profile_records_costs(self) -> None:
        prices = [20.0, 19.0, 18.0, 19.2, 20.0]
        frame = build_test_frame(prices, start="2025-10-01")

        result = run_grid_backtest(
            data=frame,
            scenario_name="realistic_unit_test",
            grid_spacing_pct=0.05,
            grid_count=3,
            take_profit_pct=0.05,
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            total_capital=200000,
            execution_config=build_execution_config(
                "realistic",
                commission_bps=10,
                slippage_bps=5,
                max_position_ratio=1.0,
                stop_loss_pct=0.0,
                cooldown_bars=0,
            ),
        )

        summary = result["summary"]
        events = result["events"]

        self.assertEqual(summary["ExecutionProfile"], "realistic")
        self.assertGreater(summary["TransactionCost"], 0)
        self.assertGreater(summary["SlippageCost"], 0)
        self.assertLess(summary["BaseUnits"], 5000)
        self.assertIn("ExecutionPrice", events.columns)
        self.assertIn("BaseOnlyReturnPct", summary)
        self.assertIn("BuyHoldReturnPct", summary)

    def test_run_grid_backtest_realistic_profile_records_stop_loss_event(self) -> None:
        prices = [20.0, 18.0, 17.0, 16.0]
        frame = build_test_frame(prices, start="2025-10-01")

        result = run_grid_backtest(
            data=frame,
            scenario_name="risk_unit_test",
            grid_spacing_pct=0.05,
            grid_count=3,
            take_profit_pct=0.05,
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            total_capital=200000,
            execution_config=build_execution_config(
                "realistic",
                commission_bps=0,
                slippage_bps=0,
                max_position_ratio=1.0,
                stop_loss_pct=0.05,
                cooldown_bars=2,
            ),
        )

        summary = result["summary"]
        events = result["events"]

        self.assertGreaterEqual(summary["StopLossEvents"], 1)
        self.assertGreaterEqual(summary["RiskSkipEvents"], 1)
        self.assertIn("risk_stop_loss", set(events["EventType"]))

    def test_split_intraday_in_sample_and_validation(self) -> None:
        dates = pd.date_range(start="2026-04-01 09:30:00", periods=40, freq="15min")
        prices = [30.0, 31.0, 32.0, 33.0, 34.0, 35.0, 34.0, 33.0, 32.0, 31.0] + [30.0] * 30
        frame = pd.DataFrame(
            {
                "Open": prices,
                "High": [price * 1.01 for price in prices],
                "Low": [price * 0.99 for price in prices],
                "Close": prices,
                "Volume": [1000] * len(prices),
            },
            index=dates,
        )
        frame.index.name = "Date"

        window, in_sample, validation = split_intraday_in_sample_and_validation(frame, validation_ratio=0.25)

        self.assertEqual(window.peak_date, "2026-04-01 10:45:00")
        self.assertEqual(window.entry_date, "2026-04-01 09:30:00")
        self.assertFalse(in_sample.empty)
        self.assertFalse(validation.empty)

    def test_build_walk_forward_windows_splits_data_in_time_order(self) -> None:
        frame = build_test_frame([20.0 + index for index in range(60)], start="2025-01-01")

        windows = build_walk_forward_windows(frame, window_count=3, min_window_size=15)

        self.assertEqual(len(windows), 3)
        self.assertEqual(len(windows[0]), 20)
        self.assertEqual(len(windows[1]), 20)
        self.assertEqual(len(windows[2]), 20)
        self.assertLess(windows[0].index.max(), windows[1].index.min())
        self.assertLess(windows[1].index.max(), windows[2].index.min())

    @patch("etf_strategy.strategy.grid.run_grid_backtest")
    def test_optimize_grid_parameters_prefers_robust_candidate(self, mock_run_grid_backtest: Mock) -> None:
        frame = build_test_frame([20.0 + index * 0.1 for index in range(60)], start="2025-01-01")
        candidate_metrics = {
            (0.03, 4, 0.03): {
                "full": {"Score": 8.0, "ReturnPct": 4.0, "MaxDrawdownPct": 6.0, "CostReductionPct": 3.0},
                "wf": [
                    {"Score": 6.0, "ReturnPct": 4.0, "MaxDrawdownPct": 5.0, "CostReductionPct": 2.5},
                    {"Score": 5.0, "ReturnPct": 3.0, "MaxDrawdownPct": 5.5, "CostReductionPct": 2.0},
                    {"Score": 4.0, "ReturnPct": 2.0, "MaxDrawdownPct": 6.0, "CostReductionPct": 1.5},
                ],
            },
            (0.04, 4, 0.03): {
                "full": {"Score": 10.0, "ReturnPct": 7.0, "MaxDrawdownPct": 7.0, "CostReductionPct": 3.5},
                "wf": [
                    {"Score": 12.0, "ReturnPct": 10.0, "MaxDrawdownPct": 4.0, "CostReductionPct": 4.0},
                    {"Score": -1.0, "ReturnPct": -5.0, "MaxDrawdownPct": 11.0, "CostReductionPct": 1.0},
                    {"Score": -2.0, "ReturnPct": -6.0, "MaxDrawdownPct": 12.0, "CostReductionPct": 0.5},
                ],
            },
        }

        def fake_run_grid_backtest(*args: object, **kwargs: object) -> dict[str, object]:
            key = (
                round(float(kwargs["grid_spacing_pct"]), 2),
                int(kwargs["grid_count"]),
                round(float(kwargs["take_profit_pct"]), 2),
            )
            scenario_name = str(kwargs["scenario_name"])
            metrics_group = candidate_metrics[key]
            if "_wf_" in scenario_name:
                window_index = int(scenario_name.rsplit("_wf_", maxsplit=1)[1]) - 1
                metrics = metrics_group["wf"][window_index]
            else:
                metrics = metrics_group["full"]
            return {
                "summary": {
                    "GridSpacingPct": float(kwargs["grid_spacing_pct"]) * 100,
                    "GridCount": int(kwargs["grid_count"]),
                    "TakeProfitPct": float(kwargs["take_profit_pct"]) * 100,
                    "Score": metrics["Score"],
                    "ReturnPct": metrics["ReturnPct"],
                    "MaxDrawdownPct": metrics["MaxDrawdownPct"],
                    "CostReductionPct": metrics["CostReductionPct"],
                }
            }

        mock_run_grid_backtest.side_effect = fake_run_grid_backtest

        results, best_run = optimize_grid_parameters(
            data=frame,
            spacings=[0.03, 0.04],
            grid_counts=[4],
            take_profits=[0.03],
            scenario_name="in_sample",
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
        )

        self.assertEqual(results.iloc[0]["GridSpacingPct"], 3.0)
        self.assertIn("RobustScore", results.columns)
        self.assertIn("WalkForwardScoreMin", results.columns)
        self.assertIn("WalkForwardPositiveWindowRatio", results.columns)
        self.assertAlmostEqual(float(best_run["summary"]["GridSpacingPct"]), 3.0)


if __name__ == "__main__":
    unittest.main()
