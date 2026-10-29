# Skeptic, round 1 — "engine seam" slice for `tools/ctx.py`

Checked at `10d9437` (one commit past the proposer's `2ef7c0c`; the diff is `tests/test_export_pages.py` only). `tools/ctx.py` 3,897 lines, last touched 2026-08-15, 0 commits in 60 days.

## Verification table

| Claim | Verdict | Evidence |
|---|---|---|
| Region map (30–47, 741–1000, 1143–1470, 1620–1891, 1892–2516, 2517–2742, 2836–3020, 3021–3228, 3229–3607, 3608–3798, 3799–) | VERIFIED | `def`/const boundaries land at 30/40/48, 741/995/1000, 1143, 1471, 1620/1625, 1892, 2517, 2743 (`cmd_serve`, unlisted but harmless), 2836, 3021, 3229, 3608, 3799 |
| `_graph_details`→`_redact` 2331 | VERIFIED | `_redact` also used at 782/990/3796 (all rim) |
| `cmd_frontier`→`_web_banner` 3490→`perf_summary` 3652 | VERIFIED | plus `cmd_brief` 3752 (rim) |
| `_ui_tokens` resolves `REPO/tools` 2444 | VERIFIED but not load-bearing | script dir is `sys.path[0]`; vendored d3 already resolves via `__file__` (2426) |
| Nothing consumes `graph --json` | VERIFIED | zero `cmd_graph` refs in tests; `export_pages.py:328`, `research_ui.py:5414` call `build_graph`/`_render_graph_html` directly; only mention is prose in `test_h36` |
| `/api/graph.json` exact-key pin | VERIFIED | `test_research_web.py:1164` `{"project","summary","nodes","edges","details"}` |
| AGENT_INDEX guard scrapes `add_parser\("(\w+)"\)` | VERIFIED | `test_context_map.py:259–270`; a top-level option is invisible to it |
| `note.py` own `KINDS`; tests inject via `ctx.WEB =` | VERIFIED, overstated | `note.py:38`, `[FHED]` at 246/253. Only `WEB` is ever reassigned (`test_research_web:41`, `test_h41:91`, `note.py:332`); nobody monkeypatches `REPO`/`MANIFEST`/`DB` |
| Import-time `REPO` capture = 4 globals | VERIFIED | only lines 31–33 derive from `REPO`; no `def f(x=REPO)` defaults; no test calls `ctx.main()` in-process |
| 38 files / 669 tests; 4 files = 164 green | VERIFIED / qualified | 38 modules → 669 tests, 165 s; **9 errors pre-exist** (5× missing `yfinance`, 4× missing `venv/bin/python`) — "green" holds for the four named files only |
| `graph --json` deterministic | **WRONG** | two runs differ (md5 `52876b82` vs `3a137bb9`); nodes identical, edges identical as a *set*, order differs from position 1945 (`tested_by`, built from `importers.get(dotted, ())` set iteration, 1677–1684). `PYTHONHASHSEED=0` → identical. Served route same defect |
| `[FHED]` at 169/1350/3021/3524; `idea` set 2236 | VERIFIED | 3021 is `[FDEH]`; `_is_idea_id` (1396) already uses `[A-Za-z]+\d+` — vocabulary is *already* inconsistent |
| No `tools/` dir-prefix area (new module ⇒ manifest edit) | VERIFIED | prefixes are only `src/research/`, `ops/`, `ops/systemd/` |
| health 170/100 in a fresh repo | repo-shape dependent | my 3-file repo: **110/100** (`cov = 6/4`); mechanism (init puts `__init__.py`+`ctx.py` in an area *and* the allowlist) confirmed |

## Probe reproduction

Fresh repo: `pkg/{__init__,alpha,beta}.py`, `main.py`, copied `tools/ctx.py`.

```
graph --json / route   → FileNotFoundError: .../context_map.json      (no manifest)
init --write           → discovered 3 area(s): main, pkg, tools · WROTE context_map.json · WROTE RESEARCH_WEB.md
graph --json           → exit 0; keys [edges,nodes,project]; 10 nodes / 9 edges; kinds {area,config,module}
web --lint             → "RESEARCH_WEB.md not found or empty."  exit 0
health                 → "CONTEXT HEALTH  110/100" · "6/4 non-allowlisted modules in an area (150%)"
perf                   → "...Do NOT fall back to the CLAUDE.md headline tables (SUPERSEDED). Run on the Pi..."
brief                  → "DEPLOY SYNC: UNKNOWN — drift renderer unavailable (ModuleNotFoundError)" + state.db rider
schema                 → "live/state.db not present."     drift → "experiments.jsonl ... sweep row"
graph --html           → banner "d3 is not vendored at tools/vendor/d3.v7.8.5.min.js"   (4th defect)
```

Rebinding only `REPO/MANIFEST/WEB/DB` in-process from MONAD's `ctx.py` at the probe: graph/health/lint/html/frontier/route/brief all OK, no MONAD module reaches the node set. The `--repo` design holds.

## Objections

1. **`ENGINE_API` is drafted, not measured — the guard is red on day one.** Diffing each consumer's `ctx.*` names against the proposed tuples: `note.py` uses 10 unlisted names (`REPO, WEB, _git, _manifest, policy_match, _stem, _tfidf, _cos, _FRONTIER_STOPWORDS, _superseder`), `research_ui.py` 3 (`_is_idea_id, _node_sort_key, _form25_population_response` — the last is a fourth SEC projection missing from `RIM_API`). That is a third layer (manifest/git/text-infra) the two-banner story hides. **Fix:** generate the tuples from the actual import set (AST scan) and add a `CORE_API` (or fold infra into ENGINE) before writing the guard; state the three layers in the banners.

2. **"Deterministic" is false; the contract test and the md5 kill-criterion inherit the flake.** Edge order is hash-seeded (above). "Two runs equal" would fail ~always without `PYTHONHASHSEED`. **Fix:** sort edges by `(from, to, type)` in `cmd_graph` *and* `_serve_route` (declare it as the one behaviour change), and run the base/head comparison on canonicalised JSON (sorted edges) — not raw md5.

3. **`_EMPTY_MANIFEST` as a silent default violates the repo's own absence doctrine.** `perf_summary` (917–920) insists absent/empty/measured are "all SPOKEN, never omitted" (F155/F159/F188). With a silent skeleton, `ctx health` on a repo with a mistyped path prints a confident score from nothing. **Fix:** return the skeleton *and* emit one stderr line ("no context_map.json at <path> — `ctx init --write`"); `health` prints `UNSCAFFOLDED` instead of a bar. The fresh-repo test asserts the line.

4. **Vocabulary drift is only half-closed.** The derivation list covers ctx's four regexes but not `note.py:246/253`; `_is_idea_id` already disagrees with `[FHED]`; and `schema_version` would exist in **three** unpinned places (`SCHEMA.md:1`, `RESEARCH_WEB.md:2`, code) plus the JSON. Today nothing pins SCHEMA.md §5a's 12 rows to `EDGE_TYPES` (`test_web_integrity` pins *content*⊆code, not doc=code). **Fix:** the contract test asserts the three `schema_version` strings are equal and `len(SCHEMA["edge_types"]) == 12 == §5a rows`; derive note.py's two regexes too; say which id grammar `_is_idea_id` follows. Keep `RELIANCE_EDGES` spelled in `note.cmd_link` — `test_note_link.py:148/156` string-pins it.

5. **"The slice makes CONTEXT_KIT true" is overstated.** It fixes one of three probe defects (the crash); score>100 and the rim prose stay. There is a fourth: step 1 "Copy `tools/ctx.py`" loses `tools/vendor/d3` and `tools/ui_tokens.py` (`graph --html` renders the not-vendored banner). `--repo` sidesteps copying, which is the real argument — make it, and change step 1 to "point `--repo` at your repo, or copy `tools/{ctx.py,ui_tokens.py,vendor/}`".

6. **Baseline the 9 pre-existing errors** so the before/after run has a defined green; otherwise "all 38 files" cannot be asserted green.

On (e): true, but secondary — VISION Stage 1 already says "no file move"; the fence is procedural (README permits approved edits), not technical. On (f): 165 s suite is not the cost; absorbing 1–2 is. 8–12 h is honest.

## Judgement on "speculative generality"

Mostly answered. `--repo` and the fresh-repo CI test are concrete, measured and cheap; the banners cost nothing. Speculation leaks in exactly one place — the API tuples were written from an idea of the surface, and measuring the surface changes the design (three layers, not two). That is an argument *for* the slice done right, not against it.

## Ruling: DISPUTE

Objections 1–3 must be answered (1 changes the design, 2 changes a behaviour, 3 contradicts repo doctrine). 4–6 are wording/scope.

## Wording fixes

- "deterministic (identical md5)" → "set-deterministic; edge order hash-seeded until sorted".
- "the same four globals tests already monkeypatch" → "the four globals; tests and `note.py` already reassign `WEB`".
- "170/100" → "> 100 (repo-shape dependent; 110 on a 3-file repo)".
- "three measurable ways" → "four" (vendor/ui_tokens not copied).
- "164 tests, green" stays; add "9 environment errors (yfinance, venv) elsewhere in the 38-file set, baselined".
