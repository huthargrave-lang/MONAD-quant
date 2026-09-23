"""
Tests for the admission gate (tools/admit.py).

The engine is replaced with a deterministic fake backtest (patched at
``src.backtest.runner.run_backtest``) so the gate's DECISION logic can be exercised on
evidence of known strength. The one property this file exists for:

    identical evidence + a different search history => a different verdict.

A strong candidate registered with no prior search is admitted; the same candidate
after a large recorded search is rejected by deflation. Everything else pins each
stage's outcome, that the gate's own backtests are counted, and that verdict records
are immutable.
"""
import datetime as dt
import subprocess
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

import admit  # noqa: E402
from src.research import prereg, refutations, trials  # noqa: E402

REGISTERED = "2021-07-02T00:00:00Z"
#: A real commit, so a verdict's code sha passes the ancestry check; the tree is reported
#: clean regardless of the developer's working copy, so the tests are deterministic.
HEAD_SHA = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
CLEAN = {"sha": HEAD_SHA, "dirty": False, "diff_sha256": None, "error": None}
MATURE = dt.datetime(2022, 2, 1, tzinfo=dt.timezone.utc)   # > 180 days after REGISTERED
from src.research.backtest_trials import mr_hourly_family  # noqa: E402
from src.backtest.runner import engine_settings  # noqa: E402

FAMILY = mr_hourly_family("SYN")
#: What a real hourly engine trial on SYN records (engine identity is version-bound).
ENGINE = engine_settings("SYN_HOURLY", "hourly")
PARAMS = {"target_gain_pct": 0.01, "stop_loss_pct": 0.005, "rsi_oversold": 35,
          "vwap_zscore_thresh": -1.0, "max_trade_bars": 8}


def _spec(**changes):
    s = {"hypothesis": "H9100", "family": FAMILY,
         "claim": "Synthetic tape: the frozen dip-buying candidate earns after costs.",
         "profile": "price_strategy", "universe": ["SYN"],
         "development_window": {"start": "2021-01-04", "end": "2021-07-01"},
         "metric": "deflated_sharpe", "threshold": 0.95, "min_trades": 30,
         "holdout": {"kind": "forward_paper", "min_days": 180, "min_trades": 30, "min_psr": 0.9},
         "cost_model": {"round_trip_cost_pct": "instrument-derived"}, "params": dict(PARAMS)}
    s.update(changes)
    return s


def flat_bars(symbol, start, end):
    """A flat, gently noisy tape: buy & hold earns ~nothing, so the benchmark is fair."""
    idx = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="h", tz="UTC")
    rng = np.random.default_rng(len(idx))
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.0005, len(idx))) * 0.1)
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close, "volume": 1e6}, index=idx)


def fake_backtest(edge):
    """A stand-in for run_backtest: one trade every 7 bars, mean ``edge`` per trade,
    minus the slippage it is given. Deterministic in the bars it sees."""
    def run(df, target_gain_pct, stop_loss_pct, slippage_pct=0.0, **_):
        idx = df.index[::7]
        rng = np.random.default_rng(len(df))
        r = pd.Series(rng.normal(edge, 0.004, len(idx)) - (slippage_pct or 0.0), index=idx)
        equity = (1 + 0.1 * r).cumprod()
        dd = float((equity / equity.cummax() - 1).min())
        return {"total_trades": len(r), "win_rate": float((r > 0).mean()),
                "total_return": float(equity.iloc[-1] - 1), "sharpe_ratio": float(r.mean() / r.std()),
                "max_drawdown": dd, "trades_per_year": 300.0, "trade_returns": r}
    return run


