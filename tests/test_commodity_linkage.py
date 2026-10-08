"""Commodity linkage confirmation rules (src/research/commodity_classes.py) and the frozen
futures panel (src/research/futures_panel.py)."""
import gzip
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import commodity_classes as cc  # noqa: E402
from src.research import futures_panel as fp  # noqa: E402
from src.research.daily_data import Snapshot, SnapshotError  # noqa: E402
from src.research.daily_domains import DOMAINS  # noqa: E402
from src.research.daily_trials import family_name  # noqa: E402

DATES = pd.bdate_range("2015-01-02", "2017-12-29")


def snap(cols):
    rng = np.random.default_rng(2)
    close = pd.DataFrame({c: 50 * np.exp(np.cumsum(rng.normal(0, 0.015, len(DATES)))) for c in cols},
                         index=DATES)
    return Snapshot(sha="s" * 64, dates=DATES, assets=tuple(cols), open=close.shift(1).fillna(close.iloc[0]),
                    close=close, dist=close * 0.0, dtb3=pd.Series(1.0, index=DATES), manifest={})


def panel(values=None):
    days = pd.bdate_range("2014-06-02", "2017-12-29")
    v = values if values is not None else 60 + 10 * np.sin(np.arange(len(days)) / 40.0)
    return fp.FuturesPanel(sha="f" * 64, close=pd.DataFrame({"CL=F": v}, index=days), manifest={})


class Ratio(unittest.TestCase):
    def setUp(self):
        self.snap = snap(["SPY", "GDX", "GLD"])
        self.point = cc.ratio_grid()[0]

    def test_weights_tilt_against_the_ratio_and_stay_long_only(self):
        w = cc.ratio_weights(self.snap, self.point["params"])
        self.assertTrue(((w >= 0) & (w <= 1)).all().all())
        self.assertTrue(np.allclose(w.sum(axis=1), 1.0))
        tr = np.log(self.snap.close["GDX"] / self.snap.close["GLD"])
        z = (tr - tr.rolling(60).mean()) / tr.rolling(60).std()
        cheap = z[z < -1].index.intersection(w.index)
        self.assertTrue((w.loc[cheap, "GDX"] > 0.5).all())

    def test_twenty_one_tranches_no_lookahead_and_the_window_opens_in_2016(self):
        ts = cc.decide_ratio(self.snap, self.point)
        self.assertEqual(len(ts), 21)
        self.assertEqual(cc.ratio_truncation(self.snap, self.point, [DATES[400]]), [])
        self.assertGreaterEqual(cc.ratio_start(self.snap), pd.Timestamp("2016-01-01"))


class Trend(unittest.TestCase):
    def setUp(self):
        self.snap = snap(["SPY", "XLE"])
        self.point = cc.trend_grid()[0]

    def test_state_reads_the_future_on_or_before_each_session_and_flips_both_ways(self):
        st = cc.trend_state(self.snap, panel(), self.point["params"])
        self.assertEqual(set(st.dropna().unique()), {0.0, 1.0})
        (t,) = cc.decide_trend(self.snap, panel(), self.point)
        o = t.open_orders["XLE"]
        self.assertTrue((o.diff().dropna() != 0).all())

    def test_a_negative_print_is_kept_and_no_order_reads_the_future(self):
        p = panel()
        p.close.iloc[300, 0] = -37.63
        self.assertEqual(cc.trend_truncation(self.snap, p, self.point, [DATES[450]]), [])
        self.assertGreaterEqual(cc.trend_start(self.snap, p), pd.Timestamp("2016-01-01"))


class Panel(unittest.TestCase):
    def test_round_trip_hash_and_tamper_refusal(self):
        days = pd.bdate_range("2015-01-02", periods=30)
        fetch = lambda s, a, b: pd.Series(np.linspace(50, -5, 30), index=days)    # noqa: E731
        with tempfile.TemporaryDirectory() as d:
            sha = fp.build(["CL=F"], "2015-01-01", "2016-01-01", fetch=fetch, data_dir=Path(d))
            p = fp.load(sha, data_dir=Path(d))
            self.assertAlmostEqual(p.close["CL=F"].iloc[-1], -5.0)
            self.assertTrue(p.manifest["non_positive"]["CL=F"])
            f = Path(d) / f"FUT-{sha}.csv.gz"
            altered = gzip.decompress(f.read_bytes()).replace(b"-5.0", b"-4.0")
            f.write_bytes(gzip.compress(altered))
            with self.assertRaises(SnapshotError):
                fp.load(sha, data_dir=Path(d))

    def test_a_fetch_past_the_bound_is_refused(self):
        days = pd.bdate_range("2015-12-20", periods=30)
        with tempfile.TemporaryDirectory() as d, self.assertRaises(SnapshotError):
            fp.build(["CL=F"], "2015-01-01", "2016-01-01",
                     fetch=lambda s, a, b: pd.Series(1.0, index=days), data_dir=Path(d))


class Registry(unittest.TestCase):
    def test_both_domains_charge_the_atlas_and_declare_their_verdict_series(self):
        r, t = DOMAINS["miner_metal_ratio"], DOMAINS["oil_trend_equities"]
        self.assertEqual((r.primary, r.sign, r.prior_search_trials), ("active", 1, 1401))
        self.assertEqual((t.primary, t.sign, t.panel_prefix), ("vol_matched", 1, "FUT"))
        self.assertEqual(family_name("oil_trend_equities"), "oil_trend_equities.v1")


if __name__ == "__main__":
    unittest.main()


class Replication(unittest.TestCase):
    def test_the_replication_domains_run_the_same_frozen_rule_on_their_own_pair(self):
        for name, pair in (("silver_miner_ratio", ("SIL", "SLV")), ("junior_miner_ratio", ("GDXJ", "GLD")),
                           ("gold_silver_ratio", ("GLD", "SLV")), ("placebo_ratio", ("IWM", "SPY"))):
            d = DOMAINS[name]
            (pt,) = d.grid()
            self.assertEqual((pt["params"]["miner"], pt["params"]["metal"]), pair)
            self.assertEqual((pt["params"]["window"], pt["params"]["slope"]), (60, 0.25))
            self.assertEqual(d.reference["params"]["weights"], {pair[0]: 0.5, pair[1]: 0.5})
            self.assertEqual(d.prior_search_trials, 2)
        self.assertEqual(DOMAINS["miner_metal_ratio"].grid(), cc.ratio_grid())     # unchanged

    def test_the_trigger_needs_every_condition(self):
        sys.path.insert(0, str(REPO / "tools"))
        import miner_tilt_replication as mt
        idx = pd.bdate_range("2016-01-04", periods=2700)
        rng = np.random.default_rng(4)
        base = pd.Series(rng.normal(0.0004, 0.004, len(idx)), index=idx)
        series = {"miner_metal_ratio": base + rng.normal(0, 0.004, len(idx)),
                  "silver_miner_ratio": base + rng.normal(0.0003, 0.004, len(idx)),
                  "junior_miner_ratio": base + rng.normal(0, 0.004, len(idx)),
                  "gold_silver_ratio": pd.Series(rng.normal(0, 0.004, len(idx)), index=idx),
                  "placebo_ratio": pd.Series(rng.normal(0, 0.004, len(idx)), index=idx)}
        good = mt.evaluate(series, cc.ERAS, spa_worst_p=0.01)
        self.assertTrue(good["register"], good["trigger"])
        self.assertFalse(mt.evaluate(series, cc.ERAS, spa_worst_p=0.02)["register"])    # 0.02 x 3 > 0.05
        self.assertGreater(good["contamination"]["miner_metal_ratio"]["beta"], 0.2)
