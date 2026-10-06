# BDC pre-period test: the discount rule on 2012-2022 BDC data nobody has examined

**Protocol frozen and committed before any BDC price or return in the window was loaded
(2026-10-06).**

F404714 ran the H404701 discount rule on listed business development companies, a
universe disjoint from the CEF panel. It covered 2022-11-07..2026-10-02, because BDCs only
began tagging NAV per share in XBRL in 2022. The result had the same sign (+0.5 active
Sharpe), but 3.9 years is underpowered.

BDCs did report NAV per share before 2022, in the statement of assets and liabilities of
every 10-Q and 10-K. `src/research/bdc_text_nav.py` reads it from the original filings.
No one has examined BDC prices, discounts or returns before 2022-11-07 in this repo: not
the search, the refuters or any board. The only pre-2022 values looked at so far are
ARCC's extracted NAVs, used to prototype the extractor. They are NAVs, not prices or
returns.

## Precondition: the extractor must reproduce the tagged era

Where a filing's period end also has tagged us-gaap `NetAssetValuePerShare` (2022 onward),
compare the extracted value with the first-filed tagged value.

- **Pass:** at least 98% of compared periods agree within $0.01, over at least 200 compared
  periods across at least 20 BDCs.
- **Fail:** the test is not run. The data is not trusted, and the reason is recorded.
- Pre-2022 coverage (filings parsed / filings attempted) is reported either way.

## Protocol

| Item | Frozen choice |
|---|---|
| Rule | `bdc_discount` exactly as frozen in `src/research/bdc_classes.py`. Primary: fraction **0.2** (H404701's cheapest-20% rule). Fraction 1/3 is reported but does not decide the verdict. No parameter is re-chosen. |
| Benchmark | `bdc_equal_weight`: every eligible BDC, equal weight, same cadence and costs |
| Universe | the 62 tickers in BDC NAV panel BDCNAV-adc3942f's manifest: listed today, no SIC code, not in the CEFConnect universe. Survivorship: listed today only. |
| NAV data | a new BDCNAV panel from the original 10-Q/10-K filings filed 2011-01-01 onward (`bdc_text_nav`). An observation is known the day after its filing date. The first original filing per period end is kept; amendments are excluded. |
| Price data | a new price snapshot: SPY plus every universe ticker, 2011-01-01..2022-11-04 |
| Window | from the rule's own scoring start (the first session with 20 eligible BDCs) through 2022-11-04, the session before F404714's window. Disjoint from it. |
| Costs, execution | unchanged: the CEF cost tier (30/15 bps one-way), decided at a close and traded at the next close, every 21 sessions in 21 tranches |
| Counting | counted trials in the `bdc_discount` family: candidate 0.2, the 1/3 point, and the benchmark |

## Success criterion, stated in advance

- **Corroborates:** active Sharpe > 0 and a t-statistic (active Sharpe × √years) above 1.0.
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** anything in between, or a window shorter than 3 years.

This is the criterion of the H404702 pre-period test (`H404702_PREPERIOD_TEST.md`), kept
identical so the two can be compared.

## Known weaknesses, stated in advance

- **Survivorship.** Only BDCs listed in 2026 are in the universe. BDCs that were delisted,
  merged or liquidated in 2012-2022 are missing. Plausibly they were disproportionately
  deep-discount names that kept falling, which would bias the rule upward.
- **Extraction error** in documents unlike the validated ones. The precondition bounds it
  on the tagged era only.
- **Thin early universe.** The 20-eligible threshold may not be met until well after 2012.
