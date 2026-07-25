"""H18: no tracked doc may state a present-tense deploy claim naming a dead branch.

`pi-ops-automation` was the deploy branch and was folded into `development`. VD-4 swept
most docs; H18 recorded that `live/CONTEXT.md` still said *"The trader **auto-starts from
`pi-ops-automation`**"* — in the file an agent reads immediately before editing the live
path, naming a branch that no longer exists even as a remote.

**That line is now corrected**, under explicit owner approval, since `live/` is fenced and
`ctx can_edit` returns DENY for it. The file now says `development` and points at
`ops/preflight_trader_start.sh`, which enforces it. The exemption list is empty, and a
test asserts it stays empty: a future entry is new debt, not carried-over debt.

**Why the check is narrow.** A naive "does any doc mention the dead branch" scan hits 13
mentions across 9 files, and almost all are *correct history*: `README.md` calls it the
prior deploy branch, `IMPROVEMENT_PLAN.md` records what shipped there, and the
`data/live_runs/` archives are dated records of runs that really did happen on it. A guard
flagging those would demand the repo forget its own past.

So the rule is: a **present-tense deployment verb** (auto-starts / runs from / deployed /
checked out) on the same line as a dead branch name, with no past-tense marker, outside
the archive directories, and outside `RESEARCH_WEB.md` — the finding ledger, which must be
able to describe a defect without committing it. That took 13 mentions to 1, and the 1 is
now 0.

The file remains behind the edit fence, and a test asserts that too: correcting one line
of prose under approval should not quietly make `live/` freely writable.
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

# Empty: the last present-tense dead-branch claim was corrected with owner approval
# (live/CONTEXT.md now says `development`, matching the manifest and the preflight gate).
# Any entry appearing here again is new debt, not a carried-over exemption.
EXEMPT = set()


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

    def test_no_claim_remains_at_all(self):
        """The exemption is gone because the defect is. Stated separately from the
        test above so a regression reads as 'the fix was reverted', not 'a new file
        appeared'."""
        self.assertEqual(
            self.hits, [],
            "a present-tense dead-branch deploy claim is back: {}".format(
                [(f, n, line[:80]) for f, _d, n, line in self.hits]))

    def test_the_exemption_list_is_empty(self):
        self.assertEqual(
            EXEMPT, set(),
            "an exemption was re-added ({}). The last one was cleared by fixing the "
            "prose; fix the new one too rather than exempting it.".format(sorted(EXEMPT)))

    def test_the_previously_fenced_file_now_names_the_real_branch(self):
        """It was corrected under explicit owner approval. The file is still fenced —
        that is asserted too, so a future edit there is still a deliberate act."""
        import json
        deploy = json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["deploy_branch"]
        text = (ROOT / "live" / "CONTEXT.md").read_text(encoding="utf-8")
        self.assertIn("auto-starts from `{}`".format(deploy), text,
                      "live/CONTEXT.md no longer names the real deploy branch")
        self.assertNotIn("pi-ops-automation", text)
        proc = subprocess.run(
            ["python3", "tools/ctx.py", "can_edit", "live/CONTEXT.md"],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertIn("DENY", proc.stdout,
                      "live/CONTEXT.md left the edit fence — edits there should stay "
                      "deliberate even for documentation")


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

    def test_the_ci_workflow_names_it_too(self):
        """The third committed statement of the same fact (F190)."""
        wf = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
        self.assertIn(self.deploy_branch(), wf,
                      "CI no longer names the deploy branch — pushes to it may go "
                      "untested")


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
