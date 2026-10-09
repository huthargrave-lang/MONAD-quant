"""The convexity-robust control (src/research/convexity_control.py,
docs/research/CONVEXITY_CONTROL_PROTOCOL.md) on synthetic books outside the calibration's
seeds: the machinery runs end to end, loadings are ex ante, and the state-conditional
loadings use only same-state past blocks."""
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import convexity_control as tool  # noqa: E402

from src.research import convexity_control as cx  # noqa: E402


def blocks_of(name, seed):
    b = tool.book(name, seed)
    return b, cx.build_blocks(b["active"], b["delta"], b["assets"], b["factor"], b["bench"], b["grid"])


class Machinery(unittest.TestCase):
    def test_a_convex_book_reads_exposure_and_a_selection_book_survives(self):
        _b, blk = blocks_of("C", 9002)
        c = cx.control(blk, min_blocks=48, window=156, minimum=48, reps=3)
        self.assertLess(c["s"], 0.25)
        self.assertGreater(c["convex_ann"], 0.0)
        _b, blk = blocks_of("S", 9000)
        self.assertEqual(cx.control(blk, min_blocks=48, window=156, minimum=48, reps=3)["verdict"], "SURVIVES")

    def test_loadings_use_no_data_from_the_current_block_or_later(self):
        _b, blk = blocks_of("C", 9010)
        coef = cx.loadings(blk, window=156, minimum=48)
        k = 400
        y2 = blk.y.copy()
        y2[k:] *= -2.0
        coef2 = cx.loadings(blk, window=156, minimum=48, y=y2)
        np.testing.assert_array_equal(coef[: k + 1], coef2[: k + 1])

    def test_a_missing_factor_inside_the_sample_is_refused(self):
        _b, blk = blocks_of("S", 9011)
        blk.missing[100] = True
        with self.assertRaises(ValueError):
            cx.control(blk, min_blocks=48, window=156, minimum=48, reps=0)

    def test_the_product_world_has_the_stated_scale(self):
        b = tool.product_book("alpha", 9012)
        self.assertEqual(len(b["grid"]) // 5, tool.PRODUCT["blocks"])
        # one seed's mean active has a standard error of ~3%/yr (9% tracking error over 8.4
        # years); six seeds bring it to ~1.3%/yr
        means = [float(tool.product_book(k, 9012 + i)["active"].mean() * 252)
                 for i in range(6) for k in ("alpha", "convex")]
        self.assertAlmostEqual(float(np.mean(means)), 0.054, delta=0.03)


class Planted(unittest.TestCase):
    def test_the_planted_payoff_is_scaled_to_the_raw_active_and_lands_in_the_active(self):
        import pandas as pd
        b = tool.book("S", 9020)
        cols = list(b["assets"].columns)
        cat = {c: f"k{i // 10}" for i, c in enumerate(cols)}
        elig = pd.DataFrame(True, index=b["dates"], columns=cols)
        inputs = {"grid": b["grid"], "delta": b["delta"], "assets": b["assets"], "category": cat, "elig": elig,
                  "factor": b["factor"], "active": b["active"], "bench": b["bench"],
                  "bench_weights": pd.DataFrame(1.0 / len(cols), index=b["dates"], columns=cols)}
        raw = float(b["active"][b["grid"].index][b["grid"] >= tool.MIN_BLOCKS].mean()) * 50.4
        for form in ("static", "conditional"):
            pl = tool._planted(inputs, form)
            self.assertAlmostEqual(pl["planted_ann"], raw, places=10)
            added = (pl["active"] - b["active"])[b["grid"].index][b["grid"] >= tool.MIN_BLOCKS].mean() * 50.4
            self.assertAlmostEqual(float(added), raw, places=10)
