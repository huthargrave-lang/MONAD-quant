"""The web had no way to say an existing Finding answers an existing Hypothesis.

Study: `docs/research/CTX_note_link.md`.

`note.py` had two writers — `add` and `supersede`. Neither can attach an edge to a node
that already exists, so recording *"F140 already settled H27"* meant minting a NEW node
whose entire content is an edge. Nobody does that, which is why **26 of the 43 items in
the unresolved queue are hypotheses a Finding already addressed** while linking them with
`relates` or `refines` (F222). The queue was not measuring open questions; it was
measuring under-typed edges.

`note.py link <src> <target> --type <edge>` closes the gap under the same discipline as
the other writers: the write fence, the lock, the full lint, atomic replace, and dry-run
by default. It refuses a self-link, an unknown edge type, a duplicate edge, a missing
node, and a reliance edge into a superseded node.

Applied to the case that surfaced it: `F140 --supports--> H27` and
`F143 --supports--> H27`. Both nodes' text already said H27 was CONFIRMED — the edge just
said `relates`. H27 left the queue, correctly, and the queue went 43 → 42.

The guards below check the writer's *refusals* as carefully as its writes, because a
writer into the one file the kit fences is exactly where a permissive bug is expensive.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ctx  # noqa: E402
import note  # noqa: E402

SAMPLE = (
    "### F1 — first\n"
    "body one\n"
    "Links: [[F2|relates]].\n"
    "_— captured x, 2026-01-01_\n"
    "### F2 — second\n"
    "body two\n"
    "_— captured x, 2026-01-01_\n"
)


class TheTextTransformIsCorrectTests(unittest.TestCase):
    def test_it_appends_to_an_existing_links_line(self):
        out = note.apply_link(SAMPLE, "F1", "F2", "supports")
        line = [l for l in out.splitlines() if l.startswith("Links:")][0]
        self.assertEqual(line, "Links: [[F2|relates]] · [[F2|supports]].")

    def test_it_creates_a_links_line_when_there_is_none(self):
        out = note.apply_link(SAMPLE, "F2", "F1", "relates")
        block = out[out.index("### F2 "):]
        self.assertIn("Links: [[F1|relates]].", block)

    def test_a_new_links_line_precedes_the_provenance_italic(self):
        """So the block still renders the way `render_add` writes one."""
        out = note.apply_link(SAMPLE, "F2", "F1", "relates")
        block = out[out.index("### F2 "):].splitlines()
        links = next(i for i, l in enumerate(block) if l.startswith("Links:"))
        prov = next(i for i, l in enumerate(block) if l.startswith("_—"))
        self.assertLess(links, prov)

    def test_it_touches_no_other_node(self):
        out = note.apply_link(SAMPLE, "F1", "F2", "supports")
        self.assertEqual(out[out.index("### F2 "):], SAMPLE[SAMPLE.index("### F2 "):])

    def test_an_unknown_source_raises(self):
        with self.assertRaises(KeyError):
            note.apply_link(SAMPLE, "F9", "F2", "relates")

    def test_the_result_still_parses_as_two_nodes(self):
        nodes, _ = ctx._parse_web_text(note.apply_link(SAMPLE, "F1", "F2", "supports"))
        self.assertEqual(sorted(nodes), ["F1", "F2"])
        self.assertIn("supports", {e["type"] for e in nodes["F1"]["edges"]})

    def test_retype_replaces_one_existing_edge_without_duplication(self):
        out = note.apply_retype(SAMPLE, "F1", "F2", "relates", "refines")
        block = out[:out.index("### F2 ")]
        self.assertIn("[[F2|refines]]", block)
        self.assertNotIn("[[F2|relates]]", block)

    def test_retype_refuses_an_absent_old_edge(self):
        with self.assertRaisesRegex(ValueError, "found 0"):
            note.apply_retype(SAMPLE, "F1", "F2", "supports", "refines")


class TheWriterRefusesTheDangerousCasesTests(unittest.TestCase):
    """Dry-run only — none of these touch the file."""

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / "note.py"), "link", *args],
            capture_output=True, text=True, timeout=120)

    def test_an_unknown_edge_type_is_refused(self):
        out = self._run("F140", "H27", "--type", "vibes")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("--type must be one of", out.stdout + out.stderr)

    def test_a_missing_node_is_refused(self):
        out = self._run("F99999", "H27", "--type", "supports")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("does not exist", out.stdout + out.stderr)

    def test_a_self_link_is_refused(self):
        out = self._run("H27", "H27", "--type", "relates")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("itself", out.stdout + out.stderr)

    def test_a_duplicate_edge_is_refused(self):
        out = self._run("F140", "H27", "--type", "supports")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("already carries", out.stdout + out.stderr)

    def test_it_is_dry_run_by_default(self):
        # F140->H27 was the original fixture and is no longer usable: F140 already
        # carries [[H27|supports]], and F265 made `link` refuse a SECOND type to a
        # target the parser would silently drop. The dry-run path needs a pair with no
        # existing edge, or it exercises the refusal instead of the write.
        before = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        out = self._run("F140", "F172", "--type", "relates")
        after = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        self.assertEqual(before, after,
                         "note.py link wrote without --commit")
        self.assertIn("DRY RUN", out.stdout + out.stderr)


class ItGoesThroughTheSameFenceAsTheOtherWritersTests(unittest.TestCase):
    def test_it_calls_the_fence_and_the_locked_commit(self):
        import inspect
        source = inspect.getsource(note.cmd_link)
        self.assertIn("_fence()", source,
                      "note.py link bypasses the write fence")
        self.assertIn("_locked_commit", source,
                      "note.py link bypasses the lock + lint + atomic write")

    def test_it_expects_no_node_count_change(self):
        import inspect
        source = inspect.getsource(note.cmd_link)
        self.assertIn("build, 0,", source,
                      "note.py link no longer asserts the node count is unchanged — a "
                      "stray '### id —' in a link would go unnoticed")

    def test_it_refuses_a_reliance_edge_into_a_superseded_node(self):
        import inspect
        self.assertIn("RELIANCE_EDGES", inspect.getsource(note.cmd_link))

    def test_retype_uses_the_same_fence_lock_and_node_count_guard(self):
        import inspect
        source = inspect.getsource(note.cmd_retype)
        self.assertIn("_fence()", source)
        self.assertIn("_locked_commit", source)
        self.assertIn("build, 0,", source)
        self.assertIn("RELIANCE_EDGES", source)


class TheCaseThatSurfacedItIsRecordedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, _ = ctx._parse_web()

    def test_the_confirming_findings_now_support_h27(self):
        for nid in ("F140", "F143"):
            types = {e["type"] for e in self.nodes[nid]["edges"] if e["target"] == "H27"}
            self.assertIn(
                "supports", types,
                "{} no longer supports H27 — its text says H27 is CONFIRMED, so the "
                "edge should say so".format(nid))

    def test_h27_has_left_the_unresolved_queue(self):
        import research_backlog as backlog
        queued = {r["node"] for r in backlog.source_unresolved(backlog.load_nodes(), 10_000)}
        self.assertNotIn(
            "H27", queued,
            "H27 is queued as unanswered again — an edge was removed, or the "
            "answering-edge rule changed")

    def test_the_queue_did_not_collapse(self):
        """One correct edge should move one item, not empty the backlog."""
        import research_backlog as backlog
        queued = backlog.source_unresolved(backlog.load_nodes(), 10_000)
        self.assertGreater(
            len(queued), 25,
            "the unresolved queue fell to {} — either a lot of edges were re-typed at "
            "once (record it) or the rule loosened".format(len(queued)))


if __name__ == "__main__":
    unittest.main()
