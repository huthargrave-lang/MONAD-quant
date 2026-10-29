# EDGAR ledger — revised proposal (round 2)

**Role:** proposer. **Answers:** `debate_edgar_ledger_skeptic_r1.md` (DISPUTE). sec.gov is unreachable
here; every SEC-format claim below that the repo does not already witness is marked **to be probed**.

## Round 2 responses

| Item | Verdict | What changes |
|---|---|---|
| **O1** `hdr.sgml` untested | **ACCEPT** | The repo has zero `hdr.sgml` references; the only acceptance parser reads `<ACCEPTANCE-DATETIME>(\d{14})` from the `.txt` submission (`sec_form25_population_lab.py:391-396`). Step 0 is a probe dispatch, defined below; `daily` mode refuses to run until a committed `probe_summary` passes (enforced in code, tested offline). `hdr_source ∈ {hdr_sgml, txt_range}` is decided by the probe and recorded per row. |
| **O2** holes are permanent | **ACCEPT** | `daily` processes every ET business day after the last `seal{complete:true}` (capped at 10 days/run; the remainder rolls forward and `verify --report-gaps` lists it). Seal row: `{day, idx_rows, accessions, hdr_ok, hdr_failed, complete, run_id}`; `complete` is true only when every allowlisted accession in that day's index has an `hdr_ok` row. Re-running a day appends only rows whose `(accession, hdr_sha256)` is new. `freeze` refuses any day with `complete=false` or `hdr_ok/accessions < 0.95` unless `--allow-partial`, which is written into the manifest (`FD00:265-267` in code). |
| **O3** "nobody clones" false | **ACCEPT** | `.git/config` refspec is `+refs/heads/*:refs/remotes/origin/*`; `git ls-remote --heads` shows 50 heads (21 `claude/*`); pack 49.22 MiB. Revised numbers: FSDS slice ≈ +15 MB gz (to be measured on the probe zip); daily header ledger forward-only ≈ +5–6 MB/yr; the 2019+ header backfill (+~38 MB, +77%) is **deferred** and only runs if the probe shows FSDS coverage is insufficient (below). Document `git clone --single-branch --branch development`; a sibling data repo is decided if the pack passes 150 MiB. |
| **O4** unguarded second workflow | **ACCEPT** | Sibling test `tests/test_edgar_ledger_workflow.py` mirroring `tests/test_export_pages.py:298-314`: every `git push` names `edgar-ledger`; no `push origin development`; `permissions` is exactly `contents: write`; no `push:` trigger; concurrency group `edgar-ledger`. Documented: branch protection on `development` is the barrier, not the token. No CI storm: `test.yml:4-5` fires on `[main, development, claude/**, fix-**]`, `pages.yml:48-50` on `workflow_run`/schedule/dispatch. |
| **O5** `clock_class` enum | **ACCEPT** | `clock_class` = fixture `acceptance_time_quality` ∈ {`second`, `legacy_midnight_display`, `not_public_event_time`} or null; `public_time_date_only` is a `quality_flags[]` entry. Test 1 asserts quality only where the fixture gives one, `market_phase` and policy for all seven. |
| **O6** S1 is a census | **ACCEPT**, definitions made explicit | S1 is replaced by S1′ (leak/lag under two naive clocks, 5% rule), H-SIZE (by `afs`), and the F163 replication — all pre-registered below. Conceded: after-close is the dominant window, so "LB ≥ 1%" was certain to fire. |
| **O7** co-registrants | **ACCEPT** | `issuer_cik` = first FILER block, `co_registrant_ciks[]` = the rest (FSDS: `cik` + `aciks`, to be probed). S2 pairs on the primary and reports the co-registrant share. `form.idx` emits one row per filer CIK, so accessions, not rows, are the unit everywhere. |
| **O8** header personal data | **ACCEPT** | Denylist, by key: `BUSINESS ADDRESS`, `MAIL ADDRESS`, `STREET 1/2`, `CITY`, `STATE`, `ZIP`, `BUSINESS PHONE`, `IRS NUMBER`, and FSDS `ein`, `*ba`, `*ma` columns. The parser whitelists fields; the verifier rejects any key outside the schema. |
| **Slice order** | **ACCEPT with a stated variant** | My round-1 counter ("FD-NUM still needs this slice's clock") is wrong **if** FSDS `sub.txt` carries `accepted` to the second — a claim the repo cannot witness (`FD00:68` names FSDS; the `adsh` hits in `tools/*_lab.py` are the full-text-search API). So: probe → FSDS → daily header ledger, with the FSDS step **conditional on probe facts**, and a narrow rebuttal: FSDS covers XBRL-bearing submissions only, so it cannot be FD-00's population frame (`FD00:238-243` wants *all* 10-K/10-Q/A, including non-XBRL Part III and exhibit-only amendments) and cannot give first-seen, `DATE AS OF CHANGE`, PRIVATE-TO-PUBLIC or role blocks. The probe measures FSDS coverage of the 10-K/10-Q population directly; the header ledger stays as the forward point-in-time frame. |
| **1c** depth-1 clone | **ACCEPT** | In CI the push gate is `verify --against origin/edgar-ledger` on a depth-1 clone: working tree vs the one fetched commit, which is exactly "this run only appended". The full `_branch_walk` is for a reviewer's full clone; the README says so. |
| **1d** `bdc_text_nav` | **ACCEPT** | All **four** SEC fetchers space at 0.12 s (`bdc_text_nav.py:36` included). The ledger guard refuses a contact at an RFC 2606 reserved domain (`example.com/.org/.net`); `bdc_text_nav.py:55`'s hint becomes `'name you@your-domain'` in the same change. |
| Wording | **ACCEPT** | `docs/research/data/README.md`; `pages.yml` bootstrap `:100-113`, push `:134-146` (the file was rewritten at `10d9437`, 17:21 today, after my read); "every commit present in the checkout". |

