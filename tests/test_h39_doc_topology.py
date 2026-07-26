"""H39: the doc-ownership tables barely drifted — the registry pointed at a finished plan.

Study: `docs/research/CTX_doc_topology.md`. View: `ctx docs`.

H39 (DP-15) says the "why vs how" topology is hand-restated in four prose docs plus
machine-readably in `context_docs`, that only the manifest is CI-bound, and that the prose
therefore drifts. Checking each prose table against the manifest, the ownership statements
were **almost entirely consistent**: `CLAUDE.md`/`AGENTS.md` = why, `OPERATIONS.md`/
`ops/README.md` = how, everywhere it is stated.

The drift was somewhere else, and worse:

**`AGENT_CONTEXT_PLAN.md` was registered as one of three `navigation` docs, and it is a
finished plan.** It is explicitly marked "This is a **plan**", with `[BUILD]` markers on
proposed artifacts — and every one of those artifacts now exists. Of the 23 `ctx`
subcommands it proposed, **21 are implemented** (the two "missing" are `ctx note`, shipped
as `tools/note.py`, and `ctx experiments`); the CLI now has 37. The manifest it specifies
is named `context_map.yaml` in **7 places**, and the repo's manifest is `context_map.json`
— a file by that name has never existed. An agent routed to "navigation" got a completed
design document pointing at a nonexistent file.

**And `CONTEXT_KIT.md` — also registered under `navigation` — was named by none of the
five prose docs**, including `AGENT_INDEX.md`, the one-screen router.

Fixed here: `ctx docs` generates the ownership table from `context_docs` (H39's first
option) and reports three separate classes of broken reference, because conflating them
makes the report noise:

* **DANGLING** — a navigation/ops doc names a path that does not exist. A real hazard.
* **STALE NAME** — the artifact exists under a different extension (`context_map.yaml` ->
  `context_map.json`). Not pending work; a rename nobody propagated.
* **named-but-unbuilt in a planning/ledger doc** — expected. `IMPROVEMENT_PLAN.md`
  proposes `src/analysis/performance.py` and `RESEARCH_WEB.md`'s F208 describes its
  absence. This is the third place in this repo needing that exclusion: a ledger must be
  able to *describe* an absence without the detector reading it as a broken link.

`AGENT_CONTEXT_PLAN.md` moved from `navigation` to a new `executed_plan` group, and the
prose in `AGENT_INDEX.md` and `AGENTS.md` was updated to match — which is the drift H39
asks to prevent, in the one place it had actually happened.
"""
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ctx  # noqa: E402

MAP = json.loads((ROOT / "context_map.json").read_text(encoding="utf-8"))
DOCS = MAP["context_docs"]
PROSE = ["AGENT_INDEX.md", "AGENTS.md", "OPERATIONS.md", "CONTEXT_KIT.md"]


class TheTopologyIsGeneratedNotRestatedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topo = ctx.doc_topology()

    def test_every_registered_doc_exists(self):
        for row in self.topo["rows"]:
            self.assertTrue(row["exists"],
                            "context_docs registers {} and it is not on disk".format(
                                row["doc"]))

    def test_every_group_has_at_least_one_doc(self):
        for group, docs in DOCS.items():
            self.assertTrue(docs, "context_docs group {!r} is empty".format(group))

    def test_the_view_covers_every_registered_doc(self):
        listed = {row["doc"] for row in self.topo["rows"]}
        registered = {d for docs in DOCS.values() for d in docs}
        self.assertEqual(
            listed, registered,
            "`ctx docs` no longer enumerates exactly the registered docs — the "
            "generated table has stopped being the manifest")

    def test_the_router_names_every_current_navigation_doc(self):
        """The one-screen router must name what it routes to. CONTEXT_KIT.md was
        registered as navigation and named by nothing, including this file."""
        index = (ROOT / "AGENT_INDEX.md").read_text(encoding="utf-8")
        for doc in DOCS["navigation"]:
            if doc == "AGENT_INDEX.md":
                continue
            self.assertIn(
                doc, index,
                "AGENT_INDEX.md does not name {}, which context_docs registers as "
                "navigation — that is exactly the restatement drift H39 names".format(
                    doc))


