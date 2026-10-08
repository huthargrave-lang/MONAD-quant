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
