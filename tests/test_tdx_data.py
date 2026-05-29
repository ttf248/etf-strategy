from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from strategy_studio.data.tdx import (
    build_day_file_signature,
    manifest_can_append,
    manifest_is_unchanged,
    normalize_day_frame,
    read_day_frame,
    read_day_frame_tail,
)


def build_day_record(
    trade_date: int,
    open_price: int,
    high_price: int,
    low_price: int,
    close_price: int,
    amount: float,
    volume: int,
) -> bytes:
    return struct.pack("<IIIII fII", trade_date, open_price, high_price, low_price, close_price, amount, volume, 0)


class TdxDataTests(unittest.TestCase):
    def test_read_day_frame_and_normalize_sz_stock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vipdoc = Path(temp_dir)
            source_file = vipdoc / "sz" / "sz000001.day"
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(
                build_day_record(20240520, 1234, 1300, 1200, 1288, 123456.0, 345600)
                + build_day_record(20240521, 1288, 1322, 1275, 1305, 223456.0, 445600)
            )

            frame = read_day_frame(source_file, vipdoc)
            normalized = normalize_day_frame(frame, source_file, vipdoc)

        self.assertEqual(len(frame), 2)
        self.assertAlmostEqual(float(frame.iloc[0]["open"]), 12.34)
        self.assertAlmostEqual(float(frame.iloc[0]["close"]), 12.88)
        self.assertAlmostEqual(float(frame.iloc[0]["volume"]), 3456.0)
        self.assertEqual(normalized.iloc[0]["market"], "sz")
        self.assertEqual(normalized.iloc[0]["symbol"], "sz000001")
        self.assertEqual(normalized.iloc[0]["datetime"], "2024-05-20")
        self.assertEqual(normalized.iloc[1]["period"], "day")

    def test_manifest_helpers_detect_skip_and_append(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vipdoc = Path(temp_dir)
            source_file = vipdoc / "sh" / "sh600000.day"
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(
                build_day_record(20240520, 1000, 1100, 900, 1050, 1000.0, 10000)
                + build_day_record(20240521, 1050, 1150, 950, 1100, 2000.0, 20000)
            )
            signature = build_day_file_signature(source_file)
            previous = SimpleNamespace(
                status="success",
                source_size=signature["source_size"],
                source_mtime=signature["source_mtime"],
                record_count=signature["record_count"],
                tail_hash=signature["tail_hash"],
            )

            self.assertTrue(manifest_is_unchanged(previous, signature))

            source_file.write_bytes(
                source_file.read_bytes() + build_day_record(20240522, 1100, 1180, 1000, 1120, 3000.0, 30000)
            )
            append_signature = build_day_file_signature(source_file)
            self.assertTrue(manifest_can_append(previous, append_signature, source_file))

            tail_frame = read_day_frame_tail(source_file, start_offset=32, vipdoc=vipdoc)
            self.assertEqual(len(tail_frame), 2)


if __name__ == "__main__":
    unittest.main()
