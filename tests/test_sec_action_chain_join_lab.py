import copy
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sec_action_chain_join_lab",
    ROOT / "tools" / "sec_action_chain_join_lab.py",
)
LAB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAB)


def population():
    sample = [
        {
            "security_family": "common_equity",
            "issuer_cik": "0000718877",
            "issuer_name": "Activision Blizzard, Inc.",
            "accession": "0001354457-23-000768",
            "filed_on": "2023-10-13",
            "accepted_at": "2023-10-13T09:01:06-04:00",
            "exchange_name": "Nasdaq Stock Market LLC",
            "rule_family": "a_3",
            "reason_family": "not_informative",
        },
        {
            "security_family": "debt_or_note",
            "issuer_cik": "0000000002",
            "issuer_name": "Excluded Debt",
            "accession": "0000000002-23-000001",
            "filed_on": "2023-10-13",
            "accepted_at": "2023-10-13T10:00:00-04:00",
            "exchange_name": "NYSE",
            "rule_family": "a_2",
            "reason_family": "redemption_or_maturity",
        },
    ]
    return {
        "fixture_id": "population-test",
        "sample_sha256": LAB.sha256(sample),
        "sample": sample,
    }


class SecActionChainJoinLabTests(unittest.TestCase):
    def write_index(self, directory):
        path = Path(directory) / "master.gz"
        content = (
            "718877|Activision Blizzard, Inc.|8-K|2023-10-13|"
            "edgar/data/718877/0001104659-23-108985.txt\n"
            "718877|Activision Blizzard, Inc.|15-12G|2023-10-23|"
            "edgar/data/718877/0001104659-23-110841.txt\n"
            "718877|Activision Blizzard, Inc.|10-Q|2023-10-31|"
            "edgar/data/718877/0000000000-23-000001.txt\n"
            "2|Excluded Debt|8-K|2023-10-13|"
            "edgar/data/2/0000000002-23-000002.txt\n"
        )
        with gzip.open(path, "wt", encoding="latin-1") as handle:
            handle.write(content)
        return path

    def test_discovery_uses_only_common_equity_and_relevant_forms(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_index(tmp)
            manifest = LAB.discover_candidates(population(), [path])
        self.assertEqual(manifest["summary"]["seed_chains"], 1)
        chain = manifest["chains"][0]
        self.assertEqual(chain["candidate_count"], 2)
        self.assertEqual(
            {item["form_type"] for item in chain["candidates"]},
            {"8-K", "15-12G"},
        )
        self.assertEqual(chain["outcome_status"], "unreviewed")
        self.assertIsNone(chain["outcome_label"])

    def test_same_day_8k_ranks_before_later_form15(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_index(tmp)
            manifest = LAB.discover_candidates(population(), [path])
        candidates = manifest["chains"][0]["candidates"]
        self.assertEqual(candidates[0]["form_type"], "8-K")
        self.assertEqual(candidates[0]["calendar_day_offset_from_form25"], 0)

    def test_filing_url_uses_subject_archive_directory(self):
        self.assertEqual(
            LAB.filing_url(
                "edgar/data/718877/0001104659-23-108985.txt"
            ),
            "https://www.sec.gov/Archives/edgar/data/718877/"
            "000110465923108985/0001104659-23-108985.txt",
        )

    def test_manifest_tampering_fails_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_index(tmp)
            manifest = LAB.discover_candidates(population(), [path])
        LAB.validate_manifest(manifest)
        broken = copy.deepcopy(manifest)
        broken["chains"][0]["outcome_label"] = "cash_merger"
        with self.assertRaisesRegex(
            ValueError, "outcome_label must be null"
        ):
            LAB.validate_manifest(broken)

    def test_content_selection_preserves_same_day_report_and_form15(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_index(tmp)
            manifest = LAB.discover_candidates(population(), [path])
        selected = LAB.select_content_candidates(manifest["chains"][0], 3)
        self.assertEqual(
            [item["form_type"] for item in selected], ["8-K", "15-12G"]
        )

    def test_content_selection_preserves_nearest_report_on_both_sides(self):
        chain = {
            "candidates": [
                {
                    "accession": "0000000001-23-000001",
                    "form_type": "8-K",
                    "calendar_day_offset_from_form25": -2,
                    "candidate_score": 99998,
                },
                {
                    "accession": "0000000001-23-000002",
                    "form_type": "8-K",
                    "calendar_day_offset_from_form25": 3,
                    "candidate_score": 99997,
                },
                {
                    "accession": "0000000001-23-000003",
                    "form_type": "8-K",
                    "calendar_day_offset_from_form25": 10,
                    "candidate_score": 99990,
                },
            ]
        }
        selected = LAB.select_content_candidates(chain, 4)
        self.assertEqual(
            [item["accession"] for item in selected],
            ["0000000001-23-000001", "0000000001-23-000002"],
        )

    def test_submission_evidence_uses_clock_without_asserting_outcome(self):
        payload = b"""<SEC-DOCUMENT>0001104659-23-108985.txt
<ACCEPTANCE-DATETIME>20231013083452
ACCESSION NUMBER: 0001104659-23-108985
<TEXT>The parties consummated the merger. Each share was converted into
the right to receive $95.00 in cash per share without interest.</TEXT>
"""
        evidence = LAB.parse_submission_evidence(
            payload, "0001104659-23-108985"
        )
        self.assertEqual(
            evidence["accepted_at"], "2023-10-13T08:34:52-04:00"
        )
        self.assertTrue(evidence["term_flags"]["completion_language"])
        self.assertTrue(
            evidence["term_flags"]["holder_conversion_language"]
        )
        self.assertEqual(evidence["cash_per_share_candidates"], ["95.00"])
        self.assertNotIn("outcome_label", evidence)

    def test_primary_material_source_reports_order_and_ignores_form15(self):
        sources = [
            {
                "accession": "0000000001-23-000001",
                "form_type": "15-12G",
                "accepted_at": "2023-10-23T17:00:00-04:00",
                "term_flags": {key: False for key in LAB.TERM_PATTERNS},
            },
            {
                "accession": "0000000001-23-000002",
                "form_type": "8-K",
                "accepted_at": "2023-10-13T08:34:52-04:00",
                "term_flags": {
                    key: key == "holder_conversion_language"
                    for key in LAB.TERM_PATTERNS
                },
            },
        ]
        primary = LAB.primary_material_source_candidate(
            "2023-10-13T09:01:06-04:00", sources
        )
        self.assertEqual(primary["order"], "issuer_source_before_exchange")
        self.assertEqual(primary["issuer_minus_exchange_seconds"], -1574)
        self.assertTrue(primary["candidate_not_outcome_confirmation"])

    def test_reviewed_fixed_cash_seed_is_content_linked_and_balanced_by_order(self):
        evidence = json.loads(
            LAB.DEFAULT_EVIDENCE_OUTPUT.read_text(encoding="utf-8")
        )
        spec = json.loads(
            LAB.DEFAULT_REVIEW_SPEC.read_text(encoding="utf-8")
        )
        fixture = LAB.build_reviewed_fixture(evidence, spec)
        LAB.validate_reviewed_fixture(fixture)
        self.assertEqual(fixture["summary"]["reviewed_chains"], 12)
        self.assertEqual(
            fixture["summary"]["source_order"],
            {
                "exchange_before_issuer_source": 6,
                "issuer_source_before_exchange": 6,
            },
        )
        amounts = {
            item["issuer_name"]: item["consideration"]["cash_per_share"]
            for item in fixture["reviewed_chains"]
        }
        self.assertEqual(amounts["REATA PHARMACEUTICALS INC"], "172.50")
        self.assertEqual(amounts["Sumo Logic, Inc."], "12.05")
        self.assertTrue(
            all(
                item["predictive_for_outcome"] is False
                for item in fixture["reviewed_chains"]
            )
        )

    def test_review_spec_rejects_nonpositive_consideration(self):
        evidence = json.loads(
            LAB.DEFAULT_EVIDENCE_OUTPUT.read_text(encoding="utf-8")
        )
        spec = json.loads(
            LAB.DEFAULT_REVIEW_SPEC.read_text(encoding="utf-8")
        )
        broken = copy.deepcopy(spec)
        broken["entries"][0]["consideration"]["cash_per_share"] = "0"
        with self.assertRaisesRegex(
            ValueError, "cash_per_share must be positive"
        ):
            LAB.build_reviewed_fixture(evidence, broken)

    def test_diverse_reviewed_seed_preserves_rights_legs_and_uncertainty(self):
        evidence = json.loads(
            LAB.DEFAULT_EVIDENCE_OUTPUT.read_text(encoding="utf-8")
        )
        spec = json.loads(
            LAB.DEFAULT_DIVERSE_REVIEW_SPEC.read_text(encoding="utf-8")
        )
        fixture = LAB.build_diverse_reviewed_fixture(evidence, spec)
        LAB.validate_diverse_reviewed_fixture(fixture)
        self.assertEqual(fixture["summary"]["reviewed_chains"], 6)
        self.assertEqual(
            fixture["summary"]["outcome_type"],
            {
                "bankruptcy_unresolved_at_source": 1,
                "bankruptcy_zero_confirmed": 1,
                "fixed_cash_plus_cvr": 1,
                "successor_equity_conversion": 3,
            },
        )
        by_name = {
            item["issuer_name"]: item
            for item in fixture["reviewed_chains"]
        }
        self.assertIsNone(
            by_name["Venator Materials PLC"]["terms"]["terminal_value"]
        )
        self.assertEqual(
            by_name["RVL Pharmaceuticals plc"]["terms"]["terminal_value"],
            "0.00",
        )
        self.assertEqual(
            by_name["PARDES BIOSCIENCES, INC."]["terms"]["cvr_per_share"],
            "1",
        )

    def test_diverse_review_rejects_invented_unresolved_value(self):
        evidence = json.loads(
            LAB.DEFAULT_EVIDENCE_OUTPUT.read_text(encoding="utf-8")
        )
        spec = json.loads(
            LAB.DEFAULT_DIVERSE_REVIEW_SPEC.read_text(encoding="utf-8")
        )
        broken = copy.deepcopy(spec)
        venator = next(
            entry
            for entry in broken["entries"]
            if entry["outcome_type"] == "bankruptcy_unresolved_at_source"
        )
        venator["terms"]["terminal_value"] = "0.00"
        with self.assertRaisesRegex(
            ValueError, "cannot invent terminal value"
        ):
            LAB.build_diverse_reviewed_fixture(evidence, broken)


if __name__ == "__main__":
    unittest.main()
