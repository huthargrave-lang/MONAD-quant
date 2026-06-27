# Study #7 — Do the Structural Levers (Vol-Targeting / Risk Parity) Reliably Beat the Fixed 60/40?

**Artifact:** [`tools/vol_target_study.py`](../../tools/vol_target_study.py) · **Reproduce:** `venv/bin/python tools/vol_target_study.py`
(deterministic, seed=0; no network fetch — reuses the cached 2000/2014 price universes; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E31 (the study) · F40 (the finding) · **builds on** the go/no-go ([[D6]]), the 26yr confirmation ([[F25]]), and the recommended-product close ([[F37]]); continues the static-product arc opened by study #5 ([[F38]]) and resolved-for-gold by study #6 ([[F39]]).
**Status:** verdict **HOLDS** (with two localized bullet corrections). Every reported number reproduces **byte-identically** (deterministic JSON equal across reruns). `blocking=false`, `verdict_holds=true`. No issue invalidates a finding. A 2-lens skeptic panel (construction/leak-freeness/reproduction; interpretation & honesty) confirmed the construct is leak-free and the headline honest, but flagged **two honesty errors in the verdict bullets** — both **writeup-only** and both **corrected below**: (1) the claim that vol-targeting's Sharpe lift is "largely the LEVERAGE" is mechanically wrong (leverage is Sharpe-invariant; the study's own numbers prove the lift is pure *timing*), and (2) the claim that risk parity "would have suffered in 2022" is contradicted by the data (in calendar 2022 risk parity lost **less** capital than the fixed 60/40). The substance is unchanged: **neither vol-targeting nor risk parity is a free or reliable upgrade; the fixed 60/40 stands.**

## The Question

Studies #4–6 closed the active-engine and third-sleeve questions: no active overlay ([[F37]]) and no added sleeve ([[F38]]/[[F39]]) reliably improves the recommended static 60/40. Two classic **structural** levers remained untested — they change *how the two existing legs are weighted/scaled* rather than adding a signal or a sleeve:

1. **Volatility targeting** — scale total exposure up/down to hold a constant risk budget, de-risking into vol spikes via a **lagged** realized-vol estimate. This bundles two distinct effects: a **timing** effect (when you are more/less invested) and a **leverage** effect (the average exposure level).
2. **Risk parity** — weight equity and bond to **equal risk contribution** (inverse-vol), rather than 60/40 by capital.

Both are real, theory-backed effects. This study asks the honest question: does *either* earn its keep over the fixed rule — **after isolating leverage from timing and disclosing regime dependence**?

The load-bearing construct is the **timing/leverage isolation**: the vol-timed series is rescaled by a single **constant** so its full-sample volatility equals the fixed 60/40's. Multiplying a return series by a constant cannot change its Sharpe, so any residual ΔSharpe is **pure vol-timing**, with the leverage/level effect removed.

## Methodology (read-only; reuses study #5's thrice-verified primitives; deterministic, seed=0)

