# Skeptic, round 2 — seam slice 1a / 1b

Re-verified at `10d9437`, `python3`, no venv. Every claim below was run, not read.

## (a) Determinism — VERIFIED, root fix covers everything

`PYTHONHASHSEED=1` vs `=2` on `graph --json`: md5 `077579a8` vs `6c919718`. Nodes identical in order; edges identical as a set; **245** positions differ (proposer: 241 — seed-pair dependent) and **every one is `tested_by`**; `imports` never moves. `graph --html` also differs (`51ccb7f8`/`656a46b2`); `--ideas-only` is stable. `_import_graph` returns `dict[str, set]`, so the mechanism is exactly ctx.py:1677. Emulating Step 1 in-process (wrapping `_import_graph` to return sorted lists) makes **both** `graph --json` and `graph --html` byte-identical across seeds 1 and 2. The six "stable" baseline commands plus `neighbors`/`walk`/`related`/`impact` on code targets are all seed-stable today, so the base/head comparison is sound.

## (b) 1a against the pins — VERIFIED zero-risk

1a adds no `add_parser` (nothing for the `add_parser\("(\w+)"\)` guard or `AGENT_INDEX.md` to see), leaves `_serve_route` untouched (`test_research_web.py:1164` key set stays `{project,summary,nodes,edges,details}`), and no test reads `cmd_graph` stdout. `test_cli_smoke`'s `graph: []` smokes the summary branch only.

## (c) CLI-JSON consumers — VERIFIED none

`graph --json` / `ctx graph` appears in no `ops/`, `.github/`, `*.sh`, `*.yml`, `*.js`, `*.html`; `export_pages.py:328` and `research_ui.py:5414` call `build_graph`/`_render_graph_html` directly. Adding `contract`/`schema_version` breaks nothing.

## (d) Fresh-repo artifact set — VERIFIED sufficient, ordering correct

Copied `tools/{ctx.py,ui_tokens.py,vendor/}` (vendor = one 280 K d3 file) into a 3-file git repo: `init` dry-run exits 0 and writes nothing (`cmd_init` never calls `_manifest()`, so the no-manifest crash is not reached); `init --write` writes both files; `graph --json` / `web --lint` / `health` / `graph --html` exit 0; html has **no** `d3 is not vendored` banner; kinds `{area,config,module}`; zero `MONAD` strings. The pre-`init` `graph` call *would* crash until Step 10 — the proposal already puts that phase in 1b. Correct as written.

## (e) Contract-test assertions vs today's output

Full graph: edge types ⊆ `EDGE_TYPES ∪ bridge ∪ code` ✓, 0 duplicate `(from,to,type)` ✓, 0 dangling ✓, all statuses ∈ `STATUS_VALUES` ✓, node keys exactly `{id,kind,title,status}` ✓, no title > 120 ✓. **One assertion is false today:** `--ideas-only` kinds are `{D,E,F,H,code,config}` — the idea↔code bridge *targets* are pseudo-nodes that survive `include_code=False`. "kinds ⊆ `{F,H,E,D}`" is red on day one. Types in ideas-only ⊆ `EDGE_TYPES ∪ bridge` ✓.

## Remaining errors (all wording/spec, none design)

1. **Step 4** — `--ideas-only` kinds must read `⊆ SCHEMA["kinds"] ∪ {code, config}` (bridge pseudo-nodes), with `module`/`area` the kinds that must be *absent*.
2. **Step 6 / Step 14** — "`_DOC_PATH_RX` resolves all three new backticked paths" is false: the regex (`3102`, `[A-Za-z0-9_./-]+\.(py|…)`) admits neither `{},` nor an extension-less `vendor/`; the brace string matches nothing, so `drift` checks nothing. Write three separate paths — `tools/ctx.py`, `tools/ui_tokens.py`, `tools/vendor/d3.v7.8.5.min.js` — so the drift guard actually resolves them (the `.js` extension is also outside the regex; either extend it or accept that only the two `.py` paths are guarded, and say so).
3. **Step 12** — "`graph --html` output contains no `F\d+`" is false on a fresh repo: the template's own banner prose cites `F155/F159/F188/F204` and hex colours like `#F09595` match. Assert on `graph --json` node ids (and `--ideas-only` nodes `== []`), not on html bytes.
4. **Step 8** — one ENGINE banner at 1143 and RIM banners at 741/2517/3608 leaves ENGINE never re-opened after each RIM block (2743–3020 and 3229–3607 would read as RIM; 1000–1142 `doc_topology` is unlabelled). Put a banner at every boundary of the r1 region map — eight, not four.
5. Minor: `_NODE_REF_RX` is pinned at `test_ctx_drift.py:89/102` — keep the name as planned; `_areas_for_module` (515) does call `_manifest()` per module, so once-per-process is the right variant; the `_ui_tokens` rebuttal (foreign `tools/` at `sys.path[0]` under `--repo`) is correct — accepted.

## Rulings

**Slice 1a — CONCUR**, conditional on fix 1 (a one-line test-spec correction the Step-4 "Suite == baseline" check would itself catch) and fix 2 (doc wording). Everything else in 1a is verified against live output: root cause, coverage of the fix, zero pin exposure, artifact sufficiency, test ordering.

**Slice 1b — CONCUR**, with fixes 3 and 4 and the three carried-over r1 variants (scanned three-layer tuples, once-per-process spoken absence with `UNSCAFFOLDED`, triple `schema_version` + 12-row pin) as specified. The single planned assertion edit (`test_research_web.py:1164`) is the right one and the only one.

## Final wording fixes

- "all 241 differing edges" → "every differing edge (241–245 depending on seed pair) is `tested_by`".
- "`--ideas-only` kinds ⊆ {F,H,E,D}" → "⊆ kinds ∪ {code, config}; `module`/`area` absent".
- Step 6/14 copy list → three separate backticked paths; state which `drift` can resolve.
- Step 12 → "no `^[FHED]\d+$` id in `graph --json` nodes; `--ideas-only` nodes empty".
- Step 8 → "a banner at each of the eight region boundaries".
