"""The sign test looks significant and is not — F267, refining F266.

F266 recorded that CEF price mean-reversion is negative on 8 of 8 tickers and that the
committed artifact carries no dispersion, so the effect "cannot be distinguished from
noise". A sign test needs no dispersion, so the obvious next move is to try one:

    8 of 8 negative  ->  exact two-tailed binomial p = 0.0078

That looks decisive and **is not**, because the exact test assumes the eight tickers are
independent draws. They are same-market closed-end funds. Under a Kish-style effective
sample size, `n_eff = n / (1 + (n-1) * rho)`:

    rho = 0.0  ->  n_eff = 8.00      (the p = 0.0078 case, and unattainable in practice)
    rho = 0.3  ->  n_eff = 2.58
    rho = 0.6  ->  n_eff = 1.54
    rho = 0.9  ->  n_eff = 1.10

A sign test on ~2 observations cannot reach significance at any threshold — the smallest
attainable two-tailed p at n=2 is 0.5. So the honest bound is **p in [0.0078, 1.0]** with
the realistic end nowhere near the left edge, and F266's original claim stands rather than
being overturned. **This node exists because the check was worth running and reporting
negative**, not because it changed the verdict.

The artifact records nothing that narrows the bound: it has no cross-ticker correlation.
`cross_ticker_correlation()` now emits mean/min/max pairwise rho and the derived
`effective_n`, so the next run can state a real p instead of a bound.

**Two genuinely new facts, both from committed data:**

1. **The tradable form is 7 of 8, not 8 of 8.** The *correlation* is negative on every
   ticker, but the quintile spread — long the low-trailing quintile, short the high, which
   is what you would actually trade — is positive on only seven; EOS's control is −0.43%.
   Sign test on that: p = 0.0703 even under the generous independence assumption.

2. **The fixed-income / equity split does not separate the price signal.** F266 proposed
   testing whether fixed-income CEFs behave differently. On the price-only spread they do
   not: +1.47% (PDI/BBN/HYT/NUV) against +1.54% (BDJ/EOS/RVT/UTF). The *correlation* is
   stronger in fixed income (−0.224 vs −0.144), but the tradable spread is flat across the
   split — so a fixed-income-only universe is not the free improvement it looked like.

   What the split *does* isolate is the discount thesis's fragility, which sits entirely in
   the equity group: UTF (−4.17%) and EOS (control negative) are both there.

Guards are bidirectional: they fail if the sign counts change, if the effective-n arithmetic
stops collapsing under correlation (which would make the sign test usable — supersede), or
if the artifact gains cross-ticker correlation, which would replace the bound with a number.
"""
import json
import statistics as st
import sys
import unittest
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cef_discount_lab as lab  # noqa: E402

ARTIFACT = ROOT / "docs" / "research" / "data" / "cef_discount_pilot_result.json"
FIXED_INCOME = ("PDI", "BBN", "HYT", "NUV")
EQUITY = ("BDJ", "EOS", "RVT", "UTF")


def sign_p(k, n):
    """Exact two-tailed binomial at p=0.5."""
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)


def _ctrl():
    a = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    return {c["ticker"]: c for c in a["price_only_controls"]}, \
           {r["ticker"]: r for r in a["rows"]}


class TheSignTestLooksSignificantTests(unittest.TestCase):

    def test_the_correlation_is_negative_on_every_ticker(self):
        ctrl, _ = _ctrl()
        k = sum(1 for c in ctrl.values() if c["corr_trail_fut"] < 0)
        self.assertEqual(k, 8)
        self.assertAlmostEqual(sign_p(k, 8), 0.0078, places=4)


