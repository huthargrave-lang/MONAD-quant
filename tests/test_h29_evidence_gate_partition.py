"""H29's "ready for real money" gate rests on the lossy partition F202 found.

H29 calls `ops/analyze_run.py`'s clean-run rubric "the evidence gate that blocks
everything". Running the protocol needs a live week and a sweep with market data, neither
available here. What IS checkable is what the gate measures — and it inherits F202's defect
in a second, independent copy.

**The same contaminated set, defined twice.** `analyze_run.py:27` declares
`ACTUAL = {"bracket_exit", "stop_hit"}` with the comment *"exits with a confirmed fill
price"* — the same partition as `ctx.CONFIRMED`, in a separate file. Both include
`stop_hit`, which `_infer_bracket_exit` can produce without a fill; both exclude
`target_hit`, which the broker writes from a real LMT fill. Two implementations of one
fact, wrong the same way, so neither can catch the other (F20/F145/F189's pattern, now
with both copies defective).

**And the gate's verdict flips on the ambiguity.** Its criterion is
*"≥80% of fills are confirmed"*. On the committed 65-trade run:

    partition                                 confirmed      verdict
    bracket_exit + stop_hit  (as written)      47/65 = 72.3%   FAIL
    bracket_exit only        (provably actual) 41/65 = 63.1%   FAIL
    bracket_exit + stop_hit + target_hit       53/65 = 81.5%   PASS

The 80% bar sits **inside** the band the ambiguity spans. So the gate that is supposed to
authorise real money returns a different answer depending on a distinction the ledger
cannot make. That is the strongest available argument for H28's column — stronger than
"PnL is uninterpretable", because here a specific go/no-go decision changes.

**A whole exit class is also unclassified.** The rubric buckets exits into `ACTUAL`,
`ARTIFACT` (`time_exit`) and `SYNTH` (`estimated_close`, `paper_reset`). `target_hit`
appears in none of them — its 6 trades count toward `ALL trades` and toward nothing else,
so they are invisible in every per-bucket line the report prints.

Not fixed here: correcting the partition needs the provenance H28 asks for, and picking a
bucket for `target_hit` without it would just move the error. Recorded and bounded.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402

GATE = ROOT / "ops" / "analyze_run.py"
TRADES = (ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"
          / "trades.jsonl")


def gate_sets():
    """Read the three buckets straight out of the gate's source."""
    import re
    text = GATE.read_text(encoding="utf-8")
    out = {}
    for name in ("ACTUAL", "ARTIFACT", "SYNTH"):
        m = re.search(r"^{}\s*=\s*\{{([^}}]*)\}}".format(name), text, re.M)
        out[name] = set(re.findall(r'"([a-z_]+)"', m.group(1)))
    return out


def trades():
    return [json.loads(l) for l in TRADES.read_text(encoding="utf-8").splitlines()
            if l.strip()]


class TheGateDuplicatesTheContaminatedPartitionTests(unittest.TestCase):
    def test_it_defines_its_own_copy_of_the_confirmed_set(self):
        self.assertEqual(
            gate_sets()["ACTUAL"], set(ctx.CONFIRMED),
            "the gate's ACTUAL set and ctx.CONFIRMED have diverged. That is not "
            "automatically good — check which one is right rather than assuming the "
            "difference is the fix")

    def test_both_include_the_possibly_inferred_type(self):
        self.assertIn("stop_hit", gate_sets()["ACTUAL"])
        self.assertIn("stop_hit", set(ctx.CONFIRMED))

    def test_both_exclude_the_possibly_actual_type(self):
        self.assertNotIn("target_hit", gate_sets()["ACTUAL"])
        self.assertNotIn("target_hit", set(ctx.CONFIRMED))

    def test_the_gate_calls_it_a_CONFIRMED_FILL_PRICE(self):
        """The comment is the claim; it is the thing that is not true of stop_hit."""
        self.assertIn(
            "exits with a confirmed fill price", GATE.read_text(encoding="utf-8"),
            "the gate no longer claims these are confirmed fill prices — if the "
            "comment was corrected, check whether the SET was too")


class TargetHitFallsThroughEveryBucketTests(unittest.TestCase):
    def test_it_is_in_none_of_the_three_sets(self):
        buckets = gate_sets()
        for name, members in buckets.items():
            self.assertNotIn(
                "target_hit", members,
                "target_hit joined the {} bucket — the unclassified-class defect is "
                "fixed; verify the bucket is the right one".format(name))

    def test_the_archive_contains_such_trades(self):
        kinds = {t["exit_type"] for t in trades()}
        self.assertIn("target_hit", kinds,
                      "no target_hit trades remain, so the fall-through is untestable")

    def test_the_three_buckets_do_not_cover_the_observed_exit_types(self):
        buckets = gate_sets()
        covered = set().union(*buckets.values())
        observed = {t["exit_type"] for t in trades()}
        self.assertTrue(
            observed - covered,
            "every observed exit type is now bucketed — the rubric's per-bucket lines "
            "would finally account for all trades")


class TheVerdictFlipsOnThePartitionTests(unittest.TestCase):
    """The consequence that makes this decision-relevant."""

    @classmethod
    def setUpClass(cls):
        cls.rows = trades()
        cls.n = len(cls.rows)

    def _frac(self, kinds):
        return sum(1 for t in self.rows if t["exit_type"] in kinds) / self.n

    def test_as_written_the_run_FAILS_the_eighty_percent_bar(self):
        self.assertLess(self._frac(gate_sets()["ACTUAL"]), 0.80)

    def test_counting_only_provably_actual_fills_fails_harder(self):
        self.assertLess(self._frac({"bracket_exit"}),
                        self._frac(gate_sets()["ACTUAL"]))

    def test_counting_the_whole_bracket_family_PASSES(self):
        self.assertGreaterEqual(
            self._frac({"bracket_exit", "stop_hit", "target_hit"}), 0.80,
            "the widest defensible partition no longer clears the bar — the verdict no "
            "longer flips, which weakens this finding; re-measure")

    def test_the_bar_sits_inside_the_ambiguity_band(self):
        low = self._frac({"bracket_exit"})
        high = self._frac({"bracket_exit", "stop_hit", "target_hit"})
        self.assertLess(low, 0.80)
        self.assertGreaterEqual(high, 0.80)
        self.assertIn(
            ">=80% of fills are confirmed", GATE.read_text(encoding="utf-8"),
            "the rubric's threshold changed — recompute whether it still lands inside "
            "the band")

    def test_the_gate_is_a_pass_fail_rubric_not_a_report(self):
        """Why the flip matters: this is a go/no-go, not a diagnostic."""
        text = GATE.read_text(encoding="utf-8")
        self.assertIn("CLEAN-RUN RUBRIC", text)
        self.assertIn("checks = [", text)


if __name__ == "__main__":
    unittest.main()
