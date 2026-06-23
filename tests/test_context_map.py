"""
Anti-drift tests for the agent context manifest (context_map.json).

These make the "fast layer" trustworthy: if config.py changes an invariant, or a
referenced file is moved/deleted, CI fails — so agents can rely on the manifest
instead of re-reading the codebase.
"""
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "context_map.json")
sys.path.insert(0, os.path.join(REPO, "tools"))
import ctx  # noqa: E402  (reuse the route scorer + manifest reader)


def _route_output(query):
    import contextlib
    import io
    import types
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ctx.cmd_route(types.SimpleNamespace(task=query.split()))
    return buf.getvalue().lower()


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

    def test_deploy_branch_matches_preflight_gate(self):
        # The manifest's deploy_branch is the FIRST line `ctx brief` prints as the
        # orientation packet. It must equal the branch the live preflight gate actually
        # enforces (ops/preflight_trader_start.sh: EXPECT_BRANCH=...), or `ctx brief`
        # confidently lies about where the bot runs. Value-vs-value, no guesswork.
        import re
        pf = os.path.join(REPO, "ops", "preflight_trader_start.sh")
        with open(pf) as f:
            mm = re.search(r'^EXPECT_BRANCH="([^"]+)"', f.read(), re.M)
        self.assertIsNotNone(mm, "could not find EXPECT_BRANCH in preflight_trader_start.sh")
        self.assertEqual(
            self.m["deploy_branch"], mm.group(1),
            f"context_map.json deploy_branch='{self.m['deploy_branch']}' but the preflight gate "
            f"enforces EXPECT_BRANCH='{mm.group(1)}' — `ctx brief` would lie about the deploy branch",
        )

    def test_paper_only_and_ports(self):
        # Hard safety: the manifest must assert paper-only and the live port as forbidden.
        self.assertTrue(self.m["invariants"]["paper_only"])
        self.assertEqual(self.m["invariants"]["api_port_paper"], 7497)
        self.assertEqual(self.m["invariants"]["api_port_live_forbidden"], 7496)


class TestParamClaims(unittest.TestCase):
    """Context Web v2 #4 — drift-prone strategy params bound to their config.py
    source of truth (generalizes invariant_sources), plus doc-prose drift."""

    # Accepted, baselined doc drift: (doc, KEY, stated_value). Add an entry here
    # only when a doc deliberately states a historical/illustrative param value that
    # differs from config and rewriting the prose is a judgment call. The test
    # self-cleans: once a doc is reconciled, the matching baseline entry must be
    # removed (a stale baseline fails the test). Currently empty — the prior
    # MAX_TRADE_BARS=20 drift in CLAUDE.md §6 was reconciled to point at config.py:71.
    KNOWN_DOC_PARAM_DRIFT = set()

    def setUp(self):
        sys.path.insert(0, REPO)
        import config
        self.config = config
        self.m = _load()
        self.claims = self.m["param_claims"]["claims"]

    def test_param_claim_sources_resolve(self):
        """No dangling binding: every claim points at a real config attribute."""
        for c in self.claims:
            with self.subTest(key=c["key"]):
                self.assertTrue(c["source"].startswith("config."),
                                f"{c['key']} source must be a config.KEY, got {c['source']}")
                attr = c["source"].split(".", 1)[1]
                self.assertTrue(hasattr(self.config, attr),
                                f"param_claim '{c['key']}' binds to {c['source']} which doesn't exist")

    def test_param_claim_values_match_config(self):
        """The recorded value must equal the live config value (the anti-drift core)."""
        for c in self.claims:
            with self.subTest(key=c["key"]):
                live = getattr(self.config, c["source"].split(".", 1)[1])
                if isinstance(live, float) or isinstance(c["value"], float):
                    self.assertAlmostEqual(
                        c["value"], live, places=6,
                        msg=f"param_claim '{c['key']}'={c['value']} but {c['source']}={live} — update the manifest")
                else:
                    self.assertEqual(
                        c["value"], live,
                        f"param_claim '{c['key']}'={c['value']} but {c['source']}={live} — update the manifest")

    def test_param_claim_keys_unique(self):
        keys = [c["key"] for c in self.claims]
        self.assertEqual(len(keys), len(set(keys)), f"duplicate param_claim keys: {keys}")

    def test_doc_param_mentions_match_config(self):
        """Any explicit `KEY = value` of a bound param in CLAUDE.md/AGENTS.md must
        match config — catches prose drift. Known-stale mentions are baselined."""
        import re
        bound = {c["source"].split(".", 1)[1] for c in self.claims}
        drift = set()
        # docs/history/MODEL_HISTORY.md carries live `KEY = value` snapshots too;
        # the guard would otherwise miss drift there (review finding #6).
        for doc in ("CLAUDE.md", "AGENTS.md", os.path.join("docs", "history", "MODEL_HISTORY.md")):
            p = os.path.join(REPO, doc)
            if not os.path.exists(p):
                continue
            text = open(p, errors="ignore").read()
            for key in bound:
                rx = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(key) + r"\s*=\s*(-?\d+\.?\d*)")
                for mm in rx.finditer(text):
                    live = getattr(self.config, key)
                    if abs(float(mm.group(1)) - float(live)) > 1e-9:
                        drift.add((doc, key, mm.group(1)))
        new = drift - self.KNOWN_DOC_PARAM_DRIFT
        self.assertEqual(
            new, set(),
            "doc params disagree with config (prose drift): "
            + "; ".join(f"{d} says {k}={v} but config={getattr(self.config, k)}"
                        for d, k, v in sorted(new)))
        stale = self.KNOWN_DOC_PARAM_DRIFT - drift
        self.assertEqual(
            stale, set(),
            f"baselined doc drift no longer present (good — the doc was fixed; "
            f"remove it from KNOWN_DOC_PARAM_DRIFT): {stale}")


