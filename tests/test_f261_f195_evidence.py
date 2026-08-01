"""F195's evidence, reconstructed — one claim exact, one not measurable here — F261.

F195 was the corpus's most-cited uncited node: 15 figures, 0 reachable documents, and a
reliance dependent. It makes two claims, and they have very different evidentiary status.

**CLAIM 1 — the thresholds are inverted. Exact, and BROADER than F195 recorded.**
F195 lists three hourly modes with `oversold > overbought`. All **six** are:

    TQQQ 80/62   GDXU 85/62   QQQ 70/62   SOXL 80/62   LABU 70/62   TNA 65/62
    BTC_DAILY 38/62  <- the only correctly ordered pair

This is config arithmetic and needs no market data. TNA is the narrowest at 65/62 and was
not in F195's list.

**CLAIM 2 — "the RSI filter is inert, the signal is the MACD tick alone."** Directionally
right, not exactly measurable from the committed archive, and F244 is why. The logged RSI
is period 7; the gate compares period 14. So the archive cannot answer the question
directly with its own `rsi` column.

Reconstructing the gating series from the logged `bar_close` gets close but not clean:
the median reconstruction error is 0.04 RSI points, yet ~5% of bars are off by >5 (max
27.4), all of them at session boundaries. Restricting to a gap-free subsample is
impossible — **a 20-bar contiguous run never occurs in 322 hourly ETF bars**, because a
trading day is ~7 bars and an overnight gap follows every one. A full RSI(14) memory
window never fits inside a contiguous run. That closes the route, and this file pins the
fact so it is not retried.

What survives is a strong partial result:

* `(rsi14 < 80) & (macd_hist rising)` reproduces the logged gate on **302 of 308 bars
  (98.1%)** — a LIVE confirmation of F244/F260, whose proof was synthetic. The gating
  series really is the default-period one.
* On that reconstruction the RSI term blocks ~5.5pp of a 45.8% MACD-tick rate, i.e. about
  **12% of would-be MACD signals** — carrying ~5% reconstruction noise, so it is an
  estimate, not a figure.
* The bars it blocks are the **highest**-RSI ones. So the term is not inert: it has been
  inverted into a weak *overbought-rejection* filter, which is the opposite of the
  documented "buy oversold dips". F195's "inert" understates by describing as absent what
  is really reversed.

Composed with F260, the live entry rule reduces to: **a MACD histogram tick at parameters
nobody configured, minus the top ~11% of RSI readings, at a period nobody configured.**

Guards are bidirectional: they fail if any mode's ordering changes, if the gate stops
reproducing as the default-period rule, if the reconstruction's discriminating power
disappears, or if a gap-free window becomes available (which would make Claim 2 exactly
measurable — good news, and a reason to supersede rather than retune).
"""
import json
import unittest
from pathlib import Path

import pandas as pd

import config
from src.signals.momentum import compute_macd, compute_rsi

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = (ROOT / "data" / "live_runs" / "archive_2026-06-18_pre_clean_run"
           / "signal_history.jsonl")
HOURLY = ("TQQQ_HOURLY", "GDXU_HOURLY", "QQQ_HOURLY", "SOXL_HOURLY",
          "LABU_HOURLY", "TNA_HOURLY")


def _rows():
    by = {}
    for line in ARCHIVE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("bar_time") and r.get("rsi") is not None and r.get("bar_close"):
            by[r["bar_time"]] = r
    return sorted(by.values(), key=lambda r: r["bar_time"])


class ClaimOneThresholdsAreInvertedTests(unittest.TestCase):
    """Pure config arithmetic — exact, no market data involved."""

    def test_every_hourly_mode_has_oversold_above_overbought(self):
        for mode in HOURLY:
            with self.subTest(mode=mode):
                os_ = int(getattr(config, "RSI_OVERSOLD_" + mode))
                ob = int(getattr(config, "RSI_OVERBOUGHT_" + mode))
                self.assertGreater(
                    os_, ob,
                    "{} is now correctly ordered ({} / {}) — F195's inversion no longer "
                    "covers every hourly mode; supersede rather than edit".format(
                        mode, os_, ob))

    def test_f195_listed_only_three_of_the_six(self):
        """The reconstruction's own contribution: TNA/SOXL/LABU were not in the node."""
        self.assertEqual(len(HOURLY), 6)
        self.assertGreater(int(config.RSI_OVERSOLD_TNA_HOURLY),
                           int(config.RSI_OVERBOUGHT_TNA_HOURLY))
        # narrowest margin — the one most likely to be "fixed" by a small edit
        self.assertEqual(int(config.RSI_OVERSOLD_TNA_HOURLY)
                         - int(config.RSI_OVERBOUGHT_TNA_HOURLY), 3)

    def test_the_daily_mode_is_correctly_ordered(self):
        """Non-vacuity: 'inverted' means nothing if no mode is ordered."""
        self.assertLess(int(config.RSI_OVERSOLD), int(config.RSI_OVERBOUGHT))


