# MONAD-quant — Research Idea Web

> A traversable graph of what we **know** (Findings), what we're **testing**
> (Hypotheses), how we **test** it (Experiments), and what we **decide** (Gates).
> Nodes link with `[[ID]]`. Walk it with `venv/bin/python tools/ctx.py web [NODE]`.
> Append nodes; supersede rather than rewrite. **Evidence-first:** a claim is only
> as strong as the Experiment behind it, and only OOS, leak-free, cost-aware
> numbers count as evidence (see [[E3]]).
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
The reframe holds only at a ~3-bars/day timescale ([[F15]]), NOT the hourly bot this gate was about.
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
single highest-value change is the EXIT ([[F17]]). (1-bars/day hourly note [[F15]] is the weaker, less
robust cousin; the daily horizon-exit result supersedes it as the recommended direction.)

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
F23 records a LIVE bug: momentum_signal/get_current_signal recompute RSI/MACD with hardcoded defaults, ignoring per-mode config, and the armed bot rides this path. ctx claims confirms F23 UNGUARDED. Open: write a test that ASSERTS the per-mode periods are ignored (flips F23 GUARDED) + add a guarded_by bridge; scope the config-routing fix on a branch without touching the armed path.
Links: [[F27|relates]] · [[F23|relates]].
_— captured development@1806b74, 2026-06-26_

### D7 — OPEN [ctx]: VD-2 — should F15 be formally superseded by F22? (contradicted-but-current limbo)
F15 ('edge real at ~3 bars/day') is status:current but contradicted by the more rigorous F22->D6, producing 2 live advisories (D1,D4). Its per-instrument measurement still holds; F22 overturns the actionable framing, and the contradicts (not supersedes) edge may be intentional. Open decision: tombstone F15 by F22 (and re-point D1/D4 to cite F22 first to avoid a stale-cite) vs leave it disputed-but-live; optionally escalate 'N current nodes contradicted by a later node' to a scored health deduction.
Links: [[F27|relates]] · [[F15|relates]] · [[F22|relates]] · [[D6|relates]].
_— captured development@1806b74, 2026-06-26_

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
