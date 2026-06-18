# Audit — Most Effective Next Changes (2026-06-18)

Read-only audit + the one diagnostic that reframes everything. No trading/strategy
logic changed (trader armed for 09:22 ET). Branch: `pi-ops-automation`.

## The reframing diagnostic — the edge is marginal, not broken plumbing

A realistic TQQQ backtest signal-funnel (3,117 hourly bars, 2024-06 → 2026-04):

| | |
|---|---|
| `signal_vote >= 1` (entry candidates) | **1,569 / 3,117 bars (50%)** — *not* signal-starved |
| trades taken | 151 |
| **win rate (realistic)** | **41.1%** (88 stops vs 62 targets, 2:1 R:R) |
| **EV / trade** | **+0.115%** (0.411×1.0% − 0.589×0.5%) — barely above breakeven |
| net | +1.45% total / **+0.08%/mo** / Sharpe ~1.2 |

The documented **70.9% WR / Sharpe 94** was **optimistic-mode** (stop loses same-bar
ambiguity, sub-spread stops). Under realistic execution the per-trade edge is **marginal**.
This matches the live confirmed-fill edge (**+0.2%**). **Two independent measurements say the
strategy's real edge is ~flat.** The bottleneck is not infrastructure — it's whether an edge
exists at the sizing/execution we actually deploy.

## Most effective next changes (by leverage)

### Tier 1 — do these, in order
1. **Let the 09:22 ET run happen, then run `ops/analyze_run.py`** (today). Zero code. First run with both fixes. The new analyzer renders a clean-run verdict + the honest confirmed-fill edge in one command.
2. **`fill_source` provenance** (`actual`/`inferred`/`estimated`) — the highest-value code change; without it live PnL is uninterpretable. Touches the live path → **post-run, trader stopped**.
3. **Fixed-10% realistic re-sweep** (`sweep.py TQQQ --sizing fixed --fixed-pct 0.10`, now supported) — answers "edge at the sizing we deploy?" Heavy compute, post-run. If still ~flat, that's the answer.

### Tier 2 — high value, lower urgency
4. ~~Root-cause trade frequency~~ **DONE (above): it's a WR/edge problem, not frequency.**
5. **Unify dashboard ↔ alert return calc** (compounded/62 vs simple-sum/65). Reporting-only, low risk.
6. **Diagnose why paper brackets don't fill** (IBC/TWS) — gates funded-account viability.

### Tier 3 — operational hardening (before real money)
7. Mid-market Gateway auto-recovery + external alerting (Phase 6.4). 8. Walk-forward `sqrt(252)` Sharpe fix (A.2).

### ❌ Not effective now
Benchmark dashboard, dead-param cleanup, more parameter tuning — all polish a strategy whose
edge isn't demonstrated. Don't spend here until a clean run + fixed-10% re-sweep show edge.

## Tooling added this pass
- **`ops/analyze_run.py`** — read-only run analyzer: confirmed-fill vs artifact vs estimated
  performance, software-net/inferred/desync/connection counts, and a **clean-run rubric**
  (≥80% confirmed fills, no time_exit artifacts, no estimated fills, no desync, no conn storm).
  Run it on the old data → `VERDICT: NOT clean` (correctly flags the contamination).

## The honest recommendation
Treat next week as a **go/no-go gate**: one clean week (with `fill_source`) + a fixed-10%
realistic re-sweep. **If confirmed-fill edge stays < ~0.5%/mo, stop investing in this
strategy's infrastructure** — re-derive the signal or repurpose it as capital-preservation.
The marginal 41% realistic WR strongly suggests this is the likely outcome; recognizing it
early is worth more than any Tier 2/3 feature.
