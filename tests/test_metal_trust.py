"""Physical-metal trust discount tilt (src/research/metal_trust_classes.py)."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import metal_trust_classes as mt  # noqa: E402
from src.research.cef_data import NavPanel  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402
from src.research.daily_domains import DOMAINS  # noqa: E402

SESSIONS = pd.bdate_range("2010-01-04", "2014-12-31")


def market(seed=0):
    rng = np.random.default_rng(seed)
    cols = ["SPY", "PHYS", "GLD", "PSLV", "SLV"]
    close = pd.DataFrame({c: 20 * np.exp(np.cumsum(rng.normal(0, 0.01, len(SESSIONS)))) for c in cols},
                         index=SESSIONS)
    snap = Snapshot(sha="s" * 64, dates=SESSIONS, assets=tuple(cols), open=close, close=close,
                    dist=close * 0.0, dtb3=pd.Series(1.0, index=SESSIONS), manifest={})
    weeks = pd.date_range("2009-01-02", "2014-12-26", freq="W-FRI")
    disc = {t: pd.Series(0.03 * np.sin(np.arange(len(weeks)) / 6.0 + k) + rng.normal(0, 0.005, len(weeks)),
                         index=weeks) for k, t in enumerate(("PHYS", "PSLV"))}
    nav = pd.DataFrame({t: 10.0 for t in disc}, index=weeks)
    price = pd.DataFrame({t: 10.0 * (1 + d) for t, d in disc.items()})
    panel = NavPanel(sha="p" * 64, price=price, nav=nav, category={}, manifest={})
    return snap, panel


class StateMachine(unittest.TestCase):
    def test_hysteresis_transitions(self):
        z = pd.Series([0.0, -1.2, -0.5, 0.1, 1.5, 0.3, -0.2, -1.1, 1.0])
        self.assertEqual(list(mt.step_states(z, 1.0, 0.0)),
                         [0.5, 1.0, 1.0, 0.5, 0.0, 0.0, 0.5, 1.0, 0.0])

    def test_a_session_reads_strictly_earlier_nav_and_stale_reads_neutral(self):
        snap, panel = market()
        p = mt.grid()[0]["params"]
        st = mt.session_states(panel, "PHYS", snap.dates, p)
        full = mt.step_states(mt.zscores(panel, "PHYS", 52), 1.0, 0.0)
        friday = full.index[full.index >= pd.Timestamp("2012-01-01")][0]
        self.assertEqual(st[friday], full.iloc[full.index.get_loc(friday) - 1])
        gap = panel.price.drop(index=panel.price.index[(panel.price.index > "2013-03-01") &
                                                       (panel.price.index < "2013-04-15")])
        stale = NavPanel(sha="q", price=gap, nav=panel.nav.loc[gap.index], category={}, manifest={})
        st2 = mt.session_states(stale, "PHYS", snap.dates, p)
        self.assertTrue((st2.loc["2013-03-20":"2013-04-12"] == 0.5).all())

    def test_weights_hold_each_pair_at_half_and_no_lookahead(self):
        snap, panel = market()
        (pt,) = mt.grid()
        w = mt.weights(snap, panel, pt)
        self.assertTrue(np.allclose(w[["PHYS", "GLD"]].sum(axis=1), 0.5))
        self.assertTrue(np.allclose(w.sum(axis=1), 1.0))
        self.assertGreater((w["PHYS"] != 0.25).mean(), 0.1)
        self.assertEqual(mt.truncation_violations(snap, panel, pt, [SESSIONS[700]]), [])
        self.assertEqual(len(mt.decide(snap, panel, pt)), 21)

    def test_episodes_count_departures_from_neutral(self):
        self.assertEqual(mt.episodes(pd.Series([0.5, 1, 1, 0.5, 0, 0.5, 0.5, 1])), 3)

    def test_registry(self):
        d = DOMAINS["metal_trust_discount"]
        self.assertEqual((d.primary, d.sign, d.prior_search_trials, d.panel_prefix),
                         ("active", 1, 22, "CEFNAV"))
        self.assertEqual(d.reference["params"]["weights"], {"PHYS": .25, "GLD": .25, "PSLV": .25, "SLV": .25})


if __name__ == "__main__":
    unittest.main()