class Gate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = Path(self._tmp.name)
        self.dirs = {"prereg_dir": d / "prereg", "refutations_dir": d / "refutations"}
        self.ledger = d / "trials"
        # The gate has no ledger parameter by design, so the test relocates the canonical
        # one (and the registrations open_run's family check reads).
        self._orig = (prereg.PREREG_DIR, trials.LEDGER_DIR)
        prereg.PREREG_DIR = self.dirs["prereg_dir"]
        trials.LEDGER_DIR = self.ledger
        self._code = mock.patch("src.research.trials.code_state", return_value=dict(CLEAN))
        self._code.start()

    def tearDown(self):
        self._code.stop()
        prereg.PREREG_DIR, trials.LEDGER_DIR = self._orig
        self._tmp.cleanup()

    def register(self, **changes):
        prereg.register(_spec(**changes), prereg_dir=self.dirs["prereg_dir"], check_web=False,
                        now=REGISTERED)

    def evaluate(self, edge=0.004, now=MATURE, parity_diverge=(), dirty=False,
                 load_bars=flat_bars, witness_problems=(), hypothesis="H9100"):
        census = {"rows": [{"dimension": d, "verdict": "DIVERGE"} for d in parity_diverge],
                  "counts": {"DIVERGE": len(parity_diverge)}}
        self.witnessed = None

        def witness(spec, prereg_path, runs):
            self.witnessed = (prereg_path, list(runs))
            return list(witness_problems)
        with mock.patch("src.backtest.runner.run_backtest", fake_backtest(edge)):
            return admit.evaluate(hypothesis, now=now, load_bars=load_bars,
                                  parity=lambda: census,
                                  code=lambda: {**CLEAN, "dirty": dirty},
                                  witness=witness, deploy_sha=lambda: HEAD_SHA, **self.dirs)

    def examined(self, hypothesis="H9100"):
        """A refuter objected and a different author refuted it: the refutation stage's
        pass condition (no objections at all now BLOCKS)."""
        o = refutations.object_to(hypothesis, claim="the candidate may be a sampling artifact",
                                  evidence="compare bars/day in the data fingerprint",
                                  by="refuter-1", directory=self.dirs["refutations_dir"])
        refutations.resolve(hypothesis, o["id"], outcome="refuted",
                            evidence="fingerprint shows 7 bars/day, full session",
                            by="author-1", directory=self.dirs["refutations_dir"])

    def stages(self, record):
        return {s["name"]: s["outcome"] for s in record["stages"]}

    def prior_search(self, n, seed=0):
        """n recorded trials in the family BEFORE registration, with widely spread Sharpes:
        the signature of a search wide enough that its best result is expected to look
        strong by luck alone."""
        rng = np.random.default_rng(seed)
        with mock.patch("src.research.trials._now", return_value="2021-06-01T00:00:00.000000Z"):
            with trials.open_run(producer="sweep.py", family=FAMILY) as run:
                for i in range(n):
                    idx = pd.bdate_range("2021-01-04", periods=120) + pd.Timedelta(hours=10)
                    s = pd.Series(rng.normal(rng.normal(0, 0.02), 0.01, 120), index=idx)
                    run.begin(params={"i": i}).complete(metrics={}, returns=s)


class TheVerdictDependsOnTheSearch(Gate):
    def test_a_strong_candidate_with_no_prior_search_is_admitted(self):
        self.register()
        self.examined()
        record = self.evaluate()
        self.assertEqual(record["verdict"], admit.ADMIT, record["stages"])
        self.assertEqual(set(self.stages(record).values()), {admit.PASS})

    def test_the_same_candidate_after_a_large_search_is_rejected(self):
        self.prior_search(300)
        self.register()
        self.examined()
        record = self.evaluate()
        self.assertEqual(self.stages(record)["deflation"], admit.FAIL)
        self.assertEqual(record["verdict"], admit.REJECT)

    def test_the_gates_own_backtests_are_counted_but_not_as_search(self):
        self.register()
        record = self.evaluate()
        counted = [r for r in trials.iter_trials()
                   if r.producer == "tools/admit.py"]
        self.assertEqual(len(counted), 3)  # development, cost stress, forward
        deflation_stage = next(s for s in record["stages"] if s["name"] == "deflation")
        self.assertEqual(deflation_stage["data"]["trials_recorded"], 1)


