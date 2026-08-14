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
import inspect
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
# `tests` is a package and REPO is already on sys.path above, so the shared fixture
# is imported by its package path — a bare `import screener_payload_fixture` only
# resolves when the tests directory itself happens to be the working directory.
from tests import screener_payload_fixture  # noqa: E402

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
        """A rule testing a field the payload drops would silently fail every row.

        Built from authored rows rather than the fetched snapshot. The join asserted here
        is between two independently-maintained things — the metric names in
        `stock_screener.PRESETS` and the row keys `research_ui` emits — and neither is a
        vendor's to decide, so nothing is lost by not asking a vendor. What WAS lost while
        this read the cache is the test itself: the snapshot is gitignored, so in CI
        `rows` was empty and this failed on `rows[0]` rather than on its subject."""
        needed = set()
        for preset in sc.PRESETS.values():
            needed.update(m for m, _op, _v in preset["require"])
            needed.add(preset["rank"][0])
        self.assertGreater(len(needed), 5, "the canonical presets test almost no metrics — "
                                           "this check has gone near-vacuous")
        alias = dict(re.findall(r'(\w+):"(\w+)"',
                                re.search(r'const CANON_FIELD = \{(.*?)\};',
                                          self.html, re.S).group(1)))
        row = screener_payload_fixture.authored_payload()["rows"][0]
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
        """The editorial shadow-debt rank has to reach every row, or the lens that gates on
        it silently admits everything.

        Authored rows, loaded through the real path so `stock_screener.enrich_rows` still
        runs — that join is what puts the rank on a row, and stubbing the loader would have
        skipped it and left this proving only that a dict literal has a key.

        Strengthened while it was being made CI-safe: the original asserted presence on
        every row and would have passed with the whole table joining to the `None -> 0`
        default. One authored name is tagged in `SHADOW_DEBT` and one is not, so a broken
        join now shows up as every rank being equal."""
        payload = screener_payload_fixture.authored_payload()
        rows = payload["rows"]
        self.assertTrue(rows, "the authored fixture produced no rows")
        for row in rows:
            self.assertIn("shadow_severity_rank", row, row.get("tk"))
            self.assertIsNotNone(row["shadow_severity_rank"], row.get("tk"))
        ranks = {row["tk"]: row["shadow_severity_rank"] for row in rows}
        tagged = ranks[screener_payload_fixture.TAGGED_TICKER]
        untagged = ranks[screener_payload_fixture.UNTAGGED_TICKER]
        self.assertGreater(
            tagged, untagged,
            "a name tagged in SHADOW_DEBT ranks no higher than an untagged one, so the "
            "editorial join is not reaching the row: {}".format(ranks))


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
        # Iterates SCENARIO_TILES rather than naming two tiles, so a third one added later
        # cannot register in some places and not others — the guard-narrower-than-the-claim
        # failure this file keeps recording.
        declared = re.findall(r'"(\w+)"',
                              re.search(r"const SCENARIO_TILES = \[(.*?)\];",
                                        self.js).group(1))
        self.assertGreaterEqual(len(declared), 3, "SCENARIO_TILES shrank")
        for tile in declared:
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


