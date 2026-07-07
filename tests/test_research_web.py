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
    return _in_synthetic_web(text, ctx._parse_web)


def _in_synthetic_web(text, fn):
    """Run fn() with ctx.WEB temporarily repointed at synthetic web markdown."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
        tf.write(text)
        name = tf.name
    old = ctx.WEB
    try:
        ctx.WEB = name
        return fn()
    finally:
        ctx.WEB = old
        os.unlink(name)


# A minimal contradicted-but-current web: F91 (later, current) contradicts F90 (still
# current, NOT superseded), and D90 relies on F90. The live corpus intentionally no
# longer contains such a node — D7 resolved the one real example (F15 contradicted by
# F22) by formal supersession — so the DISPUTED/advisory features are pinned here on a
# synthetic fixture instead of on live-corpus state.
DISPUTED_WEB = """\
### F90 — old claim: the edge is real
The edge is real at some timescale. Links: [[E90|evidenced_by]].

### F91 — newer rigorous result overturns the framing
Directly disputes the old claim ([[F90|contradicts]]). Links: [[E90|evidenced_by]].

### E90 — the deciding experiment
Ran the honest benchmark.

### D90 — decision leaning on the disputed claim
Still cites [[F90|relates]].
"""


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


class TestSupersessionPropagation(unittest.TestCase):
    """Context Web v2 — supersession propagation: a CURRENT node that `relates` to a
    superseded node must ALSO cite that node's superseder, so `ctx why <node>` can't
    hand an agent a claim standing on retracted evidence (the live failure: D1 cited
    F3/F4/F8 after F13 reversed them, never citing F13). See ctx._propagation_violations."""

    @classmethod
    def setUpClass(cls):
        cls.nodes, _ = ctx._parse_web()

    def test_web_has_no_propagation_violations(self):
        v = ctx._propagation_violations(self.nodes)
        self.assertEqual(
            v, [],
            "live nodes cite a superseded node without its superseder — cite the "
            "superseder alongside it: "
            + "; ".join(f"{nid}->{tgt} (missing {sup})" for nid, tgt, sup in v))

    def test_guard_fires_on_synthetic_violation(self):
        # The guard must actually catch the failure, not silently pass (adversarial).
        nodes, _ = _parse_web_text(
            "### F1 — old\n<!-- status: superseded; by: F2; reason: reversed -->\nx\n"
            "### F2 — new\nthe replacement\n"
            "### D1 — a live decision\nstill points at [[F1]] and never mentions the reversal.\n")
        self.assertIn(("D1", "F1", "F2"), ctx._propagation_violations(nodes),
                      "guard missed a live node citing superseded F1 without superseder F2")

    def test_citing_the_superseder_clears_it(self):
        nodes, _ = _parse_web_text(
            "### F1 — old\n<!-- status: superseded; by: F2; reason: reversed -->\nx\n"
            "### F2 — new\nthe replacement\n"
            "### D1 — a live decision\nnotes [[F1]] but now follows [[F2]].\n")
        self.assertEqual(ctx._propagation_violations(nodes), [],
                         "citing both the superseded node and its superseder must clear it")

    def test_dependency_via_lineage_cue_is_caught(self):
        # "based on" (derived_from) / "motivated by" (drives) express a current
        # dependency; a superseded target must NOT escape the guard via the cue
        # classifier (regression: adversarial-review finding — relates-only was too narrow).
        for cue in ("based on", "Motivated by"):
            nodes, _ = _parse_web_text(
                "### F1 — old\n<!-- status: superseded; by: F2; reason: reversed -->\nx\n"
                "### F2 — new\nthe replacement\n"
                f"### D1 — a live decision\n{cue} [[F1]] and never mentions the reversal.\n")
            with self.subTest(cue=cue):
                self.assertIn(("D1", "F1", "F2"), ctx._propagation_violations(nodes),
                              f"dependency cue {cue!r} to a superseded node escaped the guard")

    def test_historical_upstream_edge_is_exempt(self):
        # an experiment that PRODUCED a now-superseded finding is history, not a
        # dependency on retracted evidence — must stay exempt (no false positive).
        nodes, _ = _parse_web_text(
            "### F1 — old\n<!-- status: superseded; by: F2; reason: reversed -->\nx\n"
            "### F2 — new\nthe replacement\n"
            "### E1 — an experiment\nproduced [[F1]].\n")
        self.assertEqual(ctx._propagation_violations(nodes), [],
                         "a 'produces' (upstream) edge to a superseded node must stay exempt")

    def test_superseded_source_is_exempt(self):
        # A superseded node may freely reference history (incl. other superseded nodes).
        nodes, _ = _parse_web_text(
            "### F1 — old\n<!-- status: superseded; by: F2; reason: reversed -->\nx\n"
            "### F2 — new\nthe replacement\n"
            "### F0 — also old\n<!-- status: superseded; by: F2; reason: reversed -->\nrefers to [[F1]].\n")
        self.assertEqual(ctx._propagation_violations(nodes), [],
                         "a superseded source node must not be flagged for citing history")


class TestEffectiveConfidence(unittest.TestCase):
    """ctx._effective_conf — a node is only as strong as the weakest stated conf in
    its reliance chain (min-propagation); non-reliance edges don't drag it down."""

    def test_min_over_reliance_chain_with_bottleneck(self):
        nodes = {
            "F1": {"title": "a", "body": "<!-- status: current; conf: 0.9 -->"},
            "F2": {"title": "b", "body": "<!-- status: current; conf: 0.3 -->"},
            "F3": {"title": "c", "body": "<!-- status: current; conf: 0.8 -->"},
        }
        adj = {
            "F1": [{"to": "F2", "type": "relies_on", "dir": "out"},
                   {"to": "F3", "type": "relates", "dir": "out"}],  # relates ≠ reliance
            "F2": [], "F3": [],
        }
        eff, bott = ctx._effective_conf("F1", nodes, adj)
        self.assertAlmostEqual(eff, 0.3)
        self.assertEqual(bott, "F2", "weakest reliance link should be the bottleneck")

    def test_relates_edge_does_not_drag_confidence(self):
        # F3 (0.8) is reached only via `relates`, so it must NOT be the bottleneck.
        nodes = {
            "F1": {"title": "a", "body": "<!-- status: current; conf: 0.9 -->"},
            "F3": {"title": "c", "body": "<!-- status: current; conf: 0.1 -->"},
        }
        adj = {"F1": [{"to": "F3", "type": "relates", "dir": "out"}], "F3": []}
        eff, bott = ctx._effective_conf("F1", nodes, adj)
        self.assertAlmostEqual(eff, 0.9)
        self.assertEqual(bott, "F1", "a relates-only neighbour must not lower effective confidence")

    def test_no_conf_anywhere_returns_none(self):
        nodes = {"F1": {"title": "a", "body": "no meta"}}
        self.assertEqual(ctx._effective_conf("F1", nodes, {"F1": []}), (None, None))

    def test_tied_minimum_is_deterministic(self):
        # Candidates come from a set, so a naive min() flaps with PYTHONHASHSEED on a
        # tie. The bottleneck must be stable AND, on a tie, prefer the node itself.
        nodes = {
            "F1": {"title": "a", "body": "<!-- status: current; conf: 0.2 -->"},
            "F2": {"title": "b", "body": "<!-- status: current; conf: 0.2 -->"},
        }
        adj = {"F1": [{"to": "F2", "type": "relies_on", "dir": "out"}], "F2": []}
        eff, bott = ctx._effective_conf("F1", nodes, adj)
        self.assertAlmostEqual(eff, 0.2)
        self.assertEqual(bott, "F1", "on a tied minimum, the root node is the reported bottleneck")


