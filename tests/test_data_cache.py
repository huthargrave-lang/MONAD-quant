"""Tests for the validated market-data cache guard.

The bug this module exists to kill is subtle and self-perpetuating: `yfinance`
returns an EMPTY frame rather than raising when a fetch is blocked, so the labs
wrote a header-only CSV and then trusted it forever. The failure surfaced far from
its cause, as `IndexError: index -1 is out of bounds for axis 0 with size 0` inside
a statistics routine, which tells the reader nothing about the actual problem.

So the tests here assert three properties, in order of importance:

1. **A bad fetch is never written.** This is the one that matters — writing the stub
   is what poisons every FUTURE run, including runs that would otherwise have had
   network access.
2. **An already-poisoned cache is detected on read**, with the file path and the
   remedy in the message.
3. **A good fetch still works**, and round-trips through the cache.

Property 1 is verified by asserting the path does not exist afterwards, not merely
that an exception was raised — "raises but writes anyway" is exactly the failure
mode that would keep the trap armed.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "data_cache", ROOT / "tools" / "data_cache.py")
DC = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = DC
_SPEC.loader.exec_module(DC)

import pandas as pd  # noqa: E402


COLS = ["AAA", "BBB"]


def good_frame(rows=600):
    idx = pd.date_range("2014-01-01", periods=rows, freq="D")
    return pd.DataFrame({c: range(rows) for c in COLS}, index=idx)


def empty_frame():
    """Exactly what a blocked yfinance fetch produces: columns, no rows."""
    return pd.DataFrame({c: [] for c in COLS})


class NeverWriteABadFetchTests(unittest.TestCase):
    """Property 1 — the one that keeps the trap from re-arming itself."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "panel.csv")

    def test_empty_fetch_raises_and_writes_nothing(self):
        with self.assertRaises(DC.EmptyFetchError):
            DC.load_cached_frame(self.path, empty_frame, min_rows=500,
                                 required_cols=COLS, label="t")
        self.assertFalse(
            os.path.exists(self.path),
            "THE BUG: a failed fetch wrote a cache file. Every later run would "
            "read this stub and skip the fetch entirely.",
        )

    def test_short_fetch_raises_and_writes_nothing(self):
        """A partial fetch is as dangerous as an empty one — it looks plausible."""
        with self.assertRaises(DC.EmptyFetchError):
            DC.load_cached_frame(self.path, lambda: good_frame(10), min_rows=500,
                                 required_cols=COLS, label="t")
        self.assertFalse(os.path.exists(self.path))

    def test_fetch_missing_a_column_raises_and_writes_nothing(self):
        def partial():
            frame = good_frame()
            return frame.drop(columns=["BBB"])

        with self.assertRaises(DC.EmptyFetchError):
            DC.load_cached_frame(self.path, partial, min_rows=500,
                                 required_cols=COLS, label="t")
        self.assertFalse(os.path.exists(self.path))

    def test_column_present_but_all_nan_is_rejected(self):
        """yfinance returns the column with NaNs when one ticker fails."""
        def one_dead():
            frame = good_frame()
            frame["BBB"] = float("nan")
            return frame

        with self.assertRaises(DC.EmptyFetchError):
            DC.load_cached_frame(self.path, one_dead, min_rows=500,
                                 required_cols=COLS, label="t")
        self.assertFalse(os.path.exists(self.path))


