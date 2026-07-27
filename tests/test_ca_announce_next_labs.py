import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_lab(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


POP = load_lab(
    "sec_announce_population_lab",
    "tools/sec_announce_population_lab.py",
)
IMPLIED = load_lab(
    "deal_market_implied_baseline",
    "tools/deal_market_implied_baseline.py",
)
RHETORIC = load_lab(
    "sec_rhetoric_delta_lab",
    "tools/sec_rhetoric_delta_lab.py",
)


class AnnouncePopulationLabTests(unittest.TestCase):
    def test_collapse_and_build_against_frozen_search(self):
        response_path = Path(
            "/private/tmp/monad-merger-announcement-search-2023-01.json"
        )
        if not response_path.is_file():
            self.skipTest("frozen SEC search response unavailable")
        spec = POP.load_json(
            ROOT / "docs/research/data/ca_announce_population_spec.json"
        )
        artifact = POP.build_artifact(response_path, spec)
        self.assertEqual(artifact["summary"]["search_document_hits"], 106)
        self.assertEqual(artifact["summary"]["unique_submissions"], 93)
        self.assertEqual(artifact["summary"]["submissions_with_item_1_01"], 47)
        self.assertFalse(artifact["outcomes_assigned"])
        self.assertTrue(
            artifact["summary"]["discovery_frame_not_reviewed_cohort"]
        )

    def test_sha_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "search.json"
            payload = {
                "hits": {
                    "total": {"value": 1, "relation": "eq"},
                    "hits": [
                        {
                            "_source": {
                                "adsh": "0000000001-23-000001",
                                "ciks": ["0000000001"],
                                "file_date": "2023-01-02",
                                "form": "8-K",
                                "display_names": ["Demo"],
                                "items": ["1.01"],
                                "sics": ["7372"],
                                "file_type": "8-K",
                            }
                        }
                    ],
                }
            }
            raw = json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            path.write_bytes(raw)
            spec = {
                "schema_version": 1,
                "spec_id": "test",
                "censor_on": "2025-01-01",
                "raw_documents_committed": False,
                "outcomes_assigned": False,
                "search": {
                    "endpoint": "https://efts.sec.gov/LATEST/search-index",
                    "query": "x",
                    "start_date": "2023-01-01",
                    "end_date": "2023-01-31",
                    "forms": ["8-K"],
                    "expected_document_hits": 1,
                    "expected_unique_submissions": 1,
                    "response_sha256": "deadbeef",
                },
            }
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                POP.build_artifact(path, spec)

    def test_production_artifact_validates_if_present(self):
        path = ROOT / "docs/research/data/ca_announce_population_discovery.json"
        if not path.is_file():
            self.skipTest("discovery artifact not built yet")
        artifact = POP.load_json(path)
        POP.validate_artifact(artifact)


class MarketImpliedBaselineTests(unittest.TestCase):
    def test_cash_proxy_formula(self):
        metrics = IMPLIED.market_implied_cash_probability(80, 100, 60)
        self.assertAlmostEqual(metrics["p_close_proxy"], 0.5)
        self.assertAlmostEqual(metrics["gross_spread"], 0.2)

    def test_clip_at_boundaries(self):
        self.assertEqual(
            IMPLIED.market_implied_cash_probability(120, 100, 60)[
                "p_close_proxy"
            ],
            1.0,
        )
        self.assertEqual(
            IMPLIED.market_implied_cash_probability(50, 100, 60)[
                "p_close_proxy"
            ],
            0.0,
        )

    def test_build_production_fixture(self):
        fixture = IMPLIED.load_json(
            ROOT
            / "docs/research/data/ca_announce_market_implied_fixture.json"
        )
        artifact = IMPLIED.build_artifact(fixture)
        self.assertEqual(artifact["summary"]["snapshot_count"], 8)
        self.assertTrue(artifact["summary"]["proxy_not_true_probability"])
        for row in artifact["snapshots"]:
            self.assertFalse(row["is_probability_truth"])


class RhetoricDeltaLabTests(unittest.TestCase):
    def test_family_deltas_on_inline_chain(self):
        spec = RHETORIC.load_json(
            ROOT / "docs/research/data/ca_rhetoric_delta_spec.json"
        )
        with tempfile.TemporaryDirectory() as tmp:
            artifact = RHETORIC.build_artifact(spec, Path(tmp))
        first = artifact["chains"][0]
        self.assertEqual(first["summary"]["filing_count"], 3)
        mid = first["filings"][1]["delta_from_previous"]
        self.assertEqual(mid["regulatory"], "unchanged")
        self.assertEqual(mid["certainty"], "unchanged")
        # first filing has confident; second has no assurance / uncertain
        self.assertIn(
            first["filings"][1]["presence"]["explicit_unknowns"], (True,)
        )
        last = first["filings"][2]["delta_from_previous"]
        self.assertEqual(last["explicit_unknowns"], "unchanged")
        self.assertEqual(last["board_recommendation"], "disappeared")
        self.assertTrue(artifact["summary"]["transparent_baseline_only"])

    def test_missing_marker_fails(self):
        spec = copy.deepcopy(
            RHETORIC.load_json(
                ROOT / "docs/research/data/ca_rhetoric_delta_spec.json"
            )
        )
        spec["chains"][0]["filings"][0]["required_markers"].append(
            "this marker is absent"
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "required marker absent"):
                RHETORIC.build_artifact(spec, Path(tmp))


if __name__ == "__main__":
    unittest.main()
