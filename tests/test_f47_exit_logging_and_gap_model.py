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

**Claim 1 was measured under engine v2 and is false under ENGINE_VERSION 3**
(docs/research/ENGINE_V3_QUESTION.md, rule (b)). v3 checks each later bar's OPEN first:
an open at or through the stop fills at that open less ``stop_slippage_pct``
(``gap_stop``), so a session-boundary gap is now booked where the market opened. Only a
stop touched INSIDE a bar is still the constant ``-stop - stop_slippage_pct``. What v3
still cannot see is a move inside the first minutes of a bar (hourly OHLC), and live
fills a stop as a market order after the trigger, which ``stop_slippage_pct`` (measured
from archived live stop exits) is there to cover. The Claim-1 tests below are re-pinned
to the v3 fact. Claim 2 is about the live archive and is unaffected.
"""
import ast
import json
import collections
import re
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategy.engine import compute_trade_returns  # noqa: E402
from tests._engine_uncounted import uncounted_module  # noqa: E402

# Claim 1 probes compute_trade_returns on hand-built bars: engine arithmetic, not a
# strategy evaluation, so it runs outside the trial ledger (src/strategy/counted.py).
setUpModule, tearDownModule = uncounted_module("F47 claim 1: the stop fill model on hand-built bars")

ENGINE = ROOT / "src" / "strategy" / "engine.py"
ARCHIVE = ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"


FLAT = (100.0, 100.1, 99.9, 100.0)


def _stop_trade(third_bar, stop_slippage_pct=0.0):
    """A long signalled on bar 0, filled at bar 1's open (100), 0.5% stop at 99.5."""
    rows = [FLAT, FLAT, third_bar, FLAT, FLAT, FLAT]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                      index=pd.date_range("2026-03-02 14:30", periods=len(rows), freq="h"))
    df["entry_signal"] = [1, 0, 0, 0, 0, 0]
    res = compute_trade_returns(df, target_gain_pct=0.01, stop_loss_pct=0.005,
                                max_trade_bars=3, stop_slippage_pct=stop_slippage_pct)
    return res.iloc[0]["exit_type"], float(res.iloc[0]["return"])


class TheStopFillNowModelsAGapAtTheOpenTests(unittest.TestCase):
    """Claim 1 — measured under engine v2 as "the model cannot express a gap through
    the stop". Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md):
    the class was StopFillIsModelledAsExactTests, a name that is now false."""

    def test_an_in_bar_stop_is_a_constant_but_a_gapped_open_is_priced_at_the_open(self):
        """Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): v2 filled
        every stop at the constant ``-stop - stop_slippage_pct``. v3 keeps that constant
        only for a stop touched inside a bar; an open through the stop fills at the open
        less stop_slippage_pct (gap_stop). Renamed from
        test_the_stop_return_is_a_constant_not_a_price_lookup, now false.
        """
        et, r = _stop_trade((100.0, 100.1, 99.0, 99.2), stop_slippage_pct=0.001)
        self.assertEqual(et, "stop_hit")
        self.assertAlmostEqual(r, -0.005 - 0.001, places=12)
        # F47's own event, in miniature: an overnight gap to -4.007% through a 0.5% stop
        et, r = _stop_trade((95.993, 96.2, 95.8, 96.0), stop_slippage_pct=0.001)
        self.assertEqual(et, "gap_stop")
        self.assertAlmostEqual(r, -0.04007 - 0.001, places=12,
                               msg="a gap through the stop is no longer booked at the open "
                                   "— F47's original claim 1 would be true again")

    def test_the_gap_stop_branch_consults_the_open_price(self):
        """A gap-aware model has to look at the bar's OPEN, and v3's does.

        Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md). The v2
        version (test_no_open_price_is_consulted_on_the_stop_branch) looked for a Name
        ``open_``, which no identifier in the engine can equal (the array is
        ``open_arr``), so it passed vacuously; its claim is now false as well. This
        version matches the real identifier and also checks the behaviour: the booked
        loss grows with the depth of the gap.
        """
        tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "compute_trade_returns")
        reads_open = [
            n for n in ast.walk(fn)
            if isinstance(n, ast.Assign)
            and any(getattr(t, "id", "") == "exit_return" for t in n.targets)
            and isinstance(n.value, ast.BinOp)
            and "stop_slippage_pct" in {getattr(x, "id", "") for x in ast.walk(n.value)}
            and "open_arr" in {getattr(x, "id", "") for x in ast.walk(n.value)}
        ]
        self.assertTrue(reads_open,
                        "no stop-side exit_return reads open_arr — gap modelling is gone")
        _, shallow = _stop_trade((99.0, 99.1, 98.9, 99.0))
        _, deep = _stop_trade((90.0, 90.1, 89.9, 90.0))
        self.assertAlmostEqual(shallow, -0.01, places=12)
        self.assertAlmostEqual(deep, -0.10, places=12)

    def test_F47s_observed_gap_loss_was_over_8x_the_configured_stop(self):
        """Not a magnitude claim about markets — F47's own observation, a 0.5% stop
        realised at -4.007%.

        Measured under engine v2, where the model had no term that could grow with the
        gap, so the backtest understated this loss without bound. Re-pinned for
        ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): v3 books a gap at the open
        (test above), so the understatement is no longer unbounded; the test is renamed
        from test_the_understatement_is_arithmetically_unbounded and keeps only the
        arithmetic of F47's observation."""
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
