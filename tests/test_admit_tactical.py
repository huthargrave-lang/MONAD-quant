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
from tests._v1_registration import register_v1  # noqa: E402
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
        # The ledger checks a hypothesis-linked run against the CANONICAL registration
        # folder; point it here so the gate's runs are checked as they are in production.
        self.prereg_patch = mock.patch.object(prereg, "PREREG_DIR", self.prereg_dir)
        self.prereg_patch.start()
        self.search(CANDIDATE, *OTHERS)

    def tearDown(self):
        self.patch.stop()
        self.prereg_patch.stop()
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

    def register(self, candidate=CANDIDATE, min_days=180, rules=1):
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
        at = (self.end + pd.Timedelta(days=1)).isoformat() + "Z"
        if rules == 2:
            spec = {**spec, "metric": "familywise_spa", "gate_rules": 2}
            prereg.register(spec, prereg_dir=self.prereg_dir, check_web=False, now=at)
        else:
            register_v1(self, spec, prereg_dir=self.prereg_dir, check_web=False, now=at)
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
        self.prereg_patch.stop()
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
        self.prereg_patch = mock.patch.object(prereg, "PREREG_DIR", self.prereg_dir)
        self.prereg_patch.start()
        self.search(CANDIDATE, *OTHERS, tamper=True)

    def gate_v2(self):
        self.register(rules=2)
        now = dt.datetime.combine(self.end.date() + dt.timedelta(days=30), dt.time(), dt.timezone.utc)
        rec = self.run_gate(now)
        path = trials.LEDGER_DIR / f"{rec['ledger_run']}.jsonl"
        head = json.loads(path.read_bytes().split(b"\n", 1)[0])
        spec, _ = prereg.load("H9", prereg_dir=self.prereg_dir)
        return rec, head, spec

    def test_gate_rules_v2_skips_the_dsr_and_gates_on_the_charged_familywise_spa(self):
        rec, _, _ = self.gate_v2()
        self.assertEqual(rec["gate_rules"], 2)
        self.assertEqual(tuple(s["name"] for s in rec["stages"]), admit_tactical.ADMIT_CHAIN_V2)
        by = {s["name"]: s for s in rec["stages"]}
        self.assertEqual(by["deflation_diagnostic"]["outcome"], "skip")
        self.assertIn("dsr", by["deflation_diagnostic"]["data"])
        fw = by["familywise"]["data"]
        # three declared prior trials; every searched point is in the matrix
        self.assertEqual(fw["m_parts"], {"prior_search_trials": 3, "unknown_specs": 0,
                                         "off_window_points": 0})
        self.assertEqual(fw["m"], 3)
        self.assertAlmostEqual(fw["p_gate"], min(1.0, fw["worst_p"] * 4), places=12)
        self.assertEqual(by["familywise"]["outcome"], "pass" if fw["p_gate"] <= 0.05 else "fail")

    def test_the_v2_verifier_recomputes_the_familywise_gate_from_the_ledger(self):
        rec, head, spec = self.gate_v2()
        load = lambda data: self.ctx  # noqa: E731
        fw = next(s for s in rec["stages"] if s["name"] == "familywise")
        clears = fw["data"]["p_gate"] <= 0.05
        problems = admit_tactical._verify_familywise(rec, head, spec, trials.iter_trials(), load_context=load)
        self.assertEqual(bool(problems), not clears, problems)
        # A search after the gate ran is not what the gate saw: the recomputation ignores it.
        self.search({"class": "sma", "params": {"sma_sessions": 100, "off": "cash"}})
        again = admit_tactical._verify_familywise(rec, head, spec, trials.iter_trials(), load_context=load)
        self.assertEqual(again, problems)
        # A record whose p_gate was edited no longer reproduces.
        forged = json.loads(json.dumps(rec))
        for s in forged["stages"]:
            if s["name"] == "familywise":
                s["data"]["p_gate"] = 0.001
        bad = admit_tactical._verify_familywise(forged, head, spec, trials.iter_trials(), load_context=load)
        self.assertTrue(any("does not match" in p for p in bad), bad)

    def test_the_v2_switch_rests_on_a_passing_trigger_study(self):
        """Decision debate 2026-10-06, Q2 (vi): the tactical profile runs under gate rules
        v2 because the committed size study meets the trigger."""
        study = json.loads((REPO / "docs" / "research" / "spa_size_study.json").read_text())
        self.assertEqual(study["alpha"], 0.05)
        self.assertGreaterEqual(study["n_boot"], 1000)
        self.assertTrue(study["size"])
        for row in study["size"]:
            self.assertEqual(row["true_active_sharpe"], 0.0)
            self.assertGreaterEqual(row["reps"], 1000)
            self.assertLessEqual(row["wilson_upper"], study["trigger"], row)
        self.assertTrue(any(r["withheld_m"] > 0 for r in study["size"]))
        self.assertLessEqual(study["trigger"], 0.075)

    def test_the_witness_names_each_domains_own_panel_files(self):
        """A domain with a second frozen dataset declares its file prefix; the witness stage
        must check THAT file, not a CEF NAV panel of the same sha (found on H404703)."""
        from src.research.daily_domains import DOMAINS
        for name, prefix in (("cef_discount", "CEFNAV"), ("bdc_discount", "BDCNAV"),
                             ("insider_cluster", "INSIDER"), ("mreit_discount", "MREITBV"),
                             ("earnings_premium", "EARNDATES"), ("spinoff_drift", "SPINEVENTS"),
                             ("index_deletion", "IDXDEL")):
            files = admit_tactical._data_files({"snapshot": "s" * 64, "nav_panel": "p" * 64}, DOMAINS[name])
            self.assertTrue(any(f.endswith(f"{prefix}-{'p' * 64}.csv.gz") for f in files), (name, files))
        for name in ("etf_alloc", "credit_sleeve", "cef_product"):
            self.assertEqual(len(admit_tactical._data_files({"snapshot": "s" * 64}, DOMAINS[name])), 2)

    def test_the_overlap_check_refuses_forward_data_from_another_market(self):
        other = market(seed=99)
        self.assertTrue(admit_tactical.overlap_problems(self.ctx, Context(snap=other)))
        self.assertEqual(admit_tactical.overlap_problems(self.ctx, self.ctx), [])


if __name__ == "__main__":
    unittest.main()
