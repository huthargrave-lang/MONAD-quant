"""examples/minimal-research-web is a worked, NON-finance Context Kit web that the kit's
own commands accept as-is (seam slice 1b).

The in-repo suite proves the kit on MONAD's web; tests/test_ctx_fresh_repo.py proves the
bootstrap on a synthetic code-only repo. This file proves the third thing CONTEXT_KIT.md
promises: a small research web written by someone else, about something else (a software
benchmarking question: does link-time optimisation cut request latency?), is accepted by
`init` / `web --lint` / `health` / `graph --json` / `why`, with the `ctx.graph/1` contract
holding and a supersession-with-reason (F1 → F3, `data-fixed`) explained by `why`.

Everything runs through `ctx --repo examples/minimal-research-web`, so nothing is copied
and MONAD's own manifest and web are never read.

The example holds NO `.py` files, on purpose: `ctx._first_party_modules` walks the whole
repo and tests/test_area_coverage.py requires every first-party module to be owned by a
context_map.json area, so a Python file under examples/ would be an orphan the moment it
landed. The example therefore exercises the idea layer only; `health`'s code-coverage term
is 0 there by construction (asserted, not hidden).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
sys.path.insert(0, TOOLS)
import ctx  # noqa: E402

CTX = os.path.join(TOOLS, "ctx.py")
EX = os.path.join(REPO, "examples", "minimal-research-web")
NODE_IDS = {"F1", "F2", "F3", "H1", "E1", "E2", "D1"}
TOP_KEYS = {"contract", "schema_version", "project", "nodes", "edges"}


def _run(*args, repo=EX):
    env = dict(os.environ, PYTHONHASHSEED="1", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, CTX, "--repo", repo, *args], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=300)


class MinimalWebExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.init_dry = _run("init")
        cls.lint = _run("web", "--lint")
        cls.health = _run("health")
        cls.graph_json = _run("graph", "--json")
        cls.ideas_json = _run("graph", "--ideas-only", "--json")
        cls.why_f1 = _run("why", "F1")
        cls.why_d1 = _run("why", "D1")
        cls.why_h1 = _run("why", "H1")
        cls.pending = _run("web", "--pending")
        cls.html = _run("graph", "--html")

    def _ok(self, r, what):
        self.assertEqual(r.returncode, 0, f"{what} exited {r.returncode}:\n{r.stderr[-800:]}")
        self.assertNotIn("no context_map.json", r.stderr, "the example must be scaffolded")

    # ── shape of the example ───────────────────────────────────────────────
    def test_the_example_holds_no_python_files(self):
        py = [os.path.join(d, f) for d, _, fs in os.walk(EX) for f in fs if f.endswith(".py")]
        self.assertEqual(py, [], "a .py under examples/ would be an area-coverage orphan")
        for f in ("README.md", "RESEARCH_WEB.md", "context_map.json", "map.html"):
            self.assertTrue(os.path.exists(os.path.join(EX, f)), f)

    def test_the_web_header_pins_the_schema_version(self):
        with open(os.path.join(EX, "RESEARCH_WEB.md")) as fh:
            fh.readline()
            line2 = fh.readline().strip()
        self.assertEqual(line2, f"<!-- schema_version: {ctx.SCHEMA_VERSION} -->")

    def test_the_manifest_is_exactly_what_init_write_produces(self):
        with tempfile.TemporaryDirectory(prefix="exgen_") as tmp:
            root = os.path.join(tmp, "minimal-research-web")    # basename = project name
            os.makedirs(root)
            shutil.copy2(os.path.join(EX, "RESEARCH_WEB.md"), root)
            r = _run("init", "--write", repo=root)
            self.assertEqual(r.returncode, 0, r.stderr[-800:])
            self.assertIn("WROTE context_map.json", r.stdout)
            self.assertIn("SKIP RESEARCH_WEB.md", r.stdout)
            with open(os.path.join(root, "context_map.json")) as fh:
                generated = json.load(fh)
        with open(os.path.join(EX, "context_map.json")) as fh:
            committed = json.load(fh)
        self.assertEqual(generated, committed, "examples/minimal-research-web/context_map.json "
                         "is no longer the verbatim `ctx init --write` output")
        self.assertEqual(committed["project"], "minimal-research-web")
        self.assertEqual(committed["areas"], {})

    def test_init_dry_run_writes_nothing(self):
        self._ok(self.init_dry, "init")
        self.assertIn("dry run", self.init_dry.stdout)

    # ── the commands accept it ─────────────────────────────────────────────
    def test_lint_is_clean(self):
        self._ok(self.lint, "web --lint")
        self.assertIn("7 nodes | 1 superseded | 0 problem(s) | 0 advisory", self.lint.stdout)

    def test_health_scores_the_idea_layer(self):
        self._ok(self.health, "health")
        self.assertIn("CONTEXT HEALTH", self.health.stdout)
        self.assertNotIn("UNSCAFFOLDED", self.health.stdout)
        self.assertIn("7 nodes (1 superseded)", self.health.stdout)
        self.assertIn("0 dangling", self.health.stdout)
        self.assertIn("0 orphan idea node(s)", self.health.stdout)
        # no code by design → the coverage term is 0/0, said plainly
        self.assertIn("code coverage : 0/0", self.health.stdout)

    def test_graph_json_honours_the_contract(self):
        self._ok(self.graph_json, "graph --json")
        d = json.loads(self.graph_json.stdout)
        self.assertEqual(set(d), TOP_KEYS)
        self.assertEqual(d["contract"], "ctx.graph/1")
        self.assertEqual(d["schema_version"], ctx.SCHEMA_VERSION)
        self.assertEqual(d["project"], "minimal-research-web")
        self.assertEqual({n["id"] for n in d["nodes"]}, NODE_IDS)
        for n in d["nodes"]:
            self.assertEqual(set(n), {"id", "kind", "title", "status"})
            self.assertEqual(n["kind"], n["id"][0])
            self.assertIn(n["kind"], ctx.SCHEMA["kinds"])
            self.assertTrue(ctx.ID_RX.match(n["id"]))
            self.assertEqual(n["status"], "superseded" if n["id"] == "F1" else "current", n)
        keys = [(e["from"], e["to"], e["type"]) for e in d["edges"]]
        self.assertEqual(keys, sorted(keys), "edges not canonical")
        self.assertEqual(len(keys), len(set(keys)))
        for e in d["edges"]:
            self.assertIn(e["type"], ctx.EDGE_TYPES, e)
            self.assertIn(e["from"], NODE_IDS)
            self.assertIn(e["to"], NODE_IDS)
        self.assertIn(("F3", "F1", "supersedes"), keys)
        self.assertIn(("F1", "E1", "evidenced_by"), keys)
        self.assertIn(("D1", "H1", "resolves"), keys)
        self.assertIn(("F3", "H1", "resolves"), keys)
        # no code layer and no bridges → the full map IS the idea map
        self._ok(self.ideas_json, "graph --ideas-only --json")
        self.assertEqual(json.loads(self.ideas_json.stdout), d)

    def test_why_explains_the_supersession_and_the_provenance(self):
        self._ok(self.why_f1, "why F1")
        self.assertIn("SUPERSEDED by F3 (data-fixed)", self.why_f1.stdout)
        self.assertIn("F1 → evidenced_by:E1", self.why_f1.stdout)
        self._ok(self.why_d1, "why D1")
        self.assertIn("D1 → relies_on:F2 → evidenced_by:E2", self.why_d1.stdout)
        self.assertNotIn("FRAGILE", self.why_d1.stdout)
        self._ok(self.why_h1, "why H1")
        self.assertIn("H1 → drives:E2", self.why_h1.stdout)

    def test_the_hypothesis_is_closed_not_pending(self):
        self._ok(self.pending, "web --pending")
        self.assertNotIn("H1", self.pending.stdout)

    def test_html_renders_with_the_vendored_d3(self):
        self._ok(self.html, "graph --html")
        self.assertTrue(self.html.stdout.startswith("<!DOCTYPE html>"))
        self.assertNotIn("d3 is not vendored", self.html.stdout)
        self.assertIn("minimal-research-web", self.html.stdout)
        committed = open(os.path.join(EX, "map.html"), encoding="utf-8").read()
        self.assertTrue(committed.startswith("<!DOCTYPE html>"))
        self.assertIn("minimal-research-web", committed)
        for nid in sorted(NODE_IDS):
            self.assertIn(f'"{nid}"', committed, f"committed map.html lacks node {nid}")

    def test_readme_is_the_five_minute_tutorial(self):
        text = open(os.path.join(EX, "README.md"), encoding="utf-8").read()
        self.assertIn("5 minutes", text)
        for needle in ("--repo", "init --write", "web --lint", "health", "graph --html",
                       "why F1", "tools/ctx.py", "tools/ui_tokens.py", "tools/vendor/",
                       "data-fixed", "no `.py`"):
            self.assertIn(needle, text, needle)


if __name__ == "__main__":
    unittest.main()
