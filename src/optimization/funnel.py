"""
MONAD Quant — Strategy promotion funnel (PURE decision logic).

The offline counterpart to live promotion. A candidate strategy (a ticker + a
parameter set) must clear a sequence of gates before it earns even a SHADOW
(paper-watch) verdict, let alone PASS. This module holds ONLY the pure decision
functions: every gate is a pure function of already-computed metrics, so the
whole verdict tree is unit-testable without running a single backtest.

The heavy lifting — running realistic / harsh / cost-stressed backtests, the
leak-free walk-forward, and the bootstrap bands — lives in
``tools/strategy_funnel.py``, which computes a :class:`CandidateMetrics` and hands
it to :func:`evaluate_candidate` here.

Design stance (the project's hard-won skepticism — ``RESEARCH_WEB.md`` D6/F13):
a backtest *looking good is not evidence a strategy is tradable*. Gates are
deliberately harsh and **default to REJECT** when evidence is missing. Verdicts:

  * ``REJECT`` — failed a HARD gate (not even worth shadowing).
  * ``SHADOW`` — cleared the hard gates but a soft/robustness gate is shaky
                 (promising enough to paper-WATCH, never enough to fund).
  * ``PASS``   — cleared every gate (this still only earns a human review and a
                 shadow period; the funnel never authorises live capital).

HARD gates (any fail ⇒ REJECT): minimum trade count, minimum trades per OOS
window, leak-free walk-forward edge, benchmark (must beat buy & hold on a
risk-adjusted basis), and the bootstrap lower band (the edge must survive
sampling noise).

SOFT gates (hard gates pass, any soft fail ⇒ SHADOW): full-sample realistic
confirmation, survival under harsh (5 bps) costs, survival under 3× cost stress,
and parameter stability (a broad plateau, not one lucky magic parameter).

Nothing here touches config, the network, the filesystem, or live trading. It is
arithmetic over numbers somebody else measured.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Mapping, Optional, Sequence

# ── Verdict labels ──────────────────────────────────────────────────────────
PASS = "PASS"
SHADOW = "SHADOW"
REJECT = "REJECT"

HARD = "hard"
SOFT = "soft"


def _is_num(x) -> bool:
    """True for a finite real number (rejects None / NaN / inf)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


# ── Thresholds (every knob the funnel judges against, in one place) ──────────
@dataclass(frozen=True)
class FunnelThresholds:
    """All pass/fail thresholds. Defaults are intentionally skeptical.

    These are deliberately conservative for a *low-drawdown income* product whose
    whole thesis is risk-adjusted consistency, not raw return — so the headline
    gates are Sharpe- and benchmark-based, not return-based.
    """

    # Gate 1 — minimum total closed trades (statistical basis).
    min_total_trades: int = 30
    # Gate 2 — minimum closed trades in EVERY out-of-sample window.
    min_trades_per_window: int = 5
    # Gate 3 — leak-free walk-forward: OOS Sharpe floor and OOS return must be > 0.
    min_oos_sharpe: float = 0.5
    # Gate 4 (soft) — full-sample realistic Sharpe floor.
    min_realistic_sharpe: float = 0.5
    # Gate 5 (soft) — harsh (5 bps) survival: Sharpe must stay >= this.
    min_harsh_sharpe: float = 0.0
    # Gate 6 (soft) — cost stress: total return at 3× cost must stay >= this.
    cost_stress_min_return: float = 0.0
    # Gate 7 (soft) — parameter stability. A neighbour "retains the edge" if its
    # Sharpe is positive AND >= retain_frac × the centre Sharpe. A parameter is a
    # broad plateau when at least plateau_frac of its neighbours retain.
    stability_retain_frac: float = 0.5
    stability_plateau_frac: float = 0.6
    stability_magic_frac: float = 0.34  # <= this fraction retaining ⇒ "magic"
    # Gate 8 (hard) — must beat buy & hold of the same instrument on a risk-adjusted
    # basis (Calmar = annualized return / |max drawdown|) by this margin. Calmar,
    # not Sharpe, because the engine's equity curve is per-trade (no time index) and
    # the product's whole thesis is low drawdown — raw return is the wrong objective.
    benchmark_score_margin: float = 0.0
    # Gate 9 (hard) — bootstrap: lower CI band of Sharpe must exceed this, and the
    # probability of ending below the starting capital must be under max_prob.
    uncertainty_min_sharpe_lo: float = 0.0
    uncertainty_max_prob_below: float = 0.5


