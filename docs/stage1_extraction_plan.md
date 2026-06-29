# Stage 1 — `ctx.py` engine/adapter seam (FILE-LEVEL PLAN, no code change yet)

> **Status: PLAN ONLY.** Nothing here is implemented. Stage 1 draws a clean
> **generic-evidence-graph-engine ⟂ MONAD-adapter** seam *inside* `tools/ctx.py`
> (and `tools/note.py`) **with zero behavior change**, as preparation for an eventual
> open-source extraction. It moves **no files**, externalizes **no vocab**, and adds
> **no node/edge kinds**. See [`VISION.md`](../VISION.md) (Stage 1 row) and
> [`SCHEMA.md`](../SCHEMA.md).
>
> Line ranges are as of the current `tools/ctx.py` (2,381 lines) / `tools/note.py`.

## 0. The shape of the problem

`tools/ctx.py` is a single 2,381-line stdlib CLI with **35 subcommands** dispatched by
`main()` (≈2310–2377) via `set_defaults(fn=cmd_*) → args.fn(args)`. It fuses three
concerns that *want* to be separate:

- a **generic evidence-graph engine** (parse/edge/lint/traverse/render over the
  `RESEARCH_WEB.md` markdown — pure over a string + stdlib),
- a **generic code-map layer** (AST/import introspection + the `context_map.json`
  manifest presenters), and
- a **MONAD adapter** (live `state.db` taps, `config.py` reads, `ops/` shell-outs,
  IBKR redaction, the live-boundary verdict).

The seam is *cleaner than it looks* — **no `config`/`state.db` read hides inside the
pure engine** (verified) — but it is crossed in a few non-obvious places (§5).

---

## 1. Function-group map

| Group | Functions (line ranges) | Class | Depends on |
|---|---|---|---|
| **Generic graph parser** | `_parse_web` (915), `_parse_web_text` (923–961), `_LINK_RX`/header regex | engine | `WEB` string only |
| **Generic edge/type handling** | `_classify_edge` (891–912), `RELIANCE_EDGES`/`EDGE_TYPES`/`_EDGE_CUES` (866–888) | engine | stdlib |
| **Generic lint/integrity** | inline `web --lint` block in `cmd_web` (≈1128–1182), `_propagation_violations` (1060–1082) + `_PROPAGATION_EXEMPT` (1057), partial dup in `cmd_health` (1720) | engine | nodes dict |
| **Status / supersession model** | `_node_meta` (978), `_is_superseded` (1010), `_superseder` (1015), `_contradicted_by` (1020), `STATUS_VALUES`/`REASON_CODES` | engine | nodes dict |
| **Traversal / why / frontier / related** | `cmd_web` (1116), `build_graph` (1261–1330 — *seam*, §5), `cmd_neighbors` (1351), `cmd_walk` (1367), `cmd_why` (1436–1512), `cmd_contradicts` (1515), `cmd_frontier` (1991), `cmd_related` (2117) + TF-IDF `_strip_markup`/`_doc_terms`/`_tfidf`/`_cos` (2074–2113), `_reliance_closure`/`_effective_conf`/`_n_evidence` (1391–1433) | engine (via `build_graph`) | `WEB` + manifest (through `build_graph`) |
| **Renderer / graph export** | `_graph_compact` (1607), `_render_graph_html` (1624) + `_GRAPH_HTML`, `cmd_graph` (1638–1672), graph `--json` shape (1661–1666), `cmd_serve` (1675) | engine/renderer | built graph |
| **Code map / AST extraction** | `_iter_py` (217), `_import_graph` (496), `_module_summary` (305), `_first_party_modules` (323), `_symbol_module` (389), `cmd_where` (124), `cmd_usages` (226), `cmd_defs` (259), `cmd_tree` (332), `cmd_find` (149) | code_map | repo AST (+ manifest for `find` annotations) |
| **Manifest presenters** | `_manifest` (47), `cmd_route` (102), `cmd_map` (828), `cmd_summary` (356), `cmd_covers` (431), `cmd_tests` (850), `_areas_for_module` (404), `_tests_grepping` (415), `_graph_bridges` (1087) + `_bridge_*` (1092/1097), `cmd_init` (1913) | code_map | `context_map.json` |
| **MONAD live-ops** | `cmd_status` (814 → `ops/status_check.sh`), `cmd_uncaptured` (2227), `cmd_brief` (2247), `cmd_reverts` (2293) | adapter | `ops/`, git, redaction |
| **MONAD perf/status/state.db** | `cmd_schema` (630), `cmd_events` (646), `cmd_perf` (782) + `_compound` (775), `cmd_config` (674), `cmd_audit` (757) + `config_comment_drift` (723) + `_PCT_PARAM_RX`, constants `DB`/`PROD`/`CONFIRMED` (32–34) | adapter | `state.db`, `config.py` |
| **Edit fence / live-boundary** | `policy_match` (465 — *pure*), `cmd_can_edit` (479), `cmd_impact` (539 — blast-radius generic, verdict MONAD), `_live_boundary_modules` (526), `_is_protected` (535) | adapter (mechanism partly generic) | `context_map.json` `edit_policy` |
| **Redaction** | `_redact` (39), `_ACCT`/`_CONID` (35–36) | adapter | — |

