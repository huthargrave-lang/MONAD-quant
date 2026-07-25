import importlib.util
import json
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "index_membership_event_pilot",
    ROOT / "tools" / "index_membership_event_pilot.py",
)
ix = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ix
SPEC.loader.exec_module(ix)


def synthetic_frame(batch=ix.DEFAULT_BATCH):
    dates = pd.bdate_range("2026-02-20", periods=90)
    symbols = sorted(
        {s.provider_symbol for s in batch.securities} | {batch.benchmark}
    )
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    columns = pd.MultiIndex.from_product(
        [fields, symbols], names=["Price", "Ticker"]
    )
    frame = pd.DataFrame(index=dates, columns=columns, dtype=float)
    for symbol_i, symbol in enumerate(symbols):
        base = 100.0 + symbol_i
        for day_i, date in enumerate(dates):
            close = base + day_i
            frame.loc[date, ("Open", symbol)] = close - 0.25
            frame.loc[date, ("High", symbol)] = close + 1.0
            frame.loc[date, ("Low", symbol)] = close - 1.0
            frame.loc[date, ("Close", symbol)] = close
            frame.loc[date, ("Adj Close", symbol)] = close * 0.5
            frame.loc[date, ("Volume", symbol)] = 1_000_000 + day_i
    return frame


