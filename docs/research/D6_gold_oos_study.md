# Study #6 — Does the 10% Gold Sleeve Survive a Clean Out-of-Sample Test? (Resolving Study #5's Gold Hypothesis)

**Artifact:** [`tools/gold_oos_study.py`](../../tools/gold_oos_study.py) · **Reproduce:** `venv/bin/python tools/gold_oos_study.py`
(deterministic, seed=0; first run fetches ~30s into `/tmp/gold_oos_close.csv`, then cached; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E30 (the study) · F39 (the finding) · **resolves** the one live OOS hypothesis left by study #5 ([E29/F38](D6_static_product_study.md)); builds on the go/no-go ([[D6]]), the 26yr confirmation ([[F25]]), and the recommended-product close ([[F37]]).
**Status:** verdict **HOLDS** (with one framing softening) — adversarially verified by a 2-lens skeptic panel (data/windowing/leak-freeness/cross-check; interpretation & honesty). Every reported number reproduces **byte-identically** (deterministic JSON equal across reruns). `blocking=false`, `verdict_holds=true`. No issue invalidates a finding. The skeptics' material points — that the headline verb "survives" over-promises relative to strict-OOS evidence, that the OOS holdout is underpowered, and that "partially survives" is a post-hoc descriptive tier rather than the pre-registered pass criterion — are **disclosure/framing** items, recorded below in Results, Verdict and Surviving Caveats. The substance is unchanged: **on the only clean, independent OOS test gold does not clear, so the static 60/40 stands.**

## The Question

Study #5 ([[E29]]/[[F38]]) tested three candidate third sleeves (GLD / TLT / HYG) against the recommended static 60/40 and found that **only gold showed even a directional diversification signal** — but it was the **best of three** (a multiple-comparisons winner), tested **only on 2014–2026** (a strong gold-bull sub-window), and it **FAILED a Bonferroni correction** (one-sided P=0.031 > 0.0167; two-sided CI lower bound −0.003 already fails 0). Study #5 itself named the one clean way to settle it: **GLD launched 2004-11-18, so 2004–2013 is a genuine HOLDOUT** that study #5's gold test never touched.

This study runs the **same** +10% gold sleeve (carved 50/50 from the 0.6 equity / 0.4 IEF legs) and the **same** paired block bootstrap as study #5, on three windows:
1. **OOS holdout** (2004-11-19 → 2013-12-31) — the disjoint pre-2014 data, **the real test**.
2. **in-sample** (2014-01-02 → 2026-06-18) — **reproduces study #5's GLD result** (the cross-check).
3. **full** (2004-11-19 → 2026-06-18, 21.6yr) — the tightest CI, but **not independent** (it contains the in-sample period).

**Pre-registered decision rule (docstring, L17-20):** gold is a REAL, OOS-confirmed improvement *only if* its ΔSharpe/ΔCalmar/ΔmaxDD clears 0 in the 2004-2013 holdout **AND** over the full window — not just in 2014-2026. By that pre-registered rule the answer is an **unambiguous NO**: the holdout clears nothing. ("Partially survives" below is a *post-hoc descriptive tier*, not the pre-specified pass criterion — stated plainly so the reader does not read the tier name as a pass.)

## Methodology (read-only; reuses study #5's thrice-verified primitives; deterministic, seed=0)

- **Universe:** GLD + SPY + QQQ + IWM + DIA + IEF, fetched once via `yfinance auto_adjust=True` (total-return) from 2004-01-01 into `/tmp/gold_oos_close.csv`. The fetch's GLD column first goes non-NaN at **2004-11-18** (exactly GLD's real inception); `legs()` aligns on `.dropna()`, so the GLD inception correctly gates the start of every window (first usable return 2004-11-19).
- **Reused primitives (from [`tools/static_product_study.py`](../../tools/static_product_study.py), study #5):** SIMPLE-return product accounting, `pmetrics`, `equity_blend` (equal-weight daily-rebalanced SPY/QQQ/IWM/DIA), and the paired block bootstrap (`BLOCK=20`, `B=5000`, `seed=0`) — a single block-start array drives BOTH `blend` and `core` each iteration (real pairing), percentile CI on the difference.
- **Carve:** core = `0.6·equity + 0.4·IEF`; blend = `0.55·equity + 0.35·IEF + 0.10·gold` — the 10% gold sleeve carved exactly 50/50 from the 0.6 equity and 0.4 bond legs (weights sum to 1.0). The full-window sweep uses the same equal-carve `(0.6−0.5w, 0.4−0.5w, w)`.
- **Windows are a clean partition:** OOS (2294 days) and in-sample (3134 days) are disjoint (OOS last 2013-12-31 < IS first 2014-01-02; intersection = 0 days) and their union is exactly the full window (2294 + 3134 = 5428). Verified.

**Leak-free (independently re-checked by the panel):** recomputing the OOS legs from a price frame truncated at 2013-12-31 vs the full frame gives **byte-identical** legs (max|diff| = 0.0, 2294 rows); returns are contemporaneous `pct_change`; the bootstrap resamples only within the per-window array (no cross-window contamination).

**Cross-check (validates the reused primitives):** study #6's in-sample ΔSharpe [−0.002, +0.152], P(DD shallower)=0.939, corr +0.14 **reproduces** study #5's GLD `boot_10pct` ΔSharpe [−0.003, +0.154], P=0.944, corr +0.14 to rounding — confirming `pmetrics`/`paired_boot`/`equity_blend`/`simple_ret` are the same vetted code. (The trivial gap and the n_days 3134-vs-3133 difference come from a different-date `yfinance` fetch back-adjusting dividends to a moving anchor — IWM levels differ ~7.5% mean, daily returns ~5e-5 mean — immaterial to the verdict.)

## Results

### Three windows (point metrics + paired-bootstrap ΔCIs vs the 60/40 core)

| window | span (yr, days) | gold↔core corr | core 60/40 Sharpe / CAGR / maxDD / Calmar | +10% gold Sharpe / CAGR / maxDD / Calmar | gold standalone Sharpe | ΔSharpe CI | ΔCalmar CI | ΔmaxDD CI | P(DD shallower) |
|---|---|---:|---|---|---:|---|---|---|---:|
| **OOS holdout** (the real test) | 2004-11→2013-12 (9.1yr, 2294) | +0.09 | 0.70 / 8.0% / −30% / 0.26 | 0.78 / 8.6% / −27% / 0.32 | +0.61 | **[−0.04, +0.20]** straddles 0 | [−0.05, +0.23] straddles 0 | [−1.1, +6.2] straddles 0 | 88% |
| **in-sample** (reproduces #5) | 2014-01→2026 (12.5yr, 3134) | +0.14 | 0.88 / 9.4% / −22% / 0.43 | 0.96 / 9.8% / −21% / 0.47 | +0.69 | **[−0.00, +0.15]** straddles 0 | [−0.02, +0.19] straddles 0 | [−0.4, +4.4] straddles 0 | 94% |
| **full** (NOT independent) | 2004-11→2026 (21.6yr, 5428) | +0.11 | 0.80 / 8.8% / −30% / 0.29 | 0.88 / 9.3% / −27% / 0.34 | +0.65 | **[+0.01, +0.15] ABOVE 0** | [−0.01, +0.15] straddles 0 | [−0.7, +5.8] straddles 0 | 92% |

### Full-window gold-weight sweep (in-sample, selection-biased — not a recommendation)

| w_gold | Sharpe | CAGR | maxDD | Calmar |
|---:|---:|---:|---:|---:|
| 0% | 0.801 | 8.8% | −30.5% | 0.289 |
| 5% | 0.841 | 9.1% | −28.7% | 0.315 |
| 10% | 0.878 | 9.3% | −27.1% | 0.343 |
| 20% | 0.933 | 9.7% | −25.8% | 0.375 |
| 30% | **0.959** ←Sharpe* | 10.1% | −25.3% | **0.398** ←Calmar* |

Sharpe rises **monotonically** 0.80→0.96 and Calmar 0.29→0.40 at 30% gold. This is in-sample optimization over the full window; the paired bootstrap does **not** confirm reliability, so it is selection-biased and not a sizing recommendation.

### The four things that matter

1. **The clean OOS holdout fails.** In the genuinely disjoint 2004-2013 window — the *only* independent test of study #5's best-of-3 winner — **all three** risk-adjusted CIs straddle 0. Gold does not clear it. By the pre-registered holdout-AND-full rule, this is the binding result: gold does **not** confirm.
2. **The only CI above 0 is non-independent.** The full-window ΔSharpe [+0.01, +0.15] is the sole CI clearing 0, and the full window **contains** the 2014-2026 in-sample data. Strip it and **no independent CI clears anything** (holdout straddles 0; in-sample ΔSharpe straddles 0 too). The full-window "significance" leans on the in-sample period. *(That +0.012 lower bound is NOT a fragile artifact of the BLOCK=20 choice — verified below — but block-robustness does not make a non-independent window independent.)*
3. **Direction is robust; magnitude is not.** Gold shallows the drawdown in 88%/94%/92% of resamples (holdout/IS/full) and the point Sharpe is higher in every window — a consistent **directional tilt**. But P(DD shallower) is a sign-consistency probability, **not** a CI excluding 0, and **no ΔCalmar or ΔmaxDD CI excludes 0 in any window.** So the *sign* of the drawdown benefit is robust; its *size* is not established anywhere.
4. **Part of the lift is gold's own bull, not pure diversification.** Gold standalone Sharpe was +0.61 (holdout, riding its 2004-2011 bull) and +0.69 (in-sample) — positive throughout — so the diversification benefit cannot be cleanly separated from gold's own directional run. *(The 50/50 carve is NOT the confound: funding the 10% gold purely from equity still lifts the holdout Sharpe 0.70→0.84, so the lift is not a bond-bull-substitution artifact — the gold-own-return caveat is the right one.)*

### Panel verification (decisive additional checks)

- **Full-window ΔSharpe lower bound is BLOCK-robust (strengthens the "just clears 0" claim).** Re-running the bootstrap at BLOCK ∈ {10, 20, 30, 40, 60} keeps the full-window ΔSharpe lower bound ABOVE 0 (0.007, 0.012, 0.014, 0.015, 0.021) — it *widens* rather than collapses. The skeptic concern that the +0.012 lower bound might be a single block-length artifact is **resolved**. (It does not, however, rescue a strict-OOS edge — the window is still non-independent.)
- **OOS holdout is underpowered ("absence of evidence" caveat).** Scaling the OOS gold weight up to 30% (point ΔSharpe +0.16, ~2x the 10% lift) STILL leaves the ΔSharpe CI straddling 0 ([−0.20, +0.53]), because gold-driven variance grows faster than the point estimate. So the holdout genuinely cannot resolve a +0.08 point lift — its straddle is "**failed to confirm**" more than "confirmed null." This does not change the bottom line, but it tempers how strongly the holdout failure should be read.

## The Finding

**Gold's study-#5 signal does NOT survive a clean out-of-sample test. On the disjoint 2004-2013 holdout — the right test for a multiple-comparisons in-sample winner — every risk-adjusted CI straddles 0, exactly as study #5 anticipated for a best-of-3 / Bonferroni-failing candidate.** The only independent thing that *is* robust is a **directional** drawdown tilt (DD shallower in 88-94% of resamples in all three windows) and a higher point Sharpe in every window — but the *magnitude* of that benefit is not significant anywhere, and the single CI that clears 0 (full-window ΔSharpe [+0.01,+0.15], block-robust) comes from a window that contains the in-sample data. Part of even the point-estimate lift is gold's own 2004-2011 bull, not pure diversification. So gold is a **defensible discretionary diversifier (the direction is real), NOT a statistically-confirmed upgrade.** The pure static 60/40 stands.

## Verdict

**The verdict HOLDS, with the headline reframed to lead with the strict-OOS failure.** "Gold partially survives — directionally robust, but not a strict OOS edge; the static 60/40 stands" is correct in substance: the body of the original verdict flags the full-window non-independence, the direction-vs-magnitude split, and the gold-own-bull entanglement honestly and repeatedly. The skeptic panel's only material objection is to the *verb*: by the study's own **pre-registered** holdout-AND-full rule the answer is an unambiguous **NO**, and the only CI that clears is non-independent, so leading with "survives" relaunders a result that, on independent evidence alone, did not survive. The honest headline is therefore: **gold FAILS a strict OOS test but shows a robust directional drawdown tilt; "partially survives" is a post-hoc descriptive tier, not the pre-registered pass.** Either way the action is identical and unchanged from study #5: **the pure static 60/40 stands; a small gold sleeve is a discretionary judgment call, not an evidence-backed recommendation.**

**This RESOLVES the one live hypothesis study #5 left open.** Study #5 explicitly deferred gold to OOS confirmation ("a small gold sleeve is the single hypothesis worth testing out-of-sample"). The clean pre-2014 holdout *is* that test, and gold does not clear it — consistent with [[F38]]'s best-of-3 / Bonferroni-fail read, with [[D6]] (the active engine has no edge; a static allocation is the bond alternative), and with [[F25]] (more data narrows but does not rescue). There is no remaining live single-lever improvement to the static 60/40.

## Surviving Caveats

- **Strict-OOS failure is binding; "partially survives" is a descriptive tier, not a pass.** By the pre-registered holdout-AND-full rule gold does NOT confirm (the holdout clears nothing). Read "partially survives" as post-hoc description.
- **The only CI above 0 is non-independent.** Full-window ΔSharpe [+0.01,+0.15] is the sole clearing CI and its window contains the in-sample period; no independent CI clears anything. *(The lower bound is BLOCK-robust — ABOVE 0 for BLOCK 10-60 — so "just clears 0" is real, but non-independence stands.)*
- **Direction robust, magnitude not.** P(DD shallower)=88-94% is sign-consistency, not a CI on effect size; no ΔCalmar/ΔmaxDD CI excludes 0 in any window. Do not read "drawdown-conscious" framing as an established DD-size benefit — only its sign is robust.
- **OOS holdout is underpowered.** A +0.08 point ΔSharpe is below its minimum detectable effect; even a doubled (30%) gold weight does not clear 0. The clean-OOS straddle is "failed to confirm," partly low power, not pure confirmed null.
- **Gold-own-bull entanglement.** Gold standalone Sharpe +0.61 (holdout) / +0.69 (IS) — its diversification benefit cannot be cleanly separated from its own directional run. (The 50/50 carve is not the confound: equity-only funding still lifts holdout Sharpe 0.70→0.84.)
- **In-sample sweep is selection-biased.** Sharpe 0.80→0.96 at 30% gold is in-sample optimization; the bootstrap does not confirm reliability; a 30% gold sleeve is not recommended.
- **Cross-check is exact-to-rounding, not byte-exact, vs study #5.** Different-date `yfinance` fetch (auto_adjust moving anchor) shifts IWM levels ~7.5% mean / returns ~5e-5 mean / n_days 3134-vs-3133; immaterial. The cache is reused indefinitely without a freshness check — delete `/tmp/gold_oos_close.csv` to force a same-date re-fetch.
- **Inherited from [[F38]]/[[D6]]:** the ~9.4% CAGR rides a QQQ growth tilt + a 2002-2026 secular bond bull (IEF 3.6%/yr standalone) that won't necessarily repeat; SIMPLE-return convention makes absolute Sharpes differ ~0.01 from the log-convention studies E25-E28. A backward-looking realized ceiling, not a forward expectation.

## Reproduce

```
venv/bin/python tools/gold_oos_study.py                  # 3 windows + sweep + verdict
venv/bin/python tools/gold_oos_study.py --json out.json  # full result dict
venv/bin/python tools/ctx.py web F38                     # study #5: the gold hypothesis this resolves
venv/bin/python tools/ctx.py web D6                       # the go/no-go arc this closes on the product side
```