---

## 2. Which pieces are the generic evidence-graph engine

The **pure-over-string heart** — verified to touch *only* the `WEB` markdown + stdlib,
with **no `config` import and no `sqlite3`/`state.db`**:

- `_parse_web_text` (923–961) — markdown → `{id:{title,body,links,edges}}` + reverse map.
- `_classify_edge` (891–912) incl. the negation guard (904–906).
- the edge vocabulary `RELIANCE_EDGES`/`EDGE_TYPES`/`_EDGE_CUES`/`_LINK_RX` (866–888) — `_LINK_RX` is already prefix-agnostic (`[A-Za-z]+\d+`).
- supersession model `_node_meta`/`_is_superseded`/`_superseder`/`_contradicted_by` (978–1031).
- `_propagation_violations` (1060–1082) — the supersession-integrity invariant.
- confidence/evidence advisory `_reliance_closure`/`_effective_conf`/`_n_evidence` (1391–1433).
- `_node_sort_key` (1034) + `_is_idea_id` (1041) — **the correct prefix-agnostic pattern**.
- the TF-IDF stack `_strip_markup`/`_doc_terms`/`_tfidf`/`_cos` (2074–2113).
- renderer `_graph_compact` (1607), `_render_graph_html` (1624), graph `--json` contract (1661–1666).
- AST/code-map introspection `cmd_where`/`usages`/`defs`/`tree`/`init` (repo-agnostic).
- `policy_match` (465) — pure fnmatch matcher.
- (`note.py`) `_weblock`/`_locked_commit` — domain-agnostic flock + atomic write.

## 3. Which pieces are the MONAD adapter / project-specific (KEEP)

These are the *plugin* layer — bound to live artifacts; **do not genericize, do not move**:

- `state.db` taps: `cmd_schema` (630), `cmd_events` (646), `cmd_perf`+`_compound` (775–811); constants `DB`/`PROD`/`CONFIRMED` (32–34).
- `config.py` readers: `cmd_config` (674), `cmd_audit`+`config_comment_drift`+`_PCT_PARAM_RX` (705–772).
- `ops/` shell-out: `cmd_status` (814).
- IBKR redaction: `_redact` (39), `_ACCT`/`_CONID` (35–36).
- live-boundary: `cmd_impact`'s LIVE/PROTECTED verdict (616–621) + config-key fan-out (564–578), `_live_boundary_modules` (526), `_is_protected` (535).
- edit-fence framing: `cmd_can_edit` (479) DENY wording (armed-trader/secret/raw-DB).
- `cmd_uncaptured`/`brief`/`reverts` — git + redaction + the MONAD safety banner.
- (`note.py`) `cmd_draft` (343–484) — `experiments.jsonl` sweep-journal parser with hardcoded E2/E3 parents (the one MONAD-specific *writer*).

## 4. The in-between: code-map / manifest presenters (stay, schema-bound)

`cmd_route`/`map`/`summary`/`covers`/`tests`/`web`/`neighbors`/`walk`/`why`/`contradicts`
read manifest/web **structure** generically but are bound to the `context_map.json`
*schema* and (some) to the F/H/E/D taxonomy. They are portable *with the manifest schema*
— so they **stay in `ctx.py` for all of Stage 1** and would extract *with* a
`ctxkit.manifest` module later (§7).

---

## 5. Hidden couplings (the hardest truths — read before touching anything)

1. **`build_graph` (1261–1330) is the real seam, not the parser.** `cmd_neighbors`/`walk`/
   `why`/`contradicts`/`frontier` *look* like pure graph renderers, but each calls
   `build_graph`, whose `include_code=True` branch reads manifest areas/bridges **and scans
   repo source for `config.*`**. Label it the adapter seam in 1B; never assume the
   traversal commands are pure.
