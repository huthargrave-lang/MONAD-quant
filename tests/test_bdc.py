"""
BDC NAV panels (src/research/bdc_data.py): the knowledge state is the latest PERIOD known,
never the last row filed (a 10-K reports a decade of NAVs at once), and it only moves
forward in time.
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research.bdc_data import BdcPanel  # noqa: E402


def panel(rows):
    df = pd.DataFrame(rows, columns=["ticker", "period_end", "nav", "filed", "known"])
    for c in ("period_end", "filed", "known"):
        df[c] = pd.to_datetime(df[c])
    return BdcPanel(sha="t", rows=df, manifest={})


class KnowledgeState(unittest.TestCase):
    def test_a_10k_with_old_highlights_does_not_replace_the_current_nav(self):
        p = panel([("X", "2023-09-30", 10.0, "2023-11-01", "2023-11-02"),
                   ("X", "2014-12-31", 16.0, "2024-02-22", "2024-02-23"),   # financial highlights
                   ("X", "2023-12-31", 10.5, "2024-02-22", "2024-02-23")])
        days = pd.bdate_range("2023-11-01", "2024-03-01")
        nav = p.nav_known(days)["X"]
        self.assertTrue(pd.isna(nav.loc["2023-11-01"]), "not known before its known date")
        self.assertEqual(nav.loc["2023-11-02"], 10.0)
        self.assertEqual(nav.loc["2024-02-23"], 10.5, "the latest period, not an old highlight")
        age = p.period_age_days(days)["X"]
        self.assertEqual(age.loc["2024-02-23"], (pd.Timestamp("2024-02-23") - pd.Timestamp("2023-12-31")).days)

    def test_a_late_comparative_never_moves_knowledge_backwards(self):
        p = panel([("X", "2023-12-31", 10.5, "2024-02-22", "2024-02-23"),
                   ("X", "2023-09-30", 9.0, "2024-05-01", "2024-05-02")])
        nav = p.nav_known(pd.bdate_range("2024-02-23", "2024-06-01"))["X"]
        self.assertEqual(nav.loc["2024-05-02"], 10.5)


if __name__ == "__main__":
    unittest.main()
