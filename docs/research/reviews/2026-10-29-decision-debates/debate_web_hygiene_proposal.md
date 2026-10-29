# Proposal: research-web status hygiene (PROPOSER, round 1)

## Question

`python3 tools/ctx.py web --pending` lists 89 items. Eight ctx-layer hypotheses (H10–H13, H15–H18) are OPEN while the commands they asked for exist and a current Finding carries `resolves` → them; D7 is titled RESOLVED and still listed; D1/D3 are "overtaken in substance" by D6 in their own words; 24 pending H nodes in total already have an inbound `resolves` from a current F/D. What rule closes an OPEN node, who may apply it, what encodes it, and how do we stop the list re-inflating?

## How pending is computed

- `tools/ctx.py:1584-1590` (`cmd_web --pending`) and `tools/ctx.py:2252-2256` (`_is_open_work`, used by the map) are **two copies** of one rule: `not _is_superseded(node) and (nid[:1]=="D" or title matches ^(OPEN|IN PROGRESS))`.
- `_is_superseded` (`ctx.py:1365-1367`) reads `_node_meta` (`ctx.py:1333-1362`): the `<!-- status: … -->` block, else a `[SUPERSEDED by X]` title tag. `STATUS_VALUES = {current, superseded, retracted}` (`ctx.py:1325`).
- `resolves` edges play **no part** in pending (`ctx.py:1412` only exempts them from propagation).
- `tools/research_backlog.py:376-391` (`_nodes_resolved_since`) uses the opposite definition — "closed by a `resolves` edge from a node that is still current" — so the backlog already treats H10–H18 as closed while `--pending` lists them. Two tools, one fact, diverging.
- `note.py supersede` is lint-gated (`note.py:465-483`, `_locked_commit`); I dry-ran every candidate below. Verdicts are quoted.

## Disposition table

