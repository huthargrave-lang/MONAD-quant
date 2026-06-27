# Study #9 — Goal-Optimal Equity/Bond Mix: Is 60/40 the Right Static Blend for THIS Goal?

**Artifact:** [`tools/weight_optimization_study.py`](../../tools/weight_optimization_study.py) · **Reproduce:** `venv/bin/python tools/weight_optimization_study.py`
(deterministic, seed=0; no network fetch — reuses study #8's panel-verified forward Monte-Carlo `forward_expectation_study.montecarlo_forward` and study #5's cached 2000 price universe; JSON via `--json out.json`)
**RESEARCH_WEB nodes:** E33 (the study) · F42 (the finding) · **refines** the forward-60/40 finding ([[F41]]) and the foundational goal ([[D4]]); **builds on** the go/no-go close ([[D6]]) and the 26yr confirmation ([[F25]]).
**Status:** verdict **HOLDS**. The RESULTS table reproduces to the digit (eq0:4.2%/0.62/52%/-13%/4% … eq40:5.3%/0.68/70%/-15%/2% … eq60:5.9%/0.51/67%/-23%/6% … eq100:7.0%/0.35/59%/-40%/19%; deterministic, seed=0). `blocking=false`, `verdict_holds=true`. No issue invalidates a finding. A 2-lens skeptic panel (methodology/reproduction; interpretation & honesty) confirmed the construct and the central honest caveat, and flagged **one material wording correction and three disclosure/framing gaps — all writeup-only** — folded below: (1) the unqualified word **"DOMINATED"** oversells a base-case-specific result — strict three-axis dominance survives the realized ~19-20% equity vol but shrinks to a near-tie at an assumed ~15% forward equity vol and flips at a wide forward ERP; (2) the equity leg is the **QQQ-tilted QID basket (~20% vol)**, never flagged; (3) the "~0.3%/yr less median CAGR" cost is **median-only** (it grows to ~1-2%/yr in the right tail); (4) the **Sharpe peak at ~20% equity is a diversification effect**, not just bond>equity Sharpe, so its location is correlation-dependent. The substance is unchanged.

## The Question

This study **REFINES, it does not contradict,** the program's static-60/40 recommendation. The whole arc — [[D6]]/[[F25]] (active engine has no risk-adjusted edge over a static blend), [[F37]] (no overlay reliably improves it), and [[F41]]/study #8 (the forward 60/40 clears the income goal more-likely-than-not but fails near-zero-DD) — *assumed 60/40 as the product weight* and never asked whether 60/40 is itself the right mix.

Study #8 (E32/F41) surfaced the load-bearing reason to re-open that: **forward**, equity is high-vol / modest-return (~7% at ~20% vol → forward Sharpe ~0.35) while a held-to-horizon bond earns a decent entry yield at low vol (~4.2% at ~7% vol → forward Sharpe ~0.62). So the **forward bond Sharpe EXCEEDS the forward equity Sharpe** — an asymmetry that did *not* hold over the realized 2002-2026 bond-bull window. Given the project's actual goal (clear **~3.75% APY** with the **shallowest drawdown**, [[D4]]/CLAUDE.md §1), is 60/40 equity-heavier than the low bar requires?

**This inherits study #8's SCENARIO framing: its inputs are explicit ASSUMPTIONS, not data.** Every probability and drawdown is conditional on the forward-return assumptions (equity 7% / bond 4.2% base case) and on the historical risk shape being a fair forward proxy.

## Methodology (read-only; reuses study #8's verified Monte-Carlo; deterministic, seed=0)

- **Historical legs (the only empirical part):** same cached price universe as studies #5-8 (no new fetch). Equity leg = equal-weight daily-rebalanced **QQQ/IWM/DIA** (`sps.equity_blend`); bond leg = **IEF** (`sps.simple_ret`); aligned via `concat().dropna()` and sliced `loc['2002-07-31':]` (6010 days, 2002-07-31→2026-06-18).
- **Weight sweep:** equity weight `w` over a 0%→100% step-5% grid. For each `w` the historical mix is the true historical blend `w·eq + (1−w)·bond` (so the mix keeps that allocation's realized vol, fat tails, drawdown shape, and the −0.29 stock-bond co-movement).
- **Per-mix forward Monte-Carlo (study #8's construct, reused verbatim):** `r_centered = r − r.mean() + ann_to_daily(fwd_mean)` with `fwd_mean = w·0.07 + (1−w)·0.042` — swaps each mix's mean to its forward expectation while preserving its risk shape, then block-bootstraps (BLOCK=20, 10yr=2520 steps, 5000 paths, seed=0) the forward distribution of 10yr CAGR and worst drawdown. Panel-verified: the 60/40 mix's annualized vol is identical before/after re-center (11.56%); only the mean is swapped (9.77%→5.73% ann). Forward Sharpe = `fwd_mean / realized_vol`.
- **Located:** the P(goal)-maximizing mix, the forward-Sharpe-maximizing mix, the 60/40 reference, whether any mix clears the goal reliably (P ≥ 0.80), and whether the goal-odds-optimal mix dominates 60/40 on all three axes (goal-odds, Sharpe, drawdown) at a lower equity weight.

**Reproduction (panel-verified):** rerunning reproduces every headline number deterministically; the stored `weight_opt.json` matches stdout exactly.

## Results

### Forward goal-odds vs drawdown frontier (base case: equity 7% / bond 4.2%; goal = 10yr CAGR ≥ 3.75%)

| eq% | fwd% | fwdSharpe | P(goal) | medCAGR | medMaxDD | P(10yr loss) | |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 4.2 | 0.62 | 52% | 3.8% | −13% | 4% | |
| 20 | 4.8 | **0.83** | 65% | 4.5% | −11% | 1% | ← forward-Sharpe max |
| 40 | 5.3 | 0.68 | **70%** | 5.0% | −15% | 2% | ← P(goal) max |
| 60 | 5.9 | 0.51 | 67% | 5.3% | −23% | 6% | ← 60/40 |
| 100 | 7.0 | 0.35 | 59% | 5.1% | −40% | 19% | |

The frontier peaks **conservative**: P(goal) maxes at ~40% equity (70%), forward Sharpe at ~20% equity (0.83 — higher than pure bonds' 0.62). Adding equity past ~40% buys deeper drawdown (−15% → −40%) and higher loss-risk (2% → 19%) for *less* goal-odds, because the low 3.75% bar does not need the equity upside.

### The dominance finding (base case)

At the base-case assumptions and the **historical equity vol**, a ~40/60 equity/bond mix beats 60/40 on all three goal-relevant axes:

| | P(goal) | fwd Sharpe | med maxDD | med CAGR |
|---|---:|---:|---:|---:|
| **40/60** | 70% | 0.68 | −15% | 5.0% |
| **60/40** | 67% | 0.51 | −23% | 5.3% |

Higher goal-odds, higher forward Sharpe, shallower median drawdown — for only ~0.3%/yr less *median* CAGR. The mechanism: **forward bonds out-Sharpe forward equity** (0.62 vs 0.35), and the ~20%-equity *Sharpe* peak (0.83 > pure-bond 0.62) is a **diversification effect** — the −0.29 stock-bond correlation makes a 20% equity blend lower-vol (5.7%) than pure IEF (6.8%), so the Sharpe-optimum's *location* is itself correlation-dependent.

The P(goal) 40-vs-60 gap is **stable, not MC noise**: across 10 seeds the gap is +2.7pp (std 0.5pp, always positive). The downside also improves: 40/60's 5th-pctile 10yr CAGR is **+0.9%** vs 60/40's **−0.4%** (a lost decade avoided), and P(10yr loss) falls 6%→2% — exactly the floor protection the goal wants.

### The no-reliable-mix finding (the binding constraint)

**No allocation clears 3.75% reliably.** The best P(goal) at any mix is only **70%** (at ~40% equity), short of an 80% "reliable" bar at *every* weight. The **10yr return dispersion, not the stock/bond mix, is the binding constraint** — consistent with study #8/[[F41]]. The mix choice improves drawdown and shaves miss-risk; it cannot make 3.75% a sure thing.

### Sensitivity (folded from the skeptic panel — the most important added check)

**Equity vol / universe.** The study fixes one equity universe (QQQ-tilted QID, 20.1% vol) and never sweeps equity vol. Re-running:

| equity leg / vol | P(goal)* @ eq | 60/40 P / Sh / DD | strict dom 60/40? |
|---|---|---|---|
| QID 20.1% (study's actual) | 40% → 70% | 67% / 0.51 / −23% | **yes** |
| broad ^GSPC 18.9% (realized) | 40% → 71% | 69% / 0.54 / −21% | **yes** |
| assumed 18% vol | 45% → 73% | 72% / 0.61 / −18% | yes (narrowing) |
| assumed 15% vol | 50% → 76% | 75% / 0.73 / −16% | weakly (~1pp odds) |

The **committed tool now emits this equity-vol sensitivity** (realized 20% / 18% / 15%): the P(goal)-optimum stays **below 60% equity at all three** (drifts ~40% → 40% → 50%), so a more conservative mix **weakly dominates 60/40 throughout** — but the goal-odds margin narrows from ~3pp (at the realized ~20% vol) to ~1pp (at an assumed 15% vol — a **near-tie on ODDS**, though the bond-heavy mix's drawdown edge persists). At the *realized* ~19-20% vol — QID **and** broad ^GSPC alike (the realized broad-market vol over this window is 18.9%, since it contains 2008 and 2020) — the dominance is clear, so the conservative tilt is **not** a QQQ artifact against actual data. So the *direction* (tilt more conservative than 60/40) is assumption-robust; only the *strength* of the dominance is equity-vol-specific.

**Forward equity risk premium (ERP).** Re-sweeping the forward means:

| forward equity / bond (ERP) | P(goal)* @ eq | strict dom 60/40? |
|---|---|---|
| 7% / 4.2% (2.8%, base) | 40% → 70% | **yes** |
| 8.5% / 3.5% (5.0%) | 55% → 73% | tie |
| 9% / 3.0% (6.0%) | 65% → 74% | **no (flips)** |

The dominance holds for the base case and narrow-ERP corners but **flips** at a wide forward ERP (~5%+), where the optimum drifts back to ≈60/40 or beyond. The conservative **direction** is robust across the plausible box; **strict** dominance is base-case-specific.

**CAGR give-up is median-only.** The "~0.3%/yr" cost of 60→40% equity is the *median*. Because equity's payoff is right-tailed, 60/40 beats 40/60 by **~+1.0%/yr at the 75th pctile** and **~+1.9%/yr at the 95th** — the upside the median hides is exactly where a 60/40 holder pays for equity. Defensible to ignore on goal grounds (the low income+floor goal does not want the right tail) — but it is the *smallest* of the give-up numbers, not the whole cost.

## The Finding

**For the project's actual goal — clear ~3.75% APY with the shallowest drawdown — 60/40 is too equity-heavy. A more conservative ~30-40% equity / 60-70% bond static mix is the goal-optimal refinement:** at the base-case forward assumptions and the historical ~19-20% equity vol it carries higher goal-odds (70% vs 67%), higher forward Sharpe (0.68 vs 0.51), a shallower median drawdown (−15% vs −23%), and a *better* downside floor (5th-pctile +0.9% vs −0.4%; P(10yr loss) 2% vs 6%), for only ~0.3%/yr less *median* CAGR. The driver is that **forward bonds out-Sharpe forward equity and the low 3.75% bar does not need the equity upside.** **BUT no mix clears 3.75% reliably** — best P(goal) is ~70% at any allocation, short of an 80% bar; the **10yr return dispersion, not the mix, is the binding constraint** (consistent with [[F41]]). The conservative *direction* is robust across the plausible assumption box, but the strict three-axis *dominance* is base-case-specific: it shrinks to a near-tie if forward equity vol is materially below ~20%, and the optimum drifts back toward 60/40 at a wide forward ERP (~5%+). The tilt's drawdown/floor protection is regime-dependent — it inherits the benign −0.29 historical stock-bond correlation (already +0.12 forward since 2022); a positive-correlation regime deepens the bond-heavy mix's drawdowns AND shifts the Sharpe-optimum toward pure bonds. **Consistent with and refining the whole arc ([[D6]]/[[F25]]/[[F41]]): the honest product is a static allocation, and for this goal the right static weight is more conservative than 60/40 — but no weight makes 3.75% a sure thing.**

## Verdict

**The verdict HOLDS** — "for the low income + low-DD goal a ~30-40% equity mix beats 60/40, but no mix clears 3.75% reliably" survives every check. The reproduction is exact and deterministic; the per-mix re-centering and mix construction are panel-verified correct; the forward-bond-out-Sharpes-equity asymmetry is real on the data (IEF 6.8% vol → 0.62; QID 20.1% vol → 0.35); and the binding-constraint caveat (best P ~70%, dispersion not mix) is correctly and prominently surfaced. **No issue invalidates a finding; `blocking=false`.** The four corrections folded above are all **writeup/honesty-level**:

- **(major, corrected) "DOMINATED" softened.** Strict three-axis dominance is base-case/historical-vol-specific — it survives the realized ~19-20% equity vol (QID and broad ^GSPC) but becomes a near-tie at an assumed ~15% forward equity vol and flips at a wide forward ERP (~5%+). The conservative *direction* is robust; the strict word is not. The refined ~30-40% equity recommendation is unchanged.
- **(minor, disclosed) The equity leg is the QQQ-tilted QID basket (~20% vol).** A broad ^GSPC leg (18.9% vol) reproduces the same direction, so the conclusion is basket-robust against actual data — but the exact optimum is mildly vol-sensitive, and this should be stated (cross-ref study #8's ^GSPC drawdown point).
- **(minor, disclosed) The "~0.3%/yr" CAGR give-up is median-only** — it grows to ~1%/yr (p75) and ~2%/yr (p95) in the right tail; justified to ignore on goal grounds, not silently dropped.
- **(minor, clarified) The ~20%-equity Sharpe peak is a diversification effect** (negative correlation lowers blend vol below pure bonds), so the Sharpe-optimum's *location* — not just drawdowns — ties to the correlation caveat.

None touches a finding: the headline never relied on strict dominance or on a precise optimum weight, and every correction either scopes an over-strong word or strengthens an honest framing. **This refines [[F41]] on the WEIGHT axis: the recommended static product should tilt more conservative than 60/40 (~30-40% equity) for this specific low-income/low-DD goal — but, exactly as [[F41]] found, no static build makes ~3.75% reliable, and the protection is regime- and assumption-dependent.**

## Surviving Caveats

- **SCENARIO study, not data (dominant caveat).** Forward equity 7% / bond 4.2% are ASSUMPTIONS (CAPE-compression + entry-yield), inherited from study #8. Every P, Sharpe, and drawdown is conditional on them.
- **Strict dominance is base-case-specific.** Survives realized ~19-20% equity vol (QID + ^GSPC); near-tie at assumed ~15% forward vol; flips at wide forward ERP (~5%+). Conservative *direction* is assumption-robust.
- **Equity leg is QQQ-tilted QID (~20% vol).** Broad ^GSPC (18.9%) reproduces the direction; the exact optimum is mildly vol-sensitive.
- **Drawdown/Sharpe odds inherit the benign −0.29 stock-bond correlation** (already +0.12 forward since 2022). A positive-correlation regime deepens the bond-heavy mix's drawdowns and shifts the Sharpe-optimum toward pure bonds — the tilt's protection is regime-dependent.
- **No mix clears 3.75% reliably** (best ~70% < 80% bar). Dispersion, not the mix, is binding ([[F41]]).
- **The conservative tilt's CAGR give-up is median-only** (~0.3%/yr); it grows to ~1-2%/yr in the upside tail, which the low goal explicitly does not want.
- **Goal tested as total-return CAGR ≥ 3.75%**, a looser bar than a sustainable 3.75% cash distribution (cash yield ~1.5-2%); sequencing risk applies (inherited from study #8).

## Reproduce

```
venv/bin/python tools/weight_optimization_study.py                  # frontier table + verdict
venv/bin/python tools/weight_optimization_study.py --json out.json  # full result dict
venv/bin/python tools/ctx.py web F41                                # the forward-60/40 finding this refines on the weight axis
venv/bin/python tools/ctx.py web D4                                 # the foundational ~3.75% APY goal
venv/bin/python tools/ctx.py web D6                                 # the go/no-go arc (static-allocation conclusion)
venv/bin/python tools/ctx.py web F25                                # the 26yr confirmation
```
