#!/usr/bin/env python3
"""
admit — the admission gate: the ONLY way a hypothesis becomes an "edge".

Deterministic by construction: no LLM judges anything here. An agent (or a person) can
propose, sweep and argue, but whether a pre-registered hypothesis is admitted is decided
by the chain below, from committed evidence, and the verdict is written to an immutable
record under docs/research/verdicts/<H>/.

Profile ``price_strategy`` (the hourly RSI/VWAP mean-reversion family), in order:

  registration   the frozen spec (src/research/prereg.py) loads and names a candidate
  code           the tree is clean and at a known commit: evidence must be replayable
  refutations    at least one objection was filed (no refuter looked = BLOCK); none
                 unanswered (BLOCK); none upheld (REJECT)
  parity         the live bot decides like the backtest (tools/live_backtest_parity.py):
                 a backtest edge the bot cannot reproduce is not an edge it can trade
  witness        the registration and every trial searched before it are already on the
                 deploy branch, where CI's history checks protect them (BLOCK otherwise):
                 local files can be rewritten; merged ones cannot, silently
  development    the frozen candidate, re-run on the registered development window at
                 instrument cost, with at least min_trades trades
  deflation      its Deflated Sharpe against EVERY trial its family has recorded, by any
                 tool, is at least the registered threshold (src/research/deflation.py)
  cost_stress    still profitable at 2x cost
  benchmark      Calmar at least buy & hold's on the same bars
  forward        on bars NO recorded trial in the family has seen: the window starts at the
                 later of registered_at and the last bar any family trial touched, so a
                 backdated registration or a later peek only pushes it back. After
                 min_days: min_trades trades and P(forward Sharpe > 0) >= min_psr

Every backtest the gate runs is itself a counted trial in the family. Every stage runs
when it can, so the record says everything that is wrong, not only the first thing.
Verdict = worst stage outcome: REJECT > BLOCKED > PENDING > ADMIT.

Other profiles (event_study, allocation) are UNSUPPORTED until their holdouts exist; the
gate says so rather than admitting on a partial chain.

  venv/bin/python tools/admit.py H97            # evaluate, write the verdict record
  venv/bin/python tools/admit.py H97 --dry-run  # evaluate, write nothing but trials
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import io
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd  # noqa: E402

from src.research import deflation, prereg, refutations, trials  # noqa: E402
from src.research import allocation_stats as stats  # noqa: E402
from src.research import mark_to_market as mtm  # noqa: E402
from src.research import significance as sig  # noqa: E402
from src.research.backtest_trials import (MR_HOURLY_STRATEGY, data_spec, engine_spec,  # noqa: E402
                                          family_members, mr_hourly_family, record_backtest)

VERDICT_REL = Path("docs/research/verdicts")
VERDICT_DIR = Path(REPO) / VERDICT_REL

PASS, FAIL, BLOCK, PENDING, SKIP = "pass", "fail", "block", "pending", "skip"
ADMIT, REJECT, BLOCKED, PENDING_V, UNSUPPORTED = "ADMIT", "REJECT", "BLOCKED", "PENDING", "UNSUPPORTED"
CANDIDATE_KEYS = ("target_gain_pct", "stop_loss_pct", "rsi_oversold", "vwap_zscore_thresh",
                  "max_trade_bars")
COST_STRESS_MULTIPLE = 2
#: A stop's trigger-to-fill slippage beyond the spread (the round-trip cost already
#: charges the spread). ENGINE_VERSION 3 consensus (g): measured from live stop exits.
#: IBKR-native stop fills are UNMEASURED; the only measured evidence is the D6
#: software-risk-trigger audit (fills beyond the level 10.6-244 bp, median 32.72 bp), so
#: that median is used and every admission record states it with this source.
STOP_SLIPPAGE_PCT = 0.003272
STOP_SLIPPAGE_SOURCE = ("D6_software_risk_trigger_outcome_audit.md median 32.72 bp (software "
                        "stops); IBKR-native stop fills unmeasured")
#: A DSR over fewer daily observations than this is not evidence (red-team friction #5:
#: a Sharpe of +23 "over 2 days" was reported without complaint).
MIN_DSR_OBS = 30
#: Gate rules v2, price profile (DEFLATION_RULE_QUESTION.md (iii), (vi)): the familywise
#: stage runs only once the committed sparse-basis size study meets the trigger; until
#: then it is BLOCKED. Flipping this without that evidence fails a test.
PRICE_V2_RATIFIED = False
PRICE_V2_EVIDENCE = Path(REPO) / "docs" / "research" / "spa_price_size_study.json"
#: The named series every ENGINE_VERSION 3 price trial records (backtest_trials).
MTM_SERIES = ("mtm_pnl", "exposure", "instrument_return")
#: Bars of feature warm-up loaded before the forward window. Trades before
#: ``registered_at`` are discarded; these bars only let indicators settle.
FORWARD_WARMUP_DAYS = 60


@dataclass
class Stage:
    name: str
    outcome: str
    detail: str
    data: dict = field(default_factory=dict)


def _verdict(stages: list[Stage]) -> str:
    outcomes = {s.outcome for s in stages}
    if FAIL in outcomes:
        return REJECT
    if BLOCK in outcomes:
        return BLOCKED
    if PENDING in outcomes:
        return PENDING_V
    return ADMIT


def default_load_bars(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Hourly regular-session bars, the session judged in New York time
    (``fetcher.regular_session``; a UTC ``between_time`` keeps only the morning)."""
    from src.data.fetcher import load_session_bars

    with contextlib.redirect_stdout(io.StringIO()):
        return load_session_bars(symbol, start, end)


