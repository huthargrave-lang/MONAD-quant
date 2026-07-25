"""Tests for NUM-00, the numeric provenance audit.

Two of this lab's three measurement bugs were caught only by sampling a node and
checking by hand; both are pinned here so they cannot return:

1. **Unicode minus.** Node bodies use ASCII hyphen, docs use U+2212 (1164 times).
   Without normalisation, real figures are reported missing — the first run
   overstated absent-everywhere by 1.4-1.9x (corpus-dependent; see the lab docstring).
2. **Substring matching.** Testing `fig in text` matches numerals embedded in URLs
   and SEC accession numbers (F17's "41" matched inside `d411753d8k.htm`). Docs must
   be tokenised with the same extractor as node bodies.

The third issue is not a bug but a limit, and is asserted as a documented caveat:
common values collide across 87 documents, so the per-figure `unlinked` class is
weak. F17 is the standing calibration case — F139 established by hand that its
figures are genuinely unlocated, yet they classify `unlinked` by collision alone.
"""
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "numeric_provenance_lab", ROOT / "tools" / "numeric_provenance_lab.py"
)
LAB = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = LAB
_SPEC.loader.exec_module(LAB)


class NormalisationTests(unittest.TestCase):
    def test_unicode_minus_is_normalised(self):
        """Regression: the corpus mixes U+2212 with ASCII hyphen."""
        self.assertIn("-5.17", LAB.normalise_numerals("−5.17"))
        self.assertIn("-5.17", LAB.normalise_numerals("–5.17"))
        self.assertEqual(LAB.figures("−5.17"), LAB.figures("-5.17"))

    def test_thousands_separators_are_stripped(self):
        self.assertEqual(LAB.figures("3,429 bars"), LAB.figures("3429 bars"))

    def test_single_digits_are_ignored_as_noise(self):
        self.assertEqual(LAB.figures("we ran 5 trials"), set())
        self.assertIn("12", LAB.figures("we ran 12 trials"))

    def test_numerals_inside_identifiers_are_not_extracted(self):
        """F17/E112 must not decompose into digits, and a numeral glued to letters
        (an accession or URL fragment) is not a figure."""
        self.assertEqual(LAB.figures("see F17 and E112"), set())
        self.assertEqual(LAB.figures("d411753d8k.htm"), set())

    def test_negative_values_survive_extraction(self):
        self.assertIn("-8.96", LAB.figures("max -8.96pp"))


class TokenisedMatchingTests(unittest.TestCase):
    def test_docs_are_tokenised_not_substring_matched(self):
        """Regression: `fig in text` matched '41' inside an SEC URL. load_docs must
        return token SETS so only standalone numerals count."""
        docs = LAB.load_docs()
        self.assertTrue(docs, "no research docs found")
        sample = next(iter(docs.values()))
        self.assertIsInstance(sample, set)
        # a URL fragment must not contribute its digits as figures
        self.assertEqual(
            LAB.figures("https://www.sec.gov/Archives/edgar/data/1418091/d411753d8k.htm"),
            {"1418091"},
        )


class ClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes = LAB.load_nodes()
        cls.docs = LAB.load_docs()

    def test_every_figure_lands_in_exactly_one_class(self):
        for node_id in list(self.nodes)[:60]:
            row = LAB.classify_node(node_id, self.nodes, self.docs)
            total = len(row["linked"]) + len(row["unlinked"]) + len(row["absent"])
            self.assertEqual(total, row["n_figures"], node_id)
            self.assertEqual(
                set(row["linked"]) & set(row["unlinked"]), set(), node_id)
            self.assertEqual(
                set(row["unlinked"]) & set(row["absent"]), set(), node_id)

    def test_f17_is_the_standing_calibration_case(self):
        """F139 established by hand that F17's figures are unlocated AS CLAIMS, and
        that F17 links to no Experiment. The structural signal must reflect that even
        though token-collision puts the figures in `unlinked`."""
        row = LAB.classify_node("F17", self.nodes, self.docs)
        self.assertEqual(row["reachable_docs"], [],
                         "F17 unexpectedly reaches a doc — F139 may be stale, re-verify")
        self.assertGreater(row["n_figures"], 0)

    def test_structural_metric_is_reported_and_uncontaminated(self):
        rep = LAB.census(self.nodes, self.docs)
        self.assertIn("nodes_with_figures_but_no_reachable_doc", rep)
        self.assertGreater(rep["nodes_with_figures_but_no_reachable_doc"], 0)
        self.assertLessEqual(
            rep["nodes_with_figures_but_no_reachable_doc"], rep["nodes_with_figures"])

    def test_caveats_warn_about_collision_and_normalisation(self):
        rep = LAB.census(self.nodes, self.docs)
        blob = " ".join(str(c) for c in rep["caveats"]) + str(rep["interpretation"])
        for needle in ("normalis", "COLLISION", "F17"):
            self.assertIn(needle, blob)

    def test_census_totals_are_consistent(self):
        rep = LAB.census(self.nodes, self.docs)
        self.assertEqual(
            rep["figures_linked"] + rep["figures_unlinked"] + rep["figures_absent"],
            rep["figures_total"])

    def test_report_refuses_to_write_inside_the_repo(self):
        with self.assertRaisesRegex(ValueError, "refusing to write"):
            LAB._write_json_atomic(ROOT / "nope.json", {"a": 1})


