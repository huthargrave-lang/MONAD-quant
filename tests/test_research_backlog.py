"""Tests for the autonomous loop's work-selection engine.

The engine's job is to keep a continuous agent from two failure modes:

* **Stuttering** — redoing what it just finished. Guarded by the anti-repetition
  filter, which keys off recent commits.
* **Starving** — suppressing so much that nothing is left. This is the subtler
  failure, and it is a real one: a first version matched on title tokens like
  `strategy` and `engine`, which appear in most commit bodies, and suppressed 23 of
  30 items. A loop fed by that returns "backlog empty" while real work sits there.

So the tests below assert BOTH directions, and the starvation test is the load-bearing
one, because over-suppression fails silently while under-suppression is merely noisy.
"""
import importlib.util
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "research_backlog", ROOT / "tools" / "research_backlog.py")
BL = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = BL
_SPEC.loader.exec_module(BL)


class AntiRepetitionTests(unittest.TestCase):
    def test_a_node_named_in_a_recent_commit_is_suppressed(self):
        task = {"node": "F142", "title": "some finding"}
        self.assertTrue(BL._recently_touched(task, ["capture f142: the go/no-go cites nothing"]))

    def test_a_node_NOT_named_is_kept(self):
        task = {"node": "F999", "title": "some finding"}
        self.assertFalse(BL._recently_touched(task, ["capture f142: something else"]))

    def test_node_matching_is_whole_word_not_substring(self):
        """F14 must not be suppressed by a commit about F142."""
        self.assertFalse(
            BL._recently_touched({"node": "F14", "title": "x"}, ["about f142 here"]))

    def test_generic_engineering_words_do_NOT_suppress(self):
        """The starvation bug. `strategy`/`engine` appear in most commit bodies; if
        they suppress, the queue empties while real work remains."""
        task = {"node": None, "title": "code-claim about src/strategy/engine.py::generate_trades"}
        subjects = ["refactor the strategy engine and its config signals"]
        self.assertFalse(
            BL._recently_touched(task, subjects),
            "generic vocabulary is suppressing items — the loop will starve")

    def test_a_distinctive_filename_DOES_suppress(self):
        task = {"node": None, "title": "bond_ladder_study.py"}
        self.assertTrue(
            BL._recently_touched(task, ["route bond_ladder_study.py through data_cache"]))

    def test_a_task_with_a_node_ignores_its_title_entirely(self):
        """Precise key wins: falling through to title tokens is what caused the
        over-suppression, so a node-keyed task must not consult its title."""
        task = {"node": "F999", "title": "bond_ladder_study.py"}
        self.assertFalse(
            BL._recently_touched(task, ["route bond_ladder_study.py through data_cache"]))


class CollectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unfiltered = BL.collect(skip_recent=False)
        cls.filtered = BL.collect(skip_recent=True)

    def test_the_engine_finds_real_work(self):
        self.assertGreater(len(self.unfiltered), 5)

    def test_the_filter_suppresses_something_but_not_everything(self):
        """Both directions at once. If suppression hits 100% the loop starves; if it
        hits 0% the filter is inert and the loop stutters."""
        n_all, n_fresh = len(self.unfiltered), len(self.filtered)
        self.assertLess(n_fresh, n_all, "filter is inert — the loop will repeat itself")
        self.assertGreater(
            n_fresh, 0,
            "filter suppressed EVERYTHING — the loop will report an empty backlog "
            "while real work remains. This is the starvation failure.")
        self.assertLess(
            (n_all - n_fresh) / n_all, 0.9,
            "filter is suppressing >90% of the queue; check for generic-token matching")

    def test_every_task_carries_an_actionable_instruction(self):
        for t in self.unfiltered:
            self.assertTrue(str(t["action"]).strip(), "task {} has no action".format(t["key"]))
            self.assertIn(t["kind"],
                          {"uncited", "unresolved", "unguarded", "blocked", "open_item"})
            self.assertGreater(t["score"], 0.0)

    def test_tasks_are_ranked_by_score_descending(self):
        scores = [t["score"] for t in self.filtered]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_keys_are_unique_so_the_loop_can_deduplicate(self):
        keys = [t["key"] for t in self.unfiltered]
        self.assertEqual(len(keys), len(set(keys)))

    def test_human_stated_open_items_outrank_inferred_ones(self):
        """A handoff item is a deliberate human priority; inference should not
        outrank it at equal tractability."""
        opens = [t for t in self.unfiltered if t["kind"] == "open_item"]
        if not opens:
            self.skipTest("no handoff open items parsed")
        self.assertTrue(all(t["leverage"] >= 0.8 for t in opens))


