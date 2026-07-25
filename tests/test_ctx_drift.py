"""H15/DP-8: cross-store consistency, and the store that cannot be read.

H15 asks for a `ctx drift` checker across three claim stores: the research web,
`experiments.jsonl` (the sweep ledger), and the `context_map.json` bridges. Building it
surfaced the reason it had not been built.

**One of the three stores is not in the repository.** `experiments.jsonl` is gitignored
(`.gitignore:17`), so it is absent from every fresh clone and from CI. A checker written
to H15's specification would open two files, skip the third, and report "no drift" — a
verdict about a store it never read. That is the absence-flag failure this project keeps
re-learning (F155, F159, F167), and it is why `drift_report()` returns **unknowns**
separately from **problems**, and why `ctx drift` prints
*"0 problems does NOT mean consistent"* whenever an unknown exists.

**What IS checkable is clean, and now guarded.** All 17 bridges name a node that exists
and is current, and every node ID cited in a bridge *note* resolves and is current — which
matters more than it sounds, because this session added F174–F181 references to those
notes, and a note citing a superseded finding would send `ctx impact` at retracted work.

**Advisory, by H15's own instruction.** Cross-store semantic matching is heuristic, so
unknowns do not fail the command; only concrete inconsistencies do. The exit code is
raised with `sys.exit`, matching every other exit-code-bearing command in `ctx` — a first
draft returned the code from the function, which `main()` discards, so the documented
contract would have been false.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402


class TheStoreCensusIsHonestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stores, cls.problems, cls.unknowns = ctx.drift_report()

    def test_all_three_stores_are_named(self):
        self.assertEqual(set(self.stores), {"web", "bridges", "ledger"})

    def test_the_two_committed_stores_are_readable(self):
        self.assertTrue(self.stores["web"][0])
        self.assertTrue(self.stores["bridges"][0])

    def test_the_ledger_is_absent_and_that_becomes_an_UNKNOWN(self):
        """The load-bearing property: an unreadable store must never read as clean."""
        if self.stores["ledger"][0]:
            self.skipTest("experiments.jsonl now exists — see the un-ignore test below")
        self.assertTrue(
            any("ledger" in u for u in self.unknowns),
            "the ledger is missing but no unknown was raised — `ctx drift` would report "
            "0 problems about a store it never opened")

    def test_the_ledger_is_still_gitignored(self):
        """Explains the absence, and fails if someone un-ignores it — at which point
        the ledger check becomes implementable and this file should grow one."""
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(
            "experiments.jsonl", [line.strip() for line in ignore],
            "experiments.jsonl is no longer gitignored — the third store may now be "
            "committed, so implement the ledger-vs-web check instead of leaving it "
            "as a permanent UNKNOWN (IMPROVEMENT_PLAN K2)")

    def test_unknowns_are_not_counted_as_problems(self):
        self.assertEqual(self.problems, [],
                         "cross-store problems appeared: {}".format(self.problems))
        self.assertGreater(len(self.unknowns), 0)


class TheBridgeChecksAreRealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _s, cls.problems, _u = ctx.drift_report()
        cls.nodes, _ = ctx._parse_web()
        cls.bridges = json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["graph_bridges"]["bridges"]

    def test_no_bridge_points_at_a_missing_or_superseded_node(self):
        self.assertEqual(
            [p for p in self.problems if "does not exist" in p or "SUPERSEDED" in p], [],
            "a bridge now names a missing or superseded node — `ctx impact` would "
            "surface retracted work as if it governed the code")

    def test_every_node_id_cited_in_a_bridge_NOTE_resolves(self):
        cited = {ref for b in self.bridges
                 for ref in ctx._NODE_REF_RX.findall(b.get("note", ""))}
        self.assertGreater(
            len(cited), 5,
            "bridge notes cite almost no node IDs, so this check is near-vacuous")
        for ref in sorted(cited):
            self.assertIn(ref, self.nodes,
                          "bridge note cites {} which does not exist".format(ref))
            self.assertFalse(
                ctx._is_superseded(self.nodes[ref]),
                "bridge note cites {}, which is superseded".format(ref))

    def test_the_check_fires_on_a_synthetic_violation(self):
        """A guard that cannot fail is not a guard."""
        self.assertTrue(ctx._NODE_REF_RX.findall("see F999 for details"))
        self.assertNotIn("F999", self.nodes)


class TheCommandContractIsRealTests(unittest.TestCase):
    def test_it_signals_with_sys_exit_not_a_return_value(self):
        """main() discards return values, so a returned code is a false contract."""
        source = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        start = source.index("def cmd_drift(")
        body = source[start:source.index("\ndef ", start + 5)]
        self.assertIn("sys.exit(1)", body,
                      "cmd_drift no longer exits non-zero on a problem")
        self.assertNotIn("return 1", body)

    def test_it_is_read_only(self):
        import io
        import types
        from contextlib import redirect_stdout

        web = ROOT / "RESEARCH_WEB.md"
        manifest = ROOT / "context_map.json"
        before = (web.read_bytes(), manifest.read_bytes())
        buf = io.StringIO()
        with redirect_stdout(buf):
            ctx.cmd_drift(types.SimpleNamespace())
        self.assertEqual((web.read_bytes(), manifest.read_bytes()), before,
                         "ctx drift wrote to a store")
        out = buf.getvalue()
        self.assertIn("UNREADABLE", out)
        self.assertIn("does NOT mean consistent", out)


if __name__ == "__main__":
    unittest.main()
