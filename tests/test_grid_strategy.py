import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pandas as pd

from etf_strategy.cli import build_parser, handle_batch, handle_download, handle_run
from etf_strategy.config import DEFAULT_DATA_PATH, DEFAULT_MINUTE_DATA_PATH, DEFAULT_MINUTE_OUTPUT_DIR
from etf_strategy.data.market_rules import infer_symbol_from_data_path, resolve_lot_size_rule
from etf_strategy.reporting import build_report_index_entry, load_report_registry, register_report_index_entries
from etf_strategy.settings import build_execution_config
from etf_strategy.strategy.grid import (
    build_sample_window,
    build_walk_forward_windows,
    optimize_grid_parameters,
    run_grid_backtest,
    split_intraday_in_sample_and_validation,
    split_in_sample_and_validation,
)
from etf_strategy.strategy.rebound import run_rebound_backtest


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

    def test_backtest_parser_reads_cash_grid_policy_arguments(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "backtest",
                "--data",
                "data/processed/1810_hk_daily.csv",
                "--grid-spacing",
                "0.05",
                "--grid-count",
                "3",
                "--take-profit",
                "0.04",
                "--grid-mode",
                "cash",
                "--left-side-policy",
                "force_exit",
                "--force-exit-loss-pct",
                "0.03",
            ]
        )

        execution = build_execution_config(
            args.execution_profile,
            grid_mode=args.grid_mode,
            left_side_policy=args.left_side_policy,
            force_exit_loss_pct=args.force_exit_loss_pct,
        )

        self.assertEqual(args.grid_mode, "cash")
        self.assertEqual(args.left_side_policy, "force_exit")
        self.assertAlmostEqual(args.force_exit_loss_pct, 0.03)
        self.assertEqual(execution.grid_mode, "cash")
        self.assertEqual(execution.left_side_policy, "force_exit")
        self.assertAlmostEqual(execution.force_exit_loss_pct, 0.03)

    def test_report_parser_reads_strategy_compare_arguments(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "report",
                "--data",
                "data/processed/1810_hk_15m.csv",
                "--interval",
                "15m",
                "--strategy",
                "minute_rebound_with_fade_filter",
                "--compare-strategies",
            ]
        )

        self.assertEqual(args.strategy, "minute_rebound_with_fade_filter")
        self.assertTrue(args.compare_strategies)

    def test_handle_download_defaults_to_intraday_and_merges_existing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["download", "--symbol", "1810.HK", "--proxy", "http://127.0.0.1:7897"])
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
            patch("etf_strategy.cli.save_price_bars", return_value=DEFAULT_MINUTE_DATA_PATH) as mock_save,
            patch("builtins.print"),
        ):
            result = handle_download(args)

        self.assertEqual(result, 0)
        mock_download.assert_called_once_with(
            symbol="1810.HK",
            interval="15m",
            start_date=None,
            end_date=None,
            period="60d",
            proxy="http://127.0.0.1:7897",
        )
        mock_save.assert_called_once_with(bars, DEFAULT_MINUTE_DATA_PATH, interval="15m", merge_with_existing=True)

    def test_handle_download_allows_explicit_daily_without_range_and_merges_existing(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["download", "--symbol", "1810.HK", "--interval", "1d", "--proxy", "http://127.0.0.1:7897"]
        )
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
            proxy="http://127.0.0.1:7897",
        )
        mock_save.assert_called_once_with(bars, DEFAULT_DATA_PATH, interval="1d", merge_with_existing=True)

    def test_handle_run_defaults_to_intraday_and_merges_before_workflow(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--symbol", "1810.HK", "--proxy", "http://127.0.0.1:7897"])
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
            patch("etf_strategy.cli.save_price_bars", return_value=DEFAULT_MINUTE_DATA_PATH) as mock_save,
            patch("etf_strategy.cli.run_minute_full_workflow", return_value=workflow_result) as mock_workflow,
            patch(
                "etf_strategy.cli.build_minute_report_markdown",
                return_value="reports/1810_hk/minute/1810_hk_15m_grid_report.md",
            ),
            patch("builtins.print"),
        ):
            result = handle_run(args)

        self.assertEqual(result, 0)
        mock_download.assert_called_once_with(
            symbol="1810.HK",
            interval="15m",
            start_date=None,
            end_date=None,
            period="60d",
            proxy="http://127.0.0.1:7897",
        )
        mock_save.assert_called_once_with(bars, DEFAULT_MINUTE_DATA_PATH, interval="15m", merge_with_existing=True)
        mock_workflow.assert_called_once_with(
            data_path=DEFAULT_MINUTE_DATA_PATH,
            symbol="1810.HK",
            output_dir=str(DEFAULT_MINUTE_OUTPUT_DIR),
            validation_ratio=0.25,
            strategy_kind="grid",
            execution_config=ANY,
            wf_window_count=3,
            wf_min_window_size=20,
            jobs=1,
            cache_dir=None,
        )
        execution_config = mock_workflow.call_args.kwargs["execution_config"]
        self.assertEqual(execution_config.profile, "realistic")

    def test_batch_parser_reads_symbols_and_parallel_options(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "batch",
                "--symbols",
                "1810.HK,SPY",
                "--interval",
                "1d",
                "--jobs",
                "auto",
                "--cache-dir",
                "outputs/cache",
            ]
        )

        self.assertEqual(args.command, "batch")
        self.assertEqual(args.symbols, "1810.HK,SPY")
        self.assertEqual(args.jobs, "auto")
        self.assertEqual(args.cache_dir, "outputs/cache")
        self.assertEqual(args.execution_profile, "realistic")

    def test_batch_parser_reads_symbol_set_and_defaults_to_intraday(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["batch", "--symbol-set", "hstech_plus_513050"])

        self.assertEqual(args.command, "batch")
        self.assertEqual(args.symbol_set, "hstech_plus_513050")
        self.assertIsNone(args.symbols)
        self.assertEqual(args.interval, "15m")
        self.assertEqual(args.period, "60d")

    def test_batch_parser_reads_compare_strategy_arguments(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "batch",
                "--symbols",
                "1810.HK",
                "--interval",
                "15m",
                "--strategy",
                "minute_rebound",
                "--compare-strategies",
            ]
        )

        self.assertEqual(args.strategy, "minute_rebound")
        self.assertTrue(args.compare_strategies)

    def test_handle_batch_writes_summary_for_existing_data(self) -> None:
        parser = build_parser()
        workflow_result = {
            "combined_summary_path": "outputs/batch/1810_hk/combined_summary.csv",
            "optimization": {
                "best_run": {
                    "summary": {
                        "GridSpacingPct": 4.0,
                        "GridCount": 6,
                        "TakeProfitPct": 3.0,
                        "ReturnPct": -1.0,
                        "NetReturnPct": -1.2,
                    }
                }
            },
            "validation": {
                "run": {
                    "summary": {
                        "ReturnPct": -2.0,
                        "NetReturnPct": -2.3,
                        "MaxDrawdownPct": 5.0,
                    }
                }
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            args = parser.parse_args(
                [
                    "batch",
                    "--symbols",
                    "1810.HK",
                    "--interval",
                    "1d",
                    "--output-dir",
                    str(Path(temp_dir) / "out"),
                    "--report-dir",
                    str(Path(temp_dir) / "reports"),
                ]
            )
            with (
                patch("etf_strategy.cli.run_full_workflow", return_value=workflow_result) as mock_workflow,
                patch(
                    "etf_strategy.cli.build_report_markdown",
                    return_value=Path(temp_dir) / "reports" / "1810_hk" / "daily" / "1810_hk_grid_report.md",
                ),
                patch("builtins.print"),
            ):
                result = handle_batch(args)

            summary_path = Path(temp_dir) / "out" / "batch_summary.csv"
            summary = pd.read_csv(summary_path, encoding="utf-8-sig")
            index_path = Path(temp_dir) / "reports" / "report_index.md"
            index_content = index_path.read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertEqual(summary.iloc[0]["Status"], "ok")
        self.assertIn("1810.HK", index_content)
        self.assertIn("| grid | 网格 |", index_content)
        mock_workflow.assert_called_once()
        self.assertEqual(mock_workflow.call_args.kwargs["jobs"], 1)
        self.assertEqual(mock_workflow.call_args.kwargs["execution_config"].profile, "realistic")

    def test_handle_batch_compare_updates_unified_report_index(self) -> None:
        parser = build_parser()
        comparison_results = {
            "grid": {
                "optimization": {
                    "best_run": {
                        "summary": {
                            "StrategyKind": "grid",
                            "GridSpacingPct": 4.0,
                            "GridCount": 6,
                            "TakeProfitPct": 3.0,
                            "ReturnPct": -1.0,
                            "NetReturnPct": -1.2,
                        }
                    }
                },
                "validation": {
                    "run": {
                        "summary": {
                            "StrategyKind": "grid",
                            "ReturnPct": -2.0,
                            "NetReturnPct": -2.3,
                            "MaxDrawdownPct": 5.0,
                        }
                    }
                },
            },
            "minute_rebound": {
                "optimization": {
                    "best_run": {
                        "summary": {
                            "StrategyKind": "minute_rebound",
                            "GridSpacingPct": 0.0,
                            "GridCount": 0,
                            "TakeProfitPct": 0.0,
                            "ReturnPct": 1.0,
                            "NetReturnPct": 0.8,
                        }
                    }
                },
                "validation": {
                    "run": {
                        "summary": {
                            "StrategyKind": "minute_rebound",
                            "ReturnPct": 1.2,
                            "NetReturnPct": 1.1,
                            "MaxDrawdownPct": 2.5,
                        }
                    }
                },
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            args = parser.parse_args(
                [
                    "batch",
                    "--symbols",
                    "1810.HK",
                    "--interval",
                    "15m",
                    "--strategy",
                    "minute_rebound",
                    "--compare-strategies",
                    "--output-dir",
                    str(Path(temp_dir) / "out"),
                    "--report-dir",
                    str(Path(temp_dir) / "reports"),
                ]
            )
            with (
                patch("etf_strategy.cli._run_comparison_workflows", return_value=comparison_results),
                patch(
                    "etf_strategy.cli.build_strategy_comparison_report",
                    return_value=Path(temp_dir) / "reports" / "1810_hk" / "minute" / "1810_hk_15m_strategy_compare_report.md",
                ),
                patch("builtins.print"),
            ):
                result = handle_batch(args)

            index_path = Path(temp_dir) / "reports" / "report_index.md"
            index_content = index_path.read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertIn("1810.HK", index_content)
        self.assertIn("| compare | 多策略对比 |", index_content)
        self.assertIn("推荐 分钟急跌反抽", index_content)

    def test_register_report_index_entries_prefers_new_record_over_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_root = Path(temp_dir) / "reports"
            legacy_entry = build_report_index_entry(
                report_path=report_root / "1810_hk" / "minute" / "legacy_report.md",
                symbol="1810.HK",
                interval="15m",
                report_view="grid",
                strategy_kind="grid",
                strategy_name="网格",
                validation_return_pct=0.0,
                max_drawdown_pct=0.0,
                note="旧记录",
                generated_at="legacy",
                report_root=report_root,
            )
            current_entry = build_report_index_entry(
                report_path=report_root / "1810_hk" / "minute" / "current_report.md",
                symbol="1810.HK",
                interval="15m",
                report_view="grid",
                strategy_kind="grid",
                strategy_name="网格",
                validation_return_pct=1.5,
                max_drawdown_pct=2.0,
                note="新记录",
                generated_at="2026-05-22 04:50:17",
                report_root=report_root,
            )

            register_report_index_entries([legacy_entry], report_root=report_root)
            register_report_index_entries([current_entry], report_root=report_root)
            registry = load_report_registry(report_root=report_root)

        self.assertEqual(len(registry), 1)
        self.assertEqual(registry.iloc[0]["Note"], "新记录")
        self.assertEqual(registry.iloc[0]["ReportPath"], "1810_hk/minute/current_report.md")

    def test_handle_batch_stops_when_download_fails(self) -> None:
        parser = build_parser()

        with tempfile.TemporaryDirectory() as temp_dir:
            args = parser.parse_args(
                [
                    "batch",
                    "--symbols",
                    "1810.HK",
                    "--download",
                    "--proxy",
                    "http://127.0.0.1:7897",
                    "--output-dir",
                    str(Path(temp_dir) / "out"),
                    "--report-dir",
                    str(Path(temp_dir) / "reports"),
                ]
            )
            with (
                patch("etf_strategy.cli.download_price_bars", side_effect=ValueError("Yahoo 行情下载失败")) as mock_download,
                patch("etf_strategy.cli._write_failed_batch_report") as mock_failed_report,
            ):
                with self.assertRaisesRegex(ValueError, "Yahoo 行情下载失败"):
                    handle_batch(args)

        mock_download.assert_called_once()
        mock_failed_report.assert_not_called()

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
        self.assertEqual(infer_symbol_from_data_path("data/processed/513050_ss_15m.csv"), "513050.SS")
        self.assertEqual(infer_symbol_from_data_path("data/processed/spy_1d.csv"), "SPY")
        self.assertEqual(infer_symbol_from_data_path("data/processed/brk-b_15m.csv"), "BRK-B")

    def test_resolve_lot_size_rule_for_us_symbol(self) -> None:
        rule = resolve_lot_size_rule("SPY")
        self.assertEqual(rule.market, "US")
        self.assertEqual(rule.lot_size, 1)

    def test_resolve_lot_size_rule_for_cn_etf_symbol(self) -> None:
        rule = resolve_lot_size_rule("513050.SS")
        self.assertEqual(rule.market, "CN")
        self.assertEqual(rule.lot_size, 100)
        self.assertIn("100 股", rule.source)

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

    def test_run_grid_backtest_uses_cash_grid_without_first_bar_buy(self) -> None:
        # 这组价格同时覆盖：不初始买入、下跌开网格、反弹止盈、卖出后再进场。
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
        self.assertTrue(summary["TriggeredGridEntry"])
        self.assertEqual(summary["EntryDate"], "2025-10-01")
        self.assertAlmostEqual(summary["EntryPrice"], 20.0)
        self.assertEqual(summary["LotSize"], 200)
        self.assertEqual(summary["BaseUnits"], 0)
        self.assertEqual(summary["GridUnitsPerLevel"], 3200)
        self.assertEqual(summary["GridMode"], "cash")
        self.assertEqual(summary["RequestedLeftSidePolicy"], "both")
        self.assertIn("policy_results", result)
        self.assertFalse(events.empty)
        self.assertTrue({"grid_buy", "grid_sell"}.issubset(set(events["EventType"])))
        self.assertNotIn("base_buy", set(events["EventType"]))
        self.assertEqual(events.iloc[0]["Date"], "2025-10-02")
        self.assertEqual(events.iloc[0]["EventType"], "grid_buy")
        self.assertGreaterEqual(len(events[(events["EventType"] == "grid_buy") & (events["Level"] == 1)]), 2)
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
        self.assertEqual(summary["BaseUnits"], 0)
        self.assertIn("ExecutionPrice", events.columns)
        self.assertIn("CashIdleReturnPct", summary)
        self.assertIn("BuyHoldReturnPct", summary)

    def test_run_grid_backtest_force_exit_sells_open_grid_and_stops(self) -> None:
        prices = [20.0, 19.0, 18.0, 16.0, 15.0, 17.0]
        frame = build_test_frame(prices, start="2025-10-01")

        result = run_grid_backtest(
            data=frame,
            scenario_name="force_exit_unit_test",
            grid_spacing_pct=0.05,
            grid_count=3,
            take_profit_pct=0.05,
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            total_capital=200000,
            execution_config=build_execution_config(
                "research",
                left_side_policy="force_exit",
                force_exit_loss_pct=0.05,
            ),
        )

        summary = result["summary"]
        events = result["events"]

        self.assertTrue(summary["ForceExitTriggered"])
        self.assertGreaterEqual(summary["ForceExitEvents"], 1)
        self.assertEqual(summary["PositionUnits"], 0)
        self.assertIn("force_exit_sell", set(events["EventType"]))
        first_force_exit_index = events.index[events["EventType"] == "force_exit_sell"][0]
        after_force_exit = events.loc[first_force_exit_index + 1 :]
        self.assertNotIn("grid_buy", set(after_force_exit["EventType"]))

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

    def test_run_daily_rebound_backtest_generates_buy_and_sell(self) -> None:
        prices = [100.0, 99.0, 97.0, 94.0, 92.0, 95.0, 98.0, 101.0, 100.0, 99.0]
        frame = build_test_frame(prices, start="2025-01-01")

        result = run_rebound_backtest(
            data=frame,
            scenario_name="daily_rebound_unit_test",
            strategy_kind="daily_rebound",
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            params={
                "rsi_window": 3,
                "rsi_entry": 35.0,
                "ma_window": 3,
                "deviation_entry_pct": -2.0,
                "take_profit_pct": 3.0,
                "stop_loss_atr": 5.0,
                "max_hold_bars": 5,
            },
            execution_config=build_execution_config(
                "research",
                commission_bps=0,
                slippage_bps=0,
                max_position_ratio=0.8,
            ),
        )

        summary = result["summary"]
        events = result["events"]
        self.assertEqual(summary["StrategyKind"], "daily_rebound")
        self.assertTrue(summary["TriggeredEntry"])
        self.assertGreaterEqual(summary["ClosedTrades"], 1)
        self.assertIn("rebound_buy", set(events["EventType"]))
        self.assertTrue({"take_profit_sell", "max_hold_sell", "stop_loss_sell"}.intersection(set(events["EventType"])))

    def test_run_minute_rebound_fade_filter_blocks_entry(self) -> None:
        dates = pd.date_range(start="2026-04-01 09:30:00", periods=8, freq="15min")
        frame = pd.DataFrame(
            {
                "Open": [10.0, 10.4, 10.8, 10.5, 10.1, 9.9, 9.8, 9.9],
                "High": [10.5, 11.1, 11.5, 10.8, 10.2, 10.0, 9.9, 10.0],
                "Low": [9.9, 10.2, 10.4, 9.8, 9.7, 9.6, 9.7, 9.8],
                "Close": [10.4, 10.9, 10.5, 10.0, 9.8, 9.7, 9.85, 9.95],
                "Volume": [1000] * 8,
            },
            index=dates,
        )
        frame.index.name = "Date"

        result = run_rebound_backtest(
            data=frame,
            scenario_name="minute_rebound_filter_unit_test",
            strategy_kind="minute_rebound_with_fade_filter",
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            params={
                "lookback_bars": 3,
                "drop_entry_pct": -3.0,
                "rsi_entry": 60.0,
                "take_profit_pct": 1.0,
                "stop_loss_pct": 5.0,
                "max_hold_bars": 4,
                "fade_filter_upper_shadow_pct": 2.5,
                "fade_filter_block_bars": 2,
            },
            execution_config=build_execution_config(
                "research",
                commission_bps=0,
                slippage_bps=0,
                max_position_ratio=0.5,
            ),
        )

        summary = result["summary"]
        events = result["events"]
        self.assertEqual(summary["StrategyKind"], "minute_rebound_with_fade_filter")
        self.assertGreaterEqual(summary["FilterBlockedEvents"], 1)
        self.assertIn("filter_block", set(events["EventType"]))

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
