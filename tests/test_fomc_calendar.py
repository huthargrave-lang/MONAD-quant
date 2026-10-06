"""
The FOMC scheduled-meeting calendar (src/research/fomc_calendar.py): every heading and row
shape the Fed's pages use, the exclusions that keep surprises out, and the committed
fixture's plausibility.
"""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import fomc_calendar as fc  # noqa: E402

HISTORICAL = """
<h5>January 9 Conference Call - 2008</h5>
<h5>January 29-30 Meeting - 2008</h5>
<h5>March 18 Meeting - 2008</h5>
<h5 class="panel-heading">April/May 30-1 Meeting - 2008</h5>
<h5>March 15 (unscheduled) Meeting - 2008</h5>
<h5>March 17-18 (cancelled) Meeting - 2008</h5>
<h5>March 19 (notation vote) - 2008</h5>
<h5>October 31-November 1 Meeting - 2008</h5>
"""

CURRENT = """
<h4><a id="1">2026 FOMC Meetings</a></h4>
<div class="row fomc-meeting" ">
 <div class="fomc-meeting__month col-xs-5"><strong>January</strong></div>
 <div class="fomc-meeting__date col-xs-4">27-28</div></div>
<div class="fomc-meeting--shaded row fomc-meeting" ">
 <div class="fomc-meeting--shaded fomc-meeting__month col-xs-5"><strong>March</strong></div>
 <div class="fomc-meeting__date col-xs-4">17-18*</div></div>
<div class="row fomc-meeting" ">
 <div class="fomc-meeting__month col-xs-5"><strong>Apr/May</strong></div>
 <div class="fomc-meeting__date col-xs-4">30-1</div></div>
<div class="row fomc-meeting" ">
 <div class="fomc-meeting__month col-xs-5"><strong>May</strong></div>
 <div class="fomc-meeting__date col-xs-4">22 (notation vote)</div></div>
"""


class Parsing(unittest.TestCase):
    def test_historical_keeps_scheduled_meetings_only(self):
        got = [m["announcement"] for m in fc.parse_historical(HISTORICAL, 2008)]
        self.assertEqual(got, ["2008-01-30", "2008-03-18", "2008-05-01", "2008-11-01"])

    def test_current_page_reads_both_row_classes_and_abbreviated_months(self):
        got = [(m["start"], m["announcement"]) for m in fc.parse_current(CURRENT)]
        self.assertEqual(got, [("2026-01-27", "2026-01-28"), ("2026-03-17", "2026-03-18"),
                               ("2026-04-30", "2026-05-01")])

    def test_an_unparseable_meeting_heading_is_an_error_not_a_skip(self):
        with self.assertRaises(fc.CalendarError):
            fc.parse_historical("<h5>Sometime Meeting - 2008</h5>", 2008)


class TheFixture(unittest.TestCase):
    def test_it_is_plausible_and_has_provenance(self):
        record = json.loads(fc.FIXTURE.read_text(encoding="utf-8"))
        self.assertTrue(record["pages"] and all(len(p["sha256"]) == 64 for p in record["pages"]))
        dates = fc.announcements()
        self.assertEqual(dates, sorted(dates))
        per_year = {}
        for d in dates:
            per_year[d.year] = per_year.get(d.year, 0) + 1
        for year in range(2004, 2027):
            expected = 7 if year == 2020 else 8      # March 2020's meeting was cancelled
            self.assertEqual(per_year[year], expected, year)

    def test_known_surprises_are_absent(self):
        dates = set(fc.announcements())
        for surprise in (dt.date(2008, 1, 22), dt.date(2020, 3, 3), dt.date(2020, 3, 15)):
            self.assertNotIn(surprise, dates)
        self.assertIn(dt.date(2008, 12, 16), dates)


if __name__ == "__main__":
    unittest.main()
