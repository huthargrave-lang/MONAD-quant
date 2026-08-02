"""
Tests for direction-aware helpers in live/trader.py.

Covers:
  * `_signed_return` — long vs short sign flip
  * `_infer_bracket_exit` — direction-aware TP/SL resolution, including
    legacy positions with no `direction` attribute
"""

import sys
import types
import unittest
from dataclasses import dataclass


def _stub_missing(name: str) -> None:
    """Install a stub module if the real one isn't importable.

    `live.trader` pulls in `live.signals` → `src.data.fetcher` → `yfinance`
    and `live.broker` → `ib_insync`. Neither is needed to exercise the pure
    helper functions under test, so we install lightweight stubs before import.
    """
    if name in sys.modules:
        return
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = types.ModuleType(name)


_stub_missing("yfinance")
if "ib_insync" not in sys.modules:
    try:
        __import__("ib_insync")
    except ImportError:
        ib = types.ModuleType("ib_insync")
        for attr in ("IB", "Stock", "MarketOrder", "ExecutionFilter"):
            setattr(ib, attr, type(attr, (), {}))
        sys.modules["ib_insync"] = ib

from live.trader import _infer_bracket_exit, _signed_return  # noqa: E402


@dataclass
class _FakePos:
    entry_price: float
    target_price: float | None = None
    stop_price: float | None = None
    direction: str = "long"


@dataclass
class _LegacyPos:
    """Legacy position row with no `direction` attribute (pre-migration)."""
    entry_price: float
    target_price: float
    stop_price: float


class TestSignedReturn(unittest.TestCase):
    """Long returns should have normal sign; short returns should flip."""

    def test_long_profit_positive(self):
        self.assertAlmostEqual(_signed_return("long", 100.0, 101.0), 0.01)

    def test_long_loss_negative(self):
        self.assertAlmostEqual(_signed_return("long", 100.0, 99.0), -0.01)

    def test_short_profit_positive(self):
        # Short profits when price drops
        self.assertAlmostEqual(_signed_return("short", 100.0, 99.0), 0.01)

    def test_short_loss_negative(self):
        self.assertAlmostEqual(_signed_return("short", 100.0, 101.0), -0.01)


class TestInferBracketExitContract(unittest.TestCase):
    """Replaces TestInferBracketExitLong/Short/Legacy, which pinned the OLD contract.

    Those asserted that a current price above TP means target_hit, and that a price
    between the levels resolves to whichever is nearer. But fill data is only
    missing when the fill happened on a PREVIOUS trading day, so the current price
    has been through an overnight gap and says nothing about which leg filled. On
    2026-07-31 that booked a 63.46 stop fill as `target_hit @ 64.42, +1.0034%` — a
    -0.5% loss recorded as a +1.0% win, in the rolling win rate adaptive Kelly
    sizes from.

    First-touch-along-the-path behaviour lives in tests/test_infer_bracket_exit.py.
    These pin the half that was wrong: absent a usable path, no leg is named.
    """

    def _pos(self, entry=100.0, tp=103.0, sl=98.0, direction="long"):
        return types.SimpleNamespace(entry_price=entry, target_price=tp,
                                     stop_price=sl, direction=direction)

    def test_ref_above_tp_is_no_longer_a_target_hit(self):
        """The bug, stated as a test: this exact shape produced the false win."""
        self.assertEqual(_infer_bracket_exit(self._pos(), 105.0)[1],
                         "estimated_close")

    def test_ref_below_sl_is_not_a_stop_hit_either(self):
        """Symmetric: the right answer for the wrong reason is still unsound."""
        self.assertEqual(_infer_bracket_exit(self._pos(), 97.0)[1],
                         "estimated_close")

    def test_the_nearest_level_tiebreak_is_gone(self):
        for ref in (102.9, 98.1):
            with self.subTest(ref=ref):
                self.assertEqual(_infer_bracket_exit(self._pos(), ref)[1],
                                 "estimated_close")

    def test_short_positions_get_the_same_treatment(self):
        p = self._pos(tp=97.0, sl=102.0, direction="short")
        for ref in (95.0, 103.0):
            with self.subTest(ref=ref):
                self.assertEqual(_infer_bracket_exit(p, ref)[1], "estimated_close")

    def test_legacy_positions_without_levels_are_not_guessed(self):
        p = types.SimpleNamespace(entry_price=100.0, target_price=None,
                                  stop_price=None, direction="long")
        for ref in (105.0, 95.0):
            with self.subTest(ref=ref):
                self.assertEqual(_infer_bracket_exit(p, ref)[1], "estimated_close")

    def test_the_returned_price_is_the_reference_not_a_bracket_level(self):
        """When the leg is unknown we must not report a bracket price as if we had
        filled there — that fabricates a precise, wrong P&L."""
        price, _ = _infer_bracket_exit(self._pos(), 105.0)
        self.assertEqual(price, 105.0)


if __name__ == "__main__":
    unittest.main()
