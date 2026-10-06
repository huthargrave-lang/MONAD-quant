"""
MONAD Quant — Recording a daily-strategy evaluation as a ledger trial.

One definition of what a daily trial's spec and outcome contain, shared by the search
producer (tools/domain_search.py) and the admission gate, so a trial means the same thing
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

#: A DOMAIN is one research question with one benchmark: ETF timing against the static
#: 60/40, and closed-end-fund selection against the equal-weight CEF universe. Trials of
#: different domains answer different questions against different benchmarks, so they
#: are never pooled into one familywise test; within a domain, membership is structural.
DOMAINS = {
    "etf_alloc": {"family": "daily_alloc", "reference_class": "static_6040"},
    "cef_discount": {"family": "cef_discount", "reference_class": "cef_equal_weight"},
    "crypto_trend": {"family": "crypto_trend", "reference_class": "crypto_static_half"},
    "country_select": {"family": "country_select", "reference_class": "country_equal_weight"},
    "bdc_discount": {"family": "bdc_discount", "reference_class": "bdc_equal_weight"},
    "insider_cluster": {"family": "insider_cluster", "reference_class": "insider_index"},
    "mreit_discount": {"family": "mreit_discount", "reference_class": "mreit_equal_weight"},
}
DEFAULT_DOMAIN = "etf_alloc"      # trials recorded before domains existed (the v1 search)


def family_name(domain: str, *, reference: bool = False) -> str:
    base = DOMAINS[domain]["family"]
    return f"{base}{'_reference' if reference else ''}.v{EVALUATOR_VERSION}"


DAILY_FAMILY = family_name("etf_alloc")
REFERENCE_FAMILY = family_name("etf_alloc", reference=True)
CEF_FAMILY = family_name("cef_discount")
CEF_REFERENCE_FAMILY = family_name("cef_discount", reference=True)
REFERENCE_CLASS = DOMAINS["etf_alloc"]["reference_class"]
REFERENCE_CLASSES = frozenset(d["reference_class"] for d in DOMAINS.values())


def daily_spec(point: Mapping, *, cost_multiple: float = 1.0, domain: str = DEFAULT_DOMAIN) -> dict:
    if domain not in DOMAINS:
        raise ValueError(f"unknown domain {domain!r}")
    spec = {"evaluator": {"name": EVALUATOR_NAME, "version": EVALUATOR_VERSION},
            "class": point["class"], "params": dict(point["params"]),
            "cost_multiple": float(cost_multiple)}
    if domain != DEFAULT_DOMAIN:
        spec["domain"] = domain       # absent = the default, so v1 trials keep their hashes
    return spec


def daily_data_spec(snapshot_sha: str, start, end, *, panel_sha: str | None = None) -> dict:
    """``panel_sha``: the NAV panel a domain decides from (CEFNAV-* or BDCNAV-*)."""
    data = {"snapshot": snapshot_sha, "start": pd.Timestamp(start).date().isoformat(),
            "end": pd.Timestamp(end).date().isoformat()}
    if panel_sha is not None:
        data["nav_panel"] = panel_sha
    return data


def trial_domain(record) -> str:
    params = (record.spec or {}).get("params") or {}
    return params.get("domain", DEFAULT_DOMAIN) if isinstance(params, dict) else DEFAULT_DOMAIN


def is_daily_trial(record, *, version: int = EVALUATOR_VERSION) -> bool:
    params = (record.spec or {}).get("params") or {}
    ev = params.get("evaluator") if isinstance(params, dict) else None
    return (isinstance(ev, dict) and ev.get("name") == EVALUATOR_NAME
            and ev.get("version") == version)


def parse_family(family: str) -> tuple[str, bool, int]:
    """(domain, is_reference, version) of a daily family name."""
    base, _, version = family.rpartition(".v")
    reference = base.endswith("_reference")
    base = base[: -len("_reference")] if reference else base
    for domain, d in DOMAINS.items():
        if d["family"] == base:
            return domain, reference, int(version)
    raise ValueError(f"{family!r} is not a daily family")


def daily_family_members(records, family: str) -> list:
    """Members of a daily family: its label, OR any trial of the same evaluator version
    AND domain under ANY label (a search run under a scratch label is still this search:
    red-team attack 4a). Reference-class trials belong to the domain's reference family."""
    domain, reference, version = parse_family(family)
    ref_class = DOMAINS[domain]["reference_class"]
    out = []
    for r in records:
        if r.family == family:
            out.append(r)
            continue
        if not is_daily_trial(r, version=version) or trial_domain(r) != domain:
            continue
        is_ref = (r.spec.get("params") or {}).get("class") == ref_class
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


def live_registrations(family: str, prereg_dir=None, verdict_dir=None) -> list[str]:
    """Hypotheses registered to ``family`` that have no final verdict (ADMIT or REJECT on
    record). New trials in the family count against each of them at its next gate run,
    and can move a passing deflation below its bar (F404708)."""
    import json
    from pathlib import Path
    from src.research import prereg

    base = Path(prereg_dir) if prereg_dir is not None else prereg.PREREG_DIR
    verdicts = Path(verdict_dir) if verdict_dir is not None else prereg.REPO / "docs/research/verdicts"
    live = []
    for path in sorted(base.glob("H*.json")) if base.is_dir() else []:
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec.get("family") != family:
            continue
        final = False
        for v in sorted((verdicts / spec["hypothesis"]).glob("*.json")) if (verdicts / spec["hypothesis"]).is_dir() else []:
            if json.loads(v.read_text(encoding="utf-8")).get("verdict") in ("ADMIT", "REJECT"):
                final = True
        if not final:
            live.append(spec["hypothesis"])
    return live


def refuse_unacknowledged(family: str, acknowledged: list[str] | None) -> None:
    """Raise SystemExit unless every live registration in ``family`` is acknowledged."""
    live = live_registrations(family)
    missing = sorted(set(live) - set(acknowledged or ()))
    if missing:
        raise SystemExit(
            f"family {family} holds live registered hypotheses {missing}: every new trial here "
            f"counts against them at their next gate run and can push a passing deflation "
            f"below its bar (F404708). Re-run with --acknowledge-live {' '.join(missing)} to "
            f"accept that cost.")
