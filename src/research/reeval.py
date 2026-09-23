"""
MONAD Quant — Re-evaluating the findings the web already holds.

The accountable workflow (trial ledger, pre-registration, admission gate) governs claims
made from now on. The ~280 current Findings in RESEARCH_WEB.md predate it. Decision
(2026-09-22): re-evaluate them rather than grandfather them. That cannot be automated end
to end, because many findings were never runs and some claims need a reader to classify.
So this module sorts every current Finding into a tier that says how it will be
re-evaluated, and keeps an append-only log of the decisions made about each.

Tiers (first match wins):

  settled      superseded or retracted in the web; nothing to re-evaluate
  decided      has a recorded re-evaluation decision (see below)
  guarded      a test named after it exists (tests/test_<id>_*.py): CI re-checks it
  market       mentions market performance (Sharpe, returns, edge, drawdown...) and has
               no decision: MUST be classified, because a positive edge claim now needs
               an ADMIT verdict from tools/admit.py or an explicit "unadmitted" label
  traceable    cites evidence (an evidenced_by edge, or an Experiment/document)
  unverified   none of the above: needs evidence located, or the claim narrowed

The keyword test for ``market`` is deliberately loose: a false positive costs one
classification, a false negative lets a performance claim bypass the gate.

Decisions (``docs/research/reeval/decisions.jsonl``, append-only, CI-checked), one per
node, each citing evidence:

  classification  positive_edge | negative_or_method | not_market
  action          admitted (cites a verdict) | unadmitted_historical | reproduced
                  (cites a ledger run) | narrowed (cites the superseding node) | no_action
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Mapping

from src.research import trials
from src.research.trials import REPO, LedgerError, canonical_json

REEVAL_REL = Path("docs/research/reeval")
REEVAL_DIR = REPO / REEVAL_REL
DECISIONS = "decisions.jsonl"

TIERS = ("settled", "decided", "guarded", "market", "traceable", "unverified")
CLASSIFICATIONS = ("positive_edge", "negative_or_method", "not_market")
ACTIONS = ("admitted", "unadmitted_historical", "reproduced", "narrowed", "no_action")
#: A positive edge claim may not be closed with "no_action": it is either admitted,
#: reproduced, narrowed, or explicitly labelled as an unadmitted historical claim.
POSITIVE_EDGE_ACTIONS = ("admitted", "unadmitted_historical", "reproduced", "narrowed")

MARKET = re.compile(r"sharpe|%\s*/\s*mo|/mo\b|win rate|\bWR\b|\bedge\b|alpha|drawdown|"
                    r"total return|CAGR|profit|outperform|beats? (?:buy|b&h|the benchmark)",
                    re.I)


class ReevalError(LedgerError):
    pass


def _nodes() -> dict:
    sys.path.insert(0, str(REPO / "tools"))
    import epistemic_audit_lab as epi  # the canonical web parser the backlog also uses

    return epi.parse_web((REPO / "RESEARCH_WEB.md").read_text(encoding="utf-8"))


def guarded_ids(tests_dir: Path = REPO / "tests") -> set:
    """Finding ids with a test named after them (``test_f260_...`` -> F260)."""
    out = set()
    for p in tests_dir.glob("test_*.py"):
        for m in re.finditer(r"(?:^|_)(f\d+)(?=_|$)", p.stem[len("test_"):]):
            out.add(m.group(1).upper())
    return out


def decisions(directory: Path | None = None) -> dict:
    """{node: latest decision row}."""
    p = (Path(directory) if directory is not None else REEVAL_DIR) / DECISIONS
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line:
            row = json.loads(line)
            out[row["node"]] = row
    return out


def classify(nodes: Mapping[str, dict] | None = None, *, decided: Mapping | None = None,
             guarded: set | None = None) -> dict:
    """{finding id: tier} for every Finding in the web."""
    nodes = nodes if nodes is not None else _nodes()
    decided = decided if decided is not None else decisions()
    guarded = guarded if guarded is not None else guarded_ids()
    tiers = {}
    for nid, n in nodes.items():
        if not nid.startswith("F"):
            continue
        text = f"{n.get('title', '')}\n{n.get('body', '')}"
        if str(n.get("status", "current")).lower() in ("superseded", "retracted"):
            tiers[nid] = "settled"
        elif nid in decided:
            tiers[nid] = "decided"
        elif nid in guarded:
            tiers[nid] = "guarded"
        elif MARKET.search(text):
            tiers[nid] = "market"
        elif n.get("has_evidenced_by") or n.get("cites_experiment") or "docs/research/" in text:
            tiers[nid] = "traceable"
        else:
            tiers[nid] = "unverified"
    return tiers


def queue(tiers: Mapping[str, str]) -> list:
    """Work order: market claims first (they bypass the gate until classified), then
    unverified. Guarded, traceable, settled and decided nodes are not queued."""
    def num(nid):
        return int(re.sub(r"\D", "", nid) or 0)
    market = sorted((n for n, t in tiers.items() if t == "market"), key=num)
    unverified = sorted((n for n, t in tiers.items() if t == "unverified"), key=num)
    return market + unverified


def decide(node: str, *, classification: str, action: str, evidence: str, by: str,
           directory: Path | None = None, nodes: Mapping | None = None) -> dict:
    """Append one decision. Refuses a positive edge claim closed with no_action, an
    'admitted' action without a verdict path, and a 'reproduced' one without a run id."""
    nodes = nodes if nodes is not None else _nodes()
    if node not in nodes or not node.startswith("F"):
        raise ReevalError(f"{node} is not a Finding in RESEARCH_WEB.md")
    if classification not in CLASSIFICATIONS:
        raise ReevalError(f"classification must be one of {CLASSIFICATIONS}")
    if action not in ACTIONS:
        raise ReevalError(f"action must be one of {ACTIONS}")
    if classification == "positive_edge" and action not in POSITIVE_EDGE_ACTIONS:
        raise ReevalError("a positive edge claim must be admitted, reproduced, narrowed, or "
                          "labelled unadmitted_historical; it cannot be closed with no_action")
    if not isinstance(evidence, str) or len(evidence.strip()) < 10:
        raise ReevalError("evidence must be checkable (>= 10 characters)")
    if action == "admitted" and "docs/research/verdicts/" not in evidence:
        raise ReevalError("an admitted decision must cite its docs/research/verdicts/ record")
    if action == "reproduced" and not re.search(r"TR-\d{8}T\d{6}Z-[0-9a-f]{8}", evidence):
        raise ReevalError("a reproduced decision must cite the ledger run (TR-...) that reproduced it")
    if not isinstance(by, str) or not by.strip():
        raise ReevalError("by must name who decided")
    row = {"node": node, "classification": classification, "action": action,
           "evidence": evidence, "by": by,
           "at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    d = Path(directory) if directory is not None else REEVAL_DIR
    d.mkdir(parents=True, exist_ok=True)
    fd = os.open(d / DECISIONS, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(canonical_json(row) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return row


def verify_history(base_ref: str, *, repo: Path = REPO) -> list:
    """The decisions log on the deploy branch only grows."""
    return trials.verify_history(base_ref, REEVAL_REL, repo=repo, what="decisions log",
                                 rule=lambda r: "prefix" if r.endswith(DECISIONS) else None)