class EachStage(Gate):
    def test_no_registration_rejects(self):
        self.assertEqual(self.evaluate()["verdict"], admit.REJECT)

    def test_no_frozen_candidate_rejects(self):
        self.register(params=None)
        self.assertEqual(self.evaluate()["verdict"], admit.REJECT)

    def test_a_private_family_is_refused(self):
        self.register(family="my_fresh_start:SYN")
        rec = self.evaluate()
        self.assertEqual(rec["verdict"], admit.UNSUPPORTED)  # not the MR family at all
        self.register(hypothesis="H9101", family=mr_hourly_family("OTHER"))
        with mock.patch("src.backtest.runner.run_backtest", fake_backtest(0.004)):
            rec = admit.evaluate("H9101", now=MATURE, load_bars=flat_bars,
                                 parity=lambda: {"rows": [], "counts": {}},
                                 code=lambda: dict(CLEAN), witness=lambda *a: [], **self.dirs)
        self.assertEqual(rec["verdict"], admit.REJECT)
        self.assertIn("family must be", rec["stages"][0]["detail"])

    def test_other_profiles_are_unsupported_not_admitted(self):
        self.register(profile="event_study", holdout={"kind": "sealed_issuers", "vault": "v1"})
        self.assertEqual(self.evaluate()["verdict"], admit.UNSUPPORTED)

    def test_dirty_code_blocks(self):
        self.register()
        rec = self.evaluate(dirty=True)
        self.assertEqual(self.stages(rec)["code"], admit.BLOCK)
        self.assertEqual(rec["verdict"], admit.BLOCKED)

    def test_parity_divergence_blocks(self):
        self.register()
        rec = self.evaluate(parity_diverge=("max hold (time exit)",))
        self.assertEqual(self.stages(rec)["parity"], admit.BLOCK)
        self.assertIn("max hold", next(s for s in rec["stages"] if s["name"] == "parity")["detail"])

    def test_open_objection_blocks_and_upheld_rejects(self):
        self.register()
        o = refutations.object_to("H9100", claim="entries use the bar's own close (look-ahead)",
                                  evidence="engine.py:390 timestamp is the signal bar",
                                  by="refuter-1", directory=self.dirs["refutations_dir"])
        self.assertEqual(self.stages(self.evaluate())["refutations"], admit.BLOCK)
        refutations.resolve("H9100", o["id"], outcome="upheld",
                            evidence="confirmed by replay in tools/overnight_gap_risk_study.py",
                            by="refuter-2", directory=self.dirs["refutations_dir"])
        self.assertEqual(self.evaluate()["verdict"], admit.REJECT)

    def test_a_losing_candidate_fails_cost_and_benchmark(self):
        self.register()
        st = self.stages(self.evaluate(edge=-0.002))
        self.assertEqual((st["cost_stress"], st["benchmark"]), (admit.FAIL, admit.FAIL))

    def test_forward_is_pending_until_it_matures(self):
        self.register()
        self.examined()
        early = dt.datetime(2021, 7, 20, tzinfo=dt.timezone.utc)
        rec = self.evaluate(now=early)
        self.assertEqual(self.stages(rec)["forward"], admit.PENDING)
        self.assertEqual(rec["verdict"], admit.PENDING_V)
        counted = [r for r in trials.iter_trials() if r.producer == "tools/admit.py"]
        self.assertEqual(len(counted), 2)  # no forward backtest before the window matures

    def test_a_gate_that_cannot_measure_does_not_admit(self):
        self.register()

        def broken(*_):
            raise ConnectionError("no network")
        rec = self.evaluate(load_bars=broken)
        self.assertNotEqual(rec["verdict"], admit.ADMIT)

    def test_no_objection_at_all_blocks(self):
        self.register()
        rec = self.evaluate()
        self.assertEqual(self.stages(rec)["refutations"], admit.BLOCK)
        self.assertIn("no objection has been filed", next(
            s for s in rec["stages"] if s["name"] == "refutations")["detail"])

    def test_evidence_not_on_the_deploy_branch_blocks(self):
        self.prior_search(3)
        self.register()
        self.examined()
        rec = self.evaluate(witness_problems=["docs/research/prereg/H9100.json is not on origin/development"])
        self.assertEqual(self.stages(rec)["witness"], admit.BLOCK)
        self.assertEqual(rec["verdict"], admit.BLOCKED)
        prereg_path, runs = self.witnessed
        self.assertEqual(Path(prereg_path).name, "H9100.json")
        self.assertEqual(len(runs), 1)  # the one pre-registration search run is witnessed

    def test_thin_development_evidence_fails_deflation(self):
        self.register(development_window={"start": "2021-06-20", "end": "2021-07-01"})
        self.examined()
        st = next(s for s in self.evaluate()["stages"] if s["name"] == "deflation")
        self.assertEqual(st["outcome"], admit.FAIL)
        self.assertIn("daily observations", st["detail"])


