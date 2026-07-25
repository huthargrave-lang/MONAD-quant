# Study 57 — Quote-anchored bracket geometry and sizing audit

**Date:** 2026-07-24<br>
**Status:** reproducible execution-bound audit; no live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` → `quote_anchored_bracket_geometry_audit`

## Question

Do the current TQQQ “1.0% target / 0.5% stop / fixed 10% position” labels
describe risk relative to the actual parent fill and actual notional?

## Verdict

**No. They are quote-anchored parameters.** Current code:

1. computes quantity from the signal bar close;
2. obtains a new broker quote;
3. places a buy-limit parent up to 0.5% above that quote;
4. anchors TP and SL at +1.0% / −0.5% from the quote;
5. stores the quote as `fill_basis`; and
6. never persists the actual parent fill or resizes/reanchors after it.

At the least favorable price permitted by the parent buy limit, the exact
no-rounding geometry is:

| Basis | Target | Stop | reward:risk |
|---|---:|---:|---:|
| pre-submission quote | +1.000000% | −0.500000% | 2.00 |
| parent buy-limit cap | **+0.497512%** | **−0.995025%** | **0.50** |

The limit cap therefore can halve the target distance, nearly double the stop
distance, and invert the advertised 2:1 reward:risk into 1:2. This is an
**admissible bound**, not measured slippage: a limit fill may be better than its
cap, and the current archive does not contain parent fills.

The separate quantity basis also lets actual notional drift. A conservative
66-of-72-event archive join finds the parent-limit upper envelope ranges from
−141.121 to +382.687 bp relative to the signal-bar sizing basis. In the maximum
case, the true allocation permitted by the current formula is approximately
**10.344%–10.383% of equity** against a 10% plan.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study57.json
```

The study hashes and token-checks current config, broker, trader, state, and
tests. It does not import `live.*`, contact IBKR, touch `state.db`, or modify a
protected path.

## Current formulas

For a long entry with quote \(q\), target fraction \(t=1\%\), stop fraction
\(s=0.5\%\), and parent-limit offset \(b=0.5\%\):

```text
parent limit = round(q × (1 + b), 2)
target       = round(q × (1 + t), 2)
stop         = round(q × (1 − s), 2)
```

Quantity is computed earlier from a different price:

```text
planned dollars = account equity × 10%
qty             = floor(planned dollars / signal bar close)
```

The broker quote and actual fill do not feed back into quantity.

