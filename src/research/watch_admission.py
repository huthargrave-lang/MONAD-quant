"""
MONAD Quant — the forward-evidence route's admission chain for a forward watch
(``admit_watch``): FORWARD_ROUTE_PROPOSAL.md Q1-Q5, ratified 2026-10-29 (RESEARCH_WEB.md
D297801), exactly as frozen in ``docs/research/forward_watch/policy/route.2.json`` (its
``test``, ``de_admission`` and ``build`` blocks).

A watch is not a preregistration, so nothing here calls ``prereg.load``. The chain reads
the watch's frozen spec, its chained log, the freeze ledger, the governing policy link and
git, and decides with the watch's own engine (``forward_watch.decide``, unchanged). This
module is deliberately NOT one of any spec's ``evaluator_sources``: admission reads a
record, it never computes a return, so changing it re-attests nothing.

The stages, in the ratified order (``route.2.json`` ``build.stages``):

  registration   the spec reached the deploy branch on its first-parent history and is
                 byte-identical there
  ledger         the watch has a freeze-ledger row on the deploy branch; its alpha share
                 (ordinals come from the ledger, never from git)
  chain          the log prefix verifies (``forward_watch.verify``'s rules, on the prefix)
  evaluator      every line that computed a return ran on the evaluator pinned at that point
                 of the log, recomputed from git objects at the line's ``code.sha``; an
                 attestation (``evaluator_change``) counts only from a commit on the deploy
                 branch
  code           the tree is clean at a known commit
  refutations    no objection open (BLOCK); none upheld (REJECT); an ADMIT needs at least one
                 objection filed, all refuted
  witness        the log prefix is a byte-prefix of the deploy branch's log; ``witnessed_sha``
  window         the window_open line names the first NYSE session after the spec reached the
                 deploy branch
  sequential     the anniversary reading on the prefix that settles it: the route boundary
                 ln((1 - beta)/alpha_i) before admission; after it, the CUSUM on year k's
                 own data and the close boundary on the full record
  corroboration  every corroboration condition of the spec at the crossing
  void           no VOID line

Records (``route.2.json`` ``build.records``): one per anniversary, ``watch-aNN.json``, plus
``watch-void.json`` for a VOID, under ``docs/research/verdicts/<ID>/``, each written once
(O_EXCL). The latest governs; an upheld objection governs at once. Verdicts: CONTINUE,
ADMIT, ADMITTED (an anniversary after an ADMIT that does not de-admit), DE-ADMIT, CLOSED,
VOID, REJECT. BLOCKED and PENDING are never written: an anniversary's slot holds only the
decision the frozen test makes, so a blocked run cannot spend it. CLOSED, VOID, DE-ADMIT
and REJECT are terminal: nothing is written after them, and a de-admitted watch is never
re-admitted on the same record (Q3: "never sized up later on the same record").

Readings of this implementation where the frozen text is silent, stated once:
  * the CUSUM alarms when W_k >= h (h = 2.0), with W = 0 at the admitting anniversary
    (the most favourable start, as the consensus simulated it);
  * after an ADMIT, the watch's own terminal close (the close boundary, or H366201's
    long-leg consequence at a promote crossing) de-admits, as does a VOID;
  * an objection upheld at any time REJECTS the watch on the route (refutations.py: "the
    gate REJECTS on it"); after an ADMIT that ends the admission.

The verifier (``verify_record``) recomputes every derivable field of a record from the log
prefix it pins, so a hand-written ADMIT cannot verify (red-team 7b). One input cannot be
recomputed where the private store is absent: a domain watch's long leg, which needs vendor
returns that are never committed (docs/research/data/README.md). There the repository's
three-valued rule applies (tests/_private_store.py): absent -> the record's stated leg is
replayed and the check is reported as a NOTE (a problem with MONAD_REQUIRE_PRIVATE_STORE=1);
present -> recomputed; altered -> a problem. The episode count is always recomputed: it
reads only the log.

Sizing is NOT a stage (Q5 round 3): it is a separate record citing the ADMIT, due within
30 days of it (``route.2.json`` ``sizing``), built with the first ADMIT. Nothing here trades.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Mapping

import pandas as pd

from src.research import forward_watch as fw
from src.research import refutations, trials
from src.research.trials import REPO, canonical_json

PROFILE = "forward_watch"
SCHEMA = 1
PRODUCER = "tools/admit.py --watch"
VERDICT_REL = Path("docs/research/verdicts")
VERDICT_DIR = REPO / VERDICT_REL
#: The CUSUM alarm level, ``route.2.json`` ``de_admission.cusum`` ("alarm at h = 2.0";
#: pinned to that text by tests/test_watch_admission.py).
CUSUM_H = 2.0

PASS, FAIL, BLOCK, SKIP, NOT_MET = "pass", "fail", "block", "skip", "not_met"
ADMIT, ADMITTED, DE_ADMIT, CONTINUE, CLOSED, VOID, REJECT = (
    "ADMIT", "ADMITTED", "DE-ADMIT", "CONTINUE", "CLOSED", "VOID", "REJECT")
BLOCKED, PENDING = "BLOCKED", "PENDING"
#: The verdicts a record can carry; BLOCKED and PENDING never reach the disk.
WRITTEN = (CONTINUE, ADMIT, ADMITTED, DE_ADMIT, CLOSED, VOID, REJECT)
TERMINAL = (DE_ADMIT, CLOSED, VOID, REJECT)
#: The ratified stage chain (``route.2.json`` ``build.stages``, by its first word).
STAGES = ("registration", "ledger", "chain", "evaluator", "code", "refutations", "witness",
          "window", "sequential", "corroboration", "void")
PROCESS = STAGES[:8]
VOID_EVENT = "void"
#: Floats a verifier recomputes are compared to this tolerance (the arithmetic is the
#: engine's own and deterministic; the tolerance only absorbs a library's last bits).
TOLERANCE = 1e-9


class WatchAdmissionError(RuntimeError):
    """The watch cannot be evaluated on the route as it stands."""


@dataclass
class Stage:
    name: str
    outcome: str
    detail: str
    data: dict = field(default_factory=dict)


# ── where the chain reads from ───────────────────────────────────────────────
def _deploy_ref(repo: Path = REPO) -> str:
    """The fully qualified remote-tracking ref of the deploy branch (a LOCAL branch named
    "origin/development" cannot shadow it; tools/admit.py ``_deploy_ref``)."""
    try:
        branch = json.loads((repo / "context_map.json").read_text(encoding="utf-8"))["deploy_branch"]
    except (OSError, ValueError, KeyError):
        branch = "development"
    return f"refs/remotes/origin/{branch}"


ConditionsAt = Callable[[Mapping, list, pd.Timestamp], dict]


@dataclass
class Env:
    """Everything the chain reads besides the record itself. The defaults are the
    repository's own; tests point them at scratch directories and a scratch git repo."""
    repo: Path = REPO
    ref: str | None = None
    watch_dir: Path | None = None
    policy_dir: Path | None = None
    ledger_path: Path | None = None
    refutations_dir: Path | None = None
    verdict_dir: Path | None = None
    code_state: Callable[[], dict] = trials.code_state
    #: (spec, prefix rows, cut) -> a domain watch's corroboration at the cut. Default: from
    #: the private snapshot the prefix's last session line names.
    conditions_at: ConditionsAt | None = None
    #: sha -> "present" | "absent" | "altered", for the verifier's private-store rule.
    snapshot_status: Callable[[str], str] | None = None
    load_snapshot: Callable | None = None
    require_private: bool | None = None

    def __post_init__(self):
        self.repo = Path(self.repo)
        self.ref = self.ref or _deploy_ref(self.repo)
        self.watch_dir = Path(self.watch_dir) if self.watch_dir is not None else fw.WATCH_DIR
        self.policy_dir = Path(self.policy_dir) if self.policy_dir is not None else fw.POLICY_DIR
        self.ledger_path = Path(self.ledger_path) if self.ledger_path is not None else fw.LEDGER
        self.verdict_dir = Path(self.verdict_dir) if self.verdict_dir is not None else VERDICT_DIR
        if self.require_private is None:
            self.require_private = os.environ.get("MONAD_REQUIRE_PRIVATE_STORE") == "1"

    def rel(self, path: Path) -> str:
        return Path(path).resolve().relative_to(self.repo.resolve()).as_posix()

    def ledger(self) -> list[dict]:
        return fw.freeze_ledger(self.ledger_path)

    def git(self, *args) -> "trials.subprocess.CompletedProcess":
        return trials._git(self.repo, *args)


