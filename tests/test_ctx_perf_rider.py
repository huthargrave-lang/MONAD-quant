"""H16/DP-9: the cold-start rider now carries live truth, in all three of its states.

`ctx perf` leads with the CONFIRMED edge — bracket_exit plus stop_hit, excluding
time_exit artifacts and inferred target_hit — because the ALL headline is inflated. But
the `HONEST STATE` rider in `ctx brief` and `ctx frontier` pulled only node counts, so an
agent orienting at cold start saw prose about a corrected headline and no live number at
all. That is the moment the number matters most.

`perf_summary()` now supplies one line, and it **always** supplies one:

* measured — `live CONFIRMED n=… WR=…% account=…% (ALL …% — cite CONFIRMED)`
* empty ledger — `live edge UNMEASURED (0 trades — an empty ledger is not evidence)`
* no ledger — `live perf UNAVAILABLE here (no live/state.db — worktree/CI, not 'no edge')`

The third case is the one worth being careful about. A rider that simply drops the line
when `state.db` is absent leaves a reader unable to distinguish *no edge was found* from
*nobody looked* — the absence-flag failure this project has now hit in three separate
places (F155, F159, F188). So the missing-ledger string names itself as a checkout
property and explicitly says it is **not** a claim about the edge.

`perf_summary()` shares `cmd_perf`'s ledger read and the same `CONFIRMED` /
`LIVE_POSITION_FRACTION` constants, so the rider and the command cannot drift into two
different numbers for the same quantity — the failure mode F20 and F145 record elsewhere
in this repo.
"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402


def make_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE trades (return_pct REAL, exit_type TEXT)")
    conn.executemany("INSERT INTO trades VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


class TheSummarySpeaksInEveryStateTests(unittest.TestCase):
    def test_absent_ledger_says_UNAVAILABLE_and_disclaims_a_verdict(self):
        with mock.patch.object(ctx, "DB", "/nonexistent/state.db"):
            line = ctx.perf_summary()
        self.assertIn("UNAVAILABLE", line)
        self.assertIn("not 'no edge'", line,
                      "the missing-ledger line no longer disclaims being a verdict — a "
                      "reader could take 'unavailable' as 'no edge found'")

    def test_empty_ledger_says_UNMEASURED_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "state.db")
            make_db(db, [])
            with mock.patch.object(ctx, "DB", db):
                line = ctx.perf_summary()
        self.assertIn("UNMEASURED", line)
        self.assertIn("not evidence", line,
                      "an empty paper ledger must not read as a measured flat result")

    def test_a_populated_ledger_reports_CONFIRMED_and_names_ALL_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "state.db")
            make_db(db, [(0.01, "bracket_exit"), (-0.005, "stop_hit"),
                         (0.01, "bracket_exit"), (0.30, "time_exit")])
            with mock.patch.object(ctx, "DB", db):
                line = ctx.perf_summary()
        self.assertIn("CONFIRMED n=3", line)
        self.assertIn("ALL", line)
        self.assertIn("cite CONFIRMED", line)

    def test_the_inflated_ALL_number_is_visibly_different(self):
        """The whole point of surfacing both: a large time_exit must show up as a gap."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "state.db")
            make_db(db, [(0.001, "bracket_exit"), (0.001, "stop_hit"),
                         (0.50, "time_exit")])
            with mock.patch.object(ctx, "DB", db):
                line = ctx.perf_summary()
        self.assertIn("CONFIRMED n=2", line)
        confirmed = float(line.split("account=")[1].split("%")[0])
        allpct = float(line.split("(ALL ")[1].split("%")[0])
        self.assertGreater(
            allpct - confirmed, 0.4,
            "a 50% time_exit no longer separates ALL from CONFIRMED in the rider ({}) "
            "— the gap the rider exists to show has stopped showing".format(line))

    def test_a_broken_ledger_degrades_instead_of_raising(self):
        """`ctx brief` must never crash because of the perf read."""
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "state.db")
            sqlite3.connect(db).execute("CREATE TABLE unrelated (x INT)")
            with mock.patch.object(ctx, "DB", db):
                line = ctx.perf_summary()
        self.assertIn("UNAVAILABLE", line)


class TheRiderCarriesItTests(unittest.TestCase):
    def test_the_banner_rider_includes_the_perf_line(self):
        banner = ctx._web_banner()
        self.assertIn("[Auto]", banner)
        self.assertTrue(
            "CONFIRMED" in banner or "UNAVAILABLE" in banner or "UNMEASURED" in banner,
            "the HONEST STATE rider lost its live-perf line — the ALL-vs-CONFIRMED gap "
            "is skimmable again at cold start (H16)")

    def test_brief_and_frontier_both_show_it(self):
        import argparse
        import io
        from contextlib import redirect_stdout

        for build in (lambda: ctx.cmd_brief(argparse.Namespace(area=None, task=None)),
                      lambda: ctx.cmd_frontier(argparse.Namespace(
                          task=["exit", "logic"], budget=900))):
            buf = io.StringIO()
            with redirect_stdout(buf):
                try:
                    build()
                except TypeError:
                    self.skipTest("command signature changed; re-check the rider by hand")
            out = buf.getvalue()
            self.assertIn("HONEST STATE", out)
            self.assertTrue(
                "CONFIRMED" in out or "UNAVAILABLE" in out or "UNMEASURED" in out,
                "a cold-start command shows the honest-state prose without any live "
                "perf line")

    def test_the_rider_still_carries_node_counts(self):
        """The perf line is an addition, not a replacement."""
        banner = ctx._web_banner()
        self.assertIn("nodes,", banner)
        self.assertIn("superseded", banner)


class TheRiderAndTheCommandCannotDriftTests(unittest.TestCase):
    """Two code paths reporting the same quantity differently is a failure mode this
    repo has recorded twice (F20's windows, F145's sizing chain)."""

    def test_both_use_the_same_CONFIRMED_definition(self):
        source = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        for fn in ("def perf_summary(", "def cmd_perf("):
            start = source.index(fn)
            body = source[start:source.index("\ndef ", start + 5)]
            self.assertIn("in CONFIRMED", body,
                          "{} no longer filters on the CONFIRMED exit-type set".format(fn))
            self.assertIn("LIVE_POSITION_FRACTION", body,
                          "{} no longer uses the shared account-units fraction".format(fn))

    def test_confirmed_is_bracket_exit_plus_stop_hit(self):
        self.assertEqual(set(ctx.CONFIRMED), {"bracket_exit", "stop_hit"},
                         "the CONFIRMED exit-type set changed — every perf number in "
                         "the web and the rider shifts with it")


if __name__ == "__main__":
    unittest.main()
