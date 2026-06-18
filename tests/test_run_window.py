"""
Tests for src/analysis/run_window.py — the dashboard "current run" filtering.
Pure functions; no DB, no fastapi, no trader coupling.
"""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from src.analysis import run_window as rw

CUTOFF = datetime(2026, 6, 18, 3, 0, 0, tzinfo=timezone.utc)


class TestParseTs(unittest.TestCase):
    def test_iso_with_offset(self):
        self.assertEqual(rw.parse_ts("2026-06-18T09:32:00+00:00").year, 2026)

    def test_iso_naive_assumed_utc(self):
        dt = rw.parse_ts("2026-06-18T09:32:00")
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_space_separated_bar_time(self):
        dt = rw.parse_ts("2026-06-17 15:30:00")
        self.assertEqual((dt.hour, dt.minute), (15, 30))

    def test_z_suffix(self):
        self.assertIsNotNone(rw.parse_ts("2026-06-18T09:32:00Z"))

    def test_none_and_garbage(self):
        self.assertIsNone(rw.parse_ts(None))
        self.assertIsNone(rw.parse_ts(""))
        self.assertIsNone(rw.parse_ts("not-a-date"))


class TestFilterRows(unittest.TestCase):
    def setUp(self):
        # 2 old (pre-cutoff), 2 new (post-cutoff)
        self.rows = [
            {"entry_time": "2026-05-29T14:00:00+00:00", "id": 1},   # old
            {"entry_time": "2026-06-17T15:30:00+00:00", "id": 2},   # old
            {"entry_time": "2026-06-18T14:22:00+00:00", "id": 3},   # new
            {"entry_time": "2026-06-18T15:32:00+00:00", "id": 4},   # new
        ]

    def test_current_keeps_post_cutoff(self):
        out = rw.filter_rows(self.rows, ["entry_time"], CUTOFF, "current")
        self.assertEqual([r["id"] for r in out], [3, 4])

    def test_archive_keeps_pre_cutoff(self):
        out = rw.filter_rows(self.rows, ["entry_time"], CUTOFF, "archive")
        self.assertEqual([r["id"] for r in out], [1, 2])

    def test_all_keeps_everything(self):
        out = rw.filter_rows(self.rows, ["entry_time"], CUTOFF, "all")
        self.assertEqual(len(out), 4)

    def test_no_marker_returns_all(self):
        out = rw.filter_rows(self.rows, ["entry_time"], None, "current")
        self.assertEqual(len(out), 4)

    def test_invalid_mode_defaults_current(self):
        out = rw.filter_rows(self.rows, ["entry_time"], CUTOFF, "bogus")
        self.assertEqual([r["id"] for r in out], [3, 4])

    def test_undated_row_excluded_from_current(self):
        rows = self.rows + [{"entry_time": None, "id": 5}]
        out = rw.filter_rows(rows, ["entry_time"], CUTOFF, "current")
        self.assertNotIn(5, [r["id"] for r in out])

    def test_fallback_ts_key(self):
        rows = [{"updated_at": None, "bar_time": "2026-06-18T16:00:00+00:00", "id": 9}]
        out = rw.filter_rows(rows, ["updated_at", "bar_time"], CUTOFF, "current")
        self.assertEqual([r["id"] for r in out], [9])


class TestMarker(unittest.TestCase):
    def test_load_and_started_at(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "current_run.json")
            json.dump({"run_id": "run_x", "started_at": "2026-06-18T03:00:00+00:00"}, open(p, "w"))
            m = rw.load_run_marker(p)
            self.assertEqual(m["run_id"], "run_x")
            self.assertEqual(rw.marker_started_at(m), CUTOFF)

    def test_missing_marker_returns_none(self):
        self.assertIsNone(rw.load_run_marker("/nonexistent/current_run.json"))
        self.assertIsNone(rw.marker_started_at(None))


if __name__ == "__main__":
    unittest.main()
