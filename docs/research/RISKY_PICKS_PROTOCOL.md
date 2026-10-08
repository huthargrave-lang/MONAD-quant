# High-risk stock picking, live products: protocol

**Frozen and committed before any price of these funds was loaded (2026-10-08).** A board
of three reviewed the draft. It rejected one six-fund "best of" test and required the
signed, split design below.

## The question

Does picking high-risk individual stocks beat owning the index? The literature predicts
opposite signs for different kinds of high-risk picks:
- **Momentum** predicts the winners keep winning (Jegadeesh and Titman 1993).
- **Lottery picks** are predicted to lose on a risk-adjusted basis. This covers betting
  against beta (Frazzini and Pedersen 2014), the lottery/MAX effect (Bali, Cakici and
  Whitelaw 2011) and long-run IPO underperformance (Ritter 1991).

A stock-level, point-in-time test is blocked: free price data covers only today's
survivors (F113, H61). Live ETFs that pick these stocks are each survivorship-free. They
pay real fees, and no search in this repo chose them.

## Verdict series

Every verdict reads the **vol-matched active** series against the benchmark
(`allocation_stats.vol_matched_active`: positive in mean exactly when the fund's Sharpe
beats the benchmark's). High-risk funds carry beta above 1, and beating the market by
holding more of it is not an edge. A **sign −1** domain tests a predicted
underperformance: its SPA asks whether the benchmark beats the funds.

## Domains (each its own family; prior search 3, published effects)

| Domain | Candidates | Benchmark | Sign | Window from | Eras |
|---|---|---|---|---|---|
| `momentum_product_long` (**primary momentum test**) | PDP (Invesco DWA Momentum, 2007-03) | SPY | +1 | PDP + 21 sessions | ..2009 / 2010..2019 / 2020.. |
| `momentum_product_recent` | QMOM (Alpha Architect concentrated momentum), MTUM (iShares momentum), SPMO (Invesco S&P 500 momentum), PDP | SPY | +1 | QMOM + 21 (2015-12) | ..2019 / 2020..2022 / 2023.. |
| `lottery_product_long` (**primary lottery test**) | FPX (First Trust IPOX-100, 2006-04), SPHB (S&P 500 High Beta, 2011-05) | SPY | −1 | SPHB + 21 | ..2015 / 2016..2020 / 2021.. |
| `lottery_product_recent` | FPX, SPHB, IPO (Renaissance IPO), ARKK (ARK Innovation), FFTY (IBD 50) | SPY | −1 | FFTY + 21 (2015-04) | ..2019 / 2020..2022 / 2023.. |
| `beta_pair_product` | SPLV (S&P 500 Low Volatility) | SPHB | +1 | SPHB + 21 | ..2015 / 2016..2020 / 2021.. |

Each candidate holds 100% of its fund. Execution uses the daily evaluator's static rule:
every 21 sessions in 21 tranches at the open, distributions reinvested, tier1 costs.

Price data is one new snapshot: SPY (calendar), RSP, PDP, QMOM, MTUM, SPMO, FPX, SPHB, IPO,
ARKK, FFTY, SPLV, 2006-01-01..2026-10-02.

Before any trial, each fund's yearly total return from the snapshot is compared with
Yahoo's adjusted close (`tools/snapshot_tr_check.py`). A year more than 1% apart is
reported and explained before running, because missing capital-gain distributions would
understate a fund (ARKK pays them).

## Verdicts, stated in advance

**Momentum domains (sign +1).**
- **Corroborates:** the best point's vol-matched active Sharpe > 0 with t > 1.0, and
  familywise SPA < 5%.
- **Contradicts:** every point's vol-matched active Sharpe ≤ 0.
- **Uninformative:** anything else.

**Lottery domains (sign −1).**
- **Corroborates the underperformance hypothesis:** every point's vol-matched active
  Sharpe < 0, the best negated point has t > 1.0, and familywise SPA on the negated series
  < 5%.
- **Contradicts it:** some point has vol-matched active Sharpe > 0 with
  Sharpe × √years > 1.
- **Uninformative:** anything else.

**`beta_pair_product`.**
- **Corroborates** (low beta beats high beta, risk-adjusted): vol-matched active Sharpe
  > 0 with t > 1.0 and SPA < 5%.
- **Contradicts:** ≤ 0.

The long domains are primary. A recent domain that disagrees with its long domain is
reported as disagreement and does not override it.

**Diagnostics, stated in advance** (no new trial):
- plain active Sharpe and era Sharpes;
- vol-matched active Sharpe against RSP (equal-weight S&P 500, a passive index read
  from the snapshot's total returns). This separates picking from the cap-weight /
  mega-cap tilt of 2015-2026. A verdict whose sign flips against RSP is labelled
  style-dependent.

**What it would change.**
- Lottery corroborates: the project's answer to "high-risk individual picks" is "don't".
- Beta pair corroborates: "take risk through leverage on low-volatility stocks, not
  through high-beta picks". `levered_trend` tests the leverage half.
- Momentum contradicts: D6 extends to "packaged momentum ≈ SPY after fees".
- Momentum corroborates: a momentum sleeve becomes a registration candidate, once the
  gate can score vol-matched series (it refuses these domains until then).

**Minimum detectable vol-matched Sharpe at t = 2:** about 0.45 for PDP (about 19.5
years), 0.52 for the long lottery and beta domains (about 15 years), and 0.61 for the
recent domains (about 10.8 years). Smaller true effects will mostly read as
uninformative.

## Known weaknesses, stated in advance

- **The funds were chosen by name in 2026, so the list is survivor-conditioned.**
  - Each fund's own history is survivorship-free, but funds of these kinds that closed
    are missing, and Yahoo drops delisted tickers.
  - One closure was checked: Innovator's LDRS (closed 2021) held ETFs, not stocks, so it
    is not a peer.
  - No closed stock-picking peer launched before 2016 was confirmed.
  - Survivorship pushes toward a positive result, against the lottery hypothesis and in
    favour of momentum. A momentum corroboration is labelled survivor-conditioned.
- **ARKK's collapse after 2021 is public knowledge.** Its sign is not a prediction, and it
  sits only in the secondary lottery domain.
- **2015-2026 favoured mega-caps.** Most candidates are equal-weighted or tilted toward
  mid caps. This is why the RSP diagnostic exists.
- **Fees differ** (ARKK 0.75%, FFTY 0.80%, the rest 0.15-0.6%). A fund's fee is part of
  what an investor in it gets.

## Board record (2026-10-08)

| Amendment | Source |
|---|---|
| Split into signed families (momentum +, lottery −) instead of one six-fund "best of" | all three |
| Vol-matched series as the verdict statistic | all three |
| Long-window primaries (PDP 2007, which includes the 2009 momentum crash; FPX as a long IPO fund) | statistics, market mechanics |
| RSP style diagnostic | statistics, market mechanics |
| Disclose the name-based inclusion and the survivor-conditioned label | statistics, market mechanics |
| Distribution cross-check against adjusted closes | market mechanics |
| SPLV vs SPHB pair | research value |
| ARKK and FFTY kept, secondary only | statistics and market mechanics (keep) vs research value (drop): majority |

## Results (2026-10-08)

Data: snapshot DS-27a25f68. The yearly distribution cross-check against Yahoo's adjusted
close found 0 of 192 asset-years more than 1% apart. No look-ahead violations in any
domain.

| Domain | Window | Points: vol-matched active Sharpe | Familywise SPA (blocks 20/63/126) | Verdict |
|---|---|---|---|---|
| `momentum_product_long` | 2007-03..2026-10 (19.5 y) | PDP **-0.23** (eras -0.18 / -0.22 / -0.28) | 1.00 | **contradicts** |
| `momentum_product_recent` | 2016-01..2026-10 (10.8 y) | SPMO +0.18, MTUM -0.10, QMOM -0.39, PDP -0.44 | 0.47 / 0.46 / 0.42 | uninformative |
| `lottery_product_long` | 2011-06..2026-10 (15.3 y) | SPHB -0.43, FPX -0.24 (all < 0; best negated t +1.9 to +2.1) | 0.056 / 0.044 / 0.033 | uninformative (the worst block misses 5%) |
| `lottery_product_recent` | 2015-05..2026-10 (11.4 y) | FFTY -0.74, IPO -0.53, FPX -0.38, ARKK -0.28, SPHB -0.28 (all < 0; best negated t +3.1 to +3.5) | 0.004 / 0.001 / 0.002 | **corroborates**, labelled **style-dependent** |
| `beta_pair_product` | 2011-06..2026-10 (15.3 y) | SPLV vs SPHB +0.02 | 0.46-0.47 | uninformative, null |

Ledger runs (benchmark, search):
- momentum long: TR-20261008T152929Z-c7108bc9, TR-20261008T152934Z-3190c0b1;
- momentum recent: TR-20261008T152959Z-590e3a7c, TR-20261008T153004Z-947af75a;
- lottery long: TR-20261008T153029Z-4bcd1746, TR-20261008T153036Z-4d90226a;
- lottery recent: TR-20261008T153109Z-f7cca740, TR-20261008T153110Z-b4f08d24;
- beta pair: TR-20261008T153153Z-6f16b963, TR-20261008T153154Z-77f3f59c.

**RSP diagnostic** (vol-matched active Sharpe against equal-weight S&P 500, from the
snapshot's passive RSP returns):

| Fund | PDP | QMOM | MTUM | SPMO | FPX | SPHB | IPO | ARKK | FFTY | SPLV |
|---|---|---|---|---|---|---|---|---|---|---|
| vs RSP | -0.03 | -0.13 | +0.19 | +0.38 | -0.05 / +0.03 | +0.09 / -0.11 | -0.25 | -0.04 | **-0.41** | -0.05 |

FPX and SPHB show the recent / long window.

**Reading.**
- **High-risk picks lose to SPY, risk-adjusted, but most of that loss is the cap-weight
  tilt.** Against SPY, all five lottery funds lose on Sharpe over 2015-26, and the
  familywise test rejects at every block. Against equal-weight RSP, SPHB turns positive
  (+0.09), and FPX and ARKK are about 0. The verdict is therefore labelled style-dependent.
  What survives against both benchmarks is FFTY (IBD 50: -0.74 vs SPY, -0.41 vs RSP) and,
  more weakly, IPO.
- **Packaged momentum does not beat the market.**
  - PDP, the longest record (19.5 years, including the 2009 momentum crash), lost in
    every era: vol-matched -0.23. Its verdict is contradicts.
  - Of the recent products, only SPMO is positive (+0.18 vs SPY, +0.38 vs RSP). It is
    not significant, and its gain is concentrated after 2023, the mega-cap momentum years.
  - QMOM, the most concentrated product, did worst (-0.39).
- **Low beta does not beat high beta, risk-adjusted** (SPLV vs SPHB +0.02 over 15 years).
  The betting-against-beta premium is absent live in large caps. SPLV merely had a
  smaller drawdown (-36% against -47%).

**What it changes.** The project's answer to "high-risk individual stock picks" is:
- don't, for the IBD-50 / CAN SLIM and IPO styles;
- the rest only reshuffle style exposure, with no edge;
- packaged momentum ≈ the market after fees (D6 extends);
- no low-beta lever-up premium either.

Nothing is registered. The one corroboration is a predicted underperformance and gives
nothing to buy.
