"""deploy/monad-gitdrift.{service,timer} — the scheduler behind the drift oracle.

The oracle in ops/git_drift.sh was correct and inert: nothing fetched, so the
verdict sat at UNKNOWN between manual runs, and an always-UNKNOWN alarm gets
habituated to exactly as the old silent `clean=yes` did. These pin the wiring.

Two properties carry the weight:

  1. IT RUNS 24/7, not market hours. The obvious cheaper wiring is to hang the
     fetch off monad-healthcheck.timer, which already exists — but that runs
     Mon..Fri 09..16:00 ET. The 129-commit divergence accumulated over seven days
     and was found on a Saturday; it is created by agent sessions, which run
     whenever someone is working. A market-hours-only check would have been blind
     for the entire window in which the drift appeared.

  2. IT CANNOT AFFECT ARMING. Drift is a fact to report, never a reason the bot
     refuses to trade. The unit must not order against the trader, consume its
     state, or route into healthcheck's warn logic — whose `problems` field feeds
     preflight check 10, whose failure stops both cold-start paths.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERVICE = REPO / "deploy" / "monad-gitdrift.service"
TIMER = REPO / "deploy" / "monad-gitdrift.timer"


class UnitsExist(unittest.TestCase):
    def test_both_unit_files_are_committed(self):
        self.assertTrue(SERVICE.is_file(), "service template missing from deploy/")
        self.assertTrue(TIMER.is_file(), "timer template missing from deploy/")

    def test_the_service_runs_the_two_oracle_scripts(self):
        src = SERVICE.read_text()
        self.assertIn("ops/fetch_origin.sh", src)
        self.assertIn("ops/git_drift.sh", src)

    def test_it_runs_unprivileged(self):
        self.assertIn("User=hudson", SERVICE.read_text())


class ItRunsAroundTheClock(unittest.TestCase):
    def test_the_schedule_is_not_market_hours(self):
        cal = re.search(r"^OnCalendar=(.+)$", TIMER.read_text(), re.M)
        self.assertIsNotNone(cal, "no OnCalendar in the timer")
        spec = cal.group(1)
        self.assertNotIn("Mon..Fri", spec,
                         "drift is not a market-hours concern — the 129-commit "
                         "divergence was created and found outside market hours")
        self.assertNotRegex(spec, r"\b09\.\.16\b")

    def test_the_calendar_expression_actually_parses(self):
        cal = re.search(r"^OnCalendar=(.+)$", TIMER.read_text(), re.M).group(1)
        p = subprocess.run(["systemd-analyze", "calendar", cal],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, f"systemd rejects {cal!r}: {p.stderr}")

    def test_the_cadence_leaves_headroom_under_the_staleness_threshold(self):
        """A transient network failure must not flip the banner to UNKNOWN. The
        oracle's default staleness bound is 5400s; the timer should fire several
        times inside it."""
        cal = re.search(r"^OnCalendar=(.+)$", TIMER.read_text(), re.M).group(1)
        step = re.search(r"/(\d+)", cal)
        self.assertIsNotNone(step, f"cannot read a step from {cal!r}")
        period_s = int(step.group(1)) * 60
        default_max_age = 5400
        self.assertGreaterEqual(default_max_age // period_s, 3,
                                "too few retries before the verdict goes UNKNOWN")

    def test_it_catches_up_after_a_reboot(self):
        """A stale verdict right after a power loss is when the checkout is most
        likely to be wrong."""
        self.assertIn("Persistent=true", TIMER.read_text())


class ItCannotAffectArming(unittest.TestCase):
    """These assert on what EXECUTES, not on what the file says.

    A first pass matched raw file text and failed on its own explanatory comments —
    the service comment names monad-trader.service precisely to say it is NOT
    coupled to it. A guard that reads prose can be satisfied by deleting a comment
    and defeated by writing one, so both helpers strip to directives/code first.
    """

    @staticmethod
    def _directives(unit_path):
        """Only `Key=Value` lines — systemd ignores everything else."""
        return [ln.strip() for ln in unit_path.read_text().splitlines()
                if re.match(r"^\s*[A-Za-z]+=", ln)]

    @staticmethod
    def _code(script_path):
        """Shell source with whole-line comments removed."""
        return "\n".join(ln for ln in script_path.read_text().splitlines()
                          if not ln.lstrip().startswith("#"))

    def test_it_does_not_order_against_the_trader(self):
        joined = " ".join(self._directives(SERVICE))
        for forbidden in ("monad-trader", "BindsTo=", "Requires=", "PartOf="):
            self.assertNotIn(forbidden, joined,
                             f"{forbidden} couples the drift probe to the trader")

    def test_it_does_not_write_the_healthcheck_artifact(self):
        """healthcheck.json's `problems` feeds preflight check 10, which stops both
        cold-start paths. Drift must never reach it."""
        joined = " ".join(self._directives(SERVICE))
        self.assertNotIn("healthcheck", joined)

    def test_the_scripts_it_runs_exit_zero_unconditionally(self):
        for name in ("fetch_origin.sh", "git_drift.sh"):
            code = self._code(REPO / "ops" / name)
            with self.subTest(script=name):
                self.assertIn("exit 0", code)
                self.assertNotIn("exit 1", code)

    def test_neither_script_touches_state_or_orders(self):
        for name in ("fetch_origin.sh", "git_drift.sh"):
            code = self._code(REPO / "ops" / name)
            with self.subTest(script=name):
                for forbidden in ("state.db", "systemctl start", "ib_insync", "7497"):
                    self.assertNotIn(forbidden, code)

    def test_the_service_writes_only_its_own_log(self):
        src = SERVICE.read_text()
        outs = re.findall(r"^Standard(?:Output|Error)=append:(.+)$", src, re.M)
        self.assertTrue(outs)
        for path in outs:
            self.assertTrue(path.endswith("git_drift.log"), f"unexpected sink: {path}")


if __name__ == "__main__":
    unittest.main()