def _ref_sha(env: Env) -> str | None:
    r = env.git("rev-parse", "--verify", "--quiet", env.ref)
    return (r.stdout.decode().strip() or None) if r.returncode == 0 else None


def _blob(env: Env, rev: str, rel: str) -> bytes | None:
    r = env.git("show", f"{rev}:{rel}")
    return r.stdout if r.returncode == 0 else None


def _is_ancestor(env: Env, sha: str, rev: str | None = None) -> bool:
    return env.git("merge-base", "--is-ancestor", sha, rev or env.ref).returncode == 0


def first_parent_arrival(env: Env, rel: str) -> tuple[str, pd.Timestamp] | None:
    """(commit, UTC time) of the FIRST-PARENT commit of the deploy ref that added ``rel``:
    the merge commit when it arrived through a merge (tools/forward_watch.py ``reached``)."""
    r = env.git("log", "--first-parent", env.ref, "--diff-filter=A", "--format=%H %cI", "--", rel)
    lines = [ln for ln in r.stdout.decode().splitlines() if ln.strip()] if r.returncode == 0 else []
    if not lines:
        return None
    sha, at = lines[-1].split()
    return sha, pd.Timestamp(at).tz_convert("UTC").tz_localize(None)


def evaluator_at(env: Env, commit: str, sources) -> str | None:
    """``forward_watch.evaluator_sha256`` of ``sources`` as committed at ``commit`` (None
    when the commit or one of the sources is not in this repository's objects)."""
    h = hashlib.sha256()
    for rel in sources:
        blob = _blob(env, commit, rel)
        if blob is None:
            return None
        h.update(rel.encode() + b"\0" + blob + b"\0")
    return h.hexdigest()


def _first_session_after(day) -> str:
    from src.research.nyse_calendar import is_session
    d = pd.Timestamp(day).normalize() + pd.Timedelta(days=1)
    while not is_session(d.date()):
        d += pd.Timedelta(days=1)
    return str(d.date())


# ── the route ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Route:
    """One watch's frozen test on the governing policy link."""
    watch: str
    ordinal: int
    cohort: str
    gamma: Fraction
    alpha: float
    alpha_i: float
    beta: float
    theta: float
    upper: float
    own_upper: float
    lower: float
    first_decisive: int
    cusum_h: float
    policy_path: str
    policy_sha256: str

    def to_json(self) -> dict:
        d = asdict(self)
        d["gamma"] = f"{self.gamma.numerator}/{self.gamma.denominator}"
        return d


def governing_link(policy_dir: Path | None = None) -> tuple[Path, dict]:
    """(file, policy) of the governing link; ``forward_watch.policy_chain`` validates every
    supersession link on the way."""
    policy_dir = Path(policy_dir) if policy_dir is not None else fw.POLICY_DIR
    chain = fw.policy_chain(policy_dir)
    name = "route.json" if len(chain) == 1 else f"route.{len(chain)}.json"
    return policy_dir / name, chain[-1]


