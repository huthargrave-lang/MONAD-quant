"""Guard for the D6 <-> config.ACTIVE_MODE bridge.

The bridge in context_map.json reads:

    {"node": "D6", "relation": "gated_by", "code": ["config.ACTIVE_MODE"],
     "note": "go/no-go verdict: the active engine shows no demonstrated advantage
              over a static blend — recommend a static allocation; changing the
              live mode needs sign-off."}

D6 is the project's go/no-go: the active engine shows no demonstrated advantage
over a trivial static blend, so the recommendation is a STATIC allocation. The
recommendation has not been applied — config.ACTIVE_MODE still names an active
engine mode. That gap between "recommended" and "deployed" is the claim, and an
unguarded claim rots silently: a reader two months from now cannot tell whether
"recommend a static allocation" is still pending or was quietly done.

BIDIRECTIONAL, which is the point. It fails when the code moves away from the
web node AND when the web node moves away from the code:

  * ACTIVE_MODE stops naming an active engine  -> D6 was applied; the web node
    should be superseded to record that, not the test relaxed.
  * D6 becomes superseded/retracted            -> the bridge now points at a
    dead node and must be re-pointed.
  * the bridge disappears or stops naming
    config.ACTIVE_MODE                          -> the connective tissue is gone.

Every failure message says the same thing: SUPERSEDE THE WEB NODE, DO NOT EDIT
THIS TEST. A guard that gets edited to match new behaviour records nothing; the
web is the thing that is supposed to carry the belief revision.
"""

import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import config  # noqa: E402

MAP = json.loads((REPO / "context_map.json").read_text(encoding="utf-8"))
WEB = (REPO / "RESEARCH_WEB.md").read_text(encoding="utf-8")

SUPERSEDE = (
    "\n\n>>> Do NOT edit this test to make it pass. It guards the D6 <-> "
    "config.ACTIVE_MODE bridge. If the world genuinely changed, record that by "
    "superseding D6 in RESEARCH_WEB.md (tools/note.py supersede) and re-pointing "
    "the bridge in context_map.json — the belief revision belongs in the web, not "
    "in a quietly relaxed assertion."
)


def bridge():
    for b in MAP["graph_bridges"]["bridges"]:
        if b.get("node") == "D6":
            return b
    return None


class TheBridgeExists(unittest.TestCase):
    def test_d6_still_bridges_to_active_mode(self):
        b = bridge()
        self.assertIsNotNone(b, "the D6 bridge vanished from context_map.json" + SUPERSEDE)
        self.assertIn("config.ACTIVE_MODE", b.get("code", []),
                      "the D6 bridge no longer names config.ACTIVE_MODE" + SUPERSEDE)

    def test_the_relation_is_still_gated_by(self):
        self.assertEqual(bridge().get("relation"), "gated_by",
                         "D6's relation to ACTIVE_MODE changed" + SUPERSEDE)

    def test_the_bridge_names_this_guard(self):
        """A guard nobody registered is a guard the backlog will keep re-raising."""
        guards = bridge().get("guarded_by") or []
        self.assertTrue(any("test_d6_active_mode_bridge" in g for g in guards),
                        "context_map.json's D6 bridge does not list this file in "
                        "guarded_by, so research_backlog will keep reporting it as "
                        "an unguarded claim." + SUPERSEDE)


class TheWebNodeIsStillLive(unittest.TestCase):
    def test_d6_exists_in_the_web(self):
        self.assertRegex(WEB, r"(?m)^### D6 — ", "D6 is gone from RESEARCH_WEB.md" + SUPERSEDE)

    def test_d6_is_not_superseded_or_retracted(self):
        body = WEB.split("### D6 — ", 1)[1].split("\n### ", 1)[0]
        hit = re.search(r"\[(SUPERSEDED|RETRACTED) by ([FHED]\d+)\]", body)
        self.assertIsNone(
            hit,
            "D6 is now {} — the bridge points at a dead node and must be "
            "re-pointed at its successor.".format(hit.group(0) if hit else "") + SUPERSEDE)

    def test_d6_still_recommends_a_static_allocation(self):
        """If the recommendation itself changed, the bridge's note is stale."""
        body = WEB.split("### D6 — ", 1)[1].split("\n### ", 1)[0].lower()
        self.assertIn("static", body,
                      "D6 no longer recommends a static allocation" + SUPERSEDE)


class TheRecommendationIsStillUnapplied(unittest.TestCase):
    """The live half of the claim: D6 says 'go static', and we have not."""

    def test_active_mode_still_names_an_active_engine(self):
        mode = getattr(config, "ACTIVE_MODE", None)
        self.assertIn(
            mode, config.ASSETS,
            "config.ACTIVE_MODE = {!r} is no longer one of the active-engine modes "
            "in config.ASSETS. If D6's static-allocation recommendation was applied, "
            "that is a belief change: supersede D6 to record it.".format(mode) + SUPERSEDE)

    def test_the_gap_between_recommended_and_deployed_is_the_claim(self):
        """Stated as one assertion so the failure reads as the finding it guards:
        D6 recommends static, the deployment is active, and that is still true."""
        recommends_static = "static" in WEB.split("### D6 — ", 1)[1].split("\n### ", 1)[0].lower()
        deployed_active = getattr(config, "ACTIVE_MODE", None) in config.ASSETS
        self.assertTrue(
            recommends_static and deployed_active,
            "D6 recommends static={} while the deployment is active={} — the two "
            "halves of the bridge no longer agree.".format(recommends_static, deployed_active)
            + SUPERSEDE)

    def test_changing_the_live_mode_needs_signoff(self):
        """The bridge's note says so; config.py is deny-fenced, which is what makes
        that enforceable rather than aspirational."""
        deny = MAP["edit_policy"]["deny"]
        self.assertIn("config.py", deny,
                      "config.py left the deny fence, so 'changing the live mode "
                      "needs sign-off' is no longer mechanically true" + SUPERSEDE)


if __name__ == "__main__":
    unittest.main()
