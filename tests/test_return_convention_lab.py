"""Tests for CONV-00, the return-convention consistency check.

The point of this lab is to check someone else's self-quantified caveat, so its own
algebra has to be beyond doubt. The tests are therefore weighted toward proving the
INEQUALITY rather than exercising the CLI:

* the bound is checked against closed forms where the answer is known exactly
  (single asset, identical perfectly-correlated assets),
* it is checked for TIGHTNESS — a bound that is merely true but loose would not
  license the conclusion drawn from it,
* and the direction is checked, because a flipped inequality is exactly the class
  of transcription error the lab exists to catch in the corpus.

The corpus-facing assertions are deliberately weak: they pin only what is
mechanically certain (the disclosure sites exist and say what the lab quotes; the
committed floors exceed the smallest disclosed figure). Whether every site is
*about* the same quantity is a reading question, not a computation, and the lab
says so rather than asserting it.
"""
import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "return_convention_lab", ROOT / "tools" / "return_convention_lab.py")
LAB = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = LAB
_SPEC.loader.exec_module(LAB)


class BoundTests(unittest.TestCase):
    def test_the_inequality_holds_over_random_portfolios(self):
        res = LAB.verify_bound(trials=4000)
        self.assertEqual(res["violations"], 0)
        self.assertTrue(res["holds"])

    def test_the_bound_is_TIGHT_not_merely_true(self):
        """Equality is attainable, so sigma_p/2 is the best possible data-free
        floor. A loose bound would not license the conclusion."""
        res = LAB.verify_bound(trials=4000)
        self.assertLess(
            res["tightest_ratio"], 1.05,
            "the bound never came close to equality — it may be loose, which would "
            "weaken every conclusion drawn from it",
        )
        self.assertGreaterEqual(res["tightest_ratio"], 1.0 - 1e-9)

    def test_single_asset_case_matches_the_closed_form(self):
        """One asset: sum w_i sigma_i^2 = sigma^2 and sigma_p = sigma, so the gap is
        exactly sigma/2 — the floor is attained, not merely approached."""
        for vol in (0.02, 0.113, 0.35):
            self.assertAlmostEqual(
                LAB.sharpe_gap([1.0], [vol], vol), LAB.gap_floor(vol), places=12)

    def test_identical_perfectly_correlated_assets_attain_the_floor(self):
        vol = 0.20
        gap = LAB.sharpe_gap([0.25] * 4, [vol] * 4, vol)  # perfectly correlated => sigma_p = vol
        self.assertAlmostEqual(gap, LAB.gap_floor(vol), places=12)

    def test_diversification_pushes_the_gap_ABOVE_the_floor(self):
        """Uncorrelated equal legs: sigma_p = sigma/sqrt(n) < sigma, so the true gap
        strictly exceeds the floor. Direction check — a flipped inequality would
        show up here."""
        vol, n = 0.20, 4
        port_vol = vol / (n ** 0.5)
        gap = LAB.sharpe_gap([1.0 / n] * n, [vol] * n, port_vol)
        self.assertGreater(gap, LAB.gap_floor(port_vol))

    def test_gap_floor_is_half_the_volatility(self):
        self.assertAlmostEqual(LAB.gap_floor(0.113), 0.0565, places=12)

    def test_zero_volatility_is_rejected_not_silently_infinite(self):
        with self.assertRaises(ValueError):
            LAB.sharpe_gap([1.0], [0.1], 0.0)


class ImpliedVolTests(unittest.TestCase):
    def test_implied_vol_inverts_the_sharpe_definition(self):
        self.assertAlmostEqual(LAB.implied_vol(7.85, 0.84), 0.0785 / 0.84, places=12)

    def test_zero_sharpe_is_rejected(self):
        with self.assertRaises(ValueError):
            LAB.implied_vol(5.0, 0.0)

    def test_every_committed_portfolio_has_a_floor_far_above_one_hundredth(self):
        """The mechanically certain corpus-facing claim: no portfolio the corpus
        actually reports can have a ~0.01 absolute convention gap."""
        floors = [row["gap_floor"] for row in LAB.implied_floors()]
        self.assertTrue(floors)
        self.assertGreater(
            min(floors), 0.01,
            "a committed portfolio now admits a ~0.01 gap — re-check the caveat",
        )
        # every implied volatility should be plausible for an equity/bond blend
        for row in LAB.implied_floors():
            self.assertTrue(
                3.0 < row["implied_vol_pct"] < 40.0,
                "implausible implied vol for {}: {:.2f}%".format(
                    row["label"], row["implied_vol_pct"]),
            )