# ── Gate + verdict value objects ────────────────────────────────────────────
@dataclass(frozen=True)
class GateResult:
    """One gate's verdict. Pure value object; carries enough to explain itself."""

    name: str
    passed: bool
    severity: str               # HARD | SOFT
    value: Optional[float]      # the measured statistic (None when not computed)
    threshold: Optional[float]  # the bar it had to clear
    detail: str                 # human-readable reason

    @property
    def status(self) -> str:
        return "ok" if self.passed else "FAIL"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FunnelVerdict:
    """The aggregate decision plus the gate-by-gate trail behind it."""

    verdict: str                # PASS | SHADOW | REJECT
    reasons: Sequence[str]
    gates: Sequence[GateResult]

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "gates": [g.to_dict() for g in self.gates],
        }


@dataclass(frozen=True)
class CandidateMetrics:
    """Everything the gates need, all pre-computed by the offline runner.

    Every field defaults to ``None`` so a unit test can construct the minimal
    object a single gate needs. A HARD gate handed ``None`` FAILS (skeptical
    default); a SOFT gate handed ``None`` also fails (⇒ at most SHADOW), so
    missing evidence never silently upgrades a verdict.
    """

    total_trades: Optional[int] = None
    trades_per_window: Optional[Sequence[int]] = None
    # Leak-free walk-forward OOS aggregate.
    oos_sharpe: Optional[float] = None
    oos_total_return: Optional[float] = None
    oos_max_drawdown: Optional[float] = None
    oos_win_rate: Optional[float] = None
    # Full-sample realistic / harsh.
    realistic_sharpe: Optional[float] = None
    realistic_total_return: Optional[float] = None
    harsh_sharpe: Optional[float] = None
    harsh_total_return: Optional[float] = None
    # Cost stress: multiplier (1, 2, 3) -> total return (and optionally Sharpe).
    cost_stress_return: Optional[Mapping[int, float]] = None
    cost_stress_sharpe: Optional[Mapping[int, float]] = None
    # Parameter stability: param_name -> {"center": sharpe, "neighbors": [sharpe,...]}.
    stability: Optional[Mapping[str, Mapping[str, object]]] = None
    # Benchmark (buy & hold of the same instrument, same span). The headline
    # comparison is the risk-adjusted score (Calmar by default); the raw return and
    # max-drawdown of each leg are carried alongside for the card.
    benchmark_metric: str = "calmar"
    benchmark_score: Optional[float] = None
    strategy_benchmark_score: Optional[float] = None
    benchmark_total_return: Optional[float] = None
    strategy_return_vs_benchmark: Optional[float] = None
    benchmark_max_drawdown: Optional[float] = None
    strategy_maxdd_vs_benchmark: Optional[float] = None
    # Bootstrap / uncertainty.
    uncertainty_sharpe_point: Optional[float] = None
    uncertainty_sharpe_lo: Optional[float] = None
    uncertainty_sharpe_hi: Optional[float] = None
    prob_below_initial: Optional[float] = None


# ── Classification helpers (pure, independently testable) ────────────────────
def classify_cost_stress(curve: Optional[Mapping[int, float]],
                         *, min_return: float = 0.0) -> str:
    """Classify a cost-stress curve {multiplier: total_return}.

    * ``"dead"``    — non-positive even at 1× cost (no edge to stress).
    * ``"fragile"`` — positive at 1× but collapses to <= min_return by the
                      highest multiplier tested.
    * ``"robust"``  — still above min_return at the highest multiplier.
    * ``"unknown"`` — no/insufficient data.
    """
    if not curve:
        return "unknown"
    keys = sorted(k for k, v in curve.items() if _is_num(v))
    if not keys:
        return "unknown"
    first, last = curve[keys[0]], curve[keys[-1]]
    if first <= min_return:
        return "dead"
    if last <= min_return:
        return "fragile"
    return "robust"


