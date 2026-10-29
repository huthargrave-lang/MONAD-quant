# Skeptic, round 2 — research-web status hygiene

Reviewed `debate_web_hygiene_proposal_r2.md`. Every claim below was re-run on the working tree.

## Verification

| Claim | Verdict | Evidence |
|---|---|---|
| Five Tier-1 retypes dry-run clean | **TRUE** | `F238→H22 refines`, `F168→H50 refines`, `F271→H36 resolves`, `F272→H37 resolves`, `F41→D4 refines` — each "DRY RUN — clean." |
| `retype E7 H5` cannot fix a cue-inferred edge | TRUE | `ValueError: expected exactly one [[H5\|resolves]] in E7, found 0` (`note.py:236`). |
| H9 `add` dry-run clean, two advisories, allocates F297800 | TRUE | Ran as written: advisories "no `evidenced_by`" and "shares title terms with H15, F141, H43"; "DRY RUN — clean." |
| H27 kept as answered via F404701 | **TRUE, a real fix** | Body: `runner.resolve_regime_filter` now passes the configured gate; "before … every backtest ran the gate at its signature default True while live passes False: H27". Its "Still open:" sentence concerns `main.py`'s trade_hours gate, not H27. |
| H25 kept as answered via F198 | **TRUE, by reasoned decline** | Body: "neither can be EXECUTED [Yahoo blocked]. Both can be ANSWERED" — `sweep.py` already floors stops at `max(0.15, 5×spread)`, so the title question reduces to a per-mode price floor. The sweep itself was not run; this fits the stated criterion (decline with reasons = answer). |
| H19/H20/H23/H45 | clean | Each resolver ends with a named guard test and `[[Hxx\|resolves]]`; no remainder language. |
| 89 → 63 after Tier 1+2 | **TRUE** | Simulated the five retypes + the H9 Finding in memory through the proposed `_resolved_hypotheses`/`_is_open_work`: pending = **63**. |
| CLOSED_BY_HYGIENE (26) all closed, none vanished | TRUE | still-open ∩ set = ∅; set − nodes = ∅. D1, H4, E7 still listed (`test_research_web.py:276` safe); H22, H50 still listed. |
| 14 off-direction `resolves`; 13 remain after F41→D4 | TRUE | Computed set minus `("F41","D4")` equals `KNOWN_OFF_DIRECTION_RESOLVES` exactly. |
| backlog/ctx agree on 36 targets | TRUE | `_nodes_resolved_since(LAB.parse_web(…))` targets == ctx set, 36 == 36. |
| Contradicted set {F15, F194, E132, F259, H404700}, no resolver | TRUE | `ctx._contradicted_by` (`ctx.py:1375`) returns exactly those keys; no simulated resolver is among them. |
| `web --lint` exits 1 on advisories (why set-ratchet, not advisory) | TRUE | `ctx.py:1543-1544`. |
| Tier 2 touches no DENY file | **TRUE** | `ctx can_edit`: `tools/ctx.py`, `tools/note.py`, `SCHEMA.md`, `tests/test_research_web.py`, `RESEARCH_WEB.md` all ALLOW; `context_map.json` DENY and correctly left in Tier 3. |

## Remaining concerns (none must-answer)

**A. `test_pending_never_lists_an_answered_hypothesis` is a tautology.** The new `_is_open_work` returns False for every id in `_resolved_hypotheses`, so `open ∧ resolved` is empty by construction (simulation: `[]`). It cannot fail and so does **not** cover the F238 pattern going forward — a `resolves` whose source names a remainder is semantic; no predicate catches it. The real guards are the direction refusal (kind only), the `refines` convention, the dry-run read at `--commit`, and the frozen set making any reopen visible. Say so, and either drop the test or repoint it as a heuristic sweep (`genuinely open|remains open|PARTIALLY DONE` in resolver bodies, with a known-exception set — F404701's unrelated "Still open:" would need listing). Optional.

**B. Cost shape.** `_is_open_work(nid, node, nodes)` recomputes `_resolved_hypotheses(nodes)` (a full edge scan + `_contradicted_by`) on every call, and it is called per node at `ctx.py:2307`, `:2346` and in `--pending` — O(N²·E) on 603 nodes. Compute it once per listing and pass or cache it. Both call sites must also gain the `nodes_web` argument.

**C. "Same rule, two parsers" overstates.** The agreement test compares raw `resolves` target sets; `_nodes_resolved_since` has no direction or contradiction filter, so the backlog still treats `E7→H5` as closed while `--pending` will not. Either say "same raw edge set; backlog's filter is looser and advisory" or add the two filters to `_nodes_resolved_since`.

**D. Row wording.** H25: add "answered by reduction, sweep not run (data-blocked)". H9: do not hardcode F297800 anywhere — the id is allocated at `--commit` time; `CLOSED_BY_HYGIENE` correctly lists H9, not the F.

## Ruling: **CONCUR**, with wording fixes A–D.

Round-1 objections 1–4 are answered with verified, executable fixes: remainder-naming resolvers retyped (clean), a direction/kind refusal on the write path that admitted 14 off-direction edges, rule B gone, a frozen set that fires only on silent reopening, the target-kind filter, the duplicate test dropped, `SCHEMA.md:84` amended in the same commit. What remains is shape and phrasing.
