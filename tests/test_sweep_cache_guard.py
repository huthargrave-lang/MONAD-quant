"""sweep.py's hourly cache: usually bypassed, and endpoint-only when it isn't.

The 2026-07-25 handoff lists "`sweep.py` has the same cache footgun" as open, meaning the
poison-cache class F167 closed elsewhere. Measuring it turned up something different, and
in one respect the opposite.

**The cache is almost never read back.** The read guard is::

    if len(df) > 0 and df.index[0] <= start_dt and df.index[-1] >= end_dt - timedelta(days=2)

`start_dt` is `pd.Timestamp("2024-08-01")` — **midnight**. The first intraday bar of that
day is 13:30 UTC. So `13:30 <= 00:00` is **False** and the cache is rejected, on every
invocation where `--start` is a plain date, which is the normal one. It is accepted only
when the cached panel happens to begin on an *earlier calendar day* than requested, i.e.
when some previous run used a wider start.

Two consequences pull in opposite directions:

* **The poison-cache risk is mostly moot here.** A bad panel is written but not re-read on
  the common path, so the failure mode the handoff assumed does not usually arise.
* **But the cache provides no rate-limit protection either**, and every sweep re-fetches.
  That is precisely what provokes the yfinance 429s H30 lists as open. The cache exists to
  prevent the thing it is not preventing.

And the behaviour is **invocation-dependent** — cached or not depending on what an earlier
run happened to request — which is worse than either consistent outcome, because a sweep's
data source silently differs between runs of the same command.

**When it IS read, the guard checks endpoints, not density.** A morning-only panel (F12's
quirk, ~3 bars/day instead of 7) has *identical* first and last timestamps and **43% of the
bars**; a panel with a 400-bar interior hole (F204's silent `validate_ohlc` drop) has
identical endpoints too. Both are accepted. So the one property that would catch the two
data defects this repo has actually recorded is the one not checked.

`sweep.py` is WARN-fenced (selection-of-record), so this records and guards rather than
fixes. The one-line change would be comparing `df.index[0].normalize() <= start_dt` and
adding a bars-per-day floor — but that alters which data the parameter selection sees, and
that is a sign-off decision.
"""
import datetime as dt
import re
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SWEEP = (ROOT / "sweep.py").read_text(encoding="utf-8")
START, END = "2024-08-01", "2026-07-22"


def guard_accepts(df, start=START, end=END):
    """The exact expression from sweep.py::fetch_ticker_hourly."""
    start_dt, end_dt = pd.Timestamp(start), pd.Timestamp(end)
    return bool(len(df) > 0 and df.index[0] <= start_dt
                and df.index[-1] >= end_dt - dt.timedelta(days=2))


def panel(bars_per_day, start=START, end=END, first_hour=13):
    idx = []
    for day in pd.bdate_range(start, end):
        for h in range(bars_per_day):
            idx.append(day + pd.Timedelta(hours=first_hour + h, minutes=30))
    return pd.DataFrame({"close": np.arange(len(idx), dtype=float)},
                        index=pd.DatetimeIndex(idx))


class TheGuardExpressionIsWhatWeThinkTests(unittest.TestCase):
    def test_the_read_guard_is_still_this_expression(self):
        self.assertIn(
            "if len(df) > 0 and df.index[0] <= start_dt and "
            "df.index[-1] >= end_dt - timedelta(days=2):", SWEEP,
            "sweep.py's cache read guard changed — every measurement below is derived "
            "from that exact expression")

    def test_the_cache_is_written_without_validation(self):
        idx = SWEEP.index("df = fetch_yfinance(symbol=ticker")
        window = SWEEP[idx:idx + 400]
        self.assertIn("df.to_csv(cache_file)", window)
        self.assertNotIn("validate_frame", window,
                         "sweep.py now validates before caching — the write side may "
                         "have adopted tools/data_cache.py")

    def test_sweep_is_fenced_so_this_is_recorded_not_fixed(self):
        import subprocess
        proc = subprocess.run(["python3", "tools/ctx.py", "can_edit", "sweep.py"],
                              cwd=str(ROOT), capture_output=True, text=True)
        self.assertIn("WARN", proc.stdout,
                      "sweep.py left the WARN fence — the one-line fix could now be "
                      "made directly, with sign-off")


