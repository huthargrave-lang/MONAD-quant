"""
Tests for the trial ledger (src/research/trials.py) and its CLI (tools/trial_ledger.py).

The ledger's job is to make the trial count honest: every attempt is written before
its result exists, nothing written can be edited or removed without detection, and
a crash never erases a trial. These tests pin each of those properties, including
the adversarial ones (tampering, reordering, deletion, history rewrite).
"""
import gzip
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from src.research import trials  # noqa: E402
from src.research.trials import LedgerError, open_run  # noqa: E402
import trial_ledger  # noqa: E402


def _series(n=5, seed=0):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0, 0.01, n), index=pd.date_range("2024-01-01", periods=n, freq="h"))


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "trials"

    def tearDown(self):
        self._tmp.cleanup()

    def run_(self, **kw):
        kw.setdefault("producer", "test")
        kw.setdefault("family", "fam:test")
        return open_run(ledger_dir=self.dir, **kw)

    def rows(self, path):
        return [json.loads(l) for l in Path(path).read_text().splitlines()]

    def only_shard(self):
        shards = trials.shard_paths(self.dir)
        self.assertEqual(len(shards), 1)
        return shards[0]


class TestCanonicalEncoding(unittest.TestCase):
    def test_key_order_and_numpy_types_do_not_change_the_hash(self):
        a = {"b": np.int64(3), "a": np.float64(0.5), "c": (1, 2), "t": pd.Timestamp("2024-01-01")}
        b = {"t": "2024-01-01T00:00:00", "c": [1, 2], "a": 0.5, "b": 3}
        self.assertEqual(trials.spec_hash(a), trials.spec_hash(b))

    def test_any_value_change_changes_the_hash(self):
        self.assertNotEqual(trials.spec_hash({"rsi": 38}), trials.spec_hash({"rsi": 39}))

    def test_nonfinite_rejected_in_specs(self):
        with self.assertRaises(LedgerError):
            trials.spec_hash({"x": float("nan")})

    def test_unknown_types_rejected_not_stringified(self):
        with self.assertRaises(LedgerError):
            trials.spec_hash({"x": object()})
        with self.assertRaises(LedgerError):
            trials.spec_hash({1: "non-string key"})

    def test_metric_nonfinite_round_trips(self):
        enc = json.loads(trials.canonical_json({"s": math.nan, "u": math.inf, "d": -math.inf, "x": 1.5},
                                               nonfinite="encode"))
        dec = trials.decode_metrics(enc)
        self.assertTrue(math.isnan(dec["s"]))
        self.assertEqual((dec["u"], dec["d"], dec["x"]), (math.inf, -math.inf, 1.5))

    def test_returns_reject_nan_and_non_numbers(self):
        with self.assertRaises(LedgerError):
            trials.canonical_returns([("2024-01-01", float("nan"))])
        with self.assertRaises(LedgerError):
            trials.canonical_returns([("2024-01-01", "0.1")])
        with self.assertRaises(LedgerError):
            trials.canonical_returns([0.1, 0.2])

    def test_series_and_pairs_encode_identically(self):
        s = _series(3)
        pairs = [(ts, float(v)) for ts, v in s.items()]
        self.assertEqual(trials.canonical_returns(s), trials.canonical_returns(pairs))