def _utc_naive(df: pd.DataFrame) -> pd.DataFrame:
    """Bars indexed in naive UTC, the basis ``registered_at`` is compared on. A tz-aware
    index compared with a naive timestamp raises; one silently mixed would shift the
    forward boundary by the UTC offset."""
    if df is None or not len(df):
        return df
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        df = df.copy()
        df.index = idx.tz_convert("UTC").tz_localize(None)
    return df


def default_witness(spec: dict, prereg_path: Path, family_runs: list) -> list[str]:
    """Problems with the evidence NOT being on the deploy branch yet.

    The registration must be there byte-identical, and every other evidence file (each
    ledger shard the family searched, and for daily strategies the frozen data files) must
    be there as a byte-prefix of the local one. Until then an author could still
    rewrite them locally without any history check noticing (red-team attacks 3b, 5b)."""
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import ctx

    # Fully qualified: a LOCAL branch named "origin/development" would otherwise shadow the
    # remote-tracking ref when git resolves the short name (round-2 red team, W).
    ref = f"refs/remotes/origin/{ctx._manifest().get('deploy_branch', 'development')}"
    repo = Path(REPO)
    problems = []

    def at_ref(rel: str):
        r = trials._git(repo, "show", f"{ref}:{rel}")
        return r.stdout if r.returncode == 0 else None

    def rel_of(path) -> str | None:
        try:
            return Path(path).resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            return None

    rel = rel_of(prereg_path)
    if rel is None or at_ref(rel) != Path(prereg_path).read_bytes():
        problems.append(f"{rel or prereg_path} is not on {ref} as registered")
    for run_path in sorted(set(family_runs)):
        rel = rel_of(run_path)
        if rel is None:
            problems.append(f"{run_path} is outside the repository")
            continue
        blob = at_ref(rel)
        if blob is None or not Path(run_path).read_bytes().startswith(blob) or not blob:
            problems.append(f"{rel} (evidence the verdict rests on) is not on {ref}")
    return problems


def _deploy_ref() -> str:
    """The fully qualified remote-tracking ref of the deploy branch (a local branch named
    "origin/development" cannot shadow it)."""
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import ctx
    return f"refs/remotes/origin/{ctx._manifest().get('deploy_branch', 'development')}"


def default_deploy_sha() -> str | None:
    """The deploy-branch commit the witness reads evidence from, or None if unfetched."""
    r = trials._git(Path(REPO), "rev-parse", "--verify", "--quiet", _deploy_ref())
    return r.stdout.decode().strip() or None if r.returncode == 0 else None


def default_parity() -> dict:
    import live_backtest_parity

    return live_backtest_parity.census()


def _counted_backtest(df, ticker, params, cost, *, run, stage, evaluated_from=None):
    """One engine backtest of the frozen candidate, counted before it runs."""
    import strategy_funnel
    from src.backtest.runner import run_backtest

    mode = strategy_funnel._apply_config(ticker, params)
    key = f"{run.run_id}#{run.trials_begun}"
    trial = run.begin(
        params=engine_spec(mode, timeframe="hourly", target=params["target_gain_pct"],
                           stop=params["stop_loss_pct"], backtest_mode="realistic",
                           slippage_pct=cost, max_trade_bars=int(params["max_trade_bars"])),
        data=data_spec(df, ticker, evaluated_from), extra={"stage": stage})
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            r = run_backtest(mode=mode, max_trade_bars=int(params["max_trade_bars"]),
                             df=df.copy(), target_gain_pct=params["target_gain_pct"],
                             stop_loss_pct=params["stop_loss_pct"], require_signals=1,
                             timeframe="hourly", plot=False, backtest_mode="realistic",
                             slippage_pct=cost, stop_slippage_pct=STOP_SLIPPAGE_PCT)
        except Exception as exc:  # noqa: BLE001 — counted, then reported by the caller
            trial.fail(f"{type(exc).__name__}: {exc}")
            return key, None
    record_backtest(trial, r, evaluated_from=evaluated_from)
    return key, (r or None)


def _point(rec) -> str:
    """A searched point's identity: its engine settings, whatever data it ran on."""
    return trials.sha256_text(trials.canonical_json(rec.spec.get("params")))


def _mtm_active(recs) -> dict:
    """{record key: active series} for the records that carry all three named series."""
    loaded = {n: trials.load_series(recs, n) for n in MTM_SERIES}
    return {r.key: mtm.active_pnl(*(loaded[n][r.key] for n in MTM_SERIES))
            for r in recs if all(r.key in loaded[n] for n in MTM_SERIES)}


