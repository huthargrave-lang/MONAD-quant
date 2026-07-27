"""H11/DP-4: a semantic-staleness detector, and the check that it finds real things.

The epistemic layer detects **declared** staleness — a node says `status: superseded`
and the lint follows. It is blind to a node that never declared anything while later work
overtook it. H11 asked for a read-only `ctx stale` heuristic. Built as
`ctx.semantic_staleness()`, with two signals of deliberately different kinds.

**`edge_status_conflict` — hard, not ranked.** A node that is the TARGET of a
`supersedes` edge while still declaring `current`. The web contradicts itself about one
node.

Exactly one existed: **F10** ("all results are MORNING-ONLY"), which F12 supersedes while
F10 declared current with no `by:`. F186 called it a real find; F236 found it still
unfixed roughly fifty nodes later and said so. **It has since been fixed** (F239) — F10
declares `status: superseded; by: F12; reason: data-fixed`, and the conflict count is now
**zero**. F12 did not merely comment on F10: it diagnosed the yfinance long-range quirk
and shipped `tools/fetch_fullsession.py`, so F10's claim that *every* number in the web is
morning-only stopped describing the data. The caveat is still true of the historic
numbers, which is what `data-fixed` records rather than a deletion.

A hard signal with nothing left to find is indistinguishable from a broken one, so the
detector is now proved on synthetic input in both directions and the live web is checked
for a clean bill.

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


#: A two-node web where A supersedes B and B still declares current — the exact shape
#: the hard signal exists to catch. Used because the real web no longer contains one.
#: F1 deliberately links nothing back. Writing "Superseded by [[F2]]" in its body makes
#: the cue-classifier type F1->F2 as `supersedes` too, and the pair then flags each
#: other — a fixture that tested the detector's handling of a mutual supersession
#: rather than the one-way case being claimed.
_CONFLICTED_WEB = """
### F1 — a caveat that was later fixed
A claim about the data.

### F2 — the fix
Explains and fixes the cause. [[F1|supersedes]]
"""

_RESOLVED_WEB = """
### F1 — a caveat that was later fixed
<!-- status: superseded; by: F2; reason: data-fixed -->
A claim about the data.

### F2 — the fix
Explains and fixes the cause. [[F1|supersedes]]
"""


class TheEdgeStatusConflictIsRealTests(unittest.TestCase):
    """The hard signal — and it now has nothing to find, which is the point.

    F186 reported exactly one conflict, F10/F12: F10 declared `current` while the web
    carried an F12 `supersedes` edge pointing at it. F236 found it still unfixed roughly
    fifty nodes later and said so — *"the detector worked; nobody acted"*. It has now
    been acted on: F10 declares `status: superseded; by: F12; reason: data-fixed`, and
    D1/F186/F236 gained the `[[F12]]` citation the web's integrity rule requires of
    anything citing a superseded node.

    So the assertion that used to anchor this class — "F10 is flagged" — is deliberately
    gone, exactly as its own failure message instructed. What replaces it has to be
    stronger, because **a detector with nothing left to detect is indistinguishable from
    a broken one**. The live web is checked for a clean bill; the DETECTOR is checked
    against synthetic input in both directions.
    """

    @classmethod
    def setUpClass(cls):
        cls.conflicts, _ = ctx.semantic_staleness()
        cls.nodes, _ = ctx._parse_web()

    def test_the_web_declares_no_conflicts(self):
        """This is the check that caught the notation trap, minutes after the fix.

        F239 documented a fixture bug by QUOTING the broken fixture, and the quote
        contained wiki-style link syntax — so the parser emitted a real edge, and the
        adjacent "Superseded by" prose cue typed it `supersedes`. The node asserted a
        supersession it never meant, and this assertion went red on a conflict created
        by the very cycle that had just cleared the previous one.

        **The web has no escaping mechanism**: a node cannot discuss its own notation
        without emitting the link, so any finding *about* the syntax silently rewires
        the graph. Until an escape form exists, describe the notation rather than
        quoting it. A narrower guard ("recent nodes must not emit `supersedes`") was
        written and discarded — it fails on F232/F233, whose supersessions are real.
        The invariant is not "no supersedes edges", it is "every supersedes edge has a
        target that declares it", which is exactly this check.
        """
        self.assertEqual(
            self.conflicts, [],
            "an edge/status conflict is back: {}. The web contradicts itself about that "
            "node — either give it a `status:` comment naming its superseder, or retype "
            "the edge if the supersession is not real.".format(self.conflicts))

    def test_f10_is_now_properly_declared(self):
        """The specific fix, pinned so it cannot silently regress."""
        meta = ctx._node_meta(self.nodes["F10"])
        self.assertEqual(meta["status"], "superseded")
        self.assertEqual(meta["by"], "F12")
        self.assertEqual(meta["reason"], "data-fixed")

    def test_the_three_nodes_that_needed_the_superseder_citation_have_it(self):
        """The edits the supersession required, pinned individually.

        `note.py supersede` refused the write until D1, F186 and F236 cited F12 —
        those three, named by the lint itself. This asserts exactly that, and does NOT
        re-derive which nodes *ought* to need it: two earlier drafts tried, one being
        stricter than the lint (it failed on H5, which the lint never asks) and one
        looser (it went vacuous). Reimplementing a rule in order to check it is how a
        guard ends up testing its own restatement — the `ctx health` stale-cite count
        is the real check and has its own test.
        """
        for nid in ("D1", "F186", "F236"):
            targets = [e["target"] for e in self.nodes[nid]["edges"]]
            self.assertIn("F10", targets,
                          "{} no longer cites F10 at all".format(nid))
            self.assertIn(
                "F12", targets,
                "{} cites superseded F10 without its superseder F12 — `note.py "
                "supersede` required this edge before it would write".format(nid))

    def test_the_detector_still_finds_a_conflict_when_one_exists(self):
        """Non-vacuity. The real web is clean, so the signal is proved on synthetic input."""
        nodes, _ = ctx._parse_web_text(_CONFLICTED_WEB)
        conflicts, _ = ctx.semantic_staleness(nodes)
        self.assertEqual(
            conflicts, [("F1", "F2")],
            "the hard signal no longer fires on a node that is the target of a "
            "`supersedes` edge while declaring current — it has stopped working, and "
            "the clean bill above would mean nothing")

    def test_it_does_not_fire_once_the_status_is_declared(self):
        """The other direction: declaring the status must actually clear the signal."""
        nodes, _ = ctx._parse_web_text(_RESOLVED_WEB)
        conflicts, _ = ctx.semantic_staleness(nodes)
        self.assertEqual(
            conflicts, [],
            "the signal still fires after the node declares `status: superseded` — the "
            "remedy it recommends does not resolve it")

    def test_the_conflict_signal_stays_narrow(self):
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
