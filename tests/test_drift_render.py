"""tools/drift_render.py — the drift fact, turned into a line a human reads.

The property under test is not formatting taste. It is that this renderer can
never go quiet. For seven days `ctx status` printed

    branch=development  clean=no

next to nothing at all, while the checkout sat 129 commits behind origin. A
surface that says nothing when its sensor is dead reads exactly like a surface
saying "fine". So every bad input — missing file, malformed JSON, unknown
verdict, null counts — must still produce a visible UNKNOWN, and the renderer
must never raise, because callers embed it in status output and (later) in
scripts whose exit status gates arming.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import drift_render  # noqa: E402


def artifact(**over):
    base = {"schema": 1, "branch": "development", "verdict": "in_sync",
            "reason": "ok", "fetch_ok": True, "fetch_age_sec": 30,
            "behind": 0, "ahead": 0, "local_head": "aaa", "remote_head": "aaa",
            "armed_behind": 0, "armed_differs": False}
    base.update(over)
    d = Path(tempfile.mkdtemp()) / "git_drift.json"
    d.write_text(json.dumps(base))
    return d


class NeverGoesQuiet(unittest.TestCase):
    def test_missing_file_is_a_visible_unknown(self):
        out = drift_render.render(Path(tempfile.mkdtemp()) / "nope.json")
        self.assertTrue(out.strip())
        self.assertIn("UNKNOWN", out)

    def test_malformed_json_is_a_visible_unknown(self):
        p = Path(tempfile.mkdtemp()) / "git_drift.json"
        p.write_text("{oh no")
        self.assertIn("UNKNOWN", drift_render.render(p))

    def test_json_that_is_not_an_object_is_unknown(self):
        p = Path(tempfile.mkdtemp()) / "git_drift.json"
        p.write_text("[1,2,3]")
        self.assertIn("UNKNOWN", drift_render.render(p))

    def test_unrecognised_verdict_is_unknown_not_echoed(self):
        out = drift_render.render(artifact(verdict="probably_fine"))
        self.assertIn("UNKNOWN", out)

    def test_it_never_raises_on_any_of_these(self):
        bad = [Path("/nonexistent/x.json")]
        p = Path(tempfile.mkdtemp()) / "b.json"; p.write_text("null"); bad.append(p)
        q = Path(tempfile.mkdtemp()) / "c.json"; q.write_text(""); bad.append(q)
        for b in bad:
            self.assertIsInstance(drift_render.render(b), str)


class SaysTheUsefulThing(unittest.TestCase):
    def test_in_sync_names_the_branch_and_freshness(self):
        out = drift_render.render(artifact(verdict="in_sync", fetch_age_sec=120))
        self.assertIn("in sync with origin/development", out)
        self.assertIn("2m ago", out)

    def test_the_incident_shape_reports_counts_and_armed_paths(self):
        """The exact line that was missing for seven days."""
        out = drift_render.render(artifact(
            verdict="diverged", behind=129, ahead=8,
            armed_behind=6, armed_differs=True, fetch_age_sec=0))
        self.assertIn("DIVERGED", out)
        self.assertIn("129 behind", out)
        self.assertIn("8 ahead", out)
        self.assertIn("6 touch ARMED paths", out)
        self.assertIn("armed files DIFFER", out)

    def test_research_only_drift_does_not_cry_armed(self):
        out = drift_render.render(artifact(verdict="behind", behind=40,
                                           armed_behind=0, armed_differs=False))
        self.assertIn("40 behind", out)
        self.assertNotIn("ARMED", out)

    def test_unknown_verdict_carries_the_reason_through(self):
        out = drift_render.render(artifact(verdict="unknown",
                                           reason="no fetch stamp — never succeeded"))
        self.assertIn("UNKNOWN", out)
        self.assertIn("no fetch stamp", out)

    def test_null_counts_do_not_render_as_zero(self):
        """behind=null means 'unknown', and must never be shown as '0 behind'."""
        out = drift_render.render(artifact(verdict="unknown", behind=None,
                                           ahead=None, reason="stale stamp"))
        self.assertNotIn("0 behind", out)


class AgeFormatting(unittest.TestCase):
    def test_ages(self):
        for secs, want in ((5, "just now"), (300, "5m ago"), (7200, "2h ago")):
            with self.subTest(secs=secs):
                self.assertIn(want, drift_render.render(
                    artifact(verdict="in_sync", fetch_age_sec=secs)))

    def test_missing_age_is_not_a_crash(self):
        self.assertIn("age unknown", drift_render.render(
            artifact(verdict="in_sync", fetch_age_sec=None)))


class WiredIntoStatusCheck(unittest.TestCase):
    def test_status_check_uses_the_shared_renderer(self):
        """Not a duplicated heredoc — surfaces must agree by construction."""
        src = (REPO / "ops" / "status_check.sh").read_text()
        self.assertIn("tools/drift_render.py", src)

    def test_status_check_has_a_fallback_if_the_renderer_is_missing(self):
        src = (REPO / "ops" / "status_check.sh").read_text()
        self.assertIn("UNKNOWN (drift renderer unavailable)", src)


if __name__ == "__main__":
    unittest.main()
