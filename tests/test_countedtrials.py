"""
Tests for ``packages/countedtrials``: the trial ledger and its significance kernel,
extracted from this repository as a standalone, installable package.

Three things are pinned here.

1. NO DRIFT. The package's ``significance.py`` is byte-identical to
   ``src/research/significance.py``, and its ledger writes and reads the SAME on-disk
   format as ``src/research/trials.py`` (each side verifies the other's shards, and the
   package reads this repository's committed ledger to the same counts). A fix made on
   one side and not the other fails here.
2. THE LEDGER'S PROPERTIES SURVIVE THE PORT: intent before result, tamper evidence,
   crash orphans counted, append-only history, and the runtime refusal to evaluate
   uncounted.
3. THE VERDICT IS CALIBRATED IN THE DIRECTION THAT MATTERS: a search over noise is not
   significant, a planted edge is, and everything the test cannot see raises the bar.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "packages" / "countedtrials"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(PKG))

import countedtrials as ct  # noqa: E402
from countedtrials import analysis, cli, ledger  # noqa: E402
from src.research import trials as monad_trials  # noqa: E402

DATES = pd.bdate_range("2018-01-01", periods=1000)


def noise(seed, mean=0.0, n=1000):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mean, 0.01, n), index=DATES[:n])


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "trials"

    def tearDown(self):
        self._tmp.cleanup()

    def study(self, family="fam.test", **kw):
        return ct.Study(family, ledger_dir=self.dir, producer="test", **kw)

    def shards(self):
        return ledger.shard_paths(self.dir)


# ── 1. no drift from the repository's own implementation ─────────────────────
class TestNoDrift(unittest.TestCase):
    def test_significance_kernel_is_byte_identical(self):
        self.assertEqual(
            (PKG / "countedtrials" / "significance.py").read_bytes(),
            (REPO / "src" / "research" / "significance.py").read_bytes(),
            "packages/countedtrials/countedtrials/significance.py must be an exact copy of "
            "src/research/significance.py: `cp` the latter over the former")

    def test_kernel_reproduces_the_dsr_papers_worked_example(self):
        ppy = 250
        r = ct.significance.deflated_sharpe(2.5 / ppy ** 0.5, n_trials=100, sharpe_variance=0.5 / ppy,
                                            n_obs=1250, skew=-3.0, kurtosis=10.0)
        self.assertAlmostEqual(r.dsr, 0.9004, places=4)

    def test_format_constants_match(self):
        for name in ("SCHEMA_VERSION", "ROW_TYPES", "OUTCOME_STATUSES", "CLOSE_STATUSES", "ARTIFACTS"):
            self.assertEqual(getattr(ledger, name), getattr(monad_trials, name), name)
        self.assertEqual(ledger.genesis("TR-20260101T000000Z-00000000"),
                         monad_trials.genesis("TR-20260101T000000Z-00000000"))

    def test_canonical_encoding_matches(self):
        spec = {"params": {"b": np.float64(1.5), "a": [1, np.int64(2)], "t": pd.Timestamp("2024-01-02")},
                "data": None, "extra": {"x": True}}
        self.assertEqual(ledger.spec_hash(spec), monad_trials.spec_hash(spec))
        s = noise(1, n=20)
        self.assertEqual(ledger.canonical_returns(s), monad_trials.canonical_returns(s))


class TestInterop(Case):
    def test_a_package_shard_verifies_under_the_repository_verifier(self):
        with self.study() as st:
            st.search(lambda seed: noise(seed), {"seed": [1, 2, 3]})
            with self.assertRaises(ZeroDivisionError):
                st.evaluate(lambda seed: 1 / 0, {"seed": 9})
        (shard,) = self.shards()
        report = monad_trials.verify_shard(shard)
        self.assertEqual(report.errors, [])
        self.assertEqual((report.intents, report.outcomes), (4, {"ok": 3, "error": 1}))
        theirs = monad_trials.iter_trials(self.dir)
        ours = ledger.iter_trials(self.dir)
        self.assertEqual([(r.key, r.spec_hash, r.status, r.returns_sha) for r in theirs],
                         [(r.key, r.spec_hash, r.status, r.returns_sha) for r in ours])
        a, b = monad_trials.load_returns(theirs, self.dir), ledger.load_returns(ours, self.dir)
        self.assertEqual(sorted(a), sorted(b))
        for k in a:
            pd.testing.assert_series_equal(a[k], b[k])

    def test_a_repository_shard_verifies_under_the_package(self):
        with monad_trials.open_run(producer="test", family="fam.test", ledger_dir=self.dir) as run:
            with run.trial({"x": 1}) as t:
                t.complete({"sharpe": float("nan")}, returns=noise(1, n=30),
                           series={"mtm_pnl": noise(2, n=30)})
            run.begin({"x": 2})   # left open: abandoned at close
        (shard,) = self.shards()
        report = ledger.verify_shard(shard)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.outcomes, {"ok": 1, "abandoned": 1})
        rec = ledger.iter_trials(self.dir)[0]
        self.assertEqual(sorted(rec.series_shas), ["mtm_pnl"])
        self.assertEqual(len(ledger.load_series([rec], "mtm_pnl", self.dir)[rec.key]), 30)

    def test_the_package_reads_this_repositorys_committed_ledger(self):
        """The real fixture: every trial this research base ever counted."""
        committed = REPO / "docs" / "research" / "trials"
        reports = ledger.verify_ledger(committed)
        self.assertGreater(len(reports), 50)
        self.assertEqual([r.path.name for r in reports if not r.ok], [])
        self.assertEqual(ledger.family_counts(committed), monad_trials.family_counts(committed))


# ── 2. the ledger's properties ───────────────────────────────────────────────
class TestLedgerProperties(Case):
    def test_intent_is_on_disk_before_the_function_runs(self):
        seen = {}

        def fn(x):
            rows = [json.loads(l) for l in self.shards()[0].read_text().splitlines()]
            seen["types"] = [r["type"] for r in rows]
            seen["spec"] = rows[-1]["spec"]["params"]
            return noise(x)

        with self.study() as st:
            st.evaluate(fn, {"x": 3})
        self.assertEqual(seen["types"], ["run_open", "intent"])
        self.assertEqual(seen["spec"], {"x": 3})

    def test_a_killed_process_leaves_a_counted_orphan_and_seal_closes_it(self):
        code = (
            "import os, sys, pandas as pd, countedtrials as ct\n"
            "st = ct.Study('fam.crash', ledger_dir=sys.argv[1], producer='crash').__enter__()\n"
            "st.evaluate(lambda x: pd.Series([0.01, -0.01, 0.02], "
            "index=pd.bdate_range('2024-01-01', periods=3)), {'x': 1})\n"
            "st.evaluate(lambda x: os._exit(9), {'x': 2})\n")
        env = {**os.environ, "PYTHONPATH": str(PKG)}
        proc = subprocess.run([sys.executable, "-c", code, str(self.dir)], env=env)
        self.assertEqual(proc.returncode, 9)
        counts = ledger.family_counts(self.dir)["fam.crash"]
        self.assertEqual((counts["intents"], counts["ok"], counts["orphans"]), (2, 1, 1))
        bad = [r for r in ledger.verify_ledger(self.dir, require_closed=True) if not r.ok]
        self.assertEqual(len(bad), 1)
        self.assertIn("sealed", ledger.seal(self.shards()[0]))
        self.assertEqual([r.errors for r in ledger.verify_ledger(self.dir, require_closed=True)], [[]])
        self.assertEqual(ledger.family_counts(self.dir)["fam.crash"]["intents"], 2)

    def test_editing_a_recorded_result_is_detected(self):
        with self.study() as st:
            st.search(lambda seed: noise(seed), {"seed": [1, 2]})
        shard = self.shards()[0]
        text = shard.read_text()
        self.assertIn('"seed":2', text)
        shard.write_text(text.replace('"seed":2', '"seed":7'))
        errors = ledger.verify_shard(shard).errors
        self.assertTrue(any("hash chain broken" in e or "spec_hash" in e for e in errors), errors)
        with self.assertRaises(ct.LedgerError):
            ledger.iter_trials(self.dir)     # readers refuse a tampered ledger; they do not skip it

    def test_deleting_a_losing_trial_is_detected(self):
        with self.study() as st:
            st.search(lambda seed: noise(seed), {"seed": [1, 2, 3]})
        shard = self.shards()[0]
        lines = shard.read_text().splitlines(keepends=True)
        drop = next(i for i, l in enumerate(lines) if '"type":"intent"' in l and '"seed":2' in l)
        shard.write_text("".join(lines[:drop] + lines[drop + 1:]))
        self.assertFalse(ledger.verify_shard(shard).ok)

    def test_swapping_a_return_series_is_detected(self):
        with self.study() as st:
            st.evaluate(lambda seed: noise(seed), {"seed": 1})
        (bundle,) = (self.dir / "artifacts").glob("*.json.gz")
        import gzip
        payload = json.loads(gzip.decompress(bundle.read_bytes()))
        key = next(iter(payload["returns"]))
        payload["returns"][key][0][1] = 0.5
        bundle.write_bytes(gzip.compress(json.dumps(payload).encode()))
        self.assertFalse(ledger.verify_shard(self.shards()[0]).ok)

    def test_runs_outside_git_are_counted_and_say_so(self):
        here = os.getcwd()
        os.chdir(self._tmp.name)      # the code state is read from the working directory
        try:
            with self.study() as st:
                st.evaluate(lambda seed: noise(seed), {"seed": 1})
        finally:
            os.chdir(here)
        head = json.loads(self.shards()[0].read_text().splitlines()[0])
        self.assertIsNone(head["code"]["sha"])
        self.assertIn("git", head["code"]["error"])

    def test_same_params_on_different_data_are_different_trials(self):
        with self.study(data={"symbol": "AAA"}) as a:
            ra = a.evaluate(lambda x: noise(x), {"x": 1})
        with self.study(data={"symbol": "BBB"}) as b:
            rb = b.evaluate(lambda x: noise(x), {"x": 1})
        recs = {r.key: r.spec_hash for r in ledger.iter_trials(self.dir)}
        self.assertNotEqual(recs[ra.key], recs[rb.key])


class TestAppendOnlyHistory(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.dir = self.repo / "research" / "trials"
        self.git("init", "-q", "-b", "main")
        (self.repo / "README").write_text("x\n")
        self.commit("init")
        self._cwd = os.getcwd()
        os.chdir(self.repo)           # a run records the code state of the working directory

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t",
                        "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def test_growth_passes_and_rewrite_or_deletion_fails(self):
        with ct.Study("fam.hist", ledger_dir=self.dir, producer="t") as st:
            st.evaluate(lambda seed: noise(seed), {"seed": 1})
        (first,) = self.dir.glob("TR-*.jsonl")
        self.commit("first run")
        self.git("checkout", "-q", "-b", "work")
        with ct.Study("fam.hist", ledger_dir=self.dir, producer="t") as st:
            st.evaluate(lambda seed: noise(seed), {"seed": 2})
        self.assertEqual(ledger.verify_append_only("main", ledger_dir=self.dir), [])

        original = first.read_bytes()
        first.write_bytes(original.replace(b'"seed":1', b'"seed":5'))
        self.assertTrue(any("rewritten" in p for p in ledger.verify_append_only("main", ledger_dir=self.dir)))
        first.unlink()
        self.assertTrue(any("deleted" in p for p in ledger.verify_append_only("main", ledger_dir=self.dir)))
        first.write_bytes(original)
        self.assertEqual(ledger.verify_append_only("main", ledger_dir=self.dir), [])

    def test_a_run_writing_its_own_shard_does_not_make_the_code_dirty(self):
        with ct.Study("fam.hist", ledger_dir=self.dir, producer="t") as st:
            st.evaluate(lambda seed: noise(seed), {"seed": 1})
        with ct.Study("fam.hist", ledger_dir=self.dir, producer="t") as st:
            st.evaluate(lambda seed: noise(seed), {"seed": 2})
        before = set(self.dir.glob("TR-*.jsonl"))
        heads = [json.loads(p.read_text().splitlines()[0])["code"] for p in before]
        self.assertEqual([h["dirty"] for h in heads], [False, False])
        self.assertTrue(all(ledger.committed_clean(h) for h in heads))
        (self.repo / "strategy.py").write_text("edge = 1\n")
        with ct.Study("fam.hist", ledger_dir=self.dir, producer="t") as st:
            st.evaluate(lambda seed: noise(seed), {"seed": 3})
        (new,) = set(self.dir.glob("TR-*.jsonl")) - before
        last = json.loads(new.read_text().splitlines()[0])["code"]
        self.assertTrue(last["dirty"])
        self.assertFalse(ledger.committed_clean(last))


class TestGuard(Case):
    def test_a_guarded_backtest_refuses_to_run_uncounted(self):
        @ct.evaluator
        def backtest(seed):
            return noise(seed)

        with self.assertRaises(ct.UncountedEvaluationError):
            backtest(1)
        with self.study() as st:
            self.assertEqual(st.evaluate(backtest, {"seed": 1}).status, "ok")
            with self.assertRaises(ct.UncountedEvaluationError):
                backtest(2)                       # the trial is over; this would be a free look
        self.assertEqual(ledger.family_counts(self.dir)["fam.test"]["intents"], 1)

    def test_one_trial_buys_one_evaluation(self):
        @ct.evaluator
        def backtest(seed):
            return noise(seed)

        def peek_twice(seed):
            backtest(seed)
            return backtest(seed + 1)             # nested inside ONE counted evaluation: allowed

        with self.study() as st:
            st.evaluate(peek_twice, {"seed": 1})
            run = st.run
            trial = run.begin({"manual": True})
            backtest(1)
            with self.assertRaises(ct.UncountedEvaluationError):
                backtest(2)
            trial.complete({"n": 0})

    def test_the_bypass_needs_a_written_reason(self):
        @ct.evaluator
        def backtest(seed):
            return noise(seed)

        with self.assertRaises(ct.UncountedEvaluationError):
            with ct.uncounted("because"):
                backtest(1)
        with ct.uncounted("unit test of the fill model, measures nothing"):
            self.assertEqual(len(backtest(1)), 1000)


# ── 3. the Study API and the verdict ─────────────────────────────────────────
class TestStudy(Case):
    def test_search_counts_the_configurations_that_raise(self):
        def fn(fast, slow):
            if fast >= slow:
                raise ValueError("fast must be shorter than slow")
            return noise(fast * 100 + slow)

        with self.study() as st:
            results = st.search(fn, {"fast": [5, 50], "slow": [20, 100]})
        self.assertEqual([r.status for r in results], ["ok", "ok", "error", "ok"])
        counts = ledger.family_counts(self.dir)["fam.test"]
        self.assertEqual((counts["intents"], counts["ok"], counts["error"]), (4, 3, 1))

    def test_return_contract(self):
        with self.study() as st:
            r = st.evaluate(lambda x: (noise(x), {"turnover": 3.5}), {"x": 1})
            self.assertEqual(r.metrics["turnover"], 3.5)
            self.assertEqual(st.evaluate(lambda x: None, {"x": 2}).metrics["n"], 0)
            with self.assertRaises(ct.LedgerError):
                st.evaluate(lambda x: [0.1, 0.2], {"x": 3})
        statuses = [r.status for r in ledger.iter_trials(self.dir)]
        self.assertEqual(statuses, ["ok", "ok", "error"])

    def test_counted_decorator_is_one_trial_per_call(self):
        with self.study() as st:
            objective = st.counted(lambda x: noise(x))
            self.assertEqual(len(objective(x=1)), 1000)
            objective(x=2)
        self.assertEqual(ledger.family_counts(self.dir)["fam.test"]["intents"], 2)

    def test_a_study_must_be_entered(self):
        with self.assertRaises(ct.LedgerError):
            self.study().evaluate(lambda x: noise(x), {"x": 1})

    def test_expand_grid(self):
        self.assertEqual(ct.expand_grid({"a": [1, 2], "b": [3]}), [{"a": 1, "b": 3}, {"a": 2, "b": 3}])
        self.assertEqual(ct.expand_grid([{"a": 1}]), [{"a": 1}])


class TestVerdict(Case):
    def search(self, seeds, family="fam.test", fn=None):
        with self.study(family) as st:
            st.search(fn or (lambda seed: noise(seed)), {"seed": list(seeds)})

    def test_the_best_of_forty_noise_strategies_is_not_significant(self):
        self.search(range(40))
        rep = ct.report("fam.test", ledger_dir=self.dir, n_boot=500)
        d = rep.deflation
        self.assertGreater(d.psr, 0.95, "the naive reading: looks like an edge")
        self.assertLess(d.result.dsr, 0.90)
        self.assertGreater(d.n_trials, 30)
        self.assertFalse(rep.spa.significant)
        self.assertEqual(rep.spa.tested, 40)
        self.assertIn("NOT SIGNIFICANT", str(rep))

    def test_a_planted_edge_survives_the_same_search(self):
        self.search(range(40), fn=lambda seed: noise(seed, mean=0.0025 if seed == 7 else 0.0))
        rep = ct.report("fam.test", ledger_dir=self.dir, n_boot=500)
        self.assertEqual(json.loads(json.dumps(
            next(r.spec["params"] for r in ledger.iter_trials(self.dir) if r.key == rep.deflation.candidate))),
            {"seed": 7})
        self.assertTrue(rep.spa.significant)
        self.assertGreater(rep.deflation.result.dsr, 0.95)

    def test_rerunning_a_search_does_not_change_the_effective_count(self):
        self.search(range(10))
        once = ct.deflate(ct.best_trial("fam.test", ledger_dir=self.dir), ledger_dir=self.dir)
        self.search(range(10))
        twice = ct.deflate(once.candidate, ledger_dir=self.dir)
        self.assertEqual((once.trials_recorded, twice.trials_recorded), (10, 20))
        self.assertEqual(once.n_trials, twice.n_trials)
        self.assertEqual(once.result.dsr, twice.result.dsr)

    def test_everything_the_test_cannot_see_raises_the_bar(self):
        self.search(range(10), fn=lambda seed: noise(seed, mean=0.001 if seed == 3 else 0.0))
        best = ct.best_trial("fam.test", ledger_dir=self.dir)
        base = ct.family_spa(best, ledger_dir=self.dir, n_boot=500)
        self.assertEqual(base.m, 0)

        declared = ct.family_spa(best, ledger_dir=self.dir, n_boot=500, prior_search_trials=9)
        self.assertEqual(declared.m, 9)
        self.assertAlmostEqual(declared.p_value, min(1.0, declared.worst_p * 10))
        self.assertGreater(ct.deflate(best, ledger_dir=self.dir, prior_search_trials=9).n_trials,
                           ct.deflate(best, ledger_dir=self.dir).n_trials)

        with self.study() as st:   # two failed configurations and one that ran on other dates
            st.search(lambda seed: 1 / 0, {"seed": [100, 101]})
            st.evaluate(lambda seed: pd.Series(np.random.default_rng(5).normal(0, 0.01, 300),
                                               index=pd.bdate_range("2010-01-01", periods=300)),
                        {"seed": 200})
        after = ct.family_spa(best, ledger_dir=self.dir, n_boot=500)
        self.assertEqual((after.unknown_specs, after.off_window, after.m), (2, 1, 3))
        self.assertEqual(after.tested, base.tested)
        self.assertGreaterEqual(after.p_value, base.p_value)

    def test_a_failed_spec_that_later_ran_is_not_charged_twice(self):
        calls = {"n": 0}

        def flaky(seed):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("data feed timeout")
            return noise(seed)

        with self.study() as st:
            st.search(flaky, {"seed": [1]})
            st.search(flaky, {"seed": [1, 2]})
        best = ct.best_trial("fam.test", ledger_dir=self.dir)
        self.assertEqual(ct.deflate(best, ledger_dir=self.dir).unknown_specs_added, 0)

    def test_a_one_idea_family_says_its_dsr_is_degenerate(self):
        base = noise(1, mean=0.0005)
        self.search(range(6), fn=lambda seed: base + noise(seed + 50) * 0.05)
        d = ct.deflate(ct.best_trial("fam.test", ledger_dir=self.dir), ledger_dir=self.dir)
        self.assertEqual(d.effective.n_clusters, 1)
        self.assertTrue(d.degenerate)
        self.assertEqual(d.result.dsr, d.psr)
        self.assertIn("deflates nothing here", analysis.format_deflation(d))

    def test_benchmark_is_subtracted_and_must_cover_the_window(self):
        market = noise(999, mean=0.0005)
        self.search(range(5), fn=lambda seed: market + noise(seed) * 0.3)
        best = ct.best_trial("fam.test", ledger_dir=self.dir)
        vs_cash = ct.family_spa(best, ledger_dir=self.dir, n_boot=500)
        vs_market = ct.family_spa(best, ledger_dir=self.dir, n_boot=500, benchmark=market)
        self.assertLess(vs_market.blocks[0]["candidate_t"], vs_cash.blocks[0]["candidate_t"])
        with self.assertRaises(ValueError):
            ct.family_spa(best, ledger_dir=self.dir, n_boot=500, benchmark=market.iloc[:500])

    def test_refusals(self):
        self.search(range(2))
        with self.study() as st:
            failed = st.evaluate(lambda seed: 1 / 0, {"seed": 5}, reraise=False)
        with self.assertRaises(ValueError):
            ct.deflate(failed.key, ledger_dir=self.dir)
        with self.assertRaises(ValueError):
            ct.deflate("not-a-key", ledger_dir=self.dir)
        with self.assertRaises(ValueError):
            ct.report("fam.absent", ledger_dir=self.dir)
        with self.assertRaises(ValueError):
            ct.deflate(ct.best_trial("fam.test", ledger_dir=self.dir), ledger_dir=self.dir,
                       prior_search_trials=-1)


class TestWhatAReviewFound(Case):
    """Regressions from the independent review of the first version (2026-11-22). The first
    two made a result look MORE significant than the recorded search allows."""

    def test_results_seen_in_a_killed_run_are_charged_not_forgotten(self):
        """Series are bundled at run close. Forty trials complete, the process dies, the
        run is sealed: their outcomes say ``ok`` but their returns never reached disk. A
        second run then evaluates only the winner. The forty were looked at; they count."""
        code = (
            "import os, sys, numpy as np, pandas as pd, countedtrials as ct\n"
            "d = pd.bdate_range('2018-01-01', periods=1000)\n"
            "f = lambda seed: pd.Series(np.random.default_rng(seed).normal(0, 0.01, 1000), index=d)\n"
            "st = ct.Study('fam.test', ledger_dir=sys.argv[1], producer='killed').__enter__()\n"
            "st.search(f, {'seed': list(range(40))})\n"
            "os._exit(0)\n")
        subprocess.run([sys.executable, "-c", code, str(self.dir)],
                       env={**os.environ, "PYTHONPATH": str(PKG)}, check=True)
        ledger.seal(self.shards()[0])
        with self.study() as st:
            winner = st.evaluate(lambda seed: noise(seed), {"seed": 7})
        spa = ct.family_spa(winner.key, ledger_dir=self.dir, n_boot=500)
        # All forty: a spec is params + data + the function's qualified name, and the
        # re-run's function is a different object from the killed script's, so the winner's
        # earlier evaluation is not "the same spec, now visible". The conservative reading.
        self.assertEqual((spa.tested, spa.unknown_specs, spa.m), (1, 40, 40))
        self.assertAlmostEqual(spa.p_value, min(1.0, spa.worst_p * 41))
        d = ct.deflate(winner.key, ledger_dir=self.dir)
        self.assertEqual(d.unknown_specs_added, 40)
        self.assertGreaterEqual(d.n_trials, 41)

    def test_results_in_a_run_still_open_are_charged_too(self):
        with self.study() as other:
            other.search(lambda seed: noise(seed), {"seed": list(range(10, 20))})
            with self.study() as st:
                mine = st.evaluate(lambda seed: noise(seed), {"seed": 1})
                with self.assertRaisesRegex(ValueError, "has not written them to disk"):
                    ct.family_spa(mine.key, ledger_dir=self.dir, n_boot=300)
            spa = ct.family_spa(mine.key, ledger_dir=self.dir, n_boot=300)
            self.assertEqual((spa.tested, spa.unknown_specs), (1, 10))
        after = ct.family_spa(mine.key, ledger_dir=self.dir, n_boot=300)
        self.assertEqual((after.tested, after.unknown_specs), (11, 0))

    def test_a_benchmark_with_holes_is_refused_not_zero_filled(self):
        market = noise(999, mean=0.0005)
        with self.study() as st:
            st.search(lambda seed: market + noise(seed) * 0.1, {"seed": [1, 2, 3]})
        best = ct.best_trial("fam.test", ledger_dir=self.dir)
        full = ct.family_spa(best, ledger_dir=self.dir, n_boot=300, benchmark=market)
        self.assertGreater(full.p_value, 0.05)
        for holed in (market.iloc[::2], market.resample("W").sum()):
            with self.assertRaisesRegex(ValueError, "benchmark is missing"):
                ct.family_spa(best, ledger_dir=self.dir, n_boot=300, benchmark=holed)

    def test_timezone_aware_indexes_keep_their_local_dates(self):
        for tz in ("America/New_York", "Asia/Tokyo"):
            with self.subTest(tz=tz):
                fam = f"fam.{tz.split('/')[1]}"
                idx = pd.bdate_range("2023-01-02", periods=400).tz_localize(tz)
                rng = np.random.default_rng(3)
                with self.study(fam) as st:
                    st.search(lambda k: pd.Series(rng.normal(0, 0.01, 400), index=idx), {"k": [1, 2]})
                d = ct.deflate(ct.best_trial(fam, ledger_dir=self.dir), ledger_dir=self.dir)
                self.assertEqual(d.moments.n_obs, 400)   # no session moved onto a weekend

    def test_a_series_the_readers_could_not_use_is_refused_at_write_time(self):
        bad = {
            "int index": pd.Series([0.01, -0.01, 0.02]),
            "leading NaN": noise(1).pct_change(),
        }
        with self.study() as st:
            st.evaluate(lambda seed: noise(seed), {"seed": 1})
            for i, (name, series) in enumerate(bad.items()):
                with self.subTest(name), self.assertRaises(ct.LedgerError):
                    st.evaluate(lambda case: series, {"case": i})
        self.assertEqual([r.status for r in ledger.iter_trials(self.dir)], ["ok", "error", "error"])
        ct.report("fam.test", ledger_dir=self.dir, n_boot=300)   # the family is still readable

    def test_when_every_trial_raised_the_report_says_why(self):
        with self.study() as st:
            st.search(lambda seed: noise(seed).pct_change(), {"seed": [1, 2]})
        with self.assertRaisesRegex(ValueError, r"2 trial\(s\) raised.*pct_change"):
            ct.report("fam.test", ledger_dir=self.dir)

    def test_a_three_day_series_cannot_be_the_reported_winner(self):
        tiny = pd.Series([0.010, 0.011, 0.0105], index=pd.bdate_range("2019-06-03", periods=3))
        with self.study() as st:
            real = st.evaluate(lambda seed: noise(seed, mean=0.001), {"seed": 1})
            st.evaluate(lambda seed: tiny, {"seed": 2})
        self.assertEqual(ct.best_trial("fam.test", ledger_dir=self.dir), real.key)

    def test_searching_on_after_a_verdict_opens_a_new_run(self):
        with self.study() as st:
            st.search(lambda seed: noise(seed), {"seed": [1, 2]})
            st.report(n_boot=300)
            st.search(lambda seed: noise(seed), {"seed": [3]})
            self.assertEqual(st.deflate().trials_recorded, 3)
        counts = ledger.family_counts(self.dir)["fam.test"]
        self.assertEqual((counts["runs"], counts["intents"]), (2, 3))
        self.assertEqual([r.errors for r in ledger.verify_ledger(self.dir, require_closed=True)], [[], []])

    def test_counted_records_positional_arguments_by_name(self):
        with self.study() as st:
            objective = st.counted(lambda seed, scale=1.0: noise(seed) * scale)
            objective(4, scale=2.0)
        self.assertEqual(ledger.iter_trials(self.dir)[0].spec["params"], {"seed": 4, "scale": 2.0})

    def test_a_ledger_at_the_repository_root_still_sees_a_dirty_tree(self):
        repo = Path(self._tmp.name) / "repo"
        repo.mkdir()
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
        subprocess.run([*git, "init", "-q"], check=True)
        (repo / "strategy.py").write_text("edge = 0\n")
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "init"], check=True)
        clean = ledger.code_state(repo, exclude=[repo])
        self.assertIs(clean["dirty"], False)
        (repo / "TR-20260101T000000Z-00000000.jsonl").write_text("{}\n")   # the ledger's own file
        self.assertIs(ledger.code_state(repo, exclude=[repo])["dirty"], False)
        (repo / "strategy.py").write_text("edge = 1\n")
        self.assertIs(ledger.code_state(repo, exclude=[repo])["dirty"], True)


class TestCLI(Case):
    def cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["--ledger", str(self.dir), *argv])
        return code, out.getvalue()

    def test_stats_verify_report_deflate_show(self):
        with self.study() as st:
            st.search(lambda seed: noise(seed), {"seed": list(range(6))})
            key = st.best()
        code, out = self.cli("stats", "--json")
        self.assertEqual((code, json.loads(out)["fam.test"]["intents"]), (0, 6))
        self.assertEqual(self.cli("verify", "--require-closed")[0], 0)
        code, out = self.cli("report", "fam.test", "--n-boot", "300", "--prior", "4")
        self.assertEqual(code, 0)
        self.assertIn("VERDICT", out)
        self.assertIn("4 declared prior", out)
        code, out = self.cli("deflate", key)
        self.assertEqual(code, 0)
        self.assertIn("DSR", out)
        self.assertEqual(self.cli("show", key.split("#")[0])[0], 0)
        self.assertEqual(self.cli("report", "fam.absent")[0], 1)

    def test_verify_fails_on_a_ledger_directory_that_does_not_exist(self):
        code, out = self.cli("verify", "--require-closed")
        self.assertEqual(code, 1, "a CI gate pointed at a mistyped path must not pass")
        self.assertIn("no ledger directory", out)

    def test_a_tampered_ledger_is_refused_without_a_traceback(self):
        with self.study() as st:
            st.evaluate(lambda seed: noise(seed), {"seed": 1})
        shard = self.shards()[0]
        shard.write_text(shard.read_text().replace('"seed":1', '"seed":2'))
        code, out = self.cli("report", "fam.test")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", out)

    def test_verify_exits_nonzero_on_tampering(self):
        with self.study() as st:
            st.evaluate(lambda seed: noise(seed), {"seed": 1})
        shard = self.shards()[0]
        shard.write_text(shard.read_text().replace('"seed":1', '"seed":2'))
        code, out = self.cli("verify")
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)


class TestPackaging(unittest.TestCase):
    def test_version_is_stated_once_in_each_place_and_agrees(self):
        import re
        pyproject = (PKG / "pyproject.toml").read_text()
        self.assertEqual(re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1), ct.__version__)

    def test_the_package_imports_nothing_from_this_repository(self):
        import ast
        for path in sorted((PKG / "countedtrials").glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                mods = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mods = [node.module or ""]
                for mod in mods:
                    self.assertNotIn(mod.split(".")[0], {"src", "tools", "live", "config", "config_modules"},
                                     f"{path.name} imports {mod}")

    def test_the_readme_demo_output_is_what_the_demo_prints(self):
        """The README quotes the example's report. Re-run it and compare the lines that do
        not carry a run id, so the documented numbers cannot go stale."""
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(PKG / "examples" / "rule_zoo_on_noise.py"), str(Path(tmp) / "t")],
                env={**os.environ, "PYTHONPATH": str(PKG)}, capture_output=True, text=True, cwd=tmp)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        readme = (PKG / "README.md").read_text()
        printed = [l for l in proc.stdout.splitlines() if l.strip() and not l.startswith("candidate")]
        self.assertGreater(len(printed), 8)
        for line in printed:
            self.assertIn(line, readme)


if __name__ == "__main__":
    unittest.main()
