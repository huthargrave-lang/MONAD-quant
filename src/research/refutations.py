"""
MONAD Quant — Refutations: objections to a hypothesis, and how each was answered.

The accountable edge-hunt loop has refuter agents whose job is to break a candidate
(look-ahead leaks, live/backtest parity breaks, cost fragility, sampling artifacts like
F13). An objection that is written down and then ignored is worse than none, so the
admission gate BLOCKS any hypothesis with an objection that has no resolution.

Storage: ``docs/research/refutations/<H>.jsonl``, append-only canonical JSON lines:

  {"type": "objection",  "id": "O1", "at", "by", "claim", "evidence"}
  {"type": "resolution", "id": "S1", "at", "by", "resolves": "O1", "outcome", "evidence"}

``outcome`` is ``"refuted"`` (the objection was wrong, and ``evidence`` shows why) or
``"upheld"`` (the objection stands; the hypothesis should be rejected or refined). An
upheld objection is resolved in the sense of answered, and the gate REJECTS on it.
Nothing is ever edited or deleted; CI checks the files only grow.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path

from src.research import trials
from src.research.trials import REPO, LedgerError, _HYPOTHESIS, canonical_json

REFUTATIONS_REL = Path("docs/research/refutations")
REFUTATIONS_DIR = REPO / REFUTATIONS_REL
OUTCOMES = ("refuted", "upheld")


class RefutationError(LedgerError):
    pass


def _path(hypothesis: str, directory: Path | None) -> Path:
    if not _HYPOTHESIS.match(hypothesis):
        raise RefutationError(f"hypothesis {hypothesis!r} must look like H<n>")
    return (Path(directory) if directory is not None else REFUTATIONS_DIR) / f"{hypothesis}.jsonl"


def entries(hypothesis: str, directory: Path | None = None) -> list[dict]:
    p = _path(hypothesis, directory)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line]


def _append(hypothesis: str, row: dict, directory: Path | None) -> dict:
    p = _path(hypothesis, directory)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json(row) + "\n"
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    return row


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require(text: str, name: str) -> None:
    if not isinstance(text, str) or len(text.strip()) < 10:
        raise RefutationError(f"{name} must say something checkable (>= 10 characters)")


def _require_author(by: str) -> None:
    if not isinstance(by, str) or not by.strip():
        raise RefutationError("by must name who is objecting or resolving")


def object_to(hypothesis: str, *, claim: str, evidence: str, by: str,
              directory: Path | None = None) -> dict:
    """Record an objection. ``evidence`` names what shows it (a ledger run, a file:line,
    a command): an objection nobody could check is noise."""
    _require(claim, "claim")
    _require(evidence, "evidence")
    _require_author(by)
    n = sum(1 for e in entries(hypothesis, directory) if e["type"] == "objection") + 1
    return _append(hypothesis, {"type": "objection", "id": f"O{n}", "at": _now(), "by": by,
                                "claim": claim, "evidence": evidence}, directory)


def resolve(hypothesis: str, objection_id: str, *, outcome: str, evidence: str, by: str,
            directory: Path | None = None) -> dict:
    """Answer an objection. Refuting one requires evidence as specific as the objection's."""
    if outcome not in OUTCOMES:
        raise RefutationError(f"outcome must be one of {OUTCOMES}")
    _require(evidence, "evidence")
    _require_author(by)
    rows = entries(hypothesis, directory)
    if not any(e["type"] == "objection" and e["id"] == objection_id for e in rows):
        raise RefutationError(f"{hypothesis} has no objection {objection_id}")
    if any(e["type"] == "resolution" and e["resolves"] == objection_id for e in rows):
        raise RefutationError(f"{objection_id} is already resolved; object again if it recurs")
    objector = next(e["by"] for e in rows if e["type"] == "objection" and e["id"] == objection_id)
    if by.strip().lower() == str(objector).strip().lower():
        raise RefutationError(f"{objection_id} was raised by {objector!r}; an objection is "
                              f"answered by someone other than the one who raised it")
    n = sum(1 for e in rows if e["type"] == "resolution") + 1
    return _append(hypothesis, {"type": "resolution", "id": f"S{n}", "at": _now(), "by": by,
                                "resolves": objection_id, "outcome": outcome,
                                "evidence": evidence}, directory)


def status(hypothesis: str, directory: Path | None = None) -> dict:
    """{"open": [objections without a resolution], "upheld": [...], "refuted": [...]}."""
    rows = entries(hypothesis, directory)
    answers = {e["resolves"]: e for e in rows if e["type"] == "resolution"}
    out = {"open": [], "upheld": [], "refuted": []}
    for e in rows:
        if e["type"] != "objection":
            continue
        a = answers.get(e["id"])
        out["open" if a is None else a["outcome"]].append(e)
    return out


def verify_history(base_ref: str, *, repo: Path = REPO,
                   rel: Path = REFUTATIONS_REL) -> list[str]:
    """Refutation logs on the deploy branch only ever grow."""
    return trials.verify_history(base_ref, rel, repo=repo, what="refutation log",
                                 rule=lambda r: "prefix" if r.endswith(".jsonl") else None)
