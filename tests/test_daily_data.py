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


class CloseOnly(unittest.TestCase):
    """Close-only series (an old index, a daily fixing): opens rebuilt from the previous
    close and flagged, so no strategy can trade them at an open that never printed."""

    def fixing(self):
        df = asset(3)
        df["Open"] = np.nan                      # a fixing has no open at all
        return df

    def test_opens_are_the_previous_close_and_the_asset_is_flagged(self):
        frames, report = dd.build_frames(["AAA", "FIX"], "2012-01-01", "2016-12-31",
                                         close_only=["FIX"], **fetchers(FIX=self.fixing()))
        o, c = frames["open"]["FIX"], frames["close"]["FIX"]
        self.assertTrue(np.allclose(o.iloc[1:].to_numpy(), c.shift(1).iloc[1:].to_numpy()))
        self.assertEqual(o.iloc[0], c.iloc[0])
        self.assertTrue(report["assets"]["FIX"]["opens_unreliable"])
        self.assertTrue(report["assets"]["FIX"]["close_only"])
        self.assertNotIn("close_only", report["assets"]["AAA"])

    def test_without_the_flag_a_series_with_no_opens_is_refused(self):
        with self.assertRaises(dd.SnapshotError):
            dd.build_frames(["AAA", "FIX"], "2012-01-01", "2016-12-31", **fetchers(FIX=self.fixing()))

    def test_close_only_and_sources_must_name_universe_assets(self):
        with self.assertRaises(dd.SnapshotError):
            dd.build_frames(["AAA"], "2012-01-01", "2016-12-31", close_only=["ZZZ"], **fetchers())
        with tempfile.TemporaryDirectory() as td, self.assertRaises(dd.SnapshotError):
            dd.build_snapshot(["AAA"], "2012-01-01", "2016-12-31", asset_sources={"ZZZ": "x"},
                              data_dir=Path(td), **fetchers())

    def test_the_manifest_records_close_only_assets_and_their_sources(self):
        with tempfile.TemporaryDirectory() as td:
            sha = dd.build_snapshot(["AAA", "FIX"], "2012-01-01", "2016-12-31", close_only=["FIX"],
                                    asset_sources={"FIX": "a fixing"}, data_dir=Path(td),
                                    **fetchers(FIX=self.fixing()))
            snap = dd.load_snapshot(sha, data_dir=Path(td))
            self.assertEqual(snap.manifest["sources"]["per_asset"], {"FIX": "a fixing"})
            self.assertEqual(snap.manifest["sources"]["close_only"], ["FIX"])
            self.assertIn("FIX", snap.unreliable_opens)


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

    def test_a_real_crash_move_corroborated_by_another_source_is_kept(self):
        crash = asset(1)
        crash.iloc[500:, [0, 1]] = crash.iloc[500:, [0, 1]] * 1.8        # +80% in one session
        independent = crash["Close"].iloc[[495, 503]]                    # another source agrees
        frames, report = self.build(**fetchers(AAA=crash),
                                    independent_closes={"AAA": independent})
        self.assertIn(str(DATES[500].date()), report["assets"]["AAA"]["corroborated_extreme_sessions"])
        wrong = independent * 1.5                                         # it does not agree
        with self.assertRaises(dd.SnapshotError):
            self.build(**fetchers(AAA=crash), independent_closes={"AAA": wrong})

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


class PrivateStore(unittest.TestCase):
    """Non-redistributable observations stay in a private store; only the manifest is
    public, and the loader still verifies the bytes against the sha."""

    def test_private_snapshot_round_trip_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as pub, tempfile.TemporaryDirectory() as priv:
            sha = dd.build_snapshot(["AAA", "BBB"], "2012-01-01", "2016-12-31", private=True,
                                    manifest_extra={"calendars": {"AAA": ["2012-01-03"]}},
                                    data_dir=Path(pub), private_dir=Path(priv), **fetchers())
            self.assertFalse((Path(pub) / f"DS-{sha}.csv.gz").exists())
            self.assertTrue((Path(priv) / f"DS-{sha}.csv.gz").exists())
            snap = dd.load_snapshot(sha, data_dir=Path(pub), private_dir=Path(priv))
            self.assertEqual(snap.manifest["observations"]["csv_sha256"], sha)
            self.assertEqual(snap.manifest["calendars"], {"AAA": ["2012-01-03"]})
            with self.assertRaises(dd.SnapshotError) as err:
                dd.load_snapshot(sha, data_dir=Path(pub))          # private store not searched
            self.assertIn("private", str(err.exception))
            p = Path(priv) / f"DS-{sha}.csv.gz"
            raw = gzip.decompress(p.read_bytes()).replace(b",2.0,", b",2.5,", 1)
            p.write_bytes(gzip.compress(raw))
            with self.assertRaises(dd.SnapshotError):
                dd.load_snapshot(sha, data_dir=Path(pub), private_dir=Path(priv))

    def test_manifest_extra_cannot_override_core_fields(self):
        with tempfile.TemporaryDirectory() as td, self.assertRaises(dd.SnapshotError):
            dd.build_snapshot(["AAA"], "2012-01-01", "2016-12-31", manifest_extra={"sha": "x"},
                              data_dir=Path(td), **fetchers())

    def test_the_private_store_is_gitignored(self):
        ignored = (REPO / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(f"{dd.PRIVATE_DATA_REL.as_posix()}/", ignored.splitlines())
