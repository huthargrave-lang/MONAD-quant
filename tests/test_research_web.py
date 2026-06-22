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
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import ctx  # noqa: E402  (the context tool — reuse its canonical parser)


def _parse_web_text(text):
    """Run the real ctx._parse_web over synthetic web markdown (temporarily
    repointing ctx.WEB), so edge-classification edge cases are testable."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
        tf.write(text)
        name = tf.name
    old = ctx.WEB
    try:
        ctx.WEB = name
        return ctx._parse_web()
    finally:
        ctx.WEB = old
        os.unlink(name)


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


class TestEdgeClassificationHardening(unittest.TestCase):
    """Adversarial-review regressions (Context Web v2 #2–#5): malformed typed
    links must not vanish, and the cue classifier must not mis-type in ways that
    hide (or fabricate) a reliance-on-superseded stale-cite."""

    def _edges(self, body, node="N1"):
        nodes, _ = _parse_web_text(f"### {node} — t\n{body}\n### F2 — [SUPERSEDED by F9]\nx\n"
                                   "### F9 — y\nz\n### F3 — w\nq\n")
        return {e["target"]: e["type"] for e in nodes[node]["edges"]}, nodes

    def test_malformed_typed_link_not_dropped(self):  # finding #2
        # natural-language type → keep the link (untyped); dangling/stale-cite must still see it.
        self.assertEqual([m[0] for m in ctx._LINK_RX.findall("[[F99|relies on]]")], ["F99"])
        edges, nodes = self._edges("This relies on [[F99|relies on]] heavily.")
        self.assertIn("F99", nodes["N1"]["links"], "malformed-typed link target was dropped")

    def test_spaced_explicit_type_tolerated(self):  # finding #2
        edges, _ = self._edges("It [[F3| supersedes]] the prior view.")
        self.assertEqual(edges["F3"], "supersedes")

    def test_reliance_wins_over_closer_lineage_cue(self):  # finding #3
        # within one clause, a closer lineage cue ('based on') must NOT override the
        # reliance verb ('relies on') — else a reliance-on-superseded escapes --lint.
        edges, _ = self._edges("This decision relies on results based on [[F2]] for its conclusion.")
        self.assertEqual(edges["F2"], "relies_on", "a closer lineage cue hid the reliance edge")

    def test_negated_support_is_not_a_reliance_edge(self):  # finding #4
        edges, _ = self._edges("This conclusion is unsupported by [[F2]].")
        self.assertNotIn(edges["F2"], ctx.RELIANCE_EDGES,
                         "'unsupported' was mis-typed as a reliance edge")

    def test_dedupe_prefers_reliance_at_equal_rank(self):  # finding #5
        edges, _ = self._edges("Produced by [[F2]]. Later work relies on [[F2]] for its result.")
        self.assertEqual(edges["F2"], "relies_on",
                         "reliance edge hidden behind a same-rank lineage edge to the same target")


class TestStructuredStatus(unittest.TestCase):
    """Context Web v2 #3 — node status is parsed structured metadata, not a
    title-string match; reason codes + retracted/current are first-class."""

    def test_explicit_metadata_parsed(self):
        nodes, _ = _parse_web_text(
            "### F1 — a title\n<!-- status: superseded; by: F9; reason: data-fixed; conf: 0.2 -->\nbody\n"
            "### F9 — b\nx\n")
        m = ctx._node_meta(nodes["F1"])
        self.assertEqual(m["status"], "superseded")
        self.assertEqual(m["by"], "F9")
        self.assertEqual(m["reason"], "data-fixed")
        self.assertEqual(m["conf"], 0.2)
        self.assertTrue(ctx._is_superseded(nodes["F1"]))

    def test_title_tag_fallback_still_works(self):
        nodes, _ = _parse_web_text("### F2 — [SUPERSEDED by F9] old\nbody no meta\n### F9 — b\nx\n")
        m = ctx._node_meta(nodes["F2"])
        self.assertEqual(m["status"], "superseded")
        self.assertEqual(m["by"], "F9")
        self.assertTrue(ctx._is_superseded(nodes["F2"]))

    def test_explicit_current_overrides_title_tag(self):
        nodes, _ = _parse_web_text(
            "### F3 — [SUPERSEDED by F9] reinstated\n<!-- status: current -->\nbody\n### F9 — b\nx\n")
        self.assertFalse(ctx._is_superseded(nodes["F3"]),
                         "explicit `status: current` must override the title tag")

    def test_retracted_is_not_current(self):
        nodes, _ = _parse_web_text("### F4 — t\n<!-- status: retracted; reason: withdrawn -->\nb\n")
        self.assertTrue(ctx._is_superseded(nodes["F4"]))

    def test_known_status_and_reason_vocab_in_real_web(self):
        nodes, _ = ctx._parse_web()
        for nid, n in nodes.items():
            m = ctx._node_meta(n)
            self.assertIn(m["status"], ctx.STATUS_VALUES, f"{nid} bad status {m['status']!r}")
            if m["reason"]:
                self.assertIn(m["reason"], ctx.REASON_CODES, f"{nid} bad reason {m['reason']!r}")


if __name__ == "__main__":
    unittest.main()
