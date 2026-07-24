import copy
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sec_corporate_action_state_lab",
    ROOT / "tools" / "sec_corporate_action_state_lab.py",
)
state_lab = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = state_lab
SPEC.loader.exec_module(state_lab)
CTX_SPEC = importlib.util.spec_from_file_location(
    "ctx_for_sec_action_states", ROOT / "tools" / "ctx.py"
)
ctx = importlib.util.module_from_spec(CTX_SPEC)
sys.modules[CTX_SPEC.name] = ctx
CTX_SPEC.loader.exec_module(ctx)


class TestSecCorporateActionStateLab(unittest.TestCase):
    def setUp(self):
        self.fixture = state_lab.load_fixture()
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "sec-action-states.sqlite3"
        state_lab.build_database(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fixture_spans_parallel_state_dimensions(self):
        summary = state_lab.fixture_summary(self.fixture)
        self.assertEqual(summary["chain_count"], 3)
        self.assertEqual(summary["assertion_count"], 27)
        self.assertEqual(
            set(summary["dimension_counts"]),
            {
                "transaction",
                "listing",
                "reporting",
                "security_rights",
                "bankruptcy",
                "disclosure",
            },
        )
        self.assertEqual(summary["max_calendar_day_confirmation_lag"], 68)
        self.assertFalse(self.fixture["raw_documents_committed"])

    def test_all_sources_are_official_and_observation_order_is_contiguous(self):
        for chain in self.fixture["chains"]:
            self.assertEqual(
                [row["ordinal"] for row in chain["assertions"]],
                list(range(1, len(chain["assertions"]) + 1)),
            )
            self.assertTrue(
                all(
                    row["source"]["document_url"].startswith(
                        "https://www.sec.gov/"
                    )
                    for row in chain["assertions"]
                )
            )

    def test_twitter_completion_is_invisible_before_form25_acceptance(self):
        snapshot = state_lab.materialize_state(
            self.fixture,
            "cash-merger:TWTR:2022-10-27",
            "2022-10-28T08:30:00-04:00",
        )
        self.assertEqual(snapshot["visible_assertion_count"], 2)
        self.assertEqual(
            snapshot["state_vector"]["transaction"]["state_value"],
            "shareholder_approved",
        )
        self.assertNotIn("security_rights", snapshot["state_vector"])

    def test_future_removal_schedule_does_not_overwrite_effective_state(self):
        snapshot = state_lab.materialize_state(
            self.fixture,
            "cash-merger:TWTR:2022-10-27",
            "2022-10-28T09:00:00-04:00",
        )
        self.assertEqual(
            snapshot["knowledge_vector"]["listing"]["state_value"],
            "removal_scheduled",
        )
        self.assertNotIn("listing", snapshot["effective_state_vector"])
        self.assertEqual(
            snapshot["scheduled_transitions"][0]["status"], "future"
        )
        self.assertEqual(
            snapshot["state_vector"]["transaction"]["state_value"], "completed"
        )

    def test_issuer_completion_confirmation_enters_only_at_accepted_time(self):
        before = state_lab.materialize_state(
            self.fixture,
            "cash-merger:TWTR:2022-10-27",
            "2022-10-28T20:22:35-04:00",
        )
        after = state_lab.materialize_state(
            self.fixture,
            "cash-merger:TWTR:2022-10-27",
            "2022-10-28T20:22:36-04:00",
        )
        self.assertNotIn("disclosure", before["knowledge_vector"])
        self.assertEqual(
            after["knowledge_vector"]["disclosure"]["state_value"],
            "issuer_completion_8k_filed",
        )

    def test_activision_completion_precedes_form25_but_halt_is_only_requested(self):
        snapshot = state_lab.materialize_state(
            self.fixture,
            "cash-merger:ATVI:2023-10-13",
            "2023-10-13T08:50:00-04:00",
        )
        self.assertEqual(
            snapshot["knowledge_vector"]["transaction"]["state_value"],
            "completed",
        )
        self.assertEqual(
            snapshot["knowledge_vector"]["listing"]["state_value"],
            "trading_halt_requested",
        )
        self.assertNotIn("listing", snapshot["effective_state_vector"])
        self.assertNotIn("reporting", snapshot["knowledge_vector"])

    def test_bbby_form25_confirms_suspension_sixty_eight_days_late(self):
        snapshot = state_lab.materialize_state(
            self.fixture,
            "bankruptcy-cancellation:BBBYQ:2023-09-29",
            "2023-07-10T06:04:00-04:00",
        )
        suspended = next(
            row
            for row in snapshot["timeline"]
            if row["state_value"] == "trading_suspended"
        )
        self.assertEqual(suspended["lag"]["calendar_day_lag"], 68)
        self.assertFalse(suspended["predictive_for_downstream_transition"])
        self.assertEqual(
            snapshot["effective_state_vector"]["listing"]["state_value"],
            "trading_suspended",
        )

    def test_date_only_outcome_waits_until_next_day_in_effective_vector(self):
        same_day = state_lab.materialize_state(
            self.fixture,
            "bankruptcy-cancellation:BBBYQ:2023-09-29",
            "2023-09-29T16:30:00-04:00",
        )
        next_day = state_lab.materialize_state(
            self.fixture,
            "bankruptcy-cancellation:BBBYQ:2023-09-29",
            "2023-09-30T00:01:00-04:00",
        )
        self.assertEqual(
            same_day["knowledge_vector"]["security_rights"]["state_value"],
            "cancelled_without_consideration",
        )
        self.assertNotIn("security_rights", same_day["effective_state_vector"])
        self.assertEqual(
            next_day["effective_state_vector"]["security_rights"]["state_value"],
            "cancelled_without_consideration",
        )

    def test_validator_rejects_observation_time_reversal(self):
        bad = copy.deepcopy(self.fixture)
        bad["chains"][0]["assertions"][1]["observed_at"] = (
            "2022-01-01T00:00:00-05:00"
        )
        with self.assertRaisesRegex(ValueError, "ordered by observed_at"):
            state_lab.validate_fixture(bad)

    def test_validator_rejects_outcome_label_marked_predictive(self):
        bad = copy.deepcopy(self.fixture)
        row = bad["chains"][0]["assertions"][3]
        row["predictive_for_downstream_transition"] = True
        with self.assertRaisesRegex(ValueError, "only predictive_status"):
            state_lab.validate_fixture(bad)

    def test_database_is_strict_disposable_projection_with_integrity(self):
        con = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(con.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                con.execute("SELECT count(*) FROM action_chains").fetchone()[0],
                3,
            )
            self.assertEqual(
                con.execute("SELECT count(*) FROM state_assertions").fetchone()[0],
                27,
            )
            self.assertLess(
                con.execute("SELECT count(*) FROM sources").fetchone()[0], 27
            )
            self.assertEqual(
                con.execute(
                    "SELECT value FROM metadata WHERE key='decision_clock'"
                ).fetchone()[0],
                "observed_at",
            )
        finally:
            con.close()
        self.assertFalse(Path(str(self.db) + "-wal").exists())

    def test_database_refuses_repository_target(self):
        with self.assertRaisesRegex(ValueError, "inside the repository"):
            state_lab.build_database(ROOT / "never-write-sec-states.sqlite3")

    def test_assertions_are_append_only(self):
        con = sqlite3.connect(str(self.db))
        try:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                con.execute(
                    "UPDATE state_assertions SET state_value='x' "
                    "WHERE assertion_id='TWTR:agreement-announced:2022-04-25'"
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "cannot be deleted"):
                con.execute(
                    "DELETE FROM state_assertions "
                    "WHERE assertion_id='TWTR:agreement-announced:2022-04-25'"
                )
        finally:
            con.close()

    def test_database_as_of_filter_compares_absolute_time_not_iso_text(self):
        before = state_lab.ledger_payload(
            self.db,
            "cash-merger:ATVI:2023-10-13",
            "2023-10-13T12:34:51+00:00",
        )
        after = state_lab.ledger_payload(
            self.db,
            "cash-merger:ATVI:2023-10-13",
            "2023-10-13T12:34:53+00:00",
        )
        self.assertEqual(before["detail"]["visible_assertion_count"], 2)
        self.assertEqual(after["detail"]["visible_assertion_count"], 5)

    def test_payload_is_serializable_and_parameterized(self):
        payload = state_lab.ledger_payload(
            self.db,
            "cash-merger:TWTR:2022-10-27",
            "2022-10-28T09:00:00-04:00",
        )
        self.assertEqual(payload["detail"]["event_symbol"], "TWTR")
        json.dumps(payload)
        with self.assertRaises(KeyError):
            state_lab.ledger_payload(self.db, "' OR 1=1 --")

    def test_html_is_static_and_does_not_leak_database_path(self):
        payload = state_lab.ledger_payload(
            self.db, "bankruptcy-cancellation:BBBYQ:2023-09-29"
        )
        rendered = state_lab.render_html(payload)
        self.assertIn("SEC corporate-action state machine", rendered)
        self.assertIn("cancelled_without_consideration", rendered)
        self.assertNotIn("<script", rendered.lower())
        self.assertNotIn(str(self.db), rendered)

    def test_ctx_exposes_parameterized_point_in_time_routes(self):
        code, body, ctype = ctx._corporate_action_state_response(
            self.db,
            "/api/corporate-action-states/"
            "cash-merger%3ATWTR%3A2022-10-27"
            "?as_of=2022-10-28T09%3A00%3A00-04%3A00",
        )
        self.assertEqual((code, ctype), (200, "application/json; charset=utf-8"))
        payload = json.loads(body)
        self.assertEqual(payload["detail"]["visible_assertion_count"], 7)
        self.assertEqual(
            payload["detail"]["state_vector"]["transaction"]["state_value"],
            "completed",
        )
        code, _, _ = ctx._corporate_action_state_response(
            self.db, "/api/corporate-action-states/not-real"
        )
        self.assertEqual(code, 404)
        code, body, _ = ctx._corporate_action_state_response(
            None, "/corporate-action-states"
        )
        self.assertEqual(code, 404)
        self.assertIn("--corporate-action-state-db", body)

    def test_ctx_home_navigation_includes_state_browser_without_db_path(self):
        graph = {
            "F1": {
                "kind": "F",
                "status": "current",
                "title": "fixture",
            }
        }
        page = ctx._render_served_graph_html(
            graph,
            {"F1": []},
            event_db="/tmp/events.db",
            corporate_action_db="/tmp/actions.db",
            corporate_action_state_db=self.db,
        )
        self.assertIn('href="/corporate-action-states"', page)
        self.assertNotIn(str(self.db), page)


if __name__ == "__main__":
    unittest.main()
