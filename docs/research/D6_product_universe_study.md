# Study #11 — The Income Product Universe: Is There a Better Bond-Alternative Than the Static 60/40?

**Artifact:** [`tools/income_universe_study.py`](../../tools/income_universe_study.py) · **Reproduce:** `venv/bin/python tools/income_universe_study.py`
(deterministic; fetches the income/bond-alternative ETF universe once to `/tmp/income_universe_{adj,raw}.csv` — total-return **and** raw-price panels — then offline; reuses study #5's `static_product_study` simple-return primitives; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E35 (the survey) · F44 (the finding) · opens a NEW program (the *product universe*) that **builds on** the static-60/40 conclusion ([[D6]]) and the forward-expectation / goal-optimal-mix findings ([[F41]]/[[F42]]) it inherits.
**Status:** verdict **HOLDS and is strengthened**. A 4-lens skeptic panel (construction/leak · statistics/metric · fixed-income/domain · completeness) re-ran the code, hand-recomputed CAGR/maxDD/Calmar/corr for QYLD/PFF/TLT/BIL, and **all four confirmed the headline survives**. The panel raised **two *blocking* issues — both now RESOLVED by building new analysis into the tool, not by caveat**: (1) total-return accounting hid NAV erosion → added **cut C, a yield-vs-NAV decomposition** (QYLD's distributions contribute ~11%/yr of total return while its NAV falls −2.5%/yr; the spend-the-income drawdown is −42% vs the −25% reinvested figure); (2) JEPI was *named* as evidence but silently dropped by the apples-to-apples filter → added **cut D, a young-vehicles panel that actually measures JEPI** (and prints the excluded list). Five should-fixes folded into the verdict: the 40/60-Calmar edge **flips between windows** (lean the claim on maxDD + Sharpe, robust in both); QYLD's drawdown is **not** "equity-like" (−24.8% vs SPY −34% — calls cushion ~9pts, but still a worse income-per-DD trade than 60/40); the ladder claim **scoped** to IG/Treasury held-to-maturity (does not solve credit/reinvestment risk); MUB's worst drawdown was **Mar-2020 COVID**, not 2022; and "entire universe" softened to **"this liquid, survivor-only cross-section"** (omits BDCs/REITs/EM-debt/CEFs/MLPs). The dead `better`/`low_dd` scaffolding is now **wired into the verdict** (self-validating: "only 2 of 12 names beat 60/40 on Calmar").

## The Question

The whole active-vs-static arc (studies #1–#10, [[E25]]–[[E34]]) converged on one product: a **simple static equity/bond mix**. Study #8 ([[F41]]) then showed that mix clears the ~3.75% APY income goal more-likely-than-not but **fails the "near-zero drawdown" aspiration** (~−23% median worst drawdown — equity-like tail risk), and study #9 ([[F42]]) showed the goal-optimal weight is *more conservative* than 60/40 (~30–40% equity) but **still** can't make 3.75% a sure thing and **still** carries a double-digit drawdown.

That leaves one stone unturned: every study so far drew from the **same two-asset universe** (broad equity + Treasuries/AGG). The project's stated identity is a *high-yield bond-ETF alternative* — so the natural question the arc never asked is whether a **different asset universe** gets closer to "income **and** low drawdown" than SPY+AGG can:

> Is there an income / bond-alternative ETF — or category — (munis, IG/HY credit, preferreds, senior loans, options-income, dividend / low-vol equity, treasuries across the curve) that delivers a **better income-with-low-drawdown profile** than the static 60/40?

This is the **opening survey** of that universe — deliberately **descriptive, not inferential** (no bootstrap CIs; it maps what profiles *exist*, and the inferential follow-ups come after a candidate survives the survey).

## Methodology (read-only; simple-return product accounting; deterministic) — four cuts

- **Universe (25 tickers, category-labelled):** treasuries across the curve (BIL, SHY, IEF, TLT, TIP), aggregate/credit (AGG, LQD, HYG, JNK, BKLN), munis (MUB, VTEB), preferreds (PFF), dividend/quality (VIG, SCHD, NOBL, SPYD), low-vol (SPLV, USMV), options-income / covered-call (QYLD, XYLD, JEPI), conservative multi-asset (AOK), levered-blend (NTSX), and SPY as the equity reference.
- **Prices:** `yfinance auto_adjust=False`, keeping **both** `Adj Close` (total return — the income proxy, distributions reinvested) **and** raw `Close` (the price/NAV path). Fetched once and cached.
- **Benchmarks (every cut):** the program's **static 60/40** (0.6·SPY + 0.4·AGG, daily) and study #9's **conservative 40/60** (0.4·SPY + 0.6·AGG).

**Cut A — the survey.** Apples-to-apples: an asset is ranked in a window only if its inception is **at or before the window start** (no asset skips a crisis it didn't live through); the **excluded list is printed**. Per-asset total-return **CAGR / vol / maxDD / Calmar / Sharpe / corr_SPY** on aligned non-NaN returns. Two windows: **LONG 2008-2026** (GFC + 2020 + 2022; 13 assets) and **RECENT 2014-2026** (adds options-income / low-vol / muni; 21 assets). Ranked by **Calmar** (CAGR/|maxDD|).

> **Calmar is a ranking lens, not the objective.** It mechanically rewards near-cash — BIL tops both windows purely because its drawdown is ~0, not because it meets the income goal (its real return is ~0). The operative objective is **highest return *subject to* an acceptable drawdown**, which Cut B encodes directly.

**Cut B — the constrained objective.** For each drawdown ceiling (−15% "low-DD aspiration", −20%, and "shallower than the 60/40"), which non-equity assets clear **both** the ~3.75% income floor (historical TR CAGR ≥ `GOAL_APY`) **and** the ceiling? (LONG window.)

**Cut C — yield vs NAV erosion (the income-honest cut).** Total-return numbers hide that high-distribution funds erode principal. For each income vehicle: **price/NAV CAGR** (raw `Close`), **distribution yield** (approx., = TR_CAGR − NAV_CAGR — a CAGR-decomposition residual, not a literal cash payout rate), and the **spend-the-income drawdown** (raw-price maxDD an investor who *draws* the income actually feels) vs the **reinvested** maxDD the survey table reports. (RECENT window; a young-window variant covers JEPI/SPYD/NTSX.)

**Cut D — young vehicles (2020-06 onward).** The funds the apples-to-apples filter must drop (JEPI, SPYD, VTEB, NTSX) — measured over their short *common* life so they are not asserted unmeasured, with the same benchmarks over that window.

All metrics were **hand-recomputed independently** (QYLD/JNK/SCHD/JEPI cut C, JEPI cut D) and match the tool to the digit.

## Results

### Cut A — survey, LONG 2008-2026 (GFC + 2020 + 2022), ranked by Calmar

| tkr | category | CAGR% | vol% | maxDD% | Calmar | Sharpe | corrSPY |
|---|---|---:|---:|---:|---:|---:|---:|
| BIL | T-bill | 1.3 | 0.5 | −0.8 | 1.62 | +2.67 | −0.12 |
| SHY | treasury-short | 1.6 | 1.5 | −5.7 | 0.28 | +1.06 | −0.21 |
| VIG | dividend | 10.4 | 17.4 | −43.8 | 0.24 | +0.66 | +0.96 |
| MUB | muni | 3.1 | 5.3 | −13.7 | 0.22 | +0.59 | +0.15 |
| SPY | equity-bench | 11.3 | 19.8 | −51.9 | 0.22 | +0.64 | +1.00 |
| TIP | TIPS | 3.0 | 6.3 | −14.5 | 0.21 | +0.51 | −0.09 |
| LQD | IG-credit | 4.1 | 8.9 | −25.0 | 0.16 | +0.49 | +0.22 |
| AGG | agg-bond | 2.9 | 5.4 | −18.4 | 0.15 | +0.55 | +0.01 |
| HYG | HY-credit | 5.1 | 11.0 | −34.2 | 0.15 | +0.51 | +0.69 |
| JNK | HY-credit | 5.0 | 11.5 | −38.1 | 0.13 | +0.48 | +0.62 |
| IEF | treasury-7-10y | 2.9 | 7.0 | −23.9 | 0.12 | +0.44 | −0.29 |
| PFF | preferred | 4.6 | 18.6 | −64.4 | 0.07 | +0.34 | +0.59 |
| TLT | treasury-20y+ | 2.6 | 15.3 | −48.4 | 0.05 | +0.24 | −0.31 |
| **static 60/40** | SPY/AGG | **8.4** | 12.1 | **−33.2** | **0.25** | **+0.73** | — |
| **conservative 40/60** | | 6.7 | 8.6 | **−22.6** | 0.30 | +0.80 | — |

*Only **2 of 12** non-equity names beat the 60/40 on Calmar — BIL and SHY — both short-duration low-yield. Every high-yield name ranks below it.* (RECENT 2014-2026 reproduces the same picture; 60/40 Calmar 0.43, maxDD −21.7%, Sharpe +0.90, with the same category ordering. Full table in tool output.)

### Cut B — constrained objective: clear the ~3.75% income floor AND a low drawdown (LONG window)

| maxDD ceiling | clears the income floor **and** the ceiling |
|---|---|
| **< −15%** (low-DD aspiration) | **NONE** |
| **< −20%** (moderate) | **NONE** |
| shallower than 60/40 (−33%) | **only LQD** (CAGR 4.1%, maxDD −25%) — and bond-bull-inflated |

**The income floor and the low-drawdown ceiling are mutually exclusive across this universe.** Nothing clears 3.75% with even a moderate (<20%) drawdown; the *only* thing clearing the floor with a drawdown merely shallower than the (already deep) 60/40 is IG credit (LQD), whose historical CAGR is bond-bull-inflated and whose −25% 2022 drawdown is exactly the rate risk it carries forward.

### Cut C — yield vs NAV erosion (RECENT 2014-2026): total-return hides principal erosion

| tkr | category | TR_CAGR (reinv) | NAV_CAGR (price) | dist yield /yr | TR maxDD (reinv) | **SPEND maxDD** (draw income) |
|---|---|---:|---:|---:|---:|---:|
| QYLD | options-income | 8.4% | **−2.5%** | 11.0% | −24.8% | **−42.3%** |
| XYLD | options-income | 7.5% | −0.5% | 8.1% | −33.5% | −34.7% |
| JNK | HY-credit | 4.1% | −1.9% | 5.9% | −22.9% | −32.6% |
| PFF | preferred | 4.4% | −1.4% | 5.8% | −34.1% | −37.6% |
| HYG | HY-credit | 4.2% | −1.2% | 5.4% | −22.0% | −28.0% |
| BKLN | senior-loan | 3.6% | −1.6% | 5.2% | −24.2% | −31.3% |
| LQD | IG-credit | 3.1% | −0.4% | 3.5% | −25.0% | −29.4% |
| SCHD | dividend | 11.6% | **+8.1%** | 3.5% | −33.4% | −33.4% |
| MUB | muni | 2.8% | +0.2% | 2.5% | −13.7% | −14.4% |
| VIG | dividend | 11.8% | **+9.7%** | 2.1% | −31.7% | −31.7% |
| SPY | equity-bench | 13.9% | **+12.0%** | 1.9% | −33.7% | −34.1% |

**Every high-distribution name erodes principal; the dividend-growers and SPY grow it.** The "income" of QYLD/PFF/JNK is largely a return *of* capital, not *on* it — so the drawdown an income investor actually feels (spend basis) is materially *deeper* than the reinvested figure (QYLD −42% vs −25%; *deeper than SPY*). This **strengthens** the core finding: high distribution buys NAV erosion, not low drawdown.

### Cut D — young vehicles (2020-06 → 2026-06), measured over common life

| tkr | category | CAGR% | maxDD% (reinv) | **SPEND maxDD** | Calmar | corrSPY |
|---|---|---:|---:|---:|---:|---:|
| SCHD | dividend | 14.4 | −16.8 | −33.4* | 0.86 | +0.78 |
| **JEPI** | options-income | 10.6 | **−13.7** | **−20.0** | 0.78 | +0.87 |
| SPY | equity-bench | 17.6 | −24.5 | −25 | 0.72 | +1.00 |
| SPYD | dividend | 13.8 | −22.3 | −27 | 0.62 | +0.67 |
| USMV | low-vol | 9.1 | −17.9 | — | 0.51 | +0.85 |
| QYLD | options-income | 10.8 | −24.6 | — | 0.44 | +0.85 |
| NTSX | 90/60-levered | 13.1 | −31.3 | −32 | 0.42 | +0.94 |
| VTEB | muni | 1.5 | −12.6 | — | 0.12 | +0.19 |
| **static 60/40** | SPY/AGG | 10.7 | **−20.5** | **−21.6** | 0.52 | — |

*(\*SCHD spend-maxDD is the 2014-window figure; over 2020-26 its NAV grows so spend ≈ reinvested. The 60/40's spend-basis −21.6% is the like-for-like comparison for JEPI's spend −20.0%.)*

**JEPI is the one genuine counter-case — and it shrinks under scrutiny.** Over its short, single-regime life its *reinvested* drawdown is genuinely shallow (−13.7% vs the 60/40's reinvested −20.5% — a ~7pt edge) and, unlike QYLD, its NAV actually *grows* (+1.5%/yr). **But compared LIKE-FOR-LIKE on a spend-the-income basis the edge narrows sharply: JEPI's spend-basis maxDD −20.0% vs the 60/40's *own* spend-basis maxDD −21.6% — only ~1.6pt shallower** (most of the apparent cushion was a reinvested-basis effect, since the 60/40 also distributes income and erodes on a draw basis). So JEPI keeps a marginal edge, but over a benign window with no 2008-style event, with capped upside and high equity correlation (+0.87) — a flagged follow-up, not a refutation.

## The Finding

**There is no income / bond-alternative ETF — or category — in this liquid cross-section that delivers BOTH high income AND low drawdown; the two trade off across this cross-section, and no single vehicle dominates the static 60/40.** The high-distribution categories (preferreds, HY-credit, senior loans, options-income) all carry equity-like-or-worse drawdowns *and* erode principal — their spend-the-income drawdown is deeper than the reinvested figure, and their yield *is* compensation for the drawdown risk, not a way around it. The low-drawdown vehicles (T-bills, short Treasuries, low-vol equity) deliver the shallow drawdown only by giving up the income. **Nothing clears the ~3.75% income floor with even a moderate (<20%) drawdown — the floor and the ceiling are mutually exclusive.** The single lever that genuinely shifts the 60/40's drawdown is the one study #9 already found — **tilt more conservative** (the 40/60 is shallower-DD and higher-Sharpe in *both* windows) — at the cost of return, not a different asset. The one defensive counter-hint, JEPI, posts a shallow *reinvested* drawdown over a benign single-regime window, but **on a like-for-like spend basis its edge narrows to ~1.6pt** (−20.0% vs the 60/40's own −21.6%). **The product-universe search therefore does not change the program's conclusion: the honest income product is a static equity/bond mix, weighted conservatively for this goal, and there is no income-ETF shortcut to "income with near-zero drawdown."**

**The one structural escape this ETF survey cannot capture — and the recommended next study — is a held-to-maturity bond LADDER of investment-grade / Treasury defined-maturity ETFs** (iShares iBonds, Invesco BulletShares). A *perpetual-maturity* bond ETF (every fund here) marks to market forever, so a rate shock is a permanent-looking drawdown — exactly why AGG/LQD/TLT showed −18/−25/−48%. A bond *held to maturity* returns par regardless of the interim price path, converting **duration** drawdown into realized yield (pull-to-par realizes entry YTM). It does **not** eliminate credit/default risk (a HY or preferred ladder carries credit/solvency risk a Treasury ladder does not — PFF/JNK's drawdowns here mixed rate *and* credit), reinvestment risk (matured rungs reinvest at prevailing yields), or interim marks if sold early. The **prerequisite** follow-up is generalizing Cut C's yield-vs-NAV decomposition — the ladder is the structural version of measuring income and principal *separately* rather than marking total-return to market.

## Verdict

**The verdict HOLDS and is strengthened by the additions the panel forced.** All four skeptic lenses independently confirmed the headline survives; the construction lens hand-recomputed CAGR/maxDD/Calmar/corr and found the mechanics exact (window filter correct, simple-return accounting right, the prior `+nan` correlation bug fixed). The two *blocking* issues were not waved away but **built into the tool**:

- **(blocking → resolved) Total-return hid NAV erosion** → Cut C now decomposes yield vs NAV and reports the spend-the-income drawdown. It *strengthens* the finding: QYLD's 11%/yr distribution is largely principal (NAV −2.5%/yr; spend-maxDD −42%, deeper than SPY).
- **(blocking → resolved) JEPI asserted but unmeasured** → Cut D now measures JEPI/SPYD/VTEB/NTSX over their common life and prints the excluded list. JEPI's low-drawdown edge is ~7pt on a reinvested basis but narrows to ~1.6pt when compared like-for-like on a spend basis (−20.0% vs the 60/40's own −21.6%) — it survives but is much smaller than the reinvested figure suggests.

The should-fixes are folded as honesty corrections, none touching a finding:

- **(corrected) 40/60-beats-60/40 is window-robust on maxDD + Sharpe, not Calmar** (the Calmar edge leads in the GFC window, 0.30 vs 0.25, but *trails* in 2014-2026, 0.38 vs 0.43). The verdict now leans on maxDD/Sharpe, which favor 40/60 in both windows.
- **(corrected) QYLD's drawdown is not "equity-like"** — −24.8% vs SPY −34% (calls cushion ~9pts); but it is still a worse income-per-drawdown trade than the 60/40 (deeper maxDD, lower Calmar/Sharpe, capped upside), so "no better than 60/40" stands.
- **(corrected) ladder claim scoped** to IG/Treasury held-to-maturity, with credit/reinvestment/early-sale risks stated explicitly.
- **(corrected) MUB's worst drawdown was the Mar-2020 muni-liquidity crunch**, not the 2022 rate shock; TLT's −48% trough was the 2022-23 hike cycle. The rate-sensitivity thesis is unaffected.
- **(disclosed) Survivor-only liquid cross-section** omitting BDCs/REITs/EM-debt/CEFs/MLPs; "entire universe" softened. **No bootstrap CIs** (descriptive survey) — near-neighbor orderings (40/60 vs 60/40 Calmar) are within sampling noise.
- **(fixed) dead `better`/`low_dd` scaffolding wired into the verdict** so the no-dominance claim ("only 2 of 12 beat 60/40 on Calmar") is derived from the table, not asserted.

## Surviving Caveats

- **Descriptive survey, not an inferential test.** Single historical path per asset, **no bootstrap CIs / no equivalence test** — the rankings are point estimates and near-neighbor orderings (e.g. 40/60 vs 60/40 Calmar, which flips between windows) are within sampling noise. The program's inferential machinery applies once a candidate is chosen.
- **CAGR is bond-bull-inflated and forward-unrepresentative** (study #8/[[F41]]): every bond/credit CAGR rode a secular bond bull that will not repeat — forward, a bond's return ≈ its entry yield (~4–5% in 2026). The **drawdown + correlation** profile is the durable signal; the historical return ranking is not.
- **Calmar mechanically favors near-cash** (BIL tops both windows) — a property of the metric, not a recommendation. Cut B encodes the real constrained objective (return *subject to* an acceptable drawdown).
- **Survivor-only, liquid-ETF cross-section.** Dead income vehicles are absent (biasing the high-yield categories *favorably*), and whole high-distribution categories (BDCs, REITs, EM debt, CEFs, MLPs) are out of scope — so "no income ETF beats 60/40" is a claim about *this* cross-section.
- **Total return is the survey's default basis; Cut C is the income-honest correction** but covers only the distribution-heavy names. For an income product the yield-vs-principal split (Cut C) matters more than the reinvested table (Cut A).
- **Young-vehicle window is benign and single-regime** (2020-26, one real drawdown) — JEPI/SCHD's shallow drawdowns are untested against a 2008-style event, and both are highly equity-correlated.
- **The ladder recommendation is a hypothesis, not a result** — untested here; it converts *duration* drawdown into realized yield but does not solve credit/default, reinvestment, or early-sale risk.

## Reproduce

```
venv/bin/python tools/income_universe_study.py                 # 4 cuts (survey / constrained-objective / yield-vs-NAV / young) + verdict
venv/bin/python tools/income_universe_study.py --json out.json # full result dict
venv/bin/python tools/ctx.py web D6                            # the static-allocation conclusion this builds on
venv/bin/python tools/ctx.py web F41                           # forward 60/40: clears income goal, fails drawdown goal
venv/bin/python tools/ctx.py web F42                           # goal-optimal mix is more conservative than 60/40
```
