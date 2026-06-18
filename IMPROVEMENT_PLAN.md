# MONAD Quant — System Improvement Plan

> **Scope:** a fully fleshed-out plan to improve every system — model, backtest/sweep,
> live execution, data, testing, observability, ops, reporting, code health, and risk.
> Written 2026-06-18 after a deep audit. Pairs with `CLAUDE.md` (strategy "why"),
> `OPERATIONS.md` (live "how"), and `AGENT_CONTEXT_PLAN.md` (navigation).
>
> **Read this first:** the single most important fact is that the strategy's *realistic*
> edge is **marginal/unproven** (41% win rate, +0.115% EV/trade in a fresh realistic
> backtest; ~flat confirmed-fill edge live), while the documented headline (+35% / Sharpe
> 39–94) is an artifact of optimistic-mode backtesting and unreliable paper fills. Therefore
> **every workstream below is ranked against one question: does this help prove, disprove,
> or exploit a real edge?** Do not invest heavily in polish until edge is demonstrated.

---

## 0. Current state (honest one-paragraph summary)

The *infrastructure* is in good shape: two correctness fixes shipped (entry-time
reconciliation guard, software take-profit), Gateway autostart + preflight-gated trader +
healthcheck/export timers, a run-archive/dashboard-reset, an agent context system, 181 tests,
and a runnable backtest. The *evidence* is not: no clean live week yet, no fill-provenance
tracking, and the backtest's parameter-selection layer (walk-forward Sharpe, sweep scoring,
runner metrics) is both **buggy and untested**. The **bottleneck is trustworthy evidence and
a real edge — not features.**

## 1. Guiding principles
1. **Evidence-first.** Prefer changes that produce trustworthy data over changes that add features.
2. **Don't polish an unproven edge.** Gate feature work on a demonstrated edge.
3. **Safety:** paper-only (7497, never 7496); never change live trading logic during an armed run; no secrets in git; push via SSH, never to `main`.
4. **Test the decision layer, not just the mechanics.** Bugs hide where there are no tests — currently the param-selection layer.
5. **One source of truth per fact** (code for invariants, manifest for routing, deep docs for *why*).

---

## Workstream A — Evidence & Validation  ⭐ TOP PRIORITY

**Problem:** we cannot yet trust any performance number. Two independent measurements say
~flat; both are contaminated (paper fills, sizing mismatch, no provenance).

- **A1. Clean-run protocol + analyzer (mostly done).** `ops/analyze_run.py` renders a
  clean-run rubric (≥80% confirmed fills, no time_exit artifacts, no estimated fills, no
  desync, no connection storm) + honest confirmed-fill edge. *Next:* run it daily, accumulate
  a week, and codify a written "ready for real money" checklist (roadmap 6.5).
- **A2. `fill_source` provenance (`actual`/`inferred`/`estimated`).** The single highest-value
  data change. Add an additive `fill_source` column to `trades` (+ to exports), set it in
  `trader.py` at each close path (real bracket fill = `actual`; `_infer_bracket_exit` =
  `inferred`; force-finalized = `estimated`). Without it, live PnL is uninterpretable.
  *Risk:* live path → do it with the trader stopped.
- **A3. Use actual fill price, not `fill_basis`, for entry.** Today the recorded entry is the
  pre-fill estimate (`fill_basis`), so PnL and stop distance are slightly wrong (seen live:
  recorded 81.63 vs actual fill 81.89). Capture the real fill from the bracket parent and
  record it. *Risk:* live path.
- **A4. Fixed-10% realistic re-sweep.** Now supported (`sweep.py TQQQ --sizing fixed
  --fixed-pct 0.10`). Re-establish honest, live-relevant optima at the sizing we actually
  deploy. If still ~flat → that's the answer.
- **A5. Confirmed-fill-only performance as the headline metric** everywhere (dashboard, alerts,
  exports), with artifacts/inferred shown separately and clearly flagged.
- **A6. A/B "what-if" ledger.** For each live trade, also record what the *native* bracket
  would have done vs the software net — to quantify how much the software TP/stop is masking.

## Workstream B — Testing & Verification

**Problem:** coverage is inverted — execution mechanics are A-grade; the param-selection layer
that produced the misleading numbers is F-grade (see the testing analysis).

