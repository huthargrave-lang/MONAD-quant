# MONAD-quant — Research Idea Web

> A traversable graph of what we **know** (Findings), what we're **testing**
> (Hypotheses), how we **test** it (Experiments), and what we **decide** (Gates).
> Nodes link with `[[ID]]`. Walk it with `venv/bin/python tools/ctx.py web [NODE]`.
> Append nodes; supersede rather than rewrite. **Evidence-first:** a claim is only
> as strong as the Experiment behind it, and only OOS, leak-free, cost-aware
> numbers count as evidence (see [[E3]]).
>
> **Headline (2026-06-19):** the mean-reversion engine has a small, genuine,
> structurally-explained edge **on un-leveraged broad indices** (QQQ/SPY,
> ~+0.3%/mo, Sharpe ~3–4, t>3) and is **structurally mismatched to the 3x
> leveraged ETFs the project was built around** ([[F7]], [[F4]], [[F9]]).

---

## Findings (established by an Experiment)

### F1 — Three numbers, three stories
Documented Sharpe 39–94 / +2–3.5%/mo (fantasy), holdout-selected +4–5%/mo (biased),
leak-free +0.1–0.34%/mo (honest). Only the last is trustworthy. See [[E1]], [[E2]], [[E3]], [[F2]], [[F3]].

### F2 — Holdout-selection bias inflates the sweep
`sweep.py` picks its winner BY the holdout score, so its "holdout" numbers are the
best-of-many on that holdout — biased. The +4–5%/mo for SOXL/LABU/TNA did NOT survive
de-biasing. Motivates [[H4]]. Evidence: [[E2]] vs [[E3]].

### F3 — The honest edge is small but real (and decaying)
Leak-free walk-forward ([[E3]]): QQQ +0.34%/mo Sh 3.74, TQQQ +0.18%/mo Sh 2.17, LABU
+0.15%, TNA +0.12%, SOXL +0.08% — sub-1% DD, ~90–112 OOS trades. Robustness ([[E4]])
shows the edge is **front-loaded into late 2025 and fades** in later folds. A near-zero-DD
~0.2–0.3%/mo vehicle, NOT a 2–3.5%/mo income engine. Bears on [[D1]].

### F4 — QQQ (un-leveraged) is the best risk-adjusted instrument — structurally
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

### F8 — The QQQ edge is a signal property, not an optimizer artifact
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

### F11 — Penalty-inversion selection bug (fixed)
The sweep scorer multiplied a NEGATIVE base by penalty factors <1, moving it toward zero —
i.e. it *improved* losing configs, so among net-negative candidates it preferred the
worst-behaved one. Guarded (penalties skip base ≤ 0). Mattered precisely in the no-edge
regime this research operates in. Fixed in commit 084f15e.

---

## Hypotheses

### H1 — RESOLVED: edge is sample-luck? → NO for QQQ, YES for TQQQ
Robustness ([[E4]]): QQQ robust (t 3.3–4.3, survives no-selection [[F8]]); TQQQ fragile ([[F6]]). Closed.

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
### E7 — OPEN: full-session data re-pull & re-validate
Resolve the morning-only caveat [[F10]]/[[H5]]. Pull full RTH hourly bars; re-run [[E3]].
### E8 — OPEN: noise-ratio instrument screener
`tools/instrument_screen.py` — rank a universe by `P(bar range > stop)` / noise_ratio to
find where the signal can work ([[H6]]), before spending sweep/validation time.

---

## Decisions / Gates

### D1 — Edge go/no-go (roadmap gate #1) — UPDATED
Net edge is ~0.2–0.34%/mo OOS — below the ~0.5%/mo income threshold, so this is NOT an income
engine. BUT it is a **genuine, structurally-explained, near-zero-drawdown high-Sharpe vehicle on
the right instrument** ([[F3]], [[F4]], [[F7]], [[F8]], [[F9]]) — exactly the "bond-ETF alternative"
the project set out to be. Verdict: **don't kill it — reframe it** as a capital-preservation /
high-Sharpe product AND **switch instrument focus from 3x ETFs to un-leveraged broad indices**.
Caveats: morning-only data ([[F10]]), edge decaying ([[F3]]), TQQQ fragile ([[F6]]).

### D2 — Promote walk-forward to primary selector (C5)
Make the sweep select on rolling-origin OOS, not single-split holdout ([[H4]]). Now well-motivated
([[E4]] shows the lens is stable). Needs a design pass on integration with the 5-phase sweep.

### D3 — Adopt the noise-ratio instrument rule; make QQQ/SPY first-class candidates
Actionable design rule from [[F7]]: **only deploy this signal where `stop_pct` > median intraday
bar range (noise_ratio > 1)**. Concretely: (1) run full sweeps on QQQ + SPY (+ IWM check) as
production candidates; (2) build the screener [[E8]] to apply the rule to a wider universe; (3) do
NOT size up the leveraged ETFs on this architecture. NOTE: changing the live instrument touches the
armed trader path — requires sign-off; this node records the evidence-backed recommendation, not an applied change.
