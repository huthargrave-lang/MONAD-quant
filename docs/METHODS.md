# Methods

*How results in this research base are produced, bounded, counted, admitted and kept
honest. Written for an outside quantitative reader. Every factual statement is traceable
to a file in this repository; citations are `path:line` (at the merged tip) or a document
section. Numbers are quoted from committed documents, not recomputed here.*

---

## 1. Scope and stance

MONAD Quant is an open research base: a typed, append-only evidence graph of studies on
allocation, execution risk, SEC filings, corporate actions, closed-end-fund discounts and the
epistemics of research, plus the machinery that disciplines those claims
([`../README.md:9-17`](../README.md)). A long-only mean-reversion trading engine ships with it
as the reference test bench ([`REFERENCE_ENGINE.md`](REFERENCE_ENGINE.md)).

It is research, not advice: "Nothing here is a recommendation to buy, sell, or hold anything"
([`../README.md:364-366`](../README.md); [`../VISION.md:134`](../VISION.md)). Results are findings
about specific instruments, data and protocols, not claims about markets
([`../SCHEMA.md` §8](../SCHEMA.md)).

The benchmark every claim is measured against is a static allocation. Decision `D6` records
that the active daily mean-reversion engine shows no demonstrated advantage over a trivial
static blend of the same assets — active Sharpe 0.69 against 0.80 (50/50) and 0.86 (60/40),
with the Sharpe-difference bootstrap straddling zero
([`../RESEARCH_WEB.md:392-397`](../RESEARCH_WEB.md)). The program that tested this verdict to
destruction (studies 1–15) is recorded as closed ([`research/README.md:13`](research/README.md)),
and the contributing standard requires any timing or overlay claim to be measured "against
the trivial static mix that killed the reference engine (`D6`), not only against
buy-and-hold" ([`../CONTRIBUTING.md` §Standards](../CONTRIBUTING.md)). As of 2026-10-29 the base
recorded 956 trials across 66 families and 4 hypotheses under the admission gate
([`../README.md:37`](../README.md)).

## 2. Data contracts

**Content addressing.** Every frozen data set is `<PREFIX>-<sha>`: `<PREFIX>-<sha>.csv.gz`
holds the observations, `<PREFIX>-<sha>.json` the manifest, and the sha is the SHA-256 of the
*decompressed* canonical CSV ([`research/data/README.md` TL;DR](research/data/README.md);
regexes at [`../src/research/data_store.py:56-57`](../src/research/data_store.py)). A trial cites
the sha. One self-contained prefix (`CEFETF`) hashes its own JSON
([`data_store.py:65`](../src/research/data_store.py)).

**Public and private stores.** The repository is public, so observations from vendors whose
terms grant no redistribution right are not committed. They live in the gitignored
`local_research_data/` ([`data_store.py:52`](../src/research/data_store.py)); their manifests stay
committed with an `observations` record naming the bytes by sha
([`data_store.py:115`](../src/research/data_store.py)). The policy is decided from a manifest's
`sources` against `RESTRICTED_VENDORS` — Yahoo/yfinance, CEFConnect/Morningstar, the Frankfurt
fixing ([`data_store.py:71-73`](../src/research/data_store.py)); `private=False` with a restricted
source is refused ([`data_store.py:102-112`](../src/research/data_store.py)). Loaders search the
committed store, then the private one, and refuse bytes that do not hash to their name
([`data_store.py:1-32`](../src/research/data_store.py)). The source-by-source reading of vendor
terms, "not legal advice", is [`research/DATA_REDISTRIBUTION_AUDIT.md` §2](research/DATA_REDISTRIBUTION_AUDIT.md)
and [`research/data/README.md` §2](research/data/README.md). Restricted observations were
committed until 2026-10-09; git history was not rewritten
([`research/data/README.md` §7](research/data/README.md)).

**Point-in-time source clocks.** The SEC filing lab records that acceptance time is a source
event, not an observed public-availability time, and that filing date is not an event
timestamp — Alphabet's 10-Q accepted at 21:02 on April 29 carries an April 30 filing date
([`research/FD00_sec_filing_delta_lab.md` §PT-01 event-clock audit](research/FD00_sec_filing_delta_lab.md)).
The historical daily rule, implemented once in `tradable_time`, is the first regular-session
open strictly after acceptance, except that a premarket acceptance (before 09:30 ET on a
session day) trades at that day's open ([`../src/research/edgar_ledger.py:22-27`](../src/research/edgar_ledger.py),
[`:559-629`](../src/research/edgar_ledger.py)). `clock_class` is `second`,
`legacy_midnight_display` (a `00:00:00` display is not an acceptance time), `not_public_event_time`
(a private-to-public filing never uses its original acceptance) or null
([`edgar_ledger.py:523-530`](../src/research/edgar_ledger.py)). Corrections are new `revision`
rows, never edits ([`edgar_ledger.py:679-697`](../src/research/edgar_ledger.py)), and each index
day ends in a `seal` row that hashes that day's lines
([`edgar_ledger.py:700`](../src/research/edgar_ledger.py), [`:812-824`](../src/research/edgar_ledger.py)).