class TestWebListingViews(unittest.TestCase):
    """cmd_web listing: --pending (open work) + tombstoned superseded nodes."""

    def _web(self, **kw):
        import contextlib, io, types
        ns = types.SimpleNamespace(node=None, live=False, lint=False, pending=False)
        for k, v in kw.items():
            setattr(ns, k, v)
        buf = io.StringIO()
        self.exit_code = 0
        with contextlib.redirect_stdout(buf):
            try:
                ctx.cmd_web(ns)
            except SystemExit as e:                       # --lint now exits non-zero (SF-2)
                self.exit_code = e.code if isinstance(e.code, int) else 1
        return buf.getvalue()

    def test_pending_lists_open_and_decisions_excludes_superseded(self):
        out = self._web(pending=True)
        for nid in ("D1", "H4", "E7"):
            self.assertIn(nid, out, f"{nid} should appear in --pending")
        self.assertNotIn("F3 ", out, "superseded F3 must not appear in --pending")

    def test_superseded_tombstoned_in_full_listing(self):
        out = self._web()
        self.assertIn("[SUPERSEDED → F13]", out, "superseded nodes should be tombstoned in the listing")

    def test_live_view_hides_superseded_entirely(self):
        out = self._web(live=True)
        self.assertNotIn("[SUPERSEDED", out, "--live must hide superseded nodes, not tombstone them")

    def test_lint_advises_reliance_on_contradicted_node(self):
        # A live node relying on a contradicted (but still current) node → advisory,
        # not a hard problem. Synthetic fixture: the live example this used to pin
        # (D1/D4 → F15, contradicted by F22) was resolved by D7 — F15 is now formally
        # superseded, so the live web has no contradicted-but-current node by design.
        out = _in_synthetic_web(DISPUTED_WEB, lambda: self._web(lint=True))
        self.assertIn("contradicted by F91", out)

    def test_lint_exit_code_matches_summary(self):
        # SF-2: web --lint must encode integrity in its exit code, not always return 0.
        # 2 = hard problem (dangling/stale-cite), 1 = disputed-but-live advisory, 0 = clean.
        import re
        out = self._web(lint=True)
        m = re.search(r"(\d+) problem\(s\) \| (\d+) advisory", out)
        self.assertIsNotNone(m, out)
        problems, advisories = int(m.group(1)), int(m.group(2))
        expected = 2 if problems else (1 if advisories else 0)
        self.assertEqual(self.exit_code, expected,
                         f"exit {self.exit_code} != expected {expected} for "
                         f"{problems} problem(s)/{advisories} advisory")


