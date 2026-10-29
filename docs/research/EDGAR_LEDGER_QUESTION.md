# Open question: what is the smallest honest start of the EDGAR ledger, and where does it run?

**Status:** decided by decision debate 2026-10-29 (`/decision-debate`, one proposer, one
skeptic, two rounds: DISPUTE, then CONCUR conditional on five fixes adopted verbatim). This is
direction D-2 of `docs/DIRECTIONS.md`. The operator's doc is
[`docs/EDGAR_LEDGER.md`](../EDGAR_LEDGER.md); the code is `src/research/edgar_ledger.py`,
`tools/edgar_ledger.py`, `.github/workflows/edgar-ledger.yml`.

## Why it is open

Six queued studies (H46, H48, H49, H51, H52, H53) are `BLOCKED_ON_DATA`: the sandbox proxy
refuses sec.gov and data.sec.gov, and nothing committed substitutes. FD-00
(`FD00_sec_filing_delta_lab.md`) ruled that the accession-scoped, append-only ledger comes
before any model; the frontier orders FD-00 backfill → FD-01 → RN-01. SEC filings are
public-domain (`DATA_REDISTRIBUTION_AUDIT.md`; SEC is absent from `RESTRICTED_VENDORS`), so,
unlike Yahoo, a content-addressed corpus can be committed. The repo already has the pattern
(the `tone-ledger` branch written by `pages.yml`), the verifier (`trials.verify_history`),
and the clock fixtures (`fd00_sec_event_clock_fixtures_2026.json`) — but no fetcher has ever
read a `.hdr.sgml`, PT-01's "one function" `tradable_time` did not exist, and four SEC
fetchers space requests at 0.12 s with one shipping a placeholder `example.com` contact.

## Options

| Option | What it is | Cost / risk |
|---|---|---|
| A. Daily header ledger first | `form.idx` rows for 10-K/10-Q(/A) enriched by `<accession>.hdr.sgml`; ~30k fetches/yr | `hdr.sgml` untested; 2019+ backfill +38 MB on a 49 MB pack; holes permanent without resume |
| B. FSDS first | one Financial Statement Data Sets zip per quarter (~70 downloads) → `sub.txt` with `accepted` to the second, `prevrpt`, `afs` | XBRL-bearing submissions only: not FD-00's population frame; no first-seen, no `DATE AS OF CHANGE`, no PRIVATE-TO-PUBLIC, no role blocks |
| C. Probe → FSDS → header ledger | one dispatch measures the runner, the header source and FSDS coverage; FSDS slice conditional on P2; header ledger forward-only, conditional on P1 | an extra dispatch before any data; the first scheduled run writes only a README |
| D. Run it on the Pi | deploy key + `ReadWritePaths` | `TONE_LEDGER.md:21-22`: the Pi is not a pusher until deliberately extended; it hosts the live trader |

## Decision-debate consensus (2026-10-29)

**Decision: option C**, a separate `edgar-ledger` workflow writing the `edgar-ledger` branch,
fail-closed at three gates (bootstrap, probe, verify-before-push).

### The agreed design

- **Step 0 — probe** (`workflow_dispatch mode=probe quarter=2024Q1 n=500`): one quarterly
  `form.idx`; a deterministic sample of 500 allowlisted accessions (ranked by
  `sha256("MONAD-EDGAR-PROBE-v1|<accession>")`); for each, `hdr.sgml` (status, bytes,
  sha-256, 14-digit acceptance, FILER blocks, filed-as-of date), falling back to a 64 KiB
  `Range` of the `.txt`; one FSDS zip streamed and measured (members, `sub.txt` columns, row
  count, acceptance precision, `prevrpt` values, form counts, coverage of the sample by
  `adsh`). No header text stored. One frozen `probe/PROBE-<utc>-run<N>.jsonl`.
  - **P0 runner:** zero 403/429 → else `FAIL_RUNNER` (runner moves to the Pi; nothing else changes).
  - **P1 header:** `hdr.sgml` 200 ≥ 95% with acceptance + FILER block ≥ 99% of those →
    `hdr_source=hdr_sgml`; else the same on the `.txt` range → `txt_range`; else `FAIL_HEADER`.
  - **P2 FSDS:** zip 200, `sub.txt` columns ⊇ {adsh, cik, form, period, filed, accepted,
    prevrpt, nciks, aciks, afs, fy, fp, sic}, `accepted` second-precision ≥ 99% → FSDS is
    slice 1; coverage of **original** 10-K/10-Q accessions ≥ 95% → FSDS is also the S1′
    frame, else facts only.
