# MONAD-quant — The Active-vs-Static Research Program

*A self-contained, adversarially-verified body of work answering one question:
**does MONAD's active mean-reversion engine actually beat a simple static allocation — and if not, what is the honest product?***

This directory is the durable record. Each study is a committed, deterministic, leak-free tool
(`tools/*_study.py`) + a standalone writeup, cross-linked to the `RESEARCH_WEB.md` idea graph
(run `venv/bin/python tools/ctx.py web <node>`). Every study was hardened by an independent
multi-agent skeptic panel before it was committed; the corrections those panels forced are
recorded in each writeup's *Status* and *Surviving Caveats*.

> **Why this exists.** The headline performance in `CLAUDE.md` (Sharpe 25–94, "production-ready")
> is **superseded** — it came from optimistic-mode backtests on morning-only data ([[F13]]), and
> the live bot is flat. The go/no-go ([[D6]]) found the active engine has no risk-adjusted edge
> over a trivial static allocation. This program tests that conclusion to destruction, then asks
> what the honest product really is.

## The shared methodology

Every study uses the same disciplines, which is what makes the collection trustworthy:

- **Leak-free** — entries/weights use only lagged information (`.shift(1)`); windows verified
  byte-identical to a truncated re-computation.
- **Bootstrap confidence intervals** — paired block bootstrap (block=20, B=5000, seed=0) of the
  *difference* vs the benchmark, so every claim is a CI, not a point estimate. (Promoted from the
  research lab into a shared, unit-tested module: [`src/backtest/uncertainty.py`](../../src/backtest/uncertainty.py).)
- **Pre-registration & out-of-sample discipline** — pass criteria stated before the test; the one
  live hypothesis (gold) was settled on a genuine disjoint holdout.
- **Adversarial verification** — each study was checked by a 2–5 lens skeptic panel (construction,
  leak-freeness, statistics, interpretation) that re-ran the code and tried to refute the verdict.
- **One source of truth** — all studies reuse the same vetted primitives; no divergent Sharpe or
  drawdown implementations.

## The twelve studies

