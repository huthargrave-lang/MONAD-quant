"""Tests for F25-TIME — Form 25 acceptance timing.

Two things get pinned here, in order of importance.

**The exact test must be exact.** The lab reports p-values on strata with cells below
5, where an asymptotic test is invalid, so the hypergeometric tail is load-bearing. An
earlier version computed the support's lower bound as `max(0, col1 - b)` instead of
`max(0, row1 + col1 - n)`. In small strata that bound can exceed the OBSERVED cell,
emptying the summation and returning **p = 0 exactly** — which is impossible, since
`P(X >= a) >= P(X = a) > 0`. The impossibility is what exposed it. Every p-value is
therefore cross-checked here against an independent brute-force enumeration over all
tables with the same margins, and a test asserts no p-value is ever 0 or > 1.

**The finding must survive stratification.** The headline (Nasdaq files post-close, the
NYSE family files intraday) would be uninteresting if it were a security-mix artifact,
so the warrant stratum — where composition is held fixed — is asserted separately.
"""
import importlib.util
import sys
import unittest
from math import comb
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "form25_timing_lab", ROOT / "tools" / "form25_timing_lab.py")
LAB = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = LAB
_SPEC.loader.exec_module(LAB)


def brute_force_tail(a, b, c, d):
    """P(X >= a) by enumerating every table with these margins. Independent of LAB."""
    n, row1, col1 = a + b + c + d, a + b, a + c
    total = 0.0
    for x in range(0, min(row1, col1) + 1):
        y, z = row1 - x, col1 - x
        w = n - row1 - z
        if y < 0 or z < 0 or w < 0:
            continue
        pr = comb(row1, x) * comb(n - row1, z) / comb(n, col1)
        if x >= a:
            total += pr
    return total


class FisherExactTests(unittest.TestCase):
    TABLES = [
        (2, 0, 1, 8),      # debt_or_note — the stratum that returned p=0
        (1, 0, 1, 15),     # other_or_unknown — likewise
        (28, 18, 3, 51),   # pooled
        (22, 4, 1, 13),    # warrant stratum
        (3, 14, 0, 14),    # common equity
        (0, 5, 5, 0),      # degenerate: observed cell empty
        (5, 0, 0, 5),      # degenerate: perfect separation
    ]

    def test_matches_an_independent_enumeration(self):
        for table in self.TABLES:
            self.assertAlmostEqual(
                LAB.fisher_one_sided(*table), brute_force_tail(*table), places=12,
                msg="disagrees with brute force on {}".format(table))

    def test_no_p_value_is_ever_zero(self):
        """Regression on the support bug. P(X >= a) >= P(X = a) > 0 always."""
        for table in self.TABLES:
            p = LAB.fisher_one_sided(*table)
            self.assertGreater(
                p, 0.0,
                "p = 0 for {} — the summation support excluded the observed cell, "
                "which is the bug this test exists for".format(table))
            self.assertLessEqual(p, 1.0 + 1e-12)

    def test_an_all_or_nothing_table_is_still_a_probability(self):
        """Perfect separation should give a small p, not a degenerate one."""
        p = LAB.fisher_one_sided(5, 0, 0, 5)
        self.assertGreater(p, 0.0)
        self.assertLess(p, 0.05)

    def test_empty_margins_do_not_divide_by_zero(self):
        self.assertEqual(LAB.fisher_one_sided(0, 0, 0, 0), 1.0)
        self.assertEqual(LAB.fisher_one_sided(0, 0, 5, 5), 1.0)


class TimingFindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = LAB.load()["sample"]

    def test_the_pooled_effect_is_overwhelming(self):
        res = LAB.timing_test(self.sample)
        self.assertLess(res["p_exact"], 1e-6)
        self.assertGreater(res["nasdaq_post_share"], 0.5)
        self.assertLess(res["rest_post_share"], 0.15)

    def test_it_survives_the_warrant_stratum_where_composition_is_fixed(self):
        """The claim that matters: not a security-mix artifact."""
        res = LAB.timing_test(self.sample, "warrant_right_or_unit")
        self.assertLess(
            res["p_exact"], 0.001,
            "the effect no longer holds within a single security family — it may be "
            "a composition artifact after all; re-verify before citing")
        self.assertGreater(res["nasdaq_post_share"], 0.7)
        self.assertLess(res["rest_post_share"], 0.2)

    def test_nasdaq_and_the_rest_have_different_median_hours(self):
        hours = LAB.acceptance_hours(self.sample)
        med = {k: sorted(v)[len(v) // 2] for k, v in hours.items()}
        self.assertGreater(med["Nasdaq"], 15.5, "Nasdaq median is no longer post-close")
        self.assertLess(med["non-Nasdaq"], 14.0)
        self.assertGreater(med["Nasdaq"] - med["non-Nasdaq"], 2.0)


class SamplingFrameTests(unittest.TestCase):
    """These are the reason the descriptive claims can be quoted at all."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = LAB.load()

    def test_issuer_diversity_is_not_significantly_high(self):
        res = LAB.issuer_diversity_null(self.fixture, trials=3000)
        self.assertGreater(
            res["p_ge_observed"], 0.01,
            "the sample now looks significantly more issuer-diverse than uniform "
            "sampling would give — the SHA-256 rank draw may not be uniform")

    def test_exchange_mix_tracks_the_census(self):
        for row in LAB.exchange_representativeness(self.fixture):
            if row["census_pct"] < 5.0:
                continue  # small venues: sampling noise dominates at n=100
            self.assertLess(
                abs(row["census_pct"] - row["sample_pct"]), 8.0,
                "{} is over/under-sampled by more than 8pp".format(row["exchange"]))

    def test_design_weights_are_immaterial(self):
        """Equal allocation on unequal strata is NOT self-weighting. It only fails to
        matter because the attributes do not vary much by quarter — assert that,
        because if it changed, every quoted share would need reweighting."""
        rows = LAB.design_weight_effect(self.fixture)
        worst = max(abs(r["delta_pp"]) for r in rows)
        self.assertLess(
            worst, 2.0,
            "design weights now shift a reported share by {:.2f}pp — the fixture's "
            "raw percentages are no longer census estimates and must be "
            "reweighted".format(worst))

    def test_the_design_really_is_equal_allocation_on_unequal_strata(self):
        """Guard the premise: if the fixture is ever re-drawn proportionally, the
        caveat above becomes unnecessary and the docstring should say so."""
        import collections
        census = self.fixture["census_manifest"]
        cq = collections.Counter(r["quarter"] for r in census)
        sq = collections.Counter(r["quarter"] for r in self.fixture["sample"])
        self.assertEqual(set(sq.values()), {LAB.PER_QUARTER},
                         "sample is no longer 25-per-quarter")
        self.assertGreater(max(cq.values()) / min(cq.values()), 1.1,
                           "census quarters are now near-equal — strata are balanced")


if __name__ == "__main__":
    unittest.main()
