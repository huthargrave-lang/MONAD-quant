# Trend-timed leverage, live: protocol

**Frozen and committed before any SSO price was loaded (2026-10-08).** A board of three
(statistics, market mechanics, research value) reviewed the draft and required the
amendments built in below. No 3x domain and no per-index family: see "Board record".

## The question

Gayed and Bilello (2016, "Leverage for the Long Run") argue that a daily-reset leveraged
fund decays most when volatility is high, and that high volatility clusters below the
200-day moving average. So holding the fund only above that average should make leverage
pay. F404704 already found that a 1x 200-day filter does not beat the static 60/40 (vol
matched +0.14, SPA 0.68). The new quantity is the **decay increment**, which exists only
under leverage.

ProShares Ultra S&P 500 (**SSO**, 2x daily, June 2006) is a live fund. Its swap financing,
fees and decay are real. Its window includes 2008, 2011, 2015-16, Q4 2018, 2020 and 2022.

## Design (domain `levered_trend`, family `levered_trend.v1`)

| Item | Frozen choice |
|---|---|
| Primary point (`trend_timed` SSO, daily) | 100% SSO while SPY's total-return index closes above its 200-session SMA, else T-bills (DTB3). Decided at each close, executed at the next open, one tranche, an order only when the state changes. This is the published rule. |
| Control: `trend_timed` SSO, tranched | the same signal on F404704's schedule: checked every 21 sessions in 21 tranches |
| Control: `trend_timed` SPY, daily | the same rule at 1x |
| Control: `fund_held` SSO | SSO held, every 21 sessions in 21 tranches |
| Benchmark (`held` SPY) | SPY held, every 21 sessions in 21 tranches |
| Costs | tier1 (both liquid ETFs) |
| Price data | a new snapshot: SPY (calendar) and SSO, 2005-01-01..2026-10-02 |
| Data check | the domain refuses any snapshot with a night or day leg beyond ±40% for SPY or SSO. The snapshot's own check reads only the close-to-close total, so a split-day open left unadjusted would cancel in it. A refused snapshot is rebuilt, never repaired. |
| Window | from the first session SSO has 21 sessions and SPY's SMA is defined (about 2006-07) to the snapshot's end |
| Counting | `tools/domain_search.py levered_trend`, which runs all four points and the benchmark. Prior search **7**: the published rule (3) plus F404704's four SMA points. |
| Eras | start..2009-12-31 / 2010..2015-12-31 / **2016..end, after publication** |

## Verdict, stated in advance

The verdict series is the **vol-matched active** series against held SPY
(`allocation_stats.vol_matched_active`, which is positive in mean exactly when the
member's Sharpe beats SPY's). Leverage alone cannot move it.

- **Corroborates.** All four must hold for the primary point:
  1. vol-matched active Sharpe > 0, with t > 1.0;
  2. familywise SPA on the vol-matched series < 5%;
  3. the 2016..end era > 0 (after publication);
  4. the same sign over 2010..end as over the full window (without 2008).
- **Contradicts.** Primary vol-matched active Sharpe ≤ 0.
- **Single episode.** The 2006-09 era is positive but the two later eras are ≤ 0. This
  label is reported, and the verdict is uninformative.
- **Uninformative.** Anything else.

**Mechanism, stated in advance.** The decay increment, computed from the recorded series
of the four points and the benchmark (no new trial):

g = [lg(timed SSO) − lg(held SSO)] − 2 × [lg(timed SPY) − lg(held SPY)], where lg is
252 × the mean daily log return.

g has a stationary-bootstrap 95% interval (block 63, 5000 draws, seed 0). "Decay
avoidance" is claimed only if that interval excludes zero on the positive side.

**Diagnostics, stated in advance** (from recorded series): plain active Sharpe against
held SPY and against held SSO; excess Sharpe, CAGR and max drawdown of every point; the
tranched-schedule control against the daily rule.

**What it would change.**
- If the primary point corroborates, a leveraged-trend sleeve becomes a candidate for
  registration. The gate must first learn to score vol-matched series; it refuses this
  domain until then.
- Otherwise D6 gains "leverage does not rescue timing".
- The minimum detectable vol-matched Sharpe over about 20 years is about 0.45 (t = 2).

## Known weaknesses, stated in advance