def classify_stability(center: Optional[float],
                       neighbors: Optional[Sequence[float]],
                       *, retain_frac: float = 0.5,
                       plateau_frac: float = 0.6,
                       magic_frac: float = 0.34) -> str:
    """Classify one parameter's local neighbourhood of Sharpe values.

    A neighbour "retains the edge" when its Sharpe is positive AND at least
    ``retain_frac`` of the centre Sharpe. Returns:

    * ``"dead"``    — the centre itself is non-positive.
    * ``"plateau"`` — a broad, robust ridge: >= ``plateau_frac`` of neighbours retain.
    * ``"magic"``   — one lucky parameter: <= ``magic_frac`` of neighbours retain.
    * ``"ridge"``   — in between (narrow but not a single spike).
    * ``"unknown"`` — no neighbours measured.
    """
    if not _is_num(center) or center <= 0:
        return "dead"
    vals = [v for v in (neighbors or []) if _is_num(v)]
    if not vals:
        return "unknown"
    kept = sum(1 for v in vals if v > 0 and v >= retain_frac * center)
    frac = kept / len(vals)
    if frac >= plateau_frac:
        return "plateau"
    if frac <= magic_frac:
        return "magic"
    return "ridge"


# ── Individual gates (each a pure function of scalars ⇒ a GateResult) ─────────
def gate_min_trades(total_trades, *, min_total: int) -> GateResult:
    ok = _is_num(total_trades) and total_trades >= min_total
    n = int(total_trades) if _is_num(total_trades) else None
    detail = (f"{n} closed trades vs >= {min_total} required" if n is not None
              else "trade count not computed")
    return GateResult("min_total_trades", ok, HARD, n, min_total, detail)


def gate_trades_per_window(trades_per_window, *, min_per_window: int) -> GateResult:
    vals = [v for v in (trades_per_window or []) if _is_num(v)]
    if not vals:
        return GateResult("min_trades_per_window", False, HARD, None,
                          min_per_window, "no out-of-sample windows produced trades")
    worst = min(vals)
    ok = worst >= min_per_window
    detail = (f"weakest OOS window has {int(worst)} trades vs >= {min_per_window} "
              f"required (windows: {[int(v) for v in vals]})")
    return GateResult("min_trades_per_window", ok, HARD, float(worst), min_per_window, detail)


def gate_walkforward(oos_sharpe, oos_total_return, *, min_sharpe: float) -> GateResult:
    ok = (_is_num(oos_sharpe) and _is_num(oos_total_return)
          and oos_sharpe >= min_sharpe and oos_total_return > 0)
    sh = oos_sharpe if _is_num(oos_sharpe) else None
    if not _is_num(oos_sharpe) or not _is_num(oos_total_return):
        detail = "leak-free walk-forward not computed"
    else:
        detail = (f"OOS Sharpe {oos_sharpe:.2f} (need >= {min_sharpe}), "
                  f"OOS return {oos_total_return:+.2%} (need > 0)")
    return GateResult("walkforward_oos", ok, HARD, sh, min_sharpe, detail)


def gate_realistic(realistic_sharpe, *, min_sharpe: float) -> GateResult:
    ok = _is_num(realistic_sharpe) and realistic_sharpe >= min_sharpe
    detail = (f"realistic full-sample Sharpe {realistic_sharpe:.2f} vs >= {min_sharpe}"
              if _is_num(realistic_sharpe) else "realistic backtest not computed")
    return GateResult("realistic_mode", ok, SOFT,
                      realistic_sharpe if _is_num(realistic_sharpe) else None,
                      min_sharpe, detail)


def gate_harsh(harsh_sharpe, *, min_sharpe: float) -> GateResult:
    ok = _is_num(harsh_sharpe) and harsh_sharpe >= min_sharpe
    detail = (f"harsh-cost Sharpe {harsh_sharpe:.2f} vs >= {min_sharpe}"
              if _is_num(harsh_sharpe) else "harsh backtest not computed")
    return GateResult("harsh_mode", ok, SOFT,
                      harsh_sharpe if _is_num(harsh_sharpe) else None,
                      min_sharpe, detail)


def gate_cost_stress(cost_stress_return, *, min_return: float) -> GateResult:
    cls = classify_cost_stress(cost_stress_return, min_return=min_return)
    ok = cls == "robust"
    highest = None
    if cost_stress_return:
        nums = [k for k, v in cost_stress_return.items() if _is_num(v)]
        if nums:
            highest = float(cost_stress_return[max(nums)])
    detail = f"cost-stress class '{cls}'" + (
        f"; return at max multiplier {highest:+.2%} (need > {min_return:+.2%})"
        if highest is not None else "; no cost-stress data")
    return GateResult("cost_stress", ok, SOFT, highest, min_return, detail)


