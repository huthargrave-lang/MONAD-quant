"""
countedtrials — ``Study``: count a search without changing how you write it.

    import countedtrials as ct

    def backtest(fast, slow):            # any function of its parameters ...
        return strategy_returns          # ... returning a pandas Series of returns

    with ct.Study("ma_crossover.v1", ledger_dir="trials") as study:
        study.search(backtest, {"fast": [5, 10, 20], "slow": [50, 100, 200]})
        print(study.report())

Run it from inside your git repository: each run records the commit and whether the
working tree was dirty, read from the working directory.

Each evaluation writes its intent (the parameters, hashed) to disk BEFORE the function
runs, and its outcome after. A configuration that raises is recorded as an ``error``; one
you interrupt is recorded as ``abandoned``; one whose process is killed stays an orphan.
All of them are in the count ``report`` deflates by. Runs accumulate: rerun the script
next week with a wider grid and the family's N is the sum of everything ever tried under
that family name, which is the number that matters.

Works with any backtester: the only contract is "parameters in, returns series out".
"""
from __future__ import annotations

import inspect
import itertools
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import numpy as np
import pandas as pd

from countedtrials import analysis, ledger
from countedtrials import significance as sig
from countedtrials.guard import evaluation


@dataclass
class TrialResult:
    key: str                    # "<run_id>#<trial>": pass it to deflate()
    params: dict
    status: str                 # ok | error
    returns: pd.Series | None
    metrics: dict
    error: str | None = None

    @property
    def sharpe(self) -> float:
        """Per-period Sharpe of the returned series (NaN when undefined)."""
        return self.metrics.get("sharpe", math.nan)


def expand_grid(grid) -> list[dict]:
    """``{"a": [1, 2], "b": [3]}`` -> ``[{"a": 1, "b": 3}, {"a": 2, "b": 3}]``; an
    iterable of dicts is passed through."""
    if isinstance(grid, Mapping):
        names = list(grid)
        return [dict(zip(names, combo)) for combo in itertools.product(*(grid[n] for n in names))]
    return [dict(p) for p in grid]


def _unpack(out) -> tuple[pd.Series | None, dict]:
    extra: dict = {}
    if isinstance(out, tuple) and len(out) == 2 and isinstance(out[1], Mapping):
        out, extra = out[0], dict(out[1])
    if out is None:
        return None, extra
    if not isinstance(out, pd.Series):
        raise ledger.LedgerError(
            f"a counted function must return a pandas Series of returns indexed by time "
            f"(or (series, metrics dict), or None for 'no trades'); got {type(out).__name__}")
    return _check_returns(out), extra


def _check_returns(returns: pd.Series) -> pd.Series:
    """Refuse, at write time, a series the readers could not use later. The ledger is
    append-only: a trial stored with an unparseable index would make its whole family
    unreadable for good, so the check belongs before the outcome is written.

    A timezone-aware index is reduced to its LOCAL wall-clock time: the verdict statistics
    work on calendar dates, and converting to UTC would move an Asian or early-morning
    session onto the previous day."""
    if not len(returns):
        return returns
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise ledger.LedgerError(
            f"returns must be indexed by a pandas DatetimeIndex (got {type(returns.index).__name__}); "
            f"the statistics align trials by date")
    if returns.isna().any() or not np.isfinite(returns.to_numpy(dtype=float)).all():
        raise ledger.LedgerError(
            f"returns contain {int((~np.isfinite(returns.to_numpy(dtype=float))).sum())} non-finite "
            f"value(s); a leading NaN from pct_change() is the usual cause (fillna(0.0) or drop it)")
    if returns.index.tz is not None:
        returns = returns.copy()
        returns.index = returns.index.tz_localize(None)
    return returns


def _basic_metrics(returns: pd.Series | None) -> dict:
    if returns is None or len(returns) == 0:
        return {"n": 0, "sharpe": math.nan}
    try:
        return {"n": int(len(returns)), "sharpe": sig.sharpe_moments(returns).sharpe}
    except ValueError:
        return {"n": int(len(returns)), "sharpe": math.nan}


