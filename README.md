# MONAD Quant

[![Tests](https://github.com/huthargrave-lang/MONAD-quant/actions/workflows/test.yml/badge.svg?branch=development)](https://github.com/huthargrave-lang/MONAD-quant/actions/workflows/test.yml)
[![Research site](https://github.com/huthargrave-lang/MONAD-quant/actions/workflows/pages.yml/badge.svg)](https://huthargrave-lang.github.io/MONAD-quant/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](#setup)
[![Cite](https://img.shields.io/badge/cite-CITATION.cff-lightgrey.svg)](CITATION.cff)

> **MONAD Quant is an open quantitative finance research base.** It is a typed, append-only
> **evidence graph** of reproducible studies — on asset allocation, execution risk in leveraged
> ETFs, SEC filings and corporate actions, closed-end-fund discounts, commodity linkages, and the
> epistemics of research itself — together with the machinery that keeps those claims honest:
> pre-registration, a trial ledger, refutation and admission gates, forward watches, and a
> queryable **Context Kit** that agents and humans navigate instead of reading the repo. A
> long-only mean-reversion trading engine ships with it as the **reference test bench** the
> methodology was built on and proven against.
>
> **Start here:** [`docs/LESSONS.md`](docs/LESSONS.md) (what transfers, fact-checked) · [`docs/METHODS.md`](docs/METHODS.md) (how results are made) · [`docs/GLOSSARY.md`](docs/GLOSSARY.md) · [`VISION.md`](VISION.md) (direction) · [`docs/DIRECTIONS.md`](docs/DIRECTIONS.md) (ranked next steps and program focus) · [research compendium](docs/research/README.md) ·
> [`SCHEMA.md`](SCHEMA.md) (graph model) · [`CONTRIBUTING.md`](CONTRIBUTING.md) (how a study gets made) ·
> [`AGENT_INDEX.md`](AGENT_INDEX.md) (agent entry point) · [research site](https://huthargrave-lang.github.io/MONAD-quant/) ·
> [`docs/REFERENCE_ENGINE.md`](docs/REFERENCE_ENGINE.md) (the test-bench engine)

---

## What is in the base

| Layer | What it is | Where |
|---|---|---|
| **Evidence graph** | 600+ typed nodes — Findings, Hypotheses, Experiments, Decisions — linked by `evidenced_by` / `supersedes` / `contradicts` edges. Claims are never deleted, only superseded with a tombstone, and CI forbids a current decision from resting on a retracted finding. | [`RESEARCH_WEB.md`](RESEARCH_WEB.md), [`SCHEMA.md`](SCHEMA.md) |
| **Research compendium** | 200+ study writeups, each a deterministic tool plus a standalone document with its status, nodes, and reproduce command. | [`docs/research/`](docs/research/README.md) |
| **Research governance** | Pre-registration (`tools/prereg.py`), a hash-chained trial ledger that records every backtest attempted — losers included — and deflates results by it (`tools/trial_ledger.py`), objections (`tools/refute.py`), an admission gate that is the only way a hypothesis becomes an edge (`tools/admit.py`), and frozen forward watches with a multiplicity charge. | [`docs/research/prereg/`](docs/research/prereg/README.md), [`trials/`](docs/research/trials/README.md), [`forward_watch/`](docs/research/forward_watch/policy/route.json), [`DAILY_STRATEGIES.md`](docs/research/DAILY_STRATEGIES.md) |
| **Context Kit** | A stdlib-only, portable knowledge layer over code ∪ ideas: routing, provenance (`why`), blast radius (`impact`), edit fences, drift and staleness detectors, and an interactive 3D map served read-only. | [`CONTEXT_KIT.md`](CONTEXT_KIT.md), [`tools/ctx.py`](tools/ctx.py) |
| **Public research surfaces** | A static site (research-web browser, 500+ node views, context map, stock screener with authored lenses, daily news-tone ledger) that publishes only what the repository owns. | [site](https://huthargrave-lang.github.io/MONAD-quant/), [`tools/export_pages.py`](tools/export_pages.py), [`docs/TONE_LEDGER.md`](docs/TONE_LEDGER.md) |
| **Reference engine** | The long-only RSI/VWAP mean-reversion engine (signals → backtest → sweep → paper broker) that the methodology was proven on. Paper-only by evidence, not by caution. | [`docs/REFERENCE_ENGINE.md`](docs/REFERENCE_ENGINE.md) |
| **Guards** | 200+ test modules that fail CI on graph integrity, manifest drift, stale citations, dead config knobs, and prose that disagrees with code. | [`tests/`](tests/) |

Snapshot as of 2026-10-29: 956 recorded trials across 66 families; 4 hypotheses registered under
the admission gate (`venv/bin/python tools/edge_scorecard.py` for the live figures).

---

## Research programs

Each program is a question, a frozen protocol, and a recorded answer — including the negative
ones. Status is as recorded in the compendium; node IDs resolve with `ctx web <ID>`.

| Program | Question | Status (recorded) | Entry point |
|---|---|---|---|
| **Active vs static allocation** | Does an active, long-only mean-reversion engine beat a static stock/bond allocation on risk-adjusted terms — and what is the honest income product? | **Closed.** 15 adversarially verified studies. Verdict `D6`: no risk-adjusted edge over a static blend at any timescale; the goal-optimal static mix is more conservative than 60/40 and its drawdown promises are correlation-regime-conditional (`F46`). | [compendium](docs/research/README.md), [`D6_active_vs_6040_study.md`](docs/research/D6_active_vs_6040_study.md) |
| **Execution risk in leveraged ETFs** | How much of a tight-stop intraday strategy's risk lives in overnight gaps, and which mitigations survive paired controls? | **54 studies (16–69).** Gap tails scale almost mechanically with leverage (`F53`); a 20d/15% volatility-flatten rule survives dependence stress but is matched by trivial recent-gap rules, so it is frozen as a forward hypothesis (`F58`–`F62`); 26 runtime audits (`F79`–`F104`) specify what a production-grade execution ledger must carry. | [`D6_overnight_gap_risk_study.md`](docs/research/D6_overnight_gap_risk_study.md), [`D6_forward_shadow_validation_design.md`](docs/research/D6_forward_shadow_validation_design.md) |
| **Public investment intelligence** | Can point-in-time public information (filings, index events, corporate actions, positioning) improve a simple forecast after leakage, multiplicity, and costs? | **Active charter.** Source-contract audits and reviewed seeds for SEC filing deltas (FD-00), index membership events (IX-00/01), a corporate-action outcome lab with a Form 25 population backbone and announcement-time deal cohorts (CA-00 … CA-ANNOUNCE), late filers (LF-01), Form 4 (FORM4-POP), ATM 424B5 (DI-01). One completed pilot is a clean negative (PN-00). No alpha claims. | [`PUBLIC_INVESTMENT_INTELLIGENCE_FRONTIER.md`](docs/research/PUBLIC_INVESTMENT_INTELLIGENCE_FRONTIER.md), [`EVENT_INTELLIGENCE_FRONTIER_2026.md`](docs/research/EVENT_INTELLIGENCE_FRONTIER_2026.md) |
| **Discount mechanisms** | Does NAV-discount reversion pay in closed-end funds, and does it transfer to metal trusts, mortgage REITs, and BDCs? | **Under the admission gate.** The CEF rule `H404702` is pre-registered, capacity-tested, and has survived three objection boards; its 1998–2003 pre-period test was uninformative by the pre-stated criterion. Metal-trust discount tilt corroborates and is on a frozen forward watch (`H366201`). The mREIT and BDC transfers closed NOT RUN at their data-quality gates — recorded, not retried. | [`CEF_DISCOUNT_pilot.md`](docs/research/CEF_DISCOUNT_pilot.md), [`CEF_PRODUCT_PROTOCOL.md`](docs/research/CEF_PRODUCT_PROTOCOL.md), [`METAL_TRUST_DISCOUNT_PROTOCOL.md`](docs/research/METAL_TRUST_DISCOUNT_PROTOCOL.md) |
| **Event and corporate-finance protocols** | Spin-off drift, buybacks, merger arbitrage as a bond sleeve, index-deletion rebound, insider clusters, earnings premium, fallen-angel credit sleeves, ATM financing pressure, trend-timed leverage, microcap illiquidity. | **Protocols frozen before data.** Results land in the web as each closes — e.g. spin-off drift corroborates on its survivorship-free ETF proxy while the backtest hypothesis is reject-bound; a credit sleeve does not improve the static product. | [`DAILY_STRATEGIES.md`](docs/research/DAILY_STRATEGIES.md), [`SPINOFF_PROTOCOL.md`](docs/research/SPINOFF_PROTOCOL.md), [`CREDIT_SLEEVE_MIX_PROTOCOL.md`](docs/research/CREDIT_SLEEVE_MIX_PROTOCOL.md) |
| **Commodity linkage and miner tilt** | Which commodity/miner relationships hold out of sample, and can a miner-vs-metal tilt be replicated across metals and decades? | **Discovery → confirmation → replication.** A 1,401-statistic discovery atlas; two rules survived a three-lens board; the GDX/GLD tilt is the only lead that held its sign out of sample (+0.27 active Sharpe, not significant); replication and 1984–2005 pre-period protocols are frozen with the forward watch. | [`COMMODITY_LINKAGE_DISCOVERY.md`](docs/research/COMMODITY_LINKAGE_DISCOVERY.md), [`MINER_TILT_REPLICATION.md`](docs/research/MINER_TILT_REPLICATION.md) |
| **Biotech catalysts (BIOCAT)** | Can versioned clinical-catalyst and FDA-compliance events be turned into point-in-time labels without outcome leakage? | **Source contracts and pilots.** Disclosure-order purity, FDA pre-notice response census, trial slippage × financing pressure — feasibility pilots, not populations. | [`BIOCAT_SOURCE_CONTRACT_2026.md`](docs/research/BIOCAT_SOURCE_CONTRACT_2026.md) |
| **Screener, lenses, and tone** | A public stock screener over an authored universe with research lenses (AI shadow debt, off-balance-sheet debt, value/growth/sentiment), the Sovereign Ledger thematic buckets, and a daily news-tone ledger with pre-registered gates. | **Live on the site, daily refresh.** Vendor data stays local; the site carries only what the repo owns. | [`docs/TONE_LEDGER.md`](docs/TONE_LEDGER.md), [`AI_SHADOW_DEBT_LENS_2026.md`](docs/research/AI_SHADOW_DEBT_LENS_2026.md), [`SOVEREIGN_LEDGER_2026.md`](docs/research/SOVEREIGN_LEDGER_2026.md) |
| **Epistemics of the research web** | Is the corpus itself sound — provenance of every number, reproducibility of market-data findings, reliance cycles, revision hazards, metric conventions? | **Audited and guarded.** EPI-00 (materially corrected on review), NUM-00 numeric provenance, REPRO-00 reproducibility, the return-convention lab that found two disjoint Sharpe stacks (`F153`), config/column reachability censuses that found dead knobs (`F145`). | [`EPI00_epistemic_audit.md`](docs/research/EPI00_epistemic_audit.md), [`NUM00_numeric_provenance.md`](docs/research/NUM00_numeric_provenance.md), [`REPRO00_market_data_reproducibility.md`](docs/research/REPRO00_market_data_reproducibility.md) |

---

## Selected results

Negative results, rigorously proven, are quant knowledge — usually the expensive kind that
funds keep private. Here they sit beside the positive ones with the same evidence standard.
Each row links to a deterministic, re-runnable study and its graph nodes.

| What was established | Why it matters beyond this repo | Nodes |
|---|---|---|
| A Sharpe-25 intraday backtest was a **morning-only data-sampling artifact**; the "edge" tracked bar-sampling frequency, not instrument or time-of-day | Validate data representativeness before believing *any* intraday edge | F13/F14 |
| Daily mean-reversion (lag-1 autocorrelation) is **real and robust over 26 years** — but naive t-stats overstate its significance ~3× | Use block-bootstrap CIs, not t-stats, on autocorrelated returns | F16/F18 |
| The **exit, not the entry, is the dominant lever**: a fixed %-stop destroys a mean-reversion edge that a multi-day horizon exit recovers | Stop placement inside intrabar noise silently converts edge to churn | F17/F19/F7 |
| A **real signal ≠ a tradable edge**: active daily MR is provably *equivalent-or-worse* vs a static blend (TOST, evidence-of-absence down to ~0.3 Sharpe over 26yr) | The benchmark that kills most timing strategies is a trivial static mix, not buy&hold | F22/F25/F34/F35 |
| Active timing's one honest contribution is **crisis drawdown reduction** — paid for in calm-market under-participation (Sharpe-neutral) | "Low drawdown" claims need a static-blend control | F36/F37 |
| The static 60/40 is **hard to improve reliably**: third sleeves, vol-targeting, and risk parity all fail fair paired bootstraps; gold fails clean OOS | Most "improvements" are regime bets or multiple-comparisons artifacts | F38/F39/F40 |
| Forward-looking (2026 yields), a 60/40 returns ~5–6%/yr at **Sharpe ~0.5**; the goal-optimal mix is **more conservative than 60/40** | Historical 60/40 stats are a regime, not an expectation | F41/F42 |
| Everything above is **correlation-regime-conditional**: bonds hedged stocks in only ~22 of the last 64 years, and no composition escapes the regime bet — a 50/50 cash/bond blend *halves* it, nothing removes it | The stock-bond hedge is the exception, not the rule — test "inflation hedges" against duration-matched controls | F46/F48/F49 |
| Across the income-ETF universe **high yield ≠ low drawdown**; the one structural escape (a held-to-maturity ladder) has a *definitional, nominal-only* 0% drawdown | Distribution yield is not return; amortized-cost accounting is not safety | F44/F45 |
| A tight stop does **not** bound overnight risk in a 3× ETF, and gap tails scale near-mechanically with leverage (TQQQ/QQQ beta 2.95, R² .993) | Model session gaps at the open or remove the overnight exposure; slippage scalars cannot represent jump risk | F47/F50/F53 |
| The 20d/15% volatility-flatten rule survives dependence and threshold stress — but trivial recent-gap rules match its capture lift, and its recall is largely blanket risk-off exposure | Benchmark every risk classifier against transparent nulls and report exposure removed beside tail capture | F58–F62 |
| A simulator can be **provably different from live** while the apparent correction is still unidentifiable; "application-submitted" is not "broker-executed" | Demand lower-timeframe or order-event evidence, and a durable lifecycle ledger, before calling live PnL validated | F51/F87/F90/F91 |
| Sweep/holdout winners are **selection-biased best-of-many**; live-vs-backtest gaps decompose into measurable causes (bar frequency dominated here) | Reconcile live to backtest quantitatively before blaming execution — and count every trial, not just the winner | F2/F28/F43 |
| A corrected one-session liquid-ETF **lead–lag graph does not improve** later return forecasts | A clean negative that redirects the network branch toward monthly diffusion and event-conditioned graphs | [PN-00](docs/research/PN00_daily_cross_asset_lead_lag.md) |
| Physical-metal trust **discount reversion pays** when nothing but the discount moves; spin-off drift corroborates on its survivorship-free ETF proxy | Positive results get the same frozen-protocol, pre-stated-criterion treatment as the negatives | [metal trust](docs/research/METAL_TRUST_DISCOUNT_PROTOCOL.md), [spin-off](docs/research/SPINOFF_PROTOCOL.md) |

<details>
<summary><b>Full findings ledger from the allocation and execution-risk programs (F2–F104)</b></summary>

| What we established | Why it matters beyond this repo | Nodes |
| A Sharpe-25 intraday backtest was a **morning-only data-sampling artifact**; the "edge" tracked bar-sampling frequency, not instrument or time-of-day | Validate data representativeness before believing *any* intraday edge | F13/F14 |
| Daily mean-reversion (lag-1 autocorrelation) is **real and robust over 26 years** — but naive t-stats overstate its significance ~3× | Use block-bootstrap CIs, not t-stats, on autocorrelated returns | F16/F18 |
| The **exit, not the entry, is the dominant lever**: a fixed %-stop destroys a mean-reversion edge that a multi-day horizon exit recovers | Stop placement inside intrabar noise silently converts edge to churn | F17/F19/F7 |
| A **real signal ≠ a tradable edge**: active daily MR is provably *equivalent-or-worse* vs a static blend (TOST, evidence-of-absence down to ~0.3 Sharpe over 26yr) | The benchmark that kills most timing strategies is a trivial static mix, not buy&hold | F22/F25/F34/F35 |
| Active timing's one honest contribution is **crisis drawdown reduction** — paid for in calm-market under-participation (Sharpe-neutral) | "Low drawdown" claims need a static-blend control | F36/F37 |
| The static 60/40 is **hard to improve reliably**: third sleeves, vol-targeting, and risk parity all fail fair paired bootstraps; gold fails clean OOS | Most "improvements" are regime bets or multiple-comparisons artifacts | F38/F39/F40 |
| Forward-looking (2026 yields), a 60/40 returns ~5–6%/yr at **Sharpe ~0.5** — half its bond-bull-flattered history; the goal-optimal mix is **more conservative than 60/40** | Historical 60/40 stats are a regime, not an expectation | F41/F42 |
| Across the income-ETF universe, **high yield ≠ low drawdown** — nothing beats the 60/40 on both; the one structural escape (held-to-maturity ladder) has a **definitional, nominal-only** 0% drawdown | Distribution yield is not return; amortized-cost accounting is not safety | F44/F45 |
| Everything above is **correlation-regime-conditional**: bonds hedged stocks in only ~22 of the last 64 years; in the 1965–81 inflation regime every bond-heavy mix lost purchasing power for a decade, and the conservative tilt's drawdown edge *inverts* in real terms | The stock-bond hedge is the exception, not the rule — and it flipped again in 2022 | F46 |
| There is **no escape from the regime bet by composition**: a marked-to-market TIPS sleeve is duration-shortening in disguise (indistinguishable from a duration-matched nominal sleeve), and no fixed cash/bond blend or barbell dominates both correlation regimes — a 50/50 blend *halves* the worst-case bet, nothing removes it | Test any "inflation hedge" against a duration-matched control before crediting the label | F48/F49 |
| A tight stop does **not** bound overnight risk in a 3× ETF: exact-stop accounting roughly halves observed two-year loss/drawdown versus open-aware fills; a scalar stop penalty matches the mean but misses the tail | Model session gaps at the open or remove the overnight exposure; spread/slippage scalars cannot represent jump risk | F47/F50 |
| The research runner skips the live bracket's **entry hour**; the mismatch affects 64.6% of paired entries, but hourly dual-hit bars make its return sign unidentifiable | A simulator can be provably different from live while the apparent “correction” is still underidentified—use lower-timeframe/order-event evidence | F51 |
| Clock cutoffs can look like risk controls while repeating the **morning-only selection artifact**; only direct EOD exposure removal cleanly eliminates the gap channel | Separate mechanism-pure risk removal from in-sample opportunity-set selection | F52 |
| Leveraged-ETF gap tails scale near mechanically with leverage over 16 years (TQQQ/QQQ beta 2.95, R² .993) | A fixed stop cannot cap a discontinuous open; this is instrument structure, not one signal's bad luck | F53 |
| Sixteen resolved five-minute events cannot calibrate the entry-ordering repair; exact-stop break-even is only 2.5pp from the observed rate, while the gap-aware path needs 52.17% target-first vs 28.57% observed | Quantify the value of additional data before turning a tiny microstructure sample into a simulator parameter | F54 |
| Weekend/long closures produce 44% of gap damage but only 24% of gap events; targeting them uses 78% fewer closes than daily flatten but leaves most weekday risk | Partial tail controls should report both damage captured and event coverage—one can look excellent while the other fails | F55 |
| A time-sensitive one-minute recovery resolved July 6 **stop-first**; the best audit is now 5 target-first / 12 stop-first / 2 unresolved, tightening the gap-aware P(positive) bound to 1.2%–9.9% | Preserve expiring lower-timeframe evidence with hashes and derived audits; do not impute the missing events | F56 |
| Severe TQQQ gaps **cluster** (next-night risk 1.34× after a ≤−2% gap); lagged volatility captures them only by disabling most overnight exposure | Risk filters must report exposure removed alongside tail capture—a high recall score can be near-daily flatten in disguise | F57 |
| Daily and 15%-volatility flatten survive same-path block stress, but auction-cost budgets are only ~35/61 bp per exit and the volatility threshold is post-selected | Freeze the hypothesis for forward paper-shadow fills; a selected backtest control is not production evidence | F58 |
| The 20d/15% volatility classifier survives a 2010–2019 threshold split, but 10d fails the strategy gate and 40/60d approach daily-flatten turnover | Treat 20d/15% as one narrow forward hypothesis—not evidence that generic volatility timing works | F59 |
| A frozen 20d/15% shadow needs ~115 new strategy gap events (~6.7 years iid; ~8.4–13.3 years under heuristic clustering effects) for 80% power, and IBKR paper lacks Auction orders/real fills | Use no-order paper shadow only to falsify the classifier/plumbing; it cannot approve real MOC cost or production | F60 |
| Vol20's unconditional severe-gap capture lift (1.33×) is matched by trivial recent-gap rules (1.31×–1.38×), though vol20 aligns better with this selected strategy path | Benchmark every risk classifier against transparent clustering rules; the forward claim is strategy alignment, not unique prediction | F61 |
| Vol20 flagged every 2022 night and ~84% of 2020/2023; in 2024 its capture lift fell below 1 despite 59% exposure | Report exposure and year-level lift beside capture; high raw recall can be blanket risk-off behavior rather than stable discrimination | F62 |
| All six execution-study caches match embedded SHA-256 snapshots, but raw vendor bytes live only in `/tmp` | Separate deterministic code from self-contained data; every refresh needs a new hash and result diff | F63/F71 |
| Vol20 has only 1.11× capture lift at the 0.5% stop but 1.57×–1.70× at 4%–8% gaps; unflagged worst remains −10.54% | Treat it as a catastrophic-state exposure control, never a precise stop predictor or loss bound | F64 |
| Crediting TQQQ distributions removes only 2/1,289 raw ≥0.5% gaps, no severe gaps, and adds just +0.0338 pp to the negative strategy path | Use raw prices for stop triggers and distribution-inclusive wealth for returns; ex-dividend effects do not explain the tail | F65 |
| The hourly cache has two corrupt full-day sessions; Feb 2 begins at 13:30 and its apparent open is 463.7 bp above the daily/public open | Validate every session against the exchange calendar and prefer daily open for gap fills; both correction sensitivities slightly worsen the result | F66 |
| The joint corrected baseline is −10.1713% total / −10.2126% maxDD; vol15 and daily flatten retain only 62.58/34.89 bp cost ceilings | Consolidate valid corrections before comparing policies; never choose among accounting variants by which looks best | F67 |
| Official daily versus last-hourly close changes mitigation totals by <0.08 pp and leaves both descriptive gates intact | Paired proxy robustness removes one fragility, but shared-vendor prints still cannot validate auction execution | F68 |
| A standard Nasdaq MOC fill equals the Cross/NOCP price; 60 intended events test operational failure, not fill slippage | Reconcile Cross fills, count rejects/unfilled events in the denominator, and treat self-impact as unidentified | F78 |
| The current trader is not MOC-ready, and its hard-coded 16:00 guard admits jobs after official 13:00 early closes | Require an exchange calendar and fail-closed deadline tests before any separately authorized auction work | F79 |
| The pinned window has 162 off-calendar jobs: 65 overlap clean open-position state, and all 15 post-close early-session jobs reuse a processed bar | Gate the runtime on the official session calendar and make bar processing idempotent before protected-path remediation | F81 |
| Sanitized Pi records confirm cycles ran on Good Friday and Memorial Day; all 22 rows failed at paper-port connection rather than a calendar guard | Treat the calendar defect as observed; separately investigate historical double writes without projecting them onto the current preflight-gated deployment | F82 |
| Historical paired cycles were not cosmetic: 69/210 signals and 58/210 long-eligibility decisions disagree; seven entry minutes reached the bracket success path twice while local state kept only the later write | Require cycle/bar idempotency plus broker order/execution reconciliation; a one-row local trade table cannot prove exposure under concurrent submissions | F83 |
| Live bar labels are UTC-naive but completion/staleness uses host-local-naive time; the DST archive matches the resulting current-tail race exactly | Normalize to one timezone-aware clock and test vendor-tail present/absent cases before any protected runtime remediation | F84 |
| True-UTC aging finds 297/543 archived signals and at least 40/65 entry minutes used an in-progress hourly bar | Treat the historical live PnL as chronology-contaminated rather than completed-bar validation; require cycle-keyed bar-end evidence | F85 |
| Only two of six trader launch paths reach the full preflight, and no path proves atomic process or per-bar order ownership | Use only the managed service path; require a process-lifetime lock plus durable broker-reconciled order intent before any production-readiness claim | F86 |
| `ENTRY placed` follows three submission calls but zero broker acknowledgement/fill checks; `fill_basis` is a quote, and 0.435 bp of adverse entry-basis error flips the flat archive sign | Distinguish application-submitted, broker-accepted, and executed; call the old PnL bucket exit-confirmed until entry executions are durable | F87 |
| A locally recorded but unfilled parent can later become an inferred TP/SL round trip because broker-flat is treated as bracket-exited; the archive has five execution-unverified inferred rows and three immediate re-entry events | Reconcile positions, active orders, and executions separately; missing evidence needs an `unverified` state, not forced PnL | F88 |
| Exit recovery matches client order-number arithmetic, stores no permanent/execution identity or quantity, selects one partial price instead of VWAP, and its seven-day fallback cannot work on IB Gateway beyond midnight | Build a durable execution ledger before calling recovered prices fully attributable; broker retention is not local durability | F89 |
| SQLite serializes writes but does not atomically claim a lifecycle: two connections can cache one position and sequentially commit two trade rows; a losing closer still cannot suppress alerts/re-entry | Enforce a unique lifecycle key and atomic claim, then gate every side effect on a typed winning-close result | F90 |
| A stale cycle can attach old exit economics to a newer re-entry and then delete the newer row because close carries no expected lifecycle identity | Propagate one durable lifecycle ID through intent, broker order/execution, state, close, events, and exports; reject generation mismatches atomically | F91 |
| The 1% target and 0.5% stop are quote-anchored: at the parent limit cap they become roughly +0.5%/−1.0% from fill, while bar-close sizing can exceed the planned notional | Report fill-relative geometry and actual filled notional; preserve a cycle-keyed chain from sizing bar through order and executions | F92 |
| Force-close uses the full requested local quantity after only a nonzero broker-position test; partial fills or late child fills can overshoot flat into the opposite position | Cancel parent/children to terminal states, close the fresh signed broker residual, then verify exact broker flatness before deleting lifecycle state | F93 |
| Force-close treats the first execution as completion, records one component price instead of VWAP, and deletes local state even after a ten-second no-fill timeout | Require cumulative filled quantity, zero remaining, execution VWAP, pending-close retention on uncertainty, and a fresh broker-flat check | F94 |
| Same-cycle replacement entry checks net position but not whether old close/child orders are terminal; two archived entries followed explicit close timeouts | Require terminal prior orders plus exact broker flatness and an atomic lifecycle handoff before successor submission | F95 |
| Account summary, position lookup, orders, and state carry no common account/model identity; callback order can select capital or direction in a multi-account session | Configure and validate one paper account/model, scope every query/order/lifecycle field, and fail closed on ambiguity | F96 |
| Duplicate historical invocations advanced the shared holding counter twice: seven of nine time exits hit bar 10 after exactly five paired cycle minutes | Count unique completed bars through an atomic lifecycle+bar transition; do not use process invocations as holding age | F97 |
| Order construction accepts prior-day close, out-of-spread last, or 15–20-minute delayed data without field/type/timestamp evidence; recent 15/20-minute TQQQ moves cross the 0.5% order offset in 32.1%/36.5% of exact pairs | Require timestamped, callback-typed, positive-size, side-aware live spread evidence; fail closed on prior close, delayed data, and last outside the spread | F98 |
| Every entry obtains separate account-mark and bracket-price snapshots with no decision-age deadline; 22/72 archived application entries occurred at least 30 seconds after the nominal cycle anchor | Remove or safely reuse the redundant snapshot, impose a decision-to-submit deadline, and persist the full signal→quote→order→execution clock | F99 |
| A green `live` mark does not prove real-time data: delayed and nominal-live broker branches collapse to one scalar and every successful scalar is labeled `live`; local `mark_time` is not quote time | Preserve callback-typed, field-level, source-timestamped provenance end to end; label missing provenance unknown | F100 |
| Software risk triggers accept any non-null mark; all four uniquely joined archived stop exits remained economically beyond their stops, but two duplicate writers triggered again after the close record | Gate source/age, claim one lifecycle before ordering, retain execution identity, and verify exact broker flatness | F101 |
| After broker failure, a daily yfinance close with no row-date/age check can drive intraday exits; under a prior-session-row counterfactual, 62–65/160 archived cycle slots falsely cross the stop proxy and 17 cross take-profit | Exclude daily historical closes from intraday triggers or require typed timestamped freshness plus one end-to-end deadline | F102 |
| Paired historical writers supplied bar-close fallbacks on opposite sides of a risk boundary in ten archived position-cycle slots—five stop forks and five take-profit forks | Require one completed-bar identity and atomically claim one lifecycle/cycle owner before any forced exit | F103 |
| Broker connection refusal bypasses every mark fallback and aborts before holding-age and software-risk checks; 33 archived abort events cover 17 position-open cycle slots | Normalize broker availability, record missed-risk-check state, and define recovery/holding age from completed-bar identity | F104 |
| Distribution-inclusive QQQ returns flip only 5/4,113 vol15 labels and zero strategy decisions | Corporate-action-adjust classifier inputs even when the audit proves the current decision is unchanged | F70 |
| Vol20 reproduces exactly from t−1 data; unshifted current-close lookahead flips 20 recent labels and worsens the path | Prove decision-time availability, not merely a `.shift(1)` in source code | F72 |
| Every 14–16% quarter-point vol20 threshold retains the descriptive risk gate | A local robustness plateau rules out a threshold cliff, but cannot erase same-sample selection | F73 |
| Vol15's fixed-cohort benefit (+4.1299 pp) matches its dynamic benefit (+4.1302 pp); daily replacement trades cost 0.7724 pp | Decompose direct risk removal from newly admitted opportunity paths before calling a policy causal | F74 |
| Vol15's largest event contributes ~24% of direct benefit; removing top five still leaves +1.7657 pp | Report leave-largest-events-out results when tail-risk controls are expected to win through rare disasters | F75 |
| Corrected fixed-cohort vol15 relative wealth is +4.5976%, with block-20 95% CI [+1.860%, +8.314%] | Dependence stress the direct mechanism itself, not only a dynamic policy path | F76 |
| Vol15 improves 43/67 changed baseline trades; all 21 eventual gap stops benefit while all 24 eventual targets are harmed | Report intervention precision and sacrificed winners beside tail-loss magnitude | F77 |
| Sweep/holdout winners are **selection-biased best-of-many**; live-vs-backtest gaps decompose into measurable causes (bar frequency dominated here) | Reconcile live to backtest quantitatively before blaming execution | F2/F28/F43 |

</details>

---

## How a result gets made

Every study follows the same disciplines, enforced in code rather than promised in prose
(the compendium's [methodology section](docs/research/README.md#the-shared-methodology)
records which guarantees are machine-checked and which are process):

```
frozen data ──> counted evaluator ──> trial ledger ──> relative statistics ──> web finding
  DS-<sha>         (refuses to run      one family per     active vs the domain's      note.py
                    without a trial)     domain + version    benchmark: SPA, DSR, eras    (lint-gated)
```

- **Deterministic, re-runnable artifacts** — each study is a committed CLI tool
  (`tools/*_study.py`, `tools/*_lab.py`; seed=0, content-addressed data), not a notebook.
- **Leak-free by construction** — entries and weights use only lagged information; windows
  verified byte-identical to truncated recomputation; decision-time availability is proven,
  not inferred from a `.shift(1)` in source.
- **Uncertainty on every claim** — paired block-bootstrap CIs from a shared, unit-tested
  module ([`src/backtest/uncertainty.py`](src/backtest/uncertainty.py)); family-wise
  corrections and Deflated Sharpe against everything the family tried.
- **Pre-registration** — protocol, benchmark, window, costs, and pass criterion frozen and
  committed before the data is loaded; the admission gate judges only against the frozen spec.
- **Adversarial review** — the allocation studies were attacked by independent multi-lens
  skeptic panels; later programs convene statistics / mechanics / adversary boards whose
  amendments and rulings are recorded in the writeups. Forced corrections are folded into
  the tool, not caveated around.
- **Supersession, not revisionism** — overturned claims are tombstoned with a reason and
  every citation is re-pointed; `ctx web --lint` fails the build on stale cites.
- **Rights-aware data** — vendor observations whose terms grant no redistribution right are
  never committed or published; frozen datasets are content-addressed so a trial names
  exact bytes ([`docs/research/data/README.md`](docs/research/data/README.md)).

[`docs/METHODS.md`](docs/METHODS.md) is the paper-style methods section with every formula and
constant cited to the code; [`docs/GLOSSARY.md`](docs/GLOSSARY.md) defines the vocabulary;
[`CONTRIBUTING.md`](CONTRIBUTING.md) walks through the workflow end to end. To lift the Context Kit
into another repository, start from [`examples/minimal-research-web/`](examples/minimal-research-web/README.md).

---

## The Context Kit — a knowledge graph you can query

The **Context Kit** is a portable, stdlib-only layer that agents (and humans) query instead of
reading the whole codebase. It unifies **ideas** (findings, hypotheses, experiments, decisions),
**code** (modules, symbols, config keys, test coverage, auto-extracted by AST), and the
**bridges** between them (which finding lives in which symbol, guarded by which test).

**Start here:** [`AGENT_INDEX.md`](AGENT_INDEX.md) · [`CONTEXT_KIT.md`](CONTEXT_KIT.md) · schema: [`SCHEMA.md`](SCHEMA.md)

```bash
# Orient to a task (files to read + commands to run)
venv/bin/python tools/ctx.py route "add a pre-registered CEF discount study"

# Walk the research graph
venv/bin/python tools/ctx.py web F46          # read a finding + its evidence links
venv/bin/python tools/ctx.py why D6           # provenance: why believe this decision?
venv/bin/python tools/ctx.py contradicts F15  # dispute/supersession state
venv/bin/python tools/ctx.py related "overnight gap"   # semantic neighbours (TF-IDF)

# Blast radius and edit fences before changing anything
venv/bin/python tools/ctx.py impact live/broker.py
venv/bin/python tools/ctx.py can_edit config.py   # DENY on live/strategy paths

# Honest performance state of the reference engine
venv/bin/python tools/ctx.py perf

# Capture a new finding (dry-run by default; --commit to write)
venv/bin/python tools/note.py add --kind F --title "..." --body "..."
```

### Interactive context map (browser)

```bash
venv/bin/python tools/ctx.py serve --host 127.0.0.1 --port 8001   # → http://127.0.0.1:8001/
venv/bin/python tools/ctx.py graph --html > context_map.html       # static export
```

The map is a self-contained D3/SVG page and a *reader*, not just a picture: a dark 3D layout,
an inspector with each node's prose and clickable `[[ID]]` links, status and confidence badges
(stated *and* effective, naming the weakest link), supersession / disputed / fragile warnings,
`ctx why` provenance chains, full-text search over node bodies, TF-IDF "related by content"
neighbours, an open-work panel, `ideas` / `code` / `all` layer presets, deep links (`…/#F13`),
and keyboard navigation. It degrades to a searchable node list offline, since all research
text is inlined; drop a d3 v7 UMD build at `tools/vendor/d3.min.js` to remove the one CDN
dependency. `GET /api/graph.json` returns the same map as data; `GET /health` is the liveness
probe. The published site serves the same map statically.

---

## The reference engine (test bench)

The research base is exercised end-to-end by a real system: a long-only mean-reversion engine
(RSI dips in confirmed uptrends, regime-gated, bracket exits) with a universal parameter sweep,
three backtest-fairness modes (`optimistic` / `realistic` / `harsh`), and a paper-only trader on
Interactive Brokers with a read-only dashboard. It is the subject the methodology was proven on
— including the finding that its own hourly timescale carries no edge (`F13`/`F43`), which is
why it runs paper-only and why the allocation program's honest product recommendation is a
static mix (`D6`).

Everything about the engine — modes, the execution model and its audited backtest↔live
differences, the sweep tool's phases and scoring, the paper trader, the dashboard, Raspberry Pi
deployment, and the ETF-vs-BTC cost comparison — lives in
**[`docs/REFERENCE_ENGINE.md`](docs/REFERENCE_ENGINE.md)**. The strategy's design history
(what was tried, what failed, and why) is in [`CLAUDE.md`](CLAUDE.md); operations in
[`OPERATIONS.md`](OPERATIONS.md).

> Headline Sharpe/return numbers in older documents came from optimistic-mode backtests on
> morning-only data and are kept as optimization history. Run `venv/bin/python tools/ctx.py perf`
> and `ctx web --live` for the current verdict.

---

## Setup

Python **3.11+** is required (CI and the paper deployment use 3.11; the codebase uses modern
union/type syntax that does not import on Python 3.9).

```bash
git clone https://github.com/huthargrave-lang/MONAD-quant.git
cd MONAD-quant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

For the paper trader and dashboard: `pip install -r requirements-live.txt`.
For Raspberry Pi: `pip install -r requirements-pi.txt`.

## Reproduce

```bash
# Any research study (deterministic, seed=0; data-fetching studies cache locally)
venv/bin/python tools/bond_ladder_study.py
venv/bin/python tools/correlation_regime_study.py --selfcheck
venv/bin/python tools/overnight_gap_risk_study.py
venv/bin/python tools/epistemic_audit_lab.py risk

# The accountable daily-strategy workflow (frozen data → counted trials → finding)
venv/bin/python tools/edge_scorecard.py
venv/bin/python tools/trial_ledger.py stats
venv/bin/python tools/domain_search.py cef_discount --snapshot <DS sha> --panel <CEFNAV sha> --report-only

# The reference engine
python main.py                                    # standard backtest
python main.py --mode=walk-forward                # walk-forward optimizer (daily mode)
python sweep.py TQQQ --mode realistic --validate-best
python -m live.trader --dry-run --once            # paper trader, signals only

# Research surfaces
venv/bin/python tools/research_ui.py serve        # research-web browser + screener
venv/bin/python tools/ctx.py serve --port 8001    # context map
python tools/export_pages.py --out _site          # the static site, as CI builds it

# Tests (unittest — NOT pytest). CI needs full git history for two guard families.
python -m unittest discover -s tests
```

### Branches

- **`development`** — the canonical branch and the GitHub default. All reviewed work lands
  here; it is what the site is built from and what the paper deployment runs.
- **`main`** — legacy/divergent; not used.
- **`tone-ledger`** — bot-written daily tone observations (see [`docs/TONE_LEDGER.md`](docs/TONE_LEDGER.md)).

---

## Repository layout

```
MONAD-quant/
├── RESEARCH_WEB.md          <- The evidence graph (findings, hypotheses, experiments, decisions)
├── SCHEMA.md                <- Node kinds, edge vocabulary, write rules, invariants
├── VISION.md                <- Direction + staged roadmap
├── CONTRIBUTING.md          <- How a study is proposed, frozen, run, recorded, admitted
├── CITATION.cff             <- How to cite the base
├── docs/
│   ├── LESSONS.md           <- What the base learned that transfers (14 lessons, fact-checked)
│   ├── METHODS.md           <- Paper-style methods: data contracts, execution model, bootstrap, DSR/SPA, gates, forward route
│   ├── GLOSSARY.md          <- The vocabulary, each term pointing at its defining file
│   ├── research/            <- 200+ study writeups, the compendium index, and governance:
│   │   ├── README.md        <-   program map + the active-vs-static / execution-risk record
│   │   ├── data/            <-   content-addressed frozen datasets (rights-aware)
│   │   ├── prereg/          <-   frozen pre-registrations, one per hypothesis
│   │   ├── trials/          <-   hash-chained trial ledger (every attempt, losers included)
│   │   ├── refutations/     <-   objections and board rulings
│   │   ├── forward_watch/   <-   frozen forward records + the multiplicity policy
│   │   └── reeval/          <-   re-evaluation of pre-gate findings
│   ├── DIRECTIONS.md        <- Ranked next directions for the project (dated memo, owner ratifies)
│   ├── REFERENCE_ENGINE.md  <- The test-bench engine, execution model, sweep, deployment
│   ├── TONE_LEDGER.md       <- Pre-registered gates for the daily news-tone series
│   └── history/             <- Archived optimization logs (superseded numbers, kept as history)
├── examples/
│   └── minimal-research-web/ <- Non-finance worked example: lift the Context Kit in 5 minutes
├── tools/
│   ├── ctx.py               <- Context Kit CLI (route, web, why, impact, serve, lint, ...; --repo PATH)
│   ├── note.py              <- The only writer to the evidence graph (append / supersede / link)
│   ├── prereg.py, refute.py, admit.py, trial_ledger.py, forward_watch.py, edge_scorecard.py
│   ├── *_study.py, *_lab.py <- Deterministic research tools, one per study
│   ├── research_ui.py       <- Research-web browser, screener, node views (read-only)
│   └── export_pages.py      <- Static site build (GitHub Pages)
├── src/
│   ├── research/            <- Counted evaluators, trial ledger, prereg, admission logic
│   ├── backtest/            <- Runner + the shared uncertainty module (block bootstrap, posteriors)
│   ├── optimization/        <- Sweep scoring/sizing, the validation funnel
│   ├── signals/, strategy/  <- The reference engine's features and trade simulation
│   └── data/                <- Fetchers and caches
├── live/                    <- Paper trader, broker adapter, state DB, dashboard (edit-fenced)
├── config.py, config_modules/ <- Engine parameters (single source of truth; edit-fenced)
├── context_map.json         <- Context Kit manifest (areas, routing, bridges, edit policy)
├── AGENT_INDEX.md, AGENTS.md, CLAUDE.md, OPERATIONS.md  <- Agent router, pointers, engine history, ops
├── ops/, deploy/            <- Secret scan, edit guard hook, systemd units, Pi scripts
└── tests/                   <- 200+ guard and unit test modules (unittest)
```

---

## Scope and disclaimers

- **Research, not advice.** Nothing here is a recommendation to buy, sell, or hold anything.
  Every number is a research result with its uncertainty, benchmark, and known failure modes
  recorded in the graph.
- **Results are findings about specific instruments, data, and protocols**, not universal
  claims about markets. The reference engine's no-edge verdict (`D6`/`F13`/`F43`) is one such
  finding — and the clearest demonstration that the evidence layer bites its own author's
  strategy as hard as anyone else's.
- **The reference engine is paper-only.** It connects to Interactive Brokers paper accounts
  (port 7497); project policy prohibits the live port, and the evidence does not justify
  arming it. Its known execution-model limitations are listed in
  [`docs/REFERENCE_ENGINE.md`](docs/REFERENCE_ENGINE.md#known-limitations-engine-specific).
- **Vendor data is not redistributed.** Published pages and committed datasets carry only what
  the repository owns; see [`docs/research/data/README.md`](docs/research/data/README.md).
- **Consistency is enforced; correctness is a human's job.** The guards police that a claim
  has evidence and that nothing current rests on a retraction. A confidently wrong finding
  with a valid evidence edge still passes every lint.

## Citing

See [`CITATION.cff`](CITATION.cff) (GitHub renders a "Cite this repository" button from it).
Cite individual findings by node ID (`RESEARCH_WEB.md`, e.g. `F46`) and the study document
that carries them, so the citation survives supersession.

## License

MIT — © 2026 Monad Industries. See [`LICENSE`](LICENSE).
