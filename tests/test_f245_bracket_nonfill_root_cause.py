"""H33 root-caused from committed data — two failure modes, not one — F245.

H33 asks why IBKR paper brackets fill unreliably, and prescribes running
`tools/diagnose_brackets.py` against a live gateway plus TWS/IBC logs. No gateway is
reachable here. It did not need one: `data/live_runs/archive_2026-06-18_pre_clean_run/`
is a committed export of a 12-week live paper run — 149 monitor events, 65 trades — and
it already contains the evidence.

**The run had TWO independent failure modes, and H33 conflates them.**

1. **IBKR connectivity** — 46 of the 55 logged cycle errors (84%) are
   `ConnectionRefusedError` / `Connect call failed`, spread over **9 distinct days**
   between 2026-04-03 and 2026-05-27. This is the dominant live-ops failure by volume and
   it is not a bracket problem at all.

2. **Bracket non-execution** — 6 CRITICAL events, all of the form
   `SOFTWARE STOP triggered: mark=X breached stop=Y but IBKR bracket did not execute`,
   on 4 days in a 10-day May window.

**They are independent, and that is the finding.** If the brackets only "failed" while the
bot was disconnected, the natural reading would be that they *did* execute and the bot
could not see it. They do not: **3 of the 4** bracket-non-execution days (05-12, 05-18,
05-21) carry no connection error at all. The bot was connected, the price breached the
stop, and the bracket did not fire.

**Magnitude.** The breaches run 0.11% to 2.38% past the stop, and the realised returns on
those six trades range −0.52% to −3.08% against a configured 0.50% stop — the worst is
**6.2x the intended loss**. The software net caught them, which is why the run survived,
but it caught them late.

**What this narrows, and what it does not.** Entries filled normally throughout, so
submission works and the bracket was accepted; the order existed and did not trigger. That
rules out submission failure. It does *not* separate OCA-group handling from `tif` from
paper-engine non-execution — that still needs TWS/IBC logs, and H33 stays open for exactly
that question, now with a much smaller one to answer.

**A provenance cost nobody had counted.** 14 of 65 trades (21.5%) carry a return that was
never read from a real fill: 6 `target_hit` inferred from the TP price (all six recorded at
exactly +1.00%), 6 `stop_hit` from the software net, and 2 `estimated_close` force-finalised
after fill data never arrived. Any live-vs-backtest comparison drawn from this record is
comparing against a fifth-part-synthetic sample, and the synthetic part is biased: the
inferred exits sit exactly on the target while the software stops sit far past the stop.

**A third defect, historical.** 8 cycle errors on one day (2026-03-30) are
`Position.__init__() got an unexpected keyword argument 'pending_close_retries'` — a
migration that ran before the code that reads it. `live/state.py:183` now declares the
field and `:148` carries the migration, so it is fixed; it is recorded because it fired in
the very retry path meant to recover from missing fills.

Guards are bidirectional throughout: they fail if the archive stops witnessing either mode,
if the two modes start coinciding (which would make connectivity the explanation after
all), if the worst breach narrows, or if the synthetic share of the trade record changes.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"


def _events():
    rows = [json.loads(l) for l in
            (RUN / "monitor_events.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    rows.sort(key=lambda e: e["event_time"])
    return rows


def _trades():
    return [json.loads(l) for l in
            (RUN / "trades.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def _is_connection_error(msg):
    return ("ConnectionRefused" in msg or "Connect call failed" in msg
            or "TimeoutError" in msg)


class TheArchiveWitnessesBothModesTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev = _events()

    def test_the_archive_is_the_expected_shape(self):
        self.assertEqual(len(self.ev), 149, "monitor event count drifted")

    def test_connectivity_is_the_dominant_error_by_volume(self):
        errs = [e for e in self.ev if e["level"] == "ERROR"]
        conn = [e for e in errs if _is_connection_error(e["message"])]
        self.assertEqual(len(errs), 55)
        self.assertEqual(len(conn), 46)
        self.assertGreater(
            len(conn) / len(errs), 0.8,
            "connection errors are no longer the dominant failure mode — H33's root "
            "cause picture has changed")

    def test_bracket_non_execution_is_witnessed_and_distinct(self):
        crit = [e for e in self.ev if e["level"] == "CRITICAL"]
        self.assertEqual(len(crit), 6, "the count of bracket non-executions changed")
        for e in crit:
            self.assertIn("IBKR bracket did not execute", e["message"])

    def test_the_two_modes_do_not_coincide(self):
        """The load-bearing check. If they overlapped, 'the bracket did not execute'
        would more likely mean 'the bot could not see that it did'."""
        conn_days = {e["event_time"][:10] for e in self.ev
                     if e["level"] == "ERROR" and _is_connection_error(e["message"])}
        crit_days = {e["event_time"][:10] for e in self.ev if e["level"] == "CRITICAL"}
        overlap = conn_days & crit_days
        self.assertEqual(
            len(crit_days), 4, "the bracket-failure day count changed")
        self.assertLessEqual(
            len(overlap), 1,
            "bracket non-executions now coincide with connection loss on {} of {} days "
            "— connectivity may explain them after all, and F245's independence claim "
            "needs re-deriving".format(len(overlap), len(crit_days)))
        self.assertGreaterEqual(
            len(crit_days - conn_days), 3,
            "fewer than 3 bracket-failure days are free of connection errors")


class TheBreachesAreLargeTests(unittest.TestCase):

    def test_the_worst_breach_is_far_past_the_stop(self):
        worst = 0.0
        for e in _events():
            if e["level"] != "CRITICAL":
                continue
            m = re.search(r"mark=([\d.]+).*?stop=([\d.]+)", e["message"])
            if m:
                mark, stop = float(m.group(1)), float(m.group(2))
                worst = max(worst, 100 * (stop - mark) / stop)
        self.assertAlmostEqual(
            worst, 2.38, delta=0.05,
            msg="the worst recorded breach moved off 2.38% past the stop")

    def test_the_realised_stop_losses_exceed_the_configured_stop(self):
        import config
        configured = float(config.STOP_LOSS_PCT_TQQQ_HOURLY)
        rets = [t["return_pct"] for t in _trades()
                if t.get("exit_type") == "stop_hit" and t.get("return_pct") is not None]
        self.assertEqual(len(rets), 6)
        self.assertLess(
            min(rets), -configured,
            "no software-stop trade lost more than the configured stop any more — the "
            "late-catch cost F245 records has gone")
        self.assertGreater(
            abs(min(rets)) / configured, 5.0,
            "the worst software-stop loss is no longer >5x the configured stop; "
            "F245 records 6.2x")


class TheTradeRecordIsPartlySyntheticTests(unittest.TestCase):

    SYNTHETIC = ("target_hit", "stop_hit", "estimated_close")

    def test_a_fifth_of_the_record_was_never_read_from_a_fill(self):
        tr = _trades()
        synth = [t for t in tr if t.get("exit_type") in self.SYNTHETIC]
        self.assertEqual(len(tr), 65)
        self.assertEqual(
            len(synth), 14,
            "the synthetic-provenance trade count changed — re-derive the 21.5% share")

    def test_the_inferred_target_exits_sit_exactly_on_the_target(self):
        """Why the synthetic part is biased rather than merely uncertain."""
        rets = [t["return_pct"] for t in _trades() if t.get("exit_type") == "target_hit"]
        self.assertEqual(len(rets), 6)
        for r in rets:
            self.assertAlmostEqual(
                r, 0.01, delta=0.0002,
                msg="an inferred target exit no longer sits on the 1% target, so it may "
                    "be a real fill now — good news, re-derive the provenance split")

    def test_the_bulk_of_the_record_is_genuine(self):
        """Non-vacuity: 'a fifth is synthetic' only means something if the rest is not."""
        tr = _trades()
        genuine = [t for t in tr if t.get("exit_type") == "bracket_exit"]
        self.assertEqual(len(genuine), 41)
        self.assertGreater(len(genuine), len(tr) / 2)


class TheSchemaCrashIsFixedTests(unittest.TestCase):

    def test_it_fired_on_exactly_one_day(self):
        days = {e["event_time"][:10] for e in _events()
                if "pending_close_retries" in e["message"] and e["level"] == "ERROR"}
        self.assertEqual(days, {"2026-03-30"})

    def test_the_field_the_crash_wanted_now_exists(self):
        src = (ROOT / "live" / "state.py").read_text(encoding="utf-8")
        self.assertIn(
            "pending_close_retries: int = 0", src,
            "Position no longer declares pending_close_retries — the crash F245 records "
            "as fixed could recur")
        self.assertIn(
            "ADD COLUMN pending_close_retries", src,
            "the migration that pairs with the field is gone")


if __name__ == "__main__":
    unittest.main()
