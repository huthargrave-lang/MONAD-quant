"""
MONAD Quant — Deflating one candidate by everything its family tried.

Joins the trial ledger (``trials.py``) to the significance kernel (``significance.py``):
given one recorded trial (the candidate someone wants to call an edge), read every trial
in its family, collapse them to independent ideas, and compute the candidate's Deflated
Sharpe Ratio against the search that found it.

How the trial count is built (conservative at every fork):

  * membership is ``backtest_trials.family_members``: the family's label, plus, for an
    MR family, every hourly engine trial on the same symbol under ANY label;

  * trials with a return series are clustered by daily-PnL correlation
    (``significance.effective_trials``); the conservative max of the cluster count and
    the Li-Ji eigenvalue count is used;
  * ``ok`` trials with no trades are one "found nothing" idea (inside effective_trials);
  * trials whose result is UNKNOWN (``error``, ``abandoned``, crash ``orphan``) cannot be
    correlated with anything, so each distinct spec among them adds one independent
    trial, unless the same spec also produced an ``ok`` result elsewhere in the family.

The candidate's Sharpe, skew, kurtosis and T are measured on its own daily PnL over its
active span (first to last trading day), the same basis the cluster Sharpes use.

``exclude_producers`` (the admission gate passes itself): trials those producers wrote are
left out of N, except the candidate. The gate re-runs a FROZEN spec; its cost-stress and
forward runs cannot have chosen that spec. Every other family trial counts, whenever it
ran: a cutoff at the author-written ``registered_at`` let a backdated registration drop
the real search from N (harness red-team round 2, 7a').

``searched_before`` (diagnostic only; the gate no longer uses it): only
trials whose run opened before it count toward N, plus the candidate itself. A frozen
spec cannot have been chosen by trials run after it was frozen (the gate's own cost
stress and forward runs, or a later search); those count against the NEXT hypothesis in
the family, not this one. Without a cutoff every recorded trial counts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from src.research import significance as sig
from src.research import trials

#: Business days per year, for DISPLAY ONLY. The DSR itself is computed per period.
PERIODS_PER_YEAR = 252


@dataclass
class FamilyDeflation:
    family: str
    candidate: str                 # "<run_id>#<trial>"
    trials_recorded: int           # every intent in the family that counts (see searched_before)
    trials_with_returns: int
    unknown_specs_added: int       # distinct error/abandoned/orphan specs counted as +1 each
    effective: sig.EffectiveTrials
    n_trials: float                # the N the DSR used
    moments: sig.SharpeMoments
    result: sig.DeflatedSharpe

    @property
    def annualized_sharpe(self) -> float:
        return self.moments.sharpe * math.sqrt(PERIODS_PER_YEAR)

    @property
    def annualized_sr0(self) -> float:
        return self.result.sr0 * math.sqrt(PERIODS_PER_YEAR)


def deflate_candidate(candidate: str, *, ledger_dir: Path | None = None,
                      searched_before=None, exclude_producers=()) -> FamilyDeflation:
    """DSR of trial ``candidate`` ("<run_id>#<trial>") against its family's search."""
    run_id, _, idx = candidate.partition("#")
    if not idx.isdigit():
        raise ValueError(f"candidate must look like <run_id>#<trial>, got {candidate!r}")
    everything = trials.iter_trials(ledger_dir)
    target = next((r for r in everything if r.run_id == run_id and r.trial == int(idx)), None)
    if target is None:
        raise ValueError(f"no trial {candidate} in the ledger")
    if target.status != "ok":
        raise ValueError(f"{candidate} has status {target.status!r}; only an ok trial can be deflated")
    from src.research.backtest_trials import family_members
    family = family_members(everything, target.family)
    if exclude_producers:
        family = [r for r in family
                  if r.key == target.key or r.producer not in set(exclude_producers)]
    if searched_before is not None:
        import pandas as pd
        cutoff = pd.Timestamp(searched_before)
        cutoff = cutoff.tz_convert("UTC") if cutoff.tzinfo else cutoff.tz_localize("UTC")
        family = [r for r in family
                  if r.key == target.key or pd.Timestamp(r.opened_at) < cutoff]

    series = trials.load_returns(family, ledger_dir)
    if target.key not in series:
        raise ValueError(f"{candidate} recorded no trade returns; there is nothing to deflate")
    # ok trials without trades enter as empty series: the "found nothing" idea.
    import pandas as pd
    for r in family:
        if r.status == "ok" and r.key not in series:
            series[r.key] = pd.Series(dtype=float)
    eff = sig.effective_trials(series)

    ok_specs = {r.spec_hash for r in family if r.status == "ok"}
    unknown = {r.spec_hash for r in family if r.status != "ok"} - ok_specs
    n_trials = eff.n_effective + len(unknown)

    pnl = sig.daily_pnl({target.key: series[target.key]})[target.key]
    moments = sig.sharpe_moments(sig.active_span(pnl))
    result = sig.deflated_sharpe(moments.sharpe, n_trials=n_trials,
                                 sharpe_variance=eff.sharpe_variance, n_obs=moments.n_obs,
                                 skew=moments.skew, kurtosis=moments.kurtosis)
    return FamilyDeflation(family=target.family, candidate=target.key,
                           trials_recorded=len(family),
                           trials_with_returns=sum(1 for k, v in series.items() if len(v)),
                           unknown_specs_added=len(unknown), effective=eff,
                           n_trials=n_trials, moments=moments, result=result)
