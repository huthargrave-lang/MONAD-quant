"""F17's breakeven clause: the ratio is mislabelled, which inverts the reader's arithmetic.

F17 is the project's most actionable finding — *"replace %-stop with a horizon/time exit"*
— and it justifies itself partly with a parenthetical: *"daily WR 34–41%, **below the 2:1
breakeven**, half the instruments negative"*. That clause is pure arithmetic and it is
checkable against the shipped bands.

**A 2:1 band's breakeven win rate is 33.3%, so 34–41% is entirely ABOVE it.** Read
literally, F17's own numbers say the opposite of what the clause claims. Even at the
`harsh` mode's 5bps round-trip the 2:1 breakeven only reaches 34.4%; it takes **34bps**
— seventeen times the `realistic` cost — to reach 41%.

**But the daily ETF bands are not 2:1.** `QQQ` and `SOXL` daily are **1.67:1** (1.00/0.60
and 2.00/1.20), whose breakeven is **37.5%** at zero cost. A fixed 5bps bites harder on
the tighter band, so under harsh cost they separate: QQQ reaches **40.6%**, SOXL only
**39.1%**. Against the band F17 was actually measuring, the cited 34–41% straddles
breakeven at realistic cost and is mostly at or below it under harsh cost. The substance
survives; the label does not.

So this is a correction to a supporting clause, not a refutation. The failure mode is
worth naming: **a mislabelled ratio makes a sound claim read as false**, and a reader who
checks the arithmetic against the stated "2:1" concludes F17 is wrong when it is not.

**Why it could not be settled from the record.** F17 carries no `evidenced_by` edge and
names no experiment — unlike F16, F19, F20 and F21, which all cite E9/E10. There is no
run to open and check which band produced "34–41%". That absence is asserted below, since
it is the reason a one-word label error became unresolvable.

All arithmetic here is exact and offline. Nothing re-tests F17's APY or Sharpe figures.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.backtest.runner import BACKTEST_MODES  # noqa: E402

CITED_LO, CITED_HI = 0.34, 0.41       # F17's "daily WR 34-41%"
DAILY_ETF_MODES = ("QQQ", "SOXL")     # the un-leveraged daily bands F17 concerns


def breakeven(target, stop, slippage=0.0, stop_slippage=0.0):
    """Win rate at which p*win == (1-p)*loss, with costs charged to both sides.

    Matches compute_trade_returns' accounting: `slippage_pct` is deducted from every
    trade return, and `stop_slippage_pct` is charged on stop fills only.
    """
    win = target - slippage
    loss = stop + slippage + stop_slippage
    return loss / (win + loss)


def band(mode):
    a = config.ASSETS[mode]
    return a["target_gain_pct"], a["stop_loss_pct"]


class ATwoToOneBandCannotProduceTheCitedClaimTests(unittest.TestCase):
    """The literal reading of F17's clause, and why it fails."""

    def test_the_two_to_one_breakeven_is_below_the_entire_cited_range(self):
        self.assertAlmostEqual(breakeven(0.03, 0.015), 1 / 3, places=10)
        self.assertLess(
            breakeven(0.03, 0.015), CITED_LO,
            "a 2:1 band's breakeven is no longer below F17's cited 34% floor — the "
            "clause may have become self-consistent; re-read F17")

    def test_realistic_and_harsh_costs_barely_move_it(self):
        """Stated precisely rather than roundly: at the harsh 5bps the 2:1 breakeven is
        34.4%, which clips the very bottom of the cited range and leaves 35–41% — the
        bulk of it — still above breakeven."""
        self.assertLess(breakeven(0.03, 0.015,
                                  BACKTEST_MODES["realistic"]["slippage_pct"]), CITED_LO)
        harsh = breakeven(0.03, 0.015, BACKTEST_MODES["harsh"]["slippage_pct"])
        self.assertLess(
            harsh, 0.35,
            "the harsh-cost 2:1 breakeven now exceeds 35%, so it covers a meaningful "
            "part of F17's cited range — recompute the clause")
        covered = (harsh - CITED_LO) / (CITED_HI - CITED_LO)
        self.assertLess(
            covered, 0.10,
            "the harsh 2:1 breakeven now covers {:.0%} of the cited 34-41% range; the "
            "literal reading is no longer clearly unsupportable".format(covered))

    def test_it_takes_an_implausible_cost_to_reach_41_percent(self):
        """Bounds how far off the literal reading is: 34bps round-trip, vs 2bps
        realistic and 5bps harsh."""
        lo, hi = 0.0, 0.02
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if breakeven(0.03, 0.015, mid) < CITED_HI else (lo, mid)
        self.assertGreater(lo, 0.0030, "the required slippage dropped below 30bps")
        self.assertGreater(
            lo / BACKTEST_MODES["realistic"]["slippage_pct"], 10.0,
            "the required cost is no longer an order of magnitude above the realistic "
            "mode — the literal reading is closer to workable than F17 implies")


