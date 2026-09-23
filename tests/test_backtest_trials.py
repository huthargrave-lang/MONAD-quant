"""
Tests for src/research/backtest_trials.py (backtest result -> ledger outcome) and
trials.open_process_run (a run that lives as long as a top-level script).

The adapter is the one definition every producer shares, so these pin the mapping
itself: a zero-trade backtest is a counted losing trial, an error is an error, an
unencodable result is still counted, and a restricted (holdout/OOS) outcome drops
the full-run numbers that no longer describe it.
"""
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import config  # noqa: E402
from src.research import backtest_trials as bt  # noqa: E402
from src.research import trials  # noqa: E402


def _returns(values, start="2024-01-02 10:30"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="h"))


def _result(values):
    r = _returns(values)
    return {"total_trades": len(r), "win_rate": float((r > 0).mean()), "total_return": 0.01,
            "sharpe_ratio": 1.5, "max_drawdown": -0.02, "trades_per_year": 100.0,
            "trade_returns": r, "equity_curve": pd.Series([1.0])}


class OutcomeMapping(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ctx = trials.open_run(producer="t", family="f", ledger_dir=Path(self._tmp.name))
        self.run = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)
        self._tmp.cleanup()

    def outcome(self):
        rows = [json.loads(l) for l in self.run.path.read_text().splitlines()]
        return [r for r in rows if r["type"] == "outcome"][-1]

    def test_zero_trades_is_a_counted_losing_trial_not_an_error(self):
        for empty in ({}, None):
            bt.record_backtest(self.run.begin(params={"k": str(empty)}), empty)
            out = self.outcome()
            self.assertEqual((out["status"], out["metrics"]), ("ok", {"total_trades": 0}))

    def test_error_result_is_an_error_outcome(self):
        bt.record_backtest(self.run.begin(params={}), {"error": "boom"})
        out = self.outcome()
        self.assertEqual((out["status"], out["error"]), ("error", "boom"))

    def test_full_result_keeps_headline_metrics_and_returns(self):
        bt.record_backtest(self.run.begin(params={}), _result([0.01, -0.005, 0.02]))
        out = self.outcome()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["metrics"]["total_trades"], 3)
        self.assertEqual(out["n_returns"], 3)
        self.assertNotIn("equity_curve", out["metrics"])

    def test_unencodable_result_is_still_counted(self):
        bt.record_backtest(self.run.begin(params={}), _result([0.01, float("nan")]))
        out = self.outcome()
        self.assertEqual(out["status"], "error")
        self.assertIn("unrecordable", out["error"])

    def test_restricted_outcome_drops_full_run_numbers(self):
        res = _result([0.01, -0.01, 0.02, 0.03])
        cut = res["trade_returns"].index[2]
        bt.record_backtest(self.run.begin(params={}), res, evaluated_from=cut)
        out = self.outcome()
        self.assertEqual(out["metrics"], {"total_trades": 2, "win_rate": 1.0})
        self.assertEqual(out["n_returns"], 2)

    def test_restriction_is_inclusive_at_the_boundary(self):
        res = _result([0.01, 0.02])
        scored = bt.scored_from(res, res["trade_returns"].index[1])
        self.assertEqual(scored["total_trades"], 1)


class Specs(unittest.TestCase):
    def test_engine_spec_reads_config_at_call_time(self):
        mode = "ZZZ_TEST_HOURLY"
        setattr(config, f"RSI_OVERSOLD_{mode}", 30)
        try:
            a = bt.engine_spec(mode, timeframe="hourly", target=0.01, stop=0.005,
                               backtest_mode="realistic", slippage_pct=0.001)
            setattr(config, f"RSI_OVERSOLD_{mode}", 31)
            b = bt.engine_spec(mode, timeframe="hourly", target=0.01, stop=0.005,
                               backtest_mode="realistic", slippage_pct=0.001)
        finally:
            delattr(config, f"RSI_OVERSOLD_{mode}")
        self.assertEqual(a["mode_constants"][f"RSI_OVERSOLD_{mode}"], 30)
        self.assertNotEqual(trials.spec_hash(a), trials.spec_hash(b))

    def test_engine_spec_is_hashable(self):
        spec = bt.engine_spec("TQQQ_HOURLY", timeframe="hourly", target=0.01, stop=0.005,
                              backtest_mode="realistic", slippage_pct=None,
                              settings={"trade_hours": (9, 16)})
        self.assertRegex(trials.spec_hash(spec), r"^[0-9a-f]{64}$")

    def test_every_hourly_tool_shares_one_family_per_ticker(self):
        self.assertEqual(bt.mr_hourly_family("tqqq"), "long_only_rsi_vwap_mr_hourly:TQQQ")
        self.assertEqual(bt.mr_family("TQQQ", "hourly"), bt.mr_hourly_family("TQQQ"))
        self.assertEqual(bt.MR_HOURLY_STRATEGY, bt.mr_hourly_family("X").split(":")[0])


class ProcessRun(unittest.TestCase):
    """open_process_run closes at interpreter exit, reflecting how the process ended."""

    def _run_script(self, body):
        with tempfile.TemporaryDirectory() as td:
            script = textwrap.dedent(f"""
                import sys
                sys.path.insert(0, {str(REPO)!r})
                from pathlib import Path
                from src.research.trials import open_process_run
                run = open_process_run(producer="t", family="f", ledger_dir=Path({td!r}))
                run.begin(params={{"k": 1}}).complete(metrics={{}})
                pending = run.begin(params={{"k": 2}})
            """) + textwrap.dedent(body)
            subprocess.run([sys.executable, "-c", script], capture_output=True)
            shard = next(Path(td).glob("TR-*.jsonl"))
            report = trials.verify_shard(shard)
            return report

    def test_normal_exit_closes_complete_and_abandons_the_pending_trial(self):
        r = self._run_script("")
        self.assertEqual(r.errors, [])
        self.assertEqual((r.close_status, r.intents), ("complete", 2))
        self.assertEqual(r.outcomes, {"ok": 1, "abandoned": 1})

    def test_uncaught_exception_closes_aborted(self):
        r = self._run_script("raise RuntimeError('boom')\n")
        self.assertEqual(r.errors, [])
        self.assertEqual(r.close_status, "aborted")

    def test_keyboard_interrupt_closes_aborted(self):
        r = self._run_script("raise KeyboardInterrupt\n")
        self.assertEqual(r.close_status, "aborted")

    def test_sys_exit_closes_complete(self):
        r = self._run_script("sys.exit(0)\n")
        self.assertEqual(r.close_status, "complete")


if __name__ == "__main__":
    unittest.main()
