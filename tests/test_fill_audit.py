"""
Tests for src/research/fill_audit.py — state DB fill audit (read-only).

Tests pure computation functions using synthetic FillRecord objects,
plus a real sqlite test using a temporary database.
"""

import os
import sqlite3
import tempfile
import unittest

from src.research.fill_audit import (
    FillRecord,
    SlippageStats,
    compute_slippage_stats,
    read_trades,
)


class TestSlippageStats(unittest.TestCase):

    def test_empty_trades(self):
        stats = compute_slippage_stats([])
        self.assertEqual(stats.n_trades, 0)
        self.assertEqual(stats.mean_slippage_bps, 0.0)

    def test_target_hit_no_slippage(self):
        trades = [
            FillRecord(
                entry_time="2025-01-01", exit_time="2025-01-02",
                return_pct=0.01, exit_type="target_hit",
            ),
        ]
        stats = compute_slippage_stats(trades, expected_target_pct=0.01)
        self.assertAlmostEqual(stats.mean_slippage_bps, 0.0)

    def test_target_hit_with_slippage(self):
        trades = [
            FillRecord(
                entry_time="2025-01-01", exit_time="2025-01-02",
                return_pct=0.008, exit_type="target_hit",
            ),
        ]
        stats = compute_slippage_stats(trades, expected_target_pct=0.01)
        # Expected: 0.01 - 0.008 = 0.002 = 20 bps
        self.assertAlmostEqual(stats.mean_slippage_bps, 20.0)

    def test_stop_hit_slippage(self):
        trades = [
            FillRecord(
                entry_time="2025-01-01", exit_time="2025-01-02",
                return_pct=-0.007, exit_type="stop_hit",
            ),
        ]
        stats = compute_slippage_stats(trades, expected_stop_pct=0.005)
        # Expected: abs(-0.007) - 0.005 = 0.002 = 20 bps
        self.assertAlmostEqual(stats.mean_slippage_bps, 20.0)

    def test_mixed_exit_types(self):
        trades = [
            FillRecord(entry_time="t1", exit_time="t2",
                       return_pct=0.01, exit_type="target_hit"),
            FillRecord(entry_time="t3", exit_time="t4",
                       return_pct=-0.005, exit_type="stop_hit"),
            FillRecord(entry_time="t5", exit_time="t6",
                       return_pct=0.002, exit_type="time_exit"),
        ]
        stats = compute_slippage_stats(trades, expected_target_pct=0.01,
                                       expected_stop_pct=0.005)
        # time_exit is skipped, both target and stop have 0 slippage
        self.assertEqual(stats.n_trades, 2)
        self.assertAlmostEqual(stats.mean_slippage_bps, 0.0)

    def test_by_exit_type_populated(self):
        trades = [
            FillRecord(entry_time="t1", exit_time="t2",
                       return_pct=0.009, exit_type="target_hit"),
            FillRecord(entry_time="t3", exit_time="t4",
                       return_pct=0.008, exit_type="target_hit"),
            FillRecord(entry_time="t5", exit_time="t6",
                       return_pct=-0.006, exit_type="stop_hit"),
        ]
        stats = compute_slippage_stats(trades, expected_target_pct=0.01,
                                       expected_stop_pct=0.005)
        self.assertIn("target_hit", stats.by_exit_type)
        self.assertIn("stop_hit", stats.by_exit_type)
        self.assertEqual(stats.by_exit_type["target_hit"]["count"], 2)
        self.assertEqual(stats.by_exit_type["stop_hit"]["count"], 1)


class TestReadTradesNoDb(unittest.TestCase):

    def test_nonexistent_db_returns_empty(self):
        result = read_trades(db_path="/tmp/nonexistent_monad_test.db")
        self.assertEqual(result, [])


class TestReadTradesRealDb(unittest.TestCase):
    """Test read_trades with a real temporary sqlite database."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE trades (
                entry_time TEXT NOT NULL,
                exit_time TEXT NOT NULL,
                return_pct REAL NOT NULL,
                exit_type TEXT NOT NULL,
                exit_price REAL,
                symbol TEXT,
                qty INTEGER,
                bars_held INTEGER
            )
        """)
        conn.execute(
            "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("2025-01-01T10:00", "2025-01-01T11:00", 0.009, "target_hit",
             85.50, "TQQQ", 100, 3),
        )
        conn.execute(
            "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("2025-01-02T10:00", "2025-01-02T12:00", -0.006, "stop_hit",
             84.20, "TQQQ", 100, 5),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_reads_correct_count(self):
        trades = read_trades(db_path=self.db_path)
        self.assertEqual(len(trades), 2)

    def test_reads_all_fields(self):
        trades = read_trades(db_path=self.db_path)
        t = trades[0]
        self.assertIsNotNone(t.exit_price)
        self.assertEqual(t.symbol, "TQQQ")
        self.assertEqual(t.qty, 100)
        self.assertIsNotNone(t.bars_held)

    def test_limit_parameter(self):
        trades = read_trades(db_path=self.db_path, limit=1)
        self.assertEqual(len(trades), 1)

    def test_slippage_on_real_data(self):
        trades = read_trades(db_path=self.db_path)
        stats = compute_slippage_stats(trades, expected_target_pct=0.01,
                                       expected_stop_pct=0.005)
        self.assertEqual(stats.n_trades, 2)
        self.assertGreater(stats.mean_slippage_bps, 0)


class TestSlippageStatsToDict(unittest.TestCase):

    def test_to_dict_has_all_fields(self):
        stats = SlippageStats(n_trades=5, mean_slippage_bps=3.0)
        d = stats.to_dict()
        self.assertEqual(d["n_trades"], 5)
        self.assertAlmostEqual(d["mean_slippage_bps"], 3.0)
        self.assertIn("by_exit_type", d)


if __name__ == "__main__":
    unittest.main()
