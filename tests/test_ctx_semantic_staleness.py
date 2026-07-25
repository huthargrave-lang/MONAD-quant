"""H11/DP-4: a semantic-staleness detector, and the check that it finds real things.

The epistemic layer detects **declared** staleness — a node says `status: superseded`
and the lint follows. It is blind to a node that never declared anything while later work
overtook it. H11 asked for a read-only `ctx stale` heuristic. Built as
`ctx.semantic_staleness()`, with two signals of deliberately different kinds.

**`edge_status_conflict` — hard, not ranked.** A node that is the TARGET of a
`supersedes` edge while still declaring `current`. The web contradicts itself about one
node. Exactly one exists: **F10** ("all results are MORNING-ONLY"), which F12 supersedes
while F10 declares current and carries no `by:`. It is genuinely stale twice over — F12
replaced its mechanism, and F180 found the underlying vendor quirk did not fire in the
most recent committed fetch.

**`decay` — soft, ranked.** A current Finding/Decision that cites no evidence of its own,
is refined/contradicted/superseded by a strictly later node, and never mentions that node.
Ranked by `unacknowledged_count * max_id_gap`.

**The scoping is the design.** Being refined by something later is not staleness — 187
nodes are, which is healthy accumulation. Requiring *both* "cites no evidence of its own"
*and* "never mentions the later node" cuts 194 current F/D nodes to 12. A detector that
flags 187 items is a detector nobody reads.

**The validation that matters.** The heuristic was written before comparing it to
anything. Its top-ranked entries are D4, F12, F17 and F47 — which are, independently, four
of the nodes this session read and found stale by hand (F181, F180, F179, F172). A
mechanical rank over graph structure reproduced several sessions' worth of manual
judgement. `test_the_ranking_reproduces_the_manual_findings` pins that agreement: if the
ranking stops surfacing nodes that were independently confirmed stale, the heuristic has
lost the property that justified shipping it.

It remains a **reading queue, not a verdict**. Nothing here edits a node or changes a
status.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402

# Nodes this session independently read and amended as stale, before the heuristic
# existed. Each is paired with the Finding that recorded it.
MANUALLY_CONFIRMED = {"D4": "F181", "F12": "F180", "F17": "F179", "F47": "F172"}


class TheDetectorRunsAndIsScopedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conflicts, cls.decay = ctx.semantic_staleness()
        cls.nodes, _ = ctx._parse_web()

    def test_it_returns_a_short_readable_list(self):
        self.assertGreater(len(self.decay), 0, "the decay list is empty — either the "
                                               "web is clean or the heuristic broke")
        self.assertLess(
            len(self.decay), 30,
            "the decay list grew to {} — a queue that long stops being read; tighten "
            "the predicate rather than raising the display limit".format(len(self.decay)))

    def test_bare_refinement_is_NOT_treated_as_staleness(self):
        """The scoping decision, asserted. Most of the web is refined by something
        later; if that counted, the detector would flag an order of magnitude more."""
        inbound = ctx._inbound_edges(self.nodes)
        refined = sum(1 for nid, n in self.nodes.items()
                      if not ctx._is_superseded(n)
                      and any(t == "refines" for _s, t in inbound[nid]))
        self.assertGreater(refined, 100, "far fewer nodes are refined than expected")
        self.assertLess(
            len(self.decay), refined / 5,
            "the decay list is approaching the count of all refined nodes ({}), which "
            "means the extra predicates stopped discriminating".format(refined))

    def test_flagged_nodes_are_all_CURRENT(self):
        """A declared-superseded node is the lint's job, not this one."""
        for row in self.decay:
            self.assertFalse(
                ctx._is_superseded(self.nodes[row["node"]]),
                "{} is already declared superseded and should not be in the semantic "
                "list".format(row["node"]))

    def test_flagged_nodes_cite_no_evidence_of_their_own(self):
        for row in self.decay:
            self.assertFalse(
                ctx._cites_evidence(self.nodes[row["node"]]),
                "{} cites its own evidence yet was flagged — the predicate loosened"
                .format(row["node"]))

    def test_the_overtaking_node_is_always_LATER_and_unmentioned(self):
        for row in self.decay:
            body = self.nodes[row["node"]].get("body", "")
            for src in row["by"]:
                self.assertGreater(ctx._node_number(src), ctx._node_number(row["node"]))
                self.assertNotIn(
                    src, body,
                    "{} mentions {} in its body — an acknowledged refinement is not "
                    "unacknowledged overtaking".format(row["node"], src))

    def test_the_ranking_is_sorted(self):
        scores = [r["score"] for r in self.decay]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TheEdgeStatusConflictIsRealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conflicts, _ = ctx.semantic_staleness()
        cls.nodes, _ = ctx._parse_web()

    def test_f10_is_flagged(self):
        self.assertIn(
            ("F10", "F12"), self.conflicts,
            "F10/F12 is no longer flagged. If F10 was given a status comment, good — "
            "remove it from this test. If the F12 edge was retyped, check that was "
            "deliberate: F12 does supersede F10's caveat.")

    def test_f10_really_does_declare_current_with_no_superseder(self):
        meta = ctx._node_meta(self.nodes["F10"])
        self.assertEqual(meta["status"], "current")
        self.assertIsNone(meta["by"])

    def test_the_conflict_signal_is_narrow(self):
        """A hard signal must not become a second decay list."""
        self.assertLessEqual(
            len(self.conflicts), 3,
            "edge/status conflicts jumped to {} — this signal is supposed to be rare "
            "and individually actionable".format(len(self.conflicts)))


