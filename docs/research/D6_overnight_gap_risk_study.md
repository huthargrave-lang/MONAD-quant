# Study #16 — Overnight Gap-Through-Stop Risk

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck`<br>
**Data:** pinned TQQQ full-session hourly bars, 2024-08-01 through 2026-07-22
(3,429 bars / 494 sessions, median 7 bars/session; Yahoo cache in `/tmp`)<br>
**RESEARCH_WEB nodes:** E40 (study) · F50 (finding) · builds on [[F47]] · refines [[F28]]<br>
**Status:** verdict **HOLDS within the two-year observed path and both same-bar ordering bounds**.
The custom exact-stop replay
matches `compute_trade_returns()` over 1,516 gated-long trades with zero
return/type/timestamp differences;
the gap-fill self-check passes; Python 3.9 and 3.13 produce identical JSON; and the known July
2026 live loss is reproduced from independent market data within 0.19 percentage point.
The long-history generalization is tested separately in [study #19](D6_cross_instrument_gap_history.md);
do not promote the strategy-conditioned two-year rate into a stationary annual forecast.

## Question

The live bot holds positions overnight, and [[F47]] records the concrete consequence: a TQQQ
long with a configured 0.5% stop filled down 4.01% after an overnight gap. The backtest cannot
produce that outcome: `compute_trade_returns()` converts every stop trigger to exactly
`-stop_loss_pct - stop_slippage_pct`, regardless of the bar open.

This study asks:

> How much does exact-stop accounting understate the current hourly strategy's observed risk,
> and does a constant stop-slippage penalty or an end-of-day flatten adequately address it?

This is risk-model research, not a strategy rehabilitation. The hourly signal has no reliable
edge ([[F13]]/[[F14]]/[[F43]]), and no result here changes [[D6]].

## Method

The study downloads one pinned, full-session TQQQ panel and keeps the exchange clock explicitly
in `America/New_York`. This deliberately avoids the project's prior morning-only/UTC-hour failure
mode ([[F13]]). It runs the current live signal construction:

- `build_features(..., timeframe="hourly")`;
- `require_signals=1`;
- no hourly regime filter, matching `live/signals.py`;
- shorts disabled, matching `TRADER_ALLOW_SHORTS=False` in the armed trader;
- 1.0% target, 0.5% stop, 10-bar live cap, 2 bp round-trip slippage;
- one open position at a time, signal on completed bar → next-bar-open entry;
- bracket scanning begins on the entry bar, as a live bracket is active after the fill;
- fixed 10% position sizing, matching the live account shape.

Every selected entry is replayed twice:

1. **Exact stop (current model):** any stop touch returns exactly −0.5% less general slippage.
2. **Gap-aware:** if a bar opens through the stop, the fill is that open; otherwise the exact
   intrabar target/stop logic is unchanged.

The paired paths have identical entries and exit timestamps; only the fill on an open through
the stop differs. An additional overlapping/N+2 exact-stop replay is required to match
`compute_trade_returns()` exactly before the study runs. Two sensitivities use 8 and 10 hold
bars. A separate counterfactual flattens any surviving position at the prior session's last
official daily close instead of carrying it overnight; the final hourly-bar close is retained as
a sensitivity.

Because entry-hour dual hits materially change absolute strategy return, the full gap experiment
is repeated under both pessimistic stop-first and optimistic target-first entry-bar ordering.
The gap result is identical in both: 34 affected trades and −5.376 pp fixed-10% damage. Ordering
changes whether the entry-hour exit is a win or loss, but not its timestamp, later opportunity
set, or the overnight positions.

## Results

### The raw instrument has a large two-sided overnight tail

Across 493 close-to-next-open gaps:

| threshold | downside frequency | upside frequency (short risk) |
|---:|---:|---:|
| 0.5% | 32.7% | 44.2% |
| 1.0% | 26.0% | 31.4% |
| 2.0% | 13.4% | 18.7% |
| 4.0% | 6.1% | 5.5% |

The worst downside open was −16.16%; the largest upside open was +11.64%. These are unconditional
instrument statistics, not strategy losses, but they show why a 0.5% stop cannot bound overnight
risk in a 3× ETF.

### The current stop model halves the observed loss

The live-shaped replay generated 1,117 sequential long trades; 127 were carried overnight. Of
those overnight holds, 34 (26.8%) opened through the stop. Short signals are excluded because
the armed trader currently has `TRADER_ALLOW_SHORTS=False`.

| replay | total return at fixed 10% sizing | max drawdown | win rate |
|---|---:|---:|---:|
| exact-stop model | −5.17% | −5.88% | 31.5% |
| gap-aware fills | **−10.15%** | **−10.19%** | 31.5% |

Gap-aware fills remove **53.76 percentage points of gross per-trade returns**, or approximately
**5.38 percentage points of account performance at fixed 10% sizing** over this observed path.
The result is insensitive to the configured hold cap:

| max bars | gap events | exact total | gap-aware total | fixed-10% damage |
|---:|---:|---:|---:|---:|
| 8 | 34 | −5.18% | −10.15% | −5.38 pp |
| 10 | 34 | −5.17% | −10.15% | −5.38 pp |

The largest single miss was January 27, 2025: the model booked −0.52%, while the observed hourly
open implies −9.48%, an **8.96 pp understatement**. The July 7, 2026 event independently validates
the construction:

| quantity | value |
|---|---:|
| live entry / configured stop | $76.61 / $76.23 |
| first hourly open | $73.70 |
| exact-stop model | −0.52% |
| gap-aware hourly-open replay | −3.82% |
| observed live fill | $73.54 / **−4.01%** |

The hourly open was only 21.8 bp better than the actual fill. Thus even the gap-aware hourly-open
model is slightly optimistic in the one directly observed live case.

This is consistent with the broker's own order semantics: IBKR says a stop becomes a market order
when triggered and is not guaranteed a particular execution price
([IBKR stop-order glossary](https://www.interactivebrokers.com/campus/glossary-terms/stop-order/)).

### A mean stop penalty fixes the average, not the risk

There were 765 modeled stop/ambiguous exits. Spreading the aggregate gap damage across them
implies a mean-matching `stop_slippage_pct` of only **7.0 bp**. That sounds small because most
stops do not gap. The conditional damage is strongly skewed:

| conditional on a gap-through stop | extra loss beyond modeled stop |
|---|---:|
| median | 1.03 pp |
| 90th percentile | 3.51 pp |
| maximum | 8.96 pp |

A constant 7.0 bp stop penalty can approximately correct sample-average return, but it cannot
produce the observed loss distribution or drawdown. Risk reporting needs an open-aware fill
rule (or an explicit gap stress), not only a larger scalar slippage assumption.

### End-of-day flatten removes this tail but does not create an edge

The corrected no-overnight counterfactual exited 126 positions at the official daily close proxy:

| replay | total return | max drawdown |
|---|---:|---:|
| gap-aware overnight holds | −10.15% | −10.19% |
| end-of-day flatten | **−5.77%** | **−6.75%** |

It improves observed total return by 4.37 pp and drawdown by 3.44 pp versus the gap-aware path,
but still loses money. It is a tail-risk control, not alpha. The comparison is not perfectly
paired—flattening changes later position availability—and the official close is only a proxy for
a real market-on-close fill. The final-hour sensitivity is −5.81% / −6.74%. Any live implementation would also change strategy
behavior and requires explicit approval with the trader stopped.

## Finding

**The backtest's exact-stop rule materially understates live TQQQ tail risk.** On the pinned
two-year full-session path, modeling opens through the stop roughly doubles both loss and
drawdown at fixed 10% sizing (−5.17% → −10.15%; −5.88% → −10.19%). This is not a hypothetical
stress: 34 replayed overnight holds gap through the stop, and the July live event is reproduced
closely from independent hourly data.

The practical hierarchy is:

1. **Risk-faithful research:** fill a stop at the bar open whenever the open is beyond the stop.
2. **Cheap expected-return approximation:** add ~7 bp to every modeled stop, explicitly labeled
   as mean-only and incapable of representing tail drawdown.
3. **Operational tail removal:** flatten before the close; in this sample it removes the entire
   gap channel but still leaves a negative-return hourly strategy.

This strengthens [[F28]]: the backtest/live disconnect is not only bar frequency and accounting;
the fill model also structurally truncates the left tail. It sharpens [[F47]] from one anecdote
into a repeated historical-path property. It does **not** rehabilitate the active engine; it makes
the honest hourly result worse and therefore further supports [[D6]].

## Surviving caveats

- **Only one two-year market path.** The 34 events establish materiality on the observed path,
  not a stationary annual expectation. No bootstrap can manufacture independent gap regimes.
- **Hourly-open fills remain optimistic.** Stops execute around the open with spread and queue
  effects; the one live comparison was 21.8 bp worse than the hourly print.
- **Replay is live-shaped, not order-log reconstruction.** Scheduler latency, partial fills,
  broker state, and every historical IBKR execution are unavailable.
- **OHLC ambiguity remains.** Worst-case stop wins if target and stop appear in one hourly bar.
  Study #17 bounds and partially calibrates that ambiguity; importantly, the paired *gap damage*
  is invariant to optimistic versus pessimistic entry-hour ordering.
- **EOD flatten changes the strategy.** Its corrected outcome is an informative counterfactual,
  not a
  production recommendation or authorization to edit the armed trader.
- **The baseline is already negative.** The study measures risk-model error; it is not evidence
  for trading the hourly strategy.

## Verification

```bash
venv/bin/python tools/overnight_gap_risk_study.py --selfcheck
venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-risk.json
venv/bin/python -m unittest \
  tests.test_execution_model.TestBacktestEntryBasis \
  tests.test_execution_model.TestExitTypeTracking \
  tests.test_execution_model.TestOpposingSignalExit \
  tests.test_execution_model.TestATRDynamicStops \
  tests.test_execution_model.TestSoft50MAGate \
  tests.test_fill_model.TestStopSlippage -v
```

The focused execution suite passes 29/29. The project now requires Python 3.11+; validation is
performed on Python 3.13 as well as a legacy 3.9 reproducibility run for this read-only tool.
