"""
Tests for the engine's evaluation guard (src/strategy/counted.py): the runtime trial
token that closes the red team's counting evasions (decision-debate Q2).

Each attack the AST guard could not stop is exercised against the REAL engine entry
points: a bare call, an aliased call, a call from a script outside the repository, and
one trial trying to authorise many evaluations.
"""
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import trials  # noqa: E402
from src.strategy import counted  # noqa: E402
from src.strategy.engine import compute_trade_returns  # noqa: E402


def _trades(n=40, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    idx = pd.date_range("2024-01-02 14:30", periods=n, freq="h")
    df = pd.DataFrame({"open": close, "high": close * 1.003, "low": close * 0.997,
                       "close": close, "volume": 1e6}, index=idx)
    df["entry_signal"] = 0
    df.iloc[::5, df.columns.get_loc("entry_signal")] = 1
    return df


def _evaluate():
    return compute_trade_returns(_trades(), target_gain_pct=0.01, stop_loss_pct=0.005)


class TheGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name)

    def tearDown(self):
        counted._TOKEN.set(None)
        self._tmp.cleanup()

    def test_a_bare_evaluation_is_refused(self):
        with self.assertRaises(counted.UncountedEvaluationError):
            _evaluate()

    def test_an_aliased_evaluation_is_refused(self):
        """Round-1 attack 1b: getattr/aliasing hid the call from the AST scan."""
        import src.strategy.engine as eng
        fn = getattr(eng, "compute_" + "trade_returns")
        with self.assertRaises(counted.UncountedEvaluationError):
            fn(_trades(), target_gain_pct=0.01, stop_loss_pct=0.005)

    def test_one_trial_authorises_exactly_one_evaluation(self):
        with trials.open_run(producer="t", family="f", ledger_dir=self.ledger) as run:
            t = run.begin(params={"k": 1})
            _evaluate()
            with self.assertRaises(counted.UncountedEvaluationError):
                _evaluate()                    # the attack: one begin, many backtests
            t.complete(metrics={})
            t2 = run.begin(params={"k": 2})
            _evaluate()                        # a new trial, a new token
            t2.complete(metrics={})

    def test_nested_evaluations_pass(self):
        from src.backtest.runner import run_backtest  # calls compute_trade_returns inside
        with trials.open_run(producer="t", family="f", ledger_dir=self.ledger) as run:
            t = run.begin(params={})
            df = _trades(200).drop(columns=["entry_signal"])
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                run_backtest(df=df, target_gain_pct=0.01, stop_loss_pct=0.005,
                             timeframe="hourly", plot=False)
            t.complete(metrics={})

    def test_a_trial_that_never_evaluated_blocks_the_next_begin(self):
        with trials.open_run(producer="t", family="f", ledger_dir=self.ledger) as run:
            run.begin(params={"k": 1})
            with self.assertRaises(counted.UncountedEvaluationError):
                run.begin(params={"k": 2})
        # closing the run abandoned the open trial and cleared its token
        self.assertIsNone(counted._TOKEN.get())

    def test_outcome_clears_by_identity_not_reset(self):
        """ContextVar.reset would restore a stale token when trials end out of order."""
        with trials.open_run(producer="t", family="f", ledger_dir=self.ledger) as run:
            a = run.begin(params={"k": 1})
            _evaluate()
            b = run.begin(params={"k": 2})     # a is spent, so b may begin
            a.complete(metrics={})             # must NOT clear b's token
            self.assertIs(counted._TOKEN.get(), b._token)
            _evaluate()
            b.complete(metrics={})
            self.assertIsNone(counted._TOKEN.get())

    def test_uncounted_needs_a_reason_and_an_allowed_caller(self):
        with self.assertRaises(counted.UncountedEvaluationError):
            with counted.uncounted("short"):
                pass
        with counted.uncounted("allowed here because this file is under tests/"):
            _evaluate()

    def test_a_script_outside_the_repo_cannot_bypass(self):
        """Round-1 attack 1c: /tmp scripts were never scanned. Now they cannot run the
        engine, and cannot grant themselves uncounted()."""
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "peek.py"
            script.write_text(textwrap.dedent(f"""
                import sys
                sys.path.insert(0, {str(REPO)!r})
                from src.strategy import counted
                try:
                    with counted.uncounted("I just want to peek at recent bars"):
                        pass
                    print("BYPASSED")
                except counted.UncountedEvaluationError:
                    print("REFUSED")
            """))
            out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
            self.assertEqual(out.stdout.strip(), "REFUSED", out.stderr)

    def test_the_live_bot_does_not_import_the_research_package(self):
        """The guard sits in src/strategy/ so live's import closure gains one small file,
        not the research package (tests/test_armed_closure.py pins the drift oracle)."""
        sys.path.insert(0, str(REPO / "tools"))
        import armed_closure
        closure = armed_closure.closure(REPO)
        self.assertIn("src/strategy/counted.py", closure)
        self.assertFalse([p for p in closure if p.startswith("src/research/")])


if __name__ == "__main__":
    unittest.main()
