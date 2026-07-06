# Study #13 — Bonds Don't Hedge: The Recommended Static Product Under the Positive-Correlation / Inflation Regime

**Artifact:** [`tools/correlation_regime_study.py`](../../tools/correlation_regime_study.py) · **Reproduce:** `venv/bin/python tools/correlation_regime_study.py` (`--selfcheck` verifies the data build)
(deterministic, seed=0; fetches month-end `^GSPC`/`SPY`, the Shiller monthly dataset (dividend yield + CPI cross-check), constant-maturity Treasury yields via study #12's cache, `TIP`/`IEF`, and FRED `CPIAUCSL`/`DFII10` once to `/tmp` caches, then offline; byte-reproducible across runs; JSON via `--json`)
**RESEARCH_WEB nodes:** E37 (the study) · F46 (the finding) — tests the central *surviving caveat* of studies #8/#9/#11/#12 ([[F41]]/[[F42]]/[[F44]]/[[F45]]): every drawdown/hedging claim in the program inherits the benign 2000–2021 **negative** stock-bond correlation, which flipped positive in 2022 and was positive for most of 1962–1999.
**Status:** verdict **HOLDS — strengthened and sharpened by a 4-lens skeptic panel** (data-construction · bond-math · statistics · economic-interpretation: **1 CONFIRMED, 3 QUALIFIED, 0 REFUTED**, all four reproduced every cited number), with every forced correction **folded into the tool, not caveated around**: (1) a **duration-proxy sensitivity cut** was added — the primary 7yr *zero* leg (duration 7.0) overstates the 1965–81 real-drawdown headlines by ~3–5pp vs an exact par-coupon leg (40/60 real DD −41% → −36/−37%; every variant stays far past the pre-registered −23% bar, and the correlation record is proxy-invariant); (2) the *same* sensitivity shows the tilt's positive-era **nominal-DD edge is stronger than first stated** (the zero's zero-straddling CI is a proxy artifact; coupon-honest CI **[+2.1,+11.5] excludes 0**); (3) cut C now covers **every era + the full sample** — the cash ballast *loses on every metric in 2000–2021*, so "shorter ballast" is a **regime trade-off**, scoped to the real-drawdown criterion, not an all-weather fix; (4) a genuinely **mis-signed sentence was fixed**: the conservative mixes' inflation-era real DD is *deeper* than 60/40's (−41/−42% vs −39%) — the tilt's drawdown edge **inverts** in real terms, which *strengthens* the qualification of F42; (5) the −41%-vs−23% anchor is now explicitly framed (realized-worst **real** vs F41's forward-MC median-worst **nominal** — a pre-registered materiality bar, not like-for-like; like-for-like nominal is *shallower*: −18.9%); (6) the 2000–2021 tilt CI is reported with a **family-wise (×12 Bonferroni) band** [−0.05,+0.45] — a replication of study #9's direction, not an independent edge; (7) cut E labels changed to **shares of overlapping windows** (~2–4 independent decades per era), the TIPS-ladder fix is labeled a **forward, amortized-cost-basis claim**, and the Shiller dividend column's mid-2023 end (frozen dy over the flip era) is disclosed.

## The Question

Every static product the D6 program landed on **leans on bonds**: the static 60/40 ([[F38]]) and the goal-optimal conservative ~30–40% equity tilt ([[F42]]) — which is 60–70% *bonds* — lean on bonds *hedging equity*; the held-to-maturity ladder ([[F45]]) is 100% bonds with a separate failure mode (inflation). Study #8's forward Monte-Carlo explicitly disclosed that it "inherits the benign −0.29 historical stock-bond correlation, which flipped positive (+0.12) in 2022; a bonds-don't-hedge regime deepens it" — and no study ever tested that regime. This one does, on 64 years of monthly data spanning both correlation regimes and the one genuine inflation shock the data contains (1965–1981).

> **When bonds stop hedging stocks — the historical norm, not the exception — does the recommended conservative static mix still dominate, what happens to its drawdown in the terms that matter (purchasing power), and what ballast actually survives that regime?**

Three reads were pre-registered in the tool's docstring before the numbers were computed: (1) F42's conservative-tilt direction is regime-robust only if the 30–40% mixes keep ≥ excess-Sharpe and shallower maxDD than 60/40 *in the positive-corr era* with bootstrap support; (2) the real-terms hole is material if the conservative mix's real drawdown in the inflation era exceeds the ~−23% figure F41 already called equity-like (F41's number is a forward-MC *median-worst nominal* decade DD — quoted as a materiality threshold, not a like-for-like comparison); (3) era conditioning is **descriptive** (eras are known only ex post) — this is a stress test of the recommendation, not a regime-timing strategy.

