import copy
import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sec_announce_cohort_lab",
    ROOT / "tools" / "sec_announce_cohort_lab.py",
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)
PRODUCTION_SPEC = (
    ROOT / "docs" / "research" / "data" / "ca_announce_cohort_spec.json"
)
PRODUCTION_ARTIFACT = (
    ROOT / "docs" / "research" / "data" / "ca_announce_cohort_seed.json"
)


def _minimal_deal(**overrides):
    deal = {
        "deal_id": "demo-close",
        "target_name": "Demo Target",
        "acquirer_name": "Demo Acquirer",
        "target_cik": "0000000001",
        "acquirer_cik": "0000000002",
        "event_symbol": "DEMO",
        "stratum": "classic_public_target",
        "announced_on": "2023-01-10",
        "announcement": {
            "observed_at": "2023-01-10T12:00:00-05:00",
            "observation_time_quality": "edgar_acceptance_exact",
            "accession": "0000000001-23-000001",
            "form": "8-K",
            "source_url": "https://example.test/announce",
        },
        "announcement_terms": {
            "consideration_family": "cash",
            "cash_usd_per_share": 10.0,
        },
        "conditions": {
            "shareholder_vote": True,
            "regulatory": True,
            "financing": False,
            "outside_date_known": False,
        },
        "outcome": "close_as_announced",
        "resolution": {
            "resolved_on": "2023-06-01",
            "resolved_observed_at": "2023-06-01T09:00:00-04:00",
            "outcome_source_accession": "0000000001-23-000099",
            "outcome_source_url": "https://example.test/resolve",
            "next_counterparty": None,
            "notes": "synthetic",
        },
        "predictive_for_outcome": False,
        "reuses_research_nodes": ["E110"],
    }
    deal.update(overrides)
    return deal


def _minimal_spec(deals):
    return {
        "schema_version": 1,
        "spec_id": "ca-announce-test-spec",
        "censor_on": "2025-01-01",
        "raw_documents_committed": False,
        "predictive_features_allowed": False,
        "research_status": "test",
        "cohort": {
            "name": "test",
            "announcement_start": "2022-01-01",
            "announcement_end": "2023-12-31",
            "selection_rule": "test",
            "rights_tier": "test",
        },
        "parent_docs": ["docs/research/CA_ANNOUNCE_model_blueprint.md"],
        "deals": deals,
    }


class SecAnnounceCohortLabTests(unittest.TestCase):
    def test_production_artifact_validates(self):
        artifact = LAB.load_json(PRODUCTION_ARTIFACT)
        LAB.validate_artifact(artifact)
        self.assertEqual(artifact["summary"]["deal_count"], 6)
        self.assertTrue(artifact["summary"]["schema_seed_not_population"])
        self.assertTrue(
            artifact["summary"][
                "includes_higher_bid_as_distinct_from_negative_termination"
            ]
        )
        self.assertTrue(artifact["summary"]["zero_censored_blocks_survival_claim"])
        self.assertFalse(artifact["baseline_ladder_ready"])
        self.assertFalse(artifact["market_implied_baseline_included"])

    def test_build_is_deterministic_except_timestamp(self):
        spec = LAB.load_json(PRODUCTION_SPEC)
        first = LAB.build_artifact(spec)
        second = LAB.build_artifact(spec)
        first = copy.deepcopy(first)
        second = copy.deepcopy(second)
        first.pop("generated_at")
        second.pop("generated_at")
        self.assertEqual(first, second)

    def test_higher_bid_requires_next_counterparty(self):
        deal = _minimal_deal(
            deal_id="demo-higher",
            outcome="higher_bid",
            resolution={
                "resolved_on": "2023-06-01",
                "resolved_observed_at": "2023-06-01T09:00:00-04:00",
                "outcome_source_accession": "0000000001-23-000099",
                "outcome_source_url": "https://example.test/resolve",
                "next_counterparty": None,
                "notes": "missing counterparty",
            },
        )
        with self.assertRaisesRegex(ValueError, "next_counterparty"):
            LAB.validate_spec(_minimal_spec([deal]))

    def test_censored_deal_has_no_resolution_clock(self):
        deal = _minimal_deal(
            deal_id="demo-censored",
            outcome="censored",
            resolution={
                "resolved_on": None,
                "resolved_observed_at": None,
                "outcome_source_accession": None,
                "outcome_source_url": None,
                "next_counterparty": None,
                "notes": "still open at censor",
            },
        )
        artifact = LAB.build_artifact(_minimal_spec([deal]))
        record = artifact["deals"][0]
        self.assertEqual(record["outcome"], "censored")
        self.assertTrue(record["survival"]["right_censored"])
        self.assertFalse(record["survival"]["event_observed"])
        self.assertEqual(
            record["survival"]["time_to_event_or_censor_days"],
            (dt.date(2025, 1, 1) - dt.date(2023, 1, 10)).days,
        )
        self.assertFalse(artifact["summary"]["zero_censored_blocks_survival_claim"])

    def test_resolve_after_censor_must_be_marked_censored(self):
        deal = _minimal_deal(
            resolution={
                "resolved_on": "2025-06-01",
                "resolved_observed_at": "2025-06-01T09:00:00-04:00",
                "outcome_source_accession": "0000000001-23-000099",
                "outcome_source_url": "https://example.test/resolve",
                "next_counterparty": None,
                "notes": "too late",
            }
        )
        with self.assertRaisesRegex(ValueError, "resolved after censor_on"):
            LAB.validate_spec(_minimal_spec([deal]))

    def test_exact_announcement_clock_requires_accession(self):
        deal = _minimal_deal()
        deal["announcement"]["accession"] = None
        with self.assertRaisesRegex(ValueError, "exact clock requires accession"):
            LAB.validate_spec(_minimal_spec([deal]))

    def test_outcome_labels_cannot_be_predictive(self):
        deal = _minimal_deal(predictive_for_outcome=True)
        with self.assertRaisesRegex(ValueError, "cannot be predictive"):
            LAB.validate_spec(_minimal_spec([deal]))

    def test_build_command_writes_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "seed.json"
            LAB.command_build(
                type(
                    "Args",
                    (),
                    {"spec": PRODUCTION_SPEC, "output": out},
                )()
            )
            artifact = json.loads(out.read_text(encoding="utf-8"))
            LAB.validate_artifact(artifact)
            self.assertEqual(artifact["summary"]["deal_count"], 6)


if __name__ == "__main__":
    unittest.main()
