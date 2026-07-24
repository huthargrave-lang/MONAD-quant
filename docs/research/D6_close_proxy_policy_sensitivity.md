# Study #34 — Mitigation Close-Proxy Sensitivity

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**Data:** pinned Yahoo TQQQ hourly/daily raw bars and corporate actions, 2024-08-01–2026-07-22<br>
**RESEARCH_WEB nodes:** E58 (study) · F68 (finding) · refines [[F58]]/[[F67]]<br>
**Status:** proxy robustness passed; real-auction execution remains unvalidated.

## Question

Study #33 made the official daily close the preferred flatten counterfactual. Do the volatility
and daily-flatten conclusions depend materially on that choice versus the last hourly-bar close?

This matters because the selected volatility policy and full daily flatten both realize their
apparent benefit at synthetic closing prices. Agreement between two vendor fields cannot validate
an MOC fill, but disagreement could invalidate the backtest comparison immediately.

## Construction

Both policy replays use Study #33's corrected baseline:

- daily raw open for an already-held position's new-session fill;
- cash distributions credited only to trades that earned them;
- one position, entry-bar bracket scan, and the live 10-bar cap;
- identical entries, exit timestamps, and exit types.

Only the flatten price changes:

1. Yahoo official daily close;
2. the final Yahoo hourly bar's close.

The paired trade paths are asserted identical. Differences therefore isolate the closing-price
proxy rather than signal selection or opportunity-path drift.

## Results

| policy | exits | official-close total | last-hourly total | official minus hourly | median absolute flattened-trade difference | 95th percentile | maximum |
|---|---:|---:|---:|---:|---:|---:|---:|
| vol20 ≥15% flatten | 66 | −6.0411% | −6.1189% | +0.0778 pp | 1.93 bp | 10.21 bp | 59.29 bp |
| daily flatten | 126 | −5.7746% | −5.8090% | +0.0344 pp | 1.40 bp | 9.09 bp | 59.29 bp |

The official close is modestly more favorable in this sample, but the effect is small relative to
the roughly four-percentage-point policy deltas. The maxDD difference is +0.0141 pp for volatility
flatten and −0.0165 pp for daily flatten; even its direction is not uniformly favorable.

## Cost boundary and gate

| policy | official-close cost ceiling | last-hourly cost ceiling | descriptive risk gate |
|---|---:|---:|---:|
| vol20 ≥15% flatten | 62.58 bp/exit | 61.40 bp/exit | pass under both |
| daily flatten | 34.89 bp/exit | 34.62 bp/exit | pass under both |

The close proxy therefore does not drive the descriptive pass. It moves the volatility ceiling by
1.18 bp and the daily ceiling by 0.27 bp. Those ceilings remain first-order break-even estimates,
not expected executable costs.

## Finding

The mitigation ranking and descriptive gate survive the last-hourly-close alternative. This
removes one accounting fragility from the in-sample result, but it does **not** validate either
policy for production.

Both fields come from Yahoo and neither measures auction imbalance, bid/ask spread, latency,
market impact, fees, rejects, or an actual broker fill. Study #26's conclusion therefore remains:
paper shadow can test classifier plumbing and event capture, but real closing-auction evidence is
required before an execution-cost gate can pass.

## Falsifiers

- A broker/exchange MOC sample whose paired cost exceeds 61.4 bp for the volatility policy or
  34.6 bp for daily flatten eliminates its observed terminal-wealth advantage to first order.
- A truly independent close/auction source that changes the policy delta by several percentage
  points would overturn this proxy-robustness result.
- Forward event capture below the frozen Study #26 gate rejects the volatility policy regardless
  of close proxy.

No live, order, signal, or configuration path is modified.
