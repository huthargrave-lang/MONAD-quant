# Research data: sources, terms, and what is public

**TL;DR.**
- **Every frozen data set here is content-addressed.** `<PREFIX>-<sha>.json` is its
  manifest; `<PREFIX>-<sha>.csv.gz` holds its observations; the sha is the sha-256 of the
  *decompressed* CSV. A trial cites the sha, so it names exact bytes.
- **The repository is public, so observations from vendors whose terms grant no
  redistribution right are not committed.** Yahoo (prices, futures) and CEFConnect
  (closed-end fund NAVs) live in the gitignored private store `local_research_data/`.
  Their manifests stay here, with an `observations` record naming the bytes by sha.
- **Government and CC-licensed sources stay public:** SEC filings, Federal Reserve series,
  Treasury, NOAA, and one CC BY-SA table from Wikipedia (attribution below).
- **Every loader reads both stores and refuses bytes that do not hash to their name**, so
  a private data set is exactly as verifiable as a public one.
- **To get the private store:** import an archive from a collaborator
  (`tools/data_inventory.py import`), or rebuild a data set from its manifest (the hash
  says whether you got the same bytes).

*This is a reading of published terms, not legal advice. The full audit is
[`../DATA_REDISTRIBUTION_AUDIT.md`](../DATA_REDISTRIBUTION_AUDIT.md).*

## 1. How the two stores work

| | Committed store | Private store |
|---|---|---|
| Where | `docs/research/data/` | `local_research_data/` (gitignored) |
| Holds | every manifest; observations whose source allows redistribution | observations whose source does not |
| Who decides | `src/research/data_store.py`: `RESTRICTED_VENDORS` matched against a manifest's `sources` | the same |
| Read by | every loader (`load_snapshot`, `cef_data.load_panel`, `futures_panel.load`, ...) | the same loaders, searched second |

The rules, all enforced in `src/research/data_store.py`:
1. A writer stores observations privately exactly when its manifest's sources name a
   restricted vendor. `private=False` with such a source is refused.
2. A restricted file is never written where git would publish it. The committed store is
   refused outright; any other path inside the repository must be git-ignored.
3. A private manifest records
   `"observations": {"stored": "private (not redistributable)", "store": "local_research_data", "csv_sha256": "<sha>"}`.
4. A loader that cannot find a private file says so, and names how to restore it.

See where everything is: `venv/bin/python tools/data_inventory.py` (`PUBLIC-RESTRICTED`
must stay at 0; `tests/test_private_store.py` asserts it).

## 2. Sources and their terms

