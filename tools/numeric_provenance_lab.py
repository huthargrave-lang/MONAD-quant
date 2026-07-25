#!/usr/bin/env python3
"""NUM-00 — numeric provenance audit of the research corpus.

`RESEARCH_WEB.md` is dense with specific figures — Sharpes, percentages, counts,
confidence intervals. Each is an implicit claim that some study produced it. This
lab asks, for every such figure: **can a reader reach the document that contains
it by following the web's own links?**

Three outcomes per figure:

- ``linked``   — the figure appears in a research doc reachable from the node
  (cited in its body, or in a node one hop away — the intended
  ``Finding -> evidenced_by -> Experiment -> doc`` path).
- ``unlinked`` — the figure appears in *some* research doc, but not in one the node
  can reach. The evidence exists; the graph does not connect the claim to it.
- ``absent``   — the figure appears in no research doc at all.

This extends F135 (evidence *linkage* per node) and F139 (F17's specific figures
being unlocated) from individual claims to a corpus-wide measurement, and it
separates "we never wrote it down" from "we wrote it down but nothing points there".

**Methodological warning, learned the hard way.** A first version reported figures
as absent-everywhere at more than double the true rate. Sampling one node (F50)
showed every one of its "absent" figures was in fact present — written with a
Unicode minus (U+2212), which the docs use 1164 times, while the node bodies use
ASCII hyphen. Normalising the minus signs and thousands separators materially
cuts absent-everywhere. Measured by monkeypatching `normalise_numerals` to the
identity and re-running `census`:

    2026-07-25, 328 nodes / 2388 figures:  8.40% -> 4.50%   (1.87x)
    2026-07-25, 351 nodes / 2834 figures: 11.00% -> 8.00%   (1.38x)

**The ratio is corpus-dependent, not a constant** — it tracks how much of the corpus
was written with U+2212 versus ASCII hyphen, so nodes added in bulk by one author
dilute it. Quote the measurement with its corpus size, never the bare multiple. Any
figure-matching over this corpus MUST normalise; `normalise_numerals` does it and
`tests/test_numeric_provenance_lab.py` pins the behaviour and forced this
re-measurement when the ratio drifted below its floor. Reported numbers are
still an upper bound on "missing": a figure can be legitimately node-local (a
count of things described only in the node) without indicating a provenance defect.

**Three limits found by adversarial re-verification (do not report the token
classes without them).** Measured on the corpus as of 2026-07-25:

1. *Most "figures" are not claims.* 43.8% of extracted figures are bare two-digit
   integers and 19.1% are four-digit years — **62.9% combined**. Trade counts,
   dates and enumerations are matched with the same weight as a Sharpe ratio.
2. *Presence is a weak test.* Perturbing a real figure by one tick (a value the
   corpus never claimed) still lands "present in some doc" **59.4% of the time**
   (4000 draws, seed 20260725). A `linked`/`unlinked` verdict on a single figure
   is close to a coin-flip; only the aggregate contrast carries signal.
3. *`unlinked` is mostly a citation gap, not a traversal gap.* **80.8%** of
   `unlinked` figures sit in nodes that reach *zero* research docs — the node
   cites no study at all, so there is no path to fail to follow. Calling the
   residual a "traversability gap" mislabels it; the honest statement is that
   those nodes are uncited.

Stdlib only; reads `RESEARCH_WEB.md` + `docs/research/*.md`; writes nothing in-repo.

Commands::

    python3 tools/numeric_provenance_lab.py census        # corpus-wide classification
    python3 tools/numeric_provenance_lab.py node F17      # one node, figure by figure
    python3 tools/numeric_provenance_lab.py worst [--top N]
    python3 tools/numeric_provenance_lab.py report --output /tmp/num.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple


REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "RESEARCH_WEB.md"
DOCS_DIR = REPO / "docs" / "research"
DEFAULT_OUTPUT = Path("/tmp/monad-numeric-provenance.json")

_TOOLS = str(Path(__file__).resolve().parent)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
import epistemic_audit_lab as _epi  # noqa: E402  (canonical web parser, ctx-agreed)

DOC_REF_RE = re.compile(r"docs/research/([A-Za-z0-9_\-]+\.md)")
# A numeral, optionally signed/decimal. Word boundaries stop us splitting
# identifiers (F17, E112) or version strings into digits.
# A numeral, optionally carrying a unit suffix. The suffix must be consumed: a
# bare `(?![\w])` lookahead silently DROPS every figure written as 8.96pp / 34bps /
# 59.5bn, which under-counts the corpus (caught by this lab's own test suite).
UNIT = r"(?:%|pp|bps|bp|bn|yr|mo|x)?"
NUMERAL_RE = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)" + UNIT + r"(?![\w.])")
# Bare 0-9 carry no evidential weight and match everywhere; require 2+ digits.
MIN_DIGITS = 2


def normalise_numerals(text: str) -> str:
    """Unify minus signs and strip thousands separators before matching.

    The corpus mixes U+2212 MINUS SIGN, EN/EM DASH and ASCII hyphen, and writes
    both `3,429` and `3429`. Without this, matching silently reports real figures
    as missing — the exact false positive that inflated this lab's first result.
    """
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"(?<=\d),(?=\d\d\d)", "", text)


def figures(text: str) -> Set[str]:
    """Normalised numeric tokens carrying evidential weight."""
    found = set()
    for match in NUMERAL_RE.finditer(normalise_numerals(text)):
        value = match.group(1)
        if len(value.replace("-", "").replace(".", "")) >= MIN_DIGITS:
            found.add(value)
    return found


def load_docs(docs_dir: Path = DOCS_DIR) -> Dict[str, Set[str]]:
    """{doc name: set of numeric TOKENS it contains}.

    Tokenised, never substring-matched. A naive `fig in text` test matches numerals
    embedded in URLs, SEC accession numbers and identifiers — F17's "41" matched
    inside `d411753d8k.htm` and its "2022" matched a year, which wrongly promoted
    genuinely-undocumented figures into the "present somewhere" class.
    """
    return {
        path.name: figures(path.read_text(encoding="utf-8", errors="ignore"))
        for path in sorted(docs_dir.glob("*.md"))
    }


def load_nodes(web: Path = WEB) -> Dict[str, Dict[str, object]]:
    return _epi.parse_web(web.read_text(encoding="utf-8"))


def reachable_docs(
    node_id: str, nodes: Mapping[str, Mapping[str, object]], hops: int = 1
) -> Set[str]:
    """Docs cited by the node, or by any node within `hops` typed edges.

    One hop is the schema's intended indirection: a Finding cites an Experiment
    (`evidenced_by`) and the Experiment names the study document.
    """
    found = set(DOC_REF_RE.findall(str(nodes[node_id]["body"])))
    seen = {node_id}
    frontier = [t for t, _ in nodes[node_id].get("edges", [])]
    for _ in range(hops):
        nxt: List[str] = []
        for target in frontier:
            if target in seen or target not in nodes:
                continue
            seen.add(target)
            found |= set(DOC_REF_RE.findall(str(nodes[target]["body"])))
            nxt += [t for t, _ in nodes[target].get("edges", [])]
        frontier = nxt
    return found


def classify_node(
    node_id: str,
    nodes: Mapping[str, Mapping[str, object]],
    docs: Mapping[str, Set[str]],
    hops: int = 1,
) -> Dict[str, object]:
    """Per-figure classification for one node."""
    body = str(nodes[node_id]["body"])
    figs = figures(body)
    reach = reachable_docs(node_id, nodes, hops)
    linked_tokens: Set[str] = set()
    for d in sorted(reach):
        if d in docs:
            linked_tokens |= docs[d]
    corpus_tokens: Set[str] = set()
    for toks in docs.values():
        corpus_tokens |= toks
    linked, unlinked, absent = [], [], []
    for fig in sorted(figs, key=lambda v: (len(v), v)):
        if fig in linked_tokens:
            linked.append(fig)
        elif fig in corpus_tokens:
            unlinked.append(fig)
        else:
            absent.append(fig)
    return {
        "id": node_id,
        "title": str(nodes[node_id].get("title", ""))[:90],
        "kind": node_id[0],
        "n_figures": len(figs),
        "reachable_docs": sorted(reach),
        "linked": linked,
        "unlinked": unlinked,
        "absent": absent,
    }


def census(
    nodes: Optional[Mapping[str, Mapping[str, object]]] = None,
    docs: Optional[Mapping[str, Set[str]]] = None,
    hops: int = 1,
) -> Dict[str, object]:
    nodes = nodes if nodes is not None else load_nodes()
    docs = docs if docs is not None else load_docs()
    per_node = []
    totals = collections.Counter()
    for node_id in nodes:
        row = classify_node(node_id, nodes, docs, hops)
        if not row["n_figures"]:
            totals["nodes_without_figures"] += 1
            continue
        totals["nodes_with_figures"] += 1
        totals["linked"] += len(row["linked"])
        totals["unlinked"] += len(row["unlinked"])
        totals["absent"] += len(row["absent"])
        per_node.append(row)
    total = totals["linked"] + totals["unlinked"] + totals["absent"]
    pct = (lambda n: round(100.0 * n / total, 1)) if total else (lambda n: 0.0)
    return {
        "lab_version": "numeric-provenance-lab-v1",
        "hops": hops,
        "n_nodes": len(nodes),
        "n_docs": len(docs),
        "figures_total": total,
        "figures_linked": totals["linked"],
        "figures_unlinked": totals["unlinked"],
        "figures_absent": totals["absent"],
        "pct_linked": pct(totals["linked"]),
        "pct_unlinked": pct(totals["unlinked"]),
        "pct_absent": pct(totals["absent"]),
        "nodes_with_figures": totals["nodes_with_figures"],
        "nodes_with_figures_but_no_reachable_doc": sum(
            1 for r in per_node if not r["reachable_docs"]),
        "figures_in_nodes_with_no_reachable_doc": sum(
            int(r["n_figures"]) for r in per_node if not r["reachable_docs"]),
        "nodes_without_figures": totals["nodes_without_figures"],
        "per_node": per_node,
        "interpretation": (
            "TRUST THE STRUCTURAL METRIC, NOT THE TOKEN CLASSES. "
            "`nodes_with_figures_but_no_reachable_doc` is uncontaminated: it asks only "
            "whether a node quoting numbers links (within one hop) to any study document, "
            "and it needs no value matching. The per-figure `linked`/`unlinked`/`absent` "
            "split is weaker: `unlinked` is heavily contaminated by COLLISION, because "
            "common values (0.74, 2022, 34) occur as standalone numerals somewhere among "
            "87 documents regardless of the claim. F17 is the calibration case — F139 "
            "established by hand that its figures are genuinely unlocated, yet all six "
            "classify `unlinked` here purely by collision. Read `unlinked` as an upper "
            "bound on recoverable evidence, and `absent` as a lower bound on missing."
        ),
        "caveats": [
            "Numeral matching is normalised for Unicode minus and thousands separators; "
            "without that, real figures are reported missing (this lab's first result "
            "overstated absent-everywhere by 1.4-1.9x depending on corpus vintage; "
            "measured 8.40% vs 4.50% at 2388 figures and 11.00% vs 8.00% at 2834).",
            "A bare numeric match does not prove the doc states the SAME quantity — it "
            "proves the token appears. This measures reachability of evidence, not "
            "agreement of values. Measured null: a figure perturbed by one tick — a "
            "value the corpus never claimed — still lands 'present in some doc' 59.4% "
            "of the time (4000 draws, seed 20260725). Never read a single figure's "
            "class as a verdict; only the aggregate contrast carries signal.",
            "62.9% of extracted figures are low-information tokens (43.8% bare "
            "two-digit integers, 19.1% four-digit years). Dates and trade counts are "
            "weighted the same as a Sharpe ratio.",
            "80.8% of `unlinked` figures sit in nodes reaching ZERO research docs — "
            "those nodes cite no study at all, so this is a CITATION gap, not a "
            "traversal gap. Do not label the residual 'untraversable'.",
            "Figures with fewer than {} digits are ignored as noise.".format(MIN_DIGITS),
        ],
    }


def worst(report: Mapping[str, object], top: int = 15, key: str = "unlinked") -> List[Dict[str, object]]:
    rows = list(report["per_node"])  # type: ignore[index]
    rows.sort(key=lambda r: (-len(r[key]), -int(r["n_figures"]), str(r["id"])))
    return rows[:top]


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def _write_json_atomic(path: Path, value: object) -> None:
    if str(path.resolve()).startswith(str(REPO) + "/"):
        raise ValueError("refusing to write the disposable report inside the repo")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, default=str)
        handle.write("\n")
    tmp.replace(path)


def command_census(args: argparse.Namespace) -> None:
    rep = census(hops=args.hops)
    print("figures across {} nodes / {} docs: {}".format(
        rep["nodes_with_figures"], rep["n_docs"], rep["figures_total"]))
    print("  linked   (doc reachable from the claim) {:5}  {:>5}%".format(
        rep["figures_linked"], rep["pct_linked"]))
    print("  unlinked (in a doc, but unreachable)    {:5}  {:>5}%".format(
        rep["figures_unlinked"], rep["pct_unlinked"]))
    print("  absent   (in no research doc)           {:5}  {:>5}%".format(
        rep["figures_absent"], rep["pct_absent"]))
    print("\nSTRUCTURAL (uncontaminated — no value matching involved):")
    print("  nodes quoting figures that reach NO research doc: {} of {}  ({:.0f}%)".format(
        rep["nodes_with_figures_but_no_reachable_doc"], rep["nodes_with_figures"],
        100.0 * rep["nodes_with_figures_but_no_reachable_doc"] / max(1, rep["nodes_with_figures"])))
    print("  figures inside those nodes: {} of {}".format(
        rep["figures_in_nodes_with_no_reachable_doc"], rep["figures_total"]))
    print("\n" + str(rep["interpretation"]))


def command_node(args: argparse.Namespace) -> None:
    nodes, docs = load_nodes(), load_docs()
    if args.node_id not in nodes:
        raise SystemExit("unknown node: {}".format(args.node_id))
    row = classify_node(args.node_id, nodes, docs, args.hops)
    print(json.dumps(row, indent=2, ensure_ascii=False))


def command_worst(args: argparse.Namespace) -> None:
    rep = census(hops=args.hops)
    print("nodes quoting figures that are present in the corpus but UNREACHABLE:")
    print("  (`cites nothing` = the node links to no research doc at all, so this is")
    print("   a CITATION gap, not a traversal gap — 80.8% of `unlinked` is this case)")
    for row in worst(rep, args.top, "unlinked"):
        why = "cites nothing" if not row["reachable_docs"] else "wrong docs  "
        print("  {:5} {:3}/{:3} unlinked  {}  {}".format(
            row["id"], len(row["unlinked"]), row["n_figures"], why, row["title"][:52]))
    print("\nnodes with figures ABSENT from every research doc:")
    for row in worst(rep, args.top, "absent"):
        if not row["absent"]:
            continue
        print("  {:5} {:3}/{:3} absent    {}".format(
            row["id"], len(row["absent"]), row["n_figures"], row["title"][:52]))


def command_report(args: argparse.Namespace) -> None:
    rep = census(hops=args.hops)
    _write_json_atomic(args.output, rep)
    print(json.dumps({k: v for k, v in rep.items() if k != "per_node"},
                     indent=2, ensure_ascii=False))
    print("wrote {}".format(args.output))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hops", type=int, default=1,
                        help="edge hops to follow when resolving a node's docs")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("census", help="corpus-wide figure classification")
    c.set_defaults(func=command_census)
    n = sub.add_parser("node", help="figure-by-figure provenance for one node")
    n.add_argument("node_id")
    n.set_defaults(func=command_node)
    w = sub.add_parser("worst", help="nodes with the largest provenance gaps")
    w.add_argument("--top", type=int, default=15)
    w.set_defaults(func=command_worst)
    r = sub.add_parser("report", help="full JSON report")
    r.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    r.set_defaults(func=command_report)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
