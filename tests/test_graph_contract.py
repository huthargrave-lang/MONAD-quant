"""`ctx graph --json` is a frozen machine contract — `ctx.graph/1` (seam slice 1a).

Before this slice nothing consumed or pinned the CLI JSON, its edge order was
hash-seeded (every `tested_by` edge reordered between runs — see RESEARCH_WEB.md /
docs/DIRECTIONS.md D-6), and `schema_version` lived in two docs with nothing tying
them to the code. This file freezes the shape so a second consumer (another repo,
CI, an exporter) can rely on it:

  * top-level keys exactly {contract, schema_version, project, nodes, edges};
  * every node exactly {id, kind, title, status}; every edge exactly {from, to, type};
  * node kinds and edge types drawn from DECLARED vocabularies — the idea kinds, the
    bridge relations (mirrors tests/test_context_map.py REL_VOCAB), and — declared
    here for the first time — the auto-extracted code-layer edge types;
  * endpoints resolve, no duplicate (from, to, type), edges in canonical
    (from, to, type) order, byte-stable across PYTHONHASHSEED (JSON *and* HTML);
  * the served /api/graph.json carries the same nodes and edges as the CLI;
  * `schema_version` is pinned equal in SCHEMA.md:1, RESEARCH_WEB.md:2,
    `ctx.SCHEMA_VERSION` and the JSON; `len(EDGE_TYPES) == 12 ==` SCHEMA.md §5a rows.

`--ideas-only` keeps the idea↔code BRIDGE TARGETS (kind `code` / `config` pseudo-nodes)
— only the auto-extracted `module` / `area` layer is dropped. The assertion below says
exactly that; "kinds ⊆ {F,H,E,D}" would be red on day one.
"""
import json
import os
import re
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import ctx  # noqa: E402

CTX = os.path.join(REPO, "tools", "ctx.py")

CONTRACT = "ctx.graph/1"
TOP_KEYS = {"contract", "schema_version", "project", "nodes", "edges"}
NODE_KEYS = {"id", "kind", "title", "status"}
EDGE_KEYS = {"from", "to", "type"}
IDEA_KINDS = {"F", "H", "E", "D"}
BRIDGE_PSEUDO_KINDS = {"code", "config"}        # idea↔code bridge targets
CODE_LAYER_KINDS = {"module", "area"}           # only with include_code=True
# Mirrors tests/test_context_map.py::TestGraphBridges.REL_VOCAB (pinned below).
BRIDGE_TYPES = {"concerns", "implemented_in", "measured_by", "gated_by"}
# The auto-extracted code graph's edge vocabulary (build_graph include_code=True),
# declared here for the first time; verified against live output before declaring.
CODE_EDGE_TYPES = {"imports", "owns", "tested_by", "reads_config", "defined_in"}

_SV_RX = re.compile(r"<!-- schema_version: (\S+) -->")


def _run(args, seed):
    env = dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, CTX, *args], cwd=REPO, env=env,
                       capture_output=True, timeout=600)
    if r.returncode != 0:
        raise AssertionError(f"ctx {' '.join(args)} exited {r.returncode}: "
                             f"{r.stderr.decode(errors='replace')[-800:]}")
    return r.stdout


def _edge_key(e):
    return (e["from"], e["to"], e["type"])


class GraphJsonContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full_raw = {s: _run(["graph", "--json"], s) for s in (1, 2)}
        cls.ideas_raw = {s: _run(["graph", "--ideas-only", "--json"], s) for s in (1, 2)}
        cls.html_raw = {s: _run(["graph", "--html"], s) for s in (1, 2)}
        cls.full = json.loads(cls.full_raw[1])
        cls.ideas = json.loads(cls.ideas_raw[1])

    # ── top level ──────────────────────────────────────────────────────────
    def test_top_level_keys_and_contract_full(self):
        self.assertEqual(set(self.full), TOP_KEYS)
        self.assertEqual(self.full["contract"], CONTRACT)
        self.assertEqual(self.full["schema_version"], ctx.SCHEMA_VERSION)
        self.assertIsInstance(self.full["project"], str)
        self.assertTrue(self.full["nodes"] and self.full["edges"])

    def test_top_level_keys_and_contract_ideas_only(self):
        self.assertEqual(set(self.ideas), TOP_KEYS)
        self.assertEqual(self.ideas["contract"], CONTRACT)
        self.assertEqual(self.ideas["schema_version"], ctx.SCHEMA_VERSION)
        self.assertTrue(self.ideas["nodes"] and self.ideas["edges"])

    # ── nodes ──────────────────────────────────────────────────────────────
    def _check_nodes(self, data, allowed_kinds):
        ids = [n["id"] for n in data["nodes"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate node ids")
        for n in data["nodes"]:
            self.assertEqual(set(n), NODE_KEYS, n)
            self.assertLessEqual(len(n["title"]), 120, n["id"])
            self.assertIn(n["status"], ctx.STATUS_VALUES, n["id"])
            self.assertIn(n["kind"], allowed_kinds, n["id"])

    def test_full_graph_node_shape_and_kinds(self):
        self._check_nodes(self.full, IDEA_KINDS | BRIDGE_PSEUDO_KINDS | CODE_LAYER_KINDS)
        kinds = {n["kind"] for n in self.full["nodes"]}
        self.assertTrue(CODE_LAYER_KINDS <= kinds, f"code layer missing: {kinds}")

    def test_ideas_only_node_shape_and_kinds(self):
        # kinds ⊆ idea kinds ∪ {code, config}: bridge pseudo-nodes survive include_code=False
        self._check_nodes(self.ideas, IDEA_KINDS | BRIDGE_PSEUDO_KINDS)
        kinds = {n["kind"] for n in self.ideas["nodes"]}
        self.assertFalse(kinds & CODE_LAYER_KINDS, f"module/area leaked: {kinds}")

    # ── edges ──────────────────────────────────────────────────────────────
    def _check_edges(self, data, allowed_types):
        ids = {n["id"] for n in data["nodes"]}
        keys = [_edge_key(e) for e in data["edges"]]
        for e in data["edges"]:
            self.assertEqual(set(e), EDGE_KEYS, e)
            self.assertIn(e["from"], ids, f"dangling from: {e}")
            self.assertIn(e["to"], ids, f"dangling to: {e}")
            self.assertIn(e["type"], allowed_types, e)
        self.assertEqual(len(keys), len(set(keys)), "duplicate (from, to, type)")
        self.assertEqual(keys, sorted(keys), "edges not in canonical (from, to, type) order")

    def test_full_graph_edge_shape_types_endpoints_order(self):
        self._check_edges(self.full, ctx.EDGE_TYPES | BRIDGE_TYPES | CODE_EDGE_TYPES)
        types = {e["type"] for e in self.full["edges"]}
        self.assertTrue(types & CODE_EDGE_TYPES, "no code-layer edges in the full graph")
        # every declared code edge type that the extractor can produce today is present
        self.assertTrue({"imports", "owns", "tested_by", "reads_config", "defined_in"} <= types,
                        f"missing code edge types: {CODE_EDGE_TYPES - types}")

    def test_ideas_only_edge_shape_types_endpoints_order(self):
        self._check_edges(self.ideas, ctx.EDGE_TYPES | BRIDGE_TYPES)
        types = {e["type"] for e in self.ideas["edges"]}
        self.assertFalse(types & CODE_EDGE_TYPES, f"code-layer edges leaked: {types}")

    def test_declared_vocabularies_are_disjoint(self):
        self.assertFalse(ctx.EDGE_TYPES & BRIDGE_TYPES)
        self.assertFalse(ctx.EDGE_TYPES & CODE_EDGE_TYPES)
        self.assertFalse(BRIDGE_TYPES & CODE_EDGE_TYPES)

    def test_bridge_types_mirror_the_manifest_guard(self):
        src = open(os.path.join(REPO, "tests", "test_context_map.py")).read()
        m = re.search(r"REL_VOCAB = \{([^}]*)\}", src)
        self.assertIsNotNone(m, "REL_VOCAB literal moved in tests/test_context_map.py")
        self.assertEqual(set(re.findall(r'"(\w+)"', m.group(1))), BRIDGE_TYPES)

    # ── determinism ────────────────────────────────────────────────────────
    def test_json_and_html_are_run_stable(self):
        self.assertEqual(self.full_raw[1], self.full_raw[2], "graph --json differs across seeds")
        self.assertEqual(self.ideas_raw[1], self.ideas_raw[2],
                         "graph --ideas-only --json differs across seeds")
        self.assertEqual(self.html_raw[1], self.html_raw[2], "graph --html differs across seeds")

    # ── served route == CLI ────────────────────────────────────────────────
    def test_served_graph_json_matches_cli(self):
        code, body, ctype = ctx._serve_route("/api/graph.json")
        self.assertEqual(code, 200)
        served = json.loads(body)
        self.assertEqual(served["nodes"], self.full["nodes"])
        self.assertEqual(served["edges"], self.full["edges"])
        keys = [_edge_key(e) for e in served["edges"]]
        self.assertEqual(keys, sorted(keys), "served edges not canonical")
        # 1a leaves the served key set alone (tests/test_research_web.py pins it).
        self.assertEqual(set(served), {"project", "summary", "nodes", "edges", "details"})

    # ── version pins ───────────────────────────────────────────────────────
    def test_schema_version_is_pinned_in_all_four_places(self):
        with open(os.path.join(REPO, "SCHEMA.md")) as fh:
            schema_l1 = fh.readline()
        with open(os.path.join(REPO, "RESEARCH_WEB.md")) as fh:
            fh.readline()
            web_l2 = fh.readline()
        m1, m2 = _SV_RX.search(schema_l1), _SV_RX.search(web_l2)
        self.assertIsNotNone(m1, "SCHEMA.md line 1 lacks <!-- schema_version: X -->")
        self.assertIsNotNone(m2, "RESEARCH_WEB.md line 2 lacks <!-- schema_version: X -->")
        self.assertEqual(m1.group(1), ctx.SCHEMA_VERSION)
        self.assertEqual(m2.group(1), ctx.SCHEMA_VERSION)
        self.assertEqual(self.full["schema_version"], ctx.SCHEMA_VERSION)
        self.assertEqual(self.ideas["schema_version"], ctx.SCHEMA_VERSION)

    def test_edge_types_count_matches_schema_5a(self):
        text = open(os.path.join(REPO, "SCHEMA.md")).read()
        start = text.index("### 5a")
        end = text.index("### 5b", start)
        rows = re.findall(r"^\| `(\w+)` \|", text[start:end], flags=re.M)
        self.assertEqual(len(ctx.EDGE_TYPES), 12)
        self.assertEqual(len(rows), 12, rows)
        self.assertEqual(set(rows), ctx.EDGE_TYPES)


if __name__ == "__main__":
    unittest.main()
