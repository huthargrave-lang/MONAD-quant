"""H18: no tracked doc may state a present-tense deploy claim naming a dead branch.

`pi-ops-automation` was the deploy branch and was folded into `development`. VD-4 swept
most docs; H18 records that `live/CONTEXT.md` still says *"The trader **auto-starts from
`pi-ops-automation`**"* — in the file an agent reads immediately before editing the live
path, naming a branch that no longer exists even as a remote.

It fails safe (the preflight enforces `EXPECT_BRANCH="development"`, so acting on the
prose would be refused at the gate) but it is wrong at the highest-stakes moment, and it
is the only such claim left.

**Why the check is narrow.** A naive "does any doc mention the dead branch" scan hits 13
mentions across 9 files, and almost all of them are *correct history*: `README.md` says
"prior deploy branch, now folded into `development`", `IMPROVEMENT_PLAN.md` records what
shipped on it, and the `data/live_runs/` archives are dated records of runs that really
did happen there. A guard that flagged those would demand the repo forget its own past.

So the rule is: a **present-tense deployment verb** (auto-starts / runs from / deployed /
checked out) in the same line as a dead branch name, with no past-tense marker, outside
the archive directories, and outside `RESEARCH_WEB.md` — which is the finding ledger and
must be able to describe a defect without committing it. That takes 13 mentions to 1.

**The one hit is not fixed here.** `live/CONTEXT.md` sits behind the `live/` edit fence
(`ctx can_edit` returns DENY), and the standing instruction is that the live path needs
explicit approval. So it is recorded as a ratcheted exemption: this test fails if a
*second* such claim appears, and it fails when the exemption is cleared, so the debt
stays visible and cannot grow while the approval is pending.
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEAD_BRANCHES = {"pi-ops-automation"}

# Dated records and finding ledgers legitimately name a dead branch.
SKIP_PREFIXES = ("data/live_runs/", "docs/history/", "docs/research/")
SKIP_FILES = {"RESEARCH_WEB.md"}

PAST = re.compile(
    r"\b(prior|previous|former|was|were|old|folded into|never merged|already shipped"
    r"|historical|Appendix|sit\b|toward|in this stretch|Session \d)", re.I)
DEPLOY = re.compile(
    r"(auto-?starts?|runs? from|deploys?|deployment|deployed|checked out|the Pi runs"
    r"|is what the Pi)", re.I)

# Known, approval-blocked. Fails if it grows OR if it is cleared.
EXEMPT = {("live/CONTEXT.md", "pi-ops-automation")}


def tracked_markdown():
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=str(ROOT),
                         capture_output=True, text=True)
    return [f for f in out.stdout.split()
            if not f.startswith(SKIP_PREFIXES) and f not in SKIP_FILES]


def present_tense_deploy_claims():
    hits = []
    for rel in tracked_markdown():
        path = ROOT / rel
        if not path.exists():
            continue
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for dead in DEAD_BRANCHES:
                if dead in line and DEPLOY.search(line) and not PAST.search(line):
                    hits.append((rel, dead, lineno, line.strip()))
    return hits


class NoDocClaimsADeadDeployBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hits = present_tense_deploy_claims()

    def test_only_the_known_fenced_file_still_does(self):
        found = {(rel, dead) for rel, dead, _n, _l in self.hits}
        new = found - EXEMPT
        self.assertEqual(
            new, set(),
            "new present-tense deploy claim(s) naming a dead branch: {}. Fix the prose "
            "— do not add to EXEMPT.".format(sorted(new)))

    def test_the_exemption_is_still_needed(self):
        """Fails when someone fixes it, so the exemption cannot outlive the defect."""
        found = {(rel, dead) for rel, dead, _n, _l in self.hits}
        cleared = EXEMPT - found
        self.assertEqual(
            cleared, set(),
            "{} no longer claims a dead deploy branch — the approved edit landed. "
            "Remove it from EXEMPT.".format(sorted(cleared)))

    def test_the_exempt_file_is_actually_fenced(self):
        """The reason it is exempt rather than fixed. If the fence moves, fix it."""
        proc = subprocess.run(
            ["python3", "tools/ctx.py", "can_edit", "live/CONTEXT.md"],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertIn(
            "DENY", proc.stdout,
            "live/CONTEXT.md is no longer behind the edit fence — the one-line branch "
            "correction can now be made directly; make it and drop the exemption")


class TheLiveDeployBranchIsConsistentTests(unittest.TestCase):
    """What the docs SHOULD say, asserted at the three committed sources of truth."""

    def deploy_branch(self):
        import json
        return json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["deploy_branch"]

    def test_the_manifest_and_the_preflight_gate_agree(self):
        pf = (ROOT / "ops" / "preflight_trader_start.sh").read_text(encoding="utf-8")
        expect = re.search(r'^EXPECT_BRANCH="([^"]+)"', pf, re.M).group(1)
        self.assertEqual(expect, self.deploy_branch())

    def test_the_dead_branch_is_not_the_deploy_branch(self):
        self.assertNotIn(self.deploy_branch(), DEAD_BRANCHES,
                         "the deploy branch is now one this guard treats as dead")

    def test_the_fenced_file_disagrees_with_all_of_them(self):
        """States the defect as a fact, so it reads as a finding rather than a TODO."""
        text = (ROOT / "live" / "CONTEXT.md").read_text(encoding="utf-8")
        self.assertIn("pi-ops-automation", text)
        self.assertNotIn(
            "auto-starts from `{}`".format(self.deploy_branch()), text,
            "live/CONTEXT.md now names the real deploy branch — clear the exemption")


class TheGuardIsNotVacuousTests(unittest.TestCase):
    def test_it_scans_a_meaningful_number_of_docs(self):
        self.assertGreater(len(tracked_markdown()), 20,
                           "almost no tracked markdown is being scanned")

    def test_a_synthetic_claim_would_be_flagged(self):
        line = "The trader auto-starts from `pi-ops-automation` today."
        self.assertTrue(DEPLOY.search(line))
        self.assertFalse(PAST.search(line))

    def test_a_historical_mention_would_NOT_be_flagged(self):
        """The filter that makes the guard usable rather than noisy."""
        for line in ("- `pi-ops-automation` — prior deploy branch, now folded into "
                     "`development`.",
                     "## Appendix — already shipped (2026-06-17/18, on "
                     "`pi-ops-automation`)"):
            self.assertTrue(PAST.search(line),
                            "a historical mention would now be flagged: {!r}".format(line))


if __name__ == "__main__":
    unittest.main()
