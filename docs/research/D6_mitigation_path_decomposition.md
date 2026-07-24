# Study #39 — Direct Mitigation vs Opportunity-Path Replacement

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E63 (study) · F74 (finding) · refines [[F58]]/[[F67]]<br>
**Status:** causal decomposition; strengthens vol15 mechanism, qualifies daily-flatten return.

## Question

Flattening a position early frees the one-position engine to accept different later signals. Is the
observed policy benefit direct avoidance of overnight loss on the baseline cohort, or does it rely
on a favorable replacement-trade path?

## Construction

The corrected hold path has 1,117 trades and returns −10.1713%.

For each policy the tool computes two counterfactuals:

- **fixed cohort:** retain every one of the 1,117 baseline entries, but close a baseline trade at
  the policy's earlier official-close proxy when applicable; do not admit replacement entries;
- **dynamic policy:** rerun the normal one-position engine, allowing earlier exits to change which
  later signals are eligible.

Both use daily opens for held-position gaps, distribution-inclusive TQQQ wealth, and
distribution-inclusive lagged QQQ volatility.

This is not a perfect additive attribution because sequential compounding and account state are
path-dependent. It cleanly answers whether the headline depends on newly admitted signals.

## Results

| policy | fixed-cohort trades | fixed total | direct delta vs hold | dynamic trades | dynamic total | dynamic delta | path increment |
|---|---:|---:|---:|---:|---:|---:|---:|
| vol20 ≥15% | 1,117 | −6.0414% | +4.1299 pp | 1,154 | −6.0411% | +4.1302 pp | **+0.0003 pp** |
| daily flatten | 1,117 | −5.0022% | +5.1691 pp | 1,187 | −5.7746% | +4.3967 pp | **−0.7724 pp** |

### Volatility policy

- 1,116 signal entries are shared;
- 38 are dynamic-only and one is baseline-only;
- the fixed cohort has 67 flattens; the dynamic path has 66;
- fixed maxDD is −6.8310%, versus dynamic −6.7539%;
- direct same-cohort improvement is 99.99% of the dynamic terminal-return delta.

The 38 replacement signals nearly net to zero in aggregate. The observed terminal benefit is
therefore direct risk removal, not hidden replacement-trade alpha.

### Daily flatten

- 1,115 entries are shared;
- 72 are dynamic-only and two are baseline-only;
- the fixed cohort has 127 flattens; the dynamic path has 126;
- fixed maxDD is −6.0706%, versus dynamic −6.7518%;
- the replacement path **subtracts 0.7724 pp** from the direct cohort benefit.

Daily flatten's reported +4.3967 pp benefit is conservative relative to the fixed baseline cohort,
but its exact return and drawdown are materially opportunity-path-dependent.

## Finding

The selected vol15 result is mechanism-clean on this decomposition: essentially its entire
terminal benefit comes from closing the same baseline positions before flagged nights. It does not
borrow a favorable result from newly available signals.

Daily flatten also has a positive direct effect, but its dynamic path admits many more trades and
gives back part of that benefit. Its exact backtest total should not be interpreted as a pure
overnight-risk estimate.

Neither conclusion creates alpha or production approval. Both paths remain negative, the
volatility classifier remains selected in-sample, and auction cost remains unobserved.

No live, signal, order, or configuration file is changed.
