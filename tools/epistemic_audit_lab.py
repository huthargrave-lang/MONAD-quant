#!/usr/bin/env python3
"""EPI-00 — epistemic audit of the research idea web itself.

Every other lab in this repo asks "is this market claim true?". This one turns the
same machinery on the project's own belief ledger and asks:

1. **How fast do this project's beliefs actually die?** `RESEARCH_WEB.md` records
   supersessions, so the naive answer is a simple proportion of tombstoned nodes.
   That number is uninterpretable, for three reasons this lab measures:
   - **Backfill.** A node recorded *in the same commit* that tombstones it, with no
     stamp separating birth from death, was never an observed live belief.
   - **Left-truncation.** A node already tombstoned in the FIRST observable commit
     had both its birth and its refutation happen before the window. Whether it was
     ever live is *unobservable* — it must not be asserted to be bookkeeping. These
     are excluded from numerator and denominator and reported as a sensitivity band.
   - **Right-censoring.** Most nodes are days or hours old and have had almost no
     exposure to refutation. A raw proportion ignores exposure entirely; the honest
     quantity is a hazard per node-day with an interval reflecting how few events
     there are.

2. **Which beliefs hold up the most other beliefs, and is their evidence linked?**
   The schema names four *reliance* edges (`relies_on`, `supports`, `refines`,
   `builds_on`) meaning "node → prior node". Their transitive closure gives each
   node a blast radius: how much of the web moves if this node is wrong. Crossing
   blast radius with evidence *linkage* and attention staleness yields a ranked
   structural-risk list — where re-verification effort actually pays. Note this
   measures whether evidence is reachable **from a node's own body**, never whether
   the underlying work was done.

3. **Could reversal be predicted at all?** With a handful of events, no. This lab
   states the minimum detectable effect rather than fitting a model to noise, in
   the same spirit as the CA-ANNOUNCE power analysis.

Method notes (limitations are first-class, not footnotes):

- Birth/death dates come from git archaeology over the commits touching
  `RESEARCH_WEB.md`: a node's birth is the first commit whose file version contains
  it. This is a **lower bound on belief age** — a belief may have existed in prose,
  in `CLAUDE.md`, or in someone's head long before it was captured — and nodes
  present in the file's very first commit are **left-truncated** (their true birth
  is unobservable).
- Supersession is *detected by effort*, not by nature. The hazard measures the rate
  at which the project **notices and records** that it was wrong, which is a lower
  bound on the rate at which it **was** wrong.

Stdlib only; reads git and `RESEARCH_WEB.md`; writes nothing inside the repo.

Commands::

    python3 tools/epistemic_audit_lab.py revision   # backfill vs in-vivo + censoring + hazard
    python3 tools/epistemic_audit_lab.py graph      # reliance structure, cycles, load-bearing
    python3 tools/epistemic_audit_lab.py risk       # ranked structural risk (the actionable output)
    python3 tools/epistemic_audit_lab.py power      # is reversal predictable at this event count?
    python3 tools/epistemic_audit_lab.py report     # everything, JSON to /tmp
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple


REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "RESEARCH_WEB.md"
DEFAULT_OUTPUT = Path("/tmp/monad-epistemic-audit.json")

# The schema's four reliance edges: "node -> prior node", i.e. the citing node
# depends on the cited one. These (and only these) define the dependency graph.
RELIANCE_EDGES = frozenset({"relies_on", "supports", "refines", "builds_on"})

NODE_RE = re.compile(r"^### ([EFHD]\d+) — (.*)$", re.M)
STATUS_RE = re.compile(r"<!-- status: ([a-z]+);([^>]*)-->")
STATUS_AT_RE = re.compile(r"at:\s*(\d{4}-\d{2}-\d{2})")
LINK_RE = re.compile(r"\[\[([EFHD]\d+)(?:\|([a-z_]+))?\]\]")
EVIDENCED_RE = re.compile(r"\[\[E\d+\|evidenced_by\]\]")
ANY_EXPERIMENT_RE = re.compile(r"\[\[E\d+")
# note.py stamps `_— captured <branch>@<sha>, YYYY-MM-DD_` on every node it writes.
# That is the author's own clock and is finer-grained than the commit that
# happens to carry the node, so it is preferred over git where present.
FOOTER_DATE_RE = re.compile(r"^_— captured [^,]*,\s*(\d{4}-\d{2}-\d{2})_", re.M)

# Untyped `[[ID]]` links are CUE-CLASSIFIED from the prose immediately before them
# (SCHEMA.md §5) and only fall back to `relates`.
#
# This DELEGATES to tools/ctx.py's `_classify_edge` rather than reimplementing it.
# A hand-written copy was tried first and was materially wrong: ctx's version uses
# stem cues ("corroborat", "support"), sentence-boundary windowing, word-boundary
# matching, a negation guard ("not supported" is not an edge), and a rule letting a
# reliance verb beat a closer lineage cue. The copy mis-classified real edges (e.g.
# H2's "Confirmed by ... corroboration [[F9]]" -> `relates` instead of `supports`),
# which silently corrupts the reliance graph. One classifier, one source of truth.
_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import ctx as _ctx  # noqa: E402  (canonical web reader; stdlib-only)


def classify_untyped_link(preceding_text: str) -> str:
    """Cue-classify an untyped `[[ID]]` exactly as the project's own reader does."""
    return _ctx._classify_edge(preceding_text)


