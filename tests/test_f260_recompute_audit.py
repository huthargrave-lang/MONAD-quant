"""A detector for values that are computed twice with different parameters — F260.

F145's dead-lever census asks *"is this knob read?"* and misses the two most expensive
defects in `src/signals/`, because those knobs **are** read. `engine.py` forwards
`rsi_period`; `add_momentum_features` honours it and writes a correct `df["rsi"]`.
Everything a reader would inspect is right. The gate still ignores it, because
`momentum_signal()` calls `compute_rsi(close)` again at the default period.

`tools/recompute_audit.py` asks the other question — *does the displayed value equal the
governing one?* — and detects the mechanical signature of a No: a second call to a
`compute_*` that also has a canonical `df[col] = ...` assignment, supplying fewer
parameters than that assignment does.

On this repository it finds exactly two, both in `momentum.py:38-39`:

    compute_rsi   drops `period`             -> gate runs at the default, column at 7
    compute_macd  drops `fast, slow, signal` -> gate runs at defaults, column at 6/13/4

Every hourly mode configures non-default values for both, so on every hourly mode the
indicators that are logged, charted and swept are not the indicators that decide trades.
`config.py` already carries a *third* wrong diagnosis of this — `MACD_FAST_TQQQ_HOURLY = 6
# DEAD LEVER (confirmed: same as QQQ/BTC hourly)` — attributing the deadness to a
coincidence between modes rather than to the knob never being read.

**The detector's own first version was wrong**, and the way it was wrong is worth keeping.
It counted keyword arguments only, and reported a third finding: `compute_bb_width` inside
`volatility_regime()`. That call forwards `window` POSITIONALLY. Counting keywords alone
cannot see it. Binding positional arguments against the callee's signature removed the
false positive and left the two real ones — and it is why `volume_signal()`, which
recomputes its inputs in exactly the same shape as `momentum_signal()`, is correctly
silent: it forwards its parameters.

Guards are bidirectional. They fail if either divergence is fixed (good news — supersede
this node, do not retune the count), if a NEW one appears, if the detector stops
distinguishing positional forwarding from omission, or if it starts flagging the benign
duplicates.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import recompute_audit as ra  # noqa: E402


class TheDetectorFindsTheKnownDivergencesTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.found = ra.scan()
        cls.div = [f for f in cls.found if f["severity"] == "divergent"]

    def test_it_finds_exactly_the_two_known_divergences(self):
        got = {(f["producer"], tuple(f["missing_kwargs"])) for f in self.div}
        self.assertEqual(
            got,
            {("compute_rsi", ("period",)),
             ("compute_macd", ("fast", "signal", "slow"))},
            "the divergence set changed — if one was FIXED, supersede F260 rather than "
            "editing this expectation; if a NEW one appeared, it needs its own analysis")

    def test_both_are_the_momentum_signal_recomputations(self):
        for f in self.div:
            with self.subTest(producer=f["producer"]):
                self.assertEqual(f["recomputed_in"], "momentum_signal")
                self.assertEqual(f["canonical_func"], "add_momentum_features")

    def test_the_columns_they_diverge_from_are_named(self):
        cols = {c for f in self.div for c in f["columns"]}
        self.assertIn("rsi", cols)
        self.assertIn("macd_hist", cols,
                      "macd_hist is the column the entry gate actually compares")


class ThePositionalForwardIsNotAFindingTests(unittest.TestCase):
    """The detector's own first false positive, kept as a regression."""

    def test_bb_width_is_benign_because_window_is_forwarded_positionally(self):
        hits = [f for f in ra.scan() if f["producer"] == "compute_bb_width"]
        self.assertTrue(hits, "compute_bb_width is no longer recomputed at all")
        for f in hits:
            self.assertEqual(
                f["severity"], "duplicate",
                "compute_bb_width is flagged divergent again — the detector has stopped "
                "binding positional arguments and is back to counting keywords")

    def test_volume_signal_recomputes_but_forwards_its_parameters(self):
        """Same structural shape as momentum_signal; correctly silent."""
        hits = [f for f in ra.scan() if f["recomputed_in"] == "volume_signal"]
        self.assertTrue(hits, "volume_signal no longer recomputes its inputs")
        self.assertTrue(all(f["severity"] == "duplicate" for f in hits))


