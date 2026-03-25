"""Tests for the read-only monitoring dashboard."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

import live.dashboard as dashboard


class TestDashboardHelpers(unittest.TestCase):
    """Unit tests for dashboard staleness and timestamp helpers."""

    def test_minutes_ago_handles_none_and_bad_input(self):
        self.assertIsNone(dashboard._minutes_ago(None))
        self.assertIsNone(dashboard._minutes_ago("not-a-timestamp"))

    def test_stale_band_thresholds(self):
        self.assertEqual(dashboard._stale_band(None), ("Unknown", "red"))
        self.assertEqual(dashboard._stale_band(5.0), ("last trader cycle 5 min ago", "green"))
        self.assertEqual(dashboard._stale_band(40.0), ("last trader cycle 40 min ago", "yellow"))
        self.assertEqual(dashboard._stale_band(90.0), ("last trader cycle 90 min ago", "red"))


class TestDashboardRoutes(unittest.TestCase):
    """Integration-lite tests for FastAPI routes and read-only behavior."""

    def setUp(self):
        self.client = TestClient(dashboard.app)

    def test_health_route(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("utc", payload)

    def test_dashboard_page_renders(self):
        now = datetime.now(timezone.utc)
        with (
            patch("live.dashboard.state.get_monitor_status", return_value={"status": "ok", "last_cycle_time": now.isoformat(), "live_symbol": "TQQQ", "live_paper_mode": 1, "live_dry_run": 0, "cycle_action": "check_signal", "details": ""}),
            patch("live.dashboard.state.get_signal_snapshot", return_value={"signal": 1, "bar_close": 101.2, "updated_at": now.isoformat(), "bar_time": now.isoformat(), "rsi": 35.2, "vwap_zscore": -1.5, "momentum_signal": 1, "volume_signal": 1}),
            patch("live.dashboard.state.get_signal_history", return_value=[]),
            patch("live.dashboard.state.get_position", return_value=None),
            patch("live.dashboard.state.get_recent_trades", return_value=[]),
            patch("live.dashboard.state.get_recent_monitor_events", return_value=[]),
            patch("live.dashboard.state.get_exit_type_counts", return_value={}),
            patch("live.dashboard.state.get_account_snapshot", return_value={"ibkr_connected": True, "equity": 100000.0, "cash": 90000.0, "position_value": 10000.0, "buying_power": 180000.0, "updated_at": now.isoformat()}),
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Read-only dashboard", response.text)

    def test_dashboard_renders_with_trades_containing_none_return_pct(self):
        """Regression: return_pct=None in trade rows must not crash the template."""
        now = datetime.now(timezone.utc)
        trade_with_none = {
            "entry_time": now.isoformat(), "exit_time": now.isoformat(),
            "return_pct": None, "exit_type": "stop", "exit_price": None,
            "symbol": "TQQQ", "qty": 10, "bars_held": 3,
        }
        with (
            patch("live.dashboard.state.get_monitor_status", return_value={"status": "ok", "last_cycle_time": now.isoformat(), "live_symbol": "TQQQ", "live_paper_mode": 1, "live_dry_run": 0, "cycle_action": "check_signal", "details": ""}),
            patch("live.dashboard.state.get_signal_snapshot", return_value={"signal": 0, "bar_close": 80.0, "updated_at": now.isoformat(), "bar_time": now.isoformat(), "rsi": 50.0, "vwap_zscore": 0.0, "momentum_signal": 0, "volume_signal": 0}),
            patch("live.dashboard.state.get_signal_history", return_value=[]),
            patch("live.dashboard.state.get_position", return_value=None),
            patch("live.dashboard.state.get_recent_trades", return_value=[trade_with_none]),
            patch("live.dashboard.state.get_recent_monitor_events", return_value=[]),
            patch("live.dashboard.state.get_exit_type_counts", return_value={"stop": 1}),
            patch("live.dashboard.state.get_account_snapshot", return_value={"ibkr_connected": False, "equity": None, "cash": None, "position_value": None, "buying_power": None, "updated_at": None}),
        ):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_routes_are_get_only(self):
        for route in dashboard.app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set()) or set()
            if path in {"/", "/health"}:
                self.assertIn("GET", methods)
                self.assertFalse({"POST", "PUT", "PATCH", "DELETE"}.intersection(methods))


if __name__ == "__main__":
    unittest.main()
