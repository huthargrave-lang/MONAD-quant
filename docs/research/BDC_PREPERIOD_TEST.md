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

## Amendment 1 (2026-10-06): validation pass 1 failed; board ruling before pass 2

Committed before any pass-2 output was read, and still before any BDC price or return in
the window was loaded.

**Pass 1.** The first implementation of the precondition compared every period end that
has any tagged value. That includes pre-2022 period ends whose only tags are comparatives
first filed in 2022 or later. Three readings of the comparison gave:

| Reading | Compared | Agree | Share | Filers |
|---|---|---|---|---|
| A: every period end with a first-filed tag (as implemented) | 1165 | 1109 | **95.2%, FAIL** | 49 |
| B: period ends from 2022-01-01, first-filed tag | 821 | 809 | 98.5% | 48 |
| C: the tag in the same filing (same accession) | 720 | 711 | 98.75% | 48 |

Two classes of disagreement:

- **Comparator artifacts** (A only). Comparatives restated for reverse splits: BCIC
  (tagged 10× extracted), CION (2×), OCSL (3×). Also BBDC financial-highlights comparatives
  tagged with shifted period ends.
- **Genuine extractor errors**, in some 10-Ks:
  - OFS: the "NAV per share at beginning of year" row was read.
  - OCSL: the $10.00 hypothetical sales-below-NAV dilution table was read.
  - RAND: a "(Decrease) increase in net assets per share" row was read.

**Extractor fixes** (generic rules, no per-ticker overrides):
1. The label must start the cell.
2. Rows with "beginning of" are excluded.
3. The NAV row inside the table that is a statement of assets and liabilities (it has a
   "total liabilities" or "total net assets" row) is preferred, falling back to the first
   NAV row.

The extractor now also records the balance sheet's prior-period column.

**Board ruling.** Three independent members voted unanimously for reading **B**: it keeps
both stated qualifiers, "(2022 onward)" and "first-filed". A measures restatement, not
extraction. C would replace "first-filed". The fix is acceptable because only NAVs had
been examined. **Pass-2 validation is in-sample** (the fixes were found on the same
tagged-era set), so it bounds pre-2022 error more weakly than a held-out check would.

**Gates for pass 2.** All must pass. There is one fix round only: if any gate fails, the
test is not run, nothing further is edited, and the failure is recorded.

1. **Tagged era (B).** At least 98% of compared periods agree within $0.01, over at least
   200 periods and 20 BDCs. A and C are reported but do not decide.
2. **Pre-2022 comparative cross-check** (`bdc_text_nav.comparative_cross_check`). Each
   fiscal year-end NAV a 10-K reports for a period before 2022 is compared with the
   prior-period column of the next original filing. At least 98% must agree within $0.01.
   Pairs at a split ratio are excluded and listed.
3. **Hand audit.** Draw a seeded random sample of 50 pre-2022 filings (seed 20261006),
   stratified by filer, with 2011-2015 filings drawn at twice their share. A reviewer who
   did not write the extractor reads each source document. At most 1 of 50 may disagree
   with the extracted value.
4. **Review lists**, adjudicated in the audit report and reported in full:
   - every pre-2022 value that changed between pass 1 and pass 2;
   - every quarter-over-quarter NAV move above 25%.

The full pass-1 disagreement lists are in the commit that records pass 2's results.

## Amendment 2 (2026-10-06): the first pass-2 evaluation ran on outage-truncated data

A DNS outage during the pass-2 crawl left 16 tickers with no observations: PFLT, PFX,
PNNT, PSBD, PSEC, RAND, RVII, RWAY, SAR, SCM, SLRC, TCPC, TPVG, TRIN, TSLX and WHF. OXSQ also
lost 32 filings to timeouts. The gates were evaluated on that truncated crawl, about 45 of
the 62 universe tickers, before the outage was noticed:

- **Gate 1 (B):** 543/549, 98.9%, 31 filers.
- **Gate 2:** 275/287, 95.8%, a fail. 11 of the 12 disagreements are OCSL, whose 10-K
  extraction is still wrong; the twelfth is BCIC 2014.

**Board ruling: 2 of 3 for completing the crawl** (the third vote had not arrived when this
was committed). The gates are defined over the protocol's universe, so a truncated run is
invalid input, not a result. A pass on 45 tickers would equally have required the
re-crawl.

**Conditions:**
- The extractor code is unchanged (e30f847). The one fix round is spent.
- The 17 tickers are re-crawled until there are zero network failures. Each ticker's filing
  count must match pass 1's attempts, and a remaining fetch failure is retried, never dropped.
- All four gates are then re-evaluated on the complete pass-2 data, and that evaluation is
  final. OCSL is not excluded, and pass-1 values are not reused.
- If gate 2 still fails, the test does not run.
- If the gates pass, OCSL's known-bad 10-K values enter the test. The result excluding OCSL
  is then reported as a disclosed sensitivity, not as the deciding figure.

**Disclosed:**
- The truncated evaluation and its gate-2 failure were seen before the re-run.
- Pass-1 NAVs for these tickers had been seen, under the old extractor.
