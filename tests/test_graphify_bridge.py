"""
Unit tests for the PURE functions of the Graphify→Context Web bridge
(``tools/graphify_bridge.py``).

These exercise the classification, edge-mapping, coverage-gap, and report logic over
synthetic normalized graphs — no real ``graph.json``, no Graphify, no I/O, no network.
The bridge is suggestions-only; these tests pin that it never proposes an auto-edit and
that the human-only epistemic edges are never inferred.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import graphify_bridge as gb  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_tolerates_alias_keys(self):
        raw = {"entities": [{"key": "n1", "label": "Foo", "category": "Function", "file": "src/x.py"}],
               "relationships": [{"from": "n1", "to": "n2", "relation": "Calls"}]}
        g = gb.normalize_graph(raw)
        self.assertEqual(g["nodes"][0]["id"], "n1")
        self.assertEqual(g["nodes"][0]["name"], "Foo")
        self.assertEqual(g["nodes"][0]["kind"], "function")   # lowercased
        self.assertEqual(g["edges"][0]["source"], "n1")
        self.assertEqual(g["edges"][0]["type"], "calls")

    def test_empty_and_garbage_safe(self):
        self.assertEqual(gb.normalize_graph({}), {"nodes": [], "edges": []})
        self.assertEqual(gb.normalize_graph(None), {"nodes": [], "edges": []})
        g = gb.normalize_graph({"nodes": ["notadict", 3]})
        self.assertEqual(g["nodes"], [])


class TestClassifyNode(unittest.TestCase):
    def test_claimed_module_is_already_mapped(self):
        s = gb.classify_node({"id": "a", "name": "run_backtest", "kind": "function",
                              "path": "src/backtest/runner.py"},
                             claimed_modules={"src/backtest/runner.py"}, web_names=set())
        self.assertEqual(s["layer"], "code")
        self.assertEqual(s["action"], "already_mapped")
        self.assertFalse(s["needs_human"])

    def test_unclaimed_module_suggests_registration(self):
        s = gb.classify_node({"id": "a", "name": "foo", "kind": "function",
                              "path": "tools/new_tool.py"},
                             claimed_modules=set(), web_names=set())
        self.assertEqual(s["action"], "suggest_code_bridge")
        self.assertIn("tools/new_tool.py", s["suggested"])

    def test_code_symbol_without_path_maps_to_code_layer(self):
        s = gb.classify_node({"id": "a", "name": "Sizer", "kind": "class", "path": None},
                             claimed_modules=set(), web_names=set())
        self.assertEqual(s["layer"], "code")
        self.assertFalse(s["needs_human"])

    def test_concept_is_epistemic_and_needs_human(self):
        s = gb.classify_node({"id": "c", "name": "Cost stress", "kind": "concept", "path": None},
                             claimed_modules=set(), web_names=set())
        self.assertEqual(s["layer"], "epistemic")
        self.assertTrue(s["needs_human"])
        self.assertIn("Finding/Hypothesis", s["suggested"])

    def test_paper_is_evidence_source_candidate(self):
        s = gb.classify_node({"id": "p", "name": "Deflated Sharpe", "kind": "paper", "path": None},
                             claimed_modules=set(), web_names=set())
        self.assertIn("Experiment", s["suggested"])
        self.assertTrue(s["needs_human"])

    def test_name_matching_existing_web_node_flags_duplicate(self):
        s = gb.classify_node({"id": "x", "name": "The Mechanism", "kind": "concept", "path": None},
                             claimed_modules=set(), web_names={"the mechanism"})
        self.assertEqual(s["action"], "already_in_web")

    def test_unknown_kind_stays_graphify_only(self):
        s = gb.classify_node({"id": "z", "name": "blob", "kind": "weird", "path": None},
                             claimed_modules=set(), web_names=set())
        self.assertEqual(s["layer"], "skip")
        self.assertEqual(s["action"], "graphify_only")


class TestMapEdge(unittest.TestCase):
    def test_calls_is_mechanical_code_bridge(self):
        e = gb.map_edge({"source": "a", "target": "b", "type": "calls"})
        self.assertEqual(e["suggested_edge"], "implemented_in")
        self.assertEqual(e["disposition"], "mechanical")

    def test_references_is_review(self):
        e = gb.map_edge({"source": "a", "target": "b", "type": "references"})
        self.assertEqual(e["disposition"], "review")

    def test_unknown_edge_defaults_to_relates_review(self):
        e = gb.map_edge({"source": "a", "target": "b", "type": "xyz"})
        self.assertEqual(e["suggested_edge"], "relates")
        self.assertEqual(e["disposition"], "review")

    def test_evidence_edges_are_never_inferred(self):
        # the human-only epistemic edges must not appear as any auto-mapping target
        targets = {v[0] for v in gb.EDGE_MAP.values()}
        for forbidden in gb.NEVER_INFERRED:
            self.assertNotIn(forbidden, targets, forbidden)


class TestCoverageGaps(unittest.TestCase):
    def test_uncaptured_code_and_concepts(self):
        nodes = [
            {"name": "run", "kind": "function", "path": "src/backtest/runner.py"},   # claimed
            {"name": "f", "kind": "function", "path": "tools/unmapped.py"},           # uncaptured code
            {"name": "Calmar benchmark", "kind": "concept", "path": None},            # uncaptured concept
            {"name": "The Mechanism", "kind": "concept", "path": None},               # in web
        ]
        gaps = gb.coverage_gaps(nodes, claimed_modules={"src/backtest/runner.py"},
                                web_names={"the mechanism"})
        self.assertIn("tools/unmapped.py", gaps["uncaptured_code"])
        self.assertIn("Calmar benchmark", gaps["uncaptured_concepts"])
        self.assertNotIn("The Mechanism", gaps["uncaptured_concepts"])

    def test_reverse_check_flags_web_without_backing(self):
        gaps = gb.coverage_gaps([{"name": "Foo", "kind": "concept", "path": None}],
                                claimed_modules=set(), web_names={"foo", "orphan finding"})
        self.assertIn("orphan finding", gaps["web_without_graphify_backing"])
        self.assertNotIn("foo", gaps["web_without_graphify_backing"])


class TestBuildReport(unittest.TestCase):
    def _report(self):
        suggestions = [
            gb.classify_node({"id": "a", "name": "foo", "kind": "function", "path": "tools/new.py"}, set(), set()),
            gb.classify_node({"id": "c", "name": "Cost stress", "kind": "concept", "path": None}, set(), set()),
        ]
        edges = [gb.map_edge({"source": "a", "target": "b", "type": "references"})]
        gaps = gb.coverage_gaps([], set(), set())
        meta = {"generated_at": "2026-06-29T00:00:00", "graph_path": "graphify-out/graph.json",
                "n_nodes": 2, "n_edges": 1, "n_web": 130, "n_claimed": 40}
        return gb.build_report(suggestions, edges, gaps, meta)

    def test_report_markdown_and_json(self):
        md, obj = self._report()
        self.assertIsInstance(md, str)
        self.assertIn("Suggestions only", md)
        self.assertIn("Suggested code-symbol nodes", md)
        self.assertEqual(obj["schema"], "graphify_bridge_suggestions/v1")
        # json must round-trip and carry the safety reminder
        restored = json.loads(json.dumps(obj, default=str))
        self.assertIn("SUGGESTIONS ONLY", restored["reminder"])

    def test_safe_out_path_refuses_escape(self):
        with self.assertRaises(SystemExit):
            gb._safe_out_path("../../etc/passwd")


if __name__ == "__main__":
    unittest.main()
