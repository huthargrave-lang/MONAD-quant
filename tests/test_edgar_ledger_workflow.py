"""
Guards for .github/workflows/edgar-ledger.yml — the second workflow with `contents: write`
(docs/research/EDGAR_LEDGER_QUESTION.md, O4 and condition 1). Mirrors the WorkflowTests of
tests/test_export_pages.py for pages.yml, which inspect only that file: without this sibling
a second writing workflow would be unguarded.

What must hold:
  * `permissions` is exactly `contents: write` — no pages, no id-token;
  * every `git push` names the edgar-ledger branch; no push to development; no `push:` trigger;
  * the schedule is 07:17 UTC and dispatch takes `mode` and `quarter`;
  * nothing fetches Yahoo (no yfinance): this job may only collect what it may publish;
  * `verify` runs before the push, is not best-effort, and uses `--against` only from the
    second run — the branch-creating run is README-only and checks shards alone, because
    verify_history cannot resolve a merge-base for a branch that does not exist yet.
The last point is also RUN offline: the workflow's own shell, extracted from the YAML, is
executed against a local bare repository standing in for GitHub.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "edgar-ledger.yml"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.research import edgar_ledger as el  # noqa: E402
from tests.test_edgar_ledger import passing_summary, write_probe  # noqa: E402


def executable_lines(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def step_block(text: str, name: str) -> list[str]:
    """The lines of the step called ``name`` (from its `- name:` to the next `- `)."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == f"- name: {name}")
    indent = len(lines[start]) - len(lines[start].lstrip())
    out = [lines[start]]
    for ln in lines[start + 1:]:
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= indent:
            break
        out.append(ln)
    return out


def step_run(text: str, name: str) -> str:
    """The step's `run: |` block, dedented: plain shell (every `${{ }}` lives in `env:`)."""
    block = step_block(text, name)
    i = next(k for k, ln in enumerate(block) if ln.strip() == "run: |")
    key_indent = len(block[i]) - len(block[i].lstrip())
    body = []
    for ln in block[i + 1:]:
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= key_indent:
            break
        body.append(ln)
    body_indent = min((len(ln) - len(ln.lstrip())) for ln in body if ln.strip())
    return "\n".join(ln[body_indent:] for ln in body) + "\n"


def step_env_keys(text: str, name: str) -> list[str]:
    block = step_block(text, name)
    try:
        i = next(k for k, ln in enumerate(block) if ln.strip() == "env:")
    except StopIteration:
        return []
    key_indent = len(block[i]) - len(block[i].lstrip())
    keys = []
    for ln in block[i + 1:]:
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= key_indent:
            break
        if ln.strip():
            keys.append(ln.split(":", 1)[0].strip())
    return keys


