# Study #4 — Does a Small Active OVERLAY Improve a Static 60/40 Core (the Constructive Capstone)?

**Artifact:** [`tools/overlay_build_study.py`](../../tools/overlay_build_study.py) · **Reproduce:** `venv/bin/python tools/overlay_build_study.py`
(deterministic, seed=0, ~2 min; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E28 (the study) · F37 (the finding) · **builds on** study #3 ([E27/F36](D6_crisis_overlay_study.md)), study #2 ([E26/F35](D6_active_vs_6040_study.md)), study #1 ([E25/F34](D6_power_equivalence_study.md))
**Status:** verdict **HOLDS** (scope-narrowed) — adversarially verified by a 3-lens skeptic panel (blend construction & paired-bootstrap correctness; interpretation/selection-bias/honesty; blind-spots/missing-builds). `blocking=false`, `verdict_holds=true`. Every reported number reproduces **byte-identically** (re-run JSON is deterministic). One MAJOR framing issue (the first-draft headline over-generalized from constant-weight to *all* builds) is resolved by **adding the regime-conditional build as a first-class, reproducible test in the tool** (`regime_blend()`) — it too lifts in-sample Sharpe but fails the bootstrap, so the capstone can honestly say *no build tested* clears the bar; three minor honesty/disclosure softenings are recorded in Surviving Caveats. None invalidate the conclusion.

## The Question (the constructive flip)

Studies #1–3 were all **evaluative** and the active engine lost: no risk-adjusted edge vs static 50/50 ([[E25]]/[[F34]]), no edge vs the decision-relevant 60/40 ([[E26]]/[[F35]]), and its low-drawdown advantage is real but **crisis-concentrated, small-N, and Sharpe-neutral** ([[E27]]/[[F36]]). Study #3 showed the active engine *protects in deep crises but drags in calm markets* — so a **blend** is exactly where those two forces net out. This study flips the question from *"does active beat static?"* to the constructive **"does a 60/40 CORE + a small active OVERLAY beat the pure 60/40 core?"** — the honest test of the engine's residual *usefulness*, not another head-to-head.

`blend(w) = (1−w)·core + w·active`, daily-rebalanced to constant weights, where:
- **core** = static 60/40 = `0.6·(equal-weight equity log-return blend) + 0.4·IEF` — byte-identical to the [[E26]]/[[F35]] baseline and the `mr_daily_lab gonogo` static-60/40 row.
- **active** = the same canonical dip+5d sleeve blend used in studies #2/#3 (buy a down-day close only if price > 200d-MA, long-only, non-overlapping 5-day holds, 5bps round-trip cost), equal-weighted across the equity basket.

## Methodology (leak-free; reuses E25-verified primitives)

**Reuse, not reimplementation.** Every statistic comes from the 5-lens-verified [`tools/power_study.py`](../../tools/power_study.py) (`ps.sharpe`, `ps.ann_pct`, `ps.maxdd_pct`) and the canonical `mr_daily_lab.sleeve`. `calmar = ps.ann_pct / |ps.maxdd_pct|`.

- **Blend** = a single fixed `w` applied every bar (daily rebalance to constant weights), swept over `WGRID = [0, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100]%`.
- **Paired block bootstrap** (`block=20`, `B=5000`, `seed=0`) of `blend − core` for ΔSharpe, ΔCalmar, ΔmaxDD. A **single block-start array drives BOTH legs each iteration**, preserving cross-correlation — the pairing is real and load-bearing (paired ΔSharpe CI width ≈ 0.15 vs ≈ 1.6 unpaired, a 10.5× tightening). Reported at:
  - **(a) a PRE-SPECIFIED w = 20%** (`W_FIXED`, chosen before the sweep — selection-bias-free), and
  - **(b) the in-sample Calmar-optimal w** (found by `argmax` over the full grid, explicitly **disclosed as optimistic / selection-biased**; the code prints "read the bootstrap CIs, not the argmax").
- **Windows restricted to where IEF is real** so the bond leg is never silently cash: Window A 2014–2026 (total-return basket), Window B 2002–2026 sliced to IEF inception (2002-07-31, which drops 0 rows vs the natural inner-join start).

**Cross-check (independent, exact).** `venv/bin/python tools/mr_daily_lab.py gonogo` reports static-60/40 Sharpe **0.84** / ann 7.8% / maxDD −21.0% / Calmar 0.37 and active-D5 Sharpe 0.68 / ann 6.1% / maxDD −13.9% — matching Window A's core (w=0%) and active (w=100%) **byte-for-byte** (max |daily diff| = 0.0 for both legs). The claimed "core 0.84 == gonogo" holds exactly.

## Results

### Window A — 2014–2026 (12.5yr, 3133d; QQQ+SPY+IWM+DIA+GLD + IEF)
core 60/40 Sharpe **0.844** / ann 7.85% / maxDD −21.0% / Calmar 0.373; active Sharpe 0.676 / ann 6.09% / maxDD −13.9% / Calmar 0.437 (corr to core **+0.67**).

| w_active | Sharpe | ann% | maxDD% | Calmar |
|---:|---:|---:|---:|---:|
| 0% (core) | 0.844 | 7.85 | −21.0 | 0.373 |
| 5% | 0.849 | 7.76 | −20.4 | 0.379 |
| 10% | 0.853 | 7.67 | −19.8 | 0.387 |
| 15% | 0.855 | 7.58 | −19.2 | 0.394 |
| **20%** | **0.857** ←Sharpe* | 7.49 | −18.6 | 0.402 |
| 25% | 0.857 | 7.41 | −18.0 | 0.411 |
| 30% | 0.855 | 7.32 | −17.4 | 0.421 |
| 40% | 0.847 | 7.14 | −16.1 | 0.443 |
| 50% | 0.833 | 6.97 | −14.9 | 0.469 |
| **75%** | 0.769 | 6.53 | −13.8 | **0.474** ←Calmar* |
| 100% | 0.676 | 6.09 | −13.9 | 0.437 |

In-sample optima: Sharpe at w=20% (true argmax — full-precision 0.856760 at 20% vs 0.856668 at 25%, not a tie-break artifact), Calmar at w=75%.
**Boot @ pre-specified 20%:** ΔSharpe **+0.01** [−0.06, +0.09] ns · ΔCalmar **+0.03** [−0.08, +0.12] ns · ΔmaxDD **+2.4pp** [−0.91, +3.46] ns.
**Boot @ in-sample 75%:** ΔSharpe −0.08 [−0.38, +0.24] ns · ΔCalmar +0.10 [−0.39, +0.30] ns · ΔmaxDD +7.3pp [−5.14, +9.79] ns.

### Window B — 2002–2026 (23.9yr, 6010d; ^GSPC+QQQ+IWM+DIA + IEF, sliced to IEF inception)
core Sharpe **0.698** / ann 7.91% / maxDD −33.3% / Calmar 0.237; active Sharpe 0.435 / ann 4.63% / maxDD −19.9% / Calmar 0.233 (corr **+0.63**).

| w_active | Sharpe | ann% | maxDD% | Calmar |
|---:|---:|---:|---:|---:|
| **0% (core)** | **0.698** ←Sharpe* | 7.91 | −33.3 | 0.237 |
| 20% | 0.688 | 7.25 | −29.3 | 0.247 |
| 50% | 0.632 | 6.27 | −22.9 | 0.274 |
| **75%** | 0.544 | 5.45 | −17.2 | **0.317** ←Calmar* |
| 100% | 0.435 | 4.63 | −19.9 | 0.233 |

In-sample optima: Sharpe at w=**0%**, Calmar at w=75%.
**Boot @ pre-specified 20%:** ΔSharpe **−0.01** [−0.07, +0.05] ns · ΔCalmar **+0.01** [−0.07, +0.06] ns · ΔmaxDD **+4.0pp** [−1.59, +5.20] ns.
**Boot @ in-sample 75%:** ΔSharpe −0.15 [−0.40, +0.09] ns · ΔCalmar +0.08 [−0.32, +0.13] ns · ΔmaxDD **+16.1pp** [−9.83, +14.22] (point lies OUTSIDE the CI — a single-GFC-path artifact, see Drawdown Panel).

**Shape of the trade-off.** maxDD and Calmar improve with w up to ~75%, then **reverse at 100%** (the 75% blend is better-diversified than pure active — hence the *interior* Calmar optimum, found by argmax, not by assuming monotonicity). Total return falls **monotonically** with w across the full grid in both windows.

## The Finding

**No constant-weight overlay raises the 60/40 core's risk-adjusted return.** The Sharpe-optimal active weight is **~0%** — w=20% in Window A (economically flat, +0.013) and **0% in Window B**. At the pre-specified 20% overlay, ΔSharpe is +0.01 / −0.01 with CIs straddling 0 in both windows. There is no free lunch on Sharpe; the modest 12.5yr tick-up (0.844→0.857) sits near the center of its own bootstrap CI [−0.06, +0.09].

The overlay's only candidate benefit is **drawdown smoothing**: maxDD shallows monotonically with w (and Calmar rises to an interior 75% optimum), bought with monotonically **lower total return** (active ann 6.1%/4.6% << core 7.9%/7.9%). But — exactly as in studies #1–3 — that smoothing is **not statistically reliable**: ΔCalmar and ΔmaxDD CIs straddle 0 at the pre-specified 20% in both windows.

## Drawdown Panel (the path-dependence, made vivid)

The point-level maxDD improvement **overstates** the typical (resampled) effect by ~2×:
- **Window A, w=20%:** full-sample point ΔmaxDD **+2.4pp** but bootstrap **median only ~+1.2pp**, with ~**13% of resamples showing the overlay making drawdown WORSE**. The benefit is driven by a single path — the core's worst drawdown is the lone 2022-10-14 −21% trough.
- **Window B, w=75%:** the full-sample point ΔmaxDD **+16.1pp lies entirely OUTSIDE its bootstrap 95% CI [−9.83, +14.22]** (median +2.0pp). This is not a bug — it is the single most vivid corroboration of the path-dependence thesis: that +16pp is one GFC drawdown path, ~8× the typical resampled benefit. Point-level monotone DD gains are **not generalizable**.

The honest read: the overlay *cuts drawdown in-sample but not reliably*; the cut is one-crisis-path-driven, consistent with [[F36]]'s crisis-concentrated, small-N drawdown property.

## Regime-Conditional Overlay (now tested in-tool, not just a follow-up)

The constant-weight overlay is structurally incapable of *timing* — it holds the same active weight in calm markets (where active drags) as in crises (where it protects). The natural smarter build, motivated directly by [[F36]]'s depth result, is a **regime-conditional overlay: switch 100% to active ONLY while the core is in a deep drawdown**, gated on *yesterday's* core drawdown (lag-1, leak-free). This is now a first-class, reproducible part of the tool (`regime_blend()`), tested at pre-specified thresholds in both windows:

| trigger (deploy 100% active while core ≤ −thr) | deployed | Sharpe (vs core) | maxDD (vs core) | paired-bootstrap ΔSharpe |
|---|---:|---:|---:|---|
| Window A, −10% | 11% of days | 0.886 (0.844) | −17% (−21%) | **+0.04 [−0.19, +0.30] ns** |
| Window A, −15% | 3% of days | 0.773 (0.844) | −21% (−21%) | −0.07 [−0.22, +0.10] ns |
| Window B, −10% | 12% of days | 0.749 (0.698) | −23% (−33%) | **+0.05 [−0.17, +0.28] ns** |
| Window B, −15% | 7% of days | 0.709 (0.698) | −25% (−33%) | +0.01 [−0.18, +0.22] ns |

The conditional overlay **does lift in-sample point Sharpe and cut maxDD** (e.g. Window B −10%: Sharpe 0.70→0.75, maxDD −33%→−23%) — so a *timing* build can raise risk-adjusted return at the point level, unlike the flat-weight form. But because the deep-drawdown trigger fires on only **11–12% of days** (a handful of deep-crisis episodes), the paired-bootstrap ΔSharpe CIs are wide and **straddle 0 in every case** — the same [[F36]] small-N deep-crisis wall. An even more aggressive in-sample search (skeptic-run: thr=3% / deploy-75%) lifts Window-A Sharpe to ~0.97 (≈10× the constant-weight ceiling) and Calmar to 0.55, but its bootstrap ΔSharpe **[−0.12, +0.37]** still straddles 0 — so even the cherry-picked best does not demonstrate a reliable edge.

**Conclusion:** no build tested — constant-weight *or* regime-conditional — clears the bootstrap. The substantive verdict is unchanged and now stronger: the active engine cannot be assembled into a *reliable* improver of the static 60/40, whether by flat weight or by deep-drawdown timing. (Vol-targeted and alternative-sleeve overlays remain formally untested.)

## Verdict

**No constant-weight linear overlay of this active sleeve reliably improves the static 60/40 core; the pure static 60/40 stands.** On Sharpe the optimal active weight is ~0% (20% Window A / 0% Window B, both economically flat) — the overlay **cannot raise risk-adjusted return**. A ~20% overlay lowers maxDD at the point level, but the ΔCalmar/ΔmaxDD improvement is **not statistically reliable** (every CI straddles 0 in both windows) and is bought with strictly lower total return. The residual is a **path-dependent, crisis-concentrated drawdown effect** — consistent with [[F36]] and [[F25]] — not a Sharpe edge.

An active overlay is therefore a **discretionary path-smoothing preference, not a reliable upgrade**. **No build tested — constant-weight or regime-conditional — clears the bootstrap**, so this closes the active-vs-static arc ([[D6]]/[[F25]], [[F34]]/[[F35]]/[[F36]]): the active engine is a capital-preservation overlay, never a demonstrable risk-adjusted edge. The pure static 60/40 stays the recommended bond-alternative. (Vol-targeted and alternative-sleeve overlays remain formally untested.)

## Surviving Caveats

- **Two build families tested; others not.** Both the constant-weight overlay and the regime-conditional (deploy-in-deep-drawdown) overlay are tested in-tool and both fail the bootstrap. Vol-targeted sizing and alternative sleeves (different entry signal / hold horizon) remain formally untested — they are the only routes by which a future build could, in principle, beat the static 60/40, though all three prior studies make that unlikely.
- **Drawdown benefit is one-path-driven.** Point ΔmaxDD ≈ 2× its bootstrap median at w=20% (~13% of resamples show no improvement); the w=75% Window-B point lies outside its own CI. Report the median, not the point, as the typical effect.
- **Log-return blend convention.** The legs are mixed in log space (inherited from the canonical sleeve), which understates absolute Sharpe by ~0.005–0.04 but **cancels in the paired blend−core deltas** (verified: w=20% log ΔSharpe +0.012 vs simple-return +0.017; w=75% ΔCalmar +0.101 vs +0.108). Conservative against the overlay; no conclusion flips.
- **Monotonicity is interior-only.** maxDD/Calmar improve up to ~75% then reverse at 100%; the code uses argmax over the full grid, so it does not rely on monotonicity.
- **^GSPC price-only (Window B).** 1 of 4 equity legs omits ~1.8%/yr dividends; this is inherited from [[E25]]/`power_study.load_2000` and was **not disclosed in this study's own docstring/JSON** (a disclosure-hygiene gap). Direction is **conservative against active** (the true 60/40 is even better, and active is full-weight ~79% of the time), so it strengthens the verdict.
- **Frictionless between-leg rebalancing.** Only the 5bps intra-sleeve cost is modeled; the overlay's core↔active rebalancing turnover is free. Charging it drops blend Sharpe below core (5bps → 0.847, 10bps → 0.836) — conservative-correct for a negative verdict.
- **Calmar denominator is one trough date.** Calmar rests on the single full-sample maxDD (2022-10-14 core), making it the noisiest of the three metrics; a robust drawdown statistic (Ulcer index, or the bootstrap P(blend shallower than core), which the paired resamples already contain) would corroborate the path-smoothing claim more durably and is left as future work.
- **Underpowered for small edges / non-independent windows.** Consistent with [[E25]]/[[E26]]: the ΔSharpe CI half-widths (~0.06–0.09 Window A) dwarf any realistic overlay benefit, and Window A is a ~52% calendar subset of Window B.

## Reproduce

```
venv/bin/python tools/overlay_build_study.py                 # both windows + sweep + verdict
venv/bin/python tools/overlay_build_study.py --json out.json # full result dict
venv/bin/python tools/mr_daily_lab.py gonogo                 # cross-check: static-60/40 Sharpe 0.84 == core (w=0%)
```