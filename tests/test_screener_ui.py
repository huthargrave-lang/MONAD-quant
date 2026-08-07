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
        """The scale is declared once as --shell-zoom and referenced by .shell. Resolved
        here rather than matched as a literal, so this test keeps measuring the real number
        after the rule stopped containing one."""
        m = re.search(r"--shell-zoom:\s*([0-9.]+)", self.html)
        self.assertIsNotNone(m, "no --shell-zoom declared")
        rule = re.search(r"\.shell\{[^}]*\}", self.html, re.S)
        self.assertIsNotNone(rule, "no .shell rule")
        self.assertIn("var(--shell-zoom)", rule.group(0),
                      ".shell no longer reads the declared scale, so this number is not the "
                      "one the page renders at")
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


class TheSeriesPaletteIsCategorical(unittest.TestCase):
    """The price chart draws one line per ticker, and the only thing a line's colour says is
    WHICH ticker. That is a categorical job, and it was being done with colours borrowed from
    two ramps that mean something else: `--accent` and `--ord-3` are two steps of one blue
    (#6ba7f0 / #74aaee in dark), so two of five lines were the same blue on screen."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def _palette(self):
        block = re.search(r"const PRICE_COLORS = \[(.*?)\];", self.html, re.S).group(1)
        return re.findall(r"var\((--[\w-]+)\)", block)

    def test_the_palette_borrows_from_neither_the_ordinal_nor_the_semantic_ramp(self):
        borrowed = sorted(
            v for v in self._palette()
            if v.startswith("--ord-") or v in ("--accent", "--good", "--warning",
                                               "--serious", "--critical"))
        self.assertEqual(
            borrowed, [],
            "the series palette reuses {} — a ramp whose steps are chosen to sit CLOSE "
            "together (ordinal) or to mean good/bad (semantic), neither of which is what a "
            "ticker's line means".format(borrowed))

    def test_no_two_series_share_a_variable(self):
        palette = self._palette()
        self.assertEqual(len(palette), len(set(palette)),
                         "two series would be drawn in one colour: {}".format(palette))

    def test_every_series_variable_is_defined_in_both_themes(self):
        """A variable defined only in the dark block leaves the light board drawing that line
        in the browser's default (black), silently colliding with the selected line."""
        dark = re.search(r"prefers-color-scheme: dark\)\{(.*?)\n  \}", self.html, re.S).group(1)
        light = re.search(r":root\{(.*?)\n\}", self.html, re.S).group(1)
        for var in self._palette() + ["--cat-on", "--cat-rest"]:
            self.assertRegex(light, re.escape(var) + r"\s*:", "{} missing (light)".format(var))
            self.assertRegex(dark, re.escape(var) + r"\s*:", "{} missing (dark)".format(var))

    def test_the_cohort_cap_is_the_palette_length(self):
        """Two independent numbers would let the cohort outgrow the palette, and `i % length`
        would then draw two names in one colour — which does not look like a bug."""
        self.assertIn("const PRICE_COHORT_MAX = PRICE_COLORS.length;", self.html)
        self.assertRegex(self.html, r"function priceCohort\(cap\)\{\s*\n\s*const max = "
                                    r"cap \|\| PRICE_COHORT_MAX;",
                         "priceCohort must default to the derived cap, not a literal")


class TheSelectedSeriesSeparates(unittest.TestCase):
    """Selecting a name has to change the picture. It used to move opacity 1 -> 0.72 on the
    other lines, a step too small to see, so clicking a name looked like nothing happened."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def test_the_picked_line_is_drawn_last(self):
        """SVG paints in document order, so a dimmed line emitted after the picked one draws
        over the very line the pick was meant to bring forward."""
        self.assertRegex(
            self.html,
            r"drawn\.filter\(p => !p\.on\)[\s\S]{0,120}?drawn\.filter\(p => p\.on\)",
            "the unpicked paths must be concatenated before the picked one")

    def test_nothing_outside_the_cohort_can_be_lit(self):
        """`selected` — and a stale entry in PRICE_LIT — can name a ticker that draws no
        line. Treating one as lit dims every series and highlights none, which reads as a
        broken chart rather than as no selection."""
        body = re.search(r"function priceLit\(cohort\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "priceLit must take the cohort it is resolving against")
        self.assertRegex(
            body.group(1),
            r"PRICE_LIT\.filter\(tk => cohort\.indexOf\(tk\) !== -1\)",
            "an explicit toggle set must still be narrowed to the current cohort")
        self.assertRegex(
            body.group(1),
            r"cohort\.indexOf\(selected\) !== -1",
            "a pin outside the cohort must not be treated as lit")

    def test_white_is_reserved_for_a_lone_selection(self):
        """Two white lines are two lines the reader cannot tell apart — the same collision
        the categorical palette was introduced to end. White is the max-contrast value, so it
        only separates when exactly one line holds it."""
        self.assertRegex(self.html, r"const solo = lit\.length === 1 \? lit\[0\] : null;")
        self.assertRegex(
            self.html,
            r'\(on && solo === x\.tk\) \? "var\(--cat-on\)" : priceColor\(k\)',
            "a lit line may only take --cat-on when it is the ONLY lit line")

    def test_untouched_means_every_series_is_lit(self):
        """"I have not chosen" is not "I chose nothing". Untouched, the chart lights every
        series; the page auto-pins its first row, so reading that pin as a choice opened the
        chart with one line lit and four dimmed — a highlight nobody asked for."""
        body = re.search(r"function priceLit\(cohort\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertRegex(body, r"return cohort\.slice\(\);",
                         "the untouched default must light the whole cohort")
        self.assertRegex(body, r"if\(PRICE_LIT_TOUCHED\) return",
                         "an explicit toggle set must win over the default")
        self.assertRegex(
            self.html, r"function pinTicker\(tk\)\{ selected = tk; PIN_IS_DELIBERATE = true; \}",
            "only a reader's pin may narrow the chart; the payload's fallback assigns "
            "`selected` directly and must not")


class TheArrangementMenuIsWired(unittest.TestCase):
    """Every entry in the menu must build a tree. A key with no branch in `arrangeTree`
    returns null, `arrangeBoard` returns early, and the button is a control that does nothing
    when pressed — indistinguishable from a board that was already in that arrangement."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.keys = re.findall(r'\{key:"(\w+)"', cls.html)

    def test_every_menu_key_has_a_branch(self):
        branches = set(re.findall(r'if\(kind === "(\w+)"\)', self.html))
        missing = [k for k in self.keys if k not in branches]
        self.assertEqual(missing, [], "arrangements with no tree: {}".format(missing))

    def test_no_branch_is_unreachable_from_the_menu(self):
        branches = re.findall(r'if\(kind === "(\w+)"\)', self.html)
        orphan = [b for b in branches if b not in self.keys]
        self.assertEqual(orphan, [], "trees no menu entry can reach: {}".format(orphan))

    def test_no_two_arrangements_declare_the_same_pictogram(self):
        """Two entries drawing one picture are one entry wearing two names — and since
        `sameTree` highlights the FIRST match, the second could never light up."""
        # Whitespace-normalised: `grid`'s list is line-wrapped, so a raw comparison would
        # call two identical lists different purely because one of them was reformatted.
        boxes = [re.sub(r"\s+", "", b)
                 for b in re.findall(r'boxes:\[([^\]]*(?:\][^\]]*)*?)\]\}', self.html)]
        self.assertEqual(len(boxes), len(self.keys),
                         "found {} box lists for {} arrangements — the pictogram regex has "
                         "drifted from the menu".format(len(boxes), len(self.keys)))
        dupes = sorted({b for b in boxes if boxes.count(b) > 1})
        self.assertEqual(dupes, [], "two arrangements declare identical box lists: "
                                    "{}".format(dupes))


