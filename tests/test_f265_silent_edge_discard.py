"""A second edge to the same target is silently discarded — F265.

`_parse_web_text` keeps **one** edge per `(source, target)` pair. The tie-break is::

    if cur is None or rank > cur[0] or (
            rank == cur[0] and t in RELIANCE_EDGES and cur[1] not in RELIANCE_EDGES):

Two explicit types both score rank 2, so the second clause decides — and it can only fire
when the incumbent is *not* a reliance edge. When **both** are reliance edges
(`relies_on`, `supports`, `refines`, `builds_on`), neither clause fires and **the first
one written simply wins**, with no warning anywhere.

**Found by walking into it.** `note.py link F205 H31 --type supports` was run and reported
`F205 --supports--> H31`. F205 already carried `[[H31|refines]]`; both are reliance edges;
`refines` won; the new edge vanished. `ctx web --lint` stayed at 0 problems / 0 advisories.
The visible consequence is that H31 remained top of the backlog as *"no Finding supports or
contradicts it"* — because `refines` is not in the backlog's `ANSWERING_EDGES`
(`{supports, resolves, contradicts}`) — while an explicit `supports` link sat in the file.

So the graph's precedence rule and the backlog's semantics disagree, and the disagreement
is invisible from both ends.

**The defect is LATENT, and stating that precisely matters.** Four nodes already declare
two types to one target, and all four resolve *correctly*:

    F140 -> H27   [relates, supports]            kept supports
    F143 -> H27   [relates, supports]            kept supports
    F223 -> H27   [relates, supports, supports]  kept supports
    F263 -> H29   [relates, supports]            kept supports

Every one discards `relates` in favour of the stronger `supports` — the tie-break working
as designed. **No committed node currently loses information.** The failure needs *two
reliance* edges, which none has. An earlier draft of this file claimed five conflicts with
F205 losing `supports`; that fifth pair was one this cycle created and then reverted, and
the guard below caught the overstatement.

So this fixes a trap rather than damage: it took one session to fall into, the tool reported
success, and nothing would have flagged it.

`note.py link` now checks by **target**, not by `(target, type)`, so it refuses rather than
writing a link the parser will drop, and says which edge already exists. The no-op link this
cycle created was reverted rather than left in place: an edge that reads as an answer while
having no effect is worse than no edge.

**H31 is deliberately left open.** F205 both refines and supports it, the vocabulary permits
one edge, and picking `supports` would edit a dated node to satisfy a tool. The honest state
is that F205 answers H31 and the graph cannot say so.

Guards are bidirectional: they fail if `link` stops refusing a conflicting target, if it
starts refusing a genuinely new edge, if the parser's one-edge-per-target rule changes (then
the refusal is unnecessary — supersede), or if the count of existing conflicting pairs moves.
"""
import collections
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ctx  # noqa: E402

WEB = ROOT / "RESEARCH_WEB.md"
LINK_RX = re.compile(r"\[\[([A-Za-z]+\d+)\|([a-z_]+)\]\]")


def _declared_pairs():
    """Every (node, target) -> [types] straight from the source, pre-parser."""
    out = {}
    for block in re.split(r"^### ", WEB.read_text(encoding="utf-8"), flags=re.M)[1:]:
        m = re.match(r"([A-Za-z]+\d+)", block)
        if not m:
            continue
        per = collections.defaultdict(list)
        for link in LINK_RX.finditer(block):
            per[link.group(1)].append(link.group(2))
        out[m.group(1)] = per
    return out


