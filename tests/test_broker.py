"""
Tests for the IBKR broker adapter (live/broker.py) — previously zero coverage,
the biggest untested live-risk surface.

ib_insync is mocked throughout (no network, no TWS). broker.py imports ib_insync
lazily inside functions, so importing the module is side-effect-free and the
ib_insync order classes can be patched at call time.

Covers:
  * place_bracket_order — long/short TP/SL/limit math, GTC children, 3-leg submit,
    return shape, and the None failure paths (bad direction, qualify fail, no price)
  * get_bracket_fill   — the three-tier fill search (trades / fills / reqExecutions),
    exit-type classification, exit-side filtering, and None/exception fallbacks
  * cancel_and_close   — child cancellation, market close action, fill vs no-fill
  * get_open_position / get_account — reconciliation reads
"""
import unittest
from datetime import datetime
from unittest import mock

import live.broker as broker


def _exec(orderId=0, side="SLD", shares=10, price=100.0, t=None):
    e = mock.Mock()
    e.orderId, e.side, e.shares, e.price, e.time = orderId, side, shares, price, t
    return e


def _fill(execution):
    f = mock.Mock()
    f.execution = execution
    return f


def _order(orderId=1, parentId=0, orderType="LMT"):
    o = mock.Mock()
    o.orderId, o.parentId, o.orderType = orderId, parentId, orderType
    return o


def _trade(order, fills=()):
    t = mock.Mock()
    t.order = order
    t.fills = list(fills)
    return t


class TestPlaceBracketOrder(unittest.TestCase):
    def _ib(self, parent_id=42):
        ib = mock.Mock()
        parent = mock.Mock(orderId=parent_id)
        tp, sl = mock.Mock(), mock.Mock()
        ib.bracketOrder.return_value = [parent, tp, sl]
        return ib, parent, tp, sl

    def test_long_prices_and_submission(self):
        ib, parent, tp, sl = self._ib()
        with mock.patch.object(broker, "_ensure_connected", return_value=ib), \
             mock.patch.object(broker, "get_tradeable_price", return_value=100.0), \
             mock.patch("ib_insync.Stock"):
            out = broker.place_bracket_order("TQQQ", 10, 0.01, 0.005, "long")

        ib.bracketOrder.assert_called_once_with(
            action="BUY", quantity=10, limitPrice=100.5,
            takeProfitPrice=101.0, stopLossPrice=99.5,
        )
        self.assertEqual(tp.tif, "GTC")
        self.assertEqual(sl.tif, "GTC")
        self.assertEqual(ib.placeOrder.call_count, 3)   # parent + TP + SL
        self.assertEqual(out, {
            "order_id": "42", "fill_basis": 100.0,
            "target_price": 101.0, "stop_price": 99.5, "direction": "long",
        })

    def test_short_prices_inverted(self):
        ib, parent, tp, sl = self._ib(parent_id=7)
        with mock.patch.object(broker, "_ensure_connected", return_value=ib), \
             mock.patch.object(broker, "get_tradeable_price", return_value=100.0), \
             mock.patch("ib_insync.Stock"):
            out = broker.place_bracket_order("TQQQ", 5, 0.02, 0.01, "short")

        ib.bracketOrder.assert_called_once_with(
            action="SELL", quantity=5, limitPrice=99.5,
            takeProfitPrice=98.0, stopLossPrice=101.0,
        )
        self.assertEqual(out["order_id"], "7")
        self.assertEqual(out["direction"], "short")

    def test_invalid_direction_returns_none(self):
        with mock.patch("ib_insync.Stock"):
            self.assertIsNone(broker.place_bracket_order("TQQQ", 10, 0.01, 0.005, "sideways"))

    def test_qualify_failure_returns_none(self):
        ib = mock.Mock()
        ib.qualifyContracts.side_effect = Exception("cannot qualify")
        with mock.patch.object(broker, "_ensure_connected", return_value=ib), \
             mock.patch("ib_insync.Stock"):
            self.assertIsNone(broker.place_bracket_order("TQQQ", 10, 0.01, 0.005, "long"))
        ib.placeOrder.assert_not_called()

    def test_no_tradeable_price_returns_none(self):
        ib = mock.Mock()
        with mock.patch.object(broker, "_ensure_connected", return_value=ib), \
             mock.patch.object(broker, "get_tradeable_price", side_effect=RuntimeError("no price")), \
             mock.patch("ib_insync.Stock"):
            self.assertIsNone(broker.place_bracket_order("TQQQ", 10, 0.01, 0.005, "long"))
        ib.placeOrder.assert_not_called()