def route_for(spec: Mapping, watch: str, *, ledger: list[dict] | None = None,
              policy_dir: Path | None = None, link: tuple[Path, dict] | None = None) -> Route:
    path, policy = link or governing_link(policy_dir)
    if policy.get("schema", 1) < 2:
        raise WatchAdmissionError("the governing policy (schema 1) spends no alpha per watch")
    entry = fw.ledger_entry(watch, ledger)
    g = fw.gamma(watch, ledger=ledger, policy=policy)
    ev = spec["evaluation"]
    a, b, th = ev["alpha"], ev["beta"], ev["theta1"]
    a_i = float(a * g)
    first = fw.first_decisive_anniversary(spec)
    pinned = (policy.get("test") or {}).get("first_decisive_anniversary") or {}
    if watch in pinned and int(pinned[watch]) != first:
        raise WatchAdmissionError(f"{watch}: the spec reads first decisive anniversary {first}, "
                                  f"the policy pins {pinned[watch]}")
    return Route(watch=watch, ordinal=int(entry["ordinal"]), cohort=str(entry["cohort"]), gamma=g,
                 alpha=float(a), alpha_i=a_i, beta=float(b), theta=float(th),
                 upper=math.log((1 - b) / a_i), own_upper=math.log((1 - b) / a),
                 lower=math.log(b / (1 - a)), first_decisive=first, cusum_h=CUSUM_H,
                 policy_path=(fw.POLICY_REL / path.name).as_posix(),
                 policy_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


# ── anniversaries, pinned by log position ────────────────────────────────────
@dataclass(frozen=True)
class Anniversary:
    k: int
    cut: pd.Timestamp
    lines: int          # the prefix rows[:lines] settles it, and no shorter one does


def window_opened(rows) -> tuple[str | None, int | None]:
    for i, (_raw, r) in enumerate(rows):
        if r.get("kind") == "window_open":
            return r["opens_at_session"], i
    return None, None


def settled_anniversaries(rows) -> list[Anniversary]:
    """Every settled anniversary and the shortest prefix that settles it, by the rule
    ``forward_watch.decide`` applies: anniversary k settles when the log holds the 64th
    session line past its cut (``ANNIVERSARY_SETTLE`` + 1), in log order, before any VOID.
    A position in the log, so it never moves when later lines are appended."""
    opened, wo = window_opened(rows)
    if opened is None:
        return []
    sess = []
    for i, (_raw, r) in enumerate(rows):
        if r.get("kind") == "void":
            break
        if r.get("kind") == "session" and r["session"] >= opened:
            sess.append((i, pd.Timestamp(r["session"])))
    start, out, k = pd.Timestamp(opened), [], 1
    while True:
        cut = start + pd.DateOffset(years=k)
        if not any(d <= cut for _i, d in sess):
            break
        after = [i for i, d in sess if d > cut]
        if len(after) <= fw.ANNIVERSARY_SETTLE:
            break
        out.append(Anniversary(k, cut, max(after[fw.ANNIVERSARY_SETTLE], wo) + 1))
        k += 1
    return out


def year_reading(spec: Mapping, prefix, opened: str, k: int, theta: float) -> dict:
    """Year k's OWN reading (Q4 round 3): the sessions in (cut_{k-1}, cut_k] with the
    corrections booked before the anniversary settled, scored alone. dLLR_k = t_k (theta S_k
    - theta^2/2). Its Sharpe is year k's own, so a volatility shift alone moves nothing,
    where a difference of full-record LLRs would revalue the past whenever sigma-hat moves."""
    start = pd.Timestamp(opened)
    lo = start + pd.DateOffset(years=k - 1)
    hi = start + pd.DateOffset(years=k)
    series, after = {}, 0
    for _raw, r in prefix:
        kind = r.get("kind")
        if kind == "void":
            break
        if kind == "session":
            if r["session"] < opened:
                continue
            d = pd.Timestamp(r["session"])
            if d > hi:
                after += 1
                if after > fw.ANNIVERSARY_SETTLE:
                    break
            elif k == 1 or d > lo:
                series[r["session"]] = r["active"]["1x"]["active"]
        elif kind == "correction" and r["session"] in series:
            series[r["session"]] += r["delta"]["1x"]
    s = pd.Series(series, dtype=float).sort_index()
    t = len(s) / 252
    sd = float(s.std(ddof=1)) if len(s) > 1 else 0.0
    sh = float(s.mean() / sd * math.sqrt(252)) if sd > 0 else 0.0
    return {"anniversary": k, "from_after": str(lo.date()) if k > 1 else None,
            "through": str(hi.date()), "sessions": int(len(s)), "years": t, "sharpe": sh,
            "dllr": t * (theta * sh - theta ** 2 / 2)}


# ── a domain watch's corroboration ───────────────────────────────────────────
def _last_snapshot(prefix) -> str:
    for _raw, r in reversed(prefix):
        if r.get("kind") == "session":
            return r["data"]["snapshot"]
    raise WatchAdmissionError("the prefix has no session line naming a snapshot")


def private_conditions(load_snapshot: Callable | None = None) -> ConditionsAt:
    """A domain watch's conditions at a cut (``forward_watch.domain_conditions``), on the
    private snapshot the settling prefix's last session line names, so anniversary k's
    conditions are pinned to the data that settled it."""
    def at(spec, prefix, cut):
        from src.research import daily_data
        sha = _last_snapshot(prefix)
        snap = (load_snapshot or daily_data.load_snapshot)(sha)
        return {**fw.domain_conditions(spec, prefix, snap)(cut), "snapshot": sha}
    return at


class _WithheldReturns:
    """A snapshot stand-in with no observations: ``legs_and_episodes`` then reads only the
    log (episodes, window sessions); its legs come out 0. What the verifier can recompute
    where the private store is absent."""
    def __init__(self, assets):
        self.assets = tuple(assets)

    def returns(self):
        empty = pd.DataFrame(columns=list(self.assets), dtype=float)
        return SimpleNamespace(night=empty, day=empty)


def log_only_conditions(spec: Mapping, prefix, cut: pd.Timestamp) -> dict:
    """The parts of a domain watch's conditions the log alone decides: the episode count,
    the window sessions, and the frozen wording of both consequences."""
    return fw.domain_conditions(spec, prefix, _WithheldReturns(spec["domain_rule"]["assets"]))(cut)


def corroboration_checks(spec: Mapping, reading: Mapping) -> list[dict]:
    """Every corroboration condition of the spec at an anniversary, and whether it holds."""
    out = [{"condition": "the 2x-cost Sharpe > 0" if not fw.is_domain(spec) else "the 2x-cost active Sharpe > 0",
            "holds": reading["sharpe_stressed"] > 0}]
    if fw.is_domain(spec):
        cond = reading.get("conditions") or {}
        legs = cond.get("legs") or {}
        need = fw.episode_threshold(spec)
        out = [{"condition": "the promote boundary is crossed", "holds": bool(reading["own_crossed"])}] + out
        if legs:
            out += [{"condition": "the long leg's summed contribution > 0", "holds": legs["long_leg"] > 0,
                     "value": legs["long_leg"]},
                    {"condition": f"at least {need} forward episodes", "holds": legs["episodes"] >= need,
                     "value": legs["episodes"]}]
        else:
            out += [{"condition": "the long leg's summed contribution > 0", "holds": None},
                    {"condition": f"at least {need} forward episodes", "holds": None}]
    return out


# ── the route timeline ───────────────────────────────────────────────────────
def timeline(spec: Mapping, rows, route: Route, *, conditions_at: ConditionsAt | None = None) -> list[dict]:
    """The route's reading at every settled anniversary, in order, up to the first terminal
    one. Reading k is ``forward_watch.decide`` on the prefix that settles k, a domain watch's
    conditions at each cut pinned to the prefix that settled THAT cut; so reading k is the
    same whichever longer log computes it, and a correction booked later changes nothing."""
    anns = settled_anniversaries(rows)
    domain = fw.is_domain(spec)
    if domain and conditions_at is None and anns:
        raise WatchAdmissionError("a domain watch's corroboration needs its conditions (private snapshot)")
    opened, _wo = window_opened(rows)
    by_cut = {a.cut: a for a in anns}
    pinned: dict = {}

    def cond(cut):
        if cut not in pinned:
            pinned[cut] = conditions_at(spec, rows[:by_cut[cut].lines], cut)
        return pinned[cut]

    out, state, w = [], "open", None
    for a in anns:
        reps = [r for r in fw.decide(spec, rows[:a.lines], conditions=cond if domain else None)
                if "anniversary" in r]
        if len(reps) < a.k:
            raise WatchAdmissionError(f"anniversary {a.k} settles at line {a.lines} but decide reads "
                                      f"{len(reps)} anniversaries there")
        rep = reps[a.k - 1]
        llr, sh2 = rep["llr"], rep["sharpe_stressed"]
        own_crossed = bool(rep["decisive"] and llr >= route.own_upper and sh2 > 0)
        route_crossed = bool(rep["decisive"] and llr >= route.upper)
        conditions = rep.get("conditions")
        year = None
        if state == "open":
            if not rep["decisive"]:
                verdict = CONTINUE
                reason = (f"anniversary {a.k} decides nothing (the spec's first decisive anniversary is "
                          f"{route.first_decisive})")
            elif rep["verdict"] == "close":
                verdict = CLOSED
                reason = ((conditions or {}).get("close") if own_crossed and (conditions or {}).get("close")
                          else f"LLR {llr:.4f} <= the close boundary {route.lower:.4f}")
            elif rep["verdict"] == "promote" and route_crossed:
                verdict, state, w = ADMIT, "admitted", 0.0
                reason = (f"LLR {llr:.4f} >= the route boundary {route.upper:.4f} (alpha_i "
                          f"{route.alpha_i:.6f}) with every corroboration condition")
            elif rep["verdict"] == "promote":
                verdict = CONTINUE
                reason = (f"the spec's own promote boundary is crossed (LLR {llr:.4f} >= {route.own_upper:.4f}): "
                          f"non-terminal; the route needs {route.upper:.4f}")
            elif own_crossed and (conditions or {}).get("continue"):
                verdict = CONTINUE
                reason = "the promote boundary is crossed but " + "; ".join(conditions["continue"])
            else:
                verdict = CONTINUE
                reason = f"LLR {llr:.4f} inside ({route.lower:.4f}, {route.upper:.4f})"
        else:
            year = year_reading(spec, rows[:a.lines], opened, a.k, route.theta)
            w = max(0.0, w - year["dllr"])
            if rep["verdict"] == "close":
                verdict, state = DE_ADMIT, "closed"
                reason = ("the watch closed: " + ((conditions or {}).get("close") if own_crossed and (conditions or {}).get("close")
                                                  else f"LLR {llr:.4f} <= the close boundary {route.lower:.4f}"))
            elif w >= route.cusum_h:
                verdict, state = DE_ADMIT, "closed"
                reason = f"CUSUM W {w:.4f} >= h {route.cusum_h:g} (year {a.k}: dLLR {year['dllr']:.4f})"
            else:
                verdict = ADMITTED
                reason = f"CUSUM W {w:.4f} < h {route.cusum_h:g}; LLR {llr:.4f} above the close boundary"
        reading = {"anniversary": a.k, "as_of": rep["as_of"], "lines": a.lines, "years": rep["years"],
                   "sharpe": rep["sharpe"], "sharpe_stressed": sh2, "llr": llr, "decisive": bool(rep["decisive"]),
                   "own_verdict": rep["verdict"], "own_crossed": own_crossed, "route_crossed": route_crossed,
                   "conditions": conditions, "year": year,
                   "cusum": w if state != "open" else None,      # from the ADMIT on (W = 0 there)
                   "route": verdict, "reason": reason}
        out.append(reading)
        if verdict in TERMINAL:
            break
    return out


def state_after(readings) -> str:
    """"open", "admitted" or the terminal verdict after these readings."""
    state = "open"
    for r in readings:
        if r["route"] in (ADMIT, ADMITTED):
            state = "admitted"
        elif r["route"] in TERMINAL:
            return r["route"]
    return state


# ── stages ───────────────────────────────────────────────────────────────────
def _prefix_bytes(raws) -> bytes:
    return b"".join(raw + b"\n" for raw in raws)


def stage_registration(env: Env, watch: str, spec_bytes: bytes) -> tuple[Stage, pd.Timestamp | None]:
    rel = env.rel(fw.spec_path(watch, env.watch_dir))
    if _ref_sha(env) is None:
        return Stage("registration", BLOCK, f"{env.ref} is not available to witness the registration"), None
    hit = first_parent_arrival(env, rel)
    if hit is None:
        return Stage("registration", BLOCK, f"{rel} is not on {env.ref}'s first-parent history"), None
    if _blob(env, env.ref, rel) != spec_bytes:
        return Stage("registration", BLOCK, f"{rel} on {env.ref} is not the local spec's bytes"), None
    commit, at = hit
    return Stage("registration", PASS, f"{rel} reached {env.ref} in {commit[:12]} at {at.isoformat()}Z",
                 {"commit": commit, "reached_at": at.isoformat() + "Z",
                  "spec_sha256": hashlib.sha256(spec_bytes).hexdigest()}), at


def stage_ledger(env: Env, watch: str, spec_hash: str, route: Route) -> Stage:
    problems = fw.verify_policy(env.policy_dir, env.ledger_path, env.watch_dir)
    try:
        row = fw.ledger_entry(watch, env.ledger())
    except fw.WatchError as exc:
        return Stage("ledger", BLOCK, str(exc))
    if row.get("spec_sha256") and row["spec_sha256"] != spec_hash:
        problems.append(f"the ledger's spec_sha256 {row['spec_sha256'][:12]} is not the spec's {spec_hash[:12]}")
    rel = env.rel(env.ledger_path)
    on_ref = _blob(env, env.ref, rel)
    local = env.ledger_path.read_bytes()
    if on_ref is None:
        problems.append(f"{rel} is not on {env.ref}")
    elif not local.startswith(on_ref):
        problems.append(f"the local freeze ledger does not extend {env.ref}'s (append-only)")
    else:
        listed = [json.loads(ln) for ln in on_ref.decode("utf-8").splitlines() if ln.strip()]
        if not any(r.get("watch") == watch and r.get("ordinal") == route.ordinal for r in listed):
            problems.append(f"{watch}'s row (ordinal {route.ordinal}) is not on {env.ref}'s ledger")
    data = {"row": row, "ordinal": route.ordinal, "cohort": route.cohort,
            "gamma": route.to_json()["gamma"], "alpha_i": route.alpha_i}
    if problems:
        return Stage("ledger", BLOCK, "; ".join(problems), data)
    return Stage("ledger", PASS, f"ordinal {route.ordinal} ({route.cohort}): gamma {data['gamma']}, "
                 f"alpha_i {route.alpha_i:.6f}", data)


def stage_chain(watch: str, spec_bytes: bytes, prefix: bytes) -> Stage:
    """``forward_watch.verify`` on exactly the prefix (a scratch copy: the same rules)."""
    with tempfile.TemporaryDirectory() as td:
        Path(td, f"{watch}.json").write_bytes(spec_bytes)
        Path(td, f"{watch}.jsonl").write_bytes(prefix)
        problems = fw.verify(watch, Path(td))
    n = prefix.count(b"\n")
    if problems:
        return Stage("chain", BLOCK, "; ".join(problems[:3]), {"problems": problems})
    return Stage("chain", PASS, f"{n} line(s) chain from the genesis", {"lines": n})


def stage_evaluator(env: Env, spec: Mapping, prefix_rows) -> Stage:
    """Every line that computed a return (genesis, session, correction) ran on the
    evaluator pinned at that point of the log, recomputed from git objects at the line's
    ``code.sha``; an ``evaluator_change`` attests the evaluator its own commit holds, and
    counts only from a commit on the deploy branch."""
    pinned, sources = spec["evaluator_sha256"], tuple(spec["evaluator_sources"])
    problems, attested, checked, memo = [], [], 0, {}
    for i, (_raw, r) in enumerate(prefix_rows, 1):
        kind = r.get("kind")
        if kind not in ("genesis", "session", "correction", "evaluator_change"):
            continue
        code = r.get("code") or {}
        sha = code.get("sha")
        if not sha or code.get("dirty") is not False:
            problems.append(f"line {i} ({kind}): written on an unknown or modified tree")
            continue
        if sha not in memo:
            memo[sha] = evaluator_at(env, sha, sources)
        at = memo[sha]
        if at is None:
            problems.append(f"line {i} ({kind}): commit {sha[:12]} or a pinned source in it is not in "
                            f"this repository")
            continue
        if kind == "evaluator_change":
            if at != r.get("evaluator_sha256"):
                problems.append(f"line {i}: attests {str(r.get('evaluator_sha256'))[:12]} but commit "
                                f"{sha[:12]} holds {at[:12]}")
            elif not _is_ancestor(env, sha):
                problems.append(f"line {i}: the attestation at {sha[:12]} is not on {env.ref}")
            else:
                pinned = at
                attested.append({"line": i, "commit": sha, "evaluator_sha256": at})
            continue
        if kind == "genesis" and r.get("evaluator_sha256") not in (None, spec["evaluator_sha256"]):
            problems.append(f"line {i}: the genesis names evaluator {r['evaluator_sha256'][:12]}, the spec "
                            f"pins {spec['evaluator_sha256'][:12]}")
        if at != pinned:
            problems.append(f"line {i} ({kind} {r.get('session', '')}): ran on evaluator {at[:12]}, "
                            f"pinned {pinned[:12]}")
        checked += 1
    data = {"checked_lines": checked, "attestations": attested}
    if problems:
        return Stage("evaluator", BLOCK, "; ".join(problems[:3]) + (f" (+{len(problems) - 3} more)"
                                                                     if len(problems) > 3 else ""),
                     {**data, "problems": problems})
    return Stage("evaluator", PASS, f"{checked} computing line(s) ran on their pinned evaluator; "
                 f"{len(attested)} attestation(s) on {env.ref}", data)


def stage_code(cs: Mapping) -> Stage:
    if trials.committed_clean(cs):
        return Stage("code", PASS, f"clean at {cs['sha'][:12]}")
    return Stage("code", BLOCK, "the tree is dirty, unreadable or holds uncommitted data; admission "
                 "evidence must be replayable from a commit", {"code": dict(cs)})


def _status_of(entries) -> dict:
    """refutations.status over a given set of entries (the log as it stood at a time)."""
    answers = {e["resolves"]: e for e in entries if e["type"] == "resolution"}
    out = {"open": [], "upheld": [], "refuted": []}
    for e in entries:
        if e["type"] == "objection":
            a = answers.get(e["id"])
            out["open" if a is None else a["outcome"]].append(e)
    return out


def refutation_outcome(st: Mapping, *, admits: bool) -> str:
    if st["upheld"]:
        return FAIL
    if st["open"] or (admits and not st["refuted"]):
        return BLOCK
    return PASS if st["refuted"] else SKIP


def stage_refutations(env: Env, watch: str, *, admits: bool) -> Stage:
    st = refutations.status(watch, env.refutations_dir)
    if st["upheld"]:
        return Stage("refutations", FAIL, f"{len(st['upheld'])} objection(s) upheld",
                     {"upheld": [o["id"] for o in st["upheld"]]})
    if st["open"]:
        return Stage("refutations", BLOCK, f"{len(st['open'])} objection(s) unanswered",
                     {"open": [o["id"] for o in st["open"]]})
    if not st["refuted"]:
        if admits:
            return Stage("refutations", BLOCK, "an ADMIT needs at least one objection filed and refuted: "
                         "no refuter has examined this watch (tools/refute.py object)")
        return Stage("refutations", SKIP, "no objection filed; this record admits nothing")
    return Stage("refutations", PASS, f"{len(st['refuted'])} objection(s), all refuted",
                 {"refuted": [o["id"] for o in st["refuted"]]})


def stage_witness(env: Env, watch: str, prefix: bytes) -> tuple[Stage, str | None]:
    sha = _ref_sha(env)
    if sha is None:
        return Stage("witness", BLOCK, f"{env.ref} is not available to witness the log"), None
    rel = env.rel(fw.log_path(watch, env.watch_dir))
    blob = _blob(env, env.ref, rel)
    n = prefix.count(b"\n")
    if blob is None or not blob.startswith(prefix):
        return Stage("witness", BLOCK, f"the log prefix through line {n} is not on {env.ref}"), sha
    return Stage("witness", PASS, f"the log prefix through line {n} is on {env.ref} at {sha[:12]}",
                 {"witnessed_sha": sha}), sha


def stage_window(watch: str, rows, reached_at: pd.Timestamp | None, ledger_row: Mapping | None) -> Stage:
    opened, _wo = window_opened(rows)
    if reached_at is None:
        return Stage("window", BLOCK, "the window cannot be dated without the registration")
    expected = _first_session_after(reached_at)
    problems = []
    if opened is None:
        problems.append("the log has no window_open line")
    elif opened != expected:
        problems.append(f"the window_open line names {opened}; the first NYSE session after the spec "
                        f"reached the deploy branch ({reached_at.date()}) is {expected}")
    if ledger_row and ledger_row.get("window_opened") and ledger_row["window_opened"] != opened:
        problems.append(f"the ledger records window_opened {ledger_row['window_opened']}, the log {opened}")
    if problems:
        return Stage("window", BLOCK, "; ".join(problems))
    return Stage("window", PASS, f"opened {opened}, the first session after {reached_at.date()}",
                 {"opened": opened})


def decision_stages(spec: Mapping, reading: Mapping | None, *, void: Mapping | None) -> list[Stage]:
    """The sequential, corroboration and void stages of one record."""
    if void is not None:
        return [Stage("sequential", SKIP, "a VOID is not an anniversary reading"),
                Stage("corroboration", SKIP, "a VOID is not an anniversary reading"),
                Stage("void", NOT_MET, f"voided: {void['reason']}", dict(void))]
    r = reading
    seq_data = {k: r[k] for k in ("anniversary", "as_of", "lines", "years", "sharpe", "sharpe_stressed",
                                  "llr", "decisive", "own_verdict", "own_crossed", "route_crossed",
                                  "cusum", "year")}
    after = r["year"] is not None
    seq = Stage("sequential", PASS if r["route"] in (ADMIT, ADMITTED) else NOT_MET, r["reason"], seq_data)
    checks = corroboration_checks(spec, r)
    if after:
        corr = Stage("corroboration", SKIP, "not re-tested after an admission (Q4: the CUSUM, the close "
                     "boundary and a VOID are the only triggers)", {"checks": checks})
    elif not (r["route_crossed"] or (fw.is_domain(spec) and r["own_crossed"])):
        corr = Stage("corroboration", SKIP, "no boundary crossed at this anniversary: nothing to corroborate",
                     {"checks": checks})
    elif all(c["holds"] for c in checks):
        corr = Stage("corroboration", PASS, "every condition holds", {"checks": checks})
    else:
        failed = [c["condition"] for c in checks if not c["holds"]]
        corr = Stage("corroboration", NOT_MET, "not met: " + "; ".join(failed), {"checks": checks})
    return [seq, corr, Stage("void", PASS, "no VOID line in the prefix")]


def _verdict(process: list[Stage], decided: str) -> str:
    if any(s.outcome == FAIL for s in process):
        return REJECT
    if any(s.outcome == BLOCK for s in process):
        return BLOCKED
    return decided


# ── records ──────────────────────────────────────────────────────────────────
def event_of(k: int | None) -> str:
    return VOID_EVENT if k is None else f"a{k:02d}"


def record_name(event: str) -> str:
    return f"watch-{event}.json"


def records(watch: str, verdict_dir: Path | None = None) -> dict[str, dict]:
    """{event: record} of the watch's written records."""
    base = (Path(verdict_dir) if verdict_dir is not None else VERDICT_DIR) / watch
    out = {}
    for p in sorted(base.glob("watch-*.json")) if base.is_dir() else []:
        rec = json.loads(p.read_text(encoding="utf-8"))
        out[rec.get("event", p.stem[len("watch-"):])] = rec
    return out


def _void_line(rows) -> tuple[int, dict] | None:
    for i, (_raw, r) in enumerate(rows):
        if r.get("kind") == "void":
            return i, r
    return None


def _prefix_meta(raws, rows) -> dict:
    sessions = [r["session"] for _b, r in rows if r.get("kind") in ("genesis", "session")]
    return {"lines": len(raws), "sha256": hashlib.sha256(_prefix_bytes(raws)).hexdigest(),
            "last_line_sha256": hashlib.sha256(raws[-1]).hexdigest() if raws else None,
            "through_session": sessions[-1] if sessions else None}


def _now(now=None) -> str:
    import datetime as _dt
    now = now or _dt.datetime.now(_dt.timezone.utc)
    return now.isoformat(timespec="seconds").replace("+00:00", "Z")


def evaluate(watch: str, *, env: Env | None = None, now=None) -> dict:
    """Every record due for ``watch`` (settled anniversaries without one, in order, then a
    VOID), each with its verdict; nothing is written here. Returns ``{"watch", "records":
    [...], "pending": str | None}``, plus ``"ended"`` when a terminal record is already
    written (nothing more is then due). A BLOCKED record ends the list: the state it would
    carry forward is unknown."""
    env = env or Env()
    spec, spec_hash = fw.load(watch, env.watch_dir)
    spec_bytes = fw.spec_path(watch, env.watch_dir).read_bytes()
    rows = fw.read(watch, env.watch_dir)
    raws = [b for b, _r in rows]
    route = route_for(spec, watch, ledger=env.ledger(), policy_dir=env.policy_dir)
    written = records(watch, env.verdict_dir)
    conditions_at = env.conditions_at or (private_conditions(env.load_snapshot) if fw.is_domain(spec) else None)
    out = {"watch": watch, "records": [], "pending": None}
    try:
        readings = timeline(spec, rows, route, conditions_at=conditions_at)
    except Exception as exc:  # noqa: BLE001 — a chain that cannot read must not decide
        out["records"].append(_blocked(watch, spec_hash, f"the route cannot be read: {type(exc).__name__}: {exc}", now))
        return out
    v = _void_line(rows)
    if not readings and v is None:
        out["pending"] = pending_note(rows)
        return out
    ended = sorted(ev for ev, rec in written.items() if rec.get("verdict") in TERMINAL)
    if ended:                                            # CLOSED, VOID, DE-ADMIT, REJECT: nothing follows
        out["ended"] = f"{record_name(ended[0])} is terminal ({written[ended[0]]['verdict']}): nothing more is due"
        return out
    for ev, rec in written.items():                      # a written record must still reproduce
        if ev == VOID_EVENT:
            continue
        k = rec.get("anniversary")
        mine = [r for r in readings if r["anniversary"] == k]
        if not mine or not _same(mine[0], (rec.get("timeline") or [{}])[-1]):
            out["records"].append(_blocked(watch, spec_hash, f"the written record {record_name(ev)} no longer "
                                           f"reproduces from the log (tools/admit.py --verify-records)", now))
            return out
    cs = env.code_state()
    st_code = stage_code(cs)
    st_reg, reached_at = stage_registration(env, watch, spec_bytes)
    st_ledger = stage_ledger(env, watch, spec_hash, route)
    try:
        row = fw.ledger_entry(watch, env.ledger())
    except fw.WatchError:
        row = None
    st_window = stage_window(watch, rows, reached_at, row)
    base = {"schema": SCHEMA, "profile": PROFILE, "producer": PRODUCER, "hypothesis": watch, "watch": watch,
            "evaluated_at": _now(now), "spec_hash": spec_hash, "route": route.to_json(), "code": dict(cs)}

    def build(k, lines, decided, readings_k, void=None):
        prefix_raws, prefix_rows = raws[:lines], rows[:lines]
        prefix = _prefix_bytes(prefix_raws)
        st_chain = stage_chain(watch, spec_bytes, prefix)
        st_eval = stage_evaluator(env, spec, prefix_rows)
        st_wit, wsha = stage_witness(env, watch, prefix)
        st_ref = stage_refutations(env, watch, admits=decided == ADMIT)
        process = [st_reg, st_ledger, st_chain, st_eval, st_code, st_ref, st_wit, st_window]
        stages = process + decision_stages(spec, readings_k[-1] if readings_k and void is None else None, void=void)
        verdict = _verdict(process, decided)
        rec = {**base, "event": event_of(k), "anniversary": k,
               "as_of": readings_k[-1]["as_of"] if (k is not None and readings_k) else None,
               "prefix": _prefix_meta(prefix_raws, prefix_rows), "timeline": readings_k,
               "state_before": state_after(readings_k[:-1] if void is None else readings_k),
               "verdict": verdict,
               "reason": (next((s.detail for s in process if s.outcome in (FAIL, BLOCK)), None)
                          if verdict in (REJECT, BLOCKED) else
                          (readings_k[-1]["reason"] if void is None else f"voided: {void['reason']}")),
               "stages": [asdict(s) for s in stages], "witnessed_sha": wsha}
        if void is not None:
            rec["void"] = dict(void)
        return rec

    for i, r in enumerate(readings):
        ev = event_of(r["anniversary"])
        if ev in written:
            continue
        rec = build(r["anniversary"], r["lines"], r["route"], readings[: i + 1])
        out["records"].append(rec)
        if rec["verdict"] in (BLOCKED,) + TERMINAL:
            return out
    if v is not None and VOID_EVENT not in written and state_after(readings) in ("open", "admitted"):
        line, vr = v
        decided = DE_ADMIT if state_after(readings) == "admitted" else VOID
        out["records"].append(build(None, line + 1, decided, readings,
                                    void={"reason": vr.get("reason"), "line": line + 1,
                                          "recorded_at": vr.get("recorded_at")}))
    return out


def _blocked(watch, spec_hash, why, now) -> dict:
    return {"schema": SCHEMA, "profile": PROFILE, "hypothesis": watch, "watch": watch, "event": None,
            "anniversary": None, "evaluated_at": _now(now), "spec_hash": spec_hash, "verdict": BLOCKED,
            "reason": why, "stages": []}


def pending_note(rows) -> str:
    """When the first anniversary can settle, in words."""
    opened, _wo = window_opened(rows)
    if opened is None:
        return "the window has not opened in the log (no window_open line): nothing can settle"
    cut = pd.Timestamp(opened) + pd.DateOffset(years=1)
    return (f"anniversary 1 (cut {cut.date()}) settles once the log holds the "
            f"{fw.ANNIVERSARY_SETTLE + 1}th session line after it; nothing to decide yet")


def write_record(record: dict, verdict_dir: Path | None = None) -> Path:
    """Write one record once (O_EXCL), canonical, keyed by its event."""
    if record.get("verdict") not in WRITTEN or not record.get("event"):
        raise WatchAdmissionError(f"a {record.get('verdict')} evaluation is never written")
    base = Path(verdict_dir) if verdict_dir is not None else VERDICT_DIR
    target = base / record["watch"] / record_name(record["event"])
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        raise WatchAdmissionError(f"{target.name} exists: an anniversary's record is written once") from None
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(canonical_json(record, nonfinite="encode") + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return target


def governing(watch: str, *, env: Env | None = None) -> dict:
    """The watch's standing on the route: an upheld objection (REJECT) governs at once;
    then a VOID record; then the latest anniversary record; else none yet."""
    env = env or Env()
    st = refutations.status(watch, env.refutations_dir)
    recs = records(watch, env.verdict_dir)
    if st["upheld"]:
        return {"verdict": REJECT, "by": f"objection(s) upheld: {[o['id'] for o in st['upheld']]}"}
    if VOID_EVENT in recs:
        return {"verdict": recs[VOID_EVENT]["verdict"], "by": record_name(VOID_EVENT)}
    anns = sorted((r["anniversary"], ev) for ev, r in recs.items() if r.get("anniversary"))
    if anns:
        ev = anns[-1][1]
        return {"verdict": recs[ev]["verdict"], "by": record_name(ev)}
    return {"verdict": None, "by": "no record yet"}


# ── verification ─────────────────────────────────────────────────────────────
def _same(a, b, path="$") -> bool:
    return not _diff(a, b, path)


def _diff(a, b, path="$") -> list[str]:
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None:
        return [] if a == b else [f"{path}: {a!r} != {b!r}"]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if math.isfinite(a) and math.isfinite(b):
            return [] if abs(a - b) <= TOLERANCE * max(1.0, abs(a), abs(b)) else [f"{path}: {a!r} != {b!r}"]
        return [] if a == b else [f"{path}: {a!r} != {b!r}"]
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        if set(a) != set(b):
            return [f"{path}: keys {sorted(set(a) ^ set(b))} differ"]
        return [d for k in a for d in _diff(a[k], b[k], f"{path}.{k}")]
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in _diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def _snapshot_status(sha: str) -> str:
    from src.research import data_store
    path = data_store.find("DS", sha)
    if path is None:
        return "absent"
    return "altered" if data_store.verify_file(path) else "present"


def _replay_conditions(env: Env, record: Mapping, notes: list, problems: list) -> ConditionsAt:
    """The verifier's conditions: recomputed from the private snapshot where it is present;
    where it is absent, the record's stated legs are replayed (a NOTE, or a problem with
    MONAD_REQUIRE_PRIVATE_STORE=1) and the log's episode count recomputed; altered, a problem."""
    if env.conditions_at is not None:
        return env.conditions_at
    stated = {t["as_of"]: t.get("conditions") for t in record.get("timeline") or []}
    status = env.snapshot_status or _snapshot_status
    compute = private_conditions(env.load_snapshot)

    def at(spec, prefix, cut):
        sha = _last_snapshot(prefix)
        s = status(sha)
        if s == "present":
            return compute(spec, prefix, cut)
        if s == "altered":
            raise WatchAdmissionError(f"private snapshot {sha[:12]} does not hash to its name")
        own = stated.get(str(cut.date()))
        if not own or not own.get("legs"):
            raise WatchAdmissionError(f"the record states no conditions at {cut.date()}, which its timeline "
                                      f"consults, and snapshot {sha[:12]} is not here to compute them")
        msg = (f"{cut.date()}: the long leg {own['legs'].get('long_leg')!r} is the record's own; private "
               f"snapshot {sha[:12]} is absent here (restore the store to recompute it)")
        (problems if env.require_private else notes).append(msg)
        base = log_only_conditions(spec, prefix, cut)
        legs = {**own["legs"], "episodes": base["legs"]["episodes"], "sessions": base["legs"]["sessions"]}
        return {"continue": base["continue"], "close": base["close"] if legs["long_leg"] <= 0 else None,
                "legs": legs, "snapshot": own.get("snapshot", sha)}
    return at


def verify_record(record: Mapping, *, env: Env | None = None) -> tuple[list[str], list[str]]:
    """(problems, notes) for one watch record: every derivable field recomputed from the
    log prefix it pins. Problems make it untrustworthy; notes say what this environment
    could not recompute (a domain watch's long leg without the private store)."""
    env = env or Env()
    problems, notes = [], []
    watch = record.get("watch")
    if record.get("profile") != PROFILE or record.get("schema") != SCHEMA:
        return [f"not a schema-{SCHEMA} {PROFILE} record"], notes
    if record.get("hypothesis") != watch:
        problems.append("hypothesis and watch differ")
    if record.get("verdict") not in WRITTEN:
        return problems + [f"verdict {record.get('verdict')!r} is never written"], notes
    k = record.get("anniversary")
    if record.get("event") != event_of(k):
        problems.append(f"event {record.get('event')!r} does not match anniversary {k!r}")
    names = [s.get("name") for s in record.get("stages") or []]
    if tuple(names) != STAGES:
        return problems + [f"the stages are not the ratified chain {list(STAGES)}"], notes
    stages = {s["name"]: s for s in record["stages"]}
    try:
        spec, spec_hash = fw.load(watch, env.watch_dir)
    except (FileNotFoundError, ValueError) as exc:
        return problems + [f"the spec does not load: {exc}"], notes
    if spec_hash != record.get("spec_hash"):
        problems.append("the spec no longer matches the record's spec_hash")
    try:
        rows = fw.read(watch, env.watch_dir)
    except ValueError as exc:
        return problems + [f"the log does not parse: {exc}"], notes
    raws = [b for b, _r in rows]
    meta = record.get("prefix") or {}
    n = meta.get("lines")
    if not isinstance(n, int) or n < 1 or n > len(raws):
        return problems + [f"the record pins {n!r} log lines; the log holds {len(raws)}"], notes
    prefix_rows, prefix_raws = rows[:n], raws[:n]
    if _prefix_meta(prefix_raws, prefix_rows) != meta:
        problems.append("the log prefix is not the bytes the record pins")
    # the route, on the policy link the record names
    rt = record.get("route") or {}
    name = Path(str(rt.get("policy_path", ""))).name
    link_path = env.policy_dir / name
    try:
        chain_names = {("route.json" if i == 0 else f"route.{i + 1}.json")
                       for i in range(len(fw.policy_chain(env.policy_dir)))}
        if (rt.get("policy_path") != (fw.POLICY_REL / name).as_posix() or name not in chain_names
                or not link_path.is_file()):
            raise WatchAdmissionError(f"{rt.get('policy_path')} is not a link of the policy chain")
        if hashlib.sha256(link_path.read_bytes()).hexdigest() != rt.get("policy_sha256"):
            raise WatchAdmissionError(f"{rt.get('policy_path')} is not the bytes the record names")
        policy = json.loads(link_path.read_text(encoding="utf-8"))
        route = route_for(spec, watch, ledger=env.ledger(), link=(link_path, policy))
    except (WatchAdmissionError, fw.WatchError, OSError, ValueError) as exc:
        return problems + [f"route: {exc}"], notes
    problems += [f"route: {d}" for d in _diff(route.to_json(), dict(rt), "route")]
    # the timeline and the decision, recomputed from the prefix
    void = record.get("void")
    try:
        cond = _replay_conditions(env, record, notes, problems) if fw.is_domain(spec) else None
        readings = timeline(spec, prefix_rows, route, conditions_at=cond)
    except (WatchAdmissionError, fw.WatchError, KeyError, ValueError) as exc:
        return problems + [f"timeline: {exc}"], notes
    problems += [f"timeline: {d}" for d in _diff(readings, record.get("timeline") or [], "timeline")][:5]
    if void is None:
        anns = settled_anniversaries(rows)
        mine = [a for a in anns if a.k == k]
        if not mine or mine[0].lines != n:
            problems.append(f"the prefix ({n} lines) is not the one that settles anniversary {k}")
        if not readings or readings[-1]["anniversary"] != k:
            problems.append(f"the recomputed timeline does not end at anniversary {k}")
        decided = readings[-1]["route"] if readings else None
    else:
        v = _void_line(rows)
        if v is None or v[0] + 1 != n:
            problems.append("the prefix does not end at the log's VOID line")
        st = state_after(readings)
        if st not in ("open", "admitted"):
            problems.append(f"a VOID record after a terminal state ({st})")
        decided = DE_ADMIT if st == "admitted" else VOID
    if record.get("state_before") != state_after(readings[:-1] if void is None else readings):
        problems.append("state_before does not follow from the timeline")
    for s in decision_stages(spec, readings[-1] if (readings and void is None) else None, void=void):
        got = stages[s.name]
        if (got.get("outcome"), got.get("detail")) != (s.outcome, s.detail) or not _same(asdict(s)["data"], got.get("data")):
            problems.append(f"{s.name}: the stage does not follow from the prefix")
    if stages["refutations"].get("outcome") == FAIL:
        if record["verdict"] != REJECT:
            problems.append("an upheld objection must REJECT")
    elif record["verdict"] != decided:
        problems.append(f"verdict {record['verdict']} does not follow from the prefix ({decided})")
    for name in PROCESS:
        if stages[name].get("outcome") == BLOCK:
            problems.append(f"{name}: a written record cannot carry a blocked stage")
    problems += _verify_process(env, record, spec, prefix_rows, _prefix_bytes(prefix_raws), stages)
    if record["verdict"] == ADMIT and not all(stages[nm].get("outcome") == PASS for nm in STAGES):
        problems.append("an ADMIT must pass exactly the full stage chain")
    return problems, notes


def _verify_process(env: Env, record: Mapping, spec: Mapping, prefix_rows, prefix: bytes, stages) -> list[str]:
    """The environment-dependent stages, re-checked: chain and evaluator always; the deploy
    branch's facts where its ref is available (authoritative in CI, which fetches it)."""
    problems = []
    watch = record["watch"]
    spec_bytes = fw.spec_path(watch, env.watch_dir).read_bytes()
    if stage_chain(watch, spec_bytes, prefix).outcome != PASS:
        problems.append("chain: the prefix does not verify")
    ev = stage_evaluator(env, spec, prefix_rows)
    if ev.outcome != PASS:
        problems.append(f"evaluator: {ev.detail}")
    code = record.get("code") or {}
    if not trials.committed_clean(code):
        problems.append("code: the record was evaluated on a modified tree")
    elif env.git("merge-base", "--is-ancestor", code["sha"], "HEAD").returncode != 0:
        problems.append(f"code: commit {code['sha'][:12]} is not in this branch's history")
    # The refutation log only grows (CI-checked), so the log as it stood when the record was
    # evaluated is its entries stamped at or before evaluated_at: the stage must follow from it.
    at = record.get("evaluated_at") or ""
    try:
        then = _status_of([e for e in refutations.entries(watch, env.refutations_dir)
                           if str(e.get("at", "")) <= at])
    except (refutations.RefutationError, ValueError) as exc:
        return problems + [f"refutations: {exc}"]
    decided = ADMIT if record["verdict"] == ADMIT else None
    want = refutation_outcome(then, admits=decided == ADMIT)
    got = stages["refutations"].get("outcome")
    if got != want:
        problems.append(f"refutations: the record reads {got} but the refutation log at {at or '(no time)'} "
                        f"gives {want}" + (" (an ADMIT needs objections filed, all refuted)" if decided else ""))
    if _ref_sha(env) is None:
        if os.environ.get("CI"):
            problems.append(f"{env.ref} is not available to check the registration and the witness")
        return problems
    reg, reached_at = stage_registration(env, watch, spec_bytes)
    if reg.outcome != PASS:
        problems.append(f"registration: {reg.detail}")
    wit, _sha = stage_witness(env, watch, prefix)
    if wit.outcome != PASS:
        problems.append(f"witness: {wit.detail}")
    wsha = record.get("witnessed_sha")
    if not wsha or not _is_ancestor(env, wsha):
        problems.append(f"witness: the witnessed commit {str(wsha)[:12]} is not in {env.ref}")
    try:
        row = fw.ledger_entry(watch, env.ledger())
    except fw.WatchError as exc:
        return problems + [f"ledger: {exc}"]
    win = stage_window(watch, prefix_rows, reached_at, row)
    if win.outcome != PASS:
        problems.append(f"window: {win.detail}")
    return problems
