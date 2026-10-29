# The EDGAR ledger — schema, invariants, pre-registered questions, operation

Written 2026-10-29, BEFORE any row existed (the `docs/TONE_LEDGER.md` discipline: a gate
chosen after peeking is not a gate). The design was settled by a two-round decision debate
whose record is [`docs/research/EDGAR_LEDGER_QUESTION.md`](research/EDGAR_LEDGER_QUESTION.md);
the code is `src/research/edgar_ledger.py`, the command line `tools/edgar_ledger.py`, the
job `.github/workflows/edgar-ledger.yml`. This file is copied to the `edgar-ledger` branch as
its README when the branch is created.

## Why it exists

Six queued studies are `BLOCKED_ON_DATA` because the research sandbox cannot reach sec.gov
and nothing committed substitutes for it. FD-00 ruled: build the accession-scoped,
append-only ledger before any model. SEC filings are public-domain, so — unlike the Yahoo
and CEFConnect panels — a content-addressed corpus of them **can** be committed. This is the
smallest honest start: metadata and hashes, never a filing body.

## Where it lives

The **`edgar-ledger` git branch**, written only by the `edgar-ledger` GitHub workflow where
EDGAR is reachable. The Pi is not a pusher (`TONE_LEDGER.md`); the sandbox cannot fetch.
Layout:

```
README.md                                 editable   this file, copied at bootstrap
data/edgar_ledger/rows/YYYY-MM.jsonl      prefix     filing | revision | seal rows, by index day
data/edgar_ledger/inputs/YYYY-MM.jsonl    prefix     one line per fetched URL, by fetch month
data/edgar_ledger/probe/PROBE-<utc>-run<N>.jsonl   identical   the Step-0 probe
data/edgar_ledger/fsds/sub-YYYYqN.jsonl.gz         identical   FSDS sub.txt extracts
```

`prefix` = the file may only grow; `identical` = it may never change; both are enforced by
`trials.verify_history` (the same primitive as the trial ledger) and checked by
`tools/edgar_ledger.py verify --against origin/edgar-ledger` **before every push**. In CI
the clone is depth-1, so "every commit present in the checkout" is one commit: the working
tree against the fetched tip — exactly "this run only appended". A reviewer's full clone
walks every commit.

Growth, computed before the shape was chosen: ~30k allowlisted accessions a year at ~1 KB a
row ≈ 30 MB raw, 5–6 MB git-packed, forward-only (no 2019+ backfill in v1: that would add
≈38 MB to a 49 MB pack and is deferred until the probe shows FSDS coverage is insufficient).
The FSDS extracts are ≈1.2 MB raw a quarter, ≈15 MB gz for 70 quarters (**to be measured** on
the probe zip — above 3 MB gz for one quarter, the slice stores a per-row subset or moves to
a sibling data repo). A default clone fetches every branch's objects; contributors who want
the code alone use `git clone --single-branch --branch development`. If the pack passes
150 MiB, a sibling data repo is decided.

## What is stored, and what is not

No filing body. No raw index bytes. No raw header bytes. Every row names the public URL it
read and the sha-256 of the bytes it saw, so anyone can re-fetch and re-hash (the FD-00A
manifest rule: URL, time, bytes, sha-256 for every input).

Header fields are **whitelisted**: acceptance datetime, filed-as-of date, date-as-of-change,
conformed period, submission type, PRIVATE-TO-PUBLIC and PUBLIC-REL-DATE, and the role
blocks' CIK, conformed name and SIC code. A **denylist** the verifier enforces on every key
of every row names what must never appear: `BUSINESS ADDRESS`, `MAIL ADDRESS`, `STREET 1/2`,
`CITY`, `STATE`, `ZIP`, `BUSINESS PHONE`, `IRS NUMBER`, and FSDS `ein`, `*ba`, `*ma`.

## Rows

### `filing` (and `revision`)

