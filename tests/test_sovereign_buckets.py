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


class TheTableHasOneSource(unittest.TestCase):
    def test_research_ui_holds_no_literal_of_its_own(self):
        with open(os.path.join(REPO, "tools", "research_ui.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn(
            "const BUCKETS = [\n", src,
            "the bucket table is written down in research_ui again — it must be serialised "
            "from sovereign_buckets.as_js() at render time")
        self.assertIn("sovereign_buckets.as_js()", src)

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
        be closed or brought back is not a module, it is furniture.

        They live in BAY_IDS rather than TILE_IDS: the bay below the results table is a
        different region from the split-tree board, and layoutBoard HIDES every TILE_ID it
        did not place — one shared list made the whole buckets section vanish on the first
        layout pass. Widget options offers both registries."""
        bay = re.search(r"const BAY_IDS  = \[(.*?)\];", self.html, re.S).group(1)
        for tile in ("bucketctl", "buckets", "bpanel", "bwatch"):
            self.assertIn('"{}"'.format(tile), bay,
                          "{} is not a bay tile".format(tile))
            self.assertRegex(self.html, r'data-id="{}"'.format(tile))
            self.assertRegex(self.html, r"{}\s*:".format(tile),
                             "{} has no label/note entry".format(tile))
        self.assertRegex(
            self.html, r"tileOrder\(ALL_TILE_IDS\.filter\(id => !parked\.includes\(id\)\)\)",
            "the widget panel must offer both registries, or a bay card cannot be reopened")

    def test_a_bay_tile_never_goes_onto_the_split_tree(self):
        """placeIntoLargestPane would drop a bucket card into the analysis board, and then
        layoutBoard would position it absolutely inside a container it is not a child of."""
        self.assertRegex(
            self.html,
            r"if\(isBayTile\(id\)\)\{ setBayShown\(id, on\); return; \}",
            "setTilePlaced must route bay tiles to the bay")

    def test_the_bay_sits_below_the_results_table(self):
        results = self.html.index("<h2>Results</h2>")
        bay = self.html.index('id="bucketBay"')
        self.assertLess(results, bay,
                        "the buckets bay must come after the results table, not before it")

    def test_the_bay_reproduces_the_buckets_page_layout(self):
        """Controls across the top, grid under them, chart beside the supporting cards."""
        areas = re.search(r'grid-template-areas:(.*?)\}', self.html, re.S).group(1)
        for want in ('"ctl ctl"', '"grid grid"', '"chart side1"'):
            self.assertIn(want, areas, "bay layout lost {}".format(want))

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
            r"if\(BUCKET_SEL\.size\)\{[\s\S]{0,900}?bucketNames\(\)\.forEach\(push\)")

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
        would invent a fifth level of a judgement that only has four."""
        self.assertRegex(self.html, r"const HEAT_MAX = 4;")
        self.assertRegex(self.html, r"Math\.min\(HEAT_MAX, h \+ 1\)")

    def test_the_clock_bump_cannot_create_relevance_from_nothing(self):
        """A bucket the ledger scored 0 under a shock stays 0. The clock says which theses
        LEAD at a stage, not that an irrelevant one becomes relevant — lifting 0 to 1 drew a
        heat bar on a bucket explicitly marked as not applying, and let it outrank buckets the
        ledger had scored above it."""
        body = re.search(r"function heatOf\(b\)\{(.*?)\n\}", self.html, re.S).group(1)
        self.assertRegex(body, r"if\(h === 0\) return 0;",
                         "the bump must not apply to an authored zero")
        self.assertLess(body.index("if(h === 0) return 0;"), body.index("CLOCK_LEADS"),
                        "the zero check must run before the bump, not after it")

    def test_the_clock_leads_match_the_buckets_page(self):
        """Both surfaces must rank the theses identically, or the same shock and clock give
        two different answers depending on which page you opened."""
        with open(os.path.join(REPO, "tools", "research_ui.py"), encoding="utf-8") as fh:
            src = fh.read()
        original = dict(re.findall(
            r'clock==="(T\d)"&&\[([^\]]+)\]\.includes\(b\.id\)', src))
        self.assertTrue(original, "the buckets page's clock bump is gone — re-derive this")
        ported = re.search(r"const CLOCK_LEADS = \{(.*?)\n\};", self.html, re.S).group(1)
        for clock, ids in original.items():
            want = sorted(re.findall(r'"(\d+)"', ids))
            got = re.search(r"{}: \[([^\]]+)\]".format(clock), ported)
            self.assertIsNotNone(got, "{} missing from CLOCK_LEADS".format(clock))
            self.assertEqual(sorted(re.findall(r'"(\d+)"', got.group(1))), want,
                             "{} leads differ between the two surfaces".format(clock))


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
