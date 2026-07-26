# MONAD-quant — The Active-vs-Static Research Program

*A self-contained, adversarially-verified body of work answering one question:
**does MONAD's active mean-reversion engine actually beat a simple static allocation — and if not, what is the honest product?***

This directory is the durable record. Each study is a deterministic, leak-free tool
(`tools/*_study.py`) + a standalone writeup, cross-linked to the `RESEARCH_WEB.md` idea graph
(run `venv/bin/python tools/ctx.py web <node>`). Studies 1–15 were hardened by independent
multi-agent skeptic panels. Studies 16–69 form one execution-risk program with engine-exactness
checks, same-entry counterfactuals, pre-registered mitigation gates, lower-timeframe calibration,
long-history cross-instrument controls, and cross-runtime reproduction; they do not claim the
independent-panel status of studies 1–15. Corrections and surviving caveats are recorded in each
writeup.

The next research generation is deliberately broader than the mean-reversion arc:
the **[Public Investment Intelligence Frontier](PUBLIC_INVESTMENT_INTELLIGENCE_FRONTIER.md)**
preregisters a point-in-time public-data substrate and branching studies for SEC filing
changes, rhetoric-versus-numbers, cross-asset information flow, 52-week/trend anchors,
macro vintages, news propagation, and positioning. It is a program charter—not an
alpha claim or a seventieth completed empirical study.

Its first exploratory pilot, **[PN-00](PN00_daily_cross_asset_lead_lag.md)**, is a
useful negative result: a corrected one-session liquid-ETF information-flow graph
does not improve later return forecasts. It narrows the graph branch toward monthly
industry diffusion or point-in-time event-conditioned networks.

The first infrastructure node, **[FD-00](FD00_sec_filing_delta_lab.md)**, audits the
SEC source clock and preregisters a Filing Delta model factory. Real EDGAR fixtures
show filing-date rollover, post-close events, legacy timestamp ambiguity,
private-to-public delays, amendments, and accession/issuer identity mismatches. Its
verdict is to proceed only through an append-only, accession-scoped ledger; it does
not claim that filing changes predict returns.

The second source-contract node, **[IX-00](IX00_index_membership_event_lab.md)**,
turns the noted index-addition/deletion idea into a three-clock event lab. An
eight-security March 2026 S&P pilot finds exceptional implementation-session volume
and large raw addition/deletion separation, but explicitly rejects a causal or
trading claim. A 12-security December 2025 Nasdaq replication breaks the directional
result while repeating the extreme implementation-volume observation. A complete
2024 Nasdaq batch produces the same one/five-session addition-reversal sign as 2025;
the two-batch panel is only a hypothesis generator. A 2022 backfill is quarantined
at 12/13 coverage because acquired Splunk is absent from the free provider, and the
2023 list is quarantined because it was revised after publication. Its durable
contribution is the distinction between direct entries, index-family migrations,
provider publication, implementation close, effective open, revision state, and
coverage—plus a rights-aware model factory for forced-flow, reversal, revision,
selection, auction, anticipation, and comovement studies.

Its first child, **[IX-01](IX01_nasdaq_2023_revision_ledger.md)**, implements the
missing revision contract. A versioned fixture and disposable SQLite projection
preserve the December 2023 Nasdaq-100 list before and after the TTWO/SGEN update,
support exact as-of queries, and expose a read-only Context Web view. The empirical
diagnostic keeps TTWO's continuing-equity returns separate from SGEN's $229
cash-merger terminal outcome. It validates the data architecture; one TTWO event
does not establish a revision effect.

The resulting cross-branch foundation, **[CA-00](CA00_corporate_action_outcome_lab.md)**,
models what happens when securities disappear. Eight official SEC cases separate
fixed cash, successor stock, retained-parent-plus-spinoff wealth, bankruptcy
cancellation, and ticker continuity. A free-provider audit resolves only 7/12
required price roles and none of four cash-merger predecessors; time-bounded
aliases recover BBBY history under `BBBY` and FB history under `META`. The result
opens Form 25, inactive-price, wealth-chain, bankruptcy, and event-clock studies
without claiming a trading edge.

Its state-clock continuation,
**[CA-01](CA01_sec_form25_state_machine.md)**, joins announcement, approval,
completion, suspension, Form 25, listing-removal schedule, plan effectiveness,
rights conversion, and Form 15 into an observation-ordered state vector. Three
official chains contain 27 assertions across six dimensions. Twitter's exchange
filing led its issuer completion 8-K by almost twelve hours, Activision's issuer
filing led its exchange filing pre-open, and BBBY's Form 25 confirmed a suspension
68 days after the event. The stronger BBBY effective-date source also resolves its
common-equity terminal value to an explicit $0 without weakening the rule that
cancellation alone never implies zero.

Its first population-scale child,
**[CA-CLOCK100](CA_CLOCK100_form25_population.md)**, freezes all 1,141 unique
2023 Form 25-NSE accessions and a deterministic 100-filing content sample. It
catches the SEC master index's dual exchange/subject rows (2,282 raw rows), verifies
both identities against filing XML, preserves exact acceptance clocks, and exposes
security- and exchange-workflow heterogeneity. The result is a reproducible backbone
for issuer/exchange sequence, outcome, text, and market-response studies—not a
delisting-return or alpha claim.

The immediate sequence join,
**[CA-CLOCK100B](CA_CLOCK100B_action_chain_join.md)**, searches adjacent SEC
indexes around the 31 common-equity seeds and narrows 259 candidates to 80
content-review sources. Nineteen chains have a material issuer source within 36
hours of Form 25: issuer first in 12, exchange first in seven. Five missing chains
are all fund structures, exposing a separate fund-document pipeline. The clock
join passes; the 100-chain reviewed outcome gate remains open.

The first manually promoted batch,
**[CA-CLOCK100C](CA_CLOCK100C_reviewed_cash_seed.md)**, verifies 12 fixed-cash
holder conversions from exact issuer submissions. Each label carries terms,
source hash, and acceptance clock and is mechanically barred from predictive
features. The cases split six issuer-first and six exchange-first. This strengthens
the clock result but is intentionally not the diverse 100-chain panel.

The rights-aware continuation,
**[CA-NONCASH](CA_NONCASH_reviewed_seed.md)**, adds six manually reviewed chains
that cannot be represented by one cash amount: three successor-equity conversions,
one cash-plus-CVR merger, one bankruptcy with explicit zero recovery, and one
bankruptcy unresolved at the selected source. It preserves ratios and contingent
rights, distinguishes explicit zero from unknown, and uses the earliest
fact-establishing filing when duplicate later reports exist.

The fund-specific child,
**[CA-FUND](CA_FUND_reviewed_seed.md)**, closes all five structurally missing
CA-CLOCK100B chains. It recovers three exact closed-end-fund successor ratios, a
term-fund liquidation with separate cash and non-transferable trust legs, and an
ETF cash-at-NAV schedule whose amount and payment remain unconfirmed. It also
preserves an internal date conflict in an official NYSE exhibit instead of
silently repairing the source.

The first negative-outcome child,
**[CA-FAILFRAME](CA_FAILFRAME_termination_seed.md)**, collapses one frozen SEC
full-text query from 31 document hits to 23 submissions and 14 unique in-year
deal terminations. Five matches are false or wrong-period events and four are
counterparty/amendment duplicates. Half the primary sources arrive one to five
calendar days after the date-only termination event. This is a reviewed
failure-schema seed, explicitly not a failure-rate or prediction cohort.

Its literature and model continuation,
**[CA-ANNOUNCE](CA_ANNOUNCE_model_blueprint.md)**, turns those failure lessons
into an announcement-time, three-outcome, censored forecasting contract. It
requires calibrated market-implied, logistic, and survival baselines before
tree or language models; immutable point-in-time evidence; deal-grouped
chronological splits; and a free public deal card with official-source links and
visible uncertainty.

