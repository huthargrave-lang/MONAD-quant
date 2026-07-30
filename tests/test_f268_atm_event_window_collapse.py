"""The ATM pilot measured one date, not nineteen events — F268.

`DI-01` reports a 424B5 at-the-market price pilot whose summary reads
`median_xs_20d: -0.2155`, `frac_negative_xs_10d: 0.6842` — a −21.6% median excess return
with 17 of 19 names negative. That looks like a strong post-filing drift.

**It is one market draw wearing nineteen hats.**

    19 rows
    19 distinct file_date   2024-01-11 .. 2024-03-28
     1 distinct entry_date  2024-07-25          <- every row
     1 distinct spy_10d     -0.0367             <- every row
     1 distinct spy_20d     +0.0413             <- every row

Every "event" return is measured from the same calendar date, four to six months after the
filing it is supposed to follow. The number describes how nineteen microcaps moved in the
ten and twenty days after 25 July 2024. It is not an event study, so it says nothing about
424B5 filings — and because all nineteen share one entry date and one benchmark, the
effective sample size is **1**, the extreme case of F267's correlation problem.

**The mechanism.** `forward_window` scanned for the first day `> file_date`::

    for i, day in enumerate(days):
        if day > file_date:
            start_idx = i
            break

When the price series *starts after* the event — which it does, because the chart bundle
covers only a recent window — `days[0]` already satisfies that test. So "the day after the
event" silently became "the first bar I have", identical for every ticker fetched over the
same range. It returned a well-formed pair rather than refusing, and a well-formed pair is
indistinguishable from a real one at every downstream call site.

**The caveats do not cover it.** The artifact is labelled `descriptive_only: true` and warns
"phrase hit != ATM takedown; capped newest-biased slice; microcaps dominate; no costs".
Every one of those is a *sample-selection* caveat. None says the measurement is not aligned
to the event. A reader who accepted all four would still misread the number — which is the
recurring shape on this branch: the stated limitation and the actual limitation differ.

**Fixed** by requiring the series to cover the event (`file_date < days[0]` → refuse). The
committed artifact is left as it is; regenerating it needs SEC and Yahoo, both blocked here.

Guards are bidirectional: they fail if the window stops refusing an event that predates its
data, if it starts refusing a legitimate in-series event, and — the good-news direction — if
the committed artifact ever gains more than one distinct entry date, which would mean it was
regenerated and this node should be superseded.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import atm_424b5_lab as lab  # noqa: E402

ARTIFACT = ROOT / "docs" / "research" / "data" / "atm_424b5_discovery.json"
SERIES = ["2024-07-25", "2024-07-26", "2024-07-29", "2024-07-30",
          "2024-07-31", "2024-08-01", "2024-08-02"]


def _rows():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))["price_pilot"]["rows"]


class TheCommittedPilotCollapsedToOneDateTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()

    def test_every_row_shares_one_entry_date(self):
        entries = {r["entry_date"] for r in self.rows}
        self.assertEqual(
            entries, {"2024-07-25"},
            "the artifact now has more than one entry date — it was regenerated, so "
            "supersede F268 rather than editing this")

    def test_the_file_dates_are_all_different_and_months_earlier(self):
        """Non-vacuity: one entry date only matters because the events differ."""
        files = sorted({r["file_date"] for r in self.rows})
        self.assertEqual(len(files), len(self.rows))
        self.assertEqual(files[0], "2024-01-11")
        self.assertEqual(files[-1], "2024-03-28")
        self.assertTrue(all(f < "2024-07-25" for f in files),
                        "some filing is no longer months before the entry date")

    def test_the_benchmark_is_also_a_single_draw(self):
        self.assertEqual({r["spy_10d"] for r in self.rows}, {-0.0367})
        self.assertEqual({r["spy_20d"] for r in self.rows}, {0.0413})

    def test_the_headline_numbers_rest_on_that_single_draw(self):
        """Recorded so the size of what is invalidated is explicit."""
        summary = json.loads(ARTIFACT.read_text(encoding="utf-8"))["price_pilot"]["summary"]
        self.assertAlmostEqual(summary["median_xs_20d"], -0.2155, places=4)
        self.assertAlmostEqual(summary["frac_negative_xs_10d"], 0.6842, places=4)
        self.assertEqual(summary["n_events_with_price"], 19)

    def test_the_stated_caveats_do_not_mention_the_alignment(self):
        """The point: accepting every caveat still leaves the number misread."""
        summary = json.loads(ARTIFACT.read_text(encoding="utf-8"))["price_pilot"]["summary"]
        caveat = summary["caveat"].lower()
        self.assertTrue(summary["descriptive_only"])
        for word in ("entry", "align", "event date", "window"):
            self.assertNotIn(
                word, caveat,
                "the caveat now mentions {!r} — if alignment is disclosed, F268's "
                "'the caveats do not cover it' claim is stale".format(word))


class TheWindowNowRefusesWhatItCannotMeasureTests(unittest.TestCase):

    def test_an_event_before_the_series_is_refused(self):
        self.assertIsNone(
            lab.forward_window(SERIES, "2024-03-01", 3),
            "an event predating the price series still yields a window — the collapse "
            "that produced the committed pilot can recur")

    def test_an_event_inside_the_series_still_works(self):
        """Non-vacuity: a check that refuses everything is not a check."""
        got = lab.forward_window(SERIES, "2024-07-26", 3)
        self.assertEqual(got, ("2024-07-29", "2024-07-31"))

    def test_an_event_on_the_first_bar_is_allowed(self):
        """The boundary. The series does cover it, so it is measurable."""
        self.assertEqual(lab.forward_window(SERIES, "2024-07-25", 3),
                         ("2024-07-26", "2024-07-30"))

    def test_an_event_after_the_series_is_refused(self):
        self.assertIsNone(lab.forward_window(SERIES, "2024-12-01", 3))

    def test_an_empty_series_is_refused(self):
        self.assertIsNone(lab.forward_window([], "2024-07-26", 3))

    def test_a_horizon_running_past_the_end_is_refused(self):
        self.assertIsNone(lab.forward_window(SERIES, "2024-07-30", 99))

    def test_distinct_events_now_produce_distinct_windows(self):
        """The property whose absence was the whole defect."""
        a = lab.forward_window(SERIES, "2024-07-25", 2)
        b = lab.forward_window(SERIES, "2024-07-29", 2)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
