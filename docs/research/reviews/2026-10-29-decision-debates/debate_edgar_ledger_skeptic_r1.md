# Skeptic, round 1 — EDGAR ledger proposal

**Role:** skeptic. **Reviewed:** `debate_edgar_ledger_proposal.md`. Sandbox cannot reach sec.gov; everything below is checked against committed code and fixtures. Two claims rest on my knowledge of SEC file formats and are marked as such.

## Verification table

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1a | FD00 :238-243 population; :279 clock reproducible from stored fields; :170-178 index rebuild/revision; :85-89 "materially slower than the cap" | **VERIFIED** | all four read as cited |
| 1b | 7 timestamped fixtures; vocabulary {second, legacy_midnight_display, not_public_event_time, date_only} | **PARTLY WRONG** | `docs/research/data/fd00_sec_event_clock_fixtures_2026.json`: 8 fixtures, 7 timestamped. `acceptance_time_quality` ∈ {second, legacy_midnight_display, not_public_event_time, *null*}. `date_only` is **not** a quality value; it occurs once, as the flag `public_time_date_only` (:167). `accession_prefix_not_issuer_cik` is timestamped but has **no** expected quality |
| 1c | `trials.verify_history` reusable for a non-trial store | **VERIFIED** | `src/research/trials.py:920-956`: signature `(base_ref, rel_dir, *, rule, repo, what)`; no TR-/family assumptions; already reused by admit, prereg, reeval, refutations, forward_watch. Caveat: `_branch_walk` sees only commits in the clone; `pages.yml:104` clones the ledger `--depth 1`, so in CI "every branch commit" is one commit |
| 1d | UA/spacing | **VERIFIED, incomplete** | form25 :51-53 `research@example.com`; action_chain :83 same; `bdc_data.py:43` `"MONAD-quant research"`, `PAUSE = 0.12` (:45); `--min-interval` default 0.12 (form25 :1200, action_chain :1277). `bdc_text_nav.py:52-56` requires `@` — but it **also** runs `PAUSE = 0.12` (:36), which the proposal omits, and its error string offers `contact@example.com` as the format hint, which the proposed `example.com` refusal would reject |
| 1e | SEC public-domain: `DATA_REDISTRIBUTION_AUDIT.md:88`, `data_store.py:71-73` | **VERIFIED** | SEC row at :88; `RESTRICTED_VENDORS` lists Yahoo/CEFConnect/FSE only. **`data/README.md` does not exist** — the file is `docs/research/data/README.md` (:3-7, :51-52 content as described) |
| 1f | 993 B/row; ~30k rows/yr | **UNVERIFIABLE / PLAUSIBLE** | no sample row committed or in scratchpad. ~7-8k 10-K(+/A) + ~21-23k 10-Q(+/A) ≈ 30k accessions is consistent with my knowledge. Note `form.idx` emits one row per filer CIK, so co-registrant filings inflate rows above accessions |
| 1g | `TONE_LEDGER.md:21-22` Pi not a pusher | **VERIFIED** | verbatim at :21-22 |
| + | `pages.yml` cites | **LINE DRIFT** | :19-20 one-schedule rule ✓; bootstrap is :100-113 (not :81-99); push/rebase-retry is :134-146 (not :120-132) |
| + | `tone-ledger` exists on origin | **VERIFIED** | `git ls-remote`: `refs/heads/tone-ledger` |
| + | `hdr.sgml` precedent | **NONE** | zero references in repo; the only acceptance parser (form25 :391-396) regexes `<ACCEPTANCE-DATETIME>(\d{14})` from the **.txt** submission — seconds precision confirmed, header-file existence not |

## Objections

**O1 — `hdr.sgml` is an untested load-bearing dependency.** Nothing in the repo has ever fetched one. The proposal's conditional #2 (fallback if >5% missing) has no measurement step that would trigger it. *Fix:* the first dispatch is a `probe` mode: 500 random 2019+ accessions from one quarterly `form.idx`; report hdr-present rate, 14-digit acceptance rate, and runner HTTP status distribution as a committed `probe` shard. Schedule is enabled only after that shard shows ≥95% on both; otherwise `hdr_source` becomes the `.txt` header (first 64 KB via `Range:` if honored) and the row records which.

**O2 — holes are permanent.** "403 aborts the run and lands as a probe row" leaves a partial day; the next run does "yesterday", and the monthly sweep only revisits accessions the rebuilt index changed — never headers that were simply not fetched. The "missing-seal-day report" cannot see a day whose seal exists but is incomplete. *Fix:* the daily job processes every business day since the last `seal{complete:true}`; the seal row carries `idx_rows, hdr_ok, hdr_failed, complete`; the freeze path (`data_store.write("EDGARLEDGER")`) refuses a shard with `hdr_ok/idx_rows < 0.95` unless `--allow-partial` is given and written into the manifest (FD00:265-267 gate, enforced in code).

