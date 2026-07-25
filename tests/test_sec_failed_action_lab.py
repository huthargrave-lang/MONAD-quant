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
    "sec_failed_action_lab",
    ROOT / "tools" / "sec_failed_action_lab.py",
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)
PRODUCTION_SPEC = (
    ROOT / "docs" / "research" / "data" / "ca_failframe_review_spec.json"
)
PRODUCTION_ARTIFACT = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "ca_failframe_reviewed_seed.json"
)


class SecFailedActionLabTests(unittest.TestCase):
    def fixture(self, directory):
        spec = copy.deepcopy(LAB.load_json(PRODUCTION_SPEC))
        raw_cache = Path(directory) / "raw"
        raw_cache.mkdir()
        primary_deals = {
            deal["primary_accession"]: deal for deal in spec["deals"]
        }
        hits = []
        for index, classification in enumerate(spec["classifications"]):
            accession = classification["accession"]
            deal = primary_deals.get(accession)
            accepted_date = (
                dt.date.fromisoformat(deal["event_on"])
                if deal
                else dt.date(2023, 12, 31)
            )
            accepted_digits = accepted_date.strftime("%Y%m%d") + "120000"
            body = "\n".join(deal["required_markers"]) if deal else "other"
            payload = (
                "ACCESSION NUMBER: {}\n"
                "<ACCEPTANCE-DATETIME>{}\n{}"
            ).format(accession, accepted_digits, body).encode("latin-1")
            (raw_cache / (accession + ".txt")).write_bytes(payload)
            source = {
                "adsh": accession,
                "ciks": ["0000000001"],
                "file_date": accepted_date.isoformat(),
                "form": "8-K",
                "display_names": ["Synthetic {}".format(index)],
            }
            hits.append({"_source": source})
        for index in range(8):
            duplicate = copy.deepcopy(hits[index])
            duplicate["_id"] = "duplicate-{}".format(index)
            hits.append(duplicate)
        response = {
            "hits": {
                "total": {"value": 31, "relation": "eq"},
                "hits": hits,
            }
        }
        response_path = Path(directory) / "search.json"
        payload = json.dumps(response, sort_keys=True).encode("utf-8")
        response_path.write_bytes(payload)
        spec["search"]["response_sha256"] = hashlib.sha256(payload).hexdigest()
        return spec, response_path, raw_cache

    def test_build_collapses_document_hits_to_deals(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, response_path, raw_cache = self.fixture(tmp)
            artifact = LAB.build_artifact(
                response_path, raw_cache, spec
            )
        self.assertEqual(artifact["summary"]["search_document_hits"], 31)
        self.assertEqual(artifact["summary"]["unique_submissions"], 23)
        self.assertEqual(artifact["summary"]["reviewed_unique_deals"], 14)
        self.assertEqual(
            artifact["summary"]["submission_roles"]["excluded"], 5
        )

    def test_query_set_must_match_every_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, response_path, raw_cache = self.fixture(tmp)
            excluded = next(
                item
                for item in spec["classifications"]
                if item["role"] == "excluded"
            )
            excluded["accession"] = "0000000001-23-000001"
            with self.assertRaisesRegex(
                ValueError, "search accessions and classifications differ"
            ):
                LAB.build_artifact(response_path, raw_cache, spec)

    def test_primary_marker_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, response_path, raw_cache = self.fixture(tmp)
            accession = spec["deals"][0]["primary_accession"]
            path = raw_cache / (accession + ".txt")
            path.write_text(
                "ACCESSION NUMBER: {}\n"
                "<ACCEPTANCE-DATETIME>20230504120000\nwrong".format(
                    accession
                ),
                encoding="latin-1",
            )
            with self.assertRaisesRegex(ValueError, "required marker absent"):
                LAB.build_artifact(response_path, raw_cache, spec)

    def test_source_cannot_predate_date_only_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, response_path, raw_cache = self.fixture(tmp)
            deal = spec["deals"][0]
            accession = deal["primary_accession"]
            path = raw_cache / (accession + ".txt")
            body = "\n".join(deal["required_markers"])
            path.write_text(
                "ACCESSION NUMBER: {}\n"
                "<ACCEPTANCE-DATETIME>20230503120000\n{}".format(
                    accession, body
                ),
                encoding="latin-1",
            )
            with self.assertRaisesRegex(ValueError, "predates asserted event"):
                LAB.build_artifact(response_path, raw_cache, spec)

    def test_production_artifact_validates(self):
        artifact = LAB.load_json(PRODUCTION_ARTIFACT)
        LAB.validate_artifact(artifact)
        self.assertEqual(artifact["summary"]["same_day_primary_sources"], 7)
        self.assertEqual(artifact["summary"]["later_primary_sources"], 7)
        self.assertTrue(
            artifact["summary"]["query_conditioned_not_population"]
        )

    def test_outcomes_are_barred_from_predictive_features(self):
        artifact = copy.deepcopy(LAB.load_json(PRODUCTION_ARTIFACT))
        artifact["deals"][0]["predictive_for_outcome"] = True
        with self.assertRaisesRegex(ValueError, "cannot predict itself"):
            LAB.validate_artifact(artifact)

    def test_search_response_hash_is_frozen(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, response_path, raw_cache = self.fixture(tmp)
            spec["search"]["response_sha256"] = "0" * 64
            with self.assertRaisesRegex(
                ValueError, "search response sha256 mismatch"
            ):
                LAB.build_artifact(response_path, raw_cache, spec)


if __name__ == "__main__":
    unittest.main()
