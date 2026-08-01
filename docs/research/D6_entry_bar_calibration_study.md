# Study #20 — Entry-Bar Calibration Sufficiency

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck`<br>
**Data:** study #17's 157 full-history dual-hit entry bars and durable five-minute audit;
the one-position path contains 138 dual-hit bars and 17 recent audited events, 14 resolved<br>
**RESEARCH_WEB nodes:** E44 (study) · F54 (finding) · resolves the interpretation boundary in [[F51]]<br>
**Status:** value-of-information result; Bayesian rows are explicitly model-based sensitivity,
not evidence of alpha. [Study #22](D6_one_minute_entry_resolution_study.md) subsequently resolves
one of the three five-minute ambiguities as stop-first; this document preserves the original
five-minute-only decision surface.

## Question

Study #17 proved that activating the bracket during entry bar N+1 is material, but hourly OHLC
cannot order target versus stop when both thresholds appear. Is the recent five-minute sample
large enough to calibrate a stochastic target-first probability and recover a usable return
estimate?

## Exact break-even construction

Every conservative dual-hit entry returns −0.52% after general slippage; changing it to
target-first returns +0.98%. At fixed 10% sizing this changes that trade's account multiplier by
a known amount. Terminal return is a product, so it depends on the **number** of target-first
resolutions, not which ambiguous dates receive them. Drawdown still depends on dates and is not
inferred.

Three paths answer different questions:

| path | ambiguous entries | minimum target-first count | break-even rate | observed resolved rate |
|---|---:|---:|---:|---:|
| overlapping exact-stop diagnostic, isolates N+1 vs N+2 | 157 | 53 | **33.76%** | 5/16 = 31.25% |
| one-position exact-stop path | 138 | 36 | **26.09%** | 4/14 = 28.57% |
| one-position **open-aware gap** path | 138 | 72 | **52.17%** | 4/14 = 28.57% |

This distinction matters. Entry ordering can plausibly change the sign of the exact-stop paths.
Once the independently measured gap damage is included, more than half of dual-hit entry bars
must be target-first to reach zero—far above the observed point estimate.

## Posterior-predictive sensitivity

For transparency, the tool uses an exact beta-binomial predictive distribution with Jeffreys
prior. It assumes recent resolved events are exchangeable with all historical dual-hit events.
That assumption is strong; the purpose is to show sensitivity, not manufacture certainty.

### Paired overlapping diagnostic

| treatment of three unresolved five-minute bars | P(total > 0) | predictive total-return 95% interval |
|---|---:|---:|
| exclude unresolved | 44.0% | −4.94% to +5.58% |
| all stop-first | 27.1% | −5.51% to +3.85% |
| all target-first | 77.6% | −2.93% to +7.82% |

The sign is unidentified.

### One-position exact-stop path

| unresolved treatment | P(total > 0) | predictive median |
|---|---:|---:|
| exclude | 60.7% | +0.69% |
| all stop-first | 43.8% | −0.36% |
| all target-first | 90.8% | +3.29% |

Again, ambiguity treatment changes the conclusion.

### One-position open-aware gap path

| unresolved treatment | P(total > 0) | predictive median | predictive 95% interval |
|---|---:|---:|---:|
| exclude | **4.7%** | −4.59% | −8.38% to +0.85% |
| all stop-first | **1.2%** | −5.59% | −8.79% to −0.80% |
| all target-first | **20.4%** | −2.13% | −6.43% to +2.99% |

The gap-aware path remains likely negative under every unresolved-event treatment, but this is
conditional on exchangeability and the Jeffreys model. It is not a frequentist proof of negative
alpha.

## Value of information

The paired diagnostic's observed 31.25% rate is only 2.51 pp below its 33.76% threshold. If that
rate persisted, approximately **1,339 resolved dual-hit events** would be needed for a Wilson 95%
interval to lie wholly below break-even—about **15 years** at the observed ambiguous-event pace.

The one-position exact path has the mirror problem: 28.57% is only 2.48 pp above its 26.09%
threshold and needs roughly 1,171 resolved events for the interval to clear the threshold.

The gap-aware threshold is far away at 52.17%. With 4/14 resolved target-first, one additional
stop-first resolution would put a Wilson upper bound below that threshold. But the three currently
unresolved five-minute bars could all be target-first, so resolving those specific events at
one-minute/tick resolution has much more value than collecting a few arbitrary new examples.

## Finding

**Do not calibrate the hourly simulator with a single target-first probability from 16 events.**
For the exact-stop question, the break-even threshold lies too close to the observed rate and
would require implausibly long data collection. For the gap-aware path, the evidence leans
negative, but the highest-value next data are the three unresolved events plus historical
lower-timeframe/order-event reconstruction—not a stochastic patch.

IBKR's documentation confirms the structural timing premise: bracket children remain on hold until
the parent fills and become active after execution
([IBKR complex orders](https://www.interactivebrokers.com/campus/trading-lessons/python-complex-orders/)).
That establishes N+1 exposure; it does not resolve historical within-bar ordering.

## Surviving caveats

- The five-minute audit is recent and clustered.
- Events are not demonstrated exchangeable across volatility regimes or time of day.
- Five-minute “first” still hides ordering inside one sub-bar and order-transmission latency.
- Predictive distributions omit uncertainty in fills, spreads, signal stability, and opportunity
  selection.
- Terminal-return count invariance does not extend to drawdown.
- The active engine remains paper-only; this study specifies missing information, not a live edit.