# --------------------------------------------------------------------------- #
# Parsing (pure — operates on text, so tests can use synthetic webs)           #
# --------------------------------------------------------------------------- #
def parse_web(text: str) -> Dict[str, Dict[str, object]]:
    """Split a RESEARCH_WEB.md body into {node_id: {title, body, ...}}.

    Duplicate node IDs are a SCHEMA violation; rather than let the last one win
    silently, every occurrence is counted and surfaced via `duplicate_count`.
    """
    nodes: Dict[str, Dict[str, object]] = {}
    matches = list(NODE_RE.finditer(text))
    for i, m in enumerate(matches):
        node_id, title = m.group(1), m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        status = "current"
        superseded_by = None
        reason = None
        status_at = None
        sm = STATUS_RE.search(body)
        if sm:
            status = sm.group(1)
            attrs = sm.group(2)
            by = re.search(r"by:\s*([EFHD]\d+)", attrs)
            rs = re.search(r"reason:\s*([a-z-]+)", attrs)
            at = STATUS_AT_RE.search(attrs)
            superseded_by = by.group(1) if by else None
            reason = rs.group(1) if rs else None
            status_at = at.group(1) if at else None
        footer = FOOTER_DATE_RE.search(body)
        # Resolve every link, cue-classifying the untyped ones the way ctx.py does,
        # then collapse to ONE edge per target. An EXPLICITLY typed occurrence wins
        # over a cue-inferred one: SCHEMA calls the trailing `Links:` line the
        # authoritative echo of the typed edges, so "Builds on [[E26]]/[[F35]]" in
        # prose must not override an explicit `[[F35|relates]]` there.
        resolved: Dict[str, Tuple[str, bool]] = {}
        order: List[str] = []
        out_of_vocab: List[Tuple[str, str]] = []
        for lm in LINK_RE.finditer(body):
            target, explicit_type = lm.group(1), lm.group(2)
            # A type outside the enforced vocabulary is NOT a typed edge: ctx.py
            # falls back to cue classification for it, so an out-of-vocab label
            # like `extends` silently becomes `relates` for every other reader.
            if explicit_type and explicit_type not in _ctx.EDGE_TYPES:
                out_of_vocab.append((target, explicit_type))
                explicit_type = None
            edge_type = explicit_type or classify_untyped_link(body[: lm.start()])
            is_explicit = bool(explicit_type)
            previous = resolved.get(target)
            if previous is None:
                order.append(target)
                resolved[target] = (edge_type, is_explicit)
            elif is_explicit or not previous[1]:
                # explicit always wins; otherwise the later inference wins
                resolved[target] = (edge_type, previous[1] or is_explicit)
        edges: List[Tuple[str, str]] = [(t, resolved[t][0]) for t in order]
        explicit_edges: List[Tuple[str, str]] = [
            (t, resolved[t][0]) for t in order if resolved[t][1]
        ]
        resolved_evidence = any(
            t.startswith("E") and e == "evidenced_by" for t, e in edges
        )
        previous = nodes.get(node_id)
        nodes[node_id] = {
            "id": node_id,
            "kind": node_id[0],
            "title": title,
            "body": body,
            "status": status,
            "superseded_by": superseded_by,
            "supersession_reason": reason,
            "status_at": status_at,
            "footer_date": footer.group(1) if footer else None,
            "edges": edges,
            "explicit_edges": explicit_edges,
            # strict: an explicitly typed [[E#|evidenced_by]] link
            "has_evidenced_by": bool(EVIDENCED_RE.search(body)),
            # as the project's own reader sees it (typed OR cue-resolved)
            "has_resolved_evidence": resolved_evidence,
            "cites_experiment": bool(ANY_EXPERIMENT_RE.search(body)),
            "out_of_vocab_edges": out_of_vocab,
            "duplicate_count": (int(previous["duplicate_count"]) + 1) if previous else 1,
        }
    return nodes


def duplicate_node_ids(nodes: Mapping[str, Mapping[str, object]]) -> List[str]:
    return sorted(n for n, v in nodes.items() if int(v.get("duplicate_count", 1)) > 1)


