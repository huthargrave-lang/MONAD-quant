# Proposal: a minimal, accession-scoped, append-only EDGAR ledger job

**Role:** proposer. **Decision:** design of the first EDGAR ledger slice and its runner.

## Question

Six queued studies (H46, H48, H49, H51, H52, H53) are `BLOCKED_ON_DATA`: the sandbox proxy returns
403 at CONNECT for sec.gov and data.sec.gov (`docs/research/BACKLOG_blocked_on_data.md:22-26, 37-45`;
`tools/research_backlog.py:132-146`). FD-00 ruled: build the append-only, accession-scoped ledger
before any model (`FD00_sec_filing_delta_lab.md:10-11, 19-27`); the frontier orders FD-00 backfill →
FD-01 → RN-01 (`PUBLIC_INVESTMENT_INTELLIGENCE_FRONTIER.md:582-601`). What is the smallest job that
starts that ledger honestly, and where does it run?

## Evidence

- **A pattern exists.** `pages.yml:45-56` pushes daily tone rows to a dedicated `tone-ledger` branch
  (bootstrap `:81-99`, rebase-retry push `:120-132`), chosen over `development`, Actions artifacts
  and the Pages deploy (`docs/TONE_LEDGER.md:15-27`). Growth: 563k rows/yr, 37 MB raw, 3.6 MB gz (`:48`).
- **A verifier exists to mirror.** `src/research/trials.py:920-956` `verify_history` enforces
  `"prefix"` / `"identical"` / `None` per path against merge-base and every branch commit
  (`:959-965`), "shared by every append-only store". `tools/trial_ledger.py:57-69` exits 1 on violation.
- **Rights are settled.** SEC content is free to reuse (`DATA_REDISTRIBUTION_AUDIT.md:88`;
  `data/README.md:51-52`); SEC is absent from `RESTRICTED_VENDORS` (`src/research/data_store.py:71-73`),
  so the policy module publishes it. FD-00: store hashes and locators, quote minimally (`FD00:99-102`).
- **Fair access is encoded unevenly.** `bdc_text_nav.py:21-22, 52-56` reads `SEC_USER_AGENT` from
  the environment and refuses a value without `@`. But `sec_form25_population_lab.py:51-53` and
  `sec_action_chain_join_lab.py:83` ship a placeholder `research@example.com`, `bdc_data.py:43`
  declares no contact, and all three space requests at 0.12 s (~8 req/s), not "materially slower
  than the cap" (`FD00:85-89`).
- **Parsing precedent.** `parse_master_index` (`sec_form25_population_lab.py:169-235`) groups
  index rows by accession because the index emits a filer and a subject row per accession
  (2,282 rows → 1,141 accessions, `CA_CLOCK100_form25_population.md:59-80`). Acceptance is read
  from `<ACCEPTANCE-DATETIME>` into `America/New_York` (`:391-396`); raw index bytes are hashed,
  not committed (`:672-687`).
- **The clock rules have no consumer.** `PT01_substrate_readiness.md:54-66, 74-78`: FD-00's fixtures
  are read only by a test; re-scope item 1 is "one function, one consumer: `tradable_time(filing)`".
  Measured rollover bracket: `(17:30:14, 17:47:43]` (`tests/test_sec_clock_cross_fixture.py:18-26`).
- **Identity and corrections.** Accession prefix ≠ issuer (`FD00:180-195`); quarterly indexes are
  rebuilt weekly, old daily indexes are not (`FD00:170-178`); the SGML header is Tier 1 (`FD00:216-223`).

## Proposal

### (a) First slice

**Daily `form.idx` rows for `{10-K, 10-K/A, 10-Q, 10-Q/A}`, each enriched by its `<accession>.hdr.sgml`.**
This is exactly FD-00's population (`FD00:238-243`) and the Tier-1 header gives acceptance time,
role blocks, period, `DATE AS OF CHANGE`, and `PRIVATE-TO-PUBLIC` without touching a filing body.
Bytes: ~993 B per committed row (measured on a full sample row); ~30k rows/yr (≈119/business
day, ≈118 KB/day; ≈30 MB/yr raw, ≈5–6 MB/yr git-packed — one-sixth of the tone ledger's raw
growth). Downloads: one `form.idx` (~0.5 MB) plus ~120 headers × ~3 KB ≈ 0.9 MB/day; the worst
10-Q deadline day (~3,000 rows) is 12.5 min of header fetches at 4 req/s.
Rejected: full text (MBs per filing, needed later); `companyfacts` (Tier 3, period-shortcut hazard,
`FD00:216-223, 286-289`); 8-K (doubles volume; slice 2).

