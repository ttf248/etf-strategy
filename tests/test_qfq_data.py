from __future__ import annotations

import unittest

import pandas as pd

from strategy_studio.data.qfq import apply_qfq_segment_frame, build_qfq_segment_frame


def build_raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Date": "2024-01-02",
                "Open": 10.0,
                "High": 11.0,
                "Low": 9.0,
                "Close": 10.0,
                "Volume": 100,
                "Amount": 1000.0,
            },
            {
                "Date": "2024-01-03",
                "Open": 9.0,
                "High": 10.0,
                "Low": 8.0,
                "Close": 9.0,
                "Volume": 90,
                "Amount": 900.0,
            },
            {
                "Date": "2024-01-04",
                "Open": 8.0,
                "High": 9.0,
                "Low": 7.0,
                "Close": 8.0,
                "Volume": 80,
                "Amount": 800.0,
            },
        ]
    )


class QfqDataTests(unittest.TestCase):
    def test_build_qfq_segment_frame_without_actions_returns_identity_segment(self) -> None:
        segments = build_qfq_segment_frame(build_raw_frame(), pd.DataFrame())

        self.assertEqual(len(segments), 1)
        self.assertEqual(str(segments.iloc[0]["start_date"]), "2024-01-02")
        self.assertEqual(str(segments.iloc[0]["end_date"]), "2024-01-04")
        self.assertEqual(float(segments.iloc[0]["adjust_a"]), 1.0)
        self.assertEqual(float(segments.iloc[0]["adjust_b"]), 0.0)

    def test_build_qfq_segment_frame_accumulates_affine_events(self) -> None:
        actions = pd.DataFrame(
            [
                {
                    "action_type": "dividend",
                    "announce_date": "2024-01-01",
                    "record_date": "2024-01-02",
                    "ex_date": "2024-01-03",
                    "pay_date": "2024-01-05",
                    "cash_dividend": 1.0,
                    "stock_bonus_ratio": 0.0,
                    "stock_conversion_ratio": 0.0,
                    "rights_ratio": 0.0,
                    "rights_price": 0.0,
                },
                {
                    "action_type": "dividend",
                    "announce_date": "2024-01-02",
                    "record_date": "2024-01-03",
                    "ex_date": "2024-01-04",
                    "pay_date": "2024-01-08",
                    "cash_dividend": 0.0,
                    "stock_bonus_ratio": 1.0,
                    "stock_conversion_ratio": 0.0,
                    "rights_ratio": 0.0,
                    "rights_price": 0.0,
                },
            ]
        )

        segments = build_qfq_segment_frame(build_raw_frame(), actions)

        self.assertEqual(len(segments), 3)
        self.assertEqual(str(segments.iloc[0]["start_date"]), "2024-01-02")
        self.assertEqual(str(segments.iloc[0]["end_date"]), "2024-01-02")
        self.assertAlmostEqual(float(segments.iloc[0]["adjust_a"]), 0.5)
        self.assertAlmostEqual(float(segments.iloc[0]["adjust_b"]), -0.5)
        self.assertEqual(str(segments.iloc[1]["start_date"]), "2024-01-03")
        self.assertEqual(str(segments.iloc[1]["end_date"]), "2024-01-03")
        self.assertAlmostEqual(float(segments.iloc[1]["adjust_a"]), 0.5)
        self.assertAlmostEqual(float(segments.iloc[1]["adjust_b"]), 0.0)
        self.assertEqual(str(segments.iloc[2]["start_date"]), "2024-01-04")
        self.assertEqual(str(segments.iloc[2]["end_date"]), "2024-01-04")
        self.assertAlmostEqual(float(segments.iloc[2]["adjust_a"]), 1.0)
        self.assertAlmostEqual(float(segments.iloc[2]["adjust_b"]), 0.0)
        self.assertEqual(segments.iloc[0]["payload_json"]["event_count"], 2)
        self.assertRegex(segments.iloc[0]["payload_json"]["source_hash"], r"^[0-9a-f]{40}$")
        self.assertRegex(segments.iloc[1]["payload_json"]["source_hash"], r"^[0-9a-f]{40}$")
        self.assertEqual(segments.iloc[2]["payload_json"]["source_hash"], "empty")

    def test_apply_qfq_segment_frame_merges_same_day_actions(self) -> None:
        actions = pd.DataFrame(
            [
                {
                    "ex_date": "2024-01-03",
                    "cash_dividend": 0.4,
                    "stock_bonus_ratio": 0.1,
                    "stock_conversion_ratio": 0.0,
                    "rights_ratio": 0.0,
                    "rights_price": 0.0,
                },
                {
                    "ex_date": "2024-01-03",
                    "cash_dividend": 0.6,
                    "stock_bonus_ratio": 0.0,
                    "stock_conversion_ratio": 0.2,
                    "rights_ratio": 0.0,
                    "rights_price": 0.0,
                },
            ]
        )

        segments = build_qfq_segment_frame(build_raw_frame(), actions)
        adjusted = apply_qfq_segment_frame(build_raw_frame(), segments)

        self.assertAlmostEqual(float(adjusted.iloc[0]["Close"]), (10.0 - 1.0) / 1.3)
        self.assertAlmostEqual(float(adjusted.iloc[0]["AdjustA"]), 1.0 / 1.3)
        self.assertAlmostEqual(float(adjusted.iloc[0]["AdjustB"]), -1.0 / 1.3)
        self.assertAlmostEqual(float(adjusted.iloc[1]["Close"]), 9.0)
        self.assertAlmostEqual(float(adjusted.iloc[2]["Close"]), 8.0)

    def test_build_qfq_segment_frame_supports_rights_issue_affine_parameters(self) -> None:
        actions = pd.DataFrame(
            [
                {
                    "ex_date": "2024-01-03",
                    "cash_dividend": 0.0,
                    "stock_bonus_ratio": 0.0,
                    "stock_conversion_ratio": 0.0,
                    "rights_ratio": 0.2,
                    "rights_price": 5.0,
                }
            ]
        )

        segments = build_qfq_segment_frame(build_raw_frame(), actions)
        adjusted = apply_qfq_segment_frame(build_raw_frame(), segments)

        self.assertAlmostEqual(float(segments.iloc[0]["adjust_a"]), 1.0 / 1.2)
        self.assertAlmostEqual(float(segments.iloc[0]["adjust_b"]), 1.0 / 1.2)
        self.assertAlmostEqual(float(adjusted.iloc[0]["Close"]), 10.0 / 1.2 + 1.0 / 1.2)
        self.assertAlmostEqual(float(adjusted.iloc[1]["Close"]), 9.0)

    def test_build_qfq_segment_frame_rejects_rights_issue_without_price(self) -> None:
        actions = pd.DataFrame(
            [
                {
                    "ex_date": "2024-01-03",
                    "cash_dividend": 0.0,
                    "stock_bonus_ratio": 0.0,
                    "stock_conversion_ratio": 0.0,
                    "rights_ratio": 0.2,
                    "rights_price": 0.0,
                }
            ]
        )

        with self.assertRaisesRegex(ValueError, "缺少配股价或配股比例"):
            build_qfq_segment_frame(build_raw_frame(), actions)

    def test_apply_qfq_segment_frame_raises_when_segment_has_gap(self) -> None:
        segments = pd.DataFrame(
            [
                {
                    "start_date": "2024-01-02",
                    "end_date": "2024-01-02",
                    "adjust_a": 1.0,
                    "adjust_b": 0.0,
                    "status": "ready",
                    "payload_json": {"source": "test"},
                },
                {
                    "start_date": "2024-01-04",
                    "end_date": "2024-01-04",
                    "adjust_a": 1.0,
                    "adjust_b": 0.0,
                    "status": "ready",
                    "payload_json": {"source": "test"},
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "交易日没有匹配到连续前复权公式区间"):
            apply_qfq_segment_frame(build_raw_frame(), segments)

    def test_apply_qfq_segment_frame_normalizes_unsorted_rows_before_linear_match(self) -> None:
        raw_frame = pd.DataFrame(
            [
                {
                    "Date": "2024-01-04",
                    "Open": 8.0,
                    "High": 9.0,
                    "Low": 7.0,
                    "Close": 8.0,
                    "Volume": 80,
                    "Amount": 800.0,
                },
                {
                    "Date": "2024-01-02",
                    "Open": 10.0,
                    "High": 11.0,
                    "Low": 9.0,
                    "Close": 10.0,
                    "Volume": 100,
                    "Amount": 1000.0,
                },
                {
                    "Date": "2024-01-03",
                    "Open": 9.0,
                    "High": 10.0,
                    "Low": 8.0,
                    "Close": 9.0,
                    "Volume": 90,
                    "Amount": 900.0,
                },
            ]
        )
        segments = pd.DataFrame(
            [
                {
                    "start_date": "2024-01-02",
                    "end_date": "2024-01-03",
                    "adjust_a": 0.5,
                    "adjust_b": -1.0,
                    "status": "ready",
                    "payload_json": {"source": "test"},
                },
                {
                    "start_date": "2024-01-04",
                    "end_date": "2024-01-04",
                    "adjust_a": 1.0,
                    "adjust_b": 0.0,
                    "status": "ready",
                    "payload_json": {"source": "test"},
                },
            ]
        )

        adjusted = apply_qfq_segment_frame(raw_frame, segments)

        self.assertEqual(adjusted["Date"].dt.strftime("%Y-%m-%d").tolist(), ["2024-01-02", "2024-01-03", "2024-01-04"])
        self.assertAlmostEqual(float(adjusted.iloc[0]["Close"]), 4.0)
        self.assertAlmostEqual(float(adjusted.iloc[1]["Close"]), 3.5)
        self.assertAlmostEqual(float(adjusted.iloc[2]["Close"]), 8.0)


if __name__ == "__main__":
    unittest.main()
