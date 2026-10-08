"""Live product pairs (src/research/product_pairs.py): a generic static candidate vs
benchmark; the spin-off product domain is registered with its own family."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import product_pairs as pp  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402
from src.research.daily_domains import DOMAINS  # noqa: E402
from src.research.daily_trials import family_name  # noqa: E402


class Pair(unittest.TestCase):
    def test_static_orders_window_and_no_lookahead(self):
        pair = pp.ProductPair(candidate="AAA", benchmark="BBB", eras=(("start", "end"),))
        dates = pd.bdate_range("2010-01-04", periods=300)
        close = pd.DataFrame(10.0, index=dates, columns=["SPY", "AAA", "BBB"])
        close.loc[:dates[39], "AAA"] = np.nan
        snap = Snapshot(sha="s", dates=dates, assets=("SPY", "AAA", "BBB"), open=close, close=close,
                        dist=close * 0, dtb3=pd.Series(1.0, index=dates), manifest={})
        self.assertTrue((pair.decide(snap, pair.grid()[0])[0].open_orders["AAA"] == 1.0).all())
        self.assertGreaterEqual(pair.scoring_start(snap), dates[40])
        self.assertEqual(pair.truncation_violations(snap, pair.reference, [dates[100]]), [])

    def test_the_spinoff_product_domain_is_its_own_family(self):
        d = DOMAINS["spinoff_product"]
        self.assertEqual(d.reference["params"]["asset"], "IJH")
        self.assertEqual(d.grid()[0]["params"]["asset"], "CSD")
        self.assertEqual(family_name("spinoff_product"), "spinoff_product.v1")


if __name__ == "__main__":
    unittest.main()
