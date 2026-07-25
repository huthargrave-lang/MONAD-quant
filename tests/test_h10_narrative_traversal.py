"""H10's experiment, run: can `ctx walk/why` narrate the project's central story?

H10 asks whether the repo's most important epistemic arc — headline Sharpe 25–94 →
morning-only artifact (F13/F14) → daily edge is real (F15/F16) → the %-stop exit destroys
it (F17/F19) → OOS rejection and the static allocation (F22/D6) — is walkable with
traversal alone, and proposes adding "reversal-arc edges" if it is not.

**It is not walkable, and the proposed fix would make it worse.** Measured on the eight
story nodes:

* Of 7 consecutive pairs, exactly **1** has a direct forward edge (`F16 drives F17`).
  **4** have a direct *reverse* edge (`refines`, `supports`, `builds_on`, `relates`).
  The web encodes **provenance** — a new node points back at the older one it refines or
  supports — not **narrative**. Forward traversal is running the graph against its grain.
* The shortest directed path from F13 to D6 is `F13 → F3 → D1 → D6`: it visits **zero**
  of the six intermediate story nodes. Traversal yields *a* path, not *the* path.
* Two super-hubs cause that. D6 has degree 126 and D4 degree 33 (26 inbound). **5 of 7**
  consecutive pairs route their shortest path through D4 — a hub with 26 inbound edges
  puts any two of its neighbours 2 hops apart, which destroys sequence information.

Adding forward duplicates of every provenance edge would raise those degrees further and
create more shortcuts, so it would degrade exactly the property H10 wants.

**The constructive half: narrative order is temporal, and node-ID order is a valid proxy.**
Checked across the whole web, ID order is monotone in capture date for D, E and H with
**zero** inversions, and for F with two — both of which are nodes whose recorded date is an
*amendment* (`status: superseded`) timestamp rather than a creation one. So the story can
be narrated by sorting the relevant nodes by ID, with no new edges at all.

**And there is a catch worth recording.** 38 nodes carry no date whatsoever, and they are
exactly the earliest block — D1–D7, E1–E9, F1–F17, H1–H8 — which predates the `note.py`
capture footer. That block contains the entire narrative spine H10 cares about (F13, F14,
F16, F17, D4, D6). The one part of the web with neither ordering edges *nor* timestamps is
the part holding the central story. ID order is what makes it recoverable anyway.
"""
import collections
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402

STORY = ["F13", "F14", "F15", "F16", "F17", "F19", "F22", "D6"]

# The pre-convention block: nodes captured before note.py stamped a date footer.
# It can only shrink (a backfill) — a new undated node means the convention broke.
UNDATED = {
    "D1", "D2", "D3", "D4", "D6", "D7",
    "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F10", "F11", "F12", "F13",
    "F14", "F16", "F17",
    "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8",
}

# The two F-order inversions, both amendment timestamps rather than creation dates.
AMENDED = {"F9", "F15"}


def graph():
    nodes, _ = ctx._parse_web()
    adj = collections.defaultdict(list)
    for nid, n in nodes.items():
        for e in n.get("edges", []):
            adj[nid].append((e["target"], e["type"]))
    return nodes, adj


def shortest(adj, nodes, src, dst):
    seen = {src: None}
    queue = collections.deque([src])
    while queue:
        cur = queue.popleft()
        if cur == dst:
            break
        for tgt, _ty in adj[cur]:
            if tgt in nodes and tgt not in seen:
                seen[tgt] = cur
                queue.append(tgt)
    if dst not in seen:
        return None
    path, cur = [dst], dst
    while seen[cur]:
        cur = seen[cur]
        path.append(cur)
    return list(reversed(path))


def node_date(nodes, nid):
    m = re.search(r"_— captured [^,]+, (\d{4}-\d{2}-\d{2})_", nodes[nid]["body"])
    return m.group(1) if m else ctx._node_meta(nodes[nid]).get("at")


class ForwardTraversalCannotNarrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.adj = graph()

    def test_almost_no_consecutive_pair_has_a_direct_FORWARD_edge(self):
        forward = [(a, b) for a, b in zip(STORY, STORY[1:])
                   if any(t == b for t, _ in self.adj[a])]
        self.assertLessEqual(
            len(forward), 1,
            "the story now has {} direct forward edges ({}). If narrative arcs were "
            "added, H10's premise is closing — re-run the measurement and update the "
            "node rather than editing this test.".format(len(forward), forward))

    def test_the_reverse_direction_is_where_the_edges_actually_are(self):
        reverse = [(a, b) for a, b in zip(STORY, STORY[1:])
                   if any(t == a for t, _ in self.adj[b])]
        self.assertGreaterEqual(
            len(reverse), 4,
            "fewer than 4 consecutive pairs carry a reverse edge ({}) — the "
            "provenance-not-narrative reading rests on this asymmetry".format(reverse))
        self.assertGreater(len(reverse), len(
            [1 for a, b in zip(STORY, STORY[1:]) if any(t == b for t, _ in self.adj[a])]),
            "reverse edges no longer outnumber forward ones")

    def test_the_endpoint_shortest_path_visits_NO_story_node(self):
        path = shortest(self.adj, self.nodes, "F13", "D6")
        self.assertIsNotNone(path, "F13 no longer reaches D6 at all")
        visited = [n for n in path[1:-1] if n in set(STORY)]
        self.assertEqual(
            visited, [],
            "the F13->D6 shortest path now visits story node(s) {} — traversal may be "
            "starting to narrate; re-measure before citing H10".format(visited))
        self.assertLessEqual(len(path), 4, "the shortcut got longer: {}".format(path))

    def test_the_chain_routes_through_the_D4_hub(self):
        via = sum(1 for a, b in zip(STORY, STORY[1:])
                  if (p := shortest(self.adj, self.nodes, a, b)) and "D4" in p[1:-1])
        self.assertGreaterEqual(
            via, 5,
            "only {} of 7 consecutive pairs route through D4 — the hub explanation for "
            "the lost sequence information is weakening".format(via))

    def test_the_hubs_are_large_enough_to_short_circuit_anything(self):
        indeg = collections.Counter()
        for nid in self.nodes:
            for tgt, _ty in self.adj[nid]:
                indeg[tgt] += 1
        self.assertGreaterEqual(indeg["D4"], 20,
                                "D4's in-degree fell below 20; re-measure the hub effect")
        total = {n: indeg[n] + len(self.adj[n]) for n in self.nodes}
        self.assertEqual(max(total, key=total.get), "D6",
                         "D6 is no longer the highest-degree node")


class NarrativeOrderIsTemporalTests(unittest.TestCase):
    """The constructive half: no new edges needed."""

    @classmethod
    def setUpClass(cls):
        cls.nodes, _ = graph()

    def test_id_order_is_monotone_in_capture_date(self):
        by_kind = collections.defaultdict(list)
        for nid in self.nodes:
            m = re.match(r"([A-Za-z]+)(\d+)$", nid)
            if m:
                by_kind[m.group(1)].append((int(m.group(2)), nid))
        for kind, items in by_kind.items():
            items.sort()
            dated = [(nid, node_date(self.nodes, nid)) for _n, nid in items
                     if node_date(self.nodes, nid)]
            inversions = [(dated[i][0], dated[i + 1][0])
                          for i in range(len(dated) - 1)
                          if dated[i][1] > dated[i + 1][1]]
            unexplained = [pair for pair in inversions
                           if not (set(pair) & AMENDED)]
            self.assertEqual(
                unexplained, [],
                "{}-kind ID order is no longer monotone in capture date: {}. ID order "
                "is what makes the story narratable without new edges, so an "
                "unexplained inversion breaks the remedy.".format(kind, unexplained))

    def test_the_known_inversions_are_AMENDMENT_dates_not_creation_dates(self):
        """Otherwise the exemption above is a blanket excuse."""
        for nid in AMENDED:
            meta = ctx._node_meta(self.nodes[nid])
            self.assertEqual(
                meta["status"], "superseded",
                "{} is exempted from the ID-order check as an amended node, but it is "
                "no longer superseded — the exemption no longer applies".format(nid))

    def test_sorting_the_story_by_id_reproduces_its_order(self):
        findings = [n for n in STORY if n.startswith("F")]
        self.assertEqual(
            findings, sorted(findings, key=lambda s: int(s[1:])),
            "the story's Finding IDs are no longer in narrative order, so ID sort "
            "stops being a valid narration axis")


class TheSpineHasNeitherEdgesNorDatesTests(unittest.TestCase):
    """The catch. A ratchet: the undated set may shrink, never grow."""

    @classmethod
    def setUpClass(cls):
        cls.nodes, _ = graph()

    def test_the_undated_set_is_the_known_pre_convention_block(self):
        undated = {nid for nid in self.nodes if not node_date(self.nodes, nid)}
        self.assertEqual(
            undated - UNDATED, set(),
            "new undated node(s) {}: every node captured through note.py carries a date "
            "footer, so this means the capture convention was bypassed".format(
                sorted(undated - UNDATED)))
        backfilled = UNDATED - undated
        self.assertEqual(
            backfilled, set(),
            "dates were backfilled for {} — good; remove them from UNDATED".format(
                sorted(backfilled)))

    def test_the_undated_block_contains_the_story_spine(self):
        """Which is why H10's question had no easy answer: the central narrative is
        exactly the part with neither ordering edges nor timestamps."""
        spine = {"F13", "F14", "F16", "F17", "D4", "D6"}
        self.assertTrue(
            spine <= UNDATED,
            "part of the narrative spine is now dated ({}) — the framing above is "
            "softening".format(sorted(spine - UNDATED)))

    def test_most_of_the_web_IS_dated(self):
        """Otherwise 'the oldest nodes lack dates' is just 'nothing has dates'."""
        dated = sum(1 for nid in self.nodes if node_date(self.nodes, nid))
        self.assertGreater(dated / len(self.nodes), 0.85,
                           "under 85% of nodes carry a date; the contrast the finding "
                           "rests on has weakened")


if __name__ == "__main__":
    unittest.main()
