# Physical-metal trust discount tilt: protocol

**Frozen and committed before any price of PHYS, PSLV, GLD or SLV was loaded for this
test (2026-10-08).**
- A research-value board member proposed it.
- Two more reviewers amended it: statistics and mechanics, and an adversary.
- Their amendments are built in below.
- No discount statistic for these trusts was computed beforehand. The reviewers checked
  NAV-panel coverage only.

## The question

The project's one surviving edge is discount-to-NAV selection in closed-end funds
(H404702; live CEFS and MDCEX, F404732). Every CEF test so far compares funds holding
different assets, so category and asset beta could explain part of it.

Sprott's physical trusts hold the same metal as a physical ETF:
- PHYS (gold) against GLD;
- PSLV (silver) against SLV.

So the trust's return against the ETF is only its change in discount plus a small fee
gap. **Does a discount-reversion rule earn money when nothing but the discount moves?**

This is a new time-series rule on new funds. It is not a test of H404702: these four
funds formed a 4-fund category, below `MIN_CATEGORY` = 5, so H404702's within-category
rule never held them. They did sit in its search's whole-universe points and its
equal-weight benchmark.

## Design (domain `metal_trust_discount`, family `metal_trust_discount.v1`)

| Item | Frozen choice |
|---|---|
| Pairs | PHYS/GLD and PSLV/SLV. CEF (fixed ounces of gold and silver, about 2/3 gold by value) and SPPP (platinum and palladium, whose ratio moved 4x over 2019-21) are **excluded**: a rebalanced ETF benchmark would add a metal-spread bet. |
| NAV | the existing weekly panel CEFNAV-fd7099e2 (PHYS from 2010-02, PSLV from 2010-10). Discount = price / NAV − 1. |
| z | H404702's z52, identically: over the fund's own weekly observations, including the latest, 52 required, sample std |
| State machine | per pair, stepped once per NAV observation, starting at 0.5 (trust weight within the pair). From 0.5: z ≤ −1 → 1, z ≥ +1 → 0. From 1: z ≥ +1 → 0, else z ≥ 0 → 0.5. From 0: z ≤ −1 → 1, else z ≤ 0 → 0.5. |
| Reading | a session reads the state after the latest NAV dated **strictly before** it; a NAV more than 14 days old reads 0.5. This is stricter than H404702's "on or before"; the panel has gaps of 14-28 days in 2021-22. |
| Candidate (`trust_tilt`) | each pair has half the capital. Within a pair, the trust gets state × that half and the ETF the rest. |
| Benchmark (`pairs_static`) | 25% each of PHYS, GLD, PSLV, SLV |
| Execution | the next **close** (as in H404702; Yahoo's CEF opens are unreliable), every 21 sessions in 21 tranches |
| Costs | trusts at the `cef` tier (15 bps after 2010), ETFs at tier1 (2 bps) |
| Price data | a new snapshot: SPY (calendar), PHYS, GLD, PSLV, SLV, 2009-01-01..2026-10-02 |
| Window | from the first session after both trusts have 52 discount observations (about 2011-11) to the snapshot's end |
| Eras | ..2016 / 2017..2021 / 2022.. |
| Counting | `tools/domain_search.py metal_trust_discount --snapshot <sha> --panel fd7099e2…`, then `tools/metal_trust_report.py`, which also records a counted 2x-cost run |
| Prior search | 22: H404702's CEF search (16) + 1, plus the 5 drafts the boards weighed for this slot |

## Verdict, stated in advance

- **Corroborates.** All of the following hold:
  - active Sharpe > 0, t > 1.0, and worst-block SPA p < 0.05;
  - the 2x-cost run's active Sharpe is > 0;
  - **the long leg (trust held cheap) has a positive total contribution**;
  - there are at least 20 episodes across both pairs.

  The long-leg condition matters: Sprott's at-the-market issuance sells premiums away
  and redemption puts a soft floor under discounts. A result carried by the short leg
  alone would be an issuance effect, not discount mean reversion.
- **Contradicts.** Active Sharpe ≤ 0.
- **Inconclusive.** Anything else, including fewer than 20 episodes.

**Diagnostics, stated in advance:**
- per pair: episodes, share of sessions not neutral, and the contribution of each leg;
- leave-one-pair-out Sharpe;
- era Sharpes;
- the break-even swing per round trip: 17 bp of the pair's capital at the frozen tiers.
  Gross P&L per episode is compared with it.

**Not done, disclosed.** The adversary asked for a split at each trust's first
at-the-market prospectus date. Those dates could not be verified before the freeze, so
the split is omitted rather than set after seeing data.

**What it would change.**
- If it corroborates, discount reversion pays even with no asset or category difference.
  That strengthens H404702's mechanism and gives a near-free rule for any gold or
  silver sleeve: hold the trust when it is cheap.
- If it contradicts, the CEF edge needs category structure or illiquidity, not
  discount reversion alone.

**Power, stated in advance.** Discounts are kept tight (within a few percent) by
redemption and issuance. Each episode is worth a few tenths of a percent against a 17 bp
round trip. A small or null result is the most likely outcome.

## Result: CORROBORATES (2026-10-08)

Data:
- snapshot DS-6edd69e3 (SPY, PHYS, GLD, PSLV, SLV); the distribution cross-check found 0
  of 88 asset-years off;
- NAV panel CEFNAV-fd7099e2.

Window 2011-10-24..2026-10-02, 15.0 years. No look-ahead violations at 12 cuts.

Ledger runs:
- benchmark TR-20261008T185928Z-5c567742;
- search TR-20261008T185930Z-9488e29b;
- 2x cost: TR-20261008T185936Z-eb8af984 (benchmark) and TR-20261008T185937Z-6adb2bed
  (candidate).

| | CAGR | Max DD | Cost/yr | Active %/yr | Active Sharpe | Eras | SPA p (blocks 20/63/126) |
|---|---|---|---|---|---|---|---|
| benchmark 25% PHYS/GLD/PSLV/SLV | 4.82% | -55.0% | 0.03% | | | | |
| `trust_tilt` | 5.56% | -54.9% | 0.44% | **+0.74** | **+0.43** (vol-matched +0.41) | +0.59 / +0.26 / +0.42 | 0.022 / 0.014 / 0.010 (t +2.1 to +2.6) |

**Every pre-stated condition holds:**
1. active Sharpe +0.43 > 0, t > 1, worst-block SPA p 0.022 < 0.05;
2. at 2x costs the active Sharpe is still +0.19 (+0.32%/yr);
3. the long leg is positive in both pairs: PHYS +0.20%/yr, PSLV +0.21%/yr, total
   +0.41%/yr. The short leg adds +0.21 and +0.57%/yr; PSLV's larger short leg is
   consistent with premiums being sold away by issuance;
4. 73 episodes (PHYS 41, PSLV 32), not neutral 61% / 68% of the time.

Leave-one-pair-out Sharpe: +0.53 with either pair dropped. Gross contribution is about
1.2%/yr against 0.44%/yr of costs; the break-even swing is 17 bp per round trip.

**Verdict: corroborates.** Discount reversion pays when nothing but the discount moves.
The trust and its ETF hold the same metal, so there is no asset or category beta to
explain it. Both legs contribute, so it is not only an issuance effect.

**What it does and doesn't mean.**
- **The mechanism.** This is the cleanest evidence yet for the mechanism behind H404702.
  Its size is small: +0.74%/yr on a gold/silver sleeve.
- **Capacity.** PHYS and PSLV are multi-billion-dollar trusts, so capacity is far
  larger than in small CEFs.
- **Practical use.** For anyone holding gold or silver, owning PHYS instead of GLD (or
  PSLV instead of SLV) when the trust's 52-week discount z is ≤ -1, and the ETF when
  z ≥ +1, is a near-free improvement.
- **Admission.** It is **not admissible under gate rules v2**: p_gate = 0.022 × (1 + 22)
  ≈ 0.51. The declared prior search of 22 dominates. It is a corroborated mechanism and
  a sleeve choice (like ANGL, F404731), not a registered strategy.
- A forward record would be the next step if it is to be promoted.
