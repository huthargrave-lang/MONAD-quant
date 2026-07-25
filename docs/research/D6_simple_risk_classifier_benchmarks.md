# Study #27 — Simple Risk-Classifier Benchmarks

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Data:** TQQQ/QQQ daily adjusted OHLC, 2010–2026; live-shaped path, 2024–2026<br>
**RESEARCH_WEB nodes:** E51 (study) · F61 (finding) · null benchmark for [[F57]]/[[F59]]<br>
**Status:** same-sample mechanism benchmark; no policy approval.

## Question

Does lagged QQQ volatility uniquely concentrate severe TQQQ gap risk, or can a trivial rule—
“flatten for N sessions after any TQQQ gap at or below −2%”—do the same?

## Method

Compare the 20-session QQQ-volatility ≥15% rule with recent-severe-gap windows of 1, 2, 3, 5,
10, and 20 sessions. Every flag uses only information available before the classified open.

For the 2010–2026 instrument history:

- **exposure removed** is the fraction of all nights flagged;
- **severe-gap capture** is the fraction of TQQQ ≤−2% opens flagged;
- **capture lift** is capture divided by exposure removed. Random flags have expected lift 1;
- **downside-excess capture** weights loss beyond the 0.5% stop.

Each flag is then applied as an official-close flatten counterfactual to the same 2024–2026
live-shaped strategy path.

## Results

| rule | nights removed | severe gaps captured | capture lift | flatten exits | strategy gaps removed | strategy total | risk gate |
|---|---:|---:|---:|---:|---:|---:|:---:|
| QQQ vol20 ≥15% | 56.5% | 75.2% | 1.33× | 66 | **61.8%** | −6.10% | **pass** |
| severe gap in prior 1 | 11.7% | 15.7% | 1.34× | 8 | 2.9% | −10.36% | fail |
| prior 2 | 21.6% | 28.6% | 1.32× | 18 | 17.6% | −9.67% | fail |
| prior 3 | 30.0% | 41.2% | **1.38×** | 29 | 26.5% | −8.86% | fail |
| prior 5 | 42.8% | 55.9% | 1.31× | 39 | 38.2% | −8.22% | fail |
| prior 10 | 63.4% | 76.6% | 1.21× | 72 | 47.1% | −7.87% | fail |
| prior 20 | 82.9% | 88.8% | 1.07× | 104 | 79.4% | −5.97% | **pass** |

The baseline strategy is −10.15% total / −10.19% maxDD with 34 overnight gap stops.

## Finding

On unconditional instrument data, volatility is **not uniquely informative**. Its 1.33× capture
lift is essentially the same as the transparent 1–5-session clustering rules (1.31×–1.38×).
That supports Study #23's clustering mechanism and rejects a story in which QQQ volatility is a
special predictor by itself.

On this strategy path, however, the 20d/15% rule removes 61.8% of gap stops, while the
roughly exposure-matched prior-10 rule removes only 47.1% and fails the gate. A recent-gap rule
passes only at 20 sessions, when it disables 82.9% of all nights and uses 104 flatten exits—close
to daily flatten's 126.

The narrow conclusion is:

- volatility does not provide exceptional unconditional concentration beyond gap clustering;
- it happens to align better with this strategy's gap events than the simple rules;
- that strategy-conditioned advantage is same-sample and is exactly what the long forward
  horizon in Study #26 must test.

## Caveats

- Rules and windows share the same history; no multiple-testing-adjusted superiority claim is
  made.
- Capture lift does not price false positives, opportunity cost, or auction execution.
- The recent-gap benchmark keys off TQQQ itself while the volatility rule keys off QQQ; they are
  transparent mechanism comparators, not identical feature families.
- All counterfactual paths remain negative.
