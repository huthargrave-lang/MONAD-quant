# Study #38 — Local Volatility-Threshold Robustness

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E62 (study) · F73 (finding) · refines [[F59]]/[[F70]]/[[F72]]<br>
**Status:** local robustness passed; no threshold reselection.

## Question and guardrail

Does the vol20 policy collapse if the 15% threshold moves by a small amount because of vendor
rounding, revisions, or an arbitrary boundary?

The grid is fixed symmetrically from 14.00% to 16.00% in 0.25 percentage-point steps. It is a
robustness stress only. No row is eligible to replace the already-frozen 15% forward hypothesis,
even if another row looks better in sample.

All rows use distribution-inclusive QQQ volatility and Study #33's corrected daily-open,
distribution-inclusive TQQQ accounting.

## Results

| vol20 threshold | flagged nights | flatten exits | remaining gap stops | total return | maxDD | cost ceiling | gate |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 14.00% | 2,568 | 75 | 7 | −5.7384% | −6.5580% | 59.11 bp | pass |
| 14.25% | 2,509 | 72 | 8 | −5.6813% | −6.5014% | 62.36 bp | pass |
| 14.50% | 2,446 | 68 | 10 | −5.9360% | −6.7539% | 62.28 bp | pass |
| 14.75% | 2,383 | 66 | 11 | −6.0411% | −6.7539% | 62.58 bp | pass |
| **15.00%** | **2,321** | **66** | **11** | **−6.0411%** | **−6.7539%** | **62.58 bp** | **pass** |
| 15.25% | 2,247 | 64 | 12 | −6.2417% | −6.9530% | 61.40 bp | pass |
| 15.50% | 2,199 | 64 | 12 | −6.2417% | −6.9530% | 61.40 bp | pass |
| 15.75% | 2,146 | 61 | 12 | −6.1921% | −6.9745% | 65.23 bp | pass |
| 16.00% | 2,080 | 61 | 12 | −6.1921% | −6.9745% | 65.23 bp | pass |

Across all nine perturbations:

- total return ranges only −6.2417% to −5.6813%;
- maxDD ranges −6.9745% to −6.5014%;
- flatten exits range 61–75;
- remaining gap stops range 7–12;
- first-order cost ceilings range 59.11–65.23 bp;
- **9/9 retain the descriptive risk-gate pass**.

## Finding

The risk-control verdict sits on a local plateau rather than a 15.00% knife-edge. Small threshold
or data-source perturbations change exposure and individual events, but they do not reverse the
descriptive conclusion.

This is not validation of volatility timing. The entire 14–16% neighborhood remains broad
risk-off exposure, every path remains negative, and every result is measured on the same selected
history. The frozen 15% rule still needs the multi-year forward classifier endpoint and the
separate auction-cost evidence gate.

No live parameter, strategy, signal, order, or configuration is changed.