| Prefix or file | Source | Terms | Stored |
|---|---|---|---|
| `DS-` (price snapshots) | Yahoo via yfinance: raw OHLC and distributions. Cash leg: FRED DTB3. `^IRX` from Yahoo is a build-time check, not stored. Two CEF snapshots corroborate extremes against CEFConnect (also not stored). | Yahoo grants no redistribution right: its terms bar automated collection without approval, building a substitute database, and redistributing content without written permission. yfinance defers to Yahoo's terms. [Yahoo Terms of Service](https://legal.yahoo.com/us/en/frontier/terms/otos/index.html); [yfinance on PyPI](https://pypi.org/project/yfinance/0.2.48) | private |
| `DS-` miner pre-period segments | as above, plus the Frankfurt gold fixing via the Bundesbank, whose source is the Frankfurt Stock Exchange | ESCB reuse terms exclude third-party data without the originator's permission. [ESCB reuse terms](https://www.bundesbank.de/en/homepage/user-information/terms-of-use-regarding-the-reuse-of-escb-statistics-621188); [ECB usage policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html) | private |
| `CEFNAV-` | CEFConnect `pricinghistory` (Nuveen; the site says its data come from Morningstar) | Personal, non-commercial use; no copying, republishing or distribution without written permission. [Nuveen terms](https://www.nuveen.com/en-us/terms); [CEFConnect disclaimer](https://www.cefconnect.com/Footer/Disclaimer.aspx); [CEFConnect](https://cefconnect.com/) | private |
| `FUT-` | Yahoo `GC=F`/`CL=F` front month | as Yahoo above | private |
| `BDCNAV-`, `MREITBV-` | SEC XBRL (companyfacts, frames) | Government content and public filings, free to reuse. [SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) | public |
| `EARNDATES-`, `INSIDER-`, `SPINEVENTS-` | SEC EDGAR (submissions, Form 3/4/5 data sets, full-text search) | as SEC above | public |
| `IDXDEL-` | Wikipedia, the S&P 500 historical-components changes table | CC BY-SA 4.0: reuse with attribution, derivatives share alike. [Wikipedia:Copyrights](https://en.wikipedia.org/wiki/Wikipedia:Copyrights) | public, attributed (section 3) |
| `fred_WALCL.json`; the DTB3 cash leg inside each `DS-` snapshot | Federal Reserve Board series (H.4.1; the 3-month bill rate), via FRED | Board data may be copied and distributed with the Board cited. FRED's own terms add limits on scraping and require permission for series carrying a third-party copyright notice; WALCL and DTB3 are Board series. [FRED legal notices](https://fred.stlouisfed.org/legal/terms/); [Board disclaimer](https://federalreserve.gov/disclaimer.htm) | public (the DTB3 leg travels with its private snapshot) |
| `geomag_ap_daily.json` | NOAA geomagnetic Ap index | US government work | public |
| `treasury_coupon_auctions.json` | TreasuryDirect auction results | US government work | public |
| FOMC calendar fixture | Federal Reserve meeting calendar | as the Board above | public |
| World Bank Pink Sheet | used for validation only | CC BY 4.0. [World Bank terms](https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets) | not committed |

The other `*.json` files here are summaries, fixtures and statistics computed by this
repository, not vendor series.

## 3. Attribution for the CC BY-SA panel (`IDXDEL-`)

`IDXDEL-079e59a6a79f6ccd2fc8b3cec28cc23e047bf94f684b7cbdf0f6c9ffed539e89.csv.gz` and its
manifest are a derivative of a Wikipedia table:

- **Source:** the Wikipedia article "Historical components of the S&P 500", its dated
  changes table, fetched 2026-10-07 (the manifest's `source` records the fetch).
- **Authors:** Wikipedia contributors (the article's history lists them).
- **Licence:** [Creative Commons Attribution-ShareAlike 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **Changes:** reduced to `(ticker, effective date)` for removals whose stated reason is
  market capitalization (not an acquisition, merger or spin-off), effective 2010-01-01
  onward.
- **Share-alike:** this panel, and any derivative of it, is distributed under CC BY-SA 4.0.
  That licence covers this data set only, not the rest of the repository.

## 4. Getting the private store

**From a collaborator (the normal way).** The holder exports; you import. The archive is
shared out of band, never through this repository or any public place.

```
# on a machine that has the store
venv/bin/python tools/data_inventory.py verify
venv/bin/python tools/data_inventory.py export ~/monad-private-store.tar

# on yours
venv/bin/python tools/data_inventory.py import ~/monad-private-store.tar
venv/bin/python tools/data_inventory.py verify
```

The archive holds `local_research_data/<file>`, a `SHA256SUMS` list (checkable with
`shasum -a 256 -c SHA256SUMS` inside that directory) and an `INDEX.json`. `import` checks
every file against both its `SHA256SUMS` line and the sha in its name before writing any
of them. It refuses links, paths outside the store and files not in the list.

**Rebuilding (when no archive exists).** Each manifest records what was fetched: the
universe, window, sources, vintage and validation. To rebuild:

| Prefix | Rebuild with | Notes |
|---|---|---|
| `DS-` | `daily_data.build_snapshot(manifest["universe"], window.start, window.end, ...)`, passing the same `optional`, `close_only`, `extreme_bounds` and corroboration source the manifest records | The protocol doc that cites the sha names the exact call. |
| `DS-` miner pre-period | `miner_preperiod.build_segment(segment)` | |
| `CEFNAV-` | `cef_data.write_panel(*cef_data.build_panel())` | The universe is CEFConnect's listing on the day you fetch, so the bytes will differ. |
| `FUT-` | `futures_panel.build(manifest["symbols"], window.start, window.end)` | |

Writers store privately on their own and never overwrite an existing file. Then load the
sha the trial cites:
- the same bytes come back, so the trial replays exactly; or
- the loader reports no such file, because the rebuild produced a different sha.

Vendors revise history: Yahoo rewrites distributions, and CEFConnect's universe changes.
A different sha is a different data set. It cannot replay a trial that cited the old one;
only the original bytes can. That is why the archive is the primary path, and why a
manifest's `vintage` is recorded: it explains the mismatch.

**Continuous integration has no private store.** No test in `tests/` reads a real private
observation file except `tests/test_private_store.py`'s replay check, and that check
follows one rule (`tests/_private_store.py`):
- a private file that is **absent** skips, with a reason naming the file and the restore
  command;
- one that is **present** must verify: a hash mismatch fails, it never skips;
- with `MONAD_REQUIRE_PRIVATE_STORE=1` an absent file fails too. Set this on a machine or
  CI job that is meant to hold the store.

The admission gate's witness stage witnesses a private data set's committed manifest on
the deploy branch, and verifies the private file locally by its sha-256.

## 5. The public website (GitHub Pages)

`tools/export_pages.py` builds the site and `.github/workflows/pages.yml` publishes it.
The site carries no Yahoo fundamental, no price, and no number computed from either (the
score, flags and concentration all are). It publishes what this repository owns:
- the authored universe and its tags;
- the bucket ledger and the lens definitions;
- lens membership where authored tags alone decide it;
- its own tone readings. Headline text is withheld, because it is third-party copy.

Where a vendor value would appear, the site shows an explicit "kept local" state instead.
The policy lives in one place, `research_ui.public_screener_payload`, and fails closed on
any field it has not classified. The export never opens the vendor caches, and the
workflow no longer fetches them. The local server (`tools/research_ui.py serve`) is
unchanged and shows everything on disk.

## 6. Adding a data set or a source

- Write it through its module's writer. The writer decides public or private from the
  manifest's sources.
- **A new vendor:** read its terms first. If they grant no redistribution right, add it to
  `RESTRICTED_VENDORS` in `src/research/data_store.py` and add a row to section 2.
- Never `git add -f` a file from `local_research_data/`.

## 7. History

Until 2026-10-09 the restricted observations were committed here (24 data sets, 36.4 MB).
They were moved to the private store on that date, and their manifests gained the
`observations` record (option A of the audit). Git history was **not** rewritten, so the
earlier commits still contain those files.