| field | meaning |
|---|---|
| `kind`, `ledger_version`, `parser_version` | `filing` or `revision`; schema 1; `edgar_ledger.v1` |
| `accession` | from the index path; the unit everywhere (the index emits one row per filer CIK) |
| `submitter_cik_prefix` | the accession's first ten digits: a filing agent, **never identity** |
| `issuer_cik`, `issuer_name`, `sic` | the FIRST `FILER` block of the header |
| `co_registrant_ciks[]` | every further `FILER` block (co-registrant 10-Ks); pairing is on the primary |
| `roles[]` | every header block: `{role, cik, name, sic}` (filer, subject_company, filed_by, ...) |
| `form`, `form_base`, `is_amendment` | `10-K/A` → `10-K`, true |
| `filed`, `period`, `date_as_of_change` | header dates, ISO |
| `accepted_raw` | `<ACCEPTANCE-DATETIME>` as displayed, `YYYY-MM-DD HH:MM:SS`, ET |
| `tz_rule`, `accepted_at_utc` | `America/New_York#v1`; the UTC instant of `accepted_raw` |
| `dissemination_kind`, `public_release_date` | `PUBLIC` or `PRIVATE-TO-PUBLIC`; `PUBLIC-REL-DATE` |
| `clock_class` | `second` \| `legacy_midnight_display` \| `not_public_event_time` \| null — the FD-00 fixture enum, nothing else |
| `market_phase`, `tradable_policy_daily`, `tradable_session`, `quality_flags[]` | `tradable_time`'s outputs (below) |
| `idx_source`, `idx_sha256` | the index URL and the sha-256 of its bytes |
| `hdr_source`, `hdr_sha256`, `hdr_bytes`, `fetched_at` | `hdr_sgml` or `txt_range` (decided by the probe, recorded per row); the sha-256 of the bytes fetched |
| `revision_id`, `index_day`, `run_id` | 0 for the filing row; the ET day whose index listed it; the run |
| `supersedes_hdr_sha256`, `revision_kind` | revision rows only: `header_changed` or `removed_from_index` |

A **correction is a new row.** A re-seen accession whose header bytes hash differently gets a
`revision` row naming the sha it supersedes; an identical hash appends nothing; an accession
that vanishes from the rebuilt quarterly index gets a `removed_from_index` revision. Rows are
never edited.

### `seal`

One per processed ET business day, written after its rows:
`{day, idx_rows, accessions, hdr_ok, hdr_failed, complete, run_id, hdr_source, idx_sha256,
lines_sha256, at_utc}`. `complete` is true only when every allowlisted accession in that
day's index has a header row; `lines_sha256` hashes the day's filing/revision lines present
when the seal was written. A day re-run after a partial seal gets a new seal; the last one
counts.

### `input`

One per request: `{url, status, bytes, sha256, fetched_at, run_id, purpose, range}`. Every
`idx_sha256` and `hdr_sha256` a row cites must have an inputs line (invariant 5).

## The clock — `tradable_time` (PT-01's one function)

FD-00's historical daily default, all in `America/New_York`:

* **`second`**: the first regular-session open strictly after acceptance; a premarket
  acceptance (before 09:30 ET on a session day) trades at that day's open. 09:30–16:00 →
  `regular_session`; 16:00–17:30 → `after_regular_close`; from 17:30 → `late_evening`
  (`late_evening_friday` on a Friday). The EDGAR filing-date rollover is bracketed in
  (17:30:14, 17:47:43] (F163): `filed` is read from the header, never inferred, and
  `filing_date_rollover` is flagged when it differs from the acceptance date.
* **`legacy_midnight_display`** (`00:00:00`): not an acceptance time. Policy: next
  regular-session open after the filing date; intraday ineligible.
* **`not_public_event_time`** (PRIVATE-TO-PUBLIC): the original acceptance must not be used;
  the policy follows the public release date, date-only (`public_time_date_only`).

Flags: `filing_date_rollover`, `weekend_boundary`, `holiday_boundary`, `after_regular_close`,
`amendment`, `private_to_public`, `public_time_date_only`, `legacy_time_unresolved`,
`acceptance_missing`, `third_party_filer_or_agent_accession`. The eight FD-00 fixtures
(`docs/research/data/fd00_sec_event_clock_fixtures_2026.json`) run through the production
parser in `tests/test_edgar_ledger.py`; the verifier recomputes the clock from the stored
fields and refuses a row whose stored clock differs (FD00:279).

## Invariants (`tools/edgar_ledger.py verify`, exit 1 on any)

1. History: `rows/`, `inputs/` prefix-only; `probe/`, `fsds/` identical; README editable.
2. `(accession, revision_id)` unique; the `filing` row precedes its revisions; no edits.
3. The clock recomputed from `accepted_raw` + `filed` + `tz_rule` equals the stored clock.
4. No filing body: exactly the schema's keys, no denylisted key, every row under 4 KiB.
5. Each day's seal hashes that day's lines; every cited sha-256 has an inputs line.
6. A probe file holds exactly one `probe_summary`; an FSDS file only whitelisted columns.

