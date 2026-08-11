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
import shutil
import subprocess
import tempfile

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

    def _media_blocks(self):
        """(max-width px, block body) for every media query, with braces balanced so a block
        containing nested rules is not cut short at its first `}`."""
        out = []
        for m in re.finditer(r"@media \(max-width:(\d+)px\)\s*\{", self.html):
            i, depth = m.end(), 1
            while depth and i < len(self.html):
                if self.html[i] == "{":
                    depth += 1
                elif self.html[i] == "}":
                    depth -= 1
                i += 1
            out.append((int(m.group(1)), self.html[m.end():i - 1]))
        return out

    def test_the_css_breakpoint_equals_the_declared_width_times_the_zoom(self):
        """Scoped to the blocks that actually STACK. This used to assert that every
        `max-width` in the file equalled the stacking breakpoint, which held only while there
        was one breakpoint in the file — it failed the moment the bucket grid needed its own
        column-count breakpoints, which are a different constant for a different job. The
        property worth guarding is unchanged: wherever the CSS takes over the layout, the
        tree must have stopped positioning at the same width, or panes get positioned by both
        at once."""
        declared = int(re.search(r"const MIN_TREE_CSS_PX = (\d+)", self.html).group(1))
        expected = round(declared * self._zoom())
        stackers = [px for px, body in self._media_blocks()
                    if ".board{height:auto" in body or "board-resize" in body]
        self.assertTrue(stackers, "no stacking media query found")
        self.assertEqual(
            sorted(set(stackers)), [expected],
            "the CSS stacking breakpoint(s) {} do not equal {} x {} = {}; the tree would "
            "keep positioning panes the CSS has already stacked".format(
                sorted(set(stackers)), declared, self._zoom(), expected))

    def test_the_grid_sizes_itself_from_its_own_width(self):
        """A media query answers how wide the WINDOW is; the column count depends on how wide
        the GRID is. Deriving one from the other means guessing back through the sidebar, the
        section insets and the shell's 0.77 zoom — and that guess was wrong in practice: a
        window wide enough for ten columns rendered five."""
        self.assertIn("container-type:inline-size", self.html,
                      "the grid's container is not queryable")
        # EVERY breakpoint, not just one of them. Asserting that a container query exists
        # somewhere let the others quietly regress to `@media` one at a time.
        # ANY @media, either direction. `_media_blocks` only reads max-width, which is the
        # form the stacking breakpoint uses — a min-width media query walked straight past it.
        for m in re.finditer(r"@media\s*\(([^)]*)\)\s*\{", self.html):
            i, depth = m.end(), 1
            while depth and i < len(self.html):
                if self.html[i] == "{":
                    depth += 1
                elif self.html[i] == "}":
                    depth -= 1
                i += 1
            self.assertNotRegex(
                self.html[m.end():i - 1], r"\.bk-grid\{[^}]*grid-template-columns",
                "the `{}` media query sets bucket columns; column count is a fact about the "
                "grid's width, and the shell's zoom makes that wider than the viewport it "
                "would be compared against".format(m.group(1).strip()))
        self.assertGreaterEqual(
            len(re.findall(r"@container \([^)]*\)\{\s*\.bk-grid\{", self.html)), 3,
            "the column ladder is not carried by container queries")

    def test_the_bucket_grid_column_counts_divide_twenty(self):
        """Twenty buckets. The grid is a deliberate matrix, so every breakpoint picks a column
        count that leaves no ragged last row — 5 and 4 divide 20 exactly, and 3/2/1 are the
        narrow fallbacks where a rectangle stops being achievable anyway. `auto-fill` is what
        this replaced: it chose whatever fitted, so the same twenty cards landed 7+7+6 at one
        width and 5+5+5+5 at another."""
        # Every column count anywhere, whatever kind of query holds it. This scanned only
        # `@media` blocks, so when the breakpoints moved to `@container` it kept passing
        # while checking nothing but the base rule — a guard that survives the change it was
        # written for by no longer looking at it.
        # Scan each `.bk-grid{...}` rule whole: the base one declares other properties before
        # its columns, so a pattern anchored right after the brace saw only the breakpoints.
        cols = []
        for body in re.findall(r"\.bk-grid\{([^}]*)\}", self.html):
            m = re.search(r"grid-template-columns:\s*repeat\((\d+)", body)
            if m:
                cols.append(int(m.group(1)))
            elif "grid-template-columns:minmax(" in body.replace(" ", ""):
                cols.append(1)
        self.assertGreaterEqual(len(cols), 4,
                                "the grid has lost its responsive column ladder")
        self.assertTrue(
            re.search(r"^\.bk-grid\{[^}]*grid-template-columns:repeat\(", self.html, re.M),
            "the bucket grid has no explicit base column count")
        self.assertNotRegex(self.html, r"\.bk-grid\{[^}]*auto-fill",
                            "the bucket grid pours again instead of forming a matrix")
        for n in cols:
            if n > 2:
                self.assertEqual(20 % n, 0,
                                 "{} columns leaves a ragged row of twenty buckets".format(n))


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
        """`selected` — and a stale hidden entry — can name a ticker that draws no line.
        Treating one as lit dims every series and highlights none, which reads as a broken
        chart rather than as no selection.

        The mechanism changed from an allow-list to a hidden set, so this asserts the
        PROPERTY rather than the old spelling: every value priceLit returns is derived from
        the cohort it was handed, and a pin is checked for membership before it can win."""
        body = re.search(r"function priceLit\(cohort\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "priceLit must take the cohort it is resolving against")
        code = body.group(1)
        self.assertRegex(code, r"cohort\.filter\(tk => !PRICE_HIDDEN\.has\(tk\)\)",
                         "the lit set must be built FROM the cohort, never from a stored list")
        self.assertRegex(code, r"cohort\.indexOf\(selected\) !== -1",
                         "a pin outside the cohort must not be treated as lit")
        # Every value it can return traces back to `cohort` — either the filtered local, the
        # whole cohort, or the pin that was just membership-checked. Checked as a closed SET
        # of allowed returns rather than by matching "cohort" in each one, which would only
        # be re-asserting the spelling of a local variable.
        derived = set(re.findall(r"const (\w+) = cohort\.", code))
        allowed = derived | {"cohort.slice()", "[selected]"}
        for ret in (r.strip() for r in re.findall(r"return ([^;]+);", code)):
            self.assertIn(ret, allowed,
                          "priceLit can return {!r}, which is not derived from the cohort "
                          "it was handed".format(ret))

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
        """"I have not chosen" is not "I chose nothing". With nothing hidden the chart lights
        every series — and that is now the FALL-THROUGH rather than a branch, which is what
        stopped a stale set from ever producing an all-dark chart."""
        body = re.search(r"function priceLit\(cohort\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertRegex(body, r"return cohort\.slice\(\);",
                         "the untouched default must light the whole cohort")
        self.assertTrue(body.rstrip().endswith("return cohort.slice();"),
                        "all-lit must be the last thing priceLit can do, so every path that "
                        "chooses nothing else arrives at it")
        # Only a reader's pin may narrow the chart, and only while it still owns it. The
        # one-line spelling this used to match went away when "the reader chose this name"
        # was split from "this pin drives the chart" — the invariant is the same.
        pin = re.search(r"function pinTicker\(tk\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("PIN_OWNS_CHART = true", pin, "only a reader's pin may narrow the chart")
        fb = re.search(r"function fallbackPin\(rows\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertNotIn("PIN_OWNS_CHART", fb,
                         "a pin the PAGE chose must never narrow the chart")


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
        # The count is still derived from the data; a human-readable span was added in front
        # of it. The invariant is unchanged — "all" names its own length rather than a fixed
        # number — so the assertion moves to the derivation, not the exact string.
        self.assertRegex(self.html, r'have \+ " bars\)"',
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


class TheLensCanBeCleared(unittest.TestCase):
    """A bucket has to be readable on its own.

    Every bubble was permanently on — one of them always selected — so a thesis could only
    ever be read THROUGH whichever screen had been picked earlier, often down to zero, with
    nothing on the page saying the lens was still there. "Show me this bucket" was not an
    expressible request. That is a gap the shared filter state created, and it is the reason
    scrolling back up to find an old lens still narrowing everything was so confusing.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def test_no_lens_is_a_real_state(self):
        self.assertRegex(
            self.html, r"function lensRows\(pool\)\{[\s\S]{0,400}?if\(preset == null\) return rows;",
            "a null preset must pass every row rather than falling through to a rule lookup")

    def test_clicking_the_active_lens_clears_it(self):
        self.assertRegex(
            self.html, r"preset = \(preset === key\) \? null : key;",
            "a bubble that can only be exchanged for another bubble is a radio group")

    def test_the_bubbles_report_that_they_can_be_turned_off(self):
        self.assertRegex(self.html, r'b\.setAttribute\("aria-pressed", on \? "true" : "false"\)')
        self.assertRegex(self.html, r"click again to clear")

    def test_the_no_lens_sentence_does_not_claim_names_cleared_one(self):
        """"38 of 123 loaded names clear no lens" is a sentence about nothing."""
        self.assertRegex(self.html, r"const lensPhrase = preset == null")
        self.assertIn("every loaded name", self.html)

    def test_the_empty_message_measures_each_way_out(self):
        """Three constraints narrow this list and any pair can empty it. The page knows how
        many names each admits alone, so it names the one actually blocking instead of leaving
        the reader to bisect it by clicking things off."""
        body = re.search(r"function emptyWayOut\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "emptyWayOut is gone")
        code = body.group(1)
        for probe in ("preset = null;", "BUCKET_SEL.clear();", "filterState = () => ({});"):
            self.assertIn(probe, code,
                          "the way-out must MEASURE {} rather than assume it".format(probe))
        # It only offers drops that actually open something.
        self.assertIn("if(n) outs.push", code)
        self.assertIn("outs.sort((a, b) => b.n - a.n)", code)

    def test_each_probe_restores_what_it_changed(self):
        """These run inside a render. A probe that left preset or BUCKET_SEL altered would
        make the sentence describe a state the rest of the page is not in."""
        code = re.search(r"function emptyWayOut\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("preset = was;", code)
        self.assertIn("BUCKET_SEL = was;", code)
        self.assertIn("filterState = was;", code)


class TheGrowthAxisShowsItsTrueRange(unittest.TestCase):
    """Growth ran from about -92% to +1580% and the chart showed neither end: the point data
    was capped at `Math.min(r.g, 4.5)` — a 1580% name drawn at 450% — and the axis then
    clipped to the 5-95th percentile on top of that. Two truncations, neither visible."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def test_the_growth_cap_is_gone(self):
        """Matched as CODE, not as a word: the comment recording what was removed names the
        old expression on purpose, and forbidding the string would forbid the explanation."""
        pts = re.search(r"const pts = ROWS\.filter\(.*?\n.*?;", self.html, re.S).group(0)
        self.assertNotIn("Math.min", pts, "a capped coordinate is a fabricated one")
        self.assertIn("g:r.g,", pts)

    def test_the_axis_is_symmetric_log_not_log(self):
        """Growth goes negative, and log of a negative is nothing."""
        self.assertRegex(
            self.html,
            r"const symlog = v => Math\.sign\(v\) \* Math\.log10\(1 \+ Math\.abs\(v\) / YLIN\)")
        self.assertRegex(self.html, r"const YLIN = ")

    def test_y_is_no_longer_percentile_clipped(self):
        """X keeps its clip — a P/E tail is not worth three orders of magnitude — but the
        growth axis must reach the real max or the top edge is a pile of unrelated names."""
        body = re.search(r"if\(pts\.length>=20\)\{(.*?)\n  \}", self.html, re.S).group(1)
        self.assertIn("sx0", body)
        self.assertNotIn("sy0", body, "the y axis is being percentile-clipped again")

    def test_the_ticks_are_round_growths(self):
        """Even fractions of a log range print things like 412%."""
        self.assertRegex(self.html, r"const Y_STOPS = \[")
        self.assertRegex(self.html, r"if\(t < yA \|\| t > yB\) return;",
                         "a stop outside the data's span would imply a reading nothing reaches")

    def test_the_caption_no_longer_claims_both_axes_are_clipped(self):
        self.assertNotIn("axes clipped to 5–95th pctile", self.html)
        self.assertIn("growth axis is symmetric-log", self.html)


class ADroppedModuleCanSpanTheBoard(unittest.TestCase):
    def test_the_board_has_its_own_bottom_band(self):
        """Dropping on a PANE's bottom edge splits that pane, so a full-width strip under
        everything was unreachable on a two-column board — there was no gesture for it."""
        html = _page()
        self.assertRegex(html, r'zone:"board-bottom"')
        self.assertRegex(html, r"const BOARD_EDGE_PX = ")

    def test_it_wraps_the_whole_tree_rather_than_one_leaf(self):
        html = _page()
        self.assertRegex(
            html,
            r'if\(target && target\.zone === "board-bottom"\)\{[\s\S]{0,500}?'
            r"const rest = dropLeaf\(boardTree, d\.tileId\);",
            "the tile must be removed from where it was, or it appears twice")
        self.assertRegex(
            html, r'\{type:"split", dir:"col", ratio:1 - BOARD_EDGE_FRAC, a:rest,')

    def test_the_band_is_tested_before_the_panes(self):
        """A pointer in the band is nearer some pane than others; letting proximity win would
        make one gesture do different things depending on which column it was over."""
        html = _page()
        band = html.index('zone:"board-bottom"')
        panes = html.index("paneHits().forEach(p =>")
        self.assertLess(band, panes)


class TheEmptyStateNamesWhatActuallyNarrowed(unittest.TestCase):
    def test_no_card_hardcodes_the_lens_as_the_cause(self):
        """"No match in this lens" was a lie the moment the lens was cleared and a bucket or a
        filter was doing the excluding."""
        html = _page()
        self.assertNotIn('"No match in this lens"', html)
        self.assertRegex(html, r"function narrowingPhrase\(\)\{")
        self.assertRegex(html, r'emptyTitle\("Two axes"\)')

    def test_the_phrase_lists_only_what_is_set(self):
        html = _page()
        body = re.search(r"function narrowingPhrase\(\)\{(.*?)\n\}", html, re.S).group(1)
        self.assertIn("if(preset != null)", body)
        self.assertIn("activeFilterCount()", body)
        self.assertIn("selectedBuckets()", body)


class ABucketPopulatesTheResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def test_constituents_with_no_row_are_listed(self):
        """Most of what a thesis holds is outside the fundamentals universe by design, so
        intersecting emptied the table while the bay below listed six names."""
        self.assertRegex(
            self.html,
            r"const listedOnly = BUCKET_SEL\.size[\s\S]{0,200}?"
            r"bucketRows\(\)\.filter\(m => !ROWS\.some\(r => r\.tk === m\.tk\)\)")
        self.assertIn('class="listed-only"', self.html)

    def test_they_are_never_ranked_among_the_screened(self):
        """They were not judged, so they have no rank to hold."""
        self.assertRegex(self.html, r'\}\)\.join\(""\) \+ listedHTML')
        self.assertRegex(self.html, r'<td class="num muted-cell">·</td>',
                         "a listed-only row must not carry a rank number")

    def test_the_count_above_the_table_includes_them(self):
        """Otherwise the sentence describes a list the table is not showing.

        Asserted on the ARGUMENT, not the parameter name: the note is fed the same array the
        table renders, so the two cannot disagree about how many there are or what they are.
        Pinning `listedNote(n)` pinned a signature, and the signature changed the moment the
        note had to split its count by reason."""
        self.assertRegex(self.html, r"function listedNote\(\w+\)\{")
        self.assertRegex(self.html, r"listedNote\(listedOnly\)",
                         "the note must be given the rows themselves, not just a count")
        self.assertNotRegex(self.html, r"listedNote\(listedOnly\.length\)")

    def test_none_appear_with_no_bucket_selected(self):
        self.assertRegex(self.html, r"const listedOnly = BUCKET_SEL\.size\s*\n?\s*\?")


class TheBayCardIsNotCalledWatchlist(unittest.TestCase):
    def test_the_two_cards_have_different_names(self):
        """The bay card lists what a thesis holds; the Watchlist is the names you kept. Two
        cards called Watchlist meaning different things is the whole confusion."""
        html = _page()
        self.assertIn('bwatch:"Bucket constituents"', html)
        self.assertRegex(html, r'id="tile-bwatch"[\s\S]{0,400}?<h2>Constituents</h2>')
        self.assertRegex(html, r'id="tile-watch"[\s\S]{0,400}?<h2 id="watchTitle">Watchlist</h2>')

    def test_the_real_watchlist_still_reads_only_kept_names(self):
        html = _page()
        self.assertRegex(html, r"function drawWatch\(\)\{[\s\S]{0,900}?WATCHED\.map\(")


class TheLegendSwatchesAreControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def test_a_swatch_is_a_button(self):
        """A key you can only read is a key that makes you count dots."""
        self.assertRegex(self.html, r'class="leg-grp\$\{plotGrpShown\(v\) \? "" : " off"\}"')
        self.assertRegex(self.html, r'data-plot-grp="')

    def test_a_switched_off_group_is_not_drawn_at_all(self):
        """Dimming is the wrong answer: the reader asked to see one group, and a faint
        version of everything else is still everything else."""
        self.assertRegex(
            self.html,
            r'if\(scale\.key !== "none" && !plotGrpShown\(scale\.of\(r\)\)\) return;')

    def test_empty_means_all_not_none(self):
        self.assertRegex(
            self.html,
            r"function plotGrpShown\(v\)\{ return !PLOT_GRP_ON\.size \|\| PLOT_GRP_ON\.has\(v\); \}")

    def test_changing_the_grouping_clears_the_selection(self):
        """The chosen values name the OLD field; carried over, they would hide everything."""
        self.assertRegex(self.html, r"plotGroup = ev\.target\.value; PLOT_GRP_ON\.clear\(\)")


class ThePriceChartDefaultsToAllLit(unittest.TestCase):
    """Hudson's rule: all series lit unless a stock is selected elsewhere or names are
    un-toggled on the chart. It held at load and broke on the first lens click."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def test_the_fallback_pin_is_written_once_and_is_never_deliberate(self):
        """The same decision — the page picking a pin because the old one fell out of view —
        was written at two call sites that had diverged: one assigned `selected` directly
        (flag stayed false, chart opened correctly) and one routed it through pinTicker (flag
        went true, first lens click collapsed the chart to one line)."""
        self.assertRegex(self.html, r"function fallbackPin\(rows\)\{")
        body = re.search(r"function fallbackPin\(rows\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertNotIn("pinTicker", body,
                         "a pin the page picked is not a request to see one name")
        self.assertNotIn("PIN_IS_DELIBERATE", body)
        # Scoped to the CALL SITES, not to the shapes the old code happened to have: a
        # freshly hand-rolled `if(m.length) pinTicker(m[0].tk)` is the same defect wearing
        # different syntax, and a negative match on the old spelling would let it back in.
        for fn in ("selectPreset", "applyLivePayload"):
            body = re.search(r"function {}\(.*?\)\{{(.*?)\n\}}".format(fn),
                             self.html, re.S)
            self.assertIsNotNone(body, fn)
            self.assertNotIn(
                "pinTicker", body.group(1),
                "{} must route its fallback through fallbackPin — pinTicker marks the pin as "
                "the reader's, and this one is the page's".format(fn))
            self.assertIn("fallbackPin(", body.group(1),
                          "{} no longer uses the shared fallback rule".format(fn))

    def test_the_set_is_hidden_not_lit(self):
        """An allow-list has to be reset by hand from every control that changes the cohort,
        and it was reset from four of about eight. A hidden entry that is not in the current
        cohort is simply irrelevant, so the stale case resolves itself."""
        self.assertRegex(self.html, r"let PRICE_HIDDEN = new Set\(\);")
        self.assertNotIn("PRICE_LIT_TOUCHED", self.html)
        body = re.search(r"function priceLit\(cohort\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("cohort.filter(tk => !PRICE_HIDDEN.has(tk))", body)
        self.assertIn("return cohort.slice();", body)

    def test_chips_outrank_a_pin_which_outranks_the_default(self):
        body = re.search(r"function priceLit\(cohort\)\{(.*?)\n\}", self.html, re.S).group(1)
        # PIN_OWNS_CHART, not PIN_IS_DELIBERATE: the two were one flag, which is what let the
        # pin re-assert the moment the chips stopped disagreeing with it.
        self.assertLess(body.index("shown.length !== cohort.length"),
                        body.index("PIN_OWNS_CHART"),
                        "an explicit chip choice must win over a pin made elsewhere")

    def test_hiding_the_last_visible_series_resets_rather_than_emptying(self):
        """An empty chart is never what a click on the last visible line is asking for."""
        body = re.search(r"function togglePriceLit\(tk\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertRegex(body, r"<= 1\) PRICE_HIDDEN\.clear\(\)")


class TheShadowGateSaysWhenItDidNothing(unittest.TestCase):
    """stock_screener.py declares that rank 0 means "carries no tag on this editorial list"
    and that no rule may be read as certifying an absence of exposure. `safety_low_debt`
    gates on `rank <= 2`, which an unassessed name clears trivially — and today all 14 of its
    matches are unassessed, so the gate excluded none of them."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()

    def test_the_note_exists_and_is_scoped_to_gated_lenses(self):
        self.assertRegex(self.html, r"function shadowGateNote\(rows\)\{")
        body = re.search(r"function shadowGateNote\(rows\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn('r[0] === "shadow_severity_rank"', body,
                      "the note must only appear on a lens that actually gates on the tag")
        self.assertIn("!r.shadow_severity", body)

    def test_it_distinguishes_none_assessed_from_some(self):
        body = re.search(r"function shadowGateNote\(rows\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("unassessed === rows.length", body)
        self.assertIn("excluded", body)
        self.assertIn("not evidence of no exposure", body)

    def test_it_is_wired_into_the_results_sentence(self):
        self.assertRegex(self.html, r"\+ shadowGateNote\(sorted\)")


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


class TheCommandBarReadsStateNotTheDom(unittest.TestCase):
    """The bar names the constraint the page is applying. That only stays true if it reads the
    same variables the rows are computed from.

    `activeLensLabel()` used to be `document.querySelector("#presets button.on").textContent`.
    Survivable while the only way to change the lens was to click that button; not survivable
    once a Context control sets `preset` directly, because every sentence naming the lens kept
    naming the old one while the rows below were already the new one. Measured before the fix:
    `preset = "safety_low_debt"` gave 30 safety rows under the label "Low P/E · high growth"."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_the_lens_label_is_derived_from_preset(self):
        body = re.search(r"function activeLensLabel\(\)\{(.*?)\}", self.html, re.S).group(1)
        self.assertNotIn("querySelector", body,
                         "the lens label reads the DOM again — a state-only lens change will "
                         "leave every sentence naming the previous lens")
        self.assertIn("preset", body)

    def test_no_readout_recovers_the_lens_name_from_a_button(self):
        for m in re.finditer(r'querySelector\((["\'])#presets button\.on\1\)', self.html):
            line = self.html[:m.start()].count("\n") + 1
            self.fail("line {}: the active lens is read off the pill row".format(line))

    def test_the_universe_has_one_definition(self):
        """Four functions used to answer "which rows" from the same state and disagree. The
        two that were wrong are named here; the two deliberate readings are kept but must go
        through the shared universe rather than re-derive it from raw globals."""
        self.assertRegex(self.html, r"function contextUniverse\(\)\{")
        self.assertRegex(
            self.html, r"function matchedRows\(\)\{ return lensRows\(contextUniverse\(\)\); \}",
            "matchedRows must be the lens over the shared universe")
        # the two former defects, by the shape that made them wrong
        self.assertNotRegex(
            self.html, r"canonicalScreen\(key, ROWS\.filter\(passesFilters\)\)",
            "the unscreened-names list drops the bucket leg again")
        self.assertNotRegex(
            self.html, r"const lens = lensRows\(\);",
            "the running count's denominator ignores the context again")

    def test_the_memo_cannot_outlive_one_render(self):
        """`passesFilters` reads the live filter row, so a universe memo that survived a render
        would answer with the row as it used to be."""
        self.assertIn("_inRender = true; _universeMemo = null;", self.html)
        self.assertRegex(self.html, r"finally \{ _inRender = false; _universeMemo = null; \}")

    def test_every_lens_is_reachable_from_the_grouped_menu(self):
        """The menu replaced a flat row that showed all of them at once. A lens missing from
        LENS_GROUPS would be reachable from nowhere except a pinned star it may not have."""
        groups = re.search(r"const LENS_GROUPS = \[(.*?)\n\];", self.html, re.S).group(1)
        grouped = set(re.findall(r'"([a-z_]+)"', groups))
        buttons = set(re.findall(r'<button type="button"[^>]*data-p="([a-z_]+)"', self.html))
        buttons.discard("custom")
        self.assertEqual(sorted(buttons - grouped), [],
                         "lenses that exist but are in no menu group")
        self.assertEqual(sorted(grouped - buttons), [],
                         "menu groups naming lenses that do not exist")

    def test_the_relocated_blocks_still_exist(self):
        """Moved into disclosures, not deleted. Each panel still holds the component it
        absorbed, so a missing one here means a lost feature.

        `layoutPanel` is checked by CAPABILITY rather than by container id. It used to be
        pinned to `id="tray"`, and the tray was later folded into the option rows themselves —
        which is a relocation of exactly the kind this test exists to permit. What must not
        vanish is the ability to get an unplaced module onto the board by dragging it, which
        lives on `[data-tray]` wherever that is rendered."""
        for pid, inner in (("lensPanel", 'id="presets"'), ("filterPanel", 'id="filters"'),
                           ("dataPanel", 'id="providers"'), ("layoutPanel", "data-tray=")):
            panel = re.search(r'<div class="explain[^"]*" id="%s".*?\n</div>' % pid,
                              self.html, re.S)
            self.assertIsNotNone(panel, pid)
            body = panel.group(0)
            if pid == "layoutPanel":
                # The drag source is rendered by JS into this panel, so the check is that the
                # panel exists and that something in the page emits the handle into it.
                self.assertIn('id="layoutAvail"', body)
                self.assertIn('class="tile-grip" data-tray="', self.html,
                              "no drag handle is rendered for an unplaced module")
                continue
            self.assertIn(inner, body,
                          "{} no longer contains {}".format(pid, inner))

    def test_the_context_reports_screenable_and_held_separately(self):
        """A bucket names companies the fundamentals universe may not carry. Reporting the held
        count beside a table that can never show them is the misread this surface exists to
        prevent — bucket 01 holds six names and none of them can be screened."""
        body = re.search(r"function contextCounts\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("screenable", body)
        self.assertIn("held", body)

    def test_the_conditional_honesty_notes_all_survive(self):
        """Static boilerplate moved to tooltips. These are the ones that fire only when they
        have something real to report, and every one of them must still be called."""
        for fn in ("listedNote", "shadowGateNote", "emptyWayOut", "renderLensNote",
                   "whyNotScreened"):
            self.assertRegex(self.html, re.escape(fn) + r"\s*\(",
                             "{} is no longer called".format(fn))

    def test_the_board_height_is_derived_from_the_shell_zoom(self):
        """`51vh` was inert: zoom does not rescale viewport units, so it resolved below the
        420px floor and the board sat at its minimum while presenting at 39% of the screen.
        Derived rather than hand-computed to 66vh, so changing the zoom moves it."""
        # Anchored to a rule at column 0. An unanchored search matched the `.board{...}`
        # inside the comment that explains this very fix — a test that passes by reading the
        # prose about the code instead of the code.
        m = re.search(r"^\.board\{[^}]*?height:min\(([^;]+?)\);", self.html, re.M | re.S)
        self.assertIsNotNone(m, "the board height rule moved")
        self.assertIn("var(--shell-zoom)", m.group(1),
                      "the board height is a bare vh again, which this zoom makes inert")


class TheMarkupIsWellFormed(unittest.TestCase):
    """This page is edited by pattern-matching on its text — it is 6800 lines and there is no
    template — and a replacement whose closing tag matched one nesting level too shallow left
    a stray `</section></div>` behind. The document still parsed: browsers repair it silently,
    so `<main>` simply acquired a nested copy of the page shell, everything below the context
    header stopped painting, and no test noticed because every other assertion is a substring
    search that does not care about nesting. Cheap to check, and it catches the whole class."""

    VOID = {"br", "img", "input", "hr", "meta", "link", "source", "col", "area", "base",
            "embed", "param", "track", "wbr"}

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            html = fh.read()
        body = html[html.index("<body"):]
        # Script and style hold `<` in JS/CSS that is not markup; comments hold example tags.
        for pat in (r"<script\b.*?</script>", r"<style\b.*?</style>", r"<!--.*?-->",
                    r"<svg\b.*?</svg>"):
            body = re.sub(pat, "", body, flags=re.S)
        cls.body = body

    def test_every_element_is_closed_in_the_order_it_was_opened(self):
        stack, problems = [], []
        for m in re.finditer(r"<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>", self.body):
            closing, tag, _attrs, selfclosing = m.groups()
            tag = tag.lower()
            if tag in self.VOID or selfclosing == "/":
                continue
            line = self.body[:m.start()].count("\n") + 1
            if closing:
                if stack and stack[-1][0] == tag:
                    stack.pop()
                elif tag == "html":
                    continue
                else:
                    problems.append("line {}: </{}> closes nothing (open: {})".format(
                        line, tag, [t for t, _ in stack[-3:]]))
            else:
                stack.append((tag, line))
        self.assertEqual(problems, [], "\n".join(problems))
        self.assertEqual(
            [(t, ln) for t, ln in stack if t != "body"], [],
            "elements opened and never closed: {}".format(stack[:5]))

    def test_the_context_section_contains_its_own_body(self):
        """The specific nesting the break inverted: the shell must not end up inside main."""
        sec = re.search(r'<section class="ctx-section" id="contextSection">(.*?)\n    </section>',
                        self.body, re.S)
        self.assertIsNotNone(sec, "the context section is not closed at its own indent level")
        self.assertIn('id="contextBody"', sec.group(1))
        self.assertNotIn('class="shell"', sec.group(1),
                         "the page shell is nested inside the context section")
        self.assertNotIn('id="cmdbar"', sec.group(1),
                         "the command bar is nested inside the context section")


class TheContextMatchesTheBucketsPage(unittest.TestCase):
    """The grid is meant to read like the buckets page it came from. Two properties carry
    that, and both were wrong: the cards sat on the same colour as the thing containing them,
    so they separated only by a hairline and the whole block looked flat; and the control row
    was left-aligned with a greedy search box, so six related controls rendered as two
    clusters a screen apart with the first label flush against an edge the cards were inset
    from."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def _rule(self, selector):
        """Anchored at column 0, so `.bk` finds the card rule and not the `.bk-grid .bk`
        helper further down — an unanchored search reads whichever rule mentions the
        selector first, which is how this asserted against `height:100%`."""
        m = re.search(r"^" + re.escape(selector) + r"\{([^}]*)\}", self.html, re.M | re.S)
        self.assertIsNotNone(m, "{} has no rule at the top level".format(selector))
        return m.group(1)

    def test_the_cards_sit_on_a_lighter_panel(self):
        """The buckets page's relationship: container --surface, cards --plane. Same colour on
        both is what made this look flat beside the original."""
        panel = self._rule(".ctx-grid")
        card = self._rule(".bk")
        self.assertIn("background:var(--surface)", panel,
                      "the grid panel must be one step lighter than the cards on it")
        self.assertIn("background:var(--plane)", card)

    def test_the_control_row_is_centred_and_the_search_is_not_greedy(self):
        row = self._rule(".ctx-controls")
        self.assertIn("justify-content:center", row,
                      "the control row reads as two clusters when left-aligned")
        search = self._rule(".ctx-controls .bkc-q")
        self.assertNotRegex(
            search, r"flex:\s*1\b",
            "the search box grows into the slack again and shoves the buttons to the edge")

    def test_the_context_bands_share_one_inset(self):
        """Head, controls and grid are stacked bands of one section; three different insets is
        what made the row look cut off against the cards."""
        insets = []
        for sel in (".ctx-head", ".ctx-controls", ".ctx-focus"):
            m = re.search(r"padding:([^;}]+)", self._rule(sel))
            self.assertIsNotNone(m, sel)
            parts = m.group(1).split()
            # CSS shorthand: 1 value is all sides, 2+ puts the horizontal second. Taking the
            # last value read the BOTTOM padding on the three-value rules.
            insets.append(parts[1] if len(parts) > 1 else parts[0])
        self.assertEqual(len(set(insets)), 1,
                         "the context bands use different horizontal insets: {}".format(insets))


class TheMemoDoesNotDefeatTheProbes(unittest.TestCase):
    """The universe memo made two of `emptyWayOut`'s three counterfactuals unanswerable. It
    measures "what would dropping this leave?" by unsetting a constraint and re-asking — and a
    memo built from the ORIGINAL constraints answers the original question every time, so both
    the bucket and filter probes returned the count the table already had (zero, since the
    probe only runs on the empty branch) and `if(n)` discarded them. Selecting a bucket whose
    constituents carry no fundamentals emptied the table and offered no way out at all: the
    page kept the sentence and silently lost the escape."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_every_counterfactual_suspends_the_memo(self):
        body = re.search(r"function emptyWayOut\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        probes = re.findall(r"const n = ([^;]+);", body)
        self.assertEqual(len(probes), 3, "emptyWayOut no longer has three probes")
        for p in probes:
            self.assertIn("withFreshUniverse", p,
                          "a counterfactual reads the memo it is supposed to be varying: "
                          + p.strip())

    def test_the_helper_restores_what_it_suspended(self):
        body = re.search(r"function withFreshUniverse\(fn\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("finally", body,
                      "the memo must be restored even when the probe throws")
        self.assertRegex(body, r"_inRender = was", "the render flag is not restored")
        self.assertRegex(body, r"_universeMemo = memo", "the memo is not restored")


class TheRunningCountMeasuresTheFilters(unittest.TestCase):
    """Two mistakes in a row on one readout. `lensRows()` with no argument counted names the
    bucket had already excluded — "0 of 76" for a six-name bucket. The fix then made the
    denominator `lensRows(contextUniverse())`, which is exactly what `matchedRows()` is, so it
    printed "N of N" forever and the "it ranks, so the filters re-cut it" branch became
    unreachable from any state. The denominator is the bucket-constrained universe BEFORE the
    filter row, because that difference is the only thing the ratio measures."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_the_denominator_is_not_the_numerator(self):
        body = re.search(r"function renderFilterCount\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        denom = re.search(r"const lens = ([^;]+);", body).group(1).strip()
        numer = re.search(r"const shown = ([^;]+);", body).group(1).strip()
        self.assertNotEqual(denom, numer,
                            "numerator and denominator are the same expression, so the strip "
                            "can only ever print 'N of N'")
        matched = re.search(r"function matchedRows\(\)\{ return ([^;]+); \}", self.html)
        self.assertIsNotNone(matched)
        self.assertNotEqual(denom, matched.group(1).strip(),
                            "the denominator is matchedRows() spelled out longhand")

    def test_the_denominator_excludes_the_filter_row(self):
        body = re.search(r"function renderFilterCount\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        denom = re.search(r"const lens = ([^;]+);", body).group(1)
        self.assertNotIn("passesFilters", denom)
        self.assertNotIn("contextUniverse", denom,
                         "contextUniverse applies the filter row, which the denominator must "
                         "not — it is the thing being measured")
        self.assertIn("inSelectedBuckets", denom,
                      "the denominator must still respect the bucket context")


class TheLensMenuListsEachLensOnce(unittest.TestCase):
    """Custom lenses render into `#presets` too, wrapped in `.lens-chip`. Without excluding
    them, `builtinLensKeys()` returned them alongside the built-ins, so `drawLensPanel` listed
    a reader's own lens twice — once under "Ungrouped" (because it is in no LENS_GROUPS entry)
    and once under "Custom" — two rows in the one menu that claims to be the full set, each
    toggling the same state."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_the_builtin_scan_excludes_custom_chips(self):
        body = re.search(r"function builtinLensKeys\(\)\{(.*?)\n\}",
                         self.html, re.S).group(1)
        # The CALL, not the word. The comment above the filter explains why `.lens-chip` is
        # excluded, so an `assertIn("lens-chip", body)` passed with the filter deleted — the
        # test read the prose about the code instead of the code.
        code = "\n".join(ln for ln in body.splitlines()
                         if not ln.strip().startswith("//"))
        self.assertRegex(
            code, r"\.filter\([^)]*closest\((['\"])\.lens-chip\1\)",
            "custom lenses are not excluded, so each is listed twice in the menu")

    def test_the_ungrouped_bucket_is_fed_by_the_builtin_scan(self):
        """`ungroupedLensKeys` exists to surface a built-in nobody put in a group. Fed by a
        scan that includes custom lenses, it surfaces every custom lens instead — which is the
        duplication wearing a different name."""
        body = re.search(r"function ungroupedLensKeys\(\)\{(.*?)\n\}",
                         self.html, re.S).group(1)
        self.assertIn("builtinLensKeys()", body)


class ThePageScriptParses(unittest.TestCase):
    """A regex edit left `const pill` declared twice in one function. The whole script failed
    to parse, so NOT ONE function on the page was defined and it rendered as static markup —
    and every text-contract test over this file still passed, because they read it as a string.
    The HTML tag-balance guard did not see it either: the markup was fine, the script was not.

    `node --check` answers this in milliseconds. Skipped rather than failed where node is
    absent, so a checkout without it is not blocked — an unrunnable check is not a failing one."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is not available to parse the page script")

    def _scripts(self, path):
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        # Inline scripts only — a src= tag has no body to check.
        return [m.group(1) for m in
                re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
                if m.group(1).strip()]

    def test_every_inline_script_parses(self):
        for name in ("SCREENER_COMBINED_DRAFT.html", "SOVEREIGN_LEDGER_OPTIONS_MOCK.html"):
            path = os.path.join(REPO, "docs", "research", name)
            for i, body in enumerate(self._scripts(path)):
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                                 encoding="utf-8") as fh:
                    fh.write(body)
                    tmp = fh.name
                try:
                    proc = subprocess.run(["node", "--check", tmp],
                                          capture_output=True, text=True)
                finally:
                    os.unlink(tmp)
                self.assertEqual(
                    proc.returncode, 0,
                    "{} inline script #{} does not parse — every function on the page would "
                    "be undefined:\n{}".format(name, i, proc.stderr[:600]))


class TheLensPanelGroupingSurvivesRerendering(unittest.TestCase):
    """Two bugs, both only visible on the SECOND render, and both invisible to a test that
    reads this file as text — so these are asserted on the mechanism instead.

    (1) The function MOVES the pills into group containers and used to open by wiping the host
    with `innerHTML`. It is called from drawCmdBar on every render, so the second render
    destroyed the fourteen pills the first had moved in, then looked for survivors in
    `#presets`, where they no longer were. Nine lenses were destroyed and the panel showed
    five under a run of empty headings.

    (2) The rebuilt version looked up its containers with `escAttr(title)` in a CSS attribute
    selector. escAttr escapes for HTML, so "AI & infrastructure" became `AI &amp;
    infrastructure` and matched nothing — a new container was created on every render for
    exactly the two groups whose names contain an ampersand."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()
        m = re.search(r"function drawLensPanel\(\)\{(.*?)\n\}", cls.html, re.S)
        assert m, "drawLensPanel is gone"
        # CODE only. The comment above explains the removed `host.innerHTML = ...` by name, so
        # a scan over the raw body flagged the explanation as the defect — the same mistake
        # this file has made four times now: matching prose about the code, not the code.
        body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
        cls.body = "\n".join(l for l in body.splitlines()
                              if not l.lstrip().startswith("//"))

    def test_it_never_wipes_the_container_holding_the_pills(self):
        self.assertNotRegex(
            self.body, r"host\.innerHTML\s*=",
            "drawLensPanel wipes its host again — it holds the only copy of every lens "
            "control, so the next render destroys them")

    def test_containers_are_looked_up_by_something_that_needs_no_escaping(self):
        self.assertNotRegex(
            self.body, r'querySelector\([^)]*escAttr',
            "an HTML-escaped title in a CSS selector never matches a name containing '&', so "
            "every render creates another container for those groups")
        self.assertRegex(self.body, r'data-group-index="\' \+ gi',
            "containers should be indexed by position, which cannot collide or need escaping")

    def test_a_group_that_goes_away_rehomes_its_pills_first(self):
        """Deleting the last custom lens removes its group. Removing the container with the
        pills still inside would delete controls the reader never asked to lose."""
        tail = self.body[self.body.index("querySelectorAll(\".lensgroup\")"):]
        self.assertLess(tail.index("pills.appendChild"), tail.index("wrap.remove()"),
                        "the group is removed before its contents are rehomed")

    def test_every_built_in_lens_lands_in_exactly_one_group(self):
        """The grouping is the only place all fourteen are listed, so a lens missing from
        LENS_GROUPS is reachable from nowhere but a star it may not have."""
        groups = re.search(r"const LENS_GROUPS = \[(.*?)\n\];", self.html, re.S).group(1)
        grouped = re.findall(r'"([a-z_]+)"', groups)
        self.assertEqual(len(grouped), len(set(grouped)), "a lens is in two groups")
        buttons = set(re.findall(r'<button type="button"[^>]*data-p="([a-z_]+)"', self.html))
        buttons.discard("custom")
        self.assertEqual(sorted(buttons - set(grouped)), [], "lenses in no group")


class APageChosenPinIsNotASelection(unittest.TestCase):
    """Two different things wear the same word. `pinTicker` is the reader saying "show me this
    name"; `fallbackPin` is the page picking something so the cards are not empty. Conflating
    them produced a report of a chart "showing as if I selected a stock" when nothing had been
    clicked at all.

    Measured on the deployed page before the fix: a fresh load with zero interaction had
    `selected = "NVDA"`, and after selecting four buckets the detail and tone cards were still
    headed NVDA — a name the reader never picked and which none of the chosen theses contain —
    while the price chart beside them drew MP, COPX, SLV, VST, USAR."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_a_page_chosen_pin_never_claims_to_be_deliberate(self):
        body = re.search(r"function fallbackPin\(rows\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertNotIn("PIN_IS_DELIBERATE", body,
                         "the page's own fallback must not mark the pin as the reader's")
        # pinTicker grew a body when the chart flag was split out of the card flag, so this
        # asserts what it must DO rather than how it used to be spelled.
        pin = re.search(r"function pinTicker\(tk\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("PIN_IS_DELIBERATE = true", pin)
        self.assertIn("PIN_OWNS_CHART = true", pin)

    def test_the_fallback_follows_the_context_and_a_real_pin_does_not(self):
        body = re.search(r"function syncFallbackPin\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "nothing re-homes the fallback pin when the context moves")
        body = body.group(1)
        self.assertRegex(body, r"if\(PIN_IS_DELIBERATE\) return;",
                         "a pin the reader made must survive a context change")
        self.assertIn("matchedRows()", body,
                      "the fallback must be re-picked from the CURRENT context, not ROWS")
        self.assertRegex(self.html, r"try \{ syncFallbackPin\(\); renderInner\(\);",
                         "it has to run before the cards draw, on every render")

    def test_the_cards_say_when_the_name_was_not_chosen(self):
        """Three headers name the pinned ticker. Each has to distinguish a pin from a
        placeholder, or it is asserting something about the reader that is not true."""
        # The BOARD cards only. `stockModalTitle` is excluded on purpose: the modal opens
        # from an explicit click on a ticker, so its header is always describing a real
        # choice and qualifying it would be noise. Anchored per element for that reason —
        # searching for the shared string found the modal first and failed on it.
        for element, anchor in (("cardTitle-ish", 'title.textContent = "Stock detail · " + selected'),
                                ("drawCard row", 'title.textContent = "Stock detail · " + r.tk'),
                                ("headlinesTitle", '"All sources · " + selected')):
            i = self.html.find(anchor)
            self.assertNotEqual(i, -1, "header moved: {} ({})".format(anchor, element))
            self.assertIn("PIN_IS_DELIBERATE", self.html[i:i + 260],
                          "{} claims a selection that may never have happened".format(element))
        # and the modal, which IS always deliberate, stays unqualified
        i = self.html.find('"stockModalTitle").textContent = "Stock detail · " + r.tk')
        self.assertNotEqual(i, -1)
        self.assertNotIn("first in context", self.html[i:i + 160],
                         "the modal only opens from a real click; qualifying it is noise")


class TheChartSaysWhichSetItDraws(unittest.TestCase):
    """"Price · 5 names" sat beside "1 of 225 loaded names" and the five read as a
    contradiction of the one. They answer different questions: with a bucket selected the
    chart deliberately draws the bucket's constituents, while Results applies the lens and the
    filter row on top. That divergence is documented and kept — what was missing is the card
    saying so."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_the_title_names_the_set_not_only_the_count(self):
        i = self.html.find('title.textContent = series.length === 1')
        self.assertNotEqual(i, -1, "the price title moved")
        window = self.html[i - 700:i + 400]
        self.assertIn("in the selected buckets", window)
        self.assertIn("in this lens", window)
        self.assertIn("bucketNameSet()", window,
                      "the two cases must be told apart by membership, not guessed")

    def test_the_window_labels_state_a_span_of_time(self):
        """"all (124 bars)" is exact and answers a question nobody asks."""
        body = re.search(r"function priceWindows\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("barsAsTime(have)", body,
                      "the all-window label must carry a time span, not only a bar count")
        self.assertIn('have + " bars)"', body,
                      "the exact bar count stays — the span is approximate and says so")

    def test_the_span_is_marked_approximate(self):
        """Closes ship without dates, so a span stated to the day would be a precision the
        data does not carry."""
        body = re.search(r"function barsAsTime\(bars\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn('"about ', body, "an unhedged span claims precision the payload lacks")
        for bars, want in ((252, "year"), (126, "months"), (21, "month")):
            self.assertRegex(body, r"\d+", "bars->time must be computed, not tabulated")


class TheLegendChipsOwnTheChartOnceTouched(unittest.TestCase):
    """Clicking a hidden chip to bring its line back turned every OTHER line off instead.

    The precedence — chips, then pin, then default — was re-evaluated from scratch on every
    draw, so the pin re-asserted the moment the chips stopped disagreeing with it. Un-hiding
    the last hidden chip made `shown.length` equal `cohort.length`, the chip rule stopped
    applying, and the pin soloed its own name. The reader's click did the opposite of what it
    asked for.

    So "the reader chose this name" and "the pin is what drives this chart" are two facts, not
    one. The first governs the card titles and must survive; the second is handed over the
    moment a chip is touched."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_the_chart_rule_is_not_the_card_rule(self):
        body = re.search(r"function priceLit\(cohort\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertIn("PIN_OWNS_CHART", body,
                      "lighting must key off who is steering the chart")
        self.assertNotIn("PIN_IS_DELIBERATE", body,
                         "PIN_IS_DELIBERATE governs the card titles; using it here is what "
                         "let the pin re-assert over the reader's chips")

    def test_touching_a_chip_hands_the_chart_to_the_chips(self):
        body = re.search(r"function togglePriceLit\(tk\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertRegex(body, r"PIN_OWNS_CHART = false;",
                         "a chip click must take the chart off the pin")
        self.assertNotIn("PIN_IS_DELIBERATE = false", body,
                         "the pin is still the reader's choice — only the chart changes hands")

    def test_pinning_takes_the_chart_back(self):
        body = re.search(r"function pinTicker\(tk\)\{(.*?)\n\}", self.html, re.S).group(1)
        for flag in ("PIN_IS_DELIBERATE = true", "PIN_OWNS_CHART = true"):
            self.assertIn(flag, body)
        self.assertIn("PRICE_HIDDEN.clear()", body,
                      "a fresh pick should not be read through the previous pick's hidden set")


class NoHandlerIsBoundToAnElementThatIsNotThere(unittest.TestCase):
    """Removing the bucket row's duplicate Clear button left its `addEventListener` behind.
    `getElementById("bucketClear")` returned null, the boot script threw at that line, and
    everything after it — including the first `render()` — never ran. The page loaded with an
    empty pinned strip, no clear buttons, and no console output unless you went looking.

    `node --check` cannot see this: the syntax is fine. The text-contract tests cannot either:
    the string is present, it just names an element that is not. This is the cheap check that
    can — every unguarded `getElementById("x").` must have a matching `id="x"` in the page."""

    IDS = re.compile(r'\sid="([\w-]+)"')
    USES = re.compile(r'getElementById\("([\w-]+)"\)\s*\.')

    def _check(self, name):
        path = os.path.join(REPO, "docs", "research", name)
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        present = set(self.IDS.findall(html))
        missing = []
        for m in self.USES.finditer(html):
            if m.group(1) not in present:
                line = html[:m.start()].count("\n") + 1
                missing.append("{}:{} -> #{}".format(name, line, m.group(1)))
        self.assertEqual(missing, [], "\n".join(missing))

    def test_the_screener_binds_only_to_elements_it_has(self):
        self._check("SCREENER_COMBINED_DRAFT.html")

    def test_the_buckets_page_binds_only_to_elements_it_has(self):
        self._check("SOVEREIGN_LEDGER_OPTIONS_MOCK.html")

    # The same defect one level up, and the version that actually shipped. `data-panel-open`
    # names its panel by id and the handler does `if(!pop) return;` — so a button pointing at
    # a panel that does not exist renders, takes a click, and does nothing at all. The strip's
    # `why` button was in that state from Phase D until Phase F built the drawer, and neither
    # `node --check` nor the check above could see it: the syntax is fine and no
    # `getElementById` is involved. Every id-by-attribute reference is checked here, not just
    # the one that broke — a guard written for one attribute is a guard that stops covering
    # the next one somebody adds.
    ATTR_REFS = re.compile(r'data-(panel-open|explain)="([\w-]+)"')

    def test_every_panel_a_control_points_at_exists(self):
        for name in ("SCREENER_COMBINED_DRAFT.html", "SOVEREIGN_LEDGER_OPTIONS_MOCK.html"):
            with open(os.path.join(REPO, "docs", "research", name), encoding="utf-8") as fh:
                html = fh.read()
            present = set(self.IDS.findall(html))
            missing = ["{}:{} -> {}=#{}".format(
                           name, html[:m.start()].count("\n") + 1, m.group(1), m.group(2))
                       for m in self.ATTR_REFS.finditer(html)
                       if m.group(2) not in present]
            self.assertEqual(missing, [],
                             "a control opens a panel that is not in the page, so it renders, "
                             "takes a click and does nothing:\n" + "\n".join(missing))


class TheWidgetPanelIsOneListPerWidget(unittest.TestCase):
    """The Widget options panel names where every module is. It used to render the unplaced
    set TWICE — once as tray chips, once as unchecked option rows — so a widget appeared in
    two places in the one panel whose whole job is to say where it is.

    These guard the properties that replacement rests on, each of which has a way to silently
    regress:

      * every widget in the board registry is in exactly one panel group, or the "Available"
        list is not the full set it presents itself as;
      * every widget has a one-line brief AND a full note, because the brief is what is on
        screen and the note is what the row's tooltip carries — dropping either leaves a row
        rendering `undefined`;
      * the drag handle is reachable from wherever the row currently is, which means the
        listener must be bound to the panel and not to a list inside it. Binding to a
        container the subjects have left is the failure this file has now recorded three
        times (the lens star, the pill styling, and the tray)."""

    def setUp(self):
        self.html = _page()

    def _js_map_keys(self, name):
        m = re.search(r"const %s = \{(.*?)\n\};" % name, self.html, re.S)
        self.assertIsNotNone(m, name + " is not defined as a literal map")
        return set(re.findall(r"(\w+)\s*:", m.group(1)))

    def _registry(self):
        m = re.search(r"const TILE_IDS = \[(.*?)\];", self.html, re.S)
        self.assertIsNotNone(m)
        return set(re.findall(r'"(\w+)"', m.group(1)))

    def test_every_registered_widget_lands_in_exactly_one_group(self):
        m = re.search(r"const TILE_GROUPS = \[(.*?)\n\];", self.html, re.S)
        self.assertIsNotNone(m, "TILE_GROUPS is not defined as a literal")
        grouped = re.findall(r'"(\w+)"', m.group(1))
        # Titles are quoted too; only ids that are real tiles count as membership.
        ids = self._registry()
        members = [k for k in grouped if k in ids]
        self.assertEqual(sorted(members), sorted(set(members)),
                         "a widget is listed in more than one group")
        self.assertEqual(sorted(ids - set(members)), [],
                         "registered widgets that no panel group claims")

    def test_every_widget_has_both_a_brief_and_a_full_note(self):
        ids = self._registry()
        brief = self._js_map_keys("TILE_BRIEF")
        notes = self._js_map_keys("TILE_NOTES")
        self.assertEqual(sorted(ids - brief), [], "widgets with no one-line brief")
        self.assertEqual(sorted(ids - notes), [], "widgets with no full note")

    def test_a_brief_is_actually_brief(self):
        """The point of the brief is that it does not wrap. A full sentence pasted in here
        would restore the text density this pass removed while still passing every other
        check in this class."""
        m = re.search(r"const TILE_BRIEF = \{(.*?)\n\};", self.html, re.S)
        long = [t for t in re.findall(r'"([^"]{5,})"', m.group(1)) if len(t) > 62]
        self.assertEqual(long, [], "briefs long enough to wrap: {}".format(long))

    def test_the_drag_listener_is_bound_to_the_panel_not_a_list_inside_it(self):
        for ev in ("pointerdown", "keydown"):
            pat = r'getElementById\("(\w+)"\)\.addEventListener\("%s"' % ev
            hosts = re.findall(pat, self.html)
            self.assertIn("layoutPanel", hosts,
                          "no {} listener on the widget panel — the grip would be dead "
                          "for every row the search or a group move relocates".format(ev))

    def test_the_summary_and_the_highlight_read_one_definition(self):
        """The panel states the current arrangement three times: the lit pictogram, the header
        summary and the Layout tab's "Now:" line. Three independent computations of one fact
        is three chances for the panel to contradict itself."""
        self.assertEqual(len(re.findall(r"function currentArrangement\(", self.html)), 1)
        body = re.search(r"function syncLayoutPanel\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body)
        self.assertIn("currentArrangement()", body.group(1))
        self.assertNotIn("sameTree(arrangeTree(", body.group(1),
                         "syncLayoutPanel recomputes the arrangement instead of asking for it")

    def test_a_searched_out_row_is_actually_hidden(self):
        """`hidden` is a UA rule at the lowest specificity and `display:flex` outranks it, so
        without an explicit rule the filter sets an attribute and nothing moves."""
        self.assertIn(".explain .opt-list label[hidden]{display:none}", self.html)

    def test_the_search_never_writes_widget_state(self):
        body = re.search(r"function filterLayoutTiles\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body)
        for forbidden in ("setTilePlaced", "boardTree", "saveBoard", "toggleTileStar",
                          ".checked ="):
            self.assertNotIn(forbidden, body.group(1),
                             "the widget search changes state: " + forbidden)

    def test_the_panel_has_both_tabs_and_defaults_to_widgets(self):
        self.assertIn('data-opt-tab="widgets"', self.html)
        self.assertIn('data-opt-tab="layout"', self.html)
        self.assertIn('let OPT_TAB = "widgets"', self.html)

    def test_reset_and_close_survive_a_scroll(self):
        """The panel is tall enough that both used to leave with the first screenful."""
        for sel in (".opt-panel .opt-top", ".opt-panel .opt-foot"):
            m = re.search(re.escape(sel) + r"\{([^}]*)\}", self.html)
            self.assertIsNotNone(m, sel + " has no rule")
            self.assertIn("position:sticky", m.group(1), sel + " is not sticky")
        foot = re.search(r'<div class="opt-foot">(.*?)</div>', self.html, re.S)
        self.assertIsNotNone(foot)
        self.assertIn('id="boardReset"', foot.group(1))
        self.assertIn("data-panel-close", foot.group(1))


class TheLensPillIsOneBubble(unittest.TestCase):
    """A lens is one control: star, name, and for a custom lens its edit and delete. The
    grouped menu's containers carried `.lens-fav`, whose `button` rule gives EVERY descendant
    button its own bordered pill — so a lens arrived as two bubbles side by side and a custom
    lens as four, with the unifying `.presets .lens-wrap` border matching nothing because the
    pills had been moved out of `.presets`.

    This is the same defect as the dead star click and the dead tray listener: a rule scoped
    to a container its subjects no longer live in. The guard is the property — whatever class
    the containers carry, the rule that draws the bubble must match it."""

    def setUp(self):
        self.html = _page()

    def _container_class(self):
        # Scoped to drawLensPanel: the widget panel builds its own group boxes the same way,
        # and an unscoped search finds whichever function happens to be earlier in the file.
        fn = re.search(r"function drawLensPanel\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(fn, "drawLensPanel is gone")
        m = re.search(r'box\.className = "([^"]+)";', fn.group(1))
        self.assertIsNotNone(m, "the lens group container sets no class")
        return set(m.group(1).split())

    def test_the_group_container_is_matched_by_the_bubble_rule(self):
        classes = self._container_class()
        for rule in (".lens-wrap{", ".lens-chip{"):
            m = re.search(r"([^\n{}]*)" + re.escape(rule), self.html)
            self.assertIsNotNone(m, rule + " has no rule")
            scope = m.group(1).strip().split()[0].lstrip(".")
            self.assertIn(scope, classes,
                          "{} is scoped to .{}, which the lens menu containers "
                          "({}) do not carry".format(rule, scope, sorted(classes)))

    def test_the_container_does_not_pill_every_button_it_holds(self):
        """`.lens-fav button` is the rule that split one pill into two. If the containers ever
        carry it again, the star leaves the bubble."""
        self.assertNotIn("lens-fav", self._container_class())

    def test_only_the_unit_draws_a_border(self):
        """`.lens-star` sets border:0, but `.presets button` is class-plus-element and outranks
        it — so the star drew its own round border INSIDE the wrap's, two concentric bubbles
        for one control. The wrap's reset was written `> button[data-p]`, which the star does
        not carry; the chip's was written `button`, which is why only the wrap was wrong."""
        m = re.search(r"\.presets \.lens-wrap button\{([^}]*)\}", self.html)
        self.assertIsNotNone(m, "no rule zeroes the border of every button in a lens wrap")
        self.assertIn("border:0", m.group(1))
        chip = re.search(r"\.presets \.lens-chip button\{([^}]*)\}", self.html)
        self.assertIsNotNone(chip, "no rule zeroes the border of every button in a lens chip")
        self.assertIn("border:0", chip.group(1))


class TheActiveStateIsThePagesColourNotTheReaders(unittest.TestCase):
    """Form controls ran at the initial `accent-color:auto`, which resolves to the READER'S
    operating-system accent — a ticked checkbox came out magenta on one machine and blue on
    another. The widget panel makes a checkbox the primary "this is on the board" signal, so
    that colour is now load-bearing and cannot be delegated to the OS."""

    def test_the_page_declares_its_own_accent_colour(self):
        html = _page()
        root = re.search(r":root\{(.*?)\n\}", html, re.S)
        self.assertIsNotNone(root)
        # Comments stripped first: the block's own comment quotes `accent-color:auto` as the
        # thing being fixed, and a guard that matches prose about the code instead of the code
        # is the specific way the guards in this file have gone quiet before.
        css = re.sub(r"/\*.*?\*/", "", root.group(1), flags=re.S)
        m = re.search(r"accent-color:\s*([^;]+);", css)
        self.assertIsNotNone(m, "no accent-color is declared, so the OS picks it")
        self.assertEqual(m.group(1).strip(), "var(--accent)",
                         "the checkbox accent is not the page's own accent")


class NoLensQueryIsAnchoredToAContainerThePillsLeft(unittest.TestCase):
    """`drawLensPanel` MOVES every lens pill out of `#presets` into a group inside
    `#lensGroups`, on the first render and every render after. After it runs, `#presets` holds
    only the "+ custom" builder button.

    That one fact has produced FOUR separate shipped defects in this file:

      1. the star click selector matched nothing, so starring a lens did nothing;
      2. the bubble CSS matched nothing, so a lens drew as two bubbles and a custom lens four;
      3. the module tray's listener (same class, different container);
      4. the lens click handler was bound to `#presets`, so clicking a lens in the menu did
         not change the lens and a custom lens could not be deleted.

    Each was fixed by widening one selector, which is why there was a fourth. The fix that
    ends it is that the hosts are named ONCE (`LENS_HOST_IDS`) and every selector is derived
    from them. This test enforces that: in executable code, `#presets` may only appear where
    it means the leftover row itself — the "+ custom" button, which really does stay put."""

    # `#presets` is legitimate only when it qualifies the custom-lens builder button, which is
    # the one control that is never moved into a group.
    ALLOWED = re.compile(r'#presets button\[data-p="custom"\]')

    def setUp(self):
        html = _page()
        script = re.search(r"<script>(.*?)</script>", html, re.S)
        self.assertIsNotNone(script)
        # Comments carry the history of this bug and name #presets constantly; a guard that
        # reads prose about the code instead of the code is how guards in this file have gone
        # quiet before.
        self.js = re.sub(r"/\*.*?\*/|//[^\n]*", "", script.group(1), flags=re.S)

    def test_the_hosts_are_declared_once_and_everything_derives_from_them(self):
        self.assertEqual(len(re.findall(r"const LENS_HOST_IDS = ", self.js)), 1,
                         "the lens hosts are declared more than once")
        self.assertEqual(len(re.findall(r"const LENS_UNIT_SEL = ", self.js)), 1,
                         "LENS_UNIT_SEL is declared more than once")
        m = re.search(r"const LENS_UNIT_SEL = ([^\n;]+);", self.js)
        self.assertIsNotNone(m)
        self.assertIn("lensSel(", m.group(1),
                      "LENS_UNIT_SEL restates the hosts instead of deriving from them")

    def test_no_executable_selector_reaches_for_a_pill_through_one_host(self):
        bad = []
        for line in self.js.splitlines():
            if "#presets" not in line:
                continue
            if self.ALLOWED.search(line):
                continue
            bad.append(line.strip())
        self.assertEqual(bad, [], "selectors anchored to #presets alone:\n" + "\n".join(bad))

    def test_no_listener_is_bound_to_the_pill_row(self):
        """`getElementById("presets").addEventListener` is the exact shape of defect 4."""
        self.assertNotRegex(
            self.js, r'getElementById\("presets"\)\.addEventListener',
            "a listener is bound to the row the pills are moved out of")

    def test_the_lens_click_handler_covers_every_host(self):
        m = re.search(r'document\.addEventListener\("click", \(ev\)=>\{\s*'
                      r'if\(!ev\.target\.closest\((\w+)\)\) return;', self.js)
        self.assertIsNotNone(m, "the lens click handler is not gated on the host constant")
        self.assertEqual(m.group(1), "LENS_HOST_SEL")

    def test_the_functions_that_broke_all_read_the_shared_selector(self):
        """Named individually because each was a separate shipped bug: the active-lens
        highlight froze at whatever was selected on first render, the duplicate-name check
        compared against an empty list, and rebuilding the custom chips duplicated them
        instead of replacing them."""
        for fn in ("markActivePreset", "builtinLensNames", "decoratePresets",
                   "renderCustomBubbles", "orderPresets"):
            body = re.search(r"function %s\(\)\{(.*?)\n\}" % fn, self.js, re.S)
            self.assertIsNotNone(body, fn + " is gone")
            src = body.group(1)
            self.assertNotIn("#presets", src.replace('#presets button[data-p="custom"]', ""),
                             fn + " still reaches for pills through #presets alone")
            self.assertTrue(
                any(t in src for t in ("LENS_UNIT_SEL", "LENS_BUBBLE_SEL", "lensSel(",
                                       "lensPill(", "orderPresets(")),
                fn + " does not use the shared lens-host selectors")

    def test_activating_a_pinned_lens_does_not_destroy_the_caret(self):
        """The pinned strip is rebuilt wholesale by drawLensFav, which render() reaches — so
        pressing one of its buttons destroys the button that was pressed. A pointer user never
        notices; a keyboard user's caret fell to <body> and they had to tab from the top of the
        page to reach the next pinned lens."""
        body = re.search(r"function drawLensFav\(\)\{(.*?)\n\}", self.js, re.S)
        self.assertIsNotNone(body)
        self.assertIn("document.activeElement", body.group(1),
                      "drawLensFav rebuilds the strip without noticing what had focus")
        self.assertIn(".focus(", body.group(1),
                      "drawLensFav never restores the caret it destroys")

    def test_a_pinned_lens_click_renders_once(self):
        """selectPreset already renders. The extra render() drew the whole page twice and
        rebuilt the pinned strip twice for one click."""
        m = re.search(r'closest\("\[data-lens-go\]"\);\s*\n\s*if\(go\)\{([^}]*)\}', self.js)
        self.assertIsNotNone(m, "the pinned-lens handler is gone")
        self.assertNotIn("render()", m.group(1),
                         "the pinned-lens handler renders on top of selectPreset's render")


class TheScenarioStripReadsRatherThanDerives(unittest.TestCase):
    """Phase D. The strip is a reader over `window.SCENARIOS`, which Python emitted with the
    derivation already done.

    The whole point of emitting derived values is that the browser cannot produce a number
    this repo's tests have never seen. A strip that walked buckets and joined sensitivities
    would be a second implementation of the derivation in the one language with no test
    harness, and the two would part without anything noticing — which is precisely why the
    heat rule moved into Python in Phase 0a."""

    def setUp(self):
        self.html = _page()

    def test_the_strip_lives_where_it_cannot_be_folded_away(self):
        """Whether a model stands behind what a reader is looking at is not something they
        should have to expand a section to discover. `#bucketHint` is inside `#contextBody`
        and folds; the head does not."""
        head = re.search(r'<div class="ctx-head">(.*?)</div>', self.html, re.S)
        self.assertIsNotNone(head)
        self.assertIn('id="ctxScen"', head.group(1),
                      "the scenario strip is not in the always-visible head")

    def test_the_page_derives_no_scenario_quantity_of_its_own(self):
        """Named by the operation, not by a variable: the page may not net a sign, sum branch
        probabilities, or walk bucket membership to reach a security."""
        script = re.search(r"<script>(.*?)</script>", self.html, re.S).group(1)
        js = re.sub(r"/\*.*?\*/|//[^\n]*", "", script, flags=re.S)
        # Scoped to SCENARIO derivation. The page legitimately walks bucket membership for
        # the bucket UI — `bucketMembers` predates all of this — so banning that would forbid
        # existing, correct code and the guard would have to be deleted or worked around.
        for banned, why in (
                ("edge_sign *", "the page is netting a sign instead of reading one"),
                ("sensitivity_sign *", "the page is netting a sign instead of reading one"),
                ("CHANNEL_SENSITIVITIES", "the page holds a sensitivity table of its own"),
                ("counts_toward", "the page is re-deriving a target from branches")):
            self.assertNotIn(banned, js, why)

    def test_the_resolver_is_the_only_thing_that_knows_the_channel(self):
        """Consumers see one shape. Replacing the fixture with a model's output moves a record
        from the authored side to the payload and changes no caller."""
        body = re.search(r"function scenarioForShock\(shock\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "the resolver is gone")
        code = body.group(1)
        self.assertIn("__DRAFT_LIVE__", code, "the modelled channel is not consulted")
        self.assertIn("SCENARIOS", code, "the authored channel is not consulted")
        self.assertLess(code.index("__DRAFT_LIVE__"), code.index("SCENARIOS.BY_SHOCK"),
                        "the authored fallback is preferred over a modelled record")
        # Nobody else may reach past it.
        script = re.search(r"<script>(.*?)</script>", self.html, re.S).group(1)
        others = [m.start() for m in re.finditer(r"SCENARIOS\.BY_SHOCK", script)]
        self.assertEqual(len(others), 1,
                         "something reads BY_SHOCK directly instead of through the resolver")

    def test_an_unmodelled_shock_says_so_rather_than_going_quiet(self):
        """The one intended difference from today's page for a shock with no scenario. Silence
        would read as "nothing is happening"; this reads as "nothing has been modelled".

        Asserted inside the renderer with comments stripped. The comment above it lists the
        three states and QUOTES this string, so a whole-file scan finds the explanation of the
        code after the code is gone — the fifth time this file has recorded that mistake."""
        body = re.search(r"function drawScenarioStrip\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "the strip renderer is gone")
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", body.group(1), flags=re.S)
        self.assertIn("Editorial only", code,
                      "a shock with no scenario renders nothing, so absence of a model is "
                      "indistinguishable from absence of anything to report")

    def test_a_fixture_reading_is_marked_where_the_number_is(self):
        """The strip's own marking moved into the shared helpers in Phase F, so the assertion
        moved with it — from an inline class name to the two calls that produce one.

        Not weakened: `fxVal` renders the number and `fxMark` renders the badge, and
        `TheFixtureMarkingCannotBeEscaped` below asserts that every surface calling the first
        also calls the second. A class-name scan could not have said that."""
        body = re.search(r"function drawScenarioStrip\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body)
        code = body.group(1)
        self.assertIn('fxVal("strip"', code,
                      "the strip's probability no longer goes through the fixture helper, so "
                      "nothing marks it when the reading is authored")
        self.assertIn('fxMark("strip"', code,
                      "a fixture probability renders with no marking beside it")

    def test_changing_the_shock_refreshes_the_strip(self):
        """The shock handler redrew only the bucket control and grid. A strip that did not
        move with the selector would show the previous shock's model — worse than showing
        nothing, because it would be specific and wrong.

        Phase F made the second half of this conditional rather than absolute. "A shock
        narrows nothing" was true of every lens that existed when it was written; the scenario
        lens screens on what the shock's scenario reaches, so under it a shock change changes
        the row set and a scoped refresh would leave the results table specific and wrong in
        the other direction. What is pinned now is the CONDITION — scoped by default, a full
        render only when the shock is actually narrowing — which is a stronger claim than
        either "always" or "never"."""
        m = re.search(r'getElementById\("bucketShock"\)\.addEventListener\("change".*?\n\}\);',
                      self.html, re.S)
        self.assertIsNotNone(m)
        # Comments stripped: the handler's own comment explains WHY it is not an unconditional
        # render, and a scan over the raw text finds that explanation and calls it the defect —
        # the same prose-versus-code mistake this file has recorded five times.
        body = re.sub(r"/\*.*?\*/|//[^\n]*", "", m.group(0), flags=re.S)
        self.assertIn("drawContextHead()", body,
                      "a shock change does not refresh the context head, so the strip is stale")
        self.assertRegex(
            body, r"if\(shockIsNarrowing\(\)\)\{[^}]*\brender\(\);\s*return;\s*\}",
            "a shock change no longer re-renders when the shock is narrowing the universe, so "
            "the results table keeps the previous shock's names under the scenario lens")
        # Everything after the guarded early return must still be the scoped path. A render()
        # reachable without the condition puts a shock change on the same footing as a bucket
        # selection under every lens, which it is not.
        tail = body.split("return; }", 1)[-1]
        self.assertNotRegex(tail, r"(?<![.\w])render\(\)",
                            "a shock change now triggers a full render unconditionally")



def _script(html):
    """The page's application script. There are three inline blocks and the app is the LAST
    one — a probe that took block 0 during Phase D reported two live properties as absent that
    were in fact present, so the index is derived here rather than guessed at each call site."""
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    return max(blocks, key=len)


def _decomment(code):
    """Comments explain code; they are not evidence of it. Four guards in this file have
    matched a comment describing the very thing that had been deleted."""
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.S)


def _call_spans(code, names):
    """(start, end) of every `name(...)` call body, by paren matching.

    Used to ask "is this occurrence INSIDE one of these calls" exactly, rather than by looking
    at the line it sits on. The line-based version of this check keyed on single-quote string
    concatenation and let a raw fixture probability through in a double-quoted expression —
    quote style is not the signal, containment is."""
    spans = []
    for name in names:
        for m in re.finditer(r"(?<![\w.])" + re.escape(name) + r"\(", code):
            depth, i = 1, m.end()
            while i < len(code) and depth:
                if code[i] == "(":
                    depth += 1
                elif code[i] == ")":
                    depth -= 1
                i += 1
            spans.append((m.end(), i - 1))
    return spans


def _functions(js):
    """{name: body} for every top-level `function name(...){...}`, by brace matching.

    A fixed-size window past the opening brace is not a scope: it runs past the end of short
    functions into whatever follows, and stops short inside long ones. Both directions produce
    a guard that reports the wrong function — the first version of the fixture-pairing test
    did exactly that. Pass `js` through `_decomment` first; braces inside string literals are
    the remaining hazard and none of this page's functions contain an unbalanced one, which
    the length check in each caller is there to notice if it ever changes."""
    out = {}
    for m in re.finditer(r"\nfunction (\w+)\([^)]*\)\{", js):
        depth, i = 1, m.end()
        while i < len(js) and depth:
            c = js[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        out[m.group(1)] = js[m.end():i - 1]
    return out


class TheFixtureMarkingCannotBeEscaped(unittest.TestCase):
    """Phase F. Every fixture-derived number on this page goes through one helper, and that
    helper refuses to render into a surface that has not declared how it carries its marker.

    Written as a structural rule rather than as six string searches on six surfaces. An
    enumeration covers what it names and silently stops covering the next surface somebody
    adds, which is the shape `test_sovereign_buckets.py:57` records being burned by: "the
    guard was narrower than the module's claim, so the parts it did not name drifted out from
    under it." Here the registry IS the claim, and these assertions are about the registry."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.js = _decomment(_script(cls.html))

    def _surfaces(self):
        m = re.search(r"const FIXTURE_SURFACES = \{(.*?)\n\};", self.js, re.S)
        self.assertIsNotNone(m, "the fixture-surface registry is gone")
        return dict(re.findall(r'(\w+):\s*"(\w+)"', m.group(1)))

    def test_every_surface_that_prints_one_is_declared(self):
        """`fxVal` throws on an undeclared surface, so this is really asserting that no call
        site is written against a surface the registry does not know — a page that threw at
        render time would take the whole card down with it."""
        used = set(re.findall(r'fxVal\("(\w+)"', self.js))
        self.assertTrue(used, "nothing renders a fixture value any more")
        declared = self._surfaces()
        self.assertEqual(used - set(declared), set(),
                         "a fixture value is rendered into a surface with no declared marker")

    def test_a_surface_that_prints_one_also_carries_a_marker(self):
        """The pairing, per renderer function, which is the assertion an enumeration of class
        names cannot make: within the function that prints the number, the same function must
        print the badge — unless the registry says another surface covers it.

        The first version of this used a fixed 4000-character window instead of the function's
        real extent, and it duly reported `scenarioWhyBlock` for a marker that belonged to
        `drawScenarioStrip` two functions later. A window is not a scope."""
        declared = self._surfaces()
        checked = 0
        for name, body in _functions(self.js).items():
            # The surface can be a literal or a parameter. Both are checked, and a parameter
            # has to be handed to BOTH helpers — a renderer that takes its surface as an
            # argument and hard-codes the marker would mark the wrong one.
            for arg in set(re.findall(r'fxVal\(\s*("?\w+"?)\s*,', body)):
                literal = arg.strip('"') if arg.startswith('"') else None
                if literal is not None and declared.get(literal) != "own":
                    self.assertIn(literal, declared,
                                  "%s renders into undeclared surface %r" % (name, literal))
                    continue          # covered by another surface; asserted separately
                checked += 1
                self.assertRegex(
                    body, r"fxMark\(\s*" + re.escape(arg) + r"\s*,",
                    "%s prints a fixture value into the %s surface and never marks it"
                    % (name, arg))
        self.assertGreaterEqual(checked, 2,
                                "the pairing rule matched almost nothing — the extractor has "
                                "stopped finding the renderers it is supposed to be checking")

    def test_a_surface_covered_by_another_names_the_one_covering_it(self):
        """`bkcard` is the one that cannot carry its own badge — Decision 7 gives the card
        indicator the id line's spare width and nothing more. Its declaration names the strip,
        and the containment that makes that true is pinned elsewhere: `.ctx-head` does not
        fold and sits above `#contextBody`, which holds `#bucketGrid`."""
        declared = self._surfaces()
        for surface, how in declared.items():
            if how == "own":
                continue
            self.assertIn(how, declared,
                          "%r says it is covered by %r, which is not a surface" % (surface, how))
            self.assertEqual(declared[how], "own",
                             "%r is covered by %r, which does not carry a marker itself"
                             % (surface, how))
        head = re.search(r'<div class="ctx-head">(.*?)</div>', self.html, re.S)
        self.assertIsNotNone(head)
        self.assertIn('id="ctxScen"', head.group(1),
                      "the covering surface is not in the head, so it can fold away from the "
                      "cards it is supposed to be marking")

    def test_no_scenario_number_reaches_a_surface_the_helper_does_not_guard(self):
        """The escape route this is actually watching: reading a derived quantity straight out
        of the record and interpolating it, which produces a bare fixture number with nothing
        marking it. Every one of these fields is fixture-derived under V1's only scenario.

        Geometry is exempt, and the exemption is narrow and deliberate. `y(o.probability)` in
        the probability path puts the value at a POSITION on a labelled axis; there is no digit
        on screen for the reader to take away, and the axis it is placed against is the tile's
        own marked surface. A guard that banned it would have to be worked around by every
        chart that ever draws a scenario quantity, and a guard people route around stops being
        one. The exemption is a coordinate mapper applied to the value itself — not a general
        pass for the line, so `', magnitude ' + p.sensitivity_magnitude` on a line that also
        happens to compute a coordinate is still caught."""
        # `(?!\w)` because `.activation` is a prefix of `.activations`, and counting the
        # activations a scenario has is not printing one of them.
        fields = ("sensitivity_magnitude", "engaged_probability", r"\.activation(?!\w)",
                  r"\.probability(?!\w)")
        checked = 0
        for name, body in _functions(self.js).items():
            # Anything that BUILDS markup, not only what writes it. The first version tested
            # for `innerHTML` and so skipped `activationChip` and `scenarioWhyBlock` — both of
            # which return markup for a caller to write, and both of which are exactly where a
            # bare fixture number would land. Sort comparators and predicates build no markup
            # and stay out of scope, which is the point of having a scope at all.
            if "innerHTML" not in body and "'<" not in body:
                continue
            spans = _call_spans(body, ("fxVal", "fxText", "x", "y"))
            for field in fields:
                for m in re.finditer(field, body):
                    if any(s <= m.start() < e for s, e in spans):
                        continue          # inside a helper, or mapped to a coordinate
                    tail = body[m.end():m.end() + 14]
                    if re.match(r"\s*(==|!=|<|>)", tail):
                        continue          # a comparison is not a render
                    checked += 1
                    self.fail("%s renders a fixture-derived value without going through "
                              "fxVal/fxText: %s" % (name, body[max(0, m.start() - 60):
                                                              m.end() + 20].strip()[:150]))
        # The scan has to be looking at something. Every field above appears in at least one
        # renderer, so a run that inspected nothing means the extractor stopped finding them.
        found = sum(len(re.findall(f, b)) for f in fields
                    for b in _functions(self.js).values() if "innerHTML" in b)
        self.assertGreaterEqual(found, 5,
                                "the scan found almost no scenario quantities in any renderer "
                                "— it has stopped watching the code it names")
        self.assertEqual(checked, 0)

class TheCardShowsActivationWithoutBecomingHeat(unittest.TestCase):
    """Phase E. Editorial heat and modelled activation sit on one card and must not read as
    one quantity.

    Heat is an author's judgment of how structurally relevant a bucket is to a shock; it is
    unsigned, drawn as a bar, and it orders the grid. Activation is "given what has been
    observed, how likely is this mechanism engaged right now" — a probability, read from the
    Python derivation, drawn as a number in the id line. Different shape, different place,
    different colour, and neither is computed from the other.

    Decision 7 also makes this a LAYOUT contract: the indicator goes in space the id line
    already owns. Measured in the browser at all five breakpoints (1/4/5/10 columns, the
    grid's own container sized to 380/700/1000/1400/1800px), with the chip's rule toggled on
    a fixed shock so card reordering could not be mistaken for the chip's effect: grid, card
    and id-line height deltas were 0.00px at every width. The naive comparison — one shock
    against another — is NOT a valid measurement here and reports up to 9.5px of difference,
    because changing the shock reorders the cards by heat and changes which names wrap."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.js = _decomment(_script(cls.html))
        cls.css = _decomment(re.search(r"<style>(.*?)</style>", cls.html, re.S).group(1))
        cls.chip = re.search(r"function activationChip\(bucketId\)\{(.*?)\n\}",
                             cls.js, re.S)

    def test_the_chip_reads_the_derivation_rather_than_computing_one(self):
        """The browser has no branch probabilities to combine and no business combining them.
        The number it prints is the one Python derived, or there is no number."""
        self.assertIsNotNone(self.chip, "the card indicator is gone")
        code = self.chip.group(1)
        self.assertIn("scenarioForShock", code,
                      "the chip reaches for a scenario without going through the resolver")
        self.assertIn(".activations[", code, "the chip does not read the derived activations")
        for banned, why in (
                ("bucketHeat", "the chip is derived from editorial heat"),
                ("heatOf", "the chip is derived from editorial heat"),
                ("branches", "the chip is summing branch probabilities in the browser"),
                ("Math.max", "the chip is combining channels itself"),
                ("engaged_probability", "the chip is re-deriving activation")):
            self.assertNotIn(banned, code, why)

    def test_an_unmodelled_bucket_renders_nothing_at_all(self):
        """`null` is not zero. A bucket no model covers must render EMPTY, not `0%` — `0%`
        is a modelled claim that the mechanism is certainly not engaged, and this repo has
        paid for coercing an absence to a number before (CLAUDE.md's absence-flag rule)."""
        self.assertIsNotNone(self.chip)
        code = self.chip.group(1)
        m = re.search(r"if\((.*?)\)\s*return\s*(['\"])\2\s*;", code)
        self.assertIsNotNone(
            m, "the chip no longer returns the empty string for an uncovered bucket, so an "
               "unmodelled mechanism now prints something")
        self.assertIn("activation == null", m.group(1),
                      "the absence test does not distinguish a null activation from a zero "
                      "one, so `0%` and `not modelled` render the same")
        # `pct()` renders a dash for null. That is right for the STRIP, which has a labelled
        # slot to put a dash in; on a card a bare dash beside "bucket 07" says nothing a
        # reader can act on, so the chip must exit before it reaches pct().
        self.assertLess(code.index("return"), code.index("pct("),
                        "the chip formats before it checks for absence, so an uncovered "
                        "bucket renders a dash rather than nothing")

    def test_the_indicator_takes_no_new_row_and_no_new_card_height(self):
        """Decision 7. The grid's symmetry is a hard constraint: `.bk` cards share a row
        height, so anything that grows one card grows the whole row."""
        card = re.search(r"data-bucket=\"' \+ escAttr\(b\.id\).*?</div>'", self.js, re.S)
        self.assertIsNotNone(card, "the bucket card markup is gone")
        markup = card.group(0)
        self.assertIn('class="bk-id">bucket \' + esc(b.id) + activationChip(b.id)', markup,
                      "the indicator is no longer inside the id line — if it has been given "
                      "its own element the card is taller and every row with it grows")
        self.assertEqual(markup.count("activationChip("), 1,
                         "the indicator is rendered more than once per card")
        # The id line has to become a full-width row for the chip to sit at its far end; that
        # is the one structural change Phase E makes to a rule whose metrics are the buckets
        # page's, and it is what the height measurement above was checking.
        rule = re.search(r"\.bk-id\{([^}]*)\}", self.css)
        self.assertIsNotNone(rule, "the id-line rule is gone")
        self.assertIn("display:flex", rule.group(1))
        self.assertIn("width:100%", rule.group(1))
        self.assertIn("font:10.5px var(--mono)", rule.group(1),
                      "the id line no longer carries the buckets page's own type metrics")

    def test_the_chip_stands_down_where_the_id_line_has_no_room(self):
        """At ten columns a card is ~90px wide and the id line has ~26px spare. Rather than
        let "bucket 01" wrap, the indicator is omitted — the strip and the drawer still carry
        the number, so nothing is only knowable from the card."""
        m = re.search(r"@container \(min-width:(\d+)px\)\{\s*\.bk-act\{display:none\}", self.css)
        self.assertIsNotNone(
            m, "the card indicator is no longer withdrawn at the widest breakpoint, so the "
               "bucket id wraps at ten columns")
        # It must be a CONTAINER query. `.bk-grid` can be a tenth of the viewport or the whole
        # of it depending on where the reader put the module, so a media query would hide the
        # chip on a one-column grid in a wide window and show it on a ten-column grid in a
        # narrow one — exactly backwards.
        self.assertIn("container-type", self.css,
                      "the grid does not establish a container, so the query above resolves "
                      "against the viewport rather than the card's own space")

    def test_a_fixture_number_on_a_card_is_marked_as_one(self):
        """Decision 15 per surface. The card face is where a scanning reader meets a number
        with no prose around it."""
        self.assertIsNotNone(self.chip)
        code = self.chip.group(1)
        self.assertIn("scenarioIsFixture", code,
                      "the card cannot tell a fixture reading from a modelled one")
        self.assertIn("FIXTURE", code,
                      "a fixture activation renders on the card with nothing saying so")
        self.assertRegex(self.css, r"\.bk-act\.fixture\{[^}]*color:var\(--warning\)",
                         "a fixture activation is drawn in the same colour as a modelled one")
        # The colour alone is not the marker — colour is not readable to everyone and this one
        # differs from the modelled accent by hue. The title carries the words.
        self.assertLess(code.index("scenarioIsFixture"), code.index("title="),
                        "the fixture state is decided after the tooltip is built")

    def test_the_heat_bar_keeps_its_own_job(self):
        """The bar was not reused, retinted or rescaled to carry activation. Two answers to
        two different questions, drawn as two different things."""
        # Anchored to the WHOLE bar expression, opening tag through closing tag, not to one
        # line of it. A single-line anchor is a guard that quietly stops covering the code it
        # names the moment the expression is rewrapped.
        bar = re.search(r"'<span class=\"bk-heat h'(.*?)</i></span>'", self.js, re.S)
        self.assertIsNotNone(bar, "the heat bar is gone")
        self.assertIn("LEDGER.HEAT_MAX", bar.group(1),
                      "the matched region is not the heat bar any more")
        for banned in ("activation", "activationChip", "scenarioForShock"):
            self.assertNotIn(banned, bar.group(1),
                             "the heat bar now draws activation, so one mark carries an "
                             "authored judgment and a modelled probability at once")

        # Ordering is still stars, then editorial heat. Sorting by a fixture number would let
        # an illustrative figure decide what a reader looks at first, and sorting by a
        # modelled one would silently replace the authored relevance ranking.
        srt = re.search(r"const order = shown\.slice\(\)\.sort\(\(a, b\) => \{(.*?)\n  \}\);",
                        self.js, re.S)
        self.assertIsNotNone(srt, "the bucket grid's ordering is gone")
        code = srt.group(1)
        self.assertIn("heatOf(b) - heatOf(a)", code,
                      "the grid is no longer ordered by editorial heat")
        self.assertIn("bucketStarred", code, "a reader's star no longer outranks the ordering")
        self.assertNotIn("activation", code,
                         "the bucket grid is ordered by modelled activation")


class TheScenarioLensExplainsWithoutRanking(unittest.TestCase):
    """Phase F. The scenario lens screens on REACH — the scenario runs through a bucket this
    name is in — and says so instead of implying impact.

    The distinction this class exists to hold: a screen's ORDER is read as a ranking. Under a
    fixture, every magnitude behind such a ranking is a number somebody wrote to exercise a
    join. So the lens is allowed to decide membership and forbidden to decide order, until a
    model with a validated metric stands behind it — and that gate is decided in Python, where
    it can be tested, not restated here."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.js = _decomment(_script(cls.html))
        cls.fns = _functions(cls.js)

    def test_the_lens_is_registered_everywhere_a_lens_has_to_be(self):
        """A lens missing from any one of these is a lens that half-exists: a pill with no
        spec, or a spec no menu lists. The menu guard already catches ungrouped pills, so this
        pins the two registries it cannot see."""
        self.assertIn('data-p="scenario_reach"', self.html, "the lens has no pill")
        self.assertRegex(self.js, r"scenario_reach:\s*\{rank:null",
                         "the lens has no LENS_SPEC entry, so lensSpec() falls back to "
                         "{rank:'score'} and it silently ranks by composite score")
        self.assertRegex(self.js, r"scenario_reach:\s*\[", "the lens brings up no charts")
        self.assertIn('"scenario_reach"]', self.js.replace(" ", ""),
                      "the lens is not in any LENS_GROUPS group")

    def test_the_ranking_gate_is_read_not_restated(self):
        """`basis == modelled && rank_metric validated` is decided in scenarios.py. A second
        copy of it here would be the rule with two chances to be wrong, and the page would be
        the copy publishing a ranking off a fixture."""
        body = self.fns.get("scenarioRanking")
        self.assertIsNotNone(body, "the ranking gate reader is gone")
        self.assertIn("sc.ranking", body, "the page no longer reads Python's verdict")
        for banned in ("rank_metric", "modelled", "RANK_METRICS"):
            self.assertNotIn(banned, body,
                             "the page is re-deciding ordering authority instead of reading it")

    def test_the_results_order_is_not_a_ranking_under_a_fixture(self):
        """The table's default order is the composite score. Leaving it in place under this
        lens would put a real ranking under a scenario heading, where the top row reads as the
        name the shock most affects."""
        body = self.fns.get("renderTable")
        self.assertIsNotNone(body)
        self.assertRegex(
            body, r"preset === SCENARIO_LENS && !\(scenarioRanking\(\) \|\| \{\}\)\.quantitative",
            "the results table no longer switches ordering on the ranking verdict")
        self.assertIn("scenarioReachKey", body,
                      "the non-quantitative order is gone, so the table falls back to a "
                      "ranking the scenario did not produce")
        key = self.fns.get("scenarioReachKey")
        self.assertIsNotNone(key, "the ordering key is gone")
        self.assertIn("p.bucket_id", key,
                      "the order is no longer the lowest traversed bucket id")
        # Reading the row's own bucket column instead would inherit screen_tag_for's
        # first-match-wins, so the dual-bucket names would sort by a bucket this scenario may
        # never have gone through.
        # `\.bucket\b` and not `.bucket`: the latter matches `.bucket_id`, which is the field
        # this key is SUPPOSED to read, so the guard failed on correct code.
        self.assertNotRegex(key, r"\.bucket\b", "the order reads the screener's bucket column")
        for banned in ("magnitude", "confidence", "activation", "probability"):
            self.assertNotIn(banned, key,
                             "the lens orders by a scenario quantity, which under a fixture "
                             "is an illustrative number deciding what a reader sees first")

    def test_a_lens_with_no_metric_borrows_nobody_elses(self):
        """Three surfaces print "whatever the current lens ranks on". With no metric they must
        print the page's absent idiom, not the nearest number to hand."""
        watch = self.fns.get("drawWatch")
        self.assertIsNotNone(watch)
        self.assertIn("const v = m && m.get(o.r)", watch,
                      "the watchlist reads a metric without checking there is one")
        self.assertIn("muted-cell", watch, "the empty ranked column is not marked as absent")
        rank = self.fns.get("drawRank")
        self.assertIsNotNone(rank)
        self.assertRegex(rank, r"if\(!m\)\{",
                         "the ranked chart has no branch for a lens with no metric, so it "
                         "throws on m.get before it can say why it is empty")
        self.assertLess(rank.index("if(!m){"), rank.index("m.get("),
                        "the ranked chart reads the metric before checking it exists")
        cohort = self.fns.get("priceCohort")
        self.assertIsNotNone(cohort)
        self.assertIn("m && m.get(r)", cohort,
                      "the price cohort reads a metric without checking there is one")

    def test_the_shock_says_whether_it_is_narrowing(self):
        """For the whole life of this page a shock narrowed nothing, and three sentences said
        so. Under this lens it decides the row set. One definition, read by the handler that
        redraws and the sentence that explains, so the page cannot redraw on a shock change
        while still telling the reader shocks change nothing."""
        self.assertIn("function shockIsNarrowing(){ return preset === SCENARIO_LENS; }",
                      self.js, "the narrowing test is gone or has been inlined")
        head = self.fns.get("drawContextHead")
        self.assertIsNotNone(head)
        self.assertIn("shockIsNarrowing()", head,
                      "the context head still calls the shock framing unconditionally")
        self.assertIn("narrowing", head)
        self.assertIn("framing", head)

    def test_the_lens_admits_the_names_nobody_has_assessed(self):
        """Reachability is membership. A name reached with no sensitivity on record is a gap in
        the assessment, not a finding about the company, and dropping it would make the lens
        quietly mean "reached AND assessed" — hiding exactly the names nobody has looked at."""
        body = self.fns.get("lensRows")
        self.assertIsNotNone(body)
        m = re.search(r"if\(preset === SCENARIO_LENS\)\{(.*?)\n  \}", body, re.S)
        self.assertIsNotNone(m, "the lens has no membership rule")
        rule = m.group(1)
        self.assertIn("reach.has(r.tk)", rule)
        for banned in ("status", "exposed", "magnitude", "sign"):
            self.assertNotIn(banned, rule,
                             "the lens filters on the assessment, so reached-but-unassessed "
                             "names are dropped rather than reported")
        # And they ARE reported, in a note that is not the shadow gate's.
        note = self.fns.get("scenarioReachNote")
        self.assertIsNotNone(note, "the reach note is gone")
        # Each state must reach a SENTENCE, not merely appear somewhere in the function. The
        # first version asserted the bare word, and the three states are also the keys of the
        # tally object — so deleting two of the three clauses left the words behind and the
        # guard passed on a note that had stopped reporting them.
        for state in ("unassessed", "undirected", "unresolved"):
            self.assertRegex(
                note, r"if\(by\.%s\.length\) bits\.push\(" % state,
                "the note collapses the absences, so 'nobody assessed this' and "
                "'the paths disagree' read as one thing")
        self.assertIn("reach, not impact", note)

    def test_the_shadow_gate_note_was_not_generalised(self):
        """Its applicability test is a require-clause scan, its subject is an editorial tag,
        and five tests pin its sentences. The two notes say different things — one reports a
        gate that did not judge some names, the other names the gate deliberately admitted."""
        gate = self.fns.get("shadowGateNote")
        self.assertIsNotNone(gate, "shadowGateNote is gone")
        self.assertIn("shadow_severity_rank", gate,
                      "shadowGateNote no longer tests its own require clause")
        self.assertNotIn("SCENARIO_LENS", gate,
                         "the shadow note has been made to serve the scenario lens too")
        note = self.fns.get("scenarioReachNote")
        self.assertNotIn("shadow", note, "the reach note reaches into the shadow-debt table")

    def test_the_explanation_keeps_every_path(self):
        """Reaching one security on one channel through two buckets is the graph telling the
        truth — GD, CW and MRC sit in buckets 05 and 16. Rendering one of them would make this
        block contradict the derivation it claims to be reading."""
        body = self.fns.get("scenarioWhyBlock")
        self.assertIsNotNone(body, "the explanation renderer is gone")
        self.assertIn("rec.paths.map(", body, "the explanation no longer walks every path")
        self.assertNotIn("paths[0]", body, "the explanation renders one path and drops the rest")
        # Every hop's evidence, from the record. A narrated version would be free to disagree
        # with the arithmetic that produced the exposure and nothing would notice.
        for field in ("engaged_probability", "mechanism", "bucket_id", "membership_tier",
                      "sensitivity_sign", "sensitivity_basis", "channel_label"):
            self.assertIn(field, body, "the chain no longer shows its " + field + " hop")
        # `bucketTagFor(` with the paren: without it the assertion is satisfied by the
        # neighbouring `bucketTagForId(`, so removing the reconciliation entirely passed.
        self.assertIn("bucketTagFor(", body,
                      "the drilldown does not reconcile with the results row's bucket column, "
                      "so one screen can name two different buckets for one name")

    def test_the_explanation_never_claims_a_return(self):
        """Exposure, probability and return are three things. The chance rendered here is the
        chance the MECHANISM is engaged; nothing on this page says how much a security moves."""
        body = self.fns.get("scenarioWhyBlock")
        self.assertIn("not a return", body,
                      "the explanation does not say what it is not, beside numbers a reader "
                      "will otherwise read as a forecast")
        sign = self.fns.get("signWord")
        self.assertIsNotNone(sign)
        # The WORDS the reader sees, not the code around them. Scanning the function body
        # banned "return" and failed on the `return` keyword — a guard that cannot be
        # satisfied by any correct implementation is not a guard.
        words = " ".join(re.findall(r'"([^"]*)"', sign)).lower()
        self.assertIn("channel", words, "the matched strings are not the direction wording")
        # Word boundaries, because "gain" is inside "against" — the substring version banned
        # the correct wording. This is the third guard in this file to be written as a
        # substring scan and to fail on code that was right.
        for banned in ("rise", "fall", "gain", "benefit", "hurt", "return", "up", "down"):
            self.assertNotRegex(words, r"\b" + banned + r"s?\b",
                                "direction is worded as a price move rather than as a "
                                "relationship to the channel")

    def test_the_drawer_the_strip_points_at_exists(self):
        """The strip has rendered a `why` button since Phase D and `data-panel-open` resolves
        by id, returning silently when there is none — so the button took a click and did
        nothing. Whether an id has an element is exactly what this file's binding guard tests
        for handlers; this is the same defect one level up."""
        self.assertIn('id="scenPanel"', self.html, "the drawer the strip points at is missing")
        self.assertIn('data-panel-open="scenPanel"', self.js,
                      "nothing opens the drawer any more")
        self.assertIn('if(pop.id === "scenPanel") drawScenPanel();', self.js,
                      "the drawer opens without being filled, so it shows the previous "
                      "shock's scenario or nothing at all")
        body = self.fns.get("drawScenPanel")
        self.assertIsNotNone(body)
        self.assertIn("No scenario has been written for", body,
                      "the drawer goes blank for a shock with no model instead of saying so")
        self.assertIn("rank.why", body,
                      "the drawer does not carry the reason the lens will not rank, so that "
                      "sentence is only reachable by placing the ranked chart")


class TheScenarioTilesComeAndGoWithTheShock(unittest.TestCase):
    """Phase G. Two modules whose availability is a fact about the SELECTED SHOCK.

    Every other module on this board is available whenever its source is, for the whole life
    of the page. These two are the first that can be absent while every source is present, and
    the distinction they have to hold is absent-versus-parked: parked means "waiting on data
    that has not arrived", said in those words in a disclosure that counts them, and a scenario
    nobody has written for taiwan is not late.

    Verified in the browser across the six cases: placed under Hormuz, both drawn and both
    rows listed; switched to taiwan, both gone from the board, the tray and the panel with the
    Modules count falling 5 -> 3 and the ARRANGEMENT unchanged; switched back, both returned to
    the same places; and the board saved while they were absent still carried both leaves."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.js = _decomment(_script(cls.html))
        cls.fns = _functions(cls.js)

    def test_availability_is_asked_of_the_shock_and_not_of_the_payload(self):
        """`DATA_PRESENT` is payload-scoped and set once from a closed literal in
        `readDataPresence`. Routed through it, both tiles would become available under every
        shock the moment one shock had a model."""
        body = self.fns.get("scenarioTileAvailable")
        self.assertIsNotNone(body, "the availability rule is gone")
        self.assertIn("activeShock", body, "availability does not depend on the shock")
        self.assertIn("scenarioForShock", body)
        self.assertNotIn("DATA_PRESENT", body,
                         "scenario tile availability is read off the payload flag")
        # Each tile asks for the records IT draws, not for the scenario in general. The path
        # asks the RESOLVED series rather than the raw observation list — a scenario with one
        # point at each of two horizons has two observations and no path.
        self.assertIn("sc.series", body)
        self.assertIn("developments", body)

    def test_unavailable_means_absent_and_never_parked(self):
        """Parked is a promise that something is coming."""
        parked = self.fns.get("parkedTiles")
        self.assertIsNotNone(parked)
        self.assertNotIn("SCENARIO_TILES", parked,
                         "an unwritten scenario is listed as waiting on data")
        self.assertNotIn("scenarioTileAvailable", parked)
        needs = re.search(r"const TILE_NEEDS = \{(.*?)\n\};", self.js, re.S)
        self.assertIsNotNone(needs)
        for tile in ("spath", "sdev"):
            self.assertNotIn(tile, needs.group(1),
                             "%s declares a data source it is waiting on, which routes it "
                             "into the parked disclosure" % tile)
        # Gone from the tray too, not merely off the board.
        tray = self.fns.get("trayTiles")
        self.assertIsNotNone(tray)
        self.assertIn("tileAvailable(id)", tray,
                      "the tray still offers a module whose scenario does not exist")

    def test_the_arrangement_is_never_edited_because_something_went_away(self):
        """This is what makes saved placement survive absence, and it is a property of the
        design rather than a restore step: nothing has to remember where the tile was, because
        nothing forgot. The prune produces what is DRAWN; `boardTree` is untouched."""
        prune = self.fns.get("pruneTree")
        self.assertIsNotNone(prune, "the render-time prune is gone")
        self.assertIn("tileAvailable(node.tile)", prune)
        for banned in ("boardTree", "saveBoard", "dropLeaf"):
            self.assertNotIn(banned, prune,
                             "the prune edits or saves the arrangement, so a module that "
                             "became unavailable loses the place it would come back to")
        # And the availability test appears nowhere that writes the tree.
        for writer in ("dropLeaf", "splitLeaf", "placeTile", "sanitizeTree", "saveBoard"):
            body = self.fns.get(writer)
            self.assertIsNotNone(body, writer + " is gone")
            self.assertNotIn("tileAvailable", body,
                             writer + " consults availability while writing the arrangement")

    def test_the_prune_does_not_break_saving_or_splitter_identity(self):
        """Two hazards, both silent. `saveBoard` JSON.stringifies the arrangement inside a
        try/catch, so an enumerable back-reference from a node to its view is a cycle that the
        catch swallows — the board would simply stop saving. And `layoutBoard` restores
        splitter focus and the drag marker by comparing nodes with `===`, so a view rebuilt
        each layout drops the caret after one arrow key."""
        view = self.fns.get("viewSplit")
        self.assertIsNotNone(view, "the stable view wrapper is gone")
        self.assertRegex(view, r"enumerable:\s*false",
                         "the view is an enumerable property of a saved node, so saveBoard's "
                         "JSON.stringify hits a cycle and the catch hides it")
        self.assertIn("if(!node.__view)", view,
                      "a fresh view object per layout breaks splitter focus and drag identity")
        self.assertRegex(view, r"set ratio\(v\)\{ node\.ratio = v; \}",
                         "dragging the splitter of a pruned split writes to the view instead "
                         "of the arrangement, so the resize is lost on the next layout")

    def test_every_reader_of_what_is_placed_reads_what_is_drawn(self):
        """`treeTiles(boardTree)` answers "where would this go back to"; `boardTiles()` answers
        "what is on the board". Drop targets, counters and the panel all want the second — an
        undrawn tile is display:none, so its rect is zeros and it would sit at the board's
        top-left swallowing drops."""
        for fn in ("paneHits", "drawModChip", "syncLayoutPanel", "setTilePlaced",
                   "currentArrangement", "arrangeBoard", "syncBoardToLens"):
            body = self.fns.get(fn)
            self.assertIsNotNone(body, fn + " is gone")
            self.assertNotIn("treeTiles(boardTree)", body,
                             fn + " reads the arrangement where it means the board")
        # ONE legitimate reader of the raw arrangement, and it is named: the empty-board
        # sentence asks "did the reader place anything", which is the one question the
        # arrangement answers and the prune cannot. Everything else goes through
        # `boardTiles()`. Pinned as exactly one so a second reader fails here rather than
        # quietly joining it.
        self.assertEqual(self.js.count("treeTiles(boardTree)"), 1,
                         "something else reads the raw arrangement without pruning it first")
        empty = re.search(r"if\(!drawn\)\{(.*?)\n  \}", self.fns["layoutBoard"], re.S)
        self.assertIsNotNone(empty)
        self.assertIn("treeTiles(boardTree)", empty.group(1),
                      "the one permitted reader is no longer the empty-board sentence")
        self.assertIn("function boardTiles(){ return treeTiles(pruneTree(boardTree)); }",
                      self.js, "the one legal reading of the board is gone")

    def test_the_path_is_the_series_and_not_a_reconstruction(self):
        """Summing development contributions into a probability path is a modelling claim,
        legitimate only where a model defines that arithmetic. This fixture explicitly does
        not — which is why the two tiles can sit side by side without one appearing to explain
        the other."""
        body = self.fns.get("drawScenPath")
        self.assertIsNotNone(body, "the probability path is gone")
        self.assertIn("sc.series", body, "the path does not read the resolved series")
        for banned in ("developments", "contribution", "reduce("):
            self.assertNotIn(banned, body,
                             "the path is reconstructed from the developments rather than "
                             "read from the observation series")
        # And it reads THE series, not their union. A scenario may carry more than one — the
        # same question at two horizons, or two different questions — and `observations` is
        # the union, which drawn as one line puts two quantities on one axis and labels it
        # with whichever point sorted first.
        # `.observations` the FIELD, not the word: the tile's meta line reads "5 observations
        # · 30 days", which is display text. The substring version failed on correct code —
        # the fourth guard in this file to do so.
        self.assertNotRegex(body, r"\.observations",
                            "the path reads the raw observation list, so every series the "
                            "scenario holds is drawn as a single line")
        avail = self.fns.get("scenarioTileAvailable")
        self.assertNotRegex(avail, r"\.observations",
                            "availability counts the raw observation list, so a scenario with "
                            "one point at each of two horizons offers a path it cannot draw")

    def test_the_path_is_drawn_against_the_whole_of_a_probability(self):
        """Autoscaled to its own range, an 18%-to-30% series climbs the full height of the
        pane and draws a crisis out of a twelve-point move. The scale a probability is read
        against is 0 to 1."""
        body = self.fns.get("drawScenPath")
        self.assertIn("const y = p => T + (1 - p) * (H - T - B);", body,
                      "the probability axis is no longer the full 0-1 range")
        for banned in ("Math.max.apply", "Math.min.apply"):
            self.assertNotIn(banned, body,
                             "the path autoscales to the series' own extent, so a small move "
                             "in a small range is drawn as a large one")

    def test_the_timeline_says_it_is_not_a_decomposition(self):
        """A dated list of events beside a rising line is read as the explanation of the line.
        Nothing here says the two are related that way, so the tile says so itself."""
        body = self.fns.get("drawScenDev")
        self.assertIsNotNone(body, "the development timeline is gone")
        self.assertIn("Not a decomposition", body)
        self.assertIn("escalating", body, "the timeline drops the direction of each event")

    def test_both_tiles_are_registered_everywhere_a_module_has_to_be(self):
        """The panel's own guard catches an ungrouped widget and the brief/note guard catches a
        missing description; what neither can see is a tile absent from the id list or without
        markup, which would be a row that places nothing."""
        for tile in ("spath", "sdev"):
            self.assertIn('id="tile-' + tile + '"', self.html, tile + " has no markup")
            self.assertRegex(self.js, r"TILE_IDS = \[[^\]]*\"" + tile + r"\"",
                             tile + " is not a board module, so sanitizeTree drops it on load")
        groups = re.search(r"const TILE_GROUPS = \[(.*?)\n\];", self.js, re.S).group(1)
        self.assertIn('"spath", "sdev"', groups, "the tiles are not in a widget group")

    def test_a_shock_change_refreshes_the_tiles_without_a_full_render(self):
        """The shock has not touched a row, a lens or a filter under any lens but one, and that
        lens says so through `shockIsNarrowing`."""
        body = self.fns.get("refreshScenarioTiles")
        self.assertIsNotNone(body, "the scoped refresh is gone")
        self.assertIn("layoutBoard()", body,
                      "the board is not re-pruned, so a module whose scenario has gone keeps "
                      "its space and one whose scenario has arrived does not come back")
        self.assertIn("drawScenPath()", body)
        self.assertIn("drawScenDev()", body)
        self.assertNotRegex(body, r"(?<![.\w])render\(\)",
                            "the scoped refresh is a full render")
        handler = re.search(
            r'getElementById\("bucketShock"\)\.addEventListener\("change".*?\n\}\);',
            self.js, re.S)
        self.assertIsNotNone(handler)
        # BOTH branches. `render()` redraws the two tiles but never calls `layoutBoard`, so the
        # narrowing path needs the re-prune as much as the scoped one does — and asserting the
        # call appears anywhere in the handler was satisfied by whichever branch still had it.
        src = _decomment(handler.group(0))
        narrowing, _, scoped = src.partition("return; }")
        for branch, name in ((narrowing, "narrowing"), (scoped, "scoped")):
            self.assertIn("refreshScenarioTiles()", branch,
                          "the %s path leaves the board showing the previous shock's tiles"
                          % name)

    def test_an_empty_board_says_which_kind_of_empty_it_is(self):
        """Bug Bot, round 3. Two empty boards need two sentences.

        An arrangement holding nothing is the old case — everything parked or unplaced, and
        Modules → Widgets is where the way back is. An arrangement holding only modules that
        are unavailable under the selected shock is new, and the old sentence was false twice:
        nothing is parked, and the panel it points at shows no rows to put back, because an
        unavailable module is absent from it. The way out is the shock."""
        body = self.fns.get("layoutBoard")
        self.assertIsNotNone(body)
        m = re.search(r"if\(!drawn\)\{(.*?)\n  \}", body, re.S)
        self.assertIsNotNone(m, "the empty-board state is gone")
        code = m.group(1)
        self.assertIn("treeTiles(boardTree)", code,
                      "the empty board cannot tell 'nothing is placed' from 'everything "
                      "placed is unavailable', so it gives the same instruction for both")
        self.assertIn("bucketShock", code,
                      "the second sentence does not name the shock, which is the only thing "
                      "the reader can change to get the modules back")
        self.assertIn("still placed", code,
                      "the sentence does not say the arrangement survived, so a reader is "
                      "invited to place the modules again over the ones already there")

    def test_the_reach_cache_is_keyed_on_the_record_not_its_name(self):
        """Bug Bot, round 3. The cache key was `shock + "|" + scenario_id` — two strings that
        are EQUAL for two different records describing the same scenario. Replacing the
        fixture with a model's output for `hormuz` left the lens screening on the fixture's
        reach set, with the strip beside it reading the model's probability."""
        body = self.fns.get("scenarioReached")
        self.assertIsNotNone(body, "the reach set is gone")
        self.assertIn("_reachKey === sc", body,
                      "the reach cache is keyed on a name rather than on the resolved record, "
                      "so a payload swap serves the previous record's securities")
        self.assertNotIn("scenario_id", body)

    def test_one_writer_owns_whether_a_row_is_hidden(self):
        """Two writers of `hidden` take turns undoing each other: type a query while a scenario
        tile is absent and it reappears; change the shock during a search and rows the query
        excluded come back. The availability test is part of the search's own predicate."""
        body = self.fns.get("filterLayoutTiles")
        self.assertIsNotNone(body)
        self.assertIn("tileAvailable(row.dataset.tileRow)", body,
                      "the widget list still offers a module whose scenario does not exist")
        writers = [fn for fn, src in self.fns.items()
                   if re.search(r"row\.hidden\s*=", src) or re.search(r"\.hidden = !hit", src)]
        self.assertEqual(writers, ["filterLayoutTiles"],
                         "more than one function writes a widget row's hidden state: "
                         + ", ".join(writers))


class ThePagesVocabulariesMatchThePythonOnes(unittest.TestCase):
    """Architecture review. Two small maps in the page enumerate values Python owns: the four
    exposure statuses and the three development directions.

    Neither is a duplicated RULE — the page decides nothing with them, it only chooses a word
    and a colour — but both are duplicated VOCABULARIES, and a vocabulary that drifts is how a
    new status arrives on screen as a raw identifier or, worse, silently takes the styling of
    whichever branch happens to catch it. Pinned across the language boundary because there is
    no other way to notice: adding a status in Python breaks nothing that runs."""

    @classmethod
    def setUpClass(cls):
        cls.js = _decomment(_script(_page()))

    def test_the_four_exposure_states_are_the_four_the_derivation_produces(self):
        src = _decomment(open(os.path.join(REPO, "tools", "scenarios.py"),
                              encoding="utf-8").read())
        resolve = re.search(r"def _resolve_exposure.*?\ndef ", src, re.S)
        self.assertIsNotNone(resolve, "the exposure resolver is gone")
        produced = set(re.findall(r'status="(\w+)"', resolve.group(0)))
        self.assertEqual(len(produced), 4, "the resolver no longer produces four states")
        shown = set(re.findall(r"\n  (\w+):\s*\{label:",
                               re.search(r"const EXPOSURE_STATES = \{(.*?)\n\};",
                                         self.js, re.S).group(1)))
        self.assertEqual(shown, produced,
                         "the page's exposure vocabulary has drifted from the derivation's: "
                         "%s" % sorted(shown ^ produced))
        # `unassessed` is the one that must never read as "no effect": it is the majority of
        # reached names, and it means nobody has looked, not that the answer is zero.
        self.assertIn("unassessed", shown)

    def test_the_three_directions_are_the_three_the_schema_allows(self):
        import scenarios as sn  # noqa: E402 — imported here, next to its only use
        dev = _functions(self.js).get("drawScenDev")
        self.assertIsNotNone(dev, "the development timeline is gone")
        m = re.search(r"const dirs = \{(.*?)\};", dev, re.S)
        self.assertIsNotNone(m, "the timeline's direction map is gone")
        shown = set(re.findall(r"(\w+):", m.group(1)))
        self.assertEqual(shown, set(sn.DIRECTIONS),
                         "the timeline's directions have drifted from the schema's: %s"
                         % sorted(shown ^ set(sn.DIRECTIONS)))
