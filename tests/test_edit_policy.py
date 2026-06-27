"""Pins the safe-write fence (KA7) so it can't silently regress — the night-review
R5 finding was that the deny policy + guard hook were enforced by nobody and had no
test. Asserts (1) the edit_policy deny set covers the protected paths, (2) the
ops/guard_edit.py PreToolUse hook DENYs them and ALLOWs benign files, and (3) the
secret scanner is clean on the tracked tree but trips on a planted secret."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _guard(path):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "ops", "guard_edit.py")],
                       input=json.dumps({"tool_input": {"file_path": path}}),
                       capture_output=True, text=True)
    return r.stdout.strip()


class TestEditPolicyFence(unittest.TestCase):
    def setUp(self):
        self.deny = json.load(open(os.path.join(ROOT, "context_map.json")))["edit_policy"]["deny"]

    def test_deny_covers_protected_paths(self):
        # context_map.json is the fence policy itself — it must stay denied so the
        # deny list can't be silently edited away (VD-3b).
        for needed in ("live/", "config.py", "*.db", ".env", "context_map.json"):
            self.assertIn(needed, self.deny, f"edit_policy.deny lost {needed!r}")

    def test_guard_denies_protected(self):
        for p in ("live/trader.py", "config.py", ".env", "live/state.db", "context_map.json"):
            self.assertIn('"permissionDecision": "deny"', _guard(p), f"{p} should be DENIED")

    def test_guard_allows_benign(self):
        for p in ("AGENT_INDEX.md", "tools/ctx.py", "docs/whatever.md"):
            self.assertEqual(_guard(p), "", f"{p} should be ALLOWED (empty)")


class TestSecretScan(unittest.TestCase):
    def test_tracked_tree_is_clean(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "ops", "secret_scan.py")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_catches_planted_secret(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", dir=ROOT, delete=False) as fh:
            # built via %-format so THIS source line doesn't itself trip the scanner
            fh.write('%s = "%s"\n' % ("api_key", "AKIAPLANTED123456"))
            tmp = fh.name
        try:
            r = subprocess.run([sys.executable, os.path.join(ROOT, "ops", "secret_scan.py"), tmp],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
        finally:
            os.unlink(tmp)


class TestSessionOrient(unittest.TestCase):
    """The SessionStart hook (ops/session_orient.py) must emit a valid additionalContext
    envelope that pushes navigation via ctx — and never crash (fail-safe)."""

    def _run(self, project_dir):
        e = dict(os.environ)
        e["CLAUDE_PROJECT_DIR"] = project_dir
        return subprocess.run([sys.executable, os.path.join(ROOT, "ops", "session_orient.py")],
                              input="{}", capture_output=True, text=True, env=e)

    def test_emits_valid_session_start_context(self):
        r = self._run(ROOT)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d["hookSpecificOutput"]["hookEventName"], "SessionStart")
        ac = d["hookSpecificOutput"]["additionalContext"]
        self.assertIn("NAVIGATION", ac)
        self.assertIn("ctx.py route", ac)

    def test_fail_safe_when_ctx_unavailable(self):
        # A bad project dir means `ctx brief` can't run, but the directive must still inject.
        r = self._run("/nonexistent")
        self.assertEqual(r.returncode, 0, r.stderr)
        ac = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("NAVIGATION", ac)


if __name__ == "__main__":
    unittest.main()
