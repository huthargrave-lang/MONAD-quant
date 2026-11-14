"""The forward-evidence route's published tables (src/research/watch_route_tables.py,
docs/research/FORWARD_ROUTE_TABLES.md; route.2.json ``build.published_with_it``): the
generated block reproduces byte for byte, the daily cross-check uses the engine's own
statistic, the constants are the frozen specs' and the policy's, and the decision debate's
figures are re-derived."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import forward_watch as fw  # noqa: E402
from src.research import watch_route_tables as t  # noqa: E402

DOC = REPO / "docs/research/FORWARD_ROUTE_TABLES.md"
BEGIN = "<!-- generated: src/research/watch_route_tables.py render(compute()) -->\n"
END = "\n<!-- end generated -->"


class PublishedTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = t.compute()

    def test_the_published_block_reproduces_byte_for_byte(self):
        doc = DOC.read_text(encoding="utf-8")
        block = doc[doc.index(BEGIN) + len(BEGIN): doc.index(END)]
        self.assertEqual(block, t.render(self.tables),
                         "regenerate with `venv/bin/python tools/admit.py --watch-tables` (numpy "
                         f"{np.__version__}; the doc was generated on the pinned numpy 2.4.3)")

    def test_the_debates_figures_are_re_derived(self):
        def near(rate, published, n_pub):
            se = math.sqrt(rate.se ** 2 + published * (1 - published) / n_pub)
            self.assertLess(abs(rate.p - published), 4 * se, (rate.p, published))

        f = self.tables["founders"][("H366200", 0.3)]["admit"]
        for h, p in ((20, 0.017), (40, 0.179), (100, 0.647)):           # consensus table, 100k paths
            near(f[h], p, 100_000)
        near(self.tables["later"][3]["admit"][40], 0.045, 100_000)        # route.2.json honest_statement
        c = self.tables["cusum"]
        near(c[0.3]["alarm"][20], 0.06, 200_000)                          # Q4 round 2, 200k paths
        near(c[-0.3]["alarm"][20], 0.81, 200_000)
        self.assertEqual((c[-0.3]["median_years"], c[0.0]["median_years"]), (13, 26))
        near(self.tables["round2"]["close"][20], 0.047, 200_000)          # the 4.7% was at ln 32
        self.assertLess(c[-0.3]["close"][20].p, 0.03)                     # ...and is 2.3% at ln 48

    def test_false_admission_stays_under_ville_and_the_daily_statistic_agrees(self):
        ville = math.exp(-t.FOUNDERS)
        for w, _f in t.WATCHES:
            self.assertLess(self.tables["founders"][(w, 0.0)]["admit"][t.LONG].p, ville)
        for s in (0.0, 0.3):
            d, y = self.tables["daily"][s]["daily"], self.tables["daily"][s]["yearly"]
            for what in ("admit", "close"):
                se = math.sqrt(d[what].se ** 2 + y[what][t.DAILY_YEARS].se ** 2)
                self.assertLess(abs(d[what].p - y[what][t.DAILY_YEARS].p), 4 * se, (s, what))


class TheModel(unittest.TestCase):
    def test_the_constants_are_the_frozen_specs_and_the_policys(self):
        pol = fw.governing_policy()
        for w, first in t.WATCHES:
            spec, _h = fw.load(w)
            ev = spec["evaluation"]
            self.assertEqual((ev["theta1"], ev["alpha"], ev["beta"]), (t.THETA, t.ALPHA, t.BETA))
            self.assertAlmostEqual(fw.route_boundary(spec, watch=w), t.FOUNDERS)
            self.assertEqual(fw.first_decisive_anniversary(spec), first)
            self.assertEqual(pol["test"]["first_decisive_anniversary"][w], first)
        self.assertAlmostEqual(t.FOUNDERS, pol["alpha_spending"]["founding_cohort"]["boundary_nats"])
        self.assertIn(f"{t.boundary(3):.3f} nats", pol["alpha_spending"]["honest_statement"])
        self.assertAlmostEqual(t.LOWER, math.log(0.2 / 0.95))
        self.assertIn(f"h = {t.CUSUM_H:g}", pol["de_admission"]["cusum"])

    def test_wald_gives_0207_at_alpha_over_3_and_the_policys_0205_is_the_alpha_over_2_value(self):
        self.assertAlmostEqual(t.wald(t.FOUNDERS)[1], 0.2070, places=4)
        self.assertAlmostEqual(t.wald(math.log(32))[1], 0.2053, places=4)    # round 3: "0.205 at alpha/2"
        self.assertAlmostEqual(t.wald(math.log(96))[1], 0.2088, places=4)    # "0.209 at alpha/6"
        self.assertIn("about 0.205", fw.governing_policy()["test"]["beta_prime"])   # the frozen wording
        self.assertAlmostEqual(t.wald(math.log(16))[0], 0.05, places=4)       # the spec's own design
        self.assertAlmostEqual(t.wald(math.log(16))[1], 0.20, places=4)

    def test_the_daily_llr_is_forward_watchs_own_statistic(self):
        rng = np.random.default_rng(7)
        x = rng.normal(0.0004, 0.004, (3, 5 * 252))
        fast = t.daily_llr(x)
        upper, lower = math.log(48), t.LOWER
        for p in range(3):
            for k in range(1, 6):
                series = {i: float(v) for i, v in enumerate(x[p, : 252 * k])}
                rep = fw._reading(series, series, pd.Timestamp("2030-01-01"), k, t.THETA, upper, lower)
                self.assertAlmostEqual(fast[p, k - 1], rep["llr"], places=9)

    def test_every_cell_has_its_own_fixed_stream(self):
        self.assertEqual(len(set(t.CELLS.values())), len(t.CELLS))
        a = t.route_rates(t.FOUNDERS, sharpe=0.3, first=2, cell=3, paths=2000, years=30, horizons=(20,))
        b = t.route_rates(t.FOUNDERS, sharpe=0.3, first=2, cell=3, paths=2000, years=30, horizons=(20,))
        self.assertEqual(a["admit"][20].p, b["admit"][20].p)


if __name__ == "__main__":
    unittest.main()
