"""The sweep's cost model is one number, and the strategy trades where it is wrong — F242.

`sweep.py:228-245` takes a single scalar for the whole sweep window:

    median_price      = df_raw["close"].median()
    est_spread        = estimate_spread(median_price, broker)
    SLIPPAGE_PCT      = round_trip_cost_pct(est_spread, median_price)   # every trade
    auto_min_stop_pct = max(0.15, (5 * est_spread / median_price) * 100)

Both the per-trade cost charged to every trade AND the minimum-stop floor are point
estimates at the window median. Until now neither had ever been evaluated against real
prices — `H24`/`H25` prescribe running `sweep.py`, which needs market data the providers
403 on here, so the arithmetic in `tests/test_h24_h25_stop_vs_spread_floor.py` stops at
"needs one median price per instrument".

**This repo already contains real prices.** `data/live_runs/archive_2026-06-18_pre_clean_run/`
is a committed export of the live paper run: 543 logged TQQQ bars (2026-03-24 → 2026-06-17)
and 65 logged trades. Enough to evaluate the model for one instrument.

WHAT IT SHOWS.

1. **TQQQ's stop clears, at every broker tier.** Median $64.79; the 0.50% stop clears a
   0.150% floor (IBKR) through a 0.309% floor (retail). H24's TQQQ row is confirmed on
   real data rather than assumed.

2. **The window is not narrow enough for one number.** Those 543 bars span $37.37–$84.75,
   a 2.27x range that crosses the $50 spread tier. The true per-bar round-trip cost ranges
   0.0118%–0.0268% (IBKR) around a modelled constant of 0.0154% — the model is a single
   point inside a 2.3x spread of real values.

3. **The error is not mean-zero over trades, because this strategy is a dip-buyer.** Over
   *bars* the mean error is essentially zero (−0.0015 pp, IBKR) — the median is doing its
   job. Over the 65 *logged trades* it is a 10.7% understatement, with 62% of trades
   under-charged, because RSI-dip entries sit below the bar median ($61.87 vs $64.79).
   Spread-as-a-fraction-of-price rises as price falls, so a mean-reversion entry is
   selecting for exactly the bars the constant under-charges.

   **Magnitude, stated so it is not oversold:** ~0.0017 pp per trade, ~0.04 pp/month at
   TQQQ's ~24 trades/mo. Small. The finding is the *direction and mechanism*, not the size
   — and the size scales with trade count and with an instrument's price range.

4. **TNA is the mode with no margin.** `config.py:359` sets TNA's stop to 0.0015 — exactly
   the hard 0.15% floor, annotated "tight but TNA has tighter spreads", an assumption no
   data in this repository supports. A parameter sitting exactly on its own safety boundary
   means the constraint bound, and it is the one mode where the median-price point estimate
   decides pass/fail outright. SOXL (0.45%) and LABU (0.25%) have margin; TQQQ is clear.

STILL BLOCKED, AND NAMED: SOXL/LABU/TNA median prices. H24 cannot be closed for those three
here. What changes is that its threshold table is now a *time-varying* precondition
validated end-to-end on one instrument, not an untested formula.

Guards are bidirectional. They fail if the model becomes per-bar (good news — supersede
this node rather than retune the numbers), if TQQQ stops clearing its floor, if the
dip-buyer skew inverts, or if TNA gains/loses its zero margin.
"""
import json
import statistics as st
import unittest
from pathlib import Path

from src.optimization.sweep_costs import estimate_spread, round_trip_cost_pct

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"

HARD_FLOOR_PCT = 0.15          # sweep.py:245, the max(0.15, ...) term
SAFE_STOP_MULTIPLE = 5         # "safe stop = 5x spread"