class RedTeamAttacks(Gate):
    """Each test is an attack the harness red-team subagent landed; each must now fail."""

    def test_7a_backdating_registration_cannot_reuse_seen_bars_as_forward(self):
        self.register()                      # claims registration on 2021-07-02
        self.examined()
        # ...but a family trial had already seen bars up to mid-November.
        with trials.open_run(producer="sweep.py", family=FAMILY) as run:
            peek = flat_bars("SYN", "2021-07-02", "2021-11-15")
            peek.index = peek.index.tz_localize(None)
            run.begin(params={"timeframe": "hourly", "mode": "SYN_HOURLY", "engine": ENGINE},
                      data={"ticker": "SYN", "fingerprint": {"last_bar": str(peek.index[-1])}}
                      ).complete(metrics={})
        rec = self.evaluate()                # 2022-02-01: 214 days after the claimed date
        fwd = next(s for s in rec["stages"] if s["name"] == "forward")
        self.assertEqual(fwd["outcome"], admit.PENDING)
        self.assertIn("starts 2021-11-15", fwd["detail"])

    def test_4a_a_search_under_a_scratch_label_still_counts(self):
        with mock.patch("src.research.trials._now", return_value="2021-06-01T00:00:00.000000Z"):
            with trials.open_run(producer="sweep.py", family="scratch_peek:SYN") as run:
                for i in range(5):
                    run.begin(params={"timeframe": "hourly", "mode": "SYN_HOURLY", "engine": ENGINE, "i": i},
                              data={"ticker": "SYN"}).complete(metrics={})
        self.register()
        self.examined()
        st = next(s for s in self.evaluate()["stages"] if s["name"] == "deflation")
        self.assertEqual(st["data"]["trials_recorded"], 6)  # 5 scratch-labelled + candidate

    def test_7a_prime_a_backdated_registration_cannot_drop_the_search_from_n(self):
        """Round 2: search AFTER the date the registration claims; the search still counts."""
        self.register()                                   # claims 2021-07-02
        self.examined()
        with mock.patch("src.research.trials._now", return_value="2021-09-01T00:00:00.000000Z"):
            with trials.open_run(producer="sweep.py", family=FAMILY) as run:
                for i in range(4):
                    run.begin(params={"i": i}).complete(metrics={})
        st = next(s for s in self.evaluate()["stages"] if s["name"] == "deflation")
        self.assertEqual(st["data"]["trials_recorded"], 5)  # 4 searched + candidate

    def test_7b_prime2_an_empty_self_written_gate_run_does_not_verify(self):
        """Round 2: a shard written with producer="tools/admit.py" and the right spec hash,
        but containing none of the trials the stages cite."""
        self.register()
        h = prereg.load("H9100", prereg_dir=self.dirs["prereg_dir"])[1]
        with trials.open_run(producer="tools/admit.py", family=FAMILY, hypothesis="H9100",
                             context={"spec_hash": h}) as run:
            pass
        forged = {"hypothesis": "H9100", "evaluated_at": "2021-12-01T00:00:00Z", "verdict": "ADMIT",
                  "spec_hash": h, "ledger_run": run.run_id, "code": dict(CLEAN),
                  "stages": [{"name": n, "outcome": "pass", "detail": "",
                              "data": {"trial": f"{run.run_id}#0"}} for n in admit.ADMIT_CHAIN]}
        problems = admit.verify_record(forged, prereg_dir=self.dirs["prereg_dir"])
        self.assertTrue(any("not in run" in p for p in problems), problems)

    def test_7b_a_hand_written_admit_does_not_verify(self):
        self.register()
        forged = {"hypothesis": "H9100", "evaluated_at": "2021-12-01T00:00:00Z", "verdict": "ADMIT",
                  "spec_hash": prereg.load("H9100", prereg_dir=self.dirs["prereg_dir"])[1],
                  "stages": [{"name": n, "outcome": "pass", "detail": "", "data": {}}
                             for n in admit.ADMIT_CHAIN]}
        problems = admit.verify_record(forged, prereg_dir=self.dirs["prereg_dir"])
        self.assertTrue(any("ledger run" in p for p in problems), problems)

    def test_a_genuine_admit_verifies_and_a_tampered_one_does_not(self):
        self.register()
        self.examined()
        rec = self.evaluate()
        self.assertEqual(rec["verdict"], admit.ADMIT)
        self.assertEqual(rec["witnessed_sha"], HEAD_SHA)
        # HEAD stands in for the deploy branch: the witnessed commit is in its history.
        ok = admit.verify_record(rec, prereg_dir=self.dirs["prereg_dir"], deploy_ref="HEAD")
        self.assertEqual(ok, [])
        tampered = {**rec, "stages": rec["stages"][:-1]}
        self.assertTrue(admit.verify_record(tampered, prereg_dir=self.dirs["prereg_dir"],
                                            deploy_ref="HEAD"))

    def test_q5_a_rewritten_deploy_branch_invalidates_the_admit(self):
        """The witnessed commit is not in the branch's history any more (simulated by a
        ref that never contained it): the ADMIT stops verifying instead of passing."""
        self.register()
        self.examined()
        rec = self.evaluate()
        problems = admit.verify_record({**rec, "witnessed_sha": "f" * 40},
                                       prereg_dir=self.dirs["prereg_dir"], deploy_ref="HEAD")
        self.assertTrue(any("rewritten" in p for p in problems), problems)
        missing = admit.verify_record({k: v for k, v in rec.items() if k != "witnessed_sha"},
                                      prereg_dir=self.dirs["prereg_dir"], deploy_ref="HEAD")
        self.assertTrue(any("witnessed" in p for p in missing), missing)

    def test_6_an_objection_cannot_be_answered_by_its_author(self):
        o = refutations.object_to("H9100", claim="entries fill on the signal bar",
                                  evidence="engine.py:390", by="Refuter-1",
                                  directory=self.dirs["refutations_dir"])
        with self.assertRaises(refutations.RefutationError):
            refutations.resolve("H9100", o["id"], outcome="refuted", evidence="no it does not, see x",
                                by="refuter-1", directory=self.dirs["refutations_dir"])

    def test_verdict_order(self):
        S = admit.Stage
        self.assertEqual(admit._verdict([S("a", "pass", ""), S("b", "pending", "")]), admit.PENDING_V)
        self.assertEqual(admit._verdict([S("a", "pending", ""), S("b", "block", "")]), admit.BLOCKED)
        self.assertEqual(admit._verdict([S("a", "block", ""), S("b", "fail", "")]), admit.REJECT)


