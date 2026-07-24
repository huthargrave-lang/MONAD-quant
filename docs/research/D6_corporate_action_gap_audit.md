# Study #31 — Corporate-Action and Ex-Dividend Gap Audit

**Artifact:** [`tools/overnight_gap_risk_study.py`](../../tools/overnight_gap_risk_study.py)<br>
**Action audit:** [`data/tqqq_corporate_actions_2010_2026.csv`](data/tqqq_corporate_actions_2010_2026.csv)<br>
**Reproduce:** `venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-program.json`<br>
**Data:** Yahoo raw TQQQ prices/actions, 2010-02-12–2026-07-22; sponsor cross-check<br>
**RESEARCH_WEB nodes:** E55 (study) · F65 (finding) · tests [[F50]]/[[F57]]/[[F58]]<br>
**Status:** accounting correction; no risk verdict or policy decision changes.

## Question

Studies #16–30 use raw prices because an actual stop responds to the quoted open. But an investor
holding an ETF before its ex-dividend date also receives cash. Do raw ex-dividend price drops
inflate the measured overnight-gap tail or materially bias mitigation comparisons?

## Construction

Two facts must remain separate:

1. **Stop mechanics:** compare the raw open with the raw stop. A distribution does not move the
   broker's stop level or prevent the quoted price from triggering it.
2. **Economic wealth:** if a position was entered before the ex-date and remained open through
   it, add the cash distribution to the trade return. A short would owe the cash.

The action history contains 21 nonzero TQQQ distributions and eight splits. The fetched source is
hashed as `861f6206…c37ba87`; the small action table is committed. ProShares independently reports
the latest June 24, 2026 TQQQ distribution as $0.171229, consistent with Yahoo's rounded $0.171
([ProShares distribution table](https://www.proshares.com/our-etfs/find-leveraged-and-inverse-etfs?product=Recent+Distributions)).
ProShares also confirms the November 20, 2025 2:1 split
([sponsor announcement](https://www.proshares.com/press-releases/proshares-announces-etf-share-splits5)).

## Long-history event counts

| raw TQQQ loss threshold | raw-price events | distribution-inclusive events | raw classifications removed by cash |
|---:|---:|---:|---:|
| 0.5% | 1,289 | 1,287 | **2** |
| 1% | 935 | 933 | **2** |
| 2% | 484 | 484 | 0 |
| 4% | 158 | 158 | 0 |

Only two dates cross back above the 0.5% boundary after adding cash:

- 2023-03-22: raw −0.657%, distribution-inclusive −0.077%;
- 2024-09-25: raw −0.712%, distribution-inclusive −0.391%.

No ≥2% severe-gap classification changes. Corporate actions therefore do not explain the
leveraged-ETF tail or the volatility-severity findings.

## Strategy-path correction

| policy | trades earning distributions | total-return correction | corrected total | corrected delta vs hold |
|---|---:|---:|---:|---:|
| hold overnight, gap-aware | 2 | +0.0338 pp | −10.1133% | — |
| vol20 ≥15% flatten | 2 | +0.0352 pp | −6.0651% | +4.0482 pp |
| daily flatten | 0 | 0 | −5.7746% | +4.3387 pp |

The baseline's two credited positions earn:

- 2025-06-25: $0.109/share, +28.0 bp of trade return;
- 2025-09-24: $0.049/share, +9.6 bp.

Neither is an overnight gap-through-stop exit. The baseline has **zero** gap stops on
distribution ex-dates.

Daily flatten avoids distributions because it is out of the position before each ex-date. Its
apparent benefit therefore shrinks by the baseline's 0.0338 percentage-point credit, from about
+4.3725 pp to +4.3387 pp. The volatility policy earns the same two distributions and its relative
benefit is effectively unchanged.

## Finding

The raw-price approach was correct for stop triggering but slightly incomplete for wealth.
Crediting earned cash distributions:

- removes only 2 of 1,289 raw ≥0.5% instrument-gap classifications;
- removes no ≥2% severe gaps;
- changes the live-shaped baseline by only +0.0338 pp;
- leaves every path negative and every mitigation verdict unchanged.

Dividend omission is real accounting error, but not an explanation for the observed overnight
tail or the strategy's failure.

## Caveats

- Cash is credited on the ex-date without tax, payment delay, or reinvestment.
- The full action table comes from Yahoo; only current distribution and selected split facts are
  independently checked to sponsor records.
- Split-adjusted historical serialization is vendor-specific; the source hash prevents silent
  revision but does not certify vendor correctness.
- Raw price remains the appropriate trigger basis for a real stop even when total wealth later
  receives a distribution.
