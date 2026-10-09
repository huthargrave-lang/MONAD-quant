"""
admit_tactical — the admission chain for ``tactical_allocation`` hypotheses: daily
strategies judged against their domain's benchmark (src/research/daily_domains.py).

Called by tools/admit.py once a registration loads with this profile. Deterministic, like
the price chain: nothing here is judged by a model. Every statistic is RELATIVE to the
domain's benchmark, because a long portfolio's raw Sharpe is mostly beta (F404703: a DSR
of 0.9999 passed an artifact). Stages, in order:

  registration  the frozen candidate is a point of its domain's frozen grid (a config that
                was never searched would be judged against an N that never saw it)
  code          clean tree at a known commit
  refutations   objections filed and all refuted
  witness       the registration, every searched run, and the frozen data files are on
                the deploy branch
  lookahead     orders are unchanged when all data after each of 12 cuts is erased
  development   the candidate and benchmark re-run on the frozen data (counted) REPRODUCE
                the recorded search trial exactly; enough years and rebalances
  deflation     the candidate's ACTIVE DSR against its family's search + declared prior
  familywise    Hansen's SPA over the family: the candidate's adjusted p-value is at most
                the registered alpha at mean blocks 20, 63 and 126
  eras          active Sharpe > 0 in every registered era
  cost_stress   still beats the benchmark with both charged twice the cost
  forward       on data fetched AFTER registration (a new frozen snapshot that must
                reproduce the development snapshot where they overlap), after min_days:
                P(forward active Sharpe > 0) >= min_psr. Low power by construction: at an
                active Sharpe of 1 over a year it passes about 40% of the time, so a
                registrant who wants a fairer test registers a longer window.

There is no parity stage: no live bot trades these strategies; admission is a research
verdict, not a deployment.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from admit import (BLOCK, FAIL, MIN_DSR_OBS, PASS, PENDING, REJECT, SKIP, Stage, _verdict,  # noqa: E402
                   stage_code, stage_refutations, stage_witness)

from src.research import allocation_stats as stats  # noqa: E402
from src.research import daily_data, data_store, prereg, significance as sig, trials  # noqa: E402
from src.research.backtest_trials import family_members  # noqa: E402
from src.research.daily_domains import DOMAINS, Context, Domain  # noqa: E402
from src.research.daily_strategy import evaluate_daily  # noqa: E402
from src.research.daily_trials import (daily_spec, family_name, record_daily,  # noqa: E402
                                       stored_returns)

PRODUCER = "tools/admit.py"
COST_STRESS_MULTIPLE = 2
#: Forward data starts this many calendar days before the forward window, so a rule's
#: warm-up (a year of NAV history, 252 listed sessions) is satisfied inside it.
FORWARD_WARMUP_DAYS = 550
#: Forward snapshot vs development snapshot on overlapping sessions: an asset's raw closes
#: must agree within this, and at least this share of shared assets must, or the forward
#: data is not the same market the development data described.
OVERLAP_TOLERANCE = 0.005
MIN_OVERLAP_AGREEMENT = 0.95
REPLAY_TOLERANCE = 1e-12

ADMIT_CHAIN = ("registration", "code", "refutations", "witness", "lookahead", "development",
               "deflation", "familywise", "eras", "cost_stress", "forward")
#: Gate rules v2 (decision debate 2026-10-06): the DSR stage becomes a non-gating
#: diagnostic that is always SKIP; the familywise SPA, with its (1+m) charge, gates.
ADMIT_CHAIN_V2 = ("registration", "code", "refutations", "witness", "lookahead", "development",
                  "deflation_diagnostic", "familywise", "eras", "cost_stress", "forward")


def admit_chain(rules: int) -> tuple:
    return ADMIT_CHAIN_V2 if rules == 2 else ADMIT_CHAIN


def familywise_m(searched, latest: dict, params: dict, unknown: set) -> tuple[int, dict]:
    """m for the v2 gate: the declared prior search, every distinct spec with no known
    result, and every distinct point the family searched that has no ok trial in the SPA
    matrix (searched only on another snapshot, window or cost multiple). Each is charged
    by the union bound because the matrix cannot contain it."""
    in_matrix = set(latest)
    off_window = {_point_key(r.spec["params"]) for r in searched
                  if r.status == "ok" and isinstance(r.spec.get("params"), dict)
                  and "class" in r.spec["params"]} - in_matrix
    parts = {"prior_search_trials": int(params["prior_search_trials"]),
             "unknown_specs": len(unknown), "off_window_points": len(off_window)}
    return sum(parts.values()), parts


@dataclass(frozen=True)
class FamilyActive:
    """The family's active series on the registered window, as the gate scores them."""
    latest: dict           # point key -> the latest ok search trial on this window
    active: dict           # label -> active daily series (member minus benchmark)
    candidate_label: str
    unknown: set           # spec hashes searched with no ok result


