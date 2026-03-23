"""Tests for live/state.py — SQLite-backed position and trade management."""

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

# Patch _DB_PATH before importing state so tests use a temp database.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()

import live.state as state_module

state_module._DB_PATH = _tmp.name


class TestStateDB(unittest.TestCase):
    """Tests for position lifecycle and trade recording."""

    def setUp(self):
        """Reset the database before each test."""
        conn = sqlite3.connect(state_module._DB_PATH)
        conn.executescript("DROP TABLE IF EXISTS position; DROP TABLE IF EXISTS trades;")
        conn.close()
        state_module.init_db()

    def test_init_db_creates_tables(self):
        conn = sqlite3.connect(state_module._DB_PATH)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        table_names = {t[0] for t in tables}
        self.assertIn("position", table_names)
        self.assertIn("trades", table_names)

    def test_no_position_returns_none(self):
        self.assertIsNone(state_module.get_position())

    def test_open_and_get_position(self):
        state_module.open_position("TQQQ", 80.50, 10, "12345")
        pos = state_module.get_position()
        self.assertIsNotNone(pos)
        self.assertEqual(pos.symbol, "TQQQ")
        self.assertAlmostEqual(pos.entry_price, 80.50)
        self.assertEqual(pos.qty, 10)
        self.assertEqual(pos.bracket_order_id, "12345")
        self.assertEqual(pos.bar_count, 0)

    def test_open_position_replaces_stale(self):
        state_module.open_position("TQQQ", 80.0, 5, "111")
        state_module.open_position("GDXU", 60.0, 8, "222")
        pos = state_module.get_position()
        self.assertEqual(pos.symbol, "GDXU")
        self.assertEqual(pos.bracket_order_id, "222")

    def test_increment_bar_count(self):
        state_module.open_position("TQQQ", 80.0, 10, "12345")
        self.assertEqual(state_module.increment_bar_count(), 1)
        self.assertEqual(state_module.increment_bar_count(), 2)
        self.assertEqual(state_module.increment_bar_count(), 3)

    def test_increment_bar_count_no_position(self):
        self.assertEqual(state_module.increment_bar_count(), 0)

    def test_close_position_records_trade(self):
        state_module.open_position("TQQQ", 80.0, 10, "12345")
        state_module.close_position(return_pct=0.0042, exit_type="target_hit", exit_price=80.34)

        # Position should be gone
        self.assertIsNone(state_module.get_position())

        # Trade should be recorded
        summary = state_module.get_trade_summary()
        self.assertEqual(summary["total"], 1)
        self.assertAlmostEqual(summary["win_rate"], 1.0)
        self.assertEqual(summary["exit_types"], {"target_hit": 1})

    def test_close_position_no_position_is_safe(self):
        # Should not raise — just logs a warning
        state_module.close_position(return_pct=0.01, exit_type="stop_hit")

    def test_get_position_plan(self):
        plan = state_module.get_position_plan(100_000)
        self.assertAlmostEqual(plan["position_pct"], 0.10)
        self.assertAlmostEqual(plan["position_dollars"], 10_000.0)

    def test_get_trade_summary_empty(self):
        summary = state_module.get_trade_summary()
        self.assertEqual(summary, {"total": 0})

    def test_get_trade_summary_mixed(self):
        state_module.open_position("TQQQ", 80.0, 10, "1")
        state_module.close_position(0.004, "target_hit", 80.32)

        state_module.open_position("TQQQ", 81.0, 10, "2")
        state_module.close_position(-0.001, "stop_hit", 80.92)

        state_module.open_position("TQQQ", 79.0, 10, "3")
        state_module.close_position(0.002, "time_exit", 79.16)

        summary = state_module.get_trade_summary()
        self.assertEqual(summary["total"], 3)
        self.assertAlmostEqual(summary["win_rate"], 2 / 3)
        self.assertEqual(summary["exit_types"]["target_hit"], 1)
        self.assertEqual(summary["exit_types"]["stop_hit"], 1)
        self.assertEqual(summary["exit_types"]["time_exit"], 1)

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(state_module._DB_PATH)
        except OSError:
            pass


class TestConfig(unittest.TestCase):
    """Tests for config correctness (no heavy imports needed)."""

    def test_dry_run_flag_default_false(self):
        import config
        self.assertFalse(config.LIVE_DRY_RUN)

    def test_live_symbol_has_matching_assets_entry(self):
        import config
        mode = f"{config.LIVE_SYMBOL}_HOURLY"
        self.assertIn(mode, config.ASSETS, f"No ASSETS entry for LIVE_SYMBOL={config.LIVE_SYMBOL}")

    def test_assets_have_required_keys(self):
        import config
        for mode_name, asset in config.ASSETS.items():
            for key in ("target_gain_pct", "stop_loss_pct", "require_signals"):
                self.assertIn(key, asset, f"ASSETS['{mode_name}'] missing '{key}'")


if __name__ == "__main__":
    unittest.main()
