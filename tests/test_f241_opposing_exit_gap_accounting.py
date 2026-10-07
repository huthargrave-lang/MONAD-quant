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

MEASURED UNDER ENGINE v2; THE PREMISE IS GONE UNDER ENGINE_VERSION 3
(docs/research/ENGINE_V3_QUESTION.md, rule (b)). v3 checks each later bar's OPEN first and
fills an open at or through the stop at that open less ``stop_slippage_pct``
(``gap_stop``). So the stop path now prices the gap at the gapped open, exactly as the
opposing path always did, and the sixtyfold wedge F241 measured no longer exists:

    USE_OPPOSING_SIGNAL_EXIT = False  ->  gap_stop         -60.00%   (the gapped open)
    USE_OPPOSING_SIGNAL_EXIT = True   ->  opposing_signal  -60.00%   (the gapped open)

The one residual is ``stop_slippage_pct``, the measured trigger-to-fill slippage that v3
charges on stop and gap-stop exits only; the opposing exit, a fill at the next open, does
not pay it. With it at zero the two paths agree exactly. The flag still re-labels the
exit (gap_stop vs opposing_signal) and still matters wherever the opposing vote closes a
trade that would NOT have stopped out. This is the "adopt one convention" outcome the
guards below were written to detect; they are re-pinned to the v3 fact and the node's
supersession is a docs change outside tests/.

The coverage half also moved. Under v3 the property generator reaches seven of the eight
exit labels (still never ``opposing_signal``), and one of the new ones, ``gap_stop``, makes
the short-side breach of -1.0 reachable from the generator itself: a short whose stop
bar opens at twice the entry books exactly -1.0. Hypothesis found that frame, so the
property suite now asserts its -1.0 bound for longs only, which is the scope F241 said
it had all along.
"""
import unittest
from pathlib import Path

import pandas as pd

from src.strategy.engine import compute_trade_returns

from tests._engine_uncounted import uncounted_module  # noqa: E402

# Engine arithmetic, not a strategy evaluation: runs outside the trial ledger
# (src/strategy/counted.py).
setUpModule, tearDownModule = uncounted_module("F241: gap accounting of the two exit paths on hand-built bars")

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

    def test_the_stop_path_prices_the_gap_at_the_open(self):
        """The bar OPENED at 40, through the 99 stop: the stop path books the open.

        Measured under engine v2 as an optimistic fill at the stop (-1%, stop_hit).
        Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): an open at
        or through the stop fills at the open less stop_slippage_pct (gap_stop), so the
        v2 premise "the stop path prices the gap at the stop" is false and the test is
        renamed from test_the_stop_path_prices_the_gap_at_the_stop.
        """
        et, r = one(frame(*GAP_DOWN), flag=False)
        self.assertEqual(et, "gap_stop")
        self.assertAlmostEqual(
            r, -0.60, places=9,
            msg="the stop path no longer fills a gapped open at the open — the v3 gap "
                "rule (b) has regressed toward the v2 fill at the stop price")
        res = compute_trade_returns(frame(*GAP_DOWN), use_opposing_signal_exit=False,
                                    stop_slippage_pct=0.003, **EXIT_KW)
        self.assertAlmostEqual(float(res.iloc[0]["return"]), -0.60 - 0.003, places=9,
                               msg="the gap-stop fill no longer pays stop_slippage_pct")

    def test_the_opposing_path_prices_the_gap_at_the_open(self):
        et, r = one(frame(*GAP_DOWN), flag=True)
        self.assertEqual(
            et, "opposing_signal",
            "the opposing exit no longer pre-empts the stop on this frame")
        self.assertAlmostEqual(
            r, -0.60, places=9,
            msg="the opposing exit stopped filling at the next open")

    def test_one_flag_no_longer_changes_the_recorded_loss(self):
        """The headline. Same frame, same prices, one flag.

        Measured under engine v2 as a sixtyfold wedge (-1% vs -60%). Re-pinned for
        ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): both paths now fill the
        gapped open, so the recorded loss is the same with the flag on or off. Renamed
        from test_one_flag_changes_the_recorded_loss_sixtyfold, which is now false. The
        only residual is stop_slippage_pct, charged on the gap-stop path alone.
        """
        _, off = one(frame(*GAP_DOWN), flag=False)
        _, on = one(frame(*GAP_DOWN), flag=True)
        self.assertAlmostEqual(off, -0.60, places=9)
        self.assertAlmostEqual(on, -0.60, places=9)
        self.assertAlmostEqual(
            on, off, places=9,
            msg="the two exits price one gap differently again ({:.4f} vs {:.4f}) — "
                "F241's wedge has come back".format(on, off))
        slip = 0.003
        kw = dict(EXIT_KW, stop_slippage_pct=slip)
        off_s = float(compute_trade_returns(frame(*GAP_DOWN), use_opposing_signal_exit=False,
                                            **kw).iloc[0]["return"])
        on_s = float(compute_trade_returns(frame(*GAP_DOWN), use_opposing_signal_exit=True,
                                           **kw).iloc[0]["return"])
        self.assertAlmostEqual(on_s - off_s, slip, places=9,
                               msg="the residual between the two paths is no longer "
                                   "exactly the stop slippage")

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
        of the recorded P&L the moment a sweep turns it on.

        Measured under engine v2, where the re-route also re-priced the loss. Under
        ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md) the flag still re-routes
        a would-be gap_stop to opposing_signal, but on this gapped frame both fill the
        same open (see test_one_flag_no_longer_changes_the_recorded_loss).
        """
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

    def test_the_suites_lower_bound_is_scoped_to_longs_because_shorts_breach_it(self):
        """`assertGreater(r, -1.0)`, justified as 'price can't go below zero', is a
        long-only fact. The suite generates shorts, and this branch can show it.

        Measured under engine v2, where only the unreachable opposing branch could breach
        it, so the suite's unscoped bound was false but never tripped. Re-pinned for
        ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): gap_stop fills a gapped
        open, so a short's breach is reachable from the property generator and the suite
        now scopes the bound to longs. Renamed from
        test_the_suites_lower_bound_is_false_on_this_branch. Both short-side breaches are
        asserted, so the scoping stays justified.
        """
        self.assertIn("assertGreater(r, -1.0)", self.SRC,
                      "the -1.0 lower bound is gone from the property suite; the long "
                      "side has lost its guard")
        bound_at = self.SRC.index("assertGreater(r, -1.0)")
        self.assertIn("if direction == 1:", self.SRC[max(0, bound_at - 200):bound_at],
                      "the property suite's -1.0 bound is no longer scoped to longs, "
                      "and shorts breach it (below)")
        et, r = one(frame([100, 100, 100, 900, 900], [0, 0, 2, 0, 0], direction=-1),
                    flag=True)
        self.assertEqual(et, "opposing_signal")
        self.assertLessEqual(
            r, -1.0,
            "a short opposing exit into a 9x move no longer breaches -1.0, so the "
            "long-only scoping of the property suite's bound is no longer justified here")
        et, r = one(frame([100, 100, 100, 900, 900], [0, 0, 0, 0, 0], direction=-1),
                    flag=False)
        self.assertEqual(et, "gap_stop")
        self.assertAlmostEqual(r, -8.0, places=9,
                               msg="a short gap-stop into a 9x open no longer books the open")

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