class DetectPoisonedCacheTests(unittest.TestCase):
    """Property 2 — the stub already on disk must not be trusted."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "panel.csv")

    def _fetch_must_not_run(self):
        raise AssertionError("fetch should not be reached on a cache hit")

    def test_header_only_cache_is_rejected_with_an_actionable_message(self):
        empty_frame().to_csv(self.path)
        with self.assertRaises(DC.PoisonedCacheError) as ctx:
            DC.load_cached_frame(self.path, self._fetch_must_not_run,
                                 min_rows=500, required_cols=COLS, label="t")
        message = str(ctx.exception)
        self.assertIn(self.path, message, "the message must name the file")
        self.assertIn("rm ", message, "the message must give the remedy")
        self.assertIn("POISONED", message)

    def test_unreadable_cache_is_reported_not_crashed(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("\x00\x01 not a csv at all\n")
        with self.assertRaises(DC.PoisonedCacheError):
            DC.load_cached_frame(self.path, self._fetch_must_not_run,
                                 min_rows=500, required_cols=COLS, label="t")

    def test_the_real_world_stub_shape_is_caught(self):
        """Regression on the exact bytes observed in /tmp: a lone index header row."""
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(",DIA,GLD,HYG,IEF,IWM,QQQ,SPY,TLT\n")
        with self.assertRaises(DC.PoisonedCacheError):
            DC.load_cached_frame(self.path, self._fetch_must_not_run, min_rows=500,
                                 required_cols=["DIA", "GLD"], label="mr_daily")


class HappyPathTests(unittest.TestCase):
    """Property 3 — the guard must not break the case it is protecting."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "panel.csv")

    def test_good_fetch_is_written_and_then_reused(self):
        calls = []

        def fetch():
            calls.append(1)
            return good_frame()

        first = DC.load_cached_frame(self.path, fetch, min_rows=500,
                                     required_cols=COLS, label="t")
        self.assertEqual(len(first), 600)
        self.assertTrue(os.path.exists(self.path))

        second = DC.load_cached_frame(self.path, fetch, min_rows=500,
                                      required_cols=COLS, label="t")
        self.assertEqual(len(calls), 1, "second call should hit the cache")
        self.assertEqual(len(second), 600)

    def test_write_is_atomic_and_leaves_no_temp_file(self):
        DC.load_cached_frame(self.path, good_frame, min_rows=500,
                             required_cols=COLS, label="t")
        leftovers = [f for f in os.listdir(self.dir) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [], "atomic write leaked a temp file")

    def test_a_failed_write_leaves_no_partial_cache(self):
        class Explodes(pd.DataFrame):
            @property
            def _constructor(self):
                return Explodes

            def to_csv(self, *a, **k):
                raise OSError("disk full")

        with self.assertRaises(OSError):
            DC.write_frame_atomic(Explodes(good_frame()), self.path)
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual([f for f in os.listdir(self.dir) if f.endswith(".tmp")], [])


class DescribeFrameTests(unittest.TestCase):
    def test_describe_does_not_explode_on_an_empty_frame(self):
        """`describe_frame` runs inside the error path, so it must survive exactly
        the input that broke the labs — indexing [-1] on zero rows."""
        self.assertIn("header only", DC.describe_frame(empty_frame()))

    def test_describe_reports_the_span_of_a_real_frame(self):
        self.assertIn("600 rows", DC.describe_frame(good_frame()))


class WiredIntoTheLabsTests(unittest.TestCase):
    """The guard is worthless if a lab still has the raw pattern.

    Bidirectional: if a lab is rewritten to fetch directly again, this fails.
    """

    LABS = ["mr_daily_lab.py", "power_study.py", "gold_oos_study.py"]

    def test_no_lab_writes_a_cache_without_validating_it(self):
        for name in self.LABS:
            source = (ROOT / "tools" / name).read_text(encoding="utf-8")
            self.assertIn("data_cache", source, "{} lost the guard".format(name))
            self.assertNotIn(
                ".to_csv(cache)", source,
                "{} writes a cache directly again — re-route it through "
                "data_cache.load_cached_frame".format(name),
            )

    def test_labs_fail_cleanly_rather_than_tracebacking(self):
        for name in self.LABS:
            source = (ROOT / "tools" / name).read_text(encoding="utf-8")
            self.assertIn(
                "fail_cleanly", source,
                "{}'s entry point should report a missing panel as an "
                "environment problem, not raise a traceback".format(name),
            )


if __name__ == "__main__":
    unittest.main()