class TestIndexMembershipEventPilot(unittest.TestCase):
    def test_adjusted_open_uses_adjustment_ratio(self):
        frame = pd.DataFrame(
            {"Open": [10.0], "Close": [12.0], "Adj Close": [6.0]}
        )
        self.assertEqual(ix.adjusted_open(frame).iloc[0], 5.0)

    def test_relative_return_is_compounded(self):
        self.assertAlmostEqual(ix.relative_return(0.10, 0.05), 1.10 / 1.05 - 1)

    def test_exact_input_hash_exposes_float_jitter_but_derived_hash_is_stable(self):
        frame = synthetic_frame()
        jittered = frame.copy()
        jittered.iloc[0, 0] += 0.000001
        self.assertNotEqual(
            ix.normalized_input_fingerprint(frame),
            ix.normalized_input_fingerprint(jittered),
        )
        original = ix.analyze(frame, "2026-07-24T00:00:00+00:00")
        revised = ix.analyze(jittered, "2026-07-24T00:00:01+00:00")
        self.assertEqual(
            original["derived_result_sha256"], revised["derived_result_sha256"]
        )

    def test_nth_session_is_one_based(self):
        dates = pd.bdate_range("2026-03-23", periods=6)
        self.assertEqual(ix.nth_session_on_or_after(dates, "2026-03-23", 1), dates[0])
        self.assertEqual(ix.nth_session_on_or_after(dates, "2026-03-23", 5), dates[4])

    def test_analysis_keeps_event_and_provider_symbols_separate(self):
        result = ix.analyze(synthetic_frame(), "2026-07-24T00:00:00+00:00")
        echo = next(row for row in result["securities"] if row["event_symbol"] == "SATS")
        self.assertEqual(echo["provider_symbol"], "ECHO")
        self.assertEqual(echo["transition"], "family_up_migration")
        self.assertEqual(result["groups"]["additions"]["n"], 4)
        self.assertEqual(result["groups"]["deletions"]["n"], 4)
        self.assertEqual(result["groups"]["direct_entries"]["n"], 1)
        self.assertEqual(len(result["normalized_input_sha256"]), 64)

    def test_analysis_uses_implementation_close_not_effective_open_as_anchor(self):
        result = ix.analyze(synthetic_frame(), "2026-07-24T00:00:00+00:00")
        self.assertEqual(
            result["event_clock"]["implementation_session_close"], "2026-03-20"
        )
        self.assertEqual(result["event_clock"]["effective_session_open"], "2026-03-23")
        row = result["securities"][0]
        self.assertIn(
            "implementation_close_to_effective_open_relative", row["metrics"]
        )
        self.assertIn("post_implementation_60_sessions_relative", row["metrics"])

    def test_retained_evidence_card_preserves_clock_identity_and_small_sample_warning(self):
        artifact = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "ix00_sp500_march2026_event_pilot.json"
            ).read_text()
        )
        self.assertEqual(artifact["event_clock"]["implementation_session_close"], "2026-03-20")
        self.assertEqual(artifact["event_clock"]["effective_session_open"], "2026-03-23")
        echo = next(
            row for row in artifact["security_contract"] if row["event_symbol"] == "SATS"
        )
        self.assertEqual(echo["provider_symbol"], "ECHO")
        self.assertEqual(artifact["group_summary_percent"]["additions"]["n"], 4)
        self.assertEqual(artifact["group_summary_percent"]["deletions"]["n"], 4)
        self.assertEqual(
            len(set(artifact["refresh_audit"]["paired_derived_result_sha256"])), 1
        )
        self.assertGreater(
            len(set(artifact["refresh_audit"]["observed_exact_input_sha256"])), 1
        )
        self.assertTrue(any("descriptive" in item.lower() for item in artifact["limitations"]))

    def test_nasdaq_batch_has_exact_announcement_clock_and_direct_transitions(self):
        batch = ix.BATCHES["ndx-2025-12"]
        dates = pd.bdate_range("2025-11-20", periods=90)
        frame = synthetic_frame(batch)
        frame.index = dates
        result = ix.analyze(frame, "2026-07-24T00:00:00+00:00", batch)
        self.assertEqual(
            result["event_clock"]["announcement_source_at"],
            "2025-12-12T20:00:00-05:00",
        )
        self.assertEqual(result["event_clock"]["first_tradable_session"], "2025-12-15")
        self.assertEqual(result["groups"]["additions"]["n"], 6)
        self.assertEqual(result["groups"]["deletions"]["n"], 6)
        self.assertEqual(result["groups"]["direct_entries"]["n"], 6)
        self.assertEqual(result["groups"]["direct_exits"]["n"], 6)

    def test_2024_batch_preserves_exact_clock_and_balanced_final_list(self):
        batch = ix.BATCHES["ndx-2024-12"]
        frame = synthetic_frame(batch)
        frame.index = pd.bdate_range("2024-11-20", periods=90)
        result = ix.analyze(frame, "2026-07-24T00:00:00+00:00", batch)
        self.assertEqual(
            result["event_clock"]["announcement_source_at"],
            "2024-12-13T20:00:00-05:00",
        )
        self.assertEqual(result["event_clock"]["implementation_session_close"], "2024-12-20")
        self.assertEqual(result["groups"]["additions"]["n"], 3)
        self.assertEqual(result["groups"]["deletions"]["n"], 3)
        self.assertIn("2024-12-13", result["official_source"])

    def test_2023_revision_separates_tradable_addition_from_cash_merger_exit(self):
        batch = ix.BATCHES["ndx-2023-12-update"]
        frame = synthetic_frame(batch)
        frame.index = pd.bdate_range("2023-11-15", periods=len(frame))
        result = ix.analyze(frame, "2026-07-24T00:00:00+00:00", batch)
        self.assertEqual(
            result["event_clock"]["announcement_source_at"],
            "2023-12-12T18:00:00-05:00",
        )
        self.assertEqual(result["event_clock"]["first_tradable_session"], "2023-12-13")
        self.assertEqual(result["event_clock"]["implementation_session_close"], "2023-12-15")
        self.assertEqual(result["coverage"]["analyzed"], 1)
        self.assertEqual(result["coverage"]["official_events"], 2)
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(result["securities"][0]["event_symbol"], "TTWO")
        self.assertEqual(
            result["securities"][0]["transition"],
            "corporate_action_replacement",
        )
        self.assertEqual(result["excluded_securities"][0]["event_symbol"], "SGEN")
        self.assertIn("cash merger", result["excluded_securities"][0]["reason"])

    def test_2022_batch_preserves_missing_delisted_security_as_coverage_failure(self):
        batch = ix.BATCHES["ndx-2022-12"]
        frame = synthetic_frame(batch)
        frame.index = pd.bdate_range("2022-11-15", periods=90)
        result = ix.analyze(frame, "2026-07-24T00:00:00+00:00", batch)
        self.assertEqual(result["groups"]["additions"]["n"], 6)
        self.assertEqual(result["groups"]["deletions"]["n"], 6)
        self.assertEqual(result["coverage"]["analyzed"], 12)
        self.assertEqual(result["coverage"]["official_events"], 13)
        self.assertFalse(result["coverage"]["complete"])
        self.assertEqual(result["excluded_securities"][0]["event_symbol"], "SPLK")
        self.assertEqual(result["event_clock"]["implementation_session_close"], "2022-12-16")
        self.assertEqual(result["event_clock"]["effective_session_open"], "2022-12-19")

    def test_retained_nasdaq_replication_contradicts_direction_but_repeats_volume(self):
        artifact = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "ix00_ndx_december2025_event_replication.json"
            ).read_text()
        )
        additions = artifact["group_summary_percent"]["additions"]
        deletions = artifact["group_summary_percent"]["deletions"]
        self.assertLess(additions["first_open_to_implementation_close_relative"], 0)
        self.assertLess(deletions["first_open_to_implementation_close_relative"], 0)
        self.assertGreater(
            additions["implementation_volume_ratio_to_prior_20d_median"], 10
        )
        self.assertGreater(
            deletions["implementation_volume_ratio_to_prior_20d_median"], 5
        )
        self.assertEqual(
            len(set(artifact["refresh_audit"]["paired_derived_result_sha256"])), 1
        )
        self.assertIn("did not replicate", artifact["cross_batch_interpretation"][0])

    def test_recent_complete_panel_excludes_partial_and_revision_batches(self):
        artifact = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "ix00_ndx_recent_complete_panel.json"
            ).read_text()
        )
        self.assertEqual(artifact["included_batches"], ["ndx-2024-12", "ndx-2025-12"])
        self.assertIn("ndx-2022-12", artifact["excluded_batches"])
        self.assertIn("ndx-2023-12", artifact["excluded_batches"])
        spread = artifact["security_weighted_summary_percent"][
            "addition_minus_deletion"
        ]
        self.assertLess(spread["post_implementation_1_session_relative"], 0)
        self.assertLess(spread["post_implementation_5_sessions_relative"], 0)

    def test_retained_2022_diagnostic_keeps_splk_missingness_loud(self):
        artifact = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "ix00_ndx_december2022_partial_diagnostic.json"
            ).read_text()
        )
        self.assertFalse(artifact["coverage"]["complete"])
        self.assertEqual(artifact["coverage"]["analyzed"], 12)
        self.assertEqual(artifact["coverage"]["official_events"], 13)
        self.assertEqual(artifact["excluded_security"]["event_symbol"], "SPLK")
        self.assertIn("barred", artifact["status"])

    def test_retained_2023_revision_diagnostic_separates_outcome_types(self):
        artifact = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "ix01_ndx_2023_revision_diagnostic.json"
            ).read_text()
        )
        self.assertEqual(
            artifact["event_clock"]["revision_published_at"],
            "2023-12-12T18:00:00-05:00",
        )
        self.assertEqual(artifact["coverage"]["continuing_equity_return_events"], 1)
        self.assertEqual(artifact["coverage"]["cash_merger_terminal_events"], 1)
        self.assertEqual(artifact["sgen"]["outcome_type"], "cash_merger_terminal_value")
        self.assertEqual(artifact["sgen"]["merger_consideration_usd_per_share"], 229.0)
        self.assertEqual(
            len(set(artifact["refresh_audit"]["paired_derived_result_sha256"])), 1
        )
        self.assertGreater(
            len(set(artifact["refresh_audit"]["observed_exact_input_sha256"])), 1
        )
        self.assertLess(
            artifact["ttwo"]["relative_return_percent"][
                "first_tradable_open_to_implementation_close"
            ],
            0,
        )


if __name__ == "__main__":
    unittest.main()
