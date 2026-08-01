"""Live returns are on 10%-of-equity notional, not on the account (F160).

`live/trader.py::_signed_return` computes `(exit - entry) / entry` — a PRICE return on
the position — and the position is a fixed fraction of equity
(`live/state.py: position_pct = 0.10`). Compounding those raw gives a return on
notional, roughly 10x the account effect.

Measured on the one committed run (`data/live_runs/archive_2026-06-18_pre_clean_run`):
the dashboard's "+35.2%" is +3.13% on the account, and the CONFIRMED-fill "honest
edge" is +0.045%, not +0.205%. The flat verdict survives; the magnitude does not.

These tests pin the two reporting paths that are NOT on the live deny-fence
(`tools/ctx.py`, `ops/analyze_run.py`). `live/dashboard.py` and `live/state.py` are
fenced and still report the notional number as an account return — that is recorded in
F160, not fixed here.

The archive is used as the fixture because it is real recorded execution AND it
carries its own stored headline, so the test can prove the tool still reproduces the
number the project published while additionally reporting the account truth.
"""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


CTX = _load("ctx_units", "tools/ctx.py")
ANALYZE = _load("analyze_units", "ops/analyze_run.py")


class FractionConstantTests(unittest.TestCase):
    def test_both_tools_agree_with_the_trader_on_the_position_fraction(self):
        self.assertEqual(CTX.LIVE_POSITION_FRACTION, 0.10)
        self.assertEqual(ANALYZE.LIVE_POSITION_FRACTION, 0.10)
        state = (ROOT / "live" / "state.py").read_text(encoding="utf-8")
        self.assertIn(
            "position_pct = 0.10", state,
            "live/state.py no longer sizes at 10% — LIVE_POSITION_FRACTION in "
            "tools/ctx.py and ops/analyze_run.py must be updated to match, or every "
            "reported account return is wrong again.",
        )


class CompoundTests(unittest.TestCase):
    def test_fraction_one_reproduces_the_old_notional_behaviour(self):
        """Backwards compatibility: the notional column must be unchanged, or the
        tool stops reproducing the project's published figures."""
        rs = [0.01, -0.005, 0.02]
        expected = ((1.01 * 0.995 * 1.02) - 1) * 100
        self.assertAlmostEqual(CTX._compound(rs), expected, places=10)
        self.assertAlmostEqual(ANALYZE._compound(rs), expected, places=10)

    def test_account_units_are_materially_smaller(self):
        rs = [0.01] * 20
        notional = CTX._compound(rs)
        account = CTX._compound(rs, CTX.LIVE_POSITION_FRACTION)
        self.assertGreater(notional, account)
        # ~10x for small returns; assert the order of magnitude, not a fragile ratio
        self.assertGreater(notional / account, 8.0)
        self.assertLess(notional / account, 12.0)

    def test_zero_and_empty_are_handled(self):
        self.assertAlmostEqual(CTX._compound([], 0.10), 0.0)
        self.assertAlmostEqual(CTX._compound([0.0, 0.0], 0.10), 0.0)

    def test_a_total_loss_on_the_position_is_not_a_total_loss_on_the_account(self):
        """The direction that matters for risk: -100% on a 10% position is -10%."""
        self.assertAlmostEqual(CTX._compound([-1.0], 0.10), -10.0, places=9)
        self.assertAlmostEqual(CTX._compound([-1.0]), -100.0, places=9)


class ArchiveFixtureTests(unittest.TestCase):
    """Against real recorded execution, with the project's own stored headline."""

    @classmethod
    def setUpClass(cls):
        if not ARCHIVE.exists():
            raise unittest.SkipTest("live-run archive not present")
        cls.trades = [
            json.loads(line)
            for line in (ARCHIVE / "trades.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        cls.meta = json.loads((ARCHIVE / "metadata.json").read_text(encoding="utf-8"))

    def _returns(self, exit_types=None):
        return [
            float(t.get("return_pct") or 0.0) for t in self.trades
            if exit_types is None or t.get("exit_type") in exit_types
        ]

    def test_notional_reproduces_the_archives_own_stored_headline(self):
        """Proof the correction did not change what the project published — only
        added the account column beside it."""
        prod = self._returns(CTX.PROD)
        stored = self.meta["headline_metrics"]["dashboard_compounded_pct"]
        self.assertAlmostEqual(CTX._compound(prod), stored, places=2)

    def test_the_account_figure_is_an_order_of_magnitude_smaller(self):
        prod = self._returns(CTX.PROD)
        account = CTX._compound(prod, CTX.LIVE_POSITION_FRACTION)
        self.assertLess(
            account, 5.0,
            "the dashboard's ~35% is ~3% on the account; if this grew, re-measure")
        self.assertGreater(account, 1.0)

    def test_the_confirmed_edge_stays_flat_in_account_units(self):
        """The verdict is what must survive: F43/D6 said flat, and +0.045% is flat.
        This correction changes the magnitude of the headline, not the conclusion."""
        conf = self._returns(CTX.CONFIRMED)
        account = CTX._compound(conf, CTX.LIVE_POSITION_FRACTION)
        self.assertLess(abs(account), 0.5, "confirmed-fill edge is no longer flat")


class NoRawCompoundLeftInTheFixedToolsTests(unittest.TestCase):
    """Bidirectional: reverting either tool to a raw compound should be noticed."""

    def test_ctx_perf_reports_account_units(self):
        src = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        self.assertIn("LIVE_POSITION_FRACTION", src)
        self.assertIn("account=", src, "ctx perf no longer labels the account column")

    def test_analyze_run_reports_account_units(self):
        src = (ROOT / "ops" / "analyze_run.py").read_text(encoding="utf-8")
        self.assertIn("LIVE_POSITION_FRACTION", src)
        self.assertIn("ON THE ACCOUNT", src)


if __name__ == "__main__":
    unittest.main()