def price_family_gate(searched, dev_rec, *, prior: int, alpha: float):
    """Gate rules v2 for the price profile: ``(m, m_parts, FamilywiseGate)``.

    The matrix holds every distinct point the family searched on the candidate's exact
    data (same bars, same scoring cut) with a mark-to-market record, plus the candidate as
    the gate re-ran it. Everything the matrix cannot hold is charged in ``m`` by the union
    bound: the declared prior search, specs with no known result, and points searched only
    on other data or before trials were marked (ENGINE_VERSION < 3). Raises ValueError when
    the candidate itself has no mark-to-market record."""
    cand = _mtm_active([dev_rec]).get(dev_rec.key)
    if cand is None:
        raise ValueError("the development trial carries no mark-to-market series")
    data, cand_point = dev_rec.spec.get("data"), _point(dev_rec)
    latest = {}
    for r in searched:
        if r.status == "ok" and r.spec.get("data") == data and all(n in r.series_shas for n in MTM_SERIES):
            latest[_point(r)] = r
    latest.pop(cand_point, None)          # the candidate's own search trial IS the candidate
    found = _mtm_active(list(latest.values()))
    active = {k: found[r.key] for k, r in latest.items()}
    active["candidate"] = cand
    unknown = ({r.spec_hash for r in searched if r.status != "ok"}
               - {r.spec_hash for r in searched if r.status == "ok"})
    off = {_point(r) for r in searched if r.status == "ok"} - set(latest) - {cand_point}
    parts = {"prior_search_trials": int(prior), "unknown_specs": len(unknown),
             "off_window_points": len(off)}
    m = sum(parts.values())
    return m, parts, stats.familywise_gate(active, "candidate", m=m, alpha=alpha)


def _price_familywise_stage(spec: dict, searched, dev_key) -> Stage:
    try:
        dev_rec = next((r for r in trials.iter_trials() if r.key == dev_key), None)
        if dev_rec is None:
            raise ValueError("no development trial to score")
        m, parts, g = price_family_gate(searched, dev_rec, prior=spec["prior_search_trials"],
                                        alpha=spec["familywise_alpha"])
    except (ValueError, trials.LedgerError) as exc:
        return Stage("familywise", FAIL, f"cannot be computed: {exc}")
    return Stage("familywise", PASS if g.p_gate <= spec["familywise_alpha"] else FAIL,
                 f"p_gate {g.p_gate:.5f} = worst p {g.worst_p:.5f} x (1+{m}) vs "
                 f"{spec['familywise_alpha']} on mark-to-market active PnL (B={g.n_boot}, "
                 f"K={g.blocks[0]['family_size']})",
                 {"p_gate": g.p_gate, "worst_p": g.worst_p, "m": m, "m_parts": parts,
                  "n_boot": g.n_boot, "blocks": g.blocks,
                  "dropped_zero_variance": g.dropped_zero_variance})


def stage_code(code: Callable) -> tuple[Stage, dict]:
    cs = code()
    if cs.get("sha") and cs.get("dirty") is False:
        return Stage("code", PASS, f"clean at {cs['sha'][:12]}"), cs
    return Stage("code", BLOCK, "the tree is dirty or unreadable; admission evidence must be "
                 "replayable from a commit", {"code": cs}), cs


def stage_refutations(hypothesis: str, refutations_dir) -> Stage:
    ref = refutations.status(hypothesis, refutations_dir)
    if ref["upheld"]:
        return Stage("refutations", FAIL, f"{len(ref['upheld'])} objection(s) upheld",
                     {"upheld": [o["id"] for o in ref["upheld"]]})
    if ref["open"]:
        return Stage("refutations", BLOCK, f"{len(ref['open'])} objection(s) unanswered",
                     {"open": [o["id"] for o in ref["open"]]})
    if not ref["refuted"]:
        return Stage("refutations", BLOCK, "no objection has been filed: no refuter has "
                     "examined this hypothesis (tools/refute.py object)")
    return Stage("refutations", PASS, f"{len(ref['refuted'])} objection(s), all refuted")


def stage_witness(problems: list[str], n_runs: int) -> Stage:
    if problems:
        detail = "; ".join(problems[:3]) + (f" (+{len(problems) - 3} more)" if len(problems) > 3 else "")
        return Stage("witness", BLOCK, detail, {"problems": problems})
    return Stage("witness", PASS, f"registration and {n_runs} searched run(s) are on the deploy "
                 f"branch", {"problems": []})