## 3. Leak-free construction

Entries and weights use only lagged information. For the research studies this is literal:
`mr_daily_lab.py` lags every rolling input that feeds an entry with `.shift(1)`
([`research/README.md:215`](research/README.md)). The same table draws a distinction worth
keeping: in the engine code (`src/signals/`, `src/strategy/`) the `.shift(1)` *letter* is not
followed even though the no-look-ahead *property* holds
([`research/README.md:215`](research/README.md)). The contributing standard therefore asks for a
decision-time proof rather than a `.shift(1)` citation ([`../CONTRIBUTING.md` §Standards](../CONTRIBUTING.md)).

The model proof is the vol20 audit. For each session `t` the tool reconstructs annualised
20-day QQQ volatility from exactly the 20 returns ending at `t−1`; all 4,113 values match the
vectorised, shifted classifier to a maximum absolute difference of 2.5e−15, so the
classification is fixed before Nasdaq's 15:50 cancellation lock and 15:55 MOC cutoff
([`research/D6_volatility_decision_time_audit.md` §Exact chronology proof](research/D6_volatility_decision_time_audit.md)).
The audit also runs the unshifted version: it flips 147 historical and 20 recent threshold
labels and produces a *worse* path (−6.2049% vs −6.0411%). "A leak does not become acceptable
because it hurts the result"
([`D6_volatility_decision_time_audit.md` §Explicit lookahead falsification](research/D6_volatility_decision_time_audit.md)).

Daily strategies get the mechanical form: orders on a snapshot truncated at a cut must equal
the full-data orders up to that cut, at 12 cuts
([`../src/research/allocation_stats.py:227`](../src/research/allocation_stats.py);
[`../tools/admit_tactical.py:16`](../tools/admit_tactical.py)).

## 4. The execution model

**ENGINE_VERSION 3.** Execution semantics are versioned so that trials recorded under
different semantics never pool into one family's search count
([`../src/backtest/runner.py:62-73`](../src/backtest/runner.py)). Version 3 matches the live bot's
cycle, as ratified on 2026-10-06
([`research/ENGINE_V3_QUESTION.md` §Decision-debate consensus](research/ENGINE_V3_QUESTION.md)):
(a) a signal on bar N fills at the open of N+1 and the bracket is scanned over N+1 … N+MAX,
an N+1 touch of both levels resolving stop-first, with every result reporting its
ambiguous-exit count; (b) in each later bar the open is checked first — at or through the stop
fills at `open − stop_slippage_pct` (`gap_stop`), at or through the target at the open
(`gap_target`), otherwise both levels in one bar resolve stop-first (`ambiguous_same_bar`);
(c) the time exit fills at the open of bar N+1+MAX, falling back to the last close only at the
end of the data (`time_exit_truncated`); (d) one open position with live's same-cycle
re-entry rule; (e) `worst_case_ambiguity` defaults to True and the `optimistic` mode is
renamed `upper_bound`; (f) parity rows measure live-vs-backtest divergence rather than declare
it; (g) stop slippage, below; (h) all timeframes; (i) a declared list of unmodelled live
behaviours. Implementation: [`../src/strategy/engine.py:213-262`](../src/strategy/engine.py),
[`:327-369`](../src/strategy/engine.py).

**Fairness modes.** `upper_bound` has zero slippage, target-wins ambiguity and full-sample
(look-ahead) Kelly; its trials carry `upper_bound: true`, count in a family's N, and can never
be admitted because admission re-runs every candidate in `realistic` mode. `realistic` charges
2 bp round-trip with stop-wins ambiguity and rolling Kelly; `harsh` charges 5 bp
([`../src/backtest/runner.py:35-58`](../src/backtest/runner.py)). The configured default is
`realistic` ([`../config_modules/base.py:16-20`](../config_modules/base.py)).

