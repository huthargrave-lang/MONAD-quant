"""The web can now discuss its own notation without rewiring itself.

Until this existed there was no escape form: `_parse_web_text` turned every `[[ID]]` in
a body into a real edge, so any node writing ABOUT the link syntax emitted the links it
was describing. That is not hypothetical — F239 documented a broken test fixture by
quoting it verbatim, link syntax included, and thereby asserted a `supersedes` edge it
never meant. `ctx stale` flagged a brand-new edge/status conflict created by the very
cycle that had just cleared the previous one (F239, F236).

**A link inside a markdown code span is now skipped.** Backticked links are being
discussed; bare links are being asserted.

Adding it was safe to prove rather than hope: at the time, **zero** of the web's links
sat inside a code span, and the full edge set — 1508 typed edges over 446 nodes —
came out byte-identical before and after. A parser change that leaves every existing
edge untouched is an addition, not a migration.

Guards below are bidirectional. They fail if the escape stops working (a node
documenting the syntax would silently rewire the graph again) and they fail if it
starts swallowing real links (edges vanish, which is worse and quieter). The
live-web check compares the parser's own output against an independent count, so
neither direction can drift unnoticed.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ctx  # noqa: E402

WEB = ROOT / "RESEARCH_WEB.md"


class TheEscapeFormWorksTests(unittest.TestCase):
    """Synthetic input, both directions — the live web must not be the only witness."""

    def _edges(self, body):
        nodes, _ = ctx._parse_web_text(
            "### F1 — subject\n{}\n\n### F2 — a\nx\n\n### F3 — b\ny\n".format(body))
        return {(e["target"], e["type"]) for e in nodes["F1"]["edges"]}

    def test_a_bare_link_still_asserts_an_edge(self):
        """Non-vacuity. An escape that swallowed everything would also pass the
        'escaped links emit nothing' check below."""
        self.assertEqual(self._edges("Relies on [[F2]]."), {("F2", "relies_on")})

    def test_an_inline_escaped_link_asserts_nothing(self):
        self.assertEqual(self._edges("Discussing `[[F2]]` as notation."), set())

    def test_the_prose_cue_cannot_reach_through_the_escape(self):
        """The exact F239 failure: a `supersedes` cue beside a quoted link."""
        self.assertEqual(
            self._edges("The fixture wrote 'Superseded by `[[F2]]`' in its body."),
            set(),
            "a cue word next to an escaped link still types an edge — this is the "
            "shape that made F239 assert a supersession it never meant")

    def test_escaping_is_per_link_not_per_node(self):
        edges = self._edges("Quoting `[[F2]]` while genuinely refining [[F3|refines]].")
        self.assertEqual(edges, {("F3", "refines")})

    def test_double_backticks_and_fences_also_escape(self):
        self.assertEqual(self._edges("A ``[[F2]]`` span."), set())
        self.assertEqual(self._edges("```\n[[F2]]\n```"), set())

    def test_an_unclosed_backtick_does_not_escape(self):
        """Fail closed: a stray backtick must not silently delete a real edge."""
        self.assertEqual(self._edges("A stray ` and then [[F2|refines]]."),
                         {("F2", "refines")})


class TheLiveWebIsUnaffectedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, _ = ctx._parse_web()
        cls.text = WEB.read_text(encoding="utf-8")

    def test_the_parsers_edges_match_an_independent_count(self):
        """Counted a second way, so a bug in the skip cannot hide behind itself."""
        spans = ctx._code_spans(self.text)
        unescaped = set()
        for m in re.finditer(r"\[\[([A-Za-z]+\d+)(?:\|[^\]]+)?\]\]", self.text):
            if not any(s <= m.start() and m.end() <= e for s, e in spans):
                unescaped.add(m.group(1))
        parsed = {e["target"] for n in self.nodes.values() for e in n["edges"]}
        missing = sorted(t for t in parsed if t not in unescaped)
        self.assertEqual(
            missing, [],
            "the parser emitted edges to {} which no unescaped link supports".format(
                missing))

    def test_the_web_still_has_a_substantial_edge_set(self):
        total = sum(len(n["edges"]) for n in self.nodes.values())
        self.assertGreater(
            total, 1400,
            "typed edges fell to {} — the escape is swallowing real links".format(total))

    def test_f239_uses_the_escape_it_motivated(self):
        """The finding that needed this is now able to quote the thing it is about."""
        body = self.nodes["F239"]["body"]
        self.assertIn("`[[", body,
                      "F239 no longer quotes link syntax, so the feature it motivated "
                      "has no worked example in the corpus")
        targets = {e["target"] for e in self.nodes["F239"]["edges"]}
        self.assertNotIn(
            "F2", targets,
            "F239 asserts an edge to F2 again — the escape is not holding, and that is "
            "precisely the accidental supersession it was built to prevent")


if __name__ == "__main__":
    unittest.main()
