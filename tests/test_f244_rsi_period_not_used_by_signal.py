"""The entry signal ignores RSI_PERIOD, and the logged RSI is not the one it used — F244.

`add_momentum_features()` computes the RSI column at the CONFIGURED period::

    df["rsi"] = compute_rsi(df["close"], period=rsi_period)      # momentum.py:164

`momentum_signal()` then recomputes its own, at the DEFAULT::

    rsi = compute_rsi(close)                                     # momentum.py:38, period=14
    long_cond = (rsi < rsi_oversold) & (hist > hist.shift(1))

It never reads `df["rsi"]`. `engine.py:35` passes `rsi_period=RSI_PERIOD_<MODE>`, which is
**7 for every hourly mode** (5 for BTC hourly). So on every hourly mode the strategy enters
on a 14-period RSI while the 7-period RSI is what gets written to `df["rsi"]`, logged by
`live/signals.py`, shown on the dashboard, and swept.

Two consequences, and the second is the one that bites:

1. `RSI_PERIOD_*` is a **dead lever for entries** — the F145 family. The config comments on
   four modes already noticed the lever does nothing and wrote down a *different* cause:
   `RSI_PERIOD_GDXU_HOURLY = 7  # DEAD LEVER (MACD is binding gate)`. The symptom was real,
   the diagnosis was wrong, and the wrong diagnosis is now enshrined in config.
2. The logged RSI **disagrees with the gate**. In the committed live archive, **18 of 322
   bars (5.6%)** show `momentum_signal == 1` while the logged RSI is ABOVE the oversold
   threshold — up to 86.8 against a threshold of 80. Read literally the log says the bot
   bought an overbought bar. It did not; it bought on an RSI nobody recorded.

This is what blocks exact shadow replay (H26): inverting the logged signal to recover the
unlogged MACD term is unsound precisely because the two RSI series differ. See
`tools/shadow_replay.py:entry_bounds`, which brackets instead of pretending.

**Not fixed here.** `src/signals/**` is fenced, and correcting it changes which bars produce
entries on every hourly mode — every backtest and sweep number moves. That needs explicit
approval and a re-sweep, exactly like F148's UTC gate. Recorded and guarded.

Guards are bidirectional: they fail if the signal starts honouring `rsi_period` (good news
— supersede this node rather than retune), if the configured periods stop differing from
the default, or if the live archive stops witnessing the divergence.
"""
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import config
from src.signals.momentum import add_momentum_features, compute_rsi

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = (ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"
           / "signal_history.jsonl")
DEFAULT_RSI_PERIOD = 14


def _synthetic(n=400, seed=7):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    return pd.DataFrame(
        {"open": close, "close": close, "high": close * 1.004, "low": close * 0.996,
         "volume": rng.integers(10**5, 5 * 10**5, n)},
        index=pd.date_range("2026-01-01", periods=n, freq="h"))


class TheSignalUsesADifferentRSIThanTheColumnTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.df = _synthetic()
        cls.out = add_momentum_features(cls.df, rsi_period=7, rsi_oversold=80,
                                        rsi_overbought=62)

    def test_the_rsi_column_does_honour_the_configured_period(self):
        """Half the bug's shape: the column is right, so a reader has no cue."""
        expected = compute_rsi(self.df["close"], period=7).dropna()
        np.testing.assert_allclose(self.out["rsi"].dropna().to_numpy(),
                                   expected.to_numpy(), rtol=1e-12)

    def test_the_entry_signal_matches_the_DEFAULT_period_not_the_configured_one(self):
        hist = self.out["macd_hist"]
        up = hist > hist.shift(1)
        rsi7 = compute_rsi(self.df["close"], period=7)
        rsi14 = compute_rsi(self.df["close"], period=DEFAULT_RSI_PERIOD)
        actual = (self.out["momentum_signal"] == 1)
        mask = hist.notna() & rsi7.notna() & rsi14.notna()

        agree14 = int((((rsi14 < 80) & up)[mask] == actual[mask]).sum())
        agree7 = int((((rsi7 < 80) & up)[mask] == actual[mask]).sum())
        total = int(mask.sum())

        self.assertEqual(
            agree14, total,
            "momentum_signal no longer matches a rule on the DEFAULT-period RSI — if it "
            "now honours rsi_period, that is the fix; supersede F244")
        self.assertLess(
            agree7, total,
            "momentum_signal now also matches the CONFIGURED-period RSI, so the two "
            "series have stopped diverging and F244's premise is gone")

    def test_the_divergence_produces_impossible_looking_bars(self):
        """The observable symptom: a long fires while the RSI column reads overbought."""
        rsi7 = compute_rsi(self.df["close"], period=7)
        fired_high = ((self.out["momentum_signal"] == 1) & (rsi7 >= 80))
        self.assertGreater(
            int(fired_high.sum()), 0,
            "no bar fires long above the oversold threshold any more — the symptom "
            "F244 was diagnosed from has gone")


