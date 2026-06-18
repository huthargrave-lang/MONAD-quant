"""
End-to-end flow tests for live.trader._on_bar_inner (B7).

Covers the cycle transitions not exercised by test_trader_reconcile.py (entry
guard / happy-path entry) or test_software_take_profit.py (software TP):

  * signal-fetch failure escalation (ERROR -> CRITICAL by consecutive streak) —
    the roadmap C6 gap, previously only verified by hand
  * no-signal flat cycle
  * holding within the bar limit
  * exit reconcile: real bracket fill, inferred fill, back-to-back re-entry
  * pending_close: reconciled, unresolved (blocks entry), force-finalize (CRITICAL)
  * time-exit

signals/state/broker/alerts are mocked; the IO helpers (_sync_account_and_mark,
_log_summary) and price helpers are patched so each test isolates one transition.
trader.py itself is NOT modified.
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


def _signal(sig=1):
    return {
        "signal": sig, "bar_time": "2026-06-17 16:30:00", "bar_close": 80.0,
        "rsi": 30.0, "vwap_zscore": -1.0, "momentum_signal": 1, "volume_signal": 0,
    }


def _position(status="open", direction="long", entry=80.0, qty=100,
              bracket_id="100", symbol="TQQQ", est_exit=None):
    return types.SimpleNamespace(
        status=status, direction=direction, entry_price=entry, qty=qty,
        bracket_order_id=bracket_id, symbol=symbol, estimated_exit_price=est_exit,
        target_price=80.8, stop_price=79.6,
    )


class _Base(unittest.TestCase):
    def _mocks(self, stack):
        msig = stack.enter_context(mock.patch.object(trader, "signals"))
        mstate = stack.enter_context(mock.patch.object(trader, "state"))
        mbroker = stack.enter_context(mock.patch.object(trader, "broker"))
        malerts = stack.enter_context(mock.patch.object(trader, "alerts"))
        stack.enter_context(mock.patch.object(trader, "_sync_account_and_mark"))
        stack.enter_context(mock.patch.object(trader, "_log_summary"))
        msig.get_current_signal.return_value = _signal(0)  # default: no actionable signal
        mstate.get_trade_summary.return_value = {"total": 5, "win_rate": 0.6}
        return msig, mstate, mbroker, malerts

    @staticmethod
    def _levels(mstate):
        return [(c.args[0], c.args[1]) for c in mstate.add_monitor_event.call_args_list]


class TestSignalEscalation(_Base):
    def test_first_failure_is_error(self):
        with ExitStack() as s:
            msig, mstate, mbroker, malerts = self._mocks(s)
            msig.get_current_signal.side_effect = RuntimeError("yfinance down")
            mstate.get_recent_monitor_events.return_value = []   # no prior failures
            mstate.get_signal_snapshot.return_value = {"bar_close": 80.0}
            mstate.get_position.return_value = None
            result = trader._on_bar_inner()
        self.assertEqual(result, "signal_error")
        mbroker.place_bracket_order.assert_not_called()
        self.assertIn(("ERROR", "signal"), self._levels(mstate))
        self.assertEqual(malerts.alert_error.call_args.kwargs.get("level"), "ERROR")

    def test_consecutive_failures_escalate_to_critical(self):
        with ExitStack() as s:
            msig, mstate, mbroker, malerts = self._mocks(s)
            msig.get_current_signal.side_effect = RuntimeError("still down")
            # One prior signal/ERROR -> streak becomes 2 == threshold -> CRITICAL.
            mstate.get_recent_monitor_events.return_value = [
                {"category": "signal", "level": "ERROR"},
            ]
            mstate.get_signal_snapshot.return_value = {"bar_close": 80.0}
            mstate.get_position.return_value = None
            with mock.patch.object(trader.config, "LIVE_SIGNAL_FAIL_ALERT_THRESHOLD", 2):
                result = trader._on_bar_inner()
        self.assertEqual(result, "signal_error")
        self.assertIn(("CRITICAL", "signal"), self._levels(mstate))
        self.assertEqual(malerts.alert_error.call_args.kwargs.get("level"), "CRITICAL")


class TestFlatCycles(_Base):
    def test_no_signal_does_nothing(self):
        with ExitStack() as s:
            msig, mstate, mbroker, _ = self._mocks(s)
            msig.get_current_signal.return_value = _signal(0)
            mstate.get_position.return_value = None
            result = trader._on_bar_inner()
        self.assertEqual(result, "no_signal")
        mbroker.place_bracket_order.assert_not_called()


class TestHolding(_Base):
    def test_holding_within_bar_limit(self):
        with ExitStack() as s:
            msig, mstate, mbroker, _ = self._mocks(s)
            mstate.get_position.return_value = _position(status="open")
            mbroker.get_open_position.return_value = {"qty": 100, "avg_price": 80.0}
            mstate.increment_bar_count.return_value = 3
            s.enter_context(mock.patch.object(trader, "_get_asset_config",
                            return_value={"target_gain_pct": 0.01, "stop_loss_pct": 0.005}))
            s.enter_context(mock.patch.object(trader, "_resolve_mark_price",
                            return_value=(80.0, "live")))  # between stop & target
            s.enter_context(mock.patch.object(trader.config, "MAX_TRADE_BARS_LIVE", 10))
            result = trader._on_bar_inner()
        self.assertEqual(result, "holding_bar_3")
        mbroker.place_bracket_order.assert_not_called()
        mstate.close_position.assert_not_called()


class TestExitReconcile(_Base):
    def _holding_open(self, s, fill=None, signal=0):
        msig, mstate, mbroker, malerts = self._mocks(s)
        msig.get_current_signal.return_value = _signal(signal)
        mstate.get_position.return_value = _position(status="open")
        mbroker.get_open_position.return_value = None      # broker already exited
        mbroker.get_bracket_fill.return_value = fill
        return msig, mstate, mbroker, malerts

    def test_real_bracket_fill_closes_position(self):
        with ExitStack() as s:
            _, mstate, mbroker, malerts = self._holding_open(
                s, fill={"fill_price": 81.6, "fill_time": "t", "exit_type": "target_hit"})
            result = trader._on_bar_inner()
        self.assertEqual(result, "exit_target_hit")
        mstate.close_position.assert_called_once()
        self.assertEqual(mstate.close_position.call_args.kwargs["exit_type"], "target_hit")
        malerts.alert_exit.assert_called_once()
        mbroker.place_bracket_order.assert_not_called()

    def test_inferred_exit_when_fill_unavailable(self):
        with ExitStack() as s:
            _, mstate, mbroker, _ = self._holding_open(s, fill=None)
            mbroker.get_reference_price.return_value = 79.6
            s.enter_context(mock.patch.object(trader, "_infer_bracket_exit",
                            return_value=(79.6, "stop_hit")))
            result = trader._on_bar_inner()
        self.assertEqual(result, "exit_stop_hit_inferred")
        self.assertIn(("WARNING", "fill"), self._levels(mstate))
        self.assertEqual(mstate.close_position.call_args.kwargs["exit_type"], "stop_hit")

    def test_back_to_back_entry_after_exit(self):
        with ExitStack() as s:
            _, mstate, mbroker, _ = self._holding_open(
                s, fill={"fill_price": 81.6, "fill_time": "t", "exit_type": "target_hit"},
                signal=1)
            mbroker.get_open_position.return_value = None  # flat for re-entry guard too
            mstate.get_position_plan.return_value = {"position_pct": 0.10, "position_dollars": 10_000.0}
            mbroker.get_account.return_value = types.SimpleNamespace(equity=100_000.0)
            mbroker.place_bracket_order.return_value = {
                "order_id": "43", "fill_basis": 81.6, "target_price": 82.4, "stop_price": 81.2}
            s.enter_context(mock.patch.object(trader, "_get_asset_config",
                            return_value={"target_gain_pct": 0.01, "stop_loss_pct": 0.005}))
            s.enter_context(mock.patch.object(trader.config, "LIVE_DRY_RUN", False))
            result = trader._on_bar_inner()
        self.assertEqual(result, "exit_target_hit_then_entry")
        mbroker.place_bracket_order.assert_called_once()


class TestPendingClose(_Base):
    def test_reconciled_when_fill_found(self):
        with ExitStack() as s:
            _, mstate, mbroker, malerts = self._mocks(s)
            mstate.get_position.return_value = _position(status="pending_close")
            mbroker.get_bracket_fill.return_value = {
                "fill_price": 81.6, "fill_time": "t", "exit_type": "target_hit"}
            result = trader._on_bar_inner()
        self.assertEqual(result, "reconciled_target_hit")
        mstate.finalize_pending_close.assert_called_once()
        malerts.alert_exit.assert_called_once()

    def test_unresolved_blocks_entry(self):
        with ExitStack() as s:
            msig, mstate, mbroker, _ = self._mocks(s)
            msig.get_current_signal.return_value = _signal(1)   # would enter if not blocked
            mstate.get_position.return_value = _position(status="pending_close")
            mbroker.get_bracket_fill.return_value = None
            mstate.increment_pending_close_retries.return_value = 1
            with mock.patch.object(trader.config, "PENDING_CLOSE_MAX_RETRIES", 3):
                result = trader._on_bar_inner()
        self.assertEqual(result, "pending_close_unresolved")
        mbroker.place_bracket_order.assert_not_called()
        mstate.finalize_pending_close.assert_not_called()

    def test_force_finalize_after_max_retries_is_critical(self):
        with ExitStack() as s:
            _, mstate, mbroker, malerts = self._mocks(s)
            mstate.get_position.return_value = _position(status="pending_close", est_exit=79.5)
            mbroker.get_bracket_fill.return_value = None
            mstate.increment_pending_close_retries.return_value = 3
            with mock.patch.object(trader.config, "PENDING_CLOSE_MAX_RETRIES", 3):
                result = trader._on_bar_inner()
        self.assertEqual(result, "reconciled_estimated")
        self.assertIn(("CRITICAL", "fill"), self._levels(mstate))
        self.assertEqual(mstate.finalize_pending_close.call_args.kwargs["exit_type"], "estimated_close")
        self.assertEqual(malerts.alert_error.call_args.kwargs.get("level"), "CRITICAL")


class TestTimeExit(_Base):
    def test_time_exit_closes_at_bar_limit(self):
        with ExitStack() as s:
            _, mstate, mbroker, _ = self._mocks(s)
            mstate.get_position.return_value = _position(status="open")
            mbroker.get_open_position.return_value = {"qty": 100, "avg_price": 80.0}
            mstate.increment_bar_count.return_value = 10          # at the limit
            mbroker.cancel_and_close.return_value = {"fill_price": 80.5}
            s.enter_context(mock.patch.object(trader, "_get_asset_config",
                            return_value={"target_gain_pct": 0.01, "stop_loss_pct": 0.005}))
            s.enter_context(mock.patch.object(trader, "_resolve_mark_price",
                            return_value=(80.0, "live")))  # no stop/TP trigger
            s.enter_context(mock.patch.object(trader.config, "MAX_TRADE_BARS_LIVE", 10))
            result = trader._on_bar_inner()
        self.assertEqual(result, "exit_time_exit")
        self.assertEqual(mstate.close_position.call_args.kwargs["exit_type"], "time_exit")
        mbroker.cancel_and_close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