## Revised slice order

### Step 0 — probe (one `workflow_dispatch`, `mode=probe quarter=2024Q1 n=500`)

Fetches, in order, with `SEC_USER_AGENT` from the repository secret and 0.25 s spacing:
1. `full-index/2024/QTR1/form.idx` (one request) → allowlist rows grouped by accession.
2. A deterministic sample of 500 accessions ranked by `sha256("MONAD-EDGAR-PROBE-v1|<accession>")`
   (the `deterministic_sample` rule, `sec_form25_population_lab.py:243-262`). For each: GET
   `<accession>.hdr.sgml` (status, bytes, sha256, `has_14digit_acceptance`, `filer_blocks`,
   `has_filed_as_of_date`); on non-200, GET the `.txt` submission with `Range: bytes=0-65535`
   (status 206/200, bytes received, same three parse facts). **No header text is stored.**
3. One FSDS quarterly zip — primary URL `files/dera/data/financial-statement-data-sets/2024q1.zip`,
   **to be probed** — streamed, not committed: status, `Content-Length`, sha256, member names and
   sizes, `sub.txt`'s observed header columns, row count, share of rows whose `accepted` matches
   `\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}`, distinct `prevrpt` values, form distribution, and
   **coverage** = share of the 500 probe accessions present in `sub.txt` by `adsh`, split by form.

Writes one frozen file `data/edgar_ledger/probe/PROBE-<utc>-run<N>.jsonl` (`identical` rule) with
`probe_request`, `probe_header`, `probe_fsds` and one `probe_summary` row. **Pass** means:
- **P0 runner:** zero 403/429 across all requests. Any → `FAIL_RUNNER` → the runner question moves
  to the Pi (deploy key + `ReadWritePaths`); nothing else changes.
- **P1 header:** `hdr.sgml` 200 on ≥ 95% with 14-digit acceptance and ≥ 1 FILER block on ≥ 99% of
  those → `hdr_source=hdr_sgml`; else the same thresholds on the `.txt` range → `hdr_source=txt_range`;
  else `FAIL_HEADER` (slice 2 is redesigned, not scheduled).
- **P2 FSDS:** zip 200, `sub.txt` present, observed columns ⊇ {`adsh, cik, form, period, filed,
  accepted, prevrpt, nciks, aciks, afs, fy, fp, sic`}, `accepted` second-precision ≥ 99% → FSDS
  is slice 1. Coverage decides its role: ≥ 95% of probe 10-K/10-Q accessions found → FSDS is
  also the S1′ frame; < 95% → FSDS is the facts source and S1′ waits for the header backfill.

### Slice 1 — FSDS manifest + `sub.txt` extract (if P2 passes)

