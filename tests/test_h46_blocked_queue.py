"""H46 cannot be tested here, and five siblings behind it were about to burn a cycle each.

Study: `docs/research/BACKLOG_blocked_on_data.md`.

The backlog asked to "test H46 or retire it". H46 (RN-01) needs SEC filing text plus
contemporaneous XBRL, and sits downstream of FD-01, which needs the FD-00 corpus
backfill. Probed directly: `https://www.sec.gov/` and `https://data.sec.gov/` both fail
at the proxy CONNECT stage with **403 Forbidden**, as does the market-data provider. No
filing corpus is committed — the only FD-00 artifact is eight hand-authored clock
fixtures. So H46 can be neither tested nor killed here.

It was not alone. The next five items in the queue — H48 (cross-asset price anchors),
H49 (macro vintages, 8-K codes, CFTC, GDELT, FTD), H51 (accession-scoped XBRL), H52
(paired amendments), H53 (a graph over the ledger H51/H52 would build) — are all blocked
on the same unreachable sources. Six consecutive cycles would each have ended in the same
sentence.

**"Blocked" is a different state from "untested", and the queue could not say so.**
`DEFERRED` covers items an owner chose not to do; nothing covered items nobody *can* do
here. `BLOCKED_ON_DATA` now does, with the same visibility discipline the deferral list
uses: excluded from rotation, counted in `next`, listed with reasons under
`list --blocked`, never silently dropped.

**And a block that is never re-tested becomes a permanent excuse.** `list --blocked
--recheck` probes each host — the only place this tool touches the network — and reports
per host whether it is reachable, so un-blocking is a one-line edit rather than an act of
faith. It is not run automatically: a network call inside a backlog listing would be slow
and flaky, and a silently-skipped item is worse than a slow one.

Guards below are bidirectional. They fail if a blocked item is missing its reason or its
probe, if a blocked item leaks back into the live queue, if the exclusion swallows the
queue whole, and if `next` stops reporting the count — the last being the failure mode
this whole mechanism exists to avoid.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import research_backlog as backlog  # noqa: E402

DOC = ROOT / "docs" / "research" / "BACKLOG_blocked_on_data.md"


class TheBlockedRegistryIsWellFormedTests(unittest.TestCase):
    def test_every_entry_carries_a_reason_and_a_probe(self):
        for key, value in backlog.BLOCKED_ON_DATA.items():
            self.assertEqual(len(value), 2, "{} is malformed".format(key))
            reason, probe = value
            self.assertGreater(
                len(reason), 40,
                "{}'s reason is too short to be actionable — an unexplained block is "
                "how a real blocker becomes invisible".format(key))
            self.assertTrue(probe.startswith("https://"),
                            "{}'s probe is not a URL".format(key))

    def test_every_key_matches_a_real_task(self):
        keys = {str(t["key"]) for t in backlog.collect(skip_recent=False)}
        keys |= {str(t["key"]) for t in backlog.blocked_on_data()}
        for key in backlog.BLOCKED_ON_DATA:
            self.assertIn(
                key, keys,
                "{} is blocked but is no longer a task — the node may have been "
                "resolved; drop the entry".format(key))

    def test_the_six_frontier_children_are_covered(self):
        for node in ("H46", "H48", "H49", "H51", "H52", "H53"):
            self.assertIn("unresolved:{}".format(node), backlog.BLOCKED_ON_DATA,
                          "{} left the blocked set — if its data became reachable, "
                          "say so in the study".format(node))

    def test_blocked_and_deferred_do_not_overlap(self):
        """They have different resolution paths: approval versus access."""
        self.assertEqual(
            set(backlog.BLOCKED_ON_DATA) & set(backlog.DEFERRED), set(),
            "an item is both owner-deferred and data-blocked — pick the one that "
            "actually gates it, or the reader cannot tell what would unblock it")


class BlockedItemsLeaveTheQueueButNotTheRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queue = backlog.collect(skip_recent=False)
        cls.blocked = backlog.blocked_on_data()

    def test_no_blocked_item_is_offered_as_next(self):
        live = {str(t["key"]) for t in self.queue}
        leaked = sorted(live & set(backlog.BLOCKED_ON_DATA))
        self.assertEqual(
            leaked, [],
            "blocked items are back in the live queue ({}) — the exclusion broke and "
            "the loop will spend a cycle per item confirming they are blocked".format(
                leaked))

    def test_they_are_still_listed_with_their_reasons(self):
        self.assertEqual(len(self.blocked), len(backlog.BLOCKED_ON_DATA))
        for task in self.blocked:
            self.assertTrue(task["blocked_reason"])
            self.assertTrue(task["probe"])

    def test_the_queue_is_not_emptied_by_the_exclusion(self):
        """Non-vacuity: an exclusion that swallows the backlog is not an improvement."""
        self.assertGreater(
            len(self.queue), 0,
            "the live queue is empty after excluding blocked items — the exclusion is "
            "too broad, or the backlog genuinely ran dry (see `next` for what then)")

    def test_next_reports_the_blocked_count(self):
        import io
        import types
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            backlog.command_next(types.SimpleNamespace(no_skip=True))
        out = buf.getvalue()
        self.assertIn(
            "blocked on unreachable data", out,
            "`next` no longer reports how many items are blocked — a silent exclusion "
            "is exactly what this mechanism exists to prevent")
        self.assertIn(str(len(backlog.BLOCKED_ON_DATA)), out)


class TheBlockIsRetestableTests(unittest.TestCase):
    def test_a_recheck_helper_exists_and_covers_every_distinct_host(self):
        hosts = {probe for _, probe in backlog.BLOCKED_ON_DATA.values()}
        self.assertGreaterEqual(len(hosts), 2,
                                "all blocked items now wait on one host — simplify")
        import inspect
        source = inspect.getsource(backlog.recheck_blocks)
        self.assertIn("BLOCKED_ON_DATA", source)
        self.assertIn("timeout", source,
                      "the re-check has no timeout — it could hang a loop")

    def test_the_recheck_is_not_run_automatically(self):
        """A network call inside a plain listing would be slow and flaky."""
        import inspect
        for fn in (backlog.collect, backlog.blocked_on_data, backlog.command_next):
            self.assertNotIn(
                "recheck_blocks", inspect.getsource(fn),
                "{} now probes the network on every run".format(fn.__name__))

    def test_the_only_network_call_is_in_the_recheck(self):
        source = (ROOT / "tools" / "research_backlog.py").read_text(encoding="utf-8")
        self.assertEqual(
            source.count("urllib.request.urlopen"), 1,
            "research_backlog.py makes network calls outside recheck_blocks — it is "
            "documented as read-only and offline")


class OnlyAnsweringEdgesCloseAHypothesisTests(unittest.TestCase):
    """Found by breaking it: capturing this very finding hid the node it is about.

    `source_unresolved` counted ANY Finding->Hypothesis edge as "answered". Linking
    `H46:relates` from a finding that says H46 is BLOCKED therefore marked H46 answered
    and dropped it from the queue — and from the blocked list, which was built from the
    ranked task set.
    """

    @classmethod
    def setUpClass(cls):
        cls.nodes = backlog.load_nodes()

    def test_relates_and_refines_do_not_count_as_answers(self):
        for weak in ("relates", "refines", "builds_on", "drives"):
            self.assertNotIn(
                weak, backlog.ANSWERING_EDGES,
                "{!r} now closes a hypothesis — a finding that merely mentions an "
                "open question would mark it answered".format(weak))

    def test_evidence_edges_do_count(self):
        for strong in ("resolves", "supports", "contradicts"):
            self.assertIn(strong, backlog.ANSWERING_EDGES)

    def test_the_narrower_rule_surfaces_substantially_more_work(self):
        import re as _re
        resolved, by_type = set(), {}
        for nid, node in self.nodes.items():
            for target, etype in node.get("edges", []):
                if etype == "resolves":
                    resolved.add(target)
                if nid.startswith("F") and target.startswith("H"):
                    by_type.setdefault(etype, set()).add(target)
        open_h = {n for n, d in self.nodes.items()
                  if n.startswith("H") and not d.get("superseded")
                  and not _re.search(r"\b(RESOLVED|DEAD|DONE|CLOSED)\b",
                                     str(d.get("title", "")), _re.I)}
        any_edge = set().union(*by_type.values()) if by_type else set()
        answered = set(resolved)
        for etype in backlog.ANSWERING_EDGES:
            answered |= by_type.get(etype, set())
        hidden = len(open_h - answered) - len(open_h - resolved - any_edge)
        self.assertGreater(
            hidden, 15,
            "the narrower rule now surfaces only {} more open hypotheses — either the "
            "web's edges were re-typed (good) or the rule drifted back".format(hidden))

    def test_it_does_not_surface_everything(self):
        """Non-vacuity: if nothing counted as an answer, every hypothesis would queue."""
        answered = set()
        for nid, node in self.nodes.items():
            for target, etype in node.get("edges", []):
                if (nid.startswith("F") and target.startswith("H")
                        and etype in backlog.ANSWERING_EDGES):
                    answered.add(target)
        self.assertGreater(
            len(answered), 15,
            "almost no hypothesis is answered by an evidence edge — the rule has "
            "become too narrow to distinguish anything")

    def test_the_blocked_list_is_built_from_unlimited_sources(self):
        """The bug that hid all six: filtering the ranked top-N."""
        import inspect
        source = inspect.getsource(backlog.blocked_on_data)
        self.assertIn("big", source)
        self.assertNotIn(
            "source_unresolved(nodes)", source,
            "blocked_on_data is back on the default-limited sources — a blocked item "
            "disappears as soon as something older outranks it")


class TheStudyRecordsWhatWouldUnblockThemTests(unittest.TestCase):
    def test_it_names_the_probe_result(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("403", text,
                      "the study no longer records the observed failure mode — "
                      "'blocked' without evidence is an assertion")

    def test_it_names_every_blocked_node(self):
        text = DOC.read_text(encoding="utf-8")
        for node in ("H46", "H48", "H49", "H51", "H52", "H53"):
            self.assertIn(node, text)

    def test_it_says_how_to_un_block(self):
        text = DOC.read_text(encoding="utf-8").lower()
        self.assertIn("--recheck", text)
        self.assertIn("blocked_on_data", text)


if __name__ == "__main__":
    unittest.main()
