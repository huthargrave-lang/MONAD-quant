"""F16's code bridge: does the entry signal actually exploit mean reversion?

`context_map.json` bridges F16 to `src/strategy/engine.py::generate_trades` with the
note *"daily mean-reversion is a real serial-correlation property; the entry signal
exploits it."* That bridge had no `guarded_by` test, which puts it in the class this
project keeps getting burned by: a claim about code, in prose, that nothing re-checks
while the code moves underneath it.

**Scope, stated because half of F16 is not testable here.** F16 makes two claims:

1. *Markets mean-revert* — lag-1 ACF of SPY −0.117 (t −6.4) and friends. **Not
   decidable offline**: market-data hosts are network-blocked and the caches are
   empty stubs. Nothing here tests it, and nothing here should pretend to.
2. *The entry signal exploits it* — the bridge. **Decidable right now**, on synthetic
   data, because it is a statement about the sign of a function this repo defines.

Only (2) is guarded. The guard is BIDIRECTIONAL: if someone rewrote the entry to a
momentum rule — buying strength instead of weakness — F16's bridge would silently
become false, and this fails loudly instead.

The load-bearing test is `test_entries_follow_declines_not_advances`. Asserting that a
hand-built oversold bar fires long is weak — it can pass on a signal that fires on
*everything*. Asserting that entries are concentrated after **down** moves relative to
up moves is the property that actually distinguishes mean reversion from momentum, and
it is the one a flip would break.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.signals.momentum import momentum_signal  # noqa: E402


def synthetic_frame(n: int = 1200, seed: int = 20260725) -> pd.DataFrame:
    """A mean-reverting daily series with enough range to trigger both extremes.

    Built with an explicit negative lag-1 component so oversold and overbought
    conditions both occur often enough to measure — this is a test fixture for the
    SIGN of a signal, not a market model, and no claim is made from its returns.
    """
    rng = np.random.default_rng(seed)
    rets = np.zeros(n)
    for i in range(1, n):
        rets[i] = -0.25 * rets[i - 1] + rng.normal(0, 0.015)
    close = 100 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({"close": close, "open": close, "high": close * 1.004,
                         "low": close * 0.996, "volume": 1e6}, index=idx)


class F16EntrySignExploitsMeanReversion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = synthetic_frame()
        cls.sig = momentum_signal(cls.df)
        cls.ret = cls.df["close"].pct_change()

    def test_the_signal_fires_at_all(self):
        """A guard on a signal that never fires would be vacuous."""
        self.assertGreater((self.sig == 1).sum(), 20,
                           "no long entries on the fixture — the guard below is vacuous")

    def test_entries_follow_declines_not_advances(self):
        """THE LOAD-BEARING ASSERTION.

        Mean reversion buys weakness. If the mean prior-bar return on long-entry bars
        is not clearly negative, the entry is not exploiting negative serial
        correlation, and F16's bridge no longer describes the code.
        """
        prior = self.ret.shift(1)
        entry_prior = prior[self.sig == 1].dropna()
        all_prior = prior.dropna()
        self.assertLess(
            entry_prior.mean(), 0.0,
            "long entries no longer follow DOWN bars (mean prior return "
            "{:.5f}) — the entry signal appears to be momentum, not mean "
            "reversion. F16's code bridge is false: supersede the WEB node and "
            "re-baseline, do not edit this test.".format(entry_prior.mean()))
        self.assertLess(
            entry_prior.mean(), all_prior.mean(),
            "long entries are not selective toward declines relative to the "
            "unconditional bar — the mean-reversion character is gone.")

    def test_it_does_not_also_go_long_on_strength(self):
        """Direction check. A signal firing long on both extremes would pass the
        test above on average while not being mean-reverting at all."""
        prior = self.ret.shift(1)
        longs = prior[self.sig == 1].dropna()
        shorts = prior[self.sig == -1].dropna()
        if len(shorts) < 5:
            self.skipTest("too few short signals on this fixture to compare")
        self.assertLess(
            longs.mean(), shorts.mean(),
            "long and short entries no longer sit on opposite sides of the prior "
            "bar's return — the signal has lost its directional structure.")

    def test_a_momentum_flip_would_be_CAUGHT(self):
        """Negative control. A guard that cannot fail is not a guard.

        Synthesise the rewrite this test exists to catch — long on strength instead
        of weakness — and confirm the load-bearing assertion rejects it.
        """
        flipped = -momentum_signal(self.df)   # buy what it would have sold
        prior = self.ret.shift(1)
        flipped_entry_prior = prior[flipped == 1].dropna()
        self.assertGreater(
            flipped_entry_prior.mean(), 0.0,
            "the negative control did not invert — this test cannot detect a "
            "momentum flip and is therefore worthless")


class F16ScopeTests(unittest.TestCase):
    """Pin what this file does NOT claim, so a reader does not over-read it."""

    def test_the_market_half_of_F16_is_explicitly_not_tested_here(self):
        doc = sys.modules[__name__].__doc__ or ""
        self.assertIn("Not\n   decidable offline", doc.replace("**", ""))

    def test_the_bridge_is_registered_and_now_guarded(self):
        import json
        bridges = json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["graph_bridges"]["bridges"]
        f16 = [b for b in bridges if b.get("node") == "F16"]
        self.assertTrue(f16, "the F16 code bridge disappeared from context_map.json")
        self.assertIn("src/strategy/engine.py::generate_trades", f16[0]["code"])


if __name__ == "__main__":
    unittest.main()
