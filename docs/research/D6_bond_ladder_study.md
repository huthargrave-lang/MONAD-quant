# Study #12 — The Held-to-Maturity Bond Ladder: The Structural Escape, and What It Really Costs

**Artifact:** [`tools/bond_ladder_study.py`](../../tools/bond_ladder_study.py) · **Reproduce:** `venv/bin/python tools/bond_ladder_study.py` (`--selfcheck` verifies the bond math)
(deterministic; fetches constant-maturity Treasury yields `^IRX/^FVX/^TNX/^TYX`, defined-maturity ETF prices, and FRED `CPIAUCSL` once to `/tmp/bond_ladder_*.csv`, then offline; **exact zero-coupon bond math throughout** — ladder *and* foils; reuses study #5's `static_product_study` primitives; JSON via `--json`)
**RESEARCH_WEB nodes:** E36 (the study) · F45 (the finding) · **capstone of the product-universe program** — tests the one structural escape study #11 ([[F44]]) flagged; **builds on** [[F44]]/[[F41]] and the static-allocation conclusion ([[D6]]).
**Status:** verdict **HOLDS — and is materially more honest after a 3-lens skeptic panel** (bond-math/construction · fixed-income interpretation · empirical/completeness), all three of which **confirmed the headline survives** while forcing real corrections, **all folded into the tool, not caveated around**: (1) the realized basis is now **amortized-cost accounting** and the 0% drawdown is labelled **definitional** (no marks + non-negative nominal yields), not a derived pull-to-par result; (2) the constant-maturity ETF foils are now priced with **exact zero math** like the ladder (the 10yr's drawdown corrects −34.2% → **−31.5%**, removing an apples-to-oranges inflation of the ladder's edge); (3) a **duration-matched 5yr ETF** control is added (−14.05% ≈ the ladder's MTM −13.69% — so the MTM reduction is *just lower duration*, not a ladder property); (4) the empirical cut adds **SHY/IEI duration controls** (SHY beat the 2020 ladder on *both* return and drawdown); (5) "matured to par" is corrected to the observable **NAV-volatility collapse** (the levels are total-return prices, not par); (6) a **CPI-deflated REAL drawdown** is added and surfaced in the headline — the realized ladder lost **−19.1% of purchasing power** in the 1970s despite 0% nominal; (7) it is stated plainly that **no empirical ladder actually cleared 3.75%** — floor-clearing is a forward claim only.

## The Question

Study #11 ([[F44]]) closed the income-ETF universe with one stone unturned: every fund it surveyed is *perpetual-maturity* — it marks to market forever, so a rate shock is a permanent-looking drawdown, and **no** income ETF delivered income with low drawdown. The single structural escape it flagged, untested, was a **held-to-maturity bond ladder**: a bond *held to maturity* pulls to par regardless of the interim price path, converting **duration** drawdown into realized yield. This study tests that thesis — and quantifies what it *costs*, because "zero drawdown" from a ladder is partly an accounting choice and a careful analysis must not oversell it.

> **Is a held-to-maturity bond ladder the first construction in the program to deliver income with near-zero drawdown — and if so, what is the catch?**

## Methodology — two complementary cuts (read-only, deterministic)

**Cut B — synthetic zero-coupon Treasury ladder, 1962-2026 (exact bond math).** A rolling **1–10yr** zero-coupon ladder built from constant-maturity Treasury yields, interpolated linearly to a 1–10yr curve. A zero of maturity `T` at yield `y` is priced **exactly** as `(1+y)^(−T)`. Each month every rung reprices as its remaining maturity rolls down by 1/12yr; at maturity the par cash reinvests into a fresh 10yr rung. Scored on **two bases**:
- **Mark-to-market** — the rungs' current prices (what your statement shows; the basis on which you'd realize a loss if forced to sell).
- **Realized (amortized-cost / hold-to-maturity)** — each rung's wealth accretes at its **locked entry yield** `(1+y₀)^dt`, never marked to market; at maturity it pulls to par. Its drawdown is **0 by construction** — amortized cost never marks down and nominal yields are ≥0, so it can *never* show a drawdown regardless of rate history. That is the hold-to-maturity property (accrue to par, don't mark), **but it is an accounting choice, not a market outcome.**

Benchmarked against **two perpetual constant-maturity ETFs priced with the same exact zero math** — a **10yr** (long foil) and a **duration-matched 5yr** (the control that isolates the *pull-to-par* effect from the mere *lower-duration* effect). A **CPI-deflated real-drawdown** is computed for the realized basis (FRED `CPIAUCSL`). Bond math unit-tested (`--selfcheck`).

**Cut A — empirical defined-maturity ETFs through the 2022 rate shock.** Real **iBonds Treasury** (IBTx, 2020+) and **iBonds/BulletShares IG corporate** (IBDx/BSCx, 2018+) ladders vs **duration controls SHY (1–3y) / IEI (3–7y) / IEF (7–10y)**, **LQD**, and the static **60/40** — including three funds (**IBTF/IBDQ/BSCP**) that **matured in Dec-2025**.