**The overnight-gap qualifier.** A tight stop does not bound overnight risk in a 3× ETF. In a
live-shaped two-year TQQQ replay, 34 of 127 overnight holds opened through the stop; exact
fills reported −5.17% versus −10.15% with open-aware fills (study 16, E40/F50;
[`research/README.md` study table](research/README.md)). Gap tails scale almost mechanically
with leverage: TQQQ's gap beta versus QQQ is 2.95 (R² .993) over 2010–2026 and 11.71% of nights
open down at least 2% (study 19, E43/F53;
[`research/D6_cross_instrument_gap_history.md`](research/D6_cross_instrument_gap_history.md)).
Rule (b) follows: gaps fill at the open.

**Stop slippage and the 3× stress.** Item (g) separates trigger-to-fill slippage from the
spread the round-trip cost already charges. The 2026-10-29 amendment closes the archived-live
instrument (the committed archive holds one native intraday stop fill) and replaces it with a
stated prior `stop_slippage_pct = 0.0005` (5 bp), "a conservative prior with no claimed
derivation", with every admission record re-run at 0.0015 (3×) as a prospective gate rule
([`research/ENGINE_V3_QUESTION.md` §(g) amendment](research/ENGINE_V3_QUESTION.md);
[`research/DECOMMISSION_TRADER_QUESTION.md` §(g) amendment](research/DECOMMISSION_TRADER_QUESTION.md)).
The admission tool now carries that prior: `STOP_SLIPPAGE_PCT = 0.0005` stated with its source
in every price-profile record, `STOP_STRESS_PCT = 0.0015` (3×) applied as a `stop_stress` stage
after `cost_stress` to registrations whose frozen `registered_at` is on or after 2026-10-29, the
value every gate trial ran at recorded in the ledger, and the verifier recomputing both from the
registration and the ledger ([`../tools/admit.py`](../tools/admit.py) `STOP_SLIPPAGE_PCT`,
`STOP_STRESS_PCT`, `stop_stress_applies`; guarded by `tests/test_admit.py::StopSlippageAmendment`).
The 32.72 bp it carried before was the median cycle-lateness margin of four paper software stops
(the DIVERGE quantity of rule (i)), not trigger-to-fill slippage; no recorded verdict depended on
it, and all four existing registrations predate the rule, so they are unaffected.

## 5. Uncertainty

**Paired block bootstrap.** The shared module resamples `n // block` blocks of consecutive
observations with replacement and re-evaluates the statistic on each synthetic series; block
resampling preserves short-range autocorrelation, which matters because the daily
mean-reversion signal under test *is* lag-1 autocorrelation
([`../src/backtest/uncertainty.py:112-132`](../src/backtest/uncertainty.py)). Defaults are
`block=20`, `n_boot=2000`, `seed=0`; the effective block is capped at `n // 4`; a series shorter
than 8 reports a degenerate band rather than a false range
([`uncertainty.py:100-103`](../src/backtest/uncertainty.py), [`:139`](../src/backtest/uncertainty.py),
[`:46`](../src/backtest/uncertainty.py)). The studies use block = 20, B = 5000, seed = 0, pinned
identical in `power_study.py:55-57` and `static_product_study.py:40-42`
([`research/README.md:216`](research/README.md)). The design is *paired*: the same block-start
indices are drawn for both legs and the statistic is `Sharpe(active*) − Sharpe(bench*)`;
pairing halves the standard error (0.19 vs 0.39 unpaired on the 12.5-year window)
([`research/D6_power_equivalence_study.md` §Methodology](research/D6_power_equivalence_study.md)).

**Equivalence (TOST).** Equivalence at ±Δ is established iff the 90%
bootstrap CI lies inside (−Δ, +Δ); the smallest provable margin is
`Δ* = max(|lo90|, |hi90|)` ([`research/D6_power_equivalence_study.md:45-46`](research/D6_power_equivalence_study.md)).
Over 26.5 years active ≈ static within ±0.30 Sharpe (a narrow pass, Δ* = 0.25); over 12.5
years only ±0.50 passes (Δ* = 0.42)
([`D6_power_equivalence_study.md` §Results](research/D6_power_equivalence_study.md)). Against the
decision-relevant 60/40 the point ΔSharpe is −0.17 (12.5 yr) and −0.26 (24 yr); the 24-year
90% CI upper bound is +0.001 and the document makes no "significantly worse" claim; MDE at
80% power is 0.57 / 0.46 and Δ* is 0.50 / 0.54
([`research/D6_active_vs_6040_study.md` §Results, §The Finding](research/D6_active_vs_6040_study.md)).