class TestWriter(LedgerCase):
    def test_full_run_is_valid_and_counted(self):
        with self.run_(hypothesis="H7", context={"ticker": "QQQ"}) as run:
            for i in range(3):
                with run.trial(params={"rsi": 30 + i}, data={"data_hash": "abc"}) as t:
                    t.complete(metrics={"sharpe": 0.1 * i}, returns=_series(4, seed=i))
        r = trials.verify_shard(self.only_shard())
        self.assertEqual(r.errors, [])
        self.assertEqual((r.closed, r.close_status, r.intents, r.orphans), (True, "complete", 3, 0))
        self.assertEqual(r.outcomes, {"ok": 3})
        self.assertEqual(r.hypothesis, "H7")

    def test_intent_is_durable_before_the_result_is_computed(self):
        with self.run_() as run:
            t = run.begin(params={"k": 1})
            rows = self.rows(run.path)
            self.assertEqual([x["type"] for x in rows], ["run_open", "intent"])
            t.complete(metrics={"sharpe": 1.0})

    def test_exception_in_trial_records_error_and_run_aborts(self):
        with self.assertRaises(ZeroDivisionError):
            with self.run_() as run:
                with run.trial(params={"k": 1}):
                    1 / 0
        rows = self.rows(self.only_shard())
        outcome = [x for x in rows if x["type"] == "outcome"][0]
        self.assertEqual(outcome["status"], "error")
        self.assertIn("ZeroDivisionError", outcome["error"])
        self.assertEqual(rows[-1]["status"], "aborted")
        self.assertEqual(trials.verify_shard(self.only_shard()).errors, [])

    def test_trial_left_without_outcome_is_abandoned_not_dropped(self):
        with self.run_() as run:
            with run.trial(params={"k": 1}):
                pass
            run.begin(params={"k": 2})  # never completed
        r = trials.verify_shard(self.only_shard())
        self.assertEqual(r.outcomes, {"abandoned": 2})
        self.assertEqual(r.intents, 2)

    def test_double_outcome_refused(self):
        with self.run_() as run:
            t = run.begin(params={"k": 1})
            t.complete(metrics={})
            with self.assertRaises(LedgerError):
                t.complete(metrics={})

    def test_bad_family_and_hypothesis_refused(self):
        with self.assertRaises(LedgerError):
            open_run(producer="p", family="has space", ledger_dir=self.dir)
        with self.assertRaises(LedgerError):
            open_run(producer="p", family="ok", hypothesis="F3", ledger_dir=self.dir)

    def test_identical_returns_stored_once_and_bundle_is_content_addressed(self):
        s = _series(4)
        with self.run_() as run:
            for k in range(2):
                run.begin(params={"k": k}).complete(metrics={}, returns=s)
        close = self.rows(self.only_shard())[-1]
        bundle = trials.read_bundle(self.dir / trials.ARTIFACTS, close["bundle_sha"])
        self.assertEqual(len(bundle), 1)

    def test_bundle_bytes_are_deterministic(self):
        self.dir.mkdir(parents=True)
        sha = trials.write_bundle(self.dir, {"x": [["t", 1.0]]})
        path = self.dir / f"{sha}.json.gz"
        first = path.read_bytes()
        path.unlink()
        trials.write_bundle(self.dir, {"x": [["t", 1.0]]})
        self.assertEqual(first, path.read_bytes())

    def test_code_state_recorded(self):
        with self.run_() as run:
            pass
        code = self.rows(self.only_shard())[0]["code"]
        self.assertIn("sha", code)
        self.assertIn("dirty", code)


class TestTamperDetection(LedgerCase):
    def _make(self):
        with self.run_() as run:
            for k in range(3):
                run.begin(params={"k": k}).complete(metrics={"sharpe": float(k)}, returns=_series(3, k))
        return self.only_shard()

    def _lines(self, path):
        return path.read_text().splitlines(keepends=True)

    def test_edited_metric_breaks_the_chain(self):
        path = self._make()
        path.write_text(path.read_text().replace('"sharpe":0.0', '"sharpe":9.0'))
        self.assertTrue(any("chain" in e for e in trials.verify_shard(path).errors))

    def test_deleted_losing_trial_detected(self):
        path = self._make()
        lines = self._lines(path)
        del lines[1:3]  # the first intent and its outcome
        path.write_text("".join(lines))
        self.assertFalse(trials.verify_shard(path).ok)

    def test_reordered_rows_detected(self):
        path = self._make()
        lines = self._lines(path)
        lines[1], lines[3] = lines[3], lines[1]
        path.write_text("".join(lines))
        self.assertFalse(trials.verify_shard(path).ok)

    def test_tampered_bundle_detected(self):
        path = self._make()
        bundle = next((self.dir / trials.ARTIFACTS).glob("*.json.gz"))
        data = json.loads(gzip.decompress(bundle.read_bytes()))
        key = next(iter(data["returns"]))
        data["returns"][key][0][1] = 0.5
        bundle.write_bytes(gzip.compress(json.dumps(data).encode()))
        self.assertTrue(any("does not match" in e for e in trials.verify_shard(path).errors))

    def test_spec_edited_with_rehashed_chain_still_caught_by_spec_hash(self):
        # An attacker who recomputes the chain still cannot change a spec without its hash.
        path = self._make()
        rows = self.rows(path)
        rows[1]["spec"]["params"]["k"] = 99
        prev = trials.genesis(path.stem)
        out = []
        for row in rows:
            row["prev"] = prev
            line = trials.canonical_json(row, nonfinite="encode")
            prev = __import__("hashlib").sha256(line.encode()).hexdigest()
            out.append(line + "\n")
        path.write_text("".join(out))
        self.assertTrue(any("spec_hash" in e for e in trials.verify_shard(path).errors))


