import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sec_announce_review_lab",
    ROOT / "tools" / "sec_announce_review_lab.py",
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)

DISCOVERY = (
    ROOT / "docs/research/data/ca_announce_population_discovery.json"
)
REVIEW_SPEC = (
    ROOT / "docs/research/data/ca_announce_population_review_spec.json"
)
ARTIFACT = (
    ROOT / "docs/research/data/ca_announce_population_reviewed.json"
)


class SecAnnounceReviewLabTests(unittest.TestCase):
    def test_build_includes_right_censored_deals(self):
        artifact = LAB.build_artifact(
            LAB.load_json(DISCOVERY), LAB.load_json(REVIEW_SPEC)
        )
        self.assertEqual(artifact["summary"]["deal_count"], 11)
        self.assertEqual(artifact["summary"]["right_censored_deals"], 2)
        self.assertFalse(artifact["summary"]["zero_censored_blocks_survival_claim"])
        self.assertTrue(
            artifact["summary"]["includes_right_censored_observations"]
        )
        self.assertEqual(artifact["summary"]["exact_announcement_clocks"], 11)
        self.assertGreaterEqual(artifact["summary"]["open_at_early_censor"], 2)
        censored = [
            deal for deal in artifact["deals"] if deal["outcome"] == "censored"
        ]
        self.assertEqual(len(censored), 2)
        for deal in censored:
            self.assertTrue(deal["survival"]["right_censored"])
            self.assertIsNone(deal["resolved_on"])

    def test_production_artifact_validates(self):
        artifact = LAB.load_json(ARTIFACT)
        LAB.validate_artifact(artifact)
        self.assertFalse(artifact["summary"]["raw_content_hash_validated"])

    def test_resolved_after_censor_rejected(self):
        discovery = LAB.load_json(DISCOVERY)
        spec = LAB.load_json(REVIEW_SPEC)
        for row in spec["classifications"]:
            if row.get("deal_id") == "albireo-ipsen":
                row["resolved_on"] = "2025-06-01"
                break
        with self.assertRaisesRegex(ValueError, "resolved after censor"):
            LAB.validate_inputs(discovery, spec)

    def test_build_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reviewed.json"
            LAB.command_build(
                type(
                    "Args",
                    (),
                    {
                        "discovery": DISCOVERY,
                        "spec": REVIEW_SPEC,
                        "output": out,
                    },
                )()
            )
            artifact = LAB.load_json(out)
            LAB.validate_artifact(artifact)


if __name__ == "__main__":
    unittest.main()
