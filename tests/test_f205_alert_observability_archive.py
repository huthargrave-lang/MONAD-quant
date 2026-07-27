"""F205's unobservable-alerting claim, confirmed against the committed archive.

F205 established from CODE that all four CRITICAL events page Slack, that the escalation
passes a computed level, and that nobody can tell whether any of it lands — `_post` returns
silently when `SLACK_WEBHOOK_URL` is empty, and neither the preflight nor the startup banner
reports that state.

This file is the EMPIRICAL half. A near-duplicate finding was drafted here and withdrawn
once `ctx`'s similarity advisory flagged it against F205 (cos 0.64) — F205 said all of it
first, and better. What was genuinely additive is kept:

* the unconfigured `_post` emits **nothing at all** — measured, not inferred, by capturing
  the module's logger while calling it with an empty webhook;
* `_should_send` records the dedupe key **regardless of delivery**, so a suppressed alert
  and a delivered one leave identical state;
* the committed 12-week archive holds **0 of 149** monitor events mentioning an alert or
  Slack — F205's argument, confirmed on real logged data rather than from source;
* and the concrete consequence, which postdates F205: the **six** CRITICAL
  bracket-non-execution events F245 found have no delivery evidence anywhere.

The wiring half is guarded too, including the correction that cost this audit a pass — an
AST check reading only `ast.Constant` keyword values reported the signal-failure escalation
as hardcoded ERROR, when it passes a computed `level`. F205 records two intermediate reads
that were wrong for related reasons; this is a third, and the guard pins the shape so a
fourth reader does not repeat it.

Nothing in `live/**` is modified; this reads and measures.

Guards are bidirectional: they fail if CRITICAL coverage regresses, if the escalation stops
passing a computed level, and — the good-news direction — if an unconfigured alert ever logs
something, if dedupe stops recording undeliverable keys, or if the durable record ever
mentions alerting. Any of those would close H31 and mean F205 should be superseded.
"""
import ast
import io
import json
import logging
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRADER = ROOT / "live" / "trader.py"
EVENTS = (ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"
          / "monitor_events.jsonl")


def _calls(tree, name):
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            got = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if got == name:
                out.append(node)
    return out


class TheAlertingIsWiredTests(unittest.TestCase):
    """The half H31 assumed was missing."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(TRADER.read_text(encoding="utf-8"))

    def test_every_critical_monitor_event_has_an_alert_nearby(self):
        crit = [c.lineno for c in _calls(self.tree, "add_monitor_event")
                if c.args and isinstance(c.args[0], ast.Constant)
                and c.args[0].value == "CRITICAL"]
        self.assertGreaterEqual(len(crit), 4, "CRITICAL event sites disappeared")
        alert_lines = [c.lineno for c in _calls(self.tree, "alert_error")]
        for ln in crit:
            with self.subTest(line=ln):
                self.assertTrue(
                    any(abs(a - ln) <= 40 for a in alert_lines),
                    "the CRITICAL monitor event at line {} has no alert_error within "
                    "40 lines — external alerting regressed".format(ln))

    def test_the_signal_failure_escalation_passes_a_computed_level(self):
        """Non-vacuity for the correction in this file's docstring: the level must be a
        NAME (computed), not a hardcoded constant."""
        computed = []
        for call in _calls(self.tree, "alert_error"):
            for kw in call.keywords:
                if kw.arg == "level" and isinstance(kw.value, ast.Name):
                    computed.append(call.lineno)
        self.assertTrue(
            computed,
            "no alert_error passes a computed level any more — the ERROR-to-CRITICAL "
            "escalation on repeated signal failures is gone")

    def test_some_alerts_are_explicitly_critical(self):
        levels = [kw.value.value for c in _calls(self.tree, "alert_error")
                  for kw in c.keywords
                  if kw.arg == "level" and isinstance(kw.value, ast.Constant)]
        self.assertIn("CRITICAL", levels)


class TheAlertingIsUnobservableTests(unittest.TestCase):
    """The half that is actually open."""

    def _module(self, webhook=""):
        import importlib
        import live.alerts as al
        al = importlib.reload(al)
        al._WEBHOOK_URL = webhook
        al._recent.clear()
        return al

    def test_an_unconfigured_post_emits_nothing_at_all(self):
        al = self._module(webhook="")
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        logger = logging.getLogger(al.__name__)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            al._post("CRITICAL: software stop triggered")
        finally:
            logger.removeHandler(handler)
        self.assertEqual(
            buf.getvalue(), "",
            "an unconfigured alert now logs something — that is a durable-trace "
            "improvement; supersede F265 rather than retune it")

    def test_the_dedupe_key_is_recorded_regardless_of_delivery(self):
        """So a suppressed alert and a delivered one leave identical state."""
        al = self._module(webhook="")
        self.assertTrue(al._should_send("error-x"))
        self.assertFalse(
            al._should_send("error-x"),
            "dedupe no longer records keys when delivery is impossible")

    def test_the_archive_holds_no_evidence_that_any_alert_fired(self):
        events = [json.loads(l) for l in
                  EVENTS.read_text(encoding="utf-8").splitlines() if l.strip()]
        mentions = [e for e in events
                    if "alert" in e["message"].lower() or "slack" in e["message"].lower()]
        self.assertEqual(
            mentions, [],
            "the durable record now mentions alerting — H31's observability gap may be "
            "closed; supersede F265")
        self.assertGreater(len(events), 100,
                           "non-vacuity: the event log must be populated for its silence "
                           "about alerts to mean anything")

    def test_the_critical_events_that_would_have_alerted_are_present(self):
        """Ties the gap to a concrete consequence: six real CRITICAL events, and no way
        to know whether anyone saw them."""
        events = [json.loads(l) for l in
                  EVENTS.read_text(encoding="utf-8").splitlines() if l.strip()]
        crit = [e for e in events if e["level"] == "CRITICAL"]
        self.assertEqual(len(crit), 6)
        for e in crit:
            self.assertIn("IBKR bracket did not execute", e["message"])


if __name__ == "__main__":
    unittest.main()
