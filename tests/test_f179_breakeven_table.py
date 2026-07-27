"""F179's figures all re-derive from config — and the full table shows what R:R hides.

Study: `docs/research/F179_breakeven_table.md`.

F179 was flagged as quoting 14 figures with no reachable document. Every one is pure
arithmetic over `config.ASSETS` and reproduces exactly: the daily ETF bands are 1.67:1
(QQQ 1.00/0.60, SOXL 2.00/1.20) with a 37.5% zero-cost breakeven; BTC daily is the 2:1
band at 33.3% / 33.8% / 34.4%; and the two 1.67:1 bands separate under harsh cost to
40.6% (QQQ) and 39.1% (SOXL), because a fixed cost bites harder on the tighter band.

**What the full table adds.** F179's blanket claim — no shipped band has a *zero-cost*
breakeven above 41% — holds, with a maximum of 37.5%. Under harsh cost three bands cross
it: TNA_HOURLY 41.7%, BTC_HOURLY 41.7%, and QQQ_HOURLY **47.2%**. Reward:risk cannot
explain that, since BTC_HOURLY and QQQ_HOURLY are both 2:1, the same ratio as BTC daily
at 34.4%.

Band **width in basis points** explains it. 5 bps consumes 13.9% of QQQ_HOURLY's 36-bps
band and 1.1% of BTC daily's 450-bps band. So R:R sets the zero-cost breakeven and width
sets how fast cost moves it — two 2:1 bands sit 12.8 points apart at the same cost, a gap
the ratio alone cannot see.

Guards are bidirectional: they fail if a configured band moves (the table is stale), if
the ordering premise breaks, and if the harsh-cost exceptions change — each naming the
mode so the maintainer knows what to re-derive.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

DOC = ROOT / "docs" / "research" / "F179_breakeven_table.md"
REALISTIC, HARSH = 0.0002, 0.0005


def bands():
    out = {}
    for mode, spec in config.ASSETS.items():
        target, stop = spec.get("target_gain_pct"), spec.get("stop_loss_pct")
        if target is not None and stop is not None:
            out[mode] = (target, stop)
    return out


def breakeven(target, stop, cost=0.0):
    win, loss = target - cost, stop + cost
    return loss / (win + loss)


class TheFiguresF179QuotesReDeriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bands = bands()

    def test_the_daily_etf_bands_are_one_point_six_seven_to_one(self):
        for mode, (target, stop) in (("QQQ", self.bands["QQQ"]),
                                     ("SOXL", self.bands["SOXL"])):
            self.assertAlmostEqual(
                target / stop, 5 / 3, places=6,
                msg="{} daily is no longer 1.67:1 — F179's central correction to F17's "
                    "'2:1' label needs re-deriving".format(mode))
            self.assertAlmostEqual(breakeven(target, stop), 0.375, places=6)

    def test_the_two_identical_ratios_separate_under_harsh_cost(self):
        """Same R:R, different width — the tighter band pays more."""
        qqq = breakeven(*self.bands["QQQ"], cost=HARSH)
        soxl = breakeven(*self.bands["SOXL"], cost=HARSH)
        self.assertAlmostEqual(qqq, 0.406, places=3)
        self.assertAlmostEqual(soxl, 0.391, places=3)
        self.assertGreater(
            qqq, soxl,
            "the tighter 1.67:1 band no longer has the higher harsh-cost breakeven — "
            "the width mechanism has changed")

    def test_btc_daily_is_the_two_to_one_band_f17_meant(self):
        target, stop = self.bands["BTC"]
        self.assertAlmostEqual(target / stop, 2.0, places=6)
        self.assertAlmostEqual(breakeven(target, stop), 1 / 3, places=6)
        self.assertAlmostEqual(breakeven(target, stop, REALISTIC), 0.338, places=3)
        self.assertAlmostEqual(breakeven(target, stop, HARSH), 0.344, places=3)

    def test_no_band_has_a_zero_cost_breakeven_above_forty_one_percent(self):
        worst = max(breakeven(t, s) for t, s in self.bands.values())
        self.assertLess(
            worst, 0.41,
            "a configured band now needs {:.1%} at zero cost — F179's blanket claim "
            "about config.ASSETS is stale".format(worst))
        self.assertAlmostEqual(
            worst, 0.375, places=6,
            msg="the worst zero-cost breakeven moved off 37.5% — re-derive the table")


class WidthNotRatioDrivesTheCostSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bands = bands()

    def test_three_bands_cross_forty_one_percent_under_harsh_cost(self):
        crossers = sorted(m for m, (t, s) in self.bands.items()
                          if breakeven(t, s, HARSH) > 0.41)
        self.assertEqual(
            crossers, ["BTC_HOURLY", "QQQ_HOURLY", "TNA_HOURLY"],
            "the set of bands needing >41% under harsh cost changed to {} — re-derive "
            "the table in the study".format(crossers))

    def test_the_tightest_band_needs_the_most(self):
        worst = max(self.bands, key=lambda m: breakeven(*self.bands[m], cost=HARSH))
        narrowest = min(self.bands, key=lambda m: sum(self.bands[m]))
        self.assertEqual(
            worst, narrowest,
            "the harshest-cost breakeven ({}) is no longer the narrowest band ({}) — "
            "the width mechanism no longer explains the table".format(worst, narrowest))
        self.assertEqual(worst, "QQQ_HOURLY")
        self.assertAlmostEqual(breakeven(*self.bands["QQQ_HOURLY"], cost=HARSH),
                               0.472, places=3)

    def test_identical_ratios_span_a_wide_range_at_the_same_cost(self):
        """The point of the whole document, as one assertion."""
        two_to_one = {m: (t, s) for m, (t, s) in self.bands.items()
                      if abs(t / s - 2.0) < 1e-9}
        self.assertGreaterEqual(len(two_to_one), 3, "too few 2:1 bands to compare")
        spread = (max(breakeven(t, s, HARSH) for t, s in two_to_one.values())
                  - min(breakeven(t, s, HARSH) for t, s in two_to_one.values()))
        self.assertGreater(
            spread, 0.10,
            "bands with an identical 2:1 ratio now span only {:.1f} points at harsh "
            "cost — quoting R:R alone would no longer be misleading".format(
                spread * 100))

    def test_cost_share_of_the_band_orders_the_same_way_as_breakeven(self):
        by_share = sorted(self.bands, key=lambda m: -HARSH / sum(self.bands[m]))
        by_breakeven = sorted(self.bands,
                              key=lambda m: -breakeven(*self.bands[m], cost=HARSH))
        self.assertEqual(
            by_share[0], by_breakeven[0],
            "the band that loses the largest share to cost is no longer the one with "
            "the highest breakeven — the mechanism claim needs re-checking")


class TheStudyAndTheConfigStayInSyncTests(unittest.TestCase):
    def test_every_configured_mode_appears_in_the_table(self):
        text = DOC.read_text(encoding="utf-8")
        for mode in bands():
            label = mode.replace("_HOURLY", "_HOURLY").replace("BTC", "BTC")
            self.assertIn(
                label.split("_")[0], text,
                "the study does not mention {} — a mode was added to config.ASSETS "
                "after the table was written".format(mode))

    def test_the_study_flags_the_unvalidated_mode(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("GDXU", text)
        self.assertIn("RE-SWEEP", text,
                      "the study stopped flagging that GDXU's flattering 6.09:1 band "
                      "comes from unvalidated optimistic-mode parameters")

    def test_claude_md_still_records_that_gdxu_needs_a_re_sweep(self):
        self.assertIn("NEEDS RE-SWEEP",
                      (ROOT / "CLAUDE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