def gate_stability(stability, *, retain_frac: float, plateau_frac: float,
                   magic_frac: float) -> GateResult:
    """Pass only when no parameter degenerates into a single magic value.

    Each parameter's neighbourhood is classified; the gate fails (⇒ SHADOW) if
    any parameter is ``magic`` or ``dead``. ``ridge`` is tolerated (narrow but
    not a spike); ``plateau`` is the ideal.
    """
    if not stability:
        return GateResult("param_stability", False, SOFT, None, None,
                          "parameter stability not computed")
    classes = {}
    for param, block in stability.items():
        center = block.get("center") if isinstance(block, Mapping) else None
        neighbors = block.get("neighbors") if isinstance(block, Mapping) else None
        classes[param] = classify_stability(
            center, neighbors, retain_frac=retain_frac,
            plateau_frac=plateau_frac, magic_frac=magic_frac)
    bad = [f"{p}={c}" for p, c in classes.items() if c in ("magic", "dead")]
    n_plateau = sum(1 for c in classes.values() if c == "plateau")
    ok = not bad
    detail = (f"{n_plateau}/{len(classes)} params on a plateau; "
              + ("all robust" if ok else f"fragile: {', '.join(bad)}"))
    return GateResult("param_stability", ok, SOFT, float(n_plateau), None, detail)


def gate_benchmark(strategy_score, benchmark_score, *, margin: float,
                   metric_label: str = "Calmar",
                   strategy_return=None, benchmark_return=None) -> GateResult:
    """Must beat buy & hold of the same instrument on a risk-adjusted basis.

    Risk-adjusted (Calmar = annualized return / |max drawdown| by default), not raw
    return, because the product's whole reason to exist is low-drawdown consistency
    — a strategy that merely matches buy & hold's return while taking its full
    drawdown has earned nothing. The score is metric-agnostic: pass whatever
    risk-adjusted number both legs were measured on, with a matching ``metric_label``.
    """
    ok = (_is_num(strategy_score) and _is_num(benchmark_score)
          and strategy_score >= benchmark_score + margin)
    if not _is_num(strategy_score) or not _is_num(benchmark_score):
        detail = "benchmark comparison not computed"
        val = None
    else:
        edge = strategy_score - benchmark_score
        detail = (f"strategy {metric_label} {strategy_score:.2f} vs buy&hold "
                  f"{benchmark_score:.2f} (edge {edge:+.2f}, need >= {margin:+.2f})")
        if _is_num(strategy_return) and _is_num(benchmark_return):
            detail += f"; return {strategy_return:+.2%} vs {benchmark_return:+.2%}"
        val = edge
    return GateResult("benchmark", ok, HARD, val, margin, detail)


def gate_uncertainty(sharpe_lo, prob_below_initial, *, min_sharpe_lo: float,
                     max_prob_below: float) -> GateResult:
    """The edge must survive its own sampling noise.

    The bootstrap lower band of Sharpe must clear ``min_sharpe_lo`` (the point
    estimate being positive is not enough — the *band* must be), and the
    probability of ending below the starting capital must be under ``max_prob_below``.
    """
    have = _is_num(sharpe_lo) and _is_num(prob_below_initial)
    ok = have and sharpe_lo > min_sharpe_lo and prob_below_initial < max_prob_below
    if not have:
        detail = "uncertainty bands not computed"
    else:
        detail = (f"Sharpe lower band {sharpe_lo:.2f} (need > {min_sharpe_lo}); "
                  f"P(end below start) {prob_below_initial:.0%} (need < {max_prob_below:.0%})")
    return GateResult("uncertainty", ok, HARD,
                      sharpe_lo if _is_num(sharpe_lo) else None, min_sharpe_lo, detail)


# ── Aggregation ─────────────────────────────────────────────────────────────
def decide(gates: Sequence[GateResult]) -> FunnelVerdict:
    """Aggregate gate results into a PASS / SHADOW / REJECT verdict.

    Any HARD failure ⇒ REJECT. Otherwise any SOFT failure ⇒ SHADOW. All clear ⇒ PASS.
    """
    hard_fails = [g for g in gates if g.severity == HARD and not g.passed]
    soft_fails = [g for g in gates if g.severity == SOFT and not g.passed]
    if hard_fails:
        return FunnelVerdict(REJECT, [f"HARD {g.name}: {g.detail}" for g in hard_fails], gates)
    if soft_fails:
        return FunnelVerdict(SHADOW, [f"SOFT {g.name}: {g.detail}" for g in soft_fails], gates)
    return FunnelVerdict(PASS, ["all gates cleared"], gates)