**Two metric conventions.** The corpus has two disjoint Sharpe stacks. The active
mean-reversion family (`mr_daily_lab`, `power_study`, `power_study_6040`,
`overlay_build_study`, `crisis_overlay_study`) computes Sharpe on log returns with
`exp(cumsum)` curves; the static-product family (`static_product_study`, `gold_oos_study`,
`voltarget_riskparity_study`, `bond_ladder_study`) uses simple returns with `cumprod(1+r)`.
On a provably identical 60/40 they publish 0.70 and 0.82
([`research/README.md:235-243`](research/README.md); node `F153`), now pinned by
[`../tests/test_return_convention_lab.py:191-204`](../tests/test_return_convention_lab.py) for the five
active files and three of the four static files (`voltarget_riskparity_study` is not in the
test's list). The
lab derives a data-free lower bound for the gap, `ΔSharpe ≥ σ_p / 2`, and found the corpus's
"~0.01" caveat to be one wrong sentence copied to six sites, wrong by roughly 12×
([`../tools/return_convention_lab.py:1-60`](../tools/return_convention_lab.py)). Cross-convention
numbers must not be compared as if commensurable.

## 6. Multiple testing

**Counted trials and families.** Every research attempt is recorded before its result exists:
`Run.begin` writes and fsyncs an `intent` row (spec and spec hash) before anything is computed,
so an abandoned or crashed trial still counts ([`../src/research/trials.py:11-17`](../src/research/trials.py)).
Rows are `run_open`, `intent`, `outcome`, `run_close`, each carrying `prev` = SHA-256 of the
previous row's bytes, chained to a per-run genesis
([`trials.py:21-23`](../src/research/trials.py), [`:97-101`](../src/research/trials.py), [`:310`](../src/research/trials.py)).
Counting is enforced at runtime: `run_backtest`, `compute_trade_returns` and `evaluate_daily`
refuse to run without a begun trial holding an unspent token
([`../src/strategy/counted.py:1-25`](../src/strategy/counted.py);
[`../src/research/daily_strategy.py:187`](../src/research/daily_strategy.py)). A family is the unit
significance is deflated over — `long_only_rsi_vwap_mr_<timeframe>.v<ENGINE_VERSION>:<SYMBOL>`
for the engine — and membership is by engine identity, so a scratch-labelled search cannot
hide ([`../src/research/backtest_trials.py:58-76`](../src/research/backtest_trials.py)); trials under
an earlier engine version are lineage and still count in `m`
([`backtest_trials.py:103-108`](../src/research/backtest_trials.py)). The ledger's known gaps are
recorded, including that a trial deleted before its first commit is invisible and that
`sweep.py` still loads morning-only bars ([`research/trials/README.md` §Known gaps](research/trials/README.md)).

**Deflated Sharpe.** The candidate's per-period Sharpe, skew and non-excess kurtosis are
measured on its daily PnL over its active span
([`../src/research/deflation.py:22-23`](../src/research/deflation.py)). The probabilistic Sharpe
ratio is

```
PSR(SR*) = Φ( (SR − SR*) · sqrt(n − 1) / sqrt(1 − γ3·SR + (γ4 − 1)/4 · SR²) )
```

([`../src/research/significance.py:94-107`](../src/research/significance.py)) and the
search-implied threshold is

```
SR0 = sqrt(V) · [ (1 − γ) · Φ⁻¹(1 − 1/N) + γ · Φ⁻¹(1 − 1/(N·e)) ],   γ = 0.5772…
```

with `V` the cross-trial variance of cluster Sharpes ([`significance.py:110-124`](../src/research/significance.py)).
`DSR = PSR(SR0)` ([`significance.py:139-146`](../src/research/significance.py)). `N` is
conservative at every fork: trials with returns are clustered by daily-PnL correlation at a
fixed 0.5 threshold, the larger of the cluster count and the Li–Ji eigenvalue count is used,
and each distinct error/abandoned/orphan spec adds one
([`significance.py:59`](../src/research/significance.py), [`:259-300`](../src/research/significance.py);
[`deflation.py:1-37`](../src/research/deflation.py), [`:107`](../src/research/deflation.py)).

**Hansen's SPA.** For K strategies against one benchmark, the test studentises mean
differences with a stationary-bootstrap standard error, recentres badly losing members
(t below −sqrt(2 log log n)) at their own mean so they do not inflate the null maximum, and
reports each member's single-step max-t familywise p-value
([`significance.py:469-510`](../src/research/significance.py)). Tactical strategies run it on the
*active* series (strategy minus reference on identical sessions) at mean blocks 20, 63 and
126 with B = 5000; the candidate must clear every block
([`../src/research/allocation_stats.py:41-55`](../src/research/allocation_stats.py)).

**Gate rules v2.** The 2026-10-06 debate made the familywise SPA the gating stage and the DSR a
reported diagnostic ([`research/DEFLATION_RULE_QUESTION.md` §Decision-debate consensus](research/DEFLATION_RULE_QUESTION.md)):
(i) `p_gate = (worst SPA-adjusted p over blocks 20/63/126) × (1 + m) ≤ familywise_alpha`, with
`m = prior_search_trials + unknown_specs + off_window_points`, p = (b+1)/(B+1),
`B ≥ max(5000, ⌈20(1+m)/alpha⌉)`, a union bound needing no independence; (ii) found-nothing
members drop out exactly; (iii) the price profile scores a daily mark-to-market active series
against a close-exposure benchmark; (iv) registrations carry `gate_rules`,
`familywise_alpha ≤ 0.05` and `prior_search_trials`; (v) chains are versioned and verifiers
recompute the seeded SPA and (1+m); (vi) a profile switches only when a size study's Wilson
95% upper bound is ≤ 0.075; (vii) every member with mean ≥ 0 still raises the max-t bar;
(viii) documentation follows. The tactical trigger passed (worst upper bound
0.0687), so `tools/admit_tactical.py` runs `ADMIT_CHAIN_V2`
([`DEFLATION_RULE_QUESTION.md` §Measured: the tactical trigger](research/DEFLATION_RULE_QUESTION.md);
[`../tools/admit_tactical.py:77`](../tools/admit_tactical.py)). The price profile stays blocked:
`PRICE_V2_RATIFIED = False`, with a 1008-session floor
([`../tools/admit.py:90`](../tools/admit.py); [`../src/research/prereg.py:124`](../src/research/prereg.py)).

**What the power study found.** On synthetic families (one real idea with four correlated
variants plus unrelated null ideas, 20 years, 60 replications) the DSR stage fails in both
directions: a null candidate in a one-idea family passes 12% of the time against a nominal 5%,
and a genuine 1.0 active Sharpe with two unrelated null ideas passes only 2%. SPA stays near
nominal size (2–7%) and keeps power (83–100%)
([`research/DEFLATION_RULE_QUESTION.md` §Measured: how the two stages behave](research/DEFLATION_RULE_QUESTION.md)).

## 7. Pre-registration and admission

**Pre-registration.** One frozen file per hypothesis, written once by `tools/prereg.py register
--commit`, fixes before the evidence exists the family, the metric and threshold, the minimum
sample, the cost model and the holdout ([`research/prereg/README.md`](research/prereg/README.md)).
Required fields: `hypothesis`, `family`, `claim`, `profile`, `universe`, `development_window`,
`metric`, `threshold`, `min_trades`, `holdout`, `cost_model`
([`../src/research/prereg.py:130-131`](../src/research/prereg.py)); the engine template freezes
exactly five candidate parameters ([`../tools/prereg.py:38-40`](../tools/prereg.py)). Floors:
threshold 0.95, 30 trades, 180 forward days, forward PSR 0.90
([`prereg.py:50-52`](../src/research/prereg.py), [`:74`](../src/research/prereg.py)). Profiles are
`price_strategy`, `event_study`, `allocation`, `tactical_allocation`
([`prereg.py:76-81`](../src/research/prereg.py)). A changed spec is a new hypothesis that
`refines` the old one and shares its family, so refining never resets the trial count; CI
fails if a registration on the deploy branch is edited or deleted
([`prereg.py:386`](../src/research/prereg.py)).

**The admission chain.** `tools/admit.py` is deterministic: no model judges anything. For the
price profile the stages are registration, code (clean tree at a known commit), refutations,
parity (the live bot decides like the backtest), witness (the registration and every searched
trial are already on the deploy branch), development (the frozen candidate re-run at
instrument cost), deflation, cost_stress (2×), benchmark (Calmar ≥ buy & hold) and forward
([`../tools/admit.py:1-42`](../tools/admit.py), [`:593-597`](../tools/admit.py)). The verdict is
the worst stage outcome, `REJECT > BLOCKED > PENDING > ADMIT`
([`admit.py:112-120`](../tools/admit.py)); profiles without a holdout return `UNSUPPORTED`. The
tactical chain replaces parity with lookahead, adds `eras` (active Sharpe > 0 in every
registered era), and under v2 makes `deflation_diagnostic` a mandatory SKIP while
`familywise` gates ([`../tools/admit_tactical.py:1-32`](../tools/admit_tactical.py),
[`:73-78`](../tools/admit_tactical.py)). Verdict records are written once with `O_EXCL` and
re-verified from the ledger ([`admit.py:577-590`](../tools/admit.py), [`:599`](../tools/admit.py));
a hypothesis with no record reads `NOT EVALUATED`
([`../tools/edge_scorecard.py:71`](../tools/edge_scorecard.py)).

**Objections and boards.** Anyone may object; objections and answers must cite checkable
evidence and are appended to `docs/research/refutations/<H>.jsonl`
([`../tools/refute.py:1-16`](../tools/refute.py)); outcomes are `refuted` or `upheld`
([`../src/research/refutations.py:31`](../src/research/refutations.py)). An unanswered objection
BLOCKs; an upheld one REJECTs. A board record carries `hypothesis`, `convened`, `rule`,
`members`, per-objection `rulings` with a tally, each adjudicator's `votes` (id, outcome,
confidence, evidence, reason) and `caveats`
([`research/refutations/boards/H404702.json`](research/refutations/boards/H404702.json)). For
H404702 three objections were each refuted 3-0; for H404700 three were upheld 3-0, which
motivated ENGINE_VERSION 3 ([`research/ENGINE_V3_QUESTION.md` §Why it is open](research/ENGINE_V3_QUESTION.md)).