def family_active(searched, searched_refs, data: dict, start, end, candidate: dict,
                  candidate_active: pd.Series) -> FamilyActive:
    """Every distinct point the family searched on this data and window, as an active
    series against the benchmark's recorded run; the candidate's series is the gate's own
    re-run. Raises ValueError when the benchmark was never recorded on this window."""
    ref_rec = [r for r in searched_refs if r.status == "ok" and _same_window(r, data, start, end)]
    if not ref_rec:
        raise ValueError("the benchmark was never recorded on this data and window")
    latest = {}
    for r in searched:
        if r.status == "ok" and _same_window(r, data, start, end):
            latest[_point_key(r.spec["params"])] = r
    series = trials.load_returns(list(latest.values()) + [ref_rec[-1]])
    ref_r = stored_returns(series[ref_rec[-1].key])
    active = {f"{k[0]} {dict(k[1])}": stats.active_series(stored_returns(series[r.key]), ref_r)
              for k, r in latest.items()}
    label = f"{candidate['class']} {dict(_point_key(candidate)[1])}"
    active[label] = candidate_active
    unknown = ({r.spec_hash for r in searched if r.status != "ok"}
               - {r.spec_hash for r in searched if r.status == "ok"})
    return FamilyActive(latest, active, label, unknown)


def v2_gate(fam: FamilyActive, searched, params: dict) -> tuple[int, dict, "stats.FamilywiseGate"]:
    """The gate rules v2 familywise statistic: (m, its parts, the seeded gate)."""
    m, parts = familywise_m(searched, fam.latest, params, fam.unknown)
    return m, parts, stats.familywise_gate(fam.active, fam.candidate_label, m=m,
                                           alpha=params["familywise_alpha"])


@dataclass(frozen=True)
class DataEvidence:
    """The frozen data a verdict rests on, split by where each file can be checked.

    ``witnessed``: committed files the witness must find on the deploy branch (every
    manifest, and the observations of a data set whose terms allow committing them).
    ``private``: observations kept in the private store because their vendor's terms
    forbid redistribution (``data_store``). They cannot be on the deploy branch; their
    committed manifest is witnessed instead, and it names them by sha-256, so the stage
    checks here that each is present and hashes to that sha. ``problems``: why a private
    file fails that check."""
    witnessed: list
    private: list
    problems: list


def _data_evidence(spec_data: dict, domain: Domain, *, data_dir: Path | None = None,
                   private_dir: Path | None = None) -> DataEvidence:
    """The price snapshot, and the domain's second dataset (NAV panel, event panel) under
    the domain's own prefix. A data set whose manifest records private observations is
    witnessed by its manifest and verified locally; any other by both of its files."""
    sets = [("DS", spec_data["snapshot"])]
    if spec_data.get("nav_panel"):
        if domain.panel_prefix is None:
            raise ValueError(f"domain {domain.name} names a panel but declares no panel_prefix")
        sets.append((domain.panel_prefix, spec_data["nav_panel"]))
    base = Path(data_dir) if data_dir is not None else data_store.DATA_DIR
    witnessed, private, problems = [], [], []
    for prefix, sha in sets:
        manifest_path = base / f"{prefix}-{sha}.json"
        manifest = (json.loads(manifest_path.read_text(encoding="utf-8"))
                    if manifest_path.is_file() else None)
        if data_store.records_private(manifest):
            store = Path(private_dir) if private_dir is not None else data_store.PRIVATE_DATA_DIR
            private.append(str(store / data_store.observations_name(prefix, sha)))
            problems += data_store.verify_private(prefix, sha, manifest, private_dir=store)
        else:
            witnessed.append(str(base / data_store.observations_name(prefix, sha)))
        witnessed.append(str(manifest_path))
    return DataEvidence(witnessed, private, problems)


