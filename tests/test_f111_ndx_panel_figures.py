"""F111's twelve figures, bound to the artifacts they came from.

F111 was flagged uncited — twelve figures, zero reachable documents. The numbers turned
out to be fully recoverable: every one is present in a committed artifact under
`docs/research/data/`, and the arithmetic relating them reconciles exactly. What was
missing was a citation path, not the evidence. `docs/research/IX00_ndx_recent_complete_
panel.md` now records it.

This file is the guard, and it asserts a kind of claim the repo had no test for: **prose
figures bound to committed data**. A node states "+2.074 pp add-minus-delete"; an artifact
holds `2.073983`. Nothing previously connected the two, so either could drift silently —
a node could be edited to a rounder number, or an artifact regenerated with different
values, and no test would notice.

Three things are checked.

**Every figure F111 states is in an artifact**, at the precision the prose uses.

**Pooling is a plain n-weighted mean.** For every metric and both sides,
`(m24*n24 + m25*n25) / (n24 + n25)` equals the panel value. Nothing is reweighted,
winsorised or trimmed in the pooling step — which is worth pinning, because a pooled
figure is exactly where such a step would hide.

**`addition_minus_deletion` is the difference of the two pooled sides**, not a separately
estimated contrast.

One schema detail is asserted deliberately: the excluded 2022 batch names its deletion
group `observed_deletions`, not `deletions`. That difference is a signal, not an
inconsistency — it makes the incomplete set impossible to pool by accident, and F111's
-2.794 figure can only be reproduced by reading it knowingly.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "research" / "data"
DOC = ROOT / "docs" / "research" / "IX00_ndx_recent_complete_panel.md"
WEB = ROOT / "RESEARCH_WEB.md"

TOL = 1e-5


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def f111_body():
    text = WEB.read_text(encoding="utf-8")
    start = text.index("### F111 ")
    return text[start:text.index("\n### ", start + 5)]


class EveryFigureInTheNodeComesFromAnArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = load("ix00_ndx_recent_complete_panel.json")[
            "security_weighted_summary_percent"]
        cls.d22 = load("ix00_ndx_december2022_partial_diagnostic.json")[
            "partial_group_summary_percent"]
        cls.body = f111_body()

    def test_the_pooled_contrasts(self):
        amd = self.panel["addition_minus_deletion"]
        for stated, key in (
                ("+2.074", "announcement_close_to_first_open_relative"),
                ("-0.375", "first_open_to_implementation_close_relative"),
                ("2.226", "post_implementation_1_session_relative"),
                ("3.167", "post_implementation_5_sessions_relative")):
            self.assertAlmostEqual(
                abs(float(stated)), abs(amd[key]), places=3,
                msg="F111 states {} for {} but the artifact holds {} — one of the two "
                    "drifted".format(stated, key, amd[key]))

    def test_the_volume_ratios(self):
        self.assertAlmostEqual(
            self.panel["additions"]["implementation_volume_ratio_to_prior_20d_median"],
            12.87, places=2)
        self.assertAlmostEqual(
            self.panel["deletions"]["implementation_volume_ratio_to_prior_20d_median"],
            7.26, places=2)

    def test_the_group_sizes(self):
        self.assertEqual(self.panel["additions"]["n"], 9)
        self.assertEqual(self.panel["deletions"]["n"], 9)
        self.assertIn("nine additions versus nine deletions", self.body)

    def test_the_excluded_2022_five_session_figure(self):
        add = self.d22["additions"]["post_implementation_5_sessions_relative"]
        dele = self.d22["observed_deletions"]["post_implementation_5_sessions_relative"]
        self.assertAlmostEqual(
            add - dele, -2.794, places=3,
            msg="the 2022 diagnostic's five-session contrast no longer equals F111's "
                "-2.794 — re-read which groups it combines")
        self.assertIn("-2.794", self.body.replace("−", "-"))

    def test_no_figure_in_the_node_is_unaccounted_for(self):
        """Catches a number being ADDED to the prose without an artifact behind it."""
        numbers = {abs(float(x)) for x in
                   re.findall(r"[-−]?\d+\.\d+", f111_body().replace("−", "-"))}
        pool = set()
        for group in (self.panel["additions"], self.panel["deletions"],
                      self.panel["addition_minus_deletion"], self.d22["additions"],
                      self.d22["observed_deletions"]):
            for v in group.values():
                pool.add(abs(round(float(v), 3)))
                pool.add(abs(round(float(v), 2)))
        add = self.d22["additions"]["post_implementation_5_sessions_relative"]
        dele = self.d22["observed_deletions"]["post_implementation_5_sessions_relative"]
        pool.add(abs(round(add - dele, 3)))
        unaccounted = {n for n in numbers if n not in pool}
        self.assertEqual(
            unaccounted, set(),
            "F111 states figure(s) with no artifact value behind them: {}. Either the "
            "prose gained a number that was never measured, or an artifact changed."
            .format(sorted(unaccounted)))


class PoolingIsAPlainWeightedMeanTests(unittest.TestCase):
    """Where a hidden reweighting would live."""

    @classmethod
    def setUpClass(cls):
        cls.panel = load("ix00_ndx_recent_complete_panel.json")[
            "security_weighted_summary_percent"]
        cls.b24 = load("ix00_ndx_december2024_event_replication.json")["group_summary_percent"]
        cls.b25 = load("ix00_ndx_december2025_event_replication.json")["group_summary_percent"]

    def test_the_group_sizes_add_up(self):
        for side in ("additions", "deletions"):
            self.assertEqual(self.b24[side]["n"] + self.b25[side]["n"],
                             self.panel[side]["n"])

    def test_every_metric_is_the_n_weighted_mean_of_the_two_batches(self):
        for side in ("additions", "deletions"):
            n24, n25 = self.b24[side]["n"], self.b25[side]["n"]
            for key, v24 in self.b24[side].items():
                if key == "n":
                    continue
                calc = (v24 * n24 + self.b25[side][key] * n25) / (n24 + n25)
                self.assertAlmostEqual(
                    calc, self.panel[side][key], delta=TOL,
                    msg="{}/{}: the pooled value ({}) is not the n-weighted mean of "
                        "the batches ({}) — a reweighting step may have been "
                        "introduced".format(side, key, self.panel[side][key], calc))

    def test_the_contrast_is_the_difference_of_the_pooled_sides(self):
        for key, stated in self.panel["addition_minus_deletion"].items():
            calc = self.panel["additions"][key] - self.panel["deletions"][key]
            self.assertAlmostEqual(
                calc, stated, delta=TOL,
                msg="{}: addition_minus_deletion ({}) is not additions minus deletions "
                    "({}) — it may now be separately estimated".format(key, stated, calc))

    def test_the_volume_ratio_has_no_contrast_entry(self):
        """A difference of two ratios is not a meaningful quantity; its absence is a
        design decision worth keeping."""
        self.assertNotIn("implementation_volume_ratio_to_prior_20d_median",
                         self.panel["addition_minus_deletion"])


class TheExcludedBatchIsSchema_MarkedTests(unittest.TestCase):
    def test_the_2022_deletion_group_is_named_observed_deletions(self):
        groups = load("ix00_ndx_december2022_partial_diagnostic.json")[
            "partial_group_summary_percent"]
        self.assertIn("observed_deletions", groups)
        self.assertNotIn(
            "deletions", groups,
            "the incomplete 2022 batch now uses the same key as the complete batches, "
            "so it can be pooled by accident — that key difference was the guard")

    def test_the_panel_records_why_each_batch_is_excluded(self):
        excluded = load("ix00_ndx_recent_complete_panel.json")["excluded_batches"]
        self.assertEqual(set(excluded), {"ndx-2022-12", "ndx-2023-12"})
        for batch, reason in excluded.items():
            self.assertGreater(len(reason), 30, "{} lost its exclusion reason".format(batch))


class TheNodeNowHasADocumentTests(unittest.TestCase):
    def test_the_study_document_exists_and_names_the_artifacts(self):
        self.assertTrue(DOC.exists())
        text = DOC.read_text(encoding="utf-8")
        for artifact in ("ix00_ndx_december2024_event_replication.json",
                         "ix00_ndx_december2025_event_replication.json",
                         "ix00_ndx_december2022_partial_diagnostic.json"):
            self.assertIn(artifact, text)

    def test_the_document_states_the_limits_rather_than_the_headline(self):
        text = DOC.read_text(encoding="utf-8")
        for phrase in ("no inference", "hypothesis generator", "prior winners",
                       "raw_data_committed"):
            self.assertIn(phrase, text,
                          "the study doc dropped {!r} — it is an exploratory panel and "
                          "the write-up must keep saying so".format(phrase))


if __name__ == "__main__":
    unittest.main()
