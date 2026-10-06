"""
Country ETF selection (src/research/country_classes.py) on a synthetic panel: the rules
pick the right side of each signal, the grid has no duplicates, and every rule is
truncation invariant.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import allocation_stats as stats  # noqa: E402
from src.research import country_classes as cc  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402

FUNDS = cc.UNIVERSE[:18]
DATES = pd.bdate_range("2000-01-03", periods=900)


def world(seed=1):
    rng = np.random.default_rng(seed)
    drift = np.linspace(-0.0004, 0.0008, len(FUNDS))       # fund i trends harder with i
    close = pd.DataFrame(50 * np.exp(np.cumsum(drift + rng.normal(0, 0.004, (len(DATES), len(FUNDS))), axis=0)),
                         index=DATES, columns=FUNDS)
    return Snapshot(sha="w", dates=DATES, assets=tuple(FUNDS), open=close.shift(1).fillna(close.iloc[0]),
                    close=close, dist=pd.DataFrame(0.0, index=DATES, columns=FUNDS),
                    dtb3=pd.Series(1.0, index=DATES), manifest={})


class Rules(unittest.TestCase):
    def test_momentum_holds_the_strongest_third(self):
        snap = world()
        tr = cc.decide(snap, {"class": "country_select", "params": {"signal": "momentum", "months": 12}})
        last = tr[0].open_orders.iloc[-1]
        held = set(last.index[last > 0])
        self.assertTrue(held <= set(FUNDS[-8:]), held)

    def test_the_benchmark_is_equal_weight_and_trades_at_the_open(self):
        snap = world()
        tr = cc.decide(snap, cc.REFERENCE)
        row = tr[0].open_orders.iloc[-1]
        self.assertTrue(np.allclose(row[row > 0], 1 / len(FUNDS)))
        self.assertTrue(all(t.close_orders.empty for t in tr))

    def test_no_duplicates_and_truncation_invariant(self):
        snap = world()
        self.assertEqual(stats.duplicate_points({repr(p): cc.decide(snap, p) for p in cc.grid()}), [])
        cuts = [DATES[i] for i in (400, 600, 850)]
        for p in cc.grid() + [cc.REFERENCE]:
            with self.subTest(point=p):
                self.assertEqual(cc.truncation_violations(snap, p, cuts), [])


if __name__ == "__main__":
    unittest.main()
