"""
countedtrials — The evaluation guard: a backtest function that refuses to run uncounted.

PORTED from MONAD Quant ``src/strategy/counted.py``. A trial count is honest only if
nothing can evaluate a strategy without writing to the ledger. Reading source to check
that every call site counts was tried there first and was evaded with aliases and
``getattr``; so the check moved to runtime:

  * ``Run.begin`` issues ONE token; the first top-level evaluation spends it, so one
    trial authorises exactly one evaluation, and a second raises;
  * evaluations nested inside one pass;
  * a trial's outcome clears its token by IDENTITY, never ``ContextVar.reset``, which
    can restore a stale token when trials end out of order; ``begin`` refuses while an
    unspent token is live;
  * ``uncounted(reason)`` is the one explicit bypass. MONAD restricts it to an allowlist
    of files; a library cannot know your tree, so here it only demands a written reason.
    It is greppable: ``grep -rn "uncounted(" .`` lists every evaluation that was not
    counted, with why.

Decorate your backtest entry point with ``@evaluator`` and it cannot be called outside a
begun trial:

    @countedtrials.evaluator
    def run_backtest(prices, fast, slow): ...
"""
from __future__ import annotations

import contextlib
import contextvars
import functools
from dataclasses import dataclass
from typing import Any


class UncountedEvaluationError(RuntimeError):
    """A strategy was about to be evaluated with no trial to count it."""


@dataclass
class _Token:
    owner: Any
    consumed: bool = False


_TOKEN: contextvars.ContextVar = contextvars.ContextVar("countedtrials_token", default=None)
_DEPTH: contextvars.ContextVar = contextvars.ContextVar("countedtrials_depth", default=0)
_UNCOUNTED: contextvars.ContextVar = contextvars.ContextVar("countedtrials_uncounted", default=None)


@contextlib.contextmanager
def evaluation(entry: str):
    """One evaluation: at depth 0 it spends the active token (or runs inside an
    ``uncounted`` block); nested evaluations pass."""
    depth = _DEPTH.get()
    token = _TOKEN.get()
    if depth == 0 and token is not None and not token.consumed:
        token.consumed = True  # a begun trial is always spent, even inside uncounted()
    elif depth == 0 and _UNCOUNTED.get() is None:
        if token is None:
            raise UncountedEvaluationError(
                f"{entry} was called with no begun trial. Count it: evaluate through a "
                f"countedtrials.Study, or open_run(...) then run.begin(...) first")
        raise UncountedEvaluationError(
            f"{entry}: this trial already evaluated once; one trial is one evaluation. "
            f"Begin a new trial for the next one")
    handle = _DEPTH.set(depth + 1)
    try:
        yield
    finally:
        _DEPTH.reset(handle)


def evaluator(fn):
    """Decorate a backtest entry point so every call runs inside ``evaluation``."""
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        with evaluation(fn.__name__):
            return fn(*args, **kwargs)
    return wrapped


@contextlib.contextmanager
def uncounted(reason: str):
    """Evaluate without a trial, on the record: ``with uncounted("unit test of fills"):``."""
    if not isinstance(reason, str) or len(reason.strip()) < 10:
        raise UncountedEvaluationError("uncounted() needs a reason (>= 10 characters)")
    handle = _UNCOUNTED.set(reason)
    try:
        yield
    finally:
        _UNCOUNTED.reset(handle)


def issue_token(owner) -> None:
    """Called by ``Run.begin``: one token for one evaluation by ``owner``."""
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
