# Proposal r2: research-web status hygiene (PROPOSER, after skeptic DISPUTE)

## Round 2 responses

| # | Objection | Verdict | What changed |
|---|---|---|---|
| 1 | F238 `resolves` H22 while naming two open, data-blocked proposals; no direction/kind guard anywhere | **ACCEPT (a)(b); (c) with variant** | (a) `retype F238 H22 --type refines` (dry-run clean). I then swept **all 24** resolver bodies for open/blocked language: **F168→H50** is the same pattern ("WHAT GENUINELY REMAINS OPEN … PARTIALLY DONE") → also retyped to `refines`. H25/H27/H39/H40 were examined and kept: F198 "answered without a sweep"; F404701 fixed H27's call site (`runner.resolve_regime_filter`, "before, every backtest ran the gate at its default True"); F215 shipped `ctx docs` (H39's first option, `tests/test_h39_doc_topology.py`); F216 "VERDICT ON H40: RETIRE AS STATED" (`tests/test_h40_served_map_dependency.py`). A reasoned decline is an answer; a named remainder is not. (b) refusal in `note.py` at the three edge-writing sites (`:456` add, `:519` link, `:548` retype), shape below. (c) **variant:** a set-ratchet test, not a lint advisory — `ctx web --lint` exits 1 on advisories (`ctx.py:1543-1544`) and CI runs it (`test.yml:70-73`), so an advisory would red CI today: there are **14** live off-direction `resolves` edges, not 3, and at least two (E7→H5, H8→D4) are cue-inferred from untyped links — `retype` fails on them ("expected exactly one [[H5\|resolves]] in E7, found 0"). The test names the 13 that remain after the one clean retype (F41→D4). |
| 2 | Rule B closes D4/D5/D10 by `refines`, which the repo documents as "narrows while leaving open" (`research_backlog.py:278-279`); D5 is code-bridged | **ACCEPT** | Rule B dropped. D4/D5/D10 stay on `--pending` as decided-but-standing recommendations. Baseline moves to **63** (89 − 22 predicate-closed H − D7 − H9/H36/H37, which Tier 1's own writes close; simulated, not arithmetic). The honest follow-up is a `note.py close` title verb for the owner; not in this pass. |
| 3 | Count ceiling fires on every legitimate capture (39/33 per month in 06/07) | **ACCEPT** | Re-measured: 38 (2026-06), 32 (2026-07), 6, 3, 11 undated. Ceiling replaced by a frozen `CLOSED_BY_HYGIENE` set that only forbids reopening; `test_pending_never_lists_an_answered_hypothesis` kept as the invariant. |
| 4 | `answered` must filter target kind; CLI-equals-predicate test duplicates `test_research_web.py:1007` | **ACCEPT** | `and e["target"][:1] == "H"` added; my duplicate test dropped (`test_open_work_flag_matches_the_pending_view` already pins it). |
| 5 | backlog cannot import the ctx predicate (different parser) | **ACCEPT** | Verified: `research_backlog._nodes_resolved_since(LAB.parse_web(...))` and the ctx-side set are **identical today (36 targets)**. Rule 4 now says "same rule, two parsers, one agreement test". |
| 6 | Rule 1 should require current **and uncontradicted** | **ACCEPT** | Uses `ctx._contradicted_by` (`ctx.py:1375`). Today's contradicted-current set {F15, F194, E132, F259, H404700} contains no resolver, so nothing moves. |
| — | SCHEMA §2:66 has no `APPLIED`; §3:84 says H state "lives in the title" and must be amended in the same commit | **ACCEPT** | Rule 3(b) is RESOLVED/DONE only. `SCHEMA.md:84` amendment text below; §9 needs no bump (no new kind, edge or field). D4 row corrected: 13 PROBLEMs (5 reliance + 8 propagation). |

## Question

`ctx web --pending` lists 89 items. 24 pending hypotheses already carry an inbound `resolves` from a current F/D; D7 is titled RESOLVED. Two tools define "open" differently. What closes an OPEN node, who may do it, what encodes it, and how do we keep the list from re-inflating without penalising capture?

## How pending is computed

- Rule: `tools/ctx.py:1584-1590` (`cmd_web --pending`) and `:2252-2256` (`_is_open_work`; consumers `:2307`, `:2346`): `not _is_superseded(node) and (D-prefix or title ^OPEN|IN PROGRESS)`. `_is_superseded` `:1365` → `_node_meta` `:1333-1362` (status block, else `[SUPERSEDED by X]` title tag). `resolves` edges are not consulted (`:1412` only exempts them from propagation).
- `tools/research_backlog.py:376-391` treats "`resolves` from a current node" as closed — on the `epistemic_audit_lab` parser (tuple edges, `status` key).
- Edge writes: `note.py` checks only vocabulary and reliance-to-superseded (`:456`, `:519`, `:548`); no direction or kind check. SCHEMA §5 (`SCHEMA.md:128`): `resolves | Decision/Finding → Hypothesis | Closes an open question`.
- Every command below was dry-run; verdicts quoted. The D1/D3 chains were simulated in memory through `note.apply_link`/`apply_supersede` + the same lint functions: 0 reliance, 0 propagation, 0 dangling.

## Disposition table (exact; dry-run first by omitting `--commit`)

**Tier 1 — safe in one session (web edges, lint-gated):**

| Node | Action | Command (all dry-run **clean**) |
|---|---|---|
| H22 | stays pending — F238 names two open proposals | `python3 tools/note.py retype F238 H22 --type refines --commit` |
| H50 | stays pending — F168 names the remaining parts | `python3 tools/note.py retype F168 H50 --type refines --commit` |
| H36 | close — F271 measured the proposal dead (`tests/test_h36_graph_cost_profile.py`) | `python3 tools/note.py retype F271 H36 --type resolves --commit` |
| H37 | close — F272 audited all 29 links | `python3 tools/note.py retype F272 H37 --type resolves --commit` |
| H9 | close two-thirds, defer the fix | `python3 tools/note.py add --kind F --title "H9 answered in two of three parts: F23 is GUARDED and bridged; the config-routing fix stays deferred" --body "<as dry-run: cites tests/test_web_code_claims.py::F23PerModeWindowsClaim, tests/test_f244_rsi_period_not_used_by_signal.py, context_map.json F23 bridge; (3) deferred — armed path>" --link H9:resolves --link F23:supports --link F244:builds_on --commit` (dry-run allocated F297800; two advisories only: no `evidenced_by` — it is an observation — and shared title terms) |
| F41→D4 | tidy one off-direction edge | `python3 tools/note.py retype F41 D4 --type refines --commit` |
| H10 H11 H12 H13 H15 H16 H17 H18 H19 H20 H23 H25 H27 H38 H39 H40 H41 H42 H43 H45 H61 H404703, D7 | close by the predicate change | **no web write** — these drop when `_is_open_work` honours F/D→H `resolves` (22 H) and the RESOLVED title (D7) |

**Tier 2 — code + schema, one commit (`tools/ctx.py`, `tools/note.py`, `tests/`, `SCHEMA.md` — all `can_edit` ALLOW):** `_is_open_work` revision; `--pending` calls it; `note.py` direction refusal; the four tests below; `SCHEMA.md:84` amendment; `tests/test_research_web.py:276` keeps D1.

**Tier 3 — owner-ratified (gates):**

| Node | Action | Commands (in order; simulated through the lint: clean) |
|---|---|---|
| D1 | supersede by the gate that overtook it | `note.py link F6 D6 --type relates --commit`; `note.py link F22 D6 --type relates --commit`; `note.py supersede D1 --by D6 --reason reversed --commit`; then edit `tests/test_research_web.py:276` (D1 → D2) |
| D3 | supersede, decayed | `note.py link F7 D6 --type relates --commit`; `note.py link H2 D6 --type relates --commit`; `note.py supersede D3 --by D6 --reason decayed --commit` |
| D8 | leave open; fix the collided bridge | owner edits `context_map.json:306` (DENY-fenced) — it is D10's 3D-map bridge |
| H14 | leave open; owner adds the F26 → `generate_trades`/`runner.py` bridge (DENY-fenced) | — |

**Tier 4 — unchanged:** D2 (self-closing: `tests/test_d2_walkforward_selector.py:78`), D4, D5, D6, D10 (standing decisions; rule B dropped).

**Reeval queue (append-only log; safe in-session):** `reevaluate_web.py decide F366200 --class positive_edge --action unadmitted_historical --by <agent> --evidence "tilt sub-claim replicates in sign only (F366201, SPA p 0.09-0.13); not registered"`; `… F366201 … unadmitted_historical … "SPA p 0.096; forward watch H366200"`; `F366202`: `reproduced` **only if** a `TR-` ledger run replays it via `tools/admit.py` (as F404713's did), else `unadmitted_historical`.

Effect (Tier 1 simulated in memory through the new predicate: 0 reliance, 0 propagation): 89 → **63** (Tier 1+2) → **61** after Tier 3.

## Policy rule

1. **An H is CLOSED when a current F or D, itself not contradicted by a current node, carries an explicit `resolves` → H.** Direction F/D → H is refused otherwise by `note.py`. A Finding that names remaining open parts uses `refines` — the repo's documented "narrows while leaving open" edge (`research_backlog.py:278-279`). This is SCHEMA §5:128 made operative.
2. **An H is SUPERSEDED only when the question itself is withdrawn or ill-posed.** Answered ≠ retracted; the lint refused 6 of 10 such attempts (D7 cites H11; F191 supports H18; F209 refines H36 …).
3. **A D is open unless** (a) superseded by the gate that overtook it (D1, D3 → D6) or (b) its title carries RESOLVED/DONE (SCHEMA §2:66; D7). No inference from `refines`.
4. **Encoding:** `_is_open_work(nid, node, nodes)` implements 1–3; `cmd_web --pending` calls it. `research_backlog._nodes_resolved_since` is the same rule on the epi parser; one test asserts the two agree on the live web.
5. **Who:** Tier 1 — any session, dry-run then `--commit`. Tier 3 — owner ratification (debate-record convention). Titles are never hand-edited (SCHEMA §6.6); a `note.py close` verb is the follow-up.
6. **Schema text:** `SCHEMA.md:84` becomes: *"State of record: CLOSED when a current, uncontradicted F/D carries `resolves` → it (§5); OPEN otherwise. The `OPEN`/`RESOLVED`/`DEAD` title tag is a human-readable echo."* No `schema_version` bump (§9: no new kind, edge or field).

## Ratchet and guards

`note.py` (three sites, after the reliance-to-superseded check):
```python
if ty == "resolves" and not (src[:1] in "FD" and tgt[:1] == "H"):
    sys.exit(f"`resolves` is Decision/Finding -> Hypothesis (SCHEMA §5); {src} -> {tgt} is "
             f"off-direction — use refines (narrows, leaves open), drives or relates")
```

`tools/ctx.py`:
```python
def _resolved_hypotheses(nodes):
    contra = _contradicted_by(nodes)
    return {e["target"] for nid, n in nodes.items()
            if nid[:1] in "FD" and not _is_superseded(n) and nid not in contra
            for e in n["edges"] if e["type"] == "resolves" and e["target"][:1] == "H"}

def _is_open_work(nid, node, nodes) -> bool:
    if _is_superseded(node): return False
    if nid[:1] == "D": return not re.match(r"\s*(RESOLVED|DONE)\b", node["title"], re.I)
    if nid in _resolved_hypotheses(nodes): return False
    return bool(re.match(r"\s*(OPEN|IN PROGRESS)\b", node["title"], re.I))
```

`tests/test_research_web.py`:
```python
class TestPendingHygiene(unittest.TestCase):
    # Frozen 2026-10-29 (hygiene debate r2). Members are H nodes a current F/D `resolves`
    # (incl. H9/H36/H37, closed by this pass's Tier 1 writes), plus D7 (title RESOLVED). Reopening one is legitimate but must be acknowledged:
    # remove it HERE in the same commit as the retype/supersede that reopens it.
    # New captures never touch this set — it only forbids silent reopening.
    CLOSED_BY_HYGIENE = frozenset({
        "D7", "H9", "H10", "H11", "H12", "H13", "H15", "H16", "H17", "H18", "H19", "H20",
        "H23", "H25", "H27", "H36", "H37", "H38", "H39", "H40", "H41", "H42", "H43", "H45",
        "H61", "H404703"})
    # 14 live `resolves` edges violate SCHEMA §5 direction; F41->D4 is retyped in this pass.
    # Two (E7->H5, H8->D4) are cue-inferred from untyped links and need a typed link.
    # Set-equality: fails if one appears (note.py should have refused) AND if one is
    # fixed (shrink the set — and enjoy it).
    KNOWN_OFF_DIRECTION_RESOLVES = frozenset({
        ("H2","F7"), ("H8","D4"), ("E4","H1"), ("E5","H3"), ("E6","F4"), ("E6","H2"),
        ("E7","H5"), ("F39","F38"), ("E38","H42"), ("E39","H43"), ("E103","H62"),
        ("F199","F149"), ("F264","F204")})

    def test_hygiene_closures_stay_closed(self):
        nodes = ctx._parse_web()[0]
        reopened = sorted(n for n in self.CLOSED_BY_HYGIENE
                          if n in nodes and ctx._is_open_work(n, nodes[n], nodes))
        gone = sorted(self.CLOSED_BY_HYGIENE - set(nodes))
        self.assertEqual((reopened, gone), ([], []),
            f"reopened without acknowledgement: {reopened}; vanished: {gone}. "
            "If reopening is intended, remove the id from CLOSED_BY_HYGIENE in this commit.")

    def test_pending_never_lists_an_answered_hypothesis(self):
        nodes = ctx._parse_web()[0]
        leak = sorted(p for p, n in nodes.items()
                      if ctx._is_open_work(p, n, nodes) and p in ctx._resolved_hypotheses(nodes))
        self.assertEqual(leak, [], "answered by a current, uncontradicted F/D yet still pending")

    def test_backlog_and_ctx_agree_on_resolved_targets(self):
        epi = LAB.parse_web(LAB.WEB.read_text(encoding="utf-8"))   # research_backlog's parser
        self.assertEqual({t for t, _ in RB._nodes_resolved_since(epi)},
                         {e["target"] for nid, n in ctx._parse_web()[0].items()
                          if not ctx._is_superseded(n) for e in n["edges"] if e["type"] == "resolves"})

    def test_off_direction_resolves_is_exactly_the_known_set(self):
        nodes = ctx._parse_web()[0]
        actual = {(nid, e["target"]) for nid, n in nodes.items() for e in n["edges"]
                  if e["type"] == "resolves" and not (nid[:1] in "FD" and e["target"][:1] == "H")}
        self.assertEqual(actual, self.KNOWN_OFF_DIRECTION_RESOLVES,
            f"new: {sorted(actual - self.KNOWN_OFF_DIRECTION_RESOLVES)}; "
            f"fixed: {sorted(self.KNOWN_OFF_DIRECTION_RESOLVES - actual)}")
```

## Objection and answer

**"Closing nodes by edge is revisionism in disguise."** Conceded in part: r1 leaned on §5:128 while `SCHEMA.md:84` made the title the state of record, and rule B was an inference the schema never licensed. Both are fixed — the amendment is in the same commit, rule B is gone. What stands: a `resolves` edge is an **append** to the Finding (§6.1); `ctx web H11` still prints the question and `← F186`; `retype … refines` reopens and the frozen set makes that visible; closure is attributable through the resolver's `captured <branch>@<sha>, <date>` footer; and the sweep that found F238/F168 is the rule working, not failing — the predicate now refuses the edge that would have hidden them.

## What would change your mind

1. A resolver whose body names a remainder that my sweep's vocabulary missed — I checked 24 bodies for 13 phrases; a second reader should spot-check H19, H20, H23, H45 (no hits, not read in full).
2. The owner preferring D4/D5 off the list → that needs the `close` verb, not an inference.
3. CI friction from `KNOWN_OFF_DIRECTION_RESOLVES` while someone fixes several at once → collapse to a count ratchet on that set only.
4. A `TR-` record for F366202 → `reproduced`.