One dispatch per 1–4 quarters, 2009Q2 → current (~70 zips, ~60–120 MB each, **not committed**;
one `inputs` row each: url, bytes, sha256, fetched_at, status — `FD00:624-627`). Per quarter one
frozen `data/edgar_ledger/fsds/sub-YYYYqN.jsonl.gz` (`identical` rule) holding allowlisted forms
(10-K, 10-K/A, 10-Q, 10-Q/A; 10-KT/10-QT kept and flagged) with whitelisted columns
`adsh, cik, name, former, changed, sic, afs, fye, form, period, fy, fp, filed, accepted, prevrpt,
nciks, aciks, instance` plus the derived clock fields. ≈ 5–6k rows × ~220 B ≈ 1.2 MB raw/quarter,
≈ 15 MB gz for 70 quarters (**to be measured** on the probe zip). `num.txt` target facts for H51
are a later extract from the same zips, re-fetched by sha; a changed sha is a `revision` row.
Tier: filing-specific extracted XBRL (`FD00:221`), labelled as derived, not raw.

### Slice 2 — daily header ledger (forward-only; if P1 passes)

As round 1, with the O2/O5/O7/O8 changes: `data/edgar_ledger/rows/YYYY-MM.jsonl` and
`inputs/YYYY-MM.jsonl` (`prefix` rule); row kinds `filing | revision | seal`; `seal` carries the O2
fields; `clock_class` is the fixture enum; `issuer_cik` + `co_registrant_ciks[]`; `hdr_source`
per row. No 2019+ backfill in v1. Monthly sweep against the rebuilt quarterly index appends
`revision` rows (`FD00:170-178`). Daily at 07:17 UTC; `daily` exits 0 with "no passing probe"
until a `probe_summary` with `P0=PASS` and `P1∈{hdr_sgml, txt_range}` exists on the branch.

### Slice 3 — 8-K + `ITEM INFORMATION`; `num.txt` target facts (H51).

## Pre-registered questions (written before any row exists)

Clocks, all in `America/New_York`: `tradable` = first regular-session open strictly after
acceptance, except premarket (< 09:30 on a session day) → that day's open (`FD00:127`).
Naive **A** = open of the `filed` session (next session if `filed` is not one). Naive **B** = open
of the first session after `filed`.

- **S1′ leak/lag.** Leak share = rows with A < `tradable`; lag = A > `tradable`; staleness(B) =
  sessions from `tradable` to B. Rules: leak share ≥ 5% → `filed` is banned as FD-01's event
  clock; < 5% → A permitted with the leak share attached; B permitted iff median staleness ≤ 1
  session. By form-year; firm-clustered Wilson intervals.
- **H-SIZE.** Rollover share (acceptance after 17:30 ET) for `afs ∈ {3,4,5}` ≥ 2× that for `afs=1`,
  2012Q1 onward (XBRL phase-in ended 2011; `afs` codes to be probed). Kill: ratio < 1.25.
- **F163 replication.** Among acceptances in (17:30:00, 17:47:43], share with same-day `filed`
  reported; among acceptances after 17:47:43, same-day share < 0.5% (kill: ≥ 2%).