def evaluate(hypothesis: str, *, now: _dt.datetime | None = None,
             load_bars: Callable = default_load_bars, parity: Callable = default_parity,
             code: Callable = trials.code_state, witness: Callable = default_witness,
             deploy_sha: Callable = default_deploy_sha,
             prereg_dir=None, refutations_dir=None) -> dict:
    """Run the gate. Returns the verdict record (not yet written).

    There is deliberately no way to point the gate at another ledger: its trials land in
    the canonical one (tests/test_producer_ledger_wiring.py), and it deflates against it.
    """
    import strategy_funnel
    from src.optimization.sweep_costs import estimate_spread, round_trip_cost_pct

    now = now or _dt.datetime.now(_dt.timezone.utc)
    stages: list[Stage] = []
    record = {"schema": 1, "hypothesis": hypothesis,
              "evaluated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z")}

    # ── registration ────────────────────────────────────────────────────────
    try:
        spec, spec_hash = prereg.load(hypothesis, prereg_dir=prereg_dir)
    except prereg.PreregError as exc:
        stages.append(Stage("registration", FAIL, str(exc)))
        return {**record, "verdict": REJECT, "stages": [asdict(s) for s in stages]}
    record.update(spec_hash=spec_hash, family=spec["family"], profile=spec["profile"])
    params = spec.get("params")
    if spec["profile"] == "tactical_allocation":
        import admit_tactical
        return admit_tactical.evaluate(hypothesis, spec, spec_hash, record, now=now, code=code,
                                       witness=witness, deploy_sha=deploy_sha,
                                       prereg_dir=prereg_dir, refutations_dir=refutations_dir)
    if spec["profile"] != "price_strategy" or not spec["family"].startswith(MR_HOURLY_STRATEGY + ":"):
        stages.append(Stage("registration", BLOCK,
                            f"profile {spec['profile']!r} / family {spec['family']!r} has no "
                            f"admission chain yet (only hourly RSI/VWAP price strategies)"))
        return {**record, "verdict": UNSUPPORTED, "stages": [asdict(s) for s in stages]}
    if len(spec["universe"]) != 1:
        stages.append(Stage("registration", BLOCK, "multi-instrument universes are not supported yet"))
        return {**record, "verdict": UNSUPPORTED, "stages": [asdict(s) for s in stages]}
    if not isinstance(params, dict) or set(params) != set(CANDIDATE_KEYS):
        stages.append(Stage("registration", FAIL,
                            f"params must freeze exactly the candidate {list(CANDIDATE_KEYS)}; "
                            f"a registration without a frozen candidate cannot be admitted"))
        return {**record, "verdict": REJECT, "stages": [asdict(s) for s in stages]}
    ticker = spec["universe"][0]
    if spec["family"] != mr_hourly_family(ticker):
        stages.append(Stage("registration", FAIL,
                            f"family must be {mr_hourly_family(ticker)!r}, the one every tool "
                            f"records this strategy on {ticker} under; a private family would "
                            f"start the trial count from zero"))
        return {**record, "verdict": REJECT, "stages": [asdict(s) for s in stages]}
    stages.append(Stage("registration", PASS, f"frozen at {spec['registered_at']}"))
    record["stop_slippage"] = {"pct": STOP_SLIPPAGE_PCT, "source": STOP_SLIPPAGE_SOURCE}

    # ── code ────────────────────────────────────────────────────────────────
    st, record["code"] = stage_code(code)
    stages.append(st)

    # ── refutations ─────────────────────────────────────────────────────────
    stages.append(stage_refutations(hypothesis, refutations_dir))

    # ── parity ──────────────────────────────────────────────────────────────
    census = parity()
    diverge = [r["dimension"] for r in census["rows"] if r["verdict"] == "DIVERGE"]
    stages.append(Stage("parity", BLOCK if diverge else PASS,
                        (f"backtest and live bot decide differently on: {', '.join(diverge)}"
                         if diverge else "no divergent decision input"),
                        {"counts": census["counts"]}))

    # ── what the family has already seen (for witness and forward) ──────────
    registered_at = pd.Timestamp(spec["registered_at"]).tz_convert(None)
    try:
        members = family_members(trials.iter_trials(), spec["family"])
    except trials.LedgerError as exc:
        stages.append(Stage("witness", FAIL, f"the ledger is invalid: {exc}"))
        return {**record, "verdict": _verdict(stages), "stages": [asdict(s) for s in stages]}
    # Everything the family tried, whenever, except the gate's own re-runs of frozen specs.
    # No author-written timestamp decides what counts (round-2 red team, 7a').
    searched = [r for r in members if r.producer != "tools/admit.py"]
    seen_bars = [pd.Timestamp(r.spec["data"]["fingerprint"]["last_bar"]) for r in members
                 if ((r.spec.get("data") or {}).get("fingerprint") or {}).get("last_bar")
                 and not (r.producer == "tools/admit.py"
                          and (r.spec.get("extra") or {}).get("stage") == "admission:forward")]
    seen_until = max(seen_bars) if seen_bars else None
    forward_start = registered_at if seen_until is None or seen_until < registered_at \
        else seen_until + pd.Timedelta(microseconds=1)

    # ── witness ─────────────────────────────────────────────────────────────
    # Decision-debate Q5: the verdict names the deploy-branch commit the evidence was
    # witnessed on, so a later rewrite of that branch invalidates the verdict (verify_record)
    # instead of passing silently. Branch protection (no force-push, enforce for admins) is
    # what makes a rewrite impossible; this makes one visible if protection is ever lifted.
    record["witnessed_sha"] = deploy_sha()
    problems = witness(spec, prereg.path_for(hypothesis, prereg_dir),
                       sorted({str(trials.LEDGER_DIR / f"{r.run_id}.jsonl") for r in searched}))
    stages.append(stage_witness(problems, len({r.run_id for r in searched})))

    # ── backtests (all counted) ─────────────────────────────────────────────
    w = spec["development_window"]
    snap = strategy_funnel._snapshot_config()
    dev_key = dev = stress = fwd = None
    fwd_key = None
    now_naive = pd.Timestamp(now).tz_convert(None)
    forward_due = (now_naive - forward_start).days >= spec["holdout"]["min_days"]
    try:
        with trials.open_run(producer="tools/admit.py", family=spec["family"],
                             hypothesis=hypothesis, context={"spec_hash": spec_hash}) as run:
            df = _utc_naive(load_bars(ticker, w["start"], w["end"]))
            if df is None or not len(df):
                raise RuntimeError(f"no bars for {ticker} over {w['start']}..{w['end']}")
            median = float(df["close"].median())
            cost = round_trip_cost_pct(estimate_spread(median, None), median)
            dev_key, dev = _counted_backtest(df, ticker, params, cost, run=run,
                                             stage="admission:development")
            _, stress = _counted_backtest(df, ticker, params, cost * COST_STRESS_MULTIPLE,
                                          run=run, stage=f"admission:cost_{COST_STRESS_MULTIPLE}x")
            if forward_due:
                start = (forward_start - pd.Timedelta(days=FORWARD_WARMUP_DAYS)).date().isoformat()
                fdf = _utc_naive(load_bars(ticker, start, pd.Timestamp(now).date().isoformat()))
                if fdf is not None and len(fdf):
                    fwd_key, fwd = _counted_backtest(fdf, ticker, params, cost, run=run,
                                                     stage="admission:forward",
                                                     evaluated_from=forward_start)
        record["ledger_run"] = run.run_id
    except Exception as exc:  # noqa: BLE001 — a gate that cannot measure must not admit
        stages.append(Stage("development", BLOCK, f"could not run the candidate: {exc}"))
        return {**record, "verdict": _verdict(stages), "stages": [asdict(s) for s in stages]}
    finally:
        strategy_funnel._restore_config(snap)

    # ── development ─────────────────────────────────────────────────────────
    n_dev = int(dev["total_trades"]) if dev else 0
    stages.append(Stage("development", PASS if n_dev >= spec["min_trades"] else FAIL,
                        f"{n_dev} trades (need {spec['min_trades']})",
                        {"trial": dev_key, "total_return": dev.get("total_return") if dev else None}))

    # ── deflation (v1 gate) / diagnostic + familywise (v2) ──────────────────
    rules = prereg.gate_rules(spec)
    record["gate_rules"] = rules
    if rules == 2:
        # Gate rules v2 (decision debate 2026-10-06): the DSR is a diagnostic, and the
        # price profile's familywise stage stays BLOCKED until its trigger study passes
        # on the mark-to-market active basis (DEFLATION_RULE_QUESTION.md (iii), (vi)).
        try:
            d = deflation.deflate_candidate(dev_key, exclude_producers=("tools/admit.py",)) if dev else None
            stages.append(Stage("deflation_diagnostic", SKIP,
                                (f"DSR {d.result.dsr:.4f} (diagnostic only under gate rules v2)"
                                 if d else "no development result"),
                                {"dsr": d.result.dsr if d else None}))
        except (ValueError, trials.LedgerError) as exc:
            stages.append(Stage("deflation_diagnostic", SKIP, f"not computable: {exc}"))
        if not PRICE_V2_RATIFIED:
            stages.append(Stage("familywise", BLOCK, "v2 price chain not ratified: the familywise "
                                "SPA on mark-to-market active PnL awaits its measured trigger "
                                "(docs/research/DEFLATION_RULE_QUESTION.md (vi))"))
        else:
            stages.append(_price_familywise_stage(spec, searched, dev_key))
    elif dev and n_dev >= 2:
        try:
            d = deflation.deflate_candidate(dev_key, exclude_producers=("tools/admit.py",))
            ok = d.result.dsr >= spec["threshold"] and d.moments.n_obs >= MIN_DSR_OBS
            thin = (f"; only {d.moments.n_obs} daily observations (need {MIN_DSR_OBS})"
                    if d.moments.n_obs < MIN_DSR_OBS else "")
            stages.append(Stage("deflation", PASS if ok else FAIL,
                                f"DSR {d.result.dsr:.4f} vs {spec['threshold']}{thin} "
                                f"(N_eff {d.n_trials:.2f} from {d.trials_recorded} family "
                                f"trials)",
                                {"dsr": d.result.dsr, "sr0": d.result.sr0, "n_trials": d.n_trials,
                                 "trials_recorded": d.trials_recorded,
                                 "annualized_sharpe": d.annualized_sharpe}))
        except (ValueError, trials.LedgerError) as exc:
            stages.append(Stage("deflation", FAIL, f"cannot deflate: {exc}"))
    else:
        stages.append(Stage("deflation", FAIL, "no development trades to deflate"))

    # ── cost stress ─────────────────────────────────────────────────────────
    s_ret = float(stress["total_return"]) if stress else 0.0
    stages.append(Stage("cost_stress", PASS if s_ret > 0 else FAIL,
                        f"total return {s_ret:+.4f} at {COST_STRESS_MULTIPLE}x cost"))

    # ── benchmark ───────────────────────────────────────────────────────────
    if dev:
        strat = strategy_funnel._calmar(dev["total_return"], dev["max_drawdown"],
                                        strategy_funnel._years(df))
        bench, _, _ = strategy_funnel._benchmark_calmar(df)
        ok = strat is not None and bench is not None and strat >= bench
        stages.append(Stage("benchmark", PASS if ok else FAIL,
                            f"Calmar {strat} vs buy & hold {bench}",
                            {"strategy_calmar": strat, "buy_hold_calmar": bench}))
    else:
        stages.append(Stage("benchmark", FAIL, "no development result"))

    # ── forward ─────────────────────────────────────────────────────────────
    h = spec["holdout"]
    if not forward_due:
        due = forward_start + pd.Timedelta(days=h["min_days"])
        moved = (f" (starts {forward_start.date()}, after bars family trials already saw)"
                 if forward_start > registered_at else "")
        stages.append(Stage("forward", PENDING, f"forward window matures {due.date()}{moved}"))
    else:
        series = (fwd or {}).get("trade_returns") if fwd else None
        scored = bt_scored(series, forward_start)
        if len(scored) < h["min_trades"]:
            stages.append(Stage("forward", PENDING,
                                f"{len(scored)} forward trades (need {h['min_trades']})",
                                {"trial": fwd_key}))
        else:
            try:
                psr = forward_psr(scored)
            except ValueError as exc:
                stages.append(Stage("forward", FAIL, f"forward returns are degenerate: {exc}"))
            else:
                stages.append(Stage("forward", PASS if psr >= h["min_psr"] else FAIL,
                                    f"P(forward Sharpe > 0) = {psr:.4f} vs {h['min_psr']} "
                                    f"over {len(scored)} trades",
                                    {"trial": fwd_key, "psr": psr}))

    return {**record, "verdict": _verdict(stages), "stages": [asdict(s) for s in stages]}


