"""tools/o4_calibration.py (docs/research/O4_RESOLUTION_PROTOCOL.md): the synthetic books
have the effect sizes the protocol fixed, and one seed runs the frozen method end to end."""
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import o4_calibration as cal  # noqa: E402


class Calibration(unittest.TestCase):
    def test_the_moments_are_the_known_values(self):
        self.assertAlmostEqual(cal.GAP, 0.739, delta=0.005)         # top half of 10 normals (order statistics)
        self.assertGreater(cal.TIMING, 0.0)
        self.assertAlmostEqual(cal.CONVEX, 0.0081, delta=0.0005)

    def test_the_books_carry_the_fixed_effect_sizes(self):
        sel = [cal.book("S", np.random.default_rng(s))["active"].mean() * 252 for s in range(4)]
        self.assertAlmostEqual(float(np.mean(sel)), 0.022, delta=0.006)
        t = cal.book("T", np.random.default_rng(1))
        a_sel, a_tim = t["true_share"]
        self.assertAlmostEqual(a_sel.mean() / (a_sel.mean() + a_tim.mean()), 0.26, delta=0.12)
        c = cal.book("C", np.random.default_rng(2))
        self.assertAlmostEqual(float(c["active"].mean() * 252), 0.022, delta=0.008)

    def test_one_seed_runs_the_frozen_method(self):
        res = cal.run(1)
        self.assertEqual(set(res), {"S", "T", "C"})
        self.assertIn("passed", res["T"])
