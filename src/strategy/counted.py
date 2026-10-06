"""
MONAD Quant — The engine's evaluation guard: no strategy is evaluated uncounted.

The trial ledger (src/research/trials.py) makes a search's size honest only if nothing
can evaluate a strategy without writing to it. Counting was first enforced by CI reading
source (tests/test_producer_ledger_wiring.py), and an independent red-team evaded that
with aliases, getattr, and scripts outside the scanned tree. So the engine's two
evaluation entry points, ``run_backtest`` and ``compute_trade_returns``, now refuse to
run unless a begun trial holds an unspent token (decision-debate Q2, 2026-09-22):

  * ``Run.begin`` issues ONE token; the first top-level evaluation spends it, so one
    trial authorises exactly one evaluation, and a second raises;
  * evaluations nested inside one (run_backtest -> compute_trade_returns) pass;
  * a trial's outcome clears its token by IDENTITY, never ``ContextVar.reset``, which
    can restore a stale token when trials end out of order; ``begin`` refuses while an
    unspent token is live;
  * ``uncounted(reason)`` is the one explicit bypass, allowed only from ``tests/`` and
    the files in ``UNCOUNTED_ALLOWED``, checked against the caller's path at runtime.

The guarantee covers those two entry points only. Code that pairs ``generate_trades``
(which live/signals.py imports, so it cannot be guarded) with its own return arithmetic
is not covered; tests/test_producer_ledger_wiring.py flags that pattern best-effort.

Why this file lives here and not in src/research/: the engine imports it, and
live/signals.py imports the engine, so it is part of the live bot's import closure
(tools/armed_closure.py) and is tracked by ops/git_drift.sh's ARMED_PATHS. Keeping it
small, stdlib-only and separate keeps the research package out of that closure.
"""
from __future__ import annotations

import contextlib
import contextvars
import functools
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

#: Files outside tests/ allowed to evaluate uncounted, and why. Mirrors the EXEMPT list
#: in tests/test_producer_ledger_wiring.py, which checks the two stay equal.
UNCOUNTED_ALLOWED = {
    "tools/live_backtest_parity.py": "synthetic mechanism panels; measures no instrument",
    "tools/overnight_gap_risk_study.py": "byte-equality crosscheck of the study's own replay",
}


class UncountedEvaluationError(RuntimeError):
    """The engine was asked to evaluate a strategy with no trial to count it."""


@dataclass
class _Token:
    owner: Any
    consumed: bool = False


_TOKEN: contextvars.ContextVar = contextvars.ContextVar("monad_trial_token", default=None)
_DEPTH: contextvars.ContextVar = contextvars.ContextVar("monad_eval_depth", default=0)
_UNCOUNTED: contextvars.ContextVar = contextvars.ContextVar("monad_uncounted", default=None)


@contextlib.contextmanager
def evaluation(entry: str):
    """One engine evaluation: at depth 0 it spends the active token (or runs inside an
    allowed ``uncounted`` block); nested evaluations pass."""
    depth = _DEPTH.get()
    token = _TOKEN.get()
    if depth == 0 and token is not None and not token.consumed:
        token.consumed = True  # a begun trial is always spent, even inside uncounted()
    elif depth == 0 and _UNCOUNTED.get() is None:
        if token is None:
            raise UncountedEvaluationError(
                f"{entry} was called with no begun trial. Count it: trials.open_run(...) "
                f"then run.begin(...) before evaluating (docs/research/trials/README.md)")
        raise UncountedEvaluationError(
            f"{entry}: this trial already evaluated once; one trial is one evaluation. "
            f"Begin a new trial for the next one")
    handle = _DEPTH.set(depth + 1)
    try:
        yield
    finally:
        _DEPTH.reset(handle)


def evaluator(fn):
    """Decorate an engine entry point so every call runs inside ``evaluation``."""
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        with evaluation(fn.__name__):
            return fn(*args, **kwargs)
    return wrapped


@contextlib.contextmanager
def uncounted(reason: str):
    """Evaluate without a trial. Allowed only from tests/ or ``UNCOUNTED_ALLOWED`` files."""
    if not isinstance(reason, str) or len(reason.strip()) < 10:
        raise UncountedEvaluationError("uncounted() needs a reason (>= 10 characters)")
    caller = Path(inspect.stack()[2].filename).resolve()
    try:
        rel = caller.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        rel = None
    if rel is None or not (rel.startswith("tests/") or rel in UNCOUNTED_ALLOWED):
        raise UncountedEvaluationError(
            f"uncounted() is not allowed from {caller}: only tests/ and "
            f"{sorted(UNCOUNTED_ALLOWED)} may evaluate without counting")
    handle = _UNCOUNTED.set(reason)
    try:
        yield
    finally:
        _UNCOUNTED.reset(handle)


def issue_token(owner) -> None:
    """Called by trials.Run.begin: one token for one evaluation by ``owner``."""
    current = _TOKEN.get()
    if current is not None and not current.consumed and current.owner is not owner:
        raise UncountedEvaluationError(
            "a begun trial has not evaluated yet; complete or fail it before beginning another")
    token = _Token(owner=owner)
    owner._token = token
    _TOKEN.set(token)


def clear_token(owner) -> None:
    """Called when ``owner`` gets its outcome: clears the token only if it is still that
    trial's own (identity, not ContextVar.reset)."""
    token = getattr(owner, "_token", None)
    if token is not None and _TOKEN.get() is token:
        _TOKEN.set(None)
