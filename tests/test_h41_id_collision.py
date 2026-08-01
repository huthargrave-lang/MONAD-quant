"""H41: ID allocation saw only the local tree, and a duplicate heading was invisible.

Study: `docs/research/CTX_id_allocation.md`.

H41 records a real incident: at the 2026-07-06 merge, a parallel session on a stale base
allocated `D7`/`D8` for two ctx-graph-UI decisions while those IDs were already taken on
the canonical branch, producing duplicate `### D7`/`### D8` headings on
`origin/development` that had to be renumbered by hand.

Two defects, both confirmed against the code before fixing:

**1. The duplicate was invisible.** `ctx._parse_web_text` keys nodes by ID, so a second
`### F1` does not error — it *replaces* the first, and the first vanishes from every
downstream view. Reproduced on a three-node string: parsing keeps `F1` and `F2`, and
`F1`'s title and body are the SECOND definition's. `ctx web --lint` had no duplicate
check, so the whole integrity lint ran against a map missing a node it never saw. That is
the worse half: a corrupted web that lints clean.

**2. Allocation read the working tree only.** `next_id` scanned local text and nothing
else, so any session on a stale base could hand out a taken ID.

Fixed: `ctx web --lint` now counts duplicate headings as hard PROBLEMs (exit 2), detected
on the **raw text** before parsing — after parsing the evidence is already gone. And
`next_id` also consults the deploy branch's committed web via `git show`, which needs no
network: whatever was last fetched is in the object store.

The remote check **narrows the window, it does not close it** — it cannot see a sibling
session's unpushed work. That is why the lint check matters more than the allocation
change, and why both are here: allocation makes collisions rarer, the lint makes them
loud. Guarded in both directions below.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ctx  # noqa: E402
import note  # noqa: E402

DUPLICATED = (
    "### F1 — first\n"
    "body one\n"
    "### F2 — other\n"
    "x\n"
    "### F1 — second, shadowing\n"
    "body two\n"
)


class ADuplicateHeadingSilentlyReplacesTheFirstTests(unittest.TestCase):
    """The condition the detector exists for, demonstrated rather than assumed."""

    def test_parsing_keeps_only_the_last_definition(self):
        nodes, _ = ctx._parse_web_text(DUPLICATED)
        self.assertEqual(sorted(nodes), ["F1", "F2"])
        self.assertEqual(
            nodes["F1"]["title"], "second, shadowing",
            "the parser stopped letting a duplicate overwrite the first node — if it "
            "now errors or keeps both, simplify the detector to match")
        self.assertNotIn("body one", nodes["F1"]["body"])

    def test_the_detector_sees_what_the_parser_erases(self):
        self.assertEqual(ctx.duplicate_node_ids(DUPLICATED), {"F1": 2})

    def test_it_reports_the_count_not_just_the_fact(self):
        thrice = DUPLICATED + "### F1 — third\nz\n"
        self.assertEqual(ctx.duplicate_node_ids(thrice), {"F1": 3})

    def test_a_clean_web_has_no_duplicates(self):
        self.assertEqual(
            ctx.duplicate_node_ids(ctx._web_text()), {},
            "the live research web has duplicate node IDs — renumber the later "
            "definition; the earlier node is invisible to every ctx view until you do")

    def test_the_detector_is_not_vacuous_on_the_real_web(self):
        """It must be reading real headings, not returning {} for a trivial reason."""
        text = ctx._web_text()
        self.assertGreater(text.count("\n### "), 300)


class TheLintFailsHardOnDuplicatesTests(unittest.TestCase):
    def _lint(self, web_text, tmpdir):
        """Run `ctx web --lint` against a copy of the repo's web with `web_text`."""
        target = Path(tmpdir) / "RESEARCH_WEB.md"
        target.write_text(web_text, encoding="utf-8")
        original = ctx.WEB
        try:
            ctx.WEB = str(target)
            import io
            import types
            from contextlib import redirect_stdout
            buf = io.StringIO()
            code = 0
            try:
                with redirect_stdout(buf):
                    ctx.cmd_web(types.SimpleNamespace(lint=True, node=None, live=False))
            except SystemExit as exc:
                code = exc.code
            return code, buf.getvalue()
        finally:
            ctx.WEB = original

    def test_a_duplicate_is_a_hard_problem_with_exit_two(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._lint(DUPLICATED, tmp)
        self.assertIn("PROBLEM duplicate: F1", out)
        self.assertIn("2 times", out)
        self.assertEqual(code, 2, "a duplicate heading no longer fails the lint")

    def test_the_same_web_without_the_duplicate_passes(self):
        """Negative control: the failure must come from the duplicate, not the fixture."""
        import tempfile
        clean = DUPLICATED.replace("### F1 — second, shadowing", "### F3 — renumbered")
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._lint(clean, tmp)
        self.assertNotIn("PROBLEM duplicate", out)
        self.assertEqual(code, 0, out)

    def test_the_check_runs_before_the_graph_checks(self):
        """After parsing the evidence is gone, so order is load-bearing, not cosmetic."""
        source = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        body = source[source.index('if getattr(args, "lint", False):'):]
        self.assertLess(
            body.index("duplicate_node_ids"), body.index("dangling ="),
            "the duplicate check moved after the graph checks — those run on the "
            "PARSED map, which has already lost the shadowed node")

    def test_the_live_web_still_lints_clean(self):
        out = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ctx.py"), "web", "--lint"],
            capture_output=True, text=True, timeout=180)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


class AllocationConsultsTheDeployBranchTests(unittest.TestCase):
    def test_the_deploy_branch_is_reachable_offline(self):
        ids = note._remote_ids("F")
        self.assertTrue(
            ids,
            "no IDs readable from the deploy branch — `git show origin/<branch>` "
            "failed, so allocation is back to local-only and H41's window reopens")

    def test_a_stale_local_tree_does_not_reuse_a_taken_id(self):
        stale = "### D1 — something old\nbody\n"
        local_only = note.next_id(stale, "D")
        with_remote = note.next_id(stale, "D", remote=True)
        self.assertEqual(local_only, "D2")
        self.assertNotEqual(
            with_remote, local_only,
            "allocation from a stale tree no longer differs from local-only — the "
            "deploy-branch check has stopped contributing")
        taken = set(note._remote_ids("D"))
        self.assertNotIn(
            int(with_remote[1:]), taken,
            "the allocated ID {} is already taken on the deploy branch".format(
                with_remote))

    def test_the_local_tree_still_wins_when_it_is_ahead(self):
        """This branch is far ahead of the deploy branch; allocation must not go backwards."""
        text = ctx._web_text()
        self.assertEqual(
            note.next_id(text, "F", remote=True), note.next_id(text, "F"),
            "consulting the deploy branch changed the answer on an up-to-date tree — "
            "allocation should take the MAX of both, never the remote alone")

    def test_cmd_add_opts_into_the_remote_check(self):
        """The helper stays pure; the writer is the one that must not collide."""
        source = (ROOT / "tools" / "note.py").read_text(encoding="utf-8")
        self.assertIn(
            'next_id(text, args.kind, remote=True)', source,
            "cmd_add no longer asks for the collision-resistant allocation — it would "
            "silently fall back to local-only, reopening H41")

    def test_the_remote_check_is_documented_as_partial(self):
        source = (ROOT / "tools" / "note.py").read_text(encoding="utf-8")
        self.assertIn(
            "unpushed", source,
            "the docstring no longer records that a sibling session's unpushed work is "
            "invisible — that limit is why the lint check exists alongside this")


if __name__ == "__main__":
    unittest.main()
