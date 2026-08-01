"""The engine prices one gap two ways, and a config flag picks which — F241.

`compute_trade_returns` books a `stop_hit` at exactly `-stop_loss_pct`, even when the
bar that triggered it OPENED far through the stop. That optimism is known and measured:
`docs/research/D6_execution_semantics_study.md` puts the honest alternative ("fill opens
through the stop at the open") at **-10.15%** against **-5.17%** on the live-shaped path.

The `opposing_signal` exit does NOT share that convention. It is gated on the signal bar
sitting inside the stop/target band, but it FILLS at the *next* bar's open, which is not
bounded by anything. So it prices a gap honestly while the stop path prices it
optimistically.

On one hand-built frame — identical prices, identical everything, one flag flipped:

    USE_OPPOSING_SIGNAL_EXIT = False  ->  stop_hit          -1.00%   (the stop)
    USE_OPPOSING_SIGNAL_EXIT = True   ->  opposing_signal  -60.00%   (the gapped open)

Sixty times the recorded loss for the same market event. Neither number is a bug in
isolation: the opposing path is arguably the more realistic of the two. The defect is
that they DISAGREE, so the flag is not the inert toggle the dormant-pair guard treats it
as — it silently re-prices gap risk for every trade that would otherwise stop out. A
sweep comparing flag-on against flag-off is not comparing two exit policies; it is
comparing two gap-accounting conventions.

WHY NOTHING CAUGHT THIS. `tests/test_compute_returns_properties.py` asserts the
invariants that would have — returns finite, bounded below by -1, recorded return equals
the chosen exit level. Its generator reaches four of the five exit types. It cannot reach
the fifth: `_price_path()` never builds a `signal_vote` column (so the engine falls back
to `entry_signal`, which is zero on every future bar) and no property test ever passes
`use_opposing_signal_exit=True`. Doubly unreachable, in CI as much as anywhere — CI does
install hypothesis, so this is not an environment gap.

That unreached branch also falsifies one of those invariants outright. `assertGreater(r,
-1.0)` is justified in-file as "price can't go below zero" — true for a long, false for a
short, and the suite generates shorts half the time. A short opposing exit into a 9x move
records **-8.0**. Production is `LONGS_ONLY=True`, so this is a test-correctness finding,
not a live risk one, and it is recorded as such.

Guards below are bidirectional. They fail if the disagreement is fixed (adopt one
convention — then supersede this node rather than editing the numbers), and they fail if
the property suite grows coverage of the branch (good news, same instruction). The
no-gap control fails if the disagreement stops being attributable to the gap.
"""
import unittest
from pathlib import Path

import pandas as pd

from src.strategy.engine import compute_trade_returns

ROOT = Path(__file__).resolve().parents[1]

TARGET, STOP = 0.02, 0.01
EXIT_KW = dict(target_gain_pct=TARGET, stop_loss_pct=STOP, max_trade_bars=50,
               opposing_signal_threshold=1)


def frame(centers, votes, direction=1):
    """Flat-bodied bars so only the centers matter; entry fills at bar 1's open."""
    n = len(centers)
    return pd.DataFrame({
        "open": centers, "close": centers,
        "high": [c * 1.001 for c in centers], "low": [c * 0.999 for c in centers],
        "entry_signal": [direction] + [0] * (n - 1),
        "signal_vote": votes,
    }, index=pd.date_range("2024-01-01", periods=n, freq="D"))


def one(df, flag):
    res = compute_trade_returns(df, use_opposing_signal_exit=flag, **EXIT_KW)
    assert len(res) == 1, "fixture should produce exactly one trade, got {}".format(len(res))
    return res.iloc[0]["exit_type"], float(res.iloc[0]["return"])


# Entry fills at bar 1 (100). Bar 2 is quiet and carries the opposing vote, so the
# opposing exit is eligible. Bar 3 gaps to 40 — through the stop, and it is also the
# bar the opposing exit fills at.
GAP_DOWN = ([100, 100, 100, 40, 40], [0, 0, -2, 0, 0])
# Control: bar 3 moves +0.5%, INSIDE the stop/target band, so nothing gaps through
# anything. Deliberately a non-zero outcome — a flat frame would have both paths
# agreeing at 0.0, which any two broken paths would also satisfy.
NO_GAP = ([100, 100, 100, 100.5, 100.5], [0, 0, -2, 0, 0])


