"""The two drift surfaces that live on arming-gate scripts.

ops/status_check.sh and `ctx brief` are read-only and could carry the drift fact
safely. These two cannot be assumed safe, because both scripts decide whether the
bot starts:

  * ops/healthcheck.sh — add_problem() sets warn=1 -> status="warn" -> preflight
    check 10 fails -> the trader does not start, on BOTH cold-start paths.
  * ops/preflight_trader_start.sh — is ExecStartPre. A non-zero exit stops the
    09:22 timer AND ops/rearm_trader.sh, which gates on the same exit code.

So drift is RECORDED in both and votes in neither. Two measured hazards shape the
implementation, and neither is hypothetical:

  1. Under `set -uo pipefail`, an unbound expansion aborts the script where it
     stands. In healthcheck that happens BEFORE the `cat > "$JSON"` heredoc, so
     healthcheck.json is never written — and preflight check 10 treats a missing
     file as a PASS. A bug in the drift block would therefore silently disable the
     whole health gate (gateway-down, port-closed, disk-full all stop voting)
     while arming proceeds. In preflight it aborts before `exit 0`, blocking
     arming without ever calling fail(): a veto with no verdict.

  2. `fail` called from inside a subshell cannot increment the parent's counter,
     so a subshell cannot vote even if it tried. That is why the probes are
     subshells — belt as well as braces.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HEALTH = REPO / "ops" / "healthcheck.sh"
PREFLIGHT = REPO / "ops" / "preflight_trader_start.sh"
ARTIFACT = REPO / "local_logs" / "git_drift.json"

# Every way the drift artifact can be broken. The surfaces must be identical
# under all of them — that is the whole safety claim.
BROKEN = {"missing": None, "malformed": "{oh no", "empty": "", "notjson": "null",
          "wrongshape": '{"verdict": 12345}'}


class _ArtifactStates(unittest.TestCase):
    """Mutates the real artifact, restoring it afterwards."""

    def setUp(self):
        self.backup = tempfile.NamedTemporaryFile(delete=False).name
        if ARTIFACT.exists():
            shutil.copy(ARTIFACT, self.backup)
        else:
            self.backup = None

    def tearDown(self):
        if self.backup:
            shutil.copy(self.backup, ARTIFACT)
        elif ARTIFACT.exists():
            ARTIFACT.unlink()

    @staticmethod
    def _set(state):
        content = BROKEN[state]
        if content is None:
            ARTIFACT.unlink(missing_ok=True)
        else:
            ARTIFACT.write_text(content)

    @staticmethod
    def _code(path, start, stop):
        """Source between two markers, with whole-line comments removed. The prose
        in these blocks explains why they must not call add_problem — searching raw
        text finds that explanation and fails on it."""
        src = path.read_text()
        block = src[src.index(start):src.index(stop)]
        return "\n".join(l for l in block.splitlines() if not l.lstrip().startswith("#"))



class HealthcheckRecordsButNeverVotes(_ArtifactStates):
    def test_the_drift_block_never_calls_add_problem(self):
        """add_problem is the only route from this file into preflight's verdict."""
        code = self._code(HEALTH, "Deploy sync", 'status="ok"')
        self.assertNotIn("add_problem", code)
        self.assertNotIn("warn=1", code)

    def test_the_json_carries_the_drift_fields(self):
        subprocess.run(["bash", str(HEALTH)], capture_output=True, timeout=180)
        d = json.loads((REPO / "local_logs" / "healthcheck.json").read_text())
        for key in ("git_drift_verdict", "git_drift_behind", "git_drift_armed_behind"):
            self.assertIn(key, d)

    def test_drift_never_appears_in_problems(self):
        subprocess.run(["bash", str(HEALTH)], capture_output=True, timeout=180)
        d = json.loads((REPO / "local_logs" / "healthcheck.json").read_text())
        self.assertNotIn("drift", d["problems"].lower())
        self.assertNotIn("behind", d["problems"].lower())

    def test_exit_status_is_identical_for_every_broken_artifact(self):
        def rc():
            return subprocess.run(["bash", str(HEALTH)], capture_output=True,
                                  timeout=180).returncode
        baseline = rc()
        for state in BROKEN:
            with self.subTest(state=state):
                self._set(state)
                self.assertEqual(rc(), baseline,
                                 f"a {state} drift artifact changed healthcheck's verdict")

    def test_the_json_is_still_written_and_valid_for_every_broken_artifact(self):
        """The sharp one: if the heredoc aborts, preflight check 10 fails OPEN and
        the entire health gate silently stops voting."""
        out = REPO / "local_logs" / "healthcheck.json"
        for state in BROKEN:
            with self.subTest(state=state):
                self._set(state)
                subprocess.run(["bash", str(HEALTH)], capture_output=True, timeout=180)
                self.assertTrue(out.exists(), "healthcheck.json was not written")
                d = json.loads(out.read_text())        # raises if truncated
                self.assertEqual(d["git_drift_verdict"], "unknown")


