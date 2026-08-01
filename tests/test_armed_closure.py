"""tools/armed_closure.py — the armed boundary, derived rather than declared.

Two hand-maintained lists in this repo claim to know which files are dangerous:
context_map.json's `edit_policy.deny`, and ops/git_drift.sh's ARMED_PATHS. Both
were written by someone reading the code and typing what they saw. That is the
same epistemic move that produced the 129-commit incident — a belief about state,
held without a mechanism to keep it true.

So these tests do two things:

  1. Record the gap that already exists. live/trader.py imports live/signals.py,
     which imports src/data/fetcher.py and src/strategy/engine.py, which imports
     src/signals/*. Those decide when the bot buys, and the deny fence does not
     mention them. This is asserted, not lamented, so it cannot quietly stop
     being true in either direction.

  2. Bind ops/git_drift.sh's ARMED_PATHS to the computed closure, so the armed
     drift count cannot silently under-report as the import graph grows.
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import armed_closure  # noqa: E402


class ClosureReach(unittest.TestCase):
    def test_seed_and_live_package_are_included(self):
        c = armed_closure.closure(REPO)
        for expected in ("live/trader.py", "live/broker.py", "live/state.py",
                         "live/signals.py", "config.py"):
            self.assertIn(expected, c)

    def test_src_modules_reached_via_live_signals_are_armed(self):
        """The finding: signal parameters live outside the fence but inside the
        arming path. Editing src/signals/momentum.py changes when the bot buys."""
        c = armed_closure.closure(REPO)
        for expected in ("src/signals/momentum.py", "src/signals/volume.py",
                         "src/signals/volatility.py", "src/strategy/engine.py",
                         "src/data/fetcher.py"):
            self.assertIn(expected, c, f"{expected} is reachable from live/trader.py")

    def test_third_party_is_not_in_the_closure(self):
        """pandas and ib_insync are dependencies, not files whose edits here change
        trading behaviour. Including them would make the boundary meaningless."""
        c = armed_closure.closure(REPO)
        joined = " ".join(c)
        for noise in ("pandas", "ib_insync", "apscheduler", "yfinance"):
            self.assertNotIn(noise, joined)

    def test_closure_is_deterministic(self):
        self.assertEqual(armed_closure.closure(REPO), armed_closure.closure(REPO))

    def test_a_missing_seed_yields_empty_not_an_exception(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(armed_closure.closure(Path(d)), [])


class TheFenceGapIsReal(unittest.TestCase):
    def test_the_deny_fence_does_not_cover_the_whole_closure(self):
        gap = armed_closure.unfenced(REPO)
        self.assertTrue(gap, "if this ever passes empty, the fence was widened — "
                             "update this test deliberately, do not delete it")
        self.assertTrue(any(p.startswith("src/signals/") for p in gap))

    def test_live_and_config_are_fenced(self):
        pats = armed_closure.deny_patterns(REPO)
        for p in ("live/trader.py", "live/broker.py", "config.py"):
            self.assertTrue(armed_closure.is_fenced(p, pats), f"{p} must stay fenced")

    def test_pattern_matching_handles_dirs_globs_and_exact(self):
        pats = ["live/", "config.py", "*.db"]
        self.assertTrue(armed_closure.is_fenced("live/deep/x.py", pats))
        self.assertTrue(armed_closure.is_fenced("config.py", pats))
        self.assertTrue(armed_closure.is_fenced("live/state.db", pats))
        self.assertFalse(armed_closure.is_fenced("src/signals/momentum.py", pats))


class DriftOracleStaysHonest(unittest.TestCase):
    """ops/git_drift.sh counts 'how many incoming commits touch armed paths'. If its
    hand-written prefix list falls behind the import graph, that count silently
    under-reports — the exact shape of the bug the oracle exists to prevent."""

    def _armed_paths_from_script(self):
        src = (REPO / "ops" / "git_drift.sh").read_text()
        block = re.search(r"ARMED_PATHS=\((.*?)\)", src, re.S)
        self.assertIsNotNone(block, "ARMED_PATHS array not found in ops/git_drift.sh")
        return re.findall(r'"([^"]+)"', block.group(1))

    def test_every_closure_member_is_covered_by_the_drift_oracle(self):
        patterns = self._armed_paths_from_script()
        for member in armed_closure.closure(REPO):
            covered = any(
                member.startswith(p) if p.endswith("/") else member == p
                for p in patterns
            )
            self.assertTrue(
                covered,
                f"{member} is in the armed import closure but ops/git_drift.sh's "
                f"ARMED_PATHS does not match it — armed_behind would under-report",
            )


class CommandLine(unittest.TestCase):
    def test_unfenced_flag_exits_nonzero_while_a_gap_exists(self):
        p = subprocess.run([sys.executable, str(REPO / "tools" / "armed_closure.py"),
                            "--unfenced"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("src/signals/", p.stdout)

    def test_json_output_is_wellformed(self):
        import json
        p = subprocess.run([sys.executable, str(REPO / "tools" / "armed_closure.py"),
                            "--json"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        d = json.loads(p.stdout)
        self.assertEqual(set(d), {"seed", "closure", "deny_patterns", "unfenced"})


if __name__ == "__main__":
    unittest.main()
