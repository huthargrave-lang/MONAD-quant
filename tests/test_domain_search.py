"""tools/domain_search.py: the counted cost stress (``stress``)."""
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

import domain_search  # noqa: E402
from src.research import trials  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402
from src.research.daily_domains import DOMAINS, Context  # noqa: E402


def snapshot():
    dates = pd.bdate_range("2014-01-02", "2018-12-31")
    rng = np.random.default_rng(9)
    close = pd.DataFrame({c: 30 * np.exp(np.cumsum(rng.normal(0, 0.012, len(dates))))
                          for c in ("SPY", "GDX", "GLD")}, index=dates)
    return Snapshot(sha="c" * 64, dates=dates, assets=tuple(close.columns), open=close.shift(1).fillna(close.iloc[0]),
                    close=close, dist=close * 0.0, dtb3=pd.Series(1.0, index=dates), manifest={})


class Stress(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(trials, "LEDGER_DIR", Path(self._tmp.name) / "ledger")
        self.patch.start()
        self.domain, self.ctx = DOMAINS["miner_metal_ratio"], Context(snap=snapshot())

    def tearDown(self):
        self.patch.stop()
        self._tmp.cleanup()

    def test_it_is_counted_reused_and_costlier_than_the_base_run(self):
        domain_search.run(self.domain, self.ctx, "v1")
        base = domain_search.report(self.domain, self.ctx)["rows"][0]
        out = domain_search.stress(self.domain, self.ctx, "v1", multiple=2.0)
        (only,) = out.values()
        self.assertLess(only["active_ann"], base["active_return_ann"])
        n = len(list(trials.iter_trials()))
        self.assertEqual(domain_search.stress(self.domain, self.ctx, "v1", multiple=2.0), out)
        self.assertEqual(len(list(trials.iter_trials())), n, "a recorded stress must be reused, not re-run")
        stressed = [r for r in trials.iter_trials() if (r.spec.get("params") or {}).get("cost_multiple") == 2.0]
        self.assertEqual(len(stressed), 2)                        # the benchmark and the one point
        # The base report is unchanged by the stress runs (it reads cost_multiple 1 only).
        self.assertEqual(domain_search.report(self.domain, self.ctx)["rows"][0]["key"], base["key"])

    def test_a_non_positive_multiple_is_refused(self):
        with self.assertRaises(ValueError):
            domain_search.stress(self.domain, self.ctx, "v1", multiple=0.0)


if __name__ == "__main__":
    unittest.main()
