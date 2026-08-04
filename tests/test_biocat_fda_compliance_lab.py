"""Offline integrity guards for the committed FDA pre-notice census."""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "docs" / "research" / "data" / "biocat_fda_pre_notice_census_2026.json"


class CommittedCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_population_matches_fda_table_capture(self):
        source = self.payload["sources"]["fda_pre_notices"]
        self.assertEqual(source["notice_rows"], 246)
        self.assertEqual(source["invalid_nct_tokens"], ["NCT027047734"])
        self.assertEqual(self.payload["aggregates"]["unique_nct_ids"], 314)

    def test_missing_registry_record_is_not_silently_dropped(self):
        missing = [row["nct_id"] for row in self.payload["rows"]
                   if row["registry_record_missing"]]
        self.assertEqual(missing, ["NCT02922592"])

    def test_every_hazard_has_horizon_specific_denominator(self):
        for name in ("submission_hazard", "qc_hazard", "posting_hazard"):
            hazard = self.payload["aggregates"][name]
            self.assertGreaterEqual(hazard["30"]["eligible"], hazard["365"]["eligible"])

    def test_formal_fda_table_matches_registry_violation_annotations(self):
        formal = self.payload["sources"]["fda_formal_notices"]
        self.assertTrue(formal["sets_match"])
        self.assertEqual(len(formal["published_nct_ids"]), 8)
        self.assertEqual(
            self.payload["aggregates"]["formal_violation_rows_submitted_within_180d"],
            0,
        )

    def test_causal_claim_is_explicitly_barred(self):
        self.assertEqual(
            self.payload["design"]["causal_status"],
            "DESCRIPTIVE_ONLY_TARGETED_POPULATION_NO_UNTREATED_CONTROL",
        )

    def test_provenance_contract_is_explicit(self):
        contract = self.payload["provenance_contract"]
        self.assertEqual(contract["trial_registry"], "ClinicalTrials.gov")
        self.assertEqual(contract["horizons"], [30, 60, 90, 180, 365])
        self.assertTrue(contract["source_at"])
        self.assertTrue(contract["first_seen"])
        self.assertTrue(contract["rights_tier"])


if __name__ == "__main__":
    unittest.main()
