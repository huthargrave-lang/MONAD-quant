import copy
import datetime as dt
import gzip
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sec_form25_population_lab",
    ROOT / "tools" / "sec_form25_population_lab.py",
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)
CTX_SPEC = importlib.util.spec_from_file_location(
    "ctx_for_form25_population", ROOT / "tools" / "ctx.py"
)
CTX = importlib.util.module_from_spec(CTX_SPEC)
sys.modules[CTX_SPEC.name] = CTX
CTX_SPEC.loader.exec_module(CTX)


SUBMISSION = """<SEC-DOCUMENT>0001354457-23-000768.txt
<ACCEPTANCE-DATETIME>20231013090106
<DOCUMENT>
<TYPE>25-NSE
<FILENAME>primary_doc.xml
<TEXT><XML>
<notificationOfRemoval>
<exchange><cik>0001354457</cik><entityName>Nasdaq Stock Market LLC</entityName></exchange>
<issuer><cik>0000718877</cik><entityName>Activision Blizzard, Inc.</entityName></issuer>
<descriptionClassSecurity>Common Stock</descriptionClassSecurity>
<ruleProvision>17 CFR 240.12d2-2(a)(3)</ruleProvision>
<signatureData><signatureDate>2023-10-13</signatureDate></signatureData>
</notificationOfRemoval>
</XML></TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-99.25
<FILENAME>reason.htm
<TEXT><p>The merger was completed.</p></TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
"""


