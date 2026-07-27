"""F12/F13's fetch-span bridge: the fix was additive, and the hazard may be stale.

F12 is the root-cause finding behind F13's reversal: a yfinance 1h request over a LONG
(~710-day) range returned only ~3 bars/day (the morning), while the SAME data fetched in
<=250-day chunks returned full 7-bar sessions. The live bot fetches a short ~40-day
window, so it traded full sessions while *every backtest and sweep* fetched ~710 days and
got morning-only data — a backtest<->live gap that made the hourly edge a sampling
artifact. F12 closes with *"Fixed by `tools/fetch_fullsession.py` (chunked re-pull)"*.

Two things are checkable offline, and they pull in opposite directions.

**The fix was additive, not corrective.** `fetch_fullsession.py` chunks at 240 days, well
inside the threshold. But the original long-span call sites were never converted, and one
of them is `sweep.py` — the tool that *selects the parameters the live bot runs on*. It
still defaults to 710 days (`sweep.py:103`) and fetches that span in a single 1h call
(`sweep.py:185`). `tools/instrument_screen.py` does the same 710-day single call, and
`tools/overnight_gap_risk_study.py` pins a ~721-day span through one `yf.download`. So if
the quirk still bites, the sweep is still exposed to it.

**But the most recent committed fetch shows it did not bite.** The gap study's input
manifest (`docs/research/data/overnight_gap_input_manifest_2026.json`, captured
2026-07-23) records "TQQQ **full-session** hourly OHLCV, TQQQ 1h, 2024-08-01 through
2026-07-22" at **3430 physical lines**. That span holds 515 weekdays, so the panel carries
**~6.7 bars per trading day** — closer to 7 than to F12's 3, from a single 721-day request.
The provenance record is the evidence; the raw bytes are deliberately not committed.

That is one instrument, one window, one capture date — it does not prove the quirk is gone
everywhere. It does contradict the blanket present-tense form of F12 ("every backtest/sweep
fetched ~710 days -> morning-only") as of that date. Yahoo is network-blocked here, so the
quirk cannot be re-measured; what can be done is to record both facts so neither is lost:
**the exposure is real and unconverted, and the most recent evidence says the hazard did
not fire.**

F13's own half is intact and asserted: the live window is ~120 days, comfortably inside the
threshold, which is exactly the asymmetry that created the gap.
"""
import ast
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHUNK_THRESHOLD_DAYS = 250      # F12's stated safe chunk size
MANIFEST = ROOT / "docs" / "research" / "data" / "overnight_gap_input_manifest_2026.json"


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def weekdays(start, end):
    d, n = start, 0
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += dt.timedelta(days=1)
    return n