class TestBannerRider(unittest.TestCase):
    """_web_banner appends an [Auto] rider of computed facts to the hand-written banner."""

    def test_banner_has_auto_rider(self):
        b = ctx._web_banner()
        self.assertIn("[Auto]", b)
        self.assertRegex(b, r"\[Auto\] \d+ nodes, \d+ superseded")


class TestCtxDelta(unittest.TestCase):
    """ctx delta + the _parse_web / _parse_web_text refactor invariant."""

    def test_parse_web_text_matches_file_parse(self):
        with open(ctx.WEB) as f:
            txt = f.read()
        a_nodes, a_rev = ctx._parse_web()
        b_nodes, b_rev = ctx._parse_web_text(txt)
        self.assertEqual(set(a_nodes), set(b_nodes))
        self.assertEqual(a_rev, b_rev)
        for nid in a_nodes:
            self.assertEqual(a_nodes[nid]["edges"], b_nodes[nid]["edges"])

    def test_delta_runs_and_reports_base(self):
        import contextlib, io, types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_delta(types.SimpleNamespace(since=None))
        out = buf.getvalue()
        self.assertIn("ctx delta", out)
        self.assertIn("base", out)

    def test_delta_since_revision_uses_that_revision(self):
        # Regression: git --before (approxidate) silently coerced 'HEAD~3' into a
        # bogus date; the base must be the actual HEAD~3 commit.
        import contextlib, io, types, subprocess
        full = subprocess.run(["git", "rev-parse", "HEAD~3"], cwd=ctx.REPO,
                              capture_output=True, text=True).stdout.strip()
        if not full:
            self.skipTest("not enough git history")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_delta(types.SimpleNamespace(since="HEAD~3"))
        self.assertIn(full[:9], buf.getvalue(),
                      "delta --since HEAD~3 must use HEAD~3 as the base, not an approxidate guess")

    def test_delta_since_garbage_errors_not_silent(self):
        # SF-1 regression: git --before coerces an unparseable --since to "now" and returns
        # HEAD, so delta would print "(no changes)" against the wrong base. A garbage
        # revision must error loudly (exit 1), never a silent false-negative.
        import contextlib, io, types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as cm:
                ctx.cmd_delta(types.SimpleNamespace(since="not-a-real-rev-xyz"))
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("not a valid revision", buf.getvalue())


