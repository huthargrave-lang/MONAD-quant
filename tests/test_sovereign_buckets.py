"""The chaos buckets have one definition, and their prices are fetched rather than invented.

Two defects are guarded here, and they are the same defect at different layers.

**The table was written down twice.** `tools/research_ui.py` carried a `const BUCKETS = [...]`
literal and `docs/research/SOVEREIGN_LEDGER_OPTIONS_MOCK.html` carried another. They were
byte-identical the day this module was written — which is not reassurance, it is the state
every duplicate in this repo has been in right up to the edit that made it wrong. The lens
thresholds, the shadow-severity table and the combined-tone formula all drifted exactly this
way, each time invisibly, each time with both surfaces published side by side.

**The prices were generated.** `genSeries()` was `mulberry32(hashStr(symbol))` — a seeded
random walk over a hash of the ticker string. It was captioned "demo cache", so it was not a
lie, but it was undetectable and it was not small: it had SHV, a 1-3 month Treasury ETF,
returning +175.1% over six months against a real +1.7%, and it drew two years of confident
price action for eleven companies that no longer trade, because a hash of a delisted ticker
hashes exactly as well as a live one.

The rule these encode: a page may draw a number it FETCHED or say it has none. There is no
third option, and "shaped like the real thing" is the most dangerous version of the third
option because it survives review.
"""
import json
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_ui  # noqa: E402
import sovereign_buckets as sb  # noqa: E402
import stock_screener as sc  # noqa: E402

MOCK = os.path.join(REPO, "docs", "research", "SOVEREIGN_LEDGER_OPTIONS_MOCK.html")


def _served():
    code, body, _ct = research_ui.route("/screen", {}, {})
    assert code == 200
    return body


def _served_buckets():
    """The OTHER bucket surface. `NothingOnThePageIsGenerated` asserted its rules against
    `/screen` while the seeded price walk lived on `/screener/buckets` — the guard was green
    and the counterexample was published, for months, on the page the nav points at."""
    code, body, _ct = research_ui.route("/screener/buckets", {}, {})
    assert code == 200
    return body


class TheTableHasOneSource(unittest.TestCase):
    def test_research_ui_holds_no_literal_of_its_own(self):
        """Not the bucket table alone. `BOOK1` and `HINTS` sat in research_ui as
        byte-identical copies for as long as this guard only watched `BUCKETS` — the guard
        was narrower than the module's claim, so the parts it did not name drifted out from
        under it. Every table the module owns is named here."""
        with open(os.path.join(REPO, "tools", "research_ui.py"), encoding="utf-8") as fh:
            src = fh.read()
        for var in ("BUCKETS", "BOOK1", "HINTS", "DELISTED"):
            self.assertNotRegex(
                src, r"(?:const|let|var)\s+{}\s*=\s*[\[{{]".format(var),
                "{} is written down in research_ui again — every table the ledger owns must "
                "be serialised from sovereign_buckets.runtime_js() at render time".format(var))
        self.assertIn("sovereign_buckets.runtime_js()", src)

    def test_every_name_the_module_emits_is_one_a_surface_asked_for(self):
        """The emit is a namespace, so a name dropped from it fails at the destructuring
        rather than quietly reading undefined — but only if the returned object and the
        literals it is built from stay in step, which is itself two lists."""
        js = sb.runtime_js()
        # Scoped to the emit's own top level (two spaces). `bucketHeat` has a `const h`
        # inside it, and a bare scan would demand the module export a local.
        declared = (set(re.findall(r"^  const (\w+) = ", js, re.M))
                    | set(re.findall(r"^  function (\w+)\(", js, re.M)))
        returned = set(re.findall(
            r"\w+", re.search(r"return \{(.*?)\};", js).group(1)))
        self.assertEqual(declared, returned,
                         "runtime_js declares and returns different names")

    def test_the_served_page_gets_the_canonical_table(self):
        m = re.search(r"const BUCKETS = (\[.*?\]);\n", _served(), re.S)
        self.assertIsNotNone(m, "no bucket table reached the page")
        shipped = json.loads(m.group(1))
        self.assertEqual(
            [b["id"] for b in shipped], [b["id"] for b in sb.BUCKETS])
        for a, b in zip(shipped, sb.BUCKETS):
            self.assertEqual(a["liquid"], b["liquid"], a["name"])
            self.assertEqual(a["satellite"], b["satellite"], a["name"])
            self.assertEqual(a["fails"], b["fails"], a["name"])

    def test_the_mock_and_the_module_still_agree(self):
        """The mock is a static document rather than a served surface, so it is not rebuilt
        from the module — but if someone edits one and not the other, the wireframe and the
        page start describing different portfolios. Compared, not silently tolerated."""
        with open(MOCK, encoding="utf-8") as fh:
            body = re.search(r"const BUCKETS = \[(.*?)\n\];", fh.read(), re.S).group(1)
        names = re.findall(r'name:"([^"]+)"', body)
        self.assertEqual(names, [b["name"] for b in sb.BUCKETS],
                         "the mock's bucket names have drifted from sovereign_buckets")
        tickers = set(re.findall(r'"([A-Z][A-Z0-9.=\-]*)"', body))
        self.assertEqual(
            tickers, set(sb.all_tickers()),
            "the mock's constituents have drifted from sovereign_buckets")


class NothingOnThePageIsGenerated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = _served()

    def test_the_seeded_walk_is_gone(self):
        """Matched as CODE, not as a word: the comment recording what was removed names
        mulberry32 on purpose, and a test that forbade the name would forbid the explanation."""
        self.assertNotRegex(
            self.page, r"function mulberry32\(",
            "the seeded price generator is back on the buckets page")
        self.assertNotRegex(self.page, r"Math\.random\(")

    def test_the_series_come_from_the_injected_cache(self):
        self.assertRegex(
            self.page, r"function genSeries\(symbol,n\)\{\s*const s = PRICES\[symbol\];",
            "genSeries must read the fetched cache and nothing else")

    def test_an_unknown_ticker_yields_no_series_rather_than_a_shape(self):
        """The WHOLE body is pinned, not just the presence of a null return.

        Asserting the guard exists is not enough: `const s = PRICES[symbol] || [10,11,12];`
        leaves the guard in place and never fires it, so the test passed while every unknown
        ticker got an invented series again. What has to be true is that the lookup is
        unconditional and the only two outcomes are the cache's values or null.
        """
        body = re.search(r"function genSeries\(symbol,n\)\{(.*?)\n\}", self.page, re.S)
        self.assertIsNotNone(body, "genSeries not found")
        code = body.group(1)
        # MULTILINE: the anchors have to mean "this line", not "the whole body".
        self.assertRegex(code, re.compile(r"^\s*const s = PRICES\[symbol\];\s*$", re.M),
                         "the cache lookup must have no fallback")
        self.assertRegex(code, r"if\(!s \|\| !s\.length\) return null;")
        # Nothing may manufacture values: no arithmetic on a missing series, no literal array.
        self.assertNotRegex(code, r"\[\s*\d", "a literal series appears inside genSeries")
        self.assertNotRegex(code, r"Math\.")

    def test_the_banner_no_longer_calls_the_prices_mock(self):
        self.assertNotIn("<strong>Mock prices.</strong>", self.page)
        self.assertIn("<strong>Real prices.</strong>", self.page)

    def test_the_banner_states_when_it_was_fetched(self):
        """"Real prices" without a date is one stale cache from being wrong invisibly."""
        self.assertIn('id="priceStamp"', self.page)
        self.assertRegex(self.page, r'priceStamp"\)\.textContent\s*=\s*\n?\s*PRICE_ASOF')


