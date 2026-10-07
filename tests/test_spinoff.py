"""
Spin-off drift domain (src/research/spinoff_classes.py; docs/research/SPINOFF_PROTOCOL.md):
event sessions need a first price near the first 10-12B, entries wait k sessions, and
positions share 1/max(open, 10) with the rest in IWM.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import spinoff_classes as sc  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402


def setup():
    dates = pd.bdate_range("2015-01-02", periods=900)
    close = pd.DataFrame(10.0, index=dates, columns=["IWM", "NEW", "OLD", "LATE"])
    close.loc[:dates[99], "NEW"] = np.nan          # first priced at session 100
    close.loc[:dates[699], "LATE"] = np.nan        # first priced long after its 10-12B
    snap = Snapshot(sha="s", dates=dates, assets=("IWM", "NEW", "OLD", "LATE"), open=close, close=close,
                    dist=close * 0, dtb3=pd.Series(1.0, index=dates), manifest={})
    ev = sc.SpinEvents(sha="e", events=pd.DataFrame({
        "ticker": ["NEW", "OLD", "LATE"], "cik": [1, 2, 3],
        "first_10_12b": [dates[100] - pd.Timedelta(days=60), dates[300], dates[100]]}))
    return snap, ev


class Events(unittest.TestCase):
    def test_only_a_first_price_near_the_registration_is_an_event(self):
        snap, ev = setup()
        got = sc.event_sessions(snap, ev)
        self.assertEqual(list(got["ticker"]), ["NEW"])        # OLD was already listed; LATE abandoned
        self.assertEqual(int(got["d0"].iloc[0]), 100)


class Orders(unittest.TestCase):
    def test_entry_after_k_sessions_and_slot_weights(self):
        snap, ev = setup()
        o = sc.decide(snap, ev, {"class": "spinoff_hold", "params": {"entry": 21}})[0].close_orders
        held = o.loc[o.index <= snap.dates[120]].iloc[-1]
        self.assertAlmostEqual(held["NEW"], 0.1)
        self.assertAlmostEqual(held["IWM"], 0.9)
        before = o.loc[o.index <= snap.dates[119]].iloc[-1]
        self.assertNotIn("NEW", before[before > 0].index)


if __name__ == "__main__":
    unittest.main()