def _same_window(r, data: dict, start, end, cost_multiple=1.0) -> bool:
    d = r.spec.get("data") or {}
    p = r.spec.get("params") or {}
    return (d.get("snapshot") == data["snapshot"] and d.get("nav_panel") == data.get("nav_panel")
            and d.get("start") == start.date().isoformat() and d.get("end") == end.date().isoformat()
            and p.get("cost_multiple") == cost_multiple)


def _point_key(params: dict) -> tuple:
    return params["class"], tuple(sorted(params["params"].items()))


def _counted(run, domain: Domain, ctx: Context, point, *, start, end, stage, cost_multiple=1.0):
    """One counted evaluation; returns (trial key, DailyResult or None)."""
    key = f"{run.run_id}#{run.trials_begun}"
    t = run.begin(params=daily_spec(point, cost_multiple=cost_multiple, domain=domain.name),
                  data=ctx.data_spec(start, end), extra={"stage": stage})
    try:
        result = evaluate_daily(domain.decide(ctx, point), ctx.snap, start=start, end=end,
                                cost_multiple=cost_multiple, tiers=domain.tiers(ctx))
    except Exception as exc:  # noqa: BLE001 — counted as an error, reported by the stage
        t.fail(f"{type(exc).__name__}: {exc}")
        return key, None
    record_daily(t, result)
    return key, result


def overlap_problems(dev: Context, fwd: Context) -> list[str]:
    """Reasons the forward data does not describe the same market as the development data
    on the sessions they share."""
    shared = [a for a in dev.snap.assets if a in fwd.snap.assets]
    days = dev.snap.dates.intersection(fwd.snap.dates)
    if not shared or len(days) < 20:
        return [f"the forward data shares {len(shared)} assets and {len(days)} sessions with "
                f"the development data; it cannot be checked against it"]
    agree = 0
    for a in shared:
        x = dev.snap.close[a].reindex(days)
        y = fwd.snap.close[a].reindex(days)
        both = x.notna() & y.notna()
        if both.sum() and float((x[both] / y[both] - 1.0).abs().max()) <= OVERLAP_TOLERANCE:
            agree += 1
    share = agree / len(shared)
    if share < MIN_OVERLAP_AGREEMENT:
        return [f"only {share:.0%} of shared assets reproduce their development closes on the "
                f"{len(days)} overlapping sessions (need {MIN_OVERLAP_AGREEMENT:.0%})"]
    return []


def default_load_forward(spec: dict, dev: Context, start: pd.Timestamp, now: pd.Timestamp) -> Context:
    """Fetch, validate and freeze the data the forward window is scored on: the development
    snapshot's universe from ``start - FORWARD_WARMUP_DAYS`` to ``now`` and, for the CEF
    domain, a fresh NAV panel. Written as new content-addressed files, like any snapshot."""
    manifest = dev.snap.manifest
    universe = manifest["universe"]
    core = [universe[0]] + [a for a in universe[1:] if a in ("SPY", "IEF")]
    optional = [a for a in universe if a not in core]
    lo = (start - pd.Timedelta(days=FORWARD_WARMUP_DAYS)).date().isoformat()
    hi = (now + pd.Timedelta(days=1)).date().isoformat()
    independent, panel = None, None
    if dev.panel is not None:
        from src.research import cef_data
        frames, report = cef_data.build_panel()
        panel = cef_data.load_panel(cef_data.write_panel(frames, report))
        independent = {t: panel.price[t] for t in panel.price.columns}
    sha = daily_data.build_snapshot(universe, lo, hi, optional=optional,
                                    independent_closes=independent,
                                    independent_source="forward NAV panel" if independent else None)
    return Context(snap=daily_data.load_snapshot(sha), panel=panel)