- **B1. `test_walk_forward.py` + fix the Sharpe bug.** `walk_forward.py:42` annualizes hourly
  returns by `sqrt(252)` (daily assumption) and *selects parameters by it* (line 174). Add
  tests, then fix to annualize by the timeframe (or trade frequency, matching `runner.py`).
  **Highest-leverage test work** — it directly biases optimization.
- **B2. `test_runner_metrics.py`.** Pin Sharpe (trade-frequency annualization), `max_drawdown`,
  `monthly_returns`, `total_return`, buy-hold benchmark on a fixed synthetic equity curve.
- **B3. Golden-master pipeline regression.** A fixed synthetic OHLCV dataset → assert exact
  trade count / equity curve / Sharpe, so any engine/sizing change that alters results is
  caught automatically (today this is verified by hand).
- **B4. `test_sweep_scoring.py`.** Cover `live_score` penalties (stop-hit ratio, neg months,
  ambiguous, <5 trades/mo, holdout degradation) and `extract_metrics`.
- **B5. `test_fetcher.py`.** OHLC invariants (`low ≤ open/close ≤ high`), retry/backoff,
  cache fallback, bar-continuity, 730-day clamp.
- **B6. `test_broker.py` (mock IBKR).** Bracket construction (GTC children, OCA, transmit
  sequencing), three-tier fill search, reconnect/backoff, `cancel_and_close`. Biggest
  untested live-risk surface.
- **B7. Full `_on_bar_inner` flow tests.** End-to-end cycle: flat→entry, holding, exit→
  reconcile, pending-close retry/force-finalize, signal-fetch-failure escalation.
- **B8. Tooling:** add `coverage`/`pytest` to `requirements-dev.txt`, a CI coverage report
  with a floor (e.g., fail under 70% on `src/`), and pre-commit hooks (black/ruff/isort).
- **B9. Property-based tests (`hypothesis`).** For `compute_trade_returns`: for any random
  price path, recorded return must equal (exit−entry)/entry for the chosen exit, and exit
  type ∈ the valid set. Catches edge cases example tests miss.

## Workstream C — Backtest & Sweep Workflow

**Problem:** the backtest is structurally disconnected from live execution, so its optima don't
transfer; and the sweep optimizes a sizing model the live trader doesn't use.

- **C1. Sizing alignment (partly done).** `--sizing`/`--adaptive` added. *Next:* make the
  sweep default to the live sizing (fixed-10%) so reported numbers reflect reality, and print
  a prominent "sizing = X (live = fixed 10%)" banner.
- **C2. Model the bracket-fill reality in the backtest.** The backtest assumes clean target/
  stop/time exits; live brackets are unreliable. Add a configurable **fill model** (fill
  probability, slippage on stops, same-bar pessimism already exists) so backtests reflect
  live execution risk — closing the backtest↔live gap.
- **C3. Fee/slippage realism per instrument/broker.** Generalize `_estimate_spread`; bake
  round-trip cost into EV so the sweep stops selecting high-trade-count configs that lose to
  fees. (TQQQ is commission-free but has spread/slippage.)
- **C4. Sweep objective review.** `live_score` weights Sharpe×0.5 — and Sharpe scales with
  √(trade frequency), biasing toward churn. Consider optimizing **net-of-cost EV/trade ×
  trades**, or a deflated Sharpe, with a hard penalty on <34% WR at 2:1 R:R.
- **C5. Walk-forward as the primary selector** (after B1 fix), not single-split holdout —
  rolling-origin OOS with multiple windows; report OOS-vs-train degradation prominently.
- **C6. Multiple-testing / overfitting controls.** The sweep tries many param combos; add a
  deflation/Bonferroni-style adjustment or a minimum-OOS-Sharpe gate so the "winner" isn't
  just the luckiest of N.
- **C7. Reproducibility.** Pin the data window + a data hash in `sweep_results_*.json` so a
  result is reproducible; the `_update_mode_param` helper (added) should be used everywhere to
  kill the dual-sync hazard.

## Workstream D — The Model / Strategy (research — shadow-mode only)

**Problem:** the realistic edge is marginal (41% WR at 2:1 R:R = +0.115% EV/trade). The
documented thesis (mean-reversion RSI dips in confirmed regimes) may simply not produce edge
in current TQQQ data. **Treat all of these as offline/shadow research; never wire to live
without OOS evidence.**

