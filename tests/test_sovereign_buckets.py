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