class TheConfiguredPeriodsActuallyDifferTests(unittest.TestCase):
    """Non-vacuity: if every mode used 14, the bug would be latent, not live."""

    HOURLY = ("RSI_PERIOD_HOURLY", "RSI_PERIOD_QQQ_HOURLY", "RSI_PERIOD_TQQQ_HOURLY",
              "RSI_PERIOD_GDXU_HOURLY", "RSI_PERIOD_SOXL_HOURLY",
              "RSI_PERIOD_LABU_HOURLY", "RSI_PERIOD_TNA_HOURLY")

    def test_every_hourly_mode_configures_a_non_default_period(self):
        for name in self.HOURLY:
            with self.subTest(mode=name):
                self.assertNotEqual(
                    int(getattr(config, name)), DEFAULT_RSI_PERIOD,
                    "{} now equals the default, so the signal and the column agree "
                    "for this mode and F244 no longer bites it".format(name))

    def test_the_daily_default_is_unaffected(self):
        """Scope: BTC daily uses 14, so it is genuinely not affected. Stated so the
        finding is not inherited as 'every mode is broken'."""
        self.assertEqual(int(config.RSI_PERIOD), DEFAULT_RSI_PERIOD)

    def test_the_engine_really_passes_the_configured_period(self):
        src = (ROOT / "src" / "strategy" / "engine.py").read_text(encoding="utf-8")
        self.assertIn(
            "rsi_period=getattr(config,", src,
            "engine.py no longer passes a per-mode rsi_period, so the divergence would "
            "have a different shape")


class TheLiveArchiveWitnessesItTests(unittest.TestCase):
    """Synthetic proof is not enough for a claim about production behaviour."""

    @classmethod
    def setUpClass(cls):
        by_bar = {}
        for line in ARCHIVE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("bar_time") and row.get("rsi") is not None:
                    by_bar[row["bar_time"]] = row
        cls.bars = list(by_bar.values())

    def test_bars_fired_long_while_the_logged_rsi_was_overbought(self):
        live_os = int(config.RSI_OVERSOLD_TQQQ_HOURLY)
        odd = [b for b in self.bars
               if b.get("momentum_signal") == 1 and b["rsi"] >= live_os]
        self.assertEqual(
            len(odd), 18,
            "the count of impossible-looking bars moved off 18 — if it went to zero the "
            "log and the gate now agree; supersede F244")
        self.assertGreater(
            max(b["rsi"] for b in odd), 86.0,
            "the worst logged RSI on a firing bar fell below 86 — the divergence "
            "narrowed and the recorded magnitude is stale")

    def test_no_configured_threshold_could_explain_them(self):
        """Rules out the innocent explanation: a looser threshold in force at log time.
        The highest oversold any mode configures is 85, below the observed 86.8."""
        highest = max(int(getattr(config, n)) for n in dir(config)
                      if n.startswith("RSI_OVERSOLD"))
        worst = max(b["rsi"] for b in self.bars if b.get("momentum_signal") == 1)
        self.assertGreater(
            worst, highest,
            "a configured oversold threshold ({}) now exceeds the worst firing RSI "
            "({:.2f}), so a threshold change would explain the bars and the "
            "period-divergence diagnosis needs re-deriving".format(highest, worst))


class TheShadowReplayBracketsInsteadOfPretendingTests(unittest.TestCase):
    """H26's deliverable, scoped honestly by what F244 makes unknowable."""

    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import shadow_replay
        cls.sr = shadow_replay
        cls.bars = shadow_replay.load_bars()

    def test_the_bracket_contains_the_truth_and_is_not_degenerate(self):
        got = self.sr.entry_bounds(self.bars, 80, 0.5, 80, 0.5)
        self.assertFalse(got["exact"], "the tool must not claim exactness")
        self.assertLess(got["lower"], got["upper"])
        self.assertGreater(got["lower"], 0,
                           "a lower bound of zero is not a bound, it is a shrug")
        self.assertAlmostEqual(got["lower_pct"], 39.4, delta=0.5)
        self.assertAlmostEqual(got["upper_pct"], 81.4, delta=0.5)

    def test_tightening_the_candidate_shrinks_both_bounds(self):
        wide = self.sr.entry_bounds(self.bars, 80, 0.5, 80, 0.5)
        tight = self.sr.entry_bounds(self.bars, 38, 1.3, 80, 0.5)
        self.assertLess(tight["lower"], wide["lower"])
        self.assertLess(tight["upper"], wide["upper"])

    def test_a_looser_candidate_is_refused_on_both_axes(self):
        with self.assertRaises(ValueError):
            self.sr.entry_bounds(self.bars, 90, 0.5, 80, 0.5)
        with self.assertRaises(ValueError):
            self.sr.entry_bounds(self.bars, 38, 0.3, 80, 0.5)

    def test_the_lower_bound_only_counts_bars_the_log_confirms(self):
        """Soundness: every bar in the lower bound must have actually fired live."""
        known = self.sr.known_macd_turns(self.bars, 80)
        fired = {b["bar_time"] for b in self.bars if b.get("momentum_signal") == 1}
        self.assertTrue(set(known) <= fired,
                        "the lower bound counts a bar the log never marked as firing")


if __name__ == "__main__":
    unittest.main()
