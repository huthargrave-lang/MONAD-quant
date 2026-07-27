"""H26's shadow evaluator, mostly already possible — and F195 confirmed on real bars.

H26 asks for "a non-trading process that replays bars and logs what a candidate config
would have done", as infrastructure to de-risk active-engine experiments. Most of it
already existed and nobody had joined the pieces: `live/signals.py` writes one row per
scheduler cycle into `signal_history.jsonl`, and each row carries the **raw indicator
values** — `rsi` and `vwap_zscore` — alongside the derived signals. Those are exactly the
quantities the entry thresholds compare against, so a candidate threshold set replays
offline with no market data and no new logging.

`tools/shadow_replay.py` does that. Its first use confirms F195 on **real recorded TQQQ
hourly bars** rather than a synthetic series, and more strongly:

    oversold   rsi<os %   rsi>ob %   in BOTH zones %
        80       81.4       60.6          41.9        <- the live setting; zones OVERLAP
        38       13.7       60.6           0.0        <- the daily setting

322 distinct bars (543 cycle rows — an unchanged bar repeats across cycles, and counting
rows would weight quiet hours by how often the scheduler happened to run). The live
"oversold" threshold admits **81.4%** of real bars against **13.7%** for the daily one, and
RSI sits in *both* named zones on **41.9%** — where the synthetic estimate in F195 was
24.6%. The real inversion is worse than the modelled one.

The recorded signal composition is consistent: momentum fires long on 130 of 322 bars
(40.4%), short on 108 (33.5%), neutral on only 84 (26.1%).

**Also worth recording: 112 of 322 bars produced a final signal of −1.** The live pipeline
computes shorts (`generate_trades(..., longs_only=False)` in `live/signals.py`) and
`trader.py` discards them behind `TRADER_ALLOW_SHORTS = False`, logging "Short signal fired
but TRADER_ALLOW_SHORTS is False — skipping". That is correct behaviour on a long-only
paper bot, and it means roughly a third of live cycles produce a signal that is computed
and thrown away.

**What the replay cannot do**, asserted so the tool is not over-read: it cannot vary the
RSI *period* or MACD windows (only the indicator's value was logged), and it cannot
evaluate the MACD histogram-turn term, which is not logged at all. Every count it produces
is therefore an **upper bound** on how often a candidate would actually fire. It says
nothing about fills or PnL.
"""
import collections
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "shadow_replay", ROOT / "tools" / "shadow_replay.py")
SR = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = SR
_SPEC.loader.exec_module(SR)

HISTORY = Path(SR.DEFAULT_HISTORY)