class Study:
    """One counted run of a search over one idea (``family``)."""

    def __init__(self, family: str, *, ledger_dir: Path | str | None = None,
                 producer: str | None = None, hypothesis: str | None = None,
                 context: Mapping[str, Any] | None = None, data: Mapping[str, Any] | None = None):
        self.family = family
        self.ledger_dir = Path(ledger_dir) if ledger_dir is not None else ledger.default_ledger_dir()
        self.producer = producer or Path(sys.argv[0] or "interactive").name or "interactive"
        #: Identifies the data every trial ran on (e.g. {"symbol": "SPY", "sha256": ...}); it is
        #: part of each trial's spec hash, so the same parameters on different data are different trials.
        self.data = dict(data) if data is not None else None
        self.hypothesis = hypothesis
        self.context = dict(context) if context is not None else None
        self._ctx: ledger.open_run | None = None
        self.run: ledger.Run | None = None
        self._entered = False
        self.results: list[TrialResult] = []

    # -- lifecycle
    def _open(self) -> None:
        self._ctx = ledger.open_run(producer=self.producer, family=self.family,
                                    hypothesis=self.hypothesis, context=self.context,
                                    ledger_dir=self.ledger_dir)
        self.run = self._ctx.__enter__()

    def __enter__(self) -> "Study":
        self._entered = True
        self._open()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._entered = False
        if self.run is None or self.run._closed:   # a verdict already closed the run
            return False
        return self._ctx.__exit__(exc_type, exc, tb)

    def _need_run(self) -> ledger.Run:
        if not self._entered:
            raise ledger.LedgerError("use the Study as a context manager: `with Study(...) as study:`")
        if self.run._closed:
            # A verdict (report/deflate/spa/best) closed the previous run so its series could
            # be read. Searching on after looking is a new run in the same family, and the
            # ledger shows it as one: the look happened between two shards.
            self._open()
        return self.run

    # -- counting
    def evaluate(self, fn: Callable[..., Any], params: Mapping[str, Any], *,
                 reraise: bool = True) -> TrialResult:
        """One counted trial: record the intent, call ``fn(**params)``, record the outcome.

        An exception from ``fn`` is recorded as an ``error`` outcome and then re-raised
        (``reraise=False`` returns the failed ``TrialResult`` instead). Either way the
        attempt stays in the count.
        """
        run = self._need_run()
        params = dict(params)
        trial = run.begin(params, data=self.data,
                          extra={"fn": getattr(fn, "__qualname__", repr(fn))})
        key = f"{run.run_id}#{trial.index}"
        try:
            with evaluation(getattr(fn, "__name__", "evaluate")):
                returns, extra = _unpack(fn(**params))
            metrics = {**_basic_metrics(returns), **extra}
            trial.complete(metrics, returns=returns if returns is not None and len(returns) else None)
        except Exception as exc:
            # KeyboardInterrupt/SystemExit are not caught: the trial keeps its intent and
            # is closed as ``abandoned`` with the run, which is what happened to it.
            if not trial.done:
                trial.fail(f"{type(exc).__name__}: {exc}")
            if reraise:
                raise
            result = TrialResult(key=key, params=params, status="error", returns=None,
                                 metrics={}, error=f"{type(exc).__name__}: {exc}")
        else:
            result = TrialResult(key=key, params=params, status="ok", returns=returns, metrics=metrics)
        self.results.append(result)
        return result

    def search(self, fn: Callable[..., Any], grid) -> list[TrialResult]:
        """Evaluate every point of ``grid`` (a dict of lists, or an iterable of dicts).
        A point that raises is recorded as an error and the search continues."""
        return [self.evaluate(fn, p, reraise=False) for p in expand_grid(grid)]

    def counted(self, fn: Callable[..., Any]) -> Callable[..., pd.Series | None]:
        """Decorator form: every call of the returned function is one counted trial and
        returns ``fn``'s series. Positional arguments are recorded under ``fn``'s parameter
        names. To drive an optimizer, wrap it once more to return the scalar it wants."""
        signature = inspect.signature(fn)

        def wrapper(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            return self.evaluate(fn, dict(bound.arguments)).returns
        wrapper.__name__ = getattr(fn, "__name__", "counted")
        wrapper.__doc__ = fn.__doc__
        return wrapper

    # -- verdicts (over the WHOLE family on disk, not only this run)
    def best(self) -> str:
        self._flush()
        return analysis.best_trial(self.family, ledger_dir=self.ledger_dir)

    def deflate(self, candidate: str | None = None, **kwargs) -> analysis.FamilyDeflation:
        self._flush()
        return analysis.deflate(candidate or self.best(), ledger_dir=self.ledger_dir, **kwargs)

    def spa(self, candidate: str | None = None, *, benchmark: pd.Series | None = None,
            **kwargs) -> analysis.FamilySPA:
        self._flush()
        return analysis.family_spa(candidate or self.best(), benchmark=benchmark,
                                   ledger_dir=self.ledger_dir, **kwargs)

    def report(self, candidate: str | None = None, *, benchmark: pd.Series | None = None,
               **kwargs) -> analysis.FamilyReport:
        self._flush()
        return analysis.report(self.family, candidate=candidate, benchmark=benchmark,
                               ledger_dir=self.ledger_dir, **kwargs)

    def _flush(self) -> None:
        """Return series are bundled at run close; close this run so they can be read.
        The next ``evaluate`` opens a new run (see ``_need_run``)."""
        if self.run is not None and not self.run._closed:
            self._ctx.__exit__(None, None, None)