class TestGetBracketFill(unittest.TestCase):
    def _patch_ib(self, ib):
        return mock.patch.object(broker, "_ensure_connected", return_value=ib)

    def test_tier1_trades_target_hit(self):
        ib = mock.Mock()
        t = _trade(_order(orderId=101, parentId=100, orderType="LMT"),
                   fills=[_fill(_exec(price=105.0, t=datetime(2024, 1, 2, 15, 0)))])
        ib.trades.return_value = [t]
        with self._patch_ib(ib):
            out = broker.get_bracket_fill("100", "long")
        self.assertEqual(out["fill_price"], 105.0)
        self.assertEqual(out["exit_type"], "target_hit")
        self.assertTrue(out["fill_time"].startswith("2024-01-02"))

    def test_tier1_stop_hit_classification(self):
        ib = mock.Mock()
        t = _trade(_order(orderId=101, parentId=100, orderType="STP"),
                   fills=[_fill(_exec(price=95.0, t=None))])
        ib.trades.return_value = [t]
        with self._patch_ib(ib):
            out = broker.get_bracket_fill("100", "long")
        self.assertEqual(out["exit_type"], "stop_hit")
        self.assertIsNone(out["fill_time"])

    def test_tier2_fills_match_by_parent_plus_one(self):
        # trades empty (post-restart) -> tier 1 skipped; fill matched by parent_id+1.
        ib = mock.Mock()
        ib.trades.return_value = []
        ib.fills.return_value = [_fill(_exec(orderId=101, side="SLD", shares=10, price=99.0,
                                             t=datetime(2024, 1, 3)))]
        with self._patch_ib(ib):
            out = broker.get_bracket_fill("100", "long")
        self.assertEqual(out["fill_price"], 99.0)
        self.assertEqual(out["exit_type"], "bracket_exit")  # no order type available

    def test_tier2_wrong_side_rejected_then_none(self):
        # A BOT fill for a long exit is the entry, not the exit -> rejected.
        ib = mock.Mock()
        ib.trades.return_value = []
        ib.fills.return_value = [_fill(_exec(orderId=101, side="BOT", shares=10, price=99.0))]
        ib.reqExecutions.return_value = []
        with self._patch_ib(ib), mock.patch("ib_insync.ExecutionFilter"):
            self.assertIsNone(broker.get_bracket_fill("100", "long"))

    def test_short_uses_bot_exit_side(self):
        ib = mock.Mock()
        ib.trades.return_value = []
        ib.fills.return_value = [_fill(_exec(orderId=102, side="BOT", shares=5, price=80.0))]
        with self._patch_ib(ib):
            out = broker.get_bracket_fill("100", "short")
        self.assertEqual(out["fill_price"], 80.0)
        self.assertEqual(out["exit_type"], "bracket_exit")

    def test_tier3_reqexecutions_historical(self):
        ib = mock.Mock()
        ib.trades.return_value = []
        ib.fills.return_value = []
        ib.reqExecutions.return_value = [_fill(_exec(orderId=102, side="SLD", shares=10,
                                                     price=97.5, t=datetime(2024, 1, 1)))]
        with self._patch_ib(ib), mock.patch("ib_insync.ExecutionFilter"):
            out = broker.get_bracket_fill("100", "long")
        self.assertEqual(out["fill_price"], 97.5)
        self.assertEqual(out["exit_type"], "bracket_exit")

    def test_no_fill_returns_none(self):
        ib = mock.Mock()
        ib.trades.return_value = []
        ib.fills.return_value = []
        ib.reqExecutions.return_value = []
        with self._patch_ib(ib), mock.patch("ib_insync.ExecutionFilter"):
            self.assertIsNone(broker.get_bracket_fill("100", "long"))

    def test_exception_returns_none(self):
        ib = mock.Mock()
        ib.trades.side_effect = Exception("disconnected")
        with self._patch_ib(ib):
            self.assertIsNone(broker.get_bracket_fill("100", "long"))


