"""Tests for the CA-ANNOUNCE announcement-forward deal-risk lab.

Covers: committed-cohort validation + integrity guards, the point-in-time
leakage guard, competing-risks label derivation at both horizons, estimator
correctness (via the synthetic self-check plus closed-form metric checks),
deal-clustered bootstrap determinism, and the kill-criteria audit. Stdlib only,
runs offline on a fresh clone.
"""
import copy
import datetime as dt
import importlib.util
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ca_announce_cohort_lab", ROOT / "tools" / "ca_announce_cohort_lab.py"
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)
COHORT_PATH = ROOT / "docs" / "research" / "data" / "ca_announce_cohort_2023.json"


class CohortFixtureTests(unittest.TestCase):
    def setUp(self):
        self.cohort = LAB.load_cohort(COHORT_PATH)

    def test_committed_cohort_validates(self):
        LAB.validate_cohort(self.cohort)

    def test_frame_is_announcement_forward_not_outcome_conditioned(self):
        self.assertEqual(
            self.cohort["frame"], "announcement_forward_not_outcome_conditioned"
        )

    def test_all_three_classes_present_so_no_stratum_is_outcome_selected(self):
        classes = {d["ground_truth"]["outcome_class"] for d in self.cohort["deals"]}
        self.assertEqual(classes, set(LAB.CLASSES))

    def test_market_implied_inputs_are_flagged_proxy(self):
        self.assertTrue(self.cohort["market_implied_inputs_are_proxy"])
        for deal in self.cohort["deals"]:
            self.assertTrue(deal["market_implied"]["proxy"])

    def test_no_fabricated_provenance(self):
        """Unverified provenance must never carry an accession; frozen provenance
        must reference a sibling fixture + accession. At least one is frozen."""
        frozen = 0
        for deal in self.cohort["deals"]:
            term = deal["provenance"]["terminal"]
            if term["status"] == "frozen_upstream":
                self.assertTrue(term.get("accession"))
                self.assertTrue(term.get("fixture"))
                frozen += 1
            else:
                self.assertEqual(term["status"], "public_record_unverified_offline")
                self.assertIsNone(term.get("accession"))
                self.assertTrue(term.get("needs_freeze"))
        self.assertGreaterEqual(frozen, 1)

    def test_frozen_provenance_points_at_real_committed_fixtures(self):
        data_dir = ROOT / "docs" / "research" / "data"
        for deal in self.cohort["deals"]:
            term = deal["provenance"]["terminal"]
            if term["status"] == "frozen_upstream":
                self.assertTrue((data_dir / term["fixture"]).exists(),
                                "frozen provenance references a missing fixture")

    def test_resolution_never_precedes_announcement(self):
        for deal in self.cohort["deals"]:
            ann = dt.date.fromisoformat(deal["announced_on"])
            res = dt.date.fromisoformat(deal["ground_truth"]["resolution_on"])
            self.assertGreaterEqual(res, ann)

    def test_validation_rejects_committed_raw_documents(self):
        bad = copy.deepcopy(self.cohort)
        bad["raw_documents_committed"] = True
        with self.assertRaises(ValueError):
            LAB.validate_cohort(bad)

    def test_validation_rejects_unverified_provenance_with_accession(self):
        bad = copy.deepcopy(self.cohort)
        for deal in bad["deals"]:
            term = deal["provenance"]["terminal"]
            if term["status"] == "public_record_unverified_offline":
                term["accession"] = "0000000000-23-000000"
                break
        with self.assertRaisesRegex(ValueError, "must not carry an accession"):
            LAB.validate_cohort(bad)


class LeakageGuardTests(unittest.TestCase):
    def setUp(self):
        self.cohort = LAB.load_cohort(COHORT_PATH)

    def test_public_view_strips_ground_truth_and_provenance(self):
        deal = self.cohort["deals"][0]
        view = LAB.public_view(deal)
        self.assertNotIn("ground_truth", view)
        self.assertNotIn("provenance", view)

    def test_features_are_invariant_to_the_terminal_outcome(self):
        """The core anti-leakage property: mutating only the outcome/resolution
        must not change any feature."""
        for deal in self.cohort["deals"]:
            f1 = LAB.feature_vector(deal)
            mutated = copy.deepcopy(deal)
            mutated["ground_truth"] = {
                "outcome_class": "negative_termination",
                "resolution_on": "2023-04-01",
            }
            self.assertEqual(f1, LAB.feature_vector(mutated), deal["deal_id"])

    def test_feature_vector_has_expected_length(self):
        deal = self.cohort["deals"][0]
        self.assertEqual(len(LAB.feature_vector(deal)), len(LAB.FEATURE_NAMES))


