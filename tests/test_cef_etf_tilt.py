"""The CEF vs matched-ETF discount tilt (src/research/cef_etf_tilt.py) on a synthetic panel:
matching by R², screens, neutral windows, equal-per-family slots, no look-ahead, and the
exact within/category decomposition of the report tool."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from src.research import cef_etf_tilt as ce  # noqa: E402
from src.research.cef_data import NavPanel  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402

MUNI = "Fixed Income - Municipal-Municipal"
EQ = "Equity-U.S. Equity"


def world(seed=0, n_days=2600):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2006-01-02", periods=n_days)
    etf_r = {e: rng.normal(0.0002, s, n_days) for e, s in (("MUB", 0.004), ("TFI", 0.004), ("SPY", 0.01), ("IWM", 0.012))}
    etf_r["TFI"] = 0.3 * etf_r["MUB"] + rng.normal(0, 0.004, n_days)
    close = {e: 50 * np.exp(np.cumsum(r)) for e, r in etf_r.items()}
    funds = {}
    for k in range(6):
        funds[f"M{k}"] = (MUNI, "MUB", 1.6)
        funds[f"E{k}"] = (EQ, "SPY", 1.1)
    nav_daily = {}
    for f, (_c, etf, beta) in funds.items():
        nav_r = beta * etf_r[etf] + rng.normal(0, 0.002, n_days)
        nav_daily[f] = 10 * np.exp(np.cumsum(nav_r))
        disc = 0.05 * np.sin(np.arange(n_days) / (60 + 7 * len(f))) + rng.normal(0, 0.005, n_days)
        close[f] = nav_daily[f] * (1 + disc - 0.05)
    cl = pd.DataFrame(close, index=dates)
    cols = ["SPY"] + [c for c in cl.columns if c != "SPY"]
    cl = cl[cols]
    snap = Snapshot(sha="s" * 64, dates=dates, assets=tuple(cols), open=cl.shift(1).fillna(cl.iloc[0]), close=cl,
                    dist=cl * 0.0, dtb3=pd.Series(1.0, index=dates), manifest={})
    fridays = dates[dates.dayofweek == 4]
    nav = pd.DataFrame({f: pd.Series(v, index=dates).reindex(fridays) for f, v in nav_daily.items()})
    price = cl[list(funds)].reindex(fridays)
    panel = NavPanel(sha="p" * 64, price=price, nav=nav, category={f: c for f, (c, _e, _b) in funds.items()}, manifest={})
    return snap, panel, funds


def inputs_for(snap, panel, **over):
    fams = ce.universe(panel)
    mapping = {}
    for f in fams:
        m = ce.match(panel, snap, f, fams[f])
        assert m["status"] == "matched", m
        mapping[f] = {k: v for k, v in m.items() if k != "status"}
    data = {"families": {f: fams[f] for f in mapping}, "mapping": mapping, "corporate_actions": {},
            "index_changes": {}, "screens": {"failed": []}, "tiers": {f: {"tier": "cef"} for f in mapping},
            "window_start": str(ce.window_start(snap, fams, mapping).date()), **over}
    return ce.Inputs(sha="i" * 64, panel=panel, data=data)


class Matching(unittest.TestCase):
    def test_r2_picks_the_true_etf_and_its_beta(self):
        snap, panel, funds = world()
        for f in ("M0", "E3"):
            m = ce.match(panel, snap, f, ce.universe(panel)[f])
            self.assertEqual(m["etf"], funds[f][1])
            self.assertAlmostEqual(m["beta"], funds[f][2], delta=0.15)
            self.assertGreaterEqual(m["r2"], 0.5)

    def test_universe_and_exclusions(self):
        _snap, panel, _f = world()
        u = ce.universe(panel)
        self.assertEqual(set(u.values()), {"muni", "us_equity"})
        self.assertIn("BTT", ce.EXCLUDED)


class Screens(unittest.TestCase):
    def test_a_price_mismatch_year_fails(self):
        snap, panel, _f = world()
        bad = panel.price.copy()
        bad.loc[bad.index.year == 2008, "M1"] *= 1.03 ** np.arange((bad.index.year == 2008).sum())
        p2 = NavPanel(sha="q", price=bad, nav=panel.nav, category=panel.category, manifest={})
        out = ce.screens(p2, snap, ["M1", "M2"])
        self.assertIn(["M1", 2008, "price mismatch vs panel"], out["failed"])
        self.assertFalse(any(f == "M2" for f, _y, _r in out["failed"]))


class Rule(unittest.TestCase):
    def setUp(self):
        self.snap, self.panel, _f = world()
        self.inputs = inputs_for(self.snap, self.panel)

    def test_slots_are_equal_per_family_then_per_fund(self):
        sh = ce.slots(self.inputs, self.snap)
        row = sh.loc[pd.Timestamp(self.inputs.data["window_start"]) + pd.Timedelta(days=30):].iloc[0]
        self.assertAlmostEqual(row.sum(), 1.0)
        self.assertAlmostEqual(row[[c for c in row.index if c.startswith("M")]].sum(), 0.5)

    def test_corporate_action_window_reads_neutral(self):
        filed = str(self.snap.dates[1500].date())
        inp = inputs_for(self.snap, self.panel, corporate_actions={"M0": [["N-14", filed]]})
        st = ce.fund_states(inp, self.snap, "M0")
        after = st.loc[pd.Timestamp(filed) + pd.Timedelta(days=3): pd.Timestamp(filed) + pd.Timedelta(days=300)]
        self.assertTrue((after == 0.5).all())
        self.assertFalse((ce.fund_states(self.inputs, self.snap, "M0") == 0.5).all())

    def test_a_corporate_action_window_near_a_cut_reads_no_future(self):
        filed = str(self.snap.dates[1500].date())
        inp = inputs_for(self.snap, self.panel, corporate_actions={"M0": [["SC TO-I", filed]]})
        cut = self.snap.dates[1500 + 200]                       # inside the 52-week window
        self.assertEqual(ce.truncation_violations(self.snap, inp, ce.grid()[0], [cut]), [])

    def test_benchmark_holds_every_slot_at_half_and_no_lookahead(self):
        wb = ce.weights(self.inputs, self.snap, "bench")
        m0 = self.inputs.matched["M0"]["etf"]
        self.assertTrue(np.allclose(wb["M0"], wb[[f"M{k}" for k in range(6)]].mean(axis=1)))
        in_window = wb.loc[pd.Timestamp(self.inputs.data["window_start"]):]
        self.assertTrue((in_window[m0] > 0).all())
        cut = self.snap.dates[1800]
        self.assertEqual(ce.truncation_violations(self.snap, self.inputs, ce.grid()[0], [cut]), [])
        self.assertEqual(ce.truncation_violations(self.snap, self.inputs, ce.lag_grid()[0], [cut]), [])


class Costs(unittest.TestCase):
    def test_protocol_tiers_exist_and_map(self):
        from src.research.daily_strategy import COST_BPS
        snap, panel, _f = world()
        inp = inputs_for(snap, panel, tiers={"M0": {"tier": "cef_thin"}, "E0": {"tier": "cef"}})
        t = ce.tiers(inp)
        self.assertEqual((t["M0"], t["E0"], t["MUB"], t["SPY"]), ("cef_thin", "cef_plus", "tier1_plus", "tier1_plus"))
        self.assertEqual((COST_BPS["cef_plus"]["post"], COST_BPS["cef_thin"]["post"], COST_BPS["tier1_plus"]["post"]),
                         (17.0, 42.0, 4.0))


class Decomposition(unittest.TestCase):
    def test_within_plus_category_equals_the_fund_active_sum(self):
        import cef_etf_report as rep
        from src.research.daily_strategy import evaluate_daily
        from src.strategy.counted import uncounted
        snap, panel, _f = world()
        inp = inputs_for(snap, panel)
        start = pd.Timestamp(inp.data["window_start"])
        with uncounted("unit test of the decomposition identity on a synthetic panel"):
            t = evaluate_daily(ce.decide(snap, inp, ce.grid()[0]), snap, start=start)
            b = evaluate_daily(ce.decide(snap, inp, ce.REFERENCE), snap, start=start)
        dec = rep.decompose(inp, snap, t, b)
        total = (dec["dw"] * dec["x"]).sum(axis=1)
        np.testing.assert_allclose((dec["within"] + dec["cat"]).to_numpy(), total.to_numpy(), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
