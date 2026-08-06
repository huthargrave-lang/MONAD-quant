"""Integrity tests for the OPPORTUNISTIC-ATM-01 selected forward pilot."""
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "atm_424b5_lab_opportunistic", ROOT / "tools/atm_424b5_lab.py"
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)
SEED = ROOT / "docs/research/data/opportunistic_atm_01_gold_seed.json"
ARTIFACT = ROOT / "docs/research/data/opportunistic_atm_01_gold_pilot.json"


class OpportunisticAtm01Tests(unittest.TestCase):
    def test_selected_forward_pilot_separates_occurrence_and_instrument(self):
        artifact = LAB.build_opportunistic_atm_artifact(LAB.load_json(SEED))
        self.assertEqual(artifact["summary"]["case_count"], 3)
        self.assertEqual(artifact["summary"]["latest_high_opportunity_cases"], 2)
        self.assertEqual(artifact["summary"]["high_opportunity_cases_with_financing"], 2)
        self.assertEqual(
            artifact["summary"]["instrument_counts"],
            {"atm": 1, "none": 1, "underwritten": 1},
        )
        self.assertFalse(artifact["population_inference_allowed"])
        self.assertFalse(artifact["financing_motive_labels_created"])
        rytm = next(row for row in artifact["cases"] if row["issuer"]["ticker_at_cutoff"] == "RYTM")
        self.assertTrue(rytm["outcome"]["amount_interval_censored"])

    def test_market_opportunity_is_recomputed_and_can_refresh_after_event(self):
        artifact = LAB.build_opportunistic_atm_artifact(LAB.load_json(SEED))
        cases = {row["issuer"]["ticker_at_cutoff"]: row for row in artifact["cases"]}
        self.assertEqual(cases["RYTM"]["derived"]["latest_opportunity_state"], "high")
        self.assertEqual(cases["VKTX"]["derived"]["latest_opportunity_state"], "low")
        srrk_states = [
            item["derived"]["opportunity_state"] for item in cases["SRRK"]["market_snapshots"]
        ]
        self.assertEqual(srrk_states, ["low", "high"])
        self.assertAlmostEqual(
            cases["SRRK"]["market_snapshots"][-1]["derived"]["xbi_excess_return_63s"],
            3.329334,
            places=6,
        )

    def test_runway_and_execution_capacity_are_transparent(self):
        artifact = LAB.build_opportunistic_atm_artifact(LAB.load_json(SEED))
        cases = {row["issuer"]["ticker_at_cutoff"]: row for row in artifact["cases"]}
        self.assertAlmostEqual(cases["RYTM"]["derived"]["estimated_runway_days"], 860.31, places=2)
        self.assertAlmostEqual(cases["VKTX"]["derived"]["estimated_runway_days"], 4503.53, places=2)
        self.assertAlmostEqual(cases["SRRK"]["derived"]["estimated_runway_days"], 350.27, places=2)
        self.assertIsNone(cases["SRRK"]["derived"]["remaining_atm_capacity_to_market_cap"])
        self.assertGreater(
            cases["SRRK"]["derived"]["financing_net_proceeds_in_median_20s_dollar_volume_days"],
            40,
        )

    def test_outcomes_are_later_and_motive_is_never_ground_truth(self):
        artifact = LAB.build_opportunistic_atm_artifact(LAB.load_json(SEED))
        for row in artifact["cases"]:
            self.assertGreater(row["outcome"]["label_available_at"], row["feature_cutoff_at"])
            self.assertFalse(row["outcome"]["predictive_features_allowed"])
            self.assertEqual(row["outcome"]["financing_motive_label"], "latent_not_ground_truth")
        vktx = next(row for row in artifact["cases"] if row["issuer"]["ticker_at_cutoff"] == "VKTX")
        self.assertEqual(vktx["outcome"]["observed_calendar_days"], 68)
        self.assertNotEqual(vktx["outcome"]["observed_calendar_days"], 90)

    def test_validator_rejects_leakage_and_unsupported_zero_label(self):
        seed = copy.deepcopy(LAB.load_json(SEED))
        seed["cases"][0]["market_snapshots"][0]["available_at"] = "2024-11-07T16:05:00-05:00"
        with self.assertRaisesRegex(ValueError, "initial market state crosses cutoff"):
            LAB.validate_opportunistic_atm_seed(seed)
        seed = copy.deepcopy(LAB.load_json(SEED))
        seed["cases"][2]["market_snapshots"][1]["available_at"] = "2024-10-07T17:05:00-04:00"
        with self.assertRaisesRegex(ValueError, "latest market snapshot crosses event"):
            LAB.validate_opportunistic_atm_seed(seed)
        seed = copy.deepcopy(LAB.load_json(SEED))
        seed["cases"][1]["outcome"]["zero_atm_reconciliation"]["end_cumulative_shares"] += 1
        with self.assertRaisesRegex(ValueError, "compatible cumulative ATM evidence"):
            LAB.validate_opportunistic_atm_seed(seed)
        seed = copy.deepcopy(LAB.load_json(SEED))
        seed["cases"][2]["market_snapshots"][1].pop("material_event_source_id")
        with self.assertRaisesRegex(ValueError, "refresh lacks a material-event source"):
            LAB.validate_opportunistic_atm_seed(seed)

    def test_unknown_remaining_capacity_cannot_subtract_net_from_gross(self):
        seed = copy.deepcopy(LAB.load_json(SEED))
        seed["cases"][2]["atm_features"]["capacity_quality"] = "gross_less_net"
        with self.assertRaisesRegex(ValueError, "explicit reason"):
            LAB.validate_opportunistic_atm_seed(seed)

    def test_committed_artifact_is_self_hashed(self):
        if not ARTIFACT.is_file():
            self.skipTest("OPPORTUNISTIC-ATM-01 artifact has not been generated")
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        claimed = artifact.pop("artifact_sha256")
        self.assertEqual(claimed, LAB.sha256(artifact))
        self.assertFalse(artifact["future_return_labels_inspected"])
        self.assertFalse(artifact["model_trained"])


if __name__ == "__main__":
    unittest.main()
