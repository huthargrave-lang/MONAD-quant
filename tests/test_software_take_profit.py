"""
Tests for the software take-profit safety net in ``live.trader._on_bar_inner``.

The IBKR paper bracket TP frequently fails to fill, letting winners ride past
target to the time-exit. When the mark price reaches the target, the trader
should force-close at market (mirroring the software stop), capping the winner.
"""

import sys
import types
import unittest
from contextlib import ExitStack
from unittest import mock


def _stub_missing(name: str) -> None:
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

import live.trader as trader  # noqa: E402


def _no_entry_signal():
    return {
        "signal": 0, "bar_time": "2026-06-17 16:30:00", "bar_close": 80.0,
        "rsi": 50.0, "vwap_zscore": 0.0, "momentum_signal": 0, "volume_signal": 0,
    }


def _open_position(direction="long", entry=80.0):
    return types.SimpleNamespace(
        status="open", direction=direction, entry_price=entry, qty=125,
        symbol="TQQQ", bracket_order_id="42",
    )


class TestSoftwareTakeProfit(unittest.TestCase):
    def _setup(self, stack, *, mark, direction="long", sw_tp=True, bars=2):
        msig = stack.enter_context(mock.patch.object(trader, "signals"))
        mstate = stack.enter_context(mock.patch.object(trader, "state"))
        mbroker = stack.enter_context(mock.patch.object(trader, "broker"))
        stack.enter_context(mock.patch.object(trader, "alerts"))
        stack.enter_context(mock.patch.object(trader, "_sync_account_and_mark"))
        stack.enter_context(mock.patch.object(
            trader, "_resolve_mark_price", return_value=(mark, "live")))
        stack.enter_context(mock.patch.object(
            trader, "_get_asset_config",
            return_value={"target_gain_pct": 0.01, "stop_loss_pct": 0.005}))
        stack.enter_context(mock.patch.object(trader.config, "USE_SOFTWARE_TAKE_PROFIT", sw_tp))
        stack.enter_context(mock.patch.object(trader.config, "MAX_TRADE_BARS_LIVE", 10))

        msig.get_current_signal.return_value = _no_entry_signal()
        mstate.get_position.return_value = _open_position(direction)
        mstate.increment_bar_count.return_value = bars
        mstate.get_trade_summary.return_value = {
            "total": 1, "win_rate": 1.0, "total_ret": 0.01,
            "exit_types": {"target_hit": 1},
        }
        mbroker.get_open_position.return_value = {"qty": 125, "avg_price": 80.0, "market_value": 10_000.0}
        mbroker.cancel_and_close.return_value = {"fill_price": 80.85, "fill_time": "t"}
        return mstate, mbroker

    def test_long_take_profit_fires_at_target(self):
        # entry 80, target +1% = 80.80; mark 81.0 >= target → fire
        with ExitStack() as stack:
            mstate, mbroker = self._setup(stack, mark=81.0)
            result = trader._on_bar_inner()
        self.assertEqual(result, "exit_software_take_profit")
        mbroker.cancel_and_close.assert_called_once()
        _a, kw = mstate.close_position.call_args
        self.assertEqual(kw.get("exit_type"), "target_hit")

    def test_no_take_profit_below_target(self):
        # mark 80.30 < target 80.80 and > stop 79.60 → just holding
        with ExitStack() as stack:
            _mstate, mbroker = self._setup(stack, mark=80.30)
            result = trader._on_bar_inner()
        self.assertTrue(result.startswith("holding"))
        mbroker.cancel_and_close.assert_not_called()

    def test_flag_off_disables_software_take_profit(self):
        # mark above target but flag off → no force-close, position holds
        with ExitStack() as stack:
            _mstate, mbroker = self._setup(stack, mark=81.0, sw_tp=False)
            result = trader._on_bar_inner()
        self.assertTrue(result.startswith("holding"))
        mbroker.cancel_and_close.assert_not_called()

    def test_short_take_profit_fires_at_target(self):
        # short entry 80, target = 80*(1-0.01)=79.20; mark 79.0 <= target → fire
        with ExitStack() as stack:
            mstate, mbroker = self._setup(stack, mark=79.0, direction="short")
            result = trader._on_bar_inner()
        self.assertEqual(result, "exit_software_take_profit")
        mbroker.cancel_and_close.assert_called_once()
        _a, kw = mstate.close_position.call_args
        self.assertEqual(kw.get("exit_type"), "target_hit")


if __name__ == "__main__":
    unittest.main()
