# Mortgage REIT discount test, v2: company-stated GAAP book value

**Protocol frozen and committed before any v2 extraction run and before any mREIT price was
loaded (2026-10-06).** v1 (`MREIT_DISCOUNT_TEST.md`) closed NOT RUN: XBRL misses
series-tagged preferred stock. Its board allowed this successor on the conditions below.
There are no corrections: if a gate fails, v2 closes NOT RUN.

The research question, universe, rule, benchmark, window, costs, counting and success
criterion are exactly v1's. Only the measurement of book value per common share changes.

## Measurement: the company's own stated GAAP book value per common share

- **Sources.** For each panel mREIT, its original 10-Q and 10-K filings (primary
  document) and its 8-K filings that carry an earnings release (exhibit 99), from 2011 on.
- **Label rule.** Accept a table row or sentence whose label contains "book value per
  common share" or "book value per share" (case-insensitive). Reject the label if it also
  contains "tangible", "adjusted", "economic", "excluding", "diluted", "non-GAAP",
  "pro forma", or "estimated" (an intra-quarter estimate is not a period-end figure).
- **Value rule.**
  - In a table row: the first dollar amount after the label (the current-period column).
  - In prose: the first dollar amount within 120 characters after the label.
  - Values outside (0, 500] are rejected.
- **Period rule.**
  - A 10-Q or 10-K states its own report date.
  - An 8-K states the latest calendar quarter end before its filing date, and only if it
    was filed within 75 days of that quarter end.
- **Known date.** For each (mREIT, period end), the earliest filing that states an
  accepted value is used. The value is known the day after that filing's date. A later,
  different value for the same period (a 10-Q after an 8-K, a restatement) never replaces
  it.
- **Sanity bound.** If XBRL companyfacts reports StockholdersEquity and
  CommonStockSharesOutstanding for that period end, the stated value must not exceed
  1.02 × equity / shares. Preferred can only lower book value per common share. A failing
  value is rejected, never repaired.
- **Missing.** A period with no accepted value leaves the mREIT ineligible while its last
  known value is more than 200 days old (v1's rule). Missing values are never imputed.
  The missing rate is reported.

## Gates: all must pass, with no corrections

1. **Independent source.** For mREITs that never carried preferred stock (no preferred
   concept and no preferred dividends anywhere in their XBRL companyfacts), the stated
   value is compared with the XBRL derivation equity / shares for the same period end. At
   least 98% of compared periods must agree within 2%, over at least 100 periods and 4
   mREITs. If fewer qualify, the gate is uninformative, and gate 2 alone decides.
2. **Blind hand audit.** 30 (mREIT, period end) pairs are drawn with seed 20261007 from
   every panel pair 2011-2026, including pairs the extractor missed, at most 2 per mREIT.
   A reviewer who did not write the extractor finds the company's stated GAAP book value
   per common share for each pair, without seeing the extractor's value or source.
   - **Pass:** at most 2 of the pairs where both exist differ by more than 2%.
   - Pairs the extractor missed but the reviewer found are counted and reported as
     coverage misses. They do not fail the gate.
   - Pairs where the company states no GAAP figure are replaced by the next seeded draw.
3. **Coverage floor.** At least 70% of (mREIT, quarter) pairs 2013-2026 with a 10-Q or
   10-K must have an accepted value. Below that, the panel is too sparse to test.

## Then

Freeze the panel (`MREITBV-` prefix, source "company-stated GAAP book value per common
share"). Build the price snapshot (SPY plus panel mREITs, 2011-01-01 to the latest
close). Run `tools/domain_search.py mreit_discount`. Judge by v1's criterion: corroborates
if active Sharpe > 0 and t > 1.0; contradicts if active Sharpe ≤ 0; otherwise
uninformative. Primary fraction 0.2.