| Node | Status now | Evidence (file:line / node) | Action |
|---|---|---|---|
| D1 | current; listed as D | Body: "Overtaken in substance by D4 and D6". Dry-run `supersede D1 --by D6 --reason reversed` **REFUSED**: F6, F22 cite D1 without D6 | `note.py link F6 D6 --type relates`; `link F22 D6 --type relates`; then supersede `--by D6 --reason reversed`. **Owner-ratified** (a go/no-go gate). Update `tests/test_research_web.py:276` (asserts D1 in pending). |
| D2 | current | F165; `tests/test_d2_walkforward_selector.py:78 D2IsStillOpenTests` fails when sweep.py references walk_forward; sweep.py has zero refs today | **Leave open.** Self-closing; owner = whoever wires it. This is the model for "named next step". |
| D3 | current | Rests on F7 (current). Its actions (QQQ/SPY production sweeps, E8 screener) are mooted by D6/F13/F25. Dry-run `--by D6` **REFUSED**: F6, F7, H2 need a D6 cite | 3 `relates` links, then supersede `--by D6 --reason decayed`. **Owner.** |
| D4 | current | D5 and D6 `refines` D4 (reliance edges), plus F21/F42/F181. Dry-run **REFUSED** (5 propagation hits; would also break invariant 2) | **Do not supersede** — D6 refines, not retracts, it. Close by rule B below (zero writes). |
| D5 | current | D6 `refines`, F22 `refines`, F177 `supports`. Dry-run **REFUSED** | Same as D4: rule B, zero writes. |
| D7 | current, title RESOLVED | Listed only because of the D prefix. Dry-run `--by F22` clean but semantically wrong (resolved ≠ retracted) | Rule A title-state; zero writes. |
| D8 | current, OPEN | `builds_on D6`; its trigger ("nothing clears 0.5%/mo net OOS") is now the admission program (`tools/admit.py`; H404702's forward window matures 2027-10-07 per `decisions.jsonl`). Its `context_map.json:306` bridge is the *collided* 3D-map D8 (H41 artifact) | **Leave open**; owner = admission gate. Separately: fix the misattributed bridge (fenced file → owner). |
| D6 | current | The live verdict; no D refines it | Stays. |
| H9 | OPEN; no inbound | Asks 1–2 done: `ctx claims` → F23 GUARDED by `tests/test_web_code_claims.py:223 F23PerModeWindowsClaim`; `tests/test_f244_rsi_period_not_used_by_signal.py`; bridge `context_map.json:289-292`. Ask 3 (routing fix on a branch) untouched. No F resolves H9 (F244 supports H26) | `note.py add --kind F` (3 lines citing the two tests) `--link H9:resolves`, noting the fix is deferred — the F187/H12 pattern. Safe in-session. |
| H10 | OPEN | F185 `resolves` (negative result); `tests/test_h10_narrative_traversal.py` | Rule A; zero writes. |
| H11 | OPEN | F186 `resolves`; `ctx.py:2950 semantic_staleness`, `:2997 cmd_stale`, `:3875` parser; `tests/test_ctx_semantic_staleness.py`. Supersede **REFUSED** (D7 cites H11) | Rule A. |
| H12 | OPEN | F187 `resolves`; `.github/workflows/test.yml:70-73` runs `ctx health` + `web --lint`; `tests/test_cli_smoke.py`; preflight half declined with reasons | Rule A. |
| H13 | OPEN | F178 `resolves`; `cmd_claims ctx.py:3229` now audits concerns/gated_by ("14 behavior-asserting (4 implemented_in, 10 concerns/gated_by) · 0 UNGUARDED") | Rule A. |
| H14 | OPEN; no inbound | **Not done**: `grep F26 context_map.json` → no bridge; only F16/D4 bridges name `generate_trades` (`:162`, `:378`). File is DENY-fenced | **Leave open**; owner. Next step: bridge F26 → `engine.py::generate_trades` + `runner.py`, guarded by a test asserting the gate is absent. |
| H15 | OPEN | F188 `resolves`; `cmd_drift ctx.py:3193`, parser `:3876`; `tests/test_ctx_drift.py`. Supersede **REFUSED** (H41, H55, F218 cite) | Rule A. |
| H16 | OPEN | F189 `resolves`; rider `ctx.py:912-937`; `tests/test_ctx_perf_rider.py` | Rule A. |
| H17 | OPEN | F190 `resolves` (clean negative); folded into `cmd_drift` at `ctx.py:3198-3201` | Rule A. |
| H18 | OPEN | F196 `resolves` (APPLIED with approval); `tests/test_branch_drift_guard.py`; `grep pi-ops live/CONTEXT.md` empty. Supersede **REFUSED** (F191 supports H18) | Rule A. |
| H36 | OPEN | F209 `refines`, F271 `relates` ("retired": caching target is 2% of cost; `ctx brief` makes 0 `build_graph` calls); `tests/test_h36_graph_cost_profile.py`. Supersede **REFUSED** (F209 reliance) | `note.py retype F271 H36 --type resolves`. Safe in-session. |
| H37 | OPEN | F272 `relates` ("audited: blast radius 29 links, all right today"). Supersede **REFUSED** (F181 cites) | `note.py retype F272 H37 --type resolves`. Safe in-session. |
| F366200 | market, queued #1 | Exposures real, XLE timing fails OOS, miner tilt holds sign but SPA p 0.09–0.13 | `decide --class positive_edge --action unadmitted_historical`, evidence: tilt sub-claim replicates in sign only (F366201), not registered. |
| F366201 | market, #2 | Title itself says "not registered"; forward watch H366200 open | `positive_edge / unadmitted_historical`, evidence: SPA p 0.096; H366200 is the forward record. |
| F366202 | market, #3 | SPA p 0.022, every era positive; forward watch H366201 open | `positive_edge`; `reproduced` **only if** a `TR-` ledger run replays it via `tools/admit.py` (as F404713 did), else `unadmitted_historical`. Decider must check the ledger. |

Effect: 89 → **64** under rule A (24 resolved H + D7), → **61** with rule B (D4, D5, D10).

## Policy rule

1. **An H node is CLOSED when a current F or D carries `resolves` → H.** This is SCHEMA §5 verbatim ("`resolves` | Decision/Finding → Hypothesis | Closes an open question") and the backlog's existing rule (`research_backlog.py:376`). Direction matters: E7→H5 and H8/F41→D4 do not count. Title retag to RESOLVED is optional cosmetics; the edge is the record.
2. **An H node is SUPERSEDED only when the question itself was ill-posed or withdrawn** (`withdrawn`/`merged`), never because it was answered. Supersession is for stale *claims* (SCHEMA §6.1); the lint refused 6 of 10 ctx-H dry-runs precisely because other live nodes still legitimately cite the question.
3. **A D node is open unless** (a) superseded by the gate that overtook it (D1, D3 → D6), (b) its title carries RESOLVED/APPLIED/DONE (D7; SCHEMA §2 lists these tags), or (c) a current D `refines` it — the refining D is the frontier gate (D4, D5, D10). No new status value; `schema_version` stays 0.1.
4. **Encoding:** `_is_open_work` (`ctx.py:2252`) implements 1–3; `cmd_web --pending` calls it instead of its private copy; `research_backlog.py` imports the same predicate.
5. **Who:** H closures (`link`/`retype`/`add --link H:resolves`) — any session, dry-run then `--commit`, lint-gated (SCHEMA §6.6). D supersessions — owner ratification (the debate-record convention: "Ratified by Hudson"); the propagation `relates` links can be staged in-session as dry-runs. No title edits by hand; a `note.py close <ID> --by <F|D>` verb is the follow-up, not a prerequisite.

## Ratchet

In `tests/test_research_web.py` (ALLOW):

```python
class TestPendingRatchet(unittest.TestCase):
    # Baseline 2026-10-29 after the hygiene pass. Bump ONLY in the commit that adds the
    # new OPEN node(s), and name them in that commit. Lowering is free and expected.
    PENDING_CEILING = 61   # was 89

    def _pending(self):
        nodes = ctx._parse_web()[0]
        return sorted((n for n, d in nodes.items() if ctx._is_open_work(n, d)),
                      key=ctx._node_sort_key), nodes

    def test_pending_count_does_not_rise_silently(self):
        pend, _ = self._pending()
        self.assertLessEqual(len(pend), self.PENDING_CEILING,
            f"--pending grew to {len(pend)} > {self.PENDING_CEILING}. New open work must be "
            f"acknowledged: raise PENDING_CEILING in this commit and name the node(s).\n{pend}")
        self.assertGreaterEqual(len(pend), self.PENDING_CEILING - 5,
            f"--pending fell to {len(pend)}: lower PENDING_CEILING so the ratchet stays tight")

    def test_pending_never_lists_an_answered_hypothesis(self):
        pend, nodes = self._pending()
        answered = {e["target"] for n, d in nodes.items() if n[:1] in "FD"
                    and not ctx._is_superseded(d) for e in d["edges"] if e["type"] == "resolves"}
        self.assertEqual([p for p in pend if p in answered], [],
                         "closed by a current `resolves` edge yet still on --pending")

    def test_pending_cli_matches_predicate(self):
        # ctx.py:1584 and ctx.py:2252 were two copies of one rule; keep them one.
        pend, _ = self._pending()
        out = self._web(pending=True)   # helper already in TestWebListingViews
        self.assertEqual(sorted(re.findall(r"^  ([A-Z]+\d+) ", out, re.M),
                                key=ctx._node_sort_key), pend)
```

Friction, stated: every new OPEN H bumps the constant by one line. That is the point — adding open work becomes an acknowledged act, mirroring the repo's `KNOWN_*` set-ratchets (`test_context_map.py:468`, `test_web_code_claims.py:475`). Slack of 5 on the floor so closures don't force an edit each time.

## Objection and answer

**"Closing nodes by edge is revisionism in disguise."**

Answer from the schema's own rules:
- §6.1 *append + supersede, never delete or rewrite*: a `resolves` edge is an **append** to the Finding. The H's title, body, date and provenance footer are untouched; `ctx web H11` still prints the whole question and `← linked by: F186`.
- §5 already defines `resolves` as "Closes an open question". I am not proposing a rule; I am proposing that `--pending` obey one the schema states and the backlog already enforces. Today the project has two definitions of "open" — that is the drift this repo keeps catching elsewhere (F188, F190).
- The revisionist move is the other one: stamping `status: superseded` on an answered question asserts the question was wrong. The lint agrees — it refused D1, D3, D4, D5, D8, H11, H15, H18, H36, H37.
- Attributable and reversible: the closing F carries `captured <branch>@<sha>, <date>`; `retype … --type supports` reopens; `ctx delta --since` records the count drop with ids.
- Rule B is the only inference, bounded to three D→D `refines` edges each written by hand in the refining decision's own body ("Refines [[D4|refines]]").

## What would change your mind

1. A real `resolves` edge whose source body says "blocked, not tested" — the H46 incident (`research_backlog.py:283`) was a `relates`, but one `resolves` misuse would force a title co-signal or ANSWERING_EDGES-style vetting.
2. The owner wanting D4/D5 visible as standing recommendations → drop rule B; baseline 64.
3. More than ~1 ceiling bump per week → switch to a `KNOWN_PENDING` set-ratchet or age-scope it.
4. The schema owner preferring `status: resolved` → that is a 0.2 bump touching `_node_meta`, `note.py` and every STATUS_VALUES test; out of scope here.
5. A `TR-` record for F366202 → its action flips to `reproduced`.
