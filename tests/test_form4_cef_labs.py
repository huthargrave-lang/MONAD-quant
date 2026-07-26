"""Unit tests for Form 4 discovery and CEF discount pilot labs."""
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


FORM4 = load_lab("form4_discovery_lab", "tools/form4_discovery_lab.py")
CEF = load_lab("cef_discount_lab", "tools/cef_discount_lab.py")


class Form4DiscoveryLabTests(unittest.TestCase):
    def test_build_against_frozen_day_sliced_search(self):
        response_path = Path(
            "/private/tmp/monad-form4-pilot/search-day-sliced-2024-06-03_07.json"
        )
        if not response_path.is_file():
            self.skipTest("frozen Form 4 search response unavailable")
        spec = FORM4.load_json(
            ROOT / "docs/research/data/form4_population_spec.json"
        )
        artifact = FORM4.build_artifact(response_path, spec)
        self.assertEqual(artifact["summary"]["fetched_document_hits"], 500)
        self.assertEqual(artifact["summary"]["unique_submissions"], 500)
        self.assertEqual(
            artifact["summary"]["submissions_by_file_date"],
            {
                "2024-06-03": 100,
                "2024-06-04": 100,
                "2024-06-05": 100,
                "2024-06-06": 100,
                "2024-06-07": 100,
            },
        )
        self.assertFalse(artifact["transaction_codes_parsed"])
        self.assertTrue(
            artifact["summary"]["open_market_cluster_labels_not_assigned"]
        )

    def test_sha_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "search.json"
            payload = {
                "hits": {
                    "total": {"value": 1, "relation": "eq"},
                    "hits": [
                        {
                            "_source": {
                                "adsh": "0000000001-24-000001",
                                "ciks": ["0000000001"],
                                "file_date": "2024-06-03",
                                "form": "4",
                                "display_names": ["Demo"],
                            }
                        }
                    ],
                }
            }
            path.write_bytes(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            )
            spec = {
                "schema_version": 1,
                "spec_id": "test",
                "search": {
                    "endpoint": "https://efts.sec.gov/LATEST/search-index",
                    "forms": ["4"],
                    "start_date": "2024-06-03",
                    "end_date": "2024-06-03",
                    "response_sha256": "deadbeef",
                },
            }
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                FORM4.build_artifact(path, spec)


class CefDiscountLabTests(unittest.TestCase):
    def test_build_against_yahoo_bundle(self):
        bundle = Path("/private/tmp/monad-cef-pilot")
        required = [
            "PDI_chart.json",
            "XPDIX_nav.json",
            "BDJ_chart.json",
            "XBDJX_nav.json",
        ]
        if not all((bundle / name).is_file() for name in required):
            self.skipTest("Yahoo CEF chart bundle unavailable")
        spec = CEF.load_json(
            ROOT / "docs/research/data/cef_discount_pilot_spec.json"
        )
        # slim to two tickers for speed/robustness if others missing
        present = []
        for item in spec["tickers"]:
            px = bundle / "{}_chart.json".format(item["ticker"])
            nav = bundle / "{}_nav.json".format(item["nav_ticker"])
            if px.is_file() and nav.is_file():
                present.append(item)
        self.assertGreaterEqual(len(present), 2)
        slim = dict(spec)
        slim["tickers"] = present
        artifact = CEF.build_artifact(slim, bundle)
        self.assertEqual(artifact["lab_id"], "CEF-DISCOUNT")
        self.assertEqual(artifact["summary"]["tickers"], len(present))
        self.assertIn("mean_cheap_minus_rich_price", artifact["summary"])
        self.assertTrue(artifact["summary"]["first_cut_supports_long_cheap"])


if __name__ == "__main__":
    unittest.main()