class SecForm25PopulationLabTests(unittest.TestCase):
    def expected(self):
        return {
            "issuer_cik": "0000718877",
            "accession": "0001354457-23-000768",
        }

    def test_parse_submission_uses_exact_acceptance_clock(self):
        row = LAB.parse_submission(SUBMISSION, self.expected())
        self.assertEqual(row["accepted_at"], "2023-10-13T09:01:06-04:00")
        self.assertEqual(
            row["accepted_at_utc"], "2023-10-13T13:01:06+00:00"
        )
        self.assertEqual(row["market_window_eastern"], "pre_open")
        self.assertEqual(row["decision_clock"], "accepted_at")

    def test_parse_submission_extracts_identity_and_classes(self):
        row = LAB.parse_submission(SUBMISSION, self.expected())
        self.assertEqual(row["issuer_name"], "Activision Blizzard, Inc.")
        self.assertEqual(row["exchange_name"], "Nasdaq Stock Market LLC")
        self.assertEqual(row["security_family"], "common_equity")
        self.assertEqual(row["rule_family"], "a_3")
        self.assertEqual(row["reason_family"], "merger_or_acquisition")
        self.assertTrue(row["reason_exhibit_informative"])

    def test_parse_submission_rejects_subject_mismatch(self):
        expected = dict(self.expected())
        expected["issuer_cik"] = "0000000001"
        with self.assertRaisesRegex(ValueError, "subject CIK mismatch"):
            LAB.parse_submission(SUBMISSION, expected)

    def test_placeholder_reason_is_not_informative(self):
        text = SUBMISSION.replace(
            "<p>The merger was completed.</p>", "Form 25"
        )
        row = LAB.parse_submission(text, self.expected())
        self.assertFalse(row["reason_exhibit_informative"])
        self.assertEqual(row["reason_family"], "not_informative")

    def test_market_window_boundaries(self):
        self.assertEqual(
            LAB.market_window(dt.time(9, 29, 59)), "pre_open"
        )
        self.assertEqual(
            LAB.market_window(dt.time(9, 30, 0)), "regular_session"
        )
        self.assertEqual(
            LAB.market_window(dt.time(15, 59, 59)), "regular_session"
        )
        self.assertEqual(
            LAB.market_window(dt.time(16, 0, 0)), "post_close"
        )

    def test_security_classifier_prefers_instrument_over_underlying(self):
        self.assertEqual(
            LAB.classify_security(
                "Redeemable Warrants exercisable for Common Stock"
            ),
            "warrant_right_or_unit",
        )
        self.assertEqual(
            LAB.classify_security("Series A Preferred Shares"),
            "preferred_equity",
        )
        self.assertEqual(
            LAB.classify_security(
                "American Depositary Shares, each representing the right "
                "to receive one Ordinary Share"
            ),
            "common_equity",
        )

    def test_deterministic_sample_is_order_invariant_and_stratified(self):
        rows = []
        for quarter in ("2023Q1", "2023Q2"):
            for number in range(8):
                rows.append(
                    {
                        "quarter": quarter,
                        "accession": "0000000000-23-{:06d}".format(
                            number + (100 if quarter == "2023Q2" else 0)
                        ),
                    }
                )
        first = LAB.deterministic_sample(rows, 3)
        second = LAB.deterministic_sample(list(reversed(rows)), 3)
        self.assertEqual(first, second)
        counts = {}
        for row in first:
            counts[row["quarter"]] = counts.get(row["quarter"], 0) + 1
        self.assertEqual(counts, {"2023Q1": 3, "2023Q2": 3})

    def test_parse_master_index_filters_form(self):
        content = (
            "Description\n"
            "1354457|Nasdaq Stock Market LLC|25-NSE|2023-10-13|"
            "edgar/data/1354457/0001354457-23-000768.txt\n"
            "718877|Activision Blizzard, Inc.|25-NSE|2023-10-13|"
            "edgar/data/718877/0001354457-23-000768.txt\n"
            "718877|Activision Blizzard, Inc.|8-K|2023-10-13|"
            "edgar/data/718877/0001104659-23-108985.txt\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "master.gz"
            with gzip.open(path, "wt", encoding="latin-1") as handle:
                handle.write(content)
            rows = LAB.parse_master_index(path, "2023Q4")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["issuer_cik"], "0000718877")
        self.assertEqual(rows[0]["exchange_filer_cik"], "0001354457")
        self.assertEqual(rows[0]["quarter"], "2023Q4")

    def test_submission_url_uses_accession_directory(self):
        url = LAB.submission_url(
            {
                "issuer_cik": "0000718877",
                "exchange_filer_cik": "0001354457",
                "accession": "0001354457-23-000768",
            }
        )
        self.assertEqual(
            url,
            "https://www.sec.gov/Archives/edgar/data/1354457/"
            "000135445723000768/0001354457-23-000768.txt",
        )

    def test_master_index_does_not_assume_accession_owner_is_exchange(self):
        content = (
            "1143313|NYSE AMERICAN LLC|25-NSE|2023-07-11|"
            "edgar/data/1143313/0000876661-23-000581.txt\n"
            "1852767|Marti Technologies, Inc.|25-NSE|2023-07-11|"
            "edgar/data/1852767/0000876661-23-000581.txt\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "master.gz"
            with gzip.open(path, "wt", encoding="latin-1") as handle:
                handle.write(content)
            rows = LAB.parse_master_index(path, "2023Q3")
        self.assertEqual(rows[0]["exchange_filer_cik"], "0001143313")
        self.assertEqual(rows[0]["issuer_cik"], "0001852767")

    def test_validate_artifact_detects_tampering(self):
        sample = LAB.parse_submission(SUBMISSION, self.expected())
        sample.update(
            {
                "accession": "0001354457-23-000768",
                "quarter": "2023Q4",
                "filed_on": "2023-10-13",
            }
        )
        census = [
            {
                "accession": "0001354457-23-000768",
                "issuer_cik": "0000718877",
                "issuer_name_index": "Activision Blizzard, Inc.",
                "exchange_filer_name_index": "Nasdaq Stock Market LLC",
                "quarter": "2023Q4",
            }
        ]
        artifact = {
            "schema_version": 1,
            "raw_documents_committed": False,
            "census_manifest": census,
            "sample": [sample],
            "summary": LAB.summarize_records(census, [sample]),
            "census_manifest_sha256": LAB.sha256(census),
            "sample_sha256": LAB.sha256([sample]),
        }
        LAB.validate_artifact(artifact)
        broken = copy.deepcopy(artifact)
        broken["sample"][0]["accepted_at"] = "2023-10-13T09:02:00-04:00"
        with self.assertRaisesRegex(ValueError, "sample hash mismatch"):
            LAB.validate_artifact(broken)

    def test_sqlite_projection_is_filterable_and_complete(self):
        artifact = json.loads(LAB.DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "population.sqlite3"
            LAB.build_database(artifact, database)
            all_rows = LAB.population_payload(database, limit=10)
            common = LAB.population_payload(
                database,
                {"sampled": "yes", "security": "common_equity"},
                limit=200,
            )
        self.assertEqual(all_rows["total_matches"], 1141)
        self.assertEqual(common["total_matches"], 31)
        self.assertTrue(all_rows["read_only"])
        self.assertEqual(len(common["rows"]), 31)

    def test_sqlite_projection_rejects_mutation(self):
        artifact = json.loads(LAB.DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "population.sqlite3"
            LAB.build_database(artifact, database)
            connection = sqlite3.connect(str(database))
            try:
                with self.assertRaisesRegex(
                    sqlite3.IntegrityError, "append-only"
                ):
                    connection.execute(
                        "UPDATE filings SET sampled = 0 WHERE sampled = 1"
                    )
            finally:
                connection.close()

    def test_population_html_escapes_search_input(self):
        artifact = json.loads(LAB.DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "population.sqlite3"
            LAB.build_database(artifact, database)
            payload = LAB.population_payload(
                database, {"q": "<script>alert(1)</script>"}, limit=10
            )
            page = LAB.render_population_html(payload)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_database_cannot_be_written_inside_repository(self):
        artifact = json.loads(LAB.DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            LAB.build_database(
                artifact, ROOT / "docs" / "research" / "forbidden.sqlite3"
            )

    def test_ctx_exposes_filterable_read_only_population_routes(self):
        artifact = json.loads(LAB.DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "population.sqlite3"
            LAB.build_database(artifact, database)
            code, body, ctype = CTX._form25_population_response(
                database,
                "/api/form25-population?sampled=yes&"
                "security=common_equity&limit=1",
            )
            page_code, page, _ = CTX._form25_population_response(
                database, "/form25-population?exchange=Nasdaq%20Stock%20Market%20LLC"
            )
        payload = json.loads(body)
        self.assertEqual(code, 200)
        self.assertEqual(ctype, "application/json; charset=utf-8")
        self.assertEqual(payload["total_matches"], 31)
        self.assertTrue(payload["read_only"])
        self.assertEqual(page_code, 200)
        self.assertIn("SEC Form 25-NSE population", page)
        self.assertNotIn(str(database), page)

    def test_ctx_home_navigation_links_population_without_leaking_path(self):
        page = CTX._render_served_graph_html(
            {}, {}, form25_population_db="/private/tmp/secret.sqlite3"
        )
        self.assertIn('href="/form25-population"', page)
        self.assertNotIn("/private/tmp/secret.sqlite3", page)


if __name__ == "__main__":
    unittest.main()
