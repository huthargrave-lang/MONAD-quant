#!/usr/bin/env python3
"""BACKLOG — what should the next research cycle work on?

An autonomous loop needs a *work-selection* engine, or it drifts: it redoes what it
just did, or picks whatever is most recently in mind rather than what matters. This is
that engine. It reads the repo and returns a ranked queue, with a concrete next action
per item and — critically — an **anti-repetition filter** keyed off recent commits, so
a loop that has just closed an item moves on instead of circling it.

It deliberately reports what `ctx health` cannot. `ctx health` returns 100/100 while
the web has a single articulation point, 50 dead-end hypotheses, and 143 nodes quoting
figures with no citation (F142, F151) — because health checks dangling references and
staleness, not leverage, connectivity, or reproducibility.

Sources, each a distinct failure mode this project has actually shipped:

* ``uncited``    — nodes quoting figures that reach no research doc (F142). Ranked by
                   reliance in-degree, so blast-radius x uncitedness comes first. That
                   ranking is what put D6 at the top.
* ``unresolved`` — hypotheses no Finding ever answered (F151: 50 of 74). Ranked by age.
* ``unguarded``  — idea<->code bridges with no ``guarded_by`` test. These are the
                   claims that rot silently, because code moves and prose does not.
* ``blocked``    — labs that cannot run offline, which is what makes a finding
                   unreproducible on a fresh checkout (F144/F156).
* ``open_item``  — the newest handoff's explicit open list, so human-stated priorities
                   outrank anything this tool infers.

Scoring is ``leverage * tractability``, both in [0,1], and both are *stated* rather
than learned — there is no data here to fit them on, and a fitted score would be false
precision. Ties break toward the cheaper item.

Stdlib only; read-only; writes nothing.

Commands::

    python3 tools/research_backlog.py next          # exactly one task, for a loop
    python3 tools/research_backlog.py list [-n 15]  # the ranked queue
    python3 tools/research_backlog.py json          # machine-readable
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "RESEARCH_WEB.md"
DOCS = REPO / "docs" / "research"

_TOOLS = str(Path(__file__).resolve().parent)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
import epistemic_audit_lab as _epi  # noqa: E402  (canonical web parser)

RELIANCE = {"relies_on", "supports", "refines", "builds_on"}


def _is_superseded(node: Mapping[str, object]) -> bool:
    """Whether a parsed node is retracted.

    `epistemic_audit_lab.parse_web` exposes `status` ("current"/"superseded"), NOT a
    boolean `superseded` key. Two sources here asked for `node.get("superseded")`,
    which is always None — so the filter never fired and F9/F3/F15, all superseded,
    sat in the uncited queue as work. F9 was next up: "publish a document for the
    figures of a finding that was inverted by F13".
    """
    return str(node.get("status", "current")).lower() == "superseded"
# Edge types that carry EVIDENCE upstream: if X--type-->Y and X cites a document, a
# reader standing at Y is one hop from that document. Used for doc-REACHABILITY only.
UPSTREAM_EVIDENCE = {"resolves", "supports", "refines", "builds_on", "evidenced_by"}
DOC_REF = re.compile(r"docs/research/([A-Za-z0-9_\-]+\.md)")
# A node naming a REPRODUCING TOOL is not uncited in the same sense as one naming
# nothing: it gives a reader a way to regenerate the result, just not a document
# holding the numbers. Measured across the web: 11 nodes cite a doc only, 74 cite
# both, 39 (10.3%) cite a TOOL ONLY, and 253 cite neither. A doc-only metric treats
# that middle group as uncited, which overstates the gap. They are ranked below
# doc-cited nodes but above uncited ones, not dropped.
TOOL_REF = re.compile(r"tools/([a-z0-9_]+)\.py")
FIGURE = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)(?:%|pp|bps|bp|bn|yr|mo|x)?(?![\w.])")

# How many recent commits count as "already worked on". Large enough to cover a long
# session, small enough that a genuinely stalled item resurfaces.
RECENT_COMMITS = 40

# Items the OWNER has deferred. These are removed from the queue but never hidden —
# `next` and `list` both report the count, and `list --deferred` prints them with
# their reasons. Silent truncation is the failure mode this engine exists to avoid;
# an item nobody can see is worse than one that keeps topping the queue.
#
# Add an entry ONLY on an explicit human decision, and record WHY. An unexplained
# entry is how a real blocker becomes invisible. Remove the entry when the block
# lifts — a deferral is a pause, not a verdict.
DEFERRED = {
    "open:-sweep-py-has-the-same-cache-footgun": (
        "Owner-deferred in the handoff that raised it: item 6 of HANDOFF_2026-07-25.md "
        "reads 'fenced WARN (selection-of-record), so left alone'. The investigation is "
        "DONE and guarded by tests/test_sweep_cache_guard.py, which found the handoff's "
        "premise was partly inverted — the cache is usually REJECTED (the read guard "
        "compares an intraday first bar against a midnight start), so the poison-cache "
        "risk is mostly moot while the rate-limit protection it exists for is absent. "
        "The residual is a one-line change to which data parameter selection sees, "
        "which is a sign-off decision, not a research one."
    ),
    "open:f148-the-utc-gate-": (
        "Owner-deferred 2026-07-25. Correcting either the timezone or the "
        "else-branch changes which bars produce entries, so every hourly backtest "
        "number moves. Needs explicit sign-off plus a re-sweep; the finding stands "
        "recorded in F148 meanwhile."
    ),
}


# Items that cannot be STARTED here, as distinct from ones an owner has chosen not to
# do. Every entry below needs a data source this environment cannot reach: SEC hosts
# return `403` at the proxy CONNECT stage, and the market-data providers are blocked the
# same way, so no filing corpus, XBRL fact, macro vintage or price panel can be fetched.
# Surfacing them as "test or retire it" burns a cycle per item and produces the same
# answer every time — the honest state is BLOCKED, not untested.
#
# This is deliberately a static list with a live re-check (`--recheck`) rather than a
# probe on every run: a network call in a backlog listing would be slow and flaky, and a
# silently-skipped item is worse than a slow one. If the block lifts, `--recheck` says so
# and these come straight back into rotation.
BLOCKED_ON_DATA = {
    "unresolved:H46": ("RN-01 needs filing TEXT plus contemporaneous XBRL; it also sits "
                       "downstream of FD-01, which needs the FD-00 corpus backfill.",
                       "https://www.sec.gov/"),
    "unresolved:H48": ("TA-01 needs multi-year cross-asset PRICE history (equities, ETFs, "
                       "BTC); no panel is committed and the providers are unreachable.",
                       "https://query1.finance.yahoo.com/"),
    "unresolved:H49": ("EV-01/NG-00 needs ALFRED macro vintages, 8-K event codes, CFTC "
                       "positioning, GDELT and SEC fails-to-deliver feeds.",
                       "https://www.sec.gov/"),
    "unresolved:H51": ("FD-NUM needs accession-scoped XBRL facts.",
                       "https://data.sec.gov/"),
    "unresolved:H52": ("FD-AMEND needs paired 10-K/A and 10-Q/A accessions and their "
                       "originals.", "https://data.sec.gov/"),
    "unresolved:H53": ("FD-GRAPH needs the filing ledger H51/H52 would produce, so it is "
                       "blocked twice over.", "https://data.sec.gov/"),
}


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(REPO), *args],
                             capture_output=True, text=True, timeout=30)
        return out.stdout
    except Exception:
        return ""


def recent_subjects(n: int = RECENT_COMMITS) -> List[str]:
    return [l.strip().lower() for l in
            _git("log", "--format=%s%n%b", "-n", str(n)).splitlines() if l.strip()]


# Digits that are NOT measurements: SEC form names, artifact ids, years, node ids.
# Counting these as "figures needing evidence" is how H45 — a pre-registered DESIGN
# whose only numbers are `10-K`/`10-Q`, `FD-00`/`FD-01`, event horizons and train/select
# split years — reached the top of the uncited queue with "11 figures". A design has
# specifications, not claims, and asking it to cite evidence for `10-K` is noise.
#
# Third pass (E100). Stripping bare years was not enough: an event-study node states
# its clocks as ISO timestamps and its subject as an index name, so `2026-07-24T15:04`
# survived as `-07`/`15`, `8:00 p.m.` as `00`, and `Nasdaq-100` as `100`. E100 reached
# the uncited queue with "5 figures" of which THREE were a date fragment, a clock
# fragment and half an index name; its only real numbers are the counts 12 and 13. The
# ISO alternative must come first — the year rule would otherwise consume `2026` and
# leave the rest of the timestamp behind as separate "figures".
NOT_A_MEASUREMENT = re.compile(
    r"\b\d{4}-\d{2}-\d{2}"                                        # ISO date …
    r"(?:T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?"   # … and time
    r"|\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?"             # clock times
    r"|\b(?:Nasdaq[- ]100|NDX|S&P\s*(?:500|400|600)"              # index names …
    r"|Russell\s*(?:1000|2000|3000)|MidCap\s*400|SmallCap\s*600)" # … carrying digits
    r"|\b(?:10-[KQ]|8-K|20-F|13[FDG]|S-\d|N-\d|Form\s+\d+)\b"     # SEC form names
    r"|\b[A-Z]{2,10}-\d{2}\b"                                     # artifact ids: FD-00
    r"|\b(?:19|20)\d{2}\b"                                        # calendar years
    r"|\b[FDEH]\d+\b",                                            # node ids
    re.I)


def _figures(text: str) -> set:
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    text = re.sub(r"(?<=\d),(?=\d\d\d)", "", text)
    text = NOT_A_MEASUREMENT.sub(" ", text)
    return {m.group(1) for m in FIGURE.finditer(text)
            if len(m.group(1).replace("-", "").replace(".", "")) >= 2}


def load_nodes() -> Dict[str, dict]:
    return _epi.parse_web(WEB.read_text(encoding="utf-8"))


def reliance_in_degree(nodes: Mapping[str, dict]) -> Dict[str, int]:
    deg: Dict[str, int] = collections.Counter()
    for node in nodes.values():
        for target, etype in node.get("edges", []):
            if etype in RELIANCE and target in nodes:
                deg[target] += 1
    return deg


# --------------------------------------------------------------------------- #
# sources                                                                      #
# --------------------------------------------------------------------------- #
def source_uncited(nodes, limit: int = 8) -> List[dict]:
    """Nodes quoting figures that reach no research doc, by reliance in-degree."""
    deg = reliance_in_degree(nodes)
    rows = []
    for nid, node in nodes.items():
        body = str(node.get("body", ""))
        if _is_superseded(node):
            continue
        figs = _figures(body)
        if len(figs) < 5:
            continue
        reachable = set(DOC_REF.findall(body))
        for target, _ in node.get("edges", []):
            if target in nodes:
                reachable |= set(DOC_REF.findall(str(nodes[target].get("body", ""))))
        # Follow `resolves` INBOUND too. Evidence flows downstream for a Finding
        # (F -> evidenced_by -> E -> doc) but UPSTREAM for a hypothesis: a resolved
        # H node's evidence lives in the Finding that resolved it. Following only
        # outgoing edges left H50 flagged as uncited immediately after a resolving
        # Finding was attached to it, which is direction-blindness, not a real gap.
        # ...and the same argument applies to every other UPSTREAM edge, not just
        # `resolves`. A Finding that publishes a study and links `F113:supports` puts
        # the document one inbound hop away; from F113 it was invisible, so the loop
        # re-queued four nodes (F111/F113/F114/F115) whose docs it had itself written
        # a few cycles earlier. This metric asks whether a reader can REACH a document
        # from the node, so traversal should be symmetric — entailment is a different
        # question and is not what the floor measures.
        for other in nodes.values():
            for target, etype in other.get("edges", []):
                if target == nid and etype in UPSTREAM_EVIDENCE:
                    reachable |= set(DOC_REF.findall(str(other.get("body", ""))))
        if reachable:
            continue
        # Second-class evidence: a reproducing tool named by the node or one hop out.
        tooled = set(TOOL_REF.findall(body))
        for target, _ in node.get("edges", []):
            if target in nodes:
                tooled |= set(TOOL_REF.findall(str(nodes[target].get("body", ""))))
        rows.append({
            "key": "uncited:{}".format(nid),
            "kind": "uncited",
            "node": nid,
            "title": str(node.get("title", ""))[:90],
            "evidence": "{} figures, 0 reachable docs{}, {} reliance dependents".format(
                len(figs),
                " (names tool {})".format(sorted(tooled)[0]) if tooled else "",
                deg.get(nid, 0)),
            # Leverage scales with how much of the graph leans on it, discounted when
            # a reproducing tool is at least named — that is a weaker gap than nothing.
            "leverage": min(1.0, 0.35 + deg.get(nid, 0) / 40.0) * (0.6 if tooled else 1.0),
            "tractability": 0.6,   # writing a doc is bounded work, but not trivial
            "action": ("Locate or reconstruct the evidence for {}'s figures and publish "
                       "docs/research/<STUDY>.md, then link it. If the numbers are NOT "
                       "recoverable, say so in the node — that is also a result."
                       .format(nid)),
        })
    rows.sort(key=lambda r: -r["leverage"])
    return rows[:limit]


# Edge types by which a Finding actually ANSWERS a hypothesis. `resolves` closes it;
# `supports`/`contradicts` are evidence bearing on the claim, i.e. it was tested. The
# rest are not answers: `relates` is the weakest link in the vocabulary, `builds_on` and
# `drives` point forward rather than back, and `refines` NARROWS a hypothesis while
# leaving it open — F194 refines H21 and H21's proposal is still untested.
#
# Counting ANY F->H edge as an answer hid 28 of 69 open hypotheses: 13 behind a bare
# `relates`, 14 behind `refines`, 3 `drives`, 2 `supports`. The queue showed 17 while 45
# had no `resolves` edge at all. Found the hard way — capturing a finding that said "H46
# is BLOCKED, not tested" linked `H46:relates` and thereby marked H46 answered.
ANSWERING_EDGES = {"resolves", "supports", "contradicts"}


def source_unresolved(nodes, limit: int = 6) -> List[dict]:
    """Hypotheses no Finding ever answered."""
    cited_by_finding = set()
    resolved = set()
    for nid, node in nodes.items():
        for target, etype in node.get("edges", []):
            if etype == "resolves":
                resolved.add(target)
            if (nid.startswith("F") and target.startswith("H")
                    and etype in ANSWERING_EDGES):
                cited_by_finding.add(target)
    rows = []
    for nid, node in nodes.items():
        if not nid.startswith("H") or _is_superseded(node):
            continue
        if nid in resolved or nid in cited_by_finding:
            continue
        title = str(node.get("title", ""))
        if re.search(r"\b(RESOLVED|DEAD|DONE|CLOSED)\b", title, re.I):
            continue
        rows.append({
            "key": "unresolved:{}".format(nid),
            "kind": "unresolved",
            "node": nid,
            "title": title[:90],
            "evidence": "no resolves edge; no Finding supports or contradicts it",
            "leverage": 0.5,
            "tractability": 0.45,
            "action": ("Test {} or retire it. An untested hypothesis that is never "
                       "closed biases the project's self-measured error rate toward "
                       "looking stable (F133/F151).".format(nid)),
        })
    rows.sort(key=lambda r: r["node"])
    return rows[:limit]


def source_unguarded(limit: int = 6) -> List[dict]:
    """Idea<->code bridges with no guarded_by test — the claims that rot silently."""
    path = REPO / "context_map.json"
    if not path.exists():
        return []
    try:
        bridges = json.loads(path.read_text(encoding="utf-8"))["graph_bridges"]["bridges"]
    except Exception:
        return []
    rows = []
    for b in bridges:
        if b.get("guarded_by"):
            continue
        rows.append({
            "key": "unguarded:{}".format(b.get("node")),
            "kind": "unguarded",
            "node": b.get("node"),
            "title": "code-claim about {}".format(", ".join(b.get("code", []))[:70]),
            "evidence": "bridge has no guarded_by test",
            "leverage": 0.7,      # a rotting code-claim misleads every future reader
            "tractability": 0.8,  # an AST/behavioural guard is usually a short test
            "action": ("Write a BIDIRECTIONAL guard for {}: it must fail if the claim "
                       "stops being true, with a message telling the maintainer to "
                       "supersede the WEB node rather than edit the test."
                       .format(b.get("node"))),
        })
    return rows[:limit]


def source_blocked_labs(limit: int = 5) -> List[dict]:
    """Labs that cannot run offline are findings nobody can reproduce."""
    rows = []
    for path in sorted((REPO / "tools").glob("*_study.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "data_cache" in text or "yfinance" not in text:
            continue
        rows.append({
            "key": "blocked:{}".format(path.name),
            "kind": "blocked",
            "node": None,
            "title": path.name,
            "evidence": "fetches network data without the validated cache guard",
            "leverage": 0.45,
            "tractability": 0.75,
            "action": ("Route {}'s cache through tools/data_cache.py so a blocked "
                       "fetch raises instead of writing a stub that every later run "
                       "trusts (F144).".format(path.name)),
        })
    return rows[:limit]


def _nodes_resolved_since(nodes: Mapping[str, dict]) -> set:
    """Nodes closed by a `resolves` edge from a node that is still current.

    A handoff's Open list is a DATED record — rewriting it would be rewriting history,
    so the list itself is left alone and the staleness is computed instead. Without
    this, an item naming a node that has since been resolved tops the queue forever:
    the doc cannot know, and the anti-repetition filter only looks at recent commits,
    so the item resurfaces the moment those commits age out.
    """
    closed = set()
    for nid, node in nodes.items():
        if str(node.get("status", "current")) != "current":
            continue
        for target, etype in node.get("edges", []):
            if etype == "resolves":
                closed.add((target, nid))
    return closed


def _config_opposing_citation_is_disclaimed() -> bool:
    """Is `config.py`'s EXIT_ON_OPPOSING_SIGNAL mention a warning rather than a claim?

    Deliberately NOT `"EXIT_ON_OPPOSING_SIGNAL" not in config.py`. F200 fixed the comment
    by *quoting the dead identifier inside a disclaimer*, so the symbol is still there and
    a naive existence check answers the opposite of the truth. What actually resolved the
    item is that the citation stopped asserting a live feature — plus the fact that live/
    still has no such flag, which is the half that would matter if someone reverted it.
    """
    try:
        config_src = (REPO / "config.py").read_text(encoding="utf-8")
    except OSError:
        return False
    if "no such flag or behaviour exists" not in config_src:
        return False
    live = REPO / "live"
    if not live.is_dir():
        return False
    return not any("EXIT_ON_OPPOSING_SIGNAL" in p.read_text(encoding="utf-8",
                                                            errors="ignore")
                   for p in live.rglob("*.py"))


# Open-list items written as PROSE — naming no node id — whose resolution is nevertheless
# decidable from the repository.
#
# `_nodes_resolved_since` closes items that NAME a node. F200 built that and deliberately
# kept everything else, because most open items are prose tasks and dropping them by
# default would silently empty the highest-leverage source. That left F200's own item
# pinned to the top forever: "config.py:120 cites EXIT_ON_OPPOSING_SIGNAL" names no node,
# so no `resolves` edge can ever reach it — even though F200 corrected the comment in the
# same cycle that recorded it.
#
# Each entry is a PREDICATE, not a resolved-flag: the item must keep re-earning its
# closure on every run, so reverting the underlying fix brings it straight back. Same
# design as BLOCKED_ON_DATA's live `--recheck` — a static claim about the repo that is
# never re-tested is the failure mode this whole file exists to avoid.
PROSE_RESOLVED = {
    "EXIT_ON_OPPOSING_SIGNAL": (
        _config_opposing_citation_is_disclaimed,
        "F200 rewrote the comment to mark the flag BACKTEST-ONLY and record that the "
        "advertised identifier never existed; live/ still has no such flag.",
    ),
}


def prose_resolution(head: str):
    """Return (resolved, why) for a prose open item, or (False, None) if untracked."""
    for fingerprint, (predicate, why) in PROSE_RESOLVED.items():
        if fingerprint in head:
            return (bool(predicate()), why)
    return (False, None)


def source_open_items(limit: int = 6) -> List[dict]:
    """The newest handoff's explicit open list. Human priorities outrank inference.

    Items whose named node has since been resolved are dropped (see
    `_nodes_resolved_since`), so a static doc cannot pin finished work to the top of
    the queue.
    """
    handoffs = sorted(DOCS.glob("HANDOFF_*.md"))
    if not handoffs:
        return []
    text = handoffs[-1].read_text(encoding="utf-8")
    section = re.search(r"\n##+\s*\d*\.?\s*Open[^\n]*\n(.*?)(?=\n##\s|\Z)", text, re.S)
    if not section:
        return []
    resolved = _nodes_resolved_since(load_nodes())
    resolved_ids = {target for target, _by in resolved}
    rows = []
    for m in re.finditer(r"^\s*\d+\.\s+\*\*(.+?)\*\*(.*)$", section.group(1), re.M):
        head = m.group(1).strip()
        named = set(re.findall(r"\b([FDEH]\d+)\b", head))
        if named and named <= resolved_ids:
            continue          # every node this item names has since been closed
        if not named and prose_resolution(head)[0]:
            continue          # names no node, but the repo says it is done (PROSE_RESOLVED)
        rows.append({
            "key": "open:{}".format(re.sub(r"\W+", "-", head.lower())[:40]),
            "kind": "open_item",
            "node": None,
            "title": head[:90],
            "evidence": "listed open in {}".format(handoffs[-1].name),
            "leverage": 0.85,     # a human wrote this down deliberately
            "tractability": 0.5,
            "action": (m.group(2).strip()[:240] or "See {}".format(handoffs[-1].name)),
        })
    return rows[:limit]


# --------------------------------------------------------------------------- #
# ranking                                                                      #
# --------------------------------------------------------------------------- #
def _recently_touched(task: Mapping[str, object], subjects: Sequence[str]) -> bool:
    """Has a recent commit already addressed this item?

    Anti-repetition is the difference between a loop and a stutter. Matching is
    deliberately loose (node id, or a distinctive title token) and errs toward
    SKIPPING: re-doing finished work wastes a whole cycle, whereas skipping a live
    item only defers it — it resurfaces once the commit falls out of the window.
    """
    node = task.get("node")
    if node:
        # A node id is a PRECISE key — match on it alone and stop. Falling through to
        # title tokens here was the bug: "code-claim about src/strategy/engine.py"
        # tokenises to `strategy`/`engine`, which appear in most commit bodies, and
        # suppressed 23 of 30 items instead of the 7 genuinely addressed.
        pat = re.compile(r"\b{}\b".format(re.escape(str(node).lower())))
        return any(pat.search(s) for s in subjects)

    # No node id (blocked labs, handoff items): match a DISTINCTIVE token only.
    # Generic engineering vocabulary matches everything, so it is excluded, and a
    # filename is required to appear whole rather than as a substring.
    title = str(task.get("title", "")).lower()
    generic = {"research", "should", "because", "strategy", "engine", "signals",
               "config", "study", "python", "tools", "claim", "code-claim", "about"}
    tokens = [t for t in re.findall(r"[a-z_][a-z_0-9]{5,}", title) if t not in generic]
    return any(re.search(r"\b{}\b".format(re.escape(t)), s)
               for t in tokens[:3] for s in subjects)


def collect(skip_recent: bool = True) -> List[dict]:
    nodes = load_nodes()
    tasks: List[dict] = []
    tasks += source_open_items()
    tasks += source_uncited(nodes)
    tasks += source_unguarded()
    tasks += source_unresolved(nodes)
    tasks += source_blocked_labs()

    subjects = recent_subjects() if skip_recent else []
    for t in tasks:
        t["score"] = round(float(t["leverage"]) * float(t["tractability"]), 4)
        t["recently_touched"] = bool(subjects) and _recently_touched(t, subjects)
        t["deferred_reason"] = DEFERRED.get(str(t["key"]))
        blocked = BLOCKED_ON_DATA.get(str(t["key"]))
        t["blocked_reason"] = blocked[0] if blocked else None
    fresh = [t for t in tasks
             if not t["recently_touched"] and not t["deferred_reason"]
             and not t["blocked_reason"]]
    fresh.sort(key=lambda t: (-t["score"], -t["tractability"], str(t["key"])))
    return fresh


def deferred(skip_recent: bool = True) -> List[dict]:
    """Owner-deferred items, so a deferral is visible rather than a disappearance."""
    nodes = load_nodes()
    big = 10_000
    tasks = (source_open_items(big) + source_uncited(nodes, big) + source_unguarded(big)
             + source_unresolved(nodes, big) + source_blocked_labs(big))
    return [dict(t, deferred_reason=DEFERRED[str(t["key"])])
            for t in tasks if str(t["key"]) in DEFERRED]


def blocked_on_data() -> List[dict]:
    """Items whose data this environment cannot reach — blocked, not untested.

    Built from UNLIMITED sources. Filtering the ranked top-N would make a blocked item
    invisible as soon as something older outranked it — which is how the count silently
    went to zero the first time this ran, right after `ANSWERING_EDGES` widened the
    unresolved queue from 17 to 43.
    """
    nodes = load_nodes()
    big = 10_000
    tasks = (source_open_items(big) + source_uncited(nodes, big) + source_unguarded(big)
             + source_unresolved(nodes, big) + source_blocked_labs(big))
    return [dict(t, blocked_reason=BLOCKED_ON_DATA[str(t["key"])][0],
                 probe=BLOCKED_ON_DATA[str(t["key"])][1])
            for t in tasks if str(t["key"]) in BLOCKED_ON_DATA]


def recheck_blocks(timeout: float = 8.0) -> List[tuple]:
    """Probe each distinct blocked host. Returns [(host, reachable, detail)].

    A block that is never re-tested becomes a permanent excuse, so this exists and is
    the only place the tool touches the network.
    """
    import urllib.error
    import urllib.request
    results = []
    for host in sorted({url for _, url in BLOCKED_ON_DATA.values()}):
        try:
            req = urllib.request.Request(host, method="HEAD",
                                         headers={"User-Agent": "monad-backlog-recheck"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                results.append((host, True, "HTTP {}".format(resp.status)))
        except Exception as exc:                      # noqa: BLE001 — any failure is a block
            results.append((host, False, type(exc).__name__ + ": " + str(exc)[:60]))
    return results


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def command_next(args) -> None:
    tasks = collect(skip_recent=not args.no_skip)
    if not tasks:
        print("BACKLOG EMPTY — every tracked item was addressed in the last "
              "{} commits.".format(RECENT_COMMITS))
        print("Do NOT stop. Open a genuinely new direction: pick an unexamined")
        print("fixture in docs/research/data/, an unaudited module, or a question")
        print("the web has never asked. Record it as a new H node first.")
        return
    held = deferred()
    if held:
        print("  ({} item(s) owner-deferred and excluded — "
              "`list --deferred` to see them)".format(len(held)))
    stuck = blocked_on_data()
    if stuck:
        print("  ({} item(s) blocked on unreachable data and excluded — "
              "`list --blocked` / `list --blocked --recheck`)".format(len(stuck)))
    if held or stuck:
        print()
    # Near-starvation: the anti-repetition window is hiding almost everything, which
    # means the loop has consumed the backlog faster than RECENT_COMMITS forgets. Say so
    # rather than handing over the last two leftovers as if the queue were healthy —
    # the same reasoning as the deferred and blocked counts above.
    total = len(collect(skip_recent=False))
    if total and (total - len(tasks)) / total > 0.85:
        print("  NOTE: {} of {} items were worked in the last {} commits. The queue is "
              "nearly exhausted —\n        after this one, open a genuinely new "
              "direction rather than re-circling.\n".format(
                  total - len(tasks), total, RECENT_COMMITS))
    t = tasks[0]
    print("NEXT  [{}]  score={:.2f}".format(t["kind"], t["score"]))
    print("  {}".format(t["title"]))
    print("  why : {}".format(t["evidence"]))
    print("  do  : {}".format(t["action"]))
    if len(tasks) > 1:
        print("\n  (queue depth {}; runner-up: {})".format(
            len(tasks), tasks[1]["title"][:70]))


def command_list(args) -> None:
    if getattr(args, "blocked", False):
        stuck = blocked_on_data()
        if not stuck:
            print("  nothing is blocked on data")
        for t in stuck:
            print("  [{}] {}".format(t["kind"], t["title"][:70]))
            print("      {}".format(t["blocked_reason"]))
        if getattr(args, "recheck", False):
            print("\n  re-checking the hosts these wait on:")
            for host, ok, detail in recheck_blocks():
                print("    {:<40} {:<12} {}".format(
                    host, "REACHABLE" if ok else "blocked", detail))
            print("  (any REACHABLE host means its items can be un-blocked — remove "
                  "them from BLOCKED_ON_DATA)")
        return
    if getattr(args, "deferred", False):
        held = deferred()
        if not held:
            print("  nothing is owner-deferred")
            return
        for t in held:
            print("  [{}] {}".format(t["kind"], t["title"]))
            print("      {}".format(t["deferred_reason"]))
        return
    tasks = collect(skip_recent=not args.no_skip)
    if not tasks:
        print("  backlog empty — see `next` for what to do instead")
        return
    print("  {:<5} {:<12} {:<58} {}".format("score", "kind", "item", "why"))
    for t in tasks[: args.n]:
        print("  {:<5.2f} {:<12} {:<58} {}".format(
            t["score"], t["kind"], t["title"][:58], t["evidence"][:44]))


def command_json(args) -> None:
    print(json.dumps(collect(skip_recent=not args.no_skip), indent=2))


def main(argv: Optional[Iterable[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-skip", action="store_true",
                    help="do not filter items addressed in recent commits")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("next", help="exactly one task, for an autonomous loop")
    p.set_defaults(func=command_next)
    p = sub.add_parser("list", help="the ranked queue")
    p.add_argument("-n", type=int, default=15)
    p.add_argument("--deferred", action="store_true",
                   help="show owner-deferred items and why")
    p.add_argument("--blocked", action="store_true",
                   help="show items blocked on unreachable data and why")
    p.add_argument("--recheck", action="store_true",
                   help="with --blocked: probe the hosts, in case the block lifted")
    p.set_defaults(func=command_list)
    p = sub.add_parser("json", help="machine-readable")
    p.set_defaults(func=command_json)
    args = ap.parse_args(list(argv) if argv is not None else None)
    args.func(args)


if __name__ == "__main__":
    main()
