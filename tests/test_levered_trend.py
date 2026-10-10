"""Trend-timed leverage (src/research/levered_classes.py, docs/research/LEVERED_TREND_PROTOCOL.md)
and the domain report's verdict series (Domain.primary / Domain.sign)."""
import dataclasses
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
from src.research import allocation_stats as stats  # noqa: E402
from src.research import levered_classes as lv  # noqa: E402
from src.research import trials  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402
from src.research.daily_domains import DOMAINS, Context, Domain  # noqa: E402
from src.research.daily_trials import daily_family_members, family_name  # noqa: E402


def snapshot(assets, closes, *, opens=None):
    dates = closes.index
    opens = closes.shift(1).fillna(closes.iloc[0]) if opens is None else opens
    return Snapshot(sha="s" * 64, dates=dates, assets=tuple(assets), open=opens[assets],
                    close=closes[assets], dist=closes[assets] * 0.0,
                    dtb3=pd.Series(1.0, index=dates), manifest={})


def market(n=900, seed=3):
    """SPY rises, falls hard, then rises; SSO is 2x SPY daily from session 60."""
    dates = pd.bdate_range("2005-01-03", periods=n)
    drift = np.where((np.arange(n) > 400) & (np.arange(n) < 520), -0.004, 0.0006)
    r = drift + np.random.default_rng(seed).normal(0, 0.008, n)
    spy = 100 * np.cumprod(1 + r)
    sso = 50 * np.cumprod(1 + 2 * r)
    closes = pd.DataFrame({"SPY": spy, "SSO": sso}, index=dates)
    closes.loc[: dates[59], "SSO"] = np.nan
    return snapshot(["SPY", "SSO"], closes)


class Rule(unittest.TestCase):
    def setUp(self):
        self.snap = market()

    def point(self, schedule="daily", fund="SSO"):
        return {"class": "trend_timed", "params": {"fund": fund, "signal": "SPY", "sma": 200,
                                                   "schedule": schedule}}

    def test_daily_orders_only_on_a_change_of_state_and_only_while_listed(self):
        (t,) = lv.decide(self.snap, self.point())
        o = t.open_orders["SSO"]
        self.assertTrue(o.isin([0.0, 1.0]).all())
        self.assertTrue((o.diff().dropna() != 0).all(), "an order repeats the previous state")
        self.assertGreaterEqual(o.index[0], self.snap.dates[199])        # SMA defined
        self.assertIn(0.0, set(o))                                        # the crash exits
        self.assertEqual(lv.truncation_violations(self.snap, self.point(), [self.snap.dates[450]]), [])

    def test_the_tranched_schedule_is_twenty_one_monthly_tranches(self):
        ts = lv.decide(self.snap, self.point("tranched"))
        self.assertEqual(len(ts), 21)
        self.assertEqual(lv.truncation_violations(self.snap, self.point("tranched"),
                                                  [self.snap.dates[450]]), [])

    def test_the_grid_is_four_distinct_points_and_the_control_is_not_the_benchmark(self):
        g = lv.grid()
        self.assertEqual(len(g), 4)
        self.assertEqual(g[0], self.point())
        self.assertNotIn(lv.REFERENCE["class"], {p["class"] for p in g})
        self.assertEqual(stats.duplicate_points({str(p): lv.decide(self.snap, p) for p in g}), [])

    def test_scoring_waits_for_the_sma_and_the_fund(self):
        start = lv.scoring_start(self.snap)
        self.assertGreaterEqual(start, self.snap.dates[199])
        self.assertGreaterEqual(start, self.snap.dates[60 + lv.WARMUP - 1])

    def test_an_unadjusted_split_leg_is_caught_even_when_the_total_cancels(self):
        self.assertEqual(lv.leg_errors(self.snap), [])
        opens = self.snap.open.copy()
        day = self.snap.dates[300]
        opens.loc[day, "SSO"] = self.snap.close["SSO"].shift(1)[day] * 0.5   # night -50%, day +100%
        bad = snapshot(["SPY", "SSO"], self.snap.close, opens=opens)
        errs = lv.leg_errors(bad)
        self.assertTrue(any("night" in e for e in errs) and any("day" in e for e in errs), errs)