class TestContradictedNodeLint(unittest.TestCase):
    def test_contradicted_by_maps_current_disputes(self):
        nodes = {
            "F1": {"title": "a", "body": "", "links": ["F2"], "edges": [{"target": "F2", "type": "contradicts"}]},
            "F2": {"title": "b", "body": "", "links": [], "edges": []},
        }
        self.assertEqual(ctx._contradicted_by(nodes), {"F2": ["F1"]})

    def test_superseded_contradictor_does_not_count(self):
        nodes = {
            "F1": {"title": "a", "body": "<!-- status: superseded; by: F9; reason: reversed -->",
                   "links": ["F2"], "edges": [{"target": "F2", "type": "contradicts"}]},
            "F2": {"title": "b", "body": "", "links": [], "edges": []},
            "F9": {"title": "c", "body": "", "links": [], "edges": []},
        }
        self.assertEqual(ctx._contradicted_by(nodes), {}, "a superseded node's contradicts edge must not count")


class TestEvidenceAndInversion(unittest.TestCase):
    """ctx._n_evidence (maturity count) + the inverted/data-revised reason codes and
    cmd_why's escalated warning for an inverted supersession."""

    def test_n_evidence_counts_cited_and_corroborating(self):
        nodes = {
            "F1": {"title": "x", "body": "", "edges": [
                {"target": "E1", "type": "evidenced_by"}, {"target": "E2", "type": "evidenced_by"}]},
            "F2": {"title": "y", "body": "", "edges": [{"target": "F1", "type": "supports"}]},
            "E1": {"title": "e", "body": "", "edges": []},
            "E2": {"title": "e", "body": "", "edges": []},
        }
        self.assertEqual(ctx._n_evidence("F1", nodes), (2, 1))  # 2 cited experiments, 1 corroborator
        self.assertEqual(ctx._n_evidence("E1", nodes), (0, 0))

    def test_n_evidence_excludes_superseded_backing(self):
        # A superseded supporter / cited experiment is retracted backing — not counted.
        nodes = {
            "F1": {"title": "x", "body": "", "edges": [{"target": "E1", "type": "evidenced_by"}]},
            "E1": {"title": "e", "body": "<!-- status: superseded; by: E2; reason: reversed -->", "edges": []},
            "E2": {"title": "e2", "body": "", "edges": []},
            "F2": {"title": "y", "body": "<!-- status: superseded; by: F3; reason: reversed -->",
                   "edges": [{"target": "F1", "type": "supports"}]},
            "F3": {"title": "z", "body": "", "edges": []},
        }
        self.assertEqual(ctx._n_evidence("F1", nodes), (0, 0),
                         "superseded cited experiment and superseded supporter must both be excluded")

    def test_inversion_reason_codes_registered(self):
        self.assertIn("inverted", ctx.REASON_CODES)
        self.assertIn("data-revised", ctx.REASON_CODES)
        self.assertIn("inverted", ctx._INVERSION_REASONS)

    def test_cmd_why_escalates_inverted_supersession(self):
        # F3 is superseded by F13 with reason 'inverted' → cmd_why must escalate.
        import contextlib, io, types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_why(types.SimpleNamespace(node="F3"))
        self.assertIn("INVERTED", buf.getvalue())


