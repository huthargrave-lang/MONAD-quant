"""
Closed-end-fund discount selection: the NAV panel (src/research/cef_data.py) and the rules
(src/research/cef_classes.py), on synthetic data whose answers are known.
"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import cef_classes as cc  # noqa: E402
from src.research import cef_data as cd  # noqa: E402
from src.research.daily_data import Snapshot, SnapshotError  # noqa: E402

SESSIONS = pd.bdate_range("2010-01-04", periods=700)
FRIDAYS = SESSIONS[SESSIONS.dayofweek == 4]
FUNDS = [f"F{i:02d}" for i in range(20)]


def world(seed=0, stale=None, late=None):
    """Prices for 20 funds; fund i's discount drifts around -i%, with noise. ``stale``: a
    fund whose NAV stops updating halfway. ``late``: a fund listed 400 sessions in."""
    rng = np.random.default_rng(seed)
    close = pd.DataFrame(20 * np.exp(np.cumsum(rng.normal(0, 0.008, (len(SESSIONS), len(FUNDS))), axis=0)),
                         index=SESSIONS, columns=FUNDS)
    if late:
        close.loc[SESSIONS[:400], late] = np.nan
    snap = Snapshot(sha="s", dates=SESSIONS, assets=tuple(FUNDS), open=close.copy(), close=close,
                    dist=pd.DataFrame(0.0, index=SESSIONS, columns=FUNDS),
                    dtb3=pd.Series(1.0, index=SESSIONS), manifest={})
    price = close.reindex(FRIDAYS)
    disc = pd.DataFrame({f: -0.01 * i + rng.normal(0, 0.002, len(FRIDAYS)) for i, f in enumerate(FUNDS)},
                        index=FRIDAYS)
    nav = price / (1.0 + disc)
    if stale:
        nav.loc[FRIDAYS[len(FRIDAYS) // 2:], stale] = np.nan
        price.loc[FRIDAYS[len(FRIDAYS) // 2:], stale] = np.nan
    cats = {f: ("muni" if i % 2 else "equity") for i, f in enumerate(FUNDS)}
    panel = cd.NavPanel(sha="p", price=price, nav=nav, category=cats, manifest={})
    return snap, panel


def held(tranches):
    """Funds held by the first decision of tranche 0."""
    orders = tranches[0].close_orders
    row = orders.iloc[-1]
    return set(row.index[row > 0])


class Rules(unittest.TestCase):
    def test_level_picks_the_deepest_discounts(self):
        snap, panel = world()
        tr = cc.decide(snap, panel, {"class": "cef_discount", "params": {"signal": "level", "fraction": 0.25}})
        self.assertEqual(held(tr), {f"F{i:02d}" for i in range(15, 20)})

    def test_z52_is_relative_to_each_funds_own_history(self):
        """Every fund sits at its own mean, except F00, which just fell 10 points below it:
        z52 must pick F00 although its LEVEL is the shallowest."""
        snap, panel = world()
        panel.nav.loc[FRIDAYS[-1], "F00"] = panel.price.loc[FRIDAYS[-1], "F00"] / 0.90
        sig = cc._signals(snap, panel)
        last = SESSIONS[SESSIONS >= FRIDAYS[-1]][0]
        self.assertEqual(sig["z52"].loc[last].idxmin(), "F00")

    def test_category_selection_takes_the_cheapest_of_each_category(self):
        snap, panel = world()
        # 30% of two 10-fund categories is 3 + 3: above MIN_HOLDINGS (20% would be 4, below
        # it, and correctly place no order).
        tr = cc.decide(snap, panel, {"class": "cef_discount", "params": {"signal": "z52_cat", "fraction": 0.3}})
        picks = held(tr)
        self.assertEqual(len(picks), 6)
        cats = {panel.category[f] for f in picks}
        self.assertEqual(cats, {"muni", "equity"}, "both categories must contribute")

    def test_stale_navs_and_new_listings_are_ineligible(self):
        snap, panel = world(stale="F19", late="F18")
        sig = cc._signals(snap, panel)
        self.assertFalse(sig["eligible"].loc[SESSIONS[-1], "F19"], "a NAV weeks stale is not current")
        self.assertFalse(sig["eligible"].loc[SESSIONS[450], "F18"], "listed under a year")
        self.assertTrue(sig["eligible"].loc[SESSIONS[-1], "F18"])

    def test_the_benchmark_owns_every_eligible_fund_equally(self):
        snap, panel = world()
        tr = cc.decide(snap, panel, cc.REFERENCE)
        row = tr[0].close_orders.iloc[-1]
        self.assertTrue(np.allclose(row[row > 0], 1 / 20))

    def test_orders_trade_at_the_close_only(self):
        snap, panel = world()
        for point in cc.grid() + [cc.REFERENCE]:
            for tr in cc.decide(snap, panel, point):
                self.assertTrue(tr.open_orders.empty)

    def test_every_rule_is_truncation_invariant_across_both_datasets(self):
        snap, panel = world()
        cuts = [SESSIONS[i] for i in (380, 455, 530, 610, 690)]
        for point in cc.grid() + cc.taxloss_grid() + [cc.REFERENCE]:
            with self.subTest(point=point):
                self.assertEqual(cc.truncation_violations(snap, panel, point, cuts), [])

    def test_taxloss_equals_the_benchmark_outside_the_season(self):
        snap, panel = world()
        base = cc.decide(snap, panel, cc.REFERENCE)
        tl = cc.decide(snap, panel, {"class": "cef_taxloss", "params": {"signal": "ytd_return"}})
        for b, t in zip(base, tl):
            for d, row in b.close_orders.iterrows():
                if d.month in (3, 4, 5, 6, 7, 8, 9, 10):          # far from the season
                    self.assertTrue(np.allclose(t.close_orders.loc[d].reindex(row.index).fillna(0), row))
        season = [d for d in tl[0].close_orders.index if d.month == 12 and d.day >= 15]
        self.assertTrue(season, "an entry order in the second half of December")

    def test_the_grid_is_frozen_at_6_points(self):
        self.assertEqual(len(cc.grid()), 6)


class Panel(unittest.TestCase):
    def rows(self, n=60, bad=()):
        out = []
        for i in range(n):
            d = (pd.Timestamp("2015-01-02") + pd.Timedelta(weeks=i)).isoformat()
            price, nav = 10.0, 11.0
            disc = (price / nav - 1) * 100 + (5.0 if i in bad else 0.0)
            out.append({"DataDate": d, "Data": price, "NAVData": nav, "DiscountData": round(disc, 2)})
        return out

    def test_a_consistent_history_passes(self):
        df, removed = cd.validate_history("X", self.rows())
        self.assertEqual((len(df), removed), (60, 0))

    def test_one_inconsistent_row_is_removed_not_repaired(self):
        rows = self.rows(n=200, bad=(50,))
        df, removed = cd.validate_history("X", rows)
        self.assertEqual(removed, 1)
        self.assertNotIn(pd.Timestamp(rows[50]["DataDate"][:10]), df.index)

    def test_a_fund_with_many_inconsistent_rows_is_refused(self):
        with self.assertRaises(SnapshotError):
            cd.validate_history("X", self.rows(n=100, bad=(1, 2, 3)))

    def test_round_trip_is_content_addressed(self):
        price = pd.DataFrame({"A": [10.0, 10.5], "B": [5.0, np.nan]}, index=pd.to_datetime(["2015-01-02", "2015-01-09"]))
        nav = price * 1.1
        with tempfile.TemporaryDirectory() as td:
            sha = cd.write_panel({"price": price, "nav": nav}, {"category": {"A": "x", "B": "y"}},
                                 data_dir=Path(td))
            p = cd.load_panel(sha, data_dir=Path(td))
            self.assertAlmostEqual(float(p.discount.loc["2015-01-09", "A"]), 1 / 1.1 - 1, places=12)
            self.assertTrue(np.isnan(p.price.loc["2015-01-09", "B"]))


if __name__ == "__main__":
    unittest.main()
