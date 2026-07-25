"""F149's open question answered: the maxDD point estimate now uses the CI's comparator.

F149 found that `tools/power_study.py` measured the capital-preservation **point estimate**
against `bench` (100% equity) while bootstrapping its **confidence interval** against
`static5050`. The verdict prose then welded them: *"active maxDD far shallower at the point
… but the paired maxDD-gap bootstrap straddles 0"* — inviting the reader to see one
quantity measured two ways when it was two quantities against two benchmarks. F149 left
open which comparison *should* anchor the claim.

**The mechanism, which F149 did not name.** The same swap is harmless for Sharpe and
invalid for drawdown, and the study itself relies on that: it states *"the test is vs
buy&hold (≡ static 50/50, **Sharpe-invariant** — the EASIER bar)"*. Sharpe is
scale-invariant, so `bench` and `0.5 * bench` score identically. **maxDD is not.** On a
representative path, halving the position takes maxDD from −59.6% to −36.4% — a 39%
reduction. The equivalence was carried from the Sharpe path onto the drawdown path, where
it does not hold, and that inflation is what manufactured the "but".

**The anchor is static 50/50, on both sides.** Not because buy&hold is a bad comparator in
general, but because D6's *recommendation* is a static blend: the decision-relevant
question is whether the active engine beats what we would otherwise do. D6 never
recommends 100% equity. Matching the point estimate to the interval also changes one line
rather than re-deriving a bootstrap.

`maxdd_bench` is still reported, now labelled as a reference and explicitly disclaimed as
not a stand-in for the blend.

**Not re-run here.** The corrected numbers need market data, and the caches are empty. This
guards the *shape* of the comparison — that both sides name the same comparator — which is
the defect F149 recorded. The numbers change when someone runs it with data.
"""
import inspect
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import power_study  # noqa: E402

SOURCE = (ROOT / "tools" / "power_study.py").read_text(encoding="utf-8")


class MaxDrawdownIsNotScaleInvariantTests(unittest.TestCase):
    """The arithmetic that makes the swap invalid — and the contrast with Sharpe."""

    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(7)
        cls.r = rng.normal(0.0003, 0.012, 6000)

    def test_halving_the_position_materially_reduces_maxdd(self):
        full = power_study.maxdd_pct(self.r)
        half = power_study.maxdd_pct(0.5 * self.r)
        self.assertLess(full, -20.0, "the fixture no longer draws down meaningfully")
        self.assertGreater(
            half, full,
            "halving the position no longer reduces maxDD — the whole basis of F149's "
            "defect would be gone")
        self.assertGreater(
            (half - full) / abs(full), 0.25,
            "the reduction fell below 25%; the inflation F149 describes has shrunk")

    def test_sharpe_by_contrast_is_exactly_invariant(self):
        """Why the same swap is harmless on the Sharpe path — and why it was copied."""
        sharpe = lambda x: x.mean() / x.std()  # noqa: E731
        self.assertAlmostEqual(sharpe(self.r), sharpe(0.5 * self.r), places=12)
        self.assertAlmostEqual(sharpe(self.r), sharpe(0.25 * self.r), places=12)

    def test_the_study_still_states_the_sharpe_invariance_it_relied_on(self):
        self.assertIn(
            "Sharpe-invariant", SOURCE,
            "the study no longer states the scale-invariance claim — that bullet is the "
            "evidence the swap was copied from the Sharpe path")


class BothSidesNowNameTheSameComparatorTests(unittest.TestCase):
    """The fix. Structural, since the numbers need market data."""

    def test_the_static_5050_drawdown_is_computed(self):
        self.assertIn("dd_static = maxdd_pct(static5050)", SOURCE,
                      "the static-50/50 drawdown is no longer computed — the point "
                      "estimate has nothing consistent to compare against")

    def test_the_bootstrap_still_uses_static_5050(self):
        self.assertIn("dd_boot = paired_maxdd_diff_boot(active, static5050)", SOURCE,
                      "the CI's comparator changed; if it moved to `bench`, the point "
                      "estimate must move with it")

    def test_the_verdict_prose_pairs_the_point_with_the_SAME_comparator(self):
        start = SOURCE.index("Capital-preservation is path-dependent")
        clause = SOURCE[start:start + 700]
        self.assertIn("maxdd_static5050", clause,
                      "the verdict's point estimate no longer reads the static-50/50 "
                      "drawdown — the benchmark swap F149 found has returned")
        self.assertIn("SAME comparator", clause,
                      "the verdict no longer tells the reader both sides share a "
                      "comparator, which is the sentence F149 asked for")

    def test_the_hundred_percent_equity_figure_is_kept_but_DISCLAIMED(self):
        start = SOURCE.index("Capital-preservation is path-dependent")
        clause = SOURCE[start:start + 700]
        self.assertIn("maxdd_bench", clause, "the reference figure was dropped entirely")
        self.assertIn("reference only", clause)
        self.assertIn("not scale-invariant", clause,
                      "the disclaimer no longer says WHY 100% equity cannot stand in "
                      "for the blend")

    def test_the_result_dict_records_which_comparator_anchored_it(self):
        self.assertIn('maxdd_comparator="static5050"', SOURCE,
                      "the result no longer records its own comparator — a future "
                      "reader could not tell which benchmark the CI belongs to")
        self.assertIn("maxdd_static5050=round(dd_static, 1)", SOURCE)

    def test_the_summary_line_matches_the_verdict(self):
        """Two renderings of one number is how the swap survived the first time."""
        start = SOURCE.index("capital-preservation: maxDD active")
        line = SOURCE[start:start + 400]
        self.assertIn("maxdd_static5050", line)
        self.assertIn("reference", line)


class TheFixIsStructuralNotNumericTests(unittest.TestCase):
    """Stated so nobody reads this as a corrected result."""

    def test_no_market_data_is_available_to_re_run_with(self):
        cache = ROOT / "data" / "cache"
        self.assertEqual(
            list(cache.glob("*")) if cache.exists() else [], [],
            "market data appeared — re-run tools/power_study.py and record the "
            "corrected maxDD gap, which will be SMALLER than the previously published "
            "one")

    def test_the_reason_is_recorded_in_the_code_itself(self):
        fn_src = inspect.getsource(power_study)
        self.assertIn("F149", fn_src,
                      "the code no longer cites F149 at the fix site, so the next "
                      "reader cannot find out why the comparator was pinned")


if __name__ == "__main__":
    unittest.main()
