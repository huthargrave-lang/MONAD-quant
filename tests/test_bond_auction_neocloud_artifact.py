import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "docs/research/data/bond_auction_neocloud_2026.json"
MEMO = ROOT / "docs/research/BOND_AUCTION_NEOCLOUD_2026.md"


class BondAuctionNeocloudArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_artifact_is_explicitly_non_trading(self):
        self.assertEqual(
            self.data["status"], "descriptive_proxy_study_not_a_trading_signal"
        )
        self.assertIn("not a when-issued auction tail", self.data["factor_contract"]["warning"])
        self.assertIn("Do not use the study for live orders", self.data["kill_criteria"][-1])

    def test_population_and_tenor_contract(self):
        sample = self.data["sample"]
        self.assertEqual(sample["eligible_1pm_single_auction_events_with_all_quotes"], 103)
        self.assertEqual(sample["first_event"], "2025-04-08")
        self.assertEqual(sample["last_event"], "2026-07-28")
        self.assertEqual(
            set(sample["event_count_by_term"]),
            {"2-Year", "3-Year", "5-Year", "7-Year", "10-Year", "20-Year", "30-Year"},
        )

    def test_rate_relationship_survives_while_equity_relationship_fades(self):
        halves = self.data["results"]["temporal_halves"]
        self.assertGreater(halves["early"]["demand_vs_tlt"]["pearson_r"], 0.4)
        self.assertGreater(halves["late"]["demand_vs_tlt"]["pearson_r"], 0.4)
        self.assertGreater(halves["early"]["demand_vs_adjacent"]["pearson_r"], 0.4)
        self.assertLess(abs(halves["late"]["demand_vs_adjacent"]["pearson_r"]), 0.15)
        self.assertLess(abs(halves["late"]["demand_vs_core"]["pearson_r"]), 0.15)

    def test_recent_micro_window_is_small_and_nonconfirming(self):
        pilot = self.data["results"]["recent_5m_timing_pilot"]
        self.assertEqual(pilot["event_count"], 13)
        self.assertGreater(pilot["demand_vs_tlt_result"]["pearson_r"], 0.4)
        self.assertLess(abs(pilot["demand_vs_adjacent_result"]["pearson_r"]), 0.1)
        self.assertGreater(pilot["demand_vs_adjacent_result"]["permutation_p_two_sided"], 0.5)

    def test_raw_vendor_quotes_are_not_committed(self):
        contract = self.data["source_contract"]
        self.assertFalse(contract["raw_responses_committed"])
        self.assertIn("rights unverified", contract["rights"])
        self.assertEqual(len(contract["response_hashes"]), 17)

    def test_memo_keeps_core_and_adjacent_cohorts_separate(self):
        text = MEMO.read_text(encoding="utf-8")
        self.assertIn("core neoclouds", text)
        self.assertIn("adjacent AI infrastructure", text)
        self.assertIn("no tradable neocloud signal", text)


if __name__ == "__main__":
    unittest.main()
