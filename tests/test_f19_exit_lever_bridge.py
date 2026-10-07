"""F19's code bridge: the exit is the lever — and which way it points is set by a flag.

`context_map.json` bridges F19 to `src/strategy/engine.py::compute_trade_returns` and
`config.STOP_LOSS_PCT_TQQQ_HOURLY` with the note *"independent confirmation that the
%-stop exit destroys the edge a horizon exit captures."* The bridge had no `guarded_by`
test, so nothing re-checked it while the code moved.

**Why this one is mechanisable.** F19's headline numbers came from `tools/mr_daily_lab.py`
on 12yr of real daily data, which is not reachable offline. But the *comparison* F19 made
is expressible inside this repo's own function: widen the band far enough that neither
barrier can fire and every trade falls through to the `time_exit` branch — that IS an
N-bar horizon exit. Same entries, same bars, same code path, one parameter changed. So
the within-comparison can be re-run here on synthetic data, testing the arithmetic of
`compute_trade_returns` rather than any claim about markets.

**What the re-run found, including the part that first looked like a refutation.**
The first pass appeared to *contradict* F19: the band exit beat the horizon exit, and got
*better* as intrabar noise rose (+21 → +76 bps as `P(bar range > stop)` went 0.76 → 0.97).
That is backwards from every mechanism F7 and F19 describe.

The cause was not the mechanism. It was `worst_case_ambiguity`, which decides who wins
when a single bar's range contains **both** barriers. Under the honest rule (stop wins,
what `realistic` and `harsh` mode ship) the same trades go +16 → −32 bps — monotonically
*down*, crossing below the horizon exit, exactly F19's sign flip. Under the optimistic
rule (target wins, what `optimistic` mode ships) they go monotonically *up*.

So on identical entries and identical bars, **the flag chooses the conclusion**, and the
wedge between the two scales with the share of trades exiting `ambiguous_same_bar`:

    ambiguous share    optimistic    worst-case    horizon
              1.0%        +15.4         +13.8       +14.4
              9.2%        +26.8         +13.0       +14.4
             22.8%        +35.7          +1.5       +14.4
             50.4%        +59.1         -16.5       +14.4
             72.0%        +75.9         -32.1       +14.4

F19 survives — under the fill rule the project actually uses for its honest numbers. What
it does not survive is optimistic mode, and that is a fact about the flag, not the market.
This is the same optimistic mode CLAUDE.md's stale-performance warning already blames for
the superseded Sharpe 25–94 headline; here it is with a mechanism attached.

**Scope, stated because the anchor is missing.** The ambiguous share is a property of the
data (how often a bar spans target-plus-stop), and **no real bars are committed to this
repo** — `data/cache/` is empty and the four vendor CSVs are gone. So nothing here says
what the ambiguous share IS for TQQQ hourly at its configured 1.0%/0.5% band. The claim
is conditional: *wherever* that share is large, the reported result is chosen by the flag.
Measuring it on real bars is left open.

**Measured under engine v2; re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md).**
The table above is the v2 measurement (scan from N+2, time exit at the last scanned close,
overlapping trades, target-first by default). v3 changes four premises of this fixture:

- ``worst_case_ambiguity`` now defaults to True (stop-first), so the target-first arm must
  ask for it: ``arms()`` passes ``worst_case_ambiguity=False``, which is exactly what the
  ``upper_bound`` mode (formerly ``optimistic``) still passes.
- One position at a time: a band exit frees the slot earlier than the horizon exit, so
  the arms would take different entries. The fixture now spaces signals at least
  ``HORIZON`` bars apart, where one-position never binds and the entries stay identical.
- The horizon arm's time exit fills at the OPEN of bar N+1+HORIZON; the final trade,
  whose scheduled exit falls past the data, is ``time_exit_truncated``.
- The bracket is live from the entry bar N+1.

Re-measured under v3 on the spaced fixture (427 identical entries per arm, bps per trade):

    ambiguous share    upper_bound   worst-case    horizon
              0.5%        +15.6         +14.9       +22.2
              9.6%        +21.9          +7.5       +22.2
             32.8%        +30.0         -19.2       +22.2
             63.9%        +60.3         -35.6       +22.2
             85.0%        +82.1         -45.4       +22.2

F19's direction, its sign flip and the flag-driven wedge all survive. One v2 fact does
not: at low noise the honest band no longer matches the horizon exit within 1 bp. It
trails by 7.3 bps at 0.5% ambiguity (5.1 bps even at zero intrabar range), because the
close path alone reaches the 1%/0.5% band on most trades and capping winners at the
target costs more than the stop saves here. That shortfall is about a tenth of the
high-noise one, so the negative control is re-expressed as a ratio (see
``test_at_LOW_noise_the_band_does_not_underperform``).
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.backtest.runner import BACKTEST_MODES  # noqa: E402
from src.strategy.engine import compute_trade_returns  # noqa: E402

from tests._engine_uncounted import uncounted_module  # noqa: E402

# Engine arithmetic, not a strategy evaluation: runs outside the trial ledger
# (src/strategy/counted.py).
setUpModule, tearDownModule = uncounted_module("F19 bridge: pins the exit mechanics the finding describes, on synthetic bars")


HORIZON = 5
STOP = 0.005            # config.STOP_LOSS_PCT_TQQQ_HOURLY
TARGET = 0.010          # config.TARGET_GAIN_PCT_TQQQ_HOURLY
WIDE = 9.0              # far outside any bar → the band can never fire


def synthetic_frame(n=4000, seed=7, phi=-0.25, sigma=0.006, range_mult=1.0,
                    min_gap=HORIZON):
    """A mean-reverting close path with an INDEPENDENTLY scaled intrabar range.

    Separating the two is the whole point: it lets `range_mult` vary how often a bar
    can trigger a barrier on noise alone while the close-to-close path — and therefore
    the horizon exit, and the entries — stay bit-identical across arms. This is a
    fixture for the arithmetic of an exit rule, not a market model; no claim is made
    from its returns.

    Signals closer than ``min_gap`` bars to the previous kept signal are dropped, so
    ENGINE_VERSION 3's one-position rule never binds: an exit at the open of bar
    S+1+HORIZON frees a signal on bar S+HORIZON, so every arm takes every kept signal.
    """
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = phi * r[i - 1] + rng.normal(0, sigma)
    close = 100 * np.exp(np.cumsum(r))
    op = np.concatenate([[close[0]], close[:-1]])
    half = np.abs(rng.normal(0, sigma * range_mult, n))
    hi = np.maximum(op, close) * (1 + half)
    lo = np.minimum(op, close) * (1 - half)
    idx = pd.date_range("2020-01-01", periods=n, freq="h")
    df = pd.DataFrame({"open": op, "high": hi, "low": lo, "close": close,
                       "volume": 1e6}, index=idx)
    raw = np.flatnonzero((pd.Series(close).pct_change() < -sigma).to_numpy())
    kept, last = [], None
    for i in raw:
        if last is None or i - last >= min_gap:
            kept.append(i)
            last = i
    sig = np.zeros(n, dtype=int)
    sig[kept] = 1
    df["entry_signal"] = sig
    return df


def arms(range_mult):
    """The three exit rules on ONE frame: upper-bound band, honest band, horizon.

    The upper-bound arm passes ``worst_case_ambiguity=False`` explicitly, as the
    ``upper_bound`` mode does; under ENGINE_VERSION 3 the default is stop-first.
    """
    df = synthetic_frame(range_mult=range_mult)
    kw = dict(target_gain_pct=TARGET, stop_loss_pct=STOP, max_trade_bars=HORIZON)
    opt = compute_trade_returns(df, worst_case_ambiguity=False, **kw)
    honest = compute_trade_returns(df, worst_case_ambiguity=True, **kw)
    horizon = compute_trade_returns(df, target_gain_pct=WIDE, stop_loss_pct=WIDE,
                                    max_trade_bars=HORIZON)
    return opt, honest, horizon


def bps(trades):
    return float(trades["return"].mean()) * 1e4


def ambiguous_share(trades):
    return float((trades["exit_type"] == "ambiguous_same_bar").mean())


class TheBridgeStillDescribesTheRunningCodeTests(unittest.TestCase):
    """Structural half. If the exit stopped being a fixed band, F19's note would be
    describing code that no longer exists."""

    def test_the_exit_is_a_fixed_band_with_a_time_exit_fallback(self):
        opt, _honest, _horizon = arms(1.0)
        kinds = set(opt["exit_type"])
        self.assertTrue(
            kinds & {"target_hit", "stop_hit"},
            "no barrier exits fire any more — compute_trade_returns may no longer "
            "implement the fixed %-band F19 concerns. Re-verify F19 and its bridge "
            "rather than editing this test.")

    def test_a_horizon_exit_is_reachable_through_the_SAME_function(self):
        """What makes this a within-comparison and not a comparison of two tools.

        Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): the time
        exit fills at the open of bar N+1+MAX, and only a trade whose scheduled exit falls
        past the end of the data is ``time_exit_truncated`` (the last close). Every trade
        but the final one must take the full-length time exit.
        """
        _opt, _honest, horizon = arms(1.0)
        kinds = list(horizon["exit_type"])
        self.assertEqual(
            set(kinds[:-1]), {"time_exit"},
            "widening the band no longer routes every trade to the time-exit branch, "
            "so F19's horizon arm can no longer be reproduced in this engine")
        self.assertIn(kinds[-1], {"time_exit", "time_exit_truncated"})

    def test_the_arms_share_identical_entries(self):
        """Without this the comparison below is between different trade sets.

        Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): one
        position at a time means a band exit frees the slot before the horizon exit does,
        so on overlapping signals the arms take different entries. The fixture now spaces
        signals ``HORIZON`` bars apart (see ``synthetic_frame``); this test is what proves
        the spacing keeps the trade sets identical, in all three arms.
        """
        opt, honest, horizon = arms(1.0)
        self.assertEqual(len(opt), len(honest))
        self.assertEqual(len(opt), len(horizon))
        self.assertGreater(len(opt), 200, "too few trades to compare")
        self.assertTrue((opt["timestamp"].values == horizon["timestamp"].values).all())
        self.assertTrue((honest["timestamp"].values == horizon["timestamp"].values).all())

    def test_the_configured_tqqq_band_is_tight_and_asymmetric(self):
        """F19's and F7's premise: the stop is the tighter of the two barriers."""
        self.assertAlmostEqual(config.STOP_LOSS_PCT_TQQQ_HOURLY, STOP, places=6,
                               msg="the TQQQ hourly stop moved — F19/F7 rest on this "
                                   "value being tight; re-verify before citing them")
        self.assertLess(config.STOP_LOSS_PCT_TQQQ_HOURLY,
                        config.TARGET_GAIN_PCT_TQQQ_HOURLY)


class F19HoldsUnderTheHONESTFillRuleTests(unittest.TestCase):
    """F19's direction, reproduced with `worst_case_ambiguity=True` — the rule the
    `realistic` and `harsh` modes ship."""

    @classmethod
    def setUpClass(cls):
        cls.rows = [(rm,) + arms(rm) for rm in (0.2, 0.6, 1.0, 2.0, 4.0)]

    def test_the_band_degrades_as_intrabar_noise_rises(self):
        series = [bps(honest) for _rm, _o, honest, _h in self.rows]
        self.assertEqual(
            series, sorted(series, reverse=True),
            "the honest band exit no longer degrades monotonically with intrabar "
            "noise ({}) — that monotonicity IS F7's mechanism and F19's premise; "
            "supersede them rather than editing this test".format(
                [round(x, 1) for x in series]))

    def test_the_band_falls_BELOW_the_horizon_exit_at_high_noise(self):
        """F19's sign flip: same entries, opposite sign."""
        _rm, _opt, honest, horizon = self.rows[-1]
        self.assertLess(
            bps(honest), bps(horizon),
            "under the honest fill rule the tight band no longer underperforms the "
            "horizon exit even at maximum intrabar noise — F19's central claim would "
            "be stale; re-verify it")
        self.assertLess(bps(honest), 0.0, "the band no longer turns negative at all")
        self.assertGreater(bps(horizon), 0.0,
                           "the horizon arm lost its positive edge, so there is no "
                           "'edge the band destroys' left to talk about")

    def test_at_LOW_noise_the_band_does_not_underperform(self):
        """Negative control. A guard that fires at every noise level would be
        asserting 'bands are bad', not F19's noise-conditional mechanism.

        Measured under engine v2 as "the band is within 1 bp of the horizon at low
        noise". Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md):
        under v3 the honest band trails the horizon by 7.3 bps at 0.5% ambiguity on this
        fixture (5.1 bps at zero intrabar range: the close path alone reaches the band,
        and capping winners at the target costs more than the stop saves), so the v2
        1-bp agreement is no longer true and is not asserted. What stays true, and is
        what makes this a NOISE-conditional guard, is that the shortfall grows with
        noise and the low-noise shortfall is a small fraction of the high-noise one
        (measured 7.3 vs 67.6 bps, about 0.11; the bound is 0.2).
        """
        shortfall = [bps(horizon) - bps(honest) for _rm, _opt, honest, horizon in self.rows]
        self.assertEqual(
            shortfall, sorted(shortfall),
            "the band's shortfall to the horizon exit no longer grows with intrabar "
            "noise ({}), so this guard is insensitive to the noise ratio it claims to "
            "measure".format([round(x, 1) for x in shortfall]))
        self.assertLessEqual(
            shortfall[0], 0.2 * shortfall[-1],
            "the band underperforms almost as much when barriers rarely fire as when "
            "they always do ({}), which would mean this guard is asserting 'bands are "
            "bad', not a noise-conditional mechanism".format(
                [round(x, 1) for x in shortfall]))


