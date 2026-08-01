"""H31's premise is stale — all four CRITICAL paths alert. The gap is that nobody can tell.

H31 says CRITICAL events "land in SQLite but page nobody" and calls external alerting
decision gate 2 for real money. Checking each named event corrected that twice over.

**All four are wired.** `live/alerts.py` posts to a Slack webhook, and `trader.py` calls
`alerts.alert_error(..., level="CRITICAL")` on every event H31 lists:

* force-finalize — `trader.py:381`
* N consecutive signal failures — `trader.py:315-325`, escalating ERROR → CRITICAL
* software stop — `trader.py:500`
* desync block — `trader.py:644`

(An intermediate read here concluded the software stop was unwired; the alert is further
down the same block, after the close executes. Recorded because it was wrong.)

**The real gap: whether any of it reaches a human is unobservable.** `_post` returns
immediately when `SLACK_WEBHOOK_URL` is empty — silently, by design — and *nothing
anywhere reports that state*. The preflight's ten checks say nothing about alerting. The
startup banner prints twelve config lines (symbol, mode, port, sizing, target, stop, R:R,
max bars, warmup, schedule, timezone, git hash) and not whether alerts will be delivered.
So an operator can have correct wiring, a green preflight and a full banner while every
CRITICAL is computed and discarded, and the only way to find out is to read `.env`.

For a gate labelled "gates real money", the subsystem's status being unknowable is the
defect — not the wiring. This is the **fourth** appearance of the absence-flag family
(F155, F159, F188, F204): a thing that is off looks exactly like a thing that is fine.

**Fixed as a REPORT, not a check.** `ops/preflight_trader_start.sh` now prints whether
`SLACK_WEBHOOK_URL` is set, without voting on the verdict. Promoting it to a hard check
would block arming on a missing env var — a change to when the bot may start, which is the
owner's call and not something to slip in under a research cycle. The value never touches
the log.

**Also worth knowing: `_should_send` dedupes on `message[:80]` for 300s.** Two *different*
CRITICALs sharing an 80-character prefix collide and the second is dropped. Hourly bars are
3600s apart so the ordinary cadence is unaffected; a burst inside five minutes is not.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TRADER = (ROOT / "live" / "trader.py").read_text(encoding="utf-8")
ALERTS = (ROOT / "live" / "alerts.py").read_text(encoding="utf-8")
PREFLIGHT = (ROOT / "ops" / "preflight_trader_start.sh").read_text(encoding="utf-8")


class AllFourCriticalPathsAlertTests(unittest.TestCase):
    """H31's premise, checked event by event."""

    def test_four_alert_sites_can_fire_at_CRITICAL(self):
        """Three pass the literal; the signal-failure path passes a COMPUTED level, so
        counting `level="CRITICAL"` alone undercounts — a first version of this test
        did exactly that and reported 3."""
        lines = TRADER.splitlines()
        literal, computed = 0, 0
        for i, line in enumerate(lines):
            if "alerts.alert_error(" not in line:
                continue
            call = "\n".join(lines[i:i + 8])
            if 'level="CRITICAL"' in call:
                literal += 1
            elif "level=level" in call:
                computed += 1
        self.assertEqual(
            literal, 3,
            "the count of literal-CRITICAL alert sites changed from 3")
        self.assertEqual(
            computed, 1,
            "the computed-level alert site (signal failures) changed — that path "
            "escalates to CRITICAL without naming it literally")
        self.assertEqual(literal + computed, 4,
                         "H31 names four CRITICAL events; four sites should be able "
                         "to fire at that level")

    def test_the_force_finalize_path_alerts(self):
        """Anchored on the force-finalize MESSAGE, not on `finalize_pending_close` —
        that identifier first appears in the ordinary reconcile block hundreds of lines
        earlier, which an initial version of this test matched by mistake."""
        idx = TRADER.index("Pending close force-finalized after")
        window = TRADER[idx:idx + 900]
        self.assertIn('alerts.alert_error(warning_msg, level="CRITICAL")', window,
                      "the force-finalize path no longer alerts at CRITICAL")
        self.assertIn("finalize_pending_close(", window,
                      "the alert is no longer adjacent to the finalize call")

    def test_the_software_stop_path_alerts(self):
        """The one an intermediate read got wrong — the alert is after the close."""
        idx = TRADER.index("SOFTWARE STOP triggered")
        window = TRADER[idx:idx + 2600]
        self.assertIn("SOFTWARE STOP triggered on", window,
                      "the software-stop alert message changed")
        self.assertIn('level="CRITICAL"', window,
                      "the software-stop alert is no longer CRITICAL. Note it sits "
                      "~1900 chars after the log line, AFTER the close executes — a "
                      "narrower window here reported a false negative once already.")

    def test_the_desync_block_path_alerts(self):
        idx = TRADER.index("entry_blocked_desync")
        window = TRADER[max(0, idx - 600):idx]
        self.assertIn('level="CRITICAL"', window)

    def test_consecutive_signal_failures_escalate_to_critical(self):
        self.assertIn('level = "CRITICAL" if consecutive_failures >= threshold', TRADER,
                      "the signal-failure escalation changed — H31's fourth event may "
                      "no longer reach CRITICAL")