class AndTheEffectiveSampleSizeKillsItTests(unittest.TestCase):

    def _n_eff(self, n, rho):
        return n / (1.0 + (n - 1) * rho)

    def test_modest_correlation_collapses_eight_tickers_to_about_two(self):
        self.assertAlmostEqual(self._n_eff(8, 0.0), 8.0, places=2)
        self.assertAlmostEqual(self._n_eff(8, 0.3), 2.58, places=2)
        self.assertAlmostEqual(self._n_eff(8, 0.6), 1.54, places=2)

    def test_a_sign_test_on_two_observations_cannot_reach_significance(self):
        """The reason the collapse is fatal rather than merely weakening."""
        self.assertAlmostEqual(sign_p(2, 2), 0.5, places=6)
        self.assertGreater(
            sign_p(3, 3), 0.2,
            "a 3-observation sign test became significant — re-derive F267")

    def test_the_artifact_cannot_narrow_the_bound(self):
        a = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        self.assertNotIn(
            "cross_ticker", a["summary"],
            "the artifact now records cross-ticker correlation — a real p is "
            "computable and F267's bound should be replaced; supersede")

    def test_the_lab_now_emits_what_would_narrow_it(self):
        src = (ROOT / "tools" / "cef_discount_lab.py").read_text(encoding="utf-8")
        self.assertIn("def cross_ticker_correlation", src)
        self.assertIn("effective_n", src)

    def test_the_effective_n_helper_is_wired_into_the_summary(self):
        src = (ROOT / "tools" / "cef_discount_lab.py").read_text(encoding="utf-8")
        self.assertIn('"cross_ticker": cross', src,
                      "cross_ticker_correlation is computed but not emitted — a dead "
                      "lever (F145 family)")


class TheTradableFormIsWeakerThanTheCorrelationTests(unittest.TestCase):

    def test_the_quintile_spread_is_positive_on_only_seven(self):
        ctrl, _ = _ctrl()
        k = sum(1 for c in ctrl.values() if -c["high_minus_low"] > 0)
        self.assertEqual(
            k, 7,
            "the tradable spread's sign count changed — it is 7/8 while the "
            "correlation is 8/8, which is the distinction F267 records")
        self.assertAlmostEqual(sign_p(k, 8), 0.0703, places=4)

    def test_eos_is_the_one_whose_tradable_control_is_negative(self):
        ctrl, _ = _ctrl()
        self.assertLess(-ctrl["EOS"]["high_minus_low"], 0)
        self.assertLess(ctrl["EOS"]["corr_trail_fut"], 0,
                        "EOS's correlation is no longer negative, so it no longer "
                        "illustrates correlation and spread disagreeing")


class TheFixedIncomeSplitDoesNotSeparateThePriceSignalTests(unittest.TestCase):

    def test_the_price_only_spread_is_flat_across_the_split(self):
        ctrl, _ = _ctrl()
        fi = st.mean(-ctrl[t]["high_minus_low"] for t in FIXED_INCOME)
        eq = st.mean(-ctrl[t]["high_minus_low"] for t in EQUITY)
        self.assertAlmostEqual(fi, 0.0147, places=4)
        self.assertAlmostEqual(eq, 0.0154, places=4)
        self.assertLess(
            abs(fi - eq), 0.005,
            "the two groups' price-only spreads have separated — a fixed-income-only "
            "universe may now be the improvement F266 hoped for; re-derive")

    def test_the_correlation_is_stronger_in_fixed_income(self):
        """The one place the split does show something, recorded so it is not lost."""
        ctrl, _ = _ctrl()
        fi = st.mean(ctrl[t]["corr_trail_fut"] for t in FIXED_INCOME)
        eq = st.mean(ctrl[t]["corr_trail_fut"] for t in EQUITY)
        self.assertLess(fi, eq)
        self.assertAlmostEqual(fi, -0.224, delta=0.01)
        self.assertAlmostEqual(eq, -0.144, delta=0.01)

    def test_the_discount_theses_fragility_sits_in_the_equity_group(self):
        ctrl, rows = _ctrl()
        worst = min(rows, key=lambda t: rows[t]["cheap_minus_rich_price"]
                    + ctrl[t]["high_minus_low"])
        self.assertIn(worst, EQUITY)
        self.assertEqual(worst, "UTF")


if __name__ == "__main__":
    unittest.main()