- **Slice 1 — FSDS `sub.txt` extract** (if P2): one dispatch per quarter; zip not committed
  (one `inputs` line); `fsds/sub-YYYYqN.jsonl.gz` with allowlisted forms, whitelisted
  columns, derived clock fields; tier "filing-specific extracted XBRL", labelled derived.
- **Slice 2 — daily header ledger** (if P1), forward-only, 07:17 UTC: `rows/YYYY-MM.jsonl`
  (`filing | revision | seal`) and `inputs/YYYY-MM.jsonl`, both prefix-only; `clock_class` =
  the fixture enum; `issuer_cik` = first FILER block + `co_registrant_ciks[]`; `hdr_source`
  per row; seals `{day, idx_rows, accessions, hdr_ok, hdr_failed, complete, run_id}`; resume
  from the last complete seal, capped at 10 days a run; monthly `sweep` appends revisions
  against the rebuilt quarterly index. No 2019+ backfill in v1.
- **Slice 3** — 8-K + `ITEM INFORMATION`; `num.txt` target facts (H51).
- **Storage honesty (O3):** the refspec fetches every branch, so the branch is not "free":
  ≈15 MB gz for 70 FSDS quarters (to be measured), ≈5–6 MB/yr packed for the daily ledger;
  document `git clone --single-branch --branch development`; a sibling data repo if the pack
  passes 150 MiB.
- **Guard (O4):** `tests/test_edgar_ledger_workflow.py` — `permissions` exactly
  `contents: write`, every `git push` names `edgar-ledger`, no `push origin development`, no
  `push:` trigger, `concurrency: edgar-ledger`, no yfinance; branch protection on
  `development` is the barrier, not the token. No CI storm: `test.yml` fires on
  `[main, development, claude/**, fix-**]` only.
- **Personal data (O8):** whitelisted header fields; denylist `BUSINESS ADDRESS`,
  `MAIL ADDRESS`, `STREET 1/2`, `CITY`, `STATE`, `ZIP`, `BUSINESS PHONE`, `IRS NUMBER`, FSDS
  `ein`, `*ba`, `*ma`; the verifier rejects any key outside the schema.
- **Fair access (1d):** 0.25 s spacing with bounded backoff; the UA guard refuses a contact at
  an RFC 2606 reserved domain; `bdc_text_nav.py`'s hint becomes `'name you@your-domain'`.
- **Depth-1 clones (1c):** the CI gate `verify --against origin/edgar-ledger` compares the
  working tree with the one fetched commit — exactly "this run only appended"; a reviewer's
  full clone walks every commit.

### The five conditions (skeptic round 2, adopted verbatim)

1. **Bootstrap path.** The branch-creating run is README-only (a copy of `docs/EDGAR_LEDGER.md`)
   and runs shard checks with **no** `verify --against`: `trials.verify_history` cannot
   resolve a merge-base for a branch that does not exist yet (verified here: `["cannot
   resolve merge-base with 'origin/edgar-ledger': ..."]`). The README is the one permitted
   pre-probe write. `--against` is mandatory from the second run. Tested offline in
   `tests/test_edgar_ledger_workflow.py` by running the workflow's own shell against a local
   bare repository.
2. **Freeze refuses absent days.** `freeze` enumerates every ET weekday in `[from, to]` and
   refuses any with no seal row, an incomplete seal, or `hdr_ok/accessions < 0.95` unless
   `--allow-partial`; the manifest lists `partial_days[]` and `missing_seal_days[]`, not a
   boolean.