class LabelDerivationTests(unittest.TestCase):
    def setUp(self):
        self.cohort = LAB.load_cohort(COHORT_PATH)
        self.deals = self.cohort["deals"]

    def test_default_horizon_counts(self):
        labels = LAB.label_cohort(self.deals, dt.date(2025, 6, 30))
        observed = [l for l in labels if l.status == "observed"]
        censored = [l for l in labels if l.status == "censored"]
        self.assertEqual(len(observed), 10)
        self.assertEqual(len(censored), 1)  # Hess/Chevron resolves 2025-07-18

    def test_secondary_horizon_produces_real_censoring(self):
        labels = LAB.label_cohort(self.deals, dt.date(2024, 3, 31))
        censored = [l for l in labels if l.status == "censored"]
        self.assertEqual(len(censored), 4)

    def test_hess_chevron_is_censored_at_default_horizon(self):
        deal = next(d for d in self.deals if d["deal_id"] == "hess-chevron")
        lab = LAB.derive_label(deal, dt.date(2025, 6, 30))
        self.assertEqual(lab.status, "censored")
        self.assertIsNone(lab.event_class)

    def test_amedisys_is_higher_bid_displacement(self):
        deal = next(d for d in self.deals if d["deal_id"] == "amedisys-option-care")
        lab = LAB.derive_label(deal, dt.date(2025, 6, 30))
        self.assertEqual(lab.event_class, "higher_bid_displacement")

    def test_capri_is_negative_termination(self):
        deal = next(d for d in self.deals if d["deal_id"] == "capri-tapestry")
        lab = LAB.derive_label(deal, dt.date(2025, 6, 30))
        self.assertEqual(lab.event_class, "negative_termination")

    def test_label_time_is_non_negative(self):
        labels = LAB.label_cohort(self.deals, dt.date(2024, 3, 31))
        for l in labels:
            self.assertGreaterEqual(l.time_days, 0)


class MetricTests(unittest.TestCase):
    def test_multiclass_brier_perfect_and_worst(self):
        y = ["close_as_announced", "negative_termination"]
        perfect = [LAB._onehot("close_as_announced"), LAB._onehot("negative_termination")]
        perfect = [dict(zip(LAB.CLASSES, v)) for v in perfect]
        self.assertAlmostEqual(LAB.multiclass_brier(perfect, y), 0.0, places=9)
        worst = [dict(zip(LAB.CLASSES, LAB._onehot("higher_bid_displacement"))) for _ in y]
        self.assertAlmostEqual(LAB.multiclass_brier(worst, y), 2.0, places=9)

    def test_log_loss_of_confident_correct_is_small(self):
        y = ["close_as_announced"]
        p = [{"close_as_announced": 0.99, "higher_bid_displacement": 0.005,
              "negative_termination": 0.005}]
        self.assertLess(LAB.log_loss(p, y), 0.02)

    def test_uniform_log_loss_equals_log_three(self):
        y = ["close_as_announced", "negative_termination", "higher_bid_displacement"]
        p = [{c: 1 / 3 for c in LAB.CLASSES} for _ in y]
        self.assertAlmostEqual(LAB.log_loss(p, y), math.log(3), places=6)

    def test_auc_is_one_for_perfect_ranking(self):
        scores = [0.1, 0.2, 0.3, 0.4]
        positive = [False, False, True, True]
        self.assertAlmostEqual(LAB.auc_ovr(scores, positive), 1.0, places=9)

    def test_auc_none_when_one_class_absent(self):
        self.assertIsNone(LAB.auc_ovr([0.1, 0.2], [True, True]))

    def test_market_implied_inversion_is_exact(self):
        C, D, days = 100.0, 70.0, 180.0
        pv = C * math.exp(-LAB.ANNUAL_RATE * days / 365.0)
        for p_true in (0.15, 0.5, 0.85):
            target = p_true * pv + (1 - p_true) * D
            deal = {"consideration": {"structure": "cash", "cash_usd_per_share": C},
                    "market_implied": {"target_price": target, "downside_estimate": D,
                                       "expected_days_to_close": days}}
            self.assertAlmostEqual(LAB.market_implied_completion_prob(deal), p_true, places=4)

    def test_bootstrap_is_deterministic(self):
        y = ["close_as_announced"] * 6 + ["negative_termination"] * 2
        preds = [{"close_as_announced": 0.7, "higher_bid_displacement": 0.1,
                  "negative_termination": 0.2} for _ in y]
        a = LAB.deal_clustered_bootstrap(LAB.multiclass_brier, preds, y, n_boot=500)
        b = LAB.deal_clustered_bootstrap(LAB.multiclass_brier, preds, y, n_boot=500)
        self.assertEqual(a, b)


