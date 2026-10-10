# Commodity linkage: discovery protocol

**Frozen and committed before any price for this program was fetched (2026-10-08).**

## Why

The question: do commodities move the stocks that produce or depend on them, in a way a
rule can trade? Examples are oil and tankers or producers, gold and miners, and bitcoin
and crypto equities. Which moving averages and which news events move these groups?

F106 rejected a one-day lead-lag graph among liquid ETFs. It did not test weekly or
monthly diffusion, individual stocks, event-conditioned effects, or commodity-to-producer
links. This program does.

## Two phases, one firewall

1. **Discovery** (this document). A descriptive atlas is computed **only** on the
   discovery window. No trial is counted, because nothing is being selected yet; the
   atlas's own size is recorded and charged later as prior search.
2. **Confirmation** (a later protocol, frozen before its data is fetched). At most a
   handful of rules, chosen by a board from the atlas, are run as counted trials on the
   untouched window.

| Block | Discovery window | Confirmation window (not fetched until its protocol is frozen) |
|---|---|---|
| Commodities and stocks | 2006-01-01..2015-12-31 | 2016-01-01..latest |
| Bitcoin and crypto equities | 2018-01-01..2021-12-31 | 2022-01-01..latest |

**Mechanical firewall.** The discovery tool (`tools/commodity_atlas.py`):
- fetches with an `end` bound;
- asserts that no row falls after the window's end;
- writes the window and the bound into its output.

## Universe (fixed now)

**Anchors (futures or spot, Yahoo):** WTI CL=F, Brent BZ=F, natural gas NG=F, gold GC=F,
silver SI=F, copper HG=F, BTC-USD.

| Group | ETFs | Stocks |
|---|---|---|
| Oil producers | XLE, XOP | XOM, CVX, COP, APA, DVN, OXY |
| Oil services | OIH | SLB, HAL |
| Tankers | | FRO, DHT, TNK, NAT, TK, STNG |
| Refiners (crude is an input) | | VLO, MPC |
| Natural gas | FCG | EQT, RRC |
| Gold miners | GDX, GDXJ | NEM, GOLD, AEM, KGC, AU, GFI |
| Royalty | | FNV, RGLD, WPM |
| Silver | SIL | PAAS, HL, CDE |
| Copper | COPX | FCX, SCCO, TECK |
| Crypto equities | BLOK | MSTR, MARA, RIOT |
| Controls | SPY (market), IEF (rates), UUP (dollar) | |

Members missing from Yahoo, or listed after a window starts, are reported, not replaced.

## Atlas metrics (all fixed now, all reported)

Weekly returns run Friday close to Friday close. Weekly sampling avoids the mismatched
closes of futures (14:30 ET), stocks (16:00) and bitcoin (24/7).

1. **Exposure.**
   - Weekly correlation and beta of each member to its anchor.
   - The same after removing SPY, IEF and UUP: the partial beta, which is the anchor's
     own link.
2. **Lead-lag.**
   - Correlation of the anchor's week-t return with the member's week t+1 and t+4
     returns.
   - Correlation of the anchor's trailing 4-week and 12-week return with the member's
     next 4 weeks.
   - Each is shown raw and SPY-residual, with a circular-shift placebo (500 shifts) for
     its p-value.
3. **Moving-average state.**
   - The member's forward 4-week return, annualised, conditional on the anchor being
     above or below its 50, 100 and 200-session SMA.
   - The same conditioning on the member's own SMA.
   - Reports the spread (above minus below) and its Newey-West t.
4. **Ratio reversion.**
   - The log ratio of member to anchor (for example GDX/GC).
   - Its z-score against a 60-session mean.
   - The member's forward 4-week return relative to the anchor, by z quintile, and the
     ratio's estimated half-life.
5. **Scheduled news.** Daily, the mean return and mean absolute return of each group ETF
   (or the member basket) on:
   - FOMC announcement days (`src/research/fomc_calendar.py`), and the session before;
   - EIA weekly petroleum report days: Wednesdays, or Thursdays in a week with a Monday
     holiday (approximate);
   - all other days, for comparison.

**Multiple testing.** The atlas has about 30 members × 5 metric families × several
variants, so most "significant" cells are noise. It ranks; it does not prove. Its cell
count is written to its output and becomes the confirmation protocol's declared prior
search.

## What the confirmation protocol must contain

- At most 4 rules, each with every parameter fixed from the discovery atlas.
- A benchmark per rule: the static hold of the same group, or the group and its anchor.
- The verdict series (plain active or vol-matched) and its sign, stated before the data
  is fetched.
- Costs: tier1 for ETFs; small-cap tier for single stocks below a stated liquidity.
