"""
countedtrials — Verdicts read off the ledger: a Sharpe deflated by a MEASURED search.

Every Deflated Sharpe implementation asks the caller for N, the number of trials. That
number is the whole correction, and it is almost always a guess, a memory, or the size
of the final grid. Here nobody types N. It is read from the ledger, which recorded each
attempt before its result existed, and then reduced to the number of INDEPENDENT ideas
those attempts amount to:

  * family members with a return series are clustered by daily-PnL correlation; the
    conservative max of the cluster count and the Li-Ji eigenvalue count is used
    (``significance.effective_trials``);
  * ``ok`` trials with no trades are one "found nothing" idea;
  * trials whose result is UNKNOWN cannot be correlated with anything, so each distinct
    spec among them adds one independent trial, unless the same spec also produced a
    visible result elsewhere in the family. Unknown means ``error``, ``abandoned``, a
    crash ``orphan``, and also an ``ok`` trial whose return series never reached disk:
    series are bundled when a run closes, so a run that was killed (and sealed) or is
    still open has results somebody saw and this module cannot.

Which number to believe. MONAD measured both corrections on synthetic families
(its finding F404718) and the DSR, built this way, is miscalibrated in both directions:
when every trial is a variant of ONE idea the cross-idea Sharpe variance is ~0, so SR0 is
~0 whatever N is and a null candidate passed 12% of the time against a nominal 5%; when
one or two unrelated ideas share the family the variance balloons and a genuine Sharpe of
1.0 over 20 years passed 2% of the time. Hansen's SPA on the same families held its size
(2-7%) and its power (83-100%). So the verdict here is ``family_spa``: the candidate's
familywise p-value over the recorded returns, charged by union bound for every attempt
whose returns the test cannot see. The DSR is reported beside it as a diagnostic, with a
warning when it is degenerate.

The family-deflation logic is MONAD Quant's ``src/research/deflation.py`` without its
repo-specific family-membership rule: here a family is exactly the trials that share the
family label.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from countedtrials import ledger
from countedtrials import significance as sig

#: Business days per year, for DISPLAY ONLY. Every statistic is computed per period.
PERIODS_PER_YEAR = 252
#: Below this many daily observations a DSR is reported with a warning: too thin to mean much.
MIN_OBS = 30
#: Mean block lengths (sessions) of the stationary bootstrap; the WORST p across them is used,
#: so the verdict does not depend on a block length chosen after the fact. MONAD's gate values.
SPA_BLOCKS = (20, 63, 126)
SPA_BOOT = 5000
#: A family member is tested on the candidate's window only if its own active span covers at
#: least this share of it. Others ran on different data; they are charged to ``m`` instead.
#: Fixed in advance so it cannot be tuned per result.
MIN_WINDOW_COVERAGE = 0.8


@dataclass
class FamilyDeflation:
    family: str
    candidate: str                 # "<run_id>#<trial>"
    trials_recorded: int           # every intent in the family
    trials_with_returns: int
    unknown_specs_added: int       # distinct error/abandoned/orphan specs counted as +1 each
    effective: sig.EffectiveTrials
    n_trials: float                # the N the DSR used
    moments: sig.SharpeMoments
    result: sig.DeflatedSharpe
    psr: float                     # P(true Sharpe > 0) had this been the only thing tried
    prior_search_trials: int = 0   # declared attempts made before the ledger existed

    @property
    def degenerate(self) -> bool:
        """More than one trial but no cross-idea variance: SR0 is 0 and the DSR is the PSR."""
        return self.n_trials > 1 and self.result.sr0 == 0.0

    @property
    def annualized_sharpe(self) -> float:
        return self.moments.sharpe * math.sqrt(PERIODS_PER_YEAR)

    @property
    def annualized_sr0(self) -> float:
        return self.result.sr0 * math.sqrt(PERIODS_PER_YEAR)


def _family(ledger_dir, family: str) -> list:
    records = ledger.iter_trials(ledger_dir, family=family)
    if not records:
        raise ValueError(f"no trials recorded for family {family!r}")
    return records


def _series(records, ledger_dir) -> dict:
    """Return series by trial key; ok trials that recorded no trades enter as empty series.
    An ok trial that DID record returns but whose bundle is not on disk gets no entry: it
    is not "found nothing", it is unknown (see ``_unknown_specs``)."""
    series = ledger.load_returns(records, ledger_dir)
    for r in records:
        if r.status == "ok" and r.returns_sha is None:
            series[r.key] = pd.Series(dtype=float)
    return series


def _target(candidate: str, ledger_dir):
    """(the candidate's record, every record of its family); raises if it cannot be judged."""
    run_id, _, idx = candidate.partition("#")
    if not idx.isdigit():
        raise ValueError(f"candidate must look like <run_id>#<trial>, got {candidate!r}")
    everything = ledger.iter_trials(ledger_dir)
    target = next((r for r in everything if r.run_id == run_id and r.trial == int(idx)), None)
    if target is None:
        raise ValueError(f"no trial {candidate} in the ledger")
    if target.status != "ok":
        raise ValueError(f"{candidate} has status {target.status!r}; only an ok trial can be judged")
    return target, [r for r in everything if r.family == target.family]


def _unknown_specs(family, loaded) -> set:
    """Distinct specs with no VISIBLE result anywhere in the family. Visible = an ok trial
    whose series was read (``loaded``: the keys ``load_returns`` returned) or that recorded
    no trades. Everything else is charged: error, abandoned, crash orphan, and an ok trial
    whose returns were never bundled (killed-and-sealed run, or a run still open)."""
    visible = {r.spec_hash for r in family
               if r.status == "ok" and (r.returns_sha is None or r.key in loaded)}
    return {r.spec_hash for r in family} - visible


def _no_returns(target) -> str:
    if target.returns_sha is not None:
        return (f"{target.key} recorded returns, but its run has not written them to disk "
                f"(series are bundled when the run closes; a run that crashed never wrote them)")
    return f"{target.key} recorded no returns; there is nothing to judge"


def _prior(n) -> int:
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("prior_search_trials must be a non-negative integer")
    return n


def deflate(candidate: str, *, ledger_dir: Path | None = None,
            prior_search_trials: int = 0) -> FamilyDeflation:
    """DSR of trial ``candidate`` ("<run_id>#<trial>") against everything its family tried.

    ``prior_search_trials``: attempts made before the ledger existed (the notebook
    afternoon that led to this idea). The ledger cannot know them; declare them and they
    are added to N as independent tries. It can only raise the bar.
    """
    prior = _prior(prior_search_trials)
    target, family = _target(candidate, ledger_dir)
    series = _series(family, ledger_dir)
    if not len(series.get(target.key, ())):
        raise ValueError(_no_returns(target))
    eff = sig.effective_trials(series)

    unknown = _unknown_specs(family, series)
    n_trials = eff.n_effective + len(unknown) + prior

    pnl = sig.daily_pnl({target.key: series[target.key]})[target.key]
    moments = sig.sharpe_moments(sig.active_span(pnl))
    result = sig.deflated_sharpe(moments.sharpe, n_trials=n_trials,
                                 sharpe_variance=eff.sharpe_variance, n_obs=moments.n_obs,
                                 skew=moments.skew, kurtosis=moments.kurtosis)
    psr = sig.probabilistic_sharpe(moments.sharpe, 0.0, n_obs=moments.n_obs,
                                   skew=moments.skew, kurtosis=moments.kurtosis)
    return FamilyDeflation(family=target.family, candidate=target.key,
                           trials_recorded=len(family),
                           trials_with_returns=sum(1 for v in series.values() if len(v)),
                           unknown_specs_added=len(unknown), effective=eff,
                           n_trials=n_trials, moments=moments, result=result, psr=psr,
                           prior_search_trials=prior)


def family_sharpes(family: str, *, ledger_dir: Path | None = None) -> dict:
    """``{trial key: per-period Sharpe over its active span}`` for the family's trials
    that recorded returns (0.0 where undefined), on the same basis ``deflate`` uses."""
    records = _family(ledger_dir, family)
    series = {k: v for k, v in ledger.load_returns(records, ledger_dir).items() if len(v)}
    pnl = sig.daily_pnl(series)
    return {k: sig.active_span_sharpe(pnl[k]) for k in series}


def best_trial(family: str, *, ledger_dir: Path | None = None) -> str:
    """The key of the family's highest-Sharpe trial: the one a search would report.

    Only trials with at least ``MIN_OBS`` daily observations compete when any exist (a
    three-day series can post any Sharpe and cannot be tested). Ties break on the earliest
    key, so the answer depends only on the ledger."""
    records = _family(ledger_dir, family)
    series = {k: v for k, v in ledger.load_returns(records, ledger_dir).items() if len(v)}
    if not series:
        errors = [r for r in records if r.status == "error"]
        hint = ""
        if errors:
            first = next((row.get("error") for row in _outcome_rows(errors[0], ledger_dir)), None)
            hint = f"; {len(errors)} trial(s) raised, the first with: {first}"
        raise ValueError(f"family {family!r} has no trial with readable returns{hint}")
    pnl = sig.daily_pnl(series)
    long_enough = [k for k in series if len(sig.active_span(pnl[k])) >= MIN_OBS]
    pool = sorted(long_enough or series)
    return max(pool, key=lambda k: sig.active_span_sharpe(pnl[k]))


def _outcome_rows(record, ledger_dir):
    """The outcome row(s) of one trial, read straight from its shard (for error text)."""
    import json
    path = ledger._dir(ledger_dir) / f"{record.run_id}.jsonl"
    for line in path.read_bytes().split(b"\n"):
        if line:
            row = json.loads(line)
            if row.get("type") == "outcome" and row.get("trial") == record.trial:
                yield row


def _matrix(family: str, ledger_dir) -> pd.DataFrame:
    """Daily PnL of every family trial with variance, on one shared grid."""
    records = _family(ledger_dir, family)
    series = {k: v for k, v in ledger.load_returns(records, ledger_dir).items() if len(v)}
    pnl = sig.daily_pnl(series)
    return pnl.loc[:, pnl.std(ddof=0) > 0]


def family_pbo(family: str, *, ledger_dir: Path | None = None, n_splits: int = 16) -> sig.PBO:
    """Probability of Backtest Overfitting (CSCV) across the family's recorded trials.

    CSCV assumes every configuration ran over the same periods. Trials are placed on one
    daily grid (a day without a trade is 0), which is exact when the family was searched
    on one data slice and only an approximation when its trials span different windows.
    """
    m = _matrix(family, ledger_dir)
    if m.shape[1] < 2:
        raise ValueError("PBO needs at least two trials with returns")
    return sig.pbo_cscv(m, n_splits=n_splits)


def _by_day(series: pd.Series) -> pd.Series:
    """A return series summed per calendar date, on ITS OWN dates only. Unlike
    ``significance.daily_pnl`` it does not fill a business-day grid with zeros: for a
    benchmark, a day it does not cover must surface as missing, never as a flat day."""
    idx = pd.DatetimeIndex(pd.to_datetime(series.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    values = np.asarray(series, dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("benchmark contains non-finite values")
    return pd.Series(values, index=idx.normalize()).groupby(level=0).sum()


@dataclass
class FamilySPA:
    """The familywise verdict on one candidate (MONAD gate rules v2)."""
    candidate: str
    p_value: float                 # worst block p x (1 + m), capped at 1: the verdict statistic
    worst_p: float                 # worst (b+1)/(B+1) across blocks, before the (1 + m) charge
    m: int                         # attempts the matrix cannot contain, charged by union bound
    unknown_specs: int             #   ... results this test cannot see (error, abandoned,
                                   #       orphan, or ok with its returns never written)
    off_window: int                #   ... trials that ran on a different window
    prior_search_trials: int       #   ... declared search from before the ledger
    tested: int                    # family members in the test matrix
    dropped_zero_variance: int     # found-nothing members (exactly equivalent to dropping)
    n_obs: int
    n_boot: int
    alpha: float
    blocks: list = field(default_factory=list)   # per block: mean_block, p, candidate_t

    @property
    def significant(self) -> bool:
        return self.p_value <= self.alpha


def spa_n_boot(m: int, alpha: float) -> int:
    """B large enough that the verdict is never decided by bootstrap resolution."""
    return max(SPA_BOOT, int(math.ceil(20 * (1 + m) / alpha)))


def family_spa(candidate: str, *, benchmark: pd.Series | None = None,
               ledger_dir: Path | None = None, prior_search_trials: int = 0,
               alpha: float = 0.05, blocks=SPA_BLOCKS, n_boot: int | None = None,
               seed: int = 0) -> FamilySPA:
    """Does ``candidate`` beat ``benchmark`` after everything its family tried?

    Hansen's SPA (stationary bootstrap, consistent recentring) over the daily PnL of every
    family member that ran on the candidate's window, minus ``benchmark`` (a daily return
    series covering that window; default zero, i.e. cash at no interest). The candidate's
    p-value is familywise: the share of bootstrap worlds in which the BEST member of a
    no-edge family does at least as well. It keeps the dependence between trials, so a
    grid of near-copies is not over-charged and a zoo of unrelated ideas is not under-charged.

    Attempts the matrix cannot contain are charged by union bound, which needs no
    independence assumption: ``p = worst block p x (1 + m)`` with ``m`` = unknown-result
    specs + members that ran on another window + ``prior_search_trials``. Each block p is
    (b+1)/(B+1), never exactly zero. Block lengths longer than a quarter of the window are
    not used (the shortest always is). Members with no variance on the window found nothing;
    dropping them is an exact equivalence (the bootstrap maximum is floored at 0).
    """
    prior = _prior(prior_search_trials)
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    target, family = _target(candidate, ledger_dir)
    loaded = ledger.load_returns(family, ledger_dir)
    series = {k: v for k, v in loaded.items() if len(v)}
    if target.key not in series:
        raise ValueError(_no_returns(target))
    pnl = sig.daily_pnl(series)
    window = sig.active_span(pnl[target.key]).index
    if len(window) < MIN_OBS:
        raise ValueError(f"{candidate} has {len(window)} daily observations; the test needs {MIN_OBS}")

    kept, off_window, zero = [], 0, 0
    for k in pnl.columns:
        if k == target.key:
            kept.append(k)
            continue
        span = sig.active_span(pnl[k]).index
        if not len(span):
            zero += 1
        elif len(span.intersection(window)) < MIN_WINDOW_COVERAGE * len(window):
            off_window += 1
        elif float(pnl.loc[window, k].std(ddof=1)) == 0.0:
            zero += 1
        else:
            kept.append(k)
    d = pnl.loc[window, kept]
    if benchmark is not None:
        b = _by_day(benchmark).reindex(window)
        if b.isna().any():
            raise ValueError(f"benchmark is missing {int(b.isna().sum())} of the candidate's "
                             f"{len(window)} dates (it must be daily and cover every one; a "
                             f"missing day is not a zero return)")
        d = d.sub(b, axis=0)
        flat = [k for k in d.columns if k != target.key and float(d[k].std(ddof=1)) == 0.0]
        zero += len(flat)   # identical to the benchmark: found nothing
        d = d.drop(columns=flat)
    unknown = len(_unknown_specs(family, loaded))
    m = unknown + off_window + prior
    B = n_boot if n_boot is not None else spa_n_boot(m, alpha)
    j = list(d.columns).index(target.key)
    usable = [bl for bl in blocks if bl <= len(window) / 4] or [min(blocks)]
    per_block = []
    for bl in usable:
        r = sig.superior_predictive_ability(d.to_numpy(dtype=float), mean_block=bl, n_boot=B, seed=seed)
        exceed = int(round(r.adjusted_pvalues[j] * B))
        per_block.append({"mean_block": bl, "p": (exceed + 1) / (B + 1), "candidate_t": r.t_stats[j]})
    worst = max(x["p"] for x in per_block)
    return FamilySPA(candidate=target.key, p_value=min(1.0, worst * (1 + m)), worst_p=worst, m=m,
                     unknown_specs=unknown, off_window=off_window, prior_search_trials=prior,
                     tested=d.shape[1], dropped_zero_variance=zero, n_obs=len(window), n_boot=B,
                     alpha=alpha, blocks=per_block)


@dataclass
class FamilyReport:
    family: str
    counts: dict
    deflation: FamilyDeflation
    spa: FamilySPA | None = None
    pbo: sig.PBO | None = None
    notes: list = field(default_factory=list)

    def __str__(self) -> str:
        return format_report(self)


def report(family: str, *, candidate: str | None = None, benchmark: pd.Series | None = None,
           ledger_dir: Path | None = None, prior_search_trials: int = 0, alpha: float = 0.05,
           n_boot: int | None = None, pbo_splits: int = 10) -> FamilyReport:
    """Everything the ledger can say about a family's best (or a named) trial.

    SPA and PBO are skipped, with the reason recorded in ``notes``, when the family
    cannot support them (too few trials or observations). The DSR is never skipped.
    """
    counts = ledger.family_counts(ledger_dir).get(family)
    if counts is None:
        raise ValueError(f"no trials recorded for family {family!r}")
    key = candidate or best_trial(family, ledger_dir=ledger_dir)
    d = deflate(key, ledger_dir=ledger_dir, prior_search_trials=prior_search_trials)
    if d.family != family:
        raise ValueError(f"{key} belongs to family {d.family!r}, not {family!r}")
    rep = FamilyReport(family=family, counts=counts, deflation=d)
    try:
        rep.spa = family_spa(key, benchmark=benchmark, ledger_dir=ledger_dir,
                             prior_search_trials=prior_search_trials, alpha=alpha, n_boot=n_boot)
    except ValueError as exc:
        rep.notes.append(f"SPA skipped: {exc}")
    try:
        rep.pbo = family_pbo(family, ledger_dir=ledger_dir, n_splits=pbo_splits)
    except ValueError as exc:
        rep.notes.append(f"PBO skipped: {exc}")
    return rep


def format_deflation(d: FamilyDeflation) -> str:
    e, r, m = d.effective, d.result, d.moments
    lines = [
        f"candidate   {d.candidate}",
        f"family      {d.family}",
        f"trials      {d.trials_recorded} recorded, {d.trials_with_returns} with returns, "
        f"{e.n_distinct} distinct",
        f"effective N {d.n_trials:.2f}  (clusters {e.n_clusters}, Li-Ji {e.n_li_ji:.2f}, "
        f"+{d.unknown_specs_added} unknown-result specs, +{d.prior_search_trials} declared prior)",
        f"Sharpe      {d.annualized_sharpe:+.3f} annualized over {m.n_obs} days "
        f"(skew {m.skew:+.2f}, kurtosis {m.kurtosis:.2f})",
        f"PSR         {d.psr:.4f}  = P(true Sharpe > 0) if this were the ONLY thing tried",
        f"SR0         {d.annualized_sr0:+.3f} annualized: what the best of {d.n_trials:.1f} "
        f"zero-edge tries is expected to show",
        f"DSR         {r.dsr:.4f}  = P(true Sharpe > SR0), after the search",
    ]
    if m.n_obs < MIN_OBS:
        lines.append(f"WARNING     only {m.n_obs} daily observations: a DSR this thin is not evidence")
    if d.degenerate:
        lines.append("WARNING     the family's trials are variants of one idea, so the cross-idea Sharpe "
                     "variance is 0, SR0 is 0 and\n            the DSR above is just the PSR: it "
                     "deflates nothing here. Read the SPA verdict instead.")
    return "\n".join(lines)


def format_spa(s: FamilySPA) -> str:
    charge = (f"worst block p {s.worst_p:.4f} x (1 + {s.m}): {s.unknown_specs} unknown-result, "
              f"{s.off_window} off-window, {s.prior_search_trials} declared prior")
    verdict = "SIGNIFICANT" if s.significant else "NOT SIGNIFICANT"
    return (f"SPA         familywise p = {s.p_value:.4f}  over {s.tested} member(s), {s.n_obs} days "
            f"({charge})\n"
            f"VERDICT     {verdict} at {s.alpha:.0%} after the search that was recorded")


def format_report(rep: FamilyReport) -> str:
    c = rep.counts
    lines = [f"attempts    {c['intents']} begun in {c['runs']} run(s): {c.get('ok', 0)} ok, "
             f"{c.get('error', 0)} error, {c.get('abandoned', 0)} abandoned, {c['orphans']} orphaned",
             format_deflation(rep.deflation)]
    if rep.pbo is not None:
        lines.append(f"PBO         {rep.pbo.pbo:.3f}  = share of {rep.pbo.n_combinations} CSCV splits "
                     f"where the in-sample winner lands in the bottom half out of sample")
    if rep.spa is not None:
        lines.append(format_spa(rep.spa))
    lines.extend(rep.notes)
    if c.get("invalid_runs"):
        lines.append(f"WARNING     {c['invalid_runs']} run(s) fail verification; run `countedtrials verify`")
    return "\n".join(lines)