- **H52-lite.** `prevrpt` share by form-year and `afs`; XBRL-bearing amendments paired to originals
  by `(cik, period, form_base)`; pair rate gate ≥ 90% (`FD00:271`). The Part III hypothesis
  (≥ 25% of 10-K/A lags in [100, 135] days after FYE) moves to slice 2, because non-XBRL amendments
  are absent from FSDS (**to be probed** via the probe's coverage split for 10-K/A).

## Implementation plan — executable here without network

1. **`src/research/edgar_ledger.py`** (stdlib + `trials.verify_history`): `parse_form_idx(bytes,
   allowlist) -> {accession: {form, filed, filer_ciks[], path}}` (one entry per accession, all
   filer rows kept); `parse_sgml_header(bytes) -> dict` (whitelisted fields; `ACCEPTANCE-DATETIME`,
   `FILED AS OF DATE`, `DATE AS OF CHANGE`, `CONFORMED PERIOD`, `PRIVATE-TO-PUBLIC`,
   `PUBLIC-REL-DATE`, FILER/SUBJECT blocks → `cik`, `name`, `sic`); `tradable_time(filing) ->
   (clock_class, market_phase, tradable_policy_daily, flags)` — the PT-01 "one function"
   (`PT01_substrate_readiness.md:74, 83`); `parse_fsds_sub(text, required_cols) -> rows`, failing
   closed if a required column is absent; `plan_days(last_complete_seal, today_et, cap=10)`;
   `seal(...)`; `verify_shards(dir)`; `verify_history(base_ref)` with `rows/*.jsonl`,
   `inputs/*.jsonl` → `"prefix"`, `probe/*`, `fsds/*.jsonl.gz` → `"identical"`, README → `None`;
   `freeze(from, to, allow_partial)` writing `EDGARLEDGER-<sha>.csv.gz` via `data_store.write`
   (`data_store.py:327`, public since SEC is not restricted, `:71-73`); `probe_verdict(rows)`
   implementing P0–P2; `user_agent()` with the reserved-domain refusal. All fetches go through one
   `fetch(url, *, get, min_interval=0.25)` with an injectable `get` (the `bdc_text_nav.py:66`
   pattern) so every test is offline.
2. **`tools/edgar_ledger.py`** CLI: `probe`, `fsds`, `daily`, `sweep`, `verify [--against]
   [--report-gaps]`, `freeze`. `daily`/`fsds` refuse without a passing probe on disk.
3. **`tests/test_edgar_ledger.py`**: FD-00 fixtures → synthesized SGML headers → expected
   `market_phase`/policy for all seven, quality where given, eighth contract-only; F163 17:30:14
   same-day case; `form.idx` with two rows per accession → one accession with both CIKs; header
   with two FILER blocks → `issuer_cik` + `co_registrant_ciks`; `PRIVATE-TO-PUBLIC`; denylist keys
   never emitted; re-seen accession with changed sha → `revision`, same sha → nothing; `plan_days`
   resumes from the last complete seal and caps at 10; `freeze` refuses a partial day without
   `--allow-partial` and records it with; append-only in a temp git repo (edit/delete/rewrite
   fail, mirroring `tests/test_trial_ledger.py:358`); `probe_verdict` on synthetic results for
   each of PASS / PASS_TXT_RANGE / FAIL_RUNNER / FAIL_HEADER and the 95% coverage branch;
   `parse_fsds_sub` fails closed on a missing column; UA guard (`example.com`, missing `@`);
   `MIN_INTERVAL ≥ 0.2` pinned.
4. **`tests/test_edgar_ledger_workflow.py`**: the O4 guard.
5. **`.github/workflows/edgar-ledger.yml`**: `schedule: "17 7 * * *"` + `workflow_dispatch`
   inputs `mode`, `quarter`, `n`; `permissions: contents: write`; `concurrency: edgar-ledger`;
   steps: checkout, Python 3.11, clone-or-bootstrap `edgar-ledger` (README from
   `docs/EDGAR_LEDGER.md`, the `pages.yml:100-113` pattern), run the mode with
   `SEC_USER_AGENT: ${{ secrets.SEC_USER_AGENT }}`, `verify --against origin/edgar-ledger`
   (**fails the job, so no push, unlike the tone ledger's `continue-on-error`**), commit and push
   with the `:134-146` rebase-retry.
6. **Docs**: `docs/EDGAR_LEDGER.md` (schema, invariants, the pre-registrations above, written
   before data — the `TONE_LEDGER.md` discipline); a `docs/research/data/README.md` §2 row for
   `EDGARLEDGER-`/`EDGARFSDS-` (SEC, public); `bdc_text_nav.py:55` hint string.
7. **Outside the sandbox (Hudson):** add the `SEC_USER_AGENT` secret (real contact), dispatch
   `mode=probe`, read `probe_summary`, then dispatch `mode=fsds quarter=2024Q1` and let the
   schedule run. The daily job writes nothing until the probe passes.

## What would change my mind

1. P0 fails from GitHub runners → the Pi runs the same tool; design unchanged.
2. P2 shows `accepted` absent or date-only → FSDS gives facts only; S1′/H-SIZE/F163 move to the
   header backfill and O3's +38 MB becomes necessary, stated as such.
3. FSDS coverage of probe 10-K/10-Q accessions < 95% → FSDS is not the S1′ frame (rule above).
4. A probe-quarter `sub.txt` extract above 3 MB gz → the FSDS slice stores a per-row subset or
   lives in a sibling data repo from the start.
5. If the skeptic shows the daily header ledger is unnecessary once FSDS exists — i.e. that
   first-seen, `DATE AS OF CHANGE`, private-to-public and non-XBRL amendments are not needed by
   any of the six blocked studies — slice 2 is dropped, not deferred.
