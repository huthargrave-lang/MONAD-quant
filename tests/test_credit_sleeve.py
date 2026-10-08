"""
Fallen-angel credit sleeve domain (src/research/credit_classes.py): static single-ETF
sleeves, rebalanced in tranches; the window starts once both funds are priced.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import credit_classes as cc  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402


class Sleeve(unittest.TestCase):
    def test_static_orders_and_window(self):
        dates = pd.bdate_range("2012-01-02", periods=300)
        close = pd.DataFrame(50.0, index=dates, columns=["ANGL", "HYG"])
        close.loc[:dates[49], "ANGL"] = np.nan
        snap = Snapshot(sha="s", dates=dates, assets=("ANGL", "HYG"), open=close, close=close,
                        dist=close * 0, dtb3=pd.Series(1.0, index=dates), manifest={})
        tr = cc.decide(snap, {"class": "static_sleeve", "params": {"asset": "ANGL"}})
        self.assertEqual(len(tr), 21)
        self.assertTrue((tr[0].open_orders["ANGL"] == 1.0).all())
        self.assertGreaterEqual(cc.scoring_start(snap), dates[50])
        self.assertEqual(cc.truncation_violations(snap, cc.grid()[0], [dates[100], dates[200]]), [])


if __name__ == "__main__":
    unittest.main()
