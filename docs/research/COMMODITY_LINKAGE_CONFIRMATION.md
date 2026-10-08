# Commodity linkage: confirmation protocol

**Frozen and committed before any price dated 2016 or later was fetched for this program
(2026-10-08).** The rules come from the discovery atlas
(`COMMODITY_LINKAGE_DISCOVERY.md`; `docs/research/data/commodity_atlas_discovery.json`,
1401 statistics on 2006-2015, crypto 2018-2021). A board of three chose them: statistics,
market mechanisms, and an adversary. Two rules survived; every parameter is fixed below.

## What the atlas found (discovery only; descriptive, not evidence)

**Exposure.**
- Gold miners move about 1.5× gold (weekly correlation 0.79; partial beta t +25).
- Silver miners move about 0.9× silver, copper miners about 1.2× copper, and BTC miners
  about 1.0-1.2× BTC.
- Oil producers and services move about 0.3-0.6× crude after removing the market.
- **Tankers and refiners have no crude link** (partial t -1.0 to +1.1). Tankers trade on
  freight rates, not on oil.

**Two coherent predictive patterns.**
1. **Miners overshoot their metal, then partly revert.**
   - The miner/metal ratio's 60-session z predicts the next 20 sessions' relative return
     with a negative sign for 12 of 13 precious-metal members (GDX t -2.00, KGC -2.91, FNV
     -3.24, SIL -2.45).
   - Gold's past return predicts weaker miners over the next 4 weeks for 7 of 7 members.
2. **Oil equities follow crude's trend, not their own.**
   - Crude above its 100-session SMA predicts better 4-week returns for all 11 oil
     equities (XOP t +1.9, OIH +1.9, DVN +2.7, COP +2.4).
   - The equities' own SMAs show nothing (average t about -0.2).

**News days.**
- **EIA petroleum-report days: no effect** (every |t| < 1).
- **FOMC days:** commodity equities rose 56-107 bp (t about 2.5). That is the market-wide
  FOMC drift of the QE era counted once per group, and F404705 already showed it decays.
  Not tested.

**Rejected as artifacts or untestable.**
- BTC → crypto equities next week: gone after removing SPY. BLOK 0.18 → 0.05 (p 0.46).
  BTC's 00:00 UTC close also falls after the 16:00 equity close.
- Crude crash → tankers: one single-stock residual (TNK). Its confirmation window is
  dominated by events we already know (2020 floating storage, 2022 sanctions).
- Copper: TECK and SCCO have opposite signs.
- Ratio pairs against CL=F or NG=F: the only tradeable legs (USO, UNG) carry roll drag.
- MPC's own-SMA cell: about 3.6 years of data and a couple of episodes.

## Adversary's warnings, built in

- **Inflated t-stats.** Overlapping 20-day windows with persistent regressors inflate the
  atlas t-stats by about 1.5-2×, so its top cells are within the max-|t| null.
- **Miner reversion artifacts.** The ratio pattern could come from:
  - the mismatch between the 13:30 gold settle and the 16:00 miner close (fixed below:
    GLD replaces GC=F);
  - quintile breaks cut on the full sample (fixed: a linear weight replaces them);
  - Stambaugh bias toward false reversion.
- **Oil-trend fragility.** The oil pattern rests on two crashes (2008, 2014), and trend
  filters often win only by holding less (F404709). Its verdict is therefore vol-matched.

## Rules

| | `miner_metal_ratio` | `oil_trend_equities` |
|---|---|---|
| Rule | `ratio_tilt`: z = (log(TR GDX / TR GLD) − 60-session mean) / 60-session std, data through the decision session. GDX weight = clip(0.5 − 0.25 z, 0, 1); GLD the rest. Every 21 sessions in 21 tranches, at the next open. | `commodity_trend`: 100% XLE while CL=F's latest close on or before the session is above its 100-observation SMA, else T-bills. Decided at each close, executed at the next open, an order only on a change of state. |
| Benchmark | `pair_static`: 50% GDX / 50% GLD, same schedule | `fund_static`: 100% XLE, every 21 sessions in 21 tranches |
| Verdict series | **plain active**, sign +1. The tilt averages 50% miners, so active is exactly the predicted relative return. | **vol-matched**, sign +1, so holding less exposure cannot win it |
| Data | snapshot: SPY (calendar), GDX, GLD, XLE, 2015-01-01..2026-10-02 (2015 is warm-up only) | the same snapshot, plus a futures panel `FUT-<sha>`: CL=F raw Yahoo closes (vendor front month, unadjusted rolls), 2014-06-01..2026-10-02 |
| Window | from 2016-01-04 to the snapshot's end, about 10.75 years | the same |
| Costs | tier1 | tier1 |
| Prior search | 1401 (the whole atlas) | 1401 |

**CL=F disclosures.**
- Its 2020-04-20 print of −$37.63 stays in, and it drags the SMA down by about $0.6 for
  100 observations.
- Roll gaps stay in, as in the atlas.
- A futures close (settled 14:30 ET) dated on or before a session is known before that
  session's 16:00 close.

Counting: `tools/domain_search.py miner_metal_ratio --snapshot <sha>` and
`tools/domain_search.py oil_trend_equities --snapshot <sha> --panel <FUT sha>`.

## Verdict, stated in advance

For each rule, on its verdict series against its benchmark:
- **Corroborates:** Sharpe > 0, t > 1.0, and the worst-block familywise SPA p, Holm-adjusted
  across the two rules (the smaller p must be < 0.025, the larger < 0.05), passes.
- **Contradicts:** Sharpe ≤ 0.
- **Uninformative:** anything else.

**Diagnostics, stated in advance** (recorded series only, no new trial):
- plain active and vol-matched Sharpe, by era;
- the active DSR at N = 1401;
- max drawdown and turnover.

**Power, stated in advance.** With winner's-curse shrinkage, the true effects are probably
a Sharpe of 0.25-0.35, against a standard error of about 0.30 over 10.75 years. There is
about a 35-45% chance at least one rule passes. **A null is the most likely outcome.**

**What it would change.** A corroborated rule is a candidate for registration with a
forward window. The admission gate must first learn to score vol-matched series for the
oil rule; it refuses that domain until then. A null adds to D6: commodity linkages are
real as exposures but not tradeable as timing.