2. **Two live `[FHED]` regex warts in "generic" code:** `_node_meta` title-tag fallback
   (L995, `\[(SUPERSEDED|RETRACTED) by ([FHED]\d+)\]`) and `_strip_markup` (L2078) only
   recognize F/H/E/D prefixes. Widening these is a **deliberate, diffed** behavior change —
   the body of Stage 1D, gated behind a characterization test.
3. **`cmd_why` provenance is hardwired to E/D** (L1460 `tgt[:1]==prefix` for `'E'`/`'D'`);
   `cmd_web --pending` keys `'D'` (1225) and the bucket listing hardcodes `{F,H,E,D}` labels
   (1235). These are the prefix assumptions 1D externalizes.
4. **No `config`/`state.db` read hides in the pure engine (VERIFIED).** The only
   `sqlite3.connect(file:{DB}?mode=ro)` sites are `cmd_schema`/`events`/`perf`; the only
   `import config` is in `cmd_config`. The engine is genuinely separable.
5. **`note.py` depends on ctx's MODULE SHAPE, not just its behavior.** It does `import ctx`
   and binds ~16 names (`ctx.REPO`, `ctx.WEB`, `ctx._manifest`, `ctx.policy_match`,
   `ctx._parse_web`, `ctx._git`, the vocab constants, …). **Every one of those names must
   stay at module scope with the same spelling through all of Stage 1.**
6. **`REPO` (L29, `__file__`-derived) is load-bearing for fail-closed safety**, not just
   convenience: `note.py`'s `_fence` and the `edit_policy` deny-fence resolve writability
   against it. 1E must keep module-level `REPO`/`WEB`/`MANIFEST`/`DB` as the **unchanged
   default**; the new flag only *overrides*.
7. **The lint has no home:** it is an inline `if getattr(args,'lint',False):` block inside
   `cmd_web` (≈1128–1182), partially **duplicated** in `cmd_health` (1720). 1C may make it a
   named helper, but **only as a pure extraction with byte-identical output**.

---

## 6. What stays in `tools/ctx.py` during Stage 1

**Everything.** Stage 1 moves zero functions to other files. All 35 `cmd_*` handlers stay
registered exactly as-is; the module constants stay as module-level defaults; `note.py`
stays fully intact and its `import ctx` boundary stays valid. The engine pieces are
*labelled* as the future package boundary but physically remain in `ctx.py`.

## 7. What should move eventually (Stage 2+ — PROPOSED, do NOT create now)

| Proposed module | Contents | Rationale |
|---|---|---|
| `ctxkit/graph.py` | `_parse_web_text`, `_classify_edge`, vocab, `_node_meta`/supersession, `_propagation_violations`, confidence helpers | the portable evidence-graph heart |
| `ctxkit/codemap.py` | `_iter_py`, `_import_graph`, `_module_summary`, `_first_party_modules`, `_symbol_module`, `cmd_where`/`usages`/`defs`/`tree` cores | repo-agnostic AST introspection |
| `ctxkit/render.py` | `_graph_compact`, `_render_graph_html`, `_GRAPH_HTML`, graph `--json` serializer, `cmd_serve` http | repo-agnostic visualization |
| `ctxkit/manifest.py` | manifest loader + `_areas_for_module`, `_graph_bridges`, `_bridge_*` | schema-bearing; extracts *with* its schema |
| `ctxkit/policy.py` | `policy_match` | pure glob matcher |
| `ctxkit/writelock.py` | `note.py` `_weblock`/`_locked_commit` | generic atomic-write concurrency |
| **stays in `MONAD-quant/tools/` (NOT a kit module)** | all `state.db`/`config`/`ops`/IBKR commands, `cmd_impact` verdict, `_is_protected`/`_live_boundary_modules`, `_redact`, `build_graph`'s `include_code` adapter half, `note.py` `cmd_draft` | the MONAD reference plugin |

---

## 8. Test plan BEFORE any refactor (the 1A prerequisites)