BOOTSTRAP_STEP = "Check out or bootstrap the edgar-ledger branch"
MODE_STEP = "Run the mode"
VERIFY_STEP = "Verify the ledger (shards always; append-only history from the second run)"
PUSH_STEP = "Commit and push to edgar-ledger"


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wf = WORKFLOW.read_text(encoding="utf-8")
        cls.exe = executable_lines(cls.wf)

    def test_permissions_are_exactly_contents_write(self):
        """contents:write is repo-wide; the claim this guard protects is that the workflow writes
        exactly one thing, rows on the edgar-ledger branch, and publishes nothing."""
        perms = re.search(r"^permissions:\n((?:[ \t]+.*\n|\s*#.*\n)+)", self.exe, re.M)
        self.assertIsNotNone(perms, "no permissions block")
        keys = re.findall(r"^\s+([a-z-]+):\s*(\S+)", perms.group(1), re.M)
        self.assertEqual(keys, [("contents", "write")])
        self.assertNotIn("pages: write", self.exe)
        self.assertNotIn("id-token: write", self.exe)

    def test_every_push_targets_the_edgar_ledger_branch_and_never_development(self):
        pushes = re.findall(r"git push [^\n]*", self.exe)
        self.assertTrue(pushes, "contents:write with no push is a permission nothing uses")
        for push in pushes:
            self.assertIn("edgar-ledger", push, "the workflow pushes to a ref other than edgar-ledger: %r" % push)
        self.assertNotIn("push origin development", self.wf)
        self.assertNotIn("push origin main", self.wf)
        self.assertNotIn("tone-ledger", self.exe)

    def test_it_fires_on_the_07_17_utc_schedule_and_on_dispatch_with_mode_and_quarter_never_on_push(self):
        self.assertNotRegex(self.exe, r"^\s*push:\s*$", "edgar-ledger.yml fires on a push")
        self.assertNotIn("workflow_run:", self.exe)
        self.assertIn('cron: "17 7 * * *"', self.exe)
        self.assertEqual(self.exe.count("cron:"), 1, "one schedule per decision")
        self.assertIn("workflow_dispatch:", self.exe)
        inputs = self.exe.split("workflow_dispatch:", 1)[1].split("permissions:", 1)[0]
        for name in ("mode:", "quarter:", "n:"):
            self.assertIn(name, inputs)
        for mode in ("probe", "fsds", "daily", "sweep", "verify"):
            self.assertIn(mode, inputs)

    def test_concurrency_group_is_edgar_ledger_and_the_job_is_not_cancelled_midway(self):
        conc = self.exe.split("concurrency:", 1)[1][:200]
        self.assertIn("group: edgar-ledger", conc)
        self.assertIn("cancel-in-progress: false", conc)

    def test_nothing_fetches_yahoo_and_the_runtime_is_the_ledger_tool_only(self):
        for forbidden in ("yfinance", "stock_screener.py", "screener_lab.py", "pip install"):
            self.assertNotIn(forbidden, self.exe)
        self.assertIn("python tools/edgar_ledger.py", self.exe)
        for mode in ("probe", "fsds", "daily", "sweep"):
            self.assertRegex(self.exe, rf"edgar_ledger\.py {mode}\b")

    def test_the_sec_user_agent_secret_is_the_only_secret_and_feeds_the_mode_step(self):
        secrets = set(re.findall(r"secrets\.([A-Za-z_]+)", self.wf))
        self.assertEqual(secrets, {"SEC_USER_AGENT"})
        self.assertIn("SEC_USER_AGENT", step_env_keys(self.wf, MODE_STEP))
        self.assertIn("MONAD_EDGAR_LEDGER_DIR", step_env_keys(self.wf, MODE_STEP))

    def test_verify_runs_before_the_push_and_neither_is_best_effort(self):
        """Unlike the tone ledger's continue-on-error steps: a shard problem or an append-only
        violation fails the job, so nothing is pushed."""
        self.assertNotIn("continue-on-error", self.exe)
        order = [self.exe.index(f"- name: {s}") for s in (BOOTSTRAP_STEP, MODE_STEP, VERIFY_STEP, PUSH_STEP)]
        self.assertEqual(order, sorted(order), "steps are out of order")
        self.assertIn("python tools/edgar_ledger.py verify", step_run(self.wf, VERIFY_STEP))

    def test_against_is_used_only_from_the_second_run_and_the_mode_is_skipped_on_bootstrap(self):
        """Condition 1: the branch-creating run is README-only with shard checks and NO
        `verify --against` (there is no origin/edgar-ledger to resolve a merge-base against)."""
        boot = step_run(self.wf, BOOTSTRAP_STEP)
        self.assertIn("git ls-remote --exit-code", boot)
        self.assertIn("cp ../docs/EDGAR_LEDGER.md README.md", boot)
        self.assertIn("bootstrap=true", boot)
        self.assertIn("bootstrap=false", boot)
        self.assertNotIn("edgar_ledger.py", boot, "the bootstrap run writes nothing but the README")
        verify = step_run(self.wf, VERIFY_STEP)
        then_branch, else_branch = verify.split("else", 1)
        self.assertIn('"$BOOTSTRAP" = "true"', then_branch)
        self.assertNotIn("--against", then_branch)
        self.assertIn("verify --against origin/edgar-ledger", else_branch)
        mode_block = "\n".join(step_block(self.exe, MODE_STEP))
        self.assertIn("if: steps.ledger.outputs.bootstrap == 'false'", mode_block)
        self.assertRegex(self.exe, r"- name: " + re.escape(BOOTSTRAP_STEP) + r"\n\s+id: ledger")

    def test_every_github_expression_lives_in_env_so_the_shell_is_runnable_offline(self):
        for step in (BOOTSTRAP_STEP, MODE_STEP, VERIFY_STEP, PUSH_STEP):
            self.assertNotIn("${{", step_run(self.wf, step), f"{step}: a ${{{{ }}}} expression inside run:")