class TestCancelAndClose(unittest.TestCase):
    def test_invalid_direction_raises(self):
        with self.assertRaises(ValueError):
            broker.cancel_and_close("TQQQ", "100", 10, "flat")

    def test_long_close_cancels_children_and_fills(self):
        ib = mock.Mock()
        child = _order(orderId=101, parentId=100)
        other = _order(orderId=200, parentId=999)
        ib.openOrders.return_value = [child, other]
        trade = mock.Mock()
        trade.order = mock.Mock(orderId=300)
        trade.fills = [_fill(_exec(price=101.23, t=datetime(2024, 1, 2, 10, 0)))]
        ib.placeOrder.return_value = trade
        with mock.patch.object(broker, "_ensure_connected", return_value=ib), \
             mock.patch("ib_insync.Stock"), \
             mock.patch("ib_insync.MarketOrder") as MO:
            out = broker.cancel_and_close("TQQQ", "100", 10, "long")
        ib.cancelOrder.assert_called_once_with(child)   # only the matching child
        MO.assert_called_once_with("SELL", 10)          # long closes via SELL
        self.assertEqual(out["fill_price"], 101.23)

    def test_short_close_uses_buy(self):
        ib = mock.Mock()
        ib.openOrders.return_value = []
        trade = mock.Mock()
        trade.order = mock.Mock(orderId=301)
        trade.fills = [_fill(_exec(price=80.0, t=datetime(2024, 1, 2)))]
        ib.placeOrder.return_value = trade
        with mock.patch.object(broker, "_ensure_connected", return_value=ib), \
             mock.patch("ib_insync.Stock"), \
             mock.patch("ib_insync.MarketOrder") as MO:
            broker.cancel_and_close("TQQQ", "100", 5, "short")
        MO.assert_called_once_with("BUY", 5)

    def test_no_fill_returns_none(self):
        ib = mock.Mock()
        ib.openOrders.return_value = []
        trade = mock.Mock()
        trade.order = mock.Mock(orderId=302)
        trade.fills = []  # never fills
        ib.placeOrder.return_value = trade
        with mock.patch.object(broker, "_ensure_connected", return_value=ib), \
             mock.patch("ib_insync.Stock"), \
             mock.patch("ib_insync.MarketOrder"):
            self.assertIsNone(broker.cancel_and_close("TQQQ", "100", 10, "long"))


class TestReconciliationReads(unittest.TestCase):
    def test_get_open_position_match(self):
        ib = mock.Mock()
        pos = mock.Mock()
        pos.contract.symbol = "TQQQ"
        pos.position = 10
        pos.avgCost = 81.5
        ib.positions.return_value = [pos]
        with mock.patch.object(broker, "_ensure_connected", return_value=ib):
            out = broker.get_open_position("TQQQ")
        self.assertEqual(out["qty"], 10)
        self.assertEqual(out["avg_price"], 81.5)
        self.assertAlmostEqual(out["market_value"], 815.0)

    def test_get_open_position_no_match(self):
        ib = mock.Mock()
        ib.positions.return_value = []
        with mock.patch.object(broker, "_ensure_connected", return_value=ib):
            self.assertIsNone(broker.get_open_position("TQQQ"))

    def test_get_account_parses_summary(self):
        ib = mock.Mock()
        ib.accountSummary.return_value = [
            mock.Mock(tag="NetLiquidation", value="100000"),
            mock.Mock(tag="TotalCashValue", value="50000"),
            mock.Mock(tag="BuyingPower", value="200000"),
            mock.Mock(tag="IgnoreMe", value="999"),
        ]
        with mock.patch.object(broker, "_ensure_connected", return_value=ib):
            snap = broker.get_account()
        self.assertEqual(snap.equity, 100000.0)
        self.assertEqual(snap.cash, 50000.0)
        self.assertEqual(snap.buying_power, 200000.0)


if __name__ == "__main__":
    unittest.main()
