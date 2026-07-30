"""The CEF pilot's CONTROL is where the signal is — F266, a new strategy candidate.

`CEF-DISCOUNT` tested whether a NAV-discount z-score predicts 20-bar forward returns on
eight closed-end funds, and reported `first_cut_supports_long_cheap: true` with a mean
cheap-minus-rich spread of **+1.76%**. It carried a price-only control — rank by trailing
return instead of by discount — annotated *"negative high_minus_low is price MR; not the
discount thesis"*, i.e. treated as a nuisance.

**The nuisance captures 86% of the effect.**

    mean discount spread    +1.76%
    mean price-only spread  +1.50%      <- needs no NAV data at all
    excess of discount      +0.25%

And the excess is not robust: the discount signal beats its own control on **6 of 8**
tickers, and UTF flips hard (−4.17% against a +0.99% control, a −5.16pp excess) — one name
carrying most of the dispersion. The price-only effect is the steadier one: the trailing-vs-
forward correlation is **negative on 8 of 8** tickers (mean −0.184, range −0.297 to −0.007).

So the tradable claim is not the discount thesis. It is **price mean-reversion in CEFs**,
which needs only price data — and the NAV proxies the thesis depends on are exactly what
this environment cannot fetch.

**Why this is not the strategy D6 killed.** D6 found no risk-adjusted edge for active
mean-reversion on BTC/QQQ/TQQQ — instruments with no anchor, where "cheap" is only relative
to recent price. A closed-end fund has a NAV anchor and a structurally persistent discount,
so its price reverting IS the discount reverting; the 86% overlap is evidence they are one
phenomenon measured two ways. Whether that anchor makes the reversion survive out of sample
is the open question, not something these numbers settle.

**The economics clear costs, which is the easy part.** A 1.5% gross spread over ~20 bars
against round-trip friction on a $15 name is 0.067% (IBKR) to 0.20% (retail) per leg, so
0.13%–0.40% for a two-leg spread — net roughly **1.1%–1.4% per rebalance**. Equity spread
tiers stand in for CEF spreads here and CEFs are typically wider, so that is optimistic by
construction.

**The blocker is power, and it is a RECORDING gap rather than a data-access one.** The
pilot reports `n_pairs=421` per ticker, but windows overlap at step 1 with a 20-bar horizon:
there are only **25 non-overlapping windows per ticker** over the 501 aligned bars, and the
eight names are same-market, so pooling does not buy eight times the information. Worse, the
artifact records **means with no dispersion**, and `raw_charts_committed: false` — so no
later reader can compute a standard error from what is committed. The effect cannot be
distinguished from noise, and not because the data is unreachable.

That is fixable at write time and costs nothing: `_quintile_spread` now emits per-side SD
and n alongside the means, and both the ticker rows and the control carry `n_independent`
(the non-overlapping count) so a standard error is built on the right denominator. The same
gap F262 found when F204's single RSI figure turned out to sit at the 97th percentile of its
own distribution.

Guards below pin the comparison that reframes the pilot, the dispersion helper on synthetic
input, and the power arithmetic. They fail if the artifact is re-run with different numbers
(re-derive rather than edit), and — the good-news direction — if the artifact ever gains
dispersion, which would make the significance question answerable and supersede this node.
"""
import json
import statistics as st
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cef_discount_lab as lab  # noqa: E402

ARTIFACT = ROOT / "docs" / "research" / "data" / "cef_discount_pilot_result.json"


def _artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


class TheControlCapturesMostOfTheEffectTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        a = _artifact()
        cls.rows = {r["ticker"]: r for r in a["rows"]}
        cls.ctrl = {c["ticker"]: c for c in a["price_only_controls"]}
        cls.summary = a["summary"]

    def _discount(self, t):
        return self.rows[t]["cheap_minus_rich_price"]

    def _price_only(self, t):
        # same direction: long the low-trailing quintile, short the high
        return -self.ctrl[t]["high_minus_low"]

    def test_the_pilot_still_claims_the_thesis_passes(self):
        """The premise this node reframes. If the pilot's own verdict changed,
        re-derive rather than assume."""
        self.assertTrue(self.summary["first_cut_supports_long_cheap"])
        self.assertAlmostEqual(self.summary["mean_cheap_minus_rich_price"], 0.0176,
                               places=4)

    def test_price_only_captures_most_of_the_discount_spread(self):
        disc = st.mean(self._discount(t) for t in self.rows)
        prc = st.mean(self._price_only(t) for t in self.ctrl)
        self.assertAlmostEqual(disc, 0.0176, places=4)
        self.assertAlmostEqual(prc, 0.0150, places=4)
        share = prc / disc
        self.assertGreater(
            share, 0.75,
            "the price-only control no longer explains most of the discount spread "
            "({:.0%}) — the NAV data may now be earning its cost; supersede".format(share))

    def test_the_discount_excess_is_small_and_not_unanimous(self):
        excess = [self._discount(t) - self._price_only(t) for t in self.rows]
        self.assertAlmostEqual(st.mean(excess), 0.0025, delta=0.0005)
        beats = sum(1 for x in excess if x > 0)
        self.assertEqual(beats, 6, "the count of tickers where discount beats its "
                                   "control changed")

    def test_one_ticker_carries_the_dispersion(self):
        """UTF is the outlier; a mean over 8 with a −5pp member is fragile."""
        worst = min(self.rows, key=lambda t: self._discount(t) - self._price_only(t))
        self.assertEqual(worst, "UTF")
        self.assertLess(self._discount("UTF") - self._price_only("UTF"), -0.04)

    def test_price_reversion_is_sign_consistent_across_every_ticker(self):
        """The reason the control, not the thesis, is the candidate."""
        corrs = [c["corr_trail_fut"] for c in self.ctrl.values()]
        self.assertEqual(len(corrs), 8)
        self.assertTrue(all(c < 0 for c in corrs),
                        "price mean-reversion is no longer negative on every ticker")
        self.assertAlmostEqual(st.mean(corrs), -0.184, delta=0.01)


class ThePowerIsTheBlockerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.a = _artifact()

    def test_windows_overlap_so_n_pairs_overstates_the_sample(self):
        row = self.a["rows"][0]
        horizon = self.a["summary"]["horizon_bars"]
        independent = row["n_aligned"] // horizon
        self.assertGreater(row["n_pairs"], 400)
        self.assertEqual(independent, 25)
        self.assertLess(
            independent, row["n_pairs"] / 10,
            "overlap no longer inflates the reported pair count by >10x")

    def test_the_committed_artifact_carries_no_dispersion(self):
        """The blocker, stated as a property of the file. When this fails, the
        significance question becomes answerable and F266 should be superseded."""
        row = self.a["rows"][0]
        self.assertNotIn("dispersion_price", row,
                         "the artifact now records dispersion — re-run the pilot and "
                         "compute the standard error; supersede F266")
        self.assertFalse(self.a["source"]["raw_charts_committed"],
                         "raw charts are committed now, so dispersion is recoverable")


class TheLabNowRecordsDispersionTests(unittest.TestCase):
    """The fix: the NEXT run will be decisive even though this one cannot be."""

    def test_the_helper_reports_means_sd_and_n_per_side(self):
        ranked = [(float(i), float(i)) for i in range(10)]
        got = lab._quintile_spread(ranked, 2)
        self.assertEqual(got["low_n"], 2)
        self.assertEqual(got["high_n"], 2)
        self.assertAlmostEqual(got["low_mean"], 0.5, places=4)
        self.assertAlmostEqual(got["high_mean"], 8.5, places=4)
        self.assertIsNotNone(got["low_sd"])
        self.assertIsNotNone(got["high_sd"])

    def test_a_single_member_quintile_reports_no_sd_rather_than_zero(self):
        """Non-vacuity: a fabricated 0.0 would read as 'no variance observed'."""
        got = lab._quintile_spread([(1.0, 1.0), (2.0, 2.0)], 1)
        self.assertIsNone(got["low_sd"])
        self.assertIsNone(got["high_sd"])

    def test_dispersion_is_not_constant_across_inputs(self):
        """A helper that always returned the same SD would pass the first test."""
        tight = lab._quintile_spread([(float(i), 1.0) for i in range(10)], 3)
        wide = lab._quintile_spread([(float(i), float(i * i)) for i in range(10)], 3)
        self.assertAlmostEqual(tight["low_sd"], 0.0, places=6)
        self.assertGreater(wide["high_sd"], 1.0)

    def test_the_lab_emits_the_independent_window_count(self):
        src = (ROOT / "tools" / "cef_discount_lab.py").read_text(encoding="utf-8")
        self.assertIn("n_independent", src)
        self.assertIn("dispersion_price", src)
        self.assertIn("dispersion", src)


if __name__ == "__main__":
    unittest.main()