def parse_edges(
    nodes: Mapping[str, Mapping[str, object]]
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Return (depends_on, depended_on_by, all_citations).

    `depends_on[a]` = nodes `a` relies on via a reliance edge.
    `all_citations[a]` = every node `a` mentions, regardless of edge type.
    """
    depends: Dict[str, Set[str]] = collections.defaultdict(set)
    rdepends: Dict[str, Set[str]] = collections.defaultdict(set)
    cites: Dict[str, Set[str]] = collections.defaultdict(set)
    for a, node in nodes.items():
        for target, edge_type in node.get("edges", []):  # cue-resolved
            if target == a or target not in nodes:
                continue
            cites[a].add(target)
            if edge_type in RELIANCE_EDGES:
                depends[a].add(target)
                rdepends[target].add(a)
    return depends, rdepends, cites


# --------------------------------------------------------------------------- #
# Git archaeology                                                              #
# --------------------------------------------------------------------------- #
def _git(args: Sequence[str], repo: Path) -> str:
    return subprocess.run(
        ["git"] + list(args), cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout


def repo_provenance(repo: Path = REPO) -> Dict[str, object]:
    """Is this checkout capable of supporting a historical claim at all?

    A SHALLOW clone truncates history at a graft point, and git exits 0 while
    doing so — every "first commit" and every exposure figure derived from it is
    then an artifact of the checkout depth, not a property of the project. This
    must be reported next to any historical number, never silently.
    """
    try:
        shallow = _git(["rev-parse", "--is-shallow-repository"], repo).strip() == "true"
    except subprocess.CalledProcessError:  # pragma: no cover
        shallow = False
    graft = None
    shallow_file = repo / ".git" / "shallow"
    if shallow and shallow_file.is_file():
        graft = shallow_file.read_text(encoding="utf-8").split()[:1]
        graft = graft[0] if graft else None
    return {
        "shallow_clone": shallow,
        "graft_sha": graft,
        "history_is_complete": not shallow,
        "warning": (
            "SHALLOW CLONE: history is truncated at the graft point, so the "
            "observation window, exposure totals, and every 'first commit' claim "
            "below are artifacts of this checkout, not of the project. Re-run in a "
            "full clone (git fetch --unshallow) before citing any historical rate."
        ) if shallow else None,
    }


def web_commits(repo: Path = REPO, path: str = "RESEARCH_WEB.md") -> List[Tuple[str, str]]:
    """(sha, iso-date) for every commit touching the web, oldest first.

    `--topo-order` is required: plain `--reverse` is commit-DATE order, which
    interleaves concurrent branches and can make a node appear to vanish and
    resurrect across two sibling commits.
    """
    out = _git(
        ["log", "--reverse", "--topo-order", "--format=%H\t%ad", "--date=short", "--", path],
        repo,
    )
    commits = []
    for line in out.strip().split("\n"):
        if line.strip():
            sha, date = line.split("\t")
            commits.append((sha, date))
    return commits


def node_lifecycles(
    repo: Path = REPO, path: str = "RESEARCH_WEB.md"
) -> Dict[str, Dict[str, object]]:
    """Replay the web across its commit history to date every node's birth/death.

    Returns {node_id: {birth_index, birth_date, death_index, death_date, ...}}.
    A node's *death* is the first commit whose version marks it superseded.
    """
    commits = web_commits(repo, path)
    if not commits:
        return {}
    life: Dict[str, Dict[str, object]] = {}
    for index, (sha, date) in enumerate(commits):
        text = _git(["show", "{}:{}".format(sha, path)], repo)
        version = parse_web(text)
        for node_id, node in version.items():
            record = life.setdefault(
                node_id,
                {
                    "id": node_id,
                    "kind": node_id[0],
                    "birth_index": index,
                    "birth_date": date,
                    "birth_sha": sha,
                    "death_index": None,
                    "death_date": None,
                    "superseded_by": None,
                    "supersession_reason": None,
                    "left_truncated": index == 0,
                },
            )
            if node["status"] == "superseded" and record["death_index"] is None:
                record["death_index"] = index
                record["death_date"] = date
                record["superseded_by"] = node["superseded_by"]
                record["supersession_reason"] = node["supersession_reason"]
    last_index = len(commits) - 1
    last_date = commits[-1][1]
    # The web's own note.py stamps are a finer clock than "the commit that
    # happened to carry the node": a node captured on the 23rd and superseded on
    # the 24th is a real revision even if both landed in one commit. Prefer the
    # stamps where present, and record where the two clocks disagree.
    head_nodes = parse_web(_git(["show", "{}:{}".format(commits[-1][0], path)], repo))
    for node_id, record in life.items():
        node = head_nodes.get(node_id, {})
        footer = node.get("footer_date")
        status_at = node.get("status_at")
        record["git_birth_date"] = record["birth_date"]
        record["stamped_birth_date"] = footer
        record["clock_disagrees"] = bool(footer and footer != record["birth_date"])
        if footer:
            record["birth_date"] = footer
        record["git_death_date"] = record["death_date"]
        record["stamped_death_date"] = status_at if record["death_index"] is not None else None
        if record["death_index"] is not None and status_at:
            record["death_date"] = status_at

    for record in life.values():
        record["observed_commits"] = last_index - int(record["birth_index"])
        record["last_observed_date"] = last_date
        if record["death_index"] is None:
            record["revision_class"] = "alive"
            continue
        same_commit = record["death_index"] == record["birth_index"]
        stamped_gap = (
            record["stamped_birth_date"] and record["stamped_death_date"]
            and record["stamped_death_date"] > record["stamped_birth_date"]
        )
        if not same_commit or stamped_gap:
            # Observed to be born, live, and then be revised.
            record["revision_class"] = "in_vivo"
        elif record["left_truncated"]:
            # Present in the FIRST observed commit already carrying a tombstone.
            # Its true birth AND its true death are both before the window, so
            # whether it was a live belief is UNOBSERVABLE here — it must not be
            # asserted to be mere bookkeeping.
            record["revision_class"] = "truncated_unknown"
        else:
            # Born and tombstoned inside one commit, with no stamp separating
            # them: recorded already dead.
            record["revision_class"] = "backfill"
    return life


def _days(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


# --------------------------------------------------------------------------- #
# Belief-revision analysis (the headline)                                      #
# --------------------------------------------------------------------------- #
def poisson_ci(events: int, exposure: float) -> Dict[str, Optional[float]]:
    """Exact-ish Poisson rate CI via the chi-square relation, computed from the
    Gamma quantile by bisection (stdlib only). Returns rate per unit exposure."""
    if exposure <= 0:
        return {"rate": None, "ci95_low": None, "ci95_high": None}

    def gamma_cdf(x: float, k: int) -> float:
        # Regularized lower incomplete gamma P(k, x) for integer k, via the
        # Poisson sum identity: P(k, x) = 1 - sum_{i<k} e^-x x^i / i!
        if x <= 0:
            return 0.0
        total = 0.0
        term = math.exp(-x)
        for i in range(k):
            if i > 0:
                term *= x / i
            total += term
        return max(0.0, min(1.0, 1.0 - total))

    def invert(target: float, k: int) -> float:
        if k <= 0:
            return 0.0
        lo, hi = 0.0, max(10.0, 4.0 * k + 20.0)
        for _ in range(200):
            mid = (lo + hi) / 2
            if gamma_cdf(mid, k) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    # Exact Poisson interval via the Gamma/chi-square relation:
    #   lower = Ginv(alpha/2, shape=k), upper = Ginv(1-alpha/2, shape=k+1)
    low = invert(0.025, events) if events > 0 else 0.0
    high = invert(0.975, events + 1)
    rate = events / exposure
    lo, hi = low / exposure, high / exposure
    if not (lo <= rate <= hi):
        # The Poisson sum in gamma_cdf underflows for very large k (exp(-x) -> 0
        # above x ~ 745), which would silently return an interval that does not
        # bracket the point estimate. Fail loudly instead of reporting nonsense.
        raise ValueError(
            "poisson_ci lost precision at k={} (interval [{:.6g}, {:.6g}] does not "
            "bracket rate {:.6g}); use a normal approximation above k~500".format(
                events, lo, hi, rate)
        )
    return {"rate": rate, "ci95_low": lo, "ci95_high": hi}


def revision_analysis(life: Mapping[str, Mapping[str, object]]) -> Dict[str, object]:
    """Separate backfill from in-vivo revision, then compute an exposure-weighted
    hazard using only genuinely observable revision events."""
    records = list(life.values())
    if not records:
        return {}
    last_date = str(records[0]["last_observed_date"])
    by_class = collections.Counter(str(r["revision_class"]) for r in records)

    in_vivo = [r for r in records if r["revision_class"] == "in_vivo"]
    backfill = [r for r in records if r["revision_class"] == "backfill"]
    truncated = [r for r in records if r["revision_class"] == "truncated_unknown"]

    # Exposure in node-days: birth -> death (if in-vivo) else birth -> last commit.
    # Backfilled nodes contribute no exposure and no event (recorded already dead).
    # truncated_unknown nodes are excluded from BOTH numerator and denominator:
    # they were refuted, but before the observation window, so counting them as
    # events without their (unobservable) exposure would bias the hazard up, and
    # counting them as non-events would bias it down.
    excluded = {"backfill", "truncated_unknown"}
    exposure_days = 0.0
    for r in records:
        if r["revision_class"] in excluded:
            continue
        end = str(r["death_date"]) if r["death_date"] else last_date
        exposure_days += max(0, _days(str(r["birth_date"]), end))
    # Exposure in "commit ticks" — a revision opportunity is a commit, and dates
    # understate activity when many commits land the same day.
    exposure_commits = 0.0
    for r in records:
        if r["revision_class"] in excluded:
            continue
        end = int(r["death_index"]) if r["death_index"] is not None else int(r["observed_commits"]) + int(r["birth_index"])
        exposure_commits += max(0, end - int(r["birth_index"]))

    events = len(in_vivo)
    day_rate = poisson_ci(events, exposure_days)
    commit_rate = poisson_ci(events, exposure_commits)

    # Age distribution: how much of the corpus has barely been exposed at all?
    ages = [_days(str(r["birth_date"]), last_date) for r in records]
    ages.sort()
    n = len(ages)
    zero_age = sum(1 for a in ages if a == 0)

    naive_rate = (by_class["backfill"] + by_class["truncated_unknown"] + events) / n

    # Carry the rate interval through to the horizon probabilities: the width is
    # the point of the exercise, so quoting only the point estimate would hide it.
    # NOTE `is not None`, not truthiness — at zero events the point estimate is a
    # legitimate 0.0 and the upper bound is the ONLY inferential content there is.
    horizons = {}
    if day_rate["rate"] is not None:
        for h in (30, 90, 180, 365):
            horizons["p_revised_by_{}d".format(h)] = {
                "point": 1.0 - math.exp(-float(day_rate["rate"]) * h),
                "ci95_low": 1.0 - math.exp(-float(day_rate["ci95_low"] or 0.0) * h),
                "ci95_high": 1.0 - math.exp(-float(day_rate["ci95_high"] or 0.0) * h),
            }

    return {
        "n_nodes": n,
        "revision_classes": dict(by_class),
        "in_vivo_events": events,
        "in_vivo_detail": [
            {
                "id": r["id"],
                "born": r["birth_date"],
                "died": r["death_date"],
                "days_lived": _days(str(r["birth_date"]), str(r["death_date"])),
                "commits_lived": int(r["death_index"]) - int(r["birth_index"]),
                "superseded_by": r["superseded_by"],
                "reason": r["supersession_reason"],
            }
            for r in sorted(in_vivo, key=lambda x: str(x["birth_date"]))
        ],
        "backfilled_ids": sorted(str(r["id"]) for r in backfill),
        "truncated_unknown_ids": sorted(str(r["id"]) for r in truncated),
        "clock_disagreements": sum(1 for r in records if r.get("clock_disagrees")),
        # Sensitivity: the headline hazard depends on how the truncated_unknown
        # nodes are treated. Quote the bracket, not a single point.
        "hazard_sensitivity": {
            "events_excluding_truncated": events,
            "events_including_truncated_as_revisions": events + len(truncated),
            "p_365d_low_case": (
                1.0 - math.exp(-float(poisson_ci(events, exposure_days)["rate"] or 0.0) * 365)
                if exposure_days else None
            ),
            "p_365d_high_case": (
                1.0 - math.exp(
                    -float(poisson_ci(events + len(truncated), exposure_days)["rate"] or 0.0) * 365)
                if exposure_days else None
            ),
            "note": (
                "truncated_unknown nodes were superseded, but both their birth and "
                "death precede the observation window, so they can be argued either "
                "way. The honest headline is the bracket."
            ),
        },
        "naive_supersession_rate": naive_rate,
        "exposure_node_days": exposure_days,
        "exposure_node_commits": exposure_commits,
        "hazard_per_node_day": day_rate,
        "hazard_per_node_commit": commit_rate,
        "implied_revision_probability": horizons,
        "age_days_median": ages[n // 2],
        "nodes_with_zero_days_exposure": zero_age,
        "zero_exposure_fraction": zero_age / n,
        "left_truncated_nodes": sum(1 for r in records if r["left_truncated"]),
        "interpretation": (
            "The naive supersession proportion mixes three different things and "
            "ignores exposure time. (a) backfill: recorded in the same commit that "
            "tombstones it, with no stamp separating birth from death — never an "
            "observed live belief. (b) truncated_unknown: already tombstoned in the "
            "FIRST observed commit, so both its birth and its refutation happened "
            "before the window — it was very likely a genuine revision, but this "
            "checkout cannot see it, so it is excluded from numerator AND "
            "denominator and reported as a sensitivity bracket. (c) in_vivo: born, "
            "lived, then revised — the only directly observed evidence. Every rate "
            "here is a LOWER bound on being wrong, because supersession is detected "
            "by effort, not by nature."
        ),
    }


# --------------------------------------------------------------------------- #
# Graph structure                                                              #
# --------------------------------------------------------------------------- #
def _transitive_dependents(rdepends: Mapping[str, Set[str]], node: str) -> Set[str]:
    seen: Set[str] = set()
    stack = [node]
    while stack:
        current = stack.pop()
        for dependent in rdepends.get(current, ()):  # who relies on `current`
            if dependent not in seen:
                seen.add(dependent)
                stack.append(dependent)
    return seen


def find_cycles(depends: Mapping[str, Set[str]], nodes: Sequence[str]) -> List[List[str]]:
    """DFS cycle detection over the reliance graph (should be acyclic: reliance
    edges point to *prior* nodes, so a cycle is a schema violation)."""
    color: Dict[str, int] = {}
    cycles: List[List[str]] = []

    def visit(node: str, stack: List[str]) -> None:
        color[node] = 1
        stack.append(node)
        for target in sorted(depends.get(node, ())):
            state = color.get(target, 0)
            if state == 1 and target in stack:
                cycles.append(stack[stack.index(target):] + [target])
            elif state == 0:
                visit(target, stack)
        stack.pop()
        color[node] = 2

    for node in nodes:
        if color.get(node, 0) == 0:
            visit(node, [])
    return cycles


def graph_analysis(
    nodes: Mapping[str, Mapping[str, object]]
) -> Dict[str, object]:
    depends, rdepends, cites = parse_edges(nodes)
    ids = sorted(nodes)

    # Untyped citation closure — included to show WHY reliance typing matters.
    cited_by: Dict[str, Set[str]] = collections.defaultdict(set)
    for a, targets in cites.items():
        for b in targets:
            cited_by[b].add(a)
    largest_citation_closure = max(
        (len(_transitive_dependents(cited_by, n)) for n in ids), default=0
    )

    blast = {n: len(_transitive_dependents(rdepends, n)) for n in ids}
    cycles = find_cycles(depends, ids)

    reliance_edge_count = sum(len(v) for v in depends.values())
    citation_edge_count = sum(len(v) for v in cites.values())

    ranked = sorted(ids, key=lambda n: (-blast[n], n))
    return {
        "n_nodes": len(ids),
        "citation_edges": citation_edge_count,
        "reliance_edges": reliance_edge_count,
        "largest_untyped_citation_closure": largest_citation_closure,
        "reliance_cycles": [list(c) for c in cycles],
        "load_bearing_top": [
            {
                "id": n,
                "blast_radius": blast[n],
                "direct_dependents": len(rdepends.get(n, ())),
                "title": str(nodes[n]["title"])[:88],
            }
            for n in ranked[:15]
        ],
        "blast_radius": blast,
        "direct_dependents": {n: len(rdepends.get(n, ())) for n in ids},
        "interpretation": (
            "The untyped citation graph collapses into one near-total closure, so "
            "'what depends on what' is only meaningful over the schema's typed "
            "reliance edges. Cycles in the reliance graph are schema violations: "
            "reliance edges are defined as pointing to PRIOR nodes."
        ),
    }


# --------------------------------------------------------------------------- #
# Structural-risk ranking (the actionable output)                              #
# --------------------------------------------------------------------------- #
def risk_analysis(
    nodes: Mapping[str, Mapping[str, object]],
    life: Mapping[str, Mapping[str, object]],
    graph: Mapping[str, object],
    top: int = 15,
) -> Dict[str, object]:
    """Rank nodes by (load-bearing) x (unsubstantiated) x (unattended).

    Attention staleness = commits since any *newer* node last cited this one. A
    node nothing new has cited is one nothing has re-examined."""
    depends, rdepends, cites = parse_edges(nodes)
    blast: Mapping[str, int] = graph["blast_radius"]  # type: ignore[assignment]
    last_index = max(int(r["birth_index"]) for r in life.values()) if life else 0

    last_attention: Dict[str, int] = {}
    for citing, targets in cites.items():
        citing_birth = int(life[citing]["birth_index"]) if citing in life else 0
        for target in targets:
            if target not in life:
                continue
            # only a citation from a node born LATER counts as re-examination
            if citing_birth > int(life[target]["birth_index"]):
                prior = last_attention.get(target, -1)
                last_attention[target] = max(prior, citing_birth)

    # Incoming `supports` from a CURRENT node that itself has evidence: an
    # independent corroboration of this claim, even if this claim links no
    # Experiment of its own.
    corroborators: Dict[str, List[str]] = collections.defaultdict(list)
    for citer, node in nodes.items():
        if node["status"] == "superseded":
            continue
        if not (node["has_evidenced_by"] or node["has_resolved_evidence"]):
            continue
        for target, edge_type in node.get("edges", []):
            if edge_type == "supports" and target in nodes and target != citer:
                corroborators[target].append(citer)

    rows = []
    for node_id, node in nodes.items():
        if node["status"] == "superseded":
            continue
        record = life.get(node_id)
        if record is None:
            continue
        radius = int(blast.get(node_id, 0))
        is_finding = node["kind"] == "F"
        # Three honest levels of evidence *traversability* — the question is not
        # "does evidence exist somewhere?" but "can a reader walking the web reach
        # it from this claim?".
        if not is_finding:
            # The `evidenced_by` obligation is Finding-specific (SCHEMA §3), so
            # H/E/D nodes are not penalised; their rank reflects structure only.
            evidence_link = "n/a"
            evidence_multiplier = 1.0
        elif node["has_evidenced_by"] or node["has_resolved_evidence"]:
            # Typed [[E#|evidenced_by]], or an untyped link the cue classifier
            # resolves to evidence (e.g. "Source: [[E6]]") — as ctx.py reads it.
            evidence_link = "linked"
            evidence_multiplier = 1.0
        elif node["cites_experiment"]:
            # Names an Experiment, but no cue resolves the link to evidence.
            evidence_link = "cited_not_evidence_typed"
            evidence_multiplier = 1.5
        elif corroborators.get(node_id):
            # No Experiment in its own body, but a live node that IS evidenced
            # `supports` it — independently corroborated, a materially weaker
            # defect than an orphan claim.
            evidence_link = "corroborated_only"
            evidence_multiplier = 2.0
        else:
            # No Experiment cited in this node's body and no evidenced supporter.
            evidence_link = "no_direct_link"
            evidence_multiplier = 3.0
        attended_at = last_attention.get(node_id, int(record["birth_index"]))
        staleness = last_index - attended_at
        # Risk: structural weight, amplified when evidence is hard to reach, scaled
        # by how long since anything re-examined it. Deliberately inspectable.
        score = radius * evidence_multiplier * (1.0 + staleness / max(1, last_index))
        rows.append(
            {
                "id": node_id,
                "kind": node["kind"],
                "title": str(node["title"])[:88],
                "blast_radius": radius,
                "direct_dependents": len(rdepends.get(node_id, ())),
                "evidence_link": evidence_link,
                "corroborated_by": corroborators.get(node_id, []),
                "commits_since_reexamined": staleness,
                "risk_score": round(score, 2),
            }
        )
    rows.sort(key=lambda r: (-float(r["risk_score"]), str(r["id"])))

    findings = [n for n, v in nodes.items() if v["kind"] == "F" and v["status"] != "superseded"]
    by_level = collections.Counter(
        str(r["evidence_link"]) for r in rows if r["kind"] == "F"
    )
    orphans = [
        str(r["id"]) for r in rows
        if r["kind"] == "F" and r["evidence_link"] == "no_direct_link"
    ]
    return {
        "ranked": rows[:top],
        "current_findings": len(findings),
        "evidence_levels": dict(by_level),
        "no_direct_link_ids": sorted(orphans),
        "scoring": (
            "risk = blast_radius x evidence_multiplier x (1 + staleness/history). "
            "evidence_multiplier: 1.0 `linked` (a typed [[E#|evidenced_by]] OR an "
            "untyped link the SCHEMA cue classifier resolves to evidence, e.g. "
            "'Source: [[E6]]'); 1.5 `cited_not_evidence_typed` (names an Experiment "
            "but no cue resolves it); 2.0 `corroborated_only` (no Experiment in its "
            "own body, but an evidenced current node `supports` it); 3.0 "
            "`no_direct_link`; 1.0 `n/a` for non-Findings, whose `evidenced_by` "
            "obligation is Finding-specific (SCHEMA §3) so they rank on structure "
            "alone. This measures whether evidence is DIRECTLY LINKED FROM THIS "
            "NODE'S BODY — not whether evidence exists somewhere in the graph, and "
            "not transitive reachability. It is a TRIAGE HEURISTIC for ordering "
            "re-verification work, not a probability and not a claim of error."
        ),
    }


def integrity_checks(nodes: Mapping[str, Mapping[str, object]]) -> Dict[str, object]:
    """Schema-integrity violations this lab is uniquely placed to catch."""
    tombstoned = {n for n, v in nodes.items() if v["status"] == "superseded"}
    supersede_targets: Set[str] = set()
    for node in nodes.values():
        # Only an EXPLICITLY typed [[X|supersedes]] is a declaration. A cue-inferred
        # one (ctx maps prose like "reversal" to `supersedes`) is an inference and
        # must not be treated as the author asserting a supersession.
        for target, edge_type in node.get("explicit_edges", []):
            if edge_type == "supersedes" and target in nodes:
                supersede_targets.add(target)
    # SCHEMA §5: `supersedes` is "auto-paired with the tombstone", so a node that
    # something claims to supersede but which carries no tombstone is counted as
    # live everywhere else in the tooling.
    missing_tombstone = sorted(supersede_targets - tombstoned)
    orphan_tombstone = sorted(
        n for n in tombstoned
        if nodes[n].get("superseded_by") and nodes[n]["superseded_by"] not in nodes
    )
    out_of_vocab = sorted(
        "{} -[{}]-> {}".format(n, etype, target)
        for n, v in nodes.items()
        for target, etype in v.get("out_of_vocab_edges", [])
    )
    return {
        "supersedes_edge_without_tombstone": missing_tombstone,
        "tombstone_pointing_at_missing_node": orphan_tombstone,
        "duplicate_node_ids": duplicate_node_ids(nodes),
        "out_of_vocabulary_edge_types": out_of_vocab,
        "note": (
            "A `supersedes` edge whose target has no tombstone means the node is "
            "still counted as current by every other reader of the web. An "
            "out-of-vocabulary edge type is silently cue-classified (usually to "
            "`relates`) by ctx.py, so the author's intended relation is lost."
        ),
    }


# --------------------------------------------------------------------------- #
# Power: is reversal predictable at this event count?                          #
# --------------------------------------------------------------------------- #
def reversal_power(events: int, n_at_risk: int) -> Dict[str, object]:
    """Minimum detectable effect for 'do doomed beliefs look different at birth?'.

    Two-proportion framing: if a candidate birth-time signature splits the corpus
    in half, how large must the reversal-rate difference be before `events`
    observed revisions could establish it at 80% power / alpha 0.05?

    `n_at_risk` must be the EXPOSURE-BEARING node count, not the whole corpus:
    nodes with zero days of exposure carry no information about a revision rate,
    and including them understates the MDE (i.e. flatters detectability).
    """
    n_at_risk = max(1, int(n_at_risk))
    base_keys = {
        "events": events,
        "n_at_risk": n_at_risk,
        "alpha": 0.05,
        "target_power": 0.80,
    }
    if events <= 0:
        return dict(base_keys, base_reversal_rate=0.0,
                    min_detectable_rate_difference=None,
                    mde_as_multiple_of_base_rate=None,
                    max_feasible_rate_difference=0.0,
                    expected_events_per_arm=0.0,
                    verdict="no_events",
                    normal_approximation_valid=False,
                    interpretation=("No observed in-vivo revision: there is no rate "
                                    "to compare against and nothing to model."))
    p_bar = events / n_at_risk
    per_arm = max(1, n_at_risk // 2)
    z_sum = 1.96 + 0.84  # z_{1-a/2} + z_{1-b}
    mde = z_sum * math.sqrt(2.0 * p_bar * (1.0 - p_bar) / per_arm)
    # A two-arm split of a pooled rate p_bar cannot separate the arms by more than
    # 2*p_bar (the low arm would need a negative rate). If the MDE exceeds that,
    # NO achievable signature is detectable — the honest answer is not a number.
    max_feasible = 2.0 * p_bar
    expected_events_per_arm = per_arm * p_bar
    feasible = mde <= max_feasible
    return dict(
        base_keys,
        base_reversal_rate=p_bar,
        min_detectable_rate_difference=mde,
        mde_as_multiple_of_base_rate=mde / p_bar if p_bar else None,
        max_feasible_rate_difference=max_feasible,
        expected_events_per_arm=expected_events_per_arm,
        normal_approximation_valid=expected_events_per_arm >= 5,
        verdict="detectable" if feasible else "no_feasible_signature",
        interpretation=(
            "The minimum detectable rate difference EXCEEDS the largest difference "
            "any two-arm split of this corpus could produce ({:.4f} > {:.4f}), so no "
            "birth-time signature — however strong — could be established at this "
            "event count. Fitting a reversal classifier here would be fitting noise. "
            "Keep recording revisions with honest timestamps until events accumulate."
            if not feasible else
            "A birth-time signature is in principle detectable at this event count "
            "if it shifts the reversal rate by at least {:.4f} (max feasible {:.4f})."
        ).format(mde, max_feasible) + (
            "" if expected_events_per_arm >= 5 else
            " CAVEAT: expected events per arm is {:.2f} (<5), so the normal "
            "approximation underlying this MDE is itself unreliable.".format(
                expected_events_per_arm)
        ),
    )


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #
def full_report(repo: Path = REPO, path: str = "RESEARCH_WEB.md") -> Dict[str, object]:
    provenance = repo_provenance(repo)
    commits = web_commits(repo, path)
    # Analyse the COMMITTED web, so the graph/risk corpus and the lifecycle corpus
    # are the same set of nodes. Reading the working tree here would silently drop
    # uncommitted nodes from the ranking while still counting them in blast radius.
    head_text = _git(["show", "{}:{}".format(commits[-1][0], path)], repo) if commits else ""
    working_text = (repo / path).read_text(encoding="utf-8")
    nodes = parse_web(head_text)
    working_nodes = parse_web(working_text)
    uncommitted = sorted(set(working_nodes) - set(nodes))

    life = node_lifecycles(repo, path)
    revision = revision_analysis(life)
    graph = graph_analysis(nodes)
    risk = risk_analysis(nodes, life, graph)
    at_risk = int(revision.get("n_nodes", 0)) - int(revision.get("nodes_with_zero_days_exposure", 0))
    power = reversal_power(int(revision.get("in_vivo_events", 0)), at_risk)
    slim_graph = {k: v for k, v in graph.items() if k not in ("blast_radius", "direct_dependents")}
    return {
        "lab_version": "epistemic-audit-lab-v2",
        "web_path": path,
        "repo_provenance": provenance,
        "commits_observed": len(commits),
        "uncommitted_nodes": uncommitted,
        "revision": revision,
        "graph": slim_graph,
        "risk": risk,
        "integrity": integrity_checks(nodes),
        "power": power,
        "limitations": [
            ("THIS CHECKOUT IS A SHALLOW CLONE: the observation window below is an "
             "artifact of clone depth, not the project's history. Re-run in a full "
             "clone before citing any historical rate.")
            if provenance["shallow_clone"] else
            "History appears complete (not a shallow clone).",
            "Birth dates prefer note.py's own capture stamps and fall back to the "
            "commit that carries the node; either way they are a LOWER BOUND on "
            "belief age. Nodes present in the first observed commit are left-"
            "truncated, and if they are already tombstoned there, whether they were "
            "ever live is UNOBSERVABLE — hence the truncated_unknown class and the "
            "hazard sensitivity bracket.",
            "Supersession is detected by effort, not by nature — every rate here is "
            "a lower bound on how often the project was actually wrong.",
            "The observation window is short relative to the horizons quoted; the "
            "implied revision probabilities extrapolate a constant hazard and should "
            "be read as an order of magnitude, not a forecast.",
            "The risk score is an inspectable triage heuristic, not a probability, "
            "and `evidence_link` measures DIRECT linkage from a node's body — not "
            "whether the underlying work was done.",
        ],
    }


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def _write_json_atomic(path: Path, value: object) -> None:
    resolved = path.resolve()
    if str(resolved).startswith(str(REPO) + "/"):
        raise ValueError("refusing to write the disposable audit report inside the repo")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, default=str)
        handle.write("\n")
    tmp.replace(path)


def command_revision(args: argparse.Namespace) -> None:
    life = node_lifecycles()
    result = revision_analysis(life)
    print(json.dumps(result, indent=2, default=str))


def command_graph(args: argparse.Namespace) -> None:
    nodes = parse_web(WEB.read_text(encoding="utf-8"))
    result = graph_analysis(nodes)
    result.pop("blast_radius", None)
    result.pop("direct_dependents", None)
    print(json.dumps(result, indent=2, default=str))


def command_risk(args: argparse.Namespace) -> None:
    nodes = parse_web(WEB.read_text(encoding="utf-8"))
    life = node_lifecycles()
    graph = graph_analysis(nodes)
    result = risk_analysis(nodes, life, graph, top=args.top)
    print(json.dumps(result, indent=2, default=str))


def command_power(args: argparse.Namespace) -> None:
    revision = revision_analysis(node_lifecycles())
    # Only exposure-bearing nodes carry information about a revision rate.
    at_risk = int(revision["n_nodes"]) - int(revision["nodes_with_zero_days_exposure"])
    print(json.dumps(reversal_power(int(revision["in_vivo_events"]), at_risk),
                     indent=2, default=str))


def command_report(args: argparse.Namespace) -> None:
    report = full_report()
    _write_json_atomic(args.output, report)
    rev = report["revision"]
    print(json.dumps({
        "revision_classes": rev["revision_classes"],
        "in_vivo_events": rev["in_vivo_events"],
        "naive_supersession_rate": rev["naive_supersession_rate"],
        "exposure_node_days": rev["exposure_node_days"],
        "hazard_per_node_day": rev["hazard_per_node_day"],
        "zero_exposure_fraction": rev["zero_exposure_fraction"],
        "reliance_cycles": report["graph"]["reliance_cycles"],
        "top_risk": report["risk"]["ranked"][:5],
    }, indent=2, default=str))
    print("wrote {}".format(args.output))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("revision", help="backfill vs in-vivo revision, censoring, hazard")
    r.set_defaults(func=command_revision)

    g = sub.add_parser("graph", help="reliance-graph structure, cycles, load-bearing nodes")
    g.set_defaults(func=command_graph)

    k = sub.add_parser("risk", help="ranked structural risk (the actionable output)")
    k.add_argument("--top", type=int, default=15)
    k.set_defaults(func=command_risk)

    p = sub.add_parser("power", help="is reversal predictable at this event count?")
    p.set_defaults(func=command_power)

    a = sub.add_parser("report", help="everything, JSON to /tmp")
    a.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    a.set_defaults(func=command_report)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