## Results

### Cut B — synthetic 1–10yr Treasury ladder, 1962-2026 (exact math throughout)

| basis | CAGR% | vol% | maxDD% |
|---|---:|---:|---:|
| ladder **MARK-TO-MARKET** | 5.72 | 5.56 | **−13.69** |
| ladder **REALIZED (amortized-cost / hold-to-maturity)** | 5.78 | 0.71 | **0.00** *(definitional)* |
| duration-matched **5yr ETF** (perpetual) | 6.53 | 6.06 | −14.05 |
| constant-maturity **10yr ETF** (perpetual) | 6.36 | 10.39 | −31.48 |

| rate shock | ladder MTM | 5yr ETF | 10yr ETF | ladder **REALIZED (nominal)** |
|---|---:|---:|---:|---:|
| 1970–1984 | −12.58% | −14.05% | −31.48% | **0.0%** |
| 2021–2023 | −12.36% | −12.23% | −24.81% | **0.0%** |

**The realized 0% drawdown hides a −19.1% REAL drawdown.** CPI-deflated, the realized ladder lost **−19.13% of purchasing power** in the 1970s–80s inflation shock — comparable to the mark-to-market drawdown it is praised for avoiding. Pull-to-par protects nominal par, **not** real value, and the locked entry yield is exactly what inflation erodes.

Three facts, all essential:
1. **The realized (amortized-cost) drawdown is 0% — but definitionally so**, not as a contingent result that "survived" rate history. It is what hold-to-maturity accounting *is*.
2. **The mark-to-market drawdown reduction is just lower duration.** The ladder's MTM drawdown (−13.69%) is essentially identical to a **duration-matched 5yr ETF's (−14.05%)** — a plain short-bond ETF (SHY) delivers the same. The ladder's *unique, non-duration* property is **only** the realized pull-to-par: the 5yr ETF is perpetual and never escapes its mark, while every ladder rung returns to par.
3. **The "low drawdown" is nominal only** — see the −19.1% real drawdown above.

### Cut A — empirical defined-maturity ETF ladders + duration controls (through 2022)

| construction | CAGR% | maxDD% | Sharpe |
|---|---:|---:|---:|
| Treasury iBonds ladder (2020+) | −0.22 | −15.8 | −0.04 |
|  vs **SHY** const-mat 1–3y (~1.9yr dur) | **+1.47** | **−5.7** | +0.80 |
|  vs IEI const-mat 3–7y (~4.5yr dur) | −0.07 | −14.6 | +0.01 |
|  vs IEF const-mat 7–10y (~7.5yr dur) | −1.91 | −23.9 | −0.23 |
|  vs static 60/40 | 9.94 | −20.5 | +0.93 |
| IG corp ladder iBonds+Bullet (2018+) | **3.86** | −17.5 | +0.69 |
|  vs LQD constant-maturity IG | 2.99 | −25.0 | +0.35 |

**Duration-honest, like cut B:** the ladder's −15.8% is close to IEI's −14.6% and far shallower than IEF's −23.9% — *but SHY (~1.9yr, perpetual, no pull-to-par) drew down only −5.7% and out-returned it.* **A plain short-Treasury ETF beat the 2020 ladder on both return and mark-to-market drawdown.** The ladder's shallower-than-IEF drawdown is duration, not structure.

**The ladder-unique empirical signal is the pull-to-par at maturity** — the *NAV-volatility collapse* (not "par": the levels are total-return prices). IBTF's annualized vol fell **2.62% over its life → 0.35% in its final month** as duration→0, converging to a stable terminal value; its 2022 MTM trough (−9.5%) became moot at maturity (same for IBDQ/BSCP). No perpetual ETF, however short, has this.

The Treasury ladder's **−0.2%/yr is the entry-yield cost made concrete** — it was bought at 2020's record-low yields and faithfully locked them in. The IG ladder (started 2018 at higher yields) returned **3.86%/yr, beating LQD with a shallower drawdown**.

## The Finding

**A held-to-maturity bond ladder is the one structural escape study #11 flagged, and it works — but a careful read shows it is narrower than it first looks, and it trades risks rather than eliminating them.** Its realized (amortized-cost / hold-to-maturity) drawdown is ~0 at a return ≈ entry yield, confirmed in a 64-year zero-coupon simulation and on real iBonds/BulletShares ladders through 2022. **But:** (1) that realized 0% is **definitional** (amortized-cost accounting never marks to market; nominal yields ≥0), not a market outcome; (2) its mark-to-market drawdown reduction is **just lower duration** — a duration-matched perpetual short ETF (5yr / SHY) draws down the same with no ladder structure, and empirically SHY *beat* the 2020 ladder on both return and drawdown; the ladder's *only* unique property is the pull-to-par at maturity (a realized escape no perpetual ETF has); (3) the 0% is **nominal only** — CPI-deflated, the realized ladder lost **−19.1% of purchasing power** in the 1970s; (4) it clears the ~3.75% income floor only as a **forward claim** on 2026 entry yields — **no ladder in this study actually cleared it** on realized return (the 2020 Treasury ladder −0.2%/yr; the IG 2018 ladder 3.86% only ~at the floor).

