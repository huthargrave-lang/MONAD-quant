# Skeptic, round 1 — research-web status hygiene

Reviewed: `debate_web_hygiene_proposal.md`. Everything below was re-run on the working tree (python3, no venv).

## Verification table

| Claim | Verdict | Evidence |
|---|---|---|
| Two copies of the pending rule | **TRUE** | `ctx.py:1584-1590` inline in `cmd_web`; `ctx.py:2251-2256` `_is_open_work` (consumers `:2307`, `:2346`). `tests/test_research_web.py:1007 test_open_work_flag_matches_the_pending_view` already pins map == `--pending`. |
| `research_backlog.py:375-391` closes by `resolves` from a current node | **TRUE, different parser** | It runs on `epistemic_audit_lab.parse_web` (tuple edges, `status` key). ctx's `_parse_web` nodes have keys `body, edges, links, title` — dict edges, no `status`. `_is_open_work` cannot take an epi node. |
| SCHEMA §5 wording/direction | **TRUE** | `SCHEMA.md:128`: `resolves \| Decision/Finding → Hypothesis \| — \| Closes an open question.` §6.1 (`:159`): "Append + supersede, never delete or rewrite." |
| SCHEMA also says the opposite | **Proposal omits** | `SCHEMA.md:84`: Hypothesis "State (`OPEN`/`RESOLVED`/`DEAD`) **currently lives in the title**." `:66` tag list is `OPEN, RESOLVED, DONE, DEAD-END, [SUPERSEDED by Fx], [ctx]` — **no `APPLIED`**. |
| H11 | TRUE | `semantic_staleness` `ctx.py:2950`, `cmd_stale` `:2997`, parser `:3875`; `tests/test_ctx_semantic_staleness.py` exists. |
| H15 | TRUE | `cmd_drift` `:3193`, parser `:3876`; `tests/test_ctx_drift.py`. |
| H16 | TRUE | rider `:912-937` ("CONFIRMED edge … cold start"); `tests/test_ctx_perf_rider.py`. |
| H12 | TRUE | `.github/workflows/test.yml:70-73` runs `ctx health` + `web --lint`; `tests/test_cli_smoke.py`. |
| H14 not done | TRUE | `grep -c '"F26"' context_map.json` → 0; `generate_trades` only at `:162`, `:378`. |
| D8 bridge misattributed | TRUE | `context_map.json:306` → `implemented_in tools/ctx.py::_GRAPH_HTML`, guarded by `TestGraphHtmlExplore` (D10's topic). |
| `note.py retype` exists | TRUE | `{add,supersede,link,retype,draft}`; no `close`. |
| D7 dry-run clean | TRUE | "DRY RUN — clean." |
| Count 89 → 64 → 61 | **TRUE** | Pending now 89. Strict rule A (H target, F/D source) removes **24**: `H10 H11 H12 H13 H15 H16 H17 H18 H19 H20 H22 H23 H25 H27 H38 H39 H40 H41 H42 H43 H45 H50 H61 H404703`; +D7 (title) → 64; rule B removes `D4 D5 D10` → 61. Loose "any inbound resolves" also hits **D4** (`H8`, `F41 → D4`) and **H5** (`E7 → H5`) — three live direction violations no lint catches. |
| Confidence/dispute | latent, not live | None of the 24 resolving sources carries `conf`. Disputed-but-current set today: `F194` (by F211), `H404700` (by F404703) — neither is a resolver. |

**Refusal 1** — `python3 tools/note.py supersede D4 --by D6 --reason refined`:
```
PROBLEM  live F21 --refines--> superseded D4 (reliance on a retracted claim)
PROBLEM  live D5 --refines--> superseded D4 (reliance on a retracted claim)
PROBLEM  live D6 --refines--> superseded D4 (reliance on a retracted claim)
PROBLEM  live F42 --refines--> superseded D4 (reliance on a retracted claim)
PROBLEM  live F181 --refines--> superseded D4 (reliance on a retracted claim)
PROBLEM  live F13 cites superseded D4 without superseder D6 (cite [[D6]])
  … (F14, F16, F17, H7, F22, F23, H42 likewise)
REFUSED: the result would break the web — no write made.
```
13 PROBLEMs: 5 invariant-2 reliance + 8 invariant-3 propagation. The proposal's "5 propagation hits" undercounts and mislabels.

**Refusal 2** — `python3 tools/note.py supersede H11 --by F186 --reason merged`:
```
PROBLEM  live D7 cites superseded H11 without superseder F186 (cite [[F186]])
REFUSED: the result would break the web — no write made.
```

## Objections

**1. The H46 pattern is already in the removal set.** F238 `resolves` H22, yet its body says: *"one proposal built-but-defective, one aimed at a dead lever, **two genuinely open and blocked on data**"*. That is the proposer's own change-of-mind condition #1, met before the rule ships. Under rule A, `--pending` drops H22 while two of its four proposals are, by the closing Finding's own words, open. Nothing guards this: `note.py link/retype` check only `EDGE_TYPES` membership and reliance-to-superseded (`note.py:527-556`); lint checks no edge direction or source kind (hence `F41 → D4`, `H8 → D4`, `E7 → H5` live). **Fix that satisfies me:** (a) in the hygiene pass, `retype F238 H22 --type refines` (the repo's documented "narrows but leaves open" edge, `research_backlog.py:278-279`) and let H22 stay pending — 89 → 65; (b) `note.py link`/`retype` refuse `--type resolves` unless source ∈ {F,D} and target ∈ {H} (SCHEMA §5 direction, one `sys.exit`); (c) `ctx web --lint` advisory for any existing off-direction `resolves`.

**2. Rule B inverts the repo's own `refines` semantics.** The proposal uses `refines` to *close* D4/D5/D10 while relying, for H36 (F209 `refines` H36 ≠ closes), on the documented reading that `refines` leaves the target open. D5 ("Recommended next architecture") carries `gated_by cfg:ACTIVE_MODE, code:compute_trade_returns` bridges and inbound `supports F177` — a live, code-bridged recommendation. D4 likewise. Hiding gates from the "decisions/gates" view by an inference the lint refused to let you make explicitly is the one non-schema rule here, and the proposer admits it. **Fix:** drop rule B (baseline 64, the proposer's own fallback #2). D8 is correctly untouched (`builds_on`, not `refines`).

**3. The count ceiling punishes capture.** Every D is pending by construction and every OPEN H adds one, so each `note.py add` of either kind reds CI until a `tests/` constant is edited — a cross-fence penalty on recording. Measured capture rate of pending-kind nodes (last footer date): **39 in 2026-06, 33 in 2026-07**, 6 in 2026-08, 3 in 2026-10 — at the June/July rate that is 8–10 bumps/week, far past the proposer's own "~1/week → switch" trigger. Repo precedent (`test_context_map.py:468`, `test_web_code_claims.py:475`) is **set-equality** ratchets that name the delta, not a ceiling with a 5-slack floor. **Fix:** replace `test_pending_count_does_not_rise_silently` with a frozen `CLOSED_BY_HYGIENE` set (the 24 H + D7) asserting none reappears in pending — forbids *reopening*, never fires on a legitimate new capture; keep `test_pending_never_lists_an_answered_hypothesis` as the real invariant.

**4. The proposed test is wrong under the proposer's own fallback.** `answered` filters source kind (`n[:1] in "FD"`) but not target kind, so `F41 → D4` marks D4 "answered"; with rule B dropped, D4 stays pending as a D and the test fails. **Fix:** add `and e["target"][:1] == "H"`. Also drop `test_pending_cli_matches_predicate` — it duplicates `test_research_web.py:1007`.

**5. Encoding item 4 overpromises.** "research_backlog.py imports the same predicate" is not possible across the two parsers (Verification row 2). **Fix:** state that `_nodes_resolved_since` *is* the same rule on the epi parser, and add one test asserting both agree on the live web.

**6. Confidence gate (minor, forward-looking).** Rule A says "current" only. Today no resolver is disputed, but `ctx web --lint` already has a disputed tier (`ctx.py:1522-1541`). **Fix:** rule 1 reads "current and not contradicted by a current node".

## Ruling: **DISPUTE** — objections 1–4 must be answered; 5–6 are wording.

## On "revisionism"

The answer is sound for H nodes *as far as it goes*: a `resolves` edge is an append, `ctx web H11` still prints the question and `← resolves F186`, `retype … supports` reopens. It fails on two points. It rests on §5:128 while ignoring §2:84, which makes the title the state-of-record for an H — so "title retag is optional cosmetics" is a schema change presented as schema compliance; the hygiene commit must amend `SCHEMA.md:84` (documentary; §9 needs no bump — no new kind, edge or field). And rule B is exactly the inference the answer says it avoids: it closes decisions by reading an edge the schema never defines as closing anything.

## Wording fixes

- Rule 1: "…a **current, uncontradicted** F or D carries `resolves` → H; direction F/D→H is enforced by `note.py link`/`retype`."
- Rule 3(b): "RESOLVED/DONE (SCHEMA §2:66)" — `APPLIED` is not in the list; add it there or drop it here.
- D4 row: "REFUSED, 13 PROBLEMs: 5 reliance (invariant 2) + 8 propagation (invariant 3)".
- H22 row: "F238 `resolves` but says two proposals are open and blocked on data → retype to `refines`; stays pending."
- Rule 4: replace "imports the same predicate" per objection 5.
- Revisionism section: cite `SCHEMA.md:84` and the amendment.
