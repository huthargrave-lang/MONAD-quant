"""H30: the OHLC validation is real — and the hole it leaves behind is not checked.

H30 says "bad data silently corrupts signals" and lists bar-continuity checks as still
open. Testing the first half corrected my own starting hypothesis, so both halves are
recorded.

**The validation exists and works.** `src/data/fetcher.py::validate_ohlc` is called at the
end of `fetch_yfinance`, so it is on the live path, and it catches every corruption class
worth naming: `low > high`, open or close outside `[low, high]`, zero prices, NaN prices,
negative volume. A first pass here constructed frames directly and concluded corrupt bars
reach the indicators — that was an artifact of bypassing the fetcher, not a defect.

**But it drops rather than raises, and nothing downstream sees the gap.** Corrupting three
recent bars of a 400-bar hourly panel removes them silently, leaving 397 bars with a
**4-hour hole** in an otherwise 1-hour series. Then:

* `_fetch_recent_bars`'s `min_bars` floor (200) does not fire — the panel is still long.
* Its staleness check inspects only the **latest** bar, which is untouched.
* The NaN gate in `get_current_signal` sees finite values, because they are finite.
* Indicators are computed straight across the discontinuity: RSI moves **2.82 points**.

So the validation catches bad *values* and nothing catches the *discontinuity it creates*.
That is precisely H30's open "bar-continuity" item, with a worked example.

**And the drop leaves no durable trace.** `validate_ohlc` emits a `log.warning`, not a
monitor event, so a live run whose panel was silently shortened has nothing in the durable
record to show for it. This is the **third** instance of the same shape in this repo:
F172 (healthy exits emit no event), F202 (`_infer_bracket_exit` logs at info), and now
this. Degraded paths announce themselves to a log nobody keeps.

**Magnitude, stated honestly.** 2.82 RSI points rarely flips the live TQQQ threshold of 80
(F195 — that threshold binds on almost nothing). It matters more on the correctly-ordered
daily threshold of 38, and near any boundary. The finding is that the shift happens
unnoticed, not that it is large.

`dotenv` is absent in this environment, so `validate_ohlc` is loaded from source rather
than imported — the same function text the live path runs.
"""
import sys
import types
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategy.engine import build_features, generate_trades  # noqa: E402

FETCHER = ROOT / "src" / "data" / "fetcher.py"
SIGNALS = ROOT / "live" / "signals.py"


def load_validate_ohlc():
    """Import-free load: this module pulls in `dotenv`, which is not installed here."""
    src = FETCHER.read_text(encoding="utf-8")
    start = src.index("def validate_ohlc")
    end = src.index("\ndef ", start + 5)
    ns = {"pd": pd, "log": types.SimpleNamespace(warning=lambda *a, **k: None)}
    exec(src[start:end], ns)  # noqa: S102 — reading the repo's own source, not input
    return ns["validate_ohlc"]


VALIDATE_OHLC = load_validate_ohlc()   # module-level: a class attribute would bind as a method


def panel(n=400, seed=3):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.011, n)))
    idx = pd.date_range("2026-01-01 13:30", periods=n, freq="h")
    return pd.DataFrame({"open": close, "high": close * 1.004, "low": close * 0.996,
                         "close": close, "volume": 1e6}, index=idx)


def last_rsi(frame):
    f = build_features(frame.copy(), timeframe="hourly")
    f = generate_trades(f, require_signals=1, use_regime_filter=False,
                        use_slope_regime=False, longs_only=False)
    return float(f.iloc[-1]["rsi"])


class TheValidationIsRealAndOnTheLivePathTests(unittest.TestCase):
    """The half that corrected my starting hypothesis. Positive controls."""

    @classmethod
    def setUpClass(cls):
        cls.df = panel()

    def test_fetch_yfinance_calls_it(self):
        src = FETCHER.read_text(encoding="utf-8")
        start = src.index("def fetch_yfinance")
        self.assertIn(
            "df = validate_ohlc(df, symbol)", src[start:],
            "fetch_yfinance no longer validates OHLC — corrupt bars would reach the "
            "indicators directly, which is a much larger problem than the gap below")

    def test_the_live_path_goes_through_that_fetcher(self):
        self.assertIn("fetch_yfinance", SIGNALS.read_text(encoding="utf-8"),
                      "live/signals.py no longer uses fetch_yfinance — re-check which "
                      "validation the live path actually gets")

    def test_it_removes_every_corruption_class(self):
        for label, mutate in (
                ("low > high", lambda d: d.__setitem__("low", d["high"] * 2)),
                ("close above high", lambda d: d.__setitem__("close", d["high"] * 3)),
                ("zero close", lambda d: d.__setitem__("close", 0.0)),
                ("nan close", lambda d: d.__setitem__("close", float("nan"))),
                ("negative volume", lambda d: d.__setitem__("volume", -1.0))):
            with self.subTest(corruption=label):
                bad = self.df.copy()
                row = bad.iloc[-1].copy()
                mutate(row)
                bad.iloc[-1] = row
                cleaned = VALIDATE_OHLC(bad, "TEST")
                self.assertEqual(
                    len(cleaned), len(bad) - 1,
                    "{} is no longer removed by validate_ohlc".format(label))


class ButItDropsAndTheHoleIsUncheckedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = panel()
        bad = cls.clean.copy()
        for k in (5, 6, 7):
            bad.iloc[-k, bad.columns.get_loc("close")] = 0.0
        cls.cleaned = VALIDATE_OHLC(bad, "TEST")

    def test_it_returns_a_frame_rather_than_raising(self):
        src = FETCHER.read_text(encoding="utf-8")
        start = src.index("def validate_ohlc")
        body = src[start:src.index("\ndef ", start + 5)]
        self.assertIn("df = df[~bad_mask].copy()", body)
        self.assertNotIn("raise ", body,
                         "validate_ohlc now raises — the silent-drop path this file "
                         "documents is gone; re-read H30")

    def test_the_panel_is_silently_shortened(self):
        self.assertEqual(len(self.cleaned), len(self.clean) - 3)

    def test_the_min_bars_floor_does_not_fire(self):
        """A small drop stays well above the floor, so nothing objects."""
        import re
        floor = int(re.search(r"_MIN_BARS_DEFAULT\s*=\s*(\d+)",
                              SIGNALS.read_text(encoding="utf-8")).group(1))
        self.assertGreater(
            len(self.cleaned), floor,
            "the drop now trips the min_bars floor — a bigger drop WOULD be caught, "
            "which is the point: only large ones are")

    def test_the_staleness_check_looks_only_at_the_last_bar(self):
        text = SIGNALS.read_text(encoding="utf-8")
        self.assertIn("latest_age", text)
        self.assertIn("df.index[-1]", text)
        self.assertNotIn(
            "index.to_series().diff()", text,
            "live/signals.py now inspects bar intervals — a continuity check may have "
            "landed, which is exactly what H30 asks for")

    def test_a_discontinuity_is_left_in_an_otherwise_regular_series(self):
        deltas = pd.Series(self.cleaned.index).diff().dropna().value_counts()
        self.assertGreater(
            len(deltas), 1,
            "the index is regular again — no hole was created, so re-derive the case")
        self.assertEqual(deltas.idxmax(), pd.Timedelta(hours=1))
        self.assertIn(pd.Timedelta(hours=4), set(deltas.index),
                      "the expected 4-hour hole is missing")

    def test_indicators_shift_across_the_hole(self):
        moved = abs(last_rsi(self.cleaned) - last_rsi(self.clean))
        self.assertGreater(
            moved, 0.5,
            "RSI no longer moves across the gap — the downstream effect this finding "
            "rests on has vanished")
        self.assertLess(
            moved, 10.0,
            "the shift grew beyond 10 RSI points; re-measure before citing 2.82")


class TheDropLeavesNoDurableTraceTests(unittest.TestCase):
    """The third instance of a shape this repo keeps finding."""

    def test_it_logs_a_warning_rather_than_a_monitor_event(self):
        src = FETCHER.read_text(encoding="utf-8")
        start = src.index("def validate_ohlc")
        body = src[start:src.index("\ndef ", start + 5)]
        self.assertIn("log.warning(", body)
        self.assertNotIn(
            "add_monitor_event", body,
            "validate_ohlc now writes a durable event — the silent-drop half of this "
            "finding is fixed; update H30")

    def test_the_sibling_cases_are_still_present_to_compare_against(self):
        """F172 and F202's paths, so 'third instance' stays checkable."""
        trader = (ROOT / "live" / "trader.py").read_text(encoding="utf-8")
        self.assertIn('log.info(f"Path inference:', trader,
                      "the F202 inference log line moved — re-check whether it became "
                      "durable")


if __name__ == "__main__":
    unittest.main()