class TheRecordedHistoryCarriesRawIndicatorsTests(unittest.TestCase):
    """Why no new infrastructure was needed."""

    def test_every_row_logs_rsi_and_vwap_zscore(self):
        rows = [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines()
                if l.strip()]
        self.assertGreater(len(rows), 100)
        for row in rows:
            self.assertIn("rsi", row)
            self.assertIn("vwap_zscore", row)
        self.assertTrue(
            any(r.get("rsi") is not None for r in rows),
            "no row carries an RSI value — threshold replay is impossible")

    def test_cycles_collapse_to_fewer_distinct_bars(self):
        """Counting rows would weight quiet hours by scheduler frequency."""
        rows = sum(1 for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip())
        bars = len(SR.load_bars())
        self.assertLess(bars, rows,
                        "rows no longer repeat per bar — re-check the dedupe assumption")
        self.assertGreater(bars, 100, "too few distinct bars to measure")

    def test_it_refuses_cleanly_when_there_is_no_history(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            SR.load_bars("/nonexistent/signal_history.jsonl")
        self.assertIn("does not fetch", str(ctx.exception),
                      "the error no longer says the tool replays rather than fetches")


class F195ConfirmedOnRealBarsTests(unittest.TestCase):
    """The synthetic finding, re-measured on the committed live run."""

    @classmethod
    def setUpClass(cls):
        cls.bars = SR.load_bars()
        cls.overbought = config.RSI_OVERBOUGHT_TQQQ_HOURLY
        cls.zt = config.VWAP_ZSCORE_THRESH_TQQQ_HOURLY

    def _replay(self, oversold):
        return SR.replay(self.bars, oversold, self.overbought, self.zt)

    def test_the_live_threshold_admits_most_real_bars(self):
        live = self._replay(config.RSI_OVERSOLD_TQQQ_HOURLY)
        self.assertGreater(
            live["rsi_below_oversold_pct"], 70.0,
            "the live oversold threshold no longer admits most recorded bars — "
            "re-measure before citing F195's real-data figure")

    def test_the_daily_threshold_is_several_times_more_selective(self):
        live = self._replay(config.RSI_OVERSOLD_TQQQ_HOURLY)
        daily = self._replay(config.RSI_OVERSOLD)
        self.assertGreater(
            live["rsi_below_oversold_pct"] / max(daily["rsi_below_oversold_pct"], 0.1),
            4.0,
            "the live threshold is now within 4x the daily one's selectivity on real "
            "bars ({} vs {})".format(live["rsi_below_oversold_pct"],
                                     daily["rsi_below_oversold_pct"]))

    def test_the_zones_overlap_on_real_bars_MORE_than_the_synthetic_estimate(self):
        live = self._replay(config.RSI_OVERSOLD_TQQQ_HOURLY)
        self.assertTrue(live["zones_overlap"])
        self.assertGreater(
            live["in_both_zones_pct"], 24.6,
            "the real overlap fell below F195's synthetic 24.6% estimate — the "
            "'worse than modelled' claim no longer holds")

    def test_the_correctly_ordered_threshold_has_NO_overlap(self):
        """Non-vacuity: overlap is a property of the inversion, not of the data."""
        daily = self._replay(config.RSI_OVERSOLD)
        self.assertFalse(daily["zones_overlap"])
        self.assertEqual(daily["in_both_zones_pct"], 0.0)

    def test_the_recorded_momentum_signal_fires_on_a_large_share(self):
        counts = collections.Counter(b["momentum_signal"] for b in self.bars)
        fired = (counts[1] + counts[-1]) / len(self.bars)
        self.assertGreater(
            fired, 0.6,
            "the recorded momentum signal now fires on under 60% of bars — F195's "
            "'the RSI term is inert' reading rests on it firing constantly")


class ShortsAreComputedAndDiscardedTests(unittest.TestCase):
    def test_the_live_run_produced_many_short_signals(self):
        counts = collections.Counter(b["signal"] for b in SR.load_bars())
        self.assertGreater(
            counts[-1], 50,
            "the recorded run no longer contains many short signals — the "
            "computed-and-discarded observation would need re-measuring")

    def test_the_trader_discards_them(self):
        self.assertFalse(getattr(config, "TRADER_ALLOW_SHORTS", False),
                         "TRADER_ALLOW_SHORTS is now True — the bot would ACT on the "
                         "short signals this run only logged")
        text = (ROOT / "live" / "trader.py").read_text(encoding="utf-8")
        self.assertIn("TRADER_ALLOW_SHORTS", text)
        self.assertIn("Short signal fired but TRADER_ALLOW_SHORTS is False", text)

    def test_the_live_pipeline_deliberately_computes_them(self):
        self.assertIn("longs_only=False",
                      (ROOT / "live" / "signals.py").read_text(encoding="utf-8"),
                      "the live signal pipeline no longer computes shorts")


class TheToolStatesItsOwnLimitsTests(unittest.TestCase):
    def test_it_declares_the_counts_are_upper_bounds(self):
        source = (ROOT / "tools" / "shadow_replay.py").read_text(encoding="utf-8")
        self.assertIn("upper bound", source.lower())
        self.assertIn("histogram-turn term is not logged", source,
                      "the tool no longer says the MACD term is unavailable — its "
                      "counts would read as exact")

    def test_it_cannot_vary_the_indicator_period(self):
        """The F23 boundary: only the VALUE was logged, not the inputs."""
        rows = [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines()
                if l.strip()]
        self.assertNotIn("rsi_period", rows[0])
        self.assertNotIn("macd_hist", rows[0])


if __name__ == "__main__":
    unittest.main()
