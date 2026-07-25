# Study 69 — Broker-connection exception and missed-risk-cycle audit

**Date:** 2026-07-24<br>
**Status:** directly observed cycle aborts plus deterministic exception
contract; exact broker call site and economic effect unidentified; no
protected-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`broker_connection_exception_fallback_audit`

## Verdict

The advertised mark fallback handles a `RuntimeError` meaning “no broker price,”
but it does not handle the connection exception produced when Gateway is
unavailable.

`_ensure_connected` makes four attempts and sleeps 2, 4, and 6 seconds. After
the final failure it re-raises the original `ConnectionRefusedError`.
`get_tradeable_price` calls `_ensure_connected` before its market-data `try`,
while `_resolve_mark_price` catches only `RuntimeError`. Consequently neither
yfinance nor signal-bar fallback is reached.

For an already-open position the consequence is broader: broker-position
reconciliation happens before holding-age increment and before the software
stop/take-profit check. Connection refusal aborts the entire risk cycle.

## Direct archived evidence

| endpoint | result |
|---|---:|
| unhandled connection-failure events | **46** |
| unique minute slots | **24** |
| paired-writer slots | **22** |
| events while local position lifecycle open | **33** |
| unique position-open risk-cycle slots | **17** |
| affected local lifecycles | **3** |
| explicit `ConnectionRefusedError` labels | 38 |
| older untyped connection-refused messages | 8 |
| event offset after `:32` | **12.247–12.628 s** |

The timing tightly corroborates exhaustion of the source’s twelve seconds of
explicit connection retry waits.

## Exception matrix

| upstream failure | resolver behavior |
|---|---|
| `RuntimeError("No broker price")` | attempts yfinance, then signal bar |
| `ConnectionRefusedError` | propagates; no price fallback |
| other connect-level `OSError`/`TimeoutError` | propagates unless wrapped elsewhere |

The archive retains exception text but not stack traces, so a specific event
cannot be assigned conclusively to `get_open_position`,
`get_tradeable_price`, or another `_ensure_connected` caller. The current
position control flow proves all occur before software-risk evaluation.

## Honesty boundary

A missed application software check is not necessarily an unprotected economic
position: the IBKR bracket may remain active. Local lifecycle times do not
prove broker exposure, order state, or a missed profitable/adverse exit.
Therefore the causal PnL effect is unidentified.

## Falsification gate

1. Normalize broker availability into typed results rather than an
   exception-class allowlist.
2. Separate reconciliation availability from mark fallback and persist an
   explicit missed-risk-check state.
3. Define holding-age behavior through completed-bar identity, not process
   success.
4. Test refused connections, timeouts, socket errors, qualification failure,
   no-price results, open positions, paired writers, recovery, and deadlines.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study69.json
```
