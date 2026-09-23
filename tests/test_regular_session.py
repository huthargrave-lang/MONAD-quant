"""
fetcher.regular_session judges the US session in New York time.

sweep.py:196 and tools/equity_curve.py:193 call ``between_time("09:30", "16:00")`` on
fetch_yfinance's naive-UTC index, which keeps only the first three bars of each session
(RESEARCH_WEB.md F13's morning-only artifact, reproduced by a filter rather than by the
fetch). These pin the correct behaviour and the size of the defect, so the two call
sites can be migrated with a measured before/after once that is signed off.
"""
import unittest

import numpy as np
import pandas as pd

from src.data.fetcher import regular_session


def _session(start_utc, n=7):
    idx = pd.date_range(start_utc, periods=n, freq="h")
    return pd.DataFrame({"close": np.arange(float(n))}, index=idx)


class RegularSession(unittest.TestCase):
    def test_full_summer_session_survives(self):   # EDT: 09:30 ET = 13:30 UTC
        self.assertEqual(len(regular_session(_session("2026-08-03 13:30"))), 7)

    def test_full_winter_session_survives(self):   # EST: 09:30 ET = 14:30 UTC
        self.assertEqual(len(regular_session(_session("2026-01-05 14:30"))), 7)

    def test_pre_and_after_market_are_dropped(self):
        df = _session("2026-08-03 11:30", n=11)    # 07:30 .. 17:30 ET
        kept = regular_session(df)
        self.assertEqual(list(kept.index.strftime("%H:%M")),
                         ["13:30", "14:30", "15:30", "16:30", "17:30", "18:30", "19:30"])

    def test_tz_aware_input_is_honoured_and_output_is_naive_utc(self):
        df = _session("2026-08-03 09:30").tz_localize("America/New_York")
        out = regular_session(df)
        self.assertEqual(len(out), 7)
        self.assertIsNone(out.index.tz)
        self.assertEqual(out.index[0], pd.Timestamp("2026-08-03 13:30"))

    def test_weekend_bars_are_not_a_session(self):
        df = _session("2026-08-08 13:30")   # a Saturday
        self.assertEqual(len(regular_session(df)), 0)

    def test_the_utc_filter_it_replaces_keeps_only_the_morning(self):
        df = _session("2026-08-03 13:30")
        self.assertEqual(len(df.between_time("09:30", "16:00")), 3)


if __name__ == "__main__":
    unittest.main()
