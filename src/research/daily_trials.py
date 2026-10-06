"""
MONAD Quant — Recording a daily-strategy evaluation as a ledger trial.

One definition of what a daily trial's spec and outcome contain, shared by the search
producer (tools/daily_search.py) and the admission gate, so a trial means the same thing
whichever wrote it (the same rule ``backtest_trials`` applies to engine backtests).

Spec ``params``::

    {"evaluator": {"name": "daily_strategy", "version": 1},
     "class": "tsmom", "params": {...}, "cost_multiple": 1.0}

Spec ``data``::

    {"snapshot": "<DS sha>", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

Outcome: metrics (annualized excess Sharpe, CAGR, max drawdown, turnover, rebalances,
cost paid) and the per-session portfolio return series. Active series are NOT stored:
they are derived from the strategy's and the reference's stored returns on the same
snapshot and window, so the reference definition lives in one place.

Families: ``DAILY_FAMILY`` holds the search; the static 60/40 reference is recorded in
``REFERENCE_FAMILY``, still counted, but not a search point (a benchmark that could be
"selected" as a candidate, and that inflated N, would distort both).
"""
from __future__ import annotations

import math
from typing import Mapping

import numpy as np
import pandas as pd

from src.research.daily_strategy import EVALUATOR_NAME, EVALUATOR_VERSION, DailyResult
from src.research.trials import LedgerError, Trial

DAILY_FAMILY = f"daily_alloc.v{EVALUATOR_VERSION}"
REFERENCE_FAMILY = f"daily_alloc_reference.v{EVALUATOR_VERSION}"
REFERENCE_CLASS = "static_6040"


def daily_spec(point: Mapping, *, cost_multiple: float = 1.0) -> dict:
    return {"evaluator": {"name": EVALUATOR_NAME, "version": EVALUATOR_VERSION},
            "class": point["class"], "params": dict(point["params"]),
            "cost_multiple": float(cost_multiple)}


def daily_data_spec(snapshot_sha: str, start, end) -> dict:
    return {"snapshot": snapshot_sha, "start": pd.Timestamp(start).date().isoformat(),
            "end": pd.Timestamp(end).date().isoformat()}


def is_daily_trial(record, *, version: int = EVALUATOR_VERSION) -> bool:
    params = (record.spec or {}).get("params") or {}
    ev = params.get("evaluator") if isinstance(params, dict) else None
    return (isinstance(ev, dict) and ev.get("name") == EVALUATOR_NAME
            and ev.get("version") == version)


def daily_family_members(records, family: str) -> list:
    """Members of a daily family: its label, OR any trial of the same evaluator version
    under ANY label (a search run under a scratch label is still this search: red-team
    attack 4a), except reference-class trials, which belong to the reference family."""
    version = int(family.rsplit(".v", 1)[1])
    reference = family.startswith("daily_alloc_reference.")
    out = []
    for r in records:
        if r.family == family:
            out.append(r)
            continue
        if not is_daily_trial(r, version=version):
            continue
        is_ref = (r.spec.get("params") or {}).get("class") == REFERENCE_CLASS
        if is_ref == reference:
            out.append(r)
    return out


def daily_metrics(result: DailyResult) -> dict:
    r = result.returns
    ex = result.excess
    sd = float(ex.std(ddof=1))
    equity = (1.0 + r).cumprod()
    years = len(r) / 252.0
    return {"sessions": int(len(r)),
            "excess_sharpe": float(ex.mean() / sd * math.sqrt(252)) if sd > 0 else 0.0,
            "cagr": float(equity.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 else 0.0,
            "max_drawdown": float((equity / equity.cummax() - 1.0).min()),
            "rebalances": int(result.rebalances),
            "turnover_per_year": float(result.turnover / years) if years > 0 else 0.0,
            "cost_per_year": float(result.cost_paid / years) if years > 0 else 0.0,
            "mean_exposure": float(result.exposure.mean())}


def record_daily(trial: Trial, result: DailyResult) -> None:
    """Write ``result`` as ``trial``'s outcome. An unencodable result (a NaN return) is a
    defect in the result, recorded as an error rather than lost."""
    try:
        if not np.all(np.isfinite(result.returns.to_numpy())):
            raise LedgerError("the return series contains non-finite values")
        trial.complete(metrics=daily_metrics(result), returns=result.returns)
    except LedgerError as exc:
        trial.fail(f"unrecordable daily result: {exc}")


def stored_returns(series: pd.Series) -> pd.Series:
    """A ledger-loaded return series (timestamps as strings) as a session-indexed Series."""
    idx = pd.DatetimeIndex(pd.to_datetime(series.index)).normalize()
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    return pd.Series(np.asarray(series, dtype=float), index=idx)
