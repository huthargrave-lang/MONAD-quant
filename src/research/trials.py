"""
MONAD Quant — The trial ledger: every attempt counted, before its result exists.

Why this exists (the project's own history): the sweep picked its winner by the
holdout score and logged only that winner (RESEARCH_WEB.md F2; ``sweep.py`` appends
ONE row to a gitignored ``experiments.jsonl``). Nothing anywhere recorded how many
things were tried, so no result could be deflated for the search that produced it.
A Deflated Sharpe Ratio is only as honest as its trial count, and a trial count is
only honest if the losers are in it. This module is the one place that count lives.

The contract:

  * **Intent before result.** ``Run.begin`` durably writes an ``intent`` row (spec,
    spec hash) and fsyncs it BEFORE the caller computes anything. A trial whose
    process dies mid-computation is still counted: its intent has no outcome, and
    ``family_counts`` reports it as an orphan. Abandoning a bad-looking trial cannot
    erase it.
  * **One shard per run.** ``docs/research/trials/<run_id>.jsonl`` is written by a
    single process that holds an exclusive ``flock`` for the run's lifetime. Shards
    never share a file, so parallel worktrees never conflict on append.
  * **Hash-chained.** Every row carries ``prev`` = sha256 of the previous row's bytes
    (the first row chains to a per-run genesis). Editing, deleting or reordering any
    row breaks the chain, and ``verify_shard`` says where.
  * **Append-only across history.** ``verify_append_only`` checks that every shard
    and artifact present at a base commit is still present and a byte-prefix of
    (artifacts: identical to) its current content. CI runs it against the deploy
    branch, so a committed trial cannot be quietly rewritten or removed.
  * **Return series are content-addressed.** A trial's return series is hashed into
    its outcome row and stored in one gzip bundle per run under ``artifacts/``,
    named by the sha256 of its canonical content. Effective-N clustering (the
    significance kernel) needs the losers' returns, not only their Sharpes.
  * **Code state is recorded, not required.** Dirty-worktree runs are counted like
    any other (refusing them would push exploration outside the ledger, which is
    the undercount this module exists to prevent), but ``run_open.code`` records
    ``dirty`` plus a hash of the diff and untracked files. Admission evidence must
    come from a clean, replayable run; that is the gate's rule, not the ledger's.

Rows (``v`` = SCHEMA_VERSION, ``seq`` contiguous from 0):
  run_open  — run_id, producer, family, hypothesis, code, env, context
  intent    — trial, spec, spec_hash
  outcome   — trial, status (ok|error|abandoned), metrics, returns_sha, n_returns, error
  run_close — status (complete|aborted|crashed), n_intents, n_outcomes, bundle_sha

Only the process that opened a run writes to it. Producers that parallelise must
``begin`` in the parent before dispatching and ``complete`` in the parent as
results return.
"""
from __future__ import annotations

import datetime as _dt
import errno
import fcntl
import gzip
import hashlib
import io
import json
import math
import os
import platform
import re
import secrets
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1

REPO = Path(__file__).resolve().parents[2]
LEDGER_REL = Path("docs/research/trials")
LEDGER_DIR = REPO / LEDGER_REL
ARTIFACTS = "artifacts"
#: Research RECORDS, not code: the ledger, registrations, refutations, verdicts and
#: re-evaluation decisions. Writing one must not make the code look modified, or the gate
#: blocks on its own verdict file (harness red-team friction #4). Their integrity is
#: guarded by their own append-only/immutable history checks instead.
RECORD_RELS = tuple(Path(p) for p in ("docs/research/trials", "docs/research/prereg",
                                      "docs/research/refutations", "docs/research/verdicts",
                                      "docs/research/reeval"))

ROW_TYPES = ("run_open", "intent", "outcome", "run_close")
OUTCOME_STATUSES = ("ok", "error", "abandoned")
CLOSE_STATUSES = ("complete", "aborted", "crashed")