class NeverStopsTests(unittest.TestCase):
    """The loop must not treat an empty queue as a reason to stop."""

    def test_empty_backlog_still_instructs_the_agent_to_continue(self):
        import io
        from contextlib import redirect_stdout
        import types

        original = BL.collect
        try:
            BL.collect = lambda **kw: []
            buf = io.StringIO()
            with redirect_stdout(buf):
                BL.command_next(types.SimpleNamespace(no_skip=False))
            out = buf.getvalue()
        finally:
            BL.collect = original
        self.assertIn("Do NOT stop", out)
        self.assertIn("new direction", out)


if __name__ == "__main__":
    unittest.main()


class ResolvedHypothesesAreNotFlaggedUncitedTests(unittest.TestCase):
    """Evidence flows in DIFFERENT directions for findings and hypotheses.

    A Finding reaches its evidence downstream: F -> evidenced_by -> E -> doc. A
    HYPOTHESIS reaches its evidence upstream: the Finding that resolved it holds the
    citation. An engine that follows only outgoing edges is direction-blind, and will
    keep proposing work on a hypothesis that was just closed — which is exactly what
    happened to H50 the moment a resolving Finding was attached to it.
    """

    def test_a_hypothesis_resolved_by_a_CITING_finding_is_not_uncited(self):
        """Note the precise property. Being resolved is NOT enough — if the resolver
        itself cites no document, the resolved node genuinely has no evidence path
        and belongs in the queue. A first version of this test asserted the broader
        "resolved => not uncited" and correctly failed on D4, F7 and H3, whose
        resolvers (H8/F41, H2, E5) cite nothing. The code was right; the assertion
        was too strong.
        """
        nodes = BL.load_nodes()
        resolved_by_citing = set()
        for node in nodes.values():
            cites_doc = bool(BL.DOC_REF.findall(str(node.get("body", ""))))
            if not cites_doc:
                continue
            for target, etype in node.get("edges", []):
                if etype == "resolves":
                    resolved_by_citing.add(target)
        if not resolved_by_citing:
            self.skipTest("no hypothesis is yet resolved by a doc-citing node")
        flagged = {t["node"] for t in BL.source_uncited(nodes, limit=50)}
        overlap = resolved_by_citing & flagged
        self.assertEqual(
            overlap, set(),
            "these nodes are resolved by a Finding that DOES cite a document, yet "
            "are still flagged uncited: {}. source_uncited is following only "
            "outgoing edges again, so it cannot see that a hypothesis's evidence "
            "lives upstream in the Finding that closed it.".format(sorted(overlap)))

    def test_the_web_actually_contains_a_resolves_edge_to_test_against(self):
        """Otherwise the test above passes vacuously."""
        nodes = BL.load_nodes()
        n_resolves = sum(
            1 for node in nodes.values()
            for _t, etype in node.get("edges", []) if etype == "resolves")
        self.assertGreater(
            n_resolves, 0,
            "no resolves edges exist, so the direction-blindness guard above is "
            "vacuous — re-check when the first hypothesis is closed")


class OwnerDeferralTests(unittest.TestCase):
    """A deferral must be a PAUSE, not a disappearance.

    The whole point of this engine is that nothing worth doing goes unseen. An
    exemption list is the obvious way to stop an item topping the queue forever, and
    also the obvious way to lose it — so every deferral carries a written reason, the
    count is surfaced by `next`, and `list --deferred` prints them in full.
    """

    def test_every_deferral_carries_a_reason(self):
        for key, reason in BL.DEFERRED.items():
            self.assertTrue(
                str(reason).strip(),
                "{} is deferred with no reason — an unexplained entry is how a real "
                "blocker becomes invisible".format(key))
            self.assertGreater(
                len(str(reason)), 40,
                "{}'s reason is too terse to be actionable later".format(key))

    def test_deferred_keys_correspond_to_real_backlog_items(self):
        """A stale key silently defers nothing and hides a typo."""
        live = {str(t["key"]) for t in BL.collect(skip_recent=False)}
        held = {str(t["key"]) for t in BL.deferred()}
        for key in BL.DEFERRED:
            self.assertIn(
                key, live | held,
                "{} is in DEFERRED but matches no backlog item — the item was "
                "renamed or resolved; drop the stale entry".format(key))

    def test_deferred_items_are_excluded_from_the_queue(self):
        keys = {str(t["key"]) for t in BL.collect(skip_recent=False)}
        for key in BL.DEFERRED:
            self.assertNotIn(key, keys, "{} is deferred but still queued".format(key))

    def test_deferred_items_remain_RETRIEVABLE(self):
        """The property that makes this a pause rather than a deletion."""
        if not BL.DEFERRED:
            self.skipTest("nothing deferred")
        held = BL.deferred()
        self.assertEqual(
            {str(t["key"]) for t in held}, set(BL.DEFERRED),
            "deferred() does not return every deferred item — some are unreachable")
        for t in held:
            self.assertTrue(t["deferred_reason"], "a deferred item lost its reason")

    def test_next_surfaces_that_something_is_deferred(self):
        import io
        import types
        from contextlib import redirect_stdout

        if not BL.DEFERRED:
            self.skipTest("nothing deferred")
        buf = io.StringIO()
        with redirect_stdout(buf):
            BL.command_next(types.SimpleNamespace(no_skip=False))
        self.assertIn(
            "owner-deferred", buf.getvalue(),
            "`next` no longer mentions deferred items — they have become invisible")



