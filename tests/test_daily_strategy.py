"""
The daily-strategy evaluator (src/research/daily_strategy.py), on hand-built snapshots
whose every number can be worked out on paper: next-session execution, drift, the two
compounded legs, distributions, cash, costs, carry-in, and the refusals.
"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import trials  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402
from src.research.daily_strategy import (OrderError, Tranche, cost_bps,  # noqa: E402
                                         evaluate_daily, static_tranches)
from src.strategy import counted  # noqa: E402
from tests._engine_uncounted import uncounted_module  # noqa: E402

setUpModule, tearDownModule = uncounted_module(
    "evaluator arithmetic on hand-built snapshots; no instrument is measured")

DATES = pd.bdate_range("2012-01-02", periods=8)        # all after the 2010 cost era boundary


def snapshot(opens, closes, dist=None, dtb3=None, dates=DATES):
    o = pd.DataFrame(opens, index=dates, dtype=float)
    c = pd.DataFrame(closes, index=dates, dtype=float)
    d = pd.DataFrame(dist if dist is not None else {k: [0.0] * len(dates) for k in opens},
                     index=dates, dtype=float)
    cash = pd.Series(dtb3 if dtb3 is not None else [0.0] * len(dates), index=dates, dtype=float)
    return Snapshot(sha="test", dates=dates, assets=tuple(o.columns), open=o, close=c, dist=d,
                    dtb3=cash, manifest={})


def orders(rows: dict) -> pd.DataFrame:
    return pd.DataFrame.from_dict({DATES[i]: w for i, w in rows.items()}, orient="index")


FLAT = [100.0] * 8


class Execution(unittest.TestCase):
    def test_an_order_executes_at_the_next_session_not_the_decision_session(self):
        # A rises 10% during session 3's day leg. An order DECIDED at session 3 must miss it.
        snap = snapshot({"A": [100, 100, 100, 100, 110, 110, 110, 110]},
                        {"A": [100, 100, 100, 110, 110, 110, 110, 110]})
        tr = Tranche(open_orders=orders({3: {"A": 1.0}}), close_orders=pd.DataFrame())
        r = evaluate_daily([tr], snap, start=DATES[1], cost_multiple=1e-12)
        self.assertAlmostEqual(float((1 + r.returns).prod() - 1), 0.0, places=9)
        tr2 = Tranche(open_orders=orders({2: {"A": 1.0}}), close_orders=pd.DataFrame())
        r2 = evaluate_daily([tr2], snap, start=DATES[1], cost_multiple=1e-12)
        self.assertAlmostEqual(float((1 + r2.returns).prod() - 1), 0.10, places=9)

    def test_night_and_day_legs_compound(self):
        # Hold A all day and night: open +2% gap, then +3% in the day -> 1.02 * 1.03.
        snap = snapshot({"A": [100, 100, 102, 102, 102, 102, 102, 102]},
                        {"A": [100, 100, 105.06, 105.06, 105.06, 105.06, 105.06, 105.06]})
        tr = Tranche(open_orders=orders({0: {"A": 1.0}}), close_orders=pd.DataFrame())
        r = evaluate_daily([tr], snap, start=DATES[1], cost_multiple=1e-12)
        self.assertAlmostEqual(float(r.returns.iloc[1]), 1.02 * 1.03 - 1, places=12)

    def test_a_distribution_is_earned_overnight_on_its_ex_date(self):
        # Ex-date at session 3: the open drops by the $2 distribution; total return is 0.
        snap = snapshot({"A": [100, 100, 100, 98, 98, 98, 98, 98]},
                        {"A": [100, 100, 100, 98, 98, 98, 98, 98]},
                        dist={"A": [0, 0, 0, 2.0, 0, 0, 0, 0]})
        tr = Tranche(open_orders=orders({0: {"A": 1.0}}), close_orders=pd.DataFrame())
        r = evaluate_daily([tr], snap, start=DATES[1], cost_multiple=1e-12)
        self.assertAlmostEqual(float((1 + r.returns).prod() - 1), 0.0, places=9)

    def test_holdings_drift_and_a_rebalance_pays_for_the_drift(self):
        # 50/50 A/B; A doubles on session 2. Without a rebalance, A is 2/3 of the book.
        snap = snapshot({"A": [100, 100, 100, 200, 200, 200, 200, 200], "B": [100] * 8},
                        {"A": [100, 100, 200, 200, 200, 200, 200, 200], "B": [100] * 8})
        held = Tranche(open_orders=orders({0: {"A": 0.5, "B": 0.5}}), close_orders=pd.DataFrame())
        r = evaluate_daily([held], snap, start=DATES[1], cost_multiple=1e-12)
        self.assertAlmostEqual(float(r.exposure.iloc[-1]), 1.0, places=9)
        self.assertAlmostEqual(float((1 + r.returns).prod()), 1.5, places=9)
        # Rebalance back to 50/50 at session 4's open: trades 1/6 of the book each way.
        rb = Tranche(open_orders=orders({0: {"A": 0.5, "B": 0.5}, 3: {"A": 0.5, "B": 0.5}}),
                     close_orders=pd.DataFrame())
        r2 = evaluate_daily([rb], snap, start=DATES[1], cost_multiple=1.0)
        bps = cost_bps("A", DATES[4]) * 1e-4
        # Turnover: the carry-in build (1.0) plus 1/6 + 1/6 at the rebalance.
        self.assertAlmostEqual(r2.turnover, 1.0 + 1 / 3, places=9)
        expected = (1 - bps) * (1 + 1.0) * 0.5 + (1 - bps) * 0.5   # build cost, then A doubles
        expected *= (1 - bps * (1 / 3))                           # the drift trade
        self.assertAlmostEqual(float((1 + r2.returns).prod()), expected, places=9)

    def test_uninvested_weight_earns_the_lagged_bill_rate_over_calendar_days(self):
        # 5% discount rate; nothing invested. Session 0 is a Monday, so session 5 (Monday)
        # accrues the weekend: three calendar days.
        snap = snapshot({"A": FLAT}, {"A": FLAT}, dtb3=[5.0] * 8)
        tr = Tranche(open_orders=pd.DataFrame(), close_orders=pd.DataFrame())
        r = evaluate_daily([tr], snap, start=DATES[1])
        bey = 365 * 0.05 / (360 - 0.05 * 91)
        self.assertAlmostEqual(float(r.returns.iloc[0]), bey * 1 / 365, places=12)
        self.assertAlmostEqual(float(r.returns.loc[DATES[5]]), bey * 3 / 365, places=12)
        self.assertTrue((r.excess.abs() < 1e-15).all())

    def test_overnight_style_orders_trade_both_auctions(self):
        # Buy at each close, sell at each open: earns only the night legs, pays 2 costs/session.
        snap = snapshot({"A": [100, 101, 101, 102, 102, 103, 103, 104]},
                        {"A": [100, 100, 101, 101, 102, 102, 103, 103]})
        days = DATES[:-1]
        tr = Tranche(open_orders=pd.DataFrame({"A": 0.0}, index=days),
                     close_orders=pd.DataFrame({"A": 1.0}, index=days))
        r = evaluate_daily([tr], snap, start=DATES[2], cost_multiple=1e-12)
        night = snap.open["A"] / snap.close["A"].shift(1) - 1
        # Session 2 starts in cash: the carry-in is the latest target (cash, after the open
        # sell at session 2 itself). Then each night from session 3 on is earned.
        expected = float((1 + night.loc[DATES[3]:]).prod())
        self.assertAlmostEqual(float((1 + r.returns).prod()), expected, places=9)
        self.assertEqual(r.rebalances, 2 * 6)

    def test_carry_in_holds_the_latest_target_from_the_first_scored_session(self):
        snap = snapshot({"A": [100] * 8}, {"A": [100, 100, 100, 110, 110, 110, 110, 110]})
        tr = Tranche(open_orders=orders({0: {"A": 1.0}}), close_orders=pd.DataFrame())
        r = evaluate_daily([tr], snap, start=DATES[3], cost_multiple=1e-12)
        self.assertAlmostEqual(float(r.returns.iloc[0]), 0.10, places=9)

    def test_turnover_and_cost_are_fractions_of_the_whole_portfolio(self):
        """Twenty-one tranches each building the same position once is ONE portfolio
        turnover, not twenty-one (the bug the event-grid report exposed, 2026-10-05)."""
        snap = snapshot({"A": FLAT}, {"A": FLAT})
        trs = [Tranche(open_orders=orders({0: {"A": 1.0}}), close_orders=pd.DataFrame())
               for _ in range(21)]
        r = evaluate_daily(trs, snap, start=DATES[1])
        self.assertAlmostEqual(r.turnover, 1.0, places=12)
        self.assertAlmostEqual(r.cost_paid, cost_bps("A", DATES[1]) * 1e-4, places=12)

    def test_tranches_are_equal_capital_sub_portfolios(self):
        snap = snapshot({"A": [100, 100, 100, 100, 100, 100, 100, 100], "B": [100] * 8},
                        {"A": [100, 100, 120, 120, 120, 120, 120, 120], "B": [100] * 8})
        a = Tranche(open_orders=orders({0: {"A": 1.0}}), close_orders=pd.DataFrame())
        b = Tranche(open_orders=orders({0: {"B": 1.0}}), close_orders=pd.DataFrame())
        r = evaluate_daily([a, b], snap, start=DATES[1], cost_multiple=1e-12)
        self.assertAlmostEqual(float((1 + r.returns).prod()), 0.5 * 1.2 + 0.5, places=9)


class Refusals(unittest.TestCase):
    def setUp(self):
        self.snap = snapshot({"A": FLAT, "B": FLAT}, {"A": FLAT, "B": FLAT})

    def test_leverage_and_shorts_are_refused(self):
        for w in ({"A": 0.7, "B": 0.4}, {"A": -0.1}):
            tr = Tranche(open_orders=orders({1: w}), close_orders=pd.DataFrame())
            with self.assertRaises(OrderError):
                evaluate_daily([tr], self.snap, start=DATES[1])

    def test_unknown_asset_and_non_session_dates_are_refused(self):
        tr = Tranche(open_orders=orders({1: {"Z": 1.0}}), close_orders=pd.DataFrame())
        with self.assertRaises(OrderError):
            evaluate_daily([tr], self.snap, start=DATES[1])
        bad = pd.DataFrame({"A": [1.0]}, index=[pd.Timestamp("2012-01-07")])   # a Saturday
        with self.assertRaises(OrderError):
            evaluate_daily([Tranche(open_orders=bad, close_orders=pd.DataFrame())], self.snap,
                           start=DATES[1])

    def test_an_order_into_an_unpriced_asset_is_refused(self):
        snap = snapshot({"A": FLAT, "B": [np.nan] * 4 + [100] * 4},
                        {"A": FLAT, "B": [np.nan] * 4 + [100] * 4})
        tr = Tranche(open_orders=orders({1: {"B": 1.0}}), close_orders=pd.DataFrame())
        with self.assertRaises(OrderError):
            evaluate_daily([tr], snap, start=DATES[1])

    def test_it_will_not_run_without_a_trial(self):
        """Outside this module's uncounted() block the evaluator is a counted entry point."""
        tearDownModule()
        try:
            tr = Tranche(open_orders=orders({1: {"A": 1.0}}), close_orders=pd.DataFrame())
            with self.assertRaises(counted.UncountedEvaluationError):
                evaluate_daily([tr], self.snap, start=DATES[1])
            with tempfile.TemporaryDirectory() as td:
                with trials.open_run(producer="t", family="f", ledger_dir=Path(td)) as run:
                    t = run.begin(params={"k": 1})
                    evaluate_daily([tr], self.snap, start=DATES[1])
                    t.complete(metrics={})
        finally:
            setUpModule()