3. **Coverage rule scoped to originals.** The 95% FSDS coverage gate applies to 10-K and 10-Q
   only; 10-K/A and 10-Q/A coverage is reported and scopes H52-lite, never gating the S1′
   frame. Accessions filed in the quarter's first or last two business days are excluded
   from every denominator.
4. **S1′ is a calibration measurement**, outside the hypothesis error-rate count (it fires by
   construction: every after-close acceptance with same-day `filed` leaks under naive clock A).
5. **Gray-zone verdicts.** H-SIZE: ratio in [1.25, 2) → inconclusive, reported. F163
   replication: same-day share in [0.5%, 2%) → inconclusive.

Wording fixes adopted: the 90% same-form pair-rate gate is **FD00:273**; "the daily job writes
nothing but the bootstrap README until the probe passes"; "`verify --against` fails the job
from the second run; the bootstrap run verifies shards only"; the pre-registration header
reads "two tests (H-SIZE, F163), one gate (H52-lite), one calibration (S1′)".

Minor, also adopted: `daily` without a passing probe exits 0 with a `::warning::` and
`verify --report-gaps` counts probe-less weekdays.

## Pre-registrations (written before any row exists)

Clocks, all `America/New_York`: `tradable` = `tradable_time` (first regular-session open
strictly after acceptance; premarket on a session day → that day's open; FD00:127). Naive
**A** = open of the `filed` session (next session if `filed` is not one). Naive **B** = open
of the first session after `filed`.

| | Kind | Statistic | Rule | Kill / gray zone |
|---|---|---|---|---|
| **S1′ leak/lag** | **calibration** (not counted) | leak share = A < `tradable`; lag share = A > `tradable`; staleness(B) in sessions; by form-year, firm-clustered Wilson | leak ≥ 5% → `filed` banned as FD-01's clock; < 5% → A permitted with the share attached; B permitted iff median staleness ≤ 1 | — (fires by construction) |
| **H-SIZE** | test | rollover share (acceptance after 17:30 ET), `afs ∈ {3,4,5}` vs `afs = 1`, 2012Q1 onward | ratio ≥ 2 confirms | kill < 1.25; **[1.25, 2) inconclusive, reported** |
| **F163 replication** | test | among acceptances in (17:30:00, 17:47:43], same-day `filed` share (reported); after 17:47:43, same-day share | < 0.5% confirms | kill ≥ 2%; **[0.5%, 2%) inconclusive** |
| **H52-lite** | gate | `prevrpt` share by form-year and `afs`; amendments paired to originals by `(cik, period, form_base)` | pair rate ≥ 90% (FD00:273) | the Part III hypothesis (≥ 25% of 10-K/A lags in [100, 135] days after FYE) moves to slice 2 |

## What would change the decision

1. P0 fails from GitHub runners → the Pi runs the same tool; design unchanged.
2. P2 shows `accepted` absent or date-only → FSDS gives facts only; S1′/H-SIZE/F163 move to
   the header backfill and O3's +38 MB becomes necessary, stated as such.
3. FSDS coverage of the sample's original 10-K/10-Q accessions < 95% → FSDS is not the S1′ frame.
4. A probe-quarter `sub.txt` extract above 3 MB gz → a per-row subset, or a sibling data repo
   from the start.
5. A showing that the daily header ledger is unnecessary once FSDS exists — that first-seen,
   `DATE AS OF CHANGE`, private-to-public and non-XBRL amendments are needed by none of the six
   blocked studies — drops slice 2 rather than deferring it.

## Outside the sandbox

Everything here was built and tested on fixtures; sec.gov is unreachable from the sandbox, so
the first real fetch happens on GitHub Actions. The operator: adds the `SEC_USER_AGENT` secret
(a real contact), lets the first run create the README-only branch (or dispatches once),
dispatches `mode=probe quarter=2024Q1 n=500`, reads `probe_summary`, dispatches
`mode=fsds quarter=2024Q1`, and lets the 07:17 UTC schedule run `daily`. Step-by-step in
[`docs/EDGAR_LEDGER.md`](../EDGAR_LEDGER.md), "Outside the sandbox".