class ToolCitationIsSecondClassEvidenceTests(unittest.TestCase):
    """A node naming a reproducing TOOL is not as uncited as one naming nothing.

    Measured across the web: 11 nodes cite a doc only, 74 cite both, 39 (10.3%) cite
    a TOOL only, and 253 cite neither. A doc-only metric treats that middle group as
    fully uncited, which overstates the gap — naming `tools/bond_ladder_study.py`
    gives a reader a way to regenerate the result, even though the tool does not hold
    the numbers the way a study document does.

    So tool-cited nodes are DISCOUNTED rather than excluded: still queued, ranked
    below genuinely uncited ones. Excluding them would hide a real (if weaker) gap;
    ranking them equal would waste cycles on the more recoverable case first.
    """

    def test_a_tool_reference_lowers_leverage_but_does_not_remove_the_item(self):
        nodes = BL.load_nodes()
        rows = BL.source_uncited(nodes, limit=50)
        tooled = [r for r in rows if "names tool" in r["evidence"]]
        plain = [r for r in rows if "names tool" not in r["evidence"]]
        if not tooled:
            self.skipTest("no tool-cited node currently in the uncited queue")
        self.assertTrue(plain, "every uncited node names a tool — discount is vacuous")
        # same dependent count should rank the tool-cited node lower
        for t in tooled:
            self.assertLess(
                t["leverage"], 1.0,
                "{} names a tool yet carries undiscounted leverage".format(t["node"]))

    def test_the_discount_is_visible_in_the_evidence_string(self):
        """A silent discount is unauditable — the reason must be readable."""
        nodes = BL.load_nodes()
        for row in BL.source_uncited(nodes, limit=50):
            if row["leverage"] < min(1.0, 0.35 + 0 / 40.0) * 0.61:
                self.assertIn(
                    "names tool", row["evidence"],
                    "{} was discounted without saying why".format(row["node"]))

    def test_tool_regex_matches_this_repos_layout(self):
        self.assertTrue(BL.TOOL_REF.findall("see tools/bond_ladder_study.py for it"))
        self.assertFalse(BL.TOOL_REF.findall("no tool named here"))


class ResolvedHandoffItemsDropOutTests(unittest.TestCase):
    """A handoff's Open list is a DATED record; staleness must be computed, not edited.

    F149 was listed open in HANDOFF_2026-07-25.md and later resolved by a Finding. It
    kept topping the queue anyway: the doc cannot know, and the anti-repetition filter
    only looks at RECENT commits, so the item would resurface every time those commits
    aged out of the window. Rewriting the handoff would be rewriting history — the fix
    is to cross-check the named nodes against the web.
    """

    def test_an_item_whose_nodes_are_all_resolved_is_dropped(self):
        nodes = BL.load_nodes()
        closed = {t for t, _by in BL._nodes_resolved_since(nodes)}
        if not closed:
            self.skipTest("no node has been resolved yet")
        heads = {t["title"] for t in BL.source_open_items(limit=20)}
        for head in heads:
            named = set(re.findall(r"\b([FDEH]\d+)\b", head))
            if named:
                self.assertFalse(
                    named <= closed,
                    "handoff item {!r} names only resolved node(s) {} but is still "
                    "queued".format(head, sorted(named & closed)))

    def test_items_naming_NO_node_are_still_kept(self):
        """Most handoff items are prose tasks with no node id; dropping those would
        silently empty the highest-leverage source."""
        heads = [t["title"] for t in BL.source_open_items(limit=20)]
        self.assertTrue(heads, "the handoff open list produced nothing at all")
        self.assertTrue(
            any(not re.findall(r"\b([FDEH]\d+)\b", h) for h in heads),
            "every remaining handoff item names a node — the no-node path is untested")

    def test_resolution_only_counts_from_a_CURRENT_node(self):
        """A superseded node's `resolves` edge must not close anything."""
        nodes = BL.load_nodes()
        for target, by in BL._nodes_resolved_since(nodes):
            self.assertEqual(
                str(nodes[by].get("status", "current")), "current",
                "{} is credited with resolving {} but is not current".format(by, target))


