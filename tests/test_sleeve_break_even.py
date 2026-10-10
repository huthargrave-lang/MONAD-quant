"""tools/sleeve_break_even.py: the break-even bisection on synthetic series."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import sleeve_break_even as sbe  # noqa: E402


class BreakEven(unittest.TestCase):
    def test_the_sharpe_break_even_makes_the_mix_match_the_product(self):
        rng = np.random.default_rng(0)
        d = pd.bdate_range("2010-01-04", periods=2000)
        p = pd.Series(rng.normal(0.0003, 0.007, len(d)), index=d)
        b = pd.Series(0.8 * p.to_numpy() + rng.normal(0.0001, 0.009, len(d)), index=d)
        cash = pd.Series(0.00005, index=d)
        a = sbe.break_even(lambda r: sbe.sharpe(r, cash), sbe.sharpe(p, cash), p, b, 0.10)
        self.assertAlmostEqual(sbe.sharpe(sbe.mix(p, b, 0.10, a), cash), sbe.sharpe(p, cash), places=8)
        d_a = sbe.break_even(sbe.max_drawdown, sbe.max_drawdown(p), p, b, 0.10)
        self.assertAlmostEqual(sbe.max_drawdown(sbe.mix(p, b, 0.10, d_a)), sbe.max_drawdown(p), places=6)

    def test_no_crossing_is_none(self):
        d = pd.bdate_range("2010-01-04", periods=300)
        p = pd.Series(0.001, index=d)
        b = pd.Series(-0.05, index=d)
        self.assertIsNone(sbe.break_even(sbe.max_drawdown, 0.0, p, b, 0.2))