## Methodology — one consistent 1962–2026 monthly build

- **Equity total return:** month-end `^GSPC` price return + *lagged* Shiller dividend yield accrual (D/P from Shiller's own price level, so the scale cancels; forward-filled where the Shiller dividend column lags — it ends mid-2023, so the dy is frozen over the small-n flip era, inflating flip-era equity CAGR ~+0.26%/yr; no verdict claim rests on a flip-era return). Avoids Shiller's monthly-*average* price convention. **Validated:** corr **0.9984** to SPY total return on 1993–2026, CAGR 10.91% vs 10.81%; pre-1993 the panel independently verified `^GSPC` checkpoints, the D/P path, and a 1962–92 TR CAGR match (10.20% vs 10.19%) against a Shiller-price-based build.
- **Bond sleeve:** a perpetual constant-maturity **7-year zero-coupon Treasury**, exactly repriced monthly on a curve interpolated from `^IRX/^FVX/^TNX/^TYX` (study #12's exact zero math, same cache). **Validated:** corr **0.9815** to IEF on 2002–2026. **Duration honesty (panel-forced):** the zero holds duration 7.0 while a 1965–81 coupon book at that tenor had ~5.7–6.6, so a **par-coupon sensitivity cut** (exact annual-coupon CMT rolls; the IEF-like 7y+10y book validates *better*: corr 0.9924) brackets every inflation-era headline.
- **Cash:** 3-month T-bill accrual from `^IRX` (BEY-vs-discount bias ~0.2%/yr in high-rate eras, shown by the panel to be *conservative against* the study's own conclusions). **Inflation:** FRED `CPIAUCSL` (YoY corr **0.9992** to the independent Shiller CPI column). Every mix is scored **nominal and CPI-deflated (real)**, with **raw and excess-of-T-bill Sharpe**.
- **Eras** (fixed, disclosed; justified by detected sustained sign flips of the rolling 36m correlation at **2000-07** and **2022-08**; the panel verified conclusions are invariant to moving the boundaries to the detected dates ±12m): positive-corr 1962–1999 · inflation 1965–1981 (acute subset) · negative-corr 2000–2021 · flip 2022–2026 (small-n, point estimates only).
- **Inference:** paired block bootstrap (block=12 months, B=5000, seed=0) of the conservative tilt (30/70, 40/60) *minus* 60/40, per era, raw and excess, with a family-wise (×12) band on any positive claim. The panel verified CI conclusions are stable across block=6/12/24 and seeds 0–2.

## Results

### Cut A — the correlation record: the program's hedging assumption is the exception

| era | mean 36m stock-bond corr |
|---|---:|
| positive-corr 1962–1999 | **+0.30** (positive in **94%** of months) |
| inflation 1965–1981 | +0.23 |
| negative-corr 2000–2021 | **−0.33** (negative in 98% of months) |
| flip 2022–2026 | **+0.39** (now +0.41) |

Bonds reliably hedged stocks for ~22 of the last 64 years — exactly the 2000–2021 window every recommendation in this program was measured in. The regime flipped back positive in 2022 and remains there. (The record is proxy-invariant: identical to two decimals under the coupon bond leg.)

### Cut B — the mix sweep by era (nominal | real)

**Positive-corr era 1962–1999** — the tilt's excess-Sharpe case disappears; the *real* drawdowns are enormous:

| eq% | CAGR% | Sharpe | Sh(excess) | maxDD% | realCAGR% | realDD% |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 7.21 | 0.83 | 0.16 | −21.5 | 2.41 | **−49.4** |
| 30 | 8.95 | 1.05 | 0.35 | −14.4 | 4.07 | −42.5 |
| 40 | 9.48 | 1.06 | 0.39 | −18.9 | 4.58 | −40.8 |
| 60 | 10.48 | 1.02 | 0.44 | −27.6 | 5.54 | −39.2 |
| 100 | 12.20 | 0.86 | 0.45 | −42.8 | 7.18 | −52.0 |

Tilt bootstrap (40/60 − 60/40): **ΔSharpe(excess) CI [−0.14, +0.04]** (point negative) vs **[+0.06, +0.38]** in 2000–2021 — which itself softens to **[−0.05, +0.45] under a family-wise ×12 correction** (a replication of study #9's direction, not an independently established edge). The nominal ΔmaxDD edge is real: the zero-proxy CI narrowly straddles 0 ([−0.2, +10.8], P(shallower)=97%) but the **coupon-honest CI excludes 0** ([+2.1, +11.5], P=100%). In **1965–1981** the excess CI is [−0.21, +0.02] and *every* mix from 0% to 60% equity has **negative real CAGR** and a **−39% to −49% real drawdown**; the pure bond sleeve is the *worst* asset in the table.

**Negative-corr era 2000–2021** (for contrast — the regime F42 was derived in): 30/70 excess Sharpe 0.97 vs 60/40's 0.67, ΔmaxDD CI [+4.4, +28.8], P(shallower)=100%. Everything the program measured is true *there*.

### Cut C — the bond leg across every regime: a trade-off, not a winner

40% equity + 60% ballast:

| era | ballast | Sh(excess) | maxDD% | realCAGR% | realDD% |
|---|---|---:|---:|---:|---:|
| inflation 1965–1981 | 7yr Treasury zero | −0.12 | −18.9 | −1.76 | **−40.8** |
| inflation 1965–1981 | **T-bill cash** | +0.05 | −14.0 | **−0.07** | **−27.1** |
| neg-corr 2000–2021 | 7yr Treasury zero | **0.87** | **−16.2** | 4.30 | **−16.7** |
| neg-corr 2000–2021 | T-bill cash | 0.46 | −23.1 | 1.85 | −24.3 |
| full 1962–2026 | 7yr Treasury zero | 0.48 | **−18.9** | 4.16 | −40.8 |
| full 1962–2026 | T-bill cash | 0.46 | −23.1 | 3.17 | **−27.1** |

Cash rescues the inflation era (−41% → −27% real, real CAGR −1.8% → ~0%) and the 2022+ flip era — and **loses on every metric in 2000–2021**. Over the full 64 years the 7yr leg keeps the shallower *nominal* maxDD; the short ballast wins only on *real* drawdown. **Duration is a regime trade-off: poison when correlation is positive, the hedge itself when it is negative.** (The 2yr-zero row is corroborative only — its pre-1976 yield is a coarse interpolation that *understates* its carry, conservative against the shortening claim.)

### Cut C′ — duration-proxy sensitivity (panel-forced): the range of the headline

Inflation-era real maxDD by bond-leg construction: 40/60 = **−40.8%** (7yr zero, upper bound) / **−37.4%** (IEF-like coupon book) / **−35.7%** (7yr par coupon); bond-only = −49.4% / −44.5% / −40.8%. The cash-rescue size is ~14pp on the zero base, ~9pp coupon-honest. Every variant stays far past the pre-registered −23% bar; no conclusion flips.

### Cut D — TIPS: marginal in the observed 2022 event; structural only as a forward claim

2021–2023 shock: a 40/60 with **TIP** drew down −17.9% nominal / −22.2% real vs −18.8% / −24.2% with **IEF** — TIPS trimmed but did **not** escape the duration shock (standalone TIP marked down −22.5% *real*; 2022 raised real yields too). The structural fix is study #12's ladder built from TIPS: at the current **2.26% 10yr real yield** (`DFII10`, 2026-07), a held-to-maturity TIPS ladder locks ~2.3% **real** to maturity — addressing exactly the "−19% real in the 1970s" hole F45 left open. This is a **forward claim on 2026 real yields** (TIPS post-date 1997; untestable through the 1970s), holds only on F45's **amortized-cost / hold-to-maturity basis** (marked to market, TIPS drew down −22.5% real in 2021–23), and F45's term/liquidity/zero-upside costs carry over unchanged.

### Cut E — goal-odds by regime (shares of heavily overlapping 10yr windows — effective sample ~2–4 independent decades per era, *not* probabilities)

| mix | era of window start | share(nominal ≥ 3.75%) | share(real ≥ 0) | worst 10yr real CAGR |
|---|---|---:|---:|---:|
| 40/60 | positive-corr 1962–1999 (~4 decades) | 96% | **76%** | **−4.3%/yr** |
| 40/60 | inflation 1965–1981 (~2 decades) | 98% | **51%** | −4.3%/yr |
| 40/60 | negative-corr 2000–2021 (~2 decades) | 100% | 100% | +1.9%/yr |
| 60/40 | inflation 1965–1981 (~2 decades) | 98% | 55% | −3.9%/yr |

The **nominal** goal is regime-robust — high nominal yields made 3.75% nominal easy in exactly the era that destroyed real wealth. **Purchasing power is not:** roughly half the (heavily overlapping) decades that started in the inflation era ended with less real wealth than they began. Study #8/#9's forward Monte-Carlo inherited the benign correlation by construction; these are the numbers it could not see.

## The Finding

**The static mixes this program recommends lean on bonds hedging stocks, and that held in only ~22 of the last 64 years.** In the positive-correlation/inflation regime — 1962–1999, acutely 1965–1981, and again since 2022 — study #9's conservative tilt keeps its shallower-*nominal*-drawdown edge (real, and *understated* by the primary proxy: coupon-honest CI excludes 0), but its excess-Sharpe advantage disappears (CI straddles zero with a negative point estimate: more bonds *hurt* risk-adjusted returns when bonds don't hedge), and in **real terms the tilt's drawdown edge inverts**: the 40/60 lost **−36% to −41% of purchasing power** in 1965–1981 (depending on bond-leg construction) — *deeper* than 60/40's −39% zero-proxy figure at the same construction, monotonic in the bond share, and far past the −23% materiality bar pre-registered from F41 (a forward-MC median-worst *nominal* figure; like-for-like nominal, the 1965–81 40/60 drew down only −18.9%). What helps in that regime is **short duration** — a cash ballast cuts the real drawdown to −27% and holds real CAGR ≈ 0 — but that is **mitigation, not protection** (−27% is still deep), and it is a **regime trade-off, not an all-weather fix**: in 2000–2021 the cash ballast loses on every metric. Forward, the one construction that structurally addresses F45's inflation hole is a **held-to-maturity TIPS ladder** at ~2.3% real — a forward, amortized-cost-basis claim with F45's term/liquidity/zero-upside costs unchanged. The nominal income goal, ironically, is regime-robust (96–100% of 10yr windows cleared 3.75% *nominal* in every era) — because high nominal yields accompany exactly the inflation that destroys real wealth.

**What this changes:** [[D6]] **stands** — nothing here rehabilitates the active engine (this study contains no active strategy at all). But the *product guidance* is materially qualified: F41/F42's drawdown promises must be read as **nominal and negative-corr-regime-conditional**; F42's "weakly dominates on Sharpe *and* drawdown" holds only in the regime it was measured in (excess-Sharpe advantage vanishes positive-corr; real-DD advantage inverts); the honest all-weather answer on the *real-drawdown criterion* is **shorter and partly real ballast** (T-bills / TIPS ladder), accepting its clear cost in negative-corr regimes; and the "conservative mix" label must not be mistaken for inflation protection — in the one inflation regime on record, *every* bond-heavy mix lost purchasing power for a decade.

## Verdict

**The verdict HOLDS — 1 CONFIRMED, 3 QUALIFIED, 0 REFUTED** across the four skeptic lenses, all of which re-ran the tool, reproduced every cited number, and confirmed byte-reproducibility. The strongest refutation attempts and why they failed:

- **"The 1965–81 headline is a duration-proxy artifact"** (bond-math lens) — *partially landed, folded in.* An exact par-coupon rebuild softens −41% to −36/−37% but every variant stays far past the −23% bar, the correlation record is proxy-invariant, and the tilt's nominal-DD edge actually *strengthens* (CI excludes 0 coupon-honest). Now computed and printed by the tool (cut C′).
- **"The era-split CIs are artifacts of block length / seed / multiplicity"** (statistics lens) — *did not land:* every qualitative CI conclusion survives block=6/12/24 × seeds 0–2; the pos- and neg-era CIs don't overlap; the −41% survives a matched-horizon check (worst 10yr-window real DD identical). Forced instead: the family-wise band on the one "clearly positive" claim, and the cut C trade-off disclosure (both folded in).
- **"The correlation record leaks Shiller's averaged prices"** (data lens) — *did not land:* a price-only rebuild reproduces the record exactly; the ^IRX BEY bias and the era-boundary choices are conservative against the study; pre-1993 inputs verified against independent checkpoints.
- **"−41% real vs −23% nominal is apples-to-oranges"** (economics lens) — *partially landed:* the comparison is pre-registered and now explicitly framed as a materiality bar with the like-for-like nominal number (−18.9%) printed beside it. The lens also caught the one genuine factual error (the mis-signed "barely better than 60/40" sentence — the tilt's real-DD edge *inverts*), whose correction *strengthens* the finding.

## Surviving Caveats

- **One inflation regime in the sample.** 1965–1981 is a single historical episode, not a distribution; the 2022+ flip era adds a second, short, milder observation.
- **The bond-leg range is bracketed, not resolved:** the truth for a holdable 1965–81 Treasury book lies between the 7yr-coupon and zero constructions (−36% to −41% for the 40/60); duration is validated against IEF only on the low-coupon 2002–26 window.
- **Era conditioning is ex-post and descriptive;** nothing here is a tradable regime-timing signal, and the era-level Sharpe/DD contrasts inherit era length and macro differences beyond correlation alone.
- **Cut E windows overlap heavily** (~2–4 independent decades per era); the shares are descriptive, not probabilities.
- **The TIPS-ladder fix is forward-only** (2026 real yields; amortized-cost basis; no 1970s backtest possible) and keeps F45's term/liquidity/zero-upside costs.
- **The flip era (2022–2026) is small-n** with a frozen Shiller dividend yield (~+0.26%/yr equity CAGR inflation); its rows are point estimates only.