class TheDailyETFBandsAreNotTwoToOneTests(unittest.TestCase):
    """The correction. The substance survives against the right band."""

    def test_the_daily_etf_bands_are_five_to_three(self):
        for mode in DAILY_ETF_MODES:
            target, stop = band(mode)
            self.assertAlmostEqual(
                target / stop, 5 / 3, places=6,
                msg="{}'s reward:risk moved off 1.67:1 — F17's clause was measured "
                    "against this band, so recompute before citing it".format(mode))

    def test_their_breakeven_sits_INSIDE_the_cited_range(self):
        for mode in DAILY_ETF_MODES:
            be = breakeven(*band(mode))
            self.assertGreater(be, CITED_LO,
                               "{}'s zero-cost breakeven fell below the cited range; "
                               "the straddle claim no longer holds".format(mode))
            self.assertLess(be, CITED_HI, "{}'s breakeven rose above 41%".format(mode))

    def test_harsh_cost_pushes_it_toward_the_TOP_of_the_cited_range(self):
        """Where F17's clause becomes substantively right — and how far, per band.

        A fixed 5bps bites harder on a tighter band, so the two daily ETF modes do NOT
        land in the same place: QQQ (1.00/0.60) reaches 40.6%, covering nearly the whole
        cited range; SOXL (2.00/1.20) reaches only 39.1%. Asserted separately rather
        than rounded together — the first version of this test generalised QQQ's number
        to both and failed on SOXL.
        """
        slip = BACKTEST_MODES["harsh"]["slippage_pct"]
        floors = {"QQQ": 0.40, "SOXL": 0.385}
        for mode in DAILY_ETF_MODES:
            be = breakeven(*band(mode), slippage=slip)
            self.assertGreater(
                be, floors[mode],
                "{}'s harsh-cost breakeven fell below {:.1%} — F17's clause no longer "
                "holds even against the correct band, which would make it simply wrong "
                "rather than mislabelled".format(mode, floors[mode]))
            self.assertGreater(
                (be - CITED_LO) / (CITED_HI - CITED_LO), 0.6,
                "{}'s harsh breakeven now covers less than 60% of the cited range"
                .format(mode))

    def test_no_shipped_band_has_a_breakeven_above_the_cited_ceiling(self):
        """The bound that makes '34-41% is below breakeven' unsupportable as a blanket
        statement: at zero cost, no configured band demands 41%."""
        worst = max(breakeven(*band(m)) for m in config.ASSETS
                    if config.ASSETS[m].get("target_gain_pct")
                    and config.ASSETS[m].get("stop_loss_pct"))
        self.assertLess(
            worst, CITED_HI,
            "a shipped band now requires a win rate above 41% to break even — F17's "
            "clause could be literally true for it; identify which and re-read F17")


class F17CitesNoExperimentTests(unittest.TestCase):
    """Why the label error could not be resolved from the record."""

    def _f17_body(self):
        web = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        start = web.index("### F17 ")
        return web[start:web.index("\n### ", start + 5)]

    def test_f17_has_no_evidenced_by_edge(self):
        self.assertNotIn(
            "evidenced_by", self._f17_body(),
            "F17 now cites an experiment — open it and settle which band produced the "
            "34-41% figure, then correct or confirm the '2:1' label")

    def test_its_sibling_findings_DO_cite_one(self):
        """Otherwise the absence is the house style, not a gap."""
        web = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        for node in ("### F16 ", "### F19 ", "### F20 "):
            start = web.index(node)
            body = web[start:web.index("\n### ", start + 5)]
            self.assertTrue(
                "evidenced_by" in body or "Source:" in body,
                "{} no longer cites a source either — uncited findings may be the "
                "norm, which changes what F17's silence means".format(node.strip()))

    def test_the_clause_is_still_in_the_node(self):
        """If someone fixes the wording, this fires and points them at this file."""
        self.assertIn(
            "below the 2:1 breakeven", self._f17_body(),
            "F17's breakeven clause was reworded — good. Check the new wording names "
            "the 1.67:1 daily ETF band and the cost assumption, then retire this test.")


if __name__ == "__main__":
    unittest.main()
