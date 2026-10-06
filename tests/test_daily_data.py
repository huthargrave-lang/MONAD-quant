"""
Daily data snapshots (src/research/daily_data.py): canonical encoding and content
addressing, tamper refusal, validation refusals, and the return conventions.
"""
import gzip
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import daily_data as dd  # noqa: E402

DATES = pd.bdate_range("2012-01-02", periods=dd.MIN_SESSIONS + 10)


def asset(seed, start=0, splits=None):
    rng = np.random.default_rng(seed)
    n = len(DATES)
    close = 50 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    opens = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, 0.004, n))
    df = pd.DataFrame({"Open": opens, "Close": close, "Dividends": 0.0, "Capital Gains": 0.0,
                       "Stock Splits": 0.0}, index=DATES)
    df.iloc[100, df.columns.get_loc("Dividends")] = 0.25
    return df.iloc[start:]


def fetchers(**overrides):
    panel = {"AAA": asset(1), "BBB": asset(2, start=30)}
    panel.update(overrides)
    cash = pd.Series(2.0, index=DATES)
    return dict(fetch_asset=lambda s, a, b: panel[s], fetch_cash=lambda a, b: cash,
                fetch_check=lambda a, b: cash + 0.01)


class Building(unittest.TestCase):
    def test_round_trip_is_content_addressed_and_lossless(self):
        with tempfile.TemporaryDirectory() as td:
            sha = dd.build_snapshot(["AAA", "BBB"], "2012-01-01", "2016-12-31",
                                    data_dir=Path(td), **fetchers())
            snap = dd.load_snapshot(sha, data_dir=Path(td))
            self.assertEqual(snap.assets, ("AAA", "BBB"))
            self.assertTrue(snap.close["BBB"].iloc[:30].isna().all())
            self.assertAlmostEqual(float(snap.close["AAA"].iloc[5]), float(asset(1)["Close"].iloc[5]),
                                   places=12)
            again = dd.build_snapshot(["AAA", "BBB"], "2012-01-01", "2016-12-31",
                                      data_dir=Path(td), **fetchers())
            self.assertEqual(sha, again, "the same data must name the same snapshot")

    def test_a_tampered_snapshot_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            sha = dd.build_snapshot(["AAA", "BBB"], "2012-01-01", "2016-12-31",
                                    data_dir=Path(td), **fetchers())
            path = Path(td) / f"DS-{sha}.csv.gz"
            raw = gzip.decompress(path.read_bytes()).replace(b",2.0,", b",2.5,", 1)
            path.write_bytes(gzip.compress(raw))
            with self.assertRaises(dd.SnapshotError):
                dd.load_snapshot(sha, data_dir=Path(td))


class Validation(unittest.TestCase):
    def build(self, **f):
        return dd.build_frames(["AAA", "BBB"], "2012-01-01", "2016-12-31", **f)

    def test_a_good_panel_passes(self):
        frames, report = self.build(**fetchers())
        self.assertEqual(report["sessions"], len(DATES))

    def test_synthesised_opens_are_refused(self):
        bad = asset(1)
        bad["Open"] = bad["Close"].shift(1).fillna(bad["Close"].iloc[0])
        with self.assertRaises(dd.SnapshotError) as cm:
            self.build(**fetchers(AAA=bad))
        self.assertIn("opens are not real", str(cm.exception))

    def test_tick_bound_prices_with_genuinely_equal_opens_pass(self):
        """A short-bond ETF's price barely moves: equal opens track unchanged closes."""
        quiet = asset(1)
        rng = np.random.default_rng(3)
        moves = rng.choice([0.0, 0.01, -0.01], size=len(quiet), p=[0.4, 0.3, 0.3])
        close = 80 + np.cumsum(moves)
        quiet["Close"] = close
        quiet["Open"] = np.where(rng.random(len(quiet)) < 0.5, np.r_[close[0], close[:-1]], close)
        frames, _ = self.build(**fetchers(AAA=quiet))
        self.assertIn("AAA", frames["close"].columns)

    def test_an_unadjusted_split_is_refused(self):
        bad = asset(1)
        bad.iloc[500:, [0, 1]] = bad.iloc[500:, [0, 1]] / 3.0
        with self.assertRaises(dd.SnapshotError):
            self.build(**fetchers(AAA=bad))

    def test_a_hole_after_listing_is_refused(self):
        bad = asset(1)
        bad.iloc[400, bad.columns.get_loc("Close")] = np.nan
        with self.assertRaises(dd.SnapshotError):
            self.build(**fetchers(AAA=bad))

    def test_cash_that_disagrees_with_its_cross_check_is_refused(self):
        f = fetchers()
        f["fetch_check"] = lambda a, b: pd.Series(4.0, index=DATES)
        with self.assertRaises(dd.SnapshotError):
            self.build(**f)

    def test_a_long_cash_gap_is_refused(self):
        f = fetchers()
        cash = pd.Series(2.0, index=DATES).drop(DATES[200:210])
        f["fetch_cash"] = lambda a, b: cash
        with self.assertRaises(dd.SnapshotError):
            self.build(**f)


class Conventions(unittest.TestCase):
    def test_bond_equivalent_yield(self):
        # 5% discount on a 91-day bill: price 98.736; BEY = (100/98.736 - 1) * 365/91.
        bey = float(dd.bond_equivalent_yield(pd.Series([5.0])).iloc[0])
        price = 100 * (1 - 0.05 * 91 / 360)
        self.assertAlmostEqual(bey, (100 / price - 1) * 365 / 91, places=12)

    def test_common_start_waits_for_the_latest_listing_plus_warmup(self):
        frames, report = dd.build_frames(["AAA", "BBB"], "2012-01-01", "2016-12-31", **fetchers())
        snap = dd.Snapshot(sha="x", dates=frames["open"].index, assets=("AAA", "BBB"),
                           open=frames["open"], close=frames["close"], dist=frames["dist"],
                           dtb3=frames["dtb3"], manifest={})
        self.assertEqual(dd.common_start(snap, ["AAA", "BBB"], 10), DATES[30 + 10])


if __name__ == "__main__":
    unittest.main()
