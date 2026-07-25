# Study #17 — Backtest-to-Live Execution Semantics

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck`<br>
**Data:** 3,429 full-session TQQQ hourly bars (2024-08-01–2026-07-22) plus
3,120 five-minute bars (2026-05-26–2026-07-22); the 19 derived ordering events are
durably captured in
[`data/entry_bar_5m_ordering_2026.csv`](data/entry_bar_5m_ordering_2026.csv)<br>
**RESEARCH_WEB nodes:** E41 (study) · F51 (finding) · refines [[F28]]/[[F43]]<br>
**Status:** the execution mismatch is established; its return sign is **not identifiable from
hourly OHLC alone**. [Study #20](D6_entry_bar_calibration_study.md) quantifies why the existing
five-minute sample is insufficient to repair the exact-stop result; [study #22](D6_one_minute_entry_resolution_study.md)
recovers one unresolved event as stop-first without changing that exact-stop verdict.

## Question

The research runner and live trader share a next-open entry convention, but they do not express
the same trade path. Which differences matter, and can the return impact of activating the live
bracket during the entry hour be measured honestly?

## Method

One feature panel is replayed through a cumulative assumption waterfall. Each row changes one
thing: clock interpretation, hourly regime flag, short gate, one-position constraint, entry-bar
bracket activation, or open-aware stop fills. Every row uses fixed 10% sizing so the accounting
scale is comparable. Rows with overlapping trades are diagnostic, not deployable portfolios.

The critical entry-bar test is also run as a paired experiment over the same 1,516 long entries:

- arm A starts scanning the bracket on N+2, matching `compute_trade_returns()`;
- arm B starts on the entry bar N+1, matching a bracket active after the next-open fill;
- both otherwise use the exact-stop model and the repository's conservative dual-hit rule.

The custom N+2 arm matches `compute_trade_returns()` on count, timestamps, exit types, and returns
(maximum absolute return difference 0). For entry hours that touch both thresholds, a second arm
assumes target-first to expose the full ordering bound. Recent five-minute bars provide a limited
lower-timeframe calibration.

## Assumption waterfall

| cumulative semantics | trades | total | maxDD | gap stops |
|---|---:|---:|---:|---:|
| current runner shape: UTC-naive clock, regime on, shorts, overlap, N+2 | 151 | +2.06% | −0.48% | 8 |
| live hold cap (8 → 10 bars) | 151 | +2.06% | −0.48% | 8 |
| interpret 9–16 on the exchange clock | 395 | +1.66% | −1.19% | 51 |
| disable hourly regime filter, as live does | 2,005 | +10.67% | −2.84% | 207 |
| apply the armed trader's long-only gate | 1,516 | +11.94% | −1.77% | 147 |
| allow only one open position | 789 | +6.56% | −1.17% | 58 |
| activate bracket during entry hour, conservative ambiguity | 1,117 | **−5.17%** | **−5.88%** | 34 |
| fill opens through the stop at the open | 1,117 | **−10.15%** | **−10.19%** | 34 |

This table is a decomposition, not an attribution of causal alpha. Changing the clock, filter, or
position constraint changes the opportunity set. The last two rows change execution semantics on
the live-shaped path and therefore carry the cleanest operational meaning.

## Entry-bar audit

Of 1,516 paired entries, 980 (64.6%) exit during the entry hour:

| entry-hour result | count |
|---|---:|
| stop only | 591 |
| target only | 232 |
| both target and stop | 157 |

Starting the bracket on N+1 instead of N+2 changes 228 trade returns. Under stop-first ambiguity,
fixed-10% first-order performance changes by −19.2 percentage points and the path moves from
+11.94% to −7.61%. But if all 157 dual-hit entry hours are target-first, the immediate-bracket
path is +16.91%. **The honest hourly-OHLC bound is therefore −7.61% to +16.91%; it straddles zero.**

The recent five-minute calibration contains 19 dual-hit hourly events on 15 dates:

| five-minute ordering | events |
|---|---:|
| stop first | 11 |
| target first | 5 |
| still dual-hit within one five-minute bar | 3 |

Among 16 resolved events, target-first is 31.25%, with a wide 95% Wilson interval of
14.16%–55.60%. It leans toward the conservative convention but is too small, clustered, and
recent to identify the full-history return sign.

Yahoo's five-minute retention is rolling, so the tool records the normalized source panel's
SHA-256 (`3b6a91…5432`) and requires any still-available raw reconstruction to match the committed
19-event audit exactly. After raw expiry it reproduces the summary from that derived audit and
labels the source as a fallback. The repository does not commit the 313 KB vendor panel.

## Finding

The statement “backtest and live share a unified execution rule” is too strong. The production
research engine skips bracket evaluation during the entry bar, while the live bracket can execute
after the fill. The difference affects nearly two thirds of candidate entries and is economically
large.

However, replacing N+2 with pessimistic hourly N+1 does **not** yield a trustworthy performance
estimate. The hourly bar cannot order target and stop for 157 entry hours. The correct conclusion
is:

1. the current N+2 backtest is not live-faithful;
2. hourly OHLC is insufficient to repair it without a material ordering assumption;
3. tick/order-event or broadly available lower-timeframe data are required before using this
   engine for return claims.

The finding strengthens [[F28]] and [[F43]] but does not authorize a live/config change. The trader
remains paper-only.

## External execution check

IBKR describes a stop as becoming a market order once triggered and explicitly warns that its
execution price is not guaranteed and can be far from the stop
([IBKR stop-order glossary](https://www.interactivebrokers.com/campus/glossary-terms/stop-order/)).
That supports both entry-hour immediacy and study #16's open-through-stop treatment; it does not
resolve within-bar order.

## Surviving caveats

- The waterfall is cumulative; intermediate rows are not Shapley values.
- Overlapping rows are signal-trade accounting, not capital-feasible paths.
- Five-minute bars still hide within-bar ordering and bracket-transmission latency.
- Only 19 recent ambiguous events have five-minute coverage.
- Yahoo data are not an independent execution record.
- The active strategy remains negative/flat under the repository's honest verdict; this study
  audits simulation fidelity, not alpha.
