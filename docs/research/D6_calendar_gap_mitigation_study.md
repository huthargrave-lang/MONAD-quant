# Study #21 — Calendar-Aware Partial Flattening

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Data:** pinned TQQQ full-session hourly path, 2024-08-01–2026-07-22<br>
**RESEARCH_WEB nodes:** E45 (study) · F55 (finding) · refines [[F52]]<br>
**Status:** descriptive counterfactual; no policy clears the pre-registered gate or is approved
for production.

## Question

Full end-of-day flatten removes all overnight risk but creates 126 close executions. Can a
calendar-known, lower-turnover policy capture the concentrated weekend/holiday tail while
preserving most ordinary overnight holds?

Unlike clock cutoffs, this does not select signals by time of day. A position is closed at the
prior session's official daily close proxy only when the already-known exchange calendar says the
next session is at least 2, 3, or 4 calendar days away.

## Where the damage occurs

The 34 strategy-conditioned open-through-stop events produce 53.76 percentage points of gross
paired trade damage:

| calendar spacing to next open | events | damage | damage share | median / maximum event |
|---:|---:|---:|---:|---:|
| 1 day | 26 | 30.06 pp | 55.92% | 0.88 / 3.63 pp |
| 3 days | 5 | 13.63 pp | 25.34% | 1.37 / 8.96 pp |
| 4 days | 3 | 10.07 pp | 18.74% | 4.11 / 4.88 pp |

Weekend/long-closure opens are only **8/34 events but 44.08% of damage**. The tail is also
concentrated across individual events: the largest event contributes 16.66%, the top three
33.37%, the top five 46.14%, and the top ten 68.81%.

That concentration makes the apparent policy benefit fragile: one January 2025 Monday accounts
for 8.96 pp of gross trade damage.

## Policy results

| policy | flatten exits | trades | total | maxDD | remaining gap stops | gap-count reduction | directly targeted damage |
|---|---:|---:|---:|---:|---:|---:|---:|
| hold overnight | 0 | 1,117 | −10.15% | −10.19% | 34 | 0% | 0% |
| flatten before ≥4-day closure | 4 | 1,120 | −9.35% | −9.39% | 31 | 8.82% | 18.74% |
| flatten before weekend/≥3-day closure | 29 | 1,131 | **−8.61%** | **−8.65%** | 26 | 23.53% | **44.08%** |
| flatten before any nonconsecutive session (≥2 days) | 33 | 1,134 | −8.80% | −8.84% | 26 | 23.53% | 44.08% |
| flatten every close | 126 | 1,187 | −5.77% | −6.75% | 0 | 100% | 100% |

No two-day gap event affected the baseline strategy path. The ≥2-day policy therefore performs
four extra closes without removing another observed gap stop and ends worse than the ≥3-day rule.
This is a useful falsification: “include every holiday eve” is not free.

The weekend/long-closure rule improves total return by 1.54 pp and maxDD by 1.54 pp while using
77% fewer flatten exits than daily flatten. It still fails both pre-registered risk thresholds:
only 23.5% of events are removed (need 50%) and maxDD improves less than 2 pp.

## Approximate execution-cost budgets

Allocating each policy's observed path improvement evenly across its calendar exits gives a rough
first-order break-even extra cost:

| policy | break-even extra cost per calendar exit |
|---|---:|
| ≥4-day closure | 198.8 bp |
| weekend/≥3-day closure | 53.2 bp |
| any nonconsecutive session | 40.8 bp |
| every close | 34.7 bp |

These are not expected costs. They expose how much close-price proxy error, auction impact, and
incremental turnover the in-sample benefit can absorb before disappearing.

### Close-proxy validation and simulator correction

The last hourly-bar close and official daily close agree at the median, but across 494 sessions
their median absolute difference is 1.82 bp, 95th percentile 8.19 bp, 99th percentile 17.63 bp,
and maximum 129.91 bp; 13.16% differ by more than 5 bp. The official daily close is therefore the
primary MOC proxy. Replaying with the last hourly close changes aggregate totals only modestly:
weekend/long closure −8.61% → −8.61%, daily flatten −5.77% → −5.81%.

This audit also caught and corrected a more serious harness error: an entry at the session open
had previously been allowed to “flatten” at the prior session's close before the position existed.
The simulator now requires `loc > entry_loc` before any EOD/calendar flatten. A synthetic
opening-entry self-check guards the correction. All figures above are post-correction.

## Operational reality

IBKR defines a market-on-close order as an attempt to execute at or near the official close and
warns that closing-auction imbalances can move the price
([IBKR MOC glossary](https://www.interactivebrokers.com/campus/glossary-terms/market-on-close-order/)).
Its current lesson states Nasdaq stops accepting MOC orders at 3:55 p.m. ET and NYSE at 3:50 p.m.
ET ([IBKR MOC lesson](https://www.interactivebrokers.com/campus/trading-lessons/ibkr-desktop-market-on-close-order/?retakeFinal=1)).
Nasdaq begins publishing closing imbalance information at 3:50 and executes the cross at 4:00
([Nasdaq closing cross](https://www.nasdaqtrader.com/trader.aspx?id=openclose)).

The repository's final scheduled cycle at 15:32 ET is before those cutoffs, so MOC submission is
operationally conceivable. Implementation would still require:

1. canceling the live GTC bracket without leaving an unprotected/racing position;
2. submitting and confirming the correct close quantity before the venue cutoff;
3. reconciling partial fills/rejections and blocking same-cycle re-entry;
4. recording the actual auction fill rather than either historical close proxy.

The existing `cancel_and_close()` path sends an immediate market close, not MOC. This study does
not modify it.

## Finding

Calendar-known partial flattening is a real turnover/risk trade-off, but not a solution:

- Weekend/long closures concentrate 44% of damage and can be targeted with 29 rather than 126
  exits.
- They represent only 24% of gap-stop events, so most risk remains on ordinary weekday opens.
- The policy misses the pre-registered gate and its benefit is dominated by a few events.
- Adding two-day holiday eves adds turnover without removing another observed event.

If overnight exposure must be eliminated, daily flatten remains the mechanism-complete candidate.
If turnover must be limited, weekend/long-closure flatten is the only partial policy worth future
out-of-sample/auction-cost study—but it must be described as accepting most weekday jump risk.
