"""tools/note.py — disjoint per-branch ID blocks (W6).

H41 already narrowed cross-branch ID collisions: `_remote_ids` consults the deploy
branch's committed web before allocating. Its own docstring is honest that this is
a narrowing, not a fix — "it cannot see a sibling's unpushed work, so it narrows
the window rather than closing it". Two sessions branching from the same fetched
base still hand out the same number, which is what produced the duplicate D7/D8
headings at the 2026-07-06 merge and the 31 renumbered ids at cc7cff6.

A race is not fixed by looking harder. These tests pin the arithmetic that closes
it: side branches allocate inside a block derived from the branch name, so two
branches cannot produce the same id regardless of what either has pushed.

Two properties matter more than the numbering scheme itself:

  * the DEPLOY branch keeps the legacy dense range. The corpus carries thousands
    of bare and bracketed references; moving development's allocation would
    invalidate them, and renumbering is rejected precisely because most references
    are invisible to lint.
  * exhaustion FAILS CLOSED. A block that wraps into its neighbour hands out a
    colliding id silently, which is worse than the collision it replaced — the
    operator would have no signal at all.
"""

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import note  # noqa: E402


class TheDeployBranchIsUnchanged(unittest.TestCase):
    def test_deploy_branch_has_no_block(self):
        self.assertEqual(note.id_block("development"), (0, 0))

    def test_unknown_or_detached_head_has_no_block(self):
        """Never invent a block from a name we do not trust — fall back to dense."""
        for name in ("", "HEAD"):
            self.assertEqual(note.id_block(name), (0, 0))

    def test_deploy_allocation_is_still_max_plus_one(self):
        text = "### F265 — a\n\n### F100 — b\n"
        self.assertEqual(note.next_id(text, "F"), "F266")

    def test_existing_corpus_ids_keep_their_meaning(self):
        """The legacy range must stay below the block base, or an old id could be
        read as living inside some branch's block."""
        lo, _ = note.id_block("claude/anything")
        self.assertGreater(lo, 9999)


class BlocksAreDisjoint(unittest.TestCase):
    def test_two_branches_never_share_an_id(self):
        a, b = note.id_block("claude/research-a"), note.id_block("claude/research-b")
        self.assertNotEqual(a, b)
        self.assertTrue(a[1] < b[0] or b[1] < a[0], f"blocks overlap: {a} {b}")

    def test_a_block_is_stable_for_a_given_branch(self):
        self.assertEqual(note.id_block("claude/x"), note.id_block("claude/x"))

    def test_many_branches_produce_non_overlapping_ranges(self):
        seen = {}
        for i in range(60):
            name = f"claude/session-{i}"
            lo, hi = note.id_block(name)
            for other, (olo, ohi) in seen.items():
                if (lo, hi) == (olo, ohi):
                    continue          # same block only if the names hash alike
                self.assertTrue(hi < olo or ohi < lo,
                                f"{name} {lo}-{hi} overlaps {other} {olo}-{ohi}")
            seen[name] = (lo, hi)

    def test_block_ids_keep_the_id_grammar(self):
        """Wide ids must still match ^[FHED]\\d+$ — every regex in the repo is
        unbounded, so a 6-digit id parses, but assert it rather than assume it."""
        import re
        lo, _ = note.id_block("claude/research-a")
        self.assertRegex(f"F{lo}", r"^[FHED]\d+$")
        self.assertTrue(re.match(r"^### ([FHED]\d+) — ", f"### F{lo} — title"))


class ExhaustionFailsClosed(unittest.TestCase):
    def test_a_full_block_refuses_instead_of_wrapping(self):
        """The red-team defect: next_id was max+1 with no clamp, so the 101st node on
        a branch allocated the FIRST id of the neighbouring block — a silent
        cross-branch collision produced by the very mechanism meant to prevent it."""
        lo, hi = note.id_block("claude/research-a")
        text = "\n".join(f"### F{n} — filler" for n in range(lo, hi + 1))
        with self.assertRaises(SystemExit) as cm:
            note.next_id(text, "F", remote=True, _branch="claude/research-a")
        msg = str(cm.exception)
        self.assertIn("exhausted", msg)
        self.assertIn(str(lo), msg)

    def test_the_refusal_names_the_branch_and_the_remedy(self):
        lo, hi = note.id_block("claude/research-a")
        text = "\n".join(f"### F{n} — filler" for n in range(lo, hi + 1))
        with self.assertRaises(SystemExit) as cm:
            note.next_id(text, "F", remote=True, _branch="claude/research-a")
        self.assertIn("claude/research-a", str(cm.exception))
        self.assertIn("second block", str(cm.exception))


class AllocationInsideABlock(unittest.TestCase):
    def test_first_id_on_a_fresh_branch_is_the_block_floor(self):
        lo, _ = note.id_block("claude/research-a")
        self.assertEqual(note.next_id("", "F", remote=True, _branch="claude/research-a"),
                         f"F{lo}")

    def test_it_ignores_ids_outside_its_own_block(self):
        """Deploy-range ids (F265) and other branches' ids must not push this
        branch's allocation — that is the whole point of a disjoint range."""
        lo, _ = note.id_block("claude/research-a")
        text = "### F265 — deploy node\n### F999999 — some other branch\n"
        self.assertEqual(note.next_id(text, "F", remote=True, _branch="claude/research-a"),
                         f"F{lo}")

    def test_it_continues_from_its_own_highest(self):
        lo, _ = note.id_block("claude/research-a")
        text = f"### F{lo} — a\n### F{lo + 1} — b\n"
        self.assertEqual(note.next_id(text, "F", remote=True, _branch="claude/research-a"),
                         f"F{lo + 2}")

    def test_kinds_are_independent_within_a_block(self):
        lo, _ = note.id_block("claude/research-a")
        text = f"### F{lo} — a\n"
        self.assertEqual(note.next_id(text, "H", remote=True, _branch="claude/research-a"),
                         f"H{lo}")


if __name__ == "__main__":
    unittest.main()