def evaluate(hypothesis: str, spec: dict, spec_hash: str, record: dict, *, now=None,
             code: Callable = trials.code_state, witness: Callable, deploy_sha: Callable,
             prereg_dir=None, refutations_dir=None,
             load_context: Callable | None = None,
             load_forward: Callable = default_load_forward) -> dict:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    stages: list[Stage] = []
    p = spec["params"]
    rules = prereg.gate_rules(spec)
    record["gate_rules"] = rules
    domain = DOMAINS[p["domain"]]
    candidate = p["candidate"]
    finish = lambda: {**record, "verdict": _verdict(stages),                 # noqa: E731
                      "stages": [asdict(s) for s in stages]}

    # ── registration ────────────────────────────────────────────────────────
    if (domain.primary, domain.sign) != ("active", 1):
        stages.append(Stage("registration", FAIL, f"domain {domain.name} judges "
                            f"{'-' if domain.sign < 0 else '+'}{domain.primary} series; the gate "
                            "scores only the plain active series, so it cannot admit it yet"))
        return finish()
    grid_keys = {_point_key(pt) for pt in domain.grid()}
    if _point_key(candidate) not in grid_keys:
        stages.append(Stage("registration", FAIL, "the candidate is not a point of its domain's "
                            "frozen grid, so no recorded search could have found it"))
        return {**record, "verdict": REJECT, "stages": [asdict(s) for s in stages]}
    stages.append(Stage("registration", PASS, f"frozen at {spec['registered_at']}"))

    # ── code, refutations ───────────────────────────────────────────────────
    st, record["code"] = stage_code(code)
    stages.append(st)
    stages.append(stage_refutations(hypothesis, refutations_dir))

    # ── data and the family's search ────────────────────────────────────────
    try:
        ctx = (load_context or domain.load)(p["data"])
        start, end = domain.window(ctx)
        everything = trials.iter_trials()
    except Exception as exc:  # noqa: BLE001 — a gate that cannot load its evidence cannot admit
        stages.append(Stage("development", BLOCK, f"cannot load the frozen data: {exc}"))
        return finish()
    fam_name = family_name(domain.name)
    ref_name = family_name(domain.name, reference=True)
    searched = [r for r in family_members(everything, fam_name) if r.producer != PRODUCER]
    searched_refs = [r for r in family_members(everything, ref_name) if r.producer != PRODUCER]

    # ── witness ─────────────────────────────────────────────────────────────
    record["witnessed_sha"] = deploy_sha()
    runs = sorted({str(trials.LEDGER_DIR / f"{r.run_id}.jsonl") for r in searched + searched_refs})
    evidence = _data_evidence(p["data"], domain)
    problems = witness(spec, prereg.path_for(hypothesis, prereg_dir), runs + evidence.witnessed)
    stages.append(stage_witness(problems + evidence.problems, len(runs),
                                private=[Path(f).name for f in evidence.private]))

    # ── lookahead ───────────────────────────────────────────────────────────
    cuts = stats.default_cuts(ctx.snap, start)
    leaks = domain.truncation(ctx, candidate, cuts)
    stages.append(Stage("lookahead", FAIL if leaks else PASS,
                        "; ".join(leaks[:3]) if leaks else f"orders unchanged at {len(cuts)} cuts",
                        {"violations": leaks}))

    # ── counted re-runs ─────────────────────────────────────────────────────
    registered_at = pd.Timestamp(spec["registered_at"]).tz_convert(None)
    forward_start = max(registered_at.normalize() + pd.Timedelta(days=1),
                        ctx.snap.dates[-1] + pd.Timedelta(days=1))
    now_naive = pd.Timestamp(now).tz_convert(None)
    h = spec["holdout"]
    forward_due = (now_naive - forward_start).days >= h["min_days"]
    res = {}
    try:
        with trials.open_run(producer=PRODUCER, family=fam_name, hypothesis=hypothesis,
                             context={"spec_hash": spec_hash}) as run, \
                trials.open_run(producer=PRODUCER, family=ref_name,
                                # Not hypothesis=: the ledger ties a hypothesis to its
                                # registered family, and the benchmark has its own. The
                                # link is recorded in the context instead.
                                context={"spec_hash": spec_hash, "role": "reference",
                                         "hypothesis": hypothesis}) as ref_run:
            for label, r, point in (("dev", run, candidate), ("dev_ref", ref_run, domain.reference)):
                res[label] = _counted(r, domain, ctx, point, start=start, end=end,
                                      stage="admission:development")
            for label, r, point in (("stress", run, candidate), ("stress_ref", ref_run, domain.reference)):
                res[label] = _counted(r, domain, ctx, point, start=start, end=end,
                                      stage=f"admission:cost_{COST_STRESS_MULTIPLE}x",
                                      cost_multiple=COST_STRESS_MULTIPLE)
            if forward_due:
                fwd = load_forward(spec, ctx, forward_start, now_naive)
                record["forward_data"] = {"snapshot": fwd.snap.sha,
                                          "nav_panel": fwd.panel.sha if fwd.panel is not None else None,
                                          "overlap_problems": overlap_problems(ctx, fwd)}
                fend = fwd.snap.dates[-1]
                for label, r, point in (("fwd", run, candidate), ("fwd_ref", ref_run, domain.reference)):
                    res[label] = _counted(r, domain, fwd, point, start=forward_start, end=fend,
                                          stage="admission:forward")
        record["ledger_run"] = run.run_id
        record["reference_run"] = ref_run.run_id
    except Exception as exc:  # noqa: BLE001
        stages.append(Stage("development", BLOCK, f"could not run the candidate: {exc}"))
        return finish()

    # ── development ─────────────────────────────────────────────────────────
    (dev_key, dev), (_, dev_ref) = res["dev"], res["dev_ref"]
    if dev is None or dev_ref is None:
        stages.append(Stage("development", FAIL, "the candidate or benchmark failed to run",
                            {"trial": dev_key}))
        return finish()
    years = len(dev.returns) / 252.0
    match = [r for r in searched if r.status == "ok" and _same_window(r, p["data"], start, end)
             and _point_key(r.spec["params"]) == _point_key(candidate)]
    problems = []
    if not match:
        problems.append("no recorded search trial ran this candidate on this data and window")
    else:
        recorded = stored_returns(trials.load_returns([match[-1]])[match[-1].key])
        if not recorded.index.equals(dev.returns.index) or \
                float(np.abs(recorded.to_numpy() - dev.returns.to_numpy()).max()) > REPLAY_TOLERANCE:
            problems.append(f"the re-run does not reproduce recorded trial {match[-1].key}")
    if years < p["min_years"]:
        problems.append(f"{years:.1f} years (need {p['min_years']})")
    if dev.rebalances < spec["min_trades"]:
        problems.append(f"{dev.rebalances} rebalances (need {spec['min_trades']})")
    stages.append(Stage("development", FAIL if problems else PASS,
                        "; ".join(problems) if problems else
                        f"reproduces {match[-1].key} exactly; {years:.1f} years, {dev.rebalances} rebalances",
                        {"trial": dev_key, "years": years, "rebalances": dev.rebalances}))

    # ── deflation and familywise, on the family's active series ─────────────
    try:
        fam = family_active(searched, searched_refs, p["data"], start, end, candidate,
                            stats.active_series(dev.returns, dev_ref.returns))
        active, cand_label, unknown = fam.active, fam.candidate_label, fam.unknown
        d = stats.deflate_active(active, cand_label, calendar=ctx.snap.dates,
                                 prior_trials=p["prior_search_trials"], unknown_specs=len(unknown))
        dsr_detail = (f"active DSR {d.dsr:.4f} vs {spec['threshold']} (active Sharpe "
                      f"{d.sharpe_ann:+.2f} vs SR0 {d.sr0_ann:.2f}; N {d.n_trials:.1f})")
        dsr_data = {"dsr": d.dsr, "n_trials": d.n_trials, "sharpe_ann": d.sharpe_ann,
                    "members": d.members}
        if rules == 2:
            stages.append(Stage("deflation_diagnostic", SKIP,
                                dsr_detail + "; a diagnostic under gate rules v2, not a gate",
                                dsr_data))
            m, parts, g = v2_gate(fam, searched, p)
            stages.append(Stage("familywise", PASS if g.p_gate <= p["familywise_alpha"] else FAIL,
                                f"p_gate {g.p_gate:.5f} = worst p {g.worst_p:.5f} x (1+{m}) vs "
                                f"{p['familywise_alpha']} (B={g.n_boot}, blocks "
                                f"{[b['mean_block'] for b in g.blocks]}, K={g.blocks[0]['family_size']})",
                                {"p_gate": g.p_gate, "worst_p": g.worst_p, "m": m, "m_parts": parts,
                                 "n_boot": g.n_boot, "blocks": g.blocks,
                                 "dropped_zero_variance": g.dropped_zero_variance}))
        else:
            ok = d.dsr >= spec["threshold"] and d.n_obs >= MIN_DSR_OBS
            stages.append(Stage("deflation", PASS if ok else FAIL, dsr_detail, dsr_data))
            fw = stats.familywise(active, cand_label)
            worst = max(f["candidate_pvalue"] for f in fw)
            stages.append(Stage("familywise", PASS if worst <= p["familywise_alpha"] else FAIL,
                                f"worst adjusted p {worst:.4f} vs {p['familywise_alpha']} across mean "
                                f"blocks {[f['mean_block'] for f in fw]} (K={fw[0]['family_size']})",
                                {"blocks": fw}))
        eras = stats.era_sharpes(active[cand_label], p["eras"])
        bad = [e for e in eras if e["active_sharpe"] is None or e["active_sharpe"] <= 0]
        stages.append(Stage("eras", FAIL if bad else PASS,
                            ", ".join(f"{e['era'][0]}..{e['era'][1]} {e['active_sharpe']:+.2f}"
                                      if e["active_sharpe"] is not None else f"{e['era']} empty"
                                      for e in eras), {"eras": eras}))
    except (ValueError, trials.LedgerError) as exc:
        names = (("deflation_diagnostic", "familywise", "eras") if rules == 2
                 else ("deflation", "familywise", "eras"))
        for name in names:
            stages.append(Stage(name, SKIP if name == "deflation_diagnostic" else FAIL,
                                f"cannot be computed: {exc}"))

    # ── cost stress ─────────────────────────────────────────────────────────
    (_, stress), (_, stress_ref) = res["stress"], res["stress_ref"]
    if stress is None or stress_ref is None:
        stages.append(Stage("cost_stress", FAIL, "the cost-stress runs failed"))
    else:
        a = stats.active_series(stress.returns, stress_ref.returns)
        ann = float(a.mean() * 252)
        stages.append(Stage("cost_stress", PASS if ann > 0 else FAIL,
                            f"active return {ann:+.2%}/yr with both at {COST_STRESS_MULTIPLE}x cost",
                            {"active_return_ann": ann}))

    # ── forward ─────────────────────────────────────────────────────────────
    if not forward_due:
        due = forward_start + pd.Timedelta(days=h["min_days"])
        stages.append(Stage("forward", PENDING, f"forward window matures {due.date()} (starts "
                            f"{forward_start.date()}, the first day no recorded trial has seen)"))
    else:
        (fwd_key, f), (_, f_ref) = res["fwd"], res["fwd_ref"]
        overlap = record["forward_data"]["overlap_problems"]
        if overlap:
            stages.append(Stage("forward", BLOCK, "; ".join(overlap)))
        elif f is None or f_ref is None:
            stages.append(Stage("forward", FAIL, "the forward runs failed", {"trial": fwd_key}))
        elif f.rebalances < h["min_trades"]:
            stages.append(Stage("forward", PENDING, f"{f.rebalances} forward rebalances (need "
                                f"{h['min_trades']})", {"trial": fwd_key}))
        else:
            a = stats.active_series(f.returns, f_ref.returns)
            try:
                m = sig.sharpe_moments(a)
                psr = sig.probabilistic_sharpe(m.sharpe, 0.0, n_obs=m.n_obs, skew=m.skew,
                                               kurtosis=m.kurtosis)
            except ValueError as exc:
                stages.append(Stage("forward", FAIL, f"forward active returns are degenerate: {exc}"))
            else:
                stages.append(Stage("forward", PASS if psr >= h["min_psr"] else FAIL,
                                    f"P(forward active Sharpe > 0) = {psr:.4f} vs {h['min_psr']} "
                                    f"over {m.n_obs} sessions", {"trial": fwd_key, "psr": psr}))
    return finish()