class Costs(unittest.TestCase):
    def test_the_vectorised_matrix_equals_the_per_cell_rule(self):
        from src.research.daily_strategy import cost_matrix
        dates = pd.bdate_range("2009-12-28", periods=10)
        assets = ["SPY", "EEM", "PDI"]
        tiers = {"PDI": "cef"}
        m = cost_matrix(assets, dates, tiers)
        for i, d in enumerate(dates):
            for j, a in enumerate(assets):
                self.assertEqual(m[i, j], cost_bps(a, d, tiers))
        self.assertEqual(m[0, 2], 30.0)
        self.assertEqual(m[-1, 2], 15.0)


class StaticTranches(unittest.TestCase):
    def test_offsets_stagger_the_rebalance_days(self):
        trs = static_tranches({"A": 1.0}, DATES, every=3, offsets=(0, 1, 2))
        firsts = [tr.open_orders.index[0] for tr in trs]
        self.assertEqual(firsts, list(DATES[:3]))
        self.assertEqual(list(trs[0].open_orders.index), [DATES[0], DATES[3], DATES[6]])


if __name__ == "__main__":
    unittest.main()



class Weights(unittest.TestCase):
    """DailyResult.weights: each asset's fraction of the portfolio at every close."""

    def test_weights_are_the_target_after_a_close_rebalance_then_drift_and_sum_to_exposure(self):
        snap = snapshot({"A": [10, 10, 10, 10, 10, 10, 10, 10], "B": [20] * 8},
                        {"A": [10, 10, 10, 11, 11, 11, 11, 11], "B": [20] * 8})
        r = evaluate_daily([Tranche(open_orders=pd.DataFrame(),
                                    close_orders=orders({1: {"A": 0.3, "B": 0.5}}))],
                           snap, start=DATES[1], tiers={"A": "tier1", "B": "tier1"})
        self.assertTrue(np.allclose(r.weights.sum(axis=1), r.exposure))
        # Executed at the close of DATES[2] (decided at DATES[1]); A then rises 10% on DATES[3].
        w2 = r.weights.loc[DATES[2]]
        self.assertAlmostEqual(w2["A"] / w2["B"], 0.3 / 0.5, places=9)
        w3 = r.weights.loc[DATES[3]]
        self.assertGreater(w3["A"], w2["A"])
        self.assertEqual(list(r.weights.columns), ["A", "B"])