def forward_psr(scored: pd.Series) -> float:
    """P(forward Sharpe > 0) for per-trade forward returns: the forward stage's statistic,
    on the same daily-PnL active-span basis as the development deflation."""
    pnl = sig.active_span(sig.daily_pnl({"f": scored})["f"])
    m = sig.sharpe_moments(pnl)
    return sig.probabilistic_sharpe(m.sharpe, 0.0, n_obs=m.n_obs, skew=m.skew,
                                    kurtosis=m.kurtosis)


def bt_scored(series, evaluated_from) -> pd.Series:
    if series is None or not len(series):
        return pd.Series(dtype=float)
    return series[series.index >= pd.Timestamp(evaluated_from)]


def write_verdict(record: dict, verdict_dir: Path | None = None) -> Path:
    """Write the record once, immutably, as canonical JSON."""
    base = Path(verdict_dir) if verdict_dir is not None else VERDICT_DIR
    stamp = record["evaluated_at"].replace(":", "").replace("-", "")
    target = base / record["hypothesis"] / f"{stamp}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(trials.canonical_json(record, nonfinite="encode") + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return target


#: The stage chain an ADMIT must show, in order. A record claiming ADMIT with any other
#: chain did not come from this gate.
ADMIT_CHAIN = ("registration", "code", "refutations", "parity", "witness", "development",
               "deflation", "cost_stress", "benchmark", "forward")