class FiguresMeanMeasurementsNotDigitGroupsTests(unittest.TestCase):
    """H45 topped the uncited queue with "11 figures" and had none.

    Its numbers were `10-K`/`10-Q` (form names), `FD-00`/`FD-01` (artifact ids),
    `1/5/20/60` (event horizons) and `2010/2018/2019/2022/2023` (train/select/holdout
    split years). A pre-registered DESIGN has specifications, not claims; asking it to
    cite evidence for `10-K` is noise, and noise at the top of the queue costs a whole
    cycle.
    """

    def test_form_names_are_not_counted(self):
        self.assertEqual(BL._figures("comparable 10-K and 10-Q filings"), set())

    def test_artifact_and_node_ids_are_not_counted(self):
        self.assertEqual(BL._figures("FD-00/FD-01 extend F105 and H44"), set())

    def test_calendar_years_are_not_counted(self):
        self.assertEqual(BL._figures("train 2010-2018, select 2019-2022"), set())

    def test_real_measurements_ARE_still_counted(self):
        """The filter must not silence the metric it exists to sharpen."""
        figs = BL._figures("additions moved +10.8709% relative to SPY, 8.65x volume, "
                           "win rate 48.9%")
        self.assertIn("10.8709", figs)
        self.assertIn("8.65", figs)
        self.assertIn("48.9", figs)

    def test_h45_no_longer_reaches_the_five_figure_floor(self):
        nodes = BL.load_nodes()
        if "H45" not in nodes:
            self.skipTest("H45 is gone")
        self.assertLess(
            len(BL._figures(str(nodes["H45"].get("body", "")))), 5,
            "H45 counts 5+ figures again — either its body gained real measurements "
            "or the filter regressed")


class EvidenceReachesUpstreamNotJustDownstreamTests(unittest.TestCase):
    """The loop was re-queueing work it had already done.

    A Finding that publishes a study and links `F113:supports` puts the document one
    INBOUND hop from F113. Only `resolves` was followed inbound, so F111/F113/F114/F115
    stayed flagged as uncited after their docs were written a few cycles earlier. This
    metric asks whether a reader can REACH a document, so the traversal should be
    symmetric across evidence-carrying edges; entailment is a different question and is
    not what the floor measures.
    """

    def test_the_upstream_edge_set_covers_more_than_resolves(self):
        self.assertIn("resolves", BL.UPSTREAM_EVIDENCE)
        for etype in ("supports", "refines", "builds_on", "evidenced_by"):
            self.assertIn(etype, BL.UPSTREAM_EVIDENCE,
                          "{} no longer carries evidence upstream — nodes whose docs "
                          "were published by a supporting Finding will be re-queued"
                          .format(etype))

    def test_nodes_whose_docs_were_published_upstream_are_cleared(self):
        nodes = BL.load_nodes()
        queued = {r["node"] for r in BL.source_uncited(nodes, limit=300)}
        for nid in ("F111", "F113", "F114", "F115"):
            if nid not in nodes:
                continue
            self.assertNotIn(
                nid, queued,
                "{} is queued as uncited although a supporting Finding cites its "
                "published study — the direction-blindness is back".format(nid))

    def test_the_clearing_edges_really_are_inbound(self):
        """Non-vacuity: these nodes do NOT cite the doc themselves."""
        nodes = BL.load_nodes()
        if "F113" not in nodes:
            self.skipTest("F113 is gone")
        self.assertEqual(
            BL.DOC_REF.findall(str(nodes["F113"].get("body", ""))), [],
            "F113 now cites a doc directly, so the inbound path is untested here")

    def test_the_queue_shrank_but_did_not_empty(self):
        """Both directions: over-suppression is the starvation failure this engine
        exists to avoid."""
        rows = BL.source_uncited(BL.load_nodes(), limit=300)
        self.assertGreater(len(rows), 20, "the uncited queue collapsed — check for "
                                          "over-suppression")
        self.assertLess(len(rows), 85, "the queue did not shrink; neither fix took")
