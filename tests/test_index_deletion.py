"""
S&P 500 deletion rebound domain (src/research/deletion_classes.py;
docs/research/INDEX_DELETION_PROTOCOL.md): an event needs a price on its effective
session, entries wait k sessions, positions share 1/max(open, 10) with the rest in IJH.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import deletion_classes as dc  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402


def setup():
    dates = pd.bdate_range("2015-01-02", periods=600)
    close = pd.DataFrame(10.0, index=dates, columns=["IJH", "DEL", "REUSED"])
    close.loc[:dates[399], "REUSED"] = np.nan              # ticker reused later: no price at the event
    snap = Snapshot(sha="s", dates=dates, assets=("IJH", "DEL", "REUSED"), open=close, close=close,
                    dist=close * 0, dtb3=pd.Series(1.0, index=dates), manifest={})
    ev = dc.Deletions(sha="e", events=pd.DataFrame({
        "ticker": ["DEL", "REUSED"], "effective": [dates[100] + pd.Timedelta(hours=1), dates[200]]}))
    return snap, ev


class Events(unittest.TestCase):
    def test_the_stock_must_be_priced_on_its_effective_session(self):
        snap, ev = setup()
        got = dc.event_sessions(snap, ev)
        self.assertEqual(list(got["ticker"]), ["DEL"])
        self.assertEqual(int(got["d0"].iloc[0]), 101)      # first session on or after the date


class Orders(unittest.TestCase):
    def test_entry_and_weights(self):
        snap, ev = setup()
        o = dc.decide(snap, ev, {"class": "deletion_hold", "params": {"entry": 1}})[0].close_orders
        held = o.loc[o.index <= snap.dates[102]].iloc[-1]
        self.assertAlmostEqual(held["DEL"], 0.1)
        self.assertAlmostEqual(held["IJH"], 0.9)


if __name__ == "__main__":
    unittest.main()