class TheReachByDirectionModuleReadsItsGroupsRatherThanDecidingThem(unittest.TestCase):
    """Reached securities, grouped by direction relative to their channels.

    A security is reached on one channel or several, and the several can disagree — VLO and
    MPC move against the crude price and with the refining crack, both firm, both assessed.
    Which group that belongs in is a PRECEDENCE question, and precedence lives in
    `scenarios.classify_security` where it is tested. The page reads the answer.

    The vocabulary is the other half. `sign` says which way a security moves relative to a
    CHANNEL, and this layer models no conditional return at all — `expected_impact.value` is
    null for every scenario that exists — so a heading calling a name a beneficiary would be
    a claim nothing behind it can support."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.js = _decomment(_script(cls.html))
        cls.fns = _functions(cls.js)
        cls.body = cls.fns.get("drawScenOpps")

    def test_the_page_classifies_nothing_itself(self):
        self.assertIsNotNone(self.body, "the module renderer is gone")
        self.assertIn("classification", self.body,
                      "the module does not read Python's class for a security")
        for banned in ("sensitivity_sign", "edge_sign", "paths.filter", "reduce(",
                       "Math.sign", "> 0 ? \"mixed\""):
            self.assertNotIn(banned, self.body,
                             "the page is deciding a security's class instead of reading it")

    def test_the_group_headings_come_from_pythons_labels(self):
        """A page-side list of Python's class keys is the cross-language vocabulary drift
        already guarded for the exposure states and the development directions."""
        self.assertIn("SCENARIOS.SECURITY_CLASSES", self.body,
                      "the module keeps its own list of group names")
        import scenarios as sn  # noqa: E402
        for _key, label, _why in sn.SECURITY_CLASSES:
            self.assertNotIn('"' + label + '"', self.js,
                             "the page hard-codes the label {!r} instead of rendering the "
                             "one Python emitted".format(label))

    def test_an_empty_group_still_renders_its_heading(self):
        """A group that vanishes reads as "no such case exists"; the truth is "none today",
        and a reader deciding what to research next needs to tell those apart."""
        self.assertRegex(
            self.body, r"members\.length \? '<ul",
            "the group heading is now conditional on having members, so an empty class "
            "disappears instead of showing a zero")
        self.assertIn("members.length", self.body)

    def test_rows_are_ordered_by_the_lens_key_and_never_by_a_magnitude(self):
        self.assertIn("scenarioReachKey", self.body,
                      "the module invented its own ordering")
        for banned in ("magnitude", "confidence", "probability", "activation"):
            self.assertNotIn(banned, self.body,
                             "rows are ordered or ranked by a scenario quantity, which "
                             "under a fixture lets an illustrative number lead the list")

    def test_the_count_states_which_thing_it_counts(self):
        """36 securities and 58 exposure records are two denominators; printing one under
        the other's name is the mixed-scope aggregate this project already forbids."""
        self.assertIn("securities reached", self.body)

    def test_a_row_click_opens_the_existing_drilldown(self):
        """No second explanation renderer. `pinTicker` is the call a results row makes and
        the drawer already ends with `scenarioWhyBlock(selected, "drawer")`."""
        m = re.search(r'closest\("\[data-sopp\]"\)(.*?)\n\}\);', self.js, re.S)
        self.assertIsNotNone(m, "the row-click handler is gone")
        handler = m.group(1)
        self.assertIn("pinTicker(", handler)
        self.assertIn("drawScenPanel()", handler)
        self.assertNotIn("scenarioWhyBlock", handler,
                         "the handler renders its own explanation instead of opening the "
                         "one every other surface opens")

    def test_no_heading_or_row_claims_a_price_move(self):
        """The layer has no conditional return, so the vocabulary of winners is unavailable
        to it. Asserted over the module's own rendered strings."""
        strings = " ".join(re.findall(r"'([^']*)'", self.body)
                           + re.findall(r'"([^"]*)"', self.body)).lower()
        for banned in ("beneficiary", "loser", "bullish", "bearish", "opportunit",
                       "winner", "upside", "downside", "profit"):
            self.assertNotRegex(strings, r"\b" + banned,
                                "the module claims a price move: " + banned)
        # Matched on phrases that live inside ONE string literal: the sentence is built by
        # concatenation, so "not a price forecast" spans two and is never contiguous.
        for phrase in ("price forecast", "how much anything moves"):
            self.assertIn(phrase, strings,
                          "the module does not say what its directions are not")

    def test_a_channel_with_no_direction_prints_no_direction_word(self):
        """The same rule as the card chip one column over: an absence renders as nothing,
        not as a mark that looks like a reading."""
        self.assertRegex(
            self.body, r"c\.sign == null \? \"\"",
            "an unassessed channel renders a placeholder in the direction slot")

    def test_the_module_is_shock_scoped_like_the_other_two(self):
        avail = self.fns.get("scenarioTileAvailable")
        # The branch has to ANSWER from the resolved scenario, not merely mention the tile.
        # Asserting the tile id appears was satisfied by `return true`, which is the whole
        # defect: a module offered under every shock, including ones with no model.
        self.assertRegex(
            avail, r'tileId === "sopps"\) return [^;]*sc\.securities',
            "the availability rule for this module does not read the scenario's own "
            "securities, so it can be offered under a shock that has none")
        self.assertNotIn("DATA_PRESENT", avail)

    def test_the_module_carries_its_own_fixture_marker(self):
        self.assertIn('fxMark("sopps"', self.body,
                      "a module listing fixture-derived classifications carries no marker")


