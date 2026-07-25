# Study #42 — Fixed-Cohort Flatten Intervention Outcomes

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E66 (study) · F77 (finding) · refines [[F74]]/[[F75]]/[[F76]]<br>
**Status:** favorable-rate anatomy; tail magnitude remains the primary mechanism.

## Question

How often does a fixed-cohort flatten improve the eventual baseline outcome, and what kinds of
baseline exits does it help or hurt?

## Results

| policy | changed trades | avoided gap stops | favorable | Wilson 95% | one-sided exact p vs 50% | median changed-trade delta |
|---|---:|---:|---:|---:|---:|---:|
| vol20 ≥15% | 67 | 21 | **43 (64.2%)** | 52.2%–74.6% | 0.0136 | +50.00 bp |
| daily flatten | 127 | 32 | 70 (55.1%) | 46.4%–63.5% | 0.1435 | +28.27 bp |

Vol15's intervention is favorable more often than not in this sample, with its Wilson interval just
above 50%. Daily flatten's favorable rate is statistically compatible with a coin flip.

## Outcome anatomy

### Vol20 ≥15%

| eventual baseline exit | changed | favorable / harmful | net trade-return delta | mean delta |
|---|---:|---:|---:|---:|
| overnight gap stop | 21 | 21 / 0 | +50.5258 pp | +240.60 bp |
| ordinary stop | 14 | 14 / 0 | +9.5909 pp | +68.51 bp |
| ambiguous same bar | 8 | 8 / 0 | +4.2694 pp | +53.37 bp |
| target | 24 | 0 / 24 | −19.5424 pp | −81.43 bp |

### Daily flatten

| eventual baseline exit | changed | favorable / harmful | net trade-return delta | mean delta |
|---|---:|---:|---:|---:|
| overnight gap stop | 32 | 32 / 0 | +75.4212 pp | +235.69 bp |
| ordinary stop | 28 | 28 / 0 | +16.7029 pp | +59.65 bp |
| ambiguous same bar | 10 | 10 / 0 | +5.7176 pp | +57.18 bp |
| target | 57 | 0 / 57 | −42.0522 pp | −73.78 bp |

The mechanism is unusually interpretable: every changed trade that later loses at a modeled stop
benefits from the earlier close, and every changed trade that later reaches target is harmed. The
net result depends on asymmetric tail magnitude, not flawless classification.

## Finding

Vol15 is a coarse loss-avoidance intervention, not a precise next-gap predictor. It correctly
intervenes on 21 baseline overnight gap stops, but another 46 changed trades never have that exit;
some later lose and benefit, while 24 later win and are cut short.

Its 64.2% favorable rate is encouraging historical mechanism evidence, but it is not a prospective
precision estimate: the same sample selected the state rule, outcome categories inherit hourly
ordering assumptions, and the large gap-loss magnitude dominates average wealth. Forward
validation must retain both endpoints:

1. strategy gap-event capture;
2. all-in realized cost and rejected/unfilled closes.

No live, signal, order, or configuration path is changed.
