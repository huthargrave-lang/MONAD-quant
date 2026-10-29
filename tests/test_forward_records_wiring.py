"""deploy/monad-forward-watch.{service,timer}, deploy/monad-forward-log.{service,timer} and
ops/forward_watch_cycle.sh — the scheduler behind the forward records (docs/DIRECTIONS.md D-1;
the route ratified 2026-10-29, docs/research/FORWARD_ROUTE_PROPOSAL.md).

Three properties carry the weight:

  1. THE CADENCE MEETS THE RECORD'S DEADLINE. Session t's H366201 decision executes at
     session t+1's close (20:00 UTC) and reads only a NAV vintage fetched before then
     (src/research/forward_watch.py vintage_for). A daily weekday run after the US close
     does that; a weekend-only or morning-only schedule would lock sessions to stale
     vintages. Persistent=true because a missed evening is a session decided stale.

  2. IT COMMITS TO THE LEDGER BRANCH ONLY, OVER SSH. development is branch-protected on
     the `test` check, so the records go to `forward-ledger` (the tone ledger's pattern)
     and reach development by PR. The script must never push development.

  3. IT CANNOT AFFECT TRADING. Research only: no broker, no state.db, no live/, no
     config*, no ops/systemd/, no ordering against a trader unit, no path into
     ops/healthcheck.sh. As in tests/test_gitdrift_wiring.py the checks read what EXECUTES
     (directives and code), not the explanatory comments.
"""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DAILY_SERVICE = REPO / "deploy" / "monad-forward-watch.service"
DAILY_TIMER = REPO / "deploy" / "monad-forward-watch.timer"
WEEKLY_SERVICE = REPO / "deploy" / "monad-forward-log.service"
WEEKLY_TIMER = REPO / "deploy" / "monad-forward-log.timer"
SCRIPT = REPO / "ops" / "forward_watch_cycle.sh"
UNITS = (DAILY_SERVICE, DAILY_TIMER, WEEKLY_SERVICE, WEEKLY_TIMER)


def directives(unit_path):
    """Only `Key=Value` lines — systemd ignores everything else."""
    return [ln.strip() for ln in unit_path.read_text().splitlines() if re.match(r"^\s*[A-Za-z]+=", ln)]


def code(script_path):
    """Shell source with whole-line comments removed."""
    return "\n".join(ln for ln in script_path.read_text().splitlines() if not ln.lstrip().startswith("#"))


def on_calendar(timer_path):
    m = re.search(r"^OnCalendar=(.+)$", timer_path.read_text(), re.M)
    return m.group(1) if m else None


class UnitsExist(unittest.TestCase):
    def test_the_four_unit_files_and_the_script_are_committed(self):
        for p in UNITS + (SCRIPT,):
            self.assertTrue(p.is_file(), f"{p.relative_to(REPO)} missing")

    def test_the_services_run_the_cycle_script_in_its_two_modes(self):
        self.assertRegex(" ".join(directives(DAILY_SERVICE)), r"ExecStart=\S*ops/forward_watch_cycle\.sh daily")
        self.assertRegex(" ".join(directives(WEEKLY_SERVICE)), r"ExecStart=\S*ops/forward_watch_cycle\.sh weekly")

    def test_they_run_unprivileged_as_oneshots_on_the_ledger_worktree(self):
        for svc in (DAILY_SERVICE, WEEKLY_SERVICE):
            d = directives(svc)
            with self.subTest(unit=svc.name):
                self.assertIn("User=hudson", d)
                self.assertIn("Type=oneshot", d)
                self.assertIn("Environment=MONAD_LEDGER_HOST=pi", d)
                self.assertTrue(any(x.startswith("WorkingDirectory=") and x.endswith("MONAD-quant-forward") for x in d),
                                "the cycle must run in the dedicated ledger worktree, not the trader's checkout")


