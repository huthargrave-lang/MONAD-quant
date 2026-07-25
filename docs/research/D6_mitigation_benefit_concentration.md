# Study #40 — Direct Mitigation Benefit Concentration

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E64 (study) · F75 (finding) · refines [[F74]]<br>
**Status:** concentrated but not single-event-dependent.

## Question

Study #39 shows that vol15's benefit is direct on the baseline cohort. Is that direct benefit
broadly repeated, or is it a one-disaster result that disappears when the largest event is removed?

## Method

For every fixed-cohort trade changed by a flatten:

1. compare corrected trade return with its corrected hold counterpart;
2. classify the change as beneficial or harmful;
3. reset one changed trade at a time to its hold return and recompute account terminal wealth;
4. rank positive leave-one-out account contributions;
5. reset the top 1, 3, 5, and 10 events jointly.

This preserves the exact 1,117 baseline entries and isolates direct event concentration from
replacement-trade path changes.

## Gross trade-level balance

| policy | changed trades | beneficial | harmful | gross positive trade delta | gross negative trade delta |
|---|---:|---:|---:|---:|---:|
| vol20 ≥15% | 67 | 43 | 24 | +64.39 pp | −19.54 pp |
| daily flatten | 127 | 70 | 57 | +97.84 pp | −42.05 pp |

Flattening is not uniformly beneficial. Vol15 harms 24 of 67 changed baseline trades; its benefit
comes from the positive tail outweighing ordinary forgone continuation.

## Leave-largest-events-out stress

| policy | full direct delta | after top 1 removed | retained | after top 5 removed | retained | after top 10 removed | retained |
|---|---:|---:|---:|---:|---:|---:|---:|
| vol20 ≥15% | +4.1299 pp | +3.1321 pp | 75.84% | +1.7657 pp | 42.75% | +0.7134 pp | 17.27% |
| daily flatten | +5.1691 pp | +4.1601 pp | 80.48% | +2.5124 pp | 48.60% | +1.0378 pp | 20.08% |

The largest vol15 event is the January 24–27, 2025 hold: flattening avoids 1,062.6 bp of
trade-level loss and contributes about 0.998 pp of account terminal wealth. The next four largest
include November 2025, January 2025, the observed July 2026 gap episode, and October 2025.

The top five produce 57.25% of the direct vol15 account benefit. That is material concentration,
but removing them still leaves +1.7657 pp. Removing the single largest event leaves +3.1321 pp.

## Time concentration

| baseline exit year | changed trades | beneficial/harmful | net trade-return delta |
|---|---:|---:|---:|
| 2024 | 11 | 7 / 4 | +3.8748 pp |
| 2025 | 34 | 23 / 11 | +30.5761 pp |
| 2026 | 22 | 13 / 9 | +10.3928 pp |

Most observed benefit sits in 2025. This reinforces, rather than relaxes, the need for the frozen
multi-year forward endpoint.

## Finding

Vol15's direct mitigation is tail-concentrated but not a one-event artifact. Its largest event
accounts for about one quarter of the direct account improvement; the top five account for about
57%. A positive residue survives removing even the top ten.

This supports the loss-avoidance mechanism while limiting the claim: the magnitude is estimated
from a short sample dominated by 2025 extremes. It is not a stable expected return, and it does not
shorten Studies #26/#35's forward classifier and auction evidence requirements.

No live, signal, order, or configuration path is changed.
