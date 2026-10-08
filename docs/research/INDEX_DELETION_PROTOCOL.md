# S&P 500 deletion rebound: protocol

**Frozen and committed before any deleted stock's price was loaded (2026-10-07).**

## The question

When a stock is demoted out of the S&P 500, index funds must sell it at the effective
date's close, whatever they think of the company. That is forced selling, the mechanism
behind the CEF discount (H404702) and the spin-off drift (F404728). Studies report that
deleted stocks recover part of the drop afterwards (Chen, Noronha and Singal 2004). Does
the rebound hold in 2010-2026 for a long-only buyer, against the mid-cap index the stocks
move to?

## Events (from public metadata, before this protocol)

- **Source.** Wikipedia, "Historical components of the S&P 500", the dated changes table
  (fetched raw 2026-10-07).
- **Kept.** Removals effective 2010-01-01 onward whose stated reason cites market
  capitalization and does not mention an acquisition, merger or spin-off: 112 events.
- **Panel:** `IDXDEL-079e59a6`.
- The table is incomplete in some years (2012: 1 event; 2016: 2). That is a sample, not a
  census; the omissions are assumed unsystematic.
- **Event session.** The first session on or after the effective date. The stock must be
  priced on it, so a ticker later reused by another company drops out.

## Design

| Item | Frozen choice |
|---|---|
| Rule (`deletion_hold`) | buy at the close of event session + k, hold 252 sessions. Each open position weighs 1/max(open, 10); the remainder is IJH (S&P MidCap 400). |
| Grid | k = 1 (the day after the index funds sell) and k = 21 (after a month) |
| Benchmark | IJH 100% |
| Costs | tier2 for deleted stocks (5 bps one-way after 2010), tier1 for IJH |
| Price data | a new snapshot: IJH plus every event ticker, 2009-06-01..2026-10-02 |
| Window | from the first session with 5 events in the trailing 252 sessions, to the snapshot's end |
| Counting | `tools/domain_search.py index_deletion`, which runs both points and the benchmark. Prior search 3, for a published effect. |

## Verdict, stated in advance

- **Corroborates:** the better point has active Sharpe > 0 with t > 1.0, and passes the
  domain report's familywise SPA at 5%.
- **Contradicts:** both points have active Sharpe ≤ 0 after costs.
- **Uninformative:** anything else.

For admission under gate rules v2, a registered point would also need p_gate =
p × (1 + 3) ≤ 0.05, as H404703 showed.

## Known weaknesses, stated in advance

- **Survivorship.** Deleted stocks that later failed or were acquired, and so have no
  price history today, are missing. Demoted stocks fail more often than most, so this
  likely biases the result **toward** a rebound. The unknown share is reported.
- **Power.** About 7 events a year means about 7 positions open at once, so the
  remainder is mostly IJH. The active return is diluted, and t is modest even for a
  real effect.
- **Destination.** Not every demoted stock moves to the S&P 400; some go to the 600. IJH
  is the nearer benchmark for most.

## Result: UNINFORMATIVE (2026-10-07). No usable rebound

- **Data.** Snapshot DS-9731bf32 (IJH plus 67 of 112 event tickers priced). 65 events
  have a price on their effective session; 45 tickers (40%) are missing, as delisted,
  acquired or reused.
- **Window** 2014-11-05..2026-10-02.
- **Ledger:** benchmark TR-20261007T041447Z-15e802e9, search TR-20261007T041447Z-92a865a1.

| Point | Excess Sharpe | CAGR | Max DD | Cost/yr | Active Sharpe vs IJH | Vol-matched | Eras |
|---|---|---|---|---|---|---|---|
| IJH (benchmark) | 0.46 | 9.94% | -42.2% | 0.00% | | | |
| `deletion_hold` k = 21 | 0.53 | 12.66% | -52.5% | 0.08% | +0.31 | **+0.14** | -0.41 / +0.42 / +0.35 |
| `deletion_hold` k = 1 | 0.47 | 11.09% | -51.5% | 0.08% | +0.18 | +0.01 | -0.56 / +0.43 / +0.10 |

- **Statistics.** SPA p 0.20-0.22 at every block; active DSR 0.857; t ≈ 1.07. No
  look-ahead violations.
- **Verdict.** Active Sharpe is positive but fails the familywise SPA, so the result is
  **uninformative**.
- **Interpretation.** The vol-matched active Sharpe (+0.14 and +0.01) shows most of the
  apparent edge is extra volatility, and the first era is negative. Survivorship most
  likely biases toward a rebound, so even this is generous. There is no usable deletion
  rebound for a long-only buyer in this period.