class WhetherAnyOfItLandsIsTheRealGapTests(unittest.TestCase):
    def test_the_poster_no_ops_silently_on_an_unset_webhook(self):
        idx = ALERTS.index("def _post(")
        body = ALERTS[idx:idx + 400]
        self.assertIn("if not _WEBHOOK_URL:", body)
        self.assertIn("return", body)
        self.assertNotIn(
            "log.", body.split("return")[0],
            "_post now logs when the webhook is unset — the silent no-op this finding "
            "documents is gone")

    def test_the_startup_banner_says_nothing_about_alerting(self):
        idx = TRADER.index("Startup config:")
        banner = TRADER[idx:idx + 1400]
        self.assertIn("Git hash:", banner, "the startup banner changed shape")
        for token in ("SLACK", "alert", "webhook"):
            self.assertNotIn(
                token, banner,
                "the startup banner now mentions {!r} — if it reports alerting "
                "reachability, this finding is partly fixed there too".format(token))

    def test_the_preflight_does_not_GATE_on_alerting(self):
        """Deliberate: blocking arming on an env var is the owner's call."""
        gate_section = PREFLIGHT[:PREFLIGHT.index("# ── Alerting reachability")]
        self.assertNotIn("SLACK_WEBHOOK_URL", gate_section,
                         "an alerting check moved into the gating section — that "
                         "changes when the trader may start")


class ThePreflightNowReportsItTests(unittest.TestCase):
    """The fix: observable without changing the verdict."""

    def test_a_report_helper_exists_and_does_not_touch_the_fail_count(self):
        idx = PREFLIGHT.index("report() {")
        body = PREFLIGHT[idx:idx + 200]
        self.assertNotIn("fails=", body,
                         "report() now votes on the verdict — it must not")
        self.assertIn("INFO:", body)

    def test_both_branches_are_reported(self):
        self.assertIn("CRITICAL alerting is configured", PREFLIGHT)
        self.assertIn("CRITICAL alerting is NOT configured", PREFLIGHT)

    def test_the_unconfigured_branch_names_the_consequence(self):
        idx = PREFLIGHT.index("CRITICAL alerting is NOT configured")
        window = PREFLIGHT[idx:idx + 400]
        self.assertIn("computed", window)
        self.assertIn("discarded", window,
                      "the unconfigured report no longer says the alerts are thrown "
                      "away — that is the fact an operator needs")
        self.assertIn("still start", window,
                      "the report no longer states that it does not block arming")

    def test_the_secret_value_is_never_logged(self):
        idx = PREFLIGHT.index("CRITICAL alerting is configured")
        window = PREFLIGHT[idx:idx + 200]
        self.assertIn("value not logged", window)
        self.assertNotIn('$SLACK_WEBHOOK_URL"', window,
                         "the preflight would print the webhook URL")

    def test_the_script_still_parses(self):
        import subprocess
        proc = subprocess.run(["bash", "-n", str(ROOT / "ops" / "preflight_trader_start.sh")],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TheDedupeWindowCanCollideTests(unittest.TestCase):
    def test_dedupe_keys_on_a_truncated_message(self):
        self.assertIn('_should_send(f"error-{message[:80]}")', ALERTS,
                      "the dedupe key changed — re-check whether distinct CRITICALs "
                      "can still collide")

    def test_the_window_is_shorter_than_the_bar_cadence(self):
        """So the ordinary hourly cadence is unaffected; only bursts collapse."""
        window = int(re.search(r"_DEDUPE_WINDOW_SECS\s*=\s*(\d+)", ALERTS).group(1))
        self.assertLess(window, 3600,
                        "the dedupe window now exceeds the hourly bar interval, so a "
                        "repeated CRITICAL could be suppressed between bars")


if __name__ == "__main__":
    unittest.main()
