"""`ctx brief` carries the deploy-sync line.

This is the highest-leverage surface for the drift fact and the reason the oracle
exists at all: ops/session_orient.py runs `ctx brief` on EVERY SessionStart and
injects the output as additionalContext, so an agent cannot skip reading it.
ops/status_check.sh only fires when a human types `ctx status`, and preflight ran
ZERO times during the seven days the checkout sat 129 commits behind — the trader
process was continuously active, so systemd's daily start was a no-op and
ExecStartPre never executed.

Two things are pinned here, and both are about the surface being USEFUL rather
than merely present:

  * IT RESOLVES THE ARTIFACT AGAINST THE MAIN WORKTREE. local_logs/ is gitignored,
    so it exists only in the primary checkout. Agent sessions frequently run in
    linked worktrees (five have existed in this repo). Resolving against __file__
    would make exactly those sessions read a path that is never populated and see
    UNKNOWN forever — correct, and useless.

  * IT NEVER GOES QUIET. Missing, malformed or unreadable artifact still prints a
    visible UNKNOWN. A surface that falls silent when its sensor dies reads exactly
    like a surface saying "fine", which is the original failure.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import ctx  # noqa: E402


def run_brief(cwd=None):
    p = subprocess.run([str(REPO / "venv" / "bin" / "python"),
                        str(REPO / "tools" / "ctx.py"), "brief"],
                       capture_output=True, text=True, cwd=cwd or str(REPO), timeout=120)
    return p.stdout


class TheLineIsPresent(unittest.TestCase):
    def test_brief_carries_a_deploy_sync_line(self):
        self.assertIn("DEPLOY SYNC:", run_brief())

    def test_it_precedes_the_honest_state_banner(self):
        """Everything below describes a checkout; this says whether the checkout is
        the code anyone else is looking at, so it is read first."""
        out = run_brief()
        self.assertLess(out.index("DEPLOY SYNC:"), out.index("HONEST STATE:"))

    def test_it_reports_a_recognisable_verdict(self):
        line = [l for l in run_brief().splitlines() if l.startswith("DEPLOY SYNC:")][0]
        self.assertRegex(line, r"in sync|behind|ahead|DIVERGED|UNKNOWN")


class ItResolvesTheMainWorktree(unittest.TestCase):
    def test_main_worktree_is_the_repo_when_called_from_the_repo(self):
        self.assertEqual(os.path.realpath(ctx._main_worktree()),
                         os.path.realpath(str(REPO)))

    def test_from_a_linked_worktree_it_still_finds_the_primary_checkout(self):
        """The trap: local_logs/ is gitignored and absent from every worktree."""
        with tempfile.TemporaryDirectory() as d:
            wt = Path(d) / "wt"
            add = subprocess.run(["git", "worktree", "add", "--quiet", "--detach",
                                  str(wt), "HEAD"], cwd=str(REPO),
                                 capture_output=True, text=True)
            if add.returncode != 0:
                self.skipTest(f"cannot create worktree: {add.stderr}")
            try:
                self.assertFalse((wt / "local_logs").exists(),
                                 "fixture invalid — local_logs should not be in a worktree")
                probe = subprocess.run(
                    [str(REPO / "venv" / "bin" / "python"), "-c",
                     "import sys;sys.path.insert(0,'tools');import ctx;"
                     "print(ctx._main_worktree());print(ctx._drift_line())"],
                    cwd=str(wt), capture_output=True, text=True, timeout=120)
                lines = probe.stdout.strip().splitlines()
                self.assertGreaterEqual(
                    len(lines), 2,
                    "the worktree's ctx.py produced no output — it checks out HEAD, so "
                    "this fails while the change is uncommitted, which is expected "
                    f"locally and not in CI.\nstderr: {probe.stderr[-400:]}")
                self.assertEqual(os.path.realpath(lines[0]), os.path.realpath(str(REPO)),
                                 "a worktree session did not resolve the main checkout")
                self.assertNotIn("no readable git_drift.json", lines[1],
                                 "the worktree session cannot see the drift artifact")
            finally:
                subprocess.run(["git", "worktree", "remove", "--force", str(wt)],
                               cwd=str(REPO), capture_output=True)


class ItNeverGoesQuiet(unittest.TestCase):
    def test_a_missing_artifact_still_prints_something_visible(self):
        with tempfile.TemporaryDirectory() as d:
            out = ctx.sys.modules  # noqa: F841 — keep ctx imported
            import drift_render
            line = drift_render.render(Path(d) / "absent.json")
        self.assertTrue(line.strip())
        self.assertIn("UNKNOWN", line)

    def test_the_line_is_never_empty(self):
        self.assertTrue(ctx._drift_line().strip())

    def test_a_renderer_failure_degrades_to_unknown_rather_than_raising(self):
        """This runs inside a SessionStart hook with a 20s budget; an exception here
        would strip the orientation packet from every new agent session."""
        import builtins
        real = builtins.__import__

        def boom(name, *a, **k):
            if name == "drift_render":
                raise ImportError("simulated")
            return real(name, *a, **k)

        builtins.__import__ = boom
        try:
            line = ctx._drift_line()
        finally:
            builtins.__import__ = real
        self.assertIn("UNKNOWN", line)


class SurfacesShareOneRenderer(unittest.TestCase):
    def test_brief_and_status_check_use_the_same_function(self):
        """Two hand-formatted copies drift apart, and then the operator has two
        answers and trusts neither."""
        self.assertIn("drift_render", (REPO / "tools" / "ctx.py").read_text())
        self.assertIn("tools/drift_render.py", (REPO / "ops" / "status_check.sh").read_text())


if __name__ == "__main__":
    unittest.main()
