"""Code citations in the fact-checked prose docs are anchored (tools/ctx.py `ctx cites`;
docs/citation_anchors.json), so an edit that moves a cited line fails here instead of
silently re-pointing a public claim at unrelated code.

The case for the guard: docs/METHODS.md and docs/GLOSSARY.md were fact-checked at efbd1cc;
the very next commit (abd106c) grew tools/admit.py and moved all ten of their admit.py
cites, and the whole suite stayed green. When the guard was introduced it caught three more
in its first run, cites into docs/research/README.md that a one-line edit there had shifted."""
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

LOCK = REPO / ctx.CITATION_LOCK


class TheCommittedDocs(unittest.TestCase):
    def test_every_citation_in_the_fact_checked_docs_is_anchored_and_in_place(self):
        rep = ctx.citation_report(str(REPO))
        self.assertEqual(rep["problems"], [], "\n".join(rep["problems"][:20]))
        self.assertEqual(rep["unused"], [], "prune with `venv/bin/python tools/ctx.py cites --anchor`")
        self.assertGreaterEqual(rep["cites"], 184)
        self.assertGreaterEqual(rep["pinned"], 13)

    def test_the_lock_covers_the_two_fact_checked_docs_and_is_canonical(self):
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        self.assertEqual(lock["docs"], ["docs/METHODS.md", "docs/GLOSSARY.md"])
        self.assertEqual(LOCK.read_text(encoding="utf-8"),
                         json.dumps(lock, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        for key, anchor in lock["anchors"].items():
            with self.subTest(key=key):
                self.assertEqual(set(anchor), {"first", "last"})
                self.assertTrue(anchor["first"] and anchor["last"], "a cite of blank lines anchors nothing")


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CODE = "import os\n\n\ndef target():\n    return 42\n\n\ndef other():\n    return 0\n"
DOC = "The answer is computed in [`../src/m.py:4-5`](../src/m.py) and [`:8`](../src/m.py).\n"


class Scratch(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.repo = Path(self._td.name)
        write(self.repo / "src/m.py", CODE)
        write(self.repo / "docs/D.md", DOC)
        ctx.anchor_citations(str(self.repo), docs=["docs/D.md"])

    def tearDown(self):
        self._td.cleanup()

    def report(self):
        return ctx.citation_report(str(self.repo))

    def test_a_function_inserted_above_a_cited_line_fails_with_where_the_lines_went(self):
        self.assertEqual(self.report()["problems"], [])
        write(self.repo / "src/m.py", "def inserted():\n    pass\n\n\n" + CODE)
        problems = self.report()["problems"]
        self.assertEqual(len(problems), 2, problems)
        self.assertIn("src/m.py:4-5 moved or changed", problems[0])
        self.assertIn("now at 8-9", problems[0])
        self.assertIn("now at 12", problems[1])

    def test_re_anchoring_never_rewrites_a_moved_anchor_only_a_doc_edit_fixes_it(self):
        write(self.repo / "src/m.py", "def inserted():\n    pass\n\n\n" + CODE)
        res = ctx.anchor_citations(str(self.repo))
        self.assertEqual(res, {"added": [], "pruned": []})
        self.assertEqual(len(self.report()["problems"]), 2)               # still failing
        write(self.repo / "docs/D.md", DOC.replace("m.py:4-5", "m.py:8-9").replace("`:8`", "`:12`"))
        res = ctx.anchor_citations(str(self.repo))
        self.assertEqual(res, {"added": ["src/m.py:12", "src/m.py:8-9"], "pruned": ["src/m.py:4-5", "src/m.py:8"]})
        self.assertEqual(self.report()["problems"], [])

    def test_an_edit_to_a_cited_line_in_place_also_fails(self):
        write(self.repo / "src/m.py", CODE.replace("return 42", "return 43"))
        self.assertIn("moved or changed", self.report()["problems"][0])

    def test_unanchored_missing_out_of_range_and_misnamed_cites_fail(self):
        write(self.repo / "docs/D.md", DOC + "New: [`../src/m.py:1`](../src/m.py). Gone: [`../src/x.py:1`](../src/x.py). "
              "Far: [`../src/m.py:90`](../src/m.py). Wrong: [`other.py:4`](../src/m.py).\n")
        problems = "\n".join(self.report()["problems"])
        self.assertIn("src/m.py:1 is not anchored", problems)
        self.assertIn("src/x.py, which does not exist", problems)
        self.assertIn("outside its 9 lines", problems)
        self.assertIn("names other.py but links to src/m.py", problems)

    def test_a_removed_cite_leaves_an_unused_anchor_that_anchoring_prunes(self):
        write(self.repo / "docs/D.md", "Only [`../src/m.py:4-5`](../src/m.py).\n")
        self.assertEqual(self.report()["unused"], ["src/m.py:8"])
        self.assertEqual(ctx.anchor_citations(str(self.repo))["pruned"], ["src/m.py:8"])

    def test_a_commit_pinned_cite_is_checked_at_its_commit_and_for_the_symbol_still_existing(self):
        def git(*args):
            env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                   "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
            return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=self.repo, env=env,
                                  capture_output=True, text=True, check=True).stdout.strip()
        git("init", "-q")
        git("add", "-A")
        git("commit", "-q", "-m", "m")
        sha = git("rev-parse", "--short", "HEAD")
        pinned = (f"[`../src/m.py` (`target`, at {sha}:4)](../src/m.py) "
                  f"[`../src/m.py` (`other`, at {sha}:4)](../src/m.py)\n")
        write(self.repo / "docs/D.md", DOC + pinned)
        rep = self.report()
        self.assertEqual(rep["pinned"], 2)
        self.assertEqual(len(rep["problems"]), 1, rep["problems"])
        self.assertIn(f"`other` is not at {sha}:4", rep["problems"][0])
        write(self.repo / "src/m.py", CODE.replace("target", "renamed"))    # the symbol is gone now
        self.assertTrue(any("`target` no longer exists" in p for p in self.report()["problems"]))

    def test_a_repo_with_no_lock_has_nothing_to_check(self):
        with tempfile.TemporaryDirectory() as td:
            rep = ctx.citation_report(td)
        self.assertEqual((rep["lock"], rep["problems"], rep["cites"]), (None, [], 0))