ADMIT_CHAIN_V2 = ("registration", "code", "refutations", "parity", "witness", "development",
                  "deflation_diagnostic", "familywise", "cost_stress", "benchmark", "forward")


def verify_record(record: dict, *, prereg_dir=None, deploy_ref: str | None = None) -> list[str]:
    """Problems that make a verdict record untrustworthy (red-team attack 7b: a
    hand-written ADMIT file used to count). An ADMIT must be internally consistent, name
    a real gate run in the ledger for the same hypothesis and spec hash, and match the
    registration as it stands. Any verdict naming a ledger run must name a real one."""
    problems = []
    try:
        stages = [Stage(**s) for s in record.get("stages", [])]
    except TypeError:
        return ["stages are malformed"]
    if record.get("verdict") not in (ADMIT, REJECT, BLOCKED, PENDING_V, UNSUPPORTED):
        problems.append(f"unknown verdict {record.get('verdict')!r}")
    elif record["verdict"] != UNSUPPORTED and record["verdict"] != _verdict(stages):
        problems.append(f"verdict {record['verdict']} does not follow from its stages "
                        f"({_verdict(stages)})")
    run_id = record.get("ledger_run")
    head = None
    if run_id:
        path = trials.LEDGER_DIR / f"{run_id}.jsonl"
        if not path.exists():
            problems.append(f"ledger run {run_id} does not exist")
        else:
            rep_ = trials.verify_shard(path)
            if not rep_.ok:
                problems.append(f"ledger run {run_id} is invalid")
            head = __import__("json").loads(path.read_bytes().split(b"\n", 1)[0])
    if record.get("verdict") == ADMIT:
        tactical = record.get("profile") == "tactical_allocation"
        try:
            spec, current = prereg.load(record.get("hypothesis", ""), prereg_dir=prereg_dir)
            if current != record.get("spec_hash"):
                problems.append("the registration no longer matches the admitted spec")
        except prereg.PreregError as exc:
            spec = None
            problems.append(f"registration: {exc}")
        # The chain follows the gate rules of the hash-verified registration, never the
        # record's own claim (decision debate 2026-10-06, Q2 (v)).
        rules = prereg.gate_rules(spec) if spec is not None else None
        if rules is not None and record.get("gate_rules", 1) != rules:
            problems.append(f"the record claims gate rules {record.get('gate_rules')} but its "
                            f"registration is under rules {rules}")
        if tactical:
            import admit_tactical
            chain = admit_tactical.admit_chain(rules or 1)
        elif rules == 2 and not PRICE_V2_RATIFIED:
            chain = None
            problems.append("no price-profile ADMIT exists under gate rules v2: its familywise "
                            "stage is not ratified")
        elif rules == 2:
            chain = ADMIT_CHAIN_V2
        else:
            chain = ADMIT_CHAIN
        allowed = lambda s: s.outcome == PASS or (rules == 2 and s.name == "deflation_diagnostic"  # noqa: E731
                                                   and s.outcome == SKIP)
        if chain is not None and (tuple(s.name for s in stages) != chain
                                  or not all(allowed(s) for s in stages)):
            problems.append("an ADMIT must pass exactly the full stage chain")
        if head is None:
            problems.append("an ADMIT must name the gate's ledger run")
        else:
            if head.get("producer") != "tools/admit.py":
                problems.append("the named ledger run was not written by tools/admit.py")
            if head.get("hypothesis") != record.get("hypothesis"):
                problems.append("the named ledger run is for another hypothesis")
            if (head.get("context") or {}).get("spec_hash") != record.get("spec_hash"):
                problems.append("the named ledger run evaluated a different spec")
        if head is not None and not problems:
            problems += (admit_tactical.verify_evidence(record, head, spec) if tactical
                         else _verify_admit_evidence(record, head, spec))
        problems += _verify_witnessed_sha(record, deploy_ref or _deploy_ref())
    return problems


