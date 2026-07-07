# MONAD-quant — Research Idea Web
<!-- schema_version: 0.1 -->

> A traversable graph of what we **know** (Findings), what we're **testing**
> (Hypotheses), how we **test** it (Experiments), and what we **decide** (Gates).
> Nodes link with `[[ID]]`. Walk it with `venv/bin/python tools/ctx.py web [NODE]`.
> Append nodes; supersede rather than rewrite. **Evidence-first:** a claim is only
> as strong as the Experiment behind it, and only OOS, leak-free, cost-aware
> numbers count as evidence (see [[E3]]).
> **Schema:** v0.1 — node kinds, edge vocab & write rules are specified in [SCHEMA.md](SCHEMA.md).
>
> **⚠ HEADLINE CORRECTED (2026-06-19, later):** the QQQ/SPY edge above was a
> MORNING-ONLY DATA-SAMPLING ARTIFACT ([[F13]]). On full-session, live-representative
> data the hourly signal has NO reliable edge (QQQ/SPY negative). The edge tracks
> BAR-SAMPLING FREQUENCY, not instrument or time-of-day ([[F14]]) — it exists at a
> coarse (~daily/multi-day) timescale and vanishes at hourly, the frequency the
> live bot actually trades. This explains the flat live result. Findings F3/F4/F7/F8/F9
> below are SUPERSEDED for the hourly timescale; the mechanism [[F7]] still explains
> the leveraged-ETF failure. Live-representative verdict + next direction: [[D4]], [[H7]].

---

## Findings (established by an Experiment)

### F1 — Three numbers, three stories
Documented Sharpe 39–94 / +2–3.5%/mo (fantasy), holdout-selected +4–5%/mo (biased),
leak-free +0.1–0.34%/mo (honest). Only the last is trustworthy. See [[E1]], [[E2]], [[E3]], [[F2]], [[F3]]
— though even that "honest" ~0.34%/mo QQQ number was later shown to be a morning-only sampling artifact ([[F13]]).

### F2 — Holdout-selection bias inflates the sweep
`sweep.py` picks its winner BY the holdout score, so its "holdout" numbers are the
best-of-many on that holdout — biased. The +4–5%/mo for SOXL/LABU/TNA did NOT survive
de-biasing. Motivates [[H4]]. Evidence: [[E2]] vs [[E3]].

### F3 — [SUPERSEDED by F13] The honest edge is small but real (and decaying)
<!-- status: superseded; by: F13; reason: inverted; conf: 0.2 -->
Leak-free walk-forward ([[E3]]): QQQ +0.34%/mo Sh 3.74, TQQQ +0.18%/mo Sh 2.17, LABU
+0.15%, TNA +0.12%, SOXL +0.08% — sub-1% DD, ~90–112 OOS trades. Robustness ([[E4]])
shows the edge is **front-loaded into late 2025 and fades** in later folds. A near-zero-DD
~0.2–0.3%/mo vehicle, NOT a 2–3.5%/mo income engine. Bears on [[D1]].

### F4 — [SUPERSEDED by F13] QQQ (un-leveraged) is the best risk-adjusted instrument — structurally
<!-- status: superseded; by: F13; reason: inverted; conf: 0.2 -->
In leak-free OOS QQQ beat every 3x ETF (Sharpe 3.74, 54.5% WR). Mechanism found ([[F7]]):
it is NOT luck. Evidence: [[E3]], [[E6]]. The leverage tier is the wrong instrument class for this signal.

### F5 — Methodology note: short-slice warmup bug (fixed)
A naive walk-forward that slices each OOS window strips feature warmup → ~0 trades →
empty results. Fixed by running on `df[:fold_end]` and keeping only causal trades after
the train boundary (full warmup, no look-ahead). Lives in [[E3]].

### F6 — The live instrument (TQQQ) is fragile
TQQQ is +0.18%/mo but robustness ([[E4]]) shows it only clears significance on the default
split (pooled t≈2.1), **collapses to t=0.37 on recent-only data**, second-half t=1.03, and
has a losing fold. The live paper deployment is on a fragile, leveraged instrument. → [[D1]], [[D3]].

### F7 — THE MECHANISM: stop-vs-intrabar-noise ratio drives win rate
domain: monad_strategy
The same fixed ~0.7% stop is used on every instrument; the edge difference is entirely
**how often a bar's own intrabar range can trigger the stop on noise alone**, `P(bar range > stop)`:
3x ETFs **94–100%** (stop always inside noise → near coin-flip stop-outs) vs QQQ **37%**,
SPY **17%** (stop outside noise → fires only on genuine adverse moves). Across 7 instruments
`corr(stop_frac, WR) = −0.97`, `corr(noise_ratio, Sharpe) = +0.72`. Win/loss magnitudes and
R:R are ~identical across instruments — the edge is FEWER noise-stops, not bigger wins. Source: [[E6]]. Drives [[D3]].

### F8 — [SUPERSEDED by F13] The QQQ edge is a signal property, not an optimizer artifact
<!-- status: superseded; by: F13; reason: inverted; conf: 0.2 -->
Robustness ([[E4]]): the QQQ edge survives with a **single fixed candidate (zero parameter
selection)** — t-stat 3.3 — and across every fold count, objective, and grid width (t 3.3–4.3,
4/4 folds positive). So it is not selection overfit. Strongest evidence the edge is real. Supports [[F4]], [[D1]].

### F9 — SPY corroborates; un-leveraged broad indices are the right class
SPY (fetched fresh, vol 0.38%, noise ratio 1.83): WR 53.2%, Sharpe 2.9, +0.27%/mo —
independently corroborates QQQ. IWM (noise ratio ~1.0) lands mid-pack exactly as [[F7]]
predicts. The noise-ratio→WR relationship is continuous, not a QQQ one-off. Source: [[E6]]. → [[D3]].

### F10 — DATA CAVEAT: all results are MORNING-ONLY
The cached yfinance hourly data is truncated to ~3 bars/day (≈13–15 UTC / first 2 trading
hours). Every number in this web is the **morning-session regime**. A full-session re-pull
could shift magnitudes. → [[H5]], [[E7]].

### F13 — REVERSAL: the hourly edge was a morning-only data-sampling artifact
Re-running the leak-free walk-forward on FULL-session, live-representative data ([[F12]], [[E7]])
flips the headline: QQQ −0.05%/mo (Sh −0.75), SPY −0.05%/mo — NEGATIVE. The +0.34%/mo QQQ
edge ([[F3]], [[F4]], [[F8]]) only existed on the morning-only (3 bars/day) cache. Since the live
bot trades full sessions, this is exactly why it is FLAT. SUPERSEDES [[F3|supersedes]], [[F4|supersedes]], [[F8|supersedes]], [[F9|supersedes]] for the
hourly timescale. The instrument mechanism [[F7]] still holds for the leveraged-ETF failure. → [[D4]].

### F14 — The edge tracks BAR-SAMPLING FREQUENCY, not time-of-day or instrument
Decomposition on full-session data: QQQ AM(3 bars/day) +0.34%/mo Sh 3.72; QQQ PM(4 bars/day)
+0.32%/mo Sh 3.31; QQQ ALL-DAY(7 bars/day) −0.05%/mo Sh −0.75. AM ≈ PM (so NOT time-of-day),
but both ≫ ALL-DAY. RSI(7)/MACD on ~3 bars/day spans ~2 trading days → captures multi-day
mean-reversion (edge); on 7 bars/day it spans ~1 day → intraday noise (no edge). The signal has
edge at a COARSE (~daily) timescale and none at the HOURLY timescale the bot runs. → [[H7]], [[D4]].
CAVEAT: hour-subsampling also recomputes indicators on a coarser series — the clean confirmation
is a real DAILY-bar test ([[E9]]), not just hour-filtering.

### F15 — The edge is REAL at ~3 bars/day; the live bot just trades the wrong frequency
<!-- status: superseded; by: F22; reason: reversed; at: 2026-07-06 -->
E9 (same full-session data, proper OHLC resample to N bars/day): QQQ at **3 bars/day = +0.37%/mo,
Sharpe 4.15, DD −0.6%** (≈4.5% APY — the conservative goal); SPY 3/day +0.22%/mo Sh 2.43. But at
7 bars/day (hourly, what the LIVE bot trades) both are NEGATIVE; at 2/day weaker; 1/day (pure daily)
too sparse over 2yr to test ([[E9]]). The robustness work ([[E4]]) already showed the 3/day regime
survives zero parameter selection (t>3). So the QQQ/SPY edge is genuine at the ~3-bars/day (multi-day
mean-reversion) timescale and absent hourly — F3/F4's numbers were this 3/day regime, mislabeled as
"hourly". ACTIONABLE LEVER: sample ~3 bars/day (≈every 2h), not hourly. CAVEAT: DIA INVERTS (positive
hourly, negative 3/day) → instrument-dependent, not universal; needs multi-instrument + multi-regime
confirmation. Refines [[F13|refines]] (hourly-negative still holds) and [[F14|refines]]. → [[D4]], [[H7]].

### F16 — Daily mean-reversion is REAL (model-free, not an artifact)
12yr daily data (2014–2026, n≈3030): lag-1 autocorrelation SPY −0.117 (t −6.4), QQQ −0.105 (t −5.8),
DIA −0.125 (t −6.9), IWM −0.061 (t −3.3); variance ratios <1 at all horizons. The 3x ETFs have the
SAME serial correlation as their 1x parents (leverage is irrelevant to the edge). Unlike the hourly
"edge" ([[F13]]), this is a genuine statistical property of the price series, not a sampling artifact.
CAVEAT: in the 2022 bear, lag-1 ACF collapses to ~0 — the edge VANISHES in sustained downtrends
(→ must sit out bears; the slope-regime gate already does some of this). Source: daily-history agent ([[E9]]). → [[F17]], [[D4]].

### F17 — THE EXIT IS THE ARCHITECTURAL FLAW (fixed %-stop kills mean-reversion)
The fixed %-target/%-stop exit used everywhere destroys the real mean-reversion edge ([[F16]]) at BOTH
timescales — it exits winning trades on intraband noise before the bounce completes (daily WR 34–41%,
below the 2:1 breakeven, half the instruments negative). Root-cause isolation (leak-free daily WF):
swapping the %-stop for a multi-day HORIZON (time) exit flips EVERY instrument positive — **QQQ +1.99%
APY, Sharpe 0.74, −8% DD, survives 2022**. Cost is not the bottleneck (QQQ holds +1.74% APY at 10bps,
5× spread). This UNIFIES the flat hourly bot ([[F13]]) and the daily result: the signal is fine; the
exit is wrong. ACTIONABLE: replace %-stop with a horizon/time exit for the mean-reversion strategy. → [[D4]], [[H8]].

### F12 — ROOT CAUSE of the morning-only data + a backtest↔live data mismatch
The morning-only data ([[F10]]) is a yfinance quirk: a 1h fetch over a LONG (~710-day) range
returns only ~3 bars/day (the open, 13–15 UTC), but the SAME data fetched in ≤250-day chunks
returns FULL 7-bar sessions (13–20 UTC). Crucially: the **live bot fetches a short ~40-day
window** (`live/signals.py::_fetch_recent_bars`, `trading_days_needed*2`) → it trades on
FULL-session data; but **every backtest/sweep fetched ~710 days → morning-only**. So all
validation to date used a DIFFERENT (thinner, open-only) data distribution than the live bot
actually trades on — a serious backtest↔live gap. Fixed by `tools/fetch_fullsession.py`
(chunked re-pull, ~3× the bars). Re-running [[E3]]/screen on full-session data is [[E7]]. Supersedes the caveat in [[F10]].

### F11 — Penalty-inversion selection bug (fixed)
The sweep scorer multiplied a NEGATIVE base by penalty factors <1, moving it toward zero —
i.e. it *improved* losing configs, so among net-negative candidates it preferred the
worst-behaved one. Guarded (penalties skip base ≤ 0). Mattered precisely in the no-edge
regime this research operates in. Fixed in commit 084f15e.

---

## Hypotheses

### H1 — RESOLVED: edge is sample-luck? → NO for QQQ, YES for TQQQ
Robustness ([[E4]]): QQQ robust (t 3.3–4.3, survives no-selection [[F8]]); TQQQ fragile ([[F6]]). Closed.
(NB: the QQQ edge F8 affirmed was later shown to be a morning-only artifact — [[F13]]; this holds only at the ~3-bars/day timescale, not hourly.)

### H2 — RESOLVED: un-leveraged indices generalize the edge? → YES
Confirmed by the noise-ratio mechanism [[F7]] + SPY/IWM corroboration [[F9]] ([[E6]]). Closed → [[D3]].

### H3 — RESOLVED: edge can be cheaply lifted (ATR stops / entry quality)? → NO
Lever test ([[E5]]): ATR-1.5× helps QQQ marginally (Sh 3.74→4.09) but HURTS TQQQ (2.17→1.30)
— sign-inconsistent, fragile; the asymmetry itself corroborates [[F7]]. require_signals=2
starves trades (2–6 OOS). Neither is a reliable lift. Closed.

### H4 — OPEN: walk-forward should be the sweep's PRIMARY selector (C5)
Single-split holdout selection is biased ([[F2]]); rolling-origin OOS ([[E3]]) is honest.
Promote it inside the sweep. → [[D2]].

### H5 — OPEN: does the edge hold on FULL-session data (not morning-only)?
All current evidence is the morning regime ([[F10]]). Re-pull full-session hourly data and
re-run [[E3]] across instruments. Could change magnitudes and the instrument ranking. → [[E7]].

### H7 — OPEN (most promising): the edge lives at the DAILY timescale, not hourly
[[F14]] shows the mean-reversion edge appears at ~daily/multi-day bar spacing and vanishes
hourly. Test a clean DAILY-bar mean-reversion strategy (more history → more regimes, lower
trade count → lower cost → inherently more conservative). The project's original BTC_DAILY mode
had the best Sharpe / lowest DD — possibly the real thing before the hourly pivot chased a
sampling artifact. → [[E9]]. Directly bears on the conservative goal [[D4]].

### H8 — OPEN (the path to the goal): diversified daily-MR sleeves with a horizon exit
[[F17]] gives a real ~2% APY / −8% DD on a single broad index (QQQ) — about HALF the 3.75% target. To
reach 3.75% at acceptable drawdown without leverage (forbidden by the DD mandate), combine several
low-correlation daily mean-reversion sleeves (SPY/QQQ/DIA/IWM + maybe sector ETFs), each with a horizon
exit + the slope-regime bear gate, and measure the PORTFOLIO Sharpe/DD. Diversification should cut DD
for the same return. → builds on [[F16]], [[F17]]; resolves [[D4]].

