"""H15/DP-8: cross-store consistency, and the store that cannot be read.

H15 asks for a `ctx drift` checker across three claim stores: the research web,
`experiments.jsonl` (the sweep ledger), and the `context_map.json` bridges. Building it
surfaced the reason it had not been built.

**One of the three stores is not in the repository.** `experiments.jsonl` is gitignored
(`.gitignore:17`), so it is absent from every fresh clone and from CI. A checker written
to H15's specification would open two files, skip the third, and report "no drift" — a
verdict about a store it never read. That is the absence-flag failure this project keeps
re-learning (F155, F159, F167), and it is why `drift_report()` returns **unknowns**
separately from **problems**, and why `ctx drift` prints
*"0 problems does NOT mean consistent"* whenever an unknown exists.

**What IS checkable is clean, and now guarded.** All 17 bridges name a node that exists
and is current, and every node ID cited in a bridge *note* resolves and is current — which
matters more than it sounds, because this session added F174–F181 references to those
notes, and a note citing a superseded finding would send `ctx impact` at retracted work.

**Advisory, by H15's own instruction.** Cross-store semantic matching is heuristic, so
unknowns do not fail the command; only concrete inconsistencies do. The exit code is
raised with `sys.exit`, matching every other exit-code-bearing command in `ctx` — a first
draft returned the code from the function, which `main()` discards, so the documented
contract would have been false.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402


class TheStoreCensusIsHonestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stores, cls.problems, cls.unknowns = ctx.drift_report()

    def test_all_three_stores_are_named(self):
        self.assertEqual(set(self.stores), {"web", "bridges", "ledger"})

    def test_the_two_committed_stores_are_readable(self):
        self.assertTrue(self.stores["web"][0])
        self.assertTrue(self.stores["bridges"][0])

    def test_the_ledger_is_absent_and_that_becomes_an_UNKNOWN(self):
        """The load-bearing property: an unreadable store must never read as clean."""
        if self.stores["ledger"][0]:
            self.skipTest("experiments.jsonl now exists — see the un-ignore test below")
        self.assertTrue(
            any("ledger" in u for u in self.unknowns),
            "the ledger is missing but no unknown was raised — `ctx drift` would report "
            "0 problems about a store it never opened")

    def test_the_ledger_is_still_gitignored(self):
        """Explains the absence, and fails if someone un-ignores it — at which point
        the ledger check becomes implementable and this file should grow one."""
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(
            "experiments.jsonl", [line.strip() for line in ignore],
            "experiments.jsonl is no longer gitignored — the third store may now be "
            "committed, so implement the ledger-vs-web check instead of leaving it "
            "as a permanent UNKNOWN (IMPROVEMENT_PLAN K2)")

    def test_unknowns_are_not_counted_as_problems(self):
        self.assertEqual(self.problems, [],
                         "cross-store problems appeared: {}".format(self.problems))
        self.assertGreater(len(self.unknowns), 0)


class TheBridgeChecksAreRealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _s, cls.problems, _u = ctx.drift_report()
        cls.nodes, _ = ctx._parse_web()
        cls.bridges = json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["graph_bridges"]["bridges"]

    def test_no_bridge_points_at_a_missing_or_superseded_node(self):
        self.assertEqual(
            [p for p in self.problems if "does not exist" in p or "SUPERSEDED" in p], [],
            "a bridge now names a missing or superseded node — `ctx impact` would "
            "surface retracted work as if it governed the code")

    def test_every_node_id_cited_in_a_bridge_NOTE_resolves(self):
        cited = {ref for b in self.bridges
                 for ref in ctx._NODE_REF_RX.findall(b.get("note", ""))}
        self.assertGreater(
            len(cited), 5,
            "bridge notes cite almost no node IDs, so this check is near-vacuous")
        for ref in sorted(cited):
            self.assertIn(ref, self.nodes,
                          "bridge note cites {} which does not exist".format(ref))
            self.assertFalse(
                ctx._is_superseded(self.nodes[ref]),
                "bridge note cites {}, which is superseded".format(ref))

    def test_the_check_fires_on_a_synthetic_violation(self):
        """A guard that cannot fail is not a guard."""
        self.assertTrue(ctx._NODE_REF_RX.findall("see F999 for details"))
        self.assertNotIn("F999", self.nodes)


class TheCommandContractIsRealTests(unittest.TestCase):
    def test_it_signals_with_sys_exit_not_a_return_value(self):
        """main() discards return values, so a returned code is a false contract."""
        source = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        start = source.index("def cmd_drift(")
        body = source[start:source.index("\ndef ", start + 5)]
        self.assertIn("sys.exit(1)", body,
                      "cmd_drift no longer exits non-zero on a problem")
        self.assertNotIn("return 1", body)

    def test_it_is_read_only(self):
        import io
        import types
        from contextlib import redirect_stdout

        web = ROOT / "RESEARCH_WEB.md"
        manifest = ROOT / "context_map.json"
        before = (web.read_bytes(), manifest.read_bytes())
        buf = io.StringIO()
        # SystemExit is the command's documented way of reporting problems (the sibling
        # test asserts it exits rather than returning a code), so catching it here is what
        # lets the READ-ONLY assertion below actually run. Without this the test aborted on
        # the exit and never checked for a write: whenever real drift existed, the guard
        # reported "not read-only" about a command that had not written anything, and the
        # property it exists to protect went unverified at exactly the moment someone was
        # changing the stores. Strictly stronger — a command that both exited and wrote
        # used to pass this line and now does not.
        with redirect_stdout(buf):
            try:
                ctx.cmd_drift(types.SimpleNamespace())
            except SystemExit:
                pass
        self.assertEqual((web.read_bytes(), manifest.read_bytes()), before,
                         "ctx drift wrote to a store")
        out = buf.getvalue()
        self.assertIn("UNREADABLE", out)
        self.assertIn("does NOT mean consistent", out)


if __name__ == "__main__":
    unittest.main()


class OperatorFactDriftTests(unittest.TestCase):
    """H17/DP-10: repo facts hand-copied into prose, and the memory store that is not
    in the repository.

    H17's literal target is `.claude/memory/*.md`, which lives outside the repo and is
    per-user — absent from every clone and from CI, so it joins the ledger as a
    permanent UNKNOWN rather than a silent pass. What IS checkable is the same failure
    in the in-repo docs: the branch model and CI triggers are stated in four places and
    synced only by convention.

    The dangling-reference check needed two filters to be usable. A naive "does this
    backticked path exist" scan produced roughly 40 hits on this repo; resolving bare
    basenames anywhere in the tree and allowlisting runtime artifacts cut it to four,
    and all four were explicable — three roadmap proposals and one deliberate NEGATIVE
    reference (`skills/monad-validate-edge/SKILL.md` says "There is NO `validate.py` in
    this repo — do not cite it"). Planning documents are now excluded by name: a roadmap
    names files that do not exist yet, which is what a roadmap is.

    So the current answer is a clean negative — no operator-fact drift — and the value
    is the guard plus the filters, because a linter with a 90% false-positive rate is
    one nobody runs.
    """

    @classmethod
    def setUpClass(cls):
        cls.problems, cls.unknowns = ctx.operator_fact_drift()

    def test_there_is_no_operator_fact_drift_today(self):
        self.assertEqual(
            self.problems, [],
            "operator-fact drift appeared: {}".format(self.problems))

    def test_the_absent_memory_store_becomes_an_UNKNOWN(self):
        import os
        memdir = os.path.join(os.path.expanduser("~"), ".claude", "memory")
        if os.path.isdir(memdir):
            self.skipTest("operator memory exists here; the check should now run for real")
        self.assertTrue(
            any("operator memory" in u for u in self.unknowns),
            "the per-user memory directory is absent but no unknown was raised — "
            "`ctx drift` would read as clean about a store outside the repository")

    def test_the_branch_model_agrees_in_all_three_committed_places(self):
        """The fact H17 names first. Manifest, live preflight gate, CI workflow."""
        import json
        import re as _re
        deploy = json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["deploy_branch"]
        pf = (ROOT / "ops" / "preflight_trader_start.sh").read_text(encoding="utf-8")
        self.assertEqual(
            _re.search(r'^EXPECT_BRANCH="([^"]+)"', pf, _re.M).group(1), deploy)
        self.assertIn(
            deploy, (ROOT / ".github" / "workflows" / "test.yml").read_text(
                encoding="utf-8"),
            "the CI workflow no longer mentions the deploy branch — pushes to it may "
            "not be tested")

    def test_a_synthetic_dangling_reference_would_be_caught(self):
        """A guard that cannot fail is not a guard."""
        self.assertTrue(ctx._DOC_PATH_RX.findall("see `tools/nonexistent_thing.py` now"))
        names, relpaths = ctx._repo_file_index()
        self.assertNotIn("nonexistent_thing.py", names)
        self.assertIn("ctx.py", names, "the file index is not seeing the repo")

    def test_runtime_artifacts_are_allowlisted_with_intent(self):
        """Flagging state.db or experiments.jsonl would train a reader to ignore it."""
        for artifact in ("live/state.db", "experiments.jsonl"):
            self.assertIn(artifact, ctx._RUNTIME_ARTIFACTS)

    def test_planning_docs_are_excluded_deliberately(self):
        source = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        self.assertIn("PLANNING_DOCS", source)
        self.assertIn("that is what a roadmap is", source,
                      "the exclusion lost its stated reason")

    def test_the_finding_ledger_is_excluded_too(self):
        """Third occurrence of one pattern: a ledger must be able to DESCRIBE an
        absence without the absence-detector reading it as presence. F208 names
        `src/analysis/performance.py` as a still-unbuilt proposal and tripped this."""
        source = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        idx = source.index("PLANNING_DOCS = {")
        block = source[idx:idx + 300]
        self.assertIn('"RESEARCH_WEB.md"', block,
                      "the finding ledger is no longer excluded from the doc-reference "
                      "linter — any finding naming an unbuilt file will trip it")

    def test_the_ledger_really_does_name_an_unbuilt_file(self):
        """Non-vacuity for the exclusion above."""
        web = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        self.assertIn("src/analysis/performance.py", web)
        self.assertFalse((ROOT / "src" / "analysis" / "performance.py").exists())


class TheTwoDanglingCheckersShareOneNotionOfARuntimeArtifact(unittest.TestCase):
    """CI cleanup, 2026-08-11. `operator_fact_drift` and `doc_topology` both answer "is
    this referenced path missing", and each had its own idea of which paths are PRODUCED
    rather than committed — an exact allowlist in one, a directory-prefix list in the
    other. They disagreed: `data/cache/screener_snapshot.json` was clean to neither, and
    both reported it, but the two lists were free to diverge in either direction and
    nothing compared them.

    One fact, two places, synced by convention, is the drift this module was written to
    find. `doc_topology` now reads `_RUNTIME_ARTIFACTS` too, and this asserts it keeps
    doing so."""

    def test_doc_topology_honours_the_shared_allowlist(self):
        src = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        body = src[src.index("def doc_topology("):]
        body = body[:body.index("\ndef ", 5)]
        self.assertIn("_RUNTIME_ARTIFACTS", body,
                      "doc_topology no longer consults the shared runtime-artifact list, "
                      "so the two dangling checks can disagree about the same path again")

    def test_a_produced_screener_artifact_is_not_a_broken_link(self):
        """Both checkers, on the paths that actually broke CI. These are named
        individually in .gitignore under "Screener caches ... Regenerable by
        refresh/fetch", so they are absent by design in every clone."""
        for ref in ("data/cache/screener_snapshot.json", "data/screener/fundamentals.json"):
            self.assertIn(ref, ctx._RUNTIME_ARTIFACTS,
                          "{} is a generated cache; a doc naming it is correct".format(ref))
        problems, _ = ctx.operator_fact_drift()
        for p in problems:
            for ref in ("screener_snapshot.json", "data/screener/fundamentals.json"):
                self.assertNotIn(ref, p, "a produced artifact is reported as drift: " + p)
        self.assertEqual(ctx.doc_topology()["dangling"], {},
                         "doc_topology still reports a dangling reference")

    def test_the_allowlist_only_covers_paths_gitignore_calls_generated(self):
        """Non-vacuity, and the thing that stops this becoming a place to silence any
        inconvenient reference: every screener path allowlisted here must be one the repo
        itself declares regenerable."""
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for ref in sorted(ctx._RUNTIME_ARTIFACTS):
            if not ref.startswith("data/"):
                continue
            self.assertIn(ref, ignored,
                          "{} is allowlisted as generated but .gitignore does not say "
                          "so — either it is committed (and the reference is real) or "
                          "the ignore rule is missing".format(ref))

    def test_a_genuinely_missing_path_is_still_caught(self):
        """The guard must not have been widened into uselessness: a doc naming a file
        that does not exist and is not produced still has to fail.

        Exercised with a temporary doc rather than by rewriting a real one. The checker
        scans `ops/*.md` from disk with no injection point, so something has to appear
        there — but creating and deleting a new file cannot corrupt a tracked document if
        this process dies midway, and editing `ops/README.md` in place could."""
        probe = ROOT / "ops" / "_dangling_reference_probe.md"
        self.assertFalse(probe.exists(), "the probe file was left behind by an earlier run")
        try:
            probe.write_text("See `ops/there_is_no_such_file.md`.\n", encoding="utf-8")
            problems, _ = ctx.operator_fact_drift()
            self.assertTrue(
                any("there_is_no_such_file.md" in p for p in problems),
                "operator_fact_drift stopped reporting a genuinely dangling reference")
        finally:
            probe.unlink(missing_ok=True)
