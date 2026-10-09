# Data redistribution audit (2026-10-09)

**TL;DR.**
- **The repository is public.** It commits about 37 MB of vendor price observations so
  that every counted trial can be replayed byte for byte:
  - 22 Yahoo price snapshots;
  - a CEFConnect/Morningstar NAV panel;
  - a Yahoo futures panel.

  `venv/bin/python tools/data_inventory.py` counts **24 restricted data sets, 36.4 MB,
  cited by 197 trials**.
- **The GitHub Pages site also publishes Yahoo data.** It bakes in Yahoo fundamentals and
  daily closes.
- **Yahoo's and Nuveen's published terms do not grant redistribution rights.** The
  government sources (SEC, the Fed's DTB3, NOAA, Treasury) do.
- **The fix keeps replayability:**
  1. restricted observations move to a gitignored private store;
  2. manifests keep the sha-256 that names the exact bytes;
  3. a new build defaults to private for restricted vendors.
- **What to do about the history already pushed is Hudson's call.** Options and
  trade-offs are at the end.

*This is a reading of published terms, not legal advice.*

## 1. What is public today

### Price snapshots and panels (`docs/research/data/`)

| Prefix | Files | Size | Vendor (from each manifest's `sources`) | Trials that cite it |
|---|---|---|---|---|
| `DS-` | 22 snapshots (csv.gz + json) | 34.0 MB | Yahoo via yfinance 1.2.0 (raw OHLC + distributions); cash from FRED DTB3; ^IRX check from Yahoo. Two CEF snapshots also corroborate extremes with CEFConnect. | 164 |
| `CEFNAV-` | 1 | 2.4 MB | CEFConnect `pricinghistory` (weekly price and NAV; the site states its data come from Morningstar) | 31 |
| `FUT-` | 1 | 0.02 MB | Yahoo GC=F/CL=F front month | 2 |
| `BDCNAV-`, `MREITBV-` | 2 | 0.03 MB | SEC XBRL (companyfacts, frames) | 3 |
| `EARNDATES-`, `INSIDER-`, `SPINEVENTS-` | 3 | 0.3 MB | SEC EDGAR (submissions, Form 3/4/5 data sets, full-text search) | 19 |
| `IDXDEL-` | 1 | < 0.01 MB | Wikipedia, "Historical components of the S&P 500" changes table (CC BY-SA 4.0) | 3 |

**The largest DS snapshots:**

| Snapshot | Size | Holds |
|---|---|---|
| DS-0205b226 | 13.9 MB | 1,793 small caps, insider study |
| DS-18cef162 | 10.5 MB | 333 CEFs, 2003-2026 |
| DS-9731bf32 | 2.2 MB | 113 index deletions |
| DS-d038fe35 | 2.0 MB | 160 spin-offs |
| DS-52eda901 | 1.4 MB | 41 country ETFs |
| DS-bae9cfd9 | 1.1 MB | 332 CEFs, 1996-2003 |

The other 16 are under 0.6 MB each. The full per-file inventory, with dependent run IDs,
is reproducible:

```
venv/bin/python tools/data_inventory.py
```

### Study files (`docs/research/data/*.json`, 77 files)

These are summaries, fixtures and statistics, not price series. A scan for price-named keys
and long numeric arrays found only:
- small SEC-sourced NAV samples (`bdc_preperiod_gates*.json`);
- public-domain series: NOAA geomagnetic Ap (`geomag_ap_daily.json`), the Fed's WALCL via
  FRED (`fred_WALCL.json`), TreasuryDirect auctions (`treasury_coupon_auctions.json`), and
  the FOMC calendar.

### Other surfaces

| Surface | What is public | Source |
|---|---|---|
| GitHub Pages (`.github/workflows/pages.yml` → `tools/export_pages.py`) | The screener page bakes in `data/screener/fundamentals.json` (Yahoo fundamentals: P/E, yields, margins…) and `data/screener/prices.json` (Yahoo daily closes). Both are gitignored in the repo but published on the site. | Yahoo |
| `tone-ledger` branch | `data/tone_ledger/*.csv`: one row per (run, ticker, source) holding our own computed tone score, coverage and counts. No third-party text. | derived (own computation) |
| `data/live_runs/archive_2026-06-18_pre_clean_run/` | Paper-trading records: trades, signals, monitor events. A scan for IBKR account identifiers (`DU…`/`U…` numbers) found none. | own |
| Git history | No deleted data files: everything in history is also in the current tree. | — |

## 2. What the sources' terms say

| Source | Redistribution | Citation |
|---|---|---|
| **Yahoo** (via yfinance) | Not granted. The terms bar automated collection without prior approval, and building a database or data feed that substitutes for the services. They also bar redistributing or commercially exploiting content without written permission. APIs are licensed for personal, non-transferable use. yfinance's own README points to Yahoo's terms for any rights to the data. | [Yahoo Terms of Service](https://legal.yahoo.com/us/en/frontier/terms/otos/index.html); [yfinance on PyPI](https://pypi.org/project/yfinance/0.2.48) |
| **CEFConnect** (Nuveen; data from Morningstar) | Not granted. Nuveen's site terms limit content to personal, non-commercial use and bar copying, republishing and distribution without written permission. The CEFConnect pages say their data are supplied by Morningstar, whose licence is a further layer. | [Nuveen terms](https://www.nuveen.com/en-us/terms); [CEFConnect disclaimer](https://www.cefconnect.com/Footer/Disclaimer.aspx); [CEFConnect](https://cefconnect.com/) |
| **FRED** (DTB3, WALCL) | The underlying Federal Reserve Board data may be copied and distributed with the Board cited, unless otherwise indicated. FRED's own service terms add limits on scraping and on presenting FRED's data as a product, and require permission for series that carry a third-party copyright notice. DTB3 and WALCL are Board series. | [FRED legal notices](https://fred.stlouisfed.org/legal/terms/); [Board disclaimer](https://federalreserve.gov/disclaimer.htm) |
| **SEC EDGAR** | Free to access and reuse: government-created content and public filing content. | [SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions) |
| **Deutsche Bundesbank / ESCB** | Free reuse with the source quoted, of statistics in their standard published form. The right does **not** apply to third-party data without the originator's permission. The Frankfurt gold fixing lists the Frankfurt Stock Exchange as its source. | [ESCB reuse terms](https://www.bundesbank.de/en/homepage/user-information/terms-of-use-regarding-the-reuse-of-escb-statistics-621188); [ECB usage policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html) |
| **Wikipedia** | CC BY-SA 4.0: reuse is allowed with attribution, and derivatives must share alike. | [Wikipedia:Copyrights](https://en.wikipedia.org/wiki/Wikipedia:Copyrights) |
| **World Bank Pink Sheet** (validation only, not committed) | CC BY 4.0 | [World Bank terms](https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets) |

## 3. Assessment

| Surface | Basis to redistribute? | Exposure |
|---|---|---|
| DS snapshots (Yahoo) | none found | **high**: 34 MB of raw OHLC and distributions for about 3,000 tickers, a "database" in the terms' sense |
| CEFNAV (CEFConnect/Morningstar) | none found | **high**: a vendor NAV history |
| FUT (Yahoo futures) | none found | low in size, the same issue in kind |
| Pages screener (Yahoo fundamentals + closes) | none found | **high**: actively republished on a public website on a schedule |
| SEC-derived panels, NOAA, FRED/Board series, Treasury | yes, with citation | none, provided the citations stay |
| IDXDEL (Wikipedia) | yes, CC BY-SA | low: the manifest names the source; the panel and its derivatives must carry CC BY-SA |
| tone-ledger, live-run archive | own data | none found |

## 4. Proposal (keeps every trial replayable)

The private store already exists on `claude/commodity-linkage` (commit with
`MINER_TILT_PREPERIOD.md`):
- **`daily_data.PRIVATE_DATA_DIR`** (`local_research_data/`, gitignored).
- **`build_snapshot(..., private=True)`** writes the csv.gz there. The committed manifest
  records `observations.csv_sha256` and keeps every validation field.
- **`load_snapshot`** looks in the committed store, then the private one. It still refuses
  bytes that do not hash to the name, so a private snapshot is exactly as verifiable as a
  public one. Anyone who rebuilds it gets either the same bytes or a refusal.

### Steps

1. **Default to private for restricted vendors.**
   - `build_snapshot`: private when any price comes from Yahoo.
   - `cef_data` and `futures_panel`: the same, always.
   - Public stays the default only for SEC, Fed, Treasury and NOAA data.
   - A test asserts that a manifest whose `sources` name Yahoo or CEFConnect records private
     observations.
2. **Move existing restricted files out of the tree.**
   - Copy them to the private store.
   - `git rm` the csv.gz files (DS Yahoo snapshots, CEFNAV, FUT); keep the manifests.
   - Add `observations` to each manifest. Manifests are append-only in spirit, so record
     this as a new field.
   - Every trial still replays on any machine that holds the store. The sha in the ledger
     already names the bytes.
3. **Make the private store portable for collaborators** (proposed, not yet built):
   - a tarball of the store with its sha-256 list, shared out of band (not via GitHub);
   - a `tools/data_inventory.py rebuild <sha>` that refetches a snapshot from its manifest
     and verifies the hash. Yahoo revisions can make a rebuild differ; the manifest's
     `vintage` explains a mismatch, and the hash catches it.
4. **CI.** Tests use synthetic data and are unaffected. `trial_ledger verify` needs no
   observations. The gate's witness stage (`tools/admit_tactical._data_files`) should
   accept a private snapshot when the manifest records `observations` and the file is in
   the private store.
5. **Pages.**
   - Stop baking `prices.json` and the raw fundamentals into the public site.
   - Publish only the screener's own derived outputs (preset membership, scores, bucket
     tags), or the page structure with "data available locally".
   - The tone ledger can stay.
6. **Attribution.**
   - Keep the source citations in every public manifest.
   - Add a `docs/research/data/README.md` that states each source's terms and that
     restricted observations are not distributed.
   - Mark IDXDEL CC BY-SA.

### History already pushed (Hudson decides)

| Option | What it does | Trade-offs |
|---|---|---|
| **A. Stop adding; leave history** | Steps 1-6 only | The past files stay retrievable from old commits and PR refs. Cheapest and reversible; it does not remove past exposure. |
| **B. Rewrite history** (`git filter-repo` on the restricted csv.gz paths), then force-push | Removes them from the branch history | Breaks every clone, fork and open PR (#63, #64). GitHub keeps the old objects reachable through PR refs and caches until GitHub Support purges them. Old commit SHAs cited in protocol docs change. Irreversible. |
| **C. Make the repository private** | Ends public access to everything, including history | Ends the public Pages site on a free plan (Pages from a private repo needs a paid plan), and changes D12's public-positioning decision. Reversible. |
| **D. License or switch sources** | Licensed vendor data (with redistribution rights) or official sources | Costs money or coverage; the history question remains. |

Recommendation (for discussion): **A now** (steps 1-6 in one PR), then decide **B or C**
on whether past exposure matters enough to accept the breakage. The trial ledger and the
admission records are unaffected by every option, because they cite data by hash, not by
path.