class TestNoOrphanIdeaNodes(unittest.TestCase):
    """Soft-fail (rot-by-omission): a research idea node (F/H/E/D) with no idea-edge
    AND no bridge is invisible to frontier/why/impact. Inert code stubs (__init__.py,
    un-owned test files) are isolated by design and ignored via _is_idea_id. The
    waiver set mirrors the KNOWN_* idiom — empty today; add an id (with a reason) only
    if a finding is intentionally standalone, and the stale-waiver check self-cleans it."""

    KNOWN_ORPHAN_IDEA_NODES = set()  # e.g. {"F11"} — a SET of ids; put the reason in a comment

    def test_no_unwaived_orphan_idea_nodes(self):
        G, adj = ctx.build_graph(include_code=True)
        orphans = {nid for nid in G if not adj[nid] and ctx._is_idea_id(nid)}
        unexpected = orphans - self.KNOWN_ORPHAN_IDEA_NODES
        self.assertEqual(
            unexpected, set(),
            f"orphan idea node(s) with no edge/bridge: {sorted(unexpected)} — add an idea-edge "
            f"[[ID]] or a graph_bridge, or waive in KNOWN_ORPHAN_IDEA_NODES")

    def test_waivers_are_still_orphaned(self):
        # Keep the waiver honest: an id that's no longer orphaned must be removed.
        G, adj = ctx.build_graph(include_code=True)
        orphans = {nid for nid in G if not adj[nid] and ctx._is_idea_id(nid)}
        stale = self.KNOWN_ORPHAN_IDEA_NODES - orphans
        self.assertEqual(stale, set(), f"stale waivers (no longer orphaned): {sorted(stale)}")


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


class TestUnifiedGraph(unittest.TestCase):
    """Context Web v2 #6 — one walkable graph over research nodes ∪ idea↔code
    bridges, with directed typed adjacency."""

    @classmethod
    def setUpClass(cls):
        cls.G, cls.adj = ctx.build_graph()

    def test_research_and_code_nodes_share_one_namespace(self):
        self.assertIn("F17", self.G)
        self.assertEqual(self.G["F17"]["kind"], "F")
        # F17's bridge to compute_trade_returns is a 'code:' pseudo-node in the graph.
        self.assertIn("code:src/strategy/engine.py::compute_trade_returns", self.G)
        self.assertIn("cfg:STOP_LOSS_PCT_TQQQ_HOURLY", self.G)

    def test_edges_are_bidirectional(self):
        # every out-edge has a matching in-edge on the target (so traversal works both ways).
        for nid, edges in self.adj.items():
            for e in edges:
                if e["dir"] != "out":
                    continue
                self.assertTrue(
                    any(b["to"] == nid and b["type"] == e["type"] and b["dir"] == "in"
                        for b in self.adj[e["to"]]),
                    f"missing reverse edge for {nid} --{e['type']}--> {e['to']}")

    def test_bridge_edge_present_from_finding_to_code(self):
        outs = [(e["type"], e["to"]) for e in self.adj["F17"] if e["dir"] == "out"]
        self.assertIn(("concerns", "code:src/strategy/engine.py::compute_trade_returns"), outs)

    def test_supersession_is_walkable_both_directions(self):
        # F13 supersedes F3; the reverse (F3 superseded-by F13) must be reachable.
        f13_out = [e["to"] for e in self.adj["F13"] if e["dir"] == "out" and e["type"] == "supersedes"]
        self.assertIn("F3", f13_out)
        f3_in = [e["to"] for e in self.adj["F3"] if e["dir"] == "in" and e["type"] == "supersedes"]
        self.assertIn("F13", f3_in)


