"""tools/credit_sleeve_mix.py (docs/research/CREDIT_SLEEVE_MIX_PROTOCOL.md) on synthetic series:
the mix, the lagged replica's ex-ante betas, the crisis regression, the proxy screen, the noise
band, the verdict map and the option-A guard; and F366206's committed result still reproduces
(the study must not change its sibling)."""
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import credit_sleeve_mix as csm  # noqa: E402
import sleeve_break_even  # noqa: E402


def sessions(start="2012-05-10", n=2600):
    return pd.bdate_range(start, periods=n)


def noise(idx, seed, scale=0.01, mean=0.0):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mean, scale, len(idx)), index=idx)


class TheMix(unittest.TestCase):
    def test_the_carve_is_pro_rata_and_rebalanced_each_session(self):
        idx = sessions(n=3)
        p = pd.Series([0.01, -0.02, 0.03], index=idx)
        s = pd.Series([0.00, 0.01, -0.01], index=idx)
        np.testing.assert_allclose(csm.mix(p, s, 0.10).to_numpy(), [0.009, -0.017, 0.026])

    def test_session_returns_reinvest_distributions_at_the_open(self):
        idx = sessions(n=3)
        r = csm.daily_data.SessionReturns(
            dates=idx, night=pd.DataFrame({"X": [np.nan, 0.01, -0.02]}, index=idx),
            day=pd.DataFrame({"X": [np.nan, 0.02, 0.01]}, index=idx), cash=pd.Series(0.0, index=idx))
        np.testing.assert_allclose(csm.session_total(r, "X").to_numpy(), [1.01 * 1.02 - 1, 0.98 * 1.01 - 1])

    def test_the_build_session_is_dropped(self):
        rec = pd.Series([0.5, 0.01, 0.02], index=sessions(n=3))
        self.assertEqual(list(csm.holding(rec)), [0.01, 0.02])

    def test_the_regime_cut_is_f46s(self):
        w = csm.regimes(pd.DatetimeIndex(["2022-07-29", "2022-08-01"]))
        self.assertEqual(list(w[csm.NEGATIVE]), [pd.Timestamp("2022-07-29")])
        self.assertEqual(list(w[csm.POSITIVE]), [pd.Timestamp("2022-08-01")])

    def test_block_sharpe_sums_whole_blocks_and_annualises_by_root_252_over_5(self):
        idx = sessions(n=12)                                   # two blocks; two sessions dropped
        r = pd.Series([0.01] * 5 + [0.03] * 5 + [9.0, 9.0], index=idx)
        b = np.array([0.05, 0.15])
        self.assertAlmostEqual(csm.block_sharpe(r, pd.Series(0.0, index=idx)),
                               b.mean() / b.std(ddof=1) * math.sqrt(252 / 5))