**What admission grants.** Eligibility as a sleeve, not a size
([`research/forward_watch/policy/route.2.json` `admission_grants`](research/forward_watch/policy/route.2.json));
sizing is a separate record under a drawdown budget (§8).

## 8. Forward evidence

**Forward watches.** A watch is a frozen, tamper-evident daily paper record of a rule the gate
cannot admit. The spec is written once and named by its SHA-256; the log only grows, each
line carrying the previous line's SHA-256, the spec hash and the code state; each session's
return is computed once from the previous line's logged book and never recomputed, so a vendor
revision becomes a `correction` line; each run is one counted trial per session in family
`forward_watch.<ID>.v1` ([`../src/research/forward_watch.py:1-24`](../src/research/forward_watch.py)).
Line kinds are `genesis`, `window_open`, `session`, `correction`, `evaluator_change`, `void`,
`vintage`, `nav_revision`, `symbol_change` ([`forward_watch.py:78-79`](../src/research/forward_watch.py)).
The genesis records state only, and the window opens at the first session after the spec
reached the deploy branch, dated by the first-parent commit
([`forward_watch.py:713-715`](../src/research/forward_watch.py);
[`../tools/forward_watch.py:15-19`](../tools/forward_watch.py), [`:55-60`](../tools/forward_watch.py)).
`log` refuses a dirty tree and a changed evaluator until the change is attested
([`../tools/forward_watch.py:111-119`](../tools/forward_watch.py);
[`forward_watch.py:731-760`](../src/research/forward_watch.py)). A domain watch reads NAVs as
published: session `t` decides on the newest vintage fetched before session `t+1`'s close, a
NAV older than 14 days reads neutral, and 63 sessions without a valid vintage is a VOID
([`forward_watch.py:1060-1068`](../src/research/forward_watch.py);
[`research/METAL_TRUST_FORWARD_WATCH.md` §NAV vintages and decisions](research/METAL_TRUST_FORWARD_WATCH.md);
[`research/METAL_TRUST_DISCOUNT_PROTOCOL.md:37`](research/METAL_TRUST_DISCOUNT_PROTOCOL.md)).
`verify` is at [`forward_watch.py:372-405`](../src/research/forward_watch.py).

