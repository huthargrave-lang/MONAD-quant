"""
The tactical_allocation admission chain (tools/admit_tactical.py), end to end on a
synthetic market and a temporary ledger: it reproduces the recorded search trial, refuses
a candidate the search never ran, catches a recorded trial that does not replay, runs
every stage, and leaves the forward window pending until it matures.
"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import admit_tactical  # noqa: E402

from src.research import daily_classes as dc  # noqa: E402
from src.research import prereg, refutations, trials  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402
from src.research.daily_domains import ETF, Context  # noqa: E402
from src.research.daily_strategy import evaluate_daily  # noqa: E402
from src.research.daily_trials import (DAILY_FAMILY, REFERENCE_FAMILY, daily_spec,  # noqa: E402
                                       record_daily)

ASSETS = sorted({a for g in dc.GRIDS.values() for p in g() for a in dc.assets_used(p)} | {"SPY", "IEF"})
CANDIDATE = {"class": "sma", "params": {"sma_sessions": 200, "off": "cash"}}
OTHERS = [{"class": "dualmom", "params": {"lookback_months": 6, "safe": "IEF"}},
          {"class": "tom", "params": {"first": -1, "last": 3, "off": "cash"}}]
SHA = "a" * 64


def market(n=3300, seed=11):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2006-01-02", periods=n)
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.009, (n, len(ASSETS))), axis=0)),
                         index=dates, columns=ASSETS)
    opens = close.shift(1).fillna(close.iloc[0]) * np.exp(rng.normal(0, 0.002, (n, len(ASSETS))))
    return Snapshot(sha=SHA, dates=dates, assets=tuple(ASSETS), open=opens, close=close,
                    dist=pd.DataFrame(0.0, index=dates, columns=ASSETS),
                    dtb3=pd.Series(1.0, index=dates), manifest={})


class TacticalGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = market()
        cls.ctx = Context(snap=cls.snap)
        cls.start, cls.end = ETF.window(cls.ctx)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ledger, self.prereg_dir, self.ref_dir = root / "ledger", root / "prereg", root / "ref"
        self.patch = mock.patch.object(trials, "LEDGER_DIR", self.ledger)
        self.patch.start()
        self.search(CANDIDATE, *OTHERS)

    def tearDown(self):
        self.patch.stop()
        self._tmp.cleanup()

    def search(self, *points, tamper=False):
        data = self.ctx.data_spec(self.start, self.end)
        with trials.open_run(producer="tools/daily_search.py", family=REFERENCE_FAMILY) as run:
            t = run.begin(params=daily_spec(dc.REFERENCE), data=data)
            record_daily(t, evaluate_daily(dc.decide(self.snap, dc.REFERENCE), self.snap,
                                           start=self.start, end=self.end))
        with trials.open_run(producer="tools/daily_search.py", family=DAILY_FAMILY) as run:
            for p in points:
                t = run.begin(params=daily_spec(p), data=data)
                r = evaluate_daily(dc.decide(self.snap, p), self.snap, start=self.start, end=self.end)
                if tamper:
                    r.returns = r.returns + 1e-4
                record_daily(t, r)

    def register(self, candidate=CANDIDATE, min_days=180):
        spec = {"hypothesis": "H9", "family": DAILY_FAMILY, "profile": "tactical_allocation",
                "claim": "a trend filter beats the static 60/40 after the search",
                "universe": ["SPY", "IEF"],
                "development_window": {"start": str(self.start.date()), "end": str(self.end.date())},
                "metric": "active_deflated_sharpe", "threshold": 0.95, "min_trades": 30,
                "holdout": {"kind": "forward_paper", "min_days": min_days, "min_trades": 1,
                            "min_psr": 0.9},
                "cost_model": {"tiers": "daily_strategy.COST_BPS"},
                "params": {"domain": "etf_alloc", "candidate": candidate, "data": {"snapshot": SHA},
                           "eras": [["start", "2012-12-31"], ["2013-01-01", "end"]],
                           "min_years": 10, "familywise_alpha": 0.05, "prior_search_trials": 3}}
        prereg.register(spec, prereg_dir=self.prereg_dir, check_web=False,
                        now=(self.end + pd.Timedelta(days=1)).isoformat() + "Z")
        refutations.object_to("H9", claim="the window is too short to judge", evidence="tests: a synthetic market of twelve years",
                              by="refuter", directory=self.ref_dir)
        refutations.resolve("H9", "O1", outcome="refuted", evidence="ten years cover it",
                            by="board", directory=self.ref_dir)

    def run_gate(self, now):
        """The chain as admit.evaluate dispatches it, with the frozen data injected and the
        forward fetch forbidden (it must not run before the window matures)."""
        spec, spec_hash = prereg.load("H9", prereg_dir=self.prereg_dir)

        def no_forward(*a):
            raise AssertionError("forward data must not be fetched before the window matures")

        return admit_tactical.evaluate(
            "H9", spec, spec_hash, {"schema": 1, "hypothesis": "H9", "evaluated_at": "now",
                                     "profile": spec["profile"]},
            now=now, code=lambda: {"sha": "f" * 40, "dirty": False}, witness=lambda *a: [],
            deploy_sha=lambda: "e" * 40, prereg_dir=self.prereg_dir, refutations_dir=self.ref_dir,
            load_context=lambda data: self.ctx, load_forward=no_forward)

    def test_every_stage_runs_and_the_forward_window_waits(self):
        self.register()
        now = dt.datetime.combine(self.end.date() + dt.timedelta(days=30), dt.time(), dt.timezone.utc)
        rec = self.run_gate(now)
        names = [s["name"] for s in rec["stages"]]
        self.assertEqual(tuple(names), admit_tactical.ADMIT_CHAIN)
        by = {s["name"]: s for s in rec["stages"]}
        self.assertEqual(by["development"]["outcome"], "pass", by["development"]["detail"])
        self.assertIn("reproduces", by["development"]["detail"])
        self.assertEqual(by["lookahead"]["outcome"], "pass")
        self.assertEqual(by["forward"]["outcome"], "pending")
        self.assertIn(by["familywise"]["outcome"], ("pass", "fail"))
        self.assertIn(rec["verdict"], ("PENDING", "REJECT"))
        # The gate's own trials are counted, in the candidate's and the benchmark's families.
        gate = [r for r in trials.iter_trials() if r.producer == "tools/admit.py"]
        self.assertEqual(sorted({r.family for r in gate}), sorted({DAILY_FAMILY, REFERENCE_FAMILY}))

    def test_a_candidate_outside_the_frozen_grid_is_rejected(self):
        self.register(candidate={"class": "sma", "params": {"sma_sessions": 150, "off": "cash"}})
        now = dt.datetime.combine(self.end.date() + dt.timedelta(days=30), dt.time(), dt.timezone.utc)
        rec = self.run_gate(now)
        self.assertEqual(rec["verdict"], "REJECT")
        self.assertEqual(rec["stages"][0]["name"], "registration")

    def test_a_recorded_trial_that_does_not_replay_fails_development(self):
        self.patch.stop()
        self._tmp.cleanup()
        self.setUp_tampered()
        self.register()
        now = dt.datetime.combine(self.end.date() + dt.timedelta(days=30), dt.time(), dt.timezone.utc)
        rec = self.run_gate(now)
        by = {s["name"]: s for s in rec["stages"]}
        self.assertEqual(by["development"]["outcome"], "fail")
        self.assertIn("does not reproduce", by["development"]["detail"])

    def setUp_tampered(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ledger, self.prereg_dir, self.ref_dir = root / "ledger", root / "prereg", root / "ref"
        self.patch = mock.patch.object(trials, "LEDGER_DIR", self.ledger)
        self.patch.start()
        self.search(CANDIDATE, *OTHERS, tamper=True)

    def test_the_overlap_check_refuses_forward_data_from_another_market(self):
        other = market(seed=99)
        self.assertTrue(admit_tactical.overlap_problems(self.ctx, Context(snap=other)))
        self.assertEqual(admit_tactical.overlap_problems(self.ctx, self.ctx), [])


if __name__ == "__main__":
    unittest.main()
