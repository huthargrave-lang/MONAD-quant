"""
MONAD Quant — a forward watch: a frozen, tamper-evident, daily paper record of a rule
that the admission gate cannot admit, kept so forward evidence can still promote or close
it (board ruling 2026-10-09, docs/research/MINER_TILT_FORWARD_WATCH.md).

  * The SPEC (``docs/research/forward_watch/<ID>.json``) is written once, canonical, named
    by its sha-256, and needs a current web node, as a pre-registration does. It is NOT an
    admission candidate.
  * The LOG (``<ID>.jsonl``) only grows. Each line carries the previous line's sha-256
    (a hash chain), the spec hash, the code state, and for a session line every book's
    return and cost, the combined active return at 1x and 2x costs, and the book state
    after the session at full precision. So the log alone continues the record, and each
    session's return is computed once, from the previous line's logged book and pending
    orders, and never recomputed: a later vendor revision cannot rewrite it. A revision
    detected later (a late-booked distribution) is a CORRECTION line on the day it is
    found, carrying the active-return delta.
  * Each logging run is one COUNTED trial per session (family ``forward_watch.<ID>.v1``):
    the engine (``daily_strategy.evaluate_daily``, continued from the logged book with
    ``initial=``) refuses to run uncounted, and the watch does not loosen that.

Books: for each pair (miner, metal) of the spec, the rule's tilt book and its 50/50
benchmark book, at 1x and at ``stress_multiple`` x costs; 21 tranches each, tranche k
deciding on the sessions whose index from the spec's anchor session is k mod 21 (the
schedule ``commodity_classes`` uses), executing at the next open.

Evaluation (``decide``): a Wald sequential test of annualised active Sharpe 0 against
``theta1``, checked on anniversaries of the window's opening only: promote when
T (theta1 S_T - theta1^2/2) >= ln((1-beta)/alpha) and the stressed Sharpe is > 0; close
when it is <= ln(beta/(1-alpha)). Promotion cannot admit; it triggers a decision debate.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from src.research import commodity_classes as cc
from src.research import daily_data
from src.research.daily_classes import MONTH
from src.research.daily_strategy import BookState, Tranche, evaluate_daily
from src.research.trials import REPO, canonical_json, code_state
from src.strategy.counted import evaluator as _counted_evaluator

WATCH_DIR = REPO / "docs/research/forward_watch"
SCHEMA = 1
PRODUCER = "tools/forward_watch.py"
REQUIRED = ("watch", "claim", "status", "pairs", "pair_weights", "stress_multiple", "anchor_session",
            "snapshot_start", "replay_from", "evaluation", "evaluator_sources", "evaluator_sha256",
            "void_conditions", "window_opens")
#: Engine sources whose arithmetic a watch's record depends on; the spec pins their hash.
EVALUATOR_SOURCES = ("src/research/daily_strategy.py", "src/research/daily_data.py",
                     "src/research/commodity_classes.py", "src/research/forward_watch.py")
#: A watch on a registered domain rule (H366201 on): the spec names the domain, its frozen
#: point and reference, and the data the books continue from.
REQUIRED_DOMAIN = ("watch", "claim", "status", "domain_rule", "stress_multiple", "anchor_session",
                   "snapshot_start", "snapshot_universe", "replay_from", "genesis_session",
                   "genesis_data", "recorded", "session_dates_sha256", "identity", "nav_source",
                   "evaluation", "evaluator_sources", "evaluator_sha256", "void_conditions",
                   "window_opens")
LINE_KINDS = ("genesis", "window_open", "session", "correction", "evaluator_change", "void",
              "vintage", "nav_revision", "symbol_change")
#: A decision executes at the next session's close; a NAV vintage fetched before then is one
#: a live process could have used (board, METAL_TRUST_FORWARD_WATCH.md).
EXECUTION_CLOSE_UTC = pd.Timedelta(hours=20)
CORRECTION_LOOKBACK = 63          # sessions re-checked for late vendor revisions each run


class WatchError(RuntimeError):
    """The watch's spec, log or state is not what it must be."""


# ── spec ─────────────────────────────────────────────────────────────────────
def spec_path(watch: str, watch_dir: Path | None = None) -> Path:
    return (watch_dir or WATCH_DIR) / f"{watch}.json"


def log_path(watch: str, watch_dir: Path | None = None) -> Path:
    return (watch_dir or WATCH_DIR) / f"{watch}.jsonl"


def evaluator_sha256(sources=EVALUATOR_SOURCES, repo: Path = REPO) -> str:
    h = hashlib.sha256()
    for rel in sources:
        h.update(rel.encode() + b"\0" + (repo / rel).read_bytes() + b"\0")
    return h.hexdigest()


def spec_evaluator_sha256(spec: Mapping, repo: Path = REPO) -> str:
    """The hash of the sources THIS spec pins (its own ``evaluator_sources``), so a watch
    on another rule pins its own engine without re-scoping any other watch's pin."""
    return evaluator_sha256(tuple(spec["evaluator_sources"]), repo=repo)


def is_domain(spec: Mapping) -> bool:
    """A watch on a registered domain rule (``domain_rule``), not H366200's ratio pairs."""
    return "domain_rule" in spec


def validate(spec: Mapping) -> list[str]:
    if is_domain(spec):
        return _validate_domain(spec)
    errs = [f"missing {k}" for k in REQUIRED if k not in spec]
    if errs:
        return errs
    if abs(sum(spec["pair_weights"]) - 1.0) > 1e-12 or len(spec["pair_weights"]) != len(spec["pairs"]):
        errs.append("pair_weights must match pairs and sum to 1")
    if spec["stress_multiple"] <= 1:
        errs.append("stress_multiple must exceed 1")
    ev = spec["evaluation"]
    for k in ("theta1", "alpha", "beta"):
        if k not in ev:
            errs.append(f"evaluation lacks {k}")
    if "not an admission candidate" not in spec["status"]:
        errs.append("status must say the watch is not an admission candidate")
    return errs


def _validate_domain(spec: Mapping) -> list[str]:
    errs = [f"missing {k}" for k in REQUIRED_DOMAIN if k not in spec]
    if errs:
        return errs
    rule = spec["domain_rule"]
    errs += [f"domain_rule lacks {k}" for k in ("domain", "point", "reference", "assets", "trusts")
             if k not in rule]
    if spec["stress_multiple"] <= 1:
        errs.append("stress_multiple must exceed 1")
    errs += [f"evaluation lacks {k}" for k in ("theta1", "alpha", "beta") if k not in spec["evaluation"]]
    if "not an admission candidate" not in spec["status"]:
        errs.append("status must say the watch is not an admission candidate")
    if not errs and set(spec["recorded"]) != {n for n, *_ in book_names(spec)}:
        errs.append("recorded must give a returns sha for every book")
    return errs