**The sequential test.** Each anniversary of the window's opening computes

```
LLR = T · (θ1 · S_T − θ1² / 2)
```

with `T` in years and `S_T` the annualised active Sharpe; the watch's own verdict is `promote`
if `LLR ≥ ln((1 − β)/α)` and the cost-stressed Sharpe is positive, `close` if
`LLR ≤ ln(β/(1 − α))` ([`forward_watch.py:538-549`](../src/research/forward_watch.py)). The founding
specs freeze θ1 = 0.3, α = 0.05, β = 0.2 ([`research/forward_watch/H366200.json` `evaluation`](research/forward_watch/H366200.json)).
An anniversary settles once the log holds the 64th session line past its cut and is written
once ([`forward_watch.py:447`](../src/research/forward_watch.py), [`:466-512`](../src/research/forward_watch.py);
[`route.2.json` `test.settle`](research/forward_watch/policy/route.2.json)). Promotion is not
terminal; it triggers a decision debate.

**The ratified route.** `route.2.json` (schema 2, ratified 2026-10-29) supersedes `route.json`
by path and SHA-256. Its upper boundary is `ln((1 − β)/α_i)`, where `α_i = α · γ_i` is spent per
watch from the append-only freeze ledger: the founding cohort H366200/H366201 gets γ = 1/3 each
(boundary 3.871 nats, ln 48), ordinal i ≥ 3 gets `γ_i = 1/(i(i+1))`, the shares sum to 1, and
alpha assigned to a closed or voided watch is never recycled
([`route.2.json` `alpha_spending`](research/forward_watch/policy/route.2.json);
[`forward_watch.py:629-653`](../src/research/forward_watch.py)). Honest power is stated in the
policy: ordinal 3's boundary is 5.257 nats, 4.5% by 40 years at a true Sharpe of 0.3, so from
ordinal 3 on a watch is a record, not a practical admission path. For the founding cohort the
simulated admission probability at a true Sharpe of 0.3 is 1.7% by 20 years, 17.9% by 40 and
64.7% by 100 (100k paths; [`research/FORWARD_ROUTE_PROPOSAL.md` §Decision-debate consensus (2026-10-09), route-admission table](research/FORWARD_ROUTE_PROPOSAL.md)).
An admitted sleeve is sized against the D6 static 60/40 host
(`TR-20261006T005053Z-9336581d#0`) over a carve grid {0, 2.5%, 5%, 10%}, within a 1.0 pp
extra-drawdown budget, `maxDD(mix) − maxDD(host)` on the daily close path, the maximum over
three frozen windows binding ([`route.2.json` `sizing`](research/forward_watch/policy/route.2.json)).
De-admission is a CUSUM on per-year ΔLLR, `W_k = max(0, W_{k−1} − ΔLLR_k)`, alarming at
h = 2.0, plus the close boundary, a VOID, or a daily drawdown cut that sets the size to 0
([`route.2.json` `de_admission`](research/forward_watch/policy/route.2.json)).

