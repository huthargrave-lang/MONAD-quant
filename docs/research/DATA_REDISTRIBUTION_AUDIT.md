# Data redistribution audit (2026-10-09)

> **Decision (2026-10-09): option A, implemented.** No restricted vendor observations
> are committed any more, and the public site carries no Yahoo data. Git history is
> untouched. What was done is in [section 5](#5-decision-option-a-2026-10-09). The
> sources, their terms and the private store are documented in
> [`data/README.md`](data/README.md). Sections 1 to 4 below are the audit as written
> before the decision.

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
3. **Make the private store portable for collaborators** (built: see section 5):
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

## 5. Decision: option A (2026-10-09)

Hudson chose **option A**: stop adding restricted vendor observations to the public
repository and leave git history as it is. Steps 1 to 6 are implemented on this branch
(PR #65).

**Result.** `venv/bin/python tools/data_inventory.py` now reports:
- **0** restricted data sets in the public tree (was 24, 36.4 MB);
- **24** private data sets, cited by **197** trials, all present and verified in the local
  store.

```
committed store (public)                      private store (gitignored)
docs/research/data/                           local_research_data/
  every <PREFIX>-<sha>.json manifest  ──sha──▶  DS-*.csv.gz (22, Yahoo)
  SEC / Fed / Treasury / NOAA / CC observations CEFNAV-*.csv.gz (CEFConnect)
                                                FUT-*.csv.gz (Yahoo futures)
          ▲                                             ▲
          └──── loaders search both, verify sha-256 ────┘
```

| Step | What was built | Where |
|---|---|---|
| 1. Private by default | One policy module decides public or private from a manifest's `sources`. It covers Yahoo/yfinance, CEFConnect and the Frankfurt fixing. Every writer goes through it: `build_snapshot`, `cef_data.write_panel`, `futures_panel.build`, and the SEC panels, which stay public. `private=False` with a restricted source is refused. A restricted file can never be written where git would publish it. Every loader reads the private store and verifies the sha. | `src/research/data_store.py`; writers and loaders in `src/research/` |
| 2. Migration | `tools/data_inventory.py migrate` moved 22 DS snapshots, CEFNAV-fd7099e2 and FUT-ff5e7e3d (24 files, 36,375,595 bytes). For each file it verified the committed bytes, copied them, verified the copy, then `git rm`'d the original. Each manifest gained exactly one field, `observations`, in its own serialization. Copies are in this worktree's store and in the main checkout's store, both verified. All 24 private data sets load through their normal loaders, and all 31 recorded (domain, data) pairs load through their domains. | commit "Move the 24 restricted vendor data sets ..."; `tests/test_private_store.py` |
| 3. Portability | `data_inventory.py verify`, `export OUT.tar` and `import IN.tar`. The archive holds the files plus `SHA256SUMS` and `INDEX.json`, and an export is deterministic. Import checks every file against its sha-256 line and its content hash before writing any of them, and refuses links, path traversal and unlisted files. Rebuild guidance is in the data README. | `tools/data_inventory.py`; `tests/test_data_inventory.py`; [`data/README.md`](data/README.md) section 4 |
| 4. CI and the gate | The witness stage witnesses a private data set's committed manifest on the deploy branch. It verifies the private file locally: present, hashing to the sha, and matching the manifest's record. It records which files it verified that way. Tests that need real observations follow one rule (below). | `tools/admit_tactical.py` `_data_evidence`; `tools/admit.py` `stage_witness`; `tests/_private_store.py` |
| 5. Pages | The site publishes no Yahoo fundamental, no price, and no number computed from either. It shows the authored universe, tags, buckets, lens definitions, authored-tag lens membership and the repository's own tone readings, with an explicit "kept local" state elsewhere. The policy fails closed on any unclassified field. The export never opens the vendor caches, and the workflow no longer fetches them; it installs `requests` for the tone step. The local server is unchanged. | `tools/research_ui.py` `public_screener_payload`; `tools/export_pages.py`; `.github/workflows/pages.yml`; `docs/research/SCREENER_COMBINED_DRAFT.html` |
| 6. Attribution | Each source, its terms (the URLs in section 2), what is public and private and why, how to restore the store, and the CC BY-SA attribution for IDXDEL. | [`data/README.md`](data/README.md) |

**Moving the private store to another machine.** Share the archive out of band, never
through the repository:

```
venv/bin/python tools/data_inventory.py export ~/monad-private-store.tar   # holder
venv/bin/python tools/data_inventory.py import ~/monad-private-store.tar   # recipient
venv/bin/python tools/data_inventory.py verify
```

**The rule for tests that need real observations** (`tests/_private_store.py`). CI has no
private store:
- an **absent** private file skips the test, with a reason naming the file and the
  restore command;
- a **present** file must verify: an altered file fails and never skips;
- with `MONAD_REQUIRE_PRIVATE_STORE=1`, an absent file fails too.

Only the replay checks in `tests/test_private_store.py` need the store. Its policy checks
always run: no restricted manifest without its record, no committed restricted file, 0
PUBLIC-RESTRICTED, and every sha a trial cites has its manifest.

**Not done, by decision.**
- History is not rewritten. The 24 files remain retrievable from earlier commits and PR
  refs.
- Options B and C (rewrite history, or make the repository private) remain open. Nothing
  here forecloses them.
