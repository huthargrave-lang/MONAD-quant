"""Regression and integrity tests for the ATM financing-pressure audit."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "atm_424b5_lab", ROOT / "tools/atm_424b5_lab.py"
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)


class AtmFinancingPressureLabTests(unittest.TestCase):
    def test_program_supplements_are_collapsed_into_episodes(self):
        rows = [
            {"parsed_ticker": "ABC", "file_date": "2024-01-01", "accession": "a"},
            {"parsed_ticker": "ABC", "file_date": "2024-01-20", "accession": "b"},
            {"parsed_ticker": "ABC", "file_date": "2024-03-10", "accession": "c"},
            {"parsed_ticker": "XYZ", "file_date": "2024-01-02", "accession": "d"},
        ]
        self.assertEqual(
            [row["accession"] for row in LAB.episode_events(rows)],
            ["a", "c", "d"],
        )

    def test_event_return_rejects_late_price_coverage(self):
        event = {"ticker": "ABC", "file_date": "2024-01-02", "accession": "a"}
        prices = {
            "ABC": {"2024-07-25": 10.0, "2024-07-26": 9.0},
            "SPY": {"2024-07-25": 100.0, "2024-07-26": 101.0},
        }
        self.assertIsNone(
            LAB.financing_pressure_event_return(event, prices, horizons=(1,))
        )

    def test_event_return_uses_first_post_filing_close(self):
        event = {"ticker": "ABC", "file_date": "2024-01-05", "accession": "a"}
        prices = {
            "ABC": {"2024-01-08": 10.0, "2024-01-09": 9.0},
            "SPY": {"2024-01-08": 100.0, "2024-01-09": 101.0},
        }
        row = LAB.financing_pressure_event_return(event, prices, horizons=(1,))
        self.assertEqual(row["entry_date"], "2024-01-08")
        self.assertEqual(row["entry_lag_calendar_days"], 3)
        self.assertAlmostEqual(row["xs_1d"], -0.11)

    def test_committed_artifact_never_claims_confirmed_sales(self):
        path = ROOT / "docs/research/data/atm_financing_pressure_corrected_2024q1.json"
        if not path.is_file():
            self.skipTest("corrected artifact has not been generated")
        artifact = json.loads(path.read_text())
        self.assertFalse(artifact["confirmed_atm_program"])
        self.assertFalse(artifact["confirmed_atm_sales"])
        self.assertLessEqual(artifact["summary"]["max_entry_lag_calendar_days"], 7)
        self.assertEqual(artifact["source_class"], "424B5_phrase_hit")

    def test_committed_artifact_self_hash_and_sample_size_are_pinned(self):
        path = ROOT / "docs/research/data/atm_financing_pressure_corrected_2024q1.json"
        if not path.is_file():
            self.skipTest("corrected artifact has not been generated")
        artifact = json.loads(path.read_text())
        claimed = artifact.pop("artifact_sha256")
        self.assertEqual(claimed, LAB.sha256(artifact))
        self.assertEqual(artifact["input_unique_submissions"], 100)
        self.assertEqual(artifact["candidate_episodes"], 91)
        self.assertEqual(artifact["summary"]["priced_episodes"], 76)


if __name__ == "__main__":
    unittest.main()
