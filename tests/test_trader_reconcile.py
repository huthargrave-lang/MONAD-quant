"""
Tests for the entry-time broker/state reconciliation guard in
``live.trader._on_bar_inner``.

Regression target: a hidden broker position (e.g. an orphaned short) while the
state DB believed it was flat let the bot place an entry and stack blind
exposure. The guard must refuse to enter unless the broker is verifiably flat.
"""

import sys
import types
import unittest
from unittest import mock


def _stub_missing(name: str) -> None:
    if name in sys.modules:
        return
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = types.ModuleType(name)


# live.trader pulls in live.signals -> src.data.fetcher -> yfinance and
# live.broker -> ib_insync. Stub them if unavailable (e.g. in CI).
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


def _signal(sig=1):
    return {
        "signal": sig,
        "bar_time": "2026-06-17 16:30:00",
        "bar_close": 80.0,
        "rsi": 30.0,
        "vwap_zscore": -1.0,
        "momentum_signal": 1,
        "volume_signal": 0,
    }


class TestReconcileGuard(unittest.TestCase):
    def _common_mocks(self, stack):
        msig = stack.enter_context(mock.patch.object(trader, "signals"))
        mstate = stack.enter_context(mock.patch.object(trader, "state"))
        mbroker = stack.enter_context(mock.patch.object(trader, "broker"))
        malerts = stack.enter_context(mock.patch.object(trader, "alerts"))
        msig.get_current_signal.return_value = _signal(1)  # long signal
        mstate.get_position.return_value = None             # state DB says FLAT
        return msig, mstate, mbroker, malerts

    def test_blocks_entry_when_broker_holds_position(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            _msig, mstate, mbroker, malerts = self._common_mocks(stack)
            mbroker.get_open_position.return_value = {
                "qty": -1059, "avg_price": 77.18, "market_value": -81_000.0,
            }
            result = trader._on_bar_inner()

        self.assertEqual(result, "entry_blocked_desync")
        mbroker.place_bracket_order.assert_not_called()
        # A CRITICAL reconcile monitor event must be recorded, and an alert sent.
        levels = [(c.args[0], c.args[1]) for c in mstate.add_monitor_event.call_args_list]
        self.assertIn(("CRITICAL", "reconcile"), levels)
        malerts.alert_error.assert_called_once()

    def test_blocks_entry_when_broker_unverifiable(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            _msig, _mstate, mbroker, _malerts = self._common_mocks(stack)
            mbroker.get_open_position.side_effect = RuntimeError("Connect call failed")
            result = trader._on_bar_inner()

        self.assertEqual(result, "entry_blocked_broker_unverified")
        mbroker.place_bracket_order.assert_not_called()

    def test_allows_entry_when_broker_flat(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            _msig, mstate, mbroker, _malerts = self._common_mocks(stack)
            mbroker.get_open_position.return_value = None  # broker also FLAT
            mstate.get_position_plan.return_value = {
                "position_pct": 0.10, "position_dollars": 10_000.0,
            }
            mbroker.get_account.return_value = types.SimpleNamespace(equity=100_000.0)
            mbroker.place_bracket_order.return_value = {
                "order_id": "42", "fill_basis": 80.0,
                "target_price": 80.8, "stop_price": 79.6,
            }
            stack.enter_context(mock.patch.object(
                trader, "_get_asset_config",
                return_value={"target_gain_pct": 0.01, "stop_loss_pct": 0.005}))
            stack.enter_context(mock.patch.object(trader, "_sync_account_and_mark"))
            stack.enter_context(mock.patch.object(trader.config, "LIVE_DRY_RUN", False))
            result = trader._on_bar_inner()

        self.assertEqual(result, "entry_placed")
        mbroker.place_bracket_order.assert_called_once()


if __name__ == "__main__":
    unittest.main()
