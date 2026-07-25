"""CI guards for RESEARCH_WEB.md structural integrity (EPI-00 / H73).

EPI-00 found that the web is only ever re-examined when adjacent new work happens
to touch it — there is no background review. These four invariants were all
VIOLATED when the audit first ran, and each was invisible to existing tooling:

1. **Declared supersession implies a tombstone.** SCHEMA §5 says `supersedes` is
   "auto-paired with the tombstone". F13 declared `[[F9|supersedes]]` for weeks
   while F9 carried no tombstone, so every reader still counted F9's (retracted)
   +0.27%/mo SPY claim as current.
2. **Edge types come from the enforced vocabulary.** Three `extends` edges existed;
   `extends` is not in `EDGE_TYPES`, so ctx silently cue-classified them to
   `relates` and the author's intended relation was lost.
3. **The reliance graph is acyclic.** Reliance edges are defined as pointing to
   *prior* nodes, so a cycle means at least one points forward in time. D6 carried
   `builds_on` edges to F24/F25, which were captured three days AFTER it.
4. **Node IDs are unique.** A historical revision defined D7 and D8 twice with
   unrelated bodies; the last one silently won.

`ctx --lint` covers dangling links, stale cites and reliance-on-superseded, but
none of the above — which is precisely why they persisted. Stdlib only.
"""
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "epistemic_audit_lab", ROOT / "tools" / "epistemic_audit_lab.py"
)
LAB = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = LAB
_SPEC.loader.exec_module(LAB)


class WebIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes = LAB.parse_web(LAB.WEB.read_text(encoding="utf-8"))
        cls.checks = LAB.integrity_checks(cls.nodes)

    def test_declared_supersession_has_a_tombstone(self):
        offenders = self.checks["supersedes_edge_without_tombstone"]
        self.assertEqual(
            offenders, [],
            "node(s) are the target of an explicit [[X|supersedes]] edge but carry no "
            "`<!-- status: superseded; ... -->` tombstone, so every other reader still "
            "counts them as CURRENT claims. Fix with: "
            "python3 tools/note.py supersede <ID> --by <NEW> --reason <code> --commit "
            f"-> {offenders}",
        )

    def test_no_out_of_vocabulary_edge_types(self):
        offenders = self.checks["out_of_vocabulary_edge_types"]
        self.assertEqual(
            offenders, [],
            "edge type(s) outside ctx.EDGE_TYPES. ctx silently falls back to cue "
            "classification for these, so the author's intended relation is lost "
            "(e.g. `extends` -> `relates`; SCHEMA defines `builds_on` as "
            f"'Extends/depends on an earlier claim'). -> {offenders}",
        )

    def test_no_duplicate_node_ids(self):
        offenders = self.checks["duplicate_node_ids"]
        self.assertEqual(
            offenders, [],
            f"node ID(s) defined more than once; the last body silently wins -> {offenders}",
        )

    def test_tombstones_point_at_nodes_that_exist(self):
        offenders = self.checks["tombstone_pointing_at_missing_node"]
        self.assertEqual(offenders, [], f"tombstone(s) name a missing superseder -> {offenders}")

    def test_reliance_graph_is_acyclic(self):
        """Reliance edges (relies_on/supports/refines/builds_on) are defined as
        pointing to PRIOR nodes, so a cycle means one points forward in time."""
        depends, _rdepends, _cites = LAB.parse_edges(self.nodes)
        cycles = LAB.find_cycles(depends, sorted(self.nodes))
        self.assertEqual(
            cycles, [],
            "cycle(s) in the reliance graph. A reliance edge must point to an EARLIER "
            "node; a cycle means at least one points at a node captured later. Retype "
            "the forward-pointing edge to `relates`/`drives` (the later node should "
            f"already carry the reliance edge back). -> {cycles}",
        )


class ParserAgreementTest(unittest.TestCase):
    """The audit lab must read the web exactly as ctx.py does. A hand-written copy
    of the cue classifier drifted once already and silently corrupted the reliance
    graph (F136); this is the guard that keeps one source of truth."""

    def test_audit_lab_matches_ctx_on_every_edge(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import ctx as CTX

        ctx_nodes, _ = CTX._parse_web()
        mine = LAB.parse_web(LAB.WEB.read_text(encoding="utf-8"))
        self.assertEqual(set(ctx_nodes), set(mine))
        for node_id, node in ctx_nodes.items():
            self.assertEqual(
                {(e["target"], e["type"]) for e in node["edges"]},
                set(mine[node_id]["edges"]),
                f"edge disagreement with ctx.py at {node_id}",
            )


if __name__ == "__main__":
    unittest.main()
