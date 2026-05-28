import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

import strategy_studio.data.market_rules as market_rules
from strategy_studio.cli import build_parser, handle_batch, handle_run
from strategy_studio.data.market_rules import resolve_lot_size_rule
from strategy_studio.settings import build_execution_config
from strategy_studio.symbols import SymbolSpec
from strategy_studio.strategy.grid import (
    build_sample_window,
    build_walk_forward_windows,
    optimize_grid_parameters,
    run_grid_backtest,
    split_intraday_in_sample_and_validation,
    split_in_sample_and_validation,
)
from strategy_studio.strategy.dca import run_dca_backtest
from strategy_studio.strategy.index_grid import resolve_index_grid_spec, run_index_grid_backtest
from strategy_studio.strategy.bollinger import run_bollinger_reversion_backtest
from strategy_studio.strategy.donchian import run_donchian_breakout_backtest
from strategy_studio.strategy.macd import run_macd_trend_backtest
from strategy_studio.strategy.rebound import run_rebound_backtest
from strategy_studio.strategy.trend import run_ma_cross_backtest


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

    def test_legacy_download_command_is_removed(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["download", "--symbol", "1810.HK"])

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
        self.assertEqual(args.execution_profile, "realistic")

    def test_run_parser_no_longer_accepts_local_only_mode(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["run", "--symbol", "1810.HK", "--local-only"])

    def test_legacy_backtest_command_is_removed(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["backtest", "--symbol", "1810.HK"])

    def test_legacy_report_command_is_removed(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["report", "--symbol", "1810.HK"])

    def test_handle_run_syncs_database_and_executes_job(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--symbol", "1810.HK", "--proxy", "http://127.0.0.1:7897"])

        with (
            patch("strategy_studio.cli.sync_market_data", return_value={"run_id": 11, "bars_inserted": 120, "bars_updated": 8}) as mock_sync,
            patch("strategy_studio.cli.submit_backtest", return_value={"job_id": 7, "status": "queued"}) as mock_submit,
            patch("strategy_studio.cli.execute_next_job", return_value=7) as mock_execute,
            patch(
                "strategy_studio.cli.fetch_job",
                return_value={
                    "id": 7,
                    "status": "succeeded",
                    "job_type": "backtest",
                    "request_payload": {"symbol": "1810.HK"},
                    "progress_pct": 100.0,
                    "submitted_at": "2026-05-28 10:00:00",
                    "started_at": "2026-05-28 10:00:01",
                    "completed_at": "2026-05-28 10:00:02",
                    "error_message": "",
                    "reports": [{"id": 19}],
                },
            ) as mock_fetch,
            patch("builtins.print"),
        ):
            result = handle_run(args)

        self.assertEqual(result, 0)
        mock_sync.assert_called_once_with(
            symbol="1810.HK",
            interval="15m",
            period="60d",
            proxy="http://127.0.0.1:7897",
        )
        mock_submit.assert_called_once()
        request = mock_submit.call_args.args[0]
        self.assertEqual(request.symbol, "1810.HK")
        self.assertEqual(request.interval, "15m")
        self.assertEqual(request.strategy_kind, "grid")
        self.assertEqual(request.jobs, 8)
        mock_execute.assert_called_once_with(preferred_job_id=7)
        mock_fetch.assert_called_once_with(7)

    def test_run_parser_no_longer_accepts_compare_strategy_mode(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["run", "--symbol", "1810.HK", "--interval", "15m", "--compare-strategies"])

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
            ]
        )

        self.assertEqual(args.command, "batch")
        self.assertEqual(args.symbols, "1810.HK,SPY")
        self.assertEqual(args.jobs, "auto")
        self.assertEqual(args.execution_profile, "realistic")

    def test_batch_parser_reads_symbol_set_and_defaults_to_intraday(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["batch", "--symbol-set", "hstech_plus_513050"])

        self.assertEqual(args.command, "batch")
        self.assertEqual(args.symbol_set, "hstech_plus_513050")
        self.assertIsNone(args.symbols)
        self.assertEqual(args.interval, "15m")
        self.assertEqual(args.period, "60d")
        self.assertEqual(args.jobs, "8")

    def test_batch_parser_no_longer_accepts_local_only_mode(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["batch", "--symbol-set", "hstech_plus_513050", "--local-only"])

    def test_batch_parser_reads_hstech_symbol_set(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["batch", "--symbol-set", "hstech_plus_513050", "--interval", "1d"])

        self.assertEqual(args.command, "batch")
        self.assertEqual(args.symbol_set, "hstech_plus_513050")
        self.assertEqual(args.interval, "1d")

    def test_batch_parser_no_longer_accepts_compare_strategy_arguments(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["batch", "--symbols", "1810.HK", "--compare-strategies"])

    def test_handle_batch_submits_database_jobs_without_local_files(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "batch",
                "--symbols",
                "1810.HK",
                "--interval",
                "1d",
                "--download",
                "--proxy",
                "http://127.0.0.1:7897",
            ]
        )
        with (
            patch("strategy_studio.cli.sync_market_data", return_value={"run_id": 31, "bars_inserted": 90, "bars_updated": 6}) as mock_sync,
            patch("strategy_studio.cli.submit_backtest", return_value={"job_id": 12, "status": "queued"}) as mock_submit,
            patch("strategy_studio.cli.execute_next_job", return_value=12) as mock_execute,
            patch(
                "strategy_studio.cli.fetch_job",
                return_value={
                    "id": 12,
                    "status": "succeeded",
                    "job_type": "backtest",
                    "request_payload": {"symbol": "1810.HK"},
                    "progress_pct": 100.0,
                    "submitted_at": "2026-05-28 10:00:00",
                    "started_at": "2026-05-28 10:00:01",
                    "completed_at": "2026-05-28 10:00:02",
                    "error_message": "",
                    "reports": [{"id": 28}],
                },
            ) as mock_fetch,
            patch("builtins.print"),
        ):
            result = handle_batch(args)

        self.assertEqual(result, 0)
        mock_sync.assert_called_once_with(
            symbol="1810.HK",
            interval="1d",
            proxy="http://127.0.0.1:7897",
            period=None,
        )
        mock_submit.assert_called_once()
        request = mock_submit.call_args.args[0]
        self.assertEqual(request.symbol, "1810.HK")
        self.assertEqual(request.interval, "1d")
        self.assertEqual(request.jobs, 8)
        mock_execute.assert_called_once_with(preferred_job_id=12)
        mock_fetch.assert_called_once_with(12)

    def test_batch_parser_no_longer_accepts_output_dir_arguments(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["batch", "--symbols", "1810.HK", "--interval", "1d", "--output-dir", "outputs/batch"])

    def test_batch_parser_no_longer_accepts_compare_strategy_file_mode(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["batch", "--symbols", "1810.HK", "--interval", "15m", "--compare-strategies"])

    def test_handle_batch_returns_failed_when_database_sync_fails(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["batch", "--symbols", "1810.HK", "--download", "--proxy", "http://127.0.0.1:7897"])
        with (
            patch("strategy_studio.cli.sync_market_data", side_effect=ValueError("Yahoo 行情下载失败")) as mock_sync,
            patch("builtins.print"),
        ):
            result = handle_batch(args)

        mock_sync.assert_called_once()
        self.assertEqual(result, 1)

    def test_batch_parser_no_longer_accepts_local_only_with_download(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["batch", "--symbols", "1810.HK", "--interval", "15m", "--download", "--local-only"])

    def test_resolve_lot_size_rule_for_us_symbol(self) -> None:
        rule = resolve_lot_size_rule("SPY")
        self.assertEqual(rule.market, "US")
        self.assertEqual(rule.lot_size, 1)

    def test_resolve_lot_size_rule_for_cn_etf_symbol(self) -> None:
        rule = resolve_lot_size_rule("513050.SS")
        self.assertEqual(rule.market, "CN")
        self.assertEqual(rule.lot_size, 100)
        self.assertIn("100 股", rule.source)

    @patch("strategy_studio.data.market_rules.requests.get")
    def test_resolve_lot_size_rule_for_hk_symbol(self, mock_get: Mock) -> None:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = """
        <td class="c3">Lot Size</td>
        <td class="c4">200</td>
        """
        mock_get.return_value = mock_response

        original_cache = market_rules._HK_LOT_SIZE_CACHE
        market_rules._HK_LOT_SIZE_CACHE = None
        try:
            rule = resolve_lot_size_rule("1810.HK")
            cached_rule = resolve_lot_size_rule("1810.HK")
        finally:
            market_rules._HK_LOT_SIZE_CACHE = original_cache

        self.assertEqual(rule.market, "HK")
        self.assertEqual(rule.lot_size, 200)
        self.assertIn("AASTOCKS", rule.source)
        self.assertEqual(cached_rule.lot_size, 200)
        self.assertEqual(mock_get.call_count, 1)

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
        self.assertNotIn("BaseOnlyUnits", summary)
        self.assertNotIn("BaseOnlyFinalEquity", summary)
        self.assertNotIn("BaseOnlyReturnPct", summary)
        self.assertNotIn("GridVsBaseOnly", summary)
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
        self.assertNotIn("BaseOnlyUnits", summary)
        self.assertNotIn("GridVsBaseOnly", summary)

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

    def test_resolve_index_grid_spec_rejects_unsupported_symbol(self) -> None:
        with self.assertRaisesRegex(ValueError, "仅支持以下标的"):
            resolve_index_grid_spec("510300.SS")

    def test_run_index_grid_backtest_uses_base_position_and_retrace_grid(self) -> None:
        prices = [10.0, 9.75, 9.81, 10.06, 9.99, 10.04]
        dates = pd.date_range(start="2026-04-01 09:30:00", periods=len(prices), freq="1min")
        frame = pd.DataFrame(
            {
                "Open": prices,
                "High": [price * 1.002 for price in prices],
                "Low": [price * 0.998 for price in prices],
                "Close": prices,
                "Volume": [1000] * len(prices),
            },
            index=dates,
        )
        frame.index.name = "Date"

        result = run_index_grid_backtest(
            data=frame,
            scenario_name="minute_index_grid_unit_test",
            symbol="159941.SZ",
            market="CN",
            lot_size=100,
            lot_size_source="unit test",
            execution_config=build_execution_config(
                "research",
                commission_bps=0,
                slippage_bps=0,
                max_position_ratio=0.95,
            ),
        )

        summary = result["summary"]
        events = result["events"]

        self.assertEqual(summary["StrategyKind"], "minute_index_grid_retrace")
        self.assertEqual(summary["BaseUnits"], summary["BasePositionUnits"])
        self.assertEqual(summary["GridUnitsPerTrade"] % 100, 0)
        self.assertTrue(summary["TriggeredGridEntry"])
        self.assertEqual(summary["GridBuyCount"], 1)
        self.assertEqual(summary["GridSellCount"], 1)
        self.assertEqual(summary["GridCyclesCompleted"], 1)
        self.assertEqual(summary["PositionUnits"], summary["BasePositionUnits"])
        self.assertNotIn("BaseOnlyUnits", summary)
        self.assertNotIn("GridVsBaseOnly", summary)
        self.assertIn("base_buy", set(events["EventType"]))
        self.assertIn("retrace_buy", set(events["EventType"]))
        self.assertIn("retrace_sell", set(events["EventType"]))
        self.assertEqual(int(events.iloc[0]["Units"]), int(summary["BasePositionUnits"]))

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
        self.assertNotIn("BaseOnlyUnits", summary)
        self.assertNotIn("GridVsBaseOnly", summary)
        self.assertIn("rebound_buy", set(events["EventType"]))
        self.assertTrue({"take_profit_sell", "max_hold_sell", "stop_loss_sell"}.intersection(set(events["EventType"])))

    def test_run_dca_backtest_buys_on_period_first_trading_day(self) -> None:
        prices = [10.0 + index * 0.1 for index in range(30)]
        frame = build_test_frame(prices, start="2026-01-01")

        result = run_dca_backtest(
            data=frame,
            scenario_name="dca_unit_test",
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            params={
                "investment_amount": 10000.0,
                "frequency": "weekly",
                "day_rule": "first_trading_day",
                "max_position_ratio": 0.95,
            },
            execution_config=build_execution_config(
                "research",
                commission_bps=0,
                slippage_bps=0,
                max_position_ratio=0.95,
            ),
        )

        summary = result["summary"]
        events = result["events"]
        trades = result["trades"]

        self.assertEqual(summary["StrategyKind"], "dca")
        self.assertEqual(summary["StrategyName"], "定投")
        self.assertGreaterEqual(summary["DcaBuyCount"], 1)
        self.assertGreater(summary["DcaInvestedCash"], 0)
        self.assertNotIn("BaseOnlyUnits", summary)
        self.assertNotIn("GridVsBaseOnly", summary)
        self.assertIn("dca_buy", set(events["EventType"]))
        self.assertFalse(trades.empty)
        self.assertTrue((trades["Size"] < 0).all())
        self.assertTrue((events[events["EventType"] == "dca_buy"]["Units"] % 200 == 0).all())

    def test_run_ma_cross_backtest_generates_cross_buy_and_sell(self) -> None:
        prices = [10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.0, 9.0]
        frame = build_test_frame(prices, start="2025-02-03")

        result = run_ma_cross_backtest(
            data=frame,
            scenario_name="ma_cross_unit_test",
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            params={
                "short_window": 2,
                "long_window": 3,
                "signal_buffer_pct": 0.0,
            },
            execution_config=build_execution_config(
                "research",
                commission_bps=0,
                slippage_bps=0,
                max_position_ratio=0.8,
                stop_loss_pct=0.0,
                cooldown_bars=0,
            ),
        )

        summary = result["summary"]
        events = result["events"]
        trades = result["trades"]

        self.assertEqual(summary["StrategyKind"], "ma_cross")
        self.assertEqual(summary["StrategyName"], "双均线趋势")
        self.assertTrue(summary["TriggeredEntry"])
        self.assertEqual(summary["CrossEntryEvents"], 1)
        self.assertEqual(summary["CrossExitEvents"], 1)
        self.assertEqual(summary["PositionUnits"], 0)
        self.assertNotIn("BaseOnlyUnits", summary)
        self.assertNotIn("GridVsBaseOnly", summary)
        self.assertFalse(trades.empty)
        self.assertIn("ma_cross", set(trades["Tag"]))
        self.assertIn("ma_cross_buy", set(events["EventType"]))
        self.assertIn("ma_cross_sell", set(events["EventType"]))
        self.assertTrue((events[events["EventType"] == "ma_cross_buy"]["Units"] % 200 == 0).all())

    def test_run_macd_trend_backtest_generates_macd_buy_and_sell(self) -> None:
        prices = [10.0, 9.0, 8.0, 9.0, 10.0, 11.0, 10.5, 9.5, 8.8]
        frame = build_test_frame(prices, start="2025-02-17")

        result = run_macd_trend_backtest(
            data=frame,
            scenario_name="macd_trend_unit_test",
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            params={
                "fast_window": 2,
                "slow_window": 4,
                "signal_window": 2,
                "histogram_confirm_pct": 0.0,
                "stop_loss_pct": 20.0,
            },
            execution_config=build_execution_config(
                "research",
                commission_bps=0,
                slippage_bps=0,
                max_position_ratio=0.8,
                cooldown_bars=0,
            ),
        )

        summary = result["summary"]
        events = result["events"]
        trades = result["trades"]

        self.assertEqual(summary["StrategyKind"], "macd_trend")
        self.assertEqual(summary["StrategyName"], "MACD 趋势")
        self.assertTrue(summary["TriggeredEntry"])
        self.assertEqual(summary["MacdEntryEvents"], 1)
        self.assertEqual(summary["MacdExitEvents"], 1)
        self.assertEqual(summary["PositionUnits"], 0)
        self.assertNotIn("BaseOnlyUnits", summary)
        self.assertNotIn("GridVsBaseOnly", summary)
        self.assertFalse(trades.empty)
        self.assertIn("macd_trend", set(trades["Tag"]))
        self.assertIn("macd_buy", set(events["EventType"]))
        self.assertIn("macd_sell", set(events["EventType"]))
        self.assertTrue((events[events["EventType"] == "macd_buy"]["Units"] % 200 == 0).all())

    def test_run_bollinger_reversion_backtest_generates_buy_and_mean_revert_exit(self) -> None:
        prices = [100.0, 100.0, 100.0, 100.0, 95.0, 90.0, 91.0, 95.0, 99.0]
        frame = build_test_frame(prices, start="2025-03-03")

        result = run_bollinger_reversion_backtest(
            data=frame,
            scenario_name="bollinger_reversion_unit_test",
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            params={
                "ma_window": 3,
                "band_width": 1.0,
                "rsi_entry": 60.0,
                "take_profit_pct": 20.0,
                "stop_loss_pct": 10.0,
                "max_hold_bars": 5,
            },
            execution_config=build_execution_config(
                "research",
                commission_bps=0,
                slippage_bps=0,
                max_position_ratio=0.8,
                stop_loss_pct=0.0,
                cooldown_bars=0,
            ),
        )

        summary = result["summary"]
        events = result["events"]
        trades = result["trades"]

        self.assertEqual(summary["StrategyKind"], "bollinger_reversion")
        self.assertEqual(summary["StrategyName"], "布林带均值回归")
        self.assertTrue(summary["TriggeredEntry"])
        self.assertGreaterEqual(summary["BollingerEntryEvents"], 1)
        self.assertGreaterEqual(summary["MeanRevertExitEvents"], 1)
        self.assertEqual(summary["PositionUnits"], 0)
        self.assertNotIn("BaseOnlyUnits", summary)
        self.assertNotIn("GridVsBaseOnly", summary)
        self.assertFalse(trades.empty)
        self.assertIn("bollinger_reversion", set(trades["Tag"]))
        self.assertIn("bollinger_buy", set(events["EventType"]))
        self.assertIn("mean_revert_sell", set(events["EventType"]))
        self.assertTrue((events[events["EventType"] == "bollinger_buy"]["Units"] % 200 == 0).all())

    def test_run_donchian_breakout_backtest_generates_breakout_buy_and_channel_exit(self) -> None:
        prices = [10.0, 9.0, 8.0, 9.0, 11.0, 10.5, 8.5]
        frame = build_test_frame(prices, start="2025-03-10")

        result = run_donchian_breakout_backtest(
            data=frame,
            scenario_name="donchian_breakout_unit_test",
            symbol="1810.HK",
            market="HK",
            lot_size=200,
            lot_size_source="unit test",
            params={
                "breakout_window": 3,
                "exit_window": 2,
                "confirm_buffer_pct": 0.0,
                "stop_loss_pct": 30.0,
            },
            execution_config=build_execution_config(
                "research",
                commission_bps=0,
                slippage_bps=0,
                max_position_ratio=0.8,
                cooldown_bars=0,
            ),
        )

        summary = result["summary"]
        events = result["events"]
        trades = result["trades"]

        self.assertEqual(summary["StrategyKind"], "donchian_breakout")
        self.assertEqual(summary["StrategyName"], "唐奇安突破")
        self.assertTrue(summary["TriggeredEntry"])
        self.assertEqual(summary["DonchianEntryEvents"], 1)
        self.assertEqual(summary["DonchianExitEvents"], 1)
        self.assertEqual(summary["PositionUnits"], 0)
        self.assertNotIn("BaseOnlyUnits", summary)
        self.assertNotIn("GridVsBaseOnly", summary)
        self.assertFalse(trades.empty)
        self.assertIn("donchian_breakout", set(trades["Tag"]))
        self.assertIn("donchian_buy", set(events["EventType"]))
        self.assertIn("donchian_exit_sell", set(events["EventType"]))
        self.assertTrue((events[events["EventType"] == "donchian_buy"]["Units"] % 200 == 0).all())

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

    @patch("strategy_studio.strategy.grid.run_grid_backtest")
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
