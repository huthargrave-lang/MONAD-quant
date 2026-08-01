"""ops/git_drift.sh + ops/fetch_origin.sh — the drift oracle.

The bug these guard against, precisely: on 2026-07-31 this checkout was found to
be 129 commits behind origin/development, and had been for a week, while every
surface reported healthy. No scheduled `git fetch` existed, so the remote ref
never moved and `rev-list HEAD...origin/development` truthfully reported
behind=0 against stale evidence.

So the invariant under test is NOT "the counts are right". It is:

    a drift sensor must never report a number when it cannot know the number.

`behind` is null — never 0 — whenever the fetch is missing, stale or unparseable.
Anything that renders null as "0 behind" resurrects the original bug, which is
why the null is asserted explicitly rather than via a truthiness check.

Second invariant: the oracle must never be able to stop the bot arming. It exits
0 unconditionally, including when git itself fails.
"""

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DRIFT = REPO / "ops" / "git_drift.sh"
FETCH = REPO / "ops" / "fetch_origin.sh"


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


class DriftFixture(unittest.TestCase):
    """A real two-repo fixture: a bare 'origin' and a working clone.

    Deliberately not mocked. The failure being guarded is about how git and the
    filesystem actually behave (which ref moves when, what a stale stamp looks
    like), so a stubbed git would test the wrong thing.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.origin = root / "origin.git"
        self.work = root / "work"

        git(root, "init", "--bare", "-b", "development", str(self.origin))
        seed = root / "seed"
        seed.mkdir()
        git(seed, "init", "-b", "development")
        (seed / "README.md").write_text("seed\n")
        git(seed, "add", "-A"); git(seed, "commit", "-m", "seed")
        git(seed, "remote", "add", "origin", str(self.origin))
        git(seed, "push", "-q", "origin", "development")

        git(root, "clone", "-q", "-b", "development", str(self.origin), str(self.work))
        (self.work / "local_logs").mkdir(exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    # ── helpers ──────────────────────────────────────────────────────────────
    def run_drift(self, max_age=None):
        env = {**os.environ, "MONAD_REPO": str(self.work), "MONAD_DEPLOY_BRANCH": "development"}
        if max_age is not None:
            env["MONAD_DRIFT_MAX_AGE_SEC"] = str(max_age)
        proc = subprocess.run(["bash", str(DRIFT)], capture_output=True, text=True, env=env)
        out = self.work / "local_logs" / "git_drift.json"
        payload = json.loads(out.read_text()) if out.exists() else None
        return proc, payload

    def stamp(self, epoch=None):
        p = self.work / "local_logs" / ".git_fetch_stamp"
        p.write_text(f"{int(time.time()) if epoch is None else epoch}\n")

    def commit_on_origin(self, relpath, body="x\n", msg="upstream"):
        """Land a commit on origin and make it visible to the clone's remote ref."""
        seed = Path(self.tmp.name) / "seed"
        target = seed / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
        git(seed, "add", "-A"); git(seed, "commit", "-m", msg)
        git(seed, "push", "-q", "origin", "development")
        git(self.work, "fetch", "-q", "origin", "development")


class UnknownIsNotClean(DriftFixture):
    """The core regression: absence of evidence must not read as absence of drift."""

    def test_missing_stamp_is_unknown_and_behind_is_null(self):
        self.commit_on_origin("docs/a.md")          # genuinely 1 behind...
        _, d = self.run_drift()                      # ...but no stamp exists
        self.assertEqual(d["verdict"], "unknown")
        self.assertIsNone(d["behind"], "behind must be null, never 0, when unknown")
        self.assertIsNone(d["ahead"])
        self.assertFalse(d["fetch_ok"])

    def test_stale_stamp_is_unknown_not_a_stale_count(self):
        self.commit_on_origin("docs/a.md")
        self.stamp(epoch=1)                          # 1970
        _, d = self.run_drift()
        self.assertEqual(d["verdict"], "unknown")
        self.assertIsNone(d["behind"])
        self.assertIn("stale", d["reason"])

    def test_unparseable_stamp_is_unknown(self):
        (self.work / "local_logs" / ".git_fetch_stamp").write_text("not-a-number\n")
        _, d = self.run_drift()
        self.assertEqual(d["verdict"], "unknown")
        self.assertIsNone(d["behind"])

    def test_a_fresh_stamp_does_not_by_itself_invent_counts(self):
        """Freshness gates the counts; it must not fabricate them."""
        self.stamp()
        _, d = self.run_drift()
        self.assertEqual(d["verdict"], "in_sync")
        self.assertEqual(d["behind"], 0)             # 0 is legitimate ONLY when known
        self.assertTrue(d["fetch_ok"])


