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
                    "ex_date": "2024-01-03",
                    "cash_dividend": 1.0,
                    "stock_bonus_ratio": 0.0,
                    "stock_conversion_ratio": 0.0,
                    "rights_ratio": 0.0,
                    "rights_price": 0.0,
                },
                {
                    "ex_date": "2024-01-04",
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


if __name__ == "__main__":
    unittest.main()