class TestCrashAndSeal(LedgerCase):
    def _crash(self, torn=b""):
        ctx = self.run_()
        run = ctx.__enter__()
        run.begin(params={"k": 1}).complete(metrics={"sharpe": 1.0}, returns=_series(3))
        run.begin(params={"k": 2})  # dies while computing this one
        run._fh.close()             # process death: no close row, flock released
        if torn:
            with open(run.path, "ab") as f:
                f.write(torn)
        return run.path

    def test_orphan_counts_as_a_trial(self):
        path = self._crash()
        r = trials.verify_shard(path)
        self.assertEqual((r.intents, r.orphans, r.closed), (2, 1, False))
        self.assertEqual(trials.family_counts(self.dir)["fam:test"]["intents"], 2)

    def test_require_closed_flags_unclosed_run(self):
        self._crash()
        reports = trials.verify_ledger(self.dir, require_closed=True)
        self.assertFalse(reports[0].ok)

    def test_seal_closes_and_keeps_the_count(self):
        path = self._crash()
        trials.seal(path)
        r = trials.verify_shard(path)
        self.assertEqual(r.errors, [])
        self.assertEqual((r.close_status, r.intents, r.orphans), ("crashed", 2, 1))

    def test_seal_drops_only_a_torn_tail(self):
        path = self._crash(torn=b'{"v":1,"seq":4,"prev":"x","ty')
        self.assertTrue(trials.verify_shard(path).torn_tail)
        msg = trials.seal(path)
        self.assertIn("dropped 1 torn row", msg)
        r = trials.verify_shard(path)
        self.assertEqual(r.errors, [])
        self.assertEqual(r.intents, 2)

    def test_empty_shard_is_reported_and_not_sealable(self):
        self.dir.mkdir(parents=True)
        path = self.dir / f"{trials.new_run_id()}.jsonl"
        path.write_bytes(b'{"v":1,"seq":0,"pr')  # torn run_open
        self.assertFalse(trials.verify_shard(path).ok)
        with self.assertRaises(LedgerError):
            trials.seal(path)

    def test_seal_refuses_a_live_run(self):
        with self.run_() as run:
            with self.assertRaises(LedgerError):
                trials.seal(run.path)

    def test_seal_refuses_a_closed_run(self):
        with self.run_():
            pass
        with self.assertRaises(LedgerError):
            trials.seal(self.only_shard())


class TestAppendOnlyHistory(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.git("init", "-q", "-b", "base")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.ledger = self.repo / trials.LEDGER_REL
        with open_run(producer="t", family="f", ledger_dir=self.ledger, repo=self.repo) as run:
            run.begin(params={"k": 1}).complete(metrics={}, returns=_series(3))
        self.shard = run.path
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("checkout", "-q", "-b", "work")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def check(self):
        return trials.verify_append_only("base", repo=self.repo)

    def test_untouched_history_passes(self):
        self.assertEqual(self.check(), [])

    def test_new_run_is_fine(self):
        with open_run(producer="t", family="f", ledger_dir=self.ledger, repo=self.repo) as run:
            run.begin(params={"k": 2}).complete(metrics={})
        self.assertEqual(self.check(), [])

    def test_deleted_shard_is_a_violation(self):
        self.shard.unlink()
        self.assertTrue(any("deleted" in p for p in self.check()))

    def test_rewritten_shard_is_a_violation(self):
        self.shard.write_text(self.shard.read_text().replace('"k":1', '"k":2'))
        self.assertTrue(any("rewritten" in p for p in self.check()))

    def test_changed_artifact_is_a_violation(self):
        art = next((self.ledger / trials.ARTIFACTS).glob("*.json.gz"))
        art.write_bytes(art.read_bytes() + b"x")
        self.assertTrue(any("artifact changed" in p for p in self.check()))

    def test_docs_beside_the_ledger_stay_editable(self):
        readme = self.ledger / "README.md"
        readme.write_text("v1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "readme")
        self.git("branch", "-f", "base")
        readme.write_text("rewritten\n")
        self.assertEqual(self.check(), [])

    def test_unknown_ref_fails_loudly(self):
        self.assertTrue(trials.verify_append_only("no-such-ref", repo=self.repo))

    def test_code_state_sees_dirty_tree_but_not_its_own_ledger(self):
        clean = trials.code_state(self.repo)
        self.assertEqual((clean["dirty"], clean["error"]), (False, None))
        with open_run(producer="t", family="f", ledger_dir=self.ledger, repo=self.repo):
            pass
        self.assertFalse(trials.code_state(self.repo)["dirty"])
        (self.repo / "new_lab.py").write_text("print(1)\n")
        dirty = trials.code_state(self.repo)
        self.assertTrue(dirty["dirty"])
        self.assertRegex(dirty["diff_sha256"], r"^[0-9a-f]{64}$")


class TestCli(LedgerCase):
    def setUp(self):
        super().setUp()
        self._orig = trials.LEDGER_DIR
        trials.LEDGER_DIR = self.dir

    def tearDown(self):
        trials.LEDGER_DIR = self._orig
        super().tearDown()

    def test_verify_exit_codes(self):
        with self.run_() as run:
            run.begin(params={"k": 1}).complete(metrics={})
        self.assertEqual(trial_ledger.main(["verify", "--require-closed"]), 0)
        path = self.only_shard()
        path.write_text(path.read_text().replace('"k":1', '"k":7'))
        self.assertEqual(trial_ledger.main(["verify"]), 1)

    def test_stats_and_show_run(self):
        with self.run_() as run:
            run.begin(params={"k": 1}).complete(metrics={})
        self.assertEqual(trial_ledger.main(["stats", "--json"]), 0)
        self.assertEqual(trial_ledger.main(["show", run.run_id]), 0)


if __name__ == "__main__":
    unittest.main()
