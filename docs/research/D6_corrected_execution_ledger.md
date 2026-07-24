# Study #33 — Consolidated Corrected Execution Ledger

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**Data:** pinned Yahoo TQQQ hourly/daily raw bars and corporate actions, 2024-08-01–2026-07-22<br>
**RESEARCH_WEB nodes:** E57 (study) · F67 (finding) · consolidates [[F50]]/[[F58]]/[[F65]]/[[F66]]<br>
**Status:** authoritative research accounting convention; no live/config change.

## Why this study exists

Studies #31 and #32 established two valid corrections in separate tables:

1. stop mechanics need a raw, session-open price while wealth needs earned cash distributions;
2. the first available hourly bar is not always the session open, so held-position gap fills
   should use the daily raw open for this vendor.

Either correction can be quoted alone. This ledger applies both simultaneously, measures their
interaction, and reruns the two mitigation candidates on the same corrected baseline. It is the
single comparison table future research should use.

## Authoritative convention

- **Entry and intraday bracket path:** retain the hourly raw-price replay.
- **Held position crossing into a new session:** use that session's daily raw open.
- **Stop trigger:** test the raw open; a dividend does not move the executable stop price.
- **Wealth:** credit a cash distribution only when the trade entered before its ex-date and
  remained open through it.
- **Flatten counterfactual:** use the official daily close as a proxy, not a claimed MOC fill.

The daily open and hourly panel still share Yahoo as vendor. The convention repairs interval
serialization and incomplete-session problems; it does not supply executable auction quotes.

## Correction ladder

All returns use sequential fixed-10% position compounding.

| accounting state | trades | total return | maxDD | delta vs legacy |
|---|---:|---:|---:|---:|
| first-hour open, raw price | 1,117 | −10.1471% | −10.1883% | — |
| first-hour open + distributions | 1,117 | −10.1133% | −10.1546% | +0.0338 pp |
| daily open, raw price | 1,117 | −10.2051% | −10.2463% | −0.0580 pp |
| **daily open + distributions** | **1,117** | **−10.1713%** | **−10.2126%** | **−0.0242 pp** |
| joint convention, excluding two partial sessions and rebuilding signals | 1,116 | −10.2593% | −10.3005% | −0.1122 pp |

The joint change is the sum of +0.0338 pp distribution credit and −0.0580 pp open-source
correction, with no material rounded interaction. The corrections partly offset; neither is a
performance choice.

The final row is a sensitivity, not the primary estimate. Removing January 30 and February 2
changes feature history and removes one trade. Relative to the joint baseline, it worsens total
return and maxDD by about 0.088 pp.

## Corrected policy frontier

| policy | total return | maxDD | gap stops | flatten exits | delta vs hold | first-order cost ceiling | descriptive risk gate |
|---|---:|---:|---:|---:|---:|---:|---:|
| corrected hold | −10.1713% | −10.2126% | 32 | 0 | — | — | baseline |
| vol20 ≥15% flatten | −6.0411% | −6.7539% | 11 | 66 | +4.1302 pp | 62.58 bp/exit | pass |
| daily flatten | −5.7746% | −6.7518% | 0 | 126 | +4.3967 pp | 34.89 bp/exit | pass |

The open-source correction changes two marginal gap classifications from `overnight_gap_stop`
to ordinary intrabar `stop_hit`; it does not remove economic losses. Hence the corrected
volatility policy removes 21/32 classified gap stops (65.63%), rather than 21/34 (61.76%) under
the first-hour proxy.

The risk gate remains the pre-existing descriptive rule: remove at least 50% of gap stops,
improve maxDD by at least 2 pp, and avoid reducing total return by more than 1 pp versus the
already-negative hold baseline. Passing is not evidence of alpha or production approval.

## Decision

Use **daily-open, distribution-inclusive** accounting as the canonical research baseline:
**−10.1713% total return / −10.2126% maxDD**.

The consolidation strengthens four prior conclusions:

1. realistic gap accounting leaves the live-shaped strategy materially negative;
2. ex-dividend cash does not explain the tail;
3. the incomplete hourly sessions do not create the negative result;
4. volatility and daily flatten remain risk-control hypotheses only, with thin cost budgets and
   no real-auction validation.

No strategy, signal, configuration, order, or live-trader file is changed.

## Limits and falsifiers

- Yahoo daily opens and hourly bars are not independent vendors.
- Daily OHLC is not an auction tape, quote, spread, or fill.
- Distribution credits omit tax, payment delay, and reinvestment.
- The volatility rule remains post-selected and needs the fixed forward protocol in Study #26.
- Real closing costs above about 62.6 bp for volatility flatten or 34.9 bp for daily flatten erase
  their in-sample terminal-wealth advantage to first order.
- A broker/exchange-quality session-open series that materially changes paired held-position
  outcomes would falsify the chosen open proxy and require a new ledger.
