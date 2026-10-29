"""The Context Kit lifts into a repo that is not this one (seam slice 1a probe).

CONTEXT_KIT.md promises "lift it into another repo in ≈5 minutes". The in-repo
suite cannot see whether that is true — every other test runs against MONAD's own
manifest, web and source tree. This test is the second consumer: it copies exactly
the three artifacts CONTEXT_KIT.md names — `tools/ctx.py`, `tools/ui_tokens.py`,
`tools/vendor/` — into a scratch git repo with three source files and drives the
documented bootstrap: `init` (dry run writes nothing) → `init --write` → `graph --json`
(the `ctx.graph/1` contract, with ONLY code-layer kinds and no idea ids) →
`web --lint` → `health` → `graph --html` (no "d3 is not vendored" banner, which is
what proves the copy list is sufficient).

Deliberately NOT asserted (known scaffold defects, deferred to slice 1b / Stage 2):
  * the `health` score — it is >100 on a fresh repo (init puts `__init__.py` +
    `ctx.py` in an area AND the allowlist, so the coverage denominator is wrong);
  * HTML prose — the template's own banner text cites F155/F159/F188/F204 and hex
    colours like #F09595 match an F-id regex, so "no F-ids" is asserted on JSON node
    ids, never on html bytes;
  * the pre-`init` phase (`graph`/`health` before a manifest exists) — crashes until
    the spoken-absence manifest default lands in 1b;
  * rim prose from `perf`/`brief`, `context_schema.json` override, `cmd_init`
    allowlist/area overlap, manifest `integrations` block, `note.py --repo`.
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
ARTIFACTS = ("ctx.py", "ui_tokens.py", "vendor")      # the three CONTEXT_KIT.md names

TOP_KEYS = {"contract", "schema_version", "project", "nodes", "edges"}
NODE_KEYS = {"id", "kind", "title", "status"}
EDGE_KEYS = {"from", "to", "type"}
CODE_KINDS = {"module", "config", "area"}
IDEA_ID_RX = re.compile(r"^[FHED]\d+$")


class FreshRepoProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="ctxprobe_")
        root = cls.root = cls._tmp.name
        os.makedirs(os.path.join(root, "tools"))
        for name in ARTIFACTS:
            src = os.path.join(TOOLS, name)
            dst = os.path.join(root, "tools", name)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        os.makedirs(os.path.join(root, "pkg"))
        with open(os.path.join(root, "pkg", "__init__.py"), "w") as fh:
            fh.write("")
        with open(os.path.join(root, "pkg", "alpha.py"), "w") as fh:
            fh.write("import os\n\nLIMIT = 3\n\n\ndef alpha(x):\n    return os.path.basename(x)\n")
        with open(os.path.join(root, "main.py"), "w") as fh:
            fh.write("from pkg import alpha\n\n\ndef run():\n    return alpha.alpha('a/b')\n")
        git = ["git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid"]
        subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
        subprocess.run(git + ["add", "-A"], cwd=root, check=True, capture_output=True)
        subprocess.run(git + ["commit", "-q", "-m", "probe"], cwd=root, check=True,
                       capture_output=True)
        cls.ctx = os.path.join(root, "tools", "ctx.py")
        # The documented bootstrap, in order; each step's result is asserted below.
        cls.init_dry = cls._run("init")
        cls.dry_wrote = {f: os.path.exists(os.path.join(root, f))
                         for f in ("context_map.json", "RESEARCH_WEB.md")}
        cls.init_write = cls._run("init", "--write")
        cls.write_wrote = {f: os.path.exists(os.path.join(root, f))
                           for f in ("context_map.json", "RESEARCH_WEB.md")}
        cls.graph_json = cls._run("graph", "--json")
        cls.ideas_json = cls._run("graph", "--ideas-only", "--json")
        cls.lint = cls._run("web", "--lint")
        cls.health = cls._run("health")
        cls.html = cls._run("graph", "--html")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @classmethod
    def _run(cls, *args):
        env = dict(os.environ, PYTHONHASHSEED="1", PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, cls.ctx, *args], cwd=cls.root, env=env,
                              capture_output=True, text=True, timeout=300)

    def _ok(self, r, what):
        self.assertEqual(r.returncode, 0, f"{what} exited {r.returncode}:\n{r.stderr[-800:]}")

    # ── bootstrap ──────────────────────────────────────────────────────────
    def test_init_dry_run_writes_nothing(self):
        self._ok(self.init_dry, "init")
        self.assertIn("dry run", self.init_dry.stdout)
        self.assertEqual(self.dry_wrote, {"context_map.json": False, "RESEARCH_WEB.md": False})

    def test_init_write_scaffolds_both_files(self):
        self._ok(self.init_write, "init --write")
        self.assertEqual(self.write_wrote, {"context_map.json": True, "RESEARCH_WEB.md": True})
        with open(os.path.join(self.root, "context_map.json")) as fh:
            m = json.load(fh)
        self.assertIn("areas", m)
        self.assertTrue(m["areas"], "init discovered no areas")

    # ── graph --json: the ctx.graph/1 contract, code layer only ────────────
    def test_graph_json_honours_the_contract_with_only_code_kinds(self):
        self._ok(self.graph_json, "graph --json")
        d = json.loads(self.graph_json.stdout)
        self.assertEqual(set(d), TOP_KEYS)
        self.assertEqual(d["contract"], "ctx.graph/1")
        self.assertTrue(re.fullmatch(r"\d+\.\d+", d["schema_version"]), d["schema_version"])
        self.assertTrue(d["nodes"], "no nodes extracted from a 3-file repo")
        ids = {n["id"] for n in d["nodes"]}
        for n in d["nodes"]:
            self.assertEqual(set(n), NODE_KEYS, n)
            self.assertIn(n["kind"], CODE_KINDS, n)
            self.assertIsNone(IDEA_ID_RX.match(n["id"]), f"idea id in a fresh repo: {n['id']}")
        keys = [(e["from"], e["to"], e["type"]) for e in d["edges"]]
        for e in d["edges"]:
            self.assertEqual(set(e), EDGE_KEYS, e)
            self.assertIn(e["from"], ids, e)
            self.assertIn(e["to"], ids, e)
        self.assertEqual(keys, sorted(keys), "edges not canonical")
        self.assertEqual(len(keys), len(set(keys)), "duplicate edges")
        # the probe repo's own modules are what got mapped — not MONAD's
        self.assertIn("mod:main.py", ids)
        self.assertIn("mod:pkg/alpha.py", ids)
        self.assertNotIn("MONAD", self.graph_json.stdout)
        self.assertNotIn("live/", self.graph_json.stdout)

    def test_ideas_only_graph_is_empty_on_a_fresh_web(self):
        self._ok(self.ideas_json, "graph --ideas-only --json")
        d = json.loads(self.ideas_json.stdout)
        self.assertEqual(set(d), TOP_KEYS)
        self.assertEqual(d["nodes"], [])
        self.assertEqual(d["edges"], [])

    # ── the other documented steps run ─────────────────────────────────────
    def test_web_lint_runs(self):
        self._ok(self.lint, "web --lint")

    def test_health_runs(self):
        self._ok(self.health, "health")
        self.assertIn("CONTEXT HEALTH", self.health.stdout)

    def test_graph_html_renders_with_vendored_d3(self):
        self._ok(self.html, "graph --html")
        self.assertTrue(self.html.stdout.startswith("<!DOCTYPE html>"))
        self.assertNotIn("d3 is not vendored", self.html.stdout)
        self.assertNotIn("__D3_MISSING__=1", self.html.stdout)


if __name__ == "__main__":
    unittest.main()