class VerdictsAreThreeValued(DriftFixture):
    def test_behind(self):
        self.commit_on_origin("docs/a.md"); self.stamp()
        _, d = self.run_drift()
        self.assertEqual(d["verdict"], "behind")
        self.assertEqual((d["behind"], d["ahead"]), (1, 0))

    def test_ahead(self):
        (self.work / "local.md").write_text("mine\n")
        git(self.work, "add", "-A"); git(self.work, "commit", "-m", "local only")
        self.stamp()
        _, d = self.run_drift()
        self.assertEqual(d["verdict"], "ahead")
        self.assertEqual((d["behind"], d["ahead"]), (0, 1))

    def test_diverged(self):
        self.commit_on_origin("docs/a.md")
        (self.work / "local.md").write_text("mine\n")
        git(self.work, "add", "-A"); git(self.work, "commit", "-m", "local only")
        self.stamp()
        _, d = self.run_drift()
        self.assertEqual(d["verdict"], "diverged")
        self.assertEqual((d["behind"], d["ahead"]), (1, 1))


class ArmedPathDrift(DriftFixture):
    """'129 behind' is unreadable; '129 behind, 6 of them armed' is actionable."""

    def test_research_churn_is_not_counted_as_armed(self):
        self.commit_on_origin("docs/research/study.md"); self.stamp()
        _, d = self.run_drift()
        self.assertEqual(d["behind"], 1)
        self.assertEqual(d["armed_behind"], 0)
        self.assertFalse(d["armed_differs"])

    def test_armed_path_commit_is_counted_and_flagged(self):
        self.commit_on_origin("live/trader.py", "raise SystemExit\n"); self.stamp()
        _, d = self.run_drift()
        self.assertEqual(d["armed_behind"], 1)
        self.assertTrue(d["armed_differs"])

    def test_src_modules_reached_at_arming_time_count_as_armed(self):
        """live/signals.py imports src/signals/* and src/strategy/engine.py at arming
        time, so they can change trading behaviour even though context_map.json's
        deny fence does not list them. The oracle must not inherit that blind spot."""
        self.commit_on_origin("src/signals/momentum.py", "RSI=1\n"); self.stamp()
        _, d = self.run_drift()
        self.assertEqual(d["armed_behind"], 1, "src/signals/ is armed in effect")
        self.assertTrue(d["armed_differs"])


class NeverBlocksArming(DriftFixture):
    """Nothing here may ever become a reason the bot refuses to start."""

    def test_exits_zero_with_no_stamp(self):
        p, _ = self.run_drift()
        self.assertEqual(p.returncode, 0)

    def test_exits_zero_when_the_repo_is_not_a_repo(self):
        broken = Path(self.tmp.name) / "notarepo"
        broken.mkdir()
        p = subprocess.run(["bash", str(DRIFT)], capture_output=True, text=True,
                           env={**os.environ, "MONAD_REPO": str(broken)})
        self.assertEqual(p.returncode, 0)

    def test_fetch_script_exits_zero_when_origin_is_unreachable(self):
        git(self.work, "remote", "set-url", "origin", str(Path(self.tmp.name) / "gone.git"))
        p = subprocess.run(["bash", str(FETCH)], capture_output=True, text=True,
                           env={**os.environ, "MONAD_REPO": str(self.work)})
        self.assertEqual(p.returncode, 0)

    def test_failed_fetch_writes_no_stamp_so_the_verdict_stays_unknown(self):
        """A failed fetch must not look like a successful one."""
        git(self.work, "remote", "set-url", "origin", str(Path(self.tmp.name) / "gone.git"))
        subprocess.run(["bash", str(FETCH)], capture_output=True,
                       env={**os.environ, "MONAD_REPO": str(self.work)})
        self.assertFalse((self.work / "local_logs" / ".git_fetch_stamp").exists())
        _, d = self.run_drift()
        self.assertEqual(d["verdict"], "unknown")
        self.assertIsNone(d["behind"])


class FetchStamping(DriftFixture):
    def test_successful_fetch_writes_a_parseable_recent_stamp(self):
        p = subprocess.run(["bash", str(FETCH)], capture_output=True, text=True,
                           env={**os.environ, "MONAD_REPO": str(self.work)})
        self.assertEqual(p.returncode, 0)
        raw = (self.work / "local_logs" / ".git_fetch_stamp").read_text().strip()
        self.assertTrue(raw.isdigit())
        self.assertLess(abs(int(time.time()) - int(raw)), 120)

    def test_fetch_then_drift_is_in_sync_end_to_end(self):
        subprocess.run(["bash", str(FETCH)], capture_output=True,
                       env={**os.environ, "MONAD_REPO": str(self.work)})
        _, d = self.run_drift()
        self.assertEqual(d["verdict"], "in_sync")
        self.assertTrue(d["fetch_ok"])


class ArtifactShape(DriftFixture):
    def test_payload_is_valid_json_with_a_stable_key_set(self):
        self.stamp()
        _, d = self.run_drift()
        self.assertEqual(
            set(d),
            {"schema", "time_utc", "branch", "verdict", "reason", "fetch_ok",
             "fetch_age_sec", "behind", "ahead", "local_head", "remote_head",
             "armed_behind", "armed_differs"},
        )
        self.assertEqual(d["schema"], 1)

    def test_verdict_is_always_one_of_the_five(self):
        self.stamp()
        _, d = self.run_drift()
        self.assertIn(d["verdict"], {"in_sync", "behind", "ahead", "diverged", "unknown"})


if __name__ == "__main__":
    unittest.main()
