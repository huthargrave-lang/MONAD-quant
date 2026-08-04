"""Regression and integrity tests for the ATM financing-pressure audit."""
import importlib.util
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "atm_424b5_lab", ROOT / "tools/atm_424b5_lab.py"
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)
LEDGER_SEED = ROOT / "docs/research/data/atm_fp01_gold_seed.json"
LEDGER_ARTIFACT = ROOT / "docs/research/data/atm_fp01_gold_ledger.json"


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


class AtmFp01LedgerTests(unittest.TestCase):
    def test_reviewed_seed_has_both_period_outcomes_and_a_quarantined_cumulative(self):
        artifact = LAB.build_atm_ledger_artifact(LAB.load_json(LEDGER_SEED))
        self.assertEqual(artifact["summary"]["issuer_count"], 3)
        self.assertEqual(artifact["summary"]["program_count"], 4)
        self.assertEqual(artifact["summary"]["positive_period_labels"], 1)
        self.assertEqual(artifact["summary"]["zero_period_labels"], 1)
        self.assertEqual(artifact["summary"]["cumulative_labels_quarantined"], 1)

    def test_labels_are_available_only_after_period_end_and_never_features(self):
        artifact = LAB.build_atm_ledger_artifact(LAB.load_json(LEDGER_SEED))
        for label in artifact["utilization_labels"]:
            self.assertGreater(label["label_available_at"][:10], label["period_end"])
            self.assertFalse(label["predictive_features_allowed"])
            self.assertTrue(label["interval_censored"])

    def test_cumulative_label_cannot_train_a_quarter_model(self):
        seed = copy.deepcopy(LAB.load_json(LEDGER_SEED))
        seed["utilization_labels"][-1]["quarter_trainable"] = True
        with self.assertRaisesRegex(ValueError, "cumulative label cannot train"):
            LAB.validate_atm_ledger_seed(seed)

    def test_exact_acceptance_clock_must_precede_tradable_clock(self):
        seed = copy.deepcopy(LAB.load_json(LEDGER_SEED))
        seed["sources"][1]["conservative_tradable_at"] = seed["sources"][1][
            "accepted_at"
        ]
        with self.assertRaisesRegex(ValueError, "must follow acceptance"):
            LAB.validate_atm_ledger_seed(seed)

    def test_sqlite_projection_is_rebuildable_and_exposes_only_period_labels(self):
        artifact = LAB.build_atm_ledger_artifact(LAB.load_json(LEDGER_SEED))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "atm.sqlite3"
            LAB.build_atm_ledger_db(artifact, path)
            con = sqlite3.connect(str(path))
            try:
                labels = con.execute(
                    "SELECT label_id, shares_sold FROM quarter_label_outcomes "
                    "ORDER BY label_id"
                ).fetchall()
                states = con.execute(
                    "SELECT program_id, status_json FROM latest_program_status "
                    "ORDER BY program_id"
                ).fetchall()
            finally:
                con.close()
            self.assertEqual(len(labels), 2)
            self.assertEqual({row[1] for row in labels}, {0, 262383})
            self.assertEqual(len(states), 4)
            with self.assertRaises(FileExistsError):
                LAB.build_atm_ledger_db(artifact, path)

    def test_committed_ledger_artifact_is_self_hashed(self):
        if not LEDGER_ARTIFACT.is_file():
            self.skipTest("ATM FP-01 ledger artifact has not been generated")
        artifact = json.loads(LEDGER_ARTIFACT.read_text())
        claimed = artifact.pop("artifact_sha256")
        self.assertEqual(claimed, LAB.sha256(artifact))
        self.assertFalse(artifact["training_features_built"])


if __name__ == "__main__":
    unittest.main()