class TheForwardFloorsPower(unittest.TestCase):
    """Decision-debate Q3: the forward floor's pass rates, measured through the gate's own
    forward statistic (admit.forward_psr), not recomputed from the formula that motivated
    it. One trade per business day over ~125 trading days (the 180-day floor), at the
    0.90 floor. Measured when written (K=300, seed 0): noise 0.12, S=1 0.28, S=2 0.56,
    S=3 0.80, matching normal theory (0.10 / 0.28 / 0.55 / 0.80)."""

    @staticmethod
    def pass_rate(annual_sharpe, k=300, days=125, seed=0):
        rng = np.random.default_rng(seed)
        idx = pd.bdate_range("2022-01-03", periods=days) + pd.Timedelta(hours=15)
        hits = 0
        for _ in range(k):
            r = pd.Series(rng.normal(annual_sharpe / np.sqrt(252) * 0.01, 0.01, days), index=idx)
            hits += admit.forward_psr(r) >= prereg.MIN_FORWARD_PSR_FLOOR
        return hits / k

    def test_noise_rarely_passes(self):
        self.assertLessEqual(self.pass_rate(0.0), 0.16)

    def test_a_strong_edge_usually_passes(self):
        self.assertGreaterEqual(self.pass_rate(3.0), 0.70)

    def test_a_moderate_edge_is_a_coin_flip(self):
        self.assertTrue(0.45 <= self.pass_rate(2.0) <= 0.67)


class Records(unittest.TestCase):
    def test_written_once(self):
        with tempfile.TemporaryDirectory() as td:
            rec = {"hypothesis": "H9100", "evaluated_at": "2021-12-01T00:00:00Z", "verdict": "ADMIT",
                   "stages": []}
            path = admit.write_verdict(rec, Path(td))
            self.assertTrue(path.exists())
            with self.assertRaises(FileExistsError):
                admit.write_verdict(rec, Path(td))

    def test_history_is_immutable(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            git = lambda *a: subprocess.run(["git", "-C", td, *a], check=True, capture_output=True)
            git("init", "-q", "-b", "base")
            git("config", "user.email", "t@e.com")
            git("config", "user.name", "t")
            path = admit.write_verdict({"hypothesis": "H1", "evaluated_at": "2021-12-01T00:00:00Z",
                                        "verdict": "REJECT", "stages": []}, repo / admit.VERDICT_REL)
            git("add", "-A")
            git("commit", "-q", "-m", "v")
            git("checkout", "-q", "-b", "work")
            self.assertEqual(admit.verify_history("base", repo=repo), [])
            path.write_text(path.read_text().replace("REJECT", "ADMIT"))
            self.assertTrue(admit.verify_history("base", repo=repo))


if __name__ == "__main__":
    unittest.main()
