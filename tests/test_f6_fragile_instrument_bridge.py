"""F6's code bridge: is the deployment still on the instrument F6 calls fragile?

F6 states *"The live instrument (TQQQ) is fragile"* — clearing significance only on the
default split (pooled t≈2.1), collapsing to t=0.37 on recent-only data, with a losing
fold — and concludes *"the live paper deployment is on a fragile, leveraged
instrument."* Its bridge points at `config.ACTIVE_MODE` and
`config.STOP_LOSS_PCT_TQQQ_HOURLY`, with no `guarded_by` test.

**What is and is not testable here.** The *statistical* half — the t-statistics and the
fold behaviour — is a market claim, and market-data hosts are network-blocked with
empty caches. Nothing here tests it. What IS decidable is F6's **precondition**: the
live deployment is still pointed at TQQQ with the stop F6 describes. That precondition
is the whole reason F6 is actionable rather than historical.

So this guard is self-announcing, like the one on D2: it fails when the deployment
**moves off** the instrument. That matters more than usual because F6 `drives` D1 and
D3 — if the deployment changes, three nodes need review at once, and nothing else in
the repo would say so.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402


class F6PreconditionStillHolds(unittest.TestCase):
    """Each failure means F6 became historical rather than live."""

    DOWNSTREAM = "F6 drives D1 and D3, so review all three together."

    def test_the_active_mode_is_still_the_tqqq_mode(self):
        self.assertEqual(
            config.ACTIVE_MODE, "TQQQ_HOURLY",
            "ACTIVE_MODE moved off TQQQ_HOURLY (now {!r}). F6's conclusion — 'the "
            "live paper deployment is on a fragile, leveraged instrument' — is no "
            "longer a statement about the current deployment. Supersede F6 with a "
            "Finding recording what it moved to and whether the new instrument was "
            "robustness-tested. {}".format(config.ACTIVE_MODE, self.DOWNSTREAM))

    def test_the_live_symbol_is_still_tqqq(self):
        self.assertEqual(
            config.LIVE_SYMBOL, "TQQQ",
            "LIVE_SYMBOL moved off TQQQ (now {!r}) — see the message above. Note the "
            "startup invariant added for F157 requires ACTIVE_MODE and LIVE_SYMBOL to "
            "agree, so these two tests should fail together; if only one fails, the "
            "config is incoherent and the trader will refuse to "
            "start.".format(config.LIVE_SYMBOL))

    def test_the_stop_is_still_the_one_F6_describes(self):
        """F6's fragility argument is about a 0.5% stop on a 3x instrument. A changed
        stop does not falsify F6, but it does mean F6 describes a configuration that
        is no longer running."""
        self.assertAlmostEqual(
            config.STOP_LOSS_PCT_TQQQ_HOURLY, 0.005, places=6,
            msg="the TQQQ hourly stop changed from 0.50% to {:.3%}. F6 and F7 both "
                "reason about the stop-vs-intrabar-noise ratio at 0.50%; re-verify "
                "both before citing either.".format(config.STOP_LOSS_PCT_TQQQ_HOURLY))

    def test_the_deployment_is_still_paper(self):
        """F6 says 'live PAPER deployment'. If this ever flips, the finding is not
        merely stale — a node calling the instrument fragile would then describe a
        real-money position, which is a different conversation entirely."""
        self.assertTrue(
            config.LIVE_PAPER_MODE,
            "LIVE_PAPER_MODE is False. F6 documents a FRAGILE instrument and this "
            "repo's standing invariant is PAPER ONLY. Stop and escalate to a human "
            "before anything else.")


class BridgeRegistrationTests(unittest.TestCase):
    def test_the_bridge_exists_and_names_the_config_keys(self):
        bridges = json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["graph_bridges"]["bridges"]
        f6 = [b for b in bridges if b.get("node") == "F6"]
        self.assertTrue(f6, "the F6 code bridge disappeared from context_map.json")
        self.assertIn("config.ACTIVE_MODE", f6[0]["code"])

    def test_the_market_half_of_F6_is_not_claimed_here(self):
        doc = sys.modules[__name__].__doc__ or ""
        self.assertIn("Nothing here tests it", doc)


if __name__ == "__main__":
    unittest.main()
