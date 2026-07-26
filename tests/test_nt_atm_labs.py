"""Tests for NT late-filer and ATM 424B5 labs."""
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


NT = load_lab("nt_late_filer_lab", "tools/nt_late_filer_lab.py")
ATM = load_lab("atm_424b5_lab", "tools/atm_424b5_lab.py")


class NtLateFilerLabTests(unittest.TestCase):
    def test_month_sliced_discovery(self):
        response = Path(
            "/private/tmp/monad-nt-pilot/search-nt10k-2023-month-sliced.json"
        )
        if not response.is_file():
            self.skipTest("frozen NT search unavailable")
        spec = NT.load_json(
            ROOT / "docs/research/data/nt_late_filer_spec.json"
        )
        artifact = NT.build_artifact(response, spec)
        self.assertEqual(artifact["lab_id"], "LF-01")
        self.assertEqual(artifact["summary"]["unique_submissions"], 170)
        self.assertFalse(artifact["outcomes_assigned"])
        # March deadline cluster dominates
        by_month = artifact["summary"]["submissions_by_month"]
        self.assertGreater(by_month.get("2023-03", 0), 50)

    def test_sha_mismatch(self):
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
                                "file_date": "2023-03-15",
                                "form": "NT 10-K",
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
                "spec_id": "t",
                "search": {
                    "endpoint": "https://efts.sec.gov/LATEST/search-index",
                    "forms": ["NT 10-K"],
                    "response_sha256": "deadbeef",
                },
            }
            with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
                NT.build_artifact(path, spec)


class Atm424b5LabTests(unittest.TestCase):
    def test_discovery_and_optional_price_pilot(self):
        response = Path(
            "/private/tmp/monad-atm-pilot/search-424b5-atm-2024q1.json"
        )
        if not response.is_file():
            self.skipTest("frozen ATM search unavailable")
        spec = ATM.load_json(
            ROOT / "docs/research/data/atm_424b5_spec.json"
        )
        artifact = ATM.build_artifact(response, spec, bundle=None)
        self.assertEqual(artifact["lab_id"], "DI-01")
        self.assertEqual(artifact["summary"]["unique_submissions"], 100)
        self.assertTrue(artifact["summary"]["phrase_hit_not_takedown_event"])
        self.assertGreater(
            artifact["summary"]["submissions_with_parsed_ticker"], 50
        )

        bundle = Path("/private/tmp/monad-atm-pilot")
        if (bundle / "SPY_chart.json").is_file():
            with_price = ATM.build_artifact(response, spec, bundle=bundle)
            pilot = with_price["price_pilot"]["summary"]
            self.assertGreaterEqual(pilot["n_events_with_price"], 5)
            self.assertTrue(pilot["descriptive_only"])


if __name__ == "__main__":
    unittest.main()