- **2008 is one event.** A block bootstrap treats it as repeatable, so criteria 3 and 4
  exist to stop one crash from carrying the verdict.
- **Half the window is in the paper's own sample** (to about 2015). Criterion 3 covers the
  part after publication.
- **Only the S&P 500.** QQQ (QLD) is excluded as hindsight: it was the best large index
  of the period. IWM (UWM) would show the largest predicted decay effect but was left
  out to keep one primary.
- **No 3x.** UPRO and TQQQ start in 2009-10 and replay the same 2x history at about 1.5
  times the size. They are not independent evidence and would give the hypothesis a
  second chance.
- **Whipsaw.** Daily execution trades every SMA crossing at tier1 cost. The 2x cost
  stress belongs to the gate.

## Board record (2026-10-08)

| Amendment | Source |
|---|---|
| Benchmark is 1x held SPY, not the held levered fund (that comparison is a straw man that wins on 2008 alone) | all three |
| Primary statistic vol-matched (raw active returns reward beta) | statistics, research value |
| Daily execution, the published rule; the 21-tranche schedule is kept as a control | market mechanics, research value |
| The decay-increment mechanism test against the 1x filter | all three |
| Era after publication, check without 2008, single-episode label | statistics, research value, market mechanics |
| Prior search 7 | statistics |
| 3x dropped; QLD dropped as hindsight | all three (statistics and market mechanics: not independent) |
| Separate checks of the night and day legs | market mechanics |

## Result: UNINFORMATIVE, null in substance; the decay mechanism is real (2026-10-08)

Data: snapshot DS-9aeb5e6d (SPY and SSO). The leg check passed across SSO's four 2:1
splits. Window 2006-07-21..2026-10-02, 20.2 years. Ledger: benchmark
TR-20261008T152822Z-80310298, search TR-20261008T152830Z-b81f40c2.

| Point | Excess Sharpe | CAGR | Max DD | Plain active vs SPY | **Vol-matched vs SPY** | Vol-matched eras |
|---|---|---|---|---|---|---|
| held SPY (benchmark) | 0.57 | 11.44% | -55.2% | | | |
| **timed SSO, daily (primary)** | 0.59 | 13.60% | -43.1% | +0.14 | **+0.02** | +0.26 / -0.33 / +0.06 |
| timed SSO, tranched | 0.63 | 15.08% | -47.2% | +0.25 | +0.08 | +0.41 / -0.11 / -0.06 |
| timed SPY, daily (1x) | 0.63 | 8.80% | -24.2% | -0.23 | +0.07 | +0.29 / -0.28 / +0.12 |
| held SSO | 0.54 | 15.93% | **-84.7%** | +0.50 | -0.37 | -0.38 / -0.46 / -0.67 |

- **Statistics.** Familywise SPA p 0.40-0.42 at every block (best point, the tranched
  control: t +0.41). Active DSR 0.04. No look-ahead violations at 12 cuts.
- **Verdict: uninformative.** The primary point is above 0 (+0.02) but t ≈ 0.09, and the
  result without 2008 has the opposite sign (2010..end: -0.06). In substance it is a null.
  Timing a 2x fund on the 200-day rule matches SPY's Sharpe; it does not beat it.
- **Mechanism: corroborated.** The decay increment is
  g = **+2.76%/yr, 95% CI [+1.25%, +4.77%]**. At 2x, the filter saves more compounding
  drag than L times what it saves at 1x. Decay avoidance is real.
- **Why it doesn't pay.** The filter's whipsaw and missed rebounds cost about as much as it
  saves. Against held SSO, the timed fund's plain active Sharpe is -0.22, and its CAGR is
  13.6% against 15.9%. What it buys is the drawdown: -43% against -85%.
- **Diagnostics.**
  - Held SSO compounds faster than SPY (15.9% against 11.4%), but on a worse Sharpe
    (vol-matched -0.37), with an 85% drawdown.
  - The tranched schedule is slightly better than the daily rule (+0.08 against +0.02).
    This is the reverse of the board's concern; neither is significant.

**What it changes.** D6 gains "leverage does not rescue timing". A trend filter makes a 2x
fund survivable (it halves the drawdown) but not better than owning SPY, risk-adjusted.
Nothing is registered.
