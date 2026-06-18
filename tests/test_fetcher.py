"""
Tests for the data fetcher (src/data/fetcher.py) — previously F-grade (no tests).

Covers the parts that protect signal correctness and live stability:
  * validate_ohlc   — OHLC invariants (low<=open/close<=high, vol>=0, no zero/NaN)
  * fetch_yfinance  — retry/backoff on transient failures + post-fetch normalization
                      and validation (yfinance is mocked; no network, no real sleeps)
  * _cache_is_fresh — CSV cache staleness window

The fetcher is the live data layer; bad data here silently corrupts signals, so
these pin the guardrails.
"""
import os
import tempfile
import time
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import src.data.fetcher as fetcher


def _ohlcv(rows):
    """Build an OHLCV frame from a list of (open, high, low, close, volume)."""
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=idx)


def _yf_history(n=5, tz="America/New_York", bad_row=None):
    """A yfinance-style frame: capitalized cols, extra cols, tz-aware index."""
    idx = pd.date_range("2024-01-01 09:30", periods=n, freq="D", tz=tz)
    data = {
        "Open":  np.linspace(100, 104, n),
        "High":  np.linspace(101, 105, n),
        "Low":   np.linspace(99, 103, n),
        "Close": np.linspace(100.5, 104.5, n),
        "Volume": np.arange(1_000, 1_000 + n),
        "Dividends": np.zeros(n),
        "Stock Splits": np.zeros(n),
    }
    df = pd.DataFrame(data, index=idx)
    if bad_row is not None:
        # Corrupt one row: low above high.
        df.iloc[bad_row, df.columns.get_loc("Low")] = 999.0
    return df


class TestValidateOHLC(unittest.TestCase):
    def test_valid_data_unchanged(self):
        df = _ohlcv([(100, 101, 99, 100.5, 10), (100.5, 102, 100, 101, 12)])
        out = fetcher.validate_ohlc(df, "X")
        self.assertEqual(len(out), 2)
        pd.testing.assert_frame_equal(out, df)

    def test_empty_passthrough(self):
        df = _ohlcv([])
        self.assertTrue(fetcher.validate_ohlc(df, "X").empty)

    def test_drops_low_above_high(self):
        df = _ohlcv([(100, 101, 99, 100.5, 10), (100, 99, 101, 100, 10)])  # row2 low>high
        out = fetcher.validate_ohlc(df, "X")
        self.assertEqual(len(out), 1)
        self.assertEqual(out.iloc[0]["close"], 100.5)

    def test_drops_open_out_of_range(self):
        df = _ohlcv([(105, 101, 99, 100.5, 10)])  # open 105 > high 101
        self.assertEqual(len(fetcher.validate_ohlc(df, "X")), 0)

    def test_drops_close_out_of_range(self):
        df = _ohlcv([(100, 101, 99, 98, 10)])  # close 98 < low 99
        self.assertEqual(len(fetcher.validate_ohlc(df, "X")), 0)

    def test_drops_negative_volume(self):
        df = _ohlcv([(100, 101, 99, 100.5, -5)])
        self.assertEqual(len(fetcher.validate_ohlc(df, "X")), 0)

    def test_drops_zero_price(self):
        df = _ohlcv([(0, 101, 99, 100.5, 10)])  # zero open
        self.assertEqual(len(fetcher.validate_ohlc(df, "X")), 0)

    def test_drops_nan_price(self):
        df = _ohlcv([(100, 101, 99, np.nan, 10)])
        self.assertEqual(len(fetcher.validate_ohlc(df, "X")), 0)

    def test_keeps_good_drops_bad_mixed(self):
        df = _ohlcv([
            (100, 101, 99, 100.5, 10),   # good
            (100, 99, 101, 100, 10),     # bad: low>high
            (100.5, 102, 100, 101, 12),  # good
            (0, 5, 0, 3, 8),             # bad: zero price
        ])
        out = fetcher.validate_ohlc(df, "X")
        self.assertEqual(len(out), 2)
        self.assertListEqual(list(out["close"]), [100.5, 101])

    def test_boundary_values_are_valid(self):
        # open==low, close==high are within [low, high] -> kept
        df = _ohlcv([(99, 101, 99, 101, 0)])  # volume 0 is allowed (>=0)
        self.assertEqual(len(fetcher.validate_ohlc(df, "X")), 1)


class TestFetchYfinance(unittest.TestCase):
    @mock.patch("src.data.fetcher.time.sleep")
    @mock.patch("src.data.fetcher.yf.Ticker")
    def test_success_normalizes_columns_and_strips_tz(self, mock_ticker, mock_sleep):
        mock_ticker.return_value.history.return_value = _yf_history(n=5)
        df = fetcher.fetch_yfinance("TQQQ", "2024-01-01", "2024-02-01", "1d")
        self.assertListEqual(list(df.columns), ["open", "high", "low", "close", "volume"])
        self.assertIsNone(df.index.tz)            # tz stripped
        self.assertTrue((df.index == df.index.normalize()).all())  # daily normalized
        self.assertEqual(len(df), 5)
        mock_sleep.assert_not_called()

    @mock.patch("src.data.fetcher.time.sleep")
    @mock.patch("src.data.fetcher.yf.Ticker")
    def test_retries_then_succeeds(self, mock_ticker, mock_sleep):
        hist = mock_ticker.return_value.history
        hist.side_effect = [Exception("transient"), _yf_history(n=3)]
        df = fetcher.fetch_yfinance("X", "2024-01-01", "2024-02-01", "1d", max_retries=4)
        self.assertEqual(len(df), 3)
        self.assertEqual(hist.call_count, 2)
        mock_sleep.assert_called_once_with(2)     # 2**(0+1)

    @mock.patch("src.data.fetcher.time.sleep")
    @mock.patch("src.data.fetcher.yf.Ticker")
    def test_exponential_backoff_then_raises(self, mock_ticker, mock_sleep):
        hist = mock_ticker.return_value.history
        hist.side_effect = Exception("down")
        with self.assertRaises(Exception):
            fetcher.fetch_yfinance("X", "2024-01-01", "2024-02-01", "1d", max_retries=3)
        self.assertEqual(hist.call_count, 3)           # all attempts tried
        self.assertEqual(mock_sleep.call_count, 2)     # sleeps between attempts only
        mock_sleep.assert_has_calls([mock.call(2), mock.call(4)])

    @mock.patch("src.data.fetcher.time.sleep")
    @mock.patch("src.data.fetcher.yf.Ticker")
    def test_bad_rows_validated_out(self, mock_ticker, mock_sleep):
        # One row has low>high; fetch_yfinance runs validate_ohlc -> that row dropped.
        mock_ticker.return_value.history.return_value = _yf_history(n=5, bad_row=2)
        df = fetcher.fetch_yfinance("X", "2024-01-01", "2024-02-01", "1d")
        self.assertEqual(len(df), 4)


class TestCacheFreshness(unittest.TestCase):
    def test_fresh_then_stale_then_missing(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            self.assertTrue(fetcher._cache_is_fresh(path, max_age_hours=24))
            old = time.time() - 48 * 3600
            os.utime(path, (old, old))
            self.assertFalse(fetcher._cache_is_fresh(path, max_age_hours=24))
        finally:
            os.remove(path)
        self.assertFalse(fetcher._cache_is_fresh(path))  # missing file


if __name__ == "__main__":
    unittest.main()