def _bars():
    out = []
    for line in (RUN / "signal_history.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("bar_close"):
                out.append(float(row["bar_close"]))
    return out


def _trade_entries():
    """Entry price recovered from the logged exit and return (long: exit = entry*(1+r))."""
    out = []
    for line in (RUN / "trades.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        if t.get("exit_price") is None or t.get("return_pct") is None:
            continue
        out.append(float(t["exit_price"]) / (1.0 + float(t["return_pct"]) / 100.0))
    return out


def floor_pct(price, broker):
    return max(HARD_FLOOR_PCT,
               (SAFE_STOP_MULTIPLE * estimate_spread(price, broker) / price) * 100)


def true_cost_pct(price, broker):
    return round_trip_cost_pct(estimate_spread(price, broker), price) * 100


class TheFixtureIsRealPricesTests(unittest.TestCase):
    """If this drifts, every number below is measuring something else."""

    def test_the_committed_live_run_still_carries_bars_and_trades(self):
        bars, trades = _bars(), _trade_entries()
        self.assertEqual(len(bars), 543, "logged bar count changed")
        self.assertEqual(len(trades), 65, "logged trade count changed")

    def test_the_window_spans_a_spread_tier(self):
        """The point-estimate critique needs the window to actually be wide."""
        bars = _bars()
        lo, hi = min(bars), max(bars)
        self.assertAlmostEqual(lo, 37.37, places=2)
        self.assertAlmostEqual(hi, 84.75, places=2)
        self.assertLess(lo, 50.0)
        self.assertGreater(hi, 50.0,
                           "the run no longer crosses the $50 tier, so a single "
                           "estimate_spread() tier would cover the whole window")


class TheStopFloorHoldsForTQQQTests(unittest.TestCase):
    """H24's TQQQ row, evaluated on real prices instead of assumed."""

    TQQQ_STOP_PCT = 0.50

    def test_the_median_is_what_the_model_would_use(self):
        self.assertAlmostEqual(st.median(_bars()), 64.79, places=2)

    def test_tqqqs_stop_clears_the_floor_at_every_broker_tier(self):
        med = st.median(_bars())
        for broker in ("ibkr", "schwab", "fidelity", "retail"):
            with self.subTest(broker=broker):
                self.assertGreaterEqual(
                    self.TQQQ_STOP_PCT, floor_pct(med, broker),
                    "TQQQ's 0.50% stop fell inside the {} floor — H24's concern now "
                    "reaches the live mode".format(broker))

    def test_the_ibkr_floor_is_pinned_by_the_hard_minimum_not_the_spread(self):
        """Non-vacuity: 'clears' must not be an artifact of a floor that is trivially
        low. At IBKR the spread term is BELOW the hard 0.15% minimum, so the hard
        minimum is what binds — worth knowing, because it means the IBKR floor carries
        no information about the spread at all."""
        med = st.median(_bars())
        spread_term = (SAFE_STOP_MULTIPLE * estimate_spread(med, "ibkr") / med) * 100
        self.assertLess(spread_term, HARD_FLOOR_PCT)
        self.assertAlmostEqual(floor_pct(med, "ibkr"), HARD_FLOOR_PCT, places=9)
        # ...and at retail the spread term DOES bind, so the two tiers differ in kind.
        retail_term = (SAFE_STOP_MULTIPLE * estimate_spread(med, "retail") / med) * 100
        self.assertGreater(retail_term, HARD_FLOOR_PCT,
                           "the retail floor is now also pinned by the hard minimum, so "
                           "no broker tier exercises the spread term")


class ThePointEstimateMissesWhereTheStrategyTradesTests(unittest.TestCase):

    def test_the_true_per_bar_cost_spans_the_modelled_constant(self):
        bars = _bars()
        med = st.median(bars)
        modelled = true_cost_pct(med, "ibkr")
        true = sorted(true_cost_pct(p, "ibkr") for p in bars)
        self.assertLess(true[0], modelled, "no bar is cheaper than the modelled cost")
        self.assertGreater(true[-1], modelled, "no bar is dearer than the modelled cost")
        self.assertGreater(
            true[-1] / true[0], 2.0,
            "the true cost no longer spans >2x across the window, so one constant is "
            "a defensible summary and F242's premise weakens")

    def test_over_bars_the_median_is_nearly_unbiased(self):
        """The control that makes the next test mean something. The model is NOT
        crudely wrong on the window it was fitted to."""
        bars = _bars()
        modelled = true_cost_pct(st.median(bars), "ibkr")
        mean_err = st.mean(modelled - true_cost_pct(p, "ibkr") for p in bars)
        self.assertLess(
            abs(mean_err), 0.005,
            "the point estimate is now materially biased over BARS too, which would "
            "make F242's trade-selection mechanism redundant rather than the cause")

    def test_over_trades_it_understates_because_entries_sit_low(self):
        bars, entries = _bars(), _trade_entries()
        self.assertLess(
            st.median(entries), st.median(bars),
            "logged trade entries no longer sit below the bar median — the dip-buyer "
            "skew that drives F242 has inverted; re-derive it")
        modelled = true_cost_pct(st.median(bars), "ibkr")
        mean_true_trades = st.mean(true_cost_pct(p, "ibkr") for p in entries)
        self.assertGreater(
            mean_true_trades, modelled,
            "the modelled cost no longer understates the true cost of real trades")
        understatement = 100 * (mean_true_trades - modelled) / modelled
        self.assertAlmostEqual(
            understatement, 10.7, delta=1.5,
            msg="trade-level understatement moved off 10.7% — if the sweep switched to "
                "a per-trade cost, supersede F242 rather than retune this")

    def test_the_understatement_is_small_in_absolute_terms(self):
        """Guards the finding's own modesty claim, so it cannot be inherited as a
        headline-sized effect."""
        bars, entries = _bars(), _trade_entries()
        modelled = true_cost_pct(st.median(bars), "ibkr")
        per_trade_pp = st.mean(true_cost_pct(p, "ibkr") for p in entries) - modelled
        self.assertLess(
            per_trade_pp, 0.01,
            "the per-trade understatement grew past 0.01 pp — F242 is recorded as a "
            "small, structural effect and would need re-scoping as a material one")


class TNAHasNoMarginTests(unittest.TestCase):

    def test_tnas_configured_stop_sits_exactly_on_the_hard_floor(self):
        import config
        stop_pct = float(config.STOP_LOSS_PCT_TNA_HOURLY) * 100
        self.assertAlmostEqual(
            stop_pct, HARD_FLOOR_PCT, places=9,
            msg="TNA's stop moved off the hard floor ({:.4f}% vs {:.4f}%) — if it gained "
                "margin that is good news; supersede F242's zero-margin claim".format(
                    stop_pct, HARD_FLOOR_PCT))

    def test_the_other_leveraged_modes_do_have_margin(self):
        """Non-vacuity: 'sits on the floor' is only meaningful if others don't."""
        import config
        for name, attr in (("SOXL", "STOP_LOSS_PCT_SOXL_HOURLY"),
                           ("LABU", "STOP_LOSS_PCT_LABU_HOURLY")):
            with self.subTest(mode=name):
                self.assertGreater(
                    float(getattr(config, attr)) * 100, HARD_FLOOR_PCT,
                    "{} is now also pinned to the floor, so TNA is not distinctive "
                    "and F242's margin comparison needs re-deriving".format(name))

    def test_tnas_zero_margin_makes_its_price_precondition_binding(self):
        """At a 0.15% stop the spread term must not exceed the hard floor, which pins a
        minimum price. This is the number H24 needs and cannot get for TNA."""
        needed = SAFE_STOP_MULTIPLE * estimate_spread(100.0, "ibkr") / (HARD_FLOOR_PCT / 100)
        # Fixed point: the spread used to solve must be the spread that actually applies
        # AT the solved price, or the threshold is quoted from the wrong tier.
        self.assertAlmostEqual(
            estimate_spread(needed, "ibkr"), estimate_spread(100.0, "ibkr"), places=9,
            msg="the solved price ${:.2f} falls in a different IBKR spread tier than the "
                "one used to solve it — re-solve within the tier".format(needed))
        self.assertAlmostEqual(
            needed, 33.33, delta=0.5,
            msg="TNA's implied minimum price moved off ~$33.3; H24's precondition changed")


if __name__ == "__main__":
    unittest.main()
