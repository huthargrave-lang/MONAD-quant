# Quantifying off-balance-sheet debt for the screener — 2026 investigation

> **Status:** research + surfacing plan for `tools/stock_screener.py`. Follow-on to
> [`AI_SHADOW_DEBT_LENS_2026.md`](AI_SHADOW_DEBT_LENS_2026.md), whose closing line —
> *"Not a scrape of SPV notional from 10-K footnotes (future work if a free source
> exists)"* — this document answers: **a free source exists for part of it, verified
> by probe on 2026-08-06.** Nothing here is implemented yet; this is the plan.

## 1. What the market looks like now (Aug 2026)

- Global AI-related debt issuance is projected at **~$570B for 2026**; $236B had priced
  by May 31 (4× the year-earlier pace). Bond demand is cooling — hyperscaler order
  coverage fell from ~5× (Feb) to <2× (Jul). (Forbes, 2026-07-17.)
- The flagship off-balance-sheet structure is the **Meta / Blue Owl "Hyperion" JV**:
  ~$27B A+ rated SPV debt (PIMCO ~$18B, BlackRock ~$3B anchor), Blue Owl 80% / Meta 20%,
  Meta leases the campus back long-term — capex becomes rent, and the project debt sits
  on the SPV, not on Meta. 24-year amortizing, ~225bp over Treasuries.
- Press estimates of aggregate Big-Tech off-balance-sheet AI exposure run to
  **$1.65T**, but the widely-cited "$1.5T" figure is a *funding gap* (investment needs
  minus cash flow through 2028), not booked debt. Named SPV users in reporting: Meta,
  xAI, Oracle, CoreWeave (~$120B+ shifted to private credit so far).
- Mechanically the exposure lands in three footnote families: **VIE disclosures**
  (control without consolidation), **operating-lease commitments** (the lease-back leg),
  and **purchase obligations** (capacity / take-or-pay).

## 2. The free quantification path — verified

SEC `data.sec.gov` XBRL APIs (free, JSON, no key; declared User-Agent; ≤10 req/s).
One `companyfacts` call per ticker returns every tagged concept. Probed 2026-08-06:

| us-gaap concept | META | MSFT | ORCL | Reading |
|---|---|---|---|---|
| `OperatingLeaseLiability` | **$25.2B** (2025-12-31) | **$21.9B** (2026-06-30) | — | broadly tagged |
| `VariableInterestEntityEntityMaximumLossExposureAmount` | **$5.79B** (2026-03-31) | 404 | 404 | sparse, but live where it matters |
| `UnrecordedUnconditionalPurchaseObligation` | 404 | 404 | 404 | usually text-only, rarely tagged |

Companion concepts worth pulling in the same pass: `GuaranteeObligationsMaximumExposure`,
`SupplierFinanceProgramObligation` (ASU 2022-04), `FinanceLeaseLiability`.

**The honest shape of the data:** coverage is patchy by design of the filers, so this
slots into the repo's absence-flag discipline — an untagged concept is `None`
("filer did not tag it"), never `0` ("filer has none"). Meta's $5.79B VIE max-loss is
also much smaller than the headline $27B SPV notional: max-loss-to-the-sponsor is a
*different fact* than SPV debt outstanding, and the UI must not conflate them.

## 3. Surfacing plan for `tools/stock_screener.py` (phased)

1. **Phase 1 — shipped.** Editorial `shadow_debt` tags + `ai_shadow_debt` lens
   (bucket marks over on-BS D/E).
2. **Phase 2 — EDGAR overlay.** `fetch` gains an optional `--edgar` pass:
   ticker→CIK from SEC `company_tickers.json`, one `companyfacts` request per name
   (123 requests ≈ a nightly job), extracting the concepts above into new row fields:
   `op_lease_liab`, `vie_max_loss`, `guarantees`, `purchase_obl`, `supplier_finance`,
   plus `obs_legs` (which of the five were tagged). Derived column:
   `adj_debt_to_equity` = (total debt + tagged OBS legs) / equity, shown **next to**
   on-BS D/E, never replacing it; rows with zero tagged legs show "—" with the legs
   list empty.
3. **Phase 3 — lens upgrade.** The `ai_shadow_debt` lens scatter gains the option to
   plot on-BS D/E (x) vs adjusted D/E (y): distance above the diagonal *is* the
   shadow wedge. Editorial tags stay as the mark shape/color; XBRL numbers make the
   axes.
4. **Out of scope for free data:** untagged SPV notionals living in 10-K prose
   (Beignet-class deals disclosed narratively). Flag as `obs_legs`-absent rather than
   estimated.

## 4. The lost Reddit / Bloomberg coverage section

Not deleted — **stranded on `development`**. This branch forked at `9eed12c`;
`development` is exactly one commit ahead: `404e071` ("checkpoint before checking out
cursor/screener-buckets-toggle-45c8"), which contains the whole sentiment screener lab:

- `tools/screener_lab.py` (1,527 lines): P/E + growth (yfinance), **Bloomberg public
  RSS headline tone** (6 feeds), **Reddit Atom-feed post tone** (4 subreddits, RSS
  anonymous / OAuth optional), no-ML lexicon with `explain_tone()`, None≠0 coverage
  discipline throughout.
- `tests/test_screener_lab.py` (891 lines, 66 tests), `docs/research/SCREENER_value_growth_sentiment.md`,
  systemd units (`deploy/monad-screener.service/.timer`), +531 lines of `research_ui.py`
  (the dropdown filter page with provider-state table and tone columns).
- Its snapshot is still on disk: `data/cache/screener_snapshot.json` (2026-08-04,
  150 rows with `bloomberg_tone/coverage`, `reddit_tone/coverage`).

**Feed status re-verified 2026-08-06:** Reddit `r/stocks/new.rss` → 200 anonymous;
Bloomberg `feeds.bloomberg.com/markets/news.rss` → **301** to
`www.bloomberg.com/feeds/markets/news.rss` → 200, so the restored fetcher must follow
redirects (or update the feed URLs).

**Restore path:** merge `development` into this branch (or cherry-pick `404e071`).
Conflicts will concentrate in `tools/research_ui.py` — the checkpoint mounts the lab at
`/screener`, which this branch has since rebuilt as the preset/dropdown fundamental
screener. Resolution: keep the current `/screener`, remount the lab at its own route
(e.g. `/sentiment`) with a rail entry, or fold its tone columns into the fundamental
snapshot as a join on ticker.

## 5. Reddit *popularity* (distinct from tone)

The lab measures tone over ~25 posts/subreddit — not "what's popular". For
most-mentioned/trending, free keyless sources exist: **ApeWisdom API** (mention counts
per ticker across major stock subreddits, scanned twice hourly) and **Tradestie**
(WSB top-50 JSON). Either joins onto the snapshot as `reddit_mentions` /
`reddit_rank`, enabling a "Reddit favorites" preset — mention counts stay a
*popularity* fact, tone stays a *text* fact, and neither enters ranking un-weighted,
per the lab's own design rule.
