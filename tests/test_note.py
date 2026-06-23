"""
Tests for tools/note.py — the write-fenced research-web capture tool.

Exercises the pure builders + the candidate lint against synthetic webs (parsed
through the canonical ctx parser), the write-fence target resolution, and that the
real RESEARCH_WEB.md still lints clean by note's own rules (ties note to ctx).
note.py is dry-run by default and these tests never pass --commit, so the real
RESEARCH_WEB.md is never written.
"""
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import ctx   # noqa: E402
import note  # noqa: E402

WEB = ("# web\n\n## Findings\n\n### F1 — first finding\nbody [[E1|evidenced_by]]\n"
       "### F22 — late finding\nbody\n### F3 — [SUPERSEDED by F22] old\n"
       "<!-- status: superseded; by: F22; reason: data-fixed -->\nbody\n"
       "## Hypotheses\n\n### H8 — a hypothesis\nbody\n"
       "## Experiments\n\n### E1 — an experiment\nbody\n")


class TestNotePure(unittest.TestCase):
    def test_next_id_is_max_plus_one_per_prefix(self):
        self.assertEqual(note.next_id(WEB, "F"), "F23")   # max(F1,F22,F3)=22 → 23
        self.assertEqual(note.next_id(WEB, "H"), "H9")
        self.assertEqual(note.next_id(WEB, "E"), "E2")
        self.assertEqual(note.next_id(WEB, "D"), "D1")    # none yet → start at 1

    def test_render_add_parses_with_typed_edge(self):
        block = note.render_add("F23", "a new finding", "the body text",
                                [("E1", "evidenced_by")], "2026-06-22")
        nodes, _ = note._parse(WEB + block)
        self.assertIn("F23", nodes)
        self.assertEqual(nodes["F23"]["title"], "a new finding")
        edges = {e["target"]: e["type"] for e in nodes["F23"]["edges"]}
        self.assertEqual(edges.get("E1"), "evidenced_by")
        self.assertEqual(note.lint_nodes(nodes)[0], [])   # no problems

    def test_lint_flags_dangling_link(self):
        block = note.render_add("F23", "t", "body", [], "2026-06-22").replace(
            "_— captured", "see [[F999]]\n_— captured")
        nodes, _ = note._parse(WEB + block)
        self.assertTrue(any("dangling" in p for p in note.lint_nodes(nodes)[0]))

    def test_lint_flags_live_reliance_on_superseded(self):
        # a live F23 that relies_on the superseded F3 must be a PROBLEM
        block = note.render_add("F23", "t", "body", [("F3", "relies_on")], "2026-06-22")
        nodes, _ = note._parse(WEB + block)
        probs = note.lint_nodes(nodes)[0]
        self.assertTrue(any("F23" in p and "F3" in p for p in probs))

    def test_lint_flags_propagation_without_superseder(self):
        # The write gate must enforce the SAME supersession-propagation invariant as
        # ctx web --lint: a live F23 that `relates` to superseded F3 without also citing
        # its superseder F22 is a PROBLEM (else `supersede --commit` could write a web
        # that CI then hard-fails). Regression for the adversarial-review gap.
        block = note.render_add("F23", "t", "body", [("F3", "relates")], "2026-06-22")
        nodes, _ = note._parse(WEB + block)
        probs = note.lint_nodes(nodes)[0]
        self.assertTrue(any("F23" in p and "F3" in p and "F22" in p for p in probs),
                        f"propagation violation not flagged by note.lint_nodes: {probs}")

    def test_lint_clears_propagation_when_superseder_cited(self):
        # citing both the superseded F3 and its superseder F22 clears the violation
        block = note.render_add("F23", "t", "body", [("F3", "relates"), ("F22", "relates")], "2026-06-22")
        nodes, _ = note._parse(WEB + block)
        self.assertEqual(note.lint_nodes(nodes)[0], [])

    def test_lint_clean_on_the_real_web(self):
        # note's own lint must agree the committed RESEARCH_WEB.md is problem-free
        nodes, _ = ctx._parse_web()
        self.assertEqual(note.lint_nodes(nodes)[0], [])

    def test_apply_supersede_marks_and_links(self):
        out = note.apply_supersede(WEB, "H8", "F1", "reversed", "2026-06-22")
        nodes, _ = note._parse(out)
        self.assertTrue(ctx._is_superseded(nodes["H8"]))
        self.assertEqual(ctx._node_meta(nodes["H8"]).get("by"), "F1")
        f1_edges = {e["target"]: e["type"] for e in nodes["F1"]["edges"]}
        self.assertEqual(f1_edges.get("H8"), "supersedes")
        self.assertEqual(note.lint_nodes(nodes)[0], [])


class TestNoteFence(unittest.TestCase):
    def test_target_resolves_to_research_web(self):
        real_repo, real_target = note._fence()
        self.assertEqual(os.path.basename(real_target), "RESEARCH_WEB.md")
        self.assertEqual(os.path.dirname(real_target), real_repo)

    def test_no_path_argument_exists(self):
        # the fence relies on there being NO way to supply the destination via CLI
        src = open(os.path.join(REPO, "tools", "note.py")).read()
        for forbidden in ('add_argument("--path"', 'add_argument("--file"', 'add_argument("--out"'):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
