"""F203's evidence reproduced, and its ambiguity resolved — the gate says FAIL — F263.

F203 was uncited: 10 figures, 0 reachable documents, 1 reliance dependent. Every figure
comes from the committed 65-trade live archive, so all of them regenerate offline.

**All three of F203's partitions reproduce exactly**, against `analyze_run.py`'s
">= 80% of fills are confirmed" bar:

    bracket_exit + stop_hit  (as written)       47/65 = 72.3%  FAIL
    bracket_exit only        (provably actual)  41/65 = 63.1%  FAIL
    bracket_exit + stop_hit + target_hit        53/65 = 81.5%  PASS

So does the duplication F203 flags: `ops/analyze_run.py`'s `ACTUAL` is byte-identical in
content to `ctx.CONFIRMED` — `{"bracket_exit", "stop_hit"}` — two implementations of one
fact, in separate files, wrong the same way, so neither can catch the other.

**But the ambiguity resolves, and F203 stopped one step short.** F203's conclusion is that
the verdict *flips* depending on a distinction the ledger cannot make. F245 has since made
that distinction, from the monitor event log rather than the trade ledger: 14 of the 65
trades carry a return that was never read from a real fill — 6 `target_hit` inferred from
the TP price (all six recorded at exactly +1.00%), 6 `stop_hit` from the software net after
IBKR brackets did not execute, and 2 `estimated_close` force-finalised when fill data never
arrived.

Applying that provenance gives a fourth partition, and it is the one the gate's own wording
demands, since it asks whether *fills* are *confirmed*:

    exits with an OBSERVED fill (bracket_exit + time_exit)   50/65 = 76.9%  FAIL

**Three of the four partitions fail, and the only PASS is the one that counts the twelve
exits F245 proved were never observed.** The 81.5% branch reaches PASS precisely by
counting `target_hit` and `stop_hit` — the two classes with no confirmed fill price. So the
honest reading is not "the verdict is ambiguous"; it is **FAIL, by 3.1 points**, and the
ambiguity was an artifact of a partition that never distinguished observed fills from
inferred ones.

That matters more than the flip did: this is the gate that authorises real money.

Guards are bidirectional. They fail if any partition's arithmetic moves, if the two
duplicate definitions stop agreeing (which would mean one was fixed — supersede), if the
provenance-correct partition crosses the bar, or if the PASS branch stops depending on the
synthetic classes.
"""
import collections
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ctx  # noqa: E402

TRADES = (ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"
          / "trades.jsonl")
BAR_PCT = 80.0

# F245's provenance split, derived from the monitor event log.
OBSERVED_FILL = {"bracket_exit", "time_exit"}
SYNTHETIC_FILL = {"target_hit", "stop_hit", "estimated_close"}


def _counts():
    rows = [json.loads(l) for l in TRADES.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    return collections.Counter(t.get("exit_type") for t in rows), len(rows)


def _pct(types):
    c, n = _counts()
    return 100.0 * sum(c[t] for t in types) / n


class F203sFiguresReproduceTests(unittest.TestCase):

    def test_the_ledger_is_the_expected_shape(self):
        c, n = _counts()
        self.assertEqual(n, 65)
        self.assertEqual(c["bracket_exit"], 41)
        self.assertEqual(c["stop_hit"], 6)
        self.assertEqual(c["target_hit"], 6)
        self.assertEqual(c["time_exit"], 9)

    def test_all_three_recorded_partitions(self):
        for types, expected, verdict in (
            (("bracket_exit", "stop_hit"), 72.3, "FAIL"),
            (("bracket_exit",), 63.1, "FAIL"),
            (("bracket_exit", "stop_hit", "target_hit"), 81.5, "PASS"),
        ):
            with self.subTest(types=types):
                got = _pct(types)
                self.assertAlmostEqual(got, expected, delta=0.1)
                self.assertEqual("PASS" if got >= BAR_PCT else "FAIL", verdict)

    def test_the_bar_sits_inside_the_band(self):
        """F203's core observation: the 80% bar is spanned by the ambiguity."""
        lo, hi = _pct(("bracket_exit",)), _pct(
            ("bracket_exit", "stop_hit", "target_hit"))
        self.assertLess(lo, BAR_PCT)
        self.assertGreater(hi, BAR_PCT)


class TheDefinitionIsDuplicatedTests(unittest.TestCase):

    def test_analyze_run_and_ctx_declare_the_same_set(self):
        src = (ROOT / "ops" / "analyze_run.py").read_text(encoding="utf-8")
        m = re.search(r"ACTUAL\s*=\s*\{([^}]*)\}", src)
        self.assertIsNotNone(m, "analyze_run.ACTUAL is gone")
        actual = {x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()}
        self.assertEqual(
            actual, set(ctx.CONFIRMED),
            "the two copies have diverged — if one was corrected, supersede F263 rather "
            "than editing this expectation")

    def test_both_copies_carry_the_same_defect(self):
        """Why neither can catch the other: both include an exit the software net can
        produce without a fill, and both exclude one the broker fills for real."""
        self.assertIn("stop_hit", ctx.CONFIRMED)
        self.assertNotIn("target_hit", ctx.CONFIRMED)


class TheAmbiguityResolvesToFailTests(unittest.TestCase):
    """F245's provenance makes the distinction F203 said the ledger could not."""

    def test_the_provenance_correct_partition_fails(self):
        got = _pct(OBSERVED_FILL)
        self.assertAlmostEqual(got, 76.9, delta=0.2)
        self.assertLess(
            got, BAR_PCT,
            "the provenance-correct share crossed the 80% bar — the gate would now "
            "PASS on observed fills alone; supersede F263")

    def test_only_the_synthetic_partition_passes(self):
        """The load-bearing claim: the single PASS depends on counting exits with no
        confirmed fill."""
        passing = [types for types in (
            ("bracket_exit", "stop_hit"),
            ("bracket_exit",),
            ("bracket_exit", "stop_hit", "target_hit"),
            tuple(sorted(OBSERVED_FILL)),
        ) if _pct(types) >= BAR_PCT]
        self.assertEqual(
            [tuple(sorted(p)) for p in passing],
            [("bracket_exit", "stop_hit", "target_hit")],
            "the set of passing partitions changed — F263's conclusion that the only "
            "PASS is the synthetic one needs re-deriving")

    def test_removing_the_synthetic_classes_is_what_causes_the_fail(self):
        """Non-vacuity: the FAIL must be attributable to provenance, not to a bar that
        nothing could clear."""
        with_synth = _pct(("bracket_exit", "stop_hit", "target_hit"))
        without = _pct(OBSERVED_FILL)
        self.assertGreater(with_synth, BAR_PCT)
        self.assertLess(without, BAR_PCT)
        self.assertGreater(
            with_synth - without, 3.0,
            "the two partitions have converged, so provenance no longer decides the "
            "verdict")

    def test_the_synthetic_classes_are_a_meaningful_share(self):
        c, n = _counts()
        synthetic = sum(c[t] for t in SYNTHETIC_FILL)
        self.assertEqual(synthetic, 14)
        self.assertGreater(100.0 * synthetic / n, 20.0)


if __name__ == "__main__":
    unittest.main()
