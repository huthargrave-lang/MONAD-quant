"""Status hygiene for the research web: what CLOSES an open node, and the ratchets that
keep `ctx web --pending` honest. Decision debate 2026-10-29 (direction D-4), record in
`docs/research/WEB_HYGIENE_QUESTION.md`.

`--pending` listed 89 items while 24 of its hypotheses already carried an inbound
`resolves` from a current Finding/Decision and D7 was titled RESOLVED. Two tools read
"open" two ways — `ctx` from the title, `research_backlog` from the edge. The consensus:

  * An H is CLOSED when a CURRENT, UNCONTRADICTED F or D carries `resolves` -> it
    (`ctx._resolved_hypotheses`; SCHEMA §5 made operative). Direction is part of the
    rule: E7->H5 and H8->D4 close nothing. `refines` narrows and leaves open.
  * A D is open unless superseded or titled RESOLVED/DONE. No inference from `refines`.
  * `note.py` refuses `--type resolves` in any other direction at every write site.

The live-web guards below are SET ratchets, not count ceilings. A ceiling fires on every
legitimate capture (38 pending-kind nodes landed in 2026-06 alone); a set forbids only
SILENT change. Reopening a closed node, or fixing an off-direction edge, is legitimate —
it is acknowledged by editing the set in the same commit.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx                            # noqa: E402
import note                           # noqa: E402
import epistemic_audit_lab as LAB     # noqa: E402  (research_backlog's parser)
import research_backlog as RB         # noqa: E402

WEB_PATH = ROOT / "RESEARCH_WEB.md"


def _in_synthetic_web(text, fn):
    """Run fn() with ctx.WEB repointed at synthetic web markdown (as test_research_web)."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
        tf.write(text)
        name = tf.name
    old = ctx.WEB
    try:
        ctx.WEB = name
        return fn()
    finally:
        ctx.WEB = old
        os.unlink(name)


# Every way a `resolves` edge can FAIL to close, next to the one way it does.
SYNTHETIC = """\
### F1 — answers H1 (current, undisputed)
body. Links: [[H1|resolves]].

### F2 — [SUPERSEDED by F1] once answered H2
<!-- status: superseded; by: F1; reason: reversed -->
body. Links: [[H2|resolves]].

### F3 — answers H3 but is disputed by F4
body. Links: [[H3|resolves]].

### F4 — disputes F3
body. Links: [[F3|contradicts]].

### F5 — narrows H4 and names what remains open
body. Links: [[H4|refines]].

### H1 — OPEN: answered by F1
body.

### H2 — OPEN: its only resolver is superseded
body.

### H3 — OPEN: its only resolver is contradicted
body.

### H4 — OPEN: only refined, never resolved
body.

### H5 — OPEN: "resolved" only by an experiment
body.

### H6 — OPEN: "resolved" only by another hypothesis
body.

### H7 — a question whose title carries no OPEN tag
body.

### H8 — IN PROGRESS: a question being worked
body. Links: [[H6|resolves]].

### E1 — DONE: an experiment that claims to resolve H5
body. Links: [[H5|resolves]].

### D1 — a standing gate that also resolves H1
body. Links: [[H1|resolves]].

### D2 — RESOLVED: a closed decision
body.

### D3 — DONE: an applied decision
body.

### D4 — [SUPERSEDED by D1] an old gate
<!-- status: superseded; by: D1; reason: decayed -->
body.
"""


