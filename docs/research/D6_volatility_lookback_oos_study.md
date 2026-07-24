# Study #25 — Lagged-Volatility Lookback and Early-Split Falsification

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Classifier data:** QQQ/TQQQ daily adjusted OHLC, 2010-01-04–2026-07-22<br>
**Strategy path:** live-shaped TQQQ replay, 2024-08-01–2026-07-22<br>
**RESEARCH_WEB nodes:** E49 (study) · F59 (finding) · tests [[F57]]/[[F58]]<br>
**Status:** partial robustness evidence; still not a prospective strategy test or live approval.

## Question

Study #23 found that a 20-session QQQ volatility rule at 15% was the best partial overnight-risk
control. Does that result survive a different volatility memory and a threshold selected without
seeing the 2020–2026 classifier outcomes?

## Design

For each 10-, 20-, 40-, and 60-session QQQ realized-volatility lookback:

1. calculate annualized close-return volatility and shift it one session, so the value is known
   before the TQQQ open being classified;
2. on **2010–2019 only**, choose the highest threshold from the fixed grid
   10%, 12.5%, 15%, 17.5%, 20%, 22.5%, 25%, and 30% that still captures at least 60% of TQQQ
   gaps at or below −2%;
3. freeze that threshold and evaluate the instrument classifier on 2020–2026;
4. apply the already-frozen classifier to the 2024–2026 live-shaped strategy path as an
   official-close flatten counterfactual.

The training rule minimizes flagged exposure subject to the explicit capture floor. The
instrument test period is temporally disjoint from threshold selection.

## Results

| QQQ volatility lookback | selected threshold | 2010–19 severe-gap capture | 2020–26 severe-gap capture | strategy flatten exits | strategy gap reduction | strategy total | risk gate |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 10 sessions | 15.0% | 62.7% | 82.2% | 61 | 47.1% | −7.21% | fail |
| 20 sessions | 15.0% | 63.6% | **85.3%** | 66 | **61.8%** | −6.10% | **pass** |
| 40 sessions | 12.5% | 78.2% | 95.0% | 96 | 88.2% | −5.23% | **pass** |
| 60 sessions | 12.5% | 84.0% | 96.5% | 104 | 88.2% | −5.82% | **pass** |

The baseline is −10.15% total / −10.19% maxDD with 34 overnight gap stops. The risk gate requires
at least 50% gap-stop removal, at least 2 percentage points of maxDD improvement, and no more than
1 percentage point of return deterioration.

## What survives

The original 20-session/15% classifier is not merely the result of fitting its threshold on the
recent strategy path. The same 15% threshold is selected from 2010–2019 alone and its severe-gap
capture rises from 63.6% in training to 85.3% in 2020–2026. Its 61.8% strategy gap reduction also
passes the pre-existing risk gate.

That is meaningful evidence for a **risk-state classifier**, not evidence of alpha. The
classifier identifies conditions in which carrying a mechanically leveraged instrument
overnight is historically hazardous.

## What fails

- The 10-session version misses the strategy gate: despite strong unconditional test capture, it
  removes only 47.1% of the path's gap stops. The mitigation is therefore not invariant to a
  plausible lookback change.
- The 40/60-session rules obtain 88.2% gap reduction with 96/104 exits. Their protection is close
  to daily flatten's 126 exits, so they provide less evidence for a selective timing mechanism.
- The strategy remains negative under every rule. Risk reduction does not turn the engine into a
  profitable system.

## Verdict

Study #25 narrows the candidate rather than promoting it. A 20-session QQQ volatility state at a
15% threshold has a defensible historical origin and held-out **classifier** behavior. The
short-lookback falsification and high turnover of longer lookbacks show that “lagged volatility
works” is too broad a claim.

The only honest next hypothesis is therefore specific: freeze **20 sessions / 15%** for a
paper-only forward shadow, collect closing-auction execution evidence and every would-have-held
next open, and judge risk capture and all-in cost without changing the live trader.

## Caveats

- The lookback family and strategy application were examined after Study #23; only the
  instrument threshold split is genuinely temporal.
- The 60% training capture floor and absolute grid are research choices, not natural constants.
- The 2020–2026 classifier test contains the COVID shock and is not independent of the
  2024–2026 strategy slice.
- Official daily closes remain fill proxies. This study adds no auction or order-state evidence.
- Higher capture can be purchased trivially by removing more exposure; 40/60-session success must
  be read together with their 96/104 exits.
