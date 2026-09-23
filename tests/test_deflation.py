"""
Tests for src/research/deflation.py — deflating a recorded trial by its whole family.

The property that matters: the BEST of many pure-noise trials must not look like an
edge once the search is counted, while a genuine edge found in one trial should.
Also pinned: unknown-result trials add to N, the count spans every producer in the
family, and a tampered shard stops the computation rather than being skipped.
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.research import deflation, trials


def _series(rng, n=250, mu=0.0, sd=0.01, start="2023-01-02"):
    idx = pd.bdate_range(start, periods=n) + pd.Timedelta(hours=10)
    return pd.Series(rng.normal(mu, sd, n), index=idx)


class FamilyDeflation(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.rng = np.random.default_rng(11)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, family, series_list, statuses=None, producer="t"):
        keys = []
        with trials.open_run(producer=producer, family=family, ledger_dir=self.dir) as run:
            for i, s in enumerate(series_list):
                t = run.begin(params={"i": i, "p": producer})
                status = (statuses or {}).get(i, "ok")
                if status == "error":
                    t.fail("boom")
                elif status == "ok":
                    t.complete(metrics={"sharpe_ratio": float(s.mean() / s.std())}, returns=s)
                keys.append(f"{run.run_id}#{i}")
        return keys

    def _best(self, keys, series_list):
        sharpes = [s.mean() / s.std() for s in series_list]
        return keys[int(np.argmax(sharpes))]

    def test_best_of_many_noise_trials_is_not_an_edge(self):
        noise = [_series(self.rng) for _ in range(60)]
        keys = self._run("noise:X", noise)
        d = deflation.deflate_candidate(self._best(keys, noise), ledger_dir=self.dir)
        self.assertGreater(d.n_trials, 30)
        self.assertLess(d.result.dsr, 0.95)
        self.assertGreater(d.result.sr0, 0)

    def test_a_real_edge_tried_once_survives(self):
        keys = self._run("edge:X", [_series(self.rng, n=750, mu=0.002)])
        d = deflation.deflate_candidate(keys[0], ledger_dir=self.dir)
        self.assertEqual(d.result.sr0, 0.0)
        self.assertGreater(d.result.dsr, 0.99)

    def test_unknown_results_add_to_n(self):
        series = [_series(self.rng) for _ in range(5)]
        keys = self._run("mixed:X", series, statuses={3: "error", 4: "error"})
        d = deflation.deflate_candidate(keys[0], ledger_dir=self.dir)
        self.assertEqual(d.unknown_specs_added, 2)
        self.assertEqual(d.n_trials, d.effective.n_effective + 2)

    def test_the_count_spans_every_producer_in_the_family(self):
        a = [_series(self.rng) for _ in range(4)]
        b = [_series(self.rng) for _ in range(4)]
        keys = self._run("shared:X", a, producer="sweep.py")
        self._run("shared:X", b, producer="tools/walkforward_eval.py")
        self._run("other:Y", [_series(self.rng) for _ in range(10)])
        d = deflation.deflate_candidate(keys[0], ledger_dir=self.dir)
        self.assertEqual(d.trials_recorded, 8)

    def test_a_trial_without_returns_cannot_be_deflated(self):
        with trials.open_run(producer="t", family="f:X", ledger_dir=self.dir) as run:
            run.begin(params={}).complete(metrics={"total_trades": 0})
            key = f"{run.run_id}#0"
        with self.assertRaises(ValueError):
            deflation.deflate_candidate(key, ledger_dir=self.dir)

    def test_a_tampered_shard_stops_the_computation(self):
        keys = self._run("t:X", [_series(self.rng) for _ in range(3)])
        shard = next(self.dir.glob("TR-*.jsonl"))
        shard.write_text(shard.read_text().replace('"i":1', '"i":9'))
        with self.assertRaises(trials.LedgerError):
            deflation.deflate_candidate(keys[0], ledger_dir=self.dir)


class Calibration(unittest.TestCase):
    """Canaries on the whole ledger -> deflation path, seeded so they are deterministic.

    Measured when this was written (30 noise trials + candidate, per-family):
      pure noise, 60 families: best-of-family admitted at DSR >= 0.95 in 0/60 (median 0.46)
      planted annual Sharpe 3.0 over 750 days, 30 families: admitted 27/30
      planted annual Sharpe 2.0 over 750 days: 9/30; over 250 days: 1/30
    i.e. conservative under the null, and modest edges need long samples once the search
    is counted (consistent with the repo's own power study, E25). These bounds guard the
    calibration against silent drift in either direction.
    """

    def _family(self, seed, planted_annual_sharpe=0.0, n=31, T=750):
        rng = np.random.default_rng(seed)
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            sharpes = []
            with trials.open_run(producer="t", family="cal:X", ledger_dir=d) as run:
                for i in range(n):
                    mu = planted_annual_sharpe / np.sqrt(252) * 0.01 if i == 0 else 0.0
                    s = _series(rng, n=T, mu=mu, start="2021-01-04")
                    run.begin(params={"i": i}).complete(metrics={}, returns=s)
                    sharpes.append(s.mean() / s.std())
                rid = run.run_id
            best = int(np.argmax(sharpes))
            dsr = deflation.deflate_candidate(f"{rid}#{best}", ledger_dir=d).result.dsr
            return best, dsr

    def test_noise_is_not_admitted(self):
        admitted = sum(self._family(9000 + k, T=250)[1] >= 0.95 for k in range(20))
        self.assertLessEqual(admitted, 1)

    def test_a_strong_planted_edge_is_found(self):
        found = 0
        for k in range(10):
            best, dsr = self._family(5000 + k, planted_annual_sharpe=3.0)
            found += best == 0 and dsr >= 0.95
        self.assertGreaterEqual(found, 7)


if __name__ == "__main__":
    unittest.main()
