"""
MONAD Quant — Pre-registration: what a hypothesis claims, frozen before its evidence.

A result tested against a bar chosen after seeing it is not a test. This module freezes,
per hypothesis, everything the admission gate will judge it by: the family whose trials
count against it, the metric and threshold, the minimum sample, the cost model, and the
holdout it must survive. The file is written once and never edited. A changed spec is a
NEW hypothesis (linked to the old one with ``refines`` in the research web), and it
shares the old one's family, so refining an idea never resets its trial count.

Files: ``docs/research/prereg/<H>.json``, canonical JSON. ``spec_hash`` is the sha256 of
the file's canonical content; the gate records it with every verdict. ``verify_history``
(CI) fails if a registration present on the deploy branch was edited or deleted.

Profiles (the hybrid holdout decision, 2026-09-22):

  * ``price_strategy`` — holdout is FORWARD PAPER TRADING only. Future bars cannot be
    downloaded early and an LLM cannot remember them. The forward window starts at
    ``registered_at``.
  * ``event_study``    — holdout is a SEALED ISSUER VAULT (a secret, keyed, stratified
    subset of issuers/events the gate alone can resolve), then forward paper.
  * ``allocation``     — static-allocation claims; holdout is forward paper.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from src.research.trials import (REPO, LedgerError, _FAMILY, _HYPOTHESIS, _git, canonical_json,
                                 code_state, sha256_text)

SCHEMA_VERSION = 1
PREREG_REL = Path("docs/research/prereg")
PREREG_DIR = REPO / PREREG_REL

#: No registration may set a bar below these. A hypothesis can ask to be judged more
#: strictly than the repo's floor, never more leniently.
MIN_THRESHOLD = 0.95
MIN_TRADES_FLOOR = 30
MIN_FORWARD_DAYS_FLOOR = 60

PROFILES = {
    "price_strategy": {"forward_paper"},
    "event_study": {"sealed_issuers"},
    "allocation": {"forward_paper"},
}
METRICS = {"deflated_sharpe"}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED = ("hypothesis", "family", "claim", "profile", "universe", "development_window",
            "metric", "threshold", "min_trades", "holdout", "cost_model")


class PreregError(LedgerError):
    """A registration is malformed, too lenient, or would overwrite history."""


def validate(spec: Mapping[str, Any]) -> list[str]:
    """Every reason ``spec`` (the author-supplied part) cannot be registered."""
    errs = []
    missing = [k for k in REQUIRED if k not in spec]
    if missing:
        return [f"missing fields: {missing}"]
    extra = set(spec) - set(REQUIRED) - {"params", "notes"}
    if extra:
        errs.append(f"unknown fields: {sorted(extra)}")
    if not (isinstance(spec["hypothesis"], str) and _HYPOTHESIS.match(spec["hypothesis"])):
        errs.append("hypothesis must look like H<n>")
    if not (isinstance(spec["family"], str) and _FAMILY.match(spec["family"])):
        errs.append("family is not a valid ledger family")
    if not (isinstance(spec["claim"], str) and len(spec["claim"].strip()) >= 20):
        errs.append("claim must state what is being claimed (>= 20 characters)")
    profile = spec["profile"]
    if profile not in PROFILES:
        errs.append(f"profile must be one of {sorted(PROFILES)}")
    u = spec["universe"]
    if not (isinstance(u, list) and u and all(isinstance(x, str) and x for x in u)):
        errs.append("universe must be a non-empty list of symbols")
    w = spec["development_window"]
    if not (isinstance(w, Mapping) and _DATE.match(str(w.get("start", "")))
            and _DATE.match(str(w.get("end", ""))) and w["start"] < w["end"]):
        errs.append("development_window needs start < end as YYYY-MM-DD")
    if spec["metric"] not in METRICS:
        errs.append(f"metric must be one of {sorted(METRICS)}")
    t = spec["threshold"]
    if not (isinstance(t, (int, float)) and not isinstance(t, bool) and MIN_THRESHOLD <= t < 1):
        errs.append(f"threshold must be in [{MIN_THRESHOLD}, 1)")
    mt = spec["min_trades"]
    if not (isinstance(mt, int) and not isinstance(mt, bool) and mt >= MIN_TRADES_FLOOR):
        errs.append(f"min_trades must be an integer >= {MIN_TRADES_FLOOR}")
    h = spec["holdout"]
    if not isinstance(h, Mapping) or "kind" not in h:
        errs.append("holdout must be an object with a kind")
    else:
        if profile in PROFILES and h["kind"] not in PROFILES[profile]:
            errs.append(f"profile {profile!r} requires holdout kind {sorted(PROFILES[profile])}")
        if h["kind"] == "forward_paper":
            d = h.get("min_days")
            if not (isinstance(d, int) and d >= MIN_FORWARD_DAYS_FLOOR):
                errs.append(f"forward_paper.min_days must be an integer >= {MIN_FORWARD_DAYS_FLOOR}")
            ftr = h.get("min_trades")
            if not (isinstance(ftr, int) and ftr >= 1):
                errs.append("forward_paper.min_trades must be a positive integer")
        elif h["kind"] == "sealed_issuers":
            if not (isinstance(h.get("vault"), str) and h["vault"]):
                errs.append("sealed_issuers.vault must name the vault")
    if not isinstance(spec["cost_model"], Mapping) or not spec["cost_model"]:
        errs.append("cost_model must state the cost assumption")
    try:
        canonical_json(dict(spec))
    except LedgerError as exc:
        errs.append(f"spec is not canonically encodable: {exc}")
    return errs


def spec_hash(record: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(record))


def path_for(hypothesis: str, prereg_dir: Path | None = None) -> Path:
    return (Path(prereg_dir) if prereg_dir is not None else PREREG_DIR) / f"{hypothesis}.json"


def _web_status(hypothesis: str) -> str | None:
    """The hypothesis's status in RESEARCH_WEB.md, or None if it has no node there."""
    sys.path.insert(0, str(REPO / "tools"))
    import ctx  # the web's parser; read-only here

    nodes = ctx._parse_web()[0]
    node = nodes.get(hypothesis)
    return None if node is None else (ctx._node_meta(node)["status"] or "current")


