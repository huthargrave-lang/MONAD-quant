# Study #14 — A TIPS Sleeve Inside the Static Mix: Does It Earn Its Place?

**Artifact:** [`tools/tips_sleeve_study.py`](../../tools/tips_sleeve_study.py) · **Reproduce:** `venv/bin/python tools/tips_sleeve_study.py` (`--selfcheck` verifies the data build)
(deterministic, seed=0; fetches SPY/IEF/TIP/STIP/VTIP/IEI daily prices once to `/tmp` (end pinned 2026-06-30) + FRED `CPIAUCSL` via study #12's cache; byte-reproducible; JSON via `--json`)
**RESEARCH_WEB nodes:** E38 (the study) · F48 (the finding) — resolves [[H42]]; tests the retail-implementable middle ground [[F46]] left open between "swap the whole bond leg to TIP" (helped only marginally in 2022) and "build a held-to-maturity TIPS ladder" (a forward claim).
**Status:** verdict **HOLDS — and got *stricter* after a 3-lens skeptic panel** (data-construction · statistics · interpretation: **1 CONFIRMED, 2 QUALIFIED, 0 REFUTED**, all reproduced), with every correction **folded into the tool**: (1) the same-size IEI duration control **undercorrects** (IEI ~4.5yr vs VTIP ~2.5yr duration), biasing the direct test *toward* a TIPS effect — a **duration-matched control (IEI sleeve sized ×5/3)** was added and is now the verdict-bearing comparison, under which *both* ΔmaxDD **and** ΔSharpe CIs include 0: the first draft's "inflation-carry hint" was a **residual-duration artifact and is withdrawn**; (2) the mechanical CI tests now use **unrounded** bootstrap percentiles (the ws=10 call had hinged on rounding a raw +0.0049 bound to +0.00) and knife-edge bounds are labeled block-sensitive; (3) a **vacuous selfcheck assertion** (`… or True`) was replaced with a real one; (4) the `sharpe_ok` acceptance branch was tightened to the pre-registration exactly (a latent, never-exercised loophole removed); (5) the **negative-corr 2004–2021 cut** (the sleeves' cost side) is now printed, disclosing the criterion drift from H42's original wording; (6) this doc's sweep table was regenerated from the tool's output (the draft had transcription errors the panel caught).

## The Question

Study #13 ([[F46]]) established TIPS as the structural mitigation of the bonds-don't-hedge regime — but only as a full bond-leg swap or a forward ladder. The obvious incremental implementation is a **sleeve**: carve 5–20% of the portfolio from the recommended conservative mix's nominal-bond leg (40% SPY / 60% IEF) into a TIPS fund. Study #5's gold lesson ([[F38]]/[[F39]]) is that candidate sleeves usually die under a fair paired bootstrap plus a family-wise correction — so this study runs exactly that discipline, with the addition [[F45]] demands: a **duration control**, because short-TIPS sleeves (STIP/VTIP, ~2.5yr duration) mechanically shorten the bond leg, and "shallower drawdown" claims are usually *just lower duration*.

> **Does any TIPS sleeve improve the recommended mix's drawdown in the one observed bonds-don't-hedge event (2022+) at the family-wise level, without hurting full-window Sharpe — and is any improvement more than duration-shortening?**

Pre-registered reads (in the tool docstring, before the numbers): (1) a sleeve is an **upgrade** only if its flip-cut nominal ΔmaxDD CI excludes 0 at the family-wise (×12) level AND full-window ΔSharpe is not significantly negative AND its flip-cut real maxDD is shallower; (2) anything weaker is at best an **OOS hypothesis** (the [[F39]] gold tier); (3) the flip era is a **single regime event (n=1)**; (4) "TIPS helped" may only be claimed if the TIPS sleeve beats a **duration-matched** nominal control in a direct paired test.

## Results

**Sleeve sweep, flip 2022+ cut, 10% sleeves (each variant vs the base on its own aligned window; flip-cut bases coincide):**

| sleeve | Sharpe | maxDD% | realDD% | base: Sharpe / maxDD / realDD |
|---|---:|---:|---:|---|
| TIP 10% | 0.531 | −18.7 | −23.0 | 0.515 / −19.0 / −23.3 |
| STIP 10% | 0.579 | −17.9 | −22.2 | 0.515 / −19.0 / −23.3 |
| VTIP 10% | 0.582 | −17.9 | −22.2 | 0.515 / −19.0 / −23.3 |
| IEI 10% (nominal duration control) | 0.546 | −18.6 | −22.8 | 0.515 / −19.0 / −23.3 |

**The cost side (negative-corr 2004–2021 cut, 20% sleeves — the regime where the nominal bond leg is the hedge):** STIP 20% cuts Sharpe 1.375→1.301 and deepens maxDD −11.1→−12.6; VTIP 20% likewise (1.296→1.248, −11.1→−12.7). The F46 regime trade-off repeats at sleeve scale: what helps in the bonds-don't-hedge event costs when bonds hedge. *(H42's original wording — "no significant Sharpe cost in the negative-corr cut" — is checked here; the pre-registered full-window criterion is the binding one, a drift the panel had us disclose.)*