def freeze(spec: Mapping, *, watch_dir: Path | None = None, check_web: bool = True,
           now: str | None = None) -> tuple[Path, str]:
    """Write ``spec`` once (O_EXCL), canonical. Returns (path, spec sha-256)."""
    errs = validate(spec)
    if errs:
        raise WatchError("; ".join(errs))
    if check_web:
        from src.research.prereg import _web_status
        status = _web_status(spec["watch"])
        if status is None:
            raise WatchError(f"{spec['watch']} is not a node in RESEARCH_WEB.md; add it with note.py first")
        if status != "current":
            raise WatchError(f"{spec['watch']} is {status}")
    record = {"schema": SCHEMA, **dict(spec),
              "frozen_at": now or _utc_now(), "frozen_from": code_state()}
    target = spec_path(spec["watch"], watch_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (canonical_json(record) + "\n").encode("utf-8")
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        raise WatchError(f"{target.name} exists: a frozen watch is never rewritten") from None
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return target, hashlib.sha256(data).hexdigest()


def load(watch: str, watch_dir: Path | None = None) -> tuple[dict, str]:
    data = spec_path(watch, watch_dir).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


# ── books ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Book:
    """One book after a session: its state and the orders decided at that close
    (tranche -> target weights), which execute at the next session's open."""
    state: BookState
    pending: Mapping[int, Mapping[str, float]]
    #: When the pending orders execute: at the next session's "open" (H366200's books) or
    #: its "close" (a domain rule that trades at the close). Written only when not "open",
    #: so the books of earlier lines re-serialise byte for byte.
    leg: str = "open"

    def to_json(self) -> dict:
        out = {"state": self.state.to_json(),
               "pending": {str(k): dict(v) for k, v in sorted(self.pending.items())}}
        if self.leg != "open":
            out["leg"] = self.leg
        return out

    @classmethod
    def from_json(cls, d) -> "Book":
        return cls(state=BookState.from_json(d["state"]),
                   pending={int(k): {a: float(w) for a, w in v.items()} for k, v in d["pending"].items()},
                   leg=d.get("leg", "open"))


def book_names(spec: Mapping) -> list[tuple[str, tuple, str, float]]:
    """(name, pair, kind, cost multiple) for every book of the watch. A domain watch has
    one tilt and one benchmark book per cost level (pair None)."""
    if is_domain(spec):
        return [(f"{kind}:{mult:g}x", None, kind, mult)
                for mult in (1.0, float(spec["stress_multiple"])) for kind in ("tilt", "bench")]
    out = []
    for m, M in spec["pairs"]:
        for mult in (1.0, float(spec["stress_multiple"])):
            for kind in ("tilt", "bench"):
                out.append((f"{m}/{M}:{kind}:{mult:g}x", (m, M), kind, mult))
    return out


def targets(snap: daily_data.Snapshot, pair, kind: str) -> pd.DataFrame:
    """Each session's target weights for a book (data through that session only)."""
    m, M = pair
    if kind == "tilt":
        return cc.ratio_weights(snap, cc.ratio_point(m, M)["params"])
    w = pd.DataFrame({m: 0.5, M: 0.5}, index=snap.dates)
    return w.loc[snap.close[[m, M]].notna().all(axis=1)]


def decisions(snap, pair, kind: str, session: pd.Timestamp, index: int,
              target_weights: pd.DataFrame | None = None) -> dict:
    """The orders decided at ``session``'s close: the one tranche whose turn it is.
    ``target_weights``: ``targets(snap, pair, kind)`` when the caller has it already."""
    k = index % MONTH
    w = targets(snap, pair, kind) if target_weights is None else target_weights
    if session not in w.index or w.loc[session].isna().any():
        return {}
    return {k: {a: float(v) for a, v in w.loc[session].items()}}


def _tranches_for(book: Book, prev_session: pd.Timestamp, assets) -> list[Tranche]:
    out = []
    for k in range(MONTH):
        if k in book.pending:
            orders = pd.DataFrame([book.pending[k]], index=pd.DatetimeIndex([prev_session]))
        else:
            orders = pd.DataFrame()
        if book.leg == "close":
            out.append(Tranche(open_orders=pd.DataFrame(), close_orders=orders))
        else:
            out.append(Tranche(open_orders=orders, close_orders=pd.DataFrame()))
    return out


@_counted_evaluator
def evaluate_session(spec: Mapping, books: Mapping[str, Book], snap: daily_data.Snapshot,
                     session: pd.Timestamp, index: int, *, rets=None, cache: dict | None = None,
                     tiers: Mapping | None = None, decided: Mapping | None = None) -> dict:
    """One session for every book, continued from its logged state and pending orders.
    A counted evaluation: the caller holds a begun trial. ``rets`` and ``cache`` (target
    weights per (pair, kind)) let a run compute each once; the result does not depend on
    them. A domain watch passes its cost ``tiers`` and the orders it ``decided`` at this
    session per book kind (from its carried rule state)."""
    pos = snap.dates.get_loc(session)
    prev = snap.dates[pos - 1]
    rets = rets if rets is not None else snap.returns()
    cache = {} if cache is None else cache
    if is_domain(spec) and decided is None:
        raise WatchError("a domain watch's session needs the orders it decided")
    out = {}
    for name, pair, kind, mult in book_names(spec):
        book = books[name]
        res = evaluate_daily(_tranches_for(book, prev, snap.assets), snap, start=session, end=session,
                             cost_multiple=mult, initial=book.state, rets=rets, tiers=tiers)
        if decided is not None:
            pending = decided[kind]
        else:
            key = (tuple(pair), kind)
            if key not in cache:
                cache[key] = targets(snap, pair, kind)
            pending = decisions(snap, pair, kind, session, index, cache[key])
        nxt = Book(state=res.final, pending=pending, leg=book.leg)
        out[name] = {"return": float(res.returns.iloc[0]), "cost": float(res.cost_paid), "book": nxt}
    return out


def combine(spec: Mapping, results: Mapping[str, dict]) -> dict:
    """Pair actives (tilt minus benchmark) and their pre-stated weighted sum, per cost level;
    a domain watch's active is its tilt book minus its benchmark book."""
    if is_domain(spec):
        return {f"{m:g}x": {"active": results[f"tilt:{m:g}x"]["return"] - results[f"bench:{m:g}x"]["return"]}
                for m in (1.0, float(spec["stress_multiple"]))}
    out = {}
    for mult in (1.0, float(spec["stress_multiple"])):
        total, pairs = 0.0, {}
        for (m, M), w in zip(spec["pairs"], spec["pair_weights"]):
            a = results[f"{m}/{M}:tilt:{mult:g}x"]["return"] - results[f"{m}/{M}:bench:{mult:g}x"]["return"]
            pairs[f"{m}/{M}"] = a
            total += w * a
        out[f"{mult:g}x"] = {"pairs": pairs, "active": total}
    return out


def asset_returns_sha256(snap, session: pd.Timestamp, assets) -> str:
    """A hash of the inputs a session used (night and day returns per asset), so a later
    vendor revision is detectable without committing the observations."""
    rets = snap.returns()
    payload = {a: [_f(rets.night.at[session, a]), _f(rets.day.at[session, a])] for a in sorted(assets)}
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def _f(x) -> float | None:
    return None if x is None or not np.isfinite(x) else float(x)


# ── the log ──────────────────────────────────────────────────────────────────
def read(watch: str, watch_dir: Path | None = None) -> list[tuple[bytes, dict]]:
    path = log_path(watch, watch_dir)
    if not path.exists():
        return []
    raw = path.read_bytes().splitlines()
    return [(line, json.loads(line)) for line in raw if line]


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


_READ_PREV = object()


def line_sha256(line: Mapping) -> str:
    """The hash the next line chains to: of the line's canonical bytes, as written."""
    return hashlib.sha256(canonical_json(line).encode("utf-8")).hexdigest()


def append(watch: str, payload: Mapping, *, spec_hash: str, watch_dir: Path | None = None,
           now: str | None = None, code: Mapping | None = None, prev_sha256=_READ_PREV) -> dict:
    """Append one line, chained to the previous one. ``prev_sha256``: the previous line's
    hash when the caller just wrote it (a run appending many lines); by default it is read
    from the log."""
    if payload.get("kind") not in LINE_KINDS:
        raise WatchError(f"unknown line kind {payload.get('kind')!r}")
    if prev_sha256 is _READ_PREV:
        rows = read(watch, watch_dir)
        prev = hashlib.sha256(rows[-1][0]).hexdigest() if rows else None
    else:
        prev = prev_sha256
    line = {"watch": watch, "spec_hash": spec_hash, "prev_sha256": prev,
            "recorded_at": now or _utc_now(), "code": dict(code or code_state()), **dict(payload)}
    path = log_path(watch, watch_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "ab") as fh:
        fh.write((canonical_json(line) + "\n").encode("utf-8"))
    return line


def latest_books(rows) -> tuple[dict, dict]:
    """(books by name, the last session-carrying line) from the newest line with books."""
    for _raw, r in reversed(rows):
        if r["kind"] in ("genesis", "session"):
            return {n: Book.from_json(b) for n, b in r["books"].items()}, r
    raise WatchError("the log has no genesis")


def verify(watch: str, watch_dir: Path | None = None, *, repo: Path = REPO) -> list[str]:
    """Problems with a watch's record: the chain, the spec hash, line order and contiguity
    of session indexes, kinds, genesis first, nothing after a void."""
    problems = []
    try:
        spec, spec_hash = load(watch, watch_dir)
    except FileNotFoundError:
        return [f"{watch}: no spec"]
    errs = validate(spec)
    problems += [f"spec: {e}" for e in errs]
    rows = read(watch, watch_dir)
    prev_sha, last_index, last_session, voided = None, None, None, False
    for i, (raw, r) in enumerate(rows, 1):
        where = f"line {i}"
        if r.get("prev_sha256") != prev_sha:
            problems.append(f"{where}: chain broken (prev_sha256 does not match line {i - 1})")
        if r.get("spec_hash") != spec_hash:
            problems.append(f"{where}: logged against a different spec")
        if r.get("kind") not in LINE_KINDS:
            problems.append(f"{where}: unknown kind {r.get('kind')!r}")
        if i == 1 and r.get("kind") != "genesis":
            problems.append(f"{where}: the first line must be the genesis")
        if voided:
            problems.append(f"{where}: written after the watch was voided")
        if r.get("kind") in ("genesis", "session"):
            if last_index is not None and r["session_index"] != last_index + 1:
                problems.append(f"{where}: session index {r['session_index']} does not follow {last_index}")
            if last_session is not None and r["session"] <= last_session:
                problems.append(f"{where}: session {r['session']} not after {last_session}")
            last_index, last_session = r["session_index"], r["session"]
        if r.get("kind") == "void":
            voided = True
        prev_sha = hashlib.sha256(raw).hexdigest()
    return problems


# ── genesis and logging ──────────────────────────────────────────────────────
def build_snapshot(spec: Mapping, end: str, *, data_dir: Path | None = None,
                   private_dir: Path | None = None, **fetchers) -> str:
    """A snapshot of the watch's assets from its fixed start to ``end`` (exclusive), in
    the shared store like every other data set a trial cites: the manifest in the
    committed store, the observations (vendor prices) in the private one."""
    assets = ["SPY"] + sorted({a for pair in spec["pairs"] for a in pair})
    return daily_data.build_snapshot(assets, spec["snapshot_start"], end, private=True,
                                     data_dir=data_dir, private_dir=private_dir, **fetchers)


def load_snapshot(sha: str, *, data_dir: Path | None = None,
                  private_dir: Path | None = None) -> daily_data.Snapshot:
    return daily_data.load_snapshot(sha, data_dir=data_dir, private_dir=private_dir)


@_counted_evaluator
def genesis_books(spec: Mapping, snap: daily_data.Snapshot, session: pd.Timestamp) -> dict:
    """Every book's state at ``session``'s close, by the domain rule replayed from the
    first session on or after the spec's ``replay_from`` that the rule can score (for the
    miner tilt, 2016-01-01: the same books that produced the recorded 2016-2026 series,
    continued), plus the orders decided at that close. A counted evaluation: the caller
    holds a begun trial."""
    anchor = pd.Timestamp(spec["anchor_session"])
    if snap.dates[0] != anchor:
        raise WatchError(f"snapshot starts {snap.dates[0].date()}, the anchor is {anchor.date()}")
    index = snap.dates.get_loc(session)
    out = {}
    for name, pair, kind, mult in book_names(spec):
        m, M = pair
        point = cc.ratio_point(m, M) if kind == "tilt" else cc.ratio_reference(m, M)
        start = cc.ratio_start(snap, m, M, floor=pd.Timestamp(spec["replay_from"]))
        res = evaluate_daily(cc.decide_ratio(snap, point), snap, start=start, end=session, cost_multiple=mult)
        out[name] = Book(state=res.final, pending=decisions(snap, pair, kind, session, index))
    return out


def decide(spec: Mapping, rows) -> list[dict]:
    """The anniversary reports and the sequential decision, from the log alone (session
    actives inside the window plus any corrections booked against them)."""
    ev = spec["evaluation"]
    theta, alpha, beta = ev["theta1"], ev["alpha"], ev["beta"]
    upper, lower = math.log((1 - beta) / alpha), math.log(beta / (1 - alpha))
    stress = f"{float(spec['stress_multiple']):g}x"
    opened, series, stressed, void = None, {}, {}, None
    for _raw, r in rows:
        if r["kind"] == "window_open":
            opened = r["opens_at_session"]
        elif r["kind"] == "session" and opened and r["session"] >= opened:
            series[r["session"]] = r["active"]["1x"]["active"]
            stressed[r["session"]] = r["active"][stress]["active"]
        elif r["kind"] == "correction" and r["session"] in series:
            series[r["session"]] += r["delta"]["1x"]
            stressed[r["session"]] += r["delta"][stress]
        elif r["kind"] == "void":
            void = {"verdict": "VOID", "reason": r["reason"]}
            break
    # A VOID ends the watch but does not erase it: the anniversaries reached before it
    # are reported with it (board, METAL_TRUST_FORWARD_WATCH.md).
    if not opened or not series:
        return [void] if void else []
    reports = _anniversaries(series, stressed, opened, theta, upper, lower)
    return reports + [void] if void else reports


def _anniversaries(series: dict, stressed: dict, opened: str, theta: float, upper: float,
                   lower: float) -> list[dict]:
    s = pd.Series(series).sort_index()
    s.index = pd.DatetimeIndex(s.index)
    s2 = pd.Series(stressed).reindex(s.index.strftime("%Y-%m-%d")).to_numpy()
    start = pd.Timestamp(opened)
    reports, year = [], 1
    while True:
        cut = start + pd.DateOffset(years=year)
        if s.index[-1] < cut:
            break
        x = s.loc[:cut]
        t = len(x) / 252
        sh = float(x.mean() / x.std(ddof=1) * math.sqrt(252)) if x.std(ddof=1) > 0 else 0.0
        x2 = s2[: len(x)]
        sh2 = float(np.mean(x2) / np.std(x2, ddof=1) * math.sqrt(252)) if np.std(x2, ddof=1) > 0 else 0.0
        llr = t * (theta * sh - theta ** 2 / 2)
        verdict = ("promote" if llr >= upper and sh2 > 0 else "close" if llr <= lower else "continue")
        reports.append({"anniversary": year, "as_of": str(cut.date()), "years": t, "sharpe": sh,
                        "sharpe_stressed": sh2, "llr": llr, "upper": upper, "lower": lower,
                        "verdict": verdict})
        if verdict != "continue":
            break
        year += 1
    return reports


POLICY = WATCH_DIR / "policy" / "route.json"
_SPEC_NAME = re.compile(r"^docs/research/forward_watch/([A-Za-z0-9_]+)\.json$")


def watches_ever_frozen(repo: Path = REPO) -> list[str]:
    """Every watch ID whose spec was added in any commit the repository holds, or that is
    present now: the m of the forward-evidence route (POLICY)."""
    from src.research.trials import _git
    out = _git(repo, "log", "--all", "--diff-filter=A", "--name-only", "--format=", "--",
               WATCH_DIR.relative_to(REPO).as_posix())
    names = out.stdout.decode().split() if out.returncode == 0 else []
    ids = {m.group(1) for n in names if (m := _SPEC_NAME.match(n))}
    ids |= {p.stem for p in WATCH_DIR.glob("*.json")}
    return sorted(ids)


def route_boundary(spec: Mapping, m: int) -> float:
    """The forward-evidence route's promotion boundary for this watch: ln(m (1-beta)/alpha)."""
    ev = spec["evaluation"]
    return math.log(m * (1 - ev["beta"]) / ev["alpha"])


def boundaries(spec: Mapping, years: float) -> tuple[float, float]:
    """(promote at Sharpe >=, close at Sharpe <=) after ``years``."""
    ev = spec["evaluation"]
    theta, alpha, beta = ev["theta1"], ev["alpha"], ev["beta"]
    up = theta / 2 + math.log((1 - beta) / alpha) / (theta * years)
    lo = theta / 2 + math.log(beta / (1 - alpha)) / (theta * years)
    return up, lo


# ── one logging run ──────────────────────────────────────────────────────────
def _books_json(books: Mapping[str, Book]) -> dict:
    return {n: b.to_json() for n, b in sorted(books.items())}


def write_genesis(watch: str, snap: daily_data.Snapshot, session: pd.Timestamp, *, run,
                  watch_dir: Path | None = None, now: str | None = None, code=None) -> dict:
    """The genesis line: state only (no return), at ``session``'s close."""
    spec, spec_hash = load(watch, watch_dir)
    if read(watch, watch_dir):
        raise WatchError(f"{watch} already has a genesis")
    t = run.begin(params={"watch": watch, "spec_hash": spec_hash, "kind": "genesis",
                          "session": str(session.date())}, data={"snapshot": snap.sha})
    books = genesis_books(spec, snap, session)
    t.complete(metrics={"books": len(books)})
    return append(watch, {"kind": "genesis", "session": str(session.date()),
                          "session_index": int(snap.dates.get_loc(session)),
                          "data": {"snapshot": snap.sha}, "books": _books_json(books),
                          "evaluator_sha256": spec_evaluator_sha256(spec)},
                  spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code)


def _pinned_evaluator(spec: Mapping, rows) -> str:
    pinned = spec["evaluator_sha256"]
    for _raw, r in rows:
        if r["kind"] == "evaluator_change":
            pinned = r["evaluator_sha256"]
    return pinned


def log_sessions(watch: str, snap: daily_data.Snapshot, *, run, opens_at: str | None = None,
                 watch_dir: Path | None = None, now: str | None = None, code=None,
                 current_evaluator: str | None = None) -> list[dict]:
    """Log every session of ``snap`` after the last logged one: corrections for late
    revisions first, then a window_open line once ``opens_at`` (the first session after
    the spec reached the deploy branch) is known, then one counted, chained line per
    session. Returns the lines written."""
    spec, spec_hash = load(watch, watch_dir)
    rows = read(watch, watch_dir)
    problems = verify(watch, watch_dir)
    if problems:
        raise WatchError(f"{watch}: the record does not verify: {problems[:3]}")
    if any(r["kind"] == "void" for _raw, r in rows):
        raise WatchError(f"{watch} is void")
    pinned = _pinned_evaluator(spec, rows)
    now_sha = current_evaluator or spec_evaluator_sha256(spec)
    if now_sha != pinned:
        raise WatchError(f"the evaluator sources changed (pinned {pinned[:12]}, now {now_sha[:12]}); "
                         f"attest the change (tools/forward_watch.py attest-evaluator) before logging")
    if pd.Timestamp(spec["anchor_session"]) != snap.dates[0]:
        raise WatchError(f"snapshot starts {snap.dates[0].date()}, the anchor is {spec['anchor_session']}")
    assets = sorted({a for pair in spec["pairs"] for a in pair})
    code = dict(code or code_state())
    rets, cache = snap.returns(), {}
    written = []
    written += _corrections(watch, spec, spec_hash, rows, snap, assets, run=run,
                            watch_dir=watch_dir, now=now, code=code, rets=rets, cache=cache)
    rows = read(watch, watch_dir)
    if opens_at and not any(r["kind"] == "window_open" for _raw, r in rows):
        written.append(append(watch, {"kind": "window_open", "opens_at_session": opens_at},
                              spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code))
    books, last = latest_books(read(watch, watch_dir))
    last_session = pd.Timestamp(last["session"])
    if last_session not in snap.dates:
        raise WatchError(f"the snapshot lacks the last logged session {last['session']}")
    if int(snap.dates.get_loc(last_session)) != last["session_index"]:
        raise WatchError("the snapshot's session count from the anchor disagrees with the log")
    new = snap.dates[snap.dates > last_session]
    catch_up = len(new) > 1
    rows = read(watch, watch_dir)
    prev = hashlib.sha256(rows[-1][0]).hexdigest()
    for session in new:
        index = int(snap.dates.get_loc(session))
        t = run.begin(params={"watch": watch, "spec_hash": spec_hash, "kind": "session",
                              "session": str(session.date())}, data={"snapshot": snap.sha})
        res = evaluate_session(spec, books, snap, session, index, rets=rets, cache=cache)
        act = combine(spec, res)
        t.complete(metrics={"active_1x": act["1x"]["active"]},
                   returns=pd.Series([act["1x"]["active"]], index=pd.DatetimeIndex([session])))
        books = {n: v["book"] for n, v in res.items()}
        written.append(append(watch, {
            "kind": "session", "session": str(session.date()), "session_index": index,
            "catch_up": catch_up, "data": {"snapshot": snap.sha},
            "inputs_sha256": asset_returns_sha256(snap, session, assets),
            "returns": {n: {"return": v["return"], "cost": v["cost"]} for n, v in sorted(res.items())},
            "active": act, "books": _books_json(books)},
            spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code, prev_sha256=prev))
        prev = line_sha256(written[-1])
    return written


def _corrections(watch, spec, spec_hash, rows, snap, assets, *, run, watch_dir, now, code,
                 rets=None, cache=None, tiers=None) -> list[dict]:
    """Re-check the last CORRECTION_LOOKBACK logged sessions' inputs against ``snap``; a
    changed input (a late-booked distribution, a vendor fix) gets a correction line with
    the active delta, recomputed from the logged state before that session. A domain
    watch recomputes with its cost ``tiers`` and the orders that session logged (the
    return does not depend on them; the carried rule state is never re-stepped)."""
    sessions = [(i, r) for i, (_raw, r) in enumerate(rows) if r["kind"] == "session"]
    current = {}
    for _raw, r in rows:
        if r["kind"] == "session":
            current[r["session"]] = r["inputs_sha256"]
        elif r["kind"] == "correction":
            current[r["session"]] = r["inputs_sha256"]
    written = []
    for i, r in sessions[-CORRECTION_LOOKBACK:]:
        session = pd.Timestamp(r["session"])
        if session not in snap.dates:
            continue
        fresh = asset_returns_sha256(snap, session, assets)
        if fresh == current[r["session"]]:
            continue
        before = next(rr for _raw, rr in reversed(rows[:i]) if rr["kind"] in ("genesis", "session"))
        books = {n: Book.from_json(b) for n, b in before["books"].items()}
        data = {"snapshot": snap.sha, **({"nav_panel": r["data"]["nav_panel"]} if is_domain(spec) else {})}
        decided = None
        if is_domain(spec):
            logged = {n: Book.from_json(b) for n, b in r["books"].items()}
            decided = {kind: logged[f"{kind}:1x"].pending for kind in ("tilt", "bench")}
        t = run.begin(params={"watch": watch, "spec_hash": spec_hash, "kind": "correction",
                              "session": r["session"]}, data=data)
        res = evaluate_session(spec, books, snap, session, r["session_index"], rets=rets, cache=cache,
                               tiers=tiers, decided=decided)
        act = combine(spec, res)
        t.complete(metrics={"active_1x": act["1x"]["active"]})
        delta = {k: act[k]["active"] - r["active"][k]["active"] for k in act}
        for _raw, rr in rows:          # earlier corrections of the same session already booked
            if rr["kind"] == "correction" and rr["session"] == r["session"]:
                delta = {k: delta[k] - rr["delta"][k] for k in delta}
        written.append(append(watch, {"kind": "correction", "session": r["session"],
                                      "inputs_sha256": fresh, "delta": delta, "data": data},
                              spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code))
        rows = read(watch, watch_dir)
    return written


# ── a watch on a registered domain rule (H366201: docs/research/METAL_TRUST_FORWARD_WATCH.md)
#: The rule modules that can carry their state forward, by domain. A domain rule whose
#: decisions depend on a path (a hysteresis state) must carry it rather than recompute it
#: from each run's data, so a revised old observation cannot flip today's order.
def _rule_module(spec: Mapping):
    domain = spec["domain_rule"]["domain"]
    if domain == "metal_trust_discount":
        from src.research import metal_trust_classes
        return metal_trust_classes
    raise WatchError(f"domain {domain!r} has no carried-state rule for a forward watch")


def domain_of(spec: Mapping):
    from src.research.daily_domains import DOMAINS
    return DOMAINS[spec["domain_rule"]["domain"]]


def rule_point(spec: Mapping, kind: str) -> Mapping:
    return spec["domain_rule"]["point" if kind == "tilt" else "reference"]


def session_dates_sha256(snap: daily_data.Snapshot, through: str) -> str:
    """The sessions from the anchor through ``through``: one missing or extra session would
    shift every tranche's phase."""
    days = [d.date().isoformat() for d in snap.dates[snap.dates <= pd.Timestamp(through)]]
    return hashlib.sha256(canonical_json(days).encode()).hexdigest()


def _listed(snap: daily_data.Snapshot, assets, session: pd.Timestamp) -> bool:
    return bool(snap.close.loc[session, list(assets)].notna().all())


def domain_targets(spec: Mapping, kind: str, rule_state: Mapping, session: pd.Timestamp) -> dict:
    """The target weights a book's rule reads at ``session``: the tilt from the carried
    states (each trust's state, neutral when its last observation is stale), the benchmark
    its static weights."""
    point = rule_point(spec, kind)
    if kind == "bench":
        return {a: float(w) for a, w in point["params"]["weights"].items()}
    mod = _rule_module(spec)
    return mod.carried_targets(point, {t: mod.read_state(rule_state[t], session) for t in rule_state})


def domain_decisions(spec: Mapping, rule_state: Mapping, snap: daily_data.Snapshot,
                     session: pd.Timestamp, index: int) -> dict:
    """Per book kind, the orders decided at ``session``'s close: the one tranche whose turn
    it is (index mod 21 from the anchor), none when a leg has no close that session."""
    if not _listed(snap, spec["domain_rule"]["assets"], session):
        return {"tilt": {}, "bench": {}}
    k = index % MONTH
    return {kind: {k: domain_targets(spec, kind, rule_state, session)} for kind in ("tilt", "bench")}


def advance_rule_state(spec: Mapping, rule_state: Mapping, panel, until: pd.Timestamp) -> dict:
    mod = _rule_module(spec)
    p = rule_point(spec, "tilt")["params"]
    return {t: mod.advance(panel, t, rule_state[t], until, p) for t in spec["domain_rule"]["trusts"]}


def nav_observations(panel, trust: str, before: pd.Timestamp) -> list:
    px, nav = panel.price[trust], panel.nav[trust]
    keep = nav.notna() & px.notna() & (nav.index < before)
    return [[d.date().isoformat(), float(px[d]), float(nav[d])] for d in nav.index[keep]]


def nav_inputs_sha256(spec: Mapping, panel, session: pd.Timestamp) -> str:
    """A hash of every NAV observation dated before ``session`` in the vintage read (the
    hysteresis state depends on the whole path, not the last 52 weeks)."""
    payload = {t: nav_observations(panel, t, session) for t in spec["domain_rule"]["trusts"]}
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def nav_revisions(spec: Mapping, old_panel, new_panel, rule_state: Mapping) -> list[dict]:
    """Already-stepped observations (dated on or before each trust's last stepped one) that
    a newer vintage changed or dropped: recorded, never stepped again."""
    out = []
    for t in spec["domain_rule"]["trusts"]:
        last = rule_state[t]["obs"]
        if not last:
            continue
        cut = pd.Timestamp(last) + pd.Timedelta(days=1)
        old = {d: (p, n) for d, p, n in nav_observations(old_panel, t, cut)}
        new = {d: (p, n) for d, p, n in nav_observations(new_panel, t, cut)}
        for d in sorted(set(old) | set(new)):
            if old.get(d) != new.get(d):
                h = lambda v: hashlib.sha256(canonical_json(list(v)).encode()).hexdigest() if v else None  # noqa: E731
                out.append({"trust": t, "date": d, "old_sha256": h(old.get(d)), "new_sha256": h(new.get(d))})
    return out


def _orders_at(tranches, session: pd.Timestamp) -> dict:
    """{tranche: target weights} of the orders a domain's decide() dated ``session``; they
    must all be close orders (the leg a domain watch carries)."""
    out = {}
    for k, tr in enumerate(tranches):
        if len(tr.open_orders) and session in tr.open_orders.index:
            raise WatchError("a domain watch carries close orders only; this rule trades at the open")
        if len(tr.close_orders) and session in tr.close_orders.index:
            out[k] = {a: float(w) for a, w in tr.close_orders.loc[session].items()}
    return out


@_counted_evaluator
def genesis_books_domain(spec: Mapping, snap: daily_data.Snapshot, panel, session: pd.Timestamp
                         ) -> tuple[dict, dict, dict]:
    """The four books replayed from ``replay_from`` (the recorded run's literal start)
    through ``session`` on the given data, their return series, and the carried rule state
    at ``session``; the pending orders are the ones the domain's decide() dated
    ``session``, and they must equal the ones the carried state decides. A counted
    evaluation: the caller holds a begun trial."""
    from src.research.daily_domains import Context
    anchor = pd.Timestamp(spec["anchor_session"])
    if snap.dates[0] != anchor:
        raise WatchError(f"snapshot starts {snap.dates[0].date()}, the anchor is {anchor.date()}")
    if list(snap.assets) != list(spec["snapshot_universe"]):
        raise WatchError(f"snapshot universe {list(snap.assets)} is not the frozen {spec['snapshot_universe']}")
    ctx = Context(snap=snap, panel=panel)
    dom = domain_of(spec)
    start = pd.Timestamp(spec["replay_from"])
    index = int(snap.dates.get_loc(session))
    rule_state = _rule_module(spec).carried_genesis(panel, rule_point(spec, "tilt"), session)
    carried = domain_decisions(spec, rule_state, snap, session, index)
    books, series = {}, {}
    for name, _pair, kind, mult in book_names(spec):
        tranches = dom.decide(ctx, rule_point(spec, kind))
        res = evaluate_daily(tranches, snap, start=start, end=session, cost_multiple=mult, tiers=dom.tiers(ctx))
        pending = _orders_at(tranches, session)
        if pending != carried[kind]:
            raise WatchError(f"{name}: the carried state decides {carried[kind]} at {session.date()}, "
                             f"the rule {pending}")
        books[name] = Book(state=res.final, pending=pending, leg="close")
        series[name] = res.returns
    return books, series, rule_state


def returns_sha256(returns: pd.Series) -> str:
    """The ledger's address of a return series (trials.Run.complete)."""
    from src.research.trials import canonical_returns, sha256_text
    return sha256_text(canonical_json(canonical_returns(returns)))


def write_genesis_domain(watch: str, snap: daily_data.Snapshot, panel, *, run, fresh=None,
                         watch_dir: Path | None = None, now: str | None = None, code=None) -> dict:
    """The genesis line of a domain watch, at its frozen ``genesis_session``, on its frozen
    ``genesis_data``: every book's returns sha must equal the recorded one. ``fresh``
    (snapshot, panel): a replay of the same window on fresh data, REPORTED only."""
    spec, spec_hash = load(watch, watch_dir)
    if read(watch, watch_dir):
        raise WatchError(f"{watch} already has a genesis")
    if {"snapshot": snap.sha, "nav_panel": panel.sha} != dict(spec["genesis_data"]):
        raise WatchError("the genesis runs on the spec's frozen genesis_data")
    session = pd.Timestamp(spec["genesis_session"])
    if session_dates_sha256(snap, spec["genesis_session"]) != spec["session_dates_sha256"]:
        raise WatchError("the snapshot's sessions through the genesis differ from the frozen ones")
    t = run.begin(params={"watch": watch, "spec_hash": spec_hash, "kind": "genesis",
                          "session": str(session.date())},
                  data={"snapshot": snap.sha, "nav_panel": panel.sha})
    books, series, rule_state = genesis_books_domain(spec, snap, panel, session)
    shas = {n: returns_sha256(r) for n, r in series.items()}
    t.complete(metrics={"books": len(books)})
    wrong = {n: (shas[n][:12], spec["recorded"][n][:12]) for n in shas if shas[n] != spec["recorded"][n]}
    if wrong:
        raise WatchError(f"the genesis does not reproduce the recorded books: {wrong}")
    payload = {"kind": "genesis", "session": str(session.date()),
               "session_index": int(snap.dates.get_loc(session)),
               "data": {"snapshot": snap.sha, "nav_panel": panel.sha},
               "vintage": {"nav_panel": panel.sha, "fetched_at": panel.manifest.get("fetched_at")},
               "recorded_returns_sha256": shas, "rule_state": rule_state,
               "books": _books_json(books), "evaluator_sha256": spec_evaluator_sha256(spec)}
    if fresh is not None:
        fsnap, fpanel = fresh
        t2 = run.begin(params={"watch": watch, "spec_hash": spec_hash, "kind": "genesis_fresh_replay",
                               "session": str(session.date())},
                       data={"snapshot": fsnap.sha, "nav_panel": fpanel.sha})
        _fb, fseries, _fs = genesis_books_domain(spec, fsnap, fpanel, session)
        t2.complete(metrics={"books": len(fseries)})
        payload["fresh_replay"] = {"snapshot": fsnap.sha, "nav_panel": fpanel.sha,
                                   "books": {n: _series_diff(fseries[n], series[n]) for n in series}}
    return append(watch, payload, spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code)


def _series_diff(fresh: pd.Series, recorded: pd.Series) -> dict:
    common = fresh.index.intersection(recorded.index)
    d = (fresh.reindex(common) - recorded.reindex(common)).abs()
    return {"max_abs_diff": float(d.max()) if len(d) else None, "sessions_differ": int((d > 0).sum()),
            "sessions_fresh": int(len(fresh)), "sessions_recorded": int(len(recorded)),
            "fresh_sha256": returns_sha256(fresh), "recorded_sha256": returns_sha256(recorded)}


def append_vintage(watch: str, panel, *, watch_dir: Path | None = None, now: str | None = None,
                   code=None) -> dict:
    """Record a fetched NAV vintage (its sha and when it was fetched), so later sessions
    can read only the vintages that existed before they executed."""
    spec, spec_hash = load(watch, watch_dir)
    missing = [t for t in spec["domain_rule"]["trusts"] if t not in panel.nav.columns]
    if missing:
        raise WatchError(f"the vintage lacks {missing}: a fetch that loses a trust records nothing")
    return append(watch, {"kind": "vintage", "nav_panel": panel.sha,
                          "fetched_at": panel.manifest.get("fetched_at")},
                  spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code)


def vintages(rows) -> list[tuple[pd.Timestamp, str]]:
    """(fetched_at UTC, panel sha) of every recorded vintage, the genesis's first."""
    out = []
    for _raw, r in rows:
        v = r.get("vintage") if r["kind"] == "genesis" else (r if r["kind"] == "vintage" else None)
        if v:
            out.append((pd.Timestamp(v["fetched_at"]).tz_convert("UTC").tz_localize(None), v["nav_panel"]))
    return sorted(out)


def vintage_for(rows, next_session: pd.Timestamp) -> tuple[pd.Timestamp, str]:
    """The newest vintage fetched before ``next_session``'s close (when the decision
    executes); the latest earlier one if none was fetched since."""
    deadline = pd.Timestamp(next_session).normalize() + EXECUTION_CLOSE_UTC
    usable = [v for v in vintages(rows) if v[0] < deadline]
    if not usable:
        raise WatchError(f"no NAV vintage was fetched before {deadline}")
    return usable[-1]


def _next_session(snap: daily_data.Snapshot, session: pd.Timestamp) -> pd.Timestamp:
    later = snap.dates[snap.dates > session]
    if len(later):
        return later[0]
    from src.research.nyse_calendar import is_session
    d = session + pd.Timedelta(days=1)
    while not is_session(d.date()):
        d += pd.Timedelta(days=1)
    return d


def log_sessions_domain(watch: str, snap: daily_data.Snapshot, load_panel, *, run,
                        opens_at: str | None = None, watch_dir: Path | None = None,
                        now: str | None = None, code=None, current_evaluator: str | None = None) -> list[dict]:
    """Log every session of ``snap`` after the last logged one, for a domain watch. Each
    session reads the newest NAV vintage fetched before it executed, steps the carried rule
    state through the observations dated after its last stepped one, decides, and is one
    counted, chained line; a newer vintage that revised an already-stepped observation is a
    ``nav_revision`` line. ``load_panel``: sha -> NavPanel."""
    from src.research.daily_domains import Context
    spec, spec_hash = load(watch, watch_dir)
    rows = read(watch, watch_dir)
    problems = verify(watch, watch_dir)
    if problems:
        raise WatchError(f"{watch}: the record does not verify: {problems[:3]}")
    if any(r["kind"] == "void" for _raw, r in rows):
        raise WatchError(f"{watch} is void")
    pinned = _pinned_evaluator(spec, rows)
    now_sha = current_evaluator or spec_evaluator_sha256(spec)
    if now_sha != pinned:
        raise WatchError(f"the evaluator sources changed (pinned {pinned[:12]}, now {now_sha[:12]}); "
                         f"attest the change (tools/forward_watch.py attest-evaluator) before logging")
    if pd.Timestamp(spec["anchor_session"]) != snap.dates[0] or list(snap.assets) != list(spec["snapshot_universe"]):
        raise WatchError("the snapshot's anchor or universe is not the frozen one")
    if session_dates_sha256(snap, spec["genesis_session"]) != spec["session_dates_sha256"]:
        raise WatchError("the snapshot's sessions through the genesis differ from the frozen ones")
    assets = sorted(spec["domain_rule"]["assets"])
    code = dict(code or code_state())
    rets = snap.returns()
    panels: dict = {}

    def panel_of(sha):
        if sha not in panels:
            panels[sha] = load_panel(sha)
        return panels[sha]

    _b, newest = latest_books(rows)
    tiers = domain_of(spec).tiers(Context(snap=snap, panel=panel_of(newest["data"]["nav_panel"])))
    written = []
    written += _corrections(watch, spec, spec_hash, rows, snap, assets, run=run, watch_dir=watch_dir,
                            now=now, code=code, rets=rets, cache={}, tiers=tiers)
    rows = read(watch, watch_dir)
    if opens_at and not any(r["kind"] == "window_open" for _raw, r in rows):
        written.append(append(watch, {"kind": "window_open", "opens_at_session": opens_at},
                              spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code))
    books, last = latest_books(read(watch, watch_dir))
    rule_state = last["rule_state"]
    used = last["data"]["nav_panel"]
    last_session = pd.Timestamp(last["session"])
    if last_session not in snap.dates or int(snap.dates.get_loc(last_session)) != last["session_index"]:
        raise WatchError("the snapshot disagrees with the log about the last logged session")
    rows = read(watch, watch_dir)
    prev = hashlib.sha256(rows[-1][0]).hexdigest()
    for session in snap.dates[snap.dates > last_session]:
        fetched, sha = vintage_for(rows, _next_session(snap, session))
        panel = panel_of(sha)
        if sha != used:
            revised = nav_revisions(spec, panel_of(used), panel, rule_state)
            if revised:
                written.append(append(watch, {"kind": "nav_revision", "session": str(session.date()),
                                              "from": used, "to": sha, "observations": revised},
                                      spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code,
                                      prev_sha256=prev))
                prev = line_sha256(written[-1])
            used = sha
        index = int(snap.dates.get_loc(session))
        rule_state = advance_rule_state(spec, rule_state, panel, session)
        decided = domain_decisions(spec, rule_state, snap, session, index)
        t = run.begin(params={"watch": watch, "spec_hash": spec_hash, "kind": "session",
                              "session": str(session.date())},
                      data={"snapshot": snap.sha, "nav_panel": sha})
        res = evaluate_session(spec, books, snap, session, index, rets=rets, tiers=tiers, decided=decided)
        act = combine(spec, res)
        t.complete(metrics={"active_1x": act["1x"]["active"]},
                   returns=pd.Series([act["1x"]["active"]], index=pd.DatetimeIndex([session])))
        books = {n: v["book"] for n, v in res.items()}
        mod = _rule_module(spec)
        written.append(append(watch, {
            "kind": "session", "session": str(session.date()), "session_index": index,
            "catch_up": bool(session < snap.dates[-1]),
            "data": {"snapshot": snap.sha, "nav_panel": sha},
            "vintage": {"nav_panel": sha, "fetched_at": fetched.isoformat() + "Z"},
            "inputs_sha256": asset_returns_sha256(snap, session, assets),
            "nav_inputs_sha256": nav_inputs_sha256(spec, panel, session),
            "rule_state": rule_state,
            "read_states": {tr: mod.read_state(rule_state[tr], session) for tr in rule_state},
            "returns": {n: {"return": v["return"], "cost": v["cost"]} for n, v in sorted(res.items())},
            "active": act, "books": _books_json(books)},
            spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code, prev_sha256=prev))
        prev = line_sha256(written[-1])
    return written


# ── a domain watch's report (computed from the log and the private snapshot) ──────
def window_sessions(rows) -> list[dict]:
    opened = next((r["opens_at_session"] for _b, r in rows if r["kind"] == "window_open"), None)
    return [r for _b, r in rows if r["kind"] == "session" and opened and r["session"] >= opened]


def legs_and_episodes(spec: Mapping, rows, snap: daily_data.Snapshot) -> dict:
    """The corroboration conditions' legs and episodes, exactly as
    tools/metal_trust_report.py defines them: the held state is the mean of the last 21
    lagged read states; a pair's contribution is (1/pairs)(held - 0.5)(r_trust - r_ETF),
    gross; the long leg sums it where held > 0.5. An episode is a departure from neutral of
    the CARRIED state inside the window (the carried-in state is not one; a staleness
    neutral is a read state, so it never makes a re-departure)."""
    pairs = [tuple(x) for x in rule_point(spec, "tilt")["params"]["pairs"]]
    share = 1.0 / len(pairs)
    sess = [r for _b, r in rows if r["kind"] == "session"]
    inside = {r["session"] for r in window_sessions(rows)}
    if not sess:
        return {"long_leg": 0.0, "short_leg": 0.0, "episodes": 0, "sessions": 0}
    states = pd.DataFrame({pd.Timestamp(r["session"]): r["read_states"] for r in sess}).T.sort_index()
    held = states.shift(1).rolling(MONTH, min_periods=1).mean()
    rets = snap.returns()
    total = (1 + rets.night) * (1 + rets.day) - 1
    long_leg = short_leg = 0.0
    window = [pd.Timestamp(d) for d in sorted(inside)]
    per_pair = {}
    for trust, etf in pairs:
        h = held[trust].reindex(window)
        spread = (total[trust] - total[etf]).reindex(window)
        c = share * (h - NEUTRAL_STATE) * spread
        long_leg += float(c[h > NEUTRAL_STATE].sum())
        short_leg += float(c[h < NEUTRAL_STATE].sum())
        per_pair[trust] = float(c.sum())
    episodes = 0
    for trust, _etf in pairs:
        prev = None
        for _b, r in rows:
            if r["kind"] not in ("genesis", "session"):
                continue
            cur = r["rule_state"][trust]["state"]
            if r["kind"] == "session" and r["session"] in inside and prev == NEUTRAL_STATE and cur != NEUTRAL_STATE:
                episodes += 1
            prev = cur
    return {"long_leg": long_leg, "short_leg": short_leg, "per_pair": per_pair, "episodes": episodes,
            "sessions": len(window)}


NEUTRAL_STATE = 0.5
ATM_SHELF_MONTHS = 25


def atm_windows(filings: list[dict], *, shelf_months: int = ATM_SHELF_MONTHS) -> list[tuple[str, str]]:
    """At-the-market offering windows from SEC filings ({form, filed}): each prospectus
    supplement (``SUPPL`` or ``424B*``) opens one, which lasts until the shelf it
    supplements expires: the latest ``F-10`` or ``F-10/A`` filed before it, plus 25 months
    (under MJDS the F-10 is the shelf). A supplement with no shelf before it opens none."""
    shelves = sorted(f["filed"] for f in filings if f["form"] in ("F-10", "F-10/A"))
    out = []
    for f in sorted(filings, key=lambda x: x["filed"]):
        if not (f["form"] == "SUPPL" or f["form"].startswith("424B")):
            continue
        before = [s for s in shelves if s <= f["filed"]]
        if not before:
            continue
        end = (pd.Timestamp(before[-1]) + pd.DateOffset(months=shelf_months)).date().isoformat()
        if end > f["filed"]:
            out.append((f["filed"], end))
    return out


def issuance_split(rows, windows: list[tuple[str, str]]) -> dict:
    """The window's active split into sessions inside and outside the offering windows;
    'degenerate' when fewer than 10% or more than 90% of sessions are inside."""
    sess = window_sessions(rows)
    if not sess:
        return {"sessions": 0}
    act = pd.Series({pd.Timestamp(r["session"]): r["active"]["1x"]["active"] for r in sess}).sort_index()
    inside = pd.Series(False, index=act.index)
    for a, b in windows:
        inside |= (act.index >= pd.Timestamp(a)) & (act.index <= pd.Timestamp(b))
    share = float(inside.mean())

    def stats_of(x):
        sd = float(x.std(ddof=1)) if len(x) > 1 else 0.0
        return {"sessions": int(len(x)), "mean_ann": float(x.mean() * 252) if len(x) else None,
                "sharpe": float(x.mean() / sd * math.sqrt(252)) if sd > 0 else None}
    return {"inside_share": share, "degenerate": not (0.1 <= share <= 0.9),
            "inside": stats_of(act[inside]), "outside": stats_of(act[~inside])}
