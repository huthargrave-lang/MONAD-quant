"""tools/web_merge_driver.py — merging RESEARCH_WEB.md by node, not by line.

The tempting fix for an append-mostly file is `merge=union`, and it is measurably
wrong. Two branches that each edit the same `### F2` heading merge under union
with exit 0 and produce a file with two `### F2` lines; ctx's parser overwrites on
duplicate ids, so one node silently wins and the other's `[SUPERSEDED by …]`
marker vanishes. Union manufactures the duplicate-id corruption it was meant to
prevent, silently. The first test here pins exactly that case.

The driver's job is therefore narrow: resolve the append case (the overwhelming
majority of research work) without human attention, and CONFLICT — loudly — when
two branches genuinely disagree about one node's content. A merge driver that
picks a winner for a contested research claim is not a convenience, it is a
corruption.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import web_merge_driver as drv  # noqa: E402

PRE = "# Research Web\n\nSome preamble.\n\n"


def web(*nodes):
    return PRE + "".join(f"### {i} — {t}\n{b}\n\n" for i, t, b in nodes)


class TheAppendCaseResolvesSilently(unittest.TestCase):
    """This is ~90% of real research work: two branches each add new nodes."""

    def test_disjoint_additions_are_unioned(self):
        base = web(("F1", "one", "body one"))
        ours = web(("F1", "one", "body one"), ("F10", "ours", "our body"))
        theirs = web(("F1", "one", "body one"), ("F20", "theirs", "their body"))
        merged, conflict = drv.merge_text(base, ours, theirs)
        self.assertFalse(conflict)
        for needle in ("### F1 ", "### F10 ", "### F20 "):
            self.assertIn(needle, merged)

    def test_no_duplicate_headings_are_produced(self):
        base = web(("F1", "one", "b"))
        ours = web(("F1", "one", "b"), ("F10", "a", "x"))
        theirs = web(("F1", "one", "b"), ("F20", "b", "y"))
        merged, _ = drv.merge_text(base, ours, theirs)
        for nid in ("F1", "F10", "F20"):
            self.assertEqual(merged.count(f"### {nid} "), 1, f"{nid} duplicated")

    def test_a_one_sided_edit_is_taken(self):
        base = web(("F1", "one", "old body"))
        ours = web(("F1", "one", "old body"))
        theirs = web(("F1", "one", "NEW body"))
        merged, conflict = drv.merge_text(base, ours, theirs)
        self.assertFalse(conflict)
        self.assertIn("NEW body", merged)
        self.assertEqual(merged.count("### F1 "), 1)

    def test_identical_edits_on_both_sides_collapse(self):
        base = web(("F1", "one", "old"))
        same = web(("F1", "one", "new"))
        merged, conflict = drv.merge_text(base, same, same)
        self.assertFalse(conflict)
        self.assertEqual(merged.count("### F1 "), 1)
        self.assertIn("new", merged)


class ContestedNodesConflictLoudly(unittest.TestCase):
    def test_both_sides_editing_one_node_is_a_conflict_not_a_silent_pick(self):
        """The union failure mode, pinned. Under union this merged clean and lost a
        supersession fact; here it must conflict."""
        base = web(("F2", "beta", "original claim"))
        ours = web(("F2", "beta", "original claim [SUPERSEDED by F9]"))
        theirs = web(("F2", "beta", "original claim [RETRACTED by F8]"))
        merged, conflict = drv.merge_text(base, ours, theirs)
        self.assertTrue(conflict, "a contested research claim must not auto-resolve")
        self.assertIn("<<<<<<<", merged)
        self.assertIn("SUPERSEDED by F9", merged)
        self.assertIn("RETRACTED by F8", merged)

    def test_a_conflict_never_silently_drops_a_supersession(self):
        base = web(("F2", "beta", "claim"))
        ours = web(("F2", "beta", "claim [SUPERSEDED by F9]"))
        theirs = web(("F2", "beta", "claim edited elsewhere"))
        merged, _ = drv.merge_text(base, ours, theirs)
        self.assertIn("SUPERSEDED by F9", merged)

    def test_divergent_preambles_conflict(self):
        base = web(("F1", "a", "b"))
        ours = base.replace("Some preamble.", "Ours preamble.")
        theirs = base.replace("Some preamble.", "Theirs preamble.")
        _, conflict = drv.merge_text(base, ours, theirs)
        self.assertTrue(conflict)


class Deletions(unittest.TestCase):
    def test_a_node_deleted_on_one_side_and_untouched_on_the_other_is_removed(self):
        base = web(("F1", "a", "x"), ("F2", "b", "y"))
        ours = base
        theirs = web(("F1", "a", "x"))
        merged, conflict = drv.merge_text(base, ours, theirs)
        self.assertFalse(conflict)
        self.assertNotIn("### F2 ", merged)

    def test_a_node_deleted_on_one_side_but_edited_on_the_other_is_kept(self):
        """Deleting a node someone else just revised is a disagreement; keep the
        content rather than discarding an edit nobody reviewed."""
        base = web(("F1", "a", "x"), ("F2", "b", "y"))
        ours = web(("F1", "a", "x"), ("F2", "b", "y EDITED"))
        theirs = web(("F1", "a", "x"))
        merged, _ = drv.merge_text(base, ours, theirs)
        self.assertIn("y EDITED", merged)


class RunsAsAGitDriver(unittest.TestCase):
    def test_cli_writes_the_result_to_the_ours_path_and_signals_conflict(self):
        d = Path(tempfile.mkdtemp())
        (d / "O").write_text(web(("F2", "b", "orig")))
        (d / "A").write_text(web(("F2", "b", "ours")))
        (d / "B").write_text(web(("F2", "b", "theirs")))
        rc = subprocess.run(
            [sys.executable, str(REPO / "tools" / "web_merge_driver.py"),
             str(d / "O"), str(d / "A"), str(d / "B")],
            capture_output=True, text=True).returncode
        self.assertEqual(rc, 1, "a contested merge must exit non-zero")
        self.assertIn("<<<<<<<", (d / "A").read_text())

    def test_clean_merge_exits_zero(self):
        d = Path(tempfile.mkdtemp())
        (d / "O").write_text(web(("F1", "a", "x")))
        (d / "A").write_text(web(("F1", "a", "x"), ("F10", "m", "n")))
        (d / "B").write_text(web(("F1", "a", "x"), ("F20", "p", "q")))
        rc = subprocess.run(
            [sys.executable, str(REPO / "tools" / "web_merge_driver.py"),
             str(d / "O"), str(d / "A"), str(d / "B")],
            capture_output=True, text=True).returncode
        self.assertEqual(rc, 0)
        self.assertIn("### F20 ", (d / "A").read_text())


class WiredUp(unittest.TestCase):
    def test_gitattributes_routes_the_web_to_this_driver(self):
        ga = (REPO / ".gitattributes")
        self.assertTrue(ga.exists(), ".gitattributes is missing")
        self.assertIn("RESEARCH_WEB.md", ga.read_text())
        self.assertIn("merge=researchweb", ga.read_text())

    def test_the_real_web_round_trips_through_the_splitter(self):
        """Guard against the parser silently dropping content on the live corpus."""
        text = (REPO / "RESEARCH_WEB.md").read_text()
        pre, blocks, order = drv.split_blocks(text)
        self.assertGreater(len(blocks), 100)
        self.assertEqual(pre + "".join(blocks[i] for i in order), text,
                         "split/rejoin is not lossless on the live web")


if __name__ == "__main__":
    unittest.main()