class ThePredicateReadsClosureFromEdges(unittest.TestCase):
    """`_is_open_work` on a fixture that exercises every clause — a real test of the
    rule, in place of the proposal's `open ∧ resolved == ∅` check, which the predicate
    makes true by construction and which therefore could never fail."""

    @classmethod
    def setUpClass(cls):
        cls.nodes = _in_synthetic_web(SYNTHETIC, lambda: ctx._parse_web()[0])
        cls.resolved = ctx._resolved_hypotheses(cls.nodes)

    def _open(self):
        return {nid for nid, n in self.nodes.items()
                if ctx._is_open_work(nid, n, self.nodes, self.resolved)}

    def test_only_a_current_uncontradicted_f_or_d_closes_a_hypothesis(self):
        self.assertEqual(self.resolved, {"H1"})

    def test_a_superseded_resolver_does_not_close(self):
        self.assertIn("H2", self._open())

    def test_a_contradicted_resolver_does_not_close(self):
        self.assertIn("H3", self._open())

    def test_refines_narrows_but_leaves_open(self):
        self.assertIn("H4", self._open())

    def test_an_off_direction_resolves_closes_nothing(self):
        self.assertIn("H5", self._open(), "E -> H is not the schema's direction")
        self.assertIn("H6", self._open(), "H -> H is not the schema's direction")

    def test_the_title_tag_is_an_echo_not_the_record(self):
        open_ = self._open()
        self.assertNotIn("H1", open_, "titled OPEN yet answered by F1 — the edge wins")
        self.assertNotIn("H7", open_, "no OPEN/IN PROGRESS tag and no edge: not open work")
        self.assertIn("H8", open_, "IN PROGRESS counts as open")

    def test_decisions_close_by_title_or_supersession_only(self):
        open_ = self._open()
        self.assertIn("D1", open_)
        self.assertNotIn("D2", open_, "RESOLVED title closes a decision")
        self.assertNotIn("D3", open_, "DONE title closes a decision")
        self.assertNotIn("D4", open_, "a superseded decision is never open")

    def test_findings_and_experiments_are_not_open_work_by_kind(self):
        self.assertFalse(self._open() & {"F1", "F2", "F3", "F4", "F5", "E1"})

    def test_the_whole_fixture(self):
        self.assertEqual(self._open(), {"H2", "H3", "H4", "H5", "H6", "H8", "D1"})

    def test_a_one_off_call_derives_the_resolved_set_itself(self):
        # Listings pass `resolved` precomputed (one edge scan per listing, not per node);
        # a one-off call without it must reach the same answer.
        for nid, n in self.nodes.items():
            self.assertEqual(ctx._is_open_work(nid, n, self.nodes),
                             ctx._is_open_work(nid, n, self.nodes, self.resolved), nid)

    def test_the_resolved_set_accepts_a_precomputed_contradiction_map(self):
        contra = ctx._contradicted_by(self.nodes)
        self.assertEqual(ctx._resolved_hypotheses(self.nodes, contra), self.resolved)