The first implementation child,
**[CA-ANNOUNCE cohort seed](CA_ANNOUNCE_cohort_seed.md)**, freezes a six-deal
schema pilot with a 2025-01-01 censor, exact clocks for ATVI/TWTR, and an
explicit higher-bid vs negative-termination split. It is not a population, has
zero right-censored deals, and blocks survival claims until an announcement-search
cohort includes unresolved observations.

The population gate,
**[CA-ANNOUNCE-POP](CA_ANNOUNCE_POP_discovery.md)**, freezes a January 2023
`entered into an Agreement and Plan of Merger` SEC search (106 docs → 93
submissions). Only 47 carry Item 1.01 — phrase hits are not entry events. No
outcomes are assigned.

Its review child,
**[CA-ANNOUNCE-REVIEW](CA_ANNOUNCE_REVIEW_cohort.md)**, joins exact announcement
clocks for 11 deals and forces two right-censored observations at 2025-01-01
(WBA, Orchestra), unblocking survival framing while leaving raw content hashes
open.

Cash baseline step 0,
**[CA-ANNOUNCE market-implied](CA_ANNOUNCE_market_implied.md)**, implements the
clip((price−downside)/(cash−downside)) proxy on fixture snapshots.

Rhetoric step 0,
**[CA-RHETORIC](CA_RHETORIC_delta_seed.md)**, extracts transparent
appeared/disappeared/unchanged deltas over a frozen phrase family on synthetic
deal chains.

> **Why this exists.** The headline performance in `CLAUDE.md` (Sharpe 25–94, "production-ready")
> is **superseded** — it came from optimistic-mode backtests on morning-only data ([[F13]]), and
> the live bot is flat. The go/no-go ([[D6]]) found the active engine has no risk-adjusted edge
> over a trivial static allocation. This program tests that conclusion to destruction, then asks
> what the honest product really is.

## The shared methodology

Every study uses the same disciplines, which is what makes the collection trustworthy:

- **Leak-free** — entries/weights use only lagged information (`.shift(1)`); windows verified
  byte-identical to a truncated re-computation.
- **Bootstrap confidence intervals** — paired block bootstrap (block=20, B=5000, seed=0) of the
  *difference* vs the benchmark, so every claim is a CI, not a point estimate. (Promoted from the
  research lab into a shared, unit-tested module: [`src/backtest/uncertainty.py`](../../src/backtest/uncertainty.py).)
- **Pre-registration & out-of-sample discipline** — pass criteria stated before the test; the one
  live hypothesis (gold) was settled on a genuine disjoint holdout.
- **Adversarial verification** — studies 1–15 were checked by 2–5 lens skeptic panels
  (construction, leak-freeness, statistics, interpretation) that re-ran the code and tried to
  refute the verdict. Studies 16–69 instead expose explicit ordering bounds, paired controls,
  cross-runtime output, and mechanism-scoped caveats; independent panel review remains future work.
- **One source of truth** — all studies reuse the same vetted primitives; no divergent Sharpe or
  drawdown implementations.

## The sixty-nine studies