class CompetingRisksTests(unittest.TestCase):
    def test_incidence_partitions_probability(self):
        train = [
            LAB.Labelled("a", "observed", "close_as_announced", 10, 0),
            LAB.Labelled("b", "observed", "negative_termination", 20, 0),
            LAB.Labelled("c", "censored", None, 30, 0),
            LAB.Labelled("d", "observed", "close_as_announced", 40, 0),
        ]
        aj = LAB.aalen_johansen(train)
        total = sum(aj["cif"].values()) + aj["final_survival"]
        self.assertAlmostEqual(total, 1.0, places=9)

    def test_survival_uses_censored_observations(self):
        """Adding a censored deal changes the at-risk denominator, so incidence
        must differ from dropping it entirely (kill-criterion 6)."""
        base = [
            LAB.Labelled("a", "observed", "close_as_announced", 10, 0),
            LAB.Labelled("b", "observed", "negative_termination", 30, 0),
        ]
        with_censor = base + [LAB.Labelled("c", "censored", None, 20, 0)]
        self.assertNotEqual(
            LAB.aalen_johansen(base)["cif"]["negative_termination"],
            LAB.aalen_johansen(with_censor)["cif"]["negative_termination"],
        )


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.cohort = LAB.load_cohort(COHORT_PATH)

    def test_evaluate_default_horizon(self):
        art = LAB.evaluate_cohort(self.cohort)
        self.assertEqual(art["composition"]["n_deals"], 11)
        self.assertIn("market_implied", art["model_scores"])
        self.assertEqual(len(art["kill_criteria"]), 8)

    def test_no_lodo_leakage_predictions_only_for_observed(self):
        labels = LAB.label_cohort(self.cohort["deals"], dt.date(2025, 6, 30))
        preds = LAB.lodo_predictions(self.cohort["deals"], labels)
        censored_ids = {l.deal_id for l in labels if l.status == "censored"}
        for model_preds in preds.values():
            self.assertFalse(censored_ids & set(model_preds.keys()),
                             "a censored deal received an out-of-sample class prediction")

    def test_kill_criteria_all_report_ok(self):
        art = LAB.evaluate_cohort(self.cohort)
        for key, val in art["kill_criteria"].items():
            self.assertTrue(val["ok"], key)

    def test_evaluation_is_deterministic(self):
        a = LAB.evaluate_cohort(self.cohort)
        b = LAB.evaluate_cohort(self.cohort)
        self.assertEqual(a["model_scores"]["market_implied"]["multiclass_brier"],
                         b["model_scores"]["market_implied"]["multiclass_brier"])


class SelfCheckTests(unittest.TestCase):
    def test_selfcheck_passes(self):
        result = LAB.selfcheck(verbose=False)
        self.assertTrue(result["all_passed"])


class PowerAnalysisTests(unittest.TestCase):
    def test_t_crit_table(self):
        self.assertAlmostEqual(LAB._t_crit_one_sided_05(10), 1.812, places=3)
        self.assertEqual(LAB._t_crit_one_sided_05(100000), 1.645)  # normal limit
        # interpolated value sits between its bracketing table entries
        v = LAB._t_crit_one_sided_05(11)
        self.assertTrue(1.782 <= v <= 1.812)

    def test_false_positive_rate_is_near_alpha_at_zero_skill(self):
        """skill=0 => model and market are equally good; rejection rate must sit
        near the nominal 0.05, i.e. the test is calibrated, not lucky."""
        fpr = LAB.power_at(50, 0.0, reps=400)
        self.assertLess(fpr, 0.13)

    def test_power_rises_with_sample_size(self):
        small = LAB.power_at(11, 1.0, reps=200)
        large = LAB.power_at(2000, 1.0, reps=200)
        self.assertLess(small, large)
        self.assertLess(small, 0.15)   # 11 deals detect ~nothing
        self.assertGreater(large, 0.5)  # thousands of deals do

    def test_effect_size_increases_with_skill(self):
        low = LAB.skill_effect_size(0.1, n_big=4000)["mean_brier_gap_market_minus_model"]
        high = LAB.skill_effect_size(0.75, n_big=4000)["mean_brier_gap_market_minus_model"]
        self.assertGreater(high, low)
        self.assertGreater(low, 0.0)

    def test_power_is_deterministic(self):
        self.assertEqual(LAB.power_at(40, 0.3, reps=120), LAB.power_at(40, 0.3, reps=120))


if __name__ == "__main__":
    unittest.main()