**Paired bootstraps (sleeved − base), ΔmaxDD with family-wise ×12 band:**

| sleeve | cut | ΔSharpe 95% CI | ΔmaxDD 95% CI | ΔmaxDD fw×12 | P(shallower) |
|---|---|---|---|---|---:|
| TIP 10% | flip 2022+ | [−0.02, +0.07] | [−0.3, +1.2] | [−0.7, +1.8] | 82% |
| STIP 10% | flip 2022+ | [+0.02, +0.12] | [+0.2, +2.6] | **[−0.1, +3.5]** | 100% |
| VTIP 20% | flip 2022+ | [+0.04, +0.26] | [+0.4, +5.1] | **[−0.2, +7.0]** | 100% |
| IEI 20% (control) | flip 2022+ | [+0.02, +0.11] | [+0.3, +2.7] | [+0.0, +3.6] | 100% |

Applied mechanically: **UPGRADES: NONE** — every TIPS sleeve's family-wise band crosses zero (the panel's statistics lens verified this survives block 10/20/40 × seeds 0–2, and holds at stricter ×32 and even at the minimal ×6 family). STIP/VTIP at 10–20% qualify as unadjusted **OOS hypotheses**; full-duration TIP sleeves do nothing in the flip cut and their full-window point estimates lean mildly harmful (P(shallower) 17–20%).

**The duration-honesty test (read #4) — direct paired bootstraps, flip cut:**

| comparison | ΔmaxDD CI | ΔSharpe CI | reading |
|---|---|---|---|
| VTIP10 − IEI10 (same size, duration-**confounded**) | [+0.00, +1.40] *(knife-edge: raw lo +0.0049)* | [+0.006, +0.074] | biased toward TIPS by ~1.9yr of residual duration |
| **VTIP10 − IEI17 (duration-MATCHED)** | **[−0.20, +0.70]** | **[−0.009, +0.046]** | **indistinguishable from duration-shortening** |
| VTIP20 − IEI33 (duration-MATCHED) | [−0.40, +1.30] | [−0.018, +0.096] | indistinguishable from duration-shortening |

The matched control settles it: once the nominal sleeve sheds the *same* portfolio duration, nothing TIPS-specific survives — not drawdown, and not the Sharpe difference the confounded comparison had shown (the first draft called that a "carry hint"; the panel traced it to residual duration and it is withdrawn).

## The Finding

**No TIPS sleeve earns a place in the recommended static mix under the program's evidence bar — and the entire observed benefit of short-TIPS sleeves is duration-shortening in disguise.** Full-duration TIP sleeves do nothing (too correlated with the leg they replace). Short-TIPS sleeves improve the 2022+ cut with P(shallower)≈100% but fail the family-wise correction, cost Sharpe and drawdown in the negative-corr regime (the F46 trade-off at sleeve scale), and — decisively — are statistically indistinguishable from a duration-matched *nominal* Treasury sleeve on both drawdown and Sharpe: [[F45]]'s lesson, reconfirmed a third time. One scope limit cuts the other way: 2022+ was a **real-yield-driven** shock, the structurally worst case for marked-to-market TIPS (whose MTM hedges inflation-*expectations* moves) — so this null covers the tested mechanism, not every inflation event type. **Verdict for the product: unchanged.** The recommended mix gains nothing from a marked-to-market TIPS sleeve; the structurally honest TIPS exposure remains [[F46]]'s held-to-maturity ladder, where the inflation compensation is *realized* rather than marked.

## Verdict

**The verdict HOLDS and is stricter than the first draft.** The panel's strongest attack — that the IEI control undercorrects duration and the direct test was therefore biased *toward* TIPS — landed, and folding in the duration-matched control *removed the study's one positive sub-claim* (the carry hint) while leaving the headline (UPGRADES: NONE) untouched and now correct for the right reason. The statistics lens verified the family-wise NONE is stable across block sizes, seeds, and stricter family definitions; the interpretation lens confirmed the study refines F45/F46 rather than contradicting them and that the real-rate-shock scope note bounds the null honestly.

## Surviving Caveats

- The flip era is one regime event; every "helped in 2022+" statement is n=1.
- 2022+ was a real-yield shock — TIPS' MTM worst case; an inflation-*expectations*-led event is untested (the null is mechanism-scoped).
- Variant windows differ (TIP 2004+, STIP 2011+, VTIP 2013+); each is compared to the base on its own aligned window.
- The ×5/3 duration match is an approximation from fund durations (~2.5 vs ~4.5yr) — a small residual mismatch either way is possible.
- ETF total-return prices embed fund-level accruals (they match published fund returns to within bps); no direct CPI-indexation accounting. Monthly CPI is stamped at month-end before real-world publication — symmetric and measurement-only (orderings survive a 1-month-lag probe).