class TheDetectorCanSayBothThingsTests(unittest.TestCase):
    """Non-vacuity on synthetic source: a detector that only ever says one thing is not
    a detector. Both directions are planted and checked."""

    GOOD = '''
import pandas as pd
def compute_thing(prices, window=20):
    return prices.rolling(window).mean()
def derived(df, window=20):
    return compute_thing(df["close"], window)
def add_features(df, window=20):
    df["thing"] = compute_thing(df["close"], window=window)
    return df
'''
    BAD = '''
import pandas as pd
def compute_thing(prices, window=20):
    return prices.rolling(window).mean()
def derived(df):
    return compute_thing(df["close"])
def add_features(df, window=20):
    df["thing"] = compute_thing(df["close"], window=window)
    return df
'''

    def _scan(self, source):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "mod.py"
            p.write_text(source, encoding="utf-8")
            return ra.scan([str(d)])

    def test_a_planted_divergence_is_caught(self):
        div = [f for f in self._scan(self.BAD) if f["severity"] == "divergent"]
        self.assertEqual(len(div), 1, "a planted parameter-dropping recompute was missed")
        self.assertEqual(div[0]["missing_kwargs"], ["window"])
        self.assertEqual(div[0]["columns"], ["thing"])

    def test_a_correct_positional_forward_is_not_caught(self):
        div = [f for f in self._scan(self.GOOD) if f["severity"] == "divergent"]
        self.assertEqual(
            div, [], "a correctly-forwarded recompute was reported as divergent")

    def test_a_compute_with_no_canonical_column_is_ignored(self):
        """Scope: helpers that never back a column are not this tool's business."""
        src = ('def compute_thing(prices, window=20):\n    return prices\n'
               'def user(df):\n    return compute_thing(df["close"])\n')
        self.assertEqual(self._scan(src), [],
                         "a compute_* backing no column was reported")


class TheConfiguredValuesMakeItBiteTests(unittest.TestCase):
    """A divergence only matters if config differs from the function default."""

    def test_every_hourly_mode_configures_non_default_macd_parameters(self):
        import config
        from src.signals.momentum import compute_macd
        import inspect
        defaults = {k: v.default for k, v in
                    inspect.signature(compute_macd).parameters.items()
                    if v.default is not inspect.Parameter.empty}
        for mode in ("HOURLY", "QQQ_HOURLY", "TQQQ_HOURLY", "SOXL_HOURLY",
                     "LABU_HOURLY", "TNA_HOURLY", "GDXU_HOURLY"):
            with self.subTest(mode=mode):
                configured = {
                    "fast": int(getattr(config, "MACD_FAST_" + mode)),
                    "slow": int(getattr(config, "MACD_SLOW_" + mode)),
                    "signal": int(getattr(config, "MACD_SIGNAL_" + mode)),
                }
                self.assertNotEqual(
                    configured,
                    {k: defaults[k] for k in configured},
                    "{} now configures the function defaults, so the MACD divergence "
                    "is latent rather than live for it".format(mode))

    def test_the_daily_default_mode_is_genuinely_unaffected(self):
        """Scope, so the finding is not inherited as 'every mode is broken'."""
        import config
        import inspect
        from src.signals.momentum import compute_macd
        d = {k: v.default for k, v in inspect.signature(compute_macd).parameters.items()
             if v.default is not inspect.Parameter.empty}
        self.assertEqual(
            (int(config.MACD_FAST), int(config.MACD_SLOW), int(config.MACD_SIGNAL)),
            (d["fast"], d["slow"], d["signal"]))


class TheCLIReportsUsefullyTests(unittest.TestCase):

    def test_it_exits_nonzero_while_divergences_exist(self):
        self.assertEqual(ra.main([]), 1,
                         "the CLI stopped signalling divergences through its exit code")

    def test_the_divergent_helper_matches_the_scan(self):
        self.assertEqual(
            len(ra.divergent()),
            len([f for f in ra.scan() if f["severity"] == "divergent"]))


if __name__ == "__main__":
    unittest.main()