class TheOptimisticFlagInvertsTheConclusionTests(unittest.TestCase):
    """The part that first looked like a refutation of F19.

    "Optimistic" is the v2 name of what ENGINE_VERSION 3 calls the ``upper_bound`` mode
    (docs/research/ENGINE_V3_QUESTION.md, rule (e)); the class keeps its name because
    context_map.json's F19 bridge cites it in ``guarded_by``. The arm is still
    target-first ambiguity, passed explicitly as ``worst_case_ambiguity=False``.
    """

    @classmethod
    def setUpClass(cls):
        cls.rows = [(rm,) + arms(rm) for rm in (0.2, 0.6, 1.0, 2.0, 4.0)]

    def test_the_two_fill_rules_rank_the_exits_OPPOSITELY_at_high_noise(self):
        _rm, opt, honest, horizon = self.rows[-1]
        self.assertGreater(bps(opt), bps(horizon),
                           "upper_bound mode no longer flatters the band exit")
        self.assertLess(bps(honest), bps(horizon),
                        "the honest rule no longer penalises it")

    def test_the_upper_bound_arm_moves_the_WRONG_way_with_noise(self):
        """More noise cannot make a tight band genuinely better; the upper_bound mode
        says it does, because every ambiguous bar is booked as a win.

        Renamed from test_the_optimistic_arm_moves_the_WRONG_way_with_noise: the
        ``optimistic`` mode is ``upper_bound`` under ENGINE_VERSION 3.
        """
        series = [bps(opt) for _rm, opt, _h, _hz in self.rows]
        self.assertEqual(
            series, sorted(series),
            "upper_bound mode no longer improves monotonically with noise — the "
            "artifact this test documents may have been fixed; check whether that "
            "mode still passes worst_case_ambiguity=False")

    def test_the_wedge_is_driven_by_the_AMBIGUOUS_SHARE(self):
        """The causal link, asserted rather than asserted-by-eye: the gap between the
        two fill rules grows with the fraction of trades whose exit bar contains both
        barriers. At a low share the rules agree — which is the negative control."""
        pairs = [(ambiguous_share(opt), bps(opt) - bps(honest))
                 for _rm, opt, honest, _hz in self.rows]
        shares = [s for s, _w in pairs]
        wedges = [w for _s, w in pairs]
        self.assertEqual(shares, sorted(shares), "fixture no longer sweeps ambiguity")
        self.assertEqual(
            wedges, sorted(wedges),
            "the upper-bound/honest wedge no longer grows with the ambiguous share, so "
            "the ambiguity flag is no longer the mechanism behind the inversion: {}"
            .format([(round(s, 3), round(w, 1)) for s, w in pairs]))
        self.assertLess(shares[0], 0.05, "the low-noise control is no longer low")
        self.assertLess(wedges[0], 5.0,
                        "the two fill rules now disagree even when almost no bar is "
                        "ambiguous — the wedge has another cause; re-investigate")
        self.assertGreater(shares[-1], 0.5)
        self.assertGreater(wedges[-1], 50.0)

    def test_both_fill_rules_are_shipped_modes_not_hypotheticals(self):
        """The inversion matters because the repo offers the reader both.

        Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): the
        ``optimistic`` mode is renamed ``upper_bound``, still passes
        ``worst_case_ambiguity=False`` explicitly, and is marked as an upper bound.
        """
        self.assertNotIn("optimistic", BACKTEST_MODES)
        self.assertFalse(BACKTEST_MODES["upper_bound"]["worst_case_ambiguity"])
        self.assertTrue(BACKTEST_MODES["upper_bound"]["upper_bound"])
        self.assertTrue(BACKTEST_MODES["realistic"]["worst_case_ambiguity"])
        self.assertTrue(BACKTEST_MODES["harsh"]["worst_case_ambiguity"])


class NoRealBarsAreAvailableToAnchorTheShareTests(unittest.TestCase):
    """The scope limit, asserted so it cannot be quietly forgotten.

    Everything above is conditional on the ambiguous share. If real bars ever land in
    the repo, that share becomes measurable for TQQQ hourly at its configured band and
    this guard should be replaced by the measurement.
    """

    def test_the_repo_still_commits_no_bar_data(self):
        csvs = list((ROOT / "docs" / "research" / "data").glob("*.csv"))
        cache = list((ROOT / "data" / "cache").glob("*")) if (
            ROOT / "data" / "cache").exists() else []
        self.assertEqual(
            (csvs, cache), ([], []),
            "bar data is now committed — measure the real ambiguous share for TQQQ "
            "hourly at {}/{} instead of relying on the synthetic sweep above".format(
                config.TARGET_GAIN_PCT_TQQQ_HOURLY, config.STOP_LOSS_PCT_TQQQ_HOURLY))


if __name__ == "__main__":
    unittest.main()
