"""
The rules-based NYSE calendar (src/research/nyse_calendar.py) and the gate rules v2 price
window floor it justifies (prereg.MIN_PRICE_WINDOW_DAYS; decision debate 2026-10-06, price
trigger R1).
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import nyse_calendar as cal, prereg  # noqa: E402

#: Published NYSE trading-day counts.
PUBLISHED = {2001: 248, 2012: 250, 2018: 251, 2019: 252, 2020: 253, 2021: 252, 2022: 251,
             2023: 250, 2024: 252, 2025: 250}


class TheCalendar(unittest.TestCase):
    def test_it_reproduces_the_published_yearly_counts(self):
        for year, n in PUBLISHED.items():
            self.assertEqual(cal.sessions_between(dt.date(year, 1, 1), dt.date(year, 12, 31)), n, year)

    def test_known_rule_cases(self):
        self.assertFalse(cal.is_session(dt.date(2022, 6, 20)))   # Juneteenth observed (Sunday)
        self.assertTrue(cal.is_session(dt.date(2021, 6, 18)))    # before Juneteenth existed
        self.assertTrue(cal.is_session(dt.date(2021, 12, 31)))   # Saturday New Year not made up
        self.assertFalse(cal.is_session(dt.date(2024, 3, 29)))   # Good Friday
        self.assertFalse(cal.is_session(dt.date(2012, 10, 30)))  # Hurricane Sandy


class TheWindowFloor(unittest.TestCase):
    def test_every_window_of_the_floor_holds_the_session_floor(self):
        """Every MIN_PRICE_WINDOW_DAYS window starting 2000-01-01..2030-12-31 (end included)
        holds at least MIN_PRICE_SESSIONS sessions, so validate never accepts a window that
        perfect data could not fill."""
        span = dt.timedelta(days=prereg.MIN_PRICE_WINDOW_DAYS)
        day, last = dt.date(2000, 1, 1), dt.date(2030, 12, 31)
        n = cal.sessions_between(day, day + span)
        worst = n
        while day < last:
            # slide by one day: drop `day`, add the next end
            n += cal.is_session(day + span + dt.timedelta(days=1)) - cal.is_session(day)
            day += dt.timedelta(days=1)
            worst = min(worst, n)
        self.assertGreaterEqual(worst, prereg.MIN_PRICE_SESSIONS)


if __name__ == "__main__":
    unittest.main()