### H6 — OPEN: screen instruments by noise-ratio to find where the signal works
[[F7]] gives a one-number predictor (`P(bar range > stop) < ~0.5`, i.e. noise_ratio > 1) of
where this mean-reversion edge survives. Screen a broad universe (large-cap, low-vol ETFs/
indices) by it, then leak-free-validate the top candidates. → operationalized by [[E8]].

---

## Experiments

### E1 — Documented optimistic sweep (historical) → artifact, feeds [[F1]].
### E2 — Fixed-10% realistic HOLDOUT sweep (2026-06-19)
`sweep.py TICKER --sizing fixed --fixed-pct 0.10 --mode realistic`. Biased by holdout selection ([[F2]]). Feeds [[F1]].
### E3 — Leak-free walk-forward (PRIMARY evidence)
domain: backtest_engine
`tools/walkforward_eval.py`. Produced [[F3]], [[F4]], [[F5]], [[F6]].
### E4 — RESOLVED: edge robustness & confidence
QQQ robust (t 3.3–4.3, survives zero-selection), TQQQ fragile (t 0.37 on recent data); both
decay over time. Inert to folds/objective; survives grid width. Resolved [[H1]], produced [[F6]], [[F8]].
### E5 — RESOLVED: edge-lift levers
ATR stops + require_signals=2 in leak-free OOS. Neither lifts the edge reliably. Resolved [[H3]].
### E6 — RESOLVED: QQQ structural deep-dive + SPY/IWM
Exit-type decomposition + noise-ratio across 7 instruments + SPY/IWM fetch. Produced the
mechanism [[F7]], [[F9]]; resolved [[H2]], explained [[F4]].
### E7 — IN PROGRESS: full-session data re-pull & re-validate (now matches live)
`tools/fetch_fullsession.py` rebuilds full-session 1h data (root cause [[F12]]). Gathering a
conservative universe (broad indices + low-vol/dividend + bond ETFs). Then re-run the
noise-ratio screen [[E8]] + leak-free walk-forward [[E3]] on data that finally matches what the
live bot trades. Resolves [[H5]]; feeds the conservative-target question [[D4]].
### E8 — DONE: noise-ratio instrument screener
`tools/instrument_screen.py` — ranks a universe by `P(bar range > stop)`. On full-session data:
bonds ultra-friendly (but target unreachable), indices friendly, leveraged noise-dominated.
The screen is necessary-not-sufficient (doesn't test target reachability or timescale [[F14]]).

### E9 — DONE (part 1): edge vs bar-duration on resampled full-session data
Produced [[F15]]: QQQ/SPY edge peaks at ~3 bars/day (QQQ +0.37%/mo Sh 4.15), negative hourly,
DIA inverts. Pure daily (1/day) too sparse over 2yr. Part 2 (multi-year DAILY bars across regimes
incl. 2022 bear) is in progress via a research agent — the decisive long-history daily test.

---

## Decisions / Gates

### D1 — Edge go/no-go (roadmap gate #1) — UPDATED
Net edge is ~0.2–0.34%/mo OOS — below the ~0.5%/mo income threshold, so this is NOT an income
engine. BUT it is a **genuine, structurally-explained, near-zero-drawdown high-Sharpe vehicle on
the right instrument** ([[F3]], [[F4]], [[F7]], [[F8]], [[F9]]) — exactly the "bond-ETF alternative"
the project set out to be. Verdict: **don't kill it — reframe it** as a capital-preservation /
high-Sharpe product AND **switch instrument focus from 3x ETFs to un-leveraged broad indices**.
Caveats: morning-only data ([[F10]]), edge decaying ([[F3]]), TQQQ fragile ([[F6]]).
**CORRECTION ([[F13]]):** the high-Sharpe premise above ([[F3]], [[F4]], [[F8]]) was a MORNING-ONLY
data-sampling artifact — on full-session, live-representative data the hourly edge is FLAT/negative.
The reframe held only at a ~3-bars/day timescale ([[F22]] — superseding [[F15]]: the 3/day
per-instrument measurement is real but does NOT survive a static-blend benchmark as a portfolio),
NOT the hourly bot this gate was about.
Overtaken in substance by the sobering update [[D4]] and the final go/no-go [[D6]] (the evidence-backed
recommendation is a STATIC allocation, not the active engine).

### D2 — Promote walk-forward to primary selector (C5)
Make the sweep select on rolling-origin OOS, not single-split holdout ([[H4]]). Now well-motivated
([[E4]] shows the lens is stable). Needs a design pass on integration with the 5-phase sweep.

### D3 — Adopt the noise-ratio instrument rule; make QQQ/SPY first-class candidates
Actionable design rule from [[F7]]: **only deploy this signal where `stop_pct` > median intraday
bar range (noise_ratio > 1)**. Concretely: (1) run full sweeps on QQQ + SPY (+ IWM check) as
production candidates; (2) build the screener [[E8]] to apply the rule to a wider universe; (3) do
NOT size up the leveraged ETFs on this architecture. NOTE: changing the live instrument touches the
armed trader path — requires sign-off; this node records the evidence-backed recommendation, not an applied change.

### D4 — is the original ~3.75% APY conservative goal achievable? — UPDATED (sobering)
3.75% APY ≈ +0.307%/mo. The earlier "yes on QQQ" was a data artifact ([[F13]]). On full-session,
live-representative data the HOURLY mean-reversion architecture has NO reliable edge on any
instrument tested (QQQ/SPY negative; bonds: target unreachable; leveraged: noise-dominated [[F7]]).
DEFINITIVE ANSWER (12yr daily, model-free + leak-free): daily mean-reversion is REAL ([[F16]]), but the
project's fixed %-stop EXIT destroys it ([[F17]]); a multi-day HORIZON exit recovers it. With the fix,
**QQQ ≈ +2% APY, Sharpe 0.74, −8% DD, regime-robust (survives 2022)** — about HALF the 3.75% target on
a single index. 3.75% at acceptable drawdown requires DIVERSIFYING several low-correlation daily-MR
sleeves ([[H8]]) — NOT leverage (the 3x ETFs hit 3.75%+ but at −25% to −40% DD and invert in bears,
violating the capital-preservation mandate). So: **the goal is reachable, but as a diversified DAILY
mean-reversion product with a horizon exit and a bear gate — not the hourly %-stop bot.** Concrete next
build: daily MR + time/horizon exit + slope-regime gate, multi-instrument portfolio ([[H8]]). The
single highest-value change is the EXIT ([[F17]]). (The ~3-bars/day note [[F15]] was the weaker, less
robust cousin and is formally superseded by [[F22]] — its timing does not survive the static-blend
benchmark; the daily horizon-exit result replaced it as the recommended direction.)

---

## Strategy Lab — leverage-free daily-MR (2026-06-22, independent replication + extension)

> Reproducible harness: `tools/mr_daily_lab.py` (read-only; yfinance daily, 2014–2026).

### E10 — Independent daily-MR replication + strategy lab
<!-- status: current; conf: 0.85; at: 2026-06-22 -->
Model-free, leak-free harness (`tools/mr_daily_lab.py`) on 12yr adjusted daily data:
lag-1 autocorrelation + variance ratios; dip entry (buy the close of a down day) with
horizon vs fixed %-stop exits; diversified multi-sleeve portfolios; long-only
cross-sectional sector rotation; conditional entries; vol-targeted vs adaptive-Kelly
sizing; bond signal tests. Produces [[F18|produces]], [[F19|produces]], [[F20|produces]],
[[F21|produces]]; extends the daily direction of [[E9|supports]].

### F18 — F16 replicates exactly, but its significance was ~3× overstated
<!-- status: current; conf: 0.8; at: 2026-06-22 -->
Independent 12yr daily ([[E10|evidenced_by]]) reproduces F16's lag-1 autocorrelations
almost exactly (SPY −0.113 vs −0.117, QQQ −0.100, DIA −0.122, IWM −0.058) and variance
ratios <1. BUT F16's naive `t = ρ√n` ignores volatility clustering; under a
heteroskedasticity-robust SE the t-stats fall ~3× (SPY −6.3→−2.2, IWM −1.7 = n.s.), and
non-overlapping trades leave only QQQ at t>2. So the mean-reversion structure is REAL but
**modest**, not overwhelming. The 2022-bear collapse is confirmed (ρ→0, |t|<1 for all).
Refines [[F16|refines]].

### F19 — Confirmed: the EXIT, not the entry, is the dominant lever
<!-- status: current; conf: 0.85; at: 2026-06-22 -->
Within-comparison on identical dip entries ([[E10|evidenced_by]]): a 5-day HORIZON exit
yields +29 bps/trade on SPY (+38 QQQ, +80 TQQQ), while a fixed ±0.8% stop/target yields
−2 bps (−27 TQQQ, 36% WR) — same entry, opposite sign. The tight band is whipsawed inside
daily noise, worst on 3× ETFs. Independently confirms [[F17|supports]] and unifies it with
the noise-ratio mechanism [[F7|supports]]. The horizon exit does NOT rescue the 2022 bear
(3× −166/−346 bps/trade) → the regime gate is non-negotiable, independent of exit.

### F20 — What does NOT work (four negative results)
<!-- status: current; conf: 0.8; at: 2026-06-22 -->
From the lab ([[E10|evidenced_by]]): (1) **long-only cross-sectional** sector rotation
(buy the most-oversold of 9 SPDRs) underperforms sector buy&hold (Sharpe 0.44 vs 0.65,
−43% DD) — it loads falling knives; real cross-sectional MR needs the forbidden short leg.
(2) **Sizing — the estimator SHAPE matters** (corrected after review): a *continuous*
textbook half-Kelly HURTS (QQQ Sharpe 0.72→0.48) because its fraction (CV 0.77) chases the
noisy win/loss-ratio `b`. BUT that is a strawman for the project's LIVE `adaptive_kelly_multiplier`
— a coarse 4-tier *win-rate* step that never computes `b` (CV 0.23): re-run on the same trades
it is ~Sharpe-NEUTRAL (0.68 ≈ the fixed baseline), neither helping nor hurting (and it is bypassed
on the active fixed-sizing path). So only a noisy continuous Kelly is harmful; vol-targeting is the
sizing that actively helps (0.56→0.67).
(3) **Low-vol entry filtering** hurts (Sharpe 0.56→0.26): the biggest dips revert hardest.
(4) **Bond signal-trading** (corrected): the 200d *equity* bear gate is wrong-signed for
(anti-correlated) bonds — gated, TLT/IEF dips lose to B&H; UN-gated, a TLT dip beats B&H
(Sharpe 0.19 vs 0.10, lower DD) but insignificantly (bootstrap straddles 0) and IEF still loses.
Net: hold bonds as PASSIVE ballast (the −0.09 equity correlation), not for a signal edge.
Relates the noise mechanism [[F7|relates]].

### F21 — The honest leverage-free ceiling + the recommended build
<!-- status: current; conf: 0.8; at: 2026-06-22 -->
Best leverage-free config ([[E10|evidenced_by]]): EQUAL-WEIGHT diversified daily-MR sleeves
(equities + gold + passive-bond ballast) + 200d bear gate + VOL-TARGETED (not Kelly) sizing
→ ~Sharpe 0.66, ~4%/yr, −10% DD. "Smart" trailing-Sharpe weighting underperforms equal-weight
(0.42 vs 0.66). The ~3.75% target is reachable only by levering the low-vol (~6%) portfolio
to a vol target (≈5.8%/yr at 1.5×, −19% DD) — you buy return with drawdown, not Sharpe. So
leverage-free daily-MR is a solid BALANCED strategy (Sharpe ~0.6, equity-like DD), NOT a
near-zero-DD bond alternative — that headline was the morning-only artifact. Refines
[[H8|refines]] and [[D4|refines]]; drives [[D5|drives]].

### D5 — Recommended next architecture (the leverage-free daily-MR product)
<!-- status: current; conf: 0.7; at: 2026-06-22 -->
Build: equal-weight portfolio of daily mean-reversion sleeves on un-leveraged equities
(QQQ/SPY/IWM/DIA) + gold (GLD), each = buy-the-dip + multi-day HORIZON exit + slope/200d
bear gate, with VOL-TARGETED position sizing and passive bond ballast for correlation.
DROP, on evidence: the hourly timescale, the fixed %-stop exit, 3× leverage, and long-only
cross-sectional rotation. PREFER vol-targeted sizing (it lifts Sharpe); the live WR-tiered
adaptive-Kelly is ~Sharpe-neutral so keep-or-replace is a wash (only a noisy *continuous*
Kelly is harmful — [[F20]]). Expected ~Sharpe 0.6, ~4%/yr leverage-free
(or ~6% vol-targeted at higher DD). Builds on [[F19|builds_on]], [[F20|builds_on]];
relates the hourly/leverage evidence [[F13|relates]], [[F7|relates]]. Refines [[D4|refines]].
NOTE: changing the live instrument/exit/sizing touches the armed trader path — sign-off
required; this records the evidence-backed recommendation, not an applied change.
⚠ OOS UPDATE ([[F22]]): a walk-forward stress test shows this build does NOT beat buy&hold
risk-adjusted (Sharpe 0.69 vs 0.80) — its value is capital-preservation via reduced exposure,
which a static equity/cash blend achieves more simply at higher Sharpe. So D5 stands only as a
low-drawdown CAPITAL-PRESERVATION overlay; the go/no-go for an *active* alpha engine is negative.

### E11 — Out-of-sample / walk-forward stress test of the D5 build
<!-- status: current; conf: 0.85; at: 2026-06-22 -->
Stress-tested the D5 equal-weight daily-MR portfolio (QQQ/SPY/IWM/DIA/GLD, dip+5d+200d gate,
net 5bps) against an equal-weight BUY&HOLD of the same 5 assets: per-calendar-year, first-half
vs second-half, held-out COVID-2020 + 2022-bear regimes, and a 20-day block bootstrap of the
per-day Sharpe difference. Reproducible: `tools/mr_daily_lab.py oos`. Produces [[F22|produces]].

### F22 — OOS verdict: the daily-MR timing has NO risk-adjusted edge over buy&hold
<!-- status: current; conf: 0.8; at: 2026-06-22 -->
Stress test ([[E11|evidenced_by]]): the D5 equal-weight daily-MR portfolio scores Sharpe 0.69
vs **0.80 for an equal-weight BUY&HOLD of the same 5 assets**, and the 20-day block bootstrap of
the per-day Sharpe DIFFERENCE is [−1.12, −0.05] (`tools/mr_daily_lab.py oos`, seed 0) — the timing
is *significantly WORSE* risk-adjusted (upper bound just below 0). NOT front-loaded (2nd-half Sharpe 0.94 > 1st-half
0.42), so the negative is robust, not a one-period artifact. What timing buys is REDUCED EXPOSURE:
~half the return (6.2% vs 12.1%) at ~half the drawdown (−13.9% vs −29.5%), 87% time-in-market.
Its only edge is defensive in SLOW bears (2022 −8% vs −17%); it fails in FAST crashes (COVID
≈−11% both — the 200d gate is too slow). DECISIVE: a static ~50/50 equity/cash blend has the SAME
Sharpe as full buy&hold (0.80; cash-scaling is Sharpe-invariant) at the timing strategy's return/DD
— so daily-MR timing is DOMINATED by trivial static de-risking. This is the same lesson as the
hourly arc ([[F13|relates]]): a flattering backtest number that doesn't survive the honest
benchmark. Refines [[F21|refines]] and [[D5|refines]]; bears on the go/no-go [[D1|drives]], [[D4|drives]].
Directly disputes the "edge is REAL at ~3 bars/day" framing ([[F15|contradicts]]): the per-instrument
3/day Sharpe doesn't survive as a portfolio held against an equal-weight buy&hold of the same assets.

### E12 — Go/no-go: active daily-MR vs static blends (head-to-head)
tools/mr_daily_lab.py gonogo — 2014-2026 cached data. The D5 equal-weight daily-MR portfolio (QQQ/SPY/IWM/DIA/GLD, dip + 5d horizon + 200d gate) scores Sharpe 0.69 / 6.2%/yr / -13.9% DD, vs static 50/50 equity/cash (Sharpe 0.80), static 60/40 equity/bond via IEF (0.86), and 100% buy&hold (0.80). The 20-day block bootstrap of (active - static-50/50) Sharpe diff is [-0.41, +0.48] — straddles zero (within noise). Extends the OOS test.
Links: [[F22|relates]] · [[F21|relates]].
_— captured claude/strategy-go-nogo@54e6637, 2026-06-22_

### D6 — GO/NO-GO: the active engine is not justified — recommend a static allocation
Decisive comparison (E12): the active daily-MR engine shows NO DEMONSTRATED ADVANTAGE over a trivial static blend of the same assets — active Sharpe 0.69 / 6.2%/yr vs static 50/50 (0.80) and 60/40 equity/bond (0.86) at comparable return, with the active-minus-static Sharpe-diff bootstrap straddling zero (within noise). It is not better, while carrying all the trading, cost and live-execution risk. This unifies the arc: F22 (active doesn't beat buy&hold), F13/F17 (no hourly edge; the %-stop EXIT was the flaw), and the flat live confirmed-fill result (the ~+35% headline is a paper mark-price ESTIMATION ARTIFACT on time/target exits, not real, and not a fixable execution bug). RECOMMENDATION: the honest bond-alternative is a STATIC allocation (e.g. 50/50 or 60/40 equity/bond), de-risked and periodically rebalanced — not the active engine. NOTE: changing the live deployment touches the armed trader path — sign-off required; this records the evidence-backed recommendation, not an applied change.
⚠ UPDATE (2026-06-25, adversarially verified): D6 is CONFIRMED & STRENGTHENED and its one open gap is closed. [[F24]]: the RSI+MACD signal D6 never tested (it only used any-down-day) does NOT rescue the active engine — RSI-conditioning is no-better-or-worse on every metric. [[F25]]: ~2× the data (2000-2026, +dot-com +2008) NARROWS the (active − static-50/50) Sharpe CI to [−0.34,+0.30] (still straddles 0) → the "underpowered" objection is retired. Honest nuance for the capital-preservation mandate: the active engine does have the lowest drawdown / best Calmar of any static blend BY POINT ESTIMATE, but that edge is PATH-DEPENDENT (the paired maxDD/Calmar bootstrap straddles 0) and a static 60/40 beats it on Sharpe AND return — so the static-allocation recommendation STANDS; keep the active engine only as a low-DD overlay, not an alpha engine. SEPARATELY [[F26]]: the slope-regime "core innovation" this whole arc implicitly assumed is in fact dead-wired/stripped from the backtests, so the gate never actually contributed to any of these numbers.
Links: [[E12|evidenced_by]] · [[F22|builds_on]] · [[D5|refines]] · [[D4|refines]] · [[F24|builds_on]] · [[F25|builds_on]] · [[F26|relates]].
_— captured claude/strategy-go-nogo@54e6637, 2026-06-22 (updated development@c9a20a8, 2026-06-25)_

### F23 — Per-mode RSI period + MACD windows never reach the entry signal (code bug)
momentum_signal() (src/signals/momentum.py:38-39) recomputes RSI and MACD with HARDCODED defaults (RSI 14, MACD 12/26/9), ignoring the per-mode RSI_PERIOD_*/MACD_* config that add_momentum_features is handed (it uses them only for the stored rsi/macd_hist columns). Proven empirically: momentum_signal is byte-identical for period 7 vs 14 while stored rsi/macd_hist differ. The live trader rides this exact path (live/signals.py:95 -> build_features -> add_momentum_features -> momentum_signal), so the armed bot trades on RSI-14 / MACD-12-26-9 regardless of config. The config's '# DEAD LEVER (robust to window changes)' comments are empirically correct but MISATTRIBUTED: the cause is this code path, not market structure. Only the RSI oversold/overbought THRESHOLDS are threaded through and effective. Fixing changes live entries AND invalidates every prior sweep tuned with the bug present -> needs re-sweep + sign-off with the trader stopped, not a unilateral edit. Relates to [[D4]].
Links: [[D4|relates]].
_— captured claude/robustness@b408769, 2026-06-23_

---

## Strategy Lab — go/no-go closure (2026-06-25, adversarially verified)

> Closes D6's one open gap (it had only tested a bare "any down day" entry, never the project's
> RSI+MACD signal) and retires the "underpowered CI" objection with a 26yr extension. All three
> results were reproduced byte-for-byte and red-teamed by a 4-agent adversarial panel (leak check,
> RSI correctness, git archaeology, devil's-advocate-for-the-active-engine + completeness critic).

### E13 — RSI-conditioned go/no-go: the entry signal D6 never tested
<!-- status: current; conf: 0.85; at: 2026-06-25 -->
D6/[[E12]] declared the active engine unjustified using a BARE "any down day" entry — never the
project's ACTUAL signal. E13 adds a Wilder RSI + an `rsi_thresh` param to `mr_daily_lab.py::sleeve()`
and races RSI<30/35/40 actives against the bare active and the static blends, reporting Calmar +
time-in-market and bootstrapping each vs static 50/50. Leak-free (RSI[d] is known at the dip close,
same bar the entry already uses; a future-price scramble leaves the return head unchanged, max abs
diff 0.0). Reproducible: `tools/mr_daily_lab.py gonogo`. Produces [[F24|produces]]; extends [[E12|extends]].
_— captured development@cf78fcd, 2026-06-25_

### F24 — RSI-conditioning never overturns D6 (the project's own signal does not rescue the engine)
<!-- status: current; conf: 0.85; at: 2026-06-25 -->
[[E13|evidenced_by]]: requiring RSI<30/35/40 on the dip NEVER lifts the (active − static-50/50)
Sharpe-diff CI above 0. On 2014-2026 the RSI actives are strictly WORSE than the bare active on
Calmar (0.16/0.28/0.30 vs 0.44) and their Sharpe-spread CIs sit below 0 — though that is partly a
mechanical time-in-market artifact (they sit in cash 77–97%; the bootstrap is the Sharpe of the
spread `active − 0.5·e`), so the "worse" claim leans on Calmar/maxDD, which is immune. On the 26yr
window ([[F25]]) the RSI CIs merely straddle 0 (no edge, not worse). The bare active still does not
beat static on Sharpe. So the one gap that could have overturned D6 — "D6 used any-down-day, not the
real RSI+MACD signal" — is CLOSED: the real signal at the daily timescale does not rescue the engine.
Refines [[D6|refines]]; supports [[F22|supports]].
_— captured development@cf78fcd, 2026-06-25_

### E14 — long-history (2000-2026) go/no-go + 26yr autocorrelation + capital-preservation bootstrap
<!-- status: current; conf: 0.85; at: 2026-06-25 -->
Retires the "underpowered CI" objection to [[D6]]/[[F22]] by re-running the go/no-go on ~2× the data
(+ dot-com bust + 2008 GFC). `tools/mr_daily_lab.py gonogolong`: fetches its OWN 2000-start data into a
separate cache (cannot perturb the 2014-based [[F18]]–[[F22]]), basket = ^GSPC+QQQ+IWM+DIA (four DISTINCT
equity exposures live from ≤2000-05; GLD/SPY dropped to avoid 2004-truncation / S&P double-count — the
naive "add ^GSPC + change START" one-liner would have silently done both), and adds a PAIRED
maxDD/Calmar-difference block bootstrap — the significance test a capital-preservation mandate actually
needs (Sharpe is time-in-market sensitive). Produces [[F25|produces]]; extends [[E11|extends]], [[E12|extends]].
_— captured development@c97b56d, 2026-06-25 (hardened @c9a20a8)_

### F25 — 26yr data CONFIRMS D6; the MR autocorrelation is robustly real; the only pro-active edge is path-dependent drawdown
<!-- status: current; conf: 0.85; at: 2026-06-25 -->
[[E14|evidenced_by]], 2000-2026 / 6654 days / 332 blocks: (1) the negative lag-1 autocorrelation is
robustly REAL over 26yr under the [[F18]] robust SE — ^GSPC t −3.64, DIA −3.20, IWM −3.02, QQQ −2.55
(NOT a 2014-2026 artifact; strengthens [[F16]]/[[F18]] over a window with two extra crises). (2) NO Sharpe
edge: the (bare-active − static-50/50) CI NARROWS from [−0.41,+0.48] to [−0.34,+0.30] and still straddles
0 → D6 confirmed with more power; the "underpowered" objection is retired. (3) Capital preservation: the
active engine has the lowest maxDD / best Calmar of any listed static blend on BOTH windows by point
estimate (active −19.9% DD vs static-50/50 −34.1% vs B&H −56.5%; Calmar 0.19 vs 0.11), BUT the paired
maxDD/Calmar-difference bootstrap STRADDLES 0 ([−15.8,+18.4] / [−0.18,+0.19]) → the drawdown edge is
PATH-DEPENDENT, not statistically significant; and a static 60/40 equity/bond BEATS the active engine on
Sharpe AND return (active wins only on drawdown). Confirms [[F22|supports]]; refines [[D6|refines]].
_— captured development@c97b56d, 2026-06-25_

### E15 — engine.py slope-regime wiring audit (git archaeology + 4-combo entry test)
<!-- status: current; conf: 0.9; at: 2026-06-25 -->
Audit (read-only) of whether CLAUDE.md's "core innovation" — the 6-state slope-regime gate — actually
runs: read the current `generate_trades()`, the `runner.py` call site, every caller (main/sweep/
walk_forward/live), bisected the gate's history (`git log -S'no_long_regimes'`, merge-parent inspection),
and ran a 4-combo entry-signal equality test on synthetic OHLCV exercising all 6 regimes. Produces [[F26|produces]].
_— captured development (read-only audit), 2026-06-25_

### F26 — the "core innovation" (slope-regime gate) is DEAD-WIRED AND STRIPPED; a 2nd vol-regime gate runs against config
<!-- status: current; conf: 0.9; at: 2026-06-25 -->
[[E15|evidenced_by]]: CLAUDE.md's slope-regime classifier (§4/§12, "the entire foundation") does NOT gate
entries in any backtest. (a) The entry-gating block (`no_long_regimes`/`flat_regimes`/`longs_only` short
suppression) was added only on a feature branch (`3da676b`), never reached `main`, and was DELETED by the
merge `9b4648e` (2026-03-22) resolving to main's gate-less `generate_trades` — NOT by `8a1f42e`/`176adde`.
(b) `runner.py` calls `generate_trades()` WITHOUT `use_slope_regime`/`longs_only` anyway, so main.py/sweep.py
never pass them; only `walk_forward.py` threads them and it is test-only (main.py `--mode=walk-forward` is
dead). (c) Empirically all 4 (use_slope_regime, longs_only) combos give byte-identical entries; the flags
only mutate `regime_kelly_mult`, which no backtest path reads. SEPARATE NON-INERT BUG: `generate_trades()`
has `use_regime_filter` default True and `runner.py` never threads `config.USE_REGIME_FILTER` (=False) into
it → every backtest silently runs a 200d `trend_direction`+`vol_regime` entry gate config says is OFF (this
one DOES change entries; flagged for its own session). IMPLICATION: CLAUDE.md §1's regime-dependent Sharpe
table and the "core innovation" claim describe code that does not run; restoring the gate needs an engine.py
re-insert (`git show 194ae6d:src/strategy/engine.py`) + a `runner.py` wiring. Same bug-class as [[F23]] (a
config lever that never reaches the signal). Relates [[F23|relates]], [[D6|relates]].
_— captured development (read-only audit), 2026-06-25_

### F27 — [ctx] The context layer is a stdlib, read-only, CI-guarded ctx CLI by design — not a vector DB or MCP
Design decision (unanimous across the 12-lane context-access analysis): give agents maximum project access by extending a single-file, pure-stdlib, READ-ONLY, CI-guarded CLI (tools/ctx.py over context_map.json + RESEARCH_WEB.md + live/state.db), rather than a vector DB or an MCP server — both add dependencies and ops for near-zero benefit at this repo size. Shipped KA0-KA8; deferred by decision KA9 (vector/embedding index + hand-built MCP). This node is the WHY behind the whole context layer; the context-web open-ends hang off it (an observation/design-decision, not experiment-backed). domain: context-web.
_— captured development@1806b74, 2026-06-26_

### E16 — DONE: [ctx] context-layer audit + hardening this session (SF-1..4, VD-3a/b, VD-4/5, DP-1)
A 30-agent audit of the context layer + fixes, all on development, each test-guarded: SF-1 ctx delta errors on an unresolvable --since (was silently diffing HEAD); SF-2 ctx web --lint exits 2/1/0 by integrity; SF-3 ctx impact warns on ambiguous symbols; SF-4 ctx perf leads with the honest CONFIRMED edge + loud absent-state.db; VD-3a corrected AGENTS.md's false edit-fence claim; VD-3b self-protected context_map.json; VD-4 fixed stale pi-ops-automation->development refs; VD-5 hardened the honest-state banner; DP-1 ctx why now flags contradicted-but-current + fragile nodes. The OPEN context-web nodes below are the deferred follow-ups. domain: context-web.
Links: [[F27|relates]] · [[F13|relates]] · [[D6|relates]].
_— captured development@1806b74, 2026-06-26_

### H9 — OPEN [ctx]: VD-1 — F23 armed RSI/MACD config-ignored bug is UNGUARDED; write an asserting test
domain: context_kit
F23 records a LIVE bug: momentum_signal/get_current_signal recompute RSI/MACD with hardcoded defaults, ignoring per-mode config, and the armed bot rides this path. ctx claims confirms F23 UNGUARDED. Open: write a test that ASSERTS the per-mode periods are ignored (flips F23 GUARDED) + add a guarded_by bridge; scope the config-routing fix on a branch without touching the armed path.
Links: [[F27|relates]] · [[F23|relates]].
_— captured development@1806b74, 2026-06-26_

### D7 — RESOLVED [ctx]: VD-2 — F15 formally superseded by F22 (reason: reversed)
F15 ('edge real at ~3 bars/day') was status:current but contradicted by the more rigorous F22->D6, producing 2 live advisories (D1,D4). Its per-instrument measurement still holds; F22 overturns the actionable framing. The open decision was: tombstone F15 by F22 (re-pointing D1/D4 to cite F22 first) vs leave it disputed-but-live; optionally escalate 'N current nodes contradicted by a later node' to a scored health deduction.
**RESOLUTION (2026-07-06): tombstoned.** F15 is superseded by [[F22]] (reason: reversed) — its HEADLINE claim ('the edge is REAL at ~3 bars/day', an actionable lever) did not survive the honest static-blend benchmark ([[F22]]), the 26yr confirmation ([[F25]]), or the D6 arc; a node whose headline is overturned should not sit status:current on the strength of a surviving footnote (the per-instrument 3/day Sharpe measurement, which the tombstoned body preserves). D1 and D4 were re-pointed to cite [[F22]] first in the same change — note.py supersede REFUSES the write until they are, so the stale-cite guard works as designed. The optional escalation ('N current findings contradicted by a later node' as a scored health deduction) is NOT built here: it is exactly [[H11]]'s semantic-staleness detector — deferred there rather than duplicated.
Links: [[F27|relates]] · [[F15|relates]] · [[F22|relates]] · [[D6|relates]] · [[H11|relates]].
_— captured development@1806b74, 2026-06-26; resolved development@5bc7d7e, 2026-07-06_

### H10 — OPEN [ctx]: DP-3 — add reversal-arc edges so ctx walk/why narrates Sharpe-94 -> static-allocation end-to-end
The repo's most important epistemic story (headline Sharpe 25-94 -> D6 static allocation, via F13/F14 morning-only artifact -> F15/F16 daily edge -> F17/F19 stop destroys it -> F22/D6) should be fully walkable with ctx walk/why alone. Open: test whether traversal reconstructs it without prose, add the missing/untyped edges, and verify the human 'see F13/F14/F15/D4' citations still point at the live frontier.
Links: [[F27|relates]] · [[F13|relates]] · [[F22|relates]] · [[D6|relates]].
_— captured development@1806b74, 2026-06-26_

### H11 — OPEN [ctx]: DP-4 — ctx stale, a semantic-staleness detector independent of author declaration
The epistemic layer detects DECLARED staleness but is blind to SEMANTIC staleness (F15 is the proof: 0 cited evidence, contradicted, still current, still 100/100 health). Open: prototype a read-only ctx stale heuristic flagging current findings whose only live evidence predates a later contradicting/superseding node, ranked as a decay list. Extends DP-1 (ctx why fragility, shipped). Deferred item #9 (confidence-decay).
Links: [[F27|relates]] · [[F15|relates]] · [[F22|relates]].
_— captured development@1806b74, 2026-06-26_

### H12 — OPEN [ctx]: DP-5 — gate the live-trader preflight + CI on context-layer health (ctx health / web --lint)
ops/preflight_trader_start.sh (10-check gate) and CI assert nothing about context-layer integrity, so a drifted manifest, dangling link, or stale-cite wouldn't block arming the trader or merging. Open: slot a ctx health / web --lint==0 assertion into preflight + CI (SF-2 now provides exit codes), handling absent-state.db, plus a ctx.py/note.py CLI smoke test.
Links: [[F27|relates]] · [[D6|relates]].
_— captured development@1806b74, 2026-06-26_

### H13 — OPEN [ctx]: DP-6 — make concerns/gated_by bridges auditable (guard behavior-asserting bridges)
Of 16 graph bridges only 2 are implemented_in (the only relation ctx claims audits for guard tests); the other 14 concerns/gated_by bridges (guarded_by:None) are never checked, so a 'concerns' finding asserting code behavior (e.g. F17 concerns compute_trade_returns) can never be flagged UNGUARDED. Open: extend ctx claims to surface concerns/gated_by bridges naming a ::symbol as guard candidates; upgrade behavior-asserting ones to implemented_in+guarded_by.
Links: [[F27|relates]] · [[F17|relates]] · [[F23|relates]].
_— captured development@1806b74, 2026-06-26_

### H14 — OPEN [ctx]: DP-7 — add the F26 idea<->code bridge for the dead-wired slope-regime gate
F26 (the slope-regime 'core innovation' is stripped from generate_trades() and never wired into runner.py) has NO graph_bridge. Open: add a bridge linking F26 to engine.py::generate_trades / runner.py so ctx impact surfaces the dead-wire when those symbols are edited. Note: context_map.json is now self-fenced, so the bridge edit needs the escape hatch.
Links: [[F27|relates]] · [[F26|relates]] · [[D6|relates]].
_— captured development@1806b74, 2026-06-26_

### H15 — OPEN [ctx]: DP-8 — ctx drift, a three-store consistency guard (web vs experiments.jsonl vs context_map bridges)
Three claim/data stores have no cross-checker: RESEARCH_WEB.md (current truth), experiments.jsonl (still holds holdout-biased 'winners' SOXL/LABU/TNA that F2 proves are biased), and context_map.json bridges. Open: a read-only ctx drift / CI check flagging experiments.jsonl rows whose headline contradicts a current Finding (F2/F13/F22) without a tombstone, plus bridge targets that no longer resolve. Note: cross-store semantic match is heuristic, so this is an advisory not a hard guard.
Links: [[F27|relates]] · [[F2|relates]] · [[F22|relates]].
_— captured development@1806b74, 2026-06-26_

### H16 — OPEN [ctx]: DP-9 — surface ctx perf's CONFIRMED honest edge in the ctx brief/frontier rider
SF-4 made ctx perf lead with CONFIRMED, but the honest-state rider in ctx brief/frontier still pulls only node counts, not the live CONFIRMED edge — so the ~24x ALL-vs-CONFIRMED gap (+37% vs +1.5%) can still be skimmed past at cold start. Open: have the rider pull ctx perf's CONFIRMED line alongside node counts, degrading gracefully when state.db is absent.
Links: [[F27|relates]] · [[D6|relates]].
_— captured development@1806b74, 2026-06-26_

### H17 — OPEN [ctx]: DP-10 — ctx memory --lint: lint copied repo-facts in out-of-repo .claude operator memory
The in-repo claim web and the per-user .claude memory/*.md are disjoint with NO bridge; memory files hand-copy drift-prone repo facts (branch model, CI triggers, base SHA), synced only by unenforced convention (K6). Open: a read-only ctx memory --lint comparing copied facts to live config/ctx; move durable operator rules into a git-tracked doc; resolve K6's dangling session link.
Links: [[F27|relates]].
_— captured development@1806b74, 2026-06-26_

### H18 — OPEN [ctx]: finish the pi-ops-automation->development sweep (live/CONTEXT.md, fenced) + add a CI branch-drift guard
VD-4 corrected most docs but live/CONTEXT.md still names the dead pi-ops-automation deploy branch (it sits behind the live/ edit-fence, so needs a trader-stopped approved edit). Open: finish the sweep and add a CI assertion (extend tests/test_context_map.py) that no tracked doc names a branch other than context_map.json deploy_branch, so prose branch-drift fails CI.
Links: [[F27|relates]].
_— captured development@1806b74, 2026-06-26_

### H19 — OPEN: Regime lag during intra-bull corrections (the #1 unsolved active-engine problem)
The 252-MA stays bullish through -20-30% intra-bull corrections (Jun/Aug 2024, Apr 2021), so the active engine buys RSI dips into falling knives — the primary documented unsolved problem, with untried mitigations (ATR stops, softer 50-MA gate, vol circuit-breaker) hanging off it. MOOT while the active engine stays retired (D6); load-bearing only if it is ever revisited.
Links: [[D6|relates]] · [[F17|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H20 — OPEN: ATR-scaled stops & targets (sit outside intraday noise)
The fixed ~0.5% stop sits inside TQQQ intraday ATR; scaling stop/target by recent ATR would place them outside noise. USE_ATR_DYNAMIC_STOPS exists but compute_trade_returns() has no implementation. Recurs across CLAUDE.md §10, MODEL_HISTORY, IMPROVEMENT_PLAN D1/D2. Conditional on revisiting the active engine (D6).
Links: [[F7|relates]] · [[F17|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H21 — OPEN: Softer 5% 50-MA gate for intra-bull corrections (config at 0.02, proposed 0.05)
Gate STRONG_BULL entries only when price is >5% below the 50-MA (vs the strict any-touch gate that filtered 71/83 trades). Bad Jun-2024 entries sit 7-15% below; good Aug-2023 ones 1-3% below. STRONG_BULL_SOFT_50MA_PCT is at 0.02, not the proposed 0.05, and unvalidated. Conditional on the active engine (D6).
Links: [[D6|relates]] · [[F17|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H22 — OPEN: Entry quality over quantity (require both signals / deeper RSI / EV-per-trade objective)
The signal fires on ~50% of bars but the edge is thin; require BOTH momentum AND volume, a deeper RSI, more regime conviction, and optimize EV/trade not trade count (the churn-rewarding-Sharpe problem). IMPROVEMENT_PLAN D5. Conditional on the active engine (D6).
Links: [[F22|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H23 — OPEN: Exit-logic experiments (trailing / partial / vol-scaled hold)
F17/F19 found the EXIT is the dominant lever; concrete untried variants: trailing stops, partial profit-taking, vol-scaled hold time vs the fixed 8-10 bar time-exit. The natural successor to the exit findings. Conditional on the active engine (D6).
Links: [[F17|builds_on]] · [[F19|builds_on]] · [[D5|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H24 — OPEN: Re-validate SOXL/LABU/TNA in realistic mode before any live use (tight stops may collapse like GDXU)
The three 2026-03-22 leveraged modes were optimistic-mode swept; their tight stops (LABU 0.25%, TNA 0.15%) risk being inside the spread like GDXU (Sharpe 96.5->1.8 realistic). They are also the holdout-biased experiments.jsonl winners F2 flags. Re-run fixed-10% realistic and pick by realistic EV.
Links: [[F2|relates]] · [[D6|relates]] · [[D3|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H25 — OPEN: GDXU realistic re-sweep (optimistic 0.075% stop is inside the spread)
GDXU's optimistic Sharpe 96.5 collapsed to 1.8 / WR 27.5% realistic because the 0.075% stop is inside the bid-ask spread — not production-ready, placeholder config. Action: python sweep.py GDXU in realistic mode.
Links: [[F2|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H26 — OPEN: Shadow evaluator — replay bars and log what a candidate config would have traded
A non-trading process that replays bars and logs what a candidate config would have done to a separate table, answering 'would a different model have traded here?' without risking live. Infrastructure that would de-risk all active-engine experiments.
Links: [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H27 — OPEN bug: use_regime_filter runs at default True despite config.USE_REGIME_FILTER=False
Distinct from the dead slope gate (F26): the vol_regime Bollinger-width filter runs at its default True in backtests despite config being False — a real, non-inert bug silently changing backtest behavior. Needs the runner.py call-site fixed to honor the config flag.
Links: [[F26|relates]].
_— captured development@bebe6c5, 2026-06-26_

### D8 — OPEN: Honest fallback (D7) — accept a capital-preservation vehicle if nothing clears 0.5%/mo net OOS
If no configuration clears ~0.5%/mo net on confirmed fills out-of-sample, accept the strategy as a low-return / near-zero-drawdown capital-preservation vehicle (or re-derive the signal) — a win, not a failure. The forward-looking sibling of D6's static-allocation verdict.
Links: [[D6|builds_on]] · [[D4|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H28 — OPEN: A2 fill_source provenance column (actual/inferred/estimated) — highest-value data change
Without a fill_source provenance column on trades/exports, live PnL is uninterpretable — synthetic/estimated fills silently inflate the headline (the ~24x ALL-vs-CONFIRMED gap). Add an additive column set in trader.py at each close path. Live path: do with the trader stopped.
Links: [[F13|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H29 — OPEN: A1/A4 Phase-0 evidence gate — clean-run protocol + fixed-10% realistic re-sweep
ops/analyze_run.py renders a clean-run rubric + honest confirmed-fill edge (mostly done); next: run daily, accumulate a week, codify a 'ready for real money' checklist, then a fixed-10% realistic re-sweep (sweep.py TQQQ --sizing fixed --fixed-pct 0.10). The evidence gate that blocks everything; needs the trader stopped.
Links: [[D6|relates]] · [[H4|relates]].
_— captured development@bebe6c5, 2026-06-26_

### F28 — The backtest is structurally disconnected from live (sweep optimized a sizing model the live trader doesn't use)
Backtest optima don't transfer: the sweep optimized an adaptive-Kelly sizing model the live trader (fixed-10%) doesn't use, and execution differs. Motivates workstream C (sizing C1 shipped, fill-model C2 partial, fees C3 shipped, objective C4 partial, walk-forward-primary C5 open).
Links: [[F2|relates]] · [[H4|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H30 — OPEN: Data hardening (workstream F) — yfinance 429 rate-limits + unvalidated data silently corrupt signals
yfinance is rate-limited (429s) and bad data silently corrupts signals. Partly shipped (retry/backoff, cache fallback, OHLC validation); open: extended OHLC/bar-continuity/DST/730d-clamp checks, 429 mitigation via parquet cache + shared fetch + backup source, a data-quality table, and a point-in-time fetch/feature boundary.
Links: [[F13|relates]].
_— captured development@bebe6c5, 2026-06-26_

### F29 — Walk-forward Sharpe annualization bug (sqrt(252) on hourly) — FIXED, recorded so it isn't re-derived
walk_forward.py annualized hourly returns by sqrt(252), inflating Sharpe ~2.5x and selecting params that underperformed live. Fixed 2026-06-18 (IMPROVEMENT_PLAN B1). Recorded as a methodology finding; residual: the cross-surface Sharpe-consistency check (H3).
Links: [[F2|relates]] · [[H4|relates]].
_— captured development@bebe6c5, 2026-06-26_

### E17 — DEAD-END: Bear shorts (Phase A) — 0% WR in 2022
LONGS_ONLY=False bear shorts had 0% WR in 2022 even at a 2.5% stop; crypto's 4-7% daily range hit stops on noise and the 252-MA lag fired shorts into a +40% recovery. Lesson: don't fight bears with daily-bar shorts; bear alpha = capital preservation. Reverted.
Links: [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### E18 — DEAD-END: Bull breakout signal (Phase B) — momentum trap at ATH
STRONG_BULL breakout entries (price>20d-high + ADX>25 + MACD bull) dropped WR 49.4%->39.6%, firing relentlessly near ATH (RSI 70-80). Lesson: breakout signals are traps at tops; the core is mean-reversion. BULL_BREAKOUT_ENABLED=False.
Links: [[F16|relates]].
_— captured development@bebe6c5, 2026-06-26_

### E19 — DEAD-END: four reverted tuning attempts (strict 50-MA gate / 5% target / RSI 38-42 extras / opposing-signal exit)
Strict 50-MA gate filtered 71/83 trades; 5% STRONG_BULL target dropped WR 49.4%->33.7%; RSI 38-42 extra entries dropped WR 68.8%->57.9%; opposing-signal exit hurt TQQQ (every overbought threshold scored negative). Consolidated 'tried & abandoned' ledger.
Links: [[F17|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H31 — OPEN: External alerting for CRITICAL events (G1) — gates real money
CRITICAL events (force-finalize, software-stop, desync block, N consecutive signal failures) land in SQLite but page nobody — on a Pi the operator learns at the next dashboard open. Wire a Slack/ntfy/email webhook. Decision gate 2 for real money.
Links: [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H32 — OPEN: Hard live risk limits + circuit breakers + drawdown sizing + kill switch (J1-J4) — gates real money
Few explicit live risk controls despite near-zero modeled drawdown. Add per-day loss limit / max-consecutive-losses pause / max notional (J1), vol-spike & data-degradation & bracket-failure circuit breakers (J2), an equity-drawdown throttle (J3), and a documented kill switch (J4). Signal-independent; decision gate 2.
Links: [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H33 — OPEN: Root-cause IBKR paper bracket non-fills (E1) — determines funded-account viability
domain: live_ops
IBKR paper brackets fill unreliably; the software net masks it but provenance/recovery have gaps. Use tools/diagnose_brackets.py during open positions + TWS/IBC logs to determine if it's submission/OCA/tif/paper-engine. Determines funded-account viability; gates order-type experiments and decision gate 2.
Links: [[F6|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H34 — OPEN: Reporting consistency (H1-H3) — dashboard vs alert PnL mismatch + fill-quality + annualization
Dashboard (compounded, 62 PROD trades) != alert path (simple-sum, 65 all trades). Extract one shared src/analysis/performance.py; pick compounded + one trade population; label estimated trades; carry a fill-quality note in every view; use trade-frequency Sharpe everywhere.
Links: [[F13|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### H35 — OPEN: Config consolidation + dead params + 3-way mode-routing sync + ModeConfig migration (I2)
~165 params with ~12-15 dead ones; the 3-way mode routing (MODE_MAP / _MODE_TO_ASSET / ASSETS) has no sync check; the ModeConfig dataclass is defined but get_mode_config() is never called; 18 scattered BACKTEST_* date params; adding an instrument touches 4 sites. Consolidate + validate.
Links: [[F23|relates]].
_— captured development@bebe6c5, 2026-06-26_

### D9 — OPEN: Branch hygiene (I1) — main still ships the desync & bracket bugs
Two correctness fixes (reconciliation desync guard, software take-profit) live only on feature branches; cherry-picked clean onto land-* branches but PRs aren't opened, so main STILL ships the desync & bracket bugs. Open PRs, define merge order, land fixes on main.
Links: [[F6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### F30 — Test coverage is inverted — the param-selection layer that produced the misleading numbers is F-grade
Execution mechanics are A-grade but the param-selection layer is F-grade — bugs hide where there are no tests. Workstream B (B1-B9) largely shipped (walk-forward, runner metrics, golden-master, sweep scoring, fetcher, broker mock, trader flow, coverage floor, property tests), surfacing the walk_forward._run_slice crash. Residual: keep the floor, fill remaining live/ gaps.
Links: [[F2|relates]] · [[H4|relates]].
_— captured development@bebe6c5, 2026-06-26_

### F31 — MONAD's goal is a high-yield bond-ETF alternative, not growth (long-only; bear alpha = not losing)
Foundational framing: an actively-traded long-only income engine targeting consistent monthly income with near-zero drawdown; the benchmark is a 4-6% bond ETF, not BTC buy-and-hold. Hard constraints: no ML, no inverse ETFs/derivatives, every feature config-toggleable default-False, .shift(1) no look-ahead. Why D6's static-allocation verdict is an acceptable outcome.
Links: [[D6|relates]] · [[D4|relates]].
_— captured development@bebe6c5, 2026-06-26_

### F32 — Root cause of the invalidated headlines: optimistic-vs-realistic backtest mode
Optimistic mode resolves a both-TP-and-SL bar in the trade's favor; realistic mode assumes the stop hit. Realistic mode collapsed ultra-tight-stop configs and forced full re-sweeps. Decision: all production configs use realistic mode. The mechanism behind the stale-performance warning.
Links: [[F2|relates]] · [[F13|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### F33 — The bottleneck is trustworthy evidence + a real edge, NOT features (gate feature work on a demonstrated edge)
Infra is solid (correctness fixes, autostart, 180+ tests, runnable backtest) but evidence is not (no clean live week, no fill-provenance until A2, an under-tested param-selection layer). Decision: gate all feature work on a demonstrated edge; don't polish an unproven one. The ordering thesis behind every IMPROVEMENT_PLAN workstream.
Links: [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### E20 — DONE: mr_daily_lab adversarial-panel hardening of Exp#1/#7 before the D6 closure
Exp#1/#7 (the RSI-conditioning and 26yr go/no-go experiments, E13/E14) were hardened by an adversarial verification panel before D6's closure was recorded (commit c9a20a8) — recording the verification rigor that strengthened the no-edge verdict.
Links: [[E13|relates]] · [[E14|relates]] · [[D6|relates]].
_— captured development@bebe6c5, 2026-06-26_

### E21 — DONE: [ctx] DP-13 — ctx uncaptured nudge (shipped)
Lists strategy/research commits landed since RESEARCH_WEB.md last moved + the note.py command to capture them; wired a one-line nudge into ctx brief so every cold-start surfaces the gap. Closes the write-back compliance gap so the idea web stays complete (and this very capture was prompted by dogfooding it). Commit 4d8b25d.
Links: [[F27|relates]].
_— captured development@4d8b25d, 2026-06-26_

### H36 — OPEN [ctx]: DP-11 — computed-graph cache (no caching today)
_manifest re-reads context_map.json, _parse_web re-reads RESEARCH_WEB.md, and impact/graph/health/frontier re-walk the AST every call (~0.5s for a full graph build). Open: an mtime/git-sha-invalidated cache or a ctx graph --json sidecar that can NEVER serve stale epistemic data. Low priority — correctness first; current cost is modest.
Links: [[F27|relates]].
_— captured development@4d8b25d, 2026-06-26_

### H37 — OPEN [ctx]: DP-12 — audit + harden _classify_edge prose-cue inference
Untyped [[ID]] links are typed by a nearest-verb heuristic; a misclassification can flip a reliance edge into an exempt one (or vice-versa), silently changing lint. Open: dump every untyped link with its inferred type, quantify false-pos/neg on the stale-cite boundary, and consider requiring explicit [[ID|type]] for links into superseded/contradicted nodes.
Links: [[F27|relates]].
_— captured development@4d8b25d, 2026-06-26_

### H38 — OPEN [ctx]: DP-14 — extend ctx route synonyms + stress-test vocabulary coverage
ctx route keys off ~11 hand-built routing_synonyms; paraphrases/jargon outside them silently fall back to reading whole docs (the failure the layer exists to prevent). Open: generate realistic task phrasings, measure the miss rate, add synonyms (in context_map.json — now self-fenced, so use the escape hatch).
Links: [[F27|relates]].
_— captured development@4d8b25d, 2026-06-26_

### H39 — OPEN [ctx]: DP-15 — generate the doc-ownership tables from context_map.json context_docs
The 'why vs how' topology is hand-restated in 4+ prose docs (AGENT_INDEX/OPERATIONS/AGENTS/AGENT_CONTEXT_PLAN) plus machine-readably in context_docs; only the manifest is CI-bound, so the prose drifts. Open: generate the prose from context_docs (a ctx topology view) or add a CI test that each prose table matches context_docs.
Links: [[F27|relates]].
_— captured development@4d8b25d, 2026-06-26_

### E22 — DONE: [ctx] SessionStart hook auto-orients new chats via the context map
Closes the authority-by-convention root risk — the whole layer only worked if an agent chose to run ctx. ops/session_orient.py is a SessionStart hook (.claude/settings.json) that injects ctx brief + a 'navigate via ctx route, do not bulk-read' directive as additionalContext into every new chat, fail-safe (still injects the directive if ctx cannot run; never blocks a session). So a fresh session is oriented (honest-state, safety, command surface, open-ends) without relying on discipline. Commit c3fcb89. domain: context-web.
Links: [[F27|relates]].
_— captured development@c3fcb89, 2026-06-27_

### E23 — DONE: [ctx] ctx serve — the context map as a live read-only web app
ctx serve [--host --port] runs a stdlib http.server serving the interactive force-graph at / (rebuilt each load, always fresh) — a new chat or the user can SEE the context map in a browser, not just dump HTML. Reuses the ctx graph --html renderer (_render_graph_html). Fence-clean: lives in the ctx CLI per F27 (the context tool serves the context map), not bolted onto the fenced trading dashboard. Running on the Pi at http://100.76.6.75:8787/ over Tailscale. Commit b4490a6. domain: context-web.
Links: [[F27|relates]].
_— captured development@b4490a6, 2026-06-27_

### H40 — OPEN [ctx]: embed the context map in the trading dashboard (fenced live/dashboard.py)
ctx serve gives a standalone context-map web app (port 8787); a tighter integration would add a /context route+page to live/dashboard.py (port 8000) so the map appears alongside the trading monitor. live/ is edit-fenced, so this needs the trader stopped + explicit approval + the escape hatch. Cheaper alternative: just iframe/link to ctx serve from the dashboard. domain: context-web.
Links: [[F27|relates]].
_— captured development@b4490a6, 2026-06-27_

### E24 — DONE: uncertainty bands are now first-class in the backtest report (CI on every headline)
Built src/backtest/uncertainty.py (+23 unit tests) and wired it into run_backtest: every result now prints a 95% band beside each headline number — block-bootstrap CI on Sharpe and total-return (block resample PRESERVES autocorrelation, which is the mean-reversion signal under test), a Beta-Binomial win-rate posterior (so WR over 16 trades reports a far wider band than over 500), and a Monte-Carlo equity path band on final-equity/max-drawdown plus P(end below start). Bands bootstrap the SAME sized per-trade equity returns the headline Sharpe uses, so each band's point estimate equals the printed number. This promotes the robust-SE / bootstrap machinery that previously lived ONLY in tools/mr_daily_lab.py ([[F18]], [[E14]]) into the production reporting path, making the [[D6]] no-edge reality visible per-run: e.g. a realistic BTC run printed Sharpe 1.197 with CI [0.06, 3.22] — barely clears zero, i.e. indistinguishable from no edge. Same instinct as [[F2]]/[[E4]]: stop trusting best-of-many point estimates. Commits f073d89, 200d93e.
Links: [[F18|relates]] · [[E14|relates]] · [[D6|relates]] · [[F2|relates]] · [[E4|relates]].
_— captured development@200d93e, 2026-06-27_

### E25 — power & equivalence study: is D6 'no edge' evidence-of-absence or underpowered?
tools/power_study.py (seed=0, deterministic; writeup docs/research/D6_power_equivalence_study.md). Reuses mr_daily_lab's canonical leak-free dip+5d sleeve (200d gate, 5bps cost) and adds three tools the go/no-go harness never ran: (1) a PAIRED block bootstrap (block=20, B=5000, SAME block starts both legs) of the clean quantity dSharpe = Sharpe(active) minus Sharpe(bench), fixing the SPREAD-Sharpe confound mr_daily_lab itself flags; (2) MDE@80% + two-sided power curves + resolution-horizon; (3) TOST equivalence (90%-CI within +/-D). THREE windows: 12.5yr standard basket, 26.5yr long-history, and the DISJOINT 2000-2013 slice as genuine independent corroboration (dSharpe +0.10, CI straddles 0). Adversarially verified by a 5-lens skeptic panel (blocking=false): every power number reproduces from the SE; SE seed-stable to ~3%. Builds on [[E14]]; uses [[F18]] robust SE; the finding it produces is the next F-node.
Links: [[E14|builds_on]] · [[F18|relates]] · [[F22|relates]] · [[D6|relates]].
_— captured development@e4934a9, 2026-06-27_

### F34 — D6 is mostly EVIDENCE-OF-ABSENCE: no active edge over static down to ~0.3 Sharpe; only a small UNDETECTABLE (not irrelevant) residual remains
[[E25|evidenced_by]]: the paired dSharpe(active minus static) bootstrap straddles 0 in all three windows (-0.10 / +0.00 / +0.10 incl. the disjoint 2000-2013 slice). TOST positively rules out any edge > ~0.42 Sharpe across both main windows and > ~0.25 over the full 26.5yr (narrow pass at +/-0.30) => genuine evidence-of-absence for LARGE edges; the 'underpowered' objection is retired except in the small-edge regime (MDE ~0.42; a <=0.2-Sharpe edge needs ~90-114yr to resolve). The lag-1 MR signal is provably real ([[F18]] robust |t|>=2.5 over 26.5yr) but provably NOT tradeable-better-than-static - confirms [[D6]]/[[F22]]/[[F25]]. CORRECTION to the study's first-draft gloss: the un-excludable <=0.2-Sharpe residual is ~<=2%/yr at ~10% vol - UNDETECTABLE, not 'economically irrelevant' for a 4-6%/yr mandate. Baseline tested (50/50 = buy&hold) is the EASIER bar; recommended 60/40 beats active on Sharpe AND return, so the static recommendation STANDS. DD edge path-dependent (paired maxDD-gap CI straddles 0).
Links: [[E25|evidenced_by]] · [[D6|refines]] · [[F22|supports]] · [[F25|supports]] · [[F18|relates]] · [[F16|relates]].
_— captured development@e4934a9, 2026-06-27_

### E26 — study #2: active daily-MR power/equivalence vs the DECISION-RELEVANT static 60/40 equity/bond
tools/power_study_6040.py + docs/research/D6_active_vs_6040_study.md. Re-runs the [[E25]] power/equivalence machinery (paired dSharpe block bootstrap, MDE, TOST) against the DECISION-RELEVANT static 60/40 equity/bond (IEF) - a HARDER bar than E25's 50/50 (60/40 Sharpe ~0.84 > buy&hold ~0.80 via the negative equity-bond corr). Windows restricted to IEF's real life (2014-2026, 2002-2026, sliced to IEF inception so the bond leg is never silently cash). Active leg byte-identical to E25; the 60/40 leg byte-identical to mr_daily_lab gonogo's static-60/40 row (Sharpe 0.84 cross-check exact). 3-lens skeptic panel: blocking=false, fully reproducible; ^GSPC price-only + log-return convention disclosed (both conservative against active). Builds on [[E25]]; tests the [[D6]]/[[F25]] recommended baseline.
Links: [[E25|builds_on]] · [[D6|relates]] · [[F25|relates]] · [[F22|relates]].
_— captured development@d6b9bb6, 2026-06-27_

### F35 — Active does NOT beat the recommended static 60/40: lower point Sharpe (-0.17/-0.26, CIs straddle 0); no-edge verdict hardens vs the decision-relevant bar
[[E26|evidenced_by]]: against the recommended static 60/40 (not E25's easier 50/50), active daily-MR has a LOWER point Sharpe in both windows - dSharpe -0.17 (12.5yr) / -0.26 (24yr) - but both 95% CIs straddle 0, so the loss is WITHIN noise (over 24yr the 90% upper bound is +0.001, i.e. on the one-sided-significance boundary, p~0.051). Point ann return also lower (6.1/4.6% vs 7.8/7.9%, no CI). The only candidate edge - shallower drawdown (maxDD -14/-20% vs -21/-33%) - is PATH-DEPENDENT (paired maxDD-gap CI straddles 0). Net: the [[F34]] 'no edge vs static' verdict HARDENS at the point-estimate level against the harder bar (~0 vs 50/50 => clearly negative vs 60/40) while CIs still straddle 0 - 'no edge, leaning negative', not 'significantly worse'. Static 60/40 stays the recommended bond-alternative; active is at best a regime-dependent low-DD overlay. Confirms [[D6]]/[[F25]].
Links: [[E26|evidenced_by]] · [[F34|builds_on]] · [[D6|supports]] · [[F25|supports]].
_— captured development@d6b9bb6, 2026-06-27_

### E27 — study #3: is the active engine's low-drawdown edge CONCENTRATED in crises (not just path-dependent full-sample)?
tools/crisis_overlay_study.py + docs/research/D6_crisis_overlay_study.md. Tests whether the active engine's low-drawdown edge is CONCENTRATED in crises (studies #1/#2 only measured it full-sample, where it is path-dependent — the wrong resolution for a regime-dependent claim). Reuses the [[E25]] bootstrap primitives + canonical sleeve. Method: crisis episodes = equity buy&hold peak-to-trough drawdowns >=15% (principled; 8 over 2000-2026: dotcom/GFC/2011/2015/2018/COVID/2022/2024), per-episode decline-phase return vs active/60-40/50-50/buy&hold, episode SIGN test + pooled crisis-day paired block bootstrap + a min-depth sensitivity sweep + a crisis/calm decomposition. 3-lens skeptic panel (blocking=false): detection/leak/identities sound and reproduce byte-identically; the vs-60/40 result is threshold- and method-dependent (disclosed). Builds on [[E26]]/[[F35]]; tests the [[D6]]/[[F25]] capital-preservation-overlay claim.
Links: [[E26|builds_on]] · [[E25|builds_on]] · [[D6|relates]] · [[F25|relates]] · [[F35|relates]].
_— captured development@c219a91, 2026-06-27_

### F36 — Active's low-DD overlay is CRISIS-CONCENTRATED: reliable vs buy&hold (8/8), borderline/not-bankable vs 60/40 (~5 deep events); paid for by calm under-participation -> Sharpe ~ static
[[E27|evidenced_by]]: the active engine's low-drawdown overlay is REAL and CRISIS-CONCENTRATED but, vs the recommended 60/40, NOT BANKABLE on the available evidence. It out-protects naked buy&hold reliably (8/8, p=0.008, crisis-day CI [+15,+52]%/yr, robust to every perturbation). Vs 60/40 it wins 5/7 crisis declines - ALL deeper than ~20%, losing only the 2 shallowest (2011/2015) where the 200d gate never cleanly engages; the crisis-day diff is +13.5%/yr, 95% CI [-0.6,+26.3] (one-sided ~p0.03, 90% CI all-positive), turning strictly significant at a >=20% deep-crisis cut - but resting on only ~5 independent deep events (sign p=0.45) and partly on a boundary-crossing bootstrap. It is PAID FOR by calm-market under-participation (lags both benches significantly) -> a lower-return/lower-risk profile whose Sharpe lands ~ static. A genuine capital-preservation overlay, NOT a Sharpe edge over 60/40 ([[F35]]). Confirms [[D6]]/[[F25]] + studies #1/#2: the active engine's last claim survives only as a depth-concentrated, small-N drawdown property.
Links: [[E27|evidenced_by]] · [[F35|builds_on]] · [[D6|supports]] · [[F25|supports]] · [[F34|relates]].
_— captured development@c219a91, 2026-06-27_

### E28 — study #4 (constructive capstone): does an active OVERLAY (constant-weight or regime-conditional) improve a static 60/40 CORE?
tools/overlay_build_study.py + docs/research/D6_overlay_build_study.md. Constructive capstone: instead of active-vs-static, tests whether a 60/40 CORE + an active OVERLAY beats the pure 60/40 core. Reuses [[E25]] primitives + the canonical sleeve. Tests TWO build families: (1) constant-weight blend(w)=(1-w)core+w*active swept 0-100%; (2) a REGIME-CONDITIONAL overlay (regime_blend: 100% active only while the core is >thr underwater, lag-1 leak-free) - the build [[F36]]'s depth result motivates. Paired block bootstrap of blend-core for dSharpe/dCalmar/dMaxDD at a pre-specified weight + the in-sample optimum. Two windows (2014-2026, 2002-2026). Core 60/40 Sharpe 0.84 byte-identical to mr_daily_lab gonogo. 3-lens skeptic panel (blocking=false, reproduces byte-identically). Builds on [[E27]]/[[F36]]; tests the [[D6]]/[[F25]] recommended product.
Links: [[E27|builds_on]] · [[E26|builds_on]] · [[D6|relates]] · [[F25|relates]] · [[F36|relates]].
_— captured development@647fdaa, 2026-06-27_

### F37 — No build (constant-weight OR regime-conditional active overlay) reliably improves the static 60/40: the active engine is a capital-preservation overlay, never a risk-adjusted edge — closes the arc
[[E28|evidenced_by]]: NO build of the active engine reliably improves the recommended static 60/40 - tested both a CONSTANT-WEIGHT overlay (Sharpe-optimal active weight ~0%; at a pre-specified 20% dSharpe +0.01/-0.01, dCalmar/dMaxDD CIs all straddle 0) AND a REGIME-CONDITIONAL overlay (100% active only while the core is >10% underwater: lifts in-sample Sharpe 0.84->0.89 / 0.70->0.75 and cuts maxDD -21->-17 / -33->-23, but deploys only 11-12% of days so dSharpe +0.04/+0.05 CIs still straddle 0 - the [[F36]] small-N deep-crisis wall). The drawdown smoothing is a directional tilt (blend shallower in 87-88% of resamples) but path-driven and not significant, and costs total return. Closes the active-vs-static arc ([[D6]]/[[F25]], [[F34]]/[[F35]]/[[F36]]): the active engine is a discretionary capital-preservation overlay, NEVER a demonstrable risk-adjusted edge. The pure static 60/40 stands.
Links: [[E28|evidenced_by]] · [[F36|builds_on]] · [[F35|builds_on]] · [[D6|supports]] · [[F25|supports]] · [[F34|relates]].
_— captured development@647fdaa, 2026-06-27_

### E29 — study #5 (constructive pivot): characterize & try to improve the recommended static 60/40 product
tools/static_product_study.py + docs/research/D6_static_product_study.md. Constructive PIVOT: now that the active engine is closed (E25-E28), characterize & try to IMPROVE the recommended static 60/40 itself. Simple-return product accounting (constant-weight daily-rebal = weight-avg of simple returns, exact); reuses the 2000+2014 price caches (no new fetch). Three analyses: (1) HONEST CEILING - isolate the dividend effect (add the ^GSPC dividend back to the SAME 4-asset basket) vs a composition variant; (2) REBALANCING realism - daily/M/Q/Y/5%-band/no-rebal with turnover cost; (3) THIRD SLEEVE - +10% GLD/TLT/HYG paired block bootstrap vs 60/40. 3-lens skeptic panel (blocking=false, byte-reproducible; the rebalancing simulator was independently re-implemented bit-exact). Builds on [[E28]]/[[F37]]; tests the [[D6]]/[[F25]] recommended product.
Links: [[E28|builds_on]] · [[D6|relates]] · [[F25|relates]] · [[F37|relates]].
_— captured development@93796ae, 2026-06-27_

### F38 — Honest static 60/40 is ~Sharpe 0.85 (dividends add only +0.03), rebalance-robust, no reliable single-sleeve improver (gold best-of-3 fails Bonferroni); CAGR rides a bond bull
[[E29|evidenced_by]]: the recommended static 60/40 is honestly ~Sharpe 0.85 (dividend-correct) - fixing the studies #2-4 ^GSPC price-only leg lifts it only +0.03 Sharpe / +0.3%/yr, so the active engine's deficit ([[F37]]) was never a price-only artifact. It is ROBUST to the rebalance schedule (all rules within <0.05 Sharpe; the slight annual>daily ordering is a regime-specific DRIFT effect, not a cost saving - don't read it as 'rebalance less often'). NO single third sleeve reliably improves it: gold is the best of three (corr to core just +0.14, drawdown shallower in 94% of resamples) but its Sharpe-diff CI lower bound is ~0 even UNADJUSTED and it FAILS a best-of-3 Bonferroni correction; long-bond (TLT) and credit (HYG) don't help at all. Caveat: the ~9.4% CAGR rides a QQQ growth tilt + a 2002-2026 secular bond bull (IEF 3.6%/yr, Sharpe 0.55 standalone) that won't repeat - a backward-looking realized ceiling, not a forward expectation. The product is a strong, hard-to-beat-reliably static baseline; a small gold sleeve is the one OOS hypothesis. Closes the [[D6]] arc on the PRODUCT side; confirms [[F25]]/[[F37]].
Links: [[E29|evidenced_by]] · [[F37|builds_on]] · [[D6|supports]] · [[F25|supports]] · [[F35|relates]].
_— captured development@93796ae, 2026-06-27_

### E30 — study #6: out-of-sample (2004-2013 holdout) test of study #5's 10% gold sleeve
tools/gold_oos_study.py + docs/research/D6_gold_oos_study.md. The decisive OOS test of study #5's one live hypothesis (the +10% gold sleeve). GLD launched 2004-11, so 2004-2013 is a genuine disjoint HOLDOUT that [[F38]]'s 2014-2026 test never touched. Runs the SAME sleeve + paired bootstrap on three windows: OOS holdout (2004-2013), in-sample (2014-2026, reproduces #5 to rounding), full (2004-2026, 21.6yr). Reuses static_product_study's thrice-verified primitives; 2-lens skeptic panel (blocking=false; windows disjoint + leak-free byte-identical, study-#5 cross-check passes). Pre-registered rule: gold confirms only if the holdout AND full both clear 0. Builds on [[E29]]; resolves the gold hypothesis from [[F38]]; tests the [[D6]]/[[F25]] product.
Links: [[E29|builds_on]] · [[F38|relates]] · [[F37|relates]] · [[D6|relates]] · [[F25|relates]].
_— captured development@863c753, 2026-06-27_

### F39 — Study #5's gold signal does NOT survive a clean OOS test (2004-2013 holdout straddles 0, though underpowered); direction robust but unconfirmed - 60/40 stands
[[E30|evidenced_by]]: by the PRE-REGISTERED rule (clear 0 in the disjoint 2004-2013 holdout AND the full window), the +10% gold sleeve does NOT confirm - the clean holdout straddles 0 on Sharpe-diff/Calmar-diff/maxDD-diff. Two honest qualifiers: (1) the 9.1yr holdout is UNDERPOWERED (min detectable Sharpe-diff ~+0.17 at 80% power vs the +0.08 lift; even a doubled 30% gold weight still straddles 0) - so it's 'unconfirmed', NOT refuted; (2) the drawdown DIRECTION is robust (88-94% shallower across all 3 windows) and the full-21.6yr Sharpe-diff just clears 0 [+0.01,+0.15], but that window CONTAINS the in-sample period (not independent), and part of the lift is gold's own 2004-2011 bull. Net: gold is a DEFENSIBLE DISCRETIONARY DIVERSIFIER, NOT a statistically-confirmed upgrade - the pure static 60/40 stands. Resolves the [[F38]] gold hypothesis; confirms [[F37]]/[[D6]]/[[F25]].
Links: [[E30|evidenced_by]] · [[F38|resolves]] · [[F37|supports]] · [[D6|supports]] · [[F25|supports]].
_— captured development@863c753, 2026-06-27_

### E31 — study #7: vol-targeting / risk parity vs the fixed 60/40 (the structural levers)
tools/vol_target_study.py + docs/research/D6_voltarget_riskparity_study.md. Tests the two classic STRUCTURAL levers left after studies #4-6: vol-targeting (scale exposure to a constant risk budget via LAGGED realized vol) and risk parity (inverse-vol equity/bond). Key construct: rescale the vol-timed series by a CONSTANT to match the fixed 60/40's full-sample vol, isolating TIMING from leverage (leverage is Sharpe-invariant). Reuses static_product_study's thrice-verified primitives; 2-lens skeptic panel (blocking=false; leak-free + byte-reproducible). Two windows (2002-2026, 2014-2026). Builds on [[F37]]; tests the [[D6]]/[[F25]] product; continues the static-product arc ([[F38]]/[[F39]]).
Links: [[F37|builds_on]] · [[D6|relates]] · [[F25|relates]] · [[F38|relates]].
_— captured development@093c9d5, 2026-06-27_

### F40 — Neither vol-targeting nor risk parity reliably beats the fixed 60/40: vol-timing is an unreliable directional tilt (leverage is Sharpe-invariant), risk parity is a bond-bull regime bet that reverses OOS
[[E31|evidenced_by]]: neither STRUCTURAL lever reliably beats the fixed 60/40. VOL-TARGETING: with leverage stripped out (vol-matched), the residual vol-TIMING Sharpe-diff AND maxDD-diff both straddle 0 - a directional tilt, not reliable. Leverage is Sharpe-INVARIANT (the vol-matched and @10% forms have the IDENTICAL 0.90 Sharpe), so the +0.06 lift is timing, not leverage; a realistic financing cost pushes the levered form BELOW fixed (Sharpe 0.86 at 2%/yr, 0.82 at 4%/yr). RISK PARITY: its 1.04 Sharpe (28/72 bond-heavy) is a secular BOND-BULL regime bet - Sharpe-diff straddles 0 even in its best window and the edge REVERSES out-of-sample (2014-2026 Sharpe 0.79 < fixed 0.87); its maxDD-diff clears 0 only as a low-vol artifact. Every lever in this program is a path-smoothing directional tilt (CIs straddle 0), not a free/reliable upgrade - the fixed 60/40 stands. Confirms [[F37]]/[[D6]]/[[F25]].
Links: [[E31|evidenced_by]] · [[F37|supports]] · [[F38|supports]] · [[D6|supports]] · [[F25|supports]].
_— captured development@093c9d5, 2026-06-27_

### E32 — study #8: forward-looking 60/40 expectation (scenario matrix + mean-re-centered Monte-Carlo) vs the 3.75% income goal
tools/forward_expectation_study.py + docs/research/D6_forward_expectation_study.md. Closes the [[D6]] arc on the GOAL side: the static 60/40 is the recommended product, but its ~9.5% history rode a bond bull + QQQ tilt + a benign -0.29 stock-bond correlation that won't repeat. A forward SCENARIO study (assumptions, not data): bond fwd ~= entry yield ~4.2%, equity fwd 5-9% nominal; a scenario matrix + a Monte-Carlo that keeps the historical 60/40 RISK shape but re-centers the mean to the forward expectation. 2-lens skeptic panel (blocking=false, byte-reproducible; confirmed the MC re-centering is valid and conservative on central tendency). Builds on [[D6]]/[[F25]]/[[F37]]/[[F38]]; answers [[D4]] (is the ~3.75% APY goal achievable).
Links: [[D6|builds_on]] · [[F25|builds_on]] · [[F37|builds_on]] · [[F38|builds_on]] · [[D4|relates]].
_— captured development@6b23768, 2026-06-27_

### F41 — Forward 60/40 ~5-6% (forward Sharpe ~0.5) more-likely-than-not clears the 3.75% income goal (P~67%) but FAILS near-zero-drawdown; the near-zero-DD aspiration is unattainable - resolves D4
[[E32|evidenced_by]]: at 2026 yields the forward static 60/40 should return ~5.9%/yr (base; ~4.4-7.4% across scenarios) at a forward SHARPE of only ~0.51 (vs 0.84 historical, flattered by the bond bull). It MORE-LIKELY-THAN-NOT clears the ~3.75% APY income goal ([[D4]]) - base-case P(10yr CAGR>=3.75%)=67% (~1-in-3 miss; ~51% coin-flip in the pessimistic corner; goal read as total-return CAGR, not sustainable cash income ~1.5-2%). But it FAILS the 'near-zero drawdown' aspiration: median worst DD ~23%, 65% chance of a >20% DD - EQUITY-LIKE tail risk (basket-robust: a broad ^GSPC 60/40 is comparable-to-deeper). That DD is the OPTIMISTIC end - the MC inherits the benign -0.29 historical stock-bond correlation, which flipped positive (+0.12) in 2022; a bonds-don't-hedge regime deepens it. The achievable product is a real bond-alternative on RETURN (not a sure one, not near-zero-DD); the near-zero-DD aspiration is unattainable by any honest static OR active build ([[F37]]/[[E27]]). Resolves [[D4]]; confirms [[D6]]/[[F25]].
Links: [[E32|evidenced_by]] · [[D4|resolves]] · [[D6|supports]] · [[F37|supports]] · [[F38|builds_on]] · [[F25|supports]].
_— captured development@6b23768, 2026-06-27_

### E33 — study #9: goal-optimal static equity/bond mix (weight sweep + per-mix forward Monte-Carlo) vs the 3.75% goal
tools/weight_optimization_study.py + docs/research/D6_weight_optimization_study.md. The product-recommendation refinement: the whole arc ASSUMED 60/40, but study #8 ([[F41]]) showed forward equity is high-vol/modest-return while bonds yield decently at low vol. Sweeps the equity weight 0-100% and runs study #8's verified forward MC per mix (re-center to w*7%+(1-w)*4.2%), reporting the goal-odds-vs-drawdown frontier + an equity-vol sensitivity (20/18/15%) + the asymmetric upside give-up. 2-lens skeptic panel (blocking=false, byte-reproducible; forced DOMINATED->weakly, the equity-vol sensitivity, and the right-tail give-up disclosure). Refines [[F41]]; answers [[D4]]; builds on [[D6]]/[[F25]].
Links: [[F41|refines]] · [[D4|relates]] · [[D6|builds_on]] · [[F25|builds_on]].
_— captured development@00be0c5, 2026-06-28_

### F42 — For the ~3.75% income goal a more conservative ~30-40% equity mix weakly dominates 60/40 (forward bonds out-Sharpe equity); direction robust but no mix clears the goal reliably - refines D4/F41
[[E33|evidenced_by]]: for the project's actual goal (clear ~3.75% APY with the shallowest drawdown), 60/40 is somewhat equity-heavy - a more conservative ~30-40% equity / 60-70% bond mix WEAKLY dominates it at the realized ~20% equity vol: higher goal-odds (70% vs 67%), higher forward Sharpe (0.68 vs 0.51), shallower median drawdown (-15% vs -23%), better downside floor, for only ~0.3%/yr less median return. WHY: forward bonds out-Sharpe forward equity (~0.6 vs ~0.35 at 2026 yields), so equity beyond ~40% mostly buys drawdown + right-tail upside the LOW goal doesn't need. The DIRECTION (tilt more conservative) is assumption-robust (the optimum stays <60% equity across forward vols 20/18/15%); the strict three-axis dominance MARGIN narrows to ~1pp at 15% vol. BUT no allocation clears 3.75% reliably (best ~70%) - 10yr return DISPERSION, not the mix, is the binding constraint ([[F41]]); and the tilt's drawdown edge is regime-dependent (inherits the -0.29 stock-bond correlation, +0.12 since 2022). REFINES the static-60/40 product ([[D4]]/[[F41]]), does not change the family. Confirms [[D6]]/[[F25]].
Links: [[E33|evidenced_by]] · [[F41|refines]] · [[D4|refines]] · [[D6|supports]] · [[F25|supports]].
_— captured development@00be0c5, 2026-06-28_

### E34 — study #10: live<->backtest reconciliation (read-only forensic) - why is the live bot flat?
tools/live_backtest_reconciliation_study.py + docs/research/D6_live_backtest_reconciliation.md. READ-ONLY forensic (panel AST-audited: no live-state mutation; reproduces ctx perf against the live DB) quantifying [[F28]] - why the live bot is flat vs the backtest headline. PART A: re-derives F13/F14 on the LIVE instrument (QQQ/TQQQ hourly cache) - lag-1 return autocorrelation is negative DAILY (MR) but ~0 hourly and +0.07 within-session (momentum); the dip-buy sleeve nets +16-17bps/trade daily vs -3bps hourly. PART B: decomposes the live fills - CONFIRMED (bracket_exit+stop_hit, 51) net +1.55% (flat) vs ALL +37% (inflated by 6 inferred target_hit + 9 max-bars time_exit marks). 2-lens skeptic panel (blocking=false, byte-reproducible). Builds on [[F13]]/[[F14]]; quantifies [[F28]].
Links: [[F13|builds_on]] · [[F14|builds_on]] · [[F2|relates]] · [[D6|relates]].
_— captured development@df22530, 2026-06-28_

### F43 — Live<->backtest reconciled: the bot is flat because it trades a coarse-timescale signal hourly (no edge); both the Sharpe-25 backtest and +37% live headlines are artifacts - quantifies F28
[[E34|evidenced_by]]: the live bot is flat NOT because it is broken but because it trades a coarse-timescale (multi-day mean-reversion) signal at the HOURLY frequency where that edge does not exist - re-derived on the live instrument: QQQ/TQQQ lag-1 autocorrelation is negative DAILY (the MR fuel) but ~0 hourly and +0.07 within-session (momentum), and the dip-buy sleeve flips from +16-17bps/trade daily to -3bps hourly. BOTH eye-catching headlines are mirages: the backtest Sharpe-25 was a morning-only (3-bars/day) sampling artifact ([[F13]]/[[F14]]) compounded by an unused adaptive-Kelly sizing ([[F28]]), holdout selection ([[F2]]) and optimistic fills; the live dashboard +37% is a separate exit-accounting artifact (6 inferred target_hit + 9 max-bars time_exit marks - the 51 confirmed fills net +1.55%). The two HONEST numbers (full-session backtest ~0, live CONFIRMED +1.5%) round to FLAT and agree - a qualitative reconciliation, not a single regression. Quantifies/refines [[F28]]: the disconnect is dominated by BAR-FREQUENCY. Confirms [[D6]].
Links: [[E34|evidenced_by]] · [[F28|refines]] · [[F13|builds_on]] · [[F14|builds_on]] · [[F2|relates]] · [[D6|relates]].
_— captured development@df22530, 2026-06-28_

### E35 — Income product universe survey (study #11)
tools/income_universe_study.py: opening SURVEY of the income/bond-alternative ETF universe (treasuries across the curve, IG/HY credit, munis, preferreds, senior loans, options-income, dividend/low-vol) over apples-to-apples 2008-2026 + 2014-2026 windows, in four cuts: (A) per-asset CAGR/vol/maxDD/Calmar/Sharpe/corr_SPY ranked vs static 60/40 and conservative 40/60; (B) a constrained-objective gate (clear the ~3.75% income floor AND a low-drawdown ceiling); (C) a yield-vs-NAV decomposition (raw vs total-return prices -> distribution yield + spend-the-income drawdown); (D) a young-vehicles panel measuring JEPI/SPYD/VTEB/NTSX. Read-only, deterministic, simple-return accounting. Hardened by a 4-lens skeptic panel (2 blocking issues resolved by building cuts C/D) + a 2-lens faithfulness/overclaim pass. Descriptive survey, no bootstrap CIs.
Links: [[D6|builds_on]] · [[F41|builds_on]] · [[F42|builds_on]].
_— captured development@3f588b9, 2026-06-28_

### F44 — No income ETF beats the static 60/40 on income-plus-low-drawdown
Surveying the income/bond-alternative ETF universe (study #11 / [[E35]]) finds NO single ETF in this liquid, survivor-only cross-section delivers BOTH high income AND low drawdown — the two trade off, and no vehicle dominates the static 60/40. (1) Only 2 of 12 non-equity names beat the 60/40 on Calmar (BIL, SHY) — both short-duration low-yield, winning by low return AND low drawdown, not income. (2) High-distribution names carry equity-like-or-worse drawdowns AND erode principal: spend-the-income drawdown deeper than reinvested (QYLD distributes ~11%/yr while NAV falls -2.5%/yr -> spend maxDD -42% vs -25% reinvested; PFF/HYG/JNK/BKLN all erode). (3) NOTHING clears the ~3.75% income floor with even a <20% drawdown — the income floor and the low-drawdown ceiling are MUTUALLY EXCLUSIVE; only LQD clears a 'shallower-than-60/40' bar and its CAGR is bond-bull-inflated. (4) What beats the 60/40 on drawdown is study #9's lever — tilt MORE conservative (40/60: shallower maxDD + higher Sharpe in BOTH windows; the Calmar edge flips between windows). (5) JEPI is the lone defensive counter-hint: ~7pt shallower reinvested drawdown but only ~1.6pt like-for-like on a spend basis, over a benign single-regime window, capped upside, corr +0.87. Structural escape (UNTESTED, recommended next): a held-to-maturity ladder of IG/Treasury defined-maturity ETFs converts DURATION drawdown into realized yield (does not solve credit/reinvestment risk); prerequisite is generalizing cut C's yield-vs-NAV decomposition. Confirms [[D6]]: the honest income product is a static, conservatively-weighted mix — no income-ETF shortcut to low-drawdown income. CAVEATS: survivor-only cross-section (omits BDCs/REITs/EM-debt/CEFs/MLPs), bond-bull-inflated CAGRs, single-path point estimates, no bootstrap CIs.
Links: [[E35|evidenced_by]] · [[D6|supports]] · [[F42|builds_on]] · [[D4|relates]].
_— captured development@3f588b9, 2026-06-28_

### E36 — Held-to-maturity bond ladder study (study #12)
tools/bond_ladder_study.py: capstone of the product-universe program — tests the ONE structural escape study #11 ([[F44]]) flagged, a held-to-maturity bond LADDER. Two cuts, exact zero-coupon bond math throughout (selfcheck-verified): (B) SYNTHETIC 1-10yr zero-coupon Treasury ladder 1962-2026 scored on TWO bases — mark-to-market vs realized amortized-cost (hold-to-maturity) — plus a duration-matched 5yr and a 10yr perpetual constant-maturity ETF foil, and a CPI-deflated REAL drawdown; (A) EMPIRICAL real iBonds Treasury (IBTx 2020+) + iBonds/BulletShares IG (IBDx/BSCx 2018+) ladders vs duration controls SHY/IEI/IEF, LQD, and the static 60/40, incl funds that matured Dec-2025. Hardened by a 3-lens skeptic panel (bond-math/interpretation/empirical) + a faithfulness audit; corrections folded into the tool (amortized-cost realized basis, exact CM pricing, duration-matched controls, CPI real-DD, vol-collapse maturity reframe). Read-only, deterministic.
Links: [[F44|builds_on]] · [[F41|builds_on]] · [[D6|builds_on]].
_— captured development@8776bd6, 2026-06-28_

### F45 — Held-to-maturity ladder works but trades risk, not eliminates it
Testing the held-to-maturity bond LADDER (study #12 / [[E36]]) — the structural escape [[F44]] flagged — CONFIRMS the thesis but shows it is narrower than it looks and trades risks rather than removing them. A 1-10yr Treasury ladder's REALIZED drawdown is ~0 at a return ~= entry yield (synthetic 1962-2026 + real iBonds/BulletShares ladders through 2022), so it is the ONLY construction in the program that can plausibly deliver the ~3.75% income floor with near-zero realized-nominal drawdown. BUT: (1) the realized 0% is DEFINITIONAL — amortized-cost accounting never marks to market and nominal yields>=0, so it can never draw down regardless of rate history (an accounting choice, not a market outcome); (2) the mark-to-market drawdown reduction is JUST LOWER DURATION — a duration-matched perpetual 5yr ETF draws down the same (-14% vs the ladder's -13.7%), and empirically SHY beat the 2020 Treasury ladder on BOTH return (+1.5% vs -0.2%) and drawdown (-5.7% vs -15.8%); the ladder's ONLY unique property is the pull-to-par at maturity (NAV-volatility collapse, observable: IBTF vol 2.62%->0.35% at maturity); (3) the 0% is NOMINAL only — CPI-deflated, the realized ladder LOST -19.1% of purchasing power in the 1970s; (4) floor-clearing is a FORWARD claim on 2026 entry yields — NO ladder in the study actually cleared 3.75% on realized return. It converts MARKET/drawdown risk into TERM + REINVESTMENT + REAL (inflation) risk + zero upside — the honest NOMINAL bond-alternative for an investor who can commit capital to a horizon, NOT a free-lunch escape from risk or inflation. Capstone of the universe program; confirms [[D6]] (the honest product is a static/structural bond construction, never the active engine).
Links: [[E36|evidenced_by]] · [[F44|builds_on]] · [[D6|supports]] · [[D4|relates]].
_— captured development@8776bd6, 2026-06-28_

### E37 — study #13: bonds-dont-hedge regime stress (positive stock-bond correlation / inflation) of the recommended static product
tools/correlation_regime_study.py + docs/research/D6_correlation_regime_study.md. Tests the central SURVIVING CAVEAT of studies #8/#9/#11/#12: every drawdown/hedging claim inherited the benign 2000-2021 negative stock-bond correlation (study #8 disclosed its MC inherits the -0.29 corr, flipped +0.12 in 2022). 64yr monthly (1962-2026), one consistent build: month-end ^GSPC + lagged Shiller dividend yield equity TR (corr 0.9984 vs SPY TR), exact constant-maturity 7yr Treasury ZERO (corr 0.9815 vs IEF) plus a panel-forced par-coupon duration sensitivity, FRED CPI (0.9992 vs Shiller CPI). Cuts: rolling-36m correlation record (sustained flips detected 2000-07 and 2022-08); mix sweep per era, nominal AND real, raw AND excess-of-T-bill Sharpe, paired block bootstrap (block=12m, B=5000, seed=0) + family-wise x12 band; bond-leg swap (7yr/2yr/cash) across EVERY era + full sample; TIP-vs-IEF 2021-23 + DFII10 forward; rolling-10yr goal SHARES by start era. Pre-registered reads honored. 4-lens skeptic panel (data-construction, bond-math, statistics, economics): 1 CONFIRMED / 3 QUALIFIED / 0 REFUTED, blocking=false, byte-reproducible; all corrections FOLDED INTO THE TOOL (coupon sensitivity cut, cut-C trade-off eras, a mis-signed real-DD comparison, explicit framing of the -41-vs-23 anchor, family-wise CI, share-not-probability labels).
Links: [[F41|builds_on]] · [[F42|builds_on]] · [[F45|builds_on]] · [[D6|relates]] · [[D4|relates]].
_— captured development@11659fc, 2026-07-06_

### F46 — The recommended static product is correlation-regime-conditional: positive-corr the tilt Sharpe edge vanishes and its REAL-drawdown edge INVERTS; only short/real ballast mitigates - qualifies F41/F42, D6 stands
[[E37|evidenced_by]]: bonds hedged stocks in only ~22 of the last 64 years (36m corr avg +0.30 over 1962-1999, positive 94% of months; -0.33 over 2000-2021; re-flipped positive 2022-08, now +0.41). The F42 conservative tilt SPLITS BY REGIME: its shallower-NOMINAL-drawdown edge is real (coupon-honest 40v60 dMaxDD CI [+2.1,+11.5] excludes 0 - the primary zero-proxy straddle was a duration artifact) but its excess-Sharpe advantage is NOT regime-robust: [-0.14,+0.04] in 1962-99 and [-0.21,+0.02] in 1965-81 (points NEGATIVE) vs [+0.06,+0.38] in the 2000-21 era it was derived in (family-wise x12: [-0.05,+0.45] - a replication of the study #9 direction, not an independent edge). In REAL terms the tilt INVERTS: 1965-81 real maxDD is -41% for the 40/60 (zero proxy; -36/-37% coupon-honest) and -42% for the 30/70 vs -39% for the 60/40, monotonic in the bond share (bond leg alone -49%); EVERY bond-heavy mix lost purchasing power for a decade (share(real>=0) ~51% of inflation-era 10yr starts) while the NOMINAL 3.75% goal was regime-robust (96-100%) - high nominal yields accompany exactly the inflation that destroys real wealth, so the goal metric itself is the blind spot. Cash ballast MITIGATES that regime (real DD -27%, real CAGR ~0) but loses on every metric in 2000-21 and keeps a deeper nominal maxDD over the full 64yr - duration is a REGIME TRADE-OFF, not a free fix. The one structural fix for the F45 real hole is a held-to-maturity TIPS ladder at DFII10 2.26% real - a FORWARD, amortized-cost-basis claim (MTM TIP drew -22.5% real in 2021-23; F45 term/liquidity/zero-upside costs carry over). QUALIFIES F41/F42: their drawdown promises are NOMINAL and negative-corr-regime-conditional. CONFIRMS D6: no active rehabilitation; the honest product remains static/structural, read with regime-honest labels.
Links: [[E37|evidenced_by]] · [[F42|refines]] · [[F41|refines]] · [[F45|refines]] · [[D6|supports]] · [[D4|relates]].
_— captured development@11659fc, 2026-07-06_

### D10 — Context-map Explore prompts live in the static graph UI
Decision: selected-node exploratory prompts are generated deterministically inside the self-contained ctx graph --html template, not by a backend or LLM service. This keeps the context-map UI portable, credential-free, and safe to serve as static HTML; richer Ask-Codex handoff can layer on later. Implemented in tools/ctx.py::_GRAPH_HTML with kind-specific prompt cards and clipboard fallback, guarded by tests/test_research_web.py::TestGraphHtmlExplore. (Renumbered from a colliding "D7" at merge — captured on a branch that predated the VD-2 D7; IDs D7/D8 were already taken.)
_— captured development@af53bac, 2026-06-27_

### D11 — Shift-drag 3D map uses static SVG projection
Decision: the context-map 3D interaction is implemented as a lightweight 3D vector layout inside the existing self-contained D3/SVG ctx graph --html template. The D3 force pass still solves screen `x/y`, but each node now gets a deterministic `z` coordinate and a link-aware depth relaxation pass, so orbit/projection/focus operate on real node vectors rather than a purely 2D map with draw-time depth offsets. Holding Shift while dragging orbits the displayed projection around the current viewport center derived from the active zoom transform, not the original map center; the small `flat` control returns the camera to a top-down view without clearing selection/search or zooming back out from the current focus; clicking a node starts a slow screensaver-style orbit cruise that continuously eases through roughly minute-long viewpoint loops around the selected node, keeping one-hop connecting nodes framed on a dark outer-space canvas. Moving views enter a fast-render mode that disables expensive blur filters on distant non-focused nodes, throttles label/depth-order layout, skips label recompute during fast zoom/fit transitions, shortens initial force-layout settling, and combines cruise orbit+zoom into one render pass per animation frame; full glow quality returns after motion settles. The extra projected background-dot layer was removed, actual context nodes render as soft layered SVG glow orbs instead of explicit star icons or flat circles, and labels/tooltips use a lightweight collision pass so focused labels sit outside the glow and lower-priority labels fade instead of overlapping. Normal node drag, zoom, search, selection, fit, reset, and static serving remain unchanged. This avoids a Three.js/WebGL dependency while still giving the map a grab-and-tilt spatial layer.
Links: [[D10|refines]]. (Renumbered from a colliding "D8" at merge, and its refines target from "D7" — see [[D10]].)
_— captured development@af53bac, 2026-06-27_

### D12 — Public positioning: research substrate first, trading bot as reference implementation (README repositioned)
Decision (Stage 0.5 of the OSS plan): the public README now leads with the research SUBSTRATE - the Context Kit evidence graph, the validation funnel, and the thirteen-study adversarially-verified research library (with a findings table mapping each result to its transferable lesson + nodes) - and presents the trading stack as the REFERENCE IMPLEMENTATION that exercises the substrate end-to-end. The honest no-edge story ([[D6]], [[F13]], [[F43]]) is framed as the library's best credential (negative results, rigorously proven, are the product), NOT hidden: 'Known Limitations' became 'Honest Disclosures' and leads with the no-edge verdict. Rationale: the repo's durable value is the methodology + verified findings + graph tooling, which generalize; the bot alone reads as a failed strategy. Supports the Context-web OSS foundation plan (VISION.md Stage 0-4).
Links: [[D6|relates]] · [[F46|relates]] · [[F13|relates]].
_— captured development@cb90093, 2026-07-07_

### H41 — OPEN [ctx]: note.py ID allocation is not concurrent-session safe (D7/D8 collision at merge) - add a branch-aware ID guard
Discovered resolving the 2026-07-06 merge: a parallel session on a stale base allocated D7/D8 for two ctx-graph-UI decisions while those IDs were already taken on the canonical branch (VD-2 and honest-fallback), producing duplicate '### D7'/'### D8' headings on origin/development; the merge had to renumber them to D10/D11 by hand and fix an internal refines link. note.py add allocates the next free ID from the LOCAL working tree only. Open: make allocation collision-resistant - e.g. check git origin/<default branch> for taken IDs when reachable, or reserve per-session ID ranges, or have ctx health hard-fail duplicate headings (it currently keys nodes by ID so the second definition silently shadows the first in parsing). Cheap first step: a duplicate-heading detector in web --lint.
Links: [[H15|relates]].
_— captured development@cb90093, 2026-07-07_

### H42 — OPEN: study #14 candidate - a TIPS sleeve INSIDE the static mix (not the ladder) under study #5 discipline
[[F46]] establishes TIPS as the structural mitigation of the bonds-dont-hedge regime but tested them only as (a) a full bond-leg swap in the 2021-23 shock window and (b) a forward held-to-maturity ladder claim. Untested: a modest TIPS SLEEVE (e.g. 10-20% TIP carved from the IEF leg of the recommended conservative mix) evaluated with exactly study #5's machinery - paired block bootstrap of dSharpe/dMaxDD vs the un-sleeved mix over TIP's full 2004-2026 life, nominal AND real, with the 2021-23 event as a regime cut and a family-wise correction (this would be another best-of-N sleeve test; [[F39]] shows how gold died OOS under that discipline). Pass criteria to pre-register: the sleeve must improve the REAL drawdown in the positive-corr cut without a significant Sharpe cost in the negative-corr cut. Expected difficulty: TIP is itself ~6.7yr duration, so the 2022 duration shock hits it too ([[F46]]); the interesting version may be SHORT-duration TIPS (VTIP/STIP, 2010+).
Links: [[F46|builds_on]] · [[F42|relates]] · [[F39|relates]] · [[D4|relates]].
_— captured development@cb90093, 2026-07-07_

### H43 — OPEN: study candidate - is there a regime-AGNOSTIC ballast? (duration barbell / fixed blend vs the two poles)
[[F46]] shows duration is a regime trade-off: the 7yr leg wins the negative-corr era on every metric, cash wins the positive-corr/inflation era on real drawdown, and each loses badly in the other regime. Open: does a FIXED blend (e.g. 50/50 cash+7yr, or a 2yr/10yr barbell at matched average duration) weakly dominate BOTH poles across BOTH eras - i.e. is there a static regime-agnostic ballast, or is the frontier strictly regime-conditional? Method: reuse correlation_regime_study's builders (const_maturity_zero/coupon, cash_returns, era table, paired boot) and sweep the ballast composition per era on nominal maxDD + real maxDD + excess Sharpe; pre-register that 'dominance' means no-worse on all three in each era with bootstrap support. If no blend dominates, that ITSELF is the finding (the ballast choice is an irreducible regime bet), which sharpens [[F46]]'s product guidance and the D8 honest-fallback framing.
Links: [[F46|builds_on]] · [[D8|relates]].
_— captured development@cb90093, 2026-07-07_

### F47 — Live gap-through-stop: overnight hold turned a 0.5% stop into a -4.007% realized loss (backtest never models this)
Direct observation from live state.db (trades + monitor_events), not an experiment. 2026-07-06 18:32 UTC: live bot entered LONG 123 TQQQ @ 76.61 (14:32 ET, back-to-back re-entry). Neither TP (+1%) nor SL (-0.5%, ~76.23) hit before Monday close, so the position was held overnight — the strategy has no end-of-day flatten. TQQQ gapped down overnight; Tuesday's stop filled @ 73.54 near the open (first 9:30-10:30 ET bar closed 71.50), realizing -4.007% — 8x the configured 0.5% stop. Backtest impact: compute_trade_returns() fills every stop at exactly -stop - stop_slippage_pct (src/strategy/engine.py:353), so session-boundary gaps that blow through the stop are modeled as ~-0.5% while live realizes the full gap — a concrete live instance of the fill-model disconnect (workstream C2). Live tail risk on 3x ETFs is understated by the backtest. Mitigation candidates: (a) end-of-day flatten for hourly modes (no overnight holds), (b) model gap fills in compute_trade_returns by filling at next-bar open when it gaps past the stop level, (c) accept as known cost and size for it. Also noted: the exit wrote the trades table but emitted NO monitor_event (exit events may only fire on the fill-data-unavailable path?).
Links: [[F28|refines]].
_— captured development@9e7ca52, 2026-07-07_