class TestGraphHtmlExplore(unittest.TestCase):
    """The static `ctx graph --html` UI should keep its selected-node prompt drawer.

    This is template-level because the map is emitted as one self-contained HTML blob;
    browser behavior is smoke-checked separately by parsing the generated inline JS.
    """

    def test_explore_prompt_drawer_is_embedded(self):
        html = ctx._GRAPH_HTML
        for needle in (
            "function makePrompts",
            "function renderPrompts",
            "data-copy",
            "fallbackCopy",
            "Evidence Chain",
            "Config Value",
            "Code Impact",
            "Area Brief",
            "--map:#02040a",
            "const dark=true",
            "function targetZ",
            "function nodeZ",
            "function init3D",
            "function relax3D",
            "function orbPath",
            "function haloOpacity",
            "node-orb mark",
            "node-halo",
            "node-corona",
            "node-core",
            "node-label",
            ".attr('class','node')",
            ".attr('data-id',d=>d.id)",
            ".classed('selected'",
            "orbGlowStrong",
            "orbHalo",
            "function viewCenter",
            "x:(W/2-(zt.x||0))/k",
            "dataset.viewCx",
            "dataset.orbitRy",
            "dataset.fastRender",
            "simSettling=true",
            "function setFastRender",
            "function settleRenderQuality",
            "function filterGlow",
            "fastRender&&!vivid",
            "renderFrame%12",
            "renderFrame%24",
            "suppressZoomLabel",
            "alphaDecay(.055)",
            "alphaMin(.02)",
            "cruiseFrame++%3",
            "!suppressZoomLabel&&!fastRender",
            "setOrbit(a.rx+(b.rx-a.rx)*e,a.ry+dy*e,false)",
            "function projectPoint",
            "function projectNode",
            "function labelBox",
            "function layoutLabels",
            "function placeTip",
            "function showTip",
            "boxesOverlap",
            "text-anchor",
            ".attr('data-z'",
            ".attr('data-depth'",
            "init3D();",
            "sim.on('tick',()=>{relax3D(sim.alpha());render();});",
            "pointerdown.orbit",
            "!ev.shiftKey",
            'id="flat"',
            "function flatView",
            "function orbitToNode",
            "function egoNodes",
            "function transformForEgo",
            "function applyEgoFrame",
            "function cruiseOrbit",
            "function stopCruise",
            "dur=52000",
            "segs=views.length-1",
            "cruiseAnim=requestAnimationFrame(step)",
            "if(sel!==null){const d=nodes[sel],frame=()=>applyEgoFrame",
            "animateOrbit(0,0,420);",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, html)
        for needle in ("spaceDots", "space-dot", "function renderSpace", "node.append('circle')", "function starPath", "node-star"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, html)


class TestFrontier(unittest.TestCase):
    """Context Web v2 #7 — task-shaped progressive disclosure: seeds + corrections,
    budget-bounded, not a fixed summary."""

    def _run(self, task, budget=900):
        import contextlib
        import io
        import types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_frontier(types.SimpleNamespace(task=task.split(), budget=budget))
        return buf.getvalue()

    def test_stop_task_surfaces_flaw_reversal_and_bridge(self):
        out = self._run("retune the TQQQ hourly stop")
        self.assertIn("HONEST STATE", out)
        self.assertIn("F17", out)   # the %-stop exit-flaw finding
        self.assertIn("F13", out)   # the hourly-edge reversal pulled in by activation
        self.assertIn("cfg:STOP_LOSS_PCT_TQQQ_HOURLY", out)  # the code bridge

    def test_no_match_is_graceful(self):
        self.assertIn("no idea-graph match", self._run("zzzqqq xyzzy nonsense"))

    def test_stopwords_alone_do_not_seed(self):
        # regression on the stopword filter: bare 'the' must not seed every node.
        self.assertIn("no idea-graph match", self._run("the the the"))

    def test_smaller_budget_yields_fewer_lines(self):
        big = self._run("edge stop exit regime", 2000)
        small = self._run("edge stop exit regime", 120)
        self.assertLess(small.count("\n"), big.count("\n"))

    def test_tiny_budget_still_keeps_corrections_and_seeds(self):
        # review #4: a budget below the banner floor must NOT drop corrections/seeds.
        out = self._run("is the edge real", budget=20)
        node_lines = [l for l in out.splitlines() if l.startswith("  F") or l.startswith("  D")]
        self.assertTrue(node_lines, "tiny budget dropped every node (corrections lost)")
        self.assertIn("F13", out)  # the live reversal must survive

    def test_live_reversal_outranks_dead_nodes_it_supersedes(self):
        # review #5: when the query lands on a superseded topic, the LIVE correction
        # (F13) must lead — not the dead F3/F4/F8 that F13 overturns.
        out = self._run("is the edge real")
        lines = [l.strip() for l in out.splitlines() if l.startswith("  F") or l.startswith("  D")]
        f13_pos = next(i for i, l in enumerate(lines) if l.startswith("F13"))
        for dead in ("F3", "F4", "F8"):
            dead_pos = next((i for i, l in enumerate(lines) if l.startswith(dead + " ")), None)
            if dead_pos is not None:
                self.assertLess(f13_pos, dead_pos, f"dead {dead} ranked above the live reversal F13")


