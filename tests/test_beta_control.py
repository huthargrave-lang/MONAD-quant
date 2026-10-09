"""The beta-exposure control (src/research/beta_control.py) on synthetic books, with the
labels BETA_TIMING_CONTROL_PROTOCOL.md states in advance: pure timing reads BETA EXPOSURE,
pure selection and idiosyncratic reversion SURVIVE, a fund's own beta rising after
drawdowns and reversion only in up-blocks do not SURVIVE; betas are ex-ante; replays and
book identities are checked."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import beta_control as bc  # noqa: E402
from src.research import hac  # noqa: E402

N_DAYS = 5 * 900


def dates(n=N_DAYS):
    return pd.bdate_range("2004-01-02", periods=n)


def run_control(asset_r: pd.DataFrame, delta: pd.DataFrame, factor: pd.Series, active: pd.Series,
                *, window=156, min_blocks=48, self_factor=frozenset()):
    """The primary statistic, R0, R2, R2b and R4 for a synthetic book, as the tool computes
    them (every asset's factor is ``factor``)."""
    grid = bc.block_grid(asset_r.index, asset_r.index[0])
    Fd = pd.DataFrame({a: factor for a in asset_r.columns})
    out = {}
    for name, (w, m) in {"primary": (window, min_blocks), "R4": (26, 13)}.items():
        betas = bc.dimson_betas(bc.block_sums(asset_r, grid), [bc.block_sums(Fd, grid)],
                                window=w, min_blocks=m, self_factor=self_factor)
        X = bc.exposure(delta, [Fd], betas, grid[grid >= min_blocks])
        out[name] = X
    sample = grid[grid >= min_blocks]
    a_w = bc.block_sums(active, sample).to_numpy()
    F_w = bc.block_sums(factor, grid).to_numpy()
    X_w = bc.block_sums(out["primary"].daily, sample).to_numpy()
    X4_w = bc.block_sums(out["R4"].daily, sample).to_numpy()
    p = bc.primary(a_w, X_w)
    robust = {"R0": bc.free_g(a_w, X_w), "R4": bc.primary(a_w, X4_w),
              "R2": bc.treynor_mazuy(a_w, F_w[min_blocks:]),
              "R2b": bc.conditional_beta(a_w, F_w[min_blocks:], bc.trailing(F_w)[min_blocks:])}
    return p, robust, bc.verdict(p, robust)


class Labels(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(7)
        self.d = dates()
        self.F = pd.Series(self.rng.normal(0.0003, 0.01, N_DAYS), index=self.d)

    def test_pure_timing_reads_beta_exposure(self):
        """Hold the high-beta asset over the blocks the market rises: all of the active
        return is timed beta, so the beta-hedged alpha keeps nothing."""
        rng, d, F = self.rng, self.d, self.F
        r = pd.DataFrame({"H": 1.6 * F + rng.normal(0, 0.002, N_DAYS),
                          "L": 0.6 * F + rng.normal(0, 0.002, N_DAYS)}, index=d)
        grid = bc.block_grid(d, d[0])
        up = (bc.block_sums(F, grid) > 0).reindex(grid.to_numpy()).to_numpy()
        dh = np.where(up, 0.5, -0.5)
        delta = pd.DataFrame({"H": dh, "L": -dh}, index=d)
        active = (delta * r).sum(axis=1)
        p, robust, (v, _) = run_control(r, delta, F, active)
        self.assertLess(p["s"], 0.25)
        self.assertEqual(v, bc.BETA)

    def test_pure_selection_survives(self):
        rng, d, F = self.rng, self.d, self.F
        r = pd.DataFrame({"A": F + 0.0004 + rng.normal(0, 0.003, N_DAYS),
                          "B": F + rng.normal(0, 0.003, N_DAYS)}, index=d)
        delta = pd.DataFrame({"A": 0.5, "B": -0.5}, index=d)
        active = (delta * r).sum(axis=1)
        p, robust, (v, _) = run_control(r, delta, F, active)
        self.assertGreater(p["s"], 0.8)
        self.assertEqual(v, bc.SURVIVES, (p, robust))

    def test_idiosyncratic_reversion_survives(self):
        """Overweight the assets whose idiosyncratic return fell over the past week; the
        reversion is independent of the market, so it is selection."""
        rng, d, F = self.rng, self.d, self.F
        k = 6
        u = rng.normal(0, 0.006, (N_DAYS, k))
        past = pd.DataFrame(u).rolling(5).sum().shift(1).fillna(0.0).to_numpy()
        e = u - 0.15 * past
        r = pd.DataFrame(F.to_numpy()[:, None] + e, index=d, columns=[f"F{i}" for i in range(k)])
        sig = -pd.DataFrame(e, index=d, columns=r.columns).rolling(5).sum()
        rank = sig.rank(axis=1)
        w = (rank > k / 2).astype(float) / (k / 2)
        delta = (w - 1.0 / k).shift(1).fillna(0.0)
        active = (delta * r).sum(axis=1)
        p, robust, (v, _) = run_control(r, delta, F, active)
        self.assertEqual(v, bc.SURVIVES, (p, robust))

    def test_own_beta_rising_after_drawdowns_does_not_survive(self):
        """The held fund's beta doubles for the 8 blocks after a market drawdown, and the
        market rebounds then: a long-window beta averages it away; R4 or R2b must not."""
        rng = self.rng
        nb = N_DAYS // 5
        Fb = np.empty(nb)
        beta = np.ones(nb)
        hot = 0
        for w in range(nb):
            drift = 0.004 if hot > 0 else 0.0005
            Fb[w] = rng.normal(drift, 0.02)
            beta[w] = 2.2 if hot > 0 else 1.0
            hot = 8 if Fb[w] < -0.03 else max(hot - 1, 0)
        Fd = np.repeat(Fb / 5, 5) + rng.normal(0, 0.002, N_DAYS)
        F = pd.Series(Fd, index=self.d)
        bd = np.repeat(beta, 5)
        r = pd.DataFrame({"A": bd * Fd + rng.normal(0, 0.002, N_DAYS),
                          "B": Fd + rng.normal(0, 0.002, N_DAYS)}, index=self.d)
        delta = pd.DataFrame({"A": 1.0, "B": -1.0}, index=self.d)
        active = (delta * r).sum(axis=1)
        p, robust, (v, _) = run_control(r, delta, F, active)
        self.assertNotEqual(v, bc.SURVIVES, (p, robust))

    def test_reversion_only_in_up_blocks_is_convex_and_does_not_survive(self):
        rng, d = self.rng, self.d
        grid = bc.block_grid(d, d[0])
        F = self.F
        Fb = bc.block_sums(F, grid).reindex(grid.to_numpy()).to_numpy()
        bonus = np.where(Fb > 0, 0.25 * Fb / 5, 0.0)
        r = pd.DataFrame({"A": F + bonus + rng.normal(0, 0.001, N_DAYS),
                          "B": F + rng.normal(0, 0.001, N_DAYS)}, index=d)
        delta = pd.DataFrame({"A": 1.0, "B": -1.0}, index=d)
        active = (delta * r).sum(axis=1)
        p, robust, (v, _) = run_control(r, delta, F, active)
        self.assertTrue(robust["R2"]["convexity_detected"], robust["R2"])

    def test_a_purely_convex_payoff_does_not_survive(self):
        """Clarification 2: an active return proportional to the squared market block
        return is all convexity; Treynor-Mazuy's alpha keeps none of it."""
        rng, d = self.rng, self.d
        grid = bc.block_grid(d, d[0])
        F = self.F
        Fb = bc.block_sums(F, grid).reindex(grid.to_numpy()).to_numpy()
        bonus = 4.0 * Fb ** 2 / 5
        r = pd.DataFrame({"A": F + bonus + rng.normal(0, 0.001, N_DAYS),
                          "B": F + rng.normal(0, 0.001, N_DAYS)}, index=d)
        delta = pd.DataFrame({"A": 1.0, "B": -1.0}, index=d)
        active = (delta * r).sum(axis=1)
        p, robust, (v, _) = run_control(r, delta, F, active)
        self.assertLess(robust["R2"]["s"], 0.25, robust["R2"])
        self.assertNotEqual(v, bc.SURVIVES)


class ExAnte(unittest.TestCase):
    def test_a_beta_uses_no_data_from_its_own_block_or_later(self):
        rng = np.random.default_rng(1)
        d = dates(5 * 300)
        F = pd.Series(rng.normal(0, 0.01, len(d)), index=d)
        r = pd.DataFrame({"A": 1.3 * F + rng.normal(0, 0.003, len(d))}, index=d)
        grid = bc.block_grid(d, d[0])
        Fd = pd.DataFrame({"A": F})
        b1 = bc.dimson_betas(bc.block_sums(r, grid), [bc.block_sums(Fd, grid)], window=156, min_blocks=48)
        k = 200
        r2 = r.copy()
        r2.iloc[k * 5:] *= -3.0
        b2 = bc.dimson_betas(bc.block_sums(r2, grid), [bc.block_sums(Fd, grid)], window=156, min_blocks=48)
        np.testing.assert_array_equal(b1.coef[: k + 1], b2.coef[: k + 1])
        self.assertFalse(np.array_equal(b1.coef[k + 1], b2.coef[k + 1]))
        # block 0 has no previous factor block, so the 48th complete estimate is block 49
        self.assertTrue(b1.fallback[:49].all() and not b1.fallback[49:].any())
        self.assertAlmostEqual(b1.coef[-1, 0, 0] + b1.coef[-1, 0, 1], 1.3, delta=0.1)

    def test_self_factor_assets_have_unit_beta_and_no_fallback(self):
        rng = np.random.default_rng(2)
        d = dates(5 * 100)
        F = pd.Series(rng.normal(0, 0.01, len(d)), index=d)
        r = pd.DataFrame({"ETF": F}, index=d)
        grid = bc.block_grid(d, d[0])
        b = bc.dimson_betas(bc.block_sums(r, grid), [bc.block_sums(pd.DataFrame({"ETF": F}), grid)],
                            window=156, min_blocks=48, self_factor=frozenset({"ETF"}))
        self.assertTrue((b.coef[:, 0, 0] == 1).all() and (b.coef[:, 0, 1] == 0).all())
        self.assertFalse(b.fallback.any())

    def test_incomplete_final_block_is_dropped(self):
        d = dates(23)
        g = bc.block_grid(d, d[2])
        self.assertEqual(len(g), 20)
        self.assertEqual(g.iloc[-1], 3)


class Inference(unittest.TestCase):
    def test_fieller_is_bounded_for_a_strong_denominator_and_unbounded_for_a_weak_one(self):
        rng = np.random.default_rng(3)
        den = rng.normal(1.0, 1.0, 2000)
        num = 0.5 * den + rng.normal(0, 0.5, 2000)
        lo, hi = hac.fieller(num, den, 4)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)
        self.assertIsNone(hac.fieller(num, rng.normal(0.0, 1.0, 2000), 4))

    def test_mean_t_matches_iid_t_without_autocorrelation_at_lag_zero(self):
        x = np.random.default_rng(4).normal(0.1, 1.0, 500)
        _, _, t = hac.mean_t(x, 0)
        self.assertAlmostEqual(t, x.mean() / (x.std(ddof=0) / np.sqrt(len(x))), places=10)

    def test_auto_lag(self):
        self.assertEqual((hac.auto_lag(1086), hac.auto_lag(420), hac.auto_lag(645)), (6, 5, 6))

    def test_a_non_positive_raw_mean_is_inconclusive(self):
        p = {"raw_ann": -0.01, "s": 2.0, "t_alpha": (3.0, 3.0), "t_E": (0.0, 0.0)}
        self.assertEqual(bc.verdict(p, {})[0], bc.INCONCLUSIVE)

    def test_a_robustness_factor_can_establish_beta_unless_the_primary_survives(self):
        weak = {"raw_ann": 0.01, "s": 0.4, "t_alpha": (1.0, 1.0), "t_E": (1.0, 1.0)}
        strong = {"raw_ann": 0.01, "s": 0.9, "t_alpha": (3.0, 3.0), "t_E": (0.2, 0.2)}
        r = {"R1b": {"s": 0.1, "t_E": (3.0, 2.8)}}
        self.assertEqual(bc.verdict(weak, r)[0], bc.BETA)
        self.assertEqual(bc.verdict(strong, r)[0], bc.INCONCLUSIVE)
        self.assertEqual(bc.verdict(weak, {"R1b": {"s": 0.1, "t_E": (3.0, 2.4)}})[0], bc.INCONCLUSIVE)


class ReplayChecks(unittest.TestCase):
    def test_reproduction(self):
        d = dates(10)
        s = pd.Series(np.linspace(0, 0.01, 10), index=d)
        self.assertEqual(bc.reproduction_problems(s, s.copy()), [])
        t = s.copy()
        t.iloc[3] += 1e-9
        self.assertTrue(bc.reproduction_problems(t, s))
        self.assertTrue(bc.reproduction_problems(s.iloc[1:], s))

    def test_the_book_identity_holds_for_the_evaluator_and_fails_on_an_altered_fee(self):
        from src.research.daily_data import Snapshot
        from src.research.daily_strategy import Tranche, evaluate_daily
        from src.strategy.counted import uncounted
        rng = np.random.default_rng(5)
        d = dates(300)
        close = pd.DataFrame({a: 50 * np.exp(np.cumsum(rng.normal(0, 0.01, len(d)))) for a in ("SPY", "A", "B")},
                             index=d)
        snap = Snapshot(sha="b" * 64, dates=d, assets=tuple(close.columns), open=close.shift(1).fillna(close.iloc[0]),
                        close=close, dist=close * 0.0, dtb3=pd.Series(2.0, index=d), manifest={})
        orders = []
        for k in range(21):
            when = d[k::21]
            w = pd.DataFrame({"A": rng.uniform(0.2, 0.6, len(when))}, index=when)
            w["B"] = 0.9 - w["A"]
            orders.append(Tranche(open_orders=pd.DataFrame(), close_orders=w))
        with uncounted("unit test of the book identity on a synthetic snapshot"):
            res = evaluate_daily(orders, snap, start=d[30], end=d[-1])
        rets = snap.returns()
        tot = (1 + rets.night) * (1 + rets.day) - 1
        bound = 3 * 15e-4                          # three one-way trades at the dearest default tier
        ok = bc.weight_identity_problems(res.returns, res.weights, tot, res.cash, res.cost_paid,
                                         carry_in=True, first_session_fee_bound=bound)
        self.assertEqual(ok, [])
        # a weight series one session out of step (the failure this check exists for)
        self.assertTrue(bc.weight_identity_problems(res.returns, res.weights.shift(1), tot, res.cash,
                                                    res.cost_paid, carry_in=True, first_session_fee_bound=bound))
        with uncounted("unit test of the book identity without a carried-in build"):
            late = [Tranche(open_orders=pd.DataFrame(), close_orders=t.close_orders.loc[d[30]:]) for t in orders]
            res2 = evaluate_daily(late, snap, start=d[30], end=d[-1])
        self.assertEqual(bc.weight_identity_problems(res2.returns, res2.weights, tot, res2.cash, res2.cost_paid,
                                                     carry_in=False), [])
        self.assertTrue(bc.weight_identity_problems(res2.returns, res2.weights, tot, res2.cash,
                                                    res2.cost_paid + 1e-6, carry_in=False))


if __name__ == "__main__":
    unittest.main()