class TestGraphBridges(unittest.TestCase):
    """Context Web v2 #5 — idea↔code bridges must point at real nodes and real
    code, so the connective tissue can't silently rot (mirrors entrypoint checks)."""

    REL_VOCAB = {"concerns", "implemented_in", "measured_by", "gated_by"}

    def setUp(self):
        sys.path.insert(0, REPO)
        import config
        self.config = config
        self.m = _load()
        self.bridges = self.m["graph_bridges"]["bridges"]
        import ctx
        self.nodes = ctx._parse_web()[0]

    def test_bridge_nodes_exist(self):
        for b in self.bridges:
            with self.subTest(node=b["node"]):
                self.assertIn(b["node"], self.nodes, f"bridge node {b['node']} not in RESEARCH_WEB.md")

    def test_bridge_relations_in_vocab(self):
        for b in self.bridges:
            with self.subTest(node=b["node"]):
                self.assertIn(b["relation"], self.REL_VOCAB, f"unknown relation {b['relation']!r}")

    def test_bridge_code_targets_resolve(self):
        import re
        for b in self.bridges:
            for code in b["code"]:
                with self.subTest(node=b["node"], code=code):
                    if code.startswith("config."):
                        self.assertTrue(hasattr(self.config, code.split(".", 1)[1]),
                                        f"bridge {code} not a config attribute")
                    elif "::" in code:
                        path, sym = code.split("::", 1)
                        full = os.path.join(REPO, path)
                        self.assertTrue(os.path.exists(full), f"bridge file missing: {path}")
                        with open(full, errors="ignore") as fh:
                            src = fh.read()
                        self.assertRegex(
                            src, re.compile(rf"^\s*(def|class)\s+{re.escape(sym)}\b|^\s*{re.escape(sym)}\s*=", re.M),
                            f"bridge symbol '{sym}' not defined in {path}")
                    else:
                        self.assertTrue(os.path.exists(os.path.join(REPO, code)), f"bridge path missing: {code}")


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

    def test_agent_index_lists_every_subcommand(self):
        """The L0 router (AGENT_INDEX.md Step 1) must mention every registered ctx
        subcommand, so an agent reading only the index never misses a tool. Night
        review R4 P1-2 found brief/impact/usages/defs/can_edit/events/reverts were
        shipped but unlisted — this guard stops that recurring."""
        import re
        with open(os.path.join(REPO, "tools", "ctx.py")) as f:
            registered = set(re.findall(r'add_parser\("(\w+)"\)', f.read()))
        with open(os.path.join(REPO, "AGENT_INDEX.md")) as f:
            cited = set(re.findall(r"ctx\.py (\w+)", f.read()))
        missing = registered - cited
        self.assertFalse(missing, f"AGENT_INDEX.md Step 1 omits ctx subcommands: {sorted(missing)}")

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

    def test_routing_synonyms_resolve_to_real_keywords(self):
        """Every synonym target must be a real routing keyword (anti-drift)."""
        kws = {k for r in self.m["routing"] for k in r["keywords"]}
        for concept, targets in self.m.get("routing_synonyms", {}).items():
            if concept.startswith("_"):
                continue
            for t in targets:
                with self.subTest(concept=concept, target=t):
                    self.assertIn(t, kws, f"synonym '{concept}'→'{t}' is not a routing keyword")


