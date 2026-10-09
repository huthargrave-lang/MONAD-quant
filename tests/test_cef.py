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
        for point in cc.grid() + cc.taxloss_grid() + cc.banded_grid() + [cc.REFERENCE]:
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

    def test_banding_keeps_holdings_until_they_leave_the_exit_band(self):
        snap, panel = world()
        plain = cc.decide(snap, panel, {"class": "cef_discount", "params": {"signal": "level", "fraction": 0.2}})
        band = cc.decide(snap, panel, {"class": "cef_banded", "params": {"signal": "level", "exit": 0.5}})
        changes = lambda tr: sum(int(((a > 0) != (b > 0)).sum()) for (_, a), (_, b) in
                                 zip(tr.close_orders.iloc[:-1].iterrows(), tr.close_orders.iloc[1:].iterrows()))
        self.assertLessEqual(changes(band[0]), changes(plain[0]))

    def test_the_grid_is_frozen_at_6_points(self):
        self.assertEqual(len(cc.grid()), 6)


class LiveRegistrationGuard(unittest.TestCase):
    def test_a_family_with_a_live_hypothesis_refuses_unacknowledged_runs(self):
        import json
        from src.research import daily_trials
        with tempfile.TemporaryDirectory() as td:
            pre, ver = Path(td) / "prereg", Path(td) / "verdicts"
            pre.mkdir()
            (pre / "H1.json").write_text(json.dumps({"hypothesis": "H1", "family": "cef_discount.v1"}))
            (pre / "H2.json").write_text(json.dumps({"hypothesis": "H2", "family": "daily_alloc.v1"}))
            self.assertEqual(daily_trials.live_registrations("cef_discount.v1", pre, ver), ["H1"])
            (ver / "H1").mkdir(parents=True)
            (ver / "H1" / "x.json").write_text(json.dumps({"verdict": "REJECT"}))
            self.assertEqual(daily_trials.live_registrations("cef_discount.v1", pre, ver), [])

    def test_the_real_cef_family_refuses_until_every_live_hypothesis_is_acknowledged(self):
        from src.research import daily_trials
        live = daily_trials.live_registrations("cef_discount.v1")
        self.assertIn("H404701", live)
        with self.assertRaises(SystemExit):
            daily_trials.refuse_unacknowledged("cef_discount.v1", live[:-1])
        daily_trials.refuse_unacknowledged("cef_discount.v1", live)


class Picks(unittest.TestCase):
    def test_current_holdings_average_the_tranches_latest_targets(self):
        sys.path.insert(0, str(REPO / "tools"))
        import cef_picks
        from src.research.daily_domains import Context
        snap, panel = world()
        h = cef_picks.current_holdings(Context(snap=snap, panel=panel),
                                       {"class": "cef_discount", "params": {"signal": "level", "fraction": 0.25}})
        self.assertAlmostEqual(float(h["weight"].sum()), 1.0, places=9)
        self.assertTrue(set(h.index) <= {f"F{i:02d}" for i in range(14, 20)})


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

    def fake_get(self, histories, fail=()):
        import json as _json

        def get(url):
            if url.endswith("DailyPricing?props=Ticker,Name,CategoryName"):
                return _json.dumps([{"Ticker": t, "Name": t, "CategoryName": "Equity-Commodities"}
                                    for t in histories]).encode()
            t = url.split("pricinghistory/")[1].split("/")[0]
            if t in fail:
                raise OSError("connection reset")
            self.requested.append(t)
            return _json.dumps({"Data": {"PriceHistory": histories[t]}}).encode()
        return get

    def test_a_ticker_subset_fetches_only_those_funds(self):
        self.requested = []
        hist = {t: self.rows() for t in ("PHYS", "PSLV", "OTHER")}
        frames, report = cd.build_panel(get=self.fake_get(hist), pause=0.0, tickers=["PHYS", "PSLV"])
        self.assertEqual(sorted(self.requested), ["PHYS", "PSLV"])
        self.assertEqual(sorted(frames["nav"].columns), ["PHYS", "PSLV"])
        self.assertEqual(report["requested"], ["PHYS", "PSLV"])
        with self.assertRaises(SnapshotError):
            cd.build_panel(get=self.fake_get(hist), pause=0.0, tickers=["PHYS", "GONE"])

    def test_strict_raises_where_the_default_drops(self):
        self.requested = []
        hist = {t: self.rows() for t in ("PHYS", "PSLV")}
        frames, report = cd.build_panel(get=self.fake_get(hist, fail=("PSLV",)), pause=0.0)
        self.assertIn("PSLV", report["dropped"])
        with self.assertRaises(SnapshotError):
            cd.build_panel(get=self.fake_get(hist, fail=("PSLV",)), pause=0.0, tickers=["PHYS", "PSLV"],
                           strict=True)

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


class ForwardLog(unittest.TestCase):
    def test_entries_append_in_order_and_verify(self):
        sys.path.insert(0, str(REPO / "tools"))
        import forward_log
        from unittest import mock
        from src.research.daily_domains import Context
        snap, panel = world()
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(forward_log, "LOG_DIR", Path(td)), \
                    mock.patch.object(forward_log.prereg, "load", return_value=({}, "h" * 64)):
                cand = {"class": "cef_discount", "params": {"signal": "level", "fraction": 0.25}}
                row = forward_log.entry("H9", Context(snap=snap, panel=panel), cand, "h" * 64)
                forward_log.append("H9", row)
                with self.assertRaises(SystemExit):
                    forward_log.append("H9", row)            # the same session twice
                self.assertEqual(forward_log.verify("H9"), [])
                self.assertAlmostEqual(sum(row["weights"].values()), 1.0, places=6)


class FreshWindow(unittest.TestCase):
    def test_the_fresh_window_clears_the_snapshot_floor(self):
        """A 900-day window held 617 sessions and the first forward_log run failed on
        daily_data.MIN_SESSIONS (2026-10-06); pin the window against the floor."""
        sys.path.insert(0, str(REPO / "tools"))
        import cef_picks
        from src.research.daily_data import MIN_SESSIONS
        sessions = len(pd.bdate_range(end=pd.Timestamp("2026-10-06"), periods=cef_picks.FRESH_CALENDAR_DAYS * 5 // 7))
        self.assertGreater(sessions * 0.96, MIN_SESSIONS)    # ~4% of weekdays are holidays
