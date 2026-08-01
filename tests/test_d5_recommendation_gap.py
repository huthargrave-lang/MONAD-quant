"""D5's gap: the recommended architecture is not applied, and one guard blocks applying it.

D5 records the evidence-backed build — *"equal-weight portfolio of daily mean-reversion
sleeves on un-leveraged equities + gold, each = buy-the-dip + multi-day HORIZON exit,
with VOL-TARGETED position sizing"* — and four explicit DROPs: **the hourly timescale,
the fixed %-stop exit, 3x leverage, and long-only cross-sectional rotation**. Its own
text is careful: *"this records the evidence-backed recommendation, not an applied
change"*, and *"changing the live instrument/exit/sizing touches the armed trader path —
sign-off required"*.

A recommendation cannot be guarded the way a measurement can. What can be guarded is the
**gap**: every DROP is still in force, item by item, and each assertion fails the moment
that item is applied — which is exactly when D5 must stop being called a recommendation
and when the sign-off it demands becomes due.

**And applying D5's first DROP would trip a live guard.** `live/trader.py::
_assert_mode_symbol_coherent` (added for F157) requires `ACTIVE_MODE == f"{LIVE_SYMBOL}
_HOURLY"` — a literal suffix match. Three daily modes exist in `config._MODE_TO_ASSET`
(`BTC_DAILY`, `QQQ`, `SOXL_DAILY`) and **none of them can satisfy it**, so the live
trader cannot be armed on any daily timescale, and its refusal message would direct the
operator back to the hourly mode D5 says to drop.

That is a latent coupling, not a live bug, and it is written down as such: every live
mode the project currently supports *is* hourly, so the invariant is correct for every
configuration that exists today. Its intent — thresholds must match the traded instrument
— is timescale-independent; only its implementation is not. Fixing it means comparing the
mode's resolved asset against `LIVE_SYMBOL` instead of string-matching `_HOURLY`, and
that touches the fenced live path, so it is recorded here rather than done.
"""
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.backtest import runner as runner_mod  # noqa: E402
from src.strategy import engine as engine_mod  # noqa: E402

TRADER = ROOT / "live" / "trader.py"

# The 3x-leveraged products among the configured modes. These are facts about the ETFs
# themselves (TQQQ 3x NDX, SOXL 3x semis, LABU 3x biotech, TNA 3x Russell 2000,
# GDXU 2x/3x gold miners), not a property the repo computes.
LEVERAGED_MODES = {"TQQQ_HOURLY", "SOXL_HOURLY", "LABU_HOURLY", "TNA_HOURLY",
                   "GDXU_HOURLY"}

APPLIED = ("D5 appears to have been APPLIED. D5 records a RECOMMENDATION, not an "
           "applied change, and its own text requires sign-off because this touches "
           "the armed trader path. Update the node (and confirm the sign-off) rather "
           "than editing this test. Specifically: ")


class EveryD5DropIsStillInForceTests(unittest.TestCase):
    """One assertion per DROP. Each fires when that DROP is applied."""

    def test_the_active_mode_is_still_HOURLY(self):
        self.assertTrue(
            config.ACTIVE_MODE.endswith("_HOURLY"),
            APPLIED + "ACTIVE_MODE is no longer hourly ({!r}). See also the live "
            "invariant class below — a daily mode cannot arm the trader today."
            .format(config.ACTIVE_MODE))

    def test_the_active_instrument_is_still_3x_LEVERAGED(self):
        self.assertIn(
            config.ACTIVE_MODE, LEVERAGED_MODES,
            APPLIED + "ACTIVE_MODE {!r} is no longer a 3x-leveraged product."
            .format(config.ACTIVE_MODE))

    def test_the_exit_is_still_a_fixed_PERCENT_BAND(self):
        """D5 wants a multi-day horizon exit. The engine's time exit is a fallback
        reached only when neither barrier fires — the opposite priority."""
        source = inspect.getsource(engine_mod.compute_trade_returns)
        self.assertIn("exit_return = -stop - stop_slippage_pct", source,
                      APPLIED + "the %-stop fill is gone from compute_trade_returns.")
        self.assertIn(
            "# If no target/stop/opposing-signal hit, use close of last future bar",
            source,
            APPLIED + "the time exit is no longer the fallback branch — it may have "
            "been promoted to the primary exit, which IS D5's recommendation.")

    def test_no_multi_sleeve_PORTFOLIO_construction_exists_in_src(self):
        """D5's build is an equal-weight portfolio of sleeves. The engine takes one
        DataFrame and knows about one instrument."""
        params = list(inspect.signature(runner_mod.run_backtest).parameters)
        self.assertEqual(params[0], "df",
                         APPLIED + "run_backtest's first parameter changed; it may now "
                                   "take a panel of instruments.")
        hits = [str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py")
                if "def sleeve" in p.read_text(encoding="utf-8")
                or "equal_weight" in p.read_text(encoding="utf-8")]
        self.assertEqual(
            hits, [],
            APPLIED + "portfolio construction appeared in src/ ({}).".format(hits))

    def test_sizing_is_still_not_VOL_TARGETED(self):
        """Cross-checks F176 from the D5 side: the recommended sizing is unimplemented."""
        source = (ROOT / "src" / "strategy" / "sizing.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "vol_target", source,
            APPLIED + "vol-targeted sizing landed in src/strategy/sizing.py.")

    def test_the_node_still_describes_itself_as_a_recommendation(self):
        """If the prose changes but the code does not, the tests above go quiet while
        the node starts claiming something new. This catches the reverse drift."""
        web = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        start = web.index("### D5 ")
        body = web[start:start + 1400]
        self.assertIn(
            "not an applied change", body,
            "D5 no longer describes itself as unapplied — if it was applied, the "
            "assertions above should be failing; if it was not, restore the wording")


