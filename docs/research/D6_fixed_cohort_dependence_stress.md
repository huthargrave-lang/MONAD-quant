# Study #41 — Fixed-Cohort Direct-Effect Dependence Stress

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**RESEARCH_WEB nodes:** E65 (study) · F76 (finding) · refines [[F58]]/[[F74]]/[[F75]]<br>
**Status:** direct mechanism survives same-path dependence stress; still in-sample.

## Question

Study #24 found positive block intervals for the dynamic vol15 policy. After Studies #39–40
separate direct loss avoidance from replacement trades and expose event concentration, does the
**fixed baseline cohort** still survive dependence-aware uncertainty?

## Construction

The fixed-cohort and corrected-hold account log returns are aligned to the same daily session
calendar. Their paired daily log-return difference is resampled with circular blocks of 5, 20, and
60 sessions, 5,000 replications, deterministically seeded by block length.

This preserves local clustering better than independent trade resampling. The endpoint is relative
terminal wealth, not an annualized Sharpe.

## Results

| policy | observed relative wealth | block-5 95% | block-20 95% | block-60 95% | direct cost ceiling |
|---|---:|---:|---:|---:|---:|
| vol20 ≥15% | +4.5976% | [+1.850%, +8.135%] | **[+1.860%, +8.314%]** | [+1.796%, +8.297%] | 61.64 bp/exit |
| daily flatten | +5.7544% | [+2.341%, +9.930%] | **[+2.568%, +9.660%]** | [+2.702%, +9.523%] | 40.70 bp/exit |

All six dependence intervals exclude zero.

Fixed-cohort relative wealth is positive in every available calendar slice:

| year | vol15 | daily flatten |
|---|---:|---:|
| 2024 partial | +0.3886% | +0.6772% |
| 2025 | +3.1133% | +3.5577% |
| 2026 partial | +1.0468% | +1.4343% |

The full effect remains concentrated in 2025, but is not sign-dependent on that year.

## Finding

The corrected vol15 direct mechanism survives blocks from one week to roughly one quarter and does
not rely on replacement-trade drift. Its block-20 interval is +1.860% to +8.314% relative wealth.

This is stronger evidence for **historical loss avoidance**, not evidence of a forward forecasting
edge. The same history selected the classifier; block resampling cannot create a new regime or
observe MOC implementation. The frozen multi-year event-capture trial and separate 60-fill cost
gate remain required.

The direct vol15 cost ceiling is 61.64 bp/exit, close to the conservative last-hourly dynamic
ceiling of 61.40 bp. That agreement is useful but still only a decision boundary.

No live, signal, order, or configuration path is changed.
