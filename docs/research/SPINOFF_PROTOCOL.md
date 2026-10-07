# Spin-off drift: protocol

**Frozen and committed before any spin-off price was loaded (2026-10-07).** The events
come from SEC filing metadata only.

## The question

Spun-off companies have outperformed after the forced selling that follows the
distribution: index funds and parent-company holders dump shares they never chose
(Cusatis, Miles and Woolridge 1993; Greenblatt's "special situations"). This is the same
kind of mechanism as the CEF discount: prices move because of who must sell, not what the
business is worth. Does it survive in 2011-2026?

## Events (built before this protocol, from SEC metadata)

- **Registrants.** Every filer of an original Form 10-12B, 2011-2026, from EDGAR
  full-text search: 378 registrants.
- **Spin-off marker.** One of the registrant's first three 10-12B or 10-12B/A filings
  includes an EX-99.1 document larger than 200 kB: the information statement a
  distribution sends to the parent's shareholders. That gives 274 spin-offs. Checked on
  known cases: PayPal, Fortive, Otis and Kyndryl are marked; Lonestar, a non-spin
  registration, is not.
- **Survivors.** Spin-offs with a common ticker listed today: 159.
- **Event session.** The spin-off's first priced session (regular way) in the snapshot,
  if it falls within 30 days before to 540 days after its first 10-12B. An earlier first
  price means a company already listed; a much later one means an abandoned spin.

## Design

| Item | Frozen choice |
|---|---|
| Rule (`spinoff_hold`) | buy each event at the close of event session + k, hold 252 sessions, sell at the close. Each open position weighs 1/max(open, 10); the remainder is IWM. |
| Grid | k = 1 (buy at once) and k = 21 (after the first month of forced selling) |
| Benchmark | IWM 100% |
| Costs | tier `smallcap` for spin-offs (30 bps one-way; conservative for the large ones), tier1 for IWM |
| Price data | a new snapshot: IWM plus every surviving spin-off ticker, 2011-01-01..2026-10-02 |
| Window | from the first session with 10 events in the trailing 252 sessions, to the snapshot's end |
| Counting | `tools/domain_search.py spinoff_drift`, which runs both points and the benchmark. The declared prior search is 3, for a published effect. |

## Verdict, stated in advance

- **Corroborates:** the better point has active Sharpe > 0 with t > 1.0, and passes the
  domain report's familywise SPA at 5%.
- **Contradicts:** both points have active Sharpe ≤ 0 after costs.
- **Uninformative:** anything else.

## Known weaknesses, stated in advance

- **Survivorship, with an unknown sign.** 115 of 274 spin-offs (42%) no longer trade and
  are missing.
  - Acquired spin-offs, which the literature names as a main source of the excess
    return, are missing. That biases the test against the effect.
  - Spin-offs that failed are also missing. That biases it toward the effect.
  - The result is therefore weaker evidence than the counted statistics alone suggest,
    whichever way it comes out.
- **Benchmark mismatch.** Spin-offs span large to small caps, and IWM is a small-cap
  index. The vol-matched active Sharpe is reported to expose a size or beta artifact.
- **Marker errors.** A non-spin 10-12B with a large EX-99.1, or a spin-off whose
  information statement was filed under another exhibit number.

## Result: CORROBORATES under the pre-stated criterion (2026-10-07)

Data: snapshot DS-d038fe35 (IWM plus 125 of the 159 surviving spin-offs; 34 not served by
Yahoo) and events panel SPINEVENTS-fce8d5c3. Window 2014-11-13..2026-10-02, 11.9 years.
Ledger: benchmark TR-20261007T011447Z-a0562a41, search TR-20261007T011447Z-df9569e4.

| Point | Excess Sharpe | CAGR | Max DD | Cost/yr | Active Sharpe vs IWM | Vol-matched | Eras |
|---|---|---|---|---|---|---|---|
| IWM (benchmark) | 0.40 | 9.02% | -41.1% | 0.00% | | | |
| `spinoff_hold` k = 21 | 0.77 | 19.47% | -44.3% | 0.78% | **+0.80** | +0.71 | +0.01 / +0.45 / +1.40 |
| `spinoff_hold` k = 1 | 0.72 | 18.14% | -44.5% | 0.80% | +0.64 | +0.56 | +0.30 / +0.45 / +0.93 |

- **Statistics.** Familywise SPA p for k = 21 is 0.012, 0.021 and 0.019 at blocks
  20/63/126. Active DSR 0.997. t = 0.80 × √11.9 ≈ 2.8. No look-ahead violations at 12 cuts.
- **Verdict: corroborates** (active Sharpe > 0, t > 1.0, SPA < 5%).

**Diagnostics** (from the recorded series, no new trial):
- Against SPY, the k = 21 point has active Sharpe +0.42 (+6.3%/yr, t 1.45).
- Regressed on SPY and IWM (betas 0.19 and 0.81), its alpha is **+8.9%/yr, t 2.57**. The
  edge is not the large-over-small-cap tailwind of 2014-2026.
- Active Sharpe against SPY by era is +0.17, +0.01 and +0.87.
- **The survivorship pattern points the other way.** Recent spin-offs have had the least
  time to be acquired or fail, so the 2022-2026 cohort is the most complete. It shows the
  strongest effect; the older cohorts, filtered harder by survival to 2026, are weaker.
  Survivorship inflation would predict the reverse. This argues against, but does not
  rule out, a survivorship artifact.

**Status.** This is development evidence with a known, unquantified survivorship bias. The
forward window is the clean test: spin-offs that happen after registration have no
survivorship.

The admission machinery's forward loader (`admit_tactical.default_load_forward`) rebuilds
the development universe, so it would see no new spin-offs. An event-domain forward loader,
which adds new 10-12B registrants and their prices, is required before this can be
admitted.
