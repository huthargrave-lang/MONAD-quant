"""F47's two checkable claims: the stop fill model, and the silent exit path.

F47 is a direct live observation — an overnight gap turned a 0.5% stop into a −4.007%
realized loss — and it makes two subsidiary claims that ARE decidable offline. It also
ends with an open parenthetical: *"exit events may only fire on the
fill-data-unavailable path?"* That question is answerable from the committed archive,
and the answer is yes.

**1. The backtest cannot model a gap through the stop.** `compute_trade_returns` fills
every stop at exactly `-stop - stop_slippage_pct`, so a session-boundary gap is booked
at the configured stop regardless of where the market actually opened. Live tail risk
on a 3x ETF is therefore understated by construction, not by parameter choice.

**2. Healthy exits emit no monitor event.** In the one committed live run: 72
"Entry placed" events against 65 ledger trades, but the only exit-shaped events are
degraded paths — `Fill data unavailable`, `SOFTWARE STOP triggered`,
`Time-exit fill unavailable`. All 41 `bracket_exit` trades logged nothing.

That second point has a consequence worth stating: **`monitor_events` cannot be used
to audit exits.** Anyone reading it would conclude the bot exits only abnormally,
because the normal path is invisible. It is an exception log wearing the name of an
event log.
"""
import ast
import json
import collections
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "strategy" / "engine.py"
ARCHIVE = ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"


class StopFillIsModelledAsExactTests(unittest.TestCase):
    """Claim 1 — the model cannot express a gap through the stop."""

    def test_the_stop_return_is_a_constant_not_a_price_lookup(self):
        """`-stop - stop_slippage_pct` uses no bar data, so no gap can enter it."""
        source = ENGINE.read_text(encoding="utf-8")
        self.assertIn(
            "exit_return = -stop - stop_slippage_pct", source,
            "the stop fill is no longer a constant expression — if it now reads a "
            "bar price, gaps may be modelled and F47's backtest claim is stale. "
            "Re-verify F47 rather than editing this test.")

    def test_no_open_price_is_consulted_on_the_stop_branch(self):
        """A gap-aware model would have to look at the next bar's OPEN."""
        tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "compute_trade_returns")
        stop_assigns = [
            n for n in ast.walk(fn)
            if isinstance(n, ast.Assign)
            and any(getattr(t, "id", "") == "exit_return" for t in n.targets)
            and isinstance(n.value, ast.BinOp)
        ]
        self.assertTrue(stop_assigns, "no constant exit_return assignment found")
        for node in stop_assigns:
            names = {getattr(x, "id", "") for x in ast.walk(node.value)
                     if isinstance(x, ast.Name)}
            self.assertNotIn(
                "open_", names,
                "the stop branch now consults an open price — gap modelling may exist")

    def test_the_understatement_is_arithmetically_unbounded(self):
        """Not a magnitude claim about markets — just that the model has no term
        that can grow with the gap, so the error is bounded only by the gap itself."""
        configured_stop = 0.005
        realized = 0.04007          # F47's observed loss
        self.assertGreater(
            realized / configured_stop, 8.0,
            "F47's own numbers no longer show an 8x understatement — re-read it")


class HealthyExitsAreSilentTests(unittest.TestCase):
    """Claim 2 — answers F47's open parenthetical from committed data."""

    @classmethod
    def setUpClass(cls):
        if not ARCHIVE.exists():
            raise unittest.SkipTest("live-run archive not present")
        cls.events = [json.loads(l) for l in
                      (ARCHIVE / "monitor_events.jsonl").read_text(
                          encoding="utf-8").splitlines() if l.strip()]
        cls.trades = [json.loads(l) for l in
                      (ARCHIVE / "trades.jsonl").read_text(
                          encoding="utf-8").splitlines() if l.strip()]
        cls.messages = [str(e.get("message", "")) for e in cls.events]

    def test_entries_are_logged_roughly_one_per_trade(self):
        entries = sum(1 for m in self.messages if m.startswith("Entry placed"))
        self.assertGreaterEqual(
            entries, len(self.trades) * 0.9,
            "entries are no longer logged per trade — the asymmetry below loses its "
            "baseline")

    def test_bracket_exits_are_the_plurality_of_trades(self):
        kinds = collections.Counter(t.get("exit_type") for t in self.trades)
        self.assertGreater(
            kinds.get("bracket_exit", 0), 20,
            "bracket_exit is no longer the dominant exit path in the archive")

    def test_only_DEGRADED_exit_paths_emit_events(self):
        """F47 asked whether exits fire only on the fill-data-unavailable path. They
        do: every exit-shaped message names a degraded condition."""
        exitish = [m for m in self.messages
                   if re.search(r"\b(exit|stop|target|close)\b", m, re.I)]
        degraded = [m for m in exitish
                    if re.search(r"unavailable|SOFTWARE STOP|force-finalized|"
                                 r"pending_clos|reconciliation", m, re.I)]
        self.assertTrue(exitish, "no exit-shaped events at all")
        self.assertEqual(
            len(degraded), len(exitish),
            "an exit event now fires on a HEALTHY path ({}). That is an improvement "
            "-- monitor_events may now be usable to audit exits -- but it means F47's "
            "parenthetical is answered differently; update it.".format(
                [m for m in exitish if m not in degraded][:2]))

    def test_the_event_log_is_dominated_by_entries_and_exceptions(self):
        """The shape that makes it an exception log rather than an event log."""
        entries = sum(1 for m in self.messages if m.startswith("Entry placed"))
        exceptions = sum(1 for m in self.messages
                         if "Unhandled on_bar exception" in m)
        self.assertGreater(
            entries + exceptions, len(self.messages) * 0.7,
            "monitor_events is no longer dominated by entries plus exceptions — its "
            "character changed; re-read before citing this shape")
        self.assertGreater(
            exceptions, 20,
            "the archive's unhandled-exception count dropped — worth noting, since "
            "lost cycles silently extend live holds (F157)")


if __name__ == "__main__":
    unittest.main()
