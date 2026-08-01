"""F204's evidence, reproduced from scratch — eight figures exact, one a lucky draw — F262.

F204 was uncited: 9 figures, 0 reachable documents, 2 reliance dependents. Every figure is
reproducible offline — `validate_ohlc` takes a frame, so synthetic panels suffice and no
market data is involved. Reproducing them is therefore not a matter of *locating* evidence
but of *regenerating* it, which is stronger.

**Eight of nine reproduce exactly.**

* All six corruption classes drop **exactly one bar** each: `low > high`, close above high,
  open below low, zero close, NaN close, negative volume. Positive controls, as recorded.
* Corrupting three recent bars of a 400-bar hourly panel leaves **397** bars with a
  **4-hour** hole in an otherwise 1-hour series.
* The `min_bars` floor (200) does **not** fire — the panel is still long.
* The latest bar is untouched, so the staleness check sees nothing.
* No NaN survives, so the live NaN gate sees finite values, because they are finite.

**The ninth is series-dependent, and F204 reported the high end as if it were the centre.**
F204 records "RSI moves 2.82 points". Measured across 40 synthetic panels, the shift from
the same 3-bar hole is:

    min 0.05   median 1.22   mean 1.20   p90 2.06   max 3.57

2.82 is exceeded by **1 of 40** panels — roughly the 97th percentile. The effect is real
and the direction is right; the magnitude was a single draw quoted as characteristic. Two
of 40 panels show essentially no shift at all (<0.1), so the corruption is not always
detectable downstream either.

That does not weaken F204's conclusion, which is about a *structural* gap rather than an
effect size: the validation catches bad VALUES, and nothing catches the DISCONTINUITY it
creates. It does mean the 2.82 should not be cited as a typical magnitude, which is exactly
what an uncited figure invites.

Guards are bidirectional. They fail if any corruption class stops being caught (the
validation regressed), if it starts RAISING instead of dropping (good news — supersede),
if the hole stops being invisible to the floor/staleness/NaN checks, or if the RSI-shift
distribution moves off what is recorded here.
"""
import logging
import statistics as st
import unittest

import numpy as np
import pandas as pd

from src.data.fetcher import validate_ohlc
from src.strategy.engine import build_features

MIN_BARS_FLOOR = 200          # live/signals.py::_fetch_recent_bars


def panel(n=400, seed=0):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    return pd.DataFrame(
        {"open": c, "close": c, "high": c * 1.003, "low": c * 0.997,
         "volume": rng.integers(10**5, 5 * 10**5, n)},
        index=pd.date_range("2026-01-01", periods=n, freq="h"))


def _corrupt(df, i, kind):
    d = df.copy()
    idx = d.index[i]
    if kind == "low > high":
        d.loc[idx, "low"] = d.loc[idx, "high"] * 1.5
    elif kind == "close above high":
        d.loc[idx, "close"] = d.loc[idx, "high"] * 2
    elif kind == "open below low":
        d.loc[idx, "open"] = d.loc[idx, "low"] * 0.5
    elif kind == "zero close":
        d.loc[idx, "close"] = 0.0
    elif kind == "NaN close":
        d.loc[idx, "close"] = np.nan
    elif kind == "negative volume":
        d.loc[idx, "volume"] = -5
    else:                                              # pragma: no cover
        raise ValueError(kind)
    return d


CLASSES = ("low > high", "close above high", "open below low",
           "zero close", "NaN close", "negative volume")


class EveryCorruptionClassIsCaughtTests(unittest.TestCase):
    """F204's positive controls, regenerated."""

    @classmethod
    def setUpClass(cls):
        logging.disable(logging.WARNING)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_each_class_drops_exactly_one_bar(self):
        base = len(validate_ohlc(panel()))
        self.assertEqual(base, 400, "the clean panel is not passing through intact")
        for kind in CLASSES:
            with self.subTest(kind=kind):
                got = len(validate_ohlc(_corrupt(panel(), 300, kind)))
                self.assertEqual(
                    base - got, 1,
                    "{} no longer drops exactly one bar — if validation now RAISES "
                    "instead, that is the fix F204 asked for; supersede".format(kind))

    def test_it_drops_rather_than_raises(self):
        """The whole finding rests on this. If it ever raises, F204 is resolved."""
        out = validate_ohlc(_corrupt(panel(), 300, "zero close"))
        self.assertIsInstance(out, pd.DataFrame)
        self.assertEqual(len(out), 399)


class TheHoleIsInvisibleDownstreamTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        logging.disable(logging.WARNING)
        clean = panel()
        holed = clean.copy()
        for i in (395, 396, 397):
            holed.loc[holed.index[i], "close"] = 0.0
        cls.clean, cls.out = clean, validate_ohlc(holed)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_three_bars_leave_a_four_hour_hole(self):
        self.assertEqual(len(self.out), 397)
        gaps = pd.Series(self.out.index).diff().dt.total_seconds() / 3600
        self.assertAlmostEqual(gaps.max(), 4.0, places=6)
        self.assertAlmostEqual(gaps.median(), 1.0, places=6)

    def test_the_min_bars_floor_does_not_fire(self):
        self.assertGreater(
            len(self.out), MIN_BARS_FLOOR,
            "the panel now falls under the floor, so the drop WOULD be caught and "
            "F204's gap is closed")

    def test_the_staleness_check_sees_nothing(self):
        self.assertEqual(self.out.index[-1], self.clean.index[-1],
                         "the latest bar is no longer untouched")

    def test_the_nan_gate_sees_finite_values(self):
        self.assertFalse(bool(self.out.isna().any().any()))


class TheRsiShiftIsSeriesDependentTests(unittest.TestCase):
    """F204 quotes 2.82 points. Measured over 40 panels it is the high end."""

    @classmethod
    def setUpClass(cls):
        logging.disable(logging.WARNING)
        deltas = []
        for seed in range(40):
            clean = panel(seed=seed)
            holed = clean.copy()
            for i in (395, 396, 397):
                holed.loc[holed.index[i], "close"] = 0.0
            out = validate_ohlc(holed)
            a = float(build_features(clean)["rsi"].iloc[-1])
            b = float(build_features(out)["rsi"].iloc[-1])
            deltas.append(abs(a - b))
        cls.deltas = sorted(deltas)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_the_median_shift_is_far_below_the_recorded_figure(self):
        self.assertAlmostEqual(
            st.median(self.deltas), 1.22, delta=0.35,
            msg="the median RSI shift moved off 1.22 — F262's characterisation of "
                "F204's 2.82 as an outlier draw needs re-deriving")

    def test_the_recorded_figure_is_near_the_top_of_the_distribution(self):
        above = sum(1 for d in self.deltas if d > 2.82)
        self.assertLessEqual(
            above, 4,
            "2.82 is no longer an upper-tail draw ({}/40 panels exceed it), so quoting "
            "it as typical would now be fair".format(above))

    def test_the_shift_is_real_and_not_always_negligible(self):
        """Non-vacuity: the correction must not read as 'the effect is nothing'."""
        self.assertGreater(max(self.deltas), 2.0,
                           "no panel shows a meaningful shift — F204's effect is gone")
        self.assertGreater(st.median(self.deltas), 0.5,
                           "the typical shift collapsed; the discontinuity no longer "
                           "moves indicators at all")

    def test_some_panels_show_almost_no_shift(self):
        """The other tail, which matters for detectability."""
        self.assertGreaterEqual(
            sum(1 for d in self.deltas if d < 0.1), 1,
            "every panel now shifts materially — the corruption would be easier to "
            "notice downstream than F262 records")


if __name__ == "__main__":
    unittest.main()