class TheChunkedFixExistsTests(unittest.TestCase):
    def test_fetch_fullsession_chunks_inside_the_threshold(self):
        tree = ast.parse(_read("tools/fetch_fullsession.py"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "fetch_full")
        defaults = {a.arg: d for a, d in
                    zip(fn.args.args[-len(fn.args.defaults):], fn.args.defaults)}
        chunk = defaults["chunk_days"].value
        self.assertLessEqual(
            chunk, CHUNK_THRESHOLD_DAYS,
            "fetch_full's chunk size ({}) now exceeds F12's {}-day threshold — the fix "
            "itself would be exposed to the quirk it exists to avoid".format(
                chunk, CHUNK_THRESHOLD_DAYS))
        self.assertGreater(chunk, 100, "the chunk shrank enough to change the fetch cost")


class TheLongSpanCallSitesWereNeverConvertedTests(unittest.TestCase):
    """Each assertion fails when that site IS converted — which is good news, and means
    F12's 'fixed' wording finally describes the repo."""

    def test_the_sweep_still_defaults_to_a_710_day_span(self):
        source = _read("sweep.py")
        self.assertIn(
            "timedelta(days=710)", source,
            "sweep.py's default span changed. If it was chunked or shortened, F12's "
            "exposure through the parameter-selection tool is closed — say so in the "
            "web rather than deleting this test.")

    def test_the_sweep_fetches_that_span_in_ONE_call(self):
        source = _read("sweep.py")
        self.assertIn('fetch_yfinance(symbol=ticker, start=start, end=end, interval="1h")',
                      source,
                      "sweep.py's hourly fetch changed shape — check whether it now chunks")
        self.assertNotIn("fetch_full", source,
                         "sweep.py now imports the chunked fetcher — the conversion may "
                         "have happened; verify and update F12")

    def test_instrument_screen_still_makes_a_710_day_single_call(self):
        source = _read("tools/instrument_screen.py")
        self.assertIn("timedelta(days=710)", source)
        self.assertIn('interval="1h"', source)
        self.assertNotIn("fetch_full", source)

    def test_the_gap_study_pins_a_span_beyond_the_threshold(self):
        source = _read("tools/overnight_gap_risk_study.py")
        start = dt.date.fromisoformat(re.search(r'^START = "([\d-]+)"', source, re.M).group(1))
        end = dt.date.fromisoformat(re.search(r'^END = "([\d-]+)"', source, re.M).group(1))
        self.assertGreater(
            (end - start).days, CHUNK_THRESHOLD_DAYS,
            "the gap study's pinned span dropped inside the chunk threshold — its "
            "evidence below no longer speaks to long-span fetches")

    def test_no_call_site_was_converted_to_the_chunked_fetcher(self):
        """The summary claim: `fetch_full` has no first-party consumer outside its own
        module, so 'Fixed by tools/fetch_fullsession.py' means a tool was ADDED."""
        consumers = []
        for path in list((ROOT / "tools").glob("*.py")) + [ROOT / "sweep.py"]:
            if path.name == "fetch_fullsession.py":
                continue
            if "fetch_full(" in path.read_text(encoding="utf-8"):
                consumers.append(path.name)
        self.assertEqual(
            consumers, [],
            "fetch_full now has consumers ({}) — the chunked fix is being used, not "
            "merely available. Update F12's wording.".format(consumers))


class TheQuirkDidNotBiteInTheMostRecentCommittedFetchTests(unittest.TestCase):
    """Evidence from a provenance record, not from a live fetch — Yahoo is blocked."""

    @classmethod
    def setUpClass(cls):
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.hourly = next(i for i in payload["inputs"] if "1h," in i["query"])
        cls.captured = payload["captured_utc_date"]

    def test_the_recorded_query_spans_more_than_the_threshold(self):
        start, end = re.findall(r"(\d{4}-\d{2}-\d{2})", self.hourly["query"])
        span = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
        self.assertGreater(
            span, CHUNK_THRESHOLD_DAYS,
            "the manifest's hourly query no longer spans a long range, so it can no "
            "longer speak to whether the long-span quirk fires")

    def test_the_panel_carries_close_to_a_FULL_session_per_day(self):
        start, end = re.findall(r"(\d{4}-\d{2}-\d{2})", self.hourly["query"])
        days = weekdays(dt.date.fromisoformat(start), dt.date.fromisoformat(end))
        per_day = (self.hourly["physical_lines"] - 2) / days   # minus header rows
        self.assertGreater(
            per_day, 6.0,
            "the committed hourly panel now averages {:.2f} bars/trading-day. If it "
            "dropped toward 3, F12's quirk is firing again and every long-span fetch "
            "site listed above is actively producing morning-only data."
            .format(per_day))
        self.assertLess(per_day, 7.5, "more than a full session per day — recount")

    def test_the_study_itself_calls_the_panel_full_session(self):
        self.assertIn("full-session", self.hourly["name"],
                      "the manifest no longer labels this panel full-session")

    def test_the_evidence_is_a_provenance_record_not_committed_bytes(self):
        """Stated so nobody mistakes this for a re-measurement."""
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertFalse(
            payload["raw_bytes_committed"],
            "raw vendor bytes are now committed — count the bars directly instead of "
            "inferring density from physical_lines")
        self.assertIn("sha256", self.hourly)


class TheLiveWindowIsShortTests(unittest.TestCase):
    """F13's half — the asymmetry that created the gap."""

    def test_the_live_fetch_window_is_inside_the_threshold(self):
        source = _read("live/signals.py")
        warmup = int(re.search(r"^_WARMUP_BARS = (\d+)", source, re.M).group(1))
        self.assertIn("trading_days_needed = (_WARMUP_BARS // 6) + 10", source)
        self.assertIn("timedelta(days=trading_days_needed * 2)", source)
        span = ((warmup // 6) + 10) * 2
        self.assertLess(
            span, CHUNK_THRESHOLD_DAYS,
            "the live fetch window grew to {} days, past F12's {}-day threshold — the "
            "live bot may now be receiving morning-only data, which would invert the "
            "backtest<->live asymmetry F12 and F13 describe".format(
                span, CHUNK_THRESHOLD_DAYS))
        self.assertGreater(span, 40, "the window shrank below the warm-up it needs")


if __name__ == "__main__":
    unittest.main()