class TheAbsentAreNamedNotDropped(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = _served()

    def test_a_constituent_with_no_series_keeps_its_row(self):
        self.assertRegex(
            self.page, r"\{t,tier,bucket:b\.id,name:b\.name,s:null,why:whyNoSeries\(t\)\}",
            "an unpriced constituent must keep its row and carry its reason")

    def test_delisting_reads_differently_from_absence(self):
        """"EURN is missing" invites a refetch; "EURN was renamed CMB.TECH" does not."""
        self.assertRegex(
            self.page,
            r'return DELISTED\[symbol\] \? "delisted — " \+ DELISTED\[symbol\]')

    def test_the_chart_picks_five_that_have_data(self):
        """Slicing to five before checking spent a chart slot on a name that draws nothing,
        so a bucket led by a delisted ticker came out with four lines and no explanation."""
        self.assertRegex(self.page, r"if\(Object\.keys\(map\)\.length >= 5\) return;")

    def test_every_delisted_name_is_still_in_its_bucket(self):
        """Deleting them would make each bucket misreport its own history: that the tankers
        trade held EURN is true, and EURN not being purchasable today does not unmake it."""
        listed = set(sb.all_tickers())
        for ticker in sb.DELISTED:
            self.assertIn(ticker, listed,
                          "{} was removed from its bucket instead of flagged".format(ticker))


class TheBucketsAreOnTheScreenerBoard(unittest.TestCase):
    """The point of moving them here is that a bucket and a lens can be used together. Two
    pages cannot intersect; two cards on one board can."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()
        cls.payload = research_ui._screener_combined_draft_payload()

    def test_the_table_reaches_the_screener_unchanged(self):
        self.assertEqual([b["id"] for b in self.payload["buckets"]],
                         [b["id"] for b in sb.BUCKETS])
        self.assertEqual(self.payload["delisted"], dict(sb.DELISTED))

    def test_the_bucket_cards_are_widget_options(self):
        """The ask was for them in edit-layout, not bolted to the page — a card that cannot
        be closed or brought back is not a module, it is furniture. All four are still
        offered; what changed is WHICH registry each is in."""
        for tile in ("bpanel", "bwatch"):
            self.assertRegex(self.html, r'data-id="{}"'.format(tile))
            self.assertRegex(self.html, r"{}\s*:".format(tile),
                             "{} has no label/note entry".format(tile))
        self.assertRegex(
            self.html, r"tileOrder\(ALL_TILE_IDS\.filter",
            "widget options must offer both registries, or a hidden card cannot be reopened")

    def test_the_context_owns_controls_and_the_board_owns_the_analysis(self):
        """The split that stops the context becoming a second dashboard. A control DEFINES the
        universe; a panel ANALYSES one. Shock, clock, tier, search and the card grid define,
        and they are plain content — not modules — because a control that can be closed is a
        way to lose the framing with no way back, and the hidden set was persisted. The
        history, detail, price-feed, Book I tabs and the constituents table analyse, so they
        are board modules placed by the same system as the scatter and the ranking."""
        tiles = re.search(r"const TILE_IDS = \[(.*?)\];", self.html, re.S).group(1)
        for analysis in ("bpanel", "bwatch"):
            self.assertIn('"{}"'.format(analysis), tiles,
                          "{} analyses a universe and belongs on the board".format(analysis))
        for control in ("bucketctl", "buckets"):
            self.assertNotIn('"{}"'.format(control), tiles,
                             "{} is a context control, not a placeable module".format(control))
        self.assertNotIn("BAY_IDS", self.html,
                         "a second tile registry is back; there is one board")
        self.assertRegex(self.html, r"const ALL_TILE_IDS = TILE_IDS\.slice\(\);")

    def test_the_context_controls_cannot_be_closed_away(self):
        """`BAY_HIDDEN` persisted, so pressing x on the shock row removed the only way to
        change the framing and it stayed gone across reloads."""
        body = re.search(r'<div class="ctx-controls">(.*?)</div>', self.html, re.S).group(1)
        self.assertNotIn("tile-close", body)
        self.assertNotIn("data-close", body)
        self.assertNotIn("bayShown", self.html)
        self.assertNotIn("BAY_HIDDEN", self.html.split("-->")[-1],
                         "the hidden-set machinery is back")

    def test_the_analysis_modules_sit_in_the_board_container(self):
        """Markup, not just the registry: layoutBoard positions its children absolutely, so a
        tile listed as a board module but parked in the context markup would be positioned
        against a container it is not inside."""
        board = re.search(r'<div class="board" id="board">(.*?)\n    </div>', self.html, re.S)
        self.assertIsNotNone(board)
        for analysis in ("bpanel", "bwatch"):
            self.assertIn('data-id="{}"'.format(analysis), board.group(1),
                          "{} is a board module but is not in the board".format(analysis))
        # The property, not the expression. This used to pin the literal
        # `tileOrder(ALL_TILE_IDS.filter(id => !parked.includes(id)))`, which stopped being the
        # code the moment the panel built its rows once and moved them between lists — while
        # the thing it was protecting (every registered module has a row, so a parked bay card
        # can be got back) held throughout. What must be true is that the row builder walks the
        # WHOLE registry.
        fn = re.search(r"function renderLayoutTiles\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(fn, "the widget panel has no row builder")
        body = re.sub(r"/\*.*?\*/|//[^\n]*", "", fn.group(1), flags=re.S)
        self.assertIn("ALL_TILE_IDS", body,
                      "the widget panel does not offer the full registry, so a parked bay "
                      "card cannot be reopened")
        self.assertNotRegex(body, r"\bTILE_IDS\.(forEach|map|filter)",
                            "the row builder walks the chart registry alone, which leaves the "
                            "bucket modules with no row")

    def test_nothing_routes_around_the_board(self):
        """`setTilePlaced` used to divert bay ids to a second show/hide path. With one
        registry there is nothing to divert, and a special case that still existed would be a
        way for a module to be placed somewhere the board does not manage."""
        self.assertNotRegex(self.html, r"if\(isBayTile\(id\)\)")

    def test_the_context_layer_comes_before_what_it_constrains(self):
        """The bay used to sit under Results, so the reader chose the universe below the fold
        and read the consequence above it. It is the CONTEXT layer — what world am I
        researching — and the page now reads in the order the question is asked:
        context, then lens, then workspace, then results."""
        # Markup, not stylesheet. `cmdbar` first appears in a CSS rule 58k characters before
        # the element it styles, so a bare substring search ordered the sheet, not the page.
        order = ['id="contextSection"', 'id="bucketGrid"', 'id="cmdbar"',
                 'class="board" id="board"', "<h2>Results</h2>"]
        seen = [(name, self.html.index(name)) for name in order]
        for (an, ai), (bn, bi) in zip(seen, seen[1:]):
            self.assertLess(ai, bi, "{} must come before {}".format(an, bn))

    def test_the_context_body_folds_but_the_summary_never_does(self):
        """A collapsed context still has to say what it is constraining. The one thing a
        reader must not expand a section to discover is that a section is narrowing their
        results."""
        head = re.search(r'<div class="ctx-head">(.*?)</div>', self.html, re.S)
        self.assertIsNotNone(head, "the context summary line is gone")
        # `ctxScenario` was renamed `ctxFraming`: "scenario" now means the probabilistic
        # object, and this element has always meant the editorial shock+clock framing.
        # `ctxScen` is the modelled strip, and it is in the head for exactly the reason this
        # test exists — whether a model stands behind what a reader is looking at is not
        # something they should have to expand a section to discover.
        for el in ("ctxHeadValue", "ctxHeadSub", "ctxFraming", "ctxScen"):
            self.assertIn(el, head.group(1), "{} is not in the always-visible head".format(el))
        self.assertNotIn("ctxScenario", self.html,
                         "the old name survives somewhere, so two names mean one element")
        body = re.search(r'<div id="contextBody">(.*?)\n      </div>', self.html, re.S)
        self.assertIsNotNone(body, "the context body wrapper is gone")
        for part in ('id="bucketShock"', 'id="bucketClock"', 'id="bucketTop"',
                     'id="bucketGrid"'):
            self.assertIn(part, body.group(1),
                          "{} must be inside the foldable body".format(part))

    def test_the_grid_is_still_cards_not_a_list(self):
        """The rich card grid is the point of this surface — being able to scan twenty theses
        and see their relative heat at once. A dropdown of bucket names is not a substitute
        and was explicitly rejected."""
        self.assertRegex(self.html, r'class="bk-grid"', "the bucket card grid is gone")
        self.assertRegex(self.html, r'class="bk-heat h', "bucket heat bars are gone")
        self.assertIn('id="bucketGrid"', self.html)

    def test_the_bay_chart_is_in_the_reflow_graph(self):
        """The context workspace can now be folded, reopened and resized, so its chart has to
        redraw with the others. It was in neither the reflow list nor the ResizeObserver's:
        measured at 796 -> 1314px wide against an unchanged viewBox."""
        fns = re.search(r"\[drawPlot, drawPrice, drawRank, drawDist, drawShadow[^\]]*\]",
                        self.html)
        self.assertIsNotNone(fns)
        self.assertIn("drawBucketChart", fns.group(0),
                      "the bay chart still will not redraw when its box changes")
        obs = re.search(r'\["plot","priceChart","rankChart","distChart","shadowChart"[^\]]*\]',
                        self.html)
        self.assertIsNotNone(obs)
        self.assertIn("bChart", obs.group(0), "the bay chart is not observed for resize")

    def test_the_context_lays_out_as_controls_over_grid(self):
        """One control row, then the grid. No slot table, no grid-areas, no drag-to-swap —
        the context holds two things in a fixed order, and the machinery that arranged four
        panes in a second region went with the panes."""
        body = re.search(r'<div id="contextBody">(.*?)\n      </div>', self.html, re.S).group(1)
        self.assertLess(body.index('class="ctx-controls"'), body.index('id="bucketGrid"'),
                        "the controls must sit above the grid they frame")
        for gone in ("BAY_SLOTS", "layoutBay", "initBayDrag", "bay-grid"):
            self.assertNotIn(gone, self.html, "{} survived the dissolution".format(gone))

    def test_constituent_series_travel_not_just_screened_ones(self):
        """53 of 202 constituents are in the fundamentals universe. Shipping only screened
        rows would leave three quarters of every bucket unplottable on the page meant to
        plot it."""
        shipped = set(self.payload["price_history"])
        priceable = set(sb.price_tickers())
        covered = priceable & shipped
        self.assertGreater(
            len(covered), len(priceable) * 0.9,
            "only {} of {} tradeable constituents have a series in the screener "
            "payload".format(len(covered), len(priceable)))

    def test_a_selected_bucket_owns_the_price_chart(self):
        """It is the more specific request — the reader named these companies — so drawing
        the lens's leaders over a chosen thesis would answer a question nobody asked."""
        self.assertRegex(
            self.html,
            r"if\(BUCKET_SEL\.size\)\{[\s\S]{0,900}?"
            r"bucketRowsSpread\(\)\.forEach\(r => push\(r\.tk\)\)")

    def test_the_chart_spreads_across_the_selected_buckets(self):
        """Bucket-major order is right for a list and wrong for a five-line chart. With
        Liquid Fear selected the cohort was SGOV, BIL, SHV, JPST, TFLO — five T-bill ETFs
        from one thesis, flat and drawn on top of each other, with no slot left for anything
        else the reader had chosen."""
        body = re.search(r"function bucketRowsSpread\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "the chart cohort must interleave the selected buckets")
        self.assertRegex(body.group(1), r"lists\.forEach\(l => \{ if\(i < l\.length\)")
        # The LIST keeps bucket-major order; only the chart spreads.
        self.assertRegex(
            self.html, r"function bucketNames\(\)\{ return bucketRows\(\)\.map",
            "membership order must stay bucket-major for the constituents list")

    def test_a_pin_outside_the_bucket_does_not_ride_along(self):
        """The pin was pushed into the cohort unconditionally, which put the auto-pinned
        first row on a chart of theses it is not a constituent of — NVDA on Oil/Hormuz."""
        self.assertRegex(
            self.html,
            r"if\(selected && bucketNameSet\(\)\.has\(selected\)\) push\(selected\);",
            "only a pin that is IN the selected buckets may join the bucket chart")

    def test_an_all_unpriced_bucket_falls_through_rather_than_emptying_the_chart(self):
        self.assertRegex(
            self.html, r"if\(out\.length\) return out;",
            "a bucket whose names are all unpriced must fall back to the lens, or the empty "
            "frame reads as 'this bucket did nothing'")

    def test_the_member_list_keeps_three_states_apart(self):
        """Priced, carries fundamentals, and clears the lens are three different facts. An
        ETF with no P/E is not a failure and a delisted name with no price is not either."""
        self.assertRegex(self.html, r"function whyNoSeries\(tk\)\{")
        self.assertRegex(self.html, r'DELISTED\[tk\] \? "delisted — " \+ DELISTED\[tk\]')
        # An unpriced row collapses its three price columns into one reason rather than
        # printing three dashes: a dash in a "Last" column is a price, and there is not one.
        self.assertRegex(
            self.html,
            r"'<td colspan=\"3\" class=\"muted-cell\">' \+ esc\(whyNoSeries\(m\.tk\)\)",
            "an unpriced constituent must state its reason across the price columns")
        # Lens membership is shown, never used to filter the list.
        self.assertRegex(self.html, r'inLens\.has\(m\.tk\) \? "is-in " : ""')

    def test_the_page_supplies_no_default_bucket_table(self):
        """Authored judgement travels or it does not exist. A built-in fallback list would
        let the page draw buckets nobody wrote."""
        self.assertRegex(self.html, re.compile(r"^let BUCKETS = \[\];$", re.M),
                         "BUCKETS must start empty and be filled only from the payload")

    def test_heat_orders_and_never_scores(self):
        """Heat is editorial relevance under a chosen shock, on the same footing as the
        shadow-severity tags — ordinal and authored, not a quantity to rank COMPANIES by.

        The invariant is asserted, not the spelling: an earlier version of this test pinned
        the local variable name `order`, which broke on a rename while the property it was
        guarding was untouched. What must be true is that heatOf feeds a comparator and never
        reaches a per-company number."""
        body = re.search(r"function drawBuckets\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertRegex(body, r"\.sort\(\(a, b\) => \{[\s\S]{0,300}?heatOf\(b\) - heatOf\(a\)",
                         "heat must order the grid through a sort comparator")
        # It may size its own bar and it may sort. It may not touch a company's metrics.
        self.assertNotRegex(body, r"heatOf\([^)]*\)\s*[*/+-]\s*(?:r\.|score|rank|pe|beta)")
        self.assertNotRegex(self.html, r"(?:score|rank|pe|beta)\s*[*/+-]\s*heatOf\(")

    def test_the_shock_menu_the_heat_table_and_the_hints_agree(self):
        """Three lists that must be the same list. A shock in the menu with no heat key
        silently reads every bucket as 0 and flattens the grid; a heat key with no menu entry
        is a shock nobody can select; a hint for neither is guidance for a state that cannot
        be reached."""
        keys = set()
        for b in sb.BUCKETS:
            keys |= set(b["heat"])
        menu = set(re.findall(
            r'<option value="(\w+)"',
            re.search(r'id="bucketShock".*?</select>', self.html, re.S).group(0)))
        self.assertEqual(sorted(menu - keys), [],
                         "selectable shocks with no heat data: every bucket would read 0")
        self.assertEqual(sorted(keys - menu), [],
                         "heat data for shocks nobody can select")
        self.assertEqual(sorted(set(sb.SHOCK_HINTS) - menu), [],
                         "hints for shocks that are not in the menu")

    def test_the_clock_bump_cannot_exceed_the_authored_scale(self):
        """The heat table is authored on a 0-4 scale. Letting the clock bump run past it
        would invent a fifth level of a judgement that only has four.

        This used to assert the substring `Math.min(HEAT_MAX, h + 1)` in the emitted JS. That
        checked the arithmetic's SPELLING, and the arithmetic no longer travels — the browser
        receives a precomputed table. So the property is now asserted over every value the
        browser can actually read, which is strictly stronger: the old form passed on an
        emitter that shipped the right expression and the wrong numbers."""
        highest = max(v for b in sb.BUCKETS for v in b["heat"].values())
        self.assertEqual(sb.HEAT_MAX, highest,
                         "the ceiling and the table it caps have come apart")
        table = sb.heat_table()
        emitted = [v for row in table.values()
                   for by_clock in row.values() for v in by_clock.values()]
        self.assertTrue(emitted, "the heat table is empty")
        self.assertEqual([v for v in emitted if not 0 <= v <= sb.HEAT_MAX], [],
                         "an emitted heat is outside the authored 0-HEAT_MAX scale")
        self.assertEqual(max(emitted), sb.HEAT_MAX,
                         "no emitted state reaches the ceiling, so the scale is not the "
                         "one the table is authored on")
        # The ceiling alone is not the property. `min(HEAT_MAX, h + 2)` never exceeds the
        # scale either, and it silently doubles the step — a heat of 2 that the clock leads
        # would print 4, the ledger's top level, for a bucket its author scored mid. The
        # string this test used to assert pinned the step by accident; this pins it on
        # purpose. Every state is the authored heat, or exactly one step above it.
        off = [(b["id"], shock, clock, table[b["id"]][shock][clock], authored)
               for b in sb.BUCKETS
               for shock, authored in b["heat"].items()
               for clock, leads in sb.CLOCK_LEADS.items()
               if table[b["id"]][shock][clock] != (
                   min(sb.HEAT_MAX, authored + 1)
                   if authored and b["id"] in leads else authored)]
        self.assertEqual(off, [], "the clock bump is not exactly one step: {}".format(off[:5]))

    def test_no_surface_restates_the_ceiling(self):
        """`heat / 4` reads correctly and is a second copy of HEAT_MAX. It stops reading
        correctly the moment the table gains a fifth level, and it does so silently."""
        for path in (os.path.join(REPO, "tools", "research_ui.py"),
                     os.path.join(REPO, "docs", "research",
                                  "SCREENER_COMBINED_DRAFT.html")):
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            self.assertNotRegex(
                src, r"heatOf\([^)]*\)\}? ?/ ?\d",
                "{} divides a heat by a hard-coded ceiling; use HEAT_MAX".format(
                    os.path.basename(path)))

    def test_the_clock_bump_cannot_create_relevance_from_nothing(self):
        """A bucket the ledger scored 0 under a shock stays 0. The clock says which theses
        LEAD at a stage, not that an irrelevant one becomes relevant — lifting 0 to 1 drew a
        heat bar on a bucket explicitly marked as not applying, and let it outrank buckets the
        ledger had scored above it.

        Every (bucket, shock) pair is authored, so this is not a guess about missing data:
        a 0 here is someone writing zero."""
        self.assertEqual(
            [(b["id"], s) for b in sb.BUCKETS
             for s in sb.SHOCK_HINTS if s not in b["heat"]], [],
            "a heat is missing, so a 0 no longer unambiguously means 'scored zero'")
        # The two assertions that followed read the emitted SOURCE — that `if(h === 0)
        # return 0;` appeared, and that it appeared before `CLOCK_LEADS`. Both described one
        # particular way of writing the rule, and the rule no longer travels as source. The
        # property they were protecting is asserted directly instead, over every state a
        # surface can read: an authored zero emits zero at every clock, including the clocks
        # that lead that bucket. Source ordering cannot express that; this cannot miss it.
        table = sb.heat_table()
        lifted = [(b["id"], shock, clock)
                  for b in sb.BUCKETS
                  for shock, authored in b["heat"].items() if authored == 0
                  for clock in sb.CLOCK_LEADS
                  if table[b["id"]][shock][clock] != 0]
        self.assertEqual(lifted, [],
                         "the clock lifted an authored zero: {}".format(lifted[:5]))
        # And the case that motivates it: the 16 states where a zero-scored bucket IS led by
        # the selected clock. If this set is ever empty the test above has stopped proving
        # anything, because no clock would be trying to lift a zero in the first place.
        tempted = [(b["id"], shock, clock)
                   for b in sb.BUCKETS
                   for shock, authored in b["heat"].items() if authored == 0
                   for clock, leads in sb.CLOCK_LEADS.items() if b["id"] in leads]
        self.assertTrue(tempted,
                        "no authored zero is led by any clock, so this guard is vacuous")

    def test_neither_surface_can_answer_this_for_itself(self):
        """The two surfaces used to hold the rule separately and had already stopped agreeing
        — 16 of the 420 bucket x shock x clock states differed. Equality between two copies is
        not the property worth guarding; having one copy is. Nothing here compares the pages,
        because there is no longer anything on either page to compare."""
        for path in (os.path.join(REPO, "tools", "research_ui.py"),
                     os.path.join(REPO, "docs", "research",
                                  "SCREENER_COMBINED_DRAFT.html")):
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            name = os.path.basename(path)
            # Declarations AND uses. Watching only declarations let two bare `HEAT_MAX`
            # references survive the move to the shared rule: source-reading tests passed
            # and the served page threw ReferenceError on first draw. A name this file no
            # longer declares may only be reached through the namespace.
            # A name is legitimately bare only if the file took it out of the namespace by
            # destructuring. Otherwise every read must be qualified.
            taken = set()
            for grab in re.finditer(r"\{([^{}]*)\}\s*=\s*window\.LEDGER", src):
                taken |= set(re.findall(r"\w+", grab.group(1)))
            for owned in ("CLOCK_LEADS", "HEAT_MAX", "bucketHeat"):
                self.assertNotRegex(
                    src, r"(?:const|let|var|function)\s+{}\b".format(owned),
                    "{} defines {}, which the ledger owns".format(name, owned))
                if owned in taken:
                    continue
                for use in re.finditer(r"(?<![.\w]){}\b".format(owned), src):
                    line = src[src.rfind("\n", 0, use.start()) + 1:use.start()]
                    if line.lstrip().startswith(("*", "//", "#", "/*")):
                        continue   # prose naming the constant, not reading it
                    self.fail(
                        "{} reads a bare {} it neither declares nor destructures from "
                        "window.LEDGER: {!r}".format(name, owned, line.strip()[:70]))
            self.assertNotRegex(src, r'clock\s*===\s*"T\d"',
                                "{} bumps by clock itself".format(name))
            body = re.search(r"function heatOf\(b\)\s*\{(.*?)\n?\}", src, re.S)
            self.assertIsNotNone(body, "{} has no heatOf".format(name))
            self.assertIn("bucketHeat(", body.group(1),
                          "{}'s heatOf must delegate to the shared rule".format(name))


class ThePinnedCardsFollowABucketName(unittest.TestCase):
    """Clicking a constituent pins it and the charts move — the cards at the top must point at
    it too. 149 of 202 constituents are outside the fundamentals universe by design, so this
    is the common case rather than the edge one."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_a_pinned_name_with_no_row_is_not_reported_as_nothing_pinned(self):
        """The detail card had two branches for three states, so pinning IRDM moved the price
        chart onto it and left the card beside that chart saying nothing was pinned."""
        for fn in ("drawCard", "renderHeadlines"):
            body = re.search(r"function {}\(\)\{{(.*?)\n\}}".format(fn),
                             self.html, re.S)
            self.assertIsNotNone(body, fn)
            self.assertRegex(
                body.group(1), r"if\(!r && selected\)\{",
                "{} must separate 'nothing pinned' from 'pinned, no fundamentals "
                "row'".format(fn))

    def test_it_shows_what_it_does_know(self):
        """Absence of a fundamentals row is not absence of everything: the price, the bucket
        and the tier are all present and are what the reader clicked for."""
        body = re.search(r"function drawCard\(\)\{(.*?)\n\}", self.html, re.S).group(1)
        for cell in ("Window return", "Last close", "Bucket", "Tier"):
            self.assertIn(cell, body, "the no-row card drops {}".format(cell))
        self.assertIn("is pinned", body)
        self.assertIn("absence, not a zero", body)

    def test_pinning_a_constituent_does_not_need_the_page_scrolled(self):
        """This used to assert that clicking a constituent scrolled the top cards into view,
        because the constituents table lived in a region a page-scroll below the board and a
        click that only changed something off-screen read as a click that did nothing.

        The table is a board module now, sitting among the cards it updates, so the scroll —
        and `revealCards`, which existed only for it — is gone. Guarded as the property that
        replaced it: the module is on the board, so there is nowhere for the pin to happen
        out of sight."""
        self.assertNotIn("revealCards", self.html,
                         "a scroll-into-view helper is back; the constituents module should "
                         "be adjacent to what it pins")
        board = re.search(r'<div class="board" id="board">(.*?)\n    </div>', self.html, re.S)
        self.assertIn('data-id="bwatch"', board.group(1))


class TheContextHasNoSecondLayoutSystem(unittest.TestCase):
    """Three tests used to live here guarding the bay's slot table: that slots were assigned
    by order rather than pinned per id, that a hidden card did not hold its slot open, and
    that a stored order was repaired rather than trusted. Every one of those hazards existed
    because the bay was a second region with its own arrangement machinery.

    The context holds a control row and a grid, in that order, always both. There is no slot
    to assign, no card to hide and no order to store — so the tests are replaced by the
    property that makes them unnecessary rather than deleted quietly."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_there_is_one_arrangement_system(self):
        for gone in ("BAY_SLOTS", "BAY_ORDER", "loadBayOrder", "layoutBay", "initBayDrag",
                     "bayShown", "setBayShown", "isBayTile"):
            self.assertNotIn(gone, self.html,
                             "{} is back — the context has grown a second layout system "
                             "again".format(gone))

    def test_the_context_content_is_not_addressable_as_tiles(self):
        """A grid-area pinned per id was what made the old cards immovable. Nothing in the
        context is positioned by id now because nothing in it is positioned at all."""
        self.assertNotRegex(self.html, r"#tile-buckets\{grid-area:")
        self.assertNotRegex(self.html, r"#tile-bucketctl\{grid-area:")
        self.assertNotIn('data-id="bucketctl"', self.html)
        self.assertNotIn('data-id="buckets"', self.html)


class EveryQuestionMarkExplainsItsOwnColumn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "docs", "research",
                               "SCREENER_COMBINED_DRAFT.html"), encoding="utf-8") as fh:
            cls.html = fh.read()

    def test_each_button_names_the_panel_it_opens(self):
        """They all opened shadowExplain regardless of what they were attached to — right
        while all three were about shadow debt, and silently wrong the moment one was not. A
        "?" that explains a different column is worse than no "?" at all."""
        self.assertNotRegex(self.html, r'class="qmark" data-explain[ \n]+aria',
                            "a question mark with no named panel is left")
        self.assertRegex(
            self.html,
            r'panelOpen\(document\.getElementById\(q\.dataset\.explain \|\| "shadowExplain"\)')

    def test_every_named_panel_exists(self):
        named = set(re.findall(r'data-explain="(\w+)"', self.html))
        self.assertTrue(named, "no question mark names a panel")
        for pid in sorted(named):
            self.assertRegex(self.html, r'id="{}"'.format(pid),
                             "no panel with id {}".format(pid))

    def test_the_growth_column_explains_its_fallback(self):
        """The column is earningsGrowth OR revenueGrowth and the row does not say which, which
        is why a base-effect name can read 1368%. Both halves have to be stated."""
        panel = re.search(r'id="growthExplain".*?</div>', self.html, re.S).group(0)
        self.assertIn("earningsGrowth", panel)
        self.assertIn("revenueGrowth", panel)
        self.assertIn("base", panel)
        self.assertIn("absent, not zero", panel.replace("</b>", "").replace("<b>", ""))


class ThePriceUniverseCoversTheBuckets(unittest.TestCase):
    def test_every_tradeable_constituent_is_requested(self):
        missing = sorted(set(sb.price_tickers()) - set(sc.price_universe()))
        self.assertEqual(missing, [],
                         "these constituents would never be fetched: {}".format(missing))

    def test_the_delisted_are_not_requested(self):
        """Asking anyway spends batch slots to be told what this module already records — and
        a vendor that answers a dead symbol with a stale or reused quote would be believed."""
        asked = set(sc.price_universe())
        for ticker in sb.DELISTED:
            self.assertNotIn(ticker, asked)

    def test_the_fundamentals_universe_is_not_widened_by_this(self):
        """UNIVERSE exists to carry per-company fundamentals and an ETF has no P/E. Prices are
        a separate question with a much wider answer; conflating them would put SGOV in the
        screener's results table with an absent P/E and no explanation for why."""
        fundamentals = {t for t, *_ in sc.UNIVERSE}
        self.assertNotIn("SGOV", fundamentals)
        self.assertNotIn("CL=F", fundamentals)
        self.assertLess(len(fundamentals), len(sc.price_universe()))

    def test_the_price_payload_records_the_delisted(self):
        prices = sc.load_prices()
        if not prices:
            self.skipTest("no price cache in this checkout")
        self.assertEqual(prices.get("delisted"), dict(sb.DELISTED),
                         "the payload must carry why a constituent has no series")


if __name__ == "__main__":
    unittest.main()


class EveryConstituentIsScreenedOrExplained(unittest.TestCase):
    """Selecting two buckets emptied the whole board, and the page said "no match in this
    lens" about names no lens had ever seen. 149 of the 202 constituents carried no
    fundamentals row, so a bucket could be plotted and not screened — and the two states were
    reported with the same sentence.

    The rule this encodes: a constituent is either in the fundamentals universe or there is a
    recorded reason it cannot be. There is no third state, because the third state is what
    reads as "the screener found nothing"."""

    def test_no_constituent_is_silently_unscreenable(self):
        universe = {r[0] for r in sc.universe_rows()}
        unexplained = [
            t for t in sb.all_tickers()
            if t not in universe and t not in sb.DELISTED and t not in sb.NOT_COMPANIES]
        self.assertEqual(
            unexplained, [],
            "these constituents are in no bucket lens and no absence table — the page can "
            "only say 'no fundamentals row', which reads as an unrun fetch")

    def test_the_two_absence_tables_do_not_overlap(self):
        """A name is delisted or it is not a company. Both would let the page pick whichever
        reason it looked up first, and the two sentences tell a reader to do different
        things."""
        both = sorted(set(sb.DELISTED) & set(sb.NOT_COMPANIES))
        self.assertEqual(both, [], "recorded as delisted AND as not-a-company")

    def test_nothing_is_excused_that_is_not_a_constituent(self):
        """An absence table entry for a name no bucket holds is a stale exemption: it excuses
        nothing, and it would go on excusing a ticker after the bucket dropped it."""
        named = set(sb.all_tickers())
        for table, label in ((sb.DELISTED, "DELISTED"), (sb.NOT_COMPANIES, "NOT_COMPANIES")):
            stray = sorted(t for t in table if t not in named)
            self.assertEqual(stray, [], "{} excuses names no bucket holds".format(label))

    def test_a_fund_never_enters_the_fundamentals_universe(self):
        """The universe exists to carry per-company fundamentals. A fund in it would be
        fetched, come back with no P/E and no sector, and then be indistinguishable from a
        company the vendor happened to have nothing for."""
        universe = {r[0] for r in sc.universe_rows()}
        wrong = sorted(universe & set(sb.NOT_COMPANIES))
        self.assertEqual(wrong, [], "not-a-company entries are in the fundamentals universe")

    def test_the_screener_tag_of_every_constituent_is_a_real_bucket_tag(self):
        for ticker, _ai in sc.BUCKET_CONSTITUENTS:
            tag = sb.screen_tag_for(ticker)
            self.assertIsNotNone(tag, "{} has no bucket screen_tag".format(ticker))
            self.assertIn(tag, sc.CHAOS_BUCKETS, ticker)

    def test_the_two_bucket_vocabularies_are_one(self):
        """CHAOS_BUCKETS was a hand-kept list of 19 strings naming the same 20 buckets the
        ledger defines. Derived now, so a renamed bucket cannot leave a screener tag behind
        pointing at a bucket that no longer answers to it."""
        with open(os.path.join(REPO, "tools", "stock_screener.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotRegex(
            src, r"CHAOS_BUCKETS = \(\s*\"",
            "CHAOS_BUCKETS is written out again instead of read off sovereign_buckets")
        self.assertEqual(
            set(sc.CHAOS_BUCKETS),
            {b["screen_tag"] for b in sb.BUCKETS if b["screen_tag"]})


class TheUniverseSaysWhereItsJudgementsCameFrom(unittest.TestCase):
    """The `ai` tag is editorial. 123 of them were authored by hand and 102 by agents against
    those as the standard; both are judgement and both are editable, but a reader deciding
    whether to trust one has to be able to tell which they are looking at."""

    def test_the_two_lists_stay_separate(self):
        authored = {e[0] for e in sc.UNIVERSE}
        derived = {t for t, _ai in sc.BUCKET_CONSTITUENTS}
        self.assertEqual(sorted(authored & derived), [],
                         "a ticker is in both lists — its provenance is now ambiguous")

    def test_the_derived_rows_carry_no_transcribed_name_or_sector(self):
        """Vendor-sourced, per the fetch. A hand-typed name here would be a second spelling of
        something the same API response already carries."""
        for ticker, name, sector, _ai, _b in sc.universe_rows():
            if ticker in {t for t, _ in sc.BUCKET_CONSTITUENTS}:
                self.assertIsNone(name, ticker)
                self.assertIsNone(sector, ticker)

    def test_every_constituent_tag_is_legal(self):
        for ticker, ai in sc.BUCKET_CONSTITUENTS:
            self.assertIn(ai, sc.AI_TAGS, ticker)

    def test_the_technology_floor_the_adjudication_relied_on_still_holds(self):
        """One classification dispute was settled by measuring that no Technology-sector name
        in the authored universe is tagged `low` — ZS was held at medium on that basis. If
        that floor ever moves, the reasoning behind that tag is gone and it should be
        revisited rather than silently inherited."""
        tech_low = [e[0] for e in sc.UNIVERSE if e[2] == "Technology" and e[3] == "low"]
        self.assertEqual(
            tech_low, [],
            "a Technology name is now tagged low; ZS was held at medium because none was")


class TheBucketsPageDrawsWhatWasFetched(unittest.TestCase):
    """`genSeries()` on this page was `mulberry32(hashStr(symbol))` — a seeded random walk over
    a hash of the ticker string, with a +0.02 per-step drift baked in, under a caption stating
    the numbers came down the yfinance path. It drew SHV, a 1-3 month Treasury ETF, at +18.0%
    over six months against a real +1.7%, and two confident years of price action for EURN, X
    and MRO, which no longer trade — a hash of a delisted ticker hashes exactly as well as a
    live one.

    The rule: a page draws a number it FETCHED or says it has none. There is no third option,
    and "shaped like the real thing" is the most dangerous version of the third because it
    survives review."""

    @classmethod
    def setUpClass(cls):
        cls.page = _served_buckets()

    def test_the_seeded_walk_is_gone(self):
        """Matched as CODE, not as a word: the comment recording what was removed names
        mulberry32 on purpose, and a test forbidding the name would forbid the explanation."""
        self.assertNotRegex(self.page, r"function mulberry32\(",
                            "the seeded price generator is back on the buckets page")
        self.assertNotRegex(self.page, r"function hashStr\(")
        self.assertNotRegex(self.page, r"function genSeries\(")
        self.assertNotRegex(self.page, r"Math\.random\(")

    def test_the_series_come_from_the_fetched_cache(self):
        body = re.search(r"function seriesFor\(symbol, n\)\{(.*?)\n\}", self.page, re.S)
        self.assertIsNotNone(body, "seriesFor is gone")
        body = body.group(1)
        self.assertIn("const s = PRICES[symbol];", body,
                      "the series must be read from the injected cache and nothing else")
        # The absence path, asserted explicitly. Matching only the opening lines let a
        # hardcoded `return [50,51,52]` through — a fabricated series is exactly the defect
        # this class exists to catch, and it would have been caught by nothing.
        self.assertRegex(body, r"length < 2\) return null;",
                         "a ticker with no usable series must return null, not a stand-in")
        for ret in re.findall(r"return ([^;]+);", body):
            self.assertNotRegex(ret.strip(), r"^\[",
                                "seriesFor returns a literal array: {}".format(ret.strip()))
        self.assertRegex(self.page, r"const PRICES = \{", "no price cache was injected")

    def test_a_ticker_with_no_series_gets_a_reason_not_a_line(self):
        """Three absences, and they send a reader to different places: a fetch closes the
        first, nothing closes the other two."""
        self.assertRegex(self.page, r"function whyNoSeries\(symbol\)\{")
        for reason in ("no per-company price here", "delisted", "not in the fetched snapshot"):
            self.assertIn(reason, self.page, "missing absence reason: {}".format(reason))

    def test_the_page_no_longer_claims_a_live_quote_path(self):
        """The caption asserted `fetch_yfinance daily -> disk/SQLite cache -> this UI` over
        numbers that had never been near yfinance. It is true now, and it says what it is:
        daily closes as of a stamped fetch, not a live quote."""
        self.assertNotRegex(self.page, r"Same path as the noise screener / live quote path")
        self.assertIn("Not a live quote path", self.page)

    def test_the_real_closes_actually_reach_the_page(self):
        """The strongest form of the check: a cash ETF has to look like a cash ETF. The PRNG
        drew SHV at +18.0% over six months; T-bill funds do not do that."""
        import json as _json
        m = re.search(r"const PRICES = (\{.*?\});", self.page, re.S)
        self.assertIsNotNone(m, "no injected price cache")
        prices = _json.loads(m.group(1))
        if not prices:
            self.skipTest("no prices.json in this checkout — nothing to verify against")
        for tk in ("SHV", "BIL", "SGOV"):
            series = prices.get(tk)
            self.assertTrue(series and len(series) > 2, "{} has no series".format(tk))
            ret = (series[-1] / series[0] - 1) * 100
            self.assertLess(abs(ret), 8.0,
                            "{} moved {:.1f}% over the window — a 1-3 month T-bill fund does "
                            "not, so this is not a real series".format(tk, ret))


class TheHeatRuleHasOneImplementation(unittest.TestCase):
    """`bucketHeat` was a JavaScript string literal that only ever ran in a browser, which
    put the ledger's single most-read rule out of reach of every assertion in this suite.

    That is not a small gap. This repo installs Python alone in CI (`.github/workflows/
    test.yml` has no `actions/setup-node`), ships no JS engine reachable from Python, and its
    one `node --check` guard raises `SkipTest` when node is missing on the stated principle
    that "an unrunnable check is not a failing one". So any parity test written against
    executed JavaScript would have skipped on every CI run — a proof that pins nothing.

    The arithmetic now lives in `sovereign_buckets.bucket_heat` and the browser receives
    `heat_table()`, evaluated from it. The obvious alternative — a template that renders the
    rule back out as JS — was rejected because the arithmetic would still exist twice, once in
    Python and once in a format string, which is the two-copies condition this module was
    written to end (`sovereign_buckets.py:9-13`: they "agreed on the tables and disagreed on
    the arithmetic").

    A table makes parity a pure-Python assertion over `json.loads`. It cannot skip."""

    @classmethod
    def setUpClass(cls):
        cls.js = sb.runtime_js()
        m = re.search(r"^  const HEAT = (\{.*\});$", cls.js, re.M)
        assert m, "the emitted runtime carries no HEAT table"
        cls.emitted = json.loads(m.group(1))

    def _states(self):
        for b in sb.BUCKETS:
            for shock in b["heat"]:
                for clock in sb.CLOCK_LEADS:
                    yield b, shock, clock

    def test_every_emitted_state_equals_the_python_rule(self):
        """The whole point. What a surface reads is what `bucket_heat` computes, for all of
        it — not for a sample, and not for the states someone thought to check."""
        wrong = [(b["id"], shock, clock,
                  self.emitted[b["id"]][shock][clock], sb.bucket_heat(b, shock, clock))
                 for b, shock, clock in self._states()
                 if self.emitted[b["id"]][shock][clock] != sb.bucket_heat(b, shock, clock)]
        self.assertEqual(wrong, [], "emitted heat disagrees with bucket_heat: {}".format(
            wrong[:5]))

    def test_the_emitted_state_space_is_exactly_the_authored_one(self):
        """A table with a missing row answers `undefined` for a real state; a table with an
        extra row answers for a state nobody authored. Both are silent."""
        self.assertEqual(sorted(self.emitted), sorted(b["id"] for b in sb.BUCKETS),
                         "the emitted table's buckets are not the ledger's buckets")
        for b in sb.BUCKETS:
            self.assertEqual(sorted(self.emitted[b["id"]]), sorted(b["heat"]),
                             "bucket {} emits a different shock set than it authors".format(
                                 b["id"]))
            for shock in b["heat"]:
                self.assertEqual(sorted(self.emitted[b["id"]][shock]),
                                 sorted(sb.CLOCK_LEADS),
                                 "bucket {} under {} emits a different clock set".format(
                                     b["id"], shock))
        count = sum(len(by_shock) * len(sb.CLOCK_LEADS)
                    for by_shock in (b["heat"] for b in sb.BUCKETS))
        self.assertEqual(sum(len(c) for r in self.emitted.values() for c in r.values()),
                         count, "the emitted state count is not the authored one")

    def test_the_bump_arithmetic_does_not_travel(self):
        """If the BUMP is emitted as arithmetic anywhere there are two implementations again,
        and the parity test above is proving a copy against itself.

        Scoped to the bump, not to every read of `b.heat`: the emitted lookup legitimately
        falls back to the authored heat for an unknown clock (see the next test), and a token
        list that forbade `b.heat[` outright would have forced that fallback out and taken
        the behaviour-preservation with it. What must not travel is the clock arithmetic —
        the ceiling, the step, and the lead-list membership test."""
        for token in ("Math.min", "HEAT_MAX, h", "h + 1", "CLOCK_LEADS[clock]", "indexOf(b.id)"):
            self.assertNotIn(token, self.js,
                             "the emitted runtime still computes the bump ({!r}); it must "
                             "only look it up".format(token))

    def test_the_lookup_answers_every_miss_the_way_the_rule_did(self):
        """Three inputs nobody reaches on purpose, and the old rule had an answer for each.
        A consolidation that changes one of them is not a consolidation.

        Measured before this refactor: an unknown bucket or shock gave 0, and an UNKNOWN CLOCK
        gave the authored heat unbumped — `(CLOCK_LEADS[clock] || [])` found the bucket in an
        empty list and returned `h`. A bare table read returns `undefined` for all three, which
        `|| 0` would flatten to 0 — bucket 01 under hormuz at a typo'd clock measured 1 before
        and 0 after. Unreachable through the menus (the reconciliation test keeps it so), and
        still a behaviour change this phase forbids."""
        rule = re.search(r"function bucketHeat\(.*?\n  \}", self.js, re.S).group(0)
        self.assertIn("clock in row[shock]", rule,
                      "the lookup does not distinguish an unknown clock from a known one, so "
                      "a typo'd clock returns 0 instead of the authored heat")
        self.assertRegex(rule, r"return \(b\.heat && b\.heat\[shock\]\) \|\| 0;",
                         "the unknown-clock fallback must return the authored heat, and an "
                         "unknown bucket or shock must still return 0 rather than undefined")

    def test_every_bucket_the_page_receives_has_a_row(self):
        """The fallback above must stay unreachable in practice: the page fills BUCKETS from
        the same emit that carries HEAT, so every id it can ask about must be present."""
        shipped = json.loads(re.search(r"^  const BUCKETS = (\[.*\]);$", self.js, re.M)
                             .group(1))
        self.assertEqual([b["id"] for b in shipped if b["id"] not in self.emitted], [],
                         "a shipped bucket has no heat row and would fall back to 0")

    def test_the_clock_menus_and_the_lead_table_agree(self):
        """The shock menu, heat table and hints are reconciled (above); the clock never was.
        A surface offering a stage the lead table does not know returns unbumped heat and
        says nothing — the reader sees a clock that silently does nothing."""
        pages = {
            "SCREENER_COMBINED_DRAFT.html": os.path.join(
                REPO, "docs", "research", "SCREENER_COMBINED_DRAFT.html"),
            "SOVEREIGN_LEDGER_OPTIONS_MOCK.html": os.path.join(
                REPO, "docs", "research", "SOVEREIGN_LEDGER_OPTIONS_MOCK.html"),
            "research_ui.py": os.path.join(REPO, "tools", "research_ui.py"),
        }
        for name, path in pages.items():
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            sel = re.search(r'id="(?:bucket)?[Cc]lock"[^>]*>(.*?)</select>', src, re.S)
            self.assertIsNotNone(sel, "{} has no clock menu".format(name))
            menu = set(re.findall(r'value="([^"]+)"', sel.group(1)))
            self.assertEqual(sorted(menu), sorted(sb.CLOCK_LEADS),
                             "{}'s clock menu and CLOCK_LEADS disagree".format(name))
