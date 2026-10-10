"""tools/snapshot_tr_check.py: a missing distribution shows up as a yearly gap."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import snapshot_tr_check as chk  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402


class Check(unittest.TestCase):
    def test_a_missing_capital_gain_is_flagged_in_its_year_only(self):
        dates = pd.bdate_range("2019-01-02", "2021-12-31")
        close = pd.DataFrame({"AAA": np.linspace(100, 130, len(dates))}, index=dates)
        snap = Snapshot(sha="s", dates=dates, assets=("AAA",), open=close, close=close,
                        dist=close * 0.0, dtb3=pd.Series(0.0, index=dates), manifest={})
        adjusted = close["AAA"].copy()
        # Yahoo's adjusted series includes a 5% capital gain paid in 2020 that the snapshot lacks.
        adjusted.loc[: pd.Timestamp("2020-12-14")] *= 1 / 1.05
        rows = chk.compare(snap, ["AAA"], fetch=lambda *a: adjusted)
        flagged = {r["year"] for r in rows if r["flag"]}
        self.assertEqual(flagged, {2020})


if __name__ == "__main__":
    unittest.main()
