# Study #15 — Is There a Regime-Agnostic Ballast?

**Artifact:** [`tools/ballast_blend_study.py`](../../tools/ballast_blend_study.py) · **Reproduce:** `venv/bin/python tools/ballast_blend_study.py` (`--selfcheck` verifies the blend identities and duration ordering)
(deterministic, seed=0; imports study #13's exact data build and caches — month-end ^GSPC + Shiller dividend-yield equity TR, exact constant-maturity Treasury zeros, ^IRX cash, FRED CPI; byte-reproducible; JSON via `--json`)
**RESEARCH_WEB nodes:** E39 (the study) · F49 (the finding) — resolves [[H43]]; the direct follow-on to [[F46]]'s cut C, which showed the 7yr bond leg and T-bill cash each win one correlation regime and lose the other.
**Status:** verdict **HOLDS — sharpened by a 3-lens skeptic panel** (data-construction · statistics · interpretation: **1 CONFIRMED, 2 QUALIFIED, 0 REFUTED**, all reproduced; pole rows verified to reproduce study #13's cut C exactly), with corrections **folded in**: (1) the 50/50-by-weight z2/z10 barbell is duration **6.0**, not 7.0 — ~90% of its neg-era shortfall was that gap, so a **duration-matched 37.5/62.5 barbell (Macaulay exactly 7.0)** was added and now carries the curve-shape read (it is statistically identical to the 7yr pole in the neg era: ΔSh CI [−0.06,+0.06], ΔmaxDD [−1.5,+0.3]); (2) the headline is scoped to **fixed *nominal*-Treasury ballasts** (real/short ballast — TIPS — is study #14's question, answered there in the negative for marked-to-market sleeves), and the curve-shape conclusion is stated as **absence of evidence at one matched curve point**, not proof shape never matters; (3) this doc's draft superlative ("the 50/50 posts the best full-sample excess Sharpe") was **factually wrong** — the unmatched barbell prints 0.507 — and is corrected below to the stronger, true statement; (4) near-tolerance real-DD failures (<2pp) are flagged **bootstrap-fragile** (P(gap≤1pp) 0.36–0.55) and each candidate's verdict is documented as resting on its robust legs; the knife-edge 25/75 neg-era Sharpe line is not cited standalone; (5) the panel verified the dominance verdict and minimax winner are **proxy-robust** under study #13's coupon-honest legs (individual margins and the 2nd/3rd regret order are not); (6) the poles' own worst regret (**1.00 by construction**) is now printed as the baseline that makes 0.49 legible; dead code removed.

## The Question

Study #13 left the product guidance with an uncomfortable either/or: the 7yr Treasury leg wins the negative-correlation era (2000–2021) on *every* metric, cash wins the positive-correlation/inflation era on real drawdown — and each loses badly in the other regime. Since regime timing is off the table (eras are known ex post, and this program has repeatedly shown timing doesn't survive honest benchmarks), the remaining question is **composition**:

> **Does any *fixed nominal-Treasury* ballast — a cash/bond blend or a duration barbell — weakly dominate both poles across both correlation regimes? Or is the ballast choice an irreducible regime bet?**

Either answer is the finding. Pre-registered reads (in the tool docstring): (1) **weak dominance** = in *both* decision eras, not significantly worse than that era's *best* pole on excess Sharpe and nominal maxDD (paired block bootstrap, block=12m, B=5000, seed=0), and within 1pp of it on real maxDD; (2) if nothing dominates, the constructive output is the **minimax-regret** ballast (worst normalized shortfall vs the era-best pole in pole-gap units); (3) "not significantly worse" is absence-of-harm — any dominance verdict would be a TOST candidate, not a settled edge; (4) the barbell tests curve positioning — after the panel, at *matched* duration (37.5/62.5 z2/z10 = Macaulay 7.0).

## Results

**The decision eras (40% equity + 60% ballast):**

| era | ballast | Sh(excess) | maxDD% | realDD% |
|---|---|---:|---:|---:|
| pos-corr 1962–1999 | 7yr zero pole | 0.39 | −18.9 | −40.8 |
| pos-corr 1962–1999 | **cash pole** | 0.45 | **−14.0** | **−27.1** |
| pos-corr 1962–1999 | 50/50 cash+z7 | 0.43 | −16.2 | −30.3 |
| pos-corr 1962–1999 | barbell 37.5/62.5 (dur 7.0) | 0.41 | −18.4 | −40.0 |
| neg-corr 2000–2021 | **7yr zero pole** | **0.87** | **−16.2** | **−16.7** |
| neg-corr 2000–2021 | cash pole | 0.46 | −23.1 | −24.3 |
| neg-corr 2000–2021 | 50/50 cash+z7 | 0.69 | −19.1 | −20.4 |
| neg-corr 2000–2021 | barbell 37.5/62.5 (dur 7.0) | 0.87 | −16.6 | −17.3 |

**Dominance test (read #1) — every candidate FAILS, each on at least one robust leg:**

- **25/75 cash-z7**: pos-era real maxDD **8.6pp** deeper than cash (bootstrap CI on the gap excludes the 1pp tolerance). Its neg-era Sharpe line is knife-edge (CI upper −0.01, flips at block=24/seed=1) and is not cited standalone.
- **50/50 cash-z7**: neg-era excess Sharpe significantly below z7 ([−0.34,−0.04], robust across 9 block×seed combos); pos-era real DD 3.2pp deeper than cash.
- **75/25 cash-z7**: neg-era Sharpe far below z7 ([−0.52,−0.11]); its pos-era real-DD miss (1.2pp vs 1pp) is within noise and not load-bearing.
- **barbell (both weightings)**: pos-era real maxDD 10.0–12.9pp deeper than cash — it *is* bond-pole behavior where bonds fail. The **duration-matched** barbell is statistically identical to the z7 pole in the neg era (ΔSh [−0.06,+0.06], ΔmaxDD [−1.5,+0.3]): at this matched curve point, **shape adds nothing beyond the duration level** (absence of evidence at one point, per read #3's own caution — not a theorem).

**Minimax regret (read #2), against the poles' baseline of 1.00 by construction:** the **50/50 cash+z7** blend minimizes worst-case normalized regret at **0.49** — it *halves* the worst-case regime bet — ahead of 25/75 (0.71), the unmatched barbell (0.73), 75/25 (0.75), and the matched barbell (0.94, pole-like as expected). The statistics lens verified the ranking is robust: 50/50 wins in ~95% of bootstrap replicates of the full regret table.

**Full-sample 1962–2026 (the diversification payoff):** *every* blend beats *both* poles on excess Sharpe — 0.489–0.507 vs the poles' 0.484 (z7) and 0.463 (cash) — with the unmatched barbell highest (0.507, partly its lower duration) and the 50/50 cash+z7 at 0.498 with a real drawdown 10.5pp shallower than the bond pole. Cross-regime diversification between the two ballast exposures is real and free; it just is not *dominance* in either regime alone.

## The Finding

**There is no regime-agnostic *fixed nominal-Treasury* ballast: the ballast choice is an irreducible regime bet.** No cash/bond blend or duration barbell weakly dominates both poles across the two correlation regimes — every composition concedes something significant to the era-best pole in at least one era, and the bootstrapped shortfalls move in opposite directions as the blend shifts, so no point on the line escapes both. At matched duration the barbell is indistinguishable from the bullet, so within nominal Treasuries the question is effectively **one-dimensional — how much duration** — and study #13's trade-off maps it (with study #14 closing the marked-to-market *real* ballast variant in the negative). The honest constructive answer is the **minimax-regret 50/50 cash+z7**: never the best, bounded-worst in both regimes at ~half the pole gap (vs the poles' own 1.00), one of the blends that beat *both* poles on full-sample excess Sharpe, and ~10pp shallower 64yr real drawdown than the bond pole. **This sharpens [[F46]]'s product guidance and [[D8]]'s honest fallback:** a product that refuses to bet on the correlation regime should hold the regret-minimizing blend and accept second-best everywhere; diversification *halves* the bet — nothing removes it.

## Verdict

**The verdict HOLDS.** The panel's strongest attack — rebuilding all bond legs with study #13's coupon-honest constructors and re-running the entire dominance/regret machinery — did not land: all ballasts still fail, the era-best poles are unchanged, and 50/50 still wins minimax regret (0.51 coupon-honest vs 0.49 zero-proxy). The statistics lens' demand that every FAILS be robust also survived: three near-tolerance real-DD lines are coin-flip fragile, but every candidate retains at least one failure that is stable across blocks 6/12/24 × seeds 0–2. What landed was construction and interpretation: the barbell needed duration-matching before the curve-shape read was valid (folded in — the matched instrument makes the null cleaner), the headline needed its nominal-Treasury scoping, and the draft doc's full-sample superlative was wrong (corrected to the stronger true statement: *every* blend beats *both* poles full-sample).

## Surviving Caveats

- Two decision eras = effectively two regime observations; the dominance failures are era-level statements.
- All bond legs are zero-coupon proxies; the verdict is proxy-robust (coupon-honest re-run) but per-era failure *margins* and the 2nd/3rd regret order are construction-fragile.
- The curve-shape null is one matched barbell at one duration point and weighting — absence of evidence, not proof.
- The 2yr leg's pre-1976 interpolation coarseness (understates its carry) biases *against* the barbell, which failed anyway.
- Monthly rebalancing, no transaction costs; blend-vs-pole turnover differences are small but nonzero.
- The 50/50's minimax-regret win is bootstrap-robust (~95%), but "not significantly worse" remains a low bar by design (read #3).