def _verify_witnessed_sha(record: dict, ref: str) -> list[str]:
    """The deploy-branch commit an ADMIT was witnessed on must still be in that branch's
    history. Authoritative where the ref exists (CI checks out with fetch-depth 0);
    advisory where it does not (an unfetched local clone), unless running in CI."""
    sha = record.get("witnessed_sha")
    if not sha:
        return ["an ADMIT must name the deploy-branch commit its evidence was witnessed on"]
    repo = Path(REPO)
    if trials._git(repo, "rev-parse", "--verify", "--quiet", ref).returncode != 0:
        return [f"{ref} is not available to check the witnessed commit"] if os.environ.get("CI") else []
    if trials._git(repo, "merge-base", "--is-ancestor", sha, ref).returncode != 0:
        return [f"witnessed commit {sha[:12]} is no longer in {ref}: the branch was rewritten"]
    return []


def _verify_admit_evidence(record: dict, head: dict, spec: dict | None) -> list[str]:
    """An ADMIT's claims, re-derived from the ledger rather than read from the record.

    Round-2 red team (7b''): an empty shard written with producer="tools/admit.py" and
    the right spec hash used to verify. Now the named run must CONTAIN the development,
    cost-stress and forward trials the stages cite, with outcomes that support them; the
    DSR is recomputed from the ledger; and the recorded code commit must be real and in
    this branch's history. A shard fabricated wholesale, with invented returns, can still
    pass this; that last step needs the gate re-run from the merged evidence (documented).
    """
    problems = []
    by_stage = {s["name"]: s for s in record.get("stages", [])}
    run_id = record["ledger_run"]
    rows = trials.iter_trials()
    in_run = {r.key: r for r in rows if r.run_id == run_id}
    code_sha = (record.get("code") or {}).get("sha") or ""
    if (head.get("code") or {}).get("sha") != code_sha:
        problems.append("the gate run was recorded at a different commit than the verdict")
    if (head.get("code") or {}).get("dirty") is not False:
        problems.append("the gate run executed on a modified tree")
    if not code_sha or trials._git(Path(REPO), "merge-base", "--is-ancestor", code_sha,
                                   "HEAD").returncode != 0:
        problems.append(f"code commit {code_sha[:12] or '(none)'} is not in this branch's history")

    def trial(stage_name, expected_stage):
        key = (by_stage.get(stage_name, {}).get("data") or {}).get("trial")
        r = in_run.get(key)
        if r is None:
            problems.append(f"{stage_name}: its trial {key} is not in run {run_id}")
        elif (r.spec.get("extra") or {}).get("stage") != expected_stage or r.status != "ok":
            problems.append(f"{stage_name}: trial {key} is not an ok {expected_stage} trial")
        return r

    dev = trial("development", "admission:development")
    if dev is not None and spec is not None and prereg.gate_rules(spec) == 2:
        problems += _verify_price_familywise(by_stage, head, spec, rows, dev)
    elif dev is not None and spec is not None:
        n = int((dev.metrics or {}).get("total_trades", 0))
        if n < spec["min_trades"]:
            problems.append(f"development: the ledger shows {n} trades, below {spec['min_trades']}")
        try:
            d = deflation.deflate_candidate(dev.key, exclude_producers=("tools/admit.py",))
            if d.result.dsr < spec["threshold"] or d.moments.n_obs < MIN_DSR_OBS:
                problems.append(f"deflation: recomputed DSR {d.result.dsr:.4f} does not clear "
                                f"{spec['threshold']} (or too few observations)")
        except (ValueError, trials.LedgerError) as exc:
            problems.append(f"deflation: cannot be recomputed ({exc})")
    if not any(r.producer == "tools/admit.py" and (r.spec.get("extra") or {}).get("stage", "").startswith("admission:cost")
               for r in in_run.values()):
        problems.append("cost_stress: no cost-stress trial in the gate run")
    trial("forward", "admission:forward")
    return problems


