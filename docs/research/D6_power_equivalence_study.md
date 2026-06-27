# D6 Power & Equivalence Study — Is "No Active Edge" Evidence-of-Absence, or Just Underpowered?

**Artifact:** [`tools/power_study.py`](../../tools/power_study.py) · **Reproduce:** `venv/bin/python tools/power_study.py`
(deterministic, seed=0, ~1–2 min; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E25 (the study) · F34 (the finding)
**Status:** verdict **HOLDS** — adversarially verified by a 5-lens skeptic panel (power/MDE,
bootstrap/TOST, reproducibility/leak-free, interpretation, blind-spots); `blocking=false`,
`verdict_holds=true`. Two over-statements in the first draft were corrected (see Verdict §4 and
the disjoint-window §); all surviving caveats are listed below.

## The Question

[[D6]]/[[F22]]/[[F25]] established a *point* result: the active leverage-free daily mean-reversion
(MR) engine does not beat a trivial STATIC allocation of the same assets on a risk-adjusted basis,
and the bootstrap Sharpe-difference CI straddles zero. **A CI that straddles zero is ambiguous:**

- **(a) evidence-of-absence** — the edge is genuinely ~0 and we can RULE OUT any meaningful edge
  (a positive equivalence result), or
- **(b) absence-of-evidence** — the test is too underpowered to tell, and a real edge could hide
  inside a wide CI.

This study separates the two with three tools the go/no-go harness never ran: a **paired
block-bootstrap of the Sharpe difference**, **minimum-detectable-effect (MDE) + power curves**,
and a **TOST equivalence test**.

## Methodology (all leak-free; reuses `tools/mr_daily_lab.py`'s canonical sleeve)

- **Active leg** = equal-weight mean of dip+5d sleeves: buy the close of a DOWN day only if
  price > 200d-MA (bear gate), long-only, non-overlapping 5-day holds, 5bps round-trip cost.
  Leak-free: entry at bar `d` uses only `ret[d]` and the trailing `rolling(200).mean()` known at
  close of `d`; holds are `range(d+1, …)` and `d` advances by the hold, so windows never overlap.
- **Bench leg** = equal-weight BUY&HOLD of the same assets. Cash-scaling is Sharpe-invariant, so
  `Sharpe(static 50/50 equity/cash) == Sharpe(bench)`; bench is the Sharpe baseline and the
  `0.5·bench` cash blend is used only for the maxDD/capital-preservation panel.
- **PAIRED block bootstrap:** block = 20 trading days, B = 5000, seed = 0, the SAME block-start
  indices resampled for BOTH legs (preserves cross-correlation). Statistic =
  `Sharpe(active*) − Sharpe(bench*)`. This is the clean quantity — `mr_daily_lab`'s own
  `boot(r − 0.5e)` is the Sharpe of the SPREAD, which `mr_daily_lab.py:323-324` itself flags as
  mechanically confounded by a synthetic-short-equity artifact. The paired design halves the SE
  (0.19 vs 0.39 unpaired on the 12.5yr window) and is load-bearing.
- **MDE@80% power, two-sided 5%** = `(z0.975 + z0.80)·SE = 2.8016·SE`.
- **power(Δ)** = `Φ(Δ/SE − 1.96) + Φ(−Δ/SE − 1.96)`, Φ via `math.erf` (no scipy).
- **resolution horizon @80% power:** SE assumed ∝ 1/√years, anchored on the observed-window SE —
  *order-of-magnitude only* (see caveats).
- **TOST equivalence at ±Δ:** established iff the 90% bootstrap CI ⊂ (−Δ, +Δ). The smallest
  provable margin Δ\* = `max(|lo90|, |hi90|)`.

## Results

| Metric | A: 2014-2026 (QQQ+SPY+IWM+DIA+GLD) | B: 2000-2026 (^GSPC+QQQ+IWM+DIA) | C: 2000-2013 disjoint |
|---|---|---|---|
| Days / years | 3133 / 12.5yr | 6654 / 26.5yr | 3520 / 14.0yr |
| Sharpe active / bench | 0.68 / 0.78 | 0.37 / 0.37 | 0.26 / 0.15 |
| **ΔSharpe (active − bench)** | **−0.10** | **+0.00** | **+0.10** |
| SE (paired bootstrap) | 0.19 | 0.15 | 0.23 |
| 95% CI | [−0.48, +0.27] | [−0.30, +0.28] | [−0.36, +0.53] |
| Edge detected? | NO | NO | NO |
| **MDE@80% power** | **0.54** | **0.42** | **0.63** |
| power now {0.10/0.20/0.30/0.50} | 8/18/34/74% | 10/27/52/92% | 7/14/26/60% |
| resolution horizon {0.20/0.30}† | 90 / 40 yr | 114 / 51 yr | 141 / 62 yr |
| **TOST ±0.20 / ±0.30 / ±0.50** | fail / **fail** / PASS | fail / **PASS** / PASS | fail / fail / PASS |
| **Smallest provable margin Δ\*** | **0.42** | **0.25** | **0.45** |
| maxDD active vs bench | −14% vs −30% | −20% vs −56% | −20% vs −56% |
| paired maxDD-gap CI | [−10.6, −1.8, +6.6] | [−16.1, +1.0, +18.2] | [−13.3, +5.6, +27.0] |

† Order-of-magnitude under a stationarity assumption — see caveats. Window C is emitted directly by
the tool as the genuine independent corroboration (B's 2014–26 is a calendar subset of A, so A and B
are not independent tests; C is disjoint from A).

**Independent re-derivation (synthesis check):** all power numbers reproduce exactly from the SEs
(`2.8016·0.192 = 0.538`, `2.8016·0.148 = 0.415`; every `power(Δ)` and horizon value matches to 3 dp).
A separate skeptic agent independently recomputed Window C and got ΔSharpe +0.105 / SE 0.226 /
CI [−0.36, +0.53] — matching the tool to the decimals.

## Power vs MDE vs TOST logic

- **edge_detected = False** in all three windows (95% CI straddles 0) → no risk-adjusted edge is
  *detected*. Alone, this is ambiguous between (a) and (b).
- **MDE@80% = 0.42 (26.5yr):** true edges *smaller* than this are likely missed; power for a 0.20
  edge is only 27% — a small edge is firmly in the underpowered regime.
- **TOST resolves the ambiguity at large margins:** the 90% CI ⊂ (−0.30, +0.30) over 26.5yr, so we
  POSITIVELY conclude active ≈ static within ±0.30 Sharpe at 95% confidence — genuine
  **evidence-of-absence** for any edge bigger than ~0.25. Below the resolution floor it is genuine
  **absence-of-evidence**.

## Signal-vs-edge contrast (the load-bearing distinction)

The lag-1 daily MR **autocorrelation** — the *signal* — is well-powered and robustly negative under
the [[F18]] heteroskedasticity-robust SE: over 26.5yr `^GSPC −3.6, QQQ −2.5, IWM −3.0, DIA −3.2`
(min equity |t_robust| = 2.55, all clear ±1.96); GLD ~0 as a non-mean-reverter control. **Mean
reversion EXISTS** — this is not absence-of-evidence about the signal ([[F16]]). What is
small/equivocal is the *tradeable edge vs static*. **Scope:** this proof is on OVERLAPPING daily
autocorrelation; the engine trades NON-overlapping 5-day holds, where the evidence is weaker (per
[[F18]], only QQQ clears t>2 in the 12yr window).

## Verdict

**D6 is CORRECT and is mostly evidence-of-absence.**

1. The MR **signal** is provably real (robust |t| ≥ 2.5 over 26.5yr); the **edge vs static** is not
   detected in any window — ΔSharpe −0.10 (12.5yr) / +0.00 (26.5yr) / +0.10 (disjoint 2000-2013),
   all three CIs straddle 0.
2. **Partly evidence-of-absence:** TOST positively rules out (95% conf) any active Sharpe edge larger
   than **~0.42 robustly across both windows, and ~0.25–0.30 over the full 26.5yr** (a narrow pass at
   ±0.30, Δ\*=0.25). The "underpowered" objection is retired for large edges.
3. **Partly absence-of-evidence:** MDE ≈ 0.42 Sharpe, so a small edge (≤0.2 Sharpe) cannot be
   excluded — resolving it would need ~90–114yr at current noise (we have 26.5).
4. **Corrected over-statement:** the residual is **undetectable, NOT economically irrelevant.** At
   ~10% vol a ≤0.2-Sharpe edge is ~≤2%/yr — roughly a third of the 4–6%/yr bond-alternative income
   target. The honest framing is "too small to measure even over 26yr," not "trivial." This still
   backs the static recommendation: **you cannot bank an edge you cannot measure.**
5. **Conservative baseline:** the test is vs buy&hold (≡ static 50/50, the EASIER bar). The
   actually-recommended static 60/40 equity/bond (Sharpe ~0.86 > 0.80, per [[D6]]/[[F25]]) beats
   active on Sharpe AND return — so against the decision-relevant baseline active looks strictly worse.

**Capital preservation** is real-on-average but path-dependent: point maxDD −20% vs −56% (26.5yr),
but the paired maxDD-gap bootstrap straddles 0 ([−16.1, +1.0, +18.2]).

## Surviving caveats

- **Resolution floor:** equivalence is only established down to Δ\*≈0.25 (26.5yr, narrow) / 0.42
  (12.5yr). Smaller edges are genuine absence-of-evidence.
- **Residual is not negligible:** ≤0.2 Sharpe ≈ ≤2%/yr ≈ a third of the income mandate; undetectable
  ≠ trivial.
- **Window non-independence:** 12.5yr ⊂ 26.5yr (~47% overlap); the disjoint 2000-2013 slice
  (ΔSharpe +0.10, CI straddles 0) is the real independent corroboration (and is emitted by the tool).
- **Stationarity extrapolation:** resolution-horizon assumes SE∝1/√years; SE·√n varies ~1.65× across
  disjoint sub-windows, so the year counts are order-of-magnitude (good to a factor of ~1.6–2.7×).
- **Easier baseline:** tested vs 50/50 ≡ buy&hold, not the recommended 60/40 equity/bond. A paired
  bootstrap vs 60/40 (handling IEF's ~2002 start so the early-2000s leg isn't silently 60/40-cash)
  is the recommended follow-up.
- **One-sided conservatism:** the power apparatus uses a two-sided 5% test; the economic question
  ("does active *beat* static?") is one-sided, which would need ~79% of the reported years — the
  two-sided figures are therefore conservative against the underpowered caveat.
- **Data:** Window B/C use ^GSPC (price-only, no dividends) — its ~0.37 Sharpe is dividend-light and
  not directly comparable to Window A's `auto_adjust` total-return Sharpes; the omission is
  conservative against the active leg. `auto_adjust` re-scaling is split/dividend-neutral for the
  `close[d]/MA[d]` entry gate, so it is leak-safe. Exact reproduction requires the cached `/tmp` CSVs
  as of the stated fetch date (END hardcoded 2026-06-20).
- **SE seed-stability (checked):** Window-B SE across seeds {0,1,2,3,42} ranges 0.148–0.153 (~3%);
  B=20000 gives 0.152. Every downstream power figure keys off this single SE and is stable to ~3%.

## Reproduce

```
venv/bin/python tools/power_study.py                 # all three windows + verdict
venv/bin/python tools/power_study.py --json out.json # full result dict
```