**O3 — "a branch nobody clones" is false.** `.git/config` refspec is `+refs/heads/*:refs/remotes/origin/*`; a default clone fetches all 50 branches' objects. Pack today 49.22 MiB; the 2019+ backfill adds ~38 MB (+77%), then 5-6 MB/yr. *Fix:* state those numbers; document `git clone --single-branch` for contributors; decide explicitly between this and a sibling data repo. Not blocking if stated honestly.

**O4 — guard and scope.** `tests/test_export_pages.py:298-314` inspects only `pages.yml`; a second workflow with `contents: write` is unguarded. `contents: write` is repo-wide and cannot be narrowed to a branch. CI storm: **none** — `test.yml` fires on `[main, development, claude/**, fix-**]` and `pages.yml` only on `workflow_run`/schedule/dispatch, so an `edgar-ledger` push triggers nothing (verified). *Fix:* sibling test — every `git push` in `edgar-ledger.yml` names `edgar-ledger`, no `push origin development`, permissions exactly `contents: write` (no `pages`, no `id-token`); and record that branch protection on `development` is the real barrier, not the token.

**O5 — `clock_class` vocabulary does not match the fixture.** See 1b. Test (e)1 cannot assert a quality for the seventh fixture. *Fix:* `clock_class` takes the fixture's `acceptance_time_quality` enum; `public_time_date_only` is a `quality_flags[]` entry; test 1 asserts quality only where the fixture specifies one, and `market_phase`/policy for all seven.

**O6 — S1 is a census, not a test.** After-close acceptance (16:00-17:30 ET) is the dominant filing window for 10-K/10-Q; the share is tens of percent, and post-17:30 rollover alone is several percent. "Wilson LB ≥ 1%" fires with certainty. *Fix:* pre-register the decision-relevant split: **leak share** = rows where the naive clock (open of `filed`) precedes `tradable_policy_daily`; **lag share** = rows where it follows. Rules: leak share ≥ 5% → `filed` banned; < 5% with median lag ≤ 1 session → `filed+1 open` allowed with the measured staleness attached. Add one falsifiable contrast FD00:262 asks for: small-filer rollover share ≥ 2× large-filer share (by SIC/filer status). Replicate F163 on this population: share of acceptances in (17:30:00, 17:47:43] with same-day `filed`.

**O7 — co-registrants.** A 10-K can carry several FILER blocks; `issuer_cik` singular breaks invariant 2's meaning and S2's `(issuer_cik, period)` pairing. *Fix:* `issuer_cik` = first FILER block, `co_registrant_ciks[]` for the rest; S2 pairs on the primary and reports the co-registrant share.

**O8 — personal data.** Negligible for this population: 10-K/10-Q filers are entities; the submitter prefix is a filing agent and is stored as a prefix only. But the header carries BUSINESS/MAIL ADDRESS, phone and IRS NUMBER. *Fix:* invariant 4's denylist names those keys explicitly.

## First-slice judgement

The proposal's counter to the FSDS alternative — "FD-NUM still needs this slice's acceptance clock" — is, to my knowledge, **wrong**: the Financial Statement Data Sets' `sub.txt` carries `adsh`, `cik`, `sic`, `form`, `period`, `fy/fp`, `filed`, **`accepted` (YYYY-MM-DD HH:MM:SS)**, `prevrpt`, `nciks/aciks`; `num.txt` carries accession-scoped as-filed facts. FD00:68 already records FSDS as "as filed" from 2009-04-15; `insider_data.py:7,125` is the hash-and-manifest precedent. If the proposer confirms that field list from the FSDS readme, then **one zip per quarter (~70 downloads)** unblocks **H51 (FD-NUM), H52 (via `prevrpt` + period) and S1** at once, versus this slice's S1 + metadata-half of S2 for 30k fetches/yr. FSDS cannot give first-seen, `DATE AS OF CHANGE`, PRIVATE-TO-PUBLIC or role blocks, and is 2009+ only — so the daily header ledger stays as slice 2 for revision semantics, not as the opener. Both slices share the same residual risk (runner 403) and the same first step: the probe. Recommended order: probe → FSDS manifest + `sub.txt` extract → this ledger.

## Ruling

**DISPUTE.** O1, O2, O6 and the first-slice reordering must be answered; O3-O5, O7-O8 are fixes I expect adopted as written.

## Wording fixes

- `data/README.md` → `docs/research/data/README.md` (both cites).
- `pages.yml:81-99` → `:100-113`; `:120-132` → `:134-146`.
- "all three space requests at 0.12 s" → "all four, including `bdc_text_nav.py:36`".
- `example.com` refusal: amend `bdc_text_nav`'s hint string in the same change, or the pattern's own example is rejected.
- "`verify --against` walking every branch commit" → "…every commit present in the checkout (one, in a depth-1 clone)".
- Row schema: `clock_class` enum = fixture `acceptance_time_quality`; add `co_registrant_ciks[]`; seal row fields per O2.
- "a branch nobody clones with `development`" → the O3 numbers.
