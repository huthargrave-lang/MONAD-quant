"""
Anti-drift tests for the agent context manifest (context_map.json).

These make the "fast layer" trustworthy: if config.py changes an invariant, or a
referenced file is moved/deleted, CI fails — so agents can rely on the manifest
instead of re-reading the codebase.
"""
import json
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "context_map.json")


def _load():
    with open(MANIFEST) as f:
        return json.load(f)


class TestManifestMatchesConfig(unittest.TestCase):
    """Invariants in the manifest must equal their config.py source of truth."""

    def setUp(self):
        import sys
        sys.path.insert(0, REPO)
        import config
        self.config = config
        self.m = _load()

    def _cfg(self, dotted):
        # "config.IBKR_PORT_PAPER" -> getattr
        return getattr(self.config, dotted.split(".", 1)[1])

    def test_invariants_match_config(self):
        inv = self.m["invariants"]
        src = self.m["invariant_sources"]
        for key, source in src.items():
            with self.subTest(invariant=key):
                self.assertEqual(
                    inv[key], self._cfg(source),
                    f"context_map.json invariant '{key}'={inv[key]} but {source}={self._cfg(source)} — update the manifest",
                )

    def test_paper_only_and_ports(self):
        # Hard safety: the manifest must assert paper-only and the live port as forbidden.
        self.assertTrue(self.m["invariants"]["paper_only"])
        self.assertEqual(self.m["invariants"]["api_port_paper"], 7497)
        self.assertEqual(self.m["invariants"]["api_port_live_forbidden"], 7496)


class TestManifestReferencesExist(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_area_files_exist(self):
        for area, spec in self.m["areas"].items():
            for f in spec["files"]:
                path = os.path.join(REPO, f)
                with self.subTest(area=area, file=f):
                    self.assertTrue(os.path.exists(path), f"manifest references missing path: {f}")

    def test_area_test_files_exist(self):
        for area, spec in self.m["areas"].items():
            for t in spec.get("tests", []):
                with self.subTest(area=area, test=t):
                    self.assertTrue(os.path.exists(os.path.join(REPO, t)), f"missing test file: {t}")

    def test_context_docs_exist(self):
        """Every doc the manifest points agents at must exist (a rename otherwise
        silently sends the router to a dead file)."""
        for group, docs in self.m["context_docs"].items():
            for d in docs:
                with self.subTest(group=group, doc=d):
                    self.assertTrue(os.path.exists(os.path.join(REPO, d)),
                                    f"context_docs path missing: {d}")

    def test_routing_read_paths_exist(self):
        """Routing 'read' targets that are file paths must exist. Skips non-path
        hints (ctx commands, '(section)' notes, TICKER placeholders)."""
        for r in self.m["routing"]:
            for entry in r["read"]:
                tok = entry.split()[0].split("::")[0]  # first token, drop ::symbol
                is_path = ("/" in tok) or tok.endswith((".md", ".py", ".json", ".html"))
                if not is_path:
                    continue
                with self.subTest(read=entry):
                    self.assertTrue(os.path.exists(os.path.join(REPO, tok)),
                                    f"routing read path missing: {tok}")

    def test_referenced_ctx_subcommands_are_registered(self):
        """Every 'ctx <sub>' advertised in tools_readonly must be a real subcommand
        in tools/ctx.py — so the manifest can't send agents to a command that errors."""
        import re
        with open(os.path.join(REPO, "tools", "ctx.py")) as f:
            registered = set(re.findall(r'add_parser\("(\w+)"\)', f.read()))
        for t in self.m["tools_readonly"]:
            m = re.match(r"ctx (\w+)", t["cmd"])
            if m:
                with self.subTest(cmd=t["cmd"]):
                    self.assertIn(m.group(1), registered,
                                  f"tools_readonly advertises 'ctx {m.group(1)}' but it's not registered")

    def test_area_entrypoints_resolve(self):
        """Each area entrypoint must resolve: a bare path must exist, and a
        'file::symbol' must have that symbol actually defined in the file. This
        is what lets agents trust `ctx map` entrypoints — a rename that doesn't
        update the manifest fails here."""
        import re
        for area, spec in self.m["areas"].items():
            for ep in spec.get("entrypoints", []):
                with self.subTest(area=area, entrypoint=ep):
                    if "::" in ep:
                        path, sym = ep.split("::", 1)
                        full = os.path.join(REPO, path)
                        self.assertTrue(os.path.exists(full), f"entrypoint file missing: {path}")
                        with open(full, errors="ignore") as fh:
                            src = fh.read()
                        pat = re.compile(
                            rf"^\s*(def|class)\s+{re.escape(sym)}\b|^\s*{re.escape(sym)}\s*=", re.M)
                        self.assertRegex(src, pat, f"entrypoint '{sym}' not defined in {path}")
                    else:
                        self.assertTrue(os.path.exists(os.path.join(REPO, ep)),
                                        f"entrypoint path missing: {ep}")

    def test_routing_shape(self):
        for r in self.m["routing"]:
            for k in ("keywords", "read", "run", "avoid"):
                self.assertIn(k, r)
            self.assertTrue(r["keywords"], "routing entry has no keywords")


if __name__ == "__main__":
    unittest.main()
