# Skeptic, round 2 — EDGAR ledger (revised proposal)

**Reviewed:** `debate_edgar_ledger_proposal_r2.md`. All r2 cites re-checked against the tree: FD00:221 (Tier-2 XBRL row), :127 (daily default), :422 (exhibit-only / Part III / tagging-only amendments), form25 lab :243 `deterministic_sample`, `data_store.write` :327, `bdc_text_nav.py:66` injectable `get`, `test.yml:4-5`, `pages.yml:48-50`, commit `10d9437` 17:21 — **VERIFIED**. One drift: the 90% same-form pair gate is FD00:**273**, not :271.

## (a) REBUT on FSDS scope — CORRECT

FD00:238 says *all* public 10-K/10-K/A/10-Q/10-Q/A submissions, and :422 explicitly classifies amendments as exhibit-only, Part III incorporation, tagging-only or financial. FSDS (to my knowledge; the probe measures it) holds XBRL-bearing submissions only, so it cannot be FD-00's frame and slice 2 stays. Required precision: the **≥95% coverage rule applies to originals (10-K, 10-Q) only**; 10-K/A and 10-Q/A coverage is reported and scopes H52-lite, never gates the S1′ frame. Exclude accessions filed in the quarter's first/last two business days from the denominator (zip and `form.idx` quarters can straddle a rollover), or probe the adjacent zip.

## (b) Probe fail-closed — YES, with two defects

P0–P2 are falsifiable (numeric thresholds, named failure states) and `daily`/`fsds` refuse without a committed passing `probe_summary`. Two defects remain:

1. **Bootstrap deadlock (must fix).** The job fails on any `verify --against origin/edgar-ledger` problem. Run here: `trials.verify_history("origin/edgar-ledger", …)` → `["cannot resolve merge-base with 'origin/edgar-ledger': fatal: Not a valid object name"]`. On the first run the branch does not exist, so nothing is ever pushed. *Fix:* when `git ls-remote --exit-code` finds no branch, the run is README-only and `verify` runs shard checks without `--against`; `--against` is mandatory from the second run. Test it offline in `test_edgar_ledger_workflow.py`.
2. **Pre-probe write.** Clone-or-bootstrap pushes the README on the first *scheduled* run. Either bootstrap only in `probe` mode, or state that the README is the one permitted pre-probe write.

Minor: `daily` exiting 0 on "no passing probe" is a silent green; emit a `::warning::` and count probe-less days in `--report-gaps`.

## (c) O2 resume + freeze gate — SUFFICIENT for incomplete days, not for absent ones

`complete=false` or `hdr_ok/accessions < 0.95` is caught and `--allow-partial` reaches the manifest. A weekday with **no seal row at all** (idle disablement, failed clone) is not refused. *Fix:* `freeze` enumerates weekdays in `[from, to]` and refuses any with no seal row unless `--allow-partial`; the manifest lists `partial_days[]` and `missing_seal_days[]`, not a boolean.

## (d) Pre-registrations — two tests, one census, one gate

- **S1′ is still a census, by construction.** Every after-close acceptance with same-day `filed` leaks under A (filed-day open < next-day open), and after-close is the dominant window (conceded in O6), so "leak ≥ 5% → banned" fires with certainty. B cannot leak unless `filed` precedes acceptance, and its staleness is 0 or 1 by construction, so "median ≤ 1" passes almost surely. Useful — it fixes FD-01's clock with a measured leak magnitude — but **label it a calibration measurement, outside the hypothesis error-rate count**.
- **H-SIZE** is a test: direction (small ≥ 2× large), kill (< 1.25). Add the gray-zone verdict: ratio in [1.25, 2) → *inconclusive, reported*. `afs` codes are strings (`1-LAF`…`5-SML`, to be probed).
- **F163 replication** is a test: kill ≥ 2%. Same gray zone, [0.5%, 2%) → inconclusive.
- **H52-lite** is a gate (pair rate ≥ 90%), correctly not claimed as a test.

## (e) Remaining must-answer

None beyond b1, b2 and c. O1–O5, O7, O8, 1c/1d and the slice reorder are accepted as asked; forward-only slice 2 answers O3 honestly.

## Ruling

**CONCUR**, conditional on the following being adopted verbatim (the DEFLATION precedent):

1. Bootstrap path: no `--against` on the branch-creating run; README-only first commit; offline test.
2. `freeze` refuses missing-seal weekdays; manifest lists `partial_days[]` / `missing_seal_days[]`.
3. Coverage rule scoped to originals; boundary-day exclusion or adjacent-zip check.
4. S1′ labelled a calibration measurement, outside the hypothesis count.
5. Gray-zone verdicts for H-SIZE and F163.

## Wording fixes

- `FD00:271` → `FD00:273` for the 90% pair-rate gate.
- "the daily job writes nothing until the probe passes" → "…writes nothing but the bootstrap README".
- "`verify --against origin/edgar-ledger` fails the job" → "…from the second run; the bootstrap run verifies shards only".
- Pre-registration header: "two tests (H-SIZE, F163), one gate (H52-lite), one calibration (S1′)".
