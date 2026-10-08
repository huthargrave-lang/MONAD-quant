# Miner/metal tilt: replication protocol

**Frozen and committed before any 2016+ price of SIL, SLV, GDXJ or IWM was loaded
(2026-10-08).** The board (statistics, mechanics, research value) amended the draft as
recorded below.

## Why

The GDX/GLD ratio tilt (`COMMODITY_LINKAGE_CONFIRMATION.md`, F366200) is the only
commodity lead that held its discovery sign out of sample:
- +2.0%/yr against a 50/50 GDX/GLD mix;
- active Sharpe +0.27, with eras +0.01 / +0.22 / +0.67;
- not significant (worst-block SPA p 0.13).

The mechanism is that miners overshoot their metal, then partly revert. If that is real
it should appear in a different metal. This protocol replicates the **exact frozen rule**,
with no retuning, on pairs whose 2016+ prices have never been loaded here.

**Discovery-era stats**, from the atlas, 2006-2015, against the futures:
- SIL vs SI=F: t -2.45, Q1-Q5 +48.8%/yr, half-life about 90 sessions;
- GDXJ vs GC=F: t -0.49, Q1-Q5 +5.8%/yr, outside the discovery pattern.

The traded legs are SLV and GLD (physical), not the futures.

## Rule (unchanged)

z = (log(TR miner / TR metal) − 60-session mean) / 60-session std. Miner weight is
clip(0.5 − 0.25 z, 0, 1), and the metal ETF gets the rest. Every 21 sessions in 21
tranches, at the next open, tier1. Benchmark: a static 50/50 of the pair, same schedule.
The verdict series is plain active, sign +1.

## Domains (all counted; only the first carries a verdict)

| Domain | Pair | Role |
|---|---|---|
| `silver_miner_ratio` | SIL (2010-04) / SLV | **the verdict**: a different metal |
| `junior_miner_ratio` | GDXJ / GLD | robustness only. It is near-duplicate of GDX and its index widened in June 2017, so eras are split there too. |
| `gold_silver_ratio` | GLD / SLV | contamination check. SIL holds gold-heavy firms (Wheaton, Pan American), so the SIL/SLV tilt could be a gold/silver ratio bet. |
| `placebo_ratio` | IWM / SPY | placebo. If an unlinked pair does as well, the effect is generic pair reversion, not a miner overshoot. |

- **Data:** one snapshot, SPY (calendar), SIL, SLV, GDXJ, GLD, IWM,
  2015-01-01..2026-10-02 (2015 is warm-up only). Distribution cross-check
  (`tools/snapshot_tr_check.py`) before running.
- **Window:** 2016-01-04..2026-10-02.
- **Eras:** ..2019 / 2020..2022 / 2023..
- **Prior search: 2.** After seeing GDX/GLD's result, two choices were made: which rule
  to replicate (1 of 2) and which pair is primary (1 of 2). The rule's descent from the
  1401-cell atlas is recorded, not charged again.
  - Dissent: the mechanics member wanted 1401, which gives zero power by construction;
    the research-value member wanted 0.

## Verdict, stated in advance (`silver_miner_ratio` only)

- **Corroborates:** active Sharpe > 0, t > 1.0, worst-block SPA p < 0.05.
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** anything else.

**Registration trigger.** `tools/miner_tilt_replication.py` checks every condition from
recorded series; all must hold:
1. corroborates, and p × (1 + 2) ≤ 0.05;
2. regressing the SIL/SLV active series on GDX/GLD's leaves a positive intercept;
3. the Sharpe stays > 0 when any one era is dropped.

If it fires, one hypothesis is registered: the forward series
0.5 × (GDX/GLD tilt active) + 0.5 × (SIL/SLV tilt active), with a 365-day forward window.

**Diagnostics** (from recorded series, no trigger role):
- Regressions of SIL/SLV active on GDX/GLD active and on the GLD/SLV tilt: beta,
  Newey-West t, R², intercept per year and its Newey-West t. A high beta on GLD/SLV
  means "mostly a gold/silver ratio bet".
- Pools with stationary-bootstrap 95% CIs (block 63, the same resampled sessions):
  - `pool_unseen`: 0.5 SIL/SLV + 0.5 GDXJ/GLD;
  - `pool_all`: 0.5 SIL/SLV + 0.25 GDX/GLD + 0.25 GDXJ/GLD, labelled "includes seen data".
