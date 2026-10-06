"""
Treasury coupon auctions (src/research/treasury_auctions.py): tenor mapping for
reopenings, the exclusions, the announcement constraint, and the committed fixture.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import treasury_auctions as ta  # noqa: E402


def row(term, auction="2015-02-10", announced="2015-02-05", **kw):
    r = {"cusip": "X" + term, "securityType": "Note", "securityTerm": term, "auctionDate": auction,
         "announcementDate": announced, "reopening": "No", "tips": "No", "floatingRate": "No",
         "type": "Note"}
    r.update(kw)
    return r


class Parsing(unittest.TestCase):
    def test_reopenings_map_to_their_nominal_tenor(self):
        self.assertEqual(ta._original_term("9-Year 10-Month"), "10-Year")
        self.assertEqual(ta._original_term("29-Year 11-Month"), "30-Year")
        self.assertEqual(ta._original_term("10-Year"), "10-Year")
        self.assertIsNone(ta._original_term("13-Week"))

    def test_tips_and_frns_are_excluded(self):
        got = ta.parse([row("10-Year"), row("10-Year", tips="Yes"), row("2-Year", floatingRate="Yes")])
        self.assertEqual([a["term"] for a in got], ["10-Year"])

    def test_an_auction_announced_after_it_was_held_is_refused(self):
        with self.assertRaises(ta.AuctionError):
            ta.parse([row("10-Year", auction="2015-02-10", announced="2015-02-11")])


class TheFixture(unittest.TestCase):
    def test_coverage_and_provenance(self):
        a = ta.auctions()
        self.assertGreater(len(a), 1500)
        years = {x["auction"][:4] for x in a if x["term"] == "10-Year"}
        self.assertTrue({str(y) for y in range(2003, 2026)} <= years)
        self.assertTrue(all(x["announced"] <= x["auction"] for x in a))


if __name__ == "__main__":
    unittest.main()
