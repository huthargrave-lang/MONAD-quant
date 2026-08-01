"""deploy/smoke-test.sh must not disturb the thing it is checking.

Step 4 used to call `live.state.init_db()` directly. That function uses the
hardcoded live/state.py _DB_PATH and applies conditional `ALTER TABLE`
migrations to `position`, `trades` and `signal_snapshot` — so the documented
pre-flight check opened the LIVE trading database for write and took a lock on
it, potentially while the trader was mid-cycle holding a real position.

The migrations are conditional and therefore usually no-ops, which is exactly
what made it easy to miss: the damage is not schema corruption but lock
contention with a running trader, on a database whose `position` row is the
bot's only record of what it owns.

A read-only diagnostic that can write to live state is not read-only.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SMOKE = REPO / "deploy" / "smoke-test.sh"


class NeverTouchesLiveState(unittest.TestCase):
    def test_init_db_is_not_called_against_the_default_path(self):
        """The bare form is the bug: it resolves to live/state.db."""
        src = SMOKE.read_text()
        self.assertNotRegex(
            src, r"import live\.state;\s*live\.state\.init_db\(\)",
            "smoke-test calls init_db() without redirecting _DB_PATH — that is the live DB",
        )

    def test_the_db_path_is_redirected_before_init(self):
        src = SMOKE.read_text()
        self.assertIn("live.state._DB_PATH", src)
        self.assertIn("mktemp -d", src)

    def test_running_it_leaves_the_live_db_mtime_untouched(self):
        db = REPO / "live" / "state.db"
        if not db.exists():
            self.skipTest("no live/state.db in this checkout")
        before = db.stat().st_mtime_ns
        subprocess.run(["bash", str(SMOKE)], cwd=REPO, capture_output=True,
                       text=True, timeout=900)
        self.assertEqual(db.stat().st_mtime_ns, before,
                         "deploy/smoke-test.sh modified the live trading database")

    def test_no_step_writes_to_live_state_db_by_name(self):
        for line in SMOKE.read_text().splitlines():
            s = line.strip()
            if s.startswith("#"):
                continue
            self.assertNotIn("live/state.db", s,
                             "smoke-test must not reference the live DB path directly")


class StillActuallyChecksSomething(unittest.TestCase):
    """A scope fix must not turn the check into a no-op."""

    def test_it_still_exercises_the_real_schema_code(self):
        self.assertIn("live.state.init_db()", SMOKE.read_text())

    def test_it_cleans_up_its_temp_dir(self):
        self.assertIn('rm -rf "$SMOKE_DB_DIR"', SMOKE.read_text())

    def test_all_seven_steps_still_run_and_pass(self):
        p = subprocess.run(["bash", str(SMOKE)], cwd=REPO, capture_output=True,
                           text=True, timeout=900)
        steps = re.findall(r"^\[(\d)/7\]", p.stdout, re.M)
        self.assertEqual(steps, ["1", "2", "3", "4", "5", "6", "7"],
                         f"not all steps ran:\n{p.stdout}")
        self.assertEqual(p.returncode, 0, p.stdout)


if __name__ == "__main__":
    unittest.main()
