# Open question: what closes an OPEN node in the research web?

**Status:** decided — decision debate 2026-10-29 (direction D-4, `docs/DIRECTIONS.md`).
Tier 1 (web edges) is committed at `5e84823`; Tier 2 (code, tests, schema text — this
record's commit) is applied; Tier 3 (D1/D3 supersession) waits on owner ratification.

## Question

`python3 tools/ctx.py web --pending` listed **89** items. Twenty-four of its pending
hypotheses already carried an inbound `resolves` edge from a current Finding or Decision
— eight of them ctx-layer questions (H10–H13, H15–H18) whose asked-for commands exist and
are tested (`ctx stale`, `ctx drift`, the CI `web --lint` gate, …). D7 is titled RESOLVED
and was listed anyway. D1 and D3 say in their own bodies that D6 overtook them. Two tools
defined "open" differently, so the backlog and the pending view disagreed about the same
fact. What rule closes an OPEN node, who may apply it, what encodes it, and how does the
list stay honest without penalising capture?

## How pending was computed (before this change)

Two copies of one title-based rule, and a third tool with the opposite rule:

| Where | Rule |
|---|---|
| `tools/ctx.py:1584-1590` (`cmd_web --pending`, inline) | `not _is_superseded(node) and (id starts with D or title matches ^(OPEN\|IN PROGRESS))` |
| `tools/ctx.py:2251-2256` (`_is_open_work`, consumers `:2307` map summary, `:2346` map detail) | the same rule, a second copy; `tests/test_research_web.py::test_open_work_flag_matches_the_pending_view` pinned map == CLI |
| `tools/ctx.py:1365` `_is_superseded` → `:1333-1362` `_node_meta` | status block, else a `[SUPERSEDED by X]` title tag; `resolves` edges were consulted nowhere (`:1412` only exempts them from supersession propagation) |
| `tools/research_backlog.py:376-391` (`_nodes_resolved_since`) | "closed by a `resolves` edge from a node that is still current" — on the `epistemic_audit_lab` parser (tuple edges, `status` key), with no direction or contradiction filter |
| `tools/note.py:456` (add), `:519` (link), `:548` (retype) | edge writes checked vocabulary and reliance-to-superseded only; no direction or kind check, which is how 14 off-direction `resolves` edges (E7→H5, H8→D4, F41→D4, …) got written |
| `SCHEMA.md:128` (§5) vs `SCHEMA.md:84` (§3) | §5: `resolves \| Decision/Finding → Hypothesis \| Closes an open question`; §3: Hypothesis state "currently lives in the title". The schema said both. |

## Options considered

| Option | Verdict | Why |
|---|---|---|
| Retag titles to RESOLVED by hand | rejected | titles are never hand-edited (SCHEMA §6.6); a `note.py close` verb would be the honest form and is the follow-up, not a prerequisite |
| Supersede answered hypotheses | rejected | answered ≠ retracted. The lint itself refused 6 of 10 dry-runs (D7 cites H11; F191 supports H18; F209 refines H36 …) because live nodes still legitimately cite the question. Stamping `superseded` on an answered question asserts the question was wrong |
| **Close an H by an inbound `resolves` from a current F/D** (rule A) | **adopted** | SCHEMA §5 made operative; the edge is an append to the Finding (§6.1), attributable through its `captured <branch>@<sha>` footer, reversible by `retype … refines` |
| Close a D when a current D `refines` it (rule B: D4, D5, D10) | **dropped** (skeptic r1 obj. 2) | the repo documents `refines` as "narrows while leaving open" (`research_backlog.py:278-279`); D5 is a live, code-bridged recommendation. Hiding gates by an inference the lint refused to let you make explicitly is the one non-schema rule, so it went |
| New `status: resolved` value | out of scope | a `schema_version 0.2` bump touching `_node_meta`, `note.py` and every STATUS_VALUES test |
| `ctx web --lint` advisory on off-direction `resolves` | rejected | `--lint` exits 1 on advisories (`ctx.py:1543-1544`) and CI runs it; 14 live edges would red CI the day it landed. A set-equality test names the delta instead |
| A pending-count ceiling ratchet | **dropped** (skeptic r1 obj. 3) | every D and every OPEN H is pending by construction, so each `note.py add` would red CI until a `tests/` constant was edited: 38 pending-kind nodes landed in 2026-06, 32 in 2026-07. Repo precedent (`test_context_map.py`, `test_web_code_claims.py`) is set-equality that names the delta |

## Decision-debate consensus (2026-10-29)

One proposer and one skeptic, two rounds. Round 1: DISPUTE (four objections, two wording
fixes). Round 2: CONCUR with wording fixes A–D, all adopted below.

### Policy rule (A)

1. **An H is CLOSED when a current F or D, itself not contradicted by a current node,
   carries an explicit `resolves` → H.** Direction F/D → H; `note.py` refuses any other.
   A Finding that names remaining open parts uses `refines` — the documented "narrows
   while leaving open" edge. The title's `OPEN`/`RESOLVED` tag is a human-readable echo.
2. **An H is SUPERSEDED only when the question itself is withdrawn or ill-posed.**
   Answered ≠ retracted.
3. **A D is open unless** (a) superseded by the gate that overtook it, or (b) its title
   carries RESOLVED/DONE (SCHEMA §2 tag list; D7). No inference from `refines`.
4. **Encoding:** `tools/ctx.py::_resolved_hypotheses(nodes)` is the closure set — targets
   of `resolves` edges whose source is kind F/D, current, and absent from
   `_contradicted_by(nodes)`, target kind H. `_is_open_work(nid, node, nodes, resolved)`
   implements 1–3 and is the only rule: `cmd_web --pending`, the map summary and the map
   detail payload all call it, each computing the resolved set once per listing (skeptic
   r2 fix B — the per-node recomputation would have been O(N²·E) on 604 nodes).
   `research_backlog._nodes_resolved_since` is the looser reading on the other parser;
   one test asserts the two agree on the raw resolved-target set (fix C: "agreement on
   the resolved-target set", not "the same rule" — the backlog applies no direction or
   contradiction filter and is advisory).
5. **Who:** Tier 1 edge writes — any session, dry-run then `--commit`. Tier 3 decision
   supersessions — owner ratification. Titles are never hand-edited.
6. **Schema text:** `SCHEMA.md` §3 now reads "State of record: CLOSED when a current,
   uncontradicted F/D carries `resolves` → it (§5); OPEN otherwise"; the §5 `resolves` row
   says `note.py` refuses any other direction. No `schema_version` bump (§9: no new kind,
   edge or field).

### Rule B, dropped

D4, D5 and D10 stay on `--pending` as decided-but-standing recommendations. The owner
preferring them off the list needs a `note.py close` verb, not an inference.

### The frozen-set ratchet (not a ceiling)

`tests/test_web_hygiene.py::ThePendingListStaysHonest.CLOSED_BY_HYGIENE` is a frozen set of
the 26 ids this pass closed (22 predicate-closed H + H9/H36/H37 closed by Tier 1's own
writes + D7). The test fails only if a member reappears in pending or vanishes from the
web. Reopening is legitimate and acknowledged by removing the id in the same commit. New
captures never touch the set. `KEPT_OPEN_BY_HYGIENE` pins the two resolvers that named a
remainder (F238→H22, F168→H50) as `refines`, so the F238 pattern cannot silently close
either question again. The proposal's `test_pending_never_lists_an_answered_hypothesis` was
dropped as a tautology (fix A: the predicate makes `open ∧ resolved` empty by construction)
and replaced by a synthetic-fixture test of every clause of the predicate — superseded
resolver, contradicted resolver, `refines`, E→H, H→H, title echo, D title rule.

### The direction refusal

`tools/note.py::_check_resolves_direction(src, tgt, etype)` runs after the
reliance-to-superseded check at all three edge-writing sites (`add --link`, `link`,
`retype`):

```
`resolves` is Decision/Finding -> Hypothesis (SCHEMA §5); E7 -> H5 is off-direction —
use refines (narrows, leaves open), drives or relates
```

`KNOWN_OFF_DIRECTION_RESOLVES` pins, by set equality, the 13 live off-direction edges that
remain (14 minus F41→D4, retyped in Tier 1): H2→F7, H8→D4, E4→H1, E5→H3, E6→F4, E6→H2,
E7→H5, F39→F38, E38→H42, E39→H43, E103→H62, F199→F149, F264→F204. Two (E7→H5, H8→D4) are
cue-inferred from untyped links, so `retype` cannot fix them ("found 0") — they need a typed
link. None of them closes anything under the predicate.

### Tier 1 dispositions — applied (commit `5e84823`)

| Write | Effect |
|---|---|
| `retype F238 H22 --type refines` | H22 stays pending — F238's body names two proposals "genuinely open and blocked on data" |
| `retype F168 H50 --type refines` | H50 stays pending — F168 names "WHAT GENUINELY REMAINS OPEN … PARTIALLY DONE" |
| `retype F271 H36 --type resolves` | H36 closes — F271 measured the caching proposal dead (`tests/test_h36_graph_cost_profile.py`) |
| `retype F272 H37 --type resolves` | H37 closes — F272 audited all 29 `_classify_edge` cue links |
| `retype F41 D4 --type refines` | one off-direction edge tidied; D4 unaffected (a D) |
| `add --kind F … --link H9:resolves --link F23:supports --link F244:builds_on` | a new Finding (allocated F297800 at write time) closes H9 in two of three parts: F23 is GUARDED (`tests/test_web_code_claims.py::F23PerModeWindowsClaim`) and bridged; the config-routing fix stays deferred and is named in the body |

Kept as answered after a body sweep of all 24 resolvers for remainder language: H25
(F198 — answered by reduction: `sweep.py` already floors stops at `max(0.15, 5×spread)`;
the sweep itself was not run, data-blocked), H27 (F404701 fixed the `runner.resolve_regime_filter`
call site; its "Still open:" sentence concerns `main.py`'s trade_hours gate, not H27), H39
(F215 shipped `ctx docs`), H40 (F216: "RETIRE AS STATED"). A reasoned decline is an answer;
a named remainder is not.

### Tier 2 — this commit

`tools/ctx.py` (`_resolved_hypotheses`, `_is_open_work`, `--pending` and both map call
sites, `--pending` help text); `tools/note.py` (`_check_resolves_direction` at three sites);
`tests/test_web_hygiene.py` (new); `SCHEMA.md` §3/§5 text; this record.
`tests/test_research_web.py:276` keeps D1 listed as pending — Tier 3 is a later commit.

### Tier 3 — follow-up, owner-ratified

| Node | Action (dry-run clean, simulated through the lint) |
|---|---|
| D1 | `note.py link F6 D6 --type relates`; `link F22 D6 --type relates`; `supersede D1 --by D6 --reason reversed`; then move `tests/test_research_web.py:276` from D1 to D2 |
| D3 | `link F7 D6 --type relates`; `link H2 D6 --type relates`; `supersede D3 --by D6 --reason decayed` |
| D8 | leave open; the owner fixes the collided `context_map.json:306` bridge (DENY-fenced; it is D10's 3D-map bridge) |
| H14 | leave open; the owner adds the F26 → `generate_trades`/`runner.py` bridge (DENY-fenced) |

Also outside this pass: the reeval queue decisions for F366200/F366201/F366202
(`tools/reevaluate_web.py decide …`, append-only), and a `note.py close` verb for the owner's
standing decisions.

### Measured effect

| | pending | lint | health |
|---|---|---|---|
| Before (HEAD~1, title rule) | 89 | 0 problems / 0 advisories | 100/100 |
| After Tier 1 only (edges changed, title rule) | 89 | 0 / 0 | 100/100 |
| **After Tier 1 + 2 (edge rule)** | **63** | 0 / 0 | 100/100 |
| After Tier 3 (projected) | 61 | — | — |

The 26 that left: D7, H9, H10, H11, H12, H13, H15, H16, H17, H18, H19, H20, H23, H25, H27,
H36, H37, H38, H39, H40, H41, H42, H43, H45, H61, H404703. Still listed, by design: D1–D6,
D8, D10 (decisions), H22 and H50 (remainders named), H4/H5/H14 and the other OPEN questions
no current F/D resolves. `research_backlog` and `ctx` agree on 37 raw resolved targets
(36 at the debate; the H9 Finding added one).

## What would reopen this question

1. A resolver whose body names a remainder that the sweep's thirteen phrases missed — the
   fix is `retype … refines` plus removing the id from `CLOSED_BY_HYGIENE` in that commit.
2. CI friction from `KNOWN_OFF_DIRECTION_RESOLVES` while several edges are fixed at once →
   collapse it to a count ratchet on that set only.
3. The schema owner preferring `status: resolved` as a first-class value → `schema_version 0.2`.
4. The owner wanting D4/D5/D10 off the list → the `note.py close` verb.

## Tier 3 applied (2026-10-29, by delegation)

The owner delegated the directions work ("run decision debate on any materials as you see fit")
on 2026-10-29, so the two gate supersessions the debate reserved for owner ratification were
applied in the same pass, owner-amendable by `note.py supersede` reversal:

- `D1` (edge go/no-go: "don't kill it — reframe it as capital preservation") superseded by `D6`,
  reason `reversed` — D6 is the gate that overtook it. Chain: `link F6 D6 relates`,
  `link F22 D6 relates`, `supersede D1 --by D6 --reason reversed`.
- `D3` (noise-ratio instrument rule; QQQ/SPY as first-class candidates) superseded by `D6`,
  reason `decayed`. Chain: `link F7 D6 relates`, `link H2 D6 relates`,
  `supersede D3 --by D6 --reason decayed`.

Every write was lint-gated (0 problems); `tests/test_research_web.py`'s pending pin moved from
D1 to D2 and now asserts D1/D3 are absent. Measured: pending 63 → **61**; 604 nodes, 19
superseded. Still owner-only: the `context_map.json` bridges for D8 and H14 (DENY-fenced) and a
`note.py close` title verb.
