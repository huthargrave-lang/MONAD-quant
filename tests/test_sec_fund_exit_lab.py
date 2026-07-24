import copy
import datetime as dt
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sec_fund_exit_lab", ROOT / "tools" / "sec_fund_exit_lab.py"
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)
PRODUCTION_SPEC = (
    ROOT / "docs" / "research" / "data" / "ca_fund_review_spec.json"
)
PRODUCTION_ARTIFACT = (
    ROOT / "docs" / "research" / "data" / "ca_fund_reviewed_seed.json"
)


class SecFundExitLabTests(unittest.TestCase):
    def fixture(self, directory):
        spec = copy.deepcopy(LAB.load_json(PRODUCTION_SPEC))
        form25_cache = Path(directory) / "form25"
        fund_cache = Path(directory) / "fund"
        form25_cache.mkdir()
        fund_cache.mkdir()
        population_rows = []
        candidate_rows = []
        for case in spec["cases"]:
            source = case["source"]
            accepted = dt.datetime.fromisoformat(source["accepted_at"])
            header = (
                "<SEC-DOCUMENT>{}.txt\n"
                "<ACCEPTANCE-DATETIME>{}\n"
            ).format(
                source["accession"], accepted.strftime("%Y%m%d%H%M%S")
            )
            payload = (
                header + "\n".join(source["required_markers"])
            ).encode("latin-1")
            cache = (
                form25_cache
                if source["cache_family"] == "form25"
                else fund_cache
            )
            (cache / (source["accession"] + ".txt")).write_bytes(payload)
            source["sha256"] = hashlib.sha256(payload).hexdigest()
            population_rows.append(
                {
                    "accession": case["form25_accession"],
                    "issuer_cik": case["issuer_cik"],
                    "issuer_name": "Issuer " + case["ticker"],
                    "accepted_at": (
                        source["accepted_at"]
                        if source["accession"] == case["form25_accession"]
                        else {
                            "0000876661-23-000549":
                                "2023-06-30T15:24:14-04:00",
                            "0001354457-23-000772":
                                "2023-10-16T16:19:43-04:00",
                        }[case["form25_accession"]]
                    ),
                }
            )
            candidate_rows.append(
                {
                    "form25_accession": case["form25_accession"],
                    "candidate_count": 0,
                    "candidates": [],
                }
            )
        population = {
            "fixture_id": "population-test",
            "sample_sha256": "sample-sha",
            "sample": population_rows,
        }
        candidates = {
            "manifest_id": "candidates-test",
            "chains_sha256": "chains-sha",
            "chains": candidate_rows,
        }
        return spec, population, candidates, form25_cache, fund_cache

    def test_build_promotes_all_five_missing_fund_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            values = self.fixture(tmp)
            artifact = LAB.build_artifact(
                values[1], values[2], values[0], values[3], values[4]
            )
        self.assertEqual(artifact["summary"]["reviewed_cases"], 5)
        self.assertEqual(artifact["summary"]["exchange_source_labels"], 3)
        self.assertEqual(artifact["summary"]["issuer_source_labels"], 2)
        self.assertFalse(artifact["predictive_features_allowed"])

    def test_build_requires_exact_complete_missing_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, population, candidates, form25_cache, fund_cache = (
                self.fixture(tmp)
            )
            candidates["chains"].pop()
            with self.assertRaisesRegex(ValueError, "complete missing"):
                LAB.build_artifact(
                    population,
                    candidates,
                    spec,
                    form25_cache,
                    fund_cache,
                )

    def test_build_rejects_source_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, population, candidates, form25_cache, fund_cache = (
                self.fixture(tmp)
            )
            spec["cases"][0]["source"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                LAB.build_artifact(
                    population,
                    candidates,
                    spec,
                    form25_cache,
                    fund_cache,
                )

    def test_scheduled_nav_right_cannot_invent_cash_or_payment(self):
        spec = copy.deepcopy(LAB.load_json(PRODUCTION_SPEC))
        row = next(
            case
            for case in spec["cases"]
            if case["outcome_type"] == "scheduled_cash_at_nav_liquidation"
        )
        row["rights"]["cash_amount_usd"] = 10
        with self.assertRaisesRegex(ValueError, "must remain null"):
            LAB.validate_spec(spec)

    def test_liquidating_trust_legs_must_reconcile(self):
        spec = copy.deepcopy(LAB.load_json(PRODUCTION_SPEC))
        row = next(
            case
            for case in spec["cases"]
            if case["outcome_type"]
            == "completed_cash_plus_liquidating_trust"
        )
        row["rights"]["combined_value_at_close_usd"] = 12.99
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            LAB.validate_spec(spec)

    def test_exchange_date_conflict_is_preserved(self):
        artifact = LAB.load_json(PRODUCTION_ARTIFACT)
        LAB.validate_artifact(artifact)
        nkg = next(row for row in artifact["rows"] if row["ticker"] == "NKG")
        self.assertEqual(
            nkg["effective_date_status"],
            "rights_date_supported_but_legal_date_text_conflicts",
        )
        self.assertEqual(
            artifact["summary"]["source_internal_date_conflicts"], 1
        )

    def test_production_artifact_validates(self):
        artifact = LAB.load_json(PRODUCTION_ARTIFACT)
        LAB.validate_artifact(artifact)
        nzro = next(
            row for row in artifact["rows"] if row["ticker"] == "NZRO"
        )
        self.assertEqual(
            nzro["label_status"],
            "scheduled_right_not_payment_confirmed",
        )
        self.assertIsNone(nzro["rights"]["cash_amount_usd"])


if __name__ == "__main__":
    unittest.main()
