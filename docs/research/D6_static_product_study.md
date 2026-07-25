# Study #5 — Can the Recommended Static 60/40 Product Itself Be Improved? (Honest Ceiling, Rebalancing, Third Sleeve)

**Artifact:** [`tools/static_product_study.py`](../../tools/static_product_study.py) · **Reproduce:** `venv/bin/python tools/static_product_study.py`
(deterministic, seed=0, ~1 min; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E29 (the study) · F38 (the finding) · **builds on / tests** the recommended product from study #4 ([E28/F37](D6_overlay_build_study.md)), the go/no-go ([[D6]]) and 26yr confirmation ([[F25]]).
**Status:** verdict **HOLDS** (with three framing softenings) — adversarially verified by a 3-lens skeptic panel (accounting & rebalancing-simulator correctness; dividend-fairness & multiple-comparisons statistics; interpretation/honesty). Every reported number reproduces **byte-identically**. `blocking=false`, `verdict_holds=true`. No issue invalidates a finding. The dividend-vs-composition conflation in #1 was **fixed in-tool** (it now reports the true dividend correction + the composition split directly); the two remaining MAJOR issues are *disclosure* gaps — the best-of-3 multiple-comparisons discount on the gold sleeve and the QQQ-growth-tilt & bond-bull-market regime caveats on the ~9.5% CAGR — recorded explicitly in Results and Surviving Caveats.

## The Question (the constructive pivot)

Studies #1–4 ([[E25]]–[[E28]]) were all **evaluative** and the active engine lost: no risk-adjusted edge vs static 50/50 ([[F34]]), none vs the decision-relevant 60/40 ([[F35]]), its low-drawdown edge is crisis-concentrated and Sharpe-neutral ([[F36]]), and **no overlay build** — constant-weight or regime-conditional — reliably improves the 60/40 core ([[F37]]). That closes the active-vs-static arc: **the recommended product is a pure static 60/40.** This study flips from *"can active beat static?"* to **"is the static product itself as good as we can simply make it?"** — characterizing the honest 60/40 and testing three improvement levers, with the same paired-bootstrap rigor used against the active engine.

Three questions the active-vs-static arc kept deferring:
1. **Dividend-correct ceiling.** Studies #2–4 built the long-history equity leg partly from `^GSPC`, a **price-only** index. What is the honest total-return 60/40, and how much did the price-only leg understate it?
2. **Rebalancing realism.** The prior 60/40 was an idealized zero-cost daily-rebalanced blend. How much does the rebalance schedule matter, and what is the honest after-cost number?
3. **A third sleeve.** Does adding gold (GLD), long Treasuries (TLT), or credit (HYG) **reliably** lift the 60/40's Sharpe/Calmar (paired bootstrap), or is it path-dependent like everything else?

## Methodology (read-only; reuses the two cached price universes — no new fetch; deterministic)

**Convention — SIMPLE-return product accounting.** A constant-weight daily-rebalanced portfolio's return *is* the weight-average of component simple returns (`0.6·r_eq + 0.4·r_bond`), which is exact for a product study. This was verified to machine precision against the analytic blend (max|diff| = 3.1e-16 over 6009 days). Consequently absolute Sharpes differ ~0.01 from the prior **log-convention** studies (E25–E28); relative comparisons are internally consistent.

- **Universes (reused caches, all `auto_adjust` total-return except `^GSPC`):** `ps.load_2000` (2000 cache: `^GSPC`+QQQ+IWM+DIA+IEF, span 2002-07-31→2026, 6010 trading days, sliced to IEF inception) and `ps.load_2014` (2014 cache: SPY+QQQ+IWM+DIA+GLD+TLT+HYG+IEF, span 2014-01-03→2026, 3133 days).
- **Rebalancing simulator** (`sim_rebalance`): a target-weight 2-asset portfolio that lets weights drift and rebalances on a schedule (daily / monthly / quarterly / annual period-ends) or a drift band, paying `cost` (5bps) per unit one-way turnover at each rebalance; returns realized daily returns, CAGR, and annualized turnover. Independently re-implemented by the skeptic panel and matched **bit-exactly for all six schedules** (max|daily-return diff| = 0.00; rebalance counts 6009/287/95/24/21/0 reconcile).
- **Third-sleeve carve:** `blend10 = 0.55·equity + 0.35·bond + 0.10·sleeve` — the 10% sleeve carved exactly 50/50 from the 0.6 equity and 0.4 bond legs (weights sum to 1.0). A weight sweep (0–20%) accompanies the pre-specified 10% point.
- **Paired block bootstrap** (`BLOCK=20`, `B=5000`, `seed=0`): a single block-start array drives BOTH `blend10` and `core` each iteration (real pairing), percentile CI on the difference for ΔSharpe / ΔCalmar / ΔmaxDD.

## Results

### #1 — Honest ceiling: dividends vs composition (2002-07-31→2026-06-18, 6010 days)

The tool isolates the **true dividend effect** by keeping the *same* 4-asset basket (^GSPC+QQQ+IWM+DIA) and adding the ^GSPC dividend (~1.9%/yr, empirically 1.89% from ^GSPC 12.0% vs SPY 13.9% CAGR over the 2014 overlap) back to that one price-only leg — *not* by dropping ^GSPC. The all-total-return ETF basket is reported separately as a **composition variant** (it swaps the S&P for a growthier QQQ-heavy mix).

| 60/40 build | Sharpe | CAGR | maxDD | Calmar |
|---|---:|---:|---:|---:|
| as-used (`^GSPC` price-only leg, studies #2–4) | 0.82 | 9.1% | −31% | 0.29 |
| **+ dividends added back (same 4-asset basket)** | **0.85** | **9.4%** | −31% | 0.31 |
| composition variant (drop S&P, all-TR ETFs) | 0.84 | 9.5% | −30% | 0.31 |

**Honest read:** the **true dividend effect is small — +0.03 Sharpe / +0.3%/yr**. The all-TR ETF basket looks richer (CAGR 9.5%) but the extra is **composition** (a growthier mix), not dividends. Either way, studies #2–4 understated the 60/40 baseline only mildly, so the active engine's deficit ([[F35]]/[[F37]]) is real, not a price-only artifact.

### #2 — Rebalancing realism (2002–2026, equity = mean QQQ,IWM,DIA, 5bps/unit turnover)

| schedule | turn/yr | CAGR | Sharpe | maxDD | Calmar |
|---|---:|---:|---:|---:|---:|
| daily | 0.60x | 9.51% | 0.844 | −30.4% | 0.313 |
| monthly | 0.13x | 9.39% | 0.848 | −30.9% | 0.304 |
| quarterly | 0.08x | 9.47% | 0.861 | −30.7% | 0.308 |
| annual | 0.04x | 9.35% | 0.865 | −29.4% | 0.318 |
| 5% band | 0.05x | 9.41% | 0.839 | −30.8% | 0.305 |
| no-rebal (drift) — **NOT 60/40** | 0.00x | 10.54% | 0.796 | −32.7% | 0.323 |

Across every honest schedule, Sharpe spans **0.839–0.865** (range <0.03) at turnover falling from 0.60x/yr (daily) to 0.04–0.13x/yr (annual/monthly/band). The **magnitude** finding — *schedule barely moves Sharpe* — is robust.

Two disclosures the narrative needs:
- **The schedule Sharpe RANK (annual > quarterly > monthly > daily) is a drift effect, not a cost effect.** Re-running every schedule with cost=0 gives essentially the same ordering (0.865/0.862/0.849/0.846 vs the 5bps 0.865/0.861/0.848/0.844) — 5bps moves Sharpe by ≤0.002. Less-frequent rebalancing lets the equity weight drift *up* within each period, which is mildly Sharpe-accretive in this **monotonic 2002–2026 equity bull**. The SIGN of the ranking is regime-specific and would likely flip in a sample ending mid-drawdown, so this is **not** a "rebalance less often" recommendation.
- **The `no-rebal (drift)` row is not a like-for-like 60/40.** It never rebalances (band=99, cost=0) and the equity weight ratchets from 0.60 to **0.91**; its higher CAGR (10.5%) and deeper maxDD (−32.7%) are a rising **equity tilt**, not free alpha.

### #3 — Third sleeve (2014–2026, equity = mean SPY,QQQ,IWM,DIA; +10% sleeve carved 50/50; paired block bootstrap vs the 60/40 core, core Sharpe 0.866)

| +10% sleeve | corr to core | ΔSharpe CI | ΔCalmar CI | ΔmaxDD CI | P(DD shallower) | one-sided P(ΔSharpe≤0) |
|---|---:|---|---|---|---:|---:|
| **GLD** | +0.14 | [−0.003, +0.154] | [−0.02, +0.19] | [−0.4, +4.5] | **94%** | **0.031** |
| TLT | +0.04 | [−0.067, +0.077] | [−0.11, +0.08] | [−1.2, +3.8] | 83% | 0.449 |
| HYG | +0.79 | [−0.037, +0.013] | [−0.06, +0.02] | [−1.0, +1.1] | 60% | 0.835 |

Only **GLD** (lowest correlation, +0.14) shows a directional signal: it shallows the drawdown in 94% of resamples and its ΔSharpe two-sided CI lower bound sits *just below* 0 (−0.003). TLT (ΔSharpe dead-centered on 0) and HYG (corr +0.79, too equity-like; point ΔSharpe negative) do not help. The in-sample sweep shows a +20% GLD blend reaching Sharpe ~1.00 / Calmar 0.50 (vs core 0.87/0.42).

**The multiple-comparisons discount (required disclosure).** GLD is the **winner of three** tested sleeves. Its one-sided P(Δ≤0) = 0.031 clears an *unadjusted* 5% one-sided test but **FAILS** the 3-test Bonferroni threshold (one-sided p ≤ 0.0167). Two-sided, the CI lower bound (−0.003) already fails 0. So gold is **in-sample best-of-3, OOS-unconfirmed, and not family-wise significant**. The 94% P(shallower-DD) is a *descriptive directional tilt*, not a significant Sharpe edge. The sleeve test also runs only on 2014–2026, a strong **gold-bull** sub-window (GLD ~10%/yr), so gold's apparent benefit is exactly the kind of regime-dependent diversification that demands OOS / pre-2014 (GLD launched 2004) confirmation.

> 📝 **CORRECTION (2026-07-25 — `RESEARCH_WEB.md` F146).** The Finding and Verdict below
> originally reported the headline as **0.84 Sharpe / 9.5% CAGR "(dividend-correct)"** and the
> dividend effect as **+0.02 Sharpe**. Those are the **composition-variant** row's numbers, not
> the dividend-corrected ones — the exact conflation the "Honest read" under the Results table
> warns about 30 lines above ("the all-TR ETF basket looks richer (CAGR 9.5%) but the extra is
> *composition*, not dividends"). The table at Results is authoritative: dividend-corrected is
> **0.85 / 9.4%**, and the dividend effect is **+0.03 Sharpe**, which is what web node `F38`
> records. Corrected in place; the composition row's own 0.84 / 9.5% figures are unchanged and
> still correct where they are genuinely about composition.
>
> This error propagated: `D6_forward_expectation_study.md:10` quotes F38 but carries the wrong
> 9.5%. The general lesson is in F146 — figures move by **citation**, not by recomputation.

## The Finding

**The honest static 60/40 is ~Sharpe 0.85 / CAGR ~9.4%/yr (dividend-correct), it is robust to the rebalance schedule, and no single third sleeve reliably improves it — gold is the only borderline candidate and it fails a family-wise correction.** Specifically:
1. **Ceiling (honest, but composition-specific):** dividends lift the 60/40 by **~+0.03 Sharpe / ~+0.3%/yr** (the +0.5%/yr in the tool overstates dividends by ~0.2%/yr of composition). Studies #2–4 were mildly conservative against the active engine, so the active deficit ([[F35]]/[[F37]]) is real, not a price-only artifact. Neither the 9.4% nor the 9.5% CAGR is a **generic 60/40 number** — both rest on a QQQ-inclusive growth-tilted equity leg (a large-cap-only 60/40 is ~1.5%/yr / ~0.04 Sharpe lower, measured against the composition row: 8.06% / 0.804 vs 9.5% / 0.844) and a 2002–2026 **secular bond bull** (IEF 3.6%/yr standalone); it is a backward-looking realized ceiling, not a forward expectation.
2. **Rebalance-robust:** Sharpe spans <0.03 from daily to annual at a fraction of the turnover; a monthly or 5%-band rebalance is the honest, low-cost implementation. (The schedule rank order is a bull-market drift effect, not a recommendation to rebalance less.)
3. **Gold-borderline-only:** of GLD/TLT/HYG, only a low-correlation gold sleeve shows even a directional diversification signal (94% shallower DD); it is **borderline, best-of-3, and fails Bonferroni** — worth OOS confirmation, not adoption. Long-bond and credit do not help.

## Verdict

**The recommended product is a static 60/40, honestly ~Sharpe 0.85 / CAGR ~9.4%/yr; it is about as good as a *simple* static build reliably gets, and the only lever showing even a borderline in-sample lift is a small gold sleeve, pending OOS confirmation.** Dividends raise the honest ceiling only marginally (~+0.03 Sharpe), confirming the active engine's deficit was never a price-only mirage. The product is insensitive to the rebalance rule (monthly/band ≈ daily). Of three diversifying sleeves, only gold is borderline and it does not clear a multiple-comparisons-adjusted bar in-sample. This is the constructive close to the [[D6]]/[[F25]] arc on the *product* side: the bond-alternative is a pure static 60/40, and there is **no simple, reliable single-lever improvement** to it in-sample — a small gold sleeve is the single hypothesis worth testing out-of-sample.

## Surviving Caveats

- **Dividend vs composition (#1) — fixed in-tool.** The tool now isolates the true dividend effect (keep the 4-asset basket, add ~1.9%/yr back to the `^GSPC` leg): **+0.03 Sharpe / +0.3%/yr**. The all-TR ETF basket (CAGR 9.5%) is reported separately as a *composition* variant — its extra return is a growthier mix, not dividends. The dividend correction is genuinely small either way.
- **Gold is best-of-3 and not family-wise significant.** One-sided P=0.031 clears unadjusted 5% but fails Bonferroni 0.0167; two-sided CI lower bound −0.003 fails 0. The 94% shallower-DD is descriptive, not a significant Sharpe lift. Sleeve window is a 2014–2026 gold bull. OOS / pre-2014 confirmation required.
- **9.5% CAGR is composition-specific.** Equity leg is QQQ-inclusive/growth-tilted; large-cap-only 60/40 is ~1.5%/yr / ~0.04 Sharpe lower (8.06% / 0.804).
- **Bond bull market.** 2002–2026 spans a secular bond bull (IEF 3.60%/yr / Sharpe 0.554 standalone). The 40% bond leg's return and equity-diversification may not repeat from 2026's higher-yield/duration regime. A backward-looking realized ceiling, not a forward expectation.
- **Schedule rank is a drift, not cost, effect.** annual>quarterly>monthly>daily is identical at cost=0; specific to the monotonic equity bull; sign not stable. Only the magnitude (<0.03 Sharpe spread) is robust. Re-running the panel on a window ending mid-drawdown (2002→2009 or 2002→2020-03) would confirm the drift advantage flips — left as future work.
- **Cost convention.** Charged on one-way single-leg turnover (~2x lower than both-legs round-trip); immaterial at 0.04–0.6x/yr (worst-case ~0.04%/yr), makes after-cost numbers a mild best-case.
- **'no-rebal (drift)' is not a 60/40.** Equity weight drifts 0.60→0.91; its higher return is an equity tilt, not constant-risk alpha.
- **Near-optimality is narrow.** Only 3 single sleeves at one carve rule were tested — no cross-sleeve weight optimization, no equity-mix variation; the in-sample +20% GLD blend reaches Sharpe ~1.00. "About as good as it gets" means *as a simple static build*, not global optimality.
- **SIMPLE-return convention.** Exact for a constant-weight daily-rebalanced portfolio (verified to 3.1e-16); makes absolute Sharpes differ ~0.01 from the log-convention studies (E25–E28).

## Reproduce

```
venv/bin/python tools/static_product_study.py                 # #1 ceiling + #2 rebalance + #3 sleeve + verdict
venv/bin/python tools/static_product_study.py --json out.json # full result dict
venv/bin/python tools/ctx.py web D6                            # project context: the go/no-go this product closes
```