Studies 1–10 are the **active-vs-static** arc (does MONAD's engine beat a static allocation, and what is the honest product). Studies 11–12 are a follow-on **product-universe** program (is there a *better asset universe* than the static 60/40 the arc landed on — and does the one structural escape, a held-to-maturity ladder, actually deliver). Study 13 is the **regime stress** — the whole program's recommendations were measured inside the 2000–2021 *negative* stock-bond-correlation regime; #13 tests them in the positive-correlation/inflation regime that covers most of the last 64 years. Studies 14–15 close #13's two open ballast questions: can a marked-to-market **TIPS sleeve** or a **fixed ballast composition** escape the regime trade-off? (No, and no — but the failure is constructive.)
Studies 16–69 return to the live reference implementation: #16 quantifies the **overnight gap
tail**, #17 audits **backtest/live execution semantics**, #18 tests **mitigation trade-offs**
without promoting in-sample clock selection, and #19 checks the mechanism over **16 years and
eight instruments**. #20 asks whether the entry-ordering sample is sufficient to calibrate the
simulator; #21 tests lower-turnover **weekend/holiday partial flattening**; #22 rescues expiring
**one-minute evidence**; #23 measures **gap clustering and lagged-volatility controls**; #24
stress-tests mitigation under **dependence, auction cost, and post-selection**; #25 tests
whether the volatility rule survives **lookback changes and an early threshold split**; and #26
turns the survivor into a **fixed-horizon forward protocol** and audits paper-trading limits;
and #27 compares it with **transparent recent-gap null controls**; #28 separates raw capture
from **year-level discrimination and blanket regime exposure**; and #29 audits **input hashes,
vendor revision risk, and repo-only reconstruction limits**; #30 calibrates volatility capture
across **routine stop gaps through catastrophic discontinuities**.
Study #31 separates **raw stop triggers from ex-dividend wealth accounting**.
Study #32 audits **first-hour opens and missing intraday session bars**.
Study #33 consolidates both corrections into one **authoritative execution ledger**.
Study #34 tests whether mitigation survives the alternative **last-hourly close proxy**.
Study #35 freezes a **closing-auction evidence protocol**, corrected by #43.
Study #36 tests whether **QQQ ex-dividend returns contaminate the volatility classifier**.
Study #37 proves the classifier's **pre-close decision chronology** and quantifies lookahead.
Study #38 asks whether the selected threshold sits on a **local robustness plateau**.
Study #39 decomposes **direct risk removal from replacement-trade path drift**.
Study #40 measures whether that direct benefit is **too concentrated in a few events**.
Study #41 block-resamples the corrected **fixed-cohort direct effect** under dependence.
Study #42 audits the fixed-cohort intervention's **favorable rate and outcome anatomy**.
Study #43 proves the standard Cross **fill/NOCP identity**, repairs #35's cost endpoint, and
separates operational failure, observable fees, and unidentified self-impact.
Study #44 audits the current **runtime readiness** and finds the MOC path absent plus an
independent early-close scheduling gap.
Study #45 quantifies the broader **exchange-calendar failure** and duplicate state transitions on
closed/short sessions.
Study #46 replays every vulnerable date in the pinned window against **causal signals and clean
position state**, correcting the early-close duplicate count.
Study #47 finds **observed holiday cycles** in the sanitized Pi archive and scopes a separate
historical double-write interval.
Study #48 shows the double writes were **decision- and submission-path material**, with 69 paired
signal disagreements and seven double entry-success minutes.
Study #49 identifies an exact **UTC-naive versus host-local clock defect** behind the paired-bar
pattern and proves the current completion/staleness rule remains environment-dependent.
Study #50 measures the consequence directly: **297/543 archived signals and at least 40/65 entry
minutes used an in-progress hourly bar**, so live PnL is not completed-bar validation.
Study #51 audits **process and per-bar order ownership**: only two of six launch paths reach the
full preflight/named unit, while no path holds an atomic cross-process lock or durable order-intent
key. The current broker-position guard usually fails safe, but does not exclude a second bracket
while the first parent remains working and unfilled.
Study #52 audits **entry acknowledgement and price provenance**: local success follows three
submission calls but no broker status/fill check, and `fill_basis` is a pre-submission quote. The
47-row exit-confirmed archive crosses zero with only 0.435 bp of adverse entry-basis error, so the
flat verdict stands while the former fully “CONFIRMED” label does not.
Study #53 traces the unresolved consequence: a locally recorded but economically unfilled parent
can be converted into an inferred TP/SL round trip when positions are flat and no child execution
is found. The archive proves five execution-unverified inferred rows and three immediate re-entry
events, but cannot prove those historical parents were unfilled.
Study #54 audits the other side of that fork: even a recovered exit uses client order-number
matching without permanent/execution identity or quantity aggregation, while IB Gateway cannot
honor the code's intended seven-day execution fallback beyond midnight.
Study #55 proves the local close is not exactly once: two SQLite connections can cache the same
position and sequentially commit two trade rows, while a losing caller cannot distinguish its
no-op from success before sending alerts or evaluating re-entry.
Study #56 proves a distinct generation race: after one cycle closes and re-enters, an older cycle
can attach its old exit economics to the new position's metadata and then delete the new row,
because close carries no expected lifecycle identity.
Study #57 audits the entry labels themselves: target, stop, and stored basis are anchored to the
pre-submission quote while quantity is anchored to the signal bar, so an adverse permitted parent
fill deforms 1.0%/0.5% reward:risk from 2.0 to approximately 0.5.
Study #58 proves force-close quantity is not broker-reconciled: a partial parent or child fill
during unconfirmed cancellation can make a full-local-quantity market close overshoot flat and
create the opposite position.
Study #59 audits what “closed” means after that order is sent: the first observed execution is
treated as full completion and one component price as VWAP, while a ten-second timeout still
causes estimated PnL and local deletion. Four of nine archived time exits crossed that observed
uncertainty boundary.
Study #60 audits the successor boundary: same-cycle re-entry checks the broker position but no
working-order state. The archive contains 32 back-to-back application entries, including two
about 14 seconds after explicit time-exit fill-unavailable warnings; late old-order execution
remains a reachable but historically unidentified collision.
Study #61 audits **account/model scope**: summary sizing is last-row-per-tag, positions are the
first symbol match, orders have no explicit destination, and state retains no account identity.
The multi-account failure is deterministic but conditional; sanitized evidence cannot say whether
the current Gateway exposes more than one account.
Study #62 measures a directly observed duplicate-writer state effect: seven of nine archived time
exits reached `bars_held=10` through exactly five double-written cycle minutes, and eight used
fewer than ten distinct slots. This proves holding-clock compression, not its PnL sign.
Study #63 audits the **quote anchor itself**: prior-day close and any positive out-of-spread last
preempt a valid spread, while 15–20-minute delayed data are accepted without field/type/timestamp
evidence. A pinned recent TQQQ stress panel shows the 0.5% order offset is not a staleness bound.
Study #64 audits the **decision clock** around that quote: each entry makes separate mark and
order snapshots with no deadline or signal revalidation. The byte-matched archive records
application success 14.377–62.949 seconds after the nominal cycle anchor.

| # | Study | Question | Honest finding | Nodes · Doc |
|---|---|---|---|---|
| 1 | Power & equivalence | Is D6's "no edge vs static" genuine, or just underpowered? | Mostly **evidence-of-absence** — TOST equivalence to static within ~0.3 Sharpe over 26.5yr; the MR *signal* is provably real but provably *not* tradeable-better-than-static. | E25/F34 · [doc](D6_power_equivalence_study.md) |
| 2 | vs the recommended 60/40 | Does active beat the *decision-relevant* static 60/40 (not the easier 50/50)? | **No** — lower point Sharpe (−0.17/−0.26), nearly significantly worse over 24yr. | E26/F35 · [doc](D6_active_vs_6040_study.md) |
| 3 | Crisis low-drawdown overlay | Is the active engine's drawdown protection concentrated in crises? | **Real but small-N** — reliable vs naked buy&hold (8/8), not vs 60/40; paid for by calm-market under-participation → Sharpe ≈ static. | E27/F36 · [doc](D6_crisis_overlay_study.md) |
| 4 | Best build (overlay) | Does *any* active overlay (constant-weight or regime-conditional) improve a 60/40 core? | **No build** clears the bootstrap; the engine is a capital-preservation overlay, never a risk-adjusted edge. | E28/F37 · [doc](D6_overlay_build_study.md) |
| 5 | Optimize the static product | Honest 60/40 ceiling, rebalancing realism, a third sleeve? | ~Sharpe 0.85 (dividends add only +0.03); rebalance-robust; **no single sleeve reliably improves it** (gold borderline, best-of-3, fails Bonferroni). | E29/F38 · [doc](D6_static_product_study.md) |
| 6 | Out-of-sample gold test | Does study #5's gold sleeve survive a clean 2004–2013 holdout? | **Does not confirm** (holdout straddles 0, though underpowered) — a discretionary diversifier, not a confirmed upgrade. | E30/F39 · [doc](D6_gold_oos_study.md) |
| 7 | Structural levers | Does vol-targeting or risk parity beat the fixed 60/40? | **Neither** — vol-timing is an unreliable tilt (leverage is Sharpe-invariant); risk parity is a bond-bull regime bet that reverses OOS. | E31/F40 · [doc](D6_voltarget_riskparity_study.md) |
| 8 | Forward expectation | At 2026 yields, does the 60/40 meet the ~3.75% income goal (D4)? | Forward ~5–6%/yr **clears the income goal** (P≈67%), but with ~−23% median worst drawdown it **fails the "near-zero drawdown" aspiration**. | E32/F41 · [doc](D6_forward_expectation_study.md) |
| 9 | Goal-optimal mix | Is 60/40 the right static mix for *this* goal? | **No — too equity-heavy.** A more conservative ~30–40% equity mix weakly dominates 60/40 (higher goal-odds, Sharpe, *and* shallower drawdown) because forward bonds out-Sharpe forward equity; but no mix clears 3.75% reliably (best ~70%). | E33/F42 · [doc](D6_weight_optimization_study.md) |
| 10 | Live ↔ backtest reconciliation | *Why* is the live bot flat vs the Sharpe-25 backtest? (quantifies F28) | The bot trades a **coarse-timescale signal at an hourly frequency with no edge** (autocorr negative daily, ~0/positive hourly). **Both headlines are mirages** — the backtest's from morning-only sampling, the live dashboard's +37% from exit-accounting. Study #52 later corrects “CONFIRMED +1.5%” to **exit-confirmed on a quote-derived entry basis**; the conclusion remains flat. | E34/F43/F87 · [doc](D6_live_backtest_reconciliation.md) |
| 11 | Income product universe | Is there a *better asset universe* (munis, credit, preferreds, options-income, dividend/low-vol, treasuries) than the static 60/40? | **No** — across this liquid cross-section **high yield ≠ low drawdown**: the income-rich names (PFF/HYG/JNK/options-income) carry equity-like-or-worse drawdowns *and* erode principal (QYLD spend-the-income DD −42%); **nothing** clears the ~3.75% income floor with even a <20% drawdown. The lever that beats 60/40 on drawdown is still study #9's (tilt conservative). The one structural escape (untested) is a held-to-maturity IG/Treasury **ladder**. | E35/F44 · [doc](D6_product_universe_study.md) |
| 12 | Held-to-maturity ladder | Does the ladder (#11's structural escape) actually deliver income with low drawdown? | **Yes — but it trades risk, not eliminates it.** Realized (hold-to-maturity) drawdown ~0 at ≈entry yield (1962–2026 sim + real iBonds/Bullet ladders), but: the 0% is *amortized-cost definitional*; the MTM-drawdown reduction is *just lower duration* (SHY beats the 2020 ladder on both return and DD); it's *nominal only* (−19% **real** in the 1970s); and floor-clearing is *forward-only* (no empirical ladder cleared 3.75%). Converts market risk → term + reinvestment + inflation risk + zero upside. | E36/F45 · [doc](D6_bond_ladder_study.md) |
| 13 | Bonds-don't-hedge regime stress | Do the recommendations survive the positive stock-bond-correlation / inflation regime (the historical norm — bonds hedged in only ~22 of the last 64 years, and the regime re-flipped positive in 2022)? | **They are regime-conditional.** The conservative tilt (#9) keeps its shallower-*nominal*-DD edge (coupon-honest CI excludes 0) but its excess-Sharpe advantage **disappears** positive-corr, and in **real terms it inverts**: the 40/60 lost **−36% to −41% of purchasing power** in 1965–81 (deeper than 60/40) — *every* bond-heavy mix lost real wealth for a decade. Cash ballast **mitigates** (−27% real) but loses on every metric in 2000–2021 — duration is a **regime trade-off**. Forward fix for the real hole: a **TIPS ladder** at ~2.3% real (forward, amortized-cost-basis claim). The *nominal* 3.75% goal was regime-robust; purchasing power was not (~51% of inflation-era decades). D6 stands. | E37/F46 · [doc](D6_correlation_regime_study.md) |
| 14 | TIPS sleeve | Does carving 5–20% of the mix's bond leg into TIPS (TIP/STIP/VTIP) buy inflation protection (#13's open middle ground)? | **No sleeve earns a place — the observed benefit is duration-shortening in disguise.** Full-duration TIP sleeves do nothing; short-TIPS sleeves improve the 2022+ cut but fail the family-wise correction, cost Sharpe/DD in the bonds-hedge regime, and are **statistically indistinguishable from a duration-matched *nominal* sleeve** on both DD and Sharpe (the draft's "carry hint" was a residual-duration artifact the panel caught). Scope: 2022 was a *real-yield* shock — MTM TIPS' worst case; the null is mechanism-scoped. The honest TIPS exposure remains #12/#13's held-to-maturity ladder. | E38/F48 · [doc](D6_tips_sleeve_study.md) |
| 15 | Regime-agnostic ballast | Does any *fixed* ballast composition (cash/bond blends, duration barbell) weakly dominate both the 7yr-bond and T-bill poles across both correlation regimes? | **No — the ballast is an irreducible regime bet.** Every composition concedes a robust shortfall to the era-best pole in at least one regime; at matched duration the barbell is indistinguishable from the bullet (within nominal Treasuries the question is one-dimensional: *how much duration*). Constructive: the **minimax-regret 50/50 cash+7yr** halves the worst-case bet (0.49 vs the poles' 1.00), and *every* blend beats *both* poles on full-sample excess Sharpe — diversification softens the bet; nothing removes it. Proxy-robust (coupon-honest re-run). | E39/F49 · [doc](D6_ballast_blend_study.md) |
| 16 | Overnight gap-through-stop risk | How much risk does the hourly backtest omit by filling every 0.5% stop exactly, even across session gaps? | **Materially understates the left tail.** In a live-shaped, long-only two-year TQQQ replay, 34/127 overnight holds open through the stop; exact fills report −5.17% total / −5.88% maxDD at fixed 10% sizing versus **−10.15% / −10.19%** with open-aware fills. A 7.0bp scalar stop penalty matches the mean but misses a 1.03pp median / 8.96pp maximum conditional tail. EOD flatten removes the channel but still loses money. | E40/F50 · [doc](D6_overnight_gap_risk_study.md) |
| 17 | Execution-semantics waterfall | Does the research runner actually reproduce the live trade path, especially during the entry hour? | **No—and hourly OHLC cannot identify the repair's return sign.** N+2 matches the engine exactly, but 980/1,516 entries touch a bracket in N+1. Immediate-bracket performance spans −7.61% stop-first to +16.91% target-first because 157 entry hours hit both levels. Recent 5m calibration leans stop-first (11 vs 5 resolved), but is small and clustered. | E41/F51 · [doc](D6_execution_semantics_study.md) |
| 18 | Gap-mitigation frontier | Which controls remove jump risk without mistaking in-sample trade selection for alpha? | **Direct exposure removal is the only clean mechanism.** Corrected EOD flatten removes 34/34 gaps and improves maxDD 3.44pp but remains −5.77%; the sample benefit allows a rough 34.7bp extra-cost budget across 126 exits. Noon/13:00 cutoffs repeat the known morning-only selection failure. Stop width never bounds the 7.46–9.21pp conditional jump tail. | E42/F52 · [doc](D6_gap_mitigation_frontier_study.md) |
| 19 | Cross-instrument gap history | Is TQQQ gap risk a recent signal accident or a structural leveraged-instrument property? | **Structural across 2010–2026.** TQQQ's 1% overnight quantile is −6.69%, worst-1% mean −10.33%, and 11.71% of nights open down ≥2%. Gap beta vs QQQ is 2.95 (R² .993); all 2×/3× pairs recover near-nominal leverage. At 10% position size, TQQQ's historical ES1/worst translate to −1.03%/−2.88% of account before liquidity. Unconditional scenarios, not sizing advice or a strategy forecast. | E43/F53 · [doc](D6_cross_instrument_gap_history.md) |
| 20 | Entry-bar calibration sufficiency | Can 16 resolved five-minute events calibrate target-first probability well enough to repair the hourly simulator? | **No for the exact-stop question; the threshold is too close.** The overlapping diagnostic needs 33.76% target-first vs 31.25% observed and would require ~1,339 resolved events for a Wilson interval to clear the threshold at that rate. The open-aware one-position path needs 52.17% vs 28.57% observed; model-based P(total>0) is only 1.2%–20.4%, but remains conditional on exchangeability. Resolve the three remaining events and obtain historical lower-timeframe/order-event data—do not patch from 16 examples. | E44/F54 · [doc](D6_entry_bar_calibration_study.md) |
| 21 | Calendar-aware partial flatten | Can weekends/holidays capture most gap risk with far fewer exits than flattening daily? | **They capture disproportionate damage, not most events.** Eight weekend/long-closure gaps are 44.08% of damage but only 23.53% of events. After correcting a pre-entry flatten bug and using official closes, a ≥3-day rule uses 29 vs 126 exits and improves the path to −8.61%/−8.65%, yet fails the 50%-event/2pp-DD gate. Adding 2-day holiday eves adds four exits, removes no event, and worsens the path. | E45/F55 · [doc](D6_calendar_gap_mitigation_study.md) |
| 22 | One-minute ambiguity resolution | Can the three unresolved five-minute entry bars be recovered before minute-history retention expires? | **One recovered, stop-first; two expired.** July 6 hit the stop at 09:30 and target at 09:34. Best counts become 5 target-first / 12 stop-first / 2 unresolved. The exact-stop sign remains unidentified; gap-aware model-based P(positive) tightens to 1.24%–9.89%. | E46/F56 · [doc](D6_one_minute_entry_resolution_study.md) |
| 23 | Gap clustering and volatility control | Are severe gaps independent, and can a lagged-volatility state capture weekday risk? | **Gaps cluster; volatility works only broadly.** Next-night ≤−2% risk is 1.34× after a severe gap. A 15% lagged-QQQ-vol rule removes 62% of strategy gaps with 66 exits, but disables 56.5% of all nights and 75.3% since 2020. Same-sample hypothesis, not alpha. | E47/F57 · [doc](D6_gap_cluster_volatility_study.md) |
| 24 | Mitigation uncertainty and cost | Do daily, weekend, or volatility flatten survive dependence and auction-cost stress? | **Daily/volatility survive same-path blocks; weekend does not.** Block-20 relative-wealth CIs are +1.82%–+8.58%, −0.50%–+4.70%, and +1.99%–+7.83%. Break-even costs are only ~34.7/53.2/61.3 bp per exit; the volatility threshold is post-selected. Freeze only for forward paper-shadow fills. | E48/F58 · [doc](D6_mitigation_uncertainty_cost_study.md) |
| 25 | Volatility lookback / early split | Does the 20-day/15% rule survive alternative memories and a threshold chosen only on 2010–2019? | **Specific rule partly survives; generic vol timing does not.** The 20d/15% rule captures 85.3% of severe 2020–2026 gaps and removes 61.8% of strategy gaps. The 10d rule fails the strategy gate; 40/60d rules pass with 96/104 exits, approaching daily flatten. Classifier robustness, not prospective strategy validation. | E49/F59 · [doc](D6_volatility_lookback_oos_study.md) |
| 26 | Forward shadow evidence design | How long must a frozen trial run, and can IBKR paper fills validate MOC cost? | **Multi-year, and paper cannot identify auction cost.** Strategy capture needs 115 new gap events (~6.7yr) for 80% power under iid planning; heuristic clustering effects extend this to ~8.4–13.3yr. The surrogate needs 62 (~2.1yr). IBKR paper lacks Auction orders/real fills, so it cannot clear the 61.3 bp real-MOC cost gate. | E50/F60 · [doc](D6_forward_shadow_validation_design.md) |
| 27 | Simple risk-classifier benchmarks | Does lagged volatility concentrate severe gaps better than merely reacting to recent severe gaps? | **Not unconditionally; yes on this selected strategy path.** Vol20's 1.33× capture lift matches prior-1–5 rules' 1.31×–1.38×. But vol20 removes 61.8% of strategy gaps while exposure-near prior-10 removes 47.1%; recent-gap passes only at 82.9% exposure. Same-sample alignment, not unique predictive structure. | E51/F61 · [doc](D6_simple_risk_classifier_benchmarks.md) |
| 28 | Volatility regime stability | Is the rule's 85% recent capture genuine discrimination or broad exposure across volatile years? | **Mostly broad exposure; discrimination is unstable.** The rule flagged 100% of 2022 (lift 1), 84% of 2020/2023 (lift ~1), and in 2024 captured only 54.5% while flagging 59.1% (lift 0.92). Only 2025 shows strong recent concentration (1.38×). Raw capture cannot shorten the forward strategy trial. | E52/F62 · [doc](D6_volatility_regime_stability.md) |
| 29 | Input provenance audit | Are the exact vendor inputs identified, and can a fresh clone reconstruct the studies? | **Byte-auditable now, not repo-self-contained.** All six caches match embedded SHA-256 snapshots and a committed manifest. Raw vendor bytes remain only in `/tmp`; revisions/retention can prevent later reconstruction. A refresh requires a new hash and result diff. | E53/F63/F71 · [doc](D6_input_provenance_audit.md) |
| 30 | Gap-severity calibration | Is vol20 a predictor of ordinary stop gaps, catastrophic gaps, or a hard loss bound? | **Catastrophic-state flag, not precise stop predictor or bound.** At the 0.5% stop it captures 62.8% with 56.5% exposure (1.11× lift); at 4%–8% losses lift rises to 1.57×–1.70×. Unflagged worst remains −10.54% (about −1.05% of account at 10% position). | E54/F64 · [doc](D6_volatility_gap_severity_calibration.md) |
| 31 | Corporate-action gap audit | Do ex-dividend price drops inflate the gap tail or mitigation benefit? | **Real correction, immaterial conclusion.** Cash removes only 2/1,289 ≥0.5% raw gaps and no ≥2% gaps; none of 34 strategy gap stops is on an ex-date. Two earned distributions improve baseline only +0.0338 pp; all paths and mitigation verdicts remain negative/unapproved. | E55/F65 · [doc](D6_corporate_action_gap_audit.md) |
| 32 | Session-open source audit | Does the first hourly bar reliably represent the session open? | **Two corrupt partial sessions, but no rescue.** Jan 30 has two morning bars; Feb 2 starts at 13:30 and misstates open by 463.7 bp. Daily-open substitution changes 18 trades and worsens total/maxDD 0.058 pp; excluding both sessions worsens ~0.088 pp. Per-session validation is required. | E56/F66 · [doc](D6_session_open_source_audit.md) |
| 33 | Corrected execution ledger | What is the authoritative baseline after applying the open-source and distribution corrections together? | **Still materially negative.** Daily-open, distribution-inclusive hold is −10.1713% / −10.2126% maxDD. Vol15 and daily flatten retain descriptive risk-gate passes, with only 62.58/34.89 bp per-exit cost ceilings and no production approval. | E57/F67 · [doc](D6_corrected_execution_ledger.md) |
| 34 | Close-proxy policy sensitivity | Do mitigation conclusions depend on official daily close instead of the last hourly close? | **No material dependence, but still no fill evidence.** Official-vs-hourly changes total return only +0.0778 pp for vol15 and +0.0344 pp for daily flatten; both descriptive gates survive. The conservative cost ceilings are 61.40/34.62 bp, and neither proxy represents an auction fill. | E58/F68 · [doc](D6_close_proxy_policy_sensitivity.md) |
| 35 | Closing-auction evidence protocol | What real evidence can the project retain under Nasdaq/IBKR rules? | **Corrected by #43.** The 60-event denominator is all intended flattens, not completed fills; zero rejects/unfilled events bounds operational failure below 4.87% one-sided. Standard fill-minus-NOCP is not an independent cost endpoint. | E59/F78 · [doc](D6_closing_auction_evidence_protocol.md) |
| 36 | Volatility distribution audit | Do QQQ ex-dividend drops manufacture vol20 states or the mitigation result? | **Five marginal labels, zero strategy changes.** Distribution-inclusive returns flip only 5/4,113 threshold dates and none intersect a flatten decision; the corrected policy remains exactly −6.0411% / −6.7539%, 66 exits, 11 gaps. Use the correct input anyway. | E60/F70 · [doc](D6_volatility_distribution_audit.md) |
| 37 | Volatility decision-time audit | Is vol20 known before the MOC lock, and what happens if the current close leaks in? | **The lag is exact and feasible.** 4,113 truncated recomputations match to 2.5e−15 and use only t−1 data. Unshifted lookahead flips 147/20 labels (history/recent), produces 65 exits/12 gaps and a worse −6.2049% path. Never use the current close. | E61/F72 · [doc](D6_volatility_decision_time_audit.md) |
| 38 | Local volatility-threshold robustness | Is the 15% policy a knife-edge under small threshold/data perturbations? | **No; 14–16% is a local plateau.** All 9 quarter-point thresholds pass the descriptive gate; totals stay −6.24% to −5.68%, maxDD −6.97% to −6.50%, exits 61–75, gaps 7–12, cost ceilings 59.11–65.23 bp. Robustness is not reselection or forward proof. | E62/F73 · [doc](D6_local_volatility_threshold_robustness.md) |
| 39 | Mitigation path decomposition | Does flattening help the same baseline positions, or only by admitting favorable replacement trades? | **Vol15 is direct; daily path drift hurts.** Vol15's fixed-cohort delta is +4.1299 pp versus dynamic +4.1302 pp (path +0.0003 pp). Daily's fixed +5.1691 pp falls to dynamic +4.3967 pp (path −0.7724 pp). The selected risk mechanism does not borrow replacement alpha. | E63/F74 · [doc](D6_mitigation_path_decomposition.md) |
| 40 | Mitigation benefit concentration | Is vol15's direct benefit a one-disaster artifact? | **Concentrated, not singular.** Of 67 changed trades, 43 help and 24 hurt. Removing the largest event retains 75.84% of direct benefit; removing top five retains 42.75% (+1.7657 pp), top ten 17.27% (+0.7134 pp). Most benefit occurs in 2025, so forward evidence remains essential. | E64/F75 · [doc](D6_mitigation_benefit_concentration.md) |
| 41 | Fixed-cohort dependence stress | Does direct loss avoidance survive daily clustering after removing replacement-path effects? | **Yes in sample.** Vol15 corrected fixed-cohort relative wealth is +4.5976%; block-5/20/60 CIs are [+1.850,+8.135], [+1.860,+8.314], and [+1.796,+8.297]%. All annual slices are positive. This validates historical mechanism, not forward prediction or auction execution. | E65/F76 · [doc](D6_fixed_cohort_dependence_stress.md) |
| 42 | Flatten intervention outcomes | How often does an early close improve a fixed baseline trade, and what does it sacrifice? | **Vol15 helps 43/67 (64.2%, Wilson 52.2–74.6%, p=.0136 vs 50%).** All 21 eventual gap stops and 22 other stopped/ambiguous losers improve; all 24 eventual targets are harmed. Daily is only 70/127 (55.1%, p=.1435). The mechanism is asymmetric loss avoidance, not precise prediction. | E66/F77 · [doc](D6_flatten_intervention_outcomes.md) |
| 43 | Closing-auction benchmark identity | Can MOC fill minus published NOCP measure TQQQ auction cost? | **No for a standard qualifying Cross.** Nasdaq rules make fill = Cross price = NOCP; the difference is reconciliation, not slippage. A 60-intended-event gate measures rejects/unfilled risk (zero implies a 4.87% upper bound), observable fees are only 0.20–0.40 bp at $80–$40, and self-impact remains unidentified. | E67/F78 · [doc](D6_closing_auction_benchmark_identity.md) |
| 44 | Closing-auction runtime readiness | Does the current paper trader have the clock, decision, order, calendar, and evidence plumbing required for MOC? | **Not ready.** The 15:32 cycle leaves 18/23 nominal minutes to Nasdaq's lock/cutoff, but the vol20 decision, MOC path, deadline guard, exchange calendar, and NOCP/NOII schema are absent. The hard-coded 16:00 guard also admits 13:32/14:32/15:32 jobs after official 13:00 early closes. | E68/F79 · [doc](D6_closing_auction_runtime_readiness.md) |
| 45 | Closed-session scheduler audit | How many 2026 jobs run outside Nasdaq's calendar, and can repeated bars mutate state? | **76 jobs are admitted: 70 on ten closed weekdays plus six after two early closes.** The 120-hour freshness allowance lets prior-session bars pass; without a bar-time idempotency gate, repeated cycles can mutate holding state. Study #46 corrects the sample-specific early-close duplicate count. | E69/F81 · [doc](D6_exchange_calendar_closed_cycle_audit.md) |
| 46 | Pinned calendar-misfire materiality | Do vulnerable cycles coincide with reusable signals and clean-path positions? | **Yes, structurally—not as observed orders.** The pinned window contains 162 off-calendar jobs; 65 overlap a clean-baseline open-position state, and nine dates are clean-flat with a nonzero reused signal. All 15 post-close jobs across five early sessions reuse an 11:30 bar already processable at 12:32. | E70/F81 · [doc](D6_pinned_calendar_misfire_materiality.md) |
| 47 | Sanitized holiday-runtime evidence | Did the archived paper runtime actually execute cycles on closed dates? | **Yes; downstream trading was blocked by outage, not calendar logic.** Good Friday has 8 signal rows over 4 slots with signal +1; Memorial Day has 14 over all 7 slots. All 22 hit paper-port connection failures and neither date has a trade endpoint. Every slot was double-written; archive-wide 210/333 minute slots have two writes, a historical concurrency issue not automatically attributable to current deployment. | E71/F82 · [doc](D6_sanitized_holiday_runtime_evidence.md) |
| 48 | Historical duplicate-writer forensics | Did paired historical cycles disagree on decisions or reach the order path twice? | **Yes at the application layer.** Of 210 paired minutes, 69 disagree on the signal and 58 on long eligibility. Seven of 65 entry minutes emit two success events, proving seven extra bracket paths/21 extra `ib.placeOrder` calls while the local trade table retains only the later state. Broker acceptance and fills remain unknown. | E72/F83 · [doc](D6_historical_duplicate_writer_forensics.md) |
| 49 | Live bar-completion timezone audit | Is completed-bar selection invariant to host timezone and vendor-tail availability? | **No.** UTC-naive bar labels are compared with host-local-naive time. London BST can accept the in-progress bar; the New York service can drop the completed bar when the current tail is absent and shifts the true 120h stale boundary to 124/125h. The archive's 13-identical/197-divergent DST pattern matches the mechanism exactly. | E73/F84 · [doc](D6_live_bar_completion_timezone_audit.md) |
| 50 | Archived incomplete-bar materiality | How much historical live evidence used a bar before its hour completed? | **At least 61.5% of entry minutes.** True-UTC aging finds 297/543 signal rows about two minutes into the hour, including 100/123 single writes. A strict no-cycle-ID join attributes 40/65 entry minutes and 33/47 archive-confirmed local trades to incomplete information. The flat verdict remains, but this is not completed-bar validation. | E74/F85 · [doc](D6_archived_incomplete_bar_materiality.md) |
| 51 | Trader singleton and launch safety | Do current controls prove exactly one trader and one order intent per symbol/bar? | **No—safer, but not exactly once.** Two of six launch paths reach the full preflight; four bypass it. `pgrep`, per-scheduler `max_instances`, retried client ID 1, broker-position checks, and SQLite write serialization do not jointly exclude a second bracket while the first parent is working but unfilled. This is reachability, not historical attribution. | E75/F86 · [doc](D6_trader_singleton_launch_safety_audit.md) |
| 52 | Entry acknowledgement and basis | Does `ENTRY placed` prove acceptance/fill, and is `fill_basis` an execution? | **No.** Three application calls return, but zero status/fill/open-order checks occur before local success; `fill_basis` is the pre-submission quote. The 47-row exit-confirmed archive is +0.2047% and crosses zero at +0.435 bp adverse entry error. Flat still means flat; execution is not fully confirmed. | E76/F87 · [doc](D6_entry_acknowledgement_basis_audit.md) |
| 53 | Unfilled-parent / phantom-trade audit | Can a local entry with no economic parent fill later become a recorded TP/SL trade? | **Yes, as a reachable path; historical attribution remains unproved.** Broker-flat plus missing child fill always forces TP/SL inference without checking active/rejected parent state. Six warnings join to five unique execution-unverified `target_hit` rows; three immediately re-enter. The five compound +5.1204% as a ledger slice, but the 47-row exit-confirmed flat result excludes them. | E77/F88 · [doc](D6_unfilled_parent_phantom_trade_audit.md) |
| 54 | Bracket-fill identity and retention | Does a recovered exit have durable identity/VWAP, and can Gateway retrieve seven days? | **No.** All tiers rely on client API order IDs, two use `parent+1/+2`, no tier checks symbol/permId/execId/quantity, and one component price substitutes for VWAP. Gateway exposes executions only since midnight, so the seven-day filter cannot recover prior-day fills; 4/5 inferred rows cross a UTC date. | E78/F89 · [doc](D6_bracket_fill_identity_retention_audit.md) |
| 55 | Concurrent close idempotency | Does SQLite guarantee one local close under concurrent cycles? | **No.** Both connections can complete `SELECT` before DML begins, cache one position, and sequentially commit two trade rows because no unique lifecycle key exists. May 6 happened to produce two warnings/one row; that is not an invariant. A losing caller also continues with alerts and possible re-entry. | E79/F90 · [doc](D6_concurrent_close_idempotency_audit.md) |
| 56 | Cross-generation close/re-entry | Can an old cycle close and erase a newer re-entry? | **Yes, as a reachable schedule.** Close accepts no expected lifecycle ID, independently selects the current row, mixes it with caller-supplied old exit economics, then deletes unconditionally. The cut-point test maps bracket 100's exit onto bracket 200 and erases 200. The archive cannot test this because 0/14 duplicate-entry events and no closed trade retain parent identity. | E80/F91 · [doc](D6_cross_generation_close_reentry_audit.md) |
| 57 | Quote-anchored bracket geometry | Are the 1% target, 0.5% stop, and 10% position fill-relative? | **No.** At the parent buy-limit cap, the no-rounding geometry is +0.4975%/−0.9950% from fill and reward:risk falls from 2.0 to 0.5. A strict 66/72-event sizing join bounds the largest permitted allocation near 10.344%–10.383% versus a 10% plan. These are admissible bounds, not realized fills. | E81/F92 · [doc](D6_quote_anchored_bracket_geometry_audit.md) |
| 58 | Partial-fill force-close quantity | Does a forced exit close the fresh signed broker quantity and prove flat? | **No.** Any nonzero broker quantity enters normal management, but all three force-close paths use the full requested local quantity. A 50/100 parent fill followed by `SELL 100` leaves short 50; the parent remainder is not cancelled, and child cancels are not confirmed before market close. Historical frequency is unidentified. | E82/F93 · [doc](D6_partial_fill_force_close_quantity_audit.md) |
| 59 | Force-close completion and VWAP | Does one observed market-close execution—or a ten-second timeout—prove the position flat and its price complete? | **No.** A nonempty fill list returns immediately with one component price; 60 shares of `SELL 100` can delete local state while 40 remain long. If no fill appears in ten seconds, callers estimate PnL and delete state anyway. Four of nine archived time exits explicitly crossed that boundary; ultimate broker outcomes are unknown. | E83/F94 · [doc](D6_force_close_completion_vwap_audit.md) |
| 60 | Unresolved-close back-to-back re-entry | Does a broker-flat snapshot make same-cycle re-entry safe while old orders are nonterminal? | **No.** The entry block checks positions but zero active-order fields. An old child can flatten, a new parent can fill, and the still-working old close can erase the successor exposure. The archive has 32 back-to-back submissions and two after explicit close timeouts; it cannot prove a late-fill incident. | E84/F95 · [doc](D6_unresolved_close_back_to_back_reentry_audit.md) |
| 61 | Broker account/model scope | Do sizing, reconciliation, orders, and state share one explicit account/model identity? | **No; multi-account impact is conditional.** Summary tags are last-row-wins, position lookup is first symbol match, and orders/state are unscoped. Synthetic $100k/$1m rows change sizing 100→1,000 shares by callback order; opposite TQQQ positions flip the reported direction. Sanitization leaves actual account count unknown. | E85/F96 · [doc](D6_broker_account_scope_audit.md) |
| 62 | Duplicate-writer hold-counter materiality | Did paired historical cycles advance holding age twice and trigger time exits before ten unique cycles? | **Yes, directly observed in local state.** All nine time exits record bar 10; seven map exactly to ten signal writes over five paired minute slots, and eight use fewer than ten distinct slots. The time-exit clock was compressed, but longer-hold PnL is path-dependent and unidentified. | E86/F97 · [doc](D6_duplicate_writer_hold_counter_materiality.md) |
| 63 | Broker quote-field precedence and staleness | Does the bracket anchor prove a current, side-executable price? | **No.** Selection is last→prior close→bid→ask before the library's spread-aware midpoint; delayed 15–20-minute data are explicitly accepted without type/time retention. In a pinned recent TQQQ proxy, 32.13%/36.49% of exact 15/20-minute moves cross the 0.5% parent/stop offset. These are conditional stress frequencies, not incident rates. | E87/F98 · [doc](D6_broker_quote_field_precedence_audit.md) |
| 64 | Entry snapshot latency and decision age | How old is the decision when application-level entry success is emitted, and is that age bounded? | **Observed and unbounded.** Each entry obtains separate mark/order snapshots; the live-success path has at least two blocking snapshots and four explicit sleep seconds. All 72 archived application events occur 14.377–62.949 seconds after the `:32` anchor (median 20.292; 22 ≥30s). Causal component and fill latency remain unidentified. | E88/F99 · [doc](D6_entry_snapshot_latency_audit.md) |
| 65 | Market-data provenance label integrity | Does a green `live` mark prove real-time data and quote freshness? | **No.** Nominal-live and delayed broker branches return the same scalar shape; every successful scalar is labeled `live`, persisted, and rendered green. The same resolver feeds software risk checks, while `mark_time` is local ingestion time. The archived singleton cannot identify incident frequency. | E89/F100 · [doc](D6_market_data_provenance_label_audit.md) |
| 66 | Software risk-trigger provenance and outcomes | Do unqualified marks produce observed false software stops, and is duplicate triggering visible? | **Safety gap present; observed false stop absent in retained prices.** Six triggers all say `live`; four unique joins close beyond the stop, while two later writers trigger again 22–23 seconds after the prior close record. Quote provenance and second-order outcome remain unidentified. | E90/F101 · [doc](D6_software_risk_trigger_outcome_audit.md) |
| 67 | Software-risk fallback freshness | Can a daily fallback value force an intraday exit without proving its row is current? | **Yes; conditional materiality is large, incidence unknown.** The row date/age is unchecked and the full path has 20 explicit wait/backoff seconds. If the prior session close were returned, 62–65/160 archived cycle slots falsely cross the stop proxy and 17/160 falsely cross take-profit; zero actual fallback incidents are retained. | E91/F102 · [doc](D6_software_risk_fallback_freshness_audit.md) |
| 68 | Duplicate bar-fallback trigger divergence | Can paired writers use different final bar-close fallbacks and disagree at a software-risk boundary? | **Yes, as observed inputs and a deterministic decision fork.** Ten archived slots mix in-progress and older bars across a stop/TP boundary: five stop forks and five take-profit forks over nine trades. Writers are 0.000125–2.112320 seconds apart. Zero retained triggers use `last_close`, so realized incidence remains unproved. | E92/F103 · [doc](D6_duplicate_bar_fallback_trigger_divergence.md) |
| 69 | Broker connection exception fallback | Do connection failures reach yfinance/bar fallback, and are open-position risk cycles preserved? | **No; directly observed aborts.** `ConnectionRefusedError` bypasses the RuntimeError-only resolver catch. The archive has 46 aborts across 24 slots; 33 events/17 slots occur while three local lifecycles are open. Their 12.247–12.628-second offsets corroborate retry exhaustion. Broker protection and PnL effect remain unknown. | E93/F104 · [doc](D6_broker_connection_exception_fallback_audit.md) |

## The complete answer

**1. The active engine has no risk-adjusted edge over a static allocation — at any timescale, vs any benchmark, in any build.**
Hourly is flat ([[F13]]); daily mean-reversion is real as a *signal* but not tradeable-better-than-static (#1); it loses to the recommended 60/40 (#2); its crisis protection is real but small-N and Sharpe-neutral (#3); and no overlay — constant-weight or regime-conditional — reliably improves a 60/40 core (#4). The slope-regime "core innovation" is in fact dead-wired ([[F26]]).

**2. The honest product is a simple static 60/40 — and it is hard to beat reliably, in this universe or a different one.**
~Sharpe 0.85, robust to the rebalance rule, with no single third sleeve, vol-targeting, or risk-parity overlay that survives a fair bootstrap (#5, #6, #7). Gold is the one borderline-promising diversifier, but it fails a clean out-of-sample test and is a discretionary judgment call, not an evidence-backed edge. And widening the search to a whole *different asset universe* — munis, credit, preferreds, options-income, dividend/low-vol, treasuries — does not help: **high yield ≠ low drawdown** across that cross-section (the income-rich names carry equity-like-or-worse drawdowns *and* erode principal), nothing clears the ~3.75% income floor with even a <20% drawdown, and no income ETF dominates the 60/40 (#11). The one structural escape — a **held-to-maturity Treasury/IG ladder** — genuinely does deliver income with ~0 *realized* drawdown (#12), but it is not a free lunch: the 0% is amortized-cost *definitional*, the mark-to-market drawdown reduction is *just lower duration* (a plain short ETF gets it), it is *nominal only* (−19% real in the 1970s), and it clears 3.75% only as a *forward* claim — it converts market risk into term + reinvestment + inflation risk + zero upside. The honest "income with low drawdown" product exists only as that ladder, for an investor who can commit capital to a horizon.

**3. Forward-looking, the product clears the income goal but not the drawdown goal — and the goal-optimal mix is more conservative than 60/40, *in the regime it was measured in*.**
At 2026 starting yields the 60/40 should return ~5–6%/yr (forward Sharpe only ~0.5) — more-likely-than-not above the ~3.75% APY target ([[D4]]; P≈67%, a ~1-in-3 chance of missing over a decade) — but with equity-like tail risk (~−23% median worst drawdown). The original "near-zero drawdown" aspiration is **unattainable by any honest static or active build** in this program (#8). And because forward bonds out-Sharpe forward equity, the *goal-optimal* static mix is **more conservative than 60/40** (~30–40% equity), which weakly dominates 60/40 on goal-odds, Sharpe, *and* drawdown — though no mix makes 3.75% a sure thing (#9). **Study #13's regime qualifier:** that dominance is a *negative-correlation-regime* result — positive-corr (most of 1962–1999, and again since 2022), the tilt's excess-Sharpe advantage disappears and its *real*-drawdown edge **inverts** (more bonds → deeper real drawdown; the 40/60 lost −36 to −41% of purchasing power in 1965–81). The drawdown promises of #8/#9 are **nominal and regime-conditional**; on the real-drawdown criterion the surviving ballast is *shorter and partly real* (T-bills / TIPS ladder), at a clear cost whenever bonds hedge again. **Studies #14–15 close the escape routes:** a marked-to-market TIPS *sleeve* is duration-shortening in disguise (#14), and no fixed ballast composition dominates both regimes (#15) — the ballast choice is an **irreducible regime bet**, best *halved* (never removed) by the minimax-regret 50/50 cash+bond blend.

**4. The live bot's flat result is fully reconciled — and its backtest also truncates overnight tail risk.**
It faithfully trades a signal whose mean-reversion edge lives at the *daily* timescale and vanishes at the *hourly* frequency it runs ([[F13]]/[[F14]], re-derived on the live instrument). The two eye-catching numbers are both artifacts: the Sharpe-25 backtest from morning-only sampling (× unused adaptive-Kelly sizing [[F28]], holdout selection [[F2]], optimistic fills), and the +37% live dashboard from exit-accounting (inferred `target_hit` + max-bars `time_exit` marks). The full-session backtest is ≈0 and the former “CONFIRMED +1.5%” live bucket is now correctly **exit-confirmed on a quote-derived entry basis** ([[F87]]); both still say flat (#10/#52). This quantifies [[F28]]: the live↔backtest disconnect is dominated by **bar-frequency**.
Studies #16–69 add the execution-risk qualifiers. An exact 0.5% stop does not bound a 3× ETF held
overnight; open-aware fills roughly double the observed two-year loss and drawdown, and the July
live −4.01% stop is a direct instance. The runner also skips entry-hour bracket evaluation, but
hourly dual-hit bars prevent identifying that correction's absolute return sign. EOD flatten is
the only clean mitigation candidate, while a 16-year, eight-instrument panel shows the overnight
tail scales almost mechanically with leverage. The small lower-timeframe sample cannot calibrate
away the entry-ordering uncertainty, and weekend flatten captures 44% of observed damage but only
24% of gap events. A rescued one-minute event tightens the gap-aware negative bound; severe gaps
cluster; and lagged volatility is a better partial control only because it removes most recent
overnight exposure. Dependence/cost stress leaves that selected rule as a forward paper-shadow
hypothesis, not a live change. An early-split lookback test supports that specific 20d/15% risk
classifier but rejects the broader claim that volatility timing is specification-invariant.
The decision-relevant forward endpoint needs roughly 6.7 years under iid planning—and potentially
8.4–13.3 years under heuristic clustering effects—at the observed event rate; moreover,
IBKR paper fills cannot identify real closing-auction cost. The current runtime also lacks the
selected decision, MOC path, deadline/calendar guards, and auction evidence schema; separately,
its hard-coded 16:00 market-hours guard admits 76 off-calendar jobs in 2026. Across the pinned
window, 162 such jobs include 65 clean-baseline-open cycle exposures and all 15 post-close
early-session jobs reuse a previously processable bar. These findings make the hourly case
less defensible, not more. Sanitized Pi records confirm cycles actually ran on two official
closures; paper-Gateway connection failures, not calendar logic, prevented downstream behavior.
The same archive shows that historical double writes were operationally material: 69/210 paired
signals disagree, 58 cross the long-entry boundary, and seven entry minutes reached the bracket
success path twice while one-row local state retained only the later write. The paired-bar
structure also exposes a current clock defect: UTC-naive vendor labels are compared with
host-local-naive time, so London BST can admit an in-progress bar and the New York service can
discard a completed bar when the current vendor tail is missing. No protected remediation is
authorized by these studies. Direct true-UTC aging finds 297/543 archived signal rows and a strict
minimum 40/65 entry minutes used in-progress bars; the live result remains flat but cannot serve as
completed-bar validation.
Simple recent-gap rules match volatility's unconditional risk
concentration, so its apparent strategy advantage remains the exact selected claim requiring
forward evidence.
Its high recent raw capture is largely obtained by staying risk-off through entire volatile
years; annual discrimination even falls below an exposure-matched random flag in 2024.
All exact inputs are now byte-identified, but the raw hourly/daily vendor panels are local
runtime state rather than a repository-contained dataset.
The volatility flag is most discriminative for catastrophic gaps, not routine 0.5% stops, and
its unflagged tail still contains a historical −10.54% discontinuity.
Ex-dividend cash corrects a few routine raw-gap classifications and +0.0338 pp of strategy
return, but none of the severe tail or mitigation decisions.
Two corrupt partial hourly sessions expose a data-quality hole, yet daily-open substitution and
defect exclusion both make the negative path slightly worse.
Applying daily opens and distribution credits together establishes the canonical path at
−10.1713% total / −10.2126% maxDD; the mitigation cost ceilings remain too narrow and
unvalidated for promotion.
Switching mitigation exits from official daily closes to last-hourly closes changes the paths by
less than 0.08 pp and preserves both descriptive gates, but shared-vendor proxy agreement still
cannot substitute for auction-fill evidence.
A fixed 60-fill, zero-breach auction-cost protocol would take roughly 1.79 years for vol15 at the
observed exit rate, but MONAD's paper-only environment cannot collect the approval endpoint.
Removing QQQ ex-dividend moves from vol20 flips only five long-history state labels and no strategy
decision, ruling out distribution contamination as the selected rule's explanation.
Every vol20 state also reproduces exactly from the 20 total-return observations ending at t−1;
an impossible unshifted current-close version flips 20 recent dates and performs worse.
All nine 14–16% local threshold perturbations retain the descriptive gate, ruling out a
15.00%-specific cliff without turning the same-sample plateau into forward evidence.
Vol15's +4.1302 pp dynamic benefit is almost exactly reproduced (+4.1299 pp) on the fixed baseline
cohort; daily flatten's replacement path instead gives back 0.7724 pp.
Vol15 is tail-concentrated but not singular: removing its largest avoided event retains 75.84% of
direct benefit, while removing the top five still leaves +1.7657 pp.
The corrected fixed-cohort vol15 effect also survives block-5/20/60 dependence stress; the
block-20 relative-wealth interval is +1.860% to +8.314%.
Vol15 helps 43/67 changed baseline trades: every eventual stopped loser improves and every one of
24 eventual targets is cut short, confirming asymmetric loss avoidance rather than precision.

> **Bottom line.** MONAD's "high-yield-bond-ETF alternative" is achievable on **return** as a simple
> static 60/40, but **not** as a near-zero-drawdown active product. The active mean-reversion engine
> is, at best, a discretionary low-drawdown overlay — never a measurable risk-adjusted edge. And the
> static product's own drawdown promises are **nominal and correlation-regime-conditional** (#13):
> in the bonds-don't-hedge regime that covers most of the last 64 years — and again since 2022 —
> every bond-heavy mix lost purchasing power for a decade, and only short/real ballast mitigated it.

## Navigating & reproducing

- **Idea graph:** `venv/bin/python tools/ctx.py web <E25..E66 | F34..F77 | D6 | D4>` · `ctx why <node>` · `ctx neighbors <node>`
- **Reproduce any study:** `venv/bin/python tools/<name>_study.py` (deterministic, seed=0; data-fetching studies cache to `/tmp`).
- **The shared uncertainty module** (CIs on any backtest): `venv/bin/python -m src.backtest.uncertainty`
- **Honest live/performance state:** `ctx perf` · `ctx web --live`
