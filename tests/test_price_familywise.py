"""
Gate rules v2, price profile (tools/admit.py ``price_family_gate``; decision debate
2026-10-06, docs/research/DEFLATION_RULE_QUESTION.md (iii), (vi)): the familywise matrix is
built from the ledger's mark-to-market series, and everything it cannot hold is charged in
m. The stage itself stays BLOCKED until the committed sparse-basis size study meets the
trigger, and the ratification flag cannot be flipped without that evidence.
"""
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

import admit  # noqa: E402
from src.backtest.runner import run_backtest  # noqa: E402
from src.research import backtest_trials as bt, trials  # noqa: E402
from tests._engine_uncounted import uncounted_module  # noqa: E402

setUpModule, tearDownModule = uncounted_module("price familywise gate on synthetic bars")


def tape(n=900, seed=7):
    idx = pd.date_range("2025-01-06 14:30", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 100 * (1 + 0.15 * np.sin(np.linspace(0, 24, n)) + rng.normal(0, 0.004, n).cumsum())
    close = np.maximum(close, 1.0)
    high, low = close * (1 + rng.uniform(0, 0.004, n)), close * (1 - rng.uniform(0, 0.004, n))
    return pd.DataFrame({"open": (high + low) / 2, "high": high, "low": low, "close": close,
                         "volume": rng.integers(1_000, 50_000, n)}, index=idx)


def backtest(df, target):
    return run_backtest(df=df.copy(), target_gain_pct=target, stop_loss_pct=0.005,
                        require_signals=1, timeframe="hourly", plot=False,
                        backtest_mode="realistic")


class TheMatrixAndTheCharge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.ledger = Path(cls._tmp.name)
        cls.patch = mock.patch.object(trials, "LEDGER_DIR", cls.ledger)
        cls.patch.start()
        df, other = tape(), tape(seed=8)
        data, other_data = bt.data_spec(df, "SYN", None), bt.data_spec(other, "SYN", None)
        with trials.open_run(producer="sweep.py", family="fam:syn") as run:
            for target in (0.006, 0.008, 0.010, 0.012):
                bt.record_backtest(run.begin(params={"target": target}, data=data), backtest(df, target))
            # the same point searched again later on this window: one member, not two
            bt.record_backtest(run.begin(params={"target": 0.006}, data=data), backtest(df, 0.006))
            # a point searched only on other bars, and a spec that never produced a result
            bt.record_backtest(run.begin(params={"target": 0.020}, data=other_data),
                               backtest(other, 0.020))
            run.begin(params={"target": 0.030}, data=data).fail("boom")
        with trials.open_run(producer="tools/admit.py", family="fam:syn") as run:
            bt.record_backtest(run.begin(params={"target": 0.010}, data=data,
                                         extra={"stage": "admission:development"}),
                               backtest(df, 0.010))
        rows = trials.iter_trials()
        cls.searched = [r for r in rows if r.producer != "tools/admit.py"]
        cls.dev = next(r for r in rows if r.producer == "tools/admit.py")

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        cls._tmp.cleanup()

    def test_the_matrix_holds_each_on_window_point_once_plus_the_candidate(self):
        m, parts, g = admit.price_family_gate(self.searched, self.dev, prior=3, alpha=0.05)
        # 0.006, 0.008, 0.012 on window (0.010 is the candidate's own point), + candidate
        self.assertEqual(g.blocks[0]["family_size"] + len(g.dropped_zero_variance), 4)
        self.assertEqual(parts, {"prior_search_trials": 3, "unknown_specs": 1,
                                 "off_window_points": 1})
        self.assertEqual(m, 5)
        self.assertAlmostEqual(g.p_gate, min(1.0, g.worst_p * 6), places=12)
        self.assertGreaterEqual(g.n_boot, 5000)

    def test_it_is_deterministic(self):
        a = admit.price_family_gate(self.searched, self.dev, prior=0, alpha=0.05)[2]
        b = admit.price_family_gate(self.searched, self.dev, prior=0, alpha=0.05)[2]
        self.assertEqual(a.p_gate, b.p_gate)

    def test_a_candidate_without_marks_cannot_be_scored(self):
        bare = self.dev.__class__(**{**self.dev.__dict__, "series_shas": {}})
        with self.assertRaises(ValueError):
            admit.price_family_gate(self.searched, bare, prior=0, alpha=0.05)


class Ratification(unittest.TestCase):
    def test_the_price_switch_needs_a_passing_committed_study(self):
        """DEFLATION_RULE_QUESTION.md (vi): the price profile switches only when the
        sparse mark-to-market study's every size cell has a Wilson upper bound within the
        trigger over at least 1000 replications."""
        if not admit.PRICE_V2_RATIFIED:
            return
        study = json.loads(admit.PRICE_V2_EVIDENCE.read_text())
        self.assertIn("mark-to-market", study["basis"])
        for row in study["size"]:
            self.assertGreaterEqual(row["reps"], 1000)
            self.assertLessEqual(row["wilson_upper"], study["trigger"], row)
        self.assertLessEqual(study["trigger"], 0.075)

    def test_unratified_the_stage_blocks(self):
        self.assertFalse(admit.PRICE_V2_RATIFIED,
                         "the sparse-basis study did not meet the trigger; see "
                         "docs/research/DEFLATION_RULE_QUESTION.md")


if __name__ == "__main__":
    unittest.main()
