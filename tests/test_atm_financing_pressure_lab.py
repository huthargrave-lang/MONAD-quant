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
BIOCAT_FINANCE_SEED = ROOT / "docs/research/data/biocat_finance_01_gold_seed.json"
BIOCAT_FINANCE_ARTIFACT = ROOT / "docs/research/data/biocat_finance_01_gold_pilot.json"


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


class BiocatFinance01Tests(unittest.TestCase):
    def test_joined_fixture_preserves_components_and_rejects_brittle_product(self):
        artifact = LAB.build_biocat_finance_artifact(LAB.load_json(BIOCAT_FINANCE_SEED))
        cases = {row["issuer"]["ticker_at_cutoff"]: row for row in artifact["cases"]}
        self.assertEqual(cases["ACRX"]["derived"]["completion_slip_days"], 243)
        self.assertEqual(cases["SUPN"]["derived"]["completion_slip_days"], 366)
        self.assertEqual(cases["AXSM"]["derived"]["completion_slip_days"], 0)
        self.assertEqual(cases["AXSM"]["derived"]["prior_atm_utilization_fraction"], 0.402)
        self.assertEqual(cases["AXSM"]["derived"]["runway_gap_days"], 0)
        self.assertIsNone(cases["AXSM"]["derived"]["multiplicative_pressure"])
        self.assertIn("must not erase", cases["AXSM"]["derived"]["multiplicative_pressure_reason"])

    def test_financial_runway_is_derived_from_as_of_periods(self):
        artifact = LAB.build_biocat_finance_artifact(LAB.load_json(BIOCAT_FINANCE_SEED))
        cases = {row["issuer"]["ticker_at_cutoff"]: row for row in artifact["cases"]}
        self.assertAlmostEqual(cases["ACRX"]["derived"]["estimated_runway_days"], 1056.96, places=2)
        self.assertTrue(cases["SUPN"]["derived"]["cash_generating"])
        self.assertIsNone(cases["SUPN"]["derived"]["estimated_runway_days"])
        self.assertAlmostEqual(cases["AXSM"]["derived"]["estimated_runway_days"], 413.57, places=2)
        self.assertEqual(artifact["summary"]["cases_with_positive_runway_gap"], 0)

    def test_outcomes_and_non_exact_trial_labels_are_quarantined(self):
        artifact = LAB.build_biocat_finance_artifact(LAB.load_json(BIOCAT_FINANCE_SEED))
        for row in artifact["cases"]:
            self.assertGreater(row["outcome"]["public_at"], row["feature_cutoff_at"])
            self.assertFalse(row["outcome"]["predictive_features_allowed"])
        supn = next(row for row in artifact["cases"] if row["issuer"]["ticker_at_cutoff"] == "SUPN")
        self.assertEqual(supn["outcome"]["label_scope"], "program")
        self.assertFalse(supn["outcome"]["trainable"])

    def test_validator_rejects_future_sec_facts_and_bad_atm_arithmetic(self):
        seed = copy.deepcopy(LAB.load_json(BIOCAT_FINANCE_SEED))
        seed["cases"][0]["sources"]["sec_facts"]["available_at"] = "2017-01-01T09:30:00-05:00"
        with self.assertRaisesRegex(ValueError, "SEC facts cross"):
            LAB.validate_biocat_finance_seed(seed)
        seed = copy.deepcopy(LAB.load_json(BIOCAT_FINANCE_SEED))
        seed["cases"][2]["atm_features"]["remaining_capacity_usd"] = 30000000
        with self.assertRaisesRegex(ValueError, "ATM capacity does not reconcile"):
            LAB.validate_biocat_finance_seed(seed)

    def test_validator_requires_the_declared_source_domains(self):
        seed = copy.deepcopy(LAB.load_json(BIOCAT_FINANCE_SEED))
        seed["cases"][0]["sources"]["registry_history"]["url"] = (
            "https://example.com/history"
        )
        with self.assertRaisesRegex(ValueError, "clinicaltrials.gov"):
            LAB.validate_biocat_finance_seed(seed)

    def test_committed_biocat_finance_artifact_is_self_hashed(self):
        if not BIOCAT_FINANCE_ARTIFACT.is_file():
            self.skipTest("BIOCAT-FINANCE-01 artifact has not been generated")
        artifact = json.loads(BIOCAT_FINANCE_ARTIFACT.read_text())
        claimed = artifact.pop("artifact_sha256")
        self.assertEqual(claimed, LAB.sha256(artifact))
        self.assertFalse(artifact["return_labels_inspected"])
        self.assertFalse(artifact["model_trained"])


if __name__ == "__main__":
    unittest.main()
