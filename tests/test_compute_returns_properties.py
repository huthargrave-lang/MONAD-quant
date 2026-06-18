"""
Property-based tests for compute_trade_returns (src/strategy/engine.py) — B9.

Example-based coverage lives in tests/test_execution_model.py. These complement
it by asserting invariants across *many* randomly generated price paths, catching
edge cases hand-written examples miss:

  * every exit_type is in the valid set
  * a recorded target_hit return == the target param; stop_hit == -stop;
    ambiguous (optimistic) == target  (the "recorded return == the chosen exit"
    invariant from the roadmap)
  * returns are always finite and bounded below by -1 (price can't go negative)
  * slippage shifts every return by exactly the slippage amount
  * the function is deterministic

hypothesis is optional (dev/CI dependency, see requirements-dev.txt); on the lean
Pi venv the import is absent, so the suite degrades to a single skipped test
rather than failing to collect (same convention as the fastapi/httpx dashboard test).
"""
import unittest

import numpy as np
import pandas as pd

from src.strategy.engine import compute_trade_returns

VALID_EXIT_TYPES = {"target_hit", "stop_hit", "ambiguous_same_bar",
                    "time_exit", "opposing_signal"}

try:
    from hypothesis import given, settings, strategies as st
    HAS_HYPOTHESIS = True
except ImportError:  # lean Pi venv
    HAS_HYPOTHESIS = False


if HAS_HYPOTHESIS:

    @st.composite
    def _price_path(draw, min_bars=5, max_bars=25):
        """A valid OHLCV frame with one entry signal at bar 0.

        Each bar has a flat body (open==close==center) and a random high/low
        range around it, guaranteeing low <= open/close <= high. The single
        entry fills at bar 1's open; exits are scanned from bar 2.
        """
        n = draw(st.integers(min_bars, max_bars))
        centers = draw(st.lists(
            st.floats(min_value=10, max_value=1000, allow_nan=False, allow_infinity=False),
            min_size=n, max_size=n,
        ))
        hr = draw(st.lists(st.floats(0.0, 0.08), min_size=n, max_size=n))
        lr = draw(st.lists(st.floats(0.0, 0.08), min_size=n, max_size=n))
        direction = draw(st.sampled_from([1, -1]))
        centers = np.array(centers, dtype=float)
        df = pd.DataFrame({
            "open": centers,
            "close": centers,
            "high": centers * (1 + np.array(hr)),
            "low": centers * (1 - np.array(lr)),
            "entry_signal": [direction] + [0] * (n - 1),
        }, index=pd.date_range("2024-01-01", periods=n, freq="D"))
        return df

    class TestComputeTradeReturnsProperties(unittest.TestCase):
        TARGET = 0.02
        STOP = 0.01

        @settings(max_examples=60, deadline=None)
        @given(df=_price_path())
        def test_exit_types_and_recorded_returns(self, df):
            res = compute_trade_returns(df, target_gain_pct=self.TARGET,
                                        stop_loss_pct=self.STOP, max_trade_bars=50)
            self.assertLessEqual(len(res), int((df["entry_signal"] != 0).sum()))
            for _, row in res.iterrows():
                et, r = row["exit_type"], row["return"]
                self.assertIn(et, VALID_EXIT_TYPES)
                self.assertTrue(np.isfinite(r))
                self.assertGreater(r, -1.0)            # price can't go below zero
                if et == "target_hit":
                    self.assertAlmostEqual(r, self.TARGET, places=9)
                elif et == "stop_hit":
                    self.assertAlmostEqual(r, -self.STOP, places=9)
                elif et == "ambiguous_same_bar":
                    # default worst_case_ambiguity=False -> optimistic (target)
                    self.assertAlmostEqual(r, self.TARGET, places=9)

        @settings(max_examples=40, deadline=None)
        @given(df=_price_path())
        def test_worst_case_ambiguity_records_stop(self, df):
            res = compute_trade_returns(df, target_gain_pct=self.TARGET,
                                        stop_loss_pct=self.STOP, max_trade_bars=50,
                                        worst_case_ambiguity=True)
            for _, row in res.iterrows():
                if row["exit_type"] == "ambiguous_same_bar":
                    self.assertAlmostEqual(row["return"], -self.STOP, places=9)

        @settings(max_examples=40, deadline=None)
        @given(df=_price_path())
        def test_slippage_shifts_every_return(self, df):
            slip = 0.0007
            base = compute_trade_returns(df, self.TARGET, self.STOP, max_trade_bars=50)
            slipped = compute_trade_returns(df, self.TARGET, self.STOP, max_trade_bars=50,
                                            slippage_pct=slip)
            self.assertEqual(list(base["exit_type"]), list(slipped["exit_type"]))
            for b, s in zip(base["return"], slipped["return"]):
                self.assertAlmostEqual(s, b - slip, places=9)

        @settings(max_examples=40, deadline=None)
        @given(df=_price_path())
        def test_deterministic(self, df):
            a = compute_trade_returns(df, self.TARGET, self.STOP, max_trade_bars=50)
            b = compute_trade_returns(df, self.TARGET, self.STOP, max_trade_bars=50)
            pd.testing.assert_frame_equal(a, b)

else:

    class TestComputeTradeReturnsProperties(unittest.TestCase):
        @unittest.skip("hypothesis not installed (dev/CI dependency)")
        def test_requires_hypothesis(self):
            pass


if __name__ == "__main__":
    unittest.main()