### (b) Storage

Branch **`edgar-ledger`**, same dedicated-branch reasoning as `pages.yml:45-56`. Layout:

```
README.md                               editable (copy of docs/EDGAR_LEDGER.md at bootstrap)
data/edgar_ledger/rows/YYYY-MM.jsonl    prefix-only  — filing / revision / probe / seal rows
data/edgar_ledger/inputs/YYYY-MM.jsonl  prefix-only  — one line per fetched URL: bytes, sha256, http_status, fetched_at, run id
```

Raw `form.idx` and header bytes are **not committed**; every row carries their sha256 and URL, so
anyone can re-fetch and re-hash (the FD-00A manifest requirement, `FD00:624-627`). A study
never cites the branch; it freezes an extract through `data_store.write("EDGARLEDGER", ...)` into
`docs/research/data/EDGARLEDGER-<sha>.csv.gz` with a manifest, per `data/README.md:3-7`, and
cites that sha.

Invariants, checked by `tools/edgar_ledger.py verify [--against origin/edgar-ledger]` (exit 1 on
violation, as `trial_ledger.py:57-69`):
1. history: `trials.verify_history` with `rows/*.jsonl`, `inputs/*.jsonl` → `"prefix"`, README → `None`;
2. `(accession, revision_id)` unique; a `filing` row precedes its `revision` rows; corrections are
   new rows, never edits;
3. `accepted_at_utc`, `clock_class`, `market_phase`, `tradable_policy_daily` recomputed from
   `accepted_raw` + `filed` + `tz_rule` must equal the stored values (`FD00:279`);
4. no filing body: denylisted keys, row ≤ 4 KB;
5. each day's `seal` row hashes that day's lines; every cited sha256 has an `inputs` line.
The workflow runs `verify` **before** pushing and refuses to push on failure.

### (c) Cadence and runner

A separate workflow `edgar-ledger.yml` (`pages.yml:19-20`'s one-schedule-per-decision rule cuts
for separation: a ledger must neither gate nor be gated by the deploy). Daily at **07:17 UTC**,
after the prior Eastern day's index is final; `workflow_dispatch` with `quarter=YYYYQn` backfills
one quarter from the rebuilt quarterly `form.idx` (~7,500 rows ≈ 31 min at 4 req/s; 2019 onward is
28 runs, ~210k rows, ~38 MB packed); a monthly sweep re-reads the trailing quarter's rebuilt index
and appends `revision` rows for vanished or changed accessions.

Runner: **GitHub Actions**, not the Pi: `docs/TONE_LEDGER.md:21-22` already decided the Pi is not a
ledger pusher until `ReadWritePaths` and a deploy key are extended, and it hosts the live trader.
`SEC_USER_AGENT` comes from a repository secret via the `bdc_text_nav` pattern; the job refuses to
fetch without `@` or with `example.com`; spacing is 0.25 s (≤4 req/s) with `fetch_with_cache`'s
bounded backoff (`sec_form25_population_lab.py:486-512`); a 403/429 aborts the run and lands as a
`probe` row — degraded, never silent.

Rights: public-domain government records, and the slice redistributes metadata and hashes only, so
the third-party-exhibit caveat (`FD00:99-102`) is never reached. The job's obligations are the
declared identity and the rate; both are tested.

### (d) One row

```
kind=filing | ledger_version | parser_version
accession                      from the form.idx path
submitter_cik_prefix           stored, never identity (FD00:180-195)
issuer_cik, issuer_name, sic, roles[{role,cik}]   hdr.sgml role blocks
form, form_base, is_amendment, filed, period
accepted_raw                   <ACCEPTANCE-DATETIME> verbatim
tz_rule, accepted_at_utc       "America/New_York#v1" (FD00:202-210)
date_as_of_change, dissemination_kind, public_release_date
clock_class                    second | legacy_midnight_display | not_public_event_time | date_only
market_phase, tradable_policy_daily, quality_flags[]   PT-01 outputs (FD00:602-620)
idx_source, idx_sha256, hdr_source, hdr_sha256, hdr_bytes, fetched_at, revision_id
```

