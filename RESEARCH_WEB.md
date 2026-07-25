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
<!-- status: superseded; by: F13; reason: inverted; at: 2026-07-24 -->
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

### H2 — RESOLVED then REVERSED by F13: un-leveraged indices generalize the edge? → NO
Originally closed YES on the noise-ratio mechanism [[F7]] plus SPY/IWM corroboration ([[E6]]).
[[F13]] then reversed the premise: the hourly edge was a morning-only sampling artifact, so
there was no edge to generalize. The corroborating finding [[F9|relates]] is superseded, and
this YES no longer stands — [[F22]] later found no risk-adjusted edge at any timescale. The
mechanism [[F7]] survives as an explanation of *relative* stop-vs-noise behaviour. → [[D3]].

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
mechanism [[F7]], [[F9]]; resolved [[H2]], explained [[F4]]. CAVEAT: this ran on the
morning-only cache, so its edge magnitudes were later overturned by [[F13]] — [[F4]] and
[[F9]] are superseded. The run itself stands; the noise-ratio mechanism [[F7]] survives
because it explains *relative* stop-vs-noise behaviour, which the sampling bug did not touch.
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
Links: [[E12|evidenced_by]] · [[F22|builds_on]] · [[D5|refines]] · [[D4|refines]] · [[F24|relates]] · [[F25|relates]] · [[F26|relates]].
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
diff 0.0). Reproducible: `tools/mr_daily_lab.py gonogo`. Produces [[F24|produces]]; extends [[E12|builds_on]].
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
needs (Sharpe is time-in-market sensitive). Produces [[F25|produces]]; extends [[E11|builds_on]], [[E12|builds_on]].
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
tools/live_backtest_reconciliation_study.py + docs/research/D6_live_backtest_reconciliation.md. READ-ONLY forensic (panel AST-audited: no live-state mutation) quantifying [[F28]] - why the active hourly signal is flat vs the backtest headline. PART A re-derives F13/F14 on QQQ/TQQQ: lag-1 return autocorrelation is negative DAILY (MR), ~0 hourly, and +0.07 within-session (momentum); the dip-buy sleeve nets +16-17bps/trade daily vs -3bps hourly. PART B decomposes the former 69-row export: the historically named CONFIRMED bucket (bracket_exit+stop_hit, 51) nets +1.55% (flat) vs ALL +37%, with six ~1% target_hit and nine max-bars time_exit rows driving the difference. [[F87]] corrects CONFIRMED to project exit-confirmed on a quote-derived basis; [[F88]] establishes that inference rows are execution-unverified rather than proven non-fills. The declared input is absent from the current checkout, so the 51-row number is not currently repriceable. Builds on [[F13]]/[[F14]]; quantifies [[F28]].
Links: [[F13|builds_on]] · [[F14|builds_on]] · [[F2|relates]] · [[D6|relates]].
_— captured development@df22530, 2026-06-28_

### F43 — Live<->backtest reconciled: the bot is flat because it trades a coarse-timescale signal hourly (no edge); both the Sharpe-25 backtest and +37% live headlines are artifacts - quantifies F28
[[E34|evidenced_by]]: the active signal is flat because it applies a coarse-timescale (multi-day mean-reversion) idea at the HOURLY frequency where that edge does not exist. QQQ/TQQQ lag-1 autocorrelation is negative DAILY but ~0 hourly and +0.07 within-session; the dip-buy sleeve flips from +16-17bps/trade daily to -3bps hourly. The backtest Sharpe-25 was a morning-only sampling artifact ([[F13]]/[[F14]]) compounded by unused adaptive-Kelly sizing ([[F28]]), holdout selection ([[F2]]), and optimistic fills. The dashboard +37% is a separate accounting artifact: the 51-row project exit-confirmed bucket nets +1.55%, while six ~1% target_hit and nine max-bars time_exit rows drive the broader result. [[F87]]/[[F88]] weaken the execution-provenance labels but not the flat verdict. Full-session backtest ~0 and the project bucket +1.5% round to FLAT and agree qualitatively, not as one regression. This does not imply the runtime is operationally sound. Quantifies/refines [[F28]]: the disconnect is dominated by bar frequency; confirms [[D6]].
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

### E38 — study #14: TIPS sleeve inside the static mix (TIP/STIP/VTIP 5-20% carved from the IEF leg) under study #5 discipline
tools/tips_sleeve_study.py + docs/research/D6_tips_sleeve_study.md. Tests the retail-implementable middle ground [[F46]] left open. Base 40%SPY/60%IEF daily 2004-2026; sleeves ws in {5,10,15,20}% of portfolio from the IEF leg into TIP (2004+), STIP (2011+), VTIP (2013+); cuts: full variant life, neg-corr 2004-2021 (the cost side), flip 2022+ (the one observed bonds-dont-hedge event), 2021H2-2023 shock; nominal AND CPI-deflated. Paired block bootstrap (20d, B=5000, seed=0) of sleeved-minus-base with a family-wise x12 band; a nominal duration CONTROL (IEI) scored alongside, and - panel-forced - a duration-MATCHED control (IEI sleeve sized x5/3) as the verdict-bearing direct test, with unrounded CI bounds (a first-draft call had hinged on display rounding at +0.0049). Pre-registered reads applied mechanically. 3-lens skeptic panel: 1 CONFIRMED / 2 QUALIFIED / 0 REFUTED, byte-reproducible; corrections folded in (matched control, unrounded bounds, real selfcheck assert, sharpe_ok loophole removed, neg-corr cut printed, doc table regenerated).
Links: [[H42|resolves]] · [[F46|builds_on]] · [[F39|relates]] · [[F45|relates]].
_— captured development@0979530, 2026-07-07_

### F48 — No TIPS sleeve earns a place in the static mix: the short-TIPS benefit is duration-shortening in disguise (duration-matched control kills it) - resolves H42, third confirmation of the F45 lesson
[[E38|evidenced_by]]: UPGRADES: NONE - every TIPS sleeve's flip-cut dMaxDD family-wise (x12) band crosses 0 (robust across block 10/20/40 x seeds 0-2 and stricter families). Full-duration TIP sleeves do nothing anywhere (full-window point estimates lean mildly harmful, P(shallower) 17-20%). Short-TIPS sleeves (STIP/VTIP 10-20%) improve the 2022+ cut with P(shallower)~100% BUT: (a) fail the family-wise correction (the [[F39]] gold tier - unadjusted OOS hypotheses at best); (b) cost Sharpe AND drawdown in the neg-corr 2004-2021 cut (STIP20: Sharpe 1.375->1.301, maxDD -11.1->-12.6 - the [[F46]] regime trade-off at sleeve scale); (c) DECISIVELY, are statistically indistinguishable from a duration-MATCHED nominal Treasury sleeve on BOTH drawdown and Sharpe (VTIP10-minus-IEI17: dMaxDD [-0.20,+0.70], dSharpe [-0.009,+0.046]) - the apparent dSharpe exclusion vs a same-size control ([+0.006,+0.074]) was a RESIDUAL-DURATION artifact (IEI ~4.5yr vs VTIP ~2.5yr undercorrects), caught by the panel and withdrawn. Scope: 2022+ was a REAL-YIELD shock, MTM TIPS' structurally worst case (their MTM hedges inflation-EXPECTATIONS moves) - the null is mechanism-scoped, n=1 event. Product guidance unchanged: no marked-to-market TIPS sleeve; the honest TIPS exposure remains the [[F46]] held-to-maturity ladder (realized, not marked, inflation compensation). Confirms [[F45]] (drawdown claims = duration in disguise) a third time.
Links: [[E38|evidenced_by]] · [[H42|resolves]] · [[F46|refines]] · [[F45|supports]] · [[F39|relates]] · [[D6|supports]].
_— captured development@0979530, 2026-07-07_

### E39 — study #15: regime-agnostic ballast test (cash/z7 blends + duration barbells vs the two poles, 1962-2026)
tools/ballast_blend_study.py + docs/research/D6_ballast_blend_study.md. Resolves the [[F46]] cut-C either/or by testing COMPOSITION: 40% equity + 60% ballast on study #13's exact monthly build (imported), ballast in {7yr-zero pole, T-bill-cash pole, 25/50/75 cash-z7 blends, 50/50 z2/z10 barbell, and - panel-forced - a duration-MATCHED 37.5/62.5 barbell (Macaulay exactly 7.0)}. Pre-registered weak-dominance test vs the era-best pole in BOTH decision eras (pos-corr 1962-1999, neg-corr 2000-2021) on excess Sharpe + nominal maxDD (paired block bootstrap, 12m/B=5000/seed=0) + real maxDD (1pp tol), plus a minimax-regret ranking normalized by the pole-vs-pole gap (poles' own worst regret = 1.00 by construction, now printed). 3-lens skeptic panel: 1 CONFIRMED / 2 QUALIFIED / 0 REFUTED, byte-reproducible; pole rows verified to reproduce study #13 cut C exactly; verdict shown PROXY-ROBUST under coupon-honest legs; near-tolerance real-DD failures flagged bootstrap-fragile (every candidate keeps at least one robust failure); dead code removed.
Links: [[H43|resolves]] · [[F46|builds_on]] · [[E37|relates]] · [[D8|relates]].
_— captured development@0979530, 2026-07-07_

