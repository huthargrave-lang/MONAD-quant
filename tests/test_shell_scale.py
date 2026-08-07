"""One shell scale, across every surface that claims to share the shell.

The rail is rendered from one place and styled from one place, which is why nobody noticed
that it came out visibly larger on the buckets page than on the overview beside it. The
scale is a CSS `zoom` on `.shell`, and it had been written as a literal in five places
across two files:

  * `tools/research_ui.py`            — the shared shell served to every route (was .7)
  * `SCREENER_COMBINED_DRAFT.html`    — its own copy of the shell (was .7)
  * `SOVEREIGN_LEDGER_OPTIONS_MOCK.html` — the buckets page (was .77)

Raising one of them is a one-character edit that silently makes the surfaces disagree, and
the disagreement is invisible unless two pages are open side by side. These tests make the
literals agree by arithmetic rather than by memory.

The stacking breakpoint is checked in tests/test_screener_ui.py, which recomputes it from
this same zoom — so changing the scale here without changing the media query fails there.
The two files guard opposite halves of the same number on purpose.
"""
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_ui  # noqa: E402

SCREENER = os.path.join(REPO, "docs", "research", "SCREENER_COMBINED_DRAFT.html")
BUCKETS = os.path.join(REPO, "docs", "research", "SOVEREIGN_LEDGER_OPTIONS_MOCK.html")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class EverySurfaceRendersAtOneScale(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.served = research_ui.SHELL_CSS if hasattr(research_ui, "SHELL_CSS") else None

    def _served_zoom(self):
        """The stylesheet the server actually serves, not a module constant — a constant can
        be right while the route ships something else. The pages link /static/ui.css rather
        than inlining it, so that is the artifact to read."""
        code, css, _ct = research_ui.route("/static/ui.css", {}, {})
        self.assertEqual(code, 200, "the shared stylesheet route is gone")
        m = re.search(r"\.shell\{[^}]*zoom:\s*([0-9.]+)", css, re.S)
        self.assertIsNotNone(m, "no .shell zoom in the served stylesheet")
        return float(m.group(1))

    def test_the_pages_actually_link_that_stylesheet(self):
        """Otherwise this file would be comparing the screener against a stylesheet nothing
        loads, and reporting agreement that has no effect on what anyone sees."""
        _code, body, _ct = research_ui.route("/", {}, {})
        self.assertIn("/static/ui.css", body)
        self.assertIn('class="shell"', body)

    def _declared_zoom(self, html, where):
        m = re.search(r"--shell-zoom:\s*([0-9.]+)", html)
        if m:
            return float(m.group(1))
        m = re.search(r"\.shell\{[^}]*zoom:\s*([0-9.]+)", html, re.S)
        self.assertIsNotNone(m, "no shell zoom found in {}".format(where))
        return float(m.group(1))

    def test_the_screener_matches_the_served_shell(self):
        self.assertEqual(
            self._declared_zoom(_read(SCREENER), "the screener"), self._served_zoom(),
            "the screener renders at a different scale from the shell the server serves, so "
            "the shared rail is a different size on it than on every other route")

    def test_the_buckets_page_matches_the_served_shell(self):
        self.assertEqual(
            self._declared_zoom(_read(BUCKETS), "the buckets page"), self._served_zoom(),
            "the buckets page renders at a different scale from the rest — this is the exact "
            "defect the file was reported with: a bigger sidebar on one page than the others")

    def test_the_min_height_compensates_for_the_scale_it_actually_uses(self):
        """`min-height:calc(100vh / z)` is what keeps the shell filling the viewport. With a
        stale z the page is either short of the fold or scrolls past it by the difference."""
        for path, name in ((SCREENER, "screener"), (BUCKETS, "buckets")):
            html = _read(path)
            block = re.search(r"\.shell\{[^}]*\}", html, re.S)
            self.assertIsNotNone(block, name)
            body = block.group(0)
            zoom = re.search(r"zoom:\s*([0-9.a-z(),\- ]+?);", body)
            # Greedy up to the LAST paren before the terminator: the divisor is itself a
            # `var(...)` call now, and a lazy match stops inside it and reports a mismatch
            # between `var(--shell-zoom)` and `var(--shell-zoom`.
            mh = re.search(r"min-height:calc\(100vh / (.*)\)(?=[;}])", body)
            self.assertIsNotNone(mh, "{}: no compensating min-height".format(name))
            self.assertEqual(
                zoom.group(1).strip(), mh.group(1).strip(),
                "{}: zoom and the min-height divisor are different expressions, so one was "
                "changed without the other".format(name))

    def test_the_screener_writes_the_scale_once(self):
        """It was a literal in the rule, in the min-height and in three comments. A variable
        is not decoration here — it is what makes the next change a single edit."""
        html = _read(SCREENER)
        rule = re.search(r"\.shell\{[^}]*\}", html, re.S).group(0)
        self.assertIn("var(--shell-zoom)", rule,
                      "the screener's .shell must read the scale from the variable")

    def test_the_script_reads_the_scale_back_rather_than_repeating_it(self):
        """Board geometry converts between rendered px and CSS px on every pointer event. A
        second copy of the number there would put every drop target off by the difference."""
        html = _read(SCREENER)
        self.assertRegex(
            html, r"function shellZoom\(\)\{[\s\S]{0,220}?getComputedStyle\(shell\)\.zoom",
            "shellZoom must read the computed zoom, not restate it")


if __name__ == "__main__":
    unittest.main()
