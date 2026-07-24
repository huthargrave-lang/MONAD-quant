# Study 65 — Market-data provenance label integrity

**Date:** 2026-07-24<br>
**Status:** deterministic interface/source proof; historical incident frequency
unidentified; no live/config/order-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`market_data_provenance_label_audit`

## Verdict

**A persisted or green dashboard `live` mark does not prove real-time data.**

`get_tradeable_price` can return either a nominal-live or 15–20-minute delayed
value, but both branches return only a `float`. `_resolve_mark_price` cannot
distinguish them and maps every successful float to `(price, "live")`.

The label is stored in the overwritten `account_snapshot` singleton, rendered
as a green dashboard badge, used beside mark-derived unrealized PnL, and
reported beside software stop/take-profit decisions that consume the same
resolver. `mark_time` is generated locally after resolution; it is not the
source quote timestamp.

## Deterministic indistinguishability proof

| upstream state | broker return | resolver result | persisted label |
|---|---:|---|---|
| real-time value 100 | `100.0` | `(100.0, "live")` | green `live` |
| delayed value 100 | `100.0` | `(100.0, "live")` | green `live` |

This proves information loss, not historical incidence. A delayed price may
also equal the current price; provenance error and price error are separate.

## Archive boundary

The sanitized archive exports one overwritten account-snapshot row. It says
`mark_source=live` but retains no market-data type, selected quote field, or
source quote timestamp. It cannot establish provenance, estimate a delayed-data
rate, or attribute an archived software exit to delayed data.

## Falsification gate

1. Return a typed quote carrying callback-confirmed data type, selected field,
   source timestamp, request time, bid/ask, and sizes.
2. Preserve those fields end to end, label missing provenance `unknown`, and
   derive freshness from source time.
3. Test live, delayed, frozen, prior-close, missing-label, stale-time, and
   out-of-spread cases, including software-risk triggers.
4. Retain append-only per-cycle provenance for calibration.

These are requirements, not an authorized modification of the protected live
path.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study65.json
```

The audit does not import `live.*`, open `state.db`, contact IBKR, or submit an
order.