**It converts MARKET/drawdown risk into TERM + REINVESTMENT + REAL (inflation) risk + zero upside.** For an income investor who can commit capital to a defined horizon, never be a forced seller, and accept inflation risk, it is the honest *nominal* bond-alternative the active engine and every perpetual-maturity income ETF never were. For one who needs liquidity, upside, or real (inflation-protected) preservation, the drawdown is as real as any ETF's. **This is the capstone of the universe program: the honest "income with low drawdown" product exists — but only as a held-to-maturity Treasury/IG ladder, only in *nominal* terms, only as a *forward* expectation, and only by paying in term commitment, forgone upside, and inflation risk — not as a free structural win.**

## Verdict

**The verdict HOLDS.** All three skeptic lenses confirmed the headline survives; the bond-math lens verified the simulation is correct (seamless roll-down, no look-ahead, exact pricing) and reproduced every number. The corrections they forced were folded into the tool and *strengthen* the honesty rather than touching the conclusion:

- **(should-fix → fixed) Realized basis reframed to amortized-cost; the 0% is definitional.** The prior `mean(carry)` realized series was carry-only accounting (a carry-only 10yr ETF also shows 0% DD); now it is an explicit amortized-cost wealth path compounding at locked entry yields, labelled definitional — the honest mechanism, not a derived result.
- **(should-fix → fixed) Exact constant-maturity pricing.** The foils used a duration-linearization that *overstated* their drawdown (10yr −34.2% → exact −31.5%); the ladder's MTM-as-%-of-ETF corrects to ~43% (from ~40%). Conclusion unchanged, magnitude no longer flattering.
- **(should-fix → fixed) Duration honesty made explicit, cut A + cut B.** A duration-matched 5yr ETF (−14.05%) ≈ the ladder's MTM (−13.69%); empirically SHY (−5.7%) beat the 2020 ladder. The MTM reduction is duration, not a ladder property; only the pull-to-par is unique.
- **(should-fix → fixed) "Matured to par" → NAV-volatility collapse.** The terminal levels are total-return prices, not par; the observable pull-to-par signature is the vol collapse (IBTF 2.62%→0.35%), which is what the writeup now claims.
- **(should-fix → fixed) Real (inflation) drawdown quantified and surfaced.** −19.1% of purchasing power in the 1970s, now in the headline and its own finding, not a footnote.
- **(should-fix → fixed) Floor-clearing stated as forward-only.** No empirical ladder cleared 3.75%; the claim rests entirely on 2026 entry yields.
- **(nits → fixed) Sim starts 1962** (drops the degenerate pre-1962 flat-curve months); geometric carry accrual; "linear in tenor" docstring; the 4→3-rung shrink after IBTF matures is disclosed.

No correction touched the core finding — the thesis (held-to-maturity converts duration drawdown into realized yield; the cost is term + reinvestment + inflation + no upside) is exactly what survives, now stated without overclaim.

## Surviving Caveats

- **The realized 0% is amortized-cost *definitional*, not a market outcome** — it assumes no marking and no forced sale; economic wealth is the mark-to-market value, which does draw down (−13.7%).
- **Most of the MTM drawdown reduction is just lower duration** (a duration-matched 5yr ETF / SHY draws down the same or less) — the ladder's distinctive feature is *only* the realized pull-to-par.
- **Nominal, not real:** the realized ladder lost −19.1% of purchasing power in the 1970s despite 0% nominal — pull-to-par protects nominal par, not real value.
- **No empirical ladder cleared 3.75%** (2020 Treasury −0.2%/yr; IG 2018 3.86% ~at floor); floor-clearing is a forward claim on 2026 entry yields.
- **Stylized model + single empirical cycle:** synthetic zeros (real ladders hold coupon bonds with reinvested coupons); curve interpolated from 4 points; the empirical window is one rate cycle of young funds, and the Treasury ladder shrinks 4→3 rungs after IBTF matures Dec-2025.
- **Treasury/IG only** — a credit/HY ladder still realizes defaults; locked entry yields carry **reinvestment risk** as rungs mature.

## Reproduce

```
venv/bin/python tools/bond_ladder_study.py             # synthetic + empirical cuts + verdict
venv/bin/python tools/bond_ladder_study.py --selfcheck # verify the zero-coupon bond math
venv/bin/python tools/bond_ladder_study.py --json out.json
venv/bin/python tools/ctx.py web F44                   # study #11: no perpetual-maturity income ETF works (this study's premise)
venv/bin/python tools/ctx.py web D6                    # the static-allocation conclusion this caps
```
