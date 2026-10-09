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
LINE_KINDS = ("genesis", "window_open", "session", "correction", "evaluator_change", "void")
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


def validate(spec: Mapping) -> list[str]:
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

    def to_json(self) -> dict:
        return {"state": self.state.to_json(),
                "pending": {str(k): dict(v) for k, v in sorted(self.pending.items())}}

    @classmethod
    def from_json(cls, d) -> "Book":
        return cls(state=BookState.from_json(d["state"]),
                   pending={int(k): {a: float(w) for a, w in v.items()} for k, v in d["pending"].items()})


def book_names(spec: Mapping) -> list[tuple[str, tuple, str, float]]:
    """(name, pair, kind, cost multiple) for every book of the watch."""
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
        out.append(Tranche(open_orders=orders, close_orders=pd.DataFrame()))
    return out


@_counted_evaluator
def evaluate_session(spec: Mapping, books: Mapping[str, Book], snap: daily_data.Snapshot,
                     session: pd.Timestamp, index: int, *, rets=None, cache: dict | None = None) -> dict:
    """One session for every book, continued from its logged state and pending orders.
    A counted evaluation: the caller holds a begun trial. ``rets`` and ``cache`` (target
    weights per (pair, kind)) let a run compute each once; the result does not depend on
    them."""
    pos = snap.dates.get_loc(session)
    prev = snap.dates[pos - 1]
    rets = rets if rets is not None else snap.returns()
    cache = {} if cache is None else cache
    out = {}
    for name, pair, kind, mult in book_names(spec):
        book = books[name]
        res = evaluate_daily(_tranches_for(book, prev, snap.assets), snap, start=session, end=session,
                             cost_multiple=mult, initial=book.state, rets=rets)
        key = (tuple(pair), kind)
        if key not in cache:
            cache[key] = targets(snap, pair, kind)
        nxt = Book(state=res.final, pending=decisions(snap, pair, kind, session, index, cache[key]))
        out[name] = {"return": float(res.returns.iloc[0]), "cost": float(res.cost_paid), "book": nxt}
    return out


def combine(spec: Mapping, results: Mapping[str, dict]) -> dict:
    """Pair actives (tilt minus benchmark) and their pre-stated weighted sum, per cost level."""
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
    opened, series, stressed = None, {}, {}
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
            return [{"verdict": "VOID", "reason": r["reason"]}]
    if not opened or not series:
        return []
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
                          "evaluator_sha256": evaluator_sha256()},
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
    now_sha = current_evaluator or evaluator_sha256()
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
                 rets=None, cache=None) -> list[dict]:
    """Re-check the last CORRECTION_LOOKBACK logged sessions' inputs against ``snap``; a
    changed input (a late-booked distribution, a vendor fix) gets a correction line with
    the active delta, recomputed from the logged state before that session."""
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
        t = run.begin(params={"watch": watch, "spec_hash": spec_hash, "kind": "correction",
                              "session": r["session"]}, data={"snapshot": snap.sha})
        res = evaluate_session(spec, books, snap, session, r["session_index"], rets=rets, cache=cache)
        act = combine(spec, res)
        t.complete(metrics={"active_1x": act["1x"]["active"]})
        delta = {k: act[k]["active"] - r["active"][k]["active"] for k in act}
        for _raw, rr in rows:          # earlier corrections of the same session already booked
            if rr["kind"] == "correction" and rr["session"] == r["session"]:
                delta = {k: delta[k] - rr["delta"][k] for k in delta}
        written.append(append(watch, {"kind": "correction", "session": r["session"],
                                      "inputs_sha256": fresh, "delta": delta,
                                      "data": {"snapshot": snap.sha}},
                              spec_hash=spec_hash, watch_dir=watch_dir, now=now, code=code))
        rows = read(watch, watch_dir)
    return written
