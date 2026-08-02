"""live/trader.py::_infer_bracket_exit — which bracket leg filled, after the fact.

THE BUG THIS PINS
    IBKR's ib.trades()/ib.fills() are current-day scoped, so fill data is missing
    in exactly one situation: the bracket filled on a PREVIOUS trading day. The old
    implementation resolved that by comparing a single CURRENT price against TP/SL
    — which is precisely the input an overnight gap destroys.

    Live, on 2026-07-31: TQQQ closed 63.44 and gapped to a 65.74 open. At the 09:32
    cycle the current price sat above the 64.42 target, so the trade was booked
    `target_hit @ 64.42, +1.0034%`. The tape says the 15:32-16:00 session low was
    63.26 — through the 63.46 stop — and the high was 63.63, never within 79 cents
    of the target. A real -0.5% loss entered the book as a +1.0% win.

    That is worse than a mis-stated P&L: it flips a loss to a win in the rolling
    win rate, and adaptive Kelly sizes the next trades off that win rate.

WHAT REPLACED IT
    First touch along the price path since entry. Same-bar ambiguity resolves to
    the stop, matching the backtest fill model (src/strategy/engine.py:247) — the
    live book and the engine must guess intrabar ordering the same way or they stop
    being comparable.

    When the path cannot answer, it records `estimated_close` rather than naming a
    leg. "I don't know" is a usable record; a confident wrong leg is not.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import live.trader as T  # noqa: E402


def pos(entry=63.78, tp=64.42, sl=63.46, direction="long",
        entry_time="2026-07-30T19:32:15+00:00", symbol="TQQQ"):
    return types.SimpleNamespace(symbol=symbol, entry_price=entry, target_price=tp,
                                 stop_price=sl, entry_time=entry_time,
                                 direction=direction)


def bars(rows):
    """rows: [(iso_ts, high, low)] -> a UTC-indexed OHLC frame."""
    idx = pd.to_datetime([r[0] for r in rows], utc=True)
    return pd.DataFrame({"high": [r[1] for r in rows],
                         "low": [r[2] for r in rows],
                         "open": [r[1] for r in rows],
                         "close": [r[2] for r in rows],
                         "volume": [1] * len(rows)}, index=idx)


class TheGapRegression(unittest.TestCase):
    """The live incident, reproduced from its real numbers."""

    def test_a_gap_up_after_a_stop_fill_is_not_a_target_hit(self):
        frame = bars([("2026-07-30T19:30:00Z", 63.63, 63.26),   # stop touched here
                      ("2026-07-31T13:30:00Z", 66.55, 65.74)])  # the gap
        with mock.patch.object(T, "fetch_yfinance", return_value=frame):
            price, kind = T._infer_bracket_exit(pos(), ref_price=66.00)
        self.assertEqual(kind, "stop_hit")
        self.assertAlmostEqual(price, 63.46, places=2)

    def test_the_recorded_return_is_a_loss_not_a_win(self):
        frame = bars([("2026-07-30T19:30:00Z", 63.63, 63.26),
                      ("2026-07-31T13:30:00Z", 66.55, 65.74)])
        with mock.patch.object(T, "fetch_yfinance", return_value=frame):
            price, _ = T._infer_bracket_exit(pos(), ref_price=66.00)
        ret = (price - 63.78) / 63.78
        self.assertLess(ret, 0, "a stop fill must book a loss")
        self.assertAlmostEqual(ret, -0.005017, places=5)

    def test_the_current_price_does_not_decide_anything(self):
        """Same bars, wildly different current prices -> same verdict."""
        frame = bars([("2026-07-30T19:30:00Z", 63.63, 63.26)])
        outs = []
        for ref in (10.0, 63.50, 66.00, 999.0):
            with mock.patch.object(T, "fetch_yfinance", return_value=frame):
                outs.append(T._infer_bracket_exit(pos(), ref_price=ref))
        self.assertEqual(len(set(outs)), 1, f"ref_price still influences the verdict: {outs}")


class FirstTouchWins(unittest.TestCase):
    def test_a_genuine_target_hit_is_reported(self):
        frame = bars([("2026-07-30T19:30:00Z", 64.50, 63.70)])
        with mock.patch.object(T, "fetch_yfinance", return_value=frame):
            price, kind = T._infer_bracket_exit(pos(), ref_price=60.0)
        self.assertEqual(kind, "target_hit")
        self.assertAlmostEqual(price, 64.42, places=2)

    def test_the_earlier_bar_decides(self):
        """Target touched first, stop only later -> target_hit."""
        frame = bars([("2026-07-30T19:30:00Z", 64.50, 63.70),
                      ("2026-07-30T20:30:00Z", 63.90, 62.00)])
        with mock.patch.object(T, "fetch_yfinance", return_value=frame):
            _, kind = T._infer_bracket_exit(pos(), ref_price=62.0)
        self.assertEqual(kind, "target_hit")

    def test_same_bar_ambiguity_resolves_to_the_stop(self):
        """Matches src/strategy/engine.py:247 — intrabar order is unknowable, so the
        engine and the live book must guess identically or diverge silently."""
        frame = bars([("2026-07-30T19:30:00Z", 64.50, 63.20)])   # touches both
        with mock.patch.object(T, "fetch_yfinance", return_value=frame):
            _, kind = T._infer_bracket_exit(pos(), ref_price=64.0)
        self.assertEqual(kind, "stop_hit")

    def test_bars_before_entry_are_ignored(self):
        """A level touched before we were in the trade did not close it."""
        frame = bars([("2026-07-29T15:30:00Z", 70.0, 60.0),      # pre-entry, touches both
                      ("2026-07-30T20:30:00Z", 64.50, 63.70)])   # post-entry target
        with mock.patch.object(T, "fetch_yfinance", return_value=frame):
            _, kind = T._infer_bracket_exit(pos(), ref_price=64.0)
        self.assertEqual(kind, "target_hit")


class ShortsAreDirectionAware(unittest.TestCase):
    def test_short_stop_is_above_and_target_below(self):
        p = pos(entry=100.0, tp=99.0, sl=101.0, direction="short")
        frame = bars([("2026-07-30T19:30:00Z", 101.5, 100.2)])   # stop (high) touched
        with mock.patch.object(T, "fetch_yfinance", return_value=frame):
            _, kind = T._infer_bracket_exit(p, ref_price=98.0)
        self.assertEqual(kind, "stop_hit")

    def test_short_target_hit(self):
        p = pos(entry=100.0, tp=99.0, sl=101.0, direction="short")
        frame = bars([("2026-07-30T19:30:00Z", 100.5, 98.5)])
        with mock.patch.object(T, "fetch_yfinance", return_value=frame):
            _, kind = T._infer_bracket_exit(p, ref_price=103.0)
        self.assertEqual(kind, "target_hit")


class UnknownIsRecordedAsUnknown(unittest.TestCase):
    """A confident wrong leg is worse than an honest gap in the record."""

    def test_unavailable_bars_do_not_name_a_leg(self):
        with mock.patch.object(T, "fetch_yfinance", side_effect=RuntimeError("no network")):
            price, kind = T._infer_bracket_exit(pos(), ref_price=66.00)
        self.assertEqual(kind, "estimated_close")
        self.assertAlmostEqual(price, 66.00, places=2)

    def test_empty_bars_do_not_name_a_leg(self):
        with mock.patch.object(T, "fetch_yfinance", return_value=pd.DataFrame()):
            _, kind = T._infer_bracket_exit(pos(), ref_price=66.00)
        self.assertEqual(kind, "estimated_close")

    def test_no_bar_touching_either_leg_is_not_a_guess(self):
        frame = bars([("2026-07-30T19:30:00Z", 64.00, 63.60)])   # inside the bracket
        with mock.patch.object(T, "fetch_yfinance", return_value=frame):
            _, kind = T._infer_bracket_exit(pos(), ref_price=66.00)
        self.assertEqual(kind, "estimated_close")

    def test_a_position_without_stored_levels_is_not_a_guess(self):
        with mock.patch.object(T, "fetch_yfinance", return_value=pd.DataFrame()):
            _, kind = T._infer_bracket_exit(pos(tp=None, sl=None), ref_price=66.00)
        self.assertEqual(kind, "estimated_close")


class TheOldHeuristicIsGone(unittest.TestCase):
    def test_no_distance_to_tp_tiebreak_remains(self):
        """The old fallback picked whichever level the CURRENT price sat nearer to,
        which is the same category error as the gap bug."""
        src = (REPO / "live" / "trader.py").read_text()
        self.assertNotIn("dist_to_tp", src)
        self.assertNotIn("closer to TP", src)

    def test_inference_consults_the_price_path(self):
        src = (REPO / "live" / "trader.py").read_text()
        self.assertIn("_first_touch_from_bars", src)


if __name__ == "__main__":
    unittest.main()