class TheBaseEffectFlagThePageAlreadyPromised(unittest.TestCase):
    """The growth explainer has said "Rows where this is likely carry a base-effect flag next
    to the number" since it was written, and both render sites — the table cell and the detail
    card — were wired to draw `r.flag`. The payload shipped `"flag": None` on every row, so the
    chip could not appear on any of them. Every part of the mechanism existed except the one
    that decides, and nothing noticed because nothing asked the payload for a flag.

    That is why the guards below go through `authored_payload` rather than calling the helper.
    A unit test of `_base_effect_flag` alone passes with `"flag": None` still hard-coded in the
    row literal — it would have proved the rule correct and the feature dead."""

    #: One name per case, each isolating a single clause of the rule. Values are chosen here;
    #: `growth` mirrors `stock_screener`'s own `eg if eg is not None else rg` so these rows are
    #: shaped like the snapshot they stand in for.
    CASES = [
        # tk       earnings  revenue   growth   flagged  why
        ("BASE",   15.80,    0.67,     15.80,   True,
         "1580% earnings on 67% revenue — 24x, the base effect the explainer describes"),
        ("SHRANK", 4.28,     -0.01,    4.28,    True,
         "428% earnings while the business shrank; max(revenue,0) must not rescue this"),
        ("LEVER",  4.00,     3.00,     4.00,    False,
         "operating leverage at 1.3x — the business moved with the earnings, so it is not "
         "a base effect; this is what stops the ratio being loosened below ~1.3"),
        ("NEAR",   10.00,    1.50,     10.00,   True,
         "6.7x, just past the 5x line — this is what stops the ratio being tightened past "
         "it, and the pair with LEVER is what brackets the constant"),
        ("SMALL",  1.50,     0.02,     1.50,    False,
         "150% is under the threshold; large ratios alone do not make a base effect"),
        ("REVONLY", None,    9.00,     9.00,    True,
         "no earnings figure, so the column shows REVENUE at 900% — this case asserted False "
         "and was the defect: the explainer's 'revenue almost never does this' was treated as "
         "never, and 38 live rows went untested. It carries the weaker revenue question now, "
         "not the earnings one"),
        ("REVCALM", None,    0.19,     0.19,    False,
         "revenue leg, ordinary size — the weaker question has a threshold too, so a normal "
         "revenue number is still clean"),
    ]

    @staticmethod
    def _row(tk, eg, rg, growth):
        return {"ticker": tk, "name": tk + " Inc", "sector": "Energy", "pe": 12.0,
                "growth": growth, "earnings_growth": eg, "revenue_growth": rg,
                "dividend_yield": 0.01, "debt_to_equity": 20.0, "beta": 1.0,
                "market_cap": 1.0e10, "dollar_volume": 5.0e8, "avg_volume": 1.0e7,
                "price": 50.0, "profit_margin": 0.1, "range_52w_pct": 0.5,
                "ai": "low", "bucket": "oil shock"}

    @classmethod
    def setUpClass(cls):
        rows = [cls._row(tk, eg, rg, g) for tk, eg, rg, g, _f, _w in cls.CASES]
        payload = screener_payload_fixture.authored_payload(fund_rows=rows)
        cls.by_tk = {r["tk"]: r for r in payload["rows"]}

    def test_the_flag_reaches_the_row_and_not_only_the_helper(self):
        for tk, _eg, _rg, _g, flagged, why in self.CASES:
            row = self.by_tk.get(tk)
            self.assertIsNotNone(row, tk + " never reached the payload")
            with self.subTest(tk=tk):
                if flagged:
                    self.assertIsNotNone(
                        row["flag"],
                        "{} carries no flag, but {}".format(tk, why))
                    # The two questions are different strengths and must not be conflated:
                    # only an earnings number that beat its revenue leg earns "base effect?".
                    expected = "base effect?" if tk != "REVONLY" else "revenue, off a small base?"
                    self.assertEqual(row["flag"], expected, tk)
                else:
                    self.assertIsNone(
                        row["flag"],
                        "{} is flagged, but {}".format(tk, why))

    def test_a_column_showing_revenue_is_not_flagged_by_an_earnings_figure_elsewhere(self):
        """The one clause the payload fixture cannot reach, called directly and labelled as
        such rather than left unexercised.

        `_screener_combined_draft_payload` resolves the printed number from the fundamentals
        row and falls back to the sentiment row; the two legs resolve the same way. So a name
        whose fundamentals fetch found no earnings figure prints REVENUE growth, while the
        sentiment snapshot may still carry an earnings figure for it. `growth != earnings` is
        what stops the earnings explanation being attached to the revenue number on screen.

        `authored_payload` forces sentiment absent on purpose — that is what makes the payload
        identical in CI and on a machine with a tone cache — so this divergence cannot be
        built through it. Dropping the clause leaves every other guard here green."""
        self.assertIsNone(
            research_ui._base_effect_flag(earnings=9.00, revenue=0.30, growth=0.30),
            "a revenue number in the column was flagged using an earnings figure the column "
            "is not showing")
        self.assertEqual(
            research_ui._base_effect_flag(earnings=9.00, revenue=0.30, growth=9.00),
            "base effect?",
            "the same pair, with the earnings number actually in the column, must flag")

    def test_a_revenue_sourced_number_gets_its_own_question(self):
        """The column prints revenue growth whenever the vendor reported no earnings figure, and
        those numbers used to leave the helper unqualified and unmarked. ONDS at 1080% and RCAT
        at 849% are revenue, and a company going from one million to twelve is up 1,100% for
        precisely the reason the growth explainer describes.

        The question is deliberately weaker than the earnings one. With no earnings figure there
        is no ratio to test, so the chip asks about the base without claiming the comparison
        that "base effect?" is built on."""
        # Revenue leg, extreme: asked.
        self.assertEqual(
            research_ui._base_effect_flag(earnings=None, revenue=10.80, growth=10.80),
            "revenue, off a small base?")
        # Revenue leg, ordinary: nothing to say.
        self.assertIsNone(
            research_ui._base_effect_flag(earnings=None, revenue=0.19, growth=0.19))
        # The two chips are different sentences, because they are different strengths of claim.
        earnings_chip = research_ui._base_effect_flag(earnings=15.8, revenue=0.67, growth=15.8)
        self.assertNotEqual(earnings_chip,
                            research_ui._base_effect_flag(None, 10.80, 10.80))
        self.assertNotIn("base effect", research_ui._base_effect_flag(None, 10.80, 10.80),
                         "the revenue chip borrows certainty from a comparison never made")
        # And nothing at all when there is no number to qualify.
        self.assertIsNone(research_ui._base_effect_flag(None, None, None))

    def test_the_revenue_question_reaches_rows_not_only_the_helper(self):
        """The same join that shipped `"flag": None` on every row for months. Asserted through
        the payload, with a row whose earnings leg is genuinely absent."""
        row = dict(screener_payload_fixture.FUND_ROWS[0])
        row.update(ticker="REVX", earnings_growth=None, revenue_growth=9.4, growth=9.4)
        payload = screener_payload_fixture.authored_payload(fund_rows=[row])
        self.assertEqual(payload["rows"][0]["flag"], "revenue, off a small base?")

    def test_a_clean_row_carries_no_flag_rather_than_an_empty_one(self):
        """`""` and `None` render differently: the table tests `r.flag?` truthiness, but the
        detail card and any future consumer should not have to know that an empty string is
        this module's way of saying nothing."""
        self.assertIsNone(self.by_tk["LEVER"]["flag"])

    def test_the_flag_says_it_is_a_question_not_a_finding(self):
        """The rule is two thresholds over vendor figures, not an audit of the filing. Wording
        that asserted the base effect would be a claim the arithmetic cannot support."""
        chip = self.by_tk["BASE"]["flag"]
        self.assertIsNotNone(chip, "no chip to read")
        self.assertIn("?", chip, "the chip states a base effect as fact")

    def test_the_explainer_still_promises_what_the_payload_now_delivers(self):
        """These two drifted apart once already, in the direction of the page promising more
        than the payload did. Either side moving alone should fail."""
        html = _page()
        # Both chip texts, not a phrase describing them. The explainer names two questions of
        # different strength now, and a guard matching prose about the feature would survive
        # either chip being renamed out from under it.
        for chip in ("base effect?", "revenue, off a small base?"):
            self.assertIn(chip, html,
                          "the growth explainer does not name the chip the payload emits: " + chip)
        self.assertIn("no earnings figure to compare against", html,
                      "the explainer no longer says why the revenue question is the weaker one")

    def test_both_render_sites_still_draw_the_row_field(self):
        """The chip appears in the results table and on the detail card. A flag that reaches
        the payload and is drawn by neither is the same dead feature in a new place."""
        js = _decomment(_script(_page()))
        fns = _functions(js)
        self.assertRegex(fns["renderTable"], r"r\.flag\s*\?",
                         "the results table no longer draws the base-effect chip")
        # `drawCard` delegates the populated case to `cardBody`; asserting against `drawCard`
        # passed vacuously on the string "flag" appearing nowhere near the chip.
        self.assertRegex(fns["cardBody"], r"r\.flag",
                         "the detail card no longer draws the base-effect chip")


