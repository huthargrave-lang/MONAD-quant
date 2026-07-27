"""H32 confirmed by exhaustive search: per-trade risk is bounded, session risk is not.

H32 asks for per-day loss limits, max-consecutive-losses pauses, notional caps, circuit
breakers, a drawdown throttle and a documented kill switch, and calls it decision gate 2
for real money. A repo-wide search finds **none of them** — no `kill_switch`,
`MAX_DAILY_LOSS`, `DRAWDOWN_LIMIT`, `MAX_CONSECUTIVE`, or circuit-breaker of any kind
outside tests.

**What does exist is per-TRADE, and it is real.** Fixed 10% sizing, a 0.50% stop, a
bounded hold (`MAX_TRADE_BARS_LIVE = 10`), the reconciliation guard that refuses entry on
a broker/DB desync, the software take-profit, `TRADER_ALLOW_SHORTS = False`, and paper
mode. So each trade is capped. Nothing is capped **across** trades.

**The arithmetic that makes the gap concrete.** At the modelled stop, one trade risks
`10% × 0.50% = 0.050%` of the account. But F47 observed an overnight gap turn that same
0.50% stop into a **−4.007%** realized loss, which is `10% × 4.007% = 0.401%` of the
account — **8× the modelled figure**, and the engine has no term that can express it
(F193/F19: the stop fills at a constant, so no gap can enter it).

With ~7 hourly bars per session and no session-level limit, the worst case is bounded only
by *frequency × per-trade loss*: about 0.35%/day at the modelled stop, about **2.8%/day**
at F47's observed one. Nothing in the code stops the second day, or the tenth. That is the
shape of the gap — not "risk is unmanaged", but "risk is managed one trade at a time, and
nothing sums".

**The kill switch is `systemctl stop`, documented in one line of `ops/README.md`.** That is
a real answer to H32's J4 as far as it goes, and it is not in `OPERATIONS.md`, which is the
document the ops runbook points operators at.

Nothing here is fixed. Every control H32 asks for lives in `live/`, which is fenced, and
adding a loss limit changes when the bot refuses to trade — an owner decision, not a
research one. This records the state, the arithmetic, and what exists already, so the gate
can be argued from numbers.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

TRADER = (ROOT / "live" / "trader.py").read_text(encoding="utf-8")

RISK_TOKENS = ("kill_switch", "KILL_SWITCH", "MAX_DAILY_LOSS", "DRAWDOWN_LIMIT",
               "MAX_CONSECUTIVE", "circuit_breaker", "CIRCUIT_BREAKER",
               "MAX_NOTIONAL", "daily_loss")


# The finding ledger and the handoff docs must be able to NAME a missing control
# without the guard reading that as the control existing. Same exclusion, and same
# reason, as the branch-drift guard: F206's own text tripped this test on first run.
DESCRIBES_RATHER_THAN_IMPLEMENTS = ("tests/", "RESEARCH_WEB.md", "docs/", "IMPROVEMENT_PLAN.md")


def grep_first_party(token):
    out = subprocess.run(["git", "grep", "-l", "--", token], cwd=str(ROOT),
                         capture_output=True, text=True)
    return [f for f in out.stdout.split()
            if not f.startswith(DESCRIBES_RATHER_THAN_IMPLEMENTS)]


class NoSessionLevelRiskControlExistsTests(unittest.TestCase):
    def test_the_ledger_can_name_a_control_without_tripping_the_guard(self):
        """Non-vacuity for the exclusion above: F206 does name these tokens."""
        out = subprocess.run(["git", "grep", "-l", "--", "MAX_DAILY_LOSS"],
                             cwd=str(ROOT), capture_output=True, text=True)
        self.assertIn("RESEARCH_WEB.md", out.stdout,
                      "the ledger no longer names the missing controls, so the "
                      "exclusion is untested")

    def test_none_of_the_named_controls_appear_in_CODE(self):
        found = {t: grep_first_party(t) for t in RISK_TOKENS}
        present = {t: f for t, f in found.items() if f}
        self.assertEqual(
            present, {},
            "a session-level risk control appeared: {}. If H32's J1-J4 are landing, "
            "re-read this file and update the arithmetic below.".format(present))

    def test_the_trader_has_no_cumulative_loss_state(self):
        for token in ("cumulative", "session_loss", "losses_today", "consecutive_loss"):
            self.assertNotIn(
                token, TRADER,
                "trader.py now tracks {!r} — a session-level control may exist"
                .format(token))


class PerTradeControlsDoExistTests(unittest.TestCase):
    """The honest other half: this is not an unguarded bot."""

    def test_position_size_is_capped(self):
        self.assertAlmostEqual(config.FIXED_POSITION_PCT, 0.10, places=6)

    def test_a_stop_and_a_bounded_hold_exist(self):
        self.assertGreater(config.STOP_LOSS_PCT_TQQQ_HOURLY, 0)
        self.assertGreater(config.MAX_TRADE_BARS_LIVE, 0)

    def test_the_reconciliation_guard_refuses_entry_on_desync(self):
        self.assertIn("entry_blocked_desync", TRADER)
        self.assertIn("POSITION DESYNC", TRADER)

    def test_shorts_are_off_and_paper_mode_is_on(self):
        self.assertFalse(getattr(config, "TRADER_ALLOW_SHORTS", False))
        self.assertTrue(config.LIVE_PAPER_MODE)


class TheArithmeticOfTheGapTests(unittest.TestCase):
    """What "no session limit" costs, in account units."""

    def per_trade(self, loss_pct):
        return config.FIXED_POSITION_PCT * loss_pct

    def test_the_modelled_per_trade_risk_is_five_basis_points(self):
        self.assertAlmostEqual(
            self.per_trade(config.STOP_LOSS_PCT_TQQQ_HOURLY) * 100, 0.05, places=4)

    def test_f47s_observed_gap_is_eight_times_that(self):
        observed = self.per_trade(0.04007)
        modelled = self.per_trade(config.STOP_LOSS_PCT_TQQQ_HOURLY)
        self.assertGreater(
            observed / modelled, 7.0,
            "F47's observed loss is no longer several times the modelled stop — "
            "re-read F47 before citing the 8x")
        self.assertAlmostEqual(observed * 100, 0.4007, places=3)

    def test_a_full_session_is_unbounded_by_anything_but_frequency(self):
        """~7 hourly bars per session, no session cap."""
        bars = 7
        modelled_day = bars * self.per_trade(config.STOP_LOSS_PCT_TQQQ_HOURLY) * 100
        observed_day = bars * self.per_trade(0.04007) * 100
        self.assertAlmostEqual(modelled_day, 0.35, places=2)
        self.assertGreater(
            observed_day, 2.5,
            "the observed-gap day figure fell below 2.5% — recompute before citing 2.8%")

    def test_the_engine_cannot_model_the_gap_at_all(self):
        """Which is why the modelled day figure is the optimistic one (F19/F193)."""
        engine = (ROOT / "src" / "strategy" / "engine.py").read_text(encoding="utf-8")
        self.assertIn("exit_return = -stop - stop_slippage_pct", engine,
                      "the stop fill is no longer a constant — gap modelling may exist, "
                      "which would change the arithmetic above")


class TheKillSwitchIsOneLineInTheWrongDocTests(unittest.TestCase):
    def test_ops_readme_documents_stopping_the_service(self):
        readme = (ROOT / "ops" / "README.md").read_text(encoding="utf-8")
        self.assertIn("systemctl stop monad-trader.service", readme,
                      "the documented stop command vanished — H32's J4 would have no "
                      "answer at all")

    def test_the_main_operations_runbook_does_not(self):
        ops = (ROOT / "OPERATIONS.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "systemctl stop monad-trader", ops,
            "OPERATIONS.md now documents the stop command too — that closes the "
            "discoverability half of J4; update this test")

    def test_no_in_process_kill_switch_exists(self):
        """A file/flag the trader itself checks, which is what J4 asks for."""
        self.assertNotIn("HALT", TRADER)
        self.assertNotIn("kill", TRADER.lower().replace("killed", ""))


if __name__ == "__main__":
    unittest.main()