def verify_evidence(record: dict, head: dict, spec: dict | None) -> list[str]:
    """An ADMIT's tactical claims re-derived from the ledger: the named runs contain ok
    development, cost-stress and forward trials, the development trial is the candidate on
    the registered data, and the recorded commit is in this branch's history."""
    problems = []
    rows = trials.iter_trials()
    in_run = [r for r in rows if r.run_id == record.get("ledger_run")]
    stages_seen = {(r.spec.get("extra") or {}).get("stage") for r in in_run if r.status == "ok"}
    for need in ("admission:development", f"admission:cost_{COST_STRESS_MULTIPLE}x", "admission:forward"):
        if need not in stages_seen:
            problems.append(f"the gate run has no ok {need} trial")
    if spec is not None:
        cand = spec["params"]["candidate"]
        dev = [r for r in in_run if (r.spec.get("extra") or {}).get("stage") == "admission:development"]
        if not dev or _point_key(dev[0].spec["params"]) != _point_key(cand) or \
                (dev[0].spec.get("data") or {}).get("snapshot") != spec["params"]["data"]["snapshot"]:
            problems.append("the development trial is not the registered candidate on the registered data")
    if not record.get("reference_run") or not any(r.run_id == record["reference_run"] for r in rows):
        problems.append("the benchmark run named by the record does not exist")
    if spec is not None and prereg.gate_rules(spec) == 2 and not problems:
        problems += _verify_familywise(record, head, spec, rows)
    code_sha = (record.get("code") or {}).get("sha") or ""
    if (head.get("code") or {}).get("dirty") is not False:
        problems.append("the gate run executed on a modified tree")
    if not code_sha or trials._git(Path(REPO), "merge-base", "--is-ancestor", code_sha,
                                   "HEAD").returncode != 0:
        problems.append(f"code commit {code_sha[:12] or '(none)'} is not in this branch's history")
    return problems


