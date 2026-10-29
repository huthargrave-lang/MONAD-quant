# Skeptic, round 2 — forward route: the two owner values (2026-10-29)

Reviewed `scratchpad/debate_forward_route_proposal_r2.md` at HEAD 10d9437. All eight round-1 points are accepted as claimed; the two variants are improvements.

## Verification

| Q | Checked | Result |
|---|---|---|
| (a) consensus coverage | section A vs `FORWARD_ROUTE_PROPOSAL.md:283-290` | Every Q1-Q4 value is present (boundaries, non-terminal own promote, anniversaries 2/4, 64th-line settle, ledger, α/3, γ_i, never recycled, ordinal-3 honesty, H404702 excluded; host, 1x book, grid, stagewise 80% LCB, both-regime rule, budget, 30-day record, paper only; own-data CUSUM h=2.0, daily cut). **Omitted from Q5:** the witness detail ("log prefix on development, `witnessed_sha` recorded"); "a hand-written ADMIT cannot verify" (red-team 7b); the seven required tests (own-promote then route-admit; late correction changes no verdict; branch deletion changes no ordinal/α_i; H366201 year-3 close suppressed; long leg ≤ 0 closes; CUSUM alarm de-admits; volatility shift alone does not trip it). β' ≈ 0.205-0.209 omitted (derived). |
| (a) α sum | B rows + `gamma()` | founders `Fraction(2,3)/2` = 1/3 each; Σ_{i≥3} 1/(i(i+1)) = 1/3; total 1 ✓. Ordinal 3 → α/12 → ln 192 = 5.257 ✓ (test E matches). |
| (b) verify passes | `trials.py:920-999`; `tools/forward_watch.py:214-219` | Merge-base check lists only files present at the base; `_branch_walk` compares only paths in `prev`, so **additions pass** (`:991-998`). `route.json` byte-identical (sha `762ce64c…` matches HEAD) ✓. `freeze_ledger.jsonl` → `.jsonl` → "prefix": appends pass ✓. `_SPEC_NAME` requires no slash, so `policy/route.2.json` is not counted as a watch; `watches_ever_frozen` stays 2 ✓. `CommittedRecords` globs `*.jsonl` non-recursively, so the ledger is not held to `canonical_json` (see fix 4). |
| (c) `_require_listed` | signatures at `forward_watch.py:144, 579, 604, 852, 944` | All five take `watch_dir`; `watch_dir is None` is the repo path, scratch dirs exempt ✓. Founders are rows 1-2, so catch-up `log` passes; `governing_policy()` raises on a bad link, which is the intended refusal ✓. |
| (d) specs untouched | `sha256sum` at HEAD | H366200 `35fc8ffc…`, H366201 `6af76c10…` equal B's `spec_sha256`; `fw.load` hashes file bytes (`:171-173`), so the test's `sha == ledger_entry(...)["spec_sha256"]` is the right check ✓. Test asserts `"route_policy" not in H366200` and H366201's pointer → `route.json` → chain ✓. |
| cites | DTB3 (`SLEEVE_BREAK_EVEN:29`), maxDD from first session (`CREDIT:77`), −0.1348 in both data files, `note.py` link types — all ✓. |

## Remaining must-answer

None that blocks the values. One design gap must be closed **before `route.2.json` is committed**, because the "identical" rule then makes it uneditable without a `route.3.json`:

**Ledger rows for ordinal ≥ 3 are impossible as specified.** The rule says an ID must be listed *before* `freeze`, but B's row shape carries `spec_sha256` and `frozen_at` (unknown before the freeze), `freeze_ledger()` requires contiguous ordinals on every row (so no second row per watch), and `verify_policy` fails "a row whose `spec_sha256` differs from the spec" — a pre-freeze row has no spec. Founders are unaffected; a third watch would be unlistable (fix 1).

## Ruling: **CONCUR**, conditional on fixes 1-3 landing in the committed `route.2.json`

## Wording and implementation fixes

1. **Ledger row shape (in `route.2.json` `ledger.rule` and in `freeze_ledger()`):** a row is `{ordinal, watch, cohort, listed_at}`; `spec_sha256`, `frozen_at`, `reached_development`, `window_opened` are optional and present only for the founders (recorded at ratification). `verify_policy` checks `spec_sha256` only when present; for every other listed watch the spec's bytes are pinned by Q5's registration stage (first-parent history) and by `verify`'s "every spec file has a row". State this in the rule text.
2. **Add the omitted Q5 items to A's `build`:** `"witness": "the log prefix is on development, witnessed_sha recorded"`, `"hand_written": "the verifier recomputes every stage from the prefix; a hand-written ADMIT cannot verify"`, and `"tests_required": [the seven tests above]`. Optional: `"beta_prime": "about 0.205 at alpha_i = 0.05/3"` under `test`.
3. **`policy_chain` path comparison:** `prev.relative_to(REPO)` raises for a scratch `policy_dir` outside the repo; compare `sup["path"]` to `prev.relative_to(policy_dir.parents[2])` or simply to `prev.name` plus the fixed directory. `route_boundary(spec)` with both `m` and `watch` None must raise `WatchError`, not `TypeError`.
4. **Ledger lines are `canonical_json`** (sorted keys, no whitespace), so `CommittedRecords` can be extended to `rglob("*.jsonl")` later without a rewrite; B's rows as drafted are not key-sorted.
5. **Test E, Columbus Day:** `Snapshot` is a frozen dataclass without `_replace`; use `dataclasses.replace(market(n=10), dates=dates)` and drop the `type("S", …)` fallback.
6. **D node command:** `--link` is `action="append"` and each value is split once on `:` (`note.py:445-448`); pass `--link D6:builds_on --link D8:builds_on …`, not one space-joined string.
7. **A's `in_window_sessions_elapsed_unlogged_at_ratification`:** count as of the ratification commit's date (14 if after today's close), not a fixed 13.
8. **G:** add "`fetch` writes `vintage` lines only; it never reads a return."

## Note on the values

Uncontested: **1.0 pp absolute**, measured exactly as A freezes it; **α/3 each, ln 48 = 3.871**, on the grandfathering ground. The delegation record (consensus default; owner-amendable before the first ADMIT ~2029-01; paper only) is adequate. `fetch H366201` daily from today on the owner's machine; `log` after the PR merges.