class PreflightReportsButNeverGates(_ArtifactStates):

    def test_the_drift_block_uses_report_not_fail(self):
        code = self._code(PREFLIGHT, "Deploy sync", 'if [ "$fails" -gt 0 ]')
        self.assertIn("report ", code)
        self.assertNotIn("fail ", code)

    def test_the_probe_is_isolated_on_all_three_axes(self):
        code = self._code(PREFLIGHT, "Deploy sync", 'if [ "$fails" -gt 0 ]')
        self.assertIn("set +u", code, "an unbound expansion would abort preflight")
        self.assertIn("timeout ", code, "an unbounded probe could hang ExecStartPre")
        self.assertIn("|| true", code, "a non-zero probe must not propagate")

    def test_the_fail_count_is_identical_for_every_broken_artifact(self):
        def fails():
            out = subprocess.run(["bash", str(PREFLIGHT)], capture_output=True,
                                 text=True, timeout=300).stdout
            return out.count("[FAIL]")
        baseline = fails()
        for state in BROKEN:
            with self.subTest(state=state):
                self._set(state)
                self.assertEqual(fails(), baseline,
                                 f"a {state} drift artifact changed preflight's verdict")

    def test_it_still_reports_loudly_when_the_artifact_is_gone(self):
        self._set("missing")
        out = subprocess.run(["bash", str(PREFLIGHT)], capture_output=True,
                             text=True, timeout=300).stdout
        line = [l for l in out.splitlines() if "deploy sync" in l]
        self.assertTrue(line, "the advisory vanished instead of saying UNKNOWN")
        self.assertIn("[INFO]", line[0])
        self.assertIn("UNKNOWN", line[0])

    def test_the_advisory_is_info_not_fail(self):
        out = subprocess.run(["bash", str(PREFLIGHT)], capture_output=True,
                             text=True, timeout=300).stdout
        for line in out.splitlines():
            if "deploy sync" in line:
                self.assertTrue(line.startswith("[INFO]"), line)


class TheHazardsAreReal(unittest.TestCase):
    """Document the two shell behaviours the isolation exists for, by measuring
    them — so a future reader cannot mistake the ceremony for superstition."""

    def test_an_unbound_expansion_aborts_the_rest_of_the_script(self):
        p = subprocess.run(
            ["bash", "-c", 'set -uo pipefail; echo A; echo "${NOPE}"; echo B; exit 0'],
            capture_output=True, text=True)
        self.assertIn("A", p.stdout)
        self.assertNotIn("B", p.stdout, "set -u no longer aborts — revisit the isolation")

    def test_fail_inside_a_subshell_cannot_vote(self):
        p = subprocess.run(
            ["bash", "-c", 'fails=0; fail(){ fails=$((fails+1)); }; ( fail x ); echo $fails'],
            capture_output=True, text=True)
        self.assertEqual(p.stdout.strip(), "0")


if __name__ == "__main__":
    unittest.main()