## 9. The evidence graph

The graph is one Markdown file, `RESEARCH_WEB.md`, read by `tools/ctx.py` and written only by
`tools/note.py` (atomic, lint-gated, dry-run by default). Nodes are Findings, Hypotheses,
Experiments and Decisions; a Finding requires an `evidenced_by` edge to an Experiment
([`../SCHEMA.md` §1, §3](../SCHEMA.md)). The enforced vocabulary has 12 edge types —
`evidenced_by`, `produces`, `relies_on`, `supports`, `refines`, `builds_on`, `supersedes`,
`contradicts`, `derived_from`, `drives`, `resolves`, `relates` — and the four reliance edges
(`relies_on`, `supports`, `refines`, `builds_on`) may not point from a current node at a
superseded one ([`../SCHEMA.md` §5a](../SCHEMA.md); [`../tools/ctx.py` (`EDGE_TYPES`, at f4a57da:1155)](../tools/ctx.py)).
Status is `current`, `superseded` or `retracted`; a supersession carries a reason code from
`reversed`, `refined`, `data-fixed`, `data-revised`, `decayed`, `merged`, `withdrawn`,
`inverted` ([`../tools/ctx.py` (`STATUS_VALUES`, at f4a57da:1329-1331)](../tools/ctx.py); [`../SCHEMA.md` §6](../SCHEMA.md)).

Four integrity invariants, all violated when first audited, are now CI tests: a declared
`supersedes` edge implies a tombstone; edge types come from the vocabulary; the reliance graph
is acyclic (a reliance edge points to a prior node); node ids are unique. A fifth check
requires tombstones to name existing nodes, and a parser-agreement test keeps the audit lab
and `ctx.py` reading every edge identically ([`../tests/test_web_integrity.py`](../tests/test_web_integrity.py)).

The pending predicate was ratified on 2026-10-29: a Hypothesis is CLOSED when a current F or D,
itself not contradicted by a current node, carries `resolves` → H; it is SUPERSEDED only when
the question is withdrawn; a Decision is open unless superseded by the gate that overtook it
or titled RESOLVED/DONE ([`research/WEB_HYGIENE_QUESTION.md` §Policy rule (A)](research/WEB_HYGIENE_QUESTION.md);
[`../tools/ctx.py` (`_resolved_hypotheses`, at f4a57da:2268-2290)](../tools/ctx.py)).

In the research UI a file citing more than `ROLLUP_CITATION_LIMIT = 8` distinct nodes is an
index or session summary, not a source for any one node, and is excluded from the per-node
evidence index; the limit comes from the measured distribution (median 4, mean 6.1; README
cites 146) and exclusions are reported, not hidden
([`../tools/research_ui.py:659-662`](../tools/research_ui.py), [`:698-760`](../tools/research_ui.py)).