class TheReplica(unittest.TestCase):
    def setUp(self):
        self.idx = sessions(n=1500)
        self.cash = pd.Series(0.0001, index=self.idx)
        self.spy = noise(self.idx, 1, 0.012, 0.0004)
        self.ief = noise(self.idx, 2, 0.004, 0.0001)

    def lagged_sleeve(self):
        es, ei = self.spy - self.cash, self.ief - self.cash
        return (self.cash + 0.3 * es + 0.2 * es.shift(5) + 0.3 * ei).iloc[5:]

    def test_a_lagged_stock_bond_sleeve_is_replicated_lag_for_lag(self):
        sleeve = self.lagged_sleeve()
        rep, info = csm.replica(sleeve, self.spy, self.ief, self.cash)
        self.assertAlmostEqual(info["mean_beta_spy"], 0.5, places=6)
        self.assertAlmostEqual(info["mean_beta_ief"], 0.3, places=6)
        np.testing.assert_allclose(rep.to_numpy(), sleeve.reindex(rep.index).to_numpy(), atol=1e-9)

    def test_a_same_day_replica_would_not_match_a_lagged_sleeve(self):
        """The reason for the lag convention: the summed beta applied same-day misses."""
        sleeve = self.lagged_sleeve()
        rep, _ = csm.replica(sleeve, self.spy, self.ief, self.cash)
        same_day = self.cash + 0.5 * (self.spy - self.cash) + 0.3 * (self.ief - self.cash)
        self.assertGreater(float((same_day.reindex(rep.index) - sleeve.reindex(rep.index)).abs().max()), 1e-3)

    def test_it_starts_after_the_minimum_and_skips_the_incomplete_final_block(self):
        """Block 0 has no previous block for the Dimson lag, so the 52 usable blocks are 1-52
        and the first replica block is 53."""
        sleeve = noise(self.idx, 3, 0.005)
        rep, info = csm.replica(sleeve, self.spy, self.ief, self.cash)
        self.assertEqual(rep.index[0], self.idx[(csm.BETA_MIN + 1) * 5])
        self.assertEqual(info["sessions"], (len(self.idx) // 5 - csm.BETA_MIN - 1) * 5)

    def test_the_betas_are_ex_ante(self):
        """Rewriting the sleeve's future leaves every earlier replica session unchanged."""
        sleeve = noise(self.idx, 4, 0.005) + 0.4 * self.spy
        rep, _ = csm.replica(sleeve, self.spy, self.ief, self.cash)
        cut = self.idx[1000]                       # a block boundary: 1000 = 200 blocks of 5
        future = sleeve.copy()
        future[future.index >= cut] = noise(self.idx, 5, 0.03)[future.index >= cut]
        rep2, _ = csm.replica(future, self.spy, self.ief, self.cash)
        early = rep.index[rep.index < cut]
        pd.testing.assert_series_equal(rep.reindex(early), rep2.reindex(early))
        late = rep.index[rep.index >= self.idx[1100]]
        self.assertFalse(np.allclose(rep.reindex(late), rep2.reindex(late)))

    def test_it_refuses_a_gap_in_its_inputs(self):
        with self.assertRaises(ValueError):
            csm.replica(noise(self.idx, 6), self.spy.iloc[:-1], self.ief, self.cash)


class TheCrisisProxy(unittest.TestCase):
    def test_the_regression_recovers_a_lagged_beta_and_its_alpha(self):
        idx = sessions(n=1500)
        cash = pd.Series(0.0001, index=idx)
        h = noise(idx, 21, 0.004)
        eh = h - cash
        sleeve = (cash + 0.9 * eh + 0.4 * eh.shift(5) + 0.02 / 252).iloc[5:]
        reg = csm.crisis_regression(sleeve, h, cash)
        self.assertAlmostEqual(reg["beta_hat"], 1.3, places=8)
        self.assertAlmostEqual(reg["alpha_hat"], 0.02, places=8)

    def test_the_screen(self):
        idx = sessions(n=500)
        hyg = noise(idx, 7, 0.004)
        self.assertTrue(csm.proxy_screen(hyg, hyg)["passes"])
        self.assertFalse(csm.proxy_screen(hyg + 0.0026 / 252, hyg)["passes"])
        self.assertTrue(csm.proxy_screen(hyg + 0.0024 / 252, hyg)["passes"])
        self.assertFalse(csm.proxy_screen(0.9 * hyg + noise(idx, 8, 0.002), hyg)["passes"])
        self.assertFalse(csm.proxy_screen(hyg.iloc[1:], hyg)["passes"])


class TheBandAndTheVerdict(unittest.TestCase):
    def test_the_band_scales_with_the_carve(self):
        self.assertEqual([csm.band(x) for x in csm.CARVE_OUTS], [0.0125, 0.025, 0.05])

    def test_one_frequency(self):
        d = 0.025
        self.assertEqual(csm.status([0.03, 0.025], d), csm.PASS)
        self.assertEqual(csm.status([0.03, 0.02], d), csm.UNRESOLVED)
        self.assertEqual(csm.status([0.30, -0.025], d), csm.FAIL)
        self.assertEqual(csm.status([-0.02, 0.0], d), csm.UNRESOLVED)

    def test_both_frequencies(self):
        P, F, U = csm.PASS, csm.FAIL, csm.UNRESOLVED
        self.assertEqual(csm.combine(P, P), P)
        self.assertEqual(csm.combine(P, U), U)      # holding at one frequency only is not a pass
        self.assertEqual(csm.combine(U, P), U)
        self.assertEqual(csm.combine(P, F), F)
        self.assertEqual(csm.combine(F, U), F)
        self.assertEqual(csm.combine(U, U), U)

    def v(self, **c):
        crit = {k: {"status": csm.PASS} for k in ("C1", "C2", "C3", "C4", "C5")}
        crit.update({k: {"status": s} for k, s in c.items()})
        return csm.verdict(crit)

    def test_the_map(self):
        P, F, U = csm.PASS, csm.FAIL, csm.UNRESOLVED
        self.assertEqual(self.v(), csm.ADD)
        self.assertEqual(self.v(C5=None), csm.UNTESTED)
        self.assertEqual(self.v(C2=F), csm.SHARPE_ONLY)
        self.assertEqual(self.v(C5=F), csm.SHARPE_ONLY)
        self.assertEqual(self.v(C2=F, C5=None), csm.SHARPE_ONLY)
        for c in ("C1", "C3", "C4"):
            self.assertEqual(self.v(**{c: F}), csm.NO_CREDIT)
            self.assertEqual(self.v(**{c: U}), csm.NO_EFFECT)
            self.assertEqual(self.v(**{c: U, "C2": F}), csm.NO_EFFECT)
        self.assertEqual(self.v(C1=U, C3=F), csm.NO_CREDIT)

    def test_overall_reports_every_carve_and_sizes_nothing(self):
        per = {"5%": {"verdict": csm.ADD}, "10%": {"verdict": csm.UNTESTED}, "20%": {"verdict": csm.SHARPE_ONLY}}
        o = csm.overall(per)
        self.assertEqual(o["headline"], csm.ADD)
        self.assertEqual(o["carves_reading_add"], ["5%", "10%"])
        self.assertNotIn("recommended_carve", o)
        self.assertEqual(o["carves_reading_no_credit"], [])
        per = {"5%": {"verdict": csm.NO_CREDIT}, "10%": {"verdict": csm.NO_EFFECT}, "20%": {"verdict": csm.NO_CREDIT}}
        self.assertEqual(csm.overall(per)["headline"], csm.NO_EFFECT)
        self.assertEqual(csm.overall(per)["carves_reading_no_credit"], ["5%", "20%"])


class TheCriteriaEndToEnd(unittest.TestCase):
    def setUp(self):
        self.idx = pd.bdate_range("2012-05-11", "2026-10-02")
        self.cash = pd.Series(0.00005, index=self.idx)
        self.spy = noise(self.idx, 11, 0.011, 0.0004)
        self.ief = noise(self.idx, 12, 0.004, 0.0001)
        self.p = 0.6 * self.spy + 0.4 * self.ief

    def run_(self, angl, hyg, stress=None, x=0.10):
        rep, _ = csm.replica(angl, self.spy, self.ief, self.cash)
        st = csm.statistics(self.p, angl, hyg, rep, self.cash, x, stress)
        cr = csm.criteria(st, x)
        return cr, csm.verdict(cr), st

    def test_a_sleeve_identical_to_the_product_is_no_measurable_effect(self):
        cr, v, _ = self.run_(self.p, self.p)
        self.assertEqual(cr["C1"]["status"], csm.UNRESOLVED)
        self.assertEqual(v, csm.NO_EFFECT)

    def test_an_uncorrelated_steady_earner_is_added_when_untested(self):
        angl = noise(self.idx, 13, 0.002, 0.0004)
        hyg = noise(self.idx, 14, 0.002, 0.0)
        cr, v, st = self.run_(angl, hyg)
        self.assertEqual({k: cr[k]["status"] for k in ("C1", "C2", "C3", "C4", "C5")},
                         {"C1": csm.PASS, "C2": csm.PASS, "C3": csm.PASS, "C4": csm.PASS, "C5": None})
        self.assertEqual(v, csm.UNTESTED)
        self.assertGreater(st[csm.NEGATIVE]["vs_product_and_hyg"]["angl"]["sharpe"],
                           st[csm.NEGATIVE]["vs_product_and_hyg"]["product"]["sharpe"])

    def test_a_crisis_that_deepens_the_drawdown_downgrades(self):
        angl = noise(self.idx, 13, 0.002, 0.0004)
        hyg = noise(self.idx, 14, 0.002, 0.0)
        sidx = pd.bdate_range("2007-06-11", "2012-05-09")
        crash = pd.Series(0.0, index=sidx)
        crash.iloc[300:320] = -0.03
        stress = {"product": pd.Series(0.0, index=sidx), "proxy": crash,
                  "proxy_zero_alpha": crash, "plain_proxy": crash}
        cr, v, st = self.run_(angl, hyg, stress)
        self.assertEqual(cr["C5"]["status"], csm.FAIL)
        self.assertEqual(v, csm.SHARPE_ONLY)
        self.assertGreater(st["crisis stress"]["extra_drawdown_pp"], 0)

    def test_a_sleeve_that_is_only_its_replica_fails_c4_or_is_unresolved(self):
        """A sleeve with no return beyond its lagged stock and bond exposure cannot pass C4."""
        es, ei = self.spy - self.cash, self.ief - self.cash
        angl = (self.cash + 0.3 * es + 0.2 * es.shift(5) + 0.3 * ei).iloc[5:]
        cr, v, _ = self.run_(angl, noise(self.idx, 15, 0.004, -0.0002).iloc[5:])
        self.assertNotEqual(cr["C4"]["status"], csm.PASS)
        self.assertIn(v, (csm.NO_EFFECT, csm.NO_CREDIT))


class OptionA(unittest.TestCase):
    def test_a_daily_series_is_refused_as_a_list_or_as_a_date_keyed_object(self):
        self.assertEqual(csm.series_like({"a": {"b": list(range(11))}, "c": [1, 2]}), ["$.a.b"])
        self.assertEqual(csm.series_like({"a": {"2012-05-11": 0.01, "n": 1}}), ["$.a"])
        self.assertEqual(csm.series_like({"window": ["2007-06-11", "2012-05-09"], "5%": {"x": 1}}), [])


class _Rec:
    def __init__(self, key):
        self.key, self.returns_sha = key, "0" * 64


class _Snap:
    def __init__(self, ret):
        self._ret = ret

    def returns(self):
        return self._ret


class ThePipeline(unittest.TestCase):
    """study() on synthetic stand-ins for the ledger and the snapshots: every build session is
    gone from the windows, the replica grid, the regression and the screen, and the crisis
    window starts after the product's build."""

    def setUp(self):
        cal = pd.bdate_range("2007-01-02", "2026-10-02")
        prod = cal[cal >= "2007-06-08"]
        main = cal[cal >= "2012-05-10"]
        rob = cal[cal >= "2016-07-21"]

        def rec(idx, seed, scale, mean=0.0002):
            s = noise(idx, seed, scale, mean)
            s.iloc[0] = 1000.0                               # the build session: must not survive
            return s
        hyg = rec(main, 31, 0.004)
        self.main = main
        self.series = {csm.PRODUCT: rec(prod, 30, 0.007), csm.ANGL: rec(main, 32, 0.005), csm.HYG: hyg,
                       **{k: rec(rob, 33 + i, 0.005) for i, k in enumerate(csm.ROBUSTNESS.values())}}
        cols = {"SPY": noise(cal, 40, 0.011), "IEF": noise(cal, 41, 0.004),
                "HYG": pd.concat([noise(cal[cal < main[1]], 42, 0.006), hyg.iloc[1:]])}
        night = pd.DataFrame({k: pd.Series(0.0, index=cal) for k in cols})
        day = pd.DataFrame(cols).reindex(cal)
        night.iloc[0], day.iloc[0] = np.nan, np.nan
        self.ret = csm.daily_data.SessionReturns(dates=cal, night=night, day=day,
                                                 cash=pd.Series(0.00005, index=cal))

    def run_study(self):
        from unittest import mock
        recs = [_Rec(k) for k in self.series]
        with mock.patch.object(csm.trials, "iter_trials", return_value=recs), \
             mock.patch.object(csm.trials, "load_returns", return_value=dict(self.series)), \
             mock.patch.object(csm.daily_data, "load_snapshot", return_value=_Snap(self.ret)):
            return csm.study()

    def test_no_build_session_survives(self):
        res = self.run_study()
        c = res["carve_outs"]["10%"]["statistics"]
        self.assertEqual(c[csm.NEGATIVE]["vs_product_and_hyg"]["first"], "2012-05-11")
        self.assertEqual(c["crisis stress"]["first"], "2007-06-11")
        self.assertEqual(c["crisis stress"]["last"], "2012-05-09")
        self.assertEqual(res["crisis_proxy"]["screen"]["first"], "2012-05-11")
        self.assertTrue(res["crisis_proxy"]["run"])
        rob = res["reported"]["provider_robustness"]["FALN"]["10%"][csm.NEGATIVE]
        self.assertEqual(rob["first"], "2016-07-22")
        self.assertLess(abs(res["crisis_proxy"]["regression"]["alpha_hat"]), 1.0)   # a build day would add ~+70/yr
        self.assertEqual(res["replica"]["first"], str(self.main[1 + (csm.BETA_MIN + 1) * 5].date()))
        for x in ("5%", "10%", "20%"):
            dd = res["carve_outs"][x]["statistics"]["crisis stress"]["product_max_drawdown"]
            self.assertGreater(dd, -0.9)
        self.assertEqual(csm.series_like(json.loads(json.dumps(res, default=float))), [])

    def test_a_failed_screen_leaves_c5_not_run(self):
        self.ret.day["HYG"] = self.ret.day["HYG"] + 0.01
        res = self.run_study()
        self.assertFalse(res["crisis_proxy"]["run"])
        self.assertIsNone(res["carve_outs"]["10%"]["criteria"]["C5"]["status"])


class TheInvariants(unittest.TestCase):
    def test_a_ledger_change_during_the_run_writes_nothing(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.json"
            states = [{"family_counts": {"f": 1}}, {"family_counts": {"f": 2}}]
            with mock.patch.object(csm, "ledger_state", side_effect=states), \
                 mock.patch.object(csm, "study", return_value={}):
                with self.assertRaises(SystemExit):
                    csm.main(["--json", str(out)])
            self.assertFalse(out.exists())

    def test_a_series_in_the_output_writes_nothing(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.json"
            same = {"family_counts": {}, "evaluator_sha256": {}}
            with mock.patch.object(csm, "ledger_state", return_value=same), \
                 mock.patch.object(csm, "study", return_value={"leak": {"2012-05-11": 0.01}}):
                with self.assertRaises(SystemExit):
                    csm.main(["--json", str(out)])
            self.assertFalse(out.exists())


def _close(test, a, b, path="$"):
    if isinstance(a, dict):
        test.assertEqual(sorted(a), sorted(b), path)
        for k in a:
            _close(test, a[k], b[k], f"{path}.{k}")
    elif isinstance(a, float) and isinstance(b, float):
        test.assertTrue(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15) or (math.isnan(a) and math.isnan(b)),
                        f"{path}: {a} != {b}")
    else:
        test.assertEqual(a, b, path)


class TheSiblingStillReproduces(unittest.TestCase):
    def test_f366206s_committed_results_reproduce(self):
        committed = json.loads((REPO / "docs/research/data/sleeve_break_even.json").read_text())["results"]
        replayed = json.loads(json.dumps(sleeve_break_even.study(), default=float))
        _close(self, replayed, committed)


if __name__ == "__main__":
    unittest.main()