class Continuation(unittest.TestCase):
    """``initial``/``final``: chaining one-session evaluations from each final book
    reproduces one evaluation over the whole span, to floating-point precision."""

    def market(self, n=260, seed=7):
        dates = pd.bdate_range("2014-01-02", periods=n)
        rng = np.random.default_rng(seed)
        close = pd.DataFrame({c: 30 * np.exp(np.cumsum(rng.normal(0, 0.012, n))) for c in ("A", "B", "C")},
                             index=dates)
        opens = close.shift(1).fillna(close.iloc[0]) * np.exp(rng.normal(0, 0.003, (n, 3)))
        dist = close * 0.0
        dist.iloc[100, 0] = 0.4
        return Snapshot(sha="c" * 64, dates=dates, assets=("A", "B", "C"), open=opens, close=close,
                        dist=dist, dtb3=pd.Series(2.0, index=dates), manifest={})

    def strategy(self, snap):
        rng = np.random.default_rng(1)
        out = []
        for off in range(3):
            days = snap.dates[off::5]
            w = pd.DataFrame(rng.dirichlet([1, 1, 1], len(days)) * 0.9, index=days, columns=["A", "B", "C"])
            out.append(Tranche(open_orders=w.iloc[::2], close_orders=w.iloc[1::2]))
        return out

    def test_chained_sessions_equal_one_evaluation(self):
        snap = self.market()
        tr = self.strategy(snap)
        start = snap.dates[20]
        full = evaluate_daily(tr, snap, start=start, cost_multiple=1.0)
        first = evaluate_daily(tr, snap, start=start, end=start)
        rets, book = [first.returns.iloc[0]], first.final
        for d in snap.dates[21:]:
            step = evaluate_daily(tr, snap, start=d, end=d, initial=book)
            rets.append(step.returns.iloc[0])
            book = step.final
        np.testing.assert_allclose(np.array(rets), full.returns.to_numpy(), rtol=0, atol=1e-13)
        self.assertEqual(book.session, snap.dates[-1].date().isoformat())

    def test_a_book_from_another_session_or_shape_is_refused(self):
        snap = self.market()
        tr = self.strategy(snap)
        r = evaluate_daily(tr, snap, start=snap.dates[20], end=snap.dates[30])
        with self.assertRaises(OrderError):
            evaluate_daily(tr, snap, start=snap.dates[40], end=snap.dates[41], initial=r.final)
        with self.assertRaises(OrderError):
            evaluate_daily(tr[:2], snap, start=snap.dates[31], end=snap.dates[32], initial=r.final)

    def test_the_book_round_trips_through_json_exactly(self):
        from src.research.daily_strategy import BookState
        import json
        snap = self.market()
        r = evaluate_daily(self.strategy(snap), snap, start=snap.dates[20], end=snap.dates[60])
        again = BookState.from_json(json.loads(json.dumps(r.final.to_json())))
        self.assertEqual(again, r.final)