class TestRelated(unittest.TestCase):
    """Context Web v2 #11 — TF-IDF semantic search over the real web."""

    def _run(self, query, top=6):
        import contextlib
        import io
        import types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_related(types.SimpleNamespace(query=query.split(), top=top))
        return buf.getvalue()

    def test_related_node_surfaces_its_cluster_and_excludes_self(self):
        out = self._run("F13")           # the morning-data / sampling-artifact reversal
        self.assertNotRegex(out, r"^\s*F13\s", )    # never returns the query node itself
        # at least one of the morning-data / bar-frequency cluster ranks
        self.assertTrue(any(n in out for n in ("F10", "F12", "F14", "F15", "H5")))

    def test_free_text_query_ranks_relevant_nodes(self):
        out = self._run("exit horizon stop mean reversion")
        self.assertTrue("F17" in out or "F19" in out)   # the exit-mechanism findings

    def test_cosine_is_symmetric_and_bounded(self):
        a = {"x": 1.0, "y": 2.0}
        b = {"y": 1.0, "z": 3.0}
        self.assertAlmostEqual(ctx._cos(a, b), ctx._cos(b, a))
        self.assertLessEqual(ctx._cos(a, a), 1.0 + 1e-9)
        self.assertAlmostEqual(ctx._cos(a, a), 1.0)
        self.assertEqual(ctx._cos(a, {}), 0.0)          # empty vector → 0, no div-by-zero

    def test_nonsense_query_degrades_gracefully(self):
        out = self._run("zzqqx nonsense xyzzy")
        self.assertIn("no", out.lower())                 # fallback / no-match message, no crash

    def test_lowercase_id_matches_uppercase(self):       # review fix #1
        self.assertEqual(self._run("f13").splitlines()[0], self._run("F13").splitlines()[0])
        self.assertEqual(self._run("[[F13]]").splitlines()[0], self._run("F13").splitlines()[0])

    def test_markup_does_not_drive_results(self):        # review fix #2
        # related F13 should surface content neighbours, not the superseded nodes that merely cite it
        out = self._run("F13")
        head = "\n".join(out.splitlines()[1:4])           # top-3
        self.assertNotIn("F4", head)
        self.assertNotIn("F8", head)

    def test_top_zero_does_not_crash(self):              # review fix #3
        self.assertIsInstance(self._run("F13", top=0), str)