class ApplyingD5WouldTripTheLiveInvariantTests(unittest.TestCase):
    """The coupling. Recorded, not fixed — the live path is fenced."""

    def test_the_invariant_matches_the_HOURLY_suffix_literally(self):
        source = TRADER.read_text(encoding="utf-8")
        self.assertIn(
            'expected = f"{config.LIVE_SYMBOL}_HOURLY"', source,
            "the mode/symbol invariant changed. If it now resolves the mode's asset "
            "instead of matching a suffix, the coupling documented here is fixed — "
            "say so in the web rather than deleting this test.")

    def test_daily_modes_exist_and_NONE_can_satisfy_it(self):
        daily = [m for m in config._MODE_TO_ASSET if not m.endswith("_HOURLY")]
        self.assertTrue(daily, "no daily mode is configured any more")
        for mode in daily:
            asset = config._MODE_TO_ASSET[mode]
            self.assertNotEqual(
                mode, "{}_HOURLY".format(asset),
                "{} can now satisfy the live invariant — the timescale coupling is "
                "gone".format(mode))

    def test_the_refusal_points_the_operator_BACK_to_an_hourly_mode(self):
        """Why this matters: the guard does not merely block, it prescribes."""
        source = TRADER.read_text(encoding="utf-8")
        self.assertIn("set config.ACTIVE_MODE = {expected!r} to match", source,
                      "the refusal message changed — re-read what it now prescribes")

    def test_this_is_LATENT_because_every_live_mode_today_is_hourly(self):
        """The scope limit, asserted. If a daily live mode is ever configured, this
        stops being latent and the invariant needs the real fix."""
        self.assertTrue(
            config.LIVE_SYMBOL and "{}_HOURLY".format(config.LIVE_SYMBOL)
            in config._MODE_TO_ASSET,
            "LIVE_SYMBOL {!r} no longer has an hourly mode — the invariant may now be "
            "blocking a configuration the project actually intends to run, which makes "
            "this a live bug rather than a latent coupling".format(config.LIVE_SYMBOL))


class TheGuardWouldActuallyFireTests(unittest.TestCase):
    """A guard that cannot fail is not a guard — check the discriminators are real."""

    def test_the_leveraged_set_is_a_strict_subset_of_configured_modes(self):
        modes = set(config._MODE_TO_ASSET)
        self.assertTrue(LEVERAGED_MODES < modes,
                        "LEVERAGED_MODES no longer names configured modes: {}".format(
                            sorted(LEVERAGED_MODES - modes)))
        self.assertTrue(modes - LEVERAGED_MODES,
                        "every configured mode is leveraged, so the leverage "
                        "assertion cannot discriminate")

    def test_an_unleveraged_daily_mode_is_actually_reachable_in_config(self):
        """So 'D5 not applied' is a choice the config could reverse, not an
        impossibility that makes the test vacuous."""
        candidates = [m for m in config._MODE_TO_ASSET
                      if m not in LEVERAGED_MODES and not m.endswith("_HOURLY")]
        self.assertTrue(
            candidates,
            "no un-leveraged daily mode exists, so the DROP assertions above could "
            "never flip and are vacuous")


if __name__ == "__main__":
    unittest.main()