def register(spec: Mapping[str, Any], *, prereg_dir: Path | None = None,
             check_web: bool = True, now: str | None = None) -> tuple[Path, str]:
    """Freeze ``spec``. Returns (path, spec_hash). Refuses to overwrite, ever."""
    errs = validate(spec)
    if errs:
        raise PreregError("; ".join(errs))
    hyp = spec["hypothesis"]
    if check_web:
        status = _web_status(hyp)
        if status is None:
            raise PreregError(f"{hyp} is not a node in RESEARCH_WEB.md; add it with note.py first")
        if status != "current":
            raise PreregError(f"{hyp} is {status}; register a new hypothesis that refines it")
    record = {"schema": SCHEMA_VERSION, **dict(spec),
              "registered_at": now or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
              "registered_from": code_state()}
    target = path_for(hyp, prereg_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (canonical_json(record) + "\n").encode("utf-8")
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        raise PreregError(f"{hyp} is already registered ({target.name}); a changed spec is a "
                          f"new hypothesis that refines it") from None
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    return target, spec_hash(record)


def load(hypothesis: str, *, prereg_dir: Path | None = None) -> tuple[dict, str]:
    """The frozen registration and its hash. Raises if absent, malformed, or edited
    into a form that no longer validates."""
    p = path_for(hypothesis, prereg_dir)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PreregError(f"{hypothesis} has no pre-registration") from None
    record = json.loads(text)
    if text != canonical_json(record) + "\n":
        raise PreregError(f"{p.name} is not in canonical form (hand-edited?)")
    author = {k: v for k, v in record.items() if k in REQUIRED or k in ("params", "notes")}
    errs = validate(author)
    if errs or record.get("hypothesis") != hypothesis:
        raise PreregError(f"{p.name} no longer validates: {errs or 'hypothesis mismatch'}")
    return record, spec_hash(record)


def verify_history(base_ref: str, *, repo: Path = REPO, prereg_rel: Path = PREREG_REL) -> list[str]:
    """Registrations present at merge-base(HEAD, base_ref) are unchanged and undeleted."""
    mb = _git(repo, "merge-base", "HEAD", base_ref)
    if mb.returncode != 0:
        return [f"cannot resolve merge-base with {base_ref!r}"]
    base = mb.stdout.decode().strip()
    listing = _git(repo, "ls-tree", "-r", "-z", "--name-only", base, "--", prereg_rel.as_posix())
    problems = []
    for rel in (p for p in listing.stdout.decode().split("\0") if p.endswith(".json")):
        old = _git(repo, "show", f"{base}:{rel}").stdout
        try:
            now = (repo / rel).read_bytes()
        except FileNotFoundError:
            problems.append(f"{rel}: deleted (registered at {base[:12]})")
            continue
        if now != old:
            problems.append(f"{rel}: edited since {base[:12]}; register a refining hypothesis instead")
    return problems