| Test | Covers | Status |
|---|---|---|
| **`tests/test_ctx_cli_smoke.py`** *(NEW — #1 prerequisite)* | subprocess-invoke `ctx.py <cmd>` for all 35 subcommands (read-only, safe args): assert exit code + stable stdout substrings. `main()` dispatch (2310–2377). | **GAP (critical)** — no test invokes `main()` today |
| **graph `--json` contract snapshot** *(NEW)* | pin the `{project,nodes[id,kind,title,status],edges[from,to,type]}` shape byte-stable (1661–1666, `build_graph`, `_graph_compact`) | **GAP** — shape unpinned |
| **engine-core characterization** *(extend `test_research_web.py`)* | explicit `_parse_web_text` round-trip + `_classify_edge` negation guard (904–906) + `_propagation_violations` table | **PARTIAL** — parser/lint exercised; guard/rank-dedup unpinned |
| **`[FHED]` characterization** *(NEW)* | pin CURRENT behavior of `_node_meta` (L995) + `_strip_markup` (L2078) on F/H/E/D **and** a non-FHED prefix (e.g. `AP12`) — the before/after anchor for 1D | **GAP** |
| **`cmd_why` E/D provenance pin** *(NEW)* | assert `paths_to` (L1460) finds E/D ancestors on the real web | **GAP** |
| **gating exit-codes** | `web --lint` (2/1/0), `can_edit` (0/2/1), `audit` (1 on drift), `health` | **PARTIAL** — logic covered (`test_research_web`, `test_edit_policy`, `test_config_comment_matches_value`); no end-to-end CLI exit assertion |
| **note.py write-contract regression** | re-run existing **`test_note.py`** (dangling/reliance/propagation/`_fence`/dry-run) after each stage — the tripwire for any renamed symbol it imports | **EXISTS (strong)** |
| **`--repo` parametrization** *(NEW — 1E)* | run ctx against a tmp fixture repo; assert no-flag default still resolves to MONAD repo unchanged | **GAP (net-new in 1E)** |

Existing relevant suites to keep green throughout: `test_research_web`, `test_context_map`,
`test_area_coverage`, `test_note`, `test_edit_policy`, `test_config_comment_matches_value`.

---

## 9. Risk analysis

| Risk | Category | Mitigation |
|---|---|---|
| 1C renames/reorders a symbol `note.py` imports by name (the ~16 bound names, §5.5) | breaks_ci | Keep ALL public-to-`note.py` names identical and at module scope through Stage 1; re-run `test_note.py` after every step. |
| A downstream consumer parses ctx stdout (e.g. `monad-dashboard.service`, hooks) | breaks_web | 1A smoke test **snapshots stdout before any change**; 1B/1C assert byte-identical output. |
| `build_graph`'s `include_code` coupling silently broadens the "engine" (§5.1) | harder_public_extraction | Label it the ADAPTER seam in 1B; isolate the `include_code` branch behind the seam comment. |
| 1D widening the `[FHED]` regexes changes parsing of an existing title-tag | breaks_ci | Gate 1D behind the `[FHED]` characterization test (green first); review the parse diff deliberately. |
| Running the smoke suite touches `state.db`/`ops` | touches_live_ops | All DB opens are `file:…?mode=ro` and guard `os.path.exists(DB)`; smoke tests only **read**; never invoke writers or `--write`. |
| 1D edits the **self-fenced** `context_map.json` | touches_live_ops | 1D externalizes vocab into **NEW sidecar files**, NOT edits to the fenced manifest (and only with trader-stopped + approval if the manifest is ever touched). |
| 1E `--repo` introduces a second source of truth for `REPO`; a bug could mis-resolve the fence | touches_live_ops | Keep module-level `REPO`/`WEB`/`MANIFEST`/`DB` as the unchanged default; the flag only overrides; add the default-path regression test. |

---

## 10–11. Staged sequence — commands & exact acceptance

Each stage is independently committable and reversible. **Do not start a stage until the
prior stage's acceptance is met.**

### Stage 1A — characterization tests around current behavior (ZERO production change)
**Work:** add `tests/test_ctx_cli_smoke.py` (subprocess every read-only subcommand) + the
graph `--json` contract snapshot + the `[FHED]`/`cmd_why` characterization pins. Snapshot
baselines for any downstream stdout consumer.
```
grep -rn 'ctx.py' ops/ live/ tools/ deploy/ 2>/dev/null     # find stdout consumers to snapshot
venv/bin/python tools/ctx.py graph --json > /tmp/baseline.json
venv/bin/python -m unittest tests.test_ctx_cli_smoke -v
venv/bin/python -m unittest tests.test_research_web tests.test_note tests.test_edit_policy
```
**Acceptance:** all new + existing tests GREEN; smoke covers ≥33/35 subcommands with pinned
exit codes (`web --lint`=0, `can_edit` on a safe path=0, `audit`=0); **`git diff` shows no
change under `tools/`** (tests-only).

### Stage 1B — in-file section-boundary comments ONLY
**Work:** insert banner comments in `ctx.py`/`note.py` delineating `ENGINE: GRAPH`,
`ENGINE: CODE-MAP/AST`, `ENGINE: RENDER`, `ADAPTER: STATE.DB/CONFIG/OPS`,
`ADAPTER: FENCE/REDACTION`, and mark `build_graph`'s `include_code` branch as the adapter seam.
```
git diff --stat                                              # comment-only additions
venv/bin/python tools/ctx.py graph --json > /tmp/after.json && diff /tmp/baseline.json /tmp/after.json
venv/bin/python -m unittest tests.test_ctx_cli_smoke tests.test_research_web tests.test_note
```
**Acceptance:** all 1A tests GREEN with **byte-identical** `graph --json` and snapshotted
stdout; `git diff` contains **only comment lines** (no `def`/`return`/expression edits);
fully reversible by deleting the comments.

### Stage 1C — internal helper grouping (same file, no behavior change)
**Work:** reorder top-level helpers so engine helpers are contiguous and adapter helpers are
contiguous; optionally fold the duplicated lint into one **named, pure** helper called by
both `cmd_web` and `cmd_health`. No signature, name, or logic change.
```
venv/bin/python -m unittest discover tests
venv/bin/python -c "import sys;sys.path.insert(0,'tools');import ctx,note;print(ctx.REPO,ctx.WEB,bool(ctx._parse_web))"
git diff -M --stat                                           # rename-detection: pure moves
venv/bin/python tools/ctx.py graph --json | diff /tmp/baseline.json -
```
**Acceptance:** full `unittest discover` GREEN incl. `test_note.py`; stdout byte-identical to
the 1A baseline; `git diff -M` shows moved blocks with **no intra-block edits**; `note.py`'s
~16 imported `ctx.*` names all still resolve.

### Stage 1D — externalize vocab/schema into sidecar files (only after 1A–1C green)
**Work:** lift `EDGE_TYPES`/`RELIANCE_EDGES`/`STATUS_VALUES`/`REASON_CODES` (and the
F/H/E/D kind set) into a versioned sidecar the engine loads; widen the `[FHED]` warts
(L995/L2078) + `cmd_why` E/D + `--pending` `D` to read from the vocab. **New sidecar files —
never edit the fenced `context_map.json`.** *(This is the first stage that changes behavior;
keep it tightly scoped and characterization-gated.)*
```
venv/bin/python -m unittest tests.test_research_web -v       # FHED/E-D pins updated DELIBERATELY
venv/bin/python tools/ctx.py web --lint                      # exit 0 on the real web after widening
venv/bin/python tools/note.py add --kind F --title t --body x   # dry-run: write-side vocab still matches
venv/bin/python -m unittest discover tests
```
**Acceptance:** `web --lint` exits 0 on the real `RESEARCH_WEB.md` **before and after**
widening; the `[FHED]` characterization tests are updated to assert the NEW generic behavior
(reviewed diff); `note.py` (which reuses ctx vocab) still lints + dry-runs clean; node count
unchanged (130).

### Stage 1E — optional `--repo` / `--config-path` / `--web-path`
**Work:** add a path-resolution layer over `REPO`/`MANIFEST`/`WEB`/`DB` (29–32): resolve from
args-or-default. Module-level constants remain the default; the flag only overrides.
```
venv/bin/python tools/ctx.py graph --json | diff /tmp/baseline.json -    # no flag → identical
venv/bin/python tools/ctx.py --repo /tmp/fixture_repo tree              # operates on fixture
venv/bin/python -m unittest tests.test_ctx_repo_flag tests.test_note
```
**Acceptance:** with **no flag**, every command is byte-identical to the 1A baseline; with
`--repo FIXTURE`, `where`/`tree`/`defs`/`usages`/`init` operate on the fixture; `note.py`'s
`_fence` test still asserts the deny-fence resolves against the (unchanged) default `REPO`.

---

## What Stage 1 explicitly does NOT do
No file moves; no `ctxkit` package; no `schema.json` adoption beyond the 1D *sidecar* (still
in-repo); no new node kinds or edges; no change to live trading, `state.db`, `config`, broker,
ops, or services. The actual package split is **Stage 4**; the plugin/integration seam is
**Stage 2**; the quant-domain ontology is **Stage 3**.
