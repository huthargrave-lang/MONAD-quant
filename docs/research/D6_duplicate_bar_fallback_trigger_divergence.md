# Study 68 — Duplicate bar-fallback software-trigger divergence

**Date:** 2026-07-24<br>
**Status:** observed archived input divergence plus deterministic decision
counterfactual; zero realized `last_close`-labeled triggers retained; no
protected-path change authorized<br>
**Artifact:** `tools/overnight_gap_risk_study.py` →
`duplicate_bar_fallback_trigger_divergence_audit`

## Question

If broker and yfinance prices both fail, can the historically duplicated trader
writers use different signal-bar closes and make opposite software stop or
take-profit decisions for the same position and cycle?

## Verdict

**Yes. Ten archived in-position minute slots contain paired writer values on
opposite sides of a risk boundary.**

| archived endpoint | result |
|---|---:|
| in-position signal rows | 281 |
| unique trade-cycle minute slots | 167 |
| slots with multiple writer values | 114 |
| stop-decision forks | **5** |
| take-profit-decision forks | **5** |
| distinct affected trades | **9** |
| all divergent slots | **10 / 167 (5.99%)** |
| divergent share of multi-writer slots | **10 / 114 (8.77%)** |
| writer timing span | **0.000125–2.112320 s** |
| cross-session-date forks | **9 / 10** |
| retained software triggers labeled `last_close` | **0** |

Every fork combines the cycle’s just-started, still-in-progress hourly bar with
an older bar. Nine pair the new session’s opening bar with the prior session;
one pairs a new intra-session hour with the preceding completed hour.

The two writers therefore receive a reachable deterministic split:

```text
writer A fallback <= stop  → force close
writer B fallback > stop   → hold
```

The same split applies in reverse around take-profit. The order in which the
writers reach the boundary determines which action occurs, and the lifecycle is
not atomically claimed before the force-close order.

## Relationship to prior evidence

Study 49 proved why paired writers selected different current tails: UTC-naive
vendor labels were compared with host-local naive time, making completed-bar
selection environment dependent. Study 62 proved the same writers doubled the
holding counter. This study establishes direct risk-decision materiality at ten
specific archived position/cycle boundaries.

## Honesty boundary

All six retained software-stop messages use the provenance-unverified `live`
label, not `last_close`. The ten forks prove that opposite decisions would
occur **if both writers reached the final bar-close fallback**; they do not show
that this happened historically or that a false close order filled.

Entry basis is reconstructed from retained return and exit price and inherits
their execution-identity limitations.

## Falsification gate

1. Select one exchange-time completed bar deterministically and carry its
   timestamp/completion proof in the fallback object.
2. Atomically claim lifecycle and cycle ownership before a software-risk order.
3. Persist source bar, trigger decision, lifecycle, close order/executions, and
   exact-flat result under one identity.
4. Test current-tail presence/absence, host timezones, paired writers, boundary
   straddles, provider failure, and late fills.

## Reproduce

```bash
venv/bin/python tools/overnight_gap_risk_study.py \
  --selfcheck --json /tmp/gap_program_study68.json
```
