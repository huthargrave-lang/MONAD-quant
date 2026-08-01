"""ops/merge_gate.sh — planning a merge without performing one.

The gate answers the question that actually blocks a sync: not "can git merge
this" but "does merging change how the bot trades". It classifies incoming
commits against the arming import closure, materialises the candidate merge in a
throwaway worktree, and asks tools/arm_check.py whether that candidate would
still start.

The property these tests defend is that PLANNING CANNOT BECOME LANDING. A tool
that inspects the live tree must not be one bug away from rewriting it — the
rearm timer attempts a cold start every ten minutes during the session, so a
half-modified tree has minutes of exposure at most. The strongest cheap guarantee
is source-level: every mutating git verb in this script must be scoped to the
scratch worktree, never to the repo.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "ops" / "merge_gate.sh"


class PlanningCannotBecomeLanding(unittest.TestCase):
    def test_no_mutating_git_verb_targets_the_live_tree(self):
        """Every merge/reset/checkout must carry -C "$SCRATCH". A bare one would
        operate on $REPO, which is the tree the Pi runs from."""
        offenders = []
        for i, line in enumerate(GATE.read_text().splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or not s:
                continue
            if re.search(r"\bgit\s+(merge|reset|checkout|pull|cherry-pick|rebase)\b", s):
                if '-C "$SCRATCH"' not in s:
                    offenders.append(f"{i}: {s}")
        self.assertEqual(offenders, [],
                         "mutating git verb not scoped to the scratch worktree:\n" +
                         "\n".join(offenders))

    def test_it_never_pushes(self):
        self.assertNotRegex(GATE.read_text(), r"\bgit\s+push\b")

    def test_it_never_hard_resets_anything(self):
        self.assertNotIn("reset --hard", GATE.read_text())

    def test_the_scratch_worktree_is_cleaned_up(self):
        src = GATE.read_text()
        self.assertIn("trap cleanup EXIT", src)
        self.assertIn("worktree remove", src)


class RunningItLeavesTheTreeAlone(unittest.TestCase):
    """Behavioural counterpart to the source assertions above."""

    def test_head_and_merge_state_are_unchanged_by_a_plan(self):
        def head():
            return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                  capture_output=True, text=True).stdout.strip()

        before = head()
        subprocess.run(["bash", str(GATE)], cwd=REPO, capture_output=True,
                       text=True, timeout=600,
                       env={**__import__("os").environ,
                            "MONAD_MERGE_GATE_IGNORE_WINDOW": "1"})
        self.assertEqual(head(), before, "merge_gate moved the live HEAD")
        self.assertFalse((REPO / ".git" / "MERGE_HEAD").exists(),
                         "merge_gate left the live tree mid-merge")

    def test_it_does_not_leak_worktrees(self):
        def count():
            out = subprocess.run(["git", "worktree", "list"], cwd=REPO,
                                 capture_output=True, text=True).stdout
            return len(out.splitlines())

        before = count()
        subprocess.run(["bash", str(GATE)], cwd=REPO, capture_output=True,
                       text=True, timeout=600,
                       env={**__import__("os").environ,
                            "MONAD_MERGE_GATE_IGNORE_WINDOW": "1"})
        self.assertEqual(count(), before, "scratch worktree was not removed")


class ArmingWindow(unittest.TestCase):
    def test_it_declares_a_window_refusal(self):
        """Planning at 09:25 ET is one keystroke from landing at 09:25 ET."""
        src = GATE.read_text()
        self.assertIn("America/New_York", src)
        self.assertIn("MONAD_MERGE_GATE_IGNORE_WINDOW", src)


class ExitCodesAreDistinct(unittest.TestCase):
    def test_documented_codes_are_unique(self):
        header = GATE.read_text().split("set -uo pipefail")[0]
        codes = re.findall(r"^#\s+(\d+)\s{2,}\S", header, re.M)
        self.assertGreaterEqual(len(codes), 5)
        self.assertEqual(len(codes), len(set(codes)), "duplicate exit codes documented")

    def test_it_distinguishes_conflict_from_refusal(self):
        """'cannot merge' and 'merged tree will not start' need different codes —
        one is resolvable, the other means do not land at all."""
        src = GATE.read_text()
        self.assertIn("exit 12", src)   # conflicts
        self.assertIn("exit 13", src)   # would refuse to arm


class UsesTheSharedComponents(unittest.TestCase):
    def test_it_reuses_the_closure_and_arm_check_rather_than_reimplementing(self):
        src = GATE.read_text()
        self.assertIn("tools/armed_closure.py", src)
        self.assertIn("tools/arm_check.py", src)
        self.assertIn("tools/drift_render.py", src)

    def test_it_refuses_to_guess_when_the_closure_is_unavailable(self):
        self.assertIn("refusing to guess", GATE.read_text())


if __name__ == "__main__":
    unittest.main()