- **Universe & legs:** the same cached price universes as studies #5/#6 (no new fetch). Long window: equity = equal-weight daily-rebalanced QQQ/IWM/DIA, bond = IEF, from 2002-07-31 (6010 days). Robustness window: equity = SPY/QQQ/IWM/DIA, bond = IEF, from 2014-01-03 (3133 days). **Convention:** SIMPLE-return product accounting throughout (constant-weight daily-rebalanced = weight-average of component simple returns) — so absolute Sharpes differ ~0.01 from the log-convention studies E25–E28; relative comparisons are internally consistent.
- **Reused primitives (from [`tools/static_product_study.py`](../../tools/static_product_study.py), study #5):** `pmetrics`, `simple_ret`, `equity_blend`, and the paired block bootstrap (`BLOCK=20`, `B=5000`, `SEED=0`) — a single block-start array drives **both** the variant and the fixed baseline each iteration (real pairing, cross-correlation preserved), percentile CI on the difference.
- **Lagged realized vol (leak-free):** `realized_vol(r) = r.rolling(60).std().shift(1) * sqrt(252)` — the `.shift(1)` makes the vol estimate at bar *t* depend only on returns through *t−1*, known at the start of *t*. **Independently re-checked by the panel:** perturbing `fixed[i]` leaves `rv[i]` bit-identical and only changes `rv[i+1…]`, so leverage/weights at bar *t* use strictly past vol — no look-ahead.
- **Vol-targeting:** `lev = (target / rv).clip(upper=2.0)`; `out = lev · port`. Optional financing charged **only on the borrowed slice**: `(lev−1).clip(lower=0) · financing / 252` (zero charge wherever `lev ≤ 1`; reproduced to atol 1e-15).
- **Timing/leverage isolation (`vol_normalize`):** a single **constant** scalar (1.1005, confirmed `ratio.max − ratio.min == 0` to 1e-12) that sets the vol-timed series' full-sample vol to 11.56% == the fixed 60/40's. A pure level rescale, Sharpe-invariant — so the in-sample scaling cannot bias the timing comparison (it changes only the *level*, never the day-to-day timing).
- **Risk parity:** `w_eq = (1/ve) / (1/ve + 1/vb)` with `ve, vb` from the same lagged `realized_vol` — leak-free (same-bar shock to equity leaves `w_eq[i]` unchanged).

**Reproduction (panel-verified):** rerunning the tool produces a JSON **byte-identical** to the stored `vol_target.json` (full diff empty). All headline numbers reproduce exactly in both windows.

## Results

### Long window — 2002-07-31 → 2026-06-18 (6010 days; fixed 60/40 vol 11.6%)

Baseline **fixed 60/40: Sharpe 0.84 · CAGR 9.5% · vol 11.6% · maxDD −30% · Calmar 0.31.**

| variant | leverage / weight | Sharpe | CAGR | vol | maxDD | Calmar | ΔSharpe vs fixed | ΔmaxDD vs fixed | P(DD shallower) |
|---|---|---:|---:|---:|---:|---:|---|---|---:|
| **vol-timing only** (vol-matched → pure timing) | avg lev ≈ 1.0x | 0.90 | 10.2% | 11.6% | −21% | 0.48 | **[−0.12, +0.22]** straddles 0 | [−8.0, +9.7] straddles 0 | 58% |
| **vol-target @ 10%** (lev ≤ 2) | avg lev 1.13x | 0.90 | 9.3% | 10.5% | −20% | 0.47 | **[−0.12, +0.22]** straddles 0 | [−5.5, +11.7] straddles 0 | 75% |
| **vol-target @ 10% + 2%/yr financing** | avg lev 1.13x | 0.86 | 8.8% | 10.5% | −20% | 0.45 | **[−0.17, +0.18]** straddles 0 | [−6.2, +11.0] straddles 0 | 72% |
| **risk parity** (inverse-vol) | ~28% eq / 72% bond | 1.04 | 6.2% | 6.0% | −20% | 0.31 | **[−0.12, +0.45]** straddles 0 | **[+2.9, +24.0] ABOVE 0** | 100% |

### Robustness window — 2014-01-03 → 2026-06-18 (3133 days; fixed 60/40 vol 10.9%)

Baseline **fixed 60/40: Sharpe 0.87 · CAGR 9.2% · maxDD −22% · Calmar 0.41.**

| variant | leverage / weight | Sharpe | ΔSharpe vs fixed | ΔmaxDD vs fixed | P(DD shallower) |
|---|---|---:|---|---|---:|
| **vol-timing only** (vol-matched) | avg lev ≈ 1.0x | 0.84 | [−0.27, +0.21] straddles 0 | [−9.0, +6.5] straddles 0 | 44% |
| **vol-target @ 10%** | avg lev 1.20x | 0.84 | [−0.27, +0.21] straddles 0 | [−8.3, +7.0] straddles 0 | 49% |
| **vol-target @ 10% + 2%/yr financing** | avg lev 1.20x | 0.79 | [−0.33, +0.15] straddles 0 | [−9.2, +6.5] straddles 0 | 44% |
| **risk parity** (inverse-vol) | ~28% eq / 72% bond | **0.79 < fixed 0.87** | [−0.45, +0.29] straddles 0 | [−0.9, +19.6] straddles 0 | 96% |

### The four things that matter

1. **Vol-timing isolated is a directional tilt, NOT a reliable edge.** With leverage stripped out (the timed series rescaled to the fixed 60/40's exact full-sample vol), the residual is pure timing — and **both** its ΔSharpe [−0.12, +0.22] **and** its ΔmaxDD [−8.0, +9.7] straddle 0. The point maxDD improves (−30% → −21%) and the drawdown is shallower in 58% of resamples, but 58% is a near-coin-flip sign-consistency, not a CI excluding 0. The path-smoothing direction is plausible; its size is not established.

2. **The @10% Sharpe lift is TIMING, not leverage — and leverage adds only return, not Sharpe.** This is the load-bearing empirical point, and the study's own isolation construct contains the proof: the vol-target@10% Sharpe (**0.903**) is **identical** to the zero-net-leverage vol-timing-only Sharpe (**0.903**), and both exceed fixed (0.845) by exactly **+0.058**. Since leverage scales mean and vol equally, it is **Sharpe-invariant** — it cannot be the source of any Sharpe lift; it adds only CAGR. So the +0.05 at @10% is the (statistically insignificant — CI straddles 0) **timing** effect, with leverage contributing only the return/vol *level* (indeed the @10% CAGR 9.3% is even slightly *below* fixed's 9.5%). *(This corrects the original verdict bullet #2, which mis-attributed the lift to leverage — see Verdict.)*

3. **What little edge the @10% form has is taxed away by financing.** Charging financing on the borrowed slice drags the levered **return** (and hence the reported Sharpe): CAGR 9.3% → 8.8% and Sharpe 0.90 → 0.86 at 2%/yr — already back to the fixed 0.845. A sensitivity sweep (panel-suggested) shows it goes outright **below** fixed at realistic 2026 financing: Sharpe **0.82** at 4%/yr (and ~**0.79** at 5%/yr) vs fixed 0.845. The @10% form buys no durable edge.

4. **Risk parity's 1.04 Sharpe is a bond-bull regime bet that REVERSES — and its only-clearing CI is a low-vol artifact.** Risk parity runs ~28% equity / 72% bond — far more bond-heavy than 60/40 — so its high long-window Sharpe is largely the **secular bond bull** (it over-weights the asset that won 2002–2021). Two facts expose this as a regime bet, not an edge:
   - Even in its **best** window its ΔSharpe straddles 0 ([−0.12, +0.45]) — it was never *significantly* better even where it looks best.
   - It **reverses** out-of-sample: in 2014–2026 its Sharpe (**0.79**) falls **below** the fixed 60/40's (**0.87**), ΔSharpe [−0.45, +0.29].

   Its **only** CI that clears 0 is ΔmaxDD [+2.9, +24.0] — but that is a **mechanical low-vol / bond-heavy artifact**, not a risk-adjusted win: risk parity runs at 6.0% vol vs the fixed 60/40's 11.6%, so of course it draws down less in absolute terms. Read alongside the ΔSharpe straddle, the shallower drawdown is bought with a far lower-risk, lower-return, bond-concentrated portfolio — exactly the trade a capital-weighted investor could make by simply holding *less equity*, with no parity machinery.

## The Finding

**Neither of the two remaining structural levers — vol-targeting or risk parity — is a free or reliable upgrade to the fixed 60/40.** Vol-timing, isolated from leverage by matched-vol rescaling, smooths the path *directionally* (point maxDD −30% → −21%) but its ΔSharpe **and** ΔmaxDD CIs both straddle 0 — not a reliable improvement. The vol-target@10% form's apparent Sharpe lift is the **same +0.05 timing effect** (its Sharpe is identical to the zero-net-leverage matched-vol case); leverage adds only CAGR, not Sharpe, and a 2%/yr financing cost erases the lift (going outright negative vs fixed at 4–5%/yr). Risk parity's 1.04 long-window Sharpe is a **secular bond-bull regime bet** (it over-weights bonds ~28/72): its ΔSharpe straddles 0 even in its best window, and it **reverses** to 0.79 < fixed 0.87 in 2014–2026; its only CI that clears 0 (ΔmaxDD) is a low-vol/bond-heavy artifact, not a risk-adjusted edge. **Like every lever in this program, the path-smoothing is a directional tilt, not a free or reliable upgrade. The fixed 60/40 stands.**

## Verdict

**The verdict HOLDS, with two localized bullet corrections (writeup-only — neither changes the bottom line).** The headline as written is careful and correct: it claims only that vol-targeting "smooths the path directionally but its ΔSharpe/ΔmaxDD CIs straddle 0," that the @10% lift "is mostly leverage and dies to financing cost," and that risk parity is "a regime bet that REVERSES." The skeptic panel confirmed the construct is leak-free, the bootstrap correctly reused and paired, and the reproduction byte-identical. It flagged two honesty errors **confined to the verdict bullets**, both corrected here:

- **(major, corrected) "any Sharpe lift is largely the LEVERAGE."** Mechanically wrong: leverage is Sharpe-invariant. The study's own numbers disprove it — vol-target@10% Sharpe (0.903) == zero-net-leverage vol-timing-only Sharpe (0.903), both +0.058 over fixed. The +0.05 is **pure timing** (insignificant, CI straddles 0); leverage adds only CAGR. The 2% financing "erodes" the Sharpe because it taxes the levered *return*, not because the lift was leverage. **Corrected reading:** *the @10% lift is the (insignificant) vol-timing effect — identical to the matched-vol case; leverage adds only return; financing then taxes that return away (Sharpe 0.90 → 0.85 → below fixed at 4–5%/yr), so the @10% form buys no durable edge.*
- **(minor, corrected) "it would have suffered in 2022."** Contradicted by the data: in calendar 2022 (the rising-yield stress year) risk parity returned **−16.1%** vs the fixed 60/40's **−17.7%** — it lost *less* capital (its 2022 Sharpe looks worse only because it is lower-vol). The honest regime evidence is the **secular level** of its 2002–2021 returns and the **documented 0.79 < 0.87 reversal** in 2014–2026 — not a 2022 crater. **Corrected reading:** *a bond-heavy bet that under-performs once the bond bull stops (2014–2026 Sharpe 0.79 < fixed 0.87) and is exposed to a rising-yield regime going forward* (the forward 2026 yield-regime worry is fair; the back-tested 2022 claim is dropped).

Neither correction touches a finding: the headline never relied on the leverage attribution or the 2022 claim, and both windows still show every risk-adjusted CI straddling 0 (except risk parity's mechanical ΔmaxDD). **The action is identical and unchanged from studies #4–6: the pure static 60/40 stands; vol-targeting and risk parity are directional path-tilts and (for risk parity) a bond-regime bet, not evidence-backed upgrades.**

**This continues and closes the structural-lever side of the [[D6]] arc.** Consistent with [[F25]] (more data narrows but does not rescue an edge), [[F37]] (no active overlay reliably improves the static 60/40), and [[F38]]/[[F39]] (no added sleeve does either): every lever this program has tested — active overlay, third sleeve, vol-targeting, risk parity — produces a directional path-smoothing tilt whose risk-adjusted CIs straddle 0, never a free or reliable edge. There is no remaining single structural lever that reliably beats the fixed 60/40.

## Surviving Caveats

- **Secular bond-bull regime (the dominant caveat).** Both windows ride a 2002–2026 bond bull (IEF ~3.6%/yr standalone — see [[F38]]). Risk parity's bond-heavy ~28/72 tilt is the most exposed: its 1.04 Sharpe is largely that tailwind and it already reverses to 0.79 < 0.87 in 2014–2026. A rising-yield forward regime would hurt the bond-heavy variants most. The fixed 60/40's own ~9.5% CAGR is also a backward-looking realized ceiling, not a forward expectation.
- **Financing is assumption-driven, and the 2% base is optimistic.** The @10% form only levers to ~1.13–1.20x, so the 2%/yr charge on the small `(lev−1)+` slice is tiny by construction. A realistic levered-ETF / futures-roll / margin spread in a higher-rate 2026 regime could be 3–5%/yr — at which the @10% Sharpe (0.81–0.79) drops outright below the fixed 0.845. The "not a free upgrade" conclusion strengthens, not weakens, under realistic financing.
- **Daily-rebalancing idealization.** Vol-targeting and risk parity are simulated as zero-transaction-cost daily-rebalanced return blends. Real vol-targeting trades into vol spikes (turnover spikes exactly when spreads widen) and risk parity rebalances inverse-vol weights daily; neither turnover cost nor intra-day financing-on-scaling is charged beyond the single 2%/yr average-leverage term. The honest cost is therefore *worse* than reported — again strengthening the conclusion.
- **Risk parity's ΔmaxDD-clears-0 is a low-vol artifact, not an edge.** Its [+2.9, +24.0] ΔmaxDD CI clears 0 only because it runs at 6.0% vol vs 11.6% (bond-heavy), while its ΔSharpe straddles 0 in both windows. The shallower drawdown is bought with lower risk/return, not earned per unit of risk.
- **Warm-up zero-bars — FIXED in the committed tool.** The panel flagged that `lev.fillna(0.0)` carried 60 leading forced-flat bars through the LB=60 warm-up; the final tool leaves the warm-up `lev` as NaN so `.dropna()` removes it cleanly. This is why the committed numbers are the warm-up-removed values (vol-timing Sharpe **0.903**, ΔSharpe ≈ [−0.13, +0.21]) rather than the panel's pre-fix 0.903 — immaterial to every verdict (still straddles 0). All figures above are from the committed (warm-up-fixed) tool; reproduce with `venv/bin/python tools/vol_target_study.py`.
- **Simple-return convention.** SIMPLE-return product accounting (correct for a constant-weight product) makes absolute Sharpes differ ~0.01 from the log-convention studies E25–E28; relative comparisons are internally consistent and exact.

## Reproduce

```
venv/bin/python tools/vol_target_study.py                  # both windows + verdict
venv/bin/python tools/vol_target_study.py --json out.json  # full result dict
venv/bin/python tools/ctx.py web D6                        # the go/no-go arc this continues
venv/bin/python tools/ctx.py web F37                       # study #4: no active overlay improves the 60/40
venv/bin/python tools/ctx.py web F38                       # study #5: no third sleeve improves it either
```
