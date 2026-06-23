"""
Regression test for the backtest plot path in src/backtest/runner.run_backtest.

The plot branch (`if plot and _HAS_MPL:`) called _plot_results() with a positional
`drawdown` argument that was never defined in run_backtest's scope (only the scalar
`max_drawdown` exists). On any machine where matplotlib IS installed and plot=True
(the default), that raised `NameError: name 'drawdown' is not defined` at the very
end of the run — after all computation/printing. The Pi/live venv omits matplotlib
(`_HAS_MPL=False`), so the dead branch hid the bug.

This test forces the plot branch on with a stub _plot_results whose signature
mirrors the corrected call. It does NOT require matplotlib:
  * Old buggy code -> NameError on `drawdown` at the call site -> test fails.
  * A future call/signature arity drift -> TypeError into the stub -> test fails.
  * Fixed code -> stub receives exactly the documented args -> passes.
"""
import unittest
import numpy as np
import pandas as pd

import src.backtest.runner as runner


def _synthetic(n=500):
    """Hourly OHLCV that reliably produces trades (mirrors test_sweep_costs)."""
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    rng = np.random.default_rng(7)
    steps = rng.normal(0, 0.004, n).cumsum()
    close = 100 * (1 + 0.15 * np.sin(np.linspace(0, 18, n)) + steps)
    close = np.maximum(close, 1.0)
    high = close * (1 + rng.uniform(0, 0.004, n))
    low = close * (1 - rng.uniform(0, 0.004, n))
    return pd.DataFrame({"open": (high + low) / 2, "high": high, "low": low,
                         "close": close, "volume": rng.integers(1_000, 50_000, n)},
                        index=idx)


class TestRunBacktestPlotPath(unittest.TestCase):
    def test_plot_branch_does_not_raise_name_error(self):
        captured = {}

        # Signature mirrors the corrected _plot_results — an extra/missing
        # positional at the call site would raise TypeError here.
        def fake_plot(equity, trade_returns, trades_df, df_price, initial_capital):
            captured["called"] = True
            captured["n_equity"] = len(equity)

        orig_plot = runner._plot_results
        orig_has_mpl = runner._HAS_MPL
        runner._plot_results = fake_plot
        runner._HAS_MPL = True  # force the plot branch on without matplotlib
        try:
            res = runner.run_backtest(
                df=_synthetic(), initial_capital=100_000,
                target_gain_pct=0.01, stop_loss_pct=0.005, require_signals=1,
                timeframe="hourly", plot=True, backtest_mode="realistic",
            )
        finally:
            runner._plot_results = orig_plot
            runner._HAS_MPL = orig_has_mpl

        self.assertTrue(res, "synthetic must produce trades or this test is vacuous")
        self.assertTrue(captured.get("called"),
                        "plot branch was not exercised — _plot_results never ran")


if __name__ == "__main__":
    unittest.main()