def _verify_price_familywise(by_stage: dict, head: dict, spec: dict, rows, dev) -> list[str]:
    """Gate rules v2, price profile: the familywise stage recomputed from the ledger. The
    family is what the gate could see (search trials whose runs opened before the gate
    run); the candidate is the gate run's development trial and its recorded series."""
    problems = []
    n = int((dev.metrics or {}).get("total_trades", 0))
    if n < spec["min_trades"]:
        problems.append(f"development: the ledger shows {n} trades, below {spec['min_trades']}")
    searched = [r for r in family_members([r for r in rows if r.opened_at < head["at"]],
                                          spec["family"]) if r.producer != "tools/admit.py"]
    try:
        m, _, g = price_family_gate(searched, dev, prior=spec["prior_search_trials"],
                                    alpha=spec["familywise_alpha"])
    except (ValueError, trials.LedgerError) as exc:
        return problems + [f"familywise: cannot be recomputed from the ledger ({exc})"]
    data = (by_stage.get("familywise") or {}).get("data") or {}
    if m != data.get("m") or g.n_boot != data.get("n_boot") or \
            abs(g.p_gate - float(data.get("p_gate", float("nan")))) > 1e-12:
        problems.append(f"familywise: recomputed p_gate {g.p_gate:.5f} (m {m}, B {g.n_boot}) does "
                        f"not match the record's {data.get('p_gate')} (m {data.get('m')})")
    if g.p_gate > spec["familywise_alpha"]:
        problems.append(f"familywise: recomputed p_gate {g.p_gate:.5f} does not clear "
                        f"{spec['familywise_alpha']}")
    return problems


def verify_records(verdict_dir: Path | None = None, *, prereg_dir=None) -> dict:
    """{relative path: problems} for every verdict record that fails verification."""
    base = Path(verdict_dir) if verdict_dir is not None else VERDICT_DIR
    out = {}
    for path in sorted(base.glob("H*/*.json")) if base.is_dir() else []:
        try:
            record = __import__("json").loads(path.read_text(encoding="utf-8"))
            problems = verify_record(record, prereg_dir=prereg_dir)
            if record.get("hypothesis") != path.parent.name:
                problems.append("filed under another hypothesis")
        except ValueError as exc:
            problems = [f"not JSON: {exc}"]
        if problems:
            out[str(path.relative_to(base))] = problems
    return out


def verify_history(base_ref: str, *, repo: Path = Path(REPO)) -> list[str]:
    """Verdict records on the deploy branch are never edited or deleted."""
    return trials.verify_history(base_ref, VERDICT_REL, repo=repo, what="verdict",
                                 rule=lambda r: "identical" if r.endswith(".json") else None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hypothesis", nargs="?")
    ap.add_argument("--dry-run", action="store_true", help="do not write the verdict record")
    ap.add_argument("--verify-history", metavar="REF",
                    help="check no verdict on REF's merge-base was edited or deleted, then exit")
    ap.add_argument("--verify-records", action="store_true",
                    help="check every verdict record is consistent and backed by a gate run, then exit")
    args = ap.parse_args(argv)
    if args.verify_records:
        bad = verify_records()
        for rel, problems in bad.items():
            for p in problems:
                print(f"FAIL {rel}: {p}")
        print(f"{len(bad)} invalid record(s)")
        return 1 if bad else 0
    if args.verify_history:
        problems = verify_history(args.verify_history)
        for p in problems:
            print(f"FAIL {p}")
        print(f"{len(problems)} problem(s)")
        return 1 if problems else 0
    if not args.hypothesis:
        ap.error("hypothesis is required")
    record = evaluate(args.hypothesis)
    for s in record["stages"]:
        print(f"  {s['outcome'].upper():8} {s['name']:<13} {s['detail']}")
    print(f"\n{record['hypothesis']}: {record['verdict']}")
    if not args.dry_run:
        path = write_verdict(record)
        print(f"verdict record -> {os.path.relpath(path, REPO)}")
        if record["verdict"] == ADMIT:
            print("\nCapture it in the web, citing this record:\n"
                  f"  venv/bin/python tools/note.py add --kind F --title \"{record['hypothesis']} "
                  f"admitted\" --body \"Verdict {os.path.relpath(path, REPO)}\" "
                  f"--link {record['hypothesis']}:supports")
    return 0 if record["verdict"] in (ADMIT, PENDING_V) else 1


if __name__ == "__main__":
    sys.exit(main())