class ThePendingListStaysHonest(unittest.TestCase):
    """Set ratchets on the live web."""

    # Frozen 2026-10-29 (hygiene debate r2; 26 ids). H members are hypotheses a current,
    # uncontradicted F/D `resolves` — including H9, H36 and H37, which the debate's own
    # Tier 1 writes closed (commit 5e84823) — plus D7, whose title is RESOLVED. These
    # left `--pending` by the predicate change (89 -> 63), with no web write.
    # Reopening one is legitimate but must be ACKNOWLEDGED: remove the id here in the
    # same commit as the retype/supersede that reopens it. New captures never touch
    # this set — it forbids silent reopening, nothing else.
    CLOSED_BY_HYGIENE = frozenset({
        "D7", "H9", "H10", "H11", "H12", "H13", "H15", "H16", "H17", "H18", "H19", "H20",
        "H23", "H25", "H27", "H36", "H37", "H38", "H39", "H40", "H41", "H42", "H43", "H45",
        "H61", "H404703"})

    # The two resolvers whose bodies NAMED a remainder (F238 -> H22: "two genuinely open
    # and blocked on data"; F168 -> H50: "WHAT GENUINELY REMAINS OPEN … PARTIALLY DONE")
    # were retyped to `refines` in Tier 1, so their questions stay listed. A later
    # Finding may close them for real — by removing the id here in that commit.
    KEPT_OPEN_BY_HYGIENE = {"H22": ("F238", "refines"), "H50": ("F168", "refines")}

    # 14 live `resolves` edges violated SCHEMA §5 direction when the debate ran; F41->D4
    # was retyped in Tier 1 and these 13 remain. Two (E7->H5, H8->D4) are cue-inferred
    # from untyped links, so `note.py retype` cannot fix them ("found 0") — they need a
    # typed link. SET-EQUALITY: fails if one APPEARS (note.py should have refused it)
    # and if one is FIXED (shrink the set, and enjoy it). None of them closes anything.
    KNOWN_OFF_DIRECTION_RESOLVES = frozenset({
        ("H2", "F7"), ("H8", "D4"), ("E4", "H1"), ("E5", "H3"), ("E6", "F4"), ("E6", "H2"),
        ("E7", "H5"), ("F39", "F38"), ("E38", "H42"), ("E39", "H43"), ("E103", "H62"),
        ("F199", "F149"), ("F264", "F204")})

    @classmethod
    def setUpClass(cls):
        cls.nodes = ctx._parse_web()[0]
        cls.resolved = ctx._resolved_hypotheses(cls.nodes)

    def _is_open(self, nid):
        return ctx._is_open_work(nid, self.nodes[nid], self.nodes, self.resolved)

    def test_hygiene_closures_stay_closed(self):
        reopened = sorted(n for n in self.CLOSED_BY_HYGIENE if n in self.nodes and self._is_open(n))
        gone = sorted(self.CLOSED_BY_HYGIENE - set(self.nodes))
        self.assertEqual((reopened, gone), ([], []),
                         f"reopened without acknowledgement: {reopened}; vanished: {gone}. If "
                         "reopening is intended, remove the id from CLOSED_BY_HYGIENE in this commit.")

    def test_hygiene_closures_are_answered_not_retracted(self):
        # Policy rule 2: answered != withdrawn. Every member must be closed by an ANSWER
        # (a `resolves` edge, or D7's RESOLVED title), never by a supersession stamped on
        # a question that other live nodes still legitimately cite.
        for nid in sorted(self.CLOSED_BY_HYGIENE, key=ctx._node_sort_key):
            self.assertFalse(ctx._is_superseded(self.nodes[nid]), f"{nid} was superseded, not answered")
            if nid[:1] == "H":
                self.assertIn(nid, self.resolved, f"{nid}: no current, uncontradicted F/D resolves it")
            else:
                self.assertRegex(self.nodes[nid]["title"], r"^\s*(RESOLVED|DONE)\b")

    def test_resolvers_that_named_a_remainder_keep_their_questions_open(self):
        for h, (src, etype) in self.KEPT_OPEN_BY_HYGIENE.items():
            self.assertTrue(self._is_open(h), f"{h} was closed; its resolver named open parts")
            got = {e["target"]: e["type"] for e in self.nodes[src]["edges"]}.get(h)
            self.assertEqual(got, etype, f"{src} -> {h} is {got!r}; the debate retyped it to {etype}")

    def test_off_direction_resolves_is_exactly_the_known_set(self):
        actual = {(nid, e["target"]) for nid, n in self.nodes.items() for e in n["edges"]
                  if e["type"] == "resolves" and not (nid[:1] in ("F", "D") and e["target"][:1] == "H")}
        self.assertEqual(actual, self.KNOWN_OFF_DIRECTION_RESOLVES,
                         f"new: {sorted(actual - self.KNOWN_OFF_DIRECTION_RESOLVES)}; "
                         f"fixed: {sorted(self.KNOWN_OFF_DIRECTION_RESOLVES - actual)}")

    def test_off_direction_edges_close_nothing(self):
        for _, tgt in self.KNOWN_OFF_DIRECTION_RESOLVES:
            if tgt in self.nodes and tgt[:1] == "H" and not ctx._is_superseded(self.nodes[tgt]):
                self.assertNotIn(tgt, self.resolved - self._resolved_in_direction(tgt), tgt)

    def _resolved_in_direction(self, h):
        # H ids a schema-direction edge resolves — so the assertion above tolerates an H
        # that is ALSO properly resolved by an F/D (H42, H43 are).
        return {h} if any(nid[:1] in ("F", "D") and not ctx._is_superseded(n)
                          for nid, n in self.nodes.items()
                          for e in n["edges"] if e["type"] == "resolves" and e["target"] == h) else set()

    def test_backlog_and_ctx_agree_on_the_resolved_target_set(self):
        """AGREEMENT ON THE RESOLVED-TARGET SET — not "the same rule". research_backlog's
        `_nodes_resolved_since` runs on the epistemic_audit_lab parser (tuple edges,
        a `status` key) and applies no direction or contradiction filter: it is the
        looser, advisory reading (it counts E7 -> H5). What the two must agree on is
        the raw set of targets a CURRENT node `resolves` — 37 today (36 when the debate
        ran; the Tier 1 Finding that resolves H9 added one). ctx's closure set is that
        set narrowed by direction and contradiction, so it must be a subset."""
        epi = LAB.parse_web(LAB.WEB.read_text(encoding="utf-8"))
        backlog = {t for t, _ in RB._nodes_resolved_since(epi)}
        raw_ctx = {e["target"] for nid, n in self.nodes.items() if not ctx._is_superseded(n)
                   for e in n["edges"] if e["type"] == "resolves"}
        self.assertEqual(backlog, raw_ctx,
                         f"backlog-only: {sorted(backlog - raw_ctx)}; ctx-only: {sorted(raw_ctx - backlog)}")
        self.assertLessEqual(self.resolved, raw_ctx)

    def test_the_cli_lists_exactly_the_predicate(self):
        # test_research_web pins map == CLI; this pins CLI == the predicate directly, so
        # the inline copy of the rule that used to live in cmd_web cannot come back.
        import contextlib
        import io
        import types
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx.cmd_web(types.SimpleNamespace(node=None, pending=True, live=False, lint=False))
        listed = set(re.findall(r"^  ([A-Z]+\d+) ", buf.getvalue(), re.M))
        self.assertEqual(listed, {nid for nid in self.nodes if self._is_open(nid)})
        self.assertFalse(listed & self.CLOSED_BY_HYGIENE)


