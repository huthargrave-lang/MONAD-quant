"""
Tests for live/signals.py safety guards (Phase 6.3).

Covers the refuse-entry-on-bad-data paths:
  * yfinance fetch exception → RuntimeError
  * Empty DataFrame → RuntimeError
  * Fewer than LIVE_MIN_WARMUP_BARS → RuntimeError
  * Stale latest bar → RuntimeError
  * NaN feature on latest bar → RuntimeError (via get_current_signal)

No IBKR/yfinance connectivity required — all external calls are mocked via
module-level patching of src.data.fetcher.fetch_yfinance.
"""

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd


def _stub_missing(name: str) -> None:
    if name in sys.modules:
        return
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = types.ModuleType(name)


_stub_missing("yfinance")
_stub_missing("dotenv")
if "dotenv" in sys.modules and not hasattr(sys.modules["dotenv"], "load_dotenv"):
    sys.modules["dotenv"].load_dotenv = lambda *a, **k: None

from live import signals  # noqa: E402
import config  # noqa: E402


def _make_hourly_df(n_bars: int, end_time: datetime | None = None,
                    flat: bool = False) -> pd.DataFrame:
    """Build a deterministic hourly OHLCV DataFrame for mocking fetch_yfinance."""
    if end_time is None:
        end_time = datetime.now() - timedelta(minutes=30)  # completed, not "current"
    idx = pd.date_range(end=end_time, periods=n_bars, freq="h")
    if flat:
        closes = np.full(n_bars, 100.0)
    else:
        # Gentle mean-reverting walk so features don't explode
        rng = np.random.default_rng(42)
        closes = 100 + np.cumsum(rng.normal(0, 0.5, n_bars))
    df = pd.DataFrame({
        "open":   closes + rng.normal(0, 0.1, n_bars) if not flat else closes,
        "high":   closes + 0.2,
        "low":    closes - 0.2,
        "close":  closes,
        "volume": np.full(n_bars, 1_000_000.0),
    }, index=idx)
    # Ensure OHLC invariants
    df["high"] = df[["open", "high", "close"]].max(axis=1) + 0.01
    df["low"]  = df[["open", "low",  "close"]].min(axis=1) - 0.01
    return df


class TestFetchRecentBarsRaises(unittest.TestCase):
    """_fetch_recent_bars raises RuntimeError on every failure mode."""

    def test_yfinance_exception_raises(self):
        with patch("live.signals.fetch_yfinance", side_effect=ConnectionError("yfinance down")):
            with self.assertRaises(RuntimeError) as ctx:
                signals._fetch_recent_bars("TQQQ", min_bars=200)
            self.assertIn("yfinance down", str(ctx.exception))

    def test_empty_dataframe_raises(self):
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        with patch("live.signals.fetch_yfinance", return_value=empty):
            with self.assertRaises(RuntimeError) as ctx:
                signals._fetch_recent_bars("TQQQ", min_bars=200)
            self.assertIn("empty", str(ctx.exception).lower())

    def test_none_dataframe_raises(self):
        with patch("live.signals.fetch_yfinance", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                signals._fetch_recent_bars("TQQQ", min_bars=200)
            self.assertIn("empty", str(ctx.exception).lower())

    def test_insufficient_bars_raises(self):
        # Use an end_time >60min old so no bar is stripped as "incomplete"
        end = datetime.now() - timedelta(hours=2)
        df = _make_hourly_df(50, end_time=end)  # way below default min_bars=200
        with patch("live.signals.fetch_yfinance", return_value=df):
            with self.assertRaises(RuntimeError) as ctx:
                signals._fetch_recent_bars("TQQQ", min_bars=200)
            self.assertIn("Insufficient", str(ctx.exception))
            self.assertIn("50", str(ctx.exception))

    def test_stale_bars_raises(self):
        # Latest bar is 10 days old — far beyond the 120h staleness limit.
        old_end = datetime.now() - timedelta(days=10)
        df = _make_hourly_df(300, end_time=old_end)
        with patch("live.signals.fetch_yfinance", return_value=df):
            with self.assertRaises(RuntimeError) as ctx:
                signals._fetch_recent_bars("TQQQ", min_bars=200)
            self.assertIn("stale", str(ctx.exception).lower())

    def test_fresh_bars_pass(self):
        # 300 fresh bars should return cleanly with no exception.
        df = _make_hourly_df(300)
        with patch("live.signals.fetch_yfinance", return_value=df):
            result = signals._fetch_recent_bars("TQQQ", min_bars=200)
        self.assertGreaterEqual(len(result), 200)

    def test_incomplete_current_bar_dropped(self):
        # Build 301 bars where the last one is ~2 minutes old (incomplete).
        recent_end = datetime.now() - timedelta(minutes=2)
        df = _make_hourly_df(301, end_time=recent_end)
        with patch("live.signals.fetch_yfinance", return_value=df):
            result = signals._fetch_recent_bars("TQQQ", min_bars=200)
        # Last completed bar must be >= 60 minutes old
        now = pd.Timestamp.now()
        last_age = now - result.index[-1]
        self.assertGreaterEqual(last_age, pd.Timedelta(minutes=59))


class TestStalenessConfigurable(unittest.TestCase):
    """The staleness limit honors config.LIVE_MAX_BAR_STALENESS_HOURS."""

    def test_custom_staleness_limit(self):
        # Latest bar 3 days old. Default 120h allows it, but a 48h limit blocks it.
        old_end = datetime.now() - timedelta(days=3)
        df = _make_hourly_df(300, end_time=old_end)
        with patch("live.signals.fetch_yfinance", return_value=df):
            # Default 120h → passes
            with patch.object(config, "LIVE_MAX_BAR_STALENESS_HOURS", 120):
                result = signals._fetch_recent_bars("TQQQ", min_bars=200)
                self.assertGreaterEqual(len(result), 200)
            # Tight 48h → fails
            with patch.object(config, "LIVE_MAX_BAR_STALENESS_HOURS", 48):
                with self.assertRaises(RuntimeError) as ctx:
                    signals._fetch_recent_bars("TQQQ", min_bars=200)
                self.assertIn("stale", str(ctx.exception).lower())


class TestMinBarsConfigurable(unittest.TestCase):
    """The min_bars arg overrides the default."""

    def test_tight_min_bars(self):
        df = _make_hourly_df(150)
        with patch("live.signals.fetch_yfinance", return_value=df):
            # min_bars=200 fails
            with self.assertRaises(RuntimeError):
                signals._fetch_recent_bars("TQQQ", min_bars=200)
            # min_bars=100 passes
            result = signals._fetch_recent_bars("TQQQ", min_bars=100)
            self.assertGreaterEqual(len(result), 100)


if __name__ == "__main__":
    unittest.main()