## Fail-closed gates

* **Bootstrap.** The first workflow run creates the branch with this README and nothing else
  (the one permitted pre-probe write) and verifies shards only — `verify --against` cannot
  resolve a merge-base for a branch that does not exist yet. From the second run `--against
  origin/edgar-ledger` is mandatory and a failure fails the job before the push.
* **Probe before data.** `daily` and `fsds` refuse until a COMMITTED `probe_summary` with
  P0 = PASS and `hdr_source ∈ {hdr_sgml, txt_range}` is on the branch. `daily` exits 0 with
  a `::warning::` (so the schedule stays green) and `verify --report-gaps` counts the
  probe-less weekdays; `fsds` exits 2.
* **Resume.** `daily` processes every ET weekday after the last `seal{complete: true}`, capped
  at 10 a run; the remainder rolls forward and is reported. A partial day is re-run: only
  accessions without a row are fetched; only new `(accession, hdr_sha256)` pairs are appended.
* **Freeze.** `freeze --from --to` enumerates every ET weekday in the window and refuses one
  with **no seal**, an incomplete seal, or `hdr_ok/accessions < 0.95` (the FD00:265-267 gate)
  unless `--allow-partial`, which is written into the manifest beside `partial_days[]` and
  `missing_seal_days[]` — lists, not a boolean. The extract is `EDGARLEDGER-<sha>.csv.gz` in
  `docs/research/data/` through `data_store.write` (public: SEC is not a restricted vendor);
  a study cites the sha, never the branch. FSDS extracts freeze as `EDGARFSDS-<sha>.csv.gz`.
* **Fair access.** `SEC_USER_AGENT` must carry an `@` at a non-reserved domain (RFC 2606
  `example.com/.org/.net`, `.test`, `.invalid`, `.localhost` are refused: the pattern's own
  placeholder cannot leak into a run). Requests are spaced ≥ 0.25 s (≤ 4/s against the SEC's
  10/s cap); 429/5xx retry with bounded backoff (1, 2, 4 s, three retries); 403/429 are
  recorded and end the run (P0).

## Step 0 — the probe (`mode=probe quarter=2024Q1 n=500`)

Fetches one quarterly `form.idx`, a deterministic sample of 500 allowlisted accessions ranked
by `sha256("MONAD-EDGAR-PROBE-v1|<accession>")`, each one's `<accession>.hdr.sgml` (falling
back to a 64 KiB `Range` of the `.txt` submission), and one FSDS quarterly zip — streamed,
measured, discarded. No header text is stored. One frozen file with `probe_request`,
`probe_header`, `probe_fsds` rows and one `probe_summary`:

* **P0 runner:** zero 403/429 across all requests. Any → `FAIL_RUNNER`: the runner question
  moves to the Pi (deploy key + `ReadWritePaths`); nothing else changes.
* **P1 header:** `hdr.sgml` 200 on ≥ 95% of the sample with a 14-digit acceptance and ≥ 1
  FILER block on ≥ 99% of those → `hdr_source = hdr_sgml` (verdict `PASS`); else the same
  thresholds on the `.txt` range → `txt_range` (`PASS_TXT_RANGE`); else `FAIL_HEADER` (slice 2
  is redesigned, not scheduled).
* **P2 FSDS:** zip 200, `sub.txt` present, columns ⊇ {adsh, cik, form, period, filed,
  accepted, prevrpt, nciks, aciks, afs, fy, fp, sic}, `accepted` to the second on ≥ 99% →
  FSDS is slice 1. **Coverage decides its role, on ORIGINAL 10-K/10-Q accessions only:** ≥ 95%
  of the sample's originals found by `adsh` → FSDS is also the S1′ frame
  (`facts_and_s1prime_frame`); below → facts only and S1′ waits for a header backfill.
  10-K/A and 10-Q/A coverage is reported and scopes H52-lite; it never gates. Accessions
  filed in the quarter's first or last two business days are excluded from every
  denominator (a zip quarter and an index quarter can straddle a rollover).

## Slices

1. **FSDS `sub.txt` extract** (if P2 passes): one dispatch per quarter, 2009Q2 → current. The
   zip is not committed (one inputs line: URL, bytes, sha-256, time, status); the extract
   holds the allowlisted forms (10-KT/10-QT kept and flagged) and whitelisted columns `adsh,
   cik, name, former, changed, sic, afs, fye, form, period, fy, fp, filed, accepted, prevrpt,
   nciks, aciks, instance` plus the derived clock fields. Tier: filing-specific extracted XBRL
   (FD00:221), labelled derived. `num.txt` target facts for H51 are a later extract.