class TheGateRunsOnTheDefaultPeriodTests(unittest.TestCase):
    """F244/F260 confirmed on LIVE bars rather than synthetic ones."""

    @classmethod
    def setUpClass(cls):
        rows = _rows()
        cls.close = pd.Series([float(r["bar_close"]) for r in rows])
        cls.fired = pd.Series([1 if r.get("momentum_signal") == 1 else 0 for r in rows])
        cls.logged = pd.Series([float(r["rsi"]) for r in rows])
        _, _, hist = compute_macd(cls.close)
        cls.up = hist > hist.shift(1)
        cls.rsi14 = compute_rsi(cls.close, period=14)
        cls.rsi7 = compute_rsi(cls.close, period=7)
        cls.mask = hist.notna() & cls.rsi14.notna() & cls.rsi7.notna()

    def _agreement(self, rsi):
        os_ = int(config.RSI_OVERSOLD_TQQQ_HOURLY)
        pred = ((rsi < os_) & self.up).astype(int)
        return float((pred[self.mask] == self.fired[self.mask]).mean())

    def test_the_default_period_rule_reproduces_the_live_gate(self):
        self.assertGreaterEqual(
            self._agreement(self.rsi14), 0.97,
            "the default-period rule stopped reproducing the live gate — if the signal "
            "now honours rsi_period that is the F260 fix; supersede F261")

    def test_it_reproduces_better_than_the_configured_period_does(self):
        """The discriminating comparison. Without it, high agreement could just mean
        'the MACD term dominates', which would be true of either period."""
        self.assertGreater(
            self._agreement(self.rsi14), self._agreement(self.rsi7),
            "the configured-period rule now matches the gate at least as well, so this "
            "archive no longer discriminates between the two series")


class ClaimTwoIsNotExactlyMeasurableHereTests(unittest.TestCase):
    """Pinned so the closed route is not retried."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()
        cls.ts = pd.Series(pd.to_datetime([r["bar_time"] for r in cls.rows]))

    def test_no_contiguous_window_fits_an_rsi14_memory(self):
        contig = (self.ts.diff().dt.total_seconds() / 3600).le(1.01)
        longest, run = 0, 0
        for c in contig.fillna(False):
            run = run + 1 if c else 0
            longest = max(longest, run)
        self.assertLess(
            longest, 20,
            "a {}-bar contiguous run now exists — a gap-free RSI(14) subsample may be "
            "possible, which would make F195's claim 2 exactly measurable; supersede "
            "F261 rather than keeping the estimate".format(longest))

    def test_the_reconstruction_is_good_typically_and_bad_at_gaps(self):
        close = pd.Series([float(r["bar_close"]) for r in self.rows])
        logged = pd.Series([float(r["rsi"]) for r in self.rows])
        err = (compute_rsi(close, period=7) - logged).abs().dropna()
        self.assertLess(err.median(), 1.0, "typical reconstruction error grew")
        self.assertGreater(
            err.max(), 5.0,
            "the reconstruction is now clean everywhere — claim 2 may be exactly "
            "measurable; re-derive rather than keeping the estimate")

    def test_the_logged_rsi_is_not_the_gating_one(self):
        """Why the archive cannot answer claim 2 with its own column."""
        os_ = int(config.RSI_OVERSOLD_TQQQ_HOURLY)
        odd = [r for r in self.rows
               if r.get("momentum_signal") == 1 and r["rsi"] >= os_]
        self.assertTrue(
            odd,
            "no bar fires above the oversold threshold any more — the logged and gating "
            "series may have converged, so claim 2 could be read straight off the column")


if __name__ == "__main__":
    unittest.main()
