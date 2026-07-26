"""CLI smoke test for the agent-facing tools (H12/DP-5).

The unit tests import `ctx` and call `cmd_*` functions directly. That leaves a real gap:
argument wiring, module-level imports reached only on a given path, and `main()`'s
dispatch are never exercised as a *process*. A command can therefore be broken for every
actual user while the suite stays green.

This is not hypothetical. `ctx stale` shipped in this repo with a `NameError` on a
module-level import that its own unit tests did not reach — it surfaced only because the
command was run by hand. That is exactly the failure this file exists to catch.

**What it asserts.** Every registered `ctx` subcommand runs as a subprocess with real
argv and exits without a traceback. Commands are grouped by how they must behave:

* `RUNS_CLEAN` — must exit 0.
* `EXIT_CODE_IS_MEANINGFUL` — may exit non-zero to signal findings (`web --lint`), so
  only the absence of a crash is asserted.
* `NOT_SMOKED` — long-running or stateful commands (`serve`, `init --write`), named here
  so the exclusion is deliberate rather than an oversight, and asserted to be exactly
  this set.

**Scope, stated plainly.** A smoke test proves a command does not crash. It proves
nothing about whether the output is correct — that is what the per-command unit tests are
for. Both are needed; neither substitutes.
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CTX = ROOT / "tools" / "ctx.py"
NOTE = ROOT / "tools" / "note.py"

# A representative, safe argument for every subcommand that needs one.
RUNS_CLEAN = {
    "route": ["fix the stop loss"],
    "where": ["compute_trade_returns"],
    "find": ["entry_signal"],
    "usages": ["position_fraction"],
    "defs": ["src/strategy/engine.py"],
    "tree": ["src"],
    "summary": [],
    "covers": ["compute_trade_returns"],
    "impact": ["config.ACTIVE_MODE"],
    "can_edit": ["tools/ctx.py"],          # the ALLOW branch; DENY is smoked below
    "brief": [],
    "reverts": [],
    "events": ["5"],
    "schema": [],
    "config": ["ACTIVE_MODE"],
    "perf": [],
    "audit": [],
    "status": [],
    "recent": ["5"],
    "map": [],
    "docs": [],
    "tests": ["strategy_engine"],
    "web": ["F19"],
    "neighbors": ["F19"],
    "walk": ["F19"],
    "why": ["F19"],
    "contradicts": ["F19"],
    "frontier": ["exit logic"],
    "graph": [],
    "health": [],
    "claims": [],
    "stale": [],
    "drift": [],
    "uncaptured": [],
    "delta": [],
    "related": ["kelly sizing"],
}

# Exit code carries information, so only "did not crash" is asserted.
EXIT_CODE_IS_MEANINGFUL = {
    "web --lint": ["web", "--lint"],
    # can_edit exits 1 on a DENY. That is the fence working, not a failure — the live
    # path is meant to refuse. Both branches are smoked: ALLOW above, DENY here.
    "can_edit (deny)": ["can_edit", "live/trader.py"],
}

# Deliberately excluded, with the reason. Asserted to be exactly this set below.
NOT_SMOKED = {
    "serve": "starts a long-running HTTP server",
    "init": "writes a manifest with --write; the read-only form is covered by `map`",
}


def run(args, timeout=90):
    return subprocess.run([sys.executable, str(CTX)] + args, cwd=str(ROOT),
                          capture_output=True, text=True, timeout=timeout)


class EveryCommandRunsAsAProcessTests(unittest.TestCase):
    def test_each_subcommand_exits_zero(self):
        for cmd, args in sorted(RUNS_CLEAN.items()):
            with self.subTest(cmd=cmd):
                proc = run([cmd] + args)
                self.assertEqual(
                    proc.returncode, 0,
                    "`ctx {} {}` exited {}\n--- stderr ---\n{}".format(
                        cmd, " ".join(args), proc.returncode, proc.stderr[-1500:]))
                self.assertNotIn("Traceback", proc.stderr,
                                 "`ctx {}` printed a traceback".format(cmd))

    def test_commands_with_meaningful_exit_codes_do_not_crash(self):
        for label, args in sorted(EXIT_CODE_IS_MEANINGFUL.items()):
            with self.subTest(cmd=label):
                proc = run(args)
                self.assertNotIn(
                    "Traceback", proc.stderr,
                    "`ctx {}` crashed:\n{}".format(label, proc.stderr[-1500:]))
                self.assertIn(proc.returncode, (0, 1, 2),
                              "`ctx {}` exited {}".format(label, proc.returncode))


class TheSmokeListMatchesTheRegisteredCommandsTests(unittest.TestCase):
    """The load-bearing test. Without it, a new subcommand is silently unsmoked —
    which is precisely how `ctx stale` shipped broken."""

    def registered(self):
        import re
        source = CTX.read_text(encoding="utf-8")
        return set(re.findall(r'sub\.add_parser\("([a-z_]+)"\)', source))

    def test_every_registered_command_is_smoked_or_deliberately_excluded(self):
        covered = set(RUNS_CLEAN) | {a[0] for a in EXIT_CODE_IS_MEANINGFUL.values()} \
            | set(NOT_SMOKED)
        missing = self.registered() - covered
        self.assertEqual(
            missing, set(),
            "new ctx subcommand(s) {} are not smoke-tested. Add an entry to RUNS_CLEAN "
            "with a safe argument, or to NOT_SMOKED with a reason — do not leave them "
            "uncovered.".format(sorted(missing)))

    def test_the_smoke_list_has_no_stale_entries(self):
        extra = (set(RUNS_CLEAN) | set(NOT_SMOKED)) - self.registered()
        self.assertEqual(
            extra, set(),
            "these are smoked but no longer registered: {} — the command was renamed "
            "or removed".format(sorted(extra)))

    def test_every_exclusion_carries_a_reason(self):
        for cmd, reason in NOT_SMOKED.items():
            self.assertGreater(len(reason), 20,
                               "{} is excluded without an actionable reason".format(cmd))


class NoteCliSmokeTests(unittest.TestCase):
    """note.py writes to RESEARCH_WEB.md, so only its non-writing paths are smoked."""

    def note(self, args):
        return subprocess.run([sys.executable, str(NOTE)] + args, cwd=str(ROOT),
                              capture_output=True, text=True, timeout=60)

    def test_help_runs(self):
        proc = self.note(["--help"])
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        for sub in ("add", "supersede", "draft"):
            self.assertIn(sub, proc.stdout)

    def test_add_without_commit_is_a_dry_run_and_writes_nothing(self):
        web = ROOT / "RESEARCH_WEB.md"
        before = web.read_bytes()
        proc = self.note(["add", "--kind", "F", "--title", "smoke test placeholder",
                          "--body", "dry run only; this must never reach the web."])
        self.assertNotIn("Traceback", proc.stderr, proc.stderr[-1200:])
        self.assertEqual(
            web.read_bytes(), before,
            "note.py add wrote to RESEARCH_WEB.md WITHOUT --commit — the dry-run "
            "default is the only thing standing between a smoke test and a real node")


if __name__ == "__main__":
    unittest.main()