class TheCacheIsUsuallyBypassedTests(unittest.TestCase):
    """The surprising half: midnight vs the first intraday bar."""

    def test_a_correct_full_panel_is_REJECTED(self):
        self.assertFalse(
            guard_accepts(panel(7)),
            "the cache now accepts a correctly-spanning panel — the date-vs-timestamp "
            "mismatch was fixed, so re-read this finding")

    def test_the_reason_is_the_start_comparison_not_the_end_one(self):
        df = panel(7)
        start_dt, end_dt = pd.Timestamp(START), pd.Timestamp(END)
        self.assertFalse(df.index[0] <= start_dt, "the start comparison now passes")
        self.assertTrue(df.index[-1] >= end_dt - dt.timedelta(days=2),
                        "the end comparison is not the blocker")
        self.assertEqual(df.index[0].time(), dt.time(13, 30))
        self.assertEqual(start_dt.time(), dt.time(0, 0))

    def test_it_IS_accepted_when_a_previous_run_used_a_wider_start(self):
        """Which makes the behaviour invocation-dependent rather than simply off."""
        wider = panel(7)
        wider.index = wider.index - pd.Timedelta(days=1)
        self.assertTrue(
            guard_accepts(wider),
            "a wider cached panel is no longer accepted either — the cache would be "
            "entirely dead, which is a different (simpler) finding")

    def test_normalising_the_first_index_would_fix_it(self):
        """The one-line change, stated so the fix is unambiguous when signed off."""
        df = panel(7)
        self.assertTrue(df.index[0].normalize() <= pd.Timestamp(START))


class WhenReadItChecksEndpointsNotDensityTests(unittest.TestCase):
    """The half that matters if the start comparison is ever fixed."""

    def setUp(self):
        # shift back a day so the guard's start comparison passes, isolating density
        self.full = panel(7)
        self.full.index = self.full.index - pd.Timedelta(days=1)

    def _shift(self, df):
        out = df.copy()
        out.index = out.index - pd.Timedelta(days=1)
        return out

    def test_a_morning_only_panel_is_accepted_identically(self):
        morning = self._shift(panel(3))
        self.assertTrue(guard_accepts(morning),
                        "a 3-bar/day panel is no longer accepted — the density hole "
                        "may have been closed")
        self.assertEqual(morning.index[0], self.full.index[0])
        self.assertEqual(morning.index[-1].date(), self.full.index[-1].date())

    def test_and_it_carries_well_under_half_the_bars(self):
        morning = self._shift(panel(3))
        ratio = len(morning) / len(self.full)
        self.assertLess(
            ratio, 0.5,
            "the morning-only panel is no longer much thinner than the full one — "
            "F12's quirk shape changed")

    def test_an_interior_hole_is_accepted_too(self):
        """F204: validate_ohlc drops bad bars silently, leaving exactly this."""
        holed = self.full.drop(self.full.index[1500:1900])   # interior; the panel is ~3.6k rows
        self.assertTrue(guard_accepts(holed))
        self.assertEqual(holed.index[0], self.full.index[0])
        self.assertEqual(holed.index[-1], self.full.index[-1])
        self.assertEqual(len(self.full) - len(holed), 400,
                         "the interior slice no longer removes 400 bars — check the "
                         "panel size before trusting the hole")

    def test_a_bars_per_day_floor_would_separate_them(self):
        """The second half of the fix, stated concretely."""
        sessions = len(pd.bdate_range(START, END))
        self.assertGreater(len(self.full) / sessions, 6.0)
        self.assertLess(len(self._shift(panel(3))) / sessions, 4.0)


class TheCacheDoesNotPreventTheRateLimitsItExistsForTests(unittest.TestCase):
    def test_every_sweep_refetches_on_the_normal_invocation(self):
        self.assertFalse(guard_accepts(panel(7)))
        self.assertIn("timedelta(days=710)", SWEEP,
                      "sweep.py's default span changed — the re-fetch cost differs")

    def test_the_freshness_window_is_generous_so_it_is_not_the_limiter(self):
        fetcher = (ROOT / "src" / "data" / "fetcher.py").read_text(encoding="utf-8")
        hours = int(re.search(r"def _cache_is_fresh\(path: str, max_age_hours: int = (\d+)",
                              fetcher).group(1))
        self.assertGreaterEqual(
            hours, 24,
            "the cache freshness window shrank — staleness, not the start comparison, "
            "could now be what forces the re-fetch")


if __name__ == "__main__":
    unittest.main()
