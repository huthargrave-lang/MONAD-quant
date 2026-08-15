"""A screen whose four columns are four different kinds of fact — and the guards that
keep them from collapsing into one.

Tool: `tools/screener_lab.py`. Page: `/sentiment` in `tools/research_ui.py`.
Study: `docs/research/SCREENER_value_growth_sentiment.md`.

The screen asks for cheap, fast-growing companies and reads sentiment about them from
Bloomberg and Reddit. Three of those four inputs behaved differently from the way the
first implementation assumed, and every one of the differences was found by running it
against live vendor data rather than by reasoning about the code:

1. **Reddit's anonymous API is off, not flaky.** `www`, `old`, `api` and `oauth`
   reddit hosts all answer 403 here, under a browser and a script user-agent alike.
   Reddit requires OAuth for reads, so no header fixes it. The column is fully wired
   and turns on the moment credentials exist; until then every ticker's Reddit tone is
   `None`, and `None` renders as "no coverage" — never as 0.00. That distinction is the
   absence-flag family (F155/F159/F188/F204) applied to a data source: "nobody spoke"
   and "opinion cancelled to zero" are opposite findings and must not share a cell.

2. **Matching a document to a ticker on one name token invents coverage.** General
   Motors reduced to the alias "general", so three Bloomberg political headlines
   ("Attorney General Nomination Advanced by Senate") were scored as GM sentiment. A
   ticker whose tone is drawn from articles about a different subject is worse than one
   with no tone, because it looks like data. Aliases are now conjunctive.

3. **"High growth" from the vendor's YoY fields is mostly base effects.** The first run
   ranked Aflac first at "2434% growth" — earnings off a depressed base quarter, on
   27.9% revenue growth. Two things were wrong. `earningsGrowth` and
   `earningsQuarterlyGrowth` are near-duplicates (AFL 3860%/3414%, BMY 153.1%/153.2%),
   so averaging all three vendor fields gave earnings two votes to revenue's one; and
   nothing distinguished a company growing from one lapping a bad quarter. Earnings is
   now collapsed to one component before blending, and a flagged row is ranked on
   REVENUE growth — the component still worth trusting — with the raw figure still
   printed beside the flag. Allstate, AES, Bristol-Myers and Berkshire left the top ten
   as a result; Alphabet stayed.

The tests below are written so that each of those three regressions fails loudly if
reintroduced. Everything network-shaped is injected, so the suite runs offline.

Run: `venv/bin/python -m unittest tests.test_screener_lab -v`
"""
from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")
for _p in (REPO, TOOLS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import screener_lab as lab  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=200, text="", payload=None, headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


BLOOMBERG_XML = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title><![CDATA[Pfizer Raises Sales Guidance on Strong Demand]]></title>
<description><![CDATA[The drugmaker beat estimates.]]></description>
<link>https://www.bloomberg.com/news/articles/a</link>
<pubDate>Mon, 03 Aug 2026 22:13:40 GMT</pubDate></item>
<item><title><![CDATA[Blanche Attorney General Nomination Advanced by Senate]]></title>
<description><![CDATA[A procedural vote.]]></description>
<link>https://www.bloomberg.com/news/articles/b</link>
<pubDate>Mon, 03 Aug 2026 21:00:00 GMT</pubDate></item>
</channel></rss>"""


REDDIT_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <author><name>/u/someone</name></author>
  <content type="html">&lt;div&gt;&lt;p&gt;A blowout quarter.&lt;/p&gt;&lt;/div&gt;</content>
  <id>t3_abc123</id>
  <link href="https://www.reddit.com/r/stocks/comments/abc123/"/>
  <updated>2026-08-04T14:00:00+00:00</updated>
  <title>NVDA earnings beat, guidance raised</title>
</entry>
</feed>"""


class ToneSeparatesAbsenceFromZero(unittest.TestCase):
    """`None` and `0.0` are different readings, at every layer."""

    def test_text_with_no_lexicon_term_is_absent_not_neutral(self):
        tone = lab.score_tone("Company schedules its annual meeting for Tuesday")
        self.assertTrue(tone.is_absent)
        self.assertIsNone(tone.score)
        self.assertNotEqual(tone.score, 0.0, "absence must not be representable as zero")

    def test_balanced_text_scores_a_real_number_near_zero(self):
        """The other side of the same coin — terms matched and cancelled. This is a
        reading, and it must NOT come back as absent."""
        tone = lab.score_tone("Profit gains offset by a weak, disappointing outlook")
        self.assertFalse(tone.is_absent)
        self.assertIsInstance(tone.score, float)
        self.assertGreaterEqual(tone.n_terms, 2)

    def test_empty_and_none_text_are_absent(self):
        for value in ("", None, "   "):
            self.assertTrue(lab.score_tone(value).is_absent)

    def test_score_is_bounded_and_signed_correctly(self):
        self.assertGreater(lab.score_tone("record profit surges, upgraded").score, 0)
        self.assertLess(lab.score_tone("bankruptcy fraud plunge writedown").score, 0)
        for text in ("soars record blowout upgrade", "crash fraud bankruptcy plunge"):
            self.assertLessEqual(abs(lab.score_tone(text).score), 1.0)

    def test_negation_flips_sign_and_is_recorded(self):
        tone = lab.score_tone("Not a strong quarter for chipmakers")
        self.assertLess(tone.score, 0)
        self.assertTrue(any(hit["negated"] for hit in tone.terms))

    def test_negation_window_does_not_reach_across_a_clause(self):
        """A negator six tokens back belongs to a different assertion. If the window
        ever widens, this flips and the test says so."""
        tone = lab.score_tone("No decision was reached by the board, but profit surged")
        self.assertGreater(tone.score, 0)

    def test_intensifier_scales_the_term_in_either_word_order(self):
        """Financial prose puts the adverb on both sides — "fell sharply" is commoner
        than "sharply fell", and an implementation that only looked backwards missed
        the dominant construction entirely."""
        plain = lab.score_tone("shares fell")
        self.assertIsNotNone(plain.score)
        for text in ("shares fell sharply", "shares sharply fell"):
            self.assertLess(lab.score_tone(text).score, plain.score, text)

    def test_a_damping_intensifier_moves_the_score_toward_zero(self):
        plain = lab.score_tone("shares fell")
        self.assertGreater(lab.score_tone("shares fell slightly").score, plain.score)

    def test_every_score_can_name_the_terms_that_made_it(self):
        """No-ML is a strategy constraint (CLAUDE.md §12.1); a score nobody can
        decompose would violate it regardless of how it was computed."""
        explanation = lab.explain_tone("Pfizer beats estimates and raised guidance")
        for term in ("beats", "raised"):
            self.assertIn(term, explanation)
        self.assertIn("ABSENT", lab.explain_tone("the meeting is on Tuesday"))

    def test_tone_is_a_mean_so_it_does_not_track_document_length(self):
        short = lab.score_tone("profit surges")
        padded = lab.score_tone("profit surges " + "the quarter was reported. " * 20)
        self.assertAlmostEqual(short.score, padded.score, places=6)


class MentionMatchingDoesNotInventCoverage(unittest.TestCase):
    """The General Motors regression, and the case-sensitivity that prevents its family."""

    def test_attorney_general_is_not_general_motors(self):
        """THE regression. One-token aliases scored three political headlines as GM
        coverage; aliases are conjunctive so both name tokens must appear."""
        self.assertIsNone(lab.mention_rule(
            "Blanche Attorney General Nomination Advanced by Senate", "GM",
            "General Motors Company"))

    def test_general_motors_itself_still_matches(self):
        """Non-vacuity: a rule that matched nothing would also pass the test above."""
        self.assertEqual(lab.mention_rule("General Motors Lifts Profit Forecast", "GM",
                                          "General Motors Company"), lab.NAME)

    def test_name_aliases_are_conjunctive_for_multi_token_names(self):
        self.assertEqual(lab.name_aliases("General Motors Company"),
                         ["general", "motors"])
        self.assertEqual(lab.name_aliases("NVIDIA Corporation"), ["nvidia"])

    def test_a_generic_industry_word_is_never_a_sole_alias(self):
        """"CVS Health Corporation" reduced to the single alias `health`, so a story
        about a salmonella outbreak — "health officials" — was scored as CVS sentiment.
        The short distinctive token is now kept, and required alongside."""
        self.assertEqual(lab.name_aliases("CVS Health Corporation"), ["health", "cvs"])
        self.assertEqual(lab.name_aliases("CMS Energy Corporation"), ["energy", "cms"])
        self.assertIsNone(lab.mention_rule(
            "Chipotle stock falls on potential link to salmonella outbreak; health "
            "officials investigate", "CVS", "CVS Health Corporation"))

    def test_the_short_token_floor_can_be_lowered_because_matching_is_conjunctive(self):
        """The four-character floor guarded against a short fragment matching prose on
        its own — a disjunctive worry. An extra REQUIRED token can only tighten a
        match, so keeping the floor high only removed evidence."""
        # Lower-cased so the symbol rule (case-sensitive, and checked first) cannot
        # fire — this exercises the name path alone.
        self.assertEqual(lab.mention_rule("Shares of Cvs Health rose on pharmacy "
                                          "margins", "CVS", "CVS Health Corporation"),
                         lab.NAME)
        self.assertEqual(lab.mention_rule("CVS Health said margins rose", "CVS",
                                          "CVS Health Corporation"), lab.SYMBOL)

    def test_lowercase_prose_never_matches_a_word_like_ticker(self):
        """Prose is Title Case and tickers are not — case sensitivity does most of the
        work here, so removing it would light up IT, ALL, NOW, SO, HAS and LOW on
        nearly every sentence in the feed."""
        for text, ticker, name in (
                ("It Is All Now Over For The Bears", "IT", "Gartner Inc."),
                ("All eyes are on the Fed", "ALL", "Allstate Corporation"),
                ("The company has low expectations now", "LOW", "Lowe's Companies"),
                ("So the deal has closed", "SO", "Southern Company")):
            self.assertIsNone(lab.mention_rule(text, ticker, name),
                              "{} matched prose".format(ticker))

    def test_uppercase_ticker_token_does_match(self):
        self.assertEqual(lab.mention_rule("TSLA slides after delivery miss", "TSLA",
                                          "Tesla Inc."), lab.SYMBOL)

    def test_cashtag_always_matches_and_outranks_other_rules(self):
        self.assertEqual(lab.mention_rule("piling into $NVDA calls", "NVDA",
                                          "NVIDIA Corporation"), lab.CASHTAG)

    def test_common_acronyms_are_not_tickers(self):
        for text, ticker in (("AI stocks rally", "AI"), ("The US and EU meet", "US"),
                             ("CEO steps down", "CEO"), ("New IPO prices", "IPO")):
            self.assertIsNone(lab.mention_rule(text, ticker, "Some Corp"),
                              "{} matched as a ticker".format(ticker))

    def test_alias_does_not_match_inside_a_longer_word(self):
        """`morgan` must not fire on "JPMorgan" — an alias that matches word-internally
        would put every compound brand name back in play."""
        self.assertIsNone(lab.mention_rule("JPMorgan lifts outlook", "JPM",
                                           "JP Morgan Chase & Co."))

    def test_the_rule_that_matched_is_reported_not_just_a_boolean(self):
        """A surprising sentiment cell has to be traceable to HOW the document was
        attached, so the rule travels with the match."""
        self.assertIn(lab.mention_rule("$PFE up", "PFE", "Pfizer, Inc."),
                      (lab.CASHTAG, lab.SYMBOL, lab.NAME))


class SentimentAttachmentRecordsCoverage(unittest.TestCase):
    def setUp(self):
        self.docs = lab.parse_rss(BLOOMBERG_XML, "markets")
        self.rows = [{"ticker": "PFE", "name": "Pfizer, Inc."},
                     {"ticker": "GM", "name": "General Motors Company"},
                     {"ticker": "ZZZZ", "name": "Nonexistent Holdings"}]
        lab.attach_sentiment(self.rows, self.docs, "bloomberg")

    def test_uncovered_ticker_gets_none_not_zero(self):
        row = self.rows[2]
        self.assertEqual(row["bloomberg_coverage"], 0)
        self.assertIsNone(row["bloomberg_tone"])

    def test_the_political_headline_is_not_attached_to_gm(self):
        self.assertEqual(self.rows[1]["bloomberg_coverage"], 0)
        self.assertIsNone(self.rows[1]["bloomberg_tone"])

    def test_covered_ticker_gets_a_score_and_its_documents(self):
        row = self.rows[0]
        self.assertEqual(row["bloomberg_coverage"], 1)
        self.assertGreater(row["bloomberg_tone"], 0)
        self.assertTrue(row["bloomberg_docs"][0]["title"])
        self.assertIn(row["bloomberg_docs"][0]["rule"],
                      (lab.CASHTAG, lab.SYMBOL, lab.NAME))

    def test_a_post_listing_many_tickers_is_not_tone_about_any_of_them(self):
        """The subtlest of the three attribution bugs, and the only one where every
        match is CORRECT. One r/stocks post — "Need help consolidating my stock list" —
        named 18 of the 150 screened tickers, and all 18 inherited its +0.50, a score
        built from the word "growth" appearing twice in a request for advice. There is
        no wrong match here to find; there is a right match carrying an attribution it
        cannot support."""
        rows = [{"ticker": t, "name": t + " Inc."} for t in
                ("AMD", "AMZN", "AAPL", "COST", "CSCO", "DELL", "AVGO")]
        listing = {"title": "Need help consolidating my stock list",
                   "body": "I hold AMD AMZN AAPL COST CSCO DELL AVGO and want growth",
                   "url": "", "feed": "r/stocks"}
        stats = lab.attach_sentiment(rows, [listing], "reddit")
        self.assertEqual(stats["broadcast_dropped"], 1)
        self.assertEqual(stats["widest_document"], 7)
        for row in rows:
            self.assertEqual(row["reddit_coverage"], 0, row["ticker"])
            self.assertIsNone(row["reddit_tone"], row["ticker"])

    def test_a_post_comparing_a_few_names_is_still_attributed(self):
        """Non-vacuity — a rule that dropped everything would also pass the test above,
        and would silently empty the column."""
        rows = [{"ticker": t, "name": t + " Inc."} for t in ("AMD", "NVDA")]
        stats = lab.attach_sentiment(
            rows, [{"title": "AMD beats while NVDA guidance disappoints", "body": "",
                    "url": "", "feed": "r/stocks"}], "reddit")
        self.assertEqual(stats["broadcast_dropped"], 0)
        for row in rows:
            self.assertEqual(row["reddit_coverage"], 1)
            self.assertIsNotNone(row["reddit_tone"])

    def test_breadth_is_measured_against_the_whole_universe_not_one_row(self):
        """A document's breadth cannot be judged while walking a single row, so the
        implementation needs two passes. If it ever collapses back to one, a wide post
        is attributed to whichever ticker is examined first."""
        rows = [{"ticker": t, "name": t + " Inc."} for t in
                ("AMD", "AMZN", "AAPL", "COST", "CSCO", "DELL")]
        wide = {"title": "AMD AMZN AAPL COST CSCO DELL all rallied", "body": "",
                "url": "", "feed": "r/stocks"}
        lab.attach_sentiment(rows, [wide], "reddit")
        self.assertEqual([r["reddit_coverage"] for r in rows], [0] * 6)

    def test_covered_but_untoned_is_distinct_from_uncovered(self):
        """Three states, not two: no document, a document with no tone word, and a
        scored document."""
        rows = [{"ticker": "AAPL", "name": "Apple Inc."}]
        lab.attach_sentiment(rows, [{"title": "Apple schedules its annual meeting",
                                     "body": "", "url": "", "feed": "t"}], "bloomberg")
        self.assertEqual(rows[0]["bloomberg_coverage"], 1)
        self.assertEqual(rows[0]["bloomberg_toned"], 0)
        self.assertIsNone(rows[0]["bloomberg_tone"])


class PreFiledSentimentIsAttributedByTheFeedNotTheText(unittest.TestCase):
    """Yahoo's feed is keyed by ticker, which changes what the attribution IS — and the
    risk that comes with it.

    The gain is real: `?s=UAMY` answers 200 with 20 items for a name no Bloomberg
    headline and no r/stocks post has ever mentioned, so coverage stops being a lottery
    on what the wires wrote that hour. The overclaim to guard against is treating "filed
    under" as "about": Yahoo files sector and market round-ups under the individual
    symbols they touch, so a coal miner's feed carries "Sector Update: Energy Stocks
    Mixed" and NVDA's carries a nuclear-stocks round-up. That is the SAME defect as the
    Attorney-General/General-Motors match wearing a different hat, and the only part of
    it the documents themselves can settle is cross-filing.
    """

    def _docs(self, *pairs):
        return [{"source": "yahoo", "feed": "yahoo/" + tk, "ticker": tk,
                 "title": title, "body": body, "url": url, "published": ""}
                for tk, title, body, url in pairs]

    def test_the_feed_key_attributes_the_document_no_text_match_needed(self):
        """The whole point: a headline that never spells the company out is still that
        company's news, because the source filed it there."""
        rows = [{"ticker": "UAMY", "name": "United States Antimony Corporation"}]
        lab.attach_prefiled_sentiment(rows, self._docs(
            ("UAMY", "Shares surge after a record quarter", "Output beat plan.",
             "https://y/1")), "yahoo")
        self.assertEqual(rows[0]["yahoo_coverage"], 1)
        self.assertGreater(rows[0]["yahoo_tone"], 0)
        self.assertEqual(rows[0]["yahoo_docs"][0]["rule"], lab.FILED)

    def test_a_document_whose_text_also_names_the_company_says_so(self):
        """Corroboration is recorded, not required. It is the one thing that separates a
        story about the company from a round-up filed under it, and the reader chasing a
        surprising cell needs to see which one they are looking at."""
        rows = [{"ticker": "AREC", "name": "American Resources Corporation"}]
        lab.attach_prefiled_sentiment(rows, self._docs(
            ("AREC", "American Resources Corp approves special dividend",
             "The board approved a special cash dividend.", "https://y/2")), "yahoo")
        self.assertEqual(rows[0]["yahoo_docs"][0]["rule"], lab.FILED_NAMED)

    def test_a_round_up_cross_filed_under_many_tickers_is_dropped(self):
        """One item, one URL, filed under five names: an inventory of a sector, not
        commentary on any company in it."""
        wide = [("T{}".format(i), "Sector Update: Energy Stocks Mixed Late Afternoon",
                 "The NYSE Energy Sector Index slipped.", "https://y/sector")
                for i in range(5)]
        rows = [{"ticker": "T{}".format(i), "name": "Company {}".format(i)}
                for i in range(5)]
        stats = lab.attach_prefiled_sentiment(rows, self._docs(*wide), "yahoo")
        self.assertEqual(stats["broadcast_dropped"], 1)
        self.assertEqual(stats["widest_document"], 5)
        for row in rows:
            self.assertEqual(row["yahoo_coverage"], 0, row["ticker"])
            self.assertIsNone(row["yahoo_tone"], row["ticker"])

    def test_a_story_filed_under_two_names_is_still_attributed(self):
        """Non-vacuity: a rule that dropped every shared item would empty the column and
        still pass the test above. A merger legitimately lands under both sides."""
        pair = [("AAA", "AAA agrees to buy BBB in a record deal", "", "https://y/deal"),
                ("BBB", "AAA agrees to buy BBB in a record deal", "", "https://y/deal")]
        rows = [{"ticker": "AAA", "name": "Alpha Corp"},
                {"ticker": "BBB", "name": "Beta Inc"}]
        stats = lab.attach_prefiled_sentiment(rows, self._docs(*pair), "yahoo")
        self.assertEqual(stats["broadcast_dropped"], 0)
        for row in rows:
            self.assertEqual(row["yahoo_coverage"], 1)
            self.assertIsNotNone(row["yahoo_tone"])

    def test_a_round_up_filed_under_one_ticker_is_kept_and_the_limit_is_stated(self):
        """The residual, asserted rather than described. Cross-filing is the only
        round-up signal the feed carries; an item filed under a single screened name is
        indistinguishable from that company's news and IS scored. The provider line and
        the page say so — this test exists so the claim cannot quietly become "solved"."""
        rows = [{"ticker": "AREC", "name": "American Resources Corporation"}]
        lab.attach_prefiled_sentiment(rows, self._docs(
            ("AREC", "Sector Update: Energy Stocks Mixed Late Afternoon",
             "The NYSE Energy Sector Index slipped.", "https://y/sector")), "yahoo")
        self.assertEqual(rows[0]["yahoo_coverage"], 1)
        self.assertEqual(rows[0]["yahoo_docs"][0]["rule"], lab.FILED,
                         "an uncorroborated filing must not be labelled as named")

    def test_uncovered_ticker_is_none_never_zero(self):
        rows = [{"ticker": "AAA", "name": "Alpha Corp"},
                {"ticker": "ZZZZ", "name": "Nonexistent Holdings"}]
        lab.attach_prefiled_sentiment(rows, self._docs(
            ("AAA", "Alpha Corp profit beats", "", "https://y/3")), "yahoo")
        self.assertEqual(rows[1]["yahoo_coverage"], 0)
        self.assertIsNone(rows[1]["yahoo_tone"])
        self.assertNotEqual(rows[1]["yahoo_tone"], 0.0)

    def test_covered_but_untoned_is_its_own_state(self):
        rows = [{"ticker": "AAA", "name": "Alpha Corp"}]
        lab.attach_prefiled_sentiment(rows, self._docs(
            ("AAA", "Alpha Corp schedules its annual meeting", "", "https://y/4")),
            "yahoo")
        self.assertEqual(rows[0]["yahoo_coverage"], 1)
        self.assertEqual(rows[0]["yahoo_toned"], 0)
        self.assertIsNone(rows[0]["yahoo_tone"])

    def test_a_genuine_zero_survives_with_its_coverage(self):
        """The other half of the absence rule, and the half that is easy to lose: terms
        matched and cancelled is a READING. It must arrive as 0.0 with coverage, never be
        rounded off into the same cell as "nobody said anything"."""
        rows = [{"ticker": "AAA", "name": "Alpha Corp"}]
        lab.attach_prefiled_sentiment(rows, self._docs(
            ("AAA", "Alpha Corp shares higher", "", "https://y/up"),
            ("AAA", "Alpha Corp shares lower", "", "https://y/down")), "yahoo")
        self.assertEqual(rows[0]["yahoo_coverage"], 2)
        self.assertEqual(rows[0]["yahoo_toned"], 2)
        self.assertEqual(rows[0]["yahoo_tone"], 0.0)
        self.assertIsNotNone(rows[0]["yahoo_tone"])

    def test_the_text_rules_can_never_delete_a_filing(self):
        """The reason this is a separate function rather than a flag on the matched
        path. Running the name rules as a GATE could only remove attributions the source
        itself made — and those rules are where every past attribution defect came
        from."""
        rows = [{"ticker": "GM", "name": "General Motors Company"}]
        lab.attach_prefiled_sentiment(rows, self._docs(
            ("GM", "Quarterly deliveries rose", "", "https://y/5")), "yahoo")
        self.assertEqual(rows[0]["yahoo_coverage"], 1)

    def test_identity_falls_back_to_the_title_when_a_feed_omits_the_link(self):
        """Without a fallback, identity fragments and every round-up reads as unique —
        the breadth rule would silently stop firing."""
        wide = [("T{}".format(i), "Market Update: Stocks Mixed", "", "")
                for i in range(5)]
        rows = [{"ticker": "T{}".format(i), "name": "Company {}".format(i)}
                for i in range(5)]
        stats = lab.attach_prefiled_sentiment(rows, self._docs(*wide), "yahoo")
        self.assertEqual(stats["broadcast_dropped"], 1)


YAHOO_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<rss version="2.0"><channel>
<description>Latest Financial News for AAA</description>
<item><description>The company beat estimates and raised guidance.</description>
<guid isPermaLink="false">abc</guid>
<link>https://finance.yahoo.com/news/a.html</link>
<pubDate>Fri, 24 Jul 2026 19:59:51 +0000</pubDate>
<title>Alpha Corp profit surges on strong demand</title></item>
</channel></rss>"""


class YahooFetchReportsItsStateAndNeverReachesTheNetworkInTests(unittest.TestCase):
    """One request per ticker is the cost of the coverage, so the pacing, the failure
    accounting and the give-up rule are all part of the contract."""

    def test_it_fetches_one_feed_per_ticker_and_tags_each_document(self):
        seen = []

        def get(url, *args, **kwargs):
            seen.append(url)
            return FakeResponse(200, YAHOO_XML)

        docs, provider = lab.fetch_yahoo(("AAA", "BBB"), get=get, sleep=lambda _s: None)
        self.assertEqual(len(seen), 2)
        self.assertIn("s=AAA", seen[0])
        self.assertEqual(provider.state, lab.LIVE)
        self.assertEqual([d["ticker"] for d in docs], ["AAA", "BBB"])
        self.assertEqual(docs[0]["source"], "yahoo")
        self.assertEqual(docs[0]["feed"], "yahoo/AAA")

    def test_the_getter_is_the_only_way_out_and_nothing_else_is_called(self):
        """The injection seam, asserted directly: with a getter supplied, a `requests`
        import inside the fetcher would be the bug this catches."""
        calls = []
        lab.fetch_yahoo(("AAA",), get=lambda *a, **k: calls.append(a) or
                        FakeResponse(200, YAHOO_XML), sleep=lambda _s: None)
        self.assertEqual(len(calls), 1)

    def test_pacing_is_injectable_all_the_way_down(self):
        """Written after the Reddit path taught it: a seam that stops one level short of
        the bottom is not a seam. With `get` faked and `sleep` real, a 123-ticker pull
        would sit in the suite genuinely waiting half a minute."""
        waits = []
        lab.fetch_yahoo(("AAA", "BBB", "CCC"),
                        get=lambda *a, **k: FakeResponse(200, YAHOO_XML),
                        sleep=waits.append)
        self.assertEqual(len(waits), 2, "no pause before the first request, one between")
        for wait in waits:
            self.assertEqual(wait, lab.YAHOO_PAUSE_SECONDS)

    def test_a_404_degrades_the_provider_and_names_the_ticker(self):
        """A ticker whose feed 404s has NO reading. It must not arrive as a tone of 0.00,
        and the run must not be reported as clean."""
        def get(url, *args, **kwargs):
            return FakeResponse(404 if "s=BBB" in url else 200, YAHOO_XML)

        docs, provider = lab.fetch_yahoo(("AAA", "BBB"), get=get, sleep=lambda _s: None)
        self.assertEqual(provider.state, lab.DEGRADED)
        self.assertIn("BBB HTTP 404", provider.detail)
        self.assertEqual([d["ticker"] for d in docs], ["AAA"])

    def test_a_total_429_is_unavailable_and_says_it_is_missing_data(self):
        _docs, provider = lab.fetch_yahoo(
            ("AAA", "BBB", "CCC"), get=lambda *a, **k: FakeResponse(429, ""),
            sleep=lambda _s: None)
        self.assertEqual(provider.state, lab.UNAVAILABLE)
        self.assertIn("429", provider.detail)
        self.assertIn("not neutral sentiment", provider.detail)
        self.assertEqual(provider.documents, 0)

    def test_a_dead_endpoint_is_reported_in_seconds_not_walked_for_two_minutes(self):
        """123 sequential requests to prove a host is down is a wasted CI run, and the
        tickers never tried must be reported as NOT ATTEMPTED rather than folded in with
        the ones that genuinely answered nothing."""
        tickers = tuple("T{}".format(i) for i in range(40))
        attempts = []

        def get(url, *args, **kwargs):
            attempts.append(url)
            return FakeResponse(503, "")

        _docs, provider = lab.fetch_yahoo(tickers, get=get, sleep=lambda _s: None,
                                          give_up_after=5)
        self.assertEqual(len(attempts), 5)
        self.assertIn("5 of 40", provider.detail)

    def test_partial_failure_still_reports_what_was_not_attempted(self):
        responses = [FakeResponse(200, YAHOO_XML)] + [FakeResponse(500, "")] * 20

        def get(*args, **kwargs):
            return responses.pop(0) if responses else FakeResponse(500, "")

        _docs, provider = lab.fetch_yahoo(
            tuple("T{}".format(i) for i in range(20)), get=get, sleep=lambda _s: None,
            give_up_after=3)
        self.assertEqual(provider.state, lab.DEGRADED)
        self.assertIn("NOT ATTEMPTED", provider.detail)

    def test_the_failure_list_stays_readable_at_universe_scale(self):
        """123 verbatim failures in a panel meant to be read at a glance is a paragraph
        nobody finishes — the count is the fact, the examples are the lead."""
        _docs, provider = lab.fetch_yahoo(
            tuple("T{}".format(i) for i in range(30)),
            get=lambda *a, **k: FakeResponse(200, "<rss><channel></channel></rss>"),
            sleep=lambda _s: None, give_up_after=0)
        self.assertIn("and 24 more", provider.detail)

    def test_the_provider_line_refuses_the_vendor_sentiment_reading(self):
        _docs, provider = lab.fetch_yahoo(
            ("AAA",), get=lambda *a, **k: FakeResponse(200, YAHOO_XML),
            sleep=lambda _s: None)
        self.assertIn("NOT a vendor sentiment score", provider.detail)
        self.assertIn("ROUND-UPS", provider.detail)

    def test_malformed_xml_is_a_reported_failure_not_an_exception(self):
        _docs, provider = lab.fetch_yahoo(
            ("AAA",), get=lambda *a, **k: FakeResponse(200, "<not xml"),
            sleep=lambda _s: None)
        self.assertEqual(provider.state, lab.UNAVAILABLE)
        self.assertIn("parsed 0 items", provider.detail)

    def test_a_raising_getter_is_a_state_not_a_traceback(self):
        def get(*args, **kwargs):
            raise OSError("connection reset")

        _docs, provider = lab.fetch_yahoo(("AAA",), get=get, sleep=lambda _s: None)
        self.assertEqual(provider.state, lab.UNAVAILABLE)
        self.assertIn("OSError", provider.detail)


class GrowthIsNotDoubleCountedOrFakedByABaseEffect(unittest.TestCase):
    """The Aflac regression: what the vendor calls growth mostly is not."""

    AFL = {"earnings_growth": 38.60, "quarterly_earnings_growth": 34.14,
           "revenue_growth": 0.279}
    HEALTHY = {"earnings_growth": 0.30, "quarterly_earnings_growth": 0.28,
               "revenue_growth": 0.22}

    def test_earnings_fields_are_collapsed_before_blending(self):
        """`earningsGrowth` and `earningsQuarterlyGrowth` are near-duplicates. If they
        are averaged as peers with revenue, earnings gets two votes out of three and the
        stable measure is outvoted by the volatile one."""
        value, used, _flag = lab.growth_blend(self.HEALTHY)
        earnings = (0.30 + 0.28) / 2
        self.assertAlmostEqual(value, (earnings + 0.22) / 2, places=9)
        self.assertNotAlmostEqual(value, (0.30 + 0.28 + 0.22) / 3, places=6)
        self.assertEqual(len(used), 3, "all three source fields are still reported")

    def test_earnings_off_a_depressed_base_is_flagged(self):
        _value, _used, flag = lab.growth_blend(self.AFL)
        self.assertEqual(flag, lab.BASE_EFFECT)

    def test_ordinary_growth_is_not_flagged(self):
        _value, _used, flag = lab.growth_blend(self.HEALTHY)
        self.assertIsNone(flag)

    def test_a_flagged_row_ranks_on_revenue_growth(self):
        """Capping alone tied Allstate (3% revenue growth) with Alphabet (24%) at the
        ceiling — still ranking a non-grower as a grower. The trustworthy component
        does the ranking instead."""
        row = dict(self.AFL)
        value, _used, flag = lab.growth_blend(row)
        ranked, basis = lab.growth_for_rank(row, value, flag)
        self.assertAlmostEqual(ranked, 0.279, places=9)
        self.assertIn("revenue", basis)
        self.assertLess(ranked, value, "the raw blend must not be what ranked it")

    def test_extreme_growth_with_no_trustworthy_component_is_capped(self):
        """Capital One reported 1111% REVENUE growth (an acquisition). There is no
        second component to fall back on, so the cap is all that is left — and the flag
        says which of the two treatments the row received."""
        row = {"revenue_growth": 11.11}
        value, _used, flag = lab.growth_blend(row)
        ranked, basis = lab.growth_for_rank(row, value, flag)
        self.assertEqual(flag, lab.CAPPED)
        self.assertEqual(ranked, lab.GROWTH_RANK_CAP)
        self.assertIn("cap", basis)

    def test_the_flag_is_a_ratio_test_not_a_revenue_floor(self):
        """An absolute revenue floor was the first rule and it missed the row that
        motivated the flag: Aflac's 27.9% revenue growth cleared every sane floor while
        earnings grew 3860%. Disproportion is the signal, at any revenue level."""
        healthy_hypergrower = {"earnings_growth": 1.2, "quarterly_earnings_growth": 1.2,
                               "revenue_growth": 0.7}
        _v, _u, flag = lab.growth_blend(healthy_hypergrower)
        self.assertIsNone(flag, "earnings moving with revenue is real growth")

    def test_aflac_itself_is_flagged_by_the_ratio_rule(self):
        """The row that motivated the rule: 3860% earnings on 27.9% revenue. Under the
        original absolute-floor rule this came back merely `capped`, which ranked it at
        the 100% ceiling instead of at the business's real 27.9%."""
        _v, _u, flag = lab.growth_blend(self.AFL)
        self.assertEqual(flag, lab.BASE_EFFECT)

    def test_earnings_spike_against_falling_revenue_always_flags(self):
        _v, _u, flag = lab.growth_blend({"earnings_growth": 3.0,
                                         "quarterly_earnings_growth": 3.0,
                                         "revenue_growth": -0.1})
        self.assertEqual(flag, lab.BASE_EFFECT)

    def test_printed_figure_stays_raw(self):
        """The flag exists so the reader can see the real number and distrust it. A
        silently winsorised figure would teach them something false instead."""
        value, _used, _flag = lab.growth_blend(self.AFL)
        self.assertGreater(value, 10.0)

    def test_missing_growth_everywhere_is_none_not_zero(self):
        value, used, flag = lab.growth_blend({"trailing_pe": 12.0})
        self.assertIsNone(value)
        self.assertEqual(used, [])
        self.assertIsNone(flag)

    def test_partial_vendor_record_still_produces_a_figure(self):
        value, used, _flag = lab.growth_blend({"revenue_growth": 0.18})
        self.assertAlmostEqual(value, 0.18, places=9)
        self.assertEqual(used, ["revenue_growth"])


class ScreenNeverTreatsMissingAsCheap(unittest.TestCase):
    """The most consequential way a value screen can lie is to sort an absent or
    negative P/E to the top of a "cheapest first" list."""

    ROWS = [
        {"ticker": "CHEAP", "name": "Cheap Co", "trailing_pe": 8.0,
         "revenue_growth": 0.30, "earnings_growth": 0.30},
        {"ticker": "RICH", "name": "Rich Co", "trailing_pe": 60.0,
         "revenue_growth": 0.40, "earnings_growth": 0.40},
        {"ticker": "LOSS", "name": "Lossmaker", "trailing_pe": -12.0,
         "revenue_growth": 0.50, "earnings_growth": 0.50},
        {"ticker": "BLANK", "name": "No Data Co", "trailing_pe": None,
         "revenue_growth": 0.90, "earnings_growth": 0.90},
        {"ticker": "NOGROW", "name": "No Growth Data", "trailing_pe": 5.0},
    ]

    def rows(self):
        return [dict(r) for r in self.ROWS]

    def test_negative_pe_is_excluded_with_a_stated_reason(self):
        ranked, excluded = lab.screen(self.rows())
        self.assertNotIn("LOSS", [r["ticker"] for r in ranked])
        reason = dict((r["ticker"], why) for r, why in excluded)["LOSS"]
        self.assertEqual(reason, lab.NEGATIVE_PE)

    def test_missing_pe_is_excluded_not_defaulted(self):
        ranked, excluded = lab.screen(self.rows())
        self.assertNotIn("BLANK", [r["ticker"] for r in ranked])
        self.assertEqual(dict((r["ticker"], w) for r, w in excluded)["BLANK"], lab.NO_PE)

    def test_missing_growth_is_excluded_with_its_own_reason(self):
        _ranked, excluded = lab.screen(self.rows())
        self.assertEqual(dict((r["ticker"], w) for r, w in excluded)["NOGROW"],
                         lab.NO_GROWTH)

    def test_cheap_outranks_rich_when_growth_is_comparable(self):
        ranked, _excluded = lab.screen(self.rows())
        self.assertEqual(ranked[0]["ticker"], "CHEAP")

    def test_exclusions_are_returned_not_discarded(self):
        """A screener showing survivors with no account of the rejects invites the
        reader to assume they failed the stated filters."""
        ranked, excluded = lab.screen(self.rows())
        self.assertEqual(len(ranked) + len(excluded), len(self.ROWS))
        self.assertTrue(lab.exclusion_summary(excluded))

    def test_filters_report_the_threshold_that_rejected_the_row(self):
        _ranked, excluded = lab.screen(self.rows(), max_pe=10.0)
        reasons = dict((r["ticker"], why) for r, why in excluded)
        self.assertIn("60.0", reasons["RICH"])

    def test_sentiment_is_excluded_from_the_rank_by_default(self):
        """Folding tone into a value/growth composite by default would change what the
        screen means while still calling itself low-P/E-high-growth."""
        rows = self.rows()
        for row in rows:
            row["bloomberg_tone"] = -0.9 if row["ticker"] == "CHEAP" else 0.9
            row["bloomberg_coverage"] = 3
        ranked, _excluded = lab.screen(rows)
        self.assertEqual(ranked[0]["ticker"], "CHEAP")
        for row in ranked:
            self.assertEqual(row["blended_score"], row["screen_score"])

    def test_sentiment_weight_changes_the_order_when_asked_for(self):
        rows = self.rows()
        for row in rows:
            row["bloomberg_tone"] = -0.9 if row["ticker"] == "CHEAP" else 0.9
            row["bloomberg_coverage"] = 3
        ranked, _excluded = lab.screen(rows, sentiment_weight=0.5)
        self.assertNotEqual(ranked[0]["ticker"], "CHEAP")

    def test_uncovered_rows_are_neither_rewarded_nor_punished_by_a_blend(self):
        """A ticker with no tone must keep its value+growth score, not be scored as
        neutral — neutral is a reading it never received."""
        rows = self.rows()
        for row in rows:
            row["bloomberg_tone"] = None
            row["bloomberg_coverage"] = 0
        ranked, _excluded = lab.screen(rows, sentiment_weight=0.5)
        for row in ranked:
            self.assertEqual(row["blended_score"], row["screen_score"])
            self.assertIn("no bloomberg coverage", row["blend_note"])

    def test_percentile_ranks_are_immune_to_an_outlier_magnitude(self):
        ranks = lab._percentile_ranks([1.0, 2.0, 3.0, 900.0])
        self.assertEqual(ranks[1.0], 0.0)
        self.assertEqual(ranks[900.0], 1.0)
        self.assertAlmostEqual(ranks[2.0], 1 / 3, places=6)

    def test_percentile_ranks_average_ties(self):
        ranks = lab._percentile_ranks([5.0, 5.0, 9.0])
        self.assertAlmostEqual(ranks[5.0], 0.25, places=6)


class ProviderStateIsReportedNotThrown(unittest.TestCase):
    """An outage is a state the page renders, never a traceback and never a zero."""

    def test_reddit_without_credentials_falls_back_to_public_rss(self):
        """The correction that mattered most. The JSON API's anonymous 403 was read as
        "Reddit is closed without credentials" and the column shipped dark for a day —
        but the Atom feeds for the same subreddits answer 200 to the same anonymous
        request. An inference from one endpoint had been generalised to a whole site."""
        docs, provider = lab.fetch_reddit(
            get=lambda *a, **k: FakeResponse(200, REDDIT_ATOM), env={},
            sleep=lambda _s: None)
        self.assertEqual(provider.state, lab.LIVE)
        self.assertIn("RSS", provider.label)
        self.assertEqual(len(docs), len(lab.REDDIT_SUBS))
        self.assertEqual(docs[0]["source"], "reddit")

    def test_the_label_says_which_path_produced_the_data(self):
        """OAuth and RSS do not have the same coverage — ~25 newest posts and no scores
        on one side. A reader comparing two snapshots has to be able to tell."""
        _docs, rss = lab.fetch_reddit(
            get=lambda *a, **k: FakeResponse(200, REDDIT_ATOM), env={},
            sleep=lambda _s: None)
        self.assertIn("RSS", rss.label)
        self.assertNotIn("OAuth", rss.label)

    def test_pacing_is_read_from_reddits_own_header_not_guessed(self):
        """A flat 3-second guess got 1-2 of 4 subreddits; the observed reset runs 7-58s,
        so the guess was under it most of the time. Reddit states the answer on every
        response — `x-ratelimit-reset` — and nothing was reading it. Pacing on the
        header gets 4 of 4."""
        waits = []
        responses = [FakeResponse(200, REDDIT_ATOM, headers={"x-ratelimit-reset": "44"})
                     for _ in lab.REDDIT_SUBS]
        docs, failed = lab.fetch_reddit_rss(
            lab.REDDIT_SUBS, get=lambda *a, **k: responses.pop(0),
            sleep=waits.append)
        self.assertEqual(failed, [])
        self.assertEqual(len(docs), len(lab.REDDIT_SUBS))
        self.assertTrue(waits, "no pause was taken between requests")
        for wait in waits:
            self.assertAlmostEqual(wait, 44 + lab.RSS_RESET_MARGIN, places=6)

    def test_retry_after_wins_over_the_reset_header(self):
        pause = lab._rate_limit_pause(
            FakeResponse(429, "", headers={"Retry-After": "20",
                                           "x-ratelimit-reset": "3"}))
        self.assertAlmostEqual(pause, 20 + lab.RSS_RESET_MARGIN, places=6)

    def test_a_bogus_header_cannot_park_an_unattended_refresh(self):
        """This runs on a timer with no one watching; an hour-long sleep from a
        malformed value would look identical to a hung job."""
        self.assertEqual(
            lab._rate_limit_pause(FakeResponse(429, "",
                                               headers={"Retry-After": "99999"})),
            lab.RSS_MAX_PAUSE)
        self.assertEqual(
            lab._rate_limit_pause(FakeResponse(429, "",
                                               headers={"Retry-After": "banana"})),
            lab.RSS_PAUSE_SECONDS)

    def test_no_pause_is_taken_before_the_very_first_request(self):
        waits = []
        lab.fetch_reddit_rss(("stocks",),
                             get=lambda *a, **k: FakeResponse(200, REDDIT_ATOM),
                             sleep=waits.append)
        self.assertEqual(waits, [])

    def test_rate_limited_rss_is_retried_then_reported_not_silently_empty(self):
        codes = [429, 429, 429]

        def get(*args, **kwargs):
            return FakeResponse(codes.pop(0) if codes else 200,
                                "" if codes else REDDIT_ATOM)

        docs, failed = lab.fetch_reddit_rss(("stocks",), get=get,
                                            sleep=lambda _s: None, attempts=3)
        self.assertEqual(docs, [])
        self.assertEqual(len(failed), 1)
        self.assertIn("429", failed[0])
        self.assertIn("3 attempts", failed[0])

    def test_a_partial_rss_fetch_is_degraded_and_names_the_throttled_subs(self):
        responses = [FakeResponse(200, REDDIT_ATOM)] + [FakeResponse(429, "")] * 9

        def get(*args, **kwargs):
            return responses.pop(0) if responses else FakeResponse(429, "")

        docs, provider = lab.fetch_reddit(get=get, env={}, sleep=lambda _s: None)
        self.assertEqual(provider.state, lab.DEGRADED)
        self.assertIn("429", provider.detail)
        self.assertTrue(docs)

    def test_total_rss_failure_is_unavailable_and_says_it_is_often_temporary(self):
        _docs, provider = lab.fetch_reddit(
            get=lambda *a, **k: FakeResponse(429, ""), env={}, sleep=lambda _s: None)
        self.assertEqual(provider.state, lab.UNAVAILABLE)
        self.assertIn("rate-limit", provider.detail)
        self.assertIn("not neutral sentiment", provider.detail)

    def test_atom_entries_are_parsed_with_html_stripped_from_the_body(self):
        docs = lab.parse_atom(REDDIT_ATOM, "stocks")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["title"], "NVDA earnings beat, guidance raised")
        self.assertNotIn("<", docs[0]["body"])
        self.assertIn("blowout", docs[0]["body"])
        self.assertEqual(docs[0]["feed"], "r/stocks")

    def test_malformed_atom_yields_nothing_rather_than_raising(self):
        self.assertEqual(lab.parse_atom("<not xml", "stocks"), [])

    def test_credentials_still_take_the_oauth_path(self):
        """The fallback must not shadow the better source when it is available."""
        seen = []

        def get(url, *args, **kwargs):
            seen.append(url)
            if "access_token" in url:
                return FakeResponse(200, payload={"access_token": "t"})
            return FakeResponse(200, payload={"data": {"children": [
                {"data": {"title": "TSLA up", "selftext": "", "permalink": "/p",
                          "created_utc": 0, "score": 5}}]}})

        _docs, provider = lab.fetch_reddit(
            get=get, env={"REDDIT_CLIENT_ID": "a", "REDDIT_CLIENT_SECRET": "b"})
        self.assertIn("OAuth", provider.label)
        self.assertTrue(any("oauth.reddit.com" in u for u in seen))

    def test_reddit_absence_names_an_actionable_remedy(self):
        _docs, provider = lab.fetch_reddit(
            get=lambda *a, **k: FakeResponse(429, ""), env={}, sleep=lambda _s: None)
        self.assertIn("prefs/apps", provider.remedy)
        self.assertIn("REDDIT_CLIENT_ID", provider.remedy + provider.detail)

    def test_credentials_are_read_from_dotenv_not_just_the_process_env(self):
        """The remedy says "put them in .env". Nothing in a research CLI run loads
        that file — the live stack calls `dotenv.load_dotenv()` at import and no
        research tool does — so without this the remedy is advice that does not work,
        and the reader is told to do what they have already done."""
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, ".env")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# a comment\n\nREDDIT_CLIENT_ID=abc123\n"
                         "export REDDIT_CLIENT_SECRET='sh h'\nMALFORMED\n")
        env = lab.load_dotenv_into({}, path)
        self.assertEqual(env["REDDIT_CLIENT_ID"], "abc123")
        self.assertEqual(env["REDDIT_CLIENT_SECRET"], "sh h")
        self.assertNotIn("MALFORMED", env)

    def test_a_real_environment_variable_beats_the_file(self):
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, ".env")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("REDDIT_CLIENT_ID=from_file\n")
        env = lab.load_dotenv_into({"REDDIT_CLIENT_ID": "from_shell"}, path)
        self.assertEqual(env["REDDIT_CLIENT_ID"], "from_shell")

    def test_a_missing_dotenv_is_not_an_error(self):
        self.assertEqual(lab.load_dotenv_into({}, "/nonexistent/.env"), {})

    def test_an_explicit_env_mapping_is_not_topped_up_from_disk(self):
        """Tests pass `{}` to assert no request is made without credentials; reading
        the developer's real .env underneath that would make the suite pass or fail
        depending on whose machine it runs on."""
        self.assertEqual(lab.reddit_credentials(env={}), (None, None))

    def test_reddit_absence_says_it_is_missing_data_not_neutrality(self):
        _docs, provider = lab.fetch_reddit(
            get=lambda *a, **k: FakeResponse(429, ""), env={}, sleep=lambda _s: None)
        self.assertIn("not neutral", provider.detail)

    def test_rejected_credentials_are_distinguished_from_absent_ones(self):
        """Two different failures with two different fixes; one message for both would
        send the reader to the wrong one."""
        _docs, provider = lab.fetch_reddit(
            get=lambda *a, **k: FakeResponse(401),
            env={"REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "y"})
        self.assertEqual(provider.state, lab.UNAVAILABLE)
        self.assertIn("401", provider.detail)
        self.assertIn("not accepted", provider.detail)

    def test_bloomberg_parses_items_and_reports_live(self):
        docs, provider = lab.fetch_bloomberg(
            get=lambda *a, **k: FakeResponse(200, BLOOMBERG_XML),
            feeds=[("markets", "u1"), ("technology", "u2")])
        self.assertEqual(len(docs), 4)
        self.assertEqual(provider.state, lab.LIVE)

    def test_bloomberg_states_it_is_not_the_terminal_analytic(self):
        """The page must not let "Bloomberg sentiment" be read as the licensed NEWS
        sentiment field, which needs a Terminal and blpapi."""
        _docs, provider = lab.fetch_bloomberg(
            get=lambda *a, **k: FakeResponse(200, BLOOMBERG_XML), feeds=[("m", "u")])
        self.assertIn("NOT the Terminal", provider.detail)

    def test_a_partly_failing_fetch_is_degraded_and_names_the_failure(self):
        responses = [FakeResponse(200, BLOOMBERG_XML), FakeResponse(503, "")]
        docs, provider = lab.fetch_bloomberg(
            get=lambda *a, **k: responses.pop(0), feeds=[("ok", "u1"), ("bad", "u2")])
        self.assertEqual(provider.state, lab.DEGRADED)
        self.assertIn("503", provider.detail)
        self.assertEqual(len(docs), 2)

    def test_a_total_outage_is_unavailable_not_an_exception(self):
        def boom(*args, **kwargs):
            raise OSError("no route to host")

        docs, provider = lab.fetch_bloomberg(get=boom, feeds=[("m", "u")])
        self.assertEqual(docs, [])
        self.assertEqual(provider.state, lab.UNAVAILABLE)
        self.assertIn("OSError", provider.detail)

    def test_malformed_xml_yields_no_items_rather_than_raising(self):
        self.assertEqual(lab.parse_rss("<not xml", "m"), [])


class SnapshotIsTheContractWithTheServer(unittest.TestCase):
    def test_missing_snapshot_returns_none_rather_than_raising(self):
        """The page must be able to render an absence panel; a 500 tells the reader
        nothing about what to do."""
        self.assertIsNone(lab.load_snapshot("/nonexistent/screener_snapshot.json"))

    def test_corrupt_snapshot_returns_none(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write("{ this is not json")
            path = handle.name
        try:
            self.assertIsNone(lab.load_snapshot(path))
        finally:
            os.unlink(path)

    def test_snapshot_without_rows_is_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"version": 1}, handle)
            path = handle.name
        try:
            self.assertIsNone(lab.load_snapshot(path))
        finally:
            os.unlink(path)

    def test_write_then_load_round_trips_and_carries_provider_state(self):
        snapshot = {"version": lab.SNAPSHOT_VERSION, "built_at": lab._stamp(),
                    "screened": 1, "rows": [{"ticker": "AAA"}],
                    "providers": [lab.Provider("reddit", "Reddit", lab.UNAVAILABLE,
                                               "off", "set creds").as_dict()]}
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "snap.json")
        lab.write_snapshot(snapshot, path)
        loaded = lab.load_snapshot(path)
        self.assertEqual(loaded["rows"][0]["ticker"], "AAA")
        providers = lab.providers_from_snapshot(loaded)
        self.assertEqual(providers[0].state, lab.UNAVAILABLE)
        self.assertFalse(providers[0].is_live)

    def test_age_is_reported_for_a_fresh_snapshot(self):
        delta, human = lab.snapshot_age({"built_at": lab._stamp()})
        self.assertIsNotNone(delta)
        self.assertIn("min old", human)

    def test_unparseable_timestamp_is_unknown_not_zero(self):
        delta, human = lab.snapshot_age({"built_at": "whenever"})
        self.assertIsNone(delta)
        self.assertIn("unknown", human)

    def test_build_snapshot_runs_offline_and_records_every_provider(self):
        """End to end with every source injected — the shape the server consumes."""

        class FakeTicker:
            def __init__(self, symbol):
                self.symbol = symbol

            @property
            def info(self):
                return {"trailingPE": 11.0, "forwardPE": 10.0, "revenueGrowth": 0.2,
                        "earningsGrowth": 0.25, "shortName": "Pfizer, Inc.",
                        "sector": "Healthcare", "marketCap": 1e11}

        snapshot = lab.build_snapshot(
            universe=[("PFE", "Pfizer, Inc.", "Healthcare")],
            get=lambda *a, **k: FakeResponse(200, BLOOMBERG_XML), env={},
            ticker_factory=FakeTicker, sleep=lambda _s: None)
        self.assertEqual(snapshot["screened"], 1)
        keys = {p["key"] for p in snapshot["providers"]}
        # Derived from the registry rather than written out — this pin went stale the day a
        # fourth tone source landed in TONE_SOURCES and nobody re-ran this suite. The claim
        # was never "these five names"; it was "every source is recorded, fetched or not".
        self.assertEqual(keys, {"universe", "fundamentals"} | set(lab.TONE_SOURCES))
        states = {p["key"]: p["state"] for p in snapshot["providers"]}
        self.assertEqual(states["reddit"], lab.UNAVAILABLE)
        row = snapshot["rows"][0]
        # The fake serves the same two-item feed to each of the real feed URLs, so the
        # Pfizer item arrives once per feed.
        self.assertEqual(row["bloomberg_coverage"], len(lab.BLOOMBERG_FEEDS))
        self.assertGreater(row["bloomberg_tone"], 0)
        self.assertIsNone(row["reddit_tone"])
        self.assertEqual(row["reddit_coverage"], 0)