### (e) Tests (`tests/test_edgar_ledger.py`)

1. The seven timestamped FD-00 fixtures pass through the production parser to their expected
   `market_phase`, `acceptance_time_quality` and tradable policy; the eighth is asserted
   contract-only. This makes the parser PT-01's "one consumer".
2. A 17:30:14 acceptance with same-day `filed` is not flagged inconsistent (F163 bracket).
3. Append-only in a temp git repo: append ok; byte edit, deletion, rewrite → violation (mirrors
   `tests/test_trial_ledger.py:358`).
4. Two index rows for one accession → one `filing` row with both roles (the CA-CLOCK100 lesson).
5. Re-seen accession with changed `hdr_sha256` or `DATE AS OF CHANGE` → `revision` row; identical → nothing.
6. `<PRIVATE-TO-PUBLIC>` → `not_public_event_time`, tradable from `PUBLIC-REL-DATE`'s next session.
7. User-agent guard (`example.com`, missing `@`) refuses; `MIN_INTERVAL ≥ 0.2` pinned.
8. Invariants 3–4 (clock recomputation, no body) on a sample shard.

### (f) First study unblocked

**FD-00 coverage diagnostics 1–4 and 9** (`FD00:249-260`) become computable per form-year from day
one, and the gate "≥95% of rows retain header, hash and deterministic identity" (`FD00:265-267`)
decides whether a shard may be cited. Two pre-registered questions on the first frozen extract:

- **S1 — is `filed` a safe daily clock for 10-K/10-Q?** Statistic: share of rows accepted after
  16:00 ET or with `filed` ≠ acceptance date. Rule: Wilson 95% lower bound ≥ 1% → FD-01 must join
  on `tradable_policy_daily` and `filed` is banned as a clock; upper bound < 1% → `filed` allowed
  with the measured error attached. Either outcome is a result.
- **S2 — H52 FD-AMEND-0 (metadata half).** Pair each 10-K/A to its original by `(issuer_cik,
  period)`; gate: pair rate ≥ 90% (`FD00:271`). Hypothesis: ≥25% of 10-K/A lags fall in
  [100, 135] days after fiscal year end (the Part III mode). Confirmed → Part III amendments are a
  separate population excluded from "corrective" FD-AMEND; refuted → the split needs documents.

Not unblocked: H46/H51/FD-01 still need documents and accession-scoped XBRL. Slice 2: 8-K with
`ITEM INFORMATION` (H49; IDEAS shortlist #3/#6/#8, all EDGAR-only). Slice 3: quarterly Financial
Statement Data Sets zips, hashed in a manifest as `insider_data.py:7, 125` does.

## Strongest objection and answer

*"A GitHub Action is just another unverifiable fetcher, and committing filings bloats the repo."*

Verifiability: every row names a public URL and the sha256 of the bytes it saw; a reader
re-fetches `hdr.sgml` and compares — a check nobody can run against the Yahoo panels, which is why
those are private. The runner is further pinned by `inputs` lines (status, bytes, run id), by
`verify --against` walking every branch commit, and by `probe` rows for failures.
Bloat: no filing body is committed. ≈118 KB/day, ≈30 MB/yr raw, ≈5–6 MB/yr packed, on a branch
nobody clones with `development` (the repo pack is 49 MB today); the 2019+ backfill is ≈38 MB
packed. The tone ledger already grows faster.
The real residual risk is different: SEC may 403 Azure runner ranges as it did this proxy
(`FD00:91-97`). The first run is a probe, and a 403 is a row, not a crash.

## What would change my mind

1. The probe shows persistent 403 from GitHub runners → the runner moves to the Pi (deploy key +
   `ReadWritePaths`); the slice and schema stand.
2. `hdr.sgml` is missing for >5% of 2019+ accessions → header source becomes the first 64 KB of the
   `.txt` submission (20× download, same committed bytes).
3. Measured rows/yr exceed 2× the estimate or a row exceeds 2 KB → drop `issuer_name`/role names,
   or gzip monthly shards.
4. The skeptic shows a blocked study startable with *less* — e.g. Financial Statement Data Sets
   hashes alone for H51. My counter: FD-NUM still needs this slice's acceptance clock to be
   point-in-time; if that is wrong, the slices re-order.
5. Idle disablement or push failures produce gaps; until `verify` reports missing `seal` days,
   S1/S2 may not claim census coverage.
