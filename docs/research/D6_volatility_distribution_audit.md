# Study #36 — QQQ Distribution Contamination of Volatility State

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --selfcheck --json /tmp/gap-program.json`<br>
**Data:** Yahoo QQQ raw close/actions, 2010-02-12–2026-07-22; raw cache SHA-256 `7969bc74…ecdb94`<br>
**Durable derivative:** [`data/qqq_distributions_2010_2026.csv`](data/qqq_distributions_2010_2026.csv)<br>
**RESEARCH_WEB nodes:** E60 (study) · F70 (finding) · refines [[F57]]/[[F67]]<br>
**Status:** economically correct input convention; decision unchanged.

## Question

The vol20 classifier uses QQQ close-to-close returns. The cached `QQQ_close` is split-adjusted but
not distribution-inclusive. Do mechanical ex-dividend price drops inflate realized volatility,
move nights across the 15% threshold, or manufacture the selected policy's result?

## Construction

The audit downloads QQQ with `auto_adjust=False, actions=True`, hashes the 501,193-byte raw cache,
and preserves all 69 positive distributions in a small committed derivative. The cached QQQ close
matches the existing daily panel exactly.

Two lagged 20-session annualized volatility series are compared:

- **raw close:** `close.pct_change()`;
- **distribution-inclusive:** `(close + ex-date cash) / prior close − 1`.

Both are rolled over 20 sessions, shifted one session, and annualized by `sqrt(252)`, so the state
used for a session is known before that session's open. Invesco reports a $0.59111 distribution on
2025-06-23, while Yahoo stores the rounded $0.591
([Invesco QQQ distributions](https://www.invesco.com/us/financial-products/etfs/product-detail?audienceType=investors&productId=QQQ&ticker=QQQ)).

## Volatility effect

Across 4,113 comparable sessions:

| statistic | adjusted minus raw annualized vol |
|---|---:|
| mean signed | −0.01343 percentage points |
| median absolute | 0.00000 pp |
| 95th percentile absolute | 0.18824 pp |
| maximum absolute | 0.76546 pp |

The median is exactly zero because only 20 sessions after each quarterly distribution can differ.

## Threshold flips

Raw close flags 2,324 nights; distribution-inclusive returns flag 2,321. Only five dates flip:

| date | raw vol20 | distribution-inclusive vol20 | direction |
|---|---:|---:|---|
| 2013-07-09 | 15.1081% | 14.9274% | raw-only |
| 2015-01-21 | 14.9168% | 15.0374% | adjusted-only |
| 2016-09-27 | 15.0320% | 14.9863% | raw-only |
| 2019-04-04 | 15.0081% | 14.9842% | raw-only |
| 2021-10-04 | 15.1055% | 14.9241% | raw-only |

Exposure changes from 56.504% to 56.431%. Severe-gap capture remains exactly 75.155%.

## Corrected policy replay

Both rows use Study #33's daily-open, TQQQ-distribution-inclusive accounting.

| classifier input | flatten exits | gap stops | total return | maxDD | cost ceiling | gate |
|---|---:|---:|---:|---:|---:|---:|
| raw QQQ close | 66 | 11 | −6.0411% | −6.7539% | 62.58 bp | pass |
| QQQ distribution-inclusive | 66 | 11 | −6.0411% | −6.7539% | 62.58 bp | pass |

None of the five long-history state flips intersects an active strategy flatten decision, so the
trade path is byte-identical.

## Finding

Raw QQQ closes are conceptually wrong for the volatility state because a cash distribution is not
an economic loss. Correcting them changes five marginal historical labels but **zero strategy
trades or decision metrics**. The selected mitigation result is not an ex-dividend artifact.

Future classifier work should use distribution-inclusive QQQ returns. This is an input-hygiene
correction, not production approval: the rule remains broad, post-selected, and dependent on the
forward and auction gates in Studies #26 and #35.

## Limits

- Yahoo action amounts are rounded; only one recent distribution is sponsor-cross-checked.
- Cash addition approximates adjusted-close total return and ignores tax/reinvestment timing,
  immaterial for this volatility-state comparison.
- The result is threshold-specific. Another threshold close to an ex-dividend-affected value could
  flip more dates and must be re-audited.
