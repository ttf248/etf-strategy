from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from strategy_studio.data.tdx import (
    MINUTE_RECORD_SIZE,
    build_day_file_signature,
    build_tdx_file_signature,
    detect_period_from_suffix,
    interval_to_period,
    iter_tdx_files,
    manifest_can_append,
    manifest_is_unchanged,
    normalize_day_frame,
    normalize_minute_frame,
    read_day_frame,
    read_day_frame_tail,
    read_minute_frame,
    read_minute_frame_tail,
    suffixes_for_interval,
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
    return struct.pack("<IIIIIfII", trade_date, open_price, high_price, low_price, close_price, amount, volume, 0)


def build_minute_date_code(year: int, month: int, day: int) -> int:
    return (year - 2004) * 2048 + month * 100 + day


def build_lc_minute_record(
    *,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    amount: float,
    volume: int,
) -> bytes:
    return struct.pack(
        "<HHfffffII",
        build_minute_date_code(year, month, day),
        hour * 60 + minute,
        open_price,
        high_price,
        low_price,
        close_price,
        amount,
        volume,
        0,
    )


def build_legacy_minute_record(
    *,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    open_price: int,
    high_price: int,
    low_price: int,
    close_price: int,
    amount: float,
    volume: int,
) -> bytes:
    return struct.pack(
        "<HHIIIIfII",
        build_minute_date_code(year, month, day),
        hour * 60 + minute,
        open_price,
        high_price,
        low_price,
        close_price,
        amount,
        volume,
        0,
    )


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

    def test_read_lc1_minute_frame_and_normalize(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vipdoc = Path(temp_dir)
            source_file = vipdoc / "sh" / "sh600000.lc1"
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(
                build_lc_minute_record(
                    year=2024,
                    month=5,
                    day=21,
                    hour=9,
                    minute=31,
                    open_price=10.25,
                    high_price=10.35,
                    low_price=10.18,
                    close_price=10.30,
                    amount=10000.0,
                    volume=800,
                )
                + build_lc_minute_record(
                    year=2024,
                    month=5,
                    day=21,
                    hour=9,
                    minute=32,
                    open_price=10.30,
                    high_price=10.40,
                    low_price=10.22,
                    close_price=10.38,
                    amount=12000.0,
                    volume=950,
                )
            )

            frame = read_minute_frame(source_file)
            normalized = normalize_minute_frame(frame, source_file, vipdoc, interval="1m")

        self.assertEqual(len(frame), 2)
        self.assertAlmostEqual(float(frame.iloc[0]["open"]), 10.25, places=2)
        self.assertAlmostEqual(float(frame.iloc[1]["close"]), 10.38, places=2)
        self.assertEqual(int(frame.iloc[1]["volume"]), 950)
        self.assertEqual(normalized.iloc[0]["datetime"], "2024-05-21 09:31:00")
        self.assertEqual(normalized.iloc[0]["period"], "min1")
        self.assertEqual(normalized.iloc[1]["source_file"], "sh/sh600000.lc1")

    def test_read_legacy_minute_frame_and_normalize(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vipdoc = Path(temp_dir)
            source_file = vipdoc / "sz" / "sz000001.5"
            source_file.parent.mkdir(parents=True)
            source_file.write_bytes(
                build_legacy_minute_record(
                    year=2024,
                    month=5,
                    day=21,
                    hour=10,
                    minute=0,
                    open_price=1025,
                    high_price=1040,
                    low_price=1018,
                    close_price=1031,
                    amount=13000.0,
                    volume=1200,
                )
                + build_legacy_minute_record(
                    year=2024,
                    month=5,
                    day=21,
                    hour=10,
                    minute=5,
                    open_price=1031,
                    high_price=1048,
                    low_price=1028,
                    close_price=1042,
                    amount=14000.0,
                    volume=1500,
                )
            )

            frame = read_minute_frame(source_file)
            normalized = normalize_minute_frame(frame, source_file, vipdoc, interval="5m")

        self.assertEqual(len(frame), 2)
        self.assertAlmostEqual(float(frame.iloc[0]["open"]), 10.25)
        self.assertAlmostEqual(float(frame.iloc[1]["close"]), 10.42)
        self.assertEqual(normalized.iloc[0]["period"], "min5")
        self.assertEqual(normalized.iloc[1]["datetime"], "2024-05-21 10:05:00")

    def test_interval_helpers_and_file_iteration_support_day_and_minute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vipdoc = Path(temp_dir)
            (vipdoc / "sh").mkdir(parents=True)
            (vipdoc / "sh" / "sh600000.day").write_bytes(build_day_record(20240520, 1000, 1100, 900, 1050, 1000.0, 10000))
            (vipdoc / "sh" / "sh600000.lc1").write_bytes(
                build_lc_minute_record(
                    year=2024,
                    month=5,
                    day=20,
                    hour=9,
                    minute=31,
                    open_price=10.0,
                    high_price=10.1,
                    low_price=9.9,
                    close_price=10.05,
                    amount=1000.0,
                    volume=100,
                )
            )
            (vipdoc / "sh" / "sh600000.5").write_bytes(
                build_legacy_minute_record(
                    year=2024,
                    month=5,
                    day=20,
                    hour=9,
                    minute=35,
                    open_price=1000,
                    high_price=1010,
                    low_price=995,
                    close_price=1008,
                    amount=1500.0,
                    volume=200,
                )
            )

            day_files = iter_tdx_files(vipdoc, interval="1d")
            minute_1_files = iter_tdx_files(vipdoc, interval="1m")
            minute_5_files = iter_tdx_files(vipdoc, interval="5m")

        self.assertEqual([path.name for path in day_files], ["sh600000.day"])
        self.assertEqual([path.name for path in minute_1_files], ["sh600000.lc1"])
        self.assertEqual([path.name for path in minute_5_files], ["sh600000.5"])
        self.assertEqual(suffixes_for_interval("1m"), {".lc1", ".1"})
        self.assertEqual(detect_period_from_suffix(".5"), "min5")
        self.assertEqual(interval_to_period("1d"), "day")

    def test_manifest_helpers_detect_skip_and_append_for_day_and_minute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vipdoc = Path(temp_dir)

            day_file = vipdoc / "sh" / "sh600000.day"
            day_file.parent.mkdir(parents=True)
            day_file.write_bytes(
                build_day_record(20240520, 1000, 1100, 900, 1050, 1000.0, 10000)
                + build_day_record(20240521, 1050, 1150, 950, 1100, 2000.0, 20000)
            )
            day_signature = build_day_file_signature(day_file)
            day_previous = SimpleNamespace(
                status="success",
                source_size=day_signature["source_size"],
                source_mtime=day_signature["source_mtime"],
                record_count=day_signature["record_count"],
                record_size=day_signature["record_size"],
                tail_hash=day_signature["tail_hash"],
            )

            self.assertTrue(manifest_is_unchanged(day_previous, day_signature))

            day_file.write_bytes(
                day_file.read_bytes() + build_day_record(20240522, 1100, 1180, 1000, 1120, 3000.0, 30000)
            )
            day_append_signature = build_day_file_signature(day_file)
            self.assertTrue(manifest_can_append(day_previous, day_append_signature, day_file))
            day_tail_frame = read_day_frame_tail(day_file, start_offset=32, vipdoc=vipdoc)
            self.assertEqual(len(day_tail_frame), 2)

            minute_file = vipdoc / "sh" / "sh600000.lc1"
            minute_file.write_bytes(
                build_lc_minute_record(
                    year=2024,
                    month=5,
                    day=21,
                    hour=9,
                    minute=31,
                    open_price=10.25,
                    high_price=10.35,
                    low_price=10.18,
                    close_price=10.30,
                    amount=10000.0,
                    volume=800,
                )
                + build_lc_minute_record(
                    year=2024,
                    month=5,
                    day=21,
                    hour=9,
                    minute=32,
                    open_price=10.30,
                    high_price=10.40,
                    low_price=10.22,
                    close_price=10.38,
                    amount=12000.0,
                    volume=950,
                )
            )
            minute_signature = build_tdx_file_signature(minute_file, interval="1m")
            minute_previous = SimpleNamespace(
                status="success",
                source_size=minute_signature["source_size"],
                source_mtime=minute_signature["source_mtime"],
                record_count=minute_signature["record_count"],
                record_size=minute_signature["record_size"],
                tail_hash=minute_signature["tail_hash"],
            )

            self.assertTrue(manifest_is_unchanged(minute_previous, minute_signature))

            minute_file.write_bytes(
                minute_file.read_bytes()
                + build_lc_minute_record(
                    year=2024,
                    month=5,
                    day=21,
                    hour=9,
                    minute=33,
                    open_price=10.38,
                    high_price=10.45,
                    low_price=10.35,
                    close_price=10.42,
                    amount=15000.0,
                    volume=1100,
                )
            )
            minute_append_signature = build_tdx_file_signature(minute_file, interval="1m")
            self.assertTrue(manifest_can_append(minute_previous, minute_append_signature, minute_file))

            minute_tail_frame = read_minute_frame_tail(minute_file, start_offset=MINUTE_RECORD_SIZE)
            self.assertEqual(len(minute_tail_frame), 2)


if __name__ == "__main__":
    unittest.main()