class TestRouteRobustness(unittest.TestCase):
    """Golden natural-language queries route sensibly (locks in the matcher fix)."""

    GOLDEN = [
        ("where is position sizing decided", ["strategy", "sizing", "kelly"]),
        ("how big should each trade be", ["kelly", "sizing", "strategy"]),
        ("what happens on a software stop", ["trader", "exit", "strategy"]),
        ("how do I add a new ticker", ["sweep", "backtest"]),
        ("is the edge real", ["perf", "edge", "research_web"]),
    ]

    def test_golden_queries_match(self):
        for q, expect_any in self.GOLDEN:
            out = _route_output(q)
            with self.subTest(query=q):
                self.assertNotIn("no routing match", out, f"'{q}' got no route")
                self.assertNotIn("no exact route", out, f"'{q}' got no route")
                self.assertTrue(any(e in out for e in expect_any), f"'{q}' → {out[:140]}")

    def test_stop_question_not_misrouted_to_ops(self):
        # The classic substring bug: 'stops' contains 'ops' → was routed to ops/systemd.
        self.assertNotIn("ops/systemd", _route_output("what stops a bad trade from losing too much"))


class TestEditPolicy(unittest.TestCase):
    """The safe-write fence: every do_not_touch file must be denied, and the gate
    must allow ordinary offline code."""

    def setUp(self):
        with open(MANIFEST) as f:
            self.m = json.load(f)
        self.deny = self.m["edit_policy"]["deny"]

    def test_do_not_touch_files_are_denied(self):
        for area, spec in self.m["areas"].items():
            if spec.get("do_not_touch_without_approval"):
                for f in spec["files"]:
                    with self.subTest(area=area, file=f):
                        self.assertIsNotNone(ctx.policy_match(f, self.deny),
                                             f"do_not_touch file {f} not covered by an edit_policy deny glob")

    def test_safety_critical_paths_denied(self):
        for f in ["live/trader.py", "config.py", "config_modules/live.py",
                  ".env", "live/state.db"]:
            with self.subTest(file=f):
                self.assertIsNotNone(ctx.policy_match(f, self.deny), f"{f} should be deny-listed")

    def test_offline_code_is_allowed(self):
        for f in ["src/backtest/runner.py", "tools/ctx.py", "tests/test_signals.py",
                  "src/optimization/sweep_scoring.py"]:
            with self.subTest(file=f):
                self.assertIsNone(ctx.policy_match(f, self.deny), f"{f} should be freely editable")

    def test_impact_flags_live_boundary(self):
        # fetcher is imported transitively by the trader — impact must reach 'live'.
        importers, _ = ctx._import_graph()
        affected = set()
        queue = ["src.data.fetcher"]
        while queue:
            for imp in importers.get(queue.pop(), ()):
                if imp not in affected:
                    affected.add(imp); queue.append(imp)
        self.assertTrue(any(a.startswith("live.") for a in affected),
                        "ctx impact should detect that editing src/data/fetcher.py reaches live/")


class TestCtxFind(unittest.TestCase):
    """`ctx find` — free-text code-body search returns the hit's enclosing symbol
    (and owning area / governing bridge), so a behavioral query stays in the kit."""

    def _find(self, *query):
        import contextlib, io, types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_find(types.SimpleNamespace(query=list(query)))
        return buf.getvalue()

    def test_finds_behavior_with_enclosing_symbol(self):
        # 'worst_case_ambiguity' is used inside compute_trade_returns in engine.py
        out = self._find("worst_case_ambiguity")
        self.assertIn("src/strategy/engine.py", out)
        self.assertIn("[compute_trade_returns]", out)

    def test_excludes_tests_dir(self):
        # first-party search must not return matches from tests/ (avoids self-noise)
        out = self._find("worst_case_ambiguity")
        self.assertNotIn("tests/", out)

    def test_short_query_rejected(self):
        self.assertIn("too short", self._find("ab"))

    def test_no_match_is_graceful(self):
        self.assertIn("no first-party code matches", self._find("zzq_nonexistent_token_qzx"))


class TestEpistemicCoverage(unittest.TestCase):
    """`ctx claims` — an implemented_in finding's guarded_by must point at a real
    test (file::symbol), so a renamed/deleted guard test is caught, not silently
    treated as 'guarded'."""

    def setUp(self):
        self.m = _load()
        self.bridges = [b for b in self.m["graph_bridges"]["bridges"]
                        if b.get("relation") == "implemented_in"]

    def test_guarded_by_targets_resolve(self):
        for b in self.bridges:
            for g in b.get("guarded_by", []):
                with self.subTest(node=b["node"], guard=g):
                    self.assertTrue(
                        ctx._claim_guard_resolves(g),
                        f"{b['node']} guarded_by {g!r} does not resolve to a real test file::symbol")

    def test_claims_command_runs_and_classifies(self):
        import contextlib, io, types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_claims(types.SimpleNamespace())
        out = buf.getvalue()
        self.assertIn("implemented_in claim", out)
        self.assertIn("GUARDED", out, "F11's penalty-inversion claim should resolve as guarded")


if __name__ == "__main__":
    unittest.main()