IBKR defines a buy limit as the maximum price the investor will pay: it may
fill at that price or lower, and a fill is not guaranteed
([IBKR limit-order definition](https://ibkrcampus.com/campus/glossary-terms/limit-order/)).
IBKR's bracket mechanism stages the parent and first child with
`Transmit=False`, then the last child transmits the attached group
([official bracket-order documentation](https://ibkrcampus.com/campus/ibkr-api-page/order-types/#bracket-orders)).
That transmission construction does not change the independently supplied
parent, target, and stop prices.

## Fill-relative algebra

Ignoring penny rounding, a long parent filled at its cap has:

```text
target return = (1 + t) / (1 + b) − 1 = +0.497512%
stop return   = (1 − s) / (1 + b) − 1 = −0.995025%
```

For completeness, the short-side symmetry would be +0.502513% / −1.005025%,
also reward:risk 0.5. Current TQQQ shorts are disabled, so that is algebraic
coverage rather than a current trading path.

This result does **not** turn the stop into a loss bound. The stop child can
still trigger into a gap, and Studies 16–17 already show that overnight fills
can be far worse than the trigger.

## Penny-rounding audit on the archive's price scale

The sanitized archive contains 72 application entry-success events with quote
values from $38.13 to $83.58. Applying the **current** formula to those quote
values gives:

| Fill-at-cap geometry | minimum | median | maximum |
|---|---:|---:|---:|
| target from fill | +0.481464% | **+0.497791%** | +0.509868% |
| stop from fill | −1.017035% | **−0.998129%** | −0.979730% |
| reward:risk | 0.475 | **0.500** | 0.517 |

This is a scale/rounding audit, not reconstruction of those historical orders.
The quote events do not retain actual entry executions, and Study 52 established
that `fill_basis` is the quote itself.

## Conservative archive sizing join

The signal archive has no cycle ID and contains duplicate writers. Guessing
which signal row sized an entry would make the result look more complete than
the evidence allows. The join therefore uses a strict rule:

1. group signal rows and entry events by UTC minute;
2. keep only actionable long-signal rows, because archive/current TQQQ shorts
   are disabled;
3. require the actionable-signal count to equal the entry-event count; and
4. pair each ordered signal/event sequence only inside such a slot.

That retains 66 of 72 entry events. Four excluded minutes have one entry but two
actionable signal rows; two entry events rolled into a minute with no signal
row. All six remain unresolved rather than being assigned heuristically.

For each retained event:

```text
qty × bar close ≤ planned dollars < (qty + 1) × bar close
```

That inequality gives an exact interval for quote or parent-limit notional as a
fraction of the unknown planned dollars.

## Sizing results

| Diagnostic, 66 strict joins | minimum | median | maximum |
|---|---:|---:|---:|
| quote vs signal bar | −190.775 bp | −13.203 bp | +329.903 bp |
| parent limit vs signal bar | **−141.121 bp** | **+37.033 bp** | **+382.687 bp** |
| quote-allocation interval, lower endpoint | 97.366% | 99.257% | 102.916% |
| quote-allocation interval, upper endpoint | 98.092% | 99.868% | 103.299% |
| limit-allocation interval, lower endpoint | 97.859% | 99.756% | 103.442% |
| limit-allocation interval, upper endpoint | 98.589% | 100.370% | 103.827% |

At the recorded quote, 8 of 66 joins are definitely above the plan even after
allowing for integer truncation; 25 could be above it. At the parent-limit cap,
24 are definitely and 53 possibly above the plan.

The maximum case is the first 2026-03-31 09:32 ET duplicate path:

| input | value |
|---|---:|
| sizing bar close | $37.89 |
| entry quote | $39.14 |
| parent limit | $39.34 |
| quantity | 269 |
| fill-at-cap notional / planned dollars | 103.442%–103.827% |
| account allocation under a 10% plan | **10.344%–10.383%** |

Again, that cap is not a fill claim.

## Why this matters for recorded PnL

The stored entry basis is the quote, so a target recorded as approximately +1%
can correspond to only approximately +0.5% from an adverse permitted parent
fill. Conversely, the quote-relative −0.5% stop can be approximately −1% from
that fill before any gap-through-stop loss.

IBKR order-status data expose filled quantity and average fill price, while
execution data provide per-fill identity and prices
([official TWS API documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)).
Those are the inputs needed to compute real fill-relative risk and actual
notional. They are not durably captured by the current entry path.

## Test boundary

Current tests correctly assert the quote-derived order tickets:

```text
quote 100.00 → parent 100.50, target 101.00, stop 99.50
```

They also test fixed 10% planned dollars. They do not test:

- target/stop distance from actual fill;
- partial-fill average price and quantity;
- notional relative to the plan after bar-to-quote movement;
- fill-at-limit penny rounding across the observed price range; or
- a cycle-keyed chain from sizing bar through quote, order, fill, and close.

The tests therefore prove implementation consistency, not that the labels are
fill-relative.

## Falsification gate

The conclusion is overturned only by evidence that closes the execution loop:

1. persist parent `permId`, order status, cumulative filled quantity, average
   fill price, per-fill execution IDs/prices/times, and lifecycle ID;
2. state explicitly whether TP/SL are intended to be quote-relative or
   fill-relative;
3. if fill-relative, create/reprice protection only from a broker-confirmed
   average fill while safely handling partial fills;
4. enforce an explicit maximum actual notional or resize/reconcile filled
   quantity against the sizing plan; and
5. retain a cycle-keyed record joining signal bar, planned dollars, quote,
   parent cap, fills, protection, and closed trade.

## Decision

Rename the operational interpretation: the current values are **quote-anchored
target/stop** and **bar-close-sized planned allocation**. Do not call them a
fill-relative 1%/0.5% bracket or an exact 10% position. The current algebra is
valuable as a worst-permitted-price bound, but actual risk and notional remain
unidentified until parent fills are durably reconciled.
