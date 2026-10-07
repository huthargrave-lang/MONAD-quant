"""
Property-based tests for compute_trade_returns (src/strategy/engine.py) — B9.

Example-based coverage lives in tests/test_execution_model.py. These complement
it by asserting invariants across *many* randomly generated price paths, catching
edge cases hand-written examples miss:

  * every exit_type is in the valid set
  * a recorded target_hit return == the target param; stop_hit == -stop;
    ambiguous == -stop by default (stop-first) and == target only in the upper-bound
    branch (worst_case_ambiguity=False); a gap or time exit == the move to the OPEN of
    its exit bar; a truncated time exit == the move to the last close  (the "recorded
    return == the chosen exit" invariant from the roadmap)
  * returns are always finite; a LONG's return is bounded below by -1 (price can't go
    negative). A short has no such bound: under ENGINE_VERSION 3 a gap through a short's
    stop fills at the open, so a >100% gap books a loss beyond -1 (F241 recorded the
    same breach on the opposing-exit branch).
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

from tests._engine_uncounted import uncounted_module  # noqa: E402

# Engine arithmetic, not a strategy evaluation: runs outside the trial ledger
# (src/strategy/counted.py).
setUpModule, tearDownModule = uncounted_module("property tests of compute_trade_returns arithmetic on synthetic bars")

# ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md) adds gap_stop / gap_target (an
# open at or through a level fills at the open) and time_exit_truncated (end of data).
VALID_EXIT_TYPES = {"target_hit", "stop_hit", "ambiguous_same_bar",
                    "gap_stop", "gap_target", "time_exit", "time_exit_truncated",
                    "opposing_signal"}

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
        entry fills at bar 1's open; under ENGINE_VERSION 3 the bracket is scanned
        from bar 1 itself (the entry bar).
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
            """Every recorded return equals the exit the engine chose.

            Re-pinned for ENGINE_VERSION 3 (docs/research/ENGINE_V3_QUESTION.md): the
            default is now stop-first (an ambiguous bar records -stop, not the target),
            and the v3 exit types are covered: gap_stop / gap_target / time_exit record
            the move to the OPEN of the exit bar, time_exit_truncated the move to the
            last close. entry_time / exit_time locate those prices. The -1 lower bound is
            asserted for longs only: v3's gap_stop makes a short's breach of -1 reachable
            (a short at 10 whose stop bar opens at 20 books exactly -1.0), and that is
            the correct short-side arithmetic, not an engine defect.
            """
            res = compute_trade_returns(df, target_gain_pct=self.TARGET,
                                        stop_loss_pct=self.STOP, max_trade_bars=50)
            self.assertLessEqual(len(res), int((df["entry_signal"] != 0).sum()))
            direction = int(df["entry_signal"].iloc[0])
            for _, row in res.iterrows():
                et, r = row["exit_type"], row["return"]
                self.assertIn(et, VALID_EXIT_TYPES)
                self.assertTrue(np.isfinite(r))
                if direction == 1:                     # a long-only fact (F241)
                    self.assertGreater(r, -1.0)        # price can't go below zero
                # the fill is the open of the bar after the signal, and no exit precedes it
                self.assertEqual(df.index.get_loc(row["entry_time"]),
                                 df.index.get_loc(row["timestamp"]) + 1)
                self.assertGreaterEqual(row["exit_time"], row["entry_time"])
                entry = df.at[row["entry_time"], "open"]
                if et == "target_hit":
                    self.assertAlmostEqual(r, self.TARGET, places=9)
                elif et == "stop_hit":
                    self.assertAlmostEqual(r, -self.STOP, places=9)
                elif et == "ambiguous_same_bar":
                    # default worst_case_ambiguity=True -> stop-first
                    self.assertAlmostEqual(r, -self.STOP, places=9)
                elif et in ("gap_stop", "gap_target", "time_exit"):
                    px = df.at[row["exit_time"], "open"]
                    self.assertAlmostEqual(r, direction * (px - entry) / entry, places=9)
                    if et == "gap_stop":                # an open at or through the stop
                        self.assertLessEqual(r, -self.STOP + 1e-12)
                    elif et == "gap_target":            # an open at or through the target
                        self.assertGreaterEqual(r, self.TARGET - 1e-12)
                    else:
                        self.assertGreater(r, -self.STOP - 1e-12)
                        self.assertLess(r, self.TARGET + 1e-12)
                elif et == "time_exit_truncated":
                    self.assertEqual(row["exit_time"], df.index[-1])
                    px = df.at[row["exit_time"], "close"]
                    self.assertAlmostEqual(r, direction * (px - entry) / entry, places=9)

        @settings(max_examples=40, deadline=None)
        @given(df=_price_path())
        def test_upper_bound_ambiguity_records_target(self, df):
            """worst_case_ambiguity=False (the upper_bound mode only) books the target."""
            res = compute_trade_returns(df, target_gain_pct=self.TARGET,
                                        stop_loss_pct=self.STOP, max_trade_bars=50,
                                        worst_case_ambiguity=False)
            for _, row in res.iterrows():
                if row["exit_type"] == "ambiguous_same_bar":
                    self.assertAlmostEqual(row["return"], self.TARGET, places=9)

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