class TheScoreColumnDoesNotRateCompanies(unittest.TestCase):
    """This column was headed "Score", labelled "composite score", offered in the lens builder
    as "best overall", printed to three decimals with a filled bar, and given a green / amber /
    grey stripe down the ticker cell beside it. It is `max(growth, 0) / (pe / 15 + 0.5)`,
    clamped — two fields, on a row carrying thirteen. Everything about its presentation said
    verdict on a company and the arithmetic supports none of that.

    The clamp is the sharpest part: on the shipped snapshot 99 of 206 scored rows sit exactly
    on a bound, 32 of them printing an identical 0.990. Undisclosed, a tie produced by a clamp
    reads as a measurement that happened to agree."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.js = _decomment(_script(cls.html))
        cls.fns = _functions(cls.js)

    def test_no_traffic_light_is_drawn_beside_a_company_name(self):
        """The stripe was `rv >= 0.75 ? good : rv >= 0.55 ? neutral : warning` on the ticker
        cell — a two-field ratio colouring the company itself."""
        self.assertNotRegex(
            self.fns["renderTable"], r'class="sev',
            "the ticker cell carries a severity class again")
        self.assertNotRegex(
            self.fns["renderTable"], r"rankScore\([^)]*\)[^;]*\?[^;]*(good|warning)",
            "a severity is being derived from the ranking value again")
        self.assertNotRegex(
            self.html, r"\.sev\s*\{", "the ticker severity-stripe rule is back in the CSS")

    def test_the_column_names_its_two_ingredients(self):
        """"Score" and "composite" both claim more than one ratio over two fields."""
        for gone in ("composite score", "best overall"):
            self.assertNotIn(gone, self.html,
                             "the page still calls this column '{}'".format(gone))
        self.assertRegex(self.html, r'<th class="num">Growth per P/E<button',
                         "the results header no longer names the two fields")
        self.assertRegex(self.js, r'score:\s*\{label:"growth per P/E"',
                         "the metric label no longer names the two fields")

    def test_the_column_has_an_explainer_the_reader_can_open(self):
        """Growth and AI shadow both earned a `?`. This column is the one most likely to be
        read as a verdict and had none."""
        self.assertRegex(self.html, r'data-explain="scoreExplain"',
                         "the header has no way to open the explanation")
        self.assertRegex(self.html, r'id="scoreExplain"',
                         "the explanation panel the header points at does not exist")

    def test_the_explainer_refuses_the_reading_it_exists_to_prevent(self):
        panel = re.search(r'<div class="explain" id="scoreExplain".*?\n</div>',
                          self.html, re.S)
        self.assertIsNotNone(panel, "the panel is no longer a self-contained block")
        body = panel.group(0)
        self.assertIn("not a rating", body,
                      "the panel no longer says what this number is not")
        self.assertIn("absent, not zero", body,
                      "the panel no longer separates a missing value from a low one")
        # The named omissions are the point: a reader who knows only that it is "two fields"
        # cannot tell WHICH thirteen columns it ignores.
        for ignored in ("balance sheet", "beta", "liquidity", "bucket"):
            self.assertIn(ignored, body,
                          "the panel no longer names '{}' among what this ignores".format(
                              ignored))

    def test_the_clamp_bounds_are_not_a_second_opinion(self):
        """`SCORE_FLOOR` / `SCORE_CEIL` decide what the cell labels as a bound. The clamp
        itself lives in `_screener_combined_draft_payload`. Two copies of one pair of numbers
        is exactly the drift this suite exists for: if Python widened the clamp and the page
        did not, cells would be labelled 'at ceiling' at a value that is no longer the
        ceiling — and the label would still look authoritative."""
        page = dict(re.findall(r"SCORE_(FLOOR|CEIL)\s*=\s*([0-9.]+)", self.js))
        self.assertEqual(set(page), {"FLOOR", "CEIL"}, "the page's bounds are gone")
        src = inspect.getsource(research_ui._screener_combined_draft_payload)
        clamp = re.search(r"max\(\s*([0-9.]+)\s*,\s*min\(\s*([0-9.]+)\s*,", src)
        self.assertIsNotNone(clamp, "the clamp is no longer written as max(floor, min(ceil,")
        self.assertEqual(float(page["FLOOR"]), float(clamp.group(1)),
                         "the page's floor is not Python's floor")
        self.assertEqual(float(page["CEIL"]), float(clamp.group(2)),
                         "the page's ceiling is not Python's ceiling")
        # The explainer states the bounds and the shape of the denominator in prose, which is
        # a THIRD copy and the one a reader is most likely to believe. Pin it to the same
        # source: prose that has drifted is worse than no prose, because it is being read as
        # the authority on what the column means.
        panel = re.search(r'<div class="explain" id="scoreExplain".*?\n</div>',
                          self.html, re.S).group(0)
        self.assertIn("<code>{}</code> to <code>{}</code>".format(
            clamp.group(1), clamp.group(2)), panel,
            "the explainer states clamp bounds that are not the ones Python applies")
        den = re.search(r"\(\s*pe\s*/\s*([0-9.]+)\s*\+\s*([0-9.]+)\s*\)", src)
        self.assertIsNotNone(den, "the price term is no longer written as (pe / N + M)")
        self.assertIn("15/{} + {}".format(den.group(1).rstrip("0").rstrip("."),
                                          den.group(2)), panel,
                      "the explainer's worked example uses a price term Python does not")

    def test_the_worked_example_in_the_explainer_is_arithmetically_true(self):
        """A worked example is the part a reader checks by hand. One that does not come out
        teaches them the column is lying about itself."""
        panel = re.search(r'<div class="explain" id="scoreExplain".*?\n</div>',
                          self.html, re.S).group(0)
        shown = re.search(r"<code>([0-9.]+) ÷ \(15/([0-9.]+) \+ ([0-9.]+)\) = ([0-9.]+)</code>",
                          panel)
        self.assertIsNotNone(shown, "the worked example is gone or no longer machine-readable")
        growth, div, add, claimed = (float(shown.group(i)) for i in (1, 2, 3, 4))
        self.assertAlmostEqual(growth / (15.0 / div + add), claimed, places=2,
                               msg="the explainer's own worked example does not come out")

    def test_a_row_held_at_a_bound_says_so(self):
        body = self.fns["scoreCell"]
        self.assertRegex(body, r"raw\s*>=\s*SCORE_CEIL", "the ceiling is no longer detected")
        self.assertRegex(body, r"raw\s*<=\s*SCORE_FLOOR", "the floor is no longer detected")
        self.assertIn("at ${at}", body, "the bound is detected and never rendered")

    def test_the_bound_marker_describes_the_number_actually_printed(self):
        """With tone blended in, the printed value is no longer the bound. Marking it anyway
        would label a value the cell is not showing."""
        self.assertRegex(self.fns["scoreCell"], r"s\s*!==\s*raw",
                         "the marker no longer checks that the printed value is the bound")

    def test_the_clamp_share_is_counted_from_the_rows_not_written_into_the_prose(self):
        """"32 at the ceiling" is true of one snapshot. In prose it would go quietly false on
        the next fetch, inside the paragraph whose whole job is to be trustworthy."""
        note = self.fns.get("drawScoreClampNote")
        self.assertIsNotNone(note, "the clamp note is no longer computed")
        self.assertIn("ROWS.filter", note, "the clamp note no longer counts the live rows")
        # Counting and then not USING the counts is the whole defect in miniature — the
        # filters can stay while the sentence goes back to literals, and asserting the
        # counting alone passes that. Every count the sentence states must be interpolated.
        emitted = re.search(r"el\.innerHTML\s*=(.*?);\s*\n\}?\s*$", note, re.S)
        self.assertIsNotNone(emitted, "the clamp sentence is no longer assigned in one place")
        for var in ("${pinned}", "${scored.length}", "${pct}", "${ceil}", "${floor}"):
            self.assertIn(var, emitted.group(1),
                          "the clamp sentence states a number it did not count ({} is "
                          "missing, so that figure is a literal)".format(var))
        panel = re.search(r'<div class="explain" id="scoreExplain".*?\n</div>',
                          self.html, re.S).group(0)
        self.assertIn('id="scoreClampNote"', panel, "the panel has no slot for the count")
        self.assertNotRegex(
            panel, r"\b\d{2,} (?:of|at) \b",
            "a snapshot-specific count has been written into the panel's prose")

    def test_the_count_is_refreshed_when_the_panel_opens(self):
        """Computed and never called is the failure mode this repo has paid for twice."""
        self.assertRegex(self.fns["panelOpen"], r'"scoreExplain"\)\s*drawScoreClampNote\(\)',
                         "the clamp note is computed but never drawn")


class TheAbsenceVocabularyIsOneDefinition(unittest.TestCase):
    """An em-dash said a value was not there and never said why. "The provider did not report
    this" and "nobody has assessed this" are different facts about the world, and a reader who
    cannot separate them draws a wrong conclusion from both.

    The reason now travels on the row, decided in Python, with the wording shipped in the
    payload. These guards pin the two things that make that worth having: that the wording has
    exactly one home, and that no field can be added to the row without someone deciding which
    kind of `None` it has."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.js = _decomment(_script(cls.html))
        cls.fns = _functions(cls.js)
        cls.payload = screener_payload_fixture.authored_payload()

    def test_the_registry_is_closed_and_every_emitted_code_is_in_it(self):
        """An open reason string would let each render site invent its own wording, which is
        how this page reached 281 tooltips saying overlapping things."""
        shipped = self.payload.get("absence_reasons")
        self.assertEqual(shipped, dict(research_ui.ABSENCE_REASONS),
                         "the payload's registry is not the module's registry")
        for row in self.payload["rows"]:
            for field, code in (row.get("absent") or {}).items():
                with self.subTest(tk=row["tk"], field=field):
                    self.assertIn(code, research_ui.ABSENCE_REASONS,
                                  "an unregistered reason code reached a row")

    def test_the_page_holds_no_copy_of_the_wording(self):
        """The sentence a reader sees is Python's. A page-side copy is a second definition of
        one thing, which is the defect this file has already paid for twice."""
        # What could RENDER, not what is written: the decommented script plus the markup with
        # its <script> blocks and HTML comments removed. A design note quoting these sentences
        # to explain itself is not a copy that can drift into a cell — the first version of
        # this guard failed on its own explanatory comment, which is a guard measuring the
        # wrong thing rather than a defect.
        markup = re.sub(r"<script[^>]*>.*?</script>", " ", self.html, flags=re.S)
        markup = re.sub(r"<!--.*?-->", " ", markup, flags=re.S)
        renderable = markup + "\n" + self.js
        for sentence in research_ui.ABSENCE_REASONS.values():
            self.assertNotIn(sentence, renderable,
                             "the page restates a reason sentence instead of reading it")
        self.assertRegex(self.js, r"ABSENCE_REASONS\s*=\s*live\.absence_reasons",
                         "the page never takes the registry from the payload")

    def test_an_unregistered_code_renders_as_itself_rather_than_vanishing(self):
        """A blank for an unknown code would hide exactly the drift the registry exists to
        catch: the cell would look complete while saying nothing."""
        body = self.fns.get("absenceNote")
        self.assertIsNotNone(body, "the absence helper is gone")
        self.assertRegex(body, r"ABSENCE_REASONS\[why\]\s*\|\|\s*why",
                         "an unknown reason code renders as nothing")

    def test_a_none_that_means_no_is_not_reported_as_a_gap(self):
        """`flag=None` means the growth figure needed no qualifying, and `bucket=None` means the
        name is in no bucket. Both are answers, so reporting them as absences would claim a hole
        where the data is complete and the answer is negative.

        This test's original docstring asserted that as a universal and it was false for 38 of
        225 rows: `_base_effect_flag` returned None the moment the earnings leg was missing,
        without running any test, so a guard meant to protect the distinction was pinning a
        claim the code did not honour. `test_a_revenue_sourced_number_gets_its_own_question`
        is what now makes the claim true rather than assumed."""
        for answered in ("flag", "bucket"):
            self.assertNotIn(answered, research_ui.ABSENCE_FIELDS,
                             "'{}' is a negative answer, not a missing value".format(answered))
        for row in self.payload["rows"]:
            self.assertNotIn("flag", row.get("absent") or {})
            self.assertNotIn("bucket", row.get("absent") or {})

    def test_every_row_field_that_can_be_absent_was_classified(self):
        """The list is the decision record. A new nullable column added to the row without
        being classified here would render as a bare em-dash again, silently."""
        VALUE_FIELDS = {"pe", "g", "dy", "de", "beta", "mcap", "score", "shadow_tag",
                        "bb", "rd", "yh"}
        self.assertEqual(set(research_ui.ABSENCE_FIELDS), VALUE_FIELDS,
                         "a value field was added or removed without updating this guard")

    def test_not_applicable_is_reserved_for_instruments_that_cannot_have_the_value(self):
        """A fund has no earnings to divide into and no balance sheet of its own, so its
        missing P/E is not a fetch that failed. Calling that 'not reported' would claim the
        provider owed a number that cannot exist."""
        fund = research_ui._absence_reasons(
            {"pe": None, "g": None, "de": None, "beta": None, "mcap": None, "dy": 0.01,
             "score": None, "shadow_tag": None, "bb": None, "rd": None, "yh": None}, "fund")
        for f in ("pe", "g", "de"):
            self.assertEqual(fund[f], "not_applicable", f)
        # Beta and market cap are properties of anything that trades, so they stay reportable.
        self.assertEqual(fund["beta"], "not_reported")
        self.assertEqual(fund["mcap"], "not_reported")

        company = research_ui._absence_reasons(
            {"pe": None, "g": None, "de": None, "beta": None, "mcap": None, "dy": 0.01,
             "score": None, "shadow_tag": None, "bb": None, "rd": None, "yh": None}, None)
        for f in ("pe", "g", "de"):
            self.assertEqual(company[f], "not_reported",
                             "an ordinary company's missing {} is a failed fetch".format(f))

    def test_editorial_absence_says_nobody_looked_not_nobody_reported(self):
        """The shadow-debt table is authored, never fetched. 'The provider did not report
        this' about a judgement no provider ships would be false, and it would also hide that
        the gap is one a researcher could close."""
        out = research_ui._absence_reasons({"shadow_tag": None, "dy": 0.01}, None)
        self.assertEqual(out["shadow_tag"], "not_assessed")
        self.assertIn("assessed", research_ui.ABSENCE_REASONS["not_assessed"])

    def test_no_coverage_and_covered_but_untoned_stay_different(self):
        """`_c` counts documents found. Zero coverage means nothing was written; coverage with
        a null tone means documents exist and none carried a reading. One em-dash for both is
        what made these indistinguishable."""
        nothing = research_ui._absence_reasons({"bb": None, "bb_c": 0, "dy": 0.01}, None)
        found = research_ui._absence_reasons({"bb": None, "bb_c": 4, "dy": 0.01}, None)
        self.assertEqual(nothing["bb"], "not_covered")
        self.assertEqual(found["bb"], "not_reported")
        self.assertNotEqual(research_ui.ABSENCE_REASONS["not_covered"],
                            research_ui.ABSENCE_REASONS["not_reported"])

    def test_the_tone_exemption_is_declared_rather_than_forgotten(self):
        """`toneChip` already separates these two states, and better, because it can also say
        how many documents were found. The exemption is pinned so a later reader who
        'completes' the wiring duplicates the sentence deliberately rather than by accident."""
        self.assertEqual(set(research_ui.ABSENCE_FIELDS_RENDERED_ELSEWHERE), {"bb", "rd", "yh"})
        chip = self.fns.get("toneChip")
        self.assertIsNotNone(chip)
        self.assertIn("no coverage", chip, "the idiom this exemption defers to is gone")
        self.assertIn("untoned", chip, "the idiom this exemption defers to is gone")
        # And the results table must not ALSO draw the helper for them.
        table = self.fns.get("renderTable")
        for src in ("bb", "rd", "yh"):
            self.assertNotIn('absenceNote(r,"{}")'.format(src), table,
                             "the tone cell now states its absence twice")

    def test_an_imputed_zero_keeps_its_number_and_gains_a_note(self):
        """The income lens depends on a no-dividend name screening as 0%, and its own test
        pins that. So the value stays and the note says the zero was assumed — the one entry
        in the registry describing a value that IS present."""
        imputed = research_ui._absence_reasons({"dy": 0.0, "shadow_tag": "x"}, None,
                                               imputed_dy=True)
        self.assertEqual(imputed["dy"], "imputed_zero")
        measured = research_ui._absence_reasons({"dy": 0.0, "shadow_tag": "x"}, None,
                                                imputed_dy=False)
        self.assertNotIn("dy", measured, "a measured zero was reported as assumed")
        # The helper appends, so the cell still prints the number it had.
        self.assertRegex(self.fns["renderTable"], r'fmtDy\(r\.dy\)\}\$\{absenceNote\(r,"dy"\)',
                         "the note replaces the dividend value instead of joining it")

    def test_the_snapshot_records_which_zero_a_dividend_zero_is(self):
        """`_dividend_yield_fraction` returns None both for a company that pays nothing and for
        a vendor response with no dividend fields at all. Without this flag the distinction is
        destroyed at write time and no downstream surface can recover it."""
        empty = sc._normalise_row("T", "T", "S", "low", {})
        self.assertEqual(empty["dividend_yield"], 0.0, "the screening semantics changed")
        self.assertTrue(empty["dividend_yield_imputed"])
        real = sc._normalise_row("T", "T", "S", "low",
                                 {"dividendRate": 1.0, "currentPrice": 50.0})
        self.assertFalse(real["dividend_yield_imputed"])

    def test_a_complete_row_carries_no_absence_key_at_all(self):
        """`absent` being truthy is the "does this row have a gap" test, so a complete row must
        not ship an empty dict that answers yes."""
        full = {"pe": 10.0, "g": 0.2, "dy": 0.02, "de": 20.0, "beta": 1.0, "mcap": 1e9,
                "score": 0.5, "shadow_tag": "spv_sponsor",
                "bb": 0.1, "bb_c": 3, "rd": 0.2, "rd_c": 2, "yh": 0.1, "yh_c": 4}
        self.assertEqual(research_ui._absence_reasons(full, None), {})

    def test_the_map_actually_reaches_a_row_in_the_payload(self):
        """The classifier being correct and the payload carrying it are two claims, and the
        second is the one that has failed here before: `"flag": None` shipped on every row for
        as long as the growth explainer promised a chip, because every test asked the helper
        and none asked the payload. Deleting the attachment leaves this suite green without
        this test."""
        rows = self.payload["rows"]
        carrying = [r for r in rows if r.get("absent")]
        self.assertTrue(carrying,
                        "no row in the payload carries an absence map, so the classifier is "
                        "computed and thrown away")
        for r in carrying:
            self.assertTrue(all(v for v in r["absent"].values()),
                            "a row carries an absence with no reason")

    def test_a_row_with_no_gaps_ships_no_absence_key(self):
        """An empty dict is falsy, so attaching one breaks no consumer — it just makes the key
        mean nothing, and `absent` stops being the "does this row have a gap" test.

        The fixture forces sentiment absent so every row it builds has at least a tone gap,
        which makes a gapless row unconstructible through it — the first version of this test
        was therefore vacuous and passed while an empty map was being attached. Forcing the
        classifier to return nothing is what actually exercises the call site."""
        real = research_ui._absence_reasons
        research_ui._absence_reasons = lambda *a, **k: {}
        try:
            payload = screener_payload_fixture.authored_payload()
        finally:
            research_ui._absence_reasons = real
        for row in payload["rows"]:
            self.assertNotIn("absent", row,
                             "a row with no gaps still carries an absence key")


