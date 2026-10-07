"""`config.py:120` promises a live opposing-signal exit that does not exist.

The comment above `USE_OPPOSING_SIGNAL_EXIT` reads:

    # Live equivalent lives in live/trader.py behind EXIT_ON_OPPOSING_SIGNAL.

Two things are wrong with that sentence, and the second is the serious one.

**`EXIT_ON_OPPOSING_SIGNAL` exists nowhere.** It appears exactly once in the repository —
in that comment. No config key, no variable, no live flag.

**`live/trader.py` has no opposing-signal logic at all.** Not under another name, not
behind another flag: the word "opposing" does not appear in the file. The live exit paths
are the bracket (`target_hit` / `stop_hit`, including the inferred form), the software
take-profit, the `MAX_TRADE_BARS_LIVE` time exit, and the reconciliation paths — and none
of them consults the signal.

So the backtest can be configured with an exit rule the live bot cannot perform, while a
comment tells the reader parity exists behind a flag. `OPPOSING_SIGNAL_EXIT_MODES` makes
this reachable per-mode, so a sweep could select parameters conditioned on an exit that
will never fire in production. That is the F12 family — a backtest↔live divergence — except
manufactured by a comment rather than by data.

**Fixed by correcting the comment, not by adding the feature.** Building a live
opposing-signal exit touches `live/trader.py`, which is fenced and would need approval and
its own validation; and D6 recommends against the active engine anyway. The honest change
is to stop advertising parity that does not exist. This file then guards both halves: the
comment must not promise a live equivalent, and the moment `live/trader.py` gains real
opposing-signal handling, `test_the_live_trader_still_has_no_opposing_exit` fails and tells
the maintainer to restore the parity note.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from tests._engine_uncounted import uncounted_module  # noqa: E402

# One test probes compute_trade_returns on hand-built bars: engine arithmetic, not a
# strategy evaluation, so it runs outside the trial ledger (src/strategy/counted.py).
setUpModule, tearDownModule = uncounted_module("opposing-exit parity: the engine books one on hand-built bars")

TRADER = ROOT / "live" / "trader.py"
CONFIG = ROOT / "config.py"


def repo_mentions(token):
    out = subprocess.run(
        ["git", "grep", "-n", "--", token], cwd=str(ROOT),
        capture_output=True, text=True)
    return [line for line in out.stdout.splitlines() if line.strip()]


class TheAdvertisedLiveFlagDoesNotExistTests(unittest.TestCase):
    def test_exit_on_opposing_signal_is_not_defined_anywhere(self):
        self.assertFalse(
            hasattr(config, "EXIT_ON_OPPOSING_SIGNAL"),
            "EXIT_ON_OPPOSING_SIGNAL now exists in config — if a live opposing-signal "
            "exit was built, restore the parity note in config.py and update this file")
        self.assertNotIn("EXIT_ON_OPPOSING_SIGNAL",
                         TRADER.read_text(encoding="utf-8"))

    def test_the_backtest_flag_that_DOES_exist_is_the_other_name(self):
        """Non-vacuity: the feature is real on the backtest side."""
        self.assertTrue(hasattr(config, "USE_OPPOSING_SIGNAL_EXIT"))
        self.assertIn("USE_OPPOSING_SIGNAL_EXIT",
                      (ROOT / "src" / "backtest" / "runner.py").read_text(
                          encoding="utf-8"))

    def test_it_is_reachable_per_mode_which_is_why_this_matters(self):
        self.assertTrue(hasattr(config, "OPPOSING_SIGNAL_EXIT_MODES"),
                        "the per-mode override set is gone; the divergence is narrower")


class TheLiveTraderHasNoOpposingExitTests(unittest.TestCase):
    """The serious half. Not a naming problem — a missing behaviour."""

    def test_the_live_trader_still_has_no_opposing_exit(self):
        text = TRADER.read_text(encoding="utf-8").lower()
        self.assertNotIn(
            "opposing", text,
            "live/trader.py now mentions an opposing-signal exit. If the behaviour was "
            "implemented, config.py's comment should describe it again — and the "
            "backtest/live parity needs re-verifying, not assuming.")

    def test_the_live_exit_paths_are_the_known_signal_free_ones(self):
        text = TRADER.read_text(encoding="utf-8")
        for marker in ("_infer_bracket_exit", "MAX_TRADE_BARS_LIVE"):
            self.assertIn(marker, text,
                          "{} vanished — re-enumerate the live exit paths".format(marker))
        exit_types = set(re.findall(r'exit_type\s*=\s*"([a-z_]+)"', text))
        self.assertTrue(exit_types, "no literal exit types found in the trader")
        self.assertNotIn("opposing_signal", exit_types,
                         "the live trader now books an opposing_signal exit")

    def test_the_backtest_engine_by_contrast_DOES_book_one(self):
        """The asymmetry, stated in one assertion.

        Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): v3 rewrote
        compute_trade_returns and assigns the label in a tuple assignment, so the v2
        source token (``exit_type   = "opposing_signal"``) no longer matches although the
        exit still exists. The engine is now asked directly: a long whose later bar votes
        short closes at the next bar's open as ``opposing_signal``.
        """
        import pandas as pd
        from src.strategy.engine import compute_trade_returns

        flat = (100.0, 100.1, 99.9, 100.0)
        rows = [flat, flat, flat, (100.4, 100.5, 100.3, 100.4), flat]
        df = pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                          index=pd.date_range("2026-03-02 14:30", periods=len(rows), freq="h"))
        df["entry_signal"] = [1, 0, 0, 0, 0]
        df["signal_vote"] = [1, 0, -1, 0, 0]
        res = compute_trade_returns(df, target_gain_pct=0.05, stop_loss_pct=0.05,
                                    max_trade_bars=3, use_opposing_signal_exit=True)
        self.assertEqual(list(res["exit_type"]), ["opposing_signal"],
                         "the backtest no longer books an opposing_signal exit either — "
                         "the divergence closed from the other side")
        self.assertAlmostEqual(float(res["return"].iloc[0]), 0.004, places=12)


class TheCommentNoLongerPromisesParityTests(unittest.TestCase):
    def test_config_does_not_claim_a_live_equivalent(self):
        line = next((l for l in CONFIG.read_text(encoding="utf-8").splitlines()
                     if "opposing-signal" in l.lower() and "live/trader.py" in l), None)
        self.assertIsNone(
            line,
            "config.py again claims a live equivalent for the opposing-signal exit: "
            "{!r}. There is none.".format(line))

    def test_config_records_the_divergence_instead(self):
        text = CONFIG.read_text(encoding="utf-8")
        self.assertIn("BACKTEST-ONLY", text,
                      "config.py no longer marks the opposing-signal exit as "
                      "backtest-only — a reader could assume live parity again")


if __name__ == "__main__":
    unittest.main()
