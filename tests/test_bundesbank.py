"""Deutsche Bundesbank series (src/research/bundesbank.py): parsing, the USD gold build,
and close-only bars on an exchange calendar. No network: a fixture in the API's layout."""
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import bundesbank as bb  # noqa: E402
from src.research import nyse_calendar  # noqa: E402

G = "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic"


def message(obs: dict) -> bytes:
    """A generic-data message in the API's layout: explicit end tags; a day without a
    fixing is an observation with a status and no value."""
    parts = []
    for day, v in obs.items():
        val = (f'<generic:ObsValue value="{v}"></generic:ObsValue>' if v is not None else "")
        parts.append(f'<generic:Obs><generic:ObsDimension value="{day}"></generic:ObsDimension>{val}'
                     f'<generic:Attributes><generic:Value id="OBS_STATUS" value="K"></generic:Value>'
                     f'</generic:Attributes></generic:Obs>')
    return (f'<message:GenericData xmlns:message="m" xmlns:generic="{G}"><message:DataSet>'
            f'<generic:Series><generic:SeriesKey></generic:SeriesKey>{"".join(parts)}</generic:Series>'
            f'</message:DataSet></message:GenericData>').encode()


class Parse(unittest.TestCase):
    def test_values_by_date_and_empty_days_counted_not_filled(self):
        s, empty = bb.parse_generic(message({"2020-01-03": 1.5, "2020-01-04": None, "2020-01-06": 1.6}))
        self.assertEqual(list(s.index), [pd.Timestamp("2020-01-03"), pd.Timestamp("2020-01-06")])
        self.assertEqual(empty, 1)

    def test_a_message_without_a_series_is_refused(self):
        with self.assertRaises(bb.SourceError):
            bb.fetch_series("BBEX3", "X", "2020-01-01", "2020-01-02",
                            get=lambda url: b'<message:Error xmlns:message="m"/>')


class GoldInDollars(unittest.TestCase):
    def test_dm_per_kg_over_dm_per_usd_over_ounces(self):
        gold = {"1990-01-02": 20000.0, "1990-01-03": 20100.0, "1990-01-04": 20200.0}
        fx = {"1990-01-02": 1.7, "1990-01-03": 1.68, "1990-01-05": 1.69}
        def get(url):
            return message(gold if "XAU" in url else fx)
        usd, rep = bb.frankfurt_gold_usd("1990-01-01", "1990-01-10", get=get)
        self.assertAlmostEqual(usd["1990-01-02"], 20000.0 / 1.7 / bb.TROY_OUNCES_PER_KG)
        self.assertEqual(len(usd), 2)
        self.assertEqual((rep["gold_without_fx"], rep["fx_without_gold"]), (1, 1))
        self.assertIn("Bundesbank", rep["attribution"])


class Sessions(unittest.TestCase):
    def test_a_missing_fixing_carries_and_is_reported(self):
        sessions = pd.bdate_range("1990-01-02", "1990-01-12")
        s = pd.Series(1.0, index=sessions.delete(3)).cumsum()     # one session without a fixing
        out = bb.bars_on_sessions(s, sessions)
        self.assertEqual(out.carried, [sessions[3].date().isoformat()])
        self.assertEqual(out.bars["Close"].iloc[3], out.bars["Close"].iloc[2])
        self.assertTrue(out.bars["Close"].notna().all())

    def test_a_long_gap_is_refused_and_off_calendar_fixings_are_counted(self):
        sessions = pd.bdate_range("1990-01-02", "1990-01-31")
        s = pd.Series(1.0, index=sessions[:3].append(sessions[8:]))
        with self.assertRaises(bb.SourceError):
            bb.bars_on_sessions(s, sessions)
        extra = pd.Series(1.0, index=sessions.append(pd.DatetimeIndex(["1990-01-06"])).sort_values())
        self.assertEqual(bb.bars_on_sessions(extra, sessions).dropped_off_calendar, 1)


class PreTwoThousandOneClosures(unittest.TestCase):
    def test_hurricane_gloria_and_the_nixon_funeral_closed_the_exchange(self):
        import datetime as dt
        self.assertFalse(nyse_calendar.is_session(dt.date(1985, 9, 27)))
        self.assertFalse(nyse_calendar.is_session(dt.date(1994, 4, 27)))
        self.assertTrue(nyse_calendar.is_session(dt.date(1994, 4, 26)))


if __name__ == "__main__":
    unittest.main()
