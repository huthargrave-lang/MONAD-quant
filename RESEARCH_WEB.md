# MONAD-quant — Research Idea Web

> A traversable graph of what we **know** (Findings), what we're **testing**
> (Hypotheses), how we **test** it (Experiments), and what we **decide** (Gates).
> Nodes link with `[[ID]]`. Walk it with `venv/bin/python tools/ctx.py web [NODE]`.
> Append nodes; never rewrite history — supersede with a new node and link back.
> **Evidence-first:** a claim is only as strong as the Experiment behind it, and
> only OOS, leak-free, cost-aware numbers count as evidence (see [[E3]]).

---

## Findings (established by an Experiment)

### F1 — Three numbers, three stories
The same strategy measured three ways gives wildly different results: documented
Sharpe 39–94 / +2–3.5%/mo (fantasy), holdout-selected +4–5%/mo (biased), and
leak-free +0.1–0.3%/mo (honest). Only the last is trustworthy. See [[E1]], [[E2]], [[E3]], [[F2]], [[F3]].

### F2 — Holdout-selection bias inflates the sweep
`sweep.py` picks its winner BY the holdout score (`selection_method: holdout_live_score`),
so its reported "holdout" numbers are the best-of-many on that holdout — optimistically
biased. The +4–5%/mo for SOXL/LABU/TNA did NOT survive de-biasing. Motivates [[H4]]. Evidence: [[E2]] vs [[E3]].

### F3 — The honest edge is small but real
Leak-free walk-forward ([[E3]]): QQQ +0.34%/mo Sh 3.74, TQQQ +0.18%/mo Sh 2.17,
LABU +0.15%, TNA +0.12%, SOXL +0.08% — all sub-1% drawdown, ~90–112 OOS trades.
A near-zero-DD ~0.2%/mo vehicle, NOT a 2–3.5%/mo income engine. Confidence is open: [[H1]]. Bears on [[D1]].

### F4 — QQQ (un-leveraged) is the best risk-adjusted instrument
In leak-free OOS the un-leveraged QQQ beat every 3x-leveraged ETF the project was
built around (Sharpe 3.74, 54.5% WR). Surprising; counter to the project's focus. Why? [[H2]]. Evidence: [[E3]], [[E6]].

### F5 — Methodology note: short-slice warmup bug
A naive walk-forward that slices each OOS window strips feature warmup → ~0 trades →
statistically empty results. Fixed by running on `df[:fold_end]` and keeping only
causal trades after the train boundary (full warmup, no look-ahead). Lives in [[E3]].

### F6 — The live instrument (TQQQ) is mid-pack and below the pivot bar
TQQQ leak-free is +0.18%/mo — real but below the ~0.5%/mo pivot threshold ([[D1]]),
and worse than QQQ ([[F4]]). The live paper deployment is on a weak instrument.

---

## Hypotheses (open — each needs an Experiment to resolve)

### H1 — The edge is sample-luck, not durable
One ~2yr window, ~90–112 OOS trades, 9-candidate grid → wide error bars on Sharpe 2–3.7.
Resolve with robustness/dispersion analysis. → [[E4]]. Bears on [[F3]], [[D1]].

### H2 — Un-leveraged broad indices generalize the edge (lower vol → stops outside noise)
Lower-volatility instruments may let a fixed % stop sit OUTSIDE intraday noise →
fewer noise-stops → higher WR. If true, QQQ/SPY/IWM deserve focus over leveraged ETFs.
→ [[E6]]. Extends [[F4]].

### H3 — The edge can be lifted (ATR stops and/or entry quality)
(a) ATR-scaled stops sit outside intraday noise; (b) require_signals=2 (momentum AND
volume) raises EV/trade. Test both in leak-free OOS. → [[E5]]. Bears on [[F3]].

### H4 — Walk-forward should be the sweep's PRIMARY selector (C5)
Single-split holdout selection is biased ([[F2]]); rolling-origin OOS ([[E3]]) is the
honest selector. Promote it inside the sweep. → [[D2]].

---

## Experiments (how we test)

### E1 — Documented optimistic sweep (historical)
Optimistic backtest mode + unreliable paper fills → Sharpe 39–94. Artifact; not evidence. Feeds [[F1]].

### E2 — Fixed-10% realistic holdout sweep (2026-06-19)
`sweep.py TICKER --sizing fixed --fixed-pct 0.10 --mode realistic`. Results in
`sweep_results_*.json` (gitignored). Biased by holdout selection ([[F2]]). Feeds [[F1]].

### E3 — Leak-free walk-forward (PRIMARY evidence)
`tools/walkforward_eval.py` — expanding-window, per-fold params chosen only on prior
data, full warmup, fixed-10% sizing, realistic cost. The trustworthy lens. Produced [[F3]], [[F4]], [[F5]], [[F6]].

### E4 — Edge robustness & confidence (in progress)
Vary folds / min_train / grid; per-fold dispersion; t-stat. Resolves [[H1]].

### E5 — Edge-lift levers (in progress)
ATR-scaled stops + require_signals=2 in leak-free OOS vs baseline. Resolves [[H3]].

### E6 — QQQ structural deep-dive + SPY/IWM (in progress)
Why QQQ leads; noise-ratio (stop% / intraday range%) vs WR across instruments;
generalize to un-leveraged broad indices. Resolves [[H2]], explains [[F4]].

---

## Decisions / Gates

### D1 — Edge go/no-go (roadmap gate #1)
If confirmed net edge < ~0.5%/mo → reposition as a capital-preservation / high-Sharpe
vehicle (its real strength is sub-1% drawdown), not income. Leak-free read is ~0.2%/mo
([[F3]]) → leaning PIVOT, pending robustness [[E4]] and the QQQ angle [[E6]]/[[H2]].

### D2 — Promote walk-forward to primary selector (C5)
Make the sweep select on rolling-origin OOS, not single-split holdout ([[H4]]). Needs a
design pass on how it integrates with the 5-phase sweep. Gated on [[E4]] confirming the lens is stable.