def evaluate_candidate(m: CandidateMetrics,
                       t: FunnelThresholds = FunnelThresholds()) -> FunnelVerdict:
    """Run every gate over a candidate's metrics and return the aggregate verdict.

    Pure: no I/O, no backtests — just the gate arithmetic. The order of gates is
    the order they appear in the survivor card and report.
    """
    gates = [
        gate_min_trades(m.total_trades, min_total=t.min_total_trades),
        gate_trades_per_window(m.trades_per_window, min_per_window=t.min_trades_per_window),
        gate_walkforward(m.oos_sharpe, m.oos_total_return, min_sharpe=t.min_oos_sharpe),
        gate_benchmark(m.strategy_benchmark_score, m.benchmark_score,
                       margin=t.benchmark_score_margin,
                       metric_label=m.benchmark_metric.capitalize(),
                       strategy_return=m.strategy_return_vs_benchmark,
                       benchmark_return=m.benchmark_total_return),
        gate_uncertainty(m.uncertainty_sharpe_lo, m.prob_below_initial,
                         min_sharpe_lo=t.uncertainty_min_sharpe_lo,
                         max_prob_below=t.uncertainty_max_prob_below),
        gate_realistic(m.realistic_sharpe, min_sharpe=t.min_realistic_sharpe),
        gate_harsh(m.harsh_sharpe, min_sharpe=t.min_harsh_sharpe),
        gate_cost_stress(m.cost_stress_return, min_return=t.cost_stress_min_return),
        gate_stability(m.stability, retain_frac=t.stability_retain_frac,
                       plateau_frac=t.stability_plateau_frac,
                       magic_frac=t.stability_magic_frac),
    ]
    return decide(gates)


# ── Survivor / rejection cards (pure serialization) ──────────────────────────
def build_survivor_card(*, strategy_id: str, ticker: str, strategy_family: str,
                        params: Mapping[str, object], train_period: str,
                        oos_period: str, cost_assumptions: Mapping[str, object],
                        metrics: CandidateMetrics, verdict: FunnelVerdict,
                        generated_at: str, mode: str = "realistic",
                        extra: Optional[Mapping[str, object]] = None) -> dict:
    """Assemble the full survivor/rejection card dict (every field the spec asks
    for). Pure: no clock, no I/O — ``generated_at`` is passed in by the caller."""
    m = metrics
    trades_per_year = None
    if extra and _is_num(extra.get("trades_per_year")):
        trades_per_year = float(extra["trades_per_year"])

    stability_classes = {}
    if m.stability:
        for param, block in m.stability.items():
            if isinstance(block, Mapping):
                stability_classes[param] = classify_stability(
                    block.get("center"), block.get("neighbors"))

    card = {
        "schema_version": 1,
        "strategy_id": strategy_id,
        "ticker": ticker,
        "strategy_family": strategy_family,
        "generated_at": generated_at,
        "mode": mode,
        "params": dict(params),
        "train_period": train_period,
        "oos_period": oos_period,
        "metrics": {
            "total_trades": m.total_trades,
            "trades_per_year": trades_per_year,
            "trades_per_window": list(m.trades_per_window) if m.trades_per_window else None,
            "oos_sharpe": m.oos_sharpe,
            "oos_max_drawdown": m.oos_max_drawdown,
            "oos_total_return": m.oos_total_return,
            "oos_win_rate": m.oos_win_rate,
            "realistic_sharpe": m.realistic_sharpe,
            "realistic_total_return": m.realistic_total_return,
            "harsh_sharpe": m.harsh_sharpe,
            "harsh_total_return": m.harsh_total_return,
        },
        "cost_assumptions": dict(cost_assumptions),
        "cost_stress": {
            "return_curve": dict(m.cost_stress_return) if m.cost_stress_return else None,
            "sharpe_curve": dict(m.cost_stress_sharpe) if m.cost_stress_sharpe else None,
            "class": classify_cost_stress(m.cost_stress_return),
        },
        "uncertainty": {
            "sharpe_point": m.uncertainty_sharpe_point,
            "sharpe_lo": m.uncertainty_sharpe_lo,
            "sharpe_hi": m.uncertainty_sharpe_hi,
            "prob_below_initial": m.prob_below_initial,
        },
        "parameter_stability": {
            "by_param": {p: dict(b) for p, b in m.stability.items()} if m.stability else None,
            "class_by_param": stability_classes or None,
        },
        "benchmark": {
            "name": "buy_and_hold_same_instrument",
            "metric": m.benchmark_metric,
            "benchmark_score": m.benchmark_score,
            "strategy_score": m.strategy_benchmark_score,
            "benchmark_total_return": m.benchmark_total_return,
            "strategy_total_return": m.strategy_return_vs_benchmark,
            "benchmark_max_drawdown": m.benchmark_max_drawdown,
            "strategy_max_drawdown": m.strategy_maxdd_vs_benchmark,
        },
        "verdict": verdict.verdict,
        "reasons": list(verdict.reasons),
        "gates": [g.to_dict() for g in verdict.gates],
    }
    if extra:
        card["extra"] = dict(extra)
    return card


