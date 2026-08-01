"""F109's nine figures reconcile; three qualifiers and one unbacked clause fall out.

Study: `docs/research/IX00_f109_cross_batch_reconciliation.md`.

F109 was flagged as quoting nine figures with no reachable document. All nine read out of
the two committed batch artifacts (E97's March-2026 S&P pilot, E98's December-2025 Nasdaq
replication), and this file binds each one at the precision F109 uses.

Three things the reconciliation surfaces, each guarded here:

1. **The volume *level* replicates; the side ordering does not.** Every group is 7x-17x
   its own prior 20-day median, but S&P's larger side is deletions (13.75x vs 8.65x) and
   Nasdaq's is additions (17.14x vs 8.60x). "Liquidity demand repeats" must not be read
   as "additions draw more volume than deletions".

2. **+10.8709%, the largest figure in the node, is three-quarters family migration.** The
   additions group is exactly the n-weighted composition of one direct entry (+4.2812%)
   and three MidCap-400 -> S&P-500 migrations (+13.0675%) — verified to 1e-6. F109 quotes
   the group figure without the split, and F108 is the node that established the split
   matters.

3. **The two batches share one price vendor** (`yfinance 1.2.0`, same-day retrieval).
   "Cross-provider" refers to the INDEX providers. So agreement on volume levels is not
   vendor-independent evidence.

And one clause has no committed numbers at all: "with large winner dispersion". Neither
artifact retains per-security returns, so the claim is carried from E98's prose and cannot
be recomputed here (`raw_data_committed: false`, provider network-blocked). Guarded as an
absence — if per-security windows are ever retained, this test says so and the claim can
be measured instead of asserted.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "docs" / "research" / "data"
DOC = ROOT / "docs" / "research" / "IX00_f109_cross_batch_reconciliation.md"
WEB = ROOT / "RESEARCH_WEB.md"

SP = json.loads((DATA / "ix00_sp500_march2026_event_pilot.json").read_text("utf-8"))
NDX = json.loads(
    (DATA / "ix00_ndx_december2025_event_replication.json").read_text("utf-8"))

WINDOW = "first_open_to_implementation_close_relative"
VOLUME = "implementation_volume_ratio_to_prior_20d_median"


def f109_body():
    text = WEB.read_text(encoding="utf-8")
    start = text.index("### F109 ")
    return text[start:text.index("\n### ", start + 5)]


class TheNineFiguresReadOutOfTheArtifactsTests(unittest.TestCase):
    """Each assertion pairs the prose figure with the field it came from."""

    def test_the_two_directional_window_figures_for_nasdaq(self):
        self.assertAlmostEqual(
            NDX["group_summary_percent"]["additions"][WINDOW], -1.562714, places=6)
        self.assertAlmostEqual(
            NDX["group_summary_percent"]["deletions"][WINDOW], -0.639425, places=6)

    def test_the_two_directional_window_figures_for_sp500(self):
        self.assertAlmostEqual(
            SP["group_summary_percent"]["additions"][WINDOW], 10.870918, places=6)
        self.assertAlmostEqual(
            SP["group_summary_percent"]["deletions"][WINDOW], -3.461407, places=6)

    def test_the_four_volume_ratios(self):
        self.assertAlmostEqual(
            NDX["group_summary_percent"]["additions"][VOLUME], 17.137807, places=6)
        self.assertAlmostEqual(
            NDX["group_summary_percent"]["deletions"][VOLUME], 8.601921, places=6)
        self.assertAlmostEqual(
            SP["group_summary_percent"]["additions"][VOLUME], 8.649664, places=6)
        self.assertAlmostEqual(
            SP["group_summary_percent"]["deletions"][VOLUME], 13.751232, places=6)

    def test_twenty_securities_across_two_batches(self):
        total = SP["coverage"]["analyzed"] + NDX["coverage"]["analyzed"]
        self.assertEqual(total, 20,
                         "the two batches no longer total 20 securities ({}) — F109's "
                         "sample-size claim is stale".format(total))
        for name, art in (("S&P", SP), ("Nasdaq", NDX)):
            self.assertTrue(art["coverage"]["complete"],
                            "the {} batch is no longer complete — F109 pools it as "
                            "though it were".format(name))

    def test_the_short_then_long_sign_pattern_for_nasdaq_additions(self):
        adds = NDX["group_summary_percent"]["additions"]
        for horizon in (1, 5):
            self.assertLess(
                adds["post_implementation_{}_session{}_relative".format(
                    horizon, "" if horizon == 1 else "s")], 0,
                "Nasdaq additions no longer underperform at {} sessions — F109's "
                "reversal description is stale".format(horizon))
        for horizon in (20, 60):
            self.assertGreater(
                adds["post_implementation_{}_sessions_relative".format(horizon)], 0,
                "Nasdaq additions no longer outperform at {} sessions".format(horizon))

    def test_the_node_still_quotes_these_figures(self):
        """Non-vacuity: the bindings above mean nothing if F109 was rewritten."""
        body = f109_body()
        for figure in ("-1.5627", "-0.6394", "10.8709", "-3.4614",
                       "17.14", "8.60", "8.65", "13.75", "twenty securities"):
            self.assertIn(
                figure, body,
                "F109 no longer states {!r} — re-derive the reconciliation table in "
                "docs/research/IX00_f109_cross_batch_reconciliation.md".format(figure))


class TheVolumeOrderingInvertsBetweenBatchesTests(unittest.TestCase):
    def test_every_group_is_a_large_multiple_of_its_own_median(self):
        for name, art in (("S&P", SP), ("Nasdaq", NDX)):
            for side in ("additions", "deletions"):
                ratio = art["group_summary_percent"][side][VOLUME]
                self.assertGreater(
                    ratio, 5.0,
                    "{} {} implementation volume fell to {:.2f}x — the one claim F109 "
                    "calls directionally stable would no longer hold".format(
                        name, side, ratio))

    def test_the_larger_side_disagrees_between_the_two_batches(self):
        sp_adds_larger = (SP["group_summary_percent"]["additions"][VOLUME]
                          > SP["group_summary_percent"]["deletions"][VOLUME])
        ndx_adds_larger = (NDX["group_summary_percent"]["additions"][VOLUME]
                           > NDX["group_summary_percent"]["deletions"][VOLUME])
        self.assertNotEqual(
            sp_adds_larger, ndx_adds_larger,
            "both batches now put the same side on top — the ordering caveat in the "
            "study is obsolete and 'liquidity demand repeats' could be read "
            "directionally after all")


class TheHeadlineFigureIsMostlyFamilyMigrationTests(unittest.TestCase):
    def test_the_addition_group_is_its_n_weighted_composition(self):
        groups = SP["group_summary_percent"]
        direct, migrated, adds = (groups["direct_entries"],
                                  groups["family_up_migrations"],
                                  groups["additions"])
        shared = set(direct) & set(migrated) & set(adds) - {"n"}
        self.assertGreaterEqual(len(shared), 4, "too few shared metrics to check")
        for metric in shared:
            expected = ((direct[metric] * direct["n"] + migrated[metric] * migrated["n"])
                        / (direct["n"] + migrated["n"]))
            self.assertAlmostEqual(
                expected, adds[metric], places=5,
                msg="{} no longer decomposes into direct entries + up-migrations — the "
                    "composition claim needs re-deriving".format(metric))

    def test_three_of_the_four_additions_are_migrations(self):
        groups = SP["group_summary_percent"]
        self.assertEqual(groups["direct_entries"]["n"], 1)
        self.assertEqual(groups["family_up_migrations"]["n"], 3)
        self.assertEqual(groups["additions"]["n"], 4)

    def test_the_single_direct_entry_is_far_below_the_group_headline(self):
        groups = SP["group_summary_percent"]
        direct = groups["direct_entries"][WINDOW]
        group = groups["additions"][WINDOW]
        self.assertLess(
            direct, group - 5.0,
            "the direct entry ({:.4f}) is now close to the group headline ({:.4f}) — "
            "the 'mostly migration' qualifier weakens".format(direct, group))

    def test_the_down_migrations_are_the_deletion_group_itself(self):
        """So the family split is a partition, not an extra sample."""
        self.assertEqual(
            SP["group_summary_percent"]["family_down_migrations"]["same_as"],
            "deletions")


class TheTwoBatchesShareOnePriceVendorTests(unittest.TestCase):
    def test_same_provider_and_version(self):
        self.assertEqual(SP["provider"], NDX["provider"])
        self.assertEqual(
            SP["provider_version"], NDX["provider_version"],
            "the two batches now use different vendor versions — the shared-vendor "
            "caveat in the study weakens, which is good news; re-state it")

    def test_the_index_providers_do_differ(self):
        """Which is what 'cross-provider' means in F109 and E98."""
        self.assertIn("spglobal", SP["official_source"])
        self.assertIn("nasdaq", NDX["official_source"])

    def test_neither_batch_commits_raw_bytes(self):
        for art in (SP, NDX):
            self.assertFalse(
                art["raw_data_committed"],
                "raw vendor data is committed now — the figures become recomputable "
                "offline and the dispersion clause below can be measured")


class TheDispersionClauseHasNoCommittedNumbersTests(unittest.TestCase):
    """A guard on an absence: it fails when the absence is filled."""

    def test_the_node_makes_the_claim(self):
        self.assertIn(
            "dispersion", f109_body(),
            "F109 no longer claims winner dispersion — retire this class")

    def test_no_artifact_carries_per_security_returns(self):
        """The S&P contract IS a list of per-security records — but they carry
        identity and transition type only, never a return. Dict-ness was the wrong
        test; the question is whether any per-security RETURN was retained."""
        return_fields = (WINDOW, VOLUME, "announcement_close_to_first_open_relative",
                         "post_implementation_20_sessions_relative")
        for name, art in (("S&P", SP), ("Nasdaq", NDX)):
            contract = art["security_contract"]
            records = (contract if isinstance(contract, list)
                       else [v for v in contract.values() if isinstance(v, dict)])
            for entry in records:
                if not isinstance(entry, dict):
                    continue
                for field in return_fields:
                    self.assertNotIn(
                        field, entry,
                        "{}'s security_contract now carries per-security {} — the "
                        "dispersion claim can be MEASURED rather than asserted; do "
                        "that and update the study".format(name, field))

    def test_the_claim_is_traceable_to_prose_not_to_a_number(self):
        interpretation = " ".join(NDX.get("cross_batch_interpretation", []))
        self.assertIn(
            "dispersed", interpretation,
            "E98's interpretation no longer asserts dispersion — F109's clause has "
            "lost even its prose source")


class TheStudyExistsAndNamesItsNodesTests(unittest.TestCase):
    def test_the_doc_names_f109_and_its_two_experiments(self):
        text = DOC.read_text(encoding="utf-8")
        for nid in ("F109", "E97", "E98", "F108", "F110"):
            self.assertIn(nid, text,
                          "the study stopped naming {} — one-hop doc reachability "
                          "depends on the document citing the node".format(nid))


if __name__ == "__main__":
    unittest.main()