def _verify_familywise(record: dict, head: dict, spec: dict, rows, *,
                       load_context: Callable | None = None) -> list[str]:
    """Gate rules v2: the familywise stage recomputed from the ledger, not read from the
    record. The family is every search trial whose run opened before the gate run did
    (what the gate could see); the candidate and benchmark series are the gate run's own
    development trials. The seeded SPA, B and (1+m) must reproduce the recorded p_gate,
    and p_gate must clear the registered alpha."""
    p = spec["params"]
    domain = DOMAINS[p["domain"]]
    stage = next((s for s in record.get("stages", []) if s["name"] == "familywise"), None)
    if stage is None:
        return ["familywise: the record has no familywise stage"]
    try:
        ctx = (load_context or domain.load)(p["data"])
        start, end = domain.window(ctx)
    except Exception as exc:  # noqa: BLE001
        return [f"familywise: cannot load the registered data to recompute it ({exc})"]
    gate_at = head["at"]
    before = [r for r in rows if r.opened_at < gate_at and r.producer != PRODUCER]
    searched = family_members(before, family_name(domain.name))
    searched_refs = family_members(before, family_name(domain.name, reference=True))

    def dev_trial(run_id):
        hit = [r for r in rows if r.run_id == run_id and r.status == "ok"
               and (r.spec.get("extra") or {}).get("stage") == "admission:development"]
        return hit[0] if hit else None

    dev, dev_ref = dev_trial(record["ledger_run"]), dev_trial(record.get("reference_run"))
    if dev is None or dev_ref is None:
        return ["familywise: the gate runs lack the development trials it was scored on"]
    try:
        series = trials.load_returns([dev, dev_ref])
        cand = stats.active_series(stored_returns(series[dev.key]), stored_returns(series[dev_ref.key]))
        fam = family_active(searched, searched_refs, p["data"], start, end, p["candidate"], cand)
        m, _, g = v2_gate(fam, searched, p)
    except (ValueError, trials.LedgerError) as exc:
        return [f"familywise: cannot be recomputed from the ledger ({exc})"]
    data = stage.get("data") or {}
    problems = []
    if m != data.get("m") or g.n_boot != data.get("n_boot") or \
            abs(g.p_gate - float(data.get("p_gate", float("nan")))) > REPLAY_TOLERANCE:
        problems.append(f"familywise: recomputed p_gate {g.p_gate:.5f} (m {m}, B {g.n_boot}) does "
                        f"not match the record's {data.get('p_gate')} (m {data.get('m')}, "
                        f"B {data.get('n_boot')})")
    if g.p_gate > p["familywise_alpha"]:
        problems.append(f"familywise: recomputed p_gate {g.p_gate:.5f} does not clear "
                        f"{p['familywise_alpha']}")
    return problems
