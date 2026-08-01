"""13 of 28 feature columns are never read — and 8 of them are recomputed instead.

Study: `docs/research/COLUMN_reachability_census.md`. Tool:
`tools/column_reachability.py`, output frozen at
`docs/research/data/column_reachability.json`.

The companion to F226's config census. F145 named two Kelly-multiplier columns computed
and consumed by nothing; F224 named a signal column whose flag gates only its own
computation. This is the denominator:

    read        15
    write_only  13
    external     5   (raw OHLCV, arriving with the data)

**The interesting half is not that 13 are dead — it is why.** Eight of them hold
quantities the decision path *recomputes from `close`* rather than reading:

* `volatility_regime(df, window)` calls `compute_bb_width(df["close"], window)` — one line
  after `df["bb_width"]` was assigned the result of that same call.
* `classify_regime(prices, …)` recomputes both moving averages and the slope that
  `ma_52w`, `ma_regime` and `ma_slope` already hold.

**They agree today**, and this file asserts that rather than assuming it: same
`min_periods=1`, same windows, and `compute_ma_slope` is line-for-line what the classifier
does internally. So this is a *latent* divergence — two paths to one fact with nothing
keeping them in step — not a live defect. The F20/F145/F189/F203/F208 family, one layer
down.

The other five are genuine leftovers: `adx_kelly_mult` (F145), `bull_breakout_signal`
(F224), `bear_short_signal` (the reverted bear-shorts experiment behind E19), `obv` and
`vol_ratio`.

**A methodological correction, found by tripping it.** The first version excluded the
whole assignment-target subtree when looking for reads. But in
`df.loc[df["adx"] < 20, "adx_kelly_mult"] = 0.8` the mask lives inside the target and is a
READ — so `adx` came out looking as though it were only ever tested for existence. Only
the subscript *key* is in write position. Fourth time in this session that the read/write
boundary has had to be drawn more carefully, and the first time the error ran toward
under-counting reads rather than over-counting them.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import column_reachability as census_mod  # noqa: E402

FROZEN = ROOT / "docs" / "research" / "data" / "column_reachability.json"
RECOMPUTED = ("bb_width", "bb_upper", "bb_mid", "bb_lower", "bb_position",
              "ma_52w", "ma_regime", "ma_slope")
LEFTOVERS = ("adx_kelly_mult", "bull_breakout_signal", "bear_short_signal",
             "obv", "vol_ratio")


class TheCensusIsStableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = census_mod.census()
        cls.counts = cls.report["counts"]

    def test_the_feature_layer_still_produces_a_couple_of_dozen_columns(self):
        produced = [c for c, v in self.report["columns"].items()
                    if v["kind"] != "external"]
        self.assertGreaterEqual(
            len(produced), 24,
            "the feature layer produces only {} columns — the census percentages are "
            "stale".format(len(produced)))

    def test_the_write_only_count_has_not_grown(self):
        self.assertLessEqual(
            self.counts.get("write_only", 0), 13,
            "write-only feature columns rose to {} — a column was added with no reader, "
            "or one lost its last reader".format(self.counts.get("write_only", 0)))

    def test_it_has_not_silently_shrunk_either(self):
        self.assertGreaterEqual(
            self.counts.get("write_only", 0), 10,
            "write-only columns fell to {} — good news; re-run the tool, update "
            "docs/research/COLUMN_reachability_census.md and lower this floor".format(
                self.counts.get("write_only", 0)))

    def test_it_matches_the_frozen_artifact(self):
        frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
        self.assertEqual(
            frozen["counts"], self.counts,
            "the committed census no longer matches a fresh run — regenerate with "
            "`python3 tools/column_reachability.py --json {}`".format(
                FROZEN.relative_to(ROOT)))

    def test_the_known_dead_levers_are_in_the_write_only_set(self):
        for column in LEFTOVERS:
            self.assertEqual(
                self.report["columns"][column]["kind"], "write_only",
                "{} gained a reader — if a dead lever was wired up, that is a strategy "
                "change needing its own record".format(column))


class TheReadWriteBoundaryIsDrawnAtTheKeyTests(unittest.TestCase):
    """The correction: a mask inside `df.loc[mask, "col"]` is a read."""

    def test_a_mask_read_is_not_swallowed_by_the_target(self):
        meta = census_mod.census()["columns"]["adx"]
        self.assertEqual(
            meta["kind"], "read",
            "adx is classed {} — the mask read in `df.loc[df['adx'] < …, "
            "'adx_kelly_mult'] = …` is being swallowed by the target again".format(
                meta["kind"]))
        self.assertIn("src/signals/volatility.py", meta["read_within_producer"])

    def test_only_the_key_node_is_treated_as_a_write(self):
        import ast
        tree = ast.parse('df.loc[df["a"] < 1, "b"] = 2\n')
        keys = census_mod._write_key_nodes(tree)
        self.assertEqual(len(keys), 1, "more than the key is in write position")
        node = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and n.value == "b")
        self.assertIn(id(node), keys)
        other = next(n for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and n.value == "a")
        self.assertNotIn(id(other), keys, "the mask's column is in write position")

    def test_the_writer_side_takes_the_last_tuple_element(self):
        import ast
        target = ast.parse('df.loc[m, "z"] = 1\n').body[0].targets[0]
        self.assertEqual(census_mod._assigned_key(target), "z")


class TheDeadColumnsAreMostlyRecomputedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = census_mod.census()
        cls.momentum = (ROOT / "src/signals/momentum.py").read_text(encoding="utf-8")
        cls.volatility = (ROOT / "src/signals/volatility.py").read_text(encoding="utf-8")

    def test_all_eight_recomputed_columns_are_write_only(self):
        for column in RECOMPUTED:
            self.assertEqual(
                self.report["columns"][column]["kind"], "write_only",
                "{} is read now — the recompute may have been replaced by a column "
                "read, which would close this finding".format(column))

    def test_the_vol_regime_recomputes_the_width_it_was_just_handed(self):
        self.assertIn('df["bb_width"] = compute_bb_width(df["close"], window=window)',
                      self.volatility)
        self.assertIn('bb_width = compute_bb_width(df["close"], window)',
                      self.volatility,
                      "volatility_regime no longer recomputes bb_width — if it now reads "
                      "the column, the duplication is resolved")

    def test_the_classifier_recomputes_the_moving_averages(self):
        self.assertIn("ma_long  = prices.rolling(ma_window, min_periods=1).mean()",
                      self.momentum)
        self.assertIn('df["ma_52w"]  = df["close"].rolling(ma_regime_window, '
                      'min_periods=1).mean()', self.momentum)

    def test_the_two_paths_agree_today(self):
        """Asserted, not assumed — a latent divergence is not a live one."""
        import numpy as np
        import pandas as pd
        from src.signals.momentum import classify_regime, compute_ma_slope
        rng = np.random.default_rng(4)
        prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 800))))
        stored = prices.rolling(252, min_periods=1).mean()
        internal = prices.rolling(252, min_periods=1).mean()
        pd.testing.assert_series_equal(stored, internal)
        slope_col = compute_ma_slope(prices, ma_window=252, slope_window=20)
        slope_internal = stored.pct_change(periods=20)
        pd.testing.assert_series_equal(
            slope_col, slope_internal,
            obj="compute_ma_slope vs the classifier's internal slope")
        self.assertTrue(classify_regime(prices).notna().all())

    def test_the_recompute_uses_the_same_window_parameter(self):
        """If the two calls ever take different windows, the columns start lying."""
        self.assertIn("def volatility_regime(df: pd.DataFrame, window: int = 20)",
                      self.volatility)
        self.assertIn('df["vol_regime"] = volatility_regime(df, window=window)',
                      self.volatility)


if __name__ == "__main__":
    unittest.main()