def card_to_json(card: Mapping[str, object]) -> str:
    """Deterministic JSON serialization of a card (pure)."""
    return json.dumps(card, indent=2, sort_keys=False, default=str)


def _fmt(x, spec: str = ".2f") -> str:
    return format(x, spec) if _is_num(x) else "n/a"


def card_to_markdown(card: Mapping[str, object]) -> str:
    """Render a card as a compact human-readable Markdown report (pure)."""
    m = card.get("metrics", {})
    b = card.get("benchmark", {})
    u = card.get("uncertainty", {})
    cs = card.get("cost_stress", {})
    badge = {"PASS": "🟢 PASS", "SHADOW": "🟡 SHADOW", "REJECT": "🔴 REJECT"}.get(
        card.get("verdict"), card.get("verdict"))
    rc = cs.get("return_curve") or {}
    cost_curve_str = (", ".join(f"{k}×:{_fmt(v, '+.2%')}" for k, v in rc.items())
                      if rc else "n/a")
    lines = [
        f"# {badge} — {card.get('ticker')} ({card.get('strategy_id')})",
        "",
        f"- **Strategy family:** {card.get('strategy_family')}",
        f"- **Generated:** {card.get('generated_at')}  ·  **Mode:** {card.get('mode')}",
        f"- **Params:** `{json.dumps(card.get('params', {}))}`",
        f"- **Train:** {card.get('train_period')}  ·  **OOS:** {card.get('oos_period')}",
        "",
        "## Metrics",
        f"- Total trades: **{m.get('total_trades')}**"
        + (f" (~{_fmt(m.get('trades_per_year'), '.0f')}/yr)" if _is_num(m.get('trades_per_year')) else ""),
        f"- Trades per OOS window: {m.get('trades_per_window')}",
        f"- OOS Sharpe: **{_fmt(m.get('oos_sharpe'))}**  ·  OOS return: {_fmt(m.get('oos_total_return'), '+.2%')}"
        f"  ·  OOS max DD: {_fmt(m.get('oos_max_drawdown'), '+.2%')}  ·  OOS win rate: {_fmt(m.get('oos_win_rate'), '.1%')}",
        f"- Realistic Sharpe: {_fmt(m.get('realistic_sharpe'))} ({_fmt(m.get('realistic_total_return'), '+.2%')})"
        f"  ·  Harsh Sharpe: {_fmt(m.get('harsh_sharpe'))} ({_fmt(m.get('harsh_total_return'), '+.2%')})",
        "",
        "## Robustness",
        f"- Cost stress: **{cs.get('class')}** — return at {cost_curve_str}",
        f"- Uncertainty: Sharpe {_fmt(u.get('sharpe_point'))} "
        f"[{_fmt(u.get('sharpe_lo'))}, {_fmt(u.get('sharpe_hi'))}]  ·  "
        f"P(end below start) {_fmt(u.get('prob_below_initial'), '.0%')}",
        f"- Parameter stability: {card.get('parameter_stability', {}).get('class_by_param')}",
        f"- Benchmark (buy&hold, {b.get('metric')}): strat {_fmt(b.get('strategy_score'))} vs "
        f"{_fmt(b.get('benchmark_score'))}  ·  return {_fmt(b.get('strategy_total_return'), '+.2%')} vs "
        f"{_fmt(b.get('benchmark_total_return'), '+.2%')}  ·  maxDD "
        f"{_fmt(b.get('strategy_max_drawdown'), '+.2%')} vs {_fmt(b.get('benchmark_max_drawdown'), '+.2%')}",
        "",
        "## Verdict",
        f"**{card.get('verdict')}**",
        "",
        "Reasons:",
    ]
    lines += [f"- {r}" for r in card.get("reasons", [])]
    lines += ["", "Gate trail:"]
    for g in card.get("gates", []):
        mark = "✓" if g.get("passed") else "✗"
        lines.append(f"- {mark} [{g.get('severity')}] **{g.get('name')}** — {g.get('detail')}")
    return "\n".join(lines) + "\n"
