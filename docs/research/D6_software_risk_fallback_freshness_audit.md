# Study 67 — Software-risk fallback freshness and conditional materiality

**Date:** 2026-07-24<br>
**Status:** deterministic source audit and archived prior-session-close
counterfactual; actual fallback incidence unidentified; no protected-path change
authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`software_risk_fallback_freshness_audit`

## Verdict

After broker-price failure, the software stop/take-profit path can act on the
last daily yfinance `close` without checking the returned row’s date, session,
or age.

The complete fallback sequence can consume:

| component | explicit waits |
|---|---:|
| nominal-live and delayed IBKR snapshots | 6 seconds |
| yfinance retry backoff before attempt four | 2 + 4 + 8 = 14 seconds |
| combined explicit waits | **20 seconds** |

Network/request duration is additional, and there is no end-to-end
trigger-decision deadline.

## Archived conditional materiality

For every archived signal cycle occurring while a recorded position was open,
the study asks:

> If yfinance’s last daily row were the prior session close, would that value
> cross the recorded-basis stop/target while the archived signal bar close
> would not?

The replay uses the byte-pinned full-session hourly cache and 65 sanitized
trade records. Closed-trade exports omit entry price, so the recorded quote
basis is reconstructed as `exit_price / (1 + recorded_return)`; this is not an
actual-fill claim.

| endpoint | result |
|---|---:|
| trades with evaluable in-position cycles | 64 |
| unique trade-cycle minute slots | 160 |
| prior-close false-stop slots, strict | **62 / 160 (38.75%)** |
| prior-close false-stop slots, possible | **65 / 160 (40.63%)** |
| duplicate-writer-ambiguous stop slots | 3 |
| strict/possible affected trades | 36 / 38 |
| prior-close false-take-profit slots | **17 / 160 (10.63%)** |
| affected trades for false take-profit | 10 |
| observed actual yfinance-fallback incidents | **0** |

“Strict” means every duplicate-writer bar-close value in that minute agrees;
“possible” means at least one does. The contemporaneous comparator is
`signal_history.bar_close`, a coarse market-data proxy rather than a
side-executable quote.

These percentages are conditional materiality if the provider returns the
prior session—not an estimate of how frequently that happens.

## Provider contract boundary

The pinned dependency is yfinance 1.2.0. Its official API documentation defines
`1d` as a historical interval, describes `start` as inclusive and `end` as
exclusive, and defaults historical OHLC adjustment on. The project also states
that it is unaffiliated with Yahoo and intended for research/educational use:

- [yfinance documentation](https://ranaroussi.github.io/yfinance/index.html)
- [PriceHistory parameters](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html)
- [download parameters](https://ranaroussi.github.io/yfinance/reference/yfinance.functions.html)

This study does not interpret provider terms. It establishes that the
application neither verifies the returned row timestamp nor carries it into the
risk decision.

## Falsification gate

1. Exclude daily historical closes from intraday software-risk triggers, or
   require an explicitly approved typed source with a strict age bound.
2. If a fallback is allowed, verify and persist its row timestamp/session.
3. Apply one deadline across snapshots, provider retries, decision, and close
   submission.
4. Test prior-session and current-partial daily rows, holidays, retry
   exhaustion, duplicate writers, and both true and false trigger boundaries.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study67.json
```
