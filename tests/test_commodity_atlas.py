"""tools/commodity_atlas.py: the discovery firewall and the statistics' signs."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import commodity_atlas as ca  # noqa: E402


def prices(n=1500, seed=0, lag=0, beta=1.0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2006-01-02", periods=n)
    a = rng.normal(0, 0.02, n)
    spy = rng.normal(0.0003, 0.01, n)
    m = beta * np.roll(a, lag) + 0.5 * spy + rng.normal(0, 0.01, n)
    return pd.DataFrame({"ANC": 100 * np.exp(np.cumsum(a)), "MEM": 100 * np.exp(np.cumsum(m)),
                         "SPY": 100 * np.exp(np.cumsum(spy))}, index=idx)


class Firewall(unittest.TestCase):
    def test_a_row_at_or_after_the_bound_is_refused(self):
        leaky = lambda syms, s, e: prices().loc[:"2010-06-01"]          # noqa: E731
        with self.assertRaises(RuntimeError):
            ca.fetch(["X"], "2006-01-01", "2010-01-01", get=leaky)
        ok = lambda syms, s, e: prices().loc[:"2009-12-31"]              # noqa: E731
        self.assertLess(ca.fetch(["X"], "2006-01-01", "2010-01-01", get=ok).index.max(),
                        pd.Timestamp("2010-01-01"))


class Statistics(unittest.TestCase):
    def test_exposure_finds_the_anchor_beta_net_of_spy(self):
        close = prices(beta=1.5)
        e = ca.exposure(ca.weekly(close), "MEM", "ANC")
        self.assertAlmostEqual(e["partial_beta"], 1.5, delta=0.15)
        self.assertGreater(e["corr"], 0.8)

    def test_a_one_week_lag_shows_as_lead_lag_and_beats_the_placebo(self):
        close = prices(lag=5, n=2500)                                      # 5 sessions = 1 week
        ll = ca.lead_lag(ca.weekly(close), "MEM", "ANC", np.random.default_rng(0))
        self.assertGreater(ll["a1_m1_raw"]["corr"], 0.3)
        self.assertLess(ll["a1_m1_raw"]["placebo_p"], 0.01)
        none = ca.lead_lag(ca.weekly(prices(lag=0, n=2500, seed=1)), "MEM", "ANC", np.random.default_rng(0))
        self.assertLess(abs(none["a1_m1_raw"]["corr"]), 0.15)

    def test_eia_days_move_to_thursday_in_a_monday_holiday_week(self):
        s = pd.bdate_range("2015-01-05", "2015-01-23").drop(pd.Timestamp("2015-01-19"))
        days = ca.eia_days(s)
        self.assertIn(pd.Timestamp("2015-01-07"), days)
        self.assertIn(pd.Timestamp("2015-01-22"), days)                  # MLK week: Thursday
        self.assertNotIn(pd.Timestamp("2015-01-21"), days)


if __name__ == "__main__":
    unittest.main()