- Correlation of every series with SIL/SLV's.
- The placebo's and the GLD/SLV tilt's Sharpe and t.

**Power, stated in advance.** At a true active Sharpe of 0.2-0.3 and a standard error of
about 0.30, clearing p × 3 ≤ 0.05 has about a 10-20% chance. **A null is expected.** Its
role is to close or promote the lead.

## Result: UNINFORMATIVE, with the same sign again; the trigger does not fire (2026-10-08)

Data: snapshot DS-33bafcfd. The distribution cross-check found 0 of 72 asset-years off.
Window 2016-01-04..2026-10-02. No look-ahead violations at 12 cuts in any domain.

| Domain | Tilt CAGR (50/50) | Active %/yr | Active Sharpe | Eras | Worst-block SPA p |
|---|---|---|---|---|---|
| **`silver_miner_ratio`** SIL/SLV (verdict) | 19.05% (16.15%) | **+2.46** | **+0.34** | +0.02 / +0.90 / +0.24 | 0.096 |
| `junior_miner_ratio` GDXJ/GLD | 20.24% (17.34%) | +2.95 | +0.32 | -0.14 / +0.51 / +0.71 | 0.098 (0.056 at block 126) |
| `miner_metal_ratio` GDX/GLD (seen, F366200) | 19.06% (17.05%) | +2.05 | +0.27 | +0.01 / +0.22 / +0.67 | 0.131 |
| `gold_silver_ratio` GLD/SLV (contamination) | 12.85% (14.13%) | -1.41 | -0.20 | +0.30 / -0.75 / -0.03 | 1.00 |
| `placebo_ratio` IWM/SPY (placebo) | 13.24% (13.00%) | +0.34 | +0.10 | +0.10 / -0.55 / +0.83 | 0.38 |

Ledger runs (benchmark, search):
- silver: TR-20261008T185506Z-22d9e398, TR-20261008T185507Z-f8c2a60f;
- junior: TR-20261008T185514Z-ee85e223, TR-20261008T185515Z-cea2ea5f;
- gold/silver: TR-20261008T185522Z-602bf09b, TR-20261008T185523Z-292942c5;
- placebo: TR-20261008T185530Z-9694386a, TR-20261008T185531Z-ee54c2f4.

**Diagnostics** (`docs/research/data/miner_tilt_replication_diagnostics.json`):
- **SIL/SLV active regressed on GDX/GLD active:** beta 0.49 (NW t 11.2), R² 0.26,
  intercept +1.5%/yr (NW t 0.87). Silver adds a positive, partly independent component.
- **SIL/SLV active regressed on the GLD/SLV tilt:** beta 0.24 (t 1.65), R² 0.05. It is not
  a gold/silver ratio bet; that tilt itself loses.
- **Dropping any one era** keeps the Sharpe positive: +0.51 / +0.13 / +0.39.
- **Pools:**
  - `pool_unseen` (SIL/SLV and GDXJ/GLD): Sharpe +0.37, 95% CI [-0.16, +0.89];
  - `pool_all`: +0.37, CI [-0.16, +0.88].
- **Correlations with SIL/SLV:** GDX/GLD 0.51, GDXJ/GLD 0.52, GLD/SLV 0.23, placebo 0.03.
- **Trigger:** every condition holds except significance (SPA 0.096 > 0.05, and × 3 >
  0.05). **Not registered.**

**Reading.**
- **The miner-overshoot pattern now holds in three miner pairs out of sample** (+0.27,
  +0.34, +0.32; +2.0 to +3.0%/yr), and is absent where it should be absent:
  - the unlinked placebo is +0.10;
  - the pure metal pair is -0.20.
- That is the pattern a real mechanism produces, and generic pair reversion does not.
- Each test is underpowered: about 10.75 years at an active Sharpe of about 0.3 gives
  t ≈ 1.1-1.3. The pooled CI still includes 0.
- **Status: the strongest lead outside CEFs, not an edge.** What would settle it is time:
  a forward record, or a longer pre-2016 history of these pairs. The discovery window
  cannot be reused, because it chose the rule.