_RUN_ID = re.compile(r"^TR-\d{8}T\d{6}Z-[0-9a-f]{8}$")
_FAMILY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,127}$")
_HYPOTHESIS = re.compile(r"^H\d+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

# Non-finite metric values (a zero-trade Sharpe is NaN) are legitimate outcomes, but
# JSON has no spelling for them. They are encoded as these exact strings and decoded
# back by ``decode_metrics``; anywhere else (specs, returns) a non-finite is an error.
_NONFINITE_ENCODE = {"nan": "NaN", "inf": "Infinity", "-inf": "-Infinity"}
_NONFINITE_DECODE = {"NaN": math.nan, "Infinity": math.inf, "-Infinity": -math.inf}


class LedgerError(Exception):
    """A ledger invariant was violated, or a caller misused the API."""


# ── canonical encoding ───────────────────────────────────────────────────────
def _normalize(value: Any, *, nonfinite: str, where: str) -> Any:
    """Reduce ``value`` to plain JSON types, deterministically, or raise.

    ``nonfinite`` is ``"raise"`` or ``"encode"``. Unknown types raise rather than
    being str()-ed: a spec hash over an object's repr is not a spec hash.
    """
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if nonfinite == "encode":
            return _NONFINITE_ENCODE[repr(value)]
        raise LedgerError(f"non-finite float at {where}: {value!r}")
    if isinstance(value, Mapping):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise LedgerError(f"non-string key {k!r} at {where}")
            out[k] = _normalize(v, nonfinite=nonfinite, where=f"{where}.{k}")
        return out
    if isinstance(value, (list, tuple)):
        return [_normalize(v, nonfinite=nonfinite, where=f"{where}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    # numpy / pandas, imported lazily so the ledger has no hard dependency on them.
    np = sys.modules.get("numpy")
    if np is not None:
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return _normalize(float(value), nonfinite=nonfinite, where=where)
        if isinstance(value, np.ndarray):
            return _normalize(value.tolist(), nonfinite=nonfinite, where=where)
    pd = sys.modules.get("pandas")
    if pd is not None and isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise LedgerError(f"unsupported type {type(value).__name__} at {where}")


def canonical_json(value: Any, *, nonfinite: str = "raise") -> str:
    """Deterministic JSON: normalized types, sorted keys, no whitespace, no NaN."""
    return json.dumps(
        _normalize(value, nonfinite=nonfinite, where="$"),
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def spec_hash(spec: Mapping[str, Any]) -> str:
    """Hash identifying WHAT was tried: identical specs hash identically."""
    return sha256_text(canonical_json(spec))


def decode_metrics(metrics: Mapping[str, Any]) -> dict:
    """Inverse of the metric encoding: the three non-finite spellings back to floats."""
    return {k: (_NONFINITE_DECODE[v] if isinstance(v, str) and v in _NONFINITE_DECODE else v)
            for k, v in metrics.items()}


def canonical_returns(returns: Any) -> list[list]:
    """A return series as ``[[timestamp_iso, value], ...]`` in the caller's order.

    Accepts a pandas Series (index = timestamps) or an iterable of (timestamp, value)
    pairs. Every value must be a finite number: a NaN return is a bug upstream, and
    hashing it would make two different bugs look identical.
    """
    pd = sys.modules.get("pandas")
    if pd is not None and isinstance(returns, pd.Series):
        pairs: Iterable = zip(returns.index, returns.to_numpy())
    else:
        pairs = returns
    out = []
    for i, pair in enumerate(pairs):
        try:
            ts, val = pair
        except (TypeError, ValueError):
            raise LedgerError(f"returns[{i}] is not a (timestamp, value) pair") from None
        ts_n = _normalize(ts, nonfinite="raise", where=f"returns[{i}].ts")
        if not isinstance(ts_n, str):
            ts_n = str(ts_n)
        val_n = _normalize(val, nonfinite="raise", where=f"returns[{i}].value")
        if isinstance(val_n, bool) or not isinstance(val_n, (int, float)):
            raise LedgerError(f"returns[{i}].value is not a number: {val!r}")
        out.append([ts_n, float(val_n)])
    return out


# ── environment capture ──────────────────────────────────────────────────────
def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)


def code_state(repo: Path = REPO, record_rels=RECORD_RELS) -> dict:
    """The code a run executed: HEAD sha, and whether (and how) the tree differed.

    ``diff_sha256`` covers the tracked diff against HEAD plus every untracked,
    non-ignored file's path and content, excluding the research record directories
    (``RECORD_RELS``): a run writing its shard, or the gate writing its verdict, must not
    make the code look dirty. Failure to read git is recorded, never guessed: ``sha`` is
    None and ``error`` says why.
    """
    head = _git(repo, "rev-parse", "HEAD")
    if head.returncode != 0:
        return {"sha": None, "dirty": None, "diff_sha256": None,
                "error": head.stderr.decode(errors="replace").strip() or "git rev-parse failed"}
    excludes = [f":(exclude){Path(r).as_posix()}" for r in record_rels]
    diff = _git(repo, "diff", "HEAD", "--binary", "--", ".", *excludes)
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z", "--", ".", *excludes)
    if diff.returncode != 0 or untracked.returncode != 0:
        return {"sha": head.stdout.decode().strip(), "dirty": None, "diff_sha256": None,
                "error": "git diff/ls-files failed"}
    h = hashlib.sha256(diff.stdout)
    paths = sorted(p for p in untracked.stdout.decode(errors="surrogateescape").split("\0") if p)
    for p in paths:
        h.update(b"\0untracked\0" + p.encode(errors="surrogateescape") + b"\0")
        try:
            h.update((repo / p).read_bytes())
        except OSError as exc:  # vanished between listing and reading
            h.update(f"<unreadable:{exc.errno}>".encode())
    dirty = bool(diff.stdout) or bool(paths)
    return {"sha": head.stdout.decode().strip(), "dirty": dirty,
            "diff_sha256": h.hexdigest() if dirty else None, "error": None}


def env_state() -> dict:
    versions = {}
    for name in ("numpy", "pandas"):
        mod = sys.modules.get(name)
        versions[name] = getattr(mod, "__version__", None) if mod is not None else None
    return {"python": platform.python_version(), "platform": sys.platform, "packages": versions}


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def new_run_id() -> str:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"TR-{stamp}-{secrets.token_hex(4)}"


def genesis(run_id: str) -> str:
    return sha256_text(f"monad-trial-ledger:v{SCHEMA_VERSION}:genesis:{run_id}")


# ── writer ───────────────────────────────────────────────────────────────────
@dataclass
class Trial:
    """Handle for one begun trial. Complete it through its Run (or ``complete``)."""
    run: "Run"
    index: int
    spec_hash: str
    done: bool = False

    def complete(self, metrics: Mapping[str, Any], returns: Any = None) -> None:
        self.run.complete(self, metrics=metrics, returns=returns)

    def fail(self, error: str) -> None:
        self.run.fail(self, error=error)

    # Context-manager form: an exception inside records an ``error`` outcome and
    # propagates; leaving without an outcome records ``abandoned``.
    def __enter__(self) -> "Trial":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if not self.done:
            if exc is not None:
                self.run.fail(self, error=f"{exc_type.__name__}: {exc}")
            else:
                self.run._outcome(self, status="abandoned", error="trial exited without an outcome")
        return False


@dataclass
class Run:
    """One producer invocation. Use via ``open_run`` (a context manager)."""
    run_id: str
    path: Path
    artifacts_dir: Path
    family: str
    _fh: Any = field(repr=False, default=None)
    _prev: str = field(repr=False, default="")
    _seq: int = field(repr=False, default=0)
    _n_intents: int = field(repr=False, default=0)
    _n_outcomes: int = field(repr=False, default=0)
    _open: dict = field(repr=False, default_factory=dict)
    _returns: dict = field(repr=False, default_factory=dict)
    _lock: Any = field(repr=False, default_factory=threading.Lock)
    _closed: bool = field(repr=False, default=False)

    # -- low level
    def _write(self, row: dict) -> None:
        if self._closed:
            raise LedgerError(f"run {self.run_id} is closed")
        full = {"v": SCHEMA_VERSION, "seq": self._seq, "prev": self._prev, **row}
        line = canonical_json(full, nonfinite="encode")
        data = (line + "\n").encode("utf-8")
        self._fh.write(data)
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._prev = hashlib.sha256(line.encode("utf-8")).hexdigest()
        self._seq += 1

    @property
    def trials_begun(self) -> int:
        """Intents written so far; the next ``begin`` gets this trial index."""
        return self._n_intents

    # -- trials
    def begin(self, params: Mapping[str, Any], data: Mapping[str, Any] | None = None,
              extra: Mapping[str, Any] | None = None) -> Trial:
        """Record the intent to run one trial. Call BEFORE computing its result."""
        spec = {"params": dict(params), "data": dict(data) if data is not None else None,
                "extra": dict(extra) if extra is not None else None}
        h = spec_hash(spec)
        with self._lock:
            index = self._n_intents
            self._write({"type": "intent", "at": _now(), "trial": index,
                         "spec": spec, "spec_hash": h})
            self._n_intents += 1
            trial = Trial(run=self, index=index, spec_hash=h)
            self._open[index] = trial
        return trial

    def trial(self, params: Mapping[str, Any], data: Mapping[str, Any] | None = None,
              extra: Mapping[str, Any] | None = None) -> Trial:
        """``with run.trial(...) as t: ... t.complete(...)``."""
        return self.begin(params, data=data, extra=extra)

    def complete(self, trial: Trial, metrics: Mapping[str, Any], returns: Any = None) -> None:
        returns_sha = None
        n_returns = None
        series = None
        if returns is not None:
            series = canonical_returns(returns)
            returns_sha = sha256_text(canonical_json(series))
            n_returns = len(series)
        self._outcome(trial, status="ok", metrics=dict(metrics),
                      returns_sha=returns_sha, n_returns=n_returns)
        if series is not None:  # only after the outcome that references it was written
            with self._lock:
                self._returns.setdefault(returns_sha, series)

    def fail(self, trial: Trial, error: str) -> None:
        self._outcome(trial, status="error", error=str(error))

    def _outcome(self, trial: Trial, *, status: str, metrics: Mapping[str, Any] | None = None,
                 returns_sha: str | None = None, n_returns: int | None = None,
                 error: str | None = None) -> None:
        if trial.run is not self:
            raise LedgerError("trial belongs to a different run")
        with self._lock:
            if trial.done or trial.index not in self._open:
                raise LedgerError(f"trial {trial.index} already has an outcome")
            self._write({"type": "outcome", "at": _now(), "trial": trial.index, "status": status,
                         "metrics": metrics, "returns_sha": returns_sha,
                         "n_returns": n_returns, "error": error})
            trial.done = True
            del self._open[trial.index]
            self._n_outcomes += 1

    # -- close
    def _close(self, status: str) -> None:
        with self._lock:
            for trial in list(self._open.values()):
                self._write({"type": "outcome", "at": _now(), "trial": trial.index,
                             "status": "abandoned", "metrics": None, "returns_sha": None,
                             "n_returns": None, "error": f"run closed ({status}) without an outcome"})
                trial.done = True
                self._n_outcomes += 1
            self._open.clear()
            bundle_sha = write_bundle(self.artifacts_dir, self._returns) if self._returns else None
            self._write({"type": "run_close", "at": _now(), "status": status,
                         "n_intents": self._n_intents, "n_outcomes": self._n_outcomes,
                         "bundle_sha": bundle_sha})
            self._closed = True


class open_run:
    """Open a ledger run: ``with open_run(producer=..., family=...) as run:``.

    ``family`` groups trials that test the same idea; it is the unit the significance
    kernel deflates over, so every variant of one idea must share it. ``hypothesis``
    (``H<n>``) links the run to a web node when one exists. ``context`` is free-form,
    canonically encoded metadata (ticker, mode, CLI args).
    """

    def __init__(self, *, producer: str, family: str, hypothesis: str | None = None,
                 context: Mapping[str, Any] | None = None, ledger_dir: Path | None = None,
                 repo: Path = REPO):
        if not producer or not isinstance(producer, str):
            raise LedgerError("producer is required")
        if not isinstance(family, str) or not _FAMILY.match(family):
            raise LedgerError(f"family {family!r} must match {_FAMILY.pattern}")
        if hypothesis is not None and not _HYPOTHESIS.match(hypothesis):
            raise LedgerError(f"hypothesis {hypothesis!r} must look like H<n>")
        if hypothesis is not None:
            # A registered hypothesis's trials must land in its registered family, or a
            # relabelled sweep would escape the count its registration is judged by.
            from src.research import prereg  # lazy: prereg imports this module
            reg = prereg.path_for(hypothesis)
            if reg.exists():
                registered_family = json.loads(reg.read_text(encoding="utf-8")).get("family")
                if registered_family != family:
                    raise LedgerError(f"{hypothesis} is registered to family "
                                      f"{registered_family!r}, not {family!r}")
        self.producer = producer
        self.family = family
        self.hypothesis = hypothesis
        self.context = dict(context) if context is not None else {}
        self.ledger_dir = Path(ledger_dir) if ledger_dir is not None else LEDGER_DIR
        self.repo = repo
        self.run: Run | None = None

    def __enter__(self) -> Run:
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        artifacts = self.ledger_dir / ARTIFACTS
        artifacts.mkdir(exist_ok=True)
        run_id = new_run_id()
        path = self.ledger_dir / f"{run_id}.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o644)
        fh = os.fdopen(fd, "ab", buffering=0)
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            run = Run(run_id=run_id, path=path, artifacts_dir=artifacts, family=self.family,
                      _fh=fh, _prev=genesis(run_id))
            run._write({"type": "run_open", "at": _now(), "run_id": run_id,
                        "producer": self.producer, "family": self.family,
                        "hypothesis": self.hypothesis, "code": code_state(self.repo),
                        "env": env_state(), "context": self.context})
        except BaseException:
            fh.close()
            raise
        self.run = run
        return run

    def __exit__(self, exc_type, exc, tb) -> bool:
        run = self.run
        try:
            run._close("complete" if exc is None else "aborted")
        finally:
            run._fh.close()  # releases the flock
        return False


def open_process_run(**kwargs) -> Run:
    """Open a run that lives as long as the process: for top-level scripts.

    ``sweep.py`` does its work at module level, so there is no block to put a
    ``with`` around. This opens the run immediately and closes it at interpreter
    exit: ``aborted`` if an uncaught exception (KeyboardInterrupt included) reached
    ``sys.excepthook``, ``complete`` otherwise. A process killed outright leaves the
    run unclosed, which ``seal`` repairs and which never loses a counted trial.
    Takes the same keyword arguments as ``open_run``.
    """
    import atexit

    ctx = open_run(**kwargs)
    run = ctx.__enter__()
    failure: list = []
    previous_hook = sys.excepthook

    def hook(exc_type, exc, tb):
        failure.append(exc)
        previous_hook(exc_type, exc, tb)

    def close():
        if run._closed:
            return
        err = failure[0] if failure else None
        ctx.__exit__(type(err) if err is not None else None, err, None)

    sys.excepthook = hook
    atexit.register(close)
    return run


# ── artifacts ────────────────────────────────────────────────────────────────
def write_bundle(artifacts_dir: Path, returns: Mapping[str, list]) -> str:
    """Write a content-addressed gzip bundle of return series; return its sha.

    The address is the sha256 of the canonical (uncompressed) JSON, so it does not
    depend on the compressor. gzip's mtime is pinned to 0 so identical content also
    yields identical bytes. An existing bundle with the same address is left alone.
    """
    text = canonical_json({"returns": dict(returns)})
    sha = sha256_text(text)
    target = Path(artifacts_dir) / f"{sha}.json.gz"
    if target.exists():
        return sha
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, filename="") as gz:
        gz.write(text.encode("utf-8"))
    tmp = target.with_suffix(".gz.partial")
    with open(tmp, "wb") as f:
        f.write(buf.getvalue())
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
    return sha


def read_bundle(artifacts_dir: Path, sha: str) -> dict:
    """Load a bundle and verify its address. Raises LedgerError on mismatch."""
    path = Path(artifacts_dir) / f"{sha}.json.gz"
    try:
        text = gzip.decompress(path.read_bytes()).decode("utf-8")
    except FileNotFoundError:
        raise LedgerError(f"bundle {sha} is missing") from None
    except (OSError, EOFError, UnicodeDecodeError) as exc:
        raise LedgerError(f"bundle {sha} is unreadable: {exc}") from None
    if sha256_text(text) != sha:
        raise LedgerError(f"bundle {sha} content does not match its address")
    return json.loads(text)["returns"]


# ── reader / verifier ────────────────────────────────────────────────────────
@dataclass
class ShardReport:
    path: Path
    run_id: str | None
    family: str | None
    hypothesis: str | None
    closed: bool
    close_status: str | None
    torn_tail: bool
    intents: int
    outcomes: dict            # status -> count
    orphans: int              # intents with no outcome at all
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _split_lines(raw: bytes) -> tuple[list[bytes], bool]:
    """Lines of a shard, and whether the final line is torn (no trailing newline)."""
    if not raw:
        return [], False
    torn = not raw.endswith(b"\n")
    lines = raw.split(b"\n")
    if not torn:
        lines = lines[:-1]
    return lines, torn


def verify_shard(path: Path, artifacts_dir: Path | None = None) -> ShardReport:
    """Check every invariant of one shard. Never raises for a bad shard: reports it."""
    path = Path(path)
    artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else path.parent / ARTIFACTS
    errors: list[str] = []
    run_id = family = hypothesis = close_status = None
    closed = False
    intents: dict[int, str] = {}
    outcomes: dict[int, str] = {}
    returns_shas: set[str] = set()
    bundle_sha = None

    raw = path.read_bytes()
    lines, torn = _split_lines(raw)
    if torn:
        errors.append("torn final row (crash mid-write); run `tools/trial_ledger.py seal`")
        lines = lines[:-1]

    expected_id = path.stem
    if not _RUN_ID.match(expected_id):
        errors.append(f"file name {path.name} is not a run id")
    prev = genesis(expected_id)
    for i, line in enumerate(lines):
        where = f"row {i}"
        try:
            row = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{where}: not JSON ({exc})")
            break
        if not isinstance(row, dict):
            errors.append(f"{where}: not an object")
            break
        if row.get("v") != SCHEMA_VERSION:
            errors.append(f"{where}: schema version {row.get('v')!r}")
        if row.get("seq") != i:
            errors.append(f"{where}: seq {row.get('seq')!r}, expected {i}")
        if row.get("prev") != prev:
            errors.append(f"{where}: hash chain broken (row edited, removed or reordered)")
        try:
            if canonical_json(row, nonfinite="encode") != line.decode("utf-8"):
                errors.append(f"{where}: not in canonical form")
        except LedgerError as exc:
            errors.append(f"{where}: {exc}")
        prev = hashlib.sha256(line).hexdigest()

        kind = row.get("type")
        if kind not in ROW_TYPES:
            errors.append(f"{where}: unknown type {kind!r}")
            continue
        if closed:
            errors.append(f"{where}: row after run_close")
        if (i == 0) != (kind == "run_open"):
            errors.append(f"{where}: run_open must be exactly the first row")
        if kind == "run_open":
            run_id, family, hypothesis = row.get("run_id"), row.get("family"), row.get("hypothesis")
            if run_id != expected_id:
                errors.append(f"{where}: run_id {run_id!r} does not match file name")
            if not isinstance(family, str) or not _FAMILY.match(family):
                errors.append(f"{where}: invalid family {family!r}")
            if hypothesis is not None and not (isinstance(hypothesis, str) and _HYPOTHESIS.match(hypothesis)):
                errors.append(f"{where}: invalid hypothesis {hypothesis!r}")
        elif kind == "intent":
            t = row.get("trial")
            if t != len(intents):
                errors.append(f"{where}: trial index {t!r}, expected {len(intents)}")
            try:
                if spec_hash(row.get("spec")) != row.get("spec_hash"):
                    errors.append(f"{where}: spec_hash does not match spec")
            except LedgerError as exc:
                errors.append(f"{where}: spec not hashable ({exc})")
            intents[t] = row.get("spec_hash")
        elif kind == "outcome":
            t = row.get("trial")
            status = row.get("status")
            if t not in intents:
                errors.append(f"{where}: outcome for trial {t!r} with no prior intent")
            elif t in outcomes:
                errors.append(f"{where}: second outcome for trial {t!r}")
            if status not in OUTCOME_STATUSES:
                errors.append(f"{where}: unknown outcome status {status!r}")
            rs = row.get("returns_sha")
            if rs is not None:
                if not (isinstance(rs, str) and _SHA256.match(rs)):
                    errors.append(f"{where}: malformed returns_sha")
                else:
                    returns_shas.add(rs)
            if status == "ok" and not isinstance(row.get("metrics"), dict):
                errors.append(f"{where}: ok outcome without a metrics object")
            if status != "ok" and rs is not None:
                errors.append(f"{where}: only ok outcomes carry returns")
            outcomes[t] = status
        elif kind == "run_close":
            closed = True
            close_status = row.get("status")
            bundle_sha = row.get("bundle_sha")
            if close_status not in CLOSE_STATUSES:
                errors.append(f"{where}: unknown close status {close_status!r}")
            if row.get("n_intents") != len(intents):
                errors.append(f"{where}: n_intents {row.get('n_intents')!r} != {len(intents)}")
            if row.get("n_outcomes") != len(outcomes):
                errors.append(f"{where}: n_outcomes {row.get('n_outcomes')!r} != {len(outcomes)}")

    if not lines:
        errors.append("empty shard: the process died before run_open was written; it holds "
                      "no trial, so if it is uncommitted it can simply be deleted")

    if returns_shas:
        if not closed or close_status == "crashed":
            pass  # the process died before writing its bundle; its trials still count
        elif bundle_sha is None:
            errors.append("outcomes reference returns but run_close has no bundle")
        else:
            try:
                bundle = read_bundle(artifacts_dir, bundle_sha)
            except LedgerError as exc:
                errors.append(str(exc))
            else:
                missing = returns_shas - set(bundle)
                if missing:
                    errors.append(f"bundle lacks {len(missing)} referenced return series")
                for sha, series in bundle.items():
                    if sha256_text(canonical_json(series)) != sha:
                        errors.append(f"bundle series {sha[:12]} does not match its key")
                        break
    elif closed and bundle_sha is not None:
        errors.append("run_close names a bundle but no outcome references returns")

    counts: dict[str, int] = {}
    for status in outcomes.values():
        counts[status] = counts.get(status, 0) + 1
    return ShardReport(path=path, run_id=run_id, family=family, hypothesis=hypothesis,
                       closed=closed, close_status=close_status, torn_tail=torn,
                       intents=len(intents), outcomes=counts,
                       orphans=len(set(intents) - set(outcomes)), errors=errors)


def shard_paths(ledger_dir: Path | None = None) -> list[Path]:
    d = Path(ledger_dir) if ledger_dir is not None else LEDGER_DIR
    return sorted(d.glob("TR-*.jsonl")) if d.is_dir() else []


def verify_ledger(ledger_dir: Path | None = None, *, require_closed: bool = False) -> list[ShardReport]:
    reports = [verify_shard(p) for p in shard_paths(ledger_dir)]
    if require_closed:
        for r in reports:
            if not r.closed and not r.torn_tail:
                r.errors.append("run is not closed; if its process is gone, run `tools/trial_ledger.py seal`")
    return reports


def family_counts(ledger_dir: Path | None = None) -> dict[str, dict]:
    """Per family: runs, intents (= trials attempted), outcomes by status, orphans.

    ``intents`` is the honest trial count: it includes errors, abandonments and
    orphans from crashed runs, because each was an attempt someone could have
    reported had it looked good.
    """
    out: dict[str, dict] = {}
    for r in verify_ledger(ledger_dir):
        fam = r.family or "<unreadable>"
        agg = out.setdefault(fam, {"runs": 0, "intents": 0, "ok": 0, "error": 0,
                                   "abandoned": 0, "orphans": 0, "invalid_runs": 0})
        agg["runs"] += 1
        agg["intents"] += r.intents
        agg["orphans"] += r.orphans
        for status, n in r.outcomes.items():
            agg[status] = agg.get(status, 0) + n
        if not r.ok:
            agg["invalid_runs"] += 1
    return out


@dataclass
class TrialRecord:
    """One counted trial, as the ledger holds it (for readers such as the gate)."""
    run_id: str
    trial: int
    family: str
    hypothesis: str | None
    producer: str
    code: dict
    spec_hash: str
    spec: dict
    status: str               # ok | error | abandoned | orphan (no outcome: crashed run)
    metrics: dict | None
    returns_sha: str | None
    bundle_sha: str | None
    opened_at: str            # the run's open time (UTC ISO): when this trial's search began

    @property
    def key(self) -> str:
        return f"{self.run_id}#{self.trial}"


def iter_trials(ledger_dir: Path | None = None, *, family: str | None = None) -> list[TrialRecord]:
    """Every trial in the ledger (optionally one family), orphans included.

    Strict: an invalid shard raises ``LedgerError`` instead of being skipped. A reader
    that quietly drops a tampered shard would turn tampering into an undercount.
    """
    out: list[TrialRecord] = []
    for path in shard_paths(ledger_dir):
        report = verify_shard(path)
        if not report.ok:
            raise LedgerError(f"{path.name} is invalid: {report.errors[:3]}")
        if family is not None and report.family != family:
            continue
        rows = [json.loads(l) for l in path.read_bytes().split(b"\n") if l]
        head = rows[0]
        close = rows[-1] if rows[-1]["type"] == "run_close" else None
        outcomes = {r["trial"]: r for r in rows if r["type"] == "outcome"}
        for r in rows:
            if r["type"] != "intent":
                continue
            o = outcomes.get(r["trial"])
            out.append(TrialRecord(
                run_id=head["run_id"], trial=r["trial"], family=head["family"],
                hypothesis=head["hypothesis"], producer=head["producer"], code=head["code"],
                spec_hash=r["spec_hash"], spec=r["spec"],
                status=o["status"] if o else "orphan",
                metrics=decode_metrics(o["metrics"]) if o and o.get("metrics") else None,
                returns_sha=o.get("returns_sha") if o else None,
                bundle_sha=close.get("bundle_sha") if close else None,
                opened_at=head["at"]))
    return out


def load_returns(records: Iterable[TrialRecord], ledger_dir: Path | None = None) -> dict:
    """``{record.key: pandas Series}`` of trade returns for records that carry them.

    Bundles are read once each and verified against their address. A record whose
    bundle was never written (a crashed run) has no series and is omitted; it still
    counts wherever ``iter_trials`` is used for counting.
    """
    import pandas as pd

    artifacts = (Path(ledger_dir) if ledger_dir is not None else LEDGER_DIR) / ARTIFACTS
    bundles: dict[str, dict] = {}
    out = {}
    for rec in records:
        if rec.returns_sha is None or rec.bundle_sha is None:
            continue
        if rec.bundle_sha not in bundles:
            bundles[rec.bundle_sha] = read_bundle(artifacts, rec.bundle_sha)
        pairs = bundles[rec.bundle_sha][rec.returns_sha]
        out[rec.key] = pd.Series([v for _, v in pairs],
                                 index=pd.to_datetime([t for t, _ in pairs]), dtype=float)
    return out


# ── history ──────────────────────────────────────────────────────────────────
def verify_history(base_ref: str, rel_dir: Path, *, rule, repo: Path = REPO,
                   what: str = "file") -> list[str]:
    """Files under ``rel_dir`` at merge-base(HEAD, base_ref) survive unedited.

    ``rule(rel_path)`` returns ``"prefix"`` (the file may only grow: an append-only log),
    ``"identical"`` (the file may never change: a frozen record) or ``None`` (not
    governed: ordinary editable text such as a README). Deletions of governed files are
    violations. The merge-base is used so a branch is judged only on what it inherited,
    not on sibling work it lacks. Shared by every append-only store in src/research/.
    """
    mb = _git(repo, "merge-base", "HEAD", base_ref)
    if mb.returncode != 0:
        return [f"cannot resolve merge-base with {base_ref!r}: "
                f"{mb.stderr.decode(errors='replace').strip()}"]
    base = mb.stdout.decode().strip()
    listing = _git(repo, "ls-tree", "-r", "-z", "--name-only", base, "--", Path(rel_dir).as_posix())
    if listing.returncode != 0:
        return [f"cannot list {rel_dir} at {base[:12]}"]
    problems = _branch_walk(base, rel_dir, rule=rule, repo=repo, what=what)
    for rel in (p for p in listing.stdout.decode().split("\0") if p):
        mode = rule(rel)
        if mode is None:
            continue
        blob = _git(repo, "show", f"{base}:{rel}")
        if blob.returncode != 0:
            problems.append(f"{rel}: unreadable at {base[:12]}")
            continue
        try:
            now = (repo / rel).read_bytes()
        except FileNotFoundError:
            problems.append(f"{rel}: deleted ({what} present at {base[:12]})")
            continue
        if mode == "identical" and now != blob.stdout:
            problems.append(f"{rel}: {what} changed since {base[:12]}")
        elif mode == "prefix" and not now.startswith(blob.stdout):
            problems.append(f"{rel}: rewritten since {base[:12]} (not an append)")
    return problems


def _branch_walk(base: str, rel_dir: Path, *, rule, repo: Path, what: str) -> list[str]:
    """The same rule, between every consecutive pair of commits on this branch.

    Comparing only against the merge-base misses a record that was committed on the
    branch and then rewritten or deleted before merge (harness red-team round 2, 5b':
    an upheld objection committed, then cut out). Walking base..HEAD, then HEAD..working
    tree, catches it: once a governed file exists in any commit, every later state must
    keep it as a prefix (or identical). A file that never reached a commit cannot be
    witnessed by git at all; that limit is documented, not hidden.
    """
    revs = _git(repo, "rev-list", "--reverse", "--first-parent", f"{base}..HEAD")
    if revs.returncode != 0:
        return [f"cannot list commits since {base[:12]}"]
    states = [c for c in revs.stdout.decode().split() if c]
    problems, prev = [], {}
    for commit in states + [None]:  # None = the working tree
        if commit is None:
            listing = [str(p.relative_to(repo)) for p in (repo / rel_dir).rglob("*") if p.is_file()] \
                if (repo / rel_dir).is_dir() else []
        else:
            ls = _git(repo, "ls-tree", "-r", "-z", "--name-only", commit, "--", Path(rel_dir).as_posix())
            listing = [p for p in ls.stdout.decode().split("\0") if p]
        current = {}
        for rel in listing:
            rel = Path(rel).as_posix()
            if rule(rel) is None:
                continue
            if commit is None:
                current[rel] = (repo / rel).read_bytes()
            else:
                current[rel] = _git(repo, "show", f"{commit}:{rel}").stdout
        where = commit[:12] if commit else "the working tree"
        for rel, old in prev.items():
            if rel not in current:
                problems.append(f"{rel}: deleted in {where} ({what} committed earlier on this branch)")
            elif rule(rel) == "identical" and current[rel] != old:
                problems.append(f"{rel}: {what} changed in {where} after being committed on this branch")
            elif rule(rel) == "prefix" and not current[rel].startswith(old):
                problems.append(f"{rel}: rewritten in {where} after being committed on this branch")
        prev = current
    return sorted(set(problems))


def verify_append_only(base_ref: str, *, repo: Path = REPO, ledger_rel: Path = LEDGER_REL) -> list[str]:
    """The ledger's history rule: shards may only grow, artifacts never change."""
    def rule(rel: str):
        p = Path(rel)
        if p.parent.as_posix() == (ledger_rel / ARTIFACTS).as_posix() and p.name.endswith(".json.gz"):
            return "identical"
        if p.parent.as_posix() == ledger_rel.as_posix() and p.name.endswith(".jsonl") \
                and _RUN_ID.match(p.stem):
            return "prefix"
        return None  # documentation beside the ledger is ordinary, editable text
    return verify_history(base_ref, ledger_rel, rule=rule, repo=repo, what="ledger file")


# ── repair of a crashed, uncommitted run ─────────────────────────────────────
def seal(path: Path, *, repo: Path = REPO) -> str:
    """Close a run whose process died. Returns a one-line description of what it did.

    Refuses if the run is alive (its flock is held), already closed, or already
    committed at HEAD (committed history is append-only; a committed unclosed shard
    is sealed by appending, which is still allowed, but a committed TORN shard is
    not repaired here because truncation would rewrite history).

    A torn final row is dropped. That loses no count: an intent is fsynced before
    the caller computes anything, so a torn intent is a trial that never ran; a torn
    outcome leaves its (durable) intent as an orphan, which still counts.
    """
    path = Path(path)
    report = verify_shard(path)
    if report.closed:
        raise LedgerError(f"{path.name} is already closed")
    with open(path, "r+b") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise LedgerError(f"{path.name} is held by a live process") from None
            raise
        raw = fh.read()
        lines, torn = _split_lines(raw)
        dropped = 0
        if torn:
            try:
                rel = path.resolve().relative_to(repo.resolve()).as_posix()
            except ValueError:
                rel = None
            if rel is not None and _git(repo, "cat-file", "-e", f"HEAD:{rel}").returncode == 0:
                raise LedgerError(f"{path.name} is committed with a torn row; it cannot be truncated")
            keep = raw[: len(raw) - len(lines[-1])]
            fh.seek(0)
            fh.truncate(len(keep))
            lines = lines[:-1]
            dropped = 1
        if not lines:
            raise LedgerError(f"{path.name} holds no rows (the run died before run_open); "
                              "there is nothing to seal and no trial to count")
        report = verify_shard(path)
        if report.errors:
            raise LedgerError(f"{path.name} has errors besides a torn tail: {report.errors[:3]}")
        last = json.loads(lines[-1].decode("utf-8"))
        prev = hashlib.sha256(lines[-1]).hexdigest()
        row = {"v": SCHEMA_VERSION, "seq": last["seq"] + 1, "prev": prev, "type": "run_close",
               "at": _now(), "status": "crashed", "n_intents": report.intents,
               "n_outcomes": sum(report.outcomes.values()), "bundle_sha": None}
        fh.seek(0, os.SEEK_END)
        fh.write((canonical_json(row, nonfinite="encode") + "\n").encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())
    return (f"sealed {path.name}: {report.intents} intents, {report.orphans} orphaned"
            + (", dropped 1 torn row" if dropped else ""))
