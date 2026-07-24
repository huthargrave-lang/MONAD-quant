# Study 63 — Broker quote-field precedence and staleness audit

**Date:** 2026-07-24<br>
**Status:** source/dependency audit plus deterministic counterexamples and
pinned descriptive stress test; no live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`broker_quote_field_precedence_audit`<br>
**Durable derivative:**
`data/tqqq_quote_staleness_5m_summary_2026.json`

## Question

Does `get_tradeable_price` prove that its returned value is a current,
side-appropriate executable price before that value sets the parent limit,
target, stop, and recorded `fill_basis`?

## Verdict

**No. The function proves only that one candidate is positive and finite.**

For both its nominal-live and delayed snapshots, current source chooses:

```text
last → prior-day close → bid → ask → ib_insync marketPrice()
```

It checks none of:

- quote or last-trade timestamp;
- callback-confirmed market-data type;
- bid/ask sizes;
- whether `last` lies inside the current spread;
- halted state;
- spread width; or
- side-appropriate executable price.

This has two distinct failure modes:

1. a valid prior-day `close` beats a valid current bid/ask whenever `last` is
   absent; and
2. any positive `last` beats `ib_insync.marketPrice()`, even when that last is
   outside a valid current spread.

The fallback explicitly requests market-data type 3, which IBKR defines as
**15–20 minutes delayed**, and accepts it for order construction. Neither the
selected field nor data type nor quote timestamp is retained.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study63.json
```

The raw recent five-minute cache is hash-pinned at:

```text
/tmp/monad_tqqq_5m_panel.csv
sha256 3b6a91ebdc5b8b30dd51cb1f262dada5097819da8c98bfc79fbf2b7156845432
```

When those expiring vendor bytes are absent, the program reads the committed
derived summary. When present, it recomputes every statistic and fails if the
result differs from the durable derivative.

## Authoritative contracts

Current [IBKR Campus TWS API documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/)
defines delayed data as 15–20 minutes old and says the
`marketDataType` callback identifies the type actually returned. The official
[tick-type table](https://interactivebrokers.github.io/tws-api/tick_types.html)
defines:

- bid as the highest bid;
- ask as the lowest offer;
- last as the last traded price;
- close as the previous day’s closing price;
- delayed last/bid/ask as distinct delayed fields; and
- delayed close as the prior day’s close.

The project pins `ib-insync==0.9.86`. Its
[`reqTickers` implementation](https://ib-insync.readthedocs.io/_modules/ib_insync/ib.html)
is a blocking snapshot request: it waits for the snapshot future, ends the
ticker, then returns. Its
[`Ticker.marketPrice()` implementation](https://ib-insync.readthedocs.io/_modules/ib_insync/ticker.html)
uses `last` only if it lies inside a valid positive-size spread; otherwise it
uses the midpoint, falling back to last only without a valid spread.

The adapter places `marketPrice()` last, so that spread-aware rule is reachable
only when **last, close, bid, and ask are all invalid**.

IBKR’s [snapshot documentation](https://interactivebrokers.github.io/tws-api/md_request.html)
also says a snapshot returns available data over an approximately 11-second
span and then emits `tickSnapshotEnd`. The adapter calls `ib.sleep(2)` *after*
each blocking `reqTickers` return. That sleep cannot refresh an already-ended
snapshot; it only ages the returned values further.

## Deterministic counterexamples

### Prior close beats a current spread

Synthetic snapshot:

```text
last       unavailable
close      100.00
bid / ask  109.90 / 110.10
sizes      positive
```

Current selector:

```text
selected              close = 100.00
ib_insync marketPrice midpoint = 110.00
long parent limit     100.50
distance below ask    871.934605 bp
```

The “0.5% through market” buy limit is actually 8.72% below the available ask.
This directly constructs the unfilled-parent boundary from Study 53.

### Out-of-spread high last beats the midpoint

Synthetic snapshot:

```text
last       120.00
close      100.00
bid / ask  109.90 / 110.10
sizes      positive
```

Current selector chooses 120.00; `ib_insync.marketPrice()` would choose 110.00.
The long bracket becomes:

```text
parent limit  120.60
target        121.20
stop          119.40
```

The stop is **854.545455 bp above** the current midpoint. Conditional on the
parent filling near the current market and the child becoming active, the
sell-stop trigger is already crossed. This is order geometry, not a claim
about the venue’s exact fill sequence.

The symmetric low-last example makes a short parent immediately marketable
while its buy stop is already crossed. Shorts are disabled in current config,
so that row is a code-path counterexample rather than current-policy exposure.

## How often does the 0.5% offset fail as a staleness bound?

IBKR says delayed data are 15–20 minutes old. The pinned TQQQ panel therefore
compares exact 15- and 20-minute close pairs. This is not an IBKR quote replay;
it is a transparent five-minute OHLC stress proxy.

| lag | exact pairs | median absolute move | p90 | p95 | maximum | absolute move > 50 bp |
|---:|---:|---:|---:|---:|---:|---:|
| 15 min | 3,000 | 30.879 bp | 100.238 bp | 135.775 bp | 558.052 bp | **964 / 3,000 (32.133%)** |
| 20 min | 2,960 | 34.492 bp | 116.001 bp | 154.955 bp | 656.378 bp | **1,080 / 2,960 (36.486%)** |

For the current long-only path:

- a rise greater than 0.5% can leave the stale-quote buy limit below the
  current market; and
- a decline greater than 0.5% can put the stale-quote sell stop above the
  current market.

At 15 minutes, 469 pairs rise more than 50 bp and 495 fall more than 50 bp. At
20 minutes, the counts are 540 and 540. The parent/stop offset is therefore not
a conservative bound on delayed-price movement in this short sample.

These percentages are **not expected incident rates**. The window is recent,
short, and uses a volatile 3× ETF; OHLC closes omit spreads, timestamps within
bars, and executions.

## Prior-close stress

If `last` is unavailable but bid/ask are valid, current precedence selects the
previous session’s close. At the project’s nominal hourly cycle times, the
pinned panel compares each `:30` five-minute bar open with the prior regular
session close:

| diagnostic | result |
|---|---:|
| hourly-cycle proxies | 273 |
| current open > prior close by 50 bp | 130 |
| current open < prior close by 50 bp | 118 |
| absolute difference > 50 bp | **248 / 273 (90.842%)** |
| median absolute difference | 292.260 bp |
| p90 absolute difference | 688.873 bp |
| min / max difference | −12.916% / +9.586% |

Conditioned on the `close` branch being selected, 248/273 proxies cross the
same 0.5% geometry boundary:

- on the 130 upside cases the long buy limit can sit below the current open;
- on the 118 downside cases the long sell stop can already be above the current
  open.

This is deliberately conditional. It does not say `close` was selected 90.8%
of the time; the runtime does not retain the selected field.

## Sanitized archive overlap

Only three archived entry-success events fall inside the pinned five-minute
coverage:

| event | quote | current bar open | quote vs open | in current 5m range | in 15m-prior range | long parent ≥ bar open |
|---|---:|---:|---:|---|---|---|
| 2026-05-27 18:32 UTC | 81.32 | 81.7500 | −52.599 bp | no | yes | no |
| 2026-05-28 16:33 UTC | 83.58 | 83.7399 | −19.095 bp | no | yes | yes |
| 2026-06-17 16:32 UTC | 80.98 | 81.1550 | −21.564 bp | yes | yes | yes |

All three quotes lie inside the bar range from 15 minutes earlier. That is
**compatibility, not attribution**: one is also inside the contemporaneous bar,
and ordinary price ranges overlap. The archive retains no:

- selected field;
- market-data type;
- quote timestamp;
- bid/ask or size;
- actual entry fill; or
- quote-request identifier.

The May 27 parent cap is 2.446 bp below the current bar-open proxy, but the
actual spread, order acceptance, and fill are absent. It is not labeled an
unfilled order.

## Existing test boundary

Broker tests mock `get_tradeable_price` to a scalar and validate bracket math.
They do not directly test:

- absent last with valid close and spread;
- last outside the spread;
- bid/ask size;
- callback-confirmed data type;
- quote age;
- delayed/frozen rejection;
- halted/closed markets; or
- the 0.5% parent/stop boundary under stale data.

## Relationship to prior findings

- Study 52 proves `fill_basis` is this quote, not an entry execution.
- Study 53 proves an unfilled parent can become a local phantom trade.
- Study 57 proves target, stop, and parent are quote-anchored.
- This study shows the quote anchor itself need not be current or
  side-executable.

Together the chain is:

```text
unverified field/type/time
    → quote-anchored parent and protection
    → no entry acknowledgement or fill
    → local position committed from quote
    → later inference can manufacture a closed local trade
```

## Falsification / repair gate

Before changing the protected order path:

1. require callback-confirmed market-data type 1 for entry construction, or
   define and separately approve a bounded delayed-data policy;
2. require timestamped positive-size bid/ask inside an age and spread bound;
3. use ask for buy construction and bid for sell construction;
4. reject prior close and last outside a valid spread;
5. persist request time, source timestamp, field, type, bid/ask/size, contract,
   and eventual execution identity;
6. test no-permission, delayed, frozen, halt, closed-session, crossed/stale
   last, and snapshot-timeout cases; and
7. retain the parent lifecycle until acceptance, cumulative fill, and
   fill-relative protection are reconciled.

## Decision

Do not describe `get_tradeable_price` as “fresh” or its output as executable
evidence. Treat it as an unverified broker-field scalar. The decision gate is a
timestamped, callback-typed, side-aware live spread plus confirmed entry
execution—not another constant offset around `last` or `close`.