class TheHeuristicReproducesManualJudgementTests(unittest.TestCase):
    """The validation that justified shipping it."""

    @classmethod
    def setUpClass(cls):
        _c, cls.decay = ctx.semantic_staleness()
        cls.ranked = [r["node"] for r in cls.decay]

    def test_the_ranking_reproduces_the_manual_findings(self):
        missing = [n for n in MANUALLY_CONFIRMED if n not in self.ranked]
        self.assertEqual(
            missing, [],
            "these nodes were independently read and found stale ({}) but the "
            "heuristic no longer surfaces them: {}. That agreement is the only "
            "external evidence the ranking tracks anything real.".format(
                {k: v for k, v in MANUALLY_CONFIRMED.items() if k in missing}, missing))

    def test_they_cluster_near_the_TOP_of_the_ranking(self):
        """Recall alone is cheap when the list is short; the ordering is the claim."""
        positions = [self.ranked.index(n) for n in MANUALLY_CONFIRMED]
        self.assertLessEqual(
            max(positions), 5,
            "a manually-confirmed stale node fell to rank {} — the score is no longer "
            "ordering by how overtaken a node is".format(max(positions) + 1))

    def test_each_manual_finding_still_exists_to_anchor_the_claim(self):
        nodes, _ = ctx._parse_web()
        for stale_node, finding in MANUALLY_CONFIRMED.items():
            self.assertIn(finding, nodes,
                          "{} recorded {}'s staleness and is gone".format(
                              finding, stale_node))


class TheCommandIsReadOnlyTests(unittest.TestCase):
    def test_running_it_does_not_touch_the_web(self):
        import io
        import types
        from contextlib import redirect_stdout

        web = ROOT / "RESEARCH_WEB.md"
        before = web.read_bytes()
        buf = io.StringIO()
        with redirect_stdout(buf):
            ctx.cmd_stale(types.SimpleNamespace(limit=15))
        self.assertEqual(web.read_bytes(), before, "ctx stale wrote to the web")
        out = buf.getvalue()
        self.assertIn("DECAY LIST", out)
        self.assertIn("F10", out)

    def test_the_limit_is_honoured(self):
        import io
        import types
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            ctx.cmd_stale(types.SimpleNamespace(limit=2))
        self.assertIn("more (--limit)", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
