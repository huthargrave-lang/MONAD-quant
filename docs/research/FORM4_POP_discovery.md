# FORM4-POP — June 2024 Form 4 discovery frame

**Status:** frozen EFTS discovery sample; metadata only; no open-market
cluster labels<br>
**Parents:** research frontier (insider purchase clusters after drawdowns)<br>
**Spec:** `docs/research/data/form4_population_spec.json`<br>
**Artifact:** `docs/research/data/form4_population_discovery.json`<br>
**Tool:** `tools/form4_discovery_lab.py`

## Question

Can we freeze a Form 4 population clock without pretending EFTS hits are
already tradeable insider-buy clusters?

## Frozen window

```text
Form 4
2024-06-03 through 2024-06-07
sampling: first 100 hits per calendar day (day-sliced)
```

| Stage | Count |
|---|---:|
| Index document hits (full week) | 5,637 |
| Fetched (capped) | 500 |
| Unique submissions (capped) | 500 |
| Balanced by file_date | 100 × 5 days |

Raw response sha256:

```text
0614a7e312fd164af02e954f728f540c1e7040abdc5c516c15e9c5e56da77a47
```

Raw bytes stay in `/private/tmp/monad-form4-pilot/` and are not committed.

## Structural results

1. **`q=*` returns 0 hits** on `efts.sec.gov` for Form 4. Use `forms=4` only.
2. **Flat `from=0` over a multi-day window is newest-day biased.** A first attempt
   pulled 400 hits all dated 2024-06-07. Day-sliced caps fix the calendar mix
   for discovery; they are still not a full population.
3. **Archives raw `.txt` is 403** from this environment →
   `transaction_codes_parsed=false`. Open-market (code P) clusters cannot be
   labeled until raw ownership XML is available.

## What this does *not* claim

- No drawdown conditioning
- No Form 4 → forward-return study
- No issuer vs reporting-person disambiguation beyond EFTS display names

## Next

1. Obtain Form 4 XML (sec.gov allowlist / local archive mirror).
2. Parse `transactionCode` / `transactionShares` / `issuerTradingSymbol`.
3. Define cluster = ≥N open-market buys in M sessions after a ≥X% drawdown.
4. Only then attach prices.