Studies 1–10 are the **active-vs-static** arc (does MONAD's engine beat a static allocation, and what is the honest product). Studies 11–12 are a follow-on **product-universe** program (is there a *better asset universe* than the static 60/40 the arc landed on — and does the one structural escape, a held-to-maturity ladder, actually deliver).

| # | Study | Question | Honest finding | Nodes · Doc |
|---|---|---|---|---|
| 1 | Power & equivalence | Is D6's "no edge vs static" genuine, or just underpowered? | Mostly **evidence-of-absence** — TOST equivalence to static within ~0.3 Sharpe over 26.5yr; the MR *signal* is provably real but provably *not* tradeable-better-than-static. | E25/F34 · [doc](D6_power_equivalence_study.md) |
| 2 | vs the recommended 60/40 | Does active beat the *decision-relevant* static 60/40 (not the easier 50/50)? | **No** — lower point Sharpe (−0.17/−0.26), nearly significantly worse over 24yr. | E26/F35 · [doc](D6_active_vs_6040_study.md) |
| 3 | Crisis low-drawdown overlay | Is the active engine's drawdown protection concentrated in crises? | **Real but small-N** — reliable vs naked buy&hold (8/8), not vs 60/40; paid for by calm-market under-participation → Sharpe ≈ static. | E27/F36 · [doc](D6_crisis_overlay_study.md) |
| 4 | Best build (overlay) | Does *any* active overlay (constant-weight or regime-conditional) improve a 60/40 core? | **No build** clears the bootstrap; the engine is a capital-preservation overlay, never a risk-adjusted edge. | E28/F37 · [doc](D6_overlay_build_study.md) |
| 5 | Optimize the static product | Honest 60/40 ceiling, rebalancing realism, a third sleeve? | ~Sharpe 0.85 (dividends add only +0.03); rebalance-robust; **no single sleeve reliably improves it** (gold borderline, best-of-3, fails Bonferroni). | E29/F38 · [doc](D6_static_product_study.md) |
| 6 | Out-of-sample gold test | Does study #5's gold sleeve survive a clean 2004–2013 holdout? | **Does not confirm** (holdout straddles 0, though underpowered) — a discretionary diversifier, not a confirmed upgrade. | E30/F39 · [doc](D6_gold_oos_study.md) |
| 7 | Structural levers | Does vol-targeting or risk parity beat the fixed 60/40? | **Neither** — vol-timing is an unreliable tilt (leverage is Sharpe-invariant); risk parity is a bond-bull regime bet that reverses OOS. | E31/F40 · [doc](D6_voltarget_riskparity_study.md) |
| 8 | Forward expectation | At 2026 yields, does the 60/40 meet the ~3.75% income goal (D4)? | Forward ~5–6%/yr **clears the income goal** (P≈67%), but with ~−23% median worst drawdown it **fails the "near-zero drawdown" aspiration**. | E32/F41 · [doc](D6_forward_expectation_study.md) |
| 9 | Goal-optimal mix | Is 60/40 the right static mix for *this* goal? | **No — too equity-heavy.** A more conservative ~30–40% equity mix weakly dominates 60/40 (higher goal-odds, Sharpe, *and* shallower drawdown) because forward bonds out-Sharpe forward equity; but no mix clears 3.75% reliably (best ~70%). | E33/F42 · [doc](D6_weight_optimization_study.md) |
| 10 | Live ↔ backtest reconciliation | *Why* is the live bot flat vs the Sharpe-25 backtest? (quantifies F28) | The bot trades a **coarse-timescale signal at an hourly frequency with no edge** (autocorr negative daily, ~0/positive hourly). **Both headlines are mirages** — the backtest's from morning-only sampling, the live dashboard's +37% from exit-accounting; the two *honest* numbers (backtest ≈ 0, live CONFIRMED +1.5%) agree: flat. | E34/F43 · [doc](D6_live_backtest_reconciliation.md) |
| 11 | Income product universe | Is there a *better asset universe* (munis, credit, preferreds, options-income, dividend/low-vol, treasuries) than the static 60/40? | **No** — across this liquid cross-section **high yield ≠ low drawdown**: the income-rich names (PFF/HYG/JNK/options-income) carry equity-like-or-worse drawdowns *and* erode principal (QYLD spend-the-income DD −42%); **nothing** clears the ~3.75% income floor with even a <20% drawdown. The lever that beats 60/40 on drawdown is still study #9's (tilt conservative). The one structural escape (untested) is a held-to-maturity IG/Treasury **ladder**. | E35/F44 · [doc](D6_product_universe_study.md) |
| 12 | Held-to-maturity ladder | Does the ladder (#11's structural escape) actually deliver income with low drawdown? | **Yes — but it trades risk, not eliminates it.** Realized (hold-to-maturity) drawdown ~0 at ≈entry yield (1962–2026 sim + real iBonds/Bullet ladders), but: the 0% is *amortized-cost definitional*; the MTM-drawdown reduction is *just lower duration* (SHY beats the 2020 ladder on both return and DD); it's *nominal only* (−19% **real** in the 1970s); and floor-clearing is *forward-only* (no empirical ladder cleared 3.75%). Converts market risk → term + reinvestment + inflation risk + zero upside. | E36/F45 · [doc](D6_bond_ladder_study.md) |

## The complete answer

**1. The active engine has no risk-adjusted edge over a static allocation — at any timescale, vs any benchmark, in any build.**
Hourly is flat ([[F13]]); daily mean-reversion is real as a *signal* but not tradeable-better-than-static (#1); it loses to the recommended 60/40 (#2); its crisis protection is real but small-N and Sharpe-neutral (#3); and no overlay — constant-weight or regime-conditional — reliably improves a 60/40 core (#4). The slope-regime "core innovation" is in fact dead-wired ([[F26]]).

**2. The honest product is a simple static 60/40 — and it is hard to beat reliably, in this universe or a different one.**
~Sharpe 0.85, robust to the rebalance rule, with no single third sleeve, vol-targeting, or risk-parity overlay that survives a fair bootstrap (#5, #6, #7). Gold is the one borderline-promising diversifier, but it fails a clean out-of-sample test and is a discretionary judgment call, not an evidence-backed edge. And widening the search to a whole *different asset universe* — munis, credit, preferreds, options-income, dividend/low-vol, treasuries — does not help: **high yield ≠ low drawdown** across that cross-section (the income-rich names carry equity-like-or-worse drawdowns *and* erode principal), nothing clears the ~3.75% income floor with even a <20% drawdown, and no income ETF dominates the 60/40 (#11). The one structural escape — a **held-to-maturity Treasury/IG ladder** — genuinely does deliver income with ~0 *realized* drawdown (#12), but it is not a free lunch: the 0% is amortized-cost *definitional*, the mark-to-market drawdown reduction is *just lower duration* (a plain short ETF gets it), it is *nominal only* (−19% real in the 1970s), and it clears 3.75% only as a *forward* claim — it converts market risk into term + reinvestment + inflation risk + zero upside. The honest "income with low drawdown" product exists only as that ladder, for an investor who can commit capital to a horizon.

**3. Forward-looking, the product clears the income goal but not the drawdown goal — and the goal-optimal mix is more conservative than 60/40.**
At 2026 starting yields the 60/40 should return ~5–6%/yr (forward Sharpe only ~0.5) — more-likely-than-not above the ~3.75% APY target ([[D4]]; P≈67%, a ~1-in-3 chance of missing over a decade) — but with equity-like tail risk (~−23% median worst drawdown). The original "near-zero drawdown" aspiration is **unattainable by any honest static or active build** in this program (#8). And because forward bonds out-Sharpe forward equity, the *goal-optimal* static mix is **more conservative than 60/40** (~30–40% equity), which weakly dominates 60/40 on goal-odds, Sharpe, *and* drawdown — though no mix makes 3.75% a sure thing (#9).

**4. The live bot's flat result is fully reconciled — nothing is broken.**
It faithfully trades a signal whose mean-reversion edge lives at the *daily* timescale and vanishes at the *hourly* frequency it runs ([[F13]]/[[F14]], re-derived on the live instrument). The two eye-catching numbers are both artifacts: the Sharpe-25 backtest from morning-only sampling (× unused adaptive-Kelly sizing [[F28]], holdout selection [[F2]], optimistic fills), and the +37% live dashboard from exit-accounting (inferred `target_hit` + max-bars `time_exit` marks). The two *honest* numbers — full-session backtest ≈ 0 and live CONFIRMED +1.5% — agree: flat (#10). This quantifies [[F28]]: the live↔backtest disconnect is dominated by **bar-frequency**.

> **Bottom line.** MONAD's "high-yield-bond-ETF alternative" is achievable on **return** as a simple
> static 60/40, but **not** as a near-zero-drawdown active product. The active mean-reversion engine
> is, at best, a discretionary low-drawdown overlay — never a measurable risk-adjusted edge.

## Navigating & reproducing

- **Idea graph:** `venv/bin/python tools/ctx.py web <E25..E36 | F34..F45 | D6 | D4>` · `ctx why <node>` · `ctx neighbors <node>`
- **Reproduce any study:** `venv/bin/python tools/<name>_study.py` (deterministic, seed=0; studies #6/#8/#11/#12 fetch once to `/tmp`).
- **The shared uncertainty module** (CIs on any backtest): `venv/bin/python -m src.backtest.uncertainty`
- **Honest live/performance state:** `ctx perf` · `ctx web --live`
