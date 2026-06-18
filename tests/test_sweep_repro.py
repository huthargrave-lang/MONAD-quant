"""
Tests for the sweep reproducibility fingerprint (src/optimization/sweep_repro.py) — C7.

A saved sweep result must record which data it ran on so it can be reproduced.
These pin that the fingerprint captures the window/bar-count and that its content
hash is stable for identical data and changes when any bar changes.
"""
import unittest

import numpy as np
import pandas as pd

from src.optimization.sweep_repro import data_fingerprint


def _df(n=5, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    c = rng.uniform(10, 20, n)
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1,
                         "close": c, "volume": rng.integers(1, 100, n)}, index=idx)


class TestDataFingerprint(unittest.TestCase):
    def test_window_and_count(self):
        df = _df(5)
        fp = data_fingerprint(df, "2024-01-01", "2024-02-01")
        self.assertEqual(fp["n_bars"], 5)
        self.assertEqual(fp["requested_start"], "2024-01-01")
        self.assertEqual(fp["requested_end"], "2024-02-01")
        self.assertEqual(fp["first_bar"], str(df.index[0]))
        self.assertEqual(fp["last_bar"], str(df.index[-1]))
        self.assertIsInstance(fp["data_hash"], str)

    def test_hash_stable_for_identical_data(self):
        a, b = _df(8, seed=1), _df(8, seed=1)
        self.assertEqual(data_fingerprint(a)["data_hash"], data_fingerprint(b)["data_hash"])

    def test_hash_changes_when_a_bar_changes(self):
        a = _df(8, seed=1)
        b = a.copy()
        b.iloc[3, b.columns.get_loc("close")] += 0.01
        self.assertNotEqual(data_fingerprint(a)["data_hash"], data_fingerprint(b)["data_hash"])

    def test_hash_changes_with_different_window(self):
        self.assertNotEqual(
            data_fingerprint(_df(8, seed=1))["data_hash"],
            data_fingerprint(_df(10, seed=1))["data_hash"],
        )

    def test_empty_frame_is_safe(self):
        fp = data_fingerprint(_df(5).iloc[:0])
        self.assertEqual(fp["n_bars"], 0)
        self.assertIsNone(fp["data_hash"])
        self.assertIsNone(fp["first_bar"])

    def test_none_window_args(self):
        fp = data_fingerprint(_df(3))
        self.assertIsNone(fp["requested_start"])
        self.assertIsNone(fp["requested_end"])


if __name__ == "__main__":
    unittest.main()
