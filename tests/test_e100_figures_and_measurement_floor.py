"""E100's counts reconcile, and three more non-measurements stop counting as figures.

Study: the addendum in `docs/research/IX00_ndx_recent_complete_panel.md`.

E100 topped the uncited queue with "5 figures, 0 reachable docs". Both halves were
artifacts of the measurement, not of a missing result.

**Its numbers were already documented.** Every count E100 states reads straight out of
`docs/research/data/ix00_ndx_*.json`, and this file binds each one to its artifact field.
The document holding them was published in an earlier cycle — it names `F111` and never
named `E100`, and doc-reachability is one hop. `F111` does not cite the document either
(`F182` does), so from E100 it sat two hops away.

**Raising the hop limit would cost far more than it fixes.** Measured over the whole web:
depth 1 leaves 51 nodes queued, depth 2 leaves 23, depth 3 leaves 2, unbounded leaves 1.
Depth 2 silently marks 28 nodes as documented by a document that need not be about them.
Reaching *a* document is not reaching one that holds *your* figures — that coupling only
survives one hop. So the traversal depth is pinned here, and the fix was to cite the node
from the document that documents it.

**And three of E100's five "figures" were not measurements.** `2026-07-24T15:04:46`
survived the year rule as `-07`, `8:00 p.m.` as `00`, and `Nasdaq-100` as `100`. Only the
counts `12` and `13` are real, so E100 never met the five-figure floor. This is the third
pass over the same class — F210 removed SEC form names, artifact ids, calendar years and
node ids; this adds ISO timestamps, clock times and index names carrying digits. The
recurring lesson: **a number inside a name or a timestamp is not a claim needing
evidence.** Guarded in both directions — real measurements must survive the filter, and
the filter must actually remove each of the three new classes.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import research_backlog as backlog  # noqa: E402

DATA = ROOT / "docs" / "research" / "data"
DOC = ROOT / "docs" / "research" / "IX00_ndx_recent_complete_panel.md"


def artifact(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class E100ReconcilesAgainstItsArtifactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b2024 = artifact("ix00_ndx_december2024_event_replication.json")
        cls.b2025 = artifact("ix00_ndx_december2025_event_replication.json")
        cls.b2022 = artifact("ix00_ndx_december2022_partial_diagnostic.json")
        cls.panel = artifact("ix00_ndx_recent_complete_panel.json")

    def test_the_2024_batch_is_complete_and_three_per_side(self):
        self.assertTrue(self.b2024["coverage"]["complete"])
        self.assertEqual(self.b2024["coverage"]["analyzed"], 6)
        self.assertEqual(self.b2024["coverage"]["official_events"], 6)
        for side in ("additions", "deletions"):
            self.assertEqual(
                self.b2024["group_summary_percent"][side]["n"], 3,
                "the Dec-2024 {} count moved off 3 — E100 says three per side".format(
                    side))

    def test_pooling_2024_and_2025_gives_nine_per_side(self):
        for side in ("additions", "deletions"):
            pooled = self.panel["security_weighted_summary_percent"][side]["n"]
            parts = (self.b2024["group_summary_percent"][side]["n"]
                     + self.b2025["group_summary_percent"][side]["n"])
            self.assertEqual(pooled, 9, "the panel's {} n moved off 9".format(side))
            self.assertEqual(
                pooled, parts,
                "the panel's {} n ({}) no longer equals the two batches summed ({}) — "
                "a batch was added, dropped or reweighted".format(side, pooled, parts))

    def test_the_2022_batch_is_thirteen_official_and_twelve_analyzed(self):
        cov = self.b2022["coverage"]
        self.assertEqual(cov["official_events"], 13)
        self.assertEqual(cov["analyzed"], 12)
        self.assertFalse(
            cov["complete"],
            "the 2022 batch is marked complete now — if SPLK became available, E100's "
            "survivorship gate no longer applies and the node should be superseded")

    def test_the_missing_security_is_recorded_not_silently_dropped(self):
        excluded = self.b2022["excluded_security"]
        self.assertEqual(excluded["event_symbol"], "SPLK")
        self.assertEqual(excluded["action"], "deletion")
        self.assertTrue(excluded["reason"].strip(),
                        "the exclusion lost its reason — an unexplained hole is the "
                        "thing E100's survivorship gate exists to prevent")

    def test_both_incomplete_years_are_barred_from_the_panel_with_reasons(self):
        excluded = self.panel["excluded_batches"]
        self.assertIn("SPLK", excluded["ndx-2022-12"])
        self.assertIn("revis", excluded["ndx-2023-12"].lower(),
                      "the 2023 exclusion no longer cites the post-Seagen revision")
        self.assertEqual(
            len(self.panel["included_batches"]), 2,
            "the panel no longer pools exactly two batches — E100's counts are stale")

    def test_the_deletion_group_name_still_flags_the_incomplete_set(self):
        """2022 calls it `observed_deletions` so it cannot be pooled by accident."""
        groups = self.b2022["partial_group_summary_percent"]
        self.assertIn("observed_deletions", groups)
        self.assertNotIn(
            "deletions", groups,
            "the incomplete 2022 set is now named like a complete one — the schema "
            "signal that prevents silent pooling is gone")


class TheDocumentNowNamesTheNodeItDocumentsTests(unittest.TestCase):
    def test_the_ix00_doc_names_e100(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn(
            "E100", text,
            "the IX-00 panel document stopped naming E100 — one-hop reachability will "
            "queue it as uncited again, which is what this cycle fixed")

    def test_it_also_still_names_f111(self):
        self.assertIn("F111", DOC.read_text(encoding="utf-8"))

    def test_the_doc_records_the_depth_sensitivity_that_justifies_one_hop(self):
        text = DOC.read_text(encoding="utf-8")
        for figure in ("51", "23"):
            self.assertIn(
                figure, text,
                "the depth-sensitivity table lost the {} figure — it is the reason the "
                "hop limit was not raised".format(figure))


class NonMeasurementsDoNotCountAsFiguresTests(unittest.TestCase):
    """Bidirectional: real numbers survive, the three new classes are removed."""

    REAL = ["+10.8709%", "8.65x", "48.9%", "-1.72%", "Sharpe 4.924", "0.000125",
            "12.87x", "-2.794 pp"]
    NOT_REAL = {
        "ISO timestamp": "retrieved_at_utc 2026-07-24T15:04:46+00:00",
        "clock time": "published at 8:00 p.m. and again at 20:00",
        "index name": "the Nasdaq-100 and the Russell 2000 and the S&P 500",
        "SEC form": "a 10-K and an 8-K",
        "artifact id": "FD-00 and CA-01",
        "calendar year": "in 2024 and 2025",
        "node id": "F111 and E100 and H50",
    }

    def test_real_measurements_survive_the_filter(self):
        for text in self.REAL:
            self.assertTrue(
                backlog._figures(text),
                "{!r} is no longer counted as a figure — the filter has started eating "
                "real measurements, which would hide genuinely uncited nodes".format(
                    text))

    def test_each_non_measurement_class_is_removed(self):
        for label, text in self.NOT_REAL.items():
            self.assertEqual(
                backlog._figures(text), set(),
                "{} ({!r}) is being counted as a figure again — nodes will be queued "
                "for evidence they were never asked to have".format(label, text))

    def test_e100s_own_body_falls_below_the_five_figure_floor(self):
        nodes = backlog.load_nodes()
        figs = backlog._figures(str(nodes["E100"]["body"]))
        self.assertEqual(
            figs, {"12", "13"},
            "E100's counted figures changed from the counts 12 and 13 to {} — either "
            "the node was edited or the filter moved".format(sorted(figs)))
        self.assertLess(len(figs), 5, "E100 is over the floor again")

    def test_the_iso_rule_runs_before_the_year_rule(self):
        """Ordering matters: the year rule alone leaves the rest of the stamp behind."""
        self.assertEqual(backlog._figures("2026-07-24T15:04:46+00:00"), set())
        self.assertEqual(backlog._figures("2026-07-24"), set())

    def test_a_ratio_written_with_a_colon_is_not_mistaken_for_a_clock(self):
        self.assertTrue(
            backlog._figures("a 1.67:1 reward-to-risk ratio"),
            "the clock-time rule is now eating ratios like 1.67:1 — tighten it")

    def test_the_queue_still_has_work_in_it(self):
        """Non-vacuity: a filter that empties the queue is over-suppression."""
        queued = backlog.source_uncited(backlog.load_nodes(), limit=999)
        self.assertGreater(
            len(queued), 10,
            "the uncited queue collapsed to {} — the figure filter or the reachability "
            "walk has become too permissive".format(len(queued)))


if __name__ == "__main__":
    unittest.main()