### F49 — No regime-agnostic nominal-Treasury ballast exists: the ballast choice is an irreducible regime bet - a 50/50 cash/bond blend HALVES the worst case (minimax regret 0.49 vs the poles' 1.00), nothing removes it
[[E39|evidenced_by]]: every fixed composition FAILS weak dominance vs the era-best pole, each on at least one robust leg (25/75 and both barbells: pos-era real-DD gaps of 8.6-12.9pp with bootstrap CIs excluding the 1pp tolerance; 50/50 and 75/25: neg-era excess-Sharpe CIs entirely below 0 across 9 block-seed combos). The duration-MATCHED 37.5/62.5 z2/z10 barbell is statistically IDENTICAL to the 7yr pole in the neg era (dSh [-0.06,+0.06], dMaxDD [-1.5,+0.3]) - at matched duration, curve SHAPE adds nothing (absence of evidence at one matched point; ~90% of the unmatched 50/50 barbell's shortfall was its 6.0-vs-7.0 duration gap, a panel catch) - so within nominal Treasuries the ballast question is ONE-DIMENSIONAL: how much duration. [[F46]] maps that trade-off; [[F48]] closes the marked-to-market REAL-ballast variant. Constructive: the minimax-regret ballast is 50/50 cash/z7 - worst normalized regret 0.49 pole-gap units vs the poles' 1.00 by construction (bootstrap-robust winner in ~95% of replicates; proxy-robust: 0.51 coupon-honest), and EVERY blend beats BOTH poles on full-sample 64yr excess Sharpe (0.489-0.507 vs 0.484/0.463) with the 50/50's real DD 10.5pp shallower than the bond pole - cross-regime diversification is real and free; it is just not dominance. Sharpens [[F46]] product guidance and the [[D8]] honest fallback: refuse the regime bet -> hold the regret-minimizing blend and accept second-best everywhere; halve the bet, never remove it.
Links: [[E39|evidenced_by]] · [[H43|resolves]] · [[F46|refines]] · [[F48|relates]] · [[D8|relates]] · [[D6|supports]].
_— captured development@0979530, 2026-07-07_

### E40 — study #16: overnight gap-through-stop risk
tools/overnight_gap_risk_study.py + docs/research/D6_overnight_gap_risk_study.md. Full-session TQQQ hourly replay (2024-08-01..2026-07-22), current live signal shape including the trader's TRADER_ALLOW_SHORTS=False gate, one position, paired exact-stop vs open-aware gap fills; exact custom replay first matches compute_trade_returns over 1,516 gated-long trades with zero differences. Tests 8/10-bar caps, scalar stop-penalty calibration, and EOD flatten; selfcheck + Python 3.9/3.13 JSON-identical reproduction. Builds on [[F47]] and refines [[F28]].
Links: [[F47|builds_on]] · [[F28|refines]].
_— captured development@234691a, 2026-07-23_

### F50 — Exact-stop fills roughly halve observed hourly loss and drawdown; overnight gap risk is structural
[[E40|evidenced_by]]: on 3,429 full-session TQQQ hourly bars / 494 sessions, the live-shaped long-only sequential replay carries 127/1,117 positions overnight and 34 (26.8%) open through the 0.5% stop. Exact-stop accounting reports -5.17% total / -5.88% maxDD at fixed 10% sizing; open-aware fills report -10.15% / -10.19%, a -5.38pp account-performance hit robust at 8 and 10 hold bars. A mean-matching 7.0bp stop penalty hides the tail (conditional damage median 1.03pp, p90 3.51pp, max 8.96pp). The July live case reproduces at -3.82% vs observed -4.01%. Corrected EOD flatten (official-close proxy, cannot fire before entry) removes the gap channel and improves the path to -5.77% / -6.75% but still has no edge. Strengthens [[F47]]/[[F28]] and supports [[D6]]; two-year path, not a stationary forecast.
Links: [[E40|evidenced_by]] · [[F47|builds_on]] · [[F28|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E41 — study #17: backtest-to-live execution-semantics waterfall and entry-bar ordering audit
One shared full-session TQQQ feature panel is replayed through clock, regime, short-gate, position-overlap, entry-bar-bracket, and gap-fill assumptions. A paired 1,516-entry test proves N+2 exactly matches compute_trade_returns but 980 entries touch a bracket in N+1; 157 are dual-hit. Hourly ordering bounds total return at -7.61% to +16.91%; recent 5m calibration resolves 16/19 (11 stop-first, 5 target-first; 3 remain ambiguous). Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_execution_semantics_study.md.
Links: [[F28|refines]] · [[F43|refines]].
_— captured development@234691a, 2026-07-23_

### F51 — The research engine skips the live bracket's entry hour; the mismatch is material but hourly OHLC cannot identify its return sign
E41 pairs identical entries and shows 980/1,516 (64.6%) exit in the entry hour. Delayed N+2 returns +11.94%; immediate N+1 spans -7.61% under stop-first to +16.91% under target-first because 157 entry bars hit both thresholds. Recent 5m evidence leans stop-first (11 vs 5 resolved; Wilson95 target-first 14.2%-55.6%) but is small/clustered. Therefore N+2 is not live-faithful and pessimistic hourly N+1 is not a fully identified repair; tick/order-event or broad lower-timeframe history is required for return claims.
Links: [[E41|evidenced_by]] · [[F28|refines]] · [[F43|supports]].
_— captured development@234691a, 2026-07-23_

### E42 — study #18: overnight-risk mitigation frontier and stop-width stress
Pre-registered risk gate compares time cutoffs, end-of-day flatten, 0.25%-3% stops, and calendar slices on the live-shaped gap-aware replay. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_gap_mitigation_frontier_study.md.
Links: [[F50|builds_on]] · [[F13|relates]].
_— captured development@234691a, 2026-07-23_

### F52 — Only direct exposure removal cleanly eliminates the observed gap channel; clock cutoffs are in-sample selection and wider stops do not bound jumps
E42: corrected EOD flatten removes 34/34 gap stops and improves maxDD 3.44pp but remains -5.77% using an official-close proxy; its observed benefit implies a rough 34.7bp extra-cost budget per EOD exit across 126 exits before erasure. A source audit found the last hourly close differs from daily close by >5bp on 13.16% of sessions (max 129.9bp), and a harness bug had allowed open entries to flatten before they existed; both are corrected/self-checked. Noon/13:00 cutoffs pass the numeric risk gate but suppress 49%/36% of trades and repeat F13's morning-only selection mechanism, so they are not validated alpha. Across 0.25%-3% stops, worst conditional misses remain 7.46-9.21pp; width changes survival into the close, not the size of a discontinuous open.
Links: [[E42|evidenced_by]] · [[F50|refines]] · [[F13|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E43 — study #19: 2010-2026 cross-instrument leveraged-ETF overnight-gap history
Unconditional close-to-open tails for SPY/SSO/UPRO, QQQ/QLD/TQQQ, SOXL, and TNA plus paired leverage regressions and COVID/2022/recent slices. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_cross_instrument_gap_history.md.
Links: [[F50|builds_on]].
_— captured development@234691a, 2026-07-23_

### F53 — Leveraged-ETF overnight gap tails scale nearly mechanically with leverage across 16 years, so TQQQ's jump risk is structural rather than a two-year signal accident
E43: over 4,133 nights, TQQQ's 1% gap quantile is -6.69%, worst-1% mean -10.33%, 31.19% of opens are <=-0.5%, 11.71% <=-2%, and worst is -28.82%. TQQQ-vs-QQQ gap beta is 2.95 (R2 .993); 2x/3x pairs recover 1.99-2.99 betas. SOXL/TNA and COVID, 2022, 2025-26 slices confirm the channel. At the current 10% paper position shape, the simple account translation is -0.67% at the instrument q01, -1.03% at ES1, and -2.88% at the historical worst before spread/liquidity. These are unconditional historical scenarios, not strategy loss probabilities, sizing recommendations, limits, or a stationary forecast.
Links: [[E43|evidenced_by]] · [[F50|refines]] · [[F47|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E44 — study #20: entry-bar ordering break-even and calibration value-of-information
Derives exact target-first break-even counts for the paired overlapping diagnostic (53/157=33.76%), one-position exact path (36/138=26.09%), and one-position open-aware path (72/138=52.17%). Exact beta-binomial/Jeffreys sensitivity uses the durable 5m audit; Wilson sample-size analysis measures whether more calibration can resolve the sign. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_entry_bar_calibration_study.md.
Links: [[F51|refines]] · [[F50|builds_on]].
_— captured development@234691a, 2026-07-23_

### F54 — Entry ordering can flip the exact-stop result, but cannot plausibly rescue the gap-aware live-shaped path on current calibration evidence
E44: exact-stop break-even lies near observed target-first rates and is unidentified (overlap diagnostic predictive P(total>0) 27%-78%; one-position exact 44%-91% across unresolved bounds). The open-aware one-position path instead needs 72/138=52.17% target-first vs 4/14=28.57% resolved; Jeffreys beta-binomial predictive P(total>0) is 1.2%-20.4%, median -5.59% to -2.13%. Conditional on strong exchangeability assumptions, not proof of negative alpha. Do not patch with a 16-event stochastic rate; resolve the three 5m dual-hits and obtain historical lower-timeframe/order-event data.
Links: [[E44|evidenced_by]] · [[F51|refines]] · [[F50|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E45 — study #21: calendar-aware partial flattening before weekends and long closures
Attributes 34 strategy gap events by known session spacing and tests flatten-before-4+, 3+, and 2+ calendar-day closures against daily flatten under the pre-registered mitigation gate. Adds event concentration and first-order execution-cost budgets. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_calendar_gap_mitigation_study.md.
Links: [[F52|refines]] · [[F50|builds_on]].
_— captured development@234691a, 2026-07-23_

### F55 — Weekend and long-closure opens carry 44% of gap damage but only 24% of events; partial flatten cuts turnover, not the dominant weekday risk
E45: 8/34 gaps after 3-4 calendar-day closures cause 23.70/53.76pp (44.08%) gross trade damage. After correcting the pre-entry flatten bug and using official daily closes, flattening before >=3-day closures uses 29 exits vs daily flatten's 126, improves total -10.15% to -8.61% and maxDD -10.19% to -8.65%, but removes only 23.53% of gap stops and misses the >=50%/2pp gate. Adding 2-day holiday eves makes 4 extra exits, removes no additional baseline gap, and worsens the path. Top five events carry 46.14% of damage. Calendar partial flatten is a turnover compromise, not tail elimination.
Links: [[E45|evidenced_by]] · [[F52|refines]] · [[F50|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E46 — study #22: expiring one-minute resolution of entry-bar ambiguity
Recovered the July 6 one-minute TQQQ window before vendor retention expired, durably hashed the 1,170-row source, and resolved one of three five-minute dual hits. June 23-24 were already outside the stated 30-day range. Artifact: tools/overnight_gap_risk_study.py; audit: docs/research/data/entry_bar_1m_resolution_2026.csv; doc: docs/research/D6_one_minute_entry_resolution_study.md.
Links: [[F54|refines]] · [[E44|builds_on]].
_— captured development@234691a, 2026-07-23_

### F56 — One-minute evidence resolves July 6 stop-first; exact-stop sign remains unidentified while the gap-aware rescue bound tightens
E46: July 6 hit the 0.5% stop in the 09:30 one-minute bar and the 1% target at 09:34. Best-available counts become 5 target-first / 12 stop-first / 2 unresolved (29.41% of 17); the one-position subset is 4/15 target-first. Exact-stop break-even remains indistinguishable (26.09% vs 26.67%; ~21,887 resolved events to separate at that rate). Open-aware break-even is 52.17%; model-based P(total>0) tightens to 1.24%-9.89%. The resolved-only Wilson upper is 51.95%, only 0.22pp below break-even and not conservative to the two unknowns. Do not impute them or patch the simulator from 17 clustered events.
Links: [[E46|evidenced_by]] · [[F54|refines]] · [[F51|refines]] · [[F50|supports]].
_— captured development@234691a, 2026-07-23_

### E47 — study #23: overnight-gap clustering and lagged-volatility risk frontier
Measures dependence of TQQQ <=-2% overnight gaps over 4,113 nights, block-bootstrap rate uncertainty, conditional cluster risk, and a leak-free QQQ 20-session realized-volatility classifier shifted before each open. Applies fixed 12.5%-50% thresholds as risk-only flatten counterfactuals on the live-shaped path. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_gap_cluster_volatility_study.md.
Links: [[F53|builds_on]] · [[F55|builds_on]].
_— captured development@234691a, 2026-07-23_

### F57 — Severe TQQQ gaps cluster, and lagged volatility captures weekday risk only by disabling most overnight exposure
E47: <=-2% gaps occur 483/4,113 nights (11.74%; block20 CI 10.41%-13.13%). The next-night rate after a severe gap is 15.77% (1.34x); max clusters are 4/5 and 10/20 sessions. A 15% lagged-QQQ-vol rule captures 75.16% of unconditional severe gaps and removes 61.76% of strategy gap stops with 66 exits, improving the negative path to -6.10%/-6.81%; but it removes 56.5% of all nights and 75.3% since 2020. At 17.5% the strategy event gate already fails. This is the best partial risk mechanism found, but broad, same-sample, selected, and not alpha or production approval.
Links: [[E47|evidenced_by]] · [[F53|refines]] · [[F55|refines]] · [[F52|supports]].
_— captured development@234691a, 2026-07-23_

### E48 — study #24: mitigation dependence, auction-cost, and selection stress
Aligns candidate-policy wealth effects to exit sessions, circular-block bootstraps paired daily log differences at 5/20/60 sessions, reports calendar slices, and charges 0-80bp incremental cost per flatten exit. Compares daily, weekend/long-closure, and selected lagged-vol>=15% controls against the gap-aware baseline. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_mitigation_uncertainty_cost_study.md.
Links: [[F52|builds_on]] · [[F55|builds_on]] · [[F57|builds_on]].
_— captured development@234691a, 2026-07-23_

### F58 — Daily and lagged-volatility flatten survive same-path block stress, but cost and post-selection leave only a forward paper-shadow hypothesis
E48: block20 relative-wealth CIs are daily [+1.82,+8.58]%, weekend [-0.50,+4.70]%, and lagged-vol>=15% [+1.99,+7.83]%; the direction is stable across 5/20/60 blocks. Extra-cost break-even budgets are ~34.7/53.2/61.3bp per exit; at 40bp daily is worse than baseline while lagged-vol retains +1.60pp. Daily/vol directions are positive in all three dependent calendar slices; weekend reverses in 2024. The vol rule uses 66 vs 126 daily exits but was selected on the same two-year path and disables most recent nights. Freeze it only for future paper shadow accounting of real auction fills; no live/config change.
Links: [[E48|evidenced_by]] · [[F52|refines]] · [[F55|refines]] · [[F57|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E49 — study #25: lagged-volatility lookback and early-split falsification
For QQQ realized-volatility lookbacks of 10, 20, 40, and 60 sessions, selects the highest absolute threshold retaining at least 60% capture of TQQQ gaps at or below -2% using 2010-2019 only, freezes it, tests the classifier on 2020-2026, and applies each control to the live-shaped 2024-2026 replay. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_volatility_lookback_oos_study.md.
Links: [[F57|refines]] · [[F58|builds_on]].
_— captured development@234691a, 2026-07-23_

### F59 — The 20-day volatility rule survives an early threshold split, but the mechanism is lookback-sensitive and longer memories approach daily flatten
E49: the 2010-2019 rule independently selects 15% for both 10d and 20d QQQ volatility. In 2020-2026 their unconditional severe-gap capture is 82.2% and 85.3%, but on the strategy path 10d removes only 47.1% of gap stops and fails the risk gate while 20d removes 61.8% with 66 exits and passes. The 40d/60d rules select 12.5%, remove 88.2% of strategy gaps, and pass, but require 96/104 exits versus daily flatten 126, so much of their protection is broad exposure removal. Every path remains negative. This supports a specific paper-shadow candidate of 20d/15%, not generic vol timing or production approval.
Links: [[E49|evidenced_by]] · [[F57|refines]] · [[F58|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E50 — study #26: forward shadow validation and fixed evidence horizons
Freezes the 20-session QQQ volatility at 15% candidate, derives one-sided exact-binomial event horizons for strategy-conditioned and unconditional severe-gap capture, plans cost-precision scenarios, defines an immutable shadow ledger, and audits whether IBKR Paper Trading can identify real closing-auction cost. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_forward_shadow_validation_design.md.
Links: [[F58|builds_on]] · [[F59|builds_on]].
_— captured development@234691a, 2026-07-23_

### F60 — A paper shadow can falsify the volatility classifier, but validation is multi-year and IBKR paper fills cannot identify auction cost
E50: historical strategy capture is 21/34 and is not significant against 50% (one-sided exact p=.1147). At the observed 61.76% alternative, an iid fixed horizon needs 115 strategy gap events and at least 67 captures for 80% power, about 6.67 years; heuristic clustering design effects of 1.25-2.0 extend this to roughly 144-230 events / 8.35-13.34 years. The unconditional >60% capture surrogate needs 62 severe gaps and at least 44 captures, about 2.10 iid years, but is not decision-equivalent. IBKR documents that Paper Trading has no execution/clearing ability, does not support Auction orders, and simulates top-of-book fills; paper-only evidence therefore cannot clear the 61.3bp real MOC cost gate. Freeze a no-order ledger for classifier/plumbing falsification only; no production approval.
Links: [[E50|evidenced_by]] · [[F58|refines]] · [[F59|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E51 — study #27: simple recent-gap risk-classifier benchmarks
Benchmarks the lagged QQQ-volatility rule against transparent flags active for 1, 2, 3, 5, 10, or 20 sessions after a TQQQ gap at or below -2%. Reports exposure, severe-gap capture, lift over random flags, downside capture, and live-shaped mitigation paths. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_simple_risk_classifier_benchmarks.md.
Links: [[F57|refines]] · [[F59|refines]].
_— captured development@234691a, 2026-07-23_

### F61 — Volatility does not beat simple gap clustering on unconditional concentration, but it aligns better with this selected strategy path
E51: vol20>=15% removes 56.5% of nights and captures 75.2% of severe gaps, lift 1.33x. Recent-gap windows of 1-5 sessions have essentially the same 1.31x-1.38x lift, so unconditional concentration is not unique to volatility. On the strategy path, vol20 removes 61.8% of gap stops with 66 exits and passes, while the exposure-near prior-10 rule removes 47.1% with 72 exits and fails. A recent-gap rule passes only at 20 sessions, removing 82.9% of nights with 104 exits. The strategy alignment is same-sample and requires Study26 forward testing; all paths remain negative.
Links: [[E51|evidenced_by]] · [[F57|refines]] · [[F59|refines]] · [[F60|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E52 — study #28: volatility-classifier annual regime and base-rate decomposition
Decomposes the frozen vol20>=15% rule by year into exposure removed, severe-gap capture, capture lift over exposure-matched random flags, precision, and downside capture; also performs recent leave-one-year-out summaries. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_volatility_regime_stability.md.
Links: [[F59|refines]] · [[F61|builds_on]].
_— captured development@234691a, 2026-07-23_

### F62 — Recent volatility-rule capture is stable but mostly broad regime exposure, while year-level discrimination is unstable
E52: the vol20>=15% rule flagged 100% of 2022 nights, so 100% severe-gap capture had lift exactly 1. It flagged 84.6%/84.4% in 2020/2023 with lift 1.03x/1.05x; in 2024 it flagged 59.1% but captured 54.5%, lift .92x. Recent meaningful concentration appears in 2025 at 1.38x. Earlier annual lift ranges .56x-4.28x with small counts. Leaving one recent year out preserves high raw capture, but that reflects persistent risk-off exposure rather than stable discrimination. Report exposure and lift; do not shorten Study26 using the 85.3% capture headline.
Links: [[E52|evidenced_by]] · [[F59|refines]] · [[F61|refines]] · [[F60|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E53 — study #29: execution-risk input provenance and reconstruction audit
Hashes the five exact Yahoo/yfinance runtime caches underlying Studies16-32, records queries/sizes/line counts/durable derivatives in a committed manifest, and distinguishes deterministic transforms from repo-only raw-data reconstructability. Artifact: tools/overnight_gap_risk_study.py; manifest: docs/research/data/overnight_gap_input_manifest_2026.json; doc: docs/research/D6_input_provenance_audit.md.
Links: [[E40|refines]] · [[E46|refines]] · [[E52|refines]].
_— captured development@234691a, 2026-07-23_

### F63 — All five execution-study inputs are byte-identified, but a fresh repository clone cannot reconstruct the full vendor sample
E53: current hourly, 5m, daily, 1m, and corporate-action caches all match embedded SHA-256 snapshots. The tool and manifest preserve exact queries, byte sizes, hashes, and lower-timeframe/corporate-action derived audits. However raw vendor bytes remain only in /tmp, and expiring/revisable downloads may not reproduce them later. Thus the analysis transform is deterministic and current bytes are auditable, but the repository alone is not fully self-contained. Any refresh requires a new hash and result diff; do not silently inherit old findings.
Links: [[E53|evidenced_by]] · [[E40|refines]] · [[E46|refines]] · [[E52|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E54 — study #30: volatility-rule capture calibration across gap severity
Measures vol20>=15% capture, lift over exposure-matched random flags, and residual unflagged events for nested TQQQ overnight loss thresholds from .25% to 10%; quantifies the remaining unflagged q01, ES1, and worst gap. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_volatility_gap_severity_calibration.md.
Links: [[F57|refines]] · [[F62|refines]].
_— captured development@234691a, 2026-07-23_

### F64 — Lagged volatility is a catastrophic-severity state, not a precise routine-stop predictor or loss bound
E54: vol20>=15% removes 56.5% of nights. It captures 62.82% of >=.5% losses, only 1.11x lift, but capture/lift rise to 88.61%/1.57x at 4%, 91.38%/1.62x at 6%, and 96.30%/1.70x at 8%. The unflagged tail still has q01 -3.99%, ES1 -5.39%, and worst -10.54%, about -1.05% of account at a 10% position before liquidity. Interpret the rule as broad catastrophic-risk exposure removal; it neither predicts ordinary stop gaps precisely nor caps losses.
Links: [[E54|evidenced_by]] · [[F57|refines]] · [[F62|refines]] · [[F60|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E55 — study #31: TQQQ corporate-action and ex-dividend gap audit
Separates raw-price stop triggers from distribution-inclusive wealth using 21 TQQQ cash distributions and eight splits. Recounts long-history gap thresholds, credits distributions only to positions held before each ex-date, and reruns hold, vol15, and daily-flatten policy accounting. Source action cache is hashed and a durable audit is committed; latest distribution and 2025 split are sponsor-cross-checked. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_corporate_action_gap_audit.md.
Links: [[F50|refines]] · [[F57|refines]] · [[F58|refines]].
_— captured development@234691a, 2026-07-23_

### F65 — Ex-dividend accounting is a real but immaterial correction; it does not explain the overnight tail or mitigation result
E55: adding cash distributions removes only 2 of 1,289 raw >=.5% gap classifications, 2 of 935 >=1% classifications, and none of 484 >=2% or 158 >=4% gaps. No baseline overnight gap stop occurs on a distribution ex-date. Two held positions earn distributions, improving the gap-aware baseline only +.0338pp to -10.1133%; daily-flatten relative benefit becomes +4.3387pp and vol15 +4.0482pp. Raw price remains correct for stop triggering; distribution-inclusive wealth is the corrected performance convention. Every path and decision stays negative/unapproved.
Links: [[E55|evidenced_by]] · [[F50|refines]] · [[F57|refines]] · [[F58|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E56 — study #32: first-hour open source and missing-session-bar audit
Pairs 494 Yahoo first-hour opens with daily-bar opens, audits per-session bar completeness against known early closes, substitutes daily opens only for held-position gap fills, and recomputes after excluding two corrupt sessions. Public historical tables independently check the largest bad daily open. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_session_open_source_audit.md.
Links: [[F50|refines]] · [[F63|refines]].
_— captured development@234691a, 2026-07-23_

### F66 — The hourly cache contains two corrupt partial sessions; daily-open and exclusion sensitivities make the negative path slightly worse
E56: 487 sessions have seven bars and five have valid early-close three bars, but 2026-01-30 has only 09:30/10:30 and 2026-02-02 only 13:30-15:30. Feb2 first-hour proxy $55.625 is an afternoon value versus daily/public open $53.16, a 463.7bp mismatch. Across 494 sessions median absolute open difference is 1.04bp and p95 25.92bp. Substituting daily opens for held-position gap fills changes 18 trades and worsens total/maxDD by .0580pp to -10.2051%/-10.2463%. Excluding both defects and rebuilding worsens them .0879/.0880pp. Median-bars validation is insufficient; audit every session and prefer daily open for this vendor. Tail conclusion stands.
Links: [[E56|evidenced_by]] · [[F50|refines]] · [[F63|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E57 — study #33: consolidated corrected execution ledger
Applies the daily raw open to held-position gap-fill mechanics, credits earned TQQQ distributions separately, measures the correction interaction and defective-session exclusion sensitivity, and reruns hold, vol20>=15%, and daily-flatten policies on one accounting convention. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_corrected_execution_ledger.md.
Links: [[F50|refines]] · [[F58|refines]] · [[F65|refines]] · [[F66|refines]].
_— captured development@234691a, 2026-07-23_

### F67 — The joint corrected baseline remains materially negative; mitigation survives only as an unapproved cost-sensitive risk hypothesis
E57: daily-open plus distribution-inclusive accounting yields -10.1713% total / -10.2126% maxDD for 1,117 live-shaped trades. Excluding the two partial sessions and rebuilding worsens the path to -10.2593%/-10.3005%. Corrected vol20>=15% gives -6.0411%/-6.7539%, removes 21/32 classified gap stops with 66 exits, and has a 62.58bp first-order cost ceiling; daily flatten gives -5.7746%/-6.7518%, removes all 32 with 126 exits, and has a 34.89bp ceiling. Use the joint convention as canonical; descriptive gate passes are not production approval.
Links: [[E57|evidenced_by]] · [[F50|refines]] · [[F58|refines]] · [[F65|refines]] · [[F66|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E58 — study #34: mitigation close-proxy sensitivity
Pairs corrected vol20>=15% and daily-flatten paths under official daily-close versus last-hourly-close exits, holding entries, exit timestamps, exit types, daily-open gap fills, and distribution credits fixed. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_close_proxy_policy_sensitivity.md.
Links: [[F58|refines]] · [[F67|refines]].
_— captured development@234691a, 2026-07-23_

### F68 — Mitigation survives the close-proxy alternative, but shared-vendor agreement is not auction-fill validation
E58: official versus last-hourly close changes corrected total return by only +.0778pp for vol20>=15% and +.0344pp for daily flatten. Median absolute flattened-trade differences are 1.93/1.40bp and p95 10.21/9.09bp; both descriptive gates pass under either proxy. Conservative last-hourly cost ceilings are 61.40bp and 34.62bp per exit. The proxy choice does not drive the result, but neither Yahoo field measures executable MOC cost.
Links: [[E58|evidenced_by]] · [[F58|refines]] · [[F67|refines]] · [[F60|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E59 — study #35: fixed closing-auction evidence protocol
Freezes Nasdaq/IBKR operational facts, required event fields, a fixed intended-event horizon, and rejection rules for any future real closing-auction evidence. Study #43 corrects its original NOCP endpoint: standard-Cross fill versus NOCP is reconciliation, while the 60-event gate measures operational failure. It explicitly preserves MONAD paper-only status. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_closing_auction_evidence_protocol.md.
Links: [[F60|refines]] · [[F68|refines]] · [[F78|refines]].
_— captured development@234691a, 2026-07-23_

### F69 — Real auction-cost approval needs a fixed 60-fill zero-breach trial that MONAD paper cannot provide
<!-- status: superseded; by: F78; reason: data-fixed; at: 2026-07-24 -->
E59: require 60 executed fills, complete order/fill/NOCP records, no rejects or ceiling breaches, and a block-5 one-sided 95% upper mean below the conservative 61.40bp vol15 or 34.62bp daily ceiling. Zero breaches in 60 gives a 4.87% exact one-sided upper breach-rate bound. At observed proxy exit rates this is ~1.79/~.94 years. Nasdaq cutoff/NOII mechanics and IBKR paper limitations make this a separately authorized real-data requirement, never approval to alter the paper-only bot.
Links: [[E59|evidenced_by]] · [[F60|refines]] · [[F68|refines]] · [[F67|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E60 — study #36: QQQ distribution contamination audit for vol20
Hashes 69 QQQ distributions, reconstructs lagged 20-session volatility from distribution-inclusive returns, identifies every 15% threshold flip, and reruns the corrected volatility-flatten policy. Artifact: tools/overnight_gap_risk_study.py; derivative: docs/research/data/qqq_distributions_2010_2026.csv; doc: docs/research/D6_volatility_distribution_audit.md.
Links: [[F57|refines]] · [[F67|refines]] · [[F63|refines]].
_— captured development@234691a, 2026-07-23_

### F70 — QQQ distributions flip five marginal vol15 labels but zero strategy decisions; the mitigation result is not an ex-dividend artifact
E60: across 4,113 sessions, distribution-inclusive QQQ returns change mean vol20 by -.01343pp, with p95 absolute difference .18824pp and max .76546pp. Only five 15% labels flip (four raw-only, one adjusted-only); exposure changes 56.504% to 56.431%, severe-gap capture stays 75.155%, and no flip intersects an active flatten. The corrected policy remains exactly 66 exits, 11 gaps, -6.0411% total, -6.7539% maxDD, and 62.58bp cost ceiling. Use distribution-inclusive returns anyway.
Links: [[E60|evidenced_by]] · [[F57|refines]] · [[F67|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### F71 — The execution program now byte-identifies six inputs, while raw vendor panels remain outside the repository
E60 extends E53 with a sixth hashed runtime input: the 501,193-byte QQQ daily action cache (SHA-256 7969bc74...ecdb94) plus a committed 69-row distribution derivative. All six current caches match. The analysis remains byte-auditable in this environment but not repo-self-contained because raw Yahoo panels live in /tmp.
Links: [[E60|evidenced_by]] · [[F63|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-23_

### E61 — study #37: volatility decision-time and lookahead audit
Recomputes every vol20 state from exactly the 20 QQQ total-return observations ending at t-1, reports threshold margins, and contrasts the feasible policy with an explicit current-close lookahead replay. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_volatility_decision_time_audit.md.
Links: [[F59|refines]] · [[F78|refines]] · [[F70|refines]].
_— captured development@234691a, 2026-07-24_

### F72 — Vol20 is exactly known from t-1 data before the MOC lock; current-close lookahead changes the path and is forbidden
E61: 4,113 manual truncated recomputations match the shifted distribution-inclusive classifier within 2.5e-15. The unshifted current-close variant flips 147 historical and 20 recent labels, despite flagging the same 357 recent nights overall; it produces 65 exits, 12 gaps, -6.2049% total and -7.1522% maxDD versus the feasible path 66/11/-6.0411%/-6.7539%. Lookahead is worse here, but still impossible and invalid. Runtime ingestion timing remains a shadow-logging requirement.
Links: [[E61|evidenced_by]] · [[F59|refines]] · [[F78|refines]] · [[F70|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E62 — study #38: local vol20 threshold robustness
Runs a symmetric, non-selectable 14.00%-16.00% grid in 0.25pp steps under corrected accounting and reports exposure, exits, residual gaps, path metrics, cost ceilings, and the existing descriptive gate. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_local_volatility_threshold_robustness.md.
Links: [[F59|refines]] · [[F70|refines]] · [[F72|refines]].
_— captured development@234691a, 2026-07-24_

### F73 — The vol20 risk-control result sits on a 14%-16% local plateau, not a 15.00% threshold cliff
E62: all nine quarter-point thresholds pass the descriptive gate. Corrected totals range -6.2417% to -5.6813%, maxDD -6.9745% to -6.5014%, exits 61-75, remaining gaps 7-12, and first-order cost ceilings 59.11-65.23bp. Thus small threshold/data perturbations do not reverse the conclusion. The grid is same-sample robustness only; no row may replace the frozen 15% forward hypothesis.
Links: [[E62|evidenced_by]] · [[F59|refines]] · [[F70|refines]] · [[F72|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E63 — study #39: direct mitigation versus opportunity-path decomposition
Applies each flatten rule to the fixed 1,117-trade corrected baseline cohort, then contrasts that direct effect with the normal dynamic one-position rerun and its changed signal opportunity set. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_mitigation_path_decomposition.md.
Links: [[F58|refines]] · [[F67|refines]].
_— captured development@234691a, 2026-07-24_

### F74 — Vol15 benefit is almost entirely direct same-cohort risk removal; daily replacement trades give back part of its benefit
E63: vol15 improves the fixed baseline cohort +4.1299pp versus +4.1302pp dynamically, so 38 dynamic-only and one lost signal contribute only +.0003pp; 99.99% is direct. Daily flatten improves the fixed cohort +5.1691pp but only +4.3967pp dynamically; its 72 new and two lost signals subtract .7724pp. Vol15 therefore does not borrow favorable replacement alpha, while daily exact returns are opportunity-path-dependent. Both remain negative and unapproved.
Links: [[E63|evidenced_by]] · [[F58|refines]] · [[F67|refines]] · [[F73|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E64 — study #40: direct mitigation benefit concentration
Ranks leave-one-out account contributions for every fixed-cohort flatten, reports helpful versus harmful changes, resets the largest 1/3/5/10 events, and attributes changed trades by year. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_mitigation_benefit_concentration.md.
Links: [[F74|refines]].
_— captured development@234691a, 2026-07-24_

### F75 — Vol15 direct benefit is tail-concentrated but survives removing its largest events
E64: 43 of 67 changed vol15 trades improve and 24 worsen; gross trade deltas are +64.39pp/-19.54pp. The largest Jan24-27 2025 event contributes ~.998pp account wealth; removing it retains 75.84% (+3.1321pp) of direct benefit. Removing top five retains 42.75% (+1.7657pp), and top ten 17.27% (+.7134pp). Most net trade benefit occurs in 2025. This supports a repeated tail-loss mechanism but not a stable expected magnitude or shorter forward trial.
Links: [[E64|evidenced_by]] · [[F74|refines]] · [[F60|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E65 — study #41: fixed-cohort direct-effect dependence stress
Aligns corrected fixed-cohort and hold account log returns by session and circular-block bootstraps paired relative wealth at 5/20/60-session dependence lengths; also reports annual effects and direct cost ceilings. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_fixed_cohort_dependence_stress.md.
Links: [[F58|refines]] · [[F74|refines]] · [[F75|refines]].
_— captured development@234691a, 2026-07-24_

### F76 — Corrected fixed-cohort vol15 loss avoidance survives block-5, block-20, and block-60 dependence stress
E65: vol15 fixed-cohort relative wealth is +4.5976%; paired daily-log 95% CIs are [+1.850,+8.135]% at block5, [+1.860,+8.314]% at block20, and [+1.796,+8.297]% at block60. Partial-year effects are positive in 2024/2025/2026 (+.3886/+3.1133/+1.0468%). Direct cost ceiling is 61.64bp. This hardens historical loss avoidance after removing opportunity drift, but cannot cure classifier selection or validate real MOC cost.
Links: [[E65|evidenced_by]] · [[F58|refines]] · [[F74|refines]] · [[F75|refines]] · [[F60|supports]] · [[F78|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E66 — study #42: fixed-cohort flatten intervention outcome anatomy
Measures favorable versus harmful fixed-cohort changes with Wilson/exact-binomial uncertainty and decomposes outcomes by the baseline exit that the early close replaces. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_flatten_intervention_outcomes.md.
Links: [[F74|refines]] · [[F75|refines]] · [[F76|refines]].
_— captured development@234691a, 2026-07-24_

### F77 — Vol15 favors 43 of 67 changed baseline trades by cutting eventual losers and sacrificing eventual targets
E66: vol15 improves 43/67 interventions (64.2%, Wilson95 52.2-74.6%, one-sided p=.0136 vs 50%) with median +50bp. All 21 eventual overnight gap stops, 14 ordinary stops, and 8 ambiguous stops improve; all 24 eventual targets worsen. Daily flatten is only 70/127 favorable (55.1%, Wilson 46.4-63.5%, p=.1435). The mechanism is asymmetric loss avoidance, not precise next-gap prediction.
Links: [[E66|evidenced_by]] · [[F74|refines]] · [[F75|refines]] · [[F76|refines]] · [[F60|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E67 — study #43: closing-auction benchmark identity and cost-endpoint correction
Re-reads Nasdaq Equity 4 Rules 4702/4754, current Nasdaq Closing Cross FAQs, and IBKR MOC/paper/fee documentation; distinguishes a qualifying Closing Cross from the ETP T-WAM fallback; rescales the published per-share fee; and corrects Study #35's fill-versus-NOCP endpoint. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_closing_auction_benchmark_identity.md.
Links: [[F68|refines]] · [[F60|refines]].
_— captured development@234691a, 2026-07-24_

### F78 — Standard Nasdaq MOC fill equals the Cross/NOCP price; the 60-event gate measures operational failure, not fill slippage
E67: under Nasdaq Rules 4702/4754, a standard qualifying MOC executes at the single Closing Cross price, which is the NOCP; fill-minus-published-NOCP is therefore reconciliation, not an independent implementation-shortfall sample. For a Nasdaq-listed ETP with no Cross or less than one round lot, NOCP instead uses a 15:58:00-15:59:55 time-weighted NBBO midpoint, so those events must be separate. At the published $0.0016/share exchange fee, fee scale is only 0.40/0.2667/0.20bp at $40/$60/$80. Sixty intended events with zero rejects/unfilled flattens bounds operational failure below 4.87% one-sided; self-impact remains unidentified because the order helps form the published NOCP.
Links: [[E67|evidenced_by]] · [[F69|supersedes]] · [[F68|refines]] · [[F60|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E68 — study #44: current closing-auction runtime readiness audit
Hashes and statically audits live/trader.py, live/broker.py, live/signals.py, and the trader systemd timer against the corrected auction protocol; directly clock-tests the market-hours guard on a 2026 early-close weekday. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_closing_auction_runtime_readiness.md.
Links: [[F78|builds_on]] · [[F72|refines]].
_— captured development@234691a, 2026-07-24_

### F79 — The current trader is not MOC-ready and its hard-coded 16:00 guard admits post-close jobs on early-close weekdays
E68: the final regular-session cycle is 15:32 ET, nominally 18 minutes before Nasdaq's cancel lock and 23 before its MOC acceptance cutoff. But the live path has no frozen t-1 vol20 policy, MOC constructor, cutoff deadline, exchange-calendar/early-close guard, or NOCP/NOII schema; its close path is a SMART MarketOrder. The weekday 09:30-16:00 guard returns true at 13:32 ET on the 2026 post-Thanksgiving 13:00 close, admitting the 13:32/14:32/15:32 jobs after the exchange close. This blocks readiness and is not authorization to modify protected code.
Links: [[E68|evidenced_by]] · [[F78|supports]] · [[F72|refines]] · [[F60|supports]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E69 — study #45: 2026 closed-session scheduler and duplicate-state audit
Combines Nasdaq's official 2026 holiday calendar with the current weekday 09:32-15:32 scheduler, 09:30-16:00 guard, 120-hour bar-staleness allowance, and cycle-based holding counter to count off-exchange jobs and state-transition exposure. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_exchange_calendar_closed_cycle_audit.md.
Links: [[F79|builds_on]] · [[F66|relates]].
_— captured development@234691a, 2026-07-24_

### F80 — The 2026 weekday-only runtime admits 76 off-exchange-calendar cycles and can count the same bar repeatedly
<!-- status: superseded; by: F81; reason: data-fixed; at: 2026-07-24 -->
E69: Nasdaq lists ten fully closed weekdays and two 13:00 closes in 2026. The current seven-cycle weekday scheduler plus hard-coded 16:00 guard therefore admits 70 jobs on closed holidays and six after early closes. The configured 120-hour bar-staleness window lets prior-session data pass, while an open position's bar_count increments once per admitted cycle with no last-processed-bar idempotency gate: up to seven same-bar increments on a holiday, or three after an early close (two duplicate the final bar). This is deterministic schedule/state exposure, not evidence of 76 orders, and it independently blocks safe runtime readiness.
Links: [[E69|evidenced_by]] · [[F79|refines]] · [[F66|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E70 — study #46: pinned calendar-misfire materiality replay
Enumerates official Nasdaq closed and early-close dates inside the 2024-08 to 2026-07 pinned window, maps each admitted off-calendar scheduler cycle to the causally available TQQQ signal bar, and intersects the cycles with the clean gap-aware one-position path. It also audits actual early-close bar timestamps. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_pinned_calendar_misfire_materiality.md.
Links: [[F79|builds_on]] · [[F66|relates]].
_— captured development@234691a, 2026-07-24_

### F81 — Pinned replay finds 162 off-calendar jobs, 65 baseline-open cycle exposures, and 15 of 15 duplicate early-close jobs
E70: from 2024-08 through 2026-07, official dates produce 21 full-holiday and five early-close weekdays, hence 162 jobs admitted outside the exchange calendar. Reused signals are nonzero on 14/21 holidays and 4/5 early closes. The clean counterfactual path has a position open for 65 admitted cycle slots; nine dates are clean-flat with a nonzero signal (59 frozen-state cycle evaluations, not orders). All five early-close sessions contain three Yahoo bars ending 11:30, so all 15 post-13:00 jobs reuse the final bar already processable at 12:32, correcting F80's generic two-duplicate estimate. No Pi state, broker action, or fill is inferred.
Links: [[E70|evidenced_by]] · [[F80|supersedes]] · [[F79|refines]] · [[F66|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E71 — study #47: sanitized observed holiday-runtime audit
Hashes and audits the committed 2026-06-18 sanitized Pi archive for official closed dates inside its signal-history coverage; groups signal and monitor records by ET minute, checks repeated bars/signals, broker connection failures, trade endpoints, and archive-wide double writes. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_sanitized_holiday_runtime_evidence.md.
Links: [[F81|builds_on]] · [[F79|refines]] · [[F43|relates]].
_— captured development@234691a, 2026-07-24_

### F82 — Sanitized Pi records confirm holiday cycles ran; paper Gateway failure, not a calendar guard, prevented downstream behavior
E71: the archive covers two official closures. Good Friday 2026 logged 8 signal rows over 4 distinct hourly slots, all reusing one prior-session bar with signal +1; Memorial Day logged 14 over all 7 slots, reusing one bar with signal 0. All 22 rows have paired paper-port-7497 connection failures and neither date has a trade entry/exit endpoint. Each observed holiday slot was double-written. Archive-wide, 543 signal rows collapse to 333 minute slots, including 210 double-written slots (13 identical payload, 197 divergent), consistent with duplicate historical invocations/writers but not identifying cause. The current preflight has a duplicate-process check, so do not project that historical concurrency forward; the exchange-calendar gap remains current.
Links: [[E71|evidenced_by]] · [[F81|refines]] · [[F79|refines]] · [[F43|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E72 — study #48: historical duplicate-writer and order-path forensics
Audits paired signal rows, entry monitor events, and trade rows in the committed sanitized Pi archive; measures bar/signal disagreement, long-eligibility changes, duplicate submission success paths, and which local state survives. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_historical_duplicate_writer_forensics.md.
Links: [[F82|refines]] · [[E69|relates]].
_— captured development@234691a, 2026-07-24_

### F83 — Historical duplicate cycles changed decisions and reached the bracket path twice in seven entry minutes
E72: 210 paired minute slots disagree on the final signal 69 times (32.9%) and on long-entry eligibility 58 times (27.6%) under the archived shorts-disabled configuration. The monitor archive has 72 entry events across 65 unique entry minutes; seven minutes contain two success-path events. Archived code calls ib.placeOrder for parent, TP, and stop before each event, so this proves seven extra bracket paths and 21 extra application submission calls. All seven local trade rows retain only the later state. Broker acceptance, fills, and exposure remain unproven without an order/execution ledger.
Links: [[E72|evidenced_by]] · [[F82|refines]] · [[F43|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E73 — study #49: live bar-completion timezone and DST natural-experiment audit
Hashes and audits the current yfinance/live-signal time conversion, builds a fixed-clock host-timezone x vendor-tail decision table, and checks the sanitized paired history against the UK 2026 DST transition and holiday boundaries. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_live_bar_completion_timezone_audit.md.
Links: [[F83|builds_on]] · [[F79|refines]].
_— captured development@234691a, 2026-07-24_

### F84 — UTC-naive bars are compared with host-local time, making live completed-bar selection environment-dependent
E73: fetch_yfinance converts hourly labels to UTC-naive, but live/signals uses local-naive Timestamp.now when the index is naive. A fixed 14:32 UTC case is invariant under UTC; London BST accepts a 14:30 in-progress bar when the vendor tail is present, while New York EDT drops the completed 13:30 bar when that tail is absent. The archived natural experiment matches exactly: two pre-BST regular plus eleven closed-holiday slots agree, while the other 197 pairs differ by the predicted 60/1080/3960/5400 minutes, producing 69 signal and 58 long-eligibility disagreements. The systemd New York TZ shifts the 120h true-age boundary to 124/125h. Current runtime is not ready; no protected change is authorized.
Links: [[E73|evidenced_by]] · [[F83|relates]] · [[F82|refines]] · [[F79|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E74 — study #50: archived incomplete-bar materiality and conservative entry attribution
Reinterprets every sanitized signal row against true UTC bar age, separates paired from single writes, applies a strict cycle-without-ID attribution rule to entry events, and partitions the archive-confirmed local trade rows. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_archived_incomplete_bar_materiality.md.
Links: [[F84|builds_on]] · [[F83|relates]] · [[F43|refines]].
_— captured development@234691a, 2026-07-24_

### F85 — More than half of archived signals and at least 40 of 65 entry minutes used an in-progress hourly bar
E74: true-UTC aging classifies 297/543 signal rows (54.7%) as about two minutes into the hour, including 100/123 single-write rows. A strict join that excludes both-long ambiguity attributes at least 40/65 unique entry minutes (61.5%) and 40/72 entry events (55.6%) to an incomplete information set; all 40 have local trade rows and 33 sit in the archive-confirmed bucket. Those 33 compound +1.4388% versus -1.2166% for the 14-row remainder, a descriptive non-causal partition. The overall verdict stays flat, but archived live PnL is not clean completed-bar validation.
Links: [[E74|evidenced_by]] · [[F84|refines]] · [[F83|relates]] · [[F43|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E75 — study #51: trader singleton and launch-safety audit
Hashes and audits six repository-visible trader launch paths, scopes the preflight, named-unit, scheduler, IBKR-client, broker-position, and SQLite controls, and constructs a falsifiable current-code interleaving that can reach a second bracket path while the first parent remains working but unfilled. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_trader_singleton_launch_safety_audit.md.
Links: [[F83|builds_on]] · [[F84|relates]] · [[F85|relates]].
_— captured development@234691a, 2026-07-24_

### F86 — Managed service startup is safer, but current code does not prove exactly-once trader or per-bar order ownership
E75: only two of six repository-visible launch paths route through the full preflight/named unit; four bypass it, and none holds a cross-process lock or durable symbol+bar+direction intent. pgrep is check-then-exec, max_instances=1 is per scheduler, clientId 1 is disconnected/retried, and SQLite serializes final writes rather than the broker check-to-act sequence. The broker-position guard often fails safe, but a second retry can still proceed while the first parent is working yet unfilled because entry does not inspect working orders or reread local state. --once bypasses market hours and --live contradicts PAPER ONLY. This is a residual reachability proof, not attribution of the seven historical double-entry minutes.
Links: [[E75|evidenced_by]] · [[F83|refines]] · [[F79|refines]] · [[F84|relates]] · [[F85|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E76 — study #52: entry acknowledgement, crash cutpoint, and quote-basis audit
Hashes and audits the current bracket submission/local-state path, maps the TWS/IB acceptance and execution evidence ladder, enumerates crash cutpoints, and reprices the 47-row sanitized project exit-confirmed archive under uniform entry-basis shifts. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_entry_acknowledgement_basis_audit.md.
Links: [[F86|builds_on]] · [[F43|refines]] · [[F85|relates]] · [[E41|relates]].
_— captured development@234691a, 2026-07-24_

### F87 — ENTRY placed proves application submission, not acceptance or fill; fill_basis is a quote
E76: the current entry function makes three placeOrder calls, retains zero returned Trade objects, and performs zero status/fill/open-order checks before persisting the quote-derived basis and emitting local success. A crash after the final transmit but before SQLite can leave a working bracket without local state; startup checks positions, not active orders. The 47-row project exit-confirmed archive compounds +0.204664% on its quote basis and crosses zero at only +0.435020bp uniform adverse entry error. That threshold is sensitivity, not estimated slippage. Study 10's 51-row input is absent, so +1.55% is not numerically revised; its flat verdict stands, but CONFIRMED must mean exit-confirmed rather than fully fill-confirmed.
Links: [[E76|evidenced_by]] · [[F43|refines]] · [[F83|refines]] · [[F86|refines]] · [[F85|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E77 — study #53: unfilled-parent and execution-unverified inferred-closure audit
Hashes and audits the current entry-to-reconcile control flow and the committed sanitized Pi archive; constructs the locally-recorded-but-unfilled parent path, joins inference warnings to trade rows with duplicate-writer deduplication, partitions target_hit provenance, and measures ledger-only materiality. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_unfilled_parent_phantom_trade_audit.md.
Links: [[F87|builds_on]] · [[F86|relates]] · [[E72|relates]] · [[F63|relates]].
_— captured development@234691a, 2026-07-24_

### F88 — Broker-flat plus missing child fill can manufacture a local TP/SL lifecycle; five archived rows are execution-unverified
E77: current code checks IB positions but not active/rejected parent state; if flat and no child fill is retrieved, _infer_bracket_exit has no unknown outcome and closes local state at TP or SL before same-cycle entry evaluation. Thus a locally recorded but economically unfilled parent can become a phantom round trip. The sanitized archive has six warnings joined to five unique target_hit rows (one duplicate warning) and three explicit same-cycle reentries. The five rows compound +5.120432% as a ledger slice and removing their factors changes the 65-row endpoint by 6.595908pp, but the archive cannot distinguish missed real exits from never-filled parents. Classify them execution-unverified. Study 52's 47-row bracket_exit/stop_hit +0.204664% result excludes all five and is unchanged.
Links: [[E77|evidenced_by]] · [[F87|refines]] · [[F86|refines]] · [[F83|refines]] · [[F43|refines]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E78 — study #54: bracket-fill identity, partial aggregation, and Gateway retention audit
Hashes and audits the three current get_bracket_fill recovery tiers and tests, checks the durable state/result identity fields, proves the one-execution price rules are not VWAP aggregation, and relates IB Gateway's since-midnight execution limit to archive timing without asserting historical fills. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_bracket_fill_identity_retention_audit.md.
Links: [[F88|builds_on]] · [[F87|refines]] · [[F63|relates]] · [[E77|relates]] · [[E76|relates]] · [[H33|relates]].
_— captured development@234691a, 2026-07-24_

### F89 — Recovered bracket exits lack durable identity and VWAP; Gateway cannot satisfy the seven-day fallback
E78: current-session matching uses parentId and the last fill of the first child; cache/history tiers accept a child API order ID or parent+1/+2 plus side and positive shares, then return the first match. No tier checks symbol/conId, account, clientId, permId, execId, cumulative quantity, or avgPrice, and state retains none of those fields. A synthetic 60@100 plus 40@101 exit has VWAP 100.40, while current tier rules select 101 (+59.761bp) or 100 (-39.841bp); this is proof of non-aggregation, not estimated historic error. IBKR documents Gateway execution retrieval as since-midnight only, regardless of a seven-day filter; 4/5 archived inferred rows cross a UTC date boundary, consistent with but not proving retention loss. Call recovered prices project-matched, not durably fill-confirmed.
Links: [[E78|evidenced_by]] · [[F88|refines]] · [[F87|refines]] · [[F83|relates]] · [[F51|relates]] · [[F63|relates]] · [[H33|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E79 — study #55: concurrent close idempotency and stale-reader SQLite interleaving
Hashes and audits close_position/finalize_pending_close plus their callers/tests, reproduces a two-connection schedule in a temporary SQLite database where both readers cache one position and sequentially commit two trade rows, relates the May 6 two-warning/one-row archive outcome, and bounds one duplicate factor's ledger effect. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_concurrent_close_idempotency_audit.md.
Links: [[F88|builds_on]] · [[F86|refines]] · [[F83|refines]] · [[F63|relates]] · [[E58|relates]].
_— captured development@234691a, 2026-07-24_

### F90 — SQLite write serialization does not make local close exactly once; duplicate PnL and side effects remain reachable
E79: under the current sqlite3 defaults the connection context manager does not open a transaction and SELECT is outside the implicit DML transaction. A deterministic two-connection schedule lets A and B cache the same position, after which both sequentially INSERT a trade and DELETE/commit; two rows survive because trades has no unique lifecycle key. close_position also returns None for success and no-position, so a losing caller still syncs, alerts, sets exit_action, and can re-enter. The archive's May 6 two warnings/one trade is an observed collapse, not a guarantee. Duplicating its +1.004431% factor would add 1.360114pp to the 65-row endpoint, a ledger sensitivity rather than an exposure counterfactual.
Links: [[E79|evidenced_by]] · [[F88|refines]] · [[F86|refines]] · [[F83|refines]] · [[F81|refines]] · [[F72|relates]] · [[F56|relates]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E80 — study #56: cross-generation close/re-entry identity audit
Hashes and audits the current close/open/caller identity boundary, reproduces a temporary-SQLite cut-point where an old cycle's exit economics are attached to a newer position before that newer row is deleted, and measures which parent/lifecycle identities the sanitized duplicate-entry archive retains. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_cross_generation_close_reentry_audit.md.
Links: [[F90|builds_on]] · [[F89|refines]] · [[F86|refines]] · [[F83|relates]].
_— captured development@234691a, 2026-07-24_

### F91 — An old close can erase a newer re-entry because local lifecycle operations are not generation-safe
E80: a cycle resolves exit evidence from its cached Position, but close_position accepts only return/type/price, independently SELECTs whichever row exists, records that row's metadata, and DELETEs without an identity predicate. The deterministic cut-point maps bracket-100 exit economics onto bracket-200 metadata and deletes bracket 200, leaving local flat after the external re-entry submission. Its synthetic +1.0% record versus -49.5% selected-generation price return is a 50.5pp field-mixing proof, not historical error. The archive cannot confirm or refute the race: zero of 14 success events in seven duplicate-entry minutes and no closed trade retain parent/lifecycle identity. Require a durable lifecycle ID, exact conditional claim/delete, unique close, typed winner, and identity-complete broker ledger.
Links: [[E80|evidenced_by]] · [[F90|refines]] · [[F89|refines]] · [[F86|refines]] · [[F83|refines]] · [[F88|relates]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E81 — study #57: quote-anchored bracket geometry and bar-close sizing audit
Hashes and audits the current quantity, parent-limit, TP/SL, and stored-basis formulas; derives fill-relative geometry at the permitted limit cap; applies penny rounding over 72 archived quote values; and conservatively joins 66 entry events to actionable sizing bars to bound notional drift without asserting fills. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_quote_anchored_bracket_geometry_audit.md.
Links: [[F87|builds_on]] · [[F91|relates]] · [[F89|refines]] · [[F43|relates]].
_— captured development@234691a, 2026-07-24_

### F92 — TQQQ target stop and position labels are quote- and bar-anchored rather than fill-relative
E81: quantity is floored from planned dollars divided by the signal bar close, while parent limit, TP, SL, and stored entry basis use a later pre-submission quote. With current 1.0% target, 0.5% stop, and 0.5% buy-limit offset, the least favorable permitted no-rounding fill geometry is +0.497512%/-0.995025% and reward:risk falls from 2.0 to 0.5. Across 72 archived quote values, rounded medians are +0.497791%/-0.998129%. A strict 66-event sizing join bounds the parent-limit envelope at -141.121 to +382.687bp versus the bar basis; the maximum permitted allocation is about 10.344%-10.383% against a 10% plan. These are bounds, not fill or slippage estimates; actual entries remain absent.
Links: [[E81|evidenced_by]] · [[F87|refines]] · [[F89|refines]] · [[F91|relates]] · [[F43|refines]] · [[F28|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E82 — study #58: partial-fill and force-close quantity safety audit
Hashes and audits parent/local/broker quantity flow, attached-child activation, the three force-close callers, child-only cancellation, cancellation acknowledgement, and tests; constructs signed-quantity counterexamples for partial parents and child fills during pending cancellation; and measures the sanitized archive's missing quantity/status evidence. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_partial_fill_force_close_quantity_audit.md.
Links: [[F92|builds_on]] · [[F91|relates]] · [[F89|refines]] · [[F88|relates]] · [[F86|refines]].
_— captured development@234691a, 2026-07-24_

### F93 — Force-close can turn partial or racing bracket fills into the opposite broker position
E82: local state records requested quantity before any parent fill; reconciliation treats every nonzero broker quantity as normally open; software stop, software take-profit, and time exit all pass the full local quantity to cancel_and_close. Thus a 50/100 long parent fill followed by SELL 100 leaves short 50. IBKR states attached children remain held until complete parent fill, while the adapter cancels children but not a partial parent remainder. It also submits the market close without confirmed child cancellation, so a late child fill can independently overshoot flat. The archive has 72 requested-quantity events but zero partial/remaining/average-fill/cancellation fields, leaving historical frequency unidentified. Require terminal parent/child cancellation, fresh signed broker quantity, residual-sized close, and a post-close broker-flat assertion.
Links: [[E82|evidenced_by]] · [[F92|refines]] · [[F89|refines]] · [[F91|relates]] · [[F88|refines]] · [[F86|refines]] · [[F83|relates]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E83 — study #59: force-close completion, partial execution, VWAP, and timeout audit
Hashes and audits cancel_and_close, its three callers, state deletion, pending-close machinery, and tests; constructs a first-partial-execution residual and two-fill VWAP counterexample; and measures explicit ten-second fill-unavailable events plus missing completion identity in the sanitized archive. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_force_close_completion_vwap_audit.md.
Links: [[F93|builds_on]] · [[F89|refines]] · [[F91|relates]] · [[F88|relates]].
_— captured development@234691a, 2026-07-24_

### F94 — A force close is finalized on the first execution or after a no-fill timeout without proving flatness
E83: cancel_and_close returns when trade.fills first becomes nonempty, omitting filled, remaining, status, and identity, and using the last visible execution component rather than VWAP. Thus a first 60-share execution of SELL 100 lets callers delete a 100-share local position while 40 shares remain long; if both 60@100 and 40@101 are visible, it records 101 instead of VWAP 100.40. After ten seconds with no observed fill, it returns None without cancelling or checking the close order and all callers estimate PnL then delete state. Four of nine archived time exits explicitly logged this missing-fill boundary, but ultimate execution and residual exposure are unidentified. Require cumulative completion, execution VWAP, pending-close retention, and a fresh exact-flat broker check.
Links: [[E83|evidenced_by]] · [[F93|refines]] · [[F89|refines]] · [[F91|relates]] · [[F88|refines]] · [[F86|refines]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E84 — study #60: unresolved-close back-to-back re-entry and old-order collision audit
Hashes and audits force-close fallthrough, the broker-flat successor guard, active-order omissions, and back-to-back tests; constructs an old-child/flat-snapshot/new-parent/late-old-close interleaving; and joins explicit close-timeout warnings to same-cycle entry submissions in the sanitized archive. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_unresolved_close_back_to_back_reentry_audit.md.
Links: [[F94|builds_on]] · [[F93|builds_on]] · [[F91|relates]] · [[F86|refines]].
_— captured development@234691a, 2026-07-24_

### F95 — A broker-flat snapshot cannot safely hand off to a successor while old orders remain nonterminal
E84: software/time force-close paths fall through to same-cycle entry; the successor guard checks net broker position but zero active-order or prior-lifecycle terminal fields. A reachable schedule lets an old child flatten long 100, a new parent buy 100, and the still-working old market SELL erase the new exposure while local state remains long 100. The archive has 32 back-to-back application entries, including two placed about 14 seconds after explicit time-exit fill-unavailable warnings. Those pairs prove the unresolved boundary was crossed, not that an old order remained working or filled late. Require terminal prior orders, reconciled executions, exact flatness, and atomic lifecycle handoff.
Links: [[E84|evidenced_by]] · [[F94|refines]] · [[F93|refines]] · [[F91|refines]] · [[F89|relates]] · [[F88|refines]] · [[F86|refines]] · [[F83|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E85 — study #61: broker account, model, and order-destination scope audit
Hashes and audits account-summary reduction, position lookup, order construction, state/tests, and sanitized identity retention; permutes two synthetic account summaries and opposite-symbol positions to prove callback-order dependence without reading or exposing real account IDs. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_broker_account_scope_audit.md.
Links: [[F95|builds_on]] · [[F93|refines]] · [[F87|relates]] · [[F86|refines]].
_— captured development@234691a, 2026-07-24_

### F96 — Broker account identity is implicit, so multi-account callback order can select sizing capital or position direction
E85: get_account drops account/currency and uses last-row-per-tag values; get_open_position drops account/model/contract identity and returns the first symbol match; bracket and close orders set no account/model; local state retains none. Synthetic 100k/1m account callbacks change 10%-at-$100 sizing from 100 to 1000 shares by row order; if routing targets the smaller account that is conditionally 100% notional. Opposite TQQQ positions likewise report long 100 or short 40 by order. This is dormant when Gateway exposes exactly one account, but the repository cannot establish that because sanitized artifacts correctly omit account IDs. Require one authorized paper account/model identity end to end and fail closed on ambiguity.
Links: [[E85|evidenced_by]] · [[F95|refines]] · [[F93|refines]] · [[F92|relates]] · [[F91|refines]] · [[F87|refines]] · [[F86|refines]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E86 — study #62: duplicate-writer holding-counter materiality reconstruction
Hashes and audits the increment/threshold path, proves with temporary SQLite that two writers preserve two increments for one logical slot, and reconstructs all nine sanitized time-exit intervals from signal-history writes under a strict exact-double attribution rule. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_duplicate_writer_hold_counter_materiality.md.
Links: [[F83|builds_on]] · [[F81|refines]] · [[F95|relates]] · [[F84|relates]].
_— captured development@234691a, 2026-07-24_

### F97 — Historical duplicate writers compressed seven ten-bar time exits into exactly five distinct cycle minutes
E86: bar_count increments once per trader invocation with no completed-bar identity, so SQLite serializes and preserves both increments from two writers in one logical slot. All nine sanitized time exits record bars_held=10; seven map exactly to ten signal-history writes over five minute slots with two writes in every slot, and eight use fewer than ten distinct slots. This proves premature local time-exit triggering relative to ten unique cycles. All nine recorded returns are positive, but the longer-hold PnL sign is unidentified because later TP/SL execution is path-dependent. Require a unique lifecycle+completed-bar conditional transition.
Links: [[E86|evidenced_by]] · [[F83|refines]] · [[F81|refines]] · [[F95|relates]] · [[F90|relates]] · [[F84|relates]] · [[F85|relates]] · [[F43|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E87 — study #63: broker quote-field precedence and staleness audit
Hashes and audits quote selection, pinned ib-insync snapshot/marketPrice semantics, current tests, and sanitized quote observability; constructs prior-close and out-of-spread-last order-geometry counterexamples; and pins exact 15/20-minute TQQQ staleness stress summaries with a durable derivative. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_broker_quote_field_precedence_audit.md.
Links: [[F92|builds_on]] · [[F88|refines]] · [[F87|refines]] · [[F63|relates]].
_— captured development@234691a, 2026-07-24_

### F98 — Quote selection can turn prior-close, out-of-spread last, or delayed data into bracket geometry without executable-price proof
E87: get_tradeable_price selects first-positive last, prior-day close, bid, or ask before ib-insync's spread-aware midpoint; it checks no timestamp, data-type callback, size, spread containment, or halt and explicitly accepts 15-20-minute delayed data. A close=100 with bid/ask 109.90/110.10 yields a long limit 871.935bp below ask; a high last=120 makes the long stop 854.545bp above midpoint. In a pinned recent TQQQ OHLC proxy, 964/3,000 15-minute and 1,080/2,960 20-minute moves exceed the 0.5% offset; prior close differs from hourly-cycle open by over 0.5% in 248/273 cases. These are conditional stress frequencies, not runtime incident rates; three archive overlaps do not identify field/type/age. Require timestamped callback-typed positive-size side-aware live spread evidence and confirmed execution.
Links: [[E87|evidenced_by]] · [[F92|refines]] · [[F88|refines]] · [[F87|refines]] · [[F89|relates]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E88 — study #64: entry snapshot latency and decision-age audit
Hashes and audits the byte-matched current/archived signal-to-mark-to-order call chain, counts repeated blocking snapshot attempts and explicit sleeps, and reconstructs all 72 sanitized application entry-event offsets from the nominal schedule plus conservative same-minute signal bounds. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_entry_snapshot_latency_audit.md.
Links: [[F98|builds_on]] · [[F87|refines]] · [[F83|relates]] · [[F95|relates]].
_— captured development@234691a, 2026-07-24_

### F99 — Entry decisions age through repeated blocking snapshots without a submission deadline or signal revalidation
E88: every entry gets one broker price for account marking and a separate price for bracket construction. Nominal-live success therefore uses at least two blocking snapshots and four explicit sleep seconds; full delayed fallback can issue four snapshots and sleep twelve seconds. The byte-matched archive has 72 application Entry placed events 14.377-62.949 seconds after the :32 anchor (median 20.292; 22 at least 30 seconds, eight at least 40). Seventy join same-minute signal writes with at most 1.966 seconds of duplicate-writer attribution ambiguity; two spill into :33. Total latency includes other broker/application work and the endpoint proves neither acceptance nor fill. Remove/reuse the redundant mark request, impose a decision-to-submit deadline, revalidate after waits, and persist one signal-quote-order-execution clock.
Links: [[E88|evidenced_by]] · [[F98|refines]] · [[F87|refines]] · [[F83|relates]] · [[F95|relates]] · [[F84|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E89 — study #65: market-data provenance label integrity audit
Hashes and traces the scalar broker-price interface through mark resolution, singleton persistence, dashboard rendering, software-risk consumption, tests, and the sanitized account snapshot; constructs indistinguishable nominal-live/delayed inputs and audits missing source-time/type/field evidence. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_market_data_provenance_label_audit.md.
Links: [[F98|builds_on]] · [[F99|relates]] · [[F94|relates]] · [[F87|refines]].
_— captured development@234691a, 2026-07-24_

### F100 — A green live mark is a broker-success label, not evidence of real-time or fresh market data
E89: nominal-live and 15-20-minute delayed broker branches both return only a float, so _resolve_mark_price cannot distinguish them and labels every successful scalar live. State persists that label in an overwritten singleton, the dashboard renders it green and defaults a missing source to live, and the same resolver feeds software stop/take-profit checks. mark_time is local post-resolution time, not source quote time. The sole sanitized snapshot says live but retains no market-data type, selected field, or source timestamp, so historical false-live incidence and any exit association remain unidentified. Require callback-typed, field-level, source-timestamped provenance end to end and default missing identity to unknown.
Links: [[E89|evidenced_by]] · [[F98|refines]] · [[F99|relates]] · [[F94|relates]] · [[F87|refines]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E90 — study #66: software risk-trigger provenance and retained-outcome audit
Hashes and audits the unqualified software stop/take-profit mark gate, joins all six sanitized software-stop trigger events to retained stop exits, measures breach margins, and separates four unique close joins from two later duplicate-writer triggers. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_software_risk_trigger_outcome_audit.md.
Links: [[F100|builds_on]] · [[F94|refines]] · [[F90|relates]] · [[F97|relates]].
_— captured development@234691a, 2026-07-24_

### F101 — Archived software stops corroborate the breach, but two writers triggered again after close
E90: software stop/take-profit logic accepts any non-null resolved mark with no source or age gate. Six archived software-stop events all carry the provenance-unverified live label; four unique events join within 1.1 seconds to retained stop exits and all four execution components remain beyond the stop, so retained prices show no economic false trigger. Two further writers trigger 22-23 seconds after the prior close record; because force-close ordering precedes local close and execution identity/flatness are incomplete, their external outcome is unknown. Gate typed quote provenance, atomically claim lifecycle ownership, and persist close identity plus exact-flat verification.
Links: [[E90|evidenced_by]] · [[F100|refines]] · [[F94|refines]] · [[F90|refines]] · [[F97|relates]] · [[F93|relates]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E91 — study #67: software-risk fallback freshness and prior-close materiality audit
Hashes and audits the broker-to-daily-yfinance-to-bar-close fallback chain and retry timing, then replays a prior-session-close counterfactual across 160 unique archived in-position cycle slots using the pinned full-session hourly cache and sanitized signal/trade records. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_software_risk_fallback_freshness_audit.md.
Links: [[F101|builds_on]] · [[F100|builds_on]] · [[F99|refines]] · [[F98|refines]].
_— captured development@234691a, 2026-07-24_

### F102 — An unchecked daily fallback can reverse intraday software-risk decisions
E91: after broker-price failure, _resolve_mark_price accepts the last daily yfinance close without checking its row date/session/age and labels it delayed; software stop/take-profit accepts it without a source gate. Broker sleeps plus yfinance retry backoff total 20 explicit seconds before request duration, with no decision deadline. Under the explicit prior-session-row counterfactual, 62-65/160 archived trade-cycle slots (38.75%-40.63%) falsely cross the long-stop proxy while archived signal bar close does not; 17/160 (10.63%) falsely cross take-profit. Three stop slots are duplicate-writer ambiguous. Zero actual fallback incidents are retained, so these are conditional exposure bounds, not rates. Exclude daily closes from intraday triggers or require typed row-time freshness and one deadline.
Links: [[E91|evidenced_by]] · [[F101|refines]] · [[F100|refines]] · [[F99|refines]] · [[F98|refines]] · [[F84|relates]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E92 — study #68: duplicate bar-fallback software-trigger divergence audit
Hashes and audits the signal-bar-close fallback and software-risk boundary, reconstructs all archived in-position trade-cycle slots, and identifies paired writer bar values that straddle recorded-basis stops or targets with exact timing and bar identities. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_duplicate_bar_fallback_trigger_divergence.md.
Links: [[F102|builds_on]] · [[F84|builds_on]] · [[F97|refines]] · [[F101|relates]].
_— captured development@234691a, 2026-07-24_

### F103 — Duplicate writers can make opposite bar-fallback stop or take-profit decisions in one cycle
E92: among 167 archived in-position trade-cycle minute slots, 114 contain multiple writer bar-close values. Five paired slots straddle the reconstructed long stop and five straddle take-profit, affecting nine trades; every fork mixes the cycle's in-progress bar with an older bar, nine across session dates. Writer updates are only 0.000125-2.112320 seconds apart. If both reach the final bar-close fallback, one forces close while the other holds, with no atomic lifecycle claim. Zero retained software triggers use last_close, so this is a concrete decision fork rather than an incident claim. Require one completed-bar identity and one atomic lifecycle/cycle owner.
Links: [[E92|evidenced_by]] · [[F102|refines]] · [[F84|refines]] · [[F97|refines]] · [[F101|relates]] · [[F90|relates]] · [[F63|relates]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E93 — study #69: broker-connection exception fallback and missed-risk-cycle audit
Hashes and audits connection retry/exception propagation through broker price, position reconciliation, holding age, and software-risk control flow; classifies all sanitized unhandled connection failures and joins them to local position lifecycles with exact schedule offsets. Artifact: tools/overnight_gap_risk_study.py; doc: docs/research/D6_broker_connection_exception_fallback_audit.md.
Links: [[F102|builds_on]] · [[F103|relates]] · [[F97|refines]] · [[F63|refines]].
_— captured development@234691a, 2026-07-24_

### F104 — Connection refusal bypasses mark fallbacks and aborts open-position risk cycles
E93: _ensure_connected tries four times, sleeps 2+4+6 seconds, and re-raises the original ConnectionRefusedError. get_tradeable_price calls it outside the market-data try and _resolve_mark_price catches only RuntimeError; open-position reconciliation also calls it before holding-age increment and software-risk checks. The archive records 46 unhandled connection failures across 24 slots, 22 paired. Thirty-three events spanning 17 slots occur while three local position lifecycles are open; 12.247-12.628-second schedule offsets corroborate retry exhaustion. Stack location, broker protection, and economic effect remain unidentified. Normalize availability into typed results and persist/reconcile missed risk cycles.
Links: [[E93|evidenced_by]] · [[F102|refines]] · [[F103|relates]] · [[F97|refines]] · [[F84|relates]] · [[F63|refines]] · [[D6|supports]].
_— captured development@234691a, 2026-07-24_

### E94 — public investment intelligence frontier reconnaissance
docs/research/PUBLIC_INVESTMENT_INTELLIGENCE_FRONTIER.md records a primary-source reconnaissance of official public datasets, original return-predictability research, contradictory evidence, replication decay, source clocks, rights constraints, and a preregistered study queue. It separates published precedent from MONAD evidence and ranks branches by public usefulness, point-in-time integrity, falsifiability, data cost, leakage risk, and ability to spawn additional models. This is a program-design experiment, not an empirical alpha result and not study #70.
Links: [[D12|builds_on]] · [[F33|builds_on]].
_— captured development@234691a, 2026-07-24_

### F105 — the highest-leverage free frontier is a point-in-time filing ledger, not another isolated signal
The [[E94]] reconnaissance finds that SEC submissions plus XBRL are the strongest first substrate: official APIs require no authentication, update near real time, expose both narrative and structured facts, and can support filing-delta, rhetoric-number divergence, event, future-fundamental, and market-response models from one reproducible ledger. The finding is about research priority and feasibility, NOT predictive edge. Cross-asset price networks and transparent 52-week/trend anchors rank next as falsifiable baselines. FRED/ALFRED, CFTC, GDELT, and SEC fails-to-deliver data are valuable later sources only under their true vintage/release/publication clocks and redistribution terms. Paid-transcript and historical-options dependencies are deferred. All published effects remain unvalidated priors subject to post-publication decay, multiple-testing correction, and untouched out-of-sample tests.
Links: [[E94|evidenced_by]] · [[D12|refines]] · [[F33|relates]].
_— captured development@234691a, 2026-07-24_

### H44 — OPEN root: point-in-time public intelligence graph can become MONAD's next model factory
Build the shared event/outcome ledger specified by [[E94]]: durable entity/security mappings; source, first-seen, and conservative tradable timestamps; revision/vintage identity; payload hashes; rights metadata; multi-horizon price and future-fundamental labels; and a trial registry. Hypothesis: this substrate will make radical price, filing, news, macro, and positioning ideas cheap to test without letting each model invent its own leaky clock. First gate PT-01: adversarial SEC acceptance/dissemination fixtures plus source-specific tradable-time rules. Pass is exact point-in-time reconstruction and deterministic labels; fail if timestamp or rights provenance cannot be audited.
Links: [[F105|builds_on]] · [[E94|builds_on]] · [[D12|relates]].
_— captured development@234691a, 2026-07-24_

### H45 — OPEN child: filing changes predict future fundamentals or market response beyond numeric and market baselines
FD-00/FD-01. On comparable 10-K/10-Q filings, freeze section-diff, finance-language-change, XBRL-change, and lagged market-context families. Test next-filing revenue, margin, cash flow, leverage, and dilution plus 1/5/20/60-session abnormal return and volatility. Train 2010-2018, select 2019-2022, open 2023+ once. Pass only for corrected, stable incremental OOS information beyond numeric-only, prior-return/volatility, industry-year, length-only, and base-rate models; preserve inactive CIKs, amendments, and delistings. Published filing effects are priors, not evidence.
Links: [[H44|builds_on]] · [[F105|builds_on]].
_— captured development@234691a, 2026-07-24_

### H46 — OPEN child: rhetoric-number divergence predicts deterioration or downside better than raw sentiment
RN-01. Estimate language expected from contemporaneous XBRL results, firm history, section, industry, size, loss status, and prior returns; test the residual tone, uncertainty, emphasis, and narrative-number disagreement against next-period fundamentals and 20/60-session downside/volatility. Begin with mandatory filings, not paid call transcripts. Transparent counts/diffs are the baseline; model outputs need frozen versions and source spans. Kill if document length, boilerplate, firm style, or current performance explains the result, or if a complex language model cannot beat the transparent baseline.
Links: [[H44|builds_on]] · [[H45|builds_on]].
_— captured development@234691a, 2026-07-24_

### H47 — OPEN child: a corrected cross-asset information-flow graph improves own-lag and common-factor forecasts
PN-01. Start with liquid equity, sector, rates, credit, commodity, volatility, dollar, and crypto proxies. Estimate directed return, direction, and volatility edges using lagged/partial correlation and regularized multivariate baselines. Every fold builds its graph on training data only. Require controls for own/market/sector lags, overnight overlap, calendars/time zones, stale or nonsynchronous prices, distributions, pair-lag-horizon FDR, circular-shift placebos, edge half-life, and turnover/cost. Pass only if a frozen later-period graph adds stable calibrated information; a descriptive public flow map may ship earlier with explicit non-predictive labeling.
Links: [[H44|builds_on]] · [[F105|builds_on]].
_— captured development@234691a, 2026-07-24_

### H48 — OPEN child: 52-week and moving-average anchors generalize across equities, ETFs, and BTC
TA-01. Compare price-to-252-session high, BTC 365-day and 252-observation highs, 50/100/200-session and 26/52-week moving averages, 1/3/6/12-month returns, volatility, drawdown, and cross-sectional ranks. Evaluate 1/5/20/60-session return, direction, volatility, and downside with explicit 24/7-versus-exchange alignment. All horizon variants are reported. Pass only if a preregistered representation adds both statistical and calibrated user-facing value beyond past-return-only, volatility-only, and historical-mean baselines across more than one asset class or a mechanism-scoped subset; one lucky BTC horizon fails.
Links: [[H44|builds_on]] · [[F105|builds_on]].
_— captured development@234691a, 2026-07-24_

### H49 — OPEN child: source-clock-correct public events add information beyond single-source baselines
EV-01/NG-00. After the filing ledger, add ALFRED macro vintages, SEC 8-K event codes, CFTC positioning, GDELT entity/event propagation, and SEC fails-to-deliver data one source at a time. Define surprise relative to information available immediately before release, not observation date. Enforce actual release clocks: macro vintages and revisions; CFTC prior-Tuesday positions released Friday; GDELT duplicate/entity/publication audits; delayed FTD publication. Pass each source alone before cross-source models. Kill or defer any feed whose historical timing, entity precision, or public-use rights cannot be reconstructed.
Links: [[H44|builds_on]] · [[F105|builds_on]].
_— captured development@234691a, 2026-07-24_

### H50 — OPEN child: index additions and deletions predict price, liquidity, and reversal outcomes around announcement and effective dates
IDX-01, noted for later and not yet researched. Build a point-in-time history of index membership changes with distinct announcement, publication, close-auction, and effective timestamps. Test abnormal return, volume, spread, closing-auction imbalance, volatility, and 1/5/20/60-session reversal for additions versus deletions. Separate mechanical index-fund demand from information, size/liquidity eligibility changes, concurrent earnings/corporate events, anticipation, and survivorship. Compare against matched eligible non-events and index/sector baselines; freeze index families and event windows before testing. Membership data rights and complete historical candidate universes are a gating dependency.
Links: [[H44|builds_on]] · [[H49|relates]].
_— captured development@234691a, 2026-07-24_

### E95 — PN-00 daily liquid-ETF lead-lag falsification baseline
docs/research/PN00_daily_cross_asset_lead_lag.md + docs/research/data/pn00_daily_lead_lag_summary_2026.json. Fixed before download: 17 adjusted-close ETFs, 240 directed one-session pairs; development through 2015, validation 2016-2020, untouched test 2021-2026-07-23. Compares raw and lagged-252-session-beta SPY-residual graphs; BH-FDR plus 1,000 joint circular-shift family threshold; forecasts against own-lag + SPY-lag with ridge alpha selected only in development; paired 5,000-draw block-20 MSE intervals. Input SHA 21a95207...32; full result SHA 2e812af...d3b. Exploratory vendor-backed pilot, not clone-only reproducible and not study #70.
Links: [[H47|builds_on]] · [[F105|builds_on]].
_— captured development@234691a, 2026-07-24_

### F106 — the corrected daily ETF lead-lag graph is crisis-specific and harms later forecasts
[[E95]]: 54 raw family-wide edges collapse to four after lagged-beta SPY residualization. All four are IWM/HYG/XLF links concentrated in 2007-2009; none keeps its sign through development, validation, and test. The strict graph worsens pooled MSE in validation (-2.10 squared bp, CI [-4.76,+0.69]) and significantly in the 2021-2026 test (-1.85, [-2.88,-0.64]); sign accuracy is unchanged/slightly worse. BH and dense-ridge sensitivities also fail the preregistered validation+test rule: dense test +27.14 has CI [-10.24,+69.37] after validation -16.23. Robust across beta windows 126/252/504 and permutation seeds 0-2 (3-6 strict edges, same unstable core). Rejects a one-day liquid-ETF return graph, NOT monthly industry diffusion, intraday discovery, event-conditioned networks, individual-stock links, nonlinear features, or volatility spillovers. H47 remains open but is narrowed toward event-conditioned or monthly designs.
Links: [[E95|evidenced_by]] · [[H47|refines]] · [[F105|relates]].
_— captured development@234691a, 2026-07-24_

### E96 — FD-00 SEC filing clock and source-contract audit
Official SEC documentation plus real filing fixtures audit the point-in-time contract for the Filing Delta Lab. The fixtures cover premarket acceptance, after-5:30 filing-date rollover, post-close same-date events, weekend rollover amendments, legacy midnight ambiguity, private-to-public release months after acceptance, accession-prefix/issuer-CIK mismatch, and post-acceptance corrections. The audit also freezes source hierarchy, corpus coverage diagnostics, XBRL/text contracts, falsification gates, and a public evidence-card contract. Corpus-scale backfill was not claimed because the SEC rejected this environment's direct automated bulk/API requests.
Links: [[H44|relates]] · [[H45|relates]] · [[F105|relates]].
_— captured development@234691a, 2026-07-24_

### F107 — SEC current discovery surfaces are not a historical truth layer
The FD-00 audit finds that filing date can differ from acceptance date, acceptance is not guaranteed public availability, private-to-public records can become public months after original acceptance, current quarterly indexes can be rebuilt after corrections, accession prefixes can identify filing agents rather than issuers, current ticker mappings are explicitly not guaranteed for accuracy or scope, and filing facts have real context/tag/scaling hazards. Therefore any filing model must use an append-only, accession-scoped ledger with raw payload hashes, dissemination/revision identity, first-seen and conservative tradable clocks, header-role issuer identity, filing-specific XBRL, and time-bounded security mappings. This is a data-integrity finding, not evidence of predictive edge.
Links: [[E96|evidenced_by]] · [[F105|refines]].
_— captured development@234691a, 2026-07-24_

### H51 — OPEN child: filing numeric deltas predict next fundamentals beyond seasonal baselines
FD-NUM. Using only filing-specific, accession-scoped XBRL facts known at the event, test next-filing revenue, margin, cash-flow, leverage, and dilution against prior-value, same-fiscal-quarter, industry-year, size, and market-context baselines. Preserve first-as-filed versus corrected targets and unresolved fact contexts. Pass only for calibrated incremental validation and untouched-test information with stable era/industry coverage; fail on later-filed companyfacts leakage or unstable concept coverage.
Links: [[H45|builds_on]] · [[F107|builds_on]].
_— captured development@234691a, 2026-07-24_

### H52 — OPEN child: amendment anatomy predicts reporting and operating risk
FD-AMEND. Pair each 10-K/A or 10-Q/A to its exact original accession; classify exhibit-only, Part III, tagging-only, narrative, and financial changes; retain both events and amendment lag. Test subsequent restatement, material weakness, late filing, operating deterioration, volatility, and downside against amendment base rates, size, complexity, industry, and original-filing controls. Pass only if a frozen change taxonomy adds OOS information beyond the mere existence and delay of an amendment.
Links: [[H45|builds_on]] · [[F107|builds_on]].
_— captured development@234691a, 2026-07-24_

### H53 — OPEN child: filing-conditioned industry graph predicts related-company outcomes
FD-GRAPH. Condition edges on a new filing rather than searching every trading day: test whether issuer numeric/text surprises update future fundamentals, volatility, or returns of industry, supplier/customer, product, or factor-linked firms before their next filings. Use point-in-time relationship and security mappings, date/firm clustering, market and industry controls, and family-wide correction. Pass only if frozen edges improve untouched outcomes beyond common-event and industry-news baselines.
Links: [[H47|builds_on]] · [[H45|builds_on]] · [[F107|builds_on]].
_— captured development@234691a, 2026-07-24_

### H54 — OPEN child: disclosure and tagging instability predict future reporting failures
FD-QUALITY. Test custom-concept share, tag churn, reconciliation failures, section instability, late filing, control-language change, and parser/data-quality warnings as predictors of amendments, restatements, material weaknesses, volatility, or operating deterioration. Control for filer complexity, industry, size, rule era, and baseline reporting quality. Pass only if transparent quality features survive post-2019 and untouched-test evaluation without treating missing or unparseable rows as good firms.
Links: [[H45|builds_on]] · [[F107|builds_on]].
_— captured development@234691a, 2026-07-24_

### H55 — OPEN child: public Context Web can use a rebuildable SQLite projection plus quarantined suggestions
The existing read-only server rebuilds the 447-node/1,255-edge unified map from versioned Markdown and code metadata on every page load. Preserve that audited source of truth, but export nodes, edges, documents, and FTS5 search rows into a disposable SQLite read model for public browse/search. Put anonymous research proposals in separate suggestion and suggestion_event tables with strict size limits, parameterized statements, rate limiting, moderation states, and append-only review history; never allow a submission to allocate a graph ID, edit RESEARCH_WEB.md, execute SQL, or auto-train a model. A reviewer may convert an accepted proposal into a draft note or pull request. SQLite fits an initial single-host, low-write site, but this environment links SQLite 3.51.0, so do not enable WAL until upgrading to a WAL-reset-bug-fixed build (3.51.3+ or an official backport); use the default rollback journal and a single short-lived writer meanwhile. Graduate the inbox to a client/server database if deployment becomes multi-instance or write-heavy.
Links: [[H44|builds_on]] · [[D12|relates]] · [[H41|relates]] · [[H15|relates]].
_— captured development@234691a, 2026-07-24_

### E97 — IX-00 index-membership source contract and March 2026 event-clock pilot
docs/research/IX00_index_membership_event_lab.md, tools/index_membership_event_pilot.py, and docs/research/data/ix00_sp500_march2026_event_pilot.json audit official S&P, Nasdaq, Russell, and MSCI event clocks, revision structures, transition types, security identity, data access, and redistribution constraints. A fixed March 2026 S&P 500 batch uses announcement date 2026-03-06, conservative first tradable open 2026-03-09, implementation close 2026-03-20, and effective open 2026-03-23. It measures four additions and four deletions versus SPY with adjusted OHLCV, preserves SATS-to-ECHO identity, and retains normalized input SHA 9c88c322...88e. One batch is descriptive; it has no causal control, inference, or predictive-edge claim.
Links: [[H50|builds_on]].
_— captured development@234691a, 2026-07-24_

### F108 — index membership sign is not the flow treatment and effective date is not the implementation clock
IX-00 finds that an honest event row needs public-announcement/first-tradable time, implementation-session close, and effective-session open as separate clocks. The March 2026 S&P release also shows three of four additions migrating from the MidCap 400 and all four deletions migrating to the SmallCap 600, so gross add/delete labels mix offsetting family flows with direct entry/exit. The pilot's additions moved +10.8709% relative to SPY from first tradable open through implementation close versus -3.4614% for deletions, with implementation-session whole-day volume at 8.65x/13.75x prior medians. This is an eight-name descriptive validation, not causal evidence: later continuation and large security-specific moves reject attributing the separation to index demand. The scalable treatment is signed family-wide weight change times indexed capital divided by ex-ante dollar ADV, or a clearly labeled public proxy.
Links: [[E97|evidenced_by]] · [[H50|refines]].
_— captured development@234691a, 2026-07-24_

### H56 — OPEN child: signed net index flow relative to liquidity predicts implementation impact and reversal
IX-FLOW. Reconstruct every affected family weight change and estimate signed indexed-capital demand divided by pre-announcement dollar ADV; begin with transparent transition/size/liquidity proxies and add licensed weights/AUM only under an explicit rights contract. Predict implementation-close impact in the flow direction and prespecified 1/5/20-session reversal, controlling for market, sector, momentum, earnings/news, provider family, batch, and migration type. Pass only if ex-ante pressure has stable sign and untouched-era incremental information with batch-clustered uncertainty; fail if binary membership sign or a simple volume/liquidity baseline matches it.
Links: [[H50|builds_on]] · [[F108|builds_on]].
_— captured development@234691a, 2026-07-24_

### H57 — OPEN child: preliminary-list revision surprise predicts index-event repricing
IX-REVISION. Preserve every Russell preliminary list, scheduled update, lockdown, and final publication as a separate point-in-time event rather than overwriting with final membership. Estimate pre-revision survival probability from frozen public eligibility features, then test whether unexpected additions/deletions at each revision predict announcement response, implementation impact, and reversal beyond final membership sign. Pass only with exact source clocks, reproducible historical candidate universes, strong identity reconciliation, batch-clustered uncertainty, and an untouched later reconstitution; fail if final-only labels, timing ambiguity, or a base-rate probability performs equally well.
Links: [[H50|builds_on]] · [[F108|builds_on]].
_— captured development@234691a, 2026-07-24_

### H58 — OPEN child: discretionary index selection carries information beyond mechanical benchmark demand
IX-SELECTION. Compare S&P committee-selected changes with strongly rule-based Nasdaq/Russell events after matching transition type, flow/liquidity proxy, size, sector, momentum, profitability, earnings/news distance, and methodology era. The preregistered mechanism predicts more announcement-to-implementation continuation for discretionary selections, but more implementation-close reversal for mechanical events conditional on forced flow. Pass only if provider-mechanism interactions generalize across untouched eras and remain after concurrent-event exclusions; fail if one pooled add/delete effect or provider-specific liquidity explains the result.
Links: [[H50|builds_on]] · [[F108|builds_on]] · [[H56|relates]].
_— captured development@234691a, 2026-07-24_

### H59 — OPEN child: closing-auction imbalance mediates index flow impact and post-event reversal
IX-AUCTION. Under a rights-cleared TAQ/NOII contract, test whether signed pre-close imbalance and auction volume relative to ADV mediate the relationship between ex-ante index flow pressure and official-close impact, then whether the transitory component reverses over 1/5/20 sessions. Freeze imbalance observation time and executable latency, distinguish whole-day from auction-only volume, and include spread, volatility, market stress, provider batch, and concurrent news. Pass only if the mediator has the correct sign, adds untouched-era information, and survives realistic cost; daily OHLCV volume spikes cannot pass this hypothesis.
Links: [[H50|builds_on]] · [[F108|builds_on]] · [[H56|builds_on]].
_— captured development@234691a, 2026-07-24_

### E98 — IX-00 exact-clock Nasdaq-100 cross-provider replication
The same event-window tool applies Nasdaq's official 2025 annual reconstitution at exact publication 2025-12-12 20:00 EST, first tradable open 2025-12-15, inferred implementation close 2025-12-19, and effective open 2025-12-22. Six additions and six deletions are measured versus QQQ with the same adjusted OHLCV definitions as E97; normalized input SHA 6761aadc...ee71. The retained derived artifact is docs/research/data/ix00_ndx_december2025_event_replication.json. This is a second descriptive batch without matched controls, causal identification, or p-values.
Links: [[H50|builds_on]] · [[E97|relates]].
_— captured development@234691a, 2026-07-24_

### F109 — the recent index-event directional sign fails cross-provider replication while implementation volume repeats
E98 contradicts the tempting directional reading of E97. Nasdaq additions returned -1.5627% relative to QQQ from first tradable open through implementation close versus -0.6394% for deletions; S&P additions had been +10.8709% versus -3.4614%. Exceptional implementation-session whole-day volume repeats: Nasdaq additions/deletions average 17.14x/8.60x prior 20-day medians after S&P's 8.65x/13.75x. Nasdaq additions then underperform for 1 and 5 sessions but outperform at 20/60 sessions, with large winner dispersion and explicit prior-momentum selection. Across twenty securities in two batches, only the liquidity-demand observation is directionally stable; neither price direction nor reversal is established, and daily volume cannot identify the auction mechanism.
Links: [[E98|evidenced_by]] · [[F108|refines]] · [[H56|relates]] · [[H59|relates]].
_— captured development@234691a, 2026-07-24_

### E99 — IX-00 consecutive vendor-refresh provenance audit
Repeated same-day Yahoo/yfinance 1.2.0 downloads of both retained IX-00 batches produced different exact hashes of the sorted normalized OHLCV panels. The tool therefore preserves exact input hashes without arbitrary rounding and adds a separate decision-level hash over security metrics rounded to five decimals in return units (0.001 percentage point). Two consecutive S&P result hashes both equal ae78900f...2c74 and two Nasdaq result hashes both equal f723b4bf...2e10, while exact input hashes differ. Tests freeze the distinction. No raw vendor panel is committed.
Links: [[E97|builds_on]] · [[E98|builds_on]].
_— captured development@234691a, 2026-07-24_

### F110 — free historical price refreshes are not byte-stable even when IX-00 decisions reproduce
E99 finds that consecutive same-day Yahoo panels for both IX-00 batches have different exact normalized-input SHA-256 values, consistent with provider revision or insignificant adjusted-price float jitter. Arbitrary input rounding also failed to supply a principled stable identity. However, security-level event results hashed at the preregistered 0.001-percentage-point precision reproduce exactly in paired refreshes for both batches. Thus the current artifacts are decision-stable but vendor-backed, not clone-only reproducible. Preserve every exact snapshot hash, report a separate precision-declared result hash, and require retained rights-cleared raw snapshots before corpus-scale claims.
Links: [[E99|evidenced_by]] · [[F109|relates]] · [[F63|relates]].
_— captured development@234691a, 2026-07-24_

### E100 — IX-00 recent Nasdaq annual-panel extension and survivorship gate
The event pilot adds the complete December 2024 Nasdaq-100 batch and attempts December 2022 using official exact 8:00 p.m. announcement clocks, preceding quadruple-witching implementation closes, QQQ-relative adjusted OHLCV, and unchanged horizons. The complete 2024 batch has three additions/deletions; pooled with complete 2025 it yields nine per side. The 2022 official list has 13 security events, but Yahoo supplies only 12 because acquired Splunk is unavailable; the tool records the exclusion and bars 2022 from the complete panel. The December 2023 list is also excluded because Nasdaq revised it after Seagen acquisition news, requiring security-specific revision clocks. Artifacts: ix00_ndx_december2024_event_replication.json, ix00_ndx_december2022_partial_diagnostic.json, and ix00_ndx_recent_complete_panel.json.
Links: [[E98|builds_on]] · [[F110|builds_on]] · [[H57|relates]].
_— captured development@234691a, 2026-07-24_

### F111 — recent complete Nasdaq batches generate a short addition-reversal hypothesis but partial history cannot validate it
E100 pools only the complete 2024 and 2025 annual batches: nine additions versus nine deletions. Additions separate positively at the next tradable open (+2.074 pp add-minus-delete) but do not continue into implementation (-0.375 pp). They underperform deletions by 2.226 pp after one session and 3.167 pp after five; both batches have the same post-implementation sign. Whole-day implementation volume averages 12.87x for additions and 7.26x for deletions. The incomplete 2022 diagnostic has the same five-session sign (-2.794 pp) but is excluded because SPLK is missing. Two complete batches, eighteen securities, prior-winner selection, and no matched controls provide no inference or tradable edge; they only justify freezing IX-REVERSAL for a larger rights-cleared panel.
Links: [[E100|evidenced_by]] · [[F109|refines]] · [[F110|relates]].
_— captured development@234691a, 2026-07-24_

### H60 — OPEN child: predictable Nasdaq additions reverse after implementation conditional on prior-winner selection
IX-REVERSAL. Freeze the 1- and 5-session addition-minus-deletion outcomes before expanding annual Nasdaq reconstitutions. Recover every official security including acquired/delisted names, preserve revisions per security, and match or residualize on pre-announcement momentum, beta, volatility, size, liquidity, sector, earnings/news, and rank/eligibility proxies. Cluster by annual batch and compare against matched near-eligible non-events. Pass only if additions have stable negative post-implementation residuals in an untouched later-era panel after family-wide horizon correction and realistic close/open execution cost; fail if prior-winner mean reversion, one volatile cohort, missing deletions, or a transparent momentum reversal baseline explains it.
Links: [[F111|builds_on]] · [[H59|relates]] · [[H56|relates]].
_— captured development@234691a, 2026-07-24_

### E101 — IX-01 revision-aware Nasdaq event ledger and Context Web projection
A versioned fixture preserves Nasdaq-100 December 2023 knowledge states: r1 published 2023-12-08 20:00 ET contains the original six additions and six deletions; r2 published 2023-12-12 18:00 ET retains those twelve facts and adds TTWO/SGEN after Pfizer acquisition news. tools/research_event_ledger.py validates clocks and identities, builds an atomic STRICT SQLite projection only outside the repository, uses rollback journaling and foreign-key checks, keeps raw documents out, and supports exact as-of queries. ctx serve exposes read-only /events and /api/research-events paths; no public write route exists. The suggestion schema is append-only but quarantined. Artifacts: ix00_ndx_2023_revision_fixture.json and IX01_nasdaq_2023_revision_ledger.md.
Links: [[E100|builds_on]] · [[H55|builds_on]] · [[H57|relates]].
_— captured development@234691a, 2026-07-24_

### F112 — final-only index membership leaks revisions and conflates corporate-action outcomes
The December 2023 Nasdaq-100 case proves two separate data errors. A final table backdates the TTWO addition and SGEN deletion from the Dec 12 update into the Dec 8 initial announcement; correct as-of counts are 12 then 14. It also treats SGEN like a continuing equity even though Pfizer merger consideration converted each share into a $229 cash right on Dec 14. The TTWO diagnostic shows +2.263% QQQ-relative announcement-close-to-first-open, -1.986% first-open-to-implementation, and 9.47x implementation volume, but one event supports no edge. Revision-specific clocks and outcome-type-specific labels are mandatory before pooling.
Links: [[E101|evidenced_by]] · [[F111|refines]] · [[H57|relates]].
_— captured development@234691a, 2026-07-24_

### D13 — versioned fixtures remain authoritative while SQLite is a disposable read projection
For public Context Web research data, commit only small rights-reviewed transformed fixtures and rebuild SQLite outside the repository. The projection may index batches, revisions, event versions, identities, and FTS search, but it is not the source of truth and raw vendor documents or databases are never committed. Use rollback journaling, atomic replacement, foreign-key validation, schema versions, parameterized reads, and no anonymous write endpoint. Keep suggestions in separate append-only tables until a least-privilege moderated writer, rate limits, CSRF protection, and abuse controls exist.
Links: [[E101|evidenced_by]] · [[H55|refines]] · [[D12|relates]].
_— captured development@234691a, 2026-07-24_

### H61 — OPEN child: corporate-action-aware index exits require terminal-value and successor-security labels
IX-CORPORATE-ACTION. Build a rights-cleared outcome layer for index exits caused by cash mergers, stock mergers, spinoffs, bankruptcies, and identifier changes. For cash deals, join the last tradable price and declared consideration; for stock deals, map the successor security and exchange ratio; preserve halt, effective, delisting, and cash-payment clocks. Compare these events only within outcome type, never against ordinary continuing-equity deletions. Pass when inactive securities reconcile to official batches and terminal returns reproduce from independent corporate-action evidence; fail if current-symbol provider coverage silently drops delisted members or if successor mappings remain ambiguous.
Links: [[F112|builds_on]] · [[F110|builds_on]] · [[H57|relates]].
_— captured development@234691a, 2026-07-24_

### E102 — CA-00 corporate-action outcome ledger and eight-case official fixture
CA-00 implements five investor-wealth outcome classes across eight transformed SEC cases: SGEN/ATVI/SPLK/TWTR fixed cash; XLNX-to-AMD stock conversion; GE plus distributed GEV; BBBYQ cancellation pending plan-distribution review; and FB-to-META identity continuity. The tool validates type-specific terms, resolves terminal values through explicit consideration legs, refuses numeric cancellation values without evidence, builds an atomic STRICT SQLite projection only outside the repository, and exposes parameterized read-only Context Web routes. Raw SEC documents and market panels are not committed.
Links: [[F112|builds_on]] · [[E101|builds_on]] · [[H61|builds_on]].
_— captured development@234691a, 2026-07-24_

### F113 — current-symbol free prices fail the predecessor leg exactly where terminal outcomes matter
The CA-00 Yahoo/yfinance 1.2.0 audit resolves 7/12 required price roles and only 3/8 complete actions. SGEN, ATVI, SPLK, and TWTR have no usable pre-effective rows; AMD exists while predecessor XLNX does not. GE/GEV is complete. BBBYQ is missing but the required session appears under BBBY; FB is missing but META exposes both sides of the unchanged-CUSIP ticker transition. Two refreshes reproduce coverage-decision SHA-256 171209f5...b43fcf. Current-symbol data therefore select against acquired predecessors and require alias reconciliation or a rights-cleared inactive-security source before survivorship-free returns.
Links: [[E102|evidenced_by]] · [[F110|refines]] · [[F112|refines]].
_— captured development@234691a, 2026-07-24_

### D14 — corporate-action research continues wealth through typed consideration legs
Adopt an outcome contract rather than a delisting convention. Fixed cash terminates in contractual cash; stock mergers continue through ratio-adjusted successor shares; spinoffs retain the parent and add distributed child shares; ticker changes splice time-bounded symbols for the same security; cancellations remain numerically unresolved until distribution and contingent-right terms are reviewed. Completion filings validate terminal labels but do not replace earlier point-in-time announcement clocks. Backtests must fail closed when any required leg or identity mapping is absent.
Links: [[E102|evidenced_by]] · [[H61|resolves]] · [[D13|relates]].
_— captured development@234691a, 2026-07-24_

### H62 — OPEN child: SEC completion and delisting forms can produce a public corporate-action state machine
<!-- status: superseded; by: D15; reason: refined; at: 2026-07-24 -->
CA-FORM25. Join issuer/acquirer 8-K Items 2.01 and 1.03, exchange Form 25-NSE, issuer Form 25/15, and later distribution evidence by CIK, accession, security identity, and effective clock. Emit append-only states for announced, approved, completed, suspended, delisted, deregistered, paid, and successor-delivered. Pass on a frozen diverse sample only if every state is sourced, revisions never overwrite earlier knowledge, duplicate exchange/issuer filings reconcile, and cash/stock/spinoff/cancellation outcomes match manual review; fail if CIK-only joins conflate share classes or confirmation filings leak backward into prediction clocks.
Links: [[E102|builds_on]] · [[D14|builds_on]] · [[H57|relates]].
_— captured development@234691a, 2026-07-24_

### H63 — OPEN child: inactive-security source benchmark determines the public/private research boundary
CA-PRICE. Freeze the twelve CA-00 price roles and compare candidate sources on inactive-symbol coverage, time-bounded aliases, unadjusted and adjusted OHLCV, last-trade identity, corporate-action conventions, revision stability, API cost, and redistribution rights. Require independent agreement on last tradable sessions and wealth-chain outcomes, not merely nonempty rows. Pass a free public tier only if coverage and rights support reproducible transformed labels; otherwise keep licensed prices private while publishing official terms, source clocks, coverage gaps, and model uncertainty.
Links: [[F113|builds_on]] · [[D14|builds_on]] · [[H61|relates]].
_— captured development@234691a, 2026-07-24_

### E103 — CA-01 point-in-time SEC corporate-action state vector
CA-01 freezes three official action chains with 27 append-only assertions across transaction, listing, reporting, security-rights, bankruptcy, and disclosure dimensions. Every assertion separates effective_on/effective_at from exact EDGAR observed_at; a disposable STRICT SQLite projection supports absolute-time as-of queries and read-only Context Web routes. The Twitter, Activision, and BBBY chains are deliberately selected architecture tests, not population or alpha evidence.
Links: [[E102|builds_on]] · [[H62|resolves]] · [[D13|relates]].
_— captured development@234691a, 2026-07-24_

### F114 — corporate actions are parallel state vectors and source order is not universal
E103 finds that completed, suspended, Form-25-filed, removal-scheduled, rights-converted, and Form-15-filed are distinct states. Twitter NYSE Form 25-NSE preceded the issuer completion 8-K by 11:51:17; Activision issuer completion preceded Nasdaq Form 25-NSE by 26:14; BBBY Form 25 retrospectively confirmed a suspension 68 calendar days later. A single delisted status or effective-date join leaks information and destroys executability/reporting distinctions.
Links: [[E103|evidenced_by]] · [[D15|relates]] · [[F107|relates]].
_— captured development@234691a, 2026-07-24_

### F115 — BBBYQ terminal common-equity value is explicitly zero only after stronger effective-date evidence
The earlier confirmed-plan filing established cancellation but not by itself a numeric terminal value. The September 29 effective-date 8-K, accepted 16:23:06 ET, explicitly says all equity interests were canceled without consideration and have no value. CA-00 now resolves BBBYQ common equity to 0.00 USD while validation still refuses zero when cancellation lacks those issuer-specific facts.
Links: [[E103|evidenced_by]] · [[E102|refines]] · [[D14|refines]].
_— captured development@234691a, 2026-07-24_

### D15 — corporate-action features enter at observation time while schedules and outcomes remain separate
Adopt observed_at as the conservative decision clock. Keep effective dates, exact boundaries, future schedules, requested states, confirmed states, and terminal labels separate. Future schedules never overwrite current effective state, date-only assertions do not invent midnight timing, and post-effective confirmations/outcome labels cannot predict their own transition. EDGAR acceptance is still only a lower-bound infrastructure clock; downstream studies must add dissemination, parsing, and executable-latency assumptions.
Links: [[E103|evidenced_by]] · [[H62|resolves]] · [[D13|relates]].
_— captured development@234691a, 2026-07-24_

### H64 — OPEN child: scale the corporate-action clock to 100 outcome-balanced chains
CA-CLOCK100. Harvest completed, delayed, failed, amended, bankruptcy, spinoff, stock, and cash actions across exchanges. Join issuer and exchange filings, preserve revisions, measure source-order reversals and confirmation lag, and manually audit security identity. Pass only if at least 100 chains materialize without backdating, source clocks reconcile, and missing states are explicit; this is a data gate before event-risk modeling.
Links: [[E103|builds_on]] · [[F114|builds_on]] · [[H57|relates]].
_— captured development@234691a, 2026-07-24_

### H65 — OPEN child: legal completion to investor payment and successor delivery
CA-PAYMENT. Separate legal completion and rights conversion from broker cash receipt, successor-share delivery, fractional cash, and settlement exceptions. Build an auditable lag distribution by consideration type and custodian evidence where rights permit. Pass only if payment/delivery states reconcile independently and portfolio wealth does not assume immediate settlement; fail if evidence is anecdotal or account-specific.
Links: [[E103|builds_on]] · [[D14|builds_on]].
_— captured development@234691a, 2026-07-24_

### H66 — OPEN child: predict merger failure and delay from contemporaneous state revisions
CA-FAIL. On a frozen outcome-balanced panel, model failure and time-to-close using only observed agreement amendments, shareholder and regulatory milestones, litigation, financing conditions, spread, volatility, and issuer rhetoric. Compare transparent survival/logistic baselines before nonlinear models; group by deal, correct the feature family, and hold out a later era. Kill if completion labels leak, amendments are overwritten, or spread and deal age explain the result.
Links: [[E103|builds_on]] · [[H49|relates]] · [[H45|relates]].
_— captured development@234691a, 2026-07-24_

### E104 — CA-CLOCK100 Form 25-NSE population backbone
Official 2023 SEC quarterly master indexes contain 2,282 Form 25-NSE rows but 1,141 unique accessions because each filing is indexed under both the national-exchange filer and subject issuer. The identity-verified census contains 920 issuers; a deterministic 25-per-quarter sample enriches 100 submissions with exact acceptance clocks, security class, rule provision, exchange, reason-exhibit availability, and source hashes. Raw filings remain outside the repository. See docs/research/CA_CLOCK100_form25_population.md and docs/research/data/ca_clock100_form25_2023.json. This is descriptive data infrastructure, not return or alpha evidence.
Links: [[H64|relates]].
_— captured development@234691a, 2026-07-24_

### F116 — SEC Form 25 master rows are dual identities, not independent events
In every 2023 Form 25-NSE accession, the SEC master index contributes one national-exchange row and one subject-issuer row: 2,282 rows collapse to 1,141 filings. The accession-prefix CIK is not a reliable exchange-role resolver for all NYSE-family submissions, so the parser resolves the exchange-name row, retains both identities, and verifies the subject CIK against filing XML. Event studies must use accession-level units and issuer/action clustering.
Links: [[E104|evidenced_by]].
_— captured development@234691a, 2026-07-24_

### F117 — Form 25 acceptance windows and reason coverage are exchange-structured
In the deterministic 100-filing sample, 28/46 Nasdaq filings were accepted post-close while 25/33 NYSE filings were accepted during the regular session. Informative EX-99.25 coverage was 27/46 for Nasdaq versus 33/33 NYSE, 16/16 NYSE Arca, and 4/4 NYSE American. These are sample diagnostics, not population or quality estimates, but they show exchange workflow must be controlled before attributing clock or text effects to outcomes.
Links: [[E104|evidenced_by]].
_— captured development@234691a, 2026-07-24_

### F118 — Form 25-NSE is a mixed security-class frame, not a delisted-stock label
The 100-filing sample contains 31 common-equity removals, 11 debt/note removals, 40 warrant/right/unit or multi-class descriptions containing them, one preferred-equity removal, and 17 other/unknown securities. Rule families and reason exhibits also mix mergers, maturities/redemptions, compliance/distress, and unresolved cases. Any return or outcome study must stratify security rights and terminal wealth before pooling.
Links: [[E104|evidenced_by]] · [[F115|builds_on]] · [[H61|relates]].
_— captured development@234691a, 2026-07-24_

### H67 — CA-CLOCK100B: expand the filing backbone into observation-ordered action chains
CA-CLOCK100B. Start with the 31 common-equity filings in the frozen sample, then extend the deterministic frame until 100 outcome-aware chains exist. Join only point-in-time issuer 8-K, amendment, merger-completion, bankruptcy-effectiveness, rights-conversion, and Form 15 assertions; retain missing sources and source-order reversals. Freeze completed, delayed, failed, bankruptcy, and unresolved strata before prices. Pass when at least 100 outcome-aware chains are materialized without backdating and manual identity audits pass; this remains a data gate before event-risk modeling.
Links: [[E104|builds_on]] · [[F116|builds_on]] · [[F117|builds_on]] · [[F118|builds_on]] · [[H64|refines]] · [[H65|relates]] · [[H66|relates]].
_— captured development@234691a, 2026-07-24_

### E105 — CA-CLOCK100B issuer and exchange sequence join
Six adjacent SEC quarterly indexes join 31 common-equity Form 25 seeds to 259 nearby candidate filings. A frozen label-blind selector retains 80 content-review sources across 26 chains; 22 have a material issuer-source candidate and 19 are within 36 hours of Form 25. Exact acceptance clocks and source hashes are preserved; raw documents remain outside the repository and all outcome labels stay unreviewed. See docs/research/CA_CLOCK100B_action_chain_join.md.
Links: [[E104|builds_on]] · [[H67|relates]].
_— captured development@234691a, 2026-07-24_

### F119 — Corporate-action issuer and exchange source order reverses in both directions
Among 19 CA-CLOCK100B chains with a material issuer-source candidate within 36 hours of Form 25, the issuer source leads in 12 and the exchange filing leads in seven. Manual examples confirm both directions: Myovant issuer 8-K leads by 4:00:08 and New Relic by 24:47; Reata Form 25 leads its issuer 8-K by 8:04:22 and Fiesta by 3:11:44. One filing date or fixed source precedence would backdate information.
Links: [[E105|evidenced_by]] · [[F114|refines]] · [[D15|builds_on]] · [[H67|relates]] · [[H64|relates]] · [[H61|relates]].
_— captured development@234691a, 2026-07-24_

### F120 — Fund exits require a separate disclosure-form pipeline
All five CA-CLOCK100B seed chains with no relevant filing in the frozen 60-day-before/30-day-after corporate form search are funds: three Nuveen funds, Strategy Shares, and Virtus Stone Harbor. Two other fund seeds contribute N-CSRS. Missingness is economically structured, not a random scrape failure; widening the window would hide the need for N-CSR/N-CSRS, N-CEN, proxy, liquidation-plan, exchange-notice, and sponsor-source clocks.
Links: [[E105|evidenced_by]] · [[F118|refines]] · [[H61|relates]].
_— captured development@234691a, 2026-07-24_

### F121 — Corporate-action phrase extraction is review routing, not an outcome label
The 80 CA-CLOCK100B content sources contain material phrase families, but submissions bundle merger agreements, historical transactions, par values, bids, option terms, and boilerplate. A dollar amount near per-share text is not necessarily final consideration. The evidence manifest therefore retains hashes, phrase flags, and unvalidated candidates while forcing outcome_status=unreviewed; content-level manual evidence and abstention remain mandatory.
Links: [[E105|evidenced_by]] · [[F116|builds_on]] · [[H64|relates]] · [[H61|relates]] · [[E102|relates]].
_— captured development@234691a, 2026-07-24_

### H68 — CA-CLOCK100C reviewed outcome ledger across 100 action chains
Extend CA-CLOCK100B to at least 100 manually reviewed chains stratified across cash, stock/successor, contingent value, fund liquidation, bankruptcy, listing transfer, failed/delayed, and unresolved outcomes. Every label must cite content-level official evidence and accepted-at clock; preserve amendments, missing states, and source order. Apply CA-00 terminal-wealth legs and CA-01 parallel dimensions. Pass only when independent identity/terms audits reproduce all labels and abstentions.
Links: [[E105|builds_on]] · [[F119|builds_on]] · [[F120|builds_on]] · [[F121|builds_on]] · [[H64|refines]] · [[H65|relates]] · [[H66|relates]] · [[E102|relates]] · [[H67|refines]].
_— captured development@234691a, 2026-07-24_

### E106 — CA-CLOCK100C exact cash-right promotion benchmark
Twelve CA-CLOCK100B chains are promoted through manual content review to exact fixed-cash holder-conversion labels. Every row carries USD cash per share, exact issuer and exchange acceptance clocks, official source URL and SHA-256, and predictive_for_outcome=false. The seed spans $2.33-$172.50 per share and splits six issuer-first/six exchange-first. It is a reviewed parser/clock benchmark, not an outcome-balanced panel or return study. See docs/research/CA_CLOCK100C_reviewed_cash_seed.md.
Links: [[E105|builds_on]] · [[F121|builds_on]] · [[H68|relates]].
_— captured development@234691a, 2026-07-24_

### F122 — Manual holder-conversion labels retain dual source precedence
The 12 manually reviewed fixed-cash chains split exactly six issuer-source-before-Form-25 and six exchange-before-issuer. Eleven are within 36 hours and split six/five; Sumo completion evidence arrives more than three days after Form 25. Selection targeted unambiguous cash-right evidence, not source order, but remains a convenience seed. Fixed source precedence or date-only joins are invalid; no population frequency or price effect is claimed.
Links: [[E106|evidenced_by]] · [[F119|refines]] · [[D15|builds_on]].
_— captured development@234691a, 2026-07-24_

### H69 — CA-NONCASH review successor contingent bankruptcy and fund exits
Extend the reviewed promotion contract beyond the 12 easy fixed-cash chains. First batch: CRH, Ambrx, and Incannex successor or redomiciliation rights; Pardes fixed-plus-CVR; Venator and RVL bankruptcy with unresolved versus explicit cancellation; five structurally missing fund exits through a fund-specific source graph. Require exact legs, currency or ratio, contingencies, clocks, hashes, and explicit abstention. These strata are prerequisites for H68's 100-chain panel.
Links: [[E106|builds_on]] · [[F120|builds_on]] · [[F122|builds_on]] · [[H68|refines]] · [[H65|relates]] · [[H61|relates]].
_— captured development@234691a, 2026-07-24_

### E107 — CA-NONCASH rights-aware promotion benchmark
Six CA-CLOCK100B chains are manually promoted beyond fixed cash: three successor-equity conversions, one USD 2.13 plus non-tradeable CVR conversion, one bankruptcy with explicit zero recovery, and one bankruptcy unresolved at the selected source. Each row retains exact rights, acceptance clock, source URL and SHA-256, and predictive_for_outcome=false. Source order is four issuer-first and two exchange-first. See docs/research/CA_NONCASH_reviewed_seed.md.
Links: [[E106|builds_on]] · [[H69|relates]].
_— captured development@234691a, 2026-07-24_

### F123 — Bankruptcy and delisting do not imply zero terminal wealth
The RVL source explicitly states ordinary holders recover nothing, supporting USD 0.00. The Venator source establishes Chapter 11 and possible cancellation but not final holder recovery, so terminal value remains null. The promotion validator rejects an invented zero for Venator. Terminal wealth therefore requires rights-specific effective evidence, not a bankruptcy, cancellation, suspension, or Form 25 status alone.
Links: [[E107|evidenced_by]] · [[F115|builds_on]] · [[H69|refines]].
_— captured development@234691a, 2026-07-24_

### F124 — Corporate-action clocks use the earliest fact-establishing source
CRH has multiple nearby 6-K reports, but the 2023-09-25 06:43:16 ET filing already establishes the ADS termination and one-for-one ordinary-share exchange. A later duplicate report cannot define the information clock. The reviewed pipeline binds the outcome to the earliest harvested accession whose content proves the rights transition and validates its hash.
Links: [[E107|evidenced_by]] · [[D15|builds_on]] · [[F121|refines]].
_— captured development@234691a, 2026-07-24_

### E108 — CA-FUND five-chain rights recovery
All five CA-CLOCK100B fund chains with zero corporate-form candidates are manually recovered: NKG, NSL, and EDI convert into successor funds at exact ratios; NIQ pays USD 12.4082 plus one non-transferable liquidating-trust unit initially valued at USD 0.5768; NZRO schedules cash equal to NAV but the selected source does not establish amount or payment. Exact accessions, acceptance seconds, hashes, and source markers are validated. See docs/research/CA_FUND_reviewed_seed.md.
Links: [[E107|builds_on]] · [[H69|relates]].
_— captured development@234691a, 2026-07-24_

### F125 — Fund exits require series-aware rights and source graphs
The five missing corporate-form chains resolve through three exchange reason exhibits, one issuer N-CSR, and one Form 497. The resulting rights are NAV-ratio successor shares, cash plus an illiquid trust unit, and scheduled cash at future NAV. Target-only 8-K/6-K discovery cannot represent series identity, acquiring-fund CIKs, liquidation legs, or payment clocks.
Links: [[E108|evidenced_by]] · [[F120|refines]] · [[H69|refines]].
_— captured development@234691a, 2026-07-24_

### F126 — Official exchange exhibits can contain claim-level contradictions
NKG's NYSE exhibit says replacement rights arose and trading was suspended on April 17, 2023, but its merger-effective sentence says April 17, 2027. The 0.85425383 successor ratio is clear while the legal-date text conflicts. Official provenance does not remove the need for claim-level validation, contradiction flags, and stronger-source reconciliation.
Links: [[E108|evidenced_by]] · [[D15|builds_on]] · [[F124|relates]].
_— captured development@234691a, 2026-07-24_

### H70 — CA-FAILFRAME freeze failed delayed and amended action candidates
Build the negative and censored side of the corporate-action panel before any prediction. Start from contemporaneous merger, tender, liquidation, bankruptcy, and exchange notices; preserve amendments and deadline extensions; distinguish failed, delayed, pending, completed, and right-censored actions. Pass only with content-level official evidence, observation clocks, identity audits, and frozen sampling independent of outcome availability.
Links: [[E108|builds_on]] · [[H66|refines]] · [[H68|refines]] · [[F123|relates]].
_— captured development@234691a, 2026-07-24_

### E109 — CA-FAILFRAME 2023 mutual-termination review seed
One frozen SEC full-text query yields 31 document hits, 23 unique submissions, and 14 unique content-reviewed in-year merger terminations after removing five false or wrong-period matches and four counterparty or amendment duplicates. Exact accessions, acceptance clocks, hashes, reason families, and termination terms are retained. The query is outcome-conditioned and is not a failure population. See docs/research/CA_FAILFRAME_termination_seed.md.
Links: [[E108|builds_on]] · [[H70|relates]].
_— captured development@234691a, 2026-07-24_

### F127 — SEC search documents submissions and deals are different units
CA-FAILFRAME collapses 31 SEC document hits to 23 submissions and 14 unique 2023 deal terminations. Counterparty filings, an amendment, historical events, and nearby non-merger terminations explain the gaps. Event studies and models must cluster by deal chain and content-review event identity; search-hit or accession counts are not outcome counts.
Links: [[E109|evidenced_by]] · [[F116|builds_on]] · [[H70|refines]].
_— captured development@234691a, 2026-07-24_

### F128 — Failure labels have delayed clocks and non-shareholder cash legs
Only seven of 14 primary termination sources are accepted on the date-only event date; seven arrive one to five calendar days later. Termination economics also vary: Adobe USD 1 billion, First Horizon USD 200 million plus USD 25 million reimbursement, Amedisys USD 106 million, and Great Ajax cash plus a stock purchase. These are company/deal transfers, not direct per-share consideration, and cannot be used before source acceptance or added to holder wealth without separate evidence.
Links: [[E109|evidenced_by]] · [[D15|builds_on]] · [[F121|relates]].
_— captured development@234691a, 2026-07-24_

### H71 — CA-ANNOUNCE build an announcement-time censored deal cohort
Freeze a cohort from contemporaneous deal announcements rather than known failures. Preserve parties, terms, outside dates, conditions, revisions, votes, regulatory milestones, competing bids, litigation, completion, termination, and a fixed right-censor date. Include unresolved deals, group all filings by deal, and time-split before transparent survival or logistic baselines. This is the minimum honest frame for public deal-risk prediction.
Links: [[E109|builds_on]] · [[H70|refines]] · [[H66|refines]] · [[F127|builds_on]].
_— captured development@234691a, 2026-07-24_

### E110 — CA-ANNOUNCE deal-risk literature and model blueprint
Classical merger-arbitrage research identifies nonlinear crash exposure and completion-risk premia. A July 2026 ICML paper reports a three-outcome long-context forecaster beating calibrated market-implied and XGBoost baselines on 404 held-out large deals, but its proprietary enriched corpus is not replicated here. CA-ANNOUNCE translates the literature into a public SEC-only cohort, baseline, leakage, calibration, and product contract. See docs/research/CA_ANNOUNCE_model_blueprint.md.
Links: [[E109|builds_on]] · [[H71|relates]].
_— captured development@234691a, 2026-07-24_

### F129 — Deal failure must separate higher bids from negative termination
A binary completion label misclassifies holder outcomes. CA-FAILFRAME's Amedisys/Option Care deal terminated because Amedisys moved to a competing UnitedHealth agreement, unlike regulatory or deadline failures with no better bid. The reviewed literature independently uses close as announced, higher-bid displacement, and negative termination, plus time to resolution.
Links: [[E110|evidenced_by]] · [[E109|builds_on]] · [[H71|refines]].
_— captured development@234691a, 2026-07-24_

### D16 — Deal-risk models must beat calibrated spread on grouped chronological forecasts
Adopt an announcement-time, right-censored cohort and a strict baseline ladder: market-implied probability, multinomial logistic and cause-specific survival, then boosted trees, then evidence-constrained language models. Score Brier, log loss, calibration, and time-dependent survival metrics on deal-grouped chronological splits. Open-web retrieval and post-cutoff model knowledge are barred from backtests; unresolved deals remain censored.
Links: [[E110|evidenced_by]] · [[H71|resolves]] · [[F129|builds_on]] · [[D15|builds_on]].
_— captured development@234691a, 2026-07-24_

### H72 — CA-RHETORIC test filing-language revisions after structured deal baselines
For announcement-time deals, convert each new filing into a point-in-time delta against the previous issuer statement: closing-window changes, certainty and condition language, regulatory scope, financing, litigation, board recommendation, and explicit unknowns. Test whether structured and embedding deltas improve calibrated spread plus survival baselines out of sample. Kill if gains depend on future pages, boilerplate, deal leakage, or hindsight-selected phrases.
Links: [[D16|builds_on]] · [[H71|builds_on]] · [[F124|relates]] · [[F128|relates]].
_— captured development@234691a, 2026-07-24_

### E111 — CA-ANNOUNCE announcement-forward cohort, baselines, and evaluator
First concrete build under H71/D16: an offline, stdlib-only lab (tools/ca_announce_cohort_lab.py) plus a frozen 11-deal 2023 announcement-forward cohort (docs/research/data/ca_announce_cohort_2023.json). Implements the market-implied benchmark, the transparent baseline ladder (base-rate, cause-specific competing-risks survival via Aalen-Johansen, multinomial logistic), and a deal-clustered scoring harness (multiclass/class-balanced Brier, log loss, calibration, discrimination, time-to-resolution, economic regret, bootstrap CIs) reported versus the calibrated market-implied. Leave-one-deal-out grouping; leakage guard and no-fabricated-provenance enforced in code and tested; selfcheck validates every estimator on synthetic ground-truth. See docs/research/CA_ANNOUNCE_cohort_evaluation.md.
Links: [[E110|builds_on]] · [[H71|relates]] · [[D16|relates]].
_— captured claude/research-continuation-ca1242@8efe267, 2026-07-24_

### F130 — No transparent baseline beats calibrated market-implied on the frozen deal cohort; the evaluation architecture is the deliverable
On the 11-deal 2023 announcement-forward cohort, at the default 2025-06-30 horizon (10 observed: 8 close, 1 higher-bid displacement, 1 negative termination; 1 censored), the market-implied benchmark has the lowest multiclass Brier (0.31) and log loss (0.57); base-rate, deal-age competing-risks survival, and multinomial logistic all score worse, and deal-clustered 95% bootstrap CIs (market Brier ~[0.00,0.68]) render the models statistically inseparable. This is the expected D16 result, not an alpha claim: the market-implied inputs are illustrative proxies (CA-00 F113: free current-symbol providers miss the predecessor leg) and N is tiny by design. The real, model-free output is the competing-risks cumulative incidence (90.9% close / 9.1% higher-bid at the 2024-03-31 horizon). A real 'beats calibrated spread' claim is gated on a network-fetched provenance-and-price freeze plus a larger cohort.
Links: [[E111|evidenced_by]] · [[D16|relates]] · [[F22|relates]] · [[F129|builds_on]].
_— captured claude/research-continuation-ca1242@8efe267, 2026-07-24_

### F131 — Deal-risk integrity can be enforced in code: outcome-leakage guard plus no-fabricated-provenance, with the three-class taxonomy load-bearing
The CA-ANNOUNCE lab enforces two integrity properties as tested code, not prose. (1) No look-ahead: point_in_time_features reads a public_view with ground_truth and outcome-bearing provenance stripped, and a test mutates only the terminal outcome and asserts the feature vector is unchanged; every market_implied.as_of is >= announcement; predictions are leave-one-deal-out so no deal is in its own fold. (2) No fabricated provenance: each terminal fact is either frozen_upstream (a real accession cross-checked in a committed sibling fixture -- Seagen/Pfizer 0001193125-23-294930 and Splunk/Cisco 0001193125-24-070175 from CA-00, Amedisys/Option Care termination 0001104659-23-074547 from CA-FAILFRAME) or public_record_unverified_offline with a needs_freeze list; the validator rejects an unverified fact that carries an accession. The three-class taxonomy is load-bearing (F129): Amedisys/Option Care is higher_bid_displacement (holders gained via the Optum bid), the opposite holder outcome to Capri/Tapestry's negative termination, though a binary completed? label would score them identically.
Links: [[E111|evidenced_by]] · [[F129|builds_on]] · [[F127|builds_on]] · [[D13|relates]].
_— captured claude/research-continuation-ca1242@8efe267, 2026-07-24_

### F132 — Deal-risk evaluation is sample-size-bound: answering D16 needs hundreds-to-thousands of deals, and N=11 detects nothing
A Monte-Carlo design analysis over the deal-clustered one-sided Brier test (tools/ca_announce_cohort_lab.py power; DGP: true completion prob Beta(8,2), market observes logit(p)+N(0,0.6), a model cuts that noise by a fraction 'skill') shows the binding constraint is cohort size, not model sophistication. The test is calibrated -- false-positive rate ~0.05 at skill=0 across all N -- so the low power is the sample size. To reach 80% power: ~800 deals for a perfect model (skill 1.0), ~1600 for skill 0.5, ~3200 for skill 0.3, and >3200 for smaller edges; at N=11 no plausible advantage is detectable (power ~ the 0.05 FPR). Because each deal contributes one high-variance binary outcome, the simulated Brier gaps are small (0.003-0.016), in the ballpark of -- if smaller than -- the ICML baseline the blueprint cites (0.199 vs 0.151 = 0.048 gap); the exact N* scales with how much worse the real market-implied is than the best model. This reorders the CA-ANNOUNCE roadmap: scale the cohort to the hundreds BEFORE chasing a better model, mirroring the ICML paper's 404 held-out deals and this project's own F18 (significance ~3x oversold).
Links: [[E111|evidenced_by]] · [[D16|relates]] · [[H71|refines]] · [[F18|relates]].
_— captured claude/research-continuation-ca1242@5710d4d, 2026-07-24_

### E112 — EPI-00 epistemic audit of the research web (git archaeology + revision hazard + structural risk)
Turns the project's own apparatus (censoring, exposure, exact intervals, power) on RESEARCH_WEB.md itself. tools/epistemic_audit_lab.py replays the web across every commit touching it, dates each node's birth/death preferring note.py's own capture and 'at:' stamps over git, classifies supersessions as in_vivo / truncated_unknown / backfill, computes an exposure-weighted revision hazard with exact Poisson intervals, builds the typed-reliance dependency graph (cue-classifying untyped links the way ctx.py does), ranks structural risk as blast-radius x evidence-linkage x staleness, and checks schema integrity. Stdlib-only, offline, 51 tests. A four-lens adversarial review materially corrected v1 (see F134). See docs/research/EPI00_epistemic_audit.md.
Links: [[F27|relates]] · [[D12|relates]].
_— captured claude/research-continuation-ca1242@8d685fb, 2026-07-24_

### F133 — The web's supersession count is not a belief-revision rate, and the project still cannot measure its own error rate
Of 331 nodes, 7 carry tombstones (naive 2.1%), but decomposed by observability only 2 are directly observed revisions: F15 (lived 11 days, reversed by F22) and F69 (lived 1 day, superseded by F78, recoverable only from note.py's own stamps because git collapses both into one commit). Three (F3/F4/F8) are truncated_unknown - tombstoned in the first observable commit, so their birth AND refutation precede the window - and 2 (F80/H62) are backfill recorded already dead. Excluding both unobservable classes from numerator and denominator gives 3845 node-days and 2 events: hazard 5.20e-4/node-day, P(revised in 365d) = 17.3% with exact-Poisson 95% CI [2.3%, 49.6%]; treating the truncated nodes as real revisions instead gives 37.8%. So the honest headline is a bracket of roughly 17-38% with a CI spanning 2-50% - i.e. UNKNOWN. 44% of nodes (145/331) have zero days of exposure and the median node age is 0 days, so the web's apparent stability is mostly its youth. Every rate is a LOWER bound on being wrong because supersession is detected by effort, not by nature.
Links: [[E112|evidenced_by]] · [[F18|relates]] · [[F132|relates]].
_— captured claude/research-continuation-ca1242@8d685fb, 2026-07-24_

### F134 — EPI-00's own v1 headline was overturned by adversarial review — the load-bearing, least-verified claims are the ones that break
The first version of the epistemic audit claimed 'exactly one belief has ever been observed to be born, live, and be revised.' A four-lens adversarial review (statistical / graph-schema / archaeology / overclaim) overturned it via three load-bearing defects. (1) This checkout is a SHALLOW CLONE grafted at exactly the commit v1 called 'commit 0'; RESEARCH_WEB.md itself cites commits (9b4648e, 54e6637) absent from the clone, so the whole observation window was a checkout artifact presented as project history. (2) Left-truncation was misread as bookkeeping: v1 labelled any node tombstoned in its birth commit 'never a live belief', but F3/F4/F8 were the project's headline QQQ claims that a live bot traded on, refuted 2026-06-19 per the web's own preamble - before the first observable commit - so their status is unobservable, not 'never'. (3) The git clock is coarser than note.py's stamps, which disagree for 47 nodes; using the web's own stamps recovers F69 as a real revision. Two fairness defects also fell: F7 was penalised for an untyped [[E6]] link although SCHEMA 5 cue-classifies 'Source:' as evidenced_by (ctx.py agrees), and the label 'no Experiment reachable' asserted a reachability test the code never computed (F17 reaches E9 in one hop and is corroborated by F19). v2 detects shallow clones, adds a truncated_unknown class with a sensitivity bracket, ports the cue classifier, and renames the evidence levels. The episode instantiates the study's own thesis: the claims that were most load-bearing and least verified are the ones that broke.
Links: [[E112|evidenced_by]] · [[F133|refines]] · [[F32|relates]].
_— captured claude/research-continuation-ca1242@8d685fb, 2026-07-24_

### F135 — Only the typed reliance graph has a hierarchy, and F17 is the web's highest-leverage unlinked claim
Following all 1155 citation edges, the transitive closure of almost any node reaches 316 of 331 - the untyped citation graph is one mutually-referential blob in which 'what depends on what' is meaningless. Restricting to SCHEMA's four reliance edges (relies_on/supports/refines/builds_on, defined as pointing to PRIOR nodes) yields a genuine near-DAG: concrete support for the schema's warning that overuse of 'relates' is a typing smell, since typed edges are what make the web traversable at all. Two cycles survive, D6<->F24 and D6<->F25 (the go/no-go decision and its own confirmations are mutually load-bearing); SCHEMA 6 does not enforce acyclicity so ctx --lint cannot catch them. Ranking by blast-radius x evidence-linkage x staleness, F17 ('THE EXIT IS THE ARCHITECTURAL FLAW') is the highest-leverage edit in the web: 148 nodes rely on it and it issues the project's most consequential recommendation with specific numbers, yet links to no Experiment of its own (it is corroborated_only, via F19). Of 126 current Findings, 108 are linked, 7 cite an experiment without an evidence-resolving link, 2 are corroborated-only, and 9 have no direct link (F11,F23,F27,F28,F29,F30,F31,F32,F33). Separately the audit found a real integrity violation: F13 declares it supersedes F9 and F10, but neither carries a tombstone, so every other reader still counts them current.
Links: [[E112|evidenced_by]] · [[F17|relates]] · [[F7|relates]].
_— captured claude/research-continuation-ca1242@8d685fb, 2026-07-24_

### H73 — Make in-vivo belief revision measurable: separate supersession commits, tombstone F9/F10, link F17
EPI-00 (F133) shows the ledger cannot yet measure its own revision rate because supersessions are recorded inside capture batches rather than when they happen, and because unobservable classes dominate. Concrete, cheap actions that would make the next audit informative: (1) commit an in-vivo supersession on its own, with note.py's 'at:' stamp, separate from the batch that introduces the superseding node; (2) add tombstones to F9 and F10, which F13 already declares it supersedes; (3) add an evidenced_by link from F17 to its Experiment (E10 is the likely source) - 148 nodes rely on it; (4) break the D6<->F24/F25 reliance cycles; (5) consider adding acyclicity of the reliance graph and supersedes-tombstone pairing to the CI invariants, both of which the lab already computes. Re-running EPI-00 in a FULL clone is a precondition for any historical rate claim, since this checkout is shallow.
Links: [[F133|builds_on]] · [[F134|builds_on]] · [[F135|builds_on]] · [[F27|relates]].
_— captured claude/research-continuation-ca1242@8d685fb, 2026-07-24_

### F136 — A second parser is a second source of truth: the audit's own cue classifier drifted from ctx.py and corrupted its reliance graph
EPI-00 v2 hand-wrote a copy of ctx.py's untyped-link cue classifier. The copy was materially unfaithful: ctx uses stem cues ('corroborat', 'support', 'refine'), sentence-boundary windowing, word-boundary matching, a negation guard ('not supported' is not an edge), and a rule letting a reliance verb beat a closer lineage cue. The copy missed all of it, mis-typing real edges - H2's 'Confirmed by the noise-ratio mechanism (F7) + SPY/IWM corroboration (F9)' resolved to 'relates' instead of 'supports' - which silently corrupts the reliance graph that blast radius and the whole structural-risk ranking are computed from. (Node IDs are deliberately written bare here, not as links: quoting another node's prose verbatim with live link syntax injects SPURIOUS edges, because cue classification cannot distinguish quotation from assertion. This node's own quote manufactured a supports edge to F9 that blocked F9's tombstone - see F137.) It was caught only because note.py's write-fence REFUSED a tombstone, citing a live H2 --supports--> F9 edge the lab could not see. v3 deletes the copy and delegates to ctx._classify_edge, plus dedupes one edge per target with explicit typing beating cue inference (SCHEMA calls the trailing Links: line authoritative) and rejects out-of-vocabulary types the way ctx does. A test now asserts byte-for-byte agreement with ctx on all 1171 edges of the live web. Corrected ranking: F28 (blast 111, no evidence link of any kind) outranks F17 (blast 140, corroborated_only via F19). Corrected integrity: only F9 has a DECLARED supersedes without a tombstone - F10 and F22 were cue-inferred false positives, and the F9 fix is blocked by live dependents (H2 supports it; E6 cites it without citing F13), which is why it persisted.
Links: [[E112|evidenced_by]] · [[F135|refines]] · [[F27|relates]].
_— captured claude/research-continuation-ca1242@2ef5724, 2026-07-24_

### F137 — Quoting another node's prose verbatim injects spurious edges, because cue classification cannot tell quotation from assertion
While fixing the F9 tombstone, the blocking edge turned out to be emitted by F136 itself: F136 quoted H2's prose verbatim, including live link syntax, and ctx's cue classifier read the phrase 'SPY/IWM corroboration (F9)' inside that quotation as a first-class supports edge from F136 to F9. A finding ABOUT cue misclassification thereby manufactured the exact edge it was describing, and that phantom reliance blocked the tombstone note.py was otherwise willing to write. The point was then demonstrated a third time: the first attempt to capture THIS finding was itself refused, because its body quoted the same phrase with live brackets. This is a structural limitation of prose-cue edge inference, not a one-off typo - any node that quotes, critiques, or documents another node's text silently acquires that text's edges, and meta-research nodes do this constantly. Mitigation used here: write node IDs bare inside quotations so a quotation cannot assert a relation. A stronger fix would be an explicit quotation fence the parser skips. The episode also shows the write-fence earning its keep: it refused three writes that would each have left the graph inconsistent, and named the offending edge precisely every time.
Links: [[E112|evidenced_by]] · [[F136|refines]].
_— captured claude/research-continuation-ca1242@83292c6, 2026-07-24_

### F138 — The web's four structural invariants were all violated and all invisible; they are now CI-enforced and the violations are fixed
EPI-00 (H73) recommended making the audit's integrity checks permanent. All four invariants it defines were VIOLATED when first run, and none was visible to ctx --lint (which covers dangling links, stale cites and reliance-on-superseded, but not these). Fixed in this pass: (1) F9 carried no tombstone although F13 explicitly declared it superseded - repaired via note.py supersede after clearing two real blockers, since H2 relied on F9 and E6 cited it without citing F13; H2's own answer was stale too and now records that F13 reversed its YES. (2) Three edges used the type 'extends', which is outside ctx.EDGE_TYPES, so ctx silently degraded them to relates; retyped to builds_on, which SCHEMA literally defines as 'Extends/depends on an earlier claim'. (3) The reliance graph had two cycles, D6<->F24 and D6<->F25: D6 was captured 2026-06-22 and carried builds_on edges to findings captured 2026-06-25, i.e. reliance pointing FORWARD in time. Retyped to relates - the later findings already refine D6 correctly - and the reliance graph is now a true DAG (570 edges, 0 cycles). (4) No duplicate node IDs today, though a historical revision defined D7 and D8 twice. tests/test_web_integrity.py now enforces all four plus byte-for-byte parser agreement with ctx, verified by a negative control that reintroduces the D6 cycle and confirms CI fails with an actionable message.
Links: [[E112|evidenced_by]] · [[F135|builds_on]] · [[F27|relates]].
_— captured claude/research-continuation-ca1242@83292c6, 2026-07-24_

### F139 — F17's headline numbers exist nowhere but F17, and the load-bearing daily-MR arc is neither byte-identified nor reconstructible
EPI-00 ranked F17 the top structural risk and I described its evidence as 'almost certainly in E10'. That was too generous, and searching properly corrects it. F17's specific figures - QQQ +1.99% APY, Sharpe 0.74, -8% DD, and +1.74% APY at 10bps - appear in NO committed file except F17's own body. Every grep hit for those numbers elsewhere is a coincidental match from unrelated studies (gap betas, TNA monthly returns, block-bootstrap CIs). No deleted file in the observable history held them either. The plausible generator is tools/mr_daily_lab.py (E10's harness), which does emit exactly ann/sharpe/maxdd for a QQQ dip-plus-5-day-horizon sleeve - so the claim shape matches - but no artifact records the run. Reproduction is blocked here by design plus policy: the tool's input contract is CACHE=/tmp/mr_daily_close.csv, commented 'ephemeral; re-fetched if absent (no repo data committed)', it carries no sha256 manifest and no committed fixture, and the network policy blocks Yahoo (403) though PyPI is reachable, so numpy/pandas/yfinance install but no price data can be fetched. This is strictly weaker than F63, which established that the EXECUTION studies' inputs are byte-identified by SHA-256 yet not reconstructible from a fresh clone; the daily-MR arc is neither byte-identified NOR reconstructible. It matters because that arc carries the structural weight: F17, F19, F20, F21, D4, D5, D6 and H8 - the entire top of the load-bearing table - are produced by or rest on E9/E10. Honesty check on that claim: measured over ALL edge types 20/20 of the top-20 trace to the arc, but so do 88% of all nodes, so that framing is near-vacuous; restricted to evidence and reliance edges the figure is 70% of the top-20 against a 44% baseline - a real but modest enrichment. The structural statement does not depend on the enrichment. The SEC and corporate-action labs already solved this with committed transformed fixtures plus hashes (the D13 pattern); the market-data labs never adopted it.
Links: [[E112|evidenced_by]] · [[F63|refines]] · [[F17|relates]] · [[D13|relates]].
_— captured claude/research-continuation-ca1242@bd20f19, 2026-07-24_

### H74 — Adopt the frozen-fixture discipline for the daily-MR arc: freeze mr_daily_lab inputs + outputs so F17/F19/F20/F21 become reproducible
F139 shows the web's load-bearing arc (E9/E10 -> F17/F19/F20/F21 -> D4/D5/D6/H8) rests on an ephemeral /tmp price cache with no hash and no committed fixture, and cannot be rebuilt from a fresh clone. The SEC/corporate-action labs already solved exactly this (D13/F63 pattern: commit a small TRANSFORMED fixture plus SHA-256, keep raw vendor bytes outside the repo, validate on load). Proposed: (1) add a manifest to tools/mr_daily_lab.py recording the exact universe, date range, provider, fetch timestamp and SHA-256 of the close panel; (2) commit a small transformed artifact - per-sleeve daily return series or the summary table - under docs/research/data/, not raw vendor OHLCV, so redistribution limits are respected; (3) commit the run OUTPUT (the ann/Sharpe/DD table) so F17's numbers have a home and can be diffed on refresh; (4) then add the missing evidenced_by edge from F17 to E10, which is only honest once a recorded run substantiates the figures. Blocked in the offline environment: PyPI is reachable so numpy/pandas/yfinance install, but Yahoo returns 403 through the proxy, so the panel cannot be fetched here. Needs a run in a network-permitted environment. Until then F17 should be read as a DIRECTIONALLY corroborated claim (F19 independently confirms the sign of the exit effect from E10, in per-trade bps) whose specific portfolio figures are unverified.
Links: [[F139|builds_on]] · [[H73|refines]] · [[F17|relates]].
_— captured claude/research-continuation-ca1242@bd20f19, 2026-07-24_

### F140 — The web's code-claims are mechanically decidable, and two load-bearing ones are confirmed: the backtest ignores USE_REGIME_FILTER (8x entry divergence vs walk-forward) and the slope gate is dead
Most web claims are about markets and cannot be checked here (F139: the load-bearing arc is unreproducible and market-data hosts are network-blocked). But claims ABOUT THE CODE are decidable right now, with certainty - and they are the ones most at risk of rotting, because the code moves continuously while the web is only re-examined when adjacent work touches it (F133). Verified against current code: H27 is CONFIRMED and materially worse than recorded - src/backtest/runner.py:107 calls generate_trades WITHOUT use_regime_filter so it takes the signature default True (engine.py:107), while src/optimization/walk_forward.py:73 passes use_regime_filter=_cfg.USE_REGIME_FILTER (False). The two evidence-producing paths therefore apply DIFFERENT entry gates. Quantified on synthetic OHLCV (no market data needed, vol_regime true on 49.1% of bars): the runner path produces 112 entries where the walk-forward path produces 898 - the backtest keeps just 12.5% of the entries the OOS selector uses, so backtest and walk-forward numbers are not comparable at all. This is a concrete instance of the disconnect F2/F28/F30 describe. F26 is also CONFIRMED: runner.py never passes use_slope_regime/longs_only, both default False, and inside generate_trades every block guarded by those flags writes only regime_kelly_mult - it may read entry_signal to build a mask but never assigns to it. The only real entry mutation in that region is guarded by STRONG_BULL_SOFT_50MA_PCT, not by the slope flags. tests/test_web_code_claims.py now guards both claims BIDIRECTIONALLY via AST: each fails if the claim stops being true, with a message telling the maintainer to supersede the WEB node and re-baseline, because a silent fix leaving a stale finding is as much a defect as a regression. Includes a negative control proving the F26 detector flags a synthetic rewiring.
Links: [[H27|relates]] · [[F26|relates]] · [[F28|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@d4358fb, 2026-07-24_

### F141 — Every code-claim in the web now verified and guarded: F23 confirmed (per-mode windows never reach the entry signal), F29 still fixed, ctx claims at zero UNGUARDED
Continuing F140's executable-epistemics thread, the remaining code-claims were checked against current source rather than re-read. F23 is CONFIRMED, structurally and empirically. Structurally: inside momentum_signal (src/signals/momentum.py) both compute_rsi(close) and compute_macd(close) are called with the close series ONLY - no period argument is threaded through - so the per-mode RSI_PERIOD_*/MACD_* config cannot reach the entry signal. Empirically, reproducing F23's own stated proof on synthetic daily data: configuring rsi_period 7 with MACD 5/13/4 versus rsi_period 14 with MACD 12/26/9 makes the STORED rsi and macd_hist columns differ, while momentum_signal is byte-identical (76 nonzero signals either way). So the config reaches the stored columns but never the signal, exactly as recorded, and the armed bot trades RSI-14 / MACD-12-26-9 regardless of mode. F29 (walk-forward Sharpe annualized by sqrt(252) on hourly) is STILL FIXED: walk_forward.py calls metrics.annualized_sharpe(returns, tpy) with a periods-per-year argument and carries an explicit in-situ comment warning that a fixed sqrt(252) would be wrong - a good example of a fix documented at the site so it cannot silently regress. Both F23 halves are now guarded in tests/test_web_code_claims.py, and the F23 bridge in context_map.json carries guarded_by, so ctx claims reports 0 UNGUARDED for the first time. Per F23 itself the bug must NOT be fixed unilaterally: doing so changes live entries and invalidates every sweep tuned with it present, so it needs a re-sweep and sign-off with the trader stopped.
Links: [[F140|builds_on]] · [[F23|relates]] · [[F29|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@17f7287, 2026-07-25_

### E113 — NUM-00 numeric provenance audit: can a reader reach the document behind each figure in the web?
tools/numeric_provenance_lab.py extracts every figure from every node body and from all 87 docs/research/*.md with the SAME tokenizer, then classifies each figure as linked (in a doc reachable from the node, within one hop via Finding -> evidenced_by -> Experiment -> doc), unlinked (in some doc, but not a reachable one), or absent (in no doc at all). It extends F135 (per-node evidence linkage) and F139 (F17's figures unlocated by hand) from individual claims to a corpus-wide measurement, and separates 'we never wrote it down' from 'we wrote it down but nothing points there'. Web parsing is delegated to epistemic_audit_lab, which delegates edge classification to ctx.py - a deliberate single-source-of-truth choice because F136 records a previous audit corrupting its own graph by re-implementing that classifier. Stdlib-only, offline, refuses to write its JSON report inside the repo (asserted by test). 16 tests, four of which pin the lab's own measured LIMITS rather than its result, so the corrections survive corpus drift. See docs/research/NUM00_numeric_provenance.md.
Links: [[E112|builds_on]] · [[F135|relates]] · [[F139|relates]].
_— captured claude/research-continuation-ca1242@80b9bac, 2026-07-25_

### F142 — The project's central go/no-go decision cites nothing: D6 and its whole supporting arc quote figures with zero reachable evidence
NUM-00 result over 328 nodes and 87 docs: of 2388 figures, 58.5 percent are linked, 37.1 percent unlinked, 4.5 percent absent from every research doc. The token classes are weak (see limits) but the STRUCTURAL metric needs no value matching and is uncontaminated: 143 of 328 nodes quote figures and reach NO research doc at all, covering 794 of 2388 figures. Ranking by unreachable figures, EVERY top node cites nothing - F25 21 of 28, F22 19 of 20, F24 17 of 17, F45 17 of 17, F20 16 of 18, and D6 16 of 16. That is the finding. D6 is the repo's most consequential node, the GO/NO-GO that the active engine has no risk-adjusted edge over a static blend, the verdict CLAUDE.md's stale-performance banner defers to at the top of the file - and it quotes 16 figures while linking to zero documents, as does its entire supporting arc F22 F24 F25 E12. Blast-radius times uncitedness is maximised exactly there, so the cheap fix is not to chase 2388 figures but to attach evidence to the ~143 uncited nodes starting with D6. Whether those numbers are still RECOVERABLE is a separate question NUM-00 deliberately does not answer. Three measured limits keep this honest and are pinned as executable tests: 62.9 percent of extracted figures are low-information tokens (43.8 percent bare two-digit integers, 19.1 percent four-digit years); a figure perturbed by one tick, a value the corpus never claimed, still lands present-in-some-doc 59.4 percent of the time over 4000 draws; and 80.8 percent of unlinked sits in zero-doc nodes, making it a CITATION gap rather than the traversal gap the first write-up called it.
Links: [[E113|evidenced_by]] · [[D6|relates]] · [[F135|builds_on]].
_— captured claude/research-continuation-ca1242@80b9bac, 2026-07-25_

### F143 — The regime-gate divergence is not backtest-vs-walkforward: the runner is the odd one out of FOUR call sites, and it prints a gate it does not trade
F140 framed H27 as two evidence paths disagreeing. Counting every production call site of generate_trades shows something worse and simpler - the runner disagrees with ALL THREE others and with its own stated intent two lines earlier. src/backtest/runner.py:107 omits use_regime_filter entirely so it takes the signature default True (engine.py:107); src/optimization/walk_forward.py:73 passes _cfg.USE_REGIME_FILTER; live/signals.py:99 hardcodes False; tools/overnight_gap_risk_study.py:230 threads it as a study parameter and varies it deliberately. Every caller that was written with the gate in mind supplies it; only the runner forgot, and the runner is what produces the headline backtest numbers. Two consequences the two-path framing hid. FIRST, walk-forward and live agree only COINCIDENTALLY at today's config value: walk-forward reads config.USE_REGIME_FILTER while live hardcodes False, so flipping that config to True silently moves the OOS selector and leaves the armed bot where it is - a latent divergence between the thing that chooses parameters and the thing that trades them. SECOND, the smoking gun: runner.py:99 computes use_regime correctly and per-timeframe (USE_REGIME_FILTER_HOURLY vs USE_REGIME_FILTER), line 100 computes use_slope_regime, lines 102-104 hand both to _print_signal_diagnostics, and lines 107-111 hand NEITHER to generate_trades. With config.VERBOSE_SIGNALS=True, which is the current value, every backtest run PRINTS use_regime=False while its trades run use_regime_filter=True. The diagnostic is not merely absent, it is actively wrong, which is why the divergence survived this long. Same mechanism strands USE_SLOPE_REGIME=True in config while every backtest runs it False, independently confirming F26. Severity is high because the runner is the odd one out against both evidence-producing paths and against its own line-99 intent. Guarded bidirectionally in tests/test_web_code_claims.py by FourSiteGateTests, which pins the call-site census so a NEW caller must be classified rather than silently ignored, asserts the MECHANISM of the wf/live coincidence rather than its current value, and fails if the printed and traded gates ever agree - each with a message telling the maintainer to supersede this node rather than edit the test.
Links: [[F140|refines]] · [[H27|relates]] · [[F26|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@bf3578d, 2026-07-25_

### E114 — REPRO-00 offline-reproducibility audit of the analysis tooling, plus the validated market-data cache guard
Two parts. AUDIT: classified all 39 executable analysis scripts (tools/*.py plus main.py, sweep.py, fee_analysis.py) by whether they produce research output with no network and no missing files, preferring each script's own --selfcheck/--help/census subcommand and a short timeout; recorded the real blocker rather than the sandbox provisioning gap (dotenv/matplotlib absent here were shimmed or discounted); checked git log --all --diff-filter=A for whether each missing artifact was EVER committed, which distinguishes 'deleted' from 'never existed'; and attributed web nodes to scripts by grepping RESEARCH_WEB.md for each basename. GUARD: tools/data_cache.py replaces the shared unvalidated-cache pattern in tools/mr_daily_lab.py (two call sites), tools/power_study.py and tools/gold_oos_study.py. load_cached_frame validates a fetched frame BEFORE writing it (raising EmptyFetchError, so a blocked fetch leaves no stub), validates an existing cache on read (raising PoisonedCacheError naming the file and the rm remedy), and writes atomically via temp-file plus os.replace so an interrupted run cannot leave a half-written panel that passes a shape check. fail_cleanly turns either into a one-line message and exit 2 instead of a traceback ending in unrelated arithmetic. 14 tests in tests/test_data_cache.py, ordered by what matters: a bad fetch must leave NO file (asserted by checking non-existence, not merely that an exception was raised), an existing stub must be rejected with an actionable message, the happy path must still round-trip, and two bidirectional guards fail if any lab is rewritten to fetch directly again. Deliberately out of scope: staleness and provenance, which need the frozen-fixture plus SHA-256 manifest discipline of D13/F63. See docs/research/REPRO00_market_data_reproducibility.md.
Links: [[H74|relates]] · [[F139|relates]].
_— captured claude/research-continuation-ca1242@8bfad9d, 2026-07-25_

### F144 — Only 31 percent of the analysis tooling runs offline, no market data was ever committed, and a self-perpetuating poison cache blocked every reproduction attempt (now fixed)
Classified all 39 executable analysis scripts by whether they produce research output offline: 12 RUN (31 percent), 18 NEED-NETWORK, 5 NEED-MISSING-DATA, 4 other. The split is about substrate, not code quality - everything reading a COMMITTED artifact (RESEARCH_WEB.md, the JSON fixtures in docs/research/data/) runs; everything reading MARKET data is dead. Measured: across all 80 visible commits on any ref, ZERO .csv files were ever added (.gitignore:4 is a blanket *.csv). Honest caveat: this checkout is a SHALLOW clone, so the claim is 'none in visible history', not 'none ever'. Exposure is concentrated - tools/overnight_gap_risk_study.py needs four CSVs that do not exist, and nodes naming it plus nodes citing those come to 110 of 346 nodes, about 32 percent of the web; no other script exceeds 11. Worse than plain missing data, every market-data lab shared a POISON-CACHE footgun: yfinance returns an EMPTY frame rather than raising when blocked, so the unconditional px.to_csv(CACHE) wrote a header-only stub and every later run took the os.path.exists branch and trusted it forever. Confirmed in /tmp at 69 bytes, 0 rows. Three properties made it severe - it SURVIVES restoration of network access, so fixing connectivity does not fix the result; it fails FAR from its cause as IndexError index -1 is out of bounds inside a statistics routine with nothing pointing at the cache; and mr_daily_lab and power_study write the SAME path so one lab's stub becomes the other's input. gold_oos_study's partial guard checked every ticker COLUMN was present, which a stub passes because it has all columns and no rows. Only tips_sleeve_study reported missing data clearly; the rest died on empty-frame arithmetic and three exited 0 having done nothing; sweep.py has the same trap on its own data/cache path. FIXED by E114's guard, verified end-to-end with the stub deleted so a real fetch was attempted and failed: the lab now exits 2 with an actionable message and does NOT re-create the stub, so the trap cannot re-arm. Explicitly NOT fixed: staleness and provenance, which is the gap that let D6's published figures drift.
Links: [[E114|evidenced_by]] · [[F142|builds_on]] · [[H74|relates]].
_— captured claude/research-continuation-ca1242@8bfad9d, 2026-07-25_

### F145 — CLAUDE.md's Kelly multiplier chain exists in no code path, and five sizing knobs are dead config that reads as live tuning surface
SCOPE FIRST, because the broader version of this claim does NOT survive verification. The executed sizing is not hidden and not undocumented: config_modules/base.py:24 sets POSITION_SIZING_MODE='fixed' with FIXED_POSITION_PCT=0.10, runner.py:351 PRINTS 'Sizing: Fixed 10 percent per trade' in every result block, src/optimization/sweep_sizing.py's docstring explains the fixed default as a deliberate live-alignment choice (workstream C1) so headline numbers match how the bot actually trades, and F28 already records the backtest-vs-live sizing disconnect. Kelly is also still reachable on two paths - walk_forward.py:242-251 does NOT use position_fraction at all but runs its own equity loop with compute_position_size(kelly_multiplier=_cfg.KELLY_MULTIPLIER), reachable via main.py --mode=walk-forward, and sweep.py:91-96 exposes --sizing kelly --adaptive on. So 'every backtest is flat 10 percent' and 'KELLY_MULTIPLIER is unreachable' are both false; the honest framing is that the DEFAULT path is fixed 10 percent while a second production path sizes with half-Kelly, which is its own comparability problem and is what F28 covers. WHAT IS ACTUALLY DEFECTIVE is narrower and fully mechanical: five knobs have no consumer on ANY path. (1) adx_kelly_mult is written at volatility.py:111-113 and read by nothing outside tests that assert the column's values. (2) regime_kelly_mult is written at momentum.py:183 and overwritten at engine.py:195/205/206, read by nothing. (3) USE_ADX_SIZING exists only as config.py:109 - zero readers anywhere including tests. (4) MAX_POSITION_PCT_STRONG_BULL, which CLAUDE.md calls the KEY FIX worth 10.55 to 11.05 percent and Sharpe 4.844 to 4.924, has exactly one non-definition reference: a test that checks its inline COMMENT matches its VALUE. (5) bull_kelly_multiplier is threaded main.py:155 into the runner.py:62 signature and appears exactly ONCE in runner.py - the declaration itself - so it was born dead. Consequently CLAUDE.md's formula kelly_trade = min(base_kelly x regime_mult x adx_mult, pos_cap) describes a computation that exists in NO code path regardless of sizing mode, because runner.py:246 is simply position = capital * kelly_capped with no multipliers. CLAUDE.md's claim that the ADX multiplier is 'correctly computed (volatility.py:133-135) and applied (runner.py:129-134)' is false in both halves and both cites are stale: runner.py:129-134 is now ATR stop-widening, and volatility.py has 115 lines so the cited range is past the end of the file - evidence the claim was never re-verified after the code moved. Whether CLAUDE.md was ever accurate is NOT answerable here: the clone is shallow and config_modules/base.py appears in one commit, so do not claim either way. Guarded by DeadSizingKnobTests in tests/test_web_code_claims.py, each of which fails if a knob acquires a consumer, telling the maintainer to supersede this node.
Links: [[F143|builds_on]] · [[F28|relates]] · [[F26|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@1f9b3a2, 2026-07-25_

### E115 — DRIFT-00 corpus-wide search for silently divergent figures between web nodes and research docs
Two independent detectors over RESEARCH_WEB.md (346 nodes) and docs/research/*.md (88 docs), both normalising Unicode minus and thousands separators per NUM-00's caveat. Detector A clusters units naming the same producing script (22 clusters), extracts figures with a clause-level parse that inherits an elided metric across 'vs'/'and' lists, and compares only where the BENCHMARK-IDENTITY qualifier matches (60/40, 50/50, active, buy-and-hold, vol-target); 22 candidates. Detector B is vocabulary-free: any two sentences whose NON-NUMERIC token sets overlap at Jaccard >= 0.55 with rare-token blocking, but whose aligned numeric slots differ by 0.1 to 6 percent - 3156 sentences, 39564 blocked pairs, 20 candidates. Both are candidate GENERATORS only; every reported row was then verified by reading the source table or the producing tool. Rejection discipline was the main work: 42 unique candidates yielded 6 drift rows, 7 rounding, and 29 rejections - 9 different-window (D6_voltarget_riskparity_study.md's 2002-2026 baseline is 0.84 and its 2014-2026 baseline 0.87, same label, genuinely different quantity), 5 different-variant/row, 14 parse artifacts (95% CI read as a value, year fragments from '2002-2026', CIK digits inside SEC EDGAR URLs), 1 different-instrument. Two honest limits: mr_daily_lab.py gonogo could not be re-run to arbitrate the D6 cluster because the cache is poisoned and there is no market-data access, so the finding establishes DISAGREEMENT and the weight of evidence, not which digit is correct; and mr_daily_lab.py appears in only one commit of the shallow 80-commit history, so a methodology change between the two captures cannot be ruled out.
Links: [[E113|builds_on]] · [[F142|relates]].
_— captured claude/research-continuation-ca1242@fbdab99, 2026-07-25_

### F146 — Numeric drift is real but concentrated on the D6 arc, in both directions, and neither the web nor the docs is authoritative by default
Corpus-wide search (E115) found the corpus is NOT riddled with drift - 29 of 42 candidates were false positives and the most heavily cited study family is exact - but drift is not random either, and both confirmed clusters sit on D6, the project's most consequential decision. CLUSTER 1, a VINTAGE FORK on tools/mr_daily_lab.py Window A: two internally-consistent number sets captured 5 days apart, both still live. The 2026-06-22 vintage (E12 at RESEARCH_WEB.md:380, D6 at :385, F22 at :364/:372) reads static 60/40 Sharpe 0.86, active 0.69, active ann 6.2 percent, equity-blend 0.80; the 2026-06-27 vintage reads 0.84, 0.68, 6.1, 0.78 across D6_active_vs_6040_study.md:23/:31, D6_overlay_build_study.md:26/:31, and nodes E26/E28. maxDD -13.9 percent is the one figure that agrees. Crucially THREE separate assertions of exact reproduction - 'matching Window A exactly' at D6_active_vs_6040_study.md:23, 'byte-for-byte ... holds exactly' at D6_overlay_build_study.md:26, and RESEARCH_WEB.md:746 - are each TRUE against their own window and each FALSE against D6's published headline, and none notices. The phrase certifies internal reproducibility, never agreement with the number the decision actually cites. CLUSTER 2 runs the OPPOSITE direction and needs no market data to settle, because the document refutes itself: D6_static_product_study.md's own table at :36 lists '+ dividends added back (same 4-asset basket)' as 0.85 / 9.4 percent and 'composition variant (drop S&P, all-TR ETFs)' as 0.84 / 9.5 percent, and its Honest read immediately below warns that 'the all-TR ETF basket looks richer (CAGR 9.5 percent) but the extra is COMPOSITION ..., not dividends' - then the doc's Finding at :71 and Verdict at :78 quote that very composition row under the label 'dividend-correct', and :72 compounds it by pairing a composition-derived Sharpe delta (+0.02) with the dividend-derived CAGR delta. The web node F38 has it RIGHT (0.85, +0.03). Both errors PROPAGATED BY CITATION rather than recomputation: D6_power_equivalence_study.md:113 inherited 0.86 by quoting D6, and D6_forward_expectation_study.md:10 inherited the wrong 9.5 percent by quoting F38 in quotation marks. NOTABLE NEGATIVE RESULT: the largest cluster by citation volume, overnight_gap_risk_study.py at 55 web nodes and 143 doc mentions, is exactly self-consistent - 1516 / 980 / 157 / 33.76 / 26.09 / 52.17 / 28.57 agree digit-for-digit and the derived arithmetic checks. Drift is not uniformly distributed. The structural reason it lands where it does is the same one NUM-00 found independently: D6 and F38 NAME NO PRODUCING SCRIPT, so script-based clustering could not see them and they were found only by following the arc by hand - the nodes carrying drifted digits are exactly the nodes with no evidence link to check them against. PRACTICAL VERDICT: trust this corpus to about 2 significant figures and to the SIGN AND DIRECTION of every verdict - no drift found changes any conclusion, active still loses to static 60/40 whether by 0.17 or 0.19 Sharpe - but NOT at the third significant figure, and specifically not where a Finding or Decision quotes a number without linking the study that produced it. Neither layer is authoritative by default: in cluster 1 the web is stale and the docs are right; in cluster 2 the web is right and the doc is wrong.
Links: [[E115|evidenced_by]] · [[F142|builds_on]] · [[D6|relates]] · [[F38|relates]].
_— captured claude/research-continuation-ca1242@fbdab99, 2026-07-25_

### E116 — CONV-00 return-convention consistency check, and a 3-lens adversarial review that materially corrected its first headline
tools/return_convention_lab.py checks the size of the log-to-simple Sharpe translation the D6-arc studies disclose as a caveat, using NO market data, three ways. ALGEBRA: log-space leg mixing loses the Ito/Jensen term, so dSharpe = sum_i w_i sigma_i^2 / (2 sigma_p). DATA-FREE BOUND: for long-only weights summing to 1, sum_i w_i sigma_i^2 >= sigma_p^2 by Cauchy-Schwarz then the power-mean inequality, hence dSharpe >= sigma_p/2 - no correlations, no data, no distributional assumption. ARITHMETIC: every study prints ann percent beside Sharpe, so the implied vol and therefore the floor follow from committed numbers alone. 17 tests weighted toward proving the inequality rather than exercising the CLI - closed forms where the answer is exact, a TIGHTNESS check because a merely-true-but-loose bound would not license the conclusion (measured tightest ratio 1.000038), and a direction check, since a flipped inequality is exactly the transcription error the lab exists to catch in someone else's work. A three-lens adversarial review (algebra / same-portfolio identity / charity to the original authors) then materially corrected the lab's first headline, and the corrections are recorded in the lab rather than edited out. The ALGEBRA lens was sent to find a log-of-portfolio versus portfolio-of-logs confusion and REFUTED its own route: the code genuinely compares a simple portfolio against a portfolio-of-logs (static_product_study.py:113-119 builds sum w_i R_i and never calls np.log), and even under the alternative reading the gap decomposes additively as +0.0602 plus +0.0544, each still 5 to 9 times the disclosed figures. The IDENTITY lens confirmed basket, weights, window, data source, cost, dividend handling and Sharpe definition are all identical - it re-ran both committed pipelines on a synthetic panel with adversarial NaN holes and showed index equality is structurally forced, not coincidental - but flagged that +0.12 is a subtraction of two 2-decimal table values, so it is +0.12 plus or minus 0.01, and the source table is itself internally off by 0.01 in the same way. Stdlib only, offline, writes nothing.
Links: [[E115|builds_on]] · [[F146|relates]].
_— captured claude/research-continuation-ca1242@0ded536, 2026-07-25_

### F147 — One wrong sentence copy-pasted into six sites understates a convention gap by 12x, while the corpus states the same quantity correctly three sites earlier — a second instance of F146's citation-propagation failure
The D6 studies split on return-accounting convention: some mix portfolio legs in LOG space, others use SIMPLE returns, and the difference is disclosed as a caveat. The size of that difference is checkable with zero market data and the corpus gets it BOTH right and wrong. TRUE VALUE: the corpus's own committed tables put it at +0.12 plus or minus 0.01 - static 60/40 Window B reads Sharpe 0.70 log (D6_active_vs_6040_study.md:31) and 0.82 simple (D6_static_product_study.md:34) on a provably identical basket, weights, 6010-day window, data source, cost treatment, dividend handling and Sharpe formula, so convention is the only difference. Independently bounded without any data: dSharpe >= sigma_p/2, and that portfolio's implied vol of 11.30 percent gives a floor of +0.057, so ~0.01 would require a 2 percent volatility portfolio. CLASSIFICATION, which is the finding: of ten disclosure sites, THREE ARE CORRECT (power_study_6040.py:29 and :209, D6_active_vs_6040_study.md:70 all give 0.84 to ~0.97, i.e. +0.13, right to the printed precision) - and they come FIRST, inside the very study that supplies the log anchor. TWO ARE A DIFFERENT QUANTITY (overlay_build_study.py:29, D6_overlay_build_study.md:107) scoped in their own sentence to that study's OUTER core-to-active blending step, whose Jensen term genuinely is about +0.005 to +0.007 at the pre-specified w=20 percent; they are right answers to a different question. The ERROR is ONE SENTENCE, 'absolute Sharpes differ ~0.01 from the prior log-convention studies', written once at static_product_study.py:20 and copy-pasted verbatim into five further sites (D6_static_product_study.md:19 and :103, D6_voltarget_riskparity_study.md:21 and :90, D6_gold_oos_study.md:83), wrong by about 12x. So this is a CITATION-PROPAGATION defect - one wrong number replicated six times, coexisting with three correct statements of the same quantity - which is F146's mechanism appearing a second time, independently, on the same arc. TWO CORRECTIONS TO THIS FINDING'S OWN FIRST FRAMING, kept visible because the pattern is the point (F134). First, 'four sites state it four ways spanning 20x' was WRONG: that span is manufactured by putting the correct site, the differently-scoped site and the error on one axis, and it is only reachable by anchoring on the smallest figure. Second, an appealing causal story - that D6_overlay_build_study.md:107 licensed the error by 'verifying' an absolute-level claim with a paired-delta measurement - is REFUTED on two independent grounds: the 'verified' parenthetical attaches to the cancellation clause immediately before it, for which paired deltas are the correct measurement; and git blame puts :107 in 02ba6dc at 2026-06-27 19:12:47 and the ~0.01 in 7405f43 at 19:39:56, so the supposed cause was written 27 MINUTES AFTER the effect. CONSEQUENCE: a comparability hazard, not a wrong verdict. D6_voltarget_riskparity_study.md:34 reports a simple-convention 2002-2026 60/40 at 0.84 and D6_active_vs_6040_study.md:31 a log-convention 2014-2026 60/40 at 0.84; the ~0.01 rule invites treating those as the same measurement when under a common convention they are ~0.70 and ~0.84 - the convention flip happens to cancel the window difference. No verdict flips: active still loses to static 60/40.
Links: [[E116|evidenced_by]] · [[F146|builds_on]] · [[D6|relates]].
_— captured claude/research-continuation-ca1242@0ded536, 2026-07-25_

### F148 — HOURLY_TRADE_FILTER=False does not disable the hourly filter: main.py applies a (9,16) gate on a UTC-naive index, keeping only 2-3 of 7 session bars — the morning-only artifact re-manufactured in code
config.py:167 sets HOURLY_TRADE_FILTER = False with the comment '24hr mode confirmed best'. But main.py:112-116 takes the ELSE branch when the flag is False and sets trade_hours = (9, 16) anyway, commented 'Default for equities: US regular trading hours (9:30-16:00 ET -> bars 9-15)'. That comment states an intent the code cannot achieve, because src/data/fetcher.py:283-284 does df.index = df.index.tz_convert(None) - converting to UTC-NAIVE, not to Eastern. src/strategy/engine.py:145-147 then applies in_hours = (hour >= 9) & (hour < 16) against those UTC hours. Measured on a real 7-bar US session: in winter (EST, UTC-5) the gate keeps 2 of 7 bars (09:30 and 10:30 ET); in summer (EDT, UTC-4) it keeps 3 of 7 (09:30, 10:30, 11:30 ET). So the backtest entry path is restricted to the FIRST TWO OR THREE BARS OF EACH SESSION whenever the hourly filter is nominally OFF. This matters beyond a flag bug. F12/F13 established that the hourly edge was a morning-only DATA-SAMPLING artifact - the 710-day yfinance fetch returned morning-only bars - and that the live bot, trading full sessions, is flat. This finding shows the CODE independently re-creates the same restriction even when the data is correct full-session: the entry gate itself selects the morning. Any hourly backtest run through main.py therefore reproduces the artifact structurally, not just historically, which is a candidate explanation for why the discrepancy persisted after the data path was fixed. Two consequences for constraint 4 of CLAUDE.md section 12 ('all new features must be independently toggleable via config flag'): the flag does not toggle the feature it names, and the failure is silent because the gate is applied in a branch that reads as a sensible default. NOT FIXED HERE: correcting either the timezone or the else-branch changes which bars produce entries and therefore every hourly backtest number, so it needs sign-off and a re-sweep rather than a unilateral edit.
Links: [[F12|relates]] · [[F13|relates]] · [[F145|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@ae84dff, 2026-07-25_

### F149 — D6's capital-preservation nuance rests on a benchmark swap: the maxDD point estimate is measured against 100 percent equity and its confidence interval against 50 percent equity
tools/power_study.py:214-217 reads: static5050 = 0.5 * bench; dd_a, dd_bench = maxdd_pct(active), maxdd_pct(bench); dd_boot = paired_maxdd_diff_boot(active, static5050). So the POINT estimate compares the active engine against the FULL buy-and-hold bench, while the CONFIDENCE INTERVAL compares it against a HALF-equity 50/50 blend. Those are two different comparators. A 50/50 blend has roughly half the drawdown of full equity, so the gap the CI is about is far smaller than the gap the point estimate displays, and the CI straddling zero is close to guaranteed. The verdict prose then welds them into a single sentence at :278-280: 'Capital-preservation is path-dependent: active maxDD far shallower at the point ({maxdd_active} vs {maxdd_bench} buy&hold, 26.5yr) but the paired maxDD-gap bootstrap straddles 0 ({maxdd_diff_ci}) - real on average, not statistically reliable.' The 'but' invites the reader to read one quantity measured two ways; it is two quantities against two benchmarks. This is load-bearing for D6. D6's own headline nuance - the clause that keeps the active engine alive as a low-drawdown overlay - is exactly this tension: 'the active engine does have the lowest drawdown / best Calmar of any static blend BY POINT ESTIMATE, but that edge is PATH-DEPENDENT (the paired maxDD/Calmar bootstrap straddles 0)'. If the point estimate and the interval are against different benchmarks, then 'shallower at the point but not significant' is manufactured by the swap rather than measured. HONEST QUALIFICATIONS. The code is not hiding it: the inline comment at :214 says 'point maxDD gap vs its paired-bootstrap CI (vs static 50/50)', and static 50/50 is a legitimate comparator - it is D6's own recommended blend. The defect is in the NARRATIVE, which pairs a buy-and-hold point gap with a 50/50 interval in one breath, and in D6 inheriting the welded form. Also unresolved offline: which comparison SHOULD anchor the claim. Measuring active against 50/50 on both sides, or against buy-and-hold on both sides, are each defensible; what is not defensible is one on each side. Re-running to settle it needs market data (the caches are poisoned stubs), so this records the structural defect, not a corrected number.
Links: [[D6|relates]] · [[F146|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@ae84dff, 2026-07-25_

### F150 — CA-ANNOUNCE polices WHAT the forecaster sees but never WHEN it stands: as_of is hand-set, outcome-correlated, and a cohort forecast entirely after resolution passes every integrity gate
This qualifies my own E111/F130/F131. The only constraint on market_implied.as_of anywhere in the codebase is tools/ca_announce_cohort_lab.py:120-121, 'if as_of < announced: raise'. There is no upper bound, no relation to the resolution date, and no uniformity requirement across deals. F131 advertised exactly this as the look-ahead property - 'every market_implied.as_of is >= announcement' - which is true but far weaker than it sounds, because it permits a forecast timestamped AFTER the deal already resolved. VERIFIED DIRECTLY: constructing an adversarial copy of the committed fixture in which every single as_of is set to resolution_on + 1 day, validate_cohort ACCEPTS it without error. The repo's own leakage gate is orthogonal to forecast-time by construction: it tests that features are invariant to the terminal outcome, not that they were observable when claimed. THE VANTAGES ARE OUTCOME-CORRELATED IN THE COMMITTED FIXTURE. Measured offsets from announcement to as_of: amedisys 29d (higher_bid_displacement), focus 33, qualtrics 33, splunk 41, univar 48, seagen 49, national-instruments 50, pioneer 51 (all close_as_announced), then us-steel-nippon 166 and hess-chevron 222 (contested but closed), and capri-tapestry 265d - the LONGEST vantage in the cohort, and the ONLY negative_termination. That is the shape you would get by choosing each vantage after knowing how the deal went. It matters because the vantage is where the market-implied benchmark's information comes from: the gross deal spread at as_of is 0.55 to 6.44 percent for the eight early-vantage deals but 29.55 percent for capri and 30.95 percent for us-steel. A late vantage on a deal that broke is a nearly-resolved forecast. SIZING: giving capri the same vantage discipline as the normal deals (as_of +32d, spread set to the cohort-median 2.75 percent) moves the market-implied multiclass Brier from 0.3076 to 0.4052 and collapses its margin over the base-rate baseline from +0.1118 to +0.0143 - so most of F130's 'no transparent baseline beats calibrated market-implied' is bought by one deal's late vantage. F130's architectural conclusion survives; its comparative margin does not, at N=11. This is the forecast-time analogue of F131's outcome-leakage guard and needs the same treatment: police as_of against resolution_on, require a stated vantage rule applied uniformly, and add a kill criterion for outcome-correlated vantage.
Links: [[F130|refines]] · [[F131|relates]] · [[E111|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@ae84dff, 2026-07-25_

### F151 — Blast radius and articulation are different nodes: D6 is the web's only real cut vertex (severs 40-54) while F17 has 142 dependents and severs 0; and 50 of 74 hypotheses are dead ends
Structural audit of the typed web (351 nodes, 1222 intra-web typed edges) on the reliance projection {relies_on, supports, refines, builds_on}: 275 nodes, 583 edges, 9 components sized [169,80,10,4,3,3,2,2,2]. (a) ARTICULATION. D6 is the single articulation point of the largest component - removing it splits 169 into 128 + 39 + 1, severing 40 nodes, which is 2.5x the runner-up H44 at 16. Under a live-only graph (343 current nodes) adding evidenced_by raises the severance to 54. The redundancy around D6 is illusory: connectivity is only restored by adding ALL dependency edge types, and the paths that restore it are UNTYPED prose arrows the cue classifier guessed at, not authored typed links. (b) THE HUB IS AUTHORED, NOT INFERRED. All 73 reliance in-edges to D6 come from sources writing an explicitly TYPED link to D6 (bare ID plus a pipe and a relation name, written out rather than quoted here because quoting the syntax injects a spurious edge - F137); web-wide there are 114 explicit typed D6 links against 26 inferred from untyped mentions - so this is a real intellectual dependency, not a parsing artifact. (c) BLAST RADIUS IS A DIFFERENT METRIC FROM ARTICULATION, and the web's prior ranking used only the former. F135 ranked F17 the highest-leverage node by transitive dependents; recomputing confirms F17 leads there (142), ahead of F7 141, F16 140, D4 139, with D6 at 135. But severance tells the opposite story: D6 severs 40 while F17, F22 and D4 sever ZERO, and F7, F16, D5 sever 1. A node can be depended on by everything and still be structurally redundant. Combined with F142 - D6 quotes 16 figures and cites zero documents - the web's single point of intellectual failure is also its least evidenced node. (d) HYPOTHESIS MORTALITY. Only 9 of 74 H nodes ever receive an incoming 'resolves' edge (H1 H2 H3 H5 H42 H43 H61 H62 H71); 54 are never touched by ANY Finding in any direction; and 50 are dead ends on the strictest test (no resolves edge, title not marked RESOLVED/DEAD/DONE, never cited by a Finding), of which 33 have zero in-edges of any kind. So the web records hypotheses far more readily than it retires them, which biases any attempt to measure the project's own error rate (F133) toward looking stable. (e) ALL OF THIS IS INVISIBLE TO THE EXISTING TOOLING: ctx health reports 100/100 and ctx web --lint reports 0 problems, because both check dangling references and staleness, not connectivity or hypothesis resolution.
Links: [[F135|refines]] · [[F142|relates]] · [[F133|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@ae84dff, 2026-07-25_

### F152 — CA-ANNOUNCE forecast-time hole closed: postdiction is now rejected, but the hindsight-in-vantage channel is only reportable, not testable at N=11
Repair for F150, on my own lab. TWO DISTINCT CHANNELS, only one of which can be closed by a guard. (1) POSTDICTION, now CLOSED. validate_cohort previously required only as_of >= announced; it now additionally requires as_of strictly < ground_truth.resolution_on, raising 'that is a postdiction, not a forecast'. Verified three ways: the committed fixture still validates; the exact adversarial cohort that used to pass everything (every as_of set to resolution + 1 day) is now rejected; and a forecast dated exactly ON the resolution date is also rejected, because the outcome is known intraday. Guarded by ForecastTimeGuardTests, which also pins that the original announcement floor still works. (2) HINDSIGHT IN THE CHOICE OF VANTAGE, NOT closeable. Even with every as_of legal, picking each deal's vantage after knowing how that deal went leaves NO trace a feature-level leakage test can find, because every feature really was observable at its stated as_of - the information enters through WHICH as_of was picked. So the lab now reports it instead: vantage_audit() returns the per-deal offsets, the offsets grouped by outcome class, and an EXACT permutation rank test, and _caveats() emits an unconditional 'FORECAST-TIME VANTAGE IS NOT UNIFORM' warning on every build naming the longest vantage and its outcome class. AN HONEST NEGATIVE ON MY OWN STATISTIC. The exact test returns p=0.5455 - not significant - and the reason is instructive: the two non-clean deals sit at OPPOSITE extremes (amedisys, a higher-bid displacement, has the SHORTEST vantage at 29d; capri-tapestry, the only negative_termination, the LONGEST at 265d), so their ranks 1 and 11 sum to an unremarkable 12 and a rank-SUM is structurally blind to the pattern actually present. The audit says so in a dedicated statistic_is_blind_to field, and a test asserts that field mentions it, because a p-value of 0.55 presented without that caveat would read as an all-clear when it is a blind spot. A dispersion or extremity statistic would have more power, but at N=11 with one deal per non-clean class nothing reaches significance, so no test is reported as decisive. THE STANDING CONCLUSION IS THEREFORE UNCHANGED FROM F150: the non-uniformity is a FACT about the fixture, independent of any test, and the market-implied margin is not interpretable as forecasting skill until a uniform vantage rule (e.g. as_of := announcement + 30d for every deal) is applied and F130's comparison re-run.
Links: [[F150|refines]] · [[F131|relates]] · [[E111|relates]].
_— captured claude/research-continuation-ca1242@82ecf4a, 2026-07-25_

### F153 — The corpus has TWO disjoint Sharpe stacks with no bridge, and docs/research/README.md guarantees the opposite — the documented invariant is what licensed cross-convention comparison
Mechanically verified by grep over the whole tools/ surface. The ACTIVE mean-reversion family - mr_daily_lab.py, power_study.py, power_study_6040.py, overlay_build_study.py, crisis_overlay_study.py - computes Sharpe on LOG returns with exp(cumsum) equity curves, and ZERO of those five files contains a single pct_change or expm1 call. The STATIC-PRODUCT family - static_product_study.py, gold_oos_study.py, voltarget_riskparity_study.py, bond_ladder_study.py - computes Sharpe on SIMPLE returns with cumprod(1+r), and ZERO of those contains np.log. The two stacks are strictly disjoint: no tool in the repo computes both conventions, so nothing in the codebase could ever have surfaced the discrepancy internally. On a provably identical 60/40 (same basket, weights, 6010-day window, same cache) they publish 0.70 and 0.82 - see F147. THE DOCUMENTED INVARIANT SAYS THE OPPOSITE. docs/research/README.md:154, in the methodology-guarantees list, reads 'One source of truth - all studies reuse the same vetted primitives; no divergent Sharpe or drawdown implementations.' That is false on both clauses: there are two Sharpe implementations and two drawdown conventions (log-space exp(cumsum) versus simple-space cumprod), and they differ systematically rather than in rounding. This matters more than an ordinary stale doc, because the guarantee is exactly the licence a reader needs to compare two published Sharpes directly. F147 records the specific comparability hazard it enabled - D6_voltarget_riskparity_study.md reports a simple-convention 2002-2026 60/40 at 0.84 while D6_active_vs_6040_study.md reports a log-convention 2014-2026 60/40 at 0.84, and the convention flip happens to cancel the window difference so the two look like the same measurement. Corrected in place at README.md:154 with the original text struck through and the evidence stated. THE STRUCTURAL LESSON generalises past this one number: the project's stated invariants are prose, not tests. This one had no executable guard, so it could be false for the entire life of the corpus without any run failing - the same class as F145 (config knobs documented as active with zero readers) and F26 (a gate documented as the core innovation and wired into nothing). An invariant a repo cannot check is a belief, not an invariant.
Links: [[F147|builds_on]] · [[F145|relates]] · [[E116|evidenced_by]].
_— captured claude/research-continuation-ca1242@8559769, 2026-07-25_

### F154 — NEGATIVE RESULT: the labs' statistical machinery is sound — bootstrap pairing, MDE constant, TOST margin and the exact Poisson interval all survive closed-form and simulation checks
Worth recording precisely because the surrounding audit found so many defects: the STATISTICS are not among them. Audited against closed forms, published values, and ground-truth simulation. (1) The paired block bootstrap genuinely pairs - power_study.py:132-136 draws ONE starts array and indexes both legs with it, and the pairing is load-bearing rather than decorative, shrinking the standard error about 2.3x, with MDE and the TOST margin scaling linearly off it. (2) The dSharpe paired block bootstrap is well calibrated and slightly CONSERVATIVE at the shipped settings (block=20, B=5000), checked by pushing a GARCH(1,1) plus AR(1) mean-reverting synthetic price path through the REAL mr_daily_lab.sleeve and the REAL paired_sharpe_diff_boot, with population truth from a 400,000-day path and sampling SD from 400 independent 12.5-year samples. Block length is NOT load-bearing - results are flat across the range tested - which retires a plausible objection to the whole D6 arc. (3) The MDE constant 2.8016 is exactly right for 80 percent power at two-sided alpha 0.05: Z_0.975 + Z_0.80 = 1.959964 + 0.8416212 = 2.8015852, and a simulation with known SE returns empirical power of 79-80 percent. (4) epistemic_audit_lab.poisson_ci is genuinely EXACT (Garwood), not 'exact-ish' as its own docstring hedges - it matches an independent log-space Poisson CDF inversion to 2.66e-15 - and its coverage is correctly conservative. ONE REAL DEFECT, and it is prose not math: power_study.py's docstring at :26 describes the TOST equivalence margin as 'the 90 percent CI half-extent from 0', but the code at :200-202 computes equiv_margin = max(abs(lo90), abs(hi90)), which is the smallest margin the test actually passes - the correct quantity, and NOT half the CI width. The implementation is right and the description is wrong, which is the safer of the two failure modes but still a trap for anyone reasoning from the docstring rather than the code. TAKEN WITH THE REST OF THE AUDIT the pattern is consistent and worth stating: this project's errors live in its PROSE, its WIRING and its PROVENANCE - stale docs (F145), dead config (F145), unwired gates (F26), uncommitted fixtures (F144), copy-pasted figures (F146/F147), unchecked invariants (F153) - and essentially never in its mathematics. That is an unusual and favourable profile, and it means review effort is better spent on what the code is connected to than on what it computes.
Links: [[E116|evidenced_by]] · [[F153|relates]].
_— captured claude/research-continuation-ca1242@8559769, 2026-07-25_

### F155 — The live-safety audits' tripwires are one-directional: they fire when the buggy code is deleted and stay silent when it is FIXED, so 313 'control absent' claims survive implementing the very controls they demand
tools/overnight_gap_risk_study.py contains ~20 source audits of live/ that back F86-F104, roughly 58 nodes and the largest arc in the web. Each concludes that a safety control is ABSENT. What ties those conclusions to the code is a set of substring tokens - and every one of them cites the BUGGY code positively, so the tripwire detects only the deletion of the evidence, never the addition of the fix. MEASURED by building a shadow copy of the repo, implementing three remediations that F90/F91's own falsification_gate fields explicitly demand (BEGIN IMMEDIATE, a DELETE-with-rowcount generation guard, a CREATE UNIQUE INDEX on position) plus fcntl.flock, then re-running every audit with REPO repointed and diffing all 4,470 output leaves: 17 audits, 4470 leaf values, 777 boolean leaves, of which 313 are the False 'absence' claims. Implementing the fixes changed 18 leaves. FIFTEEN of those 18 are just the live/state.py sha256 echoed by each audit, and the other 3 are one derived flag. ZERO of the 313 False safety claims flipped and no assertion fired. The single flag that moved is the one place the author DID write a derived check - lock_tokens at :5602, consumed at :5796 as present=bool(present_lock_tokens). Everywhere else the flag is a hard-coded literal: position_uniqueness_constraint=False at :5788, begin_immediate_present=False at :8007, close_checks_delete_rowcount=False at :8429. Across the family the split is about 195 literal-False safety flags against 38 source-derived ones, so the correct technique exists in the file and was applied roughly once. The failure mode is asymmetric in the worst possible direction: a future engineer implements exactly what the falsification gates ask for, re-runs the program, and gets 313 unchanged 'control absent' flags and a green pass - the verdicts outliving their own subject matter. TWO SECONDARY RESULTS. All 206 source-contract tokens currently PASS (0 failing), so the tripwires that do exist are intact today - a clean negative on 'the audits are already silently broken'. But 3 of 20 audits build a token_audit and never enforce it (live_bar_completion_timezone_audit:4972, trader_singleton_launch_safety_audit:5515, entry_acknowledgement_and_basis_audit:5923 have no all(...)/raise), demonstrated by changing max_instances=1 to 3 - a semantically real change letting the scheduler run 3 concurrent jobs - after which the unguarded audit returned normally while publishing value: 1 from a hard-coded literal in the same dict where its own token check had just recorded False; a guarded sibling raised AssertionError. Finally the interleaving simulations run against a hand-written replica, not live/state.py: the replica position table at :7904-7907 has 5 columns in a different order versus the real 9 at live/state.py:38-48, and close_cached reads positionally while the real close_position reads by name. No token checks the schema. This is a finding about the DURABILITY of the evidence, not about whether F86-F104 are currently wrong - their reachability arguments read as sound.
Links: [[F144|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@d076d02, 2026-07-25_

### F156 — CORRECTION to F144: the live-safety audits were runnable offline the whole time — only the documented entrypoint was blocked, and 17 of 18 now pass in ~2 seconds
F144 measured that tools/overnight_gap_risk_study.py --selfcheck dies on four never-committed CSVs and attributed roughly 110 of 346 nodes (about 32 percent of the web) to that blockage. The blockage is real but the ATTRIBUTION was too broad, and the correction is constructive. The module's ~18 zero-argument source audits - the ones backing F86-F104, the live-safety half of the arc - read only live/** source text and need NO market data whatsoever. They were never blocked; --selfcheck simply runs preflight and dies before reaching them, on CSVs those audits do not read. VERIFIED by importing the module directly and calling every zero-arg audit: 17 of 18 complete, total runtime about two seconds, the only failure being _durable_ordering_audit which genuinely needs an absent file. So the honest split is: the MARKET-DATA studies in that module are blocked and remain so, while the SOURCE-AUDIT studies were reproducible on a fresh offline checkout all along and nobody could tell, because every Reproduce line in the docs routes through --selfcheck. FIXED: added a --audits subcommand that runs exactly the zero-arg source audits and reports, so the offline-reproducible portion has a working documented entrypoint. Its docstring and its final line both carry the F155 caveat, because the two findings interact badly if separated - a green --audits run means 'the cited source still reads as it did', NOT 'the safety controls are still absent', since those tripwires are one-directional. This is the second time in this audit that a documented entrypoint made working code look broken (the first being the poison cache in F144 itself), which suggests the general lesson: when a repo looks unreproducible, check whether the FRONT DOOR is what is broken before concluding the work behind it is lost.
Links: [[F144|refines]] · [[F155|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@d076d02, 2026-07-25_

### F157 — Live-safety gap: build_features keys signal thresholds on ACTIVE_MODE while the live path keys everything else on LIVE_SYMBOL, so the supported --symbol flag arms the bot with another instrument's thresholds
Systematic backtest-vs-live divergence inventory (31 rows). Most large divergences are already documented in the assumption waterfall at docs/research/D6_execution_semantics_study.md:47-58 - clock, hold cap, regime gate, short gate, one-position/overlap, entry-bar bracket, gap fills - so the new rows concentrate in config plumbing, warmup and costs. THE ONE THAT IS A SAFETY ISSUE RATHER THAN A MEASUREMENT ISSUE: src/strategy/engine.py:31-32 resolves the signal-parameter suffix from config.ACTIVE_MODE, a BACKTEST selector, and live/signals.py:96 calls build_features with no mode argument. But every other live input keys on LIVE_SYMBOL - the bars, require_signals at signals.py:98, and the target/stop at trader.py:110-113. They agree today only by coincidence: ACTIVE_MODE=TQQQ_HOURLY and LIVE_SYMBOL=TQQQ. The documented CLI override at live/trader.py:789-790 does config.LIVE_SYMBOL = args.symbol.upper() and mutates NOTHING else, so --symbol GDXU arms the bot on GDXU while it computes RSI and VWAP thresholds for TQQQ. Measured on a synthetic hourly panel: swapping ACTIVE_MODE alone flips entry_signal on 202 of 4200 bars (4.8 percent) for QQQ-versus-TQQQ parameters; GDXU-versus-TQQQ flips only 4 of 4200 because only RSI_OVERSOLD differs there (85 versus 80). Not covered by H35, which enumerates only the backtest-side MODE_MAP/_MODE_TO_ASSET/ASSETS triple. RECOMMENDED FIX, NOT APPLIED: a startup invariant asserting ACTIVE_MODE == LIVE_SYMBOL + '_HOURLY', about three lines in the existing self-check block at trader.py:831-851 - outside the signal and order path, and changing no current behaviour since the values agree today. NOT APPLIED HERE because live/** requires explicit approval. FOUR SMALLER NEW ROWS. (1) The backtest has NO warmup buffer - main.py:142-143 builds features on the exact requested window, leaving trend_direction zero for the first 199 bars, while live enforces LIVE_MIN_WARMUP_BARS=200; the reassuring half is verified - once warm, live's trailing 300-bar window reproduces full-panel features to 1.7e-12 with 0 of 103 entry-signal mismatches, so the recursive EWM/Wilder seeding worry is a non-issue. (2) NO COST MODEL reaches the headline backtest: commission is modelled nowhere in config/, src/ or live/, and the instrument-aware spread model src/optimization/sweep_costs.py is imported only by sweep.py:36, so every main.py run uses the flat 2bp default. (3) USE_ADAPTIVE_KELLY plus eight ADAPTIVE_KELLY_* knobs are inert on the default path - a SIXTH dead-knob family beyond F145's five - since sizing.py:129 returns fixed_pct before the adaptive branch; verified by position_fraction returning 0.1 after 40 straight losses. That has a positive corollary: backtest and live sizing AGREE at fixed 10 percent, so F28's 'the sweep optimized a sizing model the live trader does not use' is true of sweep.py but NOT of main.py, and CLAUDE.md section 8's 'Adaptive Kelly is the ONLY dynamic sizing mechanism' is false. (4) config.py:120 states the opposing-signal exit's 'Live equivalent lives in live/trader.py behind EXIT_ON_OPPOSING_SIGNAL' - that identifier appears NOWHERE in the repo except that comment.
Links: [[F145|builds_on]] · [[F28|relates]] · [[F143|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@d076d02, 2026-07-25_

### F158 — APPLIED with approval: the live trader now refuses to start when ACTIVE_MODE and LIVE_SYMBOL disagree, closing F157's silent instrument/threshold mismatch
Supersedes F157's 'NOT APPLIED' status - recorded because leaving that clause standing would itself become the stale-claim failure this audit has been documenting. The operator explicitly approved the change to the fenced live path. WHAT WAS ADDED: live/trader.py gains _assert_mode_symbol_coherent(), a pure startup invariant requiring config.ACTIVE_MODE == LIVE_SYMBOL + '_HOURLY', called immediately after the --symbol override is applied and before anything touches the broker. Verified positions in the file: --symbol override at line 832, invariant call at 836, first broker.* call inside main() at 856. It touches no signal, order or state logic. WHY REFUSE RATHER THAN AUTO-CORRECT: silently rewriting ACTIVE_MODE would change which RSI/VWAP/MACD thresholds fire, and choosing an instrument's signal parameters is the operator's decision, not the guard's. The error names both keys, their current values, the exact value to set, and cites F157, so the operator can act without reading source. BEHAVIOUR TODAY IS UNCHANGED: the shipped config (LIVE_SYMBOL=TQQQ, ACTIVE_MODE=TQQQ_HOURLY) satisfies the invariant, confirmed by a test that fails if the repo's own config ever becomes incoherent. VERIFIED FOUR WAYS before commit, by extracting the function via AST and exec'ing it against stub configs rather than importing the armed module: the shipped config passes; a simulated --symbol GDXU is refused with the full operator message; a COHERENT override (--symbol QQQ with ACTIVE_MODE=QQQ_HOURLY) still passes, so the guard protects the supported workflow rather than breaking it; and a missing ACTIVE_MODE is refused cleanly rather than raising AttributeError. A fifth test asserts the guard never mutates the config it inspects. TESTS: tests/test_trader_mode_symbol_invariant.py, 7 tests, deliberately loading the function by AST rather than importing live.trader - both because that module imports dotenv, absent in some environments, and because a unit test should not import the armed-trader module as a side effect. Extraction is by function NAME so a rename or deletion fails loudly instead of silently passing on nothing. Two wiring tests pin that the guard is actually CALLED and that it runs after the --symbol override and before the first broker call in main(); the ordering assertion was itself repaired twice during development - first it matched the def line instead of the call, then it compared against a broker call in an unrelated function - and a negative control confirms it genuinely fails when the call is moved after the broker (856 versus 855). Full suite 843 tests, no failures.
Links: [[F157|refines]].
_— captured claude/research-continuation-ca1242@9f3c8bc, 2026-07-25_

### F159 — F155 repaired for the four highest-value absence claims: the audits can now notice their own fix, verified end-to-end by shadow remediation
Direct repair of F155 on tools/overnight_gap_risk_study.py. THE PROBLEM RESTATED: ~195 safety flags in that module were hard-coded literal False rather than derived from source, so a tripwire fired when the buggy code was DELETED and stayed silent when it was FIXED - measured previously as 313 False absence claims of which zero flipped after implementing three remediations the audits' own falsification_gate fields demand. THE FIX: added _derived_control(source, tokens), returning present plus matched_tokens, and converted the four highest-value literals to use it - position_uniqueness_constraint and signal_bar_uniqueness_constraint in trader_singleton_launch_safety_audit, begin_immediate_present in concurrent_close_idempotency_audit, and close_delete_is_generation_conditional plus close_checks_delete_rowcount in cross_generation_close_reentry_audit. Each derives from source_text['live/state.py'], which every one of those audits already reads and hashes. This generalises the ONE place the original author got it right (lock_tokens at :5620, consumed at :5796 as present=bool(present_lock_tokens)). VALUES ARE UNCHANGED TODAY, which is the point: live/state.py contains no UNIQUE, no BEGIN IMMEDIATE and no rowcount, so all four still read absent - the claims are still true, they are simply now FALSIFIABLE. VERIFIED END-TO-END by the same shadow method that established F155: copied the repo, appended the three remediations to the shadow live/state.py only, repointed REPO, and re-ran the three audits against both. All four flags flipped False to True. Under the old literals the identical experiment moved zero of 313. DELIBERATE ERROR DIRECTION, documented in the helper's docstring: tokens match against the whole source file rather than a narrowly-scoped schema block, so an unrelated occurrence can read as present. That over-approximation errs toward INVALIDATING an absence finding, which is the safe direction - a false 'present' prompts a human to re-examine, while a false 'absent' silently perpetuates a stale claim. TESTS: tests/test_gap_study_derived_controls.py, 6 tests. The load-bearing one is the negative control - each control is implemented in a patched copy of state.py and the flag is required to change - because without it a derived check is indistinguishable from the hard-coded False it replaced, which is exactly how the original literals passed unnoticed. A bidirectional test also fails if any converted flag is reverted to a literal. NOT DONE: this converts 4 of roughly 195 literal flags. The remaining ones are unaffected and F155 stands for them; the helper and the test pattern are now in place for whoever continues.
Links: [[F155|refines]].
_— captured claude/research-continuation-ca1242@d3caa1e, 2026-07-25_

### F160 — Every live-performance number is a return on 10-percent notional reported as account return: the committed archive contradicts its own headline by 43 points and dates a ~1,177-share hidden short, and no node cites it
The one committed record of real (paper) execution, data/live_runs/archive_2026-06-18_pre_clean_run/, is cited by ZERO of the web's 360 nodes - grep for live_runs or archive_2026 in RESEARCH_WEB.md returns nothing. Opening it settles three things. (1) A UNIT ERROR ~10x. live/trader.py:731 _signed_return computes (exit_price - entry_price)/entry_price, a PRICE return on the position; the position is 10 percent of equity (live/state.py:346-347, position_pct = 0.10). But five call sites treat that number as an ACCOUNT return: live/dashboard.py:56-62 compounds it multiplicatively, live/state.py:363 sums it, plus tools/ctx.py cmd_perf, ops/analyze_run.py and tools/live_backtest_reconciliation_study.py. Meanwhile src/backtest/runner.py:248-251 does it correctly (position = capital*fraction; pnl = position*r; capital += pnl), as does the gap study at POSITION_FRACTION = 0.10 - so the backtest-versus-live reconciliation is unit-inconsistent by an order of magnitude. Recomputed in account units on all 65 rows: the dashboard's PROD figure is +3.126 percent, not the +35.203 it displays; the ALL bucket is +3.149 not +35.411; and the CONFIRMED-fill bucket that ctx perf labels HONEST EDGE is +0.045 percent, not +0.205. THE FLAT VERDICT SURVIVES - +0.045 is still flat, so this does NOT overturn F43 or D6 - but the ~24x ALL-versus-CONFIRMED gap the web tracks is measured in the wrong units, and the headline a reader sees is 35 rather than 3 before any exit-type argument is even made. (2) THE ARCHIVE CONTRADICTS ITSELF BY ~43 POINTS, in two files one directory apart. metadata.json stores dashboard_compounded_pct 35.2026; account_snapshot.json stores equity 93515.09 against a sizing-implied starting equity of about 102,025, i.e. -8.34 percent. live/dashboard.py:762-765 computes both in the same handler, so the UI renders +35 percent and 3,515 on one page. (3) A ~1,177-SHARE HIDDEN SHORT, datable. The live sizing chain is invertible - qty = int(equity * 0.10 / bar_close) - so every entry's share count reads back the trader's own equity. VERIFIED EXACTLY on the one row with ground truth: 93515.09 * 0.10 / 81.16999816894531 = 115.20893447, floor 115, and the event log records 'Entry placed: LONG 115 TQQQ @ 80.98'. Independently, cash minus equity = 188828.35 - 93515.09 = 95313.26 = 1177.4 shares at 80.95, implying a short of that size while position_snapshot.json is an empty list. The final monitor event confirms it: 'Manual reconciliation: broker flattened to 0 (covered -1059 TQQQ short @~80.72, which included the bot's phantom 115-long entry @80.98 placed 16:32Z)'. Sizing-implied versus ledger-implied equity diverges past the pre-period noise band (n=58, median +102, sd 827) starting 2026-05-21, reaching -13,303 by 2026-05-28; between 2026-05-21 and 2026-05-27 the bot placed NO orders yet equity fell 6,146 while TQQQ rose. OPERATIONS.md:81 mentions 'a state desync even let the bot trade on top of a hidden short' as prose - the archive lets you SIZE and DATE it, and shows the short predated 06-17 by at least three weeks rather than being created that day. NOT ESTABLISHED: the mechanism. Four ~23-second duplicate exit-path event pairs exist and two reach broker.cancel_and_close with only one ledger row each, demonstrating ~274 shares of unrecorded sells - about 23 percent of the short. Double-filling OCA brackets is the leading hypothesis and the repo already suspects it (tools/diagnose_brackets.py), but this data cannot test it. LIMITS: shallow clone, so the archive's commit b37a8a8 is absent and I cannot prove the sizing formula is the code that ran in March-May 2026 - only that it round-trips against the 06-17 snapshot and agrees within 0.8 percent across 58 pre-period trades. Single run, n=65, one instrument, nine weeks; nothing here is a statistical claim about edge.
Links: [[F43|relates]] · [[D6|relates]] · [[F28|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@65491e5, 2026-07-25_

### F161 — The auditor degraded the metric it built: this session's 19 nodes raised absent-everywhere from 4.5 to 8.0 percent, and the normalisation ratio's drift tripped NUM-00's own executable caveat
A self-referential result that only became visible because the caveat was executable. NUM-00 (E113/F142) measured the corpus at 328 nodes / 2388 figures, with 4.50 percent of figures absent from every research doc and a normalisation effect of 1.87x (8.40 versus 4.50). Re-measured after this session's additions: 351 nodes / 2834 figures, absent-everywhere 8.00 percent, normalisation effect 1.38x (11.00 versus 8.00). TWO DISTINCT MOVEMENTS, both caused by my own writing. FIRST, absent-everywhere NEARLY DOUBLED, from 4.50 to 8.00 percent. My ~19 finding nodes quote heavily measured values - line numbers, leaf counts, share counts, exact p-values - and those live in the WEB and in commit messages, not in any docs/research/*.md file. So the auditor made the corpus's own citation gap materially worse by exactly the metric it built to expose it, which is the same defect F142 charges against D6 and the 143 uncited nodes. The honest response is not to exempt audit nodes: a finding that quotes 30 figures and cites no document is uncited whoever wrote it. SECOND, the normalisation ratio FELL from 1.87x to 1.38x, and this is not a defect but a property of the statistic - the ratio tracks how much of the corpus was written with U+2212 versus ASCII hyphen, and a batch of same-author nodes written through note.py (which produces ASCII) dilutes it. The lab's docstring now records BOTH measurements with their corpus sizes and states that the multiple is corpus-dependent rather than a constant. HOW IT SURFACED, which is the point worth generalising. The drift was caught by tests/test_numeric_provenance_lab.py::LimitsTests, a test written earlier in this session to pin the lab's own SELF-CRITICISMS rather than its result, on the theory that a caveat should be as executable as a finding. It failed with 'normalisation stopped mattering - re-measure', i.e. the guard fired for the right reason and named the right remedy. The fix followed the message rather than the convenient path: re-measure and record both vintages, and re-scope the assertion from a numeric BAND to materiality-plus-direction, since a band failed for corpus growth rather than for the defect it guards. That is the concrete demonstration of this session's recurring rule (F153/F154) - an invariant a repo cannot check is a belief - applied to a caveat rather than to a claim.
Links: [[F142|refines]] · [[E113|relates]].
_— captured claude/research-continuation-ca1242@65491e5, 2026-07-25_

### E117 — F25-TIME empirical study of Form 25 delisting-notification timing on the committed 2023 SEC fixture
First SUBSTANTIVE empirical study on the committed SEC fixtures rather than a meta-audit of the corpus. tools/form25_timing_lab.py reads docs/research/data/ca_clock100_form25_2023.json - a SHA-256 pinned fixture holding a 1,141-row census of 2023 25-NSE master-index rows plus a 100-row sample drawn 25-per-quarter by lowest SHA-256 rank, with EXACT SEC acceptance seconds (observation_time_quality exact_sec_acceptance_second), not inferred times. Stdlib only, offline, writes nothing. THREE SAMPLING-FRAME CHECKS FIRST, established rather than assumed because every descriptive claim from this fixture inherits them, and all three came back negative for bias. (a) Issuer diversity: 99 unique issuers in 100 filings against a census where 103 issuers file more than once; under a uniform 25-per-quarter null over 20,000 draws the mean is 95.76 and P(unique >= 99) = 0.076 - high-ish but NOT significant. (b) Exchange mix tracks the census closely on every venue (Nasdaq 46.0 versus 45.9 percent, NYSE 33.0 versus 35.8). (c) Design weights: the draw is EQUAL-ALLOCATION on UNEQUAL strata (census quarters 291/262/261/327, 25 sampled from each), so it is not self-weighting and carries a 1.25x rate ratio between Q3 and Q4; but reweighting every reported attribute by census_q/25 moves the largest share by only 0.69 pp, far inside the plus-or-minus 5 pp sampling noise at n=100, so the raw percentages ARE readable as census estimates. That last check is the one worth keeping - the design is non-self-weighting in principle and benign only because the attributes happen not to vary by quarter, which is a fact about this fixture rather than a property of the design. EXACT TESTS THROUGHOUT (no scipy): a hypergeometric one-sided tail, used because several strata have cells below 5 where the asymptotic chi-square is invalid. A BUG IN THAT TEST WAS CAUGHT AND FIXED during the work: the support's lower bound was written max(0, col1 - b) instead of max(0, row1 + col1 - n), which in small strata can exceed the OBSERVED cell, empty the summation and return p = 0 exactly. A p-value of zero is impossible since P(X >= a) >= P(X = a) > 0, and that impossibility is what exposed it - it was showing 0 for the debt_or_note and other_or_unknown strata. Every p-value is now cross-checked against an independent brute-force enumeration over all tables with the same margins, agreeing to 1e-12, and a test asserts no p-value is ever 0 or above 1. 11 tests. See docs/research/F25TIME_form25_timing.md.
Links: [[D13|relates]].
_— captured claude/research-continuation-ca1242@4fe2dc4, 2026-07-25_

### F162 — A delisting notification's public timestamp is set by the FILING EXCHANGE, not by the issuer, security or reason: Nasdaq batches post-close, the NYSE family files intraday
First substantive empirical result from the committed SEC fixtures (E117), on 100 sampled 2023 Form 25 (25-NSE) filings with exact SEC acceptance seconds. THE EFFECT. Nasdaq's acceptance times cluster hard after the close - median 16:06 Eastern, with 25 of its 46 filings in the 16:00 hour alone plus 3 more at 17:00 - while the NYSE family files across the session with no spike, median 11:11 Eastern. Pooled, 28 of 46 Nasdaq filings are post_close against 3 of 54 for everyone else: Fisher exact one-sided p = 1.09e-09. IT IS NOT A SECURITY-MIX ARTIFACT. Stratifying by security family, every stratum points the same way and the warrant/right/unit stratum settles it on its own with composition held fixed - 22 of 26 Nasdaq post-close versus 1 of 14 for the rest, that is 85 percent versus 7 percent at p = 2.39e-06. The remaining strata (common_equity 3/17 versus 0/14 at p=0.151, debt_or_note 2/2 versus 1/9 at p=0.0545, other_or_unknown 1/1 versus 1/16 at p=0.118) all lean the same direction but lack the N to reach significance individually, and are reported as such. WHY IT MATTERS. Form 25 acceptance is the natural event-study anchor for a delisting, and any study that uses it while POOLING EXCHANGES is mixing two different experiments: a Nasdaq delisting is released into an after-hours market and is first tradable at the next open (an overnight gap), while an NYSE delisting prints into a live session and is tradable immediately. Which experiment a given delisting lands in is assigned by the FILER, not by anything about the event, so exchange is a confound for any outcome that depends on release timing - overnight versus intraday drift, first-print slippage, gap-through-stop risk (the mechanism F47/F50 study on the trading side). Condition on exchange or split the sample. SCOPE DISCIPLINE: this is a mechanical fact about how two venues process filings, not a claim about information content, predictability or tradability. The fixture labels itself descriptive_sampling_frame_not_alpha_evidence and nothing here changes that. LIMITS: n=100, one year, one form type; the market_window classification is taken as given rather than re-derived. The sampling frame was validated first on three independent axes (E117) and passed all three, which is what licenses reading these shares as census estimates.
Links: [[E117|evidenced_by]].
_— captured claude/research-continuation-ca1242@4fe2dc4, 2026-07-25_

### F163 — The corporate-disclosure clock is shaped by market hours and the exchange's administrative clock is not, which makes the delisting manifest's own who-filed-first statistic uninformative
Independently verified by me against docs/research/data/ca_clock100b_evidence_manifest.json (sha256 88b075d2c4913410ca3a96ae7d958880274a625d4c325845601b20eb5500f410, confirmed), 31 delisting chains carrying exact SEC acceptance seconds on BOTH legs: 31 exchange-filed Form 25s and 80 issuer-side filings across 26 distinct issuer CIKs. THE HEADLINE, reproduced independently. Scanning every 6.5-hour window on a 5-minute grid across the observed span - a scan never told where the trading session is - the MOST DEPLETED window for issuer filings starts at 09:30:37, and the five most depleted starts all fall in 09:15 to 09:35. That is the US equity regular session, recovered to the minute. In-session shares: issuer 13 of 80 = 16.2 percent against exchange 16 of 31 = 51.6 percent, Fisher exact one-sided p = 2.7e-04 at the filing level. The same scan on the EXCHANGE leg puts its minimum at 10:28, not at the open - the exchange's back-office clock is not organised around market hours. NOT A COMPOSITION ARTIFACT: within 8-K alone, the dominant form, the in-session share is 3 of 37 = 8.1 percent, and foreign-issuer 6-K is the least avoidant at 6 of 16. NOT A CLUSTERING ARTIFACT: drawing one filing per issuer CIK over 20,000 resamples (26 clusters, seed 101) gives a median of 5 in-session against a uniform-on-span expectation of 13.9, with a 95 percent band of [3,8]. THE CONSEQUENCE, which is the part that matters for this corpus. The manifest's own summary reports primary_material_source_order as 13 issuer-first against 9 exchange-first. That ordering is a nearest-neighbour statistic by construction, and because the two legs are governed by DIFFERENTLY SHAPED clocks, the split is what two unrelated processes convolve to rather than evidence about who disclosed first. Verified two ways: a selection-respecting null that resamples the Form 25 time-of-day from the empirical exchange clock, holds its calendar date fixed and re-runs the selection (100,000 draws, seed 31337) gives median 13 with a 95 percent band of [10,16] against the observed 13, P(null >= observed) = 0.63; and an exact Poisson-binomial over the 17 same-day pairs gives E = 8.81 against observed 11, exact two-sided p = 0.26. TWO HONEST QUALIFICATIONS. First, the p-values are CONSTRUCTION-DEPENDENT: an independent implementation of the same two nulls returned 0.36 and 0.52 where mine returned 0.63 and 0.26. Both implementations land far from significance, so the VERDICT is robust while the specific number is not - quote the conclusion, never the p-value. Second, NOVELTY: that issuers disclose outside trading hours is a long-established institutional regularity, not a discovery here. What is specific to this dataset is the CONTRAST with the exchange's administrative clock and the consequence for the manifest's ordering statistic. TWO INCIDENTAL FACTS, both verified exactly: EDGAR's acceptance-to-file-date rollover is bracketed in (17:30:14, 17:47:43] - a filing accepted at 17:30:14 still received a same-day filed_on - and 3 of 111 filings (2.70 percent) are mis-dated by one calendar day if events are keyed on filed_on rather than accepted_at; and 6 of 80 issuer filings land in the first 10 minutes of the 06:00 EDGAR day, on 6 different dates, consistent with a queue flush rather than one issuer's burst. LIMITS: 31 chains, 26 issuers, one year; the 80 issuer filings are the top-8 by form-priority times proximity within a window around each Form 25, so this establishes session-avoidance for DELISTING-ADJACENT disclosures in this corpus, not for all 8-Ks; and the exchange leg is 31 filings from only 4 filer CIKs, so it is clustered too.
Links: [[F162|relates]] · [[E117|relates]].
_— captured claude/research-continuation-ca1242@6fef2fb, 2026-07-25_

### F164 — F16's code bridge is now guarded: the entry signal is verifiably mean-reverting, buying bars that follow declines, and a momentum flip would be caught
Autonomous-loop cycle 1, selected by tools/research_backlog.py as the highest-scoring open item (unguarded code-claim, score 0.56). F16's bridge in context_map.json asserted that generate_trades 'exploits' daily mean reversion, with no guarded_by test - the exact class of prose-claim-about-code that this session repeatedly found rotting while the code moved underneath it. SCOPE, stated because half of F16 is not testable offline. F16 makes two claims: that MARKETS mean-revert (lag-1 ACF of SPY -0.117 at t -6.4 and similar), which is NOT decidable here because market-data hosts are network-blocked and the caches are empty stubs; and that THE ENTRY SIGNAL exploits it, which is decidable right now because it is a statement about the sign of a function this repo defines. Only the second is guarded, and the test says so explicitly so a reader cannot over-read it. MEASURED on a synthetic mean-reverting series (n=1200, seed 20260725, explicit negative lag-1 component so both extremes occur often enough to measure): long entries follow prior bars averaging -0.248 percent, against an unconditional bar of +0.017 percent, while short entries follow +0.152 percent. Clean directional separation - the signal genuinely buys weakness and sells strength. THE GUARD IS BIDIRECTIONAL AND ITS LOAD-BEARING ASSERTION IS THE SELECTIVITY ONE. Asserting that a hand-built oversold bar fires long would be weak, because it passes on a signal that fires on everything; asserting that entries are concentrated after DOWN moves relative to up moves is the property that actually distinguishes mean reversion from momentum, and it is the one a rewrite would break. A negative control synthesises exactly that rewrite - inverting the signal so it buys strength - and confirms the assertion rejects it, because a guard that cannot fail is not a guard. Failure messages tell the maintainer to supersede the WEB node and re-baseline rather than edit the test. With this registered, ctx claims reports 0 UNGUARDED across all four implemented_in claims. 6 tests; suite 889.
Links: [[F16|relates]].
_— captured claude/research-continuation-ca1242@fd6c3e4, 2026-07-25_

### F165 — Open decisions can be made to announce their own completion: D2 is now guarded by tests that FAIL when it is implemented, not when it is violated
Autonomous-loop cycle 2, selected by tools/research_backlog.py (unguarded code-claim, score 0.56). D2 is an OPEN decision - 'make the sweep select on rolling-origin OOS, not single-split holdout; needs a design pass' - bridged to walk_forward_optimize with no guarded_by test. That is a different guarding problem from a Finding: there is no result to protect, so the useful move is to make the decision self-announcing. VERIFIED CURRENT STATE, both halves. D2's PREMISE holds: src/optimization/walk_forward.py:120 walk_forward_optimize takes separate train_months=18 and test_months=6, loops over windows, and its docstring describes 'For each rolling window: enumerate, select on the training slice, apply the winner to the out-of-sample test slice' - genuinely rolling-origin, not a single split. D2's TARGET is genuinely unmet: sweep.py contains ZERO references to walk_forward, and neither does src/optimization/sweep_scoring.py, so the sweep still selects on its own lens. So D2 is correctly open rather than stale-open. THE GUARD INVERTS THE USUAL DIRECTION. Rather than failing when a claim is violated, D2IsStillOpenTests fails when the decision is SATISFIED: the moment sweep.py or sweep_scoring.py references walk_forward, the test fails with a message saying D2 appears IMPLEMENTED, supersede it with a Finding recording what was wired, and re-baseline every stored sweep result - because those were selected under the old single-split lens and are not comparable. Negative control confirms it fires: appending a walk_forward import to sweep.py trips the assertion. A third test pins that main.py still exposes the walk-forward mode, because D2 says 'promote', not 'build' - if the lens became unreachable, D2 would be mis-stated rather than merely open, and that is a different correction. WHY THIS PATTERN MATTERS BEYOND D2: the web carries roughly 50 hypotheses and decisions that no Finding ever closed (F151), which biases the project's self-measured revision rate toward looking stable (F133). A decision that fails a test when it is satisfied cannot quietly stay open, and the pattern generalises to every other open D or H node with a code bridge. 8 tests; suite 897.
Links: [[D2|relates]] · [[F151|relates]].
_— captured claude/research-continuation-ca1242@4e65f39, 2026-07-25_

### F166 — Three self-announcing guards now cover the web's live-deployment preconditions: F6's fragile-instrument claim fails the moment the deployment moves off it
Autonomous-loop cycle 3. F6 states that the live instrument TQQQ is fragile - clearing significance only on the default split at pooled t about 2.1, collapsing to t=0.37 on recent-only data, with a losing fold - and concludes that the live paper deployment is on a fragile leveraged instrument. Its bridge to config.ACTIVE_MODE and config.STOP_LOSS_PCT_TQQQ_HOURLY had no guarded_by test. SPLIT THE CLAIM, as with F16. The STATISTICAL half - the t-statistics and fold behaviour - is a market claim, not decidable offline with hosts blocked and caches empty, and nothing here tests it; a test asserts the docstring says so. The PRECONDITION is decidable and is the whole reason F6 is actionable rather than historical: the deployment is still pointed at TQQQ, with the stop F6 reasons about. Verified: ACTIVE_MODE=TQQQ_HOURLY, LIVE_SYMBOL=TQQQ, STOP_LOSS_PCT_TQQQ_HOURLY=0.005, LIVE_PAPER_MODE=True. THE GUARD IS SELF-ANNOUNCING and fails when the deployment MOVES OFF the instrument, which matters more than usual because F6 drives D1 and D3 - if the deployment changes, three nodes need review at once and nothing else in the repo would say so. Negative control confirms it fires: setting ACTIVE_MODE to SOXL_HOURLY trips the assertion. One test also pins LIVE_PAPER_MODE, on different grounds from the others: if that ever flips, a node documenting a FRAGILE instrument would be describing a real-money position, so the message says stop and escalate rather than supersede. A cross-reference notes that the F157 startup invariant requires ACTIVE_MODE and LIVE_SYMBOL to agree, so those two tests should fail together - if only one fails the config is incoherent and the trader refuses to start. THE PATTERN ACROSS CYCLES 1 TO 3 is now explicit and worth naming: a web claim about markets is usually not testable, but its PRECONDITION in code almost always is, and guarding the precondition is what converts a finding from a historical note into something that tells you when it has gone stale. 6 tests; suite 903.
Links: [[F6|relates]] · [[F165|builds_on]].
_— captured claude/research-continuation-ca1242@18b0e26, 2026-07-25_

### F167 — The poison-cache class is now closed repo-wide and enforced by a sweep, and the F12 morning-only artifact has a partial-fetch guard at its source
Autonomous-loop cycle 4. F148 was top-ranked again but stays deferred pending sign-off, so the loop took the runner-up: the four labs still fetching market data without the validated cache. ROUTED THROUGH tools/data_cache.py: tips_sleeve_study.load_px, income_universe_study.load, bond_ladder_study.load_yields and load_etfs, correlation_regime_study.load_shiller and load_gspc. Six loaders across four files. Two carried PARTIAL guards that looked adequate and were not - tips_sleeve and bond_ladder both checked that every ticker COLUMN was present, which a header-only stub passes because it has all its columns and zero rows. VERIFIED END-TO-END, not by inspection: planting a header-only stub at each cache path and calling each loader, all four refuse - three raise PoisonedCacheError naming the file and the rm remedy, and bond_ladder takes its column-check path instead, deletes the stale cache, attempts a re-fetch, fails offline and raises EmptyFetchError. Critically, afterwards ALL SIX cache paths are absent: no loader re-armed the trap on the way out, which is the property that actually matters since writing the stub is what poisons every future run. income_universe needed care because it holds TWO panels from one fetch; they are now validated and written together, since a partial write leaves the pair inconsistent, which is worse than a miss. Shiller gets a column check too, because a blocked fetch of a raw GitHub CSV can return an HTML error page that parses as a small frame rather than an empty one. ENFORCED BY A SWEEP RATHER THAN A LIST: a new test scans every tool that both fetches market data and writes a CSV, and fails on any that does not use the guard, so a NEW lab re-introducing the pattern is caught rather than silently joining the exceptions. A companion test asserts the sweep matches more than three files, because a detector that matched nothing would pass vacuously. The sweep immediately earned itself by finding two files I had not routed. THE SECOND OF THOSE IS THE INTERESTING ONE. tools/fetch_fullsession.py already refused EMPTY fetches, so it looked fine, but it wrote PARTIAL ones without complaint - and its partial 710-day fetch returning morning-only bars is the documented root cause of the entire backtest-versus-live mismatch (F12/F13), the artifact that produced the superseded Sharpe 25-94 headline. It now refuses any panel under 500 bars or under 5 bars per day, on the reasoning that a US session is 7 hourly bars while the F12 panel averaged about 3. So the guard sits exactly where the project's largest data defect originated. The other file was data_cache.py matching its own detector; both exemptions are recorded WITH reasons, and a test asserts no exemption is reasonless, because an unexplained entry is how the original footgun survived. Suite 906.
Links: [[F144|builds_on]] · [[F12|relates]] · [[E114|evidenced_by]].
_— captured claude/research-continuation-ca1242@5cf233e, 2026-07-25_

### F168 — H50 was substantially researched and nobody wired the closure: it reads not-yet-researched while carrying seven dependents, a refining Finding and a published Decision
Autonomous-loop cycle 5, selected as the highest-leverage uncited node (5 figures, 0 reachable docs, 7 reliance dependents). H50 is the index-membership research proposal IDX-01, and its own body still reads 'noted for later and not yet researched'. That is false, and the material to retire it already exists. WHAT WAS ACTUALLY DONE AGAINST IT. E97 built the IX-00 source contract and a March 2026 S&P 500 event-clock pilot measuring four additions and four deletions against SPY on adjusted OHLCV with a normalized input SHA. E98 replicated the same tool on Nasdaq's 2025 annual reconstitution at exact publication 2025-12-12 20:00 EST, six additions and six deletions against QQQ, again SHA-pinned. F108 then produced a substantive result that explicitly refines H50: an honest event row needs public-announcement/first-tradable, implementation-session close, and effective-session open as SEPARATE clocks, and gross add/delete labels mix offsetting family flows - three of four March 2026 additions migrated from the MidCap 400 while all four deletions migrated to the SmallCap 600. And docs/research/IX00_index_membership_event_lab.md records three complete batches plus a partial survivorship diagnostic and reaches a DECISION: proceed to a rights-cleared point-in-time event ledger, reject a pooled directional rule. THE DEFECT IS STRUCTURAL, NOT FACTUAL. H50 has seven incoming edges - E97 and E98 build_on it, F108 refines it, H56 through H59 build on it - and ZERO resolves edges, even though 'resolves' is in the schema's edge vocabulary. So the closure mechanism exists and was simply never used, which is why the backlog engine still ranks H50 as uncited high-leverage work and why F151's count of 50 dead-end hypotheses is inflated by cases like this one: the web records hypotheses far more readily than it retires them, and here the retirement material was sitting in three nodes and two documents. WHAT GENUINELY REMAINS OPEN, separated from what is done, because 'partially resolved' is only useful if the parts are named. DONE: point-in-time membership history with distinct clocks, and the flow-treatment correction. PARTIALLY DONE: abnormal return and volume around the events, measured descriptively - E97 and E98 both state in their own text that they have no matched controls, no causal identification and no p-values. NOT DONE: matched eligible non-event controls, index and sector baselines, separation of mechanical index-fund demand from information, anticipation and survivorship handling, and the reversal horizons H50 asks for at 1, 5, 20 and 60 sessions. STILL GATING: membership data rights and complete historical candidate universes, which IX-00's decision explicitly routes around rather than solves. So H50 should be read as PARTIALLY RESOLVED on the descriptive and clock-decomposition half, with the causal half untouched and rights-gated - not as unstarted.
Links: [[H50|resolves]] · [[F108|builds_on]] · [[E97|relates]] · [[F151|relates]].
_— captured claude/research-continuation-ca1242@3bb389c, 2026-07-25_

### F169 — Two independently-built SEC clock artifacts agree, and their one tension pins a real distinction: acceptance at 17:30:14 still filed same-day, so the cutoff bites on submission not acceptance
Autonomous-loop cycle 6. H45 was the top uncited node; unlike H50 it is GENUINELY open - E96 did the FD-00 source-contract audit and preregistration but states in its own text that no predictive edge is claimed and that corpus-scale backfill was not attempted because the SEC rejected this environment's automated bulk requests. So the predictive test is data-gated, not merely unstarted. What IS available offline is FD-00's committed fixture, and cross-checking it against a second artifact produced a result neither could give alone. TWO ARTIFACTS THAT HAD NEVER BEEN COMPARED. fd00_sec_event_clock_fixtures_2026.json is a STATED CONTRACT: eight hand-authored expectations about how acceptance time maps to filing date and market phase, built for 10-K/10-Q edge cases. ca_clock100b_evidence_manifest.json is MEASURED DATA: 111 real filings with exact acceptance seconds and their actual filed_on, from Form 25 delisting chains. Neither references the other, which makes them a mutual check - a contract nobody measured against, and a measurement nobody compared to the contract. RESULT: all seven timestamped FD-00 fixtures are CONSISTENT with the rollover bracket measured from the CA data, (17:30:14, 17:47:43] per F163. Nothing contradicts, and the fixture set covers both sides of the boundary, so the agreement is not vacuous. THE ONE TENSION IS THE INTERESTING PART. FD-00's fixture is NAMED after_1730_filing_date_rollover, encoding a 17:30 boundary - yet the measured data contains a filing ACCEPTED at 17:30:14 that still received a SAME-DAY filed_on. Both are true simultaneously only because the 17:30 cutoff bites on SUBMISSION while accepted_raw records ACCEPTANCE. That is exactly the distinction FD-00's own clock_policy flags as acceptance_is_not_public_availability, now with a worked example from real data rather than an assertion. It matters concretely: anyone keying events off accepted_raw and assuming a 17:30 cutoff will mis-date filings in the fourteen-second window this measurement exposes, and more generally across the seventeen-minute bracket. A CORRECTION TO MY OWN FIRST READ, recorded because the pattern is the point: I initially flagged the eighth FD-00 fixture as a schema defect for lacking market_phase. It is not one - post_acceptance_correction_contract carries null timestamps because it asserts a POLICY rather than an event, so it has no market phase to have. A test now pins it as contract-only so the same misreading does not recur. Guarded bidirectionally: an edit to EITHER artifact that breaks the agreement fails, with a message saying reconcile the two rather than edit the test.
Links: [[F163|builds_on]] · [[H45|relates]] · [[E96|relates]].
_— captured claude/research-continuation-ca1242@9e40e67, 2026-07-25_

### F170 — F148's timezone bug lands squarely inside F14's coarse edge regime, giving the backtest-live gap a SECOND mechanism that fixing the data path never removed
Autonomous-loop cycle 7. F14 decomposed the hourly edge by BAR-SAMPLING FREQUENCY rather than by time-of-day: QQQ AM at 3 bars/day gives +0.34 percent per month at Sharpe 3.72, PM at 4 bars/day gives +0.32 at 3.31, and ALL-DAY at 7 bars/day gives MINUS 0.05 at Sharpe MINUS 0.75. AM is approximately PM, so it is not a time-of-day effect; both vastly exceed all-day, so it is a sampling-frequency effect. F14's stated mechanism is arithmetic: RSI(7) over 3 bars/day spans about 2.3 trading days and captures multi-day mean reversion, while over 7 bars/day it spans about 1 day and captures intraday noise. THE CONNECTION NOBODY HAD DRAWN. F148 established that main.py applies a (9,16) gate to a UTC-NAIVE index, because fetcher.py converts to UTC-naive rather than Eastern. Recomputing the retention: the gate keeps 2 of 7 session bars in winter and 3 of 7 in summer. Those are exactly F14's coarse regimes - the summer retention of 3 bars/day IS the AM subsample F14 credits with Sharpe 3.72, and the winter retention of 2 bars/day is coarser still, spanning 3.5 trading days. So any hourly backtest run through main.py with the hourly filter nominally OFF is silently measuring F14's coarse regime, while the live bot trades the all-day 7-bars/day regime where F14 measures Sharpe MINUS 0.75. WHY THIS MATTERS MORE THAN EITHER FINDING ALONE. F12 and F13 attributed the backtest-versus-live gap to the DATA path - a 710-day yfinance fetch that returned morning-only bars - and that diagnosis was correct. This shows the ENTRY GATE independently reproduces the same artifact on CORRECT full-session data. So the two mechanisms are additive and the second one survives the first one's fix: repairing the fetch would not have removed the gap, which is a candidate explanation for why the discrepancy persisted after the data path was addressed. It also means the sign of the effect is predictable rather than mysterious - the backtest sits in the regime F14 measured as positive and the bot sits in the regime F14 measured as negative. RELEVANCE TO THE DEFERRED DECISION: this strengthens the case for fixing F148 rather than weakening it, because the bug is not cosmetic - it is the difference between measuring a regime with an edge and the regime actually traded. It does not change the deferral's reasoning, which is that the fix moves every published hourly number and needs a re-sweep. PINNED OFFLINE: the arithmetic is decidable and is guarded - gate retention of 2 and 3 bars, those retentions being at most 3 and therefore coarse, and the indicator-span ratio between the coarse and all-day regimes exceeding 2x. F14's Sharpe figures are NOT re-measured; market data is unavailable and they remain F14's.
Links: [[F148|builds_on]] · [[F14|relates]] · [[F12|relates]] · [[E112|evidenced_by]].
_— captured claude/research-continuation-ca1242@363f24b, 2026-07-25_

### F171 — The corpus has THREE citation modes, not two: 10 percent of nodes name a reproducing tool but no document, which a doc-only metric wrongly counts as uncited
Autonomous-loop cycle 8, and a REFINEMENT OF MY OWN F142. F45 surfaced as the top uncited node, which looked wrong on inspection: F45 carries an evidenced_by edge to E36, and docs/research/D6_bond_ladder_study.md exists. The reason the metric flagged it is that neither F45 nor E36 cites a docs/research path - E36 names the TOOL, tools/bond_ladder_study.py, instead. MEASURED ACROSS ALL 377 NODES: 11 cite a document only (2.9 percent), 74 cite both (19.6 percent), 39 cite a TOOL ONLY (10.3 percent), and 253 cite neither (67.1 percent). Of the 39 tool-only nodes, 16 name a tool that has a plausibly-matching document sitting in docs/research, so in those cases the evidence document exists and simply is not linked by path. WHY THIS REFINES F142 RATHER THAN OVERTURNING IT. F142's structural metric asked whether a node quoting figures can reach a study DOCUMENT, and reported 143 of 328 such nodes reaching none. That measurement stands - it was correctly scoped to documents. What it did not distinguish is that some of those nodes name a REPRODUCING TOOL, which is a genuinely weaker gap: a reader can regenerate the result, they simply cannot read the numbers off a written study. Naming tools/bond_ladder_study.py is not the same as naming nothing, and treating the two identically overstates how uncited the corpus is. It is also NOT equivalent to a document - the tool holds the method, not the figures, and per F144 many of these tools cannot run offline at all, so a tool citation can be a reproduction path that nobody can currently walk. THE ENGINE NOW DISCOUNTS RATHER THAN EXCLUDES. Tool-cited nodes stay in the backlog with leverage multiplied by 0.6, so they rank below genuinely uncited ones but are not hidden - excluding them would conceal a real if weaker gap, while ranking them equal would spend cycles on the more recoverable case first. The discount is written into the evidence string as 'names tool X' so it is auditable, and a test asserts no node is discounted without saying why, because a silent adjustment to a ranking is exactly the kind of thing that becomes invisible. DENOMINATOR WARNING, stated because these two numbers invite conflation: F142's 143 of 328 counts nodes WITH AT LEAST FIVE FIGURES that reach no doc; the 67.1 percent here counts ALL nodes citing neither doc nor tool. They are different populations and must not be quoted against each other.
Links: [[F142|refines]] · [[E113|relates]].
_— captured claude/research-continuation-ca1242@f703a29, 2026-07-25_

### F172 — F47's open parenthetical answered from committed data: healthy exits emit NO monitor event, so the event log is an exception log and cannot audit exits
Autonomous-loop cycle 9. F47 is a direct live observation - an overnight gap turned a 0.5 percent stop into a MINUS 4.007 percent realized loss - and it ends with an unanswered parenthetical: 'the exit wrote the trades table but emitted NO monitor_event (exit events may only fire on the fill-data-unavailable path?)'. That question is answerable offline from the committed archive, and the answer is YES. MEASURED on data/live_runs/archive_2026-06-18_pre_clean_run: 72 'Entry placed' events against 65 ledger trades, so entries log roughly one-per-trade. But the ledger's exit mix is bracket_exit 41, time_exit 9, target_hit 6, stop_hit 6, estimated_close 2, paper_reset 1 - and the ONLY exit-shaped messages in the entire event log are degraded conditions: 6 'Fill data unavailable - inferred target_hit', 6 'SOFTWARE STOP triggered', 4 'Time-exit fill unavailable - using reference', 3 'Fill data unavailable - marking pending_close', 2 'Pending close force-finalized after 3 retries', 1 'Manual reconciliation'. All 41 bracket_exit trades - the NORMAL path, and the plurality of exits - logged nothing at all. THE CONSEQUENCE IS THE FINDING. monitor_events cannot be used to audit exits, because the healthy path is invisible: anyone reading it would conclude the bot exits only abnormally. It is an exception log wearing the name of an event log, and its shape confirms that - 72 entries plus 55 'Unhandled on_bar exception' account for the large majority of its 149 records. That exception count is itself worth noting alongside F157, since a cycle lost to an exception never increments the live bar counter and silently extends a hold. F47'S OTHER SUBSIDIARY CLAIM ALSO VERIFIES. src/strategy/engine.py:353 reads exit_return = -stop - stop_slippage_pct - a constant expression consulting no bar data, so no gap can enter it by construction. Verified structurally by AST as well as by text: the stop branch's assignment references no open price. The understatement is therefore not a parameter choice that could be tuned away; the model has no term that can grow with the gap, so its error is bounded only by the size of the gap itself. On F47's own numbers that was 8x the configured stop. Guarded bidirectionally: if an exit event ever fires on a HEALTHY path the test fails and says so is an improvement but F47's parenthetical is now answered differently and should be updated, and if the stop branch starts reading a price the gap-model claim is stale.
Links: [[F47|refines]] · [[F157|relates]] · [[F160|relates]].
_— captured claude/research-continuation-ca1242@ed473f3, 2026-07-25_

### F173 — F110's dual-hash prescription is implemented and demonstrated, but the pairing covers fewer refreshes than the artifact invites
Checked offline against the six committed `docs/research/data/ix00_*.json` artifacts. Two things hold and one is narrower than it looks.

IMPLEMENTED. Four of the six carry `normalized_input_sha256` and `derived_result_sha256` side by side, plus a `fingerprint_contract` and a `refresh_audit`. The two without a hash block (`ix00_ndx_2023_revision_fixture.json`, `ix00_ndx_recent_complete_panel.json`) are a fixture and a panel, not event batches — identified rather than failed.

DEMONSTRATED. Every batch's `refresh_audit` records 3-4 DISTINCT `observed_exact_input_sha256` against IDENTICAL `paired_derived_result_sha256`. Vendor bytes moved on same-day re-fetch; the 0.001pp-precision decision hash did not. Both halves of F110 confirmed from committed data.

SCOPE CAVEAT. Each audit pairs only 2 derived hashes against those 3-4 observed inputs. F110's own wording is careful — 'reproduce exactly in PAIRED refreshes' — but the artifact reads at a glance as if every observed refresh produced the same decision, which is not what was measured. The unpaired refreshes are unmeasured, not shown-equal.

Guarded by tests/test_f110_hash_discipline.py (5 tests), which fails in BOTH directions: if the vendor becomes byte-stable (F110 goes stale), if decision-level reproducibility breaks (F110's load-bearing half fails), or if the pairing widens to cover every refresh (this caveat stops applying).
Links: [[F110|supports]] · [[E99|relates]].
_— captured claude/research-continuation-ca1242@708ca8f, 2026-07-25_

### F174 — F19 survives, but only under the honest fill rule: optimistic mode INVERTS the exit comparison, and the wedge scales with the same-bar ambiguous share
F19's bridge (compute_trade_returns + STOP_LOSS_PCT_TQQQ_HOURLY) was unguarded. It turns out to be mechanisable inside the repo's own engine: widen the band past any bar and every trade falls to the `time_exit` branch, which IS an N-bar horizon exit. Same entries, same bars, same function, one parameter changed — F19's within-comparison, re-runnable offline on synthetic data.

THE FIRST PASS LOOKED LIKE A REFUTATION. The band exit BEAT the horizon exit and got BETTER as intrabar noise rose (+21 -> +76 bps as P(bar range > stop) went 0.76 -> 0.97). That is backwards from every mechanism F7 and F19 describe.

THE CAUSE WAS THE FLAG, NOT THE MECHANISM. `worst_case_ambiguity` decides who wins when one bar's range contains BOTH barriers. Under the honest rule (stop wins — what `realistic` and `harsh` ship) the identical trades go +16 -> -32 bps, monotonically DOWN, crossing below the horizon exit: F19's sign flip, confirmed. Under the optimistic rule (target wins — what `optimistic` ships) they go monotonically UP. Measured wedge vs ambiguous share, same frames:

  amb share    optimistic   worst-case   horizon
     1.0%         +15.4        +13.8      +14.4
     9.2%         +26.8        +13.0      +14.4
    22.8%         +35.7         +1.5      +14.4
    50.4%         +59.1        -16.5      +14.4
    72.0%         +75.9        -32.1      +14.4

So on identical entries the FLAG chooses the conclusion, and the wedge grows monotonically with the ambiguous share (it is <5 bps when almost no bar is ambiguous — the negative control). This is a mechanism for CLAUDE.md's stale-performance warning: optimistic mode does not merely omit costs, it can reverse the ranking of two exit rules.

SCOPE. The ambiguous share is a property of the DATA, and no real bars are committed (`data/cache/` empty, the vendor CSVs gone). Nothing here says what that share IS for TQQQ hourly at its configured 1.0%/0.5% band. The claim is conditional: wherever the share is large, the reported result is chosen by the flag. Measuring it on real bars is open.

Guarded by tests/test_f19_exit_lever_bridge.py (12 tests, bidirectional), now wired as `guarded_by` on the F19 bridge.
Links: [[F19|supports]] · [[F7|supports]] · [[E10|relates]].
_— captured claude/research-continuation-ca1242@bf2e098, 2026-07-25_

### F175 — CORRECTION to F20's mechanism: estimator variance is driven by the 30-trade WINDOW, not by 'estimator shape' — and the project's own 'rolling' Kelly does not roll
F20 concluded that a continuous half-Kelly hurts while the project's 4-tier win-rate step is Sharpe-neutral, and attributed it to **'the estimator SHAPE matters'** — continuous chases the noisy `b = avg_win/avg_loss` (CV 0.77), the tier never computes `b` (CV 0.23). The conclusion holds. The mechanism does not survive isolation.

REPRODUCED, THEN DECOMPOSED. Transcribing F20's own estimator from `tools/mr_daily_lab.py::cmd_kelly` (half-Kelly, W=30 trades, cap 1.0) and varying one factor at a time on synthetic trade sequences:

  estimator                      CV @ wr .45 / .50 / .55
  lab continuous W=30 cap 1.0       1.79 / 1.10 / 0.88
  lab continuous W=30 cap 0.20      1.79 / 1.06 / 0.82   <- 5x tighter cap: no change
  lab continuous W=200 cap 1.0      1.42 / 0.50 / 0.38   <- window: -9% / -47% / -72%
  tiered 4-step                     0.49 / 0.37 / 0.27

A 5x tighter cap moves the variance by <10%. Widening the estimation window cuts it by half or more. The instability is in estimating a RATIO from few trades, not in continuity. (The wr .45 exception is kept, not tuned away: with no edge, Kelly's `max(...,0)` pins the fraction to zero >50% of the time, and a zero-inflated series' CV is set by the zero share, which more data cannot shrink.)

THE DECISIVE CASE. `position_fraction(kelly_mode='rolling')` passes its ENTIRE history to `estimate_stats_from_backtest` with no truncation, and `runner.py:197` backs it with an unbounded `deque()` whose comment reads 'rolling window for adaptive Kelly'. So the project's continuous Kelly is an EXPANDING-window estimator, and at wr .50/.55 it is LESS variable than the 4-tier step it is cast as the noisy alternative to. F20's ordering reverses for the estimator the repo actually ships. Continuity is not the discriminating property; sample size is. `BACKTEST_MODES['realistic']` also advertises 'rolling window Kelly' — accurate about lookahead, wrong about rolling.

(The TIER is unaffected: `recent_win_rate` slices `[-lookback:]` internally, so its window is real. Only the continuous path expands.)

AND ON THE DEFAULT PATH NONE OF IT RUNS. `position_fraction` returns `fixed_pct` before the adaptive block, and the shipped config is `POSITION_SIZING_MODE='fixed'`, so `runner.py` assembles `adaptive_params` from nine config knobs and hands them to a function that has already returned — with `USE_ADAPTIVE_KELLY=True`. Same family as F145: a flag that is on while governing nothing.

Guarded by tests/test_f20_kelly_estimator_bridge.py (16 tests), wired as `guarded_by` on the F20 bridge. Scope: F20's Sharpe numbers rest on 12yr of real daily data and are NOT re-tested here — only the estimator arithmetic is.
Links: [[F20|refines]] · [[F145|supports]].
_— captured claude/research-continuation-ca1242@87676c5, 2026-07-25_

### F176 — F21's recommended build was never run: the lab vol-targets the arm that LOST, and no sizing code implements vol-targeting at all
F21 recommends 'EQUAL-WEIGHT diversified daily-MR sleeves ... + VOL-TARGETED (not Kelly) sizing -> ~Sharpe 0.66', bridged to `src/strategy/sizing.py::position_fraction`. Three source-checkable problems, all confirmed.

1. THE BRIDGED FUNCTION CANNOT DO IT. `position_fraction`'s modes are `fixed`/`kelly`/`kelly_clamped`. No vol-target branch, no config knob, and `src/strategy/sizing.py` never computes realized volatility. `vol_target` is defined only in `tools/` — twice, in two labs, with different parameters. Same pattern as F26: aspirational design recorded as if it were running code, this time in the sizing layer.

2. THE RECOMMENDED COMBINATION WAS NEVER MEASURED. `mr_daily_lab.py` calls `vol_target` exactly twice: on `swp`, the trailing-Sharpe-WEIGHTED portfolio (line 179), and on a single QQQ sleeve (line 211). The equal-weight portfolio `ew` is never vol-targeted. So F21's headline composes two rows of one table that never met — the 0.66 is equal-weight WITHOUT vol-targeting, and the vol-target arm was applied to the weighting scheme that lost (0.42). Whether equal-weight plus vol-targeting beats either is unknown. (F20's separate 'vol-targeting helps, 0.56->0.67' is the line-211 single-sleeve QQQ result — a third scope again.)

3. F21's LAB CANNOT PRICE THE COST F40 FOUND DECISIVE. `mr_daily_lab.vol_target` has no `financing` parameter and caps leverage at 3.0; `tools/vol_target_study.vol_target` (behind F40) has one and caps at 2.0. F40 concluded the opposite of F21 — leverage is Sharpe-invariant, the measured lift is timing, and 2%/yr financing pushes the levered form BELOW the unlevered baseline. F21 and F40 contradict each other on vol-targeting with no edge between them in the web.

HONEST MAGNITUDES. The labs also differ on warm-up (`fillna(0.0)` vs `dropna()`; `perf()`'s dropna cannot remove injected ZEROS). Measured on a synthetic heteroskedastic series that is worth ~0.003 Sharpe and the leverage cap does not bind — recorded as structural discrepancies, not large ones. The one exact result: constant leverage leaves Sharpe unchanged to floating point, so any lift must be timing or cap-clipping, and omitting financing is a one-sided error that can only flatter a levered arm.

Guarded by tests/test_f21_vol_target_bridge.py (14 tests), wired as `guarded_by` on the F21 bridge. Scope: neither F21's nor F40's Sharpe numbers are re-tested — both rest on real daily data unreachable offline.
Links: [[F21|refines]] · [[F40|relates]] · [[F26|supports]].
_— captured claude/research-continuation-ca1242@afd01b2, 2026-07-25_
