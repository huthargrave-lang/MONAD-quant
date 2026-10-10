"""The 1984-2005 miner/metal test's data build and screens (src/research/miner_preperiod.py)
and its domains, on synthetic data in the vendors' shapes. No network."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import domain_search  # noqa: E402
from src.research import commodity_classes as cc  # noqa: E402
from src.research import daily_data  # noqa: E402
from src.research import miner_preperiod as mp  # noqa: E402
from src.research import trials  # noqa: E402
from src.research.daily_domains import DOMAINS, Context  # noqa: E402
from src.strategy.counted import uncounted  # noqa: E402
from tests.test_bundesbank import message  # noqa: E402

SESSIONS = pd.bdate_range("1983-12-19", "1988-12-30")


def bars(close: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"Open": close, "Close": close, "Dividends": 0.0, "Capital Gains": 0.0,
                         "Stock Splits": 0.0})


def world(seed=0, holidays=(), gold_gaps=()):
    """(yahoo fetcher, bundesbank getter, true gold USD). Frankfurt shut on ``holidays``
    (no gold, no FX); gold alone missing on ``gold_gaps`` (unexplained)."""
    rng = np.random.default_rng(seed)
    n = len(SESSIONS)
    g = pd.Series(400 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=SESSIONS)
    xau = pd.Series(100 * np.exp(np.cumsum(1.5 * np.log(g).diff().fillna(0) + rng.normal(0, 0.008, n))),
                    index=SESSIONS)
    spx = pd.Series(160 * np.exp(np.cumsum(rng.normal(0.0004, 0.009, n))), index=SESSIONS)
    fx = pd.Series(2.5, index=SESSIONS)
    shut = set(pd.DatetimeIndex(holidays))
    gold_days = [d for d in SESSIONS if d not in shut and d not in set(pd.DatetimeIndex(gold_gaps))]
    fx_days = [d for d in SESSIONS if d not in shut]
    dem_kg = (g * fx * 32.1507466)

    def bbk(url):
        if "XAU" in url:
            return message({d.date().isoformat(): float(dem_kg[d]) for d in gold_days})
        return message({d.date().isoformat(): float(fx[d]) for d in fx_days})

    def yahoo(symbol, start, end):
        s = {"^GSPC": spx, "^XAU": xau}[symbol]
        return bars(s.loc[start:pd.Timestamp(end) - pd.Timedelta(days=1)])

    return yahoo, bbk, g


CASH = dict(fetch_cash=lambda a, b: pd.Series(8.0, index=SESSIONS),
            fetch_check=lambda a, b: pd.Series(8.0, index=SESSIONS))
SEG = mp.Segment("A", "1983-12-19", "1989-01-01", "1983-12-19", mp.GOLD_FFM)


class Build(unittest.TestCase):
    def test_carries_are_classified_and_the_snapshot_is_private(self):
        yahoo, bbk, _ = world(holidays=["1985-05-01", "1986-05-01"], gold_gaps=["1987-03-03"])
        with tempfile.TemporaryDirectory() as pub, tempfile.TemporaryDirectory() as priv:
            sha, gold = mp.build_segment(SEG, yahoo=yahoo, bbk_get=bbk, data_dir=Path(pub),
                                         private_dir=Path(priv), **CASH)
            self.assertEqual(gold.explained, ["1985-05-01", "1986-05-01"])
            self.assertEqual(gold.unexplained, ["1987-03-03"])
            self.assertFalse((Path(pub) / f"DS-{sha}.csv.gz").exists())
            snap = daily_data.load_snapshot(sha, data_dir=Path(pub), private_dir=Path(priv))
            self.assertEqual(set(snap.unreliable_opens), {"^GSPC", "^XAU", mp.GOLD_FFM})
            cal = snap.manifest["calendars"][mp.GOLD_FFM]
            self.assertNotIn("1985-05-01", cal)
            self.assertEqual(snap.manifest["gold_carries"]["unexplained"], ["1987-03-03"])
            self.assertIn("Bundesbank", snap.manifest["redistribution"])

    def test_too_many_unexplained_carries_close_the_test_not_run(self):
        gaps = list(SESSIONS[100:300:20])                       # 10 of ~1300 sessions > 0.5%
        yahoo, bbk, _ = world(gold_gaps=gaps)
        with tempfile.TemporaryDirectory() as pub, tempfile.TemporaryDirectory() as priv, \
                self.assertRaises(mp.NotRun):
            mp.build_segment(SEG, yahoo=yahoo, bbk_get=bbk, data_dir=Path(pub), private_dir=Path(priv), **CASH)


class Screens(unittest.TestCase):
    def test_coverage_extreme_moves_and_world_bank(self):
        idx = pd.bdate_range("1990-01-01", "1991-12-31")
        close = pd.Series(np.linspace(100, 120, len(idx)), index=idx)
        close.iloc[10:30] = close.iloc[9]                        # 20 stale prints in 1990
        cov = mp.xau_coverage(close)
        self.assertLess(cov[1990], 0.98)
        self.assertGreater(cov[1991], 0.98)
        jump = close.copy()
        jump.iloc[300] *= 1.2
        moves = mp.extreme_moves(jump)
        self.assertEqual(len(moves), 2)                          # up, then back down
        funds = pd.DataFrame({"F1": jump.values, "F2": jump.values}, index=idx)
        self.assertTrue(all(v["confirmed"] for v in mp.fund_confirms(moves, funds).values()))
        wb = pd.Series({pd.Period("1990-01", "M"): 100.0, pd.Period("1990-02", "M"): 100.0})
        gold = pd.Series(100.0, index=idx)
        gold.loc["1990-02"] = 104.0
        rep = mp.world_bank_check(gold, [d.date().isoformat() for d in idx], wb)
        self.assertEqual(list(rep["months_beyond_tolerance"]), ["1990-02"])


class Domains(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(trials, "LEDGER_DIR", Path(self._tmp.name) / "ledger")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self._tmp.cleanup()

    def snapshot(self, **kw):
        yahoo, bbk, g = world(**kw)
        d = Path(self._tmp.name)
        sha, _ = mp.build_segment(SEG, yahoo=yahoo, bbk_get=bbk, data_dir=d / "pub", private_dir=d / "priv", **CASH)
        return daily_data.load_snapshot(sha, data_dir=d / "pub", private_dir=d / "priv"), g

    def test_counted_search_runs_at_the_close_with_no_lookahead(self):
        snap, _ = self.snapshot(holidays=["1986-05-01", "1987-05-01"])
        dom = DOMAINS["miner_preperiod_a"]
        ctx = Context(snap=snap)
        domain_search.run(dom, ctx, "v1")
        rep = domain_search.report(dom, ctx)
        self.assertEqual(rep["lookahead_violations"], {})
        (pt,) = dom.grid()
        cal = set(pd.to_datetime(snap.manifest["calendars"][mp.GOLD_FFM]))
        for t in dom.decide(ctx, pt):
            self.assertTrue(t.open_orders.empty)
            executed = [snap.dates[snap.dates.get_loc(d) + 1] for d in t.close_orders.index]
            self.assertTrue(all(e in cal for e in executed), "an execution fell on a carried fixing")
        self.assertGreaterEqual(rep["window"][0], "1984-03-01")

    def test_gold_that_moves_only_after_the_fixing_earns_nothing(self):
        """The fixing (midday Frankfurt) lags the miner close (16:00 New York): build gold as
        the miner's own driver delayed one session. Deciding at the close and trading at the
        next close must not harvest that catch-up: the active mean is indistinguishable
        from zero."""
        rng = np.random.default_rng(3)
        n = 6000
        dates = pd.bdate_range("1970-01-01", periods=n)
        true = np.cumsum(rng.normal(0, 0.01, n))
        miner = pd.Series(100 * np.exp(true), index=dates)
        fix = pd.Series(100 * np.exp(np.r_[0.0, true[:-1]]), index=dates)        # one session late
        close = pd.DataFrame({"^GSPC": miner, "^XAU": miner, mp.GOLD_FFM: fix})
        snap = daily_data.Snapshot(sha="z" * 64, dates=dates, assets=tuple(close.columns),
                                   open=close.shift(1).fillna(close.iloc[0]), close=close,
                                   dist=close * 0.0, dtb3=pd.Series(0.0, index=dates),
                                   manifest={"calendars": {mp.GOLD_FFM: [d.date().isoformat() for d in dates]}})
        from src.research.daily_strategy import evaluate_daily
        pt = cc.ratio_point("^XAU", mp.GOLD_FFM, execution="close", fixings=True)
        ref = cc.ratio_reference("^XAU", mp.GOLD_FFM, execution="close", fixings=True)
        with uncounted("synthetic panel: the fixing-lag mechanism, no instrument measured"):
            a = evaluate_daily(cc.decide_ratio(snap, pt), snap, start=dates[200],
                               tiers={"^XAU": "tier1", mp.GOLD_FFM: "tier1"}, cost_multiple=1e-9).returns
            b = evaluate_daily(cc.decide_ratio(snap, ref), snap, start=dates[200],
                               tiers={"^XAU": "tier1", mp.GOLD_FFM: "tier1"}, cost_multiple=1e-9).returns
        active = a - b
        t = active.mean() / active.std() * np.sqrt(len(active))
        self.assertLess(abs(t), 3.0, f"the fixing lag leaked into the tilt (t {t:+.2f})")

    def test_positive_control_a_truly_reverting_ratio_is_harvested(self):
        """The same machinery on a ratio that genuinely mean-reverts (AR(1), rho 0.95, a
        14-session half-life) must earn: the zero above is not a dead test."""
        rng = np.random.default_rng(4)
        n = 6000
        dates = pd.bdate_range("1970-01-01", periods=n)
        gold = np.cumsum(rng.normal(0, 0.01, n))
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = 0.95 * x[i - 1] + rng.normal(0, 0.01)
        close = pd.DataFrame({"^GSPC": 100 * np.exp(gold + x), "^XAU": 100 * np.exp(gold + x),
                              mp.GOLD_FFM: 100 * np.exp(gold)}, index=dates)
        snap = daily_data.Snapshot(sha="p" * 64, dates=dates, assets=tuple(close.columns),
                                   open=close.shift(1).fillna(close.iloc[0]), close=close,
                                   dist=close * 0.0, dtb3=pd.Series(0.0, index=dates),
                                   manifest={"calendars": {mp.GOLD_FFM: [d.date().isoformat() for d in dates]}})
        from src.research.daily_strategy import evaluate_daily
        pt = cc.ratio_point("^XAU", mp.GOLD_FFM, execution="close", fixings=True)
        ref = cc.ratio_reference("^XAU", mp.GOLD_FFM, execution="close", fixings=True)
        with uncounted("synthetic panel: positive control for the reversion harvest"):
            a = evaluate_daily(cc.decide_ratio(snap, pt), snap, start=dates[200],
                               tiers={"^XAU": "tier1", mp.GOLD_FFM: "tier1"}, cost_multiple=1e-9).returns
            b = evaluate_daily(cc.decide_ratio(snap, ref), snap, start=dates[200],
                               tiers={"^XAU": "tier1", mp.GOLD_FFM: "tier1"}, cost_multiple=1e-9).returns
        active = a - b
        t = active.mean() / active.std() * np.sqrt(len(active))
        self.assertGreater(t, 3.0, f"a genuinely reverting ratio was not harvested (t {t:+.2f})")


if __name__ == "__main__":
    unittest.main()


class Report(unittest.TestCase):
    """tools/miner_preperiod_report.py: the verdict logic, the noise estimator, the timing
    split, and the noise-only placebo end to end on a synthetic segment."""

    @classmethod
    def setUpClass(cls):
        import miner_preperiod_report as rep
        cls.rep = rep

    def series(self, mu, n=4000, seed=0):
        rng = np.random.default_rng(seed)
        return pd.Series(rng.normal(mu, 0.005, n), index=pd.bdate_range("1984-01-02", periods=n))

    def test_verdict_needs_every_gate_and_promotion_needs_p_times_six(self):
        strong = self.series(0.0006)                              # t ~ 7.6
        kw = dict(stress2=strong - 0.0001, lag1=1.0, lag6=0.8, noise_ok=True, noise_bound_ok=True,
                  drop_one=[0.5, 0.5, 0.5, 0.5], placebo_blocks=False)
        v = self.rep.verdict(strong, **kw)
        self.assertEqual(v["verdict"], "corroborates")
        self.assertTrue(v["promoted"])
        for gate, value in (("noise_ok", False), ("noise_bound_ok", False), ("lag6", 0.3)):
            with self.subTest(gate=gate):
                self.assertEqual(self.rep.verdict(strong, **{**kw, gate: value})["verdict"], "uninformative")
        self.assertFalse(self.rep.verdict(strong, **{**kw, "placebo_blocks": True})["promoted"])
        self.assertFalse(self.rep.verdict(strong, **{**kw, "drop_one": [0.5, -0.1, 0.5, 0.5]})["promoted"])
        losing = self.series(-0.0003)
        v = self.rep.verdict(losing, **kw)
        self.assertEqual(v["verdict"], "contradicts")
        self.assertTrue(v["clean_fail_closes_lead"])
        self.assertTrue(self.rep.verdict(strong, **{**kw, "lag6": -0.1})["clean_fail_closes_lead"])

    def test_noise_variance_recovers_iid_noise_and_is_zero_for_a_random_walk(self):
        rng = np.random.default_rng(1)
        rw = pd.Series(np.cumsum(rng.normal(0, 0.01, 20000)))
        self.assertLess(self.rep.noise_variance(rw), 2e-6)
        noisy = rw + rng.normal(0, 0.005, len(rw))
        self.assertAlmostEqual(self.rep.noise_variance(noisy), 0.005 ** 2, delta=0.4 * 0.005 ** 2)

    def test_noise_placebo_runs_the_exact_evaluator_on_synthetic_panels(self):
        yahoo, bbk, _ = world(seed=5)
        d = Path(tempfile.mkdtemp())
        sha, _ = mp.build_segment(SEG, yahoo=yahoo, bbk_get=bbk, data_dir=d / "pub", private_dir=d / "priv", **CASH)
        snap = daily_data.load_snapshot(sha, data_dir=d / "pub", private_dir=d / "priv")
        out = self.rep.noise_placebo(snap, "miner_preperiod_a", 0.002, sims=2, rhos=(0.5,), workers=1)
        self.assertEqual(set(out), {"0.5"})
        self.assertTrue(np.isfinite(out["0.5"]["p95"]))