class FundamentalsNeverInventANumber(unittest.TestCase):
    def test_absent_vendor_fields_stay_none(self):
        class Bare:
            def __init__(self, symbol):
                pass

            info = {"shortName": "Thin Co"}

        rows, provider = lab.fetch_fundamentals([("TC", "Thin Co", "Tech")],
                                                ticker_factory=Bare)
        self.assertIsNone(rows[0]["trailing_pe"])
        self.assertEqual(provider.state, lab.UNAVAILABLE)
        self.assertIn("unreachable", provider.detail)

    def test_nan_and_bool_are_not_numbers(self):
        self.assertIsNone(lab._as_float(float("nan")))
        self.assertIsNone(lab._as_float(True))
        self.assertIsNone(lab._as_float("n/a"))
        self.assertEqual(lab._as_float("12.5"), 12.5)

    def test_a_raising_vendor_call_does_not_abort_the_run(self):
        class Angry:
            def __init__(self, symbol):
                self.symbol = symbol

            @property
            def info(self):
                if self.symbol == "BAD":
                    raise RuntimeError("vendor blew up")
                return {"trailingPE": 9.0, "revenueGrowth": 0.1}

        rows, provider = lab.fetch_fundamentals(
            [("BAD", "Bad Co", "Tech"), ("OK", "Ok Co", "Tech")], ticker_factory=Angry)
        self.assertEqual(len(rows), 2)
        self.assertIsNone(rows[0]["trailing_pe"])
        self.assertEqual(rows[1]["trailing_pe"], 9.0)
        self.assertEqual(provider.state, lab.DEGRADED)


