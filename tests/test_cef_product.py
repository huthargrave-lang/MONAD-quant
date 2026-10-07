"""The CEF product domain (src/research/cef_product_classes.py): static single-ETF
holdings, rebalanced in tranches; the window starts once both are priced."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import cef_product_classes as cp  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402


class Product(unittest.TestCase):
    def test_static_orders_window_and_no_lookahead(self):
        dates = pd.bdate_range("2017-01-02", periods=300)
        close = pd.DataFrame(20.0, index=dates, columns=["SPY", "PCEF", "CEFS"])
        close.loc[:dates[59], "CEFS"] = np.nan
        snap = Snapshot(sha="s", dates=dates, assets=("SPY", "PCEF", "CEFS"), open=close, close=close,
                        dist=close * 0, dtb3=pd.Series(1.0, index=dates), manifest={})
        tr = cp.decide(snap, cp.grid()[0])
        self.assertTrue((tr[0].open_orders["CEFS"] == 1.0).all())
        self.assertGreaterEqual(cp.scoring_start(snap), dates[60])
        self.assertEqual(cp.truncation_violations(snap, cp.REFERENCE, [dates[150]]), [])


if __name__ == "__main__":
    unittest.main()