class LimitsTests(unittest.TestCase):
    """The docstring's three self-criticisms are claims about the corpus. Pin them.

    Adversarial re-verification found the lab's first write-up overstated its own
    result. These tests exist so the *corrections* are as executable as the result:
    if the corpus drifts far enough that a stated limit stops holding, the test
    fails and the docstring must be re-measured rather than left stale.
    """

    @classmethod
    def setUpClass(cls):
        cls.nodes = LAB.load_nodes()
        cls.docs = LAB.load_docs()
        cls.rep = LAB.census(cls.nodes, cls.docs)
        cls.figs = [
            f
            for r in cls.rep["per_node"]
            for f in list(r["linked"]) + list(r["unlinked"]) + list(r["absent"])
        ]

    def test_normalisation_effect_is_large_and_the_docstring_says_so(self):
        """Regression on the correction itself: absent-everywhere roughly halves.

        Measured by monkeypatching normalisation to the identity — the same method
        the docstring reports. The MULTIPLE is corpus-dependent (1.87x at 2388
        figures, 1.38x at 2834); only its materiality is asserted.
        """
        original = LAB.normalise_numerals
        try:
            LAB.normalise_numerals = lambda text: text
            raw = LAB.census(LAB.load_nodes(), LAB.load_docs())
        finally:
            LAB.normalise_numerals = original
        ratio = raw["pct_absent"] / self.rep["pct_absent"]
        # The ratio is CORPUS-DEPENDENT — it tracks how much of the corpus was
        # written with U+2212 vs ASCII hyphen, so a batch of same-author nodes
        # dilutes it. Measured 1.87x at 2388 figures and 1.38x at 2834. Assert
        # materiality and direction, not a band; a band made this test fail for
        # corpus growth rather than for the defect it guards.
        self.assertGreater(
            ratio, 1.15,
            "normalisation stopped mattering — re-measure and update the docstring "
            "(do NOT just lower this threshold)")
        self.assertLess(ratio, 3.0, "normalisation effect grew — docstring is stale")
        self.assertIn("corpus-dependent", LAB.__doc__,
                      "the docstring must warn that this multiple is not a constant")

    def test_most_figures_are_low_information_tokens(self):
        """62.9% are 2-digit integers or years. The lab must not be sold as if every
        matched numeral were a headline statistic."""
        def digits(f):
            return f.lstrip("-")

        two = sum(1 for f in self.figs if digits(f).isdigit() and len(digits(f)) == 2)
        years = sum(
            1 for f in self.figs
            if f.isdigit() and len(f) == 4 and 1900 <= int(f) <= 2100
        )
        share = (two + years) / len(self.figs)
        self.assertGreater(share, 0.5, "figure population changed character — re-measure")

    def test_a_wrong_value_still_lands_present_about_half_the_time(self):
        """The collision null. Perturb real figures by one tick and check how often
        the (never-claimed) result is still 'in some doc'. High rate => a single
        figure's class is near-meaningless; only aggregates carry signal."""
        import random

        doc_union = set()
        for tokens in self.docs.values():
            doc_union |= tokens
        rng = random.Random(20260725)
        hits = trials = 0
        for _ in range(4000):
            f = rng.choice(self.figs)
            try:
                value = float(f)
            except ValueError:
                continue
            if "." in f:
                cand = "%.*f" % (len(f.split(".")[1]), value + rng.choice([0.01, -0.01, 0.1, -0.1]))
            else:
                cand = str(int(value) + rng.choice([1, -1, 2, -2]))
            trials += 1
            hits += cand in doc_union
        self.assertGreater(hits / trials, 0.35,
                           "collision null collapsed — the docstring caveat is stale")

    def test_unlinked_is_dominated_by_nodes_that_cite_nothing(self):
        """80.8% of `unlinked` sits in zero-doc nodes: a citation gap, not a
        traversal gap. Mislabelling this was the write-up's third error."""
        zero_doc = sum(
            len(r["unlinked"]) for r in self.rep["per_node"] if not r["reachable_docs"])
        share = zero_doc / self.rep["figures_unlinked"]
        self.assertGreater(share, 0.6,
                           "`unlinked` is no longer dominated by uncited nodes — relabel")


if __name__ == "__main__":
    unittest.main()
