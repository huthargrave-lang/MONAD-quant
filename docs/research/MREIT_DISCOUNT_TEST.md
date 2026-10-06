# Mortgage REIT discount test: the CEF mechanism on a second disjoint universe

**Protocol frozen and committed before any mREIT price was loaded (2026-10-06).**

The CEF discount rule (H404701: hold the cheapest fraction by discount to NAV) survives in
closed-end funds. Its BDC replication had the right sign (F404714) but was underpowered,
and the BDC pre-period test could not run (F404722). Mortgage REITs are a second universe
disjoint from the CEF panel:

- their book is mostly marked-to-market securities;
- they trade around book value per common share;
- they are operating companies, so they have filed point-in-time XBRL since 2011.

No one has examined mREIT prices or returns in this repo.

## Data (built before this protocol, from SEC filings only)

- **Universe** (`src/research/mreit_data.py`). A filer qualifies if, in any quarterly
  frame 2012-2026, its repo borrowing is at least 25% of total assets. It must also have
  SIC 6798 and a common stock listed today.
  - Excluded by adjudication: Two Harbors (common delisted after its 2026 acquisition;
    TWOD is its senior notes) and InPoint/FS Credit (no listed common).
  - Ladder has no book-value observations and is dropped.
  - Survivorship: listed today only.
- **Book value per common share.** (StockholdersEquity − preferred) / CommonStockShares
  Outstanding, with every input from the same first-reporting 10-Q/10-K. Preferred is the
  liquidation preference if reported, else the carrying value. Each value is known the day
  after filing.
- **Panel:** `MREITBV-eed8ab6d` (20 mREITs).

## Precondition: a hand audit of the book-value derivation

The audit sample is 30 observations drawn with seed 20261006, at most 2 per mREIT, listed
in `docs/research/data/mreit_audit_sample.json`.

- **Method.** A reviewer who did not write the derivation opens each observation's source
  filing (or the earnings release for that period) and finds the company's stated GAAP
  book value per common share.
- **Pass:** at most 2 of 30 differ from the derived value by more than 2%. Observations
  where the company states no GAAP book value per share are replaced by the next seeded
  draw.
- **Fail:** the test is not run, and the failure is recorded. Exactly one correction round
  is allowed: if the failure is a systematic derivation defect, it may be fixed once and
  re-audited on a fresh seeded sample (seed 20261007). There is no second correction.

## Protocol

| Item | Frozen choice |
|---|---|
| Rule | `mreit_discount` (`src/research/mreit_classes.py`). **Primary: fraction 0.2** (H404701's cheapest 20%). Fraction 1/3 is reported but does not decide the verdict. Hold at least 4. |
| Benchmark | `mreit_equal_weight`: every eligible mREIT, equal weight, same cadence and costs |
| Eligibility | priced, listed for 126 sessions, book value known and describing a period at most 200 days old |
| Price data | a new price snapshot: SPY plus every panel mREIT, 2011-01-01 to the latest close |
| Window | from the first session with 12 eligible mREITs to the snapshot's end |
| Costs, execution | CEF cost tier (30/15 bps one-way), decided at a close and traded at the next close, every 21 sessions in 21 tranches |
| Counting | `tools/domain_search.py mreit_discount`: candidate 0.2, the 1/3 point and the benchmark, counted in the `mreit_discount` family |

## Success criterion, stated in advance

- **Corroborates:** active Sharpe > 0 and a t-statistic (active Sharpe × √years) above 1.0.
- **Contradicts:** active Sharpe ≤ 0.
- **Uninformative:** anything in between, or a window shorter than 3 years.

The criterion matches the H404702 and BDC pre-period tests, so the three can be compared.
The vol-matched active Sharpe and the eras (to 2016, 2017-2021, 2022 onward) are reported
but do not decide.

## Known weaknesses, stated in advance

- **Survivorship.** mREITs that failed in 2013, in March 2020 or in 2022 are missing. The
  likeliest bias is upward, since deep-discount names that failed are absent.
- **Small universe.** About 20 names, so the rule holds roughly 4.
- **Definition.** Book value is GAAP book. Some mREITs headline tangible or adjusted book
  instead. The audit compares against GAAP only.
- **Commercial vs residential mREITs differ in leverage and in how much of the book is
  marked.** The pool mixes them, as the rule does not distinguish.

## Result: NOT RUN. The book-value derivation failed its hand audit (2026-10-06)

No mREIT price was ever loaded, no snapshot was built, and no trial was run.

**Audit (seed 20261006).** 10 of 30 observations were more than 2% from the company's
stated GAAP book value per common share. The bar was at most 2. The table is in
`docs/research/data/mreit_audit_v1_results.txt`.

**Causes:**
- **Preferred stock left in common equity.** companyfacts carries only non-dimensional
  XBRL, and most mREITs tag preferred per series. This affected AGNC, ARR (twice), CIM,
  IVR, NYMT/ADAM, FBRT, and MFA (partially).
- **A 1000× share-count scale error** (NYMT 2011).
- **A definition difference** (MITT: liquidation preference against net proceeds).
- Two passes near the line (NLY, TRTX) carry the same defect at a smaller scale.

**The spent correction.** The derivation was moved to each filing's full XBRL instance:
dimensional class-of-stock members summed, and the share count checked against the cover
page (`parse_instance` and `bv_from_instance` in `src/research/mreit_data.py`, kept as
evidence). Tried on the 7 failing cases, it repaired NYMT, FBRT and IVR, but not:
- AGNC (preferred only in custom company elements);
- CIM (preferred tagged at 1/1000 scale);
- MFA (a total covering one of two series).

XBRL tagging of preferred stock is too heterogeneous for a mechanical derivation.

**Board ruling (three independent members).** Two votes closed this protocol as NOT RUN.
They held that switching to the company-stated figure would be a new method, not a fix:
it changes the source and the known-date rule, and it makes the audit near-circular. One
vote preferred that switch as a pre-registered amendment.

All three allow a successor protocol on company-stated GAAP book value per common share,
committed before any price, with these conditions:
- the GAAP-versus-adjusted rule and the known-date rule are frozen in advance;
- validation must not share its source with the extraction: compare against the XBRL
  derivation on filers with no preferred, plus an independent audit on seed 20261007 in
  which the auditor finds each figure without the extractor's pointer;
- missing figures leave the name ineligible, and the missing rate is reported;
- no further corrections.

This NOT RUN counts in the `mreit_discount` family's record.
