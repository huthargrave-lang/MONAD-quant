# Study #37 — Volatility Decision-Time and Lookahead Audit

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E61 (study) · F72 (finding) · refines [[F59]]/[[F78]]/[[F70]]<br>
**Status:** chronology proven; runtime ingestion still requires shadow evidence.

## Question

Can the vol20 ≥15% decision actually be known before a Nasdaq MOC order becomes locked, or does
the backtest accidentally use the same session's closing return?

## Exact chronology proof

For each session `t`, the tool independently reconstructs annualized vol20 from exactly the 20 QQQ
distribution-inclusive returns ending at `t−1`. All 4,113 values match the vectorized, shifted
classifier to a maximum absolute difference of `2.5e−15`.

The latest required market input for session `t` is therefore the QQQ official close and
distribution at `t−1`. The classification is fixed before session `t` opens—well before Nasdaq's
3:50 p.m. cancellation lock and 3:55 p.m. MOC cutoff.

This proves panel chronology, not operational delivery. The paper shadow must still record when
the prior close/action data arrived and when the decision was materialized.

## Threshold margin

| distance from 15% | all-history nights | two-year strategy-window nights |
|---|---:|---:|
| ≤0.10 percentage points | 49 | 2 |
| ≤0.25 pp | 136 | 12 |
| ≤0.50 pp | 247 | 22 |
| ≤1.00 pp | 488 | 46 |

The rule is not usually balanced on rounding noise, but 12 recent dates lie within 0.25 pp and
should retain full source/version provenance.

## Explicit lookahead falsification

The tempting unshifted calculation includes session `t`'s official close. That close is not known
when an MOC order must be committed. It flips 147 historical threshold labels and 20 labels in the
two-year strategy window, even though both variants happen to flag 357 recent nights overall.

| classifier | flatten exits | gap stops | total return | maxDD | cost ceiling |
|---|---:|---:|---:|---:|---:|
| **lagged, decision-feasible** | 66 | 11 | −6.0411% | −6.7539% | 62.58 bp |
| unshifted current-close lookahead | 65 | 12 | −6.2049% | −7.1522% | 61.02 bp |

Here the lookahead path is worse, so it does not explain the mitigation's apparent benefit.
Nevertheless it changes the policy path materially and is operationally impossible. A leak does
not become acceptable because it hurts the result.

## Finding

The selected vol20 classifier is correctly lagged and fully determined before the classified
session begins. Current-session close must never be substituted into the closing decision.

This closes the research-panel lookahead question. It does not show that a running process receives
and validates inputs on time, submits an accepted auction order, or obtains the modeled cost.
Those remain the paper-shadow logging and real-fill barriers in Studies #26 and #35.

No live, signal, order, or configuration path is changed.