## 10. Reproducibility and its limits

REPRO-00 measured what reproduces from the repository alone. At the time, 12 of 39 analysis
scripts ran offline; everything reading a committed artifact ran and everything reading
market data did not, because no CSV existed in any of the 80 visible commits
([`research/REPRO00_market_data_reproducibility.md` §1](research/REPRO00_market_data_reproducibility.md)).
Its fix, `tools/data_cache.py`, refuses to cache an empty fetch
([`REPRO00` §2–3](research/REPRO00_market_data_reproducibility.md)). The document states what it
does not fix — staleness and provenance, the gap that let D6's published figures drift
(0.86 → 0.84, 0.69 → 0.68, 6.2% → 6.1%) between capture and a later re-run
([`REPRO00` §4](research/REPRO00_market_data_reproducibility.md)).

Today the division is explicit. From the repository alone: every manifest, the public-domain
data sets, the trial ledger, the registrations, refutations, verdict records and the graph.
Needing the private store: every trial that cites a Yahoo, CEFConnect or Frankfurt-fixing
data set. The store comes from a collaborator's export (`tools/data_inventory.py import`,
verified against `SHA256SUMS` and the sha in each name) or is rebuilt from the manifest; a
rebuild yielding a different sha is a different data set and cannot replay the trial
([`research/data/README.md` §4](research/data/README.md)). Continuous integration has no private
store: an absent private file skips with a reason, a present one must verify, and
`MONAD_REQUIRE_PRIVATE_STORE=1` makes absence a failure ([`research/data/README.md` §4](research/data/README.md)).

The ledger's own integrity is checkable: `tools/trial_ledger.py verify` walks every shard's
hash chain and, with `--require-closed --against origin/development`, checks that every shard
and artifact present at the merge base is still a byte-prefix of (artifacts: identical to)
its current content ([`../tools/trial_ledger.py:56-70`](../tools/trial_ledger.py);
[`../src/research/trials.py:636-680`](../src/research/trials.py), [`:1002`](../src/research/trials.py)).
A run whose process died is closed with `seal`, which drops only a torn final row
([`research/trials/README.md` §Rules](research/trials/README.md)).

## 11. References

The repository cites the following works by name in code docstrings. None of them is given a
DOI, SSRN, arXiv or NBER link anywhere in `src/` or `tools/` (checked by search of `*.py`), so
bibliographic details are as the docstrings give them. (Several lab documents under
`docs/research/` do link outside literature by DOI, SSRN, arXiv or NBER — for example
`PN00_daily_cross_asset_lead_lag.md`, `IX00_index_membership_event_lab.md` and
`FD00_sec_filing_delta_lab.md` — but those are domain references of individual studies, not
sources for the methods described here.)

- Bailey, D. H. and López de Prado, M. (2014). "The Deflated Sharpe Ratio." *Journal of
  Portfolio Management* 40(5). — [`../src/research/significance.py:14-17`](../src/research/significance.py).
- Bailey, Borwein, López de Prado and Zhu (2017). "The Probability of Backtest Overfitting." —
  [`significance.py:23-25`](../src/research/significance.py).
- Hansen, P. R. (2005). "A Test for Superior Predictive Ability." *Journal of Business &
  Economic Statistics* 23(4). — [`significance.py:29-31`](../src/research/significance.py).
- Romano and Wolf, stepdown procedure (named without year). — [`significance.py:33`](../src/research/significance.py).
- Politis and Romano (1994), the stationary bootstrap. — [`significance.py:34`](../src/research/significance.py).
- Li and Ji (2005), effective number of independent tests. — [`significance.py:57`](../src/research/significance.py), [`:259`](../src/research/significance.py).
- Newey and West (1994), bandwidth rule of thumb. — [`../src/research/hac.py:16`](../src/research/hac.py).
- Wald's sequential probability ratio test is named ("a Wald sequential test", "Wald's bound")
  without a bibliographic citation. — [`../src/research/forward_watch.py:26`](../src/research/forward_watch.py);
  [`research/FORWARD_ROUTE_PROPOSAL.md:36`](research/FORWARD_ROUTE_PROPOSAL.md).
- Interactive Brokers, stop-order glossary. — [`research/D6_execution_semantics_study.md` §External execution check](research/D6_execution_semantics_study.md).
- SEC webmaster FAQ and vendor terms pages. — [`research/data/README.md` §2](research/data/README.md).

TOST is used but not cited by author anywhere in the repository.