class NoteRefusesAnOffDirectionResolves(unittest.TestCase):
    """`note.py` refuses `--type resolves` unless source is F/D and target is H, at all
    three edge-writing sites (`add --link`, `link`, `retype`). Dry-run only: none of
    these can write, and each asserts the web is byte-identical afterwards."""

    def _note(self, *args):
        before = WEB_PATH.read_bytes()
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "note.py"), *args],
                             capture_output=True, text=True, timeout=240, cwd=str(ROOT))
        self.assertEqual(WEB_PATH.read_bytes(), before, "note.py wrote without --commit")
        return out.returncode, out.stdout + out.stderr

    def test_the_helper_refuses_every_off_direction_pair_and_only_those(self):
        for s in "FHED":
            for t in "FHED":
                if s in "FD" and t == "H":
                    note._check_resolves_direction(f"{s}1", f"{t}2", "resolves")     # allowed
                else:
                    with self.assertRaises(SystemExit, msg=f"{s} -> {t} should be refused"):
                        note._check_resolves_direction(f"{s}1", f"{t}2", "resolves")
        # `add` passes a kind placeholder for the not-yet-allocated source
        note._check_resolves_direction("F(new)", "H5", "resolves")
        with self.assertRaises(SystemExit):
            note._check_resolves_direction("E(new)", "H5", "resolves")
        # every other edge type is untouched, whatever the direction
        for etype in sorted(ctx.EDGE_TYPES - {"resolves"}):
            note._check_resolves_direction("E1", "H2", etype)
            note._check_resolves_direction("H1", "D2", etype)

    def test_the_message_names_the_schema_and_the_alternatives(self):
        with self.assertRaises(SystemExit) as cm:
            note._check_resolves_direction("E7", "H5", "resolves")
        msg = str(cm.exception)
        for needle in ("SCHEMA §5", "E7 -> H5", "off-direction", "refines"):
            self.assertIn(needle, msg)

    def test_link_refuses_an_experiment_resolving_a_hypothesis(self):
        rc, out = self._note("link", "E1", "H5", "--type", "resolves")
        self.assertNotEqual(rc, 0)
        self.assertIn("off-direction", out)

    def test_link_refuses_a_hypothesis_resolving_a_hypothesis(self):
        rc, out = self._note("link", "H8", "H9", "--type", "resolves")
        self.assertNotEqual(rc, 0)
        self.assertIn("off-direction", out)

    def test_link_refuses_a_finding_resolving_a_decision(self):
        rc, out = self._note("link", "F2", "D4", "--type", "resolves")
        self.assertNotEqual(rc, 0)
        self.assertIn("off-direction", out)

    def test_retype_refuses_turning_an_experiment_edge_into_resolves(self):
        # E78 carries exactly one parsed edge to H33 (relates), so this reaches the
        # direction check rather than the "exactly one edge" guard.
        rc, out = self._note("retype", "E78", "H33", "--type", "resolves")
        self.assertNotEqual(rc, 0)
        self.assertIn("off-direction", out)

    def test_add_refuses_a_new_experiment_that_resolves(self):
        rc, out = self._note("add", "--kind", "E", "--title", "hygiene direction placeholder",
                             "--body", "placeholder body", "--link", "H5:resolves")
        self.assertNotEqual(rc, 0)
        self.assertIn("off-direction", out)
        self.assertIn("E(new) -> H5", out)

    def test_add_refuses_a_new_finding_that_resolves_a_decision(self):
        rc, out = self._note("add", "--kind", "F", "--title", "hygiene direction placeholder",
                             "--body", "placeholder body", "--link", "D4:resolves")
        self.assertNotEqual(rc, 0)
        self.assertIn("off-direction", out)

    def test_the_schema_direction_is_still_writable(self):
        # Positive control: F -> H `resolves` reaches the dry-run gate, not the refusal.
        rc, out = self._note("link", "F2", "H5", "--type", "resolves")
        self.assertNotIn("off-direction", out)
        self.assertIn("DRY RUN", out)


if __name__ == "__main__":
    unittest.main()