class TheExecutedPlanIsNoLongerRoutedToAsNavigationTests(unittest.TestCase):
    def test_the_plan_is_registered_as_an_executed_plan(self):
        self.assertIn("AGENT_CONTEXT_PLAN.md", DOCS.get("executed_plan", []))
        self.assertNotIn(
            "AGENT_CONTEXT_PLAN.md", DOCS["navigation"],
            "the executed design plan is registered as navigation again — an agent "
            "routed there gets [BUILD] markers for artifacts that already exist")

    def test_the_prose_agrees_with_the_manifest(self):
        for name in ("AGENT_INDEX.md", "AGENTS.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            nav_line = [l for l in text.splitlines()
                        if "navigation" in l.lower() or "Navigation" in l]
            self.assertTrue(nav_line, "{} no longer states the navigation set".format(name))
            joined = " ".join(nav_line)
            self.assertIn("CONTEXT_KIT.md", joined,
                          "{}'s navigation line dropped CONTEXT_KIT.md, which the "
                          "manifest registers".format(name))
            self.assertNotIn(
                "AGENT_CONTEXT_PLAN.md", joined,
                "{}'s navigation line lists the executed plan again".format(name))

    def test_the_plan_still_declares_itself_a_plan(self):
        text = (ROOT / "AGENT_CONTEXT_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("This is a **plan**", text,
                      "AGENT_CONTEXT_PLAN.md no longer says it is a plan — if it was "
                      "rewritten as current documentation, re-register it")

    def test_the_plan_was_in_fact_executed(self):
        """The claim that justifies the move, measured rather than asserted."""
        source = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        implemented = set(re.findall(r'sub\.add_parser\("([a-z_\-]+)"', source))
        proposed = set(re.findall(
            r"`ctx ([a-z_]+)", (ROOT / "AGENT_CONTEXT_PLAN.md").read_text("utf-8")))
        done = proposed & implemented
        self.assertGreaterEqual(
            len(done), 20,
            "only {} of {} proposed ctx subcommands are implemented — the plan is no "
            "longer 'executed' and belongs back in an open category".format(
                len(done), len(proposed)))
        self.assertGreater(
            len(implemented), len(proposed),
            "the CLI no longer exceeds what the plan proposed — check whether "
            "subcommands were removed")


class BrokenReferencesAreClassifiedNotConflatedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topo = ctx.doc_topology()

    def test_no_navigation_or_ops_doc_has_a_dangling_reference(self):
        self.assertEqual(
            self.topo["dangling"], {},
            "a navigation/ops doc names a path that does not exist: {} — an agent sent "
            "there hunts a missing file".format(self.topo["dangling"]))

    def test_the_stale_manifest_name_is_still_detected(self):
        renamed = self.topo["renamed"]
        self.assertIn(
            "AGENT_CONTEXT_PLAN.md", renamed,
            "the context_map.yaml -> context_map.json stale name is gone. If the plan "
            "was corrected, good — drop this assertion and the note in AGENT_INDEX.md")
        self.assertEqual(renamed["AGENT_CONTEXT_PLAN.md"].get("context_map.yaml"),
                         "context_map.json")

    def test_planning_docs_may_name_unbuilt_artifacts(self):
        """Non-vacuity for the exclusion: it must actually be excluding something."""
        proposed = self.topo["proposed"]
        self.assertTrue(
            proposed,
            "no planning doc names an unbuilt artifact any more — the exclusion is "
            "inert, so check it is not hiding a real dangling reference")
        flat = {ref for refs in proposed.values() for ref in refs}
        self.assertIn(
            "src/analysis/performance.py", flat,
            "F208's unbuilt module is no longer reported as a proposal — if it was "
            "built, supersede F208")

    def test_runtime_paths_are_not_reported_as_broken(self):
        """OPERATIONS.md names files a running bot produces; a clone has none."""
        ops = (ROOT / "OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn("local_logs/healthcheck.json", ops,
                      "the runtime-path example this exclusion exists for is gone")
        self.assertNotIn("OPERATIONS.md", self.topo["dangling"])


class TheViewIsWiredAndDiscoverableTests(unittest.TestCase):
    def test_ctx_docs_runs_and_prints_every_group(self):
        out = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ctx.py"), "docs"],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        for group in DOCS:
            self.assertIn(group, out.stdout,
                          "`ctx docs` output omits the {} group".format(group))

    def test_it_is_listed_in_the_router_and_the_manifest(self):
        self.assertIn("ctx.py docs",
                      (ROOT / "AGENT_INDEX.md").read_text(encoding="utf-8"))
        self.assertTrue(
            any(t["cmd"] == "ctx docs" for t in MAP["tools_readonly"]),
            "ctx docs is not registered in tools_readonly")


if __name__ == "__main__":
    unittest.main()