- **D1. Diagnose the WR collapse.** Realistic 41% vs documented 70.9% (optimistic). Is the
  41% real, or an artifact of pessimistic same-bar ambiguity on tight stops? Decompose:
  how many losses are "stop hit before target on the same bar"? If many, the stop is inside
  intraday noise → widen stop / use ATR-scaled stops (the long-deferred 5.2).
- **D2. ATR-scaled stops & targets.** Fixed 0.5% stop is inside TQQQ intraday range; scale
  stop/target by recent ATR so they sit outside noise. Could lift WR materially. Shadow-test.
- **D3. Regime-lag fix (the documented #1 unsolved problem).** The 252-MA stays bullish into
  20–30% corrections → longs into falling knives. Ideas: softer 5%-below-50MA gate (5.1,
  flag exists), volatility circuit breaker (skip entries when 5-day vol > 3× 20-day),
  adaptive RSI threshold when recent WR < 40%.
- **D4. Exit logic.** Time-exit (10 bars) may exit winners early or hold losers; test
  trailing stops, partial profit-taking, or a volatility-scaled hold time.
- **D5. Entry quality over quantity.** Signal fires on 50% of bars but edge is thin — tighten
  entries (require both momentum AND volume signal; deeper RSI; regime conviction) and measure
  EV/trade, not trade count.
- **D6. Instrument selection.** SOXL showed the best documented robustness (0/22 negative
  windows) but wasn't realistic-revalidated; LABU/TNA likewise. Run the fixed-10% realistic
  sweep across all instruments and pick by *realistic* EV, not optimistic Sharpe.
- **D7. Honest fallback.** If no configuration clears ~0.5%/mo net on confirmed fills OOS,
  accept the strategy as a **low-return capital-preservation vehicle** (its real strength is
  near-zero drawdown) or re-derive the signal entirely. Recognizing this is a *win*, not a
  failure.
- **D8. Shadow evaluator (infrastructure for all of D).** A non-trading process that replays
  bars and logs what a *candidate* config would have done, to a separate file/table — answers
  "would a different model have traded here?" without risking live.

## Workstream E — Live Execution & Brokerage

**Problem:** IBKR *paper* brackets fill unreliably; the software net backstops but masks; and
provenance/recovery have gaps.

- **E1. Root-cause paper bracket non-fills.** Use `tools/diagnose_brackets.py` during open
  positions + TWS/IBC logs to determine if it's submission, OCA, tif, or the paper fill-engine.
  Determines whether the strategy is viable in a *funded* account (where brackets do fill).
- **E2. Software take-profit/stop hardening (done for TP).** Confirm both nets fire reliably;
  add a software take-profit "fill unavailable" escalation mirroring the stop path.
- **E3. Mid-market Gateway auto-recovery.** Today the healthcheck *observes* but doesn't
  restart. Add a watchdog: if 7497 is down during market hours, restart the gateway service
  (rate-limited) and alert.
- **E4. Reconciliation robustness.** The hourly cycle leaves a stale `open` in `state.db`
  between a between-cycle fill and the next cycle (seen live). Consider a faster reconcile tick
  or event-driven fill callbacks; ensure the desync guard covers short positions and partial fills.
- **E5. Order-type experiments (funded only).** If paper brackets are the issue, test
  marketable-limit or attached-order variants — but only after E1.
- **E6. Real-account dry validation.** Before any real money: a documented 2-week paper
  validation (cycle stability, ≥95% live mark sources, no CRITICALs, no desyncs).

## Workstream F — Data Pipeline

**Problem:** yfinance is rate-limited (429s seen) and unvalidated; bad data silently corrupts
signals.

- **F1. Fetcher hardening (some done).** Retry/backoff + cached fallback exist for live
  signals; extend OHLC validation, bar-continuity checks (no >1h gaps in market hours, DST),
  and a 730-day clamp (fixed in `main.py`, generalize).
- **F2. yfinance 429 mitigation.** Aggressive local caching of bars (parquet), a single shared
  fetch per cycle, and exponential backoff; consider a backup source (Alpha Vantage is wired
  for BTC) or a paid feed if scaling.
- **F3. Data-quality time series.** Log fetch health (429s, stale bars, gaps) to a table so
  data degradation is visible and correlatable with bad trading days.
- **F4. Point-in-time correctness.** Ensure no look-ahead in feature construction at the data
  layer (signals already `.shift(1)`; verify the fetch/feature boundary).

## Workstream G — Observability & Operations

- **G1. External alerting (Phase 6.4).** CRITICAL events (force-finalize, software-stop,
  desync block, N consecutive signal failures) land in SQLite but page nobody. Wire a Slack/
  ntfy/email webhook. **Gate real money on this.**
- **G2. Model/run versioning.** Stamp `model_version` (a `config.py` constant) + `git_commit`
  on each signal/trade so results are attributable to a config generation. Until schema
  changes, log at trader startup.
- **G3. Signal-reason + no-trade-reason logging.** For every cycle, record decision
  (enter/hold/exit/no-trade), reason codes, key inputs, data freshness, and *why we didn't
  trade* (stale data, gateway down, not flat, no signal, outside hours). Turns the dashboard
  into a debuggable narrative.
- **G4. Dashboard benchmark comparison (paused feature).** Bot vs QQQ/SPY/TQQQ over the same
  window, compounded, with confirmed-fill filter — *do this once edge is shown* (a flat
  strategy vs QQQ just confirms it's flat).
- **G5. Auto-refresh `OPERATIONS.md` changelog / a run journal** so the institutional memory
  stays current cheaply.

## Workstream H — Reporting Integrity

- **H1. Unify the return calc.** Dashboard (compounded, 62 PROD trades) ≠ alert path
  (simple-sum, 65 all trades). Extract one shared `src/analysis/performance.py` used by both;
  pick compounded + one trade population; label (don't hide) estimated trades.
- **H2. Fill-quality note** in every performance view ("includes N inferred / N estimated
  fills"); never let synthetic fills silently inflate the headline.
- **H3. Annualization consistency.** Use the same Sharpe annualization (trade-frequency)
  everywhere — runner is correct; walk-forward is wrong (B1).

## Workstream I — Code Health & Tech Debt

- **I1. Branch hygiene + merge to `main`.** ~20 commits on `pi-ops-automation` never merged;
  the two correctness fixes live only on feature branches — **`main` still has the desync &
  bracket bugs.** Open PRs, define a merge order, land the fixes on `main`.
- **I2. Config consolidation.** ~165 params; remove ~12–15 dead ones (`ROC_PERIOD`,
  `ATR_PERIOD`, `BB_STD`, unused `BB_WINDOW_*`); collapse the 3-way mode routing (MODE_MAP /
  `_MODE_TO_ASSET` / `ASSETS`) into one registry; finish the `ModeConfig` migration; centralize
  the 18 scattered `BACKTEST_*` date params.
- **I3. Dependency hygiene.** `requirements.txt` regenerated from the live venv (done);
  keep `requirements-dev.txt` for backtest/test extras; consider a lockfile + `pip-tools`.
- **I4. Doc-drift prevention.** `AGENTS.md` deduped to a pointer (done); the manifest
  anti-drift test guards invariants — extend it to assert documented params match `config.py`.
- **I5. Refactor duplication** (MA/MACD-turn logic into `src/signals/utils.py`); split
  `compute_trade_returns` (181 LOC) exit-classification into a helper (tests cover it).
- **I6. Plugin manifest cleanup** (`.claude-plugin/plugin.json` references missing commands).

## Workstream J — Risk Management

**Problem:** the system has near-zero modeled drawdown but few explicit live risk controls.

- **J1. Hard risk limits in the live trader.** Per-day loss limit, max consecutive losses →
  pause, max position notional, max open exposure. Independent of the strategy signal.
- **J2. Circuit breakers.** Halt new entries on: volatility spike (5-day vol > 3× 20-day),
  data degradation (stale/gappy bars), or repeated bracket-fill failures.
- **J3. Drawdown-aware sizing.** The adaptive Kelly de-risks on low rolling WR; add an
  account-equity drawdown throttle (reduce size after X% drawdown).
- **J4. Kill switch.** A single documented command/flag to flatten and halt (the software stop
  + `systemctl stop` exist; formalize + alert).

---

## Prioritized roadmap (phased)

```
PHASE 0 — Evidence gate (this week, mostly done/in-flight)        ⭐ blocks everything
  A1 clean-run analyzer (done) · run daily · A4 fixed-10% re-sweep (post-run)
  → Decision: does a real edge exist?

PHASE 1 — Trustworthy data (post clean-run, trader stopped)
  A2 fill_source · A3 actual-fill entry · H1 unify reporting · B1 walk-forward fix+tests

PHASE 2 — Test the decision layer (parallelizable, safe)
  B2 runner metrics · B3 golden-master · B4 sweep scoring · B5 fetcher · B8 coverage

PHASE 3 — Close the backtest↔live gap
  C1 sizing default · C2 fill model · C3 fees · C4 objective · C5 walk-forward primary

PHASE 4 — Strategy research (only if Phase 0 shows promise; else pivot per D7)
  D1 WR diagnosis · D2 ATR stops · D3 regime-lag · D5 entry quality · D6 instrument re-eval
  (all shadow-mode via D8)

PHASE 5 — Production hardening (gate real money on these)
  G1 external alerting · E3 gateway auto-recovery · E6 2-week validation · J1–J4 risk limits

PHASE 6 — Tech debt & polish (as capacity allows)
  I1 merge to main (do early — main has the bugs) · I2 config · B6/B7/B9 · G2/G3 · G4 benchmarks
```

## Decision gates (do not skip)
1. **After 1 clean week + fixed-10% re-sweep:** if confirmed-fill edge < ~0.5%/mo net →
   **pivot** (re-derive signal or repurpose as capital-preservation) before further investment.
2. **Before real money:** G1 (alerting) + E6 (validation protocol) + J1 (risk limits) + brackets
   demonstrably reliable (E1).
3. **Before merging optimizer-selected params:** B1 (walk-forward Sharpe fixed) must land first,
   or selection is biased.

## Appendix — already shipped (2026-06-17/18, on `pi-ops-automation`)
Reconciliation guard · software take-profit · Gateway autostart (IBC+Xvfb+timer) ·
preflight-gated trader · healthcheck/export timers · run archive + dashboard run-window reset ·
agent context system (`AGENT_INDEX.md`/`context_map.json`/`ctx`) · sizing extraction + 25 tests ·
runnable backtest (matplotlib optional) + date-clamp fix · `requirements.txt` regen · CI full-suite ·
`AGENTS.md` dedup · `ops/analyze_run.py` · parameter & testing audits.

### Session 2026-06-18 (testing workstream B + I1) — on `pi-ops-automation`, offline-only
Decision/measurement layer that produced the misleading numbers is now tested
(was F-grade); no live-trader path was modified. Test count 181 → 269.
- **B1** — fixed walk-forward Sharpe annualization (`_sharpe` used a fixed
  `sqrt(252)`; now annualizes by actual trade frequency, matching `runner.py`) + 10 tests.
- **B2/B3** — extracted `src/backtest/metrics.py` (pure Sharpe/drawdown/return/monthly);
  `runner.py` delegates to it; `walk_forward._sharpe` reuses it (one Sharpe impl now).
  20 tests + a config-independent metrics golden-master.
- **B4** — extracted `src/optimization/sweep_scoring.py` (`extract_metrics` + `live_score`,
  spread/price now explicit args) so the param-selection scorer is importable/testable;
  `sweep.py` keeps a behavior-preserving wrapper. 19 tests covering every penalty tier.
- **B5** — `tests/test_fetcher.py` (15): OHLC-invariant validation, yfinance retry/backoff,
  cache freshness.
- **B6** — `tests/test_broker.py` (20, ib_insync mocked): bracket construction, three-tier
  fill search, cancel/close, reconciliation reads. `broker.py` not modified.
- **B8** — CI now runs under `coverage` with a `src/`-only floor (`--fail-under=65`;
  baseline 71%); `coverage`/`hypothesis` added to `requirements-dev.txt`; opt-in
  `.pre-commit-config.yaml` (ruff + private-key/large-file guards); coverage artifacts gitignored.
- **B9** — `tests/test_compute_returns_properties.py` (hypothesis, guarded import):
  exit-type/return invariants, slippage shift, determinism over random price paths.
- **Bug fix (found via B9)** — `walk_forward._run_slice` had drifted from the engine API
  and **crashed** `main.py --mode=walk-forward` (DataFrame unpacked as a 2-tuple;
  stale `use_ma_regime_filter` kwarg). Fixed + end-to-end optimizer test added.
- **I1** — the two correctness fixes cherry-picked clean onto `main` and pushed as
  `land-desync-guard` and `land-software-take-profit` (PRs to be opened; `main` still has the bugs).

**Still open in B:** B7 (`_on_bar_inner` end-to-end flow tests). The 8 commits sit
**locally** on `pi-ops-automation` (not pushed). Next evidence items (A2 fill-provenance,
A4 fixed-10% re-sweep) need the trader stopped.
