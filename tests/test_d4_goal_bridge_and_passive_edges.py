"""D4's bridge, and the passive-voice bug found while guarding it.

D4 asks whether the ~3.75% APY goal is achievable and answers *"the goal is reachable,
but as a diversified DAILY mean-reversion product with a horizon exit and a bear gate"*,
bridged `gated_by` to `config.ACTIVE_MODE` and `compute_trade_returns`. Two separate
things are checkable, and one of them was a live graph defect.

**1. The passive-voice inference bug.** D4's body contains: *"The ~3-bars/day note [[F15]]
was the weaker, less robust cousin and is formally superseded by [[F22]]"*. That sentence
says **F22 supersedes F15**. `_classify_edge` read the cue "superseded by" and emitted
**D4 --supersedes--> F22** — wrong on the direction (passive reverses it) and wrong on the
subject (F15, not D4). D7 carried the identical error, also aimed at F22.

F22 is the node that says the recommended daily-MR build does *not* beat buy&hold
out-of-sample — i.e. the evidence against D4's answer. The graph asserted that D4
supersedes it.

The blast radius is bounded and is stated as such: `_is_superseded` reads the explicit
`<!-- status: superseded -->` comment, not `supersedes` edges, so F22 was never flagged
stale. What the false edges did was appear as graph fact in `ctx web`, `walk`, `why` and
the graph HTML — pointing the wrong way on the most consequential relation in the
vocabulary, on the node recording the project's central question.

The fix declines rather than reverses: a cue inside `<be-verb> ... <cue> by` yields
`relates`. Guessing the reverse type would be a second guess stacked on the first, and the
prose establishes a relation between two *other* nodes, so nothing about this node's edge
is determined. (H37/DP-12 asked for exactly this audit.)

**2. D4's answer predates the evidence that changed it.** Its arithmetic checks out
(3.75% APY = +0.3072%/mo; QQQ's +2% APY is ~53% of target, "about HALF"). But its
conclusion — reachable as a diversified daily-MR product — is what F22 rejected OOS and
what F41 answered differently when it resolved D4 (a static blend clears the return goal;
near-zero drawdown is unattainable by any honest static *or* active build). D4's body
mentions none of F22's verdict, F41, D6 or F25. The bridge note carried the same stale
answer into `ctx impact`, so an agent editing `compute_trade_returns` was told the goal is
reachable as diversified daily-MR — a conclusion the project's own go/no-go rejected.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402

WEB = ROOT / "RESEARCH_WEB.md"


def node_body(nid):
    text = WEB.read_text(encoding="utf-8")
    start = text.index("### {} ".format(nid))
    end = text.find("\n### ", start + 5)
    return text[start:end if end > 0 else len(text)]


class PassiveVoiceNoLongerInvertsAnEdgeTests(unittest.TestCase):
    """The classifier fix, asserted on the exact sentences that broke it."""

    def test_the_D4_sentence_no_longer_yields_a_supersedes_edge(self):
        self.assertEqual(
            ctx._classify_edge("The ~3-bars/day note was the weaker cousin and is "
                               "formally superseded by "),
            "relates",
            "passive 'is superseded by' is being classified again — the edge would "
            "point from the wrong subject in the wrong direction")

    def test_active_voice_still_classifies(self):
        """The fix must not silence the cue table. A guard that declines everything
        would 'fix' the bug by making the inference useless."""
        for pre, want in (("this supersedes ", "supersedes"),
                          ("Supersedes ", "supersedes"),
                          ("this supports ", "supports"),
                          ("resolves ", "resolves"),
                          ("relies on ", "relies_on"),
                          ("builds on ", "builds_on"),
                          ("derived from ", "derived_from")):
            self.assertEqual(ctx._classify_edge(pre), want,
                             "active cue {!r} stopped classifying".format(pre))

    def test_other_passive_forms_are_declined_too(self):
        for pre in ("the result is supported by ", "was resolved by ",
                    "is now superseded by ", "were corroborated by "):
            self.assertEqual(ctx._classify_edge(pre), "relates",
                             "{!r} still infers a directed edge".format(pre))

    def test_the_negation_guard_survived(self):
        self.assertEqual(ctx._classify_edge("not supported by "), "relates")

    def test_no_inferred_edge_in_the_WEB_sits_behind_a_passive_cue(self):
        """The repo-wide sweep. Two existed (D4 and D7, both aimed at F22); a new one
        means the guard has a hole or a new phrasing slipped past it."""
        passive = re.compile(
            r"\b(?:is|are|was|were|been|be)\s+(?:\w+ly\s+|now\s+|already\s+|later\s+)?"
            r"(?:superseded|contradicted|supported|corroborated|refined|resolved|"
            r"closed|produced|driven|motivated)\s+by\s*$", re.I)
        nodes, _ = ctx._parse_web_text(WEB.read_text(encoding="utf-8"))
        offenders = []
        for nid, n in nodes.items():
            body = n.get("body", "")
            for m in ctx._LINK_RX.finditer(body):
                if m.group(2):
                    continue                      # explicit |type, not inferred
                pre = body[:m.start()]
                if ctx._classify_edge(pre) == "relates":
                    continue
                brk = max(pre.rfind(". "), pre.rfind("\n"), pre.rfind("; "))
                if passive.search((pre[brk + 1:] if brk >= 0 else pre).rstrip()):
                    offenders.append((nid, m.group(1)))
        self.assertEqual(
            offenders, [],
            "these inferred edges sit behind a passive cue, so their direction and "
            "subject are both suspect: {}".format(offenders))

    def test_D4_and_D7_no_longer_claim_to_supersede_F22(self):
        nodes, _ = ctx._parse_web_text(WEB.read_text(encoding="utf-8"))
        for nid in ("D4", "D7"):
            edges = {(e["target"], e["type"]) for e in nodes[nid]["edges"]}
            self.assertNotIn(
                ("F22", "supersedes"), edges,
                "{} claims to supersede F22 again — F22 is the OOS evidence against "
                "D4's answer, so this inverts the epistemic order".format(nid))

    def test_the_sweep_is_not_vacuous(self):
        """The sentences that produced the bug are still in the web, so the guard has
        real input. If they are ever reworded, this fires and points here."""
        self.assertIn("is formally superseded by [[F22]]", node_body("D4"))
        self.assertIn("superseded by", node_body("D7"))


class TheBlastRadiusWasBoundedTests(unittest.TestCase):
    """Stated so the finding is not read as larger than it was."""

    def test_superseded_status_comes_from_the_status_comment_not_edges(self):
        nodes, _ = ctx._parse_web_text(WEB.read_text(encoding="utf-8"))
        self.assertFalse(
            ctx._is_superseded(nodes["F22"]),
            "F22 is now flagged superseded — check whether an edge started driving "
            "status, which would have made the passive-voice bug far worse")
        self.assertTrue(
            ctx._is_superseded(nodes["F15"]),
            "F15 is no longer superseded, so the status mechanism this test "
            "distinguishes from edges has changed")


class D4sAnswerPredatesTheEvidenceTests(unittest.TestCase):
    """The bridge claim itself."""

    def test_the_monthly_equivalent_arithmetic_is_right(self):
        monthly = (1.0375) ** (1 / 12) - 1
        self.assertAlmostEqual(monthly * 100, 0.307, places=3,
                               msg="D4's '3.75% APY = +0.307%/mo' no longer holds")

    def test_two_percent_really_is_about_half_the_target(self):
        self.assertAlmostEqual(2.0 / 3.75, 0.533, places=3)

    def test_D4_does_not_mention_the_nodes_that_changed_its_answer(self):
        body = node_body("D4")
        missing = [n for n in ("F41", "D6", "F25") if "[[{}]]".format(n) not in body
                   and "[[{}|".format(n) not in body]
        self.assertEqual(
            missing, ["F41", "D6", "F25"],
            "D4's body now references {} — if it was updated to record the go/no-go "
            "verdict, good; retire this assertion and re-read the node".format(
                sorted(set(("F41", "D6", "F25")) - set(missing))))

    def test_F41_resolves_D4_with_a_different_answer(self):
        """The contradiction is real, not inferred from tone."""
        f41 = node_body("F41")
        self.assertIn("[[D4|resolves]]", f41)
        self.assertIn("near-zero", f41)
        self.assertIn("unattainable", f41)

    def test_F22_rejects_the_build_D4_recommends(self):
        f22 = node_body("F22")
        self.assertTrue(
            re.search(r"buy\s*&\s*hold|buy-and-hold", f22, re.I),
            "F22 no longer benchmarks against buy&hold — re-read whether it still "
            "contradicts D4's recommended build")

    def test_the_bridge_note_now_carries_the_caveat(self):
        import json
        bridges = json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["graph_bridges"]["bridges"]
        d4 = next(b for b in bridges if b["node"] == "D4")
        self.assertIn(
            "F181", d4["note"],
            "the D4 bridge note lost its caveat — `ctx impact` would again tell an "
            "agent editing compute_trade_returns that the goal is reachable as "
            "diversified daily-MR, which F22 and D6 rejected")


if __name__ == "__main__":
    unittest.main()
