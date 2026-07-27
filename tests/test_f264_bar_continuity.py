"""A continuity check for the holes `validate_ohlc` leaves — F264, closing F204's open half.

F204 established that `validate_ohlc` catches every corruption class and **drops rather
than raises**, leaving a discontinuity nothing downstream detects: the `min_bars` floor
does not fire, staleness inspects only the latest bar, and the NaN gate sees finite values.
It named that gap as H30's open bar-continuity item. `tools/bar_continuity.py` fills it.

**Why a naive detector would be useless.** Most gaps in intraday equity data are
legitimate — a US session is ~7 hourly bars with an overnight break after each. On the
committed archive, **47** steps exceed the cadence and every one is a session boundary. A
"flag any gap" check would fire 47 times and be ignored, which is how the original
poison-cache footgun survived (F167).

The useful question is whether a bar is missing from **inside** a session, which needs no
market calendar: an intra-session hole has bars on both sides on the **same calendar date**.

**It found one on its first run, in real logged data:**

    2026-05-07 15:30 -> 17:30    1 bar missing

**And the durable record cannot say why.** There are **zero** monitor events on that date,
and zero anywhere mentioning a drop — because `validate_ohlc` emits a `log.warning`, not a
monitor event. So the hole could be a validation drop, a missed scheduler cycle, or a
vendor omission, and nothing committed distinguishes them. That is F204's third-instance
claim — degraded paths announcing themselves to a log nobody keeps — demonstrated rather
than argued. **This node does not attribute the hole to `validate_ohlc`;** the point is
precisely that the record is insufficient to attribute it at all.

Nothing on the live path calls this. Wiring it into `fetch_yfinance`, to raise or to emit a
monitor event, is a one-line owner decision left to the owner.

Guards are bidirectional: they fail if the detector stops finding the known hole, if it
starts flagging session boundaries (the noise failure), if the archive's boundary count
moves, or if the monitor log gains an entry explaining the hole — which would be good news
and a reason to supersede.
"""
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import bar_continuity as bc  # noqa: E402

EVENTS = (ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"
          / "monitor_events.jsonl")


def idx(stamps):
    return pd.DatetimeIndex(pd.to_datetime(list(stamps)))


class ItDistinguishesHolesFromSessionBreaksTests(unittest.TestCase):
    """The whole design problem, on synthetic input."""

    def test_a_clean_hourly_run_has_no_holes(self):
        out = bc.analyse(idx(pd.date_range("2026-01-05 14:30", periods=7, freq="h")))
        self.assertEqual(out["intra_session_holes"], [])
        self.assertEqual(out["session_boundaries"], 0)
        self.assertEqual(out["step_seconds"], 3600)

    def test_an_overnight_break_is_not_a_hole(self):
        """Non-vacuity in the other direction: the detector must stay quiet on the
        gap that occurs after every single trading day."""
        stamps = (list(pd.date_range("2026-01-05 14:30", periods=7, freq="h"))
                  + list(pd.date_range("2026-01-06 14:30", periods=7, freq="h")))
        out = bc.analyse(idx(stamps))
        self.assertEqual(out["intra_session_holes"], [],
                         "an overnight break is being reported as a hole — the detector "
                         "would fire once per trading day and be ignored")
        self.assertEqual(out["session_boundaries"], 1)

    def test_a_bar_missing_mid_session_is_caught(self):
        stamps = list(pd.date_range("2026-01-05 14:30", periods=7, freq="h"))
        del stamps[3]
        out = bc.analyse(idx(stamps))
        self.assertEqual(len(out["intra_session_holes"]), 1)
        self.assertEqual(out["intra_session_holes"][0]["missing_bars"], 1)
        self.assertFalse(bc.is_continuous(idx(stamps)))

    def test_three_consecutive_missing_bars_are_counted(self):
        """F204's worked example: three dropped bars, one hole."""
        stamps = list(pd.date_range("2026-01-05 13:30", periods=10, freq="h"))
        del stamps[4:7]
        out = bc.analyse(idx(stamps))
        self.assertEqual(len(out["intra_session_holes"]), 1)
        self.assertEqual(out["intra_session_holes"][0]["missing_bars"], 3)

    def test_the_cadence_is_inferred_by_mode_not_by_minimum(self):
        """A duplicate stamp would drag a min-based estimate to zero and make every
        subsequent step look like a hole."""
        stamps = list(pd.date_range("2026-01-05 14:30", periods=7, freq="h"))
        stamps.insert(3, stamps[3])
        out = bc.analyse(idx(stamps))
        self.assertEqual(out["step_seconds"], 3600)
        self.assertEqual(out["duplicate_stamps"], 1)
        self.assertEqual(out["intra_session_holes"], [])

    def test_a_short_panel_is_reported_rather_than_guessed_at(self):
        out = bc.analyse(idx(pd.date_range("2026-01-05", periods=2, freq="h")))
        self.assertIsNone(out["step_seconds"])
        self.assertEqual(out["intra_session_holes"], [])


class TheLiveArchiveHasExactlyOneHoleTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = bc.analyse(bc._archive_index())

    def test_the_archive_is_the_expected_shape(self):
        self.assertEqual(self.out["bars"], 322)
        self.assertEqual(self.out["step_seconds"], 3600)

    def test_the_session_boundaries_dominate(self):
        """Why the naive detector would have been useless here."""
        self.assertEqual(
            self.out["session_boundaries"], 47,
            "the session-boundary count moved — F264's 'a flag-any-gap check would fire "
            "47 times' needs re-deriving")

    def test_exactly_one_intra_session_hole_is_found(self):
        holes = self.out["intra_session_holes"]
        self.assertEqual(
            len(holes), 1,
            "the intra-session hole count changed — if it went to zero the archive was "
            "repaired; supersede F264 rather than editing this")
        self.assertEqual(holes[0]["missing_bars"], 1)
        self.assertIn("2026-05-07", holes[0]["after"])


class TheRecordCannotExplainItTests(unittest.TestCase):
    """F204's 'a log nobody keeps', with a live witness."""

    @classmethod
    def setUpClass(cls):
        cls.events = [json.loads(l) for l in
                      EVENTS.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_no_monitor_event_exists_on_the_day_of_the_hole(self):
        same_day = [e for e in self.events if e["event_time"][:10] == "2026-05-07"]
        self.assertEqual(
            same_day, [],
            "the monitor log now has an entry on the day of the hole — the durable "
            "record may be able to explain it; supersede F264's attribution claim")

    def test_no_event_anywhere_records_a_dropped_bar(self):
        dropped = [e for e in self.events
                   if "ohlc" in e["message"].lower() or "dropping" in e["message"].lower()]
        self.assertEqual(
            dropped, [],
            "validate_ohlc now emits a monitor event — that is the fix F204 asked for; "
            "supersede rather than retune")

    def test_the_events_log_is_otherwise_populated(self):
        """Non-vacuity: 'no event explains it' must not be because there are none."""
        self.assertGreater(len(self.events), 100)


if __name__ == "__main__":
    unittest.main()