class TheLabTouchesNothingItShouldNot(unittest.TestCase):
    """`live/**`, `config.py` and the broker are out of bounds for research tooling."""

    def test_the_module_does_not_import_the_live_stack(self):
        """Checked over the IMPORT GRAPH, not the source text. Grepping caught the
        module's own docstring promising it never reads `live/state.db` — a guard that
        fires on a file SAYING it is safe is worthless, and would push the next author
        to delete the sentence rather than keep the property."""
        import ast
        with open(os.path.join(TOOLS, "screener_lab.py"), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for forbidden in ("live", "ib_insync", "config", "config_modules", "sqlite3"):
            self.assertNotIn(forbidden, imported)

    def test_no_test_in_this_file_can_reach_the_network(self):
        """Written after one did. `test_reddit_absence_says_it_is_missing_data...`
        called `fetch_reddit(env={})` with no fetcher injected, and once the RSS
        fallback landed that stopped being a no-op: the suite quietly fetched 25 live
        posts and took 104 seconds. A test whose result depends on Reddit's rate
        limiter is not a test. Every fetching call must inject `get`."""
        import ast
        with open(__file__, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        fetching = {"fetch_reddit", "fetch_reddit_rss", "fetch_bloomberg", "fetch_yahoo",
                    "fetch_universe", "fetch_fundamentals", "build_snapshot",
                    "build_tone_snapshot"}
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name not in fetching:
                continue
            keywords = {kw.arg for kw in node.keywords}
            # fetch_fundamentals reaches the vendor through `ticker_factory`, not `get`.
            needed = "ticker_factory" if name == "fetch_fundamentals" else "get"
            if needed not in keywords:
                offenders.append("line {}: {}() without {}=".format(
                    node.lineno, name, needed))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_it_writes_only_under_data_cache(self):
        self.assertTrue(lab.SNAPSHOT_PATH.startswith(os.path.join(REPO, "data",
                                                                  "cache")))
        self.assertTrue(lab.UNIVERSE_CACHE.startswith(os.path.join(REPO, "data",
                                                                   "cache")))


class ToneOnlyBuildTests(unittest.TestCase):
    """The tone-only build exists so CI can afford tone at all. Its risk is that a build
    without fundamentals quietly implies it has them."""

    def _universe(self):
        return [("AAA", "Alpha Corp", "Technology"), ("BBB", "Beta Inc", "Energy")]

    def test_it_scores_tone_without_touching_the_vendor_loop(self):
        called = []

        def factory(_ticker):            # would be the yfinance call
            called.append(_ticker)
            raise AssertionError("a tone-only build must not fetch fundamentals")

        snap = lab.build_tone_snapshot(
            self._universe(), get=lambda *a, **k: FakeResponse(200, REDDIT_ATOM),
            env={}, sleep=lambda _s: None)
        self.assertEqual(called, [])
        self.assertEqual(snap["screened"], 2)
        self.assertTrue(snap["tone_only"])

    def test_no_row_carries_an_invented_fundamental(self):
        snap = lab.build_tone_snapshot(
            self._universe(), get=lambda *a, **k: FakeResponse(200, REDDIT_ATOM),
            env={}, sleep=lambda _s: None)
        for row in snap["rows"]:
            self.assertNotIn("trailing_pe", row)
            self.assertIsNone(row.get("bloomberg_tone", None) or None)

    def test_the_missing_fundamentals_source_is_reported_not_omitted(self):
        """A source left out of the list reads as a source that found nothing."""
        snap = lab.build_tone_snapshot(
            self._universe(), get=lambda *a, **k: FakeResponse(200, REDDIT_ATOM),
            env={}, sleep=lambda _s: None)
        by_key = {p["key"]: p for p in snap["providers"]}
        self.assertIn("fundamentals", by_key)
        self.assertEqual(by_key["fundamentals"]["state"], lab.UNAVAILABLE)
        self.assertIn("tone-only", by_key["fundamentals"]["detail"])

    def test_the_snapshot_still_loads_through_the_normal_reader(self):
        import tempfile
        snap = lab.build_tone_snapshot(
            self._universe(), get=lambda *a, **k: FakeResponse(200, REDDIT_ATOM),
            env={}, sleep=lambda _s: None)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "snap.json")
            lab.write_snapshot(snap, path)
            self.assertEqual(lab.load_snapshot(path)["screened"], 2)

    def test_every_tone_source_reaches_the_tone_only_build(self):
        """`refresh --tone-only` is what CI runs, so a source wired into the full build
        and forgotten here would be live on a laptop and absent on the published page —
        where it would read as a source that found nothing."""
        asked = []

        def spy_get(url, *a, **k):
            asked.append(url)
            if "stocktwits" in url:
                return FakeResponse(200, payload={"messages": [
                    {"id": 1, "body": "up", "created_at": "2026-08-14T00:00:00Z",
                     "entities": {"sentiment": {"basic": "Bullish"}}}]})
            return FakeResponse(200, YAHOO_XML)

        snap = lab.build_tone_snapshot(
            self._universe(), get=spy_get, env={}, sleep=lambda _s: None)
        keys = {p["key"] for p in snap["providers"]}
        for source in lab.TONE_SOURCES:
            self.assertIn(source, keys)
            for row in snap["rows"]:
                self.assertIn(source + "_coverage", row, source)
        # BEHAVIOUR, not bookkeeping. A build that calls fetch_stocktwits([]) still records a
        # provider and still writes zeroed row fields, and the assertions above all pass over
        # it — found by mutation. The build must ASK the stream about the universe's own
        # tickers, and the answers must land on the rows.
        for ticker, _n, _s in self._universe():
            self.assertTrue(
                any("stocktwits" in u and ticker in u for u in asked),
                "the tone-only build never asked stocktwits about " + ticker)
        for row in snap["rows"]:
            self.assertEqual(row["stocktwits_coverage"], 1)
            self.assertEqual(row["stocktwits_tone"], 1.0)

    def test_the_yahoo_leg_scores_the_universe_it_was_handed(self):
        """Non-vacuity for the wiring above: the fetcher is called with the build's own
        tickers, not an empty list that would silently produce universal absence."""
        snap = lab.build_tone_snapshot(
            [("AAA", "Alpha Corp", "Technology")],
            get=lambda *a, **k: FakeResponse(200, YAHOO_XML), env={},
            sleep=lambda _s: None)
        row = snap["rows"][0]
        self.assertEqual(row["yahoo_coverage"], 1)
        self.assertGreater(row["yahoo_tone"], 0)


class ALabProviderMustNotSpeakForAPageItDoesNotFeed(unittest.TestCase):
    """A provider line is scoped to the snapshot that produced it, and the combined
    screener is where that stopped being true.

    `build_tone_snapshot` deliberately skips fundamentals and reports the leg as
    UNAVAILABLE — correct on `/sentiment`, where screener_lab IS the fundamentals source.
    Passed through unfiltered, that line rendered "Fundamentals (yfinance) · off" at the
    top of a page carrying 123 rows of live P/E, growth and beta from `stock_screener`,
    which leaves the reader to work out which of the two is lying. The rule that comes
    out of it: a panel names the sources that feed THAT page, with each leg's own state —
    and a genuinely missing leg is still listed, marked off, and given its command,
    because a source that vanishes reads as one that found nothing.

    These run over plain dicts: no disk, no network, no server.
    """

    def setUp(self):
        import research_ui
        self.ui = research_ui
        self.tone_only = {"providers": [
            {"key": "fundamentals", "label": "Fundamentals (yfinance)",
             "state": lab.UNAVAILABLE, "headline": "not fetched in a tone-only build",
             "detail": "tone-only build", "remedy": "x", "documents": 0},
            {"key": "bloomberg", "label": "Bloomberg (public RSS)", "state": lab.LIVE,
             "headline": "120 items", "detail": "", "remedy": "", "documents": 120},
            {"key": "reddit", "label": "Reddit (public RSS)", "state": lab.LIVE,
             "headline": "100 posts", "detail": "", "remedy": "", "documents": 100},
            {"key": "yahoo", "label": "Yahoo Finance (per-ticker RSS)",
             "state": lab.DEGRADED, "headline": "2353 items", "detail": "",
             "remedy": "", "documents": 2353},
        ]}
        self.fund = {"as_of": "2026-08-06T16:50:08Z", "rows": [{"ticker": "AAA"}]}
        self.prices = {"as_of": "2026-08-06T22:56:19Z", "bars": 126,
                       "series": {"AAA": [1.0, 2.0]}}

    def test_the_tone_only_fundamentals_line_never_reaches_the_combined_panel(self):
        """NARROWED from a whole-panel string sweep to the card it protects. The original
        assertion was `"tone-only" not in json.dumps(got)` — written when the only way that
        string could appear was the lab's "this is a tone-only build, fundamentals not
        fetched" line leaking into a panel whose fundamentals ARE live. Then a legitimate
        remedy arrived (the predates-this-source card recommends `refresh --tone-only`) and
        the sweep failed on text that is doing exactly what it should. The claim was never
        "that string appears nowhere"; it was "the lab does not speak for a fundamentals
        card it does not feed"."""
        got = self.ui._combined_draft_providers(self.fund, self.prices, self.tone_only)
        fund_card = json.dumps(got["fundamentals"])
        self.assertNotIn("tone-only", fund_card,
                         "the lab's tone-only fundamentals line leaked into the combined "
                         "panel's fundamentals card again")
        self.assertNotIn("yfinance", got["fundamentals"]["label"])

    def test_fundamentals_are_reported_from_the_snapshot_that_actually_feeds_the_page(self):
        got = self.ui._combined_draft_providers(self.fund, self.prices,
                                                self.tone_only)["fundamentals"]
        self.assertEqual(got["state"], lab.LIVE)
        self.assertIn("2026-08-06T16:50:08Z", got["headline"])
        self.assertEqual(got["documents"], 1)

    def test_a_missing_leg_is_listed_and_off_with_its_command_not_dropped(self):
        got = self.ui._combined_draft_providers(None, None, self.tone_only)
        for key, command in (("fundamentals", "stock_screener.py fetch"),
                             ("prices", "stock_screener.py prices")):
            self.assertIn(key, got, "an absent source must still be listed")
            self.assertEqual(got[key]["state"], lab.UNAVAILABLE)
            self.assertIn(command, got[key]["remedy"])

    def test_price_history_is_a_source_of_its_own_and_was_never_reported_before(self):
        got = self.ui._combined_draft_providers(self.fund, self.prices,
                                                self.tone_only)["prices"]
        self.assertEqual(got["state"], lab.LIVE)
        self.assertIn("126", got["headline"])

    def test_every_tone_source_passes_through_in_the_labs_own_words(self):
        got = self.ui._combined_draft_providers(self.fund, self.prices, self.tone_only)
        for source in lab.TONE_SOURCES:
            self.assertIn(source, got)
        self.assertEqual(got["yahoo"]["state"], lab.DEGRADED)
        self.assertEqual(got["yahoo"]["headline"], "2353 items")

    def test_no_tone_snapshot_is_one_honest_absence_not_three_silent_ones(self):
        got = self.ui._combined_draft_providers(self.fund, self.prices, None)
        self.assertEqual(got["tone"]["state"], lab.UNAVAILABLE)
        self.assertIn("--tone-only", got["tone"]["remedy"])
        self.assertIn("none is 0.00", got["tone"]["headline"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TheRingCursorRotatesTheRateCap(unittest.TestCase):
    """The free cap (~200/hour) is smaller than the universe (225), so a run that always
    starts at index 0 starves the SAME tail forever — the provider said "25 not asked" while
    guaranteeing the 25 were always the same names. Simulated over 450 runs, a ring cursor
    bounds the worst per-name gap at 2 runs against 145 runs of permanent starvation."""

    def _get(self, cap):
        calls = {"n": 0}

        def get(url, *a, **k):
            calls["n"] += 1
            if calls["n"] > cap:
                return FakeResponse(429)
            return FakeResponse(200, payload={"messages": [
                {"id": calls["n"], "body": "x", "created_at": "2026-08-15T00:00:00Z",
                 "entities": {"sentiment": {"basic": "Bullish"}}}]})
        return get

    def test_the_walk_starts_at_the_cursor_and_wraps(self):
        tickers = ["A", "B", "C", "D", "E"]
        docs, _p, report = lab.fetch_stocktwits(
            tickers, get=self._get(99), sleep=lambda _s: None, start=3)
        self.assertEqual(report["asked"], ["D", "E", "A", "B", "C"],
                         "the ring does not start at the cursor")

    def test_a_429_stops_the_walk_and_names_the_unasked(self):
        tickers = ["A", "B", "C", "D", "E"]
        _d, prov, report = lab.fetch_stocktwits(
            tickers, get=self._get(2), sleep=lambda _s: None, start=0)
        self.assertEqual(report["asked"], ["A", "B"])
        self.assertEqual(report["not_attempted"], ["C", "D", "E"])
        self.assertTrue(report["throttled"])
        self.assertIn("not asked", prov.headline)

    def test_no_name_starves_under_rotation(self):
        """The property the whole design exists for: with the cap below the universe, every
        name is still asked within a bounded number of runs when the cursor advances by the
        asked count — where a fixed start leaves the tail unasked FOREVER."""
        tickers = ["T%02d" % i for i in range(9)]
        cap = 4
        seen_rotating, seen_fixed = set(), set()
        cursor = 0
        for _run in range(6):
            _d, _p, rep = lab.fetch_stocktwits(
                tickers, get=self._get(cap), sleep=lambda _s: None, start=cursor)
            seen_rotating.update(rep["asked"])
            cursor = (cursor + len(rep["asked"])) % len(tickers)
            _d2, _p2, rep2 = lab.fetch_stocktwits(
                tickers, get=self._get(cap), sleep=lambda _s: None, start=0)
            seen_fixed.update(rep2["asked"])
        self.assertEqual(sorted(seen_rotating), tickers,
                         "rotation left a name permanently unasked")
        self.assertNotEqual(sorted(seen_fixed), tickers,
                            "the fixed-start control reached everyone, so this test can no "
                            "longer demonstrate the starvation it exists to prevent")

    def test_the_cursor_survives_a_round_trip_and_falls_back_in_order(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "cursor.json")
            lab.write_stocktwits_cursor(7, path=path)
            self.assertEqual(lab.read_stocktwits_cursor(9, path=path, env={}), 7)
            # no file, CI run number derives an offset
            gone = os.path.join(td, "absent.json")
            self.assertEqual(
                lab.read_stocktwits_cursor(225, path=gone,
                                           env={"GITHUB_RUN_NUMBER": "3"}),
                (3 * 200) % 225)
            # nothing at all: zero, the fallback of last resort
            self.assertEqual(lab.read_stocktwits_cursor(225, path=gone, env={}), 0)

    def test_a_capped_out_row_is_stamped_not_left_ambiguous(self):
        """ANET's 502 and a rate-capped tail used to render identically to "nobody posted":
        coverage 0 either way. The stamp is what the page's fourth absence state reads."""
        rows = [{"ticker": "A", "name": "A"}, {"ticker": "B", "name": "B"}]
        lab.attach_declared(rows, [{"ticker": "A", "declared": "Bullish", "title": "x"}],
                            "stocktwits", asked=["A"])
        self.assertTrue(rows[0]["stocktwits_attempted"])
        self.assertFalse(rows[1]["stocktwits_attempted"])
        self.assertEqual(rows[1]["stocktwits_coverage"], 0)


class TheToneLedgerIsTheResidueTheRefreshLeaves(unittest.TestCase):
    """Every refresh overwrites the snapshot, so weeks of scheduled runs had produced ONE
    observation: the latest. The ledger is one dated row per (run, ticker, source), and the
    scheduled jobs that already fire make it a real series by existing."""

    def _snapshot(self):
        return {
            "built_at": "2026-08-15T03:00:00+00:00", "tone_only": True, "screened": 2,
            "rows": [
                {"ticker": "AAA", "stocktwits_tone": 0.5, "stocktwits_coverage": 4,
                 "stocktwits_toned": 2, "stocktwits_fresh": 1, "stocktwits_base": 0.67,
                 "stocktwits_attempted": True, "yahoo_tone": None, "yahoo_coverage": 0,
                 "yahoo_toned": 0, "yahoo_fresh": 0},
                {"ticker": "BBB", "stocktwits_tone": None, "stocktwits_coverage": 0,
                 "stocktwits_toned": 0, "stocktwits_fresh": 0, "stocktwits_base": 0.67,
                 "stocktwits_attempted": False, "yahoo_tone": 0.1, "yahoo_coverage": 3,
                 "yahoo_toned": 3, "yahoo_fresh": 2},
            ],
            "providers": [{"key": "stocktwits", "state": "live", "documents": 4},
                          {"key": "yahoo", "state": "degraded", "documents": 3}],
        }

    def test_a_row_lands_per_run_ticker_source_and_absence_survives_csv(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            shard = lab.append_ledger(self._snapshot(), root=td)
            body = open(shard, encoding="utf-8").read().splitlines()
            self.assertEqual(body[0], ",".join(lab.LEDGER_FIELDS))
            self.assertEqual(len(body), 1 + 2 * len(lab.TONE_SOURCES))
            # BBB's stocktwits tone is None -> an EMPTY cell, never 0. The three-state
            # absence rule has to survive the format change or the ledger poisons every
            # analysis built on it with silent neutrality.
            bbb = [l for l in body if l.startswith("2026-08-15T03:00:00+00:00")
                   and ",BBB,stocktwits," in l][0]
            parts = bbb.split(",")
            self.assertEqual(parts[lab.LEDGER_FIELDS.index("tone")], "")
            self.assertEqual(parts[lab.LEDGER_FIELDS.index("attempted")], "0")
            aaa_yh = [l for l in body if ",AAA,yahoo," in l][0].split(",")
            # yahoo has no attempted concept: empty, which must never read as "not asked".
            self.assertEqual(aaa_yh[lab.LEDGER_FIELDS.index("attempted")], "")

    def test_two_appends_accumulate_rather_than_overwrite(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            lab.append_ledger(self._snapshot(), root=td)
            snap2 = self._snapshot(); snap2["built_at"] = "2026-08-16T03:00:00+00:00"
            shard = lab.append_ledger(snap2, root=td)
            body = open(shard, encoding="utf-8").read().splitlines()
            self.assertEqual(len(body), 1 + 2 * 2 * len(lab.TONE_SOURCES),
                             "the second run replaced the first instead of following it")
            self.assertEqual(sum(1 for l in body if l == ",".join(lab.LEDGER_FIELDS)), 1,
                             "the header was written twice")

    def test_runs_csv_records_provider_state_per_source(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            lab.append_ledger(self._snapshot(), root=td)
            runs = open(os.path.join(td, "runs.csv"), encoding="utf-8").read()
            self.assertIn("stocktwits,live,4,0.67", runs)
            self.assertIn("yahoo,degraded,3,", runs)

    def test_a_test_snapshot_write_leaves_no_ledger_row(self):
        """The first version appended on EVERY write_snapshot, and one unittest run salted
        the real history with a company called AAA. The hook fires only for the canonical
        path or an explicit env override — a history test runs can silently salt is worse
        than no history."""
        import tempfile
        src = inspect.getsource(lab.write_snapshot)
        self.assertIn("os.path.abspath(path) == os.path.abspath(SNAPSHOT_PATH)", src)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "elsewhere.json")
            before = os.path.exists(lab.TONE_LEDGER_DIR)
            lab.write_snapshot(self._snapshot(), path)
            self.assertEqual(os.path.exists(lab.TONE_LEDGER_DIR), before,
                             "a non-canonical write created the real ledger")

    def test_a_broken_ledger_never_breaks_the_refresh(self):
        """The firewall: the ledger is additive or absent, never a failure mode. Env points
        the writer at a path that cannot be a directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            blocker = os.path.join(td, "blocker")
            open(blocker, "w").write("a file where a directory must go")
            os.environ[lab.TONE_LEDGER_DIR_ENV] = os.path.join(blocker, "nested")
            try:
                path = os.path.join(td, "snap.json")
                lab.write_snapshot(self._snapshot(), path)   # must not raise
                self.assertTrue(os.path.exists(path), "the snapshot itself was lost")
            finally:
                del os.environ[lab.TONE_LEDGER_DIR_ENV]
