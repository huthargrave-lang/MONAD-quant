# Study #2 — Does Active Daily-MR Beat the DECISION-RELEVANT Static 60/40 (Not Just 50/50)?

**Artifact:** [`tools/power_study_6040.py`](../../tools/power_study_6040.py) · **Reproduce:** `venv/bin/python tools/power_study_6040.py`
(deterministic, seed=0, ~1–2 min; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E26 (the study) · F35 (the finding) · **builds on** study #1 ([E25/F34](D6_power_equivalence_study.md))
**Status:** verdict **HOLDS** — adversarially verified by a 3-lens skeptic panel (60/40 construction & leak-freeness; statistics reuse & reproducibility; interpretation & honesty); `blocking=false`, `verdict_holds=true`. One disclosure gap (the inherited ^GSPC price-only bias) and three interpretation softenings are recorded in Surviving Caveats; none invalidate the conclusion. Every reported number reproduces byte-identically (re-run JSON is deterministic).

## The Question

[[E25]]/[[F34]] tested the active leverage-free daily mean-reversion (MR) engine against a static **50/50 equity/cash** blend and found **no risk-adjusted edge** (ΔSharpe ≈ 0, CI straddles 0). But 50/50-equity/cash is Sharpe-invariant to buy&hold (cash-scaling does not move Sharpe), so that baseline tops out at the buy&hold Sharpe (~0.78–0.80). **The actually-recommended bond-alternative ([[D6]]/[[F25]]) is a static 60/40 equity/BOND (IEF), whose Sharpe (~0.84 over 2014–2026) EXCEEDS buy&hold** thanks to the negative equity–bond return correlation. That is the **harder, decision-relevant bar.**

A skeptic on the E25 verification panel flagged exactly this: 50/50 is conservative IN THE ACTIVE ENGINE'S FAVOUR; re-test against 60/40. This study does so — restricting the windows to where IEF actually trades, so the early-2000s bond leg is a REAL bond return and not silently "60/40-cash" (the bias `mr_daily_lab.cmd_gonogolong` warns of). The active leg is held **identical** to E25 (same `lab.sleeve` dip+5d, 200d gate, 5bps cost, same baskets): same active, harder bench.

## Methodology (leak-free; reuses E25's vetted primitives)

**Reuse, not reimplementation.** `analyze()` draws every statistic from the already-5-lens-verified [`tools/power_study.py`](../../tools/power_study.py) (E25): `ps.sharpe`, `ps.paired_sharpe_diff_boot` (block=20, B=5000, seed=0, SAME block-start indices both legs), `ps.paired_maxdd_diff_boot`, `ps.norm_cdf`, `ps.maxdd_pct`, `ps.ann_pct`, and the `Z`/`Z_ALPHA`/`ANN` constants. The only inline closures (`power()`, `years_for_power()`) are byte-identical formulas to those inside `power_study.study_window`, so the E25 verification carries over.

- **Active leg** = equal-weight mean of dip+5d sleeves: buy the close of a DOWN day only if price > 200d-MA (bear gate), long-only, non-overlapping 5-day holds, 5bps round-trip cost. Confirmed **byte-identical** to E25's active leg (max |diff| = 0.0) on the shared windows.
- **60/40 bench** = a daily-rebalanced, constant-weight `0.6·(equal-weight mean of equity daily LOG-returns) + 0.4·(IEF daily LOG-returns)`. Confirmed equal to the construction at `np.allclose(atol=1e-15)` and **byte-identical** to `mr_daily_lab._gonogo_core`'s static-60/40 daily series (max |diff| = 0.0, n=3133). IEF appears ONLY in the bond leg — never in the equity blend or active sleeve (no double-counting).
- **IEF-inception handling.** IEF's real first date is 2002-07-30; Window B's first traded day is 2002-07-31 (first log-return after inception), so the window starts exactly at inception and the bond leg is real for all 6010 days. Slicing-after-computing-sleeves was verified **leak-free**: computing sleeves on full 2000–2026 history then slicing yields byte-identical traded returns to computing on a truncated warmup-only history (the 200d-MA/252d-vol warmup on pre-window data is legitimate causal warmup). The 57 zero-return IEF days in B are GENUINE flat closes (low-precision early-2000s adjusted-close granularity), **not** silent cash-fills — Window B's IEF Sharpe is a healthy 0.52.
- **Paired statistic** = `Sharpe(active*) − Sharpe(60/40*)` on the SAME resampled block starts (preserves cross-correlation; pairing roughly halves the SE). MDE@80% power (two-sided 5%) = `(z0.975+z0.80)·SE`. TOST equivalence at ±Δ established iff the 90% bootstrap CI ⊂ (−Δ, +Δ); smallest provable margin Δ\* = `max(|lo90|,|hi90|)`. A paired maxDD-gap bootstrap judges capital-preservation against the REAL 60/40 (not a 0.5· cash blend — study #1's comparator was correctly upgraded here).

**Cross-check (independent).** `venv/bin/python tools/mr_daily_lab.py gonogo` reports static 60/40 Sharpe **0.84**, maxDD **−21.0%**, ann **7.8%**, and active D5 Sharpe **0.68** / maxDD **−13.9%** / ann **6.1%** — matching Window A exactly. The 60/40 daily series is byte-identical to the canonical go/no-go row.

## Results

| Metric | A: 2014–2026 (QQQ+SPY+IWM+DIA+GLD + IEF) | B: 2002–2026 (^GSPC+QQQ+IWM+DIA + IEF, sliced to IEF inception) |
|---|---|---|
| Days / years | 3133 / 12.5yr | 6010 / 23.9yr |
| Sharpe active | 0.68 | 0.43 |
| Sharpe 60/40 (equity / IEF) | **0.84** (0.78 / 0.28) | **0.70** (0.55 / 0.52) |
| Ann% active vs 60/40 (point est., no CI) | 6.09 vs 7.85 | 4.63 vs 7.91 |
| **ΔSharpe (active − 60/40)** | **−0.17** | **−0.26** |
| SE (paired bootstrap) | 0.20 | 0.16 |
| 95% CI | [−0.56, +0.24] | [−0.58, +0.05] |
| 90% CI | [−0.50, +0.18] | [−0.535, **+0.001**] |
| Edge detected? / active sig. worse (95%)? | NO / NO | NO / NO |
| **MDE@80% power** | **0.57** | **0.46** |
| power now {0.10/0.20/0.30/0.50} | 8/16/31/68% | 9/23/46/87% |
| **TOST ±0.20 / ±0.30 / ±0.50** | fail / fail / **PASS** | fail / fail / **fail** |
| **Smallest provable margin Δ\*** | **0.50** | **0.54** |
| maxDD active vs 60/40 | −14% vs −21% | −20% vs −33% |
| paired maxDD-gap CI (+=active shallower) | [−8.2, **+1.0**, +10.8] | [−16.8, **−0.7**, +14.3] |

## The Finding

**Against the harder, decision-relevant 60/40, active has a LOWER point Sharpe in both windows (−0.17 / −0.26) — but in both the 95% CI straddles 0, so the loss is not statistically reliable.** This is the meaningful shift versus E25/F34: against the easier 50/50 the point estimate was ≈0; against 60/40 the point estimate moves clearly negative, while the CIs honestly still include 0.

- **Window A (12.5yr):** active underperforms within noise (95% CI [−0.56, +0.24]). TOST positively rules out (95% conf) any edge larger than Δ\*=0.50, but cannot certify equivalence at the tighter ±0.20/±0.30 — and an edge that large in active's favour is firmly excluded by the negative point estimate anyway.
- **Window B (24yr):** the deficit grows to −0.26 and the **90% CI upper bound is +0.001** — i.e. one-sided, active is *almost exactly on the boundary* of "significantly worse" (recomputed one-sided P(boot≥0) ≈ 0.051) and fails to clear it by a hair. The tool correctly makes **no hard significance claim** (`active_worse_significant` is gated on the 95% upper bound, which is +0.052 > 0). "Nearly significantly worse over 24yr" is a fair, hedged reading.

Annualized return points the same way (6.09 vs 7.85; 4.63 vs 7.91), with the B gap (−3.28%/yr) large — but this is a **point estimate only (no bootstrap CI)**, so it corroborates rather than independently proves the Sharpe deficit.

## Drawdown Panel

Active's only candidate advantage is **shallower drawdown**: point maxDD −14% vs −21% (A) and −20% vs −33% (B). But the paired maxDD-gap bootstrap **straddles 0 in both windows** ([−8.2, med +1.0, +10.8] and [−16.8, med −0.7, +14.3]) — so the DD edge is **path-dependent, NOT statistically significant**. (Note the B median is actually slightly *negative*, i.e. on the median resample active's drawdown is no shallower.) A plausible-but-unquantified hypothesis is that 2022 (stocks AND bonds down together) is where 60/40's diversification erodes and active's ability to sit in cash matters most — but **no 2022-specific decomposition was run**, so this is storytelling, not evidence, and must not be read as rescuing the DD edge the bootstrap just declared unreliable.

## Verdict

**Active daily-MR does NOT beat the recommended static 60/40.** It has a lower point Sharpe in both windows (−0.17 / −0.26, within noise — the 95% CIs straddle 0), a lower point annualized return, and its only candidate advantage (shallower drawdown) is path-dependent and not statistically reliable. Over 24yr the deficit is nearly significant one-sided (90% upper bound +0.001). The E25/F34 "no edge vs static" verdict **HARDENS at the point-estimate level** against the harder, decision-relevant bar — moving from ≈0 (vs 50/50) to clearly negative (vs 60/40) — **while the CIs still straddle 0**, so the honest claim is "no edge, now leaning negative," not "significantly worse."

**The static 60/40 equity/bond stays the recommended bond-alternative.** The active engine is at best a regime-dependent low-drawdown overlay — consistent with [[D6]]/[[F25]].

## Surviving Caveats

- **^GSPC price-only (Window B) — the one disclosure gap.** 1 of 4 Window-B equity legs (^GSPC) omits ~1.9%/yr dividends, understating the equity blend ~0.5%/yr and the 60/40 bench ~0.3%/yr (~0.026 Sharpe). This is **inherited (and disclosed) from E25/`power_study.load_2000`** and is now also disclosed in study #2's own docstring/JSON. **Direction is conservative AGAINST active**: the true 60/40 is even better, so correcting it would only WIDEN active's deficit. It strengthens, not threatens, the verdict.
- **24yr near-significance.** Window B's 90% CI upper bound is +0.001 and the one-sided bootstrap p ≈ 0.051 — sitting exactly on the conventional 5% boundary and failing to reject "active worse" by a hair. No hard "significantly worse" claim is made.
- **DD edge path-dependent.** Both maxDD-gap CIs straddle 0; active's drawdown advantage is not statistically reliable.
- **Underpowered for small edges.** MDE@80% is 0.57 (A) / 0.46 (B); power for a true 0.20-Sharpe edge is only 16% / 23%. TOST certifies (95% conf) only that edges larger than Δ\*=0.50 (A) / 0.54 (B) are absent; below that floor it is genuine absence-of-evidence (resolving ~0.20 would need ~100–124yr at current noise).
- **Log-return convention.** The 60/40 Sharpe 0.84 is log-convention; a simple-return daily-rebalanced 60/40 is ~0.97. The convention is consistent across active/equity/IEF and the gonogo reference (so ΔSharpe is apples-to-apples), and the harder simple-return bar would only worsen active.
- **Window non-independence.** The 12.5yr window is a calendar subset of the 24yr window (~52% overlap); A and B are not independent tests.
- **Return comparison is point-estimate only** — no bootstrap CI on the annualized-return difference, unlike the Sharpe/maxDD claims.

## Reproduce

```
venv/bin/python tools/power_study_6040.py                 # both windows + verdict
venv/bin/python tools/power_study_6040.py --json out.json # full result dict
venv/bin/python tools/mr_daily_lab.py gonogo              # cross-check: static-60/40 Sharpe 0.84
```
