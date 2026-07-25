import copy
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "corporate_action_outcome_lab",
    ROOT / "tools" / "corporate_action_outcome_lab.py",
)
ca = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ca
SPEC.loader.exec_module(ca)
CTX_SPEC = importlib.util.spec_from_file_location(
    "ctx_for_corporate_actions", ROOT / "tools" / "ctx.py"
)
ctx = importlib.util.module_from_spec(CTX_SPEC)
sys.modules[CTX_SPEC.name] = ctx
CTX_SPEC.loader.exec_module(ctx)


class TestCorporateActionOutcomeLab(unittest.TestCase):
    def setUp(self):
        self.fixture = ca.load_fixture()
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "corporate-actions.sqlite3"
        ca.build_database(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def action(self, action_id):
        return ca._fixture_action(self.fixture, action_id)

    def test_fixture_spans_five_distinct_outcome_types(self):
        self.assertEqual(len(self.fixture["actions"]), 8)
        self.assertEqual(
            {row["action_type"] for row in self.fixture["actions"]},
            ca.ACTION_TYPES,
        )
        self.assertTrue(
            all(
                row["source"]["url"].startswith("https://www.sec.gov/")
                for row in self.fixture["actions"]
            )
        )
        self.assertFalse(self.fixture["raw_documents_committed"])

    def test_cash_merger_resolves_fixed_terminal_value_and_return(self):
        action = self.action("cash-merger:SGEN:2023-12-14")
        result = ca.resolve_terminal_return(action, 228.0, {})
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["terminal_value_usd_per_subject_share"], 229.0)
        self.assertAlmostEqual(result["terminal_return"], 229.0 / 228.0 - 1)

    def test_stock_merger_continues_wealth_through_successor(self):
        action = self.action("stock-merger:XLNX:2022-02-14")
        successor = action["terms"]["successor_security_id"]
        result = ca.resolve_terminal_value(action, {successor: 100.0})
        self.assertEqual(result["status"], "resolved")
        self.assertAlmostEqual(
            result["terminal_value_usd_per_subject_share"], 172.34
        )
        self.assertEqual(result["components"][0]["leg_type"], "successor_stock")

    def test_spinoff_keeps_parent_and_distributed_child(self):
        action = self.action("spinoff:GE-GEV:2024-04-02")
        result = ca.resolve_terminal_value(
            action,
            {
                action["subject"]["security_id"]: 120.0,
                action["terms"]["distributed_security_id"]: 200.0,
            },
        )
        self.assertEqual(result["status"], "resolved")
        self.assertAlmostEqual(
            result["terminal_value_usd_per_subject_share"], 170.0
        )
        self.assertEqual(
            [row["leg_type"] for row in result["components"]],
            ["retained_parent", "distributed_security"],
        )

    def test_ticker_change_is_identity_continuity_not_return_event(self):
        action = self.action("ticker-change:FB-META:2022-06-09")
        result = ca.resolve_terminal_value(
            action, {action["subject"]["security_id"]: 190.0}
        )
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["terminal_value_usd_per_subject_share"], 190.0)
        self.assertEqual(result["components"][0]["leg_type"], "identity_continuity")

    def test_bankruptcy_zero_requires_explicit_no_consideration_evidence(self):
        action = self.action("cancellation:BBBYQ:2023-09-29")
        result = ca.resolve_terminal_value(action, {})
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["terminal_value_usd_per_subject_share"], 0.0)
        self.assertEqual(
            result["components"][0]["leg_type"], "cancellation_rights"
        )

        incomplete = copy.deepcopy(action)
        incomplete["terms"]["equity_canceled_without_consideration"] = False
        incomplete["terms"]["issuer_stated_no_value"] = False
        incomplete["terms"]["cash_usd_per_share"] = None
        incomplete["outcome_model"]["label_type"] = (
            "canceled_security_rights_pending_distribution_review"
        )
        incomplete["outcome_model"]["value_completeness"] = (
            "insufficient_for_numeric_terminal_value"
        )
        unresolved = ca.resolve_terminal_value(incomplete, {})
        self.assertEqual(unresolved["status"], "unresolved")
        self.assertIsNone(unresolved["terminal_value_usd_per_subject_share"])

    def test_missing_successor_price_is_loudly_unresolved(self):
        action = self.action("stock-merger:XLNX:2022-02-14")
        result = ca.resolve_terminal_value(action, {})
        self.assertEqual(result["status"], "unresolved")
        self.assertIn("missing price", result["unresolved"][0])

    def test_invalid_prices_fail_closed(self):
        action = self.action("stock-merger:XLNX:2022-02-14")
        successor = action["terms"]["successor_security_id"]
        with self.assertRaisesRegex(ValueError, "invalid price"):
            ca.resolve_terminal_value(action, {successor: float("nan")})
        with self.assertRaisesRegex(ValueError, "pre_effective_price"):
            ca.resolve_terminal_return(action, 0.0, {successor: 1.0})

    def test_database_is_atomic_read_projection_with_integrity(self):
        con = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(con.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                con.execute("SELECT count(*) FROM corporate_actions").fetchone()[0],
                8,
            )
            self.assertEqual(
                con.execute(
                    "SELECT value FROM metadata WHERE key='raw_documents_committed'"
                ).fetchone()[0],
                "false",
            )
        finally:
            con.close()
        self.assertFalse(Path(str(self.db) + "-wal").exists())

    def test_database_refuses_repository_target(self):
        with self.assertRaisesRegex(ValueError, "inside the repository"):
            ca.build_database(ROOT / "never-write-corporate-actions.sqlite3")

    def test_corporate_action_rows_are_append_only(self):
        con = sqlite3.connect(str(self.db))
        try:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                con.execute(
                    "UPDATE corporate_actions SET event_symbol='X' "
                    "WHERE logical_action_id='cash-merger:SGEN:2023-12-14'"
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "cannot be deleted"):
                con.execute(
                    "DELETE FROM corporate_actions "
                    "WHERE logical_action_id='cash-merger:SGEN:2023-12-14'"
                )
        finally:
            con.close()

    def test_payload_is_serializable_and_parameterized(self):
        payload = ca.ledger_payload(
            self.db, "stock-merger:XLNX:2022-02-14"
        )
        self.assertEqual(len(payload["actions"]), 8)
        self.assertEqual(payload["detail"]["event_symbol"], "XLNX")
        self.assertEqual(payload["detail"]["legs"][0]["symbol"], "AMD")
        json.dumps(payload)
        with self.assertRaises(KeyError):
            ca.ledger_payload(self.db, "' OR 1=1 --")

    def test_html_is_static_read_model(self):
        payload = ca.ledger_payload(self.db, "spinoff:GE-GEV:2024-04-02")
        rendered = ca.render_html(payload)
        self.assertIn("Corporate-action outcome ledger", rendered)
        self.assertIn("retained_parent", rendered)
        self.assertNotIn("<script", rendered.lower())
        self.assertNotIn(str(self.db), rendered)

    def test_ctx_exposes_parameterized_read_only_corporate_action_routes(self):
        code, body, ctype = ctx._corporate_action_response(
            self.db,
            "/api/corporate-actions/stock-merger%3AXLNX%3A2022-02-14",
        )
        self.assertEqual((code, ctype), (200, "application/json; charset=utf-8"))
        self.assertEqual(json.loads(body)["detail"]["event_symbol"], "XLNX")
        code, body, ctype = ctx._corporate_action_response(
            self.db, "/corporate-actions?id=spinoff%3AGE-GEV%3A2024-04-02"
        )
        self.assertEqual((code, ctype), (200, "text/html; charset=utf-8"))
        self.assertIn("retained_parent", body)
        code, _, _ = ctx._corporate_action_response(
            self.db, "/api/corporate-actions/not-real"
        )
        self.assertEqual(code, 404)
        code, body, _ = ctx._corporate_action_response(None, "/corporate-actions")
        self.assertEqual(code, 404)
        self.assertIn("--corporate-action-db", body)

    def test_ctx_home_navigation_does_not_leak_database_paths(self):
        graph = {
            "F1": {
                "kind": "F",
                "status": "current",
                "title": "fixture",
            }
        }
        page = ctx._render_served_graph_html(
            graph, {"F1": []}, event_db="/tmp/events.db",
            corporate_action_db=self.db
        )
        self.assertIn('href="/events"', page)
        self.assertIn('href="/corporate-actions"', page)
        self.assertNotIn(str(self.db), page)

    def test_provider_coverage_uses_candidate_symbol_fallback(self):
        sessions = {
            "META": pd.DataFrame(
                {"Close": [190.0, 195.0]},
                index=pd.to_datetime(["2022-06-08", "2022-06-09"]),
            ),
            "GE": pd.DataFrame(
                {"Close": [140.0, 142.0]},
                index=pd.to_datetime(["2024-04-01", "2024-04-02"]),
            ),
            "GEV": pd.DataFrame(
                {"Close": [130.0]},
                index=pd.to_datetime(["2024-04-02"]),
            ),
            "AMD": pd.DataFrame(
                {"Close": [114.0]},
                index=pd.to_datetime(["2022-02-14"]),
            ),
        }

        def downloader(symbol, _start, _end):
            return sessions.get(symbol, pd.DataFrame())

        result = ca.audit_provider_coverage(self.fixture, downloader)
        self.assertEqual(len(result["coverage_decision_sha256"]), 64)
        meta = next(
            row for row in result["actions"] if row["event_symbol"] == "FB"
        )
        old_role = next(
            row
            for row in meta["queries"]
            if row["role"] == "old_symbol_pre_effective"
        )
        self.assertTrue(old_role["resolved"])
        self.assertEqual(old_role["selected_symbol"], "META")
        self.assertEqual(
            [row["symbol"] for row in old_role["attempts"]], ["FB", "META"]
        )
        ge = next(row for row in result["actions"] if row["event_symbol"] == "GE")
        self.assertTrue(ge["complete"])
        cash_mergers = [
            row
            for row in result["actions"]
            if row["action_type"] == "cash_merger"
        ]
        self.assertTrue(all(not row["complete"] for row in cash_mergers))

    def test_retained_coverage_artifact_keeps_survivorship_failure_loud(self):
        artifact = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "ca00_free_provider_coverage.json"
            ).read_text()
        )
        self.assertEqual(artifact["resolved_price_roles"], 7)
        self.assertEqual(artifact["required_price_roles"], 12)
        self.assertEqual(artifact["actions_complete"], 3)
        self.assertEqual(
            len(set(artifact["paired_coverage_decision_sha256"])), 1
        )
        cash = [
            row
            for row in artifact["action_decisions"]
            if row["action_type"] == "cash_merger"
        ]
        self.assertTrue(all(not row["complete"] for row in cash))
        cancellation = next(
            row
            for row in artifact["action_decisions"]
            if row["action_type"] == "bankruptcy_cancellation"
        )
        self.assertEqual(cancellation["resolved"], ["subject_pre_effective:BBBY"])


if __name__ == "__main__":
    unittest.main()
