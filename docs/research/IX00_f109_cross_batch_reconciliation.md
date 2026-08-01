# IX-00 — reconciling [`F109`](../../RESEARCH_WEB.md) against its two batch artifacts

**Status:** offline reconciliation. No new measurement, no market claim. Written because
F109 was flagged as quoting nine figures with no reachable document. Every number
reconciles; one *clause* does not, and three qualifiers on how the figures should be read
fall out of the check.

**Artifacts:** `docs/research/data/ix00_sp500_march2026_event_pilot.json` (E97) and
`docs/research/data/ix00_ndx_december2025_event_replication.json` (E98).
**Guard:** `tests/test_f109_cross_batch_reconciliation.py`.

---

## The nine figures

| F109 states | artifact | field | value |
|---|---|---|---:|
| Nasdaq additions −1.5627% first open → implementation close | E98 | `additions.first_open_to_implementation_close_relative` | −1.562714 |
| Nasdaq deletions −0.6394% | E98 | `deletions.…` | −0.639425 |
| S&P additions +10.8709% | E97 | `additions.…` | +10.870918 |
| S&P deletions −3.4614% | E97 | `deletions.…` | −3.461407 |
| Nasdaq implementation volume 17.14× | E98 | `additions.implementation_volume_ratio_to_prior_20d_median` | 17.137807 |
| …and 8.60× | E98 | `deletions.…` | 8.601921 |
| S&P 8.65× | E97 | `additions.…` | 8.649664 |
| …and 13.75× | E97 | `deletions.…` | 13.751232 |
| twenty securities in two batches | both | `coverage.analyzed` | 8 + 12 = 20 |

The sign pattern F109 describes for Nasdaq additions also holds: −1.4631 and −2.0530 at 1
and 5 sessions, +7.7643 and +20.3155 at 20 and 60.

## Three qualifiers the reconciliation surfaces

### 1. What replicates is the volume *level*, not the side ordering

F109 says exceptional implementation-session volume "repeats", which is correct as a
magnitude claim — every group is 7×–17× its own prior 20-day median. But the ordering
between sides **inverts** between the batches:

| batch | additions | deletions | larger side |
|---|---:|---:|---|
| S&P Mar 2026 | 8.65× | 13.75× | deletions |
| Nasdaq Dec 2025 | 17.14× | 8.60× | additions |

So "liquidity demand repeats" must not be read as "additions draw more volume than
deletions". Both batches show a volume spike; they disagree about which side is larger.
E98's own interpretation string is careful about this ("did replicate for both additions
and deletions"), and this note pins the numbers behind that care.

### 2. The largest figure, +10.8709%, is three-quarters family migration

F108 established that gross add/delete labels mix offsetting family flows. E97 records the
decomposition, and the additions group is exactly its n-weighted composition — verified to
1e-6 on every shared metric:

```
(direct_entries × 1 + family_up_migrations × 3) / 4  ==  additions
   first open → implementation close:  (4.281225 + 3×13.067482) / 4 = 10.870918  ✓
   implementation volume ratio:        (12.696751 + 3×7.300636) / 4 =  8.649665  ✓
```

The one genuine **direct entry** returned **+4.2812%** over that window — about a third of
the group headline — while the three MidCap-400→S&P-500 migrations returned **+13.0675%**.
F109 quotes +10.8709% as the S&P addition figure without that split, and the split is the
larger part of the story: the number is mostly a statement about securities that were
already in the index family.

### 3. The two batches share one price vendor

"Cross-provider" in F109 and E98 means the **index** provider — S&P Global vs Nasdaq
Global Indexes, and the two official sources differ accordingly. The **price** provider is
identical: `Yahoo Finance via yfinance 1.2.0` in both artifacts, retrieved on the same day.
So the agreement on volume levels is not vendor-independent evidence — a shared vendor
convention (whole-day volume, adjustment policy, revision behaviour) would produce
agreement on its own. [`F110`](../../RESEARCH_WEB.md) already records that this vendor's
exact bytes move between same-day refreshes while the decision-level hash reproduces.

## The one clause with no committed numbers

F109 says Nasdaq additions outperform at 20/60 sessions "**with large winner
dispersion**". Neither artifact contains per-security **returns**. E98 keeps symbol lists
only (`ALNY FER INSM MPWR STX WDC` / `BIIB CDW GFS LULU ON TTD`); E97 keeps a richer
per-security record — `event_symbol`, `provider_symbol`, `action`, `transition`, and the
`SATS`→`ECHO` identity note — but still no per-security window. So the records exist and
the numbers do not. The
dispersion claim is carried over from E98's interpretation text, which asserts it in prose:
*"Longer-horizon addition performance is highly dispersed and mechanically selected from
strong prior winners."*

That claim may well be true — it is the ordinary shape of index-addition samples — but it
is **not verifiable from this repository**, and it cannot be recomputed here:
`raw_data_committed: false` and the provider is network-blocked in this environment. It
should be read as an unquantified caveat, not a measured one. If it matters to a later
decision, the fix is cheap and specific: retain per-security windows in the artifact next
time the tool runs.

Nothing else in F109 is unsupported. Eight of nine figures read straight out of the two
artifacts, the ninth is an arithmetic sum of two coverage counts, and the two
decomposition identities hold to 1e-6.