class TheOfferedWindowsAreOnesTheDataCanFill(unittest.TestCase):
    """A window the payload cannot fill would relabel whatever it has as a period it is not —
    "1 year" drawn over 126 daily closes is six months wearing a year's name, which is the
    absent-as-zero defect in the time axis."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def test_a_window_is_offered_only_if_a_series_is_longer_than_it(self):
        self.assertRegex(
            self.html, r"PRICE_WINDOWS\.filter\(w => w\.bars < have\)",
            "every candidate window must be tested against the longest loaded series")

    def test_all_names_its_own_length(self):
        self.assertRegex(self.html, r'"all \(" \+ have \+ " bars\)"',
                         "the 'all' option must say how many bars it actually is")

    def test_a_stale_selection_is_dropped_when_the_payload_shrinks(self):
        self.assertRegex(
            self.html,
            r"if\(priceWindow != null && !opts\.some\(w => w\.bars === priceWindow\)\)"
            r"\s*priceWindow = null;",
            "a window that the new payload cannot fill must fall back to all")

    def test_the_window_is_cut_before_the_indexing(self):
        """Indexing to a close that is scrolled off the left would put the 100 line off the
        chart and make every percentage answer a different question."""
        body = re.search(r"const series = picks\.map\(p => \{(.*?)\}\);", self.html, re.S)
        self.assertIsNotNone(body)
        self.assertRegex(body.group(1), r"windowed\(p\.s\)[\s\S]*100 \* v / w\[0\]")


class TheWatchlistIsIndependentOfTheLens(unittest.TestCase):
    """The lens says what passes a screen now; the watchlist says what is being followed. If
    it did not survive a lens change, a filter change and a reload, it would be a second
    selection wearing a different name."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def test_it_stores_tickers_and_not_rows(self):
        """Storing rows would freeze a P/E from whenever the name was added and redisplay it
        as current after the next fetch."""
        self.assertRegex(self.html, r"filter\(x => typeof x === \"string\"\)",
                         "only tickers may be persisted")
        self.assertRegex(self.html, r"WATCHED\.map\(tk => \(\{tk: tk, r: ROWS\.find",
                         "the row must be looked up fresh on every draw")

    def test_a_kept_name_missing_from_the_snapshot_is_named_not_dropped(self):
        self.assertIn("not in this snapshot", self.html,
                      "a watched ticker the payload no longer carries must be reported")

    def test_it_shows_lens_membership_rather_than_filtering_by_it(self):
        """A watchlist that hid everything the lens excludes would just be the lens again."""
        self.assertIn("is-in", self.html)
        self.assertRegex(self.html, r'inLens\.has\(o\.tk\) \? "in lens" : "outside"')


class TheCentredPanelsClearTheirAnchor(unittest.TestCase):
    def test_centring_removes_the_inline_coordinates(self):
        """An inline left/top beats any class rule, so a panel opened anchored once would keep
        those coordinates and then translate away from centre by half its own size."""
        html = _page()
        block = re.search(r'if\(pop\.hasAttribute\("data-center"\)\)\{(.*?)\n  \}',
                          html, re.S)
        self.assertIsNotNone(block, "the centred-panel branch is gone")
        self.assertIn('removeProperty("left")', block.group(1))
        self.assertIn('removeProperty("top")', block.group(1))

    def test_the_lens_builder_is_centred(self):
        self.assertRegex(_page(), r'id="lensForm"[^>]*data-center',
                         "the lens builder is a form, not a tooltip — it must centre")


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
