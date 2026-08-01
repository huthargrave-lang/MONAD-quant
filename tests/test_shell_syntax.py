"""Every shipped shell script must parse.

This is a small test guarding a large failure. ops/preflight_trader_start.sh runs
as monad-trader.service's ExecStartPre: if it does not parse, ExecStartPre exits
non-zero, the trader never starts — and ops/rearm_trader.sh, which gates on that
same exit code, cannot recover it either. A stray quote takes the bot down for a
session, and nothing else in the suite would notice, because no test executes
these scripts.

`bash -n` is a parse, not a run: it never executes a command, connects to a
broker, or touches state.db. Safe to run against the armed scripts precisely
because it does not run them.
"""

import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def shell_scripts():
    found = []
    for d in ("ops", "deploy"):
        found += sorted((REPO / d).rglob("*.sh"))
    return found


class ShellScriptsParse(unittest.TestCase):
    def test_there_are_scripts_to_check(self):
        """Guard against the check silently covering nothing."""
        self.assertGreaterEqual(len(shell_scripts()), 5)

    def test_every_script_parses(self):
        for path in shell_scripts():
            with self.subTest(script=str(path.relative_to(REPO))):
                p = subprocess.run(["bash", "-n", str(path)],
                                   capture_output=True, text=True)
                self.assertEqual(p.returncode, 0,
                                 f"{path.relative_to(REPO)} does not parse:\n{p.stderr}")

    def test_the_cold_start_gates_are_actually_covered(self):
        """Name them explicitly: these two decide whether the bot can arm, so their
        coverage must not depend on a glob continuing to match."""
        covered = {str(p.relative_to(REPO)) for p in shell_scripts()}
        for critical in ("ops/preflight_trader_start.sh", "ops/start_trader.sh",
                         "ops/rearm_trader.sh"):
            self.assertIn(critical, covered)


if __name__ == "__main__":
    unittest.main()
