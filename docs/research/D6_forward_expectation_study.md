# Study #8 — Forward 60/40 Expectation: Does the Recommended Product Meet the Income Goal Once the Tailwinds End?

**Artifact:** [`tools/forward_expectation_study.py`](../../tools/forward_expectation_study.py) · **Reproduce:** `venv/bin/python tools/forward_expectation_study.py`
(deterministic, seed=0; no network fetch — reuses `static_product_study` primitives and the cached 2000 price universe; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E32 (the study) · F41 (the finding) · **resolves** the foundational goal question ([[D4]]); **builds on** the go/no-go ([[D6]]), the 26yr confirmation ([[F25]]), the no-active-overlay close ([[F37]]), and the static-product close that flagged the bond-bull/QQQ-tilt caveat ([[F38]]).
**Status:** verdict **HOLDS**. Every reported number reproduces **byte-identically** (deterministic JSON equal across reruns; seed=0). `blocking=false`, `verdict_holds=true`. No issue invalidates a finding. A 2-lens skeptic panel (methodology/assumptions/MC validity; interpretation & honesty) confirmed the construct is sound and the split verdict honest, but flagged **two material disclosure gaps and three wording/framing corrections — all writeup-only** — folded into this artifact below: (1) the MC inherits a benign **-0.29** historical stock-bond correlation that has **already flipped positive** forward (2022-26 = **+0.12**), so the drawdown odds are if-anything **optimistic**; (2) the **forward Sharpe (~0.51)** — a ~40% drop from the 0.845 historical figure the study leads with — is never printed; (3) 'comfortably clearing' over-states a **67%** probability; (4) the goal is tested as total-return CAGR, not cash income; (5) the QQQ tilt inflates **vol** but **not** the headline maxDD. The substance is unchanged: **the forward 60/40 is a real bond-alternative on RETURN that clears 3.75% more-likely-than-not (~67%), but it FAILS the near-zero-drawdown aspiration, and the near-zero-DD goal is unattainable by any honest static OR active build in this program.**

## The Question

This is the closing study of the [[D6]] arc on the GOAL side. [[D6]]/[[F25]] established the active engine has no risk-adjusted edge over a static blend; [[F37]]/[[F38]] established no overlay or third sleeve reliably improves the recommended static 60/40. But [[F38]] flagged a load-bearing caveat: the 60/40's ~9.5% historical CAGR **rode a 2002-2026 secular bond bull (IEF 3.6%/yr standalone) plus a QQQ growth tilt** — "a backward-looking realized ceiling, not a forward expectation."

So the foundational question of [[D4]] re-opens at 2026 starting conditions: **what should you HONESTLY expect going forward, and does it meet the project's ~3.75% APY income goal (D4) and the 'near-zero drawdown' aspiration (CLAUDE.md §1)?**

**This is a forward SCENARIO study, not a backtest. Its inputs are explicit ASSUMPTIONS, not data.** That framing is the most important thing to carry into every number below: the conclusions are conditional on the scenario inputs being roughly right, and the study's honesty rests on those inputs being conservative and disclosed rather than measured.

## Methodology (read-only; reuses study #5's primitives; deterministic, seed=0)

- **Historical decomposition (the only empirical part):** the same cached price universe as studies #5-7 (no new fetch). Equity leg = equal-weight daily-rebalanced **QQQ/IWM/DIA**; bond leg = **IEF**; from 2002-07-31 (6010 days, span 2002-07-31→2026-06-18). SIMPLE-return product accounting (constant-weight daily-rebalanced = weight-average of component simple returns) via `sps.pmetrics`/`simple_ret`/`equity_blend`.
- **Forward inputs (ASSUMPTIONS, stated as assumptions):**
  - **BOND forward return ≈ the STARTING YIELD.** A held-to-horizon Treasury (or a bond fund held ~one duration) earns its entry YTM regardless of the rate path — duration loss and reinvestment gain offset. The 10yr is ~4.2% in 2026, and IEF (dur ~7.5) maps to it. The 2002-2026 bond bull (falling yields → price gains *on top of* coupon) is exactly the part that does NOT repeat — so using **4.2%** forward (vs the realized **3.6%**) is the honest, non-cherry-picked direction. Scenario range {3.5, 4.2, 5.0}%.
  - **EQUITY forward return ≈ a conservative 5-9% nominal**, deliberately BELOW the realized QQQ-tilted 12.5% equity-leg CAGR, reflecting high US CAPE compressing forward returns. Scenario range {5, 7, 9}%. This is a CAPE-compression assumption, not a fitted estimate.
- **Scenario matrix:** forward expected 60/40 = 0.6·equity + 0.4·bond across the full 3×3 grid (exposes the dispersion rather than hiding behind one point).
- **Monte-Carlo (mean re-centering):** `r_centered = r − r.mean() + ann_to_daily(forward_annual)` — swaps the arithmetic daily mean to the forward expectation while **preserving the historical vol, autocorrelation, fat tails, and drawdown shape** of the realized 60/40. Then block-bootstrap (BLOCK=20, 10yr = 2520 steps, 5000 paths, seed=0) yields the forward distribution of 10yr CAGR and worst drawdown, plus goal odds. This construct was independently verified by the panel: it exactly swaps the mean and the realized median CAGR sits ~0.6% below the target (= the 0.5·σ² variance drag, σ_60/40 ≈ 11.6%), so the distribution is internally consistent and conservative on the central tendency.

**Reproduction (panel-verified):** rerunning the tool reproduces every headline number deterministically; the stored `forward_exp.json` matches stdout exactly.

## Results

### Historical decomposition (2002-07-31 → 2026-06-18, dividend-correct)

| leg | CAGR | vol | Sharpe | maxDD | Calmar |
|---|---:|---:|---:|---:|---:|
| equity (QQQ+IWM+DIA) | 12.5% | 20.1% | 0.69 | −54% | 0.23 |
| bond (IEF) | 3.6% | 6.8% | 0.55 | −24% | 0.15 |
| **60/40** | **9.5%** | **11.6%** | **0.84** | **−30%** | **0.31** |

The 9.5% rode a secular bond bull + a QQQ growth tilt — the part that does NOT repeat ([[F38]]).

> 📝 **PROVENANCE NOTE (2026-07-25 — `RESEARCH_WEB.md` F146). Flagged, deliberately NOT
> corrected.** The `9.5% / 0.84` baseline above is the **composition variant** (all-TR ETF
> basket) from `D6_static_product_study.md:36`, not the dividend-corrected 60/40, which is
> `9.4% / 0.85` — the value `F38` actually records. This doc inherited the wrong row by
> quoting the study's Finding, which itself mislabelled it (now corrected there). Note that
> this document also uses **0.85** for the same static baseline at the Adversarial-review
> bullet below, so the two figures are already inconsistent *within this file*.
>
> Left as-is because `9.5% / 0.84` is **load-bearing** here — the forward construct scales the
> mean from it (`~9.5% → 5.9%`, `0.0588/0.1156 = 0.51`) — and the study cannot be re-run
> offline (no market-data access; see `docs/research/REPRO00_market_data_reproducibility.md`).
> Changing the input without re-running would be worse than recording the discrepancy. The
> effect is small (0.1pp of CAGR, 0.01 of Sharpe) and changes **no conclusion**: the forward
> Sharpe drop and the sign of every verdict survive either input.

### Forward expected 60/40 return — scenario matrix (0.6·equity + 0.4·bond), vs the 3.75% goal

| equity ↓ / bond → | 3.5% | 4.2% | 5.0% |
|---|---:|---:|---:|
| **5%** | 4.4%* | 4.7%* | 5.0%* |
| **7%** | 5.6%* | **5.9%\*** | 6.2%* |
| **9%** | 6.8%* | 7.1%* | 7.4%* |

`* = meets the 3.75% APY goal.` Base case ≈ 7% equity / 4.2% bond → **5.9%**. **Every** scenario in the grid clears 3.75% on the point estimate.

### Monte-Carlo (base case: forward mean 5.9%/yr, historical risk shape, 10yr, 5000 paths)

| | 5th | 25th | 50th | 75th | 95th |
|---|---:|---:|---:|---:|---:|
| 10yr CAGR | −0.4% | 2.9% | **5.3%** | 7.7% | 11.2% |
| worst DD | −39% | −28% | **−23%** | −18% | −14% |

`P(CAGR ≥ 3.75% goal) = 67% · P(CAGR ≥ 4%) = 64% · P(10yr loss) = 6% · P(maxDD worse than −20%) = 65%.`
**Pessimistic corner** (5% eq / 3.5% bond, mean 4.4%): P(meet goal) = **51%**, P(10yr loss) = 14%, median DD −24%.

### Three things the headline numbers don't print (added by the panel)

1. **Forward Sharpe ≈ 0.51, a ~40% drop from the 0.845 the study leads with.** The forward construct cuts the mean (~9.5%→5.9%) while holding vol (11.56%) and tails constant, so the implied forward Sharpe is 0.0588/0.1156 = **0.51** (verified). The whole D6 arc is fought on Sharpe (active 0.69 vs static 0.85); the honest forward product is roughly *half as good per unit of risk* as the historical figure — this is the forward number, not just the 5.9% CAGR.

2. **The drawdown odds are OPTIMISTIC, not conservative — the MC inherits a benign stock-bond correlation that has already reversed.** Measured daily stock-bond correlation over 2002-2026 is **−0.29** (verified): bonds rallied during the 2008/2020 equity crashes, structurally suppressing 60/40 drawdowns. Forward, that correlation has **already flipped positive** — the 2022-2026 sub-window is **+0.12** (verified), both legs falling together in the rate shock. Re-centering only the mean of the *blended* series inherits the −0.29 co-movement, so the median −23% DD and the 67% goal-odds are plausibly the **optimistic** end of the forward risk shape. This cuts the opposite way from how a reader would assume — and it only **strengthens** the 'fails near-zero-DD' verdict, so it is safe to disclose.

3. **The QQQ tilt inflates VOL marginally but NOT the headline maxDD.** Rebuilding the 60/40 with a broad ^GSPC equity leg gives vol **10.8%** (vs 11.6%) but a **deeper** maxDD of **−33%** (vs −30%) — verified. The 40% IEF leg dominates the blend's risk, so the growth tilt does *not* materially inflate the headline drawdown; the equity-like-tail conclusion holds for a plain-vanilla 60/40 too. The honest QQQ-tilt caveat applies to the RETURN side (the 12.5% equity CAGR) and marginally to vol — **not** to the −23%/−39% DD figures, which are basket-robust.

## The Finding

**At 2026 starting yields the static 60/40 should be expected to return ~5.9%/yr (base case; ~4.4-7.4% across the scenario matrix), which clears the foundational ~3.75% APY goal MORE-LIKELY-THAN-NOT (P≈67% over 10yr, ~51% in the pessimistic corner) — but it FAILS the 'near-zero drawdown' aspiration: median worst drawdown −23%, a 65% chance of a >20% drawdown, and a forward Sharpe of only ~0.51 (vs the 0.845 historical).** The product is a real bond-alternative on RETURN, not on drawdown. The 67% goal-probability (not ~95%) is the honest headline: a ~1-in-3 chance of missing 3.75% over a full decade, with a −0.4% 5th-pctile (a lost decade) and the odds falling to a coin-flip if both equity valuations stay rich AND yields don't help. And the drawdown odds are if-anything **optimistic** because the MC inherits the benign 2002-2026 stock-bond correlation (−0.29) that has already flipped positive (+0.12 in 2022-26) — a forward positive-correlation regime would deepen the drawdowns further. **Consistent with the whole arc ([[D6]]/[[F25]]/[[F37]]/[[F38]]): the original near-zero-drawdown goal is unattainable by any honest static OR active build in this program — the active engine could not add reliable drawdown protection ([[F37]]), and no static lever removes the equity-like tail. The achievable product clears the income goal probabilistically and is a credible bond-alternative on return; it is not, and cannot be made, a near-zero-drawdown vehicle.**

## Verdict

**The verdict HOLDS** — the core split ("forward 60/40 ~5-6%, clears the 3.75% income goal with real dispersion, but fails near-zero-DD with equity-like tail risk") is correct and survives every check. The skeptic panel confirmed the bond≈entry-yield method is textbook-correct, the 5-9% equity range is honest and conservative (clearly below the realized 12.5%), the MC re-centering is correctly implemented and valid, and the reproduction is byte-identical. **No issue invalidates a finding; `blocking=false`.** The five corrections folded above are all **writeup/honesty-level**:

- **(major, disclosed) The drawdown odds are optimistic, not conservative.** The MC inherits the −0.29 historical stock-bond correlation; that has already flipped positive (+0.12 in 2022-26). Disclosed as a caveat — it strengthens, not weakens, the 'fails near-zero-DD' headline, but means the −23% median DD and 67% goal-odds should not be read as worst-case.
- **(major, disclosed) Forward Sharpe ~0.51 is now stated.** The forward product is ~40% worse per unit of risk than the 0.845 the study leads with — the arc-consistent honest number, derived from figures already printed.
- **(minor, corrected) 'comfortably CLEARING' → 'more-likely-than-not clears (P≈67%; ~1-in-3 miss-risk over 10yr; ~coin-flip in the pessimistic corner).'** The point estimate clears the goal; the probability does not clear it comfortably.
- **(minor, disclosed) Goal evaluated as total-return CAGR**, a defensible proxy for a bond-alternative savings vehicle — not a sustainable 3.75% cash distribution (actual cash yield ~1.5-2%), which is a stricter bar given the −0.4% 5th-pctile sequencing risk.
- **(minor, reconciled) The QQQ tilt inflates vol marginally but not the headline maxDD** — a broad ^GSPC 60/40 draws down *deeper* (−33%); the DD verdict is basket-robust.

None touches a finding: the headline never relied on a precise −23% DD or a ~95% goal-certainty, and every correction either strengthens the failure verdict (DD optimism, forward Sharpe) or sharpens an honest framing. **This closes the [[D6]] arc on the GOAL side: the recommended static 60/40 is the honest endpoint of the program — a credible bond-alternative on return that probabilistically meets ~3.75%, but the founding 'near-zero drawdown' aspiration is not deliverable by any build this program has tested.**

## Surviving Caveats

- **SCENARIO study, not data (the dominant caveat).** Bond ≈ 4.2% entry yield and equity 5-9% CAPE-compressed are ASSUMPTIONS. The base case (5.9%) is one defensible mid-estimate; the matrix exposes the full 4.4-7.4% grid. Every conclusion is conditional on these inputs.
- **Drawdown odds inherit a benign stock-bond correlation (−0.29) that has already reversed (+0.12 in 2022-26).** A sustained forward positive-correlation regime deepens drawdowns and lowers the goal odds — the −23% median DD and 67% probability are if-anything optimistic.
- **Forward Sharpe ~0.51 vs historical 0.845** — return falls, risk shape held constant, so risk-adjusted quality roughly halves.
- **67% (not ~95%) is the honest goal-probability** — a ~1-in-3 decade-miss, ~51% in the pessimistic corner; the −0.4% 5th-pctile CAGR is a plausible lost decade.
- **Income-vs-CAGR:** the goal is tested as total-return CAGR≥3.75%, a looser bar than a sustainable 3.75% cash withdrawal (actual cash yield ~1.5-2%; sequencing risk).
- **QQQ tilt inflates vol (11.6% vs 10.8%) but not maxDD (broad 60/40 is deeper, −33%)** — the equity-like-tail / fails-near-zero-DD verdict is basket-robust.
- **MC central tendency is conservative:** median realized CAGR 5.3% sits ~0.6% below the 5.9% arithmetic target (= 0.5·σ² variance drag), so the distribution does not flatter the median return.

## Reproduce

```
venv/bin/python tools/forward_expectation_study.py                  # matrix + MC + verdict
venv/bin/python tools/forward_expectation_study.py --json out.json  # full result dict
venv/bin/python tools/ctx.py web D4                                 # the foundational goal question this resolves
venv/bin/python tools/ctx.py web D6                                 # the go/no-go arc this closes (goal side)
venv/bin/python tools/ctx.py web F38                                # the bond-bull/QQQ-tilt caveat this re-prices forward
```
