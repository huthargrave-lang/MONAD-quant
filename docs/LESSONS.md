# What this research base learned that transfers

*Written for an outside quant reader. Every figure below is taken from a committed document or a
node of the evidence graph and cited beside it; node IDs resolve with
`python3 tools/ctx.py web <ID>`. Nothing here is advice: results are findings about specific
instruments, data and protocols, not universal claims
([`README.md` → Scope and disclaimers](../README.md#scope-and-disclaimers)).*

MONAD Quant opened with one question — does an active, long-only mean-reversion engine beat a
static stock/bond allocation on risk-adjusted terms, and if not, what is the honest income
product? — and answered it *no, and a static mix* ([`docs/research/README.md`](research/README.md),
verdict `D6`). The engine's headline backtests (Sharpe 25.57 for BTC hourly, 41.57 for QQQ hourly,
[`CLAUDE.md` §1](../CLAUDE.md)) were a data-sampling artifact (`F13`), its "core innovation" was
wired into nothing (`F26`), and the live paper bot was flat (`F43`). That verified negative is the
base's credential. The machinery that produced it — pre-registration, a hash-chained trial ledger,
paired block bootstraps, adversarial panels, and an append-only evidence graph that forbids a
current decision from resting on a retracted claim — went on to record 600+ typed nodes, 200+ study
writeups and 956 counted trials across 66 families ([`README.md`](../README.md)). What follows is
what we think transfers to someone else's research.

Each lesson gives a claim, the episode here, the mechanism, what to do instead, and how to
reproduce it. "Needs the private store" means the inputs are vendor observations that cannot be
redistributed: manifests and hashes are committed, bytes are not
([`docs/research/data/README.md`](research/data/README.md)).

---

## 1. Validate that your data represent what you will trade before believing any intraday edge

**What happened here.** The leak-free walk-forward on the cached hourly data showed QQQ
+0.34%/mo at Sharpe 3.74 (`F3`, `E3`). The cache was silently truncated to ~3 bars/day, 13–15 UTC
(`F10`): a yfinance quirk returns ~3 bars/day for a 1h fetch over a ~710-day range but full 7-bar
sessions in ≤250-day chunks — and the live bot, fetching a ~40-day window, traded full sessions
(`F12`). On full-session data the same walk-forward flipped to QQQ −0.05%/mo (Sharpe −0.75) and
SPY −0.05%/mo (`F13`). The decomposition settled the mechanism: QQQ AM-only (3 bars/day)
+0.34%/mo, PM-only (4 bars/day) +0.32%/mo, all-day (7 bars/day) −0.05%/mo. AM ≈ PM, so it was never
time-of-day; it was bar count (`F14`). Study #10 re-derived it on the live instrument (`F43`,
[study #10](research/D6_live_backtest_reconciliation.md)).

**Why.** RSI(7)/MACD on ~3 bars/day spans ~2 trading days and captures multi-day mean reversion;
on 7 bars/day it spans ~1 day of intraday noise (`F14`). The edge belonged to the sampling, and the
sampling was an accident of the fetch window.

**What to do instead.** Assert bars-per-session against the exchange calendar before any
backtest, and diff the research feed against the feed the live process actually pulls. "The edge
changes when I resample" is a red flag about the data, not a property of the market.

**Reproduce.** `venv/bin/python tools/live_backtest_reconciliation_study.py` (reads the hourly
caches `data/cache/{QQQ,TQQQ}_1h.csv`, vendor data not committed; the full-session re-pull is
`tools/fetch_fullsession.py`, `E7`).

## 2. A real signal is not a tradable edge: the benchmark that kills most timing is a trivial static blend

**What happened here.** The daily mean-reversion portfolio scored Sharpe 0.69 at 6.2%/yr against
0.80 for a static 50/50 equity/cash blend and 0.86 for 60/40 equity/bond, with the active-minus-static
Sharpe-difference bootstrap straddling zero (`D6`, `E12`). What timing bought was *exposure*: about
half the return (6.2% vs 12.1%) at about half the drawdown (−13.9% vs −29.5%), which a static
50/50 delivers at the same Sharpe as buy-and-hold, since cash scaling is Sharpe-invariant (`F22`).
Over 2000–2026 the CI narrowed to [−0.34, +0.30] (`F25`). A TOST equivalence test turned absence
of evidence into evidence of absence: no
edge larger than ~0.42 Sharpe in the main windows and ~0.25 over 26.5 years, with a ≤0.2-Sharpe
residual needing ~90–114 years to resolve — undetectable, not irrelevant, at ≤2%/yr (`F34`,
[study #1](research/D6_power_equivalence_study.md)). Against the decision-relevant 60/40 the point
estimate was *lower* (ΔSharpe −0.17 over 12.5yr, −0.26 over 24yr; CIs straddle 0) (`F35`). The
project's own RSI+MACD signal did not rescue it (`F24`).

**Why.** Mean reversion is a real property of the series (`F16`, `F18`), but a long-only timing
rule mostly converts it into time out of market. Any benchmark without the cash leg flatters the
active rule.

**What to do instead.** Benchmark every timing strategy against a static blend matched on
exposure, report the paired difference with a CI, and run an equivalence test so "no edge" is a
bounded claim rather than a shrug.

**Reproduce.** `venv/bin/python tools/power_study.py` and `venv/bin/python tools/power_study_6040.py`
(deterministic, seed 0); cross-check `venv/bin/python tools/mr_daily_lab.py gonogo`. The lab's price
cache is ephemeral and re-fetched from Yahoo (`F139`).

## 3. In mean reversion the exit, not the entry, is the lever

**What happened here.** On identical dip entries, a 5-day horizon exit yielded +29 bps/trade on
SPY (+38 QQQ, +80 TQQQ) while a fixed ±0.8% stop/target yielded −2 bps (−27 on TQQQ, 36% win
rate): same entry, opposite sign (`F19`, `E10`). The mechanism had been isolated earlier: with the
same ~0.7% stop on every instrument, the probability that a bar's own range triggers the stop on
noise alone is 94–100% on 3× ETFs, 37% on QQQ and 17% on SPY, and across seven instruments
corr(stop fraction, win rate) = −0.97 (`F7`). Swapping the %-stop for a horizon exit flipped every
instrument positive in the daily walk-forward (`F17`). The horizon exit does *not* rescue the 2022
bear (3× ETFs −166/−346 bps/trade), so the regime gate is a separate requirement (`F19`).

**Why.** A stop inside intrabar noise exits winning trades before the bounce completes; win rate
falls below the reward:risk break-even and the edge becomes churn. Leverage widens the bar range,
so the same stop is proportionally tighter.

**What to do instead.** Size stops against the instrument's intrabar range or use a horizon exit
for mean-reversion entries, and report P(bar range > stop) before tuning anything else.

**Reproduce.** `venv/bin/python tools/mr_daily_lab.py` (`E10`, the per-trade figures of `F19`).
`F17`'s portfolio-level numbers exist in no committed artifact and are corroborated in direction
only (`F139`, `H74`).

## 4. Naive t-statistics on autocorrelated returns overstate significance about threefold

**What happened here.** Twelve years of daily data gave lag-1 autocorrelations of SPY −0.117
(t −6.4), QQQ −0.105 (t −5.8), DIA −0.125 (t −6.9), IWM −0.061 (t −3.3) (`F16`). An independent
replication reproduced the coefficients almost exactly, but naive t = ρ√n ignores volatility
clustering; under a heteroskedasticity-robust SE the t-stats fell ~3× (SPY −6.3 → −2.2; IWM −1.7,
not significant), and in the 2022 bear ρ → 0 (`F18`). Over 26 years the robust t-stats are ^GSPC
−3.64, DIA −3.20, IWM −3.02, QQQ −2.55 — real, but modest (`F25`). An audit found the paired block
bootstrap (block 20, B 5000, seed 0) genuinely pairs — pairing shrinks the SE ~2.3× — and is slightly
conservative on a GARCH(1,1)+AR(1) synthetic path (`F154`).

**Why.** The signal under test *is* short-range autocorrelation. An i.i.d. bootstrap shuffles it
away and overstates confidence; a block bootstrap preserves it
([`src/backtest/uncertainty.py`](../src/backtest/uncertainty.py)).

**What to do instead.** Report paired block-bootstrap CIs of the *difference* versus the
benchmark, with the same block starts on both legs, never a lone point estimate.

**Reproduce.** `venv/bin/python -m src.backtest.uncertainty` (runnable smoke demo);
`venv/bin/python tools/mr_daily_lab.py gonogolong` (`E14`, network required).

## 5. Count every trial — and measure the power of your multiplicity rule before trusting it

**What happened here.** The sweep picked its winner *by* the holdout score, so its holdout numbers
were best-of-many; the +4–5%/mo for SOXL/LABU/TNA did not survive de-biasing (`F2`). The Sharpe-25
headline was morning-only sampling × an adaptive-Kelly sizing the live trader never used × holdout
selection × optimistic fills (`F28`, `F43`). The
response was a hash-chained trial ledger in which every attempt counts, errors and abandoned runs
included, and CI fails on any rewrite ([`trials/README.md`](research/trials/README.md)). The ledger
then bit its author: a null tax-loss tilt (active Sharpe +0.08) run *after* H404701 was registered
dropped H404701's Deflated Sharpe from 1.00 to 0.9367, below its registered 0.95 — REJECT at
deflation while familywise SPA still passed at p 0.0002 (`F404708`). A synthetic power study
explained why: at true active Sharpe 1.0 with two unrelated null ideas in the family the DSR passes
2% of the time while SPA passes 100%, and SPA holds 2–7% size under the null with 83–100% power
([`DEFLATION_RULE_QUESTION.md`](research/DEFLATION_RULE_QUESTION.md)). The ratified rule, prospective
only and never to rescue H404701, made SPA the multiple-testing stage with
p_gate = worst SPA p × (1 + m), m counting prior-search, unknown-spec and off-window trials
(`DEFLATION_RULE_QUESTION.md` §(i)); a Sharpe-0.6 edge passes ~37% at m = 20
against ~85% at m = 0, and the document says that price "should not be" free.

**Why.** The DSR treats heterogeneous ideas as selection noise, so a family mixing one real effect
with unrelated nulls gets an inflated bar; SPA's recentering ignores badly losing members.

**What to do instead.** Log every evaluator call, losers included; register the family before the
search; simulate your deflation rule's size and power on synthetic families.

**Reproduce.** `venv/bin/python tools/trial_ledger.py stats`; `tools/deflation_power_study.py`;
`tools/spa_size_study.py` (results in `docs/research/spa_size_study.json`).

## 6. A tight stop does not bound overnight risk in a leveraged ETF; gap tails scale with leverage

**What happened here.** On 2026-07-06 the paper bot held 123 TQQQ at 76.61 with a −0.5% stop
(~76.23) overnight; the stop filled at 73.54 near the open, −4.007%, 8× the configured stop (`F47`).
A two-year live-shaped replay (3,429 hourly bars, 494 sessions) held 127/1,117 positions
overnight, 34 (26.8%) opening through the stop; exact-stop accounting reported −5.17% total /
−5.88% maxDD versus −10.15% / −10.19% with open-aware fills, and a mean-matching 7.0 bp stop penalty
hid a conditional tail with median 1.03 pp, p90 3.51 pp, max 8.96 pp (`F50`). Over 4,133 nights
TQQQ's 1% gap quantile is −6.69%, worst-1% mean −10.33%, 11.71% of opens ≤ −2%; gap beta versus
QQQ is 2.95 (R² .993) (`F53`). Evaluating the one mitigation candidate on a *fixed* cohort
separated direct risk removal from replacement-trade drift: the volatility rule's +4.1299 pp
fixed-cohort benefit equals its +4.1302 pp dynamic benefit, while daily flatten's replacement trades
give back 0.7724 pp (`F74`); removing the largest event retains 75.84% of the benefit, the top five
42.75% (`F75`); block-20 CI [+1.860%, +8.314%] (`F76`); 43/67 changed trades improve — every one of
21 eventual gap stops helped, every one of 24 eventual targets harmed (`F77`).

**Why.** A session gap is a discontinuity; a stop is a limit on a continuous path. Slippage
scalars represent the mean of a jump distribution, not its tail. This is instrument structure,
not one signal's bad luck.

**What to do instead.** Fill stops at the next open when it gaps past them, or remove the overnight
exposure; decompose any mitigation into direct removal versus newly admitted trades, and report
leave-largest-events-out.

**Reproduce.** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck` and
`--json /tmp/gap-program.json` ([study #16](research/D6_overnight_gap_risk_study.md)). Inputs are
byte-identified by SHA-256 but the raw vendor panels live only in `/tmp` (`F63`, `F71`).

## 7. Benchmark every risk classifier against trivial nulls, and report exposure removed beside tail capture

**What happened here.** A 20-day/15% lagged-QQQ-volatility flag captured 75.16% of severe TQQQ
gaps and removed 61.76% of the strategy's gap stops with 66 exits — by disabling 56.5% of all
nights and 75.3% since 2020 (`F57`). Its unconditional capture lift, 1.33×, was matched by "a severe
gap happened in the last 1–5 sessions" rules at 1.31×–1.38× (`F61`). By year it flagged 100% of 2022
(lift exactly 1), ~84% of 2020 and 2023 (lift ~1.03–1.05), and in 2024 flagged 59.1% while capturing
54.5% (lift 0.92); only 2025 showed concentration, 1.38× (`F62`). Dependence stress left it standing
(block-20 CI [+1.99%, +7.83%]) but with a post-selected threshold (`F58`), so it was frozen as a forward hypothesis needing ~115 new gap events
— ~6.7 years i.i.d., 8.4–13.3 under clustering — for 80% power (`F60`).

**Why.** A high recall score is cheap when the classifier is risk-off most of the time. What
distinguishes a predictor from a blanket regime flag is lift *at matched exposure*, by year.

**What to do instead.** Report (capture, exposure, lift) per year, compare against transparent
clustering rules, and treat a same-sample threshold as a hypothesis to test forward, not a control
to ship.

**Reproduce.** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`
([study #27](research/D6_simple_risk_classifier_benchmarks.md), [#28](research/D6_volatility_regime_stability.md)).

## 8. "Live" is not "executed", and a simulator can be provably wrong while the correction stays unidentifiable

**What happened here.** The dashboard once showed +37%; the exit-confirmed bucket nets +1.55%,
with six ~1% `target_hit` and nine max-bars `time_exit` rows driving the difference (`F43`). The
entry function makes three `placeOrder` calls and performs zero status/fill checks before emitting
local success; `fill_basis` is the pre-submission
quote, and the 47-row archive's +0.204664% crosses zero at +0.435 bp of adverse entry error (`F87`).
Two SQLite connections can cache one position and commit two trade rows because no unique lifecycle
key exists (`F90`); an older cycle can attach its exit economics to a newer re-entry and delete it
(`F91`); duplicate writers advanced the holding counter twice, so seven of nine ten-bar time exits
fired after five distinct minutes (`F97`). On the simulator side, 980/1,516 (64.6%) of paired
entries touch a bracket in the entry hour the research runner skips, and the result spans −7.61%
stop-first to +16.91% target-first because 157 entry bars hit both levels (`F51`); a rescued
one-minute bar left the best count at 5 target-first / 12 stop-first / 2 unresolved, with
model-based P(total > 0) of 1.24%–9.89% (`F56`).

**Why.** Hourly OHLC cannot order two touches inside one bar, and application logs record intent,
not execution. Without one lifecycle identity through intent → order → execution → close, PnL rows
are inferences.

**What to do instead.** Distinguish submitted, accepted and executed; propagate a lifecycle ID
across every table and event; demand tick, order-event or lower-timeframe evidence before calling
live PnL validated; and do not patch a simulator from 16 microstructure events (`F54`).

**Reproduce.** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap_program_study52.json`
([study #52](research/D6_entry_acknowledgement_basis_audit.md)); the same tool with `study56` and
`study62` for the lifecycle and hold-counter audits. None starts a trader or contacts a broker.

## 9. Two metric conventions in one corpus silently make its numbers incommensurable

**What happened here.** The active mean-reversion family (`mr_daily_lab`, `power_study`,
`power_study_6040`, `overlay_build_study`, `crisis_overlay_study`) computes Sharpe on log returns
with `exp(cumsum)` equity curves; the static-product family (`static_product_study`, `gold_oos_study`,
`voltarget_riskparity_study`, `bond_ladder_study`) uses simple returns with `cumprod(1+r)`. No tool
computes both. On a provably identical 60/40 the two stacks publish 0.70 and 0.82 — while the
compendium guaranteed "one source of truth" (`F153`). A one-sentence estimate of the gap as "~0.01"
had been copy-pasted into six sites, wrong by ~12×: the true gap is +0.12 ± 0.01, and a data-free
bound (ΔSharpe ≥ σ_p/2, floor +0.057 at 11.30% vol) proves ~0.01 impossible. The hazard: a
simple-convention 2002–2026 60/40 at 0.84 and a log-convention 2014–2026 60/40 at 0.84 look like
one measurement because the convention flip cancels the window difference (`F147`). A provenance
audit found the corpus's errors live in prose, wiring and provenance, essentially never in its
mathematics (`F146`, `F154`).

**Why.** An invariant stated in prose with no executable check can be false for the life of a
corpus without any run failing.

**What to do instead.** One metrics module, one convention, imported everywhere; a test that fails
when a second implementation appears; and no Sharpe comparison without checking convention and
window.

**Reproduce.** `venv/bin/python tools/return_convention_lab.py sites` (also `bound`, `verify`,
`implied`; stdlib only, no market data, `E116`); `python -m unittest tests.test_return_convention_lab`.

## 10. Historical 60/40 statistics are a regime; forward they are weaker, and the ballast is an irreducible regime bet

**What happened here.** At 2026 yields a 60/40 should return ~5.9%/yr (4.4–7.4% across scenarios)
at a forward Sharpe of ~0.51 versus 0.84 historical; it clears the 3.75% income goal with P≈67% but
carries a ~23% median worst drawdown and a 65% chance of a >20% drawdown (`F41`). Because forward
bonds out-Sharpe forward equity (~0.6 vs ~0.35), a 30–40% equity mix weakly dominates — goal-odds
70% vs 67%, Sharpe 0.68 vs 0.51, median drawdown −15% vs −23% (`F42`). Then the regime test: bonds
hedged stocks in only ~22 of the last 64 years; in 1965–81 the 40/60 lost −41% of purchasing power
(zero-coupon proxy; −36/−37% coupon-honest) against −39% for the 60/40, so the conservative
tilt's real-drawdown edge *inverts*, and its
excess-Sharpe advantage ([+0.06, +0.38] in 2000–21) disappears in 1962–99 ([−0.14, +0.04]) (`F46`).
The escape routes closed: a short-TIPS sleeve is indistinguishable from a duration-matched nominal
sleeve (ΔmaxDD [−0.20, +0.70], ΔSharpe [−0.009, +0.046]) — the draft's "inflation-carry hint" was a
residual-duration artifact (`F48`) — and no fixed cash/bond composition dominates both regimes; a
50/50 cash/7yr blend halves the worst-case regret (0.49 vs the poles' 1.00) and nothing removes it
(`F49`). Third sleeves, vol-targeting and risk parity fail paired bootstraps (`F38`, `F39`, `F40`).

**Why.** Most of the usable 60/40 record sits inside one correlation regime, and nominal yield
goals are blind to the inflation that destroys real wealth in the other.

**What to do instead.** Re-price allocations at current yields; test every "improvement" against a
duration-matched control; report regime-conditional drawdowns in real terms.

**Reproduce.** `venv/bin/python tools/correlation_regime_study.py --selfcheck`;
`tools/forward_expectation_study.py`; `tools/weight_optimization_study.py`;
`tools/tips_sleeve_study.py`; `tools/ballast_blend_study.py` (deterministic; fetch once to `/tmp`).

## 11. High yield is not low drawdown, and a held-to-maturity ladder's 0% drawdown is definitional

**What happened here.** Across a liquid income-ETF cross-section only 2 of 12 non-equity names beat
the 60/40 on Calmar (BIL, SHY), both by low return *and* low drawdown; QYLD distributes ~11%/yr while
NAV falls −2.5%/yr, so its spend-the-income drawdown is −42% against −25% reinvested; nothing clears
the ~3.75% income floor with even a <20% drawdown (`F44`). The one structural escape, a 1–10yr
Treasury ladder, does deliver ~0 realized drawdown at ≈ entry yield — but the 0% is amortized-cost
accounting; the mark-to-market reduction is just lower duration (a duration-matched 5yr ETF draws
down −14% vs the ladder's −13.7%, and SHY beat the 2020 ladder on both return and drawdown); it is
nominal only (−19.1% real in the 1970s); and no ladder in the study cleared 3.75% on realized return
(`F45`).

**Why.** Distribution yield is not total return, and not marking to market is an accounting choice,
not a market outcome. The ladder converts market risk into term, reinvestment and inflation risk
with zero upside.

**What to do instead.** Decompose yield into income and NAV change; compare any "low drawdown"
vehicle to a duration-matched plain ETF; state which accounting basis a drawdown number uses.

**Reproduce.** `venv/bin/python tools/income_universe_study.py`;
`venv/bin/python tools/bond_ladder_study.py --selfcheck`.

## 12. Forced-flow and discount mechanisms are where measurable effects live — and they are small

**What happened here.** Within-category closed-end-fund discount selection with hysteresis
(`H404702`) shows active Sharpe +1.44, +2.25%/yr net of 1.09%/yr costs, SPA p < 0.001, DSR 0.99,
survived a 3–0 board, and sits in a forward window to 2027-10-07 (`F404713`). Its frozen pre-period
test on 1997–2003 data read +0.39, t 0.97 — UNINFORMATIVE under the pre-stated bar (`F404717`). Two live products corroborated the mechanism — CEFS beat PCEF by
active Sharpe +0.59, MDCEX +0.58 ([`CEF_PRODUCT_PROTOCOL.md`](research/CEF_PRODUCT_PROTOCOL.md)) —
though a later beta control attributed MDCEX's edge to equity beta, so only CEFS's corroboration
stands (`F366205`);
`F366208` reads much of that return as a state-conditional response to category rallies. The
cleanest instance holds the same metal on both legs: a PHYS/GLD + PSLV/SLV
discount tilt earns +0.74%/yr, active Sharpe +0.43, SPA p 0.022, every era positive, and is not
admissible once its declared search of 22 is charged (0.022 × 23 ≈ 0.51)
([`METAL_TRUST_DISCOUNT_PROTOCOL.md`](research/METAL_TRUST_DISCOUNT_PROTOCOL.md), `F366202`); a later
control attributed +0.23 of the tilt's +0.56%/yr raw active return (on the control's own basis) to
metal timing, leaving hedged alpha +0.33%/yr at t 1.1,
so the forward-watch document's "no beta exposure" was an overstatement, recorded rather than edited
(`F366210`). The published liquid-equity effects did not survive: a live buyback ETF shows active
Sharpe −0.04 vs SPY over 19.7 years, SPA p 1.00, CONTRADICTS
([`BUYBACK_PRODUCT_PROTOCOL.md`](research/BUYBACK_PRODUCT_PROTOCOL.md)); the survivor-only spin-off
backtest corroborated (+0.80) but the live spin-off ETF shows +0.04 vs mid caps, SPA p 0.42, and the
backtest node was superseded as a sample artifact ([`SPINOFF_PROTOCOL.md`](research/SPINOFF_PROTOCOL.md),
`F404733`); a fallen-angel sleeve reads NO CREDIT at every carve because it is measurably worse than
a replica holding only its own lagged stock and bond exposure (−0.022/−0.046/−0.098 at 5/10/20%)
([`CREDIT_SLEEVE_MIX_PROTOCOL.md`](research/CREDIT_SLEEVE_MIX_PROTOCOL.md), `F366209`).

**Why.** Prices move because of who must sell, not what the asset is worth — and that pressure is
small, capacity-limited, partly a timed exposure, and easy to mistake for alpha in a survivor-only
universe.

**What to do instead.** Test a mechanism where nothing but the mechanism moves (same asset, two
wrappers); run beta-timing and convexity controls; replicate on a disjoint universe and a
pre-period; prefer a survivorship-free live product over your own backtest when both exist.

**Reproduce.** Needs the private store (Yahoo prices, CEFConnect NAVs):
`venv/bin/python tools/domain_search.py cef_discount --snapshot <DS sha> --panel <CEFNAV sha> --report-only`;
`tools/admit.py H404702 --dry-run`; `tools/domain_search.py metal_trust_discount …` then
`tools/metal_trust_report.py`; `tools/credit_sleeve_mix.py`.

## 13. Freeze the protocol before the data, and let a skeptic rule

**What happened here.** Studies since the discount program ship as `*_PROTOCOL.md` files whose
universe, rule, benchmark, window, costs, counting rule and pass criterion are committed before any
price is loaded ([`CONTRIBUTING.md`](../CONTRIBUTING.md)). The rule binds when inconvenient: the
pre-period test missed t > 1.0 "by a hair" and was not counted (`F404717`); the beta-exposure control
could not read SURVIVES for H404702 because its frozen positive-control rule failed, so it was demoted
to INCONCLUSIVE and an objection filed although "H404702's own statistics pass every check"
(`F366205`, [`BETA_TIMING_CONTROL_PROTOCOL.md`](research/BETA_TIMING_CONTROL_PROTOCOL.md)). The
allocation studies were attacked by independent multi-lens panels that re-ran the code: the TIPS
study's draft "inflation-carry hint" was withdrawn as a residual-duration artifact
([study #14](research/D6_tips_sleeve_study.md)); the regime study's mis-signed sentence was fixed and every
correction folded into the tool ([study #13](research/D6_correlation_regime_study.md)). Governance decisions use the same shape: one
proposer, one independent skeptic who verifies every cite and rules DISPUTE or CONCUR; every
2026-10-29 debate reached CONCUR only in round 2, with named conditions
([decision-debate record](research/reviews/2026-10-29-decision-debates/README.md)). The epistemic
audit's own first headline was overturned by its review (`F134`).

**Why.** A criterion chosen after the result is a selection step, and a reviewer who sees the
result but not the author's reasoning finds the artifacts the author cannot.

**What to do instead.** Commit the pass/fail rule and the counting rule first; give the skeptic the
proposal and the repository, not the reasoning; fold forced corrections into the tool and keep the
draft's error visible.

**Reproduce.** `venv/bin/python tools/prereg.py register <spec.json> --commit`,
`tools/refute.py object`, `tools/admit.py <H> --dry-run`; the protocols are the
`docs/research/*_PROTOCOL.md` files ([compendium](research/README.md)).

## 14. Supersede, never delete — and make the graph police reliance on retracted claims

**What happened here.** The evidence graph is append-only: a stale node keeps its place under a
tombstone, a current node may not aim a reliance edge at a superseded one, and supersession
propagates — enforced by `ctx --lint`, `note.py` and tests ([`SCHEMA.md` §6](../SCHEMA.md)). Turning
the audit apparatus on the ledger itself found that of 331 nodes only two revisions were directly
observed (F15 lived 11 days, F69 one day), giving P(revised in 365d) = 17.3% with a 95% CI of
[2.3%, 49.6%] — i.e. unknown, with 44% of nodes at zero days of exposure (`F133`). All four
structural invariants were violated and invisible when first checked — a declared supersession with
no tombstone, an out-of-vocabulary edge type, two reliance cycles — and are now CI-enforced over a
570-edge, zero-cycle reliance DAG (`F138`). The hygiene
debate settled that *answered ≠ retracted*: a hypothesis closes by an inbound `resolves` edge from a
current finding; stamping it superseded would assert the question was wrong
([`WEB_HYGIENE_QUESTION.md`](research/WEB_HYGIENE_QUESTION.md)). The dead-wired regime gate (`F26`)
is the same lesson from the code side.

**Why.** Deleting a wrong claim deletes the evidence that it was believed; the reasoning history is
what lets the next reader check whether a current decision still stands on something retracted.

**What to do instead.** Keep an append-only, typed claim ledger; forbid reliance on retracted nodes
in CI; record corrections as superseding nodes with a reason; guard every documented invariant with
a test, or call it a belief.

**Reproduce.** `python3 tools/ctx.py web --lint` (610 nodes, 19 superseded, 0 problems at the tip
this was written against); `python3 tools/ctx.py contradicts F15`;
`python3 tools/epistemic_audit_lab.py risk`; `python3 -m unittest tests.test_web_integrity`.

---

## What we would not claim

- **No universal statements.** Each finding is about specific instruments, data and protocols
  ([`README.md`](../README.md#scope-and-disclaimers)). The gap-tail scaling is "unconditional
  historical scenarios, not strategy loss probabilities, sizing recommendations, limits, or a
  stationary forecast" (`F53`); the volatility rule supports "a specific paper-shadow candidate of
  20d/15%, not generic vol timing" (`F59`); the static mix's drawdown promises are "nominal and
  negative-corr-regime-conditional" (`F46`).
- **Not "no edge" but "no edge above a stated size".** The TOST leaves a ≤0.2-Sharpe residual that
  is undetectable, not irrelevant (`F34`); the income universe is survivor-only with no bootstrap CIs
  (`F44`); the CEF pre-period test was uninformative, not negative (`F404717`).
- **Paper only.** The reference engine connects to Interactive Brokers paper accounts (port 7497);
  project policy prohibits the live port and the evidence does not justify arming it
  ([`README.md`](../README.md#scope-and-disclaimers)). Its live record is exit-confirmed on a
  quote-derived basis (`F87`) and chronology-contaminated by in-progress bars (`F85`), not a
  completed-bar validation.
- **Not fully reproducible from a fresh clone.** The execution studies' inputs are byte-identified
  but the raw vendor bytes live outside the repository (`F63`, `F71`); the daily mean-reversion arc
  is neither byte-identified nor reconstructible (`F139`); discount and event studies need the
  private store ([`docs/research/data/README.md`](research/data/README.md)).
- **Trust to about two significant figures and to the sign of every verdict**, not to the third
  digit (`F146`).
- **Consistency is enforced; correctness is a human's job.** A confidently wrong finding with a
  valid evidence edge still passes every lint ([`README.md`](../README.md#scope-and-disclaimers)).
