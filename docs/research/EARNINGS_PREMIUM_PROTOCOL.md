# Earnings-announcement premium in small caps: protocol

**Frozen and committed before any announcement-window return was computed (2026-10-06).**
The price snapshot (DS-0205b226: IWM plus small caps, 2020-2026) was built for the insider
test, and its returns were examined only for insider signals. No one has computed returns
around earnings announcements in this repo.

## The question

Stocks earn more in the window in which they are expected to report earnings (Frazzini and
Lamont 2007, "The earnings announcement premium and trading volume"; Barber, De George,
Lehavy and Trueman 2013, global evidence). The usual explanation is attention-driven
buying and announcement risk. Does a long-only version survive small-cap trading costs?

## Design

| Item | Frozen choice |
|---|---|
| Announcements | 8-K filings with Item 2.02, dated by filing date, from data.sec.gov submissions for every snapshot ticker (`src/research/earnings_data.py`) |
| Expected announcer at session t | filed an earnings 8-K in (t − 365, t − 365 + h] calendar days, the same window one year earlier. Only past filings are read. |
| Eligible at t | priced at t, 252 sessions listed, and at least 4 earnings 8-Ks filed before t |
| Candidate (`earn_window`) | equal weight over eligible expected announcers, decided at t's close and traded at the next close (daily), if at least 20 qualify; otherwise equal weight over all eligible stocks |
| Grid | h = 7 days (about the announcement week) and h = 30 days (about the announcement month) |
| Benchmark (`earn_universe`) | equal weight over all eligible stocks, every 21 sessions in 21 tranches |
| Costs | tier `smallcap`: 30 bps one-way after 2010 |
| Window | from the first session with 200 eligible stocks to 2026-10-02 |
| Counting | `tools/domain_search.py earnings_premium`, which runs both points and the benchmark. The declared prior search is 3, for a published effect. |

## Verdict, stated in advance

- **Corroborates:** the better point has active Sharpe > 0 with t > 1.0, and passes the
  domain report's familywise SPA at 5%.
- **Contradicts:** both points have active Sharpe ≤ 0 after costs.
- **Uninformative:** anything else.

A corroborated point may be registered as a hypothesis, with its forward window, under
gate rules v2.

## Known weaknesses, stated in advance

- **Survivorship.** The snapshot holds tickers priced today, so failed small caps are
  missing. This affects candidate and benchmark alike, which shrinks it in the relative
  test.
- **Selected universe.** These are the insider study's tickers: small caps that had
  insider purchase clusters. They are not a random small-cap sample.
- **Item 2.02 date vs press release.** Most releases are filed the same day; a few lag.
- **Costs dominate.** The 30-day point turns over about 12 times a year. At 30 bps
  one-way that is roughly 7%/yr, similar to the published long-short premium.

## Result: CONTRADICTS (2026-10-07)

Data: dates panel EARNDATES-adfd2075, covering 1,171 of 1,259 snapshot tickers with
earnings 8-Ks. Window 2020-12-30..2026-10-02. Ledger runs: benchmark
TR-20261007T005042Z-27c366e9, search TR-20261007T005045Z-614e46c5.

| Point | Excess Sharpe | CAGR | Max DD | Cost/yr | Active Sharpe | Vol-matched |
|---|---|---|---|---|---|---|
| Benchmark (EW universe) | 0.26 | 6.75% | -35.2% | 0.47% | | |
| `earn_window` 30 days | -0.35 | -7.00% | -58.9% | 15.49% | **-1.62** | -1.67 |
| `earn_window` 7 days | -1.01 | -21.04% | -78.3% | 33.86% | **-2.69** | -2.69 |

- Both points have active Sharpe ≤ 0 after costs, in every era (best era -1.25).
- SPA p = 1.00 at every block; active DSR 0.00.
- No look-ahead violations at 12 cuts.

**Why.** Costs ran about twice the protocol's estimate. Daily equal weighting re-trims
every holding as names enter and leave, not only the entering and leaving names. Even
before costs, the 30-day point beat the universe by only about 1-2% a year, inside its
noise. In this sample of small caps, the effect is too small to pay for small-cap trading.