class Interaction(unittest.TestCase):
    def test_no_decay_benefit_when_the_levered_gap_is_exactly_l_times_the_1x_gap(self):
        idx = pd.bdate_range("2010-01-01", periods=500)
        rng = np.random.default_rng(0)
        uh = pd.Series(rng.normal(0.0004, 0.01, 500), index=idx)
        ut = uh.where(np.arange(500) % 3 != 0, 0.0)
        # Log returns constructed so lg(LT) - lg(LH) = 2 (lg(UT) - lg(UH)) exactly.
        lh = pd.Series(np.expm1(2 * np.log1p(uh)), index=idx)
        lt = pd.Series(np.expm1(2 * np.log1p(ut)), index=idx)
        out = lv.decay_interaction(lt, lh, ut, uh, n_boot=200)
        self.assertAlmostEqual(out["g"], 0.0, places=10)

    def test_avoiding_volatile_sessions_at_2x_shows_a_positive_interaction(self):
        idx = pd.bdate_range("2010-01-01", periods=2000)
        rng = np.random.default_rng(1)
        calm = (np.arange(2000) // 250) % 2 == 0
        uh = pd.Series(np.where(calm, rng.normal(0.0005, 0.006, 2000), rng.normal(0.0, 0.03, 2000)), index=idx)
        ut = uh.where(calm, 0.0)
        lh, lt = 2 * uh, (2 * uh).where(calm, 0.0)       # daily reset: 2x the daily return
        out = lv.decay_interaction(lt, lh, ut, uh, n_boot=300)
        self.assertGreater(out["g"], 0.0)
        self.assertGreater(out["ci95"][0], 0.0)


class Registry(unittest.TestCase):
    def test_the_new_domains_are_registered_with_their_verdict_series(self):
        lev = DOMAINS["levered_trend"]
        self.assertEqual((lev.primary, lev.sign, lev.prior_search_trials), ("vol_matched", 1, 7))
        self.assertEqual(family_name("levered_trend"), "levered_trend.v1")
        self.assertEqual(DOMAINS["lottery_product_long"].sign, -1)
        self.assertEqual(DOMAINS["lottery_product_recent"].sign, -1)
        for name in ("momentum_product_long", "momentum_product_recent", "beta_pair_product"):
            self.assertEqual((DOMAINS[name].primary, DOMAINS[name].sign), ("vol_matched", 1))
        self.assertEqual(DOMAINS["spinoff_product"].primary, "active")      # earlier domains unchanged

    def test_a_domain_refuses_an_unknown_verdict_series(self):
        with self.assertRaises(ValueError):
            dataclasses.replace(DOMAINS["levered_trend"], primary="raw")
        with self.assertRaises(ValueError):
            dataclasses.replace(DOMAINS["levered_trend"], sign=0)


class SignedReport(unittest.TestCase):
    """A sign -1 domain ranks, tests and deflates the NEGATED vol-matched series."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(trials, "LEDGER_DIR", Path(self._tmp.name) / "ledger")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self._tmp.cleanup()

    def test_the_benchmark_beating_a_lottery_product_is_what_the_report_ranks_first(self):
        n = 1500
        dates = pd.bdate_range("2011-01-03", periods=n)
        rng = np.random.default_rng(5)
        m = rng.normal(0.0005, 0.01, n)
        closes = pd.DataFrame({
            "SPY": 100 * np.cumprod(1 + m),
            "FPX": 100 * np.cumprod(1 + 1.5 * m - 0.0006 + rng.normal(0, 0.004, n)),   # beta, no alpha
            "SPHB": 100 * np.cumprod(1 + m + 0.0002 + rng.normal(0, 0.004, n))},        # small alpha
            index=dates)
        snap = snapshot(["SPY", "FPX", "SPHB"], closes)
        domain: Domain = DOMAINS["lottery_product_long"]
        ctx = Context(snap=snap)
        domain_search.run(domain, ctx, "v1")
        rep = domain_search.report(domain, ctx)
        rows = {r["label"]: r for r in rep["rows"]}
        fpx = next(r for lab, r in rows.items() if "FPX" in lab)
        self.assertLess(fpx["vol_matched_sharpe"], 0.0)
        self.assertAlmostEqual(fpx["primary_sharpe"], -fpx["vol_matched_sharpe"])
        self.assertIn("FPX", rep["best"])
        self.assertEqual((rep["primary"], rep["sign"]), ("vol_matched", -1))
        refs = daily_family_members(trials.iter_trials(), family_name(domain.name, reference=True))
        self.assertEqual(len(refs), 1)


if __name__ == "__main__":
    unittest.main()