class TestWhyProvenance(unittest.TestCase):
    """Review fixes for ctx why (Context Web v2 #6): grounding must not be routed
    backwards through supersedes/contradicts edges."""

    def _why(self, node):
        import contextlib
        import io
        import types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_why(types.SimpleNamespace(node=node))
        return buf.getvalue()

    def test_grounding_never_traverses_supersedes(self):
        # review #1 (high): `why F13` must not present an overturned node's evidence
        # as F13's grounding — i.e. no 'supersedes:'/'contradicts:' hop in the paths.
        out = self._why("F13")
        grounding = out.split("bears on")[0]
        self.assertNotIn("supersedes:", grounding,
                         "why routed grounding THROUGH a supersedes edge (backwards provenance)")
        self.assertNotIn("contradicts:", grounding)

    def test_grounding_reaches_real_experiments(self):
        out = self._why("F13")
        self.assertIn("E", out)  # F13 is still grounded in genuine experiments via non-supersession paths
        self.assertIn("grounded in", out)

    def test_why_flags_contradicted_current_node(self):
        # DP-1: a status:current node contradicted by a later current node must be
        # flagged DISPUTED, not presented as settled. Synthetic fixture: the live
        # example this used to pin (F15 vs F22) was resolved by D7 — F15 is now
        # superseded and carries the stronger SUPERSEDED banner instead.
        out = _in_synthetic_web(DISPUTED_WEB, lambda: self._why("F90"))
        self.assertIn("DISPUTED", out)
        self.assertIn("F91", out)

    def test_why_flags_dependency_on_contradicted_node(self):
        # DP-1: D1 references the contradicted F15 → ctx why D1 must flag the fragile
        # dependency on disputed ground.
        out = self._why("D1")
        self.assertIn("FRAGILE", out)
        self.assertIn("F15", out)


class TestUncaptured(unittest.TestCase):
    """ctx uncaptured (DP-13): nudge that strategy/research work landed since the idea
    web last moved, so findings don't escape uncaptured and routing stays complete."""

    def _run(self):
        import contextlib, io, types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_uncaptured(types.SimpleNamespace())
        return buf.getvalue()

    def test_uncaptured_reports_web_freshness(self):
        out = self._run()
        self.assertTrue("idea web is current" in out or "since the idea web last moved" in out, out)

    def test_uncaptured_helper_resolves_a_base(self):
        r = ctx._uncaptured()
        self.assertIsNotNone(r, "RESEARCH_WEB.md should have git history")
        n, base, date, sample = r
        self.assertRegex(base, r"^[0-9a-f]{7,40}$")
        self.assertGreaterEqual(n, 0)
        self.assertLessEqual(len(sample), 8)


class TestPerfHonesty(unittest.TestCase):
    """ctx perf — SF-4: lead with the honest CONFIRMED edge, and make an absent
    state.db a loud warning (not a silent one-liner that invites the SUPERSEDED tables)."""

    def _perf(self):
        import contextlib, io, types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_perf(types.SimpleNamespace())
        return buf.getvalue()

    def test_perf_leads_confirmed_or_loudly_absent(self):
        out = self._perf()
        if "UNAVAILABLE" in out:                 # no state.db (worktree/CI) → must be loud
            self.assertIn("CLAUDE.md", out)      # warns off the superseded fallback
        else:
            self.assertIn("HONEST EDGE", out)
            self.assertLess(out.index("CONFIRMED"), out.index("ALL trades"),
                            "CONFIRMED (honest) must lead the inflated ALL/PROD rows")


class TestGraphHtml(unittest.TestCase):
    """`ctx serve` and `ctx graph --html` share _render_graph_html — it must emit a
    self-contained page with the data injected (no leftover template placeholders)."""

    def test_render_graph_html_is_self_contained(self):
        G, adj = ctx.build_graph(include_code=True)
        html = ctx._render_graph_html(G, adj)
        self.assertTrue(html.startswith("<!DOCTYPE html>"), html[:40])
        self.assertIn("MONAD", html)            # __PROJECT__ substituted
        self.assertNotIn("__DATA__", html)      # graph data injected
        self.assertNotIn("__PROJECT__", html)
        self.assertIn('"n":', html)             # compact graph payload present


if __name__ == "__main__":
    unittest.main()