class DisclosureSiteTests(unittest.TestCase):
    """Bidirectional: if a quoted line moves or is reworded, this fails rather than
    letting the lab misrepresent the file."""

    def test_every_quoted_site_still_says_what_the_lab_claims(self):
        stale = []
        for rel, line_no, expect, _klass in LAB.DISCLOSURE_SITES:
            text = LAB.read_site(rel, line_no)
            if expect not in text:
                stale.append("{}:{} no longer contains {!r} -> {!r}".format(
                    rel, line_no, expect, text[:90]))
        self.assertEqual(
            stale, [],
            "disclosure sites moved or were reworded:\n  " + "\n  ".join(stale),
        )

    def test_two_sites_are_explicitly_about_the_ABSOLUTE_level(self):
        """These two say 'absolute Sharpe' in so many words, so the reading is not
        in question for them and the data-free floor applies directly."""
        for rel, line_no in (("tools/static_product_study.py", 20),
                             ("docs/research/D6_overlay_build_study.md", 107)):
            text = LAB.read_site(rel, line_no).lower()
            self.assertIn(
                "absolute", text,
                "{}:{} no longer scopes itself to the absolute Sharpe level — "
                "re-read it before relying on the floor".format(rel, line_no),
            )

    def test_sites_output_refuses_to_quote_a_span(self):
        """Regression on this lab's OWN overstatement. An earlier version put the
        correct site, the differently-scoped site, and the error on one axis and
        quoted a 20x span. The span was manufactured; the output must say so."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            LAB.command_sites(None)
        out = buf.getvalue()
        self.assertIn("manufactured", out)
        self.assertIn("CITATION-PROPAGATION", out)

    def test_sites_are_classified_and_the_error_is_the_minority(self):
        """The corpus states this quantity CORRECTLY at three sites. A framing that
        loses that is the overstatement this lab was corrected for."""
        classes = [k for *_r, k in LAB.DISCLOSURE_SITES]
        self.assertIn("correct", classes, "the corpus's correct statements vanished")
        self.assertGreaterEqual(
            classes.count("correct"), 3,
            "study #2 states the gap correctly at three sites — keep them visible")
        self.assertGreaterEqual(classes.count("other-scope"), 2)
        for klass in classes:
            self.assertIn(klass, ("correct", "other-scope", "wrong"))

    def test_implied_names_the_portfolio_the_identity_is_about(self):
        """Regression: an earlier version quoted the SMALLEST floor (+0.045, Window
        A's ACTIVE leg) as though it bounded the Window-B 60/40 (+0.057)."""
        rows = {r["label"]: r for r in LAB.implied_floors()}
        self.assertIn(LAB.IDENTITY_PORTFOLIO, rows)
        identity = rows[LAB.IDENTITY_PORTFOLIO]
        self.assertGreater(
            identity["gap_floor"], min(r["gap_floor"] for r in rows.values()),
            "the identity portfolio is no longer distinguishable from the smallest "
            "floor — re-check which portfolio is being bounded",
        )
        self.assertAlmostEqual(identity["gap_floor"], 0.0565, places=3)


class CliTests(unittest.TestCase):
    def test_verify_command_runs_and_reports_the_verdict(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            LAB.main(["verify", "--trials", "500"])
        self.assertIn("bound HOLDS", buf.getvalue())

    def test_implied_command_reports_the_two_percent_consequence(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            LAB.main(["implied"])
        self.assertIn("2.00%", buf.getvalue())


if __name__ == "__main__":
    unittest.main()


class TwoDisjointMetricStacksTests(unittest.TestCase):
    """The corpus computes Sharpe two incompatible ways, and no tool bridges them.

    `docs/research/README.md` listed "no divergent Sharpe or drawdown implementations"
    among its methodology guarantees. That guarantee was prose with no executable
    check behind it, so it could be false for the whole life of the corpus without any
    run failing — and it is exactly the licence a reader needs to compare two published
    Sharpes directly. These tests make it checkable.
    """

    ACTIVE_STACK = ["mr_daily_lab.py", "power_study.py", "power_study_6040.py",
                    "overlay_build_study.py", "crisis_overlay_study.py"]
    STATIC_STACK = ["static_product_study.py", "gold_oos_study.py",
                    "bond_ladder_study.py"]

    def _src(self, name):
        path = ROOT / "tools" / name
        if not path.exists():
            self.skipTest("{} not present".format(name))
        return path.read_text(encoding="utf-8")

    def test_the_active_stack_uses_log_returns_only(self):
        for name in self.ACTIVE_STACK:
            src = self._src(name)
            for simple in ("pct_change", "expm1"):
                self.assertNotIn(
                    simple, src,
                    "{} now uses simple returns — if the stacks were UNIFIED, that is "
                    "good news, but every published Sharpe in this family shifts by "
                    "~0.12 and F147/F153 must be superseded.".format(name),
                )

    def test_the_static_stack_uses_simple_returns_only(self):
        for name in self.STATIC_STACK:
            src = self._src(name)
            self.assertNotIn(
                "np.log", src,
                "{} now uses log returns — see the message above; the stacks may have "
                "been unified and the web nodes need re-baselining.".format(name),
            )

    def test_no_tool_computes_both_conventions(self):
        """The reason nothing in the codebase could surface the discrepancy."""
        both = []
        for path in (ROOT / "tools").glob("*.py"):
            src = path.read_text(encoding="utf-8")
            if ("np.log" in src) and ("pct_change" in src or "expm1" in src):
                both.append(path.name)
        self.assertEqual(
            both, [],
            "a tool now computes both conventions ({}) — it could serve as the bridge "
            "that reconciles the two stacks. Check whether it does.".format(both),
        )

    def test_the_readme_no_longer_asserts_a_guarantee_that_is_false(self):
        """Bidirectional: restoring the claim fails unless the stacks really merged."""
        readme = (ROOT / "docs" / "research" / "README.md").read_text(encoding="utf-8")
        if "FALSE AS WRITTEN" in readme:
            return  # correction in place
        self.fail(
            "docs/research/README.md asserts 'no divergent Sharpe or drawdown "
            "implementations' without the F153 correction. That guarantee is false "
            "while the two stacks above remain disjoint — and the disjointness tests "
            "in this class are passing, so it is still false."
        )
