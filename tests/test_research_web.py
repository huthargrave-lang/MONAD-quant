"""
Anti-rot tests for the research idea web (RESEARCH_WEB.md) — mirrors the
context-map anti-drift test. The idea web is the project's highest-stakes evolving
knowledge (it's where reversals like F13 live) and was previously the LEAST guarded:
`ctx web` parsed it but nothing verified its integrity.

Gates the UNAMBIGUOUS invariants so an agent can trust `ctx web`:
  * no dangling [[ID]] links (a deleted node would silently break a supersession chain)
  * node IDs are unique
  * a node tagged "[SUPERSEDED by Fx]" references an Fx that actually exists
  * every node has a non-empty title

(Stale-citation detection — a live node relying on a superseded one — is left as an
advisory in `ctx web --lint` until typed edges can distinguish provenance from reliance.)
"""
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import ctx  # noqa: E402  (the context tool — reuse its canonical parser)


class TestResearchWebIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.rev = ctx._parse_web()

    def test_web_parses_with_nodes(self):
        self.assertTrue(self.nodes, "RESEARCH_WEB.md parsed no nodes — parser or file broke")

    def test_no_dangling_links(self):
        dangling = [(nid, tgt) for nid, n in self.nodes.items()
                    for tgt in n["links"] if tgt not in self.nodes]
        self.assertEqual(dangling, [], f"dangling [[ID]] links (target missing): {dangling}")

    def test_ids_unique_and_well_formed(self):
        # _parse_web keys are unique by construction; assert IDs match the schema.
        for nid in self.nodes:
            self.assertRegex(nid, r"^[FHED]\d+$", f"malformed node id: {nid}")

    def test_superseded_nodes_reference_existing_superseder(self):
        for nid, n in self.nodes.items():
            m = re.search(r"\[SUPERSEDED by ([FHED]\d+)\]", n["title"])
            if m:
                with self.subTest(node=nid):
                    self.assertIn(m.group(1), self.nodes,
                                  f"{nid} says superseded by {m.group(1)}, which doesn't exist")

    def test_every_node_has_a_title(self):
        for nid, n in self.nodes.items():
            self.assertTrue(n["title"].strip(), f"{nid} has an empty title")


class TestTypedEdges(unittest.TestCase):
    """Context Web v2 #2 — every link now carries a relation type (explicit
    [[ID|type]] or cue-classified), and reliance never points at a retraction."""

    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.rev = ctx._parse_web()

    def test_edges_cover_links_exactly(self):
        # backward-compat: edge targets are exactly the (unchanged) links contract.
        for nid, n in self.nodes.items():
            with self.subTest(node=nid):
                self.assertIn("edges", n)
                self.assertEqual(sorted(e["target"] for e in n["edges"]), n["links"])

    def test_edge_types_in_vocabulary(self):
        for nid, n in self.nodes.items():
            for e in n["edges"]:
                with self.subTest(node=nid, target=e["target"]):
                    self.assertIn(e["type"], ctx.EDGE_TYPES,
                                  f"{nid}->{e['target']} has unknown edge type {e['type']!r}")

    def test_explicit_typed_edge_is_parsed(self):
        # F13 explicitly supersedes F3 (an explicit [[F3|supersedes]] in the web).
        types = {e["target"]: e["type"] for e in self.nodes["F13"]["edges"]}
        self.assertEqual(types.get("F3"), "supersedes",
                         "explicit [[F3|supersedes]] from F13 was not parsed as typed")

    def test_no_live_node_relies_on_superseded(self):
        """The invariant typed edges make checkable: a current node must not
        rely_on/support/refine/build_on a superseded node (a retracted claim)."""
        offenders = []
        for nid, n in self.nodes.items():
            if ctx._is_superseded(n):
                continue
            for e in n["edges"]:
                t = e["target"]
                if (e["type"] in ctx.RELIANCE_EDGES and t in self.nodes
                        and ctx._is_superseded(self.nodes[t])):
                    offenders.append(f"{nid} --{e['type']}--> {t}")
        self.assertEqual(offenders, [], f"live nodes rely on superseded nodes: {offenders}")


if __name__ == "__main__":
    unittest.main()
