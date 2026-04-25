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

from live.trader import _classify_bracket_exit_from_prices, _infer_bracket_exit, _signed_return  # noqa: E402


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


class TestInferBracketExitLong(unittest.TestCase):
    """Long bracket: TP above entry, SL below entry."""

    def _pos(self) -> _FakePos:
        return _FakePos(
            entry_price=48.00, target_price=48.20, stop_price=47.90, direction="long"
        )

    def test_ref_above_tp_is_target_hit(self):
        exit_price, exit_type = _infer_bracket_exit(self._pos(), 48.30)
        self.assertAlmostEqual(exit_price, 48.20)
        self.assertEqual(exit_type, "target_hit")

    def test_ref_below_sl_is_stop_hit(self):
        exit_price, exit_type = _infer_bracket_exit(self._pos(), 47.80)
        self.assertAlmostEqual(exit_price, 47.90)
        self.assertEqual(exit_type, "stop_hit")

    def test_ambiguous_closer_to_sl(self):
        _, exit_type = _infer_bracket_exit(self._pos(), 47.95)
        self.assertEqual(exit_type, "stop_hit")

    def test_ambiguous_closer_to_tp(self):
        _, exit_type = _infer_bracket_exit(self._pos(), 48.17)
        self.assertEqual(exit_type, "target_hit")


class TestInferBracketExitShort(unittest.TestCase):
    """Short bracket: TP below entry, SL above entry."""

    def _pos(self) -> _FakePos:
        return _FakePos(
            entry_price=48.00, target_price=47.80, stop_price=48.10, direction="short"
        )

    def test_ref_below_tp_is_target_hit(self):
        exit_price, exit_type = _infer_bracket_exit(self._pos(), 47.70)
        self.assertAlmostEqual(exit_price, 47.80)
        self.assertEqual(exit_type, "target_hit")

    def test_ref_above_sl_is_stop_hit(self):
        exit_price, exit_type = _infer_bracket_exit(self._pos(), 48.20)
        self.assertAlmostEqual(exit_price, 48.10)
        self.assertEqual(exit_type, "stop_hit")

    def test_ambiguous_closer_to_tp(self):
        _, exit_type = _infer_bracket_exit(self._pos(), 47.85)
        self.assertEqual(exit_type, "target_hit")

    def test_ambiguous_closer_to_sl(self):
        _, exit_type = _infer_bracket_exit(self._pos(), 48.05)
        self.assertEqual(exit_type, "stop_hit")


class TestInferBracketExitLegacy(unittest.TestCase):
    """Positions without a `direction` attribute fall back to long semantics."""

    def test_legacy_long_target_hit(self):
        pos = _LegacyPos(entry_price=48.0, target_price=48.20, stop_price=47.90)
        exit_price, exit_type = _infer_bracket_exit(pos, 48.30)
        self.assertAlmostEqual(exit_price, 48.20)
        self.assertEqual(exit_type, "target_hit")

    def test_legacy_long_stop_hit(self):
        pos = _LegacyPos(entry_price=48.0, target_price=48.20, stop_price=47.90)
        exit_price, exit_type = _infer_bracket_exit(pos, 47.80)
        self.assertAlmostEqual(exit_price, 47.90)
        self.assertEqual(exit_type, "stop_hit")


class TestClassifyBracketExitLong(unittest.TestCase):
    """Reclassify bracket_exit using stored TP/SL — long positions."""

    def test_fill_at_target_is_target_hit(self):
        pos = _FakePos(entry_price=100.0, target_price=103.0, stop_price=98.0, direction="long")
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 103.0), "target_hit")

    def test_fill_at_stop_is_stop_hit(self):
        pos = _FakePos(entry_price=100.0, target_price=103.0, stop_price=98.0, direction="long")
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 98.0), "stop_hit")

    def test_fill_near_target_is_target_hit(self):
        pos = _FakePos(entry_price=100.0, target_price=103.0, stop_price=98.0, direction="long")
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 102.8), "target_hit")

    def test_fill_near_stop_is_stop_hit(self):
        pos = _FakePos(entry_price=100.0, target_price=103.0, stop_price=98.0, direction="long")
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 98.3), "stop_hit")


class TestClassifyBracketExitShort(unittest.TestCase):
    """Reclassify bracket_exit using stored TP/SL — short positions."""

    def test_fill_at_target_is_target_hit(self):
        pos = _FakePos(entry_price=100.0, target_price=97.0, stop_price=102.0, direction="short")
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 97.0), "target_hit")

    def test_fill_at_stop_is_stop_hit(self):
        pos = _FakePos(entry_price=100.0, target_price=97.0, stop_price=102.0, direction="short")
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 102.0), "stop_hit")


class TestClassifyBracketExitEdgeCases(unittest.TestCase):
    """Edge cases: missing data, ambiguous fills."""

    def test_missing_target_returns_bracket_exit(self):
        pos = _FakePos(entry_price=100.0, target_price=None, stop_price=98.0)
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 99.0), "bracket_exit")

    def test_missing_stop_returns_bracket_exit(self):
        pos = _FakePos(entry_price=100.0, target_price=103.0, stop_price=None)
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 101.0), "bracket_exit")

    def test_missing_fill_returns_bracket_exit(self):
        pos = _FakePos(entry_price=100.0, target_price=103.0, stop_price=98.0)
        self.assertEqual(_classify_bracket_exit_from_prices(pos, None), "bracket_exit")

    def test_zero_target_returns_bracket_exit(self):
        pos = _FakePos(entry_price=100.0, target_price=0, stop_price=98.0)
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 99.0), "bracket_exit")

    def test_exact_midpoint_goes_to_target(self):
        # Equidistant: dist_tp == dist_sl → target wins (dist_tp <= dist_sl)
        pos = _FakePos(entry_price=100.0, target_price=103.0, stop_price=97.0)
        self.assertEqual(_classify_bracket_exit_from_prices(pos, 100.0), "target_hit")

    def test_already_classified_not_called(self):
        # Verify the function only handles bracket_exit — caller checks exit_type first
        pos = _FakePos(entry_price=100.0, target_price=103.0, stop_price=98.0)
        # Function always returns a label; caller gates on exit_type == "bracket_exit"
        result = _classify_bracket_exit_from_prices(pos, 103.0)
        self.assertEqual(result, "target_hit")


if __name__ == "__main__":
    unittest.main()
