import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "research_event_ledger",
    ROOT / "tools" / "research_event_ledger.py",
)
ledger = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ledger
SPEC.loader.exec_module(ledger)
CTX_SPEC = importlib.util.spec_from_file_location("ctx_for_event_ledger", ROOT / "tools" / "ctx.py")
ctx = importlib.util.module_from_spec(CTX_SPEC)
sys.modules[CTX_SPEC.name] = ctx
CTX_SPEC.loader.exec_module(ctx)


class TestResearchEventLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "events.sqlite3"
        ledger.build_database(self.db, [ledger.DEFAULT_FIXTURE])

    def tearDown(self):
        self.tmp.cleanup()

    def test_fixture_has_two_monotone_exact_clock_revisions(self):
        fixture = ledger.load_fixture(ledger.DEFAULT_FIXTURE)
        revisions = fixture["revisions"]
        self.assertEqual([row["ordinal"] for row in revisions], [1, 2])
        self.assertEqual(revisions[0]["published_at"], "2023-12-08T20:00:00-05:00")
        self.assertEqual(revisions[1]["published_at"], "2023-12-12T18:00:00-05:00")
        self.assertEqual(revisions[1]["supersedes_revision_id"], revisions[0]["revision_id"])

    def test_initial_as_of_has_only_initial_twelve_events(self):
        result = ledger.events_as_of(self.db, "ndx-2023-12", "ndx-2023-12-r1")
        symbols = {row["announced_symbol"] for row in result["events"]}
        self.assertEqual(len(result["events"]), 12)
        self.assertEqual(
            sum(row["action"] == "addition" for row in result["events"]), 6
        )
        self.assertEqual(
            sum(row["action"] == "deletion" for row in result["events"]), 6
        )
        self.assertNotIn("TTWO", symbols)
        self.assertNotIn("SGEN", symbols)

    def test_revised_as_of_retains_initial_and_adds_update_pair(self):
        result = ledger.events_as_of(self.db, "ndx-2023-12", "ndx-2023-12-r2")
        symbols = {row["announced_symbol"] for row in result["events"]}
        self.assertEqual(len(result["events"]), 14)
        self.assertEqual(
            sum(row["action"] == "addition" for row in result["events"]), 7
        )
        self.assertEqual(
            sum(row["action"] == "deletion" for row in result["events"]), 7
        )
        self.assertTrue({"CDW", "TTWO", "ZM", "SGEN"}.issubset(symbols))

    def test_timeline_preserves_security_specific_first_tradable_clocks(self):
        timeline = ledger.revision_timeline(self.db, "ndx-2023-12")
        self.assertEqual(timeline[0]["first_tradable_at"], "2023-12-11T09:30:00-05:00")
        self.assertEqual(timeline[1]["first_tradable_at"], "2023-12-13T09:30:00-05:00")
        self.assertEqual(
            {row["announced_symbol"] for row in timeline[1]["introduced_events"]},
            {"TTWO", "SGEN"},
        )
        self.assertFalse(timeline[0]["raw_document_committed"])
        self.assertEqual(len(timeline[0]["evidence_sha256"]), 64)

    def test_database_is_delete_journal_projection_with_foreign_keys(self):
        con = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(con.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(
                con.execute(
                    "SELECT value FROM metadata WHERE key='journal_mode_policy'"
                ).fetchone()[0],
                "DELETE; WAL intentionally disabled",
            )
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            con.close()
        self.assertFalse(Path(str(self.db) + "-wal").exists())

    def test_build_refuses_repository_database(self):
        with self.assertRaisesRegex(ValueError, "inside the repository"):
            ledger.build_database(
                ROOT / "should-never-exist.sqlite3", [ledger.DEFAULT_FIXTURE]
            )

    def test_parameterized_as_of_does_not_execute_injected_batch(self):
        with self.assertRaises(KeyError):
            ledger.events_as_of(
                self.db, "ndx-2023-12' OR 1=1 --", "ndx-2023-12-r2"
            )

    def test_suggestion_tables_are_quarantined_and_append_only(self):
        con = sqlite3.connect(str(self.db))
        try:
            con.execute(
                """
                INSERT INTO suggestions(
                    suggestion_id, created_at, title, body, submitter_hash
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "suggestion:test",
                    "2026-07-24T00:00:00+00:00",
                    "Study index revision surprise",
                    "Test whether later membership revisions carry distinct information.",
                    None,
                ),
            )
            con.execute(
                """
                INSERT INTO suggestion_events(
                    suggestion_event_id, suggestion_id, sequence, event_type,
                    actor, note, created_at
                ) VALUES (?, ?, 1, 'submitted', 'anonymous', '', ?)
                """,
                (
                    "suggestion-event:test:1",
                    "suggestion:test",
                    "2026-07-24T00:00:00+00:00",
                ),
            )
            con.commit()
            with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                con.execute(
                    "UPDATE suggestions SET title='Changed title' "
                    "WHERE suggestion_id='suggestion:test'"
                )
            with self.assertRaisesRegex(sqlite3.IntegrityError, "cannot be deleted"):
                con.execute(
                    "DELETE FROM suggestions WHERE suggestion_id='suggestion:test'"
                )
        finally:
            con.close()

    def test_payload_and_html_are_public_read_models(self):
        payload = ledger.ledger_payload(self.db, "ndx-2023-12", "ndx-2023-12-r1")
        self.assertIn("disposable projection", payload["database_role"])
        rendered = ledger.render_events_html(payload)
        self.assertIn("Knowledge as of ndx-2023-12-r1", rendered)
        self.assertIn("MONAD research-event ledger", rendered)
        self.assertNotIn("<script", rendered.lower())

    def test_fixture_is_valid_json_and_database_summary_is_serializable(self):
        fixture = json.loads(ledger.DEFAULT_FIXTURE.read_text())
        ledger.validate_fixture(fixture)
        json.dumps(ledger.ledger_payload(self.db))

    def test_ctx_read_only_event_api_supports_as_of_revision(self):
        code, body, ctype = ctx._event_ledger_response(
            self.db,
            "/api/research-events/ndx-2023-12?revision=ndx-2023-12-r1",
        )
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "application/json; charset=utf-8")
        payload = json.loads(body)
        self.assertEqual(payload["as_of"]["as_of_revision_id"], "ndx-2023-12-r1")
        self.assertEqual(len(payload["as_of"]["events"]), 12)

    def test_ctx_event_page_is_read_only_and_unknown_batches_are_404(self):
        code, body, ctype = ctx._event_ledger_response(
            self.db, "/events?batch=ndx-2023-12&revision=ndx-2023-12-r2"
        )
        self.assertEqual((code, ctype), (200, "text/html; charset=utf-8"))
        self.assertIn("Knowledge as of ndx-2023-12-r2", body)
        code, _, _ = ctx._event_ledger_response(
            self.db, "/api/research-events/not-a-batch"
        )
        self.assertEqual(code, 404)
        code, body, _ = ctx._event_ledger_response(None, "/events")
        self.assertEqual(code, 404)
        self.assertIn("--event-db", body)

    def test_ctx_home_links_event_browser_only_when_configured(self):
        graph = {
            "F1": {
                "kind": "F",
                "status": "current",
                "title": "fixture",
            }
        }
        adjacency = {"F1": []}
        configured = ctx._render_served_graph_html(graph, adjacency, self.db)
        plain = ctx._render_served_graph_html(graph, adjacency)
        self.assertIn('href="/events"', configured)
        self.assertNotIn('href="/events"', plain)
        self.assertNotIn(str(self.db), configured)


if __name__ == "__main__":
    unittest.main()