class TheCadenceMeetsTheDeadline(unittest.TestCase):
    def test_the_daily_cycle_runs_weekday_evenings_in_new_york_time(self):
        cal = on_calendar(DAILY_TIMER)
        self.assertIsNotNone(cal, "no OnCalendar in the daily timer")
        self.assertIn("Mon..Fri", cal)
        self.assertIn("America/New_York", cal, "the Pi clock is Europe/London; the close is a New York time")
        hour = int(re.search(r"\b(\d{2}):\d{2}\b", cal).group(1))
        # After the 16:00 ET close (a same-evening log reads only NAVs dated before the
        # session) and before midnight ET, so the vintage precedes the next 20:00 UTC close.
        self.assertGreaterEqual(hour, 16)
        self.assertLessEqual(hour, 23)

    def test_the_weekly_line_runs_on_the_weekend_after_fridays_navs(self):
        cal = on_calendar(WEEKLY_TIMER)
        self.assertIsNotNone(cal, "no OnCalendar in the weekly timer")
        self.assertRegex(cal, r"^(Sat|Sun)\b")
        self.assertIn("America/New_York", cal)

    def test_both_timers_catch_up_after_a_reboot(self):
        """A missed evening is one more H366201 session decided on a stale vintage."""
        for t in (DAILY_TIMER, WEEKLY_TIMER):
            with self.subTest(unit=t.name):
                self.assertIn("Persistent=true", directives(t))

    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd-analyze not installed")
    def test_the_calendar_expressions_actually_parse(self):
        for t in (DAILY_TIMER, WEEKLY_TIMER):
            cal = on_calendar(t)
            p = subprocess.run(["systemd-analyze", "calendar", cal], capture_output=True, text=True)
            with self.subTest(unit=t.name):
                self.assertEqual(p.returncode, 0, f"systemd rejects {cal!r}: {p.stderr}")


class TheScriptKeepsItsContract(unittest.TestCase):
    def test_it_parses(self):
        p = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_it_runs_the_four_record_commands_and_verifies_against_development(self):
        c = code(SCRIPT)
        for cmd in ("tools/forward_watch.py fetch H366201", "tools/forward_watch.py log H366200",
                    "tools/forward_watch.py log H366201", "tools/forward_log.py H404702"):
            self.assertIn(cmd, c)
        self.assertRegex(c, r"forward_watch\.py verify --against")

    def test_it_refuses_a_dirty_tree_and_any_branch_but_the_ledger_branch(self):
        c = code(SCRIPT)
        self.assertIn("status --porcelain", c)
        self.assertIn("forward-ledger", c)
        self.assertRegex(c, r'\[ "\$branch" = "\$LEDGER_BRANCH" \] \|\| die')

    def test_it_pushes_the_ledger_branch_over_ssh_and_never_development(self):
        c = code(SCRIPT)
        self.assertIn("git@github.com:huthargrave-lang/MONAD-quant.git", c)
        self.assertRegex(c, r'push[^\n]*"HEAD:refs/heads/\$LEDGER_BRANCH"')
        self.assertIsNone(re.search(r"push[^\n]*\b(development|main)\b", c),
                          "development is branch-protected and reached only by PR; main is never pushed")
        self.assertIn("BatchMode=yes", c)
        self.assertIn("GIT_TERMINAL_PROMPT=0", c)

    def test_it_cannot_reach_trading(self):
        c = code(SCRIPT)
        for forbidden in ("ops/systemd", "state.db", "live/", "config.py", "healthcheck", "7497", "7496"):
            self.assertNotIn(forbidden, c, f"{forbidden!r} has no business in a research record cycle")
        for svc in (DAILY_SERVICE, WEEKLY_SERVICE):
            joined = " ".join(directives(svc))
            for forbidden in ("monad-trader", "BindsTo=", "Requires=", "PartOf=", "healthcheck"):
                self.assertNotIn(forbidden, joined, f"{forbidden} couples {svc.name} to the trader")


if __name__ == "__main__":
    unittest.main()