class TheTwoExitsPriceOneGapDifferentlyTests(unittest.TestCase):

    def test_the_stop_path_prices_the_gap_at_the_stop(self):
        """Optimistic fill: the bar OPENED at 40 and the stop still books -1%."""
        et, r = one(frame(*GAP_DOWN), flag=False)
        self.assertEqual(et, "stop_hit")
        self.assertAlmostEqual(
            r, -STOP, places=9,
            msg="the stop path stopped filling at the stop price — if the engine "
                "adopted honest gap fills, supersede F241 rather than retune this")

    def test_the_opposing_path_prices_the_gap_at_the_open(self):
        et, r = one(frame(*GAP_DOWN), flag=True)
        self.assertEqual(
            et, "opposing_signal",
            "the opposing exit no longer pre-empts the stop on this frame")
        self.assertAlmostEqual(
            r, -0.60, places=9,
            msg="the opposing exit stopped filling at the next open")

    def test_one_flag_changes_the_recorded_loss_sixtyfold(self):
        """The headline. Same frame, same prices, one flag."""
        _, off = one(frame(*GAP_DOWN), flag=False)
        _, on = one(frame(*GAP_DOWN), flag=True)
        self.assertAlmostEqual(off, -0.01, places=9)
        self.assertAlmostEqual(on, -0.60, places=9)
        self.assertAlmostEqual(
            on / off, 60.0, delta=0.5,
            msg="the two exits agree more closely than F241 recorded ({:.4f} vs {:.4f}) "
                "— if a single gap convention was adopted, supersede F241".format(on, off))

    def test_without_a_gap_the_two_paths_agree(self):
        """Negative control. The disagreement must be the gap, not the flag alone."""
        _, off = one(frame(*NO_GAP), flag=False)
        et_on, on = one(frame(*NO_GAP), flag=True)
        self.assertEqual(et_on, "opposing_signal",
                         "control frame no longer exercises the opposing branch, so it "
                         "cannot show that the gap is what makes the paths diverge")
        self.assertNotAlmostEqual(
            off, 0.0, places=9,
            msg="the control collapsed to a zero outcome, where agreement is trivial "
                "and two broken paths would also pass")
        self.assertAlmostEqual(
            on, off, places=9,
            msg="the two exits disagree even with NO gap ({:.4f} vs {:.4f}) — the "
                "divergence is no longer attributable to gap accounting".format(on, off))

    def test_the_flag_is_not_inert_for_trades_that_would_stop_out(self):
        """RESEARCH_WEB.md counts this flag among the 'dormant pair': off on both
        sides, so no behavioural difference. That is true of the LIVE path and false
        of the recorded P&L the moment a sweep turns it on."""
        off_et, _ = one(frame(*GAP_DOWN), flag=False)
        on_et, _ = one(frame(*GAP_DOWN), flag=True)
        self.assertNotEqual(
            off_et, on_et,
            "the flag no longer re-routes a would-be stop_hit, so it really is inert "
            "and F241's premise is gone")


class TheInvariantsNeverReachThisBranchTests(unittest.TestCase):
    """Why the property suite did not find the above."""

    SRC = (ROOT / "tests" / "test_compute_returns_properties.py").read_text(encoding="utf-8")

    def test_the_property_generator_omits_the_signal_column(self):
        self.assertNotIn(
            "signal_vote", self.SRC,
            "the property generator now builds signal_vote — it may be able to reach "
            "the opposing branch, so re-derive F241's coverage claim and supersede it")

    def test_no_property_test_enables_the_opposing_exit(self):
        self.assertNotIn(
            "use_opposing_signal_exit", self.SRC,
            "a property test now enables the opposing exit — F241's 'doubly "
            "unreachable' claim is stale; supersede rather than delete this")

    def test_the_suites_lower_bound_is_false_on_this_branch(self):
        """`assertGreater(r, -1.0)`, justified as 'price can't go below zero', is a
        long-only fact. The suite generates shorts, and this branch can show it."""
        self.assertIn("assertGreater(r, -1.0)", self.SRC,
                      "the -1.0 lower bound is gone from the property suite; F241's "
                      "falsification of it no longer applies")
        et, r = one(frame([100, 100, 100, 900, 900], [0, 0, 2, 0, 0], direction=-1),
                    flag=True)
        self.assertEqual(et, "opposing_signal")
        self.assertLessEqual(
            r, -1.0,
            "a short opposing exit into a 9x move no longer breaches -1.0, so the "
            "invariant the property suite asserts is no longer falsifiable here")

    def test_the_long_side_that_production_trades_stays_above_the_bound(self):
        """Non-vacuity for the finding's own scope claim: LONGS_ONLY=True means the
        breach above is a test-correctness issue, not a live risk one."""
        _, r = one(frame(*GAP_DOWN), flag=True)
        self.assertGreater(
            r, -1.0,
            "a LONG opposing exit now breaches -1.0 — that would make this a live "
            "risk finding, not a test-correctness one; re-scope F241")


if __name__ == "__main__":
    unittest.main()
