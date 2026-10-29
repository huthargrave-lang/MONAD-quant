# Skeptic, round 1 — forward route: the two owner values (2026-10-29)

Reviewed `scratchpad/debate_forward_route_proposal.md` at HEAD 10d9437 (9266877 is a first-parent ancestor of HEAD and `origin/development`).

## Verification table

| # | Claim | Command / source | Result |
|---|---|---|---|
| a | One merge, 2026-10-10T20:29:17Z | `git log --first-parent origin/development --diff-filter=A -- <3 files>` | One line: `9266877 2026-10-10T16:29:17-04:00`. ✓ |
| b | Window opens 2026-10-13 | `tools/forward_watch.py:49-72`; `nyse_calendar.is_session(2026-10-12)` → True | `opens_at` = first snapshot date strictly after 10-10. **Columbus Day is not an NYSE closure: the window opened 2026-10-12.** ✗ |
| c | Zero in-window lines | tails of both `.jsonl` | H366200: 1 session line (10-09). H366201: 5 session lines (last 10-09); last `vintage` line recorded 10-10 but **fetched 2026-10-09T09:15Z** (panel 2e74690e). No `window_open` line. ✓ |
| d | `report` → 3.466 at m=2 | `report H366200` | `m = 2 … must reach 3.466`. ✓ `report H366201` crashes here (private DS store absent). |
| e | Route surface and tests | `forward_watch.py:545-562`; tests :404-414, :694-704 | ✓. Test :408 asserts `_history_rule(POLICY) == "identical"` (Obj. 2). POLICY's only non-test consumer is `cmd_report` (:189-191); **`log` never reads it.** |
| f | DD figures | the four docs | METAL_TRUST:102 −54.9% ✓; COMMODITY:112 −40.1% ✓; CREDIT:261 proxy spread → **0.3/≈0.6/1.3 pp** at 5/10/20%. SLEEVE_BREAK_EVEN:79-97 holds only −21.2% (:95); −32.2% is CREDIT:241; −13.5% found nowhere. The "~−27/−36/−35%" sleeve drawdowns appear in no doc. |
| g | 14-day rule | `metal_trust_classes.py:38,81-89,123`; last session line `rule_state.obs = 2026-10-02` (weekly NAV) | First stale session **2026-10-19** ✓ (approx). Both trusts' carried state at 10-02 is already 0.5 = neutral. |
| — | Round-3 text "on development at b5582a6 before that merge" | `git show b5582a6:…PROPOSAL.md` has no "ln 48"; 14ba96e (2026-10-09T12:26:59Z) does; file reached development only in 9266877 | **Wrong commit; same merge as the specs, not before.** Still pre-window. ✗ |
| — | Ledger ordinal rule (sums: 2/3 + Σ_{i≥3}1/(i(i+1)) = 1 ✓) | PROPOSAL.md:273-274, :287 | "ID on the ledger before `freeze`; concurrent branches in first-parent merge order." No same-merge tie; no coverage of pre-ledger specs. |
| — | Spec route fields | both specs | H366201: route "…m = every forward watch ever frozen (route_policy)", pointer → `route.json`. **H366200.json has neither field.** |

## Objections

**1. The window date is wrong (10-12, not 10-13), and it is about to be written into the ratification record.** Row b: 13 in-window sessions (10-12…10-28) have elapsed unlogged. Fix: 2026-10-12 everywhere.

**2. Step 2 ("replace `policy/route.json`") cannot pass `verify --against` or CI.** `_history_rule` is "identical" for every `.json` under `WATCH_DIR`; `verify_history` walks the tree recursively and `_branch_walk` rejects any commit changing a governed file (`trials.py:920-975`); test :408 pins it. Replacing the frozen policy in place weakens the mechanism that makes it frozen, in the PR that amends it. Fix: leave `route.json` byte-identical; add `policy/route.2.json` with `supersedes`, `post_open: true`, `window_opened: 2026-10-12`, `in_window_session_lines_at_merge: 0`; the engine reads the newest valid link of the supersession chain; `_history_rule` unchanged; `verify` checks the chain. The consensus's word "replaced" (:306) predates this check and should be read as "superseded".

**3. Budget rationale (c) sets the budget by its admission outcome. Strike it.** "1 pp plausibly admits H366201 at 10% and caps H366200 at 5%: the right ordering" picks the number by which sleeve it lets in, from unpublished estimates (row f). CREDIT:135-137 forbids setting the budget from that study's numbers; a preview of the candidates' own numbers is worse. Fix: delete (c) and the three estimates; keep (a) noise scale and (b) product tolerance (1 pp ≈ 3% of the host's worst DD, ≈ 5% of 2022's). Add to "what would change my mind": nothing about either candidate's measured drawdown.

