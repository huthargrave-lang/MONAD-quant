"""Contract guards for docs/research/SCREENER_COMBINED_DRAFT.html (served /screener/draft).

This page had NO test of any kind while it grew to ~4,000 lines carrying its own lens
engine, its own layout engine and its own copy of the shadow-severity table. That absence
is not incidental to the defects found on 2026-08-07 — it is the mechanism that produced
them. Seven lens definitions had drifted from `stock_screener.PRESETS`, and the drift was
invisible because nothing compared the two: the default lens had drifted all the way to
screening nothing while its bubble still said "Low P/E · high growth", and Sovereign Ledger
was reporting 55 names where 8 qualify.

These are deliberately CONTRACT tests, not behaviour tests. They do not execute the page's
JavaScript — they assert the seams through which the page and the repo agree:

  * the canonical rules reach the page, and the page keeps no second copy of them;
  * every tone lens is reachable from the tone-source map;
  * a constant derived by arithmetic from another constant is recomputed, not trusted;
  * a table defined in Python is not also defined in the page.

A behaviour harness would catch more, and is a reasonable thing to add later. What these
catch is the specific failure that has already happened twice here: two copies of one
definition, drifting silently, with both surfaces published side by side.
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
import stock_screener as sc  # noqa: E402

PAGE = os.path.join(REPO, "docs", "research", "SCREENER_COMBINED_DRAFT.html")


def _page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


class TheLensDefinitionsHaveOneSource(unittest.TestCase):
    """The page must CONSUME stock_screener.PRESETS, never restate it."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.payload = research_ui._screener_combined_draft_payload()

    def test_every_canonical_preset_reaches_the_page(self):
        shipped = self.payload.get("presets") or {}
        self.assertEqual(set(shipped), set(sc.PRESETS),
                         "the page is served a different set of lenses than the repo "
                         "defines, so a bubble can name a screen that no longer exists")

    def test_the_shipped_rules_are_the_canonical_rules(self):
        shipped = self.payload["presets"]
        for key, preset in sc.PRESETS.items():
            self.assertEqual(
                [list(rule) for rule in preset["require"]], shipped[key]["require"], key)
            self.assertEqual(list(preset["rank"]), shipped[key]["rank"], key)
            self.assertEqual(preset.get("top"), shipped[key]["top"], key)

    def test_the_page_keeps_no_second_copy_of_a_canonical_lens(self):
        """No canonical key may be branched on for MEMBERSHIP.

        Scoped to `lensRows`, deliberately. Branching on the active lens elsewhere is
        legitimate — `useBuckets = preset === "ai_shadow_debt"` picks a mark shape, and
        forbidding that would be a test demanding worse code. What must not come back is a
        second answer to "which names are in this lens", because that is the copy that
        drifted. Tone and custom lenses stay page-native here on purpose: tone belongs to
        screener_lab, which has no canonical preset to consume.
        """
        body = re.search(r"function lensRows\(pool\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "lensRows not found — did it move or get renamed?")
        for key in sc.PRESETS:
            self.assertNotIn(key, body.group(1),
                             "lensRows still decides membership for the canonical lens "
                             "{!r} instead of evaluating its shipped rule".format(key))

    def test_every_field_the_rules_test_travels_on_a_row(self):
        """A rule testing a field the payload drops would silently fail every row."""
        needed = set()
        for preset in sc.PRESETS.values():
            needed.update(m for m, _op, _v in preset["require"])
            needed.add(preset["rank"][0])
        alias = dict(re.findall(r'(\w+):"(\w+)"',
                                re.search(r'const CANON_FIELD = \{(.*?)\};',
                                          self.html, re.S).group(1)))
        row = self.payload["rows"][0]
        for metric in sorted(needed):
            field = alias.get(metric, metric)
            self.assertIn(field, row,
                          "rule metric {!r} maps to row field {!r}, which the payload does "
                          "not ship".format(metric, field))

    def test_the_cap_is_applied_after_the_filters(self):
        """Slicing before filtering made a capped lens report an empty result as a fact
        about the market: `most_volatile` plus a beta filter returned nothing while eight
        names qualified."""
        self.assertRegex(
            self.html,
            r"canonicalRows[\s\S]{0,400}?top\s*\?\s*out\.matches\.slice",
            "the top-N cap must slice what survived the filters")


class TheUnscreenableAreReported(unittest.TestCase):
    """`apply_preset` splits rows it could not judge into a no-data bin and the server
    renders them by name. The page must do the same: dropping them silently lets "did not
    qualify" and "could not be asked" share one absence — 14 names on the safety lens."""

    def test_the_page_carries_a_no_data_bin(self):
        html = _page()
        self.assertIn("noData", html)
        self.assertRegex(html, r"function lensNoData\(",
                         "the page must expose the rows it could not screen")

    def test_it_is_rendered_not_merely_computed(self):
        self.assertIn("could not be", _page(),
                      "an unscreenable name that is computed but never shown is still hidden")


class TheDerivedConstantsAreRecomputed(unittest.TestCase):
    """A constant computed from another constant is pinned by arithmetic, never by a
    comment. The stack breakpoint was the literal 770 in three places — 1100 x 0.7 worked
    out by hand — so changing the shell zoom would have left the geometry adapting while
    all three silently became wrong."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def _zoom(self):
        m = re.search(r"\.shell\{[^}]*zoom:\s*([0-9.]+)", self.html, re.S)
        self.assertIsNotNone(m, "no zoom found on .shell")
        return float(m.group(1))

    def test_the_script_derives_the_breakpoint_rather_than_hardcoding_it(self):
        self.assertRegex(
            self.html, r"const STACK_MQ = \"\(max-width:\" \+ stackBreakpointPx\(\)",
            "STACK_MQ must be derived from the declared layout width and the live zoom")

    def test_the_css_breakpoint_equals_the_declared_width_times_the_zoom(self):
        declared = int(re.search(r"const MIN_TREE_CSS_PX = (\d+)", self.html).group(1))
        expected = round(declared * self._zoom())
        found = {int(px) for px in re.findall(r"@media \(max-width:(\d+)px\)", self.html)}
        self.assertTrue(found, "no stacking media query found")
        self.assertEqual(
            found, {expected},
            "the CSS stacking breakpoint(s) {} do not equal {} x {} = {}; the tree would "
            "keep positioning panes the CSS has already stacked".format(
                sorted(found), declared, self._zoom(), expected))


class ThePageDoesNotRestateWhatPythonDefines(unittest.TestCase):
    def test_the_shadow_severity_table_lives_only_in_python(self):
        """This table existed three times — in stock_screener, in the buckets mock, and in
        this page. It is ordinal editorial judgement; two copies cannot disagree quietly."""
        html = _page()
        self.assertNotIn("const SHADOW_SEVERITY = {", html)
        self.assertNotIn("const SHADOW_RANK = {", html)
        self.assertIn("r.shadow_severity_rank", html,
                      "severity must be read from the row the server ships")

    def test_the_severity_rank_travels_on_every_row(self):
        payload = research_ui._screener_combined_draft_payload()
        rows = payload["rows"]
        self.assertTrue(rows, "no rows to check")
        for row in rows:
            self.assertIn("shadow_severity_rank", row, row.get("tk"))


class TheToneLensesAreAllReachable(unittest.TestCase):
    """Every tone lens must appear in the source map, or selecting it leaves the toggle on
    another source and the lens prints "no coverage" for names it admitted on coverage."""

    def test_every_tone_lens_has_a_source(self):
        html = _page()
        lenses = set(re.findall(r"(\w+_tone)\s*:", html))
        mapped = set(re.findall(r"(\w+_tone)\s*:\s*\"", html))
        missing = sorted(lenses - mapped)
        self.assertEqual(missing, [], "tone lenses with no mapped source: {}".format(missing))

    def test_the_social_lens_maps_to_the_combined_source(self):
        self.assertRegex(_page(), r"social_tone\s*:\s*\"all\"",
                         "the combined lens must select the combined source")


if __name__ == "__main__":
    unittest.main()