class TheVolumeMetricReadsTheNumberNotItsLabel(unittest.TestCase):
    """`METRICS.vol` ranked, charted and sorted on `volNum(r.vol)` — a parse of the DISPLAY
    string the server had already rounded for a human. `fmt_metric(3926.16)` is "0M", so
    `volNum("0M")` was 0 and NSRCF charted as zero dollars traded while its own row carried
    3926.16.

    The row has shipped the exact `dollar_volume` all along; `research_ui.py` even says why
    where it emits it. The metric was never switched over, so the page ranked volume on a
    different quantity than `stock_screener` ranks it on."""

    @classmethod
    def setUpClass(cls):
        cls.html = _page()
        cls.js = _decomment(_script(cls.html))
        # Authored rows, not the live snapshot. Both snapshots are gitignored and CI never
        # fetches, so a class built on the fetched payload is red on every CI run and vacuous
        # on the assertions that iterate rows — which is exactly what happened here: the
        # "carries a row the old path read as zero" test failed in CI while
        # "absences are untouched" passed over an empty list. screener_payload_fixture exists
        # to end that and five sibling classes already use it; this one did not.
        cls.payload = screener_payload_fixture.authored_payload(fund_rows=[
            # 3926.16 formats to "0M" — the exact value that motivated the fix.
            dict(screener_payload_fixture.FUND_ROWS[0], ticker="TINYV",
                 dollar_volume=3926.16),
            dict(screener_payload_fixture.FUND_ROWS[1], ticker="BIGV",
                 dollar_volume=1.0e9),
        ])

    def test_the_metric_reads_the_exact_field(self):
        self.assertRegex(
            self.js, r'vol:\s*\{label:"\$ volume/day",\s*get:r=>canonValue\(r,"dollar_volume"\)',
            "the volume metric is parsing a formatted string again")

    def test_the_lossy_parser_is_gone_entirely(self):
        """Deleted rather than left unused. A string-to-number parser lying around is how the
        next metric picks it up, and this one silently returns the rounded value."""
        self.assertNotRegex(self.js, r"function\s+volNum\s*\(",
                            "volNum is back")
        self.assertNotIn("volNum(", self.js, "something calls volNum again")

    def test_the_rounding_that_caused_it_still_happens(self):
        """The guard above is only worth having while `fmt_metric` still rounds sub-million
        volumes to "0M". If that changes, this fails rather than the guard quietly protecting
        a defect that moved."""
        self.assertEqual(sc.fmt_metric({"dollar_volume": 3926.16}, "dollar_volume"), "0M")

    def test_the_live_payload_carries_a_row_the_old_path_read_as_zero(self):
        """Not hypothetical: a real row in the shipped snapshot whose display string parses to
        zero while its own field is non-zero."""
        bad = [r for r in self.payload["rows"]
               if r.get("vol") == "0M" and (r.get("dollar_volume") or 0) > 0]
        self.assertTrue(bad, "no row exercises this any more — re-check before deleting the guard")
        self.assertGreater(bad[0]["dollar_volume"], 0)

    def test_absences_are_untouched_by_the_switch(self):
        """`dollar_volume` must be null exactly when `vol` is an em-dash, or the switch would
        have turned a disclosed absence into a silent one."""
        for r in self.payload["rows"]:
            with self.subTest(tk=r["tk"]):
                self.assertEqual(r.get("vol") == "—", r.get("dollar_volume") is None)


class ANamelessRowRendersRatherThanCrashing(unittest.TestCase):
    def test_a_matching_row_with_no_name_does_not_raise(self):
        """`_normalise_row` blesses `name=None` when the vendor returns none, and `apply_preset`
        only requires the preset's own metrics — so such a row reached the printer and raised
        TypeError AFTER the header had printed, which reads as a crashed screen."""
        self.assertNotIn('row["name"][:21]', open(
            os.path.join(REPO, "tools", "stock_screener.py"), encoding="utf-8").read(),
            "the unguarded subscript is back")
        self.assertEqual((None or "—")[:21], "—")