**4. The budget is not identifiable until its measurement is frozen.** With 0.3-0.6 pp of procedure spread at the grid's carves, a sleeve measuring 0.8-1.2 pp is a coin flip. Absolute pp is right (the relative-budget rejection stands), but only on a fixed procedure. Fix, into `route.2.json`: mix `m_t = (1−x)p_t + x s_t`, rebalanced each session to fixed weights, carve pro rata from the 60/40 (CREDIT:70); sleeve = the watch's recorded **1x-cost** tilt book, host = `TR-20261006T005053Z-9336581d#0` on the daily close path; DD = nominal peak-to-trough on that path; windows = full overlap, overlap-start…2022-07-31, 2022-08-01…end (F46); the max binds; no proxy extension unless a Q3 amendment freezes one before any ADMIT.

**5. "The ledger rule ties them" over-reads the rule.** :273-274 orders *concurrent branches*; it says nothing about two specs in one branch and cannot reach specs frozen before any ledger existed. On an append-only ledger the within-branch ordinal is append (= freeze) order: strict order, not a tie. The split is still right, but on the consensus's own ground: the founders predate the ledger and the policy in force at both freezes (4445325, 09:09Z) was symmetric in m; they are grandfathered as a cohort by explicit ratification. Fix: rewrite (a) accordingly; drop the "weaker-evidenced watch" remark in (c) — using which watch has the better protocol result to justify the α it receives is the same outcome-targeting as Objection 3.

**6. The ordering constraint is bookkeeping, not data-blindness, and it is mis-cited.** `log` never reads the policy (row e), so no line depends on which policy is in force; both candidate values were committed 2026-10-09T12:26:59Z (14ba96e), before the window opened, and both are ≥ the in-force 3.466. The residual exposure — *choosing* between pre-written alternatives after public in-window prices exist — is unavoidable now and unaffected by whether `log` has run. Fix: state "no `log` before the policy merges" as a preference that keeps the supersession record simple, bounded to the ratification PR's lifetime; state plainly that `fetch` must start today (see urgency note).

**7. Delegated ratification of a risk preference.** Q3 says three times "Hudson sets the budget". A delegate's 1 pp is weaker evidence of the owner's tolerance than his own word; the α split is a design choice and delegable. Fix: the D node records the budget as *the consensus default adopted by delegation*, amendable by the owner before the first ADMIT (none before ~2029-01), and that Q3's "paper only until Hudson approves" bounds the delegate's reach; the proposer's own "budget 0 on an owner mandate" clause stays.

**8. H366200 has no `route_policy` pointer.** "File governs over `evaluation.route`" is right for H366201 (its pointer is the deference mechanism; the inline formula glosses the 2026-10-09 policy). H366200 is bound only through ledger membership and the policy's `applies_to`. Fix: the test asserts both, and that no spec field is edited. Minor: cite −32.2% to CREDIT:241; source or drop −13.5%.

## Ruling: **DISPUTE**

1-4 must be answered (1-2 factual/implementation defects; 3-4 go to whether the budget is legitimately set). 5-8 are wording I expect to CONCUR on. The values themselves — 1.0 pp absolute, α/3 each — I do not contest.

## Wording fixes

- "2026-10-13" → "2026-10-12"; "zero in-window lines" → "zero in-window session lines (13 sessions elapsed)".
- "amendment text on development at b5582a6 before that merge" → "committed 2026-10-09T12:26:59Z (14ba96e), before the window opened; reached development in the same merge".
- "Replace `policy/route.json`" → "Supersede it with `policy/route.2.json`; `route.json` stays byte-identical".
- "the ledger's own ordinal rule ties the two watches" → "the ledger rule does not reach specs frozen before it existed; the founders are a grandfathered cohort".
- "Stricter than the policy in force" → "stricter than it today (m=2), equal at m=3, looser than it would become at m≥4 (the m-count the consensus rejected)".
- Section 0: "no catch-up `log` until the policy merges; **`fetch` daily from today**".

## Operational urgency (question c)

The decay is real, small per day, irreversible — and stopped by `fetch`, not `log`. `vintage_for` lets a session read only vintages fetched before the *next* session's 20:00 UTC close: a fetch today (before 20:00Z) serves 10-28 onward, while 10-12…10-27 (12 sessions) are locked to the 10-09 vintage (last observation 2026-10-02: unstepped through 10-16, stale from 10-19). The carried state was already neutral at 10-02, so all 12 read neutral: ≈0 active return, LLR drift ≈ −0.002 nats (negligible), two weekly observations of possible episodes forgone (H366201 needs 20 by year 4). Each further day locks one more session. `fetch` writes a `vintage` line, not a session line, and reads no return, so it leaves the zero-session-line condition intact; `log` catches up later, deterministically, from committed vintages. So: fetch today (owner's machine; this sandbox has neither vendor access nor the private store), log after the policy merges, and do not let the ordering preference outlive the ratification PR. Logging first then amending stricter changes no line; lost sessions cannot be recovered.