class TheParserKeepsOneEdgePerTargetTests(unittest.TestCase):

    def test_two_reliance_types_collapse_to_the_first(self):
        nodes, _ = ctx._parse_web_text(
            "### F1 — a\nSee [[F2|refines]] and also [[F2|supports]].\n\n"
            "### F2 — b\nx\n")
        edges = [e for e in nodes["F1"]["edges"] if e["target"] == "F2"]
        self.assertEqual(len(edges), 1,
                         "the parser now keeps both edges — F265's premise is gone")
        self.assertEqual(edges[0]["type"], "refines",
                         "first-wins no longer holds between two reliance edges")

    def test_a_reliance_edge_does_outrank_a_non_reliance_one(self):
        """The tie-break that DOES fire, so the rule is not simply first-wins."""
        nodes, _ = ctx._parse_web_text(
            "### F1 — a\nSee [[F2|relates]] and also [[F2|supports]].\n\n"
            "### F2 — b\nx\n")
        edges = [e for e in nodes["F1"]["edges"] if e["target"] == "F2"]
        self.assertEqual(edges[0]["type"], "supports")

    def test_the_discarded_type_can_be_the_one_tooling_needs(self):
        """`refines` is not an ANSWERING_EDGE, so losing `supports` hides an answer."""
        import research_backlog as rb
        self.assertIn("supports", rb.ANSWERING_EDGES)
        self.assertNotIn("refines", rb.ANSWERING_EDGES)


class TheLiveWebCarriesTheKnownConflictsTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        nodes, _ = ctx._parse_web()
        cls.nodes = nodes
        cls.declared = _declared_pairs()

    def _conflicts(self):
        out = []
        for nid, per in self.declared.items():
            for target, types in per.items():
                if len(set(types)) > 1:
                    out.append((nid, target, sorted(set(types))))
        return sorted(out)

    def test_exactly_the_four_known_conflicts_exist(self):
        got = {(nid, tgt) for nid, tgt, _ in self._conflicts()}
        self.assertEqual(
            got,
            {("F140", "H27"), ("F143", "H27"), ("F223", "H27"), ("F263", "H29")},
            "the set of conflicting edge pairs changed — if one was repaired, "
            "supersede F265 rather than editing this expectation")

    def test_none_of_them_currently_loses_information(self):
        """The claim that keeps this finding honest: every existing conflict resolves
        to the stronger edge, so the defect is a trap rather than present damage."""
        for nid, target, types in self._conflicts():
            with self.subTest(node=nid):
                kept = {e["type"] for e in self.nodes[nid]["edges"]
                        if e["target"] == target}
                self.assertEqual(
                    kept, {"supports"},
                    "{} -> {} now keeps {} rather than 'supports' — a committed node "
                    "IS losing information and F265 needs re-scoping".format(
                        nid, target, kept))

    def test_f205_carries_a_single_uncontested_edge_to_h31(self):
        """The no-op link this cycle created was reverted; it must stay reverted, or
        the corpus carries an edge that reads as an answer and has no effect."""
        kept = {e["type"] for e in self.nodes["F205"]["edges"] if e["target"] == "H31"}
        self.assertEqual(kept, {"refines"})
        self.assertEqual(self.declared["F205"]["H31"], ["refines"],
                         "a second declared type to H31 is back in the source")

    def test_the_lint_does_not_flag_any_of_them(self):
        """Non-vacuity for 'invisible from both ends'."""
        out = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ctx.py"), "web", "--lint"],
            capture_output=True, text=True, cwd=str(ROOT))
        self.assertIn("0 problem(s)", out.stdout)


class TheLinkCommandRefusesTests(unittest.TestCase):

    def _link(self, src, target, etype):
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / "note.py"), "link",
             src, target, "--type", etype],
            capture_output=True, text=True, cwd=str(ROOT))

    def test_a_conflicting_type_is_refused_with_the_reason(self):
        out = self._link("F205", "H31", "supports")
        self.assertNotEqual(out.returncode, 0, "the conflicting link was accepted")
        blob = out.stdout + out.stderr
        self.assertIn("refines", blob, "the refusal does not name the existing edge")
        self.assertIn("silently discarded", blob,
                      "the refusal does not explain why it would be a no-op")

    def test_the_same_type_is_still_refused(self):
        out = self._link("F205", "H31", "refines")
        self.assertNotEqual(out.returncode, 0)

    def test_a_genuinely_new_edge_is_still_accepted(self):
        """Non-vacuity: a check that refuses everything is not a check. Dry run —
        no --commit, so nothing is written."""
        out = self._link("F205", "F172", "relates")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("DRY RUN", out.stdout)


if __name__ == "__main__":
    unittest.main()