class BootstrapOfflineTests(unittest.TestCase):
    """The workflow's own shell, run against a local bare repository standing in for GitHub."""

    @classmethod
    def setUpClass(cls):
        cls.wf = WORKFLOW.read_text(encoding="utf-8")
        cls.td = tempfile.TemporaryDirectory()
        root = Path(cls.td.name)
        cls.bare = root / "remote.git"
        cls.bare.mkdir()
        subprocess.run(["git", "init", "-q", "--bare", str(cls.bare)], check=True)
        cls.remote = cls.bare.as_uri()            # file:// so --depth 1 really is shallow, as in CI
        cls.shim = root / "bin"
        cls.shim.mkdir()
        os.symlink(sys.executable, cls.shim / "python")

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def workspace(self, name: str) -> Path:
        ws = Path(self.td.name) / name
        (ws / "docs").mkdir(parents=True)
        shutil.copy(REPO / "docs" / "EDGAR_LEDGER.md", ws / "docs" / "EDGAR_LEDGER.md")
        return ws

    def run_step(self, name: str, *, cwd: Path, env: dict, check=True) -> subprocess.CompletedProcess:
        full = dict(os.environ, PATH=f"{self.shim}{os.pathsep}{os.environ.get('PATH', '')}",
                    GIT_TERMINAL_PROMPT="0", SEC_USER_AGENT="MONAD research test hud@monad-quant.org")
        full.update(env)
        return subprocess.run(["bash", "-c", step_run(self.wf, name)], cwd=str(cwd), env=full,
                              capture_output=True, text=True, check=check)

    def outputs(self, path: Path) -> dict:
        return dict(ln.split("=", 1) for ln in path.read_text().splitlines() if "=" in ln)

    def ledger_env(self, ws: Path, bootstrap: str) -> dict:
        return {"MONAD_EDGAR_LEDGER_DIR": str(ws / "ledger" / "data" / "edgar_ledger"), "BOOTSTRAP": bootstrap}

    def test_first_run_is_readme_only_second_run_verifies_against_origin_third_run_refuses_a_rewrite(self):
        # ── run 1: the branch does not exist → bootstrap, README only, shards-only verify, push
        ws1 = self.workspace("ws1")
        out1 = ws1 / "github_output"
        out1.touch()
        self.run_step(BOOTSTRAP_STEP, cwd=ws1, env={"REMOTE": self.remote, "GITHUB_OUTPUT": str(out1)})
        self.assertEqual(self.outputs(out1), {"bootstrap": "true"})
        self.assertTrue((ws1 / "ledger" / "README.md").is_file())
        self.assertFalse((ws1 / "ledger" / "data").exists(), "the bootstrap run must write nothing but the README")
        log = subprocess.run(["git", "-C", str(ws1 / "ledger"), "log", "--oneline"], capture_output=True, text=True).stdout
        self.assertEqual(len(log.splitlines()), 1)
        self.assertIn("README only", log)
        v = self.run_step(VERIFY_STEP, cwd=REPO, env=self.ledger_env(ws1, "true"))
        self.assertIn("0 problem(s)", v.stdout)
        self.assertNotIn("append-only vs", v.stdout, "the bootstrap run must not pass --against")
        self.run_step(PUSH_STEP, cwd=ws1, env={"RUN_NUMBER": "1"})
        heads = subprocess.run(["git", "ls-remote", "--heads", self.remote], capture_output=True, text=True).stdout
        self.assertIn("refs/heads/edgar-ledger", heads)
        self.assertEqual(heads.count("refs/heads/"), 1)

        # ── run 2: the branch exists → depth-1 clone, no data yet, verify --against passes
        ws2 = self.workspace("ws2")
        out2 = ws2 / "github_output"
        out2.touch()
        self.run_step(BOOTSTRAP_STEP, cwd=ws2, env={"REMOTE": self.remote, "GITHUB_OUTPUT": str(out2)})
        self.assertEqual(self.outputs(out2), {"bootstrap": "false"})
        shallow = subprocess.run(["git", "-C", str(ws2 / "ledger"), "rev-parse", "--is-shallow-repository"],
                                 capture_output=True, text=True).stdout.strip()
        self.assertEqual(shallow, "true")
        v = self.run_step(VERIFY_STEP, cwd=REPO, env=self.ledger_env(ws2, "false"))
        self.assertIn("append-only vs origin/edgar-ledger: 0 violation(s)", v.stdout)
        self.assertIn("::warning::", v.stdout)             # no passing probe yet: said out loud
        # a probe lands (as the probe mode would write it), verify still passes, push
        store = el.Store(ws2 / "ledger" / "data" / "edgar_ledger")
        write_probe(store, passing_summary())
        v = self.run_step(VERIFY_STEP, cwd=REPO, env=self.ledger_env(ws2, "false"))
        self.assertIn("0 violation(s)", v.stdout)
        self.run_step(PUSH_STEP, cwd=ws2, env={"RUN_NUMBER": "2"})
        log = subprocess.run(["git", "ls-remote", self.remote, "edgar-ledger"], capture_output=True, text=True).stdout
        self.assertTrue(log.strip())

        # ── run 3: a rewrite of a frozen probe file fails verify, so the push step is never reached
        ws3 = self.workspace("ws3")
        out3 = ws3 / "github_output"
        out3.touch()
        self.run_step(BOOTSTRAP_STEP, cwd=ws3, env={"REMOTE": self.remote, "GITHUB_OUTPUT": str(out3)})
        self.assertEqual(self.outputs(out3), {"bootstrap": "false"})
        probe = next((ws3 / "ledger" / "data" / "edgar_ledger" / "probe").glob("PROBE-*.jsonl"))
        probe.write_text(probe.read_text() + "\n", encoding="utf-8")
        v = self.run_step(VERIFY_STEP, cwd=REPO, env=self.ledger_env(ws3, "false"), check=False)
        self.assertEqual(v.returncode, 1, v.stdout + v.stderr)
        self.assertIn("FAIL history", v.stdout)
        # and the probe-less daily run is a no-op commit that still pushes cleanly (the schedule stays green)
        probe.write_text(probe.read_text()[:-1], encoding="utf-8")
        v = self.run_step(VERIFY_STEP, cwd=REPO, env=self.ledger_env(ws3, "false"))
        self.assertIn("0 violation(s)", v.stdout)
        self.run_step(PUSH_STEP, cwd=ws3, env={"RUN_NUMBER": "3"})


if __name__ == "__main__":
    unittest.main()