2. **Daily header ledger** (if P1 passes): forward-only from the first passing probe; the
   monthly `sweep` appends revisions against the rebuilt quarterly index. FSDS cannot replace
   it: FSDS holds XBRL-bearing submissions only, so it is not FD-00's population frame (all
   10-K/10-Q/A, including non-XBRL Part III and exhibit-only amendments) and gives no
   first-seen, `DATE AS OF CHANGE`, PRIVATE-TO-PUBLIC or role blocks.
3. 8-K + `ITEM INFORMATION`; `num.txt` target facts (H51).

## Pre-registered questions — two tests, one gate, one calibration

Clocks, all ET: `tradable` = `tradable_time` above. Naive **A** = open of the `filed` session
(next session if `filed` is not one). Naive **B** = open of the first session after `filed`.

* **S1′ leak/lag — a CALIBRATION MEASUREMENT, outside the hypothesis error-rate count.**
  Leak share = rows with A < `tradable`; lag share = A > `tradable`; staleness(B) = sessions
  from `tradable` to B. By construction every after-close acceptance with same-day `filed`
  leaks under A, and after-close is the dominant window, so "leak ≥ 5%" is expected to fire;
  the measurement fixes FD-01's clock with a leak magnitude attached. Rules: leak share ≥ 5% →
  `filed` is banned as FD-01's event clock; < 5% → A permitted with the leak share attached;
  B permitted iff median staleness ≤ 1 session. By form-year; firm-clustered Wilson intervals.
* **H-SIZE — a test.** Rollover share (acceptance after 17:30 ET) for `afs ∈ {3,4,5}` is
  ≥ 2× that for `afs = 1`, 2012Q1 onward (XBRL phase-in ended 2011; the `afs` codes are
  strings like `1-LAF` … `5-SML`, to be probed). Kill: ratio < 1.25. **Gray zone: ratio in
  [1.25, 2) → inconclusive, reported.**
* **F163 replication — a test.** Among acceptances in (17:30:00, 17:47:43], the share with
  same-day `filed` is reported; among acceptances after 17:47:43, same-day share < 0.5%. Kill:
  ≥ 2%. **Gray zone: [0.5%, 2%) → inconclusive.**
* **H52-lite — a gate, not a test.** `prevrpt` share by form-year and `afs`; XBRL-bearing
  amendments paired to originals by `(cik, period, form_base)`; pair rate gate ≥ 90%
  (FD00:273). The Part III hypothesis (≥ 25% of 10-K/A lags in [100, 135] days after FYE)
  moves to slice 2, because non-XBRL amendments are absent from FSDS (to be probed via the
  probe's 10-K/A coverage).

## Outside the sandbox — what the operator does

1. **Add the secret.** Repository → Settings → Secrets and variables → Actions →
   `SEC_USER_AGENT` = `MONAD research <a real address you read>`. A reserved-domain or
   `@`-less value fails every fetching run at its first request.
2. **Create the branch.** Either wait for the 07:17 UTC schedule or dispatch the workflow
   once (any mode): the first run writes the README-only `edgar-ledger` branch and stops.
3. **Dispatch `mode=probe`, `quarter=2024Q1`, `n=500`.** Read `probe_summary` in
   `data/edgar_ledger/probe/PROBE-*.jsonl` on the branch (or the job log's one-line summary):
   `verdict`, `hdr_source`, `p2.fsds_role`, `p2.coverage_originals`, `p2.coverage_amendments`,
   `p2.extract_gz_bytes`. `FAIL_RUNNER` → the runner moves to the Pi; `FAIL_HEADER` → slice 2
   is redesigned; `PASS`/`PASS_TXT_RANGE` → go on.
4. **Dispatch `mode=fsds`, `quarter=2024Q1`** (if `p2.fsds_slice`), then further quarters.
5. **Let the schedule run.** `daily` now writes rows; `verify --report-gaps` in each run's
   log lists missing or partial days. Dispatch `mode=sweep quarter=<trailing>` monthly.
6. **Freeze for a study** (locally, with the branch checked out beside the repo):
   `tools/edgar_ledger.py --ledger <clone>/data/edgar_ledger freeze --from D --to D`, commit
   the `EDGARLEDGER-<sha>.*` pair under `docs/research/data/`, cite the sha.
